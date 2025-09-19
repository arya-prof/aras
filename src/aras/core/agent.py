"""
Main agent orchestrator.
"""

import asyncio
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain.memory import ConversationBufferWindowMemory
from langchain.schema import BaseMessage, HumanMessage, AIMessage
from langchain_openai import ChatOpenAI
from langchain_community.llms import Ollama

from ..config import settings
from ..models import AgentState, Message, MessageType, ToolCall, ToolResult, UserInput
from ..tools.registry import create_tool_registry
from .state_manager import StateManager
from .message_handler import MessageHandler


class ArasAgent:
    """Main Aras agent orchestrator."""
    
    def __init__(self):
        self.agent_id = str(uuid.uuid4())
        self.state_manager = StateManager()
        self.message_handler = MessageHandler()
        self.tool_registry = create_tool_registry()
        self.llm = self._initialize_llm()
        self.memory = ConversationBufferWindowMemory(
            k=10,  # Keep last 10 exchanges
            return_messages=True
        )
        self.agent_executor = self._create_agent_executor()
        self.state = AgentState()
        
    def _initialize_llm(self):
        """Initialize the language model."""
        if settings.use_ollama:
            return Ollama(
                base_url=settings.ollama_base_url,
                model=settings.ollama_model
            )
        else:
            return ChatOpenAI(
                api_key=settings.openai_api_key,
                model=settings.openai_model,
                temperature=0.7
            )
    
    def _create_agent_executor(self) -> None:
        """Create a simple agent executor (placeholder for now)."""
        # For now, we'll handle responses directly in process_message
        # This avoids LangChain complexity during initial setup
        pass
    
    def _create_prompt(self):
        """Create the agent prompt."""
        # This method is now handled in _create_agent_executor
        pass
    
    async def process_message(self, message: UserInput) -> str:
        """Process a user message and return response."""
        try:
            self.state.is_active = True
            self.state.current_session = message.session_id
            self.state.last_activity = datetime.now()
            
            # Add to memory
            self.memory.chat_memory.add_user_message(message.content)
            
            # Simple response using LLM directly
            prompt = f"""You are {settings.agent_name}, an AI assistant.

You can help with:
- File operations and system management
- Web search and browser automation
- Smart home device control
- Communication (email, notifications)
- Knowledge management and memory
- Voice and image processing
- Security and access control

Human: {message.content}
Assistant:"""
            
            response = await self.llm.ainvoke(prompt)
            response_text = response.content if hasattr(response, 'content') else str(response)
            
            # Add to memory
            self.memory.chat_memory.add_ai_message(response_text)
            
            # Update state
            self.state_manager.update_state("agent", {
                "last_response": response_text,
                "last_input": message.content,
                "response_time": datetime.now()
            })
            
            return response_text
            
        except Exception as e:
            error_msg = f"Error processing message: {str(e)}"
            self.state_manager.log_error("agent", error_msg)
            return error_msg
        finally:
            self.state.is_active = False
    
    async def execute_tool(self, tool_call: ToolCall) -> ToolResult:
        """Execute a tool call."""
        start_time = datetime.now()
        
        try:
            tool = self.tool_registry.get_tool(tool_call.tool_name)
            if not tool:
                return ToolResult(
                    call_id=tool_call.id,
                    success=False,
                    result=None,
                    error=f"Tool '{tool_call.tool_name}' not found",
                    execution_time=0.0
                )
            
            # Execute tool
            result = await tool.execute(tool_call.parameters)
            
            execution_time = (datetime.now() - start_time).total_seconds()
            
            return ToolResult(
                call_id=tool_call.id,
                success=True,
                result=result,
                execution_time=execution_time
            )
            
        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            return ToolResult(
                call_id=tool_call.id,
                success=False,
                result=None,
                error=str(e),
                execution_time=execution_time
            )
    
    def get_state(self) -> AgentState:
        """Get current agent state."""
        return self.state
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get system status."""
        return {
            "agent_id": self.agent_id,
            "agent_name": settings.agent_name,
            "is_active": self.state.is_active,
            "current_session": self.state.current_session,
            "last_activity": self.state.last_activity,
            "active_tools": self.state.active_tools,
            "tool_count": len(self.tool_registry.get_all_tools()),
            "memory_size": len(self.memory.chat_memory.messages)
        }
    
    async def shutdown(self):
        """Shutdown the agent."""
        self.state.is_active = False
        self.state.current_session = None
        self.state_manager.cleanup()
