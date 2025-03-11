from typing import List, Dict, Any, Optional, Set, Tuple
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QScrollArea,
    QFrame,
    QLabel,
    QComboBox,
    QPushButton,
    QSizePolicy,
)
from PyQt6.QtCore import (
    Qt,
    QRectF,
    QPoint,
    QPointF,
    pyqtSignal,
    QSize,
    QEasingCurve,
    QPropertyAnimation,
    QRect,
    QTimer,
)
from PyQt6.QtGui import (
    QPainter,
    QPen,
    QColor,
    QBrush,
    QFont,
    QFontMetrics,
    QLinearGradient,
    QPainterPath,
    QMouseEvent,
    QWheelEvent,
)

from structlog import get_logger

logger = get_logger(__name__)


class EventCard(QFrame):
    """Interactive card representing a timeline event"""

    clicked = pyqtSignal(dict)  # Signal emitting event data when clicked

    def __init__(self, event_data: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.event_data = event_data
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
        self.clicked.emit(self.event_data)
        super().mousePressEvent(event)

    def sizeHint(self):
        """Provide a reasonable default size"""
        return QSize(220, 100)


class TimelineLane(QWidget):
    """A horizontal lane for a category of events"""

    def __init__(self, category: str, parent=None):
        super().__init__(parent)
        self.category = category
        self.events = []
        self.min_year = 0
        self.max_year = 100
        self.pixels_per_year = 50  # Default scale
        self.cards = []  # Keep track of created cards
        self.calendar_data = None
        self.setMinimumHeight(140)
        self.setup_ui()

    def set_calendar_data(self, calendar_data: Dict[str, Any]) -> None:
        """Set calendar data for precise date positioning"""
        self.calendar_data = calendar_data

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
            self.update()

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
            card = EventCard(event, self.content_area)
            self.cards.append(card)

        # Position the cards
        self.position_event_cards()

        QTimer.singleShot(50, self.update)

    def position_event_cards(self):
        """Position all event cards based on their dates and current scale"""
        if not self.events or not self.cards:
            return

        year_span = max(1, self.max_year - self.min_year)

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
            month = event.get("parsed_date_month", 1)
            day = event.get("parsed_date_day", 1)

            # Calculate position within year based on custom calendar
            year_fraction = 0

            if self.calendar_data:
                month_days = self.calendar_data.get("month_days", [])
                year_length = self.calendar_data.get("year_length", 360)

                # Calculate days into year
                days_into_year = 0

                # Add days from previous months
                for i in range(month - 1):
                    if i < len(month_days):
                        days_into_year += month_days[i]
                    else:
                        # Fallback value if month_days doesn't have enough entries
                        days_into_year += 30

                # Add days from current month
                days_into_year += day - 1  # -1 because day 1 is at start of month

                # Calculate year fraction
                year_fraction = days_into_year / year_length if year_length > 0 else 0
            else:
                # Fallback if no calendar data is available
                year_fraction = (month - 1) / 12

            # Calculate x position including the year fraction
            x_pos = (year - self.min_year + year_fraction) * self.pixels_per_year
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
        for event, card in events_with_cards:
            max_level = max(max_level, card.y() // 40)

        self.setMinimumHeight(140 + max_level * 40)

        self.updateGeometry()
        self.update()

        QTimer.singleShot(0, self.update)

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
            # Get basic event information
            year = event.get("parsed_date_year", self.min_year)
            month = event.get("parsed_date_month", 1)
            day = event.get("parsed_date_day", 1)

            # Calculate position with calendar awareness
            if hasattr(self, "calendar_data") and self.calendar_data:
                month_days = self.calendar_data.get("month_days", [])
                year_length = self.calendar_data.get("year_length", 360)

                # Calculate days into year
                days_into_year = 0

                # Add days from previous months
                for i in range(month - 1):
                    if i < len(month_days):
                        days_into_year += month_days[i]
                    else:
                        # Fallback value if month_days doesn't have enough entries
                        days_into_year += 30

                # Add days from current month
                days_into_year += day - 1  # -1 because day 1 is at start of month

                # Calculate year fraction
                year_fraction = days_into_year / year_length if year_length > 0 else 0
            else:
                # Fallback if no calendar data is available
                year_fraction = (month - 1) / 12

            # Calculate event center x-coordinate with year fraction
            x_pos = (year - self.min_year + year_fraction) * self.pixels_per_year

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
    """Widget displaying the time axis with markers at various detail levels"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.min_year = 0
        self.max_year = 100
        self.pixels_per_year = 50
        self.calendar_data = None  # Store calendar data
        self.setMinimumHeight(50)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_scale(self, pixels_per_year: float):
        """Set the horizontal scale for the axis"""
        self.pixels_per_year = pixels_per_year
        self.update()

    def set_year_range(self, min_year: int, max_year: int):
        """Set the year range for the axis"""
        self.min_year = min_year
        self.max_year = max_year
        self.update()

    def set_calendar_data(self, calendar_data: Dict[str, Any]) -> None:
        """Set calendar data for accurate month/day calculations"""
        self.calendar_data = calendar_data
        self.update()

    def paintEvent(self, event):
        """Draw the axis with year, month, or day markers based on zoom level"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Draw main axis line
        painter.setPen(QPen(QColor("#aaa"), 2))
        y_pos = 20
        painter.drawLine(0, y_pos, self.width(), y_pos)

        # Determine the visualization mode based on zoom level
        if self.pixels_per_year >= 300:
            self._draw_day_markers(painter, y_pos)
        elif self.pixels_per_year >= 100:
            self._draw_month_markers(painter, y_pos)
        else:
            self._draw_year_markers(painter, y_pos)

    def _draw_year_markers(self, painter, y_pos):
        """Draw year markers based on zoom level"""
        # Calculate appropriate interval based on pixels per year
        if self.pixels_per_year >= 100:
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

    def _draw_month_markers(self, painter, y_pos):
        """Draw month markers when zoomed in enough"""
        painter.setPen(QPen(QColor("#666"), 1))

        # Get visible year range (floor and ceiling)
        visible_min_year = int(self.min_year)
        visible_max_year = int(self.max_year) + 1

        # Get month names from calendar data or use defaults
        month_names = [
            "Jan",
            "Feb",
            "Mar",
            "Apr",
            "May",
            "Jun",
            "Jul",
            "Aug",
            "Sep",
            "Oct",
            "Nov",
            "Dec",
        ]

        if self.calendar_data and "month_names" in self.calendar_data:
            month_names = self.calendar_data["month_names"]
            # If we only have abbreviated versions, use those
            if all(len(name) <= 3 for name in month_names):
                pass
            else:
                # Create abbreviated versions
                month_names = [name[:3] for name in month_names]

        # Get number of months per year from calendar data or use default (12)
        months_per_year = 12
        if self.calendar_data and "months_per_year" in self.calendar_data:
            months_per_year = self.calendar_data["months_per_year"]

        # Draw month markers
        for year in range(visible_min_year, visible_max_year):
            for month in range(1, months_per_year + 1):
                # Calculate month position (year + month/months_per_year)
                x_pos = (
                    year - self.min_year + (month - 1) / months_per_year
                ) * self.pixels_per_year

                # Skip if outside visible area
                if x_pos < -50 or x_pos > self.width() + 50:
                    continue

                # Determine tick height and label visibility
                if month == 1:  # First month of year gets taller tick and year label
                    tick_height = 8
                    painter.setPen(QPen(QColor("#444"), 1.5))  # Darker for year start

                    # Draw year label (only at first month of year)
                    painter.drawText(
                        QRectF(x_pos - 20, y_pos - 25, 40, 20),
                        Qt.AlignmentFlag.AlignCenter,
                        str(year),
                    )
                else:
                    tick_height = 5
                    painter.setPen(QPen(QColor("#666"), 1))

                # Draw tick mark
                painter.drawLine(
                    int(x_pos), y_pos - tick_height, int(x_pos), y_pos + tick_height
                )

                # Draw month label (every 1, 3, or 6 months depending on zoom)
                draw_label = False
                if self.pixels_per_year >= 200:  # Very detailed, show every month
                    draw_label = True
                elif self.pixels_per_year >= 150:  # Detailed, show every other month
                    draw_label = month % 2 == 1
                else:  # Less detailed, show every quarter
                    draw_label = month % 3 == 1

                if draw_label and month <= len(month_names):
                    painter.drawText(
                        QRectF(x_pos - 15, y_pos + 10, 30, 20),
                        Qt.AlignmentFlag.AlignCenter,
                        month_names[month - 1],
                    )

    def _draw_day_markers(self, painter, y_pos):
        """Draw day markers when zoomed in very close"""
        painter.setPen(QPen(QColor("#666"), 1))

        # Get visible year range (floor and ceiling)
        visible_min_year = int(self.min_year)
        visible_max_year = int(self.max_year) + 1

        # Get month days from calendar data or use defaults
        month_days = [
            31,
            28,
            31,
            30,
            31,
            30,
            31,
            31,
            30,
            31,
            30,
            31,
        ]  # Standard calendar

        if self.calendar_data and "month_days" in self.calendar_data:
            month_days = self.calendar_data["month_days"]

        # Get month names for labels
        month_names = [
            "Jan",
            "Feb",
            "Mar",
            "Apr",
            "May",
            "Jun",
            "Jul",
            "Aug",
            "Sep",
            "Oct",
            "Nov",
            "Dec",
        ]

        if self.calendar_data and "month_names" in self.calendar_data:
            month_names = [name[:3] for name in self.calendar_data["month_names"]]

        # Calculate year_length for positioning
        year_length = sum(month_days)

        # For extremely zoomed in views, limit to displaying only a portion of the timeline
        visible_span = self.width() / self.pixels_per_year
        if visible_span < 0.5:  # Less than half a year visible
            # Determine day interval based on zoom level
            if self.pixels_per_year >= 800:
                day_interval = 1  # Every day
            elif self.pixels_per_year >= 500:
                day_interval = 2  # Every other day
            else:
                day_interval = 5  # Every fifth day

            # Draw day markers for visible range
            for year in range(visible_min_year, visible_max_year):
                day_in_year = 1
                for month_idx, days in enumerate(month_days):
                    month = month_idx + 1
                    for day in range(1, days + 1):
                        # Calculate day position
                        day_fraction = day_in_year / year_length
                        x_pos = (
                            year - self.min_year + day_fraction
                        ) * self.pixels_per_year

                        # Skip if outside visible area
                        if x_pos < -20 or x_pos > self.width() + 20:
                            day_in_year += 1
                            continue

                        # Only draw markers at specified intervals
                        if day % day_interval == 0 or day == 1:
                            # Taller tick for first day of month
                            tick_height = 7 if day == 1 else 3

                            # Darker tick for first day of month
                            if day == 1:
                                painter.setPen(QPen(QColor("#444"), 1.5))
                            else:
                                painter.setPen(QPen(QColor("#999"), 0.8))

                            # Draw tick mark
                            painter.drawLine(
                                int(x_pos),
                                y_pos - tick_height,
                                int(x_pos),
                                y_pos + tick_height,
                            )

                            # Draw day number (only at specified intervals)
                            if day == 1 or day % 5 == 0:
                                if day == 1:
                                    # Draw month name for first day
                                    painter.drawText(
                                        QRectF(x_pos - 15, y_pos - 20, 30, 20),
                                        Qt.AlignmentFlag.AlignCenter,
                                        month_names[month_idx],
                                    )

                                    # Also add year if first month
                                    if month == 1:
                                        painter.drawText(
                                            QRectF(x_pos - 20, y_pos - 35, 40, 20),
                                            Qt.AlignmentFlag.AlignCenter,
                                            str(year),
                                        )

                                # Draw day number
                                painter.drawText(
                                    QRectF(x_pos - 10, y_pos + 8, 20, 15),
                                    Qt.AlignmentFlag.AlignCenter,
                                    str(day),
                                )

                        day_in_year += 1
        else:
            # When more than half a year is visible, show simplified view with month divisions
            self._draw_month_markers(painter, y_pos)


class TimelineContent(QWidget):
    """Main widget containing the timeline content with lanes and axis"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.events = []
        self.event_types = set()  # Unique event types
        self.lanes = {}  # Maps event_type to TimelineLane
        self.min_year = 0
        self.max_year = 100
        self.pixels_per_year = 50.0  # Default scale
        self.calendar_data = None

        # Minimum and maximum zoom levels
        self.min_pixels_per_year = 1.0  # Most zoomed out
        self.max_pixels_per_year = 1500  # Most zoomed in

        # For panning support
        self.panning = False
        self.last_mouse_pos = None

        # Initialize UI
        self.setMinimumSize(800, 400)
        self.setup_ui()

        # Set up mouse tracking
        self.setMouseTracking(True)

    def set_calendar_data(self, calendar_data: Dict[str, Any]) -> None:
        """Set calendar data for date calculations"""
        self.calendar_data = calendar_data

        # Pass calendar data to the axis widget
        if hasattr(self, "axis") and hasattr(self.axis, "set_calendar_data"):
            self.axis.set_calendar_data(calendar_data)

        # Update existing lanes with calendar data
        for lane in self.lanes.values():
            lane.set_calendar_data(calendar_data)

        # Update display if we have events
        if self.events:
            self.update()

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

        # Set initial scale based on selected option
        if scale == "Decades":
            self.pixels_per_year = 5
        elif scale == "Years":
            self.pixels_per_year = 50
        elif scale == "Months":
            self.pixels_per_year = 100
        elif scale == "Days":
            self.pixels_per_year = 500
        else:
            self.pixels_per_year = 50  # Default to years

        # Update axis
        self.axis.set_year_range(self.min_year, self.max_year)
        self.axis.set_scale(self.pixels_per_year)

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

            # Create lane
            lane = TimelineLane(event_type)
            lane.set_year_range(self.min_year, self.max_year)
            lane.set_scale(self.pixels_per_year)

            # Pass calendar data if available
            if self.calendar_data:
                lane.set_calendar_data(self.calendar_data)

            lane.add_events(type_events)

            # Add to layout before the stretch
            self.layout.insertWidget(self.layout.count() - 1, lane)

            # Store in dictionary
            self.lanes[event_type] = lane

        # Update widget size
        self.updateGeometry()
        self.update()

        # Notify parent after layout has been processed
        QTimer.singleShot(10, self._notify_parent)

    def _notify_parent(self):
        """Notify parent that lanes have been updated after layout processing"""
        if hasattr(self.parent(), "on_lanes_changed"):
            self.parent().on_lanes_changed()

    def _notify_lanes_changed(self):
        """Notify parent widget that lanes have changed after layout is updated"""
        if hasattr(self.parent(), "on_lanes_changed"):
            self.parent().on_lanes_changed()

    def sizeHint(self):
        """Calculate size based on timeline span and lanes"""
        width = (
            self.max_year - self.min_year
        ) * self.pixels_per_year + 200  # Add margin
        height = 50  # Start with axis height

        # Add height for each lane
        for lane in self.lanes.values():
            height += lane.minimumHeight()

        return QSize(int(width), int(height))

    def wheelEvent(self, event: QWheelEvent):
        """Handle mouse wheel for zooming"""
        # Get mouse position for zoom focus
        mouse_pos = event.position()

        # Calculate year at cursor position before zoom
        year_at_cursor = self.min_year + (mouse_pos.x() / self.pixels_per_year)

        # Calculate new scale
        delta = event.angleDelta().y()
        zoom_factor = 1.0 + (delta / 800)  # Smoother zoom rate
        new_scale = self.pixels_per_year * zoom_factor

        # Apply new scale
        self.set_scale(new_scale)

        # Adjust min_year to keep the year under cursor at the same position
        new_x = mouse_pos.x()
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

            # Update last position
            self.last_mouse_pos = event.position()
            self.update()
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

        # Add widgets to container
        container_layout.addWidget(self.labels_area)
        container_layout.addWidget(self.scroll_area)

        # Add container to main layout
        layout.addWidget(container)

        # Connect scroll signal
        self.scroll_area.verticalScrollBar().valueChanged.connect(self.update_labels)

        # Dictionary to track labels
        self.lane_labels = {}

    def on_lanes_changed(self):
        """Handle changes in timeline lanes"""
        # Clear existing labels
        self.clear_lane_labels()

        # Create new labels for each lane
        for lane in self.content.lanes.values():
            self.add_lane_label(lane)

        # Update positions
        self.update_labels(self.scroll_area.verticalScrollBar().value())

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

    def update_labels(self, scroll_value):
        """Update label positions based on current scroll position"""
        if not self.content or not hasattr(self.content, "lanes"):
            logger.debug("update_labels: No content or lanes found")
            return

        # Use QTimer.singleShot to wait for layout to settle
        QTimer.singleShot(0, lambda: self._update_labels_after_layout(scroll_value))

    def _update_labels_after_layout(self, scroll_value):
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
        self.update_labels(self.scroll_area.verticalScrollBar().value())

    def set_data(
        self,
        events: List[Dict[str, Any]],
        scale: str,
        calendar_data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Update the timeline with new data"""
        logger.debug(
            "TimelineWidget.set_data called",
            event_count=len(events),
            scale=scale,
            has_calendar_data=calendar_data is not None,
        )

        # Set calendar data first so it's available when processing events
        if calendar_data:
            self.content.set_calendar_data(calendar_data)

        self.content.set_data(events, scale)

        # Update labels for new lanes
        self.on_lanes_changed()
