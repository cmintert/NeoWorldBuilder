import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtTest import QTest
from unittest.mock import MagicMock, patch

from ui.components.calendar_component.calendar_tab import CalendarTab


# Fixture for QApplication instance
@pytest.fixture(scope="session")
def qapp():
    app = QApplication([])
    yield app
    app.quit()


# Fixture for a mock controller
@pytest.fixture
def mock_controller():
    controller = MagicMock()
    controller.config = {}
    return controller


# Fixture for CalendarTab instance
@pytest.fixture
def calendar_tab(qapp, mock_controller):
    return CalendarTab(controller=mock_controller)


class TestCalendarTab:
    def test_initialization(self, calendar_tab):
        """Test that CalendarTab initializes correctly"""
        assert calendar_tab is not None
        assert calendar_tab.calendar_data is None
        assert calendar_tab.config_btn.text() == "⚙️ Configure Calendar"
        assert calendar_tab.save_btn.text() == "💾 Save Calendar"

    def test_set_calendar_data_valid(self, calendar_tab):
        """Test setting valid calendar data"""
        test_data = {
            "epoch_names": "['First', 'Second']",
            "epoch_abbreviations": "['1st', '2nd']",
            "epoch_start_years": "[0, 100]",
            "epoch_end_years": "[99, 199]",
        }

        calendar_tab.set_calendar_data(test_data)

        # Check transformed data
        assert isinstance(calendar_tab.calendar_data["epoch_names"], list)
        assert calendar_tab.calendar_data["epoch_names"] == ["First", "Second"]
        assert calendar_tab.calendar_data["epoch_abbreviations"] == ["1st", "2nd"]
        assert calendar_tab.calendar_data["epoch_start_years"] == [0, 100]
        assert calendar_tab.calendar_data["epoch_end_years"] == [99, 199]

    def test_set_calendar_data_empty(self, calendar_tab):
        """Test setting empty calendar data"""
        calendar_tab.set_calendar_data({})
        assert calendar_tab.calendar_data is None

    @patch("PyQt6.QtWidgets.QMessageBox.critical")
    def test_set_calendar_data_invalid(self, mock_critical, calendar_tab):
        """Test setting invalid calendar data"""
        invalid_data = {"epoch_start_years": "[invalid]"}

        calendar_tab.set_calendar_data(invalid_data)
        mock_critical.assert_called_once()

    def test_save_calendar_config_no_data(self, calendar_tab):
        """Test saving when no calendar data exists"""
        with patch("PyQt6.QtWidgets.QMessageBox.warning") as mock_warning:
            calendar_tab.calendar_data = None
            calendar_tab._save_calendar_config()
            mock_warning.assert_called_once()

    def test_save_calendar_config_success(self, calendar_tab):
        """Test successful calendar config save"""
        test_data = {"name": "test_calendar"}
        calendar_tab.calendar_data = test_data

        # Create a spy for the calendar_changed signal
        with patch("PyQt6.QtWidgets.QMessageBox.information") as mock_info:
            calendar_tab._save_calendar_config()
            mock_info.assert_called_once()

    def test_calendar_changed_signal(self, calendar_tab):
        """Test that the calendar_changed signal is emitted correctly"""
        test_data = {"name": "test_calendar"}

        # Create a signal spy
        signal_received = []
        calendar_tab.calendar_changed.connect(lambda x: signal_received.append(x))

        # Set calendar data which should emit the signal
        calendar_tab.set_calendar_data(test_data)

        assert len(signal_received) == 1
        assert signal_received[0] == test_data

    @patch("calendar_tab.CalendarConfigDialog")
    def test_show_calendar_config_accepted(self, mock_dialog, calendar_tab):
        """Test calendar configuration dialog when accepted"""
        # Setup mock dialog
        dialog_instance = MagicMock()
        dialog_instance.exec.return_value = True
        dialog_instance.get_calendar_data.return_value = {"name": "test_calendar"}
        mock_dialog.return_value = dialog_instance

        # Show dialog
        calendar_tab._show_calendar_config()

        # Verify dialog was shown and data was updated
        dialog_instance.exec.assert_called_once()
        dialog_instance.get_calendar_data.assert_called_once()
        assert calendar_tab.calendar_data == {"name": "test_calendar"}

    @patch("calendar_tab.CalendarConfigDialog")
    def test_show_calendar_config_cancelled(self, mock_dialog, calendar_tab):
        """Test calendar configuration dialog when cancelled"""
        # Setup mock dialog
        dialog_instance = MagicMock()
        dialog_instance.exec.return_value = False
        mock_dialog.return_value = dialog_instance

        # Store original calendar data
        original_data = calendar_tab.calendar_data

        # Show dialog
        calendar_tab._show_calendar_config()

        # Verify dialog was shown but data wasn't updated
        dialog_instance.exec.assert_called_once()
        dialog_instance.get_calendar_data.assert_not_called()
        assert calendar_tab.calendar_data == original_data

    def test_transform_calendar_data(self, calendar_tab):
        """Test calendar data transformation"""
        input_data = {
            "epoch_names": "[First, Second]",
            "epoch_abbreviations": "[1st, 2nd]",
            "epoch_start_years": "[0, 100]",
            "epoch_end_years": "[99, 199]",
            "other_field": "value",
        }

        result = calendar_tab._transform_calendar_data(input_data)

        assert isinstance(result["epoch_names"], list)
        assert isinstance(result["epoch_start_years"], list)
        assert result["epoch_names"] == ["First", "Second"]
        assert result["epoch_start_years"] == [0, 100]
        assert (
            result["other_field"] == "value"
        )  # Non-list field should remain unchanged
