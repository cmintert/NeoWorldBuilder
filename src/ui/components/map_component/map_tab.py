import json
from typing import Optional, List, Tuple, Dict

from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QKeyEvent, QCursor
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
from ui.components.map_component.dialogs.line_feature_dialog import LineFeatureDialog
from ui.components.map_component.dialogs.branching_line_feature_dialog import BranchingLineFeatureDialog
from .map_image_loader import ImageManager
from .map_viewport import MapViewport
from ui.components.map_component.dialogs.pin_placement_dialog import PinPlacementDialog
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
        self.branch_creation_mode = False

        # Initialize separated components
        self._setup_components()
        self._setup_ui()
        self._connect_signals()
        
        # Enable mouse tracking on the MapTab itself
        self.setMouseTracking(True)
        
        # Install event filter to catch key presses
        self.installEventFilter(self)

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
        self.scroll_area.setMouseTracking(True)

        # Create viewport for map display
        self.image_label = MapViewport(self, config=self.config)

        # Create feature container and manager
        self.feature_container = QWidget(self.image_label)
        self.feature_container.setGeometry(
            0, 0, self.image_label.width(), self.image_label.height()
        )
        self.feature_container.setMouseTracking(True)

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
            
            # Set focus to the viewport so it can receive key events
            self.image_label.setFocus()
            logger.info("Set focus to viewport for key events")
        else:
            self.image_label.set_cursor_for_mode("default")
            self.edit_toggle_btn.setStyleSheet("")

            # Disable edit mode on feature manager
            self.feature_manager.set_edit_mode(False)
            logger.info("Edit mode deactivated on feature manager")

    # Event Handling Methods
    def _handle_coordinate_click(self, x: int, y: int) -> None:
        """Handle clicks at specific coordinates."""
        if self.branch_creation_mode:
            self._complete_branch_creation(x, y)
        elif self.pin_placement_active:
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
        key_value = event.key()
        logger.info(f"Key press event received: {key_value}")
        
        # Debug log of key values for reference
        logger.info(f"Key_B value: {int(Qt.Key.Key_B)}")
        
        # Check for the 'b' key (ASCII 66 for 'B', 98 for 'b')
        if key_value == 66 or key_value == 98:  # Use literal values for reliability
            logger.info("B key pressed - starting branch creation process")
            # Get current mouse position relative to viewport
            mouse_pos = self.image_label.mapFromGlobal(QCursor.pos())

            # Convert to original coordinates using coordinate transformer
            pixmap = self.image_label.pixmap()
            if pixmap:
                logger.info(f"Pixmap found: {pixmap.width()}x{pixmap.height()}")
                original_pixmap = None
                current_scale = self.current_scale
                
                if (hasattr(self, "image_manager") and 
                    self.image_manager.original_pixmap):
                    original_pixmap = self.image_manager.original_pixmap
                    logger.info(f"Original pixmap found: {original_pixmap.width()}x{original_pixmap.height()}")
                else:
                    logger.warning("No original pixmap found")
                
                coordinates = CoordinateTransformer.widget_to_original_coordinates(
                    mouse_pos, pixmap, 
                    self.image_label.width(), self.image_label.height(),
                    original_pixmap, current_scale
                )
                
                if coordinates:
                    original_x, original_y = coordinates
                    logger.info(f"Converted to original coordinates: ({original_x}, {original_y})")
                    # Also get scaled coordinates
                    scaled_x = original_x * self.current_scale
                    scaled_y = original_y * self.current_scale
                    logger.info(f"Scaled coordinates: ({scaled_x}, {scaled_y})")

                    # Handle different modes
                    if self.branching_line_drawing_active:
                        logger.info("In branching line drawing mode - using drawing manager")
                        # For branching line mode, use existing drawing manager logic
                        if self.drawing_manager.start_branch_from_position(
                            original_x, original_y, scaled_x, scaled_y
                        ):
                            logger.info("Branch creation started in drawing manager")
                            return
                        else:
                            logger.warning("Drawing manager failed to start branch creation")
                    elif self.edit_mode_active:
                        logger.info("In edit mode - looking for nearest control point")
                        # For edit mode, find the nearest control point and trigger branch creation
                        nearest_info = self._find_nearest_control_point(scaled_x, scaled_y)
                        if nearest_info:
                            target_node, branch_idx, point_idx, point = nearest_info
                            logger.info(f"Found nearest control point: {target_node}, branch {branch_idx}, point {point_idx}")
                            
                            # Store information about selected point for highlighting
                            self.branch_creation_mode = True
                            self._branch_creation_target = target_node
                            self._branch_creation_start_point = point
                            self._branch_creation_point_indices = (branch_idx, point_idx)
                            
                            # Set cursor to indicate branch creation mode
                            self.image_label.set_cursor_for_mode("crosshair")
                            logger.info("Branch creation mode activated with highlighted point")
                            
                            # Force redraw to highlight the selected point
                            self.feature_manager.update_positions(self)
                            return
                        else:
                            logger.warning("No suitable control point found, trying line-based selection")
                            # Fallback to line-based selection if no control point found
                            if self._handle_branch_creation_request(original_x, original_y):
                                logger.info("Branch creation started from line segment")
                                return
                            else:
                                logger.warning("Failed to find any suitable branch creation point")
                    else:
                        logger.info(f"Not in a suitable mode for branch creation: edit_mode={self.edit_mode_active}, branching_line_drawing={self.branching_line_drawing_active}")
                else:
                    logger.warning("Failed to convert to original coordinates")
            else:
                logger.warning("No pixmap found in image label")

        # Try normal key handling in drawing_decap manager
        if self.drawing_manager.handle_key_press(event.key()):
            # Drawing manager handled the key
            logger.info(f"Key {event.key()} handled by drawing manager")
            return

        # Handle mode-specific keys
        if event.key() == Qt.Key.Key_Escape:
            if self.branch_creation_mode:
                logger.info("Escape pressed - exiting branch creation mode")
                self._reset_branch_creation_mode()
            elif self.pin_placement_active:
                logger.info("Escape pressed - exiting pin placement mode")
                self.pin_toggle_btn.setChecked(False)
            elif self.line_drawing_active:
                logger.info("Escape pressed - exiting line drawing mode")
                self.line_toggle_btn.setChecked(False)
            elif self.edit_mode_active:
                logger.info("Escape pressed - exiting edit mode")
                self.edit_toggle_btn.setChecked(False)
            logger.info(f"Mouse position: {mouse_pos.x()}, {mouse_pos.y()}")

            # Convert to original coordinates using coordinate transformer
            pixmap = self.image_label.pixmap()
            if pixmap:
                logger.info(f"Pixmap found: {pixmap.width()}x{pixmap.height()}")
                original_pixmap = None
                current_scale = self.current_scale
                
                if (hasattr(self, "image_manager") and 
                    self.image_manager.original_pixmap):
                    original_pixmap = self.image_manager.original_pixmap
                    logger.info(f"Original pixmap found: {original_pixmap.width()}x{original_pixmap.height()}")
                else:
                    logger.warning("No original pixmap found")
                
                coordinates = CoordinateTransformer.widget_to_original_coordinates(
                    mouse_pos, pixmap, 
                    self.image_label.width(), self.image_label.height(),
                    original_pixmap, current_scale
                )
                
                if coordinates:
                    original_x, original_y = coordinates
                    logger.info(f"Converted to original coordinates: ({original_x}, {original_y})")
                    # Also get scaled coordinates
                    scaled_x = original_x * self.current_scale
                    scaled_y = original_y * self.current_scale
                    logger.info(f"Scaled coordinates: ({scaled_x}, {scaled_y})")

                    # Handle different modes
                    if self.branching_line_drawing_active:
                        logger.info("In branching line drawing mode - using drawing manager")
                        # For branching line mode, use existing drawing manager logic
                        if self.drawing_manager.start_branch_from_position(
                            original_x, original_y, scaled_x, scaled_y
                        ):
                            logger.info("Branch creation started in drawing manager")
                            return
                        else:
                            logger.warning("Drawing manager failed to start branch creation")
                    elif self.edit_mode_active:
                        logger.info("In edit mode - looking for nearest control point")
                        # For edit mode, find the nearest control point and trigger branch creation
                        nearest_info = self._find_nearest_control_point(scaled_x, scaled_y)
                        if nearest_info:
                            target_node, branch_idx, point_idx, point = nearest_info
                            logger.info(f"Found nearest control point: {target_node}, branch {branch_idx}, point {point_idx}")
                            
                            # Store information about selected point for highlighting
                            self.branch_creation_mode = True
                            self._branch_creation_target = target_node
                            self._branch_creation_start_point = point
                            self._branch_creation_point_indices = (branch_idx, point_idx)
                            
                            # Set cursor to indicate branch creation mode
                            self.image_label.set_cursor_for_mode("crosshair")
                            logger.info("Branch creation mode activated with highlighted point")
                            
                            # Force redraw to highlight the selected point
                            self.feature_manager.update_positions(self)
                            return
                        else:
                            logger.warning("No suitable control point found, trying line-based selection")
                            # Fallback to line-based selection if no control point found
                            if self._handle_branch_creation_request(original_x, original_y):
                                logger.info("Branch creation started from line segment")
                                return
                            else:
                                logger.warning("Failed to find any suitable branch creation point")
                    else:
                        logger.info(f"Not in a suitable mode for branch creation: edit_mode={self.edit_mode_active}, branching_line_drawing={self.branching_line_drawing_active}")
                else:
                    logger.warning("Failed to convert to original coordinates")
            else:
                logger.warning("No pixmap found in image label")

        # Try normal key handling in drawing_decap manager
        if self.drawing_manager.handle_key_press(event.key()):
            # Drawing manager handled the key
            logger.info(f"Key {event.key()} handled by drawing manager")
            return

        # Handle mode-specific keys
        if event.key() == Qt.Key.Key_Escape:
            if self.branch_creation_mode:
                logger.info("Escape pressed - exiting branch creation mode")
                self._reset_branch_creation_mode()
            elif self.pin_placement_active:
                logger.info("Escape pressed - exiting pin placement mode")
                self.pin_toggle_btn.setChecked(False)
            elif self.line_drawing_active:
                logger.info("Escape pressed - exiting line drawing mode")
                self.line_toggle_btn.setChecked(False)
            elif self.edit_mode_active:
                logger.info("Escape pressed - exiting edit mode")
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

    def _handle_branch_creation_request(self, x: int, y: int) -> bool:
        """Handle branch creation request at specified coordinates.
        
        Args:
            x: X coordinate in original image space
            y: Y coordinate in original image space
            
        Returns:
            True if branch creation was initiated, False otherwise
        """
        logger.info(f"Handling branch creation request at ({x}, {y})")
        
        # Find the nearest line to the cursor position
        nearest_line = self._find_nearest_line_at_position(x, y)
        if nearest_line:
            logger.info(f"Found nearest line: {nearest_line}")
            
            # Start branch creation mode for this line
            self.branch_creation_mode = True
            self._branch_creation_target = nearest_line
            self._branch_creation_start_point = (x, y)
            
            # Set cursor to indicate branch creation mode
            self.image_label.set_cursor_for_mode("crosshair")
            
            logger.info(f"Started branch creation mode for line: {nearest_line}")
            return True
        else:
            logger.warning("No suitable line found for branch creation")
        
        return False
    
    def _find_nearest_line_at_position(self, x: int, y: int) -> Optional[str]:
        """Find the nearest line container to the specified position.
        
        Args:
            x: X coordinate in original image space
            y: Y coordinate in original image space
            
        Returns:
            Target node of nearest line, or None if no line found
        """
        print(f"Finding nearest line at position ({x}, {y})")
        
        # Get all line containers from feature manager
        line_containers = self.feature_manager.get_line_containers()
        
        if not line_containers:
            print("No line containers found")
            return None
        
        print(f"Found {len(line_containers)} line containers")
        
        nearest_line = None
        min_distance = float('inf')
        
        # Convert original coordinates to scaled for hit testing
        scaled_x = x * self.current_scale
        scaled_y = y * self.current_scale
        
        for target_node, line_container in line_containers.items():
            print(f"Checking line: {target_node}, type: {type(line_container)}")
            
            # Get line geometry and test for proximity
            if hasattr(line_container, 'geometry'):
                geometry = line_container.geometry
                print(f"Geometry found, type: {type(geometry)}")
                
                # Check if geometry has scaled_branches attribute
                if not hasattr(geometry, 'scaled_branches'):
                    print(f"ERROR: geometry has no scaled_branches attribute: {dir(geometry)}")
                    continue
                
                # Debug what scaled_branches is
                scaled_branches = geometry.scaled_branches
                print(f"scaled_branches type: {type(scaled_branches)}")
                
                # Test if point is near any branch of this line
                for branch in scaled_branches:
                    if len(branch) < 2:
                        continue
                    
                    for i in range(len(branch) - 1):
                        p1 = branch[i]
                        p2 = branch[i + 1]
                        
                        # Calculate distance to line segment
                        distance = self._point_to_line_distance(
                            (scaled_x, scaled_y), p1, p2
                        )
                        
                        if distance < min_distance:
                            min_distance = distance
                            nearest_line = target_node
        
        # Only return if within reasonable distance (e.g., 20 pixels)
        if min_distance <= 20:
            print(f"Found nearest line: {nearest_line} at distance {min_distance}")
            return nearest_line
        else:
            print(f"Nearest line too far away (distance: {min_distance})")
        
        return None
    
    def _find_nearest_control_point(self, scaled_x: float, scaled_y: float) -> Optional[Tuple[str, int, int, Tuple[int, int]]]:
        """Find the nearest control point to the specified position.
        
        Args:
            scaled_x: X coordinate in scaled image space
            scaled_y: Y coordinate in scaled image space
            
        Returns:
            Tuple of (target_node, branch_idx, point_idx, point) or None if no point found
        """
        print(f"Finding nearest control point to ({scaled_x}, {scaled_y})")
        
        # Get all line containers from feature manager
        line_containers = self.feature_manager.get_line_containers()
        
        if not line_containers:
            print("No line containers found")
            return None
        
        print(f"Found {len(line_containers)} line containers")
        
        nearest_info = None
        min_distance = float('inf')
        
        for target_node, line_container in line_containers.items():
            print(f"Checking line: {target_node}, type: {type(line_container)}")
            
            # Get line geometry
            if hasattr(line_container, 'geometry'):
                geometry = line_container.geometry
                print(f"Geometry found, type: {type(geometry)}")
                
                # Check if geometry has scaled_branches attribute
                if not hasattr(geometry, 'scaled_branches'):
                    print(f"ERROR: geometry has no scaled_branches attribute: {dir(geometry)}")
                    continue
                
                # Debug what scaled_branches is
                scaled_branches = geometry.scaled_branches
                print(f"scaled_branches type: {type(scaled_branches)}")
                
                # Test all control points in all branches
                for branch_idx, branch in enumerate(scaled_branches):
                    for point_idx, point in enumerate(branch):
                        # Calculate distance to control point
                        dx = scaled_x - point[0]
                        dy = scaled_y - point[1]
                        distance_sq = dx * dx + dy * dy
                        
                        if distance_sq < min_distance:
                            min_distance = distance_sq
                            # Store original point (not scaled)
                            original_point = geometry.branches[branch_idx][point_idx]
                            nearest_info = (target_node, branch_idx, point_idx, original_point)
        
        # Only return if within reasonable distance (e.g., 20 pixels squared)
        if min_distance <= 400:  # 20 pixels squared
            target_node, branch_idx, point_idx, point = nearest_info
            print(f"Found nearest point: {target_node}, branch {branch_idx}, point {point_idx} at distance {min_distance}")
            return nearest_info
        else:
            print(f"Nearest point too far away (distance: {min_distance})")
        
        return None
    
    def _point_to_line_distance(self, point: Tuple[float, float], 
                               line_start: Tuple[int, int], 
                               line_end: Tuple[int, int]) -> float:
        """Calculate distance from point to line segment."""
        px, py = point
        x1, y1 = line_start
        x2, y2 = line_end
        
        # Vector from line_start to line_end
        dx = x2 - x1
        dy = y2 - y1
        
        # If line segment has zero length
        if dx == 0 and dy == 0:
            return ((px - x1) ** 2 + (py - y1) ** 2) ** 0.5
        
        # Parameter t represents position along line segment (0 to 1)
        t = max(0, min(1, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))
        
        # Closest point on line segment
        closest_x = x1 + t * dx
        closest_y = y1 + t * dy
        
        # Distance from point to closest point on line
        return ((px - closest_x) ** 2 + (py - closest_y) ** 2) ** 0.5
    
    def eventFilter(self, obj, event):
        """Event filter to catch key presses globally."""
        if event.type() == 6:  # KeyPress event type
            print(f"*** GLOBAL EVENT FILTER - KeyPress caught: {event.key()} ***")
            
            # Check for the 'b' key (ASCII 66 for 'B', 98 for 'b')
            if event.key() == 66 or event.key() == 98:  # Use literal values for reliability
                print("B KEY DETECTED IN EVENT FILTER")
                if self.edit_mode_active:
                    print("EDIT MODE IS ACTIVE - HANDLING B KEY PRESS")
                    self._handle_b_key_press()
                    return True  # Event handled
            
        # Pass event to default handler
        return super().eventFilter(obj, event)
        
    def _handle_b_key_press(self):
        """Handle 'b' key press for branch creation."""
        print("*** HANDLING B KEY PRESS ***")
        
        # Get current mouse position
        mouse_pos = self.image_label.mapFromGlobal(QCursor.pos())
        print(f"Mouse position: {mouse_pos.x()}, {mouse_pos.y()}")
        
        # Convert to original coordinates
        pixmap = self.image_label.pixmap()
        if not pixmap:
            print("No pixmap available")
            return
            
        original_pixmap = None
        if hasattr(self, "image_manager") and self.image_manager.original_pixmap:
            original_pixmap = self.image_manager.original_pixmap
            
        coordinates = CoordinateTransformer.widget_to_original_coordinates(
            mouse_pos, pixmap, 
            self.image_label.width(), self.image_label.height(),
            original_pixmap, self.current_scale
        )
        
        if not coordinates:
            print("Failed to convert coordinates")
            return
            
        original_x, original_y = coordinates
        print(f"Original coordinates: {original_x}, {original_y}")
        
        # Calculate scaled coordinates
        scaled_x = original_x * self.current_scale
        scaled_y = original_y * self.current_scale
        
        # Get all line containers
        line_containers = self.feature_manager.get_line_containers()
        print(f"Found {len(line_containers)} line containers")
        
        # Find nearest control point or line segment
        if line_containers:
            # First try a quick approach - check for nearest point
            min_distance = float('inf')
            nearest_info = None
            
            for target_node, line_container in line_containers.items():
                print(f"Checking container: {target_node}, type: {type(line_container)}")
                
                # For branching lines, we need to access the _container attribute which has the actual LineContainer
                if hasattr(line_container, '_container'):
                    print(f"BranchingLineContainer found, accessing _container")
                    line_container = line_container._container
                
                # Make sure the container has a geometry attribute
                if not hasattr(line_container, 'geometry'):
                    print(f"Container {target_node} has no geometry attribute")
                    continue
                    
                geometry = line_container.geometry
                
                # Check if geometry has scaled_branches attribute
                if not hasattr(geometry, 'scaled_branches'):
                    print(f"ERROR: geometry has no scaled_branches attribute: {dir(geometry)}")
                    continue
                
                # Process each branch for points
                for branch_idx, branch in enumerate(geometry.scaled_branches):
                    for point_idx, point in enumerate(branch):
                        # Calculate distance to point
                        dx = scaled_x - point[0]
                        dy = scaled_y - point[1]
                        distance_sq = dx * dx + dy * dy
                        
                        if distance_sq < min_distance:
                            min_distance = distance_sq
                            # Get original point
                            original_point = geometry.branches[branch_idx][point_idx]
                            nearest_info = (target_node, branch_idx, point_idx, original_point, line_container)
            
            # If we found a point within reasonable distance (20 pixels squared = 400)
            if min_distance <= 400 and nearest_info:
                target_node, branch_idx, point_idx, point, line_container = nearest_info
                print(f"Found nearest point in {target_node}, branch {branch_idx}, point {point_idx}")
                
                # Set branch creation state
                self.branch_creation_mode = True
                self._branch_creation_target = target_node
                self._branch_creation_start_point = point
                self._branch_creation_point_indices = (branch_idx, point_idx)
                
                # Update cursor
                self.image_label.set_cursor_for_mode("crosshair")
                
                # Force redraw to highlight the selected point
                self.feature_manager.update_positions(self)
                print("Branch creation mode activated with highlighted point")
                return
            
            # If no point found, try line segments
            min_distance = float('inf')
            nearest_line = None
            nearest_position = None
            
            for target_node, line_container in line_containers.items():
                # For branching lines, access the actual LineContainer
                if hasattr(line_container, '_container'):
                    line_container = line_container._container
                
                if not hasattr(line_container, 'geometry'):
                    continue
                    
                geometry = line_container.geometry
                
                # Check if geometry has scaled_branches attribute
                if not hasattr(geometry, 'scaled_branches'):
                    continue
                
                # Process each branch for line segments
                for branch in geometry.scaled_branches:
                    if len(branch) < 2:
                        continue
                    
                    for i in range(len(branch) - 1):
                        p1 = branch[i]
                        p2 = branch[i + 1]
                        
                        # Calculate distance to line segment
                        distance = self._point_to_line_distance(
                            (scaled_x, scaled_y), p1, p2
                        )
                        
                        if distance < min_distance:
                            min_distance = distance
                            nearest_line = target_node
                            # Get original coordinates for the point
                            nearest_position = (
                                int(scaled_x / self.current_scale),
                                int(scaled_y / self.current_scale)
                            )
            
            # If we found a line within reasonable distance (20 pixels)
            if min_distance <= 20 and nearest_line and nearest_position:
                print(f"Found nearest line: {nearest_line}")
                
                # Set branch creation state
                self.branch_creation_mode = True
                self._branch_creation_target = nearest_line
                self._branch_creation_start_point = nearest_position
                
                # Update cursor
                self.image_label.set_cursor_for_mode("crosshair")
                
                print(f"Branch creation mode activated from line segment")
                return
        
        print("No suitable point or line found for branch creation")

    def _reset_branch_creation_mode(self) -> None:
        """Reset branch creation mode state."""
        logger.info("Resetting branch creation mode")
        self.branch_creation_mode = False
        if hasattr(self, '_branch_creation_target'):
            delattr(self, '_branch_creation_target')
        if hasattr(self, '_branch_creation_start_point'):
            delattr(self, '_branch_creation_start_point')
        if hasattr(self, '_branch_creation_point_indices'):
            delattr(self, '_branch_creation_point_indices')
        
        # Reset cursor
        if self.edit_mode_active:
            self.image_label.set_cursor_for_mode("pointing")
        else:
            self.image_label.set_cursor_for_mode("default")
            
        # Force redraw to remove any highlighted points
        self.feature_manager.update_positions(self)
        
        # Force viewport update to clear branch creation feedback
        self.image_label.update()
        
    # Utility Methods
    def get_map_image_path(self) -> Optional[str]:
        """Get the current map image path."""
        return self.map_image_path

    def get_feature_count(self) -> Dict[str, int]:
        """Get count of features by type."""
        return self.feature_manager.get_feature_count()
        
    def _complete_branch_creation(self, end_x: int, end_y: int) -> None:
        """Complete branch creation with the specified end point.
        
        Args:
            end_x: X coordinate of branch end point
            end_y: Y coordinate of branch end point
        """
        print(f"Completing branch creation: End point ({end_x}, {end_y})")
        logger.info(f"Completing branch creation: End point ({end_x}, {end_y})")
        
        if not self.branch_creation_mode:
            print("Not in branch creation mode")
            logger.warning("Not in branch creation mode")
            return
            
        if not hasattr(self, '_branch_creation_target'):
            print("No branch creation target set")
            logger.warning("No branch creation target set")
            return
            
        target_node = self._branch_creation_target
        
        if not hasattr(self, '_branch_creation_start_point'):
            print("No branch creation start point set")
            logger.warning("No branch creation start point set")
            return
            
        start_x, start_y = self._branch_creation_start_point
        print(f"Branch from ({start_x}, {start_y}) to ({end_x}, {end_y})")
        logger.info(f"Branch from ({start_x}, {start_y}) to ({end_x}, {end_y})")
        
        # Get the line container for the target
        line_containers = self.feature_manager.get_line_containers()
        if target_node in line_containers:
            line_container = line_containers[target_node]
            print(f"Found line container for {target_node}: {type(line_container)}")
            logger.info(f"Found line container for {target_node}: {type(line_container)}")
            
            # For branching lines, access the actual LineContainer
            if hasattr(line_container, '_container'):
                print("Using _container from BranchingLineContainer")
                logger.info("Using _container from BranchingLineContainer")
                line_container = line_container._container
            
            # Request branch creation from the line container
            if hasattr(line_container, 'create_branch_from_point'):
                print(f"Calling create_branch_from_point")
                logger.info(f"Calling create_branch_from_point")
                line_container.create_branch_from_point(
                    start_x, start_y, end_x, end_y
                )
                print("Branch created successfully")
                logger.info("Branch created successfully")
            else:
                print(f"Error: line_container has no create_branch_from_point method: {dir(line_container)}")
                logger.error(f"line_container has no create_branch_from_point method: {dir(line_container)}")
        else:
            print(f"Error: target_node {target_node} not found in line_containers")
            logger.error(f"target_node {target_node} not found in line_containers")
        
        # Reset branch creation mode
        print("Resetting branch creation mode")
        logger.info("Resetting branch creation mode")
        self._reset_branch_creation_mode()
        
        # Force an update of the viewport to clear the orange line
        self.image_label.update()
