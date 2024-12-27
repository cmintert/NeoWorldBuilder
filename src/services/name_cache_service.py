from typing import Set, List, Callable

from structlog import get_logger

from models.worker_model import WorkerOperation

logger = get_logger(__name__)


class NameCacheService:
    def __init__(
        self,
        model: "Neo4jModel",
        worker_manager: "WorkerManagerService",
        error_handler: Callable[[str], None],
    ) -> None:
        self.model = model
        self.worker_manager = worker_manager
        self.error_handler = error_handler
        self._name_cache: Set[str] = set()
        self._name_cache_valid = False

    def rebuild_cache(self) -> None:
        """Rebuild the name cache from database."""

        def handle_names(result: List[str]) -> None:
            if result:
                self._name_cache = set(result)
                self._name_cache_valid = True
                logger.info("Name Cache built", cache_size=len(self._name_cache))
                # log the actually cached names as strings
                logger.debug("Names cached", cached_names=str(self._name_cache))

        worker = self.model.get_all_node_names(handle_names)
        operation = WorkerOperation(
            worker=worker,
            success_callback=handle_names,
            error_callback=lambda msg: self.error_handler(
                f"Error rebuilding name cache: {msg}"
            ),
            operation_name="rebuild_name_cache",
        )
        self.worker_manager.execute_worker("name_cache", operation)

    def invalidate_cache(self) -> None:
        """Mark name cache as invalid."""
        self._name_cache_valid = False
        logger.debug("name_cache_invalidated")

    def ensure_valid_cache(self) -> None:
        """Ensure name cache is valid, rebuilding if necessary."""
        if not self._name_cache_valid:
            self.rebuild_cache()

    def get_cached_names(self) -> Set[str]:
        """Get cached node names, ensuring cache is valid."""
        self.ensure_valid_cache()
        if not self._name_cache:
            logger.warning("name_cache_empty_after_validation")
        return self._name_cache.copy()  # Return copy to prevent external modification
