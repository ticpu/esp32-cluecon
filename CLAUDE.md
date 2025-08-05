## Deployment
* This is a ESP32 MicroPython project.
* Files are located in the `esp32/` subfolder.
* To deploy, cd to esp32/ and use `./deploy.sh -r main.py boot.py file.py` this will upload those 3 files and restart (-r).
* To install packages, use `./deploy.sh -p` to install from requirements.txt
* To change WiFi, cd to esp32/ and use `./generate_boot.py SSID PSK webrepl_password` and `./deploy.sh -r boot.py`
* To reset ESP32: use `mpremote reset` (not `mpremote exec "from machine import reset; reset()"`)
* To get WiFi info: use `mpremote exec "get_wifi()"`

## ESP32 SignalWire AI Device Controller

This ESP32 project implements a real-time AI-controlled device that integrates with SignalWire AI agents, processes voice conversations, and provides sensor monitoring with visual feedback through NeoPixel status indicator and LED array.

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

### Code Style Guidelines

**IMPORTANT: Always use builder classes instead of manual JSON construction**

✅ **Correct approach using builders:**
```python
# SWML document generation
from swml_builder import SWMLBuilder

builder = (SWMLBuilder()
          .answer()
          .ai(model="gpt-4o-mini", temperature=0.7)
          .add_language("English", "en-US", "openai.alloy")
          .set_prompt("Your AI prompt here"))
return builder.build()

# SWAIG function definitions
from swml_builder import SWAIGFunctionBuilder

function = (SWAIGFunctionBuilder("function_name")
           .description("Function description")
           .url("https://example.com/webhook")
           .add_parameter("param", "string", "Parameter description", required=True)
           .build())

# SWAIG function responses
from swaig_function_result import SwaigFunctionResult

return (SwaigFunctionResult("Response text")
        .update_global_data({"key": "value"})
        .add_action("action_name", data)
        .to_dict())
```

❌ **Avoid manual JSON construction:**
```python
# Don't do this - manual JSON is error-prone and hard to maintain
return {
    "version": "1.0.0",
    "sections": {
        "main": [{"answer": {}}, {"ai": {...}}]
    }
}

# Don't do this - manual function definitions
return {
    "function": "name",
    "description": "desc", 
    "webhook": {"url": "...", "method": "POST"},
    "parameters": {...}
}

# Don't do this - manual response objects
return {"response": "text", "action": [...]}
```

**Benefits of using builder classes:**
- **Type safety**: Catch errors at development time
- **Method chaining**: Cleaner, more readable code
- **Validation**: Built-in parameter validation
- **Consistency**: Ensures correct SignalWire API format
- **Maintainability**: Easier to update when API changes
