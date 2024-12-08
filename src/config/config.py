import json
from typing import Any, Dict, List


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


class Config(ConfigNode):
    """Configuration class that maintains hierarchical structure from JSON files."""

    def __init__(self, json_files: List[str]) -> None:
        """Initialize configuration from multiple JSON files."""
        config_tree = {}
        for json_file in json_files:
            print(f"Loading configuration from {json_file}")
            with open(json_file, "r") as f:
                data = json.load(f)
                self._merge_config(config_tree, data)

        super().__init__(config_tree)
        self._add_legacy_attributes(config_tree)

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
                self._add_legacy_attributes(value, f"{key}_" if prefix else key)
            else:
                legacy_name = f"{prefix}{key}" if prefix else key
                setattr(self, legacy_name, value)

    def reload(self, json_files: List[str]) -> None:
        """Reload configuration from JSON files."""
        config_tree = {}
        for json_file in json_files:
            with open(json_file, "r") as f:
                data = json.load(f)
                self._merge_config(config_tree, data)
        super().__init__(config_tree)
        self._add_legacy_attributes(config_tree)
