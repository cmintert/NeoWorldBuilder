from dataclasses import dataclass
from enum import Enum, auto
from typing import List, Dict, Any, Optional, Union

from structlog import get_logger

logger = get_logger(__name__)


class PropertyOperator(Enum):
    """Operators for property conditions."""

    EQUALS = "="
    CONTAINS = "CONTAINS"
    STARTS_WITH = "STARTS WITH"
    ENDS_WITH = "ENDS WITH"
    GREATER_THAN = ">"
    LESS_THAN = "<"
    GREATER_EQUAL = ">="
    LESS_EQUAL = "<="
    IN = "IN"
    NOT_IN = "NOT IN"


class RelationshipDirection(Enum):
    """Direction of relationships."""

    OUTGOING = auto()  # ->[...]->
    INCOMING = auto()  # <-[...]<-
    ANY = auto()  # -[...]-


@dataclass
class PropertyCondition:
    """Property condition for query building."""

    property_name: str
    operator: PropertyOperator
    value: Any
    case_sensitive: bool = True


@dataclass
class RelationshipPattern:
    """Pattern for relationship matching."""

    type: str
    direction: RelationshipDirection
    min_depth: Optional[int] = None
    max_depth: Optional[int] = None
    properties: Optional[Dict[str, Any]] = None


