import json
import logging
from typing import Optional, Dict, Any, List, Tuple

from PyQt6.QtCore import QObject, QStringListModel, Qt, pyqtSlot, QTimer
from PyQt6.QtGui import QStandardItemModel, QStandardItem, QIcon
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QCompleter,
    QLineEdit,
    QMessageBox,
    QTableWidgetItem,
    QFileDialog,
)

from ui.dialogs import ConnectionSettingsDialog
from utils.exporters import Exporter
from ui.node_controller import NodeController
from ui.search_controller import SearchController
from ui.suggestion_controller import SuggestionController
from ui.tree_controller import TreeController
from ui.utility_controller import UtilityController
from services.node_service import NodeService
from services.relationship_service import RelationshipService
from services.search_service import SearchService
from services.suggestion_service import SuggestionService
from services.utility_service import UtilityService


class WorldBuildingController(QObject):
    """
    Controller class managing interaction between UI and Neo4j model using QThread workers.

    Args:
        ui (WorldBuildingUI): The UI instance.
        model (Neo4jModel): The Neo4j model instance.
        config (Config): The configuration instance.
    """

    def __init__(
        self,
        ui: "WorldBuildingUI",
        model: "Neo4jModel",
        config: "Config",
        app_instance: "WorldBuildingApp",
    ) -> None:
        """
        Initialize the controller with UI, model, and configuration.

        Args:
            ui (WorldBuildingUI): The UI instance.
            model (Neo4jModel): The Neo4j model instance.
            config (Config): The configuration instance.
        """
        super().__init__()
        self.ui = ui
        self.model = model
        self.config = config
        self.app_instance = app_instance
        self.exporter = Exporter(self.ui, self.config)
        self.current_image_path: Optional[str] = None
        self.original_node_data: Optional[Dict[str, Any]] = None
        self.ui.controller = self

        # Initialize services
        self.node_service = NodeService(self.model)
        self.relationship_service = RelationshipService(self.model)
        self.search_service = SearchService(self.model)
        self.suggestion_service = SuggestionService(self.model)
        self.utility_service = UtilityService(self.config)

        # Initialize controllers
        self.node_controller = NodeController(self.node_service)
        self.search_controller = SearchController(self.search_service, self.ui)
        self.suggestion_controller = SuggestionController(self.suggestion_service, self.ui)
        self.tree_controller = TreeController(self.relationship_service, self.ui)
        self.utility_controller = UtilityController(self.ui, self.config)

        # Initialize UI state
        self._initialize_tree_view()
        self._initialize_completer()
        self._initialize_target_completer()
        self._setup_debounce_timer()
        self._connect_signals()
        self._load_default_state()

    #############################################
    # 1. Initialization Methods
    #############################################

    def _initialize_tree_view(self) -> None:
        """
        Initialize the tree view model.
        """
        self.tree_model = QStandardItemModel()
        self.tree_model.setHorizontalHeaderLabels([self.tree_controller.NODE_RELATIONSHIPS_HEADER])
        self.ui.tree_view.setModel(self.tree_model)

        self.ui.tree_view.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection
        )
        self.ui.tree_view.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectItems
        )

        # connect selection signals
        self.ui.tree_view.selectionModel().selectionChanged.connect(
            self.tree_controller.on_tree_selection_changed
        )

        self.ui.tree_view.setUniformRowHeights(True)
        self.ui.tree_view.setItemsExpandable(True)
        self.ui.tree_view.setAllColumnsShowFocus(True)
        self.ui.tree_view.setHeaderHidden(False)

    def _initialize_completer(self) -> None:
        """
        Initialize name auto-completion.
        """
        self.node_name_model = QStringListModel()
        self.completer = QCompleter(self.node_name_model)
        self.completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.ui.name_input.setCompleter(self.completer)
        self.completer.activated.connect(self.search_controller.on_completer_activated)

    def _initialize_target_completer(self) -> None:
        """
        Initialize target auto-completion for relationship table.
        """
        self.target_name_model = QStringListModel()
        self.target_completer = QCompleter(self.target_name_model)
        self.target_completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.target_completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.target_completer.activated.connect(self.search_controller.on_target_completer_activated)

    def _add_target_completer_to_row(self, row: int) -> None:
        """
        Add target completer to the target input field in the relationship table.

        Args:
            row (int): The row number where the completer will be added.
        """
        self.search_controller._add_target_completer_to_row(row)

    def _setup_debounce_timer(self) -> None:
        """
        Setup debounce timer for search.
        """
        self.name_input_timer = QTimer()
        self.name_input_timer.setSingleShot(True)
        self.name_input_timer.timeout.connect(self.search_controller._fetch_matching_nodes)
        self.name_input_timer.setInterval(self.config.NAME_INPUT_DEBOUNCE_TIME_MS)

    def _connect_signals(self) -> None:
        """
        Connect all UI signals to handlers.
        """
        # Main buttons
        self.ui.save_button.clicked.connect(self.node_controller.save_node)
        self.ui.delete_button.clicked.connect(self.node_controller.delete_node)

        # Image handling
        self.ui.change_image_button.clicked.connect(self.utility_controller.change_image)
        self.ui.delete_image_button.clicked.connect(self.utility_controller.delete_image)

        # Name input and autocomplete
        self.ui.name_input.textChanged.connect(self.search_controller.debounce_name_input)
        self.ui.name_input.editingFinished.connect(self.node_controller.load_node_data)

        # Table buttons
        self.ui.add_rel_button.clicked.connect(self.ui.add_relationship_row)

        # connect the suggest button
        self.ui.suggest_button.clicked.connect(self.suggestion_controller.show_suggestions_modal)

        # Check for unsaved changes
        self.ui.name_input.textChanged.connect(self.node_controller.update_unsaved_changes_indicator)
        self.ui.description_input.textChanged.connect(
            self.node_controller.update_unsaved_changes_indicator
        )
        self.ui.labels_input.textChanged.connect(self.node_controller.update_unsaved_changes_indicator)
        self.ui.tags_input.textChanged.connect(self.node_controller.update_unsaved_changes_indicator)
        self.ui.properties_table.itemChanged.connect(
            self.node_controller.update_unsaved_changes_indicator
        )
        self.ui.relationships_table.itemChanged.connect(
            self.node_controller.update_unsaved_changes_indicator
        )

        # Depth spinbox change
        self.ui.depth_spinbox.valueChanged.connect(self.tree_controller.on_depth_changed)

    def _load_default_state(self) -> None:
        """
        Initialize default UI state.
        """
        self.ui.name_input.clear()
        self.ui.description_input.clear()
        self.ui.labels_input.clear()
        self.ui.tags_input.clear()
        self.ui.properties_table.setRowCount(0)
        self.ui.relationships_table.setRowCount(0)
        self.tree_controller.refresh_tree_view()

    #############################################
    # 2. Export Methods
    #############################################

    def _export(self, format_type: str) -> None:
        """
        Generic export method that handles all export formats.

        Args:
            format_type (str): The type of export format ('database.json', 'txt', 'csv', 'pdf')
        """
        selected_nodes = self.get_selected_nodes()
        if not selected_nodes:
            QMessageBox.warning(self.ui, "Warning", "No nodes selected for export.")
            return

        try:
            self.exporter.export(
                format_type, selected_nodes, self.node_controller._collect_node_data_for_export
            )
        except ValueError as e:
            self.handle_error(f"Export error: {str(e)}")

    def export_as_json(self) -> None:
        """
        Export selected nodes as JSON.
        """
        self._export("database.json")

    def export_as_txt(self) -> None:
        """
        Export selected nodes as TXT.
        """
        self._export("txt")

    def export_as_csv(self) -> None:
        """
        Export selected nodes as CSV.
        """
        self._export("csv")

    def export_as_pdf(self) -> None:
        """
        Export selected nodes as PDF.
        """
        self._export("pdf")

    def get_selected_nodes(self) -> List[str]:
        """
        Get the names of checked nodes in the tree view, including the root node.

        Returns:
            List[str]: The list of selected node names.
        """
        logging.debug("Starting to gather selected nodes.")
        selected_nodes = []

        def get_children(item: QStandardItem) -> List[QStandardItem]:
            """Get all children of an item"""
            return [item.child(row) for row in range(item.rowCount())]

        def process_node(item: QStandardItem) -> None:
            """Process a single node"""
            if not item:
                return
            if item.checkState() == Qt.CheckState.Checked and item.data(
                Qt.ItemDataRole.UserRole
            ):
                selected_nodes.append(item.data(Qt.ItemDataRole.UserRole))

        def process_tree() -> None:
            queue = []
            root = self.tree_model.invisibleRootItem()

            # Process root level
            root_children = get_children(root)
            for child in root_children:
                process_node(child)
                queue.append(child)

            # Process remaining items
            while queue:
                item = queue.pop(0)
                if not item.hasChildren():
                    continue

                # First pass: process all children immediately
                children = get_children(item)
                for child in children:
                    process_node(child)

                # Second pass: queue children for their own traversal
                queue.extend(children)

        process_tree()

        # Remove duplicates while preserving order
        unique_nodes = list(dict.fromkeys(selected_nodes))
        logging.debug(f"Found checked nodes: {unique_nodes}")
        return unique_nodes

    def load_last_modified_node(self) -> None:
        """
        Load the last modified node and display it in the UI.
        """
        try:
            last_modified_node = self.node_service.get_last_modified_node()
            if last_modified_node:
                self.ui.name_input.setText(last_modified_node["name"])
                self.node_controller.load_node_data()
            else:
                logging.info("No nodes available to load.")
        except Exception as e:
            self.handle_error(f"Error loading last modified node: {e}")

    def open_connection_settings(self):
        dialog = ConnectionSettingsDialog(self.config, self.app_instance)
        dialog.exec()

    #############################################
    # 3. Cleanup and Error Handling
    #############################################

    def cleanup(self) -> None:
        """
        Clean up resources.
        """
        # Cancel and wait for any running workers
        for worker in [
            self.node_controller.current_load_worker,
            self.node_controller.current_save_worker,
            self.tree_controller.current_relationship_worker,
            self.search_controller.current_search_worker,
            self.node_controller.current_delete_worker,
        ]:
            if worker is not None:
                worker.cancel()
                worker.wait()
        self.model.close()

    def handle_error(self, error_message: str) -> None:
        """
        Handle any errors.

        Args:
            error_message (str): The error message to display.
        """
        logging.error(error_message)
        QMessageBox.critical(self.ui, "Error", error_message)
