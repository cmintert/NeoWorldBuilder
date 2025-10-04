import json
from typing import Any, Dict, Optional

from structlog import get_logger

from ui.components.map_component.map_tab import MapTab

logger = get_logger(__name__)


class MapMixin:
    def _ensure_map_tab_exists(self) -> None:
        """Create map tab if it doesn't exist and connect all signals.

        This is the single source of truth for map tab creation, used by both:
        - Real-time label detection (when user types "MAP")
        - Loading existing MAP nodes from database
        """
        # Handle both attribute styles: hasattr check for UI, direct check for mixin
        if hasattr(self.ui, "map_tab") and self.ui.map_tab:
            return  # Already exists

        logger.debug("Creating map tab and connecting signals")
        self.ui.map_tab = MapTab(controller=self)

        # Connect all signals - this is the authoritative list
        logger.debug("Connecting map_image_changed signal")
        self.ui.map_tab.map_image_changed.connect(self.ui._handle_map_image_changed)

        logger.debug("Connecting pin_clicked signal")
        self.ui.map_tab.pin_clicked.connect(self._handle_pin_click)

        logger.debug("Connecting pin_created signal")
        self.ui.map_tab.pin_created.connect(self._handle_pin_created)

        logger.debug("Connecting line_created signal")
        self.ui.map_tab.line_created.connect(self._handle_line_created)

        logger.debug("Connecting polygon_created signal")
        self.ui.map_tab.polygon_created.connect(self._handle_polygon_created)

        # Verify all connections were successful
        logger.debug(
            "Map tab signal connections status",
            map_image_changed=self.ui.map_tab.map_image_changed.receivers() > 0,
            pin_clicked=self.ui.map_tab.pin_clicked.receivers() > 0,
            pin_created=self.ui.map_tab.pin_created.receivers() > 0,
            line_created=self.ui.map_tab.line_created.receivers() > 0,
            polygon_created=self.ui.map_tab.polygon_created.receivers() > 0
        )

        self.ui.tabs.addTab(self.ui.map_tab, "Map")

        # Set initial map image if available in properties
        map_image_path = self.ui._get_property_value("mapimage")
        if map_image_path:
            self.ui.map_tab.set_map_image(map_image_path)
            logger.info("Map image loaded from properties", path=map_image_path)

    def _handle_pin_created(
        self, target_node: str, direction: str, properties: dict
    ) -> None:
        """Handle creation of a new map pin relationship.

        Args:
            target_node: The node to link to
            direction: Relationship direction
            properties: Properties including x,y coordinates
        """
        logger.info(f"Pin created handler called for target: {target_node}")

        # Get current node name (the map node)
        source_node = self.ui.name_input.text().strip()
        if not source_node:
            logger.warning("No source node in name_input, skipping pin creation")
            return

        logger.info(f"Creating pin relationship: {source_node} SHOWS {target_node}")

        # Add new relationship row with SHOWS type
        self.ui.add_relationship_row(
            "SHOWS", target_node, direction, json.dumps(properties)
        )

        # Update save state to reflect changes
        self.update_unsaved_changes_indicator()

        logger.info("Pin relationship created, staying on map tab")

    def _handle_pin_click(self, target_node: str) -> None:
        """Handle pin click by loading the target node."""
        logger.info(
            f"Pin click handler called for target: {target_node} - NAVIGATING TO NODE"
        )
        self.ui.name_input.setText(target_node)
        self.load_node_data()
        self.ui.tabs.setCurrentIndex(0)

    def _populate_map_tab(self, node_data: Dict[str, Any]) -> None:
        """
        Handle map tab visibility and population.

        Args:
            node_data: Dictionary containing node information.
        """
        is_map_node = "MAP" in {label.upper() for label in node_data["labels"]}

        if is_map_node:
            self._ensure_map_tab_exists()
            self._update_map_image(node_data["properties"].get("mapimage"))
            self.ui.map_tab.load_features()
        else:
            self._remove_map_tab()

    def _remove_map_tab(self) -> None:
        """Remove map tab if it exists."""
        if self.ui.map_tab:
            map_tab_index = self.ui.tabs.indexOf(self.ui.map_tab)
            if map_tab_index != -1:
                self.ui.tabs.removeTab(map_tab_index)
                self.ui.map_tab = None

    def _update_map_image(self, image_path: Optional[str]) -> None:
        """Update map image if map tab exists."""
        if self.ui.map_tab:
            self.ui.map_tab.set_map_image(image_path)

    def _handle_line_created(
        self, target_node: str, direction: str, properties: dict
    ) -> None:
        """Handle creation of a new map line relationship.

        Args:
            target_node: The node to link to
            direction: Relationship direction
            properties: Properties including line geometry
        """
        logger.debug(
            "Line created handler called",
            target=target_node,
            direction=direction,
            properties_preview=str(properties)[:100]
        )

        # Get current node name (the map node)
        source_node = self.ui.name_input.text().strip()
        logger.debug("Line creation source node", source_node=source_node)

        if not source_node:
            logger.warning("No source node, cannot create line relationship")
            return

        # Add new relationship row with SHOWS type (same as pins)
        logger.debug(
            "Adding line relationship row",
            rel_type="SHOWS",
            target=target_node,
            direction=direction
        )
        try:
            properties_json = json.dumps(properties)
            logger.debug(
                "Line properties JSON preview",
                json_preview=properties_json[:100]
            )
            self.ui.add_relationship_row(
                "SHOWS", target_node, direction, properties_json
            )
            logger.info("Line relationship created successfully")
        except Exception as e:
            logger.error(
                "Failed to create line relationship",
                error=str(e),
                exc_info=True
            )
            return

        # Update save state to reflect changes
        self.update_unsaved_changes_indicator()
        logger.info("Line relationship creation completed")

    def _handle_polygon_created(
        self, target_node: str, direction: str, properties: dict
    ) -> None:
        """Handle creation of a new map polygon relationship.

        Args:
            target_node: The node to link to
            direction: Relationship direction
            properties: Properties including polygon geometry and style
        """
        logger.info(f"Polygon created handler called for target: {target_node}")
        logger.info(f"Properties: {properties}")

        # Get current node name (the map node)
        source_node = self.ui.name_input.text().strip()
        logger.info(f"Source node: {source_node}")

        if not source_node:
            logger.warning("No source node, cannot create polygon relationship")
            return

        # Add new relationship row with SHOWS type (same as pins and lines)
        logger.info(
            f"Adding polygon relationship row: SHOWS, {target_node}, {direction}"
        )
        try:
            properties_json = json.dumps(properties)
            logger.info(f"Properties JSON: {properties_json[:100]}...")
            self.ui.add_relationship_row(
                "SHOWS", target_node, direction, properties_json
            )
            logger.info("Polygon relationship row added successfully")
        except Exception as e:
            logger.error(f"Error adding polygon relationship row: {e}")
            import traceback

            logger.error(traceback.format_exc())
            return

        # Update save state to reflect changes
        self.update_unsaved_changes_indicator()
        logger.info("Polygon relationship creation completed")
