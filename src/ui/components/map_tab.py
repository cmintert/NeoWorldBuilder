import json
import os
from typing import Optional, Dict, Tuple, List

from PyQt6.QtCore import Qt, pyqtSignal, QPoint, QTimer, QSize, QThread
from PyQt6.QtGui import (
    QPixmap,
    QTransform,
    QMouseEvent,
    QCursor,
    QWheelEvent,
    QKeyEvent,
    QPen,
    QPainter,
    QColor,
)
from PyQt6.QtSvgWidgets import QSvgWidget
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QScrollArea,
    QSlider,
    QHBoxLayout,
    QPushButton,
    QFileDialog,
    QLineEdit,
)
from structlog import get_logger


from ui.components.line_container import LineContainer
from ui.components.dialogs import PinPlacementDialog, LineFeatureDialog
from utils.geometry_handler import GeometryHandler
from utils.path_helper import get_resource_path

logger = get_logger(__name__)


class MapImageLoader(QThread):
    """Thread for loading map images."""

    loaded = pyqtSignal(QPixmap)

    def __init__(self, image_path: str):
        super().__init__()
        self.image_path = image_path

    def run(self):
        pixmap = QPixmap(self.image_path)
        self.loaded.emit(pixmap)


class PannableLabel(QLabel):
    """Custom QLabel that supports panning with click and drag."""

    zoom_requested = pyqtSignal(float)  # Signal for zoom requests
    pin_placed = pyqtSignal(int, int)  # Signal for pin placement
    pin_clicked = pyqtSignal(str)
    line_completed = pyqtSignal(list)  # Emits list of points when line is complete
    line_clicked = pyqtSignal(str)  # Emits target_node when line is clicked

    def __init__(self, parent=None, config=None):
        super().__init__()
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMouseTracking(True)
        self.is_panning = False
        self.last_mouse_pos = QPoint()
        self.pin_placement_active = False
        self.parent_map_tab = parent
        self.config = config
        # Coordinate Label for cursor pos
        self.cursor_pos = QPoint()
        self.coordinate_label = QLabel(self)
        self.coordinate_label.setStyleSheet(
            "QLabel { background-color: rgba(0, 0, 0, 150); color: white; padding: 5px; border-radius: 3px; }"
        )
        self.coordinate_label.hide()

        self.pin_container = QWidget(self)

        self.pin_container.setGeometry(0, 0, self.width(), self.height())
        self.pins: Dict[str, QLabel] = {}

        # Line drawing support
        self.line_drawing_active = False
        self.current_line_points = []
        self.lines = {}  # Dictionary mapping target_node to LineContainer
        self.temp_line_coordinates = []  # Stores coordinates during drawing

    def resizeEvent(self, event):
        """Handle resize events to keep pin container matched to size."""
        super().resizeEvent(event)
        self.pin_container.setGeometry(0, 0, self.width(), self.height())
        self.pin_container.raise_()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Handle mouse press events for panning and pin placement."""
        pixmap = self.pixmap()
        if pixmap:
            # Get the displayed image dimensions
            pixmap_size = pixmap.size()
            widget_width, widget_height = self.width(), self.height()
            offset_x = max(0, (widget_width - pixmap_size.width()) // 2)
            offset_y = max(0, (widget_height - pixmap_size.height()) // 2)

            # Mouse position relative to the widget
            widget_pos = event.pos()

            # Calculate image-relative position
            scaled_x = widget_pos.x() - offset_x
            scaled_y = widget_pos.y() - offset_y
            current_scale = self.parent_map_tab.current_scale
            original_x = scaled_x / current_scale
            original_y = scaled_y / current_scale

            # Handle pin placement
            if (
                self.pin_placement_active
                and event.button() == Qt.MouseButton.LeftButton
            ):
                if (
                    0 <= scaled_x <= pixmap_size.width()
                    and 0 <= scaled_y <= pixmap_size.height()
                ):
                    self.pin_placed.emit(int(original_x), int(original_y))

            # Handle line drawing
            if self.line_drawing_active and event.button() == Qt.MouseButton.LeftButton:
                if (
                    0 <= scaled_x <= pixmap_size.width()
                    and 0 <= scaled_y <= pixmap_size.height()
                ):
                    # Add point to current line
                    self.current_line_points.append((int(original_x), int(original_y)))
                    self.temp_line_coordinates.append((scaled_x, scaled_y))
                    self.update()  # Redraw to show the line

            # Handle panning
            elif (
                not self.pin_placement_active
                and event.button() == Qt.MouseButton.LeftButton
            ):
                self.is_panning = True
                self.last_mouse_pos = widget_pos
                self.setCursor(QCursor(Qt.CursorShape.ClosedHandCursor))

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Handle key press events."""
        print(f"Key press: {event.key()}")

        if event.key() == Qt.Key.Key_Escape:
            if self.pin_placement_active:
                self.pin_placement_active = False
                self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
                self.coordinate_label.hide()
                # Also update button state
                if self.parent_map_tab:
                    self.parent_map_tab.pin_toggle_btn.setChecked(False)
                event.accept()
                return
            elif self.line_drawing_active:
                if self.parent_map_tab:
                    # Use toggle method to exit line mode properly
                    self.parent_map_tab.line_toggle_btn.setChecked(False)
                event.accept()
                return

        elif event.key() == Qt.Key.Key_Return:
            if self.line_drawing_active and len(self.current_line_points) >= 2:
                print("Enter key detected - completing line")
                points = self.current_line_points.copy()

                # Complete drawing but prevent duplicates
                self.line_drawing_active = False

                if self.parent_map_tab:
                    # Directly call handler instead of emitting signal
                    self.parent_map_tab._handle_line_completion(points)
                    # Update button state but block signals
                    self.parent_map_tab.line_toggle_btn.blockSignals(True)
                    self.parent_map_tab.line_toggle_btn.setChecked(False)
                    self.parent_map_tab.line_toggle_btn.blockSignals(False)

                event.accept()
                return

        # Pass unhandled events to parent
        super().keyPressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """Handle mouse release events to stop panning."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_panning = False
            if not self.pin_placement_active:
                self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """Handle mouse movement for panning and cursor updates."""
        pixmap = self.pixmap()
        if pixmap:
            # Handle panning
            if self.is_panning:
                delta = event.pos() - self.last_mouse_pos
                self.last_mouse_pos = event.pos()

                # Adjust scroll bars to pan the image
                h_bar = self.parent_map_tab.scroll_area.horizontalScrollBar()
                v_bar = self.parent_map_tab.scroll_area.verticalScrollBar()
                h_bar.setValue(h_bar.value() - delta.x())
                v_bar.setValue(v_bar.value() - delta.y())

            else:
                # Get the displayed image dimensions
                pixmap_size = pixmap.size()
                widget_width, widget_height = self.width(), self.height()
                offset_x = max(0, (widget_width - pixmap_size.width()) // 2)
                offset_y = max(0, (widget_height - pixmap_size.height()) // 2)

                # Mouse position relative to the widget
                widget_pos = event.pos()

                # Calculate image-relative position
                scaled_x = widget_pos.x() - offset_x
                scaled_y = widget_pos.y() - offset_y
                current_scale = self.parent_map_tab.current_scale
                original_x = scaled_x / current_scale
                original_y = scaled_y / current_scale

                # Update cursor coordinates if within image bounds
                if (
                    0 <= scaled_x <= pixmap_size.width()
                    and 0 <= scaled_y <= pixmap_size.height()
                ):
                    self.coordinate_label.setText(
                        f"X: {int(original_x)}, Y: {int(original_y)}"
                    )
                    self.coordinate_label.move(widget_pos.x() + 15, widget_pos.y() + 15)
                    self.coordinate_label.show()
                else:
                    self.coordinate_label.hide()

    def wheelEvent(self, event: QWheelEvent) -> None:
        """Handle mouse wheel events for zooming."""
        # Get the number of degrees rotated (usually 120 or -120)
        delta = event.angleDelta().y()

        zoom_factor = 1.0 + (delta / 1200.0)

        # Emit the zoom request signal
        self.zoom_requested.emit(zoom_factor)

    def create_pin(self, target_node: str, x: int, y: int) -> None:
        """Create and position a pin with tooltip."""

        if target_node in self.pins:
            self.pins[target_node].deleteLater()
            del self.pins[target_node]

        # Create pin container with both pin and label
        pin_container = PinContainer(
            target_node, self.pin_container, config=self.config
        )

        # Add this line to connect the pin's click signal
        pin_container.pin_clicked.connect(self.pin_clicked.emit)

        # Set initial scale
        pin_container.set_scale(self.parent_map_tab.current_scale)

        # Store original coordinates
        pin_container.original_x = x
        pin_container.original_y = y

        self.pins[target_node] = pin_container
        pin_container.show()
        self.update_pin_container_position(target_node, x, y)

    def batch_create_pins(self, pin_data: List[Tuple[str, int, int]]) -> None:
        """Create multiple pins efficiently."""
        # Pre-allocate widgets to minimize layout recalculations
        for target_node, x, y in pin_data:
            if target_node in self.pins:
                self.pins[target_node].deleteLater()
                del self.pins[target_node]

        # Temporarily disable updates
        self.pin_container.setUpdatesEnabled(False)

        try:
            for target_node, x, y in pin_data:
                pin_container = PinContainer(
                    target_node, self.pin_container, config=self.config
                )
                pin_container.pin_clicked.connect(self.pin_clicked.emit)
                pin_container.set_scale(self.parent_map_tab.current_scale)
                pin_container.original_x = x
                pin_container.original_y = y
                self.pins[target_node] = pin_container
                self.update_pin_container_position(target_node, x, y)
                pin_container.show()
        finally:
            # Re-enable updates and force a single update
            self.pin_container.setUpdatesEnabled(True)
            self.pin_container.update()

    def update_pin_container_position(self, target_node: str, x: int, y: int) -> None:
        """Update position of a pin container."""
        if target_node not in self.pins:
            return

        viewport_width = self.parent_map_tab.scroll_area.viewport().width()
        viewport_height = self.parent_map_tab.scroll_area.viewport().height()

        pin_container = self.pins[target_node]

        if not hasattr(pin_container, "original_x"):
            pin_container.original_x = x
            pin_container.original_y = y

        # Update the container's scale
        pin_container.set_scale(self.parent_map_tab.current_scale)

        # Calculate scaled position using stored original coordinates
        current_scale = self.parent_map_tab.current_scale
        scaled_x = pin_container.original_x * current_scale
        scaled_y = pin_container.original_y * current_scale

        # Account for Widget and scaled image size
        if pixmap := self.pixmap():
            image_width = pixmap.width()
            image_height = pixmap.height()
            if image_width < viewport_width:
                scaled_x += (viewport_width - image_width) / 2
            if image_height < viewport_height:
                scaled_y += (viewport_height - image_height) / 2

        # Account for container dimensions - align bottom of pin with point
        pin_x = int(scaled_x - (pin_container.pin_svg.width() / 2))
        pin_y = int(scaled_y - pin_container.pin_svg.height())

        pin_container.move(pin_x, pin_y)
        pin_container.raise_()
        pin_container.show()

    def update_pin_positions(self) -> None:
        """Update all pin and line positions using stored original
        coordinates."""

        for target_node, pin in self.pins.items():
            # Use the stored original coordinates rather than trying to calculate back
            if hasattr(pin, "original_x") and hasattr(pin, "original_y"):
                self.update_pin_container_position(
                    target_node, pin.original_x, pin.original_y
                )
        self.update_line_positions()

    def clear_pins(self) -> None:
        """Remove all pins."""
        for pin in self.pins.values():
            pin.deleteLater()
        self.pins.clear()

    def paintEvent(self, event):
        """Override paint event to draw temporary line while drawing."""
        super().paintEvent(event)

        # Draw temporary line while in drawing mode
        if self.line_drawing_active and len(self.temp_line_coordinates) > 0:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)

            # Set up pen for temporary line
            pen = QPen(QColor("#3388FF"))
            pen.setWidth(2)
            pen.setStyle(Qt.PenStyle.DashLine)
            painter.setPen(pen)

            # Draw temporary line segments
            if len(self.temp_line_coordinates) >= 2:
                for i in range(len(self.temp_line_coordinates) - 1):
                    p1 = self.temp_line_coordinates[i]
                    p2 = self.temp_line_coordinates[i + 1]
                    painter.drawLine(p1[0], p1[1], p2[0], p2[1])

    def create_line(self, target_node: str, points: List[Tuple[int, int]]) -> None:
        """Create and position a line feature.

        Args:
            target_node (str): The node name this line represents.
            points (List[Tuple[int, int]]): List of coordinate points making up the line.
        """
        if target_node in self.lines:
            self.lines[target_node].deleteLater()
            del self.lines[target_node]

        line_container = LineContainer(
            target_node,
            points,
            self.pin_container,  # Use same parent as pins
            config=self.config,
        )

        line_container.line_clicked.connect(self.line_clicked.emit)
        line_container.set_scale(self.parent_map_tab.current_scale)
        self.lines[target_node] = line_container
        line_container.show()
        line_container.raise_()

        # Look for style properties in the relationships table
        if self.parent_map_tab and self.parent_map_tab.controller:
            relationships_table = self.parent_map_tab.controller.ui.relationships_table

            if relationships_table:
                for row in range(relationships_table.rowCount()):
                    try:
                        rel_type = relationships_table.item(row, 0)
                        target = relationships_table.cellWidget(row, 1)
                        props_item = relationships_table.item(row, 3)

                        # Check if this is the right relationship
                        target_matches = False
                        if target and isinstance(target, QLineEdit):
                            target_matches = target.text() == target_node

                        if (
                            rel_type
                            and rel_type.text() == "SHOWS"
                            and target_matches
                            and props_item
                        ):

                            properties = json.loads(props_item.text())

                            # Extract style properties if they exist
                            style_color = properties.get("style_color")
                            style_width = properties.get("style_width")
                            style_pattern = properties.get("style_pattern")

                            # Apply style if any style properties exist
                            if style_color or style_width or style_pattern:
                                line_container.set_style(
                                    color=style_color,
                                    width=style_width,
                                    pattern=style_pattern,
                                )
                                break  # Found and applied style

                    except Exception as e:
                        # Just log and continue if there's an error with one relationship
                        print(f"Error getting line style: {e}")
                        continue

    def batch_create_lines(
        self, line_data: List[Tuple[str, List[Tuple[int, int]]]]
    ) -> None:
        """Create multiple lines efficiently.

        Args:
            line_data (List[Tuple[str, List[Tuple[int, int]]]]): List of (target_node, points) tuples.
        """
        # Pre-process any existing lines that need to be deleted
        for target_node, _ in line_data:
            if target_node in self.lines:
                self.lines[target_node].deleteLater()
                del self.lines[target_node]

        # Temporarily disable updates
        self.pin_container.setUpdatesEnabled(False)

        try:
            for target_node, points in line_data:
                line_container = LineContainer(
                    target_node, points, self.pin_container, config=self.config
                )
                line_container.line_clicked.connect(self.line_clicked.emit)
                line_container.set_scale(self.parent_map_tab.current_scale)
                self.lines[target_node] = line_container
                line_container.show()
                line_container.raise_()
        finally:
            # Re-enable updates and force a single update
            self.pin_container.setUpdatesEnabled(True)
            self.pin_container.update()

    def update_line_positions(self) -> None:
        """Update all line positions using stored original coordinates."""
        for line in self.lines.values():
            line.set_scale(self.parent_map_tab.current_scale)

    def clear_lines(self) -> None:
        """Remove all lines."""
        for line in self.lines.values():
            line.deleteLater()
        self.lines.clear()


class MapTab(QWidget):
    """Map tab component for displaying and interacting with map images."""

    map_image_changed = pyqtSignal(str)  # Signal when map image path changes
    pin_mode_toggled = pyqtSignal(bool)  # Signal for pin mode changes
    pin_created = pyqtSignal(
        str, str, dict
    )  # Signal target_node, direction, properties
    pin_clicked = pyqtSignal(str)
    line_created = pyqtSignal(
        str, str, dict
    )  # Signal for line creation (target_node, direction, properties)

    def __init__(self, parent: Optional[QWidget] = None, controller=None) -> None:
        """Initialize the map tab."""
        super().__init__(parent)
        self.current_scale = 1.0
        self.map_image_path = None
        self.pin_placement_active = False
        self.line_drawing_active = False
        self.controller = controller
        self.config = controller.config

        self.zoom_timer = QTimer()
        self.zoom_timer.setSingleShot(True)
        self.zoom_timer.timeout.connect(self._perform_zoom)
        self.pending_scale = None

        self._pixmap_cache = {}
        self.current_loader = None

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

        # Line toggle button
        self.line_toggle_btn = QPushButton("📏 Draw Line")
        self.line_toggle_btn.setCheckable(True)
        self.line_toggle_btn.toggled.connect(self.toggle_line_drawing)
        self.line_toggle_btn.setToolTip(
            "Toggle line drawing mode (ESC to cancel, Enter to complete)"
        )

        image_controls.addWidget(self.change_map_btn)
        image_controls.addWidget(self.clear_map_btn)
        image_controls.addStretch()
        image_controls.addWidget(self.pin_toggle_btn)
        image_controls.addWidget(self.line_toggle_btn)
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
        self.image_label = PannableLabel(self, config=self.config)
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.zoom_requested.connect(self._handle_wheel_zoom)
        self.image_label.pin_placed.connect(self._handle_pin_placement)

        if self.controller:
            self.image_label.pin_clicked.connect(self.controller._handle_pin_click)
        else:
            print("Warning: No controller present for pin clicks")

        self.image_label.line_completed.connect(self._handle_line_completion)
        self.image_label.line_clicked.connect(
            lambda target: self.pin_clicked.emit(target)
        )

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

        # Clamp scale to slider limits (1% to 200%)
        new_scale = max(0.1, min(2.0, new_scale))

        # Update slider value
        self.zoom_slider.setValue(int(new_scale * 100))

    def set_map_image(self, image_path: Optional[str]) -> None:
        """Set the map image path and display the image."""
        self.map_image_path = image_path

        # Early exit for no image
        if not image_path:
            self.image_label.clear_pins()
            self.image_label.clear()
            self.image_label.setText("No map image set")
            return

        # Check cache first
        if image_path in self._pixmap_cache:
            pixmap = self._pixmap_cache[image_path]
            self.original_pixmap = pixmap
            self._update_map_image_display()
            self.load_features()
            return

        # Show loading state
        self.image_label.setText("Loading map...")

        # Start loading in background
        self.current_loader = MapImageLoader(image_path)
        self.current_loader.loaded.connect(self._on_image_loaded)
        self.current_loader.start()

    def _on_image_loaded(self, pixmap: QPixmap) -> None:
        """Handle when image has finished loading."""
        if pixmap.isNull():
            self.image_label.clear_pins()
            self.image_label.setText(f"Error loading map image: {self.map_image_path}")
            return

            # Cache the successfully loaded pixmap
        self._pixmap_cache[self.map_image_path] = pixmap
        self.original_pixmap = pixmap

        # Calculate initial scale to fit width
        viewport_width = self.scroll_area.viewport().width()
        image_width = pixmap.width()

        if image_width > 0:
            # Calculate scale to fit width with a small margin (95% of viewport)
            self.current_scale = (viewport_width) / image_width
            # Update zoom slider to match
            self.zoom_slider.setValue(int(self.current_scale * 100))

        # Update display with calculated scale
        self._update_map_image_display()
        self.load_features()

    def load_features(self) -> None:
        """Process and load all spatial features from relationships table."""
        self.image_label.clear_pins()
        self.image_label.clear_lines()

        if not self.controller or not self.controller.ui.relationships_table:
            return

        # Batch collect all feature data first
        pin_data = []
        line_data = []
        style_data = {}  # Store style information for lines
        relationships_table = self.controller.ui.relationships_table

        for row in range(relationships_table.rowCount()):
            try:
                rel_type = relationships_table.item(row, 0)
                if not rel_type or rel_type.text() != "SHOWS":
                    continue

                target_item = relationships_table.item(row, 1)
                props_item = relationships_table.item(row, 3)

                if not (target_item and props_item):
                    continue

                properties = json.loads(props_item.text())
                if "geometry" not in properties:
                    logger.warning(
                        f"Spatial relationship missing geometry for {target_item.text()}"
                    )
                    continue

                # Skip invalid WKT
                if not GeometryHandler.validate_wkt(properties["geometry"]):
                    logger.error(f"Invalid WKT geometry for {target_item.text()}")
                    continue

                # Determine geometry type using existing GeometryHandler
                geometry_type = GeometryHandler.get_geometry_type(
                    properties["geometry"]
                )

                target_node = ""
                if hasattr(target_item, "text"):
                    target_node = target_item.text()
                else:
                    target_widget = relationships_table.cellWidget(row, 1)
                    if isinstance(target_widget, QLineEdit):
                        target_node = target_widget.text()

                if geometry_type == "LineString":
                    # Extract linestring coordinates
                    points = GeometryHandler.get_coordinates(properties["geometry"])
                    line_data.append((target_node, points))

                    # Store style data for later application
                    style_data[target_node] = {
                        "color": properties.get("style_color", "#FF0000"),
                        "width": properties.get("style_width", 2),
                        "pattern": properties.get("style_pattern", "solid"),
                    }

                elif geometry_type == "Point":
                    # Handle points (pins)
                    x, y = GeometryHandler.get_coordinates(properties["geometry"])
                    pin_data.append((target_node, x, y))
                # Additional geometry types can be handled here in the future

            except Exception as e:
                logger.error(f"Error loading spatial feature: {e}")
                continue

        # Batch create all features
        if pin_data:
            self.image_label.batch_create_pins(pin_data)

        if line_data:
            self.image_label.batch_create_lines(line_data)

            # Apply styles to created lines
            for target_node, style in style_data.items():
                if target_node in self.image_label.lines:
                    self.image_label.lines[target_node].set_style(
                        color=style["color"],
                        width=style["width"],
                        pattern=style["pattern"],
                    )

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

            self.image_label.pin_container.raise_()
            self.image_label.update_pin_positions()
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
            self.pin_toggle_btn.setStyleSheet("background: white")
        else:
            self.image_label.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
            self.pin_toggle_btn.setStyleSheet("background: grey")
        # Emit signal for other components
        self.pin_mode_toggled.emit(active)

    def _handle_pin_placement(self, x: int, y: int) -> None:
        """Handle pin placement at the specified coordinates."""
        dialog = PinPlacementDialog(x, y, self, self.controller)
        dialog.setWindowModality(Qt.WindowModality.ApplicationModal)

        if dialog.exec():
            target_node = dialog.get_target_node()
            if target_node:
                # Create relationship data using WKT format
                wkt_point = GeometryHandler.create_point(x, y)
                properties = GeometryHandler.create_geometry_properties(wkt_point)

                self.pin_created.emit(target_node, ">", properties)

                # Create pin immediately after dialog success
                self.image_label.create_pin(target_node, x, y)

                # Exit pin placement mode
                self.pin_toggle_btn.setChecked(False)

    def toggle_line_drawing(self, active: bool) -> None:
        """Toggle line drawing mode."""
        # Check if we're ending a drawing session with valid points
        completing_drawing = (
            not active
            and self.line_drawing_active
            and len(self.image_label.current_line_points) >= 2
        )

        # Store current state before changing it
        was_active = self.line_drawing_active
        self.line_drawing_active = active
        self.image_label.line_drawing_active = active

        # Disable pin placement if line drawing is enabled
        if active and self.pin_toggle_btn.isChecked():
            self.pin_toggle_btn.setChecked(False)

        # Update cursor and button appearance
        if active:
            self.image_label.setCursor(QCursor(Qt.CursorShape.CrossCursor))
            self.line_toggle_btn.setStyleSheet("background-color: #83A00E;")
            # When activating, ensure it has focus
            self.image_label.setFocus()
        else:
            self.image_label.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
            self.line_toggle_btn.setStyleSheet("")

            # If deactivating from timeout/ESC (not from a completed line),
            # and we have valid points, then handle completion
            if (
                was_active
                and completing_drawing
                and len(self.image_label.temp_line_coordinates) > 0
            ):
                points = self.image_label.current_line_points.copy()
                print(f"Toggle-triggered line completion with {len(points)} points")
                self._handle_line_completion(points)

            # Clear the temporary drawing data
            self.image_label.current_line_points = []
            self.image_label.temp_line_coordinates = []
            self.image_label.update()

    def _handle_line_completion(self, points: List[Tuple[int, int]]) -> None:
        """Handle a completed line."""
        print(f"Handling line completion with {len(points)} points")

        if len(points) < 2:
            print("Not enough points for a line")
            return  # Need at least 2 points for a line

        # Use dedicated line dialog
        dialog = LineFeatureDialog(points, self, self.controller)

        if dialog.exec():
            target_node = dialog.get_target_node()
            line_style = dialog.get_line_style()

            print(f"Line dialog accepted with target: {target_node}")
            print(f"Line style: {line_style}")

            try:
                # Create WKT LineString using existing GeometryHandler
                wkt_line = GeometryHandler.create_line(points)

                # Flatten the style properties to avoid Neo4j nested object error
                properties = {
                    "geometry": wkt_line,
                    "geometry_type": "LineString",
                    "style_color": line_style["color"],
                    "style_width": line_style["width"],
                    "style_pattern": line_style["pattern"],
                }

                print(f"Properties JSON: {json.dumps(properties, indent=2)}")
                print(f"Emitting line_created signal for {target_node}")

                # Directly add relationship instead of using signal
                if self.controller:
                    self.controller._handle_line_created(target_node, ">", properties)
                    print("Direct handler call completed")

                # Also emit signal as backup
                self.line_created.emit(target_node, ">", properties)
                print("Signal emitted")

                # Create line immediately for visual feedback
                self.image_label.create_line(target_node, points)

                # Set line style
                if target_node in self.image_label.lines:
                    self.image_label.lines[target_node].set_style(
                        color=line_style["color"],
                        width=line_style["width"],
                        pattern=line_style["pattern"],
                    )

                # We directly manipulate the button state to prevent re-triggering
                # This breaks the cycle of events that causes the double dialog
                self.line_toggle_btn.blockSignals(True)
                self.line_toggle_btn.setChecked(False)
                self.line_toggle_btn.blockSignals(False)
                self.line_drawing_active = False
                self.image_label.line_drawing_active = False

                # Clear the drawing state
                self.image_label.current_line_points = []
                self.image_label.temp_line_coordinates = []
                self.image_label.update()

            except Exception as e:
                print(f"ERROR in line completion: {str(e)}")
                import traceback

                traceback.print_exc()


class PinContainer(QWidget):
    """Container widget that holds both a pin and its label."""

    pin_clicked = pyqtSignal(str)

    def __init__(self, target_node: str, parent=None, config=None):
        super().__init__(parent)
        self._scale = 1.0  # Initialize scale attribute
        self.config = config

        # Make mouse interactive
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.setMouseTracking(True)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        # Create layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        # Create SVG pin with error handling

        svg_path = get_resource_path(self.config.map.PIN_SVG_SOURCE)

        try:
            if not os.path.exists(svg_path):
                print(f"SVG file not found: {svg_path}")
                raise FileNotFoundError(f"SVG file not found: {svg_path}")

            self.pin_svg = QSvgWidget(self)
            self.pin_svg.load(svg_path)

            # Verify the widget has valid dimensions after loading
            if self.pin_svg.width() == 0 or self.pin_svg.height() == 0:
                print(f"Failed to load SVG properly: {svg_path}")
                raise RuntimeError(f"Failed to load SVG properly: {svg_path}")

            self.update_pin_size()

        except Exception as e:
            print(f"Error loading SVG, falling back to emoji: {e}")
            # Fallback to emoji if SVG fails
            self.pin_svg = QLabel("📍", self)
            self.pin_svg.setFixedSize(
                QSize(self.config.map.BASE_PIN_WIDTH, self.config.map.BASE_PIN_HEIGHT)
            )  # Set initial size for emoji

        # Create text label
        self.text_label = QLabel(target_node)
        self.update_label_style()

        # Add widgets to layout
        layout.addWidget(self.pin_svg)
        layout.addWidget(self.text_label)

        # Set container to be transparent
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # Adjust size
        self.adjustSize()

    def update_pin_size(self) -> None:
        """Update pin size based on current scale."""
        # Calculate size based on scale, but don't go below minimum
        width = max(
            int(self.config.map.BASE_PIN_WIDTH * self._scale),
            self.config.map.MIN_PIN_WIDTH,
        )
        height = max(
            int(self.config.map.BASE_PIN_HEIGHT * self._scale),
            self.config.map.MIN_PIN_HEIGHT,
        )

        # Check if we're using SVG or emoji fallback
        if isinstance(self.pin_svg, QSvgWidget):
            self.pin_svg.setFixedSize(QSize(width, height))
        else:
            # For emoji label, just update the font size
            font_size = max(int(14 * self._scale), 8)  # Minimum font size for emoji
            font = self.pin_svg.font()
            font.setPointSize(font_size)
            self.pin_svg.setFont(font)

    def update_label_style(self) -> None:
        """Update label style based on current scale."""
        # Adjust font size based on scale
        font_size = max(int(8 * self._scale), 6)  # Minimum font size of 6pt
        self.text_label.setStyleSheet(
            f"""
            QLabel {{
                background-color: rgba(0, 0, 0, 50);
                color: white;
                padding: {max(int(2 * self._scale), 1)}px {max(int(4 * self._scale), 2)}px;
                border-radius: 3px;
                font-size: {font_size}pt;
            }}
        """
        )

    def set_scale(self, scale: float) -> None:
        """Set the current scale and update sizes."""
        self._scale = scale
        self.update_pin_size()
        self.update_label_style()
        self.adjustSize()

    @property
    def pin_height(self) -> int:
        """Get the height of the pin."""
        return self.pin_svg.height()

    def mousePressEvent(self, event: QMouseEvent) -> None:

        if event.button() == Qt.MouseButton.LeftButton:
            self.pin_clicked.emit(self.text_label.text())
        event.accept()  # Make sure we handle the event
