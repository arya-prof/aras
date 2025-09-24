#!/usr/bin/env python3
"""
Mock Raspberry Pi Server for ARAS Testing
Simulates SSH server and GPIO functionality for testing the Raspberry Pi Control Tool.
"""

import asyncio
import json
import logging
import random
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional
import threading
import socket
import socketserver
import subprocess
import sys

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class MockGPIO:
    """Mock GPIO implementation that simulates Raspberry Pi GPIO functionality."""
    
    def __init__(self):
        self.pins = {}  # pin -> {'mode': 'IN'/'OUT', 'state': 0/1, 'pwm': None}
        self.pwm_objects = {}  # pin -> PWM object
        self.mode = None
        self.warnings = True
        
    def setmode(self, mode):
        """Set GPIO mode (BCM, BOARD, etc.)."""
        self.mode = mode
        logger.info(f"GPIO mode set to {mode}")
    
    def setwarnings(self, enable):
        """Enable/disable GPIO warnings."""
        self.warnings = enable
        logger.info(f"GPIO warnings {'enabled' if enable else 'disabled'}")
    
    def setup(self, pin, mode):
        """Setup GPIO pin."""
        if pin not in self.pins:
            self.pins[pin] = {'mode': None, 'state': 0, 'pwm': None}
        
        self.pins[pin]['mode'] = mode
        logger.info(f"GPIO pin {pin} setup as {mode}")
    
    def output(self, pin, state):
        """Set GPIO pin output state."""
        if pin not in self.pins:
            self.pins[pin] = {'mode': 'OUT', 'state': 0, 'pwm': None}
        
        self.pins[pin]['state'] = state
        logger.info(f"GPIO pin {pin} set to {state}")
    
    def input(self, pin):
        """Read GPIO pin input state."""
        if pin not in self.pins:
            self.pins[pin] = {'mode': 'IN', 'state': 0, 'pwm': None}
        
        # Simulate some randomness for sensor readings
        if self.pins[pin]['mode'] == 'IN':
            # 10% chance of random value for sensor simulation
            if random.random() < 0.1:
                self.pins[pin]['state'] = random.randint(0, 1)
        
        return self.pins[pin]['state']
    
    def PWM(self, pin, frequency):
        """Create PWM object."""
        if pin not in self.pins:
            self.pins[pin] = {'mode': 'OUT', 'state': 0, 'pwm': None}
        
        pwm = MockPWM(pin, frequency)
        self.pins[pin]['pwm'] = pwm
        self.pwm_objects[pin] = pwm
        logger.info(f"PWM created for pin {pin} at {frequency}Hz")
        return pwm
    
    def cleanup(self):
        """Cleanup GPIO resources."""
        for pin, pwm in self.pwm_objects.items():
            if pwm:
                pwm.stop()
        self.pwm_objects.clear()
        self.pins.clear()
        logger.info("GPIO cleanup completed")

class MockPWM:
    """Mock PWM implementation."""
    
    def __init__(self, pin, frequency):
        self.pin = pin
        self.frequency = frequency
        self.duty_cycle = 0
        self.running = False
    
    def start(self, duty_cycle):
        """Start PWM with duty cycle."""
        self.duty_cycle = duty_cycle
        self.running = True
        logger.info(f"PWM started on pin {self.pin} with {duty_cycle}% duty cycle")
    
    def stop(self):
        """Stop PWM."""
        self.running = False
        logger.info(f"PWM stopped on pin {self.pin}")
    
    def ChangeDutyCycle(self, duty_cycle):
        """Change PWM duty cycle."""
        self.duty_cycle = duty_cycle
        logger.info(f"PWM duty cycle changed to {duty_cycle}% on pin {self.pin}")

class MockRaspberryPi:
    """Mock Raspberry Pi system that simulates real Pi functionality."""
    
    def __init__(self):
        self.gpio = MockGPIO()
        self.system_info = {
            'temperature': 45.2,
            'memory_total': '3.8G',
            'memory_used': '1.2G',
            'memory_free': '2.6G',
            'disk_total': '29G',
            'disk_used': '8.5G',
            'disk_free': '20G',
            'uptime': '2 days, 14:32:15',
            'load_average': '0.15, 0.12, 0.08'
        }
        self.start_time = time.time()
    
    def get_temperature(self):
        """Get simulated CPU temperature."""
        # Simulate temperature variation
        base_temp = 45.0
        variation = random.uniform(-2.0, 5.0)
        temp = base_temp + variation
        self.system_info['temperature'] = round(temp, 1)
        return f"temp={temp:.1f}'C"
    
    def get_memory_info(self):
        """Get simulated memory information."""
        return f"""              total        used        free      shared  buff/cache   available
Mem:           3.8G        1.2G        2.6G         45M        456M        2.3G
Swap:            0B          0B          0B"""
    
    def get_disk_info(self):
        """Get simulated disk information."""
        return f"""Filesystem      Size  Used Avail Use% Mounted on
/dev/root        29G  8.5G   20G  31% /
devtmpfs        1.9G     0  1.9G   0% /dev
tmpfs           1.9G  4.0K  1.9G   1% /dev/shm
tmpfs           1.9G  1.2M  1.9G   1% /run
tmpfs           5.0M  4.0K  5.0M   1% /run/lock
tmpfs           1.9G     0  1.9G   0% /sys/fs/cgroup
/dev/mmcblk0p1  253M   54M  199M  22% /boot"""
    
    def get_uptime(self):
        """Get simulated uptime."""
        uptime_seconds = int(time.time() - self.start_time)
        days = uptime_seconds // 86400
        hours = (uptime_seconds % 86400) // 3600
        minutes = (uptime_seconds % 3600) // 60
        seconds = uptime_seconds % 60
        
        uptime_str = f"up {days} days, {hours:02d}:{minutes:02d}:{seconds:02d}"
        self.system_info['uptime'] = uptime_str
        return uptime_str

