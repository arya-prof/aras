"""
Tool health monitoring and management service.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass

from .base import BaseTool, ToolRegistry

logger = logging.getLogger(__name__)


@dataclass
class HealthCheckResult:
    """Result of a health check."""
    tool_name: str
    healthy: bool
    error: Optional[str] = None
    response_time: float = 0.0
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


class ToolHealthMonitor:
    """Monitor and manage tool health."""
    
    def __init__(self, tool_registry: ToolRegistry, check_interval: int = 60):
        self.tool_registry = tool_registry
        self.check_interval = check_interval
        self.monitoring = False
        self.health_history: Dict[str, List[HealthCheckResult]] = {}
        self.health_callbacks: List[Callable[[HealthCheckResult], None]] = []
        self._monitor_task: Optional[asyncio.Task] = None
    
    async def start_monitoring(self):
        """Start health monitoring."""
        if self.monitoring:
            return
        
        self.monitoring = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info("Tool health monitoring started")
    
    async def stop_monitoring(self):
        """Stop health monitoring."""
        self.monitoring = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        logger.info("Tool health monitoring stopped")
    
    async def _monitor_loop(self):
        """Main monitoring loop."""
        while self.monitoring:
            try:
                await self._check_all_tools()
                await asyncio.sleep(self.check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in health monitoring loop: {e}")
                await asyncio.sleep(5)  # Short delay before retry
    
    async def _check_all_tools(self):
        """Check health of all tools."""
        tools = self.tool_registry.get_all_tools()
        
        for tool in tools:
            if not tool.enabled:
                continue
            
            try:
                result = await self._check_tool_health(tool)
                self._record_health_result(result)
                
                # Notify callbacks
                for callback in self.health_callbacks:
                    try:
                        callback(result)
                    except Exception as e:
                        logger.error(f"Error in health callback: {e}")
                
            except Exception as e:
                logger.error(f"Error checking health of tool {tool.name}: {e}")
    
    async def _check_tool_health(self, tool: BaseTool) -> HealthCheckResult:
        """Check health of a specific tool."""
        start_time = datetime.now()
        
        try:
            # Check if tool is initialized
            if not tool._initialized:
                return HealthCheckResult(
                    tool_name=tool.name,
                    healthy=False,
                    error="Tool not initialized",
                    response_time=0.0
                )
            
            # Try to execute a simple health check
            # This could be a specific health check method or a simple operation
            if hasattr(tool, 'health_check'):
                await tool.health_check()
            else:
                # For tools without specific health check, verify they're responsive
                # by checking their basic properties
                if not tool.is_available():
                    raise Exception("Tool not available")
            
            response_time = (datetime.now() - start_time).total_seconds()
            
            return HealthCheckResult(
                tool_name=tool.name,
                healthy=True,
                response_time=response_time
            )
            
        except Exception as e:
            response_time = (datetime.now() - start_time).total_seconds()
            return HealthCheckResult(
                tool_name=tool.name,
                healthy=False,
                error=str(e),
                response_time=response_time
            )
    
    def _record_health_result(self, result: HealthCheckResult):
        """Record health check result."""
        if result.tool_name not in self.health_history:
            self.health_history[result.tool_name] = []
        
        self.health_history[result.tool_name].append(result)
        
        # Keep only last 100 results per tool
        if len(self.health_history[result.tool_name]) > 100:
            self.health_history[result.tool_name] = self.health_history[result.tool_name][-100:]
    
    def add_health_callback(self, callback: Callable[[HealthCheckResult], None]):
        """Add a callback for health check results."""
        self.health_callbacks.append(callback)
    
    def remove_health_callback(self, callback: Callable[[HealthCheckResult], None]):
        """Remove a health check callback."""
        if callback in self.health_callbacks:
            self.health_callbacks.remove(callback)
    
    def get_health_summary(self) -> Dict[str, Any]:
        """Get health summary for all tools."""
        summary = {}
        
        for tool_name, history in self.health_history.items():
            if not history:
                continue
            
            recent_results = history[-10:]  # Last 10 checks
            healthy_count = sum(1 for r in recent_results if r.healthy)
            total_count = len(recent_results)
            
            avg_response_time = sum(r.response_time for r in recent_results) / total_count if total_count > 0 else 0
            
            summary[tool_name] = {
                "health_percentage": (healthy_count / total_count) * 100 if total_count > 0 else 0,
                "avg_response_time": avg_response_time,
                "last_check": recent_results[-1].timestamp if recent_results else None,
                "last_error": recent_results[-1].error if recent_results and not recent_results[-1].healthy else None,
                "total_checks": len(history)
            }
        
        return summary
    
    def get_unhealthy_tools(self) -> List[str]:
        """Get list of currently unhealthy tools."""
        unhealthy = []
        
        for tool_name, history in self.health_history.items():
            if history and not history[-1].healthy:
                unhealthy.append(tool_name)
        
        return unhealthy
    
    def get_tool_health_history(self, tool_name: str, limit: int = 50) -> List[HealthCheckResult]:
        """Get health history for a specific tool."""
        return self.health_history.get(tool_name, [])[-limit:]
    
    async def force_health_check(self, tool_name: Optional[str] = None) -> Dict[str, HealthCheckResult]:
        """Force a health check for specific tool or all tools."""
        results = {}
        
        if tool_name:
            tool = self.tool_registry.get_tool(tool_name)
            if tool:
                result = await self._check_tool_health(tool)
                results[tool_name] = result
                self._record_health_result(result)
        else:
            tools = self.tool_registry.get_all_tools()
            for tool in tools:
                if not tool.enabled:
                    continue
                
                result = await self._check_tool_health(tool)
                results[tool.name] = result
                self._record_health_result(result)
        
        return results
    
    async def auto_restart_unhealthy_tools(self, max_restart_attempts: int = 3) -> Dict[str, bool]:
        """Automatically restart unhealthy tools."""
        unhealthy_tools = self.get_unhealthy_tools()
        restart_results = {}
        
        for tool_name in unhealthy_tools:
            # Check if tool has been failing consistently
            history = self.health_history.get(tool_name, [])
            recent_failures = sum(1 for r in history[-5:] if not r.healthy)  # Last 5 checks
            
            if recent_failures >= 3:  # Failed 3+ times in last 5 checks
                try:
                    success = await self.tool_registry.restart_tool(tool_name)
                    restart_results[tool_name] = success
                    
                    if success:
                        logger.info(f"Successfully restarted unhealthy tool: {tool_name}")
                    else:
                        logger.warning(f"Failed to restart tool: {tool_name}")
                        
                except Exception as e:
                    logger.error(f"Error restarting tool {tool_name}: {e}")
                    restart_results[tool_name] = False
        
        return restart_results
