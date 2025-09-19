"""
Safety and utility tools for permission checks, access control, and audit logging.
"""

import asyncio
import json
from datetime import datetime
from typing import Any, Dict, List, Optional
from pathlib import Path

from .base import AsyncTool
from ..models import ToolCategory


class PermissionCheckTool(AsyncTool):
    """Tool for permission checks."""
    
    def __init__(self):
        super().__init__(
            name="permission_checks",
            category=ToolCategory.SAFETY,
            description="Check permissions and access rights"
        )
        self.permissions_file = Path("data/permissions.json")
        self.permissions_file.parent.mkdir(parents=True, exist_ok=True)
        self._load_permissions()
    
    def _load_permissions(self):
        """Load permissions from file."""
        if self.permissions_file.exists():
            try:
                with open(self.permissions_file, 'r') as f:
                    content = f.read().strip()
                    if content:
                        self.permissions = json.loads(content)
                    else:
                        raise json.JSONDecodeError("Empty file", "", 0)
            except (json.JSONDecodeError, FileNotFoundError):
                # File is empty or corrupted, use defaults
                self.permissions = {
                    "users": {},
                    "roles": {},
                    "resources": {}
                }
                self._save_permissions()
        else:
            self.permissions = {
                "users": {},
                "roles": {},
                "resources": {}
            }
            self._save_permissions()
    
    def _save_permissions(self):
        """Save permissions to file."""
        with open(self.permissions_file, 'w') as f:
            json.dump(self.permissions, f, indent=2)
    
    async def _execute_async(self, parameters: Dict[str, Any]) -> Any:
        """Execute permission check operation."""
        operation = parameters.get("operation")
        
        if operation == "check_permission":
            return await self._check_permission(
                user_id=parameters.get("user_id"),
                resource=parameters.get("resource"),
                action=parameters.get("action")
            )
        elif operation == "grant_permission":
            return await self._grant_permission(
                user_id=parameters.get("user_id"),
                resource=parameters.get("resource"),
                action=parameters.get("action"),
                granted_by=parameters.get("granted_by")
            )
        elif operation == "revoke_permission":
            return await self._revoke_permission(
                user_id=parameters.get("user_id"),
                resource=parameters.get("resource"),
                action=parameters.get("action")
            )
        elif operation == "list_permissions":
            return await self._list_permissions(
                user_id=parameters.get("user_id")
            )
        else:
            raise ValueError(f"Unknown operation: {operation}")
    
    async def _check_permission(self, user_id: str, resource: str, action: str) -> Dict[str, Any]:
        """Check if user has permission for resource and action."""
        if not all([user_id, resource, action]):
            raise ValueError("user_id, resource, and action are required")
        
        user_permissions = self.permissions["users"].get(user_id, {})
        resource_permissions = user_permissions.get(resource, [])
        
        has_permission = action in resource_permissions
        
        return {
            "user_id": user_id,
            "resource": resource,
            "action": action,
            "has_permission": has_permission,
            "timestamp": datetime.now().isoformat()
        }
    
    async def _grant_permission(self, user_id: str, resource: str, action: str, granted_by: str) -> Dict[str, Any]:
        """Grant permission to user."""
        if not all([user_id, resource, action, granted_by]):
            raise ValueError("user_id, resource, action, and granted_by are required")
        
        if user_id not in self.permissions["users"]:
            self.permissions["users"][user_id] = {}
        
        if resource not in self.permissions["users"][user_id]:
            self.permissions["users"][user_id][resource] = []
        
        if action not in self.permissions["users"][user_id][resource]:
            self.permissions["users"][user_id][resource].append(action)
        
        self._save_permissions()
        
        return {
            "success": True,
            "user_id": user_id,
            "resource": resource,
            "action": action,
            "granted_by": granted_by,
            "timestamp": datetime.now().isoformat()
        }
    
    async def _revoke_permission(self, user_id: str, resource: str, action: str) -> Dict[str, Any]:
        """Revoke permission from user."""
        if not all([user_id, resource, action]):
            raise ValueError("user_id, resource, and action are required")
        
        if user_id in self.permissions["users"] and resource in self.permissions["users"][user_id]:
            if action in self.permissions["users"][user_id][resource]:
                self.permissions["users"][user_id][resource].remove(action)
                self._save_permissions()
                return {
                    "success": True,
                    "user_id": user_id,
                    "resource": resource,
                    "action": action,
                    "timestamp": datetime.now().isoformat()
                }
        
        return {
            "success": False,
            "message": "Permission not found",
            "user_id": user_id,
            "resource": resource,
            "action": action
        }
    
    async def _list_permissions(self, user_id: Optional[str] = None) -> Dict[str, Any]:
        """List permissions."""
        if user_id:
            user_permissions = self.permissions["users"].get(user_id, {})
            return {
                "user_id": user_id,
                "permissions": user_permissions
            }
        else:
            return {
                "all_permissions": self.permissions["users"]
            }
    
    def get_parameters_schema(self) -> Dict[str, Any]:
        """Get parameters schema."""
        return {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": ["check_permission", "grant_permission", "revoke_permission", "list_permissions"],
                    "description": "Permission operation"
                },
                "user_id": {
                    "type": "string",
                    "description": "User ID"
                },
                "resource": {
                    "type": "string",
                    "description": "Resource name"
                },
                "action": {
                    "type": "string",
                    "description": "Action name"
                },
                "granted_by": {
                    "type": "string",
                    "description": "User who granted permission"
                }
            },
            "required": ["operation"]
        }


