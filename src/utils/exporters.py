import json
from typing import List

from PyQt6.QtWidgets import QFileDialog, QMessageBox


class Exporter:
    def __init__(self, ui, config):
        self.ui = ui
        self.config = config

    def export_as_json(self, selected_nodes: List[str], collect_node_data: callable):
        file_name, _ = QFileDialog.getSaveFileName(
            self.ui, "Export as JSON", "", "JSON Files (*.json)"
        )
        if file_name:
            try:
                all_node_data = []
                for node_name in selected_nodes:
                    if node_data := collect_node_data(node_name):
                        all_node_data.append(node_data)

                with open(file_name, "w") as file:
                    json.dump(all_node_data, file, indent=4)
                QMessageBox.information(
                    self.ui,
                    "Success",
                    "Selected nodes data exported as JSON successfully",
                )
            except Exception as e:
                self._handle_error(
                    f"Error exporting selected nodes data as JSON: {str(e)}"
                )

    def export_as_txt(self, selected_nodes: List[str], collect_node_data: callable):
        file_name, _ = QFileDialog.getSaveFileName(
            self.ui, "Export as TXT", "", "Text Files (*.txt)"
        )
        if file_name:
            try:
                with open(file_name, "w") as file:
                    for node_name in selected_nodes:
                        if node_data := collect_node_data(node_name):
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
                self._handle_error(
                    f"Error exporting selected nodes data as TXT: {str(e)}"
                )

    def export_as_csv(self, selected_nodes: List[str], collect_node_data: callable):
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
                        if node_data := collect_node_data(node_name):
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
                self._handle_error(
                    f"Error exporting selected nodes data as CSV: {str(e)}"
                )

    def export_as_pdf(self, selected_nodes: List[str], collect_node_data: callable):
        from fpdf import FPDF

        file_name, _ = QFileDialog.getSaveFileName(
            self.ui, "Export as PDF", "", "PDF Files (*.pdf)"
        )
        if file_name:
            try:
                pdf = FPDF()
                pdf.set_font("Arial", size=12)

                for node_name in selected_nodes:
                    if node_data := collect_node_data(node_name):
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
                self._handle_error(
                    f"Error exporting selected nodes data as PDF: {str(e)}"
                )

    def _handle_error(self, error_message: str):
        QMessageBox.critical(self.ui, "Error", error_message)
