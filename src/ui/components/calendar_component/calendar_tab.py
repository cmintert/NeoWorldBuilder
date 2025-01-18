from typing import Optional, Dict, Any
import json

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
    QGroupBox
)
from structlog import get_logger

logger = get_logger(__name__)

class CalendarConfigDialog(QDialog):
    """Dialog for configuring calendar settings."""

    def __init__(self, calendar_data: Optional[Dict[str, Any]] = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Calendar Configuration")
        self.setModal(True)

        # Initialize default or existing calendar data
        self.calendar_data = calendar_data or {
            "calendar_type": "custom",
            "epoch_name": "Era",
            "current_year": 1,
            "year_length": 360,
            "months": [{"name": "Month 1", "days": 30}],
            "days_per_week": 7,
            "weekday_names": ["Day 1", "Day 2", "Day 3", "Day 4", "Day 5", "Day 6", "Day 7"],
            "leap_year_rule": "none",
            "special_dates": []
        }

        self.setup_ui()

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

    def _populate_months_table(self) -> None:
        """Populate the months table with current data."""
        self.months_table.setRowCount(len(self.calendar_data["months"]))
        for i, month in enumerate(self.calendar_data["months"]):
            self.months_table.setItem(i, 0, QTableWidgetItem(month["name"]))
            days_item = QTableWidgetItem(str(month["days"]))
            self.months_table.setItem(i, 1, days_item)

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
        # Collect months data
        months = []
        for row in range(self.months_table.rowCount()):
            name = self.months_table.item(row, 0).text()
            days = int(self.months_table.item(row, 1).text())
            months.append({"name": name, "days": days})

        # Collect weekday names
        weekday_names = []
        for row in range(self.weekday_table.rowCount()):
            weekday_names.append(self.weekday_table.item(row, 0).text())

        return {
            "calendar_type": "custom",
            "epoch_name": self.epoch_name.text(),
            "current_year": self.current_year.value(),
            "year_length": self.year_length.value(),
            "months": months,
            "days_per_week": self.days_per_week.value(),
            "weekday_names": weekday_names,
            "leap_year_rule": "none",
            "special_dates": self.calendar_data.get("special_dates", [])
        }


class CalendarTab(QWidget):
    """Calendar tab component for configuring and displaying calendar information."""

    calendar_changed = pyqtSignal(dict)  # Signal when calendar configuration changes

    def __init__(self, parent: Optional[QWidget] = None, controller=None):
        """Initialize the calendar tab."""
        super().__init__(parent)
        self.controller = controller
        self.config = controller.config if controller else None
        self.calendar_data = None

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

        # Calendar info display
        self.info_label = QLabel()
        self.info_label.setWordWrap(True)
        self.info_label.setTextFormat(Qt.TextFormat.RichText)
        self._update_info_display()

        # Add components to layout
        layout.addLayout(controls_layout)
        layout.addWidget(self.info_label)
        layout.addStretch()

    def _show_calendar_config(self) -> None:
        """Show the calendar configuration dialog."""
        dialog = CalendarConfigDialog(self.calendar_data, self)
        if dialog.exec():
            self.set_calendar_data(dialog.get_calendar_data())

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
            self.calendar_data = data
            self._update_info_display()

        except Exception as e:
            logger.error("Error setting calendar data", error=str(e))
            QMessageBox.critical(self, "Error", f"Failed to set calendar data: {str(e)}")

    def _update_info_display(self) -> None:
        """Update the calendar information display."""
        if not self.calendar_data:
            self.info_label.setText("<i>No calendar configured</i>")
            return

        info_html = f"""
        <h3>{self.calendar_data['epoch_name']}</h3>
        <p><b>Current Year:</b> {self.calendar_data['current_year']}</p>
        <p><b>Days per Year:</b> {self.calendar_data['year_length']}</p>
        <p><b>Days per Week:</b> {self.calendar_data['days_per_week']}</p>
        <br>
        <p><b>Months:</b></p>
        <ul>
        """

        for month in self.calendar_data['months']:
            info_html += f"<li>{month['name']} ({month['days']} days)</li>"

        info_html += """
        </ul>
        <br>
        <p><b>Weekdays:</b></p>
        <ul>
        """

        for day in self.calendar_data['weekday_names']:
            info_html += f"<li>{day}</li>"

        info_html += "</ul>"

        self.info_label.setText(info_html)