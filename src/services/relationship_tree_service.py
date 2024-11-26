import logging
from typing import Dict, List, Tuple, Any

from PyQt6.QtGui import QStandardItemModel


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
