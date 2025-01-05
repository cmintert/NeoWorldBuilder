import atexit
import json
import os
import shutil
import subprocess
import sys
import uuid
from pathlib import Path
from tempfile import mkdtemp

import structlog

# Configure structlog
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer(),
    ]
)


class DeploymentPreparator:
    """Handles preparation of NeoWorldBuilder for deployment"""

    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.build_dir = project_root / "build"
        self.dist_dir = project_root / "dist"
        self.src_config_dir = project_root / "src" / "config"

        # Create temporary directory for deployment configs
        self.temp_dir = Path(mkdtemp())
        self.temp_config_dir = self.temp_dir / "config"

        # Initialize logger with trace ID
        self.trace_id = str(uuid.uuid4())
        self.logger = structlog.get_logger().bind(
            trace_id=self.trace_id, module="DeploymentPreparator"
        )

        # Register cleanup
        atexit.register(self._cleanup_temp)

        self.logger.info(
            "deployment_preparator_initialized", project_root=str(project_root)
        )

    def prepare_environment(self) -> None:
        """Prepares the environment for deployment"""
        self.logger.info("preparing_environment")

        try:
            # Create clean directories
            self._clean_build_directories()

            # Verify required Python version
            self._verify_python_version()

            # Install required deployment tools
            self._install_deployment_tools()

            # Prepare temporary config directory with clean configs
            self._prepare_deployment_configs()

            self.logger.info("environment_preparation_completed")

        except Exception as e:
            self.logger.error(
                "environment_preparation_failed", error=str(e), exc_info=True
            )
            raise

    def _clean_build_directories(self) -> None:
        """Removes and recreates build and dist directories"""
        for directory in [self.build_dir, self.dist_dir]:
            self.logger.debug("cleaning_directory", directory=str(directory))
            if directory.exists():
                shutil.rmtree(directory)
            directory.mkdir(exist_ok=True)

    def _verify_python_version(self) -> None:
        """Verifies Python version meets requirements"""
        required_version = (3, 12)
        current_version = sys.version_info[:2]

        self.logger.debug(
            "verifying_python_version",
            required=f"{required_version[0]}.{required_version[1]}",
            current=f"{current_version[0]}.{current_version[1]}",
        )

        if current_version < required_version:
            self.logger.error(
                "python_version_check_failed",
                required=f"{required_version[0]}.{required_version[1]}",
                current=f"{current_version[0]}.{current_version[1]}",
            )
            raise RuntimeError(
                f"Python {required_version[0]}.{required_version[1]} or higher is required. "
                f"Current version: {current_version[0]}.{current_version[1]}"
            )

    def _install_deployment_tools(self) -> None:
        """Installs required deployment tools"""
        required_tools = ["pyinstaller"]

        for tool in required_tools:
            self.logger.info("installing_tool", tool=tool)
            try:
                subprocess.run(
                    [sys.executable, "-m", "pip", "install", "--upgrade", tool],
                    check=True,
                    capture_output=True,
                    text=True,
                )
            except subprocess.CalledProcessError as e:
                self.logger.error(
                    "tool_installation_failed",
                    tool=tool,
                    error=str(e),
                    stdout=e.stdout,
                    stderr=e.stderr,
                )
                raise

    def _prepare_deployment_configs(self) -> None:
        """Creates clean configuration files for deployment in temporary directory"""
        self.logger.info(
            "preparing_deployment_configs", temp_dir=str(self.temp_config_dir)
        )

        # Create temporary config directory and styles subdirectory
        self.temp_config_dir.mkdir(parents=True, exist_ok=True)
        styles_dir = self.temp_config_dir / "styles"
        styles_dir.mkdir(exist_ok=True)

        # Copy styles directory content
        src_styles_dir = self.src_config_dir / "styles"
        if src_styles_dir.exists():
            shutil.copytree(src_styles_dir, styles_dir, dirs_exist_ok=True)

        config_files = {
            "system.json": {
                "remove_keys": ["KEY"],
                "set_values": {"ENVIRONMENT": "production"},
            },
            "database.json": {"clean_keys": ["PASSWORD"]},
            "logging.json": {},
            "limits.json": {},
            "ui.json": {},
        }

        # Copy and clean configs
        for config_file, operations in config_files.items():
            src_path = self.src_config_dir / config_file
            if not src_path.exists():
                self.logger.warning("config_file_missing", file=config_file)
                continue

            self.logger.debug(
                "processing_config_file", file=config_file, operations=operations
            )

            # Read original config
            with open(src_path, "r") as f:
                config = json.load(f)

            # Create clean version
            clean_config = config.copy()

            # Remove specified keys
            for key in operations.get("remove_keys", []):
                if key in clean_config:
                    self.logger.debug("removing_key", file=config_file, key=key)
                    clean_config.pop(key)

            # Clean specified keys
            for key in operations.get("clean_keys", []):
                if key in clean_config:
                    self.logger.debug("cleaning_key", file=config_file, key=key)
                    clean_config[key] = ""

            # Set specified values
            for key, value in operations.get("set_values", {}).items():
                self.logger.debug(
                    "setting_value", file=config_file, key=key, value=value
                )
                clean_config[key] = value

            # Save cleaned config to temporary directory
            dest_path = self.temp_config_dir / config_file
            with open(dest_path, "w") as f:
                json.dump(clean_config, f, indent=4)

    def _cleanup_temp(self) -> None:
        """Cleans up temporary directory"""
        if self.temp_dir.exists():
            self.logger.info(
                "cleaning_temporary_directory", temp_dir=str(self.temp_dir)
            )
            shutil.rmtree(self.temp_dir)

    def create_deployment(self) -> None:
        """Creates the deployment using PyInstaller"""
        spec_file = self.project_root / "NeoWorldBuilder.spec"

        if not spec_file.exists():
            self.logger.error("spec_file_not_found", spec_file=str(spec_file))
            raise FileNotFoundError(f"Spec file not found: {spec_file}")

        self.logger.info("starting_deployment_creation", spec_file=str(spec_file))

        # Set environment variable for PyInstaller to use temp config directory
        os.environ["NEOWORLDBUILDER_DEPLOY_CONFIG"] = str(self.temp_config_dir)

        try:
            # Run PyInstaller
            result = subprocess.run(
                ["pyinstaller", "--clean", "--noconfirm", str(spec_file)],
                check=True,
                capture_output=True,
                text=True,
            )
            self.logger.info("deployment_creation_completed")

        except subprocess.CalledProcessError as e:
            self.logger.error(
                "deployment_creation_failed",
                error=str(e),
                stdout=e.stdout,
                stderr=e.stderr,
            )
            raise


def main():
    # Initialize logger for main
    logger = structlog.get_logger().bind(module="deploy.py", function="main")

    logger.info("deployment_script_started")

    # Get project root (assuming script is in project root)
    project_root = Path(__file__).parent

    try:
        # Create deployment preparator
        preparator = DeploymentPreparator(project_root)

        # Prepare environment
        preparator.prepare_environment()

        # Create deployment
        preparator.create_deployment()

        logger.info("deployment_process_completed")

    except Exception as e:
        logger.error("deployment_process_failed", error=str(e), exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
