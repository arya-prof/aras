#!/usr/bin/env python3
"""
Simple test script for Aras Agent (without ChromaDB initialization).
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path("src")))

def test_basic_imports():
    """Test basic imports without initializing heavy components."""
    print("Testing basic imports...")
    
    try:
        from aras.config import settings
        print("✓ Configuration module imported")
        print(f"  Agent name: {settings.agent_name}")
        print(f"  OpenAI model: {settings.openai_model}")
    except Exception as e:
        print(f"✗ Configuration import failed: {e}")
        return False
    
    try:
        from aras.models import MessageType, ToolCategory
        print("✓ Models module imported")
        print(f"  Message types: {len(list(MessageType))}")
        print(f"  Tool categories: {len(list(ToolCategory))}")
    except Exception as e:
        print(f"✗ Models import failed: {e}")
        return False
    
    try:
        from aras.core.state_manager import StateManager
        print("✓ State manager imported")
    except Exception as e:
        print(f"✗ State manager import failed: {e}")
        return False
    
    try:
        from aras.core.message_handler import MessageHandler
        print("✓ Message handler imported")
    except Exception as e:
        print(f"✗ Message handler import failed: {e}")
        return False
    
    return True


def test_tool_imports():
    """Test tool imports without initialization."""
    print("\nTesting tool imports...")
    
    try:
        from aras.tools.system_tools import FileOperationsTool, ProcessManagementTool, SystemControlTool
        print("✓ System tools imported")
        
        # Test creating a tool instance
        file_tool = FileOperationsTool()
        print(f"  File operations tool: {file_tool.name}")
    except Exception as e:
        print(f"✗ System tools import failed: {e}")
        return False
    
    try:
        from aras.tools.web_tools import WebSearchTool, BrowserAutomationTool, APITool
        print("✓ Web tools imported")
    except Exception as e:
        print(f"✗ Web tools import failed: {e}")
        return False
    
    try:
        from aras.tools.communication_tools import EmailTool, NotificationTool
        print("✓ Communication tools imported")
    except Exception as e:
        print(f"✗ Communication tools import failed: {e}")
        return False
    
    try:
        from aras.tools.safety_tools import PermissionCheckTool, AccessControlTool, AuditLoggingTool
        print("✓ Safety tools imported")
    except Exception as e:
        print(f"✗ Safety tools import failed: {e}")
        return False
    
    return True


def test_ui_imports():
    """Test UI imports."""
    print("\nTesting UI imports...")
    
    try:
        from aras.ui.main_window import MainWindow
        print("✓ Main window imported")
    except Exception as e:
        print(f"✗ Main window import failed: {e}")
        return False
    
    try:
        from aras.ui.app import ArasApp
        print("✓ UI app imported")
    except Exception as e:
        print(f"✗ UI app import failed: {e}")
        return False
    
    return True


def main():
    """Run all tests."""
    print("=" * 60)
    print("Aras Agent Simple Installation Test")
    print("=" * 60)
    
    success = True
    
    if not test_basic_imports():
        success = False
    
    if not test_tool_imports():
        success = False
    
    if not test_ui_imports():
        success = False
    
    print("\n" + "=" * 60)
    if success:
        print("✓ All basic tests passed! Aras Agent core is working.")
        print("\nNext steps:")
        print("1. Edit .env file with your API keys")
        print("2. Run: python run_aras.py")
        print("3. Or test the server: python start_server.py")
    else:
        print("✗ Some tests failed. Check the errors above.")
    print("=" * 60)
    
    return success


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
