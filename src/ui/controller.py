import json
import logging
from typing import Optional, Dict, Any, List, Tuple

from PyQt6.QtCore import QObject, QStringListModel, Qt, pyqtSlot, QTimer
from PyQt6.QtGui import QStandardItemModel, QStandardItem
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QCompleter,
    QMessageBox,
    QTableWidgetItem,
)

from core.neo4jworkers import SuggestionWorker
from models.property_model import PropertyItem
from models.worker_model import WorkerOperation
from services.autocompletion_service import AutoCompletionService
from services.image_service import ImageService
from services.node_operation_service import NodeOperationsService
from services.property_service import PropertyService
from services.relationship_tree_service import RelationshipTreeService
from services.worker_manager_service import WorkerManagerService
from ui.dialogs import SuggestionDialog, ConnectionSettingsDialog
from utils.error_handler import ErrorHandler
from utils.exporters import Exporter
from utils.parsers import parse_comma_separated


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
        self.exporter = Exporter(self.ui, self.config)
        self.ui.controller = self
        self.error_handler = ErrorHandler(ui_feedback_handler=self._show_error_dialog)

        # Initialize services
        self.property_service = PropertyService(self.config)
        self.image_service = ImageService()
        self.worker_manager = WorkerManagerService(self.error_handler)
        self.auto_completion_service = AutoCompletionService(
            self.model,
            self.config,
            self.worker_manager,
            self.error_handler.handle_error,
        )
        self.node_operations = NodeOperationsService(
            self.model,
            self.config,
            self.worker_manager,
            self.property_service,
            self.error_handler,
        )

        # Initialize tree model and service
        self.tree_model = QStandardItemModel()
        self.relationship_tree_service = RelationshipTreeService(
            self.tree_model, self.NODE_RELATIONSHIPS_HEADER
        )

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
        # Initialize node name completion
        self.auto_completion_service.initialize_node_completer(self.ui.name_input)

        # Connect completer activation signal
        self.ui.name_input.completer().activated.connect(self.on_completer_activated)

    def on_completer_activated(self, text: str) -> None:
        """
        Handle completer selection.

        Args:
            text: The selected text from the completer
        """
        if text:
            self.ui.name_input.setText(text)
            self.load_node_data()

    def _add_target_completer_to_row(self, row: int) -> None:
        """
        Add target completer to the target input field in the relationship table.

        Args:
            row: The row number where the completer will be added
        """
        self.auto_completion_service.add_target_completer_to_row(
            self.ui.relationships_table, row
        )

    def _initialize_target_completer(self) -> None:
        """
        Initialize target auto-completion for relationship table.
        """
        self.target_name_model = QStringListModel()
        self.target_completer = QCompleter(self.target_name_model)
        self.target_completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.target_completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.target_completer.activated.connect(self.on_target_completer_activated)

    def _connect_signals(self) -> None:
        """
        Connect all UI signals to handlers.
        """
        # Main buttons
        self.ui.save_button.clicked.connect(self.save_node)
        self.ui.delete_button.clicked.connect(self.delete_node)

        # Image handling
        self.ui.change_image_button.clicked.connect(self.change_image)
        self.ui.delete_image_button.clicked.connect(self.delete_image)

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

    def load_last_modified_node(self) -> None:
        """Load the last modified node."""
        self.node_operations.load_last_modified_node(self._handle_node_data)

    #############################################
    # 4. Auto-completion and Search
    #############################################

    def show_suggestions_modal(self) -> None:
        """
        Show the suggestions modal dialog.
        """
        node_data = self._collect_node_data()
        if not node_data:
            return

        # Show loading indicator
        self.ui.show_loading(True)

        worker = SuggestionWorker(self.model._uri, self.model._auth, node_data)

        # Connect the specific signal before creating operation
        worker.suggestions_ready.connect(self.handle_suggestions)

        operation = WorkerOperation(
            worker=worker,
            success_callback=None,
            error_callback=lambda msg: self.error_handler.handle_error(
                f"Error creating suggestion: {msg}"
            ),
            finished_callback=self._handle_suggestion_finished,
            operation_name="suggestions",
        )

        self.worker_manager.execute_worker("suggestions", operation)
        logging.debug("SuggestionWorker started successfully.")

    def _handle_suggestion_finished(self) -> None:
        """Handle suggestion worker completion."""
        self.ui.show_loading(False)
        logging.debug("Suggestion worker has finished and cleaned up.")

    def handle_suggestions(self, suggestions: Dict[str, Any]) -> None:
        """
        Handle the suggestions received from the SuggestionWorker.

        Args:
            suggestions (dict): The suggestions dictionary containing tags, properties, and relationships.
        """
        logging.debug(f"handle_suggestions called with suggestions: {suggestions}")
        # Hide loading indicator
        self.ui.show_loading(False)
        logging.debug("Loading indicator hidden.")

        if not suggestions or all(not suggestions[key] for key in suggestions):
            logging.debug("No suggestions found.")
            QMessageBox.information(
                self.ui, "No Suggestions", "No suggestions were found for this node."
            )
            return

        dialog = SuggestionDialog(suggestions, self.ui)
        if dialog.exec():
            selected = dialog.selected_suggestions
            logging.debug(f"User selected suggestions: {selected}")

            # Update tags
            existing_tags = parse_comma_separated(self.ui.tags_input.text())
            new_tags = list(set(existing_tags + selected["tags"]))
            self.ui.tags_input.setText(", ".join(new_tags))
            logging.debug(f"Updated tags: {new_tags}")

            # Update properties
            for key, value in selected["properties"].items():
                self.add_or_update_property(key, value)
                logging.debug(f"Updated property - Key: {key}, Value: {value}")

            # Update relationships
            for rel in selected["relationships"]:
                rel_type, target, direction, props = rel
                self.ui.add_relationship_row(
                    rel_type, target, direction, json.dumps(props)
                )
                logging.debug(
                    f"Added relationship - Type: {rel_type}, Target: {target}, Direction: {direction}, Properties: {props}"
                )

            QMessageBox.information(
                self.ui,
                "Suggestions Applied",
                "Selected suggestions have been applied to the node.",
            )
        else:
            logging.debug("Suggestion dialog was canceled by the user.")

    def add_or_update_property(self, key: str, value: Any) -> None:
        """
        Add or update a property in the properties table.

        Args:
            key (str): The property key.
            value (Any): The property value.
        """
        found = False
        for row in range(self.ui.properties_table.rowCount()):
            item_key = self.ui.properties_table.item(row, 0)
            if item_key and item_key.text() == key:
                self.ui.properties_table.item(row, 1).setText(str(value))
                found = True
                break
        if not found:
            row = self.ui.properties_table.rowCount()
            self.ui.properties_table.insertRow(row)
            self.ui.properties_table.setItem(row, 0, QTableWidgetItem(key))
            self.ui.properties_table.setItem(row, 1, QTableWidgetItem(str(value)))
            delete_button = self.ui.create_delete_button(self.ui.properties_table, row)
            self.ui.properties_table.setCellWidget(row, 2, delete_button)

    def on_completer_activated(self, text: str) -> None:
        """
        Handle completer selection.

        Args:
            text (str): The selected text from the completer.
        """
        if text:
            self.ui.name_input.setText(text)
            self.load_node_data()

    #############################################
    # 5. Data Collection and Validation
    #############################################

    #############################################
    # 6. Event Handlers
    #############################################

    @pyqtSlot(list)
    def _handle_node_data(self, data: List[Any]) -> None:
        """Handle node data fetched by the worker."""
        logging.debug(f"Handling node data: {data}")
        if not data:
            return

        try:
            record = data[0]
            self._populate_node_fields(record)
            self.original_node_data = self.node_operations.collect_node_data(
                name=self.ui.name_input.text().strip(),
                description=self.ui.description_input.toHtml().strip(),
                tags=self.ui.tags_input.text(),
                labels=self.ui.labels_input.text(),
                properties=self._collect_table_properties(),
                relationships=self._collect_table_relationships(),
                image_path=self.current_image_path,
            )
            self.ui.save_button.setStyleSheet("background-color: #d3d3d3;")

        except Exception as e:
            self.error_handler.handle_error(f"Error populating node fields: {str(e)}")

    def is_node_changed(self) -> bool:
        """Check if the node data has changed."""
        current_data = self.node_operations.collect_node_data(
            name=self.ui.name_input.text().strip(),
            description=self.ui.description_input.toHtml().strip(),
            tags=self.ui.tags_input.text(),
            labels=self.ui.labels_input.text(),
            properties=self._collect_table_properties(),
            relationships=self._collect_table_relationships(),
            image_path=self.current_image_path,
        )
        return current_data != self.original_node_data

    def update_unsaved_changes_indicator(self) -> None:
        """Update the unsaved changes indicator."""
        if self.is_node_changed():
            self.ui.save_button.setStyleSheet("background-color: #83A00E;")
        else:
            self.ui.save_button.setStyleSheet("background-color: #d3d3d3;")

    def _handle_delete_success(self, _: Any) -> None:
        """
        Handle successful node deletion.

        Args:
            _: The result of the delete operation.
        """
        QMessageBox.information(self.ui, "Success", "Node deleted successfully")
        self._load_default_state()

    def _update_save_progress(self, current: int, total: int) -> None:
        """
        Update progress during save operation.

        Args:
            current (int): The current progress value.
            total (int): The total progress value.
        """
        # Could be connected to a progress bar in the UI
        logging.info(f"Save progress: {current}/{total}")

    @pyqtSlot(object)
    def _populate_node_fields(self, record: Any) -> None:
        """
        Populate UI fields with node data.

        Args:
            record: The record containing node data.
        """

        try:
            # Extract data from the record
            node = record["n"]
            labels = record["labels"]
            relationships = record["relationships"]
            properties = record["all_props"]

            # Ensure node properties are accessed correctly
            node_properties = dict(node)
            node_name = node_properties.get("name", "")
            node_description = node_properties.get("description", "")
            node_tags = node_properties.get("tags", [])

            # Update UI elements in the main thread
            self.ui.name_input.setText(node_name)
            self.ui.description_input.setHtml(node_description)
            self.ui.labels_input.setText(", ".join(labels))
            self.ui.tags_input.setText(", ".join(node_tags))

            # Update properties table
            self.ui.properties_table.setRowCount(0)
            for key, value in properties.items():

                if key.startswith("_"):
                    continue

                if key not in self.config.RESERVED_PROPERTY_KEYS:

                    row = self.ui.properties_table.rowCount()
                    self.ui.properties_table.insertRow(row)
                    self.ui.properties_table.setItem(row, 0, QTableWidgetItem(key))
                    self.ui.properties_table.setItem(
                        row, 1, QTableWidgetItem(str(value))
                    )
                    delete_button = self.ui.create_delete_button(
                        self.ui.properties_table, row
                    )
                    self.ui.properties_table.setCellWidget(row, 2, delete_button)

            # Update relationships table
            self.ui.relationships_table.setRowCount(0)
            for rel in relationships:
                rel_type = rel.get("type", "")
                target = rel.get("end", "")
                direction = rel.get("dir", ">")
                props = json.dumps(rel.get("props", {}))

                self.ui.add_relationship_row(rel_type, target, direction, props)

            # Update image if available
            image_path = node_properties.get("imagepath")

            if image_path:
                self.image_service.set_current_image(image_path)
                self.current_image_path = image_path  # Keep controller in sync
                self.ui.set_image(image_path)
            else:
                self.image_service.set_current_image(None)
                self.current_image_path = None
                self.ui.set_image(None)

        except Exception as e:

            self.error_handler.handle_error(f"Error populating node fields: {str(e)}")

    def process_relationship_records(
        self, records: List[Any]
    ) -> Tuple[Dict[Tuple[str, str, str], List[Tuple[str, List[str]]]], int]:
        """
        Process relationship records and build parent-child map.

        Args:
            records (List[Any]): The list of relationship records.

        Returns:
            dict: A dictionary mapping parent names to their child nodes with relationship details.
        """
        parent_child_map = {}
        skipped_records = 0

        for record in records:
            node_name = record.get("node_name")
            labels = record.get("labels", [])
            parent_name = record.get("parent_name")
            rel_type = record.get("rel_type")
            direction = record.get("direction")

            if not node_name or not parent_name or not rel_type or not direction:
                logging.warning(f"Incomplete record encountered and skipped: {record}")
                skipped_records += 1
                continue

            key = (parent_name, rel_type, direction)
            if key not in parent_child_map:
                parent_child_map[key] = []
            parent_child_map[key].append((node_name, labels))

        return parent_child_map, skipped_records

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
        self.worker_manager.cancel_all_workers()
        self.model.close()

    def _show_error_dialog(self, title: str, message: str) -> None:
        """Show error dialog to user."""
        QMessageBox.critical(self.ui, title, message)

    #############################################
    # 8. Utility Methods
    #############################################

    def change_image(self) -> None:
        """Handle image change request from UI."""
        result = self.image_service.change_image(self.ui)
        if result.success:
            self.ui.set_image(result.path)
            self.current_image_path = result.path
            self.update_unsaved_changes_indicator()  # If you need to track changes
        else:
            self.error_handler.handle_error(
                f"Error changing image - {result.error_message}"
            )

    def delete_image(self) -> None:
        """Handle image deletion request from UI."""
        self.image_service.delete_image()
        self.current_image_path = None
        self.ui.set_image(None)
        self.update_unsaved_changes_indicator()  # If you need to track changes

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
        try:

            node_data = {
                "name": node_name,
                "description": self.ui.description_input.toPlainText().strip(),
                "tags": parse_comma_separated(self.ui.tags_input.text()),
                "labels": [
                    label.strip().upper().replace(" ", "_")
                    for label in parse_comma_separated(self.ui.labels_input.text())
                ],
                "relationships": self._collect_relationships(),
                "additional_properties": self._collect_properties(),
            }

            current_image = self.image_service.get_current_image()
            node_data["imagepath"] = current_image

            return node_data
        except ValueError as e:
            self.error_handler.handle_error(str(e))
            return None

    def load_last_modified_node(self) -> None:
        """
        Load the last modified node and display it in the UI.
        """
        try:
            last_modified_node = self.model.get_last_modified_node()
            if last_modified_node:
                self.ui.name_input.setText(last_modified_node["name"])
                self.load_node_data()
            else:
                logging.info("No nodes available to load.")
        except Exception as e:

            self.error_handler.handle_error(f"Error loading last modified node: {e}")

    def open_connection_settings(self) -> None:
        dialog = ConnectionSettingsDialog(self.config, self.app_instance)
        dialog.exec()

    def save_node(self) -> None:
        """Handle node save request."""
        name = self.ui.name_input.text().strip()
        if not self.node_operations.validate_node_name(name).is_valid:
            return

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
            image_path=self.current_image_path,
        )

        if node_data:
            self.node_operations.save_node(node_data, self._handle_save_success)

    def _handle_save_success(self, _: Any) -> None:
        """Handle successful node save with proper UI updates."""
        # Show success message
        msg_box = QMessageBox(self.ui)
        msg_box.setIcon(QMessageBox.Icon.Information)
        msg_box.setWindowTitle("Success")
        msg_box.setText("Node saved successfully")
        msg_box.setStandardButtons(QMessageBox.StandardButton.NoButton)
        msg_box.show()

        # Auto-close message after 1 second
        QTimer.singleShot(1000, msg_box.accept)

        # Update UI state
        self.refresh_tree_view()
        self.load_node_data()
