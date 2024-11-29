import json
import logging
from pathlib import Path
from typing import Dict, Optional, Union

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QWidget, QMessageBox

from models.styleconfig_model import StyleConfig


class StyleRegistry(QObject):
    """Enhanced registry for managing application styles."""

    style_changed = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

    def __init__(self, config_dir: Union[str, Path]) -> None:
        super().__init__()
        self.config_dir = Path(config_dir)
        self.styles: Dict[str, StyleConfig] = {}
        self._cached_stylesheets: Dict[str, str] = {}
        self._load_styles()

    def _load_styles(self) -> None:
        """Load all style configurations from the config directory."""
        try:
            style_config_path = self.config_dir / "styles.json"
            if not style_config_path.exists():
                raise FileNotFoundError(
                    f"Style configuration not found at {style_config_path}"
                )

            with style_config_path.open() as f:
                style_data = json.load(f)
                print(f"Loaded style data: {style_data}")

            for style_name, style_info in style_data.items():
                style_path = self.config_dir / style_info["file"]
                if not style_path.exists():
                    logging.warning(f"Style file not found: {style_path}")
                    continue

                with style_path.open() as f:
                    content = f.read()
                    print(
                        f"Style content for {style_name} (first 100 chars): {content[:100]}"
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

                # Build complete stylesheet with parent styles
                stylesheet = ""
                if style_config.parent:
                    parent_style = self.styles.get(style_config.parent)
                    if parent_style:
                        stylesheet += self._load_stylesheet(parent_style)

                # Add this style's rules
                stylesheet += self._load_stylesheet(style_config)

                # Process variables
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

        # Collect variables from parent styles
        current_style = style_config
        while current_style:
            variables.update(current_style.variables)
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
