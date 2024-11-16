"""
Main module for the NeoRealmBuilder application.

This module initializes and runs the main application, including setting up the UI, 
loading configuration, establishing database connections, and handling exceptions.

Classes:
    AppComponents: Container for main application components.
    WorldBuildingApp: Main application class with improved initialization and error handling.

Functions:
    exception_hook(exctype, value, tb): Custom exception hook for logging unhandled exceptions.
"""

# Imports
import faulthandler
import json
import logging
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
    QPalette,
    QBrush,
    QPixmap,
    QAction,
    QCloseEvent,
)
from PyQt6.QtWidgets import (
    QApplication,
    QMessageBox,
    QMainWindow,
)

from config.config import Config
from core.neo4jmodel import Neo4jModel
from ui.controller import WorldBuildingController
from ui.main_window import WorldBuildingUI

# Configure logging
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.DEBUG),
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=True,
)

faulthandler.enable()


def exception_hook(exctype: type, value: Exception, tb: traceback) -> None:
    """
    Custom exception hook for logging unhandled exceptions.

    Args:
        exctype (type): The exception type.
        value (Exception): The exception instance.
        tb (traceback): The traceback object.
    """
    structlog.get_logger().critical(
        "Unhandled exception", exc_info=(exctype, value, tb)
    )
    traceback.print_exception(exctype, value, tb)
    sys.__excepthook__(exctype, value, tb)
    QMessageBox.critical(
        None, "Unhandled Exception", f"An unhandled exception occurred:\n{value}"
    )


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

    def __init__(self) -> None:
        """
        Initialize the main application window.
        """
        super().__init__()
        self.components: Optional[AppComponents] = None
        self.setObjectName("WorldBuildingApp")
        self.initialize_application()

    def initialize_application(self) -> None:
        """
        Initialize all application components with comprehensive error handling.
        """
        try:
            # 1. Load Configuration
            config = self._load_configuration()

            # 2. Setup Logging
            self._setup_logging(config)

            # 3. Initialize Database Model
            model = self._initialize_database(config)

            # 4 Setup UI
            ui = self._setup_ui(None)

            # 5. Initialize Controller
            controller = self._initialize_controller(ui, model, config)

            ui.controller = controller

            # Store components for access
            self.components = AppComponents(
                ui=ui, model=model, controller=controller, config=config
            )

            # 6. Configure Window
            self._configure_main_window()

            # 7. Set Background Image

            self.set_background_image("src/background.png")

            # 8 Load last modified node
            controller.load_last_modified_node()

            # 9. Show Window
            self.show()

            structlog.get_logger().info("Application initialized successfully")

        except Exception as e:
            self._handle_initialization_error(e)

    def set_background_image(self, image_path: str) -> None:
        """
        Set the background image for the main window.

        Args:
            image_path (str): The path to the background image file.
        """
        try:
            palette = QPalette()
            pixmap = QPixmap(image_path)
            palette.setBrush(QPalette.ColorRole.Window, QBrush(pixmap))
            self.setPalette(palette)
            structlog.get_logger().info(f"Background image set from {image_path}")
        except Exception as e:
            structlog.get_logger().error(f"Failed to set background image: {e}")

    def _load_configuration(self) -> Config:
        """
        Load application configuration with error handling.

        Returns:
            config.config.Config: The loaded configuration.

        Raises:
            RuntimeError: If the configuration file is not found or invalid.
        """
        try:
            config = Config("src/config.json")
            structlog.get_logger().info("Configuration loaded successfully")
            return config
        except FileNotFoundError:
            raise RuntimeError("Configuration file 'config.json' not found")
        except json.JSONDecodeError:
            raise RuntimeError("Invalid JSON in configuration file")
        except Exception as e:
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
        Initialize database connection with retry logic.

        Args:
            config (Config): The configuration instance.

        Returns:
            Neo4jModel: The initialized Neo4j model.

        Raises:
            RuntimeError: If database connection fails after retries.
        """
        max_retries = 3
        retry_delay = 2  # seconds

        for attempt in range(max_retries):
            try:
                model = Neo4jModel(
                    config.NEO4J_URI, config.NEO4J_USERNAME, config.NEO4J_PASSWORD
                )
                structlog.get_logger().info("Database connection established")
                return model
            except Exception as e:
                if attempt >= max_retries - 1:
                    raise RuntimeError(
                        f"Failed to connect to database after {max_retries} attempts: {str(e)}"
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

        Args:
            ui (WorldBuildingUI): The UI instance.
            model (Neo4jModel): The Neo4j model instance.
            config (Config): The configuration instance.

        Returns:
            WorldBuildingController: The initialized controller instance.

        Raises:
            RuntimeError: If controller initialization fails.
        """
        try:
            controller = WorldBuildingController(ui, model, config)
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
            self.setObjectName("WorldBuildingApp")
            self.setCentralWidget(self.components.ui)

            # Set window title with version
            self.setWindowTitle(f"NeoRealmBuilder {self.components.config.VERSION}")

            # Ensure transparency is properly set
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
            self.components.ui.setAttribute(
                Qt.WidgetAttribute.WA_TranslucentBackground, True
            )

            # Set window size
            self.resize(
                self.components.config.UI_WINDOW_WIDTH,
                self.components.config.UI_WINDOW_HEIGHT,
            )
            self.setMinimumSize(
                self.components.config.UI_WINDOW_WIDTH,
                self.components.config.UI_WINDOW_HEIGHT,
            )

            # Add Export menu to the main menu bar
            self._add_export_menu()

            structlog.get_logger().info(
                f"Window configured with size "
                f"{self.components.config.UI_WINDOW_WIDTH}x"
                f"{self.components.config.UI_WINDOW_HEIGHT}"
            )
        except Exception as e:
            raise RuntimeError(f"Failed to configure main window: {str(e)}")

    def _add_export_menu(self) -> None:
        """
        Add Export menu to the main menu bar.
        """
        menu_bar = self.menuBar()
        menu_bar.setObjectName("menuBar")

        export_menu = menu_bar.addMenu("Export")

        export_json_action = QAction("Export as JSON", self)
        export_json_action.triggered.connect(self.components.controller.export_as_json)
        export_menu.addAction(export_json_action)

        export_txt_action = QAction("Export as TXT", self)
        export_txt_action.triggered.connect(self.components.controller.export_as_txt)
        export_menu.addAction(export_txt_action)

        export_csv_action = QAction("Export as CSV", self)
        export_csv_action.triggered.connect(self.components.controller.export_as_csv)
        export_menu.addAction(export_csv_action)

        export_pdf_action = QAction("Export as PDF", self)
        export_pdf_action.triggered.connect(self.components.controller.export_as_pdf)
        export_menu.addAction(export_pdf_action)

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

            event.accept()
            structlog.get_logger().info("Application shutdown completed successfully")

        except Exception as e:
            structlog.get_logger().error(f"Error during application shutdown: {e}")
            event.accept()  # Still close the application


if __name__ == "__main__":
    try:
        app = QApplication(sys.argv)
        ex = WorldBuildingApp()
        sys.exit(app.exec())
    except Exception as e:
        structlog.get_logger().critical(
            "Unhandled exception in main loop", exc_info=True
        )
        sys.exit(1)
