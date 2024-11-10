from PyQt6.QtWidgets import QDialog, QVBoxLayout, QTabWidget, QDialogButtonBox, QWidget, QCheckBox, \
    QLabel, QHBoxLayout, QGroupBox, QLineEdit


class SuggestionDialog(QDialog):
    def __init__(self, suggestions, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Suggested Node Information")
        self.setModal(True)
        self.suggestions = suggestions
        self.selected_suggestions = {
            'tags': [],
            'properties': {},
            'relationships': []
        }
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        # Tabs for Tags, Properties, Relationships
        self.tabs = QTabWidget()
        self.tabs.addTab(self._create_tags_tab(), "Tags")
        self.tabs.addTab(self._create_properties_tab(), "Properties")
        self.tabs.addTab(self._create_relationships_tab(), "Relationships")

        # Action buttons
        button_box = button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)

        layout.addWidget(self.tabs)
        layout.addWidget(button_box)

    def _create_tags_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)

        self.tags_checkboxes = []
        for tag, confidence in self.suggestions.get('tags', []):
            checkbox = QCheckBox(f"{tag}")
            confidence_label = QLabel(f"Confidence: {confidence:.2f}%")
            h_layout = QHBoxLayout()
            h_layout.addWidget(checkbox)
            h_layout.addWidget(confidence_label)
            self.tags_checkboxes.append((checkbox, tag))
            layout.addLayout(h_layout)

        return widget

    def _create_properties_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)

        self.properties_checkboxes = []
        for key, values in self.suggestions.get('properties', {}).items():
            group_box = QGroupBox(f"Property: {key}")
            v_layout = QVBoxLayout()
            for value, confidence in values:
                checkbox = QCheckBox("Value:")
                value_edit = QLineEdit(value)
                confidence_label = QLabel(f"Confidence: {confidence:.2f}%")
                h_layout = QHBoxLayout()
                h_layout.addWidget(checkbox)
                h_layout.addWidget(value_edit)
                h_layout.addWidget(confidence_label)
                v_layout.addLayout(h_layout)
                # Store the QLineEdit widget instead of its value
                self.properties_checkboxes.append((checkbox, key, value_edit))
            group_box.setLayout(v_layout)
            layout.addWidget(group_box)

        return widget

    def _create_relationships_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)

        self.relationships_checkboxes = []
        for rel_type, target, direction, props, confidence in self.suggestions.get('relationships', []):
            checkbox = QCheckBox(f"{direction} {rel_type} -> {target}")
            confidence_label = QLabel(f"Confidence: {confidence:.2f}%")
            h_layout = QHBoxLayout()
            h_layout.addWidget(checkbox)
            h_layout.addWidget(confidence_label)
            self.relationships_checkboxes.append((checkbox, rel_type, target, direction, props))
            layout.addLayout(h_layout)

        return widget

    def accept(self):
        # Collect selected tags
        for checkbox, tag in self.tags_checkboxes:
            if checkbox.isChecked():
                self.selected_suggestions['tags'].append(tag)

        # Collect selected properties
        for checkbox, key, value_edit in self.properties_checkboxes:
            if checkbox.isChecked():
                # Get the current text from the QLineEdit when accepting
                self.selected_suggestions['properties'][key] = value_edit.text()

        # Collect selected relationships
        for checkbox, rel_type, target, direction, props in self.relationships_checkboxes:
            if checkbox.isChecked():
                self.selected_suggestions['relationships'].append(
                    (rel_type, target, direction, props)
                )

        super().accept()
