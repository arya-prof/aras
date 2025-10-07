"""
Main PyQt6 application for 3D and 2D home visualization.
"""

import sys
import asyncio
import logging
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QLabel, QStatusBar, QPushButton, QGridLayout, QSizePolicy, QTabWidget,
                            QDialog, QCheckBox, QSpinBox, QComboBox, QGroupBox)
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal, QSize, QPoint
from PyQt6.QtGui import QAction, QIcon, QPixmap, QPainter, QFont

try:
    from .home_3d_viewer import Home3DViewer
    from .home_2d_viewer import Home2DViewer
except ImportError:
    # When running directly, use absolute imports
    from home_3d_viewer import Home3DViewer
    from home_2d_viewer import Home2DViewer

# Import Arduino Bluetooth tool
try:
    from ..tools.arduino_bluetooth_tool import ArduinoBluetoothTool
    ARDUINO_TOOL_AVAILABLE = True
except ImportError:
    ARDUINO_TOOL_AVAILABLE = False

logger = logging.getLogger(__name__)


class ArduinoToolThread(QThread):
    """Thread for running Arduino tool operations without blocking the UI."""
    
    connection_status_changed = pyqtSignal(bool, str)  # connected, status
    device_state_changed = pyqtSignal(str, bool)  # device_id, state
    
    def __init__(self, arduino_tool):
        super().__init__()
        self.arduino_tool = arduino_tool
        self.running = True
    
    def run(self):
        """Run the Arduino tool in a separate thread."""
        try:
            # Initialize the Arduino tool
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # Setup the tool
            loop.run_until_complete(self.arduino_tool._setup_resources())
            
            # Check if tool is enabled
            if self.arduino_tool.enabled:
                self.connection_status_changed.emit(True, "Connected")
                logger.info("Arduino tool connected successfully")
            else:
                self.connection_status_changed.emit(False, "Disconnected - Tool disabled")
                logger.warning("Arduino tool is disabled")
            
            # Keep the thread alive and monitor connection
            while self.running:
                if self.arduino_tool.enabled and self.arduino_tool.client and self.arduino_tool.client.is_connected:
                    # Tool is connected
                    pass
                else:
                    # Tool is disconnected
                    self.connection_status_changed.emit(False, "Disconnected")
                
                # Sleep for a bit to avoid busy waiting
                self.msleep(1000)
                
        except Exception as e:
            logger.error(f"Arduino tool thread error: {e}")
            self.connection_status_changed.emit(False, f"Error: {str(e)}")
        finally:
            # Cleanup
            if self.arduino_tool:
                try:
                    loop.run_until_complete(self.arduino_tool._cleanup_resources())
                except:
                    pass
    
    def stop(self):
        """Stop the thread."""
        self.running = False
        self.quit()
        self.wait()


