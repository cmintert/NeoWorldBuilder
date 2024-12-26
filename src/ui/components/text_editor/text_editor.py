from typing import Optional

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QTextEdit, QWidget, QVBoxLayout
from structlog import get_logger

from ui.components.text_editor.text_toolbar import TextToolbar

logger = get_logger(__name__)


class TextEditor(QWidget):
    """
    Enhanced text editor component with formatting capabilities.
    Encapsulates a QTextEdit and TextToolbar into a single component.

    Method naming conventions follow PyQt conventions.
    """

    textChanged = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """
        Initialize the text editor component.

        Args:
            parent: Optional parent widget
        """
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Initialize UI components."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Create text edit
        self.text_edit = QTextEdit(self)
        self.text_edit.setObjectName("descriptionInput")
        self.text_edit.setPlaceholderText("Enter description...")
        self.text_edit.setMinimumHeight(100)

        # Add formatting toolbar
        self.formatting_toolbar = TextToolbar(self.text_edit, self)

        # Add components to layout
        layout.addWidget(self.formatting_toolbar)
        layout.addWidget(self.text_edit)

    def setHtml(self, text: str) -> None:
        """Set the HTML content of the editor.

        Args:
            text: The HTML text to set
        """
        self.text_edit.setHtml(text)

    def toHtml(self) -> str:
        """Get the content as HTML.

        Returns:
            The editor content as HTML
        """
        return self.text_edit.toHtml()

    def toPlainText(self) -> str:
        """Get the content as plain text.

        Returns:
            The editor content as plain text
        """
        return self.text_edit.toPlainText()

    def clear(self) -> None:
        """Clear the editor content."""
        self.text_edit.clear()
