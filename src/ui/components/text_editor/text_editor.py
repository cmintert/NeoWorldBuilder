import re
from typing import Optional

from PyQt6.QtCore import pyqtSignal, Qt, QTimer
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
        self.name_cache_service = None

        # Setup scanning timer
        self.scan_timer = QTimer(self)
        self.scan_timer.setInterval(2000)  # 2 seconds
        self.scan_timer.setSingleShot(True)
        self.scan_timer.timeout.connect(self._scan_for_node_names)

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

        # Enable link clicking
        self.text_edit.setOpenLinks(False)
        self.text_edit.anchorClicked.connect(self._handle_node_click)

        # Add formatting toolbar
        self.formatting_toolbar = TextToolbar(self.text_edit, self)

        # Add components to layout
        layout.addWidget(self.formatting_toolbar)
        layout.addWidget(self.text_edit)

    def _connect_signals(self) -> None:
        """Connect internal signals."""
        self.text_edit.textChanged.connect(self._handle_text_changed)
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

    def _handle_text_changed(self) -> None:
        """Handle text changes and schedule a rescan."""
        # Reset and restart the timer
        if self.name_cache_service:
            self.scan_timer.start()

    def _handle_node_click(self, url) -> None:
        """Handle clicks on node name links."""
        node_name = url.toString()
        if node_name:
            # Load the clicked node using main UI's name input
            self.main_ui.name_input.setText(node_name)

    def _scan_for_node_names(self) -> None:
        """Scan the text content for node names and format them."""
        if not self.name_cache_service:
            logger.warning("scan_skipped_service_not_initialized")
            return

        try:
            # Get current cursor position
            cursor = self.text_edit.textCursor()
            current_position = cursor.position()

            # Get cached node names
            node_names = self.name_cache_service.get_cached_names()
            if not node_names:
                return

            # Create regex pattern from node names
            # Sort by length descending to handle overlapping matches
            sorted_names = sorted(node_names, key=len, reverse=True)
            pattern = (
                r"\b(" + "|".join(re.escape(name) for name in sorted_names) + r")\b"
            )

            # Get current text
            current_text = self.text_edit.toPlainText()

            # Find all matches
            matches = list(re.finditer(pattern, current_text))
            if not matches:
                return

            # Create HTML with links
            last_end = 0
            formatted_parts = []

            for match in matches:
                start, end = match.span()
                node_name = match.group(0)

                # Add text before match
                formatted_parts.append(current_text[last_end:start])

                # Add formatted node name
                formatted_parts.append(
                    f'<a href="{node_name}" style="background-color: #e0e0e0; '
                    f"text-decoration: none; color: inherit; border-radius: 3px; "
                    f'padding: 0 2px;">{node_name}</a>'
                )

                last_end = end

            # Add remaining text
            formatted_parts.append(current_text[last_end:])

            # Combine all parts
            formatted_text = "".join(formatted_parts)

            # Update text edit with formatted content
            self.text_edit.setHtml(formatted_text)

            # Restore cursor position
            cursor.setPosition(current_position)
            self.cursor = self.text_edit.setTextCursor(cursor)

        except Exception as e:
            logger.error("scan_failed", error=str(e))

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
