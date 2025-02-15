import json
import logging
import functools
import time
from abc import abstractmethod
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple, Callable

from PyQt6.QtCore import QObject, Qt, pyqtSlot, QTimer, QStringListModel
from PyQt6.QtGui import QStandardItem
from PyQt6.QtWidgets import (
    QCompleter,
    QMessageBox,
    QTableWidgetItem,
    QTableWidget,
    QLineEdit,
    QApplication,
    QFileDialog,
)
from structlog import get_logger

from date_parser_module.dateparser import ParsedDate, DatePrecision
from models.completer_model import AutoCompletionUIHandler, CompleterInput
from models.property_model import PropertyItem
from models.suggestion_model import SuggestionUIHandler, SuggestionResult
from models.worker_model import WorkerOperation
from services.initialisation_service import InitializationService
from services.search_analysis_service.search_analysis_service import SearchCriteria
from ui.components.dialogs import (
    StyleSettingsDialog,
    ConnectionSettingsDialog,
    SuggestionDialog,
    FastInjectDialog,
    ProjectSettingsDialog,
)
from ui.components.event_component.event_tab import EventTab
from ui.components.map_tab import MapTab
from utils.error_handler import ErrorHandler

from typing import Optional, Dict, Any, Callable
from PyQt6.QtCore import QObject
from PyQt6.QtWidgets import QMessageBox
from structlog import get_logger

logger = get_logger(__name__)


class ExportMixin:
    """Mixin providing export functionality for controllers."""

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
        logger.debug(f"Found checked nodes: {unique_nodes}")
        return unique_nodes

    @abstractmethod
    def _collect_node_data_for_export(self, node_name: str) -> Optional[Dict[str, Any]]:
        """
        Collect node data for export.
        Must be implemented by classes using this mixin.

        Args:
            node_name (str): The name of the node to collect data for.

        Returns:
            Optional[Dict[str, Any]]: The collected node data.
        """
        pass


