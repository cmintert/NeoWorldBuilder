from typing import Protocol

from PyQt6.QtWidgets import QWidget, QFileDialog


class ImageDialogProvider(Protocol):
    """Protocol defining the interface for image dialog providers."""

    def get_open_file_name(
        self, parent: QWidget, caption: str, directory: str, filter: str
    ) -> tuple[str, str]: ...


class DefaultImageDialogProvider:
    """Default implementation of image dialog using QFileDialog."""

    def get_open_file_name(
        self, parent: QWidget, caption: str, directory: str, filter: str
    ) -> tuple[str, str]:
        return QFileDialog.getOpenFileName(parent, caption, directory, filter)
