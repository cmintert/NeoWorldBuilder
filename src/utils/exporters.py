import json
from typing import List, Dict, Callable, Tuple

from PyQt6.QtWidgets import QFileDialog, QMessageBox
from fpdf import FPDF


class Exporter:
    """Handles exporting node data to various file formats."""

    def __init__(self, ui, config):
        self.ui = ui
        self.config = config
        self._format_handlers = {
            "json": self._handle_json,
            "txt": self._handle_txt,
            "csv": self._handle_csv,
            "pdf": self._handle_pdf,
        }
        self._file_types = {
            "json": "JSON Files (*.json)",
            "txt": "Text Files (*.txt)",
            "csv": "CSV Files (*.csv)",
            "pdf": "PDF Files (*.pdf)",
        }

    def export(
        self, format_type: str, selected_nodes: List[str], collect_node_data: Callable
    ) -> None:
        """Main export method that handles all export formats."""
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
        """Get file name from save dialog."""
        file_name, _ = QFileDialog.getSaveFileName(
            self.ui,
            f"Export as {format_type.upper()}",
            "",
            self._file_types[format_type],
        )
        return file_name

    def _collect_nodes_data(
        self, selected_nodes: List[str], collect_node_data: Callable
    ) -> List[Dict]:
        """Collect data for all selected nodes."""
        return [data for node in selected_nodes if (data := collect_node_data(node))]

    def _format_relationship(self, rel: Tuple) -> str:
        """Format a single relationship."""
        return f"Type: {rel[0]}, Target: {rel[1]}, Direction: {rel[2]}, Properties: {json.dumps(rel[3])}"

    def _format_properties(self, properties: Dict) -> str:
        """Format additional properties."""
        return "; ".join(f"{key}: {value}" for key, value in properties.items())

    def _handle_json(self, file_name: str, nodes_data: List[Dict]) -> None:
        """Handle JSON export."""
        with open(file_name, "w") as file:
            json.dump(nodes_data, file, indent=4)

    def _handle_txt(self, file_name: str, nodes_data: List[Dict]) -> None:
        """Handle TXT export."""
        with open(file_name, "w") as file:
            for node_data in nodes_data:
                self._write_txt_node(file, node_data)
                file.write("\n")

    def _write_txt_node(self, file, node_data: Dict) -> None:
        """Write a single node's data in TXT format."""
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

    def _handle_csv(self, file_name: str, nodes_data: List[Dict]) -> None:
        """Handle CSV export."""
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

    def _handle_pdf(self, file_name: str, nodes_data: List[Dict]) -> None:
        """Handle PDF export."""
        pdf = FPDF()
        pdf.set_font("Arial", size=12)

        for node_data in nodes_data:
            pdf.add_page()
            self._write_pdf_node(pdf, node_data)

        pdf.output(file_name)

    def _write_pdf_node(self, pdf: FPDF, node_data: Dict) -> None:
        """Write a single node's data in PDF format."""
        pdf.cell(200, 10, txt=f"Name: {node_data['name']}", ln=True)
        pdf.cell(200, 10, txt=f"Description: {node_data['description']}", ln=True)
        pdf.cell(200, 10, txt=f"Tags: {', '.join(node_data['tags'])}", ln=True)
        pdf.cell(200, 10, txt=f"Labels: {', '.join(node_data['labels'])}", ln=True)
        pdf.cell(200, 10, txt="Relationships:", ln=True)
        for rel in node_data["relationships"]:
            pdf.cell(200, 10, txt=f"  - {self._format_relationship(rel)}", ln=True)
        pdf.cell(200, 10, txt="Additional Properties:", ln=True)
        for key, value in node_data["additional_properties"].items():
            pdf.cell(200, 10, txt=f"  - {key}: {value}", ln=True)

    def _show_success_message(self, format_type: str) -> None:
        """Show success message dialog."""
        QMessageBox.information(
            self.ui,
            "Success",
            f"Selected nodes data exported as {format_type.upper()} successfully",
        )

    def _handle_error(self, error_message: str) -> None:
        """Handle and display error message."""
        QMessageBox.critical(self.ui, "Error", error_message)
