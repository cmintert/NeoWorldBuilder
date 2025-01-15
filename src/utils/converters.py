"""
This module provides the Neo4jNameValidator class, which handles validation for labels, properties, tags, and relationships according to Neo4j requirements.
"""

import logging
from typing import Dict, Any, List, Tuple

import pandas as pd

from .validation_rules import ValidationRules

logger = logging.getLogger(__name__)


class Neo4jNameValidator:
    """
    Class to handle validation for Neo4j entity names according to Neo4j requirements.
    """

    def __init__(self):
        self.rules = ValidationRules()

    def validate_label(self, label: str) -> Tuple[bool, str]:
        """
        Validate a label according to Neo4j requirements.

        Args:
            label: The label to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not label or not label.strip():
            return False, self.rules.EMPTY_NAME_ERROR

        if len(label) > self.rules.MAX_LENGTH:
            return False, self.rules.LENGTH_ERROR.format(self.rules.MAX_LENGTH)

        if not self.rules.valid_chars_check.match(label):
            return False, f"Label '{label}': {self.rules.INVALID_CHARS_ERROR}"

        return True, ""

    def validate_relationship_type(self, rel_type: str) -> Tuple[bool, str]:
        """
        Validate a relationship type according to Neo4j requirements.

        Args:
            rel_type: The relationship type to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not rel_type or not rel_type.strip():
            return False, self.rules.EMPTY_NAME_ERROR

        if len(rel_type) > self.rules.MAX_LENGTH:
            return False, self.rules.LENGTH_ERROR.format(self.rules.MAX_LENGTH)

        if not self.rules.valid_chars_check.match(rel_type):
            return (
                False,
                f"Relationship type '{rel_type}': {self.rules.INVALID_CHARS_ERROR}",
            )

        return True, ""

    def validate_property_key(self, key: str) -> Tuple[bool, str]:
        """
        Validate a property key according to Neo4j requirements.

        Args:
            key: The property key to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not key or not key.strip():
            return False, self.rules.EMPTY_NAME_ERROR

        if len(key) > self.rules.MAX_LENGTH:
            return False, self.rules.LENGTH_ERROR.format(self.rules.MAX_LENGTH)

        if not self.rules.valid_chars_check.match(key):
            return False, f"Property key '{key}': {self.rules.INVALID_CHARS_ERROR}"

        return True, ""

    def validate_node_data(self, node_data: Dict[str, Any]) -> List[str]:
        """
        Validate all names in node data according to Neo4j requirements.

        Args:
            node_data: Dictionary containing node data

        Returns:
            List of error messages (empty if all valid)
        """
        errors = []

        # Validate labels
        for label in node_data.get("labels", []):
            valid, error = self.validate_label(label)
            if not valid:
                errors.append(error)

        # Validate relationships
        for rel in node_data.get("relationships", []):
            rel_type = rel[0]
            valid, error = self.validate_relationship_type(rel_type)
            if not valid:
                errors.append(error)

        # Validate property keys
        for key in node_data.get("additional_properties", {}):
            valid, error = self.validate_property_key(key)
            if not valid:
                errors.append(error)

        return errors


class DataFrameBuilder:
    def __init__(self):
        # Define expected columns
        self.nodes_columns = ["name"]
        self.properties_columns = ["node_name", "property", "value"]
        self.tags_columns = ["node_name", "tag"]
        self.labels_columns = ["node_name", "label"]
        self.relationships_columns = [
            "id",
            "source_name",
            "target_name",
            "relationship_type",
            "direction",
        ]
        self.rel_properties_columns = ["relationship_id", "property", "value"]

        # Initialize record lists
        self.nodes_list = []
        self.properties_records = []
        self.tags_records = []
        self.labels_records = []
        self.relationships_records = []
        self.rel_properties_records = []
        self.node_names = set()
        self.relationship_id_counter = 0

    def create_dataframes_from_data(
        self, nodes_data: List[Dict[str, Any]]
    ) -> Dict[str, pd.DataFrame]:
        if not nodes_data:
            logger.info("No node data provided. Returning empty DataFrames.")
            return self._empty_dataframes()

        for node in nodes_data:
            self._process_node(node)

        for node in nodes_data:
            self._process_relationships(node)

        return self._build_dataframes()

    def _empty_dataframes(self) -> Dict[str, pd.DataFrame]:
        return {
            "nodes": pd.DataFrame(columns=self.nodes_columns),
            "properties": pd.DataFrame(columns=self.properties_columns),
            "tags": pd.DataFrame(columns=self.tags_columns),
            "labels": pd.DataFrame(columns=self.labels_columns),
            "relationships": pd.DataFrame(columns=self.relationships_columns),
            "relationship_properties": pd.DataFrame(
                columns=self.rel_properties_columns
            ),
        }

    def _build_dataframes(self) -> Dict[str, pd.DataFrame]:
        nodes_df = pd.DataFrame(
            self.nodes_list, columns=self.nodes_columns
        ).drop_duplicates(subset=["name"])
        properties_df = pd.DataFrame(
            self.properties_records, columns=self.properties_columns
        )
        tags_df = pd.DataFrame(self.tags_records, columns=self.tags_columns)
        labels_df = pd.DataFrame(self.labels_records, columns=self.labels_columns)
        relationships_df = pd.DataFrame(
            self.relationships_records, columns=self.relationships_columns
        )
        rel_properties_df = pd.DataFrame(
            self.rel_properties_records, columns=self.rel_properties_columns
        )

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

    def _process_node(self, node: Dict[str, Any]):
        node_name = node.get("name")
        if not node_name:
            logger.warning("Encountered a node without a 'name'. Skipping.")
            return

        if node_name in self.node_names:
            logger.debug(
                f"Duplicate node '{node_name}' found. Skipping addition to nodes_list."
            )
            return

        self.node_names.add(node_name)
        self.nodes_list.append({"name": node_name})

        # Process properties
        self._process_properties(node_name, node.get("properties", {}))

        # Process tags
        self._process_list_attribute(
            node_name,
            node.get("tags", []),
            self.tags_records,
            "tag",
            f"Tags for node '{node_name}' are not a list. Skipping tags.",
        )

        # Process labels
        self._process_list_attribute(
            node_name,
            node.get("labels", []),
            self.labels_records,
            "label",
            f"Labels for node '{node_name}' are not a list. Skipping labels.",
        )

    def _process_properties(self, node_name: str, properties: Dict[str, Any]):
        if not isinstance(properties, dict):
            logger.warning(
                f"Properties for node '{node_name}' are not a dict. Skipping properties."
            )
            return

        for key, value in properties.items():
            self.properties_records.append(
                {
                    "node_name": node_name,
                    "property": key,
                    "value": value,
                }
            )

    def _process_list_attribute(
        self,
        node_name: str,
        attribute: Any,
        records_list: List[Dict[str, Any]],
        attribute_name: str,
        warning_message: str,
    ):
        if not isinstance(attribute, list):
            logger.warning(warning_message)
            return

        for item in attribute:
            records_list.append(
                {
                    "node_name": node_name,
                    attribute_name: item,
                }
            )

    def _process_relationships(self, node: Dict[str, Any]):
        source_name = node.get("name")
        if not source_name:
            return

        relationships = node.get("relationships", [])
        if not isinstance(relationships, list):
            logger.warning(
                f"Relationships for node '{source_name}' are not a list. Skipping relationships."
            )
            return

        for rel in relationships:
            self._process_single_relationship(source_name, rel)

    def _process_single_relationship(self, source_name: str, rel: Dict[str, Any]):
        relationship_type = rel.get("relationship")
        target_name = rel.get("target")
        direction = rel.get("direction", "UNKNOWN")
        properties = rel.get("properties", {})

        if not relationship_type or not target_name:
            logger.warning(
                f"Incomplete relationship in node '{source_name}': {rel}. Skipping."
            )
            return

        if not isinstance(properties, dict):
            logger.warning(
                f"Properties for relationship '{relationship_type}' in node '{source_name}' are not a dict. Skipping properties."
            )
            properties = {}

        if target_name not in self.node_names:
            # Add missing target node
            self.nodes_list.append({"name": target_name})
            self.node_names.add(target_name)
            logger.debug(
                f"Added missing target node '{target_name}' from relationship."
            )

        # Add relationship record
        self.relationships_records.append(
            {
                "id": self.relationship_id_counter,
                "source_name": source_name,
                "target_name": target_name,
                "relationship_type": relationship_type,
                "direction": direction,
            }
        )

        # Add relationship properties
        for prop_key, prop_value in properties.items():
            self.rel_properties_records.append(
                {
                    "relationship_id": self.relationship_id_counter,
                    "property": prop_key,
                    "value": prop_value,
                }
            )

        self.relationship_id_counter += 1
