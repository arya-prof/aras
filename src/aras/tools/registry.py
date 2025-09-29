"""
Tool registry for managing all available tools.
"""

from .base import ToolRegistry
from .system_tools import FileOperationsTool, ProcessManagementTool, SystemControlTool
from .file_tools import FileCreateRemoveTool
from .web_tools import WebSearchTool, BrowserAutomationTool, APITool
from .home_tools import DeviceControlTool, SceneManagementTool, ClimateControlTool
from .mock_pi_tool import MockPiControlTool
from .communication_tools import EmailTool, NotificationTool
from .telegram_tools import TelegramTool
from .knowledge_tools import MemoryOperationsTool, VectorSearchTool
from .voice_vision_tools import SpeechProcessingTool, ImageProcessingTool, CameraControlTool
from .safety_tools import PermissionCheckTool, AccessControlTool, AuditLoggingTool
from .arduino_bluetooth_tool import ArduinoBluetoothTool


def create_tool_registry() -> ToolRegistry:
    """Create and populate the tool registry."""
    registry = ToolRegistry()
    
    # System tools
    registry.register_tool(FileOperationsTool())
    registry.register_tool(FileCreateRemoveTool())
    registry.register_tool(ProcessManagementTool())
    registry.register_tool(SystemControlTool())
    
    # Web tools
    registry.register_tool(WebSearchTool())
    registry.register_tool(BrowserAutomationTool())
    registry.register_tool(APITool())
    
    # Home tools
    registry.register_tool(DeviceControlTool())
    registry.register_tool(SceneManagementTool())
    registry.register_tool(ClimateControlTool())
    registry.register_tool(MockPiControlTool())
    
    # Communication tools
    registry.register_tool(EmailTool())
    registry.register_tool(NotificationTool())
    registry.register_tool(TelegramTool())
    
    # Knowledge tools
    registry.register_tool(MemoryOperationsTool())
    registry.register_tool(VectorSearchTool())
    
    # Voice/Vision tools
    registry.register_tool(SpeechProcessingTool())
    registry.register_tool(ImageProcessingTool())
    registry.register_tool(CameraControlTool())
    
    # Safety tools
    registry.register_tool(PermissionCheckTool())
    registry.register_tool(AccessControlTool())
    registry.register_tool(AuditLoggingTool())
    
    # Arduino Bluetooth control
    registry.register_tool(ArduinoBluetoothTool())
    
    return registry
