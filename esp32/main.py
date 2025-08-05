from machine import Pin
import neopixel
import time

# Setup NeoPixel on GPIO pin 48 (1 pixel for ESP32-S3)
np = neopixel.NeoPixel(Pin(48), 1)

def set_color(r, g, b):
    """Set NeoPixel color"""
    np[0] = (r, g, b)
    np.write()

def flash_color(r, g, b, duration=0.5):
    """Flash a color for specified duration"""
    set_color(r, g, b)
    time.sleep(duration)
    set_color(0, 0, 0)  # Turn off

# Flash different colors at 25% brightness
colors = [
    (64, 0, 0),     # Red
    (0, 64, 0),     # Green
    (0, 0, 64),     # Blue
    (64, 64, 0),    # Yellow
    (64, 0, 64),    # Magenta
    (0, 64, 64),    # Cyan
    (64, 64, 64)    # White
]

while True:
    for color in colors:
        flash_color(*color)
        time.sleep(0.5)