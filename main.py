# Imports
import json
import sys
import logging
import re
import os
from dataclasses import dataclass

from typing import Optional

from PyQt5.QtCore import QThread, pyqtSignal, QTimer, QStringListModel, Qt
from PyQt5.QtWidgets import (
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
    QSizePolicy,
    QScrollArea,
    QGroupBox,
    QFormLayout,
    QSpacerItem,
    QMainWindow,
    QTabWidget
)
from PyQt5.QtGui import (
    QStandardItemModel,
    QStandardItem,
    QImage,
    QPalette,
    QBrush,
    QPainter,
    QColor,
    QPixmap,
)

from neo4j import GraphDatabase

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


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


class Neo4jQueryWorker(QThread):
    # Handles executing Neo4j queries asynchronously in a separate thread
    result_ready = pyqtSignal(object)
    error_occurred = pyqtSignal(str)

    def __init__(self, model_method, *args, **kwargs):
        super().__init__()
        self.model_method = model_method
        self.args = args
        self.kwargs = kwargs

    def run(self):
        try:
            result = self.model_method(*self.args, **self.kwargs)
            self.result_ready.emit(result)
        except Exception as e:
            error_message = str(e)
            logging.error(f"Neo4jQueryWorker error: {error_message}")
            self.error_occurred.emit(error_message)


class Neo4jModel:
    def __init__(self, uri, username, password):
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

    def get_node_relationships(self, node_name):
        """
        Fetch all relationships for a given node, both incoming and outgoing.

        Args:
            node_name (str): Name of the node to fetch relationships for

        Returns:
            dict: Dictionary with 'outgoing' and 'incoming' relationship lists
        """
        with self.get_session() as session:
            result = session.run("""
                MATCH (n:Node {name: $name})
                OPTIONAL MATCH (n)-[r]->(m:Node)
                WITH n, collect({end: m.name, type: type(r), dir: '>'}) as outRels
                OPTIONAL MATCH (n)<-[r2]-(o:Node)
                WITH n, outRels, collect({end: o.name, type: type(r2), dir: '<'}) as inRels
                RETURN outRels + inRels as relationships
            """, name=node_name)

            record = result.single()
            return record["relationships"] if record else []

    def get_node_hierarchy(self):
        with self.get_session() as session:
            result = session.run("""
                MATCH (n:Node)
                WITH n, labels(n) AS labels
                WHERE size(labels) > 1
                RETURN DISTINCT head(labels) as category, 
                       collect(n.name) as nodes
                ORDER BY category
            """)
            return {record["category"]: record["nodes"]
                    for record in result}

    def load_node(self, name):
        try:
            with self.get_session() as session:
                result = session.run(
                    """
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
                """,
                    name=name,
                )
                records = list(result)
                return records
        except Exception as e:
            logging.error(f"Error loading node: {e}")
            raise e  # Reraise exception to be handled by caller

    def save_node(self, node_data):
        try:
            with self.get_session() as session:
                session.execute_write(self._save_node_transaction, node_data)
            logging.info(f"Node '{node_data['name']}' saved successfully.")
            return None  # Indicate success
        except Exception as e:
            logging.error(f"Error saving node: {e}")
            raise e  # Reraise exception to be handled by caller

    @staticmethod
    def _save_node_transaction(tx, node_data):
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

    def delete_node(self, name):
        try:
            with self.get_session() as session:
                session.execute_write(self._delete_node_transaction, name)
            logging.info(f"Node '{name}' deleted successfully.")
            return None  # Indicate success
        except Exception as e:
            logging.error(f"Error deleting node: {e}")
            raise e  # Reraise exception to be handled by caller

    @staticmethod
    def _delete_node_transaction(tx, name):
        query = "MATCH (n:Node {name: $name}) DETACH DELETE n"
        tx.run(query, name=name)

    def fetch_matching_node_names(self, prefix, limit):
        try:
            with self.get_session() as session:
                result = session.run(
                    "MATCH (n:Node) WHERE toLower(n.name) CONTAINS toLower($prefix) "
                    "RETURN n.name AS name LIMIT $limit",
                    prefix=prefix,
                    limit=limit,
                )
                names = [record["name"] for record in result]
                return names
        except Exception as e:
            logging.error(f"Error fetching matching node names: {e}")
            raise e


