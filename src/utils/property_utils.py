import json
from typing import Any
from typing import Set


def transform_property_value(value_text: str) -> list:
    """
    Transform any property value to an array.
    
    Args:
        value_text (str): The raw value text
        
    Returns:
        list: Always returns a list, even for single values
    """
    if not value_text or value_text.strip() == '':
        return []
        
    # First try to parse as JSON in case it's already properly formatted
    try:
        value = json.loads(value_text)
        # Ensure the result is always an array
        if isinstance(value, list):
            return value
        else:
            return [value]
    except json.JSONDecodeError:
        # Treat as comma-separated values
        return [item.strip() for item in value_text.split(',') if item.strip()]


def validate_property_key(key: str, reserved_keys: Set[str]) -> None:
    """
    Validate a property key.

    Args:
        key (str): The property key to validate
        reserved_keys (Set[str]): Set of reserved key names

    Raises:
        ValueError: If key is invalid
    """
    if key.lower() in reserved_keys:
        raise ValueError(f"Property key '{key}' is reserved")

    if key.startswith("_"):
        raise ValueError(f"Property key '{key}' cannot start with an underscore")
