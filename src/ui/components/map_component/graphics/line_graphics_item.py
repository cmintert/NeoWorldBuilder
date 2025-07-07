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
        
        # UX Enhancement: Performance optimization flags
        self._is_being_dragged = False
        self._pending_updates = False
        
        # UX Enhancement: Visual feedback states
        self._is_highlighted = False
        self._preview_branch = None
        self._snap_preview = None
        
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
    
    def _draw_selection_outline(self, painter: QPainter) -> None:
        """Draw GIS-standard selection outline around the line.
        
        Args:
            painter: QPainter instance
        """
        # GIS Enhancement: Draw selection halo
        for branch in self.geometry.branches:
            if len(branch) < 2:
                continue
                
            # Create selection outline pen
            outline_pen = QPen(QColor(0, 120, 255, 180))  # Blue selection color
            outline_pen.setWidth(self.line_width + 4)  # Wider than main line
            outline_pen.setStyle(Qt.PenStyle.SolidLine)
            
            painter.setPen(outline_pen)
            
            # Draw outline path
            path = QPainterPath()
            path.moveTo(branch[0][0], branch[0][1])
            
            for point in branch[1:]:
                path.lineTo(point[0], point[1])
            
            painter.drawPath(path)
    
    def _draw_preview_branch(self, painter: QPainter) -> None:
        """Draw preview branch during creation mode.
        
        Args:
            painter: QPainter instance
        """
        if not self._preview_branch:
            return
            
        start_point, end_point = self._preview_branch
        
        # GIS Enhancement: Dashed preview line
        preview_pen = QPen(QColor(255, 165, 0, 200))  # Orange preview color
        preview_pen.setWidth(max(2, self.line_width))
        preview_pen.setStyle(Qt.PenStyle.DashLine)
        
        painter.setPen(preview_pen)
        painter.drawLine(start_point, end_point)
        
        # Draw preview endpoints
        endpoint_brush = QBrush(QColor(255, 165, 0, 150))
        painter.setBrush(endpoint_brush)
        painter.setPen(Qt.PenStyle.NoPen)
        
        # Use the center point and radius overload
        painter.drawEllipse(start_point, 4.0, 4.0)
        painter.drawEllipse(end_point, 4.0, 4.0)
    
    def _draw_snap_preview(self, painter: QPainter) -> None:
        """Draw snap point preview for precise positioning.
        
        Args:
            painter: QPainter instance
        """
        if not self._snap_preview:
            return
            
        # GIS Enhancement: Snap indicator circle
        snap_pen = QPen(QColor(255, 0, 255, 200))  # Magenta snap color
        snap_pen.setWidth(2)
        
        painter.setPen(snap_pen)
        painter.setBrush(QBrush(QColor(255, 0, 255, 50)))
        
        # Draw snap circle
        snap_radius = 6
        painter.drawEllipse(
            int(self._snap_preview.x() - snap_radius),
            int(self._snap_preview.y() - snap_radius),
            snap_radius * 2,
            snap_radius * 2
        )
    
    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: Optional[QWidget] = None) -> None:
        """Paint the line with enhanced GIS-standard visual feedback.
        
        Args:
            painter: QPainter instance
            option: Style options
            widget: Widget being painted on
        """
        if not self.geometry.branches:
            return
        
        # GIS Enhancement: Selection/highlight outline
        if self._is_highlighted:
            self._draw_selection_outline(painter)
        
        # Draw all branches
        for branch_idx, branch in enumerate(self.geometry.branches):
            if len(branch) < 2:
                continue
            
            # Set up pen with enhanced styling
            pen = QPen(self.line_color)
            pen.setWidth(self.line_width)
            pen.setStyle(self.line_pattern)
            
            # GIS Enhancement: Anti-aliasing for smooth lines
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            painter.setPen(pen)
            
            # Draw the line
            path = QPainterPath()
            path.moveTo(branch[0][0], branch[0][1])
            
            for point in branch[1:]:
                path.lineTo(point[0], point[1])
            
            painter.drawPath(path)
        
        # GIS Enhancement: Draw preview branch during creation
        if self._preview_branch:
            self._draw_preview_branch(painter)
        
        # GIS Enhancement: Draw snap preview
        if self._snap_preview:
            self._draw_snap_preview(painter)
        
        # Draw control points in edit mode
        if self.edit_mode:
            self._draw_control_points(painter)
        
        # Draw text background
        if self.text_item:
            text_rect = self.text_item.boundingRect()
            text_pos = self.text_item.pos()
            
            # Enhanced text background with better visibility
            bg_rect = QRectF(
                text_pos.x() - 3,
                text_pos.y() - 2,
                text_rect.width() + 6,
                text_rect.height() + 4
            )
            
            # GIS Enhancement: Better contrast background
            painter.setBrush(QBrush(QColor(0, 0, 0, 120)))
            painter.setPen(QPen(QColor(255, 255, 255, 80), 1))
            painter.drawRoundedRect(bg_rect, 4, 4)
    
    def _draw_control_points(self, painter: QPainter) -> None:
        """Draw enhanced GIS-style control points for edit mode.
        
        Args:
            painter: QPainter instance
        """
        # GIS Enhancement: Scale-responsive control points
        base_radius = max(int(self.BASE_CONTROL_POINT_RADIUS * self._scale), self.MIN_CONTROL_POINT_RADIUS)
        
        # Draw control points for all branches
        for branch_idx, branch in enumerate(self.geometry.branches):
            for point_idx, point in enumerate(branch):
                x, y = point[0], point[1]
                
                # Check if this is a shared point (branching point)
                is_shared = self._is_shared_point(point, branch_idx, point_idx)
                
                # GIS Enhancement: Different styles for different point types
                if is_shared:
                    # Branching points: Diamond shape with blue color
                    self._draw_branching_point(painter, x, y, base_radius + 2)
                elif point_idx == 0 or point_idx == len(branch) - 1:
                    # Endpoints: Square with green color
                    self._draw_endpoint(painter, x, y, base_radius)
                else:
                    # Regular control points: Circle with white color
                    self._draw_regular_point(painter, x, y, base_radius - 1)
    
    def _draw_branching_point(self, painter: QPainter, x: float, y: float, radius: int) -> None:
        """Draw a diamond-shaped branching point."""
        # GIS Enhancement: Diamond shape for branching points
        diamond_pen = QPen(QColor(0, 100, 200), 2)
        diamond_brush = QBrush(QColor(100, 150, 255, 200))
        
        painter.setPen(diamond_pen)
        painter.setBrush(diamond_brush)
        
        # Create diamond path
        diamond = QPainterPath()
        diamond.moveTo(x, y - radius)  # Top
        diamond.lineTo(x + radius, y)  # Right
        diamond.lineTo(x, y + radius)  # Bottom
        diamond.lineTo(x - radius, y)  # Left
        diamond.closeSubpath()
        
        painter.drawPath(diamond)
    
    def _draw_endpoint(self, painter: QPainter, x: float, y: float, radius: int) -> None:
        """Draw a square-shaped endpoint."""
        # GIS Enhancement: Square shape for endpoints
        endpoint_pen = QPen(QColor(0, 150, 0), 2)
        endpoint_brush = QBrush(QColor(100, 255, 100, 180))
        
        painter.setPen(endpoint_pen)
        painter.setBrush(endpoint_brush)
        
        # Draw square
        painter.drawRect(x - radius, y - radius, radius * 2, radius * 2)
    
    def _draw_regular_point(self, painter: QPainter, x: float, y: float, radius: int) -> None:
        """Draw a circular regular control point."""
        # GIS Enhancement: Circle with outline for regular points
        point_pen = QPen(QColor(100, 100, 100), 1)
        point_brush = QBrush(QColor(255, 255, 255, 200))
        
        painter.setPen(point_pen)
        painter.setBrush(point_brush)
        
        # Draw circle with subtle shadow effect
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
        """Handle mouse press events with enhanced UX feedback.
        
        Args:
            event: Mouse press event
        """
        if event.button() == Qt.MouseButton.LeftButton:
            if self.edit_mode:
                # Check if clicking on a control point
                hit_result = self._test_control_point_hit(event.pos())
                if hit_result:
                    # Shift+click on control point = delete point
                    if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                        self._delete_control_point(hit_result[0], hit_result[1])
                        event.accept()
                        return
                    else:
                        # Regular click on control point = start dragging
                        self.dragging_control_point = True
                        self.dragged_branch_index = hit_result[0]
                        self.dragged_point_index = hit_result[1]
                        self.drag_start_pos = event.pos()
                        
                        # UX Enhancement: Set visual feedback for drag start
                        self._is_being_dragged = True
                        # Only change cursor in edit mode
                        current_mode = self._get_current_mode()
                        if current_mode in ["edit", None]:
                            self.setCursor(QCursor(Qt.CursorShape.ClosedHandCursor))
                        
                        event.accept()
                        return
                else:
                    # Click on line (not control point) = add new point
                    self._add_point(event.pos())
                    event.accept()
                    return
            
            # Not in edit mode, emit click signal for node navigation
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
        """Handle mouse release events with deferred expensive operations.
        
        Args:
            event: Mouse release event
        """
        if event.button() == Qt.MouseButton.LeftButton and self.dragging_control_point:
            self.dragging_control_point = False
            self._is_being_dragged = False
            
            # UX Enhancement: Now perform expensive operations that were deferred
            if self._pending_updates:
                # Re-enable expensive operations
                self.geometry.set_performance_mode(False)
                
                # Update shared points if this is a branching line (expensive operation)
                if self.geometry.is_branching:
                    self.geometry._update_shared_points()
                
                # Final bounds update after drag completion
                logger.debug(f"Drag completed for {self.target_node}, updating bounds")
                self._update_bounds()
                self.update()
                
                # Emit geometry changed signal
                self._emit_geometry_changed()
                
                self._pending_updates = False
            
            # Reset cursor only if in default mode
            current_mode = self._get_current_mode()
            if current_mode in ["default", None]:
                self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
            
            event.accept()
        else:
            super().mouseReleaseEvent(event)
    
    def hoverMoveEvent(self, event) -> None:
        """Handle hover move events with enhanced visual feedback.
        
        Args:
            event: Hover event
        """
        if self.edit_mode and not self._is_being_dragged:
            self._update_hover_cursor(event.pos())
            
            # UX Enhancement: Show snap preview for branch creation
            self._update_snap_preview(event.pos())
        
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
        """Update control point position during drag with optimized performance.
        
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
            
            # UX Enhancement: Defer expensive operations during drag
            if not self._is_being_dragged:
                self._is_being_dragged = True
                # Enable performance mode to skip expensive shared point updates
                self.geometry.set_performance_mode(True)
            
            # Mark that we need updates but don't do them during drag
            self._pending_updates = True
            
            # Only update scaled branches for immediate visual feedback
            self.geometry._update_scaled_branches()
            
            # Minimal update for real-time feedback
            self.update()
    
    def _update_hover_cursor(self, pos: QPointF) -> None:
        """Update cursor based on hover position with GIS-standard cursors.
        
        Args:
            pos: Mouse position
        """
        # Check current mode first
        current_mode = self._get_current_mode()
        
        # Only set item-specific cursors in default or edit modes
        if current_mode in ["default", "edit", None]:
            if self._test_control_point_hit(pos):
                # GIS standard: Open hand for draggable elements
                self.setCursor(QCursor(Qt.CursorShape.OpenHandCursor))
            else:
                # GIS standard: Pointing hand for clickable lines
                self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        # Otherwise, let the mode's cursor remain active
    
    def _get_current_mode(self) -> Optional[str]:
        """Get the current interaction mode from the adapter.
        
        Returns:
            Current mode string or None
        """
        scene = self.scene()
        if scene and hasattr(scene, 'views'):
            views = scene.views()
            if views:
                view = views[0]
                if hasattr(view, 'parent') and hasattr(view.parent(), 'graphics_adapter'):
                    adapter = view.parent().graphics_adapter
                    return getattr(adapter, 'current_mode', None)
        return None
    
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
        """Show enhanced context menu with GIS-standard operations.
        
        Args:
            pos: Position where right-click occurred
        """
        from PyQt6.QtWidgets import QMenu
        from PyQt6.QtGui import QAction, QIcon
        
        menu = QMenu()
        
        # GIS Enhancement: Add icons and keyboard shortcuts
        if self.geometry.is_branching:
            # MultiLineString - can create branches
            create_branch_action = QAction("🔀 Create Branch", menu)
            create_branch_action.setShortcut("B")
            create_branch_action.setStatusTip("Create a new branch from this point (B)")
            create_branch_action.triggered.connect(lambda: self._start_branch_creation(pos))
            menu.addAction(create_branch_action)
            
            # Add branch management options
            menu.addSeparator()
            
            delete_branch_action = QAction("🗑️ Delete Branch", menu)
            delete_branch_action.setShortcut("Del")
            delete_branch_action.setStatusTip("Delete the selected branch")
            delete_branch_action.setEnabled(len(self.geometry.branches) > 1)  # Can't delete if only one branch
            delete_branch_action.triggered.connect(lambda: self._delete_branch(pos))
            menu.addAction(delete_branch_action)
            
        else:
            # LineString - offer conversion option
            convert_action = QAction("🔄 Convert to Branching Line", menu)
            convert_action.setStatusTip("Convert this simple line to support branching")
            convert_action.triggered.connect(lambda: self._convert_to_branching_line())
            menu.addAction(convert_action)
            
            menu.addSeparator()
            
            # Show create branch action but disabled with explanation
            create_branch_action = QAction("🔀 Create Branch (convert first)", menu)
            create_branch_action.setEnabled(False)
            create_branch_action.setStatusTip("This simple line must be converted to support branching")
            menu.addAction(create_branch_action)
        
        # Common operations
        menu.addSeparator()
        
        add_point_action = QAction("➕ Add Point", menu)
        add_point_action.setStatusTip("Add a control point at this position")
        add_point_action.triggered.connect(lambda: self._add_point(pos))
        menu.addAction(add_point_action)
        
        # Check if right-click is on a control point
        hit_result = self._test_control_point_hit(pos)
        if hit_result:
            branch_idx, point_idx = hit_result
            branch = self.geometry.branches[branch_idx] if branch_idx < len(self.geometry.branches) else []
            
            # Only show delete option if branch has more than 2 points
            if len(branch) > 2:
                delete_point_action = QAction("🗑️ Delete Point", menu)
                delete_point_action.setShortcut("Shift+Click")
                delete_point_action.setStatusTip("Delete this control point (Shift+Click)")
                delete_point_action.triggered.connect(lambda: self._delete_control_point(branch_idx, point_idx))
                menu.addAction(delete_point_action)
        
        properties_action = QAction("⚙️ Properties", menu)
        properties_action.setStatusTip("Edit line properties and styling")
        menu.addAction(properties_action)
        
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

    def _update_snap_preview(self, pos: QPointF) -> None:
        """Update snap preview for potential branch creation points.
        
        Args:
            pos: Mouse position
        """
        # GIS Enhancement: Show potential snap points during hover
        if not self.edit_mode:
            return
            
        # Find nearest line segment for snapping
        min_distance = float('inf')
        snap_point = None
        
        for branch in self.geometry.branches:
            if len(branch) < 2:
                continue
                
            for i in range(len(branch) - 1):
                p1 = QPointF(branch[i][0], branch[i][1])
                p2 = QPointF(branch[i+1][0], branch[i+1][1])
                
                # Calculate closest point on line segment
                line_vec = p2 - p1
                point_vec = pos - p1
                
                if line_vec.manhattanLength() == 0:
                    continue
                    
                # Project point onto line (manual dot product for compatibility)
                dot_pv_lv = point_vec.x() * line_vec.x() + point_vec.y() * line_vec.y()
                dot_lv_lv = line_vec.x() * line_vec.x() + line_vec.y() * line_vec.y()
                
                if dot_lv_lv == 0:
                    continue
                    
                t = max(0, min(1, dot_pv_lv / dot_lv_lv))
                closest_point = p1 + t * line_vec
                
                distance = (pos - closest_point).manhattanLength()
                
                # GIS standard: 10 pixel snap tolerance
                if distance < 10 and distance < min_distance:
                    min_distance = distance
                    snap_point = closest_point
        
        # Update snap preview if we found a good snap point
        if snap_point != self._snap_preview:
            self._snap_preview = snap_point
            self.update()  # Trigger repaint to show/hide snap preview

    def set_highlighted(self, highlighted: bool) -> None:
        """Set highlight state for this line (GIS standard selection feedback).
        
        Args:
            highlighted: Whether the line should be highlighted
        """
        if self._is_highlighted != highlighted:
            self._is_highlighted = highlighted
            self.update()

    def set_preview_branch(self, start_point: QPointF, end_point: QPointF) -> None:
        """Set preview branch for branch creation mode.
        
        Args:
            start_point: Branch start coordinates
            end_point: Branch end coordinates  
        """
        self._preview_branch = (start_point, end_point)
        self.update()

    def _delete_branch(self, pos) -> None:
        """Delete a branch from the branching line.
        
        Args:
            pos: Position where the delete was requested
        """
        logger.info(f"Deleting branch from context menu at {pos}")
        
        if not self.geometry.is_branching:
            logger.warning(f"Cannot delete branch from non-branching line {self.target_node}")
            return
            
        # Find which branch is closest to the click position
        scene_pos = self.mapToScene(pos)
        branch_to_delete = self._find_nearest_branch(scene_pos)
        
        if branch_to_delete is None:
            logger.warning("Could not determine which branch to delete")
            return
            
        # Don't allow deleting the main branch (index 0)
        if branch_to_delete == 0:
            logger.warning("Cannot delete the main branch")
            return
            
        # Attempt to delete the branch
        if self.geometry.delete_branch(branch_to_delete):
            logger.info(f"Successfully deleted branch {branch_to_delete} from {self.target_node}")
            
            # Update visual representation
            self._update_bounds()
            self.update()
            
            # Emit geometry changed signal to update database
            self._emit_geometry_changed()
        else:
            logger.warning(f"Failed to delete branch {branch_to_delete}")

    def _add_point(self, pos) -> None:
        """Add a point to the line at the clicked position.
        
        Args:
            pos: Position where the point should be added
        """
        logger.info(f"Adding point from context menu at {pos}")
        
        # Convert position to scene coordinates, then to original coordinates
        scene_pos = self.mapToScene(pos)
        scene = self.scene()
        if not scene or not hasattr(scene, 'scene_to_original_coords'):
            logger.error("Cannot convert coordinates for point insertion")
            return
            
        original_coords = scene.scene_to_original_coords(scene_pos)
        new_point = (int(original_coords[0]), int(original_coords[1]))
        
        # Find the best insertion point
        insertion_info = self._find_insertion_point(scene_pos)
        
        if insertion_info is None:
            logger.warning("Could not determine where to insert the point")
            return
            
        branch_idx, insert_idx = insertion_info
        
        # Insert the point
        self.geometry.insert_point(branch_idx, insert_idx, new_point)
        
        logger.info(f"Successfully added point {new_point} to branch {branch_idx} at index {insert_idx}")
        
        # Update visual representation
        self._update_bounds()
        self.update()
        
        # Emit geometry changed signal to update database
        self._emit_geometry_changed()

    def _find_nearest_branch(self, scene_pos: QPointF) -> Optional[int]:
        """Find the branch closest to the given scene position.
        
        Args:
            scene_pos: Position in scene coordinates
            
        Returns:
            Index of the nearest branch, or None if not found
        """
        min_distance = float('inf')
        nearest_branch = None
        
        for branch_idx, branch in enumerate(self.geometry.scaled_branches):
            if len(branch) < 2:
                continue
                
            # Calculate distance to each segment in this branch
            for i in range(len(branch) - 1):
                p1 = QPointF(branch[i][0], branch[i][1])
                p2 = QPointF(branch[i+1][0], branch[i+1][1])
                
                # Find closest point on line segment
                line_vec = p2 - p1
                point_vec = scene_pos - p1
                
                if line_vec.manhattanLength() == 0:
                    continue
                    
                # Manual dot product calculation for compatibility
                dot_pv_lv = point_vec.x() * line_vec.x() + point_vec.y() * line_vec.y()
                dot_lv_lv = line_vec.x() * line_vec.x() + line_vec.y() * line_vec.y()
                
                if dot_lv_lv == 0:
                    continue
                    
                t = max(0, min(1, dot_pv_lv / dot_lv_lv))
                closest_point = p1 + t * line_vec
                
                distance = (scene_pos - closest_point).manhattanLength()
                
                if distance < min_distance:
                    min_distance = distance
                    nearest_branch = branch_idx
        
        # Only return a branch if it's reasonably close (within 20 pixels)
        return nearest_branch if min_distance < 20 else None

    def _find_insertion_point(self, scene_pos: QPointF) -> Optional[Tuple[int, int]]:
        """Find the best location to insert a new point.
        
        Args:
            scene_pos: Position in scene coordinates where point should be added
            
        Returns:
            Tuple of (branch_idx, insert_idx) or None if not found
        """
        min_distance = float('inf')
        best_insertion = None
        
        for branch_idx, branch in enumerate(self.geometry.scaled_branches):
            if len(branch) < 2:
                continue
                
            # Check each line segment in this branch
            for i in range(len(branch) - 1):
                p1 = QPointF(branch[i][0], branch[i][1])
                p2 = QPointF(branch[i+1][0], branch[i+1][1])
                
                # Find closest point on line segment
                line_vec = p2 - p1
                point_vec = scene_pos - p1
                
                if line_vec.manhattanLength() == 0:
                    continue
                    
                # Manual dot product calculation for compatibility
                dot_pv_lv = point_vec.x() * line_vec.x() + point_vec.y() * line_vec.y()
                dot_lv_lv = line_vec.x() * line_vec.x() + line_vec.y() * line_vec.y()
                
                if dot_lv_lv == 0:
                    continue
                    
                t = max(0, min(1, dot_pv_lv / dot_lv_lv))
                closest_point = p1 + t * line_vec
                
                distance = (scene_pos - closest_point).manhattanLength()
                
                if distance < min_distance:
                    min_distance = distance
                    # Insert after the first point of this segment
                    best_insertion = (branch_idx, i + 1)
        
        # Only return insertion point if it's reasonably close (within 20 pixels)
        return best_insertion if min_distance < 20 else None

    def _delete_control_point(self, branch_idx: int, point_idx: int) -> None:
        """Delete a control point from the line.
        
        Args:
            branch_idx: Index of the branch containing the point
            point_idx: Index of the point within the branch
        """
        logger.info(f"Deleting control point at branch {branch_idx}, point {point_idx}")
        
        # Safety checks
        if branch_idx >= len(self.geometry.branches):
            logger.warning(f"Invalid branch index {branch_idx}")
            return
            
        branch = self.geometry.branches[branch_idx]
        if point_idx >= len(branch):
            logger.warning(f"Invalid point index {point_idx}")
            return
            
        # Don't allow deletion if it would make the branch too short
        if len(branch) <= 2:
            logger.warning("Cannot delete point - would make branch too short (need at least 2 points)")
            return
            
        # For branching lines, check if this is a shared point
        if self.geometry.is_branching:
            point = branch[point_idx]
            point_key = (int(point[0]), int(point[1]))
            
            # If it's a shared point, warn user but allow deletion
            if point_key in self.geometry._shared_points:
                locations = self.geometry._shared_points[point_key]
                if len(locations) > 1:
                    logger.info(f"Deleting shared point used by {len(locations)} branches")
        
        # Attempt to delete the point
        if self.geometry.delete_point(branch_idx, point_idx):
            logger.info(f"Successfully deleted point from branch {branch_idx}")
            
            # Update visual representation
            self._update_bounds()
            self.update()
            
            # Emit geometry changed signal to update database
            self._emit_geometry_changed()
        else:
            logger.warning(f"Failed to delete point from branch {branch_idx}")