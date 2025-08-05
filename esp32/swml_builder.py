# MicroPython-compatible SWML Builder
# Based on signalwire_agents.core.swml_builder.SWMLBuilder
# Simplified for ESP32/MicroPython use

try:
    import ujson as json
except ImportError:
    import json

class SWMLBuilder:
    """
    MicroPython-compatible SWML document builder
    
    Provides a fluent interface for building SWML documents without manual JSON construction.
    Simplified version of the full SignalWire Agents SDK SWMLBuilder.
    
    Example usage:
        # Create a complete SWML document
        builder = SWMLBuilder()
        swml_doc = (builder
            .answer()
            .ai(model="gpt-4o-mini", temperature=0.7)
            .add_language("English", "en-US", "openai.alloy")
            .set_prompt("You are a helpful assistant")
            .add_swaig_function("get_time", "Get current time", "https://api.example.com/time")
            .build())
    """
    
    def __init__(self, version="1.0.0"):
        """Initialize SWML builder with version"""
        self.version = version
        self.sections = {"main": []}
        self.current_ai = None
    
    def answer(self):
        """Add answer verb to start the call"""
        self.sections["main"].append({"answer": {}})
        return self
    
    def ai(self, model="gpt-4o-mini", temperature=0.7, **params):
        """
        Add AI verb to the document
        
        Args:
            model: AI model to use
            temperature: Model temperature (0.0-2.0)
            **params: Additional AI parameters
        """
        ai_config = {
            "languages": [],
            "params": {"ai_model": model, "temperature": temperature},
            "prompt": {"text": ""},
            "SWAIG": {"functions": []}
        }
        
        # Add any additional parameters
        ai_config["params"].update(params)
        
        self.current_ai = ai_config
        self.sections["main"].append({"ai": ai_config})
        return self
    
    def add_language(self, name, code, voice, speech_fillers=None, function_fillers=None):
        """
        Add a language configuration to the current AI
        
        Args:
            name: Display name for the language
            code: ISO language code (e.g., "en-US")
            voice: Voice identifier (e.g., "openai.alloy")
            speech_fillers: Optional list of speech filler phrases
            function_fillers: Optional list of function filler phrases
        """
        if not self.current_ai:
            raise ValueError("Must call ai() before adding languages")
            
        language = {
            "name": name,
            "code": code,
            "voice": voice
        }
        
        if speech_fillers:
            language["speech_fillers"] = speech_fillers
        if function_fillers:
            language["function_fillers"] = function_fillers
            
        self.current_ai["languages"].append(language)
        return self
    
    def set_prompt(self, text, temperature=None):
        """
        Set the AI prompt text
        
        Args:
            text: Prompt text for the AI
            temperature: Optional temperature override
        """
        if not self.current_ai:
            raise ValueError("Must call ai() before setting prompt")
            
        self.current_ai["prompt"]["text"] = text
        if temperature is not None:
            self.current_ai["prompt"]["temperature"] = temperature
        return self
    
    def add_swaig_function(self, name, description, url, method="POST", parameters=None):
        """
        Add a SWAIG function to the current AI
        
        Args:
            name: Function name
            description: Function description
            url: Webhook URL for the function
            method: HTTP method (default: POST)
            parameters: Function parameter schema
        """
        if not self.current_ai:
            raise ValueError("Must call ai() before adding SWAIG functions")
            
        function = {
            "function": name,
            "description": description,
            "webhook": {
                "url": url,
                "method": method
            }
        }
        
        if parameters:
            function["parameters"] = parameters
        else:
            function["parameters"] = {
                "type": "object",
                "properties": {}
            }
            
        self.current_ai["SWAIG"]["functions"].append(function)
        return self
    
    def add_swaig_function_with_params(self, name, description, url, param_properties, required=None, method="POST"):
        """
        Add a SWAIG function with detailed parameter schema
        
        Args:
            name: Function name
            description: Function description
            url: Webhook URL
            param_properties: Dictionary of parameter definitions
            required: List of required parameter names
            method: HTTP method (default: POST)
        """
        parameters = {
            "type": "object",
            "properties": param_properties
        }
        
        if required:
            parameters["required"] = required
            
        return self.add_swaig_function(name, description, url, method, parameters)
    
    def connect(self, destination, from_addr=None):
        """
        Add connect verb to transfer the call
        
        Args:
            destination: Where to connect (phone number, SIP address)
            from_addr: Optional caller ID override
        """
        connect_config = {"to": destination}
        if from_addr:
            connect_config["from"] = from_addr
            
        self.sections["main"].append({"connect": connect_config})
        return self
    
    def play(self, url, volume=None):
        """
        Add play verb to play audio
        
        Args:
            url: Audio file URL
            volume: Optional volume level
        """
        play_config = {"url": url}
        if volume is not None:
            play_config["volume"] = volume
            
        self.sections["main"].append({"play": play_config})
        return self
    
    def hangup(self):
        """Add hangup verb to end the call"""
        self.sections["main"].append({"hangup": {}})
        return self
    
    def record_call(self, format="wav", stereo=False):
        """
        Add record_call verb for background recording
        
        Args:
            format: Recording format ("wav" or "mp3")
            stereo: Whether to record in stereo
        """
        record_config = {
            "format": format,
            "stereo": stereo
        }
        self.sections["main"].append({"record_call": record_config})
        return self
    
    def set_variable(self, name, value):
        """
        Add set verb to set a variable
        
        Args:
            name: Variable name
            value: Variable value
        """
        self.sections["main"].append({"set": {name: value}})
        return self
    
    def transfer(self, destination):
        """
        Add transfer verb
        
        Args:
            destination: Transfer destination URL
        """
        self.sections["main"].append({"transfer": {"dest": destination}})
        return self
    
    def build(self):
        """
        Build and return the complete SWML document
        
        Returns:
            Dictionary representing the SWML document
        """
        return {
            "version": self.version,
            "sections": self.sections
        }
    
    def to_json(self):
        """
        Build and return the SWML document as JSON string
        
        Returns:
            JSON string representation of the SWML document
        """
        return json.dumps(self.build())

