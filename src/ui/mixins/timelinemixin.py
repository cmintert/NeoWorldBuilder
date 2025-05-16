from typing import Dict, Callable, Any, List

from PyQt6.QtCore import QStringListModel, pyqtSlot
from structlog import get_logger

from src.models.worker_model import WorkerOperation
logger = get_logger(__name__)

class TimelineMixin:
    """Mixin providing timeline functionality for controllers."""

    def _setup_timeline_calendar(self) -> None:
        """Set up calendar data for timeline nodes."""
        # First ensure timeline tab exists
        if not hasattr(self.ui, "timeline_tab") or not self.ui.timeline_tab:
            logger.debug("Creating timeline tab")
            from ui.components.timeline_component.timeline_widget import TimelineTab

            self.ui.timeline_tab = TimelineTab(self)
            self.ui.tabs.addTab(self.ui.timeline_tab, "Timeline")

        # Now handle the event query
        if not self.current_node_element_id:
            logger.error("No element_id available for timeline events")
            return

        calendar_query = """
        MATCH (n)-[r:USES_CALENDAR]->(c:CALENDAR)
        WHERE elementId(n) = $element_id
        AND n._project = $project
        WITH c, properties(c) as props
        RETURN {
            month_names: props.calendar_month_names,
            month_days: props.calendar_month_days,
            weekday_names: props.calendar_weekday_names,
            days_per_week: toInteger(props.calendar_days_per_week),
            year_length: toInteger(props.calendar_year_length),
            current_year: toInteger(props.calendar_current_year),
            all_props: props
        } as calendar_data
        """

        worker = self.model.execute_read_query(
            calendar_query,
            {
                "element_id": self.current_node_element_id,
                "project": self.config.user.PROJECT,
            },
        )

        worker.query_finished.connect(self._handle_calendar_query_finished)

        operation = WorkerOperation(
            worker=worker,
            success_callback=None,
            error_callback=lambda msg: self.error_handler.handle_error(
                f"Calendar query failed: {msg}"
            ),
            operation_name="calendar_lookup",
        )

        self.worker_manager.execute_worker("calendar", operation)

    def _handle_calendar_query_finished(self, result: list) -> None:
        """Handle the result from the calendar query worker."""
        logger.debug("_handle_calendar_query_finished: Signal received", result=result)

        if not result or not result[0].get("calendar_data"):
            logger.error("No calendar data found")
            return

        # Store calendar data for later use
        self.current_calendar_data = result[0]["calendar_data"]
        logger.debug("Calendar data stored", calendar_data=self.current_calendar_data)

        # Handle the calendar data as before
        self.handle_calendar_data(result)

        # After handling calendar data, load timeline events with this calendar context
        if hasattr(self.ui, "timeline_tab") and self.ui.timeline_tab:
            self._load_timeline_events_with_calendar(self.current_calendar_data)

    def _setup_timeline_tab(self) -> None:
        """
        Set up the timeline tab and load associated data.

        Creates the timeline tab if it doesn't exist and loads calendar
        and event data for the current node.
        """
        if not self._ensure_timeline_tab():
            return

        if not self.current_node_element_id:
            logger.error("No element_id available for timeline events")
            return

        self._load_calendar_data()
        # Don't load events here, they'll be loaded after calendar data is available

    def _ensure_timeline_tab(self) -> bool:
        """
        Ensure the timeline tab exists and is properly initialized.

        Returns:
            bool: True if timeline tab exists or was created successfully,
                  False otherwise.
        """
        if not hasattr(self.ui, "timeline_tab") or not self.ui.timeline_tab:
            logger.debug("Creating timeline tab")
            from ui.components.timeline_component.timeline_widget import TimelineTab

            self.ui.timeline_tab = TimelineTab(self)
            self.ui.tabs.addTab(self.ui.timeline_tab, "Timeline")

        return bool(self.ui.timeline_tab)

    def _load_calendar_data(self) -> None:
        """
        Load calendar data for the current node.

        Queries the database for calendar relationships and updates
        the timeline tab's calendar input field.
        """
        calendar_query = """
        MATCH (t)-[r:USES_CALENDAR]->(c:CALENDAR)
        WHERE elementId(t) = $element_id
          AND t._project = $project
        RETURN c.name as calendar_name
        """

        worker = self.model.execute_read_query(
            calendar_query,
            {
                "element_id": self.current_node_element_id,
                "project": self.config.user.PROJECT,
            },
        )

        worker.query_finished.connect(self._handle_calendar_result)

        operation = WorkerOperation(
            worker=worker,
            success_callback=None,
            error_callback=self._create_error_handler("Calendar lookup failed"),
            operation_name="calendar_lookup",
        )

        self.worker_manager.execute_worker("calendar_lookup", operation)

    def _handle_calendar_result(self, results: list) -> None:
        """
        Handle the results of the calendar query.

        Args:
            results: List of query results containing calendar information.
        """
        if not results or not results[0].get("calendar_name"):
            return

        if not hasattr(self.ui, "timeline_tab") or not self.ui.timeline_tab:
            return

        calendar_name = results[0]["calendar_name"]
        calendar_input = self.ui.timeline_tab.calendar_input

        # Block signals while updating
        old_state = calendar_input.blockSignals(True)
        calendar_input.setText(calendar_name)
        calendar_input.blockSignals(old_state)

        # Update validation state
        self.ui.timeline_tab._update_validation_state(True)

        # Load the actual calendar data structure for positioning
        self._load_detailed_calendar_data(calendar_name)

    def _load_detailed_calendar_data(self, calendar_name: str) -> None:
        """Load detailed calendar data for timeline event positioning.

        Args:
            calendar_name: Name of the calendar
        """
        query = """
        MATCH (c:CALENDAR {name: $calendar_name, _project: $project})
        WITH c, properties(c) as props
        RETURN {
            month_names: props.calendar_month_names,
            month_days: props.calendar_month_days,
            weekday_names: props.calendar_weekday_names,
            days_per_week: toInteger(props.calendar_days_per_week),
            year_length: toInteger(props.calendar_year_length),
            current_year: toInteger(props.calendar_current_year),
            all_props: props
        } as calendar_data
        """

        worker = self.model.execute_read_query(
            query,
            {
                "calendar_name": calendar_name,
                "project": self.config.user.PROJECT,
            },
        )

        def handle_calendar_data(results: list) -> None:
            if not results or not results[0].get("calendar_data"):
                logger.error("Failed to load detailed calendar data")
                return

            # Store the calendar data
            self.current_calendar_data = results[0]["calendar_data"]
            logger.debug(
                "Loaded detailed calendar data",
                calendar_data=self.current_calendar_data,
            )

            # Now load events with this calendar context
            self._load_timeline_events_with_calendar(self.current_calendar_data)

        worker.query_finished.connect(handle_calendar_data)

        operation = WorkerOperation(
            worker=worker,
            success_callback=handle_calendar_data,
            error_callback=self._create_error_handler(
                "Detailed calendar lookup failed"
            ),
            operation_name="detailed_calendar_lookup",
        )

        self.worker_manager.execute_worker("detailed_calendar", operation)

    def _load_timeline_events_with_calendar(
        self, calendar_data: Dict[str, Any]
    ) -> None:
        """Load timeline events with calendar data for proper positioning."""
        if not self.current_node_element_id:
            logger.error("No element_id available for timeline events")
            return

        query = """
        MATCH (t)-[:USES_CALENDAR]->(c:CALENDAR)<-[:USES_CALENDAR]-(e:EVENT)
        WHERE elementId(t) = $element_id
          AND t._project = $project
        RETURN {
            name: e.name,
            temporal_data: e.temporal_data,
            parsed_date_year: toInteger(e.parsed_date_year), 
            parsed_date_month: toInteger(e.parsed_date_month),
            parsed_date_day: toInteger(e.parsed_date_day),
            event_type: e.event_type
        } as event
        ORDER BY e.parsed_date_year, e.parsed_date_month, e.parsed_date_day
        """

        worker = self.model.execute_read_query(
            query,
            {
                "element_id": self.current_node_element_id,
                "project": self.config.user.PROJECT,
            },
        )

        # Create a new handler that includes calendar data
        def handle_events_with_calendar(results: list) -> None:
            """Process events with calendar data."""
            events = self._process_event_results(results)

            if not events:
                logger.warning("No valid events extracted from query results")
                return

            if not hasattr(self.ui, "timeline_tab") or not self.ui.timeline_tab:
                logger.warning(
                    "Timeline tab not ready yet, skipping event data setting"
                )
                return

            # Pass both events AND calendar data to the timeline tab
            logger.debug(
                "Setting timeline event data with calendar",
                event_count=len(events),
                has_calendar=True,
            )
            self.ui.timeline_tab.set_event_data(events, calendar_data)

        worker.query_finished.connect(handle_events_with_calendar)

        operation = WorkerOperation(
            worker=worker,
            success_callback=handle_events_with_calendar,
            error_callback=lambda msg: self.error_handler.handle_error(
                f"Timeline event query failed: {msg}"
            ),
            operation_name="timeline_events_with_calendar",
        )

        logger.debug("Created worker operation for timeline events with calendar data")
        self.worker_manager.execute_worker("timeline_events", operation)

    def _load_timeline_events(self) -> None:
        """
        Load timeline events for the current node.

        This method is kept for compatibility but now calendar data is loaded first,
        and events are loaded through _load_timeline_events_with_calendar.
        """
        # This method is now a fallback and shouldn't be used directly
        # When possible, use _load_timeline_events_with_calendar
        logger.debug("_load_timeline_events called (legacy method)")

        if hasattr(self, "current_calendar_data") and self.current_calendar_data:
            self._load_timeline_events_with_calendar(self.current_calendar_data)
            return

        query = """
        MATCH (t)-[:USES_CALENDAR]->(c:CALENDAR)<-[:USES_CALENDAR]-(e:EVENT)
        WHERE elementId(t) = $element_id
          AND t._project = $project
        RETURN {
            name: e.name,
            temporal_data: e.temporal_data,
            parsed_date_year: toInteger(e.parsed_date_year), 
            parsed_date_month: toInteger(e.parsed_date_month),
            parsed_date_day: toInteger(e.parsed_date_day),
            event_type: e.event_type
        } as event
        ORDER BY e.parsed_date_year, e.parsed_date_month, e.parsed_date_day
        """

        worker = self.model.execute_read_query(
            query,
            {
                "element_id": self.current_node_element_id,
                "project": self.config.user.PROJECT,
            },
        )

        worker.query_finished.connect(self._handle_timeline_events)

        operation = WorkerOperation(
            worker=worker,
            success_callback=self._handle_timeline_events,
            error_callback=self._create_error_handler("Timeline event query failed"),
            operation_name="timeline_events",
        )

        logger.debug("Created worker operation, about to execute")
        self.worker_manager.execute_worker("timeline", operation)

    def _handle_timeline_events(self, results: list) -> None:
        """
        Process and display timeline events from query results.

        Args:
            results: List of query results containing event data.
        """
        logger.debug(
            "Timeline handler received results",
            result_count=len(results) if results else 0,
        )

        events = self._process_event_results(results)

        if not events:
            logger.warning("No valid events extracted from query results")
            return

        if not hasattr(self.ui, "timeline_tab") or not self.ui.timeline_tab:
            logger.warning("Timeline tab not ready yet, skipping event data setting")
            return

        # Use current_calendar_data if it exists
        logger.debug(
            "Setting timeline event data",
            event_count=len(events),
            has_calendar=hasattr(self, "current_calendar_data"),
        )

        if hasattr(self, "current_calendar_data") and self.current_calendar_data:
            self.ui.timeline_tab.set_event_data(events, self.current_calendar_data)
        else:
            self.ui.timeline_tab.set_event_data(events)

    def _process_event_results(self, results: list) -> list:
        """
        Process raw event query results into a structured format.

        Args:
            results: Raw query results containing event data.

        Returns:
            list: Processed and validated event data.
        """
        events = []
        for record in results:
            event_data = record[0]
            if isinstance(event_data, dict) and "parsed_date_year" in event_data:
                events.append(event_data)
            else:
                logger.warning(
                    "Event data invalid or missing required field", data=event_data
                )
        return events

    def _create_error_handler(self, prefix: str) -> callable:
        """
        Create an error handler function with a specific prefix.

        Args:
            prefix: Error message prefix.

        Returns:
            callable: Error handler function.
        """
        return lambda msg: self.error_handler.handle_error(f"{prefix}: {msg}")

    def _get_events_for_timeline(self) -> List[Dict[str, Any]]:
        """Get event data for timeline visualization.

        Returns:
            List[Dict[str, Any]]: List of event data dictionaries
        """
        if not self.current_node_element_id:
            logger.error("No element_id available for timeline query")
            return []

        query = """
        MATCH (t)-[:USES_CALENDAR]->(c:CALENDAR)<-[:USES_CALENDAR]-(e:EVENT)
        WHERE elementId(t) = $element_id
          AND t._project = $project
        RETURN e { 
            name: e.name,
            temporal_data: e.temporal_data,
            parsed_date_year: toInteger(e.parsed_date_year),
            parsed_date_month: toInteger(e.parsed_date_month),
            parsed_date_day: toInteger(e.parsed_date_day),
            event_type: e.event_type
        } as event
        ORDER BY e.parsed_date_year, e.parsed_date_month, e.parsed_date_day
        """

        worker = self.model.execute_read_query(
            query,
            {
                "element_id": self.current_node_element_id,
                "project": self.config.user.PROJECT,
            },
        )

        def handle_results(results):
            events = []
            for result in results:
                if "event" in result:
                    events.append(result["event"])
            logger.debug(
                "Timeline events retrieved from database",
                event_count=len(events),
                raw_events=events,
            )
            return events

        worker.query_finished.connect(handle_results)
        return []  # Initial empty return while query executes