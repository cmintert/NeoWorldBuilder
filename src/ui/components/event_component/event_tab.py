from typing import Dict, Any, Optional
from dataclasses import asdict

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QComboBox,
    QLineEdit,
    QFormLayout,
    QLabel,
    QCheckBox,
    QMessageBox,
)

from date_parser_module.dateparser import DateParser, ParsedDate, DatePrecision
from structlog import get_logger

logger = get_logger(__name__)


class EventTab(QWidget):
    """Tab for managing temporal event data"""

    event_changed = pyqtSignal(dict)  # Emit temporal data changes

    def __init__(self, controller: "WorldBuildingController"):
        super().__init__()
        self.controller = controller
        self.date_parser = None
        self.calendar_data = None
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        """Create and arrange UI elements"""
        layout = QVBoxLayout()
        form_layout = QFormLayout()

        # Event type selection
        self.event_type = QComboBox()
        self.event_type.addItems(
            [
                "Occurrence",  # Single point in time
                "Period",  # Time span
                "Era",  # Major time period
                "Cycle",  # Recurring event
            ]
        )
        form_layout.addRow("Event Type:", self.event_type)

        # Date input with validation
        self.date_input = QLineEdit()
        self.date_input.setPlaceholderText(
            "Enter date (e.g. 15th day of Summermonth, 1245)"
        )
        date_layout = QHBoxLayout()
        date_layout.addWidget(self.date_input)
        form_layout.addRow("Date:", date_layout)

        # Validation status
        self.validation_label = QLabel()
        self.validation_label.setWordWrap(True)
        form_layout.addRow("", self.validation_label)

        # Relative event reference
        reference_layout = QHBoxLayout()
        self.relative_checkbox = QCheckBox("Relative to Event:")
        self.reference_selector = QComboBox()
        self.reference_selector.setEnabled(False)
        reference_layout.addWidget(self.relative_checkbox)
        reference_layout.addWidget(self.reference_selector)
        form_layout.addRow("", reference_layout)

        layout.addLayout(form_layout)
        layout.addStretch()
        self.setLayout(layout)

    def _connect_signals(self):
        """Connect UI signals to handlers"""
        self.date_input.textChanged.connect(self._validate_date)
        self.event_type.currentTextChanged.connect(self._handle_type_changed)
        self.relative_checkbox.toggled.connect(self._handle_relative_toggled)

    def _validate_date(self):
        """Validate date input and update UI"""
        date_str = self.date_input.text().strip()
        if not date_str:
            self.validation_label.setText("")
            return

        if not self.date_parser:
            self.validation_label.setStyleSheet("color: orange")
            self.validation_label.setText("Waiting for calendar data...")
            return

        try:
            parsed_date = self.date_parser.parse_date(date_str)
            self._show_validation_success(parsed_date)
            self._emit_event_data(parsed_date)
        except ValueError as e:
            self._show_validation_error(str(e))

    def _show_validation_success(self, parsed_date: ParsedDate):
        """Show success styling and parsed date details"""
        self.validation_label.setStyleSheet("color: green")
        msg = self._format_validation_message(parsed_date)
        self.validation_label.setText(msg)

    def _format_validation_message(self, parsed_date: ParsedDate) -> str:
        """Format the validation message based on date precision"""
        msg = "Valid date: "

        if parsed_date.precision == DatePrecision.EXACT:
            msg += f"Day {parsed_date.day} of {self._get_month_name(parsed_date.month)}, Year {parsed_date.year}"
        elif parsed_date.precision == DatePrecision.MONTH:
            msg += f"{self._get_month_name(parsed_date.month)}, Year {parsed_date.year}"
        elif parsed_date.precision == DatePrecision.YEAR:
            msg += f"Year {parsed_date.year}"
        elif parsed_date.precision == DatePrecision.SEASON:
            msg += f"{parsed_date.season.title()} of Year {parsed_date.year}"

        return msg

    def _show_validation_error(self, error: str):
        """Show error styling and message"""
        self.validation_label.setStyleSheet("color: red")
        self.validation_label.setText(f"Invalid date: {error}")

    def _emit_event_data(self, parsed_date: Optional[ParsedDate] = None):
        """Emit event data for saving"""
        temporal_data = self.date_input.text()
        parsed_temporal_data = None

        if parsed_date is None and self.date_parser is not None:
            try:
                parsed_date = self.date_parser.parse_date(temporal_data)
                parsed_temporal_data = self.date_parser.to_json(parsed_date)
            except ValueError:
                pass
        elif parsed_date and self.date_parser:
            parsed_temporal_data = self.date_parser.to_json(parsed_date)

        data = {
            "event_type": self.event_type.currentText(),
            "temporal_data": temporal_data,
            "parsed_temporal_data": parsed_temporal_data,
            "relative_to": (
                self.reference_selector.currentText()
                if self.relative_checkbox.isChecked()
                else None
            ),
        }

        self.event_changed.emit(data)

    def set_event_data(self, data: Dict[str, Any]):
        """Load event data into UI"""
        if not data:
            return

        try:
            self.date_input.setText(data.get("temporal_data", ""))
            self.event_type.setCurrentText(data.get("event_type", "Occurrence"))

            # Handle relative event data
            relative_to = data.get("relative_to")
            if relative_to:
                self.relative_checkbox.setChecked(True)
                index = self.reference_selector.findText(relative_to)
                if index >= 0:
                    self.reference_selector.setCurrentIndex(index)

        except Exception as e:
            logger.error("Failed to load event data", error=str(e))
            QMessageBox.warning(self, "Error", f"Failed to load event data: {str(e)}")

    def set_calendar_data(self, calendar_data: Dict[str, Any]) -> None:
        """Update calendar data and parser"""
        logger.debug("EventTab.set_calendar_data: received data", data=calendar_data)

        try:
            # Store calendar data
            self.calendar_data = calendar_data

            # Initialize parser
            self.date_parser = DateParser(calendar_data)
            logger.debug("DateParser initialized successfully")

            # Update UI state
            self._update_ui_state()

            # Revalidate current input if any
            if self.date_input.text():
                self._validate_date()

        except Exception as e:
            logger.error("Failed to set calendar data", error=str(e))
            self.validation_label.setStyleSheet("color: red")
            self.validation_label.setText(f"Calendar error: {str(e)}")

    def _handle_type_changed(self, event_type: str):
        """Handle event type selection change"""
        if event_type == "Period":
            self.date_input.setPlaceholderText(
                "Enter date range (e.g. from 1st to 15th Summermonth 1245)"
            )
        elif event_type == "Cycle":
            self.date_input.setPlaceholderText(
                "Enter recurring pattern (e.g. every spring)"
            )
        else:
            self.date_input.setPlaceholderText(
                "Enter date (e.g. 15th day of Summermonth, 1245)"
            )
        self._emit_event_data()

    def _handle_relative_toggled(self, checked: bool):
        """Handle relative event checkbox toggle"""
        self.reference_selector.setEnabled(checked)
        if checked and not self.reference_selector.count():
            self._populate_event_references()
        self._emit_event_data()

    def _get_month_name(self, month_num: int) -> str:
        """Get month name from number using current calendar"""
        if not self.calendar_data or "month_names" not in self.calendar_data:
            return str(month_num)
        try:
            return self.calendar_data["month_names"][month_num - 1]
        except IndexError:
            return str(month_num)

    def _populate_event_references(self):
        """Populate reference event selector with available events"""
        # TODO: Query relationships for available event references
        pass

    def _update_ui_state(self) -> None:
        """Update UI elements based on calendar availability"""
        has_calendar = bool(self.calendar_data and self.date_parser)

        # Update input placeholder
        if has_calendar:
            month_example = self.calendar_data["month_names"][0]
            self.date_input.setPlaceholderText(
                f"Enter date (e.g. 15th day of {month_example}, 1245)"
            )
        else:
            self.date_input.setPlaceholderText("Waiting for calendar data...")

        # Enable/disable inputs based on calendar availability
        self.date_input.setEnabled(has_calendar)
        self.event_type.setEnabled(has_calendar)
