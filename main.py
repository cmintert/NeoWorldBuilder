# Imports
import json
import sys
import logging
import re
import os

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
        self.driver = GraphDatabase.driver(uri, auth=(username, password))
        logging.info("Neo4jModel initialized and connected to the database.")

    def close(self):
        self.driver.close()
        logging.info("Neo4jModel connection closed.")

    def load_node(self, name):
        try:
            with self.driver.session() as session:
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
            with self.driver.session() as session:
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
            with self.driver.session() as session:
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
            with self.driver.session() as session:
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
    # Signals to communicate user actions to the controller
    save_requested = pyqtSignal()
    delete_requested = pyqtSignal()
    name_selected = pyqtSignal(str)
    image_changed = pyqtSignal(str)
    image_deleted = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        """Initialize the main UI layout"""
        main_layout = self._create_main_layout()
        left_panel = self._create_left_panel()
        right_panel = self._create_right_panel()

        main_layout.addWidget(left_panel)
        main_layout.addWidget(right_panel)

        self.setLayout(main_layout)

    def _create_main_layout(self) -> QHBoxLayout:
        """Create and configure the main horizontal layout"""
        layout = QHBoxLayout()
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(10)
        return layout

    def _create_left_panel(self) -> QTreeView:
        """Create and configure the tree view panel"""
        tree_view = QTreeView()
        tree_view.setMinimumWidth(200)
        tree_view.setMaximumWidth(300)
        tree_view.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        tree_view.setHeaderHidden(False)
        tree_view.setSortingEnabled(False)
        self.tree_view = tree_view
        return tree_view

    def _create_right_panel(self) -> QScrollArea:
        """Create the right panel with scroll area"""
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)

        container = QWidget()
        container_layout = self._create_container_layout()
        container.setLayout(container_layout)

        scroll_area.setWidget(container)
        return scroll_area

    def _create_container_layout(self) -> QVBoxLayout:
        """Create the main container layout"""
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(15)
        layout.setAlignment(Qt.AlignTop)

        # Add all major sections
        layout.addLayout(self._create_top_section())
        layout.addWidget(self._create_properties_group())
        layout.addWidget(self._create_relationships_group())
        layout.addItem(self._create_spacer())
        layout.addLayout(self._create_bottom_buttons())

        return layout

    def _create_top_section(self) -> QHBoxLayout:
        """Create the top section with node details and image"""
        layout = QHBoxLayout()
        layout.setSpacing(20)

        form_group = self._create_node_details_group()
        image_group = self._create_image_group()

        layout.addWidget(form_group, stretch=3)
        layout.addWidget(image_group, stretch=1)

        return layout

    def _create_node_details_group(self) -> QGroupBox:
        """Create the node details form group"""
        group = QGroupBox("Node Details")
        layout = QFormLayout()
        layout.setLabelAlignment(Qt.AlignRight)
        layout.setFormAlignment(Qt.AlignLeft | Qt.AlignTop)
        layout.setHorizontalSpacing(10)
        layout.setVerticalSpacing(10)

        # Create form fields
        self.name_input = QLineEdit()
        self.description_input = QTextEdit()
        self.description_input.setFixedHeight(100)
        self.labels_input = QLineEdit()
        self.tags_input = QLineEdit()

        # Add fields to layout
        layout.addRow(QLabel("Name:"), self.name_input)
        layout.addRow(QLabel("Description:"), self.description_input)
        layout.addRow(QLabel("Labels (comma-separated):"), self.labels_input)
        layout.addRow(QLabel("Tags (comma-separated):"), self.tags_input)

        group.setLayout(layout)
        return group

    def _create_image_group(self) -> QGroupBox:
        """Create the image display group"""
        group = QGroupBox("Image")
        layout = QVBoxLayout()

        # Image display
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setFixedSize(200, 200)
        layout.addWidget(self.image_label)

        # Image buttons
        button_layout = QHBoxLayout()
        self.change_image_button = QPushButton("Change Image")
        self.delete_image_button = QPushButton("Delete Image")
        button_layout.addWidget(self.change_image_button)
        button_layout.addWidget(self.delete_image_button)
        layout.addLayout(button_layout)

        group.setLayout(layout)
        return group

    def _create_properties_group(self) -> QGroupBox:
        """Create the properties group with table"""
        group = QGroupBox("Properties")
        layout = QVBoxLayout()

        # Properties table
        self.properties_table = self._create_table(
            columns=2,
            headers=["Key", "Value"]
        )
        layout.addWidget(self.properties_table)

        # Add property button
        self.add_prop_button = QPushButton("Add Property")
        layout.addWidget(self.add_prop_button)

        group.setLayout(layout)
        return group

    def _create_relationships_group(self) -> QGroupBox:
        """Create the relationships group with table"""
        group = QGroupBox("Relationships")
        layout = QVBoxLayout()

        # Relationships table
        self.relationships_table = self._create_table(
            columns=4,
            headers=["Type", "Related Node", "Direction", "Properties"]
        )
        layout.addWidget(self.relationships_table)

        # Add relationship button
        self.add_rel_button = QPushButton("Add Relationship")
        layout.addWidget(self.add_rel_button)

        group.setLayout(layout)
        return group

    def _create_table(self, columns: int, headers: list) -> QTableWidget:
        """Create a configured table widget"""
        table = QTableWidget(0, columns)
        table.setHorizontalHeaderLabels(headers)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table.verticalHeader().setVisible(False)
        return table

    def _create_spacer(self) -> QSpacerItem:
        """Create a spacer item"""
        return QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding)

    def _create_bottom_buttons(self) -> QHBoxLayout:
        """Create the bottom save/delete buttons"""
        layout = QHBoxLayout()

        self.save_button = QPushButton("Save")
        self.delete_button = QPushButton("Delete")

        layout.addStretch()
        layout.addWidget(self.save_button)
        layout.addWidget(self.delete_button)
        layout.addStretch()

        return layout

    # Methods to update UI elements
    def update_properties_table(self, properties: dict):
        self.properties_table.setRowCount(0)
        for key, value in properties.items():
            self.add_property_row(key, value)

    def add_property_row(self, key="", value=""):
        row = self.properties_table.rowCount()
        self.properties_table.insertRow(row)

        key_item = QTableWidgetItem(key)
        self.properties_table.setItem(row, 0, key_item)

        value_item = QTableWidgetItem(value)
        self.properties_table.setItem(row, 1, value_item)

    def update_relationships_table(self, relationships: list):
        self.relationships_table.setRowCount(0)
        for rel in relationships:
            related_node = rel.get("end", "")
            rel_type = rel.get("type", "")
            direction = rel.get("dir", ">")
            properties = rel.get("props", {})
            # Convert properties dict to a JSON string for better readability
            properties_str = (
                json.dumps(properties)
                if isinstance(properties, dict)
                else str(properties)
            )
            self.add_relationship_row(related_node, rel_type, direction, properties_str)

    def add_relationship_row(
        self, related_node="", rel_type="", direction=">", properties=""
    ):
        row = self.relationships_table.rowCount()
        self.relationships_table.insertRow(row)

        rel_type_item = QTableWidgetItem(rel_type)
        self.relationships_table.setItem(row, 0, rel_type_item)

        related_node_item = QTableWidgetItem(related_node)
        self.relationships_table.setItem(row, 1, related_node_item)

        direction_combo = QComboBox()
        direction_combo.addItems([">", "<"])
        direction_combo.setCurrentText(direction)
        self.relationships_table.setCellWidget(row, 2, direction_combo)

        properties_item = QTableWidgetItem(properties)
        self.relationships_table.setItem(row, 3, properties_item)

    def clear_fields(self):

        self.description_input.clear()
        self.labels_input.clear()
        self.tags_input.clear()
        self.properties_table.setRowCount(0)
        self.relationships_table.setRowCount(0)
        self.image_label.clear()

    def load_default_image_ui(self, default_image_path, default_image_size):
        if os.path.exists(default_image_path):
            pixmap = QPixmap(default_image_path)
            if pixmap.isNull():
                self.create_placeholder_image(default_image_size)
            else:
                self.display_image(pixmap)
        else:
            self.create_placeholder_image(default_image_size)

    def create_placeholder_image(self, size):
        pixmap = QPixmap(*size)
        pixmap.fill(QColor("gray"))
        painter = QPainter(pixmap)
        painter.setPen(Qt.black)
        painter.drawText(pixmap.rect(), Qt.AlignCenter, "No Image")
        painter.end()
        self.display_image(pixmap)

    def display_image(self, pixmap: QPixmap):
        if not pixmap.isNull():
            scaled_pixmap = pixmap.scaled(
                self.image_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            self.image_label.setPixmap(scaled_pixmap)
        else:
            self.image_label.clear()

    # Resize handling to update image scaling
    def resizeEvent(self, event):
        if self.image_label.pixmap():
            self.display_image(self.image_label.pixmap())
        super().resizeEvent(event)


class WorldBuildingController:
    def __init__(self, ui: WorldBuildingUI, model: Neo4jModel, config: Config):
        self.ui = ui
        self.model = model
        self.config = config
        self.worker_threads = []

        # Connect UI signals to controller methods
        self.ui.save_button.clicked.connect(self.save_node)
        self.ui.delete_button.clicked.connect(self.delete_node)
        self.ui.change_image_button.clicked.connect(self.change_image)
        self.ui.delete_image_button.clicked.connect(self.delete_image)
        self.ui.add_prop_button.clicked.connect(self.ui.add_property_row)
        self.ui.add_rel_button.clicked.connect(self.ui.add_relationship_row)

        # Connect image changed and deleted signals from UI
        self.ui.image_changed.connect(self.handle_image_changed)
        self.ui.image_deleted.connect(self.handle_image_deleted)

        # Additional UI connections (e.g., name input)
        self.ui.name_input.textChanged.connect(self.debounce_update_name_completer)
        self.ui.name_input.editingFinished.connect(self.load_node_data)

        # Initialize completer
        self.node_name_model = QStringListModel()
        self.completer = QCompleter(self.node_name_model)
        self.completer.setCaseSensitivity(False)
        self.completer.setCompletionMode(QCompleter.PopupCompletion)
        self.completer.setFilterMode(Qt.MatchContains)
        self.ui.name_input.setCompleter(self.completer)
        self.completer.activated.connect(self.on_completer_activated)

        # Initialize tree view
        self.tree_model = QStandardItemModel()
        self.ui.tree_view.setModel(self.tree_model)
        self.tree_model.clear()
        self.tree_model.setHorizontalHeaderLabels(["Relationships"])
        self.ui.tree_view.selectionModel().selectionChanged.connect(
            self.on_tree_selection_changed
        )

        # Debounce timer for name input
        self.name_input_debounce_timer = QTimer()
        self.name_input_debounce_timer.setSingleShot(True)
        self.name_input_debounce_timer.timeout.connect(self.update_name_completer)

        # Load default image
        self.default_image_path = config.UI_DEFAULT_IMAGE_PATH
        self.default_image_size = (
            config.UI_DEFAULT_IMAGE_SIZE
        )  # Assuming it's a list or tuple
        self.ui.load_default_image_ui(self.default_image_path, self.default_image_size)

    def stop_all_workers(self):
        for worker in self.worker_threads:
            if worker.isRunning():
                worker.quit()
                worker.wait()

    # Debounce methods
    def debounce_update_name_completer(self):
        self.name_input_debounce_timer.start(
            self.config.TIMING_NAME_INPUT_DEBOUNCE_TIME_MS
        )

    # Completer methods
    def update_name_completer(self):
        text = self.ui.name_input.text()
        if text.strip():
            self.fetch_matching_node_names(text)
        else:
            self.node_name_model.setStringList([])

    def fetch_matching_node_names(self, text):
        # Stop existing worker if running
        if hasattr(self, "name_fetch_worker") and self.name_fetch_worker.isRunning():
            self.name_fetch_worker.quit()
            self.name_fetch_worker.wait()

        # Create and start new worker
        worker = Neo4jQueryWorker(
            self.model.fetch_matching_node_names,
            text,
            self.config.NEO4J_MATCH_NODE_LIMIT,
        )
        worker.result_ready.connect(self.handle_matching_node_names)
        worker.error_occurred.connect(self.handle_error)
        worker.finished.connect(lambda w=worker: self.worker_threads.remove(w))
        self.worker_threads.append(worker)
        worker.start()
        self.name_fetch_worker = worker  # Assign to instance variable

    def handle_image_changed(self, image_path):
        logging.info(f"Image changed: {image_path}")

    def handle_image_deleted(self):
        logging.info("Image deleted.")

    def handle_matching_node_names(self, names):
        try:
            self.node_name_model.setStringList(names)
            self.completer.complete()
        except Exception as e:
            error_message = f"Error fetching matching node names: {e}"
            logging.error(error_message)
            QMessageBox.critical(self.ui, "Error", error_message)

    def on_completer_activated(self, text):
        self.ui.name_input.setText(text)
        self.load_node_data()

    # Tree view selection handling
    def on_tree_selection_changed(self, selected, deselected):
        indexes = selected.indexes()
        if indexes:
            selected_item = self.tree_model.itemFromIndex(indexes[0])
            node_name = re.split(r" -> | <- ", selected_item.text())[-1]
            self.ui.name_input.setText(node_name)
            self.load_node_data()

    # Load node data
    def load_node_data(self):
        name = self.ui.name_input.text()
        if not name.strip():
            self.ui.clear_fields()
            self.ui.load_default_image_ui(
                self.default_image_path, self.default_image_size
            )
            return

        logging.info(f"Loading node data for name: {name}")

        # Stop existing worker if running
        if hasattr(self, "load_node_worker") and self.load_node_worker.isRunning():
            self.load_node_worker.quit()
            self.load_node_worker.wait()

        # Create and start new worker
        worker = Neo4jQueryWorker(self.model.load_node, name)
        worker.result_ready.connect(self.handle_node_data)
        worker.error_occurred.connect(self.handle_error)
        worker.finished.connect(lambda w=worker: self.worker_threads.remove(w))
        self.worker_threads.append(worker)
        worker.start()
        self.load_node_worker = worker  # Assign to instance variable

    def handle_node_data(self, records: list):
        try:
            if records:
                node_data = records[0]
                self.populate_node_fields(node_data)
                self.populate_tree_view(node_data)
                self.load_node_image(node_data)

            else:
                self.ui.clear_fields()
                self.ui.load_default_image_ui(
                    self.default_image_path, self.default_image_size
                )

        except Exception as e:
            error_message = f"Error handling node data: {e}"
            logging.error(error_message)
            QMessageBox.critical(self.ui, "Error", error_message)

    def populate_node_fields(self, node_data: dict):
        node = node_data.get("n")
        if node:
            all_props = node_data.get("all_props", {})
            description = all_props.pop("description", "")
            tags = all_props.pop("tags", [])

            self.ui.description_input.setPlainText(
                str(description)[: self.config.LIMITS_MAX_DESCRIPTION_LENGTH]
            )

            # Handle tags
            tags = self.parse_tags(tags)
            self.ui.tags_input.setText(
                ", ".join(tags[: self.config.LIMITS_MAX_TAGS_LENGTH])
            )

            # Handle labels
            labels = self.parse_labels(node_data.get("labels", []))
            self.ui.labels_input.setText(
                ", ".join(labels[: self.config.LIMITS_MAX_LABELS_LENGTH])
            )

            # Populate properties and relationships
            self.ui.update_properties_table(all_props)
            self.ui.update_relationships_table(node_data.get("relationships", []))
        else:
            self.ui.clear_fields()

    def parse_tags(self, tags) -> list:
        if isinstance(tags, list):
            return [str(tag) for tag in tags]
        return [str(tags)]

    def parse_labels(self, labels: list) -> list:
        return [str(label) for label in labels if label != "Node"]

    def populate_tree_view(self, node_data: dict):
        self.tree_model.clear()
        self.tree_model.setHorizontalHeaderLabels(["Relationships"])

        logging.info(f"node_data: {node_data}")

        # Create the root item representing the active node
        root_item = QStandardItem(node_data["n"]["name"])

        # Highlight the active node in green
        root_item.setForeground(QBrush(QColor(90, 160, 100)))

        # Add the active node to the model (it appears only once)
        self.tree_model.appendRow(root_item)

        # Separate incoming and outgoing relationships
        incoming_rels = [rel for rel in node_data["relationships"] if rel["dir"] == "<"]
        outgoing_rels = [rel for rel in node_data["relationships"] if rel["dir"] == ">"]

        # Add a placeholder for passive relationships if they exist
        if incoming_rels:
            passive_placeholder = QStandardItem("Passive Relationships")
            root_item.appendRow(passive_placeholder)
            for rel in incoming_rels:
                parent_item = QStandardItem(f"{rel['type']} <- {rel['end']}")
                passive_placeholder.appendRow(parent_item)

        # Add active relationships as direct children of the active node
        if outgoing_rels:
            active_placeholder = QStandardItem("Active Relationships")
            root_item.appendRow(active_placeholder)
            for rel in outgoing_rels:
                parent_item = QStandardItem(f"{rel['type']} -> {rel['end']}")
                active_placeholder.appendRow(parent_item)

        # Expand the tree view
        self.expand_tree_view()

    def expand_tree_view(self):
        self.ui.tree_view.expandAll()

    def load_node_image(self, node_data: dict):
        all_props = node_data.get("all_props", {})
        image_path = all_props.get("image_path", None)

        if image_path and isinstance(image_path, str):
            if os.path.exists(image_path):
                pixmap = QPixmap(image_path)
                if pixmap.isNull():
                    logging.warning(f"Image at {image_path} is invalid.")
                    self.ui.load_default_image_ui(
                        self.default_image_path, self.default_image_size
                    )
                else:
                    self.ui.display_image(pixmap)
                    self.current_image_path = image_path
            else:
                logging.warning(f"Image path {image_path} does not exist.")
                self.ui.load_default_image_ui(
                    self.default_image_path, self.default_image_size
                )
                self.current_image_path = None
        else:
            self.ui.load_default_image_ui(
                self.default_image_path, self.default_image_size
            )
            self.current_image_path = None

    # Save Node
    def save_node(self):
        name = self.ui.name_input.text().strip()
        if not self.validate_node_name(name):
            return

        description = self.ui.description_input.toPlainText()[
            : self.config.LIMITS_MAX_DESCRIPTION_LENGTH
        ]
        tags = self.parse_input_tags()
        labels = self.parse_input_labels()

        additional_properties = self.collect_additional_properties()
        if additional_properties is None:
            return  # Error already handled

        relationships = self.collect_relationships()
        if relationships is None:
            return  # Error already handled

        # Handle image path
        image_path = getattr(self, "current_image_path", None)
        if image_path:
            additional_properties["image_path"] = image_path
        else:
            additional_properties["image_path"] = None

        node_data = {
            "name": name,
            "description": description,
            "tags": tags,
            "labels": labels,
            "additional_properties": additional_properties,
            "relationships": relationships,
        }

        # Logging the saved node data

        logging.info(f"Saving node data for name: {name}")

        try:
            node_data_json = json.dumps(node_data, indent=2)
            logging.info(f"Node data being saved: {node_data_json}")
        except (TypeError, ValueError) as e:
            logging.warning(f"Failed to serialize node_data for logging: {e}")

        # Run save operation in a separate thread to avoid blocking UI
        worker = Neo4jQueryWorker(self.model.save_node, node_data)
        worker.result_ready.connect(self.on_save_success)
        worker.error_occurred.connect(self.handle_error)
        worker.finished.connect(lambda w=worker: self.worker_threads.remove(w))
        self.worker_threads.append(worker)
        worker.start()
        self.save_node_worker = worker

    def validate_node_name(self, name: str) -> bool:
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

    def parse_input_tags(self) -> list:
        return [
            tag.strip()[: self.config.LIMITS_MAX_RELATIONSHIP_TYPE_LENGTH]
            for tag in self.ui.tags_input.text().split(",")
            if tag.strip()
        ][: self.config.LIMITS_MAX_TAGS_LENGTH]

    def parse_input_labels(self) -> list:
        return [
            label.strip()[: self.config.LIMITS_MAX_RELATIONSHIP_TYPE_LENGTH]
            for label in self.ui.labels_input.text().split(",")
            if label.strip()
        ][: self.config.LIMITS_MAX_LABELS_LENGTH]

    def collect_additional_properties(self) -> Optional[dict]:
        additional_properties = {}
        for row in range(self.ui.properties_table.rowCount()):
            key_item = self.ui.properties_table.item(row, 0)
            value_item = self.ui.properties_table.item(row, 1)
            if not key_item:
                continue
            key = key_item.text().strip()
            value = value_item.text().strip()
            if not key:
                QMessageBox.warning(
                    self.ui,
                    "Warning",
                    f"Property key in row {row + 1} cannot be empty.",
                )
                return None
            if key.lower() in self.config.RESERVED_PROPERTY_KEYS:
                QMessageBox.warning(
                    self.ui,
                    "Warning",
                    f"Property key '{key}' is reserved and cannot be used as an additional property.",
                )
                return None
            try:
                # Attempt to parse JSON value; if fails, keep as string
                parsed_value = json.loads(value) if value else value
            except json.JSONDecodeError:
                parsed_value = value
            additional_properties[key] = parsed_value
        return additional_properties

    def collect_relationships(self) -> Optional[list]:
        relationships = []
        for row in range(self.ui.relationships_table.rowCount()):
            rel_type_item = self.ui.relationships_table.item(row, 0)
            related_node_item = self.ui.relationships_table.item(row, 1)
            direction_combo = self.ui.relationships_table.cellWidget(row, 2)
            properties_item = self.ui.relationships_table.item(row, 3)

            if not related_node_item or not rel_type_item or not direction_combo:
                QMessageBox.warning(
                    self.ui, "Warning", f"Missing data in relationship row {row + 1}."
                )
                return None

            related_node = related_node_item.text().strip()[
                : self.config.LIMITS_MAX_RELATIONSHIP_NAME_LENGTH
            ]
            rel_type = rel_type_item.text().strip()[
                : self.config.LIMITS_MAX_RELATIONSHIP_TYPE_LENGTH
            ]
            direction = direction_combo.currentText()
            properties_text = (
                properties_item.text().strip()[
                    : self.config.LIMITS_MAX_RELATIONSHIP_PROPERTIES_LENGTH
                ]
                if properties_item
                else ""
            )

            if not related_node or not rel_type:
                QMessageBox.warning(
                    self.ui,
                    "Warning",
                    f"Related node and type are required in relationship row {row + 1}.",
                )
                return None

            try:
                properties = json.loads(properties_text) if properties_text else {}
            except json.JSONDecodeError:
                QMessageBox.warning(
                    self.ui,
                    "Warning",
                    f"Invalid JSON for relationship properties in row {row + 1}.",
                )
                return None

            relationships.append((rel_type, related_node, direction, properties))
        return relationships

    def on_save_success(self, _):
        QMessageBox.information(self.ui, "Success", "Node saved successfully.")
        self.update_name_completer()

    def delete_node(self):
        name = self.ui.name_input.text().strip()
        if not name:
            QMessageBox.warning(
                self.ui, "Warning", "Please enter a node name to delete."
            )
            return

        confirm = QMessageBox.question(
            self.ui,
            "Confirm Deletion",
            f"Are you sure you want to delete the node '{name}'?",
            QMessageBox.Yes | QMessageBox.No,
        )

        if confirm == QMessageBox.Yes:
            # Stop existing worker if running
            if (
                hasattr(self, "delete_node_worker")
                and self.delete_node_worker.isRunning()
            ):
                self.delete_node_worker.quit()
                self.delete_node_worker.wait()

            # Create and start new worker
            worker = Neo4jQueryWorker(self.model.delete_node, name)
            worker.result_ready.connect(self.on_delete_success)
            worker.error_occurred.connect(self.handle_error)
            worker.finished.connect(lambda w=worker: self.worker_threads.remove(w))
            self.worker_threads.append(worker)
            worker.start()
            self.delete_node_worker = worker

    def on_delete_success(self, _):
        QMessageBox.information(
            self.ui,
            "Success",
            f"Node '{self.ui.name_input.text()}' deleted successfully.",
        )
        self.ui.clear_fields()
        self.ui.name_input.clear()
        self.update_name_completer()

    def handle_error(self, error_message):
        logging.error(error_message)
        QMessageBox.critical(self.ui, "Error", error_message)

    def change_image(self):
        options = QFileDialog.Options()
        file_path, _ = QFileDialog.getOpenFileName(
            self.ui,
            "Select Image",
            "",
            "Image Files (*.png *.jpg *.jpeg *.bmp *.gif)",
            options=options,
        )
        if file_path:
            if os.path.exists(file_path):
                pixmap = QPixmap(file_path)
                if pixmap.isNull():
                    QMessageBox.warning(
                        self.ui, "Warning", "Selected file is not a valid image."
                    )
                    return
                self.ui.display_image(pixmap)
                self.current_image_path = file_path
                self.ui.image_changed.emit(file_path)  # Corrected
            else:
                QMessageBox.warning(self.ui, "Warning", "Selected file does not exist.")

    def delete_image(self):
        confirm = QMessageBox.question(
            self.ui,
            "Confirm Deletion",
            "Are you sure you want to delete the image associated with this node?",
            QMessageBox.Yes | QMessageBox.No,
        )

        if confirm == QMessageBox.Yes:
            self.ui.display_image(QPixmap())  # Clear image
            self.current_image_path = None
            self.ui.image_deleted.emit()  # Corrected


from PyQt5.QtWidgets import QMainWindow, QMessageBox
from PyQt5.QtCore import QSize
import logging
import sys
import os
from typing import Optional
from dataclasses import dataclass


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
