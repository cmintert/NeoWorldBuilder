"""
This module provides worker classes for performing Neo4j database operations in separate threads.
It includes classes for querying, writing, deleting, and generating suggestions for nodes.
"""

import json
import structlog
import traceback
from collections import Counter
from typing import Any, Callable, Dict, List, Optional, Tuple

import pandas as pd
from PyQt6.QtCore import QThread, pyqtSignal
from neo4j import GraphDatabase

logger = structlog.get_logger()

class BaseNeo4jWorker(QThread):
    """
    Base class for Neo4j worker threads.

    Args:
        uri (str): The URI of the Neo4j database.
        auth (tuple): A tuple containing the username and password for authentication.
    """

    error_occurred = pyqtSignal(str)
    progress_updated = pyqtSignal(int)

    def __init__(self, uri: str, auth: Tuple[str, str]) -> None:
        """
        Initialize the worker with Neo4j connection parameters.

        Args:
            uri (str): The URI of the Neo4j database.
            auth (tuple): A tuple containing the username and password for authentication.
        """
        super().__init__()
        self._uri = uri
        self._auth = auth
        self._driver: Optional[GraphDatabase.driver] = None
        self._is_cancelled = False

    def connect(self) -> None:
        """
        Create Neo4j driver connection.
        """
        if not self._driver:
            self._driver = GraphDatabase.driver(self._uri, auth=self._auth)

    def cleanup(self) -> None:
        """
        Clean up resources.
        """
        if self._driver:
            self._driver.close()
            self._driver = None

    def cancel(self) -> None:
        """
        Cancel current operation.
        """
        self._is_cancelled = True
        self.quit()  # Tell thread to quit
        self.wait()

    def run(self) -> None:
        """
        Base run implementation.
        """
        try:
            self.connect()
            self.execute_operation()
        except Exception as e:
            logger.error("Error occurred in BaseNeo4jWorker", exc_info=True, module="BaseNeo4jWorker", function="run")
            self.error_occurred.emit(str(e))
        finally:
            self.cleanup()

    def execute_operation(self) -> None:
        """
        Override in subclasses to execute specific operations.
        """
        raise NotImplementedError


