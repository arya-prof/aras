"""
Arduino Bluetooth control tool for HC-05 module with BTE firmware.
Controls Arduino devices via Bluetooth Low Energy (BLE) communication using Bleak.
"""

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional
from pathlib import Path

try:
    from bleak import BleakClient, BleakScanner
    from bleak.backends.characteristic import BleakGATTCharacteristic
    BLEAK_AVAILABLE = True
except ImportError:
    BLEAK_AVAILABLE = False

from .base import AsyncTool
from ..models import ToolCategory
from ..config import settings

logger = logging.getLogger(__name__)

# BLE Configuration for HC-05 BTE firmware
DEVICE_NAME = "AA"
CHAR_UUID = "0000ffe1-0000-1000-8000-00805f9b34fb"


class ArduinoBluetoothTool(AsyncTool):
    """Tool for controlling Arduino devices via Bluetooth Low Energy (HC-05 with BTE firmware)."""
    
    def __init__(self):
        super().__init__(
            name="arduino_bluetooth_control",
            category=ToolCategory.HOME,
            description="Control Arduino devices via Bluetooth Low Energy using HC-05 BTE firmware"
        )
        self.client = None
        self.device_address = None
        self.characteristic = None
        self.connection_lock = None
        self.last_heartbeat = 0
        self.heartbeat_interval = 5.0  # seconds
        self.device_states = {"L1": False, "L2": False}  # Track device states
        self.response_buffer = ""
        self.response_ready = False
        
    async def _setup_resources(self):
        """Setup Bluetooth Low Energy connection to Arduino."""
        if not BLEAK_AVAILABLE:
            logger.error("Bleak library not available. Install with: pip install bleak")
            self.disable()
            return
        
        # Initialize asyncio objects in the current event loop
        self.connection_lock = asyncio.Lock()
        
        try:
            # Find and connect to HC-05 BLE module
            await self._find_and_connect_ble()
            logger.info("ArduinoBluetoothTool initialized and connected via BLE")
        except Exception as e:
            logger.warning(f"Arduino Bluetooth tool initialization failed: {e}")
            logger.info("Arduino Bluetooth tool will be disabled. Connect Arduino device and restart to enable.")
            self.disable()
            # Don't raise the exception - just disable the tool gracefully
    
    async def _cleanup_resources(self):
        """Cleanup Bluetooth Low Energy connection."""
        if self.client and self.client.is_connected:
            await self.client.disconnect()
            logger.info("Arduino BLE connection closed")
    
    async def _find_and_connect_ble(self):
        """Find and connect to HC-05 BLE module."""
        logger.info(f"Scanning for BLE device: {DEVICE_NAME}")
        
        # Scan for BLE devices
        devices = await BleakScanner.discover(timeout=10.0)
        logger.info(f"Found {len(devices)} BLE devices during scan")
        
        # Log all discovered devices for debugging
        for device in devices:
            logger.debug(f"Discovered BLE device: {device.name or 'Unknown'} ({device.address})")
        
        target_device = None
        for device in devices:
            if device.name and DEVICE_NAME.lower() in device.name.lower():
                target_device = device
                logger.info(f"Found target BLE device: {device.name} ({device.address})")
                break
        
        if not target_device:
            logger.warning(f"BLE device '{DEVICE_NAME}' not found in {len(devices)} discovered devices")
            raise RuntimeError(f"BLE device '{DEVICE_NAME}' not found. Please ensure it's powered on and in range.")
        
        # Connect to the device
        self.device_address = target_device.address
        self.client = BleakClient(self.device_address)
        
        try:
            logger.info(f"Attempting to connect to BLE device: {target_device.address}")
            await self.client.connect()
            logger.info(f"Connected to BLE device: {target_device.name}")
            
            # Find the characteristic
            logger.info("Discovering GATT services...")
            services = self.client.services
            logger.info(f"Found GATT services collection")
            
            for service in services:
                logger.debug(f"Service: {service.uuid} with characteristics")
                for char in service.characteristics:
                    logger.debug(f"Characteristic: {char.uuid}")
                    if char.uuid.lower() == CHAR_UUID.lower():
                        self.characteristic = char
                        logger.info(f"Found target characteristic: {char.uuid}")
                        break
                if self.characteristic:
                    break
            
            if not self.characteristic:
                logger.error(f"Characteristic {CHAR_UUID} not found on device")
                logger.error("Available characteristics:")
                try:
                    for service in services:
                        for char in service.characteristics:
                            logger.error(f"  - {char.uuid}")
                except Exception as e:
                    logger.error(f"Could not enumerate characteristics: {e}")
                raise RuntimeError(f"Characteristic {CHAR_UUID} not found on device")
            
            # Set up notification handler
            logger.info("Setting up notification handler...")
            await self.client.start_notify(self.characteristic, self._notification_handler)
            
            # Test connection with ping
            logger.info("Testing connection with ping...")
            await self._test_connection()
            
            logger.info(f"Successfully connected to Arduino via BLE: {target_device.name}")
            
        except Exception as e:
            logger.error(f"BLE connection failed: {e}")
            if self.client:
                try:
                    await self.client.disconnect()
                except:
                    pass
            raise RuntimeError(f"Failed to connect to BLE device: {e}")
    
    def _notification_handler(self, sender: BleakGATTCharacteristic, data: bytearray):
        """Handle BLE notifications from Arduino."""
        try:
            response = data.decode('utf-8', errors='ignore')
            self.response_buffer += response
            logger.debug(f"Received BLE data: {response}")
            
            # Set flag if we received a complete response
            if '\n' in response or '\r' in response:
                self.response_ready = True
        except Exception as e:
            logger.error(f"Error handling BLE notification: {e}")
    
    async def _test_connection(self):
        """Test the BLE connection with a ping."""
        try:
            # Clear response buffer and flag
            self.response_buffer = ""
            self.response_ready = False
            
            # Send ping command
            await self._send_command('z')
            
            # Wait for response with timeout
            start_time = time.time()
            while time.time() - start_time < 2.0:
                if self.response_ready:
                    response = self.response_buffer.strip()
                    if 'PONG' in response or 'OK' in response:
                        logger.info("Arduino BLE connection test successful")
                        return True
                    break
                await asyncio.sleep(0.1)
            
            logger.warning("Arduino BLE connection test timeout - no response to ping")
            return False
            
        except Exception as e:
            logger.error(f"BLE connection test failed: {e}")
            return False
    
    async def _send_command(self, command: str) -> None:
        """Send a command to Arduino via BLE."""
        if not self.client or not self.client.is_connected:
            raise RuntimeError("Not connected to Arduino BLE device")
        
        if not self.characteristic:
            raise RuntimeError("BLE characteristic not available")
        
        # Clear response buffer
        self.response_buffer = ""
        
        # Send command
        await self.client.write_gatt_char(self.characteristic, command.encode('utf-8'))
        logger.debug(f"Sent BLE command: {command}")
    
    async def _wait_for_response(self, timeout: float = 2.0) -> str:
        """Wait for response from Arduino via BLE."""
        # Clear response flag
        self.response_ready = False
        
        # Wait for response with timeout
        start_time = time.time()
        while time.time() - start_time < timeout:
            if self.response_ready:
                response = self.response_buffer.strip()
                self.response_buffer = ""  # Clear buffer after reading
                return response
            await asyncio.sleep(0.1)
        
        logger.warning(f"BLE response timeout after {timeout}s")
        return ""
    

    async def _execute_async(self, parameters: Dict[str, Any]) -> Any:
        """Execute Arduino control operation."""
        if not self.enabled:
            return {
                "success": False,
                "error": "Arduino Bluetooth tool is disabled. No Arduino device found or connection failed.",
                "suggestion": "Connect Arduino device with HC-05 BLE module and restart the agent."
            }
        
        # Ensure connection lock is created in current event loop
        if self.connection_lock is None:
            self.connection_lock = asyncio.Lock()
        
        if not self.client or not self.client.is_connected:
            raise RuntimeError("Not connected to Arduino. Please check BLE connection.")
        
        operation = parameters.get("operation")
        
        if operation == "control_light":
            light_id = parameters.get("light_id")
            state = parameters.get("state")
            if not light_id or state is None:
                raise ValueError("light_id and state are required for control_light operation")
            return await self._control_light(light_id, state)
        
        elif operation == "toggle_light":
            light_id = parameters.get("light_id")
            if not light_id:
                raise ValueError("light_id is required for toggle_light operation")
            return await self._toggle_light(light_id)
        
        elif operation == "control_all_lights":
            state = parameters.get("state")
            if state is None:
                raise ValueError("state is required for control_all_lights operation")
            return await self._control_all_lights(state)
        
        elif operation == "get_status":
            return await self._get_status()
        
        elif operation == "ping":
            return await self._ping()
        
        else:
            raise ValueError(f"Unknown operation: {operation}")
    
    async def _control_light(self, light_id: str, state: bool) -> Dict[str, Any]:
        """Control a specific light."""
        async with self.connection_lock:
            try:
                # Map light IDs to Arduino commands
                command_map = {
                    "L1": "A" if state else "a",
                    "L2": "B" if state else "b"
                }
                
                if light_id not in command_map:
                    raise ValueError(f"Invalid light_id: {light_id}. Use L1 or L2")
                
                command = command_map[light_id]
                
                # Send command via BLE
                await self._send_command(command)
                
                # Update local state
                self.device_states[light_id] = state
                
                # Wait for response
                response = await self._wait_for_response(1.0)
                
                return {
                    "success": True,
                    "light_id": light_id,
                    "state": "ON" if state else "OFF",
                    "command_sent": command,
                    "arduino_response": response
                }
                
            except Exception as e:
                raise RuntimeError(f"Failed to control light {light_id}: {e}")
    
    async def _toggle_light(self, light_id: str) -> Dict[str, Any]:
        """Toggle a specific light."""
        if light_id not in self.device_states:
            raise ValueError(f"Invalid light_id: {light_id}. Use L1 or L2")
        
        current_state = self.device_states[light_id]
        new_state = not current_state
        
        return await self._control_light(light_id, new_state)
    
    async def _control_all_lights(self, state: bool) -> Dict[str, Any]:
        """Control all lights at once."""
        async with self.connection_lock:
            try:
                command = "Y" if state else "y"
                
                # Send command via BLE
                await self._send_command(command)
                
                # Update local states
                for light_id in self.device_states:
                    self.device_states[light_id] = state
                
                # Wait for response
                response = await self._wait_for_response(1.0)
                
                return {
                    "success": True,
                    "all_lights": "ON" if state else "OFF",
                    "command_sent": command,
                    "affected_lights": list(self.device_states.keys()),
                    "arduino_response": response
                }
                
            except Exception as e:
                raise RuntimeError(f"Failed to control all lights: {e}")
    
    async def _get_status(self) -> Dict[str, Any]:
        """Get current status of all devices."""
        async with self.connection_lock:
            try:
                # Send status request via BLE
                await self._send_command('Z')
                
                # Wait for response
                response = await self._wait_for_response(2.0)
                
                return {
                    "success": True,
                    "connection_status": "connected",
                    "device_address": self.device_address,
                    "device_states": self.device_states.copy(),
                    "arduino_response": response
                }
                
            except Exception as e:
                raise RuntimeError(f"Failed to get status: {e}")
    
    async def _ping(self) -> Dict[str, Any]:
        """Send ping to Arduino."""
        async with self.connection_lock:
            try:
                # Send ping via BLE
                await self._send_command('z')
                
                # Wait for response
                response = await self._wait_for_response(2.0)
                
                return {
                    "success": True,
                    "ping_sent": True,
                    "response": response,
                    "connection_alive": "PONG" in response or "OK" in response
                }
                
            except Exception as e:
                raise RuntimeError(f"Ping failed: {e}")
    
    async def try_reconnect(self) -> bool:
        """Try to reconnect to Arduino device."""
        if self.enabled:
            return True
        
        try:
            await self._find_and_connect_ble()
            self.enable()
            logger.info("Arduino Bluetooth tool reconnected successfully")
            return True
        except Exception as e:
            logger.warning(f"Failed to reconnect Arduino Bluetooth tool: {e}")
            return False
    
    def get_parameters_schema(self) -> Dict[str, Any]:
        """Get parameters schema."""
        return {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": ["control_light", "toggle_light", "control_all_lights", "get_status", "ping"],
                    "description": "Arduino control operation"
                },
                "light_id": {
                    "type": "string",
                    "enum": ["L1", "L2"],
                    "description": "Light identifier (L1 or L2)"
                },
                "state": {
                    "type": "boolean",
                    "description": "Light state (true for ON, false for OFF)"
                }
            },
            "required": ["operation"]
        }
