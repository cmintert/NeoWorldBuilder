"""
This module provides the Neo4jModel class, which serves as a gateway to the Neo4j database.
It includes methods for connecting to the database, performing CRUD operations on nodes, and querying node relationships.
"""

import datetime
from datetime import datetime
from typing import Dict, Any, Callable, Optional, List

from neo4j import GraphDatabase
from neo4j.exceptions import AuthError
from structlog import get_logger

from core.neo4jworkers import QueryWorker, WriteWorker, DeleteWorker, SuggestionWorker
from utils.converters import NamingConventionConverter as ncc

# Configure the standard logging
logger = get_logger(__name__)


class Neo4jModel:
    """
    Gateway to the Neo4j database.

    Args:
        uri (str): The URI of the Neo4j database.
        username (str): The username for authentication.
        password (str): The password for authentication.
    """

    def __init__(
        self, uri: str, username: str, password: str, config: "Config"
    ) -> None:
        """
        Initialize Neo4j connection parameters and establish connection.

        Args:
            uri (str): The URI of the Neo4j database.
            username (str): The username for authentication.
            password (str): The password for authentication.
            config (Config): Configuration object containing application settings.
        """
        self._uri = uri
        self._auth = (username, password)
        self._driver = None
        self._config = config
        self._project = self._config.user.PROJECT

        self.connect()

        logger.info(
            "Neo4jModel initialized and connected to the database.",
            module="Neo4jModel",
            function="__init__",
        )
        logger.debug(
            "Current project: " + self._project,
            module="Neo4jModel",
            function="__init__",
        )

    def connect(self) -> None:
        """
        Establish a connection to the Neo4j database with proper authentication verification.

        Raises:
            AuthError: If authentication fails
            ServiceUnavailable: If database is not accessible
        """
        if not self._driver:
            self._driver = GraphDatabase.driver(self._uri, auth=self._auth)

            # Immediately verify connectivity and authentication
            try:
                self._driver.verify_connectivity()
            except Exception:
                # Close the driver on failure
                if self._driver:
                    self._driver.close()
                    self._driver = None
                # Re-raise the exception
                raise

            logger.info(
                "Connected to Neo4j database.", module="Neo4jModel", function="connect"
            )

    def ensure_connection(self) -> None:
        """
        Ensure that the connection to the Neo4j database is valid.
        Reconnect if the connection is not valid.

        Raises:
            AuthError: If authentication fails
            ServiceUnavailable: If database is not accessible
        """
        try:
            if self._driver:
                self._driver.verify_connectivity()
            else:
                self.connect()
        except Exception as e:
            logger.warning(
                f"Connection verification failed: {e}",
                module="Neo4jModel",
                function="ensure_connection",
            )
            # Don't try to reconnect on authentication failure
            if isinstance(e, AuthError):
                raise
            self.connect()

    def get_session(self) -> Any:
        """
        Get a database session, ensuring connection is valid.

        Returns:
            The database session.
        """
        self.ensure_connection()
        return self._driver.session()

    def close(self) -> None:
        """
        Safely close the driver.
        """
        if self._driver:
            try:
                self._driver.close()
            finally:
                self._driver = None
        logger.info(
            "Neo4jModel connection closed.", module="Neo4jModel", function="close"
        )

    #############################################
    # 2. Node CRUD Operations
    #############################################

    def validate_node_data(self, node_data: Dict[str, Any]) -> bool:
        """
        Validate node data before performing any operations.

        Args:
            node_data (dict): Node data including properties and relationships.

        Raises:
            ValueError: If validation fails.
        """
        # Check for required fields
        if "name" not in node_data or not node_data["name"].strip():
            raise ValueError("Node must have a non-empty name.")

        if "labels" not in node_data or not node_data["labels"]:
            raise ValueError("Node must have at least one label.")

        # Check for proper labels
        for label in node_data["labels"]:
            if not label.strip():
                raise ValueError("Node labels must be non-empty.")

        return True

    def load_node(self, name: str, callback: Callable) -> QueryWorker:
        """
        Load a node and its relationships by name using a worker.

        Args:
            name (str): Name of the node to load.
            callback (function): Function to call with the result.

        Returns:
            QueryWorker: A worker that will execute the query.
        """
        query = """
            MATCH (n {name: $name})
            WITH n, labels(n) AS labels,
                 [(n)-[r]->(m) | {end: m.name, type: type(r), dir: '>', props: properties(r)}] AS out_rels,
                 [(n)<-[r2]-(o) | {end: o.name, type: type(r2), dir: '<', props: properties(r2)}] AS in_rels,
                 properties(n) AS all_props
            RETURN n,
                   out_rels + in_rels AS relationships,
                   labels,
                   all_props
            LIMIT 1
        """
        params = {"name": name}
        worker = QueryWorker(self._uri, self._auth, query, params)

        worker.query_finished.connect(callback)
        return worker

    def save_node(self, node_data: Dict[str, Any], callback: Callable) -> WriteWorker:
        """
        Save or update a node and its relationships using a worker.

        Args:
            node_data (dict): Node data including properties and relationships.
            callback (function): Function to call when done.

        Returns:
            WriteWorker: A worker that will execute the write operation.
        """
        self.validate_node_data(node_data)
        worker = WriteWorker(
            self._uri, self._auth, self._save_node_transaction, node_data
        )
        worker.write_finished.connect(callback)
        return worker

    def _save_node_transaction(self, tx: Any, node_data: Dict[str, Any]) -> None:
        """
        Private transaction handler for save_node.
        Preserves and updates system properties (_created, _modified, _author) while replacing all others.

        Args:
            tx: The transaction object.
            node_data (dict): Node data including properties and relationships.
        """
        logger.debug(
            "Starting Save Node Transaction",
            module="Neo4jModel",
            function="_save_node_transaction",
        )

        # Enforce naming style conventions

        node_data = ncc.convert_node_data(node_data)

        # Extract data from node_data
        name = node_data["name"]
        description = node_data["description"]
        tags = node_data["tags"]
        additional_properties = node_data["additional_properties"]
        relationships = node_data["relationships"]
        labels = node_data["labels"]

        # 1. Get existing system properties
        # Updated to specifically check for _created timestamp
        query_get_system = """
        MATCH (n {name: $name, _project: $project})
        RETURN n._created as created
        """
        result = tx.run(query_get_system, name=name, project=self._project)
        record = result.single()

        # 2. Prepare system properties
        system_props = {
            "_author": "System",  # Always set author
            "_modified": datetime.now().isoformat(),  # Always update modified time
            "_project": self._project,  # Always set to active project
        }

        # Only set _created if it doesn't exist
        if not record or record["created"] is None:
            system_props["_created"] = datetime.now().isoformat()
        else:
            system_props["_created"] = record[
                "created"
            ]  # Preserve existing creation time

        # Create a new node if it doesn't exist
        if not record:
            query_create = """
            CREATE (n {name: $name, description: $description, tags: $tags,_project: $project})
            """
            tx.run(
                query_create,
                name=name,
                description=description,
                tags=tags,
                project=self._project,
            )

        # 3. Reset node with core properties and system properties
        base_props = {
            "name": name,
            "description": description,
            "tags": tags,
            **system_props,  # Include system properties in base set
        }

        query_reset = """
        MATCH (n {name: $name, _project: $project})
        SET n = $base_props
        """
        tx.run(query_reset, name=name, base_props=base_props, project=self._project)

        # 4. Handle labels
        result = tx.run(
            "MATCH (n {name: $name,_project:$project}) RETURN labels(n) AS labels",
            name=name,
            project=self._project,
        )
        record = result.single()
        existing_labels = record["labels"] if record else []

        # Determine labels to add and remove
        input_labels_set = set(labels)
        existing_labels_set = set(existing_labels)
        labels_to_add = input_labels_set - existing_labels_set
        labels_to_remove = existing_labels_set - input_labels_set

        # Add new labels
        if labels_to_add:
            labels_str = ":".join([f"`{label}`" for label in labels_to_add])
            query_add = (
                f"MATCH (n {{name: $name,_project:$project }}) SET n:{labels_str}"
            )
            tx.run(query_add, name=name, project=self._project)

        # Remove old labels
        if labels_to_remove:
            labels_str = ", ".join([f"n:`{label}`" for label in labels_to_remove])
            query_remove = (
                f"MATCH (n {{name: $name,_project:$project }}) REMOVE {labels_str}"
            )
            tx.run(query_remove, name=name, project=self._project)

        # Add non-system properties

        # Filter out system properties and description from additional properties
        filtered_additional_props = {
            k: v
            for k, v in additional_properties.items()
            if not k.startswith("_") and k not in ["description", "tags", "name"]
        }

        if filtered_additional_props:
            query_props = "MATCH (n {name: $name, _project:$project}) SET n += $additional_properties"
            tx.run(
                query_props,
                name=name,
                additional_properties=filtered_additional_props,
                project=self._project,
            )

        # 6. Handle relationships
        # Remove existing relationships
        query_remove_rels = "MATCH (n {name: $name,_project:$project})-[r]-() DELETE r"
        tx.run(query_remove_rels, name=name, project=self._project)

        # Create/update relationships
        for rel in relationships:
            rel_type, rel_name, direction, properties = rel

            # Prepare stump node properties
            stump_props = {
                "name": rel_name,
                "_author": "System",
                "_created": datetime.now().isoformat(),
                "_modified": datetime.now().isoformat(),
                "_project": self._project,
            }

            # First check if target exists
            check_query = (
                "MATCH (target {name: $rel_name, _project:$project}) RETURN target"
            )
            result = tx.run(check_query, rel_name=rel_name, project=self._project)
            target_exists = result.single() is not None

            # Handle target node
            if not target_exists:
                # Create new node with STUMP label
                create_query = """
                    CREATE (target:STUMP)
                    SET target = $stump_props
                """
                tx.run(create_query, stump_props=stump_props)

            # Create the relationship
            if direction == ">":
                query_rel = (
                    """
                    MATCH (n {name: $name,_project:$project}), (target {name: $rel_name, _project:$project})
                    MERGE (n)-[r:`%s`]->(target)
                    SET r = $properties
                """
                    % rel_type
                )
            else:
                query_rel = (
                    """
                    MATCH (n {name: $name,_project:$project}), (target {name: $rel_name, _project:$project})
                    MERGE (n)<-[r:`%s`]-(target)
                    SET r = $properties
                """
                    % rel_type
                )

            tx.run(
                query_rel,
                name=name,
                rel_name=rel_name,
                properties=properties,
                project=self._project,
            )

        logger.debug(
            "Finished Save Node Transaction",
            module="Neo4jModel",
            function="_save_node_transaction",
        )

    def delete_node(self, name: str, callback: Callable) -> DeleteWorker:
        """
        Delete a node and all its relationships using a worker.

        Args:
            name (str): Name of the node to delete.
            callback (function): Function to call when done.

        Returns:
            DeleteWorker: A worker that will execute the delete operation.
        """
        worker = DeleteWorker(
            self._uri, self._auth, self._delete_node_transaction, name
        )
        worker.delete_finished.connect(callback)
        return worker

    @staticmethod
    def _delete_node_transaction(tx: Any, name: str) -> None:
        """
        Private transaction handler for delete_node.

        Args:
            tx: The transaction object.
            name (str): Name of the node to delete.
        """
        query = "MATCH (n {name: $name}) DETACH DELETE n"
        tx.run(query, name=name)

    #############################################
    # 3. Node Query Operations
    #############################################

    def get_node_relationships(
        self, node_name: str, depth: int, callback: Callable
    ) -> QueryWorker:
        """
        Get the relationships of a node by name up to a specified depth using a worker.

        Args:
            node_name (str): Name of the node.
            depth (int): The depth of relationships to retrieve.
            callback (function): Function to call with the result.

        Returns:
            QueryWorker: A worker that will execute the query.
        """
        # Validate depth to ensure it's a positive integer
        if not isinstance(depth, int) or depth < 1:
            raise ValueError("Depth must be a positive integer (at least 1)")

        # Safely insert the depth into the query string
        query = f"""
            MATCH path = (n)-[*1..{depth}]-(connected_node)
            WHERE n.name = $name
              AND ALL(r IN relationships(path) WHERE startNode(r) IS NOT NULL AND endNode(r) IS NOT NULL)
              AND ALL(node IN nodes(path) WHERE node IS NOT NULL)
            WITH path, length(path) AS path_length
            UNWIND range(1, path_length) AS idx
            WITH
                nodes(path)[idx] AS current_node,
                relationships(path)[idx - 1] AS current_rel,
                nodes(path)[idx - 1] AS parent_node,
                idx AS depth
            RETURN DISTINCT
                current_node.name AS node_name,
                labels(current_node) AS labels,
                parent_node.name AS parent_name,
                type(current_rel) AS rel_type,
                CASE
                    WHEN startNode(current_rel) = parent_node THEN '>' ELSE '<' END AS direction,
                depth
            ORDER BY depth ASC
        """
        params = {"name": node_name}

        worker = QueryWorker(self._uri, self._auth, query, params)
        worker.query_finished.connect(callback)

        return worker

    def get_node_hierarchy(self) -> Dict[str, Any]:
        """
        Get the hierarchy of nodes grouped by their primary label.

        Returns:
            dict: Category to node names mapping.
        """
        with self.get_session() as session:
            result = session.run(
                """
                MATCH (n)
                WITH n, labels(n) AS labels
                WHERE size(labels) > 1
                RETURN DISTINCT head(labels) as category, 
                       collect(n.name) as nodes
                ORDER BY category
            """
            )
            return {record["category"]: record["nodes"] for record in result}

    def fetch_matching_node_names(
        self, prefix: str, limit: int, callback: Callable
    ) -> QueryWorker:
        """
        Search for nodes whose names match a given prefix using a worker.

        Args:
            prefix (str): The search prefix.
            limit (int): Maximum number of results to return.
            callback (function): Function to call with the result.

        Returns:
            QueryWorker: A worker that will execute the query.
        """
        query = (
            "MATCH (n) WHERE toLower(n.name) CONTAINS toLower($prefix) "
            "AND n._project = $project "
            "RETURN n.name AS name LIMIT $limit"
        )
        params = {"prefix": prefix, "limit": limit, "project": self._project}
        worker = QueryWorker(self._uri, self._auth, query, params)
        worker.query_finished.connect(callback)
        return worker

    def generate_suggestions(
        self,
        node_data: Dict[str, Any],
        suggestions_callback: Callable,
        error_callback: Callable,
    ) -> None:
        """
        Generate suggestions for a given node using SuggestionWorker.

        Args:
            node_data (Dict[str, Any]): The data of the node for which to generate suggestions.
            suggestions_callback (callable): The function to call with the suggestions when ready.
            error_callback (callable): The function to call in case of errors.
        """
        worker = SuggestionWorker(self._uri, self._auth, node_data, self._config)
        worker.suggestions_ready.connect(suggestions_callback)
        worker.error_occurred.connect(error_callback)

        # Ensure the worker is removed from active_workers when finished
        worker.finished.connect(lambda: self.active_workers.discard(worker))

        # Add the worker to the active_workers set to keep a reference
        self.active_workers.add(worker)

        # Start the worker thread
        worker.start()

    def get_last_modified_node(self) -> Optional[Dict[str, Any]]:
        """
        Fetch the last modified node based on the '_modified' property.

        Returns:
            dict: The last modified node data or None if no nodes exist.
        """
        query = """
        MATCH (n)
        RETURN n.name AS name, n._modified AS modified
        ORDER BY modified DESC
        LIMIT 1
        """
        with self.get_session() as session:
            result = session.run(query)
            record = result.single()
            return dict(record) if record else None

    def get_all_node_names(self, callback: Callable[[List[str]], None]) -> QueryWorker:
        """Get all node names from the database.

        Args:
            callback: Function to handle query results

        Returns:
            QueryWorker instance
        """
        query = """
        MATCH (n) 
        WHERE n.name IS NOT NULL
        RETURN n.name AS name
        ORDER BY n.name
        """

        worker = QueryWorker(self._uri, self._auth, query)
        worker.query_finished.connect(
            lambda records: callback([r["name"] for r in records])
        )
        return worker

    def execute_read_query(
        self, query: str, params: Optional[Dict[str, Any]] = None
    ) -> QueryWorker:
        """
        Execute a read-only Cypher query using a QueryWorker.

        Args:
            query: The Cypher query to execute. Must be a read-only query.
            params: Optional parameters for the query

        Returns:
            QueryWorker: Worker that will execute the read-only query

        Raises:
            ValueError: If the query appears to be a write operation
        """
        # Convert query to uppercase for easier checking
        query_upper = query.upper().strip()

        # Define write operations more precisely
        write_operations = {
            # Data modification
            "CREATE": "node or relationship creation",
            "MERGE": "node or relationship merging",
            "DELETE": "node or relationship deletion",
            "REMOVE": "property removal",
            "SET": "property modification",
            "DROP": "schema modification",
            # Administrative
            "CREATE INDEX": "index creation",
            "DROP INDEX": "index deletion",
            "CREATE CONSTRAINT": "constraint creation",
            "DROP CONSTRAINT": "constraint deletion",
        }

        # Check each operation and provide specific error message
        for op, description in write_operations.items():
            if op in query_upper:
                raise ValueError(
                    f"Write operation '{op}' ({description}) not allowed in read-only query"
                )

        # Check for unsafe procedure calls
        unsafe_calls = [
            "CALL db.",  # Database procedures
            "CALL apoc.",  # APOC procedures
            "CALL graph.",  # Graph procedures
        ]

        for call in unsafe_calls:
            if call.upper() in query_upper:
                raise ValueError(
                    f"Unsafe procedure call '{call}' not allowed in read-only query"
                )

        # Create worker with basic parameters
        worker = QueryWorker(self._uri, self._auth, query, params or {})

        logger.debug(
            "query_worker_created",
            has_signal=hasattr(worker, "query_finished"),
        )

        return worker

    def rename_node(
        self, element_id: str, new_name: str, callback: Callable
    ) -> WriteWorker:
        """
        Rename a node using its element ID.

        Args:
            element_id (str): The element ID of the node to rename
            new_name (str): The new name for the node
            callback (Callable): Function to call when operation completes

        Returns:
            WriteWorker: Worker that will execute the rename operation
        """
        query = """
        MATCH (n)
        WHERE elementId(n) = $element_id
        SET n.name = $new_name, 
            n._modified = $timestamp
        RETURN n
        """

        params = {
            "element_id": element_id,
            "new_name": new_name,
            "timestamp": datetime.now().isoformat(),
        }

        worker = WriteWorker(
            self._uri, self._auth, WriteWorker._run_transaction, query, params
        )
        worker.write_finished.connect(callback)

        return worker
