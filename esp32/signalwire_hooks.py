# SignalWire SWML Integration Module
# Handles SWAIG function definitions and responses following the skill pattern

try:
    import ujson as json
except ImportError:
    import json

import config
from device_sensors import DeviceSensors
from sentiment_analyzer import SentimentAnalyzer
from swaig_function_result import SwaigFunctionResult
from swml_builder import SWMLBuilder, SWAIGFunctionBuilder

class SignalWireHooks:
    """Manages SignalWire SWAIG functions and SWML integration"""

    def __init__(self, status_indicator, led_controller, word_buffer):
        print("[DEBUG] SignalWireHooks.__init__: Starting initialization")
        self.status_indicator = status_indicator
        self.led_controller = led_controller
        self.word_buffer = word_buffer
        print("[DEBUG] SignalWireHooks.__init__: About to create DeviceSensors")
        self.sensors = DeviceSensors()
        print("[DEBUG] SignalWireHooks.__init__: DeviceSensors created successfully")
        print("[DEBUG] SignalWireHooks.__init__: About to create SentimentAnalyzer")
        self.sentiment_analyzer = SentimentAnalyzer(
            api_key=config.OPENAI_API_KEY,
            model="gpt-4.1-nano",
            status_indicator=status_indicator
        )
        print("[DEBUG] SignalWireHooks.__init__: SentimentAnalyzer created successfully")

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
        """Generate the SWML document with all available SWAIG functions using SWMLBuilder"""
        prompt_text = f"""You are connected to an ESP32 device called '{config.DEVICE_NAME}' for real-time monitoring and control.

Start the conversation by greeting the user and explaining you can monitor room sensors, check system status, and control the LED. Then ask what they'd like to know.

Available capabilities:
- Monitor room temperature, humidity, and light levels using real sensors
- Get ESP32 system information (uptime, core temperature, memory)
- Control status LED with various colors
- Real-time sentiment analysis of conversation text
- Visual feedback through LED display based on conversation emotion

Sensor details:
- DHT11 temperature/humidity sensor: Provides accurate room temperature and humidity percentage
- Photoresistor light sensor: Reports light levels as percentage (>30% = bright, 20-30% = moderate lighting, <20% = dim)

IMPORTANT INSTRUCTIONS:
1. After calling any function, always tell the user what result you received from that function call. Be specific about the data you got back.
2. After providing your response to the user, always call the analyze_ai_response function with your response text to provide visual feedback on the ESP32 device.

You can check environmental conditions, system status, and control the device LED colors. Be helpful and provide natural responses about the sensor data with specific numbers."""

        # Build SWML document using the builder pattern
        builder = (SWMLBuilder()
                  .answer()
                  .ai(model="gpt-4.1-nano", temperature=0.7)
                  .add_language("English", "en-US", "openai.alloy")
                  .set_prompt(prompt_text))

        # Add debug webhook if enabled
        if config.DEBUG_WEBHOOK_LEVEL > 0:
            debug_webhook_url = f"https://{config.PAGEKITE_DOMAIN}/debug"
            builder.current_ai["params"]["debug_webhook_url"] = debug_webhook_url
            builder.current_ai["params"]["debug_webhook_level"] = config.DEBUG_WEBHOOK_LEVEL
            if config.AUDIBLE_DEBUG:
                builder.current_ai["params"]["audible_debug"] = True
            if config.VERBOSE_LOGS:
                builder.current_ai["params"]["verbose_logs"] = True
            if config.CACHE_MODE:
                builder.current_ai["params"]["cache_mode"] = True
            if config.ENABLE_ACCOUNTING:
                builder.current_ai["params"]["enable_accounting"] = True
            if config.AUDIBLE_LATENCY:
                builder.current_ai["params"]["audible_latency"] = True

        # Add all SWAIG functions using the builder
        base_url = f"https://{config.PAGEKITE_DOMAIN}/swaig"

        # Add each SWAIG function properly to the builder
        functions = self._get_swaig_functions()
        for func_def in functions:
            # Extract function parameters for proper builder integration
            name = func_def["function"]
            description = func_def["description"]
            url = func_def["webhook"]["url"]
            method = func_def["webhook"].get("method", "POST")
            parameters = func_def.get("parameters")
            
            builder.add_swaig_function(name, description, url, method, parameters)

        return builder.build()

    def _get_swaig_functions(self):
        """Get all SWAIG function definitions following the skill pattern"""
        base_url = f"https://{config.PAGEKITE_DOMAIN}/swaig"

        functions = []

        # Startup hook function
        functions.append(
            SWAIGFunctionBuilder("startup_hook")
            .description("Initialize ESP32 for new call session")
            .url(f"{base_url}/startup_hook")
            .build()
        )

        # Hangup hook function
        functions.append(
            SWAIGFunctionBuilder("hangup_hook")
            .description("Clean up ESP32 state after call ends")
            .url(f"{base_url}/hangup_hook")
            .build()
        )

        # Room weather function
        functions.append(
            SWAIGFunctionBuilder("get_room_weather")
            .description("Get comprehensive room environmental data including temperature, humidity, light level, and conditions")
            .url(f"{base_url}/get_room_weather")
            .build()
        )

        # System info function
        functions.append(
            SWAIGFunctionBuilder("get_system_info")
            .description("Get ESP32 system information including uptime, core temperature, and memory usage")
            .url(f"{base_url}/get_system_info")
            .build()
        )

        # Status LED function
        functions.append(
            SWAIGFunctionBuilder("set_status_led")
            .description("Control the status LED color")
            .url(f"{base_url}/set_status_led")
            .add_parameter("color", "string", "LED color to set",
                         required=True, enum_values=list(self.available_colors.keys()))
            .build()
        )

        # Process text function
        functions.append(
            SWAIGFunctionBuilder("process_text")
            .description("Send text to ESP32 for real-time sentiment analysis")
            .url(f"{base_url}/process_text")
            .add_parameter("text", "string", "Text content to analyze for sentiment", required=True)
            .build()
        )

        # AI response analysis function
        functions.append(
            SWAIGFunctionBuilder("analyze_ai_response")
            .description("Analyze AI response text for sentiment and emotional content to provide visual feedback")
            .url(f"{base_url}/analyze_ai_response")
            .add_parameter("ai_text", "string", "AI response text to analyze for sentiment and emotion", required=True)
            .add_parameter("context", "string", "Optional context about the conversation or situation")
            .build()
        )

        return functions

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
            elif function_name == "analyze_ai_response":
                return self._handle_analyze_ai_response(args, raw_data)
            else:
                return SwaigFunctionResult(f"Unknown function: {function_name}").to_dict()

        except Exception as e:
            if config.DEBUG:
                print(f"Error in {function_name}: {e}")
            return SwaigFunctionResult(f"Error executing {function_name}: {str(e)}").to_dict()

    def _handle_startup_hook(self, args, raw_data):
        """Handle call startup - reset device state"""
        call_id = raw_data.get("call_id", "unknown")
        if config.DEBUG:
            print(f"SignalWire call started: {call_id}")

        # Reset state for new call
        self.word_buffer.clear()
        self.led_controller.clear_all()
        self.status_indicator.set_status('idle')

        return SwaigFunctionResult(
            f"ESP32 device '{config.DEVICE_NAME}' is ready and initialized for the call."
        ).update_global_data({
            "device_name": config.DEVICE_NAME,
            "call_state": "active"
        }).to_dict()

    def _handle_hangup_hook(self, args, raw_data):
        """Handle call hangup - cleanup device state"""
        call_id = raw_data.get("call_id", "unknown")
        if config.DEBUG:
            print(f"SignalWire call ended: {call_id}")

        # Clear state after call
        self.word_buffer.clear()
        self.led_controller.clear_all()
        self.status_indicator.set_status('idle')

        return SwaigFunctionResult(
            f"Call ended. ESP32 device '{config.DEVICE_NAME}' has been reset and is ready for the next session."
        ).update_global_data({
            "call_state": "idle",
            "last_call_ended": "now"
        }).to_dict()

    def _handle_get_room_weather(self, args, raw_data):
        """Handle room weather request"""
        weather_data = self.sensors.get_room_weather()

        if config.DEBUG:
            print(f"Room weather requested: {weather_data['summary']}")

        # Simplify response to reduce payload size
        return SwaigFunctionResult(weather_data["summary"]).to_dict()

    def _handle_get_system_info(self, args, raw_data):
        """Handle system info request"""
        uptime_data = self.sensors.get_uptime()
        core_temp = self.sensors.get_core_temperature()
        memory_data = self.sensors.get_memory_info()

        response_text = (
            f"ESP32 system status: "
            f"Uptime {uptime_data['formatted']}, "
            f"core temperature {core_temp['celsius']}C, "
            f"memory {memory_data['used_kb']}kB used, {memory_data['total_kb']}kB total."
        )

        if config.DEBUG:
            print(f"System info requested: {response_text}")

        return SwaigFunctionResult(response_text).update_global_data({
            "system_info": {
                "uptime": uptime_data,
                "core_temperature": core_temp,
                "memory": memory_data,
                "device": config.DEVICE_NAME
            },
            "last_system_check": "now"
        }).to_dict()

    def _handle_set_status_led(self, args, raw_data):
        """Handle status LED color change"""
        if config.DEBUG:
            print(f"[DEBUG] set_status_led called with args: {args}")
            print(f"[DEBUG] raw_data keys: {list(raw_data.keys())}")
        
        # Extract color from the correct location in args structure
        color_name = ""
        if "parsed" in args and args["parsed"] and len(args["parsed"]) > 0:
            color_name = args["parsed"][0].get("color", "").lower()
        elif "color" in args:
            color_name = args.get("color", "").lower()
        
        if config.DEBUG:
            print(f"[DEBUG] extracted color_name: '{color_name}'")

        if color_name not in self.available_colors:
            available = ", ".join(self.available_colors.keys())
            return SwaigFunctionResult(
                f"Invalid color '{color_name}'. Available colors are: {available}"
            ).to_dict()

        # Set the LED color
        color_rgb = self.available_colors[color_name]
        self.status_indicator.np[0] = color_rgb
        self.status_indicator.np.write()

        if config.DEBUG:
            print(f"Status LED set to {color_name}: {color_rgb}")

        return SwaigFunctionResult(
            f"Status LED has been set to {color_name}."
        ).update_global_data({
            "led_status": {
                "color": color_name,
                "rgb": color_rgb
            },
            "last_led_change": "now"
        }).to_dict()

    def _handle_process_text(self, args, raw_data):
        """Handle real-time text processing for sentiment analysis"""
        text = args.get("text", "")

        if text:
            self.word_buffer.add_words(text)
            if config.DEBUG:
                print(f"Added text via SWAIG: {text[:50]}...")
            return SwaigFunctionResult(
                f"Text processed for analysis: '{text[:50]}{'...' if len(text) > 50 else ''}'"
            ).update_global_data({
                "last_text_processed": text[:100],
                "text_buffer_size": len(self.word_buffer.words)
            }).to_dict()
        else:
            return SwaigFunctionResult("No text provided for processing.").to_dict()

    def _handle_analyze_ai_response(self, args, raw_data):
        """Handle AI response analysis for sentiment and emotional feedback"""
        ai_text = args.get("ai_text", "")
        context = args.get("context", "")

        if not ai_text:
            return SwaigFunctionResult("No AI text provided for analysis.").to_dict()

        # Add AI response text to word buffer for sentiment analysis
        self.word_buffer.add_words(ai_text)

        if config.DEBUG:
            print(f"Analyzing AI response: {ai_text[:50]}...")

        # Note: In MicroPython, we can't use async in SWAIG handlers easily
        # So we'll add the text to buffer for processing by the main loop
        if config.DEBUG:
            print(f"AI response added to buffer for sentiment analysis")

        return SwaigFunctionResult(
            f"AI response analyzed and visual feedback provided."
        ).update_global_data({
            "last_ai_response": ai_text[:200],
            "ai_analysis_context": context,
            "response_timestamp": "now"
        }).to_dict()

    async def _analyze_text_sentiment(self, text):
        """
        Analyze text sentiment using OpenAI API
        Returns urgency level 0-5
        """
        try:
            result = await self.sentiment_analyzer.analyze_sentiment(text)
            return result.get("urgency_level", 0)
        except Exception as e:
            if config.DEBUG:
                print(f"Error in sentiment analysis: {e}")
            return 0