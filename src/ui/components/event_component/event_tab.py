from typing import Dict, Any, Optional


from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,

    QLineEdit,
    QFormLayout,
    QLabel,

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

        layout.addLayout(form_layout)
        layout.addStretch()
        self.setLayout(layout)

    def _connect_signals(self):
        """Connect UI signals to handlers"""
        self.date_input.textChanged.connect(self._validate_date)

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
        """Emit event data for saving, ensuring all values are properly converted to strings.

        This method prepares event data for the UI by:
        1. Converting all numeric values to strings to avoid Qt setText() type errors
        2. Handling None/null values gracefully by converting them to empty strings
        3. Maintaining the hierarchical structure of date data

        Args:
            parsed_date (Optional[ParsedDate]): The parsed date object containing temporal information

        The emitted data will contain all date components as strings, ready for UI display.
        """
        # Get the basic temporal data from the input field
        temporal_data = self.date_input.text()

        # Start building our event data dictionary
        data = {
            # Basic event properties
            "temporal_data": temporal_data,
            # Core date fields - convert numeric values to strings
            "parsed_date_year": (
                str(parsed_date.year)
                if parsed_date and parsed_date.year is not None
                else ""
            ),
            "parsed_date_month": (
                str(parsed_date.month)
                if parsed_date and parsed_date.month is not None
                else ""
            ),
            "parsed_date_day": (
                str(parsed_date.day)
                if parsed_date and parsed_date.day is not None
                else ""
            ),
            # Precision and confidence values
            "parsed_date_precision": (
                parsed_date.precision.name
                if parsed_date and parsed_date.precision
                else ""
            ),
            "parsed_date_confidence": (
                str(parsed_date.confidence)
                if parsed_date and parsed_date.confidence is not None
                else ""
            ),
            # Relative date information
            "parsed_date_relative_to": (
                str(parsed_date.relative_to)
                if parsed_date and parsed_date.relative_to
                else ""
            ),
            "parsed_date_relative_days": (
                str(parsed_date.relative_days)
                if parsed_date and parsed_date.relative_days is not None
                else ""
            ),
            # Additional date information
            "parsed_date_season": (
                str(parsed_date.season) if parsed_date and parsed_date.season else ""
            ),
        }

        # Add range start information if it exists
        if parsed_date and parsed_date.range_start:
            data.update(
                {
                    "parsed_date_range_start_year": (
                        str(parsed_date.range_start.year)
                        if parsed_date.range_start.year is not None
                        else ""
                    ),
                    "parsed_date_range_start_month": (
                        str(parsed_date.range_start.month)
                        if parsed_date.range_start.month is not None
                        else ""
                    ),
                    "parsed_date_range_start_day": (
                        str(parsed_date.range_start.day)
                        if parsed_date.range_start.day is not None
                        else ""
                    ),
                    "parsed_date_range_start_precision": (
                        parsed_date.range_start.precision.name
                        if parsed_date.range_start.precision
                        else ""
                    ),
                }
            )
        else:
            # Add empty strings for range start fields if no range start exists
            data.update(
                {
                    "parsed_date_range_start_year": "",
                    "parsed_date_range_start_month": "",
                    "parsed_date_range_start_day": "",
                    "parsed_date_range_start_precision": "",
                }
            )

        # Add range end information if it exists
        if parsed_date and parsed_date.range_end:
            data.update(
                {
                    "parsed_date_range_end_year": (
                        str(parsed_date.range_end.year)
                        if parsed_date.range_end.year is not None
                        else ""
                    ),
                    "parsed_date_range_end_month": (
                        str(parsed_date.range_end.month)
                        if parsed_date.range_end.month is not None
                        else ""
                    ),
                    "parsed_date_range_end_day": (
                        str(parsed_date.range_end.day)
                        if parsed_date.range_end.day is not None
                        else ""
                    ),
                    "parsed_date_range_end_precision": (
                        parsed_date.range_end.precision.name
                        if parsed_date.range_end.precision
                        else ""
                    ),
                }
            )
        else:
            # Add empty strings for range end fields if no range end exists
            data.update(
                {
                    "parsed_date_range_end_year": "",
                    "parsed_date_range_end_month": "",
                    "parsed_date_range_end_day": "",
                    "parsed_date_range_end_precision": "",
                }
            )

        # Emit the event with our properly formatted data
        self.event_changed.emit(data)

    def set_event_data(self, data: Dict[str, Any]):
        """Load event data into UI components"""
        if not data:
            return

        try:
            # Set the temporal data directly in the date input field
            if temporal_data := data.get("temporal_data"):
                # Temporarily disconnect textChanged signal to prevent premature validation
                self.date_input.textChanged.disconnect(self._validate_date)
                self.date_input.setText(str(temporal_data))
                # Reconnect the signal
                self.date_input.textChanged.connect(self._validate_date)
                # Validate if we have calendar data
                if self.date_parser and self.calendar_data:
                    self._validate_date()

        except Exception as e:
            logger.error("Failed to load event data", error=str(e))

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

            # Now that we have calendar data, validate any existing input
            # This is key - we validate after calendar data is set
            if text := self.date_input.text():
                self._validate_date()

        except Exception as e:
            logger.error("Failed to set calendar data", error=str(e))
            self.validation_label.setStyleSheet("color: red")
            self.validation_label.setText(f"Calendar error: {str(e)}")

    def _get_month_name(self, month_num: int) -> str:
        """Get month name from number using current calendar"""
        if not self.calendar_data or "month_names" not in self.calendar_data:
            return str(month_num)
        try:
            return self.calendar_data["month_names"][month_num - 1]
        except IndexError:
            return str(month_num)

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
