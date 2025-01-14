import copy
import json
import os
import platform
from pathlib import Path
from typing import Any, Dict, List, Optional

import structlog

logger = structlog.get_logger().bind(module="config")


class ConfigNode:
    """A node in the configuration tree that allows both dictionary and attribute access."""

    def __init__(
        self,
        data: Dict[str, Any],
        source_file: Optional[str] = None,
        environment: Optional[str] = None,
    ):
        self._data = {}
        self._source_file = source_file
        self._env_values = {}
        self._environment = environment

        for key, value in data.items():
            if isinstance(value, dict):
                self._data[key] = ConfigNode(value, source_file, environment)
            else:
                self._data[key] = value

    def __getattr__(self, name: str) -> Any:
        if name in self._env_values:
            # Environment override takes precedence
            return self._env_values[name]
        if name in self._data:
            return self._data[name]
        raise AttributeError(f"Config has no attribute '{name}'")

    def __setattr__(self, name: str, value: Any) -> None:
        if name.startswith("_"):
            super().__setattr__(name, value)
        else:
            self._data[name] = value

    def __setitem__(self, key: str, value: Any) -> None:
        self._data[key] = value

    def __getitem__(self, key: str) -> Any:
        return self._data[key]

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set a configuration value.

        In development, we write directly to source configs.
        In other environments, we store values in _env_values.
        """
        path_parts = key.split(".")

        # Determine where to store the value
        if self._environment == "development":
            target_dict = self._data
        else:
            target_dict = self._env_values

        # Navigate to the correct nested dictionary
        current = target_dict
        for part in path_parts[:-1]:
            if part not in current:
                current[part] = {}
            current = current[part]

        # Set the value
        current[path_parts[-1]] = value

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the config node to a plain dictionary, respecting environment values.

        This method creates a complete picture of our configuration by:
        1. Starting with the base configuration from source files
        2. Recursively converting nested ConfigNode objects
        3. Overlaying any environment-specific values

        The resulting dictionary represents the actual configuration as the
        application should see it, with environment-specific values taking
        precedence over base values.

        Returns:
            Dict[str, Any]: The complete configuration dictionary
        """
        # First, create our base result dictionary from source configuration
        result = {}

        # Process all base configuration values
        for key, value in self._data.items():
            if isinstance(value, ConfigNode):
                # Recursively convert nested configuration nodes
                result[key] = value.to_dict()
            else:
                # Copy primitive values directly
                result[key] = value

        # Now overlay any environment-specific values
        # These take precedence over the base configuration
        for key, value in self._env_values.items():
            if isinstance(value, ConfigNode):
                # If we have a nested ConfigNode in environment values,
                # we need to merge it with any existing nested values
                if key in result:
                    result[key].update(value.to_dict())
                else:
                    result[key] = value.to_dict()
            else:
                # For primitive values, simply override the base value
                result[key] = value

        return result


