import json
import logging
from pathlib import Path
from typing import Dict, Optional, Union

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QWidget, QMessageBox

from models.styleconfig_model import StyleConfig
from utils.path_helper import get_resource_path


class StyleRegistry(QObject):
    """Enhanced registry for managing application styles."""

    style_changed = pyqtSignal(str)
    styles_reloaded = pyqtSignal()
    error_occurred = pyqtSignal(str)

    def __init__(self, config_dir: Union[str, Path]) -> None:
        super().__init__()
        # Convert the config_dir to use get_resource_path
        self.config_dir = Path(get_resource_path(str(config_dir)))
        print(f"StyleRegistry initialized with config_dir: {self.config_dir}")
        self.styles: Dict[str, StyleConfig] = {}
        self._cached_stylesheets: Dict[str, str] = {}
        self._load_styles()

    def _load_styles(self) -> None:
        """Load all style configurations from the config directory."""
        try:
            style_config_path = self.config_dir / "styles.json"
            print(f"Looking for styles.json at: {style_config_path}")

            if not style_config_path.exists():
                raise FileNotFoundError(
                    f"Style configuration not found at {style_config_path}"
                )

            with style_config_path.open() as f:
                style_data = json.load(f)
                print(f"Loaded style data: {style_data}")

            for style_name, style_info in style_data.items():
                style_path = self.config_dir / style_info["file"]
                print(f"Processing style {style_name} from {style_path}")

                if not style_path.exists():
                    print(f"Warning: Style file not found: {style_path}")
                    logging.warning(f"Style file not found: {style_path}")
                    continue

                with style_path.open() as f:
                    content = f.read()
                    print(
                        f"Loaded style content for {style_name} (length: {len(content)})"
                    )

                self.styles[style_name] = StyleConfig(
                    name=style_name,
                    path=style_path,
                    variables=style_info.get("variables", {}),
                    description=style_info.get("description", ""),
                    parent=style_info.get("parent"),
                )

        except Exception as e:
            error_msg = f"Failed to load styles: {str(e)}"
            print(f"Error in _load_styles: {error_msg}")
            logging.error(error_msg)
            self.error_occurred.emit(error_msg)
            raise

    def _load_stylesheet(self, style_config: StyleConfig) -> str:
        """Load stylesheet content from a style configuration."""
        try:
            with style_config.path.open() as f:
                return f.read()
        except Exception as e:
            error_msg = f"Failed to load stylesheet {style_config.path}: {str(e)}"
            logging.error(error_msg)
            raise

    def get_style_content(self, style_name: str) -> Optional[str]:
        """Get processed stylesheet content for a style."""
        try:
            if style_name not in self._cached_stylesheets:
                if style_name not in self.styles:
                    raise ValueError(f"Style not found: {style_name}")

                style_config = self.styles[style_name]
                processed_styles = []

                # Process inheritance chain from root to child
                current_style = style_config
                while current_style:
                    processed_styles.insert(0, self._load_stylesheet(current_style))
                    current_style = self.styles.get(current_style.parent)

                # Combine styles
                stylesheet = "\n".join(processed_styles)

                # Process variables after combining all styles
                processed_stylesheet = self._process_variables(stylesheet, style_config)
                self._cached_stylesheets[style_name] = processed_stylesheet

            return self._cached_stylesheets[style_name]

        except Exception as e:
            error_msg = f"Failed to get style content: {str(e)}"
            self.error_occurred.emit(error_msg)
            logging.error(error_msg)
            return None

    def _process_variables(self, stylesheet: str, style_config: StyleConfig) -> str:
        """Process all variables in stylesheet including inherited ones."""
        variables = {}

        # Collect variables from root to child
        current_style = style_config
        while current_style:
            # Child variables override parent variables
            new_vars = current_style.variables.copy()
            new_vars.update(variables)  # Existing (child) vars take precedence
            variables = new_vars

            # Move up the chain
            if current_style.parent:
                current_style = self.styles.get(current_style.parent)
            else:
                current_style = None

        # Apply variables
        processed = stylesheet
        for var_name, var_value in variables.items():
            processed = processed.replace(f"${{{var_name}}}", var_value)
            processed = processed.replace(f"${var_name}", var_value)  # Legacy support

        return processed

    def apply_style(self, widget: QWidget, style_name: str) -> None:
        """Apply a style to a widget with proper variable processing."""
        try:
            if style_name not in self.styles:
                raise ValueError(f"Style not found: {style_name}")

            if stylesheet := self.get_style_content(style_name):
                widget.setStyleSheet(stylesheet)
                self.style_changed.emit(style_name)

        except Exception as e:
            error_msg = f"Failed to apply style {style_name}: {str(e)}"
            self.error_occurred.emit(error_msg)
            logging.error(error_msg)
            QMessageBox.warning(
                widget, "Style Error", f"Failed to apply style: {str(e)}"
            )

    def reload_styles(self) -> None:
        """Force reload all styles from disk."""
        try:
            # Clear the cache
            self._cached_stylesheets.clear()

            # Clear and reload styles
            self.styles.clear()
            self._load_styles()

            # Notify listeners
            self.styles_reloaded.emit()

            logging.info("Styles successfully reloaded")
        except Exception as e:
            error_msg = f"Failed to reload styles: {str(e)}"
            logging.error(error_msg)
            self.error_occurred.emit(error_msg)
            raise
