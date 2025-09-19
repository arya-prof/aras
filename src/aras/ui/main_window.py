"""
Main window for Aras Agent Qt UI.
"""

import json
import asyncio
import websockets
from datetime import datetime
from typing import Optional, Dict, Any

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, 
    QLineEdit, QPushButton, QLabel, QStatusBar, QSplitter, QTabWidget,
    QTreeWidget, QTreeWidgetItem, QGroupBox, QGridLayout, QProgressBar
)
from PyQt6.QtCore import QTimer, QThread, pyqtSignal, QObject, QUrl
from PyQt6.QtGui import QFont, QPixmap, QIcon
from PyQt6.QtWebEngineWidgets import QWebEngineView

from ..config import settings
from ..models import MessageType


class WebSocketClient(QObject):
    """WebSocket client for communication with the agent server."""
    
    message_received = pyqtSignal(dict)
    connected = pyqtSignal()
    disconnected = pyqtSignal()
    error_occurred = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.websocket = None
        self.running = False
        self.session_id = None
    
    async def connect(self):
        """Connect to WebSocket server."""
        try:
            self.websocket = await websockets.connect(f"ws://localhost:{settings.http_port}/ws")
            self.running = True
            self.session_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            self.connected.emit()
            
            # Start listening for messages
            asyncio.create_task(self._listen())
            
        except Exception as e:
            self.error_occurred.emit(f"Connection error: {e}")
    
    async def disconnect(self):
        """Disconnect from WebSocket server."""
        self.running = False
        if self.websocket:
            await self.websocket.close()
        self.disconnected.emit()
    
    async def _listen(self):
        """Listen for incoming messages."""
        try:
            while self.running and self.websocket:
                message = await self.websocket.recv()
                data = json.loads(message)
                self.message_received.emit(data)
        except Exception as e:
            if self.running:
                self.error_occurred.emit(f"Listen error: {e}")
    
    async def send_message(self, message_type: str, content: str, **kwargs):
        """Send a message to the server."""
        if self.websocket and self.running:
            message = {
                "type": message_type,
                "content": content,
                "session_id": self.session_id,
                **kwargs
            }
            await self.websocket.send(json.dumps(message))


class WebSocketThread(QThread):
    """Thread for WebSocket communication."""
    
    def __init__(self):
        super().__init__()
        self.client = WebSocketClient()
        self.loop = None
    
    def run(self):
        """Run the WebSocket client."""
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self.client.connect())
    
    def stop(self):
        """Stop the WebSocket client."""
        if self.loop:
            self.loop.create_task(self.client.disconnect())
            self.loop.stop()


