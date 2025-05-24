from typing import Dict, Any, Set, List

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QCheckBox,
    QVBoxLayout,
    QWidget,
    QLabel,
    QHBoxLayout,
    QDialogButtonBox,
    QGroupBox,
    QScrollArea,
    QLineEdit,
    QTableWidget,
    QHeaderView,
    QTableWidgetItem,
)

from ui.components.fast_inject_component.property_value_widget import (
    PropertyValueWidget,
)


class FastInjectDialog(QDialog):
    """Dialog for previewing Fast Inject template contents with selective application."""

    def __init__(self, template: Dict[str, Any], parent=None) -> None:
        super().__init__(parent)
        self.template = template
        self.setWindowTitle(f"Fast Inject Preview - {template['name']}")
        self.setModal(True)
        self.setMinimumWidth(800)
        self.setMinimumHeight(600)

        # Track selected items
        self.selected_labels: Set[str] = set(template["content"]["labels"])
        self.selected_tags: Set[str] = set(template["content"]["tags"])
        self.selected_properties: Set[str] = set(
            template["content"]["properties"].keys()
        )
        self.modified_property_values: Dict[str, str] = {}
        self.property_checkboxes: Dict[str, QCheckBox] = {}

        self.init_ui()

    def init_ui(self) -> None:
        main_layout = QVBoxLayout(self)

        # Header section with template info
        header_widget = QWidget()
        header_layout = QVBoxLayout(header_widget)
        header_layout.setSpacing(5)

        name_label = QLabel(f"<b>{self.template['name']}</b>")
        name_label.setStyleSheet("font-size: 14px;")

        desc_label = QLabel(self.template["description"])
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("color: #666;")

        header_layout.addWidget(name_label)
        header_layout.addWidget(desc_label)
        main_layout.addWidget(header_widget)

        # Create horizontal layout for labels and tags
        top_section = QWidget()
        top_layout = QHBoxLayout(top_section)
        top_layout.setSpacing(10)

        # Labels section (left side)
        labels_group = self._create_labels_group()
        labels_group.setMaximumHeight(150)
        top_layout.addWidget(labels_group)

        # Tags section (right side)
        tags_group = self._create_tags_group()
        tags_group.setMaximumHeight(150)
        top_layout.addWidget(tags_group)

        main_layout.addWidget(top_section)

        # Properties section (expanded)
        props_group = self._create_properties_group()
        main_layout.addWidget(props_group, stretch=1)  # Give properties more space

        # Note about existing properties
        note_label = QLabel("<i>Note: Existing properties will not be overwritten</i>")
        note_label.setStyleSheet("color: #666; padding: 5px;")
        main_layout.addWidget(note_label)

        # Dialog buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        main_layout.addWidget(button_box)

    def _create_labels_group(self) -> QGroupBox:
        """Create compact labels group."""
        group = QGroupBox("Labels")
        layout = QVBoxLayout()
        layout.setSpacing(2)

        # Select All checkbox
        select_all = QCheckBox("Select All")
        select_all.setChecked(True)
        layout.addWidget(select_all)

        # Create scrollable area for labels
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        labels_widget = QWidget()
        labels_layout = QVBoxLayout(labels_widget)
        labels_layout.setSpacing(1)
        labels_layout.setContentsMargins(0, 0, 0, 0)

        # Individual label checkboxes
        label_checkboxes: List[QCheckBox] = []
        for label in self.template["content"]["labels"]:
            checkbox = QCheckBox(label)
            checkbox.setChecked(True)
            checkbox.stateChanged.connect(
                lambda state, l=label: self._update_label_selection(l, state)
            )
            labels_layout.addWidget(checkbox)
            label_checkboxes.append(checkbox)

        labels_layout.addStretch()
        scroll.setWidget(labels_widget)

        # Connect select all functionality
        select_all.stateChanged.connect(
            lambda state: self._toggle_all_labels(state, label_checkboxes)
        )

        layout.addWidget(scroll)
        group.setLayout(layout)
        return group

    def _create_tags_group(self) -> QGroupBox:
        """Create compact tags group."""
        group = QGroupBox("Tags")
        layout = QVBoxLayout()
        layout.setSpacing(2)

        # Select All checkbox
        select_all = QCheckBox("Select All")
        select_all.setChecked(True)
        layout.addWidget(select_all)

        # Create scrollable area for tags
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        tags_widget = QWidget()
        tags_layout = QVBoxLayout(tags_widget)
        tags_layout.setSpacing(1)
        tags_layout.setContentsMargins(0, 0, 0, 0)

        # Individual tag checkboxes
        tag_checkboxes: List[QCheckBox] = []
        for tag in self.template["content"]["tags"]:
            checkbox = QCheckBox(tag)
            checkbox.setChecked(True)
            checkbox.stateChanged.connect(
                lambda state, t=tag: self._update_tag_selection(t, state)
            )
            tags_layout.addWidget(checkbox)
            tag_checkboxes.append(checkbox)

        tags_layout.addStretch()
        scroll.setWidget(tags_widget)

        # Connect select all functionality
        select_all.stateChanged.connect(
            lambda state: self._toggle_all_tags(state, tag_checkboxes)
        )

        layout.addWidget(scroll)
        group.setLayout(layout)
        return group

    def _create_properties_group(self) -> QGroupBox:
        """Create expanded properties group with enhanced table."""
        group = QGroupBox("Properties")
        layout = QVBoxLayout()
        layout.setSpacing(5)

        # Header controls
        header_widget = QWidget()
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(0, 0, 0, 5)

        select_all = QCheckBox("Select All Properties")
        select_all.setChecked(True)
        header_layout.addWidget(select_all)

        filter_input = QLineEdit()
        filter_input.setPlaceholderText("Filter properties...")
        filter_input.textChanged.connect(self._filter_properties)
        header_layout.addWidget(filter_input)

        layout.addWidget(header_widget)

        # Create table
        props = self.template["content"]["properties"]
        self.props_table = QTableWidget(len(props), 3)
        self.props_table.setHorizontalHeaderLabels(["Select", "Property", "Value"])

        self.props_table.verticalHeader().setVisible(False)
        header = self.props_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.props_table.setColumnWidth(0, 50)
        self.props_table.setColumnWidth(1, 300)

        # Track value widgets for properties
        self.property_value_widgets: Dict[str, PropertyValueWidget] = {}

        for i, (key, value) in enumerate(props.items()):
            # Checkbox column with centered container
            checkbox = QCheckBox()
            checkbox.setChecked(True)
            checkbox.stateChanged.connect(
                lambda state, k=key: self._update_property_selection(k, state)
            )
            self.property_checkboxes[key] = checkbox

            # Create a container widget to center the checkbox
            container = QWidget()
            container_layout = QHBoxLayout(container)
            container_layout.setContentsMargins(0, 0, 0, 0)
            container_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            container_layout.addWidget(checkbox)

            self.props_table.setCellWidget(i, 0, container)

            # Property name column
            name_item = QTableWidgetItem(key)
            name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.props_table.setItem(i, 1, name_item)

            # Value column with PropertyValueWidget
            value_widget = PropertyValueWidget(value)
            self.property_value_widgets[key] = value_widget
            self.props_table.setCellWidget(i, 2, value_widget)

        # Connect select all functionality
        select_all.stateChanged.connect(
            lambda state: self._toggle_all_properties(state)
        )

        layout.addWidget(self.props_table)
        group.setLayout(layout)
        return group

    def _filter_properties(self, text: str) -> None:
        """Filter properties table based on search text."""
        search_text = text.lower()
        for row in range(self.props_table.rowCount()):
            property_name = self.props_table.item(row, 1).text().lower()
            property_value = self.props_table.item(row, 2).text().lower()
            matches = search_text in property_name or search_text in property_value
            self.props_table.setRowHidden(row, not matches)

    def _on_property_value_changed(self, item: QTableWidgetItem) -> None:
        """Handle property value changes in the table."""
        if item.column() == 2:  # Value column
            prop_name = self.props_table.item(item.row(), 1).text()
            self.modified_property_values[prop_name] = item.text()

    def get_selected_properties_with_values(self) -> Dict[str, str]:
        """Get selected properties with their potentially modified values."""
        result = {}
        for prop_name in self.selected_properties:
            if widget := self.property_value_widgets.get(prop_name):
                result[prop_name] = widget.get_value()
        return result

    def _update_label_selection(self, label: str, state: int) -> None:
        """Update the selected labels set based on checkbox state."""
        if state == Qt.CheckState.Checked.value:
            self.selected_labels.add(label)
        else:
            self.selected_labels.discard(label)

    def _update_tag_selection(self, tag: str, state: int) -> None:
        """Update the selected tags set based on checkbox state."""
        if state == Qt.CheckState.Checked.value:
            self.selected_tags.add(tag)
        else:
            self.selected_tags.discard(tag)

    def _update_property_selection(self, prop: str, state: int) -> None:
        """Update the selected properties set based on checkbox state."""
        if state == Qt.CheckState.Checked.value:
            self.selected_properties.add(prop)
        else:
            self.selected_properties.discard(prop)

    def _toggle_all_labels(self, state: int, checkboxes: List[QCheckBox]) -> None:
        """Toggle all label checkboxes."""
        for checkbox in checkboxes:
            checkbox.setChecked(state == Qt.CheckState.Checked.value)

    def _toggle_all_tags(self, state: int, checkboxes: List[QCheckBox]) -> None:
        """Toggle all tag checkboxes."""
        for checkbox in checkboxes:
            checkbox.setChecked(state == Qt.CheckState.Checked.value)

    def _toggle_all_properties(self, state: int) -> None:
        """Toggle all property checkboxes."""
        checked = state == Qt.CheckState.Checked.value
        for checkbox in self.property_checkboxes.values():
            checkbox.setChecked(checked)
