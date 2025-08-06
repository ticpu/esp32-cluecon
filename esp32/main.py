import gc
import time
try:
    import ujson as json
except ImportError:
    import json
import urequests
import uasyncio as asyncio
from machine import Pin
import neopixel
from collections import deque
import config
from upagekite_handler import start_pagekite_tunnel, is_pagekite_running
from signalwire_hooks import SignalWireHooks
from http_utils import HTTPResponse, HTTPRequest, HTTPRequestHandler
from sentiment_analyzer import SentimentAnalyzer

# Fragment Assembler for handling PageKite request fragmentation
class FragmentAssembler:
    def __init__(self):
        self.fragment_buffer = {}  # Track fragments by connection
        self.timeout_ms = 2000     # 2 second timeout for fragments
        
    def is_fragment(self, request_str):
        """Detect if this looks like a fragment by checking if it's a valid HTTP request"""
        if not request_str or len(request_str.strip()) == 0:
            return False
            
        # A valid HTTP request must:
        # 1. Start with HTTP method
        # 2. Have proper HTTP version
        # 3. Have complete headers ending with \r\n\r\n or \n\n
        
        if not self.is_valid_http_request(request_str):
            # Not a valid HTTP request = fragment
            first_line = request_str.split('\n')[0].strip()
            if config.DEBUG:
                print(f"Fragment detected: {first_line[:50]}...")
            return True
            
        return False
    
    def is_valid_http_request(self, request_str):
        """Check if this is a complete, valid HTTP request"""
        lines = request_str.split('\n')
        if not lines:
            return False
            
        # Check first line: METHOD /path HTTP/version
        first_line = lines[0].strip()
        parts = first_line.split()
        
        if len(parts) != 3:
            return False
            
        method, path, version = parts
        
        # Valid HTTP methods
        http_methods = ['GET', 'POST', 'PUT', 'DELETE', 'HEAD', 'OPTIONS', 'PATCH']
        if method not in http_methods:
            return False
            
        # Valid HTTP version
        if not version.startswith('HTTP/'):
            return False
            
        # Must have path starting with /
        if not path.startswith('/'):
            return False
            
        # Check for end of headers
        has_header_end = '\r\n\r\n' in request_str or '\n\n' in request_str
        if not has_header_end:
            return False
            
        return True
    
        
    def add_fragment(self, connection_id, fragment):
        """Add fragment to buffer for connection"""
        if connection_id not in self.fragment_buffer:
            self.fragment_buffer[connection_id] = {
                'fragments': [],
                'timestamp': time.ticks_ms()
            }
        
        self.fragment_buffer[connection_id]['fragments'].append(fragment)
        if config.DEBUG:
            print(f"Added fragment for connection {connection_id}: {len(self.fragment_buffer[connection_id]['fragments'])} total")
    
    def assemble_with_fragments(self, connection_id, current_request):
        """Assemble current request with any buffered fragments"""
        if connection_id not in self.fragment_buffer:
            return current_request
            
        fragments = self.fragment_buffer[connection_id]['fragments']
        if not fragments:
            return current_request
            
        # Assemble: current_request + all fragments  
        assembled = current_request
        for fragment in fragments:
            assembled += fragment
            
        if config.DEBUG:
            print(f"Assembled request from {len(fragments)} fragments: {len(assembled)} total chars")
            
        return assembled
    
    def clear_fragments(self, connection_id):
        """Clear fragments for connection"""
        if connection_id in self.fragment_buffer:
            del self.fragment_buffer[connection_id]
    
    def cleanup_expired_fragments(self):
        """Remove expired fragments to prevent memory leaks"""
        current_time = time.ticks_ms()
        expired_connections = []
        
        for conn_id, data in self.fragment_buffer.items():
            if time.ticks_diff(current_time, data['timestamp']) > self.timeout_ms:
                expired_connections.append(conn_id)
        
        for conn_id in expired_connections:
            if config.DEBUG:
                print(f"Cleaning up expired fragments for connection {conn_id}")
            del self.fragment_buffer[conn_id]

# NeoPixel Status Indicator
class StatusIndicator:
    def __init__(self, pin=config.NEOPIXEL_PIN, count=config.NEOPIXEL_COUNT):
        self.np = neopixel.NeoPixel(Pin(pin), count)
        self.set_status('startup')

    def set_status(self, status):
        """Set status color based on operation state"""
        color = config.STATUS_COLORS.get(status, config.STATUS_COLORS['off'])
        self.np[0] = color
        self.np.write()

    def off(self):
        """Turn off status indicator"""
        self.np[0] = (0, 0, 0)
        self.np.write()

