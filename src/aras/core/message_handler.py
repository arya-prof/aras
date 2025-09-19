"""
Message handling and routing.
"""

import asyncio
import json
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from loguru import logger

from ..models import Message, MessageType, UserInput, AgentResponse, ToolCall, ToolResult, StateUpdate, UICommand, ErrorMessage


class MessageHandler:
    """Handles message routing and processing."""
    
    def __init__(self):
        self.subscribers: Dict[MessageType, List[callable]] = {}
        self.message_queue: asyncio.Queue = asyncio.Queue()
        self.processing = False
    
    def subscribe(self, message_type: MessageType, handler: callable):
        """Subscribe to a message type."""
        if message_type not in self.subscribers:
            self.subscribers[message_type] = []
        self.subscribers[message_type].append(handler)
        logger.debug(f"Subscribed handler to {message_type}")
    
    def unsubscribe(self, message_type: MessageType, handler: callable):
        """Unsubscribe from a message type."""
        if message_type in self.subscribers:
            try:
                self.subscribers[message_type].remove(handler)
                logger.debug(f"Unsubscribed handler from {message_type}")
            except ValueError:
                logger.warning(f"Handler not found for {message_type}")
    
    async def publish(self, message: Message):
        """Publish a message to subscribers."""
        try:
            # Add to queue for processing
            await self.message_queue.put(message)
            
            # Notify subscribers
            if message.type in self.subscribers:
                for handler in self.subscribers[message.type]:
                    try:
                        if asyncio.iscoroutinefunction(handler):
                            await handler(message)
                        else:
                            handler(message)
                    except Exception as e:
                        logger.error(f"Error in message handler: {e}")
            
            logger.debug(f"Published {message.type} message: {message.id}")
            
        except Exception as e:
            logger.error(f"Error publishing message: {e}")
    
    async def start_processing(self):
        """Start message processing loop."""
        if self.processing:
            return
        
        self.processing = True
        logger.info("Started message processing")
        
        while self.processing:
            try:
                # Wait for message with timeout
                message = await asyncio.wait_for(
                    self.message_queue.get(), 
                    timeout=1.0
                )
                
                # Process message
                await self._process_message(message)
                
            except asyncio.TimeoutError:
                # No message, continue
                continue
            except Exception as e:
                logger.error(f"Error processing message: {e}")
    
    async def stop_processing(self):
        """Stop message processing."""
        self.processing = False
        logger.info("Stopped message processing")
    
    async def _process_message(self, message: Message):
        """Process a single message."""
        try:
            logger.debug(f"Processing {message.type} message: {message.id}")
            
            # Add any message-specific processing here
            if message.type == MessageType.USER_INPUT:
                await self._handle_user_input(message)
            elif message.type == MessageType.TOOL_CALL:
                await self._handle_tool_call(message)
            elif message.type == MessageType.TOOL_RESULT:
                await self._handle_tool_result(message)
            elif message.type == MessageType.STATE_UPDATE:
                await self._handle_state_update(message)
            elif message.type == MessageType.UI_COMMAND:
                await self._handle_ui_command(message)
            elif message.type == MessageType.ERROR:
                await self._handle_error(message)
            
        except Exception as e:
            logger.error(f"Error processing {message.type} message: {e}")
    
    async def _handle_user_input(self, message: UserInput):
        """Handle user input message."""
        logger.info(f"User input: {message.content[:100]}...")
        # Additional processing can be added here
    
    async def _handle_tool_call(self, message: Message):
        """Handle tool call message."""
        logger.info(f"Tool call: {message.content}")
        # Additional processing can be added here
    
    async def _handle_tool_result(self, message: Message):
        """Handle tool result message."""
        logger.info(f"Tool result: {message.content}")
        # Additional processing can be added here
    
    async def _handle_state_update(self, message: StateUpdate):
        """Handle state update message."""
        logger.debug(f"State update: {message.component}")
        # Additional processing can be added here
    
    async def _handle_ui_command(self, message: UICommand):
        """Handle UI command message."""
        logger.info(f"UI command: {message.command}")
        # Additional processing can be added here
    
    async def _handle_error(self, message: ErrorMessage):
        """Handle error message."""
        logger.error(f"Error: {message.content}")
        # Additional processing can be added here
    
    def create_user_input(self, content: str, input_type: str = "text", session_id: Optional[str] = None) -> UserInput:
        """Create a user input message."""
        return UserInput(
            id=str(uuid.uuid4()),
            content=content,
            input_type=input_type,
            session_id=session_id or str(uuid.uuid4())
        )
    
    def create_agent_response(self, content: str, session_id: str, tool_calls: List[Dict[str, Any]] = None) -> AgentResponse:
        """Create an agent response message."""
        return AgentResponse(
            id=str(uuid.uuid4()),
            content=content,
            session_id=session_id,
            tool_calls=tool_calls or []
        )
    
    def create_tool_call(self, tool_name: str, parameters: Dict[str, Any], session_id: str) -> ToolCall:
        """Create a tool call message."""
        return ToolCall(
            id=str(uuid.uuid4()),
            tool_name=tool_name,
            parameters=parameters,
            session_id=session_id
        )
    
    def create_tool_result(self, call_id: str, success: bool, result: Any, error: Optional[str] = None) -> ToolResult:
        """Create a tool result message."""
        return ToolResult(
            call_id=call_id,
            success=success,
            result=result,
            error=error
        )
    
    def create_state_update(self, component: str, state: Dict[str, Any]) -> StateUpdate:
        """Create a state update message."""
        return StateUpdate(
            id=str(uuid.uuid4()),
            component=component,
            state=state
        )
    
    def create_ui_command(self, command: str, parameters: Dict[str, Any], session_id: str) -> UICommand:
        """Create a UI command message."""
        return UICommand(
            id=str(uuid.uuid4()),
            command=command,
            parameters=parameters,
            session_id=session_id
        )
    
    def create_error(self, error_code: str, content: str, details: Dict[str, Any] = None) -> ErrorMessage:
        """Create an error message."""
        return ErrorMessage(
            id=str(uuid.uuid4()),
            error_code=error_code,
            content=content,
            error_details=details or {}
        )
