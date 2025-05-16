from abc import abstractmethod
from typing import List, Optional, Dict, Any

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QStandardItem
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
