"""
Polygon feature dialog for setting polygon properties and target node.
"""

from typing import Dict, Optional, Tuple

from PyQt6.QtCore import Qt, QStringListModel
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QComboBox,
    QSlider,
    QPushButton,
    QDialogButtonBox,
    QColorDialog,
    QFrame,
    QGroupBox,
    QSpinBox,
    QCompleter,
)
from PyQt6.QtGui import QColor

from ..utils.map_logger import get_map_logger

logger = get_map_logger(__name__)


class PolygonFeatureDialog(QDialog):
    """Dialog for configuring polygon feature properties."""
    
    def __init__(self, controller=None, existing_names=None, parent=None):
        """
        Initialize the polygon feature dialog.
        
        Args:
            controller: Application controller for node operations
            existing_names: List of existing node names for autocomplete
            parent: Parent widget
        """
        super().__init__(parent)
        self.controller = controller
        self.existing_names = existing_names or []
        
        # Dialog settings
        self.setWindowTitle("Polygon Feature Properties")
        self.setModal(True)
        self.setMinimumSize(400, 500)
        
        # Style properties
        self.fill_color = QColor("#4a90e2")
        self.fill_opacity = 0.3
        self.outline_color = QColor("#2c5aa0")
        self.outline_width = 2.0
        self.outline_pattern = "solid"
        
        self._setup_ui()
        self._setup_completer()
        
        logger.debug("Polygon feature dialog initialized")
    
    def _setup_ui(self) -> None:
        """Set up the user interface."""
        layout = QVBoxLayout(self)
        
        # Node name section
        name_group = QGroupBox("Target Node")
        name_layout = QVBoxLayout(name_group)
        
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Enter node name to link this polygon to...")
        name_layout.addWidget(QLabel("Node Name:"))
        name_layout.addWidget(self.name_input)
        
        layout.addWidget(name_group)
        
        # Fill properties section
        fill_group = QGroupBox("Fill Properties")
        fill_layout = QVBoxLayout(fill_group)
        
        # Fill color
        fill_color_layout = QHBoxLayout()
        fill_color_layout.addWidget(QLabel("Fill Color:"))
        self.fill_color_btn = QPushButton()
        self.fill_color_btn.setFixedSize(50, 30)
        self.fill_color_btn.clicked.connect(self._choose_fill_color)
        self._update_fill_color_button()
        fill_color_layout.addWidget(self.fill_color_btn)
        fill_color_layout.addStretch()
        fill_layout.addLayout(fill_color_layout)
        
        # Fill opacity
        opacity_layout = QHBoxLayout()
        opacity_layout.addWidget(QLabel("Fill Opacity:"))
        self.opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.opacity_slider.setMinimum(0)
        self.opacity_slider.setMaximum(100)
        self.opacity_slider.setValue(int(self.fill_opacity * 100))
        self.opacity_slider.valueChanged.connect(self._update_opacity_label)
        self.opacity_label = QLabel(f"{int(self.fill_opacity * 100)}%")
        self.opacity_label.setMinimumWidth(40)
        opacity_layout.addWidget(self.opacity_slider)
        opacity_layout.addWidget(self.opacity_label)
        fill_layout.addLayout(opacity_layout)
        
        layout.addWidget(fill_group)
        
        # Outline properties section
        outline_group = QGroupBox("Outline Properties")
        outline_layout = QVBoxLayout(outline_group)
        
        # Outline color
        outline_color_layout = QHBoxLayout()
        outline_color_layout.addWidget(QLabel("Outline Color:"))
        self.outline_color_btn = QPushButton()
        self.outline_color_btn.setFixedSize(50, 30)
        self.outline_color_btn.clicked.connect(self._choose_outline_color)
        self._update_outline_color_button()
        outline_color_layout.addWidget(self.outline_color_btn)
        outline_color_layout.addStretch()
        outline_layout.addLayout(outline_color_layout)
        
        # Outline width
        width_layout = QHBoxLayout()
        width_layout.addWidget(QLabel("Outline Width:"))
        self.width_spinner = QSpinBox()
        self.width_spinner.setMinimum(1)
        self.width_spinner.setMaximum(20)
        self.width_spinner.setValue(int(self.outline_width))
        self.width_spinner.setSuffix(" px")
        width_layout.addWidget(self.width_spinner)
        width_layout.addStretch()
        outline_layout.addLayout(width_layout)
        
        # Outline pattern
        pattern_layout = QHBoxLayout()
        pattern_layout.addWidget(QLabel("Outline Pattern:"))
        self.pattern_combo = QComboBox()
        self.pattern_combo.addItems(["solid", "dashed", "dotted", "dashdot"])
        self.pattern_combo.setCurrentText(self.outline_pattern)
        pattern_layout.addWidget(self.pattern_combo)
        pattern_layout.addStretch()
        outline_layout.addLayout(pattern_layout)
        
        layout.addWidget(outline_group)
        
        # Buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
        
        # Focus on name input
        self.name_input.setFocus()
    
    def _setup_completer(self) -> None:
        """Set up autocompletion for the name input."""
        from PyQt6.QtCore import QStringListModel
        from PyQt6.QtWidgets import QCompleter
        
        # Use the same pattern as line_feature_dialog
        if self.controller and hasattr(self.controller, 'name_cache_service') and self.controller.name_cache_service:
            # Get available names from the cache service
            cached_names = list(self.controller.name_cache_service.get_cached_names())
            
            if cached_names:
                model = QStringListModel(cached_names)
                completer = QCompleter(model, self)
                completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
                completer.setFilterMode(Qt.MatchFlag.MatchContains)
                self.name_input.setCompleter(completer)
                logger.debug("Set up autocompletion using name cache service")
            else:
                logger.debug("No cached names available for autocompletion")
        elif self.existing_names:
            # Fallback: create simple completer from existing names
            model = QStringListModel(self.existing_names)
            completer = QCompleter(model, self)
            completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
            completer.setFilterMode(Qt.MatchFlag.MatchContains)
            self.name_input.setCompleter(completer)
            logger.debug(f"Set up fallback completer with {len(self.existing_names)} names")
        else:
            logger.debug("No names available for autocompletion")
    
    def _choose_fill_color(self) -> None:
        """Open color dialog for fill color selection."""
        color = QColorDialog.getColor(
            self.fill_color,
            self,
            "Choose Fill Color"
        )
        if color.isValid():
            self.fill_color = color
            self._update_fill_color_button()
            logger.debug(f"Fill color changed to {color.name()}")
    
    def _choose_outline_color(self) -> None:
        """Open color dialog for outline color selection."""
        color = QColorDialog.getColor(
            self.outline_color,
            self,
            "Choose Outline Color"
        )
        if color.isValid():
            self.outline_color = color
            self._update_outline_color_button()
            logger.debug(f"Outline color changed to {color.name()}")
    
    def _update_fill_color_button(self) -> None:
        """Update the fill color button appearance."""
        self.fill_color_btn.setStyleSheet(
            f"background-color: {self.fill_color.name()}; border: 1px solid #ccc;"
        )
    
    def _update_outline_color_button(self) -> None:
        """Update the outline color button appearance."""
        self.outline_color_btn.setStyleSheet(
            f"background-color: {self.outline_color.name()}; border: 1px solid #ccc;"
        )
    
    def _update_opacity_label(self, value: int) -> None:
        """Update the opacity label."""
        self.opacity_label.setText(f"{value}%")
        self.fill_opacity = value / 100.0
    
    def get_node_name(self) -> str:
        """Get the target node name."""
        return self.name_input.text().strip()
    
    def get_style_properties(self) -> Dict:
        """Get the polygon style properties."""
        return {
            'fill_color': self.fill_color.name(),
            'fill_opacity': self.fill_opacity,
            'outline_color': self.outline_color.name(),
            'outline_width': float(self.width_spinner.value()),
            'outline_pattern': self.pattern_combo.currentText()
        }
    
    def set_default_node_name(self, name: str) -> None:
        """Set a default node name in the input field."""
        self.name_input.setText(name)
        logger.debug(f"Set default node name: {name}")
    
    def validate_input(self) -> Tuple[bool, str]:
        """Validate the dialog input.
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        node_name = self.get_node_name()
        
        if not node_name:
            return False, "Node name is required"
        
        # Additional validation could be added here
        # For example, checking if node name contains invalid characters
        
        return True, ""
    
    def accept(self) -> None:
        """Override accept to validate input first."""
        is_valid, error_message = self.validate_input()
        
        if not is_valid:
            # Could show a message box here, but for now just prevent closing
            logger.warning(f"Invalid input: {error_message}")
            return
        
        logger.debug(
            "Polygon dialog accepted",
            node_name=self.get_node_name(),
            style=self.get_style_properties()
        )
        super().accept()