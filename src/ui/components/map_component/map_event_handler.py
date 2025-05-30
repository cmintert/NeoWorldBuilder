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
        
        # Get current mouse position from the viewport
        if hasattr(self.parent_widget, 'image_label') and hasattr(self.parent_widget.image_label, 'current_mouse_pos'):
            mouse_pos = self.parent_widget.image_label.current_mouse_pos
            
            # Convert widget coordinates to original coordinates
            coordinates = self.parent_widget.image_label._get_original_coordinates(mouse_pos)
            if coordinates:
                x, y = coordinates
                logger.info(f"Starting branch creation at coordinates: ({x}, {y})")
                
                # Use the existing branch creation request handler
                if self.handle_branch_creation_request(x, y):
                    logger.info("Branch creation mode activated successfully")
                else:
                    logger.warning("Failed to start branch creation - no line found at cursor position")
            else:
                logger.warning("Could not get coordinates from mouse position")
        else:
            logger.warning("Could not get current mouse position from viewport")

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
                self.parent_widget.feature_manager.create_pin(target_node, x, y)

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
        print(f"Branching line point added at: ({x}, {y})")

    def handle_line_completion(self, points: list) -> None:
        """Handle completion of line drawing."""
        print(f"_handle_line_completion called with {len(points)} points")

        if len(points) < 2:
            logger.warning("Attempted to complete line with insufficient points")
            print("Line has insufficient points, aborting")
            return

        dialog = LineFeatureDialog(points, self.parent_widget, self.controller)
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
                self.parent_widget.feature_manager.create_line(
                    target_node, points, line_style
                )
                print(f"Visual line created")

                # Exit line drawing mode
                self.parent_widget.toolbar_manager.block_button_signals(True)
                self.parent_widget.line_toggle_btn.setChecked(False)
                self.parent_widget.toolbar_manager.block_button_signals(False)
                self.parent_widget.mode_manager.line_drawing_active = False

                logger.debug(f"Line created successfully: {target_node}")
                print(f"Line creation process completed")

            except Exception as e:
                logger.error(f"Error creating line: {e}")
                print(f"Exception during line creation: {e}")
                import traceback

                print(traceback.format_exc())

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
                self.parent_widget.feature_manager.create_branching_line(
                    target_node, branches, line_style
                )

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
                self.parent_widget.feature_manager.update_positions(self.parent_widget)
                print("Branch creation mode activated with highlighted point")
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

                print(f"Branch creation mode activated from line segment")
                return

    def _complete_branch_creation(self, end_x: int, end_y: int) -> None:
        """Complete branch creation with the specified end point.

        Args:
            end_x: X coordinate of branch end point
            end_y: Y coordinate of branch end point
        """
        print(f"Completing branch creation: End point ({end_x}, {end_y})")
        logger.info(f"Completing branch creation: End point ({end_x}, {end_y})")

        if not self.parent_widget.branch_creation_mode:
            print("Not in branch creation mode")
            logger.warning("Not in branch creation mode")
            return

        target_node = self.parent_widget.mode_manager.get_branch_creation_target()
        if not target_node:
            print("No branch creation target set")
            logger.warning("No branch creation target set")
            return

        start_point = self.parent_widget.mode_manager.get_branch_creation_start_point()
        if not start_point:
            print("No branch creation start point set")
            logger.warning("No branch creation start point set")
            return

        start_x, start_y = start_point
        print(f"Branch from ({start_x}, {start_y}) to ({end_x}, {end_y})")
        logger.info(f"Branch from ({start_x}, {start_y}) to ({end_x}, {end_y})")

        # Get the line container for the target
        line_containers = self.parent_widget.feature_manager.get_line_containers()
        if target_node in line_containers:
            line_container = line_containers[target_node]
            print(f"Found line container for {target_node}: {type(line_container)}")
            logger.info(
                f"Found line container for {target_node}: {type(line_container)}"
            )

            # For branching lines, access the actual LineContainer
            if hasattr(line_container, "_container"):
                print("Using _container from BranchingLineContainer")
                logger.info("Using _container from BranchingLineContainer")
                line_container = line_container._container

            # Request branch creation from the line container
            if hasattr(line_container, "create_branch_from_point"):
                print(f"Calling create_branch_from_point")
                logger.info(f"Calling create_branch_from_point")
                line_container.create_branch_from_point(start_x, start_y, end_x, end_y)
                print("Branch created successfully")
                logger.info("Branch created successfully")
            else:
                print(
                    f"Error: line_container has no create_branch_from_point method: {dir(line_container)}"
                )
                logger.error(
                    f"line_container has no create_branch_from_point method: {dir(line_container)}"
                )
        else:
            print(f"Error: target_node {target_node} not found in line_containers")
            logger.error(f"target_node {target_node} not found in line_containers")

        # Reset branch creation mode
        print("Resetting branch creation mode")
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

            # Start branch creation mode for this line
            self.parent_widget.mode_manager.branch_creation_mode = True
            self.parent_widget.mode_manager.set_branch_creation_target(nearest_line)
            self.parent_widget.mode_manager.set_branch_creation_start_point((x, y))

            # Set cursor to indicate branch creation mode
            self.parent_widget.image_label.set_cursor_for_mode("crosshair")
            
            # Update the target line container to show the preview
            line_containers = self.parent_widget.feature_manager.get_line_containers()
            if nearest_line in line_containers:
                line_containers[nearest_line].update()
                logger.info(f"Updated line container for {nearest_line}")

            logger.info(f"Started branch creation mode for line: {nearest_line}")
            return True
        else:
            logger.warning("No suitable line found for branch creation")

        return False
