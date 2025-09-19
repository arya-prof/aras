"""
3D home visualization window using Three.js for device status display.
"""

import json
import asyncio
import time
from typing import Dict, List, Any, Optional
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTextEdit
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebChannel import QWebChannel
from PyQt6.QtCore import QObject, pyqtSlot

from ..config import settings


class HomeDataBridge(QObject):
    """Bridge between Python and JavaScript for home data."""
    
    data_updated = pyqtSignal()
    
    def __init__(self):
        super().__init__()
        self.home_data = {}
    
    @pyqtSlot(result=str)
    def get_home_data(self):
        """Get current home data as JSON string."""
        return json.dumps(self.home_data)
    
    @pyqtSlot(str)
    def update_home_data(self, data_json: str):
        """Update home data from JavaScript."""
        try:
            self.home_data = json.loads(data_json)
            self.data_updated.emit()
        except json.JSONDecodeError:
            pass
    
    def set_home_data(self, data: Dict[str, Any]):
        """Set home data from Python."""
        self.home_data = data
        self.data_updated.emit()


class HomeVisualizationWindow(QWidget):
    """3D home visualization window with device status display."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Home Status - 3D Visualization")
        self.setGeometry(100, 100, 1000, 700)
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowStaysOnTopHint)
        
        # Setup data bridge first
        self.data_bridge = HomeDataBridge()
        self.data_bridge.data_updated.connect(self.on_data_updated)
        
        # Setup UI
        self.setup_ui()
        
        # Setup update timer (moved to main thread)
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_home_data)
        self.update_timer.start(5000)  # Update every 5 seconds
        
        # Load initial data
        self.update_home_data()
    
    def setup_ui(self):
        """Setup the user interface."""
        layout = QVBoxLayout(self)
        
        # Header
        header_layout = QHBoxLayout()
        self.title_label = QLabel("Home Status - 3D Visualization")
        self.title_label.setStyleSheet("font-size: 18px; font-weight: bold; margin: 10px;")
        header_layout.addWidget(self.title_label)
        
        header_layout.addStretch()
        
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self.update_home_data)
        header_layout.addWidget(self.refresh_button)
        
        self.close_button = QPushButton("Close")
        self.close_button.clicked.connect(self.close)
        header_layout.addWidget(self.close_button)
        
        layout.addLayout(header_layout)
        
        # 3D Viewer
        self.web_view = QWebEngineView()
        self.setup_web_channel()
        self.load_3d_viewer()
        layout.addWidget(self.web_view)
        
        # Status panel
        status_layout = QHBoxLayout()
        
        self.status_text = QTextEdit()
        self.status_text.setMaximumHeight(150)
        self.status_text.setReadOnly(True)
        self.status_text.setPlaceholderText("Device status will appear here...")
        status_layout.addWidget(self.status_text)
        
        layout.addLayout(status_layout)
    
    def setup_web_channel(self):
        """Setup WebChannel for communication between Python and JavaScript."""
        self.channel = QWebChannel()
        self.channel.registerObject("homeDataBridge", self.data_bridge)
        self.web_view.page().setWebChannel(self.channel)
    
    def load_3d_viewer(self):
        """Load the 3D viewer HTML content."""
        html_content = self.generate_3d_viewer_html()
        self.web_view.setHtml(html_content)
    
    def generate_3d_viewer_html(self) -> str:
        """Generate HTML content with Three.js 3D home visualization."""
        return """
        <!DOCTYPE html>
        <html>
        <head>
            <title>3D Home Visualization</title>
            <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
            <script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/controls/OrbitControls.js"></script>
            <style>
                body { margin: 0; padding: 0; background: #1a1a1a; }
                #container { width: 100%; height: 100vh; }
                #info { position: absolute; top: 10px; left: 10px; color: white; font-family: Arial; }
                .device-info { background: rgba(0,0,0,0.7); padding: 10px; margin: 5px; border-radius: 5px; }
            </style>
        </head>
        <body>
            <div id="container"></div>
            <div id="info">
                <h3>Home Status</h3>
                <div id="device-list"></div>
            </div>
            
            <script>
                let scene, camera, renderer, controls;
                let homeGroup, devices = {};
                let homeData = {};
                
                function init() {
                    // Scene setup
                    scene = new THREE.Scene();
                    scene.background = new THREE.Color(0x1a1a1a);
                    
                    // Camera setup
                    camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000);
                    camera.position.set(10, 10, 10);
                    
                    // Renderer setup
                    renderer = new THREE.WebGLRenderer({ antialias: true });
                    renderer.setSize(window.innerWidth, window.innerHeight);
                    renderer.shadowMap.enabled = true;
                    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
                    document.getElementById('container').appendChild(renderer.domElement);
                    
                    // Controls
                    controls = new THREE.OrbitControls(camera, renderer.domElement);
                    controls.enableDamping = true;
                    controls.dampingFactor = 0.05;
                    
                    // Lighting
                    const ambientLight = new THREE.AmbientLight(0x404040, 0.6);
                    scene.add(ambientLight);
                    
                    const directionalLight = new THREE.DirectionalLight(0xffffff, 0.8);
                    directionalLight.position.set(10, 10, 5);
                    directionalLight.castShadow = true;
                    directionalLight.shadow.mapSize.width = 2048;
                    directionalLight.shadow.mapSize.height = 2048;
                    scene.add(directionalLight);
                    
                    // Create home structure
                    createHome();
                    
                    // Start render loop
                    animate();
                    
                    // Handle window resize
                    window.addEventListener('resize', onWindowResize, false);
                }
                
                function createHome() {
                    homeGroup = new THREE.Group();
                    
                    // Floor
                    const floorGeometry = new THREE.PlaneGeometry(20, 20);
                    const floorMaterial = new THREE.MeshLambertMaterial({ color: 0x8B4513 });
                    const floor = new THREE.Mesh(floorGeometry, floorMaterial);
                    floor.rotation.x = -Math.PI / 2;
                    floor.receiveShadow = true;
                    homeGroup.add(floor);
                    
                    // Walls
                    const wallMaterial = new THREE.MeshLambertMaterial({ color: 0xf0f0f0 });
                    
                    // Front wall
                    const frontWallGeometry = new THREE.PlaneGeometry(20, 8);
                    const frontWall = new THREE.Mesh(frontWallGeometry, wallMaterial);
                    frontWall.position.set(0, 4, -10);
                    homeGroup.add(frontWall);
                    
                    // Back wall
                    const backWall = new THREE.Mesh(frontWallGeometry, wallMaterial);
                    backWall.position.set(0, 4, 10);
                    homeGroup.add(backWall);
                    
                    // Left wall
                    const leftWallGeometry = new THREE.PlaneGeometry(20, 8);
                    const leftWall = new THREE.Mesh(leftWallGeometry, wallMaterial);
                    leftWall.position.set(-10, 4, 0);
                    leftWall.rotation.y = Math.PI / 2;
                    homeGroup.add(leftWall);
                    
                    // Right wall
                    const rightWall = new THREE.Mesh(leftWallGeometry, wallMaterial);
                    rightWall.position.set(10, 4, 0);
                    rightWall.rotation.y = Math.PI / 2;
                    homeGroup.add(rightWall);
                    
                    scene.add(homeGroup);
                }
                
                function createDevice(type, position, status, name) {
                    let geometry, material, device;
                    
                    switch(type) {
                        case 'light':
                            geometry = new THREE.SphereGeometry(0.5, 16, 16);
                            material = new THREE.MeshLambertMaterial({ 
                                color: status === 'on' ? 0xffff00 : 0x666666,
                                emissive: status === 'on' ? 0x444400 : 0x000000
                            });
                            break;
                        case 'door':
                            geometry = new THREE.BoxGeometry(1, 2, 0.2);
                            material = new THREE.MeshLambertMaterial({ 
                                color: status === 'locked' ? 0x00ff00 : 0xff0000
                            });
                            break;
                        case 'sensor':
                            geometry = new THREE.CylinderGeometry(0.3, 0.3, 0.5, 8);
                            material = new THREE.MeshLambertMaterial({ 
                                color: status === 'active' ? 0x00ff00 : 0xff0000
                            });
                            break;
                        case 'thermostat':
                            geometry = new THREE.BoxGeometry(0.8, 1.2, 0.3);
                            material = new THREE.MeshLambertMaterial({ 
                                color: status === 'heating' ? 0xff4444 : 
                                       status === 'cooling' ? 0x4444ff : 0x888888
                            });
                            break;
                        default:
                            geometry = new THREE.BoxGeometry(0.5, 0.5, 0.5);
                            material = new THREE.MeshLambertMaterial({ color: 0x888888 });
                    }
                    
                    device = new THREE.Mesh(geometry, material);
                    device.position.set(position.x, position.y, position.z);
                    device.castShadow = true;
                    device.userData = { type, status, name };
                    
                    homeGroup.add(device);
                    devices[name] = device;
                    
                    return device;
                }
                
                function updateDevices(deviceData) {
                    // Clear existing devices
                    Object.values(devices).forEach(device => {
                        homeGroup.remove(device);
                    });
                    devices = {};
                    
                    // Create new devices
                    if (deviceData && deviceData.devices) {
                        deviceData.devices.forEach(device => {
                            createDevice(
                                device.type,
                                { x: device.x || 0, y: device.y || 1, z: device.z || 0 },
                                device.status,
                                device.name
                            );
                        });
                    }
                    
                    updateDeviceList(deviceData);
                }
                
                function updateDeviceList(deviceData) {
                    const deviceList = document.getElementById('device-list');
                    deviceList.innerHTML = '';
                    
                    if (deviceData && deviceData.devices) {
                        deviceData.devices.forEach(device => {
                            const deviceDiv = document.createElement('div');
                            deviceDiv.className = 'device-info';
                            deviceDiv.innerHTML = `
                                <strong>${device.name}</strong><br>
                                Type: ${device.type}<br>
                                Status: <span style="color: ${getStatusColor(device.status)}">${device.status}</span>
                            `;
                            deviceList.appendChild(deviceDiv);
                        });
                    }
                }
                
                function getStatusColor(status) {
                    switch(status) {
                        case 'on': case 'active': case 'locked': case 'heating': case 'cooling':
                            return '#00ff00';
                        case 'off': case 'inactive': case 'unlocked':
                            return '#ff0000';
                        default:
                            return '#ffff00';
                    }
                }
                
                function animate() {
                    requestAnimationFrame(animate);
                    controls.update();
                    renderer.render(scene, camera);
                }
                
                function onWindowResize() {
                    camera.aspect = window.innerWidth / window.innerHeight;
                    camera.updateProjectionMatrix();
                    renderer.setSize(window.innerWidth, window.innerHeight);
                }
                
                // WebChannel communication
                if (typeof homeDataBridge !== 'undefined') {
                    homeDataBridge.data_updated.connect(function() {
                        const data = JSON.parse(homeDataBridge.get_home_data());
                        updateDevices(data);
                    });
                }
                
                // Initialize when page loads
                window.addEventListener('load', init);
            </script>
        </body>
        </html>
        """
    
    def update_home_data(self):
        """Update home data from the agent."""
        try:
            # Try to get real data from Home Assistant
            real_data = self.get_real_home_data()
            
            if real_data:
                self.data_bridge.set_home_data(real_data)
                self.update_status_text(real_data)
            else:
                # Fallback to sample data
                sample_data = self.generate_sample_home_data()
                # Add a note that this is sample data
                sample_data['note'] = 'Sample data - Home Assistant not configured'
                self.data_bridge.set_home_data(sample_data)
                self.update_status_text(sample_data)
        except Exception as e:
            print(f"Error updating home data: {e}")
            # Fallback to sample data
            sample_data = self.generate_sample_home_data()
            self.data_bridge.set_home_data(sample_data)
            self.update_status_text(sample_data)
    
    def get_real_home_data(self) -> Optional[Dict[str, Any]]:
        """Get real home data from Home Assistant or other sources."""
        try:
            # Import home tools
            from ..tools.home_tools import DeviceControlTool
            from ..config import settings
            
            # Check if Home Assistant is configured
            if not settings.ha_base_url or not settings.ha_token or settings.ha_token == "your_home_assistant_token":
                # Home Assistant not configured, return None to use sample data
                return None
            
            # Create device control tool
            device_tool = DeviceControlTool()
            
            # Initialize the tool first
            asyncio.run(device_tool.initialize())
            
            # Get all devices
            devices_data = asyncio.run(device_tool._list_devices())
            
            if not devices_data or not isinstance(devices_data, list):
                return None
            
            # Convert Home Assistant data to our format
            devices = []
            for device in devices_data:
                # Ensure device is a dictionary and has required fields
                if not isinstance(device, dict):
                    continue
                    
                entity_id = device.get('entity_id', '')
                state = device.get('state', 'unknown')
                attributes = device.get('attributes', {})
                
                if not entity_id:
                    continue
                
                # Determine device type and position
                device_type = self._determine_device_type(entity_id)
                position = self._get_device_position(entity_id, device_type)
                
                devices.append({
                    'name': attributes.get('friendly_name', entity_id),
                    'type': device_type,
                    'status': state,
                    'x': position['x'],
                    'y': position['y'], 
                    'z': position['z'],
                    'entity_id': entity_id,
                    'attributes': attributes
                })
            
            return {
                'devices': devices,
                'timestamp': int(time.time()),
                'source': 'home_assistant'
            }
            
        except Exception as e:
            # Don't print error messages for connection issues - just fall back to sample data
            if any(msg in str(e).lower() for msg in [
                "cannot connect to host", 
                "refused the network connection",
                "home assistant not configured",
                "connection refused",
                "timeout",
                "network error",
                "failed to list devices"
            ]):
                # This is expected when Home Assistant is not running or configured
                pass
            else:
                print(f"Error getting real home data: {e}")
            return None
    
    def _determine_device_type(self, entity_id: str) -> str:
        """Determine device type from entity ID."""
        if entity_id.startswith('light.'):
            return 'light'
        elif entity_id.startswith('switch.'):
            return 'light'  # Treat switches as lights for visualization
        elif entity_id.startswith('lock.'):
            return 'door'
        elif entity_id.startswith('binary_sensor.'):
            return 'sensor'
        elif entity_id.startswith('sensor.'):
            return 'sensor'
        elif entity_id.startswith('climate.'):
            return 'thermostat'
        elif entity_id.startswith('fan.'):
            return 'thermostat'  # Treat fans as climate devices
        else:
            return 'sensor'  # Default fallback
    
    def _get_device_position(self, entity_id: str, device_type: str) -> Dict[str, float]:
        """Get device position in 3D space."""
        # This would ideally use room mapping or configuration
        # For now, distribute devices in a grid pattern
        
        # Simple hash-based positioning for consistency
        hash_val = hash(entity_id)
        
        # Map to 3D coordinates
        x = ((hash_val % 20) - 10) * 0.8  # -8 to 8
        z = (((hash_val // 20) % 20) - 10) * 0.8  # -8 to 8
        y = 1.5 if device_type in ['light', 'thermostat'] else 1.0  # Height
        
        return {'x': x, 'y': y, 'z': z}
    
    def generate_sample_home_data(self) -> Dict[str, Any]:
        """Generate sample home data for demonstration."""
        import random
        import time
        
        # Simulate some randomness in device states
        current_time = int(time.time())
        
        return {
            "devices": [
                {
                    "name": "Living Room Light",
                    "type": "light",
                    "status": "on" if (current_time % 10) < 5 else "off",
                    "x": -5, "y": 1.5, "z": -5
                },
                {
                    "name": "Kitchen Light",
                    "type": "light", 
                    "status": "on" if (current_time % 8) < 4 else "off",
                    "x": 5, "y": 1.5, "z": -5
                },
                {
                    "name": "Front Door",
                    "type": "door",
                    "status": "locked" if (current_time % 15) < 10 else "unlocked",
                    "x": 0, "y": 1, "z": -10
                },
                {
                    "name": "Motion Sensor",
                    "type": "sensor",
                    "status": "active" if (current_time % 6) < 3 else "inactive",
                    "x": 0, "y": 2, "z": 0
                },
                {
                    "name": "Thermostat",
                    "type": "thermostat",
                    "status": "heating" if (current_time % 12) < 6 else "cooling",
                    "x": 8, "y": 1.5, "z": 8
                },
                {
                    "name": "Bedroom Light",
                    "type": "light",
                    "status": "off" if (current_time % 20) < 15 else "on",
                    "x": -8, "y": 1.5, "z": 8
                }
            ],
            "timestamp": current_time
        }
    
    def update_status_text(self, data: Dict[str, Any]):
        """Update the status text panel."""
        if not data or 'devices' not in data:
            return
        
        status_text = f"Home Status - Last Updated: {data.get('timestamp', 'Unknown')}\n\n"
        
        for device in data['devices']:
            status_icon = "🟢" if device['status'] in ['on', 'active', 'locked', 'heating', 'cooling'] else "🔴"
            status_text += f"{status_icon} {device['name']}: {device['status']}\n"
        
        self.status_text.setPlainText(status_text)
    
    def on_data_updated(self):
        """Handle data updates from the bridge."""
        # This is called when JavaScript updates the data
        pass
