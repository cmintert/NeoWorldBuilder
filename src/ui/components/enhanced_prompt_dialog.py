from typing import Optional, List, Any

from PyQt6.QtCore import QTimer
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
    QPushButton,
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

        # Context depth
        depth_layout = QHBoxLayout()
        depth_layout.addWidget(QLabel("Context Depth:"))
        self.depth_spin = QSpinBox()
        self.depth_spin.setToolTip("Number of relationship hops to include as context")
        self.depth_spin.setFixedWidth(60)
        self.depth_spin.setMinimum(0)
        self.depth_spin.setMaximum(3)
        self.depth_spin.setValue(0)
        self.depth_spin.setToolTip("Number of relationship hops to include as context")
        depth_layout.addWidget(self.depth_spin)
        depth_layout.addStretch()
        layout.addLayout(depth_layout)

        # Custom instructions
        layout.addWidget(QLabel("Additional Instructions:"))
        self.instructions_edit = QTextEdit()
        self.instructions_edit.setPlaceholderText(
            "Enter any specific instructions here... {custom_instructions}"
        )
        self.instructions_edit.setMaximumHeight(100)
        layout.addWidget(self.instructions_edit)

        # Template Preview Section
        preview_group = QGroupBox("Template Preview")
        preview_layout = QVBoxLayout(preview_group)

        # Add refresh button and explanation
        preview_header = QHBoxLayout()
        preview_header.addWidget(QLabel("See what prompt will be sent to the AI:"))
        # refresh_button = QPushButton("Refresh Preview")
        # refresh_button.clicked.connect(self._update_template_preview)
        # preview_header.addWidget(refresh_button)
        preview_layout.addLayout(preview_header)

        # Template content preview
        self.template_preview = QTextEdit()
        self.template_preview.setReadOnly(True)
        self.template_preview.setMinimumHeight(200)
        preview_layout.addWidget(self.template_preview)

        layout.addWidget(preview_group)

        # Update preview when template selection changes
        self.template_combo.currentIndexChanged.connect(self._update_template_preview)
        self.depth_spin.valueChanged.connect(self._update_template_preview)

        # Buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        # Initialize preview
        QTimer.singleShot(100, self._update_template_preview)

    def _update_template_preview(self) -> None:
        """Update the template preview with the current node's data."""
        try:
            # Get selected template
            selected_template = self.get_selected_template()
            if not selected_template:
                self.template_preview.setText("No template selected")
                return

            # Find the controller
            parent = self
            while parent and not hasattr(parent, "controller"):
                parent = parent.parent()

            if not parent or not hasattr(parent, "controller"):
                # Fallback to just showing the raw template
                self.template_preview.setText(selected_template.template)
                return

            controller = parent.controller

            # Get current node data
            node_name = controller.ui.name_input.text().strip()
            if not node_name:
                self.template_preview.setText(
                    "No node selected. Please enter a node name first."
                )
                return

            # Get the node data from the UI
            node_data = controller._get_current_node_data()

            # Get the context based on depth
            context = ""
            if self.depth_spin.value() > 0:
                context = controller._get_node_context(
                    node_name, self.depth_spin.value()
                )

            # Prepare variables
            variables = controller.prompt_template_service.prepare_context_variables(
                node_data=node_data,
                context=context,
                custom_instructions=self.instructions_edit.toPlainText(),
            )

            # Format template with variables
            try:
                formatted_template = selected_template.format(variables)
                self.template_preview.setHtml(
                    f"<h3>Template Preview</h3><hr><pre>{formatted_template}</pre>"
                )
            except Exception as e:
                self.template_preview.setText(
                    f"Error formatting template: {str(e)}\n\nRaw template:\n{selected_template.template}"
                )

        except Exception as e:
            self.template_preview.setText(f"Error generating preview: {str(e)}")

    def get_selected_template(self) -> Any:
        """Get the currently selected prompt template.

        Returns:
            Any: The selected template object from the combo box.
        """
        return self.template_combo.currentData()

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
