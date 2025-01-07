from os.path import exists
from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QGroupBox,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QMessageBox,
)
from structlog import get_logger

logger = get_logger(__name__)


class ImageGroup(QGroupBox):
    """
    A component for displaying and managing an image with change/delete controls.
    """

    basic_image_changed = pyqtSignal(str)  # Emits the new image path
    basic_image_removed = pyqtSignal()  # Emits when image is removed

    def __init__(self, parent=None):
        super().__init__("Image", parent)
        self.setObjectName("imageGroupBox")
        self._pixmap_cache = {}  # Add caching
        self._init_image_group_ui()

    def _init_image_group_ui(self) -> None:
        """Initialize the UI layout and widgets."""
        # Set group box size
        self.setFixedWidth(220)
        self.setFixedHeight(300)

        # Main layout
        layout = QVBoxLayout()
        layout.setObjectName("imageGroupLayout")

        # Image display
        self.image_label = QLabel()
        self.image_label.setObjectName("imageLabel")
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setFixedSize(200, 200)
        layout.addWidget(self.image_label)

        # Button layout
        button_layout = QHBoxLayout()
        button_layout.setObjectName("imageButtonLayout")
        button_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

        # Create buttons
        self.change_button = QPushButton("Change")
        self.change_button.setObjectName("changeImageButton")
        self.delete_button = QPushButton("Remove")
        self.delete_button.setObjectName("deleteImageButton")

        # Set button sizes
        for button in [self.change_button, self.delete_button]:
            button.setFixedWidth(97)
            button.setMinimumHeight(30)

        # Store buttons but don't connect signals yet
        self.change_button.clicked.connect(self._on_change_clicked)
        self.delete_button.clicked.connect(self._on_delete_clicked)

        # Add buttons to layout
        button_layout.addWidget(self.change_button)
        button_layout.addWidget(self.delete_button)
        button_layout.addStretch()

        layout.addLayout(button_layout)
        self.setLayout(layout)

    def _on_change_clicked(self) -> None:
        """Internal handler for change button clicks"""
        self.basic_image_changed.emit(self.image_label.toolTip())

    def _on_delete_clicked(self) -> None:
        """Internal handler for delete button clicks"""
        self.basic_image_removed.emit()
        self.image_label.clear()
        self.image_label.setToolTip("")

    def set_basic_image(self, image_path: Optional[str]) -> None:
        """Set or clear the displayed image."""
        logger.debug("Setting basic image", image_path=image_path)

        if not image_path:
            logger.debug("Clearing image display - no path provided")
            self.image_label.clear()
            self.image_label.setToolTip("")
            return

        # Validate file exists
        if not exists(image_path):
            logger.error("Image file not found", path=image_path)
            self._handle_image_error(f"Image file not found: {image_path}")
            return

        try:
            # Check cache first
            if image_path in self._pixmap_cache:
                logger.debug("Using cached image", path=image_path)
                pixmap = self._pixmap_cache[image_path]
            else:
                logger.debug("Loading new image", path=image_path)
                pixmap = QPixmap(image_path)
                if pixmap.isNull():
                    raise ValueError(f"Failed to load image: {image_path}")
                self._pixmap_cache[image_path] = pixmap

            scaled_pixmap = pixmap.scaled(
                self.image_label.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.image_label.setPixmap(scaled_pixmap)
            self.image_label.setToolTip(image_path)
            logger.debug("Successfully set image", path=image_path)

        except Exception as e:
            logger.error(
                "Failed to load image", error=str(e), path=image_path, exc_info=True
            )
            self._handle_image_error(str(e))

    def _handle_image_error(self, error_msg: str) -> None:
        """Centralized error handling for image operations."""
        self.image_label.clear()
        self.image_label.setToolTip("")
        QMessageBox.warning(self, "Image Error", f"Failed to load image: {error_msg}")

    def get_basic_image_path(self) -> Optional[str]:
        """Get the current image path."""
        path = self.image_label.toolTip()
        return path if path else None
