from dataclasses import dataclass
from typing import Optional


@dataclass
class ValidationResult:
    is_valid: bool
    error_message: Optional[str] = None


def validate_node_name(name: str, max_length: int) -> ValidationResult:
    """
    Validate a node name according to business rules.

    Args:
        name (str): The node name to validate
        max_length (int): Maximum allowed length for node name

    Returns:
        ValidationResult: Contains validation result and error message if invalid
    """
    if not name:
        return ValidationResult(False, "Node name cannot be empty.")

    if len(name) > max_length:
        return ValidationResult(
            False, f"Node name cannot exceed {max_length} characters."
        )

    return ValidationResult(True)
