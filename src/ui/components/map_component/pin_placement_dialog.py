from typing import Optional

from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QDialogButtonBox,
)


class PinPlacementDialog(QDialog):
    """Dialog for configuring a new map pin."""

    def __init__(self, x: int, y: int, parent=None, controller=None):
        """Initialize the dialog.

        Args:
            x: X coordinate of pin placement
            y: Y coordinate of pin placement
            parent: Parent widget
        """
        super().__init__(parent)
        self.x = x
        self.y = y
        self.controller = controller
        self.target_node: Optional[str] = None
        self.setup_ui()

    def setup_ui(self) -> None:
        """Initialize dialog UI components."""
        self.setWindowTitle("Place Pin")
        layout = QVBoxLayout(self)

        # Coordinates display
        coords_layout = QHBoxLayout()
        coords_layout.addWidget(QLabel(f"X: {self.x}"))
        coords_layout.addWidget(QLabel(f"Y: {self.y}"))
        layout.addLayout(coords_layout)

        # Target node input
        target_layout = QHBoxLayout()
        target_layout.addWidget(QLabel("Target Node:"))
        self.target_input = QLineEdit()
        if self.controller:
            self.controller.auto_completion_service.initialize_target_completer(
                self.target_input
            )
        target_layout.addWidget(self.target_input)
        layout.addLayout(target_layout)

        # Buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        self.setMinimumWidth(300)

    def get_target_node(self) -> Optional[str]:
        """Get the entered target node name."""
        return self.target_input.text().strip() or None

    # Add to ui/components/dialogs.py
