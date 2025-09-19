"""
Base tool classes and interfaces.
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from datetime import datetime
from pathlib import Path
import tempfile
import shutil

from ..models import ToolCategory, ToolDefinition

logger = logging.getLogger(__name__)


class BaseTool(ABC):
    """Base class for all tools with lifecycle management."""
    
    def __init__(self, name: str, category: ToolCategory, description: str):
        self.name = name
        self.category = category
        self.description = description
        self.enabled = True
        self.requires_auth = False
        self.last_used = None
        self.usage_count = 0
        self._initialized = False
        self._resources = []  # Track resources for cleanup
        self._temp_dir = None
        self._health_status = "unknown"
        self._last_error = None
    
    async def initialize(self) -> bool:
        """Initialize tool resources."""
        if self._initialized:
            return True
        
        try:
            # Create temp directory for tool operations
            self._temp_dir = Path(tempfile.mkdtemp(prefix=f"{self.name}_"))
            self._resources.append(self._temp_dir)
            
            # Setup tool-specific resources
            await self._setup_resources()
            
            self._initialized = True
            self._health_status = "healthy"
            self._last_error = None
            logger.info(f"Tool {self.name} initialized successfully")
            return True
        except Exception as e:
            self._health_status = "unhealthy"
            self._last_error = str(e)
            logger.error(f"Failed to initialize tool {self.name}: {e}")
            await self.cleanup()
            raise RuntimeError(f"Failed to initialize {self.name}: {e}")
    
    async def cleanup(self):
        """Clean up tool resources."""
        try:
            # Cleanup tool-specific resources
            await self._cleanup_resources()
            
            # Cleanup tracked resources
            for resource in self._resources:
                try:
                    if hasattr(resource, 'close'):
                        if asyncio.iscoroutinefunction(resource.close):
                            await resource.close()
                        else:
                            resource.close()
                    elif hasattr(resource, 'cleanup'):
                        if asyncio.iscoroutinefunction(resource.cleanup):
                            await resource.cleanup()
                        else:
                            resource.cleanup()
                except Exception as e:
                    logger.warning(f"Error cleaning up resource in {self.name}: {e}")
            
            # Cleanup temp directory
            if self._temp_dir and self._temp_dir.exists():
                try:
                    shutil.rmtree(self._temp_dir)
                except Exception as e:
                    logger.warning(f"Error cleaning up temp directory for {self.name}: {e}")
            
            self._resources.clear()
            self._initialized = False
            self._temp_dir = None
            logger.info(f"Tool {self.name} cleaned up successfully")
        except Exception as e:
            logger.error(f"Error during cleanup of {self.name}: {e}")
    
    async def restart(self) -> bool:
        """Restart the tool by cleaning up and reinitializing."""
        try:
            await self.cleanup()
            return await self.initialize()
        except Exception as e:
            logger.error(f"Failed to restart tool {self.name}: {e}")
            return False
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get tool health status."""
        return {
            "name": self.name,
            "status": self._health_status,
            "initialized": self._initialized,
            "enabled": self.enabled,
            "last_used": self.last_used,
            "usage_count": self.usage_count,
            "last_error": self._last_error,
            "resource_count": len(self._resources)
        }
    
    def get_temp_dir(self) -> Optional[Path]:
        """Get the temporary directory for this tool."""
        return self._temp_dir
    
    def add_resource(self, resource: Any):
        """Add a resource to be tracked for cleanup."""
        self._resources.append(resource)
    
    @abstractmethod
    async def execute(self, parameters: Dict[str, Any]) -> Any:
        """Execute the tool with given parameters."""
        pass
    
    @abstractmethod
    def get_parameters_schema(self) -> Dict[str, Any]:
        """Get the parameters schema for this tool."""
        pass
    
    async def _setup_resources(self):
        """Setup tool-specific resources. Override in subclasses."""
        pass
    
    async def _cleanup_resources(self):
        """Cleanup tool-specific resources. Override in subclasses."""
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
        """Execute the tool asynchronously with lifecycle management."""
        if not self._initialized:
            await self.initialize()
        
        try:
            self._record_usage()
            self._health_status = "healthy"
            return await self._execute_async(parameters)
        except Exception as e:
            self._health_status = "unhealthy"
            self._last_error = str(e)
            logger.error(f"Error executing tool {self.name}: {e}")
            raise e
    
    @abstractmethod
    async def _execute_async(self, parameters: Dict[str, Any]) -> Any:
        """Async execution implementation."""
        pass