class AccessControlTool(AsyncTool):
    """Tool for access control."""
    
    def __init__(self):
        super().__init__(
            name="access_control",
            category=ToolCategory.SAFETY,
            description="Control access to resources and operations"
        )
        self.access_log = []
    
    async def _execute_async(self, parameters: Dict[str, Any]) -> Any:
        """Execute access control operation."""
        operation = parameters.get("operation")
        
        if operation == "check_access":
            return await self._check_access(
                user_id=parameters.get("user_id"),
                resource=parameters.get("resource"),
                action=parameters.get("action"),
                context=parameters.get("context", {})
            )
        elif operation == "log_access":
            return await self._log_access(
                user_id=parameters.get("user_id"),
                resource=parameters.get("resource"),
                action=parameters.get("action"),
                result=parameters.get("result"),
                context=parameters.get("context", {})
            )
        elif operation == "get_access_log":
            return await self._get_access_log(
                user_id=parameters.get("user_id"),
                limit=parameters.get("limit", 100)
            )
        else:
            raise ValueError(f"Unknown operation: {operation}")
    
    async def _check_access(self, user_id: str, resource: str, action: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Check if user has access to resource."""
        if not all([user_id, resource, action]):
            raise ValueError("user_id, resource, and action are required")
        
        # This is a simplified access control implementation
        # In a real implementation, you'd have more sophisticated rules
        
        # For now, allow all access (placeholder)
        has_access = True
        
        # Log the access attempt
        await self._log_access(user_id, resource, action, "allowed" if has_access else "denied", context)
        
        return {
            "user_id": user_id,
            "resource": resource,
            "action": action,
            "has_access": has_access,
            "context": context,
            "timestamp": datetime.now().isoformat()
        }
    
    async def _log_access(self, user_id: str, resource: str, action: str, result: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Log access attempt."""
        if not all([user_id, resource, action, result]):
            raise ValueError("user_id, resource, action, and result are required")
        
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "user_id": user_id,
            "resource": resource,
            "action": action,
            "result": result,
            "context": context
        }
        
        self.access_log.append(log_entry)
        
        # Keep only last 1000 entries
        if len(self.access_log) > 1000:
            self.access_log = self.access_log[-1000:]
        
        return {
            "success": True,
            "log_entry": log_entry
        }
    
    async def _get_access_log(self, user_id: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """Get access log."""
        log_entries = self.access_log
        
        if user_id:
            log_entries = [entry for entry in log_entries if entry["user_id"] == user_id]
        
        return log_entries[-limit:]
    
    def get_parameters_schema(self) -> Dict[str, Any]:
        """Get parameters schema."""
        return {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": ["check_access", "log_access", "get_access_log"],
                    "description": "Access control operation"
                },
                "user_id": {
                    "type": "string",
                    "description": "User ID"
                },
                "resource": {
                    "type": "string",
                    "description": "Resource name"
                },
                "action": {
                    "type": "string",
                    "description": "Action name"
                },
                "result": {
                    "type": "string",
                    "description": "Access result (allowed/denied)"
                },
                "context": {
                    "type": "object",
                    "description": "Additional context"
                },
                "limit": {
                    "type": "integer",
                    "default": 100,
                    "description": "Maximum number of log entries"
                }
            },
            "required": ["operation"]
        }


