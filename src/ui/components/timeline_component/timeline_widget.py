from typing import List, Optional, Dict, Any, Tuple
from PyQt6.QtWidgets import (
    QWidget,
    QScrollArea,
    QHBoxLayout,
    QVBoxLayout,
    QLabel,
    QFrame,
)
from PyQt6.QtCore import Qt, QSize, QRectF
from PyQt6.QtGui import QPainter, QPen, QColor, QPainterPath, QFont, QFontMetrics
from structlog import get_logger

logger = get_logger(__name__)


class TimelineContent(QWidget):
    """Optimized timeline visualization widget."""

    def __init__(self):
        super().__init__()
        self.events = []
        self.scale = "Years"
        self.visible_rect = QRectF()  # Track visible area
        self.event_layout_cache = {}  # Cache event positions

        # Visualization constants
        self.PADDING = 40  # Increased padding for better spacing
        self.MARKER_RADIUS = 6
        self.MIN_LABEL_SPACING = 80  # Minimum pixels between labels
        self.LEVEL_HEIGHT = 30  # Height for each level of events

        # Default range
        self.default_span = 500
        self.default_year = 0
        self.min_year = self.default_year - self.default_span // 2
        self.max_year = self.default_year + self.default_span // 2

        # Setup widget
        self.setMinimumHeight(300)  # Increased minimum height
        self._setup_widget()

    def _setup_widget(self):
        """Initialize widget properties."""
        self.setAutoFillBackground(True)
        palette = self.palette()
        palette.setColor(self.backgroundRole(), Qt.GlobalColor.white)
        self.setPalette(palette)
        self.setMouseTracking(True)

    def set_data(self, events: List[Dict[str, Any]], scale: str) -> None:
        """Set timeline data with improved range calculation."""
        self.events = events
        self.scale = scale

        if events:
            # Extract and validate years
            years = [
                int(event.get("parsed_date_year", 0))
                for event in events
                if event.get("parsed_date_year") is not None
            ]

            if years:
                self.min_year = min(years)
                self.max_year = max(years)

                # Calculate padding based on time range
                year_span = self.max_year - self.min_year
                padding_years = max(year_span * 0.1, 5)  # At least 5 years padding
                self.min_year = int(self.min_year - padding_years)
                self.max_year = int(self.max_year + padding_years)
            else:
                self._set_default_range()
        else:
            self._set_default_range()

        # Calculate widget width
        pixels_per_year = self._get_pixels_per_year()
        width = (self.max_year - self.min_year) * pixels_per_year + self.PADDING * 2
        self.setMinimumWidth(max(width, 800))

        # Clear layout cache
        self.event_layout_cache.clear()

        # Calculate event positions
        self._calculate_event_positions()

        self.update()

    def _set_default_range(self):
        """Set default time range."""
        self.min_year = self.default_year - self.default_span // 2
        self.max_year = self.default_year + self.default_span // 2

    def _get_pixels_per_year(self) -> float:
        """Get dynamic pixels per year based on scale."""
        if self.scale == "Decades":
            return 5
        elif self.scale == "Years":
            return 50
        elif self.scale == "Months":
            return 100
        else:  # Days
            return 200

    def _calculate_event_positions(self) -> None:
        """Calculate and cache event positions using improved layout algorithm."""
        if not self.events:
            return

        # Sort events by date
        sorted_events = sorted(
            self.events,
            key=lambda e: (
                e.get("parsed_date_year", 0),
                e.get("parsed_date_month", 0),
                e.get("parsed_date_day", 0),
            ),
        )

        # Track occupied spaces for each level
        levels: List[List[Tuple[float, float]]] = [
            []
        ]  # List of (start_x, end_x) tuples

        for event in sorted_events:
            x = self._get_x_position(event.get("parsed_date_year", 0))
            text = (
                f"{event.get('name', 'Unknown')} ({event.get('parsed_date_year', '?')})"
            )

            # Calculate text width
            metrics = QFontMetrics(self.font())
            text_width = metrics.horizontalAdvance(text)

            # Calculate space needed
            space_start = x - text_width / 2 - self.PADDING
            space_end = x + text_width / 2 + self.PADDING

            # Find level for event
            level = 0
            space_found = False

            while not space_found:
                if level >= len(levels):
                    levels.append([])
                    space_found = True
                else:
                    # Check if space is available at current level
                    space_available = True
                    for used_space in levels[level]:
                        if not (
                            space_end < used_space[0] or space_start > used_space[1]
                        ):
                            space_available = False
                            break

                    if space_available:
                        space_found = True
                    else:
                        level += 1

            # Add event position to cache and occupied spaces
            self.event_layout_cache[event.get("name")] = {
                "x": x,
                "level": level,
                "text": text,
                "text_width": text_width,
            }
            levels[level].append((space_start, space_end))

        # Update widget height based on number of levels
        total_height = (len(levels) + 1) * self.LEVEL_HEIGHT + self.PADDING * 2
        self.setMinimumHeight(max(300, total_height))

    def paintEvent(self, event):
        """Optimized paint event with improved scale drawing."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Get visible rect
        self.visible_rect = event.rect()

        # Draw base line
        base_y = self.height() // 2
        painter.setPen(QPen(Qt.GlobalColor.black, 2))
        painter.drawLine(self.PADDING, base_y, self.width() - self.PADDING, base_y)

        # Draw scale based on current view
        self._draw_scale(painter, base_y)

        # Draw events
        if self.events:
            self._draw_events(painter, base_y)

    def _draw_scale(self, painter: QPainter, base_y: int) -> None:
        """Draw year markers and labels."""
        year_span = self.max_year - self.min_year

        # Choose interval based on span
        if year_span <= 20:
            interval = 1
        elif year_span <= 100:
            interval = 5
        elif year_span <= 500:
            interval = 10
        elif year_span <= 2000:
            interval = 50
        else:
            interval = 100

        # Calculate start year to align with interval
        start_year = (self.min_year // interval) * interval
        if start_year < self.min_year:
            start_year += interval

        for year in range(start_year, self.max_year + 1, interval):
            x = self._get_x_position(year)

            # Draw marker
            painter.setPen(QPen(Qt.GlobalColor.black, 1))
            painter.drawLine(x, base_y - 5, x, base_y + 5)

            # Draw year label
            painter.drawText(x - 20, base_y + 20, str(year))

    def _draw_events(self, painter: QPainter, base_y: int) -> None:
        """Draw events using cached positions."""
        visible_min_x = self.visible_rect.x()
        visible_max_x = self.visible_rect.x() + self.visible_rect.width()

        for event in self.events:
            event_cache = self.event_layout_cache.get(event.get("name"))
            if not event_cache:
                continue

            x = event_cache["x"]

            # Skip if event is not visible
            if x < visible_min_x - 100 or x > visible_max_x + 100:
                continue

            level = event_cache["level"]
            text = event_cache["text"]
            text_width = event_cache["text_width"]

            # Calculate y position based on level
            y_offset = (level + 1) * self.LEVEL_HEIGHT * (1 if level % 2 == 0 else -1)
            text_y = base_y + y_offset

            # Draw connection line
            painter.setPen(QPen(Qt.GlobalColor.gray, 1))
            painter.drawLine(x, base_y, x, text_y)

            # Draw event marker
            painter.setPen(QPen(Qt.GlobalColor.blue, 2))
            painter.setBrush(Qt.GlobalColor.white)
            painter.drawEllipse(
                x - self.MARKER_RADIUS,
                base_y - self.MARKER_RADIUS,
                self.MARKER_RADIUS * 2,
                self.MARKER_RADIUS * 2,
            )

            # Draw text
            painter.drawText(
                int(x - text_width / 2),
                int(text_y + (5 if level % 2 == 0 else -5)),
                text,
            )

    def _get_x_position(self, year: int) -> int:
        """Calculate x position for a given year."""
        usable_width = self.width() - (self.PADDING * 2)
        year_span = max(1, self.max_year - self.min_year)
        position = (((year - self.min_year) / year_span) * usable_width) + self.PADDING
        return int(position)


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
