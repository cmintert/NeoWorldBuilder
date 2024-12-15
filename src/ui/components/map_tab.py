from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal, QPoint, QTimer
from PyQt6.QtGui import (
    QPixmap,
    QTransform,
    QMouseEvent,
    QCursor,
    QWheelEvent,
    QKeyEvent,
)
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QScrollArea,
    QSlider,
    QHBoxLayout,
    QPushButton,
    QFileDialog,
)

from ui.dialogs import PinPlacementDialog


class PannableLabel(QLabel):
    """Custom QLabel that supports panning with click and drag."""

    zoom_requested = pyqtSignal(float)  # Signal for zoom requests
    pin_placed = pyqtSignal(int, int)  # Signal for pin placement

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.is_panning = False
        self.last_mouse_pos = QPoint()
        self.pin_placement_active = False

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """
        Handle mouse press events on the graphical interface.

        This method responds to mouse press actions, either initiating a pin placement
        operation or enabling the panning mode on the widget, depending on the state
        of the `pin_placement_active` flag and the type of mouse button clicked. Pin
        placement emits the pin's position, while panning starts by capturing the mouse
        position and changing the cursor shape to indicate activity.

        Parameters:
            event (QMouseEvent): The mouse event containing information about the
            mouse interaction, such as the button pressed and its position.

        Returns:
            None
        """
        if self.pin_placement_active and event.button() == Qt.MouseButton.LeftButton:
            # Pin placement takes precedence when active
            pos = event.pos()
            self.pin_placed.emit(pos.x(), pos.y())
        elif (
            not self.pin_placement_active
            and event.button() == Qt.MouseButton.LeftButton
        ):
            # Original panning behavior
            self.is_panning = True
            self.last_mouse_pos = event.pos()
            self.setCursor(QCursor(Qt.CursorShape.ClosedHandCursor))

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Handle key press events."""
        if event.key() == Qt.Key.Key_Escape and self.pin_placement_active:
            self.pin_placement_active = False
            self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
        else:
            super().keyPressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """Handle mouse release events to stop panning."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_panning = False
            self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """Handle mouse move events to perform panning."""
        if self.is_panning:
            delta = event.pos() - self.last_mouse_pos
            self.last_mouse_pos = event.pos()

            scroll_area = self.parent().parent()
            if isinstance(scroll_area, QScrollArea):
                h_bar = scroll_area.horizontalScrollBar()
                v_bar = scroll_area.verticalScrollBar()
                h_bar.setValue(h_bar.value() - delta.x())
                v_bar.setValue(v_bar.value() - delta.y())

    def wheelEvent(self, event: QWheelEvent) -> None:
        """Handle mouse wheel events for zooming."""
        # Get the number of degrees rotated (usually 120 or -120)
        delta = event.angleDelta().y()

        # Calculate zoom factor (smaller for smoother zoom)
        # 120 degrees = standard wheel step
        zoom_factor = 1.0 + (delta / 1200.0)  # 10% zoom per full wheel step

        # Emit the zoom request signal
        self.zoom_requested.emit(zoom_factor)