# LED Setup
class LEDController:
    def __init__(self, pins):
        self.leds = [Pin(pin, Pin.OUT) for pin in pins]
        self.clear_all()

    def clear_all(self):
        for led in self.leds:
            led.off()

    def set_level(self, level):
        """Set LEDs based on urgency/anger level (0-5)"""
        self.clear_all()
        for i in range(min(level, len(self.leds))):
            self.leds[i].on()

# Word Buffer with rotating queue
class WordBuffer:
    def __init__(self, max_words=250, trim_words=50):
        self.buffer = deque((), max_words)
        self.max_words = max_words
        self.trim_words = trim_words
        self.last_update = 0
        self.processed_count = 0  # Track how many words have been processed

    def add_words(self, text):
        """Add words to buffer, trimming if needed"""
        words = text.strip().split()
        for word in words:
            if len(self.buffer) >= self.max_words:
                # Remove trim_words from the start
                for _ in range(self.trim_words):
                    if self.buffer:
                        self.buffer.popleft()
            self.buffer.append(word)

        self.last_update = time.ticks_ms()

    def get_text(self):
        """Get all words as space-separated string"""
        return " ".join(self.buffer)

    def should_process(self, timeout_ms=2000):
        """Check if we should process (2 seconds since last update AND new words)"""
        return (time.ticks_diff(time.ticks_ms(), self.last_update) >= timeout_ms and
                len(self.buffer) > self.processed_count)

    def clear(self):
        """Clear the buffer"""
        while self.buffer:
            self.buffer.popleft()
        self.processed_count = 0

    def mark_processed(self):
        """Mark current buffer contents as processed"""
        self.processed_count = len(self.buffer)


