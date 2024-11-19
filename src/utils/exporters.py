import json
from typing import List, Dict, Callable, Tuple, Any

from PyQt6.QtWidgets import QFileDialog, QMessageBox
from fpdf import FPDF


class Exporter:
    """
    Handles exporting node data to various file formats.

    Args:
        ui: The UI instance.
        config: The configuration instance.
    """

    def __init__(self, ui: Any, config: Any) -> None:
        """
        Initialize the Exporter with UI and configuration.

        Args:
            ui: The UI instance.
            config: The configuration instance.
        """
        self.ui = ui
        self.config = config
        self._format_handlers = {
            "database.json": self._handle_json,
            "txt": self._handle_txt,
            "csv": self._handle_csv,
            "pdf": self._handle_pdf,
        }
        self._file_types = {
            "database.json": "JSON Files (*.database.json)",
            "txt": "Text Files (*.txt)",
            "csv": "CSV Files (*.csv)",
            "pdf": "PDF Files (*.pdf)",
        }

    def export(
        self,
        format_type: str,
        selected_nodes: List[str],
        collect_node_data: Callable[[str], Dict[str, Any]],
    ) -> None:
        """
        Main export method that handles all export formats.

        Args:
            format_type (str): The type of export format (e.g., 'database.json', 'txt', 'csv', 'pdf').
            selected_nodes (List[str]): The list of selected node names.
            collect_node_data (Callable[[str], Dict[str, Any]]): The function to collect node data.

        Raises:
            ValueError: If the format type is unsupported.
        """
        if format_type not in self._format_handlers:
            raise ValueError(f"Unsupported format: {format_type}")

        file_name = self._get_file_name(format_type)
        if not file_name:
            return

        try:
            nodes_data = self._collect_nodes_data(selected_nodes, collect_node_data)
            if not nodes_data:
                return

            self._format_handlers[format_type](file_name, nodes_data)
            self._show_success_message(format_type)
        except Exception as e:
            self._handle_error(f"Error exporting as {format_type.upper()}: {str(e)}")

    def _get_file_name(self, format_type: str) -> str:
        """
        Get file name from save dialog.

        Args:
            format_type (str): The type of export format (e.g., 'database.json', 'txt', 'csv', 'pdf').

        Returns:
            str: The selected file name.
        """
        file_name, _ = QFileDialog.getSaveFileName(
            self.ui,
            f"Export as {format_type.upper()}",
            "",
            self._file_types[format_type],
        )
        return file_name

    def _collect_nodes_data(
        self,
        selected_nodes: List[str],
        collect_node_data: Callable[[str], Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Collect data for all selected nodes.

        Args:
            selected_nodes (List[str]): The list of selected node names.
            collect_node_data (Callable[[str], Dict[str, Any]]): The function to collect node data.

        Returns:
            List[Dict[str, Any]]: The list of collected node data.
        """
        return [data for node in selected_nodes if (data := collect_node_data(node))]

    def _format_relationship(self, rel: Tuple[str, str, str, Dict[str, Any]]) -> str:
        """
        Format a single relationship.

        Args:
            rel (Tuple[str, str, str, Dict[str, Any]]): The relationship tuple containing type, target, direction, and properties.

        Returns:
            str: The formatted relationship string.
        """
        return f"Type: {rel[0]}, Target: {rel[1]}, Direction: {rel[2]}, Properties: {json.dumps(rel[3])}"

    def _format_properties(self, properties: Dict[str, Any]) -> str:
        """
        Format additional properties.

        Args:
            properties (Dict[str, Any]): The dictionary of additional properties.

        Returns:
            str: The formatted properties string.
        """
        return "; ".join(f"{key}: {value}" for key, value in properties.items())

    def _handle_json(self, file_name: str, nodes_data: List[Dict[str, Any]]) -> None:
        """
        Handle JSON export.

        Args:
            file_name (str): The name of the file to save.
            nodes_data (List[Dict[str, Any]]): The list of node data to export.
        """
        with open(file_name, "w") as file:
            json.dump(nodes_data, file, indent=4)

    def _handle_txt(self, file_name: str, nodes_data: List[Dict[str, Any]]) -> None:
        """
        Handle TXT export.

        Args:
            file_name (str): The name of the file to save.
            nodes_data (List[Dict[str, Any]]): The list of node data to export.
        """
        with open(file_name, "w") as file:
            for node_data in nodes_data:
                self._write_txt_node(file, node_data)
                file.write("\n")

    def _write_txt_node(self, file: Any, node_data: Dict[str, Any]) -> None:
        """
        Write a single node's data in TXT format.

        Args:
            file: The file object to write to.
            node_data (Dict[str, Any]): The node data to write.
        """
        file.write(f"Name: {node_data['name']}\n")
        file.write(f"Description: {node_data['description']}\n")
        file.write(f"Tags: {', '.join(node_data['tags'])}\n")
        file.write(f"Labels: {', '.join(node_data['labels'])}\n")
        file.write("Relationships:\n")
        for rel in node_data["relationships"]:
            file.write(f"  - {self._format_relationship(rel)}\n")
        file.write("Additional Properties:\n")
        for key, value in node_data["additional_properties"].items():
            file.write(f"  - {key}: {value}\n")

    def _handle_csv(self, file_name: str, nodes_data: List[Dict[str, Any]]) -> None:
        """
        Handle CSV export.

        Args:
            file_name (str): The name of the file to save.
            nodes_data (List[Dict[str, Any]]): The list of node data to export.
        """
        with open(file_name, "w") as file:
            file.write(
                "Name,Description,Tags,Labels,Relationships,Additional Properties\n"
            )
            for node_data in nodes_data:
                relationships = "; ".join(
                    self._format_relationship(rel) for rel in node_data["relationships"]
                )
                properties = self._format_properties(node_data["additional_properties"])

                file.write(
                    f"{node_data['name']},{node_data['description']},"
                    f"{', '.join(node_data['tags'])},{', '.join(node_data['labels'])},"
                    f"{relationships},{properties}\n"
                )

    def _handle_pdf(self, file_name: str, nodes_data: List[Dict[str, Any]]) -> None:
        """
        Handle PDF export.

        Args:
            file_name (str): The name of the file to save.
            nodes_data (List[Dict[str, Any]]): The list of node data to export.
        """
        pdf = FPDF()
        pdf.set_font("Arial", size=12)

        for node_data in nodes_data:
            pdf.add_page()
            self._write_pdf_node(pdf, node_data)

        pdf.output(file_name)

    def _write_pdf_node(self, pdf: FPDF, node_data: Dict[str, Any]) -> None:
        """
        Write a single node's data in PDF format.

        Args:
            pdf (FPDF): The PDF object to write to.
            node_data (Dict[str, Any]): The node data to write.
        """
        pdf.cell(200, 10, text=f"Name: {node_data['name']}", ln=True)
        pdf.cell(200, 10, text=f"Description: {node_data['description']}", ln=True)
        pdf.cell(200, 10, text=f"Tags: {', '.join(node_data['tags'])}", ln=True)
        pdf.cell(200, 10, text=f"Labels: {', '.join(node_data['labels'])}", ln=True)
        pdf.cell(200, 10, text="Relationships:", ln=True)
        for rel in node_data["relationships"]:
            pdf.cell(200, 10, text=f"  - {self._format_relationship(rel)}", ln=True)
        pdf.cell(200, 10, text="Additional Properties:", ln=True)
        for key, value in node_data["additional_properties"].items():
            pdf.cell(200, 10, text=f"  - {key}: {value}", ln=True)

    def _show_success_message(self, format_type: str) -> None:
        """
        Show success message dialog.

        Args:
            format_type (str): The type of export format (e.g., 'database.json', 'txt', 'csv', 'pdf').
        """
        QMessageBox.information(
            self.ui,
            "Success",
            f"Selected nodes data exported as {format_type.upper()} successfully",
        )

    def _handle_error(self, error_message: str) -> None:
        """
        Handle and display error message.

        Args:
            error_message (str): The error message to display.
        """
        QMessageBox.critical(self.ui, "Error", error_message)