class QueryWorker(BaseNeo4jWorker):
    """
    Worker for read operations.

    Args:
        uri (str): The URI of the Neo4j database.
        auth (tuple): A tuple containing the username and password for authentication.
        query (str): The Cypher query to execute.
        params (dict, optional): Parameters for the query. Defaults to None.
    """

    query_finished = pyqtSignal(list)

    def __init__(
        self,
        uri: str,
        auth: Tuple[str, str],
        query: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Initialize the worker with query parameters.

        Args:
            uri (str): The URI of the Neo4j database.
            auth (tuple): A tuple containing the username and password for authentication.
            query (str): The Cypher query to execute.
            params (dict, optional): Parameters for the query. Defaults to None.
        """
        super().__init__(uri, auth)
        self.query = query
        self.params = params or {}

    def execute_operation(self) -> None:
        """
        Execute the read operation.
        """
        try:
            with self._driver.session() as session:
                result = list(session.run(self.query, self.params))
                if not self._is_cancelled:
                    self.query_finished.emit(result)
        except Exception as e:
            error_message = "".join(
                traceback.format_exception(type(e), e, e.__traceback__)
            )
            logger.error("Error occurred in QueryWorker", exc_info=True, module="QueryWorker", function="execute_operation")
            self.error_occurred.emit(error_message)


class WriteWorker(BaseNeo4jWorker):
    """
    Worker for write operations.

    Args:
        uri (str): The URI of the Neo4j database.
        auth (tuple): A tuple containing the username and password for authentication.
        func (callable): The function to execute in the write transaction.
        *args: Arguments for the function.
    """

    write_finished = pyqtSignal(bool)

    def __init__(
        self, uri: str, auth: Tuple[str, str], func: Callable[..., Any], *args: Any
    ) -> None:
        """
        Initialize the worker with write function and arguments.

        Args:
            uri (str): The URI of the Neo4j database.
            auth (tuple): A tuple containing the username and password for authentication.
            func (callable): The function to execute in the write transaction.
            *args: Arguments for the function.
        """
        super().__init__(uri, auth)
        self.func = func
        self.args = args

    def execute_operation(self) -> None:
        """
        Execute the write operation.
        """
        with self._driver.session() as session:
            session.execute_write(self.func, *self.args)
            if not self._is_cancelled:
                self.write_finished.emit(True)

    @staticmethod
    def _run_transaction(tx: Any, query: str, params: Dict[str, Any]) -> Any:
        """
        Run a transaction with the given query and parameters.

        Args:
            tx: The transaction object.
            query (str): The Cypher query to execute.
            params (dict): Parameters for the query.

        Returns:
            The result of the query.
        """
        return tx.run(query, params)


class DeleteWorker(BaseNeo4jWorker):
    """
    Worker for delete operations.

    Args:
        uri (str): The URI of the Neo4j database.
        auth (tuple): A tuple containing the username and password for authentication.
        func (callable): The function to execute in the delete transaction.
        *args: Arguments for the function.
    """

    delete_finished = pyqtSignal(bool)

    def __init__(
        self, uri: str, auth: Tuple[str, str], func: Callable[..., Any], *args: Any
    ) -> None:
        """
        Initialize the worker with delete function and arguments.

        Args:
            uri (str): The URI of the Neo4j database.
            auth (tuple): A tuple containing the username and password for authentication.
            func (callable): The function to execute in the delete transaction.
            *args: Arguments for the function.
        """
        super().__init__(uri, auth)
        self.func = func
        self.args = args

    def execute_operation(self) -> None:
        """
        Execute the delete operation.
        """
        with self._driver.session() as session:
            session.execute_write(self.func, *self.args)
            if not self._is_cancelled:
                self.delete_finished.emit(True)

    @staticmethod
    def _run_transaction(tx: Any, query: str, params: Dict[str, Any]) -> Any:
        """
        Run a transaction with the given query and parameters.

        Args:
            tx: The transaction object.
            query (str): The Cypher query to execute.
            params (dict): Parameters for the query.

        Returns:
            The result of the query.
        """
        return tx.run(query, params)


class BatchWorker(BaseNeo4jWorker):
    """
    Worker for batch operations.

    Args:
        driver_config (dict): Configuration for the Neo4j driver.
        operations (list): List of operations to execute.
    """

    batch_progress = pyqtSignal(int, int)  # current, total
    batch_finished = pyqtSignal(list)

    def __init__(
        self,
        driver_config: Dict[str, Any],
        operations: List[Tuple[str, Optional[Dict[str, Any]]]],
    ) -> None:
        """
        Initialize the worker with batch operations.

        Args:
            driver_config (dict): Configuration for the Neo4j driver.
            operations (list): List of operations to execute.
        """
        super().__init__(driver_config)
        self.operations = operations

    def execute_operation(self) -> None:
        """
        Execute the batch operations.
        """
        results = []
        total = len(self.operations)

        with self._driver.session() as session:
            for i, (query, params) in enumerate(self.operations, 1):
                if self._is_cancelled:
                    break

                result = session.run(query, params or {})
                results.extend(list(result))
                self.batch_progress.emit(i, total)

        if not self._is_cancelled:
            self.batch_finished.emit(results)


class SuggestionWorker(BaseNeo4jWorker):
    """
    Worker for generating suggestions based on node data.

    Args:
        uri (str): The URI of the Neo4j database.
        auth (tuple): A tuple containing the username and password for authentication.
        node_data (dict): The data of the node for which to generate suggestions.
    """

    suggestions_ready = pyqtSignal(dict)

    def __init__(
        self, uri: str, auth: Tuple[str, str], node_data: Dict[str, Any]
    ) -> None:
        """
        Initialize the worker with node data.

        Args:
            uri (str): The URI of the Neo4j database.
            auth (tuple): A tuple containing the username and password for authentication.
            node_data (dict): The data of the node for which to generate suggestions.
        """
        super().__init__(uri, auth)
        self.node_data = node_data

    def _find_similar_nodes(
        self, session: Any, node_data: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Find similar nodes based on labels, including their relationships.

        Args:
            session: The Neo4j session
            node_data (dict): The data of the node to find similar nodes for

        Returns:
            list: A list of similar nodes with structured properties and relationships
        """
        try:
            logger.debug("Finding similar nodes", module="SuggestionWorker", function="_find_similar_nodes")
            labels = node_data.get("labels", [])
            name = node_data.get("name", "")

            logger.debug(f"Labels: {labels}, Name: {name}", module="SuggestionWorker", function="_find_similar_nodes")

            query = """
            MATCH (n)
            WHERE any(label IN $labels WHERE label IN labels(n))
              AND n.name <> $name
            WITH n, labels(n) as node_labels
            OPTIONAL MATCH (n)-[r]->(target)
            WITH n, node_labels,
                 collect({
                    type: type(r),
                    source: n.name,
                    target: target.name,
                    direction: 'outgoing',
                    properties: properties(r)
                 }) as outRels
            OPTIONAL MATCH (n)<-[r2]-(source)
            WITH n, node_labels, outRels,
                 collect({
                    type: type(r2),
                    source: source.name,
                    target: n.name,
                    direction: 'incoming',
                    properties: properties(r2)
                 }) as inRels
            RETURN {
                properties: properties(n),
                labels: node_labels,
                relationships: outRels + inRels
            } as node_data
            """

            result = session.run(query, labels=labels, name=name)
            similar_nodes = []

            for record in result:
                similar_nodes.append(record["node_data"])

            logger.debug(f"Similar nodes: {similar_nodes}", module="SuggestionWorker", function="_find_similar_nodes")
            return similar_nodes

        except Exception as e:
            logger.error(f"Error finding similar nodes: {str(e)}", exc_info=True, module="SuggestionWorker", function="_find_similar_nodes")
            return []

    def _get_property_suggestions(
        self, df: pd.DataFrame
    ) -> Dict[str, List[Tuple[str, float]]]:
        """
        Generate property suggestions based on frequency from a DataFrame.
        """
        try:
            suggestions = {}
            exclude_props = {
                "name",
                "description",
                "tags",
                "_created",
                "_modified",
                "_author",
            }

            # Extract all properties from DataFrame
            properties_df = pd.json_normalize(df["properties"])
            for column in properties_df.columns:
                if column in exclude_props:
                    continue

                # Count occurrences of each unique value in the property column
                value_counts = properties_df[column].value_counts(dropna=True)
                total = value_counts.sum() or 1  # Avoid division by zero

                # Convert to list of tuples (value, confidence)
                suggestions[column] = [
                    (val, (count / total) * 100) for val, count in value_counts.items()
                ]

            return suggestions

        except Exception as e:
            logger.error(
                f"Error generating property suggestions: {str(e)}", exc_info=True, module="SuggestionWorker", function="_get_property_suggestions"
            )
            return {}

    def _get_tag_suggestions(self, df: pd.DataFrame) -> List[Tuple[str, float]]:
        """
        Generate tag suggestions based on frequency from a DataFrame.
        """
        try:
            all_tags = []
            current_tags = set(self.node_data.get("properties", {}).get("tags", []))

            # Flatten list of tags for all rows
            all_tags = [tag for tags_list in df["tags"].dropna() for tag in tags_list]

            # Count tag occurrences and calculate confidence
            tag_counts = Counter(all_tags)
            total = sum(tag_counts.values()) or 1  # Avoid division by zero

            suggestions = [
                (tag, (count / total) * 100)
                for tag, count in tag_counts.items()
                if tag not in current_tags
            ]
            return suggestions[:5]  # Limit to top 5 suggestions

        except Exception as e:
            logger.error(f"Error generating tag suggestions: {str(e)}", exc_info=True, module="SuggestionWorker", function="_get_tag_suggestions")
            return []

    def _get_relationship_suggestions(
        self, df: pd.DataFrame
    ) -> List[Tuple[str, str, str, Dict[str, Any], float]]:
        """
        Generate relationship suggestions, including relationship properties, based on a DataFrame.
        """
        try:
            outgoing_rels = []
            incoming_rels = []

            # Flatten and classify relationships by direction
            for rel_list in df["relationships"].dropna():
                for rel in rel_list:
                    rel_type = rel["type"]
                    target = rel["target"]
                    direction = rel["direction"]
                    properties = rel.get("properties", {})

                    if direction == "outgoing":
                        outgoing_rels.append(
                            (rel_type, target, direction, frozenset(properties.items()))
                        )
                    elif direction == "incoming":
                        incoming_rels.append(
                            (rel_type, target, direction, frozenset(properties.items()))
                        )

            # Count and calculate confidence scores
            out_counts = Counter(outgoing_rels)
            in_counts = Counter(incoming_rels)

            total_out = sum(out_counts.values()) or 1
            total_in = sum(in_counts.values()) or 1

            # Generate top 3 suggestions per direction with confidence scores
            suggestions = [
                (rel_type, target, direction, dict(props), (count / total_out) * 100)
                for (
                    rel_type,
                    target,
                    direction,
                    props,
                ), count in out_counts.most_common(3)
            ] + [
                (rel_type, target, direction, dict(props), (count / total_in) * 100)
                for (
                    rel_type,
                    target,
                    direction,
                    props,
                ), count in in_counts.most_common(3)
            ]

            suggestions.sort(key=lambda x: x[4], reverse=True)
            return suggestions[:5]  # Limit to top 5 suggestions

        except Exception as e:
            logger.error(
                f"Error generating relationship suggestions: {str(e)}", exc_info=True, module="SuggestionWorker", function="_get_relationship_suggestions"
            )
            return []

    def execute_operation(self) -> None:
        try:
            logger.info("Starting suggestion generation process", module="SuggestionWorker", function="execute_operation")

            with self._driver.session() as session:
                similar_nodes = self._find_similar_nodes(session, self.node_data)

                if not similar_nodes:
                    logger.info("No similar nodes found", module="SuggestionWorker", function="execute_operation")
                    suggestions = {"tags": [], "properties": {}, "relationships": []}
                    self.suggestions_ready.emit(suggestions)
                    return

                # Create structured DataFrame
                df = pd.DataFrame(
                    {
                        "node_id": [i for i, _ in enumerate(similar_nodes)],
                        "properties": [node["properties"] for node in similar_nodes],
                        "labels": [node["labels"] for node in similar_nodes],
                        "relationships": [
                            node["relationships"] for node in similar_nodes
                        ],
                        # Extract common properties for direct access if needed
                        "name": [
                            node["properties"].get("name") for node in similar_nodes
                        ],
                        "tags": [
                            node["properties"].get("tags", []) for node in similar_nodes
                        ],
                    }
                )

                logger.debug(f"Created DataFrame with columns: {df.columns.tolist()}", module="SuggestionWorker", function="execute_operation")
                logger.debug(f"DataFrame content:\n{df}", module="SuggestionWorker", function="execute_operation")

                # Example of the DataFrame:
                """
                   node_id  properties                  labels        relationships     name     tags
                0  0       {'name': 'Saruman', ...}    [Character]   [{type: ...}]    Saruman  [wizard, ...]
                1  1       {'name': 'Gandalf', ...}    [Character]   [{type: ...}]    Gandalf  [wizard, ...]
                """

                # Generate suggestions
                suggestions = {
                    "tags": self._get_tag_suggestions(df),
                    "properties": self._get_property_suggestions(df),
                    "relationships": self._get_relationship_suggestions(df),
                }

                logger.debug(
                    f"Generated suggestions: {json.dumps(suggestions, indent=2)}", module="SuggestionWorker", function="execute_operation"
                )
                self.suggestions_ready.emit(suggestions)
                logger.info("Suggestion generation completed successfully", module="SuggestionWorker", function="execute_operation")

        except Exception as e:
            error_message = f"Error generating suggestions: {str(e)}"
            logger.error(error_message, exc_info=True, module="SuggestionWorker", function="execute_operation")
            self.error_occurred.emit(error_message)
