"""
Qt application for Aras Agent.
"""

import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QIcon

from .main_window import MainWindow
from ..config import settings


class ArasApp(QApplication):
    """Main Qt application for Aras Agent."""
    
    def __init__(self, argv):
        super().__init__(argv)
        self.setApplicationName(settings.agent_name)
        self.setApplicationVersion("0.1.0")
        self.setOrganizationName("Aras Agent")
        
        # Set application icon (if available)
        # self.setWindowIcon(QIcon("path/to/icon.png"))
        
        # Create main window
        self.main_window = MainWindow()
        self.main_window.show()
        
        # Setup update timer
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_status)
        self.update_timer.start(1000)  # Update every second
    
    def update_status(self):
        """Update status information."""
        # This would update system status, resource usage, etc.
        pass


def run_ui():
    """Run the Qt UI application."""
    app = ArasApp(sys.argv)
    return app.exec()