class MockSSHHandler:
    """Mock SSH command handler that processes commands like a real Raspberry Pi."""
    
    def __init__(self):
        self.pi = MockRaspberryPi()
        self.gpio_script_path = Path("/tmp/gpio_control.py")
        self._create_gpio_script()
    
    def _create_gpio_script(self):
        """Create the GPIO control script that would be on a real Pi."""
        gpio_script = '''#!/usr/bin/env python3
import sys
import json

# Mock GPIO implementation
class MockGPIO:
    def __init__(self):
        self.pins = {}
        self.mode = None
        self.warnings = True
    
    def setmode(self, mode):
        self.mode = mode
    
    def setwarnings(self, enable):
        self.warnings = enable
    
    def setup(self, pin, mode):
        if pin not in self.pins:
            self.pins[pin] = {'mode': None, 'state': 0, 'pwm': None}
        self.pins[pin]['mode'] = mode
    
    def output(self, pin, state):
        if pin not in self.pins:
            self.pins[pin] = {'mode': 'OUT', 'state': 0, 'pwm': None}
        self.pins[pin]['state'] = state
    
    def input(self, pin):
        if pin not in self.pins:
            self.pins[pin] = {'mode': 'IN', 'state': 0, 'pwm': None}
        return self.pins[pin]['state']
    
    def PWM(self, pin, frequency):
        if pin not in self.pins:
            self.pins[pin] = {'mode': 'OUT', 'state': 0, 'pwm': None}
        pwm = MockPWM(pin, frequency)
        self.pins[pin]['pwm'] = pwm
        return pwm
    
    def cleanup(self):
        for pin, data in self.pins.items():
            if data['pwm']:
                data['pwm'].stop()

class MockPWM:
    def __init__(self, pin, frequency):
        self.pin = pin
        self.frequency = frequency
        self.duty_cycle = 0
        self.running = False
    
    def start(self, duty_cycle):
        self.duty_cycle = duty_cycle
        self.running = True
    
    def stop(self):
        self.running = False

# Global GPIO instance
GPIO = MockGPIO()

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
'''
        
        # Create the script in a temporary location
        script_dir = Path(__file__).parent / "tmp"
        try:
            script_dir.mkdir(exist_ok=True)
            self.gpio_script_path = script_dir / "gpio_control.py"
            
            with open(self.gpio_script_path, 'w') as f:
                f.write(gpio_script)
            
            logger.info(f"GPIO control script created at {self.gpio_script_path}")
        except Exception as e:
            logger.error(f"Failed to create GPIO script: {e}")
            # Fallback to a simpler approach
            import tempfile
            temp_dir = Path(tempfile.gettempdir())
            self.gpio_script_path = temp_dir / "gpio_control.py"
            
            with open(self.gpio_script_path, 'w') as f:
                f.write(gpio_script)
            
            logger.info(f"GPIO control script created at {self.gpio_script_path} (fallback location)")
    
    def execute_command(self, command: str) -> Dict[str, Any]:
        """Execute a command and return the result."""
        logger.info(f"Executing command: {command}")
        
        try:
            # Handle different types of commands
            if command.startswith("python3 /tmp/gpio_control.py"):
                return self._execute_gpio_command(command)
            elif command == "vcgencmd measure_temp":
                return {
                    "success": True,
                    "output": self.pi.get_temperature(),
                    "error": ""
                }
            elif command == "free -h":
                return {
                    "success": True,
                    "output": self.pi.get_memory_info(),
                    "error": ""
                }
            elif command == "df -h /":
                return {
                    "success": True,
                    "output": self.pi.get_disk_info(),
                    "error": ""
                }
            elif command == "uptime":
                return {
                    "success": True,
                    "output": self.pi.get_uptime(),
                    "error": ""
                }
            elif command.startswith("echo "):
                message = command[5:].strip('"\'')
                return {
                    "success": True,
                    "output": message,
                    "error": ""
                }
            elif command.startswith("ls "):
                # Simulate directory listing
                return {
                    "success": True,
                    "output": "total 0\ndrwxr-xr-x 2 pi pi 4096 Dec 15 10:30 .\ndrwxr-xr-x 3 pi pi 4096 Dec 15 10:30 ..\n-rw-r--r-- 1 pi pi    0 Dec 15 10:30 test.txt",
                    "error": ""
                }
            else:
                # Generic command execution
                return {
                    "success": True,
                    "output": f"Mock execution of: {command}",
                    "error": ""
                }
        
        except Exception as e:
            logger.error(f"Command execution failed: {e}")
            return {
                "success": False,
                "output": "",
                "error": str(e)
            }
    
    def _execute_gpio_command(self, command: str) -> Dict[str, Any]:
        """Execute GPIO control commands."""
        try:
            # Parse the command
            parts = command.split()
            if len(parts) < 3:
                raise ValueError("Invalid GPIO command")
            
            # Extract arguments
            gpio_command = parts[2]
            args = parts[3:]
            
            # Execute the GPIO script
            cmd = [sys.executable, str(self.gpio_script_path), gpio_command] + args
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            
            return {
                "success": result.returncode == 0,
                "output": result.stdout.strip(),
                "error": result.stderr.strip()
            }
        
        except Exception as e:
            logger.error(f"GPIO command execution failed: {e}")
            return {
                "success": False,
                "output": "",
                "error": str(e)
            }

