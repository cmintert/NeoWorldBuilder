from typing import Optional, Dict, Any


from PyQt6.QtCore import pyqtSignal, Qt

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QMessageBox,
)
from structlog import get_logger

from ui.components.calendar_component.calendar_config_dialog import CalendarConfigDialog
from ui.components.calendar_component.card_based_calendar_widget import (
    CompactCalendarDisplay,
)

logger = get_logger(__name__)


class CalendarTab(QWidget):
    """Calendar tab component for configuring and displaying calendar information."""

    calendar_changed = pyqtSignal(dict)  # Signal when calendar configuration changes

    def __init__(self, parent: Optional[QWidget] = None, controller=None):
        """Initialize the calendar tab."""
        super().__init__(parent)
        self.controller = controller
        self.config = controller.config if controller else None
        self.calendar_data = None

        logger.debug(
            "Initializing calendar tab",
            has_controller=bool(controller),
            has_config=bool(self.config),
            parent_widget=bool(parent),
        )

        self.setup_calendar_tab_ui()

    def setup_calendar_tab_ui(self) -> None:
        """Setup the UI components."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Calendar controls
        controls_layout = QHBoxLayout()

        # Configuration button
        self.config_btn = QPushButton("⚙️ Configure Calendar")
        self.config_btn.clicked.connect(self._show_calendar_config)

        # Save configuration button
        self.save_btn = QPushButton("💾 Save Calendar")
        self.save_btn.clicked.connect(self._save_calendar_config)

        controls_layout.addWidget(self.config_btn)
        controls_layout.addWidget(self.save_btn)
        controls_layout.addStretch()

        # Modern calendar display
        self.calendar_display = CompactCalendarDisplay()
        self._update_info_display()  # This will now update our new display

        # Add components to layout
        layout.addLayout(controls_layout)
        layout.addWidget(self.calendar_display)

    def _update_info_display(self) -> None:
        """Update the calendar information display."""
        if not self.calendar_data:
            # Create a simple label for no data case
            no_data_label = QLabel("<i>No calendar configured</i>")
            no_data_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.calendar_display.layout.addWidget(no_data_label)
            return

        # Update the modern display with calendar data
        self.calendar_display.update_display(self.calendar_data)

    def _show_calendar_config(self) -> None:
        """Show the calendar configuration dialog."""
        try:
            logger.debug(
                "Opening calendar config dialog", current_data=self.calendar_data
            )

            # Create dialog with explicit parent and data
            dialog = CalendarConfigDialog(calendar_data=self.calendar_data, parent=self)

            # Show dialog and handle result
            if dialog.exec():
                new_data = dialog.get_calendar_data()
                logger.debug("Calendar config dialog accepted", new_data=new_data)
                self.set_calendar_data(new_data)
            else:
                logger.debug("Calendar config dialog cancelled")

        except Exception as e:
            logger.error(
                "Error showing calendar config dialog",
                error=str(e),
                error_type=type(e).__name__,
            )
            # Show error to user
            QMessageBox.critical(
                self, "Error", f"Failed to open calendar configuration: {str(e)}"
            )

    def _save_calendar_config(self) -> None:
        """Save the current calendar configuration."""
        if not self.calendar_data:
            QMessageBox.warning(self, "Error", "No calendar data to save")
            return

        try:
            # Emit signal with new calendar data
            self.calendar_changed.emit(self.calendar_data)
            QMessageBox.information(
                self, "Success", "Calendar configuration saved successfully"
            )

        except Exception as e:
            logger.error("Error saving calendar configuration", error=str(e))
            QMessageBox.critical(
                self, "Error", f"Failed to save calendar configuration: {str(e)}"
            )

    def set_calendar_data(self, data: Dict[str, Any]) -> None:
        """Set the calendar data and update the UI.

        Args:
            data: Dictionary containing calendar configuration
        """
        try:
            logger.debug("Setting calendar data", data=data)

            if not data:
                logger.warning("Attempted to set empty calendar data")
                return

            self.calendar_data = data
            self._update_info_display()

            # Emit change signal to notify parent
            self.calendar_changed.emit(self.calendar_data)

            logger.debug("Calendar data set successfully")

        except Exception as e:
            logger.error(
                "Error setting calendar data",
                error=str(e),
                error_type=type(e).__name__,
                data=data,
            )
            QMessageBox.critical(
                self, "Error", f"Failed to update calendar configuration: {str(e)}"
            )

    def _update_info_display(self) -> None:
        """Update the calendar information display."""
        if not self.calendar_data:
            # Create a simple label for no data case
            no_data_label = QLabel("<i>No calendar configured</i>")
            no_data_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.calendar_display.layout.addWidget(no_data_label)
            return

        # Update the modern display with calendar data
        self.calendar_display.update_display(self.calendar_data)
