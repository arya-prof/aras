"""
Centralized response management for Aras Agent.
"""

from typing import Dict, List
from aras.config import settings


class ResponseManager:
    """Manages all user-facing responses and messages."""
    
    def __init__(self):
        self.error_responses = {
            "ai_unavailable": "Sorry, AI processing is not available.",
            "command_error": "Sorry, I encountered an error processing your command.",
            "file_operation_unknown": "I'm not sure what file operation you want to perform. Please be more specific.",
            "voice_recognition_unavailable": "Error: Voice recognition not available",
            "microphone_unavailable": "Error: Microphone not available",
            "speech_recognition_error": "Error: Speech recognition service error",
            "tts_error": "Error: TTS error"
        }
        
        self.interactive_prompts = {
            "file_name_request": "What would you like to name the file?",
            "folder_name_request": "What would you like to name the folder?",
            "file_delete_request": "Which file would you like to delete?",
            "folder_delete_request": "Which folder would you like to delete?",
            "file_check_request": "Which file would you like to check?",
            "file_info_request": "Which file would you like information about?"
        }
        
        self.wake_responses = {
            "listening_started": "Hello! I'm listening. How can I help you?",
            "wake_word_detected": "Hello! I'm listening. How can I help you?"
        }
        
        self.help_messages = {
            "wake_words": "Try: 'Hey Aras', 'Hi Aras', 'Hello', or 'Can you hear me'",
            "command_suggestions": "Try: 'home status', 'show system info', 'search for weather', 'send an email'",
            "voice_commands": "Available commands: 'home status', 'show system info', 'search for weather', etc.",
            "long_audio_support": "Note: Long audio support enabled (up to 30 seconds per command)",
            "speech_tip": "Tip: Pause briefly after speaking to help detection"
        }
        
        self.debug_messages = {
            "voice_processing_start": "Processing recognized text: '{text}'",
            "voice_processing_success": "Voice command processed successfully!",
            "voice_processing_failed": "Command not recognized: '{text}'",
            "llm_processing_start": "Starting LLM processing",
            "llm_processing_failed": "LLM processing failed, trying pattern matching",
            "pattern_matching_start": "Starting pattern matching",
            "pattern_matched": "Pattern matched: {pattern}",
            "no_match": "No patterns matched for: '{text}'",
            "processing_complete": "Processing complete",
            "processing_failed": "Processing failed"
        }
        
        self.status_messages = {
            "voice_listening_started": "Continuous voice listening started",
            "voice_listening_paused": "Voice listening paused",
            "voice_listening_resumed": "Voice listening resumed",
            "voice_listening_stopped": "Voice listening stopped",
            "background_listening_started": "Background listening started - waiting for wake words...",
            "background_listening_stopped": "Background listening stopped",
            "voice_thread_stopped": "Voice thread stopped",
            "microphone_initialized": "Microphone initialized successfully. Energy threshold: {threshold}",
            "voice_recognition_initialized": "Voice recognition initialized with {device}",
            "tts_initialized": "TTS initialized with {voice}",
            "duplicate_ignored": "Ignoring duplicate command within 2 seconds"
        }
    
    def get_error_response(self, error_type: str) -> str:
        """Get an error response by type."""
        return self.error_responses.get(error_type, "An error occurred.")
    
    def get_interactive_prompt(self, prompt_type: str) -> str:
        """Get an interactive prompt by type."""
        return self.interactive_prompts.get(prompt_type, "Please provide more information.")
    
    def get_wake_response(self, response_type: str) -> str:
        """Get a wake response by type."""
        return self.wake_responses.get(response_type, "Hello! How can I help you?")
    
    def get_help_message(self, message_type: str) -> str:
        """Get a help message by type."""
        return self.help_messages.get(message_type, "Help is available.")
    
    def get_debug_message(self, message_type: str, **kwargs) -> str:
        """Get a debug message by type with optional formatting."""
        message = self.debug_messages.get(message_type, "Debug: {message}")
        return message.format(**kwargs)
    
    def get_status_message(self, message_type: str, **kwargs) -> str:
        """Get a status message by type with optional formatting."""
        message = self.status_messages.get(message_type, "Status: {message}")
        return message.format(**kwargs)
    
    def add_error_response(self, error_type: str, message: str):
        """Add a new error response."""
        self.error_responses[error_type] = message
    
    def add_interactive_prompt(self, prompt_type: str, message: str):
        """Add a new interactive prompt."""
        self.interactive_prompts[prompt_type] = message
    
    def add_wake_response(self, response_type: str, message: str):
        """Add a new wake response."""
        self.wake_responses[response_type] = message
    
    def add_help_message(self, message_type: str, message: str):
        """Add a new help message."""
        self.help_messages[message_type] = message
    
    def add_debug_message(self, message_type: str, message: str):
        """Add a new debug message."""
        self.debug_messages[message_type] = message
    
    def add_status_message(self, message_type: str, message: str):
        """Add a new status message."""
        self.status_messages[message_type] = message
    
    def get_all_responses(self) -> Dict[str, Dict[str, str]]:
        """Get all responses organized by category."""
        return {
            "error_responses": self.error_responses,
            "interactive_prompts": self.interactive_prompts,
            "wake_responses": self.wake_responses,
            "help_messages": self.help_messages,
            "debug_messages": self.debug_messages,
            "status_messages": self.status_messages
        }


# Global instance
response_manager = ResponseManager()
