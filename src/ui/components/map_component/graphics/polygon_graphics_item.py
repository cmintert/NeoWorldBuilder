"""
Polygon graphics item for map visualization.
Handles rendering and interaction for polygon features.
"""

from typing import Dict, List, Optional, Tuple

from PyQt6.QtCore import QPointF, Qt, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QPainter, QPainterPath, QPen, QPolygonF
from PyQt6.QtWidgets import QGraphicsItem, QGraphicsPolygonItem, QStyleOptionGraphicsItem, QWidget

from ..utils.map_logger import get_map_logger

logger = get_map_logger(__name__)


class PolygonGraphicsItem(QGraphicsPolygonItem):
    """Graphics item for rendering polygon features on the map."""

    def __init__(
        self,
        points: List[Tuple[float, float]],
        feature_id: str,
        node_name: str,
        style: Optional[Dict] = None,
        parent: Optional[QGraphicsItem] = None
    ):
        """
        Initialize polygon graphics item.
        
        Args:
            points: List of (x, y) coordinates defining the polygon
            feature_id: Unique identifier for this feature
            node_name: Name of the associated node
            style: Visual style properties (fill_color, fill_opacity, outline_color, etc.)
            parent: Parent graphics item
        """
        # Create QPolygonF from points
        polygon = QPolygonF([QPointF(x, y) for x, y in points])
        super().__init__(polygon, parent)

        self.feature_type = 'polygon'  # Identifier for signal bridge
        self.feature_id = feature_id
        self.node_name = node_name
        self._is_hovered = False
        self._is_selected = False
        self._edit_mode = False
        
        # Default style
        self._base_style = {
            'fill_color': '#4a90e2',
            'fill_opacity': 0.3,
            'outline_color': '#2c5aa0',
            'outline_width': 2.0,
            'outline_pattern': 'solid'
        }
        
        # Update with provided style
        if style:
            self._base_style.update(style)
        
        # Set initial appearance
        self._update_appearance()
        
        # Set item flags
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setAcceptHoverEvents(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        
        # Control points for edit mode
        self._control_points: List[QGraphicsItem] = []
        
        logger.debug(
            "Created polygon graphics item",
            feature_id=feature_id,
            node_name=node_name,
            point_count=len(points)
        )
    
    def _update_appearance(self) -> None:
        """Update the visual appearance based on current state."""
        # Determine colors based on state
        if self._is_selected:
            outline_color = QColor('#ff6b6b')  # Red for selected
            outline_width = self._base_style['outline_width'] + 1
            fill_opacity = min(self._base_style['fill_opacity'] + 0.1, 1.0)
        elif self._is_hovered:
            outline_color = QColor('#ffd93d')  # Yellow for hover
            outline_width = self._base_style['outline_width'] + 0.5
            fill_opacity = min(self._base_style['fill_opacity'] + 0.05, 1.0)
        else:
            outline_color = QColor(self._base_style['outline_color'])
            outline_width = self._base_style['outline_width']
            fill_opacity = self._base_style['fill_opacity']
        
        # Set outline pen
        pen = QPen(outline_color, outline_width)
        
        # Set pen pattern
        pattern_map = {
            'solid': Qt.PenStyle.SolidLine,
            'dashed': Qt.PenStyle.DashLine,
            'dotted': Qt.PenStyle.DotLine,
            'dashdot': Qt.PenStyle.DashDotLine
        }
        pen.setStyle(pattern_map.get(self._base_style['outline_pattern'], Qt.PenStyle.SolidLine))
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        self.setPen(pen)
        
        # Set fill brush
        fill_color = QColor(self._base_style['fill_color'])
        fill_color.setAlphaF(fill_opacity)
        self.setBrush(QBrush(fill_color))
    
    def set_selected(self, selected: bool) -> None:
        """Set the selected state of the polygon."""
        if self._is_selected != selected:
            self._is_selected = selected
            self._update_appearance()
            logger.debug(
                "Polygon selection changed",
                feature_id=self.feature_id,
                selected=selected
            )
    
    def set_edit_mode(self, enabled: bool) -> None:
        """Enable or disable edit mode for the polygon."""
        if self._edit_mode != enabled:
            self._edit_mode = enabled
            if enabled:
                self._show_control_points()
            else:
                self._hide_control_points()
            logger.debug(
                "Polygon edit mode changed",
                feature_id=self.feature_id,
                enabled=enabled
            )
    
    def _show_control_points(self) -> None:
        """Show control points for editing vertices."""
        # Clear existing control points
        self._hide_control_points()
        
        # Create control points for each vertex
        polygon = self.polygon()
        for i in range(polygon.count()):
            point = polygon.at(i)
            control_point = QGraphicsPolygonItem(self)
            
            # Create a small square for the control point
            size = 8
            square = QPolygonF([
                QPointF(-size/2, -size/2),
                QPointF(size/2, -size/2),
                QPointF(size/2, size/2),
                QPointF(-size/2, size/2)
            ])
            control_point.setPolygon(square)
            control_point.setPos(point)
            
            # Style the control point
            control_point.setPen(QPen(QColor('#ff6b6b'), 2))
            control_point.setBrush(QBrush(QColor('#ffffff')))
            control_point.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
            control_point.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
            control_point.setCursor(Qt.CursorShape.SizeAllCursor)
            control_point.setZValue(self.zValue() + 1)
            
            # Store the vertex index on the control point for later reference
            control_point.vertex_index = i
            
            # Create a custom control point class that can handle movement
            control_point.itemChange = lambda change, value, idx=i: self._handle_control_point_change(change, value, idx)
            
            self._control_points.append(control_point)
    
    def _handle_control_point_change(self, change, value, vertex_index: int):
        """Handle control point movement and update polygon geometry.
        
        Args:
            change: The type of change (QGraphicsItem.ItemPositionChange, etc.)
            value: The new value
            vertex_index: Index of the vertex being moved
        """
        from PyQt6.QtWidgets import QGraphicsItem
        
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange:
            # Update the polygon vertex at this index
            new_pos = value  # This is a QPointF
            
            # Get current polygon points
            polygon = self.polygon()
            points = []
            for i in range(polygon.count()):
                if i == vertex_index:
                    # Use the new position for this vertex
                    points.append((new_pos.x(), new_pos.y()))
                else:
                    # Keep existing position
                    point = polygon.at(i)
                    points.append((point.x(), point.y()))
            
            # Update the polygon with new points (keep as floats for precision)
            self.update_vertices(points)
            
            # Emit geometry change signal for database persistence
            self._emit_geometry_changed()
            
            logger.debug(f"Updated polygon vertex {vertex_index} to ({new_pos.x()}, {new_pos.y()})")
        
        return value
    
    def _emit_geometry_changed(self) -> None:
        """Emit signal that polygon geometry has changed."""
        # Convert polygon points to list of tuples for persistence
        polygon = self.polygon()
        points = []
        for i in range(polygon.count()):
            point = polygon.at(i)
            points.append((point.x(), point.y()))
        
        # Emit through parent container if available
        if hasattr(self.parentItem(), 'geometry_changed'):
            self.parentItem().geometry_changed.emit(self.feature_id, points)
        elif hasattr(self.scene(), 'geometry_changed'):
            self.scene().geometry_changed.emit(self.feature_id, points)
    
    def _hide_control_points(self) -> None:
        """Hide control points."""
        for control_point in self._control_points:
            control_point.setParentItem(None)
            if control_point.scene():
                control_point.scene().removeItem(control_point)
        self._control_points.clear()
    
    def update_style(self, style: Dict) -> None:
        """Update the polygon's visual style."""
        self._base_style.update(style)
        self._update_appearance()
        logger.debug(
            "Updated polygon style",
            feature_id=self.feature_id,
            style=style
        )
    
    def get_vertices(self) -> List[Tuple[float, float]]:
        """Get the current vertex positions."""
        polygon = self.polygon()
        return [(point.x(), point.y()) for point in polygon]
    
    def update_vertices(self, points: List[Tuple[float, float]]) -> None:
        """Update the polygon vertices."""
        polygon = QPolygonF([QPointF(x, y) for x, y in points])
        self.setPolygon(polygon)
        
        # Update control points if in edit mode
        if self._edit_mode:
            self._show_control_points()
        
        logger.debug(
            "Updated polygon vertices",
            feature_id=self.feature_id,
            vertex_count=len(points)
        )
    
    # Qt event handlers
    def hoverEnterEvent(self, event) -> None:
        """Handle mouse hover enter."""
        self._is_hovered = True
        self._update_appearance()
        super().hoverEnterEvent(event)
    
    def hoverLeaveEvent(self, event) -> None:
        """Handle mouse hover leave."""
        self._is_hovered = False
        self._update_appearance()
        super().hoverLeaveEvent(event)
    
    def mousePressEvent(self, event) -> None:
        """Handle mouse press events."""
        if event.button() == Qt.MouseButton.LeftButton and not self._edit_mode:
            # Emit clicked signal (will be connected in container)
            logger.debug(
                "Polygon clicked",
                feature_id=self.feature_id,
                node_name=self.node_name
            )
        super().mousePressEvent(event)
    
    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: Optional[QWidget] = None) -> None:
        """Custom paint method for additional rendering control."""
        # Let the base class handle the standard polygon rendering
        super().paint(painter, option, widget)
        
        # Additional custom rendering can be added here if needed
        # For example, drawing vertex markers in edit mode