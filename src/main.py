"""
Main module for the NeoWorldBuilder application.

This module initializes and runs the main application, including setting up the UI, 
loading configuration, establishing database connections, and handling exceptions.

Classes:
    AppComponents: Container for main application components.
    WorldBuildingApp: Main application class with improved initialization and error handling.

Functions:
    exception_hook(exctype, value, tb): Custom exception hook for logging unhandled exceptions.
"""

# Imports
import json
import logging
import os
import sys
import traceback
from dataclasses import dataclass
from datetime import time
from typing import Optional

import structlog
from PyQt6.QtCore import (
    Qt,
)
from PyQt6.QtGui import (
    QAction,
    QCloseEvent,
)
from PyQt6.QtWidgets import (
    QApplication,
    QMessageBox,
    QMainWindow,
)
from neo4j.exceptions import AuthError, ServiceUnavailable

from ui.components.dialogs import ConnectionSettingsDialog
from utils.error_handler import ErrorHandler

try:
    from config.config import Config
except ImportError as e:
    print(f"Failed to import config: {e}")
    sys.exit(1)
from core.neo4jmodel import Neo4jModel
from ui.controller import WorldBuildingController
from ui.main_window import WorldBuildingUI
from utils.crypto import SecurityUtility
from utils.path_helper import get_resource_path

from services.worker_manager_service import WorkerManagerService
from services.name_cache_service import NameCacheService


def setup_app_logging():
    """Set up logging for both development and production environments."""
    # Determine if we're running from PyInstaller
    if getattr(sys, "frozen", False):
        app_dir = os.path.dirname(sys.executable)
    else:
        app_dir = os.path.dirname(os.path.abspath(__file__))

    # Create logs directory if it doesn't exist
    logs_dir = os.path.join(app_dir, "logs")
    os.makedirs(logs_dir, exist_ok=True)

    log_path = os.path.join(logs_dir, "neoworldbuilder.log")

    # Configure structlog with a file handler that stays open
    try:
        file_handler = open(log_path, "a", encoding="utf-8")

        # Configure structlog
        structlog.configure(
            processors=[
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.add_log_level,
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                structlog.processors.JSONRenderer(),
            ],
            wrapper_class=structlog.make_filtering_bound_logger(logging.DEBUG),
            context_class=dict,
            logger_factory=structlog.WriteLoggerFactory(file=file_handler),
            cache_logger_on_first_use=False,  # Changed to False to prevent caching issues
        )

        # Disable neo4j's internal debug logging
        logging.getLogger("neo4j").setLevel(logging.WARNING)

        return file_handler

    except Exception as e:
        # Fallback to a temp directory if we can't write to the app directory
        temp_dir = os.path.join(os.path.expanduser("~"), ".neoworldbuilder", "logs")
        os.makedirs(temp_dir, exist_ok=True)
        log_path = os.path.join(temp_dir, "neoworldbuilder.log")
        file_handler = open(log_path, "a", encoding="utf-8")

        # Configure with same settings as above
        structlog.configure(...)  # Same configuration as above

        return file_handler


# Initialize logging
log_file = setup_app_logging()


def exception_hook(exctype: type, value: Exception, tb: traceback) -> None:
    """
    Custom exception hook for logging unhandled exceptions.

    Args:
        exctype (type): The exception type.
        value (Exception): The exception instance.
        tb (traceback): The traceback object.
    """
    try:
        # Try to log using structlog
        logger = structlog.get_logger()
        logger.critical(
            "Unhandled exception",
            error_type=str(exctype.__name__),
            error_value=str(value),
            traceback=traceback.format_tb(tb),
        )
    except Exception:
        # If structlog fails, write to the log file directly
        if log_file and not log_file.closed:
            traceback.print_exception(exctype, value, tb, file=log_file)
            log_file.flush()

    # Show error dialog to user
    try:
        app = QApplication.instance()
        if app is not None:
            QMessageBox.critical(
                None,
                "Unhandled Exception",
                f"An unhandled exception occurred:\n{value}\n\nPlease check the log file for details.",
            )
    except Exception:
        pass  # If we can't show the dialog, at least we logged the error


sys.excepthook = exception_hook


@dataclass
class AppComponents:
    """
    Container for main application components.

    Attributes:
        ui (WorldBuildingUI): The UI instance.
        model (Neo4jModel): The Neo4j model instance.
        controller (WorldBuildingController): The controller instance.
        config (Config): The configuration instance.
    """

    ui: WorldBuildingUI
    model: Neo4jModel
    controller: WorldBuildingController
    config: Config


