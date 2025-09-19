"""
System tools for file operations, process management, and system control.
"""

import os
import psutil
import subprocess
import shutil
import logging
from pathlib import Path
from typing import Any, Dict, List

from .base import AsyncTool, SyncTool
from ..models import ToolCategory

logger = logging.getLogger(__name__)


class FileOperationsTool(AsyncTool):
    """Tool for file operations with proper resource management."""
    
    def __init__(self):
        super().__init__(
            name="file_operations",
            category=ToolCategory.SYSTEM,
            description="Perform file operations like read, write, copy, move, delete"
        )
        self._file_handles = []  # Track open file handles
    
    async def _execute_async(self, parameters: Dict[str, Any]) -> Any:
        """Execute file operation."""
        operation = parameters.get("operation")
        path = parameters.get("path")
        
        if not operation or not path:
            raise ValueError("Operation and path are required")
        
        path = Path(path)
        
        if operation == "read":
            return await self._read_file(path, parameters.get("encoding", "utf-8"))
        elif operation == "write":
            content = parameters.get("content", "")
            return await self._write_file(path, content, parameters.get("encoding", "utf-8"))
        elif operation == "copy":
            dest = parameters.get("destination")
            if not dest:
                raise ValueError("Destination is required for copy operation")
            return await self._copy_file(path, Path(dest))
        elif operation == "move":
            dest = parameters.get("destination")
            if not dest:
                raise ValueError("Destination is required for move operation")
            return await self._move_file(path, Path(dest))
        elif operation == "delete":
            return await self._delete_file(path)
        elif operation == "list":
            return await self._list_directory(path)
        elif operation == "create_dir":
            return await self._create_directory(path)
        else:
            raise ValueError(f"Unknown operation: {operation}")
    
    async def _read_file(self, path: Path, encoding: str) -> str:
        """Read file content with proper resource management."""
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")
        
        try:
            with open(path, 'r', encoding=encoding) as f:
                content = f.read()
            return content
        except Exception as e:
            logger.error(f"Error reading file {path}: {e}")
            raise
    
    async def _write_file(self, path: Path, content: str, encoding: str) -> bool:
        """Write content to file with proper resource management."""
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(path, 'w', encoding=encoding) as f:
                f.write(content)
            
            return True
        except Exception as e:
            logger.error(f"Error writing file {path}: {e}")
            raise
    
    async def _copy_file(self, src: Path, dest: Path) -> bool:
        """Copy file."""
        if not src.exists():
            raise FileNotFoundError(f"Source file not found: {src}")
        
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        return True
    
    async def _move_file(self, src: Path, dest: Path) -> bool:
        """Move file."""
        if not src.exists():
            raise FileNotFoundError(f"Source file not found: {src}")
        
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dest))
        return True
    
    async def _delete_file(self, path: Path) -> bool:
        """Delete file or directory."""
        if not path.exists():
            raise FileNotFoundError(f"Path not found: {path}")
        
        if path.is_file():
            path.unlink()
        else:
            shutil.rmtree(path)
        
        return True
    
    async def _list_directory(self, path: Path) -> List[Dict[str, Any]]:
        """List directory contents."""
        if not path.exists():
            raise FileNotFoundError(f"Directory not found: {path}")
        
        if not path.is_dir():
            raise ValueError(f"Path is not a directory: {path}")
        
        items = []
        for item in path.iterdir():
            items.append({
                "name": item.name,
                "path": str(item),
                "is_file": item.is_file(),
                "is_dir": item.is_dir(),
                "size": item.stat().st_size if item.is_file() else None,
                "modified": item.stat().st_mtime
            })
        
        return items
    
    async def _create_directory(self, path: Path) -> bool:
        """Create directory."""
        try:
            path.mkdir(parents=True, exist_ok=True)
            return True
        except Exception as e:
            logger.error(f"Error creating directory {path}: {e}")
            raise
    
    async def health_check(self):
        """Health check for file operations tool."""
        try:
            # Test basic file operations in temp directory
            temp_dir = self.get_temp_dir()
            if not temp_dir:
                raise Exception("No temp directory available")
            
            test_file = temp_dir / "health_check.txt"
            
            # Test write
            await self._write_file(test_file, "health check", "utf-8")
            
            # Test read
            content = await self._read_file(test_file, "utf-8")
            if content != "health check":
                raise Exception("File content mismatch")
            
            # Test delete
            test_file.unlink()
            
            logger.debug("FileOperationsTool health check passed")
        except Exception as e:
            logger.error(f"FileOperationsTool health check failed: {e}")
            raise
    
    def get_parameters_schema(self) -> Dict[str, Any]:
        """Get parameters schema."""
        return {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": ["read", "write", "copy", "move", "delete", "list", "create_dir"],
                    "description": "File operation to perform"
                },
                "path": {
                    "type": "string",
                    "description": "File or directory path"
                },
                "content": {
                    "type": "string",
                    "description": "Content to write (for write operation)"
                },
                "destination": {
                    "type": "string",
                    "description": "Destination path (for copy/move operations)"
                },
                "encoding": {
                    "type": "string",
                    "default": "utf-8",
                    "description": "File encoding"
                }
            },
            "required": ["operation", "path"]
        }


