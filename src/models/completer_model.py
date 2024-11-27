from dataclasses import dataclass
from typing import Protocol

from PyQt6.QtCore import Qt, QStringListModel
from PyQt6.QtWidgets import QLineEdit, QTableWidget, QCompleter


@dataclass
class CompleterInput:
    """Input widget with completion settings"""

    widget: QLineEdit
    model: QStringListModel
    case_sensitivity: Qt.CaseSensitivity = Qt.CaseSensitivity.CaseInsensitive
    filter_mode: Qt.MatchFlag = Qt.MatchFlag.MatchContains


class AutoCompletionUIHandler(Protocol):
    """Interface for UI operations needed by AutoCompletionService"""

    def create_completer(self, input: CompleterInput) -> QCompleter:
        """Create a configured completer"""
        ...

    def setup_target_cell_widget(
        self,
        table: QTableWidget,
        row: int,
        column: int,
        text: str,
    ) -> QLineEdit:
        """Create and setup a line edit widget for table cell"""
        ...
