from typing import List, Tuple, Dict, Any

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QGroupBox,
    QComboBox,
    QSpinBox,
    QDialogButtonBox,
    QCompleter,
    QDialog,
    QMessageBox,
)


class LineFeatureDialog(QDialog):
    """Dialog for setting line feature properties."""

    def __init__(self, points: List[Tuple[int, int]], parent=None, controller=None):
        """Initialize the line feature dialog."""
        super().__init__(parent)
        self.setWindowTitle("Line Feature Properties")
        self.points = points
        self.controller = controller

        # Create layout
        layout = QVBoxLayout(self)

        # Node name entry
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("Line Name:"))
        self.node_name_input = QLineEdit()

        # Only set up completer if we have a controller
        if self.controller and hasattr(self.controller, "auto_completion_service"):
            # Use controller's existing autocomplete methods instead
            self.setup_completer()

        name_layout.addWidget(self.node_name_input)
        layout.addLayout(name_layout)

        # Line style options
        style_group = QGroupBox("Line Style")
        style_layout = QVBoxLayout(style_group)

        # Color selection
        color_layout = QHBoxLayout()
        color_layout.addWidget(QLabel("Color:"))
        self.color_combo = QComboBox()
        self.setup_color_options()
        color_layout.addWidget(self.color_combo)
        style_layout.addLayout(color_layout)

        # Line width
        width_layout = QHBoxLayout()
        width_layout.addWidget(QLabel("Width:"))
        self.width_spin = QSpinBox()
        self.width_spin.setMinimum(1)
        self.width_spin.setMaximum(10)
        self.width_spin.setValue(2)
        width_layout.addWidget(self.width_spin)
        style_layout.addLayout(width_layout)

        # Line pattern
        pattern_layout = QHBoxLayout()
        pattern_layout.addWidget(QLabel("Pattern:"))
        self.pattern_combo = QComboBox()
        self.setup_pattern_options()
        pattern_layout.addWidget(self.pattern_combo)
        style_layout.addLayout(pattern_layout)

        layout.addWidget(style_group)

        # Line info
        info_label = QLabel(
            f"Line with {len(points)} points from ({points[0][0]}, {points[0][1]}) to ({points[-1][0]}, {points[-1][1]})"
        )
        layout.addWidget(info_label)

        # Dialog buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        # Set dialog size
        self.setMinimumWidth(350)

    def setup_completer(self):
        """Set up auto-completion for node name input."""
        # Build a model from all cached node names
        # The controller uses StringListModel or something similar
        from PyQt6.QtCore import QStringListModel

        if self.controller.name_cache_service:
            # Get available names from the cache service
            # This is a different approach that doesn't rely on a specific method
            cached_names = list(self.controller.name_cache_service._name_cache)

            if cached_names:
                model = QStringListModel(cached_names)
                completer = QCompleter(model, self)
                completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
                completer.setFilterMode(Qt.MatchFlag.MatchContains)
                self.node_name_input.setCompleter(completer)

    def setup_color_options(self):
        """Set up line color options."""
        colors = [
            ("Red", "#FF0000"),
            ("Blue", "#0000FF"),
            ("Green", "#00FF00"),
            ("Yellow", "#FFFF00"),
            ("Black", "#000000"),
            ("White", "#FFFFFF"),
            ("Orange", "#FFA500"),
            ("Purple", "#800080"),
        ]

        for name, code in colors:
            self.color_combo.addItem(name, code)

    def setup_pattern_options(self):
        """Set up line pattern options."""
        patterns = ["Solid", "Dash", "Dot", "DashDot"]
        for pattern in patterns:
            self.pattern_combo.addItem(pattern, pattern.lower())

    def accept(self) -> None:
        """Override accept to validate input."""
        if not self.node_name_input.text().strip():
            QMessageBox.warning(self, "Empty Name", "Please enter a valid node name.")
            return

        super().accept()

    def get_target_node(self) -> str:
        """Get the target node name."""
        return self.node_name_input.text().strip()

    def get_line_style(self) -> Dict[str, Any]:
        """Get the selected line style properties."""
        return {
            "color": self.color_combo.currentData(),
            "width": self.width_spin.value(),
            "pattern": self.pattern_combo.currentData(),
        }