class ProcessManagementTool(AsyncTool):
    """Tool for process management."""
    
    def __init__(self):
        super().__init__(
            name="process_management",
            category=ToolCategory.SYSTEM,
            description="Manage system processes - list, start, stop, monitor"
        )
    
    async def _execute_async(self, parameters: Dict[str, Any]) -> Any:
        """Execute process management operation."""
        operation = parameters.get("operation")
        
        if operation == "list":
            return await self._list_processes(parameters.get("filter", ""))
        elif operation == "start":
            command = parameters.get("command")
            if not command:
                raise ValueError("Command is required for start operation")
            return await self._start_process(command, parameters.get("args", []))
        elif operation == "stop":
            pid = parameters.get("pid")
            if not pid:
                raise ValueError("PID is required for stop operation")
            return await self._stop_process(pid)
        elif operation == "info":
            pid = parameters.get("pid")
            if not pid:
                raise ValueError("PID is required for info operation")
            return await self._get_process_info(pid)
        else:
            raise ValueError(f"Unknown operation: {operation}")
    
    async def _list_processes(self, filter_str: str) -> List[Dict[str, Any]]:
        """List running processes."""
        processes = []
        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent', 'status']):
            try:
                proc_info = proc.info
                if not filter_str or filter_str.lower() in proc_info['name'].lower():
                    processes.append({
                        "pid": proc_info['pid'],
                        "name": proc_info['name'],
                        "cpu_percent": proc_info['cpu_percent'],
                        "memory_percent": proc_info['memory_percent'],
                        "status": proc_info['status']
                    })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        
        return processes
    
    async def _start_process(self, command: str, args: List[str]) -> Dict[str, Any]:
        """Start a new process."""
        try:
            process = subprocess.Popen(
                [command] + args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            return {
                "pid": process.pid,
                "command": command,
                "args": args,
                "status": "started"
            }
        except Exception as e:
            raise RuntimeError(f"Failed to start process: {e}")
    
    async def _stop_process(self, pid: int) -> bool:
        """Stop a process by PID."""
        try:
            process = psutil.Process(pid)
            process.terminate()
            return True
        except psutil.NoSuchProcess:
            raise ValueError(f"Process with PID {pid} not found")
        except psutil.AccessDenied:
            raise PermissionError(f"Access denied to process {pid}")
    
    async def _get_process_info(self, pid: int) -> Dict[str, Any]:
        """Get detailed process information."""
        try:
            process = psutil.Process(pid)
            return {
                "pid": process.pid,
                "name": process.name(),
                "status": process.status(),
                "cpu_percent": process.cpu_percent(),
                "memory_percent": process.memory_percent(),
                "memory_info": process.memory_info()._asdict(),
                "create_time": process.create_time(),
                "cmdline": process.cmdline()
            }
        except psutil.NoSuchProcess:
            raise ValueError(f"Process with PID {pid} not found")
    
    async def health_check(self):
        """Health check for process management tool."""
        try:
            # Test basic process operations
            processes = await self._list_processes("")
            if not isinstance(processes, list):
                raise Exception("Process list not returned correctly")
            
            # Test getting current process info
            current_pid = os.getpid()
            process_info = await self._get_process_info(current_pid)
            if not isinstance(process_info, dict) or process_info.get("pid") != current_pid:
                raise Exception("Process info not returned correctly")
            
            logger.debug("ProcessManagementTool health check passed")
        except Exception as e:
            logger.error(f"ProcessManagementTool health check failed: {e}")
            raise
    
    def get_parameters_schema(self) -> Dict[str, Any]:
        """Get parameters schema."""
        return {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": ["list", "start", "stop", "info"],
                    "description": "Process operation to perform"
                },
                "filter": {
                    "type": "string",
                    "description": "Filter processes by name (for list operation)"
                },
                "command": {
                    "type": "string",
                    "description": "Command to start (for start operation)"
                },
                "args": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Command arguments (for start operation)"
                },
                "pid": {
                    "type": "integer",
                    "description": "Process ID (for stop/info operations)"
                }
            },
            "required": ["operation"]
        }


