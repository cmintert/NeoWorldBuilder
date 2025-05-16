import re
from typing import Optional

from PyQt6.QtCore import pyqtSignal, Qt, QTimer
from PyQt6.QtGui import QMouseEvent
from PyQt6.QtWidgets import QTextEdit, QWidget, QVBoxLayout
from structlog import get_logger

from ui.components.quick_relation_dialog import QuickRelationDialog
from ui.components.text_editor.text_toolbar import TextToolbar

logger = get_logger(__name__)


class LinkableTextEdit(QTextEdit):
    """Custom QTextEdit that supports clickable links."""

    linkClicked = pyqtSignal(str)  # Emit the node name when clicked

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self._clickable_links = {}  # Maps positions to node names

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Handle mouse press events to detect link clicks."""
        if event.button() == Qt.MouseButton.LeftButton:
            cursor = self.cursorForPosition(event.pos())
            char_format = cursor.charFormat()
            if char_format.isAnchor():
                node_name = char_format.anchorHref()
                if node_name:
                    self.linkClicked.emit(node_name)
                    return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """Handle mouse movement to update cursor."""
        cursor = self.cursorForPosition(event.pos())
        char_format = cursor.charFormat()

        if char_format.isAnchor():
            self.viewport().setCursor(Qt.CursorShape.PointingHandCursor)
        else:
            self.viewport().setCursor(Qt.CursorShape.IBeamCursor)

        super().mouseMoveEvent(event)


class TextEditor(QWidget):
    """Enhanced text editor component with formatting capabilities."""

    # Forward the textChanged signal from internal QTextEdit
    textChanged = pyqtSignal()
    enhancementRequested = pyqtSignal()

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

        # Create text edit with link support
        self.text_edit = LinkableTextEdit(self)
        self.text_edit.setObjectName("descriptionInput")
        self.text_edit.setPlaceholderText("Enter description...")
        self.text_edit.setMinimumHeight(100)
        self.text_edit.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.text_edit.customContextMenuRequested.connect(self._show_context_menu)
        self.text_edit.linkClicked.connect(self._handle_node_click)

        # Add formatting toolbar
        self.formatting_toolbar = TextToolbar(self.text_edit, self)

        # Add components to layout
        layout.addWidget(self.formatting_toolbar)
        layout.addWidget(self.text_edit)

    def _connect_signals(self) -> None:
        """Connect internal signals."""
        self.text_edit.textChanged.connect(self._handle_text_changed)
        self.text_edit.textChanged.connect(self.textChanged.emit)
        self.formatting_toolbar.enhancementRequested.connect(self.enhancementRequested)

    def _show_context_menu(self, position) -> None:
        """Show custom context menu with node creation option."""
        menu = self.text_edit.createStandardContextMenu()

        # Only add the create node option if there's selected text
        if self.text_edit.textCursor().hasSelection():
            menu.addSeparator()
            create_node_action = menu.addAction("Create Node from Selection")
            create_node_action.triggered.connect(self._handle_create_node_request)

        menu.exec(self.text_edit.mapToGlobal(position))

    def _scan_for_node_names(self) -> None:
        """Scan the text content for node names and format them while preserving rich text."""
        if not self.name_cache_service:
            logger.warning("scan_skipped_service_not_initialized")
            return

        try:
            # Get current cursor and selection state
            cursor = self.text_edit.textCursor()
            has_selection = cursor.hasSelection()
            selection_start = cursor.selectionStart()
            selection_end = cursor.selectionEnd()

            # Store current content before formatting
            original_content = self.text_edit.toHtml()

            # Get cached node names and verify cache
            node_names = self.name_cache_service.get_cached_names()
            if not node_names:
                return

            # Create regex pattern from node names
            sorted_names = sorted(node_names, key=len, reverse=True)
            pattern = (
                r"\b(" + "|".join(re.escape(name) for name in sorted_names) + r")\b"
            )

            # Split content into HTML tags and text
            parts = re.split(r"(<[^>]+>)", original_content)

            # Process each part
            processed_parts = []
            for part in parts:
                if part.startswith("<"):
                    processed_parts.append(part)  # Keep HTML tags as-is
                else:
                    # Apply node name highlighting only to text content
                    processed = re.sub(
                        pattern,
                        lambda m: (
                            f'<a href="{m.group(0)}" class="node-reference" '
                            f'style="background-color: #e0e0e0; '
                            f"border-radius: 3px; padding: 0 2px; "
                            f'text-decoration: none; color: inherit;">'
                            f"{m.group(0)}</a>"
                        ),
                        part,
                    )
                    processed_parts.append(processed)

            # Join processed parts back together
            processed_content = "".join(processed_parts)

            # Block signals during HTML update to prevent recursion
            self.text_edit.blockSignals(True)
            try:
                self.text_edit.setHtml(processed_content)

                # Restore selection
                cursor = self.text_edit.textCursor()
                if has_selection:
                    cursor.setPosition(selection_start)
                    cursor.setPosition(selection_end, cursor.MoveMode.KeepAnchor)
                else:
                    cursor.setPosition(selection_start)
                self.text_edit.setTextCursor(cursor)
            finally:
                self.text_edit.blockSignals(False)

        except Exception as e:
            logger.error("scan_failed", error=str(e))

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
        """Handle clicks on node name links."""
        if url:
            self.main_ui.name_input.setText(url)

    def setHtml(self, text: str) -> None:
        """Set the HTML content of the editor."""
        self.text_edit.setHtml(text)

    def toHtml(self) -> str:
        """Get the content as HTML, cleaned for saving."""
        """Get the content as HTML, cleaned for saving."""
        current_html = self.text_edit.toHtml()

        # First remove our link formatting
        cleaned = re.sub(
            r'<a href="[^"]*" class="node-reference"[^>]*style="[^"]*">([^<]+)</a>',
            r"\1",  # Keep just the text content
            current_html,
        )

        # Then remove any empty paragraphs that might have been created
        cleaned = re.sub(r"<p[^>]*>\s*<br\s*/?>\s*</p>", "", cleaned)

        return cleaned if cleaned else ""

    def toPlainText(self) -> str:
        """Get the content as plain text."""
        return self.text_edit.toPlainText()

    def clear(self) -> None:
        """Clear the editor content."""
        self.text_edit.clear()
