import pytest
from PyQt6.QtWidgets import QApplication, QTableWidgetItem, QMessageBox

from ui.components.calendar_component.calendar_config_dialog import CalendarConfigDialog


# Fixture for QApplication instance
@pytest.fixture(scope="session")
def qapp():
    app = QApplication([])
    yield app
    app.quit()


# Fixture for default calendar data
@pytest.fixture
def default_calendar_data():
    return {
        "calendar_type": "custom",
        "epoch_names": ["Ano domini"],
        "epoch_abbreviations": ["AD"],
        "epoch_start_years": [0],
        "epoch_end_years": [99999],
        "current_year": 1,
        "year_length": 30,  # Changed to match total month days
        "month_names": ["Month 1"],  # Simplified to one month for testing
        "month_days": [30],  # One month of 30 days
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


# Fixture for dialog instance
@pytest.fixture
def dialog(qapp, default_calendar_data):
    return CalendarConfigDialog(calendar_data=default_calendar_data)


class TestCalendarConfigDialog:
    def test_initialization_with_default_data(self, dialog, default_calendar_data):
        """Test that dialog initializes correctly with default data"""
        assert dialog.calendar_data == default_calendar_data
        assert dialog.current_year.value() == default_calendar_data["current_year"]
        assert dialog.year_length.value() == default_calendar_data["year_length"]
        assert dialog.days_per_week.value() == default_calendar_data["days_per_week"]

    def test_initialization_without_data(self, qapp):
        """Test that dialog initializes correctly without data"""
        dialog = CalendarConfigDialog()
        assert dialog.calendar_data is not None
        assert dialog.calendar_data["calendar_type"] == "custom"
        assert len(dialog.calendar_data["month_names"]) == 1
        assert len(dialog.calendar_data["weekday_names"]) == 7

        # Make year length match month days
        dialog.year_length.setValue(30)  # Set to match the single month's days

        # Verify the data we can collect is valid
        try:
            collected_data = dialog.get_calendar_data()
            assert collected_data["year_length"] == 30
            assert sum(collected_data["month_days"]) == collected_data["year_length"]
        except ValueError as e:
            pytest.fail(f"Failed to validate calendar data: {str(e)}")

    def test_add_epoch(self, dialog):
        """Test adding a new epoch"""
        initial_rows = dialog.epochs_table.rowCount()
        dialog._add_epoch()

        assert dialog.epochs_table.rowCount() == initial_rows + 1
        assert dialog.epochs_table.item(initial_rows, 0).text() == "New Epoch"
        assert dialog.epochs_table.item(initial_rows, 1).text() == "NE"
        assert dialog.epochs_table.item(initial_rows, 2).text() == "0"
        assert dialog.epochs_table.item(initial_rows, 3).text() == "99999"

    def test_remove_epoch(self, dialog):
        """Test removing an epoch"""
        initial_rows = dialog.epochs_table.rowCount()
        dialog.epochs_table.selectRow(0)
        dialog._remove_epoch()
        assert dialog.epochs_table.rowCount() == initial_rows - 1

    def test_add_month(self, dialog):
        """Test adding a new month"""
        initial_rows = dialog.months_table.rowCount()
        dialog._add_month()

        assert dialog.months_table.rowCount() == initial_rows + 1
        assert (
            dialog.months_table.item(initial_rows, 0).text()
            == f"Month {initial_rows + 1}"
        )
        assert dialog.months_table.item(initial_rows, 1).text() == "30"

    def test_remove_month(self, dialog):
        """Test removing a month"""
        initial_rows = dialog.months_table.rowCount()
        dialog.months_table.selectRow(0)
        dialog._remove_month()
        assert dialog.months_table.rowCount() == initial_rows - 1

    def test_update_weekday_table(self, dialog):
        """Test updating weekday table when days per week changes"""
        dialog.days_per_week.setValue(5)  # Change to 5 days
        assert dialog.weekday_table.rowCount() == 5

        # Check all rows have default names
        for i in range(5):
            assert dialog.weekday_table.item(i, 0).text() == f"Day {i + 1}"

    def test_get_calendar_data_validation(self, dialog, monkeypatch):
        """Test calendar data validation"""
        # Mock QMessageBox.critical
        monkeypatch.setattr(QMessageBox, "critical", lambda *args, **kwargs: None)

        # Rest of the test remains the same
        dialog.year_length.setValue(360)
        dialog.months_table.setRowCount(1)
        dialog.months_table.setItem(0, 0, QTableWidgetItem("Month 1"))
        dialog.months_table.setItem(0, 1, QTableWidgetItem("30"))

        with pytest.raises(ValueError) as exc_info:
            dialog.get_calendar_data()
        assert "Total days in months (30) does not match year length (360)" in str(
            exc_info.value
        )

    def test_valid_calendar_data_collection(self, dialog):
        """Test collecting valid calendar data"""
        # Setup valid data where month days sum equals year length
        dialog.year_length.setValue(30)  # Set year length

        # Clear existing months and add one month
        while dialog.months_table.rowCount() > 0:
            dialog.months_table.removeRow(0)

        dialog._add_month()  # This adds one month with 30 days

        collected_data = dialog.get_calendar_data()
        assert collected_data["calendar_type"] == "custom"
        assert len(collected_data["month_names"]) == 1
        assert collected_data["month_days"] == [30]
        assert collected_data["year_length"] == 30
        assert sum(collected_data["month_days"]) == collected_data["year_length"]
        assert len(collected_data["weekday_names"]) == collected_data["days_per_week"]

    def test_epoch_data_validation(self, dialog, monkeypatch):
        """Test validation of epoch year values"""
        # Mock QMessageBox.critical
        monkeypatch.setattr(QMessageBox, "critical", lambda *args, **kwargs: None)

        # Rest of the test remains the same
        row = dialog.epochs_table.rowCount()
        dialog.epochs_table.insertRow(row)
        dialog.epochs_table.setItem(row, 0, QTableWidgetItem("Test Epoch"))
        dialog.epochs_table.setItem(row, 1, QTableWidgetItem("TE"))
        dialog.epochs_table.setItem(row, 2, QTableWidgetItem("invalid"))
        dialog.epochs_table.setItem(row, 3, QTableWidgetItem("100"))

        with pytest.raises(ValueError) as exc_info:
            dialog.get_calendar_data()
        assert "Invalid year value" in str(exc_info.value)
