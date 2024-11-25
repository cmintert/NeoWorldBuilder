from dataclasses import dataclass
from typing import Optional


@dataclass
class ImageResult:
    """
    Result of an image operation.

    Attributes:
        success: Whether the operation was successful
        path: Path to the image if successful
        error_message: Error message if operation failed
    """

    success: bool
    path: Optional[str] = None
    error_message: Optional[str] = None
