from PyQt6.QtCore import QObject, pyqtSignal, QThread
from neo4j import GraphDatabase


class RelationshipService(QObject):
    """
    Service class to handle relationships between nodes.
    """

    def __init__(self, neo4j_model):
        """
        Initialize the RelationshipService with the Neo4j model.

        Args:
            neo4j_model: The Neo4j model instance.
        """
        super().__init__()
        self.neo4j_model = neo4j_model

    def get_node_relationships(self, node_name, depth, callback):
        """
        Fetch relationships for a given node up to a specified depth.

        Args:
            node_name (str): The name of the node.
            depth (int): The depth of relationships to fetch.
            callback (function): The callback function to handle the results.

        Returns:
            RelationshipWorker: The worker thread to fetch relationships.
        """
        worker = RelationshipWorker(self.neo4j_model, node_name, depth, callback)
        return worker


class RelationshipWorker(QThread):
    """
    Worker thread to fetch relationships for a given node.
    """

    error_occurred = pyqtSignal(str)

    def __init__(self, neo4j_model, node_name, depth, callback):
        """
        Initialize the RelationshipWorker with the Neo4j model, node name, depth, and callback.

        Args:
            neo4j_model: The Neo4j model instance.
            node_name (str): The name of the node.
            depth (int): The depth of relationships to fetch.
            callback (function): The callback function to handle the results.
        """
        super().__init__()
        self.neo4j_model = neo4j_model
        self.node_name = node_name
        self.depth = depth
        self.callback = callback
        self._is_canceled = False

    def run(self):
        """
        Run the worker thread to fetch relationships.
        """
        try:
            with self.neo4j_model.session() as session:
                query = (
                    f"MATCH (n {{name: $node_name}})-[r*1..{self.depth}]-(m) "
                    "RETURN n.name AS node_name, labels(n) AS labels, "
                    "m.name AS parent_name, type(r[0]) AS rel_type, "
                    "CASE WHEN startNode(r[0]).name = n.name THEN '>' ELSE '<' END AS direction"
                )
                result = session.run(query, node_name=self.node_name)
                records = [record.data() for record in result]
                if not self._is_canceled:
                    self.callback(records)
        except Exception as e:
            if not self._is_canceled:
                self.error_occurred.emit(str(e))

    def cancel(self):
        """
        Cancel the worker thread.
        """
        self._is_canceled = True
