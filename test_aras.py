#!/usr/bin/env python3
"""
Test script for Aras Agent.
"""

import sys
import asyncio
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from aras.config import settings
from aras.tools.registry import create_tool_registry
from aras.core.agent import ArasAgent


async def test_tools():
    """Test the tool system."""
    print("Testing Aras Agent Tools...")
    
    # Create tool registry
    registry = create_tool_registry()
    
    print(f"Registered {len(registry.get_all_tools())} tools:")
    for tool in registry.get_all_tools():
        print(f"  - {tool.name} ({tool.category.value})")
    
    # Test a simple tool
    file_tool = registry.get_tool("file_operations")
    if file_tool:
        print(f"\nTesting {file_tool.name}...")
        try:
            result = await file_tool.execute({
                "operation": "list",
                "path": "."
            })
            print(f"Result: {result}")
        except Exception as e:
            print(f"Error: {e}")
    
    print("\nTool test completed!")


async def test_agent():
    """Test the agent."""
    print("\nTesting Aras Agent...")
    
    try:
        agent = ArasAgent()
        print(f"Agent created: {agent.agent_id}")
        
        # Test user input
        user_input = {
            "id": "test-1",
            "content": "Hello, can you help me?",
            "input_type": "text",
            "session_id": "test-session"
        }
        
        from aras.models import UserInput
        message = UserInput(**user_input)
        
        response = await agent.process_message(message)
        print(f"Agent response: {response}")
        
    except Exception as e:
        print(f"Agent test error: {e}")
    
    print("Agent test completed!")


def test_config():
    """Test configuration."""
    print("Testing Configuration...")
    print(f"Agent Name: {settings.agent_name}")
    print(f"WebSocket Port: {settings.websocket_port}")
    print(f"HTTP Port: {settings.http_port}")
    print(f"OpenAI Model: {settings.openai_model}")
    print(f"Use Ollama: {settings.use_ollama}")
    print("Configuration test completed!")


async def main():
    """Run all tests."""
    print("=" * 50)
    print("Aras Agent Test Suite")
    print("=" * 50)
    
    test_config()
    await test_tools()
    await test_agent()
    
    print("\n" + "=" * 50)
    print("All tests completed!")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
