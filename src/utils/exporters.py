import html
import json
from typing import Callable, Tuple
from typing import Dict, Any, List

from PyQt6.QtWidgets import QFileDialog, QMessageBox
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak


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
        self,
        format_type: str,
        selected_nodes: List[str],
        collect_node_data: Callable[[str], Dict[str, Any]],
    ) -> None:
        """
        Main export method that handles all export formats.

        Args:
            format_type (str): The type of export format (e.g., 'json', 'txt', 'csv', 'pdf').
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
            format_type (str): The type of export format (e.g., 'json', 'txt', 'csv', 'pdf').

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
        Handle PDF export using PDFExporter.

        Args:
            file_name (str): The name of the file to save.
            nodes_data (List[Dict[str, Any]]): The list of node data to export.
        """
        pdf_exporter = PDFExporter()
        pdf_exporter.export_to_pdf(file_name, nodes_data)

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


class PDFExporter:
    def __init__(self):
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()

    def _setup_custom_styles(self):
        """Setup custom paragraph styles for better formatting"""
        self.styles.add(
            ParagraphStyle(
                name="CustomNormal",
                parent=self.styles["Normal"],
                fontSize=10,
                leading=14,
                leftIndent=0,
                rightIndent=0,
            )
        )
        self.styles.add(
            ParagraphStyle(
                name="CustomHeading1",
                parent=self.styles["Heading1"],
                fontSize=14,
                leading=18,
                spaceAfter=10,
            )
        )
        self.styles.add(
            ParagraphStyle(
                name="CustomHeading2",
                parent=self.styles["Heading2"],
                fontSize=12,
                leading=16,
                spaceBefore=10,
                spaceAfter=6,
            )
        )
        self.styles.add(
            ParagraphStyle(
                name="IndentedText",
                parent=self.styles["Normal"],
                leftIndent=20,
                fontSize=10,
                leading=14,
            )
        )

    def _escape_text(self, text: Any) -> str:
        """
        Safely convert any input to string and escape HTML entities.

        Args:
            text: Any input that needs to be converted to safe string

        Returns:
            str: HTML-escaped string safe for PDF
        """
        return html.escape(str(text))

    def _format_relationship(self, rel: tuple) -> str:
        """
        Format relationship data safely for PDF.

        Args:
            rel: Tuple containing (type, target, direction, properties)

        Returns:
            str: Formatted relationship string
        """
        try:
            rel_type, target, direction, properties = rel
            props_str = ", ".join(f"{k}: {v}" for k, v in properties.items())
            return self._escape_text(
                f"Type: {rel_type}, Target: {target}, "
                f"Direction: {direction}, Properties: {{{props_str}}}"
            )
        except Exception as e:
            return f"Error formatting relationship: {str(e)}"

    def _add_section(
        self,
        elements: List,
        title: str,
        content: Any,
        style: str = "CustomNormal",
        indented: bool = False,
    ) -> None:
        """
        Add a section to the PDF with proper formatting.

        Args:
            elements: List of PDF elements
            title: Section title
            content: Content to add
            style: Style to apply to content
            indented: Whether to indent the content
        """
        elements.append(Paragraph(title, self.styles["CustomHeading2"]))

        if isinstance(content, list):
            for item in content:
                elements.append(
                    Paragraph(
                        f"• {self._escape_text(item)}",
                        self.styles["IndentedText" if indented else style],
                    )
                )
        else:
            elements.append(
                Paragraph(
                    self._escape_text(content),
                    self.styles["IndentedText" if indented else style],
                )
            )
        elements.append(Spacer(1, 6))

    def export_to_pdf(self, file_name: str, nodes_data: List[Dict[str, Any]]) -> None:
        """
        Export nodes data to a PDF file.

        Args:
            file_name: Name of the PDF file to create
            nodes_data: List of node data dictionaries to export

        Raises:
            ValueError: If file_name is empty or nodes_data is empty
            IOError: If there are issues writing to the file
        """
        if not file_name or not nodes_data:
            raise ValueError("File name and nodes data are required")

        # Create PDF document
        doc = SimpleDocTemplate(
            file_name,
            pagesize=letter,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=72,
        )

        elements = []

        # Add title
        elements.append(Paragraph("Node Export Report", self.styles["Title"]))
        elements.append(Spacer(1, 30))

        # Process each node
        for i, node_data in enumerate(nodes_data):
            if i > 0:
                elements.append(PageBreak())

            try:
                # Node name as header
                elements.append(
                    Paragraph(
                        f"Node: {self._escape_text(node_data.get('name', 'Unnamed'))}",
                        self.styles["CustomHeading1"],
                    )
                )
                elements.append(Spacer(1, 12))

                # Description
                self._add_section(
                    elements,
                    "Description:",
                    node_data.get("description", "No description available"),
                )

                # Tags
                self._add_section(
                    elements, "Tags:", ", ".join(node_data.get("tags", []))
                )

                # Labels
                self._add_section(
                    elements, "Labels:", ", ".join(node_data.get("labels", []))
                )

                # Relationships
                elements.append(
                    Paragraph("Relationships:", self.styles["CustomHeading2"])
                )
                for rel in node_data.get("relationships", []):
                    elements.append(
                        Paragraph(
                            f"• {self._format_relationship(rel)}",
                            self.styles["IndentedText"],
                        )
                    )
                elements.append(Spacer(1, 12))

                # Additional Properties
                elements.append(
                    Paragraph("Additional Properties:", self.styles["CustomHeading2"])
                )
                for key, value in node_data.get("additional_properties", {}).items():
                    elements.append(
                        Paragraph(
                            f"• {self._escape_text(key)}: {self._escape_text(value)}",
                            self.styles["IndentedText"],
                        )
                    )
                elements.append(Spacer(1, 12))

            except Exception as e:
                elements.append(
                    Paragraph(
                        f"Error processing node: {str(e)}", self.styles["CustomNormal"]
                    )
                )

        try:
            # Build the PDF
            doc.build(elements)
        except Exception as e:
            raise IOError(f"Failed to create PDF: {str(e)}")
