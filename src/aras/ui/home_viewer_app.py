"""
Main PyQt6 application for 3D and 2D home visualization.
"""

import sys
import os
import math
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QSplitter, QLabel, QPushButton, 
                            QGroupBox, QSlider, QCheckBox, QStatusBar)
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
        
        # Add close button
        self.add_close_button()
        
        # Setup keyboard shortcuts
        self.setup_shortcuts()
        
        # State
        self.sync_views = True
        self.current_room = None
        
        # Load initial model
        self.load_home_model()
    
    def init_ui(self):
        """Initialize the user interface."""
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        main_layout = QHBoxLayout(central_widget)
        
        # Create splitter for resizable panels
        splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(splitter)
        
        # Left panel - 3D viewer
        self.create_3d_panel(splitter)
        
        # Right panel - 2D viewer and controls
        self.create_2d_panel(splitter)
        
        # Set splitter proportions
        splitter.setSizes([700, 700])
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
    
    def create_3d_panel(self, parent):
        """Create the 3D viewer panel."""
        # 3D panel container
        panel_3d = QWidget()
        layout_3d = QVBoxLayout(panel_3d)
        
        # 3D viewer title
        title_3d = QLabel("3D Home View")
        title_3d.setStyleSheet("font-size: 16px; font-weight: bold; padding: 5px;")
        layout_3d.addWidget(title_3d)
        
        # 3D viewer widget
        self.viewer_3d = Home3DViewer()
        layout_3d.addWidget(self.viewer_3d)
        
        # 3D controls
        controls_3d = self.create_3d_controls()
        layout_3d.addWidget(controls_3d)
        
        parent.addWidget(panel_3d)
    
    def create_2d_panel(self, parent):
        """Create the 2D viewer panel."""
        # 2D panel container
        panel_2d = QWidget()
        layout_2d = QVBoxLayout(panel_2d)
        
        # 2D viewer title
        title_2d = QLabel("2D Floor Plan")
        title_2d.setStyleSheet("font-size: 16px; font-weight: bold; padding: 5px;")
        layout_2d.addWidget(title_2d)
        
        # 2D viewer widget
        self.viewer_2d = Home2DViewer()
        layout_2d.addWidget(self.viewer_2d)
        
        # 2D controls and info
        controls_2d = self.create_2d_controls()
        layout_2d.addWidget(controls_2d)
        
        parent.addWidget(panel_2d)
    
    def create_3d_controls(self):
        """Create 3D viewer controls."""
        group = QGroupBox("3D Controls")
        layout = QVBoxLayout(group)
        
        # Camera controls
        camera_group = QGroupBox("Camera")
        camera_layout = QVBoxLayout(camera_group)
        
        # Distance slider
        distance_layout = QHBoxLayout()
        distance_layout.addWidget(QLabel("Distance:"))
        self.distance_slider = QSlider(Qt.Orientation.Horizontal)
        self.distance_slider.setRange(1, 50)
        self.distance_slider.setValue(3)
        distance_layout.addWidget(self.distance_slider)
        self.distance_label = QLabel("3.0")
        distance_layout.addWidget(self.distance_label)
        camera_layout.addLayout(distance_layout)
        
        # Rotation controls
        rotation_layout = QHBoxLayout()
        rotation_layout.addWidget(QLabel("Rotation X:"))
        self.rotation_x_slider = QSlider(Qt.Orientation.Horizontal)
        self.rotation_x_slider.setRange(-180, 180)
        self.rotation_x_slider.setValue(90)
        rotation_layout.addWidget(self.rotation_x_slider)
        self.rotation_x_label = QLabel("90°")
        rotation_layout.addWidget(self.rotation_x_label)
        camera_layout.addLayout(rotation_layout)
        
        rotation_y_layout = QHBoxLayout()
        rotation_y_layout.addWidget(QLabel("Rotation Y:"))
        self.rotation_y_slider = QSlider(Qt.Orientation.Horizontal)
        self.rotation_y_slider.setRange(-90, 90)
        self.rotation_y_slider.setValue(40)
        rotation_y_layout.addWidget(self.rotation_y_slider)
        self.rotation_y_label = QLabel("40°")
        rotation_y_layout.addWidget(self.rotation_y_label)
        camera_layout.addLayout(rotation_y_layout)
        
        layout.addWidget(camera_group)
        
        # Model controls
        model_group = QGroupBox("Model")
        model_layout = QVBoxLayout(model_group)
        
        # Auto rotate
        self.auto_rotate_cb = QCheckBox("Auto Rotate")
        model_layout.addWidget(self.auto_rotate_cb)
        
        # Reset view button
        reset_btn = QPushButton("Reset View")
        model_layout.addWidget(reset_btn)
        
        layout.addWidget(model_group)
        
        # Connect signals
        self.distance_slider.valueChanged.connect(self.update_3d_distance)
        self.rotation_x_slider.valueChanged.connect(self.update_3d_rotation_x)
        self.rotation_y_slider.valueChanged.connect(self.update_3d_rotation_y)
        self.auto_rotate_cb.toggled.connect(self.toggle_auto_rotate)
        reset_btn.clicked.connect(self.reset_3d_view)
        
        return group
    
    def create_2d_controls(self):
        """Create 2D viewer controls."""
        group = QGroupBox("2D Controls")
        layout = QVBoxLayout(group)
        
        # View controls
        view_group = QGroupBox("View")
        view_layout = QVBoxLayout(view_group)
        
        # Zoom controls
        zoom_layout = QHBoxLayout()
        zoom_layout.addWidget(QLabel("Zoom:"))
        self.zoom_slider = QSlider(Qt.Orientation.Horizontal)
        self.zoom_slider.setRange(10, 500)
        self.zoom_slider.setValue(100)
        zoom_layout.addWidget(self.zoom_slider)
        self.zoom_label = QLabel("100%")
        zoom_layout.addWidget(self.zoom_label)
        view_layout.addLayout(zoom_layout)
        
        # Reset view button
        reset_2d_btn = QPushButton("Reset View")
        view_layout.addWidget(reset_2d_btn)
        
        layout.addWidget(view_group)
        
        
        # Synchronization
        sync_group = QGroupBox("Synchronization")
        sync_layout = QVBoxLayout(sync_group)
        
        self.sync_views_cb = QCheckBox("Sync Views")
        self.sync_views_cb.setChecked(True)
        sync_layout.addWidget(self.sync_views_cb)
        
        layout.addWidget(sync_group)
        
        # Connect signals
        self.zoom_slider.valueChanged.connect(self.update_2d_zoom)
        reset_2d_btn.clicked.connect(self.reset_2d_view)
        self.sync_views_cb.toggled.connect(self.toggle_sync_views)
        
        return group
    
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
    
    def add_close_button(self):
        """Add a close button to the interface."""
        # Add close button to the 3D controls
        close_btn = QPushButton("Close")
        close_btn.setStyleSheet("QPushButton { background-color: #ff4444; color: white; font-weight: bold; }")
        close_btn.clicked.connect(self.close)
        
        # Add to 3D controls panel
        if hasattr(self, 'viewer_3d'):
            # Find the 3D controls group and add close button
            for child in self.findChildren(QGroupBox):
                if child.title() == "Model":
                    layout = child.layout()
                    layout.addWidget(close_btn)
                    break
    
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
        
        # Close application
        close_action = QAction("Close", self)
        close_action.setShortcut("Escape")
        close_action.triggered.connect(self.close)
        self.addAction(close_action)
    
    def load_home_model(self):
        """Load the home model."""
        self.status_label.setText("Loading home model...")
        
        # The model loading is handled in the 3D viewer constructor
        # This is just for UI feedback
        QTimer.singleShot(1000, self.on_model_loaded)
    
    def on_model_loaded(self):
        """Called when model loading is complete."""
        self.status_label.setText("Ready")
    
    def update_3d_distance(self, value):
        """Update 3D camera distance."""
        self.viewer_3d.camera_distance = value
        self.distance_label.setText(f"{value}.0")
        self.viewer_3d.update()
    
    def update_3d_rotation_x(self, value):
        """Update 3D camera rotation X."""
        self.viewer_3d.camera_angle_x = math.radians(value)
        self.rotation_x_label.setText(f"{value}°")
        self.viewer_3d.update()
    
    def update_3d_rotation_y(self, value):
        """Update 3D camera rotation Y."""
        self.viewer_3d.camera_angle_y = math.radians(value)
        self.rotation_y_label.setText(f"{value}°")
        self.viewer_3d.update()
    
    def toggle_auto_rotate(self, checked):
        """Toggle auto rotation."""
        self.viewer_3d.auto_rotate = checked
        if checked:
            self.viewer_3d.timer.start(16)
        else:
            self.viewer_3d.timer.stop()
    
    def reset_3d_view(self):
        """Reset 3D view."""
        self.viewer_3d.reset_view()
        self.distance_slider.setValue(3)
        self.rotation_x_slider.setValue(90)
        self.rotation_y_slider.setValue(40)
        self.auto_rotate_cb.setChecked(False)
    
    def update_2d_zoom(self, value):
        """Update 2D zoom."""
        zoom_factor = value / 100.0
        self.viewer_2d.zoom_factor = zoom_factor
        self.zoom_label.setText(f"{value}%")
        # Apply zoom transformation
        self.viewer_2d.resetTransform()
        self.viewer_2d.scale(zoom_factor, zoom_factor)
    
    def reset_2d_view(self):
        """Reset 2D view."""
        self.viewer_2d.reset_view()
        self.zoom_slider.setValue(100)
    
    def toggle_sync_views(self):
        """Toggle view synchronization."""
        self.sync_views = self.sync_views_cb.isChecked()
        self.status_label.setText(f"View sync: {'ON' if self.sync_views else 'OFF'}")
    
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
        self.status_label.setText(f"Selected room: {room_name}")
    
    
    def reset_all_views(self):
        """Reset both views."""
        self.reset_3d_view()
        self.reset_2d_view()
        self.status_label.setText("All views reset")
    
    def toggle_sync(self):
        """Toggle synchronization."""
        self.sync_views_cb.setChecked(not self.sync_views_cb.isChecked())
        self.toggle_sync_views()
    
    
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
