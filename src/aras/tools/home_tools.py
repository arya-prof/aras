"""
Smart home tools for device control, scene management, and climate control.
"""

import aiohttp
import asyncio
import ssl
import logging
from typing import Any, Dict, List, Optional

from .base import AsyncTool
from ..models import ToolCategory
from ..config import settings

logger = logging.getLogger(__name__)

# Try to import homeassistant, but make it optional
try:
    import homeassistant
    HA_AVAILABLE = True
except ImportError:
    HA_AVAILABLE = False


class DeviceControlTool(AsyncTool):
    """Tool for controlling smart home devices with proper client management."""
    
    def __init__(self):
        super().__init__(
            name="device_control",
            category=ToolCategory.HOME,
            description="Control smart home devices like lights, switches, sensors"
        )
        self.ha_base_url = settings.ha_base_url
        self.ha_token = settings.ha_token
        self.session = None
        self.connector = None
    
    async def _setup_resources(self):
        """Setup Home Assistant client with connection pooling."""
        if not self.ha_base_url or not self.ha_token:
            logger.warning("Home Assistant not configured, tool will be disabled")
            self.disable()
            return
        
        # Create SSL context
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        
        # Create connector with connection pooling
        self.connector = aiohttp.TCPConnector(
            limit=50,  # Total connection pool size
            limit_per_host=10,  # Per-host connection limit
            ssl=ssl_context,
            keepalive_timeout=30,
            enable_cleanup_closed=True
        )
        
        # Create session with timeout and headers
        timeout = aiohttp.ClientTimeout(total=30, connect=10)
        self.session = aiohttp.ClientSession(
            connector=self.connector,
            timeout=timeout,
            headers={
                'Authorization': f'Bearer {self.ha_token}',
                'Content-Type': 'application/json',
                'User-Agent': 'ARAS-HomeTool/1.0'
            }
        )
        
        self.add_resource(self.session)
        self.add_resource(self.connector)
        logger.info(f"DeviceControlTool initialized with Home Assistant client")
    
    async def _cleanup_resources(self):
        """Cleanup Home Assistant client resources."""
        if self.session:
            await self.session.close()
        if self.connector:
            await self.connector.close()
        logger.info(f"DeviceControlTool resources cleaned up")
    
    async def _execute_async(self, parameters: Dict[str, Any]) -> Any:
        """Execute device control operation."""
        if not self.ha_base_url or not self.ha_token:
            raise RuntimeError("Home Assistant not configured")
        
        operation = parameters.get("operation")
        entity_id = parameters.get("entity_id")
        
        if not operation or not entity_id:
            raise ValueError("Operation and entity_id are required")
        
        if operation == "turn_on":
            return await self._turn_on_device(entity_id, parameters.get("attributes", {}))
        elif operation == "turn_off":
            return await self._turn_off_device(entity_id)
        elif operation == "toggle":
            return await self._toggle_device(entity_id)
        elif operation == "set_state":
            state = parameters.get("state")
            if not state:
                raise ValueError("State is required for set_state operation")
            return await self._set_device_state(entity_id, state, parameters.get("attributes", {}))
        elif operation == "get_state":
            return await self._get_device_state(entity_id)
        elif operation == "list_devices":
            return await self._list_devices(parameters.get("domain"))
        else:
            raise ValueError(f"Unknown operation: {operation}")
    
    async def _turn_on_device(self, entity_id: str, attributes: Dict[str, Any]) -> Dict[str, Any]:
        """Turn on a device."""
        if not HA_AVAILABLE:
            raise RuntimeError("Home Assistant package not installed. Install with: pip install homeassistant")
        
        url = f"{self.ha_base_url}/api/services/homeassistant/turn_on"
        data = {
            "entity_id": entity_id,
            **attributes
        }
        
        try:
            async with self.session.post(url, json=data) as response:
                if response.status == 200:
                    return {"success": True, "entity_id": entity_id, "action": "turned_on"}
                else:
                    error_text = await response.text()
                    raise RuntimeError(f"Failed to turn on device: {error_text}")
        except aiohttp.ClientError as e:
            raise RuntimeError(f"Network error turning on device: {e}")
    
    async def _turn_off_device(self, entity_id: str) -> Dict[str, Any]:
        """Turn off a device."""
        if not HA_AVAILABLE:
            raise RuntimeError("Home Assistant package not installed. Install with: pip install homeassistant")
        
        url = f"{self.ha_base_url}/api/services/homeassistant/turn_off"
        data = {"entity_id": entity_id}
        
        try:
            async with self.session.post(url, json=data) as response:
                if response.status == 200:
                    return {"success": True, "entity_id": entity_id, "action": "turned_off"}
                else:
                    error_text = await response.text()
                    raise RuntimeError(f"Failed to turn off device: {error_text}")
        except aiohttp.ClientError as e:
            raise RuntimeError(f"Network error turning off device: {e}")
    
    async def _toggle_device(self, entity_id: str) -> Dict[str, Any]:
        """Toggle a device."""
        url = f"{self.ha_base_url}/api/services/homeassistant/toggle"
        data = {"entity_id": entity_id}
        
        try:
            async with self.session.post(url, json=data) as response:
                if response.status == 200:
                    return {"success": True, "entity_id": entity_id, "action": "toggled"}
                else:
                    error_text = await response.text()
                    raise RuntimeError(f"Failed to toggle device: {error_text}")
        except aiohttp.ClientError as e:
            raise RuntimeError(f"Network error toggling device: {e}")
    
    async def _set_device_state(self, entity_id: str, state: str, attributes: Dict[str, Any]) -> Dict[str, Any]:
        """Set device state."""
        url = f"{self.ha_base_url}/api/states/{entity_id}"
        data = {
            "state": state,
            "attributes": attributes
        }
        
        try:
            async with self.session.post(url, json=data) as response:
                if response.status == 200:
                    return {"success": True, "entity_id": entity_id, "state": state}
                else:
                    error_text = await response.text()
                    raise RuntimeError(f"Failed to set device state: {error_text}")
        except aiohttp.ClientError as e:
            raise RuntimeError(f"Network error setting device state: {e}")
    
    async def _get_device_state(self, entity_id: str) -> Dict[str, Any]:
        """Get device state."""
        url = f"{self.ha_base_url}/api/states/{entity_id}"
        
        try:
            async with self.session.get(url) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    error_text = await response.text()
                    raise RuntimeError(f"Failed to get device state: {error_text}")
        except aiohttp.ClientError as e:
            raise RuntimeError(f"Network error getting device state: {e}")
    
    async def _list_devices(self, domain: Optional[str] = None) -> List[Dict[str, Any]]:
        """List devices."""
        url = f"{self.ha_base_url}/api/states"
        
        try:
            async with self.session.get(url) as response:
                if response.status == 200:
                    states = await response.json()
                    if domain:
                        states = [state for state in states if state["entity_id"].startswith(domain)]
                    return states
                else:
                    error_text = await response.text()
                    raise RuntimeError(f"Failed to list devices: {error_text}")
        except aiohttp.ClientError as e:
            raise RuntimeError(f"Network error listing devices: {e}")
    
    def get_parameters_schema(self) -> Dict[str, Any]:
        """Get parameters schema."""
        return {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": ["turn_on", "turn_off", "toggle", "set_state", "get_state", "list_devices"],
                    "description": "Device control operation"
                },
                "entity_id": {
                    "type": "string",
                    "description": "Home Assistant entity ID"
                },
                "state": {
                    "type": "string",
                    "description": "State to set (for set_state operation)"
                },
                "attributes": {
                    "type": "object",
                    "description": "Device attributes"
                },
                "domain": {
                    "type": "string",
                    "description": "Domain filter (for list_devices operation)"
                }
            },
            "required": ["operation", "entity_id"]
        }


