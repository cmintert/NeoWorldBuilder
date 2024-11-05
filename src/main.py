# Imports
import faulthandler
import json
import logging
import os
import sys
import traceback
from dataclasses import dataclass
from datetime import time, datetime
from logging.handlers import RotatingFileHandler
from typing import Optional, Dict, Any, List

from PyQt6.QtCore import (
    QThread,
    pyqtSignal,
    QTimer,
    QStringListModel,
    Qt,
    QObject,
    pyqtSlot,
)
from PyQt6.QtGui import (
    QStandardItemModel,
    QPalette,
    QBrush,
    QPixmap,
    QStandardItem,
    QIcon,
    QAction,
)
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
    QSpinBox,
    QMenuBar,
    QCheckBox,
    QAbstractItemView,
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
    QMessageBox.critical(
        None, "Unhandled Exception", f"An unhandled exception occurred:\n{value}"
    )


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
        """
        Initialize the worker with Neo4j connection parameters.

        Args:
            uri (str): The URI of the Neo4j database.
            auth (tuple): A tuple containing the username and password for authentication.
        """
        super().__init__()
        self._uri = uri
        self._auth = auth
        self._driver = None
        self._is_cancelled = False

    def connect(self):
        """
        Create Neo4j driver connection.
        """
        if not self._driver:
            self._driver = GraphDatabase.driver(self._uri, auth=self._auth)

    def cleanup(self):
        """
        Clean up resources.
        """
        if self._driver:
            self._driver.close()
            self._driver = None

    def cancel(self):
        """
        Cancel current operation.
        """
        self._is_cancelled = True
        self.quit()  # Tell thread to quit
        self.wait()

    def run(self):
        """
        Base run implementation.
        """
        try:
            self.connect()
            self.execute_operation()
        except Exception as e:
            self.error_occurred.emit(str(e))
        finally:
            self.cleanup()

    def execute_operation(self):
        """
        Override in subclasses to execute specific operations.
        """
        raise NotImplementedError


class QueryWorker(BaseNeo4jWorker):
    """Worker for read operations"""

    query_finished = pyqtSignal(list)

    def __init__(self, uri, auth, query, params=None):
        """
        Initialize the worker with query parameters.

        Args:
            uri (str): The URI of the Neo4j database.
            auth (tuple): A tuple containing the username and password for authentication.
            query (str): The Cypher query to execute.
            params (dict, optional): Parameters for the query. Defaults to None.
        """
        super().__init__(uri, auth)
        self.query = query
        self.params = params or {}

    def execute_operation(self):
        """
        Execute the read operation.
        """
        try:
            with self._driver.session() as session:
                result = list(session.run(self.query, self.params))
                if not self._is_cancelled:
                    self.query_finished.emit(result)
        except Exception as e:
            error_message = "".join(
                traceback.format_exception(type(e), e, e.__traceback__)
            )
            self.error_occurred.emit(error_message)


class WriteWorker(BaseNeo4jWorker):
    """Worker for write operations"""

    write_finished = pyqtSignal(bool)

    def __init__(self, uri, auth, func, *args):
        """
        Initialize the worker with write function and arguments.

        Args:
            uri (str): The URI of the Neo4j database.
            auth (tuple): A tuple containing the username and password for authentication.
            func (callable): The function to execute in the write transaction.
            *args: Arguments for the function.
        """
        super().__init__(uri, auth)
        self.func = func
        self.args = args

    def execute_operation(self):
        """
        Execute the write operation.
        """
        with self._driver.session() as session:
            session.execute_write(self.func, *self.args)
            if not self._is_cancelled:
                self.write_finished.emit(True)

    @staticmethod
    def _run_transaction(tx, query, params):
        """
        Run a transaction with the given query and parameters.

        Args:
            tx: The transaction object.
            query (str): The Cypher query to execute.
            params (dict): Parameters for the query.

        Returns:
            The result of the query.
        """
        return tx.run(query, params)


class DeleteWorker(BaseNeo4jWorker):
    """Worker for delete operations"""

    delete_finished = pyqtSignal(bool)

    def __init__(self, uri, auth, func, *args):
        """
        Initialize the worker with delete function and arguments.

        Args:
            uri (str): The URI of the Neo4j database.
            auth (tuple): A tuple containing the username and password for authentication.
            func (callable): The function to execute in the delete transaction.
            *args: Arguments for the function.
        """
        super().__init__(uri, auth)
        self.func = func
        self.args = args

    def execute_operation(self):
        """
        Execute the delete operation.
        """
        with self._driver.session() as session:
            session.execute_write(self.func, *self.args)
            if not self._is_cancelled:
                self.delete_finished.emit(True)

    @staticmethod
    def _run_transaction(tx, query, params):
        """
        Run a transaction with the given query and parameters.

        Args:
            tx: The transaction object.
            query (str): The Cypher query to execute.
            params (dict): Parameters for the query.

        Returns:
            The result of the query.
        """
        return tx.run(query, params)


class BatchWorker(BaseNeo4jWorker):
    """Worker for batch operations"""

    batch_progress = pyqtSignal(int, int)  # current, total
    batch_finished = pyqtSignal(list)

    def __init__(self, driver_config, operations):
        """
        Initialize the worker with batch operations.

        Args:
            driver_config (dict): Configuration for the Neo4j driver.
            operations (list): List of operations to execute.
        """
        super().__init__(driver_config)
        self.operations = operations

    def execute_operation(self):
        """
        Execute the batch operations.
        """
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
        """
        Initialize the manager with configuration.

        Args:
            config (dict): Configuration for the Neo4j driver.
        """
        self.config = config
        self.active_workers = set()

    def create_worker(self, worker_class, *args, **kwargs):
        """
        Create and set up a new worker.

        Args:
            worker_class (type): The class of the worker to create.
            *args: Arguments for the worker.
            **kwargs: Keyword arguments for the worker.

        Returns:
            The created worker.
        """
        worker = worker_class(self.config, *args, **kwargs)
        worker.finished.connect(lambda: self._cleanup_worker(worker))
        self.active_workers.add(worker)
        return worker

    def _cleanup_worker(self, worker):
        """
        Clean up finished worker.

        Args:
            worker: The worker to clean up.
        """
        if worker in self.active_workers:
            self.active_workers.remove(worker)

    def cancel_all(self):
        """
        Cancel all active workers.
        """
        for worker in self.active_workers:
            worker.cancel()
            worker.wait()
        self.active_workers.clear()


