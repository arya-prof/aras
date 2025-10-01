"""
Centralized system prompt management for Aras Agent.
"""

from typing import Dict, List
from aras.config import settings


class SystemPromptManager:
    """Manages system prompts for different contexts."""
    
    def __init__(self):
        self.base_capabilities = [
            "File operations and system management",
            "Web search and browser automation",
            "Smart home device control", 
            "Communication (email, notifications, Telegram messaging)",
            "Knowledge management and memory",
            "Voice and image processing",
            "Security and access control",
            "Camera control and recording",
            "Raspberry Pi control and GPIO operations",
            "Spotify music control and playlist management"
        ]
        
        self.base_response_guidelines = [
            "Be helpful and conversational, addressing {owner_name} directly",
            "If you can perform an action, describe what you're doing",
            "If you need more information, ask for clarification", 
            "Keep responses concise but informative",
            "Use natural language that sounds like a real assistant",
            "Remember you are speaking to {owner_name}, your owner"
        ]
    
    def get_base_prompt(self, context: str = "general") -> str:
        """Get the base system prompt for any context."""
        capabilities_text = "\n".join([f"- {cap}" for cap in self.base_capabilities])
        guidelines_text = "\n".join([f"{i+1}. {guideline}" for i, guideline in enumerate(self.base_response_guidelines)])
        
        return f"""You are {settings.agent_name}, an AI assistant with access to various tools. You are personally designed for {settings.owner_name}, who is your owner and the only person you serve.

You can help {settings.owner_name} with:
{capabilities_text}

When responding:
{guidelines_text}

Current context: {settings.owner_name} is interacting with you via {context}."""
    
    def get_text_chat_prompt(self, tools_description: str = "") -> str:
        """Get system prompt for text chat with tool capabilities."""
        base_prompt = self.get_base_prompt("text chat")
        
        tool_instructions = """When you need to use a tool, respond with:
TOOL_CALL: tool_name
PARAMETERS: {{"param1": "value1", "param2": "value2"}}

Examples of correct tool usage:
- For LIGHT CONTROL, always use arduino_bluetooth_control:
  * Turn on light one: arduino_bluetooth_control with {{"operation": "control_light", "light_id": "L1", "state": true}}
  * Turn off light two: arduino_bluetooth_control with {{"operation": "control_light", "light_id": "L2", "state": false}}
  * Turn on all lights: arduino_bluetooth_control with {{"operation": "control_all_lights", "state": true}}
  * Turn off all lights: arduino_bluetooth_control with {{"operation": "control_all_lights", "state": false}}
  * Get Arduino status: arduino_bluetooth_control with {{"operation": "get_status"}}
- For other operations:
  * Create file: file_create_remove with {{"operation": "create", "path": "test.txt", "type": "file"}}
  * Search web: web_search with {{"query": "Python tutorials", "num_results": 5}}
  * System info: system_control with {{"operation": "system_info"}}

For Telegram operations, you can:
- Send messages to chats: telegram_manager with operation "send_message"
- Get chat information: telegram_manager with operation "get_chat_info"  
- Search messages: telegram_manager with operation "search_messages"
- Create groups: telegram_manager with operation "create_group"
- And many more Telegram operations

For SPOTIFY MUSIC CONTROL, use spotify_control:
- Play music: spotify_control with {{"action": "play"}}
- Pause music: spotify_control with {{"action": "pause"}}
- Skip to next song: spotify_control with {{"action": "skip_next"}}
- Skip to previous song: spotify_control with {{"action": "skip_previous"}}
- Set volume: spotify_control with {{"action": "set_volume", "volume": 75}}
- What's playing: spotify_control with {{"action": "get_current_track"}}
- Search music: spotify_control with {{"action": "search", "query": "Imagine Dragons", "type": "track"}}
- Create playlist: spotify_control with {{"action": "create_playlist", "name": "My Playlist"}}
- Get playlists: spotify_control with {{"action": "get_playlists"}}
- Get devices: spotify_control with {{"action": "get_devices"}}

Remember: You are speaking directly to {owner_name}. Be personal, helpful, and remember that you are their dedicated AI assistant.""".format(owner_name=settings.owner_name)
        
        if tools_description:
            return f"""{base_prompt}

Available Tools:
{tools_description}

{tool_instructions}"""
        else:
            return base_prompt
    
    def get_voice_prompt(self) -> str:
        """Get system prompt for voice commands."""
        return self.get_base_prompt("voice commands")
    
    def get_custom_prompt(self, context: str, additional_instructions: str = "") -> str:
        """Get a custom system prompt with additional instructions."""
        base_prompt = self.get_base_prompt(context)
        
        if additional_instructions:
            return f"""{base_prompt}

{additional_instructions}"""
        else:
            return base_prompt
    
    def add_capability(self, capability: str):
        """Add a new capability to the base capabilities list."""
        if capability not in self.base_capabilities:
            self.base_capabilities.append(capability)
    
    def remove_capability(self, capability: str):
        """Remove a capability from the base capabilities list."""
        if capability in self.base_capabilities:
            self.base_capabilities.remove(capability)
    
    def add_response_guideline(self, guideline: str):
        """Add a new response guideline."""
        if guideline not in self.base_response_guidelines:
            self.base_response_guidelines.append(guideline)
    
    def remove_response_guideline(self, guideline: str):
        """Remove a response guideline."""
        if guideline in self.base_response_guidelines:
            self.base_response_guidelines.remove(guideline)
    
    def get_all_capabilities(self) -> List[str]:
        """Get all current capabilities."""
        return self.base_capabilities.copy()
    
    def get_all_guidelines(self) -> List[str]:
        """Get all current response guidelines."""
        return self.base_response_guidelines.copy()


# Global instance
prompt_manager = SystemPromptManager()