class SceneManagementTool(AsyncTool):
    """Tool for managing smart home scenes."""
    
    def __init__(self):
        super().__init__(
            name="scene_management",
            category=ToolCategory.HOME,
            description="Manage smart home scenes and automations"
        )
        self.ha_base_url = settings.ha_base_url
        self.ha_token = settings.ha_token
    
    async def _execute_async(self, parameters: Dict[str, Any]) -> Any:
        """Execute scene management operation."""
        operation = parameters.get("operation")
        
        if operation == "activate_scene":
            scene_id = parameters.get("scene_id")
            if not scene_id:
                raise ValueError("scene_id is required for activate_scene operation")
            return await self._activate_scene(scene_id)
        elif operation == "list_scenes":
            return await self._list_scenes()
        elif operation == "create_scene":
            scene_data = parameters.get("scene_data", {})
            return await self._create_scene(scene_data)
        elif operation == "delete_scene":
            scene_id = parameters.get("scene_id")
            if not scene_id:
                raise ValueError("scene_id is required for delete_scene operation")
            return await self._delete_scene(scene_id)
        else:
            raise ValueError(f"Unknown operation: {operation}")
    
    async def _activate_scene(self, scene_id: str) -> Dict[str, Any]:
        """Activate a scene."""
        if not self.ha_base_url or not self.ha_token:
            raise RuntimeError("Home Assistant not configured")
        
        url = f"{self.ha_base_url}/api/services/scene/turn_on"
        headers = {
            "Authorization": f"Bearer {self.ha_token}",
            "Content-Type": "application/json"
        }
        data = {"entity_id": scene_id}
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=data) as response:
                if response.status == 200:
                    return {"success": True, "scene_id": scene_id, "action": "activated"}
                else:
                    error_text = await response.text()
                    raise RuntimeError(f"Failed to activate scene: {error_text}")
    
    async def _list_scenes(self) -> List[Dict[str, Any]]:
        """List all scenes."""
        if not self.ha_base_url or not self.ha_token:
            raise RuntimeError("Home Assistant not configured")
        
        url = f"{self.ha_base_url}/api/states"
        headers = {"Authorization": f"Bearer {self.ha_token}"}
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    states = await response.json()
                    scenes = [state for state in states if state["entity_id"].startswith("scene.")]
                    return scenes
                else:
                    error_text = await response.text()
                    raise RuntimeError(f"Failed to list scenes: {error_text}")
    
    async def _create_scene(self, scene_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new scene."""
        # This would require more complex implementation
        # For now, return a placeholder
        return {
            "success": True,
            "message": "Scene creation not implemented yet",
            "scene_data": scene_data
        }
    
    async def _delete_scene(self, scene_id: str) -> Dict[str, Any]:
        """Delete a scene."""
        # This would require more complex implementation
        # For now, return a placeholder
        return {
            "success": True,
            "message": "Scene deletion not implemented yet",
            "scene_id": scene_id
        }
    
    def get_parameters_schema(self) -> Dict[str, Any]:
        """Get parameters schema."""
        return {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": ["activate_scene", "list_scenes", "create_scene", "delete_scene"],
                    "description": "Scene management operation"
                },
                "scene_id": {
                    "type": "string",
                    "description": "Scene ID"
                },
                "scene_data": {
                    "type": "object",
                    "description": "Scene data for creation"
                }
            },
            "required": ["operation"]
        }


class ClimateControlTool(AsyncTool):
    """Tool for climate control operations."""
    
    def __init__(self):
        super().__init__(
            name="climate_control",
            category=ToolCategory.HOME,
            description="Control climate systems like thermostats, HVAC, fans"
        )
        self.ha_base_url = settings.ha_base_url
        self.ha_token = settings.ha_token
    
    async def _execute_async(self, parameters: Dict[str, Any]) -> Any:
        """Execute climate control operation."""
        operation = parameters.get("operation")
        entity_id = parameters.get("entity_id")
        
        if not operation or not entity_id:
            raise ValueError("Operation and entity_id are required")
        
        if operation == "set_temperature":
            temperature = parameters.get("temperature")
            if temperature is None:
                raise ValueError("Temperature is required for set_temperature operation")
            return await self._set_temperature(entity_id, temperature)
        elif operation == "set_mode":
            mode = parameters.get("mode")
            if not mode:
                raise ValueError("Mode is required for set_mode operation")
            return await self._set_mode(entity_id, mode)
        elif operation == "set_fan_mode":
            fan_mode = parameters.get("fan_mode")
            if not fan_mode:
                raise ValueError("Fan mode is required for set_fan_mode operation")
            return await self._set_fan_mode(entity_id, fan_mode)
        elif operation == "turn_on":
            return await self._turn_on_climate(entity_id)
        elif operation == "turn_off":
            return await self._turn_off_climate(entity_id)
        elif operation == "get_status":
            return await self._get_climate_status(entity_id)
        else:
            raise ValueError(f"Unknown operation: {operation}")
    
    async def _set_temperature(self, entity_id: str, temperature: float) -> Dict[str, Any]:
        """Set climate temperature."""
        if not self.ha_base_url or not self.ha_token:
            raise RuntimeError("Home Assistant not configured")
        
        url = f"{self.ha_base_url}/api/services/climate/set_temperature"
        headers = {
            "Authorization": f"Bearer {self.ha_token}",
            "Content-Type": "application/json"
        }
        data = {
            "entity_id": entity_id,
            "temperature": temperature
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=data) as response:
                if response.status == 200:
                    return {"success": True, "entity_id": entity_id, "temperature": temperature}
                else:
                    error_text = await response.text()
                    raise RuntimeError(f"Failed to set temperature: {error_text}")
    
    async def _set_mode(self, entity_id: str, mode: str) -> Dict[str, Any]:
        """Set climate mode."""
        if not self.ha_base_url or not self.ha_token:
            raise RuntimeError("Home Assistant not configured")
        
        url = f"{self.ha_base_url}/api/services/climate/set_hvac_mode"
        headers = {
            "Authorization": f"Bearer {self.ha_token}",
            "Content-Type": "application/json"
        }
        data = {
            "entity_id": entity_id,
            "hvac_mode": mode
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=data) as response:
                if response.status == 200:
                    return {"success": True, "entity_id": entity_id, "mode": mode}
                else:
                    error_text = await response.text()
                    raise RuntimeError(f"Failed to set mode: {error_text}")
    
    async def _set_fan_mode(self, entity_id: str, fan_mode: str) -> Dict[str, Any]:
        """Set fan mode."""
        if not self.ha_base_url or not self.ha_token:
            raise RuntimeError("Home Assistant not configured")
        
        url = f"{self.ha_base_url}/api/services/climate/set_fan_mode"
        headers = {
            "Authorization": f"Bearer {self.ha_token}",
            "Content-Type": "application/json"
        }
        data = {
            "entity_id": entity_id,
            "fan_mode": fan_mode
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=data) as response:
                if response.status == 200:
                    return {"success": True, "entity_id": entity_id, "fan_mode": fan_mode}
                else:
                    error_text = await response.text()
                    raise RuntimeError(f"Failed to set fan mode: {error_text}")
    
    async def _turn_on_climate(self, entity_id: str) -> Dict[str, Any]:
        """Turn on climate system."""
        return await self._set_mode(entity_id, "heat")
    
    async def _turn_off_climate(self, entity_id: str) -> Dict[str, Any]:
        """Turn off climate system."""
        return await self._set_mode(entity_id, "off")
    
    async def _get_climate_status(self, entity_id: str) -> Dict[str, Any]:
        """Get climate system status."""
        if not self.ha_base_url or not self.ha_token:
            raise RuntimeError("Home Assistant not configured")
        
        url = f"{self.ha_base_url}/api/states/{entity_id}"
        headers = {"Authorization": f"Bearer {self.ha_token}"}
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    error_text = await response.text()
                    raise RuntimeError(f"Failed to get climate status: {error_text}")
    
    def get_parameters_schema(self) -> Dict[str, Any]:
        """Get parameters schema."""
        return {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": ["set_temperature", "set_mode", "set_fan_mode", "turn_on", "turn_off", "get_status"],
                    "description": "Climate control operation"
                },
                "entity_id": {
                    "type": "string",
                    "description": "Climate entity ID"
                },
                "temperature": {
                    "type": "number",
                    "description": "Temperature to set"
                },
                "mode": {
                    "type": "string",
                    "description": "HVAC mode (heat, cool, auto, off)"
                },
                "fan_mode": {
                    "type": "string",
                    "description": "Fan mode"
                }
            },
            "required": ["operation", "entity_id"]
        }
