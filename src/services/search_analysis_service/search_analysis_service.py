from abc import abstractmethod, ABC
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any, Callable, Tuple

from structlog import get_logger

from models.worker_model import WorkerOperation
from services.worker_manager_service import WorkerManagerService

logger = get_logger(__name__)


class SearchField(Enum):
    """Enum defining searchable fields"""

    NAME = "name"
    DESCRIPTION = "description"
    TAGS = "tags"
    PROPERTIES = "properties"
    LABELS = "labels"


@dataclass
class QueryComponent:
    """Base class for query components with parameters"""

    text: str
    parameters: Dict[str, Any]


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

        # Initialize property discovery
        self.array_properties, self.scalar_properties = self.discover_property_types()
        self._property_discovery_timestamp = datetime.now()

    def discover_property_types(self) -> Tuple[List[str], List[str]]:
        """
        Query the database to discover all property keys and their types.
        Returns tuple of (array_properties, scalar_properties)
        """
        # Cypher query to get all property keys and determine type
        query = """
        MATCH (n)
        WHERE n._project = 'default'
        UNWIND keys(n) AS prop_key
        WITH DISTINCT prop_key, collect(n[prop_key])[0] AS sample_value
        WHERE NOT prop_key STARTS WITH '_'
        RETURN prop_key, 
               CASE WHEN sample_value IS NULL THEN 'null'
                    WHEN exists((sample_value)[0]) THEN 'array'
                    ELSE 'scalar'
               END AS prop_type
        """

        try:
            # Execute the query
            worker = self.model.execute_read_query(query, {})
            results = worker.wait_for_result()

            array_properties = []
            scalar_properties = []

            # Process results
            for record in results:
                prop_key = record.get("prop_key")
                prop_type = record.get("prop_type")

                # Filter out reserved keys
                reserved_keys = getattr(self.config, "RESERVED_PROPERTY_KEYS", [])
                if prop_key in reserved_keys:
                    continue

                if prop_type == "array":
                    array_properties.append(prop_key)
                elif prop_type == "scalar":
                    scalar_properties.append(prop_key)

            logger.debug(
                "property_discovery_completed",
                array_props=array_properties,
                scalar_props=scalar_properties,
            )

            return array_properties, scalar_properties
        except Exception as e:
            logger.error("property_discovery_failed", error=str(e))
            # Fallback to default properties
            return ["tags", "Array_Property", "defenses"], ["name", "description"]

    def refresh_property_types(self) -> None:
        """Refresh the discovered property types."""
        try:
            self.array_properties, self.scalar_properties = (
                self.discover_property_types()
            )
            self._property_discovery_timestamp = datetime.now()
            logger.debug(
                "property_types_refreshed",
                array_count=len(self.array_properties),
                scalar_count=len(self.scalar_properties),
            )
        except Exception as e:
            logger.error("property_refresh_failed", error=str(e))

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
        """Build enhanced search query using SearchQueryBuilder."""
        # Check if property discovery needs to be refreshed (once per day)
        if (
            datetime.now() - self._property_discovery_timestamp
        ).total_seconds() > 86400:  # 24 hours
            self.refresh_property_types()

        builder = SearchQueryBuilder(
            array_properties=self.array_properties,
            scalar_properties=self.scalar_properties,
        )
        return builder.build_search_query(criteria)

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
        # Safe fallback for missing config attribute
        reserved_keys = getattr(self.config, "RESERVED_PROPERTY_KEYS", [])

        return {
            k: v
            for k, v in properties.items()
            if (
                k  # Ensure key exists
                and not k.startswith("_")  # Skip system properties
                and k not in reserved_keys  # Skip reserved with fallback
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


class ClauseBuilder(ABC):
    """Abstract base class for clause builders"""

    @abstractmethod
    def build(self) -> QueryComponent:
        pass


class MatchClauseBuilder(ClauseBuilder):
    """Builds the MATCH clause based on label filters"""

    def __init__(self, label_filters: Optional[List[str]]):
        self.label_filters = label_filters

    def build(self) -> QueryComponent:
        if not self.label_filters:
            return QueryComponent("MATCH (n)", {})

        # Create individual label matches joined with OR
        label_patterns = [f"n:{label}" for label in self.label_filters]
        label_clause = f"({' OR '.join(label_patterns)})"

        # Return just the MATCH clause - let the WHERE clause be combined later
        return QueryComponent(f"MATCH (n)", {"label_clause": label_clause})


class TextSearchBuilder:
    """Handles building text search conditions"""

    @staticmethod
    def build_condition(
        field: str, param_name: str, case_sensitive: bool, exact_match: bool
    ) -> str:
        field_expr = field if case_sensitive else f"toLower({field})"
        param_expr = param_name if case_sensitive else f"toLower({param_name})"

        return (
            f"{field_expr} = {param_expr}"
            if exact_match
            else f"{field_expr} CONTAINS {param_expr}"
        )


class FieldSearchBuilder:
    """Builds search conditions for different field types"""

    def __init__(
        self,
        field_searches: List[FieldSearch],
        array_properties: List[str] = None,
        scalar_properties: List[str] = None,
    ):
        self.field_searches = field_searches
        self._parameters: Dict[str, Any] = {}
        self.array_properties = array_properties or ["tags", "Array_Property"]
        self.scalar_properties = scalar_properties or ["name", "description"]

    def build(self) -> QueryComponent:
        quick_searches = []
        exact_searches = []

        for idx, search in enumerate(self.field_searches):
            param_name = f"search_{idx}"
            self._parameters[param_name] = search.text
            param_ref = f"${param_name}"

            # Pass param_ref to _build_field_clause
            clause = self._build_field_clause(search, param_ref)
            if clause:
                if not search.exact_match and not search.case_sensitive:
                    quick_searches.append(clause)
                else:
                    exact_searches.append(clause)

        where_parts = []
        if quick_searches:
            where_parts.append(f"({' OR '.join(quick_searches)})")
        where_parts.extend(exact_searches)

        where_clause = " AND ".join(where_parts) if where_parts else ""
        return QueryComponent(where_clause, self._parameters)

    def _build_field_clause(
        self, field_search: FieldSearch, param_ref: str  # param_ref is received here
    ) -> Optional[str]:
        if not field_search.text:
            return None

        field_builders = {
            SearchField.NAME: lambda: TextSearchBuilder.build_condition(
                "n.name",
                param_ref,
                field_search.case_sensitive,
                field_search.exact_match,
            ),
            SearchField.DESCRIPTION: lambda: TextSearchBuilder.build_condition(
                "n.description",
                param_ref,
                field_search.case_sensitive,
                field_search.exact_match,
            ),
            SearchField.TAGS: lambda: f"ANY(tag IN n.tags WHERE {TextSearchBuilder.build_condition('tag', param_ref, field_search.case_sensitive, field_search.exact_match)})",
            SearchField.LABELS: lambda: f"ANY(label IN labels(n) WHERE {TextSearchBuilder.build_condition('label', param_ref, field_search.case_sensitive, field_search.exact_match)})",
            # Pass param_ref to _build_properties_clause
            SearchField.PROPERTIES: lambda: self._build_properties_clause(param_ref),
        }

        builder_func = field_builders.get(field_search.field)
        # Call the builder function, which now correctly handles param_ref for properties
        return builder_func() if builder_func else None

    def _build_properties_clause(self, param_ref: str) -> str:
        """Build search clause for properties using dynamically discovered properties."""

        # Search in property keys
        key_clause = (
            f"ANY(prop_key IN keys(n) WHERE toLower(prop_key) CONTAINS {param_ref})"
        )

        # Search in scalar properties
        scalar_clauses = []
        for prop in self.scalar_properties:
            scalar_clauses.append(
                f"n.{prop} IS NOT NULL AND toLower(toString(n.{prop})) CONTAINS {param_ref}"
            )

        # Search in array properties
        array_clauses = []
        for prop in self.array_properties:
            array_clauses.append(
                f"n.{prop} IS NOT NULL AND ANY(item IN n.{prop} WHERE toLower(toString(item)) CONTAINS {param_ref})"
            )

        # Combine all clauses with OR
        scalar_search = " OR ".join(scalar_clauses) if scalar_clauses else "false"
        array_search = " OR ".join(array_clauses) if array_clauses else "false"

        return f"{key_clause} OR ({scalar_search}) OR ({array_search})"


class FilterClauseBuilder(ClauseBuilder):
    """Builds filter clauses for various criteria"""

    def __init__(self, criteria: SearchCriteria):
        self.criteria = criteria

    def build(self) -> QueryComponent:

        clauses = []

        if self.criteria.exclude_labels:
            # Create individual exclusions for each label joined with OR
            exclusion_clauses = [f"n:{label}" for label in self.criteria.exclude_labels]
            clauses.append(f"NOT ({' OR '.join(exclusion_clauses)})")

        if self.criteria.required_properties:
            clauses.extend(
                f"ANY(prop_key IN keys(n) WHERE toLower(prop_key) CONTAINS toLower('{prop}'))"
                for prop in self.criteria.required_properties
            )

        if self.criteria.excluded_properties:
            clauses.extend(
                f"NOT ANY(prop_key IN keys(n) WHERE toLower(prop_key) CONTAINS toLower('{prop}'))"
                for prop in self.criteria.excluded_properties
            )

        # Changed to use pattern predicate for relationship check
        if self.criteria.has_relationships is not None:
            clauses.append(
                "()-[]-(n)" if self.criteria.has_relationships else "NOT ()-[]-(n)"
            )

        # Changed to use pattern predicates for relationship types
        if self.criteria.relationship_types:
            rel_patterns = [
                f"()-[:{rel_type}]-(n)" for rel_type in self.criteria.relationship_types
            ]
            clauses.append(f"({' OR '.join(rel_patterns)})")

        # Return joined conditions
        return QueryComponent((" AND ".join(clauses)) if clauses else "", {})


class ReturnClauseBuilder(ClauseBuilder):
    """Builds the RETURN clause with ordering and limits"""

    def __init__(self, limit: Optional[int] = None):
        self.limit = limit

    def build(self) -> QueryComponent:
        return QueryComponent(
            "\n".join(
                [
                    "RETURN n,",
                    "labels(n) as n_labels,",
                    "properties(n) as n_props",
                    "ORDER BY n.name",
                    f"LIMIT {self.limit or 1000}",
                ]
            ),
            {},
        )


class SearchQueryBuilder:
    """Composes all query components into the final query"""

    def __init__(
        self, array_properties: List[str] = None, scalar_properties: List[str] = None
    ):
        """Initialize with discovered property types."""
        self.array_properties = array_properties or ["tags", "Array_Property"]
        self.scalar_properties = scalar_properties or ["name", "description"]

    def build_search_query(
        self, criteria: SearchCriteria
    ) -> Tuple[str, Dict[str, Any]]:
        query_parts = []
        where_conditions = []
        parameters = {}

        # Add MATCH clause
        match_builder = MatchClauseBuilder(criteria.label_filters)
        match_component = match_builder.build()
        query_parts.append(match_component.text)
        if match_component.parameters.get("label_clause"):
            where_conditions.append(match_component.parameters["label_clause"])

        # Collect field search conditions
        field_builder = FieldSearchBuilder(
            criteria.field_searches,
            array_properties=self.array_properties,
            scalar_properties=self.scalar_properties,
        )
        field_component = field_builder.build()
        if field_component.text:
            where_conditions.append(field_component.text)
            parameters.update(field_component.parameters)

        # Fix: Use literal string for project instead of parameter
        where_conditions.append("n._project = 'default'")

        # Collect filter conditions
        filter_builder = FilterClauseBuilder(criteria)
        filter_component = filter_builder.build()
        if filter_component.text:
            where_conditions.append(filter_component.text)
            parameters.update(filter_component.parameters)

        # Add WHERE clause if we have conditions
        if where_conditions:
            query_parts.append("WHERE " + " AND ".join(where_conditions))

        # Add RETURN clause
        return_builder = ReturnClauseBuilder(criteria.limit)
        return_component = return_builder.build()
        query_parts.append(return_component.text)

        return "\n".join(query_parts), parameters
