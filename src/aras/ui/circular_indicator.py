"""
Circular indicator widget for headless agent status display.
"""

import sys
import asyncio
from PyQt6.QtWidgets import QWidget, QApplication, QLabel, QVBoxLayout
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, pyqtProperty, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QRadialGradient, QFont
from PyQt6.QtCore import QRect

from .voice_handler import VoiceCommandProcessor
from .qt_visualizer import QtVisualizer
from .chatbox import ChatBox


class CircularIndicator(QWidget):
    """Wrapper for the new QtVisualizer that maintains compatibility with existing code."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        # Size to accommodate the full 700x700 visualizer
        self.setFixedSize(700, 700)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # Create the new visualizer with original size
        self.visualizer = QtVisualizer(self)
        self.visualizer.setFixedSize(700, 700)  # Original size from your script
        self.visualizer.move(0, 0)  # Position at origin
        
        # Status properties for compatibility
        self._is_active = False
        self._voice_listening = False
        self._voice_processing = False
        self._voice_responding = False
        self._last_command = ""
        self._last_response = ""
        
        # State transition timer for smooth transitions
        self._state_timer = QTimer()
        self._state_timer.timeout.connect(self._update_visualizer_state)
        self._state_timer.start(200)  # Update every 200ms for more responsive but stable updates
        
        # Track current visualizer state to prevent unnecessary updates
        self._current_visualizer_state = "inactive"
        
        # State change debouncing
        self._last_state_change_time = 0
        self._min_state_change_interval = 0.3  # Minimum 300ms between state changes
        
        # State transition queue for handling rapid changes
        self._pending_state = None
        self._state_transition_timer = QTimer()
        self._state_transition_timer.timeout.connect(self._process_pending_state)
        self._state_transition_timer.setSingleShot(True)
        
        # Start with inactive state
        self.set_active(False)
    
    def _update_visualizer_state(self):
        """Update the visualizer state based on current status."""
        try:
            # Safety check - ensure visualizer exists
            if not hasattr(self, 'visualizer') or self.visualizer is None:
                print("Warning: Visualizer not available, skipping state update")
                return
                
            import time
            current_time = time.time()
            
            # Determine target state based on priority order: responding > processing > listening > active > inactive
            target_state = "inactive"
            if self._voice_responding:
                target_state = "responding"
            elif self._voice_processing:
                target_state = "processing"
            elif self._voice_listening:
                target_state = "voice"
            elif self._is_active:
                target_state = "active"
            
            # Only update if state has changed
            if target_state != self._current_visualizer_state:
                # Check if we need to debounce this change
                if current_time - self._last_state_change_time < self._min_state_change_interval:
                    # Store pending state and set a timer
                    self._pending_state = target_state
                    if not self._state_transition_timer.isActive():
                        self._state_transition_timer.start(int(self._min_state_change_interval * 1000))
                    return
                
                # Additional safety check for rapid responding/listening changes
                if (self._current_visualizer_state == "responding" and target_state == "voice") or \
                   (self._current_visualizer_state == "voice" and target_state == "responding"):
                    # Add extra delay for these rapid transitions
                    if current_time - self._last_state_change_time < 0.5:  # 500ms minimum
                        self._pending_state = target_state
                        if not self._state_transition_timer.isActive():
                            self._state_transition_timer.start(500)  # 500ms delay
                        return
                
                self.visualizer.set_state(target_state)
                self._current_visualizer_state = target_state
                self._last_state_change_time = current_time
                self._pending_state = None
                
        except Exception as e:
            print(f"Error updating visualizer state: {e}")
            import traceback
            traceback.print_exc()
    
    def _process_pending_state(self):
        """Process any pending state change after debounce delay."""
        if self._pending_state:
            try:
                import time
                self.visualizer.set_state(self._pending_state)
                self._current_visualizer_state = self._pending_state
                self._last_state_change_time = time.time()
                self._pending_state = None
            except Exception as e:
                print(f"Error processing pending state: {e}")
    
    def set_active(self, active: bool):
        """Set the active state of the indicator."""
        self._is_active = active
        # State will be updated by the timer
    
    def set_voice_listening(self, listening: bool):
        """Set the voice listening state of the indicator."""
        self._voice_listening = listening
        # State will be updated by the timer
    
    def set_voice_processing(self, processing: bool):
        """Set voice processing status."""
        self._voice_processing = processing
        # State will be updated by the timer
    
    def set_voice_responding(self, responding: bool):
        """Set voice responding status."""
        self._voice_responding = responding
        # State will be updated by the timer
    
    def set_last_command(self, command: str):
        """Set the last voice command."""
        try:
            self._last_command = command
            # Trigger a brief glow effect for command received
            if command:
                try:
                    self.visualizer.set_glow_mode(True)
                    # Reset glow after 1 second
                    QTimer.singleShot(1000, lambda: self._reset_glow())
                except Exception as e:
                    print(f"Error setting glow for command: {e}")
        except Exception as e:
            print(f"Error in set_last_command: {e}")
    
    def set_last_response(self, response: str):
        """Set the last voice response."""
        try:
            self._last_response = response
            # Trigger a brief glow effect for response generated
            if response:
                try:
                    self.visualizer.set_glow_mode(True)
                    # Reset glow after 1 second
                    QTimer.singleShot(1000, lambda: self._reset_glow())
                except Exception as e:
                    print(f"Error setting glow for response: {e}")
        except Exception as e:
            print(f"Error in set_last_response: {e}")
    
    def _reset_glow(self):
        """Reset glow mode safely."""
        try:
            # Let the state management system handle the transition back
            # Don't force it back to "active" - let the timer handle it
            pass
        except Exception as e:
            print(f"Error resetting glow: {e}")
    
    def is_active(self) -> bool:
        """Get the active state."""
        return self._is_active
    
    def paintEvent(self, event):
        """Override paintEvent to let the visualizer handle all drawing."""
        # Don't draw anything here - let the visualizer handle all the drawing
        pass
    
    def mousePressEvent(self, event):
        """Handle mouse press events - pass to parent window for dragging."""
        if self.parent():
            self.parent().mousePressEvent(event)
        super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event):
        """Handle mouse move events - pass to parent window for dragging."""
        if self.parent():
            self.parent().mouseMoveEvent(event)
        super().mouseMoveEvent(event)
    
    def mouseReleaseEvent(self, event):
        """Handle mouse release events - pass to parent window for dragging."""
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
        self.setFixedSize(700, 730)  # Size to accommodate full 700x700 visualizer and status text
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # Create layout
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        
        # Create circular indicator
        self.indicator = CircularIndicator(self)
        layout.addWidget(self.indicator, alignment=Qt.AlignmentFlag.AlignCenter)
        
        # Create status label
        self.status_label = QLabel("Idle")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet("""
            QLabel {
                color: white;
                background-color: transparent;
                font-size: 10px;
                font-weight: bold;
            }
        """)
        self.status_label.setFixedHeight(20)
        layout.addWidget(self.status_label, alignment=Qt.AlignmentFlag.AlignCenter)
        
        self.setLayout(layout)
        
        # Position window in bottom-right corner
        self.position_window()
        
        # Setup timer for status updates
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self.update_status)
        self.status_timer.start(1000)  # Update every second
        
        # Setup voice command processor
        self.voice_processor = VoiceCommandProcessor()
        
        # Setup chatbox
        self.chatbox = ChatBox()
        self.chatbox.chatbox_closed.connect(self.on_chatbox_closed)
        self.chatbox.message_sent.connect(self.on_chatbox_message_sent)
        
        # Setup tool registry for voice commands
        from ..tools.registry import create_tool_registry
        self.tool_registry = create_tool_registry()
        
        # Add desktop as a safe directory for file operations
        from pathlib import Path
        desktop_path = Path.home() / 'Desktop'
        file_tool = self.tool_registry.get_tool("file_create_remove")
        if file_tool:
            file_tool.add_safe_directory(str(desktop_path))
        
        self.voice_processor.handler.set_tool_registry(self.tool_registry)
        
        # Connect voice signals
        self.voice_processor.handler.command_processed.connect(self.on_command_processed)
        self.voice_processor.handler.voice_response.connect(self.on_voice_response)
        self.voice_processor.handler.speaking_started.connect(self.on_speaking_started)
        self.voice_processor.handler.speaking_stopped.connect(self.on_speaking_stopped)
        self.voice_processor.handler.file_operation_requested.connect(self.on_file_operation_requested)
        self.voice_processor.handler.chatbox_requested.connect(self.on_chatbox_requested)
        self.voice_processor.handler.chatbox_hide_requested.connect(self.on_chatbox_hide_requested)
        
        # Start background listening for wake words
        self.voice_processor.start_background_listening()
        
        # Agent status
        self.agent_active = False
        self.voice_listening = False
        self.voice_processing = False
        self.voice_responding = False
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
        
        # Update status text
        self.update_status_text()
    
    def update_status_text(self):
         """Update the status text based on current state."""
         # Priority order: Speaking > Thinking > Listening > Ready > Idle
         if self.voice_responding:
             # When speaking, ignore other states to prevent mixing
             self.status_label.setText("Speaking")
         elif self.voice_processing:
             # When processing, ignore listening state
             self.status_label.setText("Thinking")
         elif self.voice_listening and not self.voice_responding:
             # Only show listening if not speaking
             self.status_label.setText("Listening")
         elif self.agent_active:
             self.status_label.setText("Ready")
         else:
             self.status_label.setText("Idle")
         
         # Always use white text
         self.status_label.setStyleSheet("""
             QLabel {
                 color: white;
                 background-color: transparent;
                 font-size: 10px;
                 font-weight: bold;
             }
         """)
    
    def on_command_processed(self, command: str, result: dict):
        """Handle command processed signal."""
        try:
            import time
            timestamp = int(time.time() * 1000)
            print(f"[DEBUG-UI-{timestamp}] COMMAND_PROCESSED: '{command}' -> {result}")
            
            # Safely set command
            try:
                self.indicator.set_last_command(command)
            except Exception as e:
                print(f"[DEBUG-UI-{timestamp}] ERROR setting command: {e}")
            
            # Set processing state briefly
            try:
                self.voice_processing = True
                self.indicator.set_voice_processing(True)
                self.update_status_text()
                print(f"[DEBUG-UI-{timestamp}] UI_STATE_UPDATE: Voice processing state set to True")
            except Exception as e:
                print(f"[DEBUG-UI-{timestamp}] ERROR setting processing state: {e}")
            
            # Reset processing state after a short delay
            try:
                QTimer.singleShot(2000, lambda: self.set_voice_processing_false())
                print(f"[DEBUG-UI-{timestamp}] UI_TIMER_SET: Processing state reset timer set for 2000ms")
            except Exception as e:
                print(f"[DEBUG-UI-{timestamp}] ERROR setting timer: {e}")
            
            # Add user message to chatbox
            try:
                self.chatbox.add_voice_message(command, is_user=True)
            except Exception as e:
                print(f"[DEBUG-UI-{timestamp}] ERROR adding user message to chatbox: {e}")
            
            # Handle response immediately to avoid duplication with voice_response signal
            if result.get('response'):
                try:
                    # Check for duplicate response within the last 3 seconds
                    current_time = time.time()
                    response_text = result['response']
                    
                    if hasattr(self, '_last_response_time') and hasattr(self, '_last_response_text'):
                        if (current_time - self._last_response_time < 3.0 and 
                            self._last_response_text == response_text):
                            print(f"[DEBUG-UI-{timestamp}] DUPLICATE_RESPONSE_IGNORED: Ignoring duplicate response within 3 seconds")
                            return
                    
                    # Update last response tracking
                    self._last_response_time = current_time
                    self._last_response_text = response_text
                    
                    print(f"[DEBUG-UI-{timestamp}] IMMEDIATE_RESPONSE: Handling response from command_processed")
                    
                    # Add AI response to chatbox
                    try:
                        self.chatbox.add_ai_response(response_text)
                    except Exception as e:
                        print(f"[DEBUG-UI-{timestamp}] ERROR adding AI response to chatbox: {e}")
                    
                    # Safely set response
                    try:
                        self.indicator.set_last_response(response_text)
                    except Exception as e:
                        print(f"[DEBUG-UI-{timestamp}] ERROR setting response: {e}")
                    
                    # Handle TTS with error handling and timeout
                    if hasattr(self, 'voice_processor') and hasattr(self.voice_processor, 'handler'):
                        print(f"[DEBUG-UI-{timestamp}] TTS_HANDLING: Speaking response via command_processed")
                        try:
                            # Use QTimer to make TTS non-blocking
                            QTimer.singleShot(0, lambda: self._speak_response_async(response_text, timestamp))
                        except Exception as e:
                            print(f"[DEBUG-UI-{timestamp}] ERROR in TTS setup: {e}")
                    else:
                        print(f"[DEBUG-UI-{timestamp}] ERROR: Voice processor not available")
                        
                except Exception as e:
                    print(f"[DEBUG-UI-{timestamp}] ERROR handling response: {e}")
                    
        except Exception as e:
            print(f"[DEBUG-UI] CRITICAL ERROR in on_command_processed: {e}")
            import traceback
            traceback.print_exc()
    
    def on_voice_response(self, response: str):
        """Handle voice response signal - DISABLED to avoid duplication."""
        import time
        timestamp = int(time.time() * 1000)
        print(f"[DEBUG-UI-{timestamp}] VOICE_RESPONSE_IGNORED: Duplicate response ignored - handled in command_processed")
        # Response is now handled in on_command_processed to avoid duplication
        # Note: Speaking state is now handled by speaking_started/speaking_stopped signals
    
    def on_speaking_started(self):
        """Handle speaking started signal."""
        self.voice_responding = True
        self.indicator.set_voice_responding(True)
        # Don't pause listening - let it run continuously
        self.update_status_text()
    
    def on_speaking_stopped(self):
        """Handle speaking stopped signal."""
        self.voice_responding = False
        self.indicator.set_voice_responding(False)
        # Don't resume listening - it should already be running continuously
        self.update_status_text()
    
    def _speak_response_async(self, response_text: str, timestamp: int):
        """Speak response asynchronously with timeout protection."""
        try:
            print(f"[DEBUG-UI-{timestamp}] TTS_ASYNC: Starting async TTS")
            self.voice_processor.handler.speak_response(response_text)
            print(f"[DEBUG-UI-{timestamp}] TTS_ASYNC: TTS completed")
        except Exception as e:
            print(f"[DEBUG-UI-{timestamp}] ERROR in async TTS: {e}")
            import traceback
            traceback.print_exc()
    
    def on_tts_switch(self):
        """Handle TTS engine switch to prevent visual glitches."""
        # Briefly set to processing state during TTS switch
        self.voice_processing = True
        self.indicator.set_voice_processing(True)
        self.update_status_text()
        
        # Reset after a short delay
        QTimer.singleShot(500, lambda: self.set_voice_processing_false())
    
    def set_voice_processing_false(self):
        """Set voice processing to false."""
        self.voice_processing = False
        self.indicator.set_voice_processing(False)
        self.update_status_text()
    
    def on_file_operation_requested(self, operation: str, parameters: dict):
        """Handle file operation request from voice command."""
        import time
        timestamp = int(time.time() * 1000)
        print(f"[DEBUG-UI-{timestamp}] FILE_OPERATION_REQUESTED: {operation} with parameters: {parameters}")
        
        # Set processing state
        self.voice_processing = True
        self.indicator.set_voice_processing(True)
        self.update_status_text()
        
        # Execute file operation asynchronously using QTimer to avoid blocking
        QTimer.singleShot(0, lambda: asyncio.run(self.execute_file_operation(operation, parameters)))
    
    async def execute_file_operation(self, operation: str, parameters: dict):
        """Execute file operation using the agent's tools."""
        try:
            # Import here to avoid circular imports
            import time
            from ..core.agent import ArasAgent
            from ..models import UserInput, MessageType
            
            # Create agent instance
            agent = ArasAgent()
            await agent.initialize()
            
            # Create a user input message for the file operation
            command_text = f"Execute file operation: {operation}"
            if parameters.get('path'):
                command_text += f" on path: {parameters['path']}"
            
            message = UserInput(
                id=f"file_op_{int(time.time() * 1000)}",
                type=MessageType.USER_INPUT,
                content=command_text,
                input_type="voice",
                session_id="voice_session"
            )
            
            # Execute the file operation using the agent
            response = await agent.process_message(message)
            
            # Provide feedback via TTS
            if hasattr(self, 'voice_processor') and hasattr(self.voice_processor, 'handler'):
                self.voice_processor.handler.speak_response(f"File operation completed: {response}")
            
            print(f"[DEBUG-UI] FILE_OPERATION_COMPLETED: {response}")
            
        except Exception as e:
            error_msg = f"Error executing file operation: {str(e)}"
            print(f"[DEBUG-UI] FILE_OPERATION_ERROR: {error_msg}")
            
            # Provide error feedback via TTS
            if hasattr(self, 'voice_processor') and hasattr(self.voice_processor, 'handler'):
                self.voice_processor.handler.speak_response(f"Sorry, I couldn't complete the file operation: {error_msg}")
        
        finally:
            # Reset processing state
            self.voice_processing = False
            self.indicator.set_voice_processing(False)
            self.update_status_text()
    
    def process_text_command(self, text: str) -> bool:
        """Process a text command and return True if handled."""
        return self.voice_processor.process_text_input(text)
    
    def set_agent_status(self, active: bool):
        """Set the agent status externally."""
        self.agent_active = active
        self.indicator.set_active(active)
        self.update_status_text()
    
    def on_chatbox_requested(self):
        """Handle chatbox request from voice command."""
        print("=== CHATBOX REQUEST HANDLER ===")
        print("Chatbox requested via voice command")
        # Position chatbox near the main window
        main_pos = self.pos()
        chatbox_pos = (main_pos.x() + self.width() + 20, main_pos.y())
        print(f"Positioning chatbox at: {chatbox_pos}")
        self.chatbox.show_chatbox(chatbox_pos)
        print("=== CHATBOX REQUEST HANDLER COMPLETE ===")
    
    def on_chatbox_hide_requested(self):
        """Handle chatbox hide request from voice command."""
        print("=== CHATBOX HIDE REQUEST HANDLER ===")
        print("Chatbox hide requested via voice command")
        self.chatbox.close_chatbox()
        print("=== CHATBOX HIDE REQUEST HANDLER COMPLETE ===")
    
    def on_chatbox_closed(self):
        """Handle chatbox closed signal."""
        print("Chatbox closed")
    
    def on_chatbox_message_sent(self, message: str):
        """Handle message sent from chatbox."""
        print(f"Message sent from chatbox: {message}")
        # Process the message through the voice handler
        self.voice_processor.handler.process_voice_command(message)
    
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
