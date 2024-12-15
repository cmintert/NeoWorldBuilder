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

    def select_image(self, parent: QWidget) -> ImageResult:
        """
        Handle image selection through file dialog.

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
                return ImageResult(True, path=file_name)
            return ImageResult(False)

        except Exception as e:
            return ImageResult(False, error_message=str(e))
