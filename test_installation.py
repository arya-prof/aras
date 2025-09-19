#!/usr/bin/env python3
"""
Test script to verify Aras Agent installation.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path("src")))

def test_imports():
    """Test if all required modules can be imported."""
    print("Testing imports...")
    
    try:
        from aras.config import settings
        print("✓ Configuration module imported")
    except Exception as e:
        print(f"✗ Configuration import failed: {e}")
        return False
    
    try:
        from aras.models import MessageType, ToolCategory
        print("✓ Models module imported")
    except Exception as e:
        print(f"✗ Models import failed: {e}")
        return False
    
    try:
        from aras.tools.registry import create_tool_registry
        print("✓ Tools registry imported")
    except Exception as e:
        print(f"✗ Tools registry import failed: {e}")
        return False
    
    try:
        from aras.core.agent import ArasAgent
        print("✓ Agent core imported")
    except Exception as e:
        print(f"✗ Agent core import failed: {e}")
        return False
    
    return True


def test_tool_registry():
    """Test tool registry creation."""
    print("\nTesting tool registry...")
    
    try:
        from aras.tools.registry import create_tool_registry
        registry = create_tool_registry()
        
        tools = registry.get_all_tools()
        print(f"✓ Created tool registry with {len(tools)} tools")
        
        for tool in tools:
            print(f"  - {tool.name} ({tool.category.value})")
        
        return True
    except Exception as e:
        print(f"✗ Tool registry test failed: {e}")
        return False


def test_configuration():
    """Test configuration loading."""
    print("\nTesting configuration...")
    
    try:
        from aras.config import settings
        
        print(f"✓ Agent name: {settings.agent_name}")
        print(f"✓ WebSocket port: {settings.websocket_port}")
        print(f"✓ HTTP port: {settings.http_port}")
        print(f"✓ OpenAI model: {settings.openai_model}")
        print(f"✓ Whisper model: {settings.whisper_model}")
        print(f"✓ TTS model: {settings.tts_model}")
        
        return True
    except Exception as e:
        print(f"✗ Configuration test failed: {e}")
        return False


def main():
    """Run all tests."""
    print("=" * 50)
    print("Aras Agent Installation Test")
    print("=" * 50)
    
    success = True
    
    if not test_imports():
        success = False
    
    if not test_configuration():
        success = False
    
    if not test_tool_registry():
        success = False
    
    print("\n" + "=" * 50)
    if success:
        print("✓ All tests passed! Aras Agent is ready to use.")
        print("\nNext steps:")
        print("1. Edit .env file with your API keys")
        print("2. Run: python run_aras.py")
    else:
        print("✗ Some tests failed. Check the errors above.")
    print("=" * 50)
    
    return success


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
