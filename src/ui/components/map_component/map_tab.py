from typing import Optional, List, Tuple, Dict

from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QEvent
from PyQt6.QtGui import QKeyEvent, QPainter
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QScrollArea,
    QFileDialog,
)
from structlog import get_logger

from .drawing_manager import DrawingManager
from .map_image_loader import ImageManager
from .map_viewport import MapViewport
from .utils.coordinate_transformer import CoordinateTransformer
from .map_toolbar_manager import MapToolbarManager
from .map_mode_manager import MapModeManager
from .map_coordinate_utilities import MapCoordinateUtilities
from .map_feature_loader import MapFeatureLoader
from .map_event_handler import MapEventHandler

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

        # Mode flags are now managed by mode_manager

        # Initialize separated components
        self._setup_components()
        self._setup_ui()
        self._connect_signals()

        # Enable mouse tracking on the MapTab itself
        self.setMouseTracking(True)

        # Install event filter to catch key presses
        self.installEventFilter(self)
        
        # Enable graphics mode (only mode available)
        self._enable_graphics_mode()

    def _setup_components(self) -> None:
        """Initialize all the separated component managers."""
        # Image management
        self.image_manager = ImageManager()

        # Drawing management
        self.drawing_manager = DrawingManager()

        # Toolbar management
        self.toolbar_manager = MapToolbarManager(self, self.controller)

        # Mode management
        self.mode_manager = MapModeManager(self, self.controller)

        # Coordinate utilities
        self.coord_utils = MapCoordinateUtilities(self)

        # Feature loading
        self.feature_loader = MapFeatureLoader(self, self.controller)

        # Event handling
        self.event_handler = MapEventHandler(self, self.controller)

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
        image_controls = self.toolbar_manager.create_image_controls()

        # Zoom controls
        zoom_controls = self.toolbar_manager.create_zoom_controls()

        # Create scrollable image area with viewport
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scroll_area.setMouseTracking(True)

        # Create viewport for map display
        self.image_label = MapViewport(self, config=self.config)

        # Graphics mode is now the only mode - widget system removed

        self.scroll_area.setWidget(self.image_label)
        
        # Install event filter only on image label to handle wheel events over the map
        # Don't install on scroll_area.viewport() to allow zoom slider to receive wheel events
        self.image_label.installEventFilter(self)

        # Add all components to layout
        layout.addLayout(image_controls)
        layout.addLayout(zoom_controls)
        layout.addWidget(self.scroll_area)

    # Properties to access toolbar elements
    @property
    def change_map_btn(self):
        return self.toolbar_manager.change_map_btn
    
    @property
    def clear_map_btn(self):
        return self.toolbar_manager.clear_map_btn
    
    @property
    def pin_toggle_btn(self):
        return self.toolbar_manager.pin_toggle_btn
    
    @property
    def line_toggle_btn(self):
        return self.toolbar_manager.line_toggle_btn
    
    @property
    def branching_line_toggle_btn(self):
        return self.toolbar_manager.branching_line_toggle_btn
    
    @property
    def edit_toggle_btn(self):
        return self.toolbar_manager.edit_toggle_btn
    
    @property
    def zoom_slider(self):
        return self.toolbar_manager.zoom_slider
    
    @property
    def reset_button(self):
        return self.toolbar_manager.reset_button

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

        # Graphics feature manager signals connected via adapter

        # Mode manager signals
        self.mode_manager.pin_mode_toggled.connect(self.pin_mode_toggled.emit)

        # Event handler signals
        self.event_handler.pin_created.connect(self.pin_created.emit)
        self.event_handler.line_created.connect(self.line_created.emit)
        self.event_handler.pin_clicked.connect(self.pin_clicked.emit)

        # Connect to controller if available (handled through event_handler now)

    def resizeEvent(self, event):
        """Handle resize events for graphics mode."""
        super().resizeEvent(event)
        # Graphics mode handles resizing automatically via QGraphicsView

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
        self.toolbar_manager.set_zoom_value(int(self.current_scale * 100))

        # Update display
        self._update_map_image_display()
        
        # Also load image in graphics adapter if available
        if hasattr(self, 'graphics_adapter') and self.map_image_path:
            self.graphics_adapter.load_image(self.map_image_path)
        
        self.load_features()

    def _on_image_error(self, error_msg: str) -> None:
        """Handle image loading errors."""
        if hasattr(self, 'graphics_adapter'):
            self.graphics_adapter.feature_manager.clear_all_features()
        self.image_label.setText(f"Error loading map image: {error_msg}")
        logger.error(f"Map image loading failed: {error_msg}")

    def _clear_image(self) -> None:
        """Clear the current image and features."""
        if hasattr(self, 'graphics_adapter'):
            self.graphics_adapter.feature_manager.clear_all_features()
        self.image_label.clear()
        self.image_label.setText("No map image set")

    # Zoom Management Methods
    def _handle_wheel_zoom(self, zoom_factor: float) -> None:
        """Handle zoom requests from mouse wheel."""
        new_scale = self.current_scale * zoom_factor
        # Clamp to match slider limits (10% to 500%)
        new_scale = max(0.1, min(5.0, new_scale))
        new_zoom_percentage = int(new_scale * 100)
        self.toolbar_manager.set_zoom_value(new_zoom_percentage)

    def _handle_zoom(self) -> None:
        """Handle zoom slider value changes with debouncing."""
        new_scale = self.toolbar_manager.zoom_slider.value() / 100
        self.pending_scale = new_scale
        self.zoom_timer.start(10)  # 10ms debounce

    def _perform_zoom(self) -> None:
        """Actually perform the zoom operation after debounce."""
        if self.pending_scale is not None:
            old_scale = self.current_scale
            self.current_scale = self.pending_scale
            self._update_map_image_display()
            self.pending_scale = None

    def _reset_zoom(self) -> None:
        """Reset zoom to 100%."""
        self.toolbar_manager.set_zoom_value(100)

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

            # Graphics mode handles feature positioning automatically

            # Update drawing_decap manager for any active drawing_decap
            self.drawing_manager.update_scale(self.current_scale)

    # Mode Management Methods (delegated to mode_manager)
    def toggle_pin_placement(self, active: bool) -> None:
        """Toggle pin placement mode."""
        self.mode_manager.toggle_pin_placement(active)

    def toggle_line_drawing(self, active: bool) -> None:
        """Toggle line drawing mode."""
        self.mode_manager.toggle_line_drawing(active)

    def toggle_branching_line_drawing(self, active: bool) -> None:
        """Toggle branching line drawing mode."""
        self.mode_manager.toggle_branching_line_drawing(active)

    def toggle_edit_mode(self, active: bool) -> None:
        """Toggle edit mode for existing lines."""
        self.mode_manager.toggle_edit_mode(active)

    # Mode state properties (delegated to mode_manager)
    @property
    def pin_placement_active(self) -> bool:
        return self.mode_manager.pin_placement_active

    @property
    def line_drawing_active(self) -> bool:
        return self.mode_manager.line_drawing_active

    @property
    def branching_line_drawing_active(self) -> bool:
        return self.mode_manager.branching_line_drawing_active

    @property
    def edit_mode_active(self) -> bool:
        return self.mode_manager.edit_mode_active

    @property
    def branch_creation_mode(self) -> bool:
        return self.mode_manager.branch_creation_mode
    
    @branch_creation_mode.setter
    def branch_creation_mode(self, active: bool) -> None:
        self.mode_manager.branch_creation_mode = active
    
    @property
    def _branch_creation_start_point(self) -> Optional[tuple]:
        """Get the branch creation start point from mode manager."""
        return self.mode_manager.get_branch_creation_start_point()
    
    @_branch_creation_start_point.setter
    def _branch_creation_start_point(self, point: tuple) -> None:
        """Set the branch creation start point via mode manager."""
        self.mode_manager.set_branch_creation_start_point(point)
    
    @property
    def _branch_creation_target(self) -> Optional[str]:
        """Get the branch creation target from mode manager."""
        return self.mode_manager.get_branch_creation_target()
    
    @_branch_creation_target.setter
    def _branch_creation_target(self, target: str) -> None:
        """Set the branch creation target via mode manager."""
        self.mode_manager.set_branch_creation_target(target)
    
    @property
    def _branch_creation_point_indices(self) -> Optional[tuple]:
        """Get the branch creation point indices from mode manager."""
        return self.mode_manager.get_branch_creation_point_indices()
    
    @_branch_creation_point_indices.setter
    def _branch_creation_point_indices(self, indices: tuple) -> None:
        """Set the branch creation point indices via mode manager."""
        self.mode_manager.set_branch_creation_point_indices(indices)

    # Event Handling Methods (delegated to event_handler)
    def _handle_coordinate_click(self, x: int, y: int) -> None:
        """Handle clicks at specific coordinates."""
        self.event_handler.handle_coordinate_click(x, y)

    def _handle_line_completion(self, points: List[Tuple[int, int]]) -> None:
        """Handle completion of line drawing."""
        self.event_handler.handle_line_completion(points)

    def _handle_branching_line_completion(
        self, branches: List[List[Tuple[int, int]]]
    ) -> None:
        """Handle completion of branching line drawing."""
        self.event_handler.handle_branching_line_completion(branches)

    def _handle_drawing_update(self) -> None:
        """Handle updates to drawing state."""
        self.event_handler.handle_drawing_update()

    def _handle_feature_click(self, target_node: str) -> None:
        """Handle clicks on features."""
        self.event_handler.handle_feature_click(target_node)

    def handle_viewport_key_press(self, event: QKeyEvent) -> None:
        """Handle key press events from the viewport."""
        self.event_handler.handle_viewport_key_press(event)

    # Feature Loading Methods (delegated to feature_loader)
    def load_features(self) -> None:
        """Load all spatial features from the database."""
        self.feature_loader.load_features()

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
        """Handle branch creation request at specified coordinates."""
        return self.event_handler.handle_branch_creation_request(x, y)

    def _find_nearest_line_at_position(self, x: int, y: int) -> Optional[str]:
        """Find the nearest line container to the specified position."""
        return self.coord_utils.find_nearest_line_at_position(x, y)

    def _find_nearest_control_point(
        self, scaled_x: float, scaled_y: float
    ) -> Optional[Tuple[str, int, int, Tuple[int, int]]]:
        """Find the nearest control point to the specified position."""
        return self.coord_utils.find_nearest_control_point(scaled_x, scaled_y)

    def _point_to_line_distance(
        self,
        point: Tuple[float, float],
        line_start: Tuple[int, int],
        line_end: Tuple[int, int],
    ) -> float:
        """Calculate distance from point to line segment."""
        return self.coord_utils.point_to_line_distance(point, line_start, line_end)

    def eventFilter(self, obj, event):
        """Event filter to catch key presses and wheel events."""
        # Handle wheel events on image label (graphics mode handles its own events)
        if event.type() == QEvent.Type.Wheel:
            if obj == self.image_label:
                # Let the image label handle its own wheel event normally
                return False
        
        # Handle key press events
        if event.type() == QEvent.Type.KeyPress:

            # Check for the 'b' key (ASCII 66 for 'B', 98 for 'b')
            if (
                event.key() == 66 or event.key() == 98
            ):  # Use literal values for reliability
                if self.edit_mode_active:
                    self._handle_b_key_press()
                    return True  # Event handled

        # Pass event to default handler
        return super().eventFilter(obj, event)

    def _handle_b_key_press(self) -> None:
        """Handle B key press for branch creation - delegates to event handler."""
        if hasattr(self, 'event_handler'):
            self.event_handler._handle_b_key_press()
    
    def _reset_branch_creation_mode(self) -> None:
        """Reset branch creation mode state."""
        self.mode_manager.reset_branch_creation_mode()

    # Utility Methods
    def get_map_image_path(self) -> Optional[str]:
        """Get the current map image path."""
        return self.map_image_path

    def get_feature_count(self) -> Dict[str, int]:
        """Get count of features by type."""
        if hasattr(self, 'graphics_adapter'):
            return self.graphics_adapter.feature_manager.get_feature_count()
        return {}

    def _complete_branch_creation(self, end_x: int, end_y: int) -> None:
        """Complete branch creation with the specified end point."""
        self.event_handler._complete_branch_creation(end_x, end_y)
    
    # Graphics Mode Integration (Phase 1 Migration)
    def enable_graphics_mode(self) -> None:
        """Enable experimental graphics mode using QGraphicsView.
        
        This is part of the migration from widget-based to graphics-based
        map rendering. When enabled, it replaces the QLabel viewport with
        a QGraphicsView implementation.
        """
        try:
            # Import here to make it optional
            from .graphics import MapTabGraphicsAdapter
            
            # Create adapter if not already created
            if not hasattr(self, 'graphics_adapter'):
                self.graphics_adapter = MapTabGraphicsAdapter(self, self.config)
                
                # Connect adapter signals to existing signals
                self.graphics_adapter.pin_clicked.connect(self.pin_clicked.emit)
                self.graphics_adapter.line_created.connect(self.line_created.emit)
                self.graphics_adapter.map_image_changed.connect(self.map_image_changed.emit)
                
                logger.info("Graphics adapter created")
            
            # Enable graphics mode
            self.graphics_adapter.enable_migration()
            
            # Load current image if any
            if self.map_image_path:
                self.graphics_adapter.load_image(self.map_image_path)
            
            logger.info("Graphics mode enabled")
            
        except Exception as e:
            logger.error(f"Failed to enable graphics mode: {e}")
    
    def disable_graphics_mode(self) -> None:
        """Graphics mode is now the only mode - this method is deprecated."""
        logger.warning("disable_graphics_mode called but graphics mode is now the only mode")
    
    def is_graphics_mode(self) -> bool:
        """Check if graphics mode is currently enabled.
        
        Returns:
            True if graphics mode is active
        """
        return hasattr(self, 'graphics_adapter') and self.graphics_adapter.is_graphics_mode()
    
    def _enable_graphics_mode(self) -> None:
        """Enable graphics mode (only mode available)."""
        try:
            self.enable_graphics_mode()
            if hasattr(self, 'graphics_adapter'):
                logger.info("Graphics mode enabled for MapTab successfully")
            else:
                logger.error("Graphics mode failed - no adapter created")
                raise RuntimeError("Graphics adapter was not created")
        except Exception as e:
            logger.error(f"Failed to enable graphics mode: {e}")
            raise RuntimeError("Graphics mode is required but failed to initialize")