class MainWindow(QMainWindow):
    """Main window for Aras Agent."""
    
    def __init__(self):
        super().__init__()
        self.websocket_thread = None
        self.setup_ui()
        self.setup_websocket()
    
    def setup_ui(self):
        """Setup the user interface."""
        self.setWindowTitle(f"{settings.agent_name} Agent")
        self.setGeometry(100, 100, 1200, 800)
        
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        main_layout = QHBoxLayout(central_widget)
        
        # Create splitter
        splitter = QSplitter()
        main_layout.addWidget(splitter)
        
        # Left panel - Chat and controls
        left_panel = self.create_left_panel()
        splitter.addWidget(left_panel)
        
        # Right panel - Tools and status
        right_panel = self.create_right_panel()
        splitter.addWidget(right_panel)
        
        # Set splitter proportions
        splitter.setSizes([800, 400])
        
        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Disconnected")
        
        # Apply theme
        self.apply_theme()
    
    def create_left_panel(self) -> QWidget:
        """Create the left panel with chat interface."""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # Chat area
        chat_group = QGroupBox("Chat")
        chat_layout = QVBoxLayout(chat_group)
        
        # Messages display
        self.messages_display = QTextEdit()
        self.messages_display.setReadOnly(True)
        self.messages_display.setFont(QFont("Consolas", 10))
        chat_layout.addWidget(self.messages_display)
        
        # Input area
        input_layout = QHBoxLayout()
        self.message_input = QLineEdit()
        self.message_input.setPlaceholderText("Type your message here...")
        self.message_input.returnPressed.connect(self.send_message)
        input_layout.addWidget(self.message_input)
        
        self.send_button = QPushButton("Send")
        self.send_button.clicked.connect(self.send_message)
        input_layout.addWidget(self.send_button)
        
        chat_layout.addLayout(input_layout)
        layout.addWidget(chat_group)
        
        # 3D Map viewer
        map_group = QGroupBox("3D Home Map")
        map_layout = QVBoxLayout(map_group)
        
        self.map_viewer = QWebEngineView()
        self.map_viewer.setUrl(QUrl("about:blank"))  # Placeholder
        map_layout.addWidget(self.map_viewer)
        
        layout.addWidget(map_group)
        
        return panel
    
    def create_right_panel(self) -> QWidget:
        """Create the right panel with tools and status."""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # Tabs
        tab_widget = QTabWidget()
        layout.addWidget(tab_widget)
        
        # Tools tab
        tools_tab = self.create_tools_tab()
        tab_widget.addTab(tools_tab, "Tools")
        
        # Status tab
        status_tab = self.create_status_tab()
        tab_widget.addTab(status_tab, "Status")
        
        # Settings tab
        settings_tab = self.create_settings_tab()
        tab_widget.addTab(settings_tab, "Settings")
        
        return panel
    
    def create_tools_tab(self) -> QWidget:
        """Create the tools tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # System tools
        system_group = QGroupBox("System Tools")
        system_layout = QVBoxLayout(system_group)
        
        self.system_tools_tree = QTreeWidget()
        self.system_tools_tree.setHeaderLabels(["Tool", "Status", "Description"])
        system_layout.addWidget(self.system_tools_tree)
        
        layout.addWidget(system_group)
        
        # Home tools
        home_group = QGroupBox("Smart Home Tools")
        home_layout = QVBoxLayout(home_group)
        
        self.home_tools_tree = QTreeWidget()
        self.home_tools_tree.setHeaderLabels(["Tool", "Status", "Description"])
        home_layout.addWidget(self.home_tools_tree)
        
        layout.addWidget(home_group)
        
        # Web tools
        web_group = QGroupBox("Web Tools")
        web_layout = QVBoxLayout(web_group)
        
        self.web_tools_tree = QTreeWidget()
        self.web_tools_tree.setHeaderLabels(["Tool", "Status", "Description"])
        web_layout.addWidget(self.web_tools_tree)
        
        layout.addWidget(web_group)
        
        return tab
    
    def create_status_tab(self) -> QWidget:
        """Create the status tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Connection status
        conn_group = QGroupBox("Connection Status")
        conn_layout = QGridLayout(conn_group)
        
        conn_layout.addWidget(QLabel("Status:"), 0, 0)
        self.connection_status = QLabel("Disconnected")
        self.connection_status.setStyleSheet("color: red; font-weight: bold;")
        conn_layout.addWidget(self.connection_status, 0, 1)
        
        conn_layout.addWidget(QLabel("Session ID:"), 1, 0)
        self.session_id_label = QLabel("None")
        conn_layout.addWidget(self.session_id_label, 1, 1)
        
        layout.addWidget(conn_group)
        
        # Agent status
        agent_group = QGroupBox("Agent Status")
        agent_layout = QGridLayout(agent_group)
        
        agent_layout.addWidget(QLabel("Agent Name:"), 0, 0)
        agent_layout.addWidget(QLabel(settings.agent_name), 0, 1)
        
        agent_layout.addWidget(QLabel("Active:"), 1, 0)
        self.agent_active = QLabel("No")
        agent_layout.addWidget(self.agent_active, 1, 1)
        
        agent_layout.addWidget(QLabel("Last Activity:"), 2, 0)
        self.last_activity = QLabel("Never")
        agent_layout.addWidget(self.last_activity, 2, 1)
        
        layout.addWidget(agent_group)
        
        # System resources
        resources_group = QGroupBox("System Resources")
        resources_layout = QVBoxLayout(resources_group)
        
        resources_layout.addWidget(QLabel("CPU Usage:"))
        self.cpu_progress = QProgressBar()
        resources_layout.addWidget(self.cpu_progress)
        
        resources_layout.addWidget(QLabel("Memory Usage:"))
        self.memory_progress = QProgressBar()
        resources_layout.addWidget(self.memory_progress)
        
        layout.addWidget(resources_group)
        
        return tab
    
    def create_settings_tab(self) -> QWidget:
        """Create the settings tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Connection settings
        conn_group = QGroupBox("Connection Settings")
        conn_layout = QGridLayout(conn_group)
        
        conn_layout.addWidget(QLabel("WebSocket Port:"), 0, 0)
        self.ws_port_input = QLineEdit(str(settings.websocket_port))
        conn_layout.addWidget(self.ws_port_input, 0, 1)
        
        conn_layout.addWidget(QLabel("HTTP Port:"), 1, 0)
        self.http_port_input = QLineEdit(str(settings.http_port))
        conn_layout.addWidget(self.http_port_input, 1, 1)
        
        layout.addWidget(conn_group)
        
        # AI settings
        ai_group = QGroupBox("AI Settings")
        ai_layout = QGridLayout(ai_group)
        
        ai_layout.addWidget(QLabel("Model:"), 0, 0)
        self.model_input = QLineEdit(settings.openai_model)
        conn_layout.addWidget(self.model_input, 0, 1)
        
        layout.addWidget(ai_group)
        
        # Apply button
        apply_button = QPushButton("Apply Settings")
        apply_button.clicked.connect(self.apply_settings)
        layout.addWidget(apply_button)
        
        return tab
    
    def setup_websocket(self):
        """Setup WebSocket connection."""
        self.websocket_thread = WebSocketThread()
        self.websocket_thread.client.connected.connect(self.on_connected)
        self.websocket_thread.client.disconnected.connect(self.on_disconnected)
        self.websocket_thread.client.message_received.connect(self.on_message_received)
        self.websocket_thread.client.error_occurred.connect(self.on_error)
        self.websocket_thread.start()
    
    def on_connected(self):
        """Handle WebSocket connection."""
        self.connection_status.setText("Connected")
        self.connection_status.setStyleSheet("color: green; font-weight: bold;")
        self.session_id_label.setText(self.websocket_thread.client.session_id)
        self.status_bar.showMessage("Connected to agent server")
        self.add_message("Connected to agent server", "system")
    
    def on_disconnected(self):
        """Handle WebSocket disconnection."""
        self.connection_status.setText("Disconnected")
        self.connection_status.setStyleSheet("color: red; font-weight: bold;")
        self.status_bar.showMessage("Disconnected from agent server")
        self.add_message("Disconnected from agent server", "system")
    
    def on_message_received(self, data: Dict[str, Any]):
        """Handle received message."""
        message_type = data.get("type", "unknown")
        content = data.get("content", "")
        
        if message_type == "agent_response":
            self.add_message(content, "agent")
        elif message_type == "system":
            self.add_message(content, "system")
        elif message_type == "error":
            self.add_message(f"Error: {content}", "error")
        else:
            self.add_message(f"[{message_type}] {content}", "system")
    
    def on_error(self, error: str):
        """Handle WebSocket error."""
        self.add_message(f"Error: {error}", "error")
        self.status_bar.showMessage(f"Error: {error}")
    
    def add_message(self, content: str, message_type: str):
        """Add a message to the chat display."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        if message_type == "user":
            prefix = f"[{timestamp}] You: "
            color = "blue"
        elif message_type == "agent":
            prefix = f"[{timestamp}] {settings.agent_name}: "
            color = "green"
        elif message_type == "system":
            prefix = f"[{timestamp}] System: "
            color = "gray"
        elif message_type == "error":
            prefix = f"[{timestamp}] Error: "
            color = "red"
        else:
            prefix = f"[{timestamp}] {message_type}: "
            color = "black"
        
        self.messages_display.append(f'<span style="color: {color};">{prefix}{content}</span>')
    
    def send_message(self):
        """Send a message to the agent."""
        message = self.message_input.text().strip()
        if message and self.websocket_thread and self.websocket_thread.client.websocket:
            self.add_message(message, "user")
            self.message_input.clear()
            
            # Send via WebSocket
            asyncio.create_task(self.websocket_thread.client.send_message(
                "user_input", message, input_type="text"
            ))
    
    def apply_settings(self):
        """Apply settings changes."""
        # This would update settings and reconnect
        self.add_message("Settings applied", "system")
    
    def apply_theme(self):
        """Apply the UI theme."""
        if settings.ui_theme == "dark":
            self.setStyleSheet("""
                QMainWindow { background-color: #2b2b2b; color: #ffffff; }
                QGroupBox { font-weight: bold; border: 2px solid #555555; border-radius: 5px; margin: 5px; }
                QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px 0 5px; }
                QPushButton { background-color: #404040; border: 1px solid #555555; padding: 5px; border-radius: 3px; }
                QPushButton:hover { background-color: #505050; }
                QLineEdit { background-color: #404040; border: 1px solid #555555; padding: 5px; border-radius: 3px; }
                QTextEdit { background-color: #404040; border: 1px solid #555555; }
                QTreeWidget { background-color: #404040; border: 1px solid #555555; }
            """)
    
    def closeEvent(self, event):
        """Handle window close event."""
        if self.websocket_thread:
            self.websocket_thread.stop()
            self.websocket_thread.wait()
        event.accept()
