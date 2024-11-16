import logging

from PyQt6.QtCore import QObject, pyqtSlot
from PyQt6.QtWidgets import QMessageBox


class EventHandler(QObject):
    """
    Controller class to handle various event handlers.
    """

    def __init__(self, ui):
        """
        Initialize the EventHandler with the UI.

        Args:
            ui (WorldBuildingUI): The UI instance.
        """
        super().__init__()
        self.ui = ui

    @pyqtSlot(list)
    def _handle_node_data(self, data: list):
        """
        Handle node data fetched by the worker.

        Args:
            data (list): The fetched node data.
        """
        logging.debug(f"Handling node data: {data}")
        if not data:
            return  # No need to notify the user

        try:
            record = data[0]  # Extract the first record
            self._populate_node_fields(record)
            self.original_node_data = self._collect_node_data()
        except Exception as e:
            self.handle_error(f"Error populating node fields: {str(e)}")

    def update_unsaved_changes_indicator(self):
        if self.is_node_changed():
            self.ui.save_button.setStyleSheet("background-color: #83A00E;")
        else:
            self.ui.save_button.setStyleSheet("background-color: #d3d3d3;")

    def _handle_delete_success(self, _):
        """
        Handle successful node deletion.

        Args:
            _: The result of the delete operation.
        """
        QMessageBox.information(self.ui, "Success", "Node deleted successfully")
        self._load_default_state()
