from PyQt6.QtCore import QObject, pyqtSlot
from PyQt6.QtWidgets import QMessageBox

from core.neo4jworkers import SuggestionWorker
from ui.dialogs import SuggestionDialog


class SuggestionController(QObject):
    def __init__(self, ui, model):
        super().__init__()
        self.ui = ui
        self.model = model
        self.current_suggestion_worker = None

    def show_suggestions_modal(self):
        node_data = self._collect_node_data()
        if not node_data:
            return

        # Show loading indicator
        self.ui.show_loading(True)

        # Cancel any existing SuggestionWorker
        if self.current_suggestion_worker:
            self.current_suggestion_worker.cancel()
            self.current_suggestion_worker.wait()
            self.current_suggestion_worker = None
            logging.debug("Existing SuggestionWorker canceled and cleaned up.")

        # Create and start the SuggestionWorker
        self.current_suggestion_worker = SuggestionWorker(self.model._uri, self.model._auth,
                                                          node_data)
        self.current_suggestion_worker.suggestions_ready.connect(self.handle_suggestions)
        self.current_suggestion_worker.error_occurred.connect(self.handle_error)
        self.current_suggestion_worker.finished.connect(self.on_suggestion_worker_finished)
        self.current_suggestion_worker.start()

        logging.debug("SuggestionWorker started successfully.")

    def on_suggestion_worker_finished(self):
        """
        Cleanup after SuggestionWorker has finished.
        """
        self.current_suggestion_worker = None
        self.ui.show_loading(False)
        logging.debug("SuggestionWorker has finished and cleaned up.")

    def handle_suggestions(self, suggestions):
        """
        Handle the suggestions received from the SuggestionWorker.

        Args:
            suggestions (dict): The suggestions dictionary containing tags, properties, and relationships.
        """
        logging.debug(f"handle_suggestions called with suggestions: {suggestions}")
        # Hide loading indicator
        self.ui.show_loading(False)
        logging.debug("Loading indicator hidden.")

        if not suggestions or all(not suggestions[key] for key in suggestions):
            logging.debug("No suggestions found.")
            QMessageBox.information(self.ui, "No Suggestions",
                                    "No suggestions were found for this node.")
            return

        dialog = SuggestionDialog(suggestions, self.ui)
        if dialog.exec():
            selected = dialog.selected_suggestions
            logging.debug(f"User selected suggestions: {selected}")

            # Update tags
            existing_tags = self._parse_comma_separated(self.ui.tags_input.text())
            new_tags = list(set(existing_tags + selected['tags']))
            self.ui.tags_input.setText(', '.join(new_tags))
            logging.debug(f"Updated tags: {new_tags}")

            # Update properties
            for key, value in selected['properties'].items():
                self.add_or_update_property(key, value)
                logging.debug(f"Updated property - Key: {key}, Value: {value}")

            # Update relationships
            for rel in selected['relationships']:
                rel_type, target, direction, props = rel
                self.ui.add_relationship_row(rel_type, target, direction, json.dumps(props))
                logging.debug(
                    f"Added relationship - Type: {rel_type}, Target: {target}, Direction: {direction}, Properties: {props}")

            QMessageBox.information(self.ui, "Suggestions Applied",
                                    "Selected suggestions have been applied to the node.")
        else:
            logging.debug("Suggestion dialog was canceled by the user.")

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
        logging.error(error_message)
        QMessageBox.critical(self.ui, "Error", error_message)

    def _parse_comma_separated(self, text: str) -> List[str]:
        """
        Parse comma-separated input.

        Args:
            text (str): The comma-separated input text.

        Returns:
            List[str]: The parsed list of strings.
        """
        return [item.strip() for item in text.split(",") if item.strip()]

    def _collect_node_data(self) -> Optional[Dict[str, Any]]:
        """
        Collect all node data from UI.

        Returns:
            Optional[Dict[str, Any]]: The collected node data.
        """
        try:
            node_data = {
                "name": self.ui.name_input.text().strip(),
                "description": self.ui.description_input.toPlainText().strip(),
                "tags": self._parse_comma_separated(self.ui.tags_input.text()),
                "labels": [
                    label.strip().upper().replace(" ", "_")
                    for label in self._parse_comma_separated(
                        self.ui.labels_input.text()
                    )
                ],
                "relationships": self._collect_relationships(),
                "additional_properties": self._collect_properties(),
            }

            if self.current_image_path:
                node_data["additional_properties"][
                    "image_path"
                ] = self.current_image_path
            else:
                node_data["additional_properties"]["image_path"] = None

            logging.debug(f"Collected Node Data: {node_data}")

            return node_data
        except ValueError as e:
            self.handle_error(str(e))
            return None

    def _collect_properties(self) -> Dict[str, Any]:
        """
        Collect properties from table.

        Returns:
            Dict[str, Any]: The collected properties.
        """
        properties = {}
        for row in range(self.ui.properties_table.rowCount()):
            key = self.ui.properties_table.item(row, 0)
            value = self.ui.properties_table.item(row, 1)

            if not key or not key.text().strip():
                continue

            key_text = key.text().strip()

            if key_text.lower() in self.config.RESERVED_PROPERTY_KEYS:
                raise ValueError(f"Property key '{key_text}' is reserved")

            if key_text.startswith("_"):
                raise ValueError(
                    f"Property key '{key_text}' cannot start with an underscore"
                )

            try:
                value_text = value.text().strip() if value else ""
                properties[key_text] = (
                    json.loads(value_text) if value_text else value_text
                )
            except json.JSONDecodeError:
                properties[key_text] = value_text

        return properties

    def _collect_relationships(self) -> List[tuple]:
        """
        Collect relationships from table.

        Returns:
            List[tuple]: The collected relationships.
        """
        relationships = []
        for row in range(self.ui.relationships_table.rowCount()):
            rel_type = self.ui.relationships_table.item(row, 0)
            target = self.ui.relationships_table.cellWidget(row, 1)
            direction = self.ui.relationships_table.cellWidget(row, 2)
            props = self.ui.relationships_table.item(row, 3)

            if not all([rel_type, target, direction]):
                continue

            try:
                properties = (
                    json.loads(props.text()) if props and props.text().strip() else {}
                )

                # Enforce uppercase and replace spaces with underscores
                formatted_rel_type = rel_type.text().strip().upper().replace(" ", "_")

                relationships.append(
                    (
                        formatted_rel_type,
                        target.text().strip(),
                        direction.currentText(),
                        properties,
                    )
                )
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON in relationship properties: {e}")

        logging.debug(f"Collected the following Relationships: {relationships}")
        return relationships
