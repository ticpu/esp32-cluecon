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

# OpenAI API Client
class SentimentAnalyzer:
    def __init__(self, api_key, model="gpt-4.1-nano", status_indicator=None):
        self.api_key = api_key
        self.model = model
        self.base_url = "https://api.openai.com/v1/chat/completions"
        self.status_indicator = status_indicator

    def analyze_sentiment(self, text):
        """Analyze sentiment and return urgency/anger level 0-7"""
        if not text.strip():
            return 0

        # Set status to processing (blue)
        if self.status_indicator:
            self.status_indicator.set_status('processing')

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": "Analyze the urgency and anger level of the text, giving MORE WEIGHT to the most recent statements and events mentioned. The latest words in the conversation are more important than earlier ones. Focus especially on the tone and sentiment of the final sentences. Respond with ONLY a single number from 0-5, where 0 is calm/neutral and 5 is extremely urgent/angry."
                },
                {
                    "role": "user",
                    "content": text
                }
            ],
            "max_tokens": 10,
            "temperature": 0.1
        }

        try:
            response = urequests.post(
                self.base_url,
                headers=headers,
                data=json.dumps(payload)
            )

            if response.status_code == 200:
                result = json.loads(response.text)
                content = result["choices"][0]["message"]["content"].strip()
                level = int(content)
                # Set status back to idle (green) after successful processing
                if self.status_indicator:
                    self.status_indicator.set_status('idle')
                return max(0, min(5, level))  # Clamp to 0-5
            else:
                if config.DEBUG:
                    print(f"OpenAI API Error: {response.status_code}")
                # Set error status (red) on API error
                if self.status_indicator:
                    self.status_indicator.set_status('error')
                return 0

        except Exception as e:
            if config.DEBUG:
                print(f"Sentiment analysis error: {e}")
            # Set error status (red) on exception
            if self.status_indicator:
                self.status_indicator.set_status('error')
            return 0
        finally:
            if 'response' in locals():
                response.close()

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

    async def handle_request(self, reader, writer):
        """Handle incoming HTTP requests"""
        try:
            # Read request
            request = await reader.read(1024)
            request_str = request.decode('utf-8')

            if config.DEBUG:
                print(f"Request: {request_str[:200]}...")

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

                    swaig_data = {}
                    if body:
                        swaig_data = json.loads(body)

                    function_name = path.split("/")[-1]  # Extract function name from path
                    args = swaig_data.get("argument", {})
                    raw_data = swaig_data

                    # Use SignalWire hooks module to handle the function call
                    response_data = self.signalwire_hooks.handle_swaig_function(function_name, args, raw_data)

                    # Start processing task if text was added to buffer
                    if function_name == "process_text" and not self.processing:
                        asyncio.create_task(self.process_buffer())

                    await self.send_response(writer, 200, json.dumps(response_data), "application/json")

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
            await writer.aclose()

    async def send_response(self, writer, status, body, content_type="text/plain"):
        """Send HTTP response"""
        status_text = {200: "OK", 400: "Bad Request", 404: "Not Found", 500: "Internal Server Error"}
        response = f"HTTP/1.1 {status} {status_text.get(status, 'Unknown')}\r\n"
        response += f"Content-Type: {content_type}\r\n"
        response += f"Content-Length: {len(body)}\r\n"
        response += "Connection: close\r\n\r\n"
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

    # Keep server running
    while True:
        await asyncio.sleep(1)
        gc.collect()  # Regular garbage collection

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