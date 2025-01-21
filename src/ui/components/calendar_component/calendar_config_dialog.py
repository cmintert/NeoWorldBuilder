from typing import Optional, Dict, Any

from PyQt6.QtWidgets import QDialog, QFormLayout, QWidget, QTabWidget, QVBoxLayout, QLineEdit, QSpinBox, QTableWidget, \
    QHBoxLayout, QPushButton, QGroupBox, QDialogButtonBox, QTableWidgetItem, QMessageBox

from config.config import logger


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
                "leap_year_rule": "none",
                "seasons": [],
                "lunar_cycles": []
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

        # Seasons Tab
        seasons_tab = QWidget()
        seasons_layout = QVBoxLayout(seasons_tab)

        self.seasons_table = QTableWidget()
        self.seasons_table.setColumnCount(5)
        self.seasons_table.setHorizontalHeaderLabels(["Season Name", "Start Month", "Start Day", "End Month", "End Day"])

        # Add season data to table
        self._populate_seasons_table()

        # Add/Remove season buttons
        season_buttons = QHBoxLayout()
        add_season_btn = QPushButton("Add Season")
        add_season_btn.clicked.connect(self._add_season)
        remove_season_btn = QPushButton("Remove Season")
        remove_season_btn.clicked.connect(self._remove_season)
        season_buttons.addWidget(add_season_btn)
        season_buttons.addWidget(remove_season_btn)

        seasons_layout.addWidget(self.seasons_table)
        seasons_layout.addLayout(season_buttons)

        # Lunar Cycles Tab
        lunar_cycles_tab = QWidget()
        lunar_cycles_layout = QVBoxLayout(lunar_cycles_tab)

        self.lunar_cycles_table = QTableWidget()
        self.lunar_cycles_table.setColumnCount(5)
        self.lunar_cycles_table.setHorizontalHeaderLabels(["Cycle Name", "Start Month", "Start Day", "End Month", "End Day"])

        # Add lunar cycle data to table
        self._populate_lunar_cycles_table()

        # Add/Remove lunar cycle buttons
        lunar_cycle_buttons = QHBoxLayout()
        add_lunar_cycle_btn = QPushButton("Add Lunar Cycle")
        add_lunar_cycle_btn.clicked.connect(self._add_lunar_cycle)
        remove_lunar_cycle_btn = QPushButton("Remove Lunar Cycle")
        remove_lunar_cycle_btn.clicked.connect(self._remove_lunar_cycle)
        lunar_cycle_buttons.addWidget(add_lunar_cycle_btn)
        lunar_cycle_buttons.addWidget(remove_lunar_cycle_btn)

        lunar_cycles_layout.addWidget(self.lunar_cycles_table)
        lunar_cycles_layout.addLayout(lunar_cycle_buttons)

        # Add tabs
        tabs.addTab(basic_tab, "Basic Settings")
        tabs.addTab(months_tab, "Months")
        tabs.addTab(week_tab, "Week Structure")
        tabs.addTab(seasons_tab, "Seasons")
        tabs.addTab(lunar_cycles_tab, "Lunar Cycles")

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

    def _populate_seasons_table(self) -> None:
        """Populate the seasons table with current data."""
        self.seasons_table.setRowCount(len(self.calendar_data["seasons"]))
        for i, season in enumerate(self.calendar_data["seasons"]):
            self.seasons_table.setItem(i, 0, QTableWidgetItem(season["name"]))
            self.seasons_table.setItem(i, 1, QTableWidgetItem(str(season["start_month"])))
            self.seasons_table.setItem(i, 2, QTableWidgetItem(str(season["start_day"])))
            self.seasons_table.setItem(i, 3, QTableWidgetItem(str(season["end_month"])))
            self.seasons_table.setItem(i, 4, QTableWidgetItem(str(season["end_day"])))

    def _populate_lunar_cycles_table(self) -> None:
        """Populate the lunar cycles table with current data."""
        self.lunar_cycles_table.setRowCount(len(self.calendar_data["lunar_cycles"]))
        for i, cycle in enumerate(self.calendar_data["lunar_cycles"]):
            self.lunar_cycles_table.setItem(i, 0, QTableWidgetItem(cycle["name"]))
            self.lunar_cycles_table.setItem(i, 1, QTableWidgetItem(str(cycle["start_month"])))
            self.lunar_cycles_table.setItem(i, 2, QTableWidgetItem(str(cycle["start_day"])))
            self.lunar_cycles_table.setItem(i, 3, QTableWidgetItem(str(cycle["end_month"])))
            self.lunar_cycles_table.setItem(i, 4, QTableWidgetItem(str(cycle["end_day"])))

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

    def _add_season(self) -> None:
        """Add a new season to the table."""
        row = self.seasons_table.rowCount()
        self.seasons_table.insertRow(row)
        self.seasons_table.setItem(row, 0, QTableWidgetItem(f"Season {row + 1}"))
        self.seasons_table.setItem(row, 1, QTableWidgetItem("1"))
        self.seasons_table.setItem(row, 2, QTableWidgetItem("1"))
        self.seasons_table.setItem(row, 3, QTableWidgetItem("1"))
        self.seasons_table.setItem(row, 4, QTableWidgetItem("1"))

    def _remove_season(self) -> None:
        """Remove the selected season from the table."""
        current_row = self.seasons_table.currentRow()
        if current_row >= 0:
            self.seasons_table.removeRow(current_row)

    def _add_lunar_cycle(self) -> None:
        """Add a new lunar cycle to the table."""
        row = self.lunar_cycles_table.rowCount()
        self.lunar_cycles_table.insertRow(row)
        self.lunar_cycles_table.setItem(row, 0, QTableWidgetItem(f"Cycle {row + 1}"))
        self.lunar_cycles_table.setItem(row, 1, QTableWidgetItem("1"))
        self.lunar_cycles_table.setItem(row, 2, QTableWidgetItem("1"))
        self.lunar_cycles_table.setItem(row, 3, QTableWidgetItem("1"))
        self.lunar_cycles_table.setItem(row, 4, QTableWidgetItem("1"))

    def _remove_lunar_cycle(self) -> None:
        """Remove the selected lunar cycle from the table."""
        current_row = self.lunar_cycles_table.currentRow()
        if current_row >= 0:
            self.lunar_cycles_table.removeRow(current_row)

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

            # Collect seasons
            seasons = []
            for row in range(self.seasons_table.rowCount()):
                name_item = self.seasons_table.item(row, 0)
                start_month_item = self.seasons_table.item(row, 1)
                start_day_item = self.seasons_table.item(row, 2)
                end_month_item = self.seasons_table.item(row, 3)
                end_day_item = self.seasons_table.item(row, 4)

                if name_item and start_month_item and start_day_item and end_month_item and end_day_item:
                    seasons.append({
                        "name": name_item.text().strip(),
                        "start_month": int(start_month_item.text().strip()),
                        "start_day": int(start_day_item.text().strip()),
                        "end_month": int(end_month_item.text().strip()),
                        "end_day": int(end_day_item.text().strip())
                    })

            # Collect lunar cycles
            lunar_cycles = []
            for row in range(self.lunar_cycles_table.rowCount()):
                name_item = self.lunar_cycles_table.item(row, 0)
                start_month_item = self.lunar_cycles_table.item(row, 1)
                start_day_item = self.lunar_cycles_table.item(row, 2)
                end_month_item = self.lunar_cycles_table.item(row, 3)
                end_day_item = self.lunar_cycles_table.item(row, 4)

                if name_item and start_month_item and start_day_item and end_month_item and end_day_item:
                    lunar_cycles.append({
                        "name": name_item.text().strip(),
                        "start_month": int(start_month_item.text().strip()),
                        "start_day": int(start_day_item.text().strip()),
                        "end_month": int(end_month_item.text().strip()),
                        "end_day": int(end_day_item.text().strip())
                    })

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
                "leap_year_rule": "none",
                "seasons": seasons,
                "lunar_cycles": lunar_cycles
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
