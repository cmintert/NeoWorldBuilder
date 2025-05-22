import json
from typing import Optional, Set, Dict, Any

from PyQt6.QtCore import pyqtSignal, Qt, QPoint, QTimer
from PyQt6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QSplitter,
    QVBoxLayout,
    QTreeView,
    QLabel,
    QSpinBox,
    QProgressBar,
    QTabWidget,
    QLineEdit,
    QPushButton,
    QFormLayout,
    QGroupBox,
    QTableWidget,
    QMenu,
    QHeaderView,
    QMessageBox,
    QTableWidgetItem,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QApplication,
)
from structlog import get_logger

from ui.components.calendar_component.calendar_tab import CalendarTab
from ui.components.image_group import ImageGroup
from ui.components.map_component.map_tab import MapTab
from ui.components.search_component.search_panel import SearchPanel
from ui.components.text_editor.text_editor import TextEditor
from ui.components.timeline_component.timeline_tab import TimelineTab

logger = get_logger(__name__)


class WorldBuilderTreeView(QTreeView):
    """Custom tree view that handles right-click without selection."""

    def __init__(self, parent=None):
        super().__init__(parent)
        # Set up for context menu support but handle press ourselves
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

    def mousePressEvent(self, event):
        """Override to prevent selection on right click."""
        if event.button() == Qt.MouseButton.RightButton:
            # Explicitly don't handle right click
            return

        # Handle all other mouse events normally
        super().mousePressEvent(event)


