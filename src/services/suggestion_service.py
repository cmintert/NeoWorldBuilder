from typing import Dict, Any, Callable

from PyQt6.QtCore import QObject

from config.config import Config
from core.neo4jmodel import Neo4jModel
from core.neo4jworkers import SuggestionWorker
from models.worker_model import WorkerOperation
from services.worker_manager_service import WorkerManagerService
from utils.error_handler import ErrorHandler


class SuggestionService(QObject):
    def __init__(
        self,
        model: Neo4jModel,
        config: Config,
        worker_manager: WorkerManagerService,
        error_handler: ErrorHandler,
    ) -> None:
        super().__init__()
        self.model = model
        self.config = config
        self.worker_manager = worker_manager
        self.error_handler = error_handler

    def get_suggestions(
        self,
        node_data: Dict[str, Any],
        loading_callback: Callable[[bool], None],
        suggestions_callback: Callable[[Dict[str, Any]], None],
    ) -> None:
        """Get suggestions for a node with loading state management."""
        if not node_data:
            return

        loading_callback(True)
        worker = SuggestionWorker(self.model._uri, self.model._auth, node_data)
        worker.suggestions_ready.connect(suggestions_callback)

        operation = WorkerOperation(
            worker=worker,
            success_callback=None,  # Using direct signal connection instead
            error_callback=self._handle_error,
            finished_callback=lambda: loading_callback(False),
            operation_name="suggestions",
        )

        self.worker_manager.execute_worker("suggestions", operation)

    def process_selected_suggestions(
        self, selected: Dict[str, Any], current_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Process and merge selected suggestions with current data."""
        try:
            # Update tags
            existing_tags = current_data.get("tags", [])
            new_tags = list(set(existing_tags + selected["tags"]))
            current_data["tags"] = new_tags

            # Update properties
            current_props = current_data.get("additional_properties", {})
            for key, value in selected["properties"].items():
                current_props[key] = value
            current_data["additional_properties"] = current_props

            # Update relationships
            current_rels = current_data.get("relationships", [])
            for rel_type, target, direction, props in selected["relationships"]:
                current_rels.append((rel_type, target, direction, props))
            current_data["relationships"] = current_rels

            return current_data
        except Exception as e:
            self.error_handler.handle_error(f"Error processing suggestions: {str(e)}")

    def _handle_error(self, message: str) -> None:
        """Handle errors during suggestion operations."""
        self.error_handler.handle_error(f"Suggestion error: {message}")
