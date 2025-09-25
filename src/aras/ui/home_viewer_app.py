"""
Main PyQt6 application for 3D and 2D home visualization.
"""

import sys
import os
import math
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QLabel, QStatusBar, QPushButton, QGridLayout, QSizePolicy, QTabWidget,
                            QDialog, QVBoxLayout, QHBoxLayout, QCheckBox, QSpinBox, QComboBox, QGroupBox)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QAction
from PyQt6.QtOpenGLWidgets import QOpenGLWidget

try:
    from .home_3d_viewer import Home3DViewer
    from .home_2d_viewer import Home2DViewer
except ImportError:
    # When running directly, use absolute imports
    from home_3d_viewer import Home3DViewer
    from home_2d_viewer import Home2DViewer


class HomeViewerApp(QMainWindow):
    """Main application window for home visualization."""
    
    def __init__(self):
        super().__init__()
        
        # Window properties
        self.setWindowTitle("ARAS Home Viewer - 3D & 2D Visualization")
        self.setGeometry(100, 100, 1400, 900)
        
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
        
        # Device states (lights + TVs + ACs)
        self.device_states = [False] * 22  # 17 lights + 2 TVs + 3 ACs, all initially off
        self.light_states = self.device_states  # Keep compatibility with existing code
        
        # Camera states
        self.camera_states = [False] * 8  # 8 cameras, all initially off
        self.recording_states = [False] * 8  # 8 recording states, all initially off
    
    def init_ui(self):
        """Initialize the user interface."""
        # Central widget
        central_widget = QWidget()
        central_widget.setStyleSheet("""
            QWidget {
                background-color: transparent;
            }
        """)
        self.setCentralWidget(central_widget)
        
        # Main layout - horizontal split
        main_layout = QHBoxLayout(central_widget)
        
        # Left side - Viewer (50% of width)
        left_panel = QWidget()
        left_panel.setStyleSheet("""
            QWidget {
                background-color: transparent;
            }
        """)
        left_layout = QVBoxLayout(left_panel)
        
        # Create view switcher
        self.create_view_switcher(left_layout)
        
        # Create stacked widget for views
        self.stacked_widget = QWidget()
        self.stacked_layout = QHBoxLayout(self.stacked_widget)
        left_layout.addWidget(self.stacked_widget, 1)  # Add stretch factor to fill space
        
        # Right side - Controls (50% of width)
        right_panel = QWidget()
        right_panel.setStyleSheet("""
            QWidget {
                background-color: transparent;
            }
        """)
        right_layout = QVBoxLayout(right_panel)
        
        # Initialize device controls
        self.initialize_device_controls()
        
        # Create tabbed interface
        self.create_tabbed_interface(right_layout)
        
        # Add panels to main layout with equal stretch
        main_layout.addWidget(left_panel, 1)  # 50% width
        main_layout.addWidget(right_panel, 1)  # 50% width
        
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
        # Define room layout with device assignments
        self.room_layout = {
            "Bedroom 1": [0, 1, 2, 19],  # L1, L2, L3, AC1
            "Bedroom 2": [3, 4, 5],      # L4, L5, L6
            "Bedroom 3": [6, 7, 8, 17, 20],  # L7, L8, L9, TV1, AC2
            "Kitchen": [9, 10],          # L10, L11
            "Living Room": [11, 12, 13, 18, 21], # L12, L13, L14, TV2, AC3
            "Bathroom": [14],            # L15
            "Outside": [15, 16]          # L16, L17
        }
        
        # Device type mapping
        self.device_types = {
            17: "TV",   # TV1 in Bedroom 3
            18: "TV",   # TV2 in Living Room
            19: "AC",   # AC1 in Bedroom 1
            20: "AC",   # AC2 in Bedroom 3
            21: "AC"    # AC3 in Living Room
        }
        
        # Create 22 device controls (17 lights + 2 TVs + 3 ACs)
        self.light_buttons = []
        self.light_labels = []
        for i in range(22):
            # Create button
            btn = QPushButton()
            btn.setMinimumSize(60, 25)
            btn.setMaximumSize(60, 25)
            btn.setText("OFF")
            btn.setCheckable(True)
            btn.setStyleSheet(self.get_light_button_style(False))
            btn.clicked.connect(lambda checked, idx=i: self.toggle_light(idx))
            
            self.light_buttons.append(btn)
            self.light_labels.append(None)  # Will be set per room
    
    def create_view_switcher(self, parent_layout):
        """Create the view switcher (status only)."""
        switcher_layout = QHBoxLayout()
        
        # Status display
        self.view_status = QLabel("3D View")
        self.view_status.setStyleSheet("font-size: 18px; font-weight: bold; color: #4CAF50; padding: 10px;")
        switcher_layout.addWidget(self.view_status)
        
        switcher_layout.addStretch()
        
        # Instructions
        instructions = QLabel("Press 3 for 3D, 2 for 2D, R to reset, ESC to close")
        instructions.setStyleSheet("font-size: 12px; color: gray; padding: 10px;")
        switcher_layout.addWidget(instructions)
        
        # Settings button
        self.settings_button = QPushButton("⚙")
        self.settings_button.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #ffffff;
                font-weight: bold;
                font-size: 18px;
                padding: 4px;
                border: none;
                border-radius: 3px;
                min-width: 24px;
                min-height: 24px;
            }
            QPushButton:hover {
                background: rgba(255, 255, 255, 0.1);
                color: #4CAF50;
            }
            QPushButton:pressed {
                background: rgba(255, 255, 255, 0.2);
                color: #66BB6A;
            }
        """)
        self.settings_button.setToolTip("Settings")
        self.settings_button.clicked.connect(self.open_settings)
        switcher_layout.addWidget(self.settings_button)
        
        parent_layout.addLayout(switcher_layout)
    
    def create_light_panel_old(self, parent_layout):
        """Create the modern light control panel with 17 light buttons."""
        light_panel = QWidget()
        light_panel.setStyleSheet("""
            QWidget {
                background-color: transparent;
                border-radius: 10px;
                margin: 5px;
            }
        """)
        light_layout = QVBoxLayout(light_panel)
        light_layout.setSpacing(0)
        light_layout.setContentsMargins(10, 10, 10, 10)
        
        # Modern light panel header with control buttons
        header_layout = QHBoxLayout()
        
        light_title = QLabel("Lights")
        light_title.setStyleSheet("""
            font-size: 14px; 
            font-weight: bold; 
            color: #ffffff;
            padding: 2px;
        """)
        header_layout.addWidget(light_title)
        
        # Device status indicator
        self.light_status = QLabel("0/22 ON")
        self.light_status.setStyleSheet("""
            font-size: 12px; 
            color: #888888;
            padding: 2px;
        """)
        header_layout.addWidget(self.light_status)
        
        # Add stretch to push control buttons to the right
        header_layout.addStretch()
        
        # Control buttons in the header
        control_layout = QHBoxLayout()
        control_layout.setSpacing(0)
        
        all_on_btn = QPushButton("On")
        all_on_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        all_on_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 #666666, stop:1 #444444);
                color: #ffffff;
                font-weight: bold;
                font-size: 12px;
                padding: 1px 3px;
                border: 1px solid #777777;
                border-radius: 3px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 #777777, stop:1 #555555);
                border: 1px solid #888888;
            }
            QPushButton:pressed {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 #555555, stop:1 #333333);
            }
        """)
        all_on_btn.clicked.connect(self.all_lights_on)
        control_layout.addWidget(all_on_btn)
        
        all_off_btn = QPushButton("Off")
        all_off_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        all_off_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 #666666, stop:1 #444444);
                color: #ffffff;
                font-weight: bold;
                font-size: 12px;
                padding: 1px 3px;
                border: 1px solid #777777;
                border-radius: 3px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 #777777, stop:1 #555555);
                border: 1px solid #888888;
            }
            QPushButton:pressed {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 #555555, stop:1 #333333);
            }
        """)
        all_off_btn.clicked.connect(self.all_lights_off)
        control_layout.addWidget(all_off_btn)
        
        # Add control buttons to header layout
        header_layout.addLayout(control_layout)
        
        light_layout.addLayout(header_layout)
        
        # Create room-based layout for light controls
        light_list_layout = QVBoxLayout()
        light_list_layout.setSpacing(8)
        
        # Define room layout with device assignments
        self.room_layout = {
            "Bedroom 1": [0, 1, 2, 19],  # L1, L2, L3, AC1
            "Bedroom 2": [3, 4, 5],      # L4, L5, L6
            "Bedroom 3": [6, 7, 8, 17, 20],  # L7, L8, L9, TV1, AC2
            "Kitchen": [9, 10],          # L10, L11
            "Living Room": [11, 12, 13, 18, 21], # L12, L13, L14, TV2, AC3
            "Bathroom": [14],            # L15
            "Outside": [15, 16]          # L16, L17
        }
        
        # Device type mapping
        self.device_types = {
            17: "TV",   # TV1 in Bedroom 3
            18: "TV",   # TV2 in Living Room
            19: "AC",   # AC1 in Bedroom 1
            20: "AC",   # AC2 in Bedroom 3
            21: "AC"    # AC3 in Living Room
        }
        
        # Create 22 device controls (17 lights + 2 TVs + 3 ACs)
        self.light_buttons = []
        self.light_labels = []
        for i in range(22):
            # Create button
            btn = QPushButton()
            btn.setMinimumSize(60, 25)
            btn.setMaximumSize(60, 25)
            btn.setText("OFF")
            btn.setCheckable(True)
            btn.setStyleSheet(self.get_light_button_style(False))
            btn.clicked.connect(lambda checked, idx=i: self.toggle_light(idx))
            
            self.light_buttons.append(btn)
            self.light_labels.append(None)  # Will be set per room
        
        # Create room sections
        for room_name, device_indices in self.room_layout.items():
            # Room header with controls
            room_header_layout = QHBoxLayout()
            
            room_header = QLabel(room_name)
            room_header.setStyleSheet("""
                font-size: 13px;
                font-weight: bold;
                color: #4CAF50;
                padding: 4px 0px;
            """)
            room_header_layout.addWidget(room_header)
            
            # Add stretch to push buttons to the right
            room_header_layout.addStretch()
            
            # Room control buttons
            room_on_btn = QPushButton("On")
            room_on_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            room_on_btn.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                        stop:0 #4CAF50, stop:1 #45a049);
                    color: #ffffff;
                    font-weight: bold;
                    font-size: 10px;
                    padding: 2px 6px;
                    border: 1px solid #4CAF50;
                    border-radius: 3px;
                }
                QPushButton:hover {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                        stop:0 #5CBF60, stop:1 #4CAF50);
                }
            """)
            room_on_btn.clicked.connect(lambda checked, room=room_name: self.room_lights_on(room))
            
            room_off_btn = QPushButton("Off")
            room_off_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            room_off_btn.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                        stop:0 #666666, stop:1 #444444);
                    color: #ffffff;
                    font-weight: bold;
                    font-size: 10px;
                    padding: 2px 6px;
                    border: 1px solid #777777;
                    border-radius: 3px;
                }
                QPushButton:hover {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                        stop:0 #777777, stop:1 #555555);
                }
            """)
            room_off_btn.clicked.connect(lambda checked, room=room_name: self.room_lights_off(room))
            
            room_header_layout.addWidget(room_on_btn)
            room_header_layout.addWidget(room_off_btn)
            
            light_list_layout.addLayout(room_header_layout)
            
            # Room devices
            room_layout = QVBoxLayout()
            room_layout.setSpacing(2)
            room_layout.setContentsMargins(10, 0, 0, 0)
            
            for i, device_idx in enumerate(device_indices):
                # Create horizontal layout for each device
                device_row = QHBoxLayout()
                device_row.setSpacing(8)
                
                # Determine device type and global number
                device_type = self.device_types.get(device_idx, "L")
                if device_type == "TV":
                    global_label = f"TV{device_idx-16}"  # TV1, TV2
                elif device_type == "AC":
                    global_label = f"AC{device_idx-18}"  # AC1, AC2, AC3
                else:
                    global_label = f"L{device_idx+1}"
                
                # Create label for the device with both global and local numbering
                label = QLabel(f"{global_label} ({i+1}):")
                label.setStyleSheet("""
                    font-size: 11px;
                    color: #cccccc;
                    font-weight: bold;
                    min-width: 50px;
                """)
                label.setAlignment(Qt.AlignmentFlag.AlignLeft)
                
                # Set the label in our list
                self.light_labels[device_idx] = label
            
            # Add label and button to row
                device_row.addWidget(label)
                device_row.addWidget(self.light_buttons[device_idx])
                device_row.addStretch()  # Push content to left
                
                # Add row to room layout
                room_layout.addLayout(device_row)
            
            # Add room layout to main layout
            light_list_layout.addLayout(room_layout)
        
        light_layout.addLayout(light_list_layout)
        
        parent_layout.addWidget(light_panel)
    
    def create_tabbed_interface(self, parent_layout):
        """Create the tabbed interface organized by rooms."""
        # Create tab widget
        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: none;
                background-color: transparent;
            }
            QTabBar::tab {
                background-color: rgba(60, 60, 60, 0.7);
                color: #cccccc;
                padding: 4px 8px;
                margin-right: 1px;
                border-top-left-radius: 3px;
                border-top-right-radius: 3px;
                min-width: 60px;
                font-size: 11px;
                font-weight: normal;
                border: 1px solid rgba(255, 255, 255, 0.1);
            }
            QTabBar::tab:selected {
                background-color: rgba(100, 100, 100, 0.8);
                color: #ffffff;
                font-weight: bold;
                border: 1px solid rgba(150, 150, 150, 0.6);
            }
            QTabBar::tab:hover {
                background-color: rgba(74, 74, 74, 0.8);
                color: #ffffff;
                border: 1px solid rgba(255, 255, 255, 0.2);
            }
            QTabBar::tab:!selected {
                border-bottom: 1px solid rgba(255, 255, 255, 0.1);
            }
        """)
        
        # Create room-based tabs
        self.create_overview_tab()
        self.create_room_tab("Bedroom 1", [0, 1, 2, 19])  # L1, L2, L3, AC1
        self.create_room_tab("Bedroom 2", [3, 4, 5])      # L4, L5, L6
        self.create_room_tab("Bedroom 3", [6, 7, 8, 17, 20])  # L7, L8, L9, TV1, AC2
        self.create_room_tab("Kitchen", [9, 10])          # L10, L11
        self.create_room_tab("Living Room", [11, 12, 13, 18, 21]) # L12, L13, L14, TV2, AC3
        self.create_room_tab("Bathroom", [14])            # L15
        self.create_room_tab("Outside", [15, 16])         # L16, L17
        self.create_security_cameras_tab()
        
        parent_layout.addWidget(self.tab_widget)
    
    def create_overview_tab(self):
        """Create the overview tab with all devices and global controls."""
        overview_tab = QWidget()
        overview_tab.setStyleSheet("""
            QWidget {
                background-color: transparent;
            }
        """)
        overview_layout = QVBoxLayout(overview_tab)
        overview_layout.setContentsMargins(8, 8, 8, 8)
        overview_layout.setSpacing(6)
        
        # Overview header
        overview_header = QLabel("Home Overview")
        overview_header.setStyleSheet("""
            font-size: 16px;
            font-weight: bold;
            color: #ffffff;
            padding: 6px 0px;
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
        self.device_count_label = QLabel("0/22 devices ON")
        self.device_count_label.setStyleSheet("""
            font-size: 14px;
            color: #cccccc;
            padding: 5px 0px;
        """)
        global_controls_layout.addWidget(self.device_count_label)
        global_controls_layout.addStretch()
        
        overview_layout.addLayout(global_controls_layout)
        
        # Scene controls
        scenes_header = QLabel("Light Scenes")
        scenes_header.setStyleSheet("""
            font-size: 14px;
            font-weight: bold;
            color: #ffffff;
            padding: 10px 0px 4px 0px;
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
        
        self.tab_widget.addTab(overview_tab, "Overview")
    
    def create_room_tab(self, room_name, device_indices):
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
            color: #ffffff;
            padding: 6px 0px;
        """)
        room_layout.addWidget(room_header)
        
        # Room controls
        room_controls_layout = QHBoxLayout()
        room_controls_layout.setSpacing(8)
        
        # Room on/off buttons
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
        room_device_count = len(device_indices)
        room_status_label = QLabel(f"{room_device_count} devices in this room")
        room_status_label.setStyleSheet("""
            font-size: 12px;
            color: #cccccc;
            padding: 5px 0px;
        """)
        room_controls_layout.addWidget(room_status_label)
        room_controls_layout.addStretch()
        
        room_layout.addLayout(room_controls_layout)
        
        # Room devices
        devices_header = QLabel("Devices")
        devices_header.setStyleSheet("""
            font-size: 12px;
            font-weight: bold;
            color: #ffffff;
            padding: 10px 0px 4px 0px;
        """)
        room_layout.addWidget(devices_header)
        
        # Create device controls for this room
        for i, device_idx in enumerate(device_indices):
            device_row = QHBoxLayout()
            device_row.setSpacing(8)
            
            # Determine device type and global number
            device_type = self.device_types.get(device_idx, "L")
            if device_type == "TV":
                global_label = f"TV{device_idx-16}"
            elif device_type == "AC":
                global_label = f"AC{device_idx-18}"
            else:
                global_label = f"L{device_idx+1}"
            
            # Device label
            device_label = QLabel(f"{global_label} ({i+1}):")
            device_label.setStyleSheet("""
                font-size: 12px;
                color: #cccccc;
                font-weight: bold;
                min-width: 60px;
            """)
            device_row.addWidget(device_label)
            
            # Device button
            device_btn = self.light_buttons[device_idx]
            device_row.addWidget(device_btn)
            device_row.addStretch()
            
            room_layout.addLayout(device_row)
        
        room_layout.addStretch()
        self.tab_widget.addTab(room_tab, room_name)
    
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
            color: #ffffff;
            padding: 6px 0px;
        """)
        cameras_layout.addWidget(cameras_header)
        
        # Camera status overview
        status_group = QWidget()
        status_group.setStyleSheet("""
            QWidget {
                background-color: rgba(60, 60, 60, 0.3);
                border-radius: 8px;
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
        self.camera_status_label = QLabel("8 cameras online")
        self.camera_status_label.setStyleSheet("""
            font-size: 12px;
            color: #cccccc;
            padding: 2px 0px;
        """)
        status_layout.addWidget(self.camera_status_label)
        
        self.recording_status_label = QLabel("Recording: 3 cameras")
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
            color: #ffffff;
            padding: 15px 0px 5px 0px;
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
            ("Back Door", "CAM2"),
            ("Living Room", "CAM3"),
            ("Kitchen", "CAM4"),
            ("Bedroom 1", "CAM5"),
            ("Bedroom 2", "CAM6"),
            ("Bedroom 3", "CAM7"),
            ("Garage", "CAM8")
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
        
        self.tab_widget.addTab(cameras_tab, "Security")
    
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
                    border-radius: 6px;
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
                    border-radius: 6px;
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
                    border-radius: 6px;
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
                    border-radius: 6px;
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
            self.camera_status_label.setText(f"{on_count}/8 cameras online")
        
        if hasattr(self, 'recording_status_label'):
            recording_count = sum(self.recording_states)
            self.recording_status_label.setText(f"Recording: {recording_count} cameras")
    
    def start_all_recording(self):
        """Start recording on all cameras that are on."""
        for i in range(8):
            if self.camera_states[i]:
                self.recording_states[i] = True
                self.update_recording_button(i)
        
        self.update_camera_status()
        if hasattr(self, 'status_label'):
            self.status_label.setText("Started recording on all active cameras")
    
    def stop_all_recording(self):
        """Stop recording on all cameras."""
        for i in range(8):
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
                    stop:0 #555555, stop:1 #444444);
                color: #ffffff;
                font-weight: bold;
                font-size: 12px;
                padding: 8px 16px;
                border: 1px solid #666666;
                border-radius: 4px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 #666666, stop:1 #555555);
                border: 1px solid #777777;
            }
            QPushButton:pressed {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 #444444, stop:1 #333333);
            }
        """
    
    def apply_scene(self, scene_index):
        """Apply a specific scene."""
        if not hasattr(self, 'current_scene'):
            self.current_scene = 0
        
        scenes = [
            "Evening",    # Scene 0: All lights on
            "Night",      # Scene 1: Every other light
            "Party",      # Scene 2: Random pattern
            "Work",       # Scene 3: First 8 lights
            "Relax"       # Scene 4: Last 8 lights
        ]
        
        if scene_index == 0:  # Evening - All on
            for i in range(22):
                self.light_states[i] = True
        elif scene_index == 1:  # Night - Every other
            for i in range(22):
                self.light_states[i] = (i % 2 == 0)
        elif scene_index == 2:  # Party - Random pattern
            import random
            for i in range(22):
                self.light_states[i] = random.choice([True, False])
        elif scene_index == 3:  # Work - First 8
            for i in range(22):
                self.light_states[i] = (i < 8)
        elif scene_index == 4:  # Relax - Last 8
            for i in range(22):
                self.light_states[i] = (i >= 9)
        
        # Update all buttons
        for i in range(22):
            self.update_light_button(i)
        
        self.update_light_status()
        
        if hasattr(self, 'status_label'):
            self.status_label.setText(f"Applied {scenes[scene_index]} scene")
    
    def get_light_button_style(self, is_on):
        """Get the toggle button style for light buttons."""
        if is_on:
            return """
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #888888, stop:1 #666666);
                    color: white;
                    font-weight: bold;
                    font-size: 10px;
                    border: 2px solid #888888;
                    border-radius: 8px;
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
                    border-radius: 8px;
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
            self.view_status.setText("3D View")
            self.view_status.setStyleSheet("font-size: 18px; font-weight: bold; color: #4CAF50; padding: 10px;")
        if hasattr(self, 'status_label'):
            self.status_label.setText("3D View - Drag to rotate, wheel to zoom")
    
    def show_2d_view(self):
        """Show the 2D view."""
        self.current_view = "2d"
        self.panel_3d.setVisible(False)
        self.panel_2d.setVisible(True)
        if hasattr(self, 'view_status'):
            self.view_status.setText("2D View")
            self.view_status.setStyleSheet("font-size: 18px; font-weight: bold; color: #2196F3; padding: 10px;")
        if hasattr(self, 'status_label'):
            self.status_label.setText("2D View - Click rooms, wheel to zoom")
    
    
    def setup_connections(self):
        """Setup signal connections."""
        # 3D viewer signals
        self.viewer_3d.view_changed.connect(self.on_3d_view_changed)
        
        # 2D viewer signals
        self.viewer_2d.room_selected.connect(self.on_room_selected)
        self.viewer_2d.view_changed.connect(self.on_2d_view_changed)
    
    
    def setup_status_bar(self):
        """Setup simple status bar."""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
        # Simple status label
        self.status_label = QLabel("Ready")
        self.status_bar.addWidget(self.status_label)
    
    
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
            self.status_label.setText("3D View - Drag to rotate, wheel to zoom")
        else:
            self.status_label.setText("2D View - Click rooms, wheel to zoom")
    
    
    def on_3d_view_changed(self, x, y, z):
        """Handle 3D view changes."""
        if self.sync_views:
            # Update 2D view based on 3D camera position
            # This is a simplified synchronization
            pass
    
    def on_2d_view_changed(self, pan_x, pan_y, zoom):
        """Handle 2D view changes."""
        if self.sync_views:
            # Update 3D view based on 2D view
            # This is a simplified synchronization
            pass
    
    def on_room_selected(self, room_name):
        """Handle room selection."""
        self.current_room = room_name
        if self.current_view == "2d":
            self.status_label.setText(f"2D View - Selected room: {room_name}")
        else:
            self.status_label.setText(f"3D View - Selected room: {room_name}")
    
    
    def reset_all_views(self):
        """Reset both views."""
        self.viewer_3d.reset_view()
        self.viewer_2d.reset_view()
        if hasattr(self, 'status_label'):
            self.status_label.setText("Views reset")
    
    def toggle_sync(self):
        """Toggle synchronization."""
        self.sync_views = not self.sync_views
        if hasattr(self, 'status_label'):
            self.status_label.setText(f"View sync: {'ON' if self.sync_views else 'OFF'}")
    
    def toggle_light(self, light_index):
        """Toggle a specific light on/off."""
        self.light_states[light_index] = not self.light_states[light_index]
        self.update_light_button(light_index)
        self.update_light_status()
        
        # Update status
        if hasattr(self, 'status_label'):
            state = "ON" if self.light_states[light_index] else "OFF"
            # Find which room this device belongs to
            room_name = "Unknown"
            local_num = 1
            for room, devices in self.room_layout.items():
                if light_index in devices:
                    room_name = room
                    local_num = devices.index(light_index) + 1
                    break
            
            # Determine device type and global label
            device_type = self.device_types.get(light_index, "L")
            if device_type == "TV":
                global_label = f"TV{light_index-16}"
            elif device_type == "AC":
                global_label = f"AC{light_index-18}"
            else:
                global_label = f"L{light_index+1}"
            
            self.status_label.setText(f"{room_name} - {global_label} ({local_num}) turned {state}")
    
    def update_light_button(self, light_index):
        """Update the visual appearance of a light button and its label."""
        button = self.light_buttons[light_index]
        label = self.light_labels[light_index]
        
        button.setText("ON" if self.light_states[light_index] else "OFF")
        button.setChecked(self.light_states[light_index])
        button.setStyleSheet(self.get_light_button_style(self.light_states[light_index]))
        
        # Update label color based on light state (if label exists)
        if label is not None:
            if self.light_states[light_index]:
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
    
    def update_light_status(self):
        """Update the device status counter."""
        on_count = sum(self.light_states)
        
        if hasattr(self, 'light_status'):
            self.light_status.setText(f"{on_count}/22 ON")
        
        if hasattr(self, 'device_count_label'):
            self.device_count_label.setText(f"{on_count}/22 devices ON")
    
    def all_lights_on(self):
        """Turn all devices on."""
        for i in range(22):
            self.light_states[i] = True
            self.update_light_button(i)
        
        self.update_light_status()
        if hasattr(self, 'status_label'):
            self.status_label.setText("All devices turned ON")
    
    def all_lights_off(self):
        """Turn all devices off."""
        for i in range(22):
            self.light_states[i] = False
            self.update_light_button(i)
        
        self.update_light_status()
        if hasattr(self, 'status_label'):
            self.status_label.setText("All devices turned OFF")
    
    def room_lights_on(self, room_name):
        """Turn on all devices in a specific room."""
        if room_name in self.room_layout:
            for device_idx in self.room_layout[room_name]:
                self.light_states[device_idx] = True
                self.update_light_button(device_idx)
            
            self.update_light_status()
            if hasattr(self, 'status_label'):
                self.status_label.setText(f"All devices in {room_name} turned ON")
    
    def room_lights_off(self, room_name):
        """Turn off all devices in a specific room."""
        if room_name in self.room_layout:
            for device_idx in self.room_layout[room_name]:
                self.light_states[device_idx] = False
                self.update_light_button(device_idx)
            
            self.update_light_status()
            if hasattr(self, 'status_label'):
                self.status_label.setText(f"All devices in {room_name} turned OFF")
    
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
                border-radius: 8px;
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
                border-radius: 4px;
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
                border-radius: 8px;
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
                border-radius: 4px;
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
                border-radius: 4px;
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
                    stop:0 #4CAF50, stop:1 #45a049);
                color: #ffffff;
                font-weight: bold;
                font-size: 14px;
                padding: 8px 20px;
                border: none;
                border-radius: 6px;
                min-width: 80px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 #5CBF60, stop:1 #55b059);
            }
            QPushButton:pressed {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 #3d8b40, stop:1 #357a38);
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
                border-radius: 6px;
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
                background-color: #2b2b2b;
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
