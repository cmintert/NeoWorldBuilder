from typing import Optional

from PyQt6.QtWidgets import QWidget

from models.image_model import ImageResult
from ui.providers.dialog_provider import ImageDialogProvider, DefaultImageDialogProvider


class ImageService:
    """Service for managing node images."""

    def __init__(
        self, dialog_provider: ImageDialogProvider = DefaultImageDialogProvider()
    ) -> None:
        """
        Initialize the ImageService.

        Args:
            dialog_provider: Provider for file dialogs, defaults to QFileDialog implementation
        """
        self.dialog_provider = dialog_provider
        self.current_image_path: Optional[str] = None

    def change_image(self, parent: QWidget) -> ImageResult:
        """
        Handle changing the image through file dialog.

        Args:
            parent: Parent widget for the file dialog

        Returns:
            ImageResult containing success status and path/error information
        """
        try:
            file_name, _ = self.dialog_provider.get_open_file_name(
                parent, "Select Image", "", "Image Files (*.png *.jpg *.bmp)"
            )
            if file_name:
                self.current_image_path = file_name
                return ImageResult(True, path=file_name)
            return ImageResult(False)

        except Exception as e:
            return ImageResult(False, error_message=str(e))

    def delete_image(self) -> None:
        """Remove the current image."""
        self.current_image_path = None

    def get_current_image(self) -> Optional[str]:
        """Get the current image path."""
        return self.current_image_path

    def set_current_image(self, path: Optional[str]) -> None:
        """Set the current image path."""
        self.current_image_path = path
