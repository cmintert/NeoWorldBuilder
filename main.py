import json
import sys
import logging
import re

from typing import Optional

from PyQt5.QtCore import (QThread, pyqtSignal, QTimer, QStringListModel, Qt)

from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QLineEdit, QPushButton, QCompleter,
                             QTableWidget, QTableWidgetItem, QHeaderView,
                             QMessageBox, QTextEdit, QComboBox, QSplitter, QTreeView)

from PyQt5.QtGui import QStandardItemModel, QStandardItem, QImage, QPalette, QBrush, QPainter

from neo4j import GraphDatabase

# Configure logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')


class Neo4jQueryWorker(QThread):
    """
    Worker thread for executing Neo4j queries asynchronously.
    """
    result_ready = pyqtSignal(object)
    error_occurred = pyqtSignal(str)

    def __init__(self, driver, query_func, *args, **kwargs):
        super().__init__()
        self.driver = driver
        self.query_func = query_func
        self.args = args
        self.kwargs = kwargs

    def run(self):
        try:
            with self.driver.session() as session:
                result = self.query_func(session, *self.args, **self.kwargs)
                self.result_ready.emit(result)
        except Exception as e:
            error_message = str(e)
            logging.error(f"Neo4jWorker error: {error_message}")
            self.error_occurred.emit(error_message)


