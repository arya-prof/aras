"""
Main PyQt6 application for 3D and 2D home visualization.
"""

import sys
import os
import math
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QLabel, QStatusBar)
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
    
    def init_ui(self):
        """Initialize the user interface."""
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        main_layout = QVBoxLayout(central_widget)
        
        # Create view switcher
        self.create_view_switcher(main_layout)
        
        # Create stacked widget for views
        self.stacked_widget = QWidget()
        self.stacked_layout = QHBoxLayout(self.stacked_widget)
        main_layout.addWidget(self.stacked_widget)
        
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
    
    def create_3d_panel(self):
        """Create the 3D viewer panel."""
        # 3D panel container
        self.panel_3d = QWidget()
        layout_3d = QVBoxLayout(self.panel_3d)
        
        # 3D viewer widget
        self.viewer_3d = Home3DViewer()
        layout_3d.addWidget(self.viewer_3d)
        
        # Add to stacked layout
        self.stacked_layout.addWidget(self.panel_3d)
    
    def create_2d_panel(self):
        """Create the 2D viewer panel."""
        # 2D panel container
        self.panel_2d = QWidget()
        layout_2d = QVBoxLayout(self.panel_2d)
        
        # 2D viewer widget
        self.viewer_2d = Home2DViewer()
        layout_2d.addWidget(self.viewer_2d)
        
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
