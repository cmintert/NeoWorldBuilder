"""Text editor component with link detection and rich text formatting capabilities.

This module provides a specialized text editor implementation that supports clickable
links, rich text formatting, and node name detection. It consists of two main classes:
LinkableTextEdit for basic link functionality and TextEditor which adds advanced
features like node name scanning and formatting tools.

Classes:
    LinkableTextEdit: A QTextEdit subclass that supports clickable links.
    TextEditor: Main text editor component with formatting and node detection.
"""

import re
from typing import Optional, Dict, TYPE_CHECKING

from PyQt6.QtCore import pyqtSignal, Qt, QTimer, QPoint
from PyQt6.QtGui import QMouseEvent, QTextCursor
from PyQt6.QtWidgets import QTextEdit, QWidget, QVBoxLayout, QMenu
from structlog import get_logger

from ui.components.quick_relation_dialog import QuickRelationDialog
from ui.components.text_editor.text_toolbar import TextToolbar

if TYPE_CHECKING:
    from ui.main_window import WorldBuildingUI
    from services.name_cache_service import NameCacheService

logger = get_logger(__name__)


class LinkableTextEdit(QTextEdit):
    """A QTextEdit subclass that implements clickable link functionality.

    This class extends QTextEdit to provide support for clickable links within the text.
    It tracks mouse movement to update cursor appearance and emits signals when links
    are clicked.

    Attributes:
        linkClicked (pyqtSignal): Signal emitted when a link is clicked, passes the node name.
        _clickable_links (Dict[int, str]): Maps text positions to node names.
    """

    linkClicked = pyqtSignal(str)  # Emit the node name when clicked

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Initialize the LinkableTextEdit widget.

        Args:
            parent: Optional parent widget. Defaults to None.
        """
        super().__init__(parent)
        self.setMouseTracking(True)
        self._clickable_links: Dict[int, str] = {}  # Maps positions to node names

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Handle mouse press events to detect link clicks.

        Checks if the clicked position contains a link and emits the linkClicked
        signal if a link is found.

        Args:
            event: The mouse event containing click information.
        """
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
        """Handle mouse movement to update the cursor appearance.

        Changes the cursor to a pointing hand when hovering over links.

        Args:
            event: The mouse event containing movement information.
        """
        cursor = self.cursorForPosition(event.pos())
        char_format = cursor.charFormat()

        if char_format.isAnchor():
            self.viewport().setCursor(Qt.CursorShape.PointingHandCursor)
        else:
            self.viewport().setCursor(Qt.CursorShape.IBeamCursor)

        super().mouseMoveEvent(event)


