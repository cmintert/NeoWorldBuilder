from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QFrame,
    QScrollArea,
    QComboBox,
)
from PyQt6.QtCore import Qt


class CompactCalendarDisplay(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        # Existing layout setup remains the same
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

        # Add epoch selection dropdown
        self.epoch_container = QWidget()
        epoch_layout = QHBoxLayout(self.epoch_container)
        epoch_layout.setSpacing(5)

        # Create and style the epoch selector
        self.epoch_selector = QComboBox()
        self.epoch_selector.setStyleSheet(
            """
                QComboBox {
                    padding: 5px;
                    border: 1px solid #1a73e8;
                    border-radius: 4px;
                    background: white;
                    min-width: 150px;
                }
                QComboBox::drop-down {
                    border: none;
                }
                QComboBox::down-arrow {
                    image: url(:/icons/dropdown.png);
                    width: 12px;
                    height: 12px;
                }
            """
        )
        epoch_layout.addWidget(QLabel("Era:"))
        epoch_layout.addWidget(self.epoch_selector)
        epoch_layout.addStretch()

        # Header for other calendar information
        self.header = QLabel()
        self.header.setStyleSheet(
            """
                font-size: 18px;
                font-weight: bold;
                color: #1a73e8;
                padding: 5px;
            """
        )
        self.header.setAlignment(Qt.AlignmentFlag.AlignLeft)

        # Stats container now includes epoch information
        self.stats_container = QWidget()
        self.stats_layout = QHBoxLayout(self.stats_container)
        self.stats_layout.setSpacing(10)
        self.stats_container.setStyleSheet(
            """
                QLabel { 
                    padding: 5px;
                    border-radius: 4px;
                    background: #f8f9fa;
                }
            """
        )

        # Months container
        self.months_container = QFrame()
        self.months_container.setStyleSheet(
            """
            QFrame {
                background-color: #f8f9fa;
                border-radius: 4px;
                padding: 5px;
            }
            QLabel {
                padding: 5px;
            }
        """
        )
        self.months_layout = QVBoxLayout(self.months_container)
        self.months_layout.setSpacing(2)

        # Weekdays container
        self.weekdays_container = QWidget()
        self.weekdays_layout = QHBoxLayout(self.weekdays_container)
        self.weekdays_layout.setSpacing(5)

        # Add all widgets to content layout
        self.content_layout.addWidget(self.epoch_container)
        self.content_layout.addWidget(self.header)
        self.content_layout.addWidget(self.stats_container)
        self.content_layout.addWidget(self.months_container)
        self.content_layout.addWidget(self.weekdays_container)
        self.content_layout.addStretch()

        scroll.setWidget(container)
        self.layout.addWidget(scroll)

    def _create_stat_label(self, text):
        label = QLabel(text)
        label.setStyleSheet(
            """
            color: #333;
            font-size: 12px;
            padding: 5px 10px;
        """
        )
        return label

    def _create_month_label(self, text):
        label = QLabel(text)
        label.setStyleSheet(
            """
            background-color: white;
            border-radius: 4px;
            padding: 5px 10px;
            margin: 1px;
            font-size: 12px;
        """
        )
        return label

    def _create_weekday_label(self, text):
        label = QLabel(text)
        label.setStyleSheet(
            """
            background-color: #e8f0fe;
            color: #1a73e8;
            padding: 4px 8px;
            border-radius: 10px;
            font-size: 11px;
            font-weight: bold;
        """
        )
        return label

    def update_display(self, calendar_data):
        """Update the calendar display with new data.

        This method expects calendar_data to contain properly formatted data:
        - epoch_names, epoch_abbreviations should be lists of strings
        - epoch_start_years, epoch_end_years should be lists of integers
        - All other fields should maintain their expected types
        """
        # Clear existing layouts first to prepare for new content
        for layout in [self.stats_layout, self.months_layout, self.weekdays_layout]:
            for i in reversed(range(layout.count())):
                item = layout.itemAt(i)
                if item is not None and item.widget() is not None:
                    item.widget().setParent(None)

        # Update epoch selector dropdown
        self.epoch_selector.clear()
        for i, epoch_name in enumerate(calendar_data["epoch_names"]):
            display_text = f"{epoch_name} ({calendar_data['epoch_abbreviations'][i]})"
            self.epoch_selector.addItem(display_text)

        # Find the current epoch based on the year
        current_year = calendar_data["current_year"]
        current_epoch_index = 0

        # Locate which epoch contains the current year
        for i, (start, end) in enumerate(
            zip(calendar_data["epoch_start_years"], calendar_data["epoch_end_years"])
        ):
            if start <= current_year <= end:
                current_epoch_index = i
                break

        # Set the current epoch in the dropdown
        self.epoch_selector.setCurrentIndex(current_epoch_index)

        # Update the header with the year and current epoch abbreviation
        current_abbr = calendar_data["epoch_abbreviations"][current_epoch_index]
        year_display = f"Year {current_year} {current_abbr}"
        self.header.setText(year_display)

        # Display calendar statistics
        stats = [
            f"Year: {current_year}",
            f"Days/Year: {calendar_data['year_length']}",
            f"Days/Week: {calendar_data['days_per_week']}",
        ]

        for stat in stats:
            self.stats_layout.addWidget(self._create_stat_label(stat))
        self.stats_layout.addStretch()

        # Show month information
        for name, days in zip(
            calendar_data["month_names"], calendar_data["month_days"]
        ):
            self.months_layout.addWidget(
                self._create_month_label(f"{name} ({days} days)")
            )

        # Display weekday names
        for day in calendar_data["weekday_names"]:
            self.weekdays_layout.addWidget(self._create_weekday_label(day))
        self.weekdays_layout.addStretch()
