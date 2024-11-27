import logging
from typing import Any, List, Optional, Callable

from PyQt6.QtCore import Qt, QTimer, QStringListModel
from PyQt6.QtWidgets import QLineEdit, QTableWidget, QCompleter

from config.config import Config
from core.neo4jmodel import Neo4jModel
from models.worker_model import WorkerOperation
from services.worker_manager_service import WorkerManagerService


class AutoCompletionService:
    """
    Manages auto-completion functionality for node names and relationship targets.

    This service centralizes all auto-completion related functionality, including:
    - Node name completion
    - Relationship target completion
    - Debounce handling
    - Result processing
    """

    def __init__(
        self,
        model: Neo4jModel,
        config: Config,
        worker_manager: WorkerManagerService,
        error_handler: Optional[Callable[[str], None]] = None,
    ) -> None:
        """
        Initialize the auto-completion service.

        Args:
            model: The Neo4j model instance
            config: Application configuration
            worker_manager: Worker management service
            error_handler: Optional callback for error handling
        """
        self.model = model
        self.config = config
        self.worker_manager = worker_manager
        self.error_handler = error_handler or self._default_error_handler

        # Initialize models for both completer
        self.node_name_model = QStringListModel()
        self.target_name_model = QStringListModel()

        # Initialize debounce timer
        self.debounce_timer = self._setup_debounce_timer()
        self._current_completion_text: Optional[str] = None
        self._for_target: bool = False

    def initialize_node_completer(self, input_widget: QLineEdit) -> None:
        """
        Initialize a completer for node names and attach it to an input widget.

        Args:
            input_widget: The QLineEdit widget to attach the completer to
        """
        completer = self._create_base_completer(self.node_name_model)
        input_widget.setCompleter(completer)

        # Connect text changes to debounced search
        input_widget.textChanged.connect(
            lambda text: self.debounce_completion(text, False)
        )

    def initialize_target_completer(self, input_widget: QLineEdit) -> None:
        """
        Initialize a completer for relationship targets and attach it to an input widget.

        Args:
            input_widget: The QLineEdit widget to attach the completer to
        """
        completer = self._create_base_completer(self.target_name_model)
        input_widget.setCompleter(completer)

        # Connect text changes to debounced search
        input_widget.textChanged.connect(
            lambda text: self.debounce_completion(text, True)
        )

    def add_target_completer_to_row(self, table: QTableWidget, row: int) -> None:
        """
        Add target completer to a specific row in the relationship table.

        Args:
            table: The relationship table widget
            row: The row number to add the completer to
        """
        if target_item := table.item(row, 1):
            line_edit = QLineEdit(target_item.text())
            self.initialize_target_completer(line_edit)
            table.setCellWidget(row, 1, line_edit)

    def debounce_completion(self, text: str, for_target: bool) -> None:
        """
        Debounce the completion request.

        Args:
            text: The text to search for
            for_target: Whether this is for target completion
        """
        self.debounce_timer.stop()
        self._current_completion_text = text
        self._for_target = for_target

        if text.strip():
            self.debounce_timer.start()

    def fetch_matching_nodes(self) -> None:
        """Fetch matching nodes based on current completion text."""
        if not self._current_completion_text:
            return

        text = self._current_completion_text.strip()
        model = self.target_name_model if self._for_target else self.node_name_model

        worker = self.model.fetch_matching_node_names(
            text,
            self.config.MATCH_NODE_LIMIT,
            lambda records: self._handle_results(records, model),
        )

        operation = WorkerOperation(
            worker=worker,
            success_callback=lambda records: self._handle_results(records, model),
            error_callback=self._handle_error,
            operation_name="node_search",
        )

        self.worker_manager.execute_worker("search", operation)

    # Private methods
    def _create_base_completer(self, model: QStringListModel) -> QCompleter:
        """
        Create a base completer with standard configuration.

        Args:
            model: The string list model to use for completion

        Returns:
            A configured QCompleter instance
        """
        completer = QCompleter(model)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        return completer

    def _setup_debounce_timer(self) -> QTimer:
        """
        Setup and return the debounce timer.

        Returns:
            A configured QTimer instance
        """
        timer = QTimer()
        timer.setSingleShot(True)
        timer.setInterval(self.config.NAME_INPUT_DEBOUNCE_TIME_MS)
        timer.timeout.connect(self.fetch_matching_nodes)
        return timer

    def _handle_results(self, records: List[Any], model: QStringListModel) -> None:
        """
        Handle autocomplete results for both node and target completion.

        Args:
            records: The list of matching records
            model: The model to update with results
        """
        try:
            names = [record["name"] for record in records]
            model.setStringList(names)
        except Exception as e:
            self._handle_error(f"Error processing autocomplete results: {str(e)}")

    def _handle_error(self, message: str) -> None:
        """
        Handle errors during auto-completion operations.

        Args:
            message: The error message
        """
        if self.error_handler:
            self.error_handler(message)
        self._default_error_handler(message)

    def _default_error_handler(self, message: str) -> None:
        """
        Default error handler that logs errors.

        Args:
            message: The error message to log
        """
        logging.error(f"Auto-completion error: {message}")
