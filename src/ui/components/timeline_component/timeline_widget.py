import traceback
from typing import List, Dict, Any, Optional, Tuple, Union
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QScrollArea,
    QFrame,
    QLabel,
    QSizePolicy,
)
from PyQt6.QtCore import (
    Qt,
    QRectF,
    QPoint,
    QPointF,
    pyqtSignal,
    QSize,
    QTimer,
)
from PyQt6.QtGui import (
    QPainter,
    QPen,
    QColor,
    QBrush,
    QPainterPath,
    QMouseEvent,
    QWheelEvent,
)

from structlog import get_logger
from ui.components.calendar_component.calendar import CalendarHandler, CalendarDate

logger = get_logger(__name__)


class CalendarDateConverter:
    """Utility for converting between standard and calendar dates."""

    def __init__(self, calendar_handler: CalendarHandler):
        """Initialize with a calendar handler."""
        self.calendar_handler = calendar_handler
        self._date_pixel_cache = {}  # Cache for date to pixel conversions

    def year_to_pixels(
        self, year: int, min_year: float, pixels_per_year: float
    ) -> float:
        """Convert year to pixel position with calendar awareness."""
        if year in self._date_pixel_cache:
            return self._date_pixel_cache[year]

        # Calculate relative position within the calendar year system
        result = (year - min_year) * pixels_per_year
        self._date_pixel_cache[year] = result
        return result

    # In CalendarDateConverter.date_to_pixels method:
    def date_to_pixels(self, year, month, day, min_year, pixels_per_year):
        """Convert complete date to pixel position."""
        cache_key = (year, month, day)
        if cache_key in self._date_pixel_cache:
            return self._date_pixel_cache[cache_key]

        # Basic year position
        position = (year - min_year) * pixels_per_year
        logger.debug(
            "Date position calculation",
            event="date_position_base",
            year=year,
            month=month,
            day=day,
            base_position=position,
        )

        # If we have month and day information, refine the position
        if month is not None and day is not None:
            try:
                # Get month information
                month_days = self.calendar_handler.calendar_data["month_days"]
                month_names = self.calendar_handler.calendar_data.get("month_names", [])
                month_name = (
                    month_names[month - 1]
                    if month <= len(month_names)
                    else f"Month {month}"
                )

                # Get days into year
                days_into_year = 0
                for m in range(1, month):
                    days_in_month = month_days[m - 1]
                    days_into_year += days_in_month
                    logger.debug(
                        "Month calculation",
                        event="month_days_calculation",
                        month_number=m,
                        month_name=(
                            month_names[m - 1]
                            if m <= len(month_names)
                            else f"Month {m}"
                        ),
                        days_in_month=days_in_month,
                        running_total=days_into_year,
                    )

                days_into_year += day

                # Get fraction of year
                year_length = self.calendar_handler.calendar_data["year_length"]
                year_fraction = days_into_year / year_length

                # Add fractional position
                fractional_position = year_fraction * pixels_per_year
                position += fractional_position

                logger.debug(
                    "Final date position",
                    event="date_position_final",
                    year=year,
                    month=month,
                    month_name=month_name,
                    day=day,
                    days_into_year=days_into_year,
                    year_length=year_length,
                    year_fraction=year_fraction,
                    final_position=position,
                )

            except Exception as e:
                logger.error(
                    "Error calculating date position",
                    event="date_position_error",
                    error=str(e),
                    year=year,
                    month=month,
                    day=day,
                    exc_info=True,
                )

        self._date_pixel_cache[cache_key] = position
        return position

    def pixels_to_year(
        self, pixels: float, min_year: float, pixels_per_year: float
    ) -> float:
        """Convert pixel position to year with calendar awareness."""
        return min_year + (pixels / pixels_per_year)

    def format_date(
        self, year: int, month: Optional[int] = None, day: Optional[int] = None
    ) -> str:
        """Format date using calendar system."""
        # Just year
        if month is None or day is None:
            # Find which epoch this year belongs to
            epoch_names = self.calendar_handler.calendar_data.get("epoch_names", [""])
            epoch_abbrs = self.calendar_handler.calendar_data.get(
                "epoch_abbreviations", [""]
            )
            epoch_starts = self.calendar_handler.calendar_data.get(
                "epoch_start_years", [0]
            )
            epoch_ends = self.calendar_handler.calendar_data.get(
                "epoch_end_years", [99999]
            )

            # Find matching epoch
            epoch_index = 0
            for i, (start, end) in enumerate(zip(epoch_starts, epoch_ends)):
                if start <= year <= end:
                    epoch_index = i
                    break

            epoch_abbr = (
                epoch_abbrs[epoch_index] if epoch_index < len(epoch_abbrs) else ""
            )
            return f"{year} {epoch_abbr}"

        # Full date
        if month <= len(self.calendar_handler.calendar_data["month_names"]):
            month_name = self.calendar_handler.calendar_data["month_names"][month - 1]
            return f"{day} {month_name}, {year}"

        # Fallback
        return f"{year}/{month}/{day}"

    def get_interval_and_format(self, pixels_per_year: float) -> Tuple[int, str]:
        """Determine appropriate date interval and format based on scale."""
        year_length = self.calendar_handler.calendar_data["year_length"]

        # Adjust intervals based on custom year length
        year_length_ratio = year_length / 365.0  # Ratio compared to standard year

        if pixels_per_year >= 100 * year_length_ratio:  # Very detailed
            interval = 1  # Show every year
            format_type = "year_month"
        elif pixels_per_year >= 20 * year_length_ratio:
            interval = 5  # Every 5 years
            format_type = "year"
        elif pixels_per_year >= 10 * year_length_ratio:
            interval = 10  # Every decade
            format_type = "year"
        elif pixels_per_year >= 5 * year_length_ratio:
            interval = 20  # Every 20 years
            format_type = "year"
        elif pixels_per_year >= 2 * year_length_ratio:
            interval = 50  # Every 50 years
            format_type = "year"
        else:
            interval = 100  # Every century
            format_type = "year"

        return interval, format_type


