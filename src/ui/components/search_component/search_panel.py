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
        """Set up the enhanced search panel UI."""
        main_layout = QVBoxLayout(self)
        main_layout.setObjectName("searchPanelLayout")
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # Search section container (scrollable)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        search_widget = QWidget()
        search_layout = QVBoxLayout(search_widget)
        search_layout.setSpacing(10)

        # Quick search
        quick_search_layout = QHBoxLayout()
        self.quick_search = QLineEdit()
        self.quick_search.setPlaceholderText("Quick search across all fields...")
        self.search_button = QPushButton("🔍")
        self.search_button.setFixedWidth(40)

        quick_search_layout.addWidget(self.quick_search)
        quick_search_layout.addWidget(self.search_button)
        search_layout.addLayout(quick_search_layout)

        # Advanced search toggle
        self.advanced_toggle = QPushButton("Advanced Search ▼")
        self.advanced_toggle.setCheckable(True)
        search_layout.addWidget(self.advanced_toggle)

        # Advanced search container
        self.advanced_container = QWidget()
        advanced_layout = QVBoxLayout(self.advanced_container)
        advanced_layout.setContentsMargins(0, 0, 0, 0)

        # Field searches
        self.field_searches = {}
        for field in SearchField:
            field_widget = SearchFieldWidget(field)
            self.field_searches[field] = field_widget
            advanced_layout.addWidget(field_widget)

        # Filters
        self.filters = SearchFilterWidget()
        advanced_layout.addWidget(self.filters)

        self.advanced_container.setVisible(False)
        search_layout.addWidget(self.advanced_container)

        scroll.setWidget(search_widget)
        main_layout.addWidget(scroll)

        # Results section
        results_label = QLabel("Results")
        results_label.setObjectName("resultsLabel")
        main_layout.addWidget(results_label)

        self.results_tree = QTreeWidget()
        self.results_tree.setObjectName("resultsTree")
        self.results_tree.setHeaderLabels(["Name", "Type", "Properties"])
        self.results_tree.setColumnCount(3)
        self.results_tree.setAlternatingRowColors(True)
        main_layout.addWidget(self.results_tree)

        # Status section
        self.status_label = QLabel("")
        self.status_label.setObjectName("searchStatusLabel")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(self.status_label)

    def _connect_signals(self) -> None:
        """Connect internal signals."""
        self.search_button.clicked.connect(self._handle_search_clicked)
        self.quick_search.returnPressed.connect(self._handle_search_clicked)
        self.results_tree.itemDoubleClicked.connect(self._handle_result_selected)
        self.advanced_toggle.toggled.connect(self.advanced_container.setVisible)

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

    def _handle_result_selected(self, item: QTreeWidgetItem, column: int) -> None:
        """Handle result item selection."""
        node_name = item.text(0)  # Name is in first column
        logger.debug("result_selected", node_name=node_name)
        self.result_selected.emit(node_name)

    def set_loading_state(self, is_loading: bool) -> None:
        """Set the loading state of the search panel."""
        self.search_button.setEnabled(not is_loading)
        self.quick_search.setReadOnly(is_loading)
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