class Neo4jQueryBuilder:
    """
    Builder for constructing Neo4j Cypher queries dynamically.

    Supports building complex queries with multiple conditions,
    relationship patterns, and property filters.
    """

    def __init__(self) -> None:
        """Initialize query builder with empty state."""
        self._match_patterns: List[str] = []
        self._where_conditions: List[str] = []
        self._return_items: List[str] = []
        self._order_by: List[str] = []
        self._parameters: Dict[str, Any] = {}
        self._limit: Optional[int] = None
        self._skip: Optional[int] = None
        self._param_counter = 0

    def match_node(
        self,
        variable: str = "n",
        labels: Optional[List[str]] = None,
        properties: Optional[Dict[str, Any]] = None,
    ) -> "Neo4jQueryBuilder":
        """
        Add a node matching pattern.

        Args:
            variable: Variable name for the node
            labels: Optional list of labels to match
            properties: Optional properties to match

        Returns:
            Self for chaining
        """
        pattern = [variable]

        if labels:
            pattern.append(":" + ":".join(labels))

        if properties:
            param_name = self._next_param_name("props")
            self._parameters[param_name] = properties
            pattern.append(f"{{{param_name}}}")

        self._match_patterns.append(f"({' '.join(pattern)})")
        return self

    def with_property(
        self, condition: PropertyCondition, variable: str = "n"
    ) -> "Neo4jQueryBuilder":
        """
        Add a property condition.

        Args:
            condition: Property condition to apply
            variable: Node variable to apply condition to

        Returns:
            Self for chaining
        """
        param_name = self._next_param_name("prop")
        self._parameters[param_name] = condition.value

        if condition.operator in (
            PropertyOperator.CONTAINS,
            PropertyOperator.STARTS_WITH,
            PropertyOperator.ENDS_WITH,
        ):
            # Use toLower() for case-insensitive text operations
            if not condition.case_sensitive:
                where_clause = (
                    f"toLower({variable}.{condition.property_name}) "
                    f"{condition.operator.value} "
                    f"toLower(${param_name})"
                )
            else:
                where_clause = (
                    f"{variable}.{condition.property_name} "
                    f"{condition.operator.value} "
                    f"${param_name}"
                )
        else:
            where_clause = (
                f"{variable}.{condition.property_name} "
                f"{condition.operator.value} "
                f"${param_name}"
            )

        self._where_conditions.append(where_clause)
        return self

    def with_relationship(
        self,
        pattern: RelationshipPattern,
        from_variable: str = "n",
        to_variable: str = "m",
    ) -> "Neo4jQueryBuilder":
        """
        Add a relationship pattern.

        Args:
            pattern: Relationship pattern to match
            from_variable: Starting node variable
            to_variable: Ending node variable

        Returns:
            Self for chaining
        """
        rel_pattern = [f"-[r:{pattern.type}"]

        # Add depth constraints if specified
        if pattern.min_depth is not None or pattern.max_depth is not None:
            min_depth = pattern.min_depth if pattern.min_depth is not None else 1
            max_depth = pattern.max_depth if pattern.max_depth is not None else ""
            rel_pattern.append(f"*{min_depth}..{max_depth}")

        # Add relationship properties if specified
        if pattern.properties:
            param_name = self._next_param_name("rel_props")
            self._parameters[param_name] = pattern.properties
            rel_pattern.append(f"{{{param_name}}}")

        rel_pattern.append("]")

        # Add direction
        if pattern.direction == RelationshipDirection.OUTGOING:
            relationship = f"({from_variable}){''.join(rel_pattern)}->({to_variable})"
        elif pattern.direction == RelationshipDirection.INCOMING:
            relationship = f"({from_variable})<-{''.join(rel_pattern)}-({to_variable})"
        else:  # ANY
            relationship = f"({from_variable})-{''.join(rel_pattern)}-({to_variable})"

        self._match_patterns.append(relationship)
        return self

    def return_nodes(
        self,
        variables: Union[str, List[str]],
        include_labels: bool = True,
        include_props: bool = True,
    ) -> "Neo4jQueryBuilder":
        """
        Specify nodes to return.

        Args:
            variables: Node variables to return
            include_labels: Whether to include labels
            include_props: Whether to include properties

        Returns:
            Self for chaining
        """
        if isinstance(variables, str):
            variables = [variables]

        for var in variables:
            self._return_items.append(var)
            if include_labels:
                self._return_items.append(f"labels({var}) AS {var}_labels")
            if include_props:
                self._return_items.append(f"properties({var}) AS {var}_props")

        return self

    def return_relationships(self, include_props: bool = True) -> "Neo4jQueryBuilder":
        """
        Include relationships in return results.

        Args:
            include_props: Whether to include relationship properties

        Returns:
            Self for chaining
        """
        self._return_items.append("type(r) AS relationship_type")
        if include_props:
            self._return_items.append("properties(r) AS relationship_props")
        return self

    def order_by(
        self, properties: List[str], descending: bool = False
    ) -> "Neo4jQueryBuilder":
        """
        Add ordering to the query.

        Args:
            properties: Properties to order by
            descending: Whether to order in descending order

        Returns:
            Self for chaining
        """
        direction = "DESC" if descending else "ASC"
        for prop in properties:
            self._order_by.append(f"{prop} {direction}")
        return self

    def limit(self, count: int) -> "Neo4jQueryBuilder":
        """Set result limit."""
        self._limit = count
        return self

    def skip(self, count: int) -> "Neo4jQueryBuilder":
        """Set number of results to skip."""
        self._skip = count
        return self

    def build(self) -> tuple[str, Dict[str, Any]]:
        """
        Build the final Cypher query and parameters.

        Returns:
            Tuple of (query string, parameters dict)
        """
        query_parts = []

        # MATCH clause
        if self._match_patterns:
            query_parts.append("MATCH " + ", ".join(self._match_patterns))

        # WHERE clause
        if self._where_conditions:
            query_parts.append("WHERE " + " AND ".join(self._where_conditions))

        # RETURN clause
        if self._return_items:
            query_parts.append("RETURN " + ", ".join(self._return_items))

        # ORDER BY clause
        if self._order_by:
            query_parts.append("ORDER BY " + ", ".join(self._order_by))

        # SKIP and LIMIT
        if self._skip is not None:
            query_parts.append(f"SKIP {self._skip}")
        if self._limit is not None:
            query_parts.append(f"LIMIT {self._limit}")

        query = "\n".join(query_parts)
        logger.debug("built_query", query=query, parameters=self._parameters)

        return query, self._parameters

    def _next_param_name(self, prefix: str) -> str:
        """Generate next unique parameter name."""
        self._param_counter += 1
        return f"{prefix}_{self._param_counter}"

    def with_any_property(
        self, conditions: List[PropertyCondition]
    ) -> "Neo4jQueryBuilder":
        """
        Add multiple property conditions joined by OR.

        Args:
            conditions: List of property conditions to join with OR

        Returns:
            Self for chaining
        """
        if not conditions:  # Safety check
            return self

        where_clauses = []

        for condition in conditions:
            param_name = self._next_param_name("prop")
            self._parameters[param_name] = condition.value

            if condition.operator in (
                PropertyOperator.CONTAINS,
                PropertyOperator.STARTS_WITH,
                PropertyOperator.ENDS_WITH,
            ):
                if not condition.case_sensitive:
                    where_clauses.append(
                        f"toLower(n.{condition.property_name}) "
                        f"{condition.operator.value} "
                        f"toLower(${param_name})"
                    )
                else:
                    where_clauses.append(
                        f"n.{condition.property_name} "
                        f"{condition.operator.value} "
                        f"${param_name}"
                    )
            else:
                where_clauses.append(
                    f"n.{condition.property_name} "
                    f"{condition.operator.value} "
                    f"${param_name}"
                )

        if where_clauses:
            # Join the clauses with OR and wrap in parentheses
            self._where_conditions.append(f"({' OR '.join(where_clauses)})")

        return self
