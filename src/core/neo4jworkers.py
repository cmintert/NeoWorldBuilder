"""
This module provides worker classes for performing Neo4j database operations in separate threads.
It includes classes for querying, writing, deleting, and generating suggestions for nodes.
"""

import json
import logging
import statistics
import traceback
from collections import Counter
from datetime import timedelta, datetime
from threading import Lock
from typing import Any, Callable, Dict, List, Optional, Tuple, Set

import pandas as pd
from PyQt6.QtCore import QThread, pyqtSignal
from neo4j import GraphDatabase
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import StandardScaler


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
    Enhanced suggestion worker that combines pattern analysis and creative suggestions.
    All functionality is contained within this class for initial implementation,
    structured for easy future refactoring.
    """

    suggestions_ready = pyqtSignal(dict)

    def __init__(
        self, uri: str, auth: Tuple[str, str], node_data: Dict[str, Any]
    ) -> None:
        super().__init__(uri, auth)
        self.node_data = node_data
        self._setup_logging()
        self._init_cache()

    # === Setup Methods ===

    def _setup_logging(self) -> None:
        logging.basicConfig(level=logging.DEBUG)
        self.logger = logging.getLogger(__name__)

    def _init_cache(self) -> None:
        self._global_df_cache = None
        self._cache_timestamp = None
        self._cache_ttl = timedelta(minutes=30)
        self._cache_lock = Lock()

    # === Cache Management ===

    def _get_cached_global_df(
        self,
    ) -> Optional[Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]]:
        """
        Retrieve cached global DataFrames if they exist and are still valid.
        These represent patterns across the entire database.

        Returns:
            Tuple of (nodes_df, relationships_df, properties_df) or None if cache invalid
        """
        with self._cache_lock:
            if (
                self._global_df_cache is not None
                and self._cache_timestamp is not None
                and datetime.now() - self._cache_timestamp <= self._cache_ttl
            ):
                self.logger.debug("Using cached global database patterns")
                return self._global_df_cache

            self._clear_cache()
            return None

    def _cache_global_df(
        self, dataframes: Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]
    ) -> None:
        """
        Store global database patterns in cache.

        Args:
            dataframes: Tuple of (nodes_df, relationships_df, properties_df)
        """
        with self._cache_lock:
            self._global_df_cache = dataframes
            self._cache_timestamp = datetime.now()
            self.logger.debug(
                f"Cached global database patterns at {self._cache_timestamp}"
            )

    def _clear_cache(self) -> None:
        """Clear the global pattern cache"""
        self._global_df_cache = None
        self._cache_timestamp = None
        self.logger.debug("Cleared global pattern cache")

    # === Main Operation Flow ===

    def execute_operation(self) -> None:
        """Main execution flow with pattern analysis"""
        try:
            with self._driver.session() as session:
                # 1. Get similar nodes data and convert to DataFrames
                similar_nodes = self._get_unified_node_data(session, "similar")
                similar_df = self._prepare_dataframes(similar_nodes)

                # 2. Get global patterns (from cache or fresh)
                global_df = self._get_cached_global_df()

                if global_df is None:
                    self.logger.debug(
                        "Global pattern cache miss - fetching fresh database patterns"
                    )
                    global_patterns = self._get_unified_node_data(session, "global")
                    global_df = self._prepare_dataframes(global_patterns)
                    self._cache_global_df(global_df)

                # Log DataFrame info for debugging
                self._log_dataframe_info(similar_df, global_df)

                # 3. Initialize pattern analyzer
                pattern_analyzer = PatternAnalyzer(self.logger)

                # 4. Generate suggestions using pattern analyzer
                raw_suggestions = pattern_analyzer.analyze_patterns(
                    similar_dfs=similar_df,
                    global_dfs=global_df,
                    node_data=self.node_data,
                )

                # 5. Format suggestions for SuggestionDialog
                dialog_suggestions = self._format_suggestions(raw_suggestions)
                logging.debug(
                    f"Suggestion generation complete.Suggetsions: {dialog_suggestions}"
                )

                # 6. Emit results
                self.suggestions_ready.emit(dialog_suggestions)

        except Exception as e:
            self.logger.error(f"Error in suggestion worker: {str(e)}", exc_info=True)

    # === Data Gathering ===

    def _get_unified_node_data(
        self, session: Any, query_type: str = "similar"
    ) -> List<Dict[str, Any]]:
        """
        Unified method for retrieving node data with consistent output format.

        Args:
            session: Neo4j session
            query_type: "similar" for similar nodes or "global" for global patterns

        Returns:
            List of dictionaries with unified node data format
        """
        try:
            if query_type == "similar":
                query = """
                MATCH (n)
                WHERE any(label IN $labels WHERE label IN labels(n)) 
                AND n.name <> $name
                WITH n
                OPTIONAL MATCH (n)-[r]->(target)
                WITH n, 
                     collect({
                        rel_type: type(r),
                        target_labels: labels(target),
                        target_name: target.name,
                        direction: 'outgoing',
                        rel_props: properties(r)
                     }) as outgoing
                OPTIONAL MATCH (n)<-[r2]-(source)
                WITH n, outgoing,
                     collect({
                        rel_type: type(r2),
                        source_labels: labels(source),
                        source_name: source.name,
                        direction: 'incoming',
                        rel_props: properties(r2)
                     }) as incoming
                RETURN {
                    node_id: id(n),
                    name: n.name,
                    labels: labels(n),
                    properties: properties(n),
                    relationships: outgoing + incoming,
                    timestamp: datetime(),
                    metadata: {
                        created: n._created,
                        modified: n._modified,
                        author: n._author
                    }
                } as node_data
                LIMIT 200
                """
                params = {
                    "labels": self.node_data.get("labels", []),
                    "name": self.node_data.get("name", ""),
                }
            else:  # global patterns
                query = """
                MATCH (n)
                WHERE NOT n.name = $name
                WITH n
                OPTIONAL MATCH (n)-[r]->(target)
                WITH n, 
                     collect({
                        rel_type: type(r),
                        target_labels: labels(target),
                        target_name: target.name,
                        direction: 'outgoing',
                        rel_props: properties(r)
                     }) as outgoing
                OPTIONAL MATCH (n)<-[r2]-(source)
                WITH n, outgoing,
                     collect({
                        rel_type: type(r2),
                        source_labels: labels(source),
                        source_name: source.name,
                        direction: 'incoming',
                        rel_props: properties(r2)
                     }) as incoming
                RETURN {
                    node_id: id(n),
                    name: n.name,
                    labels: labels(n),
                    properties: properties(n),
                    relationships: outgoing + incoming,
                    timestamp: datetime(),
                    metadata: {
                        created: n._created,
                        modified: n._modified,
                        author: n._author
                    }
                } as node_data
                LIMIT 50
                """
                params = {"name": self.node_data.get("name", "")}

            result = session.run(query, params)
            nodes = list(result)

            # Process and normalize the results
            normalized_data = []
            for record in nodes:
                node_data = record.get("node_data", {})
                if not isinstance(node_data, dict):
                    continue

                # Log the node data dictionary
                self.logger.debug(f"Node data: {node_data}")

                # Ensure consistent property types
                properties = node_data.get("properties", {})
                processed_properties = {}
                for key, value in properties.items():
                    if isinstance(value, (list, dict)):
                        processed_properties[key] = json.dumps(value)
                    else:
                        processed_properties[key] = str(value)

                # Process relationships for statistical analysis
                relationships = node_data.get("relationships", [])
                relationship_stats = {
                    "total_count": len(relationships),
                    "outgoing_count": sum(
                        1 for r in relationships if r.get("direction") == "outgoing"
                    ),
                    "incoming_count": sum(
                        1 for r in relationships if r.get("direction") == "incoming"
                    ),
                    "types": Counter(r.get("rel_type") for r in relationships),
                    "connected_labels": Counter(
                        label
                        for r in relationships
                        for label in (
                            (r.get("target_labels", [])) + (r.get("source_labels", []))
                        )
                    ),
                }

                normalized_data.append(
                    {
                        "node_id": node_data.get("node_id"),
                        "name": node_data.get("name"),
                        "labels": node_data.get("labels", []),
                        "properties": processed_properties,
                        "relationships": relationships,
                        "relationship_stats": relationship_stats,
                        "timestamp": node_data.get("timestamp"),
                        "metadata": node_data.get("metadata", {}),
                    }
                )

            self.logger.debug(
                f"Retrieved and normalized {len(normalized_data)} nodes for {query_type} query"
            )
            return normalized_data

        except Exception as e:
            self.logger.error(
                f"Error in unified node data retrieval: {str(e)}", exc_info=True
            )
            return []

    # === Panda Dataframe creation ===

    def _prepare_dataframes(
        self, node_data: List[Dict[str, Any]]
    ) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """
        Creates normalized DataFrames from node data, separating core node data,
        relationships, and properties for efficient analysis.

        Args:
            node_data: List of dictionaries containing unified node data

        Returns:
            Tuple of (nodes_df, relationships_df, properties_df)
        """
        try:
            # 1. Create core nodes DataFrame
            nodes_df = pd.DataFrame(
                [
                    {
                        "node_id": node["node_id"],
                        "name": node["name"],
                        "labels": "|".join(
                            node["labels"]
                        ),  # Convert list to string for easier processing
                        "total_properties": len(node["properties"]),
                        "total_relationships": node["relationship_stats"][
                            "total_count"
                        ],
                        "incoming_relationships": node["relationship_stats"][
                            "incoming_count"
                        ],
                        "outgoing_relationships": node["relationship_stats"][
                            "outgoing_count"
                        ],
                        "timestamp": node["timestamp"],
                        "created": node["metadata"].get("created"),
                        "modified": node["metadata"].get("modified"),
                        "author": node["metadata"].get("author"),
                    }
                    for node in node_data
                ]
            )

            # 2. Create relationships DataFrame with one row per relationship
            relationships_rows = []
            for node in node_data:
                node_id = node["node_id"]
                for rel in node["relationships"]:
                    relationships_rows.append(
                        {
                            "node_id": node_id,
                            "relationship_type": rel["rel_type"],
                            "direction": rel["direction"],
                            "target_name": rel.get("target_name"),
                            "source_name": rel.get("source_name"),
                            "target_labels": "|".join(rel.get("target_labels", [])),
                            "source_labels": "|".join(rel.get("source_labels", [])),
                            "properties": json.dumps(
                                rel.get("rel_props", {})
                            ),  # Store as JSON for now
                        }
                    )
            relationships_df = pd.DataFrame(relationships_rows)

            # 3. Create properties DataFrame with one row per property
            properties_rows = []
            for node in node_data:
                node_id = node["node_id"]
                for key, value in node["properties"].items():
                    properties_rows.append(
                        {
                            "node_id": node_id,
                            "property_key": key,
                            "property_value": str(value),
                            "property_type": type(value).__name__,
                        }
                    )
            properties_df = pd.DataFrame(properties_rows)

            # 4. Add analytical columns to each DataFrame
            self._enhance_dataframes(nodes_df, relationships_df, properties_df)

            return nodes_df, relationships_df, properties_df

        except Exception as e:
            self.logger.error(f"Error preparing DataFrames: {str(e)}", exc_info=True)
            # Return empty DataFrames with expected columns
            return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    def _enhance_dataframes(
        self,
        nodes_df: pd.DataFrame,
        relationships_df: pd.DataFrame,
        properties_df: pd.DataFrame,
    ) -> None:
        """
        Enhances DataFrames with additional analytical columns and metrics.
        Modifies DataFrames in place.
        """
        try:
            # Enhance nodes DataFrame
            if not nodes_df.empty:
                # Add label count
                nodes_df["label_count"] = nodes_df["labels"].str.count("|") + 1

                # Calculate property diversity score (unique property keys / total properties)
                property_counts = properties_df.groupby("node_id")["property_key"].agg(
                    ["nunique", "count"]
                )
                nodes_df["property_diversity"] = (
                    property_counts["nunique"] / property_counts["count"]
                )

                # Calculate relationship diversity score
                rel_type_counts = relationships_df.groupby("node_id")[
                    "relationship_type"
                ].nunique()
                nodes_df["relationship_diversity"] = (
                    rel_type_counts / nodes_df["total_relationships"]
                )

            # Enhance relationships DataFrame
            if not relationships_df.empty:
                # Calculate property complexity for relationships
                relationships_df["property_count"] = relationships_df[
                    "properties"
                ].apply(lambda x: len(json.loads(x)) if x else 0)

                # Add connected label count
                relationships_df["target_label_count"] = (
                    relationships_df["target_labels"].str.count("|") + 1
                )
                relationships_df["source_label_count"] = (
                    relationships_df["source_labels"].str.count("|") + 1
                )

            # Enhance properties DataFrame
            if not properties_df.empty:
                # Add value length for string properties
                properties_df["value_length"] = properties_df[
                    "property_value"
                ].str.len()

                # Add complexity indicator for different property types
                properties_df["is_complex"] = properties_df["property_value"].apply(
                    lambda x: 1 if any(marker in x for marker in ["{", "[", ","]) else 0
                )

        except Exception as e:
            self.logger.error(f"Error enhancing DataFrames: {str(e)}", exc_info=True)

    # === Utility Methods ===

    def _format_suggestions(self, analyzer_output: Dict[str, Any]) -> Dict[str, Any]:
        """
        Formats analyzer output for SuggestionDialog.
        Dialog will automatically group by confidence:
        - Common Patterns: >= 70%
        - Creative Suggestions: < 70%
        """
        try:
            local = analyzer_output.get("local", {})
            creative = analyzer_output.get("creative", {})

            # 1. Format Tags
            tags = []
            # Add local tags with original high confidence
            tags.extend((tag, confidence) for tag, confidence in local.get("tags", []))
            # Add creative tags with lower confidence
            tags.extend(
                (tag, min(confidence, 69.9))
                for tag, confidence in creative.get("tags", [])
            )
            # Sort by confidence
            tags.sort(key=lambda x: x[1], reverse=True)

            # 2. Format Properties
            properties = {}
            # Add local properties (high confidence)
            for prop_name, values in local.get("properties", {}).items():
                properties[prop_name] = values

            # Add creative properties (lower confidence)
            for prop_name, values in creative.get("properties", {}).items():
                if prop_name not in properties:  # Don't override local suggestions
                    properties[prop_name] = [
                        (value, min(conf, 69.9)) for value, conf in values
                    ]

            # 3. Format Relationships
            relationships = []
            # Add local relationships (high confidence)
            for rel_type, target, conf in local.get("relationships", []):
                relationships.append(
                    (
                        rel_type,  # type
                        target,  # target
                        "outgoing",  # direction
                        {},  # properties
                        conf,  # confidence
                    )
                )

            # Add creative relationships (lower confidence)
            for rel_type, target, conf in creative.get("relationships", []):
                relationships.append(
                    (
                        rel_type,
                        target,
                        "outgoing",
                        {"creative": {}},  # Mark as creative in properties
                        min(conf, 69.9),  # Ensure lower confidence
                    )
                )

            # Sort by confidence
            relationships.sort(key=lambda x: x[4], reverse=True)

            # Limit the number of suggestions to 8 for each category
            tags = tags[:8]
            properties = {k: v[:8] for k, v in properties.items()}
            relationships = relationships[:8]

            # Final output format
            formatted = {
                "tags": tags,
                "properties": properties,
                "relationships": relationships,
            }

            self.logger.debug("\nFormatted Suggestions Summary:")
            self.logger.debug(f"Tags: {len(formatted['tags'])} total")
            self.logger.debug(f"Properties: {len(formatted['properties'])} types")
            self.logger.debug(f"Relationships: {len(formatted['relationships'])} total")

            return formatted

        except Exception as e:
            self.logger.error(f"Error formatting suggestions: {str(e)}", exc_info=True)
            return {"tags": [], "properties": {}, "relationships": []}

    def _log_dataframe_info(
        self,
        similar_df: Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame],
        global_df: Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame],
    ) -> None:
        """Log information about both DataFrame sets for debugging"""
        similar_nodes, similar_rels, similar_props = similar_df
        global_nodes, global_rels, global_props = global_df

        self.logger.debug("\nDataFrame Information:")
        self.logger.debug("Similar Nodes Data (Current Context):")
        self.logger.debug(f"- Nodes: {len(similar_nodes)} rows")
        self.logger.debug(f"- Relationships: {len(similar_rels)} rows")
        self.logger.debug(f"- Properties: {len(similar_props)} rows")

        self.logger.debug("\nGlobal Database Patterns:")
        self.logger.debug(f"- Nodes: {len(global_nodes)} rows")
        self.logger.debug(f"- Relationships: {len(global_rels)} rows")
        self.logger.debug(f"- Properties: {len(global_props)} rows")
        self.logger.debug(f"- Unique node labels: {global_nodes['labels'].nunique()}")
        self.logger.debug(
            f"- Unique relationship types: {global_rels['relationship_type'].nunique()}"
        )
        self.logger.debug(
            f"- Unique property keys: {global_props['property_key'].nunique()}"
        )


class PatternAnalyzer:
    """
    Modular pattern analyzer that can be extended with additional analysis methods.
    Works with pre-processed DataFrames from the SuggestionWorker.
    """

    def __init__(self, logger):
        self.logger = logger

    def analyze_patterns(
        self,
        similar_dfs: Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame],
        global_dfs: Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame],
        node_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Main analysis method coordinating local and global pattern analysis.

        Args:
            similar_dfs: Tuple of (nodes_df, relationships_df, properties_df) for similar nodes
            global_dfs: Tuple of (nodes_df, relationships_df, properties_df) for global patterns
            node_data: Current node data dictionary

        Returns:
            Dictionary containing:
            {
                'local': {
                    'properties': Dict[str, List[Tuple[str, float]]],  # property_name -> [(value, confidence), ...]
                    'relationships': List[Tuple[str, str, float]],     # [(type, target, confidence), ...]
                    'tags': List[Tuple[str, float]]                    # [(tag, confidence), ...]
                },
                'creative': {
                    'properties': Dict[str, List[Tuple[str, float]]],
                    'relationships': List[Tuple[str, str, float]],
                    'tags': List[Tuple[str, float]]
                }
            }
        """
        try:
            # Input validation
            if not all(isinstance(df, pd.DataFrame) for df in similar_dfs + global_dfs):
                raise ValueError("Invalid DataFrame format in input")

            similar_nodes, similar_rels, similar_props = similar_dfs
            global_nodes, global_rels, global_props = global_dfs

            # Verify required columns
            self._verify_dataframe_structure(similar_dfs, global_dfs)

            # Log analysis start
            self.logger.debug(
                f"Starting pattern analysis for node: {node_data.get('name', 'Unknown')}"
            )
            self.logger.debug(
                f"Similar nodes: {len(similar_nodes)}, Global nodes: {len(global_nodes)}"
            )

            # 1. Local Pattern Analysis
            local_suggestions = {}

            # 1.1 Properties
            local_suggestions["properties"] = self._analyze_local_properties(
                similar_props, node_data
            )
            self.logger.debug(
                f"Found {len(local_suggestions['properties'])} local property patterns"
            )

            # 1.2 Relationships
            local_suggestions["relationships"] = self._analyze_local_relationships(
                similar_rels, node_data
            )
            self.logger.debug(
                f"Found {len(local_suggestions['relationships'])} local relationship patterns"
            )

            # 1.3 Tags
            local_suggestions["tags"] = self._analyze_local_tags(
                similar_props, node_data  # Tags are stored in properties
            )
            self.logger.debug(
                f"Found {len(local_suggestions['tags'])} local tag patterns"
            )

            # 2. Global Pattern Analysis
            creative_suggestions = {}

            # 2.1 Properties
            creative_suggestions["properties"] = self._analyze_global_properties(
                global_dfs, local_suggestions, node_data
            )
            self.logger.debug(
                f"Found {len(creative_suggestions['properties'])} creative property patterns"
            )

            # 2.2 Relationships
            creative_suggestions["relationships"] = self._analyze_global_relationships(
                global_dfs, local_suggestions, node_data
            )
            self.logger.debug(
                f"Found {len(creative_suggestions['relationships'])} creative relationship patterns"
            )

            # 2.3 Tags
            creative_suggestions["tags"] = self._analyze_global_tags(
                global_dfs, local_suggestions, node_data
            )
            self.logger.debug(
                f"Found {len(creative_suggestions['tags'])} creative tag patterns"
            )

            # Combine and return results
            result = {"local": local_suggestions, "creative": creative_suggestions}

            # Log summary
            self._log_analysis_summary(result)

            return result

        except Exception as e:
            self.logger.error(f"Error in pattern analysis: {str(e)}", exc_info=True)
            return {"local": {}, "creative": {}}

    def _verify_dataframe_structure(
        self,
        similar_dfs: Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame],
        global_dfs: Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame],
    ) -> None:
        """Verifies that all required columns are present in the DataFrames"""

        required_columns = {
            "nodes": {
                "node_id",
                "name",
                "labels",
                "total_properties",
                "total_relationships",
                "property_diversity",
                "relationship_diversity",
            },
            "relationships": {
                "node_id",
                "relationship_type",
                "direction",
                "target_name",
                "source_name",
                "target_labels",
                "source_labels",
                "properties",
            },
            "properties": {
                "node_id",
                "property_key",
                "property_value",
                "property_type",
                "value_length",
                "is_complex",
            },
        }

        for df_type, (similar_df, global_df) in zip(
            ["nodes", "relationships", "properties"], zip(similar_dfs, global_dfs)
        ):
            missing_cols_similar = required_columns[df_type] - set(similar_df.columns)
            missing_cols_global = required_columns[df_type] - set(global_df.columns)

            if missing_cols_similar:
                raise ValueError(
                    f"Missing required columns in similar {df_type} DataFrame: {missing_cols_similar}"
                )
            if missing_cols_global:
                raise ValueError(
                    f"Missing required columns in global {df_type} DataFrame: {missing_cols_global}"
                )

    def _log_analysis_summary(self, result: Dict[str, Any]) -> None:
        """Logs a summary of the analysis results"""
        self.logger.debug("\nPattern Analysis Summary:")
        self.logger.debug("Local Suggestions:")
        self.logger.debug(f"- Properties: {len(result['local']['properties'])} types")
        self.logger.debug(
            f"- Relationships: {len(result['local']['relationships'])} patterns"
        )
        self.logger.debug(f"- Tags: {len(result['local']['tags'])} suggestions")

        self.logger.debug("\nCreative Suggestions:")
        self.logger.debug(
            f"- Properties: {len(result['creative']['properties'])} types"
        )
        self.logger.debug(
            f"- Relationships: {len(result['creative']['relationships'])} patterns"
        )
        self.logger.debug(f"- Tags: {len(result['creative']['tags'])} suggestions")

    def _analyze_local_properties(
        self, props_df: pd.DataFrame, node_data: Dict[str, Any]
    ) -> Dict[str, List[Tuple[str, float]]]:
        """
        Analyzes property patterns from similar nodes to suggest new properties and values.

        Args:
            props_df: Properties DataFrame containing property information
            node_data: Current node data dictionary

        Returns:
            Dict[str, List[Tuple[str, float]]]: Dictionary mapping property names to list of
            (value, confidence) tuples, sorted by confidence
        """
        try:
            # Skip if DataFrame is empty
            if props_df.empty:
                self.logger.debug("No properties to analyze in similar nodes")
                return {}

            # Get current node's properties
            current_properties = set(node_data.get("properties", {}).keys())

            # Properties to exclude from suggestions
            exclude_properties = {
                "name",
                "description",
                "created",
                "modified",
                "author",
                "tags",
                "_created",
                "_modified",
                "_author",
            }

            # Initialize results dictionary
            property_suggestions = {}

            # Group properties by key to analyze patterns
            property_groups = props_df.groupby("property_key")

            for prop_key, group in property_groups:
                # Skip if property should be excluded or already exists
                if prop_key in exclude_properties or prop_key in current_properties:
                    continue

                # Calculate basic frequency metrics
                total_occurrences = len(group)
                value_counts = group["property_value"].value_counts()
                unique_values = len(value_counts)

                # Skip if property only appears once
                if total_occurrences < 2:
                    continue

                # Calculate value frequencies and complexities
                value_metrics = []
                for value, count in value_counts.items():
                    # Base confidence from frequency
                    frequency_score = count / total_occurrences

                    # Get complexity metrics for this value
                    value_rows = group[group["property_value"] == value]
                    complexity_score = value_rows["is_complex"].mean()
                    avg_length = value_rows["value_length"].mean()

                    # Calculate consistency score
                    consistency_score = 1.0 - (unique_values / total_occurrences)

                    # Adjust confidence based on multiple factors
                    confidence = self._calculate_property_confidence(
                        frequency_score,
                        complexity_score,
                        consistency_score,
                        avg_length,
                        total_occurrences,
                    )

                    value_metrics.append((value, confidence))

                # Sort by confidence and take top 3
                property_suggestions[prop_key] = sorted(
                    value_metrics, key=lambda x: x[1], reverse=True
                )[:3]

            # Log analysis results
            self._log_property_analysis_results(property_suggestions)

            return property_suggestions

        except Exception as e:
            self.logger.error(
                f"Error in local property analysis: {str(e)}", exc_info=True
            )
            return {}

    def _calculate_property_confidence(
        self,
        frequency_score: float,
        complexity_score: float,
        consistency_score: float,
        avg_length: float,
        total_occurrences: int,
    ) -> float:
        """
        Calculates confidence score for a property value based on multiple metrics.

        The confidence score is calculated using:
        - Frequency of the value
        - Complexity of the value
        - Consistency of the property
        - Average length of the value
        - Total number of occurrences (for statistical significance)

        Returns:
            float: Confidence score between 0 and 100
        """
        try:
            # Base confidence from frequency (40% weight)
            confidence = frequency_score * 0.4

            # Adjust for consistency (20% weight)
            confidence += consistency_score * 0.2

            # Adjust for complexity (20% weight)
            # Complex values might be more significant but also riskier
            complexity_factor = 1.0 - abs(complexity_score - 0.5) * 0.4
            confidence += complexity_factor * 0.2

            # Adjust for value length (10% weight)
            # Extremely short or long values might be less reliable
            length_factor = 1.0 - min(abs(avg_length - 50) / 100, 0.5)
            confidence += length_factor * 0.1

            # Adjust for statistical significance (10% weight)
            significance_factor = min(total_occurrences / 10, 1.0)
            confidence += significance_factor * 0.1

            # Convert to percentage and ensure bounds
            confidence = min(max(confidence * 100, 0), 100)

            return round(confidence, 2)

        except Exception as e:
            self.logger.error(
                f"Error calculating property confidence: {str(e)}", exc_info=True
            )
            return 0.0

    def _log_property_analysis_results(
        self, property_suggestions: Dict[str, List[Tuple[str, float]]]
    ) -> None:
        """Logs detailed results of property pattern analysis"""
        self.logger.debug("\nLocal Property Analysis Results:")
        self.logger.debug(f"Total suggested properties: {len(property_suggestions)}")

        for prop_key, values in property_suggestions.items():
            self.logger.debug(f"\nProperty: {prop_key}")
            for value, confidence in values:
                self.logger.debug(
                    f"- Value: {value[:50]}... Confidence: {confidence:.2f}%"
                )

    def _analyze_local_relationships(
        self, rels_df: pd.DataFrame, node_data: Dict[str, Any]
    ) -> List[Tuple[str, str, float]]:
        """
        Analyzes relationship patterns from similar nodes to suggest new connections.

        Args:
            rels_df: Relationships DataFrame containing connection information
            node_data: Current node data dictionary

        Returns:
            List[Tuple[str, str, float]]: List of (relationship_type, target_type, confidence)
            tuples, sorted by confidence
        """
        try:
            # Skip if DataFrame is empty
            if rels_df.empty:
                self.logger.debug("No relationships to analyze in similar nodes")
                return []

            # Get current node's relationships
            current_relationships = {
                (rel.get("type", ""), rel.get("target", ""))
                for rel in node_data.get("relationships", [])
                if isinstance(rel, dict)
            }

            # Get current node's labels
            current_labels = set(node_data.get("labels", []))

            # Initialize relationship pattern storage
            relationship_patterns = []

            # Group relationships by type and target labels
            grouped_rels = rels_df.groupby(["relationship_type", "target_labels"])

            for (rel_type, target_labels), group in grouped_rels:
                # Skip if this exact relationship type and target already exists
                if (rel_type, target_labels) in current_relationships:
                    continue

                # Calculate base metrics
                total_occurrences = len(group)
                if total_occurrences < 2:  # Skip rare relationships
                    continue

                # Calculate pattern metrics
                pattern_metrics = self._calculate_relationship_metrics(
                    group, current_labels, total_occurrences
                )

                # Calculate confidence score
                confidence = self._calculate_relationship_confidence(pattern_metrics)

                # Store pattern if confidence meets threshold
                if confidence > 20.0:  # Minimum confidence threshold
                    relationship_patterns.append((rel_type, target_labels, confidence))

            # Sort by confidence and take top suggestions
            top_patterns = sorted(
                relationship_patterns, key=lambda x: x[2], reverse=True
            )[
                :5
            ]  # Limit to top 5 suggestions

            # Log analysis results
            self._log_relationship_analysis_results(top_patterns)

            return top_patterns

        except Exception as e:
            self.logger.error(
                f"Error in local relationship analysis: {str(e)}", exc_info=True
            )
            return []

    def _calculate_relationship_metrics(
        self, group: pd.DataFrame, current_labels: Set[str], total_occurrences: int
    ) -> Dict[str, float]:
        """
        Calculates various metrics for relationship pattern analysis.

        Args:
            group: DataFrame group for a specific relationship type and target
            current_labels: Set of current node labels
            total_occurrences: Total number of occurrences of this pattern

        Returns:
            Dict containing calculated metrics
        """
        try:
            # Frequency metric
            frequency_score = total_occurrences / len(group)

            # Direction consistency
            direction_counts = group["direction"].value_counts()
            direction_consistency = direction_counts.max() / total_occurrences

            # Property complexity
            avg_property_count = group["property_count"].mean()
            max_properties = group["property_count"].max()
            property_complexity = avg_property_count / max(max_properties, 1)

            # Target label overlap (semantic relevance)
            target_labels = set(group["target_labels"].iloc[0].split("|"))
            label_overlap = len(current_labels.intersection(target_labels)) / max(
                len(current_labels.union(target_labels)), 1
            )

            # Structural metrics
            source_diversity = group["source_label_count"].nunique() / total_occurrences
            target_diversity = group["target_label_count"].nunique() / total_occurrences

            return {
                "frequency_score": frequency_score,
                "direction_consistency": direction_consistency,
                "property_complexity": property_complexity,
                "label_overlap": label_overlap,
                "structural_diversity": (source_diversity + target_diversity) / 2,
                "total_occurrences": total_occurrences,
            }

        except Exception as e:
            self.logger.error(
                f"Error calculating relationship metrics: {str(e)}", exc_info=True
            )
            return {}

    def _calculate_relationship_confidence(self, metrics: Dict[str, float]) -> float:
        """
        Calculates confidence score for a relationship pattern based on multiple metrics.

        The confidence score considers:
        - Frequency of the relationship pattern
        - Consistency of the relationship direction
        - Complexity of relationship properties
        - Semantic relevance (label overlap)
        - Structural diversity
        - Statistical significance (total occurrences)

        Returns:
            float: Confidence score between 0 and 100
        """
        try:
            if not metrics:
                return 0.0

            # Base confidence from frequency (30% weight)
            confidence = metrics["frequency_score"] * 0.3

            # Direction consistency (20% weight)
            confidence += metrics["direction_consistency"] * 0.2

            # Property complexity (15% weight)
            # Complex relationships might be more significant
            confidence += metrics["property_complexity"] * 0.15

            # Semantic relevance (20% weight)
            confidence += metrics["label_overlap"] * 0.2

            # Structural diversity (10% weight)
            confidence += (1.0 - metrics["structural_diversity"]) * 0.1

            # Statistical significance adjustment (5% weight)
            significance_factor = min(metrics["total_occurrences"] / 10, 1.0)
            confidence += significance_factor * 0.05

            # Convert to percentage and ensure bounds
            confidence = min(max(confidence * 100, 0), 100)

            return round(confidence, 2)

        except Exception as e:
            self.logger.error(
                f"Error calculating relationship confidence: {str(e)}", exc_info=True
            )
            return 0.0

    def _log_relationship_analysis_results(
        self, patterns: List[Tuple[str, str, float]]
    ) -> None:
        """Logs detailed results of relationship pattern analysis"""
        self.logger.debug("\nLocal Relationship Analysis Results:")
        self.logger.debug(f"Total suggested relationships: {len(patterns)}")

        for rel_type, target_labels, confidence in patterns:
            self.logger.debug(f"\nType: {rel_type}")
            self.logger.debug(f"Target Labels: {target_labels}")
            self.logger.debug(f"Confidence: {confidence:.2f}%")

    def _analyze_local_tags(
        self, props_df: pd.DataFrame, node_data: Dict[str, Any]
    ) -> List[Tuple[str, float]]:
        """
        Analyzes tag patterns from similar nodes to suggest new tags.
        Tags are stored as a property value in the properties DataFrame.

        Args:
            props_df: Properties DataFrame containing property information
            node_data: Current node data dictionary

        Returns:
            List[Tuple[str, float]]: List of (tag, confidence) tuples, sorted by confidence
        """
        try:
            # Skip if DataFrame is empty
            if props_df.empty:
                self.logger.debug("No properties to analyze for tags")
                return []

            # Get current node's tags
            current_tags = set(node_data.get("properties", {}).get("tags", []))

            # Filter for tag properties and parse them
            tag_rows = props_df[props_df["property_key"] == "tags"]
            if tag_rows.empty:
                self.logger.debug("No tag data found in similar nodes")
                return []

            # Collect and analyze tags
            all_tags = []
            tag_contexts = {}  # Store contextual information for each tag
            total_nodes = len(tag_rows["node_id"].unique())

            for _, row in tag_rows.iterrows():
                try:
                    # Parse tags from property value (stored as JSON string)
                    node_tags = json.loads(row["property_value"])
                    if not isinstance(node_tags, list):
                        continue

                    # Process each tag
                    for tag in node_tags:
                        if tag in current_tags:
                            continue

                        all_tags.append(tag)

                        # Store contextual information
                        if tag not in tag_contexts:
                            tag_contexts[tag] = {
                                "occurrences": 0,
                                "node_ids": set(),
                                "co_occurrences": Counter(),  # Count co-occurring tags
                            }

                        tag_contexts[tag]["occurrences"] += 1
                        tag_contexts[tag]["node_ids"].add(row["node_id"])

                        # Record co-occurrences with other tags
                        for other_tag in node_tags:
                            if other_tag != tag:
                                tag_contexts[tag]["co_occurrences"][other_tag] += 1

                except json.JSONDecodeError:
                    continue  # Skip invalid JSON
                except Exception as e:
                    self.logger.warning(f"Error processing tag row: {str(e)}")
                    continue

            # Calculate tag metrics and confidence scores
            tag_scores = []
            for tag, context in tag_contexts.items():
                if (
                    len(context["node_ids"]) < 2
                ):  # Skip tags that appear in only one node
                    continue

                # Calculate metrics for this tag
                metrics = self._calculate_tag_metrics(
                    tag, context, current_tags, total_nodes
                )

                # Calculate confidence score
                confidence = self._calculate_tag_confidence(metrics)

                tag_scores.append((tag, confidence))

            # Sort by confidence and take top suggestions
            top_tags = sorted(tag_scores, key=lambda x: x[1], reverse=True)[
                :5
            ]  # Limit to top 5 suggestions

            # Log analysis results
            self._log_tag_analysis_results(top_tags, tag_contexts)

            return top_tags

        except Exception as e:
            self.logger.error(f"Error in local tag analysis: {str(e)}", exc_info=True)
            return []

    def _calculate_tag_metrics(
        self,
        tag: str,
        context: Dict[str, Any],
        current_tags: Set[str],
        total_nodes: int,
    ) -> Dict[str, float]:
        """
        Calculates various metrics for tag pattern analysis.

        Args:
            tag: The tag being analyzed
            context: Contextual information about the tag
            current_tags: Set of current node's tags
            total_nodes: Total number of nodes analyzed

        Returns:
            Dict containing calculated metrics
        """
        try:
            # Frequency metrics
            frequency = context["occurrences"] / total_nodes
            node_coverage = len(context["node_ids"]) / total_nodes

            # Co-occurrence metrics
            total_co_occurrences = sum(context["co_occurrences"].values())
            avg_co_occurrences = total_co_occurrences / max(
                len(context["co_occurrences"]), 1
            )

            # Relevance to current tags
            current_tag_co_occurrences = sum(
                count
                for tag, count in context["co_occurrences"].items()
                if tag in current_tags
            )
            current_tag_relevance = current_tag_co_occurrences / max(
                len(current_tags), 1
            )

            # Tag stability (consistency of appearance)
            stability = node_coverage / frequency

            return {
                "frequency": frequency,
                "node_coverage": node_coverage,
                "avg_co_occurrences": avg_co_occurrences,
                "current_tag_relevance": current_tag_relevance,
                "stability": stability,
                "total_occurrences": context["occurrences"],
            }

        except Exception as e:
            self.logger.error(f"Error calculating tag metrics: {str(e)}", exc_info=True)
            return {}

    def _calculate_tag_confidence(self, metrics: Dict[str, float]) -> float:
        """
        Calculates confidence score for a tag based on multiple metrics.

        The confidence score considers:
        - Frequency of tag appearance
        - Node coverage
        - Co-occurrence patterns
        - Relevance to current tags
        - Tag stability

        Returns:
            float: Confidence score between 0 and 100
        """
        try:
            if not metrics:
                return 0.0

            # Base confidence from frequency (30% weight)
            confidence = metrics["frequency"] * 0.3

            # Node coverage (20% weight)
            confidence += metrics["node_coverage"] * 0.2

            # Co-occurrence patterns (15% weight)
            confidence += min(metrics["avg_co_occurrences"], 1.0) * 0.15

            # Current tag relevance (25% weight)
            confidence += metrics["current_tag_relevance"] * 0.25

            # Stability (10% weight)
            confidence += min(metrics["stability"], 1.0) * 0.1

            # Convert to percentage and ensure bounds
            confidence = min(max(confidence * 100, 0), 100)

            return round(confidence, 2)

        except Exception as e:
            self.logger.error(
                f"Error calculating tag confidence: {str(e)}", exc_info=True
            )
            return 0.0

    def _log_tag_analysis_results(
        self, tag_scores: List[Tuple[str, float]], tag_contexts: Dict[str, Any]
    ) -> None:
        """Logs detailed results of tag pattern analysis"""
        self.logger.debug("\nLocal Tag Analysis Results:")
        self.logger.debug(f"Total suggested tags: {len(tag_scores)}")

        for tag, confidence in tag_scores:
            context = tag_contexts.get(tag, {})
            self.logger.debug(f"\nTag: {tag}")
            self.logger.debug(f"Confidence: {confidence:.2f}%")
            self.logger.debug(f"Occurrences: {context.get('occurrences', 0)}")
            self.logger.debug(f"Unique nodes: {len(context.get('node_ids', set()))}")
            if context.get("co_occurrences"):
                self.logger.debug("Top co-occurring tags:")
                for co_tag, count in context["co_occurrences"].most_common(3):
                    self.logger.debug(f"  - {co_tag}: {count} times")

    def _analyze_global_properties(
        self,
        global_dfs: Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame],
        local_suggestions: Dict[str, Any],
        node_data: Dict[str, Any],
    ) -> Dict[str, List[Tuple[str, float]]]:
        """
        Analyzes global property patterns to find creative property suggestions.
        Focuses on discovering novel but relevant properties across different node types.

        Args:
            global_dfs: Tuple of (nodes_df, relationships_df, properties_df) for global patterns
            local_suggestions: Dictionary containing local pattern suggestions
            node_data: Current node data dictionary

        Returns:
            Dict[str, List[Tuple[str, float]]]: Dictionary mapping property names to list of
            (value, confidence) tuples, sorted by confidence
        """
        try:
            nodes_df, _, properties_df = global_dfs

            # Skip if DataFrames are empty
            if properties_df.empty or nodes_df.empty:
                self.logger.debug("No global properties to analyze")
                return {}

            # Get existing properties and local suggestions to avoid duplication
            current_properties = set(node_data.get("properties", {}).keys())
            local_properties = set(local_suggestions.get("properties", {}).keys())
            exclude_properties = (
                current_properties
                | local_properties
                | {
                    "name",
                    "description",
                    "created",
                    "modified",
                    "author",
                    "tags",
                    "_created",
                    "_modified",
                    "_author",
                }
            )

            # Get current node's context
            current_labels = set(node_data.get("labels", []))

            # Initialize results
            creative_properties = {}

            # Analyze property patterns
            property_patterns = self._analyze_global_property_patterns(
                nodes_df, properties_df, current_labels, exclude_properties
            )

            # Generate suggestions for each discovered pattern
            for prop_key, pattern_data in property_patterns.items():
                # Skip if property should be excluded
                if prop_key in exclude_properties:
                    continue

                # Calculate metrics
                metrics = self._calculate_global_property_metrics(
                    pattern_data, current_labels, nodes_df, properties_df
                )

                # Generate value suggestions with confidence scores
                value_suggestions = self._generate_property_value_suggestions(
                    pattern_data, metrics
                )

                # Only include if we have value suggestions with sufficient confidence
                if value_suggestions:
                    creative_properties[prop_key] = value_suggestions

            # Log analysis results
            self._log_global_property_analysis(creative_properties)

            return creative_properties

        except Exception as e:
            self.logger.error(
                f"Error in global property analysis: {str(e)}", exc_info=True
            )
            return {}

    def _analyze_global_property_patterns(
        self,
        nodes_df: pd.DataFrame,
        properties_df: pd.DataFrame,
        current_labels: Set[str],
        exclude_properties: Set[str],
    ) -> Dict[str, Dict]:
        """
        Analyzes global property patterns across different node types.
        """
        try:
            patterns = {}

            # Group properties by key
            property_groups = properties_df.groupby("property_key")

            for prop_key, group in property_groups:
                if prop_key in exclude_properties:
                    continue

                # Get nodes that have this property
                node_ids = group["node_id"].unique()
                property_nodes = nodes_df[nodes_df["node_id"].isin(node_ids)]

                # Analyze label distribution for this property
                label_distribution = {}
                for _, node in property_nodes.iterrows():
                    node_labels = set(node["labels"].split("|"))
                    for label in node_labels:
                        label_distribution[label] = label_distribution.get(label, 0) + 1

                # Calculate label overlap score
                total_nodes = len(node_ids)
                label_scores = {
                    label: count / total_nodes
                    for label, count in label_distribution.items()
                }

                # Analyze value patterns
                value_patterns = (
                    group.groupby("property_value")
                    .agg(
                        {
                            "node_id": "count",
                            "value_length": "mean",
                            "is_complex": "mean",
                        }
                    )
                    .to_dict("index")
                )

                patterns[prop_key] = {
                    "total_occurrences": total_nodes,
                    "label_distribution": label_distribution,
                    "label_scores": label_scores,
                    "value_patterns": value_patterns,
                    "avg_property_diversity": property_nodes[
                        "property_diversity"
                    ].mean(),
                    "avg_relationship_diversity": property_nodes[
                        "relationship_diversity"
                    ].mean(),
                }

            return patterns

        except Exception as e:
            self.logger.error(
                f"Error analyzing global property patterns: {str(e)}", exc_info=True
            )
            return {}

    def _calculate_global_property_metrics(
        self,
        pattern_data: Dict,
        current_labels: Set[str],
        nodes_df: pd.DataFrame,
        properties_df: pd.DataFrame,
    ) -> Dict[str, float]:
        """
        Calculates metrics for global property pattern analysis.
        """
        try:
            # Calculate label relevance
            label_overlap = sum(
                score
                for label, score in pattern_data["label_scores"].items()
                if label in current_labels
            )

            # Calculate structural metrics
            structural_score = (
                pattern_data["avg_property_diversity"]
                + pattern_data["avg_relationship_diversity"]
            ) / 2

            # Calculate uniqueness score (inverse of global frequency)
            total_nodes = len(nodes_df["node_id"].unique())
            uniqueness_score = 1 - (pattern_data["total_occurrences"] / total_nodes)

            return {
                "label_relevance": label_overlap,
                "structural_score": structural_score,
                "uniqueness_score": uniqueness_score,
                "total_occurrences": pattern_data["total_occurrences"],
            }

        except Exception as e:
            self.logger.error(
                f"Error calculating global property metrics: {str(e)}", exc_info=True
            )
            return {}

    def _generate_property_value_suggestions(
        self, pattern_data: Dict, metrics: Dict[str, float]
    ) -> List[Tuple[str, float]]:
        """
        Generates value suggestions with confidence scores for a property pattern.
        """
        try:
            suggestions = []
            total_occurrences = metrics["total_occurrences"]

            for value, stats in pattern_data["value_patterns"].items():
                # Calculate base confidence from frequency
                frequency_score = stats["node_id"] / total_occurrences

                # Calculate confidence score
                confidence = self._calculate_global_property_confidence(
                    frequency_score,
                    stats["is_complex"],
                    metrics["label_relevance"],
                    metrics["structural_score"],
                    metrics["uniqueness_score"],
                )

                if confidence >= 40.0:  # Higher threshold for global suggestions
                    suggestions.append((value, confidence))

            # Sort by confidence and take top 3
            return sorted(suggestions, key=lambda x: x[1], reverse=True)[:3]

        except Exception as e:
            self.logger.error(
                f"Error generating property value suggestions: {str(e)}", exc_info=True
            )
            return []

    def _calculate_global_property_confidence(
        self,
        frequency_score: float,
        complexity_score: float,
        label_relevance: float,
        structural_score: float,
        uniqueness_score: float,
    ) -> float:
        """
        Calculates confidence score for global property suggestions.
        Uses different weights than local analysis to favor creative but relevant suggestions.
        """
        try:
            # Base confidence from frequency (20% weight)
            confidence = frequency_score * 0.2

            # Label relevance (30% weight)
            confidence += label_relevance * 0.3

            # Structural relevance (20% weight)
            confidence += structural_score * 0.2

            # Value complexity (15% weight)
            complexity_factor = 1.0 - abs(complexity_score - 0.5) * 0.4
            confidence += complexity_factor * 0.15

            # Uniqueness bonus (15% weight)
            # Scale uniqueness to favor moderately unique properties
            uniqueness_factor = 1.0 - abs(uniqueness_score - 0.7) * 2
            confidence += uniqueness_factor * 0.15

            # Convert to percentage and ensure bounds
            confidence = min(max(confidence * 100, 0), 100)

            return round(confidence, 2)

        except Exception as e:
            self.logger.error(
                f"Error calculating global property confidence: {str(e)}", exc_info=True
            )
            return 0.0

    def _log_global_property_analysis(
        self, creative_properties: Dict[str, List[Tuple[str, float]]]
    ) -> None:
        """Logs detailed results of global property pattern analysis"""
        self.logger.debug("\nGlobal Property Analysis Results:")
        self.logger.debug(
            f"Total creative properties found: {len(creative_properties)}"
        )

        for prop_key, values in creative_properties.items():
            self.logger.debug(f"\nProperty: {prop_key}")
            for value, confidence in values:
                self.logger.debug(
                    f"- Value: {value[:50]}... Confidence: {confidence:.2f}%"
                )

    def _analyze_global_relationships(
        self,
        global_dfs: Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame],
        local_suggestions: Dict[str, Any],
        node_data: Dict[str, Any],
    ) -> List[Tuple[str, str, float]]:
        """
        Analyzes global relationship patterns to find creative connection suggestions.
        Focuses on discovering meaningful cross-domain relationships and bridge patterns.

        Args:
            global_dfs: Tuple of (nodes_df, relationships_df, properties_df) for global patterns
            local_suggestions: Dictionary containing local pattern suggestions
            node_data: Current node data dictionary

        Returns:
            List[Tuple[str, str, float]]: List of (relationship_type, target_type, confidence)
            tuples, sorted by confidence
        """
        try:
            nodes_df, relationships_df, _ = global_dfs

            # Skip if DataFrames are empty
            if relationships_df.empty or nodes_df.empty:
                self.logger.debug("No global relationships to analyze")
                return []

            # Get current context
            current_labels = set(node_data.get("labels", []))
            current_relationships = {
                (rel.get("type", ""), rel.get("target", ""))
                for rel in node_data.get("relationships", [])
                if isinstance(rel, dict)
            }

            # Get local suggestions to avoid duplication
            local_relationships = {
                (rel_type, target)
                for rel_type, target, _ in local_suggestions.get("relationships", [])
            }

            # Find global patterns
            relationship_patterns = self._analyze_global_relationship_patterns(
                nodes_df,
                relationships_df,
                current_labels,
                current_relationships | local_relationships,
            )

            # Generate suggestions from patterns
            creative_suggestions = self._generate_relationship_suggestions(
                relationship_patterns, current_labels
            )

            # Log analysis results
            self._log_global_relationship_analysis(creative_suggestions)

            return creative_suggestions

        except Exception as e:
            self.logger.error(
                f"Error in global relationship analysis: {str(e)}", exc_info=True
            )
            return []

    def _analyze_global_relationship_patterns(
        self,
        nodes_df: pd.DataFrame,
        relationships_df: pd.DataFrame,
        current_labels: Set[str],
        existing_relationships: Set[Tuple[str, str]],
    ) -> Dict[str, Dict]:
        """
        Analyzes global relationship patterns to find potential bridges and cross-domain connections.
        """
        try:
            patterns = {}

            # Group relationships by type
            rel_groups = relationships_df.groupby("relationship_type")

            for rel_type, group in rel_groups:
                # Skip if this relationship type is too rare
                if len(group) < 3:
                    continue

                # Analyze connection patterns
                source_labels = group["source_labels"].str.split("|").explode()
                target_labels = group["target_labels"].str.split("|").explode()

                # Calculate label frequencies
                source_label_freq = source_labels.value_counts().to_dict()
                target_label_freq = target_labels.value_counts().to_dict()

                # Find label pairs (connection patterns)
                label_pairs = []
                for _, row in group.iterrows():
                    sources = set(row["source_labels"].split("|"))
                    targets = set(row["target_labels"].split("|"))
                    for s in sources:
                        for t in targets:
                            if (rel_type, t) not in existing_relationships:
                                label_pairs.append((s, t))

                # Calculate pair frequencies
                pair_freq = Counter(label_pairs)

                # Store pattern data
                patterns[rel_type] = {
                    "total_occurrences": len(group),
                    "source_labels": source_label_freq,
                    "target_labels": target_label_freq,
                    "label_pairs": pair_freq,
                    "avg_property_count": group["property_count"].mean(),
                    "bidirectional_ratio": (
                        group["direction"]
                        .value_counts(normalize=True)
                        .get("incoming", 0)
                    ),
                }

            return patterns

        except Exception as e:
            self.logger.error(
                f"Error analyzing global relationship patterns: {str(e)}", exc_info=True
            )
            return {}

    def _generate_relationship_suggestions(
        self, patterns: Dict[str, Dict], current_labels: Set[str]
    ) -> List[Tuple[str, str, float]]:
        """
        Generates relationship suggestions from global patterns.
        """
        try:
            suggestions = []

            for rel_type, pattern_data in patterns.items():
                # Analyze each label pair for this relationship type
                for (source_label, target_label), pair_count in pattern_data[
                    "label_pairs"
                ].items():
                    # Skip if source label doesn't match current node
                    if source_label not in current_labels:
                        continue

                    # Calculate metrics for this connection pattern
                    metrics = self._calculate_global_relationship_metrics(
                        rel_type, source_label, target_label, pair_count, pattern_data
                    )

                    # Calculate confidence score
                    confidence = self._calculate_global_relationship_confidence(metrics)

                    if confidence >= 40.0:  # Higher threshold for global suggestions
                        suggestions.append((rel_type, target_label, confidence))

            # Sort by confidence and take top suggestions
            return sorted(suggestions, key=lambda x: x[2], reverse=True)[:5]

        except Exception as e:
            self.logger.error(
                f"Error generating relationship suggestions: {str(e)}", exc_info=True
            )
            return []

    def _calculate_global_relationship_metrics(
        self,
        rel_type: str,
        source_label: str,
        target_label: str,
        pair_count: int,
        pattern_data: Dict,
    ) -> Dict[str, float]:
        """
        Calculates metrics for global relationship pattern analysis.
        """
        try:
            total_occurrences = pattern_data["total_occurrences"]

            # Frequency of this specific connection pattern
            pattern_frequency = pair_count / total_occurrences

            # Calculate source label significance
            source_significance = (
                pattern_data["source_labels"].get(source_label, 0) / total_occurrences
            )

            # Calculate target label significance
            target_significance = (
                pattern_data["target_labels"].get(target_label, 0) / total_occurrences
            )

            # Calculate structural metrics
            avg_property_complexity = (
                pattern_data["avg_property_count"] / 10
            )  # Normalize
            bidirectional_score = min(pattern_data["bidirectional_ratio"] * 2, 1.0)

            return {
                "pattern_frequency": pattern_frequency,
                "source_significance": source_significance,
                "target_significance": target_significance,
                "property_complexity": avg_property_complexity,
                "bidirectional_score": bidirectional_score,
                "total_occurrences": total_occurrences,
                "pair_count": pair_count,
            }

        except Exception as e:
            self.logger.error(
                f"Error calculating global relationship metrics: {str(e)}",
                exc_info=True,
            )
            return {}

    def _calculate_global_relationship_confidence(
        self, metrics: Dict[str, float]
    ) -> float:
        """
        Calculates confidence score for global relationship suggestions.
        Emphasizes meaningful cross-domain connections.
        """
        try:
            if not metrics or metrics["pair_count"] < 2:
                return 0.0

            # Pattern frequency (25% weight)
            confidence = metrics["pattern_frequency"] * 0.25

            # Label significance (30% weight)
            label_score = (
                metrics["source_significance"] + metrics["target_significance"]
            ) / 2
            confidence += label_score * 0.3

            # Structural relevance (25% weight)
            structural_score = (
                metrics["property_complexity"] + metrics["bidirectional_score"]
            ) / 2
            confidence += structural_score * 0.25

            # Statistical significance (20% weight)
            significance_factor = min(metrics["pair_count"] / 5, 1.0)
            confidence += significance_factor * 0.2

            # Convert to percentage and ensure bounds
            confidence = min(max(confidence * 100, 0), 100)

            return round(confidence, 2)

        except Exception as e:
            self.logger.error(
                f"Error calculating global relationship confidence: {str(e)}",
                exc_info=True,
            )
            return 0.0

    def _log_global_relationship_analysis(
        self, suggestions: List[Tuple[str, str, float]]
    ) -> None:
        """Logs detailed results of global relationship pattern analysis"""
        self.logger.debug("\nGlobal Relationship Analysis Results:")
        self.logger.debug(f"Total creative relationships found: {len(suggestions)}")

        for rel_type, target_label, confidence in suggestions:
            self.logger.debug(f"\nRelationship Type: {rel_type}")
            self.logger.debug(f"Target Label: {target_label}")
            self.logger.debug(f"Confidence: {confidence:.2f}%")

    def _analyze_global_tags(
        self,
        global_dfs: Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame],
        local_suggestions: Dict[str, Any],
        node_data: Dict[str, Any],
    ) -> List[Tuple[str, float]]:
        """
        Analyzes global tag patterns to find creative tag suggestions.
        Focuses on discovering meaningful cross-domain tags and emergent patterns.

        Args:
            global_dfs: Tuple of (nodes_df, relationships_df, properties_df) for global patterns
            local_suggestions: Dictionary containing local pattern suggestions
            node_data: Current node data dictionary

        Returns:
            List[Tuple[str, float]]: List of (tag, confidence) tuples, sorted by confidence
        """
        try:
            nodes_df, _, properties_df = global_dfs

            # Skip if DataFrames are empty
            if properties_df.empty or nodes_df.empty:
                self.logger.debug("No global data to analyze for tags")
                return []

            # Get current context
            current_tags = set(node_data.get("properties", {}).get("tags", []))
            current_labels = set(node_data.get("labels", []))

            # Get local suggestions to avoid duplication
            local_tags = {tag for tag, _ in local_suggestions.get("tags", [])}
            exclude_tags = current_tags | local_tags

            # Find global tag patterns
            tag_patterns = self._analyze_global_tag_patterns(
                nodes_df, properties_df, current_labels, exclude_tags
            )

            # Generate suggestions from patterns
            creative_suggestions = self._generate_tag_suggestions(
                tag_patterns, current_labels, node_data
            )

            # Log analysis results
            self._log_global_tag_analysis(creative_suggestions, tag_patterns)

            return creative_suggestions

        except Exception as e:
            self.logger.error(f"Error in global tag analysis: {str(e)}", exc_info=True)
            return []

    def _analyze_global_tag_patterns(
        self,
        nodes_df: pd.DataFrame,
        properties_df: pd.DataFrame,
        current_labels: Set[str],
        exclude_tags: Set[str],
    ) -> Dict[str, Dict]:
        """
        Analyzes global tag patterns across different node types.
        """
        try:
            patterns = {}
            tag_rows = properties_df[properties_df["property_key"] == "tags"]

            if tag_rows.empty:
                return {}

            # Collect tag data across all nodes
            for _, row in tag_rows.iterrows():
                try:
                    # Parse tags
                    node_tags = json.loads(row["property_value"])
                    if not isinstance(node_tags, list):
                        continue

                    node_id = row["node_id"]
                    node_info = nodes_df[nodes_df["node_id"] == node_id].iloc[0]
                    node_labels = set(node_info["labels"].split("|"))

                    # Process each tag
                    for tag in node_tags:
                        if tag in exclude_tags:
                            continue

                        if tag not in patterns:
                            patterns[tag] = {
                                "occurrences": 0,
                                "label_distribution": Counter(),
                                "co_occurring_tags": Counter(),
                                "node_properties": Counter(),
                                "relationship_types": Counter(),
                                "nodes": set(),
                                "property_diversity_scores": [],
                                "relationship_diversity_scores": [],
                            }

                        # Update pattern data
                        patterns[tag]["occurrences"] += 1
                        patterns[tag]["nodes"].add(node_id)
                        patterns[tag]["property_diversity_scores"].append(
                            node_info["property_diversity"]
                        )
                        patterns[tag]["relationship_diversity_scores"].append(
                            node_info["relationship_diversity"]
                        )

                        # Update label distribution
                        for label in node_labels:
                            patterns[tag]["label_distribution"][label] += 1

                        # Update co-occurring tags
                        for co_tag in node_tags:
                            if co_tag != tag and co_tag not in exclude_tags:
                                patterns[tag]["co_occurring_tags"][co_tag] += 1

                        # Update property patterns
                        node_properties = properties_df[
                            (properties_df["node_id"] == node_id)
                            & (properties_df["property_key"] != "tags")
                        ]
                        for _, prop in node_properties.iterrows():
                            patterns[tag]["node_properties"][prop["property_key"]] += 1

                except (json.JSONDecodeError, IndexError):
                    continue

            return patterns

        except Exception as e:
            self.logger.error(
                f"Error analyzing global tag patterns: {str(e)}", exc_info=True
            )
            return {}

    def _generate_tag_suggestions(
        self,
        patterns: Dict[str, Dict],
        current_labels: Set[str],
        node_data: Dict[str, Any],
    ) -> List[Tuple[str, float]]:
        """
        Generates tag suggestions from global patterns.
        """
        try:
            suggestions = []

            # Get current node's properties
            current_properties = set(node_data.get("properties", {}).keys())

            for tag, pattern_data in patterns.items():
                # Skip tags with too few occurrences
                if len(pattern_data["nodes"]) < 3:
                    continue

                # Calculate metrics for this tag
                metrics = self._calculate_global_tag_metrics(
                    tag, pattern_data, current_labels, current_properties
                )

                # Calculate confidence score
                confidence = self._calculate_global_tag_confidence(metrics)

                if confidence >= 40.0:  # Higher threshold for global suggestions
                    suggestions.append((tag, confidence))

            # Sort by confidence and take top suggestions
            return sorted(suggestions, key=lambda x: x[1], reverse=True)[:5]

        except Exception as e:
            self.logger.error(
                f"Error generating tag suggestions: {str(e)}", exc_info=True
            )
            return []

    def _calculate_global_tag_metrics(
        self,
        tag: str,
        pattern_data: Dict,
        current_labels: Set[str],
        current_properties: Set[str],
    ) -> Dict[str, float]:
        """
        Calculates metrics for global tag pattern analysis.
        """
        try:
            total_nodes = len(pattern_data["nodes"])

            # Calculate label relevance
            label_counts = pattern_data["label_distribution"]
            label_overlap = sum(
                count
                for label, count in label_counts.items()
                if label in current_labels
            )
            label_relevance = label_overlap / sum(label_counts.values())

            # Calculate property relevance
            property_counts = pattern_data["node_properties"]
            property_overlap = sum(
                count
                for prop, count in property_counts.items()
                if prop in current_properties
            )
            property_relevance = property_overlap / sum(property_counts.values())

            # Calculate diversity scores
            avg_property_diversity = statistics.mean(
                pattern_data["property_diversity_scores"]
            )
            avg_relationship_diversity = statistics.mean(
                pattern_data["relationship_diversity_scores"]
            )

            # Calculate contextual significance
            co_occurrence_strength = (
                len(pattern_data["co_occurring_tags"]) / total_nodes
            )

            return {
                "label_relevance": label_relevance,
                "property_relevance": property_relevance,
                "avg_property_diversity": avg_property_diversity,
                "avg_relationship_diversity": avg_relationship_diversity,
                "co_occurrence_strength": co_occurrence_strength,
                "total_occurrences": pattern_data["occurrences"],
                "unique_nodes": total_nodes,
            }

        except Exception as e:
            self.logger.error(
                f"Error calculating global tag metrics: {str(e)}", exc_info=True
            )
            return {}

    def _calculate_global_tag_confidence(self, metrics: Dict[str, float]) -> float:
        """
        Calculates confidence score for global tag suggestions.
        Emphasizes meaningful cross-domain relevance.
        """
        try:
            if not metrics or metrics["unique_nodes"] < 3:
                return 0.0

            # Label relevance (30% weight)
            confidence = metrics["label_relevance"] * 0.3

            # Property relevance (25% weight)
            confidence += metrics["property_relevance"] * 0.25

            # Structural diversity (25% weight)
            diversity_score = (
                metrics["avg_property_diversity"]
                + metrics["avg_relationship_diversity"]
            ) / 2
            confidence += diversity_score * 0.25

            # Contextual significance (20% weight)
            context_score = (
                metrics["co_occurrence_strength"] * 0.7
                + min(metrics["unique_nodes"] / 10, 1.0) * 0.3
            )
            confidence += context_score * 0.2

            # Convert to percentage and ensure bounds
            confidence = min(max(confidence * 100, 0), 100)

            return round(confidence, 2)

        except Exception as e:
            self.logger.error(
                f"Error calculating global tag confidence: {str(e)}", exc_info=True
            )
            return 0.0

    def _log_global_tag_analysis(
        self, suggestions: List[Tuple[str, float]], patterns: Dict[str, Dict]
    ) -> None:
        """Logs detailed results of global tag pattern analysis"""
        self.logger.debug("\nGlobal Tag Analysis Results:")
        self.logger.debug(f"Total creative tags found: {len(suggestions)}")

        for tag, confidence in suggestions:
            pattern = patterns.get(tag, {})
            self.logger.debug(f"\nTag: {tag}")
            self.logger.debug(f"Confidence: {confidence:.2f}%")
            self.logger.debug(f"Total Occurrences: {pattern.get('occurrences', 0)}")
            self.logger.debug(f"Unique Nodes: {len(pattern.get('nodes', set()))}")

            if pattern.get("label_distribution"):
                self.logger.debug("Top Labels:")
                for label, count in Counter(pattern["label_distribution"]).most_common(
                    3
                ):
                    self.logger.debug(f"  - {label}: {count} occurrences")

            if pattern.get("co_occurring_tags"):
                self.logger.debug("Top Co-occurring Tags:")
                for co_tag, count in Counter(pattern["co_occurring_tags"]).most_common(
                    3
                ):
                    self.logger.debug(f"  - {co_tag}: {count} occurrences")
