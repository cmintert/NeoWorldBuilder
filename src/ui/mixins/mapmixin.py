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

        self.ui.map_tab = MapTab(controller=self)

        # Connect all signals - this is the authoritative list
        self.ui.map_tab.map_image_changed.connect(self.ui._handle_map_image_changed)
        self.ui.map_tab.pin_clicked.connect(self._handle_pin_click)
        self.ui.map_tab.pin_created.connect(self._handle_pin_created)
        self.ui.map_tab.line_created.connect(self._handle_line_created)
        self.ui.map_tab.polygon_created.connect(self._handle_polygon_created)

        self.ui.tabs.addTab(self.ui.map_tab, "Map")
        logger.info("Map tab created with all signals connected")

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
        source_node = self.ui.name_input.text().strip()

        if not source_node:
            logger.warning("Cannot create pin: no source node selected")
            return

        try:
            self.ui.add_relationship_row(
                "SHOWS", target_node, direction, json.dumps(properties)
            )
            self.update_unsaved_changes_indicator()
            logger.info(f"Pin relationship created: {source_node} → {target_node}")
        except Exception as e:
            logger.error("Failed to create pin relationship", error=str(e), exc_info=True)

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
        source_node = self.ui.name_input.text().strip()

        if not source_node:
            logger.warning("Cannot create line: no source node selected")
            return

        try:
            self.ui.add_relationship_row(
                "SHOWS", target_node, direction, json.dumps(properties)
            )
            self.update_unsaved_changes_indicator()
            logger.info(f"Line relationship created: {source_node} → {target_node}")
        except Exception as e:
            logger.error("Failed to create line relationship", error=str(e), exc_info=True)

    def _handle_polygon_created(
        self, target_node: str, direction: str, properties: dict
    ) -> None:
        """Handle creation of a new map polygon relationship.

        Args:
            target_node: The node to link to
            direction: Relationship direction
            properties: Properties including polygon geometry and style
        """
        source_node = self.ui.name_input.text().strip()

        if not source_node:
            logger.warning("Cannot create polygon: no source node selected")
            return

        try:
            self.ui.add_relationship_row(
                "SHOWS", target_node, direction, json.dumps(properties)
            )
            self.update_unsaved_changes_indicator()
            logger.info(f"Polygon relationship created: {source_node} → {target_node}")
        except Exception as e:
            logger.error("Failed to create polygon relationship", error=str(e), exc_info=True)
