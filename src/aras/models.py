"""
Data models for Aras Agent.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field


class MessageType(str, Enum):
    """Message types for WebSocket communication."""
    USER_INPUT = "user_input"
    AGENT_RESPONSE = "agent_response"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    STATE_UPDATE = "state_update"
    UI_COMMAND = "ui_command"
    ERROR = "error"


class ToolCategory(str, Enum):
    """Tool categories."""
    SYSTEM = "system"
    WEB = "web"
    HOME = "home"
    COMMUNICATION = "communication"
    KNOWLEDGE = "knowledge"
    VOICE_VISION = "voice_vision"
    SAFETY = "safety"


class Message(BaseModel):
    """Base message model."""
    id: str = Field(..., description="Unique message ID")
    type: MessageType = Field(..., description="Message type")
    timestamp: datetime = Field(default_factory=datetime.now)
    content: str = Field(..., description="Message content")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class UserInput(Message):
    """User input message."""
    type: MessageType = MessageType.USER_INPUT
    input_type: str = Field(..., description="Type of input (voice, text, etc.)")
    session_id: str = Field(..., description="User session ID")


class AgentResponse(Message):
    """Agent response message."""
    type: MessageType = MessageType.AGENT_RESPONSE
    session_id: str = Field(..., description="User session ID")
    tool_calls: List[Dict[str, Any]] = Field(default_factory=list, description="Tool calls made")
    confidence: float = Field(default=1.0, description="Response confidence score")


class ToolCall(BaseModel):
    """Tool call model."""
    id: str = Field(..., description="Unique tool call ID")
    tool_name: str = Field(..., description="Name of the tool to call")
    category: ToolCategory = Field(..., description="Tool category")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Tool parameters")
    session_id: str = Field(..., description="User session ID")
    timestamp: datetime = Field(default_factory=datetime.now)


class ToolResult(BaseModel):
    """Tool execution result."""
    call_id: str = Field(..., description="ID of the tool call")
    success: bool = Field(..., description="Whether the tool call succeeded")
    result: Any = Field(..., description="Tool execution result")
    error: Optional[str] = Field(None, description="Error message if failed")
    execution_time: float = Field(..., description="Execution time in seconds")
    timestamp: datetime = Field(default_factory=datetime.now)


class StateUpdate(BaseModel):
    """State update message."""
    type: MessageType = MessageType.STATE_UPDATE
    component: str = Field(..., description="Component that updated")
    state: Dict[str, Any] = Field(..., description="New state data")
    timestamp: datetime = Field(default_factory=datetime.now)


class UICommand(BaseModel):
    """UI command message."""
    type: MessageType = MessageType.UI_COMMAND
    command: str = Field(..., description="UI command to execute")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Command parameters")
    session_id: str = Field(..., description="User session ID")
    timestamp: datetime = Field(default_factory=datetime.now)


class ErrorMessage(Message):
    """Error message."""
    type: MessageType = MessageType.ERROR
    error_code: str = Field(..., description="Error code")
    error_details: Dict[str, Any] = Field(default_factory=dict, description="Error details")


class AgentState(BaseModel):
    """Agent state model."""
    is_active: bool = Field(default=False, description="Whether agent is active")
    current_session: Optional[str] = Field(None, description="Current active session")
    last_activity: datetime = Field(default_factory=datetime.now)
    active_tools: List[str] = Field(default_factory=list, description="Currently active tools")
    system_status: Dict[str, Any] = Field(default_factory=dict, description="System status")


class ToolDefinition(BaseModel):
    """Tool definition model."""
    name: str = Field(..., description="Tool name")
    category: ToolCategory = Field(..., description="Tool category")
    description: str = Field(..., description="Tool description")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Tool parameters schema")
    enabled: bool = Field(default=True, description="Whether tool is enabled")
    requires_auth: bool = Field(default=False, description="Whether tool requires authentication")