class WorldBuildingApp(QMainWindow):
    """
    Main application class with improved initialization and error handling.

    Attributes:
        components (Optional[AppComponents]): The main application components.
    """

    log_file = None

    def __init__(self) -> None:
        """
        Initialize the main application window.
        """
        super().__init__()
        WorldBuildingApp.log_file = log_file
        self.components: Optional[AppComponents] = None
        self.setObjectName("WorldBuildingApp")
        self.initialize_application()

    def initialize_application(self) -> None:
        """Initialize the application with improved error handling."""
        try:
            # Load configuration first
            config = self._load_configuration()

            # Setup logging
            self._setup_logging(config)

            # Initialize database connection with enhanced error handling
            while True:  # Keep trying until successful connection or user cancels
                try:
                    model = self._initialize_database(config)
                    break  # Successfully connected
                except AuthError:
                    response = QMessageBox.question(
                        self,
                        "Database Authentication Error",
                        "Invalid database credentials. Would you like to update them?",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    )

                    if response == QMessageBox.StandardButton.Yes:
                        dialog = ConnectionSettingsDialog(config, self)
                        if dialog.exec():
                            # Reload configuration with new credentials
                            config = self._load_configuration()
                            continue  # Try connection again
                        else:
                            # User cancelled the settings dialog
                            raise RuntimeError(
                                "Database configuration required to run the application"
                            )
                    else:
                        # User chose not to update credentials
                        raise RuntimeError(
                            "Database connection required to run the application"
                        )
                except ServiceUnavailable:
                    QMessageBox.critical(
                        self,
                        "Database Connection Error",
                        "Cannot connect to the database server. Please ensure Neo4j is running.",
                    )
                    raise RuntimeError("Database server not available")

            # Create UI (elements created but signals not connected)
            ui = self._setup_ui(None)

            # Initialize Controller
            controller = self._initialize_controller(ui, model, config)

            # Set controller and connect signals
            ui.controller = controller
            ui.setup_ui()

            # Store components
            self.components = AppComponents(
                ui=ui, model=model, controller=controller, config=config
            )

            # Configure window
            self._configure_main_window()

            # Load initial data
            controller.load_last_modified_node()

            # Show window
            self.show()

            structlog.get_logger().info("Application initialized successfully")

        except Exception as e:
            self._handle_initialization_error(e)

    def _handle_initialization_error(self, error: Exception) -> None:
        """Handle initialization errors with improved user feedback."""
        error_message = str(error)
        detailed_message = ""

        if "database configuration required" in error_message.lower():
            detailed_message = "The application needs valid database settings to run.\n\nPlease configure the connection settings and try again."
        elif "connection required" in error_message.lower():
            detailed_message = "The application requires a working database connection.\n\nPlease ensure Neo4j is running and try again."
        else:
            detailed_message = f"Failed to initialize the application:\n\n{error_message}\n\nPlease check the logs for more details."

        QMessageBox.critical(self, "Initialization Error", detailed_message)

        # Clean up any partially initialized resources
        self._cleanup_resources()

        sys.exit(1)

    def _load_configuration(self) -> Config:
        """
        Load application configuration with error handling.
        """
        try:
            # Load system.json configuration
            system_json_path = get_resource_path("src/config/system.json")
            print(f"Loading system config from: {system_json_path}")

            with open(system_json_path, "r") as config_file:
                system_config = json.load(config_file)

            print(system_config)

            # Check if system.json contains the encryption key
            if "KEY" not in system_config:
                encryption_key = SecurityUtility.generate_key()
                system_config["KEY"] = encryption_key
                with open(system_json_path, "w") as config_file:
                    json.dump(system_config, config_file, indent=4)

            # Load all config files
            config_files = [
                get_resource_path("src/config/database.json"),
                get_resource_path("src/config/logging.json"),
                get_resource_path("src/config/limits.json"),
                get_resource_path("src/config/ui.json"),
                get_resource_path("src/config/system.json"),
            ]

            config = Config(config_files)
            structlog.get_logger().info("Configuration loaded successfully")
            return config

        except FileNotFoundError as e:
            print(f"File not found error: {e}")  # Add debug print
            raise RuntimeError(f"Configuration file not found: {e}")
        except json.JSONDecodeError as e:
            raise RuntimeError("Invalid JSON in configuration file")
        except Exception as e:
            print(f"Unexpected error: {e}")  # Add debug print
            raise RuntimeError(f"Error loading configuration: {str(e)}")

    def _setup_logging(self, config: Config) -> None:
        """
        Configure logging with rotation and formatting.

        Args:
            config (Config): The configuration instance.

        Raises:
            RuntimeError: If logging setup fails.
        """
        try:

            log_level = getattr(logging, config.LOGGING_LEVEL.upper())

            # Set up logging configuration
            structlog.configure(
                processors=[
                    structlog.processors.TimeStamper(fmt="iso"),
                    structlog.processors.JSONRenderer(),
                ],
                wrapper_class=structlog.make_filtering_bound_logger(log_level),
                context_class=dict,
                logger_factory=structlog.PrintLoggerFactory(),
                cache_logger_on_first_use=True,
            )
            structlog.get_logger().info("Logging system initialized")
        except Exception as e:
            raise RuntimeError(f"Failed to setup logging: {str(e)}") from e

    def _initialize_database(self, config: Config) -> Neo4jModel:
        """
        Initialize database connection with retry logic and improved error handling.

        Args:
            config (Config): The configuration instance.

        Returns:
            Neo4jModel: The initialized Neo4j model.

        Raises:
            RuntimeError: If database connection fails after retries.
            AuthError: If authentication fails.
            ServiceUnavailable: If database service is not available.
        """
        max_retries = 3
        retry_delay = 2  # seconds
        plain = "not set"

        security_utility = SecurityUtility(config.KEY)

        if config.PASSWORD != "":
            plain = security_utility.decrypt(config.PASSWORD)

        last_error = None
        for attempt in range(max_retries):
            try:
                model = Neo4jModel(config.URI, config.USERNAME, plain, config)
                structlog.get_logger().info("Database connection established")
                return model
            except (AuthError, ServiceUnavailable) as e:
                # Don't retry auth or service errors - propagate immediately
                raise
            except Exception as e:
                last_error = e
                if attempt >= max_retries - 1:
                    raise RuntimeError(
                        f"Failed to connect to database after {max_retries} attempts: {str(last_error)}"
                    )
                structlog.get_logger().warning(
                    f"Database connection attempt {attempt + 1} failed: {e}"
                )
                time.sleep(retry_delay)

    def _setup_ui(
        self, controller: Optional[WorldBuildingController]
    ) -> WorldBuildingUI:
        """
        Initialize user interface with error handling.

        Args:
            controller: The controller instance.

        Returns:
            ui.main_window.WorldBuildingUI: The initialized UI instance.

        Raises:
            RuntimeError: If UI initialization fails.
        """
        try:
            ui = WorldBuildingUI(controller)
            structlog.get_logger().info("UI initialized successfully")
            return ui
        except Exception as e:
            raise RuntimeError(f"Failed to initialize UI: {str(e)}")

    def _initialize_controller(
        self, ui: WorldBuildingUI, model: Neo4jModel, config: Config
    ) -> WorldBuildingController:
        """
        Initialize application controller with error handling.
        """
        try:
            # Create error handler first
            error_handler = ErrorHandler(ui_feedback_handler=self._show_error_dialog)

            # Create worker manager with error handler
            worker_manager = WorkerManagerService(error_handler)

            # Initialize name cache service
            name_cache_service = NameCacheService(
                model=model,
                worker_manager=worker_manager,
                error_handler=error_handler.handle_error,
            )

            # Create controller with all dependencies
            controller = WorldBuildingController(
                ui=ui,
                model=model,
                config=config,
                app_instance=self,
                name_cache_service=name_cache_service,
            )

            structlog.get_logger().info("Controller initialized successfully")
            return controller
        except Exception as e:
            raise RuntimeError(f"Failed to initialize controller: {str(e)}")

    def _configure_main_window(self) -> None:
        """
        Configure main window properties with error handling.

        Raises:
            RuntimeError: If main window configuration fails.
        """
        try:
            self.setObjectName("NeoWorldBuilder")
            self.setCentralWidget(self.components.ui)

            # Set window title with version
            version = self.components.config.VERSION
            build_type = self.components.config.BUILD_TYPE

            # Show version with build type if not release
            if build_type == "release":
                self.setWindowTitle(f"NeoWorldBuilder {version}")
            else:
                self.setWindowTitle(f"NeoWorldBuilder {version}-{build_type}")

            # Ensure transparency is properly set
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
            self.components.ui.setAttribute(
                Qt.WidgetAttribute.WA_TranslucentBackground, True
            )

            # Set window size
            self.resize(
                self.components.config.WINDOW_WIDTH,
                self.components.config.WINDOW_HEIGHT,
            )
            self.setMinimumSize(
                self.components.config.WINDOW_WIDTH,
                self.components.config.WINDOW_HEIGHT,
            )

            # Add Export menu to the main menu bar
            self._add_menu_bar()

            structlog.get_logger().info(
                f"Window configured with size "
                f"{self.components.config.WINDOW_WIDTH}x"
                f"{self.components.config.WINDOW_HEIGHT}"
            )
        except Exception as e:
            raise RuntimeError(f"Failed to configure main window: {str(e)}")

    def _add_menu_bar(self) -> None:
        """
        Add Export menu to the main menu bar.
        """
        menu_bar = self.menuBar()
        menu_bar.setObjectName("menuBar")

        export_menu = menu_bar.addMenu("Export")
        settings_menue = menu_bar.addMenu("Settings")

        export_json_action = QAction("Export as JSON", self)
        export_json_action.triggered.connect(
            lambda: self.components.controller.export_to_filetype("json")
        )
        export_menu.addAction(export_json_action)

        export_txt_action = QAction("Export as TXT", self)
        export_txt_action.triggered.connect(
            lambda: self.components.controller.export_to_filetype("txt")
        )
        export_menu.addAction(export_txt_action)

        export_csv_action = QAction("Export as CSV", self)
        export_csv_action.triggered.connect(
            lambda: self.components.controller.export_to_filetype("csv")
        )
        export_menu.addAction(export_csv_action)

        export_pdf_action = QAction("Export as PDF", self)
        export_pdf_action.triggered.connect(
            lambda: self.components.controller.export_to_filetype("pdf")
        )
        export_menu.addAction(export_pdf_action)

        open_connection_settings_action = QAction("Database Connection", self)
        open_connection_settings_action.triggered.connect(
            self.components.controller.open_connection_settings
        )
        settings_menue.addAction(open_connection_settings_action)

        open_style_settings_action = QAction("Style", self)
        open_style_settings_action.triggered.connect(
            self.components.controller.open_style_settings
        )

        settings_menue.addAction(open_style_settings_action)

    def _handle_initialization_error(self, error: Exception) -> None:
        """
        Handle initialization errors with cleanup.

        Args:
            error (Exception): The initialization error.
        """
        error_message = f"Failed to initialize the application:\n{str(error)}"
        structlog.get_logger().critical(error_message, exc_info=True)

        QMessageBox.critical(self, "Initialization Error", error_message)

        # Cleanup any partially initialized resources
        self._cleanup_resources()

        sys.exit(1)

    def _cleanup_resources(self) -> None:
        """
        Clean up application resources.
        """
        if self.components:
            if self.components.controller:
                try:
                    self.components.controller.cleanup()
                except Exception as e:
                    structlog.get_logger().error(
                        f"Error during controller cleanup: {e}"
                    )

            if self.components.model:
                try:
                    self.components.model.close()
                except Exception as e:
                    structlog.get_logger().error(f"Error during model cleanup: {e}")

    def _show_error_dialog(self, title: str, message: str) -> None:
        """
        Show an error dialog to the user.

        Args:
            title (str): Dialog title
            message (str): Error message to display
        """
        QMessageBox.critical(self, title, message)

    def closeEvent(self, event: QCloseEvent) -> None:
        """
        Handle application shutdown with proper cleanup.

        Args:
            event: The close event.
        """
        structlog.get_logger().info("Application shutdown initiated")

        try:
            # Clean up controller resources
            if self.components and self.components.controller:
                self.components.controller.cleanup()
                structlog.get_logger().info("Controller resources cleaned up")

            # Clean up model resources
            if self.components and self.components.model:
                self.components.model.close()
                structlog.get_logger().info("Model resources cleaned up")

            # Flush and close the log file
            if log_file:
                log_file.flush()
                log_file.close()

            event.accept()
            structlog.get_logger().info("Application shutdown completed successfully")

        except Exception as e:
            # At this point logging might not work, so print to stderr directly
            print(f"Error during application shutdown: {e}", file=sys.__stderr__)
            event.accept()  # Still close the application


if __name__ == "__main__":
    try:
        app = QApplication(sys.argv)
        # app.setStyle("Fusion")
        ex = WorldBuildingApp()
        sys.exit(app.exec())
    except Exception as e:
        structlog.get_logger().critical(
            "Unhandled exception in main loop", exc_info=True
        )
        sys.exit(1)
