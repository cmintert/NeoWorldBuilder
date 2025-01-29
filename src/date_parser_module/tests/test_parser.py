import pytest
from typing import Dict, Any

from date_parser_module.dateparser import DateParser, ParsedDate, DatePrecision


@pytest.fixture
def standard_calendar() -> Dict[str, Any]:
    """Standard calendar fixture for testing"""
    return {
        "calendar_type": "custom",
        "epoch_name": "Third Age",
        "current_year": 3019,
        "year_length": 365,
        "month_names": [
            "Wintermarch",
            "Springtide",
            "Summerday",
            "Harvest Moon",
            "Fallmist",
            "Deepwinter",
        ],
        "month_days": [60, 60, 61, 62, 61, 61],
        "days_per_week": 7,
        "weekday_names": [
            "Starday",
            "Sunday",
            "Moonday",
            "Tidesday",
            "Windsday",
            "Earthday",
            "Freeday",
        ],
    }


@pytest.fixture
def fantasy_calendar() -> Dict[str, Any]:
    """Fantasy calendar fixture with unusual structure"""
    return {
        "calendar_type": "custom",
        "epoch_name": "Age of Stars",
        "current_year": 1242,
        "year_length": 300,
        "month_names": [
            "First Moon",
            "Second Moon",
            "Third Moon",
            "Fourth Moon",
            "Fifth Moon",
        ],
        "month_days": [60, 60, 60, 60, 60],
        "days_per_week": 5,
        "weekday_names": ["Moonrise", "Starfall", "Twilight", "Dawnbreak", "Nightfall"],
    }


class TestCalendarValidation:
    """Test calendar configuration validation"""

    def test_invalid_calendar_config(self):
        """Test validation of invalid calendar configurations"""
        invalid_configs = [
            # Missing required fields
            {"month_names": [], "month_days": []},
            # Mismatched month names and days
            {
                "month_names": ["Month1", "Month2"],
                "month_days": [30],
                "days_per_week": 7,
                "weekday_names": ["1", "2", "3", "4", "5", "6", "7"],
                "year_length": 30,
            },
            # Invalid year length
            {
                "month_names": ["Month1", "Month2"],
                "month_days": [30, 31],
                "days_per_week": 7,
                "weekday_names": ["1", "2", "3", "4", "5", "6", "7"],
                "year_length": 70,  # Should be 61
            },
        ]

        for config in invalid_configs:
            with pytest.raises(ValueError):
                DateParser(config)


