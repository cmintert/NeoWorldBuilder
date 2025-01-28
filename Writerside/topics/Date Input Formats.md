User Manual: Date Input Formats for the Custom Date Parser

This document outlines the various date input formats that are accepted by the custom date parser.  This parser is designed to understand dates in a variety of natural language and structured formats, making it flexible for different types of date entries.

**Supported Date Formats**

The date parser can understand the following categories of date formats.  Each category is described below with examples to illustrate valid input strings.

**1. Exact Dates (Day, Month, Year)**

These formats represent specific dates with day, month, and year precision.

*   **"Day Month Year" Format:**
    *   Examples:
        *   `15 Wintermarch 3019`
        *   `5 Springtide 3019`
        *   `30 Summerday 3019`

*   **"Dayth day of Month, Year" Format:** (Using ordinal suffixes for the day)
    *   Examples:
        *   `3rd day of Harvest Moon, 3019`
        *   `1st day of Fallmist, 3019`
        *   `22nd day of Deepwinter, 3019`
        *   `15th day of Wintermarch, 3019`

*   **"Month Day, Year" Format:**
    *   Examples:
        *   `Wintermarch 15, 3019`
        *   `Springtide 2nd, 3019`
        *   `Summerday 30, 3019`

*   **With Weekday (Optional):** You can optionally include the weekday name at the beginning of the date string.
    *   Examples:
        *   `Starday, 15 Wintermarch 3019`
        *   `Sunday, 3rd day of Harvest Moon, 3019`
        *   `Moonday, Wintermarch 15, 3019`
        *   `Tidesday 5 Springtide 3019`

    *   **Note:** The parser recognizes the weekday names defined in your calendar configuration (e.g., "Starday", "Sunday", "Moonday", etc.). The weekday is parsed but is not used for date validation or calculation beyond recognition.

*   **Case Insensitivity:** Month names and weekday names are case-insensitive.
    *   Examples:
        *   `15 wintermarch 3019`
        *   `3rd DAY OF harvest moon, 3019`
        *   `sunday, 15 WINTERMARCH 3019`

**2. Month and Year Dates**

These formats represent dates with month and year precision, omitting the specific day.

*   **"Month Year" Format:**
    *   Examples:
        *   `Wintermarch 3019`
        *   `Harvest Moon 3019`
        *   `Springtide 3019`

*   **"In Month Year" or "During Month Year" Format:**
    *   Examples:
        *   `In Wintermarch 3019`
        *   `During Harvest Moon 3019`

*   **"The month of Month, Year" Format:**
    *   Examples:
        *   `The month of Wintermarch, 3019`
        *   `Month of Harvest Moon, 3019`

**3. Year Only Dates**

These formats represent dates with only the year specified.

*   **"Year YYYY" Format:**
    *   Examples:
        *   `Year 3019`
        *   `Year 45`

*   **"YYYY" Format:** (Year alone)
    *   Examples:
        *   `3019`
        *   `45`

*   **"In Year YYYY" or "During Year YYYY" Format:**
    *   Examples:
        *   `In Year 3019`
        *   `During Year 3019`
        *   `In 3019`
        *   `During the year 3019`

**4. Seasonal Dates**

These formats represent dates based on seasons within a year.  The parser recognizes seasons like "spring", "summer", "autumn", "winter", and "harvest".

*   **"Season Year" Format:**
    *   Examples:
        *   `spring 3019`
        *   `summer 3019`
        *   `autumn 3019`
        *   `winter 3019`
        *   `harvest 3019`

*   **"Early/Mid/Late Season Year" Format:** You can specify the time within the season.
    *   Examples:
        *   `Early spring 3019`
        *   `Mid summer 3019`
        *   `Late autumn 3019`
        *   `Early winter 3019`
        *   `Late harvest 3019`

*   **"Season of Year" Format (Optional "of"):**
    *   Examples:
        *   `spring of 3019`
        *   `summer of 3019`
        *   `Early spring of 3019`
        *   `Late winter of 3019`

**5. Relative Dates**

These formats represent dates relative to a named event. The current year from your calendar configuration is assumed for these dates.

*   **"X days before/after Event Name" Format:**
    *   Examples:
        *   `2 days after Battle of Hornburg`
        *   `5 days before Midsummer Festival`
        *   `1 day after The Great War`
        *   `10 days before the coronation`

*   **"During Event Name" or "Amid Event Name" Format:** Represents a date occurring during a specific event (0 days relative).
    *   Examples:
        *   `During the Siege`
        *   `Amid the Festival`
        *   `During the reign of the king`

**6. Fuzzy/Approximate Dates**

These formats represent dates that are approximate or uncertain.

*   **"Around Month Year", "Approximately Month Year", "About Month Year", "Circa Month Year" Formats:**
    *   Examples:
        *   `Around Wintermarch 3019`
        *   `Approximately Harvest Moon 3019`
        *   `About Springtide 3019`
        *   `Circa Deepwinter 3019`

*   **"Around Day Month Year", "Approximately Day Month Year", "About Day Month Year", "Circa Day Month Year" Formats:**
    *   Examples:
        *   `Around 15 Wintermarch 3019`
        *   `Approximately 2nd Springtide 3019`
        *   `About 30 Summerday 3019`
        *   `Circa 1st Harvest Moon 3019`

*   **"Sometime during Year" Format:** Indicates an unspecified time within a year.
    *   Examples:
        *   `Sometime during 3019`
        *   `Sometime in 3019`


**7. Date Ranges**

These formats represent a period between two dates.

*   **"From Month to Month Year" or "Between Month and Month Year" Formats:**  Represents a range from one month to another within the same year.
    *   Examples:
        *   `From Wintermarch to Summerday 3019`
        *   `Between Harvest Moon and Deepwinter 3019`
        *   `From Springtide and Fallmist 3019`
        *   `Between Wintermarch to Harvest Moon 3019`

*   **"From Day to Day Month Year" Format:** Represents a range from one day to another within the same month and year.
    *   Examples:
        *   `From 1st to 15th Summerday 3019`
        *   `From 5th to 20th Wintermarch 3019`
        *   `From 10th to 25th Harvest Moon 3019`


**Important Notes:**

*   **Calendar Configuration:** The parser relies on the calendar configuration provided during initialization. Ensure that the month names, weekday names (if used), and other calendar details are correctly configured.
*   **Error Handling:** If the parser cannot understand the input date string, it will raise an error indicating that the date could not be parsed.
*   **Flexibility:** The parser is designed to be flexible and handle slight variations in phrasing and punctuation within these formats.

By using these input formats, you can effectively parse dates within your custom calendar system using the date parser. If you encounter issues or have dates that are not being parsed correctly using these formats, please consult the parser's documentation or contact support for further assistance.