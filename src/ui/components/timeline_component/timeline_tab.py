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


class TimelineTab(QWidget):
    """Timeline tab for displaying events on a temporal scale."""

    def __init__(self, controller: "WorldBuildingController"):
        super().__init__()
        self.controller = controller
        self.calendar_data = None
        self._current_calendar_element_id = None
        self.events = []

        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        """Setup the UI components."""
        layout = QVBoxLayout()

        # Top controls
        controls_layout = QHBoxLayout()

        # Calendar selection (similar to EventTab)
        calendar_layout = QHBoxLayout()
        self.calendar_input = QLineEdit()
        self.calendar_input.setPlaceholderText("Select a calendar...")

        self.calendar_validation_label = QLabel()
        self.calendar_validation_label.setVisible(False)

        self.link_calendar_btn = QPushButton("Link Calendar")
        self.link_calendar_btn.setEnabled(True)

        self.calendar_completer = QCompleter()
        self.calendar_completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.calendar_completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.calendar_completer.setCompletionMode(
            QCompleter.CompletionMode.PopupCompletion
        )

        self.calendar_input.setCompleter(self.calendar_completer)

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

        # Timeline widget will go here
        self.timeline_widget = TimelineWidget()

        layout.addLayout(controls_layout)
        layout.addWidget(self.timeline_widget)
        self.setLayout(layout)
