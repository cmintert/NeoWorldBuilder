
from typing import Optional, Dict, Any


from PyQt6.QtCore import pyqtSignal, Qt

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QTabWidget,
    QLabel,
    QLineEdit,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QDialog,
    QFormLayout,
    QDialogButtonBox,
    QMessageBox,
    QGroupBox,
)
from structlog import get_logger

from ui.components.calendar_component.card_based_calendar_widget import CompactCalendarDisplay

logger = get_logger(__name__)

class CalendarConfigDialog(QDialog):
    """Dialog for configuring calendar settings."""

    def __init__(self, calendar_data: Optional[Dict[str, Any]] = None, parent: Optional[QWidget] = None):
        logger.debug(
            "Initializing calendar config dialog",
            calendar_data=calendar_data,
            has_parent=bool(parent)
        )

        # Ensure parent is properly handled
        if parent is None:
            logger.warning("No parent widget provided for CalendarConfigDialog")

        super().__init__(parent)

        # Initialize default or existing calendar data
        if calendar_data is None:
            logger.debug("No calendar data provided, using defaults")
            self.calendar_data = {
                "calendar_type": "custom",
                "epoch_name": "Era",
                "current_year": 1,
                "year_length": 360,
                "month_names": ["Month 1"],
                "month_days": [30],
                "days_per_week": 7,
                "weekday_names": ["Day 1", "Day 2", "Day 3", "Day 4", "Day 5", "Day 6", "Day 7"],
                "leap_year_rule": "none"
            }
        else:
            logger.debug("Using provided calendar data", data=calendar_data)
            self.calendar_data = calendar_data

        try:
            self.setup_ui()
        except Exception as e:
            logger.error(
                "Failed to setup calendar config dialog UI",
                error=str(e),
                calendar_data=self.calendar_data
            )
            raise

    def setup_ui(self) -> None:
        """Setup the dialog UI."""
        layout = QVBoxLayout(self)

        # Create tabs for different configuration sections
        tabs = QTabWidget()

        # Basic Settings Tab
        basic_tab = QWidget()
        basic_layout = QFormLayout(basic_tab)

        self.epoch_name = QLineEdit(self.calendar_data["epoch_name"])
        self.current_year = QSpinBox()
        self.current_year.setRange(1, 99999)
        self.current_year.setValue(self.calendar_data["current_year"])
        self.year_length = QSpinBox()
        self.year_length.setRange(1, 999)
        self.year_length.setValue(self.calendar_data["year_length"])

        basic_layout.addRow("Epoch Name:", self.epoch_name)
        basic_layout.addRow("Current Year:", self.current_year)
        basic_layout.addRow("Days per Year:", self.year_length)

        # Months Tab
        months_tab = QWidget()
        months_layout = QVBoxLayout(months_tab)

        self.months_table = QTableWidget()
        self.months_table.setColumnCount(2)
        self.months_table.setHorizontalHeaderLabels(["Month Name", "Days"])

        # Add month data to table
        self._populate_months_table()

        # Add/Remove month buttons
        month_buttons = QHBoxLayout()
        add_month_btn = QPushButton("Add Month")
        add_month_btn.clicked.connect(self._add_month)
        remove_month_btn = QPushButton("Remove Month")
        remove_month_btn.clicked.connect(self._remove_month)
        month_buttons.addWidget(add_month_btn)
        month_buttons.addWidget(remove_month_btn)

        months_layout.addWidget(self.months_table)
        months_layout.addLayout(month_buttons)

        # Week Structure Tab
        week_tab = QWidget()
        week_layout = QVBoxLayout(week_tab)

        week_group = QGroupBox("Week Structure")
        week_form = QFormLayout()

        self.days_per_week = QSpinBox()
        self.days_per_week.setRange(1, 10)
        self.days_per_week.setValue(self.calendar_data["days_per_week"])
        self.days_per_week.valueChanged.connect(self._update_weekday_table)

        self.weekday_table = QTableWidget()
        self.weekday_table.setColumnCount(1)
        self.weekday_table.setHorizontalHeaderLabels(["Weekday Name"])

        # Populate weekday names
        self._populate_weekday_table()

        week_form.addRow("Days per Week:", self.days_per_week)
        week_form.addRow("Weekday Names:", self.weekday_table)
        week_group.setLayout(week_form)
        week_layout.addWidget(week_group)

        # Add tabs
        tabs.addTab(basic_tab, "Basic Settings")
        tabs.addTab(months_tab, "Months")
        tabs.addTab(week_tab, "Week Structure")

        # Dialog buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)

        layout.addWidget(tabs)
        layout.addWidget(button_box)

    def accept(self) -> None:
        """Handle dialog acceptance with proper error handling."""
        try:
            # Validate and collect data before accepting
            self.get_calendar_data()  # This will validate the data
            super().accept()
        except Exception as e:
            logger.error(
                "Error accepting calendar config",
                error=str(e),
                error_type=type(e).__name__
            )
            # Error already shown to user in get_calendar_data()
            return

    def _populate_months_table(self) -> None:
        """Populate the months table with current data."""
        # Check if we have the old nested structure or the new flattened structure
        if 'months' in self.calendar_data and 'days_per_months' in self.calendar_data:
            # Old nested structure
            month_names = [m['name'] for m in self.calendar_data['months']]
            month_days = [d['days'] for d in self.calendar_data['days_per_months']]
        else:
            # Assume flattened structure
            month_names = self.calendar_data.get('month_names', [])
            month_days = self.calendar_data.get('month_days', [])

        self.months_table.setRowCount(len(month_names))
        for i, name in enumerate(month_names):
            self.months_table.setItem(i, 0, QTableWidgetItem(name))

        for i, days in enumerate(month_days):
            self.months_table.setItem(i, 1, QTableWidgetItem(str(days)))

    def _populate_weekday_table(self) -> None:
        """Populate the weekday names table."""
        self.weekday_table.setRowCount(len(self.calendar_data["weekday_names"]))
        for i, name in enumerate(self.calendar_data["weekday_names"]):
            self.weekday_table.setItem(i, 0, QTableWidgetItem(name))

    def _add_month(self) -> None:
        """Add a new month to the table."""
        row = self.months_table.rowCount()
        self.months_table.insertRow(row)
        self.months_table.setItem(row, 0, QTableWidgetItem(f"Month {row + 1}"))
        self.months_table.setItem(row, 1, QTableWidgetItem("30"))

    def _remove_month(self) -> None:
        """Remove the selected month from the table."""
        current_row = self.months_table.currentRow()
        if current_row >= 0:
            self.months_table.removeRow(current_row)

    def _update_weekday_table(self) -> None:
        """Update weekday table when days per week changes."""
        new_days = self.days_per_week.value()
        current_rows = self.weekday_table.rowCount()

        if new_days > current_rows:
            # Add rows
            for i in range(current_rows, new_days):
                self.weekday_table.insertRow(i)
                self.weekday_table.setItem(i, 0, QTableWidgetItem(f"Day {i + 1}"))
        elif new_days < current_rows:
            # Remove rows
            for _ in range(current_rows - new_days):
                self.weekday_table.removeRow(self.weekday_table.rowCount() - 1)

    def get_calendar_data(self) -> Dict[str, Any]:
        """Get the current calendar configuration.

        Returns:
            Dict[str, Any]: The calendar configuration data
        """
        try:
            # Collect months names
            month_names = []
            month_days = []
            for row in range(self.months_table.rowCount()):
                name_item = self.months_table.item(row, 0)
                days_item = self.months_table.item(row, 1)

                if name_item and days_item:  # Check for valid items
                    month_names.append(name_item.text().strip())
                    month_days.append(int(days_item.text().strip()))

            # Collect weekday names
            weekday_names = []
            for row in range(self.weekday_table.rowCount()):
                name_item = self.weekday_table.item(row, 0)
                if name_item:
                    weekday_names.append(name_item.text().strip())

            # Build and validate configuration
            calendar_data = {
                "calendar_type": "custom",
                "epoch_name": self.epoch_name.text().strip(),
                "current_year": self.current_year.value(),
                "year_length": self.year_length.value(),
                "month_names": month_names,
                "month_days": month_days,
                "days_per_week": self.days_per_week.value(),
                "weekday_names": weekday_names,
                "leap_year_rule": "none"
            }

            # Validate total days matches year length
            total_days = sum(month_days)
            if total_days != calendar_data["year_length"]:
                raise ValueError(
                    f"Total days in months ({total_days}) does not match year length ({calendar_data['year_length']})"
                )

            logger.debug("Calendar data collected", data=calendar_data)
            return calendar_data

        except Exception as e:
            logger.error(
                "Error collecting calendar data",
                error=str(e),
                error_type=type(e).__name__
            )
            # Show error to user
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to save calendar configuration: {str(e)}"
            )
            raise


