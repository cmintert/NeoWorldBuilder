from typing import Optional, List, Dict, Any

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLineEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QLabel,
    QPushButton,
    QHBoxLayout,
)
from structlog import get_logger

logger = get_logger(__name__)


class SearchPanel(QWidget):
    """
    Search panel component for the main UI.

    Provides search functionality and result display.
    """

    # Signals
    search_requested = pyqtSignal(str)  # Search text
    result_selected = pyqtSignal(str)  # Selected node name

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """
        Initialize the search panel.

        Args:
            parent: Optional parent widget
        """
        super().__init__(parent)
        self.setObjectName("searchPanel")
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self) -> None:
        """Set up the search panel UI elements."""
        # Main layout
        layout = QVBoxLayout(self)
        layout.setObjectName("searchPanelLayout")
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Search section
        search_layout = QHBoxLayout()
        search_layout.setObjectName("searchLayout")

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search nodes...")
        self.search_input.setObjectName("searchInput")

        self.search_button = QPushButton("🔍")
        self.search_button.setObjectName("searchButton")
        self.search_button.setFixedWidth(40)

        search_layout.addWidget(self.search_input)
        search_layout.addWidget(self.search_button)
        layout.addLayout(search_layout)

        # Results section
        results_label = QLabel("Results")
        results_label.setObjectName("resultsLabel")
        layout.addWidget(results_label)

        self.results_tree = QTreeWidget()
        self.results_tree.setObjectName("resultsTree")
        self.results_tree.setHeaderLabels(["Name", "Type", "Properties"])
        self.results_tree.setColumnCount(3)
        self.results_tree.setAlternatingRowColors(True)
        layout.addWidget(self.results_tree)

        # Status section
        self.status_label = QLabel("")
        self.status_label.setObjectName("searchStatusLabel")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label)

        # Set stretch factors
        layout.setStretchFactor(self.results_tree, 1)

    def _connect_signals(self) -> None:
        """Connect internal signals."""
        self.search_button.clicked.connect(self._handle_search_clicked)
        self.search_input.returnPressed.connect(self._handle_search_clicked)
        self.results_tree.itemDoubleClicked.connect(self._handle_result_selected)

    def _handle_search_clicked(self) -> None:
        """Handle search button click or return pressed in search input."""
        search_text = self.search_input.text().strip()
        if search_text:
            logger.debug("search_requested", search_text=search_text)
            self.search_requested.emit(search_text)
            self.set_loading_state(True)

    def _handle_result_selected(self, item: QTreeWidgetItem, column: int) -> None:
        """Handle result item selection."""
        node_name = item.text(0)  # Name is in first column
        logger.debug("result_selected", node_name=node_name)
        self.result_selected.emit(node_name)

    def set_loading_state(self, is_loading: bool) -> None:
        """
        Set the loading state of the search panel.

        Args:
            is_loading: Whether the panel is in loading state
        """
        self.search_button.setEnabled(not is_loading)
        self.search_input.setReadOnly(is_loading)
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

                    logger.debug(
                        "adding_result_item",
                        name=name,
                        type=type_str,
                        prop_count=len(props),
                    )

                    item.setText(0, name)
                    item.setText(1, type_str)
                    item.setText(2, props_str)
                    self.results_tree.addTopLevelItem(item)

                except Exception as e:
                    logger.error("result_item_error", error=str(e))
                    continue

            total_count = self.results_tree.topLevelItemCount()
            logger.debug("results_display_complete", displayed_count=total_count)
            self.status_label.setText(f"Found {total_count} results")
            self.results_tree.resizeColumnToContents(0)

        except Exception as e:
            logger.error("display_results_error", error=str(e), exc_info=True)
            self.status_label.setText("Error displaying results")
            self.set_loading_state(False)

    def clear_results(self) -> None:
        """Clear all search results."""
        self.results_tree.clear()
        self.status_label.setText("")

    def _format_properties(self, properties: Dict[str, Any]) -> str:
        """Format properties for display in results tree."""
        return ", ".join(f"{k}: {v}" for k, v in properties.items())

    def handle_error(self, error_message: str) -> None:
        """
        Handle and display search errors.

        Args:
            error_message: The error message to display
        """
        self.set_loading_state(False)
        self.status_label.setText(f"Error: {error_message}")
        logger.error("search_error", error=error_message)
