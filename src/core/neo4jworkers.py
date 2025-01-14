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

from config.config import Config
from utils.converters import DataFrameBuilder

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
        self, uri: str, auth: Tuple[str, str], node_data: Dict[str, Any], config: Config
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
        self.config = config
        self._project = config.user.PROJECT

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

        builder = DataFrameBuilder()

        dataframes = builder.create_dataframes_from_data(nodes_data)

        nodes_df = dataframes["nodes"]
        properties_df = dataframes["properties"]
        tags_df = dataframes["tags"]
        labels_df = dataframes["labels"]
        relationships_df = dataframes["relationships"]
        rel_properties_df = dataframes["relationship_properties"]

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
                AND n._project = $project
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
        params = {"node_name": self.node_data.get("name"), "project": self._project}

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
                AND n._project = $project
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
        params = {"node_labels": labels, "project": self._project}

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
                WHERE n._project = $project
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
            results = session.run(query, {"project": self._project})
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

    #####  The following methods are used to generate suggestions based on the fetched data  #####

    import pandas as pd
    import logging
    from typing import Dict, Any

    # Configure logging
    logger = logging.getLogger(__name__)
    logging.basicConfig(level=logging.DEBUG)

    def suggest_relationships(
        self,
        self_node_pd: Dict[str, pd.DataFrame],
        label_based_pd: Dict[str, pd.DataFrame],
        full_data_pd: Dict[str, pd.DataFrame],
        top_n: int = 10,
    ) -> List[Tuple[str, str, str, Dict[str, Any], float]]:
        """
        Suggest relationships to add to the active node based on label-based and global data.

        Args:
            self_node_pd (Dict[str, pd.DataFrame]): DataFrames related to the active node.
            label_based_pd (Dict[str, pd.DataFrame]): DataFrames related to nodes sharing the same labels.
            full_data_pd (Dict[str, pd.DataFrame]): DataFrames related to all nodes in the dataset.
            top_n (int): Maximum number of relationships to suggest.

        Returns:
            List[Tuple[str, str, str, Dict[str, Any], float]]:
        """
        logger.debug("Starting enhanced suggest_relationships method.")

        # Validate required DataFrames
        for df_name, df in [
            ("self_node_pd", self_node_pd),
            ("label_based_pd", label_based_pd),
            ("full_data_pd", full_data_pd),
        ]:
            if "relationships" not in df:
                logger.error(f"Relationships DataFrame missing in {df_name}.")
                return []

        # Extract existing relationships for the active node
        active_relationships = self_node_pd["relationships"]
        active_targets = set(active_relationships["target_name"].dropna().unique())
        logger.debug(f"Active node target nodes: {active_targets}")

        # Extract and validate label-based relationships
        label_relationships = label_based_pd["relationships"]
        if "relationship_type" not in label_relationships.columns:
            logger.error("Missing 'relationship_type' in label-based relationships.")
            return []

        filtered_label_relationships = label_relationships[
            ~label_relationships["target_name"].isin(active_targets)
        ]
        logger.debug(
            f"Filtered label-based relationships count: {filtered_label_relationships.shape[0]}"
        )

        # Extract and validate global relationships
        global_relationships = full_data_pd["relationships"]
        if "relationship_type" not in global_relationships.columns:
            logger.error("Missing 'relationship_type' in global relationships.")
            return []

        filtered_global_relationships = global_relationships[
            ~global_relationships["target_name"].isin(active_targets)
        ]
        logger.debug(
            f"Filtered global relationships count: {filtered_global_relationships.shape[0]}"
        )

        # Combine relationships
        combined_relationships = pd.concat(
            [filtered_label_relationships, filtered_global_relationships],
            ignore_index=True,
        )
        if "relationship_type" not in combined_relationships.columns:
            logger.error(
                "Combined relationships DataFrame is missing 'relationship_type'."
            )
            return []
        logger.debug(f"Combined relationships count: {combined_relationships.shape[0]}")

        # Group and calculate confidence
        relationship_counts = (
            combined_relationships.groupby(
                ["relationship_type", "target_name", "direction"]
            )
            .size()
            .reset_index(name="count")
        )

        total_label_nodes = label_based_pd["nodes"]["name"].nunique()
        total_global_nodes = full_data_pd["nodes"]["name"].nunique()
        total_nodes = total_label_nodes + total_global_nodes

        if total_nodes == 0:
            logger.warning("No nodes available for confidence calculation.")
            return []

        relationship_counts["confidence"] = (
            relationship_counts["count"] / total_nodes
        ) * 100

        # Sort and return suggestions
        suggestions = relationship_counts.sort_values(
            by="confidence", ascending=False
        ).head(top_n)

        result = [
            (
                row["relationship_type"],
                row["target_name"],
                row["direction"],
                {},  # Placeholder for relationship properties
                round(row["confidence"], 2),
            )
            for _, row in suggestions.iterrows()
        ]

        logger.debug(f"Generated relationship suggestions: {result}")
        return result

    def suggest_tags(
        self,
        self_node_pd: Dict[str, pd.DataFrame],
        label_based_pd: Dict[str, pd.DataFrame],
        full_data_pd: Dict[str, pd.DataFrame],
        top_n: int = 10,
    ) -> List[Tuple[str, float]]:
        """
        Suggest tags to add to the active node based on label-based and global data.

        Args:
            self_node_pd (Dict[str, pd.DataFrame]): DataFrames related to the active node.
            label_based_pd (Dict[str, pd.DataFrame]): DataFrames related to nodes sharing the same labels.
            full_data_pd (Dict[str, pd.DataFrame]): DataFrames related to all nodes in the dataset.
            top_n (int): Maximum number of tags to suggest.

        Returns:
            List[Tuple[str, float]]: List of suggested tags and their confidence levels.
        """
        logger.debug("Starting enhanced suggest_tags method with global data.")

        # Validate presence of 'tags' DataFrame
        if (
            "tags" not in self_node_pd
            or "tags" not in label_based_pd
            or "tags" not in full_data_pd
        ):
            logger.error("Tags DataFrame missing in one of the provided data sources.")
            return []

        # Extract existing tags in the active node
        active_tags = set(self_node_pd["tags"]["tag"].dropna().unique())
        logger.debug(f"Active node tags: {active_tags}")

        # Extract label-based tags, excluding those already present in the active node
        label_tags = label_based_pd["tags"]
        filtered_label_tags = label_tags[~label_tags["tag"].isin(active_tags)]
        logger.debug(f"Filtered label-based tags count: {filtered_label_tags.shape[0]}")

        # Calculate tag frequencies in label-based data
        label_tag_counts = filtered_label_tags["tag"].value_counts().reset_index()
        label_tag_counts.columns = ["tag", "count"]

        # Incorporate full data: Identify globally frequent tags
        global_tags = full_data_pd["tags"]
        filtered_global_tags = global_tags[~global_tags["tag"].isin(active_tags)]
        global_tag_counts = filtered_global_tags["tag"].value_counts().reset_index()
        global_tag_counts.columns = ["tag", "count"]

        # Calculate confidence for label-based tags
        total_label_nodes = label_based_pd["nodes"]["name"].nunique()
        label_tag_counts["confidence"] = (
            label_tag_counts["count"] / total_label_nodes
        ) * 100

        # Calculate confidence for global tags
        total_global_nodes = full_data_pd["nodes"]["name"].nunique()
        global_tag_counts["confidence"] = (
            global_tag_counts["count"] / total_global_nodes
        ) * 50  # Lower weight for global

        # Merge and prioritize label-based over global tags
        combined_tags = pd.concat(
            [label_tag_counts, global_tag_counts], ignore_index=True
        )
        combined_tags = (
            combined_tags.groupby("tag").agg({"confidence": "sum"}).reset_index()
        )
        combined_tags = combined_tags.sort_values(
            by="confidence", ascending=False
        ).head(top_n)

        # Prepare the suggestions list
        suggestions = [
            (row["tag"], round(row["confidence"], 2))
            for _, row in combined_tags.iterrows()
        ]
        logger.debug(f"Enhanced tag suggestions: {suggestions}")

        return suggestions

    def suggest_properties(
        self,
        self_node_pd: Dict[str, pd.DataFrame],
        label_based_pd: Dict[str, pd.DataFrame],
        full_data_pd: Dict[str, pd.DataFrame],
        top_n: int = 10,
    ) -> Dict[str, Any]:
        """
        Suggest properties to add to the active node based on label-based and global data.
        Filters out system properties and reserved properties.

        Args:
            self_node_pd (Dict[str, pd.DataFrame]): DataFrames related to the active node.
            label_based_pd (Dict[str, pd.DataFrame]): DataFrames related to nodes sharing the same labels.
            full_data_pd (Dict[str, pd.DataFrame]): DataFrames related to all nodes in the dataset.
            top_n (int): Maximum number of properties to suggest.

        Returns:
            Dict[str, Any]: Dictionary containing property suggestions compatible with SuggestionDialog.
        """
        logger.debug(
            "Starting enhanced suggest_properties method with global data and filtering."
        )

        # Validate presence of 'properties' DataFrame
        if (
            "properties" not in self_node_pd
            or "properties" not in label_based_pd
            or "properties" not in full_data_pd
        ):
            logger.error(
                "Properties DataFrame missing in one of the provided data sources."
            )
            return {}

        # Extract active node properties
        active_properties = set(
            self_node_pd["properties"]["property"].dropna().unique()
        )
        logger.debug(f"Active node properties: {active_properties}")

        # Helper function to filter properties with access to config
        def is_valid_property(prop: str) -> bool:
            """Check if a property is valid for suggestion."""
            if prop.startswith("_"):  # Filter system properties
                logger.debug(f"Filtering system property: {prop}")
                return False
            if prop in self.config.RESERVED_PROPERTY_KEYS:  # Filter reserved properties
                logger.debug(f"Filtering reserved property: {prop}")
                return False
            return True

        # Extract and filter label-based properties
        label_properties = label_based_pd["properties"]
        filtered_label_properties = label_properties[
            (~label_properties["property"].isin(active_properties))
            & (label_properties["property"].apply(is_valid_property))
        ]

        logger.debug(
            f"Filtered label-based properties count: {filtered_label_properties.shape[0]}"
        )

        # Extract and filter global properties
        global_properties = full_data_pd["properties"]
        filtered_global_properties = global_properties[
            (~global_properties["property"].isin(active_properties))
            & (global_properties["property"].apply(is_valid_property))
        ]
        logger.debug(
            f"Filtered global properties count: {filtered_global_properties.shape[0]}"
        )

        # Calculate frequencies in label-based data
        label_property_counts = (
            filtered_label_properties.groupby("property")["value"]
            .agg(["count", lambda x: x.mode().iloc[0] if not x.mode().empty else None])
            .reset_index()
        )
        label_property_counts.rename(
            columns={"<lambda_0>": "common_value"}, inplace=True
        )

        # Calculate frequencies in global data
        global_property_counts = (
            filtered_global_properties.groupby("property")["value"]
            .agg(["count", lambda x: x.mode().iloc[0] if not x.mode().empty else None])
            .reset_index()
        )
        global_property_counts.rename(
            columns={"<lambda_0>": "common_value"}, inplace=True
        )

        # Calculate confidence for label-based properties
        total_label_nodes = label_based_pd["nodes"]["name"].nunique()
        label_property_counts["confidence"] = (
            label_property_counts["count"] / total_label_nodes
        ) * 100

        # Calculate confidence for global properties
        total_global_nodes = full_data_pd["nodes"]["name"].nunique()
        global_property_counts["confidence"] = (
            global_property_counts["count"] / total_global_nodes
        ) * 50  # Lower weight for global

        # Merge and prioritize label-based over global properties
        combined_properties = pd.concat(
            [label_property_counts, global_property_counts], ignore_index=True
        )
        combined_properties = (
            combined_properties.groupby("property")
            .agg({"common_value": "first", "confidence": "sum"})
            .reset_index()
        )
        combined_properties = combined_properties.sort_values(
            by="confidence", ascending=False
        ).head(top_n)

        # Prepare suggestions in the expected format
        suggestions = {}
        for _, row in combined_properties.iterrows():
            property_name = row["property"]
            value = row["common_value"]
            confidence = round(row["confidence"], 2)

            # Ensure property is added as a list of tuples
            if property_name not in suggestions:
                suggestions[property_name] = []
            suggestions[property_name].append((value, confidence))

        logger.debug(f"Enhanced property suggestions for dialog: {suggestions}")

        return suggestions

    ##### This is the function that executes the operation of the worker #####
    def execute_operation(self) -> None:

        try:

            # Fetch data

            full_data_pd, label_based_pd, self_node_pd = self.fetch_data()

            # Calculate cluster data

            # Emit suggestions
            suggestions = {
                "tags": self.suggest_tags(self_node_pd, label_based_pd, full_data_pd),
                "properties": self.suggest_properties(
                    self_node_pd, label_based_pd, full_data_pd
                ),
                "relationships": self.suggest_relationships(
                    self_node_pd, label_based_pd, full_data_pd
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
