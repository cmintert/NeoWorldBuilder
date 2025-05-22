from typing import List, Tuple, Dict, Any
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPainter, QPen, QColor, QPainterPath


class LineRenderer:
    """Handles all line rendering operations."""
    
    # Control point styling constants
    CONTROL_POINT_OUTLINE_COLOR = "#FF4444"
    CONTROL_POINT_OUTLINE_WIDTH = 2
    CONTROL_POINT_FILL_COLOR = QColor(255, 255, 255, 180)
    
    def __init__(self, config=None):
        self.config = config
    
    def draw_line(self, painter: QPainter, scaled_points: List[Tuple[int, int]], 
                  style_config: Dict[str, Any], widget_offset: Tuple[int, int]) -> None:
        """Draw the main line.
        
        Args:
            painter: QPainter instance
            scaled_points: List of scaled coordinate points
            style_config: Dictionary with line style configuration
            widget_offset: Widget's (x, y) offset
        """
        if len(scaled_points) < 2:
            return
        
        # Set up pen with style configuration
        pen = QPen(style_config.get('color', QColor("#FF0000")))
        pen.setWidth(style_config.get('width', 2))
        pen.setStyle(style_config.get('pattern', Qt.PenStyle.SolidLine))
        painter.setPen(pen)
        
        # Create and draw the line path
        path = self.create_line_path(scaled_points, widget_offset)
        painter.drawPath(path)
    
    def draw_control_points(self, painter: QPainter, control_points: List[dict], 
                           widget_offset: Tuple[int, int]) -> None:
        """Draw edit mode control points.
        
        Args:
            painter: QPainter instance
            control_points: List of control point dictionaries
            widget_offset: Widget's (x, y) offset
        """
        if not control_points:
            return
        
        # Set up control point style
        control_pen = QPen(QColor(self.CONTROL_POINT_OUTLINE_COLOR))
        control_pen.setWidth(self.CONTROL_POINT_OUTLINE_WIDTH)
        painter.setPen(control_pen)
        painter.setBrush(self.CONTROL_POINT_FILL_COLOR)
        
        widget_x, widget_y = widget_offset
        
        for cp in control_points:
            # Convert to widget-relative coordinates
            x = cp["pos"][0] - widget_x
            y = cp["pos"][1] - widget_y
            radius = cp["radius"]
            
            painter.drawEllipse(x - radius, y - radius, radius * 2, radius * 2)
    
    def create_line_path(self, scaled_points: List[Tuple[int, int]], 
                        widget_offset: Tuple[int, int]) -> QPainterPath:
        """Create QPainterPath for the line.
        
        Args:
            scaled_points: List of scaled coordinate points
            widget_offset: Widget's (x, y) offset
            
        Returns:
            QPainterPath for the line
        """
        path = QPainterPath()
        
        if len(scaled_points) < 2:
            return path
        
        widget_x, widget_y = widget_offset
        
        # Adjust points to widget's coordinate system
        adjusted_points = [
            (p[0] - widget_x, p[1] - widget_y) for p in scaled_points
        ]
        
        # Create path from points
        path.moveTo(adjusted_points[0][0], adjusted_points[0][1])
        
        for point in adjusted_points[1:]:
            path.lineTo(point[0], point[1])
        
        return path
