import json
from typing import List, Tuple, Dict, Optional

from structlog import get_logger

from utils.geometry_handler import GeometryHandler

logger = get_logger(__name__)


class MapFeatureLoader:
    """Handles loading of map features from the database.

    Responsible for parsing relationship data and creating visual
    representations of pins, lines, and branching lines.
    """

    def __init__(self, parent_widget, controller=None):
        """Initialize the feature loader.

        Args:
            parent_widget: The parent widget (MapTab instance)
            controller: Application controller
        """
        self.parent_widget = parent_widget
        self.controller = controller

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
        self.parent_widget.feature_manager.clear_all_features()

        # Create features using the unified manager
        if pin_data:
            logger.info(f"Creating {len(pin_data)} pins")
            self.parent_widget.feature_manager.batch_create_pins(pin_data)

        if simple_line_data:
            logger.info(f"Creating {len(simple_line_data)} simple lines")
            self.parent_widget.feature_manager.batch_create_lines(simple_line_data)

        if branching_line_data:
            logger.info(f"Creating {len(branching_line_data)} branching lines")
            self.parent_widget.feature_manager.batch_create_branching_lines(
                branching_line_data
            )

    def _extract_target_node(self, target_item, relationships_table, row) -> str:
        """Extract target node name from table item."""
        if hasattr(target_item, "text"):
            return target_item.text()
        else:
            target_widget = relationships_table.cellWidget(row, 1)
            if hasattr(target_widget, "text"):
                return target_widget.text()
        return ""

    def reload_features(self) -> None:
        """Reload all features from the database."""
        logger.info("Reloading map features")
        self.load_features()

    def get_feature_statistics(self) -> Dict[str, int]:
        """Get statistics about loaded features.

        Returns:
            Dictionary with counts of each feature type
        """
        return self.parent_widget.feature_manager.get_feature_count()