class CalendarTab(QWidget):
    """Calendar tab component for configuring and displaying calendar information."""

    calendar_changed = pyqtSignal(dict)  # Signal when calendar configuration changes

    def __init__(self, parent: Optional[QWidget] = None, controller=None):
        """Initialize the calendar tab."""
        super().__init__(parent)
        self.controller = controller
        self.config = controller.config if controller else None
        self.calendar_data = None

        logger.debug(
            "Initializing calendar tab",
            has_controller=bool(controller),
            has_config=bool(self.config),
            parent_widget=bool(parent)
        )

        self.setup_calendar_tab_ui()

    def setup_calendar_tab_ui(self) -> None:
        """Setup the UI components."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Calendar controls
        controls_layout = QHBoxLayout()

        # Configuration button
        self.config_btn = QPushButton("⚙️ Configure Calendar")
        self.config_btn.clicked.connect(self._show_calendar_config)

        # Save configuration button
        self.save_btn = QPushButton("💾 Save Calendar")
        self.save_btn.clicked.connect(self._save_calendar_config)

        controls_layout.addWidget(self.config_btn)
        controls_layout.addWidget(self.save_btn)
        controls_layout.addStretch()

        # Modern calendar display
        self.calendar_display = CompactCalendarDisplay()
        self._update_info_display()  # This will now update our new display

        # Add components to layout
        layout.addLayout(controls_layout)
        layout.addWidget(self.calendar_display)

    def _update_info_display(self) -> None:
        """Update the calendar information display."""
        if not self.calendar_data:
            # Create a simple label for no data case
            no_data_label = QLabel("<i>No calendar configured</i>")
            no_data_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.calendar_display.layout.addWidget(no_data_label)
            return

        # Update the modern display with calendar data
        self.calendar_display.update_display(self.calendar_data)

    def _show_calendar_config(self) -> None:
        """Show the calendar configuration dialog."""
        try:
            logger.debug(
                "Opening calendar config dialog",
                current_data=self.calendar_data
            )

            # Create dialog with explicit parent and data
            dialog = CalendarConfigDialog(
                calendar_data=self.calendar_data,
                parent=self
            )

            # Show dialog and handle result
            if dialog.exec():
                new_data = dialog.get_calendar_data()
                logger.debug(
                    "Calendar config dialog accepted",
                    new_data=new_data
                )
                self.set_calendar_data(new_data)
            else:
                logger.debug("Calendar config dialog cancelled")

        except Exception as e:
            logger.error(
                "Error showing calendar config dialog",
                error=str(e),
                error_type=type(e).__name__
            )
            # Show error to user
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to open calendar configuration: {str(e)}"
            )

    def _save_calendar_config(self) -> None:
        """Save the current calendar configuration."""
        if not self.calendar_data:
            QMessageBox.warning(self, "Error", "No calendar data to save")
            return

        try:
            # Emit signal with new calendar data
            self.calendar_changed.emit(self.calendar_data)
            QMessageBox.information(self, "Success", "Calendar configuration saved successfully")

        except Exception as e:
            logger.error("Error saving calendar configuration", error=str(e))
            QMessageBox.critical(self, "Error", f"Failed to save calendar configuration: {str(e)}")

    def set_calendar_data(self, data: Dict[str, Any]) -> None:
        """Set the calendar data and update the UI.

        Args:
            data: Dictionary containing calendar configuration
        """
        try:
            logger.debug("Setting calendar data", data=data)

            if not data:
                logger.warning("Attempted to set empty calendar data")
                return

            self.calendar_data = data
            self._update_info_display()

            # Emit change signal to notify parent
            self.calendar_changed.emit(self.calendar_data)

            logger.debug("Calendar data set successfully")

        except Exception as e:
            logger.error(
                "Error setting calendar data",
                error=str(e),
                error_type=type(e).__name__,
                data=data
            )
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to update calendar configuration: {str(e)}"
            )

    def _update_info_display(self) -> None:
        """Update the calendar information display."""
        if not self.calendar_data:
            # Create a simple label for no data case
            no_data_label = QLabel("<i>No calendar configured</i>")
            no_data_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.calendar_display.layout.addWidget(no_data_label)
            return

        # Update the modern display with calendar data
        self.calendar_display.update_display(self.calendar_data)