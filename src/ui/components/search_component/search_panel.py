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
        main_layout.setSpacing(8)

        # Fixed header section
        header_widget = QWidget()
        header_widget.setObjectName("searchHeader")
        header_layout = QVBoxLayout(header_widget)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(4)

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

        # Clear button (only shown when text exists)
        self.clear_button = QPushButton("✕")
        self.clear_button.setObjectName("clearSearchButton")
        self.clear_button.setFixedSize(20, 20)
        self.clear_button.setVisible(False)

        quick_search_layout.addWidget(search_icon)
        quick_search_layout.addWidget(self.quick_search)
        quick_search_layout.addWidget(self.clear_button)

        header_layout.addWidget(quick_search_frame)

        # Advanced search toggle
        toggle_container = QWidget()
        toggle_layout = QHBoxLayout(toggle_container)
        toggle_layout.setContentsMargins(4, 0, 4, 4)
        toggle_layout.setSpacing(0)

        self.advanced_toggle = QPushButton("Advanced Search")
        self.advanced_toggle.setObjectName("advancedToggle")
        self.advanced_toggle.setCheckable(True)
        self.advanced_toggle.setFlat(True)

        self.toggle_icon = QLabel("▼")
        self.toggle_icon.setObjectName("toggleIcon")
        self.toggle_icon.setFixedWidth(16)

        toggle_layout.addWidget(self.advanced_toggle)
        toggle_layout.addWidget(self.toggle_icon)
        toggle_layout.addStretch()

        header_layout.addWidget(toggle_container)
        main_layout.addWidget(header_widget)

        # Scrollable content area
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setSpacing(12)

        # Advanced search section
        self.advanced_container = QFrame()
        self.advanced_container.setObjectName("advancedContainer")
        self.advanced_container.setFrameShape(QFrame.Shape.StyledPanel)
        advanced_layout = QVBoxLayout(self.advanced_container)
        advanced_layout.setSpacing(16)

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

        # Hide advanced section initially
        self.advanced_container.setVisible(False)
        content_layout.addWidget(self.advanced_container)
        self.scroll_area.setWidget(content_widget)
        main_layout.addWidget(self.scroll_area)

        # Results section
        results_container = QWidget()
        results_container.setObjectName("resultsContainer")
        results_layout = QVBoxLayout(results_container)
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

        # Add results container
        main_layout.addWidget(results_container)

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
        self.results_tree.itemDoubleClicked.connect(self._handle_result_selected)

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
        if self.advanced_container.isVisible():
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
                advanced_search=self.advanced_container.isVisible(),
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

        # Show/hide the container (we'll animate this in a future update)
        self.advanced_container.setVisible(checked)

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

        if hasattr(self, "advanced_container"):
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
