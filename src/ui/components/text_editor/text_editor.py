from typing import Optional

from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtWidgets import QTextEdit, QWidget, QVBoxLayout
from structlog import get_logger

from ui.components.quick_relation_dialog import QuickRelationDialog
from ui.components.text_editor.text_toolbar import TextToolbar

logger = get_logger(__name__)


class TextEditor(QWidget):
    """Enhanced text editor component with formatting capabilities."""

    # Forward the textChanged signal from internal QTextEdit
    textChanged = pyqtSignal()

    # Signal emitted when user requests node creation from selection
    createNodeRequested = pyqtSignal(
        str, str, str, str
    )  # selected_text, surrounding_context

    def __init__(
        self, main_ui: "WorldBuildingUI", parent: Optional[QWidget] = None
    ) -> None:
        """
        Initialize the text editor component.

               Args:
                   main_ui: Reference to the main WorldBuildingUI instance
                   parent: Optional parent widget
        """
        super().__init__(parent)
        self.main_ui = main_ui
        self._setup_ui()
        self._connect_signals()

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
        self.text_edit.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.text_edit.customContextMenuRequested.connect(self._show_context_menu)

        # Add formatting toolbar
        self.formatting_toolbar = TextToolbar(self.text_edit, self)

        # Add components to layout
        layout.addWidget(self.formatting_toolbar)
        layout.addWidget(self.text_edit)

    def _connect_signals(self) -> None:
        """Connect internal signals."""
        self.text_edit.textChanged.connect(self.textChanged.emit)

    def _show_context_menu(self, position) -> None:
        """Show custom context menu with node creation option."""
        menu = self.text_edit.createStandardContextMenu()

        # Only add the create node option if there's selected text
        if self.text_edit.textCursor().hasSelection():
            menu.addSeparator()
            create_node_action = menu.addAction("Create Node from Selection")
            create_node_action.triggered.connect(self._handle_create_node_request)

        menu.exec(self.text_edit.mapToGlobal(position))

    def _handle_create_node_request(self) -> None:
        """Handle request to create node from selected text."""
        cursor = self.text_edit.textCursor()
        if cursor.hasSelection():
            selected_text = cursor.selectedText()

            dialog = QuickRelationDialog(selected_text, self)

            if dialog.exec():
                rel_type, target, direction, properties = dialog.get_values()
                self.main_ui.add_relationship_row(
                    rel_type, target, direction, properties
                )
                self.createNodeRequested.emit(
                    target, rel_type, direction, str(properties)
                )

    def setHtml(self, text: str) -> None:
        """Set the HTML content of the editor."""
        self.text_edit.setHtml(text)

    def toHtml(self) -> str:
        """Get the content as HTML."""
        return self.text_edit.toHtml()

    def toPlainText(self) -> str:
        """Get the content as plain text."""
        return self.text_edit.toPlainText()

    def clear(self) -> None:
        """Clear the editor content."""
        self.text_edit.clear()
