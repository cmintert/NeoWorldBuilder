"""Optional logging configuration wrapper for map component.

This module provides enhanced logging configuration specifically for the map component,
allowing runtime control of logging levels and performance optimization.

Falls back gracefully to standard structlog behavior if configuration fails.
"""

import os
import json
from typing import Optional, Dict, Any
from pathlib import Path

try:
    from structlog import get_logger as _get_logger
    
    # Try to load logging configuration
    _config = None
    _logging_config_path = Path(__file__).parent.parent.parent.parent.parent / "config" / "logging.json"
    
    if _logging_config_path.exists():
        try:
            with open(_logging_config_path, 'r') as f:
                _config = json.load(f)
        except (json.JSONDecodeError, IOError):
            # Fall back to default behavior if config loading fails
            pass
    
    # Default configuration if file loading fails
    if _config is None:
        _config = {
            "LOGGING_LEVEL": "INFO",
            "LOGGING_FORMAT": "json"
        }
    
    # Environment variable override support
    _effective_level = os.environ.get("MAP_COMPONENT_LOG_LEVEL", _config.get("LOGGING_LEVEL", "INFO"))
    
    class MapLogger:
        """Enhanced logger wrapper for map component with configurable levels."""
        
        def __init__(self, name: str):
            self._logger = _get_logger(name)
            self._name = name
            self._level_map = {
                "DEBUG": 10,
                "INFO": 20, 
                "WARNING": 30,
                "ERROR": 40
            }
            self._effective_level_num = self._level_map.get(_effective_level.upper(), 20)
        
        def _should_log(self, level: str) -> bool:
            """Check if message should be logged based on current level."""
            level_num = self._level_map.get(level.upper(), 20)
            return level_num >= self._effective_level_num
        
        def debug(self, message: str, **kwargs) -> None:
            """Log debug message if debug level is enabled."""
            if self._should_log("DEBUG"):
                self._logger.debug(message, **kwargs)
        
        def info(self, message: str, **kwargs) -> None:
            """Log info message if info level or higher is enabled."""
            if self._should_log("INFO"):
                self._logger.info(message, **kwargs)
        
        def warning(self, message: str, **kwargs) -> None:
            """Log warning message if warning level or higher is enabled."""
            if self._should_log("WARNING"):
                self._logger.warning(message, **kwargs)
        
        def error(self, message: str, **kwargs) -> None:
            """Log error message (always logged)."""
            self._logger.error(message, **kwargs)
    
    def get_map_logger(name: str) -> MapLogger:
        """Get a configurable logger for map component.
        
        Args:
            name: Logger name (typically __name__)
            
        Returns:
            MapLogger instance with configurable level support
        """
        return MapLogger(name)

except ImportError:
    # Fallback if structlog is not available - should not happen in this project
    def get_map_logger(name: str):
        """Fallback logger that does nothing."""
        class NoOpLogger:
            def debug(self, message: str, **kwargs): pass
            def info(self, message: str, **kwargs): pass  
            def warning(self, message: str, **kwargs): pass
            def error(self, message: str, **kwargs): pass
        return NoOpLogger()


# For backwards compatibility, export standard get_logger as well
def get_logger(name: str):
    """Standard logger - maintains existing API."""
    return _get_logger(name)