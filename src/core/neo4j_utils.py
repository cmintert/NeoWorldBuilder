"""
Utility functions for Neo4j data processing and conversion.
"""

from typing import Any, Dict, List, Set

import pandas as pd


def convert_neo4j_result_to_df(result_records: List[Dict]) -> pd.DataFrame:
    """
    Convert Neo4j query results to a properly structured DataFrame.

    Args:
        result_records: List of Neo4j record dictionaries

    Returns:
        pd.DataFrame: Properly structured DataFrame with normalized columns
    """
    # First, normalize the nested structure
    normalized_data = []

    for record in result_records:
        if isinstance(record, dict):
            # Handle direct dictionary results
            normalized_record = record
        else:
            # Handle Neo4j Record objects
            normalized_record = dict(record.get("result", {}))

        # Ensure all expected fields exist
        normalized_record.setdefault("properties", {})
        normalized_record.setdefault("labels", [])
        normalized_record.setdefault("relationships", [])

        normalized_data.append(normalized_record)

    # Create DataFrame with explicit columns
    df = pd.DataFrame(normalized_data)

    # Ensure required columns exist
    required_columns = {"properties", "labels", "relationships"}
    for col in required_columns:
        if col not in df.columns:
            df[col] = None if col == "properties" else []

    return df


def validate_neo4j_result(result: Any) -> None:
    """
    Validate Neo4j query results.

    Args:
        result: Query result to validate

    Raises:
        ValidationError: If validation fails
    """
    if result is None:
        raise ValidationError("Query returned None result")

    if not isinstance(result, (list, dict)):
        raise ValidationError(f"Expected list or dict, got {type(result)}")


def validate_dataframe(df: pd.DataFrame, required_columns: Set[str]) -> None:
    """
    Validate DataFrame structure.

    Args:
        df: DataFrame to validate
        required_columns: Set of required column names

    Raises:
        ValidationError: If validation fails
    """
    missing_columns = required_columns - set(df.columns)
    if missing_columns:
        raise ValidationError(f"Missing required columns: {missing_columns}")


class ValidationError(Exception):
    """Custom exception for data validation errors"""

    pass
