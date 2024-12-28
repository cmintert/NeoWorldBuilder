from datetime import datetime
from typing import Optional, List, Dict, Any, Callable

import networkx as nx
from structlog import get_logger

from config.config import Config
from core.neo4jmodel import Neo4jModel
from models.worker_model import WorkerOperation
from services.worker_manager_service import WorkerManagerService
from ui.components.search_component.query_builder import (
    Neo4jQueryBuilder,
    PropertyOperator,
    PropertyCondition,
    RelationshipPattern,
    RelationshipDirection,
)

logger = get_logger(__name__)


class SearchCriteria:
    """
    Container for search criteria configuration.
    Supports building both simple and complex searches.
    """

    def __init__(self, text: str) -> None:
        self.text = text
        self.labels: Optional[List[str]] = None
        self.properties: List[PropertyCondition] = []
        self.relationship_patterns: List[RelationshipPattern] = []
        self.include_relationships: bool = False
        self.case_sensitive: bool = False
        self.limit: Optional[int] = None


class SearchAnalysisService:
    """
    Service for handling search and analysis operations.
    Uses QueryBuilder for flexible query construction and NetworkX for analysis.
    """

    def __init__(
        self,
        model: Neo4jModel,
        config: Config,
        worker_manager: WorkerManagerService,
        error_handler: Optional[Callable[[str], None]] = None,
    ) -> None:
        """Initialize the search and analysis service."""
        self.model = model
        self.config = config
        self.worker_manager = worker_manager
        self.error_handler = error_handler or self._default_error_handler

        # Cache for recent search results and graphs
        self._search_cache: Dict[str, List[Dict[str, Any]]] = {}
        self._graph_cache: Dict[str, nx.Graph] = {}

        # Cache timestamp tracking
        self._cache_timestamps: Dict[str, datetime] = {}

    def search_nodes(
        self,
        criteria: SearchCriteria,
        result_callback: Callable[[List[Dict[str, Any]]], None],
        error_callback: Optional[Callable[[str], None]] = None,
    ) -> None:
        """
        Search for nodes based on search criteria.

        Args:
            criteria: Search criteria configuration
            result_callback: Callback for search results
            error_callback: Optional error callback
        """
        logger.debug(
            "initiating_search",
            search_text=criteria.text,
            labels=criteria.labels,
            include_relationships=criteria.include_relationships,
        )

        # Check cache first if it's a simple text search
        cache_key = self._get_cache_key(criteria)
        if cached_results := self._get_from_cache(cache_key):
            logger.debug("cache_hit", search_text=criteria.text)
            result_callback(cached_results)
            return

        # Build query using QueryBuilder
        query, params = self._build_search_query(criteria)

        def handle_results(results: List[Dict[str, Any]]) -> None:
            """Process and cache search results."""

            logger.debug("search_results_received", count=len(results))
            try:
                processed_results = self._process_search_results(results)

                # Cache results
                self._cache_results(cache_key, processed_results)

                # Convert to NetworkX graph if needed
                if criteria.include_relationships:
                    self._build_and_cache_graph(cache_key, processed_results)

                result_callback(processed_results)
            except Exception as e:
                logger.error("search_processing_error", error=str(e))
                if error_callback:
                    error_callback(f"Error processing search results: {str(e)}")

        # Create worker operation
        worker = self.model.execute_read_query(query, params)

        # Connect the signal before creating the operation
        worker.query_finished.connect(handle_results)

        logger.debug("worker_setup", operation_name="node_search")

        operation = WorkerOperation(
            worker=worker,
            success_callback=handle_results,
            error_callback=error_callback or self.error_handler,
            operation_name="node_search",
        )

        self.worker_manager.execute_worker("search", operation)

    def analyze_patterns(
        self,
        node_names: List[str],
        analysis_callback: Callable[[Dict[str, Any]], None],
        error_callback: Optional[Callable[[str], None]] = None,
    ) -> None:
        """
        Analyze patterns between specified nodes using NetworkX.

        Args:
            node_names: List of node names to analyze
            analysis_callback: Callback for analysis results
            error_callback: Optional error callback
        """
        logger.debug("starting_pattern_analysis", nodes=node_names)

        # Build query to get subgraph for analysis
        builder = Neo4jQueryBuilder()
        builder.match_node("n").with_property(
            PropertyCondition("name", PropertyOperator.IN, node_names)
        )
        builder.with_relationship(
            RelationshipPattern(type="*", direction=RelationshipDirection.ANY)
        )
        builder.return_nodes(["n"]).return_relationships(include_props=True)

        query, params = builder.build()

        def handle_results(results: List[Dict[str, Any]]) -> None:
            """Convert results to NetworkX graph and analyze."""
            try:
                graph = self._build_networkx_graph(results)
                analysis = self._analyze_graph(graph)
                analysis_callback(analysis)
            except Exception as e:
                logger.error("analysis_error", error=str(e))
                if error_callback:
                    error_callback(f"Error in pattern analysis: {str(e)}")

        # Create worker operation
        worker = self.model.execute_query(query, params)
        operation = WorkerOperation(
            worker=worker,
            success_callback=handle_results,
            error_callback=error_callback or self.error_handler,
            operation_name="pattern_analysis",
        )

        self.worker_manager.execute_worker("analysis", operation)

    def _build_search_query(
        self, criteria: SearchCriteria
    ) -> tuple[str, Dict[str, Any]]:
        """Build search query using QueryBuilder with improved error handling."""
        builder = Neo4jQueryBuilder()
        logger.debug("building_search_query", criteria=criteria)
        try:
            # Start with basic node match
            builder.match_node("n", labels=criteria.labels)

            # Add text search condition using OR between multiple fields with null checks
            if criteria.text:
                where_clauses = []

                # Name search condition
                name_check = (
                    "n.name IS NOT NULL AND toLower(n.name) "
                    f"CONTAINS toLower($prop_1)"
                )
                where_clauses.append(name_check)
                builder._parameters["prop_1"] = criteria.text

                # Description search condition
                desc_check = (
                    "n.description IS NOT NULL AND toLower(n.description) "
                    f"CONTAINS toLower($prop_2)"
                )
                where_clauses.append(desc_check)
                builder._parameters["prop_2"] = criteria.text

                # Combine conditions
                builder._where_conditions.append(f"({' OR '.join(where_clauses)})")

            # Configure return values
            builder.return_nodes(["n"], include_labels=True, include_props=True)

            # Add limit for safety
            builder.limit(1000)

            return builder.build()

        except Exception as e:
            logger.error("query_build_error", error=str(e))
            raise ValueError(f"Error building search query: {str(e)}")

    def _build_networkx_graph(self, results: List[Dict[str, Any]]) -> nx.Graph:
        """Convert Neo4j results to NetworkX graph."""
        nx_graph = nx.Graph()

        # Add nodes and edges from results
        for _ in results:
            # Implementation details depend on result structure
            pass

        return nx_graph

    def _analyze_graph(self, nx_graph: nx.Graph) -> Dict[str, Any]:
        """Perform graph analysis using NetworkX."""
        analysis = {
            "centrality": nx.degree_centrality(nx_graph),
            "communities": list(nx.community.greedy_modularity_communities(nx_graph)),
            "density": nx.density(nx_graph),
            "average_clustering": nx.average_clustering(nx_graph),
        }
        return analysis

    def _get_cache_key(self, criteria: SearchCriteria) -> str:
        """Generate cache key from search criteria."""
        components = [
            criteria.text,
            str(criteria.labels),
            str(criteria.include_relationships),
            str(criteria.case_sensitive),
        ]
        return "|".join(components)

    def _get_from_cache(self, cache_key: str) -> Optional[List[Dict[str, Any]]]:
        """Get results from cache if not expired."""
        if cache_key not in self._cache_timestamps:
            return None

        # Check if cache is expired (30 minutes)
        cache_age = datetime.now() - self._cache_timestamps[cache_key]
        if cache_age.total_seconds() > 1800:  # 30 minutes
            self._clear_cache_entry(cache_key)
            return None

        return self._search_cache.get(cache_key)

    def _cache_results(self, cache_key: str, results: List[Dict[str, Any]]) -> None:
        """Cache search results with timestamp."""
        self._search_cache[cache_key] = results
        self._cache_timestamps[cache_key] = datetime.now()

    def _build_and_cache_graph(
        self, cache_key: str, results: List[Dict[str, Any]]
    ) -> None:
        """Build and cache NetworkX graph from results."""
        graph = self._build_networkx_graph(results)
        self._graph_cache[cache_key] = graph

    def _clear_cache_entry(self, cache_key: str) -> None:
        """Clear a specific cache entry and its associated data."""
        self._search_cache.pop(cache_key, None)
        self._graph_cache.pop(cache_key, None)
        self._cache_timestamps.pop(cache_key, None)

    def clear_cache(self) -> None:
        """Clear all caches."""
        self._search_cache.clear()
        self._graph_cache.clear()
        self._cache_timestamps.clear()
        logger.debug("cache_cleared")

    def _process_search_results(
        self, results: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Process raw search results into standard format with robust error handling."""
        processed_results = []

        for result in results:
            try:
                # Extract base node properties with defaults
                node_props = result.get("n_props", {}) or {}
                node_labels = result.get("n_labels", []) or []

                # Basic validation
                if not isinstance(node_props, dict) or not isinstance(
                    node_labels, list
                ):
                    logger.warning(
                        "invalid_result_format",
                        props_type=type(node_props),
                        labels_type=type(node_labels),
                    )
                    continue

                # Create standardized result entry
                processed_result = {
                    "name": node_props.get("name", "Unnamed Node"),
                    "type": ", ".join(label for label in node_labels if label),
                    "properties": {
                        k: v
                        for k, v in node_props.items()
                        if (
                            k  # Ensure key exists
                            and not k.startswith("_")  # Skip system properties
                            and k
                            not in self.config.RESERVED_PROPERTY_KEYS  # Skip reserved
                            and v is not None
                        )  # Skip null values
                    },
                }

                # Validate required fields
                if not processed_result["name"]:
                    logger.warning("missing_node_name", original_props=node_props)
                    continue

                processed_results.append(processed_result)

            except Exception as e:
                logger.error("result_processing_error", error=str(e), result=result)
                continue

        # Sort results for consistency
        processed_results.sort(key=lambda x: x["name"])

        return processed_results

    def _default_error_handler(self, error_message: str) -> None:
        """Default error handler that logs errors."""
        logger.error("search_analysis_error", error=error_message)
