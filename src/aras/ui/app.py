"""
Qt application for Aras Agent.
"""

import sys
import argparse
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QIcon

from .main_window import MainWindow
from .circular_indicator import HeadlessAgentWindow
from ..config import settings


class ArasApp(QApplication):
    """Main Qt application for Aras Agent."""
    
    def __init__(self, argv, headless=True):
        super().__init__(argv)
        self.setApplicationName(settings.agent_name)
        self.setApplicationVersion("0.1.0")
        self.setOrganizationName("Aras Agent")
        
        # Set application icon (if available)
        # self.setWindowIcon(QIcon("path/to/icon.png"))
        
        self.headless = headless
        
        if headless:
            # Create headless window with circular indicator
            self.main_window = HeadlessAgentWindow()
            self.main_window.show()
        else:
            # Create full UI window
            self.main_window = MainWindow()
            self.main_window.show()
        
        # Setup update timer
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_status)
        self.update_timer.start(1000)  # Update every second
    
    def update_status(self):
        """Update status information."""
        # This would update system status, resource usage, etc.
        if hasattr(self.main_window, 'set_agent_status'):
            # Update agent status for headless mode
            # This would check actual agent status
            import time
            current_time = int(time.time())
            agent_active = (current_time % 10) < 5  # Demo: active 50% of the time
            self.main_window.set_agent_status(agent_active)


def run_ui(headless=True):
    """Run the Qt UI application."""
    app = ArasApp(sys.argv, headless=headless)
    return app.exec()


def run_headless():
    """Run the headless UI with circular indicator."""
    return run_ui(headless=True)


def run_full_ui():
    """Run the full UI interface."""
    return run_ui(headless=False)
