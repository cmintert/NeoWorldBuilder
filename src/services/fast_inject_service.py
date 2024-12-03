import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional

from PyQt6.QtWidgets import QTableWidgetItem


class FastInjectService:
    """Service for loading and applying Fast Inject templates."""

    def __init__(self) -> None:
        """Initialize the Fast Inject service."""
        self.logger = logging.getLogger(__name__)

    def load_template(self, file_path: Path) -> Optional[Dict[str, Any]]:
        """Load a Fast Inject template from a file.

        Args:
            file_path: Path to the .fi template file

        Returns:
            Dict containing the template data if successful, None if failed

        Raises:
            ValueError: If the file format is invalid
            FileNotFoundError: If the file doesn't exist
        """
        try:
            if not file_path.suffix == ".fi":
                raise ValueError("Invalid file format. Must be .fi file")

            with open(file_path, "r", encoding="utf-8") as f:
                template = json.load(f)

            self.validate_template(template)
            return template

        except Exception as e:
            self.logger.error(f"Failed to load template: {str(e)}")
            raise

    def validate_template(self, template: Dict[str, Any]) -> None:
        """Validate the structure of a template."""
        required_keys = {"name", "description", "content"}
        content_keys = {"labels", "tags", "properties"}

        if not all(key in template for key in required_keys):
            raise ValueError(f"Template must contain keys: {required_keys}")

        if not all(key in template["content"] for key in content_keys):
            raise ValueError(f"Template content must contain keys: {content_keys}")

        if not isinstance(template["content"]["labels"], list):
            raise ValueError("Labels must be a list")

        if not isinstance(template["content"]["tags"], list):
            raise ValueError("Tags must be a list")

        if not isinstance(template["content"]["properties"], dict):
            raise ValueError("Properties must be a dictionary")

    def apply_template(
        self,
        ui: "WorldBuildingUI",
        template: Dict[str, Any],
        selected_sections: set[str],
    ) -> None:
        """Apply template data to the current UI state.

        Args:
            ui: The main UI instance
            template: Template data to apply
            selected_sections: Set of sections to apply ('labels', 'tags', 'properties')
        """
        content = template["content"]

        # Apply labels if selected
        if "labels" in selected_sections:
            current_labels = {
                label.strip()
                for label in ui.labels_input.text().split(",")
                if label.strip()
            }
            new_labels = current_labels.union(content["labels"])
            ui.labels_input.setText(", ".join(new_labels))

        # Apply tags if selected
        if "tags" in selected_sections:
            current_tags = {
                tag.strip() for tag in ui.tags_input.text().split(",") if tag.strip()
            }
            new_tags = current_tags.union(content["tags"])
            ui.tags_input.setText(", ".join(new_tags))

        # Apply properties if selected
        if "properties" in selected_sections:
            existing_properties = set()
            for row in range(ui.properties_table.rowCount()):
                if key_item := ui.properties_table.item(row, 0):
                    existing_properties.add(key_item.text())

            # Add new properties
            for key, value in content["properties"].items():
                if key not in existing_properties:
                    row = ui.properties_table.rowCount()
                    ui.properties_table.insertRow(row)
                    ui.properties_table.setItem(row, 0, QTableWidgetItem(key))
                    ui.properties_table.setItem(row, 1, QTableWidgetItem(str(value)))
                    delete_button = ui.create_delete_button(ui.properties_table, row)
                    ui.properties_table.setCellWidget(row, 2, delete_button)
