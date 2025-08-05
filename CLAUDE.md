## Deployment
* This is a ESP32 MicroPython project.
* Files are located in the `esp32/` subfolder.
* To deploy, cd to esp32/ and use `./deploy.sh -r main.py boot.py file.py` this will upload those 3 files and restart (-r).
* To install packages, use `./deploy.sh -p` to install from requirements.txt
* To change WiFi, cd to esp32/ and use `./generate_boot.py SSID PSK webrepl_password` and `./deploy.sh -r boot.py`
* To reset ESP32: use `mpremote reset` (not `mpremote exec "from machine import reset; reset()"`)
* To get WiFi info: use `mpremote exec "get_wifi()"`

## ESP32 Sentiment Monitor

This ESP32 project implements a real-time sentiment analysis monitor that processes text input via HTTP webhooks and displays emotional intensity through NeoPixel status indicator and LED array.

### Core Functionality

**Hardware Components:**
- NeoPixel status indicator (startup/idle/processing/error states)
- LED array for urgency/anger level display (0-5 scale)
- PageKite tunnel for remote access

**Software Features:**
- HTTP webhook server for receiving text input
- OpenAI API integration for sentiment analysis using GPT-4.1-nano
- Rotating word buffer with intelligent processing (250 words max, 50-word trim)
- Asynchronous processing with timeout-based analysis
- Status indication through colored NeoPixel feedback

**API Endpoints:**
- `POST /webhook` - Receives text input for sentiment analysis
- `POST /reset` - Clears buffer and resets LEDs (for call disconnect)
- `GET /` - Returns device status and configuration info

### Text Processing Flow

1. Text arrives via webhook POST to `/webhook` endpoint
2. Words added to rotating buffer (deque with 250-word capacity)  
3. Processing triggered after 2-second timeout since last update
4. OpenAI sentiment analysis returns urgency/anger level (0-5)
5. LED array displays intensity level
6. NeoPixel shows processing status (blue → green/red)

### Status Indicator Colors

- **Orange**: Startup/initialization
- **Green**: Idle/ready state  
- **Blue**: Processing sentiment analysis
- **Red**: Error state (API failure, network issues)

### PageKite Integration

The device uses PageKite tunneling for remote webhook access:
- Automatic tunnel establishment on startup
- Domain configuration via `config.PAGEKITE_DOMAIN`
- Status reporting in device info endpoint

### Configuration

Key settings in `config.py`:
- `OPENAI_API_KEY`: API key for sentiment analysis
- `LED_PINS`: GPIO pins for urgency display LEDs
- `NEOPIXEL_PIN`: GPIO pin for status indicator
- `SERVER_PORT`: HTTP server port
- `CALLBACK_PATH`: Webhook endpoint path
- `PROCESSING_TIMEOUT`: Delay before processing buffer (2000ms)
