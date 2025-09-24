#!/usr/bin/env python3
"""
Mock Raspberry Pi Server for ARAS Testing
Simulates Raspberry Pi functionality for testing the Raspberry Pi Control Tool.
"""

import json
import socket
import threading
import time
import sys
from pathlib import Path

class MockRaspberryPiServer:
    """Mock Raspberry Pi server that works with paramiko."""
    
    def __init__(self, host="localhost", port=2222):
        self.host = host
        self.port = port
        self.running = False
        self.socket = None
        self.gpio_pins = {}
        
    def start(self):
        """Start the mock server."""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.socket.bind((self.host, self.port))
            self.socket.listen(5)
            self.running = True
            
            print(f"✅ Mock Raspberry Pi server started on {self.host}:{self.port}")
            
            while self.running:
                try:
                    client_socket, address = self.socket.accept()
                    print(f"📡 Connection from {address}")
                    
                    # Handle client in a separate thread
                    client_thread = threading.Thread(
                        target=self.handle_client,
                        args=(client_socket, address),
                        daemon=True
                    )
                    client_thread.start()
                    
                except Exception as e:
                    if self.running:
                        print(f"❌ Server error: {e}")
                    break
                    
        except Exception as e:
            print(f"❌ Failed to start server: {e}")
            return False
        
        return True
    
    def stop(self):
        """Stop the mock server."""
        self.running = False
        if self.socket:
            self.socket.close()
        print("🛑 Mock server stopped")
    
    def handle_client(self, client_socket, address):
        """Handle a client connection - keep it open for multiple commands."""
        try:
            # Send welcome message
            client_socket.send(b"Mock Raspberry Pi Server Ready\n")
            
            while self.running:
                try:
                    # Receive command
                    data = client_socket.recv(1024)
                    if not data:
                        break
                    
                    command = data.decode().strip()
                    if not command:
                        continue
                    
                    # Handle special commands
                    if command.lower() in ['exit', 'quit', 'close']:
                        break
                    
                    print(f"🔧 Executing: {command}")
                    
                    # Execute command and get result
                    result = self.execute_command(command)
                    
                    # Send response
                    response = json.dumps(result) + "\n"
                    client_socket.send(response.encode())
                    
                except Exception as e:
                    print(f"❌ Error handling command: {e}")
                    break
                    
        except Exception as e:
            print(f"❌ Client error: {e}")
        finally:
            client_socket.close()
            print(f"📡 Client {address} disconnected")
    
    def execute_command(self, command):
        """Execute a command and return result."""
        try:
            if command.startswith("echo "):
                message = command[5:].strip('"\'')
                return {
                    "success": True,
                    "output": message,
                    "error": ""
                }
            
            elif command == "vcgencmd measure_temp":
                temp = 45.2 + (hash(command) % 10) - 5  # Simulate temperature variation
                return {
                    "success": True,
                    "output": f"temp={temp:.1f}'C",
                    "error": ""
                }
            
            elif command == "free -h":
                return {
                    "success": True,
                    "output": """              total        used        free      shared  buff/cache   available
Mem:           3.8G        1.2G        2.6G         45M        456M        2.3G
Swap:            0B          0B          0B""",
                    "error": ""
                }
            
            elif command == "df -h /":
                return {
                    "success": True,
                    "output": """Filesystem      Size  Used Avail Use% Mounted on
/dev/root        29G  8.5G   20G  31% /
devtmpfs        1.9G     0  1.9G   0% /dev
tmpfs           1.9G  4.0K  1.9G   1% /dev/shm""",
                    "error": ""
                }
            
            elif command == "uptime":
                uptime = "up 2 days, 14:32:15"
                return {
                    "success": True,
                    "output": uptime,
                    "error": ""
                }
            
            elif command.startswith("python3 /tmp/gpio_control.py"):
                return self.execute_gpio_command(command)
            
            else:
                return {
                    "success": True,
                    "output": f"Mock execution of: {command}",
                    "error": ""
                }
        
        except Exception as e:
            return {
                "success": False,
                "output": "",
                "error": str(e)
            }
    
    def execute_gpio_command(self, command):
        """Execute GPIO commands."""
        try:
            parts = command.split()
            if len(parts) < 3:
                return {"success": False, "output": "", "error": "Invalid GPIO command"}
            
            gpio_cmd = parts[2]
            
            if gpio_cmd == "set_pin" and len(parts) >= 5:
                pin = int(parts[3])
                state = int(parts[4])
                self.gpio_pins[pin] = state
                return {
                    "success": True,
                    "output": json.dumps({"pin": pin, "state": state}),
                    "error": ""
                }
            
            elif gpio_cmd == "read_pin" and len(parts) >= 4:
                pin = int(parts[3])
                state = self.gpio_pins.get(pin, 0)
                return {
                    "success": True,
                    "output": json.dumps({"pin": pin, "state": state}),
                    "error": ""
                }
            
            elif gpio_cmd == "set_pwm" and len(parts) >= 5:
                pin = int(parts[3])
                duty_cycle = float(parts[4])
                frequency = int(parts[5]) if len(parts) > 5 else 1000
                return {
                    "success": True,
                    "output": json.dumps({"pin": pin, "duty_cycle": duty_cycle, "frequency": frequency}),
                    "error": ""
                }
            
            else:
                return {
                    "success": False,
                    "output": "",
                    "error": "Unknown GPIO command"
                }
        
        except Exception as e:
            return {
                "success": False,
                "output": "",
                "error": str(e)
            }

def main():
    """Main function to run the mock Raspberry Pi server."""
    print("🍓 Mock Raspberry Pi Server")
    print("=" * 40)
    print("This server simulates a Raspberry Pi for testing ARAS tools.")
    print("It provides SSH-like functionality and GPIO simulation.")
    print()
    
    # Create and start server
    server = MockRaspberryPiServer(host="localhost", port=2222)
    
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