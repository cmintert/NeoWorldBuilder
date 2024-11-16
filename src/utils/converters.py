"""
This module provides the NamingConventionConverter class, which handles conversions and validations for labels, properties, tags, relationships, and relationship properties.
"""

import logging
import re
from typing import List, Dict, Any
from typing import Tuple

import pandas as pd


class NamingConventionConverter:
    """
    Class to handle conversions and validations for labels, properties, tags, relationships, and relationship properties.
    """

    @staticmethod
    def to_camel_case(label: str) -> str:
        """
        Convert a label to CamelCase, treating special characters as blanks and removing leading numbers.

        Args:
            label (str): The label to convert.

        Returns:
            str: The label in CamelCase format.
        """
        # Replace special characters with spaces and remove leading numbers
        label = re.sub(r"[^a-zA-Z0-9_ ]", " ", label)
        label = re.sub(r"^\d+", "", label)
        parts = label.split()
        return "".join(word.capitalize() for word in parts)

    @staticmethod
    def to_upper_underscore(relationship_type: str) -> str:
        """
        Convert a relationship type to UPPERCASE_WITH_UNDERSCORES, treating special characters as blanks and removing leading numbers.

        Args:
            relationship_type (str): The relationship type to convert.

        Returns:
            str: The relationship type in UPPERCASE_WITH_UNDERSCORES format.
        """
        # Replace special characters with spaces and remove leading numbers
        relationship_type = re.sub(r"[^a-zA-Z0-9_ ]", " ", relationship_type)
        relationship_type = re.sub(r"^\d+", "", relationship_type)
        return relationship_type.upper().replace(" ", "_")

    @staticmethod
    def to_camel_case_key(key: str) -> str:
        """
        Convert a property key to camelCase, treating special characters as blanks and removing leading numbers.

        Args:
            key (str): The key to convert.

        Returns:
            str: The key in camelCase format.
        """
        # Replace special characters with underscores and remove leading numbers
        key = re.sub(r"[^a-zA-Z0-9_]", "_", key)
        key = re.sub(r"^\d+", "", key)
        parts = key.split("_")
        return parts[0].lower() + "".join(word.capitalize() for word in parts[1:])

    @staticmethod
    def is_camel_case(label: str) -> bool:
        """
        Check if a label is in CamelCase format, treating special characters as blanks and removing leading numbers.

        Args:
            label (str): The label to check.

        Returns:
            bool: True if the label is in CamelCase format, False otherwise.
        """
        # Replace special characters with spaces and remove leading numbers
        label = re.sub(r"[^a-zA-Z0-9_ ]", " ", label)
        label = re.sub(r"^\d+", "", label)
        return label == "".join(word.capitalize() for word in label.split())

    @staticmethod
    def is_upper_underscore(relationship_type: str) -> bool:
        """
        Check if a relationship type is in UPPERCASE_WITH_UNDERSCORES format, treating special characters as blanks and removing leading numbers.

        Args:
            relationship_type (str): The relationship type to check.

        Returns:
            bool: True if the relationship type is in UPPERCASE_WITH_UNDERSCORES format, False otherwise.
        """
        # Replace special characters with spaces and remove leading numbers
        relationship_type = re.sub(r"[^a-zA-Z0-9_ ]", " ", relationship_type)
        relationship_type = re.sub(r"^\d+", "", relationship_type)
        return relationship_type == relationship_type.upper().replace(" ", "_")

    @staticmethod
    def is_camel_case_key(key: str) -> bool:
        """
        Check if a property key is in camelCase format, treating special characters as blanks and removing leading numbers.

        Args:
            key (str): The key to check.

        Returns:
            bool: True if the key is in camelCase format, False otherwise.
        """
        # Replace special characters with underscores and remove leading numbers
        key = re.sub(r"[^a-zA-Z0-9_]", "_", key)
        key = re.sub(r"^\d+", "", key)
        parts = key.split("_")
        formatted_key = parts[0].lower() + "".join(
            word.capitalize() for word in parts[1:]
        )
        return key == formatted_key

    @staticmethod
    def convert_node_data(node_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert labels, property keys, and relationships in node data to enforce naming conventions.

        Args:
            node_data (dict): The node data including labels, properties, and relationships.

        Returns:
            dict: The converted node data.
        """
        # Convert labels to CamelCase
        node_data["labels"] = [
            NamingConventionConverter.to_upper_underscore(label)
            for label in node_data.get("labels", [])
        ]

        # Convert property keys to camelCase
        node_data["additional_properties"] = {
            NamingConventionConverter.to_camel_case_key(k): v
            for k, v in node_data.get("additional_properties", {}).items()
        }

        # Convert relationships
        updated_realationships: List[Tuple[str, str, str, Dict[str, Any]]] = []
        for rel in node_data.get("relationships", []):
            relationship_type, target, direction, properties = rel
            converted_relationship_type = NamingConventionConverter.to_upper_underscore(
                relationship_type
            )
            converted_properties = {
                NamingConventionConverter.to_camel_case_key(k): v
                for k, v in properties.items()
            }
            updated_realationships.append(
                (converted_relationship_type, target, direction, converted_properties)
            )
        node_data["relationships"] = updated_realationships

        return node_data


logger = logging.getLogger(__name__)


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
