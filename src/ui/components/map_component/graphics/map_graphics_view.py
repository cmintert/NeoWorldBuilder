"""Map graphics view component for QGraphicsView-based map rendering."""

from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal, QPointF, QEvent
from PyQt6.QtGui import QMouseEvent, QWheelEvent, QPainter, QKeyEvent, QPen, QColor, QCursor, QPixmap, QBrush, QFont
from PyQt6.QtWidgets import QGraphicsView, QGraphicsScene
from structlog import get_logger

logger = get_logger(__name__)


class MapGraphicsView(QGraphicsView):
    """Graphics view for map display with pan, zoom, and coordinate tracking.
    
    This replaces the QLabel-based MapViewport with a proper QGraphicsView
    implementation that supports overlapping interactive elements.
    """
    
    # View signals - matching existing MapViewport interface
    zoom_requested = pyqtSignal(float)
    coordinates_changed = pyqtSignal(int, int)  # Original coordinates
    click_at_coordinates = pyqtSignal(int, int)  # For placement operations
    key_press_event = pyqtSignal(QKeyEvent)  # For key handling
    
    def __init__(self, parent=None, config=None):
        """Initialize the map graphics view.
        
        Args:
            parent: Parent widget (typically MapTab)
            config: Configuration object
        """
        super().__init__(parent)
        self.config = config
        
        # View configuration
        self.setDragMode(QGraphicsView.DragMode.NoDrag)  # We'll handle panning manually
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.SmartViewportUpdate)
        
        # Enable mouse tracking for coordinate updates
        self.setMouseTracking(True)
        
        # Enable keyboard focus to receive key events
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        
        # Viewport state
        self.is_panning = False
        self.last_mouse_pos = QPointF()
        self.current_zoom_level = 1.0
        
        # Temporary line drawing support
        self._drawing_manager = None  # Will be set by adapter
        
        # Configure scrollbars
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        logger.info("MapGraphicsView initialized")
    
    def set_scene(self, scene: QGraphicsScene) -> None:
        """Set the graphics scene for this view.
        
        Args:
            scene: The MapGraphicsScene to display
        """
        self.setScene(scene)
        # Fit the scene in view initially
        self.fitInView(scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
        
    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Handle mouse press for panning and feature interaction.
        
        Args:
            event: Mouse press event
        """
        if event.button() == Qt.MouseButton.MiddleButton:
            # Start panning
            self.is_panning = True
            self.last_mouse_pos = self.mapToScene(event.pos())
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
        elif event.button() == Qt.MouseButton.LeftButton:
            # Convert to scene coordinates for placement operations
            scene_pos = self.mapToScene(event.pos())
            if self.scene():
                # Emit click coordinates in original image space
                orig_x, orig_y = self.scene().scene_to_original_coords(scene_pos)
                self.click_at_coordinates.emit(orig_x, orig_y)
            
            # Let QGraphicsView handle the event for item interaction
            super().mousePressEvent(event)
        else:
            super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """Handle mouse move for panning and coordinate tracking.
        
        Args:
            event: Mouse move event
        """
        scene_pos = self.mapToScene(event.pos())
        
        # Update coordinate display
        if self.scene():
            orig_x, orig_y = self.scene().scene_to_original_coords(scene_pos)
            self.coordinates_changed.emit(orig_x, orig_y)
        
        # Handle panning
        if self.is_panning:
            delta = scene_pos - self.last_mouse_pos
            # Pan by scrolling
            h_bar = self.horizontalScrollBar()
            v_bar = self.verticalScrollBar()
            h_bar.setValue(int(h_bar.value() - delta.x()))
            v_bar.setValue(int(v_bar.value() - delta.y()))
            self.last_mouse_pos = self.mapToScene(event.pos())
        else:
            # Let QGraphicsView handle normal mouse movement
            super().mouseMoveEvent(event)
    
    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """Handle mouse release to stop panning.
        
        Args:
            event: Mouse release event
        """
        if event.button() == Qt.MouseButton.MiddleButton and self.is_panning:
            self.is_panning = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
            event.accept()
        else:
            super().mouseReleaseEvent(event)
    
    def wheelEvent(self, event: QWheelEvent) -> None:
        """Handle mouse wheel for zooming with zoom-to-cursor functionality.
        
        Args:
            event: Wheel event
        """
        # Calculate zoom factor based on wheel delta
        delta = event.angleDelta().y()
        
        # Check if Ctrl is held for fine zoom control
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            # Fine zoom: approximately 5% per wheel notch
            zoom_factor = 1.0 + (delta / 2400.0)
        else:
            # Regular zoom: approximately 20% per wheel notch  
            zoom_factor = 1.0 + (delta / 600.0)
        
        # Zoom-to-cursor implementation
        mouse_pos = event.position().toPoint()
        target_scene_pos = self.mapToScene(mouse_pos)
        
        # Apply the zoom transformation
        self.scale(zoom_factor, zoom_factor)
        self.current_zoom_level *= zoom_factor
        
        # Calculate where the target point is now after zoom
        current_target_in_view = self.mapFromScene(target_scene_pos)
        
        # Calculate the difference in view coordinates
        delta_view = mouse_pos - current_target_in_view
        
        # Apply translation using centerOn to correctly position the scene
        current_center = self.mapToScene(self.rect().center())
        
        # Convert the view delta to scene delta by scaling with the current zoom
        delta_scene_x = delta_view.x() / zoom_factor
        delta_scene_y = delta_view.y() / zoom_factor
        
        # Calculate and apply the new center position
        new_center_x = current_center.x() - delta_scene_x
        new_center_y = current_center.y() - delta_scene_y
        self.centerOn(new_center_x, new_center_y)
        
        # Emit zoom signal for other components that need to know about zoom changes
        self.zoom_requested.emit(self.current_zoom_level)
        
        event.accept()
    
    def fit_image_in_view(self) -> None:
        """Fit the entire map image in the view."""
        if self.scene():
            self.fitInView(self.scene().sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
            self.current_zoom_level = 1.0
            self.zoom_requested.emit(self.current_zoom_level)
    
    def center_on_coordinates(self, x: int, y: int) -> None:
        """Center the view on specific original image coordinates.
        
        Args:
            x: X coordinate in original image space
            y: Y coordinate in original image space
        """
        if self.scene():
            scene_point = self.scene().original_to_scene_coords(x, y)
            self.centerOn(scene_point)
    
    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Handle key press events and forward to parent.
        
        Args:
            event: Key press event
        """
        logger.debug(f"Graphics view received key press: {event.key()}")
        
        # Emit signal for parent to handle
        self.key_press_event.emit(event)
        
        # Also call parent handler
        super().keyPressEvent(event)
    
    def set_drawing_manager(self, drawing_manager) -> None:
        """Set the drawing manager for temporary line preview.
        
        Args:
            drawing_manager: Drawing manager instance
        """
        self._drawing_manager = drawing_manager
        logger.debug("Drawing manager set for graphics view")
    
    def paintEvent(self, event) -> None:
        """Override paint event to draw temporary lines.
        
        Args:
            event: Paint event
        """
        # Call parent paint event first
        super().paintEvent(event)
        
        # Draw temporary line if drawing manager is available and active
        if self._drawing_manager and hasattr(self._drawing_manager, 'is_drawing_line'):
            if self._drawing_manager.is_drawing_line:
                logger.debug("Drawing temporary line - regular line mode")
                self._draw_temporary_line()
            elif hasattr(self._drawing_manager, 'is_drawing_branching_line') and self._drawing_manager.is_drawing_branching_line:
                logger.debug("Drawing temporary line - branching line mode")
                self._draw_temporary_line()
    
    def _draw_temporary_line(self) -> None:
        """Draw the temporary line preview on the viewport."""
        if not self._drawing_manager:
            return
            
        # Get temporary points from drawing manager
        temp_points = []
        if self._drawing_manager.is_drawing_line:
            temp_points = getattr(self._drawing_manager, 'current_line_points', [])
        elif hasattr(self._drawing_manager, 'is_drawing_branching_line') and self._drawing_manager.is_drawing_branching_line:
            # For branching lines, get all branches and flatten them
            current_branches = getattr(self._drawing_manager, 'current_branches', [])
            for branch in current_branches:
                temp_points.extend(branch)
        
        if len(temp_points) < 1:
            logger.debug(f"No points for preview: {len(temp_points)}")
            return
        
        logger.debug(f"Drawing temporary line with {len(temp_points)} points: {temp_points[:3]}...")
        
        # Create painter for overlay
        painter = QPainter(self.viewport())
        
        # Set up blue dashed pen (matching original implementation)
        pen = QPen(QColor("#3388FF"), 2, Qt.PenStyle.DashLine)
        painter.setPen(pen)
        
        # Convert points from original coordinates to view coordinates
        view_points = []
        for point in temp_points:
            if self.scene():
                # Convert original coords to scene coords, then to view coords
                scene_point = self.scene().original_to_scene_coords(point[0], point[1])
                view_point = self.mapFromScene(scene_point)
                view_points.append(view_point)
        
        # Draw line segments (only if we have 2 or more points)
        if len(view_points) >= 2:
            for i in range(len(view_points) - 1):
                painter.drawLine(view_points[i], view_points[i + 1])
        
        # Draw point indicators
        if len(view_points) >= 1:
            if len(view_points) == 1:
                # Single point - green circle (start point)
                painter.setBrush(QColor(0, 255, 0, 180))  # Semi-transparent green
                painter.setPen(QPen(QColor(0, 150, 0), 2))
                painter.drawEllipse(view_points[0], 8, 8)
            else:
                # Start point - green circle
                painter.setBrush(QColor(0, 255, 0, 180))  # Semi-transparent green
                painter.setPen(QPen(QColor(0, 150, 0), 2))
                painter.drawEllipse(view_points[0], 8, 8)
                
                # End point - red circle (different from start)
                if len(view_points) >= 2 and view_points[-1] != view_points[0]:
                    painter.setBrush(QColor(255, 0, 0, 180))  # Semi-transparent red
                    painter.setPen(QPen(QColor(150, 0, 0), 2))
                    painter.drawEllipse(view_points[-1], 8, 8)
                
                # Intermediate points - small blue circles
                if len(view_points) > 2:
                    painter.setBrush(QColor(0, 0, 255, 120))  # Semi-transparent blue
                    painter.setPen(QPen(QColor(0, 0, 150), 1))
                    for point in view_points[1:-1]:
                        painter.drawEllipse(point, 4, 4)
        
        painter.end()
        logger.debug(f"Drew temporary line with {len(view_points)} points (start/end indicators included)")
    

    def set_cursor_for_mode(self, mode: str) -> None:
        """Set cursor based on current interaction mode using Qt built-in cursors.
        
        Uses professional GIS/CAD standard cursors:
        - CrossCursor for all precision operations (placement, drawing)
        - ArrowCursor for selection mode
        - Specialized cursors for specific interactions
        
        Args:
            mode: One of 'default', 'pin_placement', 'line_drawing', 
                  'branching_line_drawing', 'edit', 'crosshair', 'pointing'
        """
        logger.info(f"MapGraphicsView: Setting cursor for mode: {mode}")
        
        # Map modes to appropriate Qt built-in cursors
        cursor_map = {
            # Precision operations use crosshair (GIS/CAD standard)
            "pin_placement": Qt.CursorShape.CrossCursor,
            "line_drawing": Qt.CursorShape.CrossCursor,
            "branching_line_drawing": Qt.CursorShape.CrossCursor,
            
            # Edit mode uses standard arrow for selection
            "edit": Qt.CursorShape.ArrowCursor,
            
            # Specialized cursors
            "crosshair": Qt.CursorShape.CrossCursor,
            "pointing": Qt.CursorShape.PointingHandCursor,
            "default": Qt.CursorShape.ArrowCursor,
            
            # Additional interaction states
            "move_point": Qt.CursorShape.SizeAllCursor,  # When hovering over draggable points
            "panning": Qt.CursorShape.ClosedHandCursor,  # When panning the map
            "forbidden": Qt.CursorShape.ForbiddenCursor,  # Invalid operations
        }
        
        cursor_shape = cursor_map.get(mode, Qt.CursorShape.ArrowCursor)
        cursor = QCursor(cursor_shape)
        
        self.setCursor(cursor)
        logger.info(f"MapGraphicsView: Set Qt built-in cursor {cursor_shape} for mode: {mode}")