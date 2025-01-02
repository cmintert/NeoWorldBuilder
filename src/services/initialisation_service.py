from PyQt6.QtGui import QStandardItemModel
from PyQt6.QtWidgets import QAbstractItemView
from structlog import get_logger

from models.completer_model import AutoCompletionUIHandler
from models.suggestion_model import SuggestionUIHandler
from services.autocompletion_service import AutoCompletionService
from services.fast_inject_service import FastInjectService
from services.image_service import ImageService
from services.node_operation_service import NodeOperationsService
from services.property_service import PropertyService
from services.relationship_tree_service import RelationshipTreeService
from services.save_service import SaveService
from services.search_analysis_service.search_analysis_service import (
    SearchAnalysisService,
)
from services.suggestion_service import SuggestionService
from services.worker_manager_service import WorkerManagerService
from ui.styles import StyleManager
from utils.exporters import Exporter

logger = get_logger(__name__)


class InitializationService:
    """Service responsible for initializing the WorldBuilder application components."""

    def __init__(
        self,
        controller: "WorldBuildingController",
        ui: "WorldBuildingUI",
        model: "Neo4jModel",
        config: "Config",
        app_instance: "WorldBuildingApp",
        error_handler: "ErrorHandler",
        name_cache_service: "NameCacheService",
    ) -> None:
        """
        Initialize the service with required dependencies.

        Args:
            controller: Main application controller
            ui: Main UI instance
            model: Neo4j database model
            config: Application configuration
            app_instance: Main application instance
            error_handler: Error handling service
        """
        self.controller = controller
        self.ui = ui
        self.model = model
        self.config = config
        self.app_instance = app_instance
        self.error_handler = error_handler
        self.name_cache_service = name_cache_service

    def initialize_application(self) -> None:
        """Initialize all application components."""
        self._initialize_style_management()
        self._initialize_services()
        self._initialize_ui_components()
        self._initialize_tree_view()
        self._initialize_completers()
        self._connect_signals()
        self._initialize_save_service()
        self._setup_search_handlers()
        self._load_default_state()

    def _initialize_style_management(self) -> None:
        """Initialize style management system."""
        self.style_manager = StyleManager("src/config/styles")
        self.style_manager.registry.error_occurred.connect(
            self.controller._show_error_dialog
        )

        # Apply default application style
        self.style_manager.apply_style(self.app_instance, "default")

        # Apply specific styles to UI components
        self.style_manager.apply_style(self.ui.tree_view, "tree")
        self.style_manager.apply_style(self.ui.properties_table, "data-table")
        self.style_manager.apply_style(self.ui.relationships_table, "data-table")

    def _initialize_services(self) -> None:
        """Initialize all application services in dependency order."""
        # 1. Basic services that have no dependencies
        self.property_service = PropertyService(self.config)
        self.image_service = ImageService()

        # 2. Core services that others depend on
        self.worker_manager = WorkerManagerService(self.error_handler)

        # 3. Feature services
        self.fast_inject_service = FastInjectService()
        self.exporter = Exporter(self.ui, self.config)

        # Initialize the name cache for the first time
        self.name_cache_service.rebuild_cache()

        # Services requiring UI
        self.auto_completion_service = AutoCompletionService(
            self.model,
            self.config,
            self.worker_manager,
            self._create_autocompletion_ui_handler(),
            self.name_cache_service,
            self.error_handler.handle_error,
        )

        self.node_operations = NodeOperationsService(
            self.model,
            self.config,
            self.worker_manager,
            self.property_service,
            self.error_handler,
        )

        self.suggestion_service = SuggestionService(
            self.model,
            self.config,
            self.worker_manager,
            self.error_handler,
            self._create_suggestion_ui_handler(),
        )

        # Initialize search and analysis service
        self.search_service = SearchAnalysisService(
            self.model,
            self.config,
            self.worker_manager,
            self.error_handler.handle_error,
        )

        # Initialize tree model and service
        self.tree_model = QStandardItemModel()
        self.relationship_tree_service = RelationshipTreeService(
            self.tree_model, self.controller.NODE_RELATIONSHIPS_HEADER
        )

    def _initialize_save_service(self) -> None:
        """Initialize and start the save service after all other components are ready."""
        self.save_service = SaveService(self.node_operations, self.error_handler)
        self.controller.save_service = self.save_service

        # Start periodic checking only after everything is properly initialized
        self.save_service.start_periodic_check(
            get_current_data=self.controller._get_current_node_data,
            on_state_changed=self.controller._handle_save_state_changed,
        )

    def _initialize_ui_components(self) -> None:
        """Initialize UI components."""
        self.ui.controller = self.controller

        # Store references to initialized services in controller in dependency order
        self.controller.style_manager = self.style_manager
        self.controller.property_service = self.property_service
        self.controller.image_service = self.image_service
        self.controller.worker_manager = self.worker_manager
        self.controller.fast_inject_service = self.fast_inject_service
        self.controller.exporter = self.exporter
        self.controller.auto_completion_service = self.auto_completion_service
        self.controller.node_operations = self.node_operations
        self.controller.suggestion_service = self.suggestion_service
        self.controller.tree_model = self.tree_model
        self.controller.relationship_tree_service = self.relationship_tree_service
        self.controller.search_service = self.search_service
        self.ui.description_input.name_cache_service = self.name_cache_service

        # Initialize search panel handlers

    def _initialize_tree_view(self) -> None:
        """Initialize the tree view model."""
        self.tree_model.setHorizontalHeaderLabels(
            [self.controller.NODE_RELATIONSHIPS_HEADER]
        )
        self.ui.tree_view.setModel(self.tree_model)

        self.ui.tree_view.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection
        )
        self.ui.tree_view.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectItems
        )

        self.ui.tree_view.setUniformRowHeights(True)
        self.ui.tree_view.setItemsExpandable(True)
        self.ui.tree_view.setAllColumnsShowFocus(True)
        self.ui.tree_view.setHeaderHidden(False)

    def _initialize_completers(self) -> None:
        """Initialize auto-completion for node names and relationship targets."""
        self.auto_completion_service.initialize_node_completer(self.ui.name_input)

    def _connect_signals(self) -> None:
        """Connect all UI signals to handlers."""
        # Tree view selection
        self.ui.tree_view.selectionModel().selectionChanged.connect(
            self.controller.on_tree_selection_changed
        )

        # Main buttons
        self.ui.save_button.clicked.connect(self.controller.save_node)
        self.ui.delete_button.clicked.connect(self.controller.delete_node)

        # Name input and autocomplete
        self.ui.name_input.editingFinished.connect(self.controller.load_node_data)

        # Table buttons
        self.ui.add_rel_button.clicked.connect(self.ui.add_relationship_row)

        # Suggest button
        self.ui.suggest_button.clicked.connect(self.controller.show_suggestions_modal)

        # Change monitoring
        self.ui.name_input.textChanged.connect(
            self.controller.update_unsaved_changes_indicator
        )
        self.ui.description_input.textChanged.connect(
            self.controller.update_unsaved_changes_indicator
        )
        self.ui.labels_input.textChanged.connect(
            self.controller.update_unsaved_changes_indicator
        )
        self.ui.tags_input.textChanged.connect(
            self.controller.update_unsaved_changes_indicator
        )
        self.ui.properties_table.itemChanged.connect(
            self.controller.update_unsaved_changes_indicator
        )
        self.ui.relationships_table.itemChanged.connect(
            self.controller.update_unsaved_changes_indicator
        )

        # Depth spinbox
        self.ui.depth_spinbox.valueChanged.connect(self.controller.on_depth_changed)

    def _load_default_state(self) -> None:
        """Initialize default UI state."""
        self.ui.name_input.clear()
        self.ui.description_input.clear()
        self.ui.labels_input.clear()
        self.ui.tags_input.clear()
        self.ui.properties_table.setRowCount(0)
        self.ui.relationships_table.setRowCount(0)
        self.controller.refresh_tree_view()

    def _create_autocompletion_ui_handler(self) -> AutoCompletionUIHandler:
        """Create and return the UI handler for auto-completion."""
        return self.controller._create_autocompletion_ui_handler()

    def _create_suggestion_ui_handler(self) -> SuggestionUIHandler:
        """Create and return the UI handler for suggestions."""
        return self.controller._create_suggestion_ui_handler()

    def _setup_search_handlers(self) -> None:
        """Setup search panel signal connections and initialization."""

        if not hasattr(self.ui, "search_panel") or not self.ui.search_panel:
            logger.warning("search_panel_unavailable", module="InitializationService")
            return

        try:
            self.ui.search_panel.search_requested.disconnect()
            self.ui.search_panel.result_selected.disconnect()
        except TypeError:  # Raised when no connections exist
            logger.debug("No prior search panel connections to disconnect")
            pass

        # Connect enhanced search panel signals
        self.ui.search_panel.search_requested.connect(
            self.controller._handle_search_request
        )
        self.ui.search_panel.result_selected.connect(
            self.controller._handle_search_result_selected
        )

        # Apply styling to search panel
        self.style_manager.apply_style(self.ui.search_panel, "default")
        logger.debug("search_handlers_setup_complete")

        # Initialize any search panel specific settings
        self.ui.search_panel.filters.has_relationships.setCurrentIndex(
            0
        )  # Set to "Any"