# Simple HTTP Server
class WebhookServer:
    def __init__(self, word_buffer, sentiment_analyzer, led_controller, status_indicator):
        self.word_buffer = word_buffer
        self.sentiment_analyzer = sentiment_analyzer
        self.led_controller = led_controller
        self.status_indicator = status_indicator
        self.processing = False
        # Initialize SignalWire hooks integration
        self.signalwire_hooks = SignalWireHooks(status_indicator, led_controller, word_buffer)
        # Initialize fragment assembler for handling PageKite fragmentation
        self.fragment_assembler = FragmentAssembler()

    async def read_complete_http_request(self, reader):
        """Read complete HTTP request handling Content-Length properly"""
        try:
            # Read headers line by line until we get the complete header
            headers_data = b""
            
            while True:
                line = await reader.readline()
                if not line:  # EOF
                    break
                headers_data += line
                
                # Check for end of headers
                if headers_data.endswith(b'\r\n\r\n'):
                    break
                elif headers_data.endswith(b'\n\n'):  # Handle \n\n case
                    break
            
            if config.DEBUG:
                print(f"Headers received: {len(headers_data)} bytes")
            
            # Parse Content-Length from headers
            headers_str = headers_data.decode('utf-8', errors='ignore')
            content_length = 0
            
            for line in headers_str.split('\n'):
                line = line.strip()
                if line.lower().startswith('content-length:'):
                    try:
                        content_length = int(line.split(':', 1)[1].strip())
                        break
                    except (ValueError, IndexError):
                        if config.DEBUG:
                            print(f"Failed to parse Content-Length: {line}")
                        continue
            
            if config.DEBUG:
                print(f"Content-Length: {content_length}")
            
            # Read exact body length if present
            body_data = b""
            if content_length > 0:
                body_data = await reader.readexactly(content_length)
                if config.DEBUG:
                    print(f"Body received: {len(body_data)} bytes")
            
            # Combine headers and body
            complete_request = headers_data + body_data
            return complete_request.decode('utf-8', errors='ignore')
            
        except Exception as e:
            if config.DEBUG:
                print(f"Error reading HTTP request: {e}")
            return ""

    async def handle_request(self, reader, writer):
        """Handle incoming HTTP requests with fragment assembly"""
        try:
            if config.DEBUG:
                print("=== NEW HTTP REQUEST ===")
            
            # Read complete HTTP request with proper Content-Length handling
            request_str = await self.read_complete_http_request(reader)
            
            if not request_str:
                if config.DEBUG:
                    print("ERROR: Empty request received")
                return
            
            # Generate connection ID from writer object (unique per connection)
            connection_id = id(writer)
            
            # Check if this is a fragment
            if self.fragment_assembler.is_fragment(request_str):
                if config.DEBUG:
                    print(f"Fragment detected, buffering for connection {connection_id}")
                
                # Buffer the fragment and wait for complete request
                self.fragment_assembler.add_fragment(connection_id, request_str)
                
                # Send a simple response to fragment request to avoid errors
                await self.send_response(writer, 200, "Fragment received")
                return
            
            # This is a complete request - assemble with any fragments
            assembled_request = self.fragment_assembler.assemble_with_fragments(connection_id, request_str)
            self.fragment_assembler.clear_fragments(connection_id)
            
            # Use the assembled request for processing
            request_str = assembled_request

            if config.DEBUG:
                print(f"Request: {request_str[:200]}...")
                print(f"Full request length: {len(request_str)}")

            # Parse request
            lines = request_str.split('\n')
            if not lines:
                await self.send_response(writer, 400, "Bad Request")
                return

            request_line = lines[0].strip()
            parts = request_line.split(' ')
            if len(parts) < 2:
                await self.send_response(writer, 400, "Bad Request")
                return

            method, path = parts[0], parts[1]
            print(f"HTTP REQUEST: {method} {path}")

            # Handle webhook POST
            if method == "POST" and path == config.CALLBACK_PATH:
                # Find content
                content = ""
                if "\r\n\r\n" in request_str:
                    content = request_str.split("\r\n\r\n", 1)[1]
                elif "\n\n" in request_str:
                    content = request_str.split("\n\n", 1)[1]

                if content:
                    self.word_buffer.add_words(content)
                    if config.DEBUG:
                        print(f"Added words: {content[:50]}...")

                await self.send_response(writer, 200, "OK\n")

                # Start processing task if not already running
                if not self.processing:
                    asyncio.create_task(self.process_buffer())

            # Handle SignalWire SWAIG function calls
            elif method == "POST" and path.startswith("/swaig/"):
                try:
                    # Parse JSON body for SWAIG function calls
                    body = ""
                    if "\r\n\r\n" in request_str:
                        body = request_str.split("\r\n\r\n", 1)[1]
                    elif "\n\n" in request_str:
                        body = request_str.split("\n\n", 1)[1]
                    
                    if config.DEBUG:
                        print(f"SWAIG body length: {len(body)}")
                        print(f"SWAIG body preview: {body[:100]}...")

                    swaig_data = {}
                    if body:
                        try:
                            swaig_data = json.loads(body)
                        except Exception as json_error:
                            if config.DEBUG:
                                print(f"JSON parse error: {json_error}")
                                print(f"Body content (first 200 chars): {repr(body[:200])}")
                                print(f"Body length: {len(body)}")
                                print(f"Raw request (first 500 chars): {repr(request_str[:500])}")
                                print(f"Request method: {method}, path: {path}")
                                print("=== COMPLETE REQUEST DUMP ===")
                                print(repr(request_str))
                                print("=== END REQUEST DUMP ===")
                            raise json_error

                    function_name = path.split("/")[-1]  # Extract function name from path
                    args = swaig_data.get("argument", {})
                    raw_data = swaig_data

                    # Use SignalWire hooks module to handle the function call
                    response_data = self.signalwire_hooks.handle_swaig_function(function_name, args, raw_data)
                    
                    # Convert to JSON string
                    json_response = json.dumps(response_data)
                    if config.DEBUG:
                        print(f"SWAIG response size: {len(json_response)} bytes")

                    # Start processing task if text was added to buffer
                    if function_name == "process_text" and not self.processing:
                        asyncio.create_task(self.process_buffer())

                    await self.send_response(writer, 200, json_response, "application/json")

                except Exception as e:
                    if config.DEBUG:
                        print(f"SWAIG function error: {e}")
                    error_response = {"response": f"Error: {str(e)}"}
                    await self.send_response(writer, 500, json.dumps(error_response), "application/json")

            # Handle buffer reset (for call disconnect)
            elif method == "POST" and path == config.RESET_PATH:
                try:
                    self.word_buffer.clear()
                    self.led_controller.clear_all()
                    self.status_indicator.set_status('idle')
                    if config.DEBUG:
                        print("Buffer reset - call disconnected")
                    await self.send_response(writer, 200, "RESET\n")
                except Exception as e:
                    await self.send_response(writer, 500, f"Reset failed {e}\n")

            else:
                # Handle other requests
                if path == "/" or path == "/swml":
                    if config.DEBUG:
                        print(f"SWML request: {method} {path}")
                    try:
                        # Return SWML document for SignalWire (supports both GET and POST)
                        swml_doc = self.signalwire_hooks.get_swml_document()
                        if config.DEBUG:
                            print(f"SWML doc generated, size: {len(json.dumps(swml_doc))}")
                        await self.send_response(writer, 200, json.dumps(swml_doc), "application/json")
                    except Exception as e:
                        if config.DEBUG:
                            print(f"SWML generation error: {e}")
                        await self.send_response(writer, 500, f"SWML Error: {str(e)}")
                else:
                    if config.DEBUG:
                        print(f"404 for: {method} {path}")
                    await self.send_response(writer, 404, "Not Found")

        except Exception as e:
            if config.DEBUG:
                print(f"Request handler error: {e}")
            await self.send_response(writer, 500, "Internal Server Error")

        finally:
            try:
                await writer.aclose()
            except Exception as close_error:
                if config.DEBUG:
                    print(f"Error closing connection: {close_error}")

    async def send_response(self, writer, status, body, content_type="text/plain"):
        """Send HTTP response with explicit connection closure"""
        status_text = {200: "OK", 400: "Bad Request", 404: "Not Found", 500: "Internal Server Error"}
        response = f"HTTP/1.1 {status} {status_text.get(status, 'Unknown')}\r\n"
        response += f"Content-Type: {content_type}\r\n"
        response += f"Content-Length: {len(body)}\r\n"
        response += "Connection: close\r\n"
        response += "Cache-Control: no-cache\r\n\r\n"
        response += body

        writer.write(response.encode())
        await writer.drain()

    async def process_buffer(self):
        """Process word buffer when timeout occurs"""
        self.processing = True
        try:
            while True:
                await asyncio.sleep_ms(500)  # Check every 500ms

                if (len(self.word_buffer.buffer) > 0 and
                    self.word_buffer.should_process(config.PROCESSING_TIMEOUT)):

                    text = self.word_buffer.get_text()
                    if config.DEBUG:
                        print(f"Processing text ({len(text)} chars): {text[:100]}...")

                    # Analyze sentiment
                    level = self.sentiment_analyzer.analyze_sentiment(text)

                    if config.DEBUG:
                        print(f"Sentiment level: {level}")

                    # Update LEDs
                    self.led_controller.set_level(level)

                    # Mark current content as processed
                    self.word_buffer.mark_processed()

                    # Force garbage collection
                    gc.collect()

        except Exception as e:
            if config.DEBUG:
                print(f"Buffer processing error: {e}")
        finally:
            self.processing = False


