import json
import logging
from pathlib import Path
from typing import Dict, Optional, Union

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QWidget, QMessageBox

from models.styleconfig_model import StyleConfig


class StyleRegistry(QObject):
    """Central registry for managing application styles."""

    style_changed = pyqtSignal(str)  # Emitted when style changes

    def __init__(self, config_dir: Union[str, Path]) -> None:
        """Initialize the style registry.

        Args:
            config_dir: Directory containing style configurations
        """
        super().__init__()
        self.config_dir = Path(config_dir)
        self.styles: Dict[str, StyleConfig] = {}
        self.current_style: Optional[str] = None
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

            for style_name, style_info in style_data.items():
                style_path = self.config_dir / style_info["file"]
                if not style_path.exists():
                    logging.warning(f"Style file not found: {style_path}")
                    continue

                self.styles[style_name] = StyleConfig(
                    name=style_name,
                    path=style_path,
                    variables=style_info.get("variables", {}),
                    description=style_info.get("description", ""),
                    parent=style_info.get("parent"),
                )

        except Exception as e:
            logging.error(f"Failed to load styles: {e}")
            raise

    def apply_style(self, widget: QWidget, style_name: str) -> None:
        """Apply a named style to a widget.

        Args:
            widget: Widget to style
            style_name: Name of the style to apply

        Raises:
            ValueError: If style_name is not found
        """
        if style_name not in self.styles:
            raise ValueError(f"Style not found: {style_name}")

        try:
            style_config = self.styles[style_name]

            # Load parent style if it exists
            stylesheet = ""
            if style_config.parent:
                parent_style = self.styles.get(style_config.parent)
                if parent_style:
                    stylesheet += self._load_stylesheet(parent_style)

            # Add this style's rules
            stylesheet += self._load_stylesheet(style_config)

            # Apply variables
            stylesheet = self._apply_variables(stylesheet, style_config.variables)

            widget.setStyleSheet(stylesheet)
            self.current_style = style_name
            self.style_changed.emit(style_name)

        except Exception as e:
            logging.error(f"Failed to apply style {style_name}: {e}")
            QMessageBox.warning(
                widget, "Style Error", f"Failed to apply style: {str(e)}"
            )

    def _load_stylesheet(self, style_config: StyleConfig) -> str:
        """Load stylesheet content from a style configuration.

        Args:
            style_config: Style configuration to load

        Returns:
            The stylesheet content
        """
        try:
            with style_config.path.open() as f:
                return f.read()
        except Exception as e:
            logging.error(f"Failed to load stylesheet {style_config.path}: {e}")
            raise

    def _apply_variables(self, stylesheet: str, variables: Dict[str, str]) -> str:
        """Apply variable substitutions to a stylesheet.

        Args:
            stylesheet: The stylesheet content
            variables: Dictionary of variable names and values

        Returns:
            The processed stylesheet with variables replaced
        """
        for var_name, var_value in variables.items():
            stylesheet = stylesheet.replace(f"${var_name}", var_value)
        return stylesheet

    def switch_theme(self, theme_name: str) -> None:
        """Switch between light and dark themes.

        Args:
            theme_name: Name of the theme to switch to
        """
        if theme_name not in self.styles:
            raise ValueError(f"Theme not found: {theme_name}")

        self.apply_style(self, theme_name)
        self.current_style = theme_name
        self.style_changed.emit(theme_name)
