from typing import Dict, Callable, Any

from PyQt6.QtCore import QStringListModel, pyqtSlot
from structlog import get_logger

from src.models.worker_model import WorkerOperation
logger = get_logger(__name__)

class CalendarMixin:
    """Mixin providing calendar-related functionality for controllers."""

    def update_calendar_suggestions(self, text: str, completer) -> None:
        """Update calendar suggestions in the completer."""
        logger.debug("update_calendar_suggestions called", text=text)

        query = """
        MATCH (c:CALENDAR)
        WHERE c._project = $project 
        AND toLower(c.name) CONTAINS toLower($search)
        RETURN c.name as name, elementId(c) as element_id
        ORDER BY c.name
        """

        def handle_results(results):
            logger.debug("handle_results called", results=results)

            # Store element IDs for validation
            self.calendar_element_ids = {r["name"]: r["element_id"] for r in results}
            logger.debug("calendar_element_ids set", ids=self.calendar_element_ids)

            # Create string list model for completer
            completion_model = QStringListModel()
            name_list = [r["name"] for r in results]
            completion_model.setStringList(name_list)
            logger.debug("completion model created", names=name_list)

            # Set model on completer
            completer.setModel(completion_model)
            logger.debug("model set on completer")

        worker = self.model.execute_read_query(
            query, {"project": self.config.user.PROJECT, "search": text}
        )

        worker.query_finished.connect(handle_results)

        operation = WorkerOperation(
            worker=worker,
            success_callback=None,
            error_callback=lambda msg: self.error_handler.handle_error(
                f"Error updating calendar suggestions: {msg}"
            ),
            operation_name="calendar_search",
        )

        self.worker_manager.execute_worker("calendar_search", operation)

    def add_calendar_relationship(self, calendar_name: str):
        """Add USES_CALENDAR relationship to relationship table."""
        # Remove any existing USES_CALENDAR relationships
        self._remove_calendar_relationships()

        # Add new relationship
        self.ui.add_relationship_row(
            rel_type="USES_CALENDAR",
            target=calendar_name,
            direction=">",
            properties="{}",
        )

        # Update save button state
        self.update_unsaved_changes_indicator()

    def _remove_calendar_relationships(self):
        """Remove any existing USES_CALENDAR relationships from table."""
        table = self.ui.relationships_table
        rows_to_remove = []

        # Find rows with USES_CALENDAR relationship
        for row in range(table.rowCount()):
            rel_type = table.item(row, 0)
            if rel_type and rel_type.text() == "USES_CALENDAR":
                rows_to_remove.append(row)

        # Remove rows in reverse order to maintain correct indices
        for row in sorted(rows_to_remove, reverse=True):
            table.removeRow(row)

    def _get_raw_calendar_properties(self) -> Dict[str, str]:
        """Get raw calendar properties from table."""
        logger.debug("Fetching raw calendar properties")
        properties = {}
        for row in range(self.properties_table.rowCount()):
            key_item = self.properties_table.item(row, 0)
            value_item = self.properties_table.item(row, 1)
            if key_item and value_item and key_item.text().startswith("calendar_"):
                properties[key_item.text()] = value_item.text().strip()
                logger.debug(
                    "Found calendar property",
                    key=key_item.text(),
                    value=value_item.text().strip(),
                )

        logger.debug("Raw calendar properties result", properties=properties)
        return properties

    def setup_calendar_data(self) -> None:
        """Load calendar data from flat properties."""
        logger.debug(
            "Starting calendar data setup",
            has_calendar_tab=bool(self.calendar_tab),
            has_raw_props=bool(self._get_raw_calendar_properties()),
        )

        if not self.calendar_tab or not self._get_raw_calendar_properties():
            logger.debug("Exiting early - missing required components")
            return

        try:
            raw_props = self._get_raw_calendar_properties()
            logger.debug("Raw calendar properties", raw_props=raw_props)

            calendar_data = {}

            # Known types for each property
            list_props = {"month_names", "month_days", "weekday_names"}
            int_props = {"current_year", "year_length", "days_per_week"}

            logger.debug(
                "Property type classifications",
                list_props=list_props,
                int_props=int_props,
            )

            for key, value in raw_props.items():
                # Remove calendar_ prefix
                clean_key = key.replace("calendar_", "")

                logger.debug(
                    "Processing property",
                    original_key=key,
                    clean_key=clean_key,
                    original_value=value,
                )

                try:
                    if clean_key in list_props:
                        if clean_key == "month_days":
                            # Convert to list of integers
                            split_values = value.split(",")
                            calendar_data[clean_key] = [
                                int(x) for x in split_values if x
                            ]
                            logger.debug(
                                "Processed list (integers)",
                                key=clean_key,
                                split_values=split_values,
                                result=calendar_data[clean_key],
                            )
                        else:
                            # Convert to list of strings
                            split_values = value.split(",")
                            calendar_data[clean_key] = [x for x in split_values if x]
                            logger.debug(
                                "Processed list (strings)",
                                key=clean_key,
                                split_values=split_values,
                                result=calendar_data[clean_key],
                            )
                    elif clean_key in int_props:
                        # Handle integers
                        calendar_data[clean_key] = int(value)
                        logger.debug(
                            "Processed integer",
                            key=clean_key,
                            value=value,
                            result=calendar_data[clean_key],
                        )
                    else:
                        # Handle strings
                        calendar_data[clean_key] = value
                        logger.debug("Processed string", key=clean_key, value=value)
                except Exception as conversion_error:
                    logger.error(
                        "Property conversion failed",
                        key=clean_key,
                        value=value,
                        error=str(conversion_error),
                    )
                    raise

            logger.debug("Final calendar data structure", calendar_data=calendar_data)
            self.calendar_tab.set_calendar_data(calendar_data)

        except Exception as e:
            logger.error(
                "calendar_setup_failed", error=str(e), error_type=type(e).__name__
            )
            raise

    def _handle_calendar_changed(self, calendar_data: Dict[str, Any]) -> None:
        """Handle changes to calendar data by storing in flat properties."""
        try:
            # Clear existing calendar properties
            self._clear_calendar_properties()

            # Store each property with appropriate type handling
            for key, value in calendar_data.items():
                if isinstance(value, list):
                    # Convert lists to comma-separated strings
                    stored_value = ",".join(str(x) for x in value)
                else:
                    # Store other values directly as strings
                    stored_value = str(value)

                self._add_calendar_property(f"calendar_{key}", stored_value)

            self.update_unsaved_changes_indicator()
        except Exception as e:
            logger.error("calendar_update_failed", error=str(e))

    def handle_calendar_data(self, result) -> None:
        """Process calendar data and update UI."""
        logger.debug("handle_calendar_data: raw result", result=result)
        if not result or not result[0].get("calendar_data"):
            logger.error("No calendar data found")
            return

        calendar_data = result[0]["calendar_data"]
        logger.debug("handle_calendar_data: calendar_data", calendar_data=calendar_data)

        # Convert month_days from string array to integer array
        calendar_data["month_days"] = [
            int(days) for days in calendar_data["month_days"]
        ]

        # Validate all fields exist and are of correct type
        try:
            required = {
                "month_names": list,
                "month_days": list,
                "weekday_names": list,
                "days_per_week": int,
                "year_length": int,
                "current_year": int,
            }

            for field, expected_type in required.items():
                if field not in calendar_data:
                    raise ValueError(f"Missing required field: {field}")
                if not isinstance(calendar_data[field], expected_type):
                    raise ValueError(
                        f"Field {field} has wrong type. Expected {expected_type}"
                    )

            # Set calendar data in event tab
            if hasattr(self.ui, "event_tab") and self.ui.event_tab:
                try:
                    self.ui.event_tab.set_calendar_data(calendar_data)
                    logger.info(
                        "Calendar data successfully set in event tab",
                        data=calendar_data,
                    )

                    # Load existing event data if present
                    if self.all_props.get("event_data"):
                        self.ui.event_tab.set_event_data(self.all_props["event_data"])
                except Exception as e:
                    logger.error(
                        "Failed to set calendar data in event tab", error=str(e)
                    )
            else:
                logger.error("Event tab not found")

        except Exception as e:
            logger.error("Calendar data validation failed", error=str(e))

    @pyqtSlot(list)
    def _handle_calendar_query_finished(self, result: list) -> None:
        """Handle the result from the calendar query worker."""
        logger.debug("_handle_calendar_query_finished: Signal received", result=result)
        self.handle_calendar_data(result)

    def validate_calendar_node(self, element_id: str, callback: Callable) -> None:
        """Validate a node is a valid calendar using its element ID."""
        logger.debug("validate_calendar_node", element_id=element_id)
        query = """
        MATCH (c) 
        WHERE elementId(c) = $element_id 
        AND c._project = $project
        RETURN 'CALENDAR' IN labels(c) as is_calendar
        """

        worker = self.model.execute_read_query(
            query, {"element_id": element_id, "project": self.config.user.PROJECT}
        )

        operation = WorkerOperation(
            worker=worker,
            success_callback=callback,
            error_callback=lambda msg: self.error_handler.handle_error(
                f"Error validating calendar: {msg}"
            ),
            operation_name="validate_calendar",
        )

        self.worker_manager.execute_worker("validate_calendar", operation)