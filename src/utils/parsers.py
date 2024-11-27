from typing import List


def parse_comma_separated(text: str) -> List[str]:
    """
    Parse comma-separated input.

    Args:
        text (str): The comma-separated input text.

    Returns:
        List[str]: The parsed list of strings.
    """
    return [item.strip() for item in text.split(",") if item.strip()]
