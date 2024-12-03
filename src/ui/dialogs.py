import json
from typing import Dict, List, Tuple, Any, Set

from PyQt6.QtCore import Qt
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
    QRadioButton,
    QTableWidgetItem,
    QHeaderView,
    QTableWidget,
)

from utils.crypto import SecurityUtility


class StyleSettingsDialog(QDialog):
    """
    Dialog for managing application styles and themes.
    Allows users to choose and preview different styles in real-time.
    """

    def __init__(self, config, app_instance, parent=None):
        super().__init__(parent)
        self.config = config
        self.app_instance = app_instance

        # Get the controller from app_instance.components
        if not hasattr(app_instance, "components") or not app_instance.components:
            raise RuntimeError("Application components not initialized")

        self.controller = app_instance.components.controller

        self.setWindowTitle("Style Settings")
        self.setModal(True)
        self.init_ui()

    def init_ui(self):
        """Initialize the dialog UI components."""
        layout = QVBoxLayout(self)

        # Create style selection group
        style_group = QGroupBox("Available Styles")
        style_layout = QVBoxLayout()

        # Get available styles from the registry
        self.style_buttons = {}
        current_style = self.controller.style_manager.current_style or "default"

        root_styles = {
            name: config
            for name, config in self.controller.style_manager.registry.styles.items()
            if not hasattr(config, "parent") or not config.parent
        }

        for (
            style_name,
            style_config,
        ) in root_styles.items():
            radio = QRadioButton(f"{style_name.title()} - {style_config.description}")
            radio.setObjectName(f"style_radio_{style_name}")
            radio.setChecked(style_name == current_style)
            radio.clicked.connect(
                lambda checked, name=style_name: self.on_style_selected(name)
            )
            self.style_buttons[style_name] = radio
            style_layout.addWidget(radio)

        style_group.setLayout(style_layout)
        layout.addWidget(style_group)

        # Add reload button
        reload_button = QPushButton("Reload Current Style")
        reload_button.setObjectName("reload_style_button")
        reload_button.clicked.connect(self.reload_current_style)
        layout.addWidget(reload_button)

        # Add dialog buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def on_style_selected(self, style_name: str):
        """
        Handle style selection and apply it immediately.

        Args:
            style_name: The name of the selected style
        """
        try:
            self.controller.change_application_style(style_name)
        except Exception as e:
            QMessageBox.critical(
                self, "Style Error", f"Failed to apply style '{style_name}': {str(e)}"
            )

    def reload_current_style(self):
        """Reload the currently selected style."""
        try:
            self.controller.refresh_styles()
            QMessageBox.information(self, "Success", "Style reloaded successfully")
        except Exception as e:
            QMessageBox.critical(
                self, "Reload Error", f"Failed to reload style: {str(e)}"
            )

    def accept(self):
        """Handle dialog acceptance."""
        super().accept()


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


class FastInjectDialog(QDialog):
    """Dialog for previewing Fast Inject template contents with selective application."""

    def __init__(self, template: Dict[str, Any], parent=None) -> None:
        super().__init__(parent)
        self.template = template
        self.setWindowTitle(f"Fast Inject Preview - {template['name']}")
        self.setModal(True)
        self.resize(600, 400)
        self.selected_sections: Set[str] = {
            "labels",
            "tags",
            "properties",
        }  # All selected by default
        self.init_ui()

    def init_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Template name and description
        name_label = QLabel(f"<b>{self.template['name']}</b>")
        name_label.setStyleSheet("font-size: 14px;")
        layout.addWidget(name_label)

        desc_label = QLabel(self.template["description"])
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("margin-bottom: 15px;")
        layout.addWidget(desc_label)

        # Labels section
        labels_group = QGroupBox("Labels")
        labels_layout = QVBoxLayout()
        self.labels_checkbox = QCheckBox("Include Labels")
        self.labels_checkbox.setChecked(True)
        labels_layout.addWidget(self.labels_checkbox)
        labels_text = ", ".join(self.template["content"]["labels"])
        labels_label = QLabel(labels_text)
        labels_label.setWordWrap(True)
        labels_layout.addWidget(labels_label)
        labels_group.setLayout(labels_layout)
        layout.addWidget(labels_group)

        # Tags section
        tags_group = QGroupBox("Tags")
        tags_layout = QVBoxLayout()
        self.tags_checkbox = QCheckBox("Include Tags")
        self.tags_checkbox.setChecked(True)
        tags_layout.addWidget(self.tags_checkbox)
        tags_text = ", ".join(self.template["content"]["tags"])
        tags_label = QLabel(tags_text)
        tags_label.setWordWrap(True)
        tags_layout.addWidget(tags_label)
        tags_group.setLayout(tags_layout)
        layout.addWidget(tags_group)

        # Properties section
        props_group = QGroupBox("Properties")
        props_layout = QVBoxLayout()
        self.properties_checkbox = QCheckBox("Include Properties")
        self.properties_checkbox.setChecked(True)
        props_layout.addWidget(self.properties_checkbox)

        props = self.template["content"]["properties"]
        props_table = QTableWidget(len(props), 2)
        props_table.setHorizontalHeaderLabels(["Property", "Default Value"])
        header = props_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)

        for i, (key, value) in enumerate(props.items()):
            props_table.setItem(i, 0, QTableWidgetItem(key))
            props_table.setItem(i, 1, QTableWidgetItem(str(value)))

        props_table.setMinimumHeight(200)
        props_layout.addWidget(props_table)
        props_group.setLayout(props_layout)
        layout.addWidget(props_group)

        # Add note about existing properties
        note_label = QLabel("<i>Note: Existing properties will not be overwritten</i>")
        note_label.setStyleSheet("color: gray;")
        layout.addWidget(note_label)

        # Connect checkbox signals
        self.labels_checkbox.stateChanged.connect(
            lambda state: self._update_selection("labels", state)
        )
        self.tags_checkbox.stateChanged.connect(
            lambda state: self._update_selection("tags", state)
        )
        self.properties_checkbox.stateChanged.connect(
            lambda state: self._update_selection("properties", state)
        )

        # Buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def _update_selection(self, section: str, state: int) -> None:
        """Update the selected_sections set based on checkbox state."""
        if state == Qt.CheckState.Checked.value:
            self.selected_sections.add(section)
        else:
            self.selected_sections.discard(section)
