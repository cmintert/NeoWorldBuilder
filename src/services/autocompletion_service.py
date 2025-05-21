import logging
from typing import Any, List, Optional, Callable

from PyQt6.QtCore import QTimer, QStringListModel
from PyQt6.QtWidgets import QLineEdit, QTableWidget
from structlog import get_logger

from config.config import Config
from core.neo4jmodel import Neo4jModel
from models.completer_model import AutoCompletionUIHandler, CompleterInput
from services.name_cache_service import NameCacheService
from services.worker_manager_service import WorkerManagerService

logger = get_logger(__name__)


class AutoCompletionService:
    """
    Manages auto-completion functionality for node names and relationship targets.
    """

    def __init__(
        self,
        model: Neo4jModel,
        config: Config,
        worker_manager: WorkerManagerService,
        ui_handler: AutoCompletionUIHandler,
        name_cache_service: NameCacheService,
        error_handler: Optional[Callable[[str], None]] = None,
    ) -> None:
        self.model = model
        self.config = config
        self.worker_manager = worker_manager
        self.name_cache_service = name_cache_service
        self.ui_handler = ui_handler
        self.error_handler = error_handler or self._default_error_handler

        # Initialize models for both completers
        self.node_name_model = QStringListModel()
        self.target_name_model = QStringListModel()

        # Initialize debounce timer
        self.debounce_timer = self._setup_debounce_timer()
        self._current_completion_text: Optional[str] = None
        self._for_target: bool = False

    def initialize_node_completer(self, input_widget: QLineEdit) -> None:
        """Initialize a completer for node names and attach it to an input widget."""
        completer_input = CompleterInput(
            widget=input_widget, model=self.node_name_model
        )
        completer = self.ui_handler.create_completer(completer_input)
        input_widget.setCompleter(completer)

        # Connect text changes to debounced search
        input_widget.textChanged.connect(
            lambda text: self.debounce_completion(text, False)
        )

    def initialize_target_completer(self, input_widget: QLineEdit) -> None:
        """Initialize a completer for relationship targets."""
        completer_input = CompleterInput(
            widget=input_widget, model=self.target_name_model
        )
        completer = self.ui_handler.create_completer(completer_input)
        input_widget.setCompleter(completer)

        # Connect text changes to debounced search
        input_widget.textChanged.connect(
            lambda text: self.debounce_completion(text, True)
        )

    def add_target_completer_to_row(self, table: QTableWidget, row: int) -> None:
        """Add target completer to a specific row in the relationship table."""
        if target_item := table.item(row, 1):
            line_edit = self.ui_handler.setup_target_cell_widget(
                table, row, 1, target_item.text()
            )
            self.initialize_target_completer(line_edit)

    # Rest of the original AutoCompletionService methods remain unchanged
    def debounce_completion(self, text: str, for_target: bool) -> None:
        """Debounce the completion request."""
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

        # Use cached names
        cached_names = self.name_cache_service.get_cached_names()

        # Algorythm that matches partial inputs to cached names
        matching_names: List = []
        text_length = len(text)
        for name in cached_names:
            if text.lower() in name[:text_length].lower():
                matching_names.append(name)

        model.setStringList(matching_names)

    def _setup_debounce_timer(self) -> QTimer:
        """Setup and return the debounce timer."""
        timer = QTimer()
        timer.setSingleShot(True)
        timer.setInterval(self.config.NAME_INPUT_DEBOUNCE_TIME_MS)
        timer.timeout.connect(self.fetch_matching_nodes)
        return timer

    def _handle_results(self, records: List[Any], model: QStringListModel) -> None:
        """Handle autocomplete results for both node and target completion."""
        try:
            names = [record["name"] for record in records]
            model.setStringList(names)
        except Exception as e:
            self._handle_error(f"Error processing autocomplete results: {str(e)}")

    def _handle_error(self, message: str) -> None:
        """Handle errors during auto-completion operations."""
        if self.error_handler:
            self.error_handler(message)
        self._default_error_handler(message)

    def _default_error_handler(self, message: str) -> None:
        """Default error handler that logs errors."""
        logging.error(f"Auto-completion error: {message}")
