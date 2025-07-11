from typing import Any, Dict, List, Tuple

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QColorDialog,
    QComboBox,
    QCompleter,
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)
from structlog import get_logger

from ui.components.map_component.line_geometry import BranchingLineGeometry
from utils.geometry_handler import GeometryHandler

logger = get_logger(__name__)


class BranchingLineFeatureDialog(QDialog):
    """Dialog for configuring a branching line feature.

    Allows selection of target node and line style.
    """

    def __init__(
        self, branches: List[List[Tuple[int, int]]], parent=None, controller=None
    ):
        """Initialize the dialog.

        Args:
            branches: List of branches, each branch is a list of points
            parent: Parent widget
            controller: WorldBuildingController
        """
        super().__init__(parent)
        self.branches = branches
        self.controller = controller
        self.target_node = None
        self.line_style = {
            "color": "#0000FF",  # Default blue
            "width": 2,
            "pattern": "solid",
        }

        # Create branching geometry to get stable IDs
        self.branching_geometry = BranchingLineGeometry(branches)
        self.branch_assignments = {}  # Maps stable ID to node ID

        # Log branch structure
        logger.debug(
            f"BranchingLineFeatureDialog created with {len(branches)} branches"
        )
        for i, branch in enumerate(branches):
            logger.debug(f"  Branch {i}: {len(branch)} points")

        self.setup_ui()

    def setup_ui(self):
        """Set up dialog UI elements."""
        self.setWindowTitle("Branching Line Feature")
        self.resize(400, 300)

        layout = QVBoxLayout(self)

        # Branch assignment section
        branch_group = QGroupBox("Branch Assignments")
        branch_layout = QFormLayout(branch_group)

        self.branch_inputs = {}  # Maps stable ID to QLineEdit

        # Create input fields for each branch
        for stable_id in self.branching_geometry.stable_branch_ids:
            display_name = self.branching_geometry.get_branch_display_name(stable_id)

            branch_input = QLineEdit()
            branch_input.setPlaceholderText(f"Enter node name for {display_name}...")

            # Set up autocomplete for each input
            if self.controller and hasattr(self.controller, "auto_completion_service"):
                self.setup_completer_for_input(branch_input)

            self.branch_inputs[stable_id] = branch_input
            branch_layout.addRow(f"{display_name}:", branch_input)

        layout.addWidget(branch_group)

        # Legacy single target selection (for backward compatibility)
        target_layout = QHBoxLayout()
        target_layout.addWidget(QLabel("Primary Target:"))

        self.target_input = QLineEdit()
        self.target_input.setPlaceholderText("Enter primary node name...")

        # Set up node name autocomplete
        if self.controller and hasattr(self.controller, "auto_completion_service"):
            self.setup_completer_for_input(self.target_input)

        target_layout.addWidget(self.target_input)
        layout.addLayout(target_layout)

        # Style section
        style_section = QVBoxLayout()
        layout.addLayout(style_section)

        # Line color
        color_layout = QHBoxLayout()
        color_layout.addWidget(QLabel("Color:"))

        self.color_btn = QPushButton()
        self.color_btn.setFixedWidth(80)
        self.update_color_button()
        self.color_btn.clicked.connect(self.choose_color)

        color_layout.addWidget(self.color_btn)
        color_layout.addStretch()
        style_section.addLayout(color_layout)

        # Line width
        width_layout = QHBoxLayout()
        width_layout.addWidget(QLabel("Width:"))

        self.width_spinner = QSpinBox()
        self.width_spinner.setRange(1, 10)
        self.width_spinner.setValue(self.line_style["width"])

        width_layout.addWidget(self.width_spinner)
        width_layout.addStretch()
        style_section.addLayout(width_layout)

        # Line pattern
        pattern_layout = QHBoxLayout()
        pattern_layout.addWidget(QLabel("Pattern:"))

        self.pattern_combo = QComboBox()
        self.pattern_combo.addItems(["solid", "dash", "dot", "dashdot"])
        self.pattern_combo.setCurrentText(self.line_style["pattern"])

        pattern_layout.addWidget(self.pattern_combo)
        pattern_layout.addStretch()
        style_section.addLayout(pattern_layout)

        # Statistics about the branching line
        branch_info_layout = QVBoxLayout()
        layout.addLayout(branch_info_layout)

        branch_count_label = QLabel(f"Branches: {len(self.branches)}")
        branch_info_layout.addWidget(branch_count_label)

        total_points = sum(len(branch) for branch in self.branches)
        points_label = QLabel(f"Total Points: {total_points}")
        branch_info_layout.addWidget(points_label)

        # For each branch, display starting and ending points using stable IDs
        for i, branch in enumerate(self.branches):
            if len(branch) >= 2:
                stable_id = self.branching_geometry.get_stable_id_from_branch_index(i)
                display_name = (
                    self.branching_geometry.get_branch_display_name(stable_id)
                    if stable_id
                    else f"Branch {i+1}"
                )
                branch_info = QLabel(
                    f"{display_name}: {len(branch)} points, from ({branch[0][0]}, {branch[0][1]}) to ({branch[-1][0]}, {branch[-1][1]})"
                )
                branch_info_layout.addWidget(branch_info)

        # Generate WKT preview (truncated)
        wkt = GeometryHandler.create_multi_line(self.branches)
        if len(wkt) > 50:
            wkt_preview = wkt[:47] + "..."
        else:
            wkt_preview = wkt
        wkt_label = QLabel(f"Geometry: {wkt_preview}")
        branch_info_layout.addWidget(wkt_label)

        # Bottom buttons
        button_layout = QHBoxLayout()
        layout.addLayout(button_layout)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)

        self.ok_btn = QPushButton("Create Branching Line")
        self.ok_btn.clicked.connect(self.accept_dialog)
        self.ok_btn.setDefault(True)

        button_layout.addWidget(self.cancel_btn)
        button_layout.addWidget(self.ok_btn)

    def update_color_button(self):
        """Update color button style to show selected color."""
        color = QColor(self.line_style["color"])
        style = f"background-color: {color.name()}; color: {'black' if color.lightness() > 128 else 'white'};"
        self.color_btn.setStyleSheet(style)
        self.color_btn.setText(color.name())

    def choose_color(self):
        """Open color picker dialog."""
        color = QColorDialog.getColor(QColor(self.line_style["color"]), self)
        if color.isValid():
            self.line_style["color"] = color.name()
            self.update_color_button()

    def accept_dialog(self):
        """Handle dialog acceptance with validation."""
        # Validate primary target node
        target_text = self.target_input.text().strip()
        if not target_text:
            return  # TODO: Show validation message

        # Collect branch assignments
        self.branch_assignments = {}
        for stable_id, input_widget in self.branch_inputs.items():
            node_name = input_widget.text().strip()
            if node_name:
                self.branch_assignments[stable_id] = node_name

        # Update line style from UI
        self.line_style["width"] = self.width_spinner.value()
        self.line_style["pattern"] = self.pattern_combo.currentText()

        # Set values and accept
        self.target_node = target_text
        self.accept()

    def get_target_node(self) -> str:
        """Get the selected target node."""
        return self.target_node

    def get_line_style(self) -> Dict[str, Any]:
        """Get the configured line style."""
        return self.line_style.copy()

    def get_geometry_wkt(self) -> str:
        """Get the WKT representation of the branching line."""
        return GeometryHandler.create_multi_line(self.branches)

    def get_branch_assignments(self) -> Dict[str, str]:
        """Get the branch assignments (stable ID -> node ID)."""
        return self.branch_assignments.copy()

    def setup_completer(self):
        """Set up auto-completion for target node input."""
        self.setup_completer_for_input(self.target_input)

    def setup_completer_for_input(self, input_widget: QLineEdit):
        """Set up auto-completion for a specific input widget."""
        from PyQt6.QtCore import QStringListModel

        if self.controller.name_cache_service:
            # Get available names from the cache service
            cached_names = list(self.controller.name_cache_service._name_cache)

            if cached_names:
                model = QStringListModel(cached_names)
                completer = QCompleter(model, self)
                completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
                completer.setFilterMode(Qt.MatchFlag.MatchContains)
                input_widget.setCompleter(completer)