class AuditLoggingTool(AsyncTool):
    """Tool for audit logging."""
    
    def __init__(self):
        super().__init__(
            name="audit_logging",
            category=ToolCategory.SAFETY,
            description="Log system events and actions for audit purposes"
        )
        self.audit_log = []
        self.audit_file = Path("data/audit.log")
        self.audit_file.parent.mkdir(parents=True, exist_ok=True)
    
    async def _execute_async(self, parameters: Dict[str, Any]) -> Any:
        """Execute audit logging operation."""
        operation = parameters.get("operation")
        
        if operation == "log_event":
            return await self._log_event(
                event_type=parameters.get("event_type"),
                user_id=parameters.get("user_id"),
                resource=parameters.get("resource"),
                action=parameters.get("action"),
                details=parameters.get("details", {}),
                severity=parameters.get("severity", "info")
            )
        elif operation == "get_audit_log":
            return await self._get_audit_log(
                event_type=parameters.get("event_type"),
                user_id=parameters.get("user_id"),
                severity=parameters.get("severity"),
                limit=parameters.get("limit", 100)
            )
        else:
            raise ValueError(f"Unknown operation: {operation}")
    
    async def _log_event(self, event_type: str, user_id: str, resource: str, action: str, 
                        details: Dict[str, Any], severity: str = "info") -> Dict[str, Any]:
        """Log an audit event."""
        if not all([event_type, user_id, resource, action]):
            raise ValueError("event_type, user_id, resource, and action are required")
        
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "event_type": event_type,
            "user_id": user_id,
            "resource": resource,
            "action": action,
            "details": details,
            "severity": severity
        }
        
        self.audit_log.append(log_entry)
        
        # Write to file
        with open(self.audit_file, 'a') as f:
            f.write(json.dumps(log_entry) + '\n')
        
        return {
            "success": True,
            "log_entry": log_entry
        }
    
    async def _get_audit_log(self, event_type: Optional[str] = None, user_id: Optional[str] = None, 
                           severity: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """Get audit log entries."""
        log_entries = self.audit_log
        
        if event_type:
            log_entries = [entry for entry in log_entries if entry["event_type"] == event_type]
        
        if user_id:
            log_entries = [entry for entry in log_entries if entry["user_id"] == user_id]
        
        if severity:
            log_entries = [entry for entry in log_entries if entry["severity"] == severity]
        
        return log_entries[-limit:]
    
    def get_parameters_schema(self) -> Dict[str, Any]:
        """Get parameters schema."""
        return {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": ["log_event", "get_audit_log"],
                    "description": "Audit logging operation"
                },
                "event_type": {
                    "type": "string",
                    "description": "Type of event"
                },
                "user_id": {
                    "type": "string",
                    "description": "User ID"
                },
                "resource": {
                    "type": "string",
                    "description": "Resource name"
                },
                "action": {
                    "type": "string",
                    "description": "Action performed"
                },
                "details": {
                    "type": "object",
                    "description": "Additional event details"
                },
                "severity": {
                    "type": "string",
                    "enum": ["debug", "info", "warning", "error", "critical"],
                    "default": "info",
                    "description": "Event severity"
                },
                "limit": {
                    "type": "integer",
                    "default": 100,
                    "description": "Maximum number of log entries"
                }
            },
            "required": ["operation"]
        }
