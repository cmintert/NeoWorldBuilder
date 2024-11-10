import json
from typing import Any


class Config:
    """
    Configuration class to load and access settings from a JSON file.

    Args:
        json_file (str): Path to the JSON configuration file.
    """

    def __init__(self, json_file: str) -> None:
        """
        Initialize the Config class by loading the JSON file and setting attributes.

        Args:
            json_file (str): Path to the JSON configuration file.
        """
        with open(json_file, "r") as f:
            constants = json.load(f)
        for category, values in constants.items():
            if isinstance(values, dict):
                for key, value in values.items():
                    setattr(self, f"{category}_{key}", value)
            else:
                setattr(self, category, values)
