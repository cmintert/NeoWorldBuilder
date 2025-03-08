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
        self.setMinimumHeight(140)
        self.setup_ui()

    def setup_ui(self):
        """Set up the lane UI elements"""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 5, 0, 15)  # Add bottom margin for connection lines

        # Category label on the left
        self.label = QLabel(self.category)
        self.label.setStyleSheet("font-weight: bold; color: #555;")
        self.label.setFixedWidth(120)
        self.label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)

        # Content area for events
        self.content_area = QWidget()
        self.content_area.setMinimumHeight(120)

        layout.addWidget(self.label)
        layout.addWidget(self.content_area, 1)  # Content area stretches

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
            card = EventCard(event, self.content_area)
            self.cards.append(card)

        # Position the cards
        self.position_event_cards()

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

            # Calculate x position based on year
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
        for event, card in events_with_cards:
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

    def paintEvent(self, event):
        """Draw the axis and year markers"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Draw main axis line
        painter.setPen(QPen(QColor("#aaa"), 2))
        y_pos = 20
        painter.drawLine(0, y_pos, self.width(), y_pos)

        # Calculate marker interval based on zoom level
        year_span = self.max_year - self.min_year
        width_in_pixels = year_span * self.pixels_per_year

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

        # Minimum and maximum zoom levels
        self.min_pixels_per_year = 1.0  # Most zoomed out
        self.max_pixels_per_year = 200.0  # Most zoomed in

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
            self.pixels_per_year = 200
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

        # Create new lanes for each event type
        for event_type in sorted(self.event_types):
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
            lane.add_events(type_events)

            # Add to layout before the stretch
            self.layout.insertWidget(self.layout.count() - 1, lane)

            # Store in dictionary
            self.lanes[event_type] = lane

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
        zoom_factor = 1.0 + (delta / 1200.0)  # Smoother zoom rate
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

        layout.addWidget(self.scroll_area)

    def set_data(self, events: List[Dict[str, Any]], scale: str) -> None:
        """Update the timeline with new data"""
        logger.debug(
            "TimelineWidget.set_data called", event_count=len(events), scale=scale
        )
        self.content.set_data(events, scale)
