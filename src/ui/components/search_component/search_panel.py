from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLineEdit,
    QTreeWidget,
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

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """
        Initialize the search panel.

        Args:
            parent: Optional parent widget
        """
        super().__init__(parent)
        self.setObjectName("searchPanel")
        self._setup_ui()

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
