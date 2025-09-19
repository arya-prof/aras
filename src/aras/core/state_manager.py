"""
State management for the agent.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from loguru import logger

from ..config import get_data_dir


class StateManager:
    """Manages agent state and persistence."""
    
    def __init__(self):
        self.data_dir = get_data_dir()
        self.state_file = self.data_dir / "agent_state.json"
        self.state: Dict[str, Any] = {}
        self.load_state()
    
    def load_state(self):
        """Load state from file."""
        try:
            if self.state_file.exists():
                with open(self.state_file, 'r') as f:
                    self.state = json.load(f)
                logger.info(f"Loaded state from {self.state_file}")
            else:
                self.state = {
                    "created_at": datetime.now().isoformat(),
                    "sessions": {},
                    "system_status": {},
                    "tool_history": [],
                    "errors": []
                }
                self.save_state()
        except Exception as e:
            logger.error(f"Error loading state: {e}")
            self.state = {
                "created_at": datetime.now().isoformat(),
                "sessions": {},
                "system_status": {},
                "tool_history": [],
                "errors": []
            }
    
    def save_state(self):
        """Save state to file."""
        try:
            self.state["last_updated"] = datetime.now().isoformat()
            with open(self.state_file, 'w') as f:
                json.dump(self.state, f, indent=2)
            logger.debug(f"Saved state to {self.state_file}")
        except Exception as e:
            logger.error(f"Error saving state: {e}")
    
    def update_state(self, component: str, data: Dict[str, Any]):
        """Update component state."""
        if component not in self.state["system_status"]:
            self.state["system_status"][component] = {}
        
        self.state["system_status"][component].update(data)
        self.state["system_status"][component]["last_updated"] = datetime.now().isoformat()
        self.save_state()
    
    def get_state(self, component: Optional[str] = None) -> Dict[str, Any]:
        """Get state for component or all state."""
        if component:
            return self.state["system_status"].get(component, {})
        return self.state
    
    def add_session(self, session_id: str, data: Dict[str, Any]):
        """Add or update session data."""
        self.state["sessions"][session_id] = {
            **data,
            "created_at": datetime.now().isoformat(),
            "last_activity": datetime.now().isoformat()
        }
        self.save_state()
    
    def update_session(self, session_id: str, data: Dict[str, Any]):
        """Update session data."""
        if session_id in self.state["sessions"]:
            self.state["sessions"][session_id].update(data)
            self.state["sessions"][session_id]["last_activity"] = datetime.now().isoformat()
            self.save_state()
    
    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session data."""
        return self.state["sessions"].get(session_id)
    
    def add_tool_call(self, tool_call: Dict[str, Any]):
        """Add tool call to history."""
        self.state["tool_history"].append({
            **tool_call,
            "timestamp": datetime.now().isoformat()
        })
        # Keep only last 1000 tool calls
        if len(self.state["tool_history"]) > 1000:
            self.state["tool_history"] = self.state["tool_history"][-1000:]
        self.save_state()
    
    def get_tool_history(self, limit: int = 100) -> list:
        """Get tool call history."""
        return self.state["tool_history"][-limit:]
    
    def log_error(self, component: str, error: str, details: Optional[Dict[str, Any]] = None):
        """Log an error."""
        error_entry = {
            "component": component,
            "error": error,
            "details": details or {},
            "timestamp": datetime.now().isoformat()
        }
        self.state["errors"].append(error_entry)
        # Keep only last 100 errors
        if len(self.state["errors"]) > 100:
            self.state["errors"] = self.state["errors"][-100:]
        self.save_state()
        logger.error(f"Error in {component}: {error}")
    
    def get_errors(self, component: Optional[str] = None, limit: int = 50) -> list:
        """Get error log."""
        errors = self.state["errors"]
        if component:
            errors = [e for e in errors if e["component"] == component]
        return errors[-limit:]
    
    def cleanup(self):
        """Cleanup old data."""
        # Remove sessions older than 24 hours
        cutoff = datetime.now().timestamp() - (24 * 60 * 60)
        sessions_to_remove = []
        
        for session_id, session_data in self.state["sessions"].items():
            last_activity = datetime.fromisoformat(session_data["last_activity"])
            if last_activity.timestamp() < cutoff:
                sessions_to_remove.append(session_id)
        
        for session_id in sessions_to_remove:
            del self.state["sessions"][session_id]
        
        if sessions_to_remove:
            logger.info(f"Cleaned up {len(sessions_to_remove)} old sessions")
            self.save_state()