class EventCard(QFrame):
    """Interactive card representing a timeline event"""

    clicked = pyqtSignal(dict)  # Signal emitting event data when clicked

    def __init__(
        self,
        event_data: Dict[str, Any],
        calendar_converter: Optional[CalendarDateConverter] = None,
        parent=None,
    ):
        super().__init__(parent)
        self.event_data = event_data
        self.calendar_converter = calendar_converter
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setMinimumWidth(200)
        self.setMaximumWidth(250)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setup_ui()

    def setup_ui(self):
        """Set up the card UI elements"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(5)

        # Create title with bold font
        title = QLabel(self.event_data.get("name", "Unknown Event"))
        title.setStyleSheet("font-weight: bold; font-size: 13px;")
        title.setWordWrap(True)

        # Create date display
        year = self.event_data.get("parsed_date_year")
        month = self.event_data.get("parsed_date_month")
        day = self.event_data.get("parsed_date_day")

        # Format date based on available calendar information
        if self.calendar_converter and year is not None:
            date_text = self.calendar_converter.format_date(year, month, day)
        else:
            # Fallback to standard formatting
            date_text = f"{year}"
            if month:
                date_text += f"/{month}"
                if day:
                    date_text += f"/{day}"

        date = QLabel(date_text)
        date.setStyleSheet("color: #666; font-size: 11px;")

        # Create summary/description if available
        description = self.event_data.get("description", "")
        if not description and "temporal_data" in self.event_data:
            description = self.event_data.get("temporal_data", "")

        summary = QLabel(description[:100] + ("..." if len(description) > 100 else ""))
        summary.setWordWrap(True)
        summary.setStyleSheet("font-size: 12px;")

        # Add all elements to layout
        layout.addWidget(title)
        layout.addWidget(date)
        if description:
            layout.addWidget(summary)

        # Set border color based on event type
        event_type = self.event_data.get("event_type", "Occurrence")
        self.set_card_style(event_type)

    def set_card_style(self, event_type: str):
        """Apply style based on event type"""
        base_style = """
            QFrame {
                border-radius: 6px;
                background-color: white;
                border: 1px solid #ddd;
            }
            QFrame:hover {
                border: 1px solid #aaa;
                background-color: #f9f9f9;
            }
        """

        # Color mapping for different event types
        colors = {
            "battle": "#e74c3c",
            "war": "#e74c3c",
            "conflict": "#e74c3c",
            "political": "#3498db",
            "coronation": "#3498db",
            "treaty": "#3498db",
            "cultural": "#2ecc71",
            "foundation": "#2ecc71",
            "founding": "#2ecc71",
            "discovery": "#f39c12",
            "death": "#7f8c8d",
            "birth": "#9b59b6",
            "occurrence": "#34495e",
            "default": "#95a5a6",
        }

        # Get color for event type, defaulting to occurrence or generic default
        color = colors.get(
            event_type.lower(), colors.get("occurrence", colors["default"])
        )

        # Apply style with left border in the type color
        self.setStyleSheet(
            base_style
            + f"""
            QFrame {{
                border-left: 4px solid {color};
            }}
        """
        )

    def mousePressEvent(self, event):
        """Handle mouse press to emit clicked signal"""
        self.clicked.emit(self.event_data)  # type: ignore
        super().mousePressEvent(event)

    def sizeHint(self):
        """Provide a reasonable default size"""
        return QSize(220, 100)


class TimelineLane(QWidget):
    """A horizontal lane for a category of events"""

    def __init__(
        self,
        category: str,
        calendar_converter: Optional[CalendarDateConverter] = None,
        parent=None,
    ):
        super().__init__(parent)
        self.category = category
        self.events = []
        self.min_year = 0
        self.max_year = 100
        self.pixels_per_year = 50  # Default scale
        self.cards = []  # Keep track of created cards
        self.content_area = None  # Initialize here
        self.calendar_converter = calendar_converter
        self.calendar_mode = calendar_converter is not None
        self.setMinimumHeight(140)
        self.setup_ui()

    def setup_ui(self):
        """Set up the lane UI elements"""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 5, 0, 15)  # Add bottom margin for connection lines

        # Content area for events
        self.content_area = QWidget()
        self.content_area.setMinimumHeight(120)

        layout.addWidget(self.content_area, 1)  # Content area stretches

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

    def get_category(self) -> str:
        """Return the category name for this lane"""
        return self.category

    def set_calendar_handler(self, handler: CalendarHandler) -> None:
        """Set the calendar handler for this lane."""
        self.calendar_converter = CalendarDateConverter(handler)
        self.calendar_mode = True
        self.position_event_cards()  # Reposition with new calendar

    def set_scale(self, pixels_per_year: float):
        """Update the horizontal scale and reposition events"""
        if pixels_per_year != self.pixels_per_year:
            self.pixels_per_year = pixels_per_year
            self.position_event_cards()
            self.update()

    def set_year_range(self, min_year: int, max_year: int):
        """Set the visible year range"""
        if min_year != self.min_year or max_year != self.max_year:
            self.min_year = min_year
            self.max_year = max_year
            self.position_event_cards()

    def clear_events(self):
        """Clear all events from the lane"""
        # Remove all cards
        for card in self.cards:
            card.deleteLater()
        self.cards = []
        self.events = []

    def add_events(self, events: List[Dict[str, Any]]):
        """Add events to the lane with proper positioning"""
        self.events = events

        # Clear any existing event cards
        for card in self.cards:
            card.deleteLater()
        self.cards = []

        # Create event cards
        for event in events:
            card = EventCard(event, self.calendar_converter, self.content_area)
            self.cards.append(card)

        # Position the cards
        self.position_event_cards()

    def position_event_cards(self):
        """Position all event cards based on their dates and current scale"""
        if not self.events or not self.cards:
            return

        # Order cards by date
        events_with_cards = sorted(
            zip(self.events, self.cards),
            key=lambda pair: (
                pair[0].get("parsed_date_year", 0),
                pair[0].get("parsed_date_month", 0),
                pair[0].get("parsed_date_day", 0),
            ),
        )

        # Calculate vertical positions to prevent overlaps
        used_ranges = []  # List of (x_start, x_end) of used horizontal ranges

        for event, card in events_with_cards:
            year = event.get("parsed_date_year", self.min_year)
            month = event.get("parsed_date_month")
            day = event.get("parsed_date_day")

            # Calculate x position based on date
            if self.calendar_converter and self.calendar_mode:
                # Use calendar-aware positioning
                x_pos = self.calendar_converter.date_to_pixels(
                    year, month, day, self.min_year, self.pixels_per_year
                )
            else:
                # Standard positioning
                x_pos = (year - self.min_year) * self.pixels_per_year

            card_width = card.width()

            # Check for overlaps with existing cards
            card_start = x_pos - card_width / 2
            card_end = x_pos + card_width / 2

            # Find vertical level for card (0 = top, increments for lower positions)
            level = 0
            overlap = True

            while (
                overlap and level < 3
            ):  # Limit to 3 levels to prevent excessive stacking
                overlap = False
                for start, end in used_ranges:
                    if not (card_end < start or card_start > end):
                        overlap = True
                        break

                if overlap:
                    level += 1
                else:
                    used_ranges.append((card_start, card_end))

            # Position the card
            y_pos = level * 40  # 40 pixels per level
            card.move(int(card_start), int(y_pos))
            card.show()

        # Update height based on levels used
        max_level = 0
        for _, card in events_with_cards:
            max_level = max(max_level, card.y() // 40)

        self.setMinimumHeight(140 + max_level * 40)

    def paintEvent(self, event):
        """Draw connecting lines from cards to timeline"""
        super().paintEvent(event)

        if not self.cards:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Line style for connections
        painter.setPen(QPen(QColor("#ccc"), 1, Qt.PenStyle.DashLine))

        # Draw connection from each card to the timeline
        timeline_y = self.height() - 10

        for event, card in zip(self.events, self.cards):
            # Calculate event center x-coordinate
            year = event.get("parsed_date_year", self.min_year)
            month = event.get("parsed_date_month")
            day = event.get("parsed_date_day")

            # Calculate x position with calendar awareness if available
            if self.calendar_converter and self.calendar_mode:
                x_pos = self.calendar_converter.date_to_pixels(
                    year, month, day, self.min_year, self.pixels_per_year
                )
            else:
                x_pos = (year - self.min_year) * self.pixels_per_year

            # Calculate bottom center of card
            card_bottom_x = card.x() + card.width() / 2
            card_bottom_y = card.y() + card.height()

            # Draw dot at timeline position
            painter.setBrush(QBrush(QColor("#666")))
            painter.setPen(QPen(QColor("#666"), 1))
            painter.drawEllipse(QPointF(x_pos, timeline_y), 3, 3)

            # Draw connection line from card to timeline dot
            path = QPainterPath()
            path.moveTo(card_bottom_x, card_bottom_y)

            # Use a curved connection line for better visual appearance
            control_y = (card_bottom_y + timeline_y) / 2
            path.cubicTo(
                card_bottom_x,
                control_y,  # First control point
                x_pos,
                control_y,  # Second control point
                x_pos,
                timeline_y,  # End point
            )

            painter.setPen(QPen(QColor("#ccc"), 1, Qt.PenStyle.DashLine))
            painter.drawPath(path)


class TimelineAxisWidget(QWidget):
    """Widget displaying the time axis with markers"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.min_year = 0
        self.max_year = 100
        self.pixels_per_year = 50
        self.display_mode = "years"  # years, months, days
        self.calendar_handler = None
        self.calendar_converter = None
        self.calendar_mode = False
        self.setMinimumHeight(50)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_calendar_handler(self, handler: CalendarHandler) -> None:
        """Set the calendar handler for this axis."""
        self.calendar_handler = handler
        self.calendar_converter = CalendarDateConverter(handler)
        self.calendar_mode = True
        self.update()  # Redraw with calendar awareness

    def set_display_mode(self, mode: str) -> None:
        """Set the display mode for the axis (years, months, days)."""
        if mode in ("years", "months", "days"):
            self.display_mode = mode
            self.update()

    def set_scale(self, pixels_per_year: float):
        """Set the horizontal scale for the axis"""
        self.pixels_per_year = pixels_per_year

        # Set appropriate display mode based on scale
        if self.calendar_mode and self.calendar_converter:
            if pixels_per_year >= 80:  # Reduced threshold to match _paint_calendar_axis
                self.display_mode = "months"
                logger.debug(
                    f"Timeline scale set to months mode: {pixels_per_year} pixels/year"
                )
            elif pixels_per_year >= 20:
                self.display_mode = "years"
            else:
                self.display_mode = "years"

        self.update()

    def set_year_range(self, min_year: int, max_year: int):
        """Set the year range for the axis"""
        self.min_year = min_year
        self.max_year = max_year
        self.update()

    def paintEvent(self, event):
        """Draw the axis and year markers"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Draw main axis line
        painter.setPen(QPen(QColor("#aaa"), 2))
        y_pos = 20
        painter.drawLine(0, y_pos, self.width(), y_pos)

        # Choose rendering method based on calendar mode
        if self.calendar_mode and self.calendar_converter and self.calendar_handler:
            self._paint_calendar_axis(painter, y_pos)
        else:
            self._paint_standard_axis(painter, y_pos)

    def _paint_standard_axis(self, painter: QPainter, y_pos: int):
        """Draw standard axis with regular year intervals."""
        # Calculate appropriate interval based on pixels per year
        if self.pixels_per_year >= 100:  # Very detailed
            interval = 1  # Show every year
        elif self.pixels_per_year >= 20:
            interval = 5  # Every 5 years
        elif self.pixels_per_year >= 10:
            interval = 10  # Every decade
        elif self.pixels_per_year >= 5:
            interval = 20  # Every 20 years
        elif self.pixels_per_year >= 2:
            interval = 50  # Every 50 years
        else:
            interval = 100  # Every century

        # Draw markers
        painter.setPen(QPen(QColor("#666"), 1))

        # Calculate a nice starting year that aligns with the interval
        start_year = (int(self.min_year) // interval) * interval
        if start_year < self.min_year:
            start_year += interval

        for year in range(int(start_year), int(self.max_year) + 1, interval):
            # Calculate x position
            x_pos = (year - self.min_year) * self.pixels_per_year

            # Skip if outside visible area with some padding
            if x_pos < -100 or x_pos > self.width() + 100:
                continue

            # Draw tick mark
            painter.drawLine(int(x_pos), y_pos - 5, int(x_pos), y_pos + 5)

            # Draw year text
            painter.drawText(
                QRectF(x_pos - 30, y_pos + 10, 60, 20),
                Qt.AlignmentFlag.AlignCenter,
                str(year),
            )

    def _paint_calendar_axis(self, painter: QPainter, y_pos: int):
        """Draw calendar-aware axis with proper date markers."""
        # Get appropriate interval based on scale
        interval, format_type = self.calendar_converter.get_interval_and_format(
            self.pixels_per_year
        )

        # Draw markers
        painter.setPen(QPen(QColor("#666"), 1))

        # Calculate a nice starting year that aligns with the interval
        start_year = (int(self.min_year) // interval) * interval
        if start_year < self.min_year:
            start_year += interval

        # Draw year markers
        for year in range(int(start_year), int(self.max_year) + 1, interval):
            # Calculate x position
            x_pos = self.calendar_converter.year_to_pixels(
                year, self.min_year, self.pixels_per_year
            )

            # Skip if outside visible area with some padding
            if x_pos < -100 or x_pos > self.width() + 100:
                continue

            # Draw tick mark
            painter.drawLine(int(x_pos), y_pos - 5, int(x_pos), y_pos + 5)

            # Format date text based on display mode
            if format_type == "year":
                date_text = self.calendar_converter.format_date(year)
            else:
                # For now, just years - month display would be implemented in a more detailed version
                date_text = self.calendar_converter.format_date(year)

            # Draw date text
            text_rect = QRectF(x_pos - 40, y_pos + 10, 80, 20)
            painter.drawText(
                text_rect,
                Qt.AlignmentFlag.AlignCenter,
                date_text,
            )

        # Show month markers when zoomed in enough (lowered threshold)
        if self.pixels_per_year >= 80:  # Reduced from 100 to make months appear sooner
            self._draw_month_markers(painter, y_pos)

    def _draw_month_markers(self, painter: QPainter, y_pos: int):
        """Draw month markers when zoomed in enough."""
        # Only show months for a reasonable range to prevent overcrowding
        visible_years = max(1, min(20, int(self.max_year - self.min_year) + 1))
        view_min_year = max(int(self.min_year), int(self.max_year) - visible_years)

        # Log current zoom level for debugging
        logger.debug(f"Drawing month markers at {self.pixels_per_year} pixels/year")

        # For each visible year
        for year in range(view_min_year, int(self.max_year) + 1):
            month_names = self.calendar_handler.calendar_data["month_names"]
            month_days = self.calendar_handler.calendar_data["month_days"]

            # For each month in this year
            cumulative_days = 0
            for i, (month_name, days) in enumerate(zip(month_names, month_days)):
                month_num = i + 1  # 1-based month index

                # Calculate month position
                year_start_x = self.calendar_converter.year_to_pixels(
                    year, self.min_year, self.pixels_per_year
                )
                year_length = self.calendar_handler.calendar_data["year_length"]

                # Position based on cumulative days
                month_pos = (
                    year_start_x
                    + (cumulative_days / year_length) * self.pixels_per_year
                )

                # Skip if outside visible area
                if month_pos < -50 or month_pos > self.width() + 50:
                    cumulative_days += days
                    continue

                # Draw more visible month marker
                painter.setPen(QPen(QColor("#666"), 1, Qt.PenStyle.DashLine))
                painter.drawLine(int(month_pos), y_pos - 5, int(month_pos), y_pos + 5)

                # Draw month label with lower threshold
                if self.pixels_per_year >= 150:  # Reduced from 200
                    painter.setPen(QPen(QColor("#666"), 1))
                    text_rect = QRectF(month_pos - 15, y_pos + 10, 30, 15)
                    painter.drawText(
                        text_rect,
                        Qt.AlignmentFlag.AlignCenter,
                        month_name[:3],  # Abbreviate to prevent crowding
                    )

                cumulative_days += days


class TimelineContent(QWidget):
    """Main widget containing the timeline content with lanes and axis"""

    # Define a signal to notify parent of lane changes
    lanes_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.events = []
        self.event_types = set()  # Unique event types
        self.lanes = {}  # Maps event_type to TimelineLane
        self.min_year = 0
        self.max_year = 100
        self.pixels_per_year = 50.0  # Default scale
        self.layout = None  # Initialize here
        self.axis = None  # Initialize here

        # Calendar support
        self.calendar_handler = None
        self.calendar_converter = None
        self.calendar_mode = False

        # Minimum and maximum zoom levels
        self.min_pixels_per_year = 1.0  # Most zoomed out
        self.max_pixels_per_year = (
            5000.0  # Most zoomed in (increased to allow deeper zoom)
        )

        # For panning support
        self.panning = False
        self.last_mouse_pos = None

        # Initialize UI
        self.setMinimumSize(800, 400)
        self.setup_ui()

        # Set up mouse tracking
        self.setMouseTracking(True)

    def setup_ui(self):
        """Set up UI components"""
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(10, 10, 10, 10)
        self.layout.setSpacing(0)

        # Add the axis widget
        self.axis = TimelineAxisWidget()
        self.layout.addWidget(self.axis)

        # Lanes will be added dynamically
        self.layout.addStretch()

    def set_calendar_data(self, calendar_data: Dict[str, Any]) -> None:
        """Set calendar data for timeline content."""
        if not calendar_data:
            return

        try:
            # Store calendar handler
            self.calendar_handler = CalendarHandler(calendar_data)

            # Create converter for date calculations
            self.calendar_converter = CalendarDateConverter(self.calendar_handler)

            # CRITICAL FIX 5: Set calendar mode to True
            self.calendar_mode = True

            # CRITICAL FIX 6: Propagate to axis
            if hasattr(self, "axis") and self.axis:
                self.axis.set_calendar_handler(self.calendar_handler)

            # CRITICAL FIX 7: Propagate to existing lanes
            if hasattr(self, "lanes"):
                for lane in self.lanes.values():
                    lane.set_calendar_handler(self.calendar_handler)

            logger.debug(
                "Calendar data set in TimelineContent",
                calendar_mode=self.calendar_mode,
                has_handler=self.calendar_handler is not None,
                has_converter=self.calendar_converter is not None,
                propagated_to_lanes=hasattr(self, "lanes"),
            )
        except Exception as e:
            logger.error(
                "Error setting calendar data in TimelineContent",
                error=str(e),
                traceback=traceback.format_exc(),
            )

    def set_scale(self, pixels_per_year: float):
        """Set the timeline scale (pixels per year)"""
        # Clamp scale within limits
        pixels_per_year = max(
            self.min_pixels_per_year, min(self.max_pixels_per_year, pixels_per_year)
        )

        if pixels_per_year != self.pixels_per_year:
            self.pixels_per_year = pixels_per_year

            # Update axis scale
            self.axis.set_scale(pixels_per_year)

            # Update all lanes
            for lane in self.lanes.values():
                lane.set_scale(pixels_per_year)

            # Update widget size
            self.updateGeometry()

    def set_data(self, events: List[Dict[str, Any]], scale: str):
        """Set timeline data and update display"""

        if not hasattr(self, "calendar_mode"):
            self.calendar_mode = False

        self.events = events

        # Extract year range
        years = [
            event.get("parsed_date_year", 0)
            for event in events
            if event.get("parsed_date_year") is not None
        ]

        if years:
            self.min_year = min(years)
            self.max_year = max(years)

            # Add padding
            year_span = self.max_year - self.min_year
            padding = max(year_span * 0.1, 5)
            self.min_year = int(self.min_year - padding)
            self.max_year = int(self.max_year + padding)
        else:
            self.min_year = 0
            self.max_year = 100

        # Set initial scale based on selected option and calendar awareness
        year_length_factor = 1.0
        if self.calendar_mode and self.calendar_handler:
            # Adjust scale for custom calendar year length
            year_length = self.calendar_handler.calendar_data["year_length"]
            year_length_factor = year_length / 365.0  # Rough approximation

        if scale == "Decades":
            self.pixels_per_year = 5 * year_length_factor
        elif scale == "Years":
            self.pixels_per_year = 50 * year_length_factor
        elif scale == "Months":
            self.pixels_per_year = 100 * year_length_factor
        elif scale == "Days":
            self.pixels_per_year = 200 * year_length_factor
        else:
            self.pixels_per_year = 50 * year_length_factor  # Default to years

        # Update axis
        self.axis.set_year_range(self.min_year, self.max_year)
        self.axis.set_scale(self.pixels_per_year)

        logger.debug(
            "TimelineContent.set_data - Before organizing events",
            event_count=len(events),
            calendar_mode=self.calendar_mode,
            has_converter=hasattr(self, "calendar_converter")
            and self.calendar_converter is not None,
        )

        # Organize events by type
        self.organize_events_by_type()

        # Update widget size
        self.updateGeometry()

    def organize_events_by_type(self):
        """Create lanes for each event type"""
        # Extract event types
        self.event_types = set()
        for event in self.events:
            event_type = event.get("event_type", "Occurrence")
            self.event_types.add(event_type)

        # Clear existing lanes
        for lane in self.lanes.values():
            self.layout.removeWidget(lane)
            lane.deleteLater()

        self.lanes = {}

        # Create new lanes for each event type with vertical separation
        for i, event_type in enumerate(sorted(self.event_types)):
            # Get events for this type
            type_events = [
                e
                for e in self.events
                if e.get("event_type", "Occurrence") == event_type
            ]

            # Create lane with calendar awareness if available
            lane = TimelineLane(
                event_type, self.calendar_converter if self.calendar_mode else None
            )
            lane.set_year_range(self.min_year, self.max_year)
            lane.set_scale(self.pixels_per_year)
            lane.add_events(type_events)

            # Add to layout before the stretch
            self.layout.insertWidget(self.layout.count() - 1, lane)

            # Store in dictionary
            self.lanes[event_type] = lane

        # Update widget size
        self.updateGeometry()
        self.update()

        # Emit signal after layout has been processed
        QTimer.singleShot(10, self.lanes_changed.emit)  # type: ignore

    def sizeHint(self):
        """Calculate size based on timeline span and lanes"""
        width = int(
            (self.max_year - self.min_year) * self.pixels_per_year + 200
        )  # Add margin
        height = 50  # Start with axis height

        # Add height for each lane
        for lane in self.lanes.values():
            height += lane.minimumHeight()

        return QSize(width, int(height))

    def wheelEvent(self, event: QWheelEvent):
        """Handle mouse wheel for zooming"""
        # Get mouse position for zoom focus
        mouse_pos = event.position()

        # Calculate year at cursor position before zoom
        if self.calendar_converter and self.calendar_mode:
            year_at_cursor = self.calendar_converter.pixels_to_year(
                mouse_pos.x(), self.min_year, self.pixels_per_year
            )
        else:
            year_at_cursor = self.min_year + (mouse_pos.x() / self.pixels_per_year)

        # Calculate new scale
        delta = event.angleDelta().y()
        zoom_factor = 1.0 + (delta / 800.0)  # Increased zoom rate for faster zooming
        new_scale = self.pixels_per_year * zoom_factor

        # Apply new scale
        self.set_scale(new_scale)

        # Adjust min_year to keep the year under cursor at the same position
        new_x = mouse_pos.x()

        if self.calendar_converter and self.calendar_mode:
            new_year_at_cursor = self.calendar_converter.pixels_to_year(
                new_x, self.min_year, self.pixels_per_year
            )
        else:
            new_year_at_cursor = self.min_year + (new_x / self.pixels_per_year)

        year_offset = year_at_cursor - new_year_at_cursor

        self.min_year += year_offset
        self.max_year = self.min_year + (self.width() / self.pixels_per_year)

        # Update axis and lanes
        self.axis.set_year_range(self.min_year, self.max_year)
        for lane in self.lanes.values():
            lane.set_year_range(self.min_year, self.max_year)

        # Accept event
        event.accept()

    def mousePressEvent(self, event: QMouseEvent):
        """Handle mouse press for panning"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.panning = True
            self.last_mouse_pos = event.position()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        """Handle mouse move for panning"""
        if self.panning and self.last_mouse_pos:
            # Calculate movement in pixels
            delta_x = event.position().x() - self.last_mouse_pos.x()

            # Convert to years
            delta_years = delta_x / self.pixels_per_year

            # Update year range
            self.min_year -= delta_years
            self.max_year -= delta_years

            # Update axis and lanes
            self.axis.set_year_range(self.min_year, self.max_year)
            for lane in self.lanes.values():
                lane.set_year_range(self.min_year, self.max_year)

            # Force repaint and update widget sizing
            self.updateGeometry()
            self.update()

            # Update last position
            self.last_mouse_pos = event.position()
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        """Handle mouse release for panning"""
        if event.button() == Qt.MouseButton.LeftButton and self.panning:
            self.panning = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
            event.accept()
        else:
            super().mouseReleaseEvent(event)


