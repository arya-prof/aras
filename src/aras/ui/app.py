"""
Headless Qt application for Aras Agent.
"""

import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer

from .circular_indicator import HeadlessAgentWindow
from ..config import settings


class ArasApp(QApplication):
    """Main Qt application for Aras Agent (headless only)."""
    
    def __init__(self, argv):
        super().__init__(argv)
        self.setApplicationName(settings.agent_name)
        self.setApplicationVersion("0.1.0")
        self.setOrganizationName("Aras Agent")
        
        # Create headless window with circular indicator
        self.main_window = HeadlessAgentWindow()
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


def run_headless():
    """Run the headless UI with circular indicator."""
    app = ArasApp(sys.argv)
    return app.exec()
