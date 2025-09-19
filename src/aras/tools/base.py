"""
Base tool classes and interfaces.
"""

import asyncio
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from datetime import datetime

from ..models import ToolCategory, ToolDefinition


class BaseTool(ABC):
    """Base class for all tools."""
    
    def __init__(self, name: str, category: ToolCategory, description: str):
        self.name = name
        self.category = category
        self.description = description
        self.enabled = True
        self.requires_auth = False
        self.last_used = None
        self.usage_count = 0
    
    @abstractmethod
    async def execute(self, parameters: Dict[str, Any]) -> Any:
        """Execute the tool with given parameters."""
        pass
    
    @abstractmethod
    def get_parameters_schema(self) -> Dict[str, Any]:
        """Get the parameters schema for this tool."""
        pass
    
    def get_definition(self) -> ToolDefinition:
        """Get tool definition."""
        return ToolDefinition(
            name=self.name,
            category=self.category,
            description=self.description,
            parameters=self.get_parameters_schema(),
            enabled=self.enabled,
            requires_auth=self.requires_auth
        )
    
    def _record_usage(self):
        """Record tool usage."""
        self.last_used = datetime.now()
        self.usage_count += 1
    
    def is_available(self) -> bool:
        """Check if tool is available."""
        return self.enabled
    
    def enable(self):
        """Enable the tool."""
        self.enabled = True
    
    def disable(self):
        """Disable the tool."""
        self.enabled = False


class AsyncTool(BaseTool):
    """Base class for async tools."""
    
    async def execute(self, parameters: Dict[str, Any]) -> Any:
        """Execute the tool asynchronously."""
        self._record_usage()
        return await self._execute_async(parameters)
    
    @abstractmethod
    async def _execute_async(self, parameters: Dict[str, Any]) -> Any:
        """Async execution implementation."""
        pass


class SyncTool(BaseTool):
    """Base class for synchronous tools."""
    
    async def execute(self, parameters: Dict[str, Any]) -> Any:
        """Execute the tool synchronously in a thread pool."""
        self._record_usage()
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._execute_sync, parameters)
    
    @abstractmethod
    def _execute_sync(self, parameters: Dict[str, Any]) -> Any:
        """Sync execution implementation."""
        pass


class ToolRegistry:
    """Registry for managing tools."""
    
    def __init__(self):
        self.tools: Dict[str, BaseTool] = {}
        self.categories: Dict[ToolCategory, List[str]] = {
            category: [] for category in ToolCategory
        }
    
    def register_tool(self, tool: BaseTool):
        """Register a tool."""
        self.tools[tool.name] = tool
        self.categories[tool.category].append(tool.name)
    
    def unregister_tool(self, tool_name: str):
        """Unregister a tool."""
        if tool_name in self.tools:
            tool = self.tools[tool_name]
            self.categories[tool.category].remove(tool_name)
            del self.tools[tool_name]
    
    def get_tool(self, tool_name: str) -> Optional[BaseTool]:
        """Get a tool by name."""
        return self.tools.get(tool_name)
    
    def get_tools_by_category(self, category: ToolCategory) -> List[BaseTool]:
        """Get all tools in a category."""
        return [self.tools[name] for name in self.categories[category] if name in self.tools]
    
    def get_all_tools(self) -> List[BaseTool]:
        """Get all registered tools."""
        return list(self.tools.values())
    
    def get_enabled_tools(self) -> List[BaseTool]:
        """Get all enabled tools."""
        return [tool for tool in self.tools.values() if tool.enabled]
    
    def get_tool_definitions(self) -> List[ToolDefinition]:
        """Get all tool definitions."""
        return [tool.get_definition() for tool in self.tools.values()]
    
    def get_tools_for_langchain(self) -> List[Any]:
        """Get tools formatted for LangChain."""
        # This would need to be implemented based on LangChain's tool format
        # For now, return empty list
        return []