class MapTab(QWidget):
    """Map tab component for displaying and interacting with map images."""

    map_image_changed = pyqtSignal(str)  # Signal when map image path changes
    pin_mode_toggled = pyqtSignal(bool)  # Signal for pin mode changes
    pin_created = pyqtSignal(
        str, str, dict
    )  # Signal target_node, direction, properties

    def __init__(self, parent: Optional[QWidget] = None, controller=None) -> None:
        """Initialize the map tab."""
        super().__init__(parent)
        self.current_scale = 1.0
        self.map_image_path = None
        self.pin_placement_active = False
        self.controller = controller

        self.zoom_timer = QTimer()
        self.zoom_timer.setSingleShot(True)
        self.zoom_timer.timeout.connect(self._perform_zoom)
        self.pending_scale = None
        self.setup_map_tab_ui()

    def setup_map_tab_ui(self) -> None:
        """Setup the UI components."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Image controls
        image_controls = QHBoxLayout()

        # Change map image button
        self.change_map_btn = QPushButton("Change Map Image")
        self.change_map_btn.clicked.connect(self._change_map_image)

        # Clear map image button
        self.clear_map_btn = QPushButton("Clear Map Image")
        self.clear_map_btn.clicked.connect(self._clear_map_image)

        # Pin toggle button
        self.pin_toggle_btn = QPushButton("📍 Place Pin")
        self.pin_toggle_btn.setCheckable(True)
        self.pin_toggle_btn.toggled.connect(self.toggle_pin_placement)
        self.pin_toggle_btn.setToolTip("Toggle pin placement mode (ESC to cancel)")

        image_controls.addWidget(self.change_map_btn)
        image_controls.addWidget(self.clear_map_btn)
        image_controls.addWidget(self.pin_toggle_btn)
        image_controls.addStretch()

        # Zoom controls
        zoom_controls = QHBoxLayout()

        self.zoom_slider = QSlider(Qt.Orientation.Horizontal)
        self.zoom_slider.setMinimum(10)  # 10% zoom
        self.zoom_slider.setMaximum(200)  # 200% zoom
        self.zoom_slider.setValue(100)  # 100% default
        self.zoom_slider.valueChanged.connect(self._handle_zoom)

        self.reset_button = QPushButton("Reset Zoom")
        self.reset_button.clicked.connect(self._reset_zoom)

        zoom_controls.addWidget(QLabel("Zoom:"))
        zoom_controls.addWidget(self.zoom_slider)
        zoom_controls.addWidget(self.reset_button)

        # Create scrollable image area
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Image display using PannableLabel
        self.image_label = PannableLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.zoom_requested.connect(self._handle_wheel_zoom)
        self.image_label.pin_placed.connect(self._handle_pin_placement)
        self.scroll_area.setWidget(self.image_label)

        # Add all components to layout
        layout.addLayout(image_controls)
        layout.addLayout(zoom_controls)
        layout.addWidget(self.scroll_area)

        self.setLayout(layout)

    def _handle_wheel_zoom(self, zoom_factor: float) -> None:
        """Handle zoom requests from mouse wheel."""
        # Calculate new scale
        new_scale = self.current_scale * zoom_factor

        # Clamp scale to slider limits (10% to 200%)
        new_scale = max(0.1, min(2.0, new_scale))

        # Update slider value
        self.zoom_slider.setValue(int(new_scale * 100))

    def set_map_image(self, image_path: Optional[str]) -> None:
        """Set the map image path and display the image."""
        self.map_image_path = image_path
        if not image_path:
            self.image_label.clear()
            self.image_label.setText("No map image set")
            return

        pixmap = QPixmap(image_path)
        if pixmap.isNull():
            self.image_label.setText(f"Error loading map image: {image_path}")
            return

        self.original_pixmap = pixmap
        self._update_map_image_display()

    def get_map_image_path(self) -> Optional[str]:
        """Get the current map image path."""
        return self.map_image_path

    def _change_map_image(self) -> None:
        """Handle changing the map image."""
        file_name, _ = QFileDialog.getOpenFileName(
            self,
            "Select Map Image",
            "",
            "Image Files (*.png *.jpg *.jpeg);;All Files (*)",
        )
        if file_name:
            self.set_map_image(file_name)
            self.map_image_changed.emit(file_name)

    def _clear_map_image(self) -> None:
        """Clear the current map image."""
        self.set_map_image(None)
        self.map_image_changed.emit("")

    def _handle_zoom(self) -> None:
        """Handle zoom slider value changes with debouncing."""
        self.pending_scale = self.zoom_slider.value() / 100

        # Reset and restart the timer
        self.zoom_timer.start(10)  # 10ms debounce

    def _perform_zoom(self) -> None:
        """Actually perform the zoom operation after debounce."""
        if self.pending_scale is not None:
            self.current_scale = self.pending_scale
            self._update_map_image_display()
            self.pending_scale = None

    def _reset_zoom(self) -> None:
        """Reset zoom to 100%."""
        self.zoom_slider.setValue(100)
        self.current_scale = 1.0
        self._update_map_image_display()

    def _update_map_image_display(self) -> None:
        """Update the displayed image with current scale while maintaining the center point."""
        if not hasattr(self, "original_pixmap"):
            return

        # Get the scroll area's viewport dimensions
        viewport_width = self.scroll_area.viewport().width()
        viewport_height = self.scroll_area.viewport().height()

        # Get current scroll bars' positions and ranges
        h_bar = self.scroll_area.horizontalScrollBar()
        v_bar = self.scroll_area.verticalScrollBar()

        # Calculate current viewport center in scroll coordinates
        visible_center_x = h_bar.value() + viewport_width / 2
        visible_center_y = v_bar.value() + viewport_height / 2

        # Calculate relative position (0 to 1) in the current image
        if self.image_label.pixmap():
            current_image_width = self.image_label.pixmap().width()
            current_image_height = self.image_label.pixmap().height()
            rel_x = (
                visible_center_x / current_image_width
                if current_image_width > 0
                else 0.5
            )
            rel_y = (
                visible_center_y / current_image_height
                if current_image_height > 0
                else 0.5
            )
        else:
            rel_x = 0.5
            rel_y = 0.5

        # Create the scaled pixmap
        scaled_pixmap = self.original_pixmap.transformed(
            QTransform().scale(self.current_scale, self.current_scale),
            Qt.TransformationMode.SmoothTransformation,
        )

        # Update the image
        self.image_label.setPixmap(scaled_pixmap)

        # Calculate new scroll position based on relative position
        new_width = scaled_pixmap.width()
        new_height = scaled_pixmap.height()
        new_x = int(new_width * rel_x - viewport_width / 2)
        new_y = int(new_height * rel_y - viewport_height / 2)

        # Use a short delay to ensure the scroll area has updated its geometry
        QTimer.singleShot(1, lambda: self._set_scroll_position(new_x, new_y))

    def _set_scroll_position(self, x: int, y: int) -> None:
        """Set scroll position with boundary checking."""
        h_bar = self.scroll_area.horizontalScrollBar()
        v_bar = self.scroll_area.verticalScrollBar()

        # Ensure values are within valid range
        x = max(0, min(x, h_bar.maximum()))
        y = max(0, min(y, v_bar.maximum()))

        h_bar.setValue(x)
        v_bar.setValue(y)

    def toggle_pin_placement(self, active: bool) -> None:
        """Toggle pin placement mode."""
        self.pin_placement_active = active
        self.image_label.pin_placement_active = active

        # Update cursor based on mode
        if active:
            self.image_label.setCursor(QCursor(Qt.CursorShape.CrossCursor))
        else:
            self.image_label.setCursor(QCursor(Qt.CursorShape.ArrowCursor))

        # Emit signal for other components
        self.pin_mode_toggled.emit(active)

    def _handle_pin_placement(self, x: int, y: int) -> None:
        """Handle pin placement at the specified coordinates."""
        dialog = PinPlacementDialog(x, y, self, self.controller)
        dialog.setWindowModality(Qt.WindowModality.ApplicationModal)

        if dialog.exec():
            target_node = dialog.get_target_node()
            if target_node:
                # Create relationship data
                properties = {"x": x, "y": y}

                self.pin_created.emit(target_node, ">", properties)

                # Exit pin placement mode
                self.pin_toggle_btn.setChecked(False)
