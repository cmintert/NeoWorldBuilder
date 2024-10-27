# Imports
import json
import sys
import logging
import os
import faulthandler
import traceback

from dataclasses import dataclass
from datetime import time
from logging.handlers import RotatingFileHandler

from typing import Optional, Dict, Any, List

from PyQt6.QtCore import (QThread, pyqtSignal, QTimer, QStringListModel, Qt, QObject, QMetaObject, Q_ARG, QObject,
                          pyqtSlot)
from PyQt6.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QCompleter,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QMessageBox,
    QTextEdit,
    QComboBox,
    QSplitter,
    QTreeView,
    QFileDialog,


    QGroupBox,
    QFormLayout,

    QMainWindow,
    QTabWidget,
    QProgressBar,
    QMenu,
)
from PyQt6.QtGui import (
    QStandardItemModel,

    QImage,
    QPalette,
    QBrush,

    QPixmap, QStandardItem,
)

from neo4j import GraphDatabase

# Configure logging
logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s"
)

faulthandler.enable()

def exception_hook(exctype, value, tb):
    logging.critical("Unhandled exception", exc_info=(exctype, value, tb))
    traceback.print_exception(exctype, value, tb)
    sys.__excepthook__(exctype, value, tb)
    QMessageBox.critical(None, "Unhandled Exception", f"An unhandled exception occurred:\n{value}")

sys.excepthook = exception_hook


class Config:
    def __init__(self, json_file):
        with open(json_file, "r") as f:
            constants = json.load(f)
        for category, values in constants.items():
            if isinstance(values, dict):
                for key, value in values.items():
                    setattr(self, f"{category}_{key}", value)
            else:
                setattr(self, category, values)

class BaseNeo4jWorker(QThread):
    """Base class for Neo4j worker threads"""

    error_occurred = pyqtSignal(str)
    progress_updated = pyqtSignal(int)

    def __init__(self, uri, auth):
        super().__init__()
        self._uri = uri
        self._auth = auth
        self._driver = None
        self._is_cancelled = False

    def connect(self):
        """Create Neo4j driver connection"""
        if not self._driver:
            self._driver = GraphDatabase.driver(self._uri, auth=self._auth)

    def cleanup(self):
        """Clean up resources"""
        if self._driver:
            self._driver.close()
            self._driver = None

    def cancel(self):
        """Cancel current operation"""
        self._is_cancelled = True
        self.quit()  # Tell thread to quit
        self.wait()

    def run(self):
            """Base run implementation"""
            try:
                self.connect()
                self.execute_operation()
            except Exception as e:
                self.error_occurred.emit(str(e))
            finally:
                self.cleanup()

    def execute_operation(self):
        """Override in subclasses"""
        raise NotImplementedError


class QueryWorker(BaseNeo4jWorker):
    """Worker for read operations"""

    query_finished = pyqtSignal(list)

    def __init__(self, uri, auth, query, params=None):
        super().__init__(uri, auth)
        self.query = query
        self.params = params or {}

    def execute_operation(self):
        try:
            with self._driver.session() as session:
                result = list(session.run(self.query, self.params))
                if not self._is_cancelled:
                    self.query_finished.emit(result)
        except Exception as e:
            error_message = ''.join(traceback.format_exception(type(e), e, e.__traceback__))
            self.error_occurred.emit(error_message)


class WriteWorker(BaseNeo4jWorker):
    """Worker for write operations"""

    write_finished = pyqtSignal(bool)

    def __init__(self, uri, auth, func, *args):
        super().__init__(uri, auth)
        self.func = func
        self.args = args

    def execute_operation(self):
        with self._driver.session() as session:
            session.execute_write(self.func, *self.args)
            if not self._is_cancelled:
                self.write_finished.emit(True)

    @staticmethod
    def _run_transaction(tx, query, params):
        return tx.run(query, params)


class BatchWorker(BaseNeo4jWorker):
    """Worker for batch operations"""

    batch_progress = pyqtSignal(int, int)  # current, total
    batch_finished = pyqtSignal(list)

    def __init__(self, driver_config, operations):
        super().__init__(driver_config)
        self.operations = operations

    def execute_operation(self):
        results = []
        total = len(self.operations)

        with self._driver.session() as session:
            for i, (query, params) in enumerate(self.operations, 1):
                if self._is_cancelled:
                    break

                result = session.run(query, params or {})
                results.extend(list(result))
                self.batch_progress.emit(i, total)

        if not self._is_cancelled:
            self.batch_finished.emit(results)


class Neo4jWorkerManager:
    """Manages Neo4j worker threads"""

    def __init__(self, config):
        self.config = config
        self.active_workers = set()

    def create_worker(self, worker_class, *args, **kwargs):
        """Create and setup a new worker"""
        worker = worker_class(self.config, *args, **kwargs)
        worker.finished.connect(lambda: self._cleanup_worker(worker))
        self.active_workers.add(worker)
        return worker

    def _cleanup_worker(self, worker):
        """Clean up finished worker"""
        if worker in self.active_workers:
            self.active_workers.remove(worker)

    def cancel_all(self):
        """Cancel all active workers"""
        for worker in self.active_workers:
            worker.cancel()
            worker.wait()
        self.active_workers.clear()


