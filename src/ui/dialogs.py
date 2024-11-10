from typing import Dict, List, Tuple, Any

from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QTabWidget,
    QDialogButtonBox,
    QWidget,
    QCheckBox,
    QLabel,
    QHBoxLayout,
    QGroupBox,
    QLineEdit,
)


class SuggestionDialogOld(QDialog):
    def __init__(self, suggestions: Dict[str, Any], parent: QWidget = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Suggested Node Information")
        self.setModal(True)
        self.suggestions = suggestions
        self.selected_suggestions: Dict[str, Any] = {
            "tags": [],
            "properties": {},
            "relationships": [],
        }
        self.init_ui()

    def init_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Tabs for Tags, Properties, Relationships
        self.tabs = QTabWidget()
        self.tabs.addTab(self._create_tags_tab(), "Tags")
        self.tabs.addTab(self._create_properties_tab(), "Properties")
        self.tabs.addTab(self._create_relationships_tab(), "Relationships")

        # Action buttons
        button_box = button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)

        layout.addWidget(self.tabs)
        layout.addWidget(button_box)

    def _create_tags_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        self.tags_checkboxes: List[Tuple[QCheckBox, str]] = []
        for tag, confidence in self.suggestions.get("tags", []):
            checkbox = QCheckBox(f"{tag}")
            confidence_label = QLabel(f"Confidence: {confidence:.2f}%")
            h_layout = QHBoxLayout()
            h_layout.addWidget(checkbox)
            h_layout.addWidget(confidence_label)
            self.tags_checkboxes.append((checkbox, tag))
            layout.addLayout(h_layout)

        return widget

    def _create_properties_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        self.properties_checkboxes: List[Tuple[QCheckBox, str, QLineEdit]] = []
        for key, values in self.suggestions.get("properties", {}).items():
            group_box = QGroupBox(f"Property: {key}")
            v_layout = QVBoxLayout()
            for value, confidence in values:
                checkbox = QCheckBox("Value:")
                value_edit = QLineEdit(str(value))
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

    def _create_relationships_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        self.relationships_checkboxes: List[
            Tuple[QCheckBox, str, str, str, Dict[str, Any]]
        ] = []
        for rel_type, target, direction, props, confidence in self.suggestions.get(
            "relationships", []
        ):
            checkbox = QCheckBox(f"{direction} {rel_type} -> {target}")
            confidence_label = QLabel(f"Confidence: {confidence:.2f}%")
            h_layout = QHBoxLayout()
            h_layout.addWidget(checkbox)
            h_layout.addWidget(confidence_label)
            self.relationships_checkboxes.append(
                (checkbox, rel_type, target, direction, props)
            )
            layout.addLayout(h_layout)

        return widget

    def accept(self) -> None:
        # Collect selected tags
        for checkbox, tag in self.tags_checkboxes:
            if checkbox.isChecked():
                self.selected_suggestions["tags"].append(tag)

        # Collect selected properties
        for checkbox, key, value_edit in self.properties_checkboxes:
            if checkbox.isChecked():
                # Get the current text from the QLineEdit when accepting
                self.selected_suggestions["properties"][key] = value_edit.text()

        # Collect selected relationships
        for (
            checkbox,
            rel_type,
            target,
            direction,
            props,
        ) in self.relationships_checkboxes:
            if checkbox.isChecked():
                self.selected_suggestions["relationships"].append(
                    (rel_type, target, direction, props)
                )

        super().accept()


