from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                             QFrame, QScrollArea)
from PyQt6.QtCore import Qt

class CompactCalendarDisplay(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        self.layout = QVBoxLayout(self)
        self.layout.setSpacing(10)
        self.layout.setContentsMargins(10, 10, 10, 10)

        # Create scrollable area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        # Main container
        container = QWidget()
        self.content_layout = QVBoxLayout(container)
        self.content_layout.setSpacing(10)

        # Header
        self.header = QLabel()
        self.header.setStyleSheet("""
            font-size: 18px;
            font-weight: bold;
            color: #1a73e8;
            padding: 5px;
        """)
        self.header.setAlignment(Qt.AlignmentFlag.AlignLeft)

        # Stats container
        self.stats_container = QWidget()
        self.stats_layout = QHBoxLayout(self.stats_container)
        self.stats_layout.setSpacing(10)
        self.stats_container.setStyleSheet("""
            QLabel { 
                padding: 5px;
                border-radius: 4px;
                background: #f8f9fa;
            }
        """)

        # Months container
        self.months_container = QFrame()
        self.months_container.setStyleSheet("""
            QFrame {
                background-color: #f8f9fa;
                border-radius: 4px;
                padding: 5px;
            }
            QLabel {
                padding: 5px;
            }
        """)
        self.months_layout = QVBoxLayout(self.months_container)
        self.months_layout.setSpacing(2)

        # Weekdays container
        self.weekdays_container = QWidget()
        self.weekdays_layout = QHBoxLayout(self.weekdays_container)
        self.weekdays_layout.setSpacing(5)

        # Seasons container
        self.seasons_container = QFrame()
        self.seasons_container.setStyleSheet("""
            QFrame {
                background-color: #f8f9fa;
                border-radius: 4px;
                padding: 5px;
            }
            QLabel {
                padding: 5px;
            }
        """)
        self.seasons_layout = QVBoxLayout(self.seasons_container)
        self.seasons_layout.setSpacing(2)

        # Lunar Cycles container
        self.lunar_cycles_container = QFrame()
        self.lunar_cycles_container.setStyleSheet("""
            QFrame {
                background-color: #f8f9fa;
                border-radius: 4px;
                padding: 5px;
            }
            QLabel {
                padding: 5px;
            }
        """)
        self.lunar_cycles_layout = QVBoxLayout(self.lunar_cycles_container)
        self.lunar_cycles_layout.setSpacing(2)

        # Add all widgets to content layout
        self.content_layout.addWidget(self.header)
        self.content_layout.addWidget(self.stats_container)
        self.content_layout.addWidget(self.months_container)
        self.content_layout.addWidget(self.weekdays_container)
        self.content_layout.addWidget(self.seasons_container)
        self.content_layout.addWidget(self.lunar_cycles_container)
        self.content_layout.addStretch()

        scroll.setWidget(container)
        self.layout.addWidget(scroll)

    def _create_stat_label(self, text):
        label = QLabel(text)
        label.setStyleSheet("""
            color: #333;
            font-size: 12px;
            padding: 5px 10px;
        """)
        return label

    def _create_month_label(self, text):
        label = QLabel(text)
        label.setStyleSheet("""
            background-color: white;
            border-radius: 4px;
            padding: 5px 10px;
            margin: 1px;
            font-size: 12px;
        """)
        return label

    def _create_weekday_label(self, text):
        label = QLabel(text)
        label.setStyleSheet("""
            background-color: #e8f0fe;
            color: #1a73e8;
            padding: 4px 8px;
            border-radius: 10px;
            font-size: 11px;
            font-weight: bold;
        """)
        return label

    def _create_season_label(self, text):
        label = QLabel(text)
        label.setStyleSheet("""
            background-color: #d4edda;
            border-radius: 4px;
            padding: 5px 10px;
            margin: 1px;
            font-size: 12px;
        """)
        return label

    def _create_lunar_cycle_label(self, text):
        label = QLabel(text)
        label.setStyleSheet("""
            background-color: #f8d7da;
            border-radius: 4px;
            padding: 5px 10px;
            margin: 1px;
            font-size: 12px;
        """)
        return label

    def update_display(self, calendar_data):
        """Update the calendar display with new data"""
        # Clear existing layouts
        for layout in [self.stats_layout, self.months_layout, self.weekdays_layout, self.seasons_layout, self.lunar_cycles_layout]:
            for i in reversed(range(layout.count())):
                item = layout.itemAt(i)
                if item is not None and item.widget() is not None:
                    item.widget().setParent(None)

        # Update header
        self.header.setText(calendar_data['epoch_name'])

        # Update stats
        stats = [
            f"Year: {calendar_data['current_year']}",
            f"Days/Year: {calendar_data['year_length']}",
            f"Days/Week: {calendar_data['days_per_week']}"
        ]

        for stat in stats:
            self.stats_layout.addWidget(self._create_stat_label(stat))
        self.stats_layout.addStretch()

        # Update months
        for name, days in zip(calendar_data['month_names'], calendar_data['month_days']):
            self.months_layout.addWidget(self._create_month_label(f"{name} ({days} days)"))

        # Update weekdays
        for day in calendar_data['weekday_names']:
            self.weekdays_layout.addWidget(self._create_weekday_label(day))
        self.weekdays_layout.addStretch()

        # Update seasons
        for season in calendar_data['seasons']:
            self.seasons_layout.addWidget(self._create_season_label(f"{season['name']} ({season['start_month']}/{season['start_day']} - {season['end_month']}/{season['end_day']})"))

        # Update lunar cycles
        for cycle in calendar_data['lunar_cycles']:
            self.lunar_cycles_layout.addWidget(self._create_lunar_cycle_label(f"{cycle['name']} ({cycle['start_month']}/{cycle['start_day']} - {cycle['end_month']}/{cycle['end_day']})"))