class WorldBuildingUI(QWidget):

    # Class-level signals
    name_selected = pyqtSignal(str)
    refresh_requested = pyqtSignal()

    def __init__(self, controller: "WorldBuildingController") -> None:
        """
        Initialize the UI with the given controller.

        Args:
            controller (WorldBuildingController): The controller managing the UI.
        """
        super().__init__()
        self.controller = controller
        self.map_tab = None
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setObjectName("WorldBuildingContent")
        self.setAttribute(
            Qt.WidgetAttribute.WA_StyledBackground, True
        )  # Important for QSS styling
        self.setAttribute(
            Qt.WidgetAttribute.WA_TranslucentBackground, True
        )  # Allow transparency

        self._signals_connected = False

        self._create_ui_elements()

    def _create_ui_elements(self) -> None:
        """Create all UI elements without connecting signals"""
        main_layout = QHBoxLayout()
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(20)

        # Create splitter for resizable panels
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left panel with search and tree
        left_panel = self._create_left_panel()
        splitter.addWidget(left_panel)

        # Right panel with node details and progress
        right_panel = self._create_right_panel()
        splitter.addWidget(right_panel)

        # Search panel
        self.search_panel = SearchPanel()
        splitter.addWidget(self.search_panel)

        main_layout.addWidget(splitter)
        self.setLayout(main_layout)

    def _connect_signals(self) -> None:
        """Connect all UI signals to their handlers"""

        # Check for unsaved changes
        self.name_input.textChanged.connect(
            self.controller.update_unsaved_changes_indicator
        )
        self.description_input.textChanged.connect(
            self.controller.update_unsaved_changes_indicator
        )
        self.labels_input.textChanged.connect(
            self.controller.update_unsaved_changes_indicator
        )
        self.tags_input.textChanged.connect(
            self.controller.update_unsaved_changes_indicator
        )
        self.properties_table.itemChanged.connect(
            self.controller.update_unsaved_changes_indicator
        )
        self.relationships_table.itemChanged.connect(
            self.controller.update_unsaved_changes_indicator
        )

        self.description_input.enhancementRequested.connect(
            lambda: self.controller.enhance_node_description()
        )

        # Depth spinbox change
        self.depth_spinbox.valueChanged.connect(self.controller.on_depth_changed)

        # Tree view
        self.tree_view.customContextMenuRequested.connect(self._show_tree_context_menu)

        # FastInject
        self.fast_inject_button.clicked.connect(self.controller.handle_fast_inject)

    def setup_ui(self) -> None:
        """Connect signals and finalize UI setup after controller is set"""
        if not self.controller:
            raise RuntimeError("Controller must be set before initializing UI")

        if not self._signals_connected:
            # Connect image group signals only once
            self.image_group.basic_image_changed.connect(
                self.controller.change_basic_image
            )
            self.image_group.basic_image_removed.connect(
                self.controller.delete_basic_image
            )

            # Connect all signals
            self._connect_signals()
            self._signals_connected = True

        # Apply styles
        self.apply_styles()

    def _update_timeline_tab_visibility(self, should_show_timeline: bool) -> None:
        """Update timeline tab visibility."""
        if should_show_timeline:
            self._ensure_timeline_tab_exists()
        else:
            self._remove_timeline_tab_if_exists()

    def _ensure_timeline_tab_exists(self) -> None:
        """Create and configure timeline tab if it doesn't exist."""
        if not hasattr(self, "timeline_tab") or not self.timeline_tab:
            self.timeline_tab = TimelineTab(controller=self.controller)
            self.tabs.addTab(self.timeline_tab, "Timeline")

    def _remove_timeline_tab_if_exists(self) -> None:
        """Remove timeline tab if it exists."""
        if hasattr(self, "timeline_tab") and self.timeline_tab:
            timeline_tab_index = self.tabs.indexOf(self.timeline_tab)
            if timeline_tab_index != -1:
                self.tabs.removeTab(timeline_tab_index)
                self.timeline_tab = None

    def show_loading(self, is_loading: bool) -> None:
        """
        Show or hide loading state for the UI.

        Args:
            is_loading (bool): Whether the UI is in loading state.
        """
        self.save_button.setEnabled(not is_loading)
        self.delete_button.setEnabled(not is_loading)
        self.cancel_button.setVisible(is_loading)
        self.name_input.setReadOnly(is_loading)
        self.suggest_button.setEnabled(not is_loading)
        if is_loading:
            self.progress_bar.setVisible(True)
            self.progress_bar.setRange(0, 0)  # Indeterminate progress
        else:
            self.progress_bar.setVisible(False)

    def _create_left_panel(self) -> QWidget:
        """
        Create improved left panel with tree view and search.

        Returns:
            QWidget: The left panel widget.
        """
        panel = QWidget()
        panel.setObjectName("leftPanel")
        panel.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)

        layout = QVBoxLayout(panel)
        layout.setObjectName("leftPanelLayout")
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Enhanced tree view
        self.tree_view = WorldBuilderTreeView()
        self.tree_view.setObjectName("treeView")

        self.tree_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        panel.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.tree_view.customContextMenuRequested.connect(self._show_tree_context_menu)

        layout.addWidget(self.tree_view)

        # Depth selector

        depth_layout = QHBoxLayout()
        depth_layout.setObjectName("depthLayout")

        depth_label = QLabel("Relationship Depth:")
        depth_label.setObjectName("depthLabel")

        self.depth_spinbox = QSpinBox()
        self.depth_spinbox.setObjectName("depthSpinBox")

        self.depth_spinbox.setFixedWidth(70)
        self.depth_spinbox.setFixedHeight(40)
        self.depth_spinbox.setMinimum(1)
        self.depth_spinbox.setMaximum(3)
        self.depth_spinbox.setValue(1)

        depth_layout.addWidget(depth_label)
        depth_layout.addWidget(self.depth_spinbox)
        depth_layout.addStretch()

        layout.addLayout(depth_layout)

        return panel

    def _create_right_panel(self) -> QWidget:
        """
        Create improved right panel with proper spacing and opacity.

        Returns:
            QWidget: The right panel widget.
        """
        panel = QWidget()
        panel.setObjectName("rightPanel")

        layout = QVBoxLayout(panel)
        layout.setObjectName("rightPanelLayout")
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(15)

        # Header with node name and actions
        header_widget = QWidget()
        header_widget.setObjectName("headerWidget")
        header_layout = self._create_header_layout()
        header_widget.setLayout(header_layout)
        layout.addWidget(header_widget)

        # Progress bar (initially hidden)
        self.progress_bar = QProgressBar()
        self.progress_bar.setObjectName("progressBar")
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # Tabs
        self.tabs = QTabWidget()
        self.tabs.setObjectName("mainTabs")
        self.tabs.addTab(self._create_basic_info_tab(), "Basic Info")
        self.tabs.addTab(self._create_relationships_tab(), "Relationships")
        self.tabs.addTab(self._create_properties_tab(), "Properties")

        # Add label change monitoring
        self.labels_input.textChanged.connect(self._handle_label_changes)

        layout.addWidget(self.tabs)

        # Suggest button
        self.suggest_button = QPushButton("Suggest additional Node Data")
        self.suggest_button.setObjectName("suggestButton")
        self.suggest_button.setFixedWidth(250)
        self.suggest_button.setMinimumHeight(30)
        button_layout = QHBoxLayout()
        button_layout.setObjectName("suggestButtonLayout")
        button_layout.addStretch()
        button_layout.addWidget(self.suggest_button)
        button_layout.addStretch()

        # Fast Inject button
        self.fast_inject_button = QPushButton("Fast Inject Template")
        self.fast_inject_button.setObjectName("fastInjectButton")
        self.fast_inject_button.setFixedWidth(250)
        self.fast_inject_button.setMinimumHeight(30)
        button_layout.addWidget(self.fast_inject_button)

        layout.addLayout(button_layout)

        return panel

    def _create_header_layout(self) -> QHBoxLayout:
        """
        Create enhanced header with loading indication.

        Returns:
            QHBoxLayout: The header layout.
        """
        layout = QHBoxLayout()

        # Node name input
        self.name_input = QLineEdit()
        self.name_input.setObjectName("nameInput")
        self.name_input.setPlaceholderText("Enter node name...")
        self.name_input.setMinimumHeight(35)
        self.name_input.setMaxLength(100)

        self.name_input.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.name_input.customContextMenuRequested.connect(self._show_name_context_menu)

        # Action buttons with loading states
        self.save_button = QPushButton("💾 Save")
        self.save_button.setObjectName("saveButton")
        self.save_button.setShortcut("Ctrl+S")
        self.save_button.setToolTip("Ctrl+S")

        self.delete_button = QPushButton("🗑️ Delete")
        self.delete_button.setObjectName("deleteButton")
        self.cancel_button = QPushButton("⚠️ Cancel")
        self.cancel_button.setObjectName("cancelButton")
        self.cancel_button.setVisible(False)

        # Style buttons
        for button in [self.save_button, self.delete_button, self.cancel_button]:
            button.setMinimumHeight(35)
            button.setFixedWidth(100)

        layout.addWidget(self.name_input, stretch=1)
        layout.addWidget(self.save_button)
        layout.addWidget(self.delete_button)
        layout.addWidget(self.cancel_button)

        return layout

    def _create_basic_info_tab(self) -> QWidget:
        """
        Create the basic info tab with input fields and image handling.

        Returns:
            QWidget: The basic info tab widget.
        """
        tab = QWidget()
        tab.setObjectName("basicInfoTab")
        main_layout = QHBoxLayout(tab)
        main_layout.setObjectName("basicInfoLayout")
        form_layout = QFormLayout()
        form_layout.setObjectName("basicInfoFormLayout")
        form_layout.setSpacing(15)

        # Description
        self.description_input = TextEditor(main_ui=self)

        self.description_input.setObjectName("descriptionEditor")

        # Labels with auto-completion
        self.labels_input = QLineEdit()
        self.labels_input.setObjectName("labelsInput")
        self.labels_input.setPlaceholderText("Enter labels (comma-separated)")
        self.labels_input.setToolTip("Labels help categorize nodes. Keep to a minimum.")

        # Tags
        self.tags_input = QLineEdit()
        self.tags_input.setObjectName("tagsInput")
        self.tags_input.setPlaceholderText("Enter tags (comma-separated)")
        self.tags_input.setToolTip(
            "Tags are used to cluster nodes based on common themes or attributes."
        )

        # Image section
        image_group = self._create_image_group()

        form_layout.addRow("Description:", self.description_input)
        form_layout.addRow("Labels:", self.labels_input)
        form_layout.addRow("Tags:", self.tags_input)

        main_layout.addLayout(form_layout)
        main_layout.addWidget(image_group)

        return tab

    def _create_image_group(self) -> QGroupBox:
        """Create the image display group."""
        self.image_group = ImageGroup()

        return self.image_group

    def _create_relationships_tab(self) -> QWidget:
        """
        Create relationships tab with table.

        Returns:
            QWidget: The relationships tab widget.
        """
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Add relationship button
        self.add_rel_button = QPushButton("➕ Add Relationship")
        self.add_rel_button.setObjectName("addRelationshipButton")
        self.add_rel_button.setFixedWidth(150)
        self.add_rel_button.setMinimumHeight(30)

        # Enhanced table
        self.relationships_table = QTableWidget(0, 5)
        self.relationships_table.setObjectName("relationshipsTable")
        self.relationships_table.setAlternatingRowColors(True)
        self.relationships_table.verticalHeader().setVisible(False)

        # Set up columns
        self._setup_relationships_table_columns()

        layout.addWidget(self.add_rel_button)
        layout.addWidget(self.relationships_table)

        return tab

    def _create_properties_tab(self) -> QWidget:
        """
        Create properties tab with table.

        Returns:
            QWidget: The properties tab widget.
        """
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Add property button
        self.add_prop_button = QPushButton("➕ Add Property")
        self.add_prop_button.setObjectName("addPropertyButton")
        self.add_prop_button.clicked.connect(
            lambda checked=False: self.add_property_row(self.properties_table)
        )
        self.add_prop_button.setFixedWidth(150)
        self.add_prop_button.setMinimumHeight(30)

        # Enhanced table
        self.properties_table = QTableWidget(0, 3)
        self.properties_table.setObjectName("propertiesTable")
        self.properties_table.setAlternatingRowColors(True)
        self.properties_table.verticalHeader().setVisible(False)

        # Set up columns
        self._setup_properties_table_columns(self.properties_table)

        layout.addWidget(self.add_prop_button)
        layout.addWidget(self.properties_table)
        return tab

    def _show_tree_context_menu(self, position: QPoint) -> None:
        """
        Show context menu for tree items.

        Args:
            position (QPoint): The position where the context menu should appear.
        """
        menu = QMenu()

        # Add actions based on selected item
        expand_action = menu.addAction("Expand All")
        collapse_action = menu.addAction("Collapse All")
        refresh_action = menu.addAction("Refresh")

        # Execute menu and handle selection
        action = menu.exec(self.tree_view.mapToGlobal(position))
        if action == expand_action:
            self.tree_view.expandAll()
        elif action == collapse_action:
            self.tree_view.collapseAll()
        elif action == refresh_action:
            self.refresh_requested.emit()

    def create_delete_button(self, table: QTableWidget, row: int) -> QWidget:
        """
        Create a centered delete button for table rows.

        Args:
            table (QTableWidget): The table to which the button will be added.
            row (int): The row number where the button will be placed.

        Returns:
            QWidget: The container widget with the delete button.
        """
        # Create container widget for centering
        container = QWidget()
        container.setObjectName("deleteButtonContainer")
        layout = QHBoxLayout(container)
        layout.setObjectName("deleteButtonLayout")
        layout.setContentsMargins(4, 0, 4, 0)  # Small horizontal margins for spacing
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Create the delete button
        button = QPushButton("-")
        button.setObjectName("rowDeleteButton")
        button.setFixedWidth(20)
        button.setFixedHeight(20)
        button.clicked.connect(lambda: table.removeRow(row))

        # Add button to container
        layout.addWidget(button)

        return container

    def _setup_relationships_table_columns(self) -> None:
        """
        Set up relationships table columns with proper sizing.
        """
        self.relationships_table.setColumnCount(6)
        self.relationships_table.setHorizontalHeaderLabels(
            ["Type", "Related Node", "Direction", "Properties", " ", " "]
        )

        # Set relationships table column behaviors
        header = self.relationships_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)  # Type
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)  # Related Node
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)  # Direction
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)  # Properties
        header.setSectionResizeMode(
            4, QHeaderView.ResizeMode.Fixed
        )  # Delete button column
        header.setSectionResizeMode(
            5, QHeaderView.ResizeMode.Fixed
        )  # Edit button column

        # Set fixed widths for specific columns
        self.relationships_table.setColumnWidth(2, 60)  # Direction column
        self.relationships_table.setColumnWidth(4, 38)  # Delete button column
        self.relationships_table.setColumnWidth(5, 120)  # Edit button column

    def _setup_properties_table_columns(self, table: QTableWidget) -> None:
        """
        Set up properties table columns with proper sizing.

        Args:
            table (QTableWidget): The properties table widget.
        """
        table.setColumnCount(3)
        table.setHorizontalHeaderLabels(["Key", "Value", ""])

        table.verticalHeader().setVisible(False)

        # Set properties table column behaviors
        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)  # Key
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)  # Value
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)  # Delete button

        # Set fixed width for delete button column
        table.setColumnWidth(2, 38)  # Delete button column

    #############################################
    # UI Update Methods
    #############################################

    def clear_all_fields(self) -> None:
        """
        Clear all input fields except the name_input.
        """
        self.description_input.clear()
        self.labels_input.clear()
        self.tags_input.clear()
        self.properties_table.setRowCount(0)
        self.relationships_table.setRowCount(0)
        self.image_group.set_basic_image(None)

        self._remove_map_tab_if_exists()

    def _remove_map_tab_if_exists(self) -> None:
        """Remove the map tab if it exists and clear the reference."""
        if self.map_tab:
            map_tab_index = self.tabs.indexOf(self.map_tab)
            if map_tab_index != -1:
                self.tabs.removeTab(map_tab_index)
            self.map_tab = None

    def set_image(self, image_path: Optional[str]) -> None:
        """Set image with proper scaling and error handling."""
        self.image_group.set_basic_image(image_path)

    def add_relationship_row(
        self,
        rel_type: str = "",
        target: str = "",
        direction: str = ">",
        properties: str = "",
    ) -> None:
        """
        Add relationship row with improved validation.

        Args:
            rel_type (str): The type of the relationship.
            target (str): The target node of the relationship.
            direction (str): The direction of the relationship. Defaults to ">".
            properties (str): The properties of the relationship in JSON format.
        """
        row = self.relationships_table.rowCount()
        self.relationships_table.insertRow(row)

        # Type with validation
        type_item = QTableWidgetItem(rel_type)

        self.relationships_table.setItem(row, 0, type_item)

        # Target with completion
        target_item = QTableWidgetItem(target)

        self.relationships_table.setItem(row, 1, target_item)
        self.controller._add_target_completer_to_row(row)

        # Direction ComboBox
        direction_combo = QComboBox()

        direction_combo.addItems([">", "<"])
        direction_combo.setCurrentText(direction)
        self.relationships_table.setCellWidget(row, 2, direction_combo)

        # Properties with validation
        props_item = QTableWidgetItem(properties)

        props_item.setBackground(Qt.GlobalColor.lightGray)
        props_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.relationships_table.setItem(row, 3, props_item)

        # Add a centered delete button
        delete_button = self.create_delete_button(self.relationships_table, row)
        self.relationships_table.setCellWidget(row, 4, delete_button)

        # Add 'Edit Properties' button
        edit_properties_button = QPushButton("Edit Properties")
        edit_properties_button.setObjectName("editPropertiesButton")
        edit_properties_button.clicked.connect(
            lambda: self.open_relation_properties_dialog(row)
        )
        self.relationships_table.setCellWidget(row, 5, edit_properties_button)

    def add_property_row(self, table: QTableWidget) -> None:
        """
        Add property row with centered delete button.

        Args:
            table (QTableWidget): The properties table widget.
        """
        row = table.rowCount()
        table.insertRow(row)

        # Add a centered delete button
        delete_button = self.create_delete_button(table, row)
        table.setCellWidget(row, 2, delete_button)

    def apply_styles(self) -> None:
        """Apply styles to UI components with enhanced error checking."""
        try:
            print("\nStarting style application...")

            if not self.controller:
                raise RuntimeError("Controller not initialized when applying styles")

            style_manager = self.controller.style_manager

            # First, apply the default style to the applicationstyle_manager
            print("Applying default style to application")
            if app := QApplication.instance():
                style_manager.apply_style(app, "default")

            # Then apply styles to specific components
            components = [
                (self, "default", "Main Widget"),
                (self.tree_view, "tree", "Tree View"),
                (self.properties_table, "data-table", "Properties Table"),
                (self.relationships_table, "data-table", "Relationships Table"),
                (self.search_panel, "default", "Search Panel"),
            ]

            for widget, style, name in components:
                print(f"\nApplying {style} style to {name}")
                if not widget:
                    print(f"Warning: {name} widget is None")
                    continue

                if not widget.objectName():
                    widget.setObjectName(name.replace(" ", ""))

                # Ensure stylesheet processing is enabled
                widget.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

                # Apply the style
                style_manager.apply_style(widget, style)

                # Verify style application
                if not widget.styleSheet():
                    print(f"Warning: No stylesheet applied to {name}")
                else:
                    print(f"Successfully applied style to {name}")

            print("\nStyle application completed")

        except Exception as e:
            print(f"Error during style application: {str(e)}")
            import traceback

            traceback.print_exc()
            QMessageBox.warning(
                self, "Style Error", f"Failed to apply styles: {str(e)}"
            )

    def open_relation_properties_dialog(self, row: int) -> None:
        """
        Open a dialog to edit relationship properties.

        Args:
            row (int): The row number of the relationship.
        """
        dialog = QDialog(self)
        dialog.setWindowTitle("Edit Relationship Properties")
        dialog.setModal(True)
        dialog.setMinimumWidth(600)

        layout = QVBoxLayout(dialog)
        layout.ObjectName = "RelPropLayout"

        # Add property button
        add_prop_button = QPushButton("➕ Add Property")
        add_prop_button.setObjectName("addRelPropertyButton")
        add_prop_button.clicked.connect(
            lambda checked=False: self.add_property_row(rel_properties_table)
        )
        add_prop_button.setFixedWidth(150)
        add_prop_button.setMinimumHeight(30)

        layout.addWidget(add_prop_button)

        # Create properties table
        rel_properties_table = QTableWidget(0, 3)
        rel_properties_table.setObjectName("relPropertiesTable")
        rel_properties_table.setHorizontalHeaderLabels(["Key", "Value", ""])
        rel_properties_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        layout.addWidget(rel_properties_table)

        self._setup_properties_table_columns(rel_properties_table)

        if properties_json := self.relationships_table.item(row, 3).text():
            properties = json.loads(properties_json)
            for key, value in properties.items():
                rel_properties_table.insertRow(rel_properties_table.rowCount())
                key_item = QTableWidgetItem(key)
                key_item.setBackground(Qt.GlobalColor.lightGray)
                key_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                value_item = QTableWidgetItem(value)
                value_item.setBackground(Qt.GlobalColor.lightGray)
                value_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                rel_properties_table.setItem(
                    rel_properties_table.rowCount() - 1, 0, key_item
                )
                rel_properties_table.setItem(
                    rel_properties_table.rowCount() - 1, 1, value_item
                )

                # Add a delete button
                delete_button = self.create_delete_button(
                    rel_properties_table, rel_properties_table.rowCount() - 1
                )
                rel_properties_table.setCellWidget(
                    rel_properties_table.rowCount() - 1, 2, delete_button
                )

        # Add buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(
            lambda: self.set_relationship_properties(row, rel_properties_table, dialog)
        )
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)

        dialog.exec()

    def set_relationship_properties(
        self, row: int, properties_table: QTableWidget, dialog: QDialog
    ) -> None:
        """
        Set relationship properties from the dialog.

        Args:
            row (int): The row number of the relationship.
            properties_table (QTableWidget): The properties table widget.
            dialog (QDialog): The dialog widget.
        """
        properties = {}
        for i in range(properties_table.rowCount()):
            key = properties_table.item(i, 0).text()
            value = properties_table.item(i, 1).text()
            if key in properties:
                QMessageBox.warning(
                    self,
                    "Duplicate Key",
                    f"Duplicate key '{key}' found. Please ensure all keys are unique.",
                )
                return
            properties[key] = value

        properties_json = json.dumps(properties)
        self.relationships_table.item(row, 3).setText(properties_json)
        dialog.accept()

    def _handle_label_changes(self) -> None:
        """
        Handle changes to labels and update tab visibility.

        Updates the map tab and calendar tab visibility based on whether the respective
        labels ('Map' or 'Calendar') are present in the entity's labels. Creates or
        removes tabs and manages associated properties as needed.
        """
        try:
            if not self._can_handle_label_changes():
                return

            current_labels = self._get_normalized_labels()

            # Handle Map tab
            self._update_map_tab_visibility("MAP" in current_labels)

            # Handle Calendar tab
            has_calendar = "CALENDAR" in current_labels
            if has_calendar:
                self._ensure_calendar_tab_exists()
                # Initialize calendar data after properties are populated
                QTimer.singleShot(100, self._initialize_calendar_data)
            else:
                self._remove_calendar_tab_if_exists()

            # Handle Event tab
            self._update_event_tab_visibility("EVENT" in current_labels)

            # Handle Timeline tab
            self._update_timeline_tab_visibility("TIMELINE" in current_labels)

        except Exception as e:
            self._handle_tab_error(e)

    def _initialize_calendar_data(self) -> None:
        """Initialize calendar data after ensuring properties are loaded."""
        if hasattr(self, "calendar_tab") and self.calendar_tab:
            raw_props = self._get_raw_calendar_properties()
            logger.debug("Got raw calendar properties", raw_props=raw_props)
            self.calendar_tab.initialize_calendar_data(raw_props)

    def _update_calendar_tab_visibility(self, should_show_calendar: bool) -> None:
        """Update calendar tab visibility and manage associated resources.

        Args:
            should_show_calendar (bool): Whether the calendar tab should be visible
        """
        if should_show_calendar:
            self._ensure_calendar_tab_exists()
        else:
            self._remove_calendar_tab_if_exists()

    def _ensure_calendar_tab_exists(self) -> None:
        """Create and configure calendar tab if it doesn't exist."""
        if not hasattr(self, "calendar_tab") or not self.calendar_tab:
            logger.debug("creating_calendar_tab", widget_id=self.objectName())
            self.calendar_tab = CalendarTab(controller=self.controller)
            self.calendar_tab.calendar_changed.connect(self._handle_calendar_changed)
            self.tabs.addTab(self.calendar_tab, "Calendar")
            raw_props = self._get_raw_calendar_properties()
            if raw_props:
                QTimer.singleShot(
                    100, lambda: self.calendar_tab.initialize_calendar_data(raw_props)
                )

    def _remove_calendar_tab_if_exists(self) -> None:
        """Remove calendar tab if it exists."""
        if hasattr(self, "calendar_tab") and self.calendar_tab:
            calendar_tab_index = self.tabs.indexOf(self.calendar_tab)
            if calendar_tab_index != -1:
                self.tabs.removeTab(calendar_tab_index)
                self.calendar_tab = None
                logger.info("calendar_tab_removed", widget_id=self.objectName())

    def _add_calendar_property(self, key: str, value: str) -> None:
        """Add a calendar property to the properties table."""
        try:
            row = self.properties_table.rowCount()
            self.properties_table.insertRow(row)
            self.properties_table.setItem(row, 0, QTableWidgetItem(key))
            self.properties_table.setItem(row, 1, QTableWidgetItem(value))
            delete_button = self.create_delete_button(self.properties_table, row)
            self.properties_table.setCellWidget(row, 2, delete_button)
        except Exception as e:
            logger.error("calendar_property_add_failed", key=key, error=str(e))

    def _get_raw_calendar_properties(self) -> Dict[str, str]:
        """Get raw calendar properties from table."""
        properties = {}
        for row in range(self.properties_table.rowCount()):
            key_item = self.properties_table.item(row, 0)
            value_item = self.properties_table.item(row, 1)
            if key_item and value_item and key_item.text().startswith("calendar_"):
                properties[key_item.text()] = value_item.text().strip()
        return properties

    def setup_calendar_data(self) -> None:
        """Load calendar data from flat properties."""
        logger.debug(
            "Starting calendar data setup",
            has_calendar_tab=bool(self.calendar_tab),
            has_raw_props=bool(self._get_raw_calendar_properties()),
        )

        if not self.calendar_tab or not self._get_raw_calendar_properties():
            return

        try:
            raw_props = self._get_raw_calendar_properties()
            logger.debug("Raw calendar properties", raw_props=raw_props)
            calendar_data = {}

            # Known types for each property
            list_props = {"month_names", "month_days", "weekday_names"}
            int_props = {"current_year", "year_length", "days_per_week"}

            for key, value in raw_props.items():
                # Remove calendar_ prefix
                clean_key = key.replace("calendar_", "")

                logger.debug(
                    "Processing property",
                    original_key=key,
                    clean_key=clean_key,
                    original_value=value,
                )

                try:
                    if clean_key in list_props:
                        # Handle list properties by properly parsing the string representation
                        try:
                            # Use ast.literal_eval to safely evaluate the string representation of list
                            import ast

                            parsed_list = ast.literal_eval(value)
                            if clean_key == "month_days":
                                # Ensure all values are integers for month_days
                                calendar_data[clean_key] = [int(x) for x in parsed_list]
                            else:
                                # Keep as strings for other list properties
                                calendar_data[clean_key] = [str(x) for x in parsed_list]
                        except (ValueError, SyntaxError) as e:
                            # Fallback to simple comma splitting if literal_eval fails
                            items = [
                                x.strip()
                                for x in value.strip("[]").split(",")
                                if x.strip()
                            ]
                            if clean_key == "month_days":
                                calendar_data[clean_key] = [int(x) for x in items]
                            else:
                                calendar_data[clean_key] = items

                    elif clean_key in int_props:
                        # Handle integers
                        calendar_data[clean_key] = int(value)
                    else:
                        # Handle strings
                        calendar_data[clean_key] = value.strip()

                except Exception as conversion_error:
                    logger.error(
                        "Property conversion failed",
                        key=clean_key,
                        value=value,
                        error=str(conversion_error),
                    )
                    raise

            logger.debug("Final calendar data structure", calendar_data=calendar_data)
            self.calendar_tab.set_calendar_data(calendar_data)

        except Exception as e:
            logger.error(
                "calendar_setup_failed", error=str(e), error_type=type(e).__name__
            )

    def _get_calendar_data(self) -> Optional[Dict[str, Any]]:
        """Get current calendar data for events"""
        try:
            raw_props = {}
            for row in range(self.properties_table.rowCount()):
                key_item = self.properties_table.item(row, 0)
                value_item = self.properties_table.item(row, 1)
                if key_item and value_item and key_item.text().startswith("calendar_"):
                    raw_props[key_item.text().replace("calendar_", "")] = (
                        value_item.text().strip()
                    )

            if raw_props:
                return raw_props

        except Exception as e:
            logger.error("Failed to get calendar data", error=str(e))

        return None

    def _handle_calendar_changed(self, calendar_data: Dict[str, Any]) -> None:
        """Store calendar data as flat properties."""
        try:
            self._clear_calendar_properties()
            for key, value in calendar_data.items():
                self._add_calendar_property(f"calendar_{key}", json.dumps(value))
            self.controller.update_unsaved_changes_indicator()
        except Exception as e:
            logger.error("calendar_update_failed", error=str(e))

    def _clear_calendar_properties(self) -> None:
        """Remove all existing calendar properties."""
        row = 0
        while row < self.properties_table.rowCount():
            if key_item := self.properties_table.item(row, 0):
                if key_item.text().startswith("calendar_"):
                    self.properties_table.removeRow(row)
                    continue
            row += 1

    def _handle_event_changed(self, event_data: Dict[str, Any]) -> None:
        """Handle changes to event data"""
        try:
            # Update properties
            logger.debug("Updating event data", event_data=event_data)
            self._set_property_value("event_type", event_data["event_type"])
            self._set_property_value("temporal_data", event_data["temporal_data"])

            for key in event_data:
                if "parsed_date_" in key:
                    logger.debug("Parsed property", key=key, value=event_data[key])
                    logger.debug("-" * 20)
                    self._set_property_value(key, event_data[key])

            if event_data["relative_to"]:
                self._set_property_value("event_relative_to", event_data["relative_to"])
            else:
                self._remove_property("event_relative_to")

            # Update save state
            self.controller.update_unsaved_changes_indicator()

        except Exception as e:
            logger.error("event_update_failed", error=str(e))

    def _handle_tab_error(self, error: Exception) -> None:
        """Handle errors related to tab management.

        Args:
            error: The error that occurred
        """
        logger.error(
            "tab_error",
            error=str(error),
            widget_id=self.objectName(),
            module="world_building_ui",
            function="_handle_label_changes",
        )

        if hasattr(self, "controller"):
            self.controller.error_handler.handle_error(
                f"Error updating specialized tabs: {str(error)}"
            )

    def _can_handle_label_changes(self) -> bool:
        """
        Check if the UI is ready to handle label changes.

        Returns:
            bool: True if tabs attribute exists, False otherwise.
        """
        return hasattr(self, "tabs")

    def _get_normalized_labels(self) -> Set[str]:
        """
        Get normalized set of labels from the input field.

        Returns:
            Set[str]: Set of normalized label strings.
        """
        return {
            label.strip()
            for label in self.labels_input.text().split(",")
            if label.strip()
        }

    def _update_map_tab_visibility(self, should_show_map: bool) -> None:
        """
        Update map tab visibility and manage associated resources.

        Args:
            should_show_map (bool): Whether the map tab should be visible.
        """
        if should_show_map:
            self._ensure_map_tab_exists()
        else:
            self._remove_map_tab_if_exists()

    def _update_event_tab_visibility(self, should_show_event: bool) -> None:
        """Update event tab visibility and manage associated resources"""
        if should_show_event:
            self._ensure_event_tab_exists()
        else:
            self._remove_event_tab_if_exists()

    def _ensure_map_tab_exists(self) -> None:
        """Create and configure map tab if it doesn't exist."""
        if not hasattr(self, "map_tab") or not self.map_tab:
            logger.debug("creating_map_tab", widget_id=self.objectName())
            self.map_tab = MapTab(controller=self.controller)
            self.map_tab.map_image_changed.connect(self._handle_map_image_changed)
            self.map_tab.pin_created.connect(self._handle_pin_created)
            self.tabs.addTab(self.map_tab, "Map")

            # Set initial map image if available in properties
            map_image_path = self._get_property_value("mapimage")
            if map_image_path:
                self.map_tab.set_map_image(map_image_path)
                logger.info(
                    "map_image_loaded", path=map_image_path, widget_id=self.objectName()
                )

    def _ensure_event_tab_exists(self) -> None:
        """Create and configure event tab if it doesn't exist"""
        if not hasattr(self, "event_tab") or not self.event_tab:
            logger.debug("creating_event_tab", widget_id=self.objectName())
            from ui.components.event_component.event_tab import EventTab

            self.event_tab = EventTab(controller=self.controller)
            self.event_tab.event_changed.connect(self._handle_event_changed)
            self.tabs.addTab(self.event_tab, "Event")

            # Set initial data if available
            self.setup_event_data()

    def _remove_map_tab_if_exists(self) -> None:
        """Remove map tab if it exists."""
        if hasattr(self, "map_tab") and self.map_tab:
            map_tab_index = self.tabs.indexOf(self.map_tab)
            if map_tab_index != -1:
                self.tabs.removeTab(map_tab_index)
                self.map_tab = None
                logger.info("map_tab_removed", widget_id=self.objectName())

    def _remove_event_tab_if_exists(self) -> None:
        """Remove event tab if it exists"""
        if hasattr(self, "event_tab") and self.event_tab:
            event_tab_index = self.tabs.indexOf(self.event_tab)
            if event_tab_index != -1:
                self.tabs.removeTab(event_tab_index)
                self.event_tab = None
                logger.info("event_tab_removed", widget_id=self.objectName())

    def _handle_map_tab_error(self, error: Exception) -> None:
        """
        Handle errors related to map tab management.

        Args:
            error (Exception): The error that occurred.
        """
        logger.error(
            "map_tab_error",
            error=str(error),
            widget_id=self.objectName(),
            module="world_building_ui",
            function="_handle_label_changes",
        )

        if hasattr(self, "controller"):
            self.controller.error_handler.handle_error(
                f"Error updating map tab: {str(error)}"
            )

    def _handle_map_image_changed(self, image_path: str) -> None:
        """Handle changes to the map image path."""
        # Directly update all_props in controller
        self.controller.all_props["mapimage"] = image_path

        # Trigger unsaved changes update
        self.controller.update_unsaved_changes_indicator()

    def _get_property_value(self, key: str) -> Optional[str]:
        """Get a property value from the properties table."""
        for row in range(self.properties_table.rowCount()):
            if self.properties_table.item(row, 0).text() == key:
                return self.properties_table.item(row, 1).text()
        return None

    def _set_property_value(self, key: str, value: str) -> None:
        """Set a property value in the properties table."""
        logger.debug("Setting property value", key=key, value=value)

        # Look for existing property
        for row in range(self.properties_table.rowCount()):

            if self.properties_table.item(row, 0).text() == key:
                self.properties_table.item(row, 1).setText(value)
                return

        # Add new property if not found
        logger.debug("Adding as new property")
        row = self.properties_table.rowCount()
        self.properties_table.insertRow(row)
        self.properties_table.setItem(row, 0, QTableWidgetItem(key))
        self.properties_table.setItem(row, 1, QTableWidgetItem(value))
        delete_button = self.create_delete_button(self.properties_table, row)
        self.properties_table.setCellWidget(row, 2, delete_button)

    def _handle_pin_created(
        self, target: str, direction: str, properties: dict
    ) -> None:
        """Handle creation of new pin relationship."""
        self.add_relationship_row(
            rel_type="SHOWS",
            target=target,
            direction=direction,
            properties=json.dumps(properties),
        )

    def _show_name_context_menu(self, position: QPoint) -> None:
        """Show context menu for name input field."""
        # Only show rename option if we have a node loaded
        if not self.controller.current_node_element_id:
            return

        # Create standard context menu with default actions
        menu = self.name_input.createStandardContextMenu()

        # Add rename option if we have a node loaded
        if self.controller.current_node_element_id:
            menu.addSeparator()
            rename_action = menu.addAction("Rename Node")
            rename_action.triggered.connect(self.show_rename_dialog)

        menu.exec(self.name_input.mapToGlobal(position))

    def show_rename_dialog(self) -> None:
        """Show dialog for renaming node."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Rename Node")
        dialog.setModal(True)

        layout = QVBoxLayout(dialog)

        # Add name input
        name_input = QLineEdit(dialog)
        name_input.setText(self.name_input.text())
        name_input.setPlaceholderText("Enter new name...")
        layout.addWidget(name_input)

        # Add buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(
            lambda: self._handle_rename_dialog(name_input.text(), dialog)
        )
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)

        dialog.exec()

    def _handle_rename_dialog(self, new_name: str, dialog: QDialog) -> None:
        """Handle rename dialog acceptance."""
        if new_name.strip():
            self.controller.rename_node(new_name)
            dialog.accept()

    def setup_event_data(self) -> None:
        """Load event data from properties"""
        if not self.event_tab:
            return

        # Get event properties
        event_data = {
            "event_type": self._get_property_value("event_type") or "Occurrence",
            "temporal_data": self._get_property_value("temporal_data"),
            "parsed_temporal_data": self._get_property_value("parsed_temporal_data"),
            "calendar_id": self._get_property_value("calendar_id"),
            "description": self._get_property_value("event_description"),
            "relative_to": self._get_property_value("event_relative_to"),
        }

        # Get active calendar data
        calendar_data = self._get_calendar_data()
        if calendar_data:
            self.event_tab.set_calendar_data(calendar_data, "default")

        # Load data into UI
        self.event_tab.set_event_data(event_data)

    def _remove_property(self, key: str) -> None:
        """Remove a property from the properties table"""
        for row in range(self.properties_table.rowCount()):
            if self.properties_table.item(row, 0).text() == key:
                self.properties_table.removeRow(row)
                return