class MockSSHServer:
    """Mock SSH server that simulates Raspberry Pi SSH functionality."""
    
    def __init__(self, host="localhost", port=2222):
        self.host = host
        self.port = port
        self.handler = MockSSHHandler()
        self.running = False
        self.server = None
        self.thread = None
    
    def start(self):
        """Start the mock SSH server."""
        try:
            # Create a simple TCP server that simulates SSH
            self.server = socketserver.TCPServer((self.host, self.port), self._handle_connection)
            self.running = True
            
            # Start server in a separate thread
            self.thread = threading.Thread(target=self._run_server, daemon=True)
            self.thread.start()
            
            logger.info(f"Mock Raspberry Pi SSH server started on {self.host}:{self.port}")
            return True
        
        except Exception as e:
            logger.error(f"Failed to start mock SSH server: {e}")
            return False
    
    def stop(self):
        """Stop the mock SSH server."""
        self.running = False
        if self.server:
            self.server.shutdown()
        logger.info("Mock Raspberry Pi SSH server stopped")
    
    def _run_server(self):
        """Run the server in a separate thread."""
        try:
            self.server.serve_forever()
        except Exception as e:
            logger.error(f"Server error: {e}")
    
    def _handle_connection(self, request, client_address):
        """Handle incoming SSH-like connections."""
        logger.info(f"Connection from {client_address}")
        
        # Simulate SSH handshake
        try:
            # Send SSH banner
            request.sendall(b"SSH-2.0-OpenSSH_8.0\n")
            
            # Simple command processing
            while self.running:
                try:
                    # Read command (simplified)
                    data = request.recv(1024)
                    if not data:
                        break
                    
                    command = data.decode().strip()
                    if command.lower() in ['exit', 'quit']:
                        break
                    
                    # Execute command
                    result = self.handler.execute_command(command)
                    
                    # Send response
                    response = {
                        "success": result["success"],
                        "output": result["output"],
                        "error": result["error"]
                    }
                    
                    response_data = json.dumps(response) + "\n"
                    request.sendall(response_data.encode())
                    
                    # Close connection after each command (simplified)
                    break
                
                except Exception as e:
                    logger.error(f"Error handling command: {e}")
                    break
        
        except Exception as e:
            logger.error(f"Connection error: {e}")
        finally:
            try:
                request.close()
            except:
                pass
            logger.info(f"Connection from {client_address} closed")

def main():
    """Main function to run the mock Raspberry Pi server."""
    print("🍓 Mock Raspberry Pi Server")
    print("=" * 40)
    print("This server simulates a Raspberry Pi for testing ARAS tools.")
    print("It provides SSH-like functionality and GPIO simulation.")
    print()
    
    # Create and start server
    server = MockSSHServer(host="localhost", port=2222)
    
    if server.start():
        print(f"✅ Server started successfully!")
        print(f"   Host: {server.host}")
        print(f"   Port: {server.port}")
        print()
        print("Configuration for ARAS:")
        print(f"   PI_HOST={server.host}")
        print(f"   PI_PORT={server.port}")
        print(f"   PI_USERNAME=pi")
        print(f"   PI_PASSWORD=raspberry")
        print(f"   PI_GPIO_ENABLED=true")
        print()
        print("Press Ctrl+C to stop the server...")
        
        try:
            # Keep the main thread alive
            while server.running:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n🛑 Stopping server...")
            server.stop()
            print("✅ Server stopped")
    else:
        print("❌ Failed to start server")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
