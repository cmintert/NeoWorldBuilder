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
)

from core.neo4jworkers import SuggestionWorker
from models.property_model import PropertyItem
from models.worker_model import WorkerOperation
from services.image_service import ImageService
from services.property_service import PropertyService
from services.relationship_tree_service import RelationshipTreeService
from services.worker_manager_service import WorkerManagerService
from ui.dialogs import SuggestionDialog, ConnectionSettingsDialog
from utils.error_handler import ErrorHandler
from utils.exporters import Exporter
from utils.parsers import parse_comma_separated
from utils.validation import validate_node_name as validate_node_name_logic


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
        self.current_image_path: Optional[str] = None
        self.original_node_data: Optional[Dict[str, Any]] = None
        self.ui.controller = self
        self.error_handler = ErrorHandler(ui_feedback_handler=self._show_error_dialog)

        # Initialize services
        self.property_service = PropertyService(self.config)
        self.image_service = ImageService()
        self.worker_manager = WorkerManagerService(self.error_handler)

        # Initialize tree model and service
        self.tree_model = QStandardItemModel()
        self.tree_model.setHorizontalHeaderLabels([self.NODE_RELATIONSHIPS_HEADER])
        self.relationship_tree_service = RelationshipTreeService(
            self.tree_model, self.NODE_RELATIONSHIPS_HEADER
        )

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

    def _initialize_completer(self) -> None:
        """
        Initialize name auto-completion.
        """
        self.node_name_model = QStringListModel()
        self.completer = QCompleter(self.node_name_model)
        self.completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.ui.name_input.setCompleter(self.completer)
        self.completer.activated.connect(self.on_completer_activated)

    def _initialize_target_completer(self) -> None:
        """
        Initialize target auto-completion for relationship table.
        """
        self.target_name_model = QStringListModel()
        self.target_completer = QCompleter(self.target_name_model)
        self.target_completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.target_completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.target_completer.activated.connect(self.on_target_completer_activated)

    def _add_target_completer_to_row(self, row: int) -> None:
        """
        Add target completer to the target input field in the relationship table.

        Args:
            row (int): The row number where the completer will be added.
        """
        if target_item := self.ui.relationships_table.item(row, 1):
            target_text = target_item.text()
            line_edit = QLineEdit(target_text)
            line_edit.setCompleter(self.target_completer)
            line_edit.textChanged.connect(
                lambda text: self._fetch_matching_target_nodes(text)
            )
            self.ui.relationships_table.setCellWidget(row, 1, line_edit)

    def on_target_completer_activated(self, text: str) -> None:
        """
        Handle target completer selection.

        Args:
            text (str): The selected text from the completer.
        """
        current_row = self.ui.relationships_table.currentRow()
        if current_row >= 0:
            self.ui.relationships_table.item(current_row, 1).setText(text)

    def _fetch_matching_target_nodes(self, text: str) -> None:
        """
        Fetch matching target nodes for auto-completion.

        Args:
            text (str): The text to match against node names.
        """
        if not text:
            return

        worker = self.model.fetch_matching_node_names(
            text,
            self.config.MATCH_NODE_LIMIT,
            self._handle_target_autocomplete_results,
        )

        operation = WorkerOperation(
            worker=worker,
            success_callback=self._handle_target_autocomplete_results,
            error_callback=lambda msg: self.error_handler.handle_error(
                f"Error fetching target nodes: {msg}"
            ),
            operation_name="target_search",
        )

        self.worker_manager.execute_worker("target_search", operation)

    @pyqtSlot(list)
    def _handle_target_autocomplete_results(self, records: List[Any]) -> None:
        """
        Handle target autocomplete results.

        Args:
            records (List[Any]): The list of matching records.
        """
        try:
            names = [record["name"] for record in records]
            self.target_name_model.setStringList(names)
        except Exception as e:
            self.error_handler.handle_error(
                f"Error processing target autocomplete results: {str(e)}"
            )

    def _setup_debounce_timer(self) -> None:
        """
        Setup debounce timer for search.
        """
        self.name_input_timer = QTimer()
        self.name_input_timer.setSingleShot(True)
        self.name_input_timer.timeout.connect(self._fetch_matching_nodes)
        self.name_input_timer.setInterval(self.config.NAME_INPUT_DEBOUNCE_TIME_MS)

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
        self.ui.name_input.textChanged.connect(self.debounce_name_input)
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
        """
        Load node data using worker thread.
        """
        name = self.ui.name_input.text().strip()
        if not name:
            return

        # Clear all fields to populate them again
        self.ui.clear_all_fields()

        # Create load operation
        worker = self.model.load_node(name, self._handle_node_data)

        operation = WorkerOperation(
            worker=worker,
            success_callback=self._handle_node_data,
            error_callback=lambda msg: self.error_handler.handle_error(
                f"Error loading node: {msg}"
            ),
            finished_callback=lambda: self.update_relationship_tree(name),
            operation_name="load_node",
        )

        self.worker_manager.execute_worker("load", operation)

    def delete_node(self) -> None:
        """
        Delete node using worker thread.
        """
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
            worker = self.model.delete_node(name, self._handle_delete_success)

            operation = WorkerOperation(
                worker=worker,
                success_callback=self._handle_delete_success,
                error_callback=lambda msg: self.error_handler.handle_error(
                    f"Error deleting node: {msg}"
                ),
                operation_name="delete_node",
            )

            self.worker_manager.execute_worker("delete", operation)

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

    def debounce_name_input(self, text: str) -> None:
        """
        Debounce name input for search.

        Args:
            text (str): The input text.
        """
        self.name_input_timer.stop()
        if text.strip():
            self.name_input_timer.start()

    def _fetch_matching_nodes(self) -> None:
        """
        Fetch matching nodes for auto-completion.
        """
        text = self.ui.name_input.text().strip()
        if not text:
            return

        worker = self.model.fetch_matching_node_names(
            text, self.config.MATCH_NODE_LIMIT, self._handle_autocomplete_results
        )

        operation = WorkerOperation(
            worker=worker,
            success_callback=self._handle_autocomplete_results,
            error_callback=lambda msg: self.error_handler.handle_error(
                f"Error on autocompletion: {msg}"
            ),
            operation_name="search_nodes",
        )

        self.worker_manager.execute_worker("search", operation)

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

    def _collect_node_data(self) -> Optional[Dict[str, Any]]:
        """
        Collect all node data from UI with proper handling of additional properties.

        Returns:
            Optional[Dict[str, Any]]: The collected node data, or None if collection fails.
        """
        try:
            # Ensure properties are collected first and properly initialized
            additional_properties = self._collect_properties()
            if additional_properties is None:
                additional_properties = {}  # Ensure we always have a dict

            # Now build the complete node data structure
            node_data = {
                "name": self.ui.name_input.text().strip(),
                "description": self.ui.description_input.toHtml().strip(),
                "tags": parse_comma_separated(self.ui.tags_input.text()),
                "labels": [
                    label.strip().upper().replace(" ", "_")
                    for label in parse_comma_separated(self.ui.labels_input.text())
                ],
                "relationships": self._collect_relationships(),
                "additional_properties": additional_properties,  # Use our guaranteed dict
            }

            # Handle image path after ensuring additional_properties exists
            node_data["additional_properties"]["imagepath"] = (
                self.current_image_path if self.current_image_path else None
            )

            logging.debug(f"Collected Node Data: {node_data}")
            return node_data

        except Exception as e:
            logging.error(f"Error collecting node data: {str(e)}")
            self.error_handler.handle_error(str(e))
            return None

    def _collect_properties(self) -> Dict[str, Any]:
        """
        Collect properties from table with proper error handling and type safety.

        Returns:
            Dict[str, Any]: The collected properties, never returns None.
        """
        properties = []
        try:
            for row in range(self.ui.properties_table.rowCount()):
                key_item = self.ui.properties_table.item(row, 0)
                value_item = self.ui.properties_table.item(row, 1)

                prop = PropertyItem.from_table_item(key_item, value_item)
                if prop:
                    properties.append(prop)

            processed_properties = self.property_service.process_properties(properties)
            return processed_properties if processed_properties is not None else {}

        except ValueError as e:
            logging.error(f"Error collecting properties: {str(e)}")
            self.error_handler.handle_error(str(e))
            return {}  # Return empty dict instead of None on error
        except Exception as e:
            logging.error(f"Unexpected error collecting properties: {str(e)}")
            self.error_handler.handle_error(
                f"Unexpected error in property collection: {str(e)}"
            )
            return {}  # Return empty dict on any error

    def _collect_relationships(self) -> List[Tuple[str, str, str, Dict[str, Any]]]:
        """
        Collect relationships from table.

        Returns:
            List[Tuple[str, str, str, Dict[str, Any]]]: The collected relationships.
        """
        relationships = []
        for row in range(self.ui.relationships_table.rowCount()):
            rel_type = self.ui.relationships_table.item(row, 0)
            target = self.ui.relationships_table.cellWidget(row, 1)
            direction = self.ui.relationships_table.cellWidget(row, 2)
            props = self.ui.relationships_table.item(row, 3)

            if not all([rel_type, target, direction]):
                continue

            try:
                properties = (
                    json.loads(props.text()) if props and props.text().strip() else {}
                )

                # Enforce uppercase and replace spaces with underscores
                formatted_rel_type = rel_type.text().strip().upper().replace(" ", "_")

                relationships.append(
                    (
                        formatted_rel_type,
                        target.text().strip(),
                        direction.currentText(),
                        properties,
                    )
                )
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON in relationship properties: {e}") from e

        logging.debug(f"Collected the following Relationships: {relationships}")
        return relationships

    #############################################
    # 6. Event Handlers
    #############################################

    @pyqtSlot(list)
    def _handle_node_data(self, data: List[Any]) -> None:
        """
        Handle node data fetched by the worker.

        Args:
            data (List[Any]): The fetched node data.
        """
        logging.debug(f"Handling node data: {data}")
        if not data:
            return  # No need to notify the user

        try:
            record = data[0]  # Extract the first record
            self._populate_node_fields(record)
            self.original_node_data = self._collect_node_data()
            self.ui.save_button.setStyleSheet("background-color: #d3d3d3;")

        except Exception as e:
            self.error_handler.handle_error(f"Error populating node fields: {str(e)}")

    def is_node_changed(self) -> bool:
        """
        Check if the node data has changed.

        Returns:
            bool: Whether the node data has changed.
        """
        current_data = self._collect_node_data()
        return current_data != self.original_node_data

    def update_unsaved_changes_indicator(self) -> None:
        """
        Update the unsaved changes indicator.
        """
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

    @pyqtSlot(list)
    def _handle_autocomplete_results(self, records: List[Any]) -> None:
        """
        Handle autocomplete results.

        Args:
            records (List[Any]): The list of matching records.
        """
        try:
            names = [record["name"] for record in records]
            self.node_name_model.setStringList(names)
        except Exception as e:

            self.error_handler.handle_error(
                f"Error processing autocomplete results: {str(e)}"
            )

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

    def add_children(
        self,
        parent_name: str,
        parent_item: QStandardItem,
        path: List[str],
        parent_child_map: Dict[Tuple[str, str, str], List[Tuple[str, List[str]]]],
    ) -> None:
        """
        Add child nodes to the relationship tree with checkboxes.

        Args:
            parent_name (str): The name of the parent node.
            parent_item (QStandardItem): The parent item in the tree.
            path (List[str]): The path of node names to avoid cycles.
            parent_child_map (dict): The parent-child map of relationships.
        """
        for (p_name, rel_type, direction), children in parent_child_map.items():
            if p_name != parent_name:
                continue

            for child_name, child_labels in children:
                if child_name in path:
                    self.handle_cycles(parent_item, rel_type, direction, child_name)
                    continue

                arrow = "➡️" if direction == ">" else "⬅️"

                # Create relationship item (non-checkable separator)
                rel_item = QStandardItem(f"{arrow} [{rel_type}]")
                rel_item.setFlags(
                    Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
                )

                # Create node item (checkable)
                child_item = QStandardItem(
                    f"🔹 {child_name} [{', '.join(child_labels)}]"
                )
                child_item.setData(child_name, Qt.ItemDataRole.UserRole)
                child_item.setFlags(
                    Qt.ItemFlag.ItemIsEnabled
                    | Qt.ItemFlag.ItemIsSelectable
                    | Qt.ItemFlag.ItemIsUserCheckable
                )
                child_item.setCheckState(Qt.CheckState.Unchecked)

                rel_item.appendRow(child_item)
                parent_item.appendRow(rel_item)

                self.add_children(
                    child_name, child_item, path + [child_name], parent_child_map
                )

    def handle_cycles(
        self, parent_item: QStandardItem, rel_type: str, direction: str, child_name: str
    ) -> None:
        """
        Handle cycles in the relationship data to avoid infinite loops.

        Args:
            parent_item (QStandardItem): The parent item in the tree.
            rel_type (str): The type of the relationship.
            direction (str): The direction of the relationship.
            child_name (str): The name of the child node.
        """
        rel_item = QStandardItem(f"🔄 [{rel_type}] ({direction})")
        rel_item.setIcon(QIcon("path/to/relationship_icon.png"))

        cycle_item = QStandardItem(f"🔁 {child_name} (Cycle)")
        cycle_item.setData(child_name, Qt.ItemDataRole.UserRole)
        cycle_item.setIcon(QIcon("path/to/cycle_icon.png"))

        rel_item.appendRow(cycle_item)
        parent_item.appendRow(rel_item)

    @pyqtSlot(list)
    def _populate_relationship_tree(self, records: List[Any]) -> None:
        """
        Populate the tree view with relationships up to the specified depth.

        Args:
            records (List[Any]): The list of relationship records.
        """
        logging.debug(f"Populating relationship tree with records: {records}")
        try:
            self.tree_model.clear()
            self.tree_model.setHorizontalHeaderLabels([self.NODE_RELATIONSHIPS_HEADER])

            if not records:
                logging.info("No relationship records found.")
                return

            root_node_name = self.ui.name_input.text().strip()
            if not root_node_name:
                logging.warning("Root node name is empty.")
                return

            # Create root item with checkbox
            root_item = QStandardItem(f"🔵 {root_node_name}")
            root_item.setData(root_node_name, Qt.ItemDataRole.UserRole)
            root_item.setFlags(
                Qt.ItemFlag.ItemIsEnabled
                | Qt.ItemFlag.ItemIsSelectable
                | Qt.ItemFlag.ItemIsUserCheckable
            )
            root_item.setCheckState(Qt.CheckState.Unchecked)
            root_item.setIcon(QIcon("path/to/node_icon.png"))

            parent_child_map, skipped_records = self.process_relationship_records(
                records
            )

            self.add_children(
                root_node_name, root_item, [root_node_name], parent_child_map
            )

            self.tree_model.appendRow(root_item)
            self.ui.tree_view.expandAll()
            logging.info("Relationship tree populated successfully.")

            if skipped_records > 0:
                logging.warning(
                    f"Skipped {skipped_records} incomplete relationship records."
                )

        except Exception as e:
            self.handle_error(f"Error populating relationship tree: {str(e)}")

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
        """
        Save node data using worker thread.
        """
        name = self.ui.name_input.text().strip()
        if not self.validate_node_name(name):
            return

        node_data = self._collect_node_data()
        if not node_data:
            return

        worker = self.model.save_node(node_data, self._handle_save_success)

        operation = WorkerOperation(
            worker=worker,
            success_callback=self._handle_save_success,  # We'll create this new method
            error_callback=lambda msg: self.error_handler.handle_error(
                f"Error saving node: {msg}"
            ),
            operation_name="save_node",
        )

        self.worker_manager.execute_worker("save", operation)

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

    def validate_node_name(self, name: str) -> bool:
        """
        Validate node name and show appropriate UI feedback.

        Args:
            name (str): The node name to validate.

        Returns:
            bool: True if the node name is valid, False otherwise.
        """
        result = validate_node_name_logic(name, self.config.MAX_NODE_NAME_LENGTH)

        if not result.is_valid:
            QMessageBox.warning(self.ui, "Warning", result.error_message)

        return result.is_valid
