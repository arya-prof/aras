"""
Main PyQt6 application for 3D and 2D home visualization.
"""

import sys
import os
import math
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QLabel, QStatusBar, QPushButton, QGridLayout, QSizePolicy)
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
        
        # Light states
        self.light_states = [False] * 17  # 17 lights, all initially off
    
    def init_ui(self):
        """Initialize the user interface."""
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout - horizontal split
        main_layout = QHBoxLayout(central_widget)
        
        # Left side - Viewer (50% of width)
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        
        # Create view switcher
        self.create_view_switcher(left_layout)
        
        # Create stacked widget for views
        self.stacked_widget = QWidget()
        self.stacked_layout = QHBoxLayout(self.stacked_widget)
        left_layout.addWidget(self.stacked_widget, 1)  # Add stretch factor to fill space
        
        # Right side - Controls (50% of width)
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        
        # Create light control panel at the top
        self.create_light_panel(right_layout)
        
        # Add stretch to push panel to top
        right_layout.addStretch()
        
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
        
        parent_layout.addLayout(switcher_layout)
    
    def create_light_panel(self, parent_layout):
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
        
        # Light status indicator
        self.light_status = QLabel("0/17 ON")
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
        
        # Scene button
        scene_btn = QPushButton("Scene")
        scene_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        scene_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 #666666, stop:1 #444444);
                color: #ffffff;
                font-weight: bold;
                font-size: 12px;
                padding: 2px 4px;
                border: 1px solid #777777;
                border-radius: 4px;
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
        scene_btn.clicked.connect(self.toggle_scene)
        control_layout.addWidget(scene_btn)
        
        # Add control buttons to header layout
        header_layout.addLayout(control_layout)
        
        light_layout.addLayout(header_layout)
        
        # Create vertical list for light controls
        light_list_layout = QVBoxLayout()
        light_list_layout.setSpacing(0)
        
        # Create 17 light controls in vertical list
        self.light_buttons = []
        self.light_labels = []
        for i in range(17):
            # Create horizontal layout for each light
            light_row = QHBoxLayout()
            light_row.setSpacing(0)
            
            # Create label for the light
            label = QLabel(f"L{i+1}:")
            label.setStyleSheet("""
                font-size: 12px;
                color: #ffffff;
                font-weight: bold;
                min-width: 30px;
            """)
            label.setAlignment(Qt.AlignmentFlag.AlignLeft)
            
            # Create button
            btn = QPushButton()
            btn.setMinimumSize(60, 25)
            btn.setMaximumSize(60, 25)
            btn.setText("OFF")
            btn.setCheckable(True)
            btn.setStyleSheet(self.get_light_button_style(False))
            btn.clicked.connect(lambda checked, idx=i: self.toggle_light(idx))
            
            self.light_buttons.append(btn)
            self.light_labels.append(label)
            
            # Add label and button to row
            light_row.addWidget(label)
            light_row.addWidget(btn)
            light_row.addStretch()  # Push content to left
            
            # Add row to main layout
            light_list_layout.addLayout(light_row)
        
        light_layout.addLayout(light_list_layout)
        
        parent_layout.addWidget(light_panel)
    
    def get_light_button_style(self, is_on):
        """Get the toggle button style for light buttons."""
        if is_on:
            return """
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #4CAF50, stop:1 #45a049);
                    color: white;
                    font-weight: bold;
                    font-size: 10px;
                    border: 2px solid #4CAF50;
                    border-radius: 8px;
                }
                QPushButton:hover {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #5CBF60, stop:1 #4CAF50);
                    border: 2px solid #5CBF60;
                }
                QPushButton:pressed {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #45a049, stop:1 #3d8b40);
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
            self.status_label.setText(f"Light {light_index + 1} turned {state}")
    
    def update_light_button(self, light_index):
        """Update the visual appearance of a light button and its label."""
        button = self.light_buttons[light_index]
        label = self.light_labels[light_index]
        
        button.setText("ON" if self.light_states[light_index] else "OFF")
        button.setChecked(self.light_states[light_index])
        button.setStyleSheet(self.get_light_button_style(self.light_states[light_index]))
        
        # Update label color based on light state
        if self.light_states[light_index]:
            label.setStyleSheet("""
                font-size: 12px;
                color: #4CAF50;
                font-weight: bold;
                min-width: 30px;
            """)
        else:
            label.setStyleSheet("""
                font-size: 12px;
                color: #ffffff;
                font-weight: bold;
                min-width: 30px;
            """)
    
    def update_light_status(self):
        """Update the light status counter."""
        if hasattr(self, 'light_status'):
            on_count = sum(self.light_states)
            self.light_status.setText(f"{on_count}/17 ON")
    
    def all_lights_on(self):
        """Turn all lights on."""
        for i in range(17):
            self.light_states[i] = True
            self.update_light_button(i)
        
        self.update_light_status()
        if hasattr(self, 'status_label'):
            self.status_label.setText("All lights turned ON")
    
    def all_lights_off(self):
        """Turn all lights off."""
        for i in range(17):
            self.light_states[i] = False
            self.update_light_button(i)
        
        self.update_light_status()
        if hasattr(self, 'status_label'):
            self.status_label.setText("All lights turned OFF")
    
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
            for i in range(17):
                self.light_states[i] = True
        elif self.current_scene == 1:  # Night - Every other
            for i in range(17):
                self.light_states[i] = (i % 2 == 0)
        elif self.current_scene == 2:  # Party - Random pattern
            import random
            for i in range(17):
                self.light_states[i] = random.choice([True, False])
        elif self.current_scene == 3:  # Work - First 8
            for i in range(17):
                self.light_states[i] = (i < 8)
        elif self.current_scene == 4:  # Relax - Last 8
            for i in range(17):
                self.light_states[i] = (i >= 9)
        
        # Update all buttons
        for i in range(17):
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
