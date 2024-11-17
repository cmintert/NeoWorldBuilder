from PyQt6.QtWidgets import QMessageBox, QFileDialog, QTableWidgetItem
from config.config import Config

class UtilityController:
    """
    Controller class to handle utility methods.
    """

    def __init__(self, ui, config):
        """
        Initialize the UtilityController with the UI and configuration.

        Args:
            ui (WorldBuildingUI): The UI instance.
            config (Config): The configuration instance.
        """
        self.ui = ui
        self.config = config
        self.current_image_path = None

    def _parse_comma_separated(self, text: str):
        """
        Parse comma-separated input.

        Args:
            text (str): The comma-separated input text.

        Returns:
            list: The parsed list of strings.
        """
        return [item.strip() for item in text.split(",") if item.strip()]

    def validate_node_name(self, name: str):
        """
        Validate node name.

        Args:
            name (str): The node name to validate.

        Returns:
            bool: True if the node name is valid, False otherwise.
        """
        if not name:
            QMessageBox.warning(self.ui, "Warning", "Node name cannot be empty.")
            return False

        if len(name) > self.config.LIMITS_MAX_NODE_NAME_LENGTH:
            QMessageBox.warning(
                self.ui,
                "Warning",
                f"Node name cannot exceed {self.config.LIMITS_MAX_NODE_NAME_LENGTH} characters.",
            )
            return False

        return True

    def change_image(self):
        """
        Handle changing the image.
        """
        try:
            file_name, _ = QFileDialog.getOpenFileName(
                self.ui,
                "Select Image",
                "",
                "Image Files (*.png *.jpg *.bmp)",
            )
            if file_name:
                # Process image in the UI thread since it's UI-related
                self.current_image_path = file_name
                self.ui.set_image(file_name)
        except Exception as e:
            self.handle_error(f"Error changing image: {str(e)}")

    def delete_image(self):
        """
        Handle deleting the image.
        """
        self.current_image_path = None
        self.ui.set_image(None)

    def add_or_update_property(self, key, value):
        found = False
        for row in range(self.ui.properties_table.rowCount()):
            item_key = self.ui.properties_table.item(row, 0)
            if item_key and item_key.text() == key:
                self.ui.properties_table.item(row, 1).setText(str(value))
                found = True
                break
        if not found:
            row = self.ui.properties_table.rowCount()
            self.ui.properties_table.insertRow(row)
            self.ui.properties_table.setItem(row, 0, QTableWidgetItem(key))
            self.ui.properties_table.setItem(row, 1, QTableWidgetItem(str(value)))
            delete_button = self.ui.create_delete_button(self.ui.properties_table, row)
            self.ui.properties_table.setCellWidget(row, 2, delete_button)

    def handle_error(self, error_message: str):
        """
        Handle any errors.

        Args:
            error_message (str): The error message to display.
        """
        QMessageBox.critical(self.ui, "Error", error_message)
