import logging
from typing import Dict, List, Tuple, Any

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QStandardItemModel, QStandardItem


class RelationshipTreeService:
    """Service for managing the relationship tree visualization and data."""

    def __init__(self, tree_model: QStandardItemModel, header: str):
        self.tree_model = tree_model
        self.header = header

    def process_relationship_records(
        self, records: List[Any]
    ) -> Tuple[Dict[Tuple[str, str, str], List[Tuple[str, List[str]]]], int]:
        """
        Process relationship records and build parent-child map.

        Args:
            records: List of relationship records from the database

        Returns:
            Tuple containing:
            - Dictionary mapping parent names to child nodes with relationship details
            - Count of skipped records
        """
        parent_child_map = {}
        skipped_records = 0

        for record in records:
            node_name = record.get("node_name")
            labels = record.get("labels", [])
            parent_name = record.get("parent_name")
            rel_type = record.get("rel_type")
            direction = record.get("direction")

            if not all([node_name, parent_name, rel_type, direction]):
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
        Handle cycles in the tree to prevent infinite loops.

        Args:
            parent_item (QStandardItem): The parent item.
            rel_type (str): Relationship type.
            direction (str): Relationship direction.
            child_name (str): The child node involved in the cycle.
        """
        cycle_item = QStandardItem(f"🔁 Cycle: {child_name} ({rel_type}) [{direction}]")
        parent_item.appendRow(cycle_item)