class TimelineWidget(QWidget):
    """Main timeline widget providing scrolling and controls"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.labels_area = None  # Initialize here
        self.scroll_area = None  # Initialize here
        self.content = None  # Initialize here
        self.lane_labels = {}  # Initialize here
        self.calendar_handler = None  # Initialize calendar handler
        self.calendar_mode = False
        self.setup_ui()

    def setup_ui(self):
        """Set up the main UI components"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Create container widget to hold both labels and timeline
        container = QWidget()
        container_layout = QHBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)

        # Create labels area with fixed width
        self.labels_area = QWidget()
        self.labels_area.setFixedWidth(120)
        self.labels_area.setStyleSheet("background-color: white;")

        # Create scroll area
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self.scroll_area.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )

        # Create content widget
        self.content = TimelineContent()
        self.scroll_area.setWidget(self.content)

        # Connect the signal
        self.content.lanes_changed.connect(self.on_lanes_changed)  # type: ignore

        # Add widgets to container
        container_layout.addWidget(self.labels_area)
        container_layout.addWidget(self.scroll_area)

        # Add container to main layout
        layout.addWidget(container)

        # Connect scroll signal
        self.scroll_area.verticalScrollBar().valueChanged.connect(self.update_labels)  # type: ignore

    def set_calendar_data(self, calendar_data: Dict[str, Any]) -> None:
        """Set calendar data for timeline."""
        logger.debug("Setting calendar data in TimelineWidget")

        if not calendar_data:
            logger.debug("No calendar data provided")
            return

        try:
            # Store and create handler
            self.calendar_handler = CalendarHandler(calendar_data)

            # CRITICAL FIX 1: Explicitly set calendar awareness in this widget
            self.calendar_mode = True

            # Pass to content widget
            if self.content:
                # CRITICAL FIX 2: Now that we have calendar data, propagate it to content
                self.content.set_calendar_data(calendar_data)
                logger.debug(
                    "Calendar data propagation status",
                    content_calendar_mode=(
                        self.content.calendar_mode
                        if hasattr(self.content, "calendar_mode")
                        else False
                    ),
                    content_has_converter=(
                        self.content.calendar_converter is not None
                        if hasattr(self.content, "calendar_converter")
                        else False
                    ),
                )

        except Exception as e:
            logger.error(f"Error setting calendar data: {e}")
            self.calendar_handler = None

    def on_lanes_changed(self):
        """Handle changes in timeline lanes"""
        # Clear existing labels
        self.clear_lane_labels()

        # Create new labels for each lane
        for lane in self.content.lanes.values():
            self.add_lane_label(lane)

        # Update positions
        self.update_labels()

    def add_lane_label(self, lane):
        """Add a label for a timeline lane"""
        # Create label widget as direct child of labels area for precise positioning
        label = QLabel(lane.get_category(), self.labels_area)
        label.setStyleSheet(
            """
            font-weight: bold; 
            color: #555; 
            font-size: 12px; 
            padding: 5px;
            background-color: rgba(255, 255, 255, 210);
            border-radius: 3px;
        """
        )
        label.setFixedWidth(100)
        label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        # Store reference
        self.lane_labels[lane] = label

    def clear_lane_labels(self):
        """Remove all lane labels"""
        for label in self.lane_labels.values():
            label.deleteLater()
        self.lane_labels.clear()

    def update_labels(self):
        """Update label positions based on current scroll position"""
        if not self.content or not hasattr(self.content, "lanes"):
            logger.debug("update_labels: No content or lanes found")
            return

        # Use QTimer.singleShot to wait for layout to settle
        QTimer.singleShot(0, self._update_labels_after_layout)

    def _update_labels_after_layout(self):
        """Update labels after the layout has settled"""
        if not hasattr(self.content, "lanes"):
            return

        # Create any missing labels
        for lane_type, lane in self.content.lanes.items():
            if lane not in self.lane_labels:
                self.add_lane_label(lane)

        # Remove obsolete labels
        to_remove = [
            lane for lane in self.lane_labels if lane not in self.content.lanes.values()
        ]
        for lane in to_remove:
            if lane in self.lane_labels:
                self.lane_labels[lane].deleteLater()
                del self.lane_labels[lane]

        # Ensure each lane has a unique vertical position by forcing layout update
        for i, lane in enumerate(self.content.lanes.values()):
            lane.updateGeometry()

        # Process each lane
        lane_positions = {}
        label_positions = []

        # First pass - get actual positions
        for lane, label in self.lane_labels.items():
            # Map lane position to viewport coordinates
            lane_rect = lane.geometry()
            lane_pos = lane.mapToGlobal(QPoint(0, 0))
            viewport_pos = self.scroll_area.viewport().mapFromGlobal(lane_pos)

            # Calculate center position
            lane_center_y = viewport_pos.y() + (lane_rect.height() // 2)

            # Store actual vertical position and height
            lane_positions[lane] = {
                "y": viewport_pos.y(),
                "height": lane_rect.height(),
                "center_y": lane_center_y,
                "category": lane.get_category(),
            }

            # Log actual position of each lane
            logger.debug(
                f"Lane '{lane.get_category()}' actual position: y={viewport_pos.y()}, "
                f"height={lane_rect.height()}, center={lane_center_y}"
            )

        # Sort lanes by vertical position to prevent overlapping labels
        for lane, info in sorted(lane_positions.items(), key=lambda x: x[1]["y"]):
            label = self.lane_labels[lane]
            category = info["category"]

            # Calculate label position
            label_height = label.height()
            label_y = info["center_y"] - (label_height // 2)

            # Check if lane is visible in viewport
            viewport_height = self.scroll_area.viewport().height()
            lane_y = info["y"]
            lane_height = info["height"]
            is_visible = lane_y < viewport_height and (lane_y + lane_height) > 0

            if is_visible:
                logger.debug(f"Positioning label for '{category}' at y={label_y}")
                label.move(10, int(label_y))
                label.show()

                # Store this position to check for overlaps with next label
                label_positions.append((label_y, label_y + label_height))
            else:
                label.hide()

        # Log final positions
        logger.debug("Final label positions:")
        for lane, label in self.lane_labels.items():
            logger.debug(
                f"  - {lane.get_category()}: at {label.pos()}, visible: {label.isVisible()}"
            )

    def resizeEvent(self, event):
        """Handle resize event"""
        super().resizeEvent(event)
        self.update_labels()

    def set_data(self, events: List[Dict[str, Any]], scale: str) -> None:
        """Update the timeline with new data."""
        logger.debug(
            "TimelineWidget.set_data called",
            event_count=len(events),
            scale=scale,
            # CRITICAL FIX 3: Use self.calendar_mode instead of checking handler
            has_calendar=self.calendar_mode,
        )

        # CRITICAL FIX 4: If we have calendar data but content doesn't, reapply it
        if self.calendar_mode and self.calendar_handler and self.content:
            if (
                not hasattr(self.content, "calendar_mode")
                or not self.content.calendar_mode
            ):
                self.content.set_calendar_data(self.calendar_handler.calendar_data)
                logger.debug(
                    "Reapplied calendar data to timeline content before setting events"
                )

        # Now pass the events to content
        self.content.set_data(events, scale)
