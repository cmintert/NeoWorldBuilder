import json
import logging
import traceback
from collections import Counter

import pandas as pd
from PyQt6.QtCore import QThread, pyqtSignal
from neo4j import GraphDatabase


class BaseNeo4jWorker(QThread):
    """Base class for Neo4j worker threads"""

    error_occurred = pyqtSignal(str)
    progress_updated = pyqtSignal(int)

    def __init__(self, uri, auth):
        """
        Initialize the worker with Neo4j connection parameters.

        Args:
            uri (str): The URI of the Neo4j database.
            auth (tuple): A tuple containing the username and password for authentication.
        """
        super().__init__()
        self._uri = uri
        self._auth = auth
        self._driver = None
        self._is_cancelled = False

    def connect(self):
        """
        Create Neo4j driver connection.
        """
        if not self._driver:
            self._driver = GraphDatabase.driver(self._uri, auth=self._auth)

    def cleanup(self):
        """
        Clean up resources.
        """
        if self._driver:
            self._driver.close()
            self._driver = None

    def cancel(self):
        """
        Cancel current operation.
        """
        self._is_cancelled = True
        self.quit()  # Tell thread to quit
        self.wait()

    def run(self):
        """
        Base run implementation.
        """
        try:
            self.connect()
            self.execute_operation()
        except Exception as e:
            self.error_occurred.emit(str(e))
        finally:
            self.cleanup()

    def execute_operation(self):
        """
        Override in subclasses to execute specific operations.
        """
        raise NotImplementedError


class QueryWorker(BaseNeo4jWorker):
    """Worker for read operations"""

    query_finished = pyqtSignal(list)

    def __init__(self, uri, auth, query, params=None):
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

    def execute_operation(self):
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
            self.error_occurred.emit(error_message)


