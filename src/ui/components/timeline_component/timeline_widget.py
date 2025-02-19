from typing import List, Optional, Dict, Any
from PyQt6.QtWidgets import (
    QWidget,
    QScrollArea,
    QHBoxLayout,
    QVBoxLayout,
    QLabel,
    QFrame,
)
from PyQt6.QtCore import Qt, QSize, QRectF
from PyQt6.QtGui import QPainter, QPen, QColor, QPainterPath, QFont
from structlog import get_logger

logger = get_logger(__name__)


class TimelineContent(QWidget):
    """The actual content widget containing the timeline visualization."""

    def __init__(self):
        super().__init__()
        self.events = []
        self.scale = "Years"
        # Initialize with default values
        self.default_span = 1500  # Show 100 years by default
        self.default_year = 0  # Center point for empty timeline
        self.min_year = self.default_year - self.default_span // 2
        self.max_year = self.default_year + self.default_span // 2

        self.setMinimumHeight(200)
        self.padding = 2  # Padding on both sides
        self.marker_radius = 5
        self.label_padding = 25  # Space for labels

        # Set white background
        self.setAutoFillBackground(True)
        palette = self.palette()
        palette.setColor(self.backgroundRole(), Qt.GlobalColor.white)
        self.setPalette(palette)

        # Enable mouse tracking for tooltips
        self.setMouseTracking(True)

    def set_data(self, events: List[Dict[str, Any]], scale: str) -> None:
        """Set the timeline data and trigger redraw."""
        logger.debug(
            "TimelineContent received data",
            event_count=len(events),
            event_details=[
                {
                    "name": e.get("name"),
                    "year": e.get("parsed_date_year"),
                    "full_event": e,
                }
                for e in events
            ],
        )

        self.events = events
        self.scale = scale

        # Calculate width and year range
        if events:
            # Extract years from events
            years = [int(event.get("parsed_date_year", 0)) for event in events]
            if years:  # Check if we got valid years
                self.min_year = min(years)
                self.max_year = max(years)

                # Add padding years for better visualization
                year_span = self.max_year - self.min_year
                padding_years = max(year_span * 0.1, 10)  # At least 10 years padding
                self.min_year = int(self.min_year - padding_years)
                self.max_year = int(self.max_year + padding_years)
            else:
                # Fallback to defaults if no valid years
                self.min_year = self.default_year - self.default_span // 2
                self.max_year = self.default_year + self.default_span // 2
        else:
            # Set default range when no events
            self.min_year = self.default_year - self.default_span // 2
            self.max_year = self.default_year + self.default_span // 2

        # Calculate width based on scale and range
        pixels_per_year = self._get_pixels_per_year()
        width = (self.max_year - self.min_year) * pixels_per_year + self.padding * 2
        self.setMinimumWidth(max(width, 800))

        logger.debug(
            "Timeline dimensions calculated",
            min_year=self.min_year,
            max_year=self.max_year,
            width=width,
            scale=self.scale,
            pixels_per_year=pixels_per_year,
        )

        self.update()

    def _get_pixels_per_year(self) -> int:
        """Get pixels per year based on current scale."""
        if self.scale == "Decades":
            return 5
        elif self.scale == "Years":
            return 50
        elif self.scale == "Months":
            return 200
        else:  # Days
            return 600

    def paintEvent(self, event):
        """Draw the timeline visualization."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Draw timeline base line
        base_y = self.height() // 2
        painter.setPen(QPen(Qt.GlobalColor.black, 2))
        painter.drawLine(self.padding, base_y, self.width() - self.padding, base_y)

        # Calculate scale and intervals
        if self.scale == "Decades":
            self._draw_decade_scale(painter, base_y)
        elif self.scale == "Years":
            self._draw_year_scale(painter, base_y)
        elif self.scale == "Months":
            self._draw_month_scale(painter, base_y)
        else:  # Days
            self._draw_day_scale(painter, base_y)

        # Draw events if we have any
        if self.events:
            self._draw_events(painter, base_y)

    def _draw_year_scale(self, painter: QPainter, base_y: int) -> None:
        """Draw year markers and labels."""
        year_span = self.max_year - self.min_year
        interval = max(1, year_span // 20)  # Show max 20 year labels

        for year in range(self.min_year, self.max_year + 1, interval):
            x = self._get_x_position(year)

            # Draw marker
            painter.setPen(QPen(Qt.GlobalColor.black, 1))
            painter.drawLine(x, base_y - 5, x, base_y + 5)

            # Draw year label
            painter.drawText(x - 20, base_y + 20, str(year))

    def _draw_decade_scale(self, painter: QPainter, base_y: int) -> None:
        """Draw decade markers and labels."""
        start_decade = (self.min_year // 10) * 10
        end_decade = ((self.max_year + 9) // 10) * 10

        for decade in range(start_decade, end_decade + 1, 10):
            x = self._get_x_position(decade)

            # Draw marker
            painter.setPen(QPen(Qt.GlobalColor.black, 1))
            painter.drawLine(x, base_y - 10, x, base_y + 10)

            # Draw label
            painter.drawText(x - 20, base_y + 25, f"{decade}s")

    def _get_x_position(self, year: int) -> int:
        """Calculate x position for a given year based on current scale."""
        usable_width = self.width() - (self.padding * 2)
        year_span = self.max_year - self.min_year
        if year_span == 0:
            year_span = 1

        position = (((year - self.min_year) / year_span) * usable_width) + self.padding

        return int(position)

    def _draw_events(self, painter: QPainter, base_y: int) -> None:
        """Draw event markers and labels on the timeline."""
        for event in self.events:
            year = event.get("parsed_date_year", 0)
            if not year:
                continue

            x = self._get_x_position(int(year))

            # Draw vertical connection line
            line_height = 30
            painter.setPen(QPen(Qt.GlobalColor.gray, 1))
            painter.drawLine(x, base_y - line_height, x, base_y + line_height)

            # Draw event marker
            painter.setPen(QPen(Qt.GlobalColor.blue, 2))
            painter.setBrush(Qt.GlobalColor.white)
            painter.drawEllipse(
                x - self.marker_radius,
                base_y - self.marker_radius,
                self.marker_radius * 2,
                self.marker_radius * 2,
            )

            # Draw event name - alternate above/below timeline
            text = f"{event.get('name', 'Unknown')} ({year})"
            text_width = painter.fontMetrics().horizontalAdvance(text)
            text_x = x - (text_width / 2)

            # Alternate text position above/below timeline
            index = self.events.index(event)
            if index % 2 == 0:
                text_y = base_y - line_height - 5
            else:
                text_y = base_y + line_height + 15

            painter.drawText(int(text_x), int(text_y), text)


class TimelineWidget(QWidget):
    """Widget containing the scrollable timeline visualization."""

    def __init__(self):
        super().__init__()
        self._setup_ui()

    def _setup_ui(self):
        """Setup the UI components."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Create scroll area
        self.scroll_area = QScrollArea()
        self.scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOn
        )
        self.scroll_area.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.scroll_area.setWidgetResizable(True)

        # Create and set content widget
        self.content = TimelineContent()
        self.scroll_area.setWidget(self.content)

        layout.addWidget(self.scroll_area)

    def set_data(self, events: List[Dict[str, Any]], scale: str) -> None:
        """Update the timeline with new data."""
        logger.debug(
            "TimelineWidget.set_data called",
            event_count=len(events),
            scale=scale,
            events=events,
        )
        self.content.set_data(events, scale)