class SWAIGFunctionBuilder:
    """
    Builder for creating SWAIG function definitions
    
    Example usage:
        func = (SWAIGFunctionBuilder("get_weather")
                .description("Get current weather")
                .url("https://api.example.com/weather")
                .add_parameter("location", "string", "Location name", required=True)
                .build())
    """
    
    def __init__(self, name):
        """Initialize with function name"""
        self.function_def = {
            "function": name,
            "description": "",
            "webhook": {
                "url": "",
                "method": "POST"
            },
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    
    def description(self, desc):
        """Set function description"""
        self.function_def["description"] = desc
        return self
    
    def url(self, webhook_url):
        """Set webhook URL"""
        self.function_def["webhook"]["url"] = webhook_url
        return self
    
    def method(self, http_method):
        """Set HTTP method"""
        self.function_def["webhook"]["method"] = http_method
        return self
    
    def add_parameter(self, name, param_type, description, required=False, enum_values=None):
        """
        Add a parameter to the function
        
        Args:
            name: Parameter name
            param_type: Parameter type ("string", "number", "boolean", etc.)
            description: Parameter description
            required: Whether parameter is required
            enum_values: Optional list of allowed values
        """
        param_def = {
            "type": param_type,
            "description": description
        }
        
        if enum_values:
            param_def["enum"] = enum_values
            
        self.function_def["parameters"]["properties"][name] = param_def
        
        if required:
            self.function_def["parameters"]["required"].append(name)
            
        return self
    
    def build(self):
        """Build and return the function definition"""
        # Clean up empty required array
        if not self.function_def["parameters"]["required"]:
            del self.function_def["parameters"]["required"]
        return self.function_def