class WorldBuildingUI(QWidget):
    # Keep only essential signals
    name_selected = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.init_ui()
        self.apply_styles()

    def init_ui(self):
        """Initialize the main UI layout with modern styling"""
        main_layout = QHBoxLayout()
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(20)

        # Create splitter for resizable panels
        splitter = QSplitter(Qt.Horizontal)

        # Left panel with search and tree
        left_panel = self._create_left_panel()
        splitter.addWidget(left_panel)

        # Right panel with node details
        right_panel = self._create_right_panel()
        splitter.addWidget(right_panel)

        # Set stretch factors
        splitter.setStretchFactor(0, 1)  # Left panel
        splitter.setStretchFactor(1, 2)  # Right panel gets more space

        main_layout.addWidget(splitter)
        self.setLayout(main_layout)

    def _create_left_panel(self):
        """Create improved left panel with tree view"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        # Enhanced tree view
        self.tree_view = QTreeView()
        self.tree_view.setHeaderHidden(True)
        self.tree_view.setAnimated(True)
        self.tree_view.setAlternatingRowColors(True)
        self.tree_view.setStyleSheet("""
            QTreeView {
                border: 1px solid #ccc;
                border-radius: 4px;
                background-color: white;
            }
            QTreeView::item {
                padding: 5px;
            }
            QTreeView::item:hover {
                background: #e6f3ff;
            }
            QTreeView::item:selected {
                background: #e6f3ff;
                color: black;
            }
            QTreeView::item:selected:active {
            background: #e6f3ff;
            color: black;
        }
        """)

        layout.addWidget(self.tree_view)
        return panel

    def _create_right_panel(self):
        """Create improved right panel with tabs"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(15)

        # Header with node name and actions
        header_layout = self._create_header_layout()
        layout.addLayout(header_layout)

        # Tab widget
        tabs = QTabWidget()
        tabs.addTab(self._create_basic_info_tab(), "Basic Info")
        tabs.addTab(self._create_relationships_tab(), "Relationships")
        tabs.addTab(self._create_properties_tab(), "Properties")
        tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #ccc;
                border-radius: 4px;
                background: white;
            }
            QTabBar::tab {
                background: #f0f0f0;
                border: 1px solid #ccc;
                padding: 8px 16px;
                margin-right: 2px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            QTabBar::tab:selected {
                background: white;
                border-bottom-color: white;
            }
        """)
        layout.addWidget(tabs)
        return panel

    def _create_header_layout(self):
        """Create header with node name and actions"""
        layout = QHBoxLayout()

        # Node name input with modern styling
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Enter node name...")
        self.name_input.setMinimumHeight(35)

        # Action buttons
        self.save_button = QPushButton("💾 Save")
        self.delete_button = QPushButton("🗑️ Delete")

        for button in [self.save_button, self.delete_button]:
            button.setMinimumHeight(35)
            button.setFixedWidth(100)

        layout.addWidget(self.name_input, stretch=1)
        layout.addWidget(self.save_button)
        layout.addWidget(self.delete_button)
        return layout

    def _create_basic_info_tab(self):
        """Create the basic info tab with improved layout"""
        tab = QWidget()
        layout = QFormLayout(tab)
        layout.setSpacing(15)

        # Description
        self.description_input = QTextEdit()
        self.description_input.setPlaceholderText("Enter description...")
        self.description_input.setMinimumHeight(100)

        # Labels with auto-completion
        self.labels_input = QLineEdit()
        self.labels_input.setPlaceholderText("Enter labels (comma-separated)")

        # Tags
        self.tags_input = QLineEdit()
        self.tags_input.setPlaceholderText("Enter tags (comma-separated)")

        # Image section
        image_group = self._create_image_group()

        layout.addRow("Description:", self.description_input)
        layout.addRow("Labels:", self.labels_input)
        layout.addRow("Tags:", self.tags_input)
        layout.addRow(image_group)

        return tab

    def _create_relationships_tab(self):
        """Create improved relationships tab"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Add relationship button
        self.add_rel_button = QPushButton("➕ Add Relationship")
        self.add_rel_button.setFixedWidth(150)
        self.add_rel_button.setMinimumHeight(30)

        # Enhanced table
        self.relationships_table = self._create_table(
            4, ["Type", "Related Node", "Direction", "Properties"]
        )

        layout.addWidget(self.add_rel_button)
        layout.addWidget(self.relationships_table)
        return tab

    def _create_properties_tab(self):
        """Create improved properties tab"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Add property button
        self.add_prop_button = QPushButton("➕ Add Property")
        self.add_prop_button.setFixedWidth(150)
        self.add_prop_button.setMinimumHeight(30)

        # Enhanced table
        self.properties_table = self._create_table(2, ["Key", "Value"])

        layout.addWidget(self.add_prop_button)
        layout.addWidget(self.properties_table)
        return tab

    def _create_table(self, columns, headers):
        """Create a styled table widget"""
        table = QTableWidget(0, columns)
        table.setHorizontalHeaderLabels(headers)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table.setAlternatingRowColors(True)
        table.verticalHeader().setVisible(False)
        table.setStyleSheet("""
            QTableWidget {
                border: 1px solid #ccc;
                border-radius: 4px;
                background: white;
            }
            QTableWidget::item {
                padding: 5px;
            }
            QHeaderView::section {
                background: #f8f9fa;
                padding: 5px;
                border: none;
                border-bottom: 1px solid #dee2e6;
            }
        """)
        return table

    def _create_image_group(self):
        """Create the image display group"""
        group = QGroupBox("Image")
        layout = QVBoxLayout()

        # Image display
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setFixedSize(200, 200)
        self.image_label.setStyleSheet("""
            QLabel {
                border: 1px solid #ccc;
                border-radius: 4px;
                background: white;
            }
        """)
        layout.addWidget(self.image_label)

        # Image buttons
        button_layout = QHBoxLayout()
        button_layout.setAlignment(Qt.AlignLeft)
        self.change_image_button = QPushButton("📷 Change")
        self.delete_image_button = QPushButton("🗑️ Remove")

        for button in [self.change_image_button, self.delete_image_button]:
            button.setFixedWidth(97)
            button.setMinimumHeight(30)

        button_layout.addWidget(self.change_image_button)
        button_layout.addWidget(self.delete_image_button)
        button_layout.addStretch()
        layout.addLayout(button_layout)

        group.setLayout(layout)
        return group

    def add_relationship_row(self, rel_type="", target="", direction=">", properties=""):
        """Add a new relationship row with combobox"""
        row = self.relationships_table.rowCount()
        self.relationships_table.insertRow(row)

        # Type
        type_item = QTableWidgetItem(rel_type)
        self.relationships_table.setItem(row, 0, type_item)

        # Target
        target_item = QTableWidgetItem(target)
        self.relationships_table.setItem(row, 1, target_item)

        # Direction ComboBox
        direction_combo = QComboBox()
        direction_combo.addItems([">", "<"])
        direction_combo.setCurrentText(direction)
        self.relationships_table.setCellWidget(row, 2, direction_combo)

        # Properties
        props_item = QTableWidgetItem(properties)
        self.relationships_table.setItem(row, 3, props_item)

    def apply_styles(self):
        """Apply modern styling to the UI"""
        self.setStyleSheet("""
            QWidget {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto;
                font-size: 13px;
            }

            QPushButton {
                background-color: #f8f9fa;
                border: 1px solid #ddd;
                border-radius: 4px;
                padding: 5px 15px;
            }

            QPushButton:hover {
                background-color: #e9ecef;
            }

            QPushButton:pressed {
                background-color: #dee2e6;
            }

            QLineEdit, QTextEdit {
                border: 1px solid #ccc;
                border-radius: 4px;
                padding: 5px;
                background: white;
            }

            QLineEdit:focus, QTextEdit:focus {
                border-color: #007bff;
            }

            QGroupBox {
                border: 1px solid #ccc;
                border-radius: 4px;
                margin-top: 1em;
                padding-top: 10px;
            }
        """)


class WorldBuildingController:
    def __init__(self, ui: WorldBuildingUI, model: Neo4jModel, config: Config):
        self.ui = ui
        self.model = model
        self.config = config
        self.worker_threads = []

        # Connect UI elements
        self._initialize_tree_view()
        self._initialize_completer()

        self._setup_debounce_timer()
        self._connect_signals()

        self._load_default_state()

    def change_image(self):
        """Handle image selection and update"""
        file_dialog = QFileDialog()
        file_path, _ = file_dialog.getOpenFileName(
            self.ui,
            "Select Image",
            "",
            "Image Files (*.png *.jpg *.jpeg *.gif *.bmp);;All Files (*)"
        )

        if file_path:
            try:
                # Load and display the image
                pixmap = QPixmap(file_path)
                if not pixmap.isNull():
                    scaled_pixmap = pixmap.scaled(
                        self.ui.image_label.size(),
                        Qt.KeepAspectRatio,
                        Qt.SmoothTransformation
                    )
                    self.ui.image_label.setPixmap(scaled_pixmap)

                    # Store the image path
                    self.current_image_path = file_path

                    # Save the node to update the image
                    self.save_node()
                else:
                    raise ValueError("Failed to load image")

            except Exception as e:
                self.handle_error(f"Error loading image: {str(e)}")

    def delete_image(self):
        """Remove the current image"""
        reply = QMessageBox.question(
            self.ui,
            'Confirm Image Deletion',
            'Are you sure you want to remove this image?',
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            self.ui.image_label.clear()
            self.current_image_path = None
            self.save_node()

    def _connect_signals(self):
        """Connect all UI signals to their handlers"""
        # Direct button connections
        self.ui.save_button.clicked.connect(self.save_node)
        self.ui.delete_button.clicked.connect(self.delete_node)

        # Image buttons
        self.ui.change_image_button.clicked.connect(self.change_image)
        self.ui.delete_image_button.clicked.connect(self.delete_image)

        # Name input with autocomplete
        self.ui.name_input.textChanged.connect(self.debounce_name_input)
        self.ui.name_input.editingFinished.connect(self.load_node_data)

        # Ensure completer is connected
        self.completer.activated.connect(self.on_completer_activated)

        # Table buttons
        self.ui.add_prop_button.clicked.connect(
            lambda: self.ui.properties_table.insertRow(
                self.ui.properties_table.rowCount()
            )
        )
        self.ui.add_rel_button.clicked.connect(
            lambda: self.ui.add_relationship_row()
        )

    def _initialize_completer(self):
        """Initialize and set up name completer"""
        self.node_name_model = QStringListModel()
        self.completer = QCompleter(self.node_name_model)
        self.completer.setCaseSensitivity(False)
        self.completer.setFilterMode(Qt.MatchContains)
        self.ui.name_input.setCompleter(self.completer)
        self.completer.activated.connect(self.on_completer_activated)

    def _initialize_tree_view(self):
        """Initialize the tree view model with relationship structure"""
        self.tree_model = QStandardItemModel()
        self.tree_model.setHorizontalHeaderLabels(["Node Relationships"])
        self.ui.tree_view.setModel(self.tree_model)

        # Connect selection changed signal
        self.ui.tree_view.selectionModel().selectionChanged.connect(
            self.on_tree_selection_changed
        )

    def update_relationship_tree(self, node_name):
        """Update the tree view to show relationships for the selected node"""
        if not node_name:
            self.tree_model.clear()
            self.tree_model.setHorizontalHeaderLabels(["Node Relationships"])
            return

        self._create_worker(
            self.model.get_node_relationships,
            self._populate_relationship_tree,
            node_name
        )

    def _populate_relationship_tree(self, relationships):
        """Populate the tree view with relationship data"""
        self.tree_model.clear()
        self.tree_model.setHorizontalHeaderLabels(["Node Relationships"])

        # Create root item for the current node
        current_node = self.ui.name_input.text()
        root_item = QStandardItem(f"🔵 {current_node}")
        root_item.setEditable(False)
        self.tree_model.appendRow(root_item)

        # Group relationships by type and direction
        relationship_groups = {}
        for rel in relationships:
            key = (rel["type"], rel["dir"])
            if key not in relationship_groups:
                relationship_groups[key] = []
            relationship_groups[key].append(rel["end"])

        # Add relationship groups to the tree
        for (rel_type, direction), nodes in relationship_groups.items():
            # Create relationship type item
            direction_symbol = "▶" if direction == ">" else "◀"
            group_item = QStandardItem(f"{direction_symbol} {rel_type}")
            group_item.setEditable(False)
            root_item.appendRow(group_item)

            # Add related nodes
            for node in sorted(nodes):
                node_item = QStandardItem(f"🔵 {node}")
                node_item.setEditable(False)
                group_item.appendRow(node_item)

        # Expand all items
        self.ui.tree_view.expandAll()

    def _setup_debounce_timer(self):
        """Set up debounce timer for name input"""
        self.name_input_timer = QTimer()
        self.name_input_timer.setSingleShot(True)
        self.name_input_timer.timeout.connect(self._fetch_matching_nodes)

    def debounce_name_input(self, text):
        """Debounce the name input for autocompletion"""
        self.name_input_timer.start(300)  # 300ms debounce

    def _load_default_state(self):
        """Load initial UI state"""
        # Clear all fields
        self.ui.name_input.clear()
        self.ui.description_input.clear()
        self.ui.labels_input.clear()
        self.ui.tags_input.clear()
        self.ui.properties_table.setRowCount(0)
        self.ui.relationships_table.setRowCount(0)

        # Initial tree view population
        self.refresh_tree_view()

    def _fetch_matching_nodes(self):
        """Fetch matching node names for autocompletion"""
        text = self.ui.name_input.text()
        if text.strip():
            self._create_worker(
                self.model.fetch_matching_node_names,
                self._handle_autocomplete_results,
                text,
                self.config.NEO4J_MATCH_NODE_LIMIT
            )

    def _handle_autocomplete_results(self, names):
        """Handle autocomplete results"""
        self.node_name_model.setStringList(names)

    def _create_worker(self, method, callback, *args, **kwargs):
        """Create and start a new worker thread"""
        worker = Neo4jQueryWorker(method, *args, **kwargs)
        worker.result_ready.connect(callback)
        worker.error_occurred.connect(self.handle_error)
        worker.finished.connect(lambda w=worker: self.worker_threads.remove(w))
        self.worker_threads.append(worker)
        worker.start()
        return worker

    def save_node(self):
        """Save the current node"""
        name = self.ui.name_input.text().strip()
        if not self.validate_node_name(name):
            return

        node_data = self._collect_node_data()
        if node_data:
            self._create_worker(
                self.model.save_node,
                self.on_save_success,
                node_data
            )

    def _collect_node_data(self):
        """Collect all node data from UI"""
        try:
            # Get the basic node data
            node_data = {
                "name": self.ui.name_input.text().strip(),
                "description": self.ui.description_input.toPlainText().strip(),
                "tags": self._parse_comma_separated(self.ui.tags_input.text()),
                "labels": self._parse_comma_separated(self.ui.labels_input.text()),
                "relationships": self._collect_relationships()
            }

            # Collect properties including image path
            properties = self._collect_properties()

            # Add image path to properties if it exists
            if self.current_image_path:
                properties["image_path"] = self.current_image_path
            else:
                # Ensure image_path is None if no image is set
                properties["image_path"] = None

            node_data["additional_properties"] = properties

            return node_data
        except ValueError as e:
            self.handle_error(str(e))
            return None

    def _parse_comma_separated(self, text):
        """Parse comma-separated input with validation"""
        return [item.strip() for item in text.split(',') if item.strip()]

    def _collect_properties(self):
        """Collect properties from the properties table"""
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
                properties[key_text] = json.loads(value_text) if value_text else value_text
            except json.JSONDecodeError:
                properties[key_text] = value_text

        return properties

    def _collect_relationships(self):
        """Collect relationships from the relationships table"""
        relationships = []
        for row in range(self.ui.relationships_table.rowCount()):
            rel_type = self.ui.relationships_table.item(row, 0)
            target = self.ui.relationships_table.item(row, 1)
            direction = self.ui.relationships_table.cellWidget(row, 2)
            props = self.ui.relationships_table.item(row, 3)

            if not all([rel_type, target, direction]):
                continue

            try:
                properties = json.loads(props.text()) if props and props.text().strip() else {}
                relationships.append((
                    rel_type.text().strip(),
                    target.text().strip(),
                    direction.currentText(),
                    properties
                ))
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON in relationship properties: {e}")

        return relationships

    def refresh_tree_view(self):
        """Refresh the tree view with current node hierarchy"""
        name = self.ui.name_input.text().strip()
        if name:
            self.update_relationship_tree(name)

    def _update_tree_view(self, hierarchy_data):
        """Update tree view with hierarchy data"""
        self.tree_model.clear()
        self.tree_model.setHorizontalHeaderLabels(["Node Hierarchy"])

        # Add root items
        for category, nodes in hierarchy_data.items():
            category_item = QStandardItem(category)
            category_item.setEditable(False)

            for node in nodes:
                node_item = QStandardItem(node)
                node_item.setEditable(False)
                category_item.appendRow(node_item)

            self.tree_model.appendRow(category_item)

        self.ui.tree_view.expandAll()

    def on_save_success(self, _):
        """Handle successful node save"""
        QMessageBox.information(self.ui, "Success", "Node saved successfully")
        self.refresh_tree_view()

    def handle_error(self, error_message: str):
        """Handle any errors that occur"""
        logging.error(error_message)
        QMessageBox.critical(self.ui, "Error", error_message)

    def stop_all_workers(self):
        """Stop all running worker threads"""
        for worker in self.worker_threads:
            if worker.isRunning():
                worker.quit()
                worker.wait()

    def on_completer_activated(self, text):
        """Handle completer selection"""
        if text:
            self.ui.name_input.setText(text)
            self.load_node_data()

    def on_tree_selection_changed(self, selected, deselected):
        """Handle tree view selection"""
        indexes = selected.indexes()
        if indexes:
            selected_item = self.tree_model.itemFromIndex(indexes[0])
            if selected_item and selected_item.parent():
                # Only act on node items (those with the 🔵 prefix)
                text = selected_item.text()
                if text.startswith("🔵"):
                    node_name = text[2:].strip()  # Remove emoji and whitespace
                    if node_name != self.ui.name_input.text():
                        self.ui.name_input.setText(node_name)
                        self.load_node_data()

    def load_node_data(self):
        """Load node data when selected"""
        name = self.ui.name_input.text()
        if not name.strip():
            return

        # Update the relationship tree when loading a node
        self.update_relationship_tree(name)

        self._create_worker(
            self.model.load_node,
            self._handle_node_data,
            name
        )

    def _handle_node_data(self, records):
        """Handle loaded node data"""
        if not records:
            return

        node_data = records[0]
        self._populate_node_fields(node_data)

    def validate_node_name(self, name: str) -> bool:
        """Validate node name"""
        if not name:
            QMessageBox.warning(self.ui, "Warning", "Node name cannot be empty.")
            return False

        if len(name) > self.config.LIMITS_MAX_NODE_NAME_LENGTH:
            QMessageBox.warning(
                self.ui,
                "Warning",
                f"Node name cannot exceed {self.config.LIMITS_MAX_NODE_NAME_LENGTH} characters."
            )
            return False

        return True

    def delete_node(self):
        """Delete the current node"""
        name = self.ui.name_input.text().strip()
        if not name:
            return

        reply = QMessageBox.question(
            self.ui,
            'Confirm Deletion',
            f'Are you sure you want to delete node "{name}"?',
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            self._create_worker(
                self.model.delete_node,
                self._handle_delete_success,
                name
            )

    def _handle_delete_success(self, _):
        """Handle successful node deletion"""
        QMessageBox.information(self.ui, "Success", "Node deleted successfully")
        self.ui.name_input.clear()
        self._load_default_state()
        self.refresh_tree_view()

    def _populate_node_fields(self, node_data):
        """Populate UI fields with node data"""
        try:
            # Extract data from Neo4j response
            node = node_data["n"]
            relationships = node_data["relationships"]
            labels = node_data["labels"]
            all_props = node_data["all_props"]

            # Set basic fields
            self.ui.description_input.setText(all_props.get("description", ""))

            # Set labels (excluding 'Node' label)
            label_list = [label for label in labels if label != "Node"]
            self.ui.labels_input.setText(", ".join(label_list))

            # Set tags
            tags = all_props.get("tags", [])
            if isinstance(tags, list):
                self.ui.tags_input.setText(", ".join(tags))

            # Clear and populate properties table
            self.ui.properties_table.setRowCount(0)
            for key, value in all_props.items():
                if key not in self.config.RESERVED_PROPERTY_KEYS:
                    row = self.ui.properties_table.rowCount()
                    self.ui.properties_table.insertRow(row)
                    self.ui.properties_table.setItem(row, 0, QTableWidgetItem(key))
                    self.ui.properties_table.setItem(row, 1, QTableWidgetItem(str(value)))

            # Clear and populate relationships table
            self.ui.relationships_table.setRowCount(0)
            for rel in relationships:
                rel_type = rel.get("type", "")
                end_node = rel.get("end", "")
                direction = rel.get("dir", ">")
                props = json.dumps(rel.get("props", {}))
                self.ui.add_relationship_row(rel_type, end_node, direction, props)

            # Handle image if present
            image_path = node_data["all_props"].get("image_path")
            self.current_image_path = image_path
            if image_path and os.path.exists(image_path):
                pixmap = QPixmap(image_path)
                scaled_pixmap = pixmap.scaled(
                    self.ui.image_label.size(),
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation
                )
                self.ui.image_label.setPixmap(scaled_pixmap)
            else:
                self.ui.image_label.clear()
                self.current_image_path = None

        except Exception as e:
            logging.error(f"Error populating node fields: {e}")
            self.handle_error(f"Error loading node data: {str(e)}")


@dataclass
class AppComponents:
    """Container for main application components"""

    ui: "WorldBuildingUI"
    model: "Neo4jModel"
    controller: "WorldBuildingController"
    config: "Config"


class WorldBuildingApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.components: Optional[AppComponents] = None
        self.initialize_application()

    def initialize_application(self) -> None:
        """Initialize all application components with proper error handling"""
        try:
            # 1. Load Configuration
            config = self._load_configuration()

            # 2. Initialize Database Model
            model = self._initialize_database(config)

            # 3. Setup UI
            ui = self._setup_ui()

            # 4. Initialize Controller
            controller = self._initialize_controller(ui, model, config)

            # Store components for access in other methods
            self.components = AppComponents(
                ui=ui, model=model, controller=controller, config=config
            )

            # 5. Configure Window
            self._configure_main_window()

            # 6. Setup Background
            self._setup_background()

            # 7. Show Window
            self.show()

            logging.info("Application initialized successfully")

        except Exception as e:
            self._handle_initialization_error(e)

    def _load_configuration(self) -> "Config":
        """Load application configuration"""
        config = Config("config.json")
        logging.info("Configuration loaded successfully")
        return config

    def _initialize_database(self, config: "Config") -> "Neo4jModel":
        """Initialize database connection"""
        model = Neo4jModel(
            config.NEO4J_URI, config.NEO4J_USERNAME, config.NEO4J_PASSWORD
        )
        logging.info("Neo4jModel initialized and connected to the database")
        return model

    def _setup_ui(self) -> "WorldBuildingUI":
        """Initialize user interface"""
        ui = WorldBuildingUI()
        logging.info("WorldBuildingUI initialized")
        return ui

    def _initialize_controller(
        self, ui: "WorldBuildingUI", model: "Neo4jModel", config: "Config"
    ) -> "WorldBuildingController":
        """Initialize application controller"""
        controller = WorldBuildingController(ui, model, config)
        logging.info("WorldBuildingController initialized")
        return controller

    def _configure_main_window(self) -> None:
        """Configure main window properties"""
        self.setObjectName("WorldBuildingApp")
        self.setCentralWidget(self.components.ui)

        # Set window title
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
            f"Application window resized to "
            f"{self.components.config.UI_WINDOW_WIDTH}x"
            f"{self.components.config.UI_WINDOW_HEIGHT}"
        )

    def _setup_background(self) -> None:
        """Setup tiling background image using PyQt5's palette system"""
        bg_path = self.components.config.UI_BACKGROUND_IMAGE_PATH
        if os.path.exists(bg_path):
            try:
                # Create a palette for the window
                palette = self.palette()

                # Load the image
                image = QImage(bg_path)
                if image.isNull():
                    logging.error("Failed to load background image")
                    return

                # Create a brush that tiles the image
                brush = QBrush(image)

                # Set the background using the palette
                palette.setBrush(QPalette.Window, brush)

                # Apply the palette
                self.setPalette(palette)

                # Enable auto fill background
                self.setAutoFillBackground(True)

                # Also set for central widget
                self.centralWidget().setAutoFillBackground(True)
                self.centralWidget().setPalette(palette)

                logging.info(f"Tiling background image set from {bg_path}")

            except Exception as e:
                logging.error(f"Error setting background image: {e}")
        else:
            logging.warning(f"Background image path {bg_path} does not exist.")

    def _handle_initialization_error(self, error: Exception) -> None:
        """Handle initialization errors"""
        error_message = f"Failed to initialize the application:\n{str(error)}"
        logging.error(error_message)

        QMessageBox.critical(self, "Initialization Error", error_message)

        # Cleanup resources if needed
        if self.components and self.components.model:
            try:
                self.components.model.close()
            except Exception as e:
                logging.error(f"Failed to cleanup resources: {e}")

        sys.exit(1)

    def closeEvent(self, event) -> None:
        """Handle application shutdown"""
        logging.info("Closing application...")
        try:
            # Stop all worker threads
            self.components.controller.stop_all_workers()
            logging.info("All worker threads terminated.")

            # Close database connection
            self.components.model.close()
            logging.info("Neo4jModel connection closed.")

            event.accept()
        except Exception as e:
            logging.error(f"Error during application shutdown: {e}")
            event.accept()  # Accept the close event even if cleanup fails



if __name__ == "__main__":
    app = QApplication(sys.argv)
    ex = WorldBuildingApp()
    sys.exit(app.exec_())
