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
        """Handle mouse wheel for zooming.
        
        Args:
            event: Wheel event
        """
        # Calculate zoom factor
        zoom_in_factor = 1.15
        zoom_out_factor = 1.0 / zoom_in_factor
        
        # Get the current transformation matrix
        old_pos = self.mapToScene(event.position().toPoint())
        
        # Apply zoom
        if event.angleDelta().y() > 0:
            zoom_factor = zoom_in_factor
        else:
            zoom_factor = zoom_out_factor
        
        self.scale(zoom_factor, zoom_factor)
        self.current_zoom_level *= zoom_factor
        
        # Get the new position and adjust to keep point under cursor
        new_pos = self.mapToScene(event.position().toPoint())
        delta = new_pos - old_pos
        self.translate(delta.x(), delta.y())
        
        # Emit zoom signal
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
    
    def _create_professional_cursor(self, cursor_type: str) -> QCursor:
        """Create a professional GIS/CAD-style cursor with precise interaction point.
        
        Professional cursor design principles:
        - Small size (20x20) for minimal view obstruction
        - Precise crosshair for exact interaction point
        - High contrast black/white for visibility on any background
        - Clean geometric tool icons matching GIS standards
        - Hotspot at exact interaction point (crosshair center)
        
        Args:
            cursor_type: Type of cursor ('pin', 'line', 'branch', 'edit')
            
        Returns:
            QCursor with professional GIS-style design
        """
        size = 20  # Professional standard size
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Calculate center point for crosshair
        center_x, center_y = size // 2, size // 2
        crosshair_len = 6  # Length of crosshair arms
        
        # Draw precise crosshair (ALWAYS present for interaction point)
        # Black outline for visibility on light backgrounds
        painter.setPen(QPen(QColor(0, 0, 0), 2))
        painter.drawLine(center_x - crosshair_len, center_y, center_x + crosshair_len, center_y)
        painter.drawLine(center_x, center_y - crosshair_len, center_x, center_y + crosshair_len)
        
        # White inner lines for visibility on dark backgrounds
        painter.setPen(QPen(QColor(255, 255, 255), 1))
        painter.drawLine(center_x - crosshair_len, center_y, center_x + crosshair_len, center_y)
        painter.drawLine(center_x, center_y - crosshair_len, center_x, center_y + crosshair_len)
        
        # Add mode-specific tool indicator (offset from crosshair)
        icon_x, icon_y = center_x + 8, center_y - 8  # Top-right offset
        icon_size = 6
        
        if cursor_type == "pin":
            # Pin placement: Small location marker
            painter.setPen(QPen(QColor(0, 0, 0), 2))
            painter.setBrush(QBrush(QColor(255, 255, 255)))
            painter.drawEllipse(icon_x - 2, icon_y - 2, 4, 4)
            painter.drawLine(icon_x, icon_y + 2, icon_x, icon_y + 5)
            
        elif cursor_type == "line":
            # Line drawing: Simple line segment
            painter.setPen(QPen(QColor(0, 0, 0), 2))
            painter.drawLine(icon_x - 3, icon_y + 1, icon_x + 3, icon_y - 1)
            painter.setPen(QPen(QColor(255, 255, 255), 1))
            painter.drawLine(icon_x - 3, icon_y + 1, icon_x + 3, icon_y - 1)
            
        elif cursor_type == "branch":
            # Branching line: Y-shaped fork
            painter.setPen(QPen(QColor(0, 0, 0), 2))
            painter.drawLine(icon_x, icon_y + 2, icon_x, icon_y)      # Main stem
            painter.drawLine(icon_x, icon_y, icon_x - 2, icon_y - 2)  # Left branch
            painter.drawLine(icon_x, icon_y, icon_x + 2, icon_y - 2)  # Right branch
            painter.setPen(QPen(QColor(255, 255, 255), 1))
            painter.drawLine(icon_x, icon_y + 2, icon_x, icon_y)
            painter.drawLine(icon_x, icon_y, icon_x - 2, icon_y - 2)
            painter.drawLine(icon_x, icon_y, icon_x + 2, icon_y - 2)
            
        elif cursor_type == "edit":
            # Edit mode: Selection handles
            painter.setPen(QPen(QColor(0, 0, 0), 1))
            painter.setBrush(QBrush(QColor(255, 255, 255)))
            painter.drawRect(icon_x - 2, icon_y - 2, 2, 2)
            painter.drawRect(icon_x + 1, icon_y - 2, 2, 2)
            painter.drawRect(icon_x - 2, icon_y + 1, 2, 2)
            painter.drawRect(icon_x + 1, icon_y + 1, 2, 2)
        
        painter.end()
        
        # Hotspot at crosshair center for precise interaction
        return QCursor(pixmap, center_x, center_y)

    def set_cursor_for_mode(self, mode: str) -> None:
        """Set cursor based on current interaction mode with custom icons.

        Args:
            mode: One of 'default', 'pin_placement', 'line_drawing', 
                  'branching_line_drawing', 'edit', 'crosshair', 'pointing'
        """
        logger.info(f"MapGraphicsView: Setting professional cursor for mode: {mode}")
        
        # Professional GIS/CAD-style cursors
        if mode == "pin_placement":
            cursor = self._create_professional_cursor("pin")
            logger.info("Created professional pin placement cursor with crosshair + location marker")
            
        elif mode == "line_drawing":
            cursor = self._create_professional_cursor("line")
            logger.info("Created professional line drawing cursor with crosshair + line indicator")
            
        elif mode == "branching_line_drawing":
            cursor = self._create_professional_cursor("branch")
            logger.info("Created professional branching line cursor with crosshair + fork indicator")
            
        elif mode == "edit":
            cursor = self._create_professional_cursor("edit")
            logger.info("Created professional edit cursor with crosshair + selection handles")
        elif mode == "crosshair":
            # Use crosshair for precision
            cursor = QCursor(Qt.CursorShape.CrossCursor)
        elif mode == "pointing":
            # Use pointing hand
            cursor = QCursor(Qt.CursorShape.PointingHandCursor)
        elif mode == "default":
            # Default arrow
            cursor = QCursor(Qt.CursorShape.ArrowCursor)
        else:
            # Fallback to default
            logger.warning(f"Unknown cursor mode: {mode}, using default")
            cursor = QCursor(Qt.CursorShape.ArrowCursor)
        
        self.setCursor(cursor)
        logger.info(f"MapGraphicsView: Cursor successfully set for mode: {mode}, cursor type: {type(cursor)}")