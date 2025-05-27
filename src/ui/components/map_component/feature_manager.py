"""Unified feature manager for handling all map feature types.

This module provides a single, unified feature manager that handles all types of map features:
- Pins
- Simple lines
- Branching lines

This replaces the original separate FeatureManager and EnhancedFeatureManager classes.
"""

import json
from typing import Dict, List, Tuple, Optional, Any, Union
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QWidget
from structlog import get_logger

# Import existing container classes
from ui.components.map_component.pin_container import PinContainer
from ui.components.map_component.line_container import LineContainer
from utils.geometry_handler import GeometryHandler

logger = get_logger(__name__)


class BranchingLineGeometry:
    """Manages geometry for branching lines as a single logical entity."""

    def __init__(self, branches: List[List[Tuple[int, int]]]):
        """Initialize with a list of branches.

        Args:
            branches: List of branches, each branch is a list of coordinate points
        """
        self.branches = [branch.copy() for branch in branches]
        self._scale = 1.0
        self._scaled_branches = []
        self._shared_points = (
            {}
        )  # Maps point coordinates to list of (branch_idx, point_idx)
        self._bounds_cache = None
        self._bounds_cache_valid = False
        self._update_shared_points()
        self._update_scaled_branches()

    def _update_shared_points(self):
        """Update mapping of shared points between branches."""
        self._shared_points = {}

        for branch_idx, branch in enumerate(self.branches):
            for point_idx, point in enumerate(branch):
                if point not in self._shared_points:
                    self._shared_points[point] = []
                self._shared_points[point].append((branch_idx, point_idx))

    def _update_scaled_branches(self):
        """Update scaled branches based on current scale."""
        self._scaled_branches = []
        for branch in self.branches:
            scaled_branch = [
                (int(p[0] * self._scale), int(p[1] * self._scale)) for p in branch
            ]
            self._scaled_branches.append(scaled_branch)
        self._invalidate_bounds()

    def set_scale(self, scale: float):
        """Set the scale and update all branches."""
        self._scale = scale
        self._update_scaled_branches()

    def get_bounds(self) -> Tuple[int, int, int, int]:
        """Get bounds encompassing all branches."""
        if not self._bounds_cache_valid:
            self._calculate_bounds()
        return self._bounds_cache

    def _calculate_bounds(self):
        """Calculate bounds across all branches."""
        if not self._scaled_branches:
            self._bounds_cache = (0, 0, 0, 0)
            return

        all_points = []
        for branch in self._scaled_branches:
            all_points.extend(branch)

        if not all_points:
            self._bounds_cache = (0, 0, 0, 0)
            return

        min_x = min(p[0] for p in all_points)
        min_y = min(p[1] for p in all_points)
        max_x = max(p[0] for p in all_points)
        max_y = max(p[1] for p in all_points)

        self._bounds_cache = (min_x, min_y, max_x, max_y)
        self._bounds_cache_valid = True

    def _invalidate_bounds(self):
        """Invalidate bounds cache."""
        self._bounds_cache_valid = False

    def update_point(self, branch_idx: int, point_idx: int, new_point: Tuple[int, int]):
        """Update a point, handling shared points across branches."""
        if branch_idx >= len(self.branches) or point_idx >= len(
            self.branches[branch_idx]
        ):
            return

        old_point = self.branches[branch_idx][point_idx]

        # Check if this point is shared with other branches
        if old_point in self._shared_points:
            shared_locations = self._shared_points[old_point]

            # Update all instances of this shared point
            for shared_branch_idx, shared_point_idx in shared_locations:
                if shared_branch_idx < len(self.branches) and shared_point_idx < len(
                    self.branches[shared_branch_idx]
                ):
                    self.branches[shared_branch_idx][shared_point_idx] = new_point
        else:
            # Update just this point
            self.branches[branch_idx][point_idx] = new_point

        # Rebuild shared points mapping and scaled branches
        self._update_shared_points()
        self._update_scaled_branches()

    def insert_point(self, branch_idx: int, point_idx: int, new_point: Tuple[int, int]):
        """Insert a point into a specific branch."""
        if branch_idx >= len(self.branches):
            return

        self.branches[branch_idx].insert(point_idx, new_point)
        self._update_shared_points()
        self._update_scaled_branches()

    def delete_point(self, branch_idx: int, point_idx: int) -> bool:
        """Delete a point, handling shared points carefully."""
        if branch_idx >= len(self.branches) or point_idx >= len(
            self.branches[branch_idx]
        ):
            return False

        # Don't allow deletion if it would make a branch too short
        if len(self.branches[branch_idx]) <= 2:
            return False

        point_to_delete = self.branches[branch_idx][point_idx]

        # Check if this is a shared point
        if point_to_delete in self._shared_points:
            shared_locations = self._shared_points[point_to_delete]

            # If shared with multiple branches, only delete from this branch
            if len(shared_locations) > 1:
                self.branches[branch_idx].pop(point_idx)
            else:
                # Not actually shared, safe to delete
                self.branches[branch_idx].pop(point_idx)
        else:
            self.branches[branch_idx].pop(point_idx)

        self._update_shared_points()
        self._update_scaled_branches()
        return True

    def get_center(self) -> Tuple[int, int]:
        """Get center point of all branches."""
        min_x, min_y, max_x, max_y = self.get_bounds()
        return ((min_x + max_x) // 2, (min_y + max_y) // 2)

    @property
    def scaled_branches(self) -> List[List[Tuple[int, int]]]:
        """Get scaled branches."""
        return self._scaled_branches

    @property
    def original_branches(self) -> List[List[Tuple[int, int]]]:
        """Get original branches."""
        return self.branches


class BranchingLineContainer(QWidget):
    """Container widget for branching lines."""

    line_clicked = pyqtSignal(str)
    geometry_changed = pyqtSignal(str, list)  # target_node, branches

    def __init__(
        self,
        target_node: str,
        branches: List[List[Tuple[int, int]]],
        parent=None,
        config=None,
    ):
        """Initialize branching line container.

        Args:
            target_node: Node name this line represents
            branches: List of branches, each branch is a list of coordinate points
            parent: Parent widget
            config: Configuration object
        """
        super().__init__(parent)

        # Import required classes here to avoid circular imports
        from ui.components.map_component.line_container import LineContainer

        # Create the actual container implementation using unified system
        self._container = LineContainer(
            target_node, branches, parent, config
        )

        # Connect signals
        self._container.line_clicked.connect(self.line_clicked)
        self._container.geometry_changed.connect(self.geometry_changed)

        # Forward methods
        self.set_scale = self._container.set_scale
        self.set_style = self._container.set_style
        self.set_edit_mode = self._container.set_edit_mode
        self.deleteLater = self._container.deleteLater
        self.show = self._container.show
        self.raise_ = self._container.raise_


class UnifiedFeatureManager(QObject):
    """Unified manager for all map features (pins, lines, and branching lines).

    This replaces both the original FeatureManager and EnhancedFeatureManager
    with a single, consistent interface.
    """

    # Feature management signals
    feature_created = pyqtSignal(str, str)  # feature_type, target_node
    feature_deleted = pyqtSignal(str, str)  # feature_type, target_node
    feature_clicked = pyqtSignal(str)  # target_node
    geometry_changed = pyqtSignal(
        str, list
    )  # target_node, branches (for branching lines)

    def __init__(self, parent_container: QWidget, config=None):
        """Initialize the feature manager.

        Args:
            parent_container: Widget to contain all features
            config: Configuration object
        """
        super().__init__()
        self.parent_container = parent_container
        self.config = config

        # Feature storage
        self.pins: Dict[str, PinContainer] = {}
        self.simple_lines: Dict[str, LineContainer] = {}
        self.branching_lines: Dict[str, BranchingLineContainer] = {}

        # Current scale for features
        self.current_scale = 1.0

    def set_scale(self, scale: float) -> None:
        """Update scale for all features.

        Args:
            scale: New scale factor
        """
        self.current_scale = scale

        # Update existing features
        for pin in self.pins.values():
            pin.set_scale(scale)

        for line in self.simple_lines.values():
            line.set_scale(scale)
            # Ensure the line container is visible and properly positioned
            line.show()
            line.raise_()

        for line in self.branching_lines.values():
            line.set_scale(scale)
            line.show()
            line.raise_()

    def create_pin(self, target_node: str, x: int, y: int) -> None:
        """Create a pin feature.

        Args:
            target_node: Node name this pin represents
            x: Original x-coordinate
            y: Original y-coordinate
        """
        # Remove existing pin if it exists
        if target_node in self.pins:
            self.pins[target_node].deleteLater()
            del self.pins[target_node]

        # Create new pin container
        pin_container = PinContainer(target_node, self.parent_container, self.config)
        pin_container.pin_clicked.connect(self.feature_clicked.emit)
        pin_container.set_scale(self.current_scale)

        # Store original coordinates
        pin_container.original_x = x
        pin_container.original_y = y

        self.pins[target_node] = pin_container
        self._update_pin_position(target_node, x, y)
        pin_container.show()

        self.feature_created.emit("pin", target_node)

    def create_line(
        self,
        target_node: str,
        points: List[Tuple[int, int]],
        style_config: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Create a simple line feature.

        Args:
            target_node: Node name this line represents
            points: List of coordinate points
            style_config: Optional style configuration
        """
        # Remove existing line if it exists
        if target_node in self.simple_lines:
            self.simple_lines[target_node].deleteLater()
            del self.simple_lines[target_node]

        # Create new line container
        line_container = LineContainer(
            target_node, points, self.parent_container, self.config
        )
        line_container.line_clicked.connect(self.feature_clicked.emit)
        line_container.set_scale(self.current_scale)

        # Apply style if provided
        if style_config:
            line_container.set_style(
                color=style_config.get("color"),
                width=style_config.get("width"),
                pattern=style_config.get("pattern"),
            )

        self.simple_lines[target_node] = line_container
        line_container.show()
        line_container.raise_()

        self.feature_created.emit("line", target_node)

    def create_branching_line(
        self,
        target_node: str,
        branches: List[List[Tuple[int, int]]],
        style_config: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Create a branching line feature.

        Args:
            target_node: Node name this line represents
            branches: List of branches, each branch is a list of coordinate points
            style_config: Optional style configuration
        """
        # Remove existing branching line if it exists
        if target_node in self.branching_lines:
            self.branching_lines[target_node].deleteLater()
            del self.branching_lines[target_node]

        # Create new branching line container
        line_container = BranchingLineContainer(
            target_node, branches, self.parent_container, self.config
        )

        # Connect signals
        line_container.line_clicked.connect(self.feature_clicked.emit)
        line_container.geometry_changed.connect(self.geometry_changed.emit)

        # Apply style if provided
        if style_config:
            line_container.set_style(
                color=style_config.get("color"),
                width=style_config.get("width"),
                pattern=style_config.get("pattern"),
            )

        # Set scale and show
        line_container.set_scale(self.current_scale)
        self.branching_lines[target_node] = line_container
        line_container.show()
        line_container.raise_()

        self.feature_created.emit("branching_line", target_node)

    def batch_create_pins(self, pin_data: List[Tuple[str, int, int]]) -> None:
        """Create multiple pins efficiently.

        Args:
            pin_data: List of (target_node, x, y) tuples
        """
        # Remove existing pins
        for target_node, _, _ in pin_data:
            if target_node in self.pins:
                self.pins[target_node].deleteLater()
                del self.pins[target_node]

        # Temporarily disable updates for performance
        self.parent_container.setUpdatesEnabled(False)

        try:
            for target_node, x, y in pin_data:
                pin_container = PinContainer(
                    target_node, self.parent_container, self.config
                )
                pin_container.pin_clicked.connect(self.feature_clicked.emit)
                pin_container.set_scale(self.current_scale)
                pin_container.original_x = x
                pin_container.original_y = y
                self.pins[target_node] = pin_container
                self._update_pin_position(target_node, x, y)
                pin_container.show()
        finally:
            self.parent_container.setUpdatesEnabled(True)
            self.parent_container.update()

    def batch_create_lines(
        self, line_data: List[Tuple[str, List[Tuple[int, int]], Dict[str, Any]]]
    ) -> None:
        """Create multiple simple lines efficiently.

        Args:
            line_data: List of (target_node, points, style_config) tuples
        """
        logger.debug(f"batch_create_lines called with {len(line_data)} lines")

        # Group lines by target_node
        grouped_lines = {}
        for target_node, points, style_config in line_data:
            logger.debug(f"Processing line for {target_node} with {len(points)} points")

            if target_node not in grouped_lines:
                grouped_lines[target_node] = []

            grouped_lines[target_node].append((points, style_config))

        # Remove existing lines
        for target_node in grouped_lines.keys():
            if target_node in self.simple_lines:
                logger.debug(f"Removing existing line for {target_node}")
                self.simple_lines[target_node].deleteLater()
                del self.simple_lines[target_node]

        # Temporarily disable updates for performance
        self.parent_container.setUpdatesEnabled(False)

        try:
            for target_node, lines_data in grouped_lines.items():
                # Handle single lines normally
                if len(lines_data) == 1:
                    points, style_config = lines_data[0]
                    line_container = LineContainer(
                        target_node, points, self.parent_container, self.config
                    )
                    line_container.line_clicked.connect(self.feature_clicked.emit)
                    line_container.set_scale(self.current_scale)

                    if style_config:
                        line_container.set_style(
                            color=style_config.get("color"),
                            width=style_config.get("width"),
                            pattern=style_config.get("pattern"),
                        )

                    self.simple_lines[target_node] = line_container
                    line_container.show()
                    line_container.raise_()

                # Multiple lines for same target should be a branching line
                else:
                    # Convert to branches format and create branching line
                    branches = [points for points, _ in lines_data]
                    style_config = lines_data[0][1]  # Use style from first line

                    self.create_branching_line(target_node, branches, style_config)
        finally:
            self.parent_container.setUpdatesEnabled(True)
            self.parent_container.update()

    def batch_create_branching_lines(
        self, branching_data: Dict[str, Dict[str, Any]]
    ) -> None:
        """Create multiple branching lines efficiently.

        Args:
            branching_data: Dictionary mapping target_node to
                           {"branches": List[List[Tuple[int, int]]], "style": Dict}
        """
        logger.debug(
            f"batch_create_branching_lines called with {len(branching_data)} items"
        )

        # Temporarily disable updates for performance
        self.parent_container.setUpdatesEnabled(False)

        try:
            for target_node, data in branching_data.items():
                branches = data["branches"]
                style_config = data["style"]

                self.create_branching_line(target_node, branches, style_config)
        finally:
            self.parent_container.setUpdatesEnabled(True)
            self.parent_container.update()

    def update_positions(self, parent_map_tab) -> None:
        """Update positions of all features based on current scale and viewport."""
        # Update pin positions
        for target_node, pin in self.pins.items():
            if hasattr(pin, "original_x") and hasattr(pin, "original_y"):
                self._update_pin_position_with_viewport(
                    target_node, pin.original_x, pin.original_y, parent_map_tab
                )

        # Update line positions - lines handle their own geometry updates through set_scale
        # but we need to ensure they're properly visible
        for line_container in self.simple_lines.values():
            line_container.raise_()
            line_container.show()

        # Same for branching lines
        for line_container in self.branching_lines.values():
            line_container.raise_()
            line_container.show()

    def _update_pin_position(self, target_node: str, x: int, y: int) -> None:
        """Update position of a single pin (basic version)."""
        if target_node not in self.pins:
            return

        pin_container = self.pins[target_node]

        # Calculate scaled position
        scaled_x = x * self.current_scale
        scaled_y = y * self.current_scale

        # Basic positioning (will be enhanced by viewport-aware version)
        pin_container.move(int(scaled_x), int(scaled_y))
        pin_container.raise_()

    def _update_pin_position_with_viewport(
        self, target_node: str, x: int, y: int, parent_map_tab
    ) -> None:
        """Update position of a single pin with viewport awareness."""
        if target_node not in self.pins:
            return

        pin_container = self.pins[target_node]

        # Get current scaled pixmap
        pixmap = parent_map_tab.image_label.pixmap()
        if not pixmap:
            return

        # Get scaled dimensions
        scaled_width = pixmap.width()
        scaled_height = pixmap.height()

        # Get original dimensions
        original_width = parent_map_tab.image_manager.original_pixmap.width()
        original_height = parent_map_tab.image_manager.original_pixmap.height()

        # Calculate scale ratios
        width_ratio = scaled_width / original_width
        height_ratio = scaled_height / original_height

        # Calculate scaled position directly using the ratios
        scaled_x = x * width_ratio
        scaled_y = y * height_ratio

        # Position pin (align bottom with coordinate)
        pin_x = int(scaled_x - (pin_container.pin_svg.width() / 2))
        pin_y = int(scaled_y - pin_container.pin_svg.height())

        pin_container.move(pin_x, pin_y)
        pin_container.raise_()
        pin_container.show()

        logger.debug(
            f"Pin {target_node} positioned at ({pin_x}, {pin_y}) - scaled coords: ({scaled_x}, {scaled_y})"
        )

    def clear_all_features(self) -> None:
        """Remove all features."""
        self.clear_pins()
        self.clear_simple_lines()
        self.clear_branching_lines()

    def clear_pins(self) -> None:
        """Remove all pins."""
        for pin in self.pins.values():
            pin.deleteLater()
        self.pins.clear()

    def clear_simple_lines(self) -> None:
        """Remove all simple lines."""
        for line in self.simple_lines.values():
            line.deleteLater()
        self.simple_lines.clear()

    def clear_branching_lines(self) -> None:
        """Remove all branching lines."""
        for line in self.branching_lines.values():
            line.deleteLater()
        self.branching_lines.clear()

    def set_edit_mode(self, active: bool) -> None:
        """Set edit mode for all features.

        Args:
            active: Whether edit mode should be active
        """
        # Set edit mode for pins
        for pin_container in self.pins.values():
            pin_container.set_edit_mode(active)
        
        # Set edit mode for lines
        for line_container in self.simple_lines.values():
            line_container.set_edit_mode(active)

        for line_container in self.branching_lines.values():
            line_container.set_edit_mode(active)

    def get_feature_count(self) -> Dict[str, int]:
        """Get count of features by type.

        Returns:
            Dictionary with feature counts
        """
        return {
            "pins": len(self.pins),
            "simple_lines": len(self.simple_lines),
            "branching_lines": len(self.branching_lines),
            "total": len(self.pins)
            + len(self.simple_lines)
            + len(self.branching_lines),
        }

    def get_line_containers(self) -> Dict[str, Any]:
        """Get all line containers (both simple and branching).
        
        Returns:
            Dictionary mapping target_node to line container
            Note: For branching lines, it returns the actual LineContainer
                 by accessing the _container attribute
        """
        all_lines = {}
        all_lines.update(self.simple_lines)
        
        # For branching lines, add the inner _container which has the actual geometry
        for target_node, container in self.branching_lines.items():
            if hasattr(container, '_container'):
                all_lines[target_node] = container._container
            else:
                all_lines[target_node] = container
                
        return all_lines


def integrate_unified_feature_manager(map_tab_instance):
    """Integrate unified feature manager into existing MapTab instance.

    Args:
        map_tab_instance: Existing MapTab instance to enhance

    Returns:
        The modified map_tab_instance
    """
    # Store reference to old feature managers for cleanup
    old_feature_manager = getattr(map_tab_instance, "feature_manager", None)
    old_enhanced_manager = getattr(map_tab_instance, "enhanced_feature_manager", None)

    # Create new unified feature manager
    map_tab_instance.unified_manager = UnifiedFeatureManager(
        map_tab_instance.feature_container, map_tab_instance.config
    )

    # Connect signals
    map_tab_instance.unified_manager.feature_clicked.connect(
        map_tab_instance._handle_feature_click
    )

    # Connect to controller's pin_click handler for navigation
    if map_tab_instance.controller:
        map_tab_instance.unified_manager.feature_clicked.connect(
            map_tab_instance.controller._handle_pin_click
        )

    # Handle geometry changes from branching lines
    def handle_geometry_change(target_node: str, branches: List[List[Tuple[int, int]]]):
        """Handle geometry changes from branching lines."""
        if map_tab_instance.controller:
            try:
                from utils.geometry_handler import GeometryHandler

                # Create WKT MultiLineString from branches
                wkt_multiline = GeometryHandler.create_multi_line(branches)

                # Find and update the relationship
                relationships_table = map_tab_instance.controller.ui.relationships_table

                for row in range(relationships_table.rowCount()):
                    rel_type_item = relationships_table.item(row, 0)
                    target_item = relationships_table.item(row, 1)

                    if (
                        rel_type_item
                        and rel_type_item.text() == "SHOWS"
                        and target_item
                        and map_tab_instance._extract_target_node(
                            target_item, relationships_table, row
                        )
                        == target_node
                    ):

                        # Update properties
                        props_item = relationships_table.item(row, 3)
                        if props_item:
                            properties = json.loads(props_item.text())
                            properties["geometry"] = wkt_multiline
                            properties["geometry_type"] = "MultiLineString"
                            properties["branch_count"] = len(branches)

                            props_item.setText(json.dumps(properties))
                            map_tab_instance.controller.save_data()
                            logger.info(
                                f"Updated geometry for {target_node} with {len(branches)} branches"
                            )
                            break

            except Exception as e:
                logger.error(f"Error updating geometry: {e}")

    map_tab_instance.unified_manager.geometry_changed.connect(handle_geometry_change)

    # Replace the map_tab's feature_manager with the unified manager
    map_tab_instance.feature_manager = map_tab_instance.unified_manager

    # Update the map image display to handle unified manager
    original_update_display = map_tab_instance._update_map_image_display

    def enhanced_update_map_image_display():
        """Enhanced display update that handles unified feature manager."""
        # Call original method
        original_update_display()

        # Update unified feature manager scale
        map_tab_instance.unified_manager.set_scale(map_tab_instance.current_scale)

    map_tab_instance._update_map_image_display = enhanced_update_map_image_display

    # Replace the load_features method
    def unified_load_features():
        """Unified feature loading method."""
        if (
            not map_tab_instance.controller
            or not map_tab_instance.controller.ui.relationships_table
        ):
            return

        # Collect feature data
        branching_line_data = {}  # Group by target_node
        simple_line_data = []
        pin_data = []

        relationships_table = map_tab_instance.controller.ui.relationships_table
        logger.info(
            f"Starting unified_load_features with {relationships_table.rowCount()} relationships"
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

                from utils.geometry_handler import GeometryHandler

                if not GeometryHandler.validate_wkt(properties["geometry"]):
                    logger.warning(f"Invalid WKT geometry at row {row}")
                    continue

                geometry_type = properties.get(
                    "geometry_type",
                    GeometryHandler.get_geometry_type(properties["geometry"]),
                )
                target_node = map_tab_instance._extract_target_node(
                    target_item, relationships_table, row
                )

                logger.info(f"Found {geometry_type} for {target_node}")

                style_config = {
                    "color": properties.get("style_color", "#FF0000"),
                    "width": properties.get("style_width", 2),
                    "pattern": properties.get("style_pattern", "solid"),
                }

                if geometry_type == "MultiLineString":
                    # Handle as branching line
                    branches = GeometryHandler.get_coordinates(properties["geometry"])
                    logger.info(f"MultiLineString has {len(branches)} branches")

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
                logger.error(f"Error loading feature: {e}")
                import traceback

                logger.error(traceback.format_exc())
                continue

        # Clear all existing features
        map_tab_instance.unified_manager.clear_all_features()

        logger.info(
            f"Found features: {len(pin_data)} pins, {len(simple_line_data)} simple lines, {len(branching_line_data)} branching lines"
        )

        # Create features using unified manager
        if pin_data:
            map_tab_instance.unified_manager.batch_create_pins(pin_data)

        if simple_line_data:
            map_tab_instance.unified_manager.batch_create_lines(simple_line_data)

        if branching_line_data:
            map_tab_instance.unified_manager.batch_create_branching_lines(
                branching_line_data
            )

    # Replace the load_features method
    map_tab_instance.load_features = unified_load_features

    # Ensure the edit mode toggle works with unified manager
    original_toggle_edit = map_tab_instance.toggle_edit_mode

    def unified_toggle_edit_mode(active: bool):
        """Toggle edit mode using unified manager."""
        # Keep original behavior for consistency
        original_toggle_edit(active)

        # Set edit mode on unified manager
        map_tab_instance.unified_manager.set_edit_mode(active)

    map_tab_instance.toggle_edit_mode = unified_toggle_edit_mode

    # Clean up old feature managers if they exist
    if old_feature_manager and old_feature_manager != map_tab_instance.unified_manager:
        # Clean up old feature manager
        old_feature_manager.clear_all_features()

    if old_enhanced_manager and hasattr(old_enhanced_manager, "clear_all_features"):
        # Clean up old enhanced feature manager
        old_enhanced_manager.clear_all_features()

    # Remove references to old managers
    if hasattr(map_tab_instance, "enhanced_feature_manager"):
        delattr(map_tab_instance, "enhanced_feature_manager")

    logger.info("Unified feature manager integration complete")

    return map_tab_instance
