from typing import Dict, List, Tuple, Optional
from PyQt6.QtCore import Qt, pyqtSignal, QPoint
from PyQt6.QtGui import (
    QMouseEvent,
    QWheelEvent,
    QKeyEvent,
    QCursor,
    QPainter,
    QPen,
    QColor,
)
from PyQt6.QtWidgets import QLabel, QWidget
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
            if self.parent_map_tab.drawing_manager.is_drawing_line:
                painter = QPainter(self)
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                self.parent_map_tab.drawing_manager.draw_temporary_line(painter)
            elif self.parent_map_tab.drawing_manager.is_drawing_branching_line:
                painter = QPainter(self)
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                self.parent_map_tab.drawing_manager.draw_temporary_branching_line(
                    painter
                )

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

    def wheelEvent(self, event: QWheelEvent) -> None:
        """Handle mouse wheel for zooming."""
        delta = event.angleDelta().y()
        zoom_factor = 1.0 + (delta / 1200.0)
        self.zoom_requested.emit(zoom_factor)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Handle key press events."""
        # Delegate key handling to parent for mode-specific behavior
        if self.parent_map_tab:
            self.parent_map_tab.handle_viewport_key_press(event)
        else:
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
            widget_pos, pixmap, self.width(), self.height(),
            original_pixmap, current_scale
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
        )

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
