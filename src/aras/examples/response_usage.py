"""
Example usage of the centralized response system.
"""

from aras.responses import response_manager


def example_usage():
    """Demonstrate how to use the centralized response system."""
    
    # Get error responses
    print("=== Error Responses ===")
    print(f"AI Unavailable: {response_manager.get_error_response('ai_unavailable')}")
    print(f"Command Error: {response_manager.get_error_response('command_error')}")
    print(f"File Operation Unknown: {response_manager.get_error_response('file_operation_unknown')}")
    print()
    
    # Get interactive prompts
    print("=== Interactive Prompts ===")
    print(f"File Name Request: {response_manager.get_interactive_prompt('file_name_request')}")
    print(f"Folder Name Request: {response_manager.get_interactive_prompt('folder_name_request')}")
    print(f"File Delete Request: {response_manager.get_interactive_prompt('file_delete_request')}")
    print()
    
    # Get wake responses
    print("=== Wake Responses ===")
    print(f"Wake Word Detected: {response_manager.get_wake_response('wake_word_detected')}")
    print(f"Listening Started: {response_manager.get_wake_response('listening_started')}")
    print()
    
    # Get help messages
    print("=== Help Messages ===")
    print(f"Wake Words: {response_manager.get_help_message('wake_words')}")
    print(f"Command Suggestions: {response_manager.get_help_message('command_suggestions')}")
    print()
    
    # Get status messages with formatting
    print("=== Status Messages ===")
    print(f"Voice Listening Started: {response_manager.get_status_message('voice_listening_started')}")
    print(f"Microphone Initialized: {response_manager.get_status_message('microphone_initialized', threshold=300)}")
    print()
    
    # Get debug messages with formatting
    print("=== Debug Messages ===")
    print(f"Voice Processing Start: {response_manager.get_debug_message('voice_processing_start', text='hello world')}")
    print(f"Pattern Matched: {response_manager.get_debug_message('pattern_matched', pattern='home status')}")
    print()
    
    # Add custom responses
    print("=== Adding Custom Responses ===")
    response_manager.add_error_response('custom_error', 'This is a custom error message')
    response_manager.add_interactive_prompt('custom_prompt', 'This is a custom prompt')
    
    print(f"Custom Error: {response_manager.get_error_response('custom_error')}")
    print(f"Custom Prompt: {response_manager.get_interactive_prompt('custom_prompt')}")
    print()
    
    # Get all responses
    print("=== All Responses ===")
    all_responses = response_manager.get_all_responses()
    for category, responses in all_responses.items():
        print(f"{category}: {len(responses)} responses")
        for key, value in list(responses.items())[:2]:  # Show first 2 of each category
            print(f"  {key}: {value}")
        if len(responses) > 2:
            print(f"  ... and {len(responses) - 2} more")
        print()


if __name__ == "__main__":
    example_usage()
