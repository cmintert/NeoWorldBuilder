import json
import logging
from typing import Optional, Dict, Any, List, Tuple

from PyQt6.QtCore import QObject, QStringListModel, Qt, pyqtSlot, QTimer
from PyQt6.QtGui import QStandardItemModel, QStandardItem, QIcon
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QCompleter,
    QLineEdit,
    QMessageBox,
    QTableWidgetItem,
    QFileDialog,
)

from core.neo4jworkers import SuggestionWorker
from ui.dialogs import SuggestionDialog, ConnectionSettingsDialog
from utils.exporters import Exporter


class NodeOperationsController(QObject):
    def __init__(self, model: "Neo4jModel", ui: "WorldBuildingUI", config: "Config"):
        super().__init__()
        self.model = model
        self.ui = ui
        self.config = config
        self.current_load_worker = None
        self.current_save_worker = None
        self.current_delete_worker = None

    def load_node_data(self) -> None:
        name = self.ui.name_input.text().strip()
        if not name:
            return

        self.ui.clear_all_fields()

        if self.current_load_worker:
            self.current_load_worker.cancel()
            self.current_load_worker.wait()

        self.current_load_worker = self.model.load_node(name, self._handle_node_data)
        self.current_load_worker.error_occurred.connect(self.handle_error)
        self.current_load_worker.start()

    def save_node(self) -> None:
        name = self.ui.name_input.text().strip()
        if not self.validate_node_name(name):
            return

        node_data = self._collect_node_data()
        if not node_data:
            return

        if self.current_save_worker:
            self.current_save_worker.cancel()

        self.current_save_worker = self.model.save_node(node_data, self.on_save_success)
        self.current_save_worker.error_occurred.connect(self.handle_error)
        self.current_save_worker.start()

    def delete_node(self) -> None:
        name = self.ui.name_input.text().strip()
        if not name:
            return

        reply = QMessageBox.question(
            self.ui,
            "Confirm Deletion",
            f'Are you sure you want to delete node "{name}"?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            if self.current_delete_worker:
                self.current_delete_worker.cancel()
                self.current_delete_worker.wait()

            self.current_delete_worker = self.model.delete_node(
                name, self._handle_delete_success
            )
            self.current_delete_worker.error_occurred.connect(self.handle_error)
            self.current_delete_worker.start()

    def _handle_node_data(self, data: List[Any]) -> None:
        if not data:
            return

        try:
            record = data[0]
            self._populate_node_fields(record)
            self.original_node_data = self._collect_node_data()
            self.ui.save_button.setStyleSheet("background-color: #d3d3d3;")
        except Exception as e:
            self.handle_error(f"Error populating node fields: {str(e)}")

    def _handle_delete_success(self, _: Any) -> None:
        QMessageBox.information(self.ui, "Success", "Node deleted successfully")
        self._load_default_state()

    def on_save_success(self, _: Any) -> None:
        msg_box = QMessageBox(self.ui)
        msg_box.setIcon(QMessageBox.Icon.Information)
        msg_box.setWindowTitle("Success")
        msg_box.setText("Node saved successfully")
        msg_box.setStandardButtons(QMessageBox.StandardButton.NoButton)
        msg_box.show()

        QTimer.singleShot(1000, msg_box.accept)

        self.refresh_tree_view()
        self.load_node_data()

    def _collect_node_data(self) -> Optional[Dict[str, Any]]:
        try:
            node_data = {
                "name": self.ui.name_input.text().strip(),
                "description": self.ui.description_input.toHtml().strip(),
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

    def _collect_relationships(self) -> List[Tuple[str, str, str, Dict[str, Any]]]:
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
                raise ValueError(f"Invalid JSON in relationship properties: {e}") from e

        logging.debug(f"Collected the following Relationships: {relationships}")
        return relationships

    def _populate_node_fields(self, record: Any) -> None:
        try:
            node = record["n"]
            labels = record["labels"]
            relationships = record["relationships"]
            properties = record["all_props"]

            node_properties = dict(node)
            node_name = node_properties.get("name", "")
            node_description = node_properties.get("description", "")
            node_tags = node_properties.get("tags", [])
            image_path = node_properties.get("image_path")

            self.ui.name_input.setText(node_name)
            self.ui.description_input.setHtml(node_description)
            self.ui.labels_input.setText(", ".join(labels))
            self.ui.tags_input.setText(", ".join(node_tags))

            self.ui.properties_table.setRowCount(0)
            for key, value in properties.items():
                if key.startswith("_"):
                    continue

                if key not in ["name", "description", "tags", "image_path"]:
                    row = self.ui.properties_table.rowCount()
                    self.ui.properties_table.insertRow(row)
                    self.ui.properties_table.setItem(row, 0, QTableWidgetItem(key))
                    self.ui.properties_table.setItem(
                        row, 1, QTableWidgetItem(str(value))
                    )
                    delete_button = self.ui.create_delete_button(
                        self.ui.properties_table, row
                    )
                    self.ui.properties_table.setCellWidget(row, 2, delete_button)

            self.ui.relationships_table.setRowCount(0)
            for rel in relationships:
                rel_type = rel.get("type", "")
                target = rel.get("end", "")
                direction = rel.get("dir", ">")
                props = json.dumps(rel.get("props", {}))

                self.ui.add_relationship_row(rel_type, target, direction, props)

            self.current_image_path = image_path
            self.ui.set_image(image_path)

        except Exception as e:
            self.handle_error(f"Error populating node fields: {str(e)}")

    def validate_node_name(self, name: str) -> bool:
        if not name:
            QMessageBox.warning(self.ui, "Warning", "Node name cannot be empty.")
            return False

        if len(name) > self.config.MAX_NODE_NAME_LENGTH:
            QMessageBox.warning(
                self.ui,
                "Warning",
                f"Node name cannot exceed {self.config.MAX_NODE_NAME_LENGTH} characters.",
            )
            return False

        return True

    def handle_error(self, error_message: str) -> None:
        logging.error(error_message)
        QMessageBox.critical(self.ui, "Error", error_message)

    def _parse_comma_separated(self, text: str) -> List[str]:
        return [item.strip() for item in text.split(",") if item.strip()]


class TreeController(QObject):
    def __init__(self, model: "Neo4jModel", ui: "WorldBuildingUI", config: "Config"):
        super().__init__()
        self.model = model
        self.ui = ui
        self.config = config
        self.current_relationship_worker = None
        self.tree_model = QStandardItemModel()
        self.tree_model.setHorizontalHeaderLabels(["Node Relationships"])
        self.ui.tree_view.setModel(self.tree_model)

    def update_relationship_tree(self, node_name: str) -> None:
        if not node_name:
            self.tree_model.clear()
            self.tree_model.setHorizontalHeaderLabels(["Node Relationships"])
            return

        depth = self.ui.depth_spinbox.value()

        if self.current_relationship_worker:
            self.current_relationship_worker.cancel()
            self.current_relationship_worker.wait()

        self.current_relationship_worker = self.model.get_node_relationships(
            node_name, depth, self._populate_relationship_tree
        )
        self.current_relationship_worker.error_occurred.connect(self.handle_error)
        self.current_relationship_worker.start()

    def refresh_tree_view(self) -> None:
        if name := self.ui.name_input.text().strip():
            self.update_relationship_tree(name)

    def on_tree_selection_changed(self, selected: Any, deselected: Any) -> None:
        if indexes := selected.indexes():
            if selected_item := self.tree_model.itemFromIndex(indexes[0]):
                node_name = selected_item.data(Qt.ItemDataRole.UserRole)
                if node_name and node_name != self.ui.name_input.text():
                    self.ui.name_input.setText(node_name)
                    self.load_node_data()

    def _populate_relationship_tree(self, records: List[Any]) -> None:
        try:
            self.tree_model.clear()
            self.tree_model.setHorizontalHeaderLabels(["Node Relationships"])

            if not records:
                return

            root_node_name = self.ui.name_input.text().strip()
            if not root_node_name:
                return

            root_item = QStandardItem(f"🔵 {root_node_name}")
            root_item.setData(root_node_name, Qt.ItemDataRole.UserRole)
            root_item.setFlags(
                Qt.ItemFlag.ItemIsEnabled
                | Qt.ItemFlag.ItemIsSelectable
                | Qt.ItemFlag.ItemIsUserCheckable
            )
            root_item.setCheckState(Qt.CheckState.Unchecked)
            root_item.setIcon(QIcon("path/to/node_icon.png"))

            parent_child_map, skipped_records = self.process_relationship_records(
                records
            )

            self.add_children(
                root_node_name, root_item, [root_node_name], parent_child_map
            )

            self.tree_model.appendRow(root_item)
            self.ui.tree_view.expandAll()

            if skipped_records > 0:
                logging.warning(
                    f"Skipped {skipped_records} incomplete relationship records."
                )

        except Exception as e:
            self.handle_error(f"Error populating relationship tree: {str(e)}")

    def process_relationship_records(
        self, records: List[Any]
    ) -> Tuple[Dict[Tuple[str, str, str], List[Tuple[str, List[str]]]], int]:
        parent_child_map = {}
        skipped_records = 0

        for record in records:
            node_name = record.get("node_name")
            labels = record.get("labels", [])
            parent_name = record.get("parent_name")
            rel_type = record.get("rel_type")
            direction = record.get("direction")

            if not node_name or not parent_name or not rel_type or not direction:
                logging.warning(f"Incomplete record encountered and skipped: {record}")
                skipped_records += 1
                continue

            key = (parent_name, rel_type, direction)
            if key not in parent_child_map:
                parent_child_map[key] = []
            parent_child_map[key].append((node_name, labels))

        return parent_child_map, skipped_records

    def add_children(
        self,
        parent_name: str,
        parent_item: QStandardItem,
        path: List[str],
        parent_child_map: Dict[Tuple[str, str, str], List[Tuple[str, List[str]]]],
    ) -> None:
        for (p_name, rel_type, direction), children in parent_child_map.items():
            if p_name != parent_name:
                continue

            for child_name, child_labels in children:
                if child_name in path:
                    self.handle_cycles(parent_item, rel_type, direction, child_name)
                    continue

                arrow = "➡️" if direction == ">" else "⬅️"

                rel_item = QStandardItem(f"{arrow} [{rel_type}]")
                rel_item.setFlags(
                    Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
                )

                child_item = QStandardItem(
                    f"🔹 {child_name} [{', '.join(child_labels)}]"
                )
                child_item.setData(child_name, Qt.ItemDataRole.UserRole)
                child_item.setFlags(
                    Qt.ItemFlag.ItemIsEnabled
                    | Qt.ItemFlag.ItemIsSelectable
                    | Qt.ItemFlag.ItemIsUserCheckable
                )
                child_item.setCheckState(Qt.CheckState.Unchecked)

                rel_item.appendRow(child_item)
                parent_item.appendRow(rel_item)

                self.add_children(
                    child_name, child_item, path + [child_name], parent_child_map
                )

    def handle_cycles(
        self, parent_item: QStandardItem, rel_type: str, direction: str, child_name: str
    ) -> None:
        rel_item = QStandardItem(f"🔄 [{rel_type}] ({direction})")
        rel_item.setIcon(QIcon("path/to/relationship_icon.png"))

        cycle_item = QStandardItem(f"🔁 {child_name} (Cycle)")
        cycle_item.setData(child_name, Qt.ItemDataRole.UserRole)
        cycle_item.setIcon(QIcon("path/to/cycle_icon.png"))

        rel_item.appendRow(cycle_item)
        parent_item.appendRow(rel_item)

    def handle_error(self, error_message: str) -> None:
        logging.error(error_message)
        QMessageBox.critical(self.ui, "Error", error_message)


class AutoCompletionController(QObject):
    def __init__(self, model: "Neo4jModel", ui: "WorldBuildingUI", config: "Config"):
        super().__init__()
        self.model = model
        self.ui = ui
        self.config = config
        self.current_search_worker = None
        self.node_name_model = QStringListModel()
        self.completer = QCompleter(self.node_name_model)
        self.completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.ui.name_input.setCompleter(self.completer)
        self.completer.activated.connect(self.on_completer_activated)

    def _fetch_matching_nodes(self) -> None:
        text = self.ui.name_input.text().strip()
        if not text:
            return

        if self.current_search_worker:
            self.current_search_worker.cancel()
            self.current_search_worker.wait()

        self.current_search_worker = self.model.fetch_matching_node_names(
            text, self.config.MATCH_NODE_LIMIT, self._handle_autocomplete_results
        )
        self.current_search_worker.error_occurred.connect(self.handle_error)
        self.current_search_worker.start()

    def on_completer_activated(self, text: str) -> None:
        if text:
            self.ui.name_input.setText(text)
            self.load_node_data()

    def _handle_autocomplete_results(self, records: List[Any]) -> None:
        try:
            names = [record["name"] for record in records]
            self.node_name_model.setStringList(names)
        except Exception as e:
            self.handle_error(f"Error processing autocomplete results: {str(e)}")

    def handle_error(self, error_message: str) -> None:
        logging.error(error_message)
        QMessageBox.critical(self.ui, "Error", error_message)


class UIController(QObject):
    def __init__(self, ui: "WorldBuildingUI", config: "Config"):
        super().__init__()
        self.ui = ui
        self.config = config
        self.name_input_timer = QTimer()
        self.name_input_timer.setSingleShot(True)
        self.name_input_timer.timeout.connect(self._fetch_matching_nodes)
        self.name_input_timer.setInterval(self.config.NAME_INPUT_DEBOUNCE_TIME_MS)

    def debounce_name_input(self, text: str) -> None:
        self.name_input_timer.stop()
        if text.strip():
            self.name_input_timer.start()

    def update_unsaved_changes_indicator(self) -> None:
        if self.is_node_changed():
            self.ui.save_button.setStyleSheet("background-color: #83A00E;")
        else:
            self.ui.save_button.setStyleSheet("background-color: #d3d3d3;")

    def is_node_changed(self) -> bool:
        current_data = self._collect_node_data()
        return current_data != self.original_node_data

    def change_image(self) -> None:
        try:
            file_name, _ = QFileDialog.getOpenFileName(
                self.ui,
                "Select Image",
                "",
                "Image Files (*.png *.jpg *.bmp)",
            )
            if file_name:
                self.current_image_path = file_name
                self.ui.set_image(file_name)
        except Exception as e:
            self.handle_error(f"Error changing image: {str(e)}")

    def delete_image(self) -> None:
        self.current_image_path = None
        self.ui.set_image(None)

    def handle_error(self, error_message: str) -> None:
        logging.error(error_message)
        QMessageBox.critical(self.ui, "Error", error_message)


class ExportController(QObject):
    def __init__(self, ui: "WorldBuildingUI", config: "Config"):
        super().__init__()
        self.ui = ui
        self.config = config
        self.exporter = Exporter(self.ui, self.config)

    def export_as_json(self) -> None:
        self._export("database.json")

    def export_as_txt(self) -> None:
        self._export("txt")

    def export_as_csv(self) -> None:
        self._export("csv")

    def export_as_pdf(self) -> None:
        self._export("pdf")

    def _export(self, format_type: str) -> None:
        selected_nodes = self.get_selected_nodes()
        if not selected_nodes:
            QMessageBox.warning(self.ui, "Warning", "No nodes selected for export.")
            return

        try:
            self.exporter.export(
                format_type, selected_nodes, self._collect_node_data_for_export
            )
        except ValueError as e:
            self.handle_error(f"Export error: {str(e)}")

    def get_selected_nodes(self) -> List[str]:
        selected_nodes = []

        def get_children(item: QStandardItem) -> List[QStandardItem]:
            return [item.child(row) for row in range(item.rowCount())]

        def process_node(item: QStandardItem) -> None:
            if not item:
                return
            if item.checkState() == Qt.CheckState.Checked and item.data(
                Qt.ItemDataRole.UserRole
            ):
                selected_nodes.append(item.data(Qt.ItemDataRole.UserRole))

        def process_tree() -> None:
            queue = []
            root = self.tree_model.invisibleRootItem()

            root_children = get_children(root)
            for child in root_children:
                process_node(child)
                queue.append(child)

            while queue:
                item = queue.pop(0)
                if not item.hasChildren():
                    continue

                children = get_children(item)
                for child in children:
                    process_node(child)

                queue.extend(children)

        process_tree()

        unique_nodes = list(dict.fromkeys(selected_nodes))
        return unique_nodes

    def _collect_node_data_for_export(self, node_name: str) -> Optional[Dict[str, Any]]:
        try:
            node_data = {
                "name": node_name,
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

            return node_data
        except ValueError as e:
            self.handle_error(str(e))
            return None

    def handle_error(self, error_message: str) -> None:
        logging.error(error_message)
        QMessageBox.critical(self.ui, "Error", error_message)

    def _parse_comma_separated(self, text: str) -> List[str]:
        return [item.strip() for item in text.split(",") if item.strip()]


class WorldBuildingController(QObject):
    def __init__(
        self,
        ui: "WorldBuildingUI",
        model: "Neo4jModel",
        config: "Config",
        app_instance: "WorldBuildingApp",
    ) -> None:
        super().__init__()
        self.ui = ui
        self.model = model
        self.config = config
        self.app_instance = app_instance

        self.node_operations_controller = NodeOperationsController(
            model, ui, config
        )
        self.tree_controller = TreeController(model, ui, config)
        self.auto_completion_controller = AutoCompletionController(
            model, ui, config
        )
        self.ui_controller = UIController(ui, config)
        self.export_controller = ExportController(ui, config)

        self._connect_signals()

    def _connect_signals(self) -> None:
        self.ui.save_button.clicked.connect(self.node_operations_controller.save_node)
        self.ui.delete_button.clicked.connect(self.node_operations_controller.delete_node)
        self.ui.change_image_button.clicked.connect(self.ui_controller.change_image)
        self.ui.delete_image_button.clicked.connect(self.ui_controller.delete_image)
        self.ui.name_input.textChanged.connect(self.ui_controller.debounce_name_input)
        self.ui.name_input.editingFinished.connect(self.node_operations_controller.load_node_data)
        self.ui.add_rel_button.clicked.connect(self.ui.add_relationship_row)
        self.ui.suggest_button.clicked.connect(self.show_suggestions_modal)
        self.ui.name_input.textChanged.connect(self.ui_controller.update_unsaved_changes_indicator)
        self.ui.description_input.textChanged.connect(self.ui_controller.update_unsaved_changes_indicator)
        self.ui.labels_input.textChanged.connect(self.ui_controller.update_unsaved_changes_indicator)
        self.ui.tags_input.textChanged.connect(self.ui_controller.update_unsaved_changes_indicator)
        self.ui.properties_table.itemChanged.connect(self.ui_controller.update_unsaved_changes_indicator)
        self.ui.relationships_table.itemChanged.connect(self.ui_controller.update_unsaved_changes_indicator)
        self.ui.depth_spinbox.valueChanged.connect(self.tree_controller.on_depth_changed)

    def show_suggestions_modal(self) -> None:
        node_data = self.node_operations_controller._collect_node_data()
        if not node_data:
            return

        self.ui.show_loading(True)

        if self.current_suggestion_worker:
            self.current_suggestion_worker.cancel()
            self.current_suggestion_worker.wait()
            self.current_suggestion_worker = None
            logging.debug("Existing SuggestionWorker canceled and cleaned up.")

        self.current_suggestion_worker = SuggestionWorker(
            self.model._uri, self.model._auth, node_data
        )
        self.current_suggestion_worker.suggestions_ready.connect(
            self.handle_suggestions
        )
        self.current_suggestion_worker.error_occurred.connect(self.handle_error)
        self.current_suggestion_worker.finished.connect(
            self.on_suggestion_worker_finished
        )
        self.current_suggestion_worker.start()

        logging.debug("SuggestionWorker started successfully.")

    def on_suggestion_worker_finished(self) -> None:
        self.current_suggestion_worker = None
        self.ui.show_loading(False)
        logging.debug("SuggestionWorker has finished and cleaned up.")

    def handle_suggestions(self, suggestions: Dict[str, Any]) -> None:
        logging.debug(f"handle_suggestions called with suggestions: {suggestions}")
        self.ui.show_loading(False)
        logging.debug("Loading indicator hidden.")

        if not suggestions or all(not suggestions[key] for key in suggestions):
            logging.debug("No suggestions found.")
            QMessageBox.information(
                self.ui, "No Suggestions", "No suggestions were found for this node."
            )
            return

        dialog = SuggestionDialog(suggestions, self.ui)
        if dialog.exec():
            selected = dialog.selected_suggestions
            logging.debug(f"User selected suggestions: {selected}")

            existing_tags = self.node_operations_controller._parse_comma_separated(self.ui.tags_input.text())
            new_tags = list(set(existing_tags + selected["tags"]))
            self.ui.tags_input.setText(", ".join(new_tags))
            logging.debug(f"Updated tags: {new_tags}")

            for key, value in selected["properties"].items():
                self.add_or_update_property(key, value)
                logging.debug(f"Updated property - Key: {key}, Value: {value}")

            for rel in selected["relationships"]:
                rel_type, target, direction, props = rel
                self.ui.add_relationship_row(
                    rel_type, target, direction, json.dumps(props)
                )
                logging.debug(
                    f"Added relationship - Type: {rel_type}, Target: {target}, Direction: {direction}, Properties: {props}"
                )

            QMessageBox.information(
                self.ui,
                "Suggestions Applied",
                "Selected suggestions have been applied to the node.",
            )
        else:
            logging.debug("Suggestion dialog was canceled by the user.")

    def add_or_update_property(self, key: str, value: Any) -> None:
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

    def handle_error(self, error_message: str) -> None:
        logging.error(error_message)
        QMessageBox.critical(self.ui, "Error", error_message)

    def load_last_modified_node(self) -> None:
        try:
            last_modified_node = self.model.get_last_modified_node()
            if last_modified_node:
                self.ui.name_input.setText(last_modified_node["name"])
                self.node_operations_controller.load_node_data()
            else:
                logging.info("No nodes available to load.")
        except Exception as e:
            self.handle_error(f"Error loading last modified node: {e}")

    def open_connection_settings(self):
        dialog = ConnectionSettingsDialog(self.config, self.app_instance)
        dialog.exec()
