from typing import Optional, Tuple

from PyQt6.QtCore import Qt, QObject, pyqtSignal
from PyQt6.QtGui import QKeyEvent, QCursor
from structlog import get_logger

from utils.geometry_handler import GeometryHandler
from ui.components.map_component.dialogs.pin_placement_dialog import PinPlacementDialog
from ui.components.map_component.dialogs.line_feature_dialog import LineFeatureDialog
from ui.components.map_component.dialogs.branching_line_feature_dialog import (
    BranchingLineFeatureDialog,
)

from .utils.coordinate_transformer import CoordinateTransformer

logger = get_logger(__name__)


class MapEventHandler(QObject):
    """Handles all event processing for the map component.

    Manages coordinate clicks, keyboard events, and user interactions
    with map features.
    """

    # Signals
    pin_created = pyqtSignal(str, str, dict)
    line_created = pyqtSignal(str, str, dict)
    pin_clicked = pyqtSignal(str)

    def __init__(self, parent_widget, controller=None):
        """Initialize the event handler.

        Args:
            parent_widget: The parent widget (MapTab instance)
            controller: Application controller
        """
        super().__init__()
        self.parent_widget = parent_widget
        self.controller = controller

    def handle_coordinate_click(self, x: int, y: int) -> None:
        """Handle clicks at specific coordinates."""
        if self.parent_widget.branch_creation_mode:
            self._complete_branch_creation(x, y)
        elif self.parent_widget.pin_placement_active:
            self._handle_pin_placement(x, y)
        elif self.parent_widget.line_drawing_active:
            self._handle_line_point_add(x, y)
        elif self.parent_widget.branching_line_drawing_active:
            self._handle_branching_line_point_add(x, y)

    def handle_viewport_key_press(self, event: QKeyEvent) -> None:
        """Handle key press events from the viewport."""
        key_value = event.key()
        logger.info(f"Key press event received: {key_value}")

        # Check for the 'b' key (ASCII 66 for 'B', 98 for 'b')
        if key_value == 66 or key_value == 98:  # Use literal values for reliability
            logger.info("B key pressed - starting branch creation process")
            self._handle_b_key_press()
            return

        # Try normal key handling in drawing manager
        if self.parent_widget.drawing_manager.handle_key_press(event.key()):
            # Drawing manager handled the key
            logger.info(f"Key {event.key()} handled by drawing manager")
            return

        # Handle mode-specific keys
        if event.key() == Qt.Key.Key_Escape:
            if self.parent_widget.mode_manager.handle_escape_key():
                return

    def _handle_b_key_press(self) -> None:
        """Handle B key press to start branch creation in edit mode."""
        logger.info("Handling B key press for branch creation")
        
        # Check if we're in edit mode
        if not self.parent_widget.edit_mode_active:
            logger.info("Not in edit mode, ignoring B key press")
            return
        
        # Get current mouse position - try graphics system first, then fall back to widget system
        coordinates = None
        
        if hasattr(self.parent_widget, 'graphics_adapter'):
            # Graphics system - get mouse position from graphics view
            try:
                graphics_view = self.parent_widget.graphics_adapter.graphics_view
                if hasattr(graphics_view, 'current_mouse_position'):
                    # Get the current mouse position in scene coordinates
                    scene_pos = graphics_view.current_mouse_position
                    # Convert scene coordinates to original coordinates
                    if hasattr(graphics_view.scene(), 'scene_to_original_coords'):
                        coordinates = graphics_view.scene().scene_to_original_coords(scene_pos)
                        logger.debug(f"Got coordinates from graphics system: {coordinates}")
                elif hasattr(graphics_view, 'mapFromGlobal') and hasattr(graphics_view, 'cursor'):
                    # Fallback - get global cursor position and map to view
                    from PyQt6.QtGui import QCursor
                    global_pos = QCursor.pos()
                    view_pos = graphics_view.mapFromGlobal(global_pos)
                    scene_pos = graphics_view.mapToScene(view_pos)
                    if hasattr(graphics_view.scene(), 'scene_to_original_coords'):
                        coordinates = graphics_view.scene().scene_to_original_coords(scene_pos)
                        logger.debug(f"Got coordinates from global cursor position: {coordinates}")
            except Exception as e:
                logger.warning(f"Failed to get mouse position from graphics system: {e}")
        
        # Fallback to widget system if graphics system failed
        if not coordinates and hasattr(self.parent_widget, 'image_label') and hasattr(self.parent_widget.image_label, 'current_mouse_pos'):
            mouse_pos = self.parent_widget.image_label.current_mouse_pos
            # Convert widget coordinates to original coordinates
            coordinates = self.parent_widget.image_label._get_original_coordinates(mouse_pos)
            logger.debug(f"Got coordinates from widget system: {coordinates}")
        
        if coordinates:
            x, y = coordinates
            logger.info(f"Starting branch creation at coordinates: ({x}, {y})")
            
            # Use the existing branch creation request handler
            if self.handle_branch_creation_request(x, y):
                logger.info("Branch creation mode activated successfully")
            else:
                logger.warning("Failed to start branch creation - no line found at cursor position")
        else:
            logger.warning("Could not get coordinates from mouse position - trying center of view as fallback")
            # Last resort - use center of the graphics view
            if hasattr(self.parent_widget, 'graphics_adapter'):
                try:
                    graphics_view = self.parent_widget.graphics_adapter.graphics_view
                    center_view = graphics_view.rect().center()
                    center_scene = graphics_view.mapToScene(center_view)
                    if hasattr(graphics_view.scene(), 'scene_to_original_coords'):
                        coordinates = graphics_view.scene().scene_to_original_coords(center_scene)
                        x, y = coordinates
                        logger.info(f"Using view center for branch creation: ({x}, {y})")
                        self.handle_branch_creation_request(x, y)
                except Exception as e:
                    logger.error(f"Failed to get coordinates even from view center: {e}")

    def handle_feature_click(self, target_node: str) -> None:
        """Handle clicks on features."""
        self.pin_clicked.emit(target_node)

    def handle_drawing_update(self) -> None:
        """Handle updates to drawing state."""
        self.parent_widget.image_label.update()  # Trigger repaint for temporary drawing
        self.parent_widget.update()  # Trigger repaint for temporary drawing

    def _handle_pin_placement(self, x: int, y: int) -> None:
        """Handle pin placement at specified coordinates."""
        dialog = PinPlacementDialog(x, y, self.parent_widget, self.controller)
        dialog.setWindowModality(Qt.WindowModality.ApplicationModal)

        if dialog.exec():
            target_node = dialog.get_target_node()
            if target_node:
                # Create relationship data using WKT format
                wkt_point = GeometryHandler.create_point(x, y)
                properties = GeometryHandler.create_geometry_properties(wkt_point)

                self.pin_created.emit(target_node, ">", properties)
                # Create pin in graphics mode
                logger.debug(f"Checking for graphics adapter: {hasattr(self.parent_widget, 'graphics_adapter')}")
                if hasattr(self.parent_widget, 'graphics_adapter'):
                    logger.info(f"Creating pin in graphics mode: {target_node} at ({x}, {y})")
                    adapter = self.parent_widget.graphics_adapter
                    logger.debug(f"Graphics adapter: {adapter}, is_migrated: {getattr(adapter, 'is_migrated', 'unknown')}")
                    adapter.feature_manager.add_pin_feature(target_node, x, y)
                    logger.info(f"Pin created successfully in graphics system")
                else:
                    logger.warning("No graphics adapter available for pin creation")
                    logger.debug(f"Parent widget attributes: {[attr for attr in dir(self.parent_widget) if 'graphics' in attr.lower()]}")

                # Exit pin placement mode
                self.parent_widget.pin_toggle_btn.setChecked(False)

    def _handle_line_point_add(self, x: int, y: int) -> None:
        """Handle adding a point to the current line being drawn."""
        # Convert to scaled coordinates for display
        scaled_x = x * self.parent_widget.current_scale
        scaled_y = y * self.parent_widget.current_scale

        self.parent_widget.drawing_manager.add_point(x, y, scaled_x, scaled_y)

    def _handle_branching_line_point_add(self, x: int, y: int) -> None:
        """Handle adding a point to the current branching line being drawn."""
        # Convert to scaled coordinates for display
        scaled_x = x * self.parent_widget.current_scale
        scaled_y = y * self.parent_widget.current_scale

        self.parent_widget.drawing_manager.add_branching_point(x, y, scaled_x, scaled_y)

    def handle_line_completion(self, points: list) -> None:
        """Handle completion of line drawing."""

        if len(points) < 2:
            logger.warning("Attempted to complete line with insufficient points")
            return

        dialog = LineFeatureDialog(points, self.parent_widget, self.controller)
        if dialog.exec():
            target_node = dialog.get_target_node()
            line_style = dialog.get_line_style()

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

                # Create the line and emit signals
                self.line_created.emit(target_node, ">", properties)

                # Create visual representation
                # Create line in graphics mode with style properties
                if hasattr(self.parent_widget, 'graphics_adapter'):
                    # Convert properties to style config format expected by graphics system
                    style_properties = {
                        "color": properties.get("style_color", "#FF0000"),
                        "width": properties.get("style_width", 2),
                        "pattern": properties.get("style_pattern", "solid"),
                    }
                    self.parent_widget.graphics_adapter.feature_manager.add_line_feature(target_node, points, style_properties)

                # Exit line drawing mode
                self.parent_widget.toolbar_manager.block_button_signals(True)
                self.parent_widget.line_toggle_btn.setChecked(False)
                self.parent_widget.toolbar_manager.block_button_signals(False)
                self.parent_widget.mode_manager.line_drawing_active = False

                logger.debug(f"Line created successfully: {target_node}")

            except Exception as e:
                logger.error(f"Error creating line: {e}")
                import traceback
                logger.error(traceback.format_exc())

    def handle_branching_line_completion(self, branches: list) -> None:
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
        dialog = BranchingLineFeatureDialog(
            branches, self.parent_widget, self.controller
        )
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
                # Create branching line in graphics mode with style properties
                if hasattr(self.parent_widget, 'graphics_adapter'):
                    # Convert properties to style config format expected by graphics system
                    style_properties = {
                        "color": properties.get("style_color", "#FF0000"),
                        "width": properties.get("style_width", 2),
                        "pattern": properties.get("style_pattern", "solid"),
                    }
                    self.parent_widget.graphics_adapter.feature_manager.add_branching_line_feature(target_node, branches, style_properties)

                # Exit branching line drawing mode
                self.parent_widget.toolbar_manager.block_button_signals(True)
                self.parent_widget.branching_line_toggle_btn.setChecked(False)
                self.parent_widget.toolbar_manager.block_button_signals(False)
                self.parent_widget.mode_manager.branching_line_drawing_active = False

            except Exception as e:
                logger.error(f"Error creating branching line: {e}")
                import traceback

                logger.error(traceback.format_exc())
                return

        elif self.parent_widget.edit_mode_active:
            if nearest["type"] == "control_point":
                # Set branch creation state
                self.parent_widget.mode_manager.branch_creation_mode = True
                self.parent_widget.mode_manager.set_branch_creation_target(
                    nearest["target_node"]
                )
                self.parent_widget.mode_manager.set_branch_creation_start_point(
                    nearest["point"]
                )
                self.parent_widget.mode_manager.set_branch_creation_point_indices(
                    (nearest["branch_idx"], nearest["point_idx"])
                )

                # Update cursor
                self.parent_widget.image_label.set_cursor_for_mode("crosshair")

                # Force redraw to highlight the selected point
                # Graphics mode handles position updates automatically
                logger.debug("Graphics mode position updates handled automatically")
                return

            elif nearest["type"] == "line_segment":
                # Set branch creation state
                self.parent_widget.mode_manager.branch_creation_mode = True
                self.parent_widget.mode_manager.set_branch_creation_target(
                    nearest["target_node"]
                )
                self.parent_widget.mode_manager.set_branch_creation_start_point(
                    nearest["original_coords"]
                )

                # Update cursor
                self.parent_widget.image_label.set_cursor_for_mode("crosshair")
                return

    def _complete_branch_creation(self, end_x: int, end_y: int) -> None:
        """Complete branch creation with the specified end point.

        Args:
            end_x: X coordinate of branch end point
            end_y: Y coordinate of branch end point
        """
        logger.info(f"Completing branch creation: End point ({end_x}, {end_y})")

        if not self.parent_widget.branch_creation_mode:
            logger.warning("Not in branch creation mode")
            return

        target_node = self.parent_widget.mode_manager.get_branch_creation_target()
        if not target_node:
            logger.warning("No branch creation target set")
            return

        start_point = self.parent_widget.mode_manager.get_branch_creation_start_point()
        if not start_point:
            logger.warning("No branch creation start point set")
            return

        start_x, start_y = start_point
        logger.info(f"Branch from ({start_x}, {start_y}) to ({end_x}, {end_y})")

        # Implement branch creation for graphics mode
        if hasattr(self.parent_widget, 'graphics_adapter'):
            try:
                # Get the target line graphics item
                scene = self.parent_widget.graphics_adapter.graphics_view.scene()
                feature_manager = self.parent_widget.graphics_adapter.feature_manager
                
                if target_node in feature_manager.features:
                    line_item = feature_manager.features[target_node]
                    
                    # Get current geometry
                    current_geometry = line_item.get_geometry_data()
                    logger.debug(f"Current geometry for {target_node}: {current_geometry}")
                    
                    # Add new branch - only works on MultiLineString geometry (Option A)
                    new_branch = [[start_x, start_y], [end_x, end_y]]
                    
                    # Verify this is already a branching line (MultiLineString)
                    if not isinstance(current_geometry[0], list):
                        logger.error(f"Cannot create branch on LineString geometry {target_node} - requires explicit conversion")
                        return
                    
                    # Add new branch to existing MultiLineString
                    updated_geometry = current_geometry + [new_branch]
                    logger.info(f"Adding branch to existing branching line")
                    
                    # Update the line item geometry
                    line_item.update_geometry(updated_geometry)
                    
                    # Mark the geometry as branching
                    line_item.geometry.is_branching = True
                    line_item.geometry._update_shared_points()
                    line_item.geometry._update_scaled_branches()
                    
                    # Update the visual
                    line_item._update_bounds()
                    line_item.update()
                    
                    # Emit geometry changed signal to update database
                    line_item._emit_geometry_changed()
                    
                    logger.info(f"Successfully created branch on {target_node}")
                    
                else:
                    logger.error(f"Target line {target_node} not found in graphics features")
                    
            except Exception as e:
                logger.error(f"Error creating branch in graphics mode: {e}")
                import traceback
                traceback.print_exc()
        else:
            logger.warning("No graphics adapter available for branch creation")
        
        # Reset branch creation mode
        logger.info("Resetting branch creation mode")
        self.parent_widget.mode_manager.reset_branch_creation_mode()

        # Force an update of the viewport to clear the orange line
        self.parent_widget.image_label.update()

    def handle_branch_creation_request(self, x: int, y: int) -> bool:
        """Handle branch creation request at specified coordinates.

        Args:
            x: X coordinate in original image space
            y: Y coordinate in original image space

        Returns:
            True if branch creation was initiated, False otherwise
        """
        logger.info(f"Handling branch creation request at ({x}, {y})")

        from .map_coordinate_utilities import MapCoordinateUtilities

        coord_utils = MapCoordinateUtilities(self.parent_widget)

        # Find the nearest line to the cursor position
        nearest_line = coord_utils.find_nearest_line_at_position(x, y)
        if nearest_line:
            logger.info(f"Found nearest line: {nearest_line}")

            # Check if the line geometry supports branching (Option A: MultiLineString only)
            if not self._can_create_branch_on_line(nearest_line):
                logger.warning(f"Line {nearest_line} does not support branch creation (LineString geometry)")
                return False

            # Start branch creation mode for this line
            self.parent_widget.mode_manager.branch_creation_mode = True
            self.parent_widget.mode_manager.set_branch_creation_target(nearest_line)
            self.parent_widget.mode_manager.set_branch_creation_start_point((x, y))

            # Set cursor to indicate branch creation mode
            self.parent_widget.image_label.set_cursor_for_mode("crosshair")
            
            # Update the target line container to show the preview
            # TODO: Migrate to graphics system - old widget feature manager removed
            logger.warning("Line container update not yet implemented for graphics mode")

            logger.info(f"Started branch creation mode for line: {nearest_line}")
            return True
        else:
            logger.warning("No suitable line found for branch creation")

        return False

    def _can_create_branch_on_line(self, target_node: str) -> bool:
        """Check if branch creation is allowed on the specified line.
        
        Option A: Only MultiLineString geometry supports branch creation.
        LineString geometry requires explicit conversion.
        
        Args:
            target_node: Name of the line node to check
            
        Returns:
            True if branch creation is allowed, False otherwise
        """
        if hasattr(self.parent_widget, 'graphics_adapter'):
            feature_manager = self.parent_widget.graphics_adapter.feature_manager
            
            if target_node in feature_manager.features:
                line_item = feature_manager.features[target_node]
                
                # Check if this is a branching line (MultiLineString)
                if hasattr(line_item, 'geometry') and hasattr(line_item.geometry, 'is_branching'):
                    is_branching = line_item.geometry.is_branching
                    logger.debug(f"Line {target_node} is_branching: {is_branching}")
                    return is_branching
                else:
                    logger.warning(f"Line {target_node} does not have geometry.is_branching attribute")
                    return False
            else:
                logger.warning(f"Line {target_node} not found in graphics features")
                return False
        else:
            logger.warning("No graphics adapter available for geometry type checking")
            return False