class TextEditor(QWidget):
    """Enhanced text editor component with formatting capabilities.

    This widget provides a rich text editor with additional features like node name
    detection, link support, and text formatting. It includes a toolbar for text
    formatting options and supports creating nodes from selected text.

    Attributes:
        textChanged (pyqtSignal): Emitted when the text content changes.
        enhancementRequested (pyqtSignal): Emitted when text enhancement is requested.
        enhancedEnhancementRequested (pyqtSignal): Emitted for enhanced text enhancement.
        createNodeRequested (pyqtSignal): Emitted when node creation is requested.
        main_ui (WorldBuildingUI): Reference to the main UI.
        name_cache_service (NameCacheService): Service for caching node names.
        scan_timer (QTimer): Timer for scheduling node name scans.
        text_edit (LinkableTextEdit): The main text editing widget.
        formatting_toolbar (TextToolbar): Toolbar with formatting options.
    """

    textChanged = pyqtSignal()
    enhancementRequested = pyqtSignal()
    enhancedEnhancementRequested = pyqtSignal(
        str, int, str
    )  # template, focus, depth, instructions
    createNodeRequested = pyqtSignal(
        str, str, str, str
    )  # target, rel_type, direction, properties

    def __init__(
        self, main_ui: "WorldBuildingUI", parent: Optional[QWidget] = None
    ) -> None:
        """Initialize the text editor component.

        Args:
            main_ui: Reference to the main WorldBuildingUI instance for coordination.
            parent: Optional parent widget. Defaults to None.
        """
        super().__init__(parent)
        self.main_ui: "WorldBuildingUI" = main_ui
        self.name_cache_service: Optional["NameCacheService"] = None
        self.scan_timer: QTimer = QTimer(self)
        self.text_edit: LinkableTextEdit
        self.formatting_toolbar: TextToolbar

        # Setup scanning timer
        self.scan_timer.setInterval(2000)  # 2 seconds
        self.scan_timer.setSingleShot(True)
        self.scan_timer.timeout.connect(self._scan_for_node_names)

        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self) -> None:
        """Initialize and arrange the UI components.

        Creates and configures:
            - Main text editor widget with link support
            - Formatting toolbar
            - Layout arrangement
            - Context menu support
        """
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
        """Connect internal signal handlers.

        Connects:
            - Text change handlers
            - Enhancement request signals
            - Text formatting signals
        """
        self.text_edit.textChanged.connect(self._handle_text_changed)
        self.text_edit.textChanged.connect(self.textChanged.emit)
        self.formatting_toolbar.enhancementRequested.connect(self.enhancementRequested)
        self.formatting_toolbar.enhancedEnhancementRequested.connect(
            self.enhancedEnhancementRequested.emit
        )

    def _show_context_menu(self, position: QPoint) -> None:
        """Display the context menu at the specified position.

        Shows a custom context menu with additional options like node creation
        when text is selected.

        Args:
            position: Screen coordinates where the menu should appear.
        """
        menu: QMenu = self.text_edit.createStandardContextMenu()

        # Only add the create node option if there's selected text
        if self.text_edit.textCursor().hasSelection():
            menu.addSeparator()
            create_node_action = menu.addAction("Create Node from Selection")
            create_node_action.triggered.connect(self._handle_create_node_request)

        menu.exec(self.text_edit.mapToGlobal(position))

    def _scan_for_node_names(self) -> None:
        """Scan and format node names in the text content.

        Searches for known node names in the text and formats them as clickable links
        while preserving existing rich text formatting. Handles:
            - Node name detection
            - Link formatting
            - Selection preservation
            - HTML structure preservation

        Note:
            This method is triggered by the scan timer to avoid excessive processing
            during rapid text changes.
        """
        if not self.name_cache_service:
            logger.warning("scan_skipped_service_not_initialized")
            return

        try:
            # Get current cursor and selection state
            cursor: QTextCursor = self.text_edit.textCursor()
            has_selection: bool = cursor.hasSelection()
            selection_start: int = cursor.selectionStart()
            selection_end: int = cursor.selectionEnd()

            # Store current content before formatting
            original_content: str = self.text_edit.toHtml()

            # Get cached node names and verify cache
            node_names: Optional[list[str]] = self.name_cache_service.get_cached_names()
            if not node_names:
                return

            # Create regex pattern from node names
            sorted_names: list[str] = sorted(node_names, key=len, reverse=True)
            pattern: str = (
                r"\b(" + "|".join(re.escape(name) for name in sorted_names) + r")\b"
            )

            # Split content into HTML tags and text
            parts: list[str] = re.split(r"(<[^>]+>)", original_content)

            # Process each part
            processed_parts: list[str] = []
            for part in parts:
                if part.startswith("<"):
                    processed_parts.append(part)  # Keep HTML tags as-is
                else:
                    # Apply node name highlighting only to text content
                    processed: str = re.sub(
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
            processed_content: str = "".join(processed_parts)

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
        """Process a request to create a new node from selected text.

        Opens a dialog for configuring the new node relationship and emits
        the createNodeRequested signal with the user's configuration.

        Note:
            This is triggered from the context menu when text is selected.
        """
        cursor: QTextCursor = self.text_edit.textCursor()
        if cursor.hasSelection():
            selected_text: str = cursor.selectedText()

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
        """Handle text content changes.

        Starts the node name scanning timer to schedule a new scan
        after the user stops typing.
        """
        # Reset and restart the timer
        if self.name_cache_service:
            self.scan_timer.start()

    def _handle_node_click(self, url: str) -> None:
        """Process clicks on node name links.

        Updates the main UI's name input field with the clicked node name.

        Args:
            url: The node name that was clicked (stored in the link's href).
        """
        if url:
            self.main_ui.name_input.setText(url)

    def setHtml(self, text: str) -> None:
        """Set the editor's content as HTML.

        Args:
            text: The HTML content to display in the editor.
        """
        self.text_edit.setHtml(text)

    def toHtml(self) -> str:
        """Get the editor's content as cleaned HTML.

        Returns:
            str: The HTML content with link formatting and empty paragraphs removed.

        Note:
            This method cleans up the HTML by removing the custom link formatting
            and empty paragraphs before returning.
        """
        current_html: str = self.text_edit.toHtml()

        # First remove our link formatting
        cleaned: str = re.sub(
            r'<a href="[^"]*" class="node-reference"[^>]*style="[^"]*">([^<]+)</a>',
            r"\1",  # Keep just the text content
            current_html,
        )

        # Then remove any empty paragraphs that might have been created
        cleaned = re.sub(r"<p[^>]*>\s*<br\s*/?>\s*</p>", "", cleaned)

        return cleaned if cleaned else ""

    def toPlainText(self) -> str:
        """Get the editor's content as plain text.

        Returns:
            str: The unformatted text content of the editor.
        """
        return self.text_edit.toPlainText()

    def clear(self) -> None:
        """Clear all content from the editor."""
        self.text_edit.clear()
