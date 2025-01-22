import pytest
from typing import Dict, Any
from ui.components.calendar_component.calendar import CalendarHandler, CalendarDate


@pytest.fixture
def sample_calendar_data() -> Dict[str, Any]:
    return {
        "calendar_type": "standard",
        "epoch_name": "CE",
        "current_year": 2025,
        "year_length": 365,
        "months": [
            {"name": "January", "days": 31},
            {"name": "February", "days": 28},
            {"name": "March", "days": 31},
            {"name": "April", "days": 30},
            {"name": "May", "days": 31},
            {"name": "June", "days": 30},
            {"name": "July", "days": 31},
            {"name": "August", "days": 31},
            {"name": "September", "days": 30},
            {"name": "October", "days": 31},
            {"name": "November", "days": 30},
            {"name": "December", "days": 31},
        ],
        "days_per_week": 7,
        "weekday_names": [
            "Monday",
            "Tuesday",
            "Wednesday",
            "Thursday",
            "Friday",
            "Saturday",
            "Sunday",
        ],
        "special_dates": [
            {"name": "New Year's Day", "month": 1, "day": 1},
            {"name": "Christmas", "month": 12, "day": 25},
        ],
    }


@pytest.fixture
def calendar_handler(sample_calendar_data):
    return CalendarHandler(sample_calendar_data)


def test_validate_calendar_data_valid(sample_calendar_data):
    handler = CalendarHandler(sample_calendar_data)
    assert handler.calendar_data == sample_calendar_data


def test_validate_calendar_data_missing_field():
    invalid_data = {
        "calendar_type": "standard",
        # Missing epoch_name and other required fields
    }
    with pytest.raises(ValueError, match="Missing required field:"):
        CalendarHandler(invalid_data)


def test_validate_calendar_data_incorrect_year_length(sample_calendar_data):
    invalid_data = dict(sample_calendar_data)
    invalid_data["year_length"] = 360
    with pytest.raises(ValueError, match="Total month days .* must match year length"):
        CalendarHandler(invalid_data)


def test_validate_calendar_data_invalid_month_days(sample_calendar_data):
    invalid_data = dict(sample_calendar_data)
    invalid_data["months"][0]["days"] = 0  # Invalid number of days
    with pytest.raises(ValueError):
        CalendarHandler(invalid_data)


def test_validate_calendar_data_invalid_weekday_count(sample_calendar_data):
    invalid_data = dict(sample_calendar_data)
    invalid_data["weekday_names"] = ["Monday", "Tuesday"]  # Doesn't match days_per_week
    with pytest.raises(ValueError):
        CalendarHandler(invalid_data)


def test_date_to_day_number(calendar_handler):
    # Start of year
    date = CalendarDate(year=2025, month=1, day=1, weekday=0)
    assert calendar_handler.date_to_day_number(date) == (2024 * 365) + 1

    # End of year
    date = CalendarDate(year=2025, month=12, day=31, weekday=6)
    assert calendar_handler.date_to_day_number(date) == (2024 * 365) + 365

    # Mid-year date
    date = CalendarDate(year=2025, month=7, day=15, weekday=2)
    expected_days = (2024 * 365) + calendar_handler.days_before_month[6] + 15
    assert calendar_handler.date_to_day_number(date) == expected_days

    # First year of calendar
    date = CalendarDate(year=1, month=1, day=1, weekday=0)
    assert calendar_handler.date_to_day_number(date) == 1


def test_day_number_to_date(calendar_handler):
    # Start of year
    date = calendar_handler.day_number_to_date((2024 * 365) + 1)
    assert (date.year, date.month, date.day) == (2025, 1, 1)

    # End of month
    date = calendar_handler.day_number_to_date((2024 * 365) + 31)
    assert (date.year, date.month, date.day) == (2025, 1, 31)

    # Start of next month
    date = calendar_handler.day_number_to_date((2024 * 365) + 32)
    assert (date.year, date.month, date.day) == (2025, 2, 1)

    # End of year
    date = calendar_handler.day_number_to_date((2024 * 365) + 365)
    assert (date.year, date.month, date.day) == (2025, 12, 31)

    # First day of calendar
    date = calendar_handler.day_number_to_date(1)
    assert (date.year, date.month, date.day) == (1, 1, 1)


