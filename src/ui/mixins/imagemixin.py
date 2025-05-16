from typing import Dict, Any

from structlog import get_logger

logger = get_logger(__name__)


class ImageMixin:

    def _populate_basic_info_image(self, node_properties: Dict[str, Any]) -> None:
        """Set node's image if available."""
        image_path = node_properties.get("imagepath")
        self.ui.image_group.set_basic_image(image_path)

    def _handle_basic_image_changed(self, image_path: str) -> None:
        """Handle image change signal from ImageGroup."""
        self.all_props["imagepath"] = image_path
        self.update_unsaved_changes_indicator()

    def _handle_basic_image_removed(self) -> None:
        """Handle image removal signal from ImageGroup."""
        self.all_props["imagepath"] = None
        self.update_unsaved_changes_indicator()