class BaseController(QObject):
    """Base controller providing core infrastructure."""

    NODE_RELATIONSHIPS_HEADER = "Node Relationships"

    def __init__(
        self,
        ui: "WorldBuildingUI",
        model: "Neo4jModel",
        config: "Config",
        app_instance: "WorldBuildingApp",
        error_handler: "ErrorHandler",
        name_cache_service: "NameCacheService" = None,
    ) -> None:
        """Initialize base controller with core dependencies."""
        super().__init__()

        # Core dependencies
        self.ui = ui
        self.model = model
        self.config = config
        self.app_instance = app_instance
        self.error_handler = error_handler
        self.name_cache_service = name_cache_service

        # Essential state
        self.current_node_element_id: Optional[str] = None
        self.all_props: Dict[str, Any] = {}
        self._signals_connected: bool = False

        # Operation flags
        self._delete_in_progress: bool = False
        self._last_delete_timestamp: float = 0.0
        self._previous_name: Optional[str] = None

        # Required services - will be set by derived class
        self.worker_manager = None
        self.node_operations = None
        self.save_service = None

    def _load_empty_state(self):
        """Reset all UI components to their empty state while preserving headers and structure."""

        # Clear basic info fields
        self.ui.name_input.setText("")
        self.ui.description_input.clear()
        self.ui.tags_input.clear()
        self.ui.labels_input.clear()

        # Clear and reset properties table
        self.ui.properties_table.setRowCount(0)
        self.ui.properties_table.setHorizontalHeaderLabels(["Key", "Value", ""])

        # Clear and reset relationships table
        self.ui.relationships_table.setRowCount(0)
        self.ui.relationships_table.setHorizontalHeaderLabels(
            ["Type", "Related Node", "Direction", "Properties", " ", " "]
        )

        # Clear tree view
        tree_model = self.ui.tree_view.model()
        if tree_model:
            tree_model.clear()
            tree_model.setHorizontalHeaderLabels([self.NODE_RELATIONSHIPS_HEADER])

        # Reset map tab if it exists
        if self.ui.map_tab:
            map_tab_index = self.ui.tabs.indexOf(self.ui.map_tab)
            if map_tab_index != -1:
                self.ui.tabs.removeTab(map_tab_index)
                self.ui.map_tab = None

        # Reset save state
        if hasattr(self, "save_service"):
            self.save_service.update_save_state(None)
            self.ui.save_button.setStyleSheet(self.config.colors.passiveSave)

        # Reset operation flags
        self._delete_in_progress = False
        self._last_delete_time = 0.0

        # Ensure all buttons are enabled
        self.ui.save_button.setEnabled(True)
        self.ui.delete_button.setEnabled(True)

        logger.debug("UI reset to empty state")

    def load_node_data(self) -> None:
        """Load node data."""
        self._validate_service(self.node_operations, "node_operations")

        name = self.ui.name_input.text().strip()
        if not name:
            return

        # Clear all fields to populate them again
        self.ui.clear_all_fields()

        self.node_operations.load_node(
            name, self._handle_node_data, lambda: self.update_relationship_tree(name)
        )

    def rename_node(self, new_name: str) -> None:
        """
        Rename the current node using its element ID.

        Args:
            new_name (str): The new name for the node
        """
        if not self.current_node_element_id:
            return

        # Validate new name
        if not self.node_operations.validate_node_name(new_name).is_valid:
            return

        def handle_rename_success(success: bool) -> None:
            if success:
                self._handle_rename_success(new_name)
            else:
                self.error_handler.handle_error("Failed to rename node")

        worker = self.model.rename_node(
            self.current_node_element_id, new_name, handle_rename_success
        )

        operation = WorkerOperation(
            worker=worker,
            success_callback=handle_rename_success,
            error_callback=lambda msg: self.error_handler.handle_error(
                f"Error renaming node: {msg}"
            ),
            operation_name="rename_node",
        )

        self.worker_manager.execute_worker("rename", operation)

    def _handle_rename_success(self, new_name: str) -> None:
        """
        Handle successful node rename.

        Args:
            new_name: New name of the node
        """
        # Block signal handling temporarily
        old_state = self.ui.name_input.blockSignals(True)

        # Update UI with new name
        self.ui.name_input.setText(new_name)

        # Restore signal handling
        self.ui.name_input.blockSignals(old_state)

        # Reload node data
        self.load_node_data()

        # Update cache
        if self.name_cache_service:
            self.name_cache_service.invalidate_cache()
            self.name_cache_service.rebuild_cache()

        # Show success message
        QMessageBox.information(self.ui, "Success", "Node renamed successfully")

    def update_unsaved_changes_indicator(self) -> None:
        """Update unsaved changes indicator in UI."""
        self._validate_service(self.save_service, "save_service")

        current_data = self._get_current_node_data()
        if current_data and self.save_service.check_for_changes(current_data):
            self.ui.save_button.setStyleSheet(self.config.colors.activeSave)
        else:
            self.ui.save_button.setStyleSheet(self.config.colors.passiveSave)

    def _handle_node_data(self, data: List[Any]) -> None:
        """Handle node data loaded from database."""
        raise NotImplementedError("Must be implemented by child class")

    def _get_current_node_data(self) -> Optional[Dict[str, Any]]:
        """Get current node data from UI."""
        raise NotImplementedError("Must be implemented by child class")

    def update_relationship_tree(self, node_name: str) -> None:
        """Update relationship tree for node."""
        raise NotImplementedError("Must be implemented by child class")

    def _handle_error(self, error: str) -> None:
        """Centralized error handling."""
        if self.error_handler:
            self.error_handler.handle_error(error)

    def _validate_service(self, service: Any, name: str) -> None:
        """Validate required service exists."""
        if service is None:
            raise RuntimeError(f"Required service {name} not initialized")

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
            all_props=self.all_props,
        )

        if node_data:
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
        QTimer.singleShot(500, msg_box.accept)

        # Invalidate and rebuild name cache
        self.name_cache_service.invalidate_cache()
        self.name_cache_service.rebuild_cache()

        # Refresh UI state
        self.refresh_tree_view()
        self.load_node_data()
        if self.ui.map_tab:
            self.ui.map_tab.load_pins()
        self.update_unsaved_changes_indicator()

        # Activate the basic info tab
        self.ui.tabs.setCurrentIndex(0)

    def delete_node(self) -> None:
        """Handle node deletion request."""
        if self._delete_in_progress:
            logger.warning("delete_operation_already_in_progress")
            return

        # Guard against rapid successive calls (debounce)
        current_time = time.time()
        if current_time - self._last_delete_timestamp < 0.5:  # 500ms debounce
            logger.warning("delete_operation_debounced")
            return

        try:
            self._delete_in_progress = True
            self._last_delete_timestamp = current_time

            name = self.ui.name_input.text().strip()
            if not name:
                self._delete_in_progress = False
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
            else:
                self._cleanup_delete_operation()

        except Exception as e:
            logger.error("delete_operation_failed", error=str(e))
            self._cleanup_delete_operation()
            raise

    def _handle_delete_success(self, _: Any) -> None:
        """
        Handle successful node deletion.

        Args:
            _: The result of the delete operation.
        """
        try:
            # Invalidate and rebuild name cache
            self.name_cache_service.invalidate_cache()
            self.name_cache_service.rebuild_cache()

            QMessageBox.information(self.ui, "Success", "Node deleted successfully")
            self._load_empty_state()

        finally:
            self._cleanup_delete_operation()

    def _cleanup_delete_operation(self) -> None:
        """Clean up delete operation state."""
        self._delete_in_progress = False
        self.ui.delete_button.setEnabled(True)

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


