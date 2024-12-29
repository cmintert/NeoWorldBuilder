from typing import Optional, List, Dict, Any

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLineEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QLabel,
    QPushButton,
    QComboBox,
    QCheckBox,
    QFrame,
    QScrollArea,
    QGroupBox,
)
from structlog import get_logger

from services.search_analysis_service import SearchCriteria, SearchField, FieldSearch

logger = get_logger(__name__)


class SearchFieldWidget(QWidget):
    """Widget for a single search field with options."""

    def __init__(self, field: SearchField, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.field = field
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Field selector
        self.field_label = QLabel(self.field.value.capitalize())
        self.field_label.setFixedWidth(100)

        # Search input
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(f"Search {self.field.value}...")

        # Exact match checkbox
        self.exact_match = QCheckBox("Exact")
        self.exact_match.setToolTip("Match exact text only")

        # Add to layout
        layout.addWidget(self.field_label)
        layout.addWidget(self.search_input, 1)  # Stretch factor 1
        layout.addWidget(self.exact_match)

    def get_search_value(self) -> Optional[FieldSearch]:
        """Get the field search if text is entered."""
        if text := self.search_input.text().strip():
            return FieldSearch(
                field=self.field, text=text, exact_match=self.exact_match.isChecked()
            )
        return None


class SearchFilterWidget(QWidget):
    """Widget for managing search filters."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Label filters
        label_group = QGroupBox("Label Filters")
        label_layout = QVBoxLayout()

        # Include labels
        self.include_labels = QLineEdit()
        self.include_labels.setPlaceholderText("Include labels (comma-separated)")
        label_layout.addWidget(self.include_labels)

        # Exclude labels
        self.exclude_labels = QLineEdit()
        self.exclude_labels.setPlaceholderText("Exclude labels (comma-separated)")
        label_layout.addWidget(self.exclude_labels)

        label_group.setLayout(label_layout)
        layout.addWidget(label_group)

        # Property filters
        prop_group = QGroupBox("Property Filters")
        prop_layout = QVBoxLayout()

        # Required properties
        self.required_props = QLineEdit()
        self.required_props.setPlaceholderText("Required properties (comma-separated)")
        prop_layout.addWidget(self.required_props)

        # Property existence
        self.has_props = QCheckBox("Has any custom properties")
        prop_layout.addWidget(self.has_props)

        prop_group.setLayout(prop_layout)
        layout.addWidget(prop_group)

        # Relationship filters
        rel_group = QGroupBox("Relationship Filters")
        rel_layout = QVBoxLayout()

        # Has relationships
        self.has_relationships = QComboBox()
        self.has_relationships.addItems(
            ["Any", "Has relationships", "No relationships"]
        )
        rel_layout.addWidget(self.has_relationships)

        # Relationship types
        self.rel_types = QLineEdit()
        self.rel_types.setPlaceholderText("Relationship types (comma-separated)")
        rel_layout.addWidget(self.rel_types)

        rel_group.setLayout(rel_layout)
        layout.addWidget(rel_group)


class SearchPanel(QWidget):
    """Enhanced search panel with advanced search capabilities."""

    # Signals
    search_requested = pyqtSignal(SearchCriteria)  # Enhanced search criteria
    result_selected = pyqtSignal(str)  # Selected node name

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("searchPanel")
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self) -> None:
        """Set up the enhanced search panel UI with optimized UX."""
        main_layout = QVBoxLayout(self)
        main_layout.setObjectName("searchPanelLayout")
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(0)  # Remove spacing between elements

        # Top search container
        top_container = QWidget()
        top_layout = QVBoxLayout(top_container)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(4)

        # Quick search container
        quick_search_frame = QFrame()
        quick_search_frame.setObjectName("quickSearchFrame")
        quick_search_frame.setFrameShape(QFrame.Shape.StyledPanel)
        quick_search_layout = QHBoxLayout(quick_search_frame)
        quick_search_layout.setContentsMargins(8, 8, 8, 8)
        quick_search_layout.setSpacing(8)

        # Search icon and input
        search_icon = QLabel("🔍")
        search_icon.setFixedWidth(20)
        self.quick_search = QLineEdit()
        self.quick_search.setPlaceholderText("Search across all fields...")
        self.quick_search.setObjectName("quickSearchInput")

        # Clear button
        self.clear_button = QPushButton("✕")
        self.clear_button.setObjectName("clearSearchButton")
        self.clear_button.setFixedSize(20, 20)
        self.clear_button.setVisible(False)

        quick_search_layout.addWidget(search_icon)
        quick_search_layout.addWidget(self.quick_search)
        quick_search_layout.addWidget(self.clear_button)

        top_layout.addWidget(quick_search_frame)

        # Advanced search toggle - centered
        toggle_container = QWidget()
        toggle_layout = QHBoxLayout(toggle_container)
        toggle_layout.setContentsMargins(0, 0, 0, 0)
        toggle_layout.setSpacing(0)

        self.advanced_toggle = QPushButton("Advanced Search")
        self.advanced_toggle.setObjectName("advancedToggle")
        self.advanced_toggle.setCheckable(True)
        self.advanced_toggle.setFlat(True)

        self.toggle_icon = QLabel("▼")
        self.toggle_icon.setObjectName("toggleIcon")
        self.toggle_icon.setFixedWidth(16)

        # Center the toggle button
        toggle_layout.addStretch()
        toggle_layout.addWidget(self.advanced_toggle)
        toggle_layout.addWidget(self.toggle_icon)
        toggle_layout.addStretch()

        top_layout.addWidget(toggle_container)
        main_layout.addWidget(top_container)

        # Create expandable section
        self.expandable_widget = QWidget()
        expandable_layout = QVBoxLayout(self.expandable_widget)
        expandable_layout.setContentsMargins(0, 0, 0, 0)
        expandable_layout.setSpacing(0)

        # Scrollable advanced search area
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.scroll_area.setVisible(False)

        # Advanced search content
        advanced_content = QWidget()
        advanced_layout = QVBoxLayout(advanced_content)
        advanced_layout.setSpacing(12)

        # Group search fields logically
        field_groups = {
            "Basic Information": [SearchField.NAME, SearchField.DESCRIPTION],
            "Classification": [SearchField.TAGS, SearchField.LABELS],
            "Advanced": [SearchField.PROPERTIES],
        }

        self.field_searches = {}
        for group_name, fields in field_groups.items():
            group = QGroupBox(group_name)
            group.setObjectName("searchGroup")
            group_layout = QVBoxLayout(group)
            group_layout.setSpacing(8)

            for field in fields:
                field_widget = SearchFieldWidget(field)
                self.field_searches[field] = field_widget
                group_layout.addWidget(field_widget)

            advanced_layout.addWidget(group)

        # Add filters
        self.filters = SearchFilterWidget()
        advanced_layout.addWidget(self.filters)
        advanced_layout.addStretch()

        self.scroll_area.setWidget(advanced_content)
        expandable_layout.addWidget(self.scroll_area)
        main_layout.addWidget(self.expandable_widget)

        # Results section
        self.results_widget = QWidget()
        self.results_widget.setMinimumHeight(150)  # Minimum height as specified
        results_layout = QVBoxLayout(self.results_widget)
        results_layout.setContentsMargins(0, 8, 0, 0)
        results_layout.setSpacing(8)

        # Results header with count
        header_layout = QHBoxLayout()
        results_label = QLabel("Results")
        results_label.setObjectName("resultsLabel")
        self.results_count = QLabel("0 items")
        self.results_count.setObjectName("resultsCount")
        header_layout.addWidget(results_label)
        header_layout.addStretch()
        header_layout.addWidget(self.results_count)
        results_layout.addLayout(header_layout)

        # Results tree
        self.results_tree = QTreeWidget()
        self.results_tree.setObjectName("resultsTree")
        self.results_tree.setHeaderLabels(["Name", "Type", "Properties"])
        self.results_tree.setAlternatingRowColors(True)
        self.results_tree.setUniformRowHeights(True)
        results_layout.addWidget(self.results_tree)

        main_layout.addWidget(self.results_widget, 1)  # Give it stretch factor of 1

        # Status bar
        self.status_label = QLabel("")
        self.status_label.setObjectName("searchStatusLabel")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(self.status_label)

    def _connect_signals(self) -> None:
        """Connect internal signals."""
        # Quick search interactions
        self.quick_search.returnPressed.connect(self._handle_search_clicked)
        self.quick_search.textChanged.connect(self._handle_quick_search_text_changed)
        self.clear_button.clicked.connect(self._clear_quick_search)

        # Advanced search toggle with animation
        self.advanced_toggle.toggled.connect(self._toggle_advanced_search)
        self.results_tree.itemClicked.connect(self._handle_result_selected)

    def _handle_search_clicked(self) -> None:
        """Handle search button click or return pressed."""
        # Create search criteria based on UI state
        criteria = SearchCriteria()

        # Handle quick search - search across all fields with smart defaults
        if quick_text := self.quick_search.text().strip():
            # Add searches for each field type with appropriate settings
            for field in SearchField:
                # Skip PROPERTIES field for quick search performance unless specifically needed
                if field != SearchField.PROPERTIES:
                    criteria.field_searches.append(
                        FieldSearch(
                            field=field,
                            text=quick_text,
                            exact_match=False,  # Always use contains for quick search
                            case_sensitive=False,  # Default to case-insensitive
                        )
                    )

        # If advanced search is visible, add those criteria
        if self.scroll_area.isVisible():
            # Add field searches from advanced search widgets
            for field_widget in self.field_searches.values():
                if field_search := field_widget.get_search_value():
                    criteria.field_searches.append(field_search)

            # Add filters
            if label_text := self.filters.include_labels.text().strip():
                criteria.label_filters = [
                    l.strip() for l in label_text.split(",") if l.strip()
                ]

            if exclude_text := self.filters.exclude_labels.text().strip():
                criteria.exclude_labels = [
                    l.strip() for l in exclude_text.split(",") if l.strip()
                ]

            if props_text := self.filters.required_props.text().strip():
                criteria.required_properties = [
                    p.strip() for p in props_text.split(",") if p.strip()
                ]

            # Handle relationship filters
            rel_selection = self.filters.has_relationships.currentText()
            if rel_selection != "Any":
                criteria.has_relationships = rel_selection == "Has relationships"

            if rel_types := self.filters.rel_types.text().strip():
                criteria.relationship_types = [
                    r.strip() for r in rel_types.split(",") if r.strip()
                ]

        # Only emit search if we have criteria
        if (
            criteria.field_searches
            or criteria.label_filters
            or criteria.required_properties
        ):
            logger.debug(
                "search_requested",
                quick_search=bool(quick_text),
                advanced_search=self.scroll_area.isVisible(),
                criteria=criteria,
            )
            self.search_requested.emit(criteria)
            self.set_loading_state(True)
        else:
            self.status_label.setText("Please enter search criteria")

    def _handle_quick_search_text_changed(self, text: str) -> None:
        """Handle quick search text changes."""
        # Show/hide clear button based on text content
        self.clear_button.setVisible(bool(text))
        # If text is non-empty, trigger search after a short delay
        if text:
            # You might want to add debouncing here
            self._handle_search_clicked()

    def _clear_quick_search(self) -> None:
        """Clear the quick search field."""
        self.quick_search.clear()
        self.quick_search.setFocus()

    def _toggle_advanced_search(self, checked: bool) -> None:
        """Toggle advanced search with smooth animation."""
        # Update icon
        self.toggle_icon.setText("▼" if checked else "▶")

        if not checked:
            # Clear any active advanced search fields when hiding
            for field_widget in self.field_searches.values():
                field_widget.search_input.clear()
                field_widget.exact_match.setChecked(False)

            # Clear filters
            self.filters.include_labels.clear()
            self.filters.exclude_labels.clear()
            self.filters.required_props.clear()
            self.filters.has_props.setChecked(False)
            self.filters.has_relationships.setCurrentIndex(0)
            self.filters.rel_types.clear()

        # Show/hide the scroll area
        self.scroll_area.setVisible(checked)

        # Trigger a new search if we're closing advanced search and have quick search text
        if not checked and self.quick_search.text().strip():
            self._handle_search_clicked()

    def _handle_result_selected(self, item: QTreeWidgetItem, column: int) -> None:
        """Handle result item selection."""
        node_name = item.text(0)  # Name is in first column
        logger.debug("result_selected", node_name=node_name)
        self.result_selected.emit(node_name)

    def set_loading_state(self, is_loading: bool) -> None:
        """Set the loading state of the search panel."""
        # Control input abilities during loading
        self.quick_search.setReadOnly(is_loading)
        self.clear_button.setEnabled(not is_loading)
        self.advanced_toggle.setEnabled(not is_loading)

        # Control advanced search fields if visible
        if self.scroll_area.isVisible():
            for field_widget in self.field_searches.values():
                field_widget.setEnabled(not is_loading)
            self.filters.setEnabled(not is_loading)

        # Update status text
        self.status_label.setText("Searching..." if is_loading else "")

    def display_results(self, results: List[Dict[str, Any]]) -> None:
        """Display search results in the tree widget."""
        try:
            logger.debug("displaying_search_results", result_count=len(results))
            self.clear_results()
            self.set_loading_state(False)

            if not results:
                logger.debug("no_results_found")
                self.status_label.setText("No results found")
                return

            for result in results:
                try:
                    item = QTreeWidgetItem()
                    name = result.get("name", "")
                    type_str = result.get("type", "")
                    props = result.get("properties", {})
                    props_str = ", ".join(f"{k}: {v}" for k, v in props.items())

                    item.setText(0, name)
                    item.setText(1, type_str)
                    item.setText(2, props_str)
                    self.results_tree.addTopLevelItem(item)

                except Exception as e:
                    logger.error("result_item_error", error=str(e))
                    continue

            total_count = self.results_tree.topLevelItemCount()
            self.status_label.setText(f"Found {total_count} results")
            self.results_tree.resizeColumnToContents(0)

        except Exception as e:
            logger.error("display_results_error", error=str(e))
            self.status_label.setText("Error displaying results")
            self.set_loading_state(False)

    def clear_results(self) -> None:
        """Clear all search results."""
        self.results_tree.clear()
        self.status_label.setText("")

    def handle_error(self, error_message: str) -> None:
        """Handle and display search errors."""
        self.set_loading_state(False)
        self.status_label.setText(f"Error: {error_message}")
        logger.error("search_error", error=error_message)
