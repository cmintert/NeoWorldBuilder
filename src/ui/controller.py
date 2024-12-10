import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple

from PyQt6.QtCore import QObject, Qt, pyqtSlot, QTimer
from PyQt6.QtGui import QStandardItemModel, QStandardItem
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QCompleter,
    QMessageBox,
    QTableWidgetItem,
    QTableWidget,
    QLineEdit,
    QApplication,
    QFileDialog,
)
from structlog import get_logger

from models.completer_model import AutoCompletionUIHandler, CompleterInput
from models.property_model import PropertyItem
from models.suggestion_model import SuggestionUIHandler, SuggestionResult
from models.worker_model import WorkerOperation
from services.autocompletion_service import AutoCompletionService
from services.fast_inject_service import FastInjectService
from services.image_service import ImageService
from services.map_service import MapService
from services.node_operation_service import NodeOperationsService
from services.property_service import PropertyService
from services.relationship_tree_service import RelationshipTreeService
from services.save_service import SaveService
from services.suggestion_service import SuggestionService
from services.worker_manager_service import WorkerManagerService
from ui.dialogs import (
    StyleSettingsDialog,
    ConnectionSettingsDialog,
    SuggestionDialog,
    FastInjectDialog,
)
from ui.styles import StyleManager
from utils.error_handler import ErrorHandler
from utils.exporters import Exporter

logger = get_logger(__name__)


