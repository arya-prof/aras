"""
Advanced Qt visualizer widget for ARAS agent status display.
"""

import sys
import math
import random
from PyQt6.QtWidgets import QApplication, QWidget
from PyQt6.QtGui import QPainter, QColor, QPolygonF
from PyQt6.QtCore import QTimer, Qt, QPointF, pyqtSignal


STATES = ["inactive", "active", "voice", "processing", "responding", "glow"]

STATE_COLORS = {
    "inactive": [(80, 80, 80)],
    "active": [(0, 150, 255), (0, 200, 180)],
    "voice": [(255, 100, 100), (255, 180, 50)],
    "processing": [(180, 50, 255), (100, 100, 255)],
    "responding": [(50, 255, 120), (0, 200, 80)],
    "glow": [(255, 255, 200), (255, 255, 255)],
}

STATE_STYLE = {
    "inactive": {"sides": 4, "radius": 40, "speed": 0.002, "pulse": 0.01, "rotate": 0.0},
    "active": {"sides": 6, "radius": 60, "speed": 0.008, "pulse": 0.05, "rotate": 0.002},
    "voice": {"sides": 8, "radius": 80, "speed": 0.015, "pulse": 0.12, "rotate": 0.01},
    "processing": {"sides": 3, "radius": 50, "speed": 0.004, "pulse": 0.025, "rotate": 0.004},
    "responding": {"sides": 5, "radius": 70, "speed": 0.012, "pulse": 0.08, "rotate": 0.006},
    "glow": {"sides": 12, "radius": 90, "speed": 0.006, "pulse": 0.04, "rotate": 0.004},
}


class QtVisualizer(QWidget):
    """Advanced Qt visualizer widget for ARAS agent status display."""
    
    # Signals for external communication
    state_changed = pyqtSignal(str)  # Emitted when state changes
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.resize(700, 700)  # Original size from your script
        self.t = 0
        self.angle = 0
        self.state_index = 0
        self.state = STATES[self.state_index]

        # Frameless + transparent
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_animation)
        self.timer.start(30)

    def update_animation(self):
        """Update animation frame."""
        style = STATE_STYLE[self.state]
        self.t += style["speed"]
        self.angle += style["rotate"]
        self.update()

    def keyPressEvent(self, event):
        """Handle key press events for testing."""
        if event.key() == Qt.Key.Key_Space:
            self.state_index = (self.state_index + 1) % len(STATES)
            self.state = STATES[self.state_index]
            print("Switched to:", self.state)
            self.state_changed.emit(self.state)
        elif event.key() == Qt.Key.Key_Q:
            QApplication.quit()

    def draw_polygon(self, painter, cx, cy, radius, sides, rotation, color, fill=True):
        """Draw a polygon with the given parameters."""
        points = []
        for i in range(sides):
            theta = 2 * math.pi * i / sides + rotation
            x = cx + math.cos(theta) * radius
            y = cy + math.sin(theta) * radius
            points.append(QPointF(x, y))

        painter.setPen(color)
        if fill:
            painter.setBrush(color)
        else:
            painter.setBrush(Qt.BrushStyle.NoBrush)

        polygon = QPolygonF(points)
        painter.drawPolygon(polygon)

    def paintEvent(self, event):
        """Paint the visualizer."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        style = STATE_STYLE[self.state]
        colors = STATE_COLORS[self.state]
        cx, cy = self.width() // 2, self.height() // 2

        # Base pulsing radius
        pulse = math.sin(self.t * 4) * style["pulse"] * style["radius"]
        base_radius = style["radius"] + pulse

        # Draw concentric rotating polygons
        for k in range(5, 0, -1):
            color = QColor(*random.choice(colors))
            color.setAlpha(40 + k * 30)
            self.draw_polygon(
                painter,
                cx,
                cy,
                base_radius * (k * 0.6 + 0.5),
                style["sides"],
                self.angle * k,
                color,
                fill=False
            )

        # Central filled polygon
        color = QColor(*random.choice(colors))
        color.setAlpha(200)
        self.draw_polygon(
            painter,
            cx,
            cy,
            base_radius,
            style["sides"],
            self.angle,
            color,
            fill=True
        )

    def set_state(self, state: str):
        """Set the visualizer state."""
        try:
            if state in STATES and self.state != state:
                self.state = state
                self.state_index = STATES.index(state)
                self.state_changed.emit(self.state)
                # Only print state changes for debugging, reduce verbosity
                if state != "inactive":  # Don't spam inactive state changes
                    print(f"Visualizer: {state}")
        except Exception as e:
            print(f"Error setting visualizer state to {state}: {e}")

    def get_state(self) -> str:
        """Get the current visualizer state."""
        return self.state

    def set_active(self, active: bool):
        """Set active state (maps to 'active' or 'inactive')."""
        self.set_state("active" if active else "inactive")

    def set_voice_listening(self, listening: bool):
        """Set voice listening state."""
        if listening:
            self.set_state("voice")
        elif self.state == "voice":
            self.set_state("active")

    def set_voice_processing(self, processing: bool):
        """Set voice processing state."""
        if processing:
            self.set_state("processing")
        elif self.state == "processing":
            self.set_state("active")

    def set_voice_responding(self, responding: bool):
        """Set voice responding state."""
        if responding:
            self.set_state("responding")
        elif self.state == "responding":
            self.set_state("active")

    def set_glow_mode(self, glow: bool):
        """Set glow mode."""
        try:
            if glow:
                self.set_state("glow")
            # Don't automatically reset to "active" - let the state management handle it
        except Exception as e:
            print(f"Error in set_glow_mode: {e}")

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


if __name__ == "__main__":
    app = QApplication(sys.argv)
    vis = QtVisualizer()
    vis.show()
    sys.exit(app.exec())