class TestExactDateParsing:
    """Test exact date parsing with various formats"""

    def test_standard_formats(self, standard_calendar):
        parser = DateParser(standard_calendar)

        test_cases = [
            # Standard format
            ("3rd day of Harvest Moon, 3019", ParsedDate(year=3019, month=4, day=3)),
            # Abbreviated format
            ("5 Wintermarch 3019", ParsedDate(year=3019, month=1, day=5)),
            # Full formal format
            (
                "The 15th day of Springtide, 3019",
                ParsedDate(year=3019, month=2, day=15),
            ),
            # Day with different suffixes
            ("1st Summerday 3019", ParsedDate(year=3019, month=3, day=1)),
            ("2nd Summerday 3019", ParsedDate(year=3019, month=3, day=2)),
            ("3rd Summerday 3019", ParsedDate(year=3019, month=3, day=3)),
            ("4th Summerday 3019", ParsedDate(year=3019, month=3, day=4)),
        ]

        for input_str, expected in test_cases:
            result = parser.parse_date(input_str)
            assert result.year == expected.year
            assert result.month == expected.month
            assert result.day == expected.day
            assert result.precision == DatePrecision.EXACT

    def test_case_insensitivity(self, standard_calendar):
        parser = DateParser(standard_calendar)
        test_cases = [
            "3rd DAY OF HARVEST MOON, 3019",
            "3rd day of Harvest Moon, 3019",
            "3RD DAY OF harvest MOON, 3019",
        ]
        expected = ParsedDate(year=3019, month=4, day=3)

        for input_str in test_cases:
            result = parser.parse_date(input_str)
            assert result.year == expected.year
            assert result.month == expected.month
            assert result.day == expected.day

    def test_exact_dates_with_weekdays(self, standard_calendar):
        parser = DateParser(standard_calendar)

        test_cases = [
            # With weekday names
            (
                "Starday, 3rd day of Harvest Moon, 3019",
                ParsedDate(year=3019, month=4, day=3),
            ),
            ("Sunday, 5 Wintermarch 3019", ParsedDate(year=3019, month=1, day=5)),
            (
                "Moonday, The 15th day of Springtide, 3019",
                ParsedDate(year=3019, month=2, day=15),
            ),
            (
                "Tidesday 1st Summerday 3019",
                ParsedDate(year=3019, month=3, day=1),
            ),  # No comma after weekday
            ("Windsday, 2nd Summerday 3019", ParsedDate(year=3019, month=3, day=2)),
            (
                "Earthday 3rd Summerday, 3019",
                ParsedDate(year=3019, month=3, day=3),
            ),  # Comma after day, not weekday
            ("Freeday, 4th Summerday 3019", ParsedDate(year=3019, month=3, day=4)),
            # Weekday with Month Day Year style
            ("Starday, Wintermarch 15, 3019", ParsedDate(year=3019, month=1, day=15)),
            ("Sunday, Springtide the 2nd, 3019", ParsedDate(year=3019, month=2, day=2)),
            # Weekday with Day Month Year style
            ("Moonday, 15 Wintermarch 3019", ParsedDate(year=3019, month=1, day=15)),
            ("Tidesday, 2nd Springtide 3019", ParsedDate(year=3019, month=2, day=2)),
        ]

        for input_str, expected in test_cases:
            result = parser.parse_date(input_str)
            assert result.year == expected.year
            assert result.month == expected.month
            assert result.day == expected.day
            assert result.precision == DatePrecision.EXACT


class TestPartialDates:
    """Test parsing of partial dates"""

    def test_month_year(self, standard_calendar):
        parser = DateParser(standard_calendar)

        test_cases = [
            (
                "Harvest Moon 3019",
                ParsedDate(year=3019, month=4, precision=DatePrecision.MONTH),
            ),
            (
                "In Wintermarch 3019",
                ParsedDate(year=3019, month=1, precision=DatePrecision.MONTH),
            ),
            (
                "The month of Springtide, 3019",
                ParsedDate(year=3019, month=2, precision=DatePrecision.MONTH),
            ),
        ]

        for input_str, expected in test_cases:
            result = parser.parse_date(input_str)
            assert result.year == expected.year
            assert result.month == expected.month
            assert result.precision == DatePrecision.MONTH

    def test_year_only(self, standard_calendar):
        parser = DateParser(standard_calendar)

        test_cases = [
            ("Year 3019", ParsedDate(year=3019, precision=DatePrecision.YEAR)),
            ("In 3019", ParsedDate(year=3019, precision=DatePrecision.YEAR)),
            (
                "During the year 3019",
                ParsedDate(year=3019, precision=DatePrecision.YEAR),
            ),
            ("Year 30", ParsedDate(year=30, precision=DatePrecision.YEAR)),
        ]

        for input_str, expected in test_cases:
            result = parser.parse_date(input_str)
            assert result.year == expected.year
            assert result.precision == DatePrecision.YEAR


