import json
from typing import Dict, List, Tuple, Optional, Any
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QWidget, QLineEdit
from structlog import get_logger

from ui.components.map_component.line_container import LineContainer
from ui.components.map_component.pin_container import PinContainer
from utils.geometry_handler import GeometryHandler

logger = get_logger(__name__)


class FeatureManager(QObject):
    """Manages spatial features (pins, lines) on the map.
    
    Handles creation, deletion, styling, and batch operations for map features.
    """
    
    # Feature management signals
    feature_created = pyqtSignal(str, str)  # feature_type, target_node
    feature_deleted = pyqtSignal(str, str)  # feature_type, target_node
    feature_clicked = pyqtSignal(str)       # target_node
    
    def __init__(self, parent_container: QWidget, config=None):
        """Initialize the feature manager.
        
        Args:
            parent_container: Widget to contain all features
            config: Configuration object
        """
        super().__init__()
        self.parent_container = parent_container
        self.config = config
        
        # Feature storage
        self.pins: Dict[str, PinContainer] = {}
        self.lines: Dict[str, LineContainer] = {}
        
        # Current scale for features
        self.current_scale = 1.0
    
    def set_scale(self, scale: float) -> None:
        """Update scale for all features.
        
        Args:
            scale: New scale factor
        """
        self.current_scale = scale
        
        # Update existing features
        for pin in self.pins.values():
            pin.set_scale(scale)
        
        for line in self.lines.values():
            line.set_scale(scale)
            # Ensure the line container is visible and properly positioned
            line.show()
            line.raise_()
    
    def create_pin(self, target_node: str, x: int, y: int) -> None:
        """Create a pin feature.
        
        Args:
            target_node: Node name this pin represents
            x: Original x-coordinate
            y: Original y-coordinate
        """
        # Remove existing pin if it exists
        if target_node in self.pins:
            self.pins[target_node].deleteLater()
            del self.pins[target_node]
        
        # Create new pin container
        pin_container = PinContainer(target_node, self.parent_container, self.config)
        pin_container.pin_clicked.connect(self.feature_clicked.emit)
        pin_container.set_scale(self.current_scale)
        
        # Store original coordinates
        pin_container.original_x = x
        pin_container.original_y = y
        
        self.pins[target_node] = pin_container
        self._update_pin_position(target_node, x, y)
        pin_container.show()
        
        self.feature_created.emit("pin", target_node)
    
    def create_line(self, target_node: str, points: List[Tuple[int, int]], 
                   style_config: Optional[Dict[str, Any]] = None) -> None:
        """Create a line feature.
        
        Args:
            target_node: Node name this line represents
            points: List of coordinate points
            style_config: Optional style configuration
        """
        # Remove existing line if it exists
        if target_node in self.lines:
            self.lines[target_node].deleteLater()
            del self.lines[target_node]
        
        # Create new line container
        line_container = LineContainer(target_node, points, self.parent_container, self.config)
        line_container.line_clicked.connect(self.feature_clicked.emit)
        line_container.set_scale(self.current_scale)
        
        # Apply style if provided
        if style_config:
            line_container.set_style(
                color=style_config.get("color"),
                width=style_config.get("width"),
                pattern=style_config.get("pattern")
            )
        
        self.lines[target_node] = line_container
        line_container.show()
        line_container.raise_()
        
        self.feature_created.emit("line", target_node)
    
    def batch_create_pins(self, pin_data: List[Tuple[str, int, int]]) -> None:
        """Create multiple pins efficiently.
        
        Args:
            pin_data: List of (target_node, x, y) tuples
        """
        # Remove existing pins
        for target_node, _, _ in pin_data:
            if target_node in self.pins:
                self.pins[target_node].deleteLater()
                del self.pins[target_node]
        
        # Temporarily disable updates for performance
        self.parent_container.setUpdatesEnabled(False)
        
        try:
            for target_node, x, y in pin_data:
                pin_container = PinContainer(target_node, self.parent_container, self.config)
                pin_container.pin_clicked.connect(self.feature_clicked.emit)
                pin_container.set_scale(self.current_scale)
                pin_container.original_x = x
                pin_container.original_y = y
                self.pins[target_node] = pin_container
                self._update_pin_position(target_node, x, y)
                pin_container.show()
        finally:
            self.parent_container.setUpdatesEnabled(True)
            self.parent_container.update()
    
    def batch_create_lines(self, line_data: List[Tuple[str, List[Tuple[int, int]], Dict[str, Any]]]) -> None:
        """Create multiple lines efficiently.
        
        Args:
            line_data: List of (target_node, points, style_config) tuples
        """
        # Remove existing lines
        for target_node, _, _ in line_data:
            if target_node in self.lines:
                self.lines[target_node].deleteLater()
                del self.lines[target_node]
        
        # Temporarily disable updates for performance
        self.parent_container.setUpdatesEnabled(False)
        
        try:
            for target_node, points, style_config in line_data:
                line_container = LineContainer(target_node, points, self.parent_container, self.config)
                line_container.line_clicked.connect(self.feature_clicked.emit)
                line_container.set_scale(self.current_scale)
                
                # Apply style
                if style_config:
                    line_container.set_style(
                        color=style_config.get("color"),
                        width=style_config.get("width"),
                        pattern=style_config.get("pattern")
                    )
                
                self.lines[target_node] = line_container
                line_container.show()
                line_container.raise_()
        finally:
            self.parent_container.setUpdatesEnabled(True)
            self.parent_container.update()
    
    def update_positions(self, parent_map_tab) -> None:
        """Update positions of all features based on current scale and viewport."""
        # Update pin positions
        for target_node, pin in self.pins.items():
            if hasattr(pin, "original_x") and hasattr(pin, "original_y"):
                self._update_pin_position_with_viewport(target_node, pin.original_x, pin.original_y, parent_map_tab)
        
        # Update line positions - lines handle their own geometry updates through set_scale
        # but we need to ensure they're properly visible
        for line_container in self.lines.values():
            line_container.raise_()
            line_container.show()
    
    def _update_pin_position(self, target_node: str, x: int, y: int) -> None:
        """Update position of a single pin (basic version)."""
        if target_node not in self.pins:
            return
        
        pin_container = self.pins[target_node]
        
        # Calculate scaled position
        scaled_x = x * self.current_scale
        scaled_y = y * self.current_scale
        
        # Basic positioning (will be enhanced by viewport-aware version)
        pin_container.move(int(scaled_x), int(scaled_y))
        pin_container.raise_()
    
    def _update_pin_position_with_viewport(self, target_node: str, x: int, y: int, parent_map_tab) -> None:
        """Update position of a single pin with viewport awareness."""
        if target_node not in self.pins:
            return
        
        pin_container = self.pins[target_node]
        
        # Get viewport dimensions
        viewport_width = parent_map_tab.scroll_area.viewport().width()
        viewport_height = parent_map_tab.scroll_area.viewport().height()
        
        # Calculate scaled position
        scaled_x = x * self.current_scale
        scaled_y = y * self.current_scale
        
        # Account for image centering in viewport
        if pixmap := parent_map_tab.image_label.pixmap():
            image_width = pixmap.width()
            image_height = pixmap.height()
            if image_width < viewport_width:
                scaled_x += (viewport_width - image_width) / 2
            if image_height < viewport_height:
                scaled_y += (viewport_height - image_height) / 2
        
        # Position pin (align bottom with coordinate)
        pin_x = int(scaled_x - (pin_container.pin_svg.width() / 2))
        pin_y = int(scaled_y - pin_container.pin_svg.height())
        
        pin_container.move(pin_x, pin_y)
        pin_container.raise_()
        pin_container.show()
    
    def clear_all_features(self) -> None:
        """Remove all features."""
        self.clear_pins()
        self.clear_lines()
    
    def clear_pins(self) -> None:
        """Remove all pins."""
        for pin in self.pins.values():
            pin.deleteLater()
        self.pins.clear()
    
    def clear_lines(self) -> None:
        """Remove all lines."""
        for line in self.lines.values():
            line.deleteLater()
        self.lines.clear()
    
    def set_edit_mode(self, active: bool) -> None:
        """Set edit mode for all line features.
        
        Args:
            active: Whether edit mode should be active
        """
        for line_container in self.lines.values():
            line_container.set_edit_mode(active)
    
    def get_feature_count(self) -> Dict[str, int]:
        """Get count of features by type.
        
        Returns:
            Dictionary with feature counts
        """
        return {
            "pins": len(self.pins),
            "lines": len(self.lines)
        }
