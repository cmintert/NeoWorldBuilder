from __future__ import annotations

import logging
from contextlib import contextmanager
from dataclasses import dataclass, field
from functools import partial
from typing import Optional, Callable, Dict, Any, TypeVar, Protocol

from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import (
    QFont,
    QAction,
    QTextCharFormat,
    QTextCursor,
    QKeySequence,
    QColor,
    QTextBlockFormat,
)
from PyQt6.QtWidgets import (
    QToolBar,
    QWidget,
    QTextEdit,
    QColorDialog,
    QComboBox,
    QWidgetAction,
    QToolButton,
    QMenu,
    QFontComboBox,
    QVBoxLayout,
)

# Type variables for generic protocols
T = TypeVar("T")

# Configure logging
logger = logging.getLogger(__name__)


class ToolbarRow(QToolBar):
    """Represents a single row in the text formatting toolbar.

    A specialized QToolBar that provides consistent styling and behavior
    for the text formatting toolbar rows.

    Args:
        parent: The parent widget. Defaults to None.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setIconSize(QSize(16, 16))
        self.setMovable(False)


class FormatChange(Protocol):
    """Protocol for format change operations.

    Defines the interface for objects that can apply and revert
    text formatting changes to a QTextCursor.
    """

    def apply(self, cursor: QTextCursor) -> None:
        """Apply the format change to the cursor.

        Args:
            cursor: The text cursor to apply formatting to.
        """
        ...

    def revert(self, cursor: QTextCursor) -> None:
        """Revert the format change.

        Args:
            cursor: The text cursor to revert formatting changes on.
        """
        ...


@dataclass
class TextStyle:
    """Represents a complete text style configuration.

    A dataclass that encapsulates all formatting attributes for a text style,
    including font properties, colors, and alignment.

    Args:
        name: The name of the style.
        size: Font size in points.
        weight: Font weight (boldness).
        family: Font family name. Defaults to "Arial".
        color: Text color. Defaults to black.
        background: Background/highlight color. Defaults to None.
        italic: Whether text is italic. Defaults to False.
        underline: Whether text is underlined. Defaults to False.
        alignment: Text alignment. Defaults to left alignment.
    """

    name: str
    size: int
    weight: QFont.Weight
    family: str = "Arial"
    color: QColor = field(default_factory=lambda: QColor("black"))
    background: Optional[QColor] = None
    italic: bool = False
    underline: bool = False
    alignment: Qt.AlignmentFlag = Qt.AlignmentFlag.AlignLeft

    def to_char_format(self) -> QTextCharFormat:
        """Convert style to QTextCharFormat.

        Creates and configures a QTextCharFormat with all the text styling
        attributes defined in this TextStyle.

        Returns:
            A QTextCharFormat configured with this style's attributes.
        """
        fmt = QTextCharFormat()
        font = QFont(self.family, self.size, self.weight)
        font.setItalic(self.italic)
        font.setUnderline(self.underline)
        fmt.setFont(font)
        fmt.setForeground(self.color)
        if self.background:
            fmt.setBackground(self.background)
        return fmt


class StyleRegistry:
    """Registry for managing text styles.

    Maintains a collection of named text styles that can be applied
    to text in the editor.
    """

    def __init__(self) -> None:
        """Initialize the style registry with default styles."""
        self._styles: Dict[str, TextStyle] = {}
        self._initialize_default_styles()

    def _initialize_default_styles(self) -> None:
        """Initialize default text styles.

        Creates and registers a set of predefined styles including headings,
        body text, code blocks, and quotes.
        """
        self._styles.update(
            {
                "h1": TextStyle("Heading 1", 16, QFont.Weight.Bold),
                "h2": TextStyle("Heading 2", 14, QFont.Weight.Medium),
                "h3": TextStyle("Heading 3", 12, QFont.Weight.Normal),
                "body": TextStyle("Body", 10, QFont.Weight.Normal),
                "code": TextStyle(
                    "Code",
                    10,
                    QFont.Weight.Normal,
                    family="Courier New",
                    background=QColor("#f5f5f5"),
                ),
                "quote": TextStyle(
                    "Quote",
                    10,
                    QFont.Weight.Normal,
                    italic=True,
                    color=QColor("#666666"),
                ),
            }
        )

    def get_style(self, name: str) -> TextStyle:
        """Get a style by name.

        Args:
            name: The name of the style to retrieve.

        Returns:
            The requested TextStyle, or the body style if name not found.
        """
        return self._styles.get(name, self._styles["body"])

    def register_style(self, name: str, style: TextStyle) -> None:
        """Register a new style.

        Args:
            name: The name to register the style under.
            style: The TextStyle to register.
        """
        self._styles[name] = style


class UndoableFormatChange:
    """Represents an undoable formatting operation.

    Tracks formatting operations to allow for undoing them later.

    Args:
        operation: Function that applies a formatting change to a cursor.
    """

    def __init__(self, operation: Callable[[QTextCursor], Any]) -> None:
        """Initialize the undoable format change.

        Args:
            operation: The formatting operation to apply.
        """
        self.operation = operation
        self.previous_format: Optional[QTextCharFormat] = None

    def apply(self, cursor: QTextCursor) -> None:
        """Apply the format change.

        Saves the current format before applying the new one.

        Args:
            cursor: The text cursor to apply formatting to.
        """
        self.previous_format = cursor.charFormat()
        self.operation(cursor)

    def revert(self, cursor: QTextCursor) -> None:
        """Revert to previous format.

        Args:
            cursor: The text cursor to revert formatting on.
        """
        if self.previous_format:
            cursor.setCharFormat(self.previous_format)


class FormattingContext:
    """Context manager for formatting operations.

    Provides a convenient way to group formatting operations into a single
    undo operation using a context manager.

    Args:
        text_edit: The QTextEdit to apply formatting to.
    """

    def __init__(self, text_edit: QTextEdit) -> None:
        """Initialize the formatting context.

        Args:
            text_edit: The text edit widget to operate on.
        """
        self.text_edit = text_edit
        self.cursor = text_edit.textCursor()

    def __enter__(self) -> QTextCursor:
        """Begin the editing block and return the cursor.

        Returns:
            The text cursor to use for operations.
        """
        self.cursor.beginEditBlock()
        return self.cursor

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """End the editing block and handle any exceptions.

        Args:
            exc_type: Exception type if an exception occurred.
            exc_val: Exception value if an exception occurred.
            exc_tb: Exception traceback if an exception occurred.
        """
        self.cursor.endEditBlock()
        if exc_type:
            logger.error(f"Error during formatting: {exc_val}")


class TextToolbar(QWidget):
    """Advanced toolbar for text formatting operations.

    Provides a comprehensive set of text formatting controls organized into
    multiple rows of toolbars.

    Args:
        text_edit: The QTextEdit to apply formatting to.
        parent: The parent widget. Defaults to None.
        style_registry: Registry of text styles. If not provided, a default one is created.

    Signals:
        styleChanged: Emitted when a named style is applied.
        formatChanged: Emitted when text format changes.
        enhancementRequested: Emitted when basic AI enhancement is requested.
        enhancedEnhancementRequested: Emitted when advanced AI enhancement is requested.
    """

    # Signals
    styleChanged = pyqtSignal(str)  # Style name
    formatChanged = pyqtSignal(QTextCharFormat)
    enhancementRequested = pyqtSignal()
    enhancedEnhancementRequested = pyqtSignal(str, str, int, str)

    def __init__(
        self,
        text_edit: QTextEdit,
        parent: Optional[QWidget] = None,
        style_registry: Optional[StyleRegistry] = None,
    ) -> None:
        """Initialize the toolbar.

        Args:
            text_edit: The text edit widget to operate on.
            parent: The parent widget. Defaults to None.
            style_registry: Registry of text styles. If not provided, a default one is created.
        """
        super().__init__(parent)

        self.text_edit = text_edit
        self.style_registry = style_registry or StyleRegistry()
        self._undo_stack: list[UndoableFormatChange] = []

        # Create layout
        layout = QVBoxLayout(self)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)

        # Create two toolbar rows
        self.row1 = ToolbarRow(self)
        self.row2 = ToolbarRow(self)

        layout.addWidget(self.row1)
        layout.addWidget(self.row2)

        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self) -> None:
        """Set up the toolbar UI in two rows.

        Organizes formatting controls into two logical rows:
        - First row: style selectors and font controls
        - Second row: formatting controls, alignment, and AI enhancement
        """
        # First row - styles and font controls
        self._add_style_selector(self.row1)
        self.row1.addSeparator()
        self._add_font_controls(self.row1)
        self.row1.addSeparator()
        self._add_font_size_controls(self.row1)

        # Second row - formatting controls
        self._add_basic_formatting(self.row2)
        self.row2.addSeparator()
        self._add_advanced_formatting(self.row2)
        self.row2.addSeparator()
        self._add_alignment_controls(self.row2)

    def _add_style_selector(self, toolbar: QToolBar) -> None:
        """Add the style selection dropdown.

        Creates a dropdown button with all available text styles.

        Args:
            toolbar: The toolbar to add the selector to.
        """
        style_menu = QMenu(toolbar)
        for style_name, style in self.style_registry._styles.items():
            action = style_menu.addAction(style.name)
            action.triggered.connect(partial(self._apply_style, style_name))

        style_button = QToolButton(toolbar)
        style_button.setText("Default Styles")
        style_button.setMinimumWidth(110)
        style_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        style_button.setMenu(style_menu)

        style_action = QWidgetAction(toolbar)
        style_action.setDefaultWidget(style_button)
        toolbar.addAction(style_action)

    def _add_font_controls(self, toolbar: QToolBar) -> None:
        """Add font family selector.

        Adds a font combo box for selecting text font families.

        Args:
            toolbar: The toolbar to add the controls to.
        """
        font_combo = QFontComboBox(toolbar)
        font_combo.setMinimumWidth(150)
        font_combo.currentFontChanged.connect(self._set_font_family)
        toolbar.addWidget(font_combo)

    def _get_standard_font_sizes(self) -> list[int]:
        """Return a list of standard font sizes.

        Returns:
            A list of common font sizes in points.
        """
        return [8, 9, 10, 11, 12, 14, 16, 18, 20, 22, 24, 26, 28, 36, 48, 72]

    def _handle_font_size_change(self, text: str) -> None:
        """Handle font size changes from the combo box.

        Validates and applies font size changes.

        Args:
            text: The size as text from the combo box.
        """
        try:
            size = int(text)
            if 4 <= size <= 100:  # Reasonable size limits
                self._set_font_size(size)
        except ValueError:
            pass

    def _add_font_size_controls(self, toolbar: QToolBar) -> None:
        """Add font size selector as a dropdown.

        Creates an editable combo box with standard font sizes.

        Args:
            toolbar: The toolbar to add the size controls to.
        """
        size_combo = QComboBox(toolbar)
        size_combo.setMinimumWidth(60)
        size_combo.setEditable(True)

        # Add standard sizes
        for size in self._get_standard_font_sizes():
            size_combo.addItem(str(size), size)

        # Set default size
        default_index = size_combo.findData(10)
        if default_index >= 0:
            size_combo.setCurrentIndex(default_index)

        # Handle both editing and selection
        size_combo.currentTextChanged.connect(self._handle_font_size_change)

        toolbar.addWidget(size_combo)

    def _add_basic_formatting(self, toolbar: QToolBar) -> None:
        """Add basic formatting buttons.

        Adds bold, italic, and underline formatting controls.

        Args:
            toolbar: The toolbar to add the controls to.
        """
        formats = {
            "Bold": (self._toggle_bold, "Ctrl+B"),
            "Italic": (self._toggle_italic, "Ctrl+I"),
            "Underline": (self._toggle_underline, "Ctrl+U"),
        }

        for name, (slot, shortcut) in formats.items():
            self._add_formatting_action(toolbar, name, slot, True, shortcut)

    def _add_advanced_formatting(self, toolbar: QToolBar) -> None:
        """Add color picker and other advanced formatting options.

        Adds text color, background color, and AI enhancement controls.

        Args:
            toolbar: The toolbar to add the controls to.
        """
        color_button = QToolButton(toolbar)
        color_button.setText("Text Color")
        color_button.clicked.connect(self._choose_color)
        toolbar.addWidget(color_button)

        bg_color_button = QToolButton(toolbar)
        bg_color_button.setText("Highlight")
        bg_color_button.clicked.connect(self._choose_background_color)
        toolbar.addWidget(bg_color_button)

        # enhance button with dropdown
        enhance_button = QToolButton(toolbar)
        enhance_button.setText("Enhance with AI")
        enhance_button.setToolTip("Use AI to enhance the text description")
        enhance_button.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)

        # Create menu for the button
        enhance_menu = QMenu()
        enhance_action = enhance_menu.addAction("Quick Enhance")
        enhance_action.triggered.connect(self._request_enhancement)

        advanced_enhance_action = enhance_menu.addAction("Advanced Enhance...")
        advanced_enhance_action.triggered.connect(self._request_enhanced_enhancement)

        enhance_button.setMenu(enhance_menu)
        enhance_button.clicked.connect(self._request_enhancement)  # Default action

        toolbar.addWidget(enhance_button)

    def _add_alignment_controls(self, toolbar: QToolBar) -> None:
        """Add text alignment controls.

        Adds buttons for left, center, right, and justified text alignment.

        Args:
            toolbar: The toolbar to add the alignment controls to.
        """
        alignments = {
            "Left": Qt.AlignmentFlag.AlignLeft,
            "Center": Qt.AlignmentFlag.AlignCenter,
            "Right": Qt.AlignmentFlag.AlignRight,
            "Justify": Qt.AlignmentFlag.AlignJustify,
        }

        for name, alignment in alignments.items():
            self._add_formatting_action(
                toolbar, name, partial(self._set_alignment, alignment), True
            )

    def _choose_background_color(self) -> None:
        """Open color picker dialog for background color.

        Displays a color picker and applies the selected background color to text.
        """
        color = QColorDialog.getColor(
            self.text_edit.textBackgroundColor(), self, "Choose Background Color"
        )

        if color.isValid():
            with FormattingContext(self.text_edit) as cursor:
                char_format = cursor.charFormat()
                char_format.setBackground(color)
                cursor.setCharFormat(char_format)

    def _add_formatting_action(
        self,
        toolbar: QToolBar,
        text: str,
        slot: Callable,
        checkable: bool = False,
        shortcut: Optional[str] = None,
    ) -> QAction:
        """Add a formatting action to the toolbar.

        Creates an action with specified properties and adds it to the toolbar.

        Args:
            toolbar: The toolbar to add the action to.
            text: The text/name of the action.
            slot: The function to call when triggered.
            checkable: Whether the action can be toggled. Defaults to False.
            shortcut: Keyboard shortcut for the action. Defaults to None.

        Returns:
            The created QAction.
        """
        action = QAction(text, toolbar)
        action.setCheckable(checkable)
        action.triggered.connect(slot)

        if shortcut:
            action.setShortcut(QKeySequence(shortcut))
            action.setShortcutContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)

        toolbar.addAction(action)
        return action

    def _request_enhanced_enhancement(self) -> None:
        """Request AI enhancement with template options."""
        from ui.components.enhanced_prompt_dialog import EnhancedPromptDialog
        import logging

        logger = logging.getLogger(__name__)

        try:
            # Find parent until WorldBuildingUI
            parent = self.text_edit.parent()
            while parent and not parent.__class__.__name__ == "WorldBuildingUI":
                parent = parent.parent()

            # Get the controller from WorldBuildingUI
            if parent and hasattr(parent, "controller"):
                controller = parent.controller
                prompt_template_service = controller.prompt_template_service

                # Create and show the dialog
                templates = prompt_template_service.get_all_templates()
                dialog = EnhancedPromptDialog(self.text_edit.window(), templates)
                if dialog.exec():
                    template = dialog.get_selected_template()
                    focus_type = dialog.get_focus_type()
                    context_depth = dialog.get_context_depth()
                    custom_instructions = dialog.get_custom_instructions()

                    # Emit signal with enhancement parameters
                    self.enhancedEnhancementRequested.emit(
                        template.id if template else focus_type,
                        focus_type,
                        context_depth,
                        custom_instructions,
                    )
            else:
                from PyQt6.QtWidgets import QMessageBox

                QMessageBox.critical(
                    self.text_edit.window(),
                    "Feature Unavailable",
                    "Cannot access template service. The application structure may have changed.",
                )
        except Exception as e:
            logger.error(f"Error in _request_enhanced_enhancement: {str(e)}")
            from PyQt6.QtWidgets import QMessageBox

            QMessageBox.critical(
                self.text_edit.window(), "Error", f"An error occurred: {str(e)}"
            )

    def _connect_signals(self) -> None:
        """Connect to text edit signals.

        Sets up connections between text edit events and toolbar state updates.
        """
        self.text_edit.selectionChanged.connect(self._update_toolbar_state)
        self.text_edit.currentCharFormatChanged.connect(
            lambda fmt: self.formatChanged.emit(fmt)
        )

    def actions(self) -> list[QAction]:
        """Return all actions from both toolbar rows.

        Returns:
            A combined list of all actions from all toolbar rows.
        """
        return self.row1.actions() + self.row2.actions()

    def _apply_style(self, style_name: str) -> None:
        """Apply a named style to the selection.

        Sets character and block formatting based on the named style.

        Args:
            style_name: The name of the style to apply.
        """
        style = self.style_registry.get_style(style_name)

        with FormattingContext(self.text_edit) as cursor:
            char_format = style.to_char_format()
            cursor.setCharFormat(char_format)

            # Apply block format for alignment
            block_format = QTextBlockFormat()
            block_format.setAlignment(style.alignment)
            cursor.setBlockFormat(block_format)

        self.styleChanged.emit(style_name)

    def _set_font_family(self, font: QFont) -> None:
        """Set font family for selection.

        Args:
            font: The font to apply to the selection.
        """
        with FormattingContext(self.text_edit) as cursor:
            char_format = cursor.charFormat()
            char_format.setFont(font)
            cursor.setCharFormat(char_format)

    def _set_font_size(self, size: int) -> None:
        """Set font size for selection.

        Args:
            size: The font size in points.
        """
        with FormattingContext(self.text_edit) as cursor:
            char_format = cursor.charFormat()
            font = char_format.font()
            font.setPointSize(size)
            char_format.setFont(font)
            cursor.setCharFormat(char_format)

    def _toggle_bold(self, checked: bool) -> None:
        """Toggle bold formatting.

        Args:
            checked: Whether bold should be on or off.
        """
        with FormattingContext(self.text_edit) as cursor:
            char_format = cursor.charFormat()
            weight = QFont.Weight.Bold if checked else QFont.Weight.Normal
            char_format.setFontWeight(weight)
            cursor.setCharFormat(char_format)

    def _toggle_italic(self, checked: bool) -> None:
        """Toggle italic formatting.

        Args:
            checked: Whether italic should be on or off.
        """
        with FormattingContext(self.text_edit) as cursor:
            char_format = cursor.charFormat()
            char_format.setFontItalic(checked)
            cursor.setCharFormat(char_format)

    def _toggle_underline(self, checked: bool) -> None:
        """Toggle underline formatting.

        Args:
            checked: Whether underline should be on or off.
        """
        with FormattingContext(self.text_edit) as cursor:
            char_format = cursor.charFormat()
            char_format.setFontUnderline(checked)
            cursor.setCharFormat(char_format)

    def _request_enhancement(self) -> None:
        """Request AI enhancement of the text.

        Emits a signal requesting default AI enhancement of the selected text.
        """
        self.enhancementRequested.emit()

    def _choose_color(self) -> None:
        """Open color picker dialog.

        Displays a color picker and applies the selected color to text.
        """
        color = QColorDialog.getColor(
            self.text_edit.textColor(), self, "Choose Text Color"
        )

        if color.isValid():
            with FormattingContext(self.text_edit) as cursor:
                char_format = cursor.charFormat()
                char_format.setForeground(color)
                cursor.setCharFormat(char_format)

    def _set_alignment(self, alignment: Qt.AlignmentFlag) -> None:
        """Set text alignment.

        Args:
            alignment: The alignment flag to apply.
        """
        with FormattingContext(self.text_edit) as cursor:
            block_format = cursor.blockFormat()
            block_format.setAlignment(alignment)
            cursor.setBlockFormat(block_format)

    def _update_toolbar_state(self) -> None:
        """Update toolbar state to match current selection.

        Updates all toolbar controls to reflect the formatting of the current text selection.
        """
        cursor = self.text_edit.textCursor()
        char_format = cursor.charFormat()
        font = char_format.font()

        # Update font size combo
        size_combo = self.row1.findChild(QComboBox)
        if size_combo and not isinstance(
            size_combo, QFontComboBox
        ):  # Make sure we don't get the font combo
            current_size = font.pointSize()
            size_index = size_combo.findData(current_size)
            if size_index >= 0:
                size_combo.setCurrentIndex(size_index)
            else:
                size_combo.setCurrentText(str(current_size))

        # Update font family combo
        font_combo = self.row1.findChild(QFontComboBox)
        if font_combo:
            font_combo.setCurrentFont(font)

        # Update format toggles in both rows
        for row in [self.row1, self.row2]:
            for action in row.actions():
                if not action.isCheckable():
                    continue

                checked = False
                if action.text() == "Bold":
                    checked = font.weight() == QFont.Weight.Bold
                elif action.text() == "Italic":
                    checked = font.italic()
                elif action.text() == "Underline":
                    checked = font.underline()
                elif action.text() in ["Left", "Center", "Right", "Justify"]:
                    block_format = cursor.blockFormat()
                    current_alignment = block_format.alignment()
                    alignment_map = {
                        "Left": Qt.AlignmentFlag.AlignLeft,
                        "Center": Qt.AlignmentFlag.AlignCenter,
                        "Right": Qt.AlignmentFlag.AlignRight,
                        "Justify": Qt.AlignmentFlag.AlignJustify,
                    }
                    if action.text() in alignment_map:
                        checked = current_alignment == alignment_map[action.text()]

                action.setChecked(checked)

    def undo(self) -> None:
        """Undo last formatting operation.

        Reverts the most recent formatting change from the undo stack.
        """
        if self._undo_stack:
            with FormattingContext(self.text_edit) as cursor:
                format_change = self._undo_stack.pop()
                format_change.revert(cursor)

    @contextmanager
    def batch_format(self) -> None:
        """Context manager for batched formatting operations.

        Groups multiple formatting operations into a single undo operation.

        Yields:
            None
        """
        self.text_edit.textCursor().beginEditBlock()
        try:
            yield
        finally:
            self.text_edit.textCursor().endEditBlock()
