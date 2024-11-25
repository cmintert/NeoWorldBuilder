import json
from typing import Any
from typing import Set


def transform_property_value(value_text: str) -> Any:
    """
    Transform a property value from string to appropriate type.

    Args:
        value_text (str): The raw value text

    Returns:
        Any: Transformed value (could be dict, list, string, etc.)
    """
    if not value_text:
        return value_text

    try:
        return json.loads(value_text)
    except json.JSONDecodeError:
        return value_text


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