class Config(ConfigNode):
    """Configuration class that maintains hierarchical structure from JSON files."""

    def __init__(self, json_files: List[str]) -> None:

        self._file_mapping = {}  # Maps top-level keys to their source files
        self._json_files = json_files

        # First determine our environment from system.json
        system_json = next(f for f in json_files if f.endswith("system.json"))
        with open(system_json, "r") as f:
            system_config = json.load(f)
            self._environment = system_config.get("ENVIRONMENT", "development")

        # Set up paths based on environment
        self._source_path = Path(__file__).parent
        if self._environment != "development":
            self._env_path = self._get_env_specific_path()
            self._ensure_env_config_exists()

        # Load configuration data
        config_tree = {}  # This will hold all our configuration values

        # In development, we just load from source files
        if self._environment == "development":
            for json_file in json_files:
                with open(json_file, "r") as f:
                    data = json.load(f)
                    # Store which file each top-level key came from
                    for key in data.keys():
                        self._file_mapping[key] = json_file
                    self._merge_config(config_tree, data)
        else:
            # In other environments, we need to handle both source and environment files
            for json_file in json_files:
                source_path = Path(json_file)
                env_file = self._env_path / source_path.name

                # First load the source file
                with open(json_file, "r") as f:
                    data = json.load(f)
                    for key in data.keys():
                        self._file_mapping[key] = json_file
                    self._merge_config(config_tree, data)

                # Then overlay environment-specific values if they exist
                if env_file.exists():
                    with open(env_file, "r") as f:
                        env_data = json.load(f)
                        self._merge_config(config_tree, env_data)

        # Finally, initialize the ConfigNode with our complete tree
        super().__init__(config_tree, source_file=None, environment=self._environment)

    def _ensure_env_config_exists(self) -> None:
        """Ensure environment-specific config files exist.

        If running in a non-development environment for the first time,
        this copies the default configs to the environment-specific location
        while maintaining the original source files unchanged.
        """
        if not self._env_path.exists():
            self._env_path.mkdir(parents=True, exist_ok=True)

            # Copy each source config to environment path if it doesn't exist
            for json_file in self._json_files:
                source_path = Path(json_file)
                env_file = self._env_path / source_path.name

                if not env_file.exists():
                    with source_path.open("r") as src, env_file.open("w") as dst:
                        content = json.load(src)
                        json.dump(content, dst, indent=2)

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
        """Save configuration changes back to the appropriate JSON files."""
        current_config = self.to_dict()

        logger.info(
            "Preparing to save configuration",
            environment=self._environment,
            is_development=(self._environment == "development"),
        )

        logger.debug(
            "Saving configuration changes",
            current_config=self.to_dict(),
            file_mapping=self._file_mapping,
        )

        # Determine target directory based on environment
        target_dir = (
            self._source_path if self._environment == "development" else self._env_path
        )

        logger.info(
            "Directory status before operations",
            target_dir=str(target_dir),
            exists=target_dir.exists(),
            is_dir=target_dir.is_dir() if target_dir.exists() else None,
            parent_exists=target_dir.parent.exists(),
            absolute_path=str(target_dir.absolute()),
        )
        # Ensure target directory exists
        try:
            if not target_dir.exists():

                logger.info(
                    "Creating configuration directory",
                    directory=str(target_dir),
                    parent_dir=str(target_dir.parent),
                    parent_exists=target_dir.parent.exists(),
                )

                target_dir.parent.mkdir(exist_ok=True)
                target_dir.mkdir(exist_ok=True)

                # Verify after creation
                logger.info(
                    "Directory creation result",
                    exists=target_dir.exists(),
                    is_dir=target_dir.is_dir() if target_dir.exists() else None,
                    absolute_path=str(target_dir.absolute()),
                )

            # Verify directory was created
            if not target_dir.exists():
                raise RuntimeError(
                    f"Failed to create configuration directory: {target_dir}"
                )

            logger.info("Configuration directory verified", directory=str(target_dir))
        except Exception as e:
            logger.error(
                "Failed to create/verify config directory",
                error=str(e),
                directory=str(target_dir),
            )
            raise

        # Determine which files need updating
        files_to_update = set()
        for key, value in current_config.items():
            if key in self._file_mapping:
                source_file = self._file_mapping[key]
                if specific_file is None or source_file == specific_file:
                    files_to_update.add(source_file)

        successful_updates = []
        failed_updates = []

        # Update each file
        for source_file in files_to_update:
            source_path = Path(source_file)
            target_file = target_dir / source_path.name

            try:
                # Read existing configuration if the file exists
                if target_file.exists():
                    with open(target_file, "r") as f:
                        file_config = json.load(f)
                else:
                    file_config = {}

                # Update changed values
                for key, value in current_config.items():
                    if self._file_mapping.get(key) == source_file:
                        file_config[key] = value

                # Write the updated configuration
                with open(target_file, "w") as f:
                    json.dump(file_config, f, indent=2)

                # Verify file was written
                if not target_file.exists():
                    logger.error(
                        "File not found after write",
                        file=str(target_file),
                        parent_exists=target_file.parent.exists(),
                        parent_is_dir=(
                            target_file.parent.is_dir()
                            if target_file.parent.exists()
                            else None
                        ),
                    )
                else:
                    file_size = target_file.stat().st_size
                    logger.info(
                        "File write verification",
                        file=str(target_file),
                        exists=True,
                        size=file_size,
                    )

                # Verify file content
                with open(target_file, "r") as f:
                    verification_content = json.load(f)
                    if verification_content != file_config:
                        raise ValueError("File content verification failed")

                successful_updates.append(target_file)
                logger.info(
                    "Configuration file updated and verified", file=str(target_file)
                )

            except Exception as e:
                failed_updates.append((target_file, str(e)))
                logger.error(
                    "Failed to update configuration file",
                    file=str(target_file),
                    error=str(e),
                )

                if isinstance(e, PermissionError):
                    raise PermissionError(
                        f"Cannot write to configuration file {target_file}. "
                        "Please check file permissions."
                    ) from e
                elif isinstance(e, FileNotFoundError):
                    raise FileNotFoundError(
                        f"Cannot create configuration file {target_file}. "
                        "Please check directory permissions."
                    ) from e
                else:
                    raise RuntimeError(
                        f"Failed to save configuration to {target_file}: {str(e)}"
                    ) from e

        # Final status report
        if successful_updates:
            logger.info(
                "Configuration updates completed",
                successful=len(successful_updates),
                failed=len(failed_updates),
            )
        if failed_updates:
            logger.error(
                "Some configuration updates failed",
                failed_files=[str(f[0]) for f in failed_updates],
                errors=[f[1] for f in failed_updates],
            )

    def reload(self, json_files: Optional[List[str]] = None) -> None:
        """Reload configuration from appropriate JSON files.

        This method reloads the configuration, respecting the environment settings:
        - In development: Loads directly from source configuration files
        - In other environments: Loads source files as defaults, then overlays
          environment-specific configurations

        Args:
            json_files: Optional list of JSON files to reload. If None, uses existing file list.
        """
        # Update file list if provided
        if json_files is not None:
            self._json_files = json_files

        # Start with a clean slate
        config_tree = {}
        self._file_mapping.clear()

        try:
            # First, always load the source files as they contain defaults
            for json_file in self._json_files:
                source_path = Path(json_file)

                # Load source configuration
                try:
                    with open(source_path, "r") as f:
                        source_data = json.load(f)

                    # Track where each top-level key originated
                    for key in source_data:
                        self._file_mapping[key] = str(source_path)

                    # Merge source configuration into our tree
                    self._merge_config(config_tree, source_data)

                except FileNotFoundError:
                    print(f"Warning: Source configuration file {source_path} not found")
                    continue

            # In non-development environments, overlay environment-specific configurations
            if self._environment != "development":
                for json_file in self._json_files:
                    env_file = self._env_path / Path(json_file).name

                    if env_file.exists():
                        try:
                            with open(env_file, "r") as f:
                                env_data = json.load(f)

                            # Environment values overlay the defaults
                            self._merge_config(config_tree, env_data)

                        except json.JSONDecodeError:
                            print(
                                f"Warning: Invalid JSON in environment config {env_file}"
                            )
                            continue

            # Initialize our configuration tree with the loaded data
            super().__init__(
                config_tree,
                source_file=None,  # No single source file for the root node
                environment=self._environment,
            )

            # Maintain backward compatibility
            self._add_legacy_attributes(config_tree)

            # Store original state for change detection
            self._original_config = copy.deepcopy(config_tree)

        except Exception as e:
            # Provide detailed error information for troubleshooting
            raise RuntimeError(
                f"Failed to reload configuration. Environment: {self._environment}, "
                f"Error: {str(e)}"
            ) from e

    def _get_env_specific_path(self) -> Path:
        """Get the environment-specific configuration path based on the operating system."""
        system = platform.system().lower()
        logger.info("Determining environment path for system", system=system)

        if system == "windows":
            base_path = Path(os.getenv("APPDATA"))
            logger.info("Using Windows APPDATA path", appdata=str(base_path))
        elif system == "darwin":
            base_path = Path.home() / "Library" / "Application Support"
            logger.info("Using macOS Application Support path", path=str(base_path))
        else:
            base_path = Path.home() / ".config"
            logger.info("Using Linux config path", path=str(base_path))

        final_path = base_path / "neoworldbuilder" / "config"
        logger.info("Final environment config path", path=str(final_path))
        return final_path
