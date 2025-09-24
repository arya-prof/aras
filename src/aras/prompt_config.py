"""
Configuration for system prompts - easily customizable settings.
"""

from aras.prompts import prompt_manager


def configure_default_prompts():
    """Configure the default prompt settings."""
    
    # Add any additional capabilities specific to your setup
    additional_capabilities = [
        # Add your custom capabilities here
        # "Custom capability 1",
        # "Custom capability 2",
    ]
    
    for capability in additional_capabilities:
        prompt_manager.add_capability(capability)
    
    # Add any additional response guidelines
    additional_guidelines = [
        # Add your custom guidelines here
        # "Always be polite and professional",
        # "Provide step-by-step instructions when possible",
    ]
    
    for guideline in additional_guidelines:
        prompt_manager.add_response_guideline(guideline)


def get_prompt_for_context(context: str, **kwargs) -> str:
    """Get a prompt for a specific context with optional parameters."""
    
    if context == "voice":
        return prompt_manager.get_voice_prompt()
    elif context == "text_chat":
        tools_description = kwargs.get("tools_description", "")
        return prompt_manager.get_text_chat_prompt(tools_description)
    elif context == "debugging":
        return prompt_manager.get_custom_prompt(
            "debugging session",
            "Focus on providing detailed technical explanations and debugging steps."
        )
    elif context == "creative":
        return prompt_manager.get_custom_prompt(
            "creative writing",
            "Be more creative and expressive in your responses. Use metaphors and analogies when helpful."
        )
    elif context == "technical":
        return prompt_manager.get_custom_prompt(
            "technical discussion",
            "Provide detailed technical explanations with code examples when relevant."
        )
    else:
        return prompt_manager.get_base_prompt(context)


# Initialize default configuration when module is imported
configure_default_prompts()
