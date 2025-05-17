from typing import Optional, List, Any

from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QComboBox,
    QLabel,
    QTextEdit,
    QSpinBox,
    QDialogButtonBox,
    QRadioButton,
    QButtonGroup,
    QGroupBox,
)


class EnhancedPromptDialog(QDialog):
    """A dialog for configuring enhanced LLM prompting options.

    This dialog allows users to configure various parameters for enhanced LLM prompting,
    including template selection, enhancement focus, context depth, and custom instructions.

    Attributes:
        template_combo (QComboBox): Combo box for selecting prompt templates.
        focus_buttons (QButtonGroup): Group of radio buttons for enhancement focus options.
        depth_spin (QSpinBox): Spin box for selecting context depth.
        instructions_edit (QTextEdit): Text area for additional instructions.
        templates (List[Any]): List of available prompt templates.
    """

    template_combo: QComboBox
    focus_buttons: QButtonGroup
    depth_spin: QSpinBox
    instructions_edit: QTextEdit
    templates: List[Any]

    def __init__(
        self, parent: Optional[QDialog] = None, templates: Optional[List[Any]] = None
    ) -> None:
        """Initialize the EnhancedPromptDialog.

        Args:
            parent: Optional parent widget. Defaults to None.
            templates: Optional list of prompt templates. Defaults to None.
        """
        super().__init__(parent)
        self.templates = templates or []
        self.setWindowTitle("Enhance Description")
        self.setMinimumWidth(500)
        self.setMinimumHeight(400)

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the user interface components.

        Creates and arranges all UI elements including:
        - Template selection combo box
        - Enhancement focus radio buttons
        - Context depth spinner
        - Custom instructions text area
        - OK/Cancel buttons
        """
        layout = QVBoxLayout(self)

        # Template selection
        template_layout = QHBoxLayout()
        template_layout.addWidget(QLabel("Template:"))
        self.template_combo = QComboBox()
        for template in self.templates:
            self.template_combo.addItem(template.name, template)
        template_layout.addWidget(self.template_combo)
        layout.addLayout(template_layout)

        # Enhancement focus
        focus_group = QGroupBox("Enhancement Focus")
        focus_layout = QVBoxLayout(focus_group)
        self.focus_buttons = QButtonGroup(self)

        focus_options = [
            ("general", "General Enhancement", "Improve overall quality"),
            ("details", "Add Details", "Expand with additional information"),
            ("style", "Improve Style", "Refine the writing style"),
            ("consistency", "Fix Inconsistencies", "Align with connected nodes"),
        ]

        for focus_id, text, tooltip in focus_options:
            radio = QRadioButton(text)
            radio.setToolTip(tooltip)
            radio.setProperty("focus_id", focus_id)
            self.focus_buttons.addButton(radio)
            focus_layout.addWidget(radio)

        # Select the first option by default
        self.focus_buttons.buttons()[0].setChecked(True)
        layout.addWidget(focus_group)

        # Context depth
        depth_layout = QHBoxLayout()
        depth_layout.addWidget(QLabel("Context Depth:"))
        self.depth_spin = QSpinBox()
        self.depth_spin.setToolTip("Number of relationship hops to include as context")
        self.depth_spin.setFixedWidth(60)
        self.depth_spin.setMinimum(0)
        self.depth_spin.setMaximum(3)
        self.depth_spin.setValue(1)
        self.depth_spin.setToolTip("Number of relationship hops to include as context")
        depth_layout.addWidget(self.depth_spin)
        depth_layout.addStretch()
        layout.addLayout(depth_layout)

        # Custom instructions
        layout.addWidget(QLabel("Additional Instructions:"))
        self.instructions_edit = QTextEdit()
        self.instructions_edit.setPlaceholderText(
            "Enter any specific instructions here..."
        )
        self.instructions_edit.setMaximumHeight(100)
        layout.addWidget(self.instructions_edit)

        # Buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def get_selected_template(self) -> Any:
        """Get the currently selected prompt template.

        Returns:
            Any: The selected template object from the combo box.
        """
        return self.template_combo.currentData()

    def get_focus_type(self) -> str:
        """Get the selected enhancement focus type.

        Returns:
            str: The focus type ID ('general', 'details', 'style', or 'consistency').
                Returns 'general' if no button is selected.
        """
        checked_button = self.focus_buttons.checkedButton()
        return checked_button.property("focus_id") if checked_button else "general"

    def get_context_depth(self) -> int:
        """Get the selected context depth value.

        Returns:
            int: The number of relationship hops to include as context (0-3).
        """
        return self.depth_spin.value()

    def get_custom_instructions(self) -> str:
        """Get the user-provided custom instructions.

        Returns:
            str: The text content of the custom instructions field.
        """
        return self.instructions_edit.toPlainText()
