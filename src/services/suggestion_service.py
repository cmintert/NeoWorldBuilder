from typing import Dict, Any, Callable

from PyQt6.QtCore import QObject

from config.config import Config
from core.neo4jmodel import Neo4jModel
from core.neo4jworkers import SuggestionWorker
from models.suggestion_model import SuggestionUIHandler
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
        ui_handler: SuggestionUIHandler,
    ) -> None:
        super().__init__()
        self.model = model
        self.config = config
        self.worker_manager = worker_manager
        self.error_handler = error_handler
        self.ui_handler = ui_handler

    def show_suggestions_modal(self, node_data: Dict[str, Any]) -> None:
        """Show the suggestions modal dialog and handle the results."""
        if not node_data:
            return

        self.get_suggestions(node_data, self._handle_suggestions)

    def get_suggestions(
        self,
        node_data: Dict[str, Any],
        suggestions_callback: Callable[[Dict[str, Any]], None],
    ) -> None:
        """Get suggestions for a node with loading state management."""
        if not node_data:
            return

        self.ui_handler.show_loading(True)
        worker = SuggestionWorker(self.model._uri, self.model._auth, node_data)
        worker.suggestions_ready.connect(suggestions_callback)

        operation = WorkerOperation(
            worker=worker,
            success_callback=None,  # Using direct signal connection instead
            error_callback=self._handle_error,
            finished_callback=lambda: self.ui_handler.show_loading(False),
            operation_name="suggestions",
        )

        self.worker_manager.execute_worker("suggestions", operation)

    def _handle_suggestions(self, suggestions: Dict[str, Any]) -> None:
        """Handle received suggestions."""
        if not suggestions or all(not suggestions[key] for key in suggestions):
            self.ui_handler.show_message(
                "No Suggestions", "No suggestions were found for this node."
            )
            return

        result = self.ui_handler.show_suggestion_dialog(suggestions)
        if result.success and result.selected_suggestions:
            self._apply_suggestions(result.selected_suggestions)
            self.ui_handler.show_message(
                "Success", "Selected suggestions have been applied."
            )

    def _apply_suggestions(self, selected: Dict[str, Any]) -> None:
        """Apply selected suggestions to the UI."""
        # Apply tags
        if tags := selected.get("tags"):
            self.ui_handler.update_tags(tags)

        # Apply properties
        if properties := selected.get("properties"):
            for key, value in properties.items():
                self.ui_handler.add_property(key, value)

        # Apply relationships
        if relationships := selected.get("relationships"):
            for rel_type, target, direction, props in relationships:
                self.ui_handler.add_relationship(rel_type, target, direction, props)

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
