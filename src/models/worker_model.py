from dataclasses import dataclass
from typing import Callable, Optional, Any

from PyQt6.QtCore import QThread


@dataclass
class WorkerOperation:
    """Represents a worker operation configuration."""

    worker: QThread
    success_callback: Optional[Callable[[Any], None]] = None
    error_callback: Optional[Callable[[str], None]] = None
    finished_callback: Optional[Callable[[], None]] = None
    operation_name: str = "operation"