# Main application
async def main():
    print(f"Starting {config.DEVICE_NAME}...")

    # Initialize components
    status_indicator = StatusIndicator()  # Starts with startup (orange) color
    led_controller = LEDController(config.LED_PINS)
    word_buffer = WordBuffer(config.MAX_WORDS, config.TRIM_WORDS)
    sentiment_analyzer = SentimentAnalyzer(config.OPENAI_API_KEY, config.OPENAI_MODEL, status_indicator)
    webhook_server = WebhookServer(word_buffer, sentiment_analyzer, led_controller, status_indicator)

    # Flash LEDs to show startup
    for i in range(len(config.LED_PINS)):
        led_controller.set_level(i + 1)
        await asyncio.sleep_ms(200)
    led_controller.clear_all()

    print(f"Server starting on port {config.SERVER_PORT}")
    print(f"Webhook endpoint: {config.CALLBACK_PATH}")

    # Start server
    server = await asyncio.start_server(
        webhook_server.handle_request,
        '0.0.0.0',
        config.SERVER_PORT
    )

    print("Server ready!")

    # Start PageKite tunnel
    print("Starting PageKite tunnel...")
    pagekite_success = await start_pagekite_tunnel(webhook_server)
    if not pagekite_success:
        print("Warning: PageKite tunnel failed to start")
        status_indicator.set_status('error')
        await asyncio.sleep(2)  # Show error briefly

    # Set status to idle (green) when server is ready
    status_indicator.set_status('idle')

    # Keep server running with periodic cleanup
    cleanup_counter = 0
    while True:
        await asyncio.sleep(1)
        gc.collect()  # Regular garbage collection
        
        # Cleanup expired fragments every 30 seconds
        cleanup_counter += 1
        if cleanup_counter >= 30:
            if hasattr(webhook_server, 'fragment_assembler'):
                webhook_server.fragment_assembler.cleanup_expired_fragments()
            cleanup_counter = 0

# Run the application
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Shutting down...")
    except Exception as e:
        print(f"Fatal error: {e}")
        # Set error status and flash all LEDs on fatal error
        try:
            status_indicator = StatusIndicator()
            status_indicator.set_status('error')
            led_controller = LEDController(config.LED_PINS)
            for _ in range(10):
                led_controller.set_level(5)  # Max level is now 5
                time.sleep(0.1)
                led_controller.clear_all()
                time.sleep(0.1)
        except:
            pass  # Ignore errors during error handling