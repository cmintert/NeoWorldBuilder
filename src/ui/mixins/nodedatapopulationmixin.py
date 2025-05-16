import json
from typing import Dict, Any, List

from PyQt6.QtWidgets import QTableWidgetItem

from structlog import get_logger

logger = get_logger(__name__)


class NodeDataPopulationMixin:

    def _populate_basic_info(self, node_data: Dict[str, Any]) -> None:
        """Populate basic node information fields."""
        self.ui.name_input.setText(node_data["name"])
        self.ui.description_input.setHtml(node_data["description"])
        self.ui.labels_input.setText(", ".join(node_data["labels"]))
        self.ui.tags_input.setText(", ".join(node_data["tags"]))

    def _populate_properties(self, properties: Dict[str, Any]) -> None:
        """Populate properties table."""
        logger.debug("_populate_properties: received properties", properties=properties)
        self.ui.properties_table.setRowCount(0)
        for key, value in properties.items():
            if self._should_display_property(key):
                self._add_property_row(key, value)

    def _should_display_property(self, key: str) -> bool:
        """Check if a property should be displayed in properties table."""
        return not key.startswith("_") and key not in self.config.RESERVED_PROPERTY_KEYS

    def _add_property_row(self, key: str, value: Any) -> None:
        """Add a row to the properties table."""
        logger.debug("_add_property_row: adding property", key=key, value=value)
        row = self.ui.properties_table.rowCount()
        self.ui.properties_table.insertRow(row)
        self.ui.properties_table.setItem(row, 0, QTableWidgetItem(key))
        self.ui.properties_table.setItem(row, 1, QTableWidgetItem(str(value)))
        delete_button = self.ui.create_delete_button(self.ui.properties_table, row)
        self.ui.properties_table.setCellWidget(row, 2, delete_button)

    def _populate_relationships(self, relationships: List[Dict[str, Any]]) -> None:
        """Populate relationships table."""
        self.ui.relationships_table.setRowCount(0)
        for rel in relationships:
            self.ui.add_relationship_row(
                rel.get("type", ""),
                rel.get("end", ""),
                rel.get("dir", ">"),
                json.dumps(rel.get("props", {})),
            )
