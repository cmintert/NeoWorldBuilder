from abc import abstractmethod
from typing import Any, Dict


from structlog import get_logger

logger = get_logger(__name__)


class NodeDataExtractionMixin:
    """
    Mixin providing node data handling functionality.

    Required properties that must be implemented by inheriting class:
    - ui: The UI instance
    - all_props: Dictionary of all properties
    - config: Configuration instance
    """

    @property
    @abstractmethod
    def ui(self):
        """The UI instance."""
        pass

    @property
    @abstractmethod
    def all_props(self):
        """Dictionary of all properties."""
        pass

    @property
    @abstractmethod
    def config(self):
        """Configuration instance."""
        pass

    def extract_element_id(self, data: dict) -> str | None:
        """Extract element_id from node data."""
        try:
            node = data[0]["n"]
            node_str = str(node)
            start_marker = "element_id='"
            end_marker = "'"

            start_pos = node_str.find(start_marker) + len(start_marker)
            end_pos = node_str.find(end_marker, start_pos)

            if start_pos == -1 or end_pos == -1:
                return None

            return node_str[start_pos:end_pos]

        except (IndexError, KeyError, AttributeError) as e:
            logger.error("Error extracting element_id", error=str(e))
            return None

    def _extract_node_data(self, record: Any) -> Dict[str, Any]:
        """Extract and organize node data from database record."""
        node = record["n"]
        node_properties = dict(node)

        return {
            "node_properties": node_properties,
            "name": node_properties.get("name", ""),
            "description": node_properties.get("description", ""),
            "tags": node_properties.get("tags", []),
            "labels": record["labels"],
            "relationships": record["relationships"],
            "properties": record["all_props"],
        }
