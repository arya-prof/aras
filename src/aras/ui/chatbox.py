"""
ChatBox widget for displaying conversation history.
"""

import sys
import json
from datetime import datetime
from typing import List, Dict, Any, Optional
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                            QScrollArea, QFrame, QPushButton, QTextEdit, 
                            QSizePolicy, QApplication)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QPropertyAnimation, QEasingCurve, QRect
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QFont, QTextCursor, QKeyEvent


class ChatTextEdit(QTextEdit):
    """Custom QTextEdit that handles Enter key for sending messages."""
    
    message_send_requested = pyqtSignal()
    
    def keyPressEvent(self, event: QKeyEvent):
        """Handle key press events."""
        if event.key() == Qt.Key.Key_Return and not event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            # Enter key pressed without Shift - send message
            self.message_send_requested.emit()
        else:
            super().keyPressEvent(event)


class ChatMessage(QWidget):
    """Individual chat message widget."""
    
    def __init__(self, message: str, is_user: bool, timestamp: str = None, parent=None):
        super().__init__(parent)
        self.message = message
        self.is_user = is_user
        self.timestamp = timestamp or datetime.now().strftime("%H:%M")
        self.init_ui()
    
    def init_ui(self):
        """Initialize the message UI."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 5, 0, 5)  # Remove left/right margins
        
        # Set colors and alignment based on message type
        if self.is_user:
            # User messages: align to right - add stretch before to push content right
            layout.addStretch()
        else:
            # AI messages: align to left - no stretch before
            pass
        
        # Message container
        message_frame = QFrame()
        message_frame.setFrameStyle(QFrame.Shape.Box)
        message_frame.setLineWidth(1)
        
        # Set maximum width for both message types - use full width
        # message_frame.setMaximumWidth(350)  # Removed to allow full width
        
        # Set colors based on message type
        if self.is_user:
            message_frame.setStyleSheet("""
                QFrame {
                    background-color: #1E3A8A;
                    border: 1px solid #1E40AF;
                    border-radius: 0px;
                    color: white;
                    margin-right: 10px;
                }
            """)
        else:
            message_frame.setStyleSheet("""
                QFrame {
                    background-color: #2A2A2A;
                    border: 1px solid #333333;
                    border-radius: 0px;
                    color: #FFFFFF;
                    margin-left: 10px;
                }
            """)
        
        # Message content layout
        content_layout = QVBoxLayout(message_frame)
        content_layout.setContentsMargins(15, 10, 15, 10)
        
        # Set alignment for content based on message type
        if self.is_user:
            content_layout.setAlignment(Qt.AlignmentFlag.AlignRight)
        else:
            content_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        
        # Message text
        message_label = QLabel(self.message)
        message_label.setWordWrap(True)
        # message_label.setMaximumWidth(320)  # Removed to allow full width
        message_label.setAlignment(Qt.AlignmentFlag.AlignLeft if not self.is_user else Qt.AlignmentFlag.AlignRight)
        message_label.setStyleSheet("""
            QLabel {
                font-size: 13px;
                line-height: 1.3;
                background-color: transparent;
                border: none;
                font-weight: 400;
            }
        """)
        
        # Timestamp
        time_label = QLabel(self.timestamp)
        time_label.setAlignment(Qt.AlignmentFlag.AlignLeft if not self.is_user else Qt.AlignmentFlag.AlignRight)
        time_label.setStyleSheet("""
            QLabel {
                font-size: 10px;
                color: #666666;
                background-color: transparent;
                border: none;
                font-weight: 300;
            }
        """)
        
        content_layout.addWidget(message_label)
        content_layout.addWidget(time_label)
        
        # Add the message frame with appropriate stretch factor
        if self.is_user:
            # User messages: add to the right side
            layout.addWidget(message_frame, 0)  # No stretch factor
        else:
            # AI messages: add to the left side
            layout.addWidget(message_frame, 0)  # No stretch factor
            layout.addStretch()  # Add stretch after to push to left


class ChatBox(QWidget):
    """ChatBox widget for displaying conversation history."""
    
    # Signals
    chatbox_closed = pyqtSignal()
    message_sent = pyqtSignal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.conversation_history: List[Dict[str, Any]] = []
        self.current_session_messages: List[Dict[str, Any]] = []  # Only current session
        self.init_ui()
        self.setup_animations()
        
        # Load persistent history for storage purposes only (not displayed)
        self.load_conversation_history()
    
    def init_ui(self):
        """Initialize the chatbox UI."""
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # Get screen dimensions for full height
        screen = QApplication.primaryScreen().geometry()
        self.setFixedSize(400, screen.height())
        
        # Main container with sharp borders
        self.main_frame = QFrame()
        self.main_frame.setFrameStyle(QFrame.Shape.Box)
        self.main_frame.setStyleSheet("""
            QFrame {
                background-color: rgba(18, 18, 18, 0.95);
                border: 1px solid #333333;
                border-radius: 0px;
            }
        """)
        
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self.main_frame)
        
        # Content layout
        content_layout = QVBoxLayout(self.main_frame)
        content_layout.setContentsMargins(0, 0, 0, 0)
        
        # Header
        self.create_header(content_layout)
        
        # Messages area
        self.create_messages_area(content_layout)
        
        # Input area
        self.create_input_area(content_layout)
        
        # Initially hidden
        self.hide()
    
    def create_header(self, parent_layout):
        """Create the chatbox header."""
        header_frame = QFrame()
        header_frame.setStyleSheet("""
            QFrame {
                background-color: #1A1A1A;
                border-top-left-radius: 0px;
                border-top-right-radius: 0px;
                border-bottom: 1px solid #333333;
            }
        """)
        header_frame.setFixedHeight(50)
        
        header_layout = QHBoxLayout(header_frame)
        header_layout.setContentsMargins(15, 10, 15, 10)
        
        # Title
        title_label = QLabel("Chat")
        title_label.setStyleSheet("""
            QLabel {
                font-size: 14px;
                font-weight: 500;
                color: #FFFFFF;
                background-color: transparent;
                border: none;
            }
        """)
        
        # Close button
        close_button = QPushButton("×")
        close_button.setFixedSize(24, 24)
        close_button.setStyleSheet("""
            QPushButton {
                background-color: #333333;
                color: #CCCCCC;
                border: 1px solid #444444;
                border-radius: 0px;
                font-size: 12px;
                font-weight: 400;
            }
            QPushButton:hover {
                background-color: #444444;
                color: #FFFFFF;
            }
            QPushButton:pressed {
                background-color: #555555;
            }
        """)
        close_button.clicked.connect(self.close_chatbox)
        
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        header_layout.addWidget(close_button)
        
        parent_layout.addWidget(header_frame)
    
    def create_messages_area(self, parent_layout):
        """Create the messages scroll area."""
        # Scroll area for messages
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setStyleSheet("""
            QScrollArea {
                background-color: transparent;
                border: none;
            }
            QScrollBar:vertical {
                background-color: #1A1A1A;
                width: 6px;
                border-radius: 0px;
            }
            QScrollBar::handle:vertical {
                background-color: #333333;
                border-radius: 0px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #444444;
            }
        """)
        
        # Messages container
        self.messages_widget = QWidget()
        self.messages_layout = QVBoxLayout(self.messages_widget)
        self.messages_layout.setContentsMargins(0, 10, 0, 10)  # Remove left/right margins
        self.messages_layout.setSpacing(5)
        self.messages_layout.addStretch()  # Push messages to top
        
        self.scroll_area.setWidget(self.messages_widget)
        parent_layout.addWidget(self.scroll_area, 1)  # Take most of the space
    
    def create_input_area(self, parent_layout):
        """Create the input area."""
        input_frame = QFrame()
        input_frame.setStyleSheet("""
            QFrame {
                background-color: #1A1A1A;
                border-top: 1px solid #333333;
                border-bottom-left-radius: 0px;
                border-bottom-right-radius: 0px;
            }
        """)
        input_frame.setFixedHeight(80)
        
        input_layout = QHBoxLayout(input_frame)
        input_layout.setContentsMargins(15, 10, 15, 10)
        
        # Text input
        self.text_input = ChatTextEdit()
        self.text_input.setMaximumHeight(40)
        self.text_input.setPlaceholderText("Type a message...")
        self.text_input.setStyleSheet("""
            QTextEdit {
                background-color: #2A2A2A;
                border: 1px solid #333333;
                border-radius: 0px;
                padding: 8px 12px;
                font-size: 14px;
                color: #FFFFFF;
            }
            QTextEdit:focus {
                border-color: #007AFF;
            }
        """)
        self.text_input.message_send_requested.connect(self.send_message)
        
        # Send button
        send_button = QPushButton("Send")
        send_button.setFixedSize(60, 40)
        send_button.setStyleSheet("""
            QPushButton {
                background-color: #007AFF;
                color: white;
                border: none;
                border-radius: 0px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0056CC;
            }
            QPushButton:pressed {
                background-color: #004BB5;
            }
        """)
        send_button.clicked.connect(self.send_message)
        
        # Connect Enter key to send (QTextEdit uses keyPressEvent)
        # We'll handle this in the keyPressEvent method
        
        input_layout.addWidget(self.text_input, 1)
        input_layout.addWidget(send_button)
        
        parent_layout.addWidget(input_frame)
    
    def setup_animations(self):
        """Setup show/hide animations."""
        self.show_animation = QPropertyAnimation(self, b"geometry")
        self.show_animation.setDuration(300)
        self.show_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        
        self.hide_animation = QPropertyAnimation(self, b"geometry")
        self.hide_animation.setDuration(300)
        self.hide_animation.setEasingCurve(QEasingCurve.Type.InCubic)
        self.hide_animation.finished.connect(self.hide)
    
    def show_chatbox(self, position=None):
        """Show the chatbox with animation."""
        print("=== CHATBOX SHOW ===")
        print(f"show_chatbox called with position: {position}")
        
        # Get screen dimensions
        screen = QApplication.primaryScreen().geometry()
        
        if position is None:
            # Position at right edge of screen, full height
            x = screen.width() - self.width()
            y = 0
            position = (x, y)
            print(f"Right edge position: {position}")
        else:
            # Use provided position but ensure full height
            x = position[0]
            y = 0
            position = (x, y)
            print(f"Custom position (adjusted for full height): {position}")
        
        # Set initial position (off-screen to the right)
        start_rect = QRect(position[0] + self.width(), position[1], self.width(), self.height())
        end_rect = QRect(position[0], position[1], self.width(), self.height())
        
        print(f"Start rect: {start_rect}")
        print(f"End rect: {end_rect}")
        
        self.setGeometry(start_rect)
        self.show()
        print("Chatbox widget shown")
        
        # Animate in
        self.show_animation.setStartValue(start_rect)
        self.show_animation.setEndValue(end_rect)
        self.show_animation.start()
        print("Animation started")
        
        # Auto-scroll to bottom after animation completes
        self.show_animation.finished.connect(self.scroll_to_bottom)
        print("=== CHATBOX SHOW COMPLETE ===")
    
    def close_chatbox(self):
        """Close the chatbox with animation."""
        current_rect = self.geometry()
        end_rect = QRect(current_rect.x() + self.width(), current_rect.y(), 
                        current_rect.width(), current_rect.height())
        
        self.hide_animation.setStartValue(current_rect)
        self.hide_animation.setEndValue(end_rect)
        self.hide_animation.start()
        
        self.chatbox_closed.emit()
    
    def hide_chatbox(self):
        """Hide the chatbox (same as close for now, but can be differentiated later)."""
        self.close_chatbox()
    
    def add_message(self, message: str, is_user: bool, timestamp: str = None):
        """Add a message to the chat with optimized real-time updates."""
        if not timestamp:
            timestamp = datetime.now().strftime("%H:%M")
        
        # Create message widget
        message_widget = ChatMessage(message, is_user, timestamp)
        
        # Insert before the stretch
        self.messages_layout.insertWidget(self.messages_layout.count() - 1, message_widget)
        
        # Store in current session only
        message_data = {
            "message": message,
            "is_user": is_user,
            "timestamp": timestamp,
            "datetime": datetime.now().isoformat()
        }
        self.current_session_messages.append(message_data)
        
        # Also store in persistent history for long-term storage
        self.conversation_history.append(message_data)
        
        # Optimized immediate UI update - like awsmarthome
        self.scroll_to_bottom()
        
        # Force immediate repaint for real-time feel
        self.messages_widget.repaint()
        self.scroll_area.repaint()
        
        # Process events immediately for responsiveness
        QApplication.processEvents()
        
        # Save history asynchronously to avoid blocking
        QTimer.singleShot(0, self.save_conversation_history)
    
    def send_message(self):
        """Send a message."""
        text = self.text_input.toPlainText().strip()
        if text:
            self.add_message(text, True)
            self.message_sent.emit(text)
            self.text_input.clear()
    
    def scroll_to_bottom(self):
        """Optimized scroll to bottom for real-time performance."""
        scrollbar = self.scroll_area.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
        # Immediate repaint for responsiveness
        self.scroll_area.repaint()
    
    def load_conversation_history(self):
        """Load conversation history from file (for persistent storage only)."""
        try:
            from ..config import get_data_dir
            data_dir = get_data_dir()
            history_file = data_dir / "conversation_history.json"
            
            if history_file.exists():
                with open(history_file, 'r', encoding='utf-8') as f:
                    self.conversation_history = json.load(f)
            else:
                self.conversation_history = []
        except Exception as e:
            print(f"Error loading conversation history: {e}")
            self.conversation_history = []
    
    def save_conversation_history(self):
        """Save conversation history to file."""
        try:
            from ..config import get_data_dir
            data_dir = get_data_dir()
            history_file = data_dir / "conversation_history.json"
            
            # Keep only last 1000 messages to prevent file from growing too large
            history_to_save = self.conversation_history[-1000:]
            
            with open(history_file, 'w', encoding='utf-8') as f:
                json.dump(history_to_save, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving conversation history: {e}")
    
    def start_new_session(self):
        """Start a new conversation session (clear current session messages)."""
        print("Starting new chat session - clearing current session messages")
        self.current_session_messages = []
        # Clear UI messages
        for i in reversed(range(self.messages_layout.count() - 1)):  # Keep the stretch
            child = self.messages_layout.itemAt(i).widget()
            if child:
                child.deleteLater()
    
    def clear_history(self):
        """Clear conversation history."""
        self.conversation_history = []
        self.current_session_messages = []
        # Clear UI
        for i in reversed(range(self.messages_layout.count() - 1)):  # Keep the stretch
            child = self.messages_layout.itemAt(i).widget()
            if child:
                child.deleteLater()
        self.save_conversation_history()
    
    def add_voice_message(self, message: str, is_user: bool = False):
        """Add a message from voice input."""
        self.add_message(message, is_user)
    
    def add_ai_response(self, response: str):
        """Add an AI response to the chat."""
        self.add_message(response, False)
    
    def add_streaming_message(self, message: str, is_user: bool = False, message_id: str = None):
        """Add a streaming message that can be updated in real-time."""
        if message_id is None:
            message_id = f"stream_{datetime.now().strftime('%H%M%S%f')}"
        
        # Create message widget
        message_widget = ChatMessage(message, is_user)
        message_widget.setProperty("message_id", message_id)
        
        # Insert before the stretch
        self.messages_layout.insertWidget(self.messages_layout.count() - 1, message_widget)
        
        # Force immediate UI update
        self.messages_widget.update()
        self.scroll_area.update()
        self.update()
        QApplication.processEvents()
        
        # Scroll to bottom
        self.scroll_to_bottom()
        
        return message_id
    
    def update_streaming_message(self, message_id: str, new_content: str):
        """Update a streaming message with new content."""
        # Find the message widget by ID
        for i in range(self.messages_layout.count() - 1):  # Exclude the stretch
            widget = self.messages_layout.itemAt(i).widget()
            if widget and widget.property("message_id") == message_id:
                # Update the message content
                message_label = widget.findChild(QLabel)
                if message_label:
                    message_label.setText(new_content)
                    # Force immediate update
                    widget.update()
                    self.scroll_to_bottom()
                    QApplication.processEvents()
                break
    
    def handle_wake_word_detected(self, wake_word: str):
        """Handle wake word detection - start new session and optionally add wake word message."""
        print(f"Chatbox: Wake word '{wake_word}' detected - starting new session")
        self.start_new_session()
        
        # Optionally add the wake word as the first message
        # Uncomment the next line if you want to show the wake word in chat
        # self.add_message(f"Wake word detected: {wake_word}", True)
    
    def show_historical_messages(self, limit: int = 50):
        """Show historical messages from persistent storage (optional feature)."""
        try:
            # Clear current session first
            self.start_new_session()
            
            # Load and display historical messages
            messages_to_load = self.conversation_history[-limit:]
            for i, msg in enumerate(messages_to_load):
                self.add_message(msg["message"], msg["is_user"], msg["timestamp"])
                # Process events every 5 messages to show progress without blocking
                if i % 5 == 0:
                    QApplication.processEvents()
            
            # Final scroll to bottom
            self.scroll_to_bottom()
            print(f"Loaded {min(limit, len(self.conversation_history))} historical messages")
        except Exception as e:
            print(f"Error showing historical messages: {e}")
    
    def add_messages_bulk(self, messages: List[Dict[str, Any]]):
        """Add multiple messages efficiently in bulk."""
        try:
            for i, msg in enumerate(messages):
                # Create message widget
                message_widget = ChatMessage(msg["message"], msg["is_user"], msg.get("timestamp"))
                
                # Insert before the stretch
                self.messages_layout.insertWidget(self.messages_layout.count() - 1, message_widget)
                
                # Store in current session
                self.current_session_messages.append(msg)
                
                # Process events every 10 messages to maintain responsiveness
                if i % 10 == 0:
                    QApplication.processEvents()
            
            # Force final UI update
            self.messages_widget.update()
            self.scroll_area.update()
            self.update()
            QApplication.processEvents()
            
            # Scroll to bottom
            self.scroll_to_bottom()
            
            print(f"Added {len(messages)} messages in bulk")
        except Exception as e:
            print(f"Error adding messages in bulk: {e}")