class TestSeasonalDates:
    """Test parsing of season-based dates"""

    def test_season_parsing(self, standard_calendar):
        parser = DateParser(standard_calendar)

        test_cases = [
            (
                "Early spring 3019",
                ParsedDate(year=3019, season="spring", precision=DatePrecision.SEASON),
            ),
            (
                "Mid summer 3019",
                ParsedDate(year=3019, season="summer", precision=DatePrecision.SEASON),
            ),
            (
                "Late harvest 3019",
                ParsedDate(year=3019, season="harvest", precision=DatePrecision.SEASON),
            ),
            (
                "Winter 3019",
                ParsedDate(year=3019, season="winter", precision=DatePrecision.SEASON),
            ),
        ]

        for input_str, expected in test_cases:
            result = parser.parse_date(input_str)
            assert result.year == expected.year
            assert result.season == expected.season
            assert result.precision == DatePrecision.SEASON


class TestRelativeDates:
    """Test parsing of relative dates"""

    def test_relative_dates(self, standard_calendar):
        parser = DateParser(standard_calendar)

        test_cases = [
            (
                "2 days after Battle of Hornburg",
                ParsedDate(
                    year=3019,
                    relative_days=2,
                    relative_to="battle of hornburg",
                    precision=DatePrecision.RELATIVE,
                ),
            ),
            (
                "5 days before Midsummer Festival",
                ParsedDate(
                    year=3019,
                    relative_days=-5,
                    relative_to="midsummer festival",
                    precision=DatePrecision.RELATIVE,
                ),
            ),
            (
                "During the Siege",
                ParsedDate(
                    year=3019,
                    relative_days=0,
                    relative_to="the siege",
                    precision=DatePrecision.RELATIVE,
                ),
            ),
        ]

        for input_str, expected in test_cases:
            result = parser.parse_date(input_str)
            assert result.precision == DatePrecision.RELATIVE
            assert result.relative_days == expected.relative_days
            assert result.relative_to == expected.relative_to


class TestFuzzyDates:
    """Test parsing of fuzzy/approximate dates"""

    def test_approximate_dates(self, standard_calendar):
        parser = DateParser(standard_calendar)

        test_cases = [
            (
                "Around Harvest Moon 3019",
                ParsedDate(
                    year=3019, month=4, precision=DatePrecision.FUZZY, confidence=0.8
                ),
            ),
            (
                "Approximately 15 Wintermarch 3019",
                ParsedDate(
                    year=3019,
                    month=1,
                    day=15,
                    precision=DatePrecision.FUZZY,
                    confidence=0.8,
                ),
            ),
            (
                "Sometime during 3019",
                ParsedDate(year=3019, precision=DatePrecision.FUZZY, confidence=0.5),
            ),
        ]

        for input_str, expected in test_cases:
            result = parser.parse_date(input_str)
            assert result.year == expected.year
            assert result.precision == DatePrecision.FUZZY
            assert result.confidence < 1.0


class TestDateRanges:
    """Test parsing of date ranges"""

    def test_date_ranges(self, standard_calendar):
        parser = DateParser(standard_calendar)

        test_cases = [
            (
                "Between Harvest Moon and Wintermarch 3019",
                ParsedDate(
                    year=3019,
                    precision=DatePrecision.RANGE,
                    range_start=ParsedDate(
                        year=3019, month=4, precision=DatePrecision.MONTH
                    ),
                    range_end=ParsedDate(
                        year=3019, month=1, precision=DatePrecision.MONTH
                    ),
                ),
            ),
            (
                "From 1st to 15th Summerday 3019",
                ParsedDate(
                    year=3019,
                    precision=DatePrecision.RANGE,
                    range_start=ParsedDate(year=3019, month=3, day=1),
                    range_end=ParsedDate(year=3019, month=3, day=15),
                ),
            ),
        ]

        for input_str, expected in test_cases:
            result = parser.parse_date(input_str)
            assert result.precision == DatePrecision.RANGE
            assert result.range_start is not None
            assert result.range_end is not None


