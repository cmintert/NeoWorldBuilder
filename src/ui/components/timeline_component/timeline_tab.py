from typing import List, Dict, Any, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QVBoxLayout,
    QHBoxLayout,
    QLineEdit,
    QLabel,
    QPushButton,
    QCompleter,
    QComboBox,
    QWidget,
)
from structlog import get_logger

from ui.components.timeline_component.timeline_widget import TimelineWidget

logger = get_logger(__name__)


class TimelineTab(QWidget):
    """Timeline tab for displaying events on a temporal scale."""

    def __init__(self, controller: "WorldBuildingController"):
        super().__init__()
        self.controller = controller
        self.calendar_data = None
        self._current_calendar_element_id = None
        self.events = []

        # Initialize completer before setup_ui
        self.calendar_completer = QCompleter()
        self.calendar_completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.calendar_completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.calendar_completer.setCompletionMode(
            QCompleter.CompletionMode.PopupCompletion
        )

        # Create UI elements
        self._setup_ui()

        # Connect signals after UI is set up
        self._connect_signals()

    def _setup_ui(self):
        """Setup the UI components."""
        layout = QVBoxLayout()

        # Top controls
        controls_layout = QHBoxLayout()

        # Calendar section
        calendar_layout = QHBoxLayout()
        self.calendar_input = QLineEdit()
        self.calendar_input.setPlaceholderText("Select a calendar...")
        self.calendar_input.setCompleter(
            self.calendar_completer
        )  # Set completer after creation

        self.calendar_validation_label = QLabel()
        self.calendar_validation_label.setVisible(False)

        self.link_calendar_btn = QPushButton("Link Calendar")
        self.link_calendar_btn.setEnabled(True)

        # Scale selection
        scale_layout = QHBoxLayout()
        scale_label = QLabel("Scale:")
        self.scale_combo = QComboBox()
        self.scale_combo.addItems(["Decades", "Years", "Months", "Days"])

        # Layout assembly
        calendar_layout.addWidget(QLabel("Calendar:"))
        calendar_layout.addWidget(self.calendar_input)
        calendar_layout.addWidget(self.calendar_validation_label)
        calendar_layout.addWidget(self.link_calendar_btn)

        scale_layout.addWidget(scale_label)
        scale_layout.addWidget(self.scale_combo)

        controls_layout.addLayout(calendar_layout)
        controls_layout.addSpacing(20)
        controls_layout.addLayout(scale_layout)
        controls_layout.addStretch()

        # Timeline widget
        self.timeline_widget = TimelineWidget()

        layout.addLayout(controls_layout)
        layout.addWidget(self.timeline_widget)
        self.setLayout(layout)

    def _connect_signals(self):
        """Connect UI signals to handlers"""
        self.link_calendar_btn.clicked.connect(self._link_calendar)
        self.calendar_input.textChanged.connect(self._on_calendar_input_changed)
        self.calendar_completer.activated.connect(self._on_calendar_selected)
        self.calendar_completer.highlighted.connect(self._on_completion_highlighted)
        self.scale_combo.currentTextChanged.connect(self._on_scale_changed)

    def _on_calendar_input_changed(self, text: str):
        """Handle changes to calendar input."""
        if hasattr(self.controller, "update_calendar_suggestions"):
            self.controller.update_calendar_suggestions(text, self.calendar_completer)

    def _on_calendar_selected(self, name: str):
        """Handle calendar selection from completer."""
        if hasattr(self.controller, "calendar_element_ids"):
            element_id = self.controller.calendar_element_ids.get(name)
            if element_id:
                self._current_calendar_element_id = element_id
                self._validate_selected_calendar(element_id)
                self.calendar_input.setText(name)

    def _on_completion_highlighted(self, text: str):
        """Handle highlighting of completion items."""
        # Required by the completer interface but no action needed
        pass

    def _on_scale_changed(self, scale: str):
        """Handle scale selection changes."""
        if hasattr(self, "timeline_widget"):
            self.timeline_widget.set_data(self.events, scale)

    def _link_calendar(self):
        """Link calendar to timeline."""
        calendar_name = self.calendar_input.text().strip()
        if hasattr(self.controller, "add_calendar_relationship"):
            self.controller.add_calendar_relationship(calendar_name)

    def _validate_selected_calendar(self, element_id: str):
        """Validate selected calendar node."""

        def handle_validation(results):
            is_valid = results[0].get("is_calendar", False) if results else False
            self._update_validation_state(is_valid)

        if hasattr(self.controller, "validate_calendar_node"):
            self.controller.validate_calendar_node(element_id, handle_validation)

    def _update_validation_state(self, is_valid: bool):
        """Update UI based on validation state."""
        self.calendar_validation_label.setVisible(True)
        if is_valid:
            self.calendar_validation_label.setText("✓")
            self.calendar_validation_label.setStyleSheet("color: green")
            self.calendar_input.setStyleSheet("")
        else:
            self.calendar_validation_label.setText("✗")
            self.calendar_validation_label.setStyleSheet("color: red")
            self.calendar_input.setStyleSheet("border: 1px solid red")

    def set_event_data(self, events: List[Dict[str, Any]]) -> None:
        """Set event data for the timeline.

        Args:
            events: List of event dictionaries containing date and description info
        """
        self.events = events
        if hasattr(self, "timeline_widget"):
            self.timeline_widget.set_data(events, self.scale_combo.currentText())

    def set_calendar_data(self, calendar_data: Dict[str, Any]) -> None:
        """Set calendar data for date handling.

        Args:
            calendar_data: Dictionary containing calendar configuration
        """
        self.calendar_data = calendar_data
