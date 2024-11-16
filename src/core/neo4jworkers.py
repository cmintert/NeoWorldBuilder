"""
This module provides worker classes for performing Neo4j database operations in separate threads.
It includes classes for querying, writing, deleting, and generating suggestions for nodes.
"""

import traceback
from typing import Any, Callable, Dict, List, Optional, Tuple

import pandas as pd
import structlog
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
            logger.error(
                "Error occurred in BaseNeo4jWorker",
                exc_info=True,
                module="BaseNeo4jWorker",
                function="run",
            )
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
            logger.error(
                "Error occurred in QueryWorker",
                exc_info=True,
                module="QueryWorker",
                function="execute_operation",
            )
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

    #####  The following methods are used to fetch data from the Neo4j database  #####

    def fetch_data(
        self,
    ) -> Tuple[
        Dict[str, pd.DataFrame], Dict[str, pd.DataFrame], Dict[str, pd.DataFrame]
    ]:

        # Fetch full data (cached), label-based data, and self node data
        full_data = self._fetch_full_data()
        label_based = self._fetch_label_based_data()
        self_node = self._fetch_self_node_data()

        logger.info("Creating pd_full_data")
        pd_full_data = self._create_dataframes_from_data(full_data)
        logger.info("Creating pd_label_based")
        pd_label_based = self._create_dataframes_from_data(label_based)
        logger.info("Creating pd_self_node")
        pd_self_node = self._create_dataframes_from_data([self_node])

        return pd_full_data, pd_label_based, pd_self_node

    def _create_dataframes_from_data(
        self, nodes_data: List[Dict[str, Any]]
    ) -> Dict[str, pd.DataFrame]:
        # Define expected columns
        nodes_columns = ["name"]
        properties_columns = ["node_name", "property", "value"]
        tags_columns = ["node_name", "tag"]
        labels_columns = ["node_name", "label"]
        relationships_columns = [
            "id",
            "source_name",
            "target_name",
            "relationship_type",
            "direction",
        ]
        rel_properties_columns = ["relationship_id", "property", "value"]

        # Initialize record lists
        nodes_list = []
        properties_records = []
        tags_records = []
        labels_records = []
        relationships_records = []
        rel_properties_records = []
        node_names = set()

        if not nodes_data:
            logger.info("No node data provided. Returning empty DataFrames.")
            return {
                "nodes": pd.DataFrame(columns=nodes_columns),
                "properties": pd.DataFrame(columns=properties_columns),
                "tags": pd.DataFrame(columns=tags_columns),
                "labels": pd.DataFrame(columns=labels_columns),
                "relationships": pd.DataFrame(columns=relationships_columns),
                "relationship_properties": pd.DataFrame(columns=rel_properties_columns),
            }

        for node in nodes_data:
            node_name = node.get("name")
            if not node_name:
                logger.warning("Encountered a node without a 'name'. Skipping.")
                continue  # Skip nodes without a name
            if node_name in node_names:
                logger.debug(
                    f"Duplicate node '{node_name}' found. Skipping addition to nodes_list."
                )
                continue  # Avoid duplicate nodes
            node_names.add(node_name)
            nodes_list.append({"name": node_name})

            # Properties
            properties = node.get("properties", {})
            if isinstance(properties, dict):
                for key, value in properties.items():
                    properties_records.append(
                        {
                            "node_name": node_name,
                            "property": key,
                            "value": value,
                        }
                    )
            else:
                logger.warning(
                    f"Properties for node '{node_name}' are not a dict. Skipping properties."
                )

            # Tags
            tags = node.get("tags", [])
            if isinstance(tags, list):
                for tag in tags:
                    tags_records.append(
                        {
                            "node_name": node_name,
                            "tag": tag,
                        }
                    )
            else:
                logger.warning(
                    f"Tags for node '{node_name}' are not a list. Skipping tags."
                )

            # Labels
            labels = node.get("labels", [])
            if isinstance(labels, list):
                for label in labels:
                    labels_records.append(
                        {
                            "node_name": node_name,
                            "label": label,
                        }
                    )
            else:
                logger.warning(
                    f"Labels for node '{node_name}' are not a list. Skipping labels."
                )

        # Process relationships
        relationship_id_counter = 0

        for node in nodes_data:
            source_name = node.get("name")
            if not source_name:
                continue  # Already handled

            relationships = node.get("relationships", [])
            if not isinstance(relationships, list):
                logger.warning(
                    f"Relationships for node '{source_name}' are not a list. Skipping relationships."
                )
                continue

            for rel in relationships:
                relationship_type = rel.get("relationship")
                target_name = rel.get("target")
                direction = rel.get(
                    "direction", "UNKNOWN"
                )  # Default direction if missing
                properties = rel.get("properties", {})

                if not relationship_type or not target_name:
                    logger.warning(
                        f"Incomplete relationship in node '{source_name}': {rel}. Skipping."
                    )
                    continue

                if not isinstance(properties, dict):
                    logger.warning(
                        f"Properties for relationship '{relationship_type}' in node '{source_name}' are not a dict. Skipping properties."
                    )
                    properties = {}

                if target_name not in node_names:
                    # Add missing target node
                    nodes_list.append({"name": target_name})
                    node_names.add(target_name)
                    logger.debug(
                        f"Added missing target node '{target_name}' from relationship."
                    )

                relationship_id = relationship_id_counter
                relationship_id_counter += 1

                # Add relationship record
                relationships_records.append(
                    {
                        "id": relationship_id,
                        "source_name": source_name,
                        "target_name": target_name,
                        "relationship_type": relationship_type,
                        "direction": direction,
                    }
                )

                # Add relationship properties
                for prop_key, prop_value in properties.items():
                    rel_properties_records.append(
                        {
                            "relationship_id": relationship_id,
                            "property": prop_key,
                            "value": prop_value,
                        }
                    )

        # Create DataFrames with predefined columns
        nodes_df = pd.DataFrame(nodes_list, columns=nodes_columns).drop_duplicates(
            subset=["name"]
        )
        properties_df = pd.DataFrame(properties_records, columns=properties_columns)
        tags_df = pd.DataFrame(tags_records, columns=tags_columns)
        labels_df = pd.DataFrame(labels_records, columns=labels_columns)
        relationships_df = pd.DataFrame(
            relationships_records, columns=relationships_columns
        )
        rel_properties_df = pd.DataFrame(
            rel_properties_records, columns=rel_properties_columns
        )

        logger.debug(f"Nodes DataFrame:\n{nodes_df}")
        logger.debug(f"Properties DataFrame:\n{properties_df}")
        logger.debug(f"Tags DataFrame:\n{tags_df}")
        logger.debug(f"Labels DataFrame:\n{labels_df}")
        logger.debug(f"Relationships DataFrame:\n{relationships_df}")
        logger.debug(f"Relationship Properties DataFrame:\n{rel_properties_df}")

        return {
            "nodes": nodes_df,
            "properties": properties_df,
            "tags": tags_df,
            "labels": labels_df,
            "relationships": relationships_df,
            "relationship_properties": rel_properties_df,
        }

    def _fetch_self_node_data(self) -> Dict[str, Any]:
        """Fetch data for the active node from the database."""
        logger.debug("Fetching data for the active node from the database")
        query = """
                MATCH (n)
                WHERE n.name = $node_name
                OPTIONAL MATCH (n)-[r]->(m)
                OPTIONAL MATCH (n)<-[r_in]-(m_in)
                RETURN n,
                       COLLECT(DISTINCT {
                           relationship: type(r),
                           target: m.name,
                           properties: properties(r),
                           direction: 'OUTGOING'
                       }) +
                       COLLECT(DISTINCT {
                           relationship: type(r_in),
                           target: m_in.name,
                           properties: properties(r_in),
                           direction: 'INCOMING'
                       }) AS relationships
        """
        params = {"node_name": self.node_data.get("name")}

        with self._driver.session() as session:
            result = session.run(query, params).single()
            if result:
                node = result["n"]
                relationships = [
                    {
                        "relationship": rel["relationship"],
                        "target": rel["target"],
                        "properties": rel["properties"],
                        "direction": rel["direction"],
                    }
                    for rel in result["relationships"]
                ]
                node_data = {
                    "name": node["name"],
                    "tags": node.get("tags", []),
                    "labels": list(node.labels),
                    "properties": dict(node),
                    "relationships": relationships,
                }
                logger.debug(f"Fetched active node data: {node_data}")
                return node_data
        return {}

    def _fetch_label_based_data(self) -> List[Dict[str, Any]]:
        """Fetch data for nodes sharing the same label."""
        logger.debug("Fetching data for nodes sharing the same label")
        labels = self.node_data["labels"]
        query = """
                MATCH (n)
                WHERE ANY(label IN $node_labels WHERE label IN labels(n))
                OPTIONAL MATCH (n)-[r]->(m)
                OPTIONAL MATCH (n)<-[r_in]-(m_in)
                RETURN n,
                       COLLECT(DISTINCT {
                           relationship: type(r),
                           target: m.name,
                           properties: properties(r),
                           direction: 'OUTGOING'
                       }) +
                       COLLECT(DISTINCT {
                           relationship: type(r_in),
                           target: m_in.name,
                           properties: properties(r_in),
                           direction: 'INCOMING'
                       }) AS relationships
                """
        params = {"node_labels": labels}

        nodes_data = []
        with self._driver.session() as session:
            results = session.run(query, params)
            for result in results:
                node = result["n"]
                relationships = [
                    {
                        "relationship": rel["relationship"],
                        "target": rel["target"],
                        "properties": rel["properties"],
                        "direction": rel["direction"],
                    }
                    for rel in result["relationships"]
                ]
                node_data = {
                    "name": node["name"],
                    "tags": node.get("tags", []),
                    "labels": list(node.labels),
                    "properties": dict(node),
                    "relationships": relationships,
                }
                nodes_data.append(node_data)
        logger.debug(f"Fetched label-based node data: {nodes_data}")
        return nodes_data

    def _fetch_full_data(self) -> List[Dict[str, Any]]:
        """Fetch data for all nodes in the database."""
        logger.debug("Fetching data for all nodes in the database")
        query = """
                MATCH (n)
                OPTIONAL MATCH (n)-[r]->(m)
                OPTIONAL MATCH (n)<-[r_in]-(m_in)
                RETURN n,
                       COLLECT(DISTINCT {
                           relationship: type(r),
                           target: m.name,
                           properties: properties(r),
                           direction: 'OUTGOING'
                       }) +
                       COLLECT(DISTINCT {
                           relationship: type(r_in),
                           target: m_in.name,
                           properties: properties(r_in),
                           direction: 'INCOMING'
                       }) AS relationships
        """

        nodes_data = []
        with self._driver.session() as session:
            results = session.run(query)
            for result in results:
                node = result["n"]
                relationships = [
                    {
                        "relationship": rel["relationship"],
                        "target": rel["target"],
                        "properties": rel["properties"],
                        "direction": rel["direction"],
                    }
                    for rel in result["relationships"]
                ]
                node_data = {
                    "name": node["name"],
                    "tags": node.get("tags", []),
                    "labels": list(node.labels),
                    "properties": dict(node),
                    "relationships": relationships,
                }
                nodes_data.append(node_data)
        logger.debug(f"Fetched full node data: {nodes_data}")
        return nodes_data

    def _format_data(self, result, source="unknown"):
        pass

    #####  The following methods are used to generate suggestions based on the fetched data  #####

    import pandas as pd
    import logging
    from typing import Dict, Any

    # Configure logging
    logger = logging.getLogger(__name__)
    logging.basicConfig(level=logging.DEBUG)

    def suggest_properties(
        self,
        self_node_pd: Dict[str, pd.DataFrame],
        label_based_pd: Dict[str, pd.DataFrame],
        top_n: int = 10,
    ) -> Dict[str, Any]:
        """
        Suggest properties to add to the active node based on label-based data.

        Args:
            self_node_pd (Dict[str, pd.DataFrame]): DataFrames related to the active node.
            label_based_pd (Dict[str, pd.DataFrame]): DataFrames related to nodes sharing the same labels.
            top_n (int): Maximum number of properties to suggest.

        Returns:
            Dict[str, Any]: Dictionary containing suggested properties with their common values and confidence levels.
        """
        logger.debug("Starting suggest_properties method.")

        # Validate presence of 'properties' DataFrame in self_node_pd
        if "properties" not in self_node_pd:
            logger.error("Active node data is missing 'properties' DataFrame.")
            return {"properties": {}}
        if (
            "property" not in self_node_pd["properties"].columns
            or "value" not in self_node_pd["properties"].columns
        ):
            logger.error(
                "Active node 'properties' DataFrame lacks 'property' or 'value' columns."
            )
            return {"properties": {}}

        # Validate presence of 'properties' DataFrame in label_based_pd
        if "properties" not in label_based_pd:
            logger.error("Label-based data is missing 'properties' DataFrame.")
            return {"properties": {}}
        if (
            "property" not in label_based_pd["properties"].columns
            or "value" not in label_based_pd["properties"].columns
        ):
            logger.error(
                "Label-based 'properties' DataFrame lacks 'property' or 'value' columns."
            )
            return {"properties": {}}

        # Extract properties present in the active node
        try:
            active_properties = set(
                self_node_pd["properties"]["property"].dropna().unique().tolist()
            )
            logger.debug(f"Active node properties: {active_properties}")
        except KeyError as e:
            logger.error(
                f"Error accessing 'property' in self_node_pd['properties']: {e}"
            )
            return {"properties": {}}

        # Extract label-based properties excluding those already present in the active node
        label_properties = label_based_pd["properties"]
        filtered_label_properties = label_properties[
            ~label_properties["property"].isin(active_properties)
        ]
        logger.debug(
            f"Filtered label-based properties count: {filtered_label_properties.shape[0]}"
        )

        if filtered_label_properties.empty:
            logger.info(
                "No new properties to suggest after filtering existing properties."
            )
            return {"properties": {}}

        # Calculate property frequencies
        property_counts = (
            filtered_label_properties.groupby("property")["value"]
            .agg(["count", lambda x: x.mode().iloc[0] if not x.mode().empty else None])
            .reset_index()
        )
        property_counts.rename(columns={"<lambda_0>": "common_value"}, inplace=True)
        logger.debug(f"Property counts:\n{property_counts.head()}")

        # Calculate total number of nodes sharing the same label
        try:
            total_nodes = label_based_pd["nodes"]["name"].nunique()
            logger.debug(f"Total nodes sharing the label: {total_nodes}")
        except KeyError as e:
            logger.error(
                f"Error accessing 'nodes' DataFrame or 'name' column in label_based_pd: {e}"
            )
            return {"properties": {}}

        if total_nodes == 0:
            logger.warning(
                "No nodes found in label-based data. Cannot compute confidence levels."
            )
            return {"properties": {}}

        # Calculate confidence levels
        property_counts["confidence"] = (property_counts["count"] / total_nodes) * 100
        logger.debug(f"Property counts with confidence:\n{property_counts.head()}")

        # Sort properties by confidence descending and take top N
        top_properties = property_counts.sort_values(
            by="confidence", ascending=False
        ).head(top_n)
        logger.debug(f"Top {top_n} properties:\n{top_properties}")

        # Prepare the suggestions dictionary
        suggestions = {
            row["property"]: [(row["common_value"], round(row["confidence"], 2))]
            for _, row in top_properties.iterrows()
            if pd.notna(row["common_value"])  # Ensure common_value is not NaN
        }

        logger.debug(f"Generated property suggestions: {suggestions}")

        return suggestions

    def suggest_tags(
        self,
        self_node_pd: Dict[str, pd.DataFrame],
        label_based_pd: Dict[str, pd.DataFrame],
        top_n: int = 10,
    ) -> List[Tuple[str, float]]:
        """
        Suggest tags to add to the active node based on label-based data.

        Args:
            self_node_pd (Dict[str, pd.DataFrame]): DataFrames related to the active node.
            label_based_pd (Dict[str, pd.DataFrame]): DataFrames related to nodes sharing the same labels.
            top_n (int): Maximum number of tags to suggest.

        Returns:
            List[Tuple[str, float]]: List of suggested tags and their confidence levels.
        """
        logger.debug("Starting suggest_tags method.")

        # Validate presence of 'tags' DataFrame in both self_node_pd and label_based_pd
        if "tags" not in self_node_pd or "tags" not in label_based_pd:
            logger.error("Tags DataFrame missing in the provided data.")
            return []

        # Extract existing tags in the active node
        active_tags = set(self_node_pd["tags"]["tag"].dropna().unique())
        logger.debug(f"Active node tags: {active_tags}")

        # Extract label-based tags, excluding those already present in the active node
        label_tags = label_based_pd["tags"]
        filtered_label_tags = label_tags[~label_tags["tag"].isin(active_tags)]
        logger.debug(f"Filtered label-based tags count: {filtered_label_tags.shape[0]}")

        if filtered_label_tags.empty:
            logger.info("No new tags to suggest after filtering existing tags.")
            return []

        # Calculate tag frequencies
        tag_counts = filtered_label_tags["tag"].value_counts().reset_index()
        tag_counts.columns = ["tag", "count"]

        # Calculate total number of nodes sharing the same label
        total_nodes = label_based_pd["nodes"]["name"].nunique()
        logger.debug(f"Total nodes sharing the label: {total_nodes}")

        if total_nodes == 0:
            logger.warning(
                "No nodes found in label-based data. Cannot compute confidence levels."
            )
            return []

        # Calculate confidence levels
        tag_counts["confidence"] = (tag_counts["count"] / total_nodes) * 100
        logger.debug(f"Tag counts with confidence:\n{tag_counts.head()}")

        # Sort tags by confidence descending and take top N
        top_tags = tag_counts.sort_values(by="confidence", ascending=False).head(top_n)

        # Prepare the suggestions list
        suggestions = [
            (row["tag"], round(row["confidence"], 2)) for _, row in top_tags.iterrows()
        ]

        logger.debug(f"Generated tag suggestions: {suggestions}")
        return suggestions

    def suggest_relationships(
        self,
        self_node_pd: Dict[str, pd.DataFrame],
        label_based_pd: Dict[str, pd.DataFrame],
        top_n: int = 10,
    ) -> List[Tuple[str, str, str, Dict[str, Any], float]]:
        """
        Suggest relationships to add to the active node based on label-based data.

        Args:
            self_node_pd (Dict[str, pd.DataFrame]): DataFrames related to the active node.
            label_based_pd (Dict[str, pd.DataFrame]): DataFrames related to nodes sharing the same labels.
            top_n (int): Maximum number of relationships to suggest.

        Returns:
            List[Tuple[str, str, str, Dict[str, Any], float]]:
                List of tuples containing:
                - relationship type (str)
                - target node name (str)
                - direction (str)
                - properties (dict)
                - confidence level (float)
        """
        logger.debug("Starting suggest_relationships method.")

        # Validate the presence of 'relationships' DataFrame in both self_node_pd and label_based_pd
        if "relationships" not in self_node_pd or "relationships" not in label_based_pd:
            logger.error("Relationships DataFrame missing in the provided data.")
            return []

        # Extract existing relationships from the active node
        active_relationships = self_node_pd["relationships"]
        active_targets = set(active_relationships["target_name"].dropna().unique())
        logger.debug(f"Active node target nodes: {active_targets}")

        # Extract label-based relationships excluding those already connected to the active node
        label_relationships = label_based_pd["relationships"]
        filtered_relationships = label_relationships[
            ~label_relationships["target_name"].isin(active_targets)
        ]
        logger.debug(
            f"Filtered label-based relationships count: {filtered_relationships.shape[0]}"
        )

        if filtered_relationships.empty:
            logger.info(
                "No new relationships to suggest after filtering existing targets."
            )
            return []

        # Calculate relationship frequencies
        relationship_counts = (
            filtered_relationships.groupby(
                ["relationship_type", "target_name", "direction"]
            )
            .size()
            .reset_index(name="count")
        )

        # Integrate relationship properties
        if "relationship_properties" in label_based_pd:
            # Join relationship properties to the relationship counts
            relationship_properties_df = label_based_pd["relationship_properties"]
            filtered_relationships_with_props = pd.merge(
                filtered_relationships,
                relationship_properties_df,
                left_on="id",
                right_on="relationship_id",
                how="left",
            )
            relationship_properties = (
                filtered_relationships_with_props.groupby(
                    ["relationship_type", "target_name", "direction"]
                )[
                    ["property", "value"]
                ]  # Correctly subset columns using a list
                .apply(lambda df: df.set_index("property").to_dict()["value"])
                .reset_index(name="properties")
            )
            relationship_data = pd.merge(
                relationship_counts,
                relationship_properties,
                on=["relationship_type", "target_name", "direction"],
                how="left",
            )
        else:
            logger.warning("Relationship properties are missing in the provided data.")
            relationship_counts["properties"] = [{}] * len(relationship_counts)
            relationship_data = relationship_counts

        # Calculate total number of nodes sharing the same label
        total_nodes = label_based_pd["nodes"]["name"].nunique()
        logger.debug(f"Total nodes sharing the label: {total_nodes}")

        if total_nodes == 0:
            logger.warning(
                "No nodes found in label-based data. Cannot compute confidence levels."
            )
            return []

        # Calculate confidence levels
        relationship_data["confidence"] = (
            relationship_data["count"] / total_nodes
        ) * 100
        logger.debug(f"Relationship data with confidence:\n{relationship_data.head()}")

        # Sort relationships by confidence descending and take top N
        top_relationships = relationship_data.sort_values(
            by="confidence", ascending=False
        ).head(top_n)

        # Prepare the suggestions list
        suggestions = [
            (
                row["relationship_type"],
                row["target_name"],
                row["direction"],
                row.get("properties", {}),
                round(row["confidence"], 2),
            )
            for _, row in top_relationships.iterrows()
        ]

        logger.debug(f"Generated relationship suggestions: {suggestions}")
        return suggestions

    ##### This is the function that executes the operation of the worker #####
    def execute_operation(self) -> None:

        try:

            # Fetch data

            full_data_pd, label_based_pd, self_node_pd = self.fetch_data()

            # Emit suggestions
            suggestions = {
                "tags": self.suggest_tags(self_node_pd, label_based_pd),
                "properties": self.suggest_properties(self_node_pd, label_based_pd),
                "relationships": self.suggest_relationships(
                    self_node_pd, label_based_pd
                ),
            }
            self.suggestions_ready.emit(suggestions)

            logger.info(
                "Suggestion generation completed successfully",
                module="SuggestionWorker",
                function="execute_operation",
            )

        except Exception as e:
            error_message = f"Error generating suggestions: {str(e)}"
            logger.error(
                error_message,
                exc_info=True,
                module="SuggestionWorker",
                function="execute_operation",
            )
            self.error_occurred.emit(error_message)