class TestEdgeCases:
    """Test edge cases and error handling"""

    def test_invalid_inputs(self, standard_calendar):
        parser = DateParser(standard_calendar)

        invalid_cases = [
            "",  # Empty string
            "not a date",  # Nonsense input
            "99th day of Nonexistent, 3019",  # Invalid month
            "0 Wintermarch 3019",  # Invalid day
            "-1 Wintermarch 3019",  # Negative day
            "61 Wintermarch 3019",  # Day beyond month length
        ]

        for input_str in invalid_cases:
            with pytest.raises(ValueError):
                parser.parse_date(input_str)

    def test_boundary_conditions(self, standard_calendar):
        parser = DateParser(standard_calendar)

        # Test first and last days of months
        test_cases = [
            ("1 Wintermarch 3019", ParsedDate(year=3019, month=1, day=1)),
            (f"60 Wintermarch 3019", ParsedDate(year=3019, month=1, day=60)),
            ("1 Deepwinter 3019", ParsedDate(year=3019, month=6, day=1)),
            (f"61 Deepwinter 3019", ParsedDate(year=3019, month=6, day=61)),
        ]

        for input_str, expected in test_cases:
            result = parser.parse_date(input_str)
            assert result.year == expected.year
            assert result.month == expected.month
            assert result.day == expected.day

    def test_robust_error_handling(self, standard_calendar):
        """Test parser's ability to handle 'creative' user input"""
        parser = DateParser(standard_calendar)

        problematic_inputs = [
            # Nonsensical inputs
            "tomorrow",
            "yesterday",
            "next week",
            "idk maybe last week?",
            "when the moon is blue",
            "January Wintermarch 3019",
            "31st of December, 3019",
            # Wrong spelling/typos
            "Wintermarche 3019",
            "Sprointide 3019",
            "Harvist Moon 3019",
            # Extra punctuation and symbols blocking parsing
            "***Harvest Moon*** 3019",
            # Wrong separators blocking parsing
            "15/Wintermarch/3019",
            "15-Wintermarch-3019",
            # Completely unstructured inputs
            "15WintermarchMoon3019",
            # Numbers as words (not supported)
            "first of Wintermarch 3019",
            "second day of Harvest Moon 3019",
            # Emoji or special character interference
            "15th 🌙 Harvest Moon 🌙 3019",
            # Vague or imprecise ranges
            "from beginning to end of Wintermarch",
            "somewhere between Harvest and Winter",
            # Invalid day ranges or unclear ranges
            "maybe from 1st to 99th Wintermarch",
            # Unicode character inputs
            "１５ｔｈ Ｗｉｎｔｅｒｍａｒｃｈ ３０１９",
            # HTML-like or potentially malicious inputs
            "<script>alert('15th Wintermarch 3019')</script>",
        ]

        for bad_input in problematic_inputs:
            with pytest.raises(ValueError) as exc_info:
                parser.parse_date(bad_input)
            assert "Could not parse date:" in str(
                exc_info.value
            ), f"Should raise appropriate ValueError for: {bad_input}"

        # Test that the parser recovers after bad inputs
        valid_date = "15th Wintermarch 3019"
        result = parser.parse_date(valid_date)
        assert result.year == 3019
        assert result.month == 1
        assert result.day == 15

    class TestJsonSerialization:
        """Test JSON serialization and deserialization of ParsedDate objects"""

        def test_to_json_exact_date(self, standard_calendar):
            parser = DateParser(standard_calendar)
            parsed_date = ParsedDate(year=3019, month=1, day=15)
            json_output = parser.to_json(parsed_date)
            expected_json = {
                "year": 3019,
                "month": 1,
                "day": 15,
                "precision": "EXACT",
                "relative_to": None,
                "relative_days": None,
                "confidence": 1.0,
                "season": None,
                "range_start": None,
                "range_end": None,
            }
            assert json_output == expected_json

        def test_to_json_month_year_date(self, standard_calendar):
            parser = DateParser(standard_calendar)
            parsed_date = ParsedDate(year=3019, month=4, precision=DatePrecision.MONTH)
            json_output = parser.to_json(parsed_date)
            expected_json = {
                "year": 3019,
                "month": 4,
                "day": None,
                "precision": "MONTH",
                "relative_to": None,
                "relative_days": None,
                "confidence": 1.0,
                "season": None,
                "range_start": None,
                "range_end": None,
            }
            assert json_output == expected_json

        def test_to_json_date_range(self, standard_calendar):
            parser = DateParser(standard_calendar)
            range_start = ParsedDate(year=3019, month=1, day=1)
            range_end = ParsedDate(year=3019, month=1, day=15)
            parsed_date = ParsedDate(
                year=3019,
                precision=DatePrecision.RANGE,
                range_start=range_start,
                range_end=range_end,
            )
            json_output = parser.to_json(parsed_date)
            expected_json = {
                "year": 3019,
                "month": None,
                "day": None,
                "precision": "RANGE",
                "relative_to": None,
                "relative_days": None,
                "confidence": 1.0,
                "season": None,
                "range_start": parser.to_json(
                    range_start
                ),  # Use parser.to_json for nested objects
                "range_end": parser.to_json(
                    range_end
                ),  # Use parser.to_json for nested objects
            }
            assert json_output == expected_json

        def test_from_json_exact_date(self, standard_calendar):
            parser = DateParser(standard_calendar)
            json_data = {
                "year": 3019,
                "month": 1,
                "day": 15,
                "precision": "EXACT",
                "relative_to": None,
                "relative_days": None,
                "confidence": 1.0,
                "season": None,
                "range_start": None,
                "range_end": None,
            }
            parsed_date = parser.from_json(json_data)
            expected_date = ParsedDate(year=3019, month=1, day=15)
            assert (
                parsed_date == expected_date
            )  # Ensure ParsedDate objects are comparable

        def test_from_json_date_range(self, standard_calendar):
            parser = DateParser(standard_calendar)
            json_data = {
                "year": 3019,
                "month": None,
                "day": None,
                "precision": "RANGE",
                "relative_to": None,
                "relative_days": None,
                "confidence": 1.0,
                "season": None,
                "range_start": {  # Nested JSON for range_start
                    "year": 3019,
                    "month": 1,
                    "day": 1,
                    "precision": "EXACT",
                    "relative_to": None,
                    "relative_days": None,
                    "confidence": 1.0,
                    "season": None,
                    "range_start": None,
                    "range_end": None,
                },
                "range_end": {  # Nested JSON for range_end
                    "year": 3019,
                    "month": 1,
                    "day": 15,
                    "precision": "EXACT",
                    "relative_to": None,
                    "relative_days": None,
                    "confidence": 1.0,
                    "season": None,
                    "range_start": None,
                    "range_end": None,
                },
            }
            parsed_date = parser.from_json(json_data)
            expected_range_start = ParsedDate(year=3019, month=1, day=1)
            expected_range_end = ParsedDate(year=3019, month=1, day=15)
            expected_date = ParsedDate(
                year=3019,
                precision=DatePrecision.RANGE,
                range_start=expected_range_start,
                range_end=expected_range_end,
            )
            assert (
                parsed_date == expected_date
            )  # Ensure ParsedDate objects are comparable

        def test_year_formats(self, standard_calendar):
            parser = DateParser(standard_calendar)

            test_cases = [
                # Single digit year
                ("15 Wintermarch 5", ParsedDate(year=5, month=1, day=15)),
                # Two digit year
                ("15 Wintermarch 42", ParsedDate(year=42, month=1, day=15)),
                # Three digit year
                ("15 Wintermarch 342", ParsedDate(year=342, month=1, day=15)),
                # Four digit year
                ("15 Wintermarch 3019", ParsedDate(year=3019, month=1, day=15)),
            ]

            for input_str, expected in test_cases:
                result = parser.parse_date(input_str)
                assert result.year == expected.year
                assert result.month == expected.month
                assert result.day == expected.day


if __name__ == "__main__":
    pytest.main([__file__])