class WorldBuildingApp(QWidget):
    """
    Main application class.
    """
    def __init__(self):
        super().__init__()
        self.worker = None  # Initialize self.worker
        try:
            # Use a plain password (replace with your actual password)
            neo4j_password = 'Godfather666'  # Replace with your actual password
            self.driver = GraphDatabase.driver(
                "bolt://192.168.178.84:7687", auth=("neo4j", neo4j_password))
            self.init_ui()
            self.setObjectName("WorldBuildingApp")

        except Exception as e:
            logging.error(f"Initialization error: {e}")
            QMessageBox.critical(self, "Error",
                                 f"Failed to initialize the application: {e}")
            sys.exit(1)

        self.resize(800, 600)

        background = QImage("background.png")
        palette = QPalette()
        palette.setBrush(QPalette.Window, QBrush(background))
        self.setPalette(palette)


    def on_tree_selection_changed(self, selected, deselected):
        indexes = selected.indexes()
        if indexes:
            selected_item = self.tree_model.itemFromIndex(indexes[0])
            node_name = re.split(r' -> | <- ', selected_item.text())[-1]
            self.name_input.setText(node_name)
            self.load_node_data()

    def init_ui(self):
        layout = QVBoxLayout()

        # Set margins and spacing
        layout.setContentsMargins(20, 20,20, 20)

        # Splitter to separate tree view and main UI
        splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(splitter)

        # Tree view for the left sidebar
        self.tree_view = QTreeView()
        splitter.addWidget(self.tree_view)

        # **Disable automatic sorting to preserve order**
        self.tree_view.setSortingEnabled(False)

        # Main UI container
        main_ui_container = QWidget()
        main_ui_layout = QVBoxLayout()
        main_ui_container.setLayout(main_ui_layout)
        splitter.addWidget(main_ui_container)

        # Name input
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("Name:"))
        self.name_input = QLineEdit()
        self.name_input.setMaxLength(100)
        name_layout.addWidget(self.name_input)
        main_ui_layout.addLayout(name_layout)

        # Description input
        main_ui_layout.addWidget(QLabel("Description:"))
        self.description_input = QTextEdit()
        self.description_input.setPlaceholderText("Enter description (max 10,000 characters)")
        main_ui_layout.addWidget(self.description_input)

        # Labels input
        main_ui_layout.addWidget(QLabel("Labels (comma-separated):"))
        self.labels_input = QLineEdit()
        self.labels_input.setMaxLength(500)  # Adjust as needed
        main_ui_layout.addWidget(self.labels_input)

        # Tags input
        main_ui_layout.addWidget(QLabel("Tags (comma-separated):"))
        self.tags_input = QLineEdit()
        self.tags_input.setMaxLength(500)  # Adjust as needed
        main_ui_layout.addWidget(self.tags_input)

        # Properties input
        main_ui_layout.addWidget(QLabel("Properties:"))
        self.properties_table = QTableWidget(0, 2)
        self.properties_table.setHorizontalHeaderLabels(["Key", "Value"])
        self.properties_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        main_ui_layout.addWidget(self.properties_table)

        # Add property button
        add_prop_button = QPushButton("Add Property")
        add_prop_button.clicked.connect(self.add_property_row)
        main_ui_layout.addWidget(add_prop_button)

        # Relationships table
        main_ui_layout.addWidget(QLabel("Relationships:"))
        self.relationships_table = QTableWidget(0, 4)
        self.relationships_table.setHorizontalHeaderLabels(
            ["Related Node", "Type", "Direction", "Properties"])
        self.relationships_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch)
        main_ui_layout.addWidget(self.relationships_table)

        # Add relationship button
        add_rel_button = QPushButton("Add Relationship")
        add_rel_button.clicked.connect(self.add_relationship_row)
        main_ui_layout.addWidget(add_rel_button)


        # Save and Delete buttons
        buttons_layout = QHBoxLayout()
        save_button = QPushButton("Save")
        save_button.clicked.connect(self.save_node)
        buttons_layout.addWidget(save_button)

        delete_button = QPushButton("Delete")
        delete_button.clicked.connect(self.delete_node)
        buttons_layout.addWidget(delete_button)

        main_ui_layout.addLayout(buttons_layout)

        self.setLayout(layout)
        self.setWindowTitle('NeoRealmBuilder')
        self.show()

        # Initialize the model and completer
        self.node_name_model = QStringListModel()
        self.completer = QCompleter(self.node_name_model)
        self.completer.setCaseSensitivity(False)
        self.completer.setCompletionMode(QCompleter.PopupCompletion)
        self.completer.setFilterMode(Qt.MatchContains)
        self.name_input.setCompleter(self.completer)

        # Connect the completers activated signal
        self.completer.activated.connect(self.on_completer_activated)

        # Initialize the tree view model
        self.tree_model = QStandardItemModel()
        self.tree_view.setModel(self.tree_model)
        self.tree_model.clear()
        self.tree_model.setHorizontalHeaderLabels(['Relationships'])

        # Connect tree view selection signal
        self.tree_view.selectionModel().selectionChanged.connect(self.on_tree_selection_changed)

        # Setup debounce timer for name input (for updating completer suggestions)
        self.name_input_debounce_timer = QTimer()
        self.name_input_debounce_timer.setSingleShot(True)
        self.name_input.textChanged.connect(self.debounce_update_name_completer)
        self.name_input_debounce_timer.timeout.connect(self.update_name_completer)

        # Connect editingFinished to load data when user presses Enter or focus leaves
        self.name_input.editingFinished.connect(self.load_node_data)

    def add_property_row(self, key="", value=""):
        row = self.properties_table.rowCount()
        self.properties_table.insertRow(row)

        key_item = QTableWidgetItem(key)
        self.properties_table.setItem(row, 0, key_item)

        value_item = QTableWidgetItem(value)
        self.properties_table.setItem(row, 1, value_item)

    def debounce_update_name_completer(self):
        self.name_input_debounce_timer.start(100)  # Reduced debounce time

    def update_name_completer(self):
        text = self.name_input.text()
        if text.strip():
            # Start a thread to fetch matching node names
            self.fetch_matching_node_names(text)
        else:
            # Clear the completer if the text is empty
            self.node_name_model.setStringList([])

    def fetch_matching_node_names(self, text):
        if hasattr(self, 'name_fetch_worker') and self.name_fetch_worker.isRunning():
            self.name_fetch_worker.quit()
            self.name_fetch_worker.wait()

        self.name_fetch_worker = Neo4jQueryWorker(
            self.driver, self.query_func_fetch_names, text)
        self.name_fetch_worker.result_ready.connect(
            self.handle_matching_node_names)
        self.name_fetch_worker.error_occurred.connect(self.handle_error)
        self.name_fetch_worker.start()

    def query_func_fetch_names(self, session, prefix):
        result = session.run(
            "MATCH (n:Node) WHERE toLower(n.name) CONTAINS toLower($prefix) RETURN n.name AS name LIMIT 50",
            prefix=prefix)
        return [record["name"] for record in result]

    def handle_matching_node_names(self, names):
        try:
            self.node_name_model.setStringList(names)
            # Force the completer to update its popup
            self.completer.complete()
        except Exception as e:
            error_message = f"Error fetching matching node names: {e}"
            logging.error(error_message)
            QMessageBox.critical(self, "Error", error_message)

    def on_completer_activated(self, text):
        self.name_input.setText(text)
        self.load_node_data()

    def load_node_data(self):
        name = self.name_input.text()
        if not name.strip():
            self.clear_fields()
            return

        logging.info(f"Loading node data for name: {name}")

        # Ensure self.worker is initialized and not running
        if self.worker is not None and self.worker.isRunning():
            self.worker.quit()
            self.worker.wait()

        self.worker = Neo4jQueryWorker(
            self.driver, self.query_func_load_node, name)
        self.worker.result_ready.connect(self.handle_node_data)
        self.worker.error_occurred.connect(self.handle_error)
        self.worker.start()

    def query_func_load_node(self, session, name):
        result = session.run("""
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
        """, name=name)
        return list(result)

    def handle_node_data(self, records: list) -> None:
        try:
            if records:
                node_data = records[0]
                self.populate_node_fields(node_data)
                self.populate_tree_view(node_data)
            else:
                self.clear_fields()
        except Exception as e:
            error_message = f"Error handling node data: {e}"
            logging.error(error_message)
            QMessageBox.critical(self, "Error", error_message)

    def populate_tree_view(self, node_data: dict) -> None:
        self.tree_model.clear()
        self.tree_model.setHorizontalHeaderLabels(['Relationships'])

        # Log the contents of node_data
        logging.info(f"node_data: {node_data}")

        # Create the root item representing the active node
        root_item = QStandardItem(node_data['n']['name'])

        # Highlight the active node in green
        root_item.setForeground(QBrush(Qt.green))

        # Add the active node to the model (it appears only once)
        self.tree_model.appendRow(root_item)

        # Separate incoming and outgoing relationships
        incoming_rels = [rel for rel in node_data['relationships'] if rel['dir'] == '<']
        outgoing_rels = [rel for rel in node_data['relationships'] if rel['dir'] == '>']

        # Add a placeholder for passive relationships if they exist
        if incoming_rels:
            passive_placeholder = QStandardItem("Passive Relationships")
            root_item.appendRow(passive_placeholder)
            for rel in incoming_rels:
                parent_item = QStandardItem(f"{rel['type']} <- {rel['end']}")
                passive_placeholder.appendRow(parent_item)

        # Add active relationships as direct children of the active node
        active_placeholder = None
        if outgoing_rels:
            active_placeholder = QStandardItem("Active Relationships")
            root_item.appendRow(active_placeholder)
            for rel in outgoing_rels:
                parent_item = QStandardItem(f"{rel['type']} -> {rel['end']}")
                active_placeholder.appendRow(parent_item)

        # Expand only the 'Active Relationships' branch
        if active_placeholder:
            self.expand_active_relationships_branch(root_item, active_placeholder)

    def expand_all_tree_items(self):
        def recursive_expand(item):
            for row in range(item.rowCount()):
                child = item.child(row)
                print(child.text())
                if child:
                    self.tree_view.setExpanded(self.tree_model.indexFromItem(child), True)
                    recursive_expand(child)

        root_item = self.tree_model.invisibleRootItem()
        recursive_expand(root_item)

    def expand_active_relationships_branch(self, root_item, active_placeholder):
        def recursive_expand(item):
            for row in range(item.rowCount()):
                child = item.child(row)
                if child:
                    self.tree_view.setExpanded(self.tree_model.indexFromItem(child), True)
                    recursive_expand(child)

        # Expand the root node (active node)
        self.tree_view.setExpanded(self.tree_model.indexFromItem(root_item), True)

        # Expand the entire 'Active Relationships' branch
        self.tree_view.setExpanded(self.tree_model.indexFromItem(active_placeholder), True)
        recursive_expand(active_placeholder)

    def add_relationships_to_tree(self, parent_item, relationships, depth):
        if depth <= 0:
            return
        for rel in relationships:
            branch_name = f"{rel['type']} -> {rel['end']}" if rel['dir'] == '>' else f"{rel['type']} <- {rel['end']}"
            child_item = QStandardItem(branch_name)
            parent_item.appendRow(child_item)
            # Optionally, fetch and add further relationships recursively
            # self.add_relationships_to_tree(child_item, child_relationships, depth - 1)

    def populate_node_fields(self, node_data: dict) -> None:
        node = node_data.get('n')
        if node:
            all_props = node_data.get('all_props', {})
            description = all_props.pop('description', '')
            tags = all_props.pop('tags', [])

            self.description_input.setPlainText(str(description)[:10000])

            # Handle tags
            tags = self.parse_tags(tags)
            self.tags_input.setText(', '.join(tags[:100]))

            # Handle labels
            labels = self.parse_labels(node_data.get('labels', []))
            self.labels_input.setText(', '.join(labels[:100]))

            # Populate properties and relationships
            self.populate_properties(all_props)
            self.populate_relationships(node_data.get('relationships', []))
        else:
            self.clear_fields()

    def parse_tags(self, tags) -> list:
        if isinstance(tags, list):
            return [str(tag) for tag in tags]
        return [str(tags)]

    def parse_labels(self, labels: list) -> list:
        return [str(label) for label in labels if label != 'Node']

    def populate_properties(self, properties: dict) -> None:
        self.properties_table.setRowCount(0)
        for key, value in properties.items():
            self.add_property_row(key, json.dumps(value) if isinstance(value, (dict, list)) else str(value)[:1000])

    def populate_relationships(self, relationships: list) -> None:
        self.relationships_table.setRowCount(0)
        relationships = [rel for rel in relationships if rel is not None]
        for rel in relationships[:100]:
            if not isinstance(rel, dict):
                continue
            related_node = rel.get('end', '')[:100] if rel.get('end') else ''
            rel_type = str(rel.get('type', ''))[:50]
            direction = str(rel.get('dir', ''))
            properties = json.dumps(rel.get('props', {}))[:1000] if rel.get('props') else '{}'
            self.add_relationship_row(related_node, rel_type, direction, properties)

    def clear_fields(self):
        self.description_input.clear()
        self.tags_input.clear()
        self.labels_input.clear()
        self.properties_table.setRowCount(0)
        self.relationships_table.setRowCount(0)

    def handle_error(self, error_message):
        logging.error(error_message)
        QMessageBox.critical(self, "Error", error_message)

    def add_relationship_row(self, related_node="", rel_type="", direction=">", properties=""):
        row = self.relationships_table.rowCount()
        if row >= 100:  # Limit number of relationships
            QMessageBox.warning(
                self, "Warning", "Maximum number of relationships reached.")
            return
        self.relationships_table.insertRow(row)

        # Ensure related_node is a string
        related_node_str = str(related_node)
        related_node_item = QTableWidgetItem(related_node_str)
        related_node_item.setToolTip(related_node_str)
        self.relationships_table.setItem(row, 0, related_node_item)

        # Relationship Type
        rel_type_str = str(rel_type)
        rel_type_item = QTableWidgetItem(rel_type_str)
        rel_type_item.setToolTip(rel_type_str)
        self.relationships_table.setItem(row, 1, rel_type_item)

        # Direction
        direction_combo = QComboBox()
        direction_combo.addItems(['>', '<'])
        index = direction_combo.findText(direction)
        if index >= 0:
            direction_combo.setCurrentIndex(index)
        self.relationships_table.setCellWidget(row, 2, direction_combo)

        # Properties
        properties_str = str(properties)
        properties_item = QTableWidgetItem(properties_str)
        properties_item.setToolTip(properties_str)
        self.relationships_table.setItem(row, 3, properties_item)

    def save_node(self):
        name = self.name_input.text().strip()
        if not self.validate_node_name(name):
            return

        description = self.description_input.toPlainText()[:10000]
        tags = self.parse_input_tags()
        labels = self.parse_input_labels()

        additional_properties = self.collect_additional_properties()
        if additional_properties is None:
            return  # Error already handled in collect_additional_properties

        relationships = self.collect_relationships()
        if relationships is None:
            return  # Error already handled in collect_relationships

        # Run save operation in a separate thread to avoid blocking UI
        self.worker = Neo4jQueryWorker(
            self.driver,
            self._save_node,
            name,
            description,
            tags,
            additional_properties,
            relationships,
            labels
        )
        self.worker.result_ready.connect(self.on_save_success)
        self.worker.error_occurred.connect(self.handle_error)
        self.worker.start()

    def validate_node_name(self, name: str) -> bool:
        if not name:
            QMessageBox.warning(self, "Warning", "Node name cannot be empty.")
            return False
        if len(name) > 100:
            QMessageBox.warning(self, "Warning", "Node name cannot exceed 100 characters.")
            return False
        return True

    def parse_input_tags(self) -> list:
        return [
                   tag.strip()[:50]
                   for tag in self.tags_input.text().split(',')
                   if tag.strip()
               ][:100]

    def parse_input_labels(self) -> list:
        return [
                   label.strip()[:50]
                   for label in self.labels_input.text().split(',')
                   if label.strip()
               ][:100]

    def collect_additional_properties(self) -> Optional[dict]:
        additional_properties = {}
        for row in range(self.properties_table.rowCount()):
            key_item = self.properties_table.item(row, 0)
            value_item = self.properties_table.item(row, 1)
            if not key_item:
                continue
            key = key_item.text().strip()
            value = value_item.text().strip()
            if not key:
                QMessageBox.warning(
                    self, "Warning",
                    f"Property key in row {row + 1} cannot be empty."
                )
                return None
            if key.lower() in ['description', 'tags']:
                QMessageBox.warning(
                    self, "Warning",
                    f"Property key '{key}' is reserved and cannot be used as an additional property."
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
        for row in range(self.relationships_table.rowCount()):
            related_node_item = self.relationships_table.item(row, 0)
            rel_type_item = self.relationships_table.item(row, 1)
            direction_combo = self.relationships_table.cellWidget(row, 2)
            properties_item = self.relationships_table.item(row, 3)

            if not related_node_item or not rel_type_item or not direction_combo:
                QMessageBox.warning(
                    self, "Warning",
                    f"Missing data in relationship row {row + 1}."
                )
                return None

            related_node = related_node_item.text().strip()[:100]
            rel_type = rel_type_item.text().strip()[:50]
            direction = direction_combo.currentText()
            properties_text = properties_item.text().strip()[:1000] if properties_item else ''

            if not related_node or not rel_type:
                QMessageBox.warning(
                    self, "Warning",
                    f"Related node and type are required in relationship row {row + 1}."
                )
                return None

            try:
                properties = json.loads(properties_text) if properties_text else {}
            except json.JSONDecodeError:
                QMessageBox.warning(
                    self, "Warning",
                    f"Invalid JSON for relationship properties in row {row + 1}."
                )
                return None

            relationships.append((related_node, rel_type, direction, properties))
        return relationships

    def _save_node(self, session, name, description, tags, additional_properties, relationships, labels):
        session.execute_write(
            self._save_node_transaction, name, description, tags, additional_properties, relationships, labels)
        return None

    @staticmethod
    def _save_node_transaction(tx, name, description, tags, additional_properties, relationships, labels):
        # Merge with 'Node' label
        query_merge = (
            "MERGE (n:Node {name: $name}) "
            "SET n.description = $description, n.tags = $tags"
        )
        tx.run(query_merge, name=name, description=description, tags=tags)

        # Retrieve existing labels excluding 'Node'
        result = tx.run("MATCH (n:Node {name: $name}) RETURN labels(n) AS labels", name=name)
        record = result.single()
        existing_labels = record["labels"] if record else []
        existing_labels = [label for label in existing_labels if label != 'Node']

        # Determine labels to add and remove
        input_labels_set = set(labels)
        existing_labels_set = set(existing_labels)

        labels_to_add = input_labels_set - existing_labels_set
        labels_to_remove = existing_labels_set - input_labels_set

        # Add new labels
        if labels_to_add:
            # Properly escape labels to prevent Cypher injection
            labels_str = ":".join([f"`{label}`" for label in labels_to_add])
            query_add = f"MATCH (n:Node {{name: $name}}) SET n:{labels_str}"
            tx.run(query_add, name=name)

        # Remove labels that are no longer needed
        for label in labels_to_remove:
            # Properly escape label to prevent Cypher injection
            query_remove = f"MATCH (n:Node {{name: $name}}) REMOVE n:`{label}`"
            tx.run(query_remove, name=name)

        # Set additional properties if any
        if additional_properties:
            query_props = "MATCH (n:Node {name: $name}) SET n += $additional_properties"
            tx.run(query_props, name=name, additional_properties=additional_properties)

        # Remove existing relationships
        query_remove_rels = "MATCH (n:Node {name: $name})-[r]-() DELETE r"
        tx.run(query_remove_rels, name=name)

        # Create/update relationships
        for rel in relationships:
            rel_name, rel_type, direction, properties = rel
            if direction == '>':
                query_rel = (
                    "MATCH (n:Node {name: $name}) "
                    "MERGE (m:Node {name: $rel_name}) "
                    f"MERGE (n)-[r:`{rel_type}`]->(m) "
                    "SET r = $properties"
                )
            else:
                query_rel = (
                    "MATCH (n:Node {name: $name}) "
                    "MERGE (m:Node {name: $rel_name}) "
                    f"MERGE (m)-[r:`{rel_type}`]->(n) "
                    "SET r = $properties"
                )
            tx.run(query_rel, name=name, rel_name=rel_name, properties=properties)

    def on_save_success(self, _):
        QMessageBox.information(self, "Success", "Node saved successfully.")
        self.update_name_completer()

    def delete_node(self):
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(
                self, "Warning", "Please enter a node name to delete.")
            return

        confirm = QMessageBox.question(
            self, "Confirm Deletion",
            f"Are you sure you want to delete the node '{name}'?",
            QMessageBox.Yes | QMessageBox.No)

        if confirm == QMessageBox.Yes:
            # Run delete operation in a separate thread to avoid blocking UI
            self.worker = Neo4jQueryWorker(
                self.driver, self._delete_node, name)
            self.worker.result_ready.connect(self.on_delete_success)
            self.worker.error_occurred.connect(self.handle_error)
            self.worker.start()

    def _delete_node(self, session, name):
        session.execute_write(self._delete_node_transaction, name)
        return None

    @staticmethod
    def _delete_node_transaction(tx, name):
        query = "MATCH (n:Node {name: $name}) DETACH DELETE n"
        tx.run(query, name=name)

    def on_delete_success(self, _):
        QMessageBox.information(self, "Success", f"Node '{self.name_input.text()}' deleted successfully.")
        self.clear_fields()
        self.name_input.clear()
        self.update_name_completer()

    def closeEvent(self, event):
        logging.info("Closing application")
        try:
            # Ensure all threads are stopped
            if self.worker is not None and self.worker.isRunning():
                self.worker.quit()
                self.worker.wait()
            self.driver.close()
        except Exception as e:
            logging.error(f"Error closing Neo4j driver: {e}")
        event.accept()

    def update_name_completer(self):
        # Fetch all node names starting with an empty string to refresh the completer
        self.fetch_matching_node_names('')


if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = WorldBuildingApp()
    sys.exit(app.exec_())
