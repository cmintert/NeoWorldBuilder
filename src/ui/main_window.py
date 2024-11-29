import json
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import pyqtSignal, Qt, QPoint
from PyQt6.QtGui import QPixmap, QAction, QFont
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
    QTextEdit,
    QGroupBox,
    QTableWidget,
    QMenu,
    QHeaderView,
    QMessageBox,
    QTableWidgetItem,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QToolBar,
    QApplication,
)

from ui.styles import StyleManager


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

        self.style_manager = StyleManager(Path("src/config/styles"))

        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setObjectName("CentralWidget")
        self.setAttribute(
            Qt.WidgetAttribute.WA_StyledBackground, True
        )  # Important for QSS styling
        self.setAttribute(
            Qt.WidgetAttribute.WA_TranslucentBackground, True
        )  # Allow transparency

        self._create_ui_elements()

    def init_ui(self) -> None:
        """
        Initialize the main UI layout with enhanced components.
        """
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

        # Set stretch factors
        splitter.setStretchFactor(0, 1)  # Left panel
        splitter.setStretchFactor(1, 2)  # Right panel gets more space

        main_layout.addWidget(splitter)
        self.setLayout(main_layout)

        # Apply styles
        self.apply_styles()

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

        # Set stretch factors
        splitter.setStretchFactor(0, 1)  # Left panel
        splitter.setStretchFactor(1, 2)  # Right panel gets more space

        main_layout.addWidget(splitter)
        self.setLayout(main_layout)

    def _connect_signals(self) -> None:
        """Connect all UI signals to their handlers"""
        # Main buttons
        self.save_button.clicked.connect(self.controller.save_node)
        self.delete_button.clicked.connect(self.controller.delete_node)

        # Image handling
        self.change_image_button.clicked.connect(self.controller.change_image)
        self.delete_image_button.clicked.connect(self.controller.delete_image)

        # Name input
        self.name_input.editingFinished.connect(self.controller.load_node_data)

        # Table buttons
        self.add_rel_button.clicked.connect(self.add_relationship_row)

        # connect the suggest button
        self.suggest_button.clicked.connect(self.controller.show_suggestions_modal)

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

        # Depth spinbox change
        self.depth_spinbox.valueChanged.connect(self.controller.on_depth_changed)

        # Tree view
        self.tree_view.customContextMenuRequested.connect(self._show_tree_context_menu)

    def setup_ui(self) -> None:
        """Connect signals and finalize UI setup after controller is set"""
        if not self.controller:
            raise RuntimeError("Controller must be set before initializing UI")

        # Connect all signals
        self._connect_signals()

        # Apply styles
        self.apply_styles()

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
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Enhanced tree view
        self.tree_view = QTreeView()
        self.tree_view.setObjectName("treeView")
        self.tree_view.setHeaderHidden(True)
        self.tree_view.setAnimated(True)
        self.tree_view.setAlternatingRowColors(True)
        self.tree_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree_view.customContextMenuRequested.connect(self._show_tree_context_menu)

        layout.addWidget(self.tree_view)

        # Depth selector

        depth_layout = QHBoxLayout()
        depth_label = QLabel("Relationship Depth:")
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

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(15)

        # Header with node name and actions
        header_widget = QWidget()
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

        layout.addWidget(self.tabs)

        # Suggest button
        self.suggest_button = QPushButton("Suggest additional Node Data")
        self.suggest_button.setObjectName("suggestButton")
        self.suggest_button.setFixedWidth(250)
        self.suggest_button.setMinimumHeight(30)
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(self.suggest_button)
        button_layout.addStretch()

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
        main_layout = QHBoxLayout(tab)
        form_layout = QFormLayout()
        form_layout.setSpacing(15)

        # Description
        self.description_input = QTextEdit()
        self.description_input.setObjectName("descriptionInput")
        self.description_input.setPlaceholderText("Enter description...")
        self.description_input.setMinimumHeight(100)

        # Add formatting toolbar
        self.formatting_toolbar = self._create_formatting_toolbar()

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

        form_layout.addRow("", self.formatting_toolbar)
        form_layout.addRow("Description:", self.description_input)
        form_layout.addRow("Labels:", self.labels_input)
        form_layout.addRow("Tags:", self.tags_input)

        main_layout.addLayout(form_layout)
        main_layout.addWidget(image_group)

        return tab

    def _create_formatting_toolbar(self) -> QToolBar:
        """
        Create the formatting toolbar with rich text options.

        Returns:
            QToolBar: The formatting toolbar.
        """
        toolbar = QToolBar("Formatting")
        toolbar.setObjectName("formattingToolbar")
        toolbar.setFixedHeight(24)

        # Add actions for formatting
        self._add_formatting_action(
            toolbar, "H1", lambda: self._set_heading(1), shortcut="Ctrl+1"
        )
        self._add_formatting_action(
            toolbar, "H2", lambda: self._set_heading(2), shortcut="Ctrl+2"
        )
        self._add_formatting_action(
            toolbar, "H3", lambda: self._set_heading(3), shortcut="Ctrl+3"
        )
        self._add_formatting_action(toolbar, "Body", self._set_body, shortcut="Ctrl+0")
        self._add_formatting_action(
            toolbar, "Bold", self._set_bold, checkable=True, shortcut="Ctrl+B"
        )
        self._add_formatting_action(
            toolbar, "Italic", self._set_italic, checkable=True, shortcut="Ctrl+I"
        )
        self._add_formatting_action(
            toolbar, "Underline", self._set_underline, checkable=True, shortcut="Ctrl+U"
        )

        return toolbar

    def _add_formatting_action(
        self,
        toolbar: QToolBar,
        text: str,
        slot: callable,
        checkable: bool = False,
        shortcut: Optional[str] = None,
    ) -> None:
        """
        Add a formatting action to the toolbar.

        Args:
            toolbar (QToolBar): The toolbar to add the action to.
            text (str): The text for the action.
            slot (callable): The slot to connect the action to.
            checkable (bool): Whether the action is checkable. Defaults to False.
        """
        action = QAction(text, self)
        action.setCheckable(checkable)
        action.triggered.connect(slot)

        # Set the shortcut if provided
        if shortcut:
            action.setShortcut(shortcut)
            action.setShortcutVisibleInContextMenu(True)

        toolbar.addAction(action)
        self.addAction(action)

    def _set_heading1(self) -> None:
        """
        Set the selected text to heading 1.
        """
        self._set_heading(1)

    def _set_heading2(self) -> None:
        """
        Set the selected text to heading 2.
        """
        self._set_heading(2)

    def _set_heading3(self) -> None:
        """
        Set the selected text to heading 3.
        """
        self._set_heading(3)

    def _set_heading(self, level: int) -> None:
        """
        Set the selected text to the specified heading level.

        Args:
            level (int): The heading level (1, 2, or 3).
        """
        cursor = self.description_input.textCursor()
        cursor.beginEditBlock()

        # Adjust font size and weight for heading levels
        font = cursor.charFormat().font()
        if level == 1:
            font.setPointSize(16)  # Large size for H1
            font.setWeight(QFont.Weight.Bold)  # Bold weight
        elif level == 2:
            font.setPointSize(14)  # Medium size for H2
            font.setWeight(QFont.Weight.Medium)  # Medium weight
        elif level == 3:
            font.setPointSize(12)  # Smaller size for H3
            font.setWeight(QFont.Weight.Normal)  # Normal weight

        # Apply the font changes
        char_format = cursor.charFormat()
        char_format.setFont(font)
        cursor.setCharFormat(char_format)

        cursor.endEditBlock()

    def _set_body(self) -> None:
        """
        Reset the selected text to standard body text formatting.
        """
        cursor = self.description_input.textCursor()
        cursor.beginEditBlock()

        # Create a standard font
        standard_font = QFont()
        standard_font.setPointSize(10)  # Default font size
        standard_font.setWeight(QFont.Weight.Normal)  # Default weight

        # Apply the standard font to the selected text
        char_format = cursor.charFormat()
        char_format.setFont(standard_font)
        char_format.setFontItalic(False)
        char_format.setFontUnderline(False)
        cursor.setCharFormat(char_format)

        cursor.endEditBlock()

    def _set_bold(self) -> None:
        """
        Toggle bold formatting for the selected text.
        """
        self._toggle_format("bold")

    def _set_italic(self) -> None:
        """
        Toggle italic formatting for the selected text.
        """
        self._toggle_format("italic")

    def _set_underline(self) -> None:
        """
        Toggle underline formatting for the selected text.
        """
        self._toggle_format("underline")

    def _toggle_format(self, format_type: str) -> None:
        """
        Toggle the specified format for the selected text.

        Args:
            format_type (str): The format type ('bold', 'italic', 'underline').
        """
        cursor = self.description_input.textCursor()
        cursor.beginEditBlock()

        char_format = cursor.charFormat()
        if format_type == "bold":
            char_format.setFontWeight(
                QFont.Weight.Bold
                if char_format.fontWeight() != QFont.Weight.Bold
                else QFont.Weight.Normal
            )
        elif format_type == "italic":
            char_format.setFontItalic(not char_format.fontItalic())
        elif format_type == "underline":
            char_format.setFontUnderline(not char_format.fontUnderline())

        cursor.setCharFormat(char_format)
        cursor.endEditBlock()

    def _create_image_group(self) -> QGroupBox:
        """
        Create the image display group.

        Returns:
            QGroupBox: The image group box.
        """
        group = QGroupBox("Image")
        group.setObjectName("imageGroupBox")
        layout = QVBoxLayout()

        group.setFixedWidth(220)
        group.setFixedHeight(300)

        # Image display
        self.image_label = QLabel()
        self.image_label.setObjectName("imageLabel")
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setFixedSize(200, 200)

        layout.addWidget(self.image_label)

        # Image buttons
        button_layout = QHBoxLayout()
        button_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.change_image_button = QPushButton("Change")
        self.change_image_button.setObjectName("changeImageButton")
        self.delete_image_button = QPushButton("Remove")
        self.delete_image_button.setObjectName("deleteImageButton")

        for button in [self.change_image_button, self.delete_image_button]:
            button.setFixedWidth(97)
            button.setMinimumHeight(30)

        button_layout.addWidget(self.change_image_button)
        button_layout.addWidget(self.delete_image_button)
        button_layout.addStretch()
        layout.addLayout(button_layout)

        group.setLayout(layout)
        return group

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
        action = menu.exec_(self.tree_view.mapToGlobal(position))
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
        layout = QHBoxLayout(container)
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
    # Progress and Status Methods
    #############################################

    def show_progress(self, visible: bool = True) -> None:
        """
        Show or hide progress bar.

        Args:
            visible (bool): Whether to show the progress bar. Defaults to True.
        """
        self.progress_bar.setVisible(visible)
        if visible:
            self.progress_bar.setValue(0)

    def set_progress(self, value: int, maximum: int = 100) -> None:
        """
        Update progress bar.

        Args:
            value (int): The current progress value.
            maximum (int): The maximum progress value. Defaults to 100.
        """
        self.progress_bar.setMaximum(maximum)
        self.progress_bar.setValue(value)

    def set_status(self, message: str) -> None:
        """
        Update status message.

        Args:
            message (str): The status message to display.
        """
        self.status_label.setText(message)

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
        self.image_label.clear()

    def set_image(self, image_path: Optional[str]) -> None:
        """
        Set image with proper scaling and error handling.

        Args:
            image_path (Optional[str]): The path to the image file.
        """
        if not image_path:
            self.image_label.clear()
            return

        try:
            pixmap = QPixmap(image_path)
            if pixmap.isNull():
                raise ValueError("Failed to load image")
            scaled_pixmap = pixmap.scaled(
                self.image_label.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.image_label.setPixmap(scaled_pixmap)
        except Exception as e:
            self.image_label.clear()
            QMessageBox.warning(self, "Image Error", f"Failed to load image: {str(e)}")

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

            # First, apply the default style to the application
            print("Applying default style to application")
            if app := QApplication.instance():
                self.style_manager.apply_style(app, "default")

            # Then apply styles to specific components
            components = [
                (self, "default", "Main Widget"),
                (self.tree_view, "tree", "Tree View"),
                (self.properties_table, "data-table", "Properties Table"),
                (self.relationships_table, "data-table", "Relationships Table"),
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
                self.style_manager.apply_style(widget, style)

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


class ConnectionSettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Manage Connection Settings")
        self.layout = QVBoxLayout()

        self.uri_input = QLineEdit(self)
        self.username_input = QLineEdit(self)
        self.password_input = QLineEdit(self)
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)

        self.test_button = QPushButton("Test Connection", self)
        self.save_button = QPushButton("Save", self)

        self.layout.addWidget(self.uri_input)
        self.layout.addWidget(self.username_input)
        self.layout.addWidget(self.password_input)
        self.layout.addWidget(self.test_button)
        self.layout.addWidget(self.save_button)
        self.setLayout(self.layout)

        self.test_button.clicked.connect(self.test_connection)
        self.save_button.clicked.connect(self.save_settings)

    def test_connection(self):
        # Logic to test database connection
        pass

    def save_settings(self):
        # Logic to save the encrypted settings
        pass
