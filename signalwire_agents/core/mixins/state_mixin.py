"""
Copyright (c) 2025 SignalWire

This file is part of the SignalWire AI Agents SDK.

Licensed under the MIT License.
See LICENSE file in the project root for full license information.
"""

from typing import Callable

from signalwire_agents.core.function_result import SwaigFunctionResult


class StateMixin:
    """
    Mixin class containing all state and session management methods for AgentBase
    """
    
    def _create_tool_token(self, tool_name: str, call_id: str) -> str:
        """
        Create a secure token for a tool call
        
        Args:
            tool_name: Name of the tool
            call_id: Call ID for this session
            
        Returns:
            Secure token string
        """
        try:
            # Ensure we have a session manager
            if not hasattr(self, '_session_manager'):
                self.log.error("no_session_manager")
                return ""
                
            # Create the token using the session manager
            return self._session_manager.create_tool_token(tool_name, call_id)
        except Exception as e:
            self.log.error("token_creation_error", error=str(e), tool=tool_name, call_id=call_id)
            return ""
    
    def validate_tool_token(self, function_name: str, token: str, call_id: str) -> bool:
        """
        Validate a tool token
        
        Args:
            function_name: Name of the function/tool
            token: Token to validate
            call_id: Call ID for the session
            
        Returns:
            True if token is valid, False otherwise
        """
        try:
            # Skip validation for non-secure tools
            if function_name not in self._tool_registry._swaig_functions:
                self.log.warning("unknown_function", function=function_name)
                return False
                
            # Get the function and check if it's secure
            func = self._tool_registry._swaig_functions[function_name]
            is_secure = True  # Default to secure
            
            if isinstance(func, dict):
                # For raw dictionaries (DataMap functions), they're always secure
                is_secure = True
            else:
                # For SWAIGFunction objects, check the secure attribute
                is_secure = func.secure
                
            # Always allow non-secure functions
            if not is_secure:
                self.log.debug("non_secure_function_allowed", function=function_name)
                return True
            
            # Check if we have a session manager
            if not hasattr(self, '_session_manager'):
                self.log.error("no_session_manager")
                return False
            
            # Handle missing token
            if not token:
                self.log.warning("missing_token", function=function_name)
                return False
                
            # For debugging: Log token details
            try:
                # Capture original parameters
                self.log.debug("token_validate_input", 
                              function=function_name, 
                              call_id=call_id, 
                              token_length=len(token))
                
                # Try to decode token for debugging
                if hasattr(self._session_manager, 'debug_token'):
                    debug_info = self._session_manager.debug_token(token)
                    self.log.debug("token_debug", debug_info=debug_info)
                    
                    # Extract token components
                    if debug_info.get("valid_format") and "components" in debug_info:
                        components = debug_info["components"]
                        token_call_id = components.get("call_id")
                        token_function = components.get("function")
                        token_expiry = components.get("expiry")
                        
                        # Log parameter mismatches
                        if token_function != function_name:
                            self.log.warning("token_function_mismatch", 
                                           expected=function_name, 
                                           actual=token_function)
                        
                        if token_call_id != call_id:
                            self.log.warning("token_call_id_mismatch", 
                                           expected=call_id, 
                                           actual=token_call_id)
                            
                        # Check expiration
                        if debug_info.get("status", {}).get("is_expired"):
                            self.log.warning("token_expired", 
                                           expires_in=debug_info["status"].get("expires_in_seconds"))
            except Exception as e:
                self.log.error("token_debug_error", error=str(e))
                
            # Use call_id from token if the provided one is empty
            if not call_id and hasattr(self._session_manager, 'debug_token'):
                try:
                    debug_info = self._session_manager.debug_token(token)
                    if debug_info.get("valid_format") and "components" in debug_info:
                        token_call_id = debug_info["components"].get("call_id")
                        if token_call_id:
                            self.log.debug("using_call_id_from_token", call_id=token_call_id)
                            is_valid = self._session_manager.validate_tool_token(function_name, token, token_call_id)
                            if is_valid:
                                self.log.debug("token_valid_with_extracted_call_id")
                                return True
                except Exception as e:
                    self.log.error("error_using_call_id_from_token", error=str(e))
            
            # Normal validation with provided call_id
            is_valid = self._session_manager.validate_tool_token(function_name, token, call_id)
            
            if is_valid:
                self.log.debug("token_valid", function=function_name)
            else:
                self.log.warning("token_invalid", function=function_name)
                
            return is_valid
        except Exception as e:
            self.log.error("token_validation_error", error=str(e), function=function_name)
            return False
    
    # Note: set_dynamic_config_callback is implemented in WebMixin
    
    def _register_state_tracking_tools(self):
        """
        Register special tools for state tracking
        
        This adds startup_hook and hangup_hook SWAIG functions that automatically
        activate and deactivate the session when called. These are useful for
        tracking call state and cleaning up resources when a call ends.
        """
        # Register startup hook to activate session
        self.define_tool(
            name="startup_hook",
            description="Called when a new conversation starts to initialize state",
            parameters={},
            handler=lambda args, raw_data: self._handle_startup_hook(args, raw_data),
            secure=False  # No auth needed for this system function
        )
        
        # Register hangup hook to end session
        self.define_tool(
            name="hangup_hook",
            description="Called when conversation ends to clean up resources",
            parameters={},
            handler=lambda args, raw_data: self._handle_hangup_hook(args, raw_data),
            secure=False  # No auth needed for this system function
        )
    
    def _handle_startup_hook(self, args, raw_data):
        """
        Handle the startup hook function call
        
        Args:
            args: Function arguments (empty for this hook)
            raw_data: Raw request data containing call_id
            
        Returns:
            Success response
        """
        call_id = raw_data.get("call_id") if raw_data else None
        if call_id:
            self.log.info("session_activated", call_id=call_id)
            self._session_manager.activate_session(call_id)
            return SwaigFunctionResult("Session activated")
        else:
            self.log.warning("session_activation_failed", error="No call_id provided")
            return SwaigFunctionResult("Failed to activate session: No call_id provided")
    
    def _handle_hangup_hook(self, args, raw_data):
        """
        Handle the hangup hook function call
        
        Args:
            args: Function arguments (empty for this hook)
            raw_data: Raw request data containing call_id
            
        Returns:
            Success response
        """
        call_id = raw_data.get("call_id") if raw_data else None
        if call_id:
            self.log.info("session_ended", call_id=call_id)
            self._session_manager.end_session(call_id)
            return SwaigFunctionResult("Session ended")
        else:
            self.log.warning("session_end_failed", error="No call_id provided")
            return SwaigFunctionResult("Failed to end session: No call_id provided")