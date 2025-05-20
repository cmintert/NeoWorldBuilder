import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, Callable

from structlog import get_logger

from config.config import Config
from core.neo4jmodel import Neo4jModel
from models.property_model import PropertyItem
from models.worker_model import WorkerOperation
from services.property_service import PropertyService
from services.worker_manager_service import WorkerManagerService
from utils.error_handler import ErrorHandler
from utils.parsers import parse_comma_separated
from utils.validation import (
    ValidationResult,
    validate_node_name as validate_node_name_logic,
)

logger = get_logger(__name__)

@dataclass
class NodeData:
    """Data class for node information"""

    name: str
    description: str
    tags: List[str]
    labels: List[str]
    relationships: List[Tuple[str, str, str, Dict[str, Any]]]
    additional_properties: Dict[str, Any]


class NodeOperationsService:
    """
    Manages node operations including CRUD, data collection, and validation.

    This service centralizes all node-related operations and provides a clean interface
    for node manipulation while managing worker threads and error handling.
    """

    def __init__(
        self,
        model: Neo4jModel,
        config: Config,
        worker_manager: WorkerManagerService,
        property_service: PropertyService,
        error_handler: ErrorHandler,
    ) -> None:
        """Initialize the node operations service.

        Args:
            model: Database model instance
            config: Application configuration
            worker_manager: Worker thread manager
            property_service: Property handling service
            error_handler: Error handling service
        """
        self.model = model
        self.config = config
        self.worker_manager = worker_manager
        self.property_service = property_service
        self.error_handler = error_handler

    def save_node(
        self, node_data: Dict[str, Any], success_callback: Callable[[Any], None]
    ) -> None:
        """Save node with worker thread management.

        Args:
            node_data: Complete node data to save
            success_callback: Callback for successful save
        """
        worker = self.model.save_node(node_data, success_callback)

        operation = WorkerOperation(
            worker=worker,
            success_callback=success_callback,
            error_callback=lambda msg: self.error_handler.handle_error(
                f"Error saving node: {msg}"
            ),
            operation_name="save_node",
        )

        self.worker_manager.execute_worker("save", operation)

    def load_node(
        self,
        name: str,
        success_callback: Callable[[List[Any]], None],
        finished_callback: Optional[Callable[[], None]] = None,
    ) -> None:
        """Load node data using worker thread.

        Args:
            name: Name of the node to load
            success_callback: Callback for successful load
            finished_callback: Optional callback when operation completes
        """
        if not name.strip():
            return

        worker = self.model.load_node(name, success_callback)

        operation = WorkerOperation(
            worker=worker,
            success_callback=success_callback,
            error_callback=lambda msg: self.error_handler.handle_error(
                f"Error loading node: {msg}"
            ),
            finished_callback=finished_callback,
            operation_name="load_node",
        )

        self.worker_manager.execute_worker("load", operation)

    def delete_node(self, name: str, success_callback: Callable[[Any], None]) -> None:
        """Delete node using worker thread.

        Args:
            name: Name of the node to delete
            success_callback: Callback for successful deletion
        """
        if not name.strip():
            return

        worker = self.model.delete_node(name, success_callback)

        operation = WorkerOperation(
            worker=worker,
            success_callback=success_callback,
            error_callback=lambda msg: self.error_handler.handle_error(
                f"Error deleting node: {msg}"
            ),
            operation_name="delete_node",
        )

        self.worker_manager.execute_worker("delete", operation)

    def collect_node_data(
        self,
        name: str,
        description: str,
        tags: str,
        labels: str,
        properties: List[PropertyItem],  # From table
        relationships: List[Tuple[str, str, str, str]],
        all_props: Optional[Dict[str, Any]] = None,  # From database
    ) -> Optional[Dict[str, Any]]:
        """Collect and validate all node data."""
        try:
            # Convert table properties to dict
            properties: Dict[str, Any] = self.property_service.process_properties(
                properties
            )

            # Handle existing properties from database
            if all_props:
                # Filter out properties with underscores in keys
                filtered_props = {
                    key: value
                    for key, value in all_props.items()
                    if not key.startswith("_")
                }

                # Filter out properties with empty values
                filtered_props = {
                    key: value
                    for key, value in filtered_props.items()
                    if value is not None and value != ""
                }

                # Keep properties in config.reserved_properties
                filtered_props = {
                    key: value
                    for key, value in filtered_props.items()
                    if key in self.config.RESERVED_PROPERTY_KEYS
                }

                properties.update(filtered_props)

            return {
                "name": name.strip(),
                "description": description.strip(),
                "tags": parse_comma_separated(tags),
                "labels": [label.strip() for label in parse_comma_separated(labels)],
                "relationships": self._format_relationships(relationships),
                "additional_properties": properties,
            }

        except Exception as e:
            logging.error(f"Error collecting node data: {str(e)}")
            self.error_handler.handle_error(str(e))
            return None

    def validate_node_name(self, name: str) -> ValidationResult:
        """Validate node name against configuration rules.

        Args:
            name: Node name to validate

        Returns:
            ValidationResult containing validation status and error message
        """
        return validate_node_name_logic(name, self.config.MAX_NODE_NAME_LENGTH)

    def load_last_modified_node(self, success_callback: Callable[[Any], None]) -> None:
        """Load the most recently modified node.

        Args:
            success_callback: Callback for successful load
        """
        try:
            last_modified_node = self.model.get_last_modified_node()
            if last_modified_node:
                self.load_node(last_modified_node["name"], success_callback)
            else:
                logging.info("No nodes available to load.")
        except Exception as e:
            self.error_handler.handle_error(f"Error loading last modified node: {e}")

    def _format_relationships(
        self, relationships: List[Tuple[str, str, str, str]]
    ) -> List[Tuple[str, str, str, Dict[str, Any]]]:
        """Format relationships with proper property handling.

        Args:
            relationships: List of relationship tuples (type, target, direction, props_json)

        Returns:
            Formatted relationships with parsed properties
        """
        formatted_relationships = []
        for rel_type, target, direction, props_str in relationships:
            try:
                # Skip incomplete relationships
                if not all([rel_type, target, direction]):
                    continue

                # Parse properties if present
                properties = (
                    json.loads(props_str) if props_str and props_str.strip() else {}
                )

                # Format relationship type
                formatted_rel_type = rel_type.strip()

                formatted_relationships.append(
                    (formatted_rel_type, target.strip(), direction, properties)
                )
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON in relationship properties: {e}") from e

        return formatted_relationships

    def get_node_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Get node by name synchronously with relationship data.

        Args:
            name: Name of the node to retrieve

        Returns:
            Dict containing node data or None if not found
        """
        if not name or not name.strip():
            return None

        try:
            with self.model.get_session() as session:
                result = session.run(
                    """
                    MATCH (n {name: $name, _project: $project})
                    WITH n, labels(n) AS labels,
                         [(n)-[r]->(m) | {target: m.name, type: type(r), direction: 'OUTGOING'}] AS out_rels,
                         [(n)<-[r2]-(o) | {target: o.name, type: type(r2), direction: 'INCOMING'}] AS in_rels,
                         properties(n) AS all_props
                    RETURN n,
                           out_rels + in_rels AS relationships,
                           labels,
                           all_props
                    LIMIT 1
                    """,
                    name=name,
                    project=self.model._project,
                )
                record = result.single()
                if record:
                    # Convert Neo4j node to dict and ensure 'name' is included
                    node_data = dict(record["n"])  # This preserves all node properties

                    # Make sure these fields are available at the top level
                    node_data.update(
                        {
                            "name": name,
                            "labels": record["labels"],
                            "all_props": record["all_props"],
                            "relationships": record["relationships"],
                        }
                    )
                    # Remove reserved properties
                    logger.debug(f"Node data from get_node_by_name:"
                                 f" {node_data}")
                    return node_data
                return None
        except Exception as e:
            self.error_handler.handle_error(f"Error getting node: {str(e)}")
            return None
