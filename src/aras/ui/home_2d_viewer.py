"""
2D Home Viewer using PyQt6 for floor plan visualization.
"""

import sys
import math
import numpy as np
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                            QSlider, QPushButton, QGroupBox, QGraphicsView, 
                            QGraphicsScene, QGraphicsItem, QGraphicsRectItem,
                            QGraphicsEllipseItem, QGraphicsTextItem, QFrame)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QRectF, QPointF
from PyQt6.QtGui import (QPainter, QPen, QBrush, QColor, QFont, QPolygonF,
                        QPainterPath, QLinearGradient, QRadialGradient)
from PyQt6.QtWidgets import QGraphicsView


class FloorPlanItem(QGraphicsItem):
    """Custom graphics item for floor plan elements."""
    
    def __init__(self, item_type, rect, label="", parent=None):
        super().__init__(parent)
        self.item_type = item_type
        self.rect = rect
        self.label = label
        self.selected = False
        
        # Set up colors based on room type
        self.colors = {
            'living_room': QColor(135, 206, 235),  # Sky blue
            'kitchen': QColor(255, 182, 193),      # Light pink
            'bedroom': QColor(152, 251, 152),      # Light green
            'bathroom': QColor(176, 224, 230),     # Powder blue
            'hallway': QColor(245, 245, 220),      # Beige
            'office': QColor(221, 160, 221),       # Plum
            'garage': QColor(169, 169, 169),       # Dark gray
            'outdoor': QColor(144, 238, 144),      # Light green
            'wall': QColor(105, 105, 105),         # Dim gray
            'door': QColor(139, 69, 19),           # Saddle brown
            'window': QColor(173, 216, 230),       # Light blue
        }
    
    def boundingRect(self):
        return self.rect
    
    def paint(self, painter, option, widget):
        """Paint the floor plan item."""
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Set color based on item type
        color = self.colors.get(self.item_type, QColor(200, 200, 200))
        
        if self.item_type == 'wall':
            # Draw wall as thick line
            pen = QPen(QColor(80, 80, 80), 8, Qt.PenStyle.SolidLine)
            painter.setPen(pen)
            painter.drawRect(self.rect)
        elif self.item_type in ['door', 'window']:
            # Draw door/window as line
            pen = QPen(QColor(139, 69, 19), 4, Qt.PenStyle.SolidLine)
            painter.setPen(pen)
            painter.drawLine(self.rect.topLeft(), self.rect.bottomRight())
        else:
            # Draw room as filled rectangle
            brush = QBrush(color)
            painter.setBrush(brush)
            pen = QPen(QColor(100, 100, 100), 2, Qt.PenStyle.SolidLine)
            painter.setPen(pen)
            painter.drawRect(self.rect)
        
        # Draw label
        if self.label:
            painter.setPen(QPen(QColor(50, 50, 50), 1))
            font = QFont("Arial", 10, QFont.Weight.Bold)
            painter.setFont(font)
            painter.drawText(self.rect, Qt.AlignmentFlag.AlignCenter, self.label)
        
        # Draw selection highlight
        if self.selected:
            pen = QPen(QColor(255, 0, 0), 3, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.drawRect(self.rect.adjusted(-2, -2, 2, 2))


class Home2DViewer(QGraphicsView):
    """2D floor plan viewer widget."""
    
    # Signals
    room_selected = pyqtSignal(str)  # room name
    view_changed = pyqtSignal(float, float, float)  # pan x, pan y, zoom
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Create scene
        self.scene = QGraphicsScene()
        self.setScene(self.scene)
        
        # View settings
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        
        # Zoom and pan
        self.zoom_factor = 1.0
        self.pan_x = 0.0
        self.pan_y = 0.0
        
        # Room data
        self.rooms = {}
        self.current_room = None
        
        # Create sample floor plan
        self.create_sample_floor_plan()
        
        # Setup view
        self.setup_view()
    
    def create_sample_floor_plan(self):
        """Create a sample floor plan layout."""
        # Clear existing items
        self.scene.clear()
        self.rooms.clear()
        
        # Define room layout (x, y, width, height, type, label)
        room_data = [
            # Ground floor
            (0, 0, 300, 200, 'living_room', 'Living Room'),
            (300, 0, 200, 100, 'kitchen', 'Kitchen'),
            (300, 100, 200, 100, 'dining', 'Dining'),
            (0, 200, 150, 150, 'bedroom', 'Master Bedroom'),
            (150, 200, 150, 150, 'bedroom', 'Bedroom 2'),
            (300, 200, 200, 150, 'bathroom', 'Bathroom'),
            (0, 350, 500, 100, 'garage', 'Garage'),
            
            # Second floor
            (600, 0, 200, 150, 'bedroom', 'Bedroom 3'),
            (600, 150, 200, 150, 'office', 'Office'),
            (800, 0, 150, 300, 'bathroom', 'Bathroom 2'),
        ]
        
        # Create room items
        for x, y, w, h, room_type, label in room_data:
            rect = QRectF(x, y, w, h)
            item = FloorPlanItem(room_type, rect, label)
            self.scene.addItem(item)
            self.rooms[label] = item
        
        # Add walls
        self.add_walls()
        
        # Add doors and windows
        self.add_doors_windows()
        
        # Add furniture (simplified)
        self.add_furniture()
    
    def add_walls(self):
        """Add wall elements to the floor plan."""
        wall_data = [
            # Exterior walls
            (0, 0, 500, 10, 'wall'),      # Top wall
            (0, 0, 10, 450, 'wall'),      # Left wall
            (490, 0, 10, 450, 'wall'),    # Right wall
            (0, 440, 500, 10, 'wall'),    # Bottom wall
            
            # Interior walls
            (300, 0, 10, 200, 'wall'),    # Kitchen divider
            (0, 200, 300, 10, 'wall'),    # Bedroom divider
            (150, 200, 10, 150, 'wall'),  # Between bedrooms
            (300, 200, 10, 150, 'wall'),  # Bathroom divider
            
            # Second floor walls
            (600, 0, 10, 300, 'wall'),    # Second floor left
            (600, 0, 350, 10, 'wall'),    # Second floor top
            (950, 0, 10, 300, 'wall'),    # Second floor right
            (600, 290, 350, 10, 'wall'),  # Second floor bottom
            (800, 0, 10, 300, 'wall'),    # Bathroom divider
        ]
        
        for x, y, w, h, wall_type in wall_data:
            rect = QRectF(x, y, w, h)
            item = FloorPlanItem(wall_type, rect)
            self.scene.addItem(item)
    
    def add_doors_windows(self):
        """Add doors and windows to the floor plan."""
        door_window_data = [
            # Doors
            (150, 0, 20, 5, 'door'),      # Main entrance
            (300, 100, 5, 20, 'door'),    # Kitchen to dining
            (150, 200, 5, 20, 'door'),    # Living to bedroom
            (300, 200, 5, 20, 'door'),    # Dining to bathroom
            (600, 150, 20, 5, 'door'),    # Second floor entrance
            (800, 150, 5, 20, 'door'),    # Office to bathroom
            
            # Windows
            (50, 0, 30, 5, 'window'),     # Living room window
            (250, 0, 30, 5, 'window'),    # Living room window 2
            (350, 0, 30, 5, 'window'),    # Kitchen window
            (0, 100, 5, 30, 'window'),    # Living room side window
            (0, 250, 5, 30, 'window'),    # Bedroom window
            (150, 250, 5, 30, 'window'),  # Bedroom 2 window
            (600, 0, 30, 5, 'window'),    # Bedroom 3 window
            (600, 300, 30, 5, 'window'),  # Office window
        ]
        
        for x, y, w, h, item_type in door_window_data:
            rect = QRectF(x, y, w, h)
            item = FloorPlanItem(item_type, rect)
            self.scene.addItem(item)
    
    def add_furniture(self):
        """Add simplified furniture to rooms."""
        furniture_data = [
            # Living room furniture
            (50, 50, 40, 30, 'sofa'),
            (100, 50, 30, 20, 'table'),
            (150, 50, 25, 25, 'tv'),
            
            # Kitchen furniture
            (320, 20, 60, 15, 'counter'),
            (320, 40, 15, 40, 'fridge'),
            (380, 20, 15, 40, 'stove'),
            
            # Bedroom furniture
            (20, 220, 50, 40, 'bed'),
            (80, 220, 30, 20, 'dresser'),
            (180, 220, 50, 40, 'bed'),
            (240, 220, 30, 20, 'dresser'),
            
            # Office furniture
            (620, 170, 60, 30, 'desk'),
            (620, 210, 30, 20, 'chair'),
        ]
        
        for x, y, w, h, furniture_type in furniture_data:
            rect = QRectF(x, y, w, h)
            item = FloorPlanItem('furniture', rect, furniture_type)
            item.colors['furniture'] = QColor(160, 82, 45)  # Saddle brown
            self.scene.addItem(item)
    
    def setup_view(self):
        """Setup the view settings."""
        # Set scene rectangle
        self.scene.setSceneRect(0, 0, 1000, 500)
        
        # Center the view
        self.centerOn(500, 250)
        
        # Set background
        self.setBackgroundBrush(QBrush(QColor(250, 250, 250)))
    
    def mousePressEvent(self, event):
        """Handle mouse press events."""
        if event.button() == Qt.MouseButton.LeftButton:
            # Get item under mouse
            item = self.itemAt(event.position().toPoint())
            if item and hasattr(item, 'label') and item.label:
                self.select_room(item.label)
        
        super().mousePressEvent(event)
    
    def select_room(self, room_name):
        """Select a room and emit signal."""
        # Deselect all rooms
        for room in self.rooms.values():
            room.selected = False
        
        # Select the clicked room
        if room_name in self.rooms:
            self.rooms[room_name].selected = True
            self.current_room = room_name
            self.room_selected.emit(room_name)
            self.update()
    
    def wheelEvent(self, event):
        """Handle wheel events for zooming."""
        # Get zoom factor
        zoom_factor = 1.15 if event.angleDelta().y() > 0 else 0.87
        self.zoom_factor *= zoom_factor
        
        # Limit zoom
        self.zoom_factor = max(0.1, min(5.0, self.zoom_factor))
        
        # Apply zoom
        self.scale(zoom_factor, zoom_factor)
        
        # Emit view changed signal
        self.view_changed.emit(self.pan_x, self.pan_y, self.zoom_factor)
    
    def keyPressEvent(self, event):
        """Handle key press events."""
        if event.key() == Qt.Key.Key_Plus:
            self.zoom_factor *= 1.1
            self.scale(1.1, 1.1)
        elif event.key() == Qt.Key.Key_Minus:
            self.zoom_factor *= 0.9
            self.scale(0.9, 0.9)
        elif event.key() == Qt.Key.Key_Home:
            self.reset_view()
        elif event.key() == Qt.Key.Key_Left:
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - 20)
        elif event.key() == Qt.Key.Key_Right:
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() + 20)
        elif event.key() == Qt.Key.Key_Up:
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - 20)
        elif event.key() == Qt.Key.Key_Down:
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() + 20)
    
    def reset_view(self):
        """Reset view to default."""
        self.resetTransform()
        self.zoom_factor = 1.0
        self.centerOn(500, 250)
        self.pan_x = 0.0
        self.pan_y = 0.0
        self.view_changed.emit(self.pan_x, self.pan_y, self.zoom_factor)
    
    def get_room_info(self, room_name):
        """Get information about a room."""
        if room_name in self.rooms:
            room = self.rooms[room_name]
            rect = room.rect
            return {
                'name': room_name,
                'type': room.item_type,
                'area': rect.width() * rect.height(),
                'position': (rect.x(), rect.y()),
                'size': (rect.width(), rect.height())
            }
        return None
    
    def highlight_room(self, room_name, highlight=True):
        """Highlight a specific room."""
        if room_name in self.rooms:
            self.rooms[room_name].selected = highlight
            self.update()
    
    def add_room(self, x, y, width, height, room_type, label):
        """Add a new room to the floor plan."""
        rect = QRectF(x, y, width, height)
        item = FloorPlanItem(room_type, rect, label)
        self.scene.addItem(item)
        self.rooms[label] = item
        return item
    
    def remove_room(self, room_name):
        """Remove a room from the floor plan."""
        if room_name in self.rooms:
            item = self.rooms[room_name]
            self.scene.removeItem(item)
            del self.rooms[room_name]
    
    def export_floor_plan(self, filename):
        """Export floor plan as image."""
        # This would implement floor plan export functionality
        pass
