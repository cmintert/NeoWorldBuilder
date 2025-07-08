from typing import Optional
from PyQt6.QtCore import Qt, QObject
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QVBoxLayout,
    QLabel,
    QSlider,
    QPushButton,
)


class MapToolbarManager(QObject):
    """Manages the toolbar controls for the map component.

    Handles creation and management of image controls, zoom controls,
    and mode toggle buttons.
    """

    def __init__(self, parent_widget, controller=None):
        """Initialize the toolbar manager.

        Args:
            parent_widget: The parent widget (MapTab instance)
            controller: Application controller
        """
        super().__init__()
        self.parent_widget = parent_widget
        self.controller = controller

        # Button references
        self.change_map_btn = None
        self.clear_map_btn = None
        self.pin_toggle_btn = None
        self.line_toggle_btn = None
        self.branching_line_toggle_btn = None
        self.edit_toggle_btn = None
        self.zoom_slider = None
        self.reset_button = None

    def create_image_controls(self) -> QHBoxLayout:
        """Create the image control buttons."""
        image_controls = QHBoxLayout()

        # Change/Clear map buttons
        self.change_map_btn = QPushButton("Change Map Image")
        self.change_map_btn.clicked.connect(self._handle_change_map)

        self.clear_map_btn = QPushButton("Clear Map Image")
        self.clear_map_btn.clicked.connect(self._handle_clear_map)

        # Mode toggle buttons
        self.pin_toggle_btn = QPushButton("📍 Place Pin")
        self.pin_toggle_btn.setCheckable(True)
        self.pin_toggle_btn.toggled.connect(self._handle_pin_toggle)
        self.pin_toggle_btn.setToolTip("Toggle pin placement mode (ESC to cancel)")

        self.line_toggle_btn = QPushButton("📏 Draw Line")
        self.line_toggle_btn.setCheckable(True)
        self.line_toggle_btn.toggled.connect(self._handle_line_toggle)
        self.line_toggle_btn.setToolTip(
            "Toggle line drawing mode (ESC to cancel, Enter to complete)"
        )

        self.branching_line_toggle_btn = QPushButton("🌿 Draw Branching Line")
        self.branching_line_toggle_btn.setCheckable(True)
        self.branching_line_toggle_btn.toggled.connect(
            self._handle_branching_line_toggle
        )
        self.branching_line_toggle_btn.setToolTip(
            "Toggle branching line drawing mode (ESC to cancel, Enter to complete)"
        )

        self.edit_toggle_btn = QPushButton("✏️ Edit Mode")
        self.edit_toggle_btn.setCheckable(True)
        self.edit_toggle_btn.toggled.connect(self._handle_edit_toggle)
        self.edit_toggle_btn.setToolTip("Edit existing lines (click line to edit)")

        image_controls.addWidget(self.change_map_btn)
        image_controls.addWidget(self.clear_map_btn)
        image_controls.addStretch()
        image_controls.addWidget(self.pin_toggle_btn)
        image_controls.addWidget(self.line_toggle_btn)
        image_controls.addWidget(self.branching_line_toggle_btn)
        image_controls.addWidget(self.edit_toggle_btn)
        image_controls.addStretch()

        return image_controls

    def create_zoom_controls(self) -> QHBoxLayout:
        """Create the zoom control widgets."""
        zoom_controls = QHBoxLayout()

        self.zoom_slider = QSlider(Qt.Orientation.Horizontal)
        self.zoom_slider.setMinimum(10)  # 10% zoom
        self.zoom_slider.setMaximum(500)  # 500% zoom for better detail viewing
        self.zoom_slider.setValue(100)  # 100% default
        self.zoom_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.zoom_slider.setTickInterval(50)  # Tick marks every 50%
        self.zoom_slider.setPageStep(25)  # Page up/down changes by 25%
        self.zoom_slider.setSingleStep(5)  # Arrow keys change by 5%
        self.zoom_slider.setFocusPolicy(
            Qt.FocusPolicy.WheelFocus
        )  # Enable wheel events on slider
        self.zoom_slider.valueChanged.connect(self._handle_zoom_change)

        self.reset_button = QPushButton("Reset Zoom")
        self.reset_button.clicked.connect(self._handle_zoom_reset)

        # Add zoom percentage label
        self.zoom_label = QLabel("100%")
        self.zoom_label.setMinimumWidth(45)
        self.zoom_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        zoom_controls.addWidget(QLabel("Zoom:"))
        zoom_controls.addWidget(self.zoom_slider)
        zoom_controls.addWidget(self.zoom_label)
        zoom_controls.addWidget(self.reset_button)

        return zoom_controls

    def update_pin_button_style(self, active: bool) -> None:
        """Update pin button styling based on active state."""
        if self.pin_toggle_btn:
            if active:
                self.pin_toggle_btn.setStyleSheet("background: white")
            else:
                self.pin_toggle_btn.setStyleSheet(
                    ""
                )  # Return to default light grey styling

    def update_line_button_style(self, active: bool) -> None:
        """Update line button styling based on active state."""
        if self.line_toggle_btn:
            if active:
                self.line_toggle_btn.setStyleSheet("background-color: #83A00E;")
            else:
                self.line_toggle_btn.setStyleSheet("")

    def update_branching_line_button_style(self, active: bool) -> None:
        """Update branching line button styling based on active state."""
        if self.branching_line_toggle_btn:
            if active:
                self.branching_line_toggle_btn.setStyleSheet(
                    "background-color: #83A00E;"
                )
            else:
                self.branching_line_toggle_btn.setStyleSheet("")

    def update_edit_button_style(self, active: bool) -> None:
        """Update edit button styling based on active state."""
        if self.edit_toggle_btn:
            if active:
                self.edit_toggle_btn.setStyleSheet("background-color: #FFA500;")
            else:
                self.edit_toggle_btn.setStyleSheet("")

    def set_zoom_value(self, value: int) -> None:
        """Set zoom slider value without triggering signals."""
        if self.zoom_slider:
            self.zoom_slider.blockSignals(True)
            self.zoom_slider.setValue(value)
            self.zoom_slider.blockSignals(False)
            # Update zoom label
            if hasattr(self, "zoom_label"):
                self.zoom_label.setText(f"{value}%")
            # Manually trigger zoom handling since signals are blocked
            if hasattr(self.parent_widget, "_handle_zoom"):
                self.parent_widget._handle_zoom()

    def block_button_signals(self, blocked: bool) -> None:
        """Block/unblock signals from all toggle buttons."""
        buttons = [
            self.pin_toggle_btn,
            self.line_toggle_btn,
            self.branching_line_toggle_btn,
            self.edit_toggle_btn,
        ]
        for button in buttons:
            if button:
                button.blockSignals(blocked)

    def _handle_change_map(self) -> None:
        """Handle change map button click."""
        if hasattr(self.parent_widget, "_change_map_image"):
            self.parent_widget._change_map_image()

    def _handle_clear_map(self) -> None:
        """Handle clear map button click."""
        if hasattr(self.parent_widget, "_clear_map_image"):
            self.parent_widget._clear_map_image()

    def _handle_pin_toggle(self, active: bool) -> None:
        """Handle pin toggle button state change."""
        if hasattr(self.parent_widget, "toggle_pin_placement"):
            self.parent_widget.toggle_pin_placement(active)

    def _handle_line_toggle(self, active: bool) -> None:
        """Handle line toggle button state change."""
        if hasattr(self.parent_widget, "toggle_line_drawing"):
            self.parent_widget.toggle_line_drawing(active)

    def _handle_branching_line_toggle(self, active: bool) -> None:
        """Handle branching line toggle button state change."""
        if hasattr(self.parent_widget, "toggle_branching_line_drawing"):
            self.parent_widget.toggle_branching_line_drawing(active)

    def _handle_edit_toggle(self, active: bool) -> None:
        """Handle edit toggle button state change."""
        if hasattr(self.parent_widget, "toggle_edit_mode"):
            self.parent_widget.toggle_edit_mode(active)

    def _handle_zoom_change(self) -> None:
        """Handle zoom slider value change."""
        # Update zoom label
        if hasattr(self, "zoom_label") and self.zoom_slider:
            self.zoom_label.setText(f"{self.zoom_slider.value()}%")
        # Notify parent widget
        if hasattr(self.parent_widget, "_handle_zoom"):
            self.parent_widget._handle_zoom()

    def _handle_zoom_reset(self) -> None:
        """Handle zoom reset button click."""
        if hasattr(self.parent_widget, "_reset_zoom"):
            self.parent_widget._reset_zoom()
