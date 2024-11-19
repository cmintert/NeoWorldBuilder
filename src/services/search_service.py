from typing import Callable
from core.neo4jmodel import Neo4jModel
from core.neo4jworkers import QueryWorker


class SearchService:
    """
    Service class to handle search functionality.
    """

    def __init__(self, model: Neo4jModel):
        """
        Initialize the SearchService with the Neo4jModel.

        Args:
            model (Neo4jModel): The Neo4jModel instance.
        """
        self.model = model

    def fetch_matching_node_names(self, prefix: str, limit: int, callback: Callable) -> QueryWorker:
        """
        Search for nodes whose names match a given prefix using a worker.

        Args:
            prefix (str): The search prefix.
            limit (int): Maximum number of results to return.
            callback (function): Function to call with the result.

        Returns:
            QueryWorker: A worker that will execute the query.
        """
        return self.model.fetch_matching_node_names(prefix, limit, callback)
