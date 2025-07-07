"""Line graphics item for QGraphicsView-based map rendering."""

from typing import List, Tuple, Optional, Dict, Any

from PyQt6.QtCore import Qt, QRectF, QPointF
from PyQt6.QtGui import QPainter, QPen, QColor, QBrush, QPainterPath, QCursor, QPainterPathStroker
from PyQt6.QtWidgets import QGraphicsItem, QGraphicsTextItem, QStyleOptionGraphicsItem, QWidget
from structlog import get_logger

# Import existing line components for reuse
from ui.components.map_component.edit_mode import UnifiedLineGeometry, UnifiedLineRenderer

logger = get_logger(__name__)


class LineGraphicsItem(QGraphicsItem):
    """Graphics item representing a map line with interactive control points.
    
    This replaces the widget-based LineContainer with a QGraphicsItem
    implementation that integrates with the existing line geometry system.
    """
    
    feature_type = 'line'
    
    # Line appearance constants (from LineContainer)
    DEFAULT_LINE_COLOR = "#FF0000"
    DEFAULT_LINE_WIDTH = 2
    DEFAULT_LINE_PATTERN = Qt.PenStyle.SolidLine
    
    # Control point constants
    BASE_CONTROL_POINT_RADIUS = 4
    MIN_CONTROL_POINT_RADIUS = 3
    
    # Label styling
    LABEL_FONT_SIZE_BASE = 8
    MIN_LABEL_FONT_SIZE = 6
    
    def __init__(self, target_node: str, points_or_branches: List,
                 config: Optional[Dict[str, Any]] = None, 
                 style_properties: Optional[Dict[str, Any]] = None, parent=None):
        """Initialize the line graphics item.
        
        Args:
            target_node: Name of the node this line represents
            points_or_branches: List of points for simple line, or list of branches
            config: Configuration object
            parent: Parent graphics item
        """
        super().__init__(parent)
        
        self.target_node = target_node
        self.config = config or {}
        self._scale = 1.0
        self.edit_mode = False
        
        # Initialize geometry and rendering components
        self.geometry = UnifiedLineGeometry(points_or_branches)
        self.renderer = UnifiedLineRenderer(self.config)
        # Hit testing handled natively by QGraphicsItem
        
        # Visual style properties - use style_properties if provided
        style_props = style_properties or {}
        logger.debug(f"LineGraphicsItem received style properties: {style_props}")
        
        self.line_color = QColor(style_props.get('color', self.DEFAULT_LINE_COLOR))
        # Handle width - convert to int if it's a string or empty
        width_value = style_props.get('width', self.DEFAULT_LINE_WIDTH)
        if isinstance(width_value, str):
            if width_value.strip():
                try:
                    self.line_width = int(width_value)
                except ValueError:
                    self.line_width = self.DEFAULT_LINE_WIDTH
            else:
                self.line_width = self.DEFAULT_LINE_WIDTH
        else:
            self.line_width = width_value
        # Convert pattern string to Qt enum if needed
        pattern_str = style_props.get('pattern', 'solid')
        if pattern_str == 'dashed':
            self.line_pattern = Qt.PenStyle.DashLine
        elif pattern_str == 'dotted':
            self.line_pattern = Qt.PenStyle.DotLine
        else:
            self.line_pattern = Qt.PenStyle.SolidLine
            
        logger.debug(f"LineGraphicsItem using color: {self.line_color.name()}, width: {self.line_width}, pattern: {self.line_pattern}")
        
        # Drag state for control points
        self.dragging_control_point = False
        self.dragged_branch_index = 0
        self.dragged_point_index = -1
        self.drag_start_pos = QPointF()
        
        # Set item flags
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setAcceptHoverEvents(True)
        
        # Create text label
        self.text_item = QGraphicsTextItem(self.target_node, self)
        self._setup_text_label()
        
        # Set Z-value for lines (below pins but above background)
        self.setZValue(50)
        
        # Update geometry
        self._update_bounds()
        
        logger.debug(f"Created LineGraphicsItem for {target_node} with {len(points_or_branches)} elements")
    
    def _setup_text_label(self) -> None:
        """Set up the text label for the line."""
        # Position label at the midpoint of the first branch
        if self.geometry.branches and self.geometry.branches[0]:
            midpoint = self._get_line_midpoint()
            self.text_item.setPos(midpoint.x(), midpoint.y())
        
        # Style the text
        self._update_text_style()
    
    def _get_line_midpoint(self) -> QPointF:
        """Get the midpoint of the line for label positioning.
        
        Returns:
            Midpoint coordinates
        """
        if not self.geometry.branches or not self.geometry.branches[0]:
            return QPointF(0, 0)
        
        points = self.geometry.branches[0]
        if len(points) < 2:
            return QPointF(points[0][0] if points else 0, points[0][1] if points else 0)
        
        # Find the midpoint along the line path
        total_length = 0
        segment_lengths = []
        
        for i in range(len(points) - 1):
            p1 = QPointF(points[i][0], points[i][1])
            p2 = QPointF(points[i + 1][0], points[i + 1][1])
            length = (p2 - p1).manhattanLength()
            segment_lengths.append(length)
            total_length += length
        
        if total_length == 0:
            return QPointF(points[0][0], points[0][1])
        
        # Find the segment containing the midpoint
        target_length = total_length / 2
        current_length = 0
        
        for i, segment_length in enumerate(segment_lengths):
            if current_length + segment_length >= target_length:
                # Midpoint is in this segment
                ratio = (target_length - current_length) / segment_length
                p1 = QPointF(points[i][0], points[i][1])
                p2 = QPointF(points[i + 1][0], points[i + 1][1])
                return p1 + ratio * (p2 - p1)
            current_length += segment_length
        
        # Fallback to last point
        return QPointF(points[-1][0], points[-1][1])
    
    def _update_text_style(self) -> None:
        """Update text label styling based on scale."""
        font_size = max(int(self.LABEL_FONT_SIZE_BASE * self._scale), self.MIN_LABEL_FONT_SIZE)
        font = self.text_item.font()
        font.setPointSize(font_size)
        self.text_item.setFont(font)
        
        # Set text color to white for visibility
        self.text_item.setDefaultTextColor(QColor(255, 255, 255))
    
    def _update_bounds(self) -> None:
        """Update the item's bounds based on line geometry."""
        if not self.geometry.branches:
            return
        
        # Get bounds from geometry
        min_x, min_y, max_x, max_y = self.geometry.get_bounds()
        
        if min_x == max_x and min_y == max_y:
            # Single point or no valid bounds
            return
        
        # Tell Qt that the geometry is about to change
        self.prepareGeometryChange()
        
        # Add padding for control points and labels
        padding = max(self.BASE_CONTROL_POINT_RADIUS * 2, 10)
        self._bounds = QRectF(
            min_x - padding,
            min_y - padding,
            max_x - min_x + 2 * padding,
            max_y - min_y + 2 * padding
        )
        
        logger.debug(f"Updated bounds for {self.target_node}: {self._bounds}")
    
    def boundingRect(self) -> QRectF:
        """Return the bounding rectangle of the line.
        
        Returns:
            Bounding rectangle in item coordinates
        """
        if hasattr(self, '_bounds'):
            return self._bounds
        
        # Fallback bounds
        return QRectF(-10, -10, 20, 20)
    
    def shape(self) -> QPainterPath:
        """Return the precise shape for hit testing.
        
        Returns:
            QPainterPath representing the line's shape
        """
        path = QPainterPath()
        
        if not self.geometry.branches:
            return path
        
        # Create path for all branches
        for branch in self.geometry.branches:
            if len(branch) < 2:
                continue
            
            branch_path = QPainterPath()
            branch_path.moveTo(branch[0][0], branch[0][1])
            
            for point in branch[1:]:
                branch_path.lineTo(point[0], point[1])
            
            # Create stroke path for better hit testing
            # Use QPainterPathStroker for creating hit area
            stroker = QPainterPathStroker()
            stroker.setWidth(max(self.line_width, 5))  # Minimum hit area
            stroke_path = stroker.createStroke(branch_path)
            path.addPath(stroke_path)
        
        return path
    
    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: Optional[QWidget] = None) -> None:
        """Paint the line and control points.
        
        Args:
            painter: QPainter instance
            option: Style options
            widget: Widget being painted on
        """
        if not self.geometry.branches:
            return
        
        # Draw all branches
        for branch_idx, branch in enumerate(self.geometry.branches):
            if len(branch) < 2:
                continue
            
            # Set up pen
            pen = QPen(self.line_color)
            pen.setWidth(self.line_width)
            pen.setStyle(self.line_pattern)
            painter.setPen(pen)
            
            # Draw the line
            path = QPainterPath()
            path.moveTo(branch[0][0], branch[0][1])
            
            for point in branch[1:]:
                path.lineTo(point[0], point[1])
            
            painter.drawPath(path)
        
        # Draw control points in edit mode
        if self.edit_mode:
            self._draw_control_points(painter)
        
        # Draw text background
        if self.text_item:
            text_rect = self.text_item.boundingRect()
            text_pos = self.text_item.pos()
            
            # Draw semi-transparent background behind text
            bg_rect = QRectF(
                text_pos.x() - 2,
                text_pos.y() - 1,
                text_rect.width() + 4,
                text_rect.height() + 2
            )
            
            painter.setBrush(QBrush(QColor(0, 0, 0, 50)))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(bg_rect, 3, 3)
    
    def _draw_control_points(self, painter: QPainter) -> None:
        """Draw control points for edit mode.
        
        Args:
            painter: QPainter instance
        """
        control_pen = QPen(QColor("#FF4444"))
        control_pen.setWidth(2)
        painter.setPen(control_pen)
        painter.setBrush(QBrush(QColor(255, 255, 255, 180)))
        
        radius = max(int(self.BASE_CONTROL_POINT_RADIUS * self._scale), self.MIN_CONTROL_POINT_RADIUS)
        
        # Draw control points for all branches
        for branch_idx, branch in enumerate(self.geometry.branches):
            for point_idx, point in enumerate(branch):
                x, y = point[0], point[1]
                
                # Check if this is a shared point (branching point)
                is_shared = self._is_shared_point(point, branch_idx, point_idx)
                
                if is_shared:
                    # Draw blue for shared/branching points
                    painter.setBrush(QBrush(QColor(100, 150, 255, 180)))
                else:
                    # Draw white for regular control points
                    painter.setBrush(QBrush(QColor(255, 255, 255, 180)))
                
                painter.drawEllipse(x - radius, y - radius, radius * 2, radius * 2)
    
    def _is_shared_point(self, point: Tuple[int, int], branch_idx: int, point_idx: int) -> bool:
        """Check if a point is shared between branches.
        
        Args:
            point: The point coordinates
            branch_idx: Branch index
            point_idx: Point index within branch
            
        Returns:
            True if the point is shared
        """
        if not self.geometry.is_branching:
            return False
        
        point_key = (int(point[0]), int(point[1]))
        return point_key in self.geometry._shared_points
    
    def mousePressEvent(self, event) -> None:
        """Handle mouse press events.
        
        Args:
            event: Mouse press event
        """
        if event.button() == Qt.MouseButton.LeftButton:
            if self.edit_mode:
                # Check if clicking on a control point
                hit_result = self._test_control_point_hit(event.pos())
                if hit_result:
                    self.dragging_control_point = True
                    self.dragged_branch_index = hit_result[0]
                    self.dragged_point_index = hit_result[1]
                    self.drag_start_pos = event.pos()
                    event.accept()
                    return
            
            # Not dragging, emit click signal
            self._emit_click_signal()
            event.accept()
        elif event.button() == Qt.MouseButton.RightButton:
            # Handle right-click for context menu
            self._show_context_menu(event.pos())
            event.accept()
        else:
            super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event) -> None:
        """Handle mouse move events.
        
        Args:
            event: Mouse move event
        """
        if self.edit_mode:
            if self.dragging_control_point:
                # Update control point position
                self._update_control_point_position(event.pos())
                event.accept()
                return
            else:
                # Update cursor based on hover
                self._update_hover_cursor(event.pos())
        
        super().mouseMoveEvent(event)
    
    def mouseReleaseEvent(self, event) -> None:
        """Handle mouse release events.
        
        Args:
            event: Mouse release event
        """
        if event.button() == Qt.MouseButton.LeftButton and self.dragging_control_point:
            self.dragging_control_point = False
            
            # Final bounds update after drag completion
            logger.debug(f"Drag completed for {self.target_node}, updating bounds")
            self._update_bounds()
            self.update()
            
            self._emit_geometry_changed()
            event.accept()
        else:
            super().mouseReleaseEvent(event)
    
    def hoverMoveEvent(self, event) -> None:
        """Handle hover move events.
        
        Args:
            event: Hover event
        """
        if self.edit_mode:
            self._update_hover_cursor(event.pos())
        super().hoverMoveEvent(event)
    
    def _test_control_point_hit(self, pos: QPointF) -> Optional[Tuple[int, int]]:
        """Test if position hits a control point.
        
        Args:
            pos: Position to test
            
        Returns:
            Tuple of (branch_index, point_index) if hit, None otherwise
        """
        radius = max(int(self.BASE_CONTROL_POINT_RADIUS * self._scale), self.MIN_CONTROL_POINT_RADIUS)
        hit_distance = radius + 2  # Small tolerance
        
        for branch_idx, branch in enumerate(self.geometry.branches):
            for point_idx, point in enumerate(branch):
                point_pos = QPointF(point[0], point[1])
                distance = (pos - point_pos).manhattanLength()
                
                if distance <= hit_distance:
                    return (branch_idx, point_idx)
        
        return None
    
    def _update_control_point_position(self, pos: QPointF) -> None:
        """Update control point position during drag.
        
        Args:
            pos: New position
        """
        if (self.dragged_branch_index >= 0 and self.dragged_point_index >= 0 and
            self.dragged_branch_index < len(self.geometry.branches) and
            self.dragged_point_index < len(self.geometry.branches[self.dragged_branch_index])):
            
            # Update the point position
            self.geometry.branches[self.dragged_branch_index][self.dragged_point_index] = [
                int(pos.x()), int(pos.y())
            ]
            
            # Update shared points if this is a branching line
            if self.geometry.is_branching:
                self.geometry._update_shared_points()
            
            # CRITICAL: Update scaled branches to reflect the new position
            # This ensures get_bounds() uses the updated coordinates
            self.geometry._update_scaled_branches()
            
            # Update bounds and visual
            self._update_bounds()
            self.update()
    
    def _update_hover_cursor(self, pos: QPointF) -> None:
        """Update cursor based on hover position.
        
        Args:
            pos: Mouse position
        """
        if self._test_control_point_hit(pos):
            self.setCursor(QCursor(Qt.CursorShape.SizeAllCursor))
        else:
            self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
    
    def set_scale(self, scale: float) -> None:
        """Set the display scale for the line.
        
        Args:
            scale: Scale factor
        """
        self._scale = scale
        self.geometry.set_scale(scale)
        self._update_text_style()
        self._update_bounds()
        self.update()
    
    def set_edit_mode(self, enabled: bool) -> None:
        """Enable or disable edit mode.
        
        Args:
            enabled: Whether edit mode should be enabled
        """
        self.edit_mode = enabled
        self.update()  # Redraw to show/hide control points
    
    def update_geometry(self, points_or_branches: List) -> None:
        """Update the line geometry.
        
        Args:
            points_or_branches: New geometry data
        """
        self.geometry = UnifiedLineGeometry(points_or_branches)
        self._update_bounds()
        
        # Update label position
        midpoint = self._get_line_midpoint()
        self.text_item.setPos(midpoint.x(), midpoint.y())
        
        self.update()
    
    def get_geometry_data(self) -> List:
        """Get the current geometry data.
        
        Returns:
            Current geometry as list of branches or points
        """
        if self.geometry.is_branching:
            return [branch.copy() for branch in self.geometry.branches]
        else:
            return self.geometry.branches[0].copy() if self.geometry.branches else []
    
    def _emit_click_signal(self) -> None:
        """Emit click signal through signal bridge."""
        # Find signal bridge through scene's feature manager
        scene = self.scene()
        if scene and hasattr(scene, 'feature_items'):
            parent_widget = scene.parent()
            while parent_widget:
                if hasattr(parent_widget, 'graphics_adapter'):
                    if hasattr(parent_widget.graphics_adapter, 'signal_bridge'):
                        parent_widget.graphics_adapter.signal_bridge.line_clicked.emit(self.target_node)
                        break
                    elif hasattr(parent_widget.graphics_adapter, 'feature_manager'):
                        if hasattr(parent_widget.graphics_adapter.feature_manager, 'signal_bridge'):
                            parent_widget.graphics_adapter.feature_manager.signal_bridge.line_clicked.emit(self.target_node)
                            break
                parent_widget = getattr(parent_widget, 'parent', lambda: None)()
        
        logger.debug(f"Line clicked: {self.target_node}")
    
    def _emit_geometry_changed(self) -> None:
        """Emit geometry changed signal."""
        geometry_data = self.get_geometry_data()
        
        # Find signal bridge
        scene = self.scene()
        if scene and hasattr(scene, 'feature_items'):
            parent_widget = scene.parent()
            while parent_widget:
                if hasattr(parent_widget, 'graphics_adapter'):
                    if hasattr(parent_widget.graphics_adapter, 'signal_bridge'):
                        parent_widget.graphics_adapter.signal_bridge.line_geometry_changed.emit(self.target_node, geometry_data)
                        break
                    elif hasattr(parent_widget.graphics_adapter, 'feature_manager'):
                        if hasattr(parent_widget.graphics_adapter.feature_manager, 'signal_bridge'):
                            parent_widget.graphics_adapter.feature_manager.signal_bridge.line_geometry_changed.emit(self.target_node, geometry_data)
                            break
                parent_widget = getattr(parent_widget, 'parent', lambda: None)()
        
        logger.debug(f"Line geometry changed: {self.target_node}")
    
    def _show_context_menu(self, pos) -> None:
        """Show context menu for line operations.
        
        Args:
            pos: Position where right-click occurred
        """
        from PyQt6.QtWidgets import QMenu, QApplication
        
        menu = QMenu()
        
        # Check if this line supports branching (MultiLineString vs LineString)
        if self.geometry.is_branching:
            # MultiLineString - can create branches
            create_branch_action = menu.addAction("Create Branch")
            create_branch_action.triggered.connect(lambda: self._start_branch_creation(pos))
        else:
            # LineString - offer conversion option
            convert_action = menu.addAction("Convert to Branching Line")
            convert_action.triggered.connect(lambda: self._convert_to_branching_line())
            
            # Also show create branch action but it will be disabled/informational
            create_branch_action = menu.addAction("Create Branch (requires conversion)")
            create_branch_action.setEnabled(False)
        
        # Convert item position to global position for menu
        global_pos = self.mapToScene(pos)
        scene = self.scene()
        if scene:
            views = scene.views()
            if views:
                view = views[0]
                view_pos = view.mapFromScene(global_pos)
                global_pos = view.mapToGlobal(view_pos)
                
                # Show menu
                menu.exec(global_pos)
    
    def _start_branch_creation(self, pos) -> None:
        """Start branch creation from the clicked position.
        
        Args:
            pos: Position where the branch should start
        """
        logger.info(f"Starting branch creation from context menu at {pos}")
        
        # Check if this line supports branching (Option A enforcement)
        if not self.geometry.is_branching:
            logger.warning(f"Cannot create branch on LineString geometry {self.target_node}")
            return
        
        # Convert position to original coordinates
        scene_pos = self.mapToScene(pos)
        scene = self.scene()
        if scene and hasattr(scene, 'scene_to_original_coords'):
            original_coords = scene.scene_to_original_coords(scene_pos)
            
            # Find the parent widget to set branch creation mode
            parent_widget = scene.parent()
            while parent_widget:
                if hasattr(parent_widget, 'graphics_adapter'):
                    # Get the actual map tab
                    map_tab = parent_widget.graphics_adapter.map_tab
                    
                    # Set branch creation mode
                    map_tab.mode_manager.branch_creation_mode = True
                    map_tab.mode_manager.set_branch_creation_target(self.target_node)
                    map_tab.mode_manager.set_branch_creation_start_point(original_coords)
                    
                    # Update cursor
                    if hasattr(map_tab, 'image_label'):
                        map_tab.image_label.set_cursor_for_mode("crosshair")
                    
                    logger.info(f"Branch creation mode activated for {self.target_node} at {original_coords}")
                    break
                parent_widget = getattr(parent_widget, 'parent', lambda: None)()

    def _convert_to_branching_line(self) -> None:
        """Convert this LineString to MultiLineString geometry to support branching.
        
        This method converts the current simple line to a branching line format
        in both the visual representation and the database.
        """
        logger.info(f"Converting {self.target_node} from LineString to MultiLineString")
        
        if self.geometry.is_branching:
            logger.warning(f"Line {self.target_node} is already a branching line")
            return
        
        # Get current geometry
        current_points = self.get_geometry_data()
        if not current_points or len(current_points) < 2:
            logger.error(f"Cannot convert line {self.target_node}: insufficient points")
            return
        
        # Convert to branching format (list of branches)
        branching_geometry = [current_points]
        
        # Update the visual geometry
        self.update_geometry(branching_geometry)
        
        # Mark as branching
        self.geometry.is_branching = True
        self.geometry._update_shared_points()
        self.geometry._update_scaled_branches()
        
        # Update the visual
        self._update_bounds()
        self.update()
        
        # Emit geometry changed signal to update database
        self._emit_geometry_changed()
        
        logger.info(f"Successfully converted {self.target_node} to branching line")