class SyncTool(BaseTool):
    """Base class for synchronous tools."""
    
    async def execute(self, parameters: Dict[str, Any]) -> Any:
        """Execute the tool synchronously in a thread pool with lifecycle management."""
        if not self._initialized:
            await self.initialize()
        
        try:
            self._record_usage()
            self._health_status = "healthy"
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, self._execute_sync, parameters)
        except Exception as e:
            self._health_status = "unhealthy"
            self._last_error = str(e)
            logger.error(f"Error executing tool {self.name}: {e}")
            raise e
    
    @abstractmethod
    def _execute_sync(self, parameters: Dict[str, Any]) -> Any:
        """Sync execution implementation."""
        pass


class ToolRegistry:
    """Registry for managing tools with lifecycle management."""
    
    def __init__(self):
        self.tools: Dict[str, BaseTool] = {}
        self.categories: Dict[ToolCategory, List[str]] = {
            category: [] for category in ToolCategory
        }
        self._initialized = False
    
    async def initialize_all_tools(self) -> Dict[str, bool]:
        """Initialize all tools and return status."""
        results = {}
        for tool_name, tool in self.tools.items():
            try:
                success = await tool.initialize()
                results[tool_name] = success
                if not success:
                    logger.warning(f"Tool {tool_name} failed to initialize")
            except Exception as e:
                logger.error(f"Error initializing tool {tool_name}: {e}")
                results[tool_name] = False
        
        self._initialized = True
        return results
    
    async def cleanup_all_tools(self):
        """Cleanup all tools."""
        for tool_name, tool in self.tools.items():
            try:
                await tool.cleanup()
            except Exception as e:
                logger.error(f"Error cleaning up tool {tool_name}: {e}")
        
        self._initialized = False
    
    async def restart_tool(self, tool_name: str) -> bool:
        """Restart a specific tool."""
        tool = self.get_tool(tool_name)
        if not tool:
            logger.error(f"Tool {tool_name} not found")
            return False
        
        try:
            return await tool.restart()
        except Exception as e:
            logger.error(f"Error restarting tool {tool_name}: {e}")
            return False
    
    async def restart_unhealthy_tools(self) -> Dict[str, bool]:
        """Restart all unhealthy tools."""
        results = {}
        for tool_name, tool in self.tools.items():
            if tool._health_status == "unhealthy":
                try:
                    success = await tool.restart()
                    results[tool_name] = success
                except Exception as e:
                    logger.error(f"Error restarting unhealthy tool {tool_name}: {e}")
                    results[tool_name] = False
        
        return results
    
    def get_tool_health_status(self) -> Dict[str, Dict[str, Any]]:
        """Get health status of all tools."""
        return {
            tool_name: tool.get_health_status() 
            for tool_name, tool in self.tools.items()
        }
    
    def get_unhealthy_tools(self) -> List[str]:
        """Get list of unhealthy tool names."""
        return [
            tool_name for tool_name, tool in self.tools.items()
            if tool._health_status == "unhealthy"
        ]
    
    def register_tool(self, tool: BaseTool):
        """Register a tool."""
        self.tools[tool.name] = tool
        self.categories[tool.category].append(tool.name)
        logger.info(f"Registered tool: {tool.name}")
    
    async def unregister_tool(self, tool_name: str):
        """Unregister a tool."""
        if tool_name in self.tools:
            tool = self.tools[tool_name]
            # Cleanup before unregistering
            try:
                await tool.cleanup()
            except Exception as e:
                logger.warning(f"Error cleaning up tool {tool_name} during unregister: {e}")
            
            self.categories[tool.category].remove(tool_name)
            del self.tools[tool_name]
            logger.info(f"Unregistered tool: {tool_name}")
    
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
    
    def get_healthy_tools(self) -> List[BaseTool]:
        """Get all healthy tools."""
        return [tool for tool in self.tools.values() if tool._health_status == "healthy"]
    
    def get_tool_definitions(self) -> List[ToolDefinition]:
        """Get all tool definitions."""
        return [tool.get_definition() for tool in self.tools.values()]
    
    def get_tools_for_langchain(self) -> List[Any]:
        """Get tools formatted for LangChain."""
        # This would need to be implemented based on LangChain's tool format
        # For now, return empty list
        return []
