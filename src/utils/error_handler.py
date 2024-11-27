import logging
from typing import Optional, Callable

class ErrorHandler:
    def __init__(self,
                 ui_feedback_handler: Optional[Callable[[str, str], None]] = None):
        """
        Initialize ErrorHandler.

        Args:
            ui_feedback_handler: Function to handle UI feedback,
                               takes (title, message) as arguments
        """
        self.ui_feedback_handler = ui_feedback_handler

    def handle_error(self, error_message: str, log_level: int = logging.ERROR) -> None:
        """
        Handle an error with logging and optional UI feedback.

        Args:
            error_message: The error message
            log_level: Logging level to use
        """
        # Always log the error
        logging.log(log_level, error_message)

        # Show UI feedback if handler is configured
        if self.ui_feedback_handler:
            self.ui_feedback_handler("Error", error_message)