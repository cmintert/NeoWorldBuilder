import json
from typing import Optional, List, Tuple, Dict

from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QPainter, QKeyEvent, QCursor
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
from structlog import get_logger

from utils.geometry_handler import GeometryHandler
from .drawing_manager import DrawingManager
from .line_feature_dialog import LineFeatureDialog
from .branching_line_feature_dialog import BranchingLineFeatureDialog
from .map_image_loader import ImageManager
from .map_viewport import MapViewport
from .pin_placement_dialog import PinPlacementDialog
from .feature_manager import UnifiedFeatureManager
from .utils.coordinate_transformer import CoordinateTransformer

logger = get_logger(__name__)


class MapTab(QWidget):
    """Refactored map tab with separated concerns.

    Coordinates between viewport, features, drawing_decap, and image management components
    to provide a complete map editing experience.
    """

    # Map tab signals
    map_image_changed = pyqtSignal(str)
    pin_mode_toggled = pyqtSignal(bool)
    pin_created = pyqtSignal(str, str, dict)
    pin_clicked = pyqtSignal(str)
    line_created = pyqtSignal(str, str, dict)

    def __init__(self, parent: Optional[QWidget] = None, controller=None) -> None:
        """Initialize the map tab.

        Args:
            parent: Parent widget.
            controller: Application controller that manages data flow.
        """
        super().__init__(parent)
        self.controller = controller
        self.config = controller.config if controller else None

        # Core state
        self.current_scale = 1.0
        self.map_image_path = None

        # Mode flags
        self.pin_placement_active = False
        self.line_drawing_active = False
        self.edit_mode_active = False
        self.branching_line_drawing_active = False

        # Initialize separated components
        self._setup_components()
        self._setup_ui()
        self._connect_signals()

    def _setup_components(self) -> None:
        """Initialize all the separated component managers."""
        # Image management
        self.image_manager = ImageManager()

        # Drawing management
        self.drawing_manager = DrawingManager()

        # Zoom management
        self.zoom_timer = QTimer()
        self.zoom_timer.setSingleShot(True)
        self.zoom_timer.timeout.connect(self._perform_zoom)
        self.pending_scale = None

        # Enhanced edit mode will be integrated after basic initialization

    def _setup_ui(self) -> None:
        """Setup the UI components."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Image controls
        image_controls = self._create_image_controls()

        # Zoom controls
        zoom_controls = self._create_zoom_controls()

        # Create scrollable image area with viewport
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Create viewport for map display
        self.image_label = MapViewport(self, config=self.config)

        # Create feature container and manager
        self.feature_container = QWidget(self.image_label)
        self.feature_container.setGeometry(
            0, 0, self.image_label.width(), self.image_label.height()
        )

        # Initialize the unified feature manager
        self.feature_manager = UnifiedFeatureManager(
            self.feature_container, self.config
        )

        self.scroll_area.setWidget(self.image_label)

        # Add all components to layout
        layout.addLayout(image_controls)
        layout.addLayout(zoom_controls)
        layout.addWidget(self.scroll_area)

    def _create_image_controls(self) -> QHBoxLayout:
        """Create the image control buttons."""
        image_controls = QHBoxLayout()

        # Change/Clear map buttons
        self.change_map_btn = QPushButton("Change Map Image")
        self.change_map_btn.clicked.connect(self._change_map_image)

        self.clear_map_btn = QPushButton("Clear Map Image")
        self.clear_map_btn.clicked.connect(self._clear_map_image)

        # Mode toggle buttons
        self.pin_toggle_btn = QPushButton("📍 Place Pin")
        self.pin_toggle_btn.setCheckable(True)
        self.pin_toggle_btn.toggled.connect(self.toggle_pin_placement)
        self.pin_toggle_btn.setToolTip("Toggle pin placement mode (ESC to cancel)")

        self.line_toggle_btn = QPushButton("📏 Draw Line")
        self.line_toggle_btn.setCheckable(True)
        self.line_toggle_btn.toggled.connect(self.toggle_line_drawing)
        self.line_toggle_btn.setToolTip(
            "Toggle line drawing_decap mode (ESC to cancel, Enter to complete)"
        )

        self.branching_line_toggle_btn = QPushButton("🌿 Draw Branching Line")
        self.branching_line_toggle_btn.setCheckable(True)
        self.branching_line_toggle_btn.toggled.connect(
            self.toggle_branching_line_drawing
        )
        self.branching_line_toggle_btn.setToolTip(
            "Toggle branching line drawing_decap mode (ESC to cancel, Enter to complete)"
        )

        self.edit_toggle_btn = QPushButton("✏️ Edit Mode")
        self.edit_toggle_btn.setCheckable(True)
        self.edit_toggle_btn.toggled.connect(self.toggle_edit_mode)
        self.edit_toggle_btn.setToolTip("Edit existing lines (click line to edit)")

        image_controls.addWidget(self.change_map_btn)
        image_controls.addWidget(self.clear_map_btn)
        image_controls.addStretch()
        image_controls.addWidget(self.pin_toggle_btn)
        image_controls.addWidget(self.line_toggle_btn)
        image_controls.addWidget(self.branching_line_toggle_btn)
        image_controls.addWidget(self.edit_toggle_btn)
        image_controls.addStretch()

        return image_controls

    def _create_zoom_controls(self) -> QHBoxLayout:
        """Create the zoom control widgets."""
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

        return zoom_controls

    def _connect_signals(self) -> None:
        """Connect signals between components."""
        # Viewport signals
        self.image_label.zoom_requested.connect(self._handle_wheel_zoom)
        self.image_label.click_at_coordinates.connect(self._handle_coordinate_click)

        # Drawing manager signals
        self.drawing_manager.line_completed.connect(self._handle_line_completion)
        self.drawing_manager.branching_line_completed.connect(
            self._handle_branching_line_completion
        )
        self.drawing_manager.drawing_updated.connect(self._handle_drawing_update)

        # Feature manager signals
        self.feature_manager.feature_clicked.connect(self._handle_feature_click)

        # Connect to controller if available
        if self.controller:
            self.feature_manager.feature_clicked.connect(
                self.controller._handle_pin_click
            )

    def resizeEvent(self, event):
        """Handle resize events to keep feature container matched to viewport size."""
        super().resizeEvent(event)
        if hasattr(self, "feature_container") and hasattr(self, "image_label"):
            # Update feature container to match image label size
            self.feature_container.setGeometry(
                0, 0, self.image_label.width(), self.image_label.height()
            )
            self.feature_container.raise_()

    def paintEvent(self, event):
        """Handle paint events for drawing_decap temporary elements."""
        super().paintEvent(event)

    # Image Management Methods
    def set_map_image(self, image_path: Optional[str]) -> None:
        """Set the map image path and display the image."""
        self.map_image_path = image_path

        if not image_path:
            self._clear_image()
            return

        # Show loading state
        self.image_label.setText("Loading map...")

        # Load image through image manager
        self.image_manager.load_image(
            image_path,
            success_callback=self._on_image_loaded,
            error_callback=self._on_image_error,
        )

    def _on_image_loaded(self, pixmap) -> None:
        """Handle successful image loading."""
        if pixmap.isNull():
            self._clear_image()
            return

        # Calculate initial scale to fit width
        viewport_width = self.scroll_area.viewport().width()
        self.current_scale = self.image_manager.calculate_fit_to_width_scale(
            viewport_width
        )
        self.zoom_slider.setValue(int(self.current_scale * 100))

        # Update display
        self._update_map_image_display()
        self.load_features()

    def _on_image_error(self, error_msg: str) -> None:
        """Handle image loading errors."""
        self.feature_manager.clear_all_features()
        self.image_label.setText(f"Error loading map image: {error_msg}")
        logger.error(f"Map image loading failed: {error_msg}")

    def _clear_image(self) -> None:
        """Clear the current image and features."""
        self.feature_manager.clear_all_features()
        self.image_label.clear()
        self.image_label.setText("No map image set")

    # Zoom Management Methods
    def _handle_wheel_zoom(self, zoom_factor: float) -> None:
        """Handle zoom requests from mouse wheel."""
        new_scale = self.current_scale * zoom_factor
        new_scale = max(0.1, min(2.0, new_scale))  # Clamp to slider limits
        self.zoom_slider.setValue(int(new_scale * 100))

    def _handle_zoom(self) -> None:
        """Handle zoom slider value changes with debouncing."""
        self.pending_scale = self.zoom_slider.value() / 100
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

    def _set_scroll_position(self, x: int, y: int) -> None:
        """Set scroll position with boundary checking.

        Args:
            x: Horizontal scroll position.
            y: Vertical scroll position.
        """
        h_bar = self.scroll_area.horizontalScrollBar()
        v_bar = self.scroll_area.verticalScrollBar()

        # Ensure values are within valid range
        x = max(0, min(x, h_bar.maximum()))
        y = max(0, min(y, v_bar.maximum()))

        h_bar.setValue(x)
        v_bar.setValue(y)

    def _update_map_image_display(self) -> None:
        """Update the displayed image with current scale while maintaining center point."""
        if not self.image_manager.original_pixmap:
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

        # Get scaled pixmap
        scaled_pixmap = self.image_manager.get_scaled_pixmap(self.current_scale)
        if scaled_pixmap:
            self.image_label.setPixmap(scaled_pixmap)

            # Calculate new scroll position based on relative position
            new_width = scaled_pixmap.width()
            new_height = scaled_pixmap.height()
            new_x = int(new_width * rel_x - viewport_width / 2)
            new_y = int(new_height * rel_y - viewport_height / 2)

            # Use a short delay to ensure the scroll area has updated its geometry
            QTimer.singleShot(1, lambda: self._set_scroll_position(new_x, new_y))

            # Update feature container size AND position to match new image size
            if hasattr(self, "feature_container"):
                # Use coordinate transformer to calculate centering offsets
                container_x, container_y = CoordinateTransformer.calculate_centering_offsets(
                    viewport_width, viewport_height, new_width, new_height
                )

                print(
                    f"Setting feature container: pos=({container_x}, {container_y}), size=({new_width}, {new_height})"
                )
                print(
                    f"Viewport size: {viewport_width}x{viewport_height}, Image size: {new_width}x{new_height}"
                )

                self.feature_container.setGeometry(
                    container_x, container_y, new_width, new_height
                )
                self.feature_container.raise_()

            # Update feature positions
            self.feature_manager.set_scale(self.current_scale)
            self.feature_manager.update_positions(self)

            # Update drawing_decap manager for any active drawing_decap
            self.drawing_manager.update_scale(self.current_scale)

    # Mode Management Methods
    def toggle_pin_placement(self, active: bool) -> None:
        """Toggle pin placement mode."""
        self.pin_placement_active = active

        if active:
            self.image_label.set_cursor_for_mode("crosshair")
            self.pin_toggle_btn.setStyleSheet("background: white")
        else:
            self.image_label.set_cursor_for_mode("default")
            self.pin_toggle_btn.setStyleSheet("background: grey")

        self.pin_mode_toggled.emit(active)

    def toggle_line_drawing(self, active: bool) -> None:
        """Toggle line drawing_decap mode."""
        self.line_drawing_active = active

        if active:
            # Disable other modes
            if self.pin_toggle_btn.isChecked():
                self.pin_toggle_btn.setChecked(False)

            self.drawing_manager.start_line_drawing()
            self.image_label.set_cursor_for_mode("crosshair")
            self.line_toggle_btn.setStyleSheet("background-color: #83A00E;")
            self.image_label.setFocus()
        else:
            # Complete or cancel current drawing_decap
            completing = self.drawing_manager.can_complete_line()
            self.drawing_manager.stop_line_drawing(complete=completing)

            self.image_label.set_cursor_for_mode("default")
            self.line_toggle_btn.setStyleSheet("")

    def toggle_branching_line_drawing(self, active: bool) -> None:
        """Toggle branching line drawing_decap mode."""
        self.branching_line_drawing_active = active

        if active:
            # Disable other modes
            if self.pin_toggle_btn.isChecked():
                self.pin_toggle_btn.setChecked(False)
            if self.line_toggle_btn.isChecked():
                self.line_toggle_btn.setChecked(False)
            if self.edit_toggle_btn.isChecked():
                self.edit_toggle_btn.setChecked(False)

            self.drawing_manager.start_branching_line_drawing()
            self.image_label.set_cursor_for_mode("crosshair")
            self.branching_line_toggle_btn.setStyleSheet("background-color: #83A00E;")
            self.image_label.setFocus()
            print(f"Branching line mode activated: {active}")
        else:
            # Complete or cancel current drawing_decap
            completing = self.drawing_manager._can_complete_branching_line()
            self.drawing_manager.stop_branching_line_drawing(complete=completing)

            self.image_label.set_cursor_for_mode("default")
            self.branching_line_toggle_btn.setStyleSheet("")
            print(f"Branching line mode deactivated: {active}")

    def toggle_edit_mode(self, active: bool) -> None:
        """Toggle edit mode for existing lines."""
        self.edit_mode_active = active
        logger.info(f"Toggle edit mode: {active}")

        if active:
            # Disable other modes
            if self.pin_toggle_btn.isChecked():
                self.pin_toggle_btn.setChecked(False)
            if self.line_toggle_btn.isChecked():
                self.line_toggle_btn.setChecked(False)

            self.image_label.set_cursor_for_mode("pointing")
            self.edit_toggle_btn.setStyleSheet("background-color: #FFA500;")

            # Set edit mode on feature manager
            self.feature_manager.set_edit_mode(True)
            logger.info("Edit mode activated on feature manager")
        else:
            self.image_label.set_cursor_for_mode("default")
            self.edit_toggle_btn.setStyleSheet("")

            # Disable edit mode on feature manager
            self.feature_manager.set_edit_mode(False)
            logger.info("Edit mode deactivated on feature manager")

    # Event Handling Methods
    def _handle_coordinate_click(self, x: int, y: int) -> None:
        """Handle clicks at specific coordinates."""
        if self.pin_placement_active:
            self._handle_pin_placement(x, y)
        elif self.line_drawing_active:
            self._handle_line_point_add(x, y)
        elif self.branching_line_drawing_active:
            self._handle_branching_line_point_add(x, y)

    def _handle_pin_placement(self, x: int, y: int) -> None:
        """Handle pin placement at specified coordinates."""
        dialog = PinPlacementDialog(x, y, self, self.controller)
        dialog.setWindowModality(Qt.WindowModality.ApplicationModal)

        if dialog.exec():
            target_node = dialog.get_target_node()
            if target_node:
                # Create relationship data using WKT format
                wkt_point = GeometryHandler.create_point(x, y)
                properties = GeometryHandler.create_geometry_properties(wkt_point)

                self.pin_created.emit(target_node, ">", properties)
                self.feature_manager.create_pin(target_node, x, y)

                # Exit pin placement mode
                self.pin_toggle_btn.setChecked(False)

    def _handle_line_point_add(self, x: int, y: int) -> None:
        """Handle adding a point to the current line being drawn."""
        # Convert to scaled coordinates for display
        scaled_x = x * self.current_scale
        scaled_y = y * self.current_scale

        self.drawing_manager.add_point(x, y, scaled_x, scaled_y)

    def _handle_line_completion(self, points: List[Tuple[int, int]]) -> None:
        """Handle completion of line drawing_decap."""

        print(f"_handle_line_completion called with {len(points)} points")

        if len(points) < 2:
            logger.warning("Attempted to complete line with insufficient points")
            print("Line has insufficient points, aborting")
            return

        dialog = LineFeatureDialog(points, self, self.controller)
        if dialog.exec():
            target_node = dialog.get_target_node()
            line_style = dialog.get_line_style()
            print(
                f"Dialog accepted with target_node: {target_node}, style: {line_style}"
            )

            try:
                # Create WKT LineString
                wkt_line = GeometryHandler.create_line(points)
                properties = {
                    "geometry": wkt_line,
                    "geometry_type": "LineString",
                    "style_color": line_style["color"],
                    "style_width": line_style["width"],
                    "style_pattern": line_style["pattern"],
                }
                print(f"Created properties: {properties}")

                # Create the line and emit signals
                print(f"About to emit line_created signal")
                self.line_created.emit(target_node, ">", properties)
                print(f"line_created signal emitted")

                # Create visual representation
                print(f"Creating visual line representation")
                self.feature_manager.create_line(target_node, points, line_style)
                print(f"Visual line created")

                # Exit line drawing_decap mode
                self.line_toggle_btn.blockSignals(True)
                self.line_toggle_btn.setChecked(False)
                self.line_toggle_btn.blockSignals(False)
                self.line_drawing_active = False

                logger.debug(f"Line created successfully: {target_node}")
                print(f"Line creation process completed")

            except Exception as e:
                logger.error(f"Error creating line: {e}")
                print(f"Exception during line creation: {e}")
                import traceback

                print(traceback.format_exc())

    def _handle_branching_line_point_add(self, x: int, y: int) -> None:
        """Handle adding a point to the current branching line being drawn."""
        # Convert to scaled coordinates for display
        scaled_x = x * self.current_scale
        scaled_y = y * self.current_scale

        self.drawing_manager.add_branching_point(x, y, scaled_x, scaled_y)
        print(f"Branching line point added at: ({x}, {y})")

    def _handle_branching_line_completion(
        self, branches: List[List[Tuple[int, int]]]
    ) -> None:
        """Handle completion of branching line drawing.

        Args:
            branches: List of branches, each branch is a list of points
        """
        logger.info(
            f"_handle_branching_line_completion called with {len(branches)} branches"
        )

        if not branches or all(len(branch) < 2 for branch in branches):
            logger.warning(
                "Attempted to complete branching line with insufficient points"
            )
            return

        # Use branching line feature dialog
        dialog = BranchingLineFeatureDialog(branches, self, self.controller)
        if dialog.exec():
            target_node = dialog.get_target_node()
            line_style = dialog.get_line_style()

            try:
                # Create WKT MultiLineString
                wkt_multiline = GeometryHandler.create_multi_line(branches)

                logger.info(f"Created WKT MultiLineString for {target_node}")

                properties = {
                    "geometry": wkt_multiline,
                    "geometry_type": "MultiLineString",
                    "branch_count": len(branches),
                    "style_color": line_style["color"],
                    "style_width": line_style["width"],
                    "style_pattern": line_style["pattern"],
                }

                # Store geometry in database
                if self.controller:
                    self.controller._handle_line_created(target_node, ">", properties)

                # Create visual representation using the unified feature manager
                self.feature_manager.create_branching_line(
                    target_node, branches, line_style
                )

                # Exit branching line drawing mode
                self.branching_line_toggle_btn.blockSignals(True)
                self.branching_line_toggle_btn.setChecked(False)
                self.branching_line_toggle_btn.blockSignals(False)
                self.branching_line_drawing_active = False

            except Exception as e:
                logger.error(f"Error creating branching line: {e}")
                import traceback

                logger.error(traceback.format_exc())

    def _handle_drawing_update(self) -> None:
        """Handle updates to drawing_decap state."""
        self.image_label.update()  # Trigger repaint for temporary drawing_decap of lines
        self.update()  # Trigger repaint for temporary drawing_decap

    def _handle_feature_click(self, target_node: str) -> None:
        """Handle clicks on features."""
        self.pin_clicked.emit(target_node)

    def handle_viewport_key_press(self, event: QKeyEvent) -> None:
        """Handle key press events from the viewport."""
        # For B key in branching line mode, get current mouse position
        if event.key() == Qt.Key.Key_B and self.branching_line_drawing_active:
            # Get current mouse position relative to viewport
            mouse_pos = self.image_label.mapFromGlobal(QCursor.pos())

            # Convert to original coordinates using coordinate transformer
            pixmap = self.image_label.pixmap()
            if pixmap:
                original_pixmap = None
                current_scale = self.current_scale
                
                if (hasattr(self, "image_manager") and 
                    self.image_manager.original_pixmap):
                    original_pixmap = self.image_manager.original_pixmap
                
                coordinates = CoordinateTransformer.widget_to_original_coordinates(
                    mouse_pos, pixmap, 
                    self.image_label.width(), self.image_label.height(),
                    original_pixmap, current_scale
                )
                
                if coordinates:
                    original_x, original_y = coordinates
                    # Also get scaled coordinates
                    scaled_x = original_x * self.current_scale
                    scaled_y = original_y * self.current_scale

                    # Call a new method on drawing_decap manager with these coordinates
                    if self.drawing_manager.start_branch_from_position(
                        original_x, original_y, scaled_x, scaled_y
                    ):
                        return

        # Try normal key handling in drawing_decap manager
        if self.drawing_manager.handle_key_press(event.key()):
            # Drawing manager handled the key
            return

        # Handle mode-specific keys
        if event.key() == Qt.Key.Key_Escape:
            if self.pin_placement_active:
                self.pin_toggle_btn.setChecked(False)
            elif self.line_drawing_active:
                self.line_toggle_btn.setChecked(False)
            elif self.edit_mode_active:
                self.edit_toggle_btn.setChecked(False)

    # Feature Loading Methods
    def load_features(self) -> None:
        """Load all spatial features from the database."""
        if not self.controller or not self.controller.ui.relationships_table:
            return

        # Collect feature data from relationships table
        pin_data = []
        simple_line_data = []
        branching_line_data = {}

        relationships_table = self.controller.ui.relationships_table
        logger.info(
            f"Loading features from {relationships_table.rowCount()} relationships"
        )

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
                    continue

                if not GeometryHandler.validate_wkt(properties["geometry"]):
                    continue

                geometry_type = properties.get(
                    "geometry_type",
                    GeometryHandler.get_geometry_type(properties["geometry"]),
                )
                target_node = self._extract_target_node(
                    target_item, relationships_table, row
                )

                style_config = {
                    "color": properties.get("style_color", "#FF0000"),
                    "width": properties.get("style_width", 2),
                    "pattern": properties.get("style_pattern", "solid"),
                }

                if geometry_type == "MultiLineString":
                    # Handle as branching line
                    branches = GeometryHandler.get_coordinates(properties["geometry"])
                    logger.info(
                        f"Found MultiLineString for {target_node} with {len(branches)} branches"
                    )

                    if target_node not in branching_line_data:
                        branching_line_data[target_node] = {
                            "branches": [],
                            "style": style_config,
                        }

                    branching_line_data[target_node]["branches"] = branches

                elif geometry_type == "LineString":
                    # Handle as simple line
                    points = GeometryHandler.get_coordinates(properties["geometry"])
                    simple_line_data.append((target_node, points, style_config))

                elif geometry_type == "Point":
                    # Handle pins
                    x, y = GeometryHandler.get_coordinates(properties["geometry"])
                    pin_data.append((target_node, x, y))

            except Exception as e:
                logger.error(f"Error loading spatial feature: {e}")
                continue

        # Clear existing features
        self.feature_manager.clear_all_features()

        # Create features using the unified manager
        if pin_data:
            logger.info(f"Creating {len(pin_data)} pins")
            self.feature_manager.batch_create_pins(pin_data)

        if simple_line_data:
            logger.info(f"Creating {len(simple_line_data)} simple lines")
            self.feature_manager.batch_create_lines(simple_line_data)

        if branching_line_data:
            logger.info(f"Creating {len(branching_line_data)} branching lines")
            self.feature_manager.batch_create_branching_lines(branching_line_data)

    def _extract_target_node(self, target_item, relationships_table, row) -> str:
        """Extract target node name from table item."""
        if hasattr(target_item, "text"):
            return target_item.text()
        else:
            target_widget = relationships_table.cellWidget(row, 1)
            if hasattr(target_widget, "text"):
                return target_widget.text()
        return ""

    # File Operations
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

    # Utility Methods
    def get_map_image_path(self) -> Optional[str]:
        """Get the current map image path."""
        return self.map_image_path

    def get_feature_count(self) -> Dict[str, int]:
        """Get count of features by type."""
        return self.feature_manager.get_feature_count()
