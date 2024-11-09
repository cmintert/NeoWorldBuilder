import json
import logging
from typing import Optional, Dict, Any, List

from PyQt6.QtCore import QObject, pyqtSlot
from PyQt6.QtWidgets import QMessageBox, QTableWidgetItem, QFileDialog

from ui.node_controller import NodeController
from ui.tree_controller import TreeController
from ui.search_controller import SearchController
from ui.suggestion_controller import SuggestionController
from ui.event_handler import EventHandler
from ui.utility_controller import UtilityController


class WorldBuildingController(QObject):
    """
    Controller class managing interaction between UI and Neo4j model using QThread workers
    """

    def __init__(self, ui: "WorldBuildingUI", model: "Neo4jModel", config: "Config"):
        """
        Initialize the controller with UI, model, and configuration.

        Args:
            ui (ui.main_window.WorldBuildingUI): The UI instance.
            model (Neo4jModel): The Neo4j model instance.
            config (config.config.Config): The configuration instance.
        """
        super().__init__()
        self.ui = ui
        self.model = model
        self.config = config
        self.current_image_path: Optional[str] = None
        self.original_node_data: Optional[Dict[str, Any]] = None
        self.ui.controller = self

        # Initialize sub-controllers
        self.node_controller = NodeController(model)
        self.tree_controller = TreeController(model, ui)
        self.search_controller = SearchController(model, ui)
        self.suggestion_controller = SuggestionController(ui, model)
        self.event_handler = EventHandler(ui)
        self.utility_controller = UtilityController(ui, config)

        # Connect signals
        self._connect_signals()

        # Initialize UI state
        self._load_default_state()

    def _connect_signals(self):
        """
        Connect all UI signals to handlers.
        """
        # Main buttons
        self.ui.save_button.clicked.connect(self.node_controller.save_node)
        self.ui.delete_button.clicked.connect(self.node_controller.delete_node)

        # Image handling
        self.ui.change_image_button.clicked.connect(self.utility_controller.change_image)
        self.ui.delete_image_button.clicked.connect(self.utility_controller.delete_image)

        # Name input and autocomplete
        self.ui.name_input.textChanged.connect(self.search_controller.debounce_name_input)
        self.ui.name_input.editingFinished.connect(self.node_controller.load_node_data)

        # Table buttons
        self.ui.add_rel_button.clicked.connect(self.ui.add_relationship_row)

        # Connect the suggest button
        self.ui.suggest_button.clicked.connect(self.suggestion_controller.show_suggestions_modal)

        # Check for unsaved changes
        self.ui.name_input.textChanged.connect(self.event_handler.update_unsaved_changes_indicator)
        self.ui.description_input.textChanged.connect(self.event_handler.update_unsaved_changes_indicator)
        self.ui.labels_input.textChanged.connect(self.event_handler.update_unsaved_changes_indicator)
        self.ui.tags_input.textChanged.connect(self.event_handler.update_unsaved_changes_indicator)
        self.ui.properties_table.itemChanged.connect(self.event_handler.update_unsaved_changes_indicator)
        self.ui.relationships_table.itemChanged.connect(self.event_handler.update_unsaved_changes_indicator)

        # Depth spinbox change
        self.ui.depth_spinbox.valueChanged.connect(self.tree_controller.on_depth_changed)

    def _load_default_state(self):
        """
        Initialize default UI state.
        """
        self.ui.name_input.clear()
        self.ui.description_input.clear()
        self.ui.labels_input.clear()
        self.ui.tags_input.clear()
        self.ui.properties_table.setRowCount(0)
        self.ui.relationships_table.setRowCount(0)
        self.tree_controller.refresh_tree_view()

    def cleanup(self):
        """
        Clean up resources.
        """
        self.node_controller.cleanup()
        self.model.close()

    def handle_error(self, error_message: str):
        """
        Handle any errors.

        Args:
            error_message (str): The error message to display.
        """
        logging.error(error_message)
        QMessageBox.critical(self.ui, "Error", error_message)

    def export_as_json(self):
        """
        Export selected nodes data as JSON file.
        """
        selected_nodes = self.get_selected_nodes()
        if not selected_nodes:
            QMessageBox.warning(self.ui, "Warning", "No nodes selected for export.")
            return

        file_name, _ = QFileDialog.getSaveFileName(
            self.ui, "Export as JSON", "", "JSON Files (*.json)"
        )
        if file_name:
            try:
                all_node_data = []
                for node_name in selected_nodes:
                    if node_data := self._collect_node_data_for_export(node_name):
                        all_node_data.append(node_data)

                with open(file_name, "w") as file:
                    json.dump(all_node_data, file, indent=4)
                QMessageBox.information(
                    self.ui,
                    "Success",
                    "Selected nodes data exported as JSON successfully",
                )
            except Exception as e:
                self.handle_error(
                    f"Error exporting selected nodes data as JSON: {str(e)}"
                )

    def export_as_txt(self):
        """
        Export selected nodes data as plain text file.
        """
        selected_nodes = self.get_selected_nodes()
        if not selected_nodes:
            QMessageBox.warning(self.ui, "Warning", "No nodes selected for export.")
            return

        file_name, _ = QFileDialog.getSaveFileName(
            self.ui, "Export as TXT", "", "Text Files (*.txt)"
        )
        if file_name:
            try:
                with open(file_name, "w") as file:
                    for node_name in selected_nodes:
                        if node_data := self._collect_node_data_for_export(
                            node_name
                        ):
                            file.write(f"Name: {node_data['name']}\n")
                            file.write(f"Description: {node_data['description']}\n")
                            file.write(f"Tags: {', '.join(node_data['tags'])}\n")
                            file.write(f"Labels: {', '.join(node_data['labels'])}\n")
                            file.write("Relationships:\n")
                            for rel in node_data["relationships"]:
                                file.write(
                                    f"  - Type: {rel[0]}, Target: {rel[1]}, Direction: {rel[2]}, Properties: {json.dumps(rel[3])}\n"
                                )
                            file.write("Additional Properties:\n")
                            for key, value in node_data[
                                "additional_properties"
                            ].items():
                                file.write(f"  - {key}: {value}\n")
                            file.write("\n")
                QMessageBox.information(
                    self.ui,
                    "Success",
                    "Selected nodes data exported as TXT successfully",
                )
            except Exception as e:
                self.handle_error(
                    f"Error exporting selected nodes data as TXT: {str(e)}"
                )

    def export_as_csv(self):
        """
        Export selected nodes data as CSV file.
        """
        selected_nodes = self.get_selected_nodes()
        if not selected_nodes:
            QMessageBox.warning(self.ui, "Warning", "No nodes selected for export.")
            return

        file_name, _ = QFileDialog.getSaveFileName(
            self.ui, "Export as CSV", "", "CSV Files (*.csv)"
        )
        if file_name:
            try:
                with open(file_name, "w") as file:
                    file.write(
                        "Name,Description,Tags,Labels,Relationships,Additional Properties\n"
                    )
                    for node_name in selected_nodes:
                        if node_data := self._collect_node_data_for_export(
                            node_name
                        ):
                            file.write(
                                f"{node_data['name']},{node_data['description']},{', '.join(node_data['tags'])},{', '.join(node_data['labels'])},"
                            )
                            relationships = "; ".join(
                                [
                                    f"Type: {rel[0]}, Target: {rel[1]}, Direction: {rel[2]}, Properties: {json.dumps(rel[3])}"
                                    for rel in node_data["relationships"]
                                ]
                            )
                            additional_properties = "; ".join(
                                [
                                    f"{key}: {value}"
                                    for key, value in node_data[
                                        "additional_properties"
                                    ].items()
                                ]
                            )
                            file.write(f"{relationships},{additional_properties}\n")
                QMessageBox.information(
                    self.ui,
                    "Success",
                    "Selected nodes data exported as CSV successfully",
                )
            except Exception as e:
                self.handle_error(
                    f"Error exporting selected nodes data as CSV: {str(e)}"
                )

    def export_as_pdf(self):
        """
        Export selected nodes data as PDF file.
        """
        from fpdf import FPDF

        selected_nodes = self.get_selected_nodes()
        if not selected_nodes:
            QMessageBox.warning(self.ui, "Warning", "No nodes selected for export.")
            return

        file_name, _ = QFileDialog.getSaveFileName(
            self.ui, "Export as PDF", "", "PDF Files (*.pdf)"
        )
        if file_name:
            try:
                pdf = FPDF()
                pdf.set_font("Arial", size=12)

                for node_name in selected_nodes:
                    if node_data := self._collect_node_data_for_export(node_name):
                        pdf.add_page()
                        pdf.cell(200, 10, txt=f"Name: {node_data['name']}", ln=True)
                        pdf.cell(
                            200,
                            10,
                            txt=f"Description: {node_data['description']}",
                            ln=True,
                        )
                        pdf.cell(
                            200,
                            10,
                            txt=f"Tags: {', '.join(node_data['tags'])}",
                            ln=True,
                        )
                        pdf.cell(
                            200,
                            10,
                            txt=f"Labels: {', '.join(node_data['labels'])}",
                            ln=True,
                        )
                        pdf.cell(200, 10, txt="Relationships:", ln=True)
                        for rel in node_data["relationships"]:
                            pdf.cell(
                                200,
                                10,
                                txt=f"  - Type: {rel[0]}, Target: {rel[1]}, Direction: {rel[2]}, Properties: {json.dumps(rel[3])}",
                                ln=True,
                            )
                        pdf.cell(200, 10, txt="Additional Properties:", ln=True)
                        for key, value in node_data["additional_properties"].items():
                            pdf.cell(200, 10, txt=f"  - {key}: {value}", ln=True)

                pdf.output(file_name)
                QMessageBox.information(
                    self.ui,
                    "Success",
                    "Selected nodes data exported as PDF successfully",
                )
            except Exception as e:
                self.handle_error(
                    f"Error exporting selected nodes data as PDF: {str(e)}"
                )

    def get_selected_nodes(self) -> List[str]:
        """
        Get the names of checked nodes in the tree view.
        """
        selected_nodes = []
        logging.debug("Starting to gather selected nodes.")

        def traverse_tree(parent_item):
            """Recursively traverse tree to find checked items"""
            if parent_item.hasChildren():
                for row in range(parent_item.rowCount()):
                    child = parent_item.child(row)
                    if child.hasChildren():
                        # If this is a relationship item, check its children
                        for child_row in range(child.rowCount()):
                            node_item = child.child(child_row)
                            if (
                                node_item
                                and node_item.checkState() == Qt.CheckState.Checked
                                and node_item.data(Qt.ItemDataRole.UserRole)
                            ):
                                selected_nodes.append(
                                    node_item.data(Qt.ItemDataRole.UserRole)
                                )
                        traverse_tree(child)
                    else:
                        # If this is a node item directly
                        if child.checkState() == Qt.CheckState.Checked and child.data(
                            Qt.ItemDataRole.UserRole
                        ):
                            selected_nodes.append(child.data(Qt.ItemDataRole.UserRole))

        # Start traversal from root
        root_item = self.tree_controller.tree_model.invisibleRootItem()
        traverse_tree(root_item)

        # Remove duplicates while preserving order
        unique_nodes = list(dict.fromkeys(selected_nodes))
        logging.debug(f"Found checked nodes: {unique_nodes}")
        return unique_nodes

    def _collect_node_data_for_export(self, node_name: str) -> Optional[Dict[str, Any]]:
        """
        Collect node data for export.

        Args:
            node_name (str): The name of the node to collect data for.

        Returns:
            Optional[Dict[str, Any]]: The collected node data.
        """
        try:
            node_data = {
                "name": node_name,
                "description": self.ui.description_input.toPlainText().strip(),
                "tags": self.utility_controller._parse_comma_separated(self.ui.tags_input.text()),
                "labels": [
                    label.strip().upper().replace(" ", "_")
                    for label in self.utility_controller._parse_comma_separated(
                        self.ui.labels_input.text()
                    )
                ],
                "relationships": self.node_controller._collect_relationships(),
                "additional_properties": self.node_controller._collect_properties(),
            }

            if self.current_image_path:
                node_data["additional_properties"][
                    "image_path"
                ] = self.current_image_path
            else:
                node_data["additional_properties"]["image_path"] = None

            return node_data
        except ValueError as e:
            self.handle_error(str(e))
            return None
