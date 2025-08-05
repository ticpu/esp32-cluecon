# Device Sensors Module
# Handles all ESP32 sensor readings and hardware interactions

import gc
import time
from machine import Pin, ADC, reset_cause
import config

class DeviceSensors:
    """Manages all ESP32 sensor readings and hardware data"""

    def __init__(self):
        self.start_time = time.ticks_ms()

        # Initialize light sensor (photoresistor voltage divider)
        # Pin 7 (3.3V) -> Photoresistor -> Pin 15 (ADC) -> 1kΩ resistor -> Ground
        try:
            # Pin 7 as digital output (HIGH to provide voltage)
            self.light_vcc_pin = Pin(7, Pin.OUT)
            self.light_vcc_pin.on()  # Provide 3.3V to one side of photoresistor

            # Pin 15 as ADC input to read voltage divider
            self.light_adc = ADC(Pin(15))
            self.light_adc.atten(ADC.ATTN_11DB)  # Full range: 3.3v

            if config.DEBUG:
                print("Light sensor initialized: Pin 7 (3.3V) -> photoresistor -> Pin 15 (ADC) -> 1kΩ -> GND")
        except Exception as e:
            if config.DEBUG:
                print(f"Light sensor init failed: {e}")
            self.light_adc = None
            self.light_vcc_pin = None

        # Initialize DHT11 sensor (3-pin temp/humidity module)
        # Pin 45: Data (D), Pin 48: VCC (N), Pin 47: Ground (G)
        try:
            from dht import DHT11
            # Setup power pins for DHT11 module
            self.dht_vcc_pin = Pin(48, Pin.OUT)  # N pin provides VCC
            self.dht_vcc_pin.on()  # Provide 3.3V power

            self.dht_gnd_pin = Pin(47, Pin.OUT)  # G pin is ground
            self.dht_gnd_pin.off()  # Provide ground

            # Initialize DHT11 sensor on data pin (D pin)
            # 10kΩ pull-up resistor between Pin 45 (data) and Pin 48 (VCC)
            self.dht_sensor = DHT11(Pin(45))

            if config.DEBUG:
                print("DHT11 sensor initialized: Pin 45 (Data), Pin 48 (VCC), Pin 47 (GND)")
        except Exception as e:
            if config.DEBUG:
                print(f"DHT sensor init failed: {e}")
            self.dht_sensor = None
            self.dht_vcc_pin = None
            self.dht_gnd_pin = None

    def get_temperature(self):
        """Get ambient temperature reading from DHT sensor"""
        if self.dht_sensor:
            try:
                # Ensure power pins are correct
                self.dht_vcc_pin.on()
                self.dht_gnd_pin.off()

                # Read from DHT sensor
                self.dht_sensor.measure()
                temp_c = self.dht_sensor.temperature()
                temp_f = temp_c * 9/5 + 32

                if config.DEBUG:
                    print(f"DHT temperature: {temp_c}°C ({temp_f}°F)")

                return {
                    "celsius": round(temp_c, 1),
                    "fahrenheit": round(temp_f, 1),
                    "source": "dht22_pin47"
                }
            except Exception as e:
                if config.DEBUG:
                    print(f"DHT temperature read error: {e}")
                return {
                    "celsius": 0.0,
                    "fahrenheit": 32.0,
                    "source": "dht_error"
                }
        else:
            return {
                "celsius": None,
                "fahrenheit": None,
                "source": "sensor_failed"
            }

    def get_humidity(self):
        """Get humidity reading from DHT sensor"""
        if self.dht_sensor:
            try:
                # Ensure power pins are correct
                self.dht_vcc_pin.on()
                self.dht_gnd_pin.off()

                # Read from DHT sensor (reuse measurement from temperature)
                self.dht_sensor.measure()
                humidity = self.dht_sensor.humidity()

                if config.DEBUG:
                    print(f"DHT humidity: {humidity}%")

                return round(humidity, 1)
            except Exception as e:
                if config.DEBUG:
                    print(f"DHT humidity read error: {e}")
                return None
        else:
            return None

    def get_light_level(self):
        """Get light sensor reading from photoresistor voltage divider"""
        if self.light_adc and self.light_vcc_pin:
            try:
                # Ensure VCC pin is still high
                self.light_vcc_pin.on()

                # Read ADC value (0-4095)
                raw_reading = self.light_adc.read()

                # Convert to voltage (0-3.3V)
                voltage = (raw_reading / 4095) * 3.3

                # Convert to light percentage
                # Higher voltage = more light (lower photoresistor resistance)
                # Lower voltage = less light (higher photoresistor resistance)
                light_percent = (voltage / 3.3) * 100

                if config.DEBUG:
                    print(f"Light sensor: raw={raw_reading}, voltage={voltage:.2f}V, light={light_percent:.1f}%")

                return {
                    "percent": round(light_percent, 1),
                    "raw": raw_reading,
                    "voltage": round(voltage, 2),
                    "source": "photoresistor_voltage_divider"
                }
            except Exception as e:
                if config.DEBUG:
                    print(f"Light sensor read error: {e}")
                return {
                    "percent": 0.0,
                    "raw": 0,
                    "voltage": 0.0,
                    "source": "error"
                }
        else:
            return {
                "percent": 0.0,
                "raw": 0,
                "voltage": 0.0,
                "source": "no_sensor"
            }

    def get_core_temperature(self):
        """Get ESP32 internal core temperature"""
        try:
            # ESP32 internal temperature sensor (if available)
            from esp32 import raw_temperature
            temp_f = raw_temperature()
            temp_c = (temp_f - 32) * 5/9
            return {
                "celsius": round(temp_c, 1),
                "fahrenheit": round(temp_f, 1),
                "source": "esp32_core"
            }
        except:
            # Fallback mock reading
            return {
                "celsius": 42.0,
                "fahrenheit": 107.6,
                "source": "mock_core"
            }

    def get_uptime(self):
        """Get ESP32 uptime since boot"""
        current_time = time.ticks_ms()
        uptime_ms = time.ticks_diff(current_time, self.start_time)

        uptime_seconds = uptime_ms // 1000
        uptime_minutes = uptime_seconds // 60
        uptime_hours = uptime_minutes // 60
        uptime_days = uptime_hours // 24

        return {
            "milliseconds": uptime_ms,
            "seconds": uptime_seconds,
            "minutes": uptime_minutes,
            "hours": uptime_hours,
            "days": uptime_days,
            "formatted": f"{uptime_days}d {uptime_hours%24}h {uptime_minutes%60}m {uptime_seconds%60}s"
        }

    def get_memory_info(self):
        """Get memory usage information"""
        gc.collect()  # Force garbage collection for accurate reading
        free_memory = gc.mem_free()
        allocated_memory = gc.mem_alloc()
        total_memory = free_memory + allocated_memory

        return {
            "free_bytes": free_memory,
            "allocated_bytes": allocated_memory,
            "total_bytes": total_memory,
            "free_percent": round((free_memory / total_memory) * 100, 1),
            "used_percent": round((allocated_memory / total_memory) * 100, 1)
        }

    def get_room_weather(self):
        """Get comprehensive room weather data"""
        if config.DEBUG:
            print("[DEBUG] get_room_weather: Starting sensor readings")
        temp_data = self.get_temperature()
        if config.DEBUG:
            print(f"[DEBUG] get_room_weather: temp_data = {temp_data}")
        humidity = self.get_humidity()
        if config.DEBUG:
            print(f"[DEBUG] get_room_weather: humidity = {humidity}")
        light_data = self.get_light_level()
        if config.DEBUG:
            print(f"[DEBUG] get_room_weather: light_data = {light_data}")

        # Determine weather description based on sensors
        if temp_data["celsius"] > 25:
            if humidity is not None and humidity > 60:
                weather_desc = "warm and humid"
            else:
                weather_desc = "warm and dry"
        elif temp_data["celsius"] < 20:
            if humidity is not None and humidity > 60:
                weather_desc = "cool and humid"
            else:
                weather_desc = "cool and dry"
        else:
            weather_desc = "comfortable"

        # Add lighting condition based on light sensor data
        # Adjusted thresholds based on actual sensor readings:
        # Covered: ~9.5%, Conference room: ~33.8%
        light_percent = light_data["percent"]
        if light_percent > 30:
            light_desc = "bright"
        elif light_percent > 20:
            light_desc = "moderate lighting"
        else:
            light_desc = "dim"

        return {
            "temperature": temp_data,
            "humidity_percent": humidity,
            "light_data": light_data,
            "weather_description": weather_desc,
            "lighting_description": light_desc,
            "summary": f"The room is {weather_desc} with {light_desc}. Temperature is {temp_data['celsius']}°C ({temp_data['fahrenheit']}°F), humidity at {humidity if humidity is not None else 'N/A'}%, and light level at {light_percent}% ({light_data['voltage']}V from photoresistor)."
        }

    def get_all_sensor_data(self):
        """Get all available sensor data"""
        return {
            "device": config.DEVICE_NAME,
            "timestamp": time.ticks_ms(),
            "room_weather": self.get_room_weather(),
            "core_temperature": self.get_core_temperature(),
            "uptime": self.get_uptime(),
            "memory": self.get_memory_info()
        }