class Neo4jModel:
    #############################################
    # 1. Connection Management
    #############################################

    def __init__(self, uri, username, password):
        """Initialize Neo4j connection parameters and establish connection."""
        self._uri = uri
        self._auth = (username, password)
        self._driver = None
        self.connect()
        logging.info("Neo4jModel initialized and connected to the database.")

    def connect(self):
        """Establish connection to Neo4j"""
        if not self._driver:
            self._driver = GraphDatabase.driver(self._uri, auth=self._auth)

    def ensure_connection(self):
        """Ensure we have a valid connection, reconnect if necessary"""
        try:
            if self._driver:
                self._driver.verify_connectivity()
            else:
                self.connect()
        except Exception as e:
            logging.warning(f"Connection verification failed: {e}")
            self.connect()

    def get_session(self):
        """Get a database session, ensuring connection is valid"""
        self.ensure_connection()
        return self._driver.session()

    def close(self):
        """Safely close the driver"""
        if self._driver:
            try:
                self._driver.close()
            finally:
                self._driver = None
        logging.info("Neo4jModel connection closed.")

    #############################################
    # 2. Node CRUD Operations
    #############################################

    def load_node(self, name, callback):
        """
        Load a node and its relationships by name using a worker.

        Args:
            name (str): Name of the node to load
            callback (function): Function to call with the result

        Returns:
            QueryWorker: A worker that will execute the query
        """
        query = """
            MATCH (n:Node {name: $name})
            WITH n, labels(n) AS labels,
                 [(n)-[r]->(m) | {end: m.name, type: type(r), dir: '>', props: properties(r)}] AS out_rels,
                 [(n)<-[r2]-(o) | {end: o.name, type: type(r2), dir: '<', props: properties(r2)}] AS in_rels,
                 properties(n) AS all_props
            RETURN n,
                   out_rels + in_rels AS relationships,
                   labels,
                   all_props
            LIMIT 1
        """
        params = {"name": name}
        worker = QueryWorker(self._uri, self._auth, query, params)
        worker.query_finished.connect(callback)
        return worker

    def save_node(self, node_data, callback):
        """
        Save or update a node and its relationships using a worker.

        Args:
            node_data (dict): Node data including properties and relationships
            callback (function): Function to call when done

        Returns:
            WriteWorker: A worker that will execute the write operation
        """
        worker = WriteWorker(self._uri, self._auth, self._save_node_transaction, node_data)
        worker.write_finished.connect(callback)
        return worker

    @staticmethod
    def _save_node_transaction(tx, node_data):
        """
        Private transaction handler for save_node.
        Handles the complex transaction of saving a node and its relationships.
        """
        # Extract data from node_data
        name = node_data["name"]
        description = node_data["description"]
        tags = node_data["tags"]
        additional_properties = node_data["additional_properties"]
        relationships = node_data["relationships"]
        labels = node_data["labels"]

        # Merge with 'Node' label
        query_merge = (
            "MERGE (n:Node {name: $name}) "
            "SET n.description = $description, n.tags = $tags"
        )
        tx.run(query_merge, name=name, description=description, tags=tags)

        # Retrieve existing labels excluding 'Node'
        result = tx.run(
            "MATCH (n:Node {name: $name}) RETURN labels(n) AS labels", name=name
        )
        record = result.single()
        existing_labels = record["labels"] if record else []
        existing_labels = [label for label in existing_labels if label != "Node"]

        # Determine labels to add and remove
        input_labels_set = set(labels)
        existing_labels_set = set(existing_labels)

        labels_to_add = input_labels_set - existing_labels_set
        labels_to_remove = existing_labels_set - input_labels_set

        # Add new labels
        if labels_to_add:
            labels_str = ":".join([f"`{label}`" for label in labels_to_add])
            query_add = f"MATCH (n:Node {{name: $name}}) SET n:{labels_str}"
            tx.run(query_add, name=name)

        # Remove labels that are no longer needed
        if labels_to_remove:
            labels_str = ", ".join([f"n:`{label}`" for label in labels_to_remove])
            query_remove = f"MATCH (n:Node {{name: $name}}) REMOVE {labels_str}"
            tx.run(query_remove, name=name)

        # Set additional properties if any
        if additional_properties:
            # Remove image_path if it's None
            if (
                "image_path" in additional_properties
                and additional_properties["image_path"] is None
            ):
                tx.run("MATCH (n:Node {name: $name}) REMOVE n.image_path", name=name)
                del additional_properties["image_path"]
            if additional_properties:
                query_props = (
                    "MATCH (n:Node {name: $name}) SET n += $additional_properties"
                )
                tx.run(
                    query_props, name=name, additional_properties=additional_properties
                )

        # Remove existing relationships
        query_remove_rels = "MATCH (n:Node {name: $name})-[r]-() DELETE r"
        tx.run(query_remove_rels, name=name)

        # Create/update relationships
        for rel in relationships:
            rel_type, rel_name, direction, properties = rel
            if direction == ">":
                query_rel = (
                    "MATCH (n:Node {name: $name}) "
                    "WITH n "
                    "MATCH (m:Node {name: $rel_name}) "
                    f"MERGE (n)-[r:`{rel_type}`]->(m) "
                    "SET r = $properties"
                )
            else:
                query_rel = (
                    "MATCH (n:Node {name: $name}) "
                    "WITH n "
                    "MATCH (m:Node {name: $rel_name}) "
                    f"MERGE (m)-[r:`{rel_type}`]->(n) "
                    "SET r = $properties"
                )
            tx.run(query_rel, name=name, rel_name=rel_name, properties=properties)

    def delete_node(self, name, callback):
        """
        Delete a node and all its relationships using a worker.

        Args:
            name (str): Name of the node to delete
            callback (function): Function to call when done

        Returns:
            WriteWorker: A worker that will execute the delete operation
        """
        worker = WriteWorker(self._uri, self._auth, self._delete_node_transaction, name)
        worker.write_finished.connect(callback)
        return worker

    @staticmethod
    def _delete_node_transaction(tx, name):
        """Private transaction handler for delete_node."""
        query = "MATCH (n:Node {name: $name}) DETACH DELETE n"
        tx.run(query, name=name)

    #############################################
    # 3. Node Query Operations
    #############################################

    def get_node_relationships(self, node_name, callback):
        query = """
            MATCH (n:Node {name: $name})
            OPTIONAL MATCH (n)-[r]->(m:Node)
            WITH n, collect({end: m.name, type: type(r), dir: '>'}) as outRels
            OPTIONAL MATCH (n)<-[r2]-(o:Node)
            WITH n, outRels, collect({end: o.name, type: type(r2), dir: '<'}) as inRels
            RETURN outRels + inRels as relationships
        """
        params = {"name": node_name}
        worker = QueryWorker(self._uri, self._auth, query, params)
        worker.query_finished.connect(callback)
        return worker

    def get_node_hierarchy(self):
        """
        Get the hierarchy of nodes grouped by their primary label.

        Returns:
            dict: Category to node names mapping
        """
        with self.get_session() as session:
            result = session.run(
                """
                MATCH (n:Node)
                WITH n, labels(n) AS labels
                WHERE size(labels) > 1
                RETURN DISTINCT head(labels) as category, 
                       collect(n.name) as nodes
                ORDER BY category
            """
            )
            return {record["category"]: record["nodes"] for record in result}

    def fetch_matching_node_names(self, prefix, limit, callback):
        """
        Search for nodes whose names match a given prefix using a worker.

        Args:
            prefix (str): The search prefix
            limit (int): Maximum number of results to return
            callback (function): Function to call with the result

        Returns:
            QueryWorker: A worker that will execute the query
        """
        query = (
            "MATCH (n:Node) WHERE toLower(n.name) CONTAINS toLower($prefix) "
            "RETURN n.name AS name LIMIT $limit"
        )
        params = {"prefix": prefix, "limit": limit}
        worker = QueryWorker(self._uri, self._auth, query, params)
        worker.query_finished.connect(callback)
        return worker


