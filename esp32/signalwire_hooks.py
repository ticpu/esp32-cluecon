# SignalWire SWML Integration Module
# Handles SWAIG function definitions and responses following the skill pattern

try:
    import ujson as json
except ImportError:
    import json

import config
from device_sensors import DeviceSensors

class SignalWireHooks:
    """Manages SignalWire SWAIG functions and SWML integration"""
    
    def __init__(self, status_indicator, led_controller, word_buffer):
        self.status_indicator = status_indicator
        self.led_controller = led_controller
        self.word_buffer = word_buffer
        self.sensors = DeviceSensors()
        
        # Available LED colors for user selection
        self.available_colors = {
            "red": (102, 0, 0),
            "green": (0, 102, 0),
            "blue": (0, 0, 102),
            "yellow": (102, 102, 0),
            "purple": (102, 0, 102),
            "cyan": (0, 102, 102),
            "white": (102, 102, 102),
            "orange": (102, 51, 0),
            "pink": (102, 51, 51),
            "lime": (51, 102, 0),
            "off": (0, 0, 0)
        }
    
    def get_swml_document(self):
        """Generate the SWML document with all available SWAIG functions"""
        return {
            "version": "1.0.0",
            "sections": {
                "main": [
                    {
                        "answer": {}
                    },
                    {
                        "ai": {
                            "languages": [
                                {
                                    "name": "English",
                                    "code": "en-US",
                                    "voice": "openai.alloy"
                                }
                            ],
                            "params": {
                                "ai_model": "gpt-4o-mini"
                            },
                            "prompt": {
                                "text": f"""You are connected to an ESP32 device called '{config.DEVICE_NAME}' for real-time monitoring and control.

Start the conversation by greeting the user and explaining you can monitor room sensors, check system status, and control the LED. Then ask what they'd like to know.

Available capabilities:
- Monitor room temperature, humidity, and light levels using real sensors
- Get ESP32 system information (uptime, core temperature, memory)
- Control status LED with various colors
- Real-time sentiment analysis of conversation text

Sensor details:
- DHT11 temperature/humidity sensor: Provides accurate room temperature (°C/°F) and humidity percentage
- Photoresistor light sensor: Reports light levels as percentage (>30% = bright, 20-30% = moderate lighting, <20% = dim)
- Light readings: Phone LED ~74%, conference room ~34%, covered ~10%

You can check environmental conditions, system status, and control the device LED colors. Be helpful and provide natural responses about the sensor data with specific numbers.""",
                                "temperature": 0.7
                            },
                            "SWAIG": {
                                "functions": self._get_swaig_functions()
                            }
                        }
                    }
                ]
            }
        }
    
    def _get_swaig_functions(self):
        """Get all SWAIG function definitions following the skill pattern"""
        base_url = f"https://{config.PAGEKITE_DOMAIN}/swaig"
        
        return [
            {
                "function": "startup_hook",
                "description": "Initialize ESP32 for new call session",
                "webhook": {
                    "url": f"{base_url}/startup_hook",
                    "method": "POST"
                },
                "parameters": {
                    "type": "object",
                    "properties": {}
                }
            },
            {
                "function": "hangup_hook", 
                "description": "Clean up ESP32 state after call ends",
                "webhook": {
                    "url": f"{base_url}/hangup_hook",
                    "method": "POST"
                },
                "parameters": {
                    "type": "object",
                    "properties": {}
                }
            },
            {
                "function": "get_room_weather",
                "description": "Get comprehensive room environmental data including temperature, humidity, light level, and conditions",
                "webhook": {
                    "url": f"{base_url}/get_room_weather",
                    "method": "POST"
                },
                "parameters": {
                    "type": "object",
                    "properties": {}
                }
            },
            {
                "function": "get_system_info",
                "description": "Get ESP32 system information including uptime, core temperature, and memory usage",
                "webhook": {
                    "url": f"{base_url}/get_system_info", 
                    "method": "POST"
                },
                "parameters": {
                    "type": "object",
                    "properties": {}
                }
            },
            {
                "function": "set_status_led",
                "description": f"Control the status LED color. Available colors: {', '.join(self.available_colors.keys())}",
                "webhook": {
                    "url": f"{base_url}/set_status_led",
                    "method": "POST"
                },
                "parameters": {
                    "type": "object",
                    "properties": {
                        "color": {
                            "type": "string",
                            "description": f"LED color to set. Options: {', '.join(self.available_colors.keys())}",
                            "enum": list(self.available_colors.keys())
                        }
                    },
                    "required": ["color"]
                }
            },
            {
                "function": "process_text",
                "description": "Send text to ESP32 for real-time sentiment analysis",
                "webhook": {
                    "url": f"{base_url}/process_text",
                    "method": "POST"
                },
                "parameters": {
                    "type": "object",
                    "properties": {
                        "text": {
                            "type": "string",
                            "description": "Text content to analyze for sentiment"
                        }
                    },
                    "required": ["text"]
                }
            }
        ]
    
    def handle_swaig_function(self, function_name, args, raw_data):
        """Handle SWAIG function calls and return appropriate responses"""
        if config.DEBUG:
            print(f"SWAIG function called: {function_name}")
        
        try:
            if function_name == "startup_hook":
                return self._handle_startup_hook(args, raw_data)
            elif function_name == "hangup_hook":
                return self._handle_hangup_hook(args, raw_data)
            elif function_name == "get_room_weather":
                return self._handle_get_room_weather(args, raw_data)
            elif function_name == "get_system_info":
                return self._handle_get_system_info(args, raw_data)
            elif function_name == "set_status_led":
                return self._handle_set_status_led(args, raw_data)
            elif function_name == "process_text":
                return self._handle_process_text(args, raw_data)
            else:
                return {"response": f"Unknown function: {function_name}"}
                
        except Exception as e:
            if config.DEBUG:
                print(f"Error in {function_name}: {e}")
            return {"response": f"Error executing {function_name}: {str(e)}"}
    
    def _handle_startup_hook(self, args, raw_data):
        """Handle call startup - reset device state"""
        call_id = raw_data.get("call_id", "unknown")
        if config.DEBUG:
            print(f"SignalWire call started: {call_id}")
        
        # Reset state for new call
        self.word_buffer.clear()
        self.led_controller.clear_all()
        self.status_indicator.set_status('idle')
        
        return {
            "response": f"ESP32 device '{config.DEVICE_NAME}' is ready and initialized for the call."
        }
    
    def _handle_hangup_hook(self, args, raw_data):
        """Handle call hangup - cleanup device state"""
        call_id = raw_data.get("call_id", "unknown")
        if config.DEBUG:
            print(f"SignalWire call ended: {call_id}")
        
        # Clear state after call
        self.word_buffer.clear()
        self.led_controller.clear_all()
        self.status_indicator.set_status('idle')
        
        return {
            "response": f"Call ended. ESP32 device '{config.DEVICE_NAME}' has been reset and is ready for the next session."
        }
    
    def _handle_get_room_weather(self, args, raw_data):
        """Handle room weather request"""
        weather_data = self.sensors.get_room_weather()
        
        if config.DEBUG:
            print(f"Room weather requested: {weather_data['summary']}")
        
        return {
            "response": weather_data["summary"],
            "data": weather_data
        }
    
    def _handle_get_system_info(self, args, raw_data):
        """Handle system info request"""
        uptime_data = self.sensors.get_uptime()
        core_temp = self.sensors.get_core_temperature()
        memory_data = self.sensors.get_memory_info()
        
        response_text = (
            f"ESP32 system status: "
            f"Uptime {uptime_data['formatted']}, "
            f"core temperature {core_temp['celsius']}°C ({core_temp['fahrenheit']}°F), "
            f"memory usage {memory_data['used_percent']}% with {memory_data['free_bytes']} bytes free."
        )
        
        if config.DEBUG:
            print(f"System info requested: {response_text}")
        
        return {
            "response": response_text,
            "data": {
                "uptime": uptime_data,
                "core_temperature": core_temp,
                "memory": memory_data,
                "device": config.DEVICE_NAME
            }
        }
    
    def _handle_set_status_led(self, args, raw_data):
        """Handle status LED color change"""
        color_name = args.get("color", "").lower()
        
        if color_name not in self.available_colors:
            available = ", ".join(self.available_colors.keys())
            return {
                "response": f"Invalid color '{color_name}'. Available colors are: {available}"
            }
        
        # Set the LED color
        color_rgb = self.available_colors[color_name]
        self.status_indicator.np[0] = color_rgb
        self.status_indicator.np.write()
        
        if config.DEBUG:
            print(f"Status LED set to {color_name}: {color_rgb}")
        
        return {
            "response": f"Status LED has been set to {color_name}.",
            "data": {
                "color": color_name,
                "rgb": color_rgb
            }
        }
    
    def _handle_process_text(self, args, raw_data):
        """Handle real-time text processing for sentiment analysis"""
        text = args.get("text", "")
        
        if text:
            self.word_buffer.add_words(text)
            if config.DEBUG:
                print(f"Added text via SWAIG: {text[:50]}...")
            return {
                "response": f"Text processed for sentiment analysis: '{text[:50]}{'...' if len(text) > 50 else ''}'"
            }
        else:
            return {
                "response": "No text provided for processing."
            }