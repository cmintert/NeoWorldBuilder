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
        """Handle paint events for drawing_decap temporary elements."""
        super().paintEvent(event)

        # Draw temporary line if parent is in line drawing_decap mode
        if self.parent_map_tab and hasattr(self.parent_map_tab, "drawing_manager"):
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)

            if self.parent_map_tab.drawing_manager.is_drawing_line:
                self.parent_map_tab.drawing_manager.draw_temporary_line(painter)
            elif self.parent_map_tab.drawing_manager.is_drawing_branching_line:
                self.parent_map_tab.drawing_manager.draw_temporary_branching_line(
                    painter
                )
            elif getattr(self.parent_map_tab, "branch_creation_mode", False):
                logger.debug(
                    f"Drawing branch creation feedback, mouse pos: {self.current_mouse_pos.x()}, {self.current_mouse_pos.y()}"
                )
                self._draw_branch_creation_feedback(painter)

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

        self.update()  # Trigger repaint for branch creation feedback

    def wheelEvent(self, event: QWheelEvent) -> None:
        """Handle mouse wheel for zooming."""
        print(f"MapViewport wheelEvent called with delta: {event.angleDelta().y()}")

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

        print(f"Emitting zoom_requested with factor: {zoom_factor}")
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

    def set_cursor_for_mode(self, mode: str) -> None:
        """Set cursor based on current interaction mode.

        Args:
            mode: One of 'default', 'crosshair', 'pointing'
        """
        cursor_map = {
            "default": Qt.CursorShape.ArrowCursor,
            "crosshair": Qt.CursorShape.CrossCursor,
            "pointing": Qt.CursorShape.PointingHandCursor,
        }

        cursor = cursor_map.get(mode, Qt.CursorShape.ArrowCursor)
        self.setCursor(QCursor(cursor))
