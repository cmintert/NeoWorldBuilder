from PyQt6.QtCore import QObject, pyqtSlot, Qt
from PyQt6.QtGui import QStandardItem, QIcon, QStandardItemModel
from PyQt6.QtWidgets import QMessageBox

from core.neo4jmodel import Neo4jModel


class TreeController(QObject):
    """
    Controller class to manage the tree view and relationships.
    """

    NODE_RELATIONSHIPS_HEADER = "Node Relationships"

    def __init__(self, model: Neo4jModel, ui: "WorldBuildingUI"):
        """
        Initialize the TreeController with the Neo4j model and UI.

        Args:
            model (Neo4jModel): The Neo4j model instance.
            ui (WorldBuildingUI): The UI instance.
        """
        super().__init__()
        self.model = model
        self.ui = ui
        self.tree_model = QStandardItemModel()
        self.tree_model.setHorizontalHeaderLabels([self.NODE_RELATIONSHIPS_HEADER])
        self.ui.tree_view.setModel(self.tree_model)
        self.current_relationship_worker = None

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
        if name := self.ui.name_input.text().strip():
            self.update_relationship_tree(name)

    def on_tree_selection_changed(self, selected, deselected):
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
                    self.ui.controller.load_node_data()

    @pyqtSlot(list)
    def _populate_relationship_tree(self, records: list):
        """
        Populate the tree view with relationships up to the specified depth.

        Args:
            records (list): The list of relationship records.
        """
        self.tree_model.clear()
        self.tree_model.setHorizontalHeaderLabels([self.NODE_RELATIONSHIPS_HEADER])

        if not records:
            return

        root_node_name = self.ui.name_input.text().strip()
        if not root_node_name:
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

        parent_child_map, skipped_records = self.process_relationship_records(records)

        self.add_children(root_node_name, root_item, [root_node_name], parent_child_map)

        self.tree_model.appendRow(root_item)
        self.ui.tree_view.expandAll()

        if skipped_records > 0:
            QMessageBox.warning(
                self.ui,
                "Warning",
                f"Skipped {skipped_records} incomplete relationship records.",
            )

    def process_relationship_records(self, records: list):
        """
        Process relationship records and build parent-child map, handling both incoming and outgoing relationships.

        Args:
            records (list): The list of relationship records.

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
                skipped_records += 1
                continue

            if direction == ">":
                # Outgoing relationship: parent_name -> node_name
                parent = parent_name
                child = node_name
            elif direction == "<":
                # Incoming relationship: node_name -> parent_name
                parent = node_name
                child = parent_name

            key = (parent, rel_type, direction)
            if key not in parent_child_map:
                parent_child_map[key] = []
            parent_child_map[key].append((child, labels))

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

    def handle_error(self, error_message: str):
        """
        Handle any errors.

        Args:
            error_message (str): The error message to display.
        """
        QMessageBox.critical(self.ui, "Error", error_message)
