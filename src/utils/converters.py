"""
This module provides the NamingConventionConverter class, which handles conversions and validations for labels, properties, tags, relationships, and relationship properties.
"""

import re
from typing import Dict, List, Tuple, Any


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
