"""
This module provides worker classes for performing Neo4j database operations in separate threads.
It includes classes for querying, writing, deleting, and generating suggestions for nodes.
"""

import json
import logging
import traceback
from collections import Counter
from datetime import timedelta, datetime
from threading import Lock
from typing import Any, Callable, Dict, List, Optional, Tuple, Set

import pandas as pd
from PyQt6.QtCore import QThread, pyqtSignal
from neo4j import GraphDatabase

from .neo4j_utils import (
    validate_neo4j_result,
    validate_dataframe,
    ValidationError,
)


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
        self._cache = {}
        self._cache_timestamps = {}
        self._cache_ttl = timedelta(minutes=60)
        self._cache_lock = Lock()

    # === Main Operation Flow ===

    def execute_operation(self) -> None:
        """Main execution flow with improved error handling"""
        try:
            with self._driver.session() as session:
                # Fetch and validate data
                similar_nodes = self._get_similar_nodes(session)
                validate_neo4j_result(similar_nodes)

                # Convert similar nodes using node pattern
                similar_df = pd.DataFrame(
                    self._normalize_neo4j_results(similar_nodes, "node")
                )

                # Process global patterns
                global_patterns = self._get_global_patterns(session)
                validate_neo4j_result(global_patterns)

                # Convert global patterns using pattern type
                global_df = pd.DataFrame(
                    self._normalize_neo4j_results(global_patterns, "pattern")
                )

                # Debug DataFrame contents
                self.logger.debug(
                    f"Similar nodes columns: {similar_df.columns.tolist()}"
                )
                self.logger.debug(
                    f"Global patterns columns: {global_df.columns.tolist()}"
                )

                # Validate DataFrame structure
                required_columns = {"properties", "labels", "relationships"}
                validate_dataframe(similar_df, required_columns)
                validate_dataframe(global_df, required_columns)

                # Process suggestions
                try:
                    local_suggestions = self._analyze_local_patterns(similar_df)
                except Exception as e:
                    self.logger.error("Error in local pattern analysis", exc_info=True)
                    local_suggestions = self._empty_suggestions()

                try:
                    creative_suggestions = self._analyze_global_patterns(
                        global_df, local_suggestions
                    )
                except Exception as e:
                    self.logger.error("Error in global pattern analysis", exc_info=True)
                    creative_suggestions = self._empty_suggestions()

                final_suggestions = self._merge_suggestions(
                    local_suggestions, creative_suggestions
                )
                self.suggestions_ready.emit(final_suggestions)

        except ValidationError as e:
            self.logger.error(f"Validation error: {str(e)}", exc_info=True)
            self.error_occurred.emit(f"Data validation failed: {str(e)}")
        except Exception as e:
            self.logger.error(f"Unexpected error: {str(e)}", exc_info=True)
            self.error_occurred.emit(f"An unexpected error occurred: {str(e)}")

    # === Data Gathering ===

    def _get_similar_nodes(self, session: Any) -> List[Dict[str, Any]]:
        """Get nodes with similar structure"""
        try:
            query = """
                    MATCH (n)
                    WHERE any(label IN $labels WHERE label IN labels(n)) 
                    AND n.name <> $name
                    WITH n, labels(n) as node_labels
                    OPTIONAL MATCH (n)-[r]-()
                    WITH n, node_labels, collect(r) as rels
                    RETURN {
                        node: n,
                        labels: node_labels,
                        relationships: [rel in rels | {
                            type: type(rel),
                            direction: CASE WHEN startNode(rel) = n THEN 'outgoing' ELSE 'incoming' END,
                            properties: properties(rel)
                        }]
                    } as result
                    LIMIT 200
                    """

            result = session.run(
                query,
                {
                    "labels": self.node_data.get("labels", []),
                    "name": self.node_data.get("name", ""),
                },
            )
            nodes = list(result)
            self.logger.debug(f"Found {len(nodes)} similar nodes")
            return nodes

        except Exception as e:
            self.logger.error(f"Error in _get_similar_nodes: {str(e)}", exc_info=True)
            return []

    def _get_global_patterns(self, session: Any) -> List[Dict[str, Any]]:
        """Get broader pattern data without label restrictions"""
        try:
            # Check cache first
            cache_key = f"global_patterns_{self.node_data.get('labels', [''])[0]}"
            cached_patterns = self._get_from_cache(cache_key)
            if cached_patterns:
                self.logger.debug("Using cached global patterns")
                return cached_patterns

            # Query for global patterns
            query = """
            MATCH (n)
            WHERE NOT n.name = $name  // Exclude current node
            WITH n, labels(n) as node_labels
            OPTIONAL MATCH (n)-[r]->(target)
            WITH n, node_labels,
                 collect({
                    type: type(r),
                    target_labels: labels(target),
                    target_name: target.name,
                    direction: 'outgoing',
                    properties: properties(r)
                 }) as outgoing
            OPTIONAL MATCH (n)<-[r2]-(source)
            WITH n, node_labels, outgoing,
                 collect({
                    type: type(r2),
                    source_labels: labels(source),
                    source_name: source.name,
                    direction: 'incoming',
                    properties: properties(r2)
                 }) as incoming
            RETURN {
                name: n.name,
                properties: properties(n),
                labels: node_labels,
                relationships: outgoing + incoming,
                tags: n.tags
            } as pattern
            LIMIT 50
            """

            self.logger.debug("Querying for global patterns")
            result = session.run(query, {"name": self.node_data.get("name", "")})
            patterns = list(result)

            # Store in cache
            self._store_in_cache(cache_key, patterns)

            self.logger.debug(f"Found {len(patterns)} global patterns")
            return patterns

        except Exception as e:
            self.logger.error(f"Error in _get_global_patterns: {str(e)}", exc_info=True)
            return []

    # === Pattern Analysis ===

    def _analyze_local_patterns(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Analyze patterns from similar nodes with enhanced logging"""
        try:
            self.logger.debug(f"Starting local pattern analysis with {len(df)} records")
            self.logger.debug(f"DataFrame columns: {df.columns.tolist()}")

            if df.empty:
                self.logger.debug("Empty DataFrame, returning empty suggestions")
                return self._empty_suggestions()

            # Extract patterns
            patterns = {"tags": [], "properties": {}, "relationships": []}

            # Process properties
            all_property_keys = set()
            property_values = {}

            for _, row in df.iterrows():
                props = row["properties"]
                if not isinstance(props, dict):
                    continue

                # Collect property keys and values
                for key, value in props.items():
                    if key not in all_property_keys:
                        all_property_keys.add(key)
                        property_values[key] = []
                    property_values[key].append(str(value))

            # Process relationships
            for _, row in df.iterrows():
                rels = row.get("relationships", [])
                if not isinstance(rels, list):
                    continue

                for rel in rels:
                    if not isinstance(rel, dict):
                        continue

                    rel_type = rel.get("type")
                    if rel_type:
                        patterns["relationships"].append(rel_type)

            # Calculate frequencies
            for key, values in property_values.items():
                if len(values) > 0:
                    value_counts = Counter(values)
                    top_values = value_counts.most_common(3)
                    patterns["properties"][key] = [
                        (value, count / len(df) * 100) for value, count in top_values
                    ]

            self.logger.debug(f"Found {len(patterns['properties'])} property patterns")
            self.logger.debug(
                f"Found {len(patterns['relationships'])} relationship patterns"
            )

            return patterns

        except Exception as e:
            self.logger.error(
                f"Error in local pattern analysis: {str(e)}", exc_info=True
            )
            return self._empty_suggestions()

    def _analyze_global_patterns(
        self, df: pd.DataFrame, local_suggestions: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Find creative suggestions from global patterns"""
        if df.empty:
            return self._empty_suggestions()

        try:
            return {
                "tags": self._find_creative_tags(df, local_suggestions),
                "properties": self._find_creative_properties(df, local_suggestions),
                "relationships": self._find_creative_relationships(
                    df, local_suggestions
                ),
            }
        except Exception as e:
            self.logger.error(
                f"Error in global pattern analysis: {str(e)}", exc_info=True
            )
            return self._empty_suggestions()

    # === Pattern Extraction Methods ===

    def _extract_tag_suggestions(self, df: pd.DataFrame) -> List[Tuple[str, float]]:
        """Extract and score tag suggestions"""
        try:
            # Collect all tags from properties
            all_tags = []
            current_tags = set(self.node_data.get("properties", {}).get("tags", []))

            # Flatten tags from all nodes
            for tags in df["properties"].apply(lambda x: x.get("tags", [])):
                all_tags.extend(tags)

            # Count and calculate confidence
            tag_counts = Counter(all_tags)
            total_nodes = len(df)

            # Calculate confidence and filter out current tags
            suggestions = [
                (tag, (count / total_nodes) * 100)
                for tag, count in tag_counts.items()
                if tag not in current_tags
            ]

            # Sort by confidence and return top 5
            return sorted(suggestions, key=lambda x: x[1], reverse=True)[:5]

        except Exception as e:
            self.logger.error(f"Error extracting tags: {str(e)}", exc_info=True)
            return []

    def _extract_property_suggestions(
        self, df: pd.DataFrame
    ) -> Dict[str, List[Tuple[str, float]]]:
        """Extract and score property suggestions"""
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
            current_props = self.node_data.get("properties", {})

            # Analyze properties across nodes
            for _, row in df.iterrows():
                props = row["properties"]
                for key, value in props.items():
                    if key in exclude_props:
                        continue

                    if key not in suggestions:
                        suggestions[key] = []

                    if isinstance(value, (list, dict)):
                        value = json.dumps(value)

                    suggestions[key].append(str(value))

            # Calculate confidence scores
            result = {}
            for key, values in suggestions.items():
                if key in current_props:
                    continue

                value_counts = Counter(values)
                total = len(values)

                # Get top 3 values with confidence scores
                result[key] = [
                    (value, (count / total) * 100)
                    for value, count in value_counts.most_common(3)
                ]

            return result

        except Exception as e:
            self.logger.error(f"Error extracting properties: {str(e)}", exc_info=True)
            return {}

    def _extract_relationship_suggestions(
        self, df: pd.DataFrame
    ) -> List[Tuple[str, str, str, Dict, float]]:
        """Extract and score relationship suggestions with improved error handling"""
        try:
            relationship_patterns = []
            current_rels = set()

            # Get current relationships if they exist
            if self.node_data and "relationships" in self.node_data:
                current_rels = {
                    (r.get("type"), r.get("target"))
                    for r in self.node_data["relationships"]
                    if isinstance(r, dict) and "type" in r and "target" in r
                }

            # Process relationships from DataFrame
            for rel_data in df["relationships"].dropna():
                if not isinstance(rel_data, list):
                    continue

                for rel in rel_data:
                    if not isinstance(rel, dict):
                        continue

                    rel_key = (rel.get("type"), rel.get("target"))
                    if None not in rel_key and rel_key not in current_rels:
                        relationship_patterns.append(
                            (
                                rel.get("type", ""),
                                rel.get("target", ""),
                                rel.get("direction", "outgoing"),
                                rel.get("properties", {}),
                            )
                        )

            # Calculate confidence scores
            pattern_counts = Counter(relationship_patterns)
            total_nodes = len(df)

            if total_nodes == 0:
                return []

            suggestions = [
                (*pattern, (count / total_nodes) * 100)
                for pattern, count in pattern_counts.most_common(5)
            ]

            return suggestions

        except Exception as e:
            self.logger.error(
                f"Error extracting relationships: {str(e)}", exc_info=True
            )
            return []

    # === Creative Pattern Finding ===

    def _find_creative_tags(
        self, df: pd.DataFrame, local_suggestions: Dict[str, Any]
    ) -> List[Tuple[str, float]]:
        """Find creative tag suggestions based on global patterns"""
        try:
            # Get tags from nodes with similar property patterns
            property_signature = self._get_property_signature(
                self.node_data.get("properties", {})
            )

            similar_property_nodes = df[
                df["properties"].apply(
                    lambda x: self._property_similarity(
                        self._get_property_signature(x), property_signature
                    )
                    > 0.3
                )
            ]

            # Get tags from these nodes
            creative_tags = []
            local_tags = {tag for tag, _ in local_suggestions["tags"]}

            for props in similar_property_nodes["properties"]:
                creative_tags.extend(props.get("tags", []))

            # Calculate confidence based on structural similarity
            tag_counts = Counter(creative_tags)
            total = len(similar_property_nodes)

            if total == 0:
                return []

            suggestions = [
                (tag, (count / total) * 70)  # Lower confidence for creative suggestions
                for tag, count in tag_counts.items()
                if tag not in local_tags
            ]

            return sorted(suggestions, key=lambda x: x[1], reverse=True)[:3]

        except Exception as e:
            self.logger.error(f"Error finding creative tags: {str(e)}", exc_info=True)
            return []

    def _find_creative_properties(
        self, df: pd.DataFrame, local_suggestions: Dict[str, Any]
    ) -> Dict[str, List[Tuple[str, float]]]:
        """Find creative property suggestions based on global patterns"""
        try:
            # Find nodes that share some but not all properties
            current_props = set(self.node_data.get("properties", {}).keys())
            local_suggestion_props = set(local_suggestions["properties"].keys())

            creative_props = {}

            for _, row in df.iterrows():
                node_props = row["properties"]
                shared_props = current_props.intersection(node_props.keys())

                # If nodes share some properties, look at their unique properties
                if shared_props and len(shared_props) >= 2:
                    unique_props = (
                        set(node_props.keys()) - current_props - local_suggestion_props
                    )

                    for prop in unique_props:
                        if prop not in creative_props:
                            creative_props[prop] = []
                        creative_props[prop].append(str(node_props[prop]))

            # Calculate confidence scores
            result = {}
            for prop, values in creative_props.items():
                value_counts = Counter(values)
                total = len(values)

                result[prop] = [
                    (
                        value,
                        (count / total) * 60,
                    )  # Lower confidence for creative suggestions
                    for value, count in value_counts.most_common(2)
                ]

            return result

        except Exception as e:
            self.logger.error(
                f"Error finding creative properties: {str(e)}", exc_info=True
            )
            return {}

    def _find_creative_relationships(
        self, df: pd.DataFrame, local_suggestions: Dict[str, Any]
    ) -> List[Tuple[str, str, str, Dict, float]]:
        """Find creative relationship suggestions based on global patterns"""
        try:
            # Look for bridge relationships (connections between different node types)
            current_labels = set(self.node_data.get("labels", []))
            local_rels = {(r[0], r[1]) for r in local_suggestions["relationships"]}

            bridge_patterns = []

            for _, row in df.iterrows():
                node_labels = set(row["labels"])

                # If nodes share some labels, look at their unique relationships
                if current_labels.intersection(node_labels):
                    for rel in row["relationships"]:
                        rel_key = (rel["type"], rel["target"])

                        if rel_key not in local_rels:
                            bridge_patterns.append(
                                (
                                    rel["type"],
                                    rel["target"],
                                    rel["direction"],
                                    rel.get("properties", {}),
                                )
                            )

            # Calculate confidence scores
            pattern_counts = Counter(bridge_patterns)
            total = sum(pattern_counts.values())

            if total == 0:
                return []

            suggestions = [
                (
                    *pattern,
                    (count / total) * 50,
                )  # Lower confidence for creative suggestions
                for pattern, count in pattern_counts.most_common(3)
            ]

            return suggestions

        except Exception as e:
            self.logger.error(
                f"Error finding creative relationships: {str(e)}", exc_info=True
            )
            return []

    # === Cache Management ===

    def _get_from_cache(self, key: str) -> Optional[Any]:
        """Thread-safe cache retrieval"""
        with self._cache_lock:
            if key not in self._cache:
                return None

            if datetime.now() - self._cache_timestamps[key] > self._cache_ttl:
                self._remove_from_cache(key)
                return None

            return self._cache[key]

    def _store_in_cache(self, key: str, value: Any) -> None:
        """Thread-safe cache storage"""
        with self._cache_lock:
            self._cache[key] = value
            self._cache_timestamps[key] = datetime.now()

    def _remove_from_cache(self, key: str) -> None:
        """Remove cache entry"""
        self._cache.pop(key, None)
        self._cache_timestamps.pop(key, None)

    # === Utility Methods ===

    def _normalize_neo4j_results(self, results, pattern_type="node"):
        """Normalize Neo4j results for DataFrame conversion

        Args:
            results: Neo4j result records
            pattern_type: Either 'node' or 'pattern' based on query type
        """
        normalized = []
        for record in results:
            try:
                # Handle differently based on query type
                if pattern_type == "node":
                    data = record.get("result", {})
                    if not isinstance(data, dict):
                        continue

                    node_data = data.get("node", {})
                    if not isinstance(node_data, dict):
                        continue

                    # Extract properties from Neo4j node
                    properties = {}
                    if hasattr(node_data, "properties"):
                        properties = dict(node_data.properties)
                    else:
                        properties = node_data.get("properties", {})

                    row = {
                        "properties": properties,
                        "labels": data.get("labels", []),
                        "relationships": data.get("relationships", []),
                    }
                else:  # pattern type
                    data = record.get("pattern", {})
                    if not isinstance(data, dict):
                        continue

                    row = {
                        "properties": data.get("properties", {}),
                        "labels": data.get("labels", []),
                        "relationships": data.get("relationships", []),
                    }

                normalized.append(row)
            except Exception as e:
                self.logger.error(f"Error normalizing record: {str(e)}", exc_info=True)
                continue

        self.logger.debug(f"Normalized {len(normalized)} records")
        return normalized

    def _empty_suggestions(self) -> Dict[str, Any]:
        """Return empty suggestion structure"""
        return {"tags": [], "properties": {}, "relationships": []}

    def _get_property_signature(self, properties: Dict) -> Set[str]:
        """Get a signature of property keys and types"""
        return {f"{k}:{type(v).__name__}" for k, v in properties.items()}

    def _property_similarity(self, sig1: Set[str], sig2: Set[str]) -> float:
        """Calculate Jaccard similarity between property signatures"""
        if not sig1 or not sig2:
            return 0.0
        return len(sig1.intersection(sig2)) / len(sig1.union(sig2))

    def _merge_suggestions(
        self, local: Dict[str, Any], creative: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Merge local and creative suggestions"""
        try:
            # Merge tags
            all_tags = list(set(local.get("tags", []) + creative.get("tags", [])))

            # Merge properties
            all_properties = {
                **local.get("properties", {}),
                **creative.get("properties", {}),
            }

            # Merge relationships
            all_relationships = list(
                set(local.get("relationships", []) + creative.get("relationships", []))
            )

            return {
                "tags": all_tags,
                "properties": all_properties,
                "relationships": all_relationships,
            }

        except Exception as e:
            self.logger.error(f"Error merging suggestions: {str(e)}", exc_info=True)
            return self._empty_suggestions()

    def _merge_tags(
        self,
        local_tags: List[Tuple[str, float]],
        creative_tags: List[Tuple[str, float]],
    ) -> List[Tuple[str, float]]:
        """Merge and dedupe tags, keeping highest confidence score"""
        tag_dict = {}

        # Process all tags
        for tag_list in [local_tags, creative_tags]:
            for tag, confidence in tag_list:
                # Keep highest confidence if tag appears multiple times
                if tag not in tag_dict or confidence > tag_dict[tag]:
                    tag_dict[tag] = confidence

        # Convert back to list of tuples
        return sorted(
            [(tag, conf) for tag, conf in tag_dict.items()],
            key=lambda x: x[1],
            reverse=True,
        )

    def _merge_properties(
        self,
        local_props: Dict[str, List[Tuple[str, float]]],
        creative_props: Dict[str, List[Tuple[str, float]]],
    ) -> Dict[str, List[Tuple[str, float]]]:
        """Merge property suggestions, combining values and keeping highest confidence scores"""
        merged = {}

        # Process all property keys
        for props_dict in [local_props, creative_props]:
            for key, values in props_dict.items():
                if key not in merged:
                    merged[key] = {}

                # Merge values for this property
                for value, confidence in values:
                    if value not in merged[key] or confidence > merged[key][value]:
                        merged[key][value] = confidence

        # Convert back to expected format
        return {
            key: sorted(
                [(val, conf) for val, conf in values.items()],
                key=lambda x: x[1],
                reverse=True,
            )
            for key, values in merged.items()
        }

    def _merge_relationships(
        self,
        local_rels: List[Tuple[str, str, str, Dict, float]],
        creative_rels: List[Tuple[str, str, str, Dict, float]],
    ) -> List[Tuple[str, str, str, Dict, float]]:
        """Merge relationship suggestions, deduping and keeping highest confidence scores"""
        rel_dict = {}

        # Process all relationships
        for rel_list in [local_rels, creative_rels]:
            for rel_type, target, direction, props, confidence in rel_list:
                key = (rel_type, target, direction)
                # Keep highest confidence version if relationship appears multiple times
                if key not in rel_dict or confidence > rel_dict[key][1]:
                    rel_dict[key] = (props, confidence)

        # Convert back to list of tuples
        return sorted(
            [
                (rel_type, target, direction, props, confidence)
                for (rel_type, target, direction), (
                    props,
                    confidence,
                ) in rel_dict.items()
            ],
            key=lambda x: x[4],
            reverse=True,
        )
