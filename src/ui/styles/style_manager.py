from pathlib import Path
from typing import Dict, Union

from PyQt6.QtWidgets import QWidget

from .style_registry import StyleRegistry


class StyleManager:
    """High-level interface for style management."""

    def __init__(self, config_dir: Union[str, Path]) -> None:
        """Initialize the style manager.

        Args:
            config_dir: Directory containing style configurations
        """
        self.registry = StyleRegistry(config_dir)
        self._widget_styles: Dict[int, str] = {}  # Track widget styles by id

    def apply_style(self, widget: QWidget, style_name: str) -> None:
        """Apply a style to a widget and track the association.

        Args:
            widget: Widget to style
            style_name: Name of the style to apply
        """
        self.registry.apply_style(widget, style_name)
        self._widget_styles[id(widget)] = style_name

    def reapply_current_styles(self) -> None:
        """Reapply current styles to all tracked widgets."""
        for widget_id, style_name in self._widget_styles.items():
            widget = QWidget.find(widget_id)
            if widget:
                self.registry.apply_style(widget, style_name)

    def get_available_styles(self) -> Dict[str, str]:
        """Get available styles and their descriptions.

        Returns:
            Dictionary of style names and descriptions
        """
        return {name: style.description for name, style in self.registry.styles.items()}

    def switch_theme(self, theme_name: str) -> None:
        """Switch between light and dark themes.

        Args:
            theme_name: Name of the theme to switch to
        """
        self.registry.apply_style(self, theme_name)
        self.reapply_current_styles()
