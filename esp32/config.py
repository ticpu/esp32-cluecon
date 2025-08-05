# Configuration file for ESP32 project
# API keys are imported from secrets files

# Import API keys and secrets
try:
    from secrets_local import *  # Use local secrets if available
except ImportError:
    try:
        from secrets import *  # Fall back to template secrets
    except ImportError:
        # Default values if no secrets file exists
        OPENAI_API_KEY = "your-openai-api-key-here"
        PAGEKITE_SECRET = "your-pagekite-secret-here"
        SIGNALWIRE_PROJECT_ID = "your-project-id"
        SIGNALWIRE_API_TOKEN = "your-api-token"
        SIGNALWIRE_SPACE_URL = "your-space.signalwire.com"
        WIFI_SSID = "your-wifi-ssid"
        WIFI_PASSWORD = "your-wifi-password"
        WEBREPL_PASSWORD = "your-webrepl-password"

# OpenAI Configuration
OPENAI_MODEL = "gpt-4o-mini"  # Using 4o-mini as it's more available than 4.1-nano

# PageKite Configuration (can be overridden in secrets files)
if 'PAGEKITE_DOMAIN' not in locals():
    PAGEKITE_DOMAIN = "yourname.pagekite.me"  # Default value

# Application Settings
DEBUG = True
SERVER_PORT = 80
CALLBACK_PATH = "/webhook"
RESET_PATH = "/reset"  # Endpoint to reset buffer (for call disconnect)

# Word Buffer Settings
MAX_WORDS = 250
TRIM_WORDS = 50
PROCESSING_TIMEOUT = 2000  # 2 seconds in milliseconds

# LED Configuration (pins for sentiment display)
LED_PINS = [9, 10, 11, 12, 13]  # 5 LEDs for urgency/anger levels (0-5 scale)

# NeoPixel Status Indicator Configuration
NEOPIXEL_PIN = 48  # GPIO pin for NeoPixel
NEOPIXEL_COUNT = 1  # Number of NeoPixels
NEOPIXEL_BRIGHTNESS = 0.4  # 40% brightness limit

# Status Colors (RGB values at 40% brightness = max 102)
STATUS_COLORS = {
    'idle': (0, 102, 0),      # Green - system idle
    'processing': (0, 0, 102), # Blue - waiting for OpenAI
    'error': (102, 0, 0),     # Red - error state
    'startup': (102, 51, 0),  # Orange - starting up
    'off': (0, 0, 0)          # Off
}

# Device Configuration
DEVICE_ID = "esp32-clucon-001"
DEVICE_NAME = "ESP32-AI-Controller"