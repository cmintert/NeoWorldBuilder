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

        # Initialize UI without loading data
        self.setup_calendar_tab_ui()

    def initialize_calendar_data(self, raw_props: Dict[str, str]) -> None:
        """Initialize calendar data after properties are loaded.

        Args:
            raw_props: Dictionary of raw calendar properties from the main UI
        """
        logger.debug("Initializing calendar data with raw props", raw_props=raw_props)
        try:
            if not raw_props:
                logger.debug("No calendar properties found")
                return

            calendar_data = self._process_calendar_properties(raw_props)
            if calendar_data:
                self.set_calendar_data(calendar_data)
                logger.info("Calendar data initialized successfully")
        except Exception as e:
            logger.error("Failed to initialize calendar data", error=str(e))

    def _process_calendar_properties(
        self, raw_props: Dict[str, str]
    ) -> Optional[Dict[str, Any]]:
        """Process raw calendar properties into structured data."""
        calendar_data = {}

        # Known types for each property
        list_props = {"month_names", "month_days", "weekday_names"}
        int_props = {"current_year", "year_length", "days_per_week"}

        for key, value in raw_props.items():
            # Remove calendar_ prefix
            clean_key = key.replace("calendar_", "")

            try:
                if clean_key in list_props:
                    # Handle list properties by properly parsing the string representation
                    try:
                        import ast

                        parsed_list = ast.literal_eval(value)
                        if clean_key == "month_days":
                            calendar_data[clean_key] = [int(x) for x in parsed_list]
                        else:
                            calendar_data[clean_key] = [str(x) for x in parsed_list]
                    except (ValueError, SyntaxError):
                        # Fallback to simple comma splitting if literal_eval fails
                        items = [
                            x.strip() for x in value.strip("[]").split(",") if x.strip()
                        ]
                        if clean_key == "month_days":
                            calendar_data[clean_key] = [int(x) for x in items]
                        else:
                            calendar_data[clean_key] = items
                elif clean_key in int_props:
                    calendar_data[clean_key] = int(value)
                else:
                    calendar_data[clean_key] = value.strip()

                logger.debug(
                    f"Processed calendar property: {clean_key}",
                    value=calendar_data[clean_key],
                )

            except Exception as e:
                logger.error(
                    f"Failed to process calendar property: {key}", error=str(e)
                )
                raise

        return calendar_data if self._validate_calendar_data(calendar_data) else None

    def _validate_calendar_data(self, data: Dict[str, Any]) -> bool:
        """Validate calendar data structure."""
        required = {
            "month_names": list,
            "month_days": list,
            "weekday_names": list,
            "days_per_week": int,
            "year_length": int,
            "current_year": int,
        }

        try:
            for field, expected_type in required.items():
                if field not in data:
                    logger.error(f"Missing required field: {field}")
                    return False
                if not isinstance(data[field], expected_type):
                    logger.error(
                        f"Invalid type for {field}: expected {expected_type}, got {type(data[field])}"
                    )
                    return False
            return True
        except Exception as e:
            logger.error("Calendar data validation failed", error=str(e))
            return False

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
        self._update_info_display()

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

        This method validates and transforms the data before updating the display.

        Args:
            data: Dictionary containing calendar configuration
        """
        try:
            logger.debug("Setting calendar data", data=data)

            if not data:
                logger.warning("Attempted to set empty calendar data")
                return

            # Transform any string-formatted lists into proper Python lists
            transformed_data = self._transform_calendar_data(data)

            # Update the internal data store
            self.calendar_data = transformed_data

            # Update the display with the clean data
            self._update_info_display()

            # Notify parent of changes
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

    def _transform_calendar_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Transform calendar data into the proper format.

        Handles conversion of string-formatted lists to proper Python lists.

        Args:
            data: Raw calendar data dictionary

        Returns:
            Dict[str, Any]: Transformed calendar data with proper types
        """
        # Create a copy to avoid modifying the input
        transformed = data.copy()

        # Handle epoch-related fields
        list_fields = [
            ("epoch_names", str),
            ("epoch_abbreviations", str),
            ("epoch_start_years", int),
            ("epoch_end_years", int),
        ]

        for field, type_func in list_fields:
            if field in transformed:
                value = transformed[field]
                if isinstance(value, str):
                    # Convert string representation to list
                    clean_str = value.strip("[]").replace("'", "").replace('"', "")
                    transformed[field] = [
                        type_func(item.strip())
                        for item in clean_str.split(",")
                        if item.strip()
                    ]

        return transformed

    def _update_info_display(self) -> None:
        """Update the calendar information display."""

        if not self.calendar_data:
            # Create a simple label for no data case
            no_data_label = QLabel("<i>No calendar configured</i>")
            no_data_label.setObjectName("no_data_label")
            no_data_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.calendar_display.layout.addWidget(no_data_label)
            return

        # Clear existing layouts with name 'no_data_label'
        for i in reversed(range(self.calendar_display.layout.count())):
            item = self.calendar_display.layout.itemAt(i)
            if item is not None and item.widget() is not None:
                if item.widget().objectName() == "no_data_label":
                    item.widget().setParent(None)

        # Update the modern display with calendar data
        self.calendar_display.update_display(self.calendar_data)