class SuggestionDialog(QDialog):
    def __init__(self, suggestions: Dict[str, Any], parent: QWidget = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Node Suggestions")
        self.setModal(True)
        self.suggestions = suggestions
        self.selected_suggestions: Dict[str, Any] = {
            "tags": [],
            "properties": {},
            "relationships": [],
        }

        # Constants for visual indicators
        self.PATTERN_INDICATORS = {
            "statistical": "📊",  # Statistical pattern
            "creative": "💡",  # Creative suggestion
            "bridge": "🌉",  # Cross-domain connection
        }

        self.init_ui()

    def init_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Info label at top
        info_label = QLabel(
            "Suggestions are based on pattern analysis and creative connections. "
            "📊 Statistical patterns • 💡 Creative suggestions • 🌉 Cross-domain connections"
        )
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        # Tabs for different suggestion types
        self.tabs = QTabWidget()
        self.tabs.addTab(self._create_tags_tab(), "Tags")
        self.tabs.addTab(self._create_properties_tab(), "Properties")
        self.tabs.addTab(self._create_relationships_tab(), "Relationships")
        layout.addWidget(self.tabs)

        # Action buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def _create_suggestion_item(
        self, text: str, confidence: float, suggestion_type: str
    ) -> QWidget:
        """Create a suggestion item with visual indicator and confidence"""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)

        # Add indicator
        indicator = QLabel(self.PATTERN_INDICATORS.get(suggestion_type, ""))
        layout.addWidget(indicator)

        # Checkbox with suggestion
        checkbox = QCheckBox(text)
        layout.addWidget(checkbox)

        # Confidence display
        confidence_label = QLabel(f"{confidence:.1f}%")
        confidence_label.setStyleSheet(self._get_confidence_style(confidence))
        layout.addWidget(confidence_label)

        return widget, checkbox

    def _get_confidence_style(self, confidence: float) -> str:
        """Get color style based on confidence level"""
        if confidence >= 80:
            return "color: green;"
        elif confidence >= 50:
            return "color: #707000;"  # Dark yellow
        return "color: #A07000;"  # Orange-ish

    def _create_tags_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Group tags by type
        statistical_tags = [
            (t, c) for t, c in self.suggestions.get("tags", []) if c >= 70
        ]
        creative_tags = [(t, c) for t, c in self.suggestions.get("tags", []) if c < 70]

        self.tags_checkboxes = []

        # Add statistical patterns
        if statistical_tags:
            group = QGroupBox("Common Patterns")
            group_layout = QVBoxLayout()
            for tag, confidence in statistical_tags:
                item, checkbox = self._create_suggestion_item(
                    tag, confidence, "statistical"
                )
                self.tags_checkboxes.append((checkbox, tag))
                group_layout.addWidget(item)
            group.setLayout(group_layout)
            layout.addWidget(group)

        # Add creative suggestions
        if creative_tags:
            group = QGroupBox("Creative Suggestions")
            group_layout = QVBoxLayout()
            for tag, confidence in creative_tags:
                item, checkbox = self._create_suggestion_item(
                    tag, confidence, "creative"
                )
                self.tags_checkboxes.append((checkbox, tag))
                group_layout.addWidget(item)
            group.setLayout(group_layout)
            layout.addWidget(group)

        layout.addStretch()
        return widget

    def _create_properties_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        self.properties_checkboxes = []

        for key, values in self.suggestions.get("properties", {}).items():
            group = QGroupBox(f"Property: {key}")
            group_layout = QVBoxLayout()

            for value, confidence in values:
                # Create property item with edit field
                item = QWidget()
                item_layout = QHBoxLayout(item)
                item_layout.setContentsMargins(0, 0, 0, 0)

                # Add appropriate indicator based on confidence
                suggestion_type = "statistical" if confidence >= 70 else "creative"
                indicator = QLabel(self.PATTERN_INDICATORS[suggestion_type])
                item_layout.addWidget(indicator)

                # Checkbox and value edit
                checkbox = QCheckBox("Value:")
                value_edit = QLineEdit(str(value))

                item_layout.addWidget(checkbox)
                item_layout.addWidget(value_edit)

                # Confidence label
                confidence_label = QLabel(f"{confidence:.1f}%")
                confidence_label.setStyleSheet(self._get_confidence_style(confidence))
                item_layout.addWidget(confidence_label)

                group_layout.addWidget(item)
                self.properties_checkboxes.append((checkbox, key, value_edit))

            group.setLayout(group_layout)
            layout.addWidget(group)

        layout.addStretch()
        return widget

    def _create_relationships_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        self.relationships_checkboxes = []

        # Group relationships by type
        statistical_rels = []
        creative_rels = []
        bridge_rels = []

        for rel_type, target, direction, props, confidence in self.suggestions.get(
            "relationships", []
        ):
            rel_data = (rel_type, target, direction, props, confidence)
            if confidence >= 70:
                statistical_rels.append(rel_data)
            elif any(p.get("bridge", False) for p in props.values()):
                bridge_rels.append(rel_data)
            else:
                creative_rels.append(rel_data)

        # Add statistical patterns
        if statistical_rels:
            group = QGroupBox("Common Patterns")
            group_layout = QVBoxLayout()
            self._add_relationship_items(group_layout, statistical_rels, "statistical")
            group.setLayout(group_layout)
            layout.addWidget(group)

        # Add bridge connections
        if bridge_rels:
            group = QGroupBox("Cross-Domain Connections")
            group_layout = QVBoxLayout()
            self._add_relationship_items(group_layout, bridge_rels, "bridge")
            group.setLayout(group_layout)
            layout.addWidget(group)

        # Add creative suggestions
        if creative_rels:
            group = QGroupBox("Creative Suggestions")
            group_layout = QVBoxLayout()
            self._add_relationship_items(group_layout, creative_rels, "creative")
            group.setLayout(group_layout)
            layout.addWidget(group)

        layout.addStretch()
        return widget

    def _add_relationship_items(
        self, layout: QVBoxLayout, relationships: List[Tuple], rel_type: str
    ) -> None:
        """Add relationship items to the given layout"""
        for rel_type, target, direction, props, confidence in relationships:
            text = f"{direction} {rel_type} -> {target}"
            item, checkbox = self._create_suggestion_item(text, confidence, rel_type)
            self.relationships_checkboxes.append(
                (checkbox, rel_type, target, direction, props)
            )
            layout.addWidget(item)

    def accept(self) -> None:
        """Process selected suggestions when OK is clicked"""
        # Collect selected tags
        self.selected_suggestions["tags"] = [
            tag for checkbox, tag in self.tags_checkboxes if checkbox.isChecked()
        ]

        # Collect selected properties
        self.selected_suggestions["properties"] = {
            key: value_edit.text()
            for checkbox, key, value_edit in self.properties_checkboxes
            if checkbox.isChecked()
        }

        # Collect selected relationships
        self.selected_suggestions["relationships"] = [
            (rel_type, target, direction, props)
            for checkbox, rel_type, target, direction, props in self.relationships_checkboxes
            if checkbox.isChecked()
        ]

        super().accept()
