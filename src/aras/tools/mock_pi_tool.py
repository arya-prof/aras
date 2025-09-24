"""
Mock Raspberry Pi tool that works with our mock server.
"""

import socket
import json
import asyncio
import logging
from typing import Any, Dict, List, Optional

from .base import AsyncTool
from ..models import ToolCategory
from ..config import settings

logger = logging.getLogger(__name__)


class MockPiControlTool(AsyncTool):
    """Tool for controlling the mock Raspberry Pi server."""
    
    def __init__(self):
        super().__init__(
            name="mock_pi_control",
            category=ToolCategory.HOME,
            description="Control mock Raspberry Pi devices for testing and development"
        )
        self.pi_host = getattr(settings, 'pi_host', 'localhost')
        self.pi_port = getattr(settings, 'pi_port', 2222)
        self.gpio_enabled = getattr(settings, 'pi_gpio_enabled', True)
    
    async def _execute_async(self, parameters: Dict[str, Any]) -> Any:
        """Execute mock Pi control operation."""
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
        """Execute a command on the mock Pi server."""
        try:
            result = await self._send_command(command)
            return {
                "success": result["success"],
                "command": command,
                "output": result["output"],
                "error": result["error"]
            }
        except Exception as e:
            return {
                "success": False,
                "command": command,
                "output": "",
                "error": str(e)
            }
    
    async def _gpio_set_pin(self, pin: int, state: int) -> Dict[str, Any]:
        """Set GPIO pin state."""
        if not self.gpio_enabled:
            raise RuntimeError("GPIO not enabled")
        
        try:
            command = f"python3 /tmp/gpio_control.py set_pin {pin} {state}"
            result = await self._send_command(command)
            
            if result["success"]:
                return json.loads(result["output"])
            else:
                raise RuntimeError(f"GPIO operation failed: {result['error']}")
        except Exception as e:
            raise RuntimeError(f"Failed to set GPIO pin: {e}")
    
    async def _gpio_read_pin(self, pin: int) -> Dict[str, Any]:
        """Read GPIO pin state."""
        if not self.gpio_enabled:
            raise RuntimeError("GPIO not enabled")
        
        try:
            command = f"python3 /tmp/gpio_control.py read_pin {pin}"
            result = await self._send_command(command)
            
            if result["success"]:
                return json.loads(result["output"])
            else:
                raise RuntimeError(f"GPIO operation failed: {result['error']}")
        except Exception as e:
            raise RuntimeError(f"Failed to read GPIO pin: {e}")
    
    async def _gpio_set_pwm(self, pin: int, duty_cycle: float, frequency: int = 1000) -> Dict[str, Any]:
        """Set GPIO pin PWM."""
        if not self.gpio_enabled:
            raise RuntimeError("GPIO not enabled")
        
        try:
            command = f"python3 /tmp/gpio_control.py set_pwm {pin} {duty_cycle} {frequency}"
            result = await self._send_command(command)
            
            if result["success"]:
                return json.loads(result["output"])
            else:
                raise RuntimeError(f"GPIO operation failed: {result['error']}")
        except Exception as e:
            raise RuntimeError(f"Failed to set GPIO PWM: {e}")
    
    async def _control_light(self, pin: int, brightness: int) -> Dict[str, Any]:
        """Control LED light brightness using PWM."""
        if not self.gpio_enabled:
            raise RuntimeError("GPIO not enabled")
        
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
            raise RuntimeError("GPIO not enabled")
        
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
            raise RuntimeError("GPIO not enabled")
        
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
        """Get mock Pi system information."""
        try:
            # Get CPU temperature
            temp_result = await self._send_command("vcgencmd measure_temp")
            temperature = temp_result["output"].strip().replace("temp=", "").replace("'C", "")
            
            # Get memory usage
            mem_result = await self._send_command("free -h")
            memory_info = mem_result["output"]
            
            # Get disk usage
            disk_result = await self._send_command("df -h /")
            disk_info = disk_result["output"]
            
            # Get uptime
            uptime_result = await self._send_command("uptime")
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
    
    async def _send_command(self, command: str) -> Dict[str, Any]:
        """Send a command to the mock Pi server."""
        try:
            # Create connection
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            sock.connect((self.pi_host, self.pi_port))
            
            # Receive welcome message first
            welcome = sock.recv(1024)
            
            # Send command
            sock.send(command.encode() + b'\n')
            
            # Receive response
            response_data = sock.recv(1024)
            response = response_data.decode().strip()
            
            sock.close()
            
            try:
                # Try to parse as JSON
                result = json.loads(response)
                return result
            except json.JSONDecodeError:
                return {
                    "success": True,
                    "output": response,
                    "error": ""
                }
                
        except Exception as e:
            return {
                "success": False,
                "output": "",
                "error": str(e)
            }
    
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
                    "description": "Mock Pi control operation"
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
