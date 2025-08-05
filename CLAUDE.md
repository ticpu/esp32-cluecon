## Deployment
* This is a ESP32 MicroPython project.
* Files are located in the `esp32/` subfolder.
* To deploy, cd to esp32/ and use `./deploy.sh -r main.py boot.py file.py` this will upload those 3 files and restart (-r).
* To change WiFi, cd to esp32/ and use `./generate_boot.py SSID PSK webrepl_password` and `./deploy.sh -r boot.py`

## SignalWire Integration

This project integrates ESP32 with SignalWire's AI Gateway (SWAIG) and SignalWire Markup Language (SWML) for voice-enabled AI applications.

### ESP32 ↔ SignalWire Data Flow

**What runs on ESP32:**
- HTTP client for SignalWire API calls
- Audio capture/playback
- Local sensor integration
- WiFi connectivity management
- Button/input handling

**What runs on SignalWire:**
- AI model inference
- Voice-to-text / text-to-voice
- Call routing and telephony
- SWML document processing
- SWAIG function execution

**Communication:**
- **To SignalWire**: HTTP requests with audio data, sensor readings, status updates
- **From SignalWire**: SWML responses, audio streams, function calls
- **Protocol**: REST API over HTTPS

### Key SignalWire Concepts for ESP32

**SWAIG Functions**: AI tools that can be called from ESP32:
```python
# Example function the ESP32 can trigger
@AgentBase.tool(name="control_device", description="Control ESP32 device", parameters={...})
def control_device(self, args, raw_data):
    # This would run on SignalWire server, responding to ESP32 requests
    return SwaigFunctionResult("Device controlled")
```

**SWML Responses**: Structured responses that ESP32 can parse:
- Audio playback instructions
- Device control commands  
- Status updates
- Next action prompts

### ESP32 Integration Patterns

**Device Registration**: ESP32 identifies itself to SignalWire service
**Audio Streaming**: Real-time audio data exchange
**Command Processing**: Parse SWML responses for device actions
**State Synchronization**: Keep ESP32 and SignalWire agent in sync

### Environment Variables (for SignalWire server component)

**Authentication:**
- `SWML_BASIC_AUTH_USER` / `SWML_BASIC_AUTH_PASSWORD`: HTTP Basic Auth

**Configuration:**
- `SWML_PROXY_URL_BASE`: Reverse proxy setup
- `SWML_SSL_ENABLED`: Enable HTTPS
- `SWML_DOMAIN`: Domain configuration

### Deployment Architecture

1. **ESP32 Device**: Runs MicroPython code for hardware interface
2. **SignalWire Agent**: Cloud-hosted AI agent (Python/FastAPI)
3. **Communication**: HTTPS REST API between ESP32 and SignalWire
