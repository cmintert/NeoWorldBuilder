from PyQt6.QtCore import QObject, QTimer, pyqtSlot, Qt
from PyQt6.QtGui import QStringListModel, QCompleter
from PyQt6.QtWidgets import QLineEdit

from core.neo4jmodel import Neo4jModel


class SearchController(QObject):
    """
    Controller class to handle auto-completion and search functionality.
    """

    def __init__(self, model: Neo4jModel, ui: "WorldBuildingUI"):
        """
        Initialize the SearchController with the Neo4j model and UI.

        Args:
            model (Neo4jModel): The Neo4j model instance.
            ui (WorldBuildingUI): The UI instance.
        """
        super().__init__()
        self.model = model
        self.ui = ui
        self.current_search_worker = None
        self._initialize_completer()
        self._initialize_target_completer()
        self._setup_debounce_timer()

    def _initialize_completer(self):
        """
        Initialize name auto-completion.
        """
        self.node_name_model = QStringListModel()
        self.completer = QCompleter(self.node_name_model)
        self.completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.ui.name_input.setCompleter(self.completer)
        self.completer.activated.connect(self.on_completer_activated)

    def _initialize_target_completer(self):
        """
        Initialize target auto-completion for relationship table.
        """
        self.target_name_model = QStringListModel()
        self.target_completer = QCompleter(self.target_name_model)
        self.target_completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.target_completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.target_completer.activated.connect(self.on_target_completer_activated)

    def _add_target_completer_to_row(self, row):
        """
        Add target completer to the target input field in the relationship table.

        Args:
            row (int): The row number where the completer will be added.
        """
        target_item = self.ui.relationships_table.item(row, 1)
        if target_item:
            target_text = target_item.text()
            line_edit = QLineEdit(target_text)
            line_edit.setCompleter(self.target_completer)
            line_edit.textChanged.connect(
                lambda text: self._fetch_matching_target_nodes(text)
            )
            self.ui.relationships_table.setCellWidget(row, 1, line_edit)

    def on_target_completer_activated(self, text: str):
        """
        Handle target completer selection.

        Args:
            text (str): The selected text from the completer.
        """
        current_row = self.ui.relationships_table.currentRow()
        if current_row >= 0:
            self.ui.relationships_table.item(current_row, 1).setText(text)

    def _fetch_matching_target_nodes(self, text: str):
        """
        Fetch matching target nodes for auto-completion.

        Args:
            text (str): The text to match against node names.
        """
        if not text:
            return

        # Cancel any existing search worker
        if self.current_search_worker:
            self.current_search_worker.cancel()
            self.current_search_worker.wait()

        self.current_search_worker = self.model.fetch_matching_node_names(
            text,
            self.ui.controller.config.NEO4J_MATCH_NODE_LIMIT,
            self._handle_target_autocomplete_results,
        )
        self.current_search_worker.error_occurred.connect(self.ui.controller.handle_error)
        self.current_search_worker.start()

    @pyqtSlot(list)
    def _handle_target_autocomplete_results(self, records: list):
        """
        Handle target autocomplete results.

        Args:
            records (list): The list of matching records.
        """
        try:
            names = [record["name"] for record in records]
            self.target_name_model.setStringList(names)
        except Exception as e:
            self.ui.controller.handle_error(f"Error processing target autocomplete results: {str(e)}")

    def _setup_debounce_timer(self):
        """
        Setup debounce timer for search.
        """
        self.name_input_timer = QTimer()
        self.name_input_timer.setSingleShot(True)
        self.name_input_timer.timeout.connect(self._fetch_matching_nodes)
        self.name_input_timer.setInterval(
            self.ui.controller.config.TIMING_NAME_INPUT_DEBOUNCE_TIME_MS
        )

    def debounce_name_input(self, text: str):
        """
        Debounce name input for search.

        Args:
            text (str): The input text.
        """
        self.name_input_timer.stop()
        if text.strip():
            self.name_input_timer.start()

    def _fetch_matching_nodes(self):
        """
        Fetch matching nodes for auto-completion.
        """
        text = self.ui.name_input.text().strip()
        if not text:
            return

        # Cancel any existing search worker
        if self.current_search_worker:
            self.current_search_worker.cancel()
            self.current_search_worker.wait()

        self.current_search_worker = self.model.fetch_matching_node_names(
            text, self.ui.controller.config.NEO4J_MATCH_NODE_LIMIT, self._handle_autocomplete_results
        )
        self.current_search_worker.error_occurred.connect(self.ui.controller.handle_error)
        self.current_search_worker.start()

    @pyqtSlot(list)
    def _handle_autocomplete_results(self, records: list):
        """
        Handle autocomplete results.

        Args:
            records (list): The list of matching records.
        """
        try:
            names = [record["name"] for record in records]
            self.node_name_model.setStringList(names)
        except Exception as e:
            self.ui.controller.handle_error(f"Error processing autocomplete results: {str(e)}")

    def on_completer_activated(self, text: str):
        """
        Handle completer selection.

        Args:
            text (str): The selected text from the completer.
        """
        if text:
            self.ui.name_input.setText(text)
            self.ui.controller.load_node_data()
