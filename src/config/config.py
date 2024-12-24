import copy
import json
from typing import Any, Dict, List, Optional


class ConfigNode:
    """A node in the configuration tree that allows both dictionary and attribute access."""

    def __init__(self, data: Dict[str, Any]) -> None:
        self._data = {}
        for key, value in data.items():
            if isinstance(value, dict):
                self._data[key] = ConfigNode(value)
            else:
                self._data[key] = value

    def __getattr__(self, name: str) -> Any:
        if name in self._data:
            return self._data[name]
        raise AttributeError(f"Config has no attribute '{name}'")

    def __getitem__(self, key: str) -> Any:
        return self._data[key]

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set a configuration value."""
        path_parts = key.split(".")
        current = self._data

        # Navigate to the correct nested dictionary
        for part in path_parts[:-1]:
            if part not in current:
                current[part] = {}
            if not isinstance(current[part], dict):
                current[part] = {}
            current = current[part]

        # Set the value
        current[path_parts[-1]] = value

    def to_dict(self) -> Dict[str, Any]:
        """Convert the config node back to a plain dictionary."""
        result = {}
        for key, value in self._data.items():
            if isinstance(value, ConfigNode):
                result[key] = value.to_dict()
            else:
                result[key] = value
        return result


class Config(ConfigNode):
    """Configuration class that maintains hierarchical structure from JSON files."""

    def __init__(self, json_files: List[str]) -> None:
        """Initialize configuration from multiple JSON files."""
        self._file_mapping: Dict[str, Dict[str, Any]] = (
            {}
        )  # Maps top-level keys to their source files
        self._json_files = json_files
        config_tree = {}

        for json_file in json_files:
            print(f"Loading configuration from {json_file}")
            with open(json_file, "r") as f:
                data = json.load(f)
                # Store which file each top-level key came from
                for key in data.keys():
                    self._file_mapping[key] = json_file
                self._merge_config(config_tree, data)

        super().__init__(config_tree)
        self._add_legacy_attributes(config_tree)
        self._original_config = copy.deepcopy(
            config_tree
        )  # Store original config for change tracking

    def _merge_config(self, tree: Dict[str, Any], new_data: Dict[str, Any]) -> None:
        """Merge while maintaining hierarchy."""
        for key, value in new_data.items():
            if isinstance(value, dict):
                if key not in tree:
                    tree[key] = {}
                current = tree[key]
                for subkey, subvalue in value.items():
                    print(f"Setting {key}.{subkey} to {subvalue}")
                    current[subkey] = subvalue
            else:
                print(f"Setting {key} to {value}")
                tree[key] = value

    def _add_legacy_attributes(self, tree: Dict[str, Any], prefix: str = "") -> None:
        """Add flat attribute access for backwards compatibility."""
        for key, value in tree.items():
            if isinstance(value, dict):
                self._add_legacy_attributes(value, f"{prefix}{key}_" if prefix else key)
            else:
                legacy_name = f"{prefix}{key}" if prefix else key
                setattr(self, legacy_name, value)

    def set_value(self, key: str, value: Any, persist: bool = True) -> None:
        """
        Set a configuration value and optionally persist it to disk.

        Args:
            key: Dot-notation path to the config value (e.g., 'ui.colors.activeSave')
            value: The new value to set
            persist: Whether to immediately write the change to disk
        """
        # Set the value in memory
        self.set(key, value)

        if persist:
            self.save_changes()

    def save_changes(self, specific_file: Optional[str] = None) -> None:
        """
        Save configuration changes back to the JSON files.

        Args:
            specific_file: Optional specific JSON file to update. If None, updates all changed files.
        """
        current_config = self.to_dict()

        # Determine which files need updating
        files_to_update = set()
        for key, value in current_config.items():
            if key in self._file_mapping:
                source_file = self._file_mapping[key]
                if specific_file is None or source_file == specific_file:
                    files_to_update.add(source_file)

        # Update each file
        for file_path in files_to_update:
            # Read current file content
            with open(file_path, "r") as f:
                file_config = json.load(f)

            # Update changed values
            for key, value in current_config.items():
                if self._file_mapping.get(key) == file_path:
                    file_config[key] = value

            # Write back to file
            with open(file_path, "w") as f:
                json.dump(file_config, f, indent=2)

            print(f"Updated configuration in {file_path}")

    def reload(self, json_files: Optional[List[str]] = None) -> None:
        """Reload configuration from JSON files."""
        if json_files is not None:
            self._json_files = json_files

        config_tree = {}
        self._file_mapping.clear()

        for json_file in self._json_files:
            with open(json_file, "r") as f:
                data = json.load(f)
                for key in data.keys():
                    self._file_mapping[key] = json_file
                self._merge_config(config_tree, data)

        super().__init__(config_tree)
        self._add_legacy_attributes(config_tree)
        self._original_config = copy.deepcopy(config_tree)
