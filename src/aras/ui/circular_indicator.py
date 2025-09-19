"""
Circular indicator widget for headless agent status display.
"""

import sys
from PyQt6.QtWidgets import QWidget, QApplication
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, pyqtProperty, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QRadialGradient, QFont
from PyQt6.QtCore import QRect

from .voice_handler import VoiceCommandProcessor


class CircularIndicator(QWidget):
    """A circular indicator widget that shows agent status with glowing effect."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(120, 120)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # Status properties
        self._is_active = False
        self._voice_listening = False
        self._voice_processing = False
        self._pulse_animation = None
        self._pulse_radius = 0
        self._opacity = 1.0
        self._last_command = ""
        self._last_response = ""
        
        
        # Colors
        self.active_color = QColor(0, 255, 100)  # Green when active
        self.inactive_color = QColor(100, 100, 100)  # Gray when inactive
        self.voice_color = QColor(0, 150, 255)  # Blue when listening
        self.processing_color = QColor(255, 165, 0)  # Orange when processing
        self.glow_color = QColor(0, 255, 100, 50)  # Glow effect
        
        # Setup pulse animation
        self.setup_animation()
        
        # Start with inactive state
        self.set_active(False)
    
    def setup_animation(self):
        """Setup the pulse animation."""
        self._pulse_animation = QPropertyAnimation(self, b"pulse_radius")
        self._pulse_animation.setDuration(2000)
        self._pulse_animation.setLoopCount(-1)  # Infinite loop
        self._pulse_animation.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self._pulse_animation.setStartValue(0)
        self._pulse_animation.setEndValue(60)
    
    @pyqtProperty(int)
    def pulse_radius(self):
        return self._pulse_radius
    
    @pulse_radius.setter
    def pulse_radius(self, value):
        self._pulse_radius = value
        self.update()
    
    def set_active(self, active: bool):
        """Set the active state of the indicator."""
        self._is_active = active
        if active:
            self._pulse_animation.start()
            self._opacity = 1.0
        else:
            self._pulse_animation.stop()
            self._opacity = 0.6
        self.update()
    
    def set_voice_listening(self, listening: bool):
        """Set the voice listening state of the indicator."""
        self._voice_listening = listening
        self.update()
    
    def set_voice_processing(self, processing: bool):
        """Set voice processing status."""
        self._voice_processing = processing
        self.update()
    
    def set_last_command(self, command: str):
        """Set the last voice command."""
        self._last_command = command
        self.update()
    
    def set_last_response(self, response: str):
        """Set the last voice response."""
        self._last_response = response
        self.update()
    
    def is_active(self) -> bool:
        """Get the active state."""
        return self._is_active
    
    def paintEvent(self, event):
        """Paint the circular indicator."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Get widget dimensions
        rect = self.rect()
        center = rect.center()
        radius = min(rect.width(), rect.height()) // 2 - 5
        
        # Set opacity
        painter.setOpacity(self._opacity)
        
        # Choose color based on status
        if self._voice_processing:
            # Orange when processing voice
            main_color = self.processing_color
            glow_color = QColor(255, 165, 0, 80)
        elif self._voice_listening:
            # Blue when listening
            main_color = self.voice_color
            glow_color = QColor(0, 150, 255, 80)
        elif self._is_active:
            # Green when active
            main_color = self.active_color
            glow_color = QColor(0, 255, 100, 80)
        else:
            # Gray when inactive
            main_color = self.inactive_color
            glow_color = QColor(100, 100, 100, 0)
        
        if self._is_active or self._voice_listening:
            # Draw glow effect
            if self._pulse_radius > 0:
                glow_rect = QRect(
                    center.x() - radius - self._pulse_radius,
                    center.y() - radius - self._pulse_radius,
                    (radius + self._pulse_radius) * 2,
                    (radius + self._pulse_radius) * 2
                )
                
                gradient = QRadialGradient(center.x(), center.y(), radius + self._pulse_radius)
                gradient.setColorAt(0, glow_color)
                gradient.setColorAt(0.7, QColor(glow_color.red(), glow_color.green(), glow_color.blue(), 20))
                gradient.setColorAt(1, QColor(glow_color.red(), glow_color.green(), glow_color.blue(), 0))
                
                painter.setBrush(QBrush(gradient))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawEllipse(glow_rect)
            
            # Draw main circle
            painter.setBrush(QBrush(main_color))
            painter.setPen(QPen(main_color.darker(150), 2))
            painter.drawEllipse(center.x() - radius, center.y() - radius, radius * 2, radius * 2)
            
            # Draw inner indicator
            inner_radius = radius // 3
            if self._voice_listening:
                # Draw microphone icon (simple representation)
                painter.setBrush(QBrush(QColor(255, 255, 255)))
                painter.setPen(QPen(QColor(255, 255, 255), 2))
                # Draw a simple microphone shape
                mic_rect = QRect(center.x() - inner_radius//2, center.y() - inner_radius, inner_radius, inner_radius)
                painter.drawRect(mic_rect)
                # Draw microphone stand
                painter.drawLine(center.x(), center.y() + inner_radius//2, center.x(), center.y() + inner_radius)
            else:
                # Draw inner dot
                painter.setBrush(QBrush(QColor(255, 255, 255)))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawEllipse(center.x() - inner_radius, center.y() - inner_radius, 
                                  inner_radius * 2, inner_radius * 2)
        else:
            # Draw inactive circle
            painter.setBrush(QBrush(main_color))
            painter.setPen(QPen(main_color.darker(150), 2))
            painter.drawEllipse(center.x() - radius, center.y() - radius, radius * 2, radius * 2)
            
            # Draw "A" for Agent
            painter.setPen(QPen(QColor(255, 255, 255), 3))
            font = QFont("Arial", 24, QFont.Weight.Bold)
            painter.setFont(font)
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "A")
    
    def mousePressEvent(self, event):
        """Handle mouse press events - pass to parent window for dragging."""
        # Pass mouse events to parent window for dragging
        if self.parent():
            self.parent().mousePressEvent(event)
        super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event):
        """Handle mouse move events - pass to parent window for dragging."""
        # Pass mouse events to parent window for dragging
        if self.parent():
            self.parent().mouseMoveEvent(event)
        super().mouseMoveEvent(event)
    
    def mouseReleaseEvent(self, event):
        """Handle mouse release events - pass to parent window for dragging."""
        # Pass mouse events to parent window for dragging
        if self.parent():
            self.parent().mouseReleaseEvent(event)
        super().mouseReleaseEvent(event)
    
    def enterEvent(self, event):
        """Handle mouse enter events."""
        if self.parent():
            self.parent().enterEvent(event)
        super().enterEvent(event)
    
    def leaveEvent(self, event):
        """Handle mouse leave events."""
        if self.parent():
            self.parent().leaveEvent(event)
        super().leaveEvent(event)


