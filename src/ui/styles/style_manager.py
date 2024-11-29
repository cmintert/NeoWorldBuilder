from pathlib import Path
from typing import Dict, Union, Optional

from PyQt6.QtWidgets import QWidget, QApplication

from .style_registry import StyleRegistry


class StyleManager:
    """Manages application styling using StyleRegistry."""

    def __init__(self, config_dir: Union[str, Path]) -> None:
        self.registry = StyleRegistry(config_dir)
        self._app_style: Optional[str] = None
        self._widget_styles: Dict[int, str] = {}

        # Connect to registry signals
        self.registry.style_changed.connect(self._on_style_changed)

    def apply_style(
        self, target: Union[QApplication, QWidget], style_name: str
    ) -> None:
        """Apply style to target, handling both app-level and widget-specific styling."""
        try:
            if isinstance(target, QApplication):
                self._app_style = style_name
                # Apply to app first, then all tracked widgets to maintain hierarchy
                self.registry.apply_style(target, style_name)
                self._reapply_widget_styles()
            else:
                self._widget_styles[id(target)] = style_name
                self.registry.apply_style(target, style_name)
                # Connect to widget destruction
                target.destroyed.connect(lambda: self._cleanup_widget(id(target)))
        except Exception as e:
            self.registry.error_occurred.emit(f"Style application failed: {str(e)}")

    def _reapply_widget_styles(self) -> None:
        """Reapply styles to all tracked widgets."""
        for widget_id, style_name in self._widget_styles.items():
            if widget := QWidget.find(widget_id):
                self.registry.apply_style(widget, style_name)

    def _cleanup_widget(self, widget_id: int) -> None:
        """Remove widget from tracking when destroyed."""
        self._widget_styles.pop(widget_id, None)

    def _on_style_changed(self, style_name: str) -> None:
        """Handle style change notifications."""
        # Additional style change handling if needed
        pass

    def get_available_styles(self) -> Dict[str, str]:
        """Get available styles and descriptions."""
        return {name: style.description for name, style in self.registry.styles.items()}

    def get_current_style(self, widget: Optional[QWidget] = None) -> Optional[str]:
        """Get current style for widget or application."""
        if widget:
            return self._widget_styles.get(id(widget))
        return self._app_style
