from typing import Optional, Dict, Any

from PyQt6.QtWidgets import (
    QDialog,
    QFormLayout,
    QWidget,
    QTabWidget,
    QVBoxLayout,
    QLineEdit,
    QSpinBox,
    QTableWidget,
    QHBoxLayout,
    QPushButton,
    QGroupBox,
    QDialogButtonBox,
    QTableWidgetItem,
    QMessageBox,
)

from config.config import logger


class CalendarConfigDialog(QDialog):
    """Dialog for configuring calendar settings."""

    def __init__(
        self,
        calendar_data: Optional[Dict[str, Any]] = None,
        parent: Optional[QWidget] = None,
    ):
        logger.debug(
            "Initializing calendar config dialog",
            calendar_data=calendar_data,
            has_parent=bool(parent),
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
                "epoch_names": ["Ano domini"],
                "epoch_abbreviations": ["AD"],
                "epoch_start_years": [0],
                "epoch_end_years": [99999],
                "current_year": 1,
                "year_length": 30,
                "month_names": ["Month 1"],
                "month_days": [30],
                "days_per_week": 7,
                "weekday_names": [
                    "Day 1",
                    "Day 2",
                    "Day 3",
                    "Day 4",
                    "Day 5",
                    "Day 6",
                    "Day 7",
                ],
                "leap_year_rule": "none",
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
                calendar_data=self.calendar_data,
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

        self.current_year = QSpinBox()
        self.current_year.setRange(1, 99999)
        self.current_year.setValue(self.calendar_data["current_year"])
        self.year_length = QSpinBox()
        self.year_length.setRange(1, 999)
        self.year_length.setValue(self.calendar_data["year_length"])

        basic_layout.addRow("Current Year:", self.current_year)
        basic_layout.addRow("Days per Year:", self.year_length)

        # Epochs Tab
        epochs_tab = QWidget()
        epochs_layout = QVBoxLayout(epochs_tab)

        self.epochs_table = QTableWidget()
        self.epochs_table.setColumnCount(4)  # 4 columns for each epoch attribute
        self.epochs_table.setHorizontalHeaderLabels(
            ["Epoch Name", "Abbreviation", "Start Year", "End Year"]
        )

        # Add epoch data to table
        self._populate_epochs_table()

        # Add/Remove epoch buttons
        epoch_buttons = QHBoxLayout()
        add_epoch_btn = QPushButton("Add Epoch")
        add_epoch_btn.clicked.connect(self._add_epoch)
        remove_epoch_btn = QPushButton("Remove Epoch")
        remove_epoch_btn.clicked.connect(self._remove_epoch)
        epoch_buttons.addWidget(add_epoch_btn)
        epoch_buttons.addWidget(remove_epoch_btn)

        epochs_layout.addWidget(self.epochs_table)
        epochs_layout.addLayout(epoch_buttons)

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
        tabs.addTab(epochs_tab, "Epochs")
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

    def _add_epoch(self) -> None:
        """Add a new epoch to the table."""
        row = self.epochs_table.rowCount()
        self.epochs_table.insertRow(row)
        self.epochs_table.setItem(row, 0, QTableWidgetItem("New Epoch"))
        self.epochs_table.setItem(row, 1, QTableWidgetItem("NE"))
        self.epochs_table.setItem(row, 2, QTableWidgetItem("0"))
        self.epochs_table.setItem(row, 3, QTableWidgetItem("99999"))

    def _remove_epoch(self) -> None:
        """Remove the selected epoch from the table."""
        current_row = self.epochs_table.currentRow()
        if current_row >= 0:
            self.epochs_table.removeRow(current_row)

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
                error_type=type(e).__name__,
            )
            # Error already shown to user in get_calendar_data()
            return

    def _populate_months_table(self) -> None:
        """Populate the months table with current data."""
        # Check if we have the old nested structure or the new flattened structure
        if "months" in self.calendar_data and "days_per_months" in self.calendar_data:
            # Old nested structure
            month_names = [m["name"] for m in self.calendar_data["months"]]
            month_days = [d["days"] for d in self.calendar_data["days_per_months"]]
        else:
            # Assume flattened structure
            month_names = self.calendar_data.get("month_names", [])
            month_days = self.calendar_data.get("month_days", [])

        self.months_table.setRowCount(len(month_names))
        for i, name in enumerate(month_names):
            self.months_table.setItem(i, 0, QTableWidgetItem(name))

        for i, days in enumerate(month_days):
            self.months_table.setItem(i, 1, QTableWidgetItem(str(days)))

    def _populate_epochs_table(self) -> None:
        """Populate the epochs table with current data."""
        epoch_names = self.calendar_data.get("epoch_names", [])
        epoch_abbreviations = self.calendar_data.get("epoch_abbreviations", [])
        epoch_start_years = self.calendar_data.get("epoch_start_years", [])
        epoch_end_years = self.calendar_data.get("epoch_end_years", [])

        self.epochs_table.setRowCount(len(epoch_names))
        for i, name in enumerate(epoch_names):
            self.epochs_table.setItem(i, 0, QTableWidgetItem(name))

        for i, abbr in enumerate(epoch_abbreviations):
            self.epochs_table.setItem(i, 1, QTableWidgetItem(abbr))

        for i, start in enumerate(epoch_start_years):
            self.epochs_table.setItem(i, 2, QTableWidgetItem(str(start)))

        for i, end in enumerate(epoch_end_years):
            self.epochs_table.setItem(i, 3, QTableWidgetItem(str(end)))

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

            # Collect epoch data
            epoch_names = []
            epoch_abbreviations = []
            epoch_start_years = []
            epoch_end_years = []

            for row in range(self.epochs_table.rowCount()):
                name_item = self.epochs_table.item(row, 0)
                abbr_item = self.epochs_table.item(row, 1)
                start_item = self.epochs_table.item(row, 2)
                end_item = self.epochs_table.item(row, 3)

                if all(
                    item is not None
                    for item in [name_item, abbr_item, start_item, end_item]
                ):
                    epoch_names.append(name_item.text().strip())
                    epoch_abbreviations.append(abbr_item.text().strip())
                    try:
                        epoch_start_years.append(int(start_item.text().strip()))
                        epoch_end_years.append(int(end_item.text().strip()))
                    except ValueError as e:
                        raise ValueError(f"Invalid year value in epoch data: {e}")

            # Build and validate configuration
            calendar_data = {
                "calendar_type": "custom",
                "epoch_names": epoch_names,
                "epoch_abbreviations": epoch_abbreviations,
                "epoch_start_years": epoch_start_years,
                "epoch_end_years": epoch_end_years,
                "current_year": self.current_year.value(),
                "year_length": self.year_length.value(),
                "month_names": month_names,
                "month_days": month_days,
                "days_per_week": self.days_per_week.value(),
                "weekday_names": weekday_names,
                "leap_year_rule": "none",
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
                error_type=type(e).__name__,
            )
            # Show error to user
            QMessageBox.critical(
                self, "Error", f"Failed to save calendar configuration: {str(e)}"
            )
            raise
