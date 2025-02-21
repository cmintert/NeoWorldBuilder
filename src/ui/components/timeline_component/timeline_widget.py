from typing import List, Optional, Dict, Any, Tuple
from PyQt6.QtWidgets import (
    QWidget,
    QScrollArea,
    QVBoxLayout,
    QApplication,
)
from PyQt6.QtCore import Qt, QRectF, QEvent
from PyQt6.QtGui import QPainter, QPen, QColor, QFontMetrics
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

        # Add panning variables
        self.panning = False
        self.last_mouse_pos = None

        # Add zoom control properties
        self.zoom_level = 1.0  # Default zoom level
        self.min_zoom = 0.1
        self.max_zoom = 10.0
        self.pixels_per_year_base = 50  # Base scaling factor

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
        self.setMouseTracking(True)
        self._setup_widget()

    def wheelEvent(self, event):
        """Handle mouse wheel for zooming"""
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            # Add debug logging
            logger.debug(
                "Timeline content wheel event",
                zoom_level_before=self.zoom_level,
                mouse_x=event.position().x(),
                delta_y=event.angleDelta().y(),
            )

            # Calculate zoom factor based on wheel delta
            zoom_factor = 1.1 if event.angleDelta().y() > 0 else 0.9

            # Get mouse position for zoom center
            mouse_x = event.position().x()

            # Calculate year at mouse position before zoom
            year_at_mouse = self._get_year_at_position(mouse_x)

            # Apply zoom
            old_zoom = self.zoom_level
            self.zoom_level = max(
                self.min_zoom, min(self.max_zoom, self.zoom_level * zoom_factor)
            )

            # Add more debug logging
            logger.debug(
                "Zoom calculation",
                old_zoom=old_zoom,
                new_zoom=self.zoom_level,
                year_at_mouse=year_at_mouse,
            )

            # Only proceed if zoom actually changed
            if old_zoom != self.zoom_level:
                # Recalculate positions and update
                self._calculate_event_positions()

                # Calculate scroll adjustment
                new_x = self._get_x_position(int(year_at_mouse))
                delta_x = new_x - mouse_x

                # Get scroll area and scrollbar
                scroll_area = self.parent().parent()
                scrollbar = scroll_area.horizontalScrollBar()

                # Set new scroll value
                new_scroll_value = int(scrollbar.value() + delta_x)
                scrollbar.setValue(new_scroll_value)

                # Force immediate UI updates
                self.update()
                scroll_area.viewport().update()
                scroll_area.update()

                # Process pending events to ensure updates are rendered
                QApplication.processEvents()

            event.accept()
            super().wheelEvent(event)
        else:
            event.ignore()
            super().wheelEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.panning = True
            self.last_mouse_pos = event.pos()
            self.setCursor(Qt.ClosedHandCursor)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.panning = False
            self.setCursor(Qt.ArrowCursor)

    def mouseMoveEvent(self, event):
        if self.panning:
            delta = event.pos() - self.last_mouse_pos
            scrollbar = self.parent().horizontalScrollBar()
            scrollbar.setValue(scrollbar.value() - delta.x())
            self.last_mouse_pos = event.pos()

    def _get_pixels_per_year(self) -> float:
        """Get dynamic pixels per year based on zoom level"""
        return self.pixels_per_year_base * self.zoom_level

    def _get_year_at_position(self, x: float) -> float:
        """Convert x coordinate to year"""
        usable_width = self.width() - (self.PADDING * 2)
        year_span = self.max_year - self.min_year
        year = ((x - self.PADDING) / usable_width * year_span) + self.min_year
        return year

    def _setup_widget(self):
        """Initialize widget properties."""
        self.setAutoFillBackground(True)
        palette = self.palette()
        palette.setColor(self.backgroundRole(), Qt.GlobalColor.white)
        self.setPalette(palette)
        self.setMouseTracking(True)

    def set_data(self, events: List[Dict[str, Any]], scale: str) -> None:
        """Set timeline data with improved range calculation."""
        logger.debug(
            "Timeline content set_data",
            event_count=len(events) if events else 0,
            old_scale=self.scale,
            new_scale=scale,
        )

        old_scale = self.scale
        self.events = events
        self.scale = scale

        # Force recalculation of dimensions if scale changed
        if old_scale != scale:
            pixels_per_year = self._get_pixels_per_year()
            width = (self.max_year - self.min_year) * pixels_per_year + self.PADDING * 2
            self.setMinimumWidth(int(max(width, 800)))

            # Clear cache and force recalculation
            self.event_layout_cache.clear()
            self._calculate_event_positions()

            # Force complete redraw
            self.update()

            # Update parent scroll area
            if self.parent():
                self.parent().update()

            logger.debug(
                "Scale change applied", new_width=width, pixels_per_year=pixels_per_year
            )

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
        self.setMinimumWidth(int(max(width, 800)))

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
        """Get dynamic pixels per year based on scale and zoom."""
        base_pixels = {"Decades": 5, "Years": 50, "Months": 100, "Days": 200}
        # Apply zoom level to base pixels
        pixels = base_pixels.get(self.scale, 50) * self.zoom_level

        logger.debug(
            "Getting pixels per year",
            scale=self.scale,
            base_pixels=base_pixels.get(self.scale, 50),
            zoom_level=self.zoom_level,
            final_pixels=pixels,
        )

        return pixels

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

        # Draw baseline
        base_y = self.height() // 2
        painter.setPen(QPen(Qt.GlobalColor.black, 2))
        painter.drawLine(self.PADDING, base_y, self.width() - self.PADDING, base_y)

        # Draw scale based on current view
        self._draw_scale(painter, base_y)

        # Draw events
        if self.events:
            self._draw_events(painter, base_y)

    def _draw_scale(self, painter: QPainter, base_y: int) -> None:
        """Draw improved timeline grid with adaptive intervals"""
        pixels_per_year = self._get_pixels_per_year()

        logger.debug(
            "Drawing scale",
            scale=self.scale,
            pixels_per_year=pixels_per_year,
            zoom_level=self.zoom_level,
        )

        # Calculate optimal interval based on zoom level
        min_pixels_between_lines = 80
        interval = 1
        while (interval * pixels_per_year) < min_pixels_between_lines:
            if interval < 10:
                interval += 1
            elif interval < 100:
                interval += 10
            else:
                interval += 100

        # Draw vertical grid lines
        painter.setPen(QPen(QColor(200, 200, 200), 1))  # Light gray
        start_year = (self.min_year // interval) * interval

        for year in range(start_year, self.max_year + interval, interval):
            x = self._get_x_position(year)

            # Only draw if in visible area
            if self.visible_rect.left() - 10 <= x <= self.visible_rect.right() + 10:
                # Draw vertical line
                painter.drawLine(x, 0, x, self.height())

                # Draw year label
                painter.setPen(Qt.GlobalColor.black)
                painter.drawText(x - 20, 20, str(year))

        # Draw major intervals with darker lines
        major_interval = interval * 5
        painter.setPen(QPen(QColor(150, 150, 150), 1))  # Darker gray

        for year in range(start_year, self.max_year + major_interval, major_interval):
            x = self._get_x_position(year)
            if self.visible_rect.left() - 10 <= x <= self.visible_rect.right() + 10:
                painter.drawLine(x, 0, x, self.height())

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
        # Use scaled pixels per year
        position = (((year - self.min_year) / year_span) * usable_width) + self.PADDING

        logger.debug(
            "Calculating x position",
            year=year,
            scale=self.scale,
            pixels_per_year=self._get_pixels_per_year(),
            position=position,
        )

        return int(position)


class TimelineWidget(QWidget):
    def __init__(self):
        super().__init__()
        self._setup_ui()

    def _setup_ui(self):
        """Setup the UI components."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Create scroll area with explicit policy settings
        self.scroll_area = QScrollArea()
        self.scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOn
        )
        self.scroll_area.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.scroll_area.setWidgetResizable(True)

        # Make sure viewport accepts wheel events
        self.scroll_area.viewport().setAttribute(
            Qt.WidgetAttribute.WA_AcceptTouchEvents, False
        )
        self.scroll_area.viewport().setFocusPolicy(Qt.FocusPolicy.WheelFocus)

        # Create and set content widget
        self.content = TimelineContent()
        self.scroll_area.setWidget(self.content)

        # Enable mouse tracking
        self.scroll_area.setMouseTracking(True)
        self.scroll_area.viewport().setMouseTracking(True)

        # Install event filter
        self.scroll_area.viewport().installEventFilter(self)

        layout.addWidget(self.scroll_area)

    def eventFilter(self, obj, event):
        """Filter events to pass wheel events to content widget when Ctrl is pressed"""
        if (
            obj == self.scroll_area.viewport()
            and event.type() == QEvent.Type.Wheel
            and event.modifiers() & Qt.KeyboardModifier.ControlModifier
        ):
            # Add debug logging
            logger.debug(
                "Wheel event received",
                ctrl_pressed=bool(
                    event.modifiers() & Qt.KeyboardModifier.ControlModifier
                ),
                delta_y=event.angleDelta().y(),
            )
            self.content.wheelEvent(event)
            return True
        return super().eventFilter(obj, event)

    def set_data(self, events: List[Dict[str, Any]], scale: str) -> None:
        """Update the timeline with new data.

        Delegates to the content widget's set_data method.
        """
        self.content.set_data(events, scale)
