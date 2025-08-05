import gc
import uasyncio as asyncio
from upagekite_lib.proto import uPageKiteDefaults, Kite, Frame
import config
try:
    import ujson as json
except ImportError:
    import json

class PageKiteConn:
    """Wrapper for PageKite connection to handle replies"""
    def __init__(self, conn, uPK):
        self.conn = conn
        self.uPK = uPK

    async def reply(self, frame, data, eof=False):
        """Send reply data back through the tunnel"""
        if data:
            chunk = self.uPK.fmt_data(frame, data)
            await self.uPK.send(self.conn, chunk)
        if eof:
            eof_chunk = self.uPK.fmt_eof(frame)
            await self.uPK.send(self.conn, eof_chunk)

    def async_await_data(self, uPK, sid, handler):
        """Register data handler for this session"""
        # This is handled by the main frame processing loop
        pass

    def close(self, sid=None):
        """Close connection"""
        if hasattr(self.conn, 'close'):
            self.conn.close()

class PageKiteHandler(uPageKiteDefaults):
    def __init__(self, debug=False, webhook_server=None):
        self.debug = debug
        self.info = self.log if debug else lambda x: None
        self.error = self.log
        self.trace = self.log if debug else lambda x: None
        self.global_secret = self.make_random_secret()
        self.running = False
        self.webhook_server = webhook_server

    @classmethod
    def log(cls, message):
        print(f'[PageKite] {message}')

    async def start_tunnel(self, domain, secret, local_port=80):
        """Start PageKite tunnel with proper upagekite implementation"""
        try:
            # Create kite configuration
            kite = Kite(domain, secret, 'http', None)

            # No proxy needed - we'll handle requests directly

            # Get relay addresses
            relay_addrs = await self.get_relays_addrinfo()
            if not relay_addrs:
                self.error('No PageKite relays available')
                return False

            # Try connecting to best relay
            best_relay = None
            best_ping = 99999

            for addr_info in relay_addrs[:3]:  # Try top 3 relays
                addr = addr_info[-1]
                ping = await self.ping_relay(addr)
                if ping < best_ping:
                    best_ping = ping
                    best_relay = addr

            if not best_relay:
                self.error('No working PageKite relays found')
                return False

            self.info(f'Connecting to relay {best_relay} (ping: {best_ping}ms)')

            # Connect to PageKite relay
            cfd, conn = await self.connect(best_relay, [kite], self.global_secret)

            self.info(f'PageKite tunnel established: http://{domain}')
            self.running = True

            # Wrap connection for proxy use
            wrapped_conn = PageKiteConn(conn, self)

            # Start processing frames
            asyncio.create_task(self._process_frames(conn, wrapped_conn))

            return True

        except Exception as e:
            self.error(f'Failed to start PageKite tunnel: {e}')
            return False

    async def _process_frames(self, conn, wrapped_conn):
        """Process incoming PageKite frames"""
        try:
            while self.running:
                try:
                    # Read frame from PageKite tunnel
                    frame_data = await self.read_chunk(conn)
                    if not frame_data:
                        break

                    # Parse frame
                    frame = Frame(self, frame_data)

                    if frame.ping:
                        # Handle ping
                        pong = self.fmt_pong(frame.ping)
                        await self.send(conn, pong)
                    elif frame.sid:
                        # Handle HTTP request directly
                        await self._handle_http_request(wrapped_conn, frame)

                    # Garbage collection
                    gc.collect()

                except Exception as e:
                    from upagekite_lib.proto import EofTunnelError
                    if isinstance(e, EofTunnelError):
                        self.error('PageKite tunnel connection lost')
                        break  # Exit the loop and close connection
                    else:
                        import sys
                        self.error(f'Frame processing error: {e}')
                        if self.debug:
                            sys.print_exception(e)
                        await asyncio.sleep_ms(100)

        except Exception as e:
            self.error(f'Frame processing loop error: {e}')

        finally:
            self.running = False
            if hasattr(conn, 'close'):
                conn.close()
    
    async def _handle_http_request(self, conn, frame):
        """Handle HTTP request directly with simple parsing"""
        try:
            if not frame.payload or not self.webhook_server:
                await conn.reply(frame, b"HTTP/1.1 400 Bad Request\r\n\r\n", eof=True)
                return
                
            # Parse HTTP request
            request_str = str(frame.payload, 'utf-8')
            lines = request_str.split('\n')
            
            if not lines:
                await conn.reply(frame, b"HTTP/1.1 400 Bad Request\r\n\r\n", eof=True)
                return
                
            request_line = lines[0].strip()
            parts = request_line.split(' ')
            
            if len(parts) < 2:
                await conn.reply(frame, b"HTTP/1.1 400 Bad Request\r\n\r\n", eof=True)
                return
                
            method, path = parts[0], parts[1]
            
            # Extract request body if present
            content = ""
            if "\r\n\r\n" in request_str:
                content = request_str.split("\r\n\r\n", 1)[1]
            elif "\n\n" in request_str:
                content = request_str.split("\n\n", 1)[1]
            
            # Handle different endpoints
            if method == "POST" and path == config.CALLBACK_PATH:
                # Webhook endpoint
                if content:
                    self.webhook_server.word_buffer.add_words(content)
                    if config.DEBUG:
                        print(f"[PageKite] Added words: {content[:50]}...")
                    
                    # Start processing if not already running
                    if not self.webhook_server.processing:
                        asyncio.create_task(self.webhook_server.process_buffer())
                
                response = b"HTTP/1.1 200 OK\r\nContent-Length: 3\r\n\r\nOK\n"
                await conn.reply(frame, response, eof=True)
                
            elif method == "POST" and path == config.RESET_PATH:
                # Reset endpoint
                self.webhook_server.word_buffer.clear()
                self.webhook_server.led_controller.clear_all()
                self.webhook_server.status_indicator.set_status('idle')
                if config.DEBUG:
                    print("[PageKite] Buffer reset - call disconnected")
                
                response = b"HTTP/1.1 200 OK\r\nContent-Length: 6\r\n\r\nRESET\n"
                await conn.reply(frame, response, eof=True)
                
            elif method == "GET" and path == "/":
                # Status endpoint
                status_data = {
                    "status": "active",
                    "device": config.DEVICE_NAME,
                    "buffer_size": len(self.webhook_server.word_buffer.buffer),
                    "webhook_path": config.CALLBACK_PATH,
                    "reset_path": config.RESET_PATH,
                    "pagekite_running": True
                }
                body = json.dumps(status_data)
                response = f"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: {len(body)}\r\n\r\n{body}".encode()
                await conn.reply(frame, response, eof=True)
                
            else:
                response = b"HTTP/1.1 404 Not Found\r\nContent-Length: 9\r\n\r\nNot Found"
                await conn.reply(frame, response, eof=True)
                
        except Exception as e:
            self.error(f'HTTP request handling error: {e}')
            if self.debug:
                import sys
                sys.print_exception(e)
            await conn.reply(frame, b"HTTP/1.1 500 Internal Server Error\r\n\r\n", eof=True)

# Global PageKite handler instance
_pagekite_handler = None

async def start_pagekite_tunnel(webhook_server=None):
    """Start PageKite tunnel using proper upagekite implementation"""
    global _pagekite_handler

    try:
        from secrets_local import PAGEKITE_SECRET, PAGEKITE_DOMAIN
    except ImportError:
        from config import PAGEKITE_SECRET, PAGEKITE_DOMAIN

    _pagekite_handler = PageKiteHandler(debug=config.DEBUG, webhook_server=webhook_server)

    success = await _pagekite_handler.start_tunnel(
        PAGEKITE_DOMAIN,
        PAGEKITE_SECRET,
        config.SERVER_PORT
    )

    if success:
        print(f"✅ PageKite tunnel active: http://{PAGEKITE_DOMAIN}")
    else:
        print("❌ Failed to establish PageKite tunnel")

    return success

def is_pagekite_running():
    """Check if PageKite tunnel is running"""
    return _pagekite_handler and _pagekite_handler.running