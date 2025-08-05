# HTTP Utilities for ESP32 MicroPython
# Provides reusable HTTP response building functions

class HTTPResponse:
    """Utility class for building HTTP responses"""

    STATUS_CODES = {
        200: "OK",
        400: "Bad Request",
        404: "Not Found",
        500: "Internal Server Error"
    }

    @staticmethod
    def build_response(status_code, body="", content_type="text/plain", additional_headers=None):
        """
        Build a complete HTTP response string

        Args:
            status_code (int): HTTP status code
            body (str): Response body content
            content_type (str): Content-Type header value
            additional_headers (dict): Optional additional headers

        Returns:
            str: Complete HTTP response string
        """
        status_text = HTTPResponse.STATUS_CODES.get(status_code, "Unknown")

        # Build response headers
        response = f"HTTP/1.1 {status_code} {status_text}\r\n"
        response += f"Content-Type: {content_type}\r\n"

        # Calculate content length automatically
        body_bytes = body.encode('utf-8') if isinstance(body, str) else body
        response += f"Content-Length: {len(body_bytes)}\r\n"

        # Add any additional headers
        if additional_headers:
            for header_name, header_value in additional_headers.items():
                response += f"{header_name}: {header_value}\r\n"

        response += "Connection: close\r\n\r\n"
        response += body

        return response

    @staticmethod
    def json_response(status_code, data, additional_headers=None):
        """
        Build a JSON HTTP response

        Args:
            status_code (int): HTTP status code
            data (dict or str): JSON data (will be serialized if dict)
            additional_headers (dict): Optional additional headers

        Returns:
            str: Complete HTTP response string
        """
        try:
            import ujson as json
        except ImportError:
            import json

        if isinstance(data, dict):
            body = json.dumps(data)
        else:
            body = str(data)

        return HTTPResponse.build_response(
            status_code,
            body,
            "application/json",
            additional_headers
        )

    @staticmethod
    def text_response(status_code, text, additional_headers=None):
        """
        Build a plain text HTTP response

        Args:
            status_code (int): HTTP status code
            text (str): Response text
            additional_headers (dict): Optional additional headers

        Returns:
            str: Complete HTTP response string
        """
        return HTTPResponse.build_response(
            status_code,
            text,
            "text/plain",
            additional_headers
        )

class HTTPRequest:
    """Utility class for parsing HTTP requests"""

    @staticmethod
    def parse_request(request_str):
        """
        Parse HTTP request string into components

        Args:
            request_str (str): Complete HTTP request string

        Returns:
            dict: Parsed request with method, path, headers, body
        """
        lines = request_str.split('\n')
        if not lines:
            return None

        # Parse request line
        request_line = lines[0].strip()
        parts = request_line.split(' ')
        if len(parts) < 2:
            return None

        method, path = parts[0], parts[1]

        # Extract request body
        body = ""
        if "\r\n\r\n" in request_str:
            body = request_str.split("\r\n\r\n", 1)[1]
        elif "\n\n" in request_str:
            body = request_str.split("\n\n", 1)[1]

        # Parse headers (optional - can be added if needed)
        headers = {}

        return {
            "method": method,
            "path": path,
            "body": body,
            "headers": headers,
            "raw": request_str
        }

