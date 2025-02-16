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
from PyQt6.QtGui import QPainter, QPen, QColor, QPainterPath
from structlog import get_logger

logger = get_logger(__name__)


class TimelineContent(QWidget):
    """The actual content widget containing the timeline visualization."""

    def __init__(self):
        super().__init__()
        self.events = []
        self.scale = "Years"
        self.min_year = None
        self.max_year = None
        self.setMinimumHeight(200)

        # Set white background
        self.setAutoFillBackground(True)
        palette = self.palette()
        palette.setColor(self.backgroundRole(), Qt.GlobalColor.white)
        self.setPalette(palette)

        # Enable mouse tracking for tooltips
        self.setMouseTracking(True)

    def set_data(self, events: List[Dict[str, Any]], scale: str) -> None:
        """Set the timeline data and trigger redraw."""
        self.events = events
        self.scale = scale

        # Calculate year range
        if events:
            years = [int(event.get("parsed_date_year", 0)) for event in events]
            self.min_year = min(years) if years else None
            self.max_year = max(years) if years else None

            # Adjust width based on scale and range
            if self.min_year and self.max_year:
                if scale == "Decades":
                    width = (self.max_year - self.min_year) // 10 * 100 + 200
                elif scale == "Years":
                    width = (self.max_year - self.min_year) * 100 + 200
                elif scale == "Months":
                    width = (self.max_year - self.min_year) * 1200 + 200
                else:  # Days
                    width = (self.max_year - self.min_year) * 36500 + 200

                self.setMinimumWidth(max(width, 800))

        self.update()

    def paintEvent(self, event):
        """Draw the timeline visualization."""
        if not self.events or self.min_year is None or self.max_year is None:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Draw timeline base line
        base_y = self.height() // 2
        painter.setPen(QPen(Qt.GlobalColor.black, 2))
        painter.drawLine(50, base_y, self.width() - 50, base_y)

        # Calculate scale and intervals
        if self.scale == "Decades":
            self._draw_decade_scale(painter, base_y)
        elif self.scale == "Years":
            self._draw_year_scale(painter, base_y)
        elif self.scale == "Months":
            self._draw_month_scale(painter, base_y)
        else:  # Days
            self._draw_day_scale(painter, base_y)

        # Draw events
        self._draw_events(painter, base_y)

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

    def _draw_year_scale(self, painter: QPainter, base_y: int) -> None:
        """Draw year markers and labels."""
        for year in range(self.min_year, self.max_year + 1):
            x = self._get_x_position(year)

            # Draw marker
            painter.setPen(QPen(Qt.GlobalColor.black, 1))
            painter.drawLine(x, base_y - 5, x, base_y + 5)

            # Draw label every 5 years
            if year % 5 == 0:
                painter.drawText(x - 15, base_y + 20, str(year))

    def _draw_month_scale(self, painter: QPainter, base_y: int) -> None:
        """Draw month markers and labels."""
        # Implementation depends on calendar data
        # For now, just draw year divisions
        for year in range(self.min_year, self.max_year + 1):
            x = self._get_x_position(year)
            painter.setPen(QPen(Qt.GlobalColor.black, 1))
            painter.drawLine(x, base_y - 10, x, base_y + 10)
            painter.drawText(x - 15, base_y + 25, str(year))

    def _draw_day_scale(self, painter: QPainter, base_y: int) -> None:
        """Draw day markers and labels."""
        # Implementation depends on calendar data
        # For now, just draw month divisions
        for year in range(self.min_year, self.max_year + 1):
            x = self._get_x_position(year)
            painter.setPen(QPen(Qt.GlobalColor.black, 1))
            painter.drawLine(x, base_y - 10, x, base_y + 10)
            painter.drawText(x - 15, base_y + 25, str(year))

    def _get_x_position(self, year: int) -> int:
        """Calculate x position for a given year based on current scale."""
        total_width = self.width() - 100  # Margin on both sides
        year_span = self.max_year - self.min_year
        if year_span == 0:
            year_span = 1

        position = (year - self.min_year) / year_span * total_width + 50
        return int(position)

    def _draw_events(self, painter: QPainter, base_y: int) -> None:
        """Draw event markers on the timeline."""
        marker_radius = 5

        for event in self.events:
            year = int(event.get("parsed_date_year", 0))
            x = self._get_x_position(year)

            # Draw event marker
            painter.setPen(QPen(Qt.GlobalColor.blue, 2))
            painter.setBrush(Qt.GlobalColor.white)
            painter.drawEllipse(
                x - marker_radius,
                base_y - marker_radius,
                marker_radius * 2,
                marker_radius * 2,
            )


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
        self.content.set_data(events, scale)
