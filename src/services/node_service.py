from typing import Dict, Any, Callable
from core.neo4jmodel import Neo4jModel
from core.neo4jworkers import QueryWorker, WriteWorker, DeleteWorker


class NodeService:
    """
    Service class to handle node-related operations such as loading, saving, and deleting nodes.
    """

    def __init__(self, model: Neo4jModel):
        """
        Initialize the NodeService with the Neo4jModel.

        Args:
            model (Neo4jModel): The Neo4jModel instance.
        """
        self.model = model

    def load_node(self, name: str, callback: Callable) -> QueryWorker:
        """
        Load a node and its relationships by name using a worker.

        Args:
            name (str): Name of the node to load.
            callback (function): Function to call with the result.

        Returns:
            QueryWorker: A worker that will execute the query.
        """
        return self.model.load_node(name, callback)

    def save_node(self, node_data: Dict[str, Any], callback: Callable) -> WriteWorker:
        """
        Save or update a node and its relationships using a worker.

        Args:
            node_data (dict): Node data including properties and relationships.
            callback (function): Function to call when done.

        Returns:
            WriteWorker: A worker that will execute the write operation.
        """
        return self.model.save_node(node_data, callback)

    def delete_node(self, name: str, callback: Callable) -> DeleteWorker:
        """
        Delete a node and all its relationships using a worker.

        Args:
            name (str): Name of the node to delete.
            callback (function): Function to call when done.

        Returns:
            DeleteWorker: A worker that will execute the delete operation.
        """
        return self.model.delete_node(name, callback)

    def get_last_modified_node(self) -> Dict[str, Any]:
        """
        Fetch the last modified node based on the '_modified' property.

        Returns:
            dict: The last modified node data or None if no nodes exist.
        """
        return self.model.get_last_modified_node()
