"""
Example usage of the centralized prompt system.
"""

from aras.prompts import prompt_manager


def example_usage():
    """Demonstrate how to use the centralized prompt system."""
    
    # Get basic prompts
    print("=== Basic Voice Prompt ===")
    voice_prompt = prompt_manager.get_voice_prompt()
    print(voice_prompt)
    print()
    
    # Get text chat prompt with tools
    print("=== Text Chat Prompt with Tools ===")
    tools_description = """
- file_manager: Manage files and directories
- web_search: Search the web for information
- telegram_manager: Send messages via Telegram
"""
    text_prompt = prompt_manager.get_text_chat_prompt(tools_description)
    print(text_prompt)
    print()
    
    # Get custom prompt
    print("=== Custom Prompt ===")
    custom_prompt = prompt_manager.get_custom_prompt(
        "debugging session",
        "Focus on providing detailed technical explanations and debugging steps."
    )
    print(custom_prompt)
    print()
    
    # Add new capability
    print("=== Adding New Capability ===")
    prompt_manager.add_capability("Database management and SQL queries")
    updated_prompt = prompt_manager.get_voice_prompt()
    print("Updated prompt with new capability:")
    print(updated_prompt)
    print()
    
    # Add new response guideline
    print("=== Adding New Response Guideline ===")
    prompt_manager.add_response_guideline("Always provide code examples when explaining technical concepts")
    updated_prompt = prompt_manager.get_voice_prompt()
    print("Updated prompt with new guideline:")
    print(updated_prompt)


if __name__ == "__main__":
    example_usage()