class WorldBuildingUI(QWidget):
    """Enhanced UI class with thread-aware components and better feedback"""

    # Class-level signals
    name_selected = pyqtSignal(str)
    refresh_requested = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.init_ui()
        self.apply_styles()

    def init_ui(self):
        """Initialize the main UI layout with enhanced components"""
        main_layout = QHBoxLayout()
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(20)

        # Create splitter for resizable panels
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left panel with search and tree
        left_panel = self._create_left_panel()
        splitter.addWidget(left_panel)

        # Right panel with node details and progress
        right_panel = self._create_right_panel()
        splitter.addWidget(right_panel)

        # Set stretch factors
        splitter.setStretchFactor(0, 1)  # Left panel
        splitter.setStretchFactor(1, 2)  # Right panel gets more space

        main_layout.addWidget(splitter)
        self.setLayout(main_layout)

    def _create_left_panel(self):
        """Create improved left panel with tree view and search"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        # Enhanced tree view
        self.tree_view = QTreeView()
        self.tree_view.setObjectName("treeView")
        self.tree_view.setHeaderHidden(True)
        self.tree_view.setAnimated(True)
        self.tree_view.setAlternatingRowColors(True)
        self.tree_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree_view.customContextMenuRequested.connect(self._show_tree_context_menu)

        layout.addWidget(self.tree_view)

        # Add status label
        self.status_label = QLabel("Ready")
        self.status_label.setObjectName("statusLabel")
        layout.addWidget(self.status_label)

        return panel

    def _create_right_panel(self):
        """Create improved right panel with proper spacing and opacity"""
        panel = QWidget()

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(15)

        # Header with node name and actions
        header_widget = QWidget()
        header_layout = self._create_header_layout()
        header_widget.setLayout(header_layout)
        layout.addWidget(header_widget)

        # Progress bar (initially hidden)
        self.progress_bar = QProgressBar()
        self.progress_bar.setObjectName("progressBar")
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # Tabs
        self.tabs = QTabWidget()
        self.tabs.setObjectName("mainTabs")
        self.tabs.addTab(self._create_basic_info_tab(), "Basic Info")
        self.tabs.addTab(self._create_relationships_tab(), "Relationships")
        self.tabs.addTab(self._create_properties_tab(), "Properties")

        layout.addWidget(self.tabs)
        return panel

    def _create_header_layout(self):
        """Create enhanced header with loading indication"""
        layout = QHBoxLayout()

        # Node name input
        self.name_input = QLineEdit()
        self.name_input.setObjectName("nameInput")
        self.name_input.setPlaceholderText("Enter node name...")
        self.name_input.setMinimumHeight(35)
        self.name_input.setMaxLength(100)

        # Action buttons with loading states
        self.save_button = QPushButton("💾 Save")
        self.save_button.setObjectName("saveButton")
        self.delete_button = QPushButton("🗑️ Delete")
        self.delete_button.setObjectName("deleteButton")
        self.cancel_button = QPushButton("⚠️ Cancel")
        self.cancel_button.setObjectName("cancelButton")
        self.cancel_button.setVisible(False)

        # Style buttons
        for button in [self.save_button, self.delete_button, self.cancel_button]:
            button.setMinimumHeight(35)
            button.setFixedWidth(100)

        layout.addWidget(self.name_input, stretch=1)
        layout.addWidget(self.save_button)
        layout.addWidget(self.delete_button)
        layout.addWidget(self.cancel_button)

        return layout

    def _create_basic_info_tab(self):
        """Create the basic info tab with input fields and image handling"""
        tab = QWidget()
        layout = QFormLayout(tab)
        layout.setSpacing(15)

        # Description
        self.description_input = QTextEdit()
        self.description_input.setObjectName("descriptionInput")
        self.description_input.setPlaceholderText("Enter description...")
        self.description_input.setMinimumHeight(100)

        # Labels with auto-completion
        self.labels_input = QLineEdit()
        self.labels_input.setObjectName("labelsInput")
        self.labels_input.setPlaceholderText("Enter labels (comma-separated)")

        # Tags
        self.tags_input = QLineEdit()
        self.tags_input.setObjectName("tagsInput")
        self.tags_input.setPlaceholderText("Enter tags (comma-separated)")

        # Image section
        image_group = self._create_image_group()

        layout.addRow("Description:", self.description_input)
        layout.addRow("Labels:", self.labels_input)
        layout.addRow("Tags:", self.tags_input)
        layout.addRow(image_group)

        return tab

    def _create_image_group(self):
        """Create the image display group"""
        group = QGroupBox("Image")
        group.setObjectName("imageGroupBox")
        layout = QVBoxLayout()

        # Image display
        self.image_label = QLabel()
        self.image_label.setObjectName("imageLabel")
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setFixedSize(200, 200)

        layout.addWidget(self.image_label)

        # Image buttons
        button_layout = QHBoxLayout()
        button_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.change_image_button = QPushButton("📷 Change")
        self.change_image_button.setObjectName("changeImageButton")
        self.delete_image_button = QPushButton("🗑️ Remove")
        self.delete_image_button.setObjectName("deleteImageButton")

        for button in [self.change_image_button, self.delete_image_button]:
            button.setFixedWidth(97)
            button.setMinimumHeight(30)

        button_layout.addWidget(self.change_image_button)
        button_layout.addWidget(self.delete_image_button)
        button_layout.addStretch()
        layout.addLayout(button_layout)

        group.setLayout(layout)
        return group

    def _create_relationships_tab(self):
        """Create relationships tab with table"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Add relationship button
        self.add_rel_button = QPushButton("➕ Add Relationship")
        self.add_rel_button.setObjectName("addRelationshipButton")
        self.add_rel_button.setFixedWidth(150)
        self.add_rel_button.setMinimumHeight(30)

        # Enhanced table
        self.relationships_table = QTableWidget(0, 4)
        self.relationships_table.setObjectName("relationshipsTable")
        self.relationships_table.setHorizontalHeaderLabels(
            ["Type", "Related Node", "Direction", "Properties"]
        )
        self.relationships_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.relationships_table.setAlternatingRowColors(True)
        self.relationships_table.verticalHeader().setVisible(False)


        layout.addWidget(self.add_rel_button)
        layout.addWidget(self.relationships_table)
        return tab

    def _create_properties_tab(self):
        """Create properties tab with table"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Add property button
        self.add_prop_button = QPushButton("➕ Add Property")
        self.add_prop_button.setObjectName("addPropertyButton")
        self.add_prop_button.setFixedWidth(150)
        self.add_prop_button.setMinimumHeight(30)

        # Enhanced table
        self.properties_table = QTableWidget(0, 2)
        self.properties_table.setObjectName("propertiesTable")
        self.properties_table.setHorizontalHeaderLabels(["Key", "Value"])
        self.properties_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.properties_table.setAlternatingRowColors(True)
        self.properties_table.verticalHeader().setVisible(False)

        layout.addWidget(self.add_prop_button)
        layout.addWidget(self.properties_table)
        return tab

    def _show_tree_context_menu(self, position):
        """Show context menu for tree items"""
        menu = QMenu()

        # Add actions based on selected item
        expand_action = menu.addAction("Expand All")
        collapse_action = menu.addAction("Collapse All")
        refresh_action = menu.addAction("Refresh")

        # Execute menu and handle selection
        action = menu.exec_(self.tree_view.mapToGlobal(position))
        if action == expand_action:
            self.tree_view.expandAll()
        elif action == collapse_action:
            self.tree_view.collapseAll()
        elif action == refresh_action:
            self.refresh_requested.emit()

    #############################################
    # Progress and Status Methods
    #############################################

    def show_progress(self, visible: bool = True):
        """Show or hide progress bar"""
        self.progress_bar.setVisible(visible)
        if visible:
            self.progress_bar.setValue(0)

    def set_progress(self, value: int, maximum: int = 100):
        """Update progress bar"""
        self.progress_bar.setMaximum(maximum)
        self.progress_bar.setValue(value)

    def set_status(self, message: str):
        """Update status message"""
        self.status_label.setText(message)

    def show_loading(self, is_loading: bool):
        """Show loading state"""
        self.save_button.setEnabled(not is_loading)
        self.delete_button.setEnabled(not is_loading)
        self.cancel_button.setVisible(is_loading)
        self.name_input.setReadOnly(is_loading)

    #############################################
    # UI Update Methods
    #############################################

    def clear_all_fields(self):
        """Clear all input fields"""
        self.name_input.clear()
        self.description_input.clear()
        self.labels_input.clear()
        self.tags_input.clear()
        self.properties_table.setRowCount(0)
        self.relationships_table.setRowCount(0)
        self.image_label.clear()

    def set_image(self, image_path: Optional[str]):
        """Set image with proper scaling and error handling"""
        if not image_path:
            self.image_label.clear()
            return

        try:
            pixmap = QPixmap(image_path)
            if not pixmap.isNull():
                scaled_pixmap = pixmap.scaled(
                    self.image_label.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
                )
                self.image_label.setPixmap(scaled_pixmap)
            else:
                raise ValueError("Failed to load image")
        except Exception as e:
            self.image_label.clear()
            QMessageBox.warning(self, "Image Error", f"Failed to load image: {str(e)}")



    def add_relationship_row(
        self, rel_type="", target="", direction=">", properties=""
    ):
        """Add relationship row with improved validation"""
        row = self.relationships_table.rowCount()
        self.relationships_table.insertRow(row)

        # Type with validation
        type_item = QTableWidgetItem(rel_type)
        self.relationships_table.setItem(row, 0, type_item)

        # Target with completion
        target_item = QTableWidgetItem(target)
        self.relationships_table.setItem(row, 1, target_item)

        # Direction ComboBox
        direction_combo = QComboBox()
        direction_combo.addItems([">", "<"])
        direction_combo.setCurrentText(direction)
        self.relationships_table.setCellWidget(row, 2, direction_combo)

        # Properties with validation
        props_item = QTableWidgetItem(properties)
        self.relationships_table.setItem(row, 3, props_item)

    def apply_styles(self):
        try:

            current_dir = os.path.dirname(os.path.abspath(__file__))
            stylesheet_path = os.path.join(current_dir, "style_default.qss")

            with open(stylesheet_path, "r") as f:
                stylesheet = f.read()
            self.setStyleSheet(stylesheet)
            logging.info(f"Stylesheet applied successfully from {stylesheet_path}")
        except Exception as e:
            error_message = f"Failed to load stylesheet: {e}"
            logging.error(error_message)
            QMessageBox.warning(self, "Stylesheet Error", error_message)


class WorldBuildingController(QObject):
    """
    Controller class managing interaction between UI and Neo4j model using QThread workers
    """

    def __init__(self, ui: "WorldBuildingUI", model: "Neo4jModel", config: "Config"):
        super().__init__()
        self.ui = ui
        self.model = model
        self.config = config
        self.current_image_path: Optional[str] = None

        # Initialize UI state
        self._initialize_tree_view()
        self._initialize_completer()
        self._setup_debounce_timer()
        self._connect_signals()
        self._load_default_state()

        # Initialize worker manager
        self.current_load_worker = None
        self.current_save_worker = None
        self.current_relationship_worker = None
        self.current_search_worker = None

    #############################################
    # 1. Initialization Methods
    #############################################

    def _initialize_tree_view(self):
        """Initialize the tree view model"""
        self.tree_model = QStandardItemModel()
        self.tree_model.setHorizontalHeaderLabels(["Node Relationships"])
        self.ui.tree_view.setModel(self.tree_model)
        self.ui.tree_view.selectionModel().selectionChanged.connect(
            self.on_tree_selection_changed
        )

    def _initialize_completer(self):
        """Initialize name auto-completion"""
        self.node_name_model = QStringListModel()
        self.completer = QCompleter(self.node_name_model)
        self.completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.ui.name_input.setCompleter(self.completer)
        self.completer.activated.connect(self.on_completer_activated)

    def _setup_debounce_timer(self):
        """Setup debounce timer for search"""
        self.name_input_timer = QTimer()
        self.name_input_timer.setSingleShot(True)
        self.name_input_timer.timeout.connect(self._fetch_matching_nodes)
        self.name_input_timer.setInterval(self.config.TIMING_NAME_INPUT_DEBOUNCE_TIME_MS)

    def _connect_signals(self):
        """Connect all UI signals to handlers"""
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
        self.ui.add_prop_button.clicked.connect(
            lambda: self.ui.properties_table.insertRow(
                self.ui.properties_table.rowCount()
            )
        )
        self.ui.add_rel_button.clicked.connect(lambda: self.ui.add_relationship_row())

    def _load_default_state(self):
        """Initialize default UI state"""
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

    def load_node_data(self):
        """Load node data using worker thread"""
        name = self.ui.name_input.text().strip()
        if not name:
            return

        # Cancel any existing load operation
        if self.current_load_worker:
            self.current_load_worker.cancel()
            self.current_load_worker.wait()

        # Start new load operation
        self.current_load_worker = self.model.load_node(name, self._handle_node_data)
        self.current_load_worker.error_occurred.connect(self.handle_error)
        self.current_load_worker.start()

        # Update relationship tree
        self.update_relationship_tree(name)

    def save_node(self):
        """Save node data using worker thread"""
        name = self.ui.name_input.text().strip()
        if not self.validate_node_name(name):
            return

        node_data = self._collect_node_data()
        if not node_data:
            return

        # Cancel any existing save operation
        if hasattr(self, 'current_save_worker') and self.current_save_worker:
            self.current_save_worker.cancel()

        # Start new save operation
        self.current_save_worker = self.model.save_node(node_data, self.on_save_success)
        self.current_save_worker.error_occurred.connect(self.handle_error)
        self.current_save_worker.start()

    def delete_node(self):
        """Delete node using worker thread"""
        name = self.ui.name_input.text().strip()
        if not name:
            return

        reply = QMessageBox.question(
            self.ui,
            "Confirm Deletion",
            f'Are you sure you want to delete node "{name}"?',
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        if reply == QMessageBox.Yes:
            worker = self.model.delete_node(name, self._handle_delete_success)
            worker.error_occurred.connect(self.handle_error)
            worker.start()

    #############################################
    # 3. Tree and Relationship Management
    #############################################

    def update_relationship_tree(self, node_name: str):
        """Update tree view with node relationships"""
        if not node_name:
            self.tree_model.clear()
            self.tree_model.setHorizontalHeaderLabels(["Node Relationships"])
            return

        # Cancel any existing relationship worker
        if self.current_relationship_worker:
            self.current_relationship_worker.cancel()
            self.current_relationship_worker.wait()

        self.current_relationship_worker = self.model.get_node_relationships(
            node_name, self._populate_relationship_tree
        )
        self.current_relationship_worker.error_occurred.connect(self.handle_error)
        self.current_relationship_worker.start()

    def refresh_tree_view(self):
        """Refresh the entire tree view"""
        name = self.ui.name_input.text().strip()
        if name:
            self.update_relationship_tree(name)

    def on_tree_selection_changed(self, selected, deselected):
        """Handle tree view selection changes"""
        indexes = selected.indexes()
        if indexes:
            selected_item = self.tree_model.itemFromIndex(indexes[0])
            if selected_item and selected_item.parent():
                text = selected_item.text()
                if text.startswith("🔵"):
                    node_name = text[2:].strip()
                    if node_name != self.ui.name_input.text():
                        self.ui.name_input.setText(node_name)
                        self.load_node_data()

    #############################################
    # 4. Auto-completion and Search
    #############################################

    def debounce_name_input(self, text: str):
        """Debounce name input for search"""
        self.name_input_timer.stop()
        if text.strip():
            self.name_input_timer.start()

    def _fetch_matching_nodes(self):
        """Fetch matching nodes for auto-completion"""
        text = self.ui.name_input.text().strip()
        if not text:
            return

        # Cancel any existing search worker
        if self.current_search_worker:
            self.current_search_worker.cancel()
            self.current_search_worker.wait()

        self.current_search_worker = self.model.fetch_matching_node_names(
            text, self.config.NEO4J_MATCH_NODE_LIMIT, self._handle_autocomplete_results
        )
        self.current_search_worker.error_occurred.connect(self.handle_error)
        self.current_search_worker.start()

    def on_completer_activated(self, text: str):
        """Handle completer selection"""
        if text:
            self.ui.name_input.setText(text)
            self.load_node_data()

    #############################################
    # 5. Data Collection and Validation
    #############################################

    def _collect_node_data(self) -> Optional[Dict[str, Any]]:
        """Collect all node data from UI"""
        try:
            node_data = {
                "name": self.ui.name_input.text().strip(),
                "description": self.ui.description_input.toPlainText().strip(),
                "tags": self._parse_comma_separated(self.ui.tags_input.text()),
                "labels": self._parse_comma_separated(self.ui.labels_input.text()),
                "relationships": self._collect_relationships(),
                "additional_properties": self._collect_properties(),
            }

            if self.current_image_path:
                node_data["additional_properties"][
                    "image_path"
                ] = self.current_image_path
            else:
                node_data["additional_properties"]["image_path"] = None

            return node_data
        except ValueError as e:
            self.handle_error(str(e))
            return None

    def _collect_properties(self) -> Dict[str, Any]:
        """Collect properties from table"""
        properties = {}
        for row in range(self.ui.properties_table.rowCount()):
            key = self.ui.properties_table.item(row, 0)
            value = self.ui.properties_table.item(row, 1)

            if not key or not key.text().strip():
                continue

            key_text = key.text().strip()
            if key_text.lower() in self.config.RESERVED_PROPERTY_KEYS:
                raise ValueError(f"Property key '{key_text}' is reserved")

            try:
                value_text = value.text().strip() if value else ""
                properties[key_text] = (
                    json.loads(value_text) if value_text else value_text
                )
            except json.JSONDecodeError:
                properties[key_text] = value_text

        return properties

    def _collect_relationships(self) -> List[tuple]:
        """Collect relationships from table"""
        relationships = []
        for row in range(self.ui.relationships_table.rowCount()):
            rel_type = self.ui.relationships_table.item(row, 0)
            target = self.ui.relationships_table.item(row, 1)
            direction = self.ui.relationships_table.cellWidget(row, 2)
            props = self.ui.relationships_table.item(row, 3)

            if not all([rel_type, target, direction]):
                continue

            try:
                properties = (
                    json.loads(props.text()) if props and props.text().strip() else {}
                )
                relationships.append(
                    (
                        rel_type.text().strip(),
                        target.text().strip(),
                        direction.currentText(),
                        properties,
                    )
                )
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON in relationship properties: {e}")

        return relationships

    #############################################
    # 6. Event Handlers
    #############################################

    @pyqtSlot(list)
    def _handle_node_data(self, data: List[Any]):
        """Handle node data fetched by the worker"""
        logging.debug(f"Handling node data: {data}")
        if data:
            record = data[0]  # Extract the first record
            self._populate_node_fields(record)
        else:
            self.handle_error("No data returned from query")

    def _handle_delete_success(self, _):
        """Handle successful node deletion"""
        QMessageBox.information(self.ui, "Success", "Node deleted successfully")
        self._load_default_state()

    def on_save_success(self, _):
        """Handle successful node save"""
        QMessageBox.information(self.ui, "Success", "Node saved successfully")
        self.refresh_tree_view()

    @pyqtSlot(list)
    def _handle_autocomplete_results(self, records: List[Any]):
        """Handle autocomplete results"""
        try:
            names = [record["name"] for record in records]
            self.node_name_model.setStringList(names)
        except Exception as e:
            self.handle_error(f"Error processing autocomplete results: {str(e)}")

    def _update_save_progress(self, current: int, total: int):
        """Update progress during save operation"""
        # Could be connected to a progress bar in the UI
        logging.info(f"Save progress: {current}/{total}")

    @pyqtSlot(object)
    def _populate_node_fields(self, record):
        """Populate UI fields with node data."""
        logging.debug(f"Populating node fields with record: {record}")
        try:
            # Extract data from the record
            node = record['n']
            labels = record['labels']
            relationships = record['relationships']
            properties = record['all_props']

            # Ensure node properties are accessed correctly
            node_properties = dict(node)
            node_name = node_properties.get('name', '')
            node_description = node_properties.get('description', '')
            node_tags = node_properties.get('tags', [])
            image_path = node_properties.get('image_path')

            # Update UI elements in the main thread
            self.ui.name_input.setText(node_name)
            self.ui.description_input.setPlainText(node_description)
            self.ui.labels_input.setText(', '.join(labels))
            self.ui.tags_input.setText(', '.join(node_tags))

            # Update properties table
            self.ui.properties_table.setRowCount(0)
            for key, value in properties.items():
                if key not in ['name', 'description', 'tags', 'image_path']:
                    row = self.ui.properties_table.rowCount()
                    self.ui.properties_table.insertRow(row)
                    self.ui.properties_table.setItem(row, 0, QTableWidgetItem(key))
                    self.ui.properties_table.setItem(row, 1, QTableWidgetItem(str(value)))

            # Update relationships table
            self.ui.relationships_table.setRowCount(0)
            for rel in relationships:
                rel_type = rel.get('type', '')
                target = rel.get('end', '')
                direction = rel.get('dir', '>')
                props = json.dumps(rel.get('props', {}))

                self.ui.add_relationship_row(rel_type, target, direction, props)

            # Update image if available
            self.current_image_path = image_path
            self.ui.set_image(image_path)

            logging.info("Node data populated successfully.")

        except Exception as e:
            self.handle_error(f"Error populating node fields: {str(e)}")

    @pyqtSlot(list)
    def _populate_relationship_tree(self, records: List[Any]):
        """Populate the tree view with relationships."""
        logging.debug(f"Populating relationship tree with records: {records}")
        try:
            self.tree_model.clear()
            self.tree_model.setHorizontalHeaderLabels(["Node Relationships"])

            if not records:
                return

            record = records[0]
            relationships = record['relationships']

            root_item = self.tree_model.invisibleRootItem()
            node_item = QStandardItem(f"🔵 {self.ui.name_input.text()}")

            for rel in relationships:
                direction = rel['dir']
                rel_type = rel['type']
                end_node = rel['end']
                item_text = f"{direction} [{rel_type}] 🔵 {end_node}"
                child_item = QStandardItem(item_text)
                node_item.appendRow(child_item)

            root_item.appendRow(node_item)
            self.ui.tree_view.expandAll()
            logging.info("Relationship tree populated successfully.")

        except Exception as e:
            self.handle_error(f"Error populating relationship tree: {str(e)}")

    #############################################
    # 7. Cleanup and Error Handling
    #############################################

    def cleanup(self):
        """Clean up resources"""
        # Cancel and wait for any running workers
        for worker in [
            self.current_load_worker,
            self.current_save_worker,
            self.current_relationship_worker,
            self.current_search_worker,
        ]:
            if worker is not None:
                worker.cancel()
                worker.wait()
        self.model.close()

    def handle_error(self, error_message: str):
        """Handle any errors"""
        logging.error(error_message)
        QMessageBox.critical(self.ui, "Error", error_message)

    #############################################
    # 8. Utility Methods
    #############################################

    def _parse_comma_separated(self, text: str) -> List[str]:
        """Parse comma-separated input"""
        return [item.strip() for item in text.split(",") if item.strip()]

    def validate_node_name(self, name: str) -> bool:
        """Validate node name"""
        if not name:
            QMessageBox.warning(self.ui, "Warning", "Node name cannot be empty.")
            return False

        if len(name) > self.config.LIMITS_MAX_NODE_NAME_LENGTH:
            QMessageBox.warning(
                self.ui,
                "Warning",
                f"Node name cannot exceed {self.config.LIMITS_MAX_NODE_NAME_LENGTH} characters.",
            )
            return False

        return True

    def change_image(self):
        """Handle changing the image"""
        try:
            file_name, _ = QFileDialog.getOpenFileName(
                self.ui,
                "Select Image",
                "",
                "Image Files (*.png *.jpg *.bmp)",
            )
            if file_name:
                # Process image in the UI thread since it's UI-related
                self.current_image_path = file_name
                self.ui.set_image(file_name)
        except Exception as e:
            self.handle_error(f"Error changing image: {str(e)}")

    def delete_image(self):
        """Handle deleting the image"""
        self.current_image_path = None
        self.ui.set_image(None)

@dataclass
class AppComponents:
    """Container for main application components"""

    ui: "WorldBuildingUI"
    model: "Neo4jModel"
    controller: "WorldBuildingController"
    config: "Config"


class WorldBuildingApp(QMainWindow):
    """Main application class with improved initialization and error handling"""

    def __init__(self):
        super().__init__()
        self.components: Optional[AppComponents] = None
        self.setObjectName("WorldBuildingApp")
        self.initialize_application()

    def initialize_application(self) -> None:
        """Initialize all application components with comprehensive error handling"""
        try:
            # 1. Load Configuration
            config = self._load_configuration()

            # 2. Setup Logging
            self._setup_logging(config)

            # 3. Initialize Database Model
            model = self._initialize_database(config)

            # 4. Setup UI
            ui = self._setup_ui()

            # 5. Initialize Controller
            controller = self._initialize_controller(ui, model, config)

            # Store components for access
            self.components = AppComponents(
                ui=ui, model=model, controller=controller, config=config
            )

            # 6. Configure Window
            self._configure_main_window()

            # 7. Show Window
            self.show()

            logging.info("Application initialized successfully")

        except Exception as e:
            self._handle_initialization_error(e)

    def _load_configuration(self) -> "Config":
        """Load application configuration with error handling"""
        try:
            config = Config("src/config.json")
            logging.info("Configuration loaded successfully")
            return config
        except FileNotFoundError:
            raise RuntimeError("Configuration file 'config.json' not found")
        except json.JSONDecodeError:
            raise RuntimeError("Invalid JSON in configuration file")
        except Exception as e:
            raise RuntimeError(f"Error loading configuration: {str(e)}")

    def _setup_logging(self, config: "Config") -> None:
        """Configure logging with rotation and formatting"""
        try:
            log_file = config.LOGGING_FILE
            log_level = getattr(logging, config.LOGGING_LEVEL.upper())

            # Create a rotating file handler
            rotating_handler = RotatingFileHandler(
                log_file, maxBytes=1024 * 1024, backupCount=5  # 1MB per file, keep 5 backups
            )

            # Set up logging configuration
            logging.basicConfig(
                level=log_level,
                format="%(asctime)s - %(levelname)s - %(message)s",
                handlers=[
                    rotating_handler,
                    logging.StreamHandler(),
                ],
            )
            logging.info("Logging system initialized")
        except Exception as e:
            raise RuntimeError(f"Failed to setup logging: {str(e)}")

    def _initialize_database(self, config: "Config") -> "Neo4jModel":
        """Initialize database connection with retry logic"""
        max_retries = 3
        retry_delay = 2  # seconds

        for attempt in range(max_retries):
            try:
                model = Neo4jModel(
                    config.NEO4J_URI, config.NEO4J_USERNAME, config.NEO4J_PASSWORD
                )
                logging.info("Database connection established")
                return model
            except Exception as e:
                if attempt < max_retries - 1:
                    logging.warning(
                        f"Database connection attempt {attempt + 1} failed: {e}"
                    )
                    time.sleep(retry_delay)
                else:
                    raise RuntimeError(
                        f"Failed to connect to database after {max_retries} attempts: {str(e)}"
                    )

    def _setup_ui(self) -> "WorldBuildingUI":
        """Initialize user interface with error handling"""
        try:
            ui = WorldBuildingUI()
            logging.info("UI initialized successfully")
            return ui
        except Exception as e:
            raise RuntimeError(f"Failed to initialize UI: {str(e)}")

    def _initialize_controller(
        self, ui: "WorldBuildingUI", model: "Neo4jModel", config: "Config"
    ) -> "WorldBuildingController":
        """Initialize application controller with error handling"""
        try:
            controller = WorldBuildingController(ui, model, config)
            logging.info("Controller initialized successfully")
            return controller
        except Exception as e:
            raise RuntimeError(f"Failed to initialize controller: {str(e)}")

    def _configure_main_window(self) -> None:
        """Configure main window properties with error handling"""
        try:
            self.setObjectName("WorldBuildingApp")
            self.setCentralWidget(self.components.ui)

            # Set window title with version
            self.setWindowTitle(f"NeoRealmBuilder {self.components.config.VERSION}")

            # Set window size
            self.resize(
                self.components.config.UI_WINDOW_WIDTH,
                self.components.config.UI_WINDOW_HEIGHT,
            )
            self.setMinimumSize(
                self.components.config.UI_WINDOW_WIDTH,
                self.components.config.UI_WINDOW_HEIGHT,
            )

            logging.info(
                f"Window configured with size "
                f"{self.components.config.UI_WINDOW_WIDTH}x"
                f"{self.components.config.UI_WINDOW_HEIGHT}"
            )
        except Exception as e:
            raise RuntimeError(f"Failed to configure main window: {str(e)}")

    def _handle_initialization_error(self, error: Exception) -> None:
        """Handle initialization errors with cleanup"""
        error_message = f"Failed to initialize the application:\n{str(error)}"
        logging.critical(error_message, exc_info=True)

        QMessageBox.critical(self, "Initialization Error", error_message)

        # Cleanup any partially initialized resources
        self._cleanup_resources()

        sys.exit(1)

    def _cleanup_resources(self) -> None:
        """Clean up application resources"""
        if self.components:
            if self.components.controller:
                try:
                    self.components.controller.cleanup()
                except Exception as e:
                    logging.error(f"Error during controller cleanup: {e}")

            if self.components.model:
                try:
                    self.components.model.close()
                except Exception as e:
                    logging.error(f"Error during model cleanup: {e}")

    def closeEvent(self, event) -> None:
        """Handle application shutdown with proper cleanup"""
        logging.info("Application shutdown initiated")

        try:
            # Clean up controller resources
            if self.components and self.components.controller:
                self.components.controller.cleanup()
                logging.info("Controller resources cleaned up")

            # Clean up model resources
            if self.components and self.components.model:
                self.components.model.close()
                logging.info("Model resources cleaned up")

            event.accept()
            logging.info("Application shutdown completed successfully")

        except Exception as e:
            logging.error(f"Error during application shutdown: {e}")
            event.accept()  # Still close the application


if __name__ == "__main__":
    try:
        app = QApplication(sys.argv)
        ex = WorldBuildingApp()
        sys.exit(app.exec())
    except Exception as e:
        logging.critical("Unhandled exception in main loop", exc_info=True)
        sys.exit(1)