class HTTPRequestHandler:
    """Shared HTTP request handler to eliminate duplication between main.py and upagekite_handler.py"""

    def __init__(self, webhook_server):
        self.webhook_server = webhook_server

    def _log_debug_webhook(self, debug_data):
        """Log debug webhook data to serial output based on debug level"""
        import config
        
        if config.DEBUG_WEBHOOK_LEVEL == 0:
            return
        
        try:
            if config.DEBUG_WEBHOOK_LEVEL >= 1:
                # Basic info
                print(f"SW_DEBUG: Event={debug_data.get('event_type', 'unknown')}, Call={debug_data.get('call_id', 'unknown')}")
                
                # AI interaction data
                if 'ai_data' in debug_data:
                    ai_data = debug_data['ai_data']
                    print(f"SW_DEBUG: AI_Model={ai_data.get('model', 'unknown')}")
                    if 'user_input' in ai_data:
                        print(f"SW_DEBUG: User_Input={ai_data['user_input'][:100]}...")
                    if 'ai_response' in ai_data:
                        print(f"SW_DEBUG: AI_Response={ai_data['ai_response'][:100]}...")
                        
                # SWAIG function calls
                if 'swaig_function' in debug_data:
                    swaig = debug_data['swaig_function']
                    print(f"SW_DEBUG: SWAIG_Function={swaig.get('name', 'unknown')}, Args={swaig.get('arguments', {})}")
                    
            if config.DEBUG_WEBHOOK_LEVEL >= 2:
                # Verbose info - full JSON dump
                try:
                    import ujson as json
                except ImportError:
                    import json
                print(f"SW_DEBUG_FULL: {json.dumps(debug_data)}")
                
        except Exception as e:
            # If there's any error processing the debug data, output raw data
            print(f"SW_DEBUG_ERROR: {e}")
            print(f"SW_DEBUG_RAW: {debug_data}")

    async def handle_http_request(self, method, path, body):
        """
        Handle HTTP request and return response string

        Args:
            method (str): HTTP method (GET, POST, etc.)
            path (str): Request path
            body (str): Request body content

        Returns:
            str: Complete HTTP response string
        """
        import config
        try:
            import ujson as json
        except ImportError:
            import json

        try:
            print(f"HTTP REQUEST: {method} {path}")

            # Handle webhook POST
            if method == "POST" and path == config.CALLBACK_PATH:
                if body:
                    self.webhook_server.word_buffer.add_words(body)
                    if config.DEBUG:
                        print(f"Added words: {body[:50]}...")

                # Start processing task if not already running
                if not self.webhook_server.processing:
                    import uasyncio as asyncio
                    asyncio.create_task(self.webhook_server.process_buffer())

                return HTTPResponse.text_response(200, "OK\n")

            # Handle SignalWire SWAIG function calls
            elif method == "POST" and path.startswith("/swaig/"):
                try:
                    swaig_data = {}
                    if body:
                        swaig_data = json.loads(body)

                    function_name = path.split("/")[-1]  # Extract function name from path
                    args = swaig_data.get("argument", {})
                    raw_data = swaig_data

                    # Use SignalWire hooks module to handle the function call
                    response_data = self.webhook_server.signalwire_hooks.handle_swaig_function(function_name, args, raw_data)

                    # Start processing task if text was added to buffer
                    if function_name == "process_text" and not self.webhook_server.processing:
                        import uasyncio as asyncio
                        asyncio.create_task(self.webhook_server.process_buffer())

                    return HTTPResponse.json_response(200, response_data)

                except Exception as e:
                    if config.DEBUG:
                        print(f"SWAIG function error: {e}")
                    error_response = {"response": f"Error: {str(e)}"}
                    return HTTPResponse.json_response(500, error_response)

            # Handle debug webhook from SignalWire
            elif method == "POST" and path == "/debug":
                try:
                    if body and config.DEBUG_WEBHOOK_LEVEL > 0:
                        debug_data = json.loads(body)
                        self._log_debug_webhook(debug_data)
                    return HTTPResponse.text_response(200, "OK")
                except Exception as e:
                    if config.DEBUG:
                        print(f"Debug webhook error: {e}")
                    return HTTPResponse.text_response(500, f"Debug webhook failed: {e}")

            # Handle buffer reset (for call disconnect)
            elif method == "POST" and path == config.RESET_PATH:
                try:
                    self.webhook_server.word_buffer.clear()
                    self.webhook_server.led_controller.clear_all()
                    self.webhook_server.status_indicator.set_status('idle')
                    if config.DEBUG:
                        print("Buffer reset - call disconnected")
                    return HTTPResponse.text_response(200, "RESET\n")
                except Exception as e:
                    return HTTPResponse.text_response(500, f"Reset failed {e}\n")

            # Handle SWML document requests
            elif path == "/" or path == "/swml":
                if config.DEBUG:
                    print(f"SWML request: {method} {path}")
                try:
                    # Return SWML document for SignalWire (supports both GET and POST)
                    swml_doc = self.webhook_server.signalwire_hooks.get_swml_document()
                    if config.DEBUG:
                        print(f"SWML doc generated, size: {len(json.dumps(swml_doc))}")
                    return HTTPResponse.json_response(200, swml_doc)
                except Exception as e:
                    if config.DEBUG:
                        print(f"SWML generation error: {e}")
                    return HTTPResponse.text_response(500, f"SWML Error: {str(e)}")

            # Handle 404
            else:
                if config.DEBUG:
                    print(f"404 for: {method} {path}")
                return HTTPResponse.text_response(404, "Not Found")

        except Exception as e:
            if config.DEBUG:
                print(f"Request handler error: {e}")
            return HTTPResponse.text_response(500, "Internal Server Error")