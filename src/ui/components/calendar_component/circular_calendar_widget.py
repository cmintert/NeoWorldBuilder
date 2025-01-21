from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QFrame,
                             QScrollArea, QHBoxLayout)
from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QPainter, QColor, QPen, QFont, QPainterPath
import math

class CircularMonthView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.months_data = []
        self.setMinimumSize(400, 400)

    def set_data(self, months_data):
        """Set the months data and trigger repaint"""
        self.months_data = months_data
        self.update()

    def paintEvent(self, event):
        if not self.months_data:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Calculate center and radius
        center_x = self.width() / 2
        center_y = self.height() / 2
        radius = min(center_x, center_y) - 50

        # Colors for the months
        colors = [
            "#FF9AA2", "#FFB7B2", "#FFDAC1", "#E2F0CB",
            "#B5EAD7", "#C7CEEA", "#E2F0CB", "#B5EAD7",
            "#C7CEEA", "#FF9AA2", "#FFB7B2", "#FFDAC1"
        ]

        # Calculate total days for angle calculation
        total_days = sum(days for _, days in self.months_data)
        start_angle = 0

        for i, (name, days) in enumerate(self.months_data):
            # Calculate sweep angle based on days in month
            sweep_angle = (days / total_days) * 360

            # Draw segment
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(colors[i % len(colors)]))

            # Create arc path for segment
            path = QPainterPath()
            path.moveTo(center_x, center_y)
            path.arcTo(
                QRectF(
                    center_x - radius,
                    center_y - radius,
                    radius * 2,
                    radius * 2
                ),
                -start_angle,
                -sweep_angle
            )
            path.lineTo(center_x, center_y)
            painter.drawPath(path)

            # Draw month label
            label_angle = start_angle + sweep_angle / 2
            label_radius = radius * 0.7

            # Convert to radians and adjust for Qt's coordinate system
            rad_angle = math.radians(-label_angle)
            label_x = center_x + math.cos(rad_angle) * label_radius
            label_y = center_y + math.sin(rad_angle) * label_radius

            # Configure text rendering
            painter.setPen(QColor("#333333"))
            font = painter.font()
            font.setPointSize(10)
            painter.setFont(font)

            # Draw rotated text
            painter.save()
            painter.translate(label_x, label_y)
            painter.rotate(label_angle)
            painter.drawText(
                QRectF(-50, -20, 100, 40),
                Qt.AlignmentFlag.AlignCenter,
                f"{name}\n{days}d"
            )
            painter.restore()

            start_angle += sweep_angle

class ModernCalendarDisplay(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        self.layout = QVBoxLayout(self)
        self.layout.setSpacing(20)
        self.layout.setContentsMargins(20, 20, 20, 20)

        # Create scrollable area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        # Main container
        container = QWidget()
        self.content_layout = QVBoxLayout(container)
        self.content_layout.setSpacing(25)

        # Header (will be set later)
        self.header = QLabel()
        self.header.setStyleSheet("""
            font-size: 24px;
            font-weight: 300;
            color: #1a73e8;
            padding: 10px;
        """)
        self.header.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Stats container
        self.stats_container = QFrame()
        self.stats_container.setStyleSheet("""
            QFrame {
                background-color: #f8f9fa;
                border-radius: 10px;
                padding: 15px;
            }
        """)
        self.stats_layout = QHBoxLayout(self.stats_container)

        # Circular month view
        self.month_view = CircularMonthView()

        # Weekdays container
        self.weekdays_container = QFrame()
        self.weekdays_container.setStyleSheet("""
            QFrame {
                background-color: #f8f9fa;
                border-radius: 10px;
                padding: 15px;
            }
        """)
        self.weekdays_layout = QHBoxLayout(self.weekdays_container)

        # Add all widgets to content layout
        self.content_layout.addWidget(self.header)
        self.content_layout.addWidget(self.stats_container)
        self.content_layout.addWidget(self.month_view)
        self.content_layout.addWidget(self.weekdays_container)

        scroll.setWidget(container)
        self.layout.addWidget(scroll)

    def _create_stat_widget(self, title, value):
        widget = QFrame()
        widget.setStyleSheet("""
            QFrame {
                background-color: white;
                border-radius: 8px;
                padding: 15px;
            }
        """)

        layout = QVBoxLayout(widget)

        title_label = QLabel(title)
        title_label.setStyleSheet("color: #666; font-size: 14px;")

        value_label = QLabel(str(value))
        value_label.setStyleSheet("color: #333; font-size: 24px; font-weight: bold;")

        layout.addWidget(title_label)
        layout.addWidget(value_label)

        return widget

    def _create_weekday_label(self, name):
        label = QLabel(name)
        label.setStyleSheet("""
            background-color: #e8f0fe;
            color: #1a73e8;
            padding: 8px 16px;
            border-radius: 15px;
            font-weight: 500;
        """)
        return label

    def update_display(self, calendar_data):
        """Update the calendar display with new data"""
        # Clear existing layouts
        for i in reversed(range(self.stats_layout.count())):
            self.stats_layout.itemAt(i).widget().setParent(None)
        for i in reversed(range(self.weekdays_layout.count())):
            self.weekdays_layout.itemAt(i).widget().setParent(None)

        # Update header
        self.header.setText(calendar_data['epoch_name'])

        # Update stats
        stats = [
            ("Current Year", calendar_data['current_year']),
            ("Days per Year", calendar_data['year_length']),
            ("Days per Week", calendar_data['days_per_week'])
        ]

        for title, value in stats:
            self.stats_layout.addWidget(self._create_stat_widget(title, value))

        # Update circular month view
        months_data = list(zip(calendar_data['month_names'], calendar_data['month_days']))
        self.month_view.set_data(months_data)

        # Update weekdays
        for day in calendar_data['weekday_names']:
            self.weekdays_layout.addWidget(self._create_weekday_label(day))
        self.weekdays_layout.addStretch()