from typing import Dict

from PyQt6.QtCore import QObject

from models.worker_model import WorkerOperation


class WorkerManagerService(QObject):
    """Service for managing background worker threads."""

    def __init__(self, error_handler) -> None:
        super().__init__()
        self.error_handler = error_handler
        self._active_workers: Dict[str, WorkerOperation] = {}

    def execute_worker(self, worker_id: str, operation: WorkerOperation) -> None:
        """
        Execute a worker with proper cleanup and error handling.

        Args:
            worker_id: Unique identifier for this worker operation
            operation: Worker operation configuration
        """
        # Cancel existing worker if present
        self.cancel_worker(worker_id)

        # Store the operation
        self._active_workers[worker_id] = operation

        # Connect signals
        operation.worker.error_occurred.connect(
            lambda err: self._handle_worker_error(worker_id, err, operation)
        )

        if operation.finished_callback:
            operation.worker.finished.connect(
                lambda: self._handle_worker_finished(worker_id, operation)
            )

        # Start the worker
        operation.worker.start()

    def cancel_worker(self, worker_id: str) -> None:
        """
        Cancel and clean up a specific worker.

        Args:
            worker_id: ID of the worker to cancel
        """
        if operation := self._active_workers.get(worker_id):
            operation.worker.cancel()
            operation.worker.wait()
            del self._active_workers[worker_id]

    def cancel_all_workers(self) -> None:
        """Cancel and clean up all active workers."""
        for worker_id in list(self._active_workers.keys()):
            self.cancel_worker(worker_id)

    def _handle_worker_error(
        self, worker_id: str, error: str, operation: WorkerOperation
    ) -> None:
        """Handle worker error with cleanup."""
        if operation.error_callback:
            operation.error_callback(error)
        else:
            self.error_handler.handle_error(
                f"Error in {operation.operation_name}: {error}"
            )
        self.cancel_worker(worker_id)

    def _handle_worker_finished(
        self, worker_id: str, operation: WorkerOperation
    ) -> None:
        """Handle worker completion with cleanup."""
        if operation.finished_callback:
            operation.finished_callback()
        self.cancel_worker(worker_id)
