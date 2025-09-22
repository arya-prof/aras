"""
File creation and removal tools for ARAS.
"""

import os
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from .base import AsyncTool
from ..models import ToolCategory

logger = logging.getLogger(__name__)


class FileCreateRemoveTool(AsyncTool):
    """Tool for creating and removing files and directories."""
    
    def __init__(self):
        super().__init__(
            name="file_create_remove",
            category=ToolCategory.SYSTEM,
            description="Create and remove files and directories with safety checks"
        )
        self._safe_directories = set()  # Track safe directories for operations
    
    async def _execute_async(self, parameters: Dict[str, Any]) -> Any:
        """Execute file creation or removal operation."""
        operation = parameters.get("operation")
        path = parameters.get("path")
        
        if not operation or not path:
            raise ValueError("Operation and path are required")
        
        path = Path(path).resolve()  # Resolve to absolute path
        
        # Safety check - prevent operations outside safe directories
        if not self._is_safe_path(path):
            raise PermissionError(f"Path {path} is not in a safe directory for file operations")
        
        if operation == "create_file":
            content = parameters.get("content", "")
            encoding = parameters.get("encoding", "utf-8")
            return await self._create_file(path, content, encoding)
        elif operation == "create_directory":
            return await self._create_directory(path)
        elif operation == "remove_file":
            return await self._remove_file(path)
        elif operation == "remove_directory":
            force = parameters.get("force", False)
            return await self._remove_directory(path, force)
        elif operation == "remove_path":
            force = parameters.get("force", False)
            return await self._remove_path(path, force)
        elif operation == "exists":
            return await self._check_exists(path)
        elif operation == "get_info":
            return await self._get_path_info(path)
        else:
            raise ValueError(f"Unknown operation: {operation}")
    
    def _is_safe_path(self, path: Path) -> bool:
        """Check if path is in a safe directory for operations."""
        # Define safe base directories
        safe_bases = [
            Path.cwd(),  # Current working directory
            Path.home(),  # User home directory
            self.get_temp_dir(),  # Tool's temp directory
        ]
        
        # Add any configured safe directories
        safe_bases.extend(self._safe_directories)
        
        # Check if path is within any safe base
        for safe_base in safe_bases:
            if safe_base and path.is_relative_to(safe_base):
                return True
        
        return False
    
    def add_safe_directory(self, directory: str):
        """Add a directory to the safe list."""
        safe_path = Path(directory).resolve()
        if safe_path.exists() and safe_path.is_dir():
            self._safe_directories.add(safe_path)
            logger.info(f"Added safe directory: {safe_path}")
        else:
            logger.warning(f"Cannot add safe directory (doesn't exist or not a directory): {safe_path}")
    
    async def _create_file(self, path: Path, content: str, encoding: str) -> Dict[str, Any]:
        """Create a file with content."""
        try:
            # Ensure parent directory exists
            path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write file content
            with open(path, 'w', encoding=encoding) as f:
                f.write(content)
            
            # Get file info
            file_info = await self._get_path_info(path)
            
            logger.info(f"Created file: {path}")
            return {
                "success": True,
                "operation": "create_file",
                "path": str(path),
                "file_info": file_info,
                "message": f"File created successfully: {path}"
            }
        except Exception as e:
            logger.error(f"Error creating file {path}: {e}")
            raise RuntimeError(f"Failed to create file {path}: {e}")
    
    async def _create_directory(self, path: Path) -> Dict[str, Any]:
        """Create a directory."""
        try:
            path.mkdir(parents=True, exist_ok=True)
            
            # Get directory info
            dir_info = await self._get_path_info(path)
            
            logger.info(f"Created directory: {path}")
            return {
                "success": True,
                "operation": "create_directory",
                "path": str(path),
                "directory_info": dir_info,
                "message": f"Directory created successfully: {path}"
            }
        except Exception as e:
            logger.error(f"Error creating directory {path}: {e}")
            raise RuntimeError(f"Failed to create directory {path}: {e}")
    
    async def _remove_file(self, path: Path) -> Dict[str, Any]:
        """Remove a file."""
        try:
            if not path.exists():
                raise FileNotFoundError(f"File not found: {path}")
            
            if not path.is_file():
                raise ValueError(f"Path is not a file: {path}")
            
            path.unlink()
            
            logger.info(f"Removed file: {path}")
            return {
                "success": True,
                "operation": "remove_file",
                "path": str(path),
                "message": f"File removed successfully: {path}"
            }
        except Exception as e:
            logger.error(f"Error removing file {path}: {e}")
            raise RuntimeError(f"Failed to remove file {path}: {e}")
    
    async def _remove_directory(self, path: Path, force: bool = False) -> Dict[str, Any]:
        """Remove a directory."""
        try:
            if not path.exists():
                raise FileNotFoundError(f"Directory not found: {path}")
            
            if not path.is_dir():
                raise ValueError(f"Path is not a directory: {path}")
            
            if force:
                # Remove directory and all contents
                import shutil
                shutil.rmtree(path)
            else:
                # Only remove if empty
                path.rmdir()
            
            logger.info(f"Removed directory: {path}")
            return {
                "success": True,
                "operation": "remove_directory",
                "path": str(path),
                "force": force,
                "message": f"Directory removed successfully: {path}"
            }
        except Exception as e:
            logger.error(f"Error removing directory {path}: {e}")
            raise RuntimeError(f"Failed to remove directory {path}: {e}")
    
    async def _remove_path(self, path: Path, force: bool = False) -> Dict[str, Any]:
        """Remove a file or directory (auto-detect type)."""
        try:
            if not path.exists():
                raise FileNotFoundError(f"Path not found: {path}")
            
            if path.is_file():
                return await self._remove_file(path)
            elif path.is_dir():
                return await self._remove_directory(path, force)
            else:
                raise ValueError(f"Unknown path type: {path}")
        except Exception as e:
            logger.error(f"Error removing path {path}: {e}")
            raise RuntimeError(f"Failed to remove path {path}: {e}")
    
    async def _check_exists(self, path: Path) -> Dict[str, Any]:
        """Check if a path exists."""
        exists = path.exists()
        path_type = None
        
        if exists:
            if path.is_file():
                path_type = "file"
            elif path.is_dir():
                path_type = "directory"
            else:
                path_type = "other"
        
        return {
            "success": True,
            "operation": "exists",
            "path": str(path),
            "exists": exists,
            "type": path_type,
            "message": f"Path {'exists' if exists else 'does not exist'}: {path}"
        }
    
    async def _get_path_info(self, path: Path) -> Dict[str, Any]:
        """Get detailed information about a path."""
        if not path.exists():
            raise FileNotFoundError(f"Path not found: {path}")
        
        stat = path.stat()
        
        info = {
            "name": path.name,
            "path": str(path),
            "absolute_path": str(path.resolve()),
            "is_file": path.is_file(),
            "is_dir": path.is_dir(),
            "size": stat.st_size if path.is_file() else None,
            "created": stat.st_ctime,
            "modified": stat.st_mtime,
            "accessed": stat.st_atime,
            "permissions": oct(stat.st_mode)[-3:],
        }
        
        # Add directory-specific info
        if path.is_dir():
            try:
                contents = list(path.iterdir())
                info["item_count"] = len(contents)
                info["is_empty"] = len(contents) == 0
            except PermissionError:
                info["item_count"] = "unknown"
                info["is_empty"] = "unknown"
        
        return info
    
    async def health_check(self):
        """Health check for file create/remove tool."""
        try:
            # Test basic operations in temp directory
            temp_dir = self.get_temp_dir()
            if not temp_dir:
                raise Exception("No temp directory available")
            
            test_file = temp_dir / "health_check.txt"
            test_dir = temp_dir / "health_check_dir"
            
            # Test file creation
            result = await self._create_file(test_file, "health check", "utf-8")
            if not result.get("success"):
                raise Exception("File creation failed")
            
            # Test file existence check
            exists_result = await self._check_exists(test_file)
            if not exists_result.get("exists"):
                raise Exception("File existence check failed")
            
            # Test directory creation
            dir_result = await self._create_directory(test_dir)
            if not dir_result.get("success"):
                raise Exception("Directory creation failed")
            
            # Test file removal
            remove_result = await self._remove_file(test_file)
            if not remove_result.get("success"):
                raise Exception("File removal failed")
            
            # Test directory removal
            dir_remove_result = await self._remove_directory(test_dir)
            if not dir_remove_result.get("success"):
                raise Exception("Directory removal failed")
            
            logger.debug("FileCreateRemoveTool health check passed")
        except Exception as e:
            logger.error(f"FileCreateRemoveTool health check failed: {e}")
            raise
    
    def get_parameters_schema(self) -> Dict[str, Any]:
        """Get parameters schema."""
        return {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": [
                        "create_file", 
                        "create_directory", 
                        "remove_file", 
                        "remove_directory", 
                        "remove_path",
                        "exists",
                        "get_info"
                    ],
                    "description": "File operation to perform"
                },
                "path": {
                    "type": "string",
                    "description": "File or directory path"
                },
                "content": {
                    "type": "string",
                    "description": "Content to write (for create_file operation)"
                },
                "encoding": {
                    "type": "string",
                    "default": "utf-8",
                    "description": "File encoding (for create_file operation)"
                },
                "force": {
                    "type": "boolean",
                    "default": False,
                    "description": "Force removal of non-empty directories"
                }
            },
            "required": ["operation", "path"]
        }
