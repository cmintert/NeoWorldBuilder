import json
from typing import Dict, Any, Callable, List
from core.neo4jmodel import Neo4jModel
from core.neo4jworkers import SuggestionWorker


class SuggestionService:
    """
    Service class to handle suggestions, including fetching and applying suggestions.
    """

    def __init__(self, model: Neo4jModel):
        """
        Initialize the SuggestionService with the Neo4jModel.

        Args:
            model (Neo4jModel): The Neo4jModel instance.
        """
        self.model = model

    def generate_suggestions(self, node_data: Dict[str, Any], callback: Callable, error_callback: Callable) -> SuggestionWorker:
        """
        Generate suggestions for a given node using a worker.

        Args:
            node_data (dict): Node data including properties and relationships.
            callback (function): Function to call with the result.
            error_callback (function): Function to call in case of an error.

        Returns:
            SuggestionWorker: A worker that will execute the suggestion generation.
        """
        return self.model.generate_suggestions(node_data, callback, error_callback)

    def apply_suggestions(self, suggestions: Dict[str, Any], node_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply the given suggestions to the node data.

        Args:
            suggestions (dict): The suggestions dictionary containing tags, properties, and relationships.
            node_data (dict): The original node data.

        Returns:
            dict: The updated node data with applied suggestions.
        """
        # Update tags
        existing_tags = self._parse_comma_separated(node_data.get("tags", ""))
        new_tags = list(set(existing_tags + suggestions.get("tags", [])))
        node_data["tags"] = ", ".join(new_tags)

        # Update properties
        for key, value in suggestions.get("properties", {}).items():
            node_data["additional_properties"][key] = value

        # Update relationships
        for rel in suggestions.get("relationships", []):
            rel_type, target, direction, props = rel
            node_data["relationships"].append(
                (rel_type, target, direction, json.dumps(props))
            )

        return node_data

    def _parse_comma_separated(self, text: str) -> List[str]:
        """
        Parse comma-separated input.

        Args:
            text (str): The comma-separated input text.

        Returns:
            List[str]: The parsed list of strings.
        """
        return [item.strip() for item in text.split(",") if item.strip()]
