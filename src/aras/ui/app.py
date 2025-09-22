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
    # Check for existing instance to prevent multiple instances
    import os
    import tempfile
    import sys
    
    lock_file_path = os.path.join(tempfile.gettempdir(), "aras_agent.lock")
    
    # Check if lock file exists and if the process is still running
    if os.path.exists(lock_file_path):
        try:
            with open(lock_file_path, 'r') as f:
                pid = int(f.read().strip())
            
            # Check if process is still running
            if sys.platform == "win32":
                import psutil
                if psutil.pid_exists(pid):
                    print("Error: ARAS Agent is already running!")
                    print("Only one instance of ARAS Agent can run at a time.")
                    print("Please close the existing instance or restart your system.")
                    return 1
            else:
                # Unix-like systems
                try:
                    os.kill(pid, 0)  # Check if process exists
                    print("Error: ARAS Agent is already running!")
                    print("Only one instance of ARAS Agent can run at a time.")
                    print("Please close the existing instance or restart your system.")
                    return 1
                except OSError:
                    # Process doesn't exist, remove stale lock file
                    os.unlink(lock_file_path)
        except (ValueError, FileNotFoundError):
            # Invalid lock file, remove it
            try:
                os.unlink(lock_file_path)
            except:
                pass
    
    # Create lock file
    try:
        with open(lock_file_path, 'w') as f:
            f.write(str(os.getpid()))
        
        print("Starting ARAS Agent - Single instance check passed")
        
        app = ArasApp(sys.argv)
        result = app.exec()
        
        # Clean up lock file
        try:
            os.unlink(lock_file_path)
        except:
            pass
            
        return result
        
    except Exception as e:
        print(f"Error: Failed to start ARAS Agent: {e}")
        return 1
