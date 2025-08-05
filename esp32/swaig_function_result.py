# MicroPython-compatible SignalWire SWAIG Function Result
# Based on signalwire_agents.core.function_result.SwaigFunctionResult
# Simplified for ESP32/MicroPython use

try:
    import ujson as json
except ImportError:
    import json

class SwaigFunctionResult:
    """
    MicroPython-compatible wrapper for SWAIG function responses.

    Handles proper formatting of response text and actions for SignalWire AI.
    Simplified version of the full SignalWire Agents SDK SwaigFunctionResult.

    Example usage:
        # Simple response
        return SwaigFunctionResult("Task completed successfully")

        # With actions
        result = SwaigFunctionResult("Setting LED color")
        result.add_action("set_global_data", {"led_color": "red"})
        return result

        # Method chaining
        return (SwaigFunctionResult("Processing request")
                .add_action("log", {"message": "Request processed"})
                .add_action("set_global_data", {"status": "complete"}))
    """

    def __init__(self, response=None, post_process=False):
        """
        Initialize a new SWAIG function result

        Args:
            response: Optional text response for the AI to speak
            post_process: If True, let AI respond once more before executing actions
        """
        self.response = response or ""
        self.action = []
        self.post_process = post_process

    def set_response(self, response):
        """Set the natural language response text"""
        self.response = response
        return self

    def set_post_process(self, post_process):
        """Set whether to enable post-processing"""
        self.post_process = post_process
        return self

    def add_action(self, name, data):
        """
        Add a structured action to the response

        Args:
            name: Action type (e.g., "set_global_data", "log")
            data: Action data (string, boolean, dict, list)
        """
        self.action.append({name: data})
        return self

    def add_actions(self, actions):
        """
        Add multiple structured actions

        Args:
            actions: List of action dictionaries
        """
        self.action.extend(actions)
        return self

    def update_global_data(self, data):
        """
        Update global agent data variables

        Args:
            data: Dictionary of key-value pairs to set
        """
        return self.add_action("set_global_data", data)

    def say(self, text):
        """Make the agent speak specific text"""
        return self.add_action("say", text)

    def hangup(self):
        """Terminate the call"""
        return self.add_action("hangup", True)

    def stop(self):
        """Stop the agent execution"""
        return self.add_action("stop", True)

    def wait_for_user(self, enabled=None, timeout=None):
        """
        Control how agent waits for user input

        Args:
            enabled: Boolean to enable/disable waiting
            timeout: Number of seconds to wait
        """
        if timeout is not None:
            wait_value = timeout
        elif enabled is not None:
            wait_value = enabled
        else:
            wait_value = True

        return self.add_action("wait_for_user", wait_value)

    def play_background_file(self, filename, wait=False):
        """
        Play audio file in background

        Args:
            filename: Audio file URL or path
            wait: Whether to suppress attention-getting during playback
        """
        if wait:
            return self.add_action("playback_bg", {"file": filename, "wait": True})
        else:
            return self.add_action("playback_bg", filename)

    def stop_background_file(self):
        """Stop currently playing background file"""
        return self.add_action("stop_playback_bg", True)

    def set_end_of_speech_timeout(self, milliseconds):
        """Adjust end of speech timeout in milliseconds"""
        return self.add_action("end_of_speech_timeout", milliseconds)

    def remove_global_data(self, keys):
        """
        Remove global agent data variables

        Args:
            keys: Single key string or list of keys to remove
        """
        return self.add_action("unset_global_data", keys)

    def toggle_functions(self, function_toggles):
        """
        Enable/disable specific SWAIG functions

        Args:
            function_toggles: List of dicts with 'function' and 'active' keys
        """
        return self.add_action("toggle_functions", function_toggles)

    def update_settings(self, settings):
        """
        Update agent runtime settings

        Args:
            settings: Dictionary of settings (temperature, top-p, etc.)
        """
        return self.add_action("settings", settings)

    def switch_context(self, system_prompt=None, user_prompt=None,
                      consolidate=False, full_reset=False):
        """
        Change agent context/prompt during conversation

        Args:
            system_prompt: New system prompt
            user_prompt: User message to add
            consolidate: Whether to summarize existing conversation
            full_reset: Whether to do complete context reset
        """
        if system_prompt and not user_prompt and not consolidate and not full_reset:
            # Simple string context switch
            return self.add_action("context_switch", system_prompt)
        else:
            # Advanced object context switch
            context_data = {}
            if system_prompt:
                context_data["system_prompt"] = system_prompt
            if user_prompt:
                context_data["user_prompt"] = user_prompt
            if consolidate:
                context_data["consolidate"] = True
            if full_reset:
                context_data["full_reset"] = True
            return self.add_action("context_switch", context_data)

    def execute_swml(self, swml_content, transfer=False):
        """
        Execute SWML content with optional transfer behavior

        Args:
            swml_content: SWML data as dict or JSON string
            transfer: Whether call should exit agent after execution
        """
        if isinstance(swml_content, str):
            # Parse JSON string
            try:
                swml_data = json.loads(swml_content)
            except:
                raise ValueError("Invalid JSON in swml_content")
        elif isinstance(swml_content, dict):
            swml_data = swml_content
        else:
            raise TypeError("swml_content must be string or dict")

        action = swml_data
        if transfer:
            action["transfer"] = "true"

        return self.add_action("SWML", action)

    def to_dict(self):
        """
        Convert to the JSON structure expected by SWAIG

        Returns:
            Dictionary in SWAIG function response format
        """
        result = {}

        # Add response if present
        if self.response:
            result["response"] = self.response

        # Add action if present
        if self.action:
            result["action"] = self.action

        # Add post_process if enabled and we have actions
        if self.post_process and self.action:
            result["post_process"] = True

        # Ensure we have at least one of response or action
        if not result:
            result["response"] = "Action completed."

        return result

    def to_json(self):
        """Convert to JSON string for HTTP responses"""
        return json.dumps(self.to_dict())