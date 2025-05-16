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
    """Represents a single row in the text formatting toolbar."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setIconSize(QSize(16, 16))
        self.setMovable(False)


class FormatChange(Protocol):
    """Protocol for format change operations."""

    def apply(self, cursor: QTextCursor) -> None:
        """Apply the format change to the cursor."""
        ...

    def revert(self, cursor: QTextCursor) -> None:
        """Revert the format change."""
        ...


@dataclass
class TextStyle:
    """Represents a complete text style configuration."""

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
        """Convert style to QTextCharFormat."""
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
    """Registry for managing text styles."""

    def __init__(self) -> None:
        self._styles: Dict[str, TextStyle] = {}
        self._initialize_default_styles()

    def _initialize_default_styles(self) -> None:
        """Initialize default text styles."""
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
        """Get a style by name."""
        return self._styles.get(name, self._styles["body"])

    def register_style(self, name: str, style: TextStyle) -> None:
        """Register a new style."""
        self._styles[name] = style


class UndoableFormatChange:
    """Represents an undoable formatting operation."""

    def __init__(self, operation: Callable[[QTextCursor], Any]) -> None:
        self.operation = operation
        self.previous_format: Optional[QTextCharFormat] = None

    def apply(self, cursor: QTextCursor) -> None:
        """Apply the format change."""
        self.previous_format = cursor.charFormat()
        self.operation(cursor)

    def revert(self, cursor: QTextCursor) -> None:
        """Revert to previous format."""
        if self.previous_format:
            cursor.setCharFormat(self.previous_format)


class FormattingContext:
    """Context manager for formatting operations."""

    def __init__(self, text_edit: QTextEdit) -> None:
        self.text_edit = text_edit
        self.cursor = text_edit.textCursor()

    def __enter__(self) -> QTextCursor:
        self.cursor.beginEditBlock()
        return self.cursor

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.cursor.endEditBlock()
        if exc_type:
            logger.error(f"Error during formatting: {exc_val}")


class TextToolbar(QWidget):
    """Advanced toolbar for text formatting operations."""

    # Signals
    styleChanged = pyqtSignal(str)  # Style name
    formatChanged = pyqtSignal(QTextCharFormat)
    enhancementRequested = pyqtSignal()

    def __init__(
        self,
        text_edit: QTextEdit,
        parent: Optional[QWidget] = None,
        style_registry: Optional[StyleRegistry] = None,
    ) -> None:
        """Initialize the toolbar."""
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
        """Set up the toolbar UI in two rows."""
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
        """Add the style selection dropdown."""
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
        """Add font family selector."""
        font_combo = QFontComboBox(toolbar)
        font_combo.setMinimumWidth(150)
        font_combo.currentFontChanged.connect(self._set_font_family)
        toolbar.addWidget(font_combo)

    def _get_standard_font_sizes(self) -> list[int]:
        """Return a list of standard font sizes."""
        return [8, 9, 10, 11, 12, 14, 16, 18, 20, 22, 24, 26, 28, 36, 48, 72]

    def _handle_font_size_change(self, text: str) -> None:
        """Handle font size changes from the combo box."""
        try:
            size = int(text)
            if 4 <= size <= 100:  # Reasonable size limits
                self._set_font_size(size)
        except ValueError:
            pass

    def _add_font_size_controls(self, toolbar: QToolBar) -> None:
        """Add font size selector as a dropdown."""
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
        """Add basic formatting buttons."""
        formats = {
            "Bold": (self._toggle_bold, "Ctrl+B"),
            "Italic": (self._toggle_italic, "Ctrl+I"),
            "Underline": (self._toggle_underline, "Ctrl+U"),
        }

        for name, (slot, shortcut) in formats.items():
            self._add_formatting_action(toolbar, name, slot, True, shortcut)

    def _add_advanced_formatting(self, toolbar: QToolBar) -> None:
        """Add color picker and other advanced formatting options."""
        color_button = QToolButton(toolbar)
        color_button.setText("Text Color")
        color_button.clicked.connect(self._choose_color)
        toolbar.addWidget(color_button)

        bg_color_button = QToolButton(toolbar)
        bg_color_button.setText("Highlight")
        bg_color_button.clicked.connect(self._choose_background_color)
        toolbar.addWidget(bg_color_button)

        # Add AI enhancement button
        enhance_button = QToolButton(toolbar)
        enhance_button.setText("Enhance with AI")
        enhance_button.setToolTip("Use AI to enhance the text description")
        enhance_button.clicked.connect(self._request_enhancement)
        toolbar.addWidget(enhance_button)

    def _add_alignment_controls(self, toolbar: QToolBar) -> None:
        """Add text alignment controls."""
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
        """Open color picker dialog for background color."""
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
        """Add a formatting action to the toolbar."""
        action = QAction(text, toolbar)
        action.setCheckable(checkable)
        action.triggered.connect(slot)

        if shortcut:
            action.setShortcut(QKeySequence(shortcut))
            action.setShortcutContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)

        toolbar.addAction(action)
        return action

    def _connect_signals(self) -> None:
        """Connect to text edit signals."""
        self.text_edit.selectionChanged.connect(self._update_toolbar_state)
        self.text_edit.currentCharFormatChanged.connect(
            lambda fmt: self.formatChanged.emit(fmt)
        )

    def actions(self) -> list[QAction]:
        """Return all actions from both toolbar rows."""
        return self.row1.actions() + self.row2.actions()

    def _apply_style(self, style_name: str) -> None:
        """Apply a named style to the selection."""
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
        """Set font family for selection."""
        with FormattingContext(self.text_edit) as cursor:
            char_format = cursor.charFormat()
            char_format.setFont(font)
            cursor.setCharFormat(char_format)

    def _set_font_size(self, size: int) -> None:
        """Set font size for selection."""
        with FormattingContext(self.text_edit) as cursor:
            char_format = cursor.charFormat()
            font = char_format.font()
            font.setPointSize(size)
            char_format.setFont(font)
            cursor.setCharFormat(char_format)

    def _toggle_bold(self, checked: bool) -> None:
        """Toggle bold formatting."""
        with FormattingContext(self.text_edit) as cursor:
            char_format = cursor.charFormat()
            weight = QFont.Weight.Bold if checked else QFont.Weight.Normal
            char_format.setFontWeight(weight)
            cursor.setCharFormat(char_format)

    def _toggle_italic(self, checked: bool) -> None:
        """Toggle italic formatting."""
        with FormattingContext(self.text_edit) as cursor:
            char_format = cursor.charFormat()
            char_format.setFontItalic(checked)
            cursor.setCharFormat(char_format)

    def _toggle_underline(self, checked: bool) -> None:
        """Toggle underline formatting."""
        with FormattingContext(self.text_edit) as cursor:
            char_format = cursor.charFormat()
            char_format.setFontUnderline(checked)
            cursor.setCharFormat(char_format)

    def _request_enhancement(self) -> None:
        """Request AI enhancement of the text."""
        # Default to depth 1, or you could add a depth selector

        self.enhancementRequested.emit()

    def _choose_color(self) -> None:
        """Open color picker dialog."""
        color = QColorDialog.getColor(
            self.text_edit.textColor(), self, "Choose Text Color"
        )

        if color.isValid():
            with FormattingContext(self.text_edit) as cursor:
                char_format = cursor.charFormat()
                char_format.setForeground(color)
                cursor.setCharFormat(char_format)

    def _set_alignment(self, alignment: Qt.AlignmentFlag) -> None:
        """Set text alignment."""
        with FormattingContext(self.text_edit) as cursor:
            block_format = cursor.blockFormat()
            block_format.setAlignment(alignment)
            cursor.setBlockFormat(block_format)

    def _update_toolbar_state(self) -> None:
        """Update toolbar state to match current selection."""
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
        """Undo last formatting operation."""
        if self._undo_stack:
            with FormattingContext(self.text_edit) as cursor:
                format_change = self._undo_stack.pop()
                format_change.revert(cursor)

    @contextmanager
    def batch_format(self) -> None:
        """Context manager for batched formatting operations."""
        self.text_edit.textCursor().beginEditBlock()
        try:
            yield
        finally:
            self.text_edit.textCursor().endEditBlock()
