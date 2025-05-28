"""Unified feature manager for handling all map feature types.

This module provides a single, unified feature manager that handles all types of map features:
- Pins
- Simple lines
- Branching lines

This replaces the original separate FeatureManager and EnhancedFeatureManager classes.
"""

import json
from typing import Dict, List, Tuple, Optional, Any
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QWidget
from structlog import get_logger

# Import container classes from the containers package
from ui.components.map_component.containers.pin_container import PinContainer
from ui.components.map_component.containers.line_container import LineContainer
from ui.components.map_component.containers.branching_line_container import (
    BranchingLineContainer,
)

# Import geometry classes
from ui.components.map_component.line_geometry import BranchingLineGeometry

logger = get_logger(__name__)


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
                 by accessing the internal container through the public interface
        """
        all_lines = {}
        all_lines.update(self.simple_lines)

        # For branching lines, add the inner container which has the actual geometry
        for target_node, container in self.branching_lines.items():
            all_lines[target_node] = container.get_line_container()

        return all_lines
