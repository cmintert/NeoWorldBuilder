import json
from typing import Dict, List, Tuple, Any

from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QTabWidget,
    QDialogButtonBox,
    QWidget,
    QCheckBox,
    QLabel,
    QHBoxLayout,
    QGroupBox,
    QLineEdit,
    QPushButton,
    QMessageBox,
)

from ui.utility_controller import SecurityUtility


class SuggestionDialog(QDialog):
    def __init__(self, suggestions: Dict[str, Any], parent: QWidget = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Suggested Node Information")
        self.setModal(True)
        self.suggestions = suggestions
        self.selected_suggestions: Dict[str, Any] = {
            "tags": [],
            "properties": {},
            "relationships": [],
        }
        self.init_ui()

    def init_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Tabs for Tags, Properties, Relationships
        self.tabs = QTabWidget()
        self.tabs.addTab(self._create_tags_tab(), "Tags")
        self.tabs.addTab(self._create_properties_tab(), "Properties")
        self.tabs.addTab(self._create_relationships_tab(), "Relationships")

        # Action buttons
        button_box = button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)

        layout.addWidget(self.tabs)
        layout.addWidget(button_box)

    def _create_tags_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        self.tags_checkboxes: List[Tuple[QCheckBox, str]] = []
        for tag, confidence in self.suggestions.get("tags", []):
            checkbox = QCheckBox(f"{tag}")
            confidence_label = QLabel(f"Confidence: {confidence:.2f}%")
            h_layout = QHBoxLayout()
            h_layout.addWidget(checkbox)
            h_layout.addWidget(confidence_label)
            self.tags_checkboxes.append((checkbox, tag))
            layout.addLayout(h_layout)

        return widget

    def _create_properties_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        self.properties_checkboxes: List[Tuple[QCheckBox, str, QLineEdit]] = []
        for key, values in self.suggestions.get("properties", {}).items():
            group_box = QGroupBox(f"Property: {key}")
            v_layout = QVBoxLayout()
            for value, confidence in values:
                checkbox = QCheckBox("Value:")
                value_edit = QLineEdit(str(value))
                confidence_label = QLabel(f"Confidence: {confidence:.2f}%")
                h_layout = QHBoxLayout()
                h_layout.addWidget(checkbox)
                h_layout.addWidget(value_edit)
                h_layout.addWidget(confidence_label)
                v_layout.addLayout(h_layout)
                # Store the QLineEdit widget instead of its value
                self.properties_checkboxes.append((checkbox, key, value_edit))
            group_box.setLayout(v_layout)
            layout.addWidget(group_box)

        return widget

    def _create_relationships_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        self.relationships_checkboxes: List[
            Tuple[QCheckBox, str, str, str, Dict[str, Any]]
        ] = []
        for rel_type, target, direction, props, confidence in self.suggestions.get(
            "relationships", []
        ):
            checkbox = QCheckBox(f"{direction} {rel_type} -> {target}")
            confidence_label = QLabel(f"Confidence: {confidence:.2f}%")
            h_layout = QHBoxLayout()
            h_layout.addWidget(checkbox)
            h_layout.addWidget(confidence_label)
            self.relationships_checkboxes.append(
                (checkbox, rel_type, target, direction, props)
            )
            layout.addLayout(h_layout)

        return widget

    def accept(self) -> None:
        # Collect selected tags
        for checkbox, tag in self.tags_checkboxes:
            if checkbox.isChecked():
                self.selected_suggestions["tags"].append(tag)

        # Collect selected properties
        for checkbox, key, value_edit in self.properties_checkboxes:
            if checkbox.isChecked():
                # Get the current text from the QLineEdit when accepting
                self.selected_suggestions["properties"][key] = value_edit.text()

        # Collect selected relationships
        for (
            checkbox,
            rel_type,
            target,
            direction,
            props,
        ) in self.relationships_checkboxes:
            if checkbox.isChecked():
                self.selected_suggestions["relationships"].append(
                    (rel_type, target, direction, props)
                )

        super().accept()


class ConnectionSettingsDialog(QDialog):
    def __init__(self, config, app_instance, parent=None):
        super().__init__(parent)

        self.config = config
        self.app_instance = app_instance

        self.setWindowTitle("Manage Connection Settings")
        self.layout = QVBoxLayout()

        self.uri_label = QLabel("URI:", self)
        self.uri_input = QLineEdit(config.URI, self)
        self.uri_label.setBuddy(self.uri_input)
        self.layout.addWidget(self.uri_label)
        self.layout.addWidget(self.uri_input)

        self.username_label = QLabel("Username:", self)
        self.username_input = QLineEdit(config.USERNAME, self)
        self.username_label.setBuddy(self.username_input)
        self.layout.addWidget(self.username_label)
        self.layout.addWidget(self.username_input)

        self.password_label = QLabel("Password:", self)
        self.password_input = QLineEdit(config.PASSWORD, self)
        self.password_label.setBuddy(self.password_input)
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.layout.addWidget(self.password_label)
        self.layout.addWidget(self.password_input)

        self.test_button = QPushButton("Establish Connection", self)
        self.test_button.setObjectName("establish_connect_button")

        self.save_button = QPushButton("Save", self)
        self.save_button.setObjectName("save_button")

        self.layout.addWidget(self.test_button)
        self.layout.addWidget(self.save_button)
        self.setLayout(self.layout)

        self.test_button.clicked.connect(self.establish_connection)
        self.save_button.clicked.connect(self.save_settings)

    def establish_connection(self):
        # Logic to test database connection
        try:
            # Attempt to initialize the database connection using the main application instance
            self.app_instance._initialize_database(self.config)
            QMessageBox.information(self, "Success", "Connection successful.")
        except RuntimeError as e:
            QMessageBox.critical(
                self, "Error", f"Failed to connect to the database: {e}"
            )

    def save_settings(self):
        # Retrieve the input values
        uri = self.uri_input.text()
        username = self.username_input.text()
        password = self.password_input.text()

        # Encrypt the password
        encryption_key = self.config.KEY
        security_utility = SecurityUtility(encryption_key)
        encrypted_password = security_utility.encrypt(password)

        # Prepare the new settings dictionary
        new_settings = {
            "URI": uri,
            "USERNAME": username,
            "PASSWORD": encrypted_password,
        }

        # Load existing settings from the JSON file
        try:
            with open("src/config/database.json", "r") as config_file:
                existing_settings = json.load(config_file)
        except FileNotFoundError:
            existing_settings = {}

        # Update the existing settings with the new settings
        existing_settings |= new_settings

        # Save the updated settings back to the JSON file
        with open("src/config/database.json", "w") as config_file:
            json.dump(existing_settings, config_file, indent=4)

        QMessageBox.information(self, "Success", "Settings saved successfully.")
