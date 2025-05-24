import json
import time
from pathlib import Path
from typing import List, Tuple

from PyQt6.QtCore import Qt, pyqtSlot, QTimer
from PyQt6.QtGui import QStandardItem
from PyQt6.QtWidgets import (
    QCompleter,
    QTableWidgetItem,
    QTableWidget,
    QLineEdit,
    QApplication,
    QFileDialog,
)

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
from ui.mixins.exportmixin import ExportMixin
from ui.mixins.imagemixin import ImageMixin
from ui.mixins.mapmixin import MapMixin
from ui.mixins.nodedataextractionmixin import NodeDataExtractionMixin
from ui.mixins.nodedatapopulationmixin import NodeDataPopulationMixin

from utils.error_handler import ErrorHandler

from typing import Optional, Dict, Any
from PyQt6.QtCore import QObject
from PyQt6.QtWidgets import QMessageBox
from structlog import get_logger

from ui.mixins.calendarmixin import CalendarMixin
from ui.mixins.timelinemixin import TimelineMixin
from ui.mixins.eventmixin import EventMixin

logger = get_logger(__name__)


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

        # Store core dependencies as protected attributes
        self._ui = ui
        self._model = model
        self._config = config
        self._app_instance = app_instance
        self._error_handler = error_handler
        self._name_cache_service = name_cache_service

        # Essential state
        self.current_node_element_id: Optional[str] = None
        self._all_props: Dict[str, Any] = {}
        self._signals_connected: bool = False

        # Operation flags
        self._delete_in_progress: bool = False
        self._last_delete_timestamp: float = 0.0
        self._previous_name: Optional[str] = None

        # Required services - will be set by derived class
        self.worker_manager = None
        self.node_operations = None
        self.save_service = None

    # Add properties to access protected attributes
    @property
    def model(self):
        return self._model

    @property
    def error_handler(self):
        return self._error_handler

    @property
    def name_cache_service(self):
        return self._name_cache_service

    @property
    def app_instance(self):
        return self._app_instance

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
            self.ui.map_tab.load_features()
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


class WorldBuildingController(
    BaseController,
    ExportMixin,
    NodeDataExtractionMixin,
    NodeDataPopulationMixin,
    CalendarMixin,
    EventMixin,
    MapMixin,
    ImageMixin,
    TimelineMixin,
):
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
        # Create an error handler instance to pass to super()
        error_handler = ErrorHandler(ui_feedback_handler=self._show_error_dialog)

        # Initialize parent class
        super().__init__(
            ui=ui,
            model=model,
            config=config,
            app_instance=app_instance,
            error_handler=error_handler,  # Pass the created error handler
            name_cache_service=name_cache_service,
        )

        # Initialize services through initialization service
        self.init_service = InitializationService(
            controller=self,
            ui=ui,
            model=model,
            config=config,
            app_instance=app_instance,
            error_handler=self.error_handler,  # Use the property to access error handler
            name_cache_service=name_cache_service,
        )

        self.init_service.initialize_application()
        self._setup_name_input_handling()

    # Implement required properties from NodeDataMixin
    @property
    def ui(self):
        """The UI instance."""
        return self._ui

    @property
    def config(self):
        """The configuration instance."""
        return self._config

    @property
    def all_props(self):
        """Dictionary of all properties."""
        return self._all_props

    @all_props.setter
    def all_props(self, value):
        """Setter for all_props."""
        if not isinstance(value, dict):
            value = {}
        self._all_props = value

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

            # Handle TIMELINE nodes
            if "TIMELINE" in labels:
                self._setup_timeline_tab()
                self._setup_timeline_calendar()

        except Exception as e:
            self.error_handler.handle_error(f"Error populating node fields: {str(e)}")

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
            self.ui,
            "Select Fast Inject Template",
            "",
            "Fast Inject Files (*.fi);;All Files (*.*)",
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

    def enhance_node_description(self, depth: int = 0) -> None:
        """
        Use LLM to enhance the current node description with a default template.
        This is a simplified wrapper around the template-based enhancement.

        Args:
            depth: How many levels of connected nodes to include
        """
        # Define default parameters for quick enhancement
        template_id = "general"
        instructions = ""

        # Ensure templates are available
        if (
            not self.prompt_template_service
            or not self.prompt_template_service.get_template(template_id)
        ):
            QMessageBox.warning(
                self.ui,
                "Template Not Found",
                f"The template '{template_id}' was not found. Please ensure your template file exists and contains this template.",
            )
            return

        # Delegate to the template-based method
        self.enhance_node_description_with_template(template_id, depth, instructions)

    def enhance_node_description_with_template(
        self, template_id: str, depth: int, instructions: str
    ) -> None:
        """Use LLM to enhance node description with template-based approach."""
        current_node = self.ui.name_input.text().strip()
        current_description = self.ui.description_input.toHtml().strip()
        payload_description = self.ui.description_input.toPlainText().strip()

        if not current_description:
            QMessageBox.information(
                self.ui,
                "Empty Description",
                "Please enter a description before enhancing.",
            )
            return

        self.ui.show_loading(True)

        def handle_completion(enhanced_text: str, error: Optional[str]) -> None:
            self.ui.show_loading(False)
            if error:
                self.error_handler.handle_error(f"LLM Generation Error: {error}")
            elif enhanced_text:
                current_description = self.ui.description_input.toHtml().strip()
                payload_description = self.ui.description_input.toPlainText().strip()

                logger.debug(
                    "enhanced_description",
                    current_description=current_description,
                    payload_description=payload_description,
                    enhanced_text=enhanced_text,
                )
                new_description = (
                    f"{current_description}<br>⬆️Old   New⬇️<br>{enhanced_text}"
                )
                self.ui.description_input.setHtml(new_description)
                self.update_unsaved_changes_indicator()

        # Call the enhanced LLM service
        self.llm_service.enhance_description_with_template(
            current_node,
            payload_description,
            template_id,
            depth,
            instructions,
            handle_completion,
        )