class SystemControlTool(AsyncTool):
    """Tool for system control operations."""
    
    def __init__(self):
        super().__init__(
            name="system_control",
            category=ToolCategory.SYSTEM,
            description="Control system operations - shutdown, restart, sleep, system info"
        )
    
    async def _execute_async(self, parameters: Dict[str, Any]) -> Any:
        """Execute system control operation."""
        operation = parameters.get("operation")
        
        if operation == "shutdown":
            delay = parameters.get("delay", 0)
            return await self._shutdown_system(delay)
        elif operation == "restart":
            delay = parameters.get("delay", 0)
            return await self._restart_system(delay)
        elif operation == "sleep":
            return await self._sleep_system()
        elif operation == "info":
            return await self._get_system_info()
        elif operation == "disk_usage":
            return await self._get_disk_usage()
        elif operation == "memory_usage":
            return await self._get_memory_usage()
        else:
            raise ValueError(f"Unknown operation: {operation}")
    
    async def _shutdown_system(self, delay: int) -> bool:
        """Shutdown the system."""
        if delay > 0:
            subprocess.run(["shutdown", "/s", "/t", str(delay)])
        else:
            subprocess.run(["shutdown", "/s", "/t", "0"])
        return True
    
    async def _restart_system(self, delay: int) -> bool:
        """Restart the system."""
        if delay > 0:
            subprocess.run(["shutdown", "/r", "/t", str(delay)])
        else:
            subprocess.run(["shutdown", "/r", "/t", "0"])
        return True
    
    async def _sleep_system(self) -> bool:
        """Put system to sleep."""
        subprocess.run(["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"])
        return True
    
    async def _get_system_info(self) -> Dict[str, Any]:
        """Get system information."""
        return {
            "platform": psutil.WINDOWS if os.name == 'nt' else psutil.LINUX,
            "cpu_count": psutil.cpu_count(),
            "cpu_percent": psutil.cpu_percent(interval=1),
            "boot_time": psutil.boot_time(),
            "uptime": psutil.boot_time() - psutil.time.time(),
            "memory": psutil.virtual_memory()._asdict(),
            "disk": psutil.disk_usage('/')._asdict()
        }
    
    async def _get_disk_usage(self) -> List[Dict[str, Any]]:
        """Get disk usage information."""
        partitions = psutil.disk_partitions()
        usage = []
        
        for partition in partitions:
            try:
                partition_usage = psutil.disk_usage(partition.mountpoint)
                usage.append({
                    "device": partition.device,
                    "mountpoint": partition.mountpoint,
                    "fstype": partition.fstype,
                    "total": partition_usage.total,
                    "used": partition_usage.used,
                    "free": partition_usage.free,
                    "percent": (partition_usage.used / partition_usage.total) * 100
                })
            except PermissionError:
                continue
        
        return usage
    
    async def _get_memory_usage(self) -> Dict[str, Any]:
        """Get memory usage information."""
        memory = psutil.virtual_memory()
        swap = psutil.swap_memory()
        
        return {
            "virtual": memory._asdict(),
            "swap": swap._asdict()
        }
    
    async def health_check(self):
        """Health check for system control tool."""
        try:
            # Test basic system info operations
            system_info = await self._get_system_info()
            if not isinstance(system_info, dict):
                raise Exception("System info not returned correctly")
            
            # Test memory usage
            memory_info = await self._get_memory_usage()
            if not isinstance(memory_info, dict) or "virtual" not in memory_info:
                raise Exception("Memory info not returned correctly")
            
            # Test disk usage
            disk_info = await self._get_disk_usage()
            if not isinstance(disk_info, list):
                raise Exception("Disk info not returned correctly")
            
            logger.debug("SystemControlTool health check passed")
        except Exception as e:
            logger.error(f"SystemControlTool health check failed: {e}")
            raise
    
    def get_parameters_schema(self) -> Dict[str, Any]:
        """Get parameters schema."""
        return {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": ["shutdown", "restart", "sleep", "info", "disk_usage", "memory_usage"],
                    "description": "System control operation to perform"
                },
                "delay": {
                    "type": "integer",
                    "default": 0,
                    "description": "Delay in seconds before executing operation"
                }
            },
            "required": ["operation"]
        }
