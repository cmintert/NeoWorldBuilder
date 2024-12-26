import json
from typing import Tuple

from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QComboBox,
    QPushButton,
    QDialogButtonBox,
    QTableWidget,
    QTableWidgetItem,
    QWidget,
)


class QuickRelationDialog(QDialog):
    """Dialog for quickly creating a relationship from selected text."""

    def __init__(self, selected_text: str, parent=None):
        super().__init__(parent)
        self.selected_text = selected_text
        self.properties = {}
        self.setWindowTitle("Create Relationship")
        self.setModal(True)
        self.setup_ui()

    def setup_ui(self) -> None:
        """Initialize the dialog's UI components."""
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # Relationship Section

        relationship_layout = QHBoxLayout()

        # Target node (from selected text)
        target_layout = QHBoxLayout()
        target_label = QLabel("Target Node:")
        self.target_input = QLineEdit(self.selected_text)
        target_layout.addWidget(target_label)
        target_layout.addWidget(self.target_input)
        relationship_layout.addLayout(target_layout)

        # Relationship type
        rel_layout = QHBoxLayout()
        rel_label = QLabel("Relationship:")
        self.rel_type = QComboBox()
        self.rel_type.setEditable(True)
        # Add common relationship types
        self.rel_type.addItems(["HAS", "CONTAINS", "RELATES_TO", "REFERENCES"])
        rel_layout.addWidget(rel_label)
        rel_layout.addWidget(self.rel_type)
        relationship_layout.addLayout(rel_layout)

        # Direction
        dir_layout = QHBoxLayout()
        dir_label = QLabel("Direction:")
        self.direction = QComboBox()
        self.direction.addItems([">", "<"])
        dir_layout.addWidget(dir_label)
        dir_layout.addWidget(self.direction)
        relationship_layout.addLayout(dir_layout)

        layout.addLayout(relationship_layout)

        # Properties section
        props_group = self._create_properties_section()
        layout.addWidget(props_group)

        # Buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def _create_properties_section(self) -> QWidget:
        """Create the properties editing section."""
        # Create properties table
        self.props_table = QTableWidget(0, 3)  # Initially empty, 3 columns
        self.props_table.setHorizontalHeaderLabels(["Key", "Value", ""])
        self.props_table.horizontalHeader().setStretchLastSection(True)

        # Add property button
        add_button = QPushButton("Add Property")
        add_button.clicked.connect(self._add_property_row)

        # Layout
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.addWidget(add_button)
        layout.addWidget(self.props_table)

        return container

    def _add_property_row(self) -> None:
        """Add a new row to the properties table."""
        row = self.props_table.rowCount()
        self.props_table.insertRow(row)

        self.props_table.setRowHeight(row, 25)

        # Delete button
        delete_button = QPushButton("-")
        delete_button.setFixedWidth(25)
        delete_button.clicked.connect(lambda: self.props_table.removeRow(row))
        self.props_table.setCellWidget(row, 2, delete_button)

        # Key and value cells
        self.props_table.setItem(row, 0, QTableWidgetItem(""))
        self.props_table.setItem(row, 1, QTableWidgetItem(""))
        self.props_table.setCellWidget(row, 2, delete_button)

        # Set column 2 to fixed width
        self.props_table.setColumnWidth(2, 25)

    def get_values(self) -> Tuple[str, str, str, str]:
        """Get the values from the dialog.

        Returns:
            Tuple containing (relationship type, target node, direction, properties_json)
        """
        # Collect properties from table
        properties = {}
        for row in range(self.props_table.rowCount()):
            key_item = self.props_table.item(row, 0)
            value_item = self.props_table.item(row, 1)
            if key_item and value_item and key_item.text().strip():
                properties[key_item.text().strip()] = value_item.text().strip()

        return (
            self.rel_type.currentText().strip().upper(),
            self.target_input.text().strip(),
            self.direction.currentText(),
            json.dumps(properties),
        )
