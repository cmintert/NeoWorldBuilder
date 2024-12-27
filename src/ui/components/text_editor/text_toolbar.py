from typing import Optional, Callable

from PyQt6.QtGui import QFont, QAction
from PyQt6.QtWidgets import QToolBar, QWidget, QTextEdit


class TextToolbar(QToolBar):
    """A toolbar for text formatting operations."""

    def __init__(self, text_edit: QTextEdit, parent: Optional[QWidget] = None) -> None:
        """
        Initialize the formatting toolbar.

        Args:
            text_edit: The QTextEdit widget this toolbar will format
            parent: Optional parent widget
        """
        super().__init__("Formatting", parent)
        self.text_edit = text_edit
        self.setObjectName("formattingToolbar")
        self.setFixedHeight(24)

        self._setup_actions()

    def _setup_actions(self) -> None:
        """Setup all formatting actions with their shortcuts."""
        self._add_formatting_action(
            "H1", lambda: self._set_heading(1), shortcut="Ctrl+1"
        )
        self._add_formatting_action(
            "H2", lambda: self._set_heading(2), shortcut="Ctrl+2"
        )
        self._add_formatting_action(
            "H3", lambda: self._set_heading(3), shortcut="Ctrl+3"
        )
        self._add_formatting_action("Body", self._set_body, shortcut="Ctrl+0")
        self._add_formatting_action(
            "Bold", self._toggle_bold, checkable=True, shortcut="Ctrl+B"
        )
        self._add_formatting_action(
            "Italic", self._toggle_italic, checkable=True, shortcut="Ctrl+I"
        )
        self._add_formatting_action(
            "Underline", self._toggle_underline, checkable=True, shortcut="Ctrl+U"
        )

    def _add_formatting_action(
        self,
        text: str,
        slot: Callable,
        checkable: bool = False,
        shortcut: Optional[str] = None,
    ) -> None:
        """
        Add a formatting action to the toolbar.

        Args:
            text: The text for the action
            slot: The function to call when triggered
            checkable: Whether the action can be toggled
            shortcut: Optional keyboard shortcut
        """
        action = QAction(text, self)
        action.setCheckable(checkable)
        action.triggered.connect(slot)

        if shortcut:
            action.setShortcut(shortcut)
            action.setShortcutVisibleInContextMenu(True)

        self.addAction(action)
        if self.parent():
            self.parent().addAction(action)

    def _set_heading(self, level: int) -> None:
        """
        Set the selected text to the specified heading level.

        Args:
            level: The heading level (1, 2, or 3)
        """
        cursor = self.text_edit.textCursor()
        cursor.beginEditBlock()

        font = cursor.charFormat().font()
        if level == 1:
            font.setPointSize(16)
            font.setWeight(QFont.Weight.Bold)
        elif level == 2:
            font.setPointSize(14)
            font.setWeight(QFont.Weight.Medium)
        elif level == 3:
            font.setPointSize(12)
            font.setWeight(QFont.Weight.Normal)

        char_format = cursor.charFormat()
        char_format.setFont(font)
        cursor.setCharFormat(char_format)

        cursor.endEditBlock()

    def _set_body(self) -> None:
        """Reset the selected text to standard body text formatting."""
        cursor = self.text_edit.textCursor()
        cursor.beginEditBlock()

        standard_font = QFont()
        standard_font.setPointSize(12)
        standard_font.setWeight(QFont.Weight.Normal)

        char_format = cursor.charFormat()
        char_format.setFont(standard_font)
        char_format.setFontItalic(False)
        char_format.setFontUnderline(False)
        cursor.setCharFormat(char_format)

        cursor.endEditBlock()

    def _toggle_bold(self) -> None:
        """Toggle bold formatting for the selected text."""
        cursor = self.text_edit.textCursor()
        cursor.beginEditBlock()

        char_format = cursor.charFormat()
        new_weight = (
            QFont.Weight.Bold
            if char_format.fontWeight() != QFont.Weight.Bold
            else QFont.Weight.Normal
        )
        char_format.setFontWeight(new_weight)
        cursor.setCharFormat(char_format)

        cursor.endEditBlock()

    def _toggle_italic(self) -> None:
        """Toggle italic formatting for the selected text."""
        cursor = self.text_edit.textCursor()
        cursor.beginEditBlock()

        char_format = cursor.charFormat()
        char_format.setFontItalic(not char_format.fontItalic())
        cursor.setCharFormat(char_format)

        cursor.endEditBlock()

    def _toggle_underline(self) -> None:
        """Toggle underline formatting for the selected text."""
        cursor = self.text_edit.textCursor()
        cursor.beginEditBlock()

        char_format = cursor.charFormat()
        char_format.setFontUnderline(not char_format.fontUnderline())
        cursor.setCharFormat(char_format)

        cursor.endEditBlock()