class HomeViewerApp(QMainWindow):
    """Main application window for home visualization."""
    
    def __init__(self, arduino_tool=None):
        super().__init__()
        
        # Window properties
        self.setWindowTitle("ARAS Home Viewer - 3D & 2D Visualization")
        self.setGeometry(100, 100, 1400, 900)
        
        # Initialize Arduino tool (use provided instance or create new one)
        self.arduino_tool = arduino_tool
        self.arduino_connected = False
        self.arduino_connection_status = "Disconnected"
        
        # Initialize UI
        self.init_ui()
        self.setup_connections()
        self.setup_status_bar()
        
        # Set frameless window
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        
        # Setup keyboard shortcuts
        self.setup_shortcuts()
        
        # State
        self.sync_views = True
        self.current_room = None
        
        # Device states - Updated to match Arduino tool (L1, L2, RING)
        self.device_states = {"L1": False, "L2": False, "RING": False}  # Real Arduino devices
        self.light_states = self.device_states  # Keep compatibility with existing code
        
        # Camera states
        self.camera_states = [False] * 2  # 2 cameras, all initially off
        self.recording_states = [False] * 2  # 2 recording states, all initially off
        
        # Initialize Arduino tool
        self.init_arduino_tool()
        
        # Setup connection monitoring timer for shared Arduino tool
        if self.arduino_tool is not None:
            self.connection_timer = QTimer()
            self.connection_timer.timeout.connect(self.check_arduino_connection)
            self.connection_timer.start(2000)  # Check every 2 seconds
    
    def init_arduino_tool(self):
        """Initialize the Arduino Bluetooth tool."""
        if self.arduino_tool is not None:
            # Use the provided Arduino tool instance
            logger.info("Using provided Arduino tool instance")
            self.arduino_connected = self.arduino_tool.enabled and self.arduino_tool.client and self.arduino_tool.client.is_connected
            if self.arduino_connected:
                self.arduino_connection_status = "Connected (shared)"
            else:
                self.arduino_connection_status = "Disconnected (shared)"
            self.update_arduino_status_display()
        elif ARDUINO_TOOL_AVAILABLE:
            try:
                # Create new Arduino tool only if none provided
                self.arduino_tool = ArduinoBluetoothTool()
                # Start the tool in a separate thread to avoid blocking UI
                self.arduino_thread = ArduinoToolThread(self.arduino_tool)
                self.arduino_thread.connection_status_changed.connect(self.on_arduino_connection_changed)
                self.arduino_thread.device_state_changed.connect(self.on_arduino_device_state_changed)
                self.arduino_thread.start()
                logger.info("Arduino tool initialized")
            except Exception as e:
                logger.error(f"Failed to initialize Arduino tool: {e}")
                self.arduino_tool = None
        else:
            logger.warning("Arduino tool not available - running in simulation mode")
            self.arduino_tool = None
    
    def on_arduino_connection_changed(self, connected: bool, status: str):
        """Handle Arduino connection status changes."""
        self.arduino_connected = connected
        self.arduino_connection_status = status
        self.update_arduino_status_display()
    
    def on_arduino_device_state_changed(self, device_id: str, state: bool):
        """Handle Arduino device state changes."""
        if device_id in self.device_states:
            self.device_states[device_id] = state
            self.update_device_button(device_id)
            self.update_device_status()
    
    def check_arduino_connection(self):
        """Check Arduino connection status for shared tool."""
        if self.arduino_tool is not None:
            was_connected = self.arduino_connected
            self.arduino_connected = self.arduino_tool.enabled and self.arduino_tool.client and self.arduino_tool.client.is_connected
            
            if self.arduino_connected:
                self.arduino_connection_status = "Connected (shared)"
            else:
                self.arduino_connection_status = "Disconnected (shared)"
            
            # Update display if connection status changed
            if was_connected != self.arduino_connected:
                self.update_arduino_status_display()
    
    def update_arduino_status_display(self):
        """Update the Arduino status display in the UI."""
        if hasattr(self, 'arduino_status_label'):
            if self.arduino_connected:
                self.arduino_status_label.setText(f"Arduino: {self.arduino_connection_status}")
                self.arduino_status_label.setStyleSheet("color: #4CAF50; font-weight: bold;")
            else:
                self.arduino_status_label.setText(f"Arduino: {self.arduino_connection_status}")
                self.arduino_status_label.setStyleSheet("color: #f44336; font-weight: bold;")
    
    def init_ui(self):
        """Initialize the user interface."""
        # Central widget with futuristic dark theme
        central_widget = QWidget()
        central_widget.setStyleSheet("""
            QWidget {
                background-color: #000000;
                color: #E0E0E0;
                font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
            }
        """)
        self.setCentralWidget(central_widget)
        
        # Main layout - horizontal split (tabs, controls, viewer)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(8)
        
        # Left section - Tabs (fixed width)
        tabs_section = QWidget()
        tabs_section.setObjectName("tabs_section")
        tabs_section.setFixedWidth(45)  # Further reduced width for more compact layout
        tabs_section.setStyleSheet("""
            #tabs_section {
                background-color: transparent;
                border: none;
                border-radius: 0px;
                margin: 0px;
            }
        """)
        tabs_layout = QVBoxLayout(tabs_section)
        tabs_layout.setContentsMargins(4, 4, 4, 4)
        tabs_layout.setSpacing(4)
        
        # Middle section - Controls (fixed width)
        controls_section = QWidget()
        controls_section.setObjectName("controls_section")
        controls_section.setFixedWidth(420)  # Further increased width for controls
        controls_section.setStyleSheet("""
            #controls_section {
                background-color: rgba(0, 0, 0, 0.4);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 4px;
                margin: 2px;
            }
        """)
        controls_layout = QVBoxLayout(controls_section)
        controls_layout.setContentsMargins(6, 6, 6, 6)
        controls_layout.setSpacing(6)
        
        # Initialize device controls
        self.initialize_device_controls()
        
        # Create tabbed interface (tabs only)
        self.create_tabbed_interface(tabs_layout)
        
        # Create controls interface
        self.create_controls_interface(controls_layout)
        
        # Right section - Viewer (stretches to fill remaining space)
        viewer_section = QWidget()
        viewer_section.setStyleSheet("""
            QWidget {
                background-color: rgba(0, 0, 0, 0.4);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 4px;
                margin: 2px;
            }
        """)
        viewer_layout = QVBoxLayout(viewer_section)
        viewer_layout.setContentsMargins(6, 6, 6, 6)
        viewer_layout.setSpacing(6)
        
        # Create view switcher
        self.create_view_switcher(viewer_layout)
        
        # Create stacked widget for views
        self.stacked_widget = QWidget()
        self.stacked_layout = QHBoxLayout(self.stacked_widget)
        viewer_layout.addWidget(self.stacked_widget, 1)  # Add stretch factor to fill space
        
        # Add sections to main layout
        main_layout.addWidget(tabs_section, 0)  # Fixed width for tabs
        main_layout.addWidget(controls_section, 0)  # Fixed width for controls
        main_layout.addWidget(viewer_section, 1)  # Stretch to fill remaining space
        
        # Create 3D panel
        self.create_3d_panel()
        
        # Create 2D panel
        self.create_2d_panel()
        
        # Set initial view (but don't call show_3d_view yet)
        self.current_view = "3d"
        
        # Load initial model after UI is ready
        QTimer.singleShot(100, self.load_home_model)
    
    def initialize_device_controls(self):
        """Initialize device controls and room layout."""
        # Define room layout with device assignments - Updated for Arduino devices
        self.room_layout = {
            "Bedroom 1": ["L1", "L2", "RING"],   # L1, L2, and RING (Arduino controlled)
            "Living Room": [],                   # No Arduino devices
            "Kitchen": [],                       # No Arduino devices
            "Bathroom": [],                      # No Arduino devices
            "Outside": []                        # No Arduino devices
        }
        
        # Device type mapping - Only Arduino devices
        self.device_types = {
            "L1": "Light",   # L1 in Bedroom 1
            "L2": "Light",   # L2 in Bedroom 1
            "RING": "Ring Light"  # RING in Bedroom 1
        }
        
        # Create device controls for Arduino devices only
        self.light_buttons = {}
        self.light_labels = {}
        for device_id in ["L1", "L2", "RING"]:
            # Create button
            btn = QPushButton()
            btn.setMinimumSize(60, 25)
            btn.setMaximumSize(60, 25)
            btn.setText("OFF")
            btn.setCheckable(True)
            btn.setStyleSheet(self.get_light_button_style(False))
            btn.clicked.connect(lambda checked, dev_id=device_id: self.toggle_light(dev_id))
            
            self.light_buttons[device_id] = btn
            self.light_labels[device_id] = None  # Will be set per room
    
    def create_view_switcher(self, parent_layout):
        """Create the view switcher (status only)."""
        switcher_layout = QHBoxLayout()
        
        # Header bar with futuristic styling
        header_widget = QWidget()
        header_widget.setStyleSheet("""
            QWidget {
                background-color: rgba(50, 50, 50, 0.8);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 0px;
                padding: 8px;
            }
        """)
        header_layout = QHBoxLayout(header_widget)
        
        # Back button (left arrow)
        back_btn = QPushButton("<<")
        back_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(50, 50, 50, 0.8);
                color: #E0E0E0;
                font-weight: bold;
                font-size: 16px;
                padding: 4px 8px;
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 0px;
                min-width: 30px;
                font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
            }
            QPushButton:hover {
                background-color: rgba(244, 67, 54, 0.8);
                color: #ffffff;
                border: 1px solid rgba(244, 67, 54, 0.6);
            }
            QPushButton:pressed {
                background-color: rgba(244, 67, 54, 0.9);
            }
        """)
        header_layout.addWidget(back_btn)
        
        # Title and status
        title_layout = QVBoxLayout()
        title_layout.setSpacing(2)
        
        # Main title
        self.view_status = QLabel("AGENT DATA OVERVIEW")
        self.view_status.setStyleSheet("""
            font-size: 20px;
            font-weight: bold;
            color: #E0E0E0;
            padding: 8px 12px;
            text-align: center;
            font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
            background-color: rgba(50, 50, 50, 0.6);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 0px;
        """)
        title_layout.addWidget(self.view_status)
        
        # Last update timestamp
        self.last_update = QLabel("Last Update 05/06/2025 20:00")
        self.last_update.setStyleSheet("""
            font-size: 12px;
            color: #888888;
            padding: 4px 12px;
            text-align: center;
            font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
            background-color: rgba(30, 30, 30, 0.6);
            border: 1px solid rgba(255, 255, 255, 0.05);
            border-radius: 0px;
        """)
        title_layout.addWidget(self.last_update)
        
        header_layout.addLayout(title_layout)
        header_layout.addStretch()
        
        # User initials and controls
        user_controls_layout = QHBoxLayout()
        user_controls_layout.setSpacing(8)
        
        # User initials
        user_initials = QLabel("JM SW RW")
        user_initials.setStyleSheet("""
            font-size: 12px;
            color: #E0E0E0;
            font-weight: bold;
            padding: 6px 12px;
            background-color: rgba(50, 50, 50, 0.8);
            border-radius: 0px;
            border: 1px solid rgba(255, 255, 255, 0.1);
            font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
        """)
        user_controls_layout.addWidget(user_initials)
        
        # Control buttons
        refresh_btn = QPushButton("↻")
        refresh_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(50, 50, 50, 0.8);
                color: #E0E0E0;
                font-weight: bold;
                font-size: 14px;
                padding: 4px;
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 0px;
                min-width: 24px;
                min-height: 24px;
                font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
            }
            QPushButton:hover {
                background-color: rgba(244, 67, 54, 0.8);
                color: #ffffff;
                border: 1px solid rgba(244, 67, 54, 0.6);
            }
            QPushButton:pressed {
                background-color: rgba(244, 67, 54, 0.9);
            }
        """)
        user_controls_layout.addWidget(refresh_btn)
        
        export_btn = QPushButton("⊞")
        export_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(50, 50, 50, 0.8);
                color: #E0E0E0;
                font-weight: bold;
                font-size: 14px;
                padding: 4px;
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 0px;
                min-width: 24px;
                min-height: 24px;
                font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
            }
            QPushButton:hover {
                background-color: rgba(244, 67, 54, 0.8);
                color: #ffffff;
                border: 1px solid rgba(244, 67, 54, 0.6);
            }
            QPushButton:pressed {
                background-color: rgba(244, 67, 54, 0.9);
            }
        """)
        user_controls_layout.addWidget(export_btn)
        
        
        header_layout.addLayout(user_controls_layout)
        
        switcher_layout.addWidget(header_widget)
        parent_layout.addLayout(switcher_layout)
    
    def create_tab_icon(self, icon_type, size=32):
        """Create an icon for a tab based on the icon type."""
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Set colors
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(Qt.BrushStyle.SolidPattern)
        
        if icon_type == "overview":
            # Grid of 9 squares (3x3) - waffle icon
            painter.setBrush(Qt.GlobalColor.white)
            square_size = 6
            spacing = 2
            start_x = (size - (3 * square_size + 2 * spacing)) // 2
            start_y = (size - (3 * square_size + 2 * spacing)) // 2
            
            for row in range(3):
                for col in range(3):
                    x = start_x + col * (square_size + spacing)
                    y = start_y + row * (square_size + spacing)
                    painter.drawRect(x, y, square_size, square_size)
                    
        elif icon_type == "bedroom":
            # Diamond with dot in center
            painter.setBrush(Qt.GlobalColor.white)
            center_x, center_y = size // 2, size // 2
            diamond_size = 12
            
            # Draw diamond
            points = [
                QPoint(center_x, center_y - diamond_size),  # Top
                QPoint(center_x + diamond_size, center_y),  # Right
                QPoint(center_x, center_y + diamond_size),  # Bottom
                QPoint(center_x - diamond_size, center_y)   # Left
            ]
            painter.drawPolygon(points)
            
            # Draw center dot
            painter.setBrush(Qt.GlobalColor.darkGray)
            painter.drawEllipse(center_x - 2, center_y - 2, 4, 4)
            
        elif icon_type == "living":
            # Square with horizontal line through middle
            painter.setBrush(Qt.GlobalColor.white)
            square_size = 16
            x = (size - square_size) // 2
            y = (size - square_size) // 2
            painter.drawRect(x, y, square_size, square_size)
            
            # Draw horizontal line
            painter.setBrush(Qt.GlobalColor.darkGray)
            center_x, center_y = size // 2, size // 2
            line_y = center_y
            painter.drawRect(x + 2, line_y - 1, square_size - 4, 2)
            
        elif icon_type == "kitchen":
            # Starburst/asterisk symbol
            painter.setBrush(Qt.GlobalColor.white)
            center_x, center_y = size // 2, size // 2
            radius = 10
            
            # Draw starburst
            for i in range(8):
                angle = i * 45
                import math
                x1 = center_x + radius * math.cos(math.radians(angle))
                y1 = center_y + radius * math.sin(math.radians(angle))
                x2 = center_x + (radius * 0.5) * math.cos(math.radians(angle))
                y2 = center_y + (radius * 0.5) * math.sin(math.radians(angle))
                painter.drawLine(int(x1), int(y1), int(x2), int(y2))
            
        elif icon_type == "bathroom":
            # Circle with 'i' inside
            painter.setBrush(Qt.GlobalColor.white)
            center_x, center_y = size // 2, size // 2
            radius = 10
            painter.drawEllipse(center_x - radius, center_y - radius, radius * 2, radius * 2)
            
            # Draw 'i'
            painter.setBrush(Qt.GlobalColor.darkGray)
            painter.drawRect(center_x - 1, center_y - 6, 2, 2)  # Dot
            painter.drawRect(center_x - 1, center_y - 2, 2, 6)  # Line
            
        elif icon_type == "outside":
            # Gear icon
            painter.setBrush(Qt.GlobalColor.white)
            center_x, center_y = size // 2, size // 2
            outer_radius = 10
            inner_radius = 6
            
            # Draw gear teeth
            for i in range(8):
                angle = i * 45
                import math
                x1 = center_x + outer_radius * math.cos(math.radians(angle))
                y1 = center_y + outer_radius * math.sin(math.radians(angle))
                x2 = center_x + (outer_radius * 0.7) * math.cos(math.radians(angle))
                y2 = center_y + (outer_radius * 0.7) * math.sin(math.radians(angle))
                painter.drawLine(int(x1), int(y1), int(x2), int(y2))
            
            # Draw center circle
            painter.drawEllipse(center_x - inner_radius, center_y - inner_radius, inner_radius * 2, inner_radius * 2)
            
        elif icon_type == "security":
            # Camera/eye icon
            painter.setBrush(Qt.GlobalColor.white)
            center_x, center_y = size // 2, size // 2
            
            # Draw camera body
            painter.drawRect(center_x - 8, center_y - 4, 16, 8)
            
            # Draw lens
            painter.setBrush(Qt.GlobalColor.darkGray)
            painter.drawEllipse(center_x - 3, center_y - 3, 6, 6)
            
        painter.end()
        return QIcon(pixmap)

    def create_tabbed_interface(self, parent_layout):
        """Create the tabbed interface (tabs only)."""
        # Create vertical tab bar
        self.tab_bar = QWidget()
        self.tab_bar.setStyleSheet("""
            QWidget {
                background-color: transparent;
            }
        """)
        tab_bar_layout = QVBoxLayout(self.tab_bar)
        tab_bar_layout.setContentsMargins(4, 4, 4, 4)
        tab_bar_layout.setSpacing(2)
        
        # Create tab buttons
        self.tab_buttons = []
        
        # Tab definitions with icon types
        tabs = [
            ("Overview", "overview", "overview"),
            ("Bedroom 1", "bedroom1", "bedroom"),
            ("Living Room", "livingroom", "living"),
            ("Kitchen", "kitchen", "kitchen"),
            ("Bathroom", "bathroom", "bathroom"),
            ("Outside", "outside", "outside"),
            ("Security", "security", "security")
        ]
        
        for i, (tab_name, tab_id, icon_type) in enumerate(tabs):
            btn = QPushButton()
            btn.setCheckable(True)
            btn.setFixedSize(35, 35)  # Compact square buttons for vertical layout
            btn.setIcon(self.create_tab_icon(icon_type, 18))
            btn.setIconSize(QSize(18, 18))
            btn.setToolTip(tab_name)  # Show name on hover
            btn.setStyleSheet("""
                QPushButton {
                    background-color: rgba(50, 50, 50, 0.8);
                    color: #E0E0E0;
                    border: 1px solid rgba(255, 255, 255, 0.1);
                    border-radius: 0px;
                    padding: 4px;
                }
                QPushButton:checked {
                    background-color: rgba(244, 67, 54, 0.8);
                    color: #ffffff;
                    border: 1px solid rgba(244, 67, 54, 0.6);
                }
                QPushButton:hover {
                    background-color: rgba(244, 67, 54, 0.8);
                    color: #ffffff;
                    border: 1px solid rgba(244, 67, 54, 0.6);
                }
                QPushButton:checked:hover {
                    background-color: rgba(244, 67, 54, 0.9);
                }
            """)
            btn.clicked.connect(lambda checked, idx=i: self.switch_tab(idx))
            self.tab_buttons.append(btn)
            tab_bar_layout.addWidget(btn)
        
        tab_bar_layout.addStretch()
        
        # Add settings button at the very bottom
        self.settings_button = QPushButton("⋮")
        self.settings_button.setFixedSize(35, 35)  # Same size as other tab buttons
        self.settings_button.setStyleSheet("""
            QPushButton {
                background-color: rgba(50, 50, 50, 0.8);
                color: #E0E0E0;
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 0px;
                padding: 4px;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: rgba(244, 67, 54, 0.8);
                color: #ffffff;
                border: 1px solid rgba(244, 67, 54, 0.6);
            }
            QPushButton:pressed {
                background-color: rgba(76, 175, 80, 0.8);
                color: #ffffff;
                border: 1px solid rgba(76, 175, 80, 0.6);
            }
        """)
        self.settings_button.setToolTip("Settings")
        self.settings_button.clicked.connect(self.open_settings)
        tab_bar_layout.addWidget(self.settings_button)
        
        parent_layout.addWidget(self.tab_bar)
    
    def create_controls_interface(self, parent_layout):
        """Create the controls interface with all tab content."""
        # Create content area
        self.content_area = QWidget()
        self.content_area.setStyleSheet("""
            QWidget {
                background-color: rgba(0, 0, 0, 0.1);
            }
        """)
        self.content_layout = QVBoxLayout(self.content_area)
        self.content_layout.setContentsMargins(12, 12, 12, 12)
        self.content_layout.setSpacing(8)
        
        # Create tab pages
        self.create_overview_tab()
        self.create_room_tab("Bedroom 1", ["L1", "L2", "RING"])
        self.create_room_tab("Living Room", [])
        self.create_room_tab("Kitchen", [])
        self.create_room_tab("Bathroom", [])
        self.create_room_tab("Outside", [])
        self.create_security_cameras_tab()
        
        # Store tab pages
        self.tab_pages = {
            "overview": self.overview_tab,
            "bedroom1": self.bedroom1_tab,
            "livingroom": self.livingroom_tab,
            "kitchen": self.kitchen_tab,
            "bathroom": self.bathroom_tab,
            "outside": self.outside_tab,
            "security": self.security_tab
        }
        
        # Show initial tab
        self.current_tab_index = 0
        self.tab_buttons[0].setChecked(True)
        self.show_tab_content("overview")
        
        parent_layout.addWidget(self.content_area)
    
    def switch_tab(self, tab_index):
        """Switch to a different tab."""
        # Uncheck all buttons
        for btn in self.tab_buttons:
            btn.setChecked(False)
        
        # Check the selected button
        self.tab_buttons[tab_index].setChecked(True)
        self.current_tab_index = tab_index
        
        # Show corresponding content
        tab_names = ["overview", "bedroom1", "livingroom", "kitchen", "bathroom", "outside", "security"]
        self.show_tab_content(tab_names[tab_index])
    
    def show_tab_content(self, tab_name):
        """Show the content for the specified tab."""
        # Clear current content
        for i in reversed(range(self.content_layout.count())):
            self.content_layout.itemAt(i).widget().setParent(None)
        
        # Add the selected tab content
        if tab_name in self.tab_pages:
            self.content_layout.addWidget(self.tab_pages[tab_name])
    
    def create_overview_tab(self):
        """Create the overview tab with all devices and global controls."""
        overview_tab = QWidget()
        overview_tab.setStyleSheet("""
            QWidget {
                background-color: transparent;
            }
        """)
        overview_layout = QVBoxLayout(overview_tab)
        overview_layout.setContentsMargins(12, 12, 12, 12)
        overview_layout.setSpacing(8)
        
        # Overview header
        overview_header = QLabel("Device Controls")
        overview_header.setStyleSheet("""
            font-size: 18px;
            font-weight: bold;
            color: #E0E0E0;
            padding: 8px 0px;
            font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
            background-color: rgba(50, 50, 50, 0.8);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 0px;
            padding: 8px 12px;
        """)
        overview_layout.addWidget(overview_header)
        
        # Global controls
        global_controls_layout = QHBoxLayout()
        global_controls_layout.setSpacing(8)
        
        # All devices on/off
        all_on_btn = QPushButton("All ON")
        all_on_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        all_on_btn.setStyleSheet(self.get_scene_button_style())
        all_on_btn.clicked.connect(self.all_lights_on)
        global_controls_layout.addWidget(all_on_btn)
        
        all_off_btn = QPushButton("All OFF")
        all_off_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        all_off_btn.setStyleSheet(self.get_scene_button_style())
        all_off_btn.clicked.connect(self.all_lights_off)
        global_controls_layout.addWidget(all_off_btn)
        
        # Device status
        self.device_count_label = QLabel("0/3 devices ON")
        self.device_count_label.setStyleSheet("""
            font-size: 14px;
            color: #E0E0E0;
            padding: 5px 0px;
            font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
        """)
        global_controls_layout.addWidget(self.device_count_label)
        
        global_controls_layout.addStretch()
        
        overview_layout.addLayout(global_controls_layout)
        
        # Scene controls
        scenes_header = QLabel("Light Scenes")
        scenes_header.setStyleSheet("""
            font-size: 14px;
            font-weight: bold;
            color: #E0E0E0;
            padding: 8px 12px;
            font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
            background-color: rgba(50, 50, 50, 0.6);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 0px;
        """)
        overview_layout.addWidget(scenes_header)
        
        # Scene buttons in a grid
        scene_grid = QGridLayout()
        scene_grid.setSpacing(6)
        
        scenes = [
            ("Evening", 0), ("Night", 1), ("Party", 2),
            ("Work", 3), ("Relax", 4)
        ]
        
        for i, (name, index) in enumerate(scenes):
            btn = QPushButton(f"{name} Scene")
            btn.setStyleSheet(self.get_scene_button_style())
            btn.clicked.connect(lambda checked, idx=index: self.apply_scene(idx))
            scene_grid.addWidget(btn, i // 3, i % 3)
        
        overview_layout.addLayout(scene_grid)
        overview_layout.addStretch()
        
        # Store reference for vertical tabs
        self.overview_tab = overview_tab
    
    def create_room_tab(self, room_name, device_ids):
        """Create a tab for a specific room with its devices."""
        room_tab = QWidget()
        room_tab.setStyleSheet("""
            QWidget {
                background-color: transparent;
            }
        """)
        room_layout = QVBoxLayout(room_tab)
        room_layout.setContentsMargins(8, 8, 8, 8)
        room_layout.setSpacing(6)
        
        # Room header
        room_header = QLabel(room_name)
        room_header.setStyleSheet("""
            font-size: 16px;
            font-weight: bold;
            color: #E0E0E0;
            padding: 6px 12px;
            font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
            background-color: rgba(50, 50, 50, 0.8);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 0px;
        """)
        room_layout.addWidget(room_header)
        
        # Room controls
        room_controls_layout = QHBoxLayout()
        room_controls_layout.setSpacing(8)
        
        # Room on/off buttons (only if room has devices)
        if device_ids:
            room_on_btn = QPushButton("Room ON")
            room_on_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            room_on_btn.setStyleSheet(self.get_scene_button_style())
            room_on_btn.clicked.connect(lambda: self.room_lights_on(room_name))
            room_controls_layout.addWidget(room_on_btn)
            
            room_off_btn = QPushButton("Room OFF")
            room_off_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            room_off_btn.setStyleSheet(self.get_scene_button_style())
            room_off_btn.clicked.connect(lambda: self.room_lights_off(room_name))
            room_controls_layout.addWidget(room_off_btn)
        
        # Room device count
        room_device_count = len(device_ids)
        if room_device_count > 0:
            room_status_label = QLabel(f"{room_device_count} device{'s' if room_device_count > 1 else ''} in this room")
        else:
            room_status_label = QLabel("No Arduino devices in this room")
        room_status_label.setStyleSheet("""
            font-size: 12px;
            color: #cccccc;
            padding: 5px 0px;
        """)
        room_controls_layout.addWidget(room_status_label)
        room_controls_layout.addStretch()
        
        room_layout.addLayout(room_controls_layout)
        
        # Room devices
        if device_ids:
            devices_header = QLabel("Devices")
            devices_header.setStyleSheet("""
                font-size: 12px;
                font-weight: bold;
                color: #E0E0E0;
                padding: 6px 12px;
                font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
                background-color: rgba(50, 50, 50, 0.6);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 0px;
            """)
            room_layout.addWidget(devices_header)
            
            # Create device controls for this room
            for i, device_id in enumerate(device_ids):
                device_row = QHBoxLayout()
                device_row.setSpacing(8)
                
                # Device label
                device_label = QLabel(f"{device_id}:")
                device_label.setStyleSheet("""
                    font-size: 12px;
                    color: #cccccc;
                    font-weight: bold;
                    min-width: 60px;
                """)
                device_row.addWidget(device_label)
                
                # Device button
                device_btn = self.light_buttons[device_id]
                device_row.addWidget(device_btn)
                device_row.addStretch()
                
                room_layout.addLayout(device_row)
        else:
            # Show message for rooms without devices
            no_devices_label = QLabel("No Arduino devices in this room")
            no_devices_label.setStyleSheet("""
                font-size: 12px;
                color: #888888;
                padding: 20px 0px;
                text-align: center;
            """)
            room_layout.addWidget(no_devices_label)
        
        room_layout.addStretch()
        
        # Store reference for vertical tabs based on room name
        if room_name == "Bedroom 1":
            self.bedroom1_tab = room_tab
        elif room_name == "Living Room":
            self.livingroom_tab = room_tab
        elif room_name == "Kitchen":
            self.kitchen_tab = room_tab
        elif room_name == "Bathroom":
            self.bathroom_tab = room_tab
        elif room_name == "Outside":
            self.outside_tab = room_tab
    
    def create_security_cameras_tab(self):
        """Create the security cameras tab with camera controls."""
        cameras_tab = QWidget()
        cameras_tab.setStyleSheet("""
            QWidget {
                background-color: transparent;
            }
        """)
        cameras_layout = QVBoxLayout(cameras_tab)
        cameras_layout.setContentsMargins(8, 8, 8, 8)
        cameras_layout.setSpacing(6)
        
        # Security cameras header
        cameras_header = QLabel("Security Cameras")
        cameras_header.setStyleSheet("""
            font-size: 16px;
            font-weight: bold;
            color: #E0E0E0;
            padding: 6px 12px;
            font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
            background-color: rgba(50, 50, 50, 0.8);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 0px;
        """)
        cameras_layout.addWidget(cameras_header)
        
        # Camera status overview
        status_group = QWidget()
        status_group.setStyleSheet("""
            QWidget {
                background-color: rgba(0, 0, 0, 0.3);
                border-radius: 0px;
                padding: 10px;
                border: 1px solid rgba(255, 255, 255, 0.1);
            }
        """)
        status_layout = QVBoxLayout(status_group)
        
        status_title = QLabel("System Status")
        status_title.setStyleSheet("""
            font-size: 14px;
            font-weight: bold;
            color: #ffffff;
            padding: 5px 0px;
        """)
        status_layout.addWidget(status_title)
        
        # Camera count and status
        self.camera_status_label = QLabel("2 cameras online")
        self.camera_status_label.setStyleSheet("""
            font-size: 12px;
            color: #cccccc;
            padding: 2px 0px;
        """)
        status_layout.addWidget(self.camera_status_label)
        
        self.recording_status_label = QLabel("Recording: 0 cameras")
        self.recording_status_label.setStyleSheet("""
            font-size: 12px;
            color: #cccccc;
            padding: 2px 0px;
        """)
        status_layout.addWidget(self.recording_status_label)
        
        cameras_layout.addWidget(status_group)
        
        # Camera controls
        controls_header = QLabel("Camera Controls")
        controls_header.setStyleSheet("""
            font-size: 14px;
            font-weight: bold;
            color: #E0E0E0;
            padding: 8px 12px;
            font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
            background-color: rgba(50, 50, 50, 0.6);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 0px;
        """)
        cameras_layout.addWidget(controls_header)
        
        # Global camera controls
        global_controls_layout = QHBoxLayout()
        global_controls_layout.setSpacing(8)
        
        all_record_btn = QPushButton("Start All Recording")
        all_record_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        all_record_btn.setStyleSheet(self.get_scene_button_style())
        all_record_btn.clicked.connect(self.start_all_recording)
        global_controls_layout.addWidget(all_record_btn)
        
        all_stop_btn = QPushButton("Stop All Recording")
        all_stop_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        all_stop_btn.setStyleSheet(self.get_scene_button_style())
        all_stop_btn.clicked.connect(self.stop_all_recording)
        global_controls_layout.addWidget(all_stop_btn)
        
        global_controls_layout.addStretch()
        cameras_layout.addLayout(global_controls_layout)
        
        # Individual camera controls
        cameras_list_layout = QVBoxLayout()
        cameras_list_layout.setSpacing(4)
        
        # Define camera locations
        camera_locations = [
            ("Front Door", "CAM1"),
            ("Back Door", "CAM2")
        ]
        
        # Create camera controls
        self.camera_buttons = []
        self.camera_recording_buttons = []
        
        for i, (location, cam_id) in enumerate(camera_locations):
            camera_row = QHBoxLayout()
            camera_row.setSpacing(8)
            
            # Camera label
            camera_label = QLabel(f"{cam_id} - {location}")
            camera_label.setStyleSheet("""
                font-size: 12px;
                color: #cccccc;
                font-weight: bold;
                min-width: 120px;
            """)
            camera_row.addWidget(camera_label)
            
            # Camera on/off button
            camera_btn = QPushButton("OFF")
            camera_btn.setMinimumSize(50, 25)
            camera_btn.setMaximumSize(50, 25)
            camera_btn.setCheckable(True)
            camera_btn.setStyleSheet(self.get_camera_button_style(False))
            camera_btn.clicked.connect(lambda checked, idx=i: self.toggle_camera(idx))
            self.camera_buttons.append(camera_btn)
            camera_row.addWidget(camera_btn)
            
            # Recording button
            record_btn = QPushButton("Record")
            record_btn.setMinimumSize(60, 25)
            record_btn.setMaximumSize(60, 25)
            record_btn.setCheckable(True)
            record_btn.setStyleSheet(self.get_recording_button_style(False))
            record_btn.clicked.connect(lambda checked, idx=i: self.toggle_recording(idx))
            self.camera_recording_buttons.append(record_btn)
            camera_row.addWidget(record_btn)
            
            camera_row.addStretch()
            cameras_list_layout.addLayout(camera_row)
        
        cameras_layout.addLayout(cameras_list_layout)
        cameras_layout.addStretch()
        
        # Store reference for vertical tabs
        self.security_tab = cameras_tab
    
    def get_camera_button_style(self, is_on):
        """Get the style for camera on/off buttons."""
        if is_on:
            return """
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #888888, stop:1 #666666);
                    color: white;
                    font-weight: bold;
                    font-size: 10px;
                    border: 2px solid #888888;
                    border-radius: 0px;
                }
                QPushButton:hover {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #999999, stop:1 #777777);
                    border: 2px solid #999999;
                }
                QPushButton:pressed {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #777777, stop:1 #555555);
                }
            """
        else:
            return """
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #666666, stop:1 #444444);
                    color: #cccccc;
                    font-weight: bold;
                    font-size: 10px;
                    border: 2px solid #666666;
                    border-radius: 0px;
                }
                QPushButton:hover {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #777777, stop:1 #555555);
                    color: #dddddd;
                    border: 2px solid #777777;
                }
                QPushButton:pressed {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #555555, stop:1 #333333);
                }
            """
    
    def get_recording_button_style(self, is_recording):
        """Get the style for recording buttons."""
        if is_recording:
            return """
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #cc4444, stop:1 #aa3333);
                    color: white;
                    font-weight: bold;
                    font-size: 10px;
                    border: 2px solid #cc4444;
                    border-radius: 0px;
                }
                QPushButton:hover {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #dd5555, stop:1 #bb4444);
                    border: 2px solid #dd5555;
                }
                QPushButton:pressed {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #bb3333, stop:1 #992222);
                }
            """
        else:
            return """
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #666666, stop:1 #444444);
                    color: #cccccc;
                    font-weight: bold;
                    font-size: 10px;
                    border: 2px solid #666666;
                    border-radius: 0px;
                }
                QPushButton:hover {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #777777, stop:1 #555555);
                    color: #dddddd;
                    border: 2px solid #777777;
                }
                QPushButton:pressed {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #555555, stop:1 #333333);
                }
            """
    
    def toggle_camera(self, camera_index):
        """Toggle a specific camera on/off."""
        self.camera_states[camera_index] = not self.camera_states[camera_index]
        self.update_camera_button(camera_index)
        self.update_camera_status()
        
        # Update status
        if hasattr(self, 'status_label'):
            state = "ON" if self.camera_states[camera_index] else "OFF"
            self.status_label.setText(f"Camera {camera_index + 1} turned {state}")
    
    def toggle_recording(self, camera_index):
        """Toggle recording for a specific camera."""
        if self.camera_states[camera_index]:  # Only allow recording if camera is on
            self.recording_states[camera_index] = not self.recording_states[camera_index]
            self.update_recording_button(camera_index)
            self.update_camera_status()
            
            # Update status
            if hasattr(self, 'status_label'):
                state = "STARTED" if self.recording_states[camera_index] else "STOPPED"
                self.status_label.setText(f"Camera {camera_index + 1} recording {state}")
        else:
            # Update status
            if hasattr(self, 'status_label'):
                self.status_label.setText(f"Camera {camera_index + 1} must be ON to record")
    
    def update_camera_button(self, camera_index):
        """Update the visual appearance of a camera button."""
        button = self.camera_buttons[camera_index]
        button.setText("ON" if self.camera_states[camera_index] else "OFF")
        button.setChecked(self.camera_states[camera_index])
        button.setStyleSheet(self.get_camera_button_style(self.camera_states[camera_index]))
        
        # If camera is turned off, also stop recording
        if not self.camera_states[camera_index] and self.recording_states[camera_index]:
            self.recording_states[camera_index] = False
            self.update_recording_button(camera_index)
    
    def update_recording_button(self, camera_index):
        """Update the visual appearance of a recording button."""
        button = self.camera_recording_buttons[camera_index]
        button.setText("Stop" if self.recording_states[camera_index] else "Record")
        button.setChecked(self.recording_states[camera_index])
        button.setStyleSheet(self.get_recording_button_style(self.recording_states[camera_index]))
    
    def update_camera_status(self):
        """Update the camera status display."""
        if hasattr(self, 'camera_status_label'):
            on_count = sum(self.camera_states)
            self.camera_status_label.setText(f"{on_count}/2 cameras online")
        
        if hasattr(self, 'recording_status_label'):
            recording_count = sum(self.recording_states)
            self.recording_status_label.setText(f"Recording: {recording_count} cameras")
    
    def start_all_recording(self):
        """Start recording on all cameras that are on."""
        for i in range(2):
            if self.camera_states[i]:
                self.recording_states[i] = True
                self.update_recording_button(i)
        
        self.update_camera_status()
        if hasattr(self, 'status_label'):
            self.status_label.setText("Started recording on all active cameras")
    
    def stop_all_recording(self):
        """Stop recording on all cameras."""
        for i in range(2):
            self.recording_states[i] = False
            self.update_recording_button(i)
        
        self.update_camera_status()
        if hasattr(self, 'status_label'):
            self.status_label.setText("Stopped recording on all cameras")
    
    def get_scene_button_style(self):
        """Get the style for scene buttons."""
        return """
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 #404040, stop:1 #2a2a2a);
                color: #E0E0E0;
                font-weight: bold;
                font-size: 12px;
                padding: 8px 16px;
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: 0px;
                font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 #f44336, stop:1 #d32f2f);
                border: 1px solid rgba(244, 67, 54, 0.6);
                color: #ffffff;
            }
            QPushButton:pressed {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 #d32f2f, stop:1 #b71c1c);
            }
        """
    
    def apply_scene(self, scene_index):
        """Apply a specific scene."""
        if not hasattr(self, 'current_scene'):
            self.current_scene = 0
        
        scenes = [
            "Evening",    # Scene 0: All lights on
            "Night",      # Scene 1: L1 only
            "Party",      # Scene 2: L2 and RING
            "Work",       # Scene 3: L1 and RING
            "Relax"       # Scene 4: L2 only
        ]
        
        # Define scene patterns for Arduino devices
        scene_patterns = {
            0: {"L1": True, "L2": True, "RING": True},   # Evening - All on
            1: {"L1": True, "L2": False, "RING": False}, # Night - L1 only
            2: {"L1": False, "L2": True, "RING": True},  # Party - L2 and RING
            3: {"L1": True, "L2": False, "RING": True},  # Work - L1 and RING
            4: {"L1": False, "L2": True, "RING": False}  # Relax - L2 only
        }
        
        if scene_index in scene_patterns:
            scene_states = scene_patterns[scene_index]
            
            if self.arduino_tool and self.arduino_connected:
                # Use Arduino tool to apply scene
                asyncio.create_task(self._apply_arduino_scene(scene_states, scenes[scene_index]))
            else:
                # Fallback to local state change (simulation mode)
                for device_id, state in scene_states.items():
                    self.device_states[device_id] = state
                    self.update_device_button(device_id)
                
                self.update_device_status()
                
                if hasattr(self, 'status_label'):
                    self.status_label.setText(f"Applied {scenes[scene_index]} scene (simulation mode)")
    
    async def _apply_arduino_scene(self, scene_states, scene_name):
        """Apply Arduino scene asynchronously."""
        try:
            if self.arduino_tool and self.arduino_connected:
                # Control each device according to scene
                for device_id, state in scene_states.items():
                    result = await self.arduino_tool._execute_async({
                        "operation": "control_light",
                        "light_id": device_id,
                        "state": state
                    })
                    
                    if result.get("success"):
                        # Update local state based on Arduino response
                        self.device_states[device_id] = state
                        self.update_device_button(device_id)
                    else:
                        logger.error(f"Failed to apply scene to {device_id}: {result.get('error')}")
                
                self.update_device_status()
                
                # Update status
                if hasattr(self, 'status_label'):
                    self.status_label.setText(f"Applied {scene_name} scene")
        except Exception as e:
            logger.error(f"Error applying Arduino scene: {e}")
            if hasattr(self, 'status_label'):
                self.status_label.setText(f"Error applying scene: {str(e)}")
    
    def get_light_button_style(self, is_on):
        """Get the toggle button style for light buttons."""
        if is_on:
            return """
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #f44336, stop:1 #d32f2f);
                    color: #ffffff;
                    font-weight: bold;
                    font-size: 10px;
                    border: 2px solid #f44336;
                    border-radius: 0px;
                    font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
                }
                QPushButton:hover {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #ff5722, stop:1 #e64a19);
                    border: 2px solid #ff5722;
                }
                QPushButton:pressed {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #d32f2f, stop:1 #b71c1c);
                }
            """
        else:
            return """
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #404040, stop:1 #2a2a2a);
                    color: #888888;
                    font-weight: bold;
                    font-size: 10px;
                    border: 2px solid rgba(255, 255, 255, 0.2);
                    border-radius: 0px;
                    font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
                }
                QPushButton:hover {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #505050, stop:1 #3a3a3a);
                    color: #E0E0E0;
                    border: 2px solid rgba(255, 255, 255, 0.4);
                }
                QPushButton:pressed {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #303030, stop:1 #1a1a1a);
                }
            """
    
    def create_3d_panel(self):
        """Create the 3D viewer panel."""
        # 3D panel container
        self.panel_3d = QWidget()
        layout_3d = QVBoxLayout(self.panel_3d)
        layout_3d.setContentsMargins(0, 0, 0, 0)  # Remove margins
        
        # 3D viewer widget
        self.viewer_3d = Home3DViewer()
        layout_3d.addWidget(self.viewer_3d, 1)  # Add stretch factor
        
        # Add to stacked layout
        self.stacked_layout.addWidget(self.panel_3d)
    
    def create_2d_panel(self):
        """Create the 2D viewer panel."""
        # 2D panel container
        self.panel_2d = QWidget()
        layout_2d = QVBoxLayout(self.panel_2d)
        layout_2d.setContentsMargins(0, 0, 0, 0)  # Remove margins
        
        # 2D viewer widget
        self.viewer_2d = Home2DViewer()
        layout_2d.addWidget(self.viewer_2d, 1)  # Add stretch factor
        
        # Add to stacked layout
        self.stacked_layout.addWidget(self.panel_2d)
    
    def show_3d_view(self):
        """Show the 3D view."""
        self.current_view = "3d"
        self.panel_3d.setVisible(True)
        self.panel_2d.setVisible(False)
        if hasattr(self, 'view_status'):
            self.view_status.setText("AGENT DATA OVERVIEW")
            self.view_status.setStyleSheet("""
                font-size: 20px;
                font-weight: bold;
                color: #E0E0E0;
                padding: 0px;
                text-align: center;
                font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
            """)
        if hasattr(self, 'status_label'):
            self.status_label.setText("3D VIEW - DRAG TO ROTATE, WHEEL TO ZOOM")
    
    def show_2d_view(self):
        """Show the 2D view."""
        self.current_view = "2d"
        self.panel_3d.setVisible(False)
        self.panel_2d.setVisible(True)
        if hasattr(self, 'view_status'):
            self.view_status.setText("AGENT DATA OVERVIEW")
            self.view_status.setStyleSheet("""
                font-size: 20px;
                font-weight: bold;
                color: #E0E0E0;
                padding: 0px;
                text-align: center;
                font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
            """)
        if hasattr(self, 'status_label'):
            self.status_label.setText("2D VIEW - CLICK ROOMS, WHEEL TO ZOOM")
    
    
    def setup_connections(self):
        """Setup signal connections."""
        # 3D viewer signals
        self.viewer_3d.view_changed.connect(self.on_3d_view_changed)
        
        # 2D viewer signals
        self.viewer_2d.room_selected.connect(self.on_room_selected)
        self.viewer_2d.view_changed.connect(self.on_2d_view_changed)
    
    
    def setup_status_bar(self):
        """Setup futuristic status bar."""
        self.status_bar = QStatusBar()
        self.status_bar.setStyleSheet("""
            QStatusBar {
                background-color: rgba(0, 0, 0, 0.7);
                border-top: 1px solid rgba(255, 255, 255, 0.1);
                color: #E0E0E0;
                font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
                font-size: 12px;
                padding: 4px;
            }
        """)
        self.setStatusBar(self.status_bar)
        
        # Status label with futuristic styling
        self.status_label = QLabel("SYSTEM READY")
        self.status_label.setStyleSheet("""
            font-size: 12px;
            color: #4CAF50;
            font-weight: bold;
            font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
        """)
        self.status_bar.addWidget(self.status_label)
        
        # Add system status indicators
        separator = QLabel("|")
        separator.setStyleSheet("""
            font-size: 11px;
            color: #666666;
            font-weight: bold;
            font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
        """)
        self.status_bar.addPermanentWidget(separator)
        
        # Connection status
        self.connection_status = QLabel("CONN: ONLINE")
        self.connection_status.setStyleSheet("""
            font-size: 11px;
            color: #4CAF50;
            font-weight: bold;
            font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
        """)
        self.status_bar.addPermanentWidget(self.connection_status)
        
        separator2 = QLabel("|")
        separator2.setStyleSheet("""
            font-size: 11px;
            color: #666666;
            font-weight: bold;
            font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
        """)
        self.status_bar.addPermanentWidget(separator2)
        
        # Arduino status
        self.arduino_status_label = QLabel("Arduino: Disconnected")
        self.arduino_status_label.setStyleSheet("""
            font-size: 11px;
            color: #f44336;
            font-weight: bold;
            font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
        """)
        self.status_bar.addPermanentWidget(self.arduino_status_label)
        
        separator3 = QLabel("|")
        separator3.setStyleSheet("""
            font-size: 11px;
            color: #666666;
            font-weight: bold;
            font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
        """)
        self.status_bar.addPermanentWidget(separator3)
        
        # Time display
        self.time_display = QLabel("20:00:00")
        self.time_display.setStyleSheet("""
            font-size: 11px;
            color: #E0E0E0;
            font-weight: bold;
            font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
        """)
        self.status_bar.addPermanentWidget(self.time_display)
    
    
    def setup_shortcuts(self):
        """Setup keyboard shortcuts."""
        # Reset views
        reset_action = QAction("Reset Views", self)
        reset_action.setShortcut("R")
        reset_action.triggered.connect(self.reset_all_views)
        self.addAction(reset_action)
        
        # Toggle sync
        sync_action = QAction("Toggle Sync", self)
        sync_action.setShortcut("S")
        sync_action.triggered.connect(self.toggle_sync)
        self.addAction(sync_action)
        
        # Switch to 3D view
        view_3d_action = QAction("3D View", self)
        view_3d_action.setShortcut("3")
        view_3d_action.triggered.connect(self.show_3d_view)
        self.addAction(view_3d_action)
        
        # Switch to 2D view
        view_2d_action = QAction("2D View", self)
        view_2d_action.setShortcut("2")
        view_2d_action.triggered.connect(self.show_2d_view)
        self.addAction(view_2d_action)
        
        # Close application
        close_action = QAction("Close", self)
        close_action.setShortcut("Escape")
        close_action.triggered.connect(self.close)
        self.addAction(close_action)
    
    def load_home_model(self):
        """Load the home model."""
        # Show the initial view now that status bar is ready
        self.show_3d_view()
        
        self.status_label.setText("Loading home model...")
        
        # The model loading is handled in the 3D viewer constructor
        # This is just for UI feedback
        QTimer.singleShot(1000, self.on_model_loaded)
    
    def on_model_loaded(self):
        """Called when model loading is complete."""
        if self.current_view == "3d":
            self.status_label.setText("3D VIEW - DRAG TO ROTATE, WHEEL TO ZOOM")
        else:
            self.status_label.setText("2D VIEW - CLICK ROOMS, WHEEL TO ZOOM")
    
    
    def on_3d_view_changed(self, x, y, z):
        """Handle 3D view changes."""
        # TODO: Implement 3D to 2D view synchronization
        pass
    
    def on_2d_view_changed(self, pan_x, pan_y, zoom):
        """Handle 2D view changes."""
        # TODO: Implement 2D to 3D view synchronization
        pass
    
    def on_room_selected(self, room_name):
        """Handle room selection."""
        self.current_room = room_name
        if self.current_view == "2d":
            self.status_label.setText(f"2D VIEW - SELECTED ROOM: {room_name.upper()}")
        else:
            self.status_label.setText(f"3D VIEW - SELECTED ROOM: {room_name.upper()}")
    
    
    def reset_all_views(self):
        """Reset both views."""
        self.viewer_3d.reset_view()
        self.viewer_2d.reset_view()
        if hasattr(self, 'status_label'):
            self.status_label.setText("VIEWS RESET")
    
    def toggle_sync(self):
        """Toggle synchronization."""
        self.sync_views = not self.sync_views
        if hasattr(self, 'status_label'):
            self.status_label.setText(f"VIEW SYNC: {'ON' if self.sync_views else 'OFF'}")
    
    def toggle_light(self, device_id):
        """Toggle a specific light on/off."""
        if self.arduino_tool and self.arduino_connected:
            # Use Arduino tool to control the device
            asyncio.create_task(self._toggle_arduino_device(device_id))
        else:
            # Fallback to local state change (simulation mode)
            self.device_states[device_id] = not self.device_states[device_id]
            self.update_device_button(device_id)
            self.update_device_status()
            
            # Update status
            if hasattr(self, 'status_label'):
                state = "ON" if self.device_states[device_id] else "OFF"
                # Find which room this device belongs to
                room_name = "Unknown"
                for room, devices in self.room_layout.items():
                    if device_id in devices:
                        room_name = room
                        break
                
                self.status_label.setText(f"{room_name} - {device_id} turned {state} (simulation mode)")
    
    async def _toggle_arduino_device(self, device_id):
        """Toggle Arduino device asynchronously."""
        try:
            if self.arduino_tool and self.arduino_connected:
                result = await self.arduino_tool._execute_async({
                    "operation": "toggle_light",
                    "light_id": device_id
                })
                
                if result.get("success"):
                    # Update local state based on Arduino response
                    new_state = result.get("state") == "ON"
                    self.device_states[device_id] = new_state
                    self.update_device_button(device_id)
                    self.update_device_status()
                    
                    # Update status
                    if hasattr(self, 'status_label'):
                        room_name = "Unknown"
                        for room, devices in self.room_layout.items():
                            if device_id in devices:
                                room_name = room
                                break
                        self.status_label.setText(f"{room_name} - {device_id} turned {result.get('state')}")
                else:
                    # Handle error
                    if hasattr(self, 'status_label'):
                        self.status_label.setText(f"Failed to control {device_id}: {result.get('error', 'Unknown error')}")
        except Exception as e:
            logger.error(f"Error toggling Arduino device {device_id}: {e}")
            if hasattr(self, 'status_label'):
                self.status_label.setText(f"Error controlling {device_id}: {str(e)}")
    
    def update_device_button(self, device_id):
        """Update the visual appearance of a device button and its label."""
        if device_id in self.light_buttons:
            button = self.light_buttons[device_id]
            label = self.light_labels.get(device_id)
            
            button.setText("ON" if self.device_states[device_id] else "OFF")
            button.setChecked(self.device_states[device_id])
            button.setStyleSheet(self.get_light_button_style(self.device_states[device_id]))
            
            # Update label color based on device state (if label exists)
            if label is not None:
                if self.device_states[device_id]:
                    label.setStyleSheet("""
                        font-size: 11px;
                        color: #ffffff;
                        font-weight: bold;
                        min-width: 30px;
                    """)
                else:
                    label.setStyleSheet("""
                        font-size: 11px;
                        color: #cccccc;
                        font-weight: bold;
                        min-width: 30px;
                    """)
    
    def update_light_button(self, light_index):
        """Legacy method for compatibility - redirects to update_device_button."""
        # Convert old index-based system to new device_id system
        if isinstance(light_index, int):
            # This is the old system - convert to device_id
            device_id = f"L{light_index + 1}"
            if device_id in self.device_states:
                self.update_device_button(device_id)
        else:
            # This is already a device_id
            self.update_device_button(light_index)
    
    def update_device_status(self):
        """Update the device status counter."""
        on_count = sum(1 for state in self.device_states.values() if state)
        
        if hasattr(self, 'light_status'):
            self.light_status.setText(f"{on_count}/2 ON")
        
        if hasattr(self, 'device_count_label'):
            self.device_count_label.setText(f"{on_count}/3 devices ON")
    
    def update_light_status(self):
        """Legacy method for compatibility - redirects to update_device_status."""
        self.update_device_status()
    
    def all_lights_on(self):
        """Turn all devices on."""
        if self.arduino_tool and self.arduino_connected:
            # Use Arduino tool to control all devices
            asyncio.create_task(self._control_all_arduino_devices(True))
        else:
            # Fallback to local state change (simulation mode)
            for device_id in self.device_states:
                self.device_states[device_id] = True
                self.update_device_button(device_id)
            
            self.update_device_status()
            if hasattr(self, 'status_label'):
                self.status_label.setText("All devices turned ON (simulation mode)")
    
    def all_lights_off(self):
        """Turn all devices off."""
        if self.arduino_tool and self.arduino_connected:
            # Use Arduino tool to control all devices
            asyncio.create_task(self._control_all_arduino_devices(False))
        else:
            # Fallback to local state change (simulation mode)
            for device_id in self.device_states:
                self.device_states[device_id] = False
                self.update_device_button(device_id)
            
            self.update_device_status()
            if hasattr(self, 'status_label'):
                self.status_label.setText("All devices turned OFF (simulation mode)")
    
    async def _control_all_arduino_devices(self, state):
        """Control all Arduino devices asynchronously."""
        try:
            if self.arduino_tool and self.arduino_connected:
                result = await self.arduino_tool._execute_async({
                    "operation": "control_all_lights",
                    "state": state
                })
                
                if result.get("success"):
                    # Update local states based on Arduino response
                    for device_id in self.device_states:
                        self.device_states[device_id] = state
                        self.update_device_button(device_id)
                    
                    self.update_device_status()
                    
                    # Update status
                    if hasattr(self, 'status_label'):
                        state_text = "ON" if state else "OFF"
                        self.status_label.setText(f"All devices turned {state_text}")
                else:
                    # Handle error
                    if hasattr(self, 'status_label'):
                        self.status_label.setText(f"Failed to control all devices: {result.get('error', 'Unknown error')}")
        except Exception as e:
            logger.error(f"Error controlling all Arduino devices: {e}")
            if hasattr(self, 'status_label'):
                self.status_label.setText(f"Error controlling all devices: {str(e)}")
    
    def room_lights_on(self, room_name):
        """Turn on all devices in a specific room."""
        if room_name in self.room_layout:
            device_ids = self.room_layout[room_name]
            if device_ids:
                if self.arduino_tool and self.arduino_connected:
                    # Use Arduino tool to control room devices
                    asyncio.create_task(self._control_room_arduino_devices(room_name, device_ids, True))
                else:
                    # Fallback to local state change (simulation mode)
                    for device_id in device_ids:
                        self.device_states[device_id] = True
                        self.update_device_button(device_id)
                    
                    self.update_device_status()
                    if hasattr(self, 'status_label'):
                        self.status_label.setText(f"All devices in {room_name} turned ON (simulation mode)")
            else:
                if hasattr(self, 'status_label'):
                    self.status_label.setText(f"No Arduino devices in {room_name}")
    
    def room_lights_off(self, room_name):
        """Turn off all devices in a specific room."""
        if room_name in self.room_layout:
            device_ids = self.room_layout[room_name]
            if device_ids:
                if self.arduino_tool and self.arduino_connected:
                    # Use Arduino tool to control room devices
                    asyncio.create_task(self._control_room_arduino_devices(room_name, device_ids, False))
                else:
                    # Fallback to local state change (simulation mode)
                    for device_id in device_ids:
                        self.device_states[device_id] = False
                        self.update_device_button(device_id)
                    
                    self.update_device_status()
                    if hasattr(self, 'status_label'):
                        self.status_label.setText(f"All devices in {room_name} turned OFF (simulation mode)")
            else:
                if hasattr(self, 'status_label'):
                    self.status_label.setText(f"No Arduino devices in {room_name}")
    
    async def _control_room_arduino_devices(self, room_name, device_ids, state):
        """Control room Arduino devices asynchronously."""
        try:
            if self.arduino_tool and self.arduino_connected:
                # Control each device in the room
                for device_id in device_ids:
                    result = await self.arduino_tool._execute_async({
                        "operation": "control_light",
                        "light_id": device_id,
                        "state": state
                    })
                    
                    if result.get("success"):
                        # Update local state based on Arduino response
                        self.device_states[device_id] = state
                        self.update_device_button(device_id)
                    else:
                        logger.error(f"Failed to control {device_id}: {result.get('error')}")
                
                self.update_device_status()
                
                # Update status
                if hasattr(self, 'status_label'):
                    state_text = "ON" if state else "OFF"
                    self.status_label.setText(f"All devices in {room_name} turned {state_text}")
        except Exception as e:
            logger.error(f"Error controlling room Arduino devices: {e}")
            if hasattr(self, 'status_label'):
                self.status_label.setText(f"Error controlling devices in {room_name}: {str(e)}")
    
    def toggle_scene(self):
        """Toggle between different light scenes."""
        if not hasattr(self, 'current_scene'):
            self.current_scene = 0
        
        scenes = [
            "Evening",    # Scene 0: All lights on
            "Night",      # Scene 1: Every other light
            "Party",      # Scene 2: Random pattern
            "Work",       # Scene 3: First 8 lights
            "Relax"       # Scene 4: Last 8 lights
        ]
        
        if self.current_scene == 0:  # Evening - All on
            for i in range(22):
                self.light_states[i] = True
        elif self.current_scene == 1:  # Night - Every other
            for i in range(22):
                self.light_states[i] = (i % 2 == 0)
        elif self.current_scene == 2:  # Party - Random pattern
            import random
            for i in range(22):
                self.light_states[i] = random.choice([True, False])
        elif self.current_scene == 3:  # Work - First 8
            for i in range(22):
                self.light_states[i] = (i < 8)
        elif self.current_scene == 4:  # Relax - Last 8
            for i in range(22):
                self.light_states[i] = (i >= 9)
        
        # Update all buttons
        for i in range(22):
            self.update_light_button(i)
        
        self.update_light_status()
        self.current_scene = (self.current_scene + 1) % len(scenes)
        
        if hasattr(self, 'status_label'):
            self.status_label.setText(f"Scene: {scenes[self.current_scene - 1] if self.current_scene > 0 else scenes[-1]}")
    
    def closeEvent(self, event):
        """Handle application close."""
        # Clean up Arduino thread (only if we created our own)
        if hasattr(self, 'arduino_thread') and self.arduino_thread:
            self.arduino_thread.stop()
        
        # Stop connection monitoring timer
        if hasattr(self, 'connection_timer'):
            self.connection_timer.stop()
        
        # Clean up resources
        if hasattr(self.viewer_3d, 'timer'):
            self.viewer_3d.timer.stop()
        
        event.accept()
    
    def open_settings(self):
        """Open the settings dialog."""
        settings_dialog = SettingsDialog(self)
        settings_dialog.exec()


class SettingsDialog(QDialog):
    """Settings dialog for the home viewer application."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.setWindowTitle("Settings")
        self.setModal(True)
        self.resize(400, 300)
        
        # Set window flags for frameless window
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        
        self.init_ui()
    
    def init_ui(self):
        """Initialize the settings dialog UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # Title
        title = QLabel("Settings")
        title.setStyleSheet("""
            font-size: 18px;
            font-weight: bold;
            color: #ffffff;
            padding: 10px 0px;
        """)
        layout.addWidget(title)
        
        # View Settings Group
        view_group = QGroupBox("View Settings")
        view_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                color: #cccccc;
                border: 2px solid #666666;
                border-radius: 0px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
        """)
        view_layout = QVBoxLayout(view_group)
        
        # Sync views checkbox
        self.sync_views_cb = QCheckBox("Synchronize 3D and 2D views")
        self.sync_views_cb.setChecked(self.parent.sync_views)
        self.sync_views_cb.setStyleSheet("""
            QCheckBox {
                color: #ffffff;
                font-size: 14px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
            }
        """)
        view_layout.addWidget(self.sync_views_cb)
        
        # Default view selection
        default_view_layout = QHBoxLayout()
        default_view_layout.addWidget(QLabel("Default View:"))
        self.default_view_combo = QComboBox()
        self.default_view_combo.addItems(["3D View", "2D View"])
        self.default_view_combo.setCurrentText("3D View" if self.parent.current_view == "3d" else "2D View")
        self.default_view_combo.setStyleSheet("""
            QComboBox {
                background-color: #444444;
                color: #ffffff;
                border: 1px solid #666666;
                border-radius: 0px;
                padding: 5px;
                min-width: 100px;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 5px solid #ffffff;
                margin-right: 5px;
            }
        """)
        default_view_layout.addWidget(self.default_view_combo)
        default_view_layout.addStretch()
        view_layout.addLayout(default_view_layout)
        
        layout.addWidget(view_group)
        
        # Display Settings Group
        display_group = QGroupBox("Display Settings")
        display_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                color: #cccccc;
                border: 2px solid #666666;
                border-radius: 0px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
        """)
        display_layout = QVBoxLayout(display_group)
        
        # Window size settings
        size_layout = QHBoxLayout()
        size_layout.addWidget(QLabel("Window Size:"))
        self.width_spin = QSpinBox()
        self.width_spin.setRange(800, 2000)
        self.width_spin.setValue(self.parent.width())
        self.width_spin.setStyleSheet("""
            QSpinBox {
                background-color: #444444;
                color: #ffffff;
                border: 1px solid #666666;
                border-radius: 0px;
                padding: 5px;
                min-width: 80px;
            }
        """)
        size_layout.addWidget(self.width_spin)
        size_layout.addWidget(QLabel("x"))
        self.height_spin = QSpinBox()
        self.height_spin.setRange(600, 1500)
        self.height_spin.setValue(self.parent.height())
        self.height_spin.setStyleSheet("""
            QSpinBox {
                background-color: #444444;
                color: #ffffff;
                border: 1px solid #666666;
                border-radius: 0px;
                padding: 5px;
                min-width: 80px;
            }
        """)
        size_layout.addWidget(self.height_spin)
        size_layout.addStretch()
        display_layout.addLayout(size_layout)
        
        layout.addWidget(display_group)
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        # Apply button
        apply_btn = QPushButton("Apply")
        apply_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 #f44336, stop:1 #d32f2f);
                color: #ffffff;
                font-weight: bold;
                font-size: 14px;
                padding: 8px 20px;
                border: none;
                border-radius: 0px;
                min-width: 80px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 #ff5722, stop:1 #e64a19);
            }
            QPushButton:pressed {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 #d32f2f, stop:1 #b71c1c);
            }
        """)
        apply_btn.clicked.connect(self.apply_settings)
        button_layout.addWidget(apply_btn)
        
        # Cancel button
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 #666666, stop:1 #444444);
                color: #ffffff;
                font-weight: bold;
                font-size: 14px;
                padding: 8px 20px;
                border: 1px solid #777777;
                border-radius: 0px;
                min-width: 80px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 #777777, stop:1 #555555);
            }
            QPushButton:pressed {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 #555555, stop:1 #333333);
            }
        """)
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        layout.addLayout(button_layout)
        
        # Set dialog background
        self.setStyleSheet("""
            QDialog {
                background-color: rgba(0, 0, 0, 0.8);
            }
            QLabel {
                color: #ffffff;
            }
        """)
    
    def apply_settings(self):
        """Apply the settings and close the dialog."""
        # Apply sync views setting
        self.parent.sync_views = self.sync_views_cb.isChecked()
        
        # Apply default view setting
        if self.default_view_combo.currentText() == "3D View":
            self.parent.current_view = "3d"
        else:
            self.parent.current_view = "2d"
        
        # Apply window size setting
        new_width = self.width_spin.value()
        new_height = self.height_spin.value()
        self.parent.resize(new_width, new_height)
        
        # Close dialog
        self.accept()


def main():
    """Main application entry point."""
    app = QApplication(sys.argv)
    app.setApplicationName("ARAS Home Viewer")
    app.setApplicationVersion("1.0")
    
    # Set application style
    app.setStyle('Fusion')
    
    # Create and show main window
    window = HomeViewerApp()
    window.show()
    
    # Run application
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
