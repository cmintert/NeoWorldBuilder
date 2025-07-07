from typing import Tuple, Optional

from PyQt6.QtCore import Qt, pyqtSignal, QPoint
from PyQt6.QtGui import (
    QMouseEvent,
    QWheelEvent,
    QKeyEvent,
    QCursor,
    QPainter,
    QPen,
    QColor,
    QBrush,
    QPixmap,
    QIcon,
    QFont,
)
from PyQt6.QtWidgets import QLabel
from structlog import get_logger

from .utils.coordinate_transformer import CoordinateTransformer

logger = get_logger(__name__)


class MapViewport(QLabel):
    """Handles map display, panning, zooming, and coordinate tracking.

    Separated from feature management and drawing_decap logic for cleaner architecture.
    """

    # Viewport signals
    zoom_requested = pyqtSignal(float)
    coordinates_changed = pyqtSignal(int, int)  # Original coordinates
    click_at_coordinates = pyqtSignal(int, int)  # For placement operations

    def __init__(self, parent=None, config=None):
        """Initialize the map viewport.

        Args:
            parent: Parent widget (typically MapTab)
            config: Configuration object
        """
        super().__init__(parent)
        self.config = config
        self.parent_map_tab = parent

        # Viewport state
        self.is_panning = False
        self.last_mouse_pos = QPoint()

        # Store current mouse position for branch creation feedback
        self.current_mouse_pos = QPoint(0, 0)

        # Flag to track if we're in branch creation mode
        self.is_branch_creation_active = False

        # Coordinate tracking
        self.coordinate_label = QLabel(self)
        self.coordinate_label.setStyleSheet(
            "QLabel { background-color: rgba(0, 0, 0, 150); color: white; "
            "padding: 5px; border-radius: 3px; }"
        )
        self.coordinate_label.hide()

        self._setup_viewport()

    def _setup_viewport(self) -> None:
        """Setup viewport properties."""
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMouseTracking(True)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Handle mouse press for panning and coordinate clicks."""
        if not self.pixmap():
            return

        coordinates = self._get_original_coordinates(event.pos())
        if coordinates is None:
            return

        original_x, original_y = coordinates

        # Emit click coordinates for other components to handle
        if event.button() == Qt.MouseButton.LeftButton:
            self.click_at_coordinates.emit(original_x, original_y)

            # Start panning if no other mode is active
            if not self._is_in_special_mode():
                self.is_panning = True
                self.last_mouse_pos = event.pos()
                self.setCursor(QCursor(Qt.CursorShape.ClosedHandCursor))

    def paintEvent(self, event):
        """Handle paint events for drawing temporary elements."""
        super().paintEvent(event)

        # Draw temporary line if parent is in line drawing mode
        if self.parent_map_tab and hasattr(self.parent_map_tab, "drawing_manager"):
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)

            if self.parent_map_tab.drawing_manager.is_drawing_line:
                self.parent_map_tab.drawing_manager.draw_temporary_line(painter)
            elif self.parent_map_tab.drawing_manager.is_drawing_branching_line:
                self.parent_map_tab.drawing_manager.draw_temporary_branching_line(
                    painter
                )
            # Branch creation is now drawn by the line container to ensure proper z-order

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """Handle mouse release to stop panning."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_panning = False
            if not self._is_in_special_mode():
                self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """Handle mouse movement for panning and coordinate updates."""
        if not self.pixmap():
            return

        # Always store current mouse position for branch creation feedback
        self.current_mouse_pos = event.pos()

        # Check if branch creation mode is active
        branch_creation_active = getattr(
            self.parent_map_tab, "branch_creation_mode", False
        )
        if branch_creation_active != self.is_branch_creation_active:
            # Mode has changed - log it and update our flag
            logger.debug(
                f"Branch creation mode changed: {self.is_branch_creation_active} -> {branch_creation_active}"
            )
            self.is_branch_creation_active = branch_creation_active

        # Handle panning
        if self.is_panning:
            delta = event.pos() - self.last_mouse_pos
            self.last_mouse_pos = event.pos()

            # Delegate panning to parent's scroll area
            if self.parent_map_tab and hasattr(self.parent_map_tab, "scroll_area"):
                h_bar = self.parent_map_tab.scroll_area.horizontalScrollBar()
                v_bar = self.parent_map_tab.scroll_area.verticalScrollBar()
                h_bar.setValue(h_bar.value() - delta.x())
                v_bar.setValue(v_bar.value() - delta.y())
        else:
            # Update coordinate display
            coordinates = self._get_original_coordinates(event.pos())
            if coordinates is not None:
                original_x, original_y = coordinates
                self.coordinates_changed.emit(original_x, original_y)
                self.coordinate_label.setText(f"X: {original_x}, Y: {original_y}")
                self.coordinate_label.move(event.pos().x() + 15, event.pos().y() + 15)
                self.coordinate_label.show()
            else:
                self.coordinate_label.hide()

        self.update()  # Trigger repaint for temporary drawing
        
        # Update the target line container if in branch creation mode
        if branch_creation_active and self.parent_map_tab:
            target = getattr(self.parent_map_tab.mode_manager, "_branch_creation_target", None)
            # TODO: Migrate branch creation preview to graphics mode
            if target:
                logger.debug("Branch creation preview not yet implemented for graphics mode")

    def wheelEvent(self, event: QWheelEvent) -> None:
        """Handle mouse wheel for zooming."""
        pass

        # Accept the event to prevent it from being propagated
        event.accept()

        delta = event.angleDelta().y()

        # Check if Ctrl is held for fine zoom control
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            # Fine zoom: approximately 5% per wheel notch
            zoom_factor = 1.0 + (delta / 2400.0)
        else:
            # Regular zoom: approximately 20% per wheel notch
            zoom_factor = 1.0 + (delta / 600.0)

        pass
        self.zoom_requested.emit(zoom_factor)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Handle key press events."""
        logger.info(f"MapViewport received key press: {event.key()}")

        # Delegate key handling to parent for mode-specific behavior
        if self.parent_map_tab:
            logger.info(f"Delegating key press to parent_map_tab")
            self.parent_map_tab.handle_viewport_key_press(event)
        else:
            logger.warning("No parent_map_tab to delegate key press to")
            super().keyPressEvent(event)

    def _get_original_coordinates(
        self, widget_pos: QPoint
    ) -> Optional[Tuple[int, int]]:
        """Convert widget position to original image coordinates.

        Args:
            widget_pos: Position in widget coordinates

        Returns:
            Tuple of (original_x, original_y) or None if outside image
        """
        pixmap = self.pixmap()
        if not pixmap or not self.parent_map_tab:
            return None

        # Get original pixmap and current scale for transformation
        original_pixmap = None
        current_scale = 1.0

        if self._has_image_manager_with_original():
            original_pixmap = self.parent_map_tab.image_manager.original_pixmap
        else:
            current_scale = getattr(self.parent_map_tab, "current_scale", 1.0)

        # Use coordinate transformer utility
        return CoordinateTransformer.widget_to_original_coordinates(
            widget_pos,
            pixmap,
            self.width(),
            self.height(),
            original_pixmap,
            current_scale,
        )

    def _has_image_manager_with_original(self) -> bool:
        """Check if image manager with original pixmap is available.

        Returns:
            True if image manager with original pixmap exists, False otherwise
        """
        return (
            hasattr(self.parent_map_tab, "image_manager")
            and self.parent_map_tab.image_manager.original_pixmap
        )

    def _is_in_special_mode(self) -> bool:
        """Check if viewport is in a special interaction mode."""
        if not self.parent_map_tab:
            return False

        return (
            getattr(self.parent_map_tab, "pin_placement_active", False)
            or getattr(self.parent_map_tab, "line_drawing_active", False)
            or getattr(self.parent_map_tab, "branching_line_drawing_active", False)
            or getattr(self.parent_map_tab, "edit_mode_active", False)
            or getattr(self.parent_map_tab, "branch_creation_mode", False)
        )

    def _draw_branch_creation_feedback(self, painter: QPainter) -> None:
        """Draw visual feedback for branch creation mode."""
        if not hasattr(self.parent_map_tab, "_branch_creation_start_point"):
            logger.warning("No _branch_creation_start_point found")
            return

        start_point = self.parent_map_tab._branch_creation_start_point
        logger.debug(f"Branch creation start point: {start_point}")

        # Convert start point from original coordinates to widget coordinates
        pixmap = self.pixmap()
        if not pixmap:
            logger.warning("No pixmap available for branch creation drawing")
            return

        # Get original pixmap and current scale for transformation
        original_pixmap = None
        current_scale = self.parent_map_tab.current_scale
        logger.debug(f"Current scale: {current_scale}")

        if self._has_image_manager_with_original():
            original_pixmap = self.parent_map_tab.image_manager.original_pixmap
            logger.debug(
                f"Original pixmap size: {original_pixmap.width()}x{original_pixmap.height()}"
            )
        else:
            logger.debug("No original pixmap available")

        # Convert start point to widget coordinates using coordinate transformer
        start_widget_pos = CoordinateTransformer.original_to_widget_coordinates(
            start_point[0],
            start_point[1],
            pixmap,
            self.width(),
            self.height(),
            original_pixmap,
            current_scale,
        )

        if start_widget_pos is None:
            logger.warning("Failed to convert start point to widget coordinates")
            return

        start_widget_x, start_widget_y = start_widget_pos
        logger.debug(
            f"Start point widget coordinates: ({start_widget_x}, {start_widget_y})"
        )

        # Use stored mouse position (already in widget coordinates)
        mouse_pos = self.current_mouse_pos
        logger.debug(f"Current mouse position: ({mouse_pos.x()}, {mouse_pos.y()})")

        # Safety check: if mouse position is not valid, use center of widget
        if mouse_pos.isNull():
            logger.warning("Mouse position is null, using widget center")
            mouse_pos = QPoint(self.width() // 2, self.height() // 2)

        # Set up pen for temporary branch line
        pen = QPen(QColor("#FF8800"))  # Orange color for branch creation
        pen.setWidth(3)
        pen.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(pen)

        # Draw temporary line from start point to current mouse position (both in widget coordinates)
        painter.drawLine(
            int(start_widget_x), int(start_widget_y), mouse_pos.x(), mouse_pos.y()
        )
        logger.debug(
            f"Drew line from ({int(start_widget_x)}, {int(start_widget_y)}) to ({mouse_pos.x()}, {mouse_pos.y()})"
        )

        # Draw start point indicator
        painter.setBrush(QBrush(QColor("#FF8800")))
        painter.setPen(QPen(QColor("#FFFFFF"), 2))
        painter.drawEllipse(int(start_widget_x - 6), int(start_widget_y - 6), 12, 12)
        logger.debug("Drew start point indicator")

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
        logger.debug(f"Setting cursor for mode: {mode}")
        
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
        logger.debug(f"Cursor set for mode: {mode}")
