from typing import Dict, List, Tuple, Any, Set, Union, Optional

from PyQt6.QtCore import Qt, pyqtSlot, QTimer
from PyQt6.QtWidgets import (
    QTabWidget,
    QWidget,
    QCheckBox,
    QHBoxLayout,
    QGroupBox,
    QRadioButton,
    QTableWidgetItem,
    QHeaderView,
    QTableWidget,
    QScrollArea,
    QListWidget,
    QInputDialog,
    QButtonGroup,
    QDialog,
    QVBoxLayout,
    QFormLayout,
    QLineEdit,
    QPushButton,
    QMessageBox,
    QLabel,
    QProgressBar,
    QDialogButtonBox,
)
from neo4j.exceptions import AuthError, ServiceUnavailable
from structlog import get_logger

from config.config import ConfigNode
from utils.app_shutdown import perform_application_exit
from utils.crypto import SecurityUtility

logger = get_logger(__name__)


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
        layout.addStretch()

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
            group_box.setFixedHeight(60)
            layout.addWidget(group_box)
        layout.addStretch()

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
        self.test_succeeded = False

        self.setup_ui()
        self.load_existing_settings()

    def setup_ui(self):
        self.setWindowTitle("Database Connection Settings")
        self.setModal(True)
        self.setMinimumWidth(400)

        layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        # Create input fields
        self.uri_input = QLineEdit()
        self.uri_input.setPlaceholderText("bolt://localhost:7687")

        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("neo4j")

        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)

        # Add fields to form
        form_layout.addRow("Database URI:", self.uri_input)
        form_layout.addRow("Username:", self.username_input)
        form_layout.addRow("Password:", self.password_input)

        layout.addLayout(form_layout)

        # Add status indicator
        self.status_label = QLabel()
        self.status_label.setVisible(False)
        layout.addWidget(self.status_label)

        # Add progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # Create button box
        button_box = QDialogButtonBox()
        self.test_button = QPushButton("Test Connection")
        self.test_button.clicked.connect(self.test_connection)
        button_box.addButton(self.test_button, QDialogButtonBox.ButtonRole.ActionRole)

        button_box.addButton(QDialogButtonBox.StandardButton.Save)
        button_box.addButton(QDialogButtonBox.StandardButton.Cancel)

        button_box.accepted.connect(self.save_settings)
        button_box.rejected.connect(self.reject)

        layout.addWidget(button_box)

    def load_existing_settings(self):
        """
        Load existing connection settings if available.
        Uses Config class methods to ensure proper environment handling.
        """
        try:
            # Get values through Config class to respect environment settings
            uri = self.config.get("URI", "")
            username = self.config.get("USERNAME", "")

            # Set the values in the UI
            self.uri_input.setText(uri)
            self.username_input.setText(username)
            self.password_input.setPlaceholderText("New password")

        except Exception as e:
            self.show_error("Failed to load existing settings", str(e))

    def show_status(self, message, is_error=False):
        """Display status message with appropriate styling."""
        self.status_label.setText(message)
        color = "#FF0000" if is_error else "#008000"
        self.status_label.setStyleSheet(f"color: {color};")
        self.status_label.setVisible(True)

    @pyqtSlot()
    def test_connection(self):
        """Test the database connection with provided credentials."""
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # Indeterminate progress
        self.test_button.setEnabled(False)
        self.status_label.setVisible(False)

        uri = self.uri_input.text().strip()
        username = self.username_input.text().strip()
        password = self.password_input.text()

        if not all([uri, username, password]):
            self.show_status("Please fill in all fields", True)
            self.progress_bar.setVisible(False)
            self.test_button.setEnabled(True)
            return

        try:
            # Create temporary model to test connection
            from core.neo4jmodel import Neo4jModel

            # Create a simple test config with just the necessary attributes
            test_config = ConfigNode(
                {
                    "URI": uri,
                    "USERNAME": username,
                    "PASSWORD": password,
                    "KEY": self.config.KEY,  # Need this for encryption
                }
            )

            test_model = Neo4jModel(uri, username, password, test_config)

            try:
                test_model._driver.verify_connectivity()
                self.show_status("Connection successful!")
                self.test_succeeded = True

            except AuthError:
                self.show_status("Invalid username or password", True)
            except ServiceUnavailable:
                self.show_status("Database server not accessible", True)
            except Exception as e:
                self.show_status(f"Connection failed: {str(e)}", True)
            finally:
                test_model.close()

        except Exception as e:
            self.show_status(f"Failed to establish connection: {str(e)}", True)

        self.progress_bar.setVisible(False)
        self.test_button.setEnabled(True)

    def save_settings(self):
        """
        Save connection settings using the Config class to ensure proper handling
        across different environments.
        """
        if not self.test_succeeded:
            response = QMessageBox.warning(
                self,
                "Untested Connection",
                "Connection hasn't been successfully tested. Save anyway?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if response == QMessageBox.StandardButton.No:
                return

        try:
            # Encrypt password using existing security utility
            security_utility = SecurityUtility(self.config.KEY)
            encrypted_password = security_utility.encrypt(self.password_input.text())

            # Save each setting individually through the Config class
            # This ensures proper environment handling and validation
            self.config.set_value("URI", self.uri_input.text().strip(), persist=False)
            self.config.set_value(
                "USERNAME", self.username_input.text().strip(), persist=False
            )
            self.config.set_value("PASSWORD", encrypted_password, persist=False)

            # Save all changes at once to minimize file operations
            self.config.save_changes()

            # Show success message with restart prompt
            response = QMessageBox.information(
                self,
                "Success",
                "Database settings have been saved. The application needs to restart "
                "for changes to take effect. Would you like to quit the application now?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )

            if response == QMessageBox.StandardButton.Yes:
                logger.info(
                    "User requested application restart after saving database settings"
                )
                # Accept dialog first
                self.accept()
                # Schedule application exit
                QTimer.singleShot(0, lambda: perform_application_exit())
            else:
                self.accept()

        except Exception as e:
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to save settings: {str(e)}\n\n"
                "Please check application permissions and try again.",
            )


class ValueEditorDialog(QDialog):
    """Dialog for editing a list of predefined values."""

    def __init__(self, current_values: List[str], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Property Values")
        self.setModal(True)
        self.values = current_values.copy()
        self.init_ui()

    def init_ui(self) -> None:
        """Initialize the dialog UI."""
        layout = QVBoxLayout(self)

        # Create list widget for values
        self.list_widget = QListWidget()
        for value in self.values:
            self.list_widget.addItem(value)
        layout.addWidget(self.list_widget)

        # Buttons for manipulating values
        button_layout = QHBoxLayout()

        add_button = QPushButton("Add Value")
        add_button.clicked.connect(self.add_value)
        button_layout.addWidget(add_button)

        edit_button = QPushButton("Edit Selected")
        edit_button.clicked.connect(self.edit_value)
        button_layout.addWidget(edit_button)

        remove_button = QPushButton("Remove Selected")
        remove_button.clicked.connect(self.remove_value)
        button_layout.addWidget(remove_button)

        layout.addLayout(button_layout)

        # Dialog buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def add_value(self) -> None:
        """Add a new value to the list."""
        text, ok = QInputDialog.getText(self, "Add Value", "Enter new value:")
        if ok and text:
            self.list_widget.addItem(text)

    def edit_value(self) -> None:
        """Edit the currently selected value."""
        if current := self.list_widget.currentItem():
            text, ok = QInputDialog.getText(
                self, "Edit Value", "Edit value:", text=current.text()
            )
            if ok and text:
                current.setText(text)

    def remove_value(self) -> None:
        """Remove the currently selected value."""
        if current := self.list_widget.currentRow():
            self.list_widget.takeItem(current)

    def get_values(self) -> List[str]:
        """Get the current list of values."""
        return [
            self.list_widget.item(i).text() for i in range(self.list_widget.count())
        ]


class ProjectSettingsDialog(QDialog):
    """
    Dialog for managing application styles and themes.
    Allows users to choose and preview different styles in real-time.
    """

    def __init__(self, config, app_instance, parent=None):
        super().__init__(parent)

        self.config = config
        self.app_instance = app_instance
        self._project_name_input = QLineEdit()

        # Get the controller from app_instance.components
        if not hasattr(app_instance, "components") or not app_instance.components:
            raise RuntimeError("Application components not initialized")

        self.controller = app_instance.components.controller

        self.setWindowTitle("Project Settings")
        self.setModal(True)
        self._setup_ui()

    def _setup_ui(self):
        self.setWindowTitle("Project Settings")
        self.setModal(True)
        self.setMinimumWidth(300)

        layout = QVBoxLayout(self)

        form_layout = QFormLayout()
        warning = QLabel("WARNING: Changing the project name will require a restart")

        # Create input fields
        self._project_name_input.setPlaceholderText(
            f"Current: {self.config.user.PROJECT}"
        )

        # Add fields to form
        form_layout.addRow("Project Name:", self._project_name_input)

        # Add a save button
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.save_project_name)
        button_box.rejected.connect(self.reject)

        layout.addWidget(warning)
        layout.addLayout(form_layout)
        layout.addWidget(button_box)

    def save_project_name(self):
        project_name = self._project_name_input.text().strip()
        if not project_name:
            QMessageBox.critical(self, "Error", "Project name cannot be empty")
            return

        try:
            self.config.set_value("user.PROJECT", project_name)
            QMessageBox.information(
                self,
                "Success",
                "Project name updated successfully, application will shutdown, please restart",
            )
            self.accept()
            # QTimer.singleShot(0, lambda: perform_application_exit(self))

        except Exception as e:
            QMessageBox.critical(
                self, "Error", f"Failed to save project name: {str(e)}"
            )
