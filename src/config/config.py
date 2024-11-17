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
            with open(json_file, "r") as f:
                data = json.load(f)
                self._merge_config(data)

    def _merge_config(self, new_data: Dict[str, Any]) -> None:
        """
        Merge new configuration data into the existing configuration.

        Args:
            new_data (Dict[str, Any]): New configuration data to merge.
        """
        for category, values in new_data.items():
            if isinstance(values, dict):
                if category not in self.config_data:
                    self.config_data[category] = {}
                self.config_data[category].update(values)
            else:
                self.config_data[category] = values

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

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value by key.

        Args:
            key (str): The key of the configuration value.
            default (Any): The default value to return if the key is not found.

        Returns:
            Any: The configuration value.
        """
        keys = key.split("_")
        value = self.config_data
        for k in keys:
            value = value.get(k, default)
            if value is default:
                break
        return value
