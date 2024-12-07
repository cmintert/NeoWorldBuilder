import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional, Callable
from typing import List, Tuple

from PyQt6.QtCore import QObject, QTimer
from models.property_model import PropertyItem
from services.node_operation_service import NodeOperationsService
from utils.error_handler import ErrorHandler


@dataclass
class SaveState:
    """Tracks the state of node data for change detection"""

    original_data: Optional[Dict[str, Any]] = None
    has_unsaved_changes: bool = False


class SaveService(QObject):
    """
    Manages all saving operations and tracks save state.

    This service handles:
    - Save state management
    - Change detection for all node data
    - Save operations coordination
    - Save-related UI updates
    - Periodic change checking
    """

    def __init__(
        self,
        node_operations: NodeOperationsService,
        error_handler: ErrorHandler,
        check_interval: int = 1000,  # Default to checking every 1000ms (1 second)
    ) -> None:
        super().__init__()
        self.node_operations = node_operations
        self.error_handler = error_handler
        self.save_state = SaveState()

        # Initialize change check timer
        self.check_timer = QTimer(self)
        self.check_timer.timeout.connect(self._periodic_check)
        self.check_timer.setInterval(check_interval)

        # Callback to get current data
        self._get_current_data_callback: Optional[Callable[[], Dict[str, Any]]] = None

        # Callback to handle state changes
        self._on_state_changed_callback: Optional[Callable[[bool], None]] = None

    def start_periodic_check(
        self,
        get_current_data: Callable[[], Dict[str, Any]],
        on_state_changed: Callable[[bool], None],
    ) -> None:
        """
        Start periodic change checking.

        Args:
            get_current_data: Callback to get current node data
            on_state_changed: Callback to handle state changes
        """
        self._get_current_data_callback = get_current_data
        self._on_state_changed_callback = on_state_changed

        # Initialize original data state when starting checks
        try:
            current_data = get_current_data()
            self.save_state.original_data = current_data
        except Exception as e:
            logging.error(f"Error initializing save state: {e}")

        self.check_timer.start()
        logging.debug("Started periodic change checking")

    def stop_periodic_check(self) -> None:
        """Stop periodic change checking."""
        self.check_timer.stop()
        logging.debug("Stopped periodic change checking")

    def set_check_interval(self, interval_ms: int) -> None:
        """
        Set the interval for periodic checks.

        Args:
            interval_ms: Check interval in milliseconds
        """
        self.check_timer.setInterval(interval_ms)
        if self.check_timer.isActive():
            self.check_timer.start()  # Restart timer with new interval
        logging.debug(f"Change check interval set to {interval_ms}ms")

    def _periodic_check(self) -> None:
        """Perform periodic change check."""
        if not self._get_current_data_callback or not self._on_state_changed_callback:
            return

        try:
            current_data = self._get_current_data_callback()
            has_changes = self.check_for_changes(current_data)
            self._on_state_changed_callback(has_changes)
        except Exception as e:
            self.error_handler.handle_error(
                f"Error during periodic change check: {str(e)}"
            )
            self.stop_periodic_check()  # Stop checking on error

    def save_node(
        self,
        name: str,
        description: str,
        tags: str,
        labels: str,
        properties: List[PropertyItem],
        relationships: List[Tuple[str, str, str, str]],
        image_path: Optional[str],
        success_callback: Callable[[Any], None],
    ) -> None:
        """
        Save node data and handle state updates.

        Args:
            name: Node name
            description: Node description
            tags: Comma-separated tags
            labels: Comma-separated labels
            properties: List of property items
            relationships: List of relationship tuples
            image_path: Optional path to node image
            success_callback: Callback for successful save
        """
        try:
            validation_result = self.node_operations.validate_node_name(name)
            if not validation_result.is_valid:
                self.error_handler.handle_error(validation_result.error_message)
                return

            node_data = self.node_operations.collect_node_data(
                name=name,
                description=description,
                tags=tags,
                labels=labels,
                properties=properties,
                relationships=relationships,
                image_path=image_path,
            )

            if node_data:

                def wrapped_callback(result: Any) -> None:
                    self._handle_save_success(node_data, result)
                    success_callback(result)

                self.node_operations.save_node(node_data, wrapped_callback)

        except Exception as e:
            self.error_handler.handle_error(f"Error during save operation: {str(e)}")

    def update_save_state(self, node_data: Optional[Dict[str, Any]]) -> None:
        """
        Update the save state with new node data.

        Args:
            node_data: The node data to set as original state
        """
        self.save_state.original_data = node_data
        self.save_state.has_unsaved_changes = False
        logging.debug("Save state updated with new node data")

    def check_for_changes(self, current_data: Dict[str, Any]) -> bool:
        """
        Check if the current node data differs from the original state.

        Args:
            current_data: The current state of the node data

        Returns:
            bool: True if there are unsaved changes, False otherwise
        """
        # If no current data, no changes to track
        if not current_data:
            return False

        # If we have no original data, treat this as original
        if not self.save_state.original_data:
            self.save_state.original_data = current_data
            self.save_state.has_unsaved_changes = False
            return False

        # Compare with original data
        has_changes = current_data != self.save_state.original_data
        self.save_state.has_unsaved_changes = has_changes
        return has_changes

    def has_unsaved_changes(self) -> bool:
        """
        Get the current unsaved changes state.

        Returns:
            bool: True if there are unsaved changes
        """
        return self.save_state.has_unsaved_changes

    def _handle_save_success(self, saved_data: Dict[str, Any], result: Any) -> None:
        """
        Handle successful save operation.

        Args:
            saved_data: The data that was saved
            result: Save operation result
        """
        self.update_save_state(saved_data)
        logging.info("Node saved successfully")

    def clear_save_state(self) -> None:
        """Reset save state to initial values"""
        self.save_state = SaveState()
        logging.debug("Save state cleared")
