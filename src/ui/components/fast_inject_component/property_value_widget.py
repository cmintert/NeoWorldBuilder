from typing import Union, List, Optional

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QCheckBox,
    QPushButton,
    QLineEdit,
)


class PropertyValueWidget(QWidget):
    """Widget for displaying property values either as line edit or checkboxes."""

    def __init__(self, value: Union[str, List[str]], parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(2)

        # Parse values
        if isinstance(value, str) and "," in value:
            self.values = [v.strip() for v in value.split(",")]
        elif isinstance(value, list):
            self.values = value
        else:
            self.values = [str(value)]

        # Create container for input widgets
        input_container = QWidget()
        input_layout = QHBoxLayout(input_container)
        input_layout.setContentsMargins(0, 0, 0, 0)

        # Create value input widget
        self.value_container = QWidget()
        self.value_layout = QHBoxLayout(self.value_container)
        self.value_layout.setContentsMargins(0, 0, 0, 0)
        self.value_layout.setSpacing(2)

        self.setup_input_widget(input_layout)
        self.layout.addWidget(input_container)

    def setup_input_widget(self, input_layout: QHBoxLayout) -> None:
        """Setup the appropriate input widget based on number of values."""
        if len(self.values) > 1:
            # Create checkboxes for multiple selection
            self.checkboxes = []
            for val in self.values:
                checkbox = QCheckBox(str(val))
                self.checkboxes.append(checkbox)
                self.value_layout.addWidget(checkbox)
                # Check first checkbox by default to provide a starting value
                if val == self.values[0]:
                    checkbox.setChecked(True)

            # Add edit button
            edit_button = QPushButton("✏️")
            edit_button.setMaximumWidth(30)
            edit_button.setMinimumWidth(30)
            edit_button.clicked.connect(self.edit_values)
            input_layout.addWidget(self.value_container)
            input_layout.addWidget(edit_button)
        else:
            # Use line edit for single value without any container border
            self.line_edit = QLineEdit(str(self.values[0]))
            # Remove any border from the line edit
            self.line_edit.setStyleSheet("border: none; background: transparent;")
            # Add directly to input layout to avoid extra container
            input_layout.addWidget(self.line_edit)

            # No need to use the value container for single values
            self.value_container.hide()

    def edit_values(self) -> None:
        """Open dialog to edit selectable values."""
        # Get user's new values through dialog
        new_values = self._get_new_values_from_dialog()
        if not new_values:
            return

        # Remember current selection before modifying UI
        current_values = self.get_value()
        if not isinstance(current_values, list):
            current_values = [current_values]

        # Update checkboxes
        self._update_checkboxes(new_values, current_values)

    def _get_new_values_from_dialog(self) -> Optional[List[str]]:
        """Show dialog to get new values from user."""
        from ui.components.dialogs import ValueEditorDialog

        if hasattr(self, "checkboxes"):
            current_values = [cb.text() for cb in self.checkboxes]
        else:
            current_values = []

        dialog = ValueEditorDialog(current_values, self)

        if dialog.exec():
            return dialog.get_values()
        return None

    def _update_checkboxes(
        self, new_values: List[str], previous_values: List[str]
    ) -> None:
        """Update checkboxes with new values.

        Args:
            new_values: List of new values for checkboxes
            previous_values: Previously selected values to preserve if possible
        """
        self._clear_existing_checkboxes()
        self._create_new_checkboxes(new_values)
        self._restore_checkbox_selections(previous_values)

    def _clear_existing_checkboxes(self) -> None:
        """Remove all existing checkboxes from the layout."""
        for checkbox in self.checkboxes:
            self.value_layout.removeWidget(checkbox)
            checkbox.deleteLater()
        self.checkboxes = []

    def _create_new_checkboxes(self, values: List[str]) -> None:
        """Create new checkboxes for the given values."""
        self.values = values
        self.checkboxes = []
        for val in values:
            checkbox = QCheckBox(str(val))
            self.checkboxes.append(checkbox)
            self.value_layout.addWidget(checkbox)

    def _restore_checkbox_selections(self, previous_values: List[str]) -> None:
        """Restore previous selections or select first checkbox.

        Args:
            previous_values: The previously selected values to restore
        """
        any_selected = False

        # Try to find and select checkboxes with previous values
        for checkbox in self.checkboxes:
            if checkbox.text() in previous_values:
                checkbox.setChecked(True)
                any_selected = True

        # Select first checkbox if no previous values were found
        if not any_selected and self.checkboxes:
            self.checkboxes[0].setChecked(True)

    def get_value(self) -> Union[str, List[str]]:
        """Get the currently selected/entered value(s)."""
        if hasattr(self, "checkboxes"):
            # Return a list of selected values
            selected = [cb.text() for cb in self.checkboxes if cb.isChecked()]
            return selected if selected else []  # Return empty list instead of None
        else:
            return self.line_edit.text()
