from structlog import get_logger

from src.models.worker_model import WorkerOperation

logger = get_logger(__name__)


class EventMixin:

    def _setup_event_calendar(self) -> None:
        """Set up calendar data for event nodes."""
        if not self.current_node_element_id:
            logger.error("No element_id available for calendar lookup")
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

        logger.debug("_setup_event_calendar: before execute_worker calendar operation")
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
        logger.debug("_setup_event_calendar: after execute_worker calendar operation")
