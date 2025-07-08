import json
from typing import Dict, Any, Optional

from ui.components.map_component.map_tab import MapTab
from structlog import get_logger

logger = get_logger(__name__)


class MapMixin:

    def _ensure_map_tab_exists(self) -> None:
        """Create map tab if it doesn't exist."""
        if not self.ui.map_tab:
            print("Creating map tab and connecting signals...")
            self.ui.map_tab = MapTab(controller=self)

            print("Connecting map_image_changed signal")
            self.ui.map_tab.map_image_changed.connect(self.ui._handle_map_image_changed)

            print("Connecting pin_clicked signal")
            self.ui.map_tab.pin_clicked.connect(self._handle_pin_click)

            # Add new connection for pin creation
            print("Connecting pin_created signal")
            self.ui.map_tab.pin_created.connect(self._handle_pin_created)

            print("Connecting line_created signal")
            self.ui.map_tab.line_created.connect(self._handle_line_created)

            # Check if connections were successful
            print(f"Signal connections status:")
            print(
                f"- map_image_changed: {self.ui.map_tab.map_image_changed.receivers() > 0}"
            )
            print(f"- pin_clicked: {self.ui.map_tab.pin_clicked.receivers() > 0}")
            print(f"- pin_created: {self.ui.map_tab.pin_created.receivers() > 0}")
            print(f"- line_created: {self.ui.map_tab.line_created.receivers() > 0}")

            self.ui.tabs.addTab(self.ui.map_tab, "Map")

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
        logger.info(f"Pin click handler called for target: {target_node} - NAVIGATING TO NODE")
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
        print(
            f"*** _handle_line_created called with target={target_node}, direction={direction}"
        )
        print(f"*** Properties: {properties}")

        # Get current node name (the map node)
        source_node = self.ui.name_input.text().strip()
        print(f"Source node: {source_node}")

        if not source_node:
            print("No source node, cannot create relationship")
            return

        # Add new relationship row with SHOWS type (same as pins)
        print(f"Adding relationship row: SHOWS, {target_node}, {direction}")
        try:
            properties_json = json.dumps(properties)
            print(f"Properties JSON: {properties_json[:100]}...")
            self.ui.add_relationship_row(
                "SHOWS", target_node, direction, properties_json
            )
            print("Relationship row added successfully")
        except Exception as e:
            print(f"Error adding relationship row: {e}")
            import traceback

            print(traceback.format_exc())
            return

        # Update save state to reflect changes
        self.update_unsaved_changes_indicator()
        print("Line relationship creation completed")