class Neo4jModel:
    #############################################
    # 1. Connection Management
    #############################################

    def __init__(self, uri, username, password):
        """
        Initialize Neo4j connection parameters and establish connection.

        Args:
            uri (str): The URI of the Neo4j database.
            username (str): The username for authentication.
            password (str): The password for authentication.
        """
        self._uri = uri
        self._auth = (username, password)
        self._driver = None
        self.connect()
        logging.info("Neo4jModel initialized and connected to the database.")

    def connect(self):
        """
        Establish connection to Neo4j.
        """
        if not self._driver:
            self._driver = GraphDatabase.driver(self._uri, auth=self._auth)

    def ensure_connection(self):
        """
        Ensure we have a valid connection, reconnect if necessary.
        """
        try:
            if self._driver:
                self._driver.verify_connectivity()
            else:
                self.connect()
        except Exception as e:
            logging.warning(f"Connection verification failed: {e}")
            self.connect()

    def get_session(self):
        """
        Get a database session, ensuring connection is valid.

        Returns:
            The database session.
        """
        self.ensure_connection()
        return self._driver.session()

    def close(self):
        """
        Safely close the driver.
        """
        if self._driver:
            try:
                self._driver.close()
            finally:
                self._driver = None
        logging.info("Neo4jModel connection closed.")

    #############################################
    # 2. Node CRUD Operations
    #############################################

    def validate_node_data(self, node_data):
        """
        Validate node data before performing any operations.

        Args:
            node_data (dict): Node data including properties and relationships.

        Raises:
            ValueError: If validation fails.
        """
        # Check for required fields
        if "name" not in node_data or not node_data["name"].strip():
            raise ValueError("Node must have a non-empty name.")

        if "labels" not in node_data or not node_data["labels"]:
            raise ValueError("Node must have at least one label.")

        # Check for proper labels
        for label in node_data["labels"]:
            if not label.strip():
                raise ValueError("Node labels must be non-empty.")

        return True

    def load_node(self, name, callback):
        """
        Load a node and its relationships by name using a worker.

        Args:
            name (str): Name of the node to load.
            callback (function): Function to call with the result.

        Returns:
            QueryWorker: A worker that will execute the query.
        """
        query = """
            MATCH (n {name: $name})
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
            node_data (dict): Node data including properties and relationships.
            callback (function): Function to call when done.

        Returns:
            WriteWorker: A worker that will execute the write operation.
        """
        self.validate_node_data(node_data)
        worker = WriteWorker(
            self._uri, self._auth, self._save_node_transaction, node_data
        )
        worker.write_finished.connect(callback)
        return worker

    @staticmethod
    def _save_node_transaction(tx, node_data):
        """
        Private transaction handler for save_node.
        Preserves and updates system properties (_created, _modified, _author) while replacing all others.
        """
        # Extract data from node_data
        name = node_data["name"]
        description = node_data["description"]
        tags = node_data["tags"]
        additional_properties = node_data["additional_properties"]
        relationships = node_data["relationships"]
        labels = node_data["labels"]

        # 1. Get existing system properties
        # Updated to specifically check for _created timestamp
        query_get_system = """
        MATCH (n {name: $name})
        RETURN n._created as created
        """
        result = tx.run(query_get_system, name=name)
        record = result.single()

        # 2. Prepare system properties
        system_props = {
            "_author": "System",  # Always set author
            "_modified": datetime.now().isoformat(),  # Always update modified time
        }

        # Only set _created if it doesn't exist
        if not record or record["created"] is None:
            system_props["_created"] = datetime.now().isoformat()
        else:
            system_props["_created"] = record["created"]  # Preserve existing creation time

        # 3. Reset node with core properties and system properties
        base_props = {
            "name": name,
            "description": description,
            "tags": tags,
            **system_props,  # Include system properties in base set
        }

        query_reset = """
        MATCH (n {name: $name})
        SET n = $base_props
        """
        tx.run(query_reset, name=name, base_props=base_props)

        # 4. Handle labels
        result = tx.run("MATCH (n {name: $name}) RETURN labels(n) AS labels", name=name)
        record = result.single()
        existing_labels = record["labels"] if record else []
        existing_labels = [label for label in existing_labels if label != "Node"]

        # Determine labels to add and remove
        input_labels_set = set(labels) - {"Node"}
        existing_labels_set = set(existing_labels)
        labels_to_add = input_labels_set - existing_labels_set
        labels_to_remove = existing_labels_set - input_labels_set

        # Add new labels
        if labels_to_add:
            labels_str = ":".join([f"`{label}`" for label in labels_to_add])
            query_add = f"MATCH (n {{name: $name}}) SET n:{labels_str}"
            tx.run(query_add, name=name)

        # Remove old labels
        if labels_to_remove:
            labels_str = ", ".join([f"n:`{label}`" for label in labels_to_remove])
            query_remove = f"MATCH (n {{name: $name}}) REMOVE {labels_str}"
            tx.run(query_remove, name=name)

        # 5. Add non-system additional properties (if any)
        filtered_additional_props = {
            k: v for k, v in additional_properties.items() if not k.startswith("_")
        }
        if filtered_additional_props:
            query_props = "MATCH (n {name: $name}) SET n += $additional_properties"
            tx.run(
                query_props, name=name, additional_properties=filtered_additional_props
            )

        # 6. Handle relationships
        # Remove existing relationships
        query_remove_rels = "MATCH (n {name: $name})-[r]-() DELETE r"
        tx.run(query_remove_rels, name=name)

        # Create/update relationships
        for rel in relationships:
            rel_type, rel_name, direction, properties = rel
            if direction == ">":
                query_rel = (
                    f"MATCH (n {{name: $name}}), (m {{name: $rel_name}}) "
                    f"MERGE (n)-[r:`{rel_type}`]->(m) "
                    "SET r = $properties"
                )
            else:
                query_rel = (
                    f"MATCH (n {{name: $name}}), (m {{name: $rel_name}}) "
                    f"MERGE (n)<-[r:`{rel_type}`]-(m) "
                    "SET r = $properties"
                )
            tx.run(query_rel, name=name, rel_name=rel_name, properties=properties)

    def delete_node(self, name, callback):
        """
        Delete a node and all its relationships using a worker.

        Args:
            name (str): Name of the node to delete.
            callback (function): Function to call when done.

        Returns:
            DeleteWorker: A worker that will execute the delete operation.
        """
        worker = DeleteWorker(
            self._uri, self._auth, self._delete_node_transaction, name
        )
        worker.delete_finished.connect(callback)
        return worker

    @staticmethod
    def _delete_node_transaction(tx, name):
        """
        Private transaction handler for delete_node.

        Args:
            tx: The transaction object.
            name (str): Name of the node to delete.
        """
        query = "MATCH (n {name: $name}) DETACH DELETE n"
        tx.run(query, name=name)

    #############################################
    # 3. Node Query Operations
    #############################################

    def get_node_relationships(self, node_name: str, depth: int, callback: callable):
        """
        Get the relationships of a node by name up to a specified depth using a worker.

        Args:
            node_name (str): Name of the node.
            depth (int): The depth of relationships to retrieve.
            callback (function): Function to call with the result.

        Returns:
            QueryWorker: A worker that will execute the query.
        """
        depth += 1  # Adjust depth for query
        query = f"""
            MATCH path = (n {{name: $name}})-[*1..{depth}]-()
            WHERE ALL(r IN relationships(path) WHERE startNode(r) IS NOT NULL AND endNode(r) IS NOT NULL)
              AND ALL(node IN nodes(path) WHERE node IS NOT NULL)
            WITH path, length(path) AS path_length
            UNWIND range(1, path_length - 1) AS idx
            WITH
                nodes(path)[idx] AS current_node,
                relationships(path)[idx - 1] AS current_rel,
                nodes(path)[idx - 1] AS parent_node,
                idx AS depth
            RETURN DISTINCT
                current_node.name AS node_name,
                labels(current_node) AS labels,
                parent_node.name AS parent_name,
                type(current_rel) AS rel_type,
                CASE
                    WHEN startNode(current_rel) = parent_node THEN '>' ELSE '<' END AS direction,
                depth
            ORDER BY depth ASC
        """
        params = {"name": node_name}
        worker = QueryWorker(self._uri, self._auth, query, params)
        worker.query_finished.connect(callback)
        return worker

    def get_node_hierarchy(self):
        """
        Get the hierarchy of nodes grouped by their primary label.

        Returns:
            dict: Category to node names mapping.
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
            prefix (str): The search prefix.
            limit (int): Maximum number of results to return.
            callback (function): Function to call with the result.

        Returns:
            QueryWorker: A worker that will execute the query.
        """
        query = (
            "MATCH (n) WHERE toLower(n.name) CONTAINS toLower($prefix) "
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

    def __init__(self, controller):
        """
        Initialize the UI with the given controller.

        Args:
            controller (WorldBuildingController): The controller managing the UI.
        """
        super().__init__()
        self.controller = controller
        self.setObjectName("CentralWidget")
        self.setAttribute(
            Qt.WidgetAttribute.WA_StyledBackground, True
        )  # Important for QSS styling
        self.setAttribute(
            Qt.WidgetAttribute.WA_TranslucentBackground, True
        )  # Allow transparency
        self.init_ui()

    def init_ui(self):
        """
        Initialize the main UI layout with enhanced components.
        """
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

        # Apply styles
        self.apply_styles()

    def _create_left_panel(self):
        """
        Create improved left panel with tree view and search.

        Returns:
            QWidget: The left panel widget.
        """
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

        # Depth selector

        depth_layout = QHBoxLayout()
        depth_label = QLabel("Relationship Depth:")
        self.depth_spinbox = QSpinBox()
        self.depth_spinbox.setObjectName("depthSpinBox")
        self.depth_spinbox.setFixedWidth(70)
        self.depth_spinbox.setFixedHeight(40)
        self.depth_spinbox.setMinimum(0)
        self.depth_spinbox.setMaximum(3)
        self.depth_spinbox.setValue(1)  # Default value; can be loaded from config

        depth_layout.addWidget(depth_label)
        depth_layout.addWidget(self.depth_spinbox)
        depth_layout.addStretch()

        layout.addLayout(depth_layout)

        return panel

    def _create_right_panel(self):
        """
        Create improved right panel with proper spacing and opacity.

        Returns:
            QWidget: The right panel widget.
        """
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
        """
        Create enhanced header with loading indication.

        Returns:
            QHBoxLayout: The header layout.
        """
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
        """
        Create the basic info tab with input fields and image handling.

        Returns:
            QWidget: The basic info tab widget.
        """
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
        """
        Create the image display group.

        Returns:
            QGroupBox: The image group box.
        """
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
        self.change_image_button = QPushButton("Change")
        self.change_image_button.setObjectName("changeImageButton")
        self.delete_image_button = QPushButton("Remove")
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
        """
        Create relationships tab with table.

        Returns:
            QWidget: The relationships tab widget.
        """
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Add relationship button
        self.add_rel_button = QPushButton("➕ Add Relationship")
        self.add_rel_button.setObjectName("addRelationshipButton")
        self.add_rel_button.setFixedWidth(150)
        self.add_rel_button.setMinimumHeight(30)

        # Enhanced table
        self.relationships_table = QTableWidget(0, 5)
        self.relationships_table.setObjectName("relationshipsTable")
        self.relationships_table.setAlternatingRowColors(True)
        self.relationships_table.verticalHeader().setVisible(False)

        # Set up columns
        self._setup_relationships_table_columns()

        layout.addWidget(self.add_rel_button)
        layout.addWidget(self.relationships_table)
        return tab

    def _create_properties_tab(self):
        """
        Create properties tab with table.

        Returns:
            QWidget: The properties tab widget.
        """
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Add property button
        self.add_prop_button = QPushButton("➕ Add Property")
        self.add_prop_button.setObjectName("addPropertyButton")
        self.add_prop_button.setFixedWidth(150)
        self.add_prop_button.setMinimumHeight(30)

        # Enhanced table
        self.properties_table = QTableWidget(0, 3)
        self.properties_table.setObjectName("propertiesTable")
        self.properties_table.setAlternatingRowColors(True)
        self.properties_table.verticalHeader().setVisible(False)

        # Set up columns
        self._setup_properties_table_columns()

        layout.addWidget(self.add_prop_button)
        layout.addWidget(self.properties_table)
        return tab

    def _show_tree_context_menu(self, position):
        """
        Show context menu for tree items.

        Args:
            position (QPoint): The position where the context menu should appear.
        """
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

    def create_delete_button(self, table, row):
        """
        Create a centered delete button for table rows.

        Args:
            table (QTableWidget): The table to which the button will be added.
            row (int): The row number where the button will be placed.

        Returns:
            QWidget: The container widget with the delete button.
        """
        # Create container widget for centering
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(4, 0, 4, 0)  # Small horizontal margins for spacing
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Create the delete button
        button = QPushButton("-")
        button.setObjectName("rowDeleteButton")
        button.setFixedWidth(20)
        button.setFixedHeight(20)
        button.clicked.connect(lambda: table.removeRow(row))

        # Add button to container
        layout.addWidget(button)

        return container

    def _setup_relationships_table_columns(self):
        """
        Set up relationships table columns with proper sizing.
        """
        self.relationships_table.setColumnCount(5)
        self.relationships_table.setHorizontalHeaderLabels(
            ["Type", "Related Node", "Direction", "Properties", ""]
        )

        # Set relationships table column behaviors
        header = self.relationships_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)  # Type
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)  # Related Node
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)  # Direction
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)  # Properties
        header.setSectionResizeMode(
            4, QHeaderView.ResizeMode.Fixed
        )  # Delete button column

        # Set fixed widths for specific columns
        self.relationships_table.setColumnWidth(2, 80)  # Direction column
        self.relationships_table.setColumnWidth(4, 38)  # Delete button column

    def _setup_properties_table_columns(self):
        """
        Set up properties table columns with proper sizing.
        """
        self.properties_table.setColumnCount(3)
        self.properties_table.setHorizontalHeaderLabels(["Key", "Value", ""])

        # Set properties table column behaviors
        header = self.properties_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)  # Key
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)  # Value
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)  # Delete button

        # Set fixed width for delete button column
        self.properties_table.setColumnWidth(2, 38)  # Delete button column

    #############################################
    # Progress and Status Methods
    #############################################

    def show_progress(self, visible: bool = True):
        """
        Show or hide progress bar.

        Args:
            visible (bool): Whether to show the progress bar. Defaults to True.
        """
        self.progress_bar.setVisible(visible)
        if visible:
            self.progress_bar.setValue(0)

    def set_progress(self, value: int, maximum: int = 100):
        """
        Update progress bar.

        Args:
            value (int): The current progress value.
            maximum (int): The maximum progress value. Defaults to 100.
        """
        self.progress_bar.setMaximum(maximum)
        self.progress_bar.setValue(value)

    def set_status(self, message: str):
        """
        Update status message.

        Args:
            message (str): The status message to display.
        """
        self.status_label.setText(message)

    def show_loading(self, is_loading: bool):
        """
        Show loading state.

        Args:
            is_loading (bool): Whether the UI is in a loading state.
        """
        self.save_button.setEnabled(not is_loading)
        self.delete_button.setEnabled(not is_loading)
        self.cancel_button.setVisible(is_loading)
        self.name_input.setReadOnly(is_loading)

    #############################################
    # UI Update Methods
    #############################################

    def clear_all_fields(self):
        """
        Clear all input fields except the name_input.
        """
        self.description_input.clear()
        self.labels_input.clear()
        self.tags_input.clear()
        self.properties_table.setRowCount(0)
        self.relationships_table.setRowCount(0)
        self.image_label.clear()

    def set_image(self, image_path: Optional[str]):
        """
        Set image with proper scaling and error handling.

        Args:
            image_path (Optional[str]): The path to the image file.
        """
        if not image_path:
            self.image_label.clear()
            return

        try:
            pixmap = QPixmap(image_path)
            if not pixmap.isNull():
                scaled_pixmap = pixmap.scaled(
                    self.image_label.size(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
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
        """
        Add relationship row with improved validation.

        Args:
            rel_type (str): The type of the relationship.
            target (str): The target node of the relationship.
            direction (str): The direction of the relationship. Defaults to ">".
            properties (str): The properties of the relationship in JSON format.
        """
        row = self.relationships_table.rowCount()
        self.relationships_table.insertRow(row)

        # Type with validation
        type_item = QTableWidgetItem(rel_type)
        self.relationships_table.setItem(row, 0, type_item)

        # Target with completion
        target_item = QTableWidgetItem(target)
        self.relationships_table.setItem(row, 1, target_item)
        self.controller._add_target_completer_to_row(row)

        # Direction ComboBox
        direction_combo = QComboBox()
        direction_combo.addItems([">", "<"])
        direction_combo.setCurrentText(direction)
        self.relationships_table.setCellWidget(row, 2, direction_combo)

        # Properties with validation
        props_item = QTableWidgetItem(properties)
        self.relationships_table.setItem(row, 3, props_item)

        # Add a centered delete button
        delete_button = self.create_delete_button(self.relationships_table, row)
        self.relationships_table.setCellWidget(row, 4, delete_button)

    def add_property_row(self):
        """
        Add property row with centered delete button.
        """
        row = self.properties_table.rowCount()
        self.properties_table.insertRow(row)

        # Add a centered delete button
        delete_button = self.create_delete_button(self.properties_table, row)
        self.properties_table.setCellWidget(row, 2, delete_button)

    def apply_styles(self):
        """
        Apply styles to the UI components.
        """
        logging.debug("apply_styles method called")
        try:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            stylesheet_path = os.path.join(current_dir, "style_default.qss")

            # Log the paths for debugging
            logging.info(f"Stylesheet path: {stylesheet_path}")

            with open(stylesheet_path, "r") as f:
                stylesheet = f.read()

            self.setStyleSheet(stylesheet)
            logging.info(f"Stylesheet applied successfully from {stylesheet_path}")

        except Exception as e:
            error_message = f"Failed to load stylesheet: {e}"
            logging.error(error_message)
            QMessageBox.warning(self, "Stylesheet Error", error_message)
        logging.debug("Completed apply_styles method")


class WorldBuildingController(QObject):
    """
    Controller class managing interaction between UI and Neo4j model using QThread workers
    """

    NODE_RELATIONSHIPS_HEADER = "Node Relationships"

    def __init__(self, ui: "WorldBuildingUI", model: "Neo4jModel", config: "Config"):
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
        self.current_image_path: Optional[str] = None
        self.original_node_data: Optional[Dict[str, Any]] = None
        self.ui.controller = self

        # Initialize UI state
        self._initialize_tree_view()
        self._initialize_completer()
        self._initialize_target_completer()
        self._setup_debounce_timer()
        self._connect_signals()
        self._load_default_state()

        # Initialize worker manager
        self.current_load_worker = None
        self.current_save_worker = None
        self.current_relationship_worker = None
        self.current_search_worker = None
        self.current_delete_worker = None

    #############################################
    # 1. Initialization Methods
    #############################################

    def _initialize_tree_view(self):
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
            self.config.NEO4J_MATCH_NODE_LIMIT,
            self._handle_target_autocomplete_results,
        )
        self.current_search_worker.error_occurred.connect(self.handle_error)
        self.current_search_worker.start()

    @pyqtSlot(list)
    def _handle_target_autocomplete_results(self, records: List[Any]):
        """
        Handle target autocomplete results.

        Args:
            records (List[Any]): The list of matching records.
        """
        try:
            names = [record["name"] for record in records]
            self.target_name_model.setStringList(names)
        except Exception as e:
            self.handle_error(f"Error processing target autocomplete results: {str(e)}")

    def _setup_debounce_timer(self):
        """
        Setup debounce timer for search.
        """
        self.name_input_timer = QTimer()
        self.name_input_timer.setSingleShot(True)
        self.name_input_timer.timeout.connect(self._fetch_matching_nodes)
        self.name_input_timer.setInterval(
            self.config.TIMING_NAME_INPUT_DEBOUNCE_TIME_MS
        )

    def _connect_signals(self):
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
        self.ui.add_prop_button.clicked.connect(self.ui.add_property_row)
        self.ui.add_rel_button.clicked.connect(self.ui.add_relationship_row)

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

    def _load_default_state(self):
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

    def load_node_data(self):
        """
        Load node data using worker thread.
        """
        name = self.ui.name_input.text().strip()
        if not name:
            return

        # Clear all fields to populate them again
        self.ui.clear_all_fields()

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
        """
        Save node data using worker thread.
        """
        name = self.ui.name_input.text().strip()
        if not self.validate_node_name(name):
            return

        node_data = self._collect_node_data()
        if not node_data:
            return

        # Cancel any existing save operation
        if hasattr(self, "current_save_worker") and self.current_save_worker:
            self.current_save_worker.cancel()

        # Start new save operation
        self.current_save_worker = self.model.save_node(node_data, self.on_save_success)
        self.current_save_worker.error_occurred.connect(self.handle_error)
        self.current_save_worker.start()

    def delete_node(self):
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
            # Cancel any existing delete operation
            if self.current_delete_worker:
                self.current_delete_worker.cancel()
                self.current_delete_worker.wait()

            # Start new delete operation
            self.current_delete_worker = self.model.delete_node(
                name, self._handle_delete_success
            )
            self.current_delete_worker.error_occurred.connect(self.handle_error)
            self.current_delete_worker.start()

    #############################################
    # 3. Tree and Relationship Management
    #############################################

    def on_depth_changed(self, value: int):
        """
        Handle changes in relationship depth.

        Args:
            value (int): The new depth value.
        """
        node_name = self.ui.name_input.text().strip()
        if node_name:
            self.update_relationship_tree(node_name)

    def update_relationship_tree(self, node_name: str):
        """
        Update tree view with node relationships.

        Args:
            node_name (str): The name of the node.
        """
        if not node_name:
            self.tree_model.clear()
            self.tree_model.setHorizontalHeaderLabels([self.NODE_RELATIONSHIPS_HEADER])
            return

        depth = self.ui.depth_spinbox.value()  # Get depth from UI

        # Cancel any existing relationship worker
        if self.current_relationship_worker:
            self.current_relationship_worker.cancel()
            self.current_relationship_worker.wait()

        self.current_relationship_worker = self.model.get_node_relationships(
            node_name, depth, self._populate_relationship_tree
        )
        self.current_relationship_worker.error_occurred.connect(self.handle_error)
        self.current_relationship_worker.start()

    def refresh_tree_view(self):
        """
        Refresh the entire tree view.
        """
        name = self.ui.name_input.text().strip()
        if name:
            self.update_relationship_tree(name)

    def on_tree_selection_changed(self, selected, deselected):
        """
        Handle tree view selection changes.

        Args:
            selected: The selected indexes.
            deselected: The deselected indexes.
        """
        indexes = selected.indexes()
        if indexes:
            selected_item = self.tree_model.itemFromIndex(indexes[0])
            if selected_item:
                node_name = selected_item.data(Qt.ItemDataRole.UserRole)
                if node_name and node_name != self.ui.name_input.text():
                    self.ui.name_input.setText(node_name)
                    self.load_node_data()

    #############################################
    # 4. Auto-completion and Search
    #############################################

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
            text, self.config.NEO4J_MATCH_NODE_LIMIT, self._handle_autocomplete_results
        )
        self.current_search_worker.error_occurred.connect(self.handle_error)
        self.current_search_worker.start()

    def on_completer_activated(self, text: str):
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
        Collect all node data from UI.

        Returns:
            Optional[Dict[str, Any]]: The collected node data.
        """
        try:
            node_data = {
                "name": self.ui.name_input.text().strip(),
                "description": self.ui.description_input.toPlainText().strip(),
                "tags": self._parse_comma_separated(self.ui.tags_input.text()),
                "labels": [
                    label.strip().upper().replace(" ", "_")
                    for label in self._parse_comma_separated(
                        self.ui.labels_input.text()
                    )
                ],
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
        """
        Collect properties from table.

        Returns:
            Dict[str, Any]: The collected properties.
        """
        properties = {}
        for row in range(self.ui.properties_table.rowCount()):
            key = self.ui.properties_table.item(row, 0)
            value = self.ui.properties_table.item(row, 1)

            if not key or not key.text().strip():
                continue

            key_text = key.text().strip()

            if key_text.lower() in self.config.RESERVED_PROPERTY_KEYS:
                raise ValueError(f"Property key '{key_text}' is reserved")

            if key_text.startswith("_"):
                raise ValueError(
                    f"Property key '{key_text}' cannot start with an underscore"
                )

            try:
                value_text = value.text().strip() if value else ""
                properties[key_text] = (
                    json.loads(value_text) if value_text else value_text
                )
            except json.JSONDecodeError:
                properties[key_text] = value_text

        return properties

    def _collect_relationships(self) -> List[tuple]:
        """
        Collect relationships from table.

        Returns:
            List[tuple]: The collected relationships.
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
                raise ValueError(f"Invalid JSON in relationship properties: {e}")

        logging.debug(f"Collected the following Relationships: {relationships}")
        return relationships

    #############################################
    # 6. Event Handlers
    #############################################

    @pyqtSlot(list)
    def _handle_node_data(self, data: List[Any]):
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
        except Exception as e:
            self.handle_error(f"Error populating node fields: {str(e)}")

    def is_node_changed(self) -> bool:
        """
        Check if the node data has changed.

        Returns:
            bool: Whether the node data has changed.
        """
        current_data = self._collect_node_data()
        return current_data != self.original_node_data

    def update_unsaved_changes_indicator(self):
        if self.is_node_changed():
            self.ui.save_button.setStyleSheet("background-color: #83A00E;")
        else:
            self.ui.save_button.setStyleSheet("background-color: #d3d3d3;")

    def _handle_delete_success(self, _):
        """
        Handle successful node deletion.

        Args:
            _: The result of the delete operation.
        """
        QMessageBox.information(self.ui, "Success", "Node deleted successfully")
        self._load_default_state()

    def on_save_success(self, _):
        """
        Handle successful node save.

        Args:
            _: The result of the save operation.
        """
        QMessageBox.information(self.ui, "Success", "Node saved successfully")
        self.refresh_tree_view()
        self.load_node_data()

    @pyqtSlot(list)
    def _handle_autocomplete_results(self, records: List[Any]):
        """
        Handle autocomplete results.

        Args:
            records (List[Any]): The list of matching records.
        """
        try:
            names = [record["name"] for record in records]
            self.node_name_model.setStringList(names)
        except Exception as e:
            self.handle_error(f"Error processing autocomplete results: {str(e)}")

    def _update_save_progress(self, current: int, total: int):
        """
        Update progress during save operation.

        Args:
            current (int): The current progress value.
            total (int): The total progress value.
        """
        # Could be connected to a progress bar in the UI
        logging.info(f"Save progress: {current}/{total}")

    @pyqtSlot(object)
    def _populate_node_fields(self, record):
        """
        Populate UI fields with node data.

        Args:
            record: The record containing node data.
        """
        logging.debug(f"Populating node fields with record: {record}")
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
            image_path = node_properties.get("image_path")

            # Update UI elements in the main thread
            self.ui.name_input.setText(node_name)
            self.ui.description_input.setPlainText(node_description)
            self.ui.labels_input.setText(", ".join(labels))
            self.ui.tags_input.setText(", ".join(node_tags))

            # Update properties table
            self.ui.properties_table.setRowCount(0)
            for key, value in properties.items():

                if key.startswith("_"):
                    continue

                if key not in ["name", "description", "tags", "image_path"]:

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
            self.current_image_path = image_path
            self.ui.set_image(image_path)

            logging.info("Node data populated successfully.")

        except Exception as e:
            self.handle_error(f"Error populating node fields: {str(e)}")

    def process_relationship_records(self, records):
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

    def add_children(self, parent_name, parent_item, path, parent_child_map):
        """
        Add child nodes to the relationship tree with checkboxes.
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

    def handle_cycles(self, parent_item, rel_type, direction, child_name):
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
    def _populate_relationship_tree(self, records: List[Any]):
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

    def cleanup(self):
        """
        Clean up resources.
        """
        # Cancel and wait for any running workers
        for worker in [
            self.current_load_worker,
            self.current_save_worker,
            self.current_relationship_worker,
            self.current_search_worker,
            self.current_delete_worker,
        ]:
            if worker is not None:
                worker.cancel()
                worker.wait()
        self.model.close()

    def handle_error(self, error_message: str):
        """
        Handle any errors.

        Args:
            error_message (str): The error message to display.
        """
        logging.error(error_message)
        QMessageBox.critical(self.ui, "Error", error_message)

    #############################################
    # 8. Utility Methods
    #############################################

    def _parse_comma_separated(self, text: str) -> List[str]:
        """
        Parse comma-separated input.

        Args:
            text (str): The comma-separated input text.

        Returns:
            List[str]: The parsed list of strings.
        """
        return [item.strip() for item in text.split(",") if item.strip()]

    def validate_node_name(self, name: str) -> bool:
        """
        Validate node name.

        Args:
            name (str): The node name to validate.

        Returns:
            bool: True if the node name is valid, False otherwise.
        """
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
        """
        Handle changing the image.
        """
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
        """
        Handle deleting the image.
        """
        self.current_image_path = None
        self.ui.set_image(None)

    def export_as_json(self):
        """
        Export selected nodes data as JSON file.
        """
        selected_nodes = self.get_selected_nodes()
        if not selected_nodes:
            QMessageBox.warning(self.ui, "Warning", "No nodes selected for export.")
            return

        file_name, _ = QFileDialog.getSaveFileName(
            self.ui, "Export as JSON", "", "JSON Files (*.json)"
        )
        if file_name:
            try:
                all_node_data = []
                for node_name in selected_nodes:
                    node_data = self._collect_node_data_for_export(node_name)
                    if node_data:
                        all_node_data.append(node_data)

                with open(file_name, "w") as file:
                    json.dump(all_node_data, file, indent=4)
                QMessageBox.information(
                    self.ui,
                    "Success",
                    "Selected nodes data exported as JSON successfully",
                )
            except Exception as e:
                self.handle_error(
                    f"Error exporting selected nodes data as JSON: {str(e)}"
                )

    def export_as_txt(self):
        """
        Export selected nodes data as plain text file.
        """
        selected_nodes = self.get_selected_nodes()
        if not selected_nodes:
            QMessageBox.warning(self.ui, "Warning", "No nodes selected for export.")
            return

        file_name, _ = QFileDialog.getSaveFileName(
            self.ui, "Export as TXT", "", "Text Files (*.txt)"
        )
        if file_name:
            try:
                with open(file_name, "w") as file:
                    for node_name in selected_nodes:
                        node_data = self._collect_node_data_for_export(node_name)
                        if node_data:
                            file.write(f"Name: {node_data['name']}\n")
                            file.write(f"Description: {node_data['description']}\n")
                            file.write(f"Tags: {', '.join(node_data['tags'])}\n")
                            file.write(f"Labels: {', '.join(node_data['labels'])}\n")
                            file.write("Relationships:\n")
                            for rel in node_data["relationships"]:
                                file.write(
                                    f"  - Type: {rel[0]}, Target: {rel[1]}, Direction: {rel[2]}, Properties: {json.dumps(rel[3])}\n"
                                )
                            file.write("Additional Properties:\n")
                            for key, value in node_data[
                                "additional_properties"
                            ].items():
                                file.write(f"  - {key}: {value}\n")
                            file.write("\n")
                QMessageBox.information(
                    self.ui,
                    "Success",
                    "Selected nodes data exported as TXT successfully",
                )
            except Exception as e:
                self.handle_error(
                    f"Error exporting selected nodes data as TXT: {str(e)}"
                )

    def export_as_csv(self):
        """
        Export selected nodes data as CSV file.
        """
        selected_nodes = self.get_selected_nodes()
        if not selected_nodes:
            QMessageBox.warning(self.ui, "Warning", "No nodes selected for export.")
            return

        file_name, _ = QFileDialog.getSaveFileName(
            self.ui, "Export as CSV", "", "CSV Files (*.csv)"
        )
        if file_name:
            try:
                with open(file_name, "w") as file:
                    file.write(
                        "Name,Description,Tags,Labels,Relationships,Additional Properties\n"
                    )
                    for node_name in selected_nodes:
                        node_data = self._collect_node_data_for_export(node_name)
                        if node_data:
                            file.write(
                                f"{node_data['name']},{node_data['description']},{', '.join(node_data['tags'])},{', '.join(node_data['labels'])},"
                            )
                            relationships = "; ".join(
                                [
                                    f"Type: {rel[0]}, Target: {rel[1]}, Direction: {rel[2]}, Properties: {json.dumps(rel[3])}"
                                    for rel in node_data["relationships"]
                                ]
                            )
                            additional_properties = "; ".join(
                                [
                                    f"{key}: {value}"
                                    for key, value in node_data[
                                        "additional_properties"
                                    ].items()
                                ]
                            )
                            file.write(f"{relationships},{additional_properties}\n")
                QMessageBox.information(
                    self.ui,
                    "Success",
                    "Selected nodes data exported as CSV successfully",
                )
            except Exception as e:
                self.handle_error(
                    f"Error exporting selected nodes data as CSV: {str(e)}"
                )

    def export_as_pdf(self):
        """
        Export selected nodes data as PDF file.
        """
        from fpdf import FPDF

        selected_nodes = self.get_selected_nodes()
        if not selected_nodes:
            QMessageBox.warning(self.ui, "Warning", "No nodes selected for export.")
            return

        file_name, _ = QFileDialog.getSaveFileName(
            self.ui, "Export as PDF", "", "PDF Files (*.pdf)"
        )
        if file_name:
            try:
                pdf = FPDF()
                pdf.set_font("Arial", size=12)

                for node_name in selected_nodes:
                    node_data = self._collect_node_data_for_export(node_name)
                    if node_data:
                        pdf.add_page()
                        pdf.cell(200, 10, txt=f"Name: {node_data['name']}", ln=True)
                        pdf.cell(
                            200,
                            10,
                            txt=f"Description: {node_data['description']}",
                            ln=True,
                        )
                        pdf.cell(
                            200,
                            10,
                            txt=f"Tags: {', '.join(node_data['tags'])}",
                            ln=True,
                        )
                        pdf.cell(
                            200,
                            10,
                            txt=f"Labels: {', '.join(node_data['labels'])}",
                            ln=True,
                        )
                        pdf.cell(200, 10, txt="Relationships:", ln=True)
                        for rel in node_data["relationships"]:
                            pdf.cell(
                                200,
                                10,
                                txt=f"  - Type: {rel[0]}, Target: {rel[1]}, Direction: {rel[2]}, Properties: {json.dumps(rel[3])}",
                                ln=True,
                            )
                        pdf.cell(200, 10, txt="Additional Properties:", ln=True)
                        for key, value in node_data["additional_properties"].items():
                            pdf.cell(200, 10, txt=f"  - {key}: {value}", ln=True)

                pdf.output(file_name)
                QMessageBox.information(
                    self.ui,
                    "Success",
                    "Selected nodes data exported as PDF successfully",
                )
            except Exception as e:
                self.handle_error(
                    f"Error exporting selected nodes data as PDF: {str(e)}"
                )

    def get_selected_nodes(self) -> List[str]:
        """
        Get the names of checked nodes in the tree view.
        """
        selected_nodes = []
        logging.debug("Starting to gather selected nodes.")

        def traverse_tree(parent_item):
            """Recursively traverse tree to find checked items"""
            if parent_item.hasChildren():
                for row in range(parent_item.rowCount()):
                    child = parent_item.child(row)
                    if child.hasChildren():
                        # If this is a relationship item, check its children
                        for child_row in range(child.rowCount()):
                            node_item = child.child(child_row)
                            if (
                                node_item
                                and node_item.checkState() == Qt.CheckState.Checked
                                and node_item.data(Qt.ItemDataRole.UserRole)
                            ):
                                selected_nodes.append(
                                    node_item.data(Qt.ItemDataRole.UserRole)
                                )
                        traverse_tree(child)
                    else:
                        # If this is a node item directly
                        if child.checkState() == Qt.CheckState.Checked and child.data(
                            Qt.ItemDataRole.UserRole
                        ):
                            selected_nodes.append(child.data(Qt.ItemDataRole.UserRole))

        # Start traversal from root
        root_item = self.tree_model.invisibleRootItem()
        traverse_tree(root_item)

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
                "tags": self._parse_comma_separated(self.ui.tags_input.text()),
                "labels": [
                    label.strip().upper().replace(" ", "_")
                    for label in self._parse_comma_separated(
                        self.ui.labels_input.text()
                    )
                ],
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
        """
        Initialize the main application window.
        """
        super().__init__()
        self.components: Optional[AppComponents] = None
        self.setObjectName("WorldBuildingApp")
        self.initialize_application()

    def initialize_application(self) -> None:
        """
        Initialize all application components with comprehensive error handling.
        """
        try:
            # 1. Load Configuration
            config = self._load_configuration()

            # 2. Setup Logging
            self._setup_logging(config)

            # 3. Initialize Database Model
            model = self._initialize_database(config)

            # 4 Setup UI
            ui = self._setup_ui(None)

            # 5. Initialize Controller
            controller = self._initialize_controller(ui, model, config)

            ui.controller = controller

            # Store components for access
            self.components = AppComponents(
                ui=ui, model=model, controller=controller, config=config
            )

            # 6. Configure Window
            self._configure_main_window()

            # 8. Set Background Image

            self.set_background_image("src/background.png")

            # 7. Show Window
            self.show()

            logging.info("Application initialized successfully")

        except Exception as e:
            self._handle_initialization_error(e)

    def set_background_image(self, image_path: str) -> None:
        """
        Set the background image for the main window.

        Args:
            image_path (str): The path to the background image file.
        """
        try:
            palette = QPalette()
            pixmap = QPixmap(image_path)
            palette.setBrush(QPalette.ColorRole.Window, QBrush(pixmap))
            self.setPalette(palette)
            logging.info(f"Background image set from {image_path}")
        except Exception as e:
            logging.error(f"Failed to set background image: {e}")

    def _load_configuration(self) -> "Config":
        """
        Load application configuration with error handling.

        Returns:
            Config: The loaded configuration.

        Raises:
            RuntimeError: If the configuration file is not found or invalid.
        """
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
        """
        Configure logging with rotation and formatting.

        Args:
            config (Config): The configuration instance.

        Raises:
            RuntimeError: If logging setup fails.
        """
        try:
            log_file = config.LOGGING_FILE
            log_level = getattr(logging, config.LOGGING_LEVEL.upper())

            # Create a rotating file handler
            rotating_handler = RotatingFileHandler(
                log_file,
                maxBytes=1024 * 1024,
                backupCount=5,  # 1MB per file, keep 5 backups
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
        """
        Initialize database connection with retry logic.

        Args:
            config (Config): The configuration instance.

        Returns:
            Neo4jModel: The initialized Neo4j model.

        Raises:
            RuntimeError: If database connection fails after retries.
        """
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

    def _setup_ui(self, controller) -> "WorldBuildingUI":
        """
        Initialize user interface with error handling.

        Args:
            controller: The controller instance.

        Returns:
            WorldBuildingUI: The initialized UI instance.

        Raises:
            RuntimeError: If UI initialization fails.
        """
        try:
            ui = WorldBuildingUI(controller)
            logging.info("UI initialized successfully")
            return ui
        except Exception as e:
            raise RuntimeError(f"Failed to initialize UI: {str(e)}")

    def _initialize_controller(
        self, ui: "WorldBuildingUI", model: "Neo4jModel", config: "Config"
    ) -> "WorldBuildingController":
        """
        Initialize application controller with error handling.

        Args:
            ui (WorldBuildingUI): The UI instance.
            model (Neo4jModel): The Neo4j model instance.
            config (Config): The configuration instance.

        Returns:
            WorldBuildingController: The initialized controller instance.

        Raises:
            RuntimeError: If controller initialization fails.
        """
        try:
            controller = WorldBuildingController(ui, model, config)
            logging.info("Controller initialized successfully")
            return controller
        except Exception as e:
            raise RuntimeError(f"Failed to initialize controller: {str(e)}")

    def _configure_main_window(self) -> None:
        """
        Configure main window properties with error handling.

        Raises:
            RuntimeError: If main window configuration fails.
        """
        try:
            self.setObjectName("WorldBuildingApp")
            self.setCentralWidget(self.components.ui)

            # Set window title with version
            self.setWindowTitle(f"NeoRealmBuilder {self.components.config.VERSION}")

            # Ensure transparency is properly set
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
            self.components.ui.setAttribute(
                Qt.WidgetAttribute.WA_TranslucentBackground, True
            )

            # Set window size
            self.resize(
                self.components.config.UI_WINDOW_WIDTH,
                self.components.config.UI_WINDOW_HEIGHT,
            )
            self.setMinimumSize(
                self.components.config.UI_WINDOW_WIDTH,
                self.components.config.UI_WINDOW_HEIGHT,
            )

            # Add Export menu to the main menu bar
            self._add_export_menu()

            logging.info(
                f"Window configured with size "
                f"{self.components.config.UI_WINDOW_WIDTH}x"
                f"{self.components.config.UI_WINDOW_HEIGHT}"
            )
        except Exception as e:
            raise RuntimeError(f"Failed to configure main window: {str(e)}")

    def _add_export_menu(self):
        """
        Add Export menu to the main menu bar.
        """
        menu_bar = self.menuBar()
        menu_bar.setObjectName("menuBar")

        export_menu = menu_bar.addMenu("Export")

        export_json_action = QAction("Export as JSON", self)
        export_json_action.triggered.connect(self.components.controller.export_as_json)
        export_menu.addAction(export_json_action)

        export_txt_action = QAction("Export as TXT", self)
        export_txt_action.triggered.connect(self.components.controller.export_as_txt)
        export_menu.addAction(export_txt_action)

        export_csv_action = QAction("Export as CSV", self)
        export_csv_action.triggered.connect(self.components.controller.export_as_csv)
        export_menu.addAction(export_csv_action)

        export_pdf_action = QAction("Export as PDF", self)
        export_pdf_action.triggered.connect(self.components.controller.export_as_pdf)
        export_menu.addAction(export_pdf_action)

    def _handle_initialization_error(self, error: Exception) -> None:
        """
        Handle initialization errors with cleanup.

        Args:
            error (Exception): The initialization error.
        """
        error_message = f"Failed to initialize the application:\n{str(error)}"
        logging.critical(error_message, exc_info=True)

        QMessageBox.critical(self, "Initialization Error", error_message)

        # Cleanup any partially initialized resources
        self._cleanup_resources()

        sys.exit(1)

    def _cleanup_resources(self) -> None:
        """
        Clean up application resources.
        """
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
        """
        Handle application shutdown with proper cleanup.

        Args:
            event: The close event.
        """
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
