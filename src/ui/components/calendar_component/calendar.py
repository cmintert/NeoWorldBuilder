from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import json

@dataclass
class CalendarDate:
    year: int
    month: int
    day: int
    weekday: int

class CalendarHandler:
    """Handles calendar operations for custom calendar systems."""

    def __init__(self, calendar_data: Dict[str, Any]):
        """
        Initialize calendar handler with calendar configuration.

        Args:
            calendar_data: Dictionary containing calendar configuration
        """
        self.validate_calendar_data(calendar_data)
        self.calendar_data = calendar_data
        self._build_month_lookup()

    def _build_month_lookup(self) -> None:
        """Build lookup tables for quick date calculations."""
        self.days_before_month = [0]  # Days before each month starts
        total = 0
        for month in self.calendar_data['months']:
            self.days_before_month.append(total + month['days'])
            total += month['days']

    def validate_calendar_data(self, data: Dict[str, Any]) -> None:
        """
        Validate calendar configuration data.

        Args:
            data: Calendar configuration to validate

        Raises:
            ValueError: If calendar configuration is invalid
        """
        required_fields = [
            'calendar_type', 'epoch_name', 'current_year',
            'year_length', 'months', 'days_per_week', 'weekday_names'
        ]

        # Check required fields
        for field in required_fields:
            if field not in data:
                raise ValueError(f"Missing required field: {field}")

        # Validate year length matches total month days
        total_days = sum(month['days'] for month in data['months'])
        if total_days != data['year_length']:
            raise ValueError(
                f"Total month days ({total_days}) must match year length ({data['year_length']})"
            )

        # Validate weekday names match days_per_week
        if len(data['weekday_names']) != data['days_per_week']:
            raise ValueError("Number of weekday names must match days per week")

        # Validate special dates
        if 'special_dates' in data:
            for date in data['special_dates']:
                if date['month'] > len(data['months']):
                    raise ValueError(f"Invalid month in special date: {date['name']}")
                month_length = data['months'][date['month'] - 1]['days']
                if date['day'] > month_length:
                    raise ValueError(
                        f"Invalid day in special date: {date['name']}"
                    )

    def date_to_daynum(self, date: CalendarDate) -> int:
        """
        Convert a calendar date to a day number (days since epoch).

        Args:
            date: CalendarDate object

        Returns:
            int: Number of days since epoch
        """
        days = (date.year - 1) * self.calendar_data['year_length']
        days += self.days_before_month[date.month - 1]
        days += date.day
        return days

    def daynum_to_date(self, daynum: int) -> CalendarDate:
        """
        Convert a day number to a calendar date.

        Args:
            daynum: Number of days since epoch

        Returns:
            CalendarDate: Corresponding calendar date
        """
        year = (daynum - 1) // self.calendar_data['year_length'] + 1
        days_remaining = daynum - (year - 1) * self.calendar_data['year_length']

        # Find month
        month = 1
        while month < len(self.days_before_month) and self.days_before_month[month] < days_remaining:
            month += 1
        month -= 1

        day = days_remaining - self.days_before_month[month]
        weekday = (daynum - 1) % self.calendar_data['days_per_week']

        return CalendarDate(year, month, day, weekday)

    def format_date(self, date: CalendarDate, include_weekday: bool = True) -> str:
        """
        Format a calendar date as a string.

        Args:
            date: CalendarDate to format
            include_weekday: Whether to include weekday name

        Returns:
            str: Formatted date string
        """
        month_name = self.calendar_data['months'][date.month - 1]['name']
        if include_weekday:
            weekday_name = self.calendar_data['weekday_names'][date.weekday]
            return f"{weekday_name}, {date.day} {month_name}, {date.year} {self.calendar_data['epoch_name']}"
        return f"{date.day} {month_name}, {date.year} {self.calendar_data['epoch_name']}"

    def get_special_dates(self, year: int) -> List[Tuple[str, CalendarDate]]:
        """
        Get all special dates for a given year.

        Args:
            year: Year to get special dates for

        Returns:
            List[Tuple[str, CalendarDate]]: List of (event name, date) tuples
        """
        special_dates = []
        for event in self.calendar_data.get('special_dates', []):
            date = CalendarDate(
                year=year,
                month=event['month'],
                day=event['day'],
                weekday=self.get_weekday(year, event['month'], event['day'])
            )
            special_dates.append((event['name'], date))
        return special_dates

    def get_weekday(self, year: int, month: int, day: int) -> int:
        """
        Calculate weekday for a given date.

        Args:
            year: Year
            month: Month
            day: Day

        Returns:
            int: Weekday index (0-based)
        """
        date = CalendarDate(year, month, day, 0)
        daynum = self.date_to_daynum(date)
        return (daynum - 1) % self.calendar_data['days_per_week']

    def add_days(self, date: CalendarDate, days: int) -> CalendarDate:
        """
        Add days to a date.

        Args:
            date: Starting date
            days: Number of days to add (can be negative)

        Returns:
            CalendarDate: Resulting date
        """
        daynum = self.date_to_daynum(date)
        new_daynum = daynum + days
        return self.daynum_to_date(new_daynum)

    def days_between(self, date1: CalendarDate, date2: CalendarDate) -> int:
        """
        Calculate days between two dates.

        Args:
            date1: First date
            date2: Second date

        Returns:
            int: Number of days between dates (positive if date2 is later)
        """
        days1 = self.date_to_daynum(date1)
        days2 = self.date_to_daynum(date2)
        return days2 - days1