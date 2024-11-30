from pathlib import Path
from typing import Dict, Union

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QWidget, QApplication

from .style_registry import StyleRegistry


class StyleManager:
    """Manages application styling using StyleRegistry."""

    def __init__(self, config_dir: Union[str, Path]) -> None:
        print(f"Initializing StyleManager with config dir: {config_dir}")
        self.registry = StyleRegistry(config_dir)
        self._current_style: str = "default"
        self._widget_styles: Dict[int, str] = {}

    @property
    def current_style(
        self,
    ) -> str:  # Renamed from app_style to current_style for clarity
        """Get the current application style."""
        print(f"Getting current style: {self._current_style}")  # Debug logging
        return self._current_style

    def apply_style(
        self, target: Union[QApplication, QWidget], style_name: str
    ) -> None:
        """Apply style to target, with enhanced debugging."""
        try:
            print(f"Applying style '{style_name}' to {target.__class__.__name__}")

            if isinstance(target, QApplication):
                print(f"Applying application-wide style: {style_name}")
                self._current_style = style_name  # Store style name when applying
                print(
                    f"Updated current_style to: {self._current_style}"
                )  # Debug logging
                stylesheet = self.registry.get_style_content(style_name)
                if stylesheet:
                    target.setStyleSheet(stylesheet)
                self._reapply_widget_styles()
            else:
                # Widget-specific styling logic remains the same
                target.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
                stylesheet = self.registry.get_style_content(style_name)
                if stylesheet:
                    target.setStyleSheet(stylesheet)
                self._widget_styles[id(target)] = style_name
                target.destroyed.connect(lambda: self._cleanup_widget(id(target)))

            print(f"Style '{style_name}' applied successfully")

        except Exception as e:
            print(f"Error applying style: {str(e)}")
            self.registry.error_occurred.emit(f"Style application failed: {str(e)}")

    def get_style(self) -> str:
        """Get the current style with debug information."""
        print(f"StyleManager.get_style called, returning: {self._current_style}")
        return self._current_style

    def _scope_stylesheet(self, widget: QWidget, stylesheet: str) -> str:
        """Scope stylesheet to specific widget to prevent style leakage."""
        widget_class = widget.metaObject().className()
        widget_name = widget.objectName()

        # Create widget selector
        selector = f"#{widget_name}" if widget_name else f"{widget_class}"

        # Split stylesheet into rules
        rules = [rule.strip() for rule in stylesheet.split("}") if rule.strip()]

        # Process each rule
        scoped_rules = []
        for rule in rules:
            if "{" in rule:
                selectors, properties = rule.split("{", 1)
                # Handle multiple selectors
                sub_selectors = [s.strip() for s in selectors.split(",")]
                scoped_selectors = [
                    (
                        f"{selector} {sub_selector}"
                        if not sub_selector.startswith("#")
                        else sub_selector
                    )
                    for sub_selector in sub_selectors
                ]
                scoped_rules.append(f"{', '.join(scoped_selectors)} {{{properties}}}")
            else:
                scoped_rules.append(rule)

        return "}".join(scoped_rules)

    def _reapply_widget_styles(self) -> None:
        """Reapply styles to all tracked widgets."""
        for widget_id, style_name in self._widget_styles.items():
            if widget := QWidget.find(widget_id):
                print(
                    f"Reapplying style '{style_name}' to widget {widget.objectName()}"
                )
                self.apply_style(widget, style_name)

    def _cleanup_widget(self, widget_id: int) -> None:
        """Remove widget from tracking when destroyed."""
        print(f"Cleaning up widget {widget_id}")
        self._widget_styles.pop(widget_id, None)
