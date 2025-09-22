"""
Main agent orchestrator.
"""

import asyncio
import json
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
        self._initialized = False
        
    def _initialize_llm(self):
        """Initialize the language model."""
        if settings.use_ollama:
            return Ollama(
                base_url=settings.ollama_base_url,
                model=settings.ollama_model
            )
        elif settings.use_openrouter:
            return ChatOpenAI(
                api_key=settings.openrouter_api_key,
                base_url=settings.openrouter_base_url,
                model=settings.openai_model,  # Use the model name from settings
                temperature=0.7
            )
        else:
            return ChatOpenAI(
                api_key=settings.openai_api_key,
                model=settings.openai_model,
                temperature=0.7
            )
    
    async def initialize(self) -> bool:
        """Initialize the agent and all tools."""
        if self._initialized:
            return True
        
        try:
            # Initialize all tools
            tool_results = await self.tool_registry.initialize_all_tools()
            
            # Log tool initialization results
            for tool_name, success in tool_results.items():
                if not success:
                    print(f"Warning: Tool {tool_name} failed to initialize")
            
            self._initialized = True
            print(f"Agent initialized with {len(self.tool_registry.get_all_tools())} tools")
            return True
        except Exception as e:
            print(f"Error initializing agent: {e}")
            return False
    
    def _create_agent_executor(self) -> None:
        """Create a simple agent executor (placeholder for now)."""
        # For now, we'll handle responses directly in process_message
        # This avoids LangChain complexity during initial setup
        pass
    
    def _create_prompt(self):
        """Create the agent prompt."""
        # This method is now handled in _create_agent_executor
        pass
    
    def _get_available_tools(self) -> List[Dict[str, Any]]:
        """Get list of available tools with their descriptions."""
        tools = []
        for tool in self.tool_registry.get_healthy_tools():
            if tool.enabled:
                tools.append({
                    "name": tool.name,
                    "description": tool.description,
                    "category": tool.category.value,
                    "parameters": tool.get_parameters_schema()
                })
        return tools
    
    def _format_tools_description(self, tools: List[Dict[str, Any]]) -> str:
        """Format tools description for the LLM prompt."""
        if not tools:
            return "No tools available."
        
        description = ""
        for tool in tools:
            description += f"\n- {tool['name']}: {tool['description']}"
            if tool['name'] == 'telegram_manager':
                description += "\n  Operations: send_message, get_chats, get_chat_info, get_messages, search_messages, create_group, add_users_to_group, remove_users_from_group, get_me, forward_message, delete_message, edit_message"
        
        return description
    
    async def _process_tool_calls(self, response_text: str, session_id: str) -> str:
        """Process tool calls in the response and execute them."""
        lines = response_text.split('\n')
        processed_response = []
        i = 0
        
        while i < len(lines):
            line = lines[i].strip()
            
            if line.startswith("TOOL_CALL:"):
                tool_name = line.replace("TOOL_CALL:", "").strip()
                
                # Look for parameters in the next line
                if i + 1 < len(lines) and lines[i + 1].strip().startswith("PARAMETERS:"):
                    params_line = lines[i + 1].strip().replace("PARAMETERS:", "").strip()
                    try:
                        parameters = json.loads(params_line)
                        
                        # Execute the tool
                        tool_call = ToolCall(
                            id=str(uuid.uuid4()),
                            tool_name=tool_name,
                            parameters=parameters,
                            session_id=session_id
                        )
                        
                        result = await self.execute_tool(tool_call)
                        
                        if result.success:
                            processed_response.append(f"✅ Executed {tool_name} successfully")
                            processed_response.append(f"Result: {str(result.result)}")
                        else:
                            processed_response.append(f"❌ Error executing {tool_name}: {result.error}")
                        
                        # Skip the parameters line
                        i += 2
                        continue
                        
                    except json.JSONDecodeError as e:
                        processed_response.append(f"❌ Invalid parameters for {tool_name}: {e}")
                        i += 2
                        continue
                else:
                    processed_response.append(f"❌ No parameters found for {tool_name}")
            
            processed_response.append(line)
            i += 1
        
        return '\n'.join(processed_response)
    
    async def process_message(self, message: UserInput) -> str:
        """Process a user message and return response."""
        try:
            # Ensure agent is initialized
            if not self._initialized:
                await self.initialize()
            
            self.state.is_active = True
            self.state.current_session = message.session_id
            self.state.last_activity = datetime.now()
            
            # Add to memory
            self.memory.chat_memory.add_user_message(message.content)
            
            # Get available tools for the LLM
            available_tools = self._get_available_tools()
            tools_description = self._format_tools_description(available_tools)
            
            # Enhanced prompt with tool capabilities
            prompt = f"""You are {settings.agent_name}, an AI assistant with access to various tools.

You can help with:
- File operations and system management
- Web search and browser automation  
- Smart home device control
- Communication (email, notifications, Telegram messaging)
- Knowledge management and memory
- Voice and image processing
- Security and access control

Available Tools:
{tools_description}

When you need to use a tool, respond with:
TOOL_CALL: tool_name
PARAMETERS: {{"param1": "value1", "param2": "value2"}}

For Telegram operations, you can:
- Send messages to chats: telegram_manager with operation "send_message"
- Get chat information: telegram_manager with operation "get_chat_info"  
- Search messages: telegram_manager with operation "search_messages"
- Create groups: telegram_manager with operation "create_group"
- And many more Telegram operations

Human: {message.content}
Assistant:"""
            
            response = await self.llm.ainvoke(prompt)
            response_text = response.content if hasattr(response, 'content') else str(response)
            
            # Check if the response contains tool calls
            if "TOOL_CALL:" in response_text:
                response_text = await self._process_tool_calls(response_text, message.session_id)
            
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
            "healthy_tools": len(self.tool_registry.get_healthy_tools()),
            "unhealthy_tools": len(self.tool_registry.get_unhealthy_tools()),
            "memory_size": len(self.memory.chat_memory.messages),
            "initialized": self._initialized
        }
    
    def get_tool_health_status(self) -> Dict[str, Dict[str, Any]]:
        """Get health status of all tools."""
        return self.tool_registry.get_tool_health_status()
    
    async def restart_unhealthy_tools(self) -> Dict[str, bool]:
        """Restart all unhealthy tools."""
        return await self.tool_registry.restart_unhealthy_tools()
    
    async def restart_tool(self, tool_name: str) -> bool:
        """Restart a specific tool."""
        return await self.tool_registry.restart_tool(tool_name)
    
    async def shutdown(self):
        """Shutdown the agent and cleanup all resources."""
        self.state.is_active = False
        self.state.current_session = None
        
        # Cleanup all tools
        await self.tool_registry.cleanup_all_tools()
        
        # Cleanup state manager
        self.state_manager.cleanup()
        
        self._initialized = False
        print("Agent shutdown complete")
