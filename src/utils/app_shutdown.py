import sys

from PyQt6.QtWidgets import QApplication
from structlog import get_logger

logger = get_logger(__name__)


def perform_application_exit(self):
    """Perform a clean application exit."""
    try:
        # Get the main window instance
        main_window = self.app_instance

        # Cleanup if possible
        if hasattr(main_window, "cleanup"):
            main_window.cleanup()

        # Quit the application
        QApplication.instance().quit()

        # Force exit if needed
        sys.exit(0)
    except Exception as e:
        logger.error(f"Error during application exit: {e}")
        sys.exit(1)
