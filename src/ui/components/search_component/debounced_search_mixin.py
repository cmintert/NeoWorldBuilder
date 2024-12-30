from typing import Callable

from PyQt6.QtCore import QTimer, QObject
from structlog import get_logger

logger = get_logger(__name__)


class DebouncedSearchMixin(QObject):
    """Mixin to add debounced search functionality.

    This mixin provides debounced timer functionality for search operations,
    helping prevent excessive database queries during rapid user input.

    Attributes:
        _search_timer: QTimer instance for debouncing
        _trace_id: UUID for tracking related search events
    """

    def __init__(self) -> None:
        """Initialize the debounced search mixin."""
        super().__init__()
        self._search_timer = QTimer()
        self._search_timer.setSingleShot(True)
        self._trace_id: str = ""

    def setup_debounced_search(
        self, callback: Callable[[], None], delay_ms: int = 100
    ) -> None:
        """Setup debounced search timer with callback.

        Args:
            callback: Function to call when timer triggers
            delay_ms: Debounce delay in milliseconds

        Raises:
            RuntimeError: If timer connection fails
        """
        try:
            self._search_timer.setInterval(delay_ms)
            self._search_timer.timeout.connect(callback)
            logger.debug(
                "debounced_search_setup", delay_ms=delay_ms, trace_id=self._trace_id
            )
        except Exception as e:
            logger.error(
                "debounced_search_setup_failed", error=str(e), trace_id=self._trace_id
            )
            raise RuntimeError(f"Failed to setup debounced search: {str(e)}")

    def trigger_debounced_search(self) -> None:
        """Trigger the debounced search operation.

        Starts or restarts the timer for the search operation.
        """
        self._search_timer.start()

    def cleanup_timer(self) -> None:
        """Clean up the timer resources.

        Should be called when the object is being destroyed to prevent memory leaks.
        """
        if self._search_timer:
            self._search_timer.stop()
            self._search_timer.deleteLater()
            logger.debug("debounced_search_cleanup", trace_id=self._trace_id)