class WriteWorker(BaseNeo4jWorker):
    """Worker for write operations"""

    write_finished = pyqtSignal(bool)

    def __init__(self, uri, auth, func, *args):
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

    def execute_operation(self):
        """
        Execute the write operation.
        """
        with self._driver.session() as session:
            session.execute_write(self.func, *self.args)
            if not self._is_cancelled:
                self.write_finished.emit(True)

    @staticmethod
    def _run_transaction(tx, query, params):
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
    """Worker for delete operations"""

    delete_finished = pyqtSignal(bool)

    def __init__(self, uri, auth, func, *args):
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

    def execute_operation(self):
        """
        Execute the delete operation.
        """
        with self._driver.session() as session:
            session.execute_write(self.func, *self.args)
            if not self._is_cancelled:
                self.delete_finished.emit(True)

    @staticmethod
    def _run_transaction(tx, query, params):
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
    """Worker for batch operations"""

    batch_progress = pyqtSignal(int, int)  # current, total
    batch_finished = pyqtSignal(list)

    def __init__(self, driver_config, operations):
        """
        Initialize the worker with batch operations.

        Args:
            driver_config (dict): Configuration for the Neo4j driver.
            operations (list): List of operations to execute.
        """
        super().__init__(driver_config)
        self.operations = operations

    def execute_operation(self):
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
    suggestions_ready = pyqtSignal(dict)

    def __init__(self, uri, auth, node_data):
        super().__init__(uri, auth)
        self.node_data = node_data
        logging.basicConfig(level=logging.DEBUG)

    def _find_similar_nodes(self, session, node_data):
        """Simple node finder based on labels."""
        try:
            logging.debug("Finding similar nodes")
            labels = node_data.get("labels", [])
            name = node_data.get("name", "")

            # Just get nodes with same label, excluding self
            query = """
            MATCH (n)
            WHERE any(label IN $labels WHERE label IN labels(n))
            AND n.name <> $name
            RETURN n
            """
            result = session.run(query, labels=labels, name=name)
            similar_nodes = [record["n"] for record in result]
            logging.debug("Found similar nodes with full properties:")
            for node in similar_nodes:
                logging.debug(f"Node Properties: {dict(node)}")
            return similar_nodes

        except Exception as e:
            logging.error(f"Error finding similar nodes: {str(e)}", exc_info=True)
            return []

    def _get_tag_suggestions(self, df):
        """Simple tag frequency-based suggestions."""
        logging.debug("Generating tag suggestions")
        try:
            all_tags = []
            current_tags = set(self.node_data.get("tags", []))

            # Collect all tags from similar nodes
            for tags in df["tags"]:
                if isinstance(tags, list):
                    all_tags.extend(tags)

            # Count tag frequencies
            tag_counts = Counter(all_tags)

            # Convert to suggestions with confidence scores
            suggestions = []
            total_occurrences = sum(tag_counts.values())

            for tag, count in tag_counts.most_common():
                # Skip if tag is already in current node
                if tag in current_tags:
                    continue

                # Simple confidence calculation: (count / total) * 100
                confidence = (count / total_occurrences) * 100
                suggestions.append((tag, confidence))

                if len(suggestions) >= 5:  # Limit to top 5 suggestions
                    break

            logging.debug(f"Tag suggestions: {suggestions}")
            return suggestions

        except Exception as e:
            logging.error(f"Error generating tag suggestions: {str(e)}", exc_info=True)
            return []

    def _get_property_suggestions(self, df):
        """Property value frequency-based suggestions."""
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

            logging.debug(f"DataFrame raw content before property suggestions:\n{df}")

            # Get properties directly from the Neo4j node data
            for column in df.columns:
                if column in exclude_props or column.startswith("_"):
                    continue

                value_counts = df[column].value_counts()
                total = len(df[column].dropna())  # Only count non-null values

                if total == 0:
                    continue

                prop_suggestions = []
                for value, count in value_counts.items():
                    if pd.isna(value):  # Skip null values
                        continue
                    confidence = (count / total) * 100
                    prop_suggestions.append((str(value), confidence))

                if prop_suggestions:
                    suggestions[column] = prop_suggestions
                    logging.debug(
                        f"Found suggestions for property {column}: {prop_suggestions}"
                    )

            logging.debug(f"Final property suggestions: {suggestions}")
            return suggestions

        except Exception as e:
            logging.error(
                f"Error generating property suggestions: {str(e)}", exc_info=True
            )
            return {}

    def execute_operation(self):
        """Execute the simplified suggestion generation."""
        try:
            logging.info("Starting suggestion generation process")

            with self._driver.session() as session:
                similar_nodes = self._find_similar_nodes(session, self.node_data)

                if not similar_nodes:
                    logging.info("No similar nodes found")
                    suggestions = {"tags": [], "properties": {}, "relationships": []}
                    self.suggestions_ready.emit(suggestions)
                    return

                # Convert Neo4j nodes to dictionaries
                node_data_list = []
                for node in similar_nodes:
                    # Get all properties as a dict using Neo4j's dict() conversion
                    # This ensures we get ALL properties, not just the standard ones
                    properties = dict(node)
                    # Convert Neo4j types to Python native types where needed
                    properties["tags"] = list(properties.get("tags", []))
                    node_data_list.append(properties)

                # Create DataFrame from full property dictionaries
                df = pd.DataFrame.from_records(node_data_list)

                logging.debug(f"Created DataFrame with columns: {df.columns.tolist()}")
                logging.debug(f"DataFrame content:\n{df}")

                # Generate suggestions
                suggestions = {
                    "tags": self._get_tag_suggestions(df),
                    "properties": self._get_property_suggestions(df),
                    "relationships": [],  # Simplified version skips relationships
                }

                logging.debug(
                    f"Generated suggestions: {json.dumps(suggestions, indent=2)}"
                )
                self.suggestions_ready.emit(suggestions)
                logging.info("Suggestion generation completed successfully")

        except Exception as e:
            error_message = f"Error generating suggestions: {str(e)}"
            logging.error(error_message, exc_info=True)
            self.error_occurred.emit(error_message)
