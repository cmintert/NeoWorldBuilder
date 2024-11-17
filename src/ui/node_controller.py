from PyQt6.QtCore import QObject, pyqtSlot
from PyQt6.QtWidgets import QMessageBox

from core.neo4jmodel import Neo4jModel
from core.neo4jworkers import QueryWorker, WriteWorker, DeleteWorker
from config.config import Config


class NodeController(QObject):
    """
    Controller class to handle node-related operations such as loading, saving, and deleting nodes.
    """

    def __init__(self, model: Neo4jModel, config: Config):
        """
        Initialize the NodeController with the Neo4j model and configuration.

        Args:
            model (Neo4jModel): The Neo4j model instance.
            config (Config): The configuration instance.
        """
        super().__init__()
        self.model = model
        self.config = config
        self.current_load_worker = None
        self.current_save_worker = None
        self.current_delete_worker = None

    def load_node_data(self, name: str, callback: callable):
        """
        Load node data using worker thread.

        Args:
            name (str): Name of the node to load.
            callback (callable): Function to call with the result.
        """
        if not name:
            return

        # Cancel any existing load operation
        if self.current_load_worker:
            self.current_load_worker.cancel()
            self.current_load_worker.wait()

        # Start new load operation
        self.current_load_worker = self.model.load_node(name, callback)
        self.current_load_worker.error_occurred.connect(self.handle_error)
        self.current_load_worker.start()

    def save_node(self, node_data: dict, callback: callable):
        """
        Save node data using worker thread.

        Args:
            node_data (dict): Node data including properties and relationships.
            callback (callable): Function to call when done.
        """
        if not node_data:
            return

        # Cancel any existing save operation
        if self.current_save_worker:
            self.current_save_worker.cancel()

        # Start new save operation
        self.current_save_worker = self.model.save_node(node_data, callback)
        self.current_save_worker.error_occurred.connect(self.handle_error)
        self.current_save_worker.start()

    def delete_node(self, name: str, callback: callable):
        """
        Delete node using worker thread.

        Args:
            name (str): Name of the node to delete.
            callback (callable): Function to call when done.
        """
        if not name:
            return

        reply = QMessageBox.question(
            None,
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
            self.current_delete_worker = self.model.delete_node(name, callback)
            self.current_delete_worker.error_occurred.connect(self.handle_error)
            self.current_delete_worker.start()

    def handle_error(self, error_message: str):
        """
        Handle any errors.

        Args:
            error_message (str): The error message to display.
        """
        QMessageBox.critical(None, "Error", error_message)
