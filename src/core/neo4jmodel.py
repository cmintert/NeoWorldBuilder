"""
This module provides the Neo4jModel class, which serves as a gateway to the Neo4j database.
It includes methods for connecting to the database, performing CRUD operations on nodes, and querying node relationships.
"""

import datetime
import logging
from datetime import datetime
from typing import Dict, Any

from PyQt6.QtWidgets import QMessageBox
from neo4j import GraphDatabase

from core.neo4jworkers import QueryWorker, WriteWorker, DeleteWorker, SuggestionWorker
from utils.converters import NamingConventionConverter as ncc


class Neo4jModel:
    """
    Gateway to the Neo4j database.

    Args:
        uri (str): The URI of the Neo4j database.
        username (str): The username for authentication.
        password (str): The password for authentication.
    """

    def __init__(self, uri, username, password):
        """
        Initialize Neo4j connection parameters and establish connection.

        Args:
            uri (str): The URI of the Neo4j database.
            username (str): The username for authentication.
            password (str): The password for authentication.
        """
        self._uri = uri
        self._auth = (username, password)
        self._driver = None
        self.connect()
        logging.info("Neo4jModel initialized and connected to the database.")

    def connect(self):
        """
        Establish a connection to the Neo4j database.
        """
        if not self._driver:
            self._driver = GraphDatabase.driver(self._uri, auth=self._auth)

    def ensure_connection(self):
        """
        Ensure that the connection to the Neo4j database is valid.
        Reconnect if the connection is not valid.
        """
        try:
            if self._driver:
                self._driver.verify_connectivity()
            else:
                self.connect()
        except Exception as e:
            logging.warning(f"Connection verification failed: {e}")
            self.connect()

    def get_session(self):
        """
        Get a database session, ensuring connection is valid.

        Returns:
            The database session.
        """
        self.ensure_connection()
        return self._driver.session()

    def close(self):
        """
        Safely close the driver.
        """
        if self._driver:
            try:
                self._driver.close()
            finally:
                self._driver = None
        logging.info("Neo4jModel connection closed.")

    #############################################
    # 2. Node CRUD Operations
    #############################################

    def validate_node_data(self, node_data):
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

    def load_node(self, name, callback):
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

    def save_node(self, node_data, callback):
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

    @staticmethod
    def _save_node_transaction(tx, node_data):
        """
        Private transaction handler for save_node.
        Preserves and updates system properties (_created, _modified, _author) while replacing all others.

        Args:
            tx: The transaction object.
            node_data (dict): Node data including properties and relationships.
        """
        logging.debug(
            "+++++++++++++++++ Starting Save Node Transaction +++++++++++++++++++++++"
        )

        # Enforce naming style conventions

        logging.debug(f"Node data to save: {node_data}")
        logging.debug(f"Node data is of type: {type(node_data)}")
        original_node_data = node_data
        node_data = ncc.convert_node_data(node_data)

        # Compare the original and converted data and give feedback on automatic conversion
        # Feedback is in form of an info message popup

        if original_node_data != node_data:
            logging.info(
                "Node data was automatically converted to adhere to naming conventions."
            )
            logging.info(f"Original data: {original_node_data}")
            logging.info(f"Converted data: {node_data}")
            QMessageBox.information(
                None,
                "Naming Convention Conversion",
                "Node data was automatically converted to adhere to naming conventions.\n"
                f"Original data: {original_node_data}\n"
                f"Converted data: {node_data}",
            )

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
        MATCH (n {name: $name})
        RETURN n._created as created
        """
        result = tx.run(query_get_system, name=name)
        record = result.single()

        # 2. Prepare system properties
        system_props = {
            "_author": "System",  # Always set author
            "_modified": datetime.now().isoformat(),  # Always update modified time
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
            CREATE (n {name: $name, description: $description, tags: $tags})
            """
            tx.run(query_create, name=name, description=description, tags=tags)

        # 3. Reset node with core properties and system properties
        base_props = {
            "name": name,
            "description": description,
            "tags": tags,
            **system_props,  # Include system properties in base set
        }

        query_reset = """
        MATCH (n {name: $name})
        SET n = $base_props
        """
        tx.run(query_reset, name=name, base_props=base_props)

        # 4. Handle labels
        result = tx.run("MATCH (n {name: $name}) RETURN labels(n) AS labels", name=name)
        record = result.single()
        existing_labels = record["labels"] if record else []
        existing_labels = [label for label in existing_labels if label != "Node"]

        # Determine labels to add and remove
        input_labels_set = set(labels) - {"Node"}
        existing_labels_set = set(existing_labels)
        labels_to_add = input_labels_set - existing_labels_set
        labels_to_remove = existing_labels_set - input_labels_set

        # Add new labels
        if labels_to_add:
            labels_str = ":".join([f"`{label}`" for label in labels_to_add])
            query_add = f"MATCH (n {{name: $name}}) SET n:{labels_str}"
            tx.run(query_add, name=name)

        # Remove old labels
        if labels_to_remove:
            labels_str = ", ".join([f"n:`{label}`" for label in labels_to_remove])
            query_remove = f"MATCH (n {{name: $name}}) REMOVE {labels_str}"
            tx.run(query_remove, name=name)

        # Add non-system properties

        if filtered_additional_props := {
            k: v for k, v in additional_properties.items() if not k.startswith("_")
        }:
            query_props = "MATCH (n {name: $name}) SET n += $additional_properties"
            tx.run(
                query_props, name=name, additional_properties=filtered_additional_props
            )

        # 6. Handle relationships
        # Remove existing relationships
        query_remove_rels = "MATCH (n {name: $name})-[r]-() DELETE r"
        tx.run(query_remove_rels, name=name)

        # Create/update relationships
        for rel in relationships:
            rel_type, rel_name, direction, properties = rel
            if direction == ">":
                query_rel = (
                    f"MATCH (n {{name: $name}}), (m {{name: $rel_name}}) "
                    f"MERGE (n)-[r:`{rel_type}`]->(m) "
                    "SET r = $properties"
                )
            else:
                query_rel = (
                    f"MATCH (n {{name: $name}}), (m {{name: $rel_name}}) "
                    f"MERGE (n)<-[r:`{rel_type}`]-(m) "
                    "SET r = $properties"
                )
            tx.run(query_rel, name=name, rel_name=rel_name, properties=properties)

        logging.debug(
            "+++++++++++++++++ Finished Save Node Transaction +++++++++++++++++++++++"
        )

    def delete_node(self, name, callback):
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
    def _delete_node_transaction(tx, name):
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

    def get_node_relationships(self, node_name: str, depth: int, callback: callable):
        """
        Get the relationships of a node by name up to a specified depth using a worker.

        Args:
            node_name (str): Name of the node.
            depth (int): The depth of relationships to retrieve.
            callback (function): Function to call with the result.

        Returns:
            QueryWorker: A worker that will execute the query.
        """
        depth += 1  # Adjust depth for query
        query = f"""
            MATCH path = (n {{name: $name}})-[*1..{depth}]-()
            WHERE ALL(r IN relationships(path) WHERE startNode(r) IS NOT NULL AND endNode(r) IS NOT NULL)
              AND ALL(node IN nodes(path) WHERE node IS NOT NULL)
            WITH path, length(path) AS path_length
            UNWIND range(1, path_length - 1) AS idx
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

    def get_node_hierarchy(self):
        """
        Get the hierarchy of nodes grouped by their primary label.

        Returns:
            dict: Category to node names mapping.
        """
        with self.get_session() as session:
            result = session.run(
                """
                MATCH (n:Node)
                WITH n, labels(n) AS labels
                WHERE size(labels) > 1
                RETURN DISTINCT head(labels) as category, 
                       collect(n.name) as nodes
                ORDER BY category
            """
            )
            return {record["category"]: record["nodes"] for record in result}

    def fetch_matching_node_names(self, prefix, limit, callback):
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
            "RETURN n.name AS name LIMIT $limit"
        )
        params = {"prefix": prefix, "limit": limit}
        worker = QueryWorker(self._uri, self._auth, query, params)
        worker.query_finished.connect(callback)
        return worker

    def generate_suggestions(
        self,
        node_data: Dict[str, Any],
        suggestions_callback: callable,
        error_callback: callable,
    ):
        """
        Generate suggestions for a given node using SuggestionWorker.

        Args:
            node_data (Dict[str, Any]): The data of the node for which to generate suggestions.
            suggestions_callback (callable): The function to call with the suggestions when ready.
            error_callback (callable): The function to call in case of errors.
        """
        worker = SuggestionWorker(self._uri, self._auth, node_data)
        worker.suggestions_ready.connect(suggestions_callback)
        worker.error_occurred.connect(error_callback)

        # Ensure the worker is removed from active_workers when finished
        worker.finished.connect(lambda: self.active_workers.discard(worker))

        # Add the worker to the active_workers set to keep a reference
        self.active_workers.add(worker)

        # Start the worker thread
        worker.start()