def test_format_date(calendar_handler):
    # Regular date with weekday
    date = CalendarDate(year=2025, month=1, day=1, weekday=0)
    assert calendar_handler.format_date(date) == "Monday, 1 January, 2025 CE"

    # Without weekday
    assert (
        calendar_handler.format_date(date, include_weekday=False)
        == "1 January, 2025 CE"
    )

    # Different months
    date = CalendarDate(year=2025, month=12, day=25, weekday=3)
    assert calendar_handler.format_date(date) == "Thursday, 25 December, 2025 CE"

    # First year of calendar
    date = CalendarDate(year=1, month=1, day=1, weekday=0)
    assert calendar_handler.format_date(date) == "Monday, 1 January, 1 CE"


def test_get_special_dates(calendar_handler):
    special_dates = calendar_handler.get_special_dates(2025)
    assert len(special_dates) == 2

    # Test New Year's Day
    new_years, christmas = special_dates
    assert new_years[0] == "New Year's Day"
    assert (new_years[1].month, new_years[1].day) == (1, 1)

    # Test Christmas
    assert christmas[0] == "Christmas"
    assert (christmas[1].month, christmas[1].day) == (12, 25)

    # Test different year
    special_dates_2026 = calendar_handler.get_special_dates(2026)
    assert len(special_dates_2026) == 2
    assert all(date[1].year == 2026 for date in special_dates_2026)


def test_get_weekday(calendar_handler):
    # Test start of year
    assert 0 <= calendar_handler.get_weekday(2025, 1, 1) < 7

    # Test end of year
    assert 0 <= calendar_handler.get_weekday(2025, 12, 31) < 7

    # Test mid-year
    assert 0 <= calendar_handler.get_weekday(2025, 6, 15) < 7

    # Test consecutive days
    day1 = calendar_handler.get_weekday(2025, 1, 1)
    day2 = calendar_handler.get_weekday(2025, 1, 2)
    assert (day2 - day1) % 7 == 1


def test_add_days(calendar_handler):
    start_date = CalendarDate(year=2025, month=1, day=1, weekday=0)

    # Add single day
    result = calendar_handler.add_days(start_date, 1)
    assert (result.year, result.month, result.day) == (2025, 1, 2)

    # Add days to next month
    result = calendar_handler.add_days(start_date, 31)
    assert (result.year, result.month, result.day) == (2025, 2, 1)

    # Add days to next year
    result = calendar_handler.add_days(start_date, 365)
    assert (result.year, result.month, result.day) == (2026, 1, 1)

    # Subtract days
    result = calendar_handler.add_days(start_date, -1)
    assert (result.year, result.month, result.day) == (2024, 12, 31)

    # Test large day additions
    result = calendar_handler.add_days(start_date, 1000)
    assert result.year == 2027  # approximately

    # Test large day subtractions
    result = calendar_handler.add_days(start_date, -1000)
    assert result.year == 2022  # approximately


def test_days_between(calendar_handler):
    date1 = CalendarDate(year=2025, month=1, day=1, weekday=0)

    # Same date
    assert calendar_handler.days_between(date1, date1) == 0

    # Next day
    date2 = CalendarDate(year=2025, month=1, day=2, weekday=1)
    assert calendar_handler.days_between(date1, date2) == 1

    # Previous day
    assert calendar_handler.days_between(date2, date1) == -1

    # Month difference
    date3 = CalendarDate(year=2025, month=2, day=1, weekday=3)
    assert calendar_handler.days_between(date1, date3) == 31

    # Year difference
    date4 = CalendarDate(year=2026, month=1, day=1, weekday=1)
    assert calendar_handler.days_between(date1, date4) == 365

    # Multiple years
    date5 = CalendarDate(year=2027, month=6, day=15, weekday=4)
    diff = calendar_handler.days_between(date1, date5)
    assert diff > 365 * 2  # More than 2 years worth of days


def test_cross_year_calculations(calendar_handler):
    # Test December to January transition
    dec31_2024 = CalendarDate(year=2024, month=12, day=31, weekday=6)
    jan1_2025 = CalendarDate(year=2025, month=1, day=1, weekday=0)
    assert calendar_handler.days_between(dec31_2024, jan1_2025) == 1

    # Test full year calculation
    jan1_2024 = CalendarDate(year=2024, month=1, day=1, weekday=0)
    jan1_2025 = CalendarDate(year=2025, month=1, day=1, weekday=0)
    assert calendar_handler.days_between(jan1_2024, jan1_2025) == 365
