from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any, Callable

from structlog import get_logger

from models.worker_model import WorkerOperation
from services.worker_manager_service import WorkerManagerService
from ui.components.search_component.query_builder import (
    Neo4jQueryBuilder,
)

logger = get_logger(__name__)


class SearchField(Enum):
    """Enum defining searchable fields"""

    NAME = "name"
    DESCRIPTION = "description"
    TAGS = "tags"
    PROPERTIES = "properties"
    LABELS = "labels"


@dataclass
class FieldSearch:
    """Configuration for searching a specific field"""

    field: SearchField
    text: str
    exact_match: bool = False
    case_sensitive: bool = False


@dataclass
class SearchCriteria:
    """Enhanced search criteria configuration."""

    # Field searches
    field_searches: List[FieldSearch] = field(default_factory=list)

    # Label filters
    label_filters: Optional[List[str]] = None
    exclude_labels: Optional[List[str]] = None

    # Property filters
    required_properties: Optional[List[str]] = None
    excluded_properties: Optional[List[str]] = None

    # Relationship filters
    has_relationships: Optional[bool] = None
    relationship_types: Optional[List[str]] = None

    # Search options
    case_sensitive: bool = False
    limit: Optional[int] = None


class SearchAnalysisService:
    """Enhanced service for handling search and analysis operations."""

    def __init__(
        self,
        model: "Neo4jModel",
        config: "Config",
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
        self._cache_timestamps: Dict[str, datetime] = {}

    def search_nodes(
        self,
        criteria: SearchCriteria,
        result_callback: Callable[[List[Dict[str, Any]]], None],
        error_callback: Optional[Callable[[str], None]] = None,
    ) -> None:
        """
        Search for nodes based on enhanced search criteria.

        Args:
            criteria: SearchCriteria configuration with field searches and filters
            result_callback: Callback for search results
            error_callback: Optional error callback
        """
        logger.debug(
            "initiating_search",
            field_searches=[
                (fs.field.value, fs.text) for fs in criteria.field_searches
            ],
            label_filters=criteria.label_filters,
            required_properties=criteria.required_properties,
            has_relationships=criteria.has_relationships,
        )

        # Check cache for simple searches
        cache_key = self._get_cache_key(criteria)
        if (
            not criteria.label_filters
            and not criteria.required_properties
            and len(criteria.field_searches) <= 2
        ):
            if cached_results := self._get_from_cache(cache_key):
                logger.debug("cache_hit", field_searches=criteria.field_searches)
                result_callback(cached_results)
                return

        # Build query using QueryBuilder
        try:
            query, params = self._build_search_query(criteria)
        except ValueError as e:
            logger.error("query_build_error", error=str(e))
            if error_callback:
                error_callback(str(e))
            return

        def handle_results(results: List[Dict[str, Any]]) -> None:
            """Process and cache search results."""
            logger.debug("search_results_received", count=len(results))
            try:
                processed_results = self._process_search_results(results)

                # Cache simple search results
                if not criteria.label_filters and not criteria.required_properties:
                    self._cache_results(cache_key, processed_results)

                result_callback(processed_results)
            except Exception as e:
                logger.error("search_processing_error", error=str(e))
                if error_callback:
                    error_callback(f"Error processing search results: {str(e)}")

        # Execute query through worker
        worker = self.model.execute_read_query(query, params)
        worker.query_finished.connect(handle_results)

        operation = WorkerOperation(
            worker=worker,
            success_callback=handle_results,
            error_callback=error_callback or self.error_handler,
            operation_name="node_search",
        )

        self.worker_manager.execute_worker("search", operation)

    def _build_search_query(
        self, criteria: SearchCriteria
    ) -> tuple[str, Dict[str, Any]]:
        """Build enhanced search query using QueryBuilder."""
        builder = Neo4jQueryBuilder()
        logger.debug("building_search_query", criteria=criteria)

        try:
            # Start with basic node match
            builder.match_node("n", labels=criteria.label_filters)

            # Handle field searches
            where_clauses = []
            param_idx = 0

            # Group all quick search conditions with OR
            quick_search_clauses = []
            other_clauses = []

            for field_search in criteria.field_searches:
                param_name = f"search_{param_idx}"
                builder._parameters[param_name] = field_search.text

                if field_search.field == SearchField.NAME:
                    clause = self._build_text_search_clause(
                        "n.name", f"${param_name}", field_search
                    )
                elif field_search.field == SearchField.DESCRIPTION:
                    clause = self._build_text_search_clause(
                        "n.description", f"${param_name}", field_search
                    )
                elif field_search.field == SearchField.TAGS:
                    clause = f"ANY(tag IN n.tags WHERE {self._build_text_search_clause('tag', f'${param_name}', field_search)})"
                elif field_search.field == SearchField.LABELS:
                    clause = f"ANY(label IN labels(n) WHERE {self._build_text_search_clause('label', f'${param_name}', field_search)})"
                elif field_search.field == SearchField.PROPERTIES:
                    clause = (
                        f"ANY(prop_key IN keys(n) WHERE "
                        f"{self._build_text_search_clause('prop_key', f'${param_name}', field_search)} OR "
                        f"{self._build_text_search_clause('toString(n[prop_key])', f'${param_name}', field_search)})"
                    )

                # For quick search, use OR between conditions
                if not field_search.exact_match and not field_search.case_sensitive:
                    quick_search_clauses.append(clause)
                else:
                    other_clauses.append(clause)

                param_idx += 1

            # Combine quick search clauses with OR
            if quick_search_clauses:
                where_clauses.append(f"({' OR '.join(quick_search_clauses)})")

            # Add other clauses with AND
            where_clauses.extend(other_clauses)

            # Handle excluded labels
            if criteria.exclude_labels:
                labels_str = ":".join(criteria.exclude_labels)
                where_clauses.append(f"NOT n:{labels_str}")

            # Handle property filters
            if criteria.required_properties:
                for prop in criteria.required_properties:
                    where_clauses.append(f"(n.{prop}) IS NOT NULL")

            if criteria.excluded_properties:
                for prop in criteria.excluded_properties:
                    where_clauses.append(f"(n.{prop}) IS NULL")

            # Handle relationship filters
            if criteria.has_relationships is not None:
                rel_clause = (
                    "((n)--()) IS NOT NULL"
                    if criteria.has_relationships
                    else "((n)--()) IS NULL"
                )
                where_clauses.append(rel_clause)

            if criteria.relationship_types:
                rel_patterns = []
                for rel_type in criteria.relationship_types:
                    rel_patterns.append(f"((n)-[:{rel_type}]-()) IS NOT NULL")
                where_clauses.append(f"({' OR '.join(rel_patterns)})")

            # Combine all WHERE clauses with AND
            if where_clauses:
                builder._where_conditions.append(f"({' AND '.join(where_clauses)})")

            # Configure return values
            builder.return_nodes(["n"], include_labels=True, include_props=True)

            # Add ordering for consistent results
            builder.order_by(["n.name"])

            # Add limit for safety
            builder.limit(criteria.limit or 1000)

            return builder.build()

        except Exception as e:
            logger.error("query_build_error", error=str(e))
            raise ValueError(f"Error building search query: {str(e)}")

    def _build_field_search_clause(
        self, field_search: FieldSearch, idx: int
    ) -> Optional[str]:
        """Build WHERE clause for a field search."""
        if not field_search.text:
            return None

        param_name = f"$search_{idx}"

        if field_search.field == SearchField.NAME:
            return self._build_text_search_clause("n.name", param_name, field_search)

        elif field_search.field == SearchField.DESCRIPTION:
            return self._build_text_search_clause(
                "n.description", param_name, field_search
            )

        elif field_search.field == SearchField.TAGS:
            return f"ANY(tag IN n.tags WHERE {self._build_text_search_clause('tag', param_name, field_search)})"

        elif field_search.field == SearchField.PROPERTIES:
            # Search both property keys and values
            return (
                f"ANY(prop_key IN keys(n) WHERE "
                f"{self._build_text_search_clause('prop_key', param_name, field_search)} OR "
                f"{self._build_text_search_clause('toString(n[prop_key])', param_name, field_search)})"
            )

        return None

    def _build_text_search_clause(
        self, field: str, param_name: str, field_search: FieldSearch
    ) -> str:
        """Build the appropriate text matching clause based on search options."""
        if not field_search.case_sensitive:
            field = f"toLower({field})"
            param_name = f"toLower({param_name})"

        if field_search.exact_match:
            return f"{field} = {param_name}"
        else:
            return f"{field} CONTAINS {param_name}"

    def _process_search_results(
        self, results: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Process raw search results with enhanced property and relationship handling."""
        processed_results = []

        for result in results:
            try:
                # Extract and validate base node properties
                node_props = result.get("n_props", {}) or {}
                node_labels = result.get("n_labels", []) or []

                # Type validation
                if not isinstance(node_props, dict) or not isinstance(
                    node_labels, list
                ):
                    logger.warning(
                        "invalid_result_format",
                        props_type=type(node_props),
                        labels_type=type(node_labels),
                    )
                    continue

                # Enhanced property processing
                filtered_props = self._filter_system_properties(node_props)

                # Create standardized result entry
                processed_result = {
                    "name": node_props.get("name", "Unnamed Node"),
                    "type": ", ".join(label for label in node_labels if label),
                    "properties": filtered_props,
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

    def _filter_system_properties(self, properties: Dict[str, Any]) -> Dict[str, Any]:
        """Filter out system properties and format values."""
        return {
            k: v
            for k, v in properties.items()
            if (
                k  # Ensure key exists
                and not k.startswith("_")  # Skip system properties
                and k not in self.config.RESERVED_PROPERTY_KEYS  # Skip reserved
                and v is not None  # Skip null values
            )
        }

    def _get_cache_key(self, criteria: SearchCriteria) -> str:
        """Generate cache key from enhanced search criteria."""
        components = []

        # Add field searches to key
        for fs in criteria.field_searches:
            components.append(
                f"{fs.field.value}:{fs.text}:{fs.exact_match}:{fs.case_sensitive}"
            )

        # Add filters to key
        if criteria.label_filters:
            components.append(f"labels:{','.join(sorted(criteria.label_filters))}")
        if criteria.exclude_labels:
            components.append(
                f"exclude_labels:{','.join(sorted(criteria.exclude_labels))}"
            )
        if criteria.required_properties:
            components.append(
                f"required_props:{','.join(sorted(criteria.required_properties))}"
            )
        if criteria.has_relationships is not None:
            components.append(f"has_rels:{criteria.has_relationships}")
        if criteria.relationship_types:
            components.append(
                f"rel_types:{','.join(sorted(criteria.relationship_types))}"
            )

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

    def _clear_cache_entry(self, cache_key: str) -> None:
        """Clear a specific cache entry and its associated data."""
        self._search_cache.pop(cache_key, None)
        self._cache_timestamps.pop(cache_key, None)

    def clear_cache(self) -> None:
        """Clear all caches."""
        self._search_cache.clear()
        self._cache_timestamps.clear()
        logger.debug("cache_cleared")

    def _default_error_handler(self, error_message: str) -> None:
        """Default error handler that logs errors."""
        logger.error("search_analysis_error", error=error_message)