class HeadlessAgentWindow(QWidget):
    """Main headless window that contains only the circular indicator."""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Aras Agent")
        self.setFixedSize(120, 120)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # Create circular indicator
        self.indicator = CircularIndicator(self)
        self.indicator.move(0, 0)
        
        # Position window in bottom-right corner
        self.position_window()
        
        # Setup timer for status updates
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self.update_status)
        self.status_timer.start(1000)  # Update every second
        
        # Setup voice command processor
        self.voice_processor = VoiceCommandProcessor()
        
        # Connect voice signals
        self.voice_processor.handler.command_processed.connect(self.on_command_processed)
        self.voice_processor.handler.voice_response.connect(self.on_voice_response)
        
        # Start background listening for wake words
        self.voice_processor.start_background_listening()
        
        # Agent status
        self.agent_active = False
        self.voice_listening = False
        self.voice_processing = False
        self._processing_voice_command = False
        
        # Dragging properties for the main window
        self._dragging = False
        self._drag_start_position = None
    
    def position_window(self):
        """Position the window in the center of the screen."""
        screen = QApplication.primaryScreen().geometry()
        x = (screen.width() - self.width()) // 2
        y = (screen.height() - self.height()) // 2
        self.move(x, y)
    
    def update_status(self):
        """Update the agent status."""
        # This would check actual agent status
        # For now, toggle every 5 seconds as demo
        import time
        current_time = int(time.time())
        self.agent_active = (current_time % 10) < 5
        
        # Update voice listening status
        self.voice_listening = self.voice_processor.is_listening and self.voice_processor.voice_enabled
        
        # Update indicator with both agent and voice status
        self.indicator.set_active(self.agent_active)
        self.indicator.set_voice_listening(self.voice_listening)
        self.indicator.set_voice_processing(self.voice_processing)
    
    def on_command_processed(self, command: str, result: dict):
        """Handle command processed signal."""
        print(f"Command processed: '{command}' -> {result}")
        self.indicator.set_last_command(command)
        
        # Set processing state briefly
        self.voice_processing = True
        self.indicator.set_voice_processing(True)
        
        # Reset processing state after a short delay
        QTimer.singleShot(2000, lambda: self.set_voice_processing_false())
    
    def on_voice_response(self, response: str):
        """Handle voice response signal."""
        print(f"Aras: {response}")
        self.indicator.set_last_response(response)
    
    def set_voice_processing_false(self):
        """Set voice processing to false."""
        self.voice_processing = False
        self.indicator.set_voice_processing(False)
    
    
    def process_text_command(self, text: str) -> bool:
        """Process a text command and return True if handled."""
        return self.voice_processor.process_text_input(text)
    
    def set_agent_status(self, active: bool):
        """Set the agent status externally."""
        self.agent_active = active
        self.indicator.set_active(active)
    
    def mousePressEvent(self, event):
        """Handle mouse press events for dragging."""
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self._drag_start_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
        super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event):
        """Handle mouse move events for dragging."""
        if self._dragging and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_start_position)
        super().mouseMoveEvent(event)
    
    def mouseReleaseEvent(self, event):
        """Handle mouse release events."""
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = False
            self.setCursor(Qt.CursorShape.OpenHandCursor)
        super().mouseReleaseEvent(event)
    
    def enterEvent(self, event):
        """Handle mouse enter events."""
        if not self._dragging:
            self.setCursor(Qt.CursorShape.OpenHandCursor)
        super().enterEvent(event)
    
    def leaveEvent(self, event):
        """Handle mouse leave events."""
        if not self._dragging:
            self.setCursor(Qt.CursorShape.ArrowCursor)
        super().leaveEvent(event)
