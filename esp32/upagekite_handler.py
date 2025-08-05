import gc
import uasyncio as asyncio
from upagekite_lib.proto import uPageKiteDefaults, Kite, Frame
import config
from http_utils import HTTPResponse, HTTPRequest, HTTPRequestHandler
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
        # Initialize shared HTTP handler if webhook_server is available
        self.http_handler = HTTPRequestHandler(webhook_server) if webhook_server else None

    @classmethod
    def log(cls, message):
        print(f'[PageKite] {message}')

    async def _discover_expected_relay(self, domain):
        """Try to discover which relay the PageKite frontend expects"""
        try:
            import urequests
            # Try making a request to the domain to see which relay the error points to
            response = urequests.get(f'http://{domain}', timeout=5)
            if response.status_code != 200:
                content = response.text
                response.close()

                # Look for relay IP in the offline page
                if 'relay=' in content:
                    relay_part = content.split('relay=')[1].split('"')[0]
                    if '::ffff:' in relay_part:
                        # IPv4-mapped IPv6 address
                        ip = relay_part.split('::ffff:')[1]
                        return (ip, 443)
                    elif relay_part.count('.') == 3:
                        # Direct IPv4
                        return (relay_part, 443)
            else:
                response.close()
        except Exception as e:
            self.info(f'Relay discovery failed: {e}')

        return None

    async def start_tunnel(self, domain, secret, local_port=80):
        """Start PageKite tunnel with proper upagekite implementation"""
        try:
            # Create kite configuration
            kite = Kite(domain, secret, 'http', None)

            # No proxy needed - we'll handle requests directly

            # Discover which relay PageKite frontend expects
            expected_relay = await self._discover_expected_relay(domain)
            if expected_relay:
                self.info(f'Frontend expects relay {expected_relay}')
                ping = await self.ping_relay(expected_relay)
                if ping < 99999:
                    best_relay = expected_relay
                    best_ping = ping
                    self.info(f'Using expected relay {best_relay} (ping: {best_ping}ms)')
                else:
                    self.error(f'Expected relay {expected_relay} is not responding')
                    best_relay = None
                    best_ping = 99999
            else:
                self.info('Could not discover expected relay, using discovery')
                best_relay = None
                best_ping = 99999

            if not best_relay or best_ping >= 99999:
                self.error('Expected relay failed, using discovery')
                # Fall back to default relay discovery
                relay_addrs = await self.get_relays_addrinfo()
                if not relay_addrs:
                    self.error('No PageKite relays available')
                    return False

                for addr_info in relay_addrs[:3]:
                    addr = addr_info[-1]
                    ping = await self.ping_relay(addr)
                    if ping < best_ping:
                        best_ping = ping
                        best_relay = addr

                if not best_relay:
                    self.error('No working PageKite relays found')
                    return False

                self.info(f'Using fallback relay {best_relay} (ping: {best_ping}ms)')

            # Connect to PageKite relay
            try:
                cfd, conn = await self.connect(best_relay, [kite], self.global_secret)
            except Exception as e:
                if 'X-PageKite-Duplicate' in str(e):
                    self.error('Duplicate tunnel detected - waiting 30s and retrying...')
                    await asyncio.sleep(30)
                    try:
                        cfd, conn = await self.connect(best_relay, [kite], self.global_secret)
                    except Exception as e2:
                        self.error(f'Retry failed: {e2}')
                        return False
                else:
                    raise e

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
        """Handle HTTP request using shared handler"""
        try:
            # Only log actual HTTP requests, not connection management
            if frame.payload and len(frame.payload) > 20:
                self.info(f'PageKite HTTP request: frame.sid={frame.sid}, payload_len={len(frame.payload)}')

            if not frame.payload or not self.http_handler:
                # Silently handle empty payloads (connection management)
                response = HTTPResponse.text_response(400, "Bad Request")
                await conn.reply(frame, response, eof=True)
                return

            # Parse HTTP request
            request_str = str(frame.payload, 'utf-8')
            parsed_request = HTTPRequest.parse_request(request_str)

            if not parsed_request:
                response = HTTPResponse.text_response(400, "Bad Request")
                await conn.reply(frame, response, eof=True)
                return

            self.info(f'PageKite HTTP {parsed_request["method"]} {parsed_request["path"]}')

            # Use shared HTTP handler
            response = await self.http_handler.handle_http_request(
                parsed_request["method"],
                parsed_request["path"],
                parsed_request["body"]
            )

            await conn.reply(frame, response, eof=True)

        except Exception as e:
            self.error(f'PageKite HTTP request handling error: {e}')
            if self.debug:
                import sys
                sys.print_exception(e)
            response = HTTPResponse.text_response(500, "Internal Server Error")
            await conn.reply(frame, response, eof=True)


# Global PageKite handler instance
_pagekite_handler = None

def stop_pagekite_tunnel():
    """Stop any existing PageKite tunnel"""
    global _pagekite_handler
    if _pagekite_handler and _pagekite_handler.running:
        _pagekite_handler.running = False
        print("[PageKite] Stopping existing tunnel...")

async def start_pagekite_tunnel(webhook_server=None):
    """Start PageKite tunnel using proper upagekite implementation"""
    global _pagekite_handler

    # Stop any existing tunnel first
    stop_pagekite_tunnel()
    await asyncio.sleep(2)  # Give time for cleanup

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