class WorldBuildingController(QObject):
    """
    Controller class managing interaction between UI and Neo4j model using QThread workers.

    Args:
        ui (WorldBuildingUI): The UI instance.
        model (Neo4jModel): The Neo4j model instance.
        config (Config): The configuration instance.
    """

    NODE_RELATIONSHIPS_HEADER = "Node Relationships"

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

        # Initialize style management
        self.style_manager = StyleManager("src/config/styles")
        self.style_manager.registry.error_occurred.connect(self._show_error_dialog)

        self.exporter = Exporter(ui, self.config)
        self.ui.controller = self
        self.error_handler = ErrorHandler(ui_feedback_handler=self._show_error_dialog)

        # Initialize services
        self.property_service = PropertyService(self.config)
        self.image_service = ImageService()
        self.worker_manager = WorkerManagerService(self.error_handler)
        self.fast_inject_service = FastInjectService()
        self.map_service = MapService(self.ui)

        # Initialize the ui
        self.ui = ui
        self.ui.controller = self

        # Initialize services that require the ui
        self.auto_completion_service = AutoCompletionService(
            self.model,
            self.config,
            self.worker_manager,
            self._create_autocompletion_ui_handler(),
            self.error_handler.handle_error,
        )
        self.node_operations = NodeOperationsService(
            self.model,
            self.config,
            self.worker_manager,
            self.property_service,
            self.error_handler,
        )
        self.suggestion_service = SuggestionService(
            self.model,
            self.config,
            self.worker_manager,
            self.error_handler,
            self._create_suggestion_ui_handler(),
        )

        self.save_service = SaveService(self.node_operations, self.error_handler)
        self.save_service.start_periodic_check(
            get_current_data=self._get_current_node_data,
            on_state_changed=self._handle_save_state_changed,
        )

        # Initialize tree model and service
        self.tree_model = QStandardItemModel()
        self.relationship_tree_service = RelationshipTreeService(
            self.tree_model, self.NODE_RELATIONSHIPS_HEADER
        )

        # Apply default application style
        self.style_manager.apply_style(app_instance, "default")

        # Apply specific styles to UI components
        self.style_manager.apply_style(self.ui.tree_view, "tree")
        self.style_manager.apply_style(self.ui.properties_table, "data-table")
        self.style_manager.apply_style(self.ui.relationships_table, "data-table")

        # Track UI state
        self.current_image_path: Optional[str] = None
        self.original_node_data: Optional[Dict[str, Any]] = None

        # Initialize UI state
        self._initialize_tree_view()
        self._initialize_completers()
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
        self.tree_model.setHorizontalHeaderLabels([self.NODE_RELATIONSHIPS_HEADER])
        self.ui.tree_view.setModel(self.tree_model)

        self.ui.tree_view.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection
        )
        self.ui.tree_view.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectItems
        )

        # connect selction signals
        self.ui.tree_view.selectionModel().selectionChanged.connect(
            self.on_tree_selection_changed
        )

        self.ui.tree_view.setUniformRowHeights(True)
        self.ui.tree_view.setItemsExpandable(True)
        self.ui.tree_view.setAllColumnsShowFocus(True)
        self.ui.tree_view.setHeaderHidden(False)

    def _initialize_completers(self) -> None:
        """Initialize auto-completion for node names and relationship targets."""
        self.auto_completion_service.initialize_node_completer(self.ui.name_input)

    def _add_target_completer_to_row(self, row: int) -> None:
        """
        Add target completer to the target input field in the relationship table.

        Args:
            row: The row number where the completer will be added
        """
        self.auto_completion_service.add_target_completer_to_row(
            self.ui.relationships_table, row
        )

    def _connect_signals(self) -> None:
        """
        Connect all UI signals to handlers.
        """
        # Main buttons
        self.ui.save_button.clicked.connect(self.save_node)
        self.ui.delete_button.clicked.connect(self.delete_node)

        # Name input and autocomplete

        self.ui.name_input.editingFinished.connect(self.load_node_data)

        # Table buttons
        self.ui.add_rel_button.clicked.connect(self.ui.add_relationship_row)

        # connect the suggest button
        self.ui.suggest_button.clicked.connect(self.show_suggestions_modal)

        # Check for unsaved changes
        self.ui.name_input.textChanged.connect(self.update_unsaved_changes_indicator)
        self.ui.description_input.textChanged.connect(
            self.update_unsaved_changes_indicator
        )
        self.ui.labels_input.textChanged.connect(self.update_unsaved_changes_indicator)
        self.ui.tags_input.textChanged.connect(self.update_unsaved_changes_indicator)
        self.ui.properties_table.itemChanged.connect(
            self.update_unsaved_changes_indicator
        )
        self.ui.relationships_table.itemChanged.connect(
            self.update_unsaved_changes_indicator
        )

        # Depth spinbox change
        self.ui.depth_spinbox.valueChanged.connect(self.on_depth_changed)

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
        self.refresh_tree_view()

    #############################################
    # 2. Node Operations
    #############################################

    def load_node_data(self) -> None:
        """Load node data."""
        name = self.ui.name_input.text().strip()
        if not name:
            return

        # Clear all fields to populate them again
        self.ui.clear_all_fields()

        self.node_operations.load_node(
            name, self._handle_node_data, lambda: self.update_relationship_tree(name)
        )

    def delete_node(self) -> None:
        """Handle node deletion request."""
        name = self.ui.name_input.text().strip()
        if not name:
            return

        reply = QMessageBox.question(
            self.ui,
            "Confirm Deletion",
            f'Are you sure you want to delete node "{name}"?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.node_operations.delete_node(name, self._handle_delete_success)

    #############################################
    # 3. Tree and Relationship Management
    #############################################

    def on_depth_changed(self, value: int) -> None:
        """
        Handle changes in relationship depth.

        Args:
            value (int): The new depth value.
        """
        if node_name := self.ui.name_input.text().strip():
            self.update_relationship_tree(node_name)

    def update_relationship_tree(self, node_name: str) -> None:
        """
        Update tree view with node relationships.

        Args:
            node_name (str): The name of the node.
        """
        if not node_name:
            self.tree_model.clear()
            self.tree_model.setHorizontalHeaderLabels([self.NODE_RELATIONSHIPS_HEADER])
            return

        depth = self.ui.depth_spinbox.value()

        worker = self.model.get_node_relationships(
            node_name, depth, self._populate_relationship_tree
        )

        operation = WorkerOperation(
            worker=worker,
            success_callback=self._populate_relationship_tree,
            error_callback=lambda msg: self.error_handler.handle_error(
                f"Error getting relationships: {msg}"
            ),
            operation_name="relationship_tree",
        )

        self.worker_manager.execute_worker("relationships", operation)

    def refresh_tree_view(self) -> None:
        """
        Refresh the entire tree view.
        """
        if name := self.ui.name_input.text().strip():
            self.update_relationship_tree(name)

    def on_tree_selection_changed(self, selected: Any, deselected: Any) -> None:
        """
        Handle tree view selection changes.

        Args:
            selected: The selected indexes.
            deselected: The deselected indexes.
        """
        if indexes := selected.indexes():
            if selected_item := self.tree_model.itemFromIndex(indexes[0]):
                node_name = selected_item.data(Qt.ItemDataRole.UserRole)
                if node_name and node_name != self.ui.name_input.text():
                    self.ui.name_input.setText(node_name)
                    self.load_node_data()

    def _collect_table_relationships(self) -> List[Tuple[str, str, str, str]]:
        """Get relationships from the relationships table.

        Returns:
            List[Tuple[str, str, str, str]]: List of relationship tuples (type, target, direction, props_json)
        """
        relationships = []
        for row in range(self.ui.relationships_table.rowCount()):
            rel_type = self.ui.relationships_table.item(row, 0)
            target = self.ui.relationships_table.cellWidget(row, 1)
            direction = self.ui.relationships_table.cellWidget(row, 2)
            props = self.ui.relationships_table.item(row, 3)

            if all([rel_type, target, direction]):
                relationships.append(
                    (
                        rel_type.text(),
                        target.text(),
                        direction.currentText(),
                        props.text() if props else "",
                    )
                )
        return relationships

    def _collect_table_properties(self) -> List[PropertyItem]:
        """Get properties from the properties table.

        Returns:
            List[PropertyItem]: The list of property items from the table
        """
        properties = []
        for row in range(self.ui.properties_table.rowCount()):
            key_item = self.ui.properties_table.item(row, 0)
            value_item = self.ui.properties_table.item(row, 1)

            if prop := PropertyItem.from_table_item(key_item, value_item):
                properties.append(prop)
        return properties

    #############################################
    # 4. Auto-completion and Search
    #############################################

    def show_suggestions_modal(self) -> None:
        """
        Show the suggestions modal dialog.
        """
        if node_data := self._get_current_node_data():
            self.suggestion_service.show_suggestions_modal(node_data)

    def on_completer_activated(self, text: str) -> None:
        """
        Handle completer selection.

        Args:
            text (str): The selected text from the completer.
        """
        if text:
            self.ui.name_input.setText(text)
            self.load_node_data()

    @pyqtSlot(list)
    def _handle_node_data(self, data: List[Any]) -> None:
        """Handle node data fetched by the worker."""
        logging.debug(f"Handling node data: {data}")
        if not data:
            return

        try:
            record = data[0]
            self._populate_node_fields(record)

            # First, update the original data
            self.original_node_data = self.node_operations.collect_node_data(
                name=self.ui.name_input.text().strip(),
                description=self.ui.description_input.toHtml().strip(),
                tags=self.ui.tags_input.text(),
                labels=self.ui.labels_input.text(),
                properties=self._collect_table_properties(),
                relationships=self._collect_table_relationships(),
                image_path=self.current_image_path,
            )

            # Update the save service's original data
            self.save_service.update_save_state(self.original_node_data)

            # Reset button to gray
            self.ui.save_button.setStyleSheet(self.config.colors.passiveSave)

        except Exception as e:
            self.error_handler.handle_error(f"Error populating node fields: {str(e)}")

    def update_unsaved_changes_indicator(self) -> None:
        """Update the unsaved changes indicator based on current state."""
        current_data = self.node_operations.collect_node_data(
            name=self.ui.name_input.text().strip(),
            description=self.ui.description_input.toHtml().strip(),
            tags=self.ui.tags_input.text(),
            labels=self.ui.labels_input.text(),
            properties=self._collect_table_properties(),
            relationships=self._collect_table_relationships(),
            image_path=self.current_image_path,
        )

        if current_data and self.save_service.check_for_changes(current_data):
            self.ui.save_button.setStyleSheet(self.config.colors.activeSave)
        else:
            self.ui.save_button.setStyleSheet(self.config.colors.passiveSave)

    def _handle_delete_success(self, _: Any) -> None:
        """
        Handle successful node deletion.

        Args:
            _: The result of the delete operation.
        """
        QMessageBox.information(self.ui, "Success", "Node deleted successfully")
        self._load_default_state()

    @pyqtSlot(object)
    def _populate_node_fields(self, record: Any) -> None:
        """
        Populate UI fields with node data.

        Args:
            record: The record containing node data.
        """
        try:
            node_data = self._extract_node_data(record)
            self._populate_basic_info(node_data)
            self.map_service.populate_map_tab(node_data)
            self._populate_properties(node_data["properties"])
            self._populate_relationships(node_data["relationships"])
            self._populate_basic_info_image(node_data["node_properties"])
        except Exception as e:
            self.error_handler.handle_error(f"Error populating node fields: {str(e)}")

    def _extract_node_data(self, record: Any) -> Dict[str, Any]:
        """
        Extract and organize node data from the database record.

        Args:
            record: The raw database record.

        Returns:
            Dict containing organized node data.
        """
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

    def _populate_basic_info(self, node_data: Dict[str, Any]) -> None:
        """
        Populate basic node information fields.

        Args:
            node_data: Dictionary containing node information.
        """
        self.ui.name_input.setText(node_data["name"])
        self.ui.description_input.setHtml(node_data["description"])
        self.ui.labels_input.setText(", ".join(node_data["labels"]))
        self.ui.tags_input.setText(", ".join(node_data["tags"]))

    def _populate_properties(self, properties: Dict[str, Any]) -> None:
        """
        Populate properties table.

        Args:
            properties: Dictionary of node properties.
        """
        self.ui.properties_table.setRowCount(0)
        for key, value in properties.items():
            if self._should_display_property(key):
                self._add_property_row(key, value)

    def _should_display_property(self, key: str) -> bool:
        """
        Check if a property should be displayed in the properties table.

        Args:
            key: Property key to check.

        Returns:
            bool: True if property should be displayed.
        """
        return not key.startswith("_") and key not in self.config.RESERVED_PROPERTY_KEYS

    def _add_property_row(self, key: str, value: Any) -> None:
        """
        Add a row to the properties table.

        Args:
            key: Property key.
            value: Property value.
        """
        row = self.ui.properties_table.rowCount()
        self.ui.properties_table.insertRow(row)
        self.ui.properties_table.setItem(row, 0, QTableWidgetItem(key))
        self.ui.properties_table.setItem(row, 1, QTableWidgetItem(str(value)))
        delete_button = self.ui.create_delete_button(self.ui.properties_table, row)
        self.ui.properties_table.setCellWidget(row, 2, delete_button)

    def _populate_relationships(self, relationships: List[Dict[str, Any]]) -> None:
        """
        Populate relationships table.

        Args:
            relationships: List of relationship dictionaries.
        """
        self.ui.relationships_table.setRowCount(0)
        for rel in relationships:
            self.ui.add_relationship_row(
                rel.get("type", ""),
                rel.get("end", ""),
                rel.get("dir", ">"),
                json.dumps(rel.get("props", {})),
            )

    def _populate_basic_info_image(self, node_properties: Dict[str, Any]) -> None:
        """
        Set the node's image if available.

        Args:
            node_properties: Dictionary of node properties.
        """
        image_path = node_properties.get("imagepath")
        self.ui.image_group.set_basic_image(image_path)

    @pyqtSlot(list)
    def _populate_relationship_tree(self, records: List[Any]) -> None:
        """
        Populate the relationship tree in the UI.

        Args:
            records (List[Any]): The relationship data.
        """
        try:
            self.tree_model.clear()
            self.tree_model.setHorizontalHeaderLabels([self.NODE_RELATIONSHIPS_HEADER])
            root_node_name = self.ui.name_input.text().strip()
            root_item = QStandardItem(f"🔵 {root_node_name}")
            root_item.setData(root_node_name, Qt.ItemDataRole.UserRole)
            root_item.setFlags(
                Qt.ItemFlag.ItemIsEnabled
                | Qt.ItemFlag.ItemIsSelectable
                | Qt.ItemFlag.ItemIsUserCheckable
            )
            root_item.setCheckState(Qt.CheckState.Checked)
            self.tree_model.appendRow(root_item)

            parent_child_map, _ = (
                self.relationship_tree_service.process_relationship_records(records)
            )
            self.relationship_tree_service.add_children(
                root_node_name, root_item, [root_node_name], parent_child_map
            )
            self.ui.tree_view.expandAll()
        except Exception as e:
            self.error_handler.handle_error(f"Tree population failed: {e}")

    #############################################
    # 7. Cleanup and Error Handling
    #############################################

    def cleanup(self) -> None:
        """
        Clean up resources.
        """
        self.save_service.stop_periodic_check()
        self.worker_manager.cancel_all_workers()
        self.model.close()

    def _show_error_dialog(self, title: str, message: str) -> None:
        """Show error dialog to user."""
        QMessageBox.critical(self.ui, title, message)

    #############################################
    # 8. Utility Methods
    #############################################

    def change_basic_image(self) -> None:
        """Handle image change request from UI."""
        result = self.image_service.change_image(self.ui)
        if result.success:
            self.current_image_path = result.path
            self.image_service.set_current_image(result.path)
            self.ui.image_group.set_basic_image(result.path)
            self.update_unsaved_changes_indicator()
        else:
            self.error_handler.handle_error(
                f"Error changing image - {result.error_message}"
            )

    def delete_basic_image(self) -> None:
        """Handle image deletion request from UI."""
        self.image_service.delete_image()
        self.ui.image_group.set_basic_image(None)
        self.update_unsaved_changes_indicator()

    def export_to_filetype(self, format_type: str) -> None:
        """
        Generic export method that handles all export formats.

        Args:
            format_type (str): The type of export format ('json', 'txt', 'csv', 'pdf')
        """
        selected_nodes = self.get_selected_nodes()
        if not selected_nodes:
            QMessageBox.warning(self.ui, "Warning", "No nodes selected for export.")
            return

        try:
            self.exporter.export(
                format_type, selected_nodes, self._collect_node_data_for_export
            )
        except ValueError as e:

            self.error_handler.handle_error(f"Export error: {str(e)}")

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

    def _collect_node_data_for_export(self, node_name: str) -> Optional[Dict[str, Any]]:
        """
        Collect node data for export.

        Args:
            node_name (str): The name of the node to collect data for.

        Returns:
            Optional[Dict[str, Any]]: The collected node data.
        """
        image_path = self.image_service.get_current_image()
        return self.node_operations.collect_node_data(
            name=node_name,
            description=self.ui.description_input.toPlainText().strip(),
            tags=self.ui.tags_input.text(),
            labels=self.ui.labels_input.text(),
            properties=self._collect_table_properties(),
            relationships=self._collect_table_relationships(),
            image_path=image_path,
        )

    def load_last_modified_node(self) -> None:
        """Load the last modified node and display it in the UI."""

        def on_load(data: List[Any]) -> None:
            self._handle_node_data(data)
            self.update_relationship_tree(self.ui.name_input.text().strip())

        self.node_operations.load_last_modified_node(on_load)

    def open_connection_settings(self) -> None:
        dialog = ConnectionSettingsDialog(self.config, self.app_instance)
        dialog.exec()

    def open_style_settings(self) -> None:
        dialog = StyleSettingsDialog(self.config, self.app_instance)
        dialog.exec()

    def save_node(self) -> None:
        """Handle node save request."""
        name = self.ui.name_input.text().strip()
        if not self.node_operations.validate_node_name(name).is_valid:
            return

        # Debug logging
        print(f"Current image path before save: {self.current_image_path}")
        print(
            f"Image group path before save: {self.ui.image_group.get_basic_image_path()}"
        )

        # Collect properties from UI
        properties = self._collect_table_properties()
        relationships = self._collect_table_relationships()

        node_data = self.node_operations.collect_node_data(
            name=name,
            description=self.ui.description_input.toHtml().strip(),
            tags=self.ui.tags_input.text(),
            labels=self.ui.labels_input.text(),
            properties=properties,
            relationships=relationships,
            image_path=self.current_image_path,  # Use the controller's tracked path
        )

        if node_data:
            print(f"Node data being saved: {node_data}")
            self.node_operations.save_node(node_data, self._handle_save_success)

    def _handle_save_success(self, _: Any) -> None:
        """Handle successful node save with proper UI updates."""
        msg_box = QMessageBox(self.ui)
        msg_box.setIcon(QMessageBox.Icon.Information)
        msg_box.setWindowTitle("Success")
        msg_box.setText("Node saved successfully")
        msg_box.setStandardButtons(QMessageBox.StandardButton.NoButton)
        msg_box.show()

        # Auto-close message after 1 second
        QTimer.singleShot(1000, msg_box.accept)

        # Refresh UI state
        self.refresh_tree_view()
        self.load_node_data()
        self.update_unsaved_changes_indicator()

        # Activate the basic info tab
        self.ui.tabs.setCurrentIndex(0)

    def _get_current_node_data(self) -> Dict[str, Any]:
        """Get current node data from UI."""
        return self.node_operations.collect_node_data(
            name=self.ui.name_input.text().strip(),
            description=self.ui.description_input.toHtml().strip(),
            tags=self.ui.tags_input.text(),
            labels=self.ui.labels_input.text(),
            properties=self._collect_table_properties(),
            relationships=self._collect_table_relationships(),
            image_path=self.ui.image_group.get_basic_image_path(),
        )

    def change_application_style(self, style_name: str) -> None:
        """Change the application-wide style.

        Args:
            style_name: Name of the style to apply
        """

        app = QApplication.instance()
        if app:
            self.style_manager.apply_style(app, style_name)

    def refresh_styles(self) -> None:
        """Reload all styles from disk and reapply current style."""

        self.style_manager.reload_styles()

    def _create_suggestion_ui_handler(self) -> SuggestionUIHandler:
        class UIHandler:
            def __init__(self, controller: "WorldBuildingController"):
                self.controller = controller

            def show_loading(self, is_loading: bool) -> None:
                self.controller.ui.show_loading(is_loading)

            def show_message(self, title: str, message: str) -> None:
                QMessageBox.information(self.controller.ui, title, message)

            def show_suggestion_dialog(
                self, suggestions: Dict[str, Any]
            ) -> SuggestionResult:
                dialog = SuggestionDialog(suggestions, self.controller.ui)
                if dialog.exec():
                    return SuggestionResult(
                        success=True, selected_suggestions=dialog.selected_suggestions
                    )
                return SuggestionResult(success=False)

            def update_tags(self, tags: List[str]) -> None:
                current_tags = self.controller.ui.tags_input.text().split(",")
                all_tags = list(set(current_tags + tags))
                self.controller.ui.tags_input.setText(", ".join(all_tags))

            def add_property(self, key: str, value: Any) -> None:
                row = self.controller.ui.properties_table.rowCount()
                self.controller.ui.properties_table.insertRow(row)
                self.controller.ui.properties_table.setItem(
                    row, 0, QTableWidgetItem(key)
                )
                self.controller.ui.properties_table.setItem(
                    row, 1, QTableWidgetItem(str(value))
                )
                delete_button = self.controller.ui.create_delete_button(
                    self.controller.ui.properties_table, row
                )
                self.controller.ui.properties_table.setCellWidget(row, 2, delete_button)

            def add_relationship(
                self, rel_type: str, target: str, direction: str, props: Dict[str, Any]
            ) -> None:
                self.controller.ui.add_relationship_row(
                    rel_type, target, direction, json.dumps(props)
                )

        return UIHandler(self)

    def _create_autocompletion_ui_handler(self) -> AutoCompletionUIHandler:
        """Create the UI handler for auto-completion operations."""

        class UIHandler:
            def __init__(self, controller: "WorldBuildingController"):
                self.controller = controller

            def create_completer(self, input: CompleterInput) -> QCompleter:
                """Create a configured completer for the input widget."""
                completer = QCompleter(input.model)
                completer.setCaseSensitivity(input.case_sensitivity)
                completer.setFilterMode(input.filter_mode)

                # Connect completer activation signal to node data loading
                if input.widget == self.controller.ui.name_input:
                    completer.activated.connect(self.controller.on_completer_activated)

                return completer

            def setup_target_cell_widget(
                self,
                table: QTableWidget,
                row: int,
                column: int,
                text: str,
            ) -> QLineEdit:
                """Create and setup a line edit widget for table cell."""
                line_edit = QLineEdit(text)
                table.setCellWidget(row, column, line_edit)
                return line_edit

        return UIHandler(self)

    def handle_fast_inject(self) -> None:
        """Handle the Fast Inject button click."""
        file_path = QFileDialog.getOpenFileName(
            self.ui, "Select Fast Inject Template", "", "Fast Inject Files (*.fi)"
        )[0]

        if not file_path:
            return

        try:
            template = self.fast_inject_service.load_template(Path(file_path))
            if template:
                dialog = FastInjectDialog(template, self.ui)
                if dialog.exec():
                    selected_properties = dialog.get_selected_properties_with_values()

                    self.fast_inject_service.apply_template(
                        self.ui,
                        template,
                        dialog.selected_labels,
                        dialog.selected_tags,
                        selected_properties,
                    )
                    self.update_unsaved_changes_indicator()
        except Exception as e:
            self.error_handler.handle_error(f"Fast Inject Error: {str(e)}")

    def _handle_save_state_changed(self, has_changes: bool) -> None:
        """Handle changes in save state."""
        if has_changes:
            self.ui.save_button.setStyleSheet("background-color: #83A00E;")
        else:
            self.ui.save_button.setStyleSheet("background-color: #d3d3d3;")
