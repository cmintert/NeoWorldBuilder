import json
from typing import Any, Dict


class Config:
    """
    Configuration class to load and access settings from multiple JSON files.
    Args:
        json_files (list): List of paths to the JSON configuration files.
    """

    def __init__(self, json_files: list) -> None:
        """
        Initialize the Config class by loading and merging multiple JSON files.
        Args:
            json_files (list): List of paths to the JSON configuration files.
        """
        self.config_data = {}
        for json_file in json_files:
            print(f"Loading configuration from {json_file}")
            with open(json_file, "r") as f:
                data = json.load(f)
                self._merge_config(data)

    def _merge_config(self, new_data: Dict[str, Any]) -> None:

        for category, values in new_data.items():
            if isinstance(values, dict):
                for key, value in values.items():
                    setattr(self, f"{category}_{key}", value)
                    print(f"Setting {category}_{key} to {value}")
            else:
                setattr(self, category, values)
                print(f"Setting {category} to {values}")

    def reload(self, json_files: list) -> None:
        """
        Reload the configuration from the JSON files and apply changes dynamically.
        Args:
            json_files (list): List of paths to the JSON configuration files.
        """
        self.config_data = {}
        for json_file in json_files:
            with open(json_file, "r") as f:
                data = json.load(f)
                self._merge_config(data)