class WorldBuildingController(BaseController, ExportMixin):
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
        name_cache_service: "NameCacheService",
    ) -> None:
        """
        Initialize the controller with UI, model, and configuration.

        Args:
            ui (WorldBuildingUI): The UI instance.
            model (Neo4jModel): The Neo4j model instance.
            config (Config): The configuration instance.
        """
        self.error_handler = ErrorHandler(ui_feedback_handler=self._show_error_dialog)
        super().__init__(
            ui=ui,
            model=model,
            config=config,
            app_instance=app_instance,
            error_handler=self.error_handler,
            name_cache_service=name_cache_service,
        )

        # Initialize services through initialization service
        self.init_service = InitializationService(
            controller=self,
            ui=ui,
            model=model,
            config=config,
            app_instance=app_instance,
            error_handler=self.error_handler,
            name_cache_service=name_cache_service,
        )

        self.init_service.initialize_application()
        self._setup_name_input_handling()

    def update_calendar_suggestions(self, text: str, completer) -> None:
        logger.debug("update_calendar_suggestions called", text=text)

        query = """
        MATCH (c:CALENDAR)
        WHERE c._project = $project 
        AND toLower(c.name) CONTAINS toLower($search)
        RETURN c.name as name, elementId(c) as element_id
        ORDER BY c.name
        """

        def handle_results(results):
            logger.debug("handle_results called", results=results)

            # Store element IDs for validation
            self.calendar_element_ids = {r["name"]: r["element_id"] for r in results}
            logger.debug("calendar_element_ids set", ids=self.calendar_element_ids)

            # Create string list model for completer
            completion_model = QStringListModel()
            name_list = [r["name"] for r in results]
            completion_model.setStringList(name_list)
            logger.debug("completion model created", names=name_list)

            # Set model on completer
            completer.setModel(completion_model)
            logger.debug("model set on completer")

        # Create worker first to store reference
        worker = self.model.execute_read_query(
            query, {"project": self.config.user.PROJECT, "search": text}
        )

        # Connect signals before creating operation
        worker.query_finished.connect(handle_results)

        operation = WorkerOperation(
            worker=worker,
            success_callback=None,  # Set to None since we're using direct signal connection
            error_callback=lambda msg: self.error_handler.handle_error(
                f"Error updating calendar suggestions: {msg}"
            ),
            operation_name="calendar_search",
        )

        self.worker_manager.execute_worker("calendar_search", operation)

    def add_calendar_relationship(self, calendar_name: str):
        """Add USES_CALENDAR relationship to relationship table"""
        # Remove any existing USES_CALENDAR relationships
        self._remove_calendar_relationships()

        # Add new relationship
        self.ui.add_relationship_row(
            rel_type="USES_CALENDAR",
            target=calendar_name,
            direction=">",
            properties="{}",
        )

        # Update save button state
        self.update_unsaved_changes_indicator()

    def _remove_calendar_relationships(self):
        """Remove any existing USES_CALENDAR relationships from table"""
        table = self.ui.relationships_table
        rows_to_remove = []

        # Find rows with USES_CALENDAR relationship
        for row in range(table.rowCount()):
            rel_type = table.item(row, 0)
            if rel_type and rel_type.text() == "USES_CALENDAR":
                rows_to_remove.append(row)

        # Remove rows in reverse order to maintain correct indices
        for row in sorted(rows_to_remove, reverse=True):
            table.removeRow(row)

    def _setup_name_input_handling(self) -> None:
        """Setup name input field event handling."""
        # Remove all focus event handling
        self._previous_name = self.ui.name_input.text().strip()
        # Add text changed handler
        self.ui.name_input.textChanged.connect(self._on_name_changed)

    def _on_name_changed(self, text: str) -> None:
        """Handle name input changes and load node data if it exists."""
        current_name = text.strip()

        # Skip if name hasn't actually changed
        if current_name == self._previous_name:
            return

        self._previous_name = current_name

        # Skip empty names
        if not current_name:
            self.ui.clear_all_fields()
            return

        logger.debug(
            "Name field changed",
            previous_name=self._previous_name,
            new_name=current_name,
        )

        def create_check_callback(name: str):
            """Create a callback that knows about the name being checked."""

            def callback(data: List[Any]) -> None:
                if data:  # Node exists
                    # Only load data if this is still the current name
                    if name == self.ui.name_input.text().strip():
                        self.load_node_data()
                else:
                    # Only clear if this is still the current name
                    if name == self.ui.name_input.text().strip():
                        logger.info("Wiping all_props for new node", new_name=name)
                        self.all_props = {}
                        self.ui.clear_all_fields()

            return callback

        # Create callback with closure over current_name
        callback = create_check_callback(current_name)

        # Check if node exists in database
        worker = self.model.load_node(current_name, callback)
        operation = WorkerOperation(
            worker=worker,
            success_callback=callback,
            error_callback=lambda msg: self.error_handler.handle_error(
                f"Error checking node: {msg}"
            ),
            operation_name="check_node_exists",
        )
        self.worker_manager.execute_worker("check", operation)

    def _add_target_completer_to_row(self, row: int) -> None:
        """
        Add target completer to the target input field in the relationship table.

        Args:
            row: The row number where the completer will be added
        """
        self.auto_completion_service.add_target_completer_to_row(
            self.ui.relationships_table, row
        )

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

            # Skip if any required field is missing
            if not all([rel_type, isinstance(target, QLineEdit), direction, props]):
                continue

            relationships.append(
                (
                    rel_type.text(),
                    target.text(),  # Now we know it's a QLineEdit
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

    def extract_element_id(self, data: dict) -> str | None:
        """
        Extract element_id from NeoWorldBuilder node data JSON.

        Args:
            data: Dictionary containing node data in format {"data": [[node_str, ...]]}

        Returns:
            str: The element_id if found
            None: If element_id cannot be extracted
        """
        """
            Extract element_id from NeoWorldBuilder node data.

            Args:
                data: List containing node data

            Returns:
                str: The element_id if found
                None: If element_id cannot be extracted
            """
        try:
            # Get the Node object from the Record
            node = data[0]["n"]

            # Get the Node's string representation
            node_str = str(node)

            # Extract element_id using string markers
            start_marker = "element_id='"
            end_marker = "'"

            start_pos = node_str.find(start_marker) + len(start_marker)
            end_pos = node_str.find(end_marker, start_pos)

            if start_pos == -1 or end_pos == -1:
                return None

            return node_str[start_pos:end_pos]

        except (IndexError, KeyError, AttributeError) as e:
            print(f"Error: {str(e)}")
            return None

    @pyqtSlot(list)
    def _handle_node_data(self, data: List[Any]) -> None:
        """Handle node data fetched by the worker."""
        if not data:
            return

        try:
            record = data[0]

            self.current_node_element_id = self.extract_element_id(data)
            logger.debug(
                "Current node element_id", element_id=self.current_node_element_id
            )

            self._populate_node_fields(record)

            # Simple direct all_props update from record
            self.all_props = record.get("all_props", {})
            if not isinstance(self.all_props, dict):
                self.all_props = {}

            # Reconstruct ParsedDate from flat properties
            parsed_date = None
            if "parsed_date_year" in self.all_props:
                try:
                    precision_str = self.all_props.get(
                        "parsed_date_precision", "EXACT"
                    )  # Default to EXACT if missing
                    precision = DatePrecision[precision_str]
                    range_start = None
                    range_end = None

                    if "parsed_date_range_start_year" in self.all_props:
                        range_start = ParsedDate(
                            year=self.all_props["parsed_date_range_start_year"],
                            month=self.all_props.get("parsed_date_range_start_month"),
                            day=self.all_props.get("parsed_date_range_start_day"),
                            precision=DatePrecision[
                                self.all_props.get(
                                    "parsed_date_range_start_precision", "EXACT"
                                )
                            ],  # Default to EXACT
                        )
                    if "parsed_date_range_end_year" in self.all_props:
                        range_end = ParsedDate(
                            year=self.all_props["parsed_date_range_end_year"],
                            month=self.all_props.get("parsed_date_range_end_month"),
                            day=self.all_props.get("parsed_date_range_end_day"),
                            precision=DatePrecision[
                                self.all_props.get(
                                    "parsed_date_range_end_precision", "EXACT"
                                )
                            ],  # Default to EXACT
                        )

                    parsed_date = ParsedDate(
                        year=self.all_props["parsed_date_year"],
                        month=self.all_props.get("parsed_date_month"),
                        day=self.all_props.get("parsed_date_day"),
                        precision=precision,
                        relative_to=self.all_props.get("parsed_date_relative_to"),
                        relative_days=self.all_props.get("parsed_date_relative_days"),
                        confidence=self.all_props.get(
                            "parsed_date_confidence", 1.0
                        ),  # Default to 1.0 if missing
                        season=self.all_props.get("parsed_date_season"),
                        range_start=range_start,
                        range_end=range_end,
                    )
                except (ValueError, KeyError) as e:
                    logger.warning(
                        "Error reconstructing ParsedDate from flat props", error=str(e)
                    )
                    parsed_date = None  # Handle reconstruction failure gracefully

            labels = record.get("labels", [])
            index_of_map_tab = self.ui.tabs.indexOf(self.ui.map_tab)
            if "MAP" in labels:
                self.ui.tabs.setCurrentIndex(index_of_map_tab)
            else:
                self.ui.tabs.setCurrentIndex(0)

            if "EVENT" in labels:
                self._setup_event_calendar()

                # Just pass the basic event data including the original temporal string
                event_data = {
                    "event_type": self.all_props.get("event_type", "Occurrence"),
                    "temporal_data": self.all_props.get(
                        "temporal_data", ""
                    ),  # Original date string
                    "relative_to": self.all_props.get("event_relative_to"),
                }

                if hasattr(self.ui, "event_tab") and self.ui.event_tab:
                    self.ui.event_tab.set_event_data(event_data)

            # Update original data for save state tracking
            self.original_node_data = self.node_operations.collect_node_data(
                name=self.ui.name_input.text().strip(),
                description=self.ui.description_input.toHtml().strip(),
                tags=self.ui.tags_input.text(),
                labels=self.ui.labels_input.text(),
                properties=self._collect_table_properties(),
                relationships=self._collect_table_relationships(),
                all_props=self.all_props,
            )

            # Update save state with new original data
            self.save_service.update_save_state(self.original_node_data)
            self.ui.save_button.setStyleSheet(self.config.colors.passiveSave)

        except AttributeError as e:
            logger.error("invalid_data_format", error=str(e))
            self.error_handler.handle_error("Invalid data format in node properties")
        except Exception as e:
            logger.error("node_processing_error", error=str(e))
            self.error_handler.handle_error(f"Error processing node data: {str(e)}")

    @pyqtSlot(object)
    def _populate_node_fields(self, record: Any) -> None:
        """
        Populate UI fields with node data.
        """
        try:
            node_data = self._extract_node_data(record)

            # Basic info population (existing code)
            self._populate_basic_info(node_data)
            self.ui.description_input.setHtml(node_data.get("description", ""))
            self._populate_properties(node_data["properties"])
            self._populate_relationships(node_data["relationships"])
            self._populate_basic_info_image(node_data["node_properties"])

            # Handle special node types
            labels = {label.upper() for label in node_data["labels"]}

            # Handle MAP nodes
            if "MAP" in labels:
                self._ensure_map_tab_exists()
                QTimer.singleShot(
                    0,
                    lambda: self._update_map_image(
                        node_data["properties"].get("mapimage")
                    ),
                )

            # Handle EVENT nodes
            if "EVENT" in record.get("labels", []):
                for rel in record.get("relationships", []):
                    if rel.get("type") == "USES_CALENDAR":
                        if hasattr(self.ui, "event_tab") and self.ui.event_tab:
                            self.ui.event_tab.update_calendar_name(rel.get("end", ""))
                        break

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

    def _ensure_map_tab_exists(self) -> None:
        """Create map tab if it doesn't exist."""
        if not self.ui.map_tab:

            self.ui.map_tab = MapTab(controller=self)

            self.ui.map_tab.map_image_changed.connect(self.ui._handle_map_image_changed)
            self.ui.map_tab.pin_clicked.connect(self._handle_pin_click)

            # Add new connection for pin creation
            self.ui.map_tab.pin_created.connect(self._handle_pin_created)

            self.ui.tabs.addTab(self.ui.map_tab, "Map")

    def _ensure_event_tab_exists(self) -> None:
        """Ensure event tab exists and is properly initialized"""
        if not hasattr(self.ui, "event_tab") or not self.ui.event_tab:
            # Create event tab if it doesn't exist
            self.ui.event_tab = EventTab(self)
            self.ui.tabs.addTab(self.ui.event_tab, "Event")

            # Connect event data change signal
            self.ui.event_tab.event_changed.connect(self._handle_event_data_changed)

    def _handle_event_data_changed(self, event_data: dict) -> None:
        """Handle changes to event data"""
        logger.debug(
            "_handle_event_data_changed: event_data received - START",
            event_data=event_data,
        )

        # Convert numeric values to strings before storing
        for key, value in event_data.items():
            if key.startswith("parsed_date_") and value is not None:
                self.all_props[key] = str(value)
            else:
                self.all_props[key] = value

        # Store other event data properties directly in all_props
        self.all_props["event_type"] = event_data["event_type"]
        self.all_props["temporal_data"] = event_data["temporal_data"]
        self.all_props["event_relative_to"] = event_data.get("event_relative_to")

        logger.debug(
            "_handle_event_changed: all_props final - END", all_props=self.all_props
        )
        self.update_unsaved_changes_indicator()

    def _handle_pin_created(
        self, target_node: str, direction: str, properties: dict
    ) -> None:
        """Handle creation of a new map pin relationship.

        Args:
            target_node: The node to link to
            direction: Relationship direction
            properties: Properties including x,y coordinates
        """
        # Get current node name (the map node)
        source_node = self.ui.name_input.text().strip()
        if not source_node:
            return

        # Add new relationship row with SHOWS type
        self.ui.add_relationship_row(
            "SHOWS", target_node, direction, json.dumps(properties)
        )

        # Update save state to reflect changes
        self.update_unsaved_changes_indicator()

    def _handle_pin_click(self, target_node: str) -> None:
        """Handle pin click by loading the target node."""

        self.ui.name_input.setText(target_node)

        self.load_node_data()
        self.ui.tabs.setCurrentIndex(0)

    def _populate_map_tab(self, node_data: Dict[str, Any]) -> None:
        """
        Handle map tab visibility and population.

        Args:
            node_data: Dictionary containing node information.
        """
        is_map_node = "MAP" in {label.upper() for label in node_data["labels"]}

        if is_map_node:
            self._ensure_map_tab_exists()
            self._update_map_image(node_data["properties"].get("mapimage"))
            self.ui.map_tab.load_pins()
        else:
            self._remove_map_tab()

    def _remove_map_tab(self) -> None:
        """Remove map tab if it exists."""
        if self.ui.map_tab:
            map_tab_index = self.ui.tabs.indexOf(self.ui.map_tab)
            if map_tab_index != -1:
                self.ui.tabs.removeTab(map_tab_index)
                self.ui.map_tab = None

    def _update_map_image(self, image_path: Optional[str]) -> None:
        """Update map image if map tab exists."""
        if self.ui.map_tab:
            self.ui.map_tab.set_map_image(image_path)

    def _populate_properties(self, properties: Dict[str, Any]) -> None:
        """
        Populate properties table.
        """
        logger.debug(
            "_populate_properties: received properties", properties=properties
        )  # Log received properties
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
        """
        logger.debug(
            "_add_property_row: adding property", key=key, value=value
        )  # Log each property row addition
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

    def _handle_basic_image_changed(self, image_path: str) -> None:
        """Handle image change signal from ImageGroup."""
        self.all_props["imagepath"] = image_path
        self.update_unsaved_changes_indicator()

    def _handle_basic_image_removed(self) -> None:
        """Handle image removal signal from ImageGroup."""
        self.all_props["imagepath"] = None
        self.update_unsaved_changes_indicator()

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
    # 8. Utility Methods
    #############################################

    def change_basic_image(self) -> None:
        """Handle image change request from UI."""
        result = self.image_service.select_image(self.ui)
        if result.success:
            self.all_props["imagepath"] = result.path
            self.ui.image_group.set_basic_image(result.path)
            self.update_unsaved_changes_indicator()
        else:
            self.error_handler.handle_error(
                f"Error changing image - {result.error_message}"
            )

    def delete_basic_image(self) -> None:
        """Handle image deletion request from UI."""
        self.all_props["imagepath"] = None
        self.ui.image_group.set_basic_image(None)
        self.update_unsaved_changes_indicator()

    def _collect_node_data_for_export(self, node_name: str) -> Optional[Dict[str, Any]]:
        """
        Collect node data for export.

        Args:
            node_name (str): The name of the node to collect data for.

        Returns:
            Optional[Dict[str, Any]]: The collected node data.
        """
        # First create a filtered copy of all_props
        filtered_props = {
            k: v
            for k, v in self.all_props.items()
            if k not in {"name", "description", "tags"}
        }

        return self.node_operations.collect_node_data(
            name=node_name,
            description=self.ui.description_input.toHtml().strip(),
            tags=self.ui.tags_input.text(),
            labels=self.ui.labels_input.text(),
            properties=self._collect_table_properties(),
            relationships=self._collect_table_relationships(),
            all_props=filtered_props,  # Use filtered version
        )

    def load_last_modified_node(self) -> None:
        """Load the last modified node and display it in the UI."""

        def on_load(data: List[Any]) -> None:
            self._handle_node_data(data)
            self.update_relationship_tree(self.ui.name_input.text().strip())

        self.node_operations.load_last_modified_node(on_load)

    def open_project_settings(self) -> None:
        dialog = ProjectSettingsDialog(self.config, self.app_instance)
        dialog.exec()

    def open_connection_settings(self) -> None:
        dialog = ConnectionSettingsDialog(self.config, self.app_instance)
        dialog.exec()

    def open_style_settings(self) -> None:
        dialog = StyleSettingsDialog(self.config, self.app_instance)
        dialog.exec()

    def _get_current_node_data(self) -> Optional[Dict[str, Any]]:
        """Implementation of base class method."""
        return self.node_operations.collect_node_data(
            name=self.ui.name_input.text().strip(),
            description=self.ui.description_input.toHtml().strip(),
            tags=self.ui.tags_input.text(),
            labels=self.ui.labels_input.text(),
            properties=self._collect_table_properties(),
            relationships=self._collect_table_relationships(),
            all_props=self.all_props,
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

    def _get_raw_calendar_properties(self) -> Dict[str, str]:
        """Get raw calendar properties from table."""
        logger.debug("Fetching raw calendar properties")
        properties = {}
        for row in range(self.properties_table.rowCount()):
            key_item = self.properties_table.item(row, 0)
            value_item = self.properties_table.item(row, 1)
            if key_item and value_item and key_item.text().startswith("calendar_"):
                properties[key_item.text()] = value_item.text().strip()
                logger.debug(
                    "Found calendar property",
                    key=key_item.text(),
                    value=value_item.text().strip(),
                )

        logger.debug("Raw calendar properties result", properties=properties)
        return properties

    def setup_calendar_data(self) -> None:
        """Load calendar data from flat properties."""
        # Log initial check
        logger.debug(
            "Starting calendar data setup",
            has_calendar_tab=bool(self.calendar_tab),
            has_raw_props=bool(self._get_raw_calendar_properties()),
        )

        if not self.calendar_tab or not self._get_raw_calendar_properties():
            logger.debug("Exiting early - missing required components")
            return

        try:
            raw_props = self._get_raw_calendar_properties()
            logger.debug("Raw calendar properties", raw_props=raw_props)

            calendar_data = {}

            # Known types for each property
            list_props = {"month_names", "month_days", "weekday_names"}
            int_props = {"current_year", "year_length", "days_per_week"}

            logger.debug(
                "Property type classifications",
                list_props=list_props,
                int_props=int_props,
            )

            for key, value in raw_props.items():
                # Remove calendar_ prefix
                clean_key = key.replace("calendar_", "")

                logger.debug(
                    "Processing property",
                    original_key=key,
                    clean_key=clean_key,
                    original_value=value,
                )

                try:
                    if clean_key in list_props:
                        if clean_key == "month_days":
                            # Convert to list of integers
                            split_values = value.split(",")
                            calendar_data[clean_key] = [
                                int(x) for x in split_values if x
                            ]
                            logger.debug(
                                "Processed list (integers)",
                                key=clean_key,
                                split_values=split_values,
                                result=calendar_data[clean_key],
                            )
                        else:
                            # Convert to list of strings
                            split_values = value.split(",")
                            calendar_data[clean_key] = [x for x in split_values if x]
                            logger.debug(
                                "Processed list (strings)",
                                key=clean_key,
                                split_values=split_values,
                                result=calendar_data[clean_key],
                            )
                    elif clean_key in int_props:
                        # Handle integers
                        calendar_data[clean_key] = int(value)
                        logger.debug(
                            "Processed integer",
                            key=clean_key,
                            value=value,
                            result=calendar_data[clean_key],
                        )
                    else:
                        # Handle strings
                        calendar_data[clean_key] = value
                        logger.debug("Processed string", key=clean_key, value=value)
                except Exception as conversion_error:
                    logger.error(
                        "Property conversion failed",
                        key=clean_key,
                        value=value,
                        error=str(conversion_error),
                    )
                    raise

            logger.debug("Final calendar data structure", calendar_data=calendar_data)
            self.calendar_tab.set_calendar_data(calendar_data)

        except Exception as e:
            logger.error(
                "calendar_setup_failed", error=str(e), error_type=type(e).__name__
            )
            raise

    def _handle_calendar_changed(self, calendar_data: Dict[str, Any]) -> None:
        """Handle changes to calendar data by storing in flat properties."""
        try:
            # Clear existing calendar properties
            self._clear_calendar_properties()

            # Store each property with appropriate type handling
            for key, value in calendar_data.items():
                if isinstance(value, list):
                    # Convert lists to comma-separated strings
                    stored_value = ",".join(str(x) for x in value)
                else:
                    # Store other values directly as strings
                    stored_value = str(value)

                self._add_calendar_property(f"calendar_{key}", stored_value)

            self.update_unsaved_changes_indicator()
        except Exception as e:
            logger.error("calendar_update_failed", error=str(e))

    def _handle_search_request(self, criteria: SearchCriteria) -> None:
        """
        Handle enhanced search request from search panel.

        Args:
            criteria: The enhanced search criteria
        """
        logger.debug(
            "handling_search_request",
            field_searches=[
                (fs.field.value, fs.text) for fs in criteria.field_searches
            ],
            label_filters=criteria.label_filters,
            required_properties=criteria.required_properties,
        )

        def handle_results(results: List[Dict[str, Any]]) -> None:
            """Handle search results callback."""
            self.ui.search_panel.display_results(results)

        # Execute search using search service
        self.search_service.search_nodes(
            criteria=criteria,  # Now using the enhanced criteria directly
            result_callback=handle_results,
            error_callback=lambda msg: self.ui.search_panel.handle_error(
                f"Search failed: {msg}"
            ),
        )

    def _handle_search_result_selected(self, node_name: str) -> None:
        """
        Handle selection of a search result.

        Args:
            node_name: The name of the selected node
        """
        logger.debug("Putting selected name into name text input", node_name=node_name)

        # Update the name input field
        self.ui.name_input.setText(node_name)

        # Switch to the main tab if we're in search
        if self.ui.tabs.currentWidget() == self.ui.search_panel:
            self.ui.tabs.setCurrentIndex(0)

    def _setup_event_calendar(self) -> None:
        """Set up calendar data for event nodes"""
        if not self.current_node_element_id:
            logger.error("No element_id available for calendar lookup")
            return

        # Query to get calendar data with proper prefixed property names
        calendar_query = """
        MATCH (n)-[r:USES_CALENDAR]->(c:CALENDAR)
        WHERE elementId(n) = $element_id
        AND n._project = $project
        RETURN {
            month_names: c.calendar_month_names,
            month_days: c.calendar_month_days,
            weekday_names: c.calendar_weekday_names,
            days_per_week: toInteger(c.calendar_days_per_week),
            year_length: toInteger(c.calendar_year_length),
            current_year: toInteger(c.calendar_current_year)
        } as calendar_data
        """

        logger.debug("_setup_event_calendar: before execute_worker calendar operation")
        worker = self.model.execute_read_query(
            calendar_query,
            {
                "element_id": self.current_node_element_id,
                "project": self.config.user.PROJECT,
            },
        )

        worker.query_finished.connect(
            self._handle_calendar_query_finished
        )  # ADD THIS LINE - Signal connection

        operation = WorkerOperation(
            worker=worker,
            success_callback=None,  # SET TO None - We are using signal now
            error_callback=lambda msg: self.error_handler.handle_error(
                f"Calendar query failed: {msg}"
            ),
            operation_name="calendar_lookup",
        )

        self.worker_manager.execute_worker("calendar", operation)
        logger.debug("_setup_event_calendar: after execute_worker calendar operation")

    def handle_calendar_data(
        self,
        result,
    ):  # Keep handle_calendar_data as is, but it will be called from signal handler
        """Process calendar data and update UI"""
        logger.debug("handle_calendar_data: raw result", result=result)
        if not result or not result[0].get("calendar_data"):
            logger.error("No calendar data found")
            return

        calendar_data = result[0]["calendar_data"]
        logger.debug("handle_calendar_data: calendar_data", calendar_data=calendar_data)

        # Convert month_days from string array to integer array
        calendar_data["month_days"] = [
            int(days) for days in calendar_data["month_days"]
        ]

        # Validate all fields exist and are of correct type
        try:
            required = {
                "month_names": list,
                "month_days": list,
                "weekday_names": list,
                "days_per_week": int,
                "year_length": int,
                "current_year": int,
            }

            for field, expected_type in required.items():
                if field not in calendar_data:
                    raise ValueError(f"Missing required field: {field}")
                if not isinstance(calendar_data[field], expected_type):
                    raise ValueError(
                        f"Field {field} has wrong type. Expected {expected_type}"
                    )

            # Set calendar data in event tab
            if hasattr(self.ui, "event_tab") and self.ui.event_tab:
                try:
                    self.ui.event_tab.set_calendar_data(calendar_data)
                    logger.info(
                        "Calendar data successfully set in event tab",
                        data=calendar_data,
                    )

                    # Load existing event data if present
                    if self.all_props.get("event_data"):
                        self.ui.event_tab.set_event_data(self.all_props["event_data"])
                except Exception as e:
                    logger.error(
                        "Failed to set calendar data in event tab", error=str(e)
                    )
            else:
                logger.error("Event tab not found")

        except Exception as e:
            logger.error("Calendar data validation failed", error=str(e))

    @pyqtSlot(list)
    def _handle_calendar_query_finished(self, result: list) -> None:
        """
        Handle the result from the calendar query worker.

        Args:
            result (list): The result data from the query worker.
        """
        logger.debug(
            "_handle_calendar_query_finished: Signal received", result=result
        )  # Add log

        # Now call the original handle_calendar_data function to process the result
        self.handle_calendar_data(result)

    def validate_calendar_node(self, element_id: str, callback: Callable) -> None:
        """Validate a node is a valid calendar using its element ID."""
        logger.debug("validate_calendar_node", element_id=element_id)
        query = """
        MATCH (c) 
        WHERE elementId(c) = $element_id 
        AND c._project = $project
        RETURN 'CALENDAR' IN labels(c) as is_calendar
        """

        worker = self.model.execute_read_query(
            query, {"element_id": element_id, "project": self.config.user.PROJECT}
        )

        operation = WorkerOperation(
            worker=worker,
            success_callback=callback,
            error_callback=lambda msg: self.error_handler.handle_error(
                f"Error validating calendar: {msg}"
            ),
            operation_name="validate_calendar",
        )

        self.worker_manager.execute_worker("validate_calendar", operation)
