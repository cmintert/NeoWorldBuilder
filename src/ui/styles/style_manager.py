from pathlib import Path
from typing import Dict, Union, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QWidget, QApplication

from .style_registry import StyleRegistry


class StyleManager:
    """Manages application styling using StyleRegistry."""

    def __init__(self, config_dir: Union[str, Path]) -> None:
        print(f"Initializing StyleManager with config dir: {config_dir}")
        self.registry = StyleRegistry(config_dir)
        self._app_style: Optional[str] = None
        self._widget_styles: Dict[int, str] = {}

    def apply_style(
        self, target: Union[QApplication, QWidget], style_name: str
    ) -> None:
        """Apply style to target, with enhanced debugging."""
        try:
            print(f"Applying style '{style_name}' to {target.__class__.__name__}")

            if isinstance(target, QApplication):
                print("Applying application-wide style")
                self._app_style = style_name
                stylesheet = self.registry.get_style_content(style_name)
                if stylesheet:
                    print(
                        f"Application stylesheet (first 100 chars): {stylesheet[:100]}"
                    )
                    target.setStyleSheet(stylesheet)
                self._reapply_widget_styles()
            else:
                print(
                    f"Applying widget-specific style to {target.objectName() or 'unnamed widget'}"
                )
                # Force widget to use stylesheet
                target.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

                # Get and apply the stylesheet
                stylesheet = self.registry.get_style_content(style_name)
                if stylesheet:
                    print(f"Widget stylesheet (first 100 chars): {stylesheet[:100]}")
                    target.setStyleSheet(stylesheet)
                    print(f"Style applied to widget {target.objectName()}")
                else:
                    print(f"No stylesheet content found for style '{style_name}'")

                # Store the style
                self._widget_styles[id(target)] = style_name

                # Connect to widget destruction
                target.destroyed.connect(lambda: self._cleanup_widget(id(target)))

            print(f"Style '{style_name}' applied successfully")

        except Exception as e:
            print(f"Error applying style: {str(e)}")
            self.registry.error_occurred.emit(f"Style application failed: {str(e)}")

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
