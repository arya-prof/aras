"""
Smart home tools for device control, scene management, and climate control.
"""

import aiohttp
import asyncio
import ssl
import logging
import paramiko
import json
import subprocess
from typing import Any, Dict, List, Optional
from pathlib import Path

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


class RaspberryPiControlTool(AsyncTool):
    """Tool for controlling Raspberry Pi devices via SSH and GPIO."""
    
    def __init__(self):
        super().__init__(
            name="raspberry_pi_control",
            category=ToolCategory.HOME,
            description="Control Raspberry Pi devices via SSH and GPIO for smart home automation"
        )
        self.pi_host = settings.pi_host
        self.pi_port = settings.pi_port
        self.pi_username = settings.pi_username
        self.pi_password = settings.pi_password
        self.pi_key_file = settings.pi_key_file
        self.gpio_enabled = settings.pi_gpio_enabled
        self.ssh_client = None
        self.sftp_client = None
    
    async def _setup_resources(self):
        """Setup SSH connection to Raspberry Pi."""
        if not self.pi_host:
            logger.warning("Raspberry Pi not configured, tool will be disabled")
            self.disable()
            return
        
        try:
            # Create SSH client
            self.ssh_client = paramiko.SSHClient()
            self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            # Connect to Raspberry Pi
            if self.pi_key_file and Path(self.pi_key_file).exists():
                # Use SSH key authentication
                self.ssh_client.connect(
                    hostname=self.pi_host,
                    port=self.pi_port,
                    username=self.pi_username,
                    key_filename=self.pi_key_file,
                    timeout=10
                )
            elif self.pi_password:
                # Use password authentication
                self.ssh_client.connect(
                    hostname=self.pi_host,
                    port=self.pi_port,
                    username=self.pi_username,
                    password=self.pi_password,
                    timeout=10
                )
            else:
                raise ValueError("Either pi_password or pi_key_file must be configured")
            
            # Create SFTP client for file operations
            self.sftp_client = self.ssh_client.open_sftp()
            
            self.add_resource(self.ssh_client)
            self.add_resource(self.sftp_client)
            
            # Test GPIO setup if enabled
            if self.gpio_enabled:
                await self._setup_gpio()
            
            logger.info(f"RaspberryPiControlTool connected to {self.pi_host}")
            
        except Exception as e:
            logger.error(f"Failed to connect to Raspberry Pi: {e}")
            self.disable()
            raise
    
    async def _cleanup_resources(self):
        """Cleanup SSH connections."""
        if self.sftp_client:
            self.sftp_client.close()
        if self.ssh_client:
            self.ssh_client.close()
        logger.info("RaspberryPiControlTool SSH connections closed")
    
    async def _setup_gpio(self):
        """Setup GPIO on Raspberry Pi."""
        try:
            # Check if RPi.GPIO is available
            stdin, stdout, stderr = self.ssh_client.exec_command("python3 -c 'import RPi.GPIO as GPIO; print(\"GPIO available\")'")
            result = stdout.read().decode().strip()
            if "GPIO available" not in result:
                logger.warning("RPi.GPIO not available on Raspberry Pi")
                self.gpio_enabled = False
                return
            
            # Create GPIO control script
            gpio_script = """
import RPi.GPIO as GPIO
import sys
import json

def setup_gpio():
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)

def cleanup_gpio():
    GPIO.cleanup()

def set_pin(pin, state):
    GPIO.setup(pin, GPIO.OUT)
    GPIO.output(pin, state)
    return {"pin": pin, "state": state}

def read_pin(pin):
    GPIO.setup(pin, GPIO.IN)
    state = GPIO.input(pin)
    return {"pin": pin, "state": state}

def set_pwm(pin, duty_cycle, frequency=1000):
    GPIO.setup(pin, GPIO.OUT)
    pwm = GPIO.PWM(pin, frequency)
    pwm.start(duty_cycle)
    return {"pin": pin, "duty_cycle": duty_cycle, "frequency": frequency}

if __name__ == "__main__":
    try:
        command = sys.argv[1]
        setup_gpio()
        
        if command == "set_pin":
            pin = int(sys.argv[2])
            state = int(sys.argv[3])
            result = set_pin(pin, state)
        elif command == "read_pin":
            pin = int(sys.argv[2])
            result = read_pin(pin)
        elif command == "set_pwm":
            pin = int(sys.argv[2])
            duty_cycle = float(sys.argv[3])
            frequency = int(sys.argv[4]) if len(sys.argv) > 4 else 1000
            result = set_pwm(pin, duty_cycle, frequency)
        else:
            result = {"error": "Unknown command"}
        
        print(json.dumps(result))
    except Exception as e:
        print(json.dumps({"error": str(e)}))
    finally:
        cleanup_gpio()
"""
            
            # Write script to Pi
            with self.sftp_client.open('/tmp/gpio_control.py', 'w') as f:
                f.write(gpio_script)
            
            logger.info("GPIO control script installed on Raspberry Pi")
            
        except Exception as e:
            logger.error(f"Failed to setup GPIO: {e}")
            self.gpio_enabled = False
    
    async def _execute_async(self, parameters: Dict[str, Any]) -> Any:
        """Execute Raspberry Pi control operation."""
        if not self.ssh_client:
            raise RuntimeError("Not connected to Raspberry Pi")
        
        operation = parameters.get("operation")
        
        if operation == "execute_command":
            command = parameters.get("command")
            if not command:
                raise ValueError("Command is required for execute_command operation")
            return await self._execute_command(command)
        
        elif operation == "gpio_set_pin":
            pin = parameters.get("pin")
            state = parameters.get("state")
            if pin is None or state is None:
                raise ValueError("Pin and state are required for gpio_set_pin operation")
            return await self._gpio_set_pin(pin, state)
        
        elif operation == "gpio_read_pin":
            pin = parameters.get("pin")
            if pin is None:
                raise ValueError("Pin is required for gpio_read_pin operation")
            return await self._gpio_read_pin(pin)
        
        elif operation == "gpio_set_pwm":
            pin = parameters.get("pin")
            duty_cycle = parameters.get("duty_cycle")
            frequency = parameters.get("frequency", 1000)
            if pin is None or duty_cycle is None:
                raise ValueError("Pin and duty_cycle are required for gpio_set_pwm operation")
            return await self._gpio_set_pwm(pin, duty_cycle, frequency)
        
        elif operation == "control_light":
            pin = parameters.get("pin")
            brightness = parameters.get("brightness", 100)
            if pin is None:
                raise ValueError("Pin is required for control_light operation")
            return await self._control_light(pin, brightness)
        
        elif operation == "control_relay":
            pin = parameters.get("pin")
            state = parameters.get("state")
            if pin is None or state is None:
                raise ValueError("Pin and state are required for control_relay operation")
            return await self._control_relay(pin, state)
        
        elif operation == "read_sensor":
            pin = parameters.get("pin")
            sensor_type = parameters.get("sensor_type", "digital")
            if pin is None:
                raise ValueError("Pin is required for read_sensor operation")
            return await self._read_sensor(pin, sensor_type)
        
        elif operation == "get_system_info":
            return await self._get_system_info()
        
        else:
            raise ValueError(f"Unknown operation: {operation}")
    
    async def _execute_command(self, command: str) -> Dict[str, Any]:
        """Execute a command on the Raspberry Pi."""
        try:
            stdin, stdout, stderr = self.ssh_client.exec_command(command)
            exit_code = stdout.channel.recv_exit_status()
            output = stdout.read().decode()
            error = stderr.read().decode()
            
            return {
                "success": exit_code == 0,
                "command": command,
                "exit_code": exit_code,
                "output": output,
                "error": error
            }
        except Exception as e:
            raise RuntimeError(f"Failed to execute command: {e}")
    
    async def _gpio_set_pin(self, pin: int, state: int) -> Dict[str, Any]:
        """Set GPIO pin state."""
        if not self.gpio_enabled:
            raise RuntimeError("GPIO not enabled or not available")
        
        try:
            command = f"python3 /tmp/gpio_control.py set_pin {pin} {state}"
            result = await self._execute_command(command)
            
            if result["success"]:
                return json.loads(result["output"])
            else:
                raise RuntimeError(f"GPIO operation failed: {result['error']}")
        except Exception as e:
            raise RuntimeError(f"Failed to set GPIO pin: {e}")
    
    async def _gpio_read_pin(self, pin: int) -> Dict[str, Any]:
        """Read GPIO pin state."""
        if not self.gpio_enabled:
            raise RuntimeError("GPIO not enabled or not available")
        
        try:
            command = f"python3 /tmp/gpio_control.py read_pin {pin}"
            result = await self._execute_command(command)
            
            if result["success"]:
                return json.loads(result["output"])
            else:
                raise RuntimeError(f"GPIO operation failed: {result['error']}")
        except Exception as e:
            raise RuntimeError(f"Failed to read GPIO pin: {e}")
    
    async def _gpio_set_pwm(self, pin: int, duty_cycle: float, frequency: int = 1000) -> Dict[str, Any]:
        """Set GPIO pin PWM."""
        if not self.gpio_enabled:
            raise RuntimeError("GPIO not enabled or not available")
        
        try:
            command = f"python3 /tmp/gpio_control.py set_pwm {pin} {duty_cycle} {frequency}"
            result = await self._execute_command(command)
            
            if result["success"]:
                return json.loads(result["output"])
            else:
                raise RuntimeError(f"GPIO operation failed: {result['error']}")
        except Exception as e:
            raise RuntimeError(f"Failed to set GPIO PWM: {e}")
    
    async def _control_light(self, pin: int, brightness: int) -> Dict[str, Any]:
        """Control LED light brightness using PWM."""
        if not self.gpio_enabled:
            raise RuntimeError("GPIO not enabled or not available")
        
        try:
            # Convert brightness percentage to duty cycle (0-100)
            duty_cycle = max(0, min(100, brightness))
            result = await self._gpio_set_pwm(pin, duty_cycle)
            
            return {
                "success": True,
                "pin": pin,
                "brightness": brightness,
                "duty_cycle": duty_cycle
            }
        except Exception as e:
            raise RuntimeError(f"Failed to control light: {e}")
    
    async def _control_relay(self, pin: int, state: bool) -> Dict[str, Any]:
        """Control relay switch."""
        if not self.gpio_enabled:
            raise RuntimeError("GPIO not enabled or not available")
        
        try:
            result = await self._gpio_set_pin(pin, 1 if state else 0)
            
            return {
                "success": True,
                "pin": pin,
                "state": state,
                "relay_on": state
            }
        except Exception as e:
            raise RuntimeError(f"Failed to control relay: {e}")
    
    async def _read_sensor(self, pin: int, sensor_type: str = "digital") -> Dict[str, Any]:
        """Read sensor value."""
        if not self.gpio_enabled:
            raise RuntimeError("GPIO not enabled or not available")
        
        try:
            if sensor_type == "digital":
                result = await self._gpio_read_pin(pin)
                return {
                    "success": True,
                    "pin": pin,
                    "sensor_type": sensor_type,
                    "value": result["state"],
                    "digital_value": bool(result["state"])
                }
            else:
                # For analog sensors, you might need an ADC
                raise ValueError(f"Unsupported sensor type: {sensor_type}")
        except Exception as e:
            raise RuntimeError(f"Failed to read sensor: {e}")
    
    async def _get_system_info(self) -> Dict[str, Any]:
        """Get Raspberry Pi system information."""
        try:
            # Get CPU temperature
            temp_result = await self._execute_command("vcgencmd measure_temp")
            temperature = temp_result["output"].strip().replace("temp=", "").replace("'C", "")
            
            # Get memory usage
            mem_result = await self._execute_command("free -h")
            memory_info = mem_result["output"]
            
            # Get disk usage
            disk_result = await self._execute_command("df -h /")
            disk_info = disk_result["output"]
            
            # Get uptime
            uptime_result = await self._execute_command("uptime")
            uptime = uptime_result["output"].strip()
            
            return {
                "success": True,
                "temperature": temperature,
                "memory": memory_info,
                "disk": disk_info,
                "uptime": uptime,
                "gpio_enabled": self.gpio_enabled
            }
        except Exception as e:
            raise RuntimeError(f"Failed to get system info: {e}")
    
    def get_parameters_schema(self) -> Dict[str, Any]:
        """Get parameters schema."""
        return {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": [
                        "execute_command", "gpio_set_pin", "gpio_read_pin", "gpio_set_pwm",
                        "control_light", "control_relay", "read_sensor", "get_system_info"
                    ],
                    "description": "Raspberry Pi control operation"
                },
                "command": {
                    "type": "string",
                    "description": "Command to execute (for execute_command operation)"
                },
                "pin": {
                    "type": "integer",
                    "description": "GPIO pin number"
                },
                "state": {
                    "type": "integer",
                    "description": "Pin state (0 or 1)"
                },
                "brightness": {
                    "type": "integer",
                    "minimum": 0,
                    "maximum": 100,
                    "description": "Light brightness percentage"
                },
                "duty_cycle": {
                    "type": "number",
                    "minimum": 0,
                    "maximum": 100,
                    "description": "PWM duty cycle percentage"
                },
                "frequency": {
                    "type": "integer",
                    "description": "PWM frequency in Hz"
                },
                "sensor_type": {
                    "type": "string",
                    "enum": ["digital", "analog"],
                    "description": "Type of sensor to read"
                }
            },
            "required": ["operation"]
        }
