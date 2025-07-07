"""Feature manager for graphics-based map items."""

from typing import Dict, Optional, Any, List, Tuple

from PyQt6.QtCore import QObject, pyqtSignal
from structlog import get_logger

from .map_graphics_scene import MapGraphicsScene
from .signal_bridge import GraphicsSignalBridge
from .coordinate_mapper import GraphicsCoordinateMapper

logger = get_logger(__name__)


class GraphicsFeatureManager(QObject):
    """Manages graphics items representing map features.
    
    This is the graphics equivalent of the widget-based FeatureManager,
    handling creation, removal, and lifecycle of graphics items.
    """
    
    # Manager signals (compatible with existing FeatureManager)
    feature_added = pyqtSignal(str, str)  # feature_type, node_name
    feature_removed = pyqtSignal(str)  # node_name
    all_features_cleared = pyqtSignal()
    
    def __init__(self, scene: MapGraphicsScene, parent=None):
        """Initialize the graphics feature manager.
        
        Args:
            scene: The graphics scene to manage features in
            parent: Parent object
        """
        super().__init__(parent)
        self.scene = scene
        self.signal_bridge = GraphicsSignalBridge(self)
        self.coordinate_mapper = GraphicsCoordinateMapper()
        
        # Feature tracking
        self.features: Dict[str, Any] = {}  # node_name -> graphics item
        self.feature_types: Dict[str, str] = {}  # node_name -> feature type
        
        # Edit mode state
        self.edit_mode_enabled = False
        
        # Connect to scene changes
        self.scene.image_loaded.connect(self._on_image_loaded)
        
        logger.info("GraphicsFeatureManager initialized")
    
    def _get_config_dict(self) -> Dict[str, Any]:
        """Get configuration as dictionary for graphics items.
        
        Returns:
            Configuration dictionary
        """
        # If scene has a parent view that has a parent map tab with config
        if hasattr(self.scene, 'parent') and self.scene.parent():
            parent = self.scene.parent()
            if hasattr(parent, 'parent') and hasattr(parent.parent(), 'config'):
                config_obj = parent.parent().config
                # Convert config object to dict format expected by graphics items
                return {
                    'map': {
                        'PIN_SVG_SOURCE': getattr(config_obj.map, 'PIN_SVG_SOURCE', ''),
                        'BASE_PIN_WIDTH': getattr(config_obj.map, 'BASE_PIN_WIDTH', 24),
                        'BASE_PIN_HEIGHT': getattr(config_obj.map, 'BASE_PIN_HEIGHT', 32),
                        'MIN_PIN_WIDTH': getattr(config_obj.map, 'MIN_PIN_WIDTH', 12),
                        'MIN_PIN_HEIGHT': getattr(config_obj.map, 'MIN_PIN_HEIGHT', 16),
                    }
                }
        
        # Fallback defaults
        return {
            'map': {
                'PIN_SVG_SOURCE': 'src/resources/graphics/NWB_Map_Pin.svg',
                'BASE_PIN_WIDTH': 24,
                'BASE_PIN_HEIGHT': 32,
                'MIN_PIN_WIDTH': 12,
                'MIN_PIN_HEIGHT': 16,
            }
        }
    
    def _on_image_loaded(self, path: str, width: int, height: int) -> None:
        """Handle image loading in scene.
        
        Args:
            path: Image path
            width: Image width
            height: Image height
        """
        self.coordinate_mapper.update_scene_dimensions(width, height)
        logger.debug(f"Updated coordinate mapper for image: {width}x{height}")
    
    def add_pin_feature(self, node_name: str, x: int, y: int,
                       properties: Optional[Dict[str, Any]] = None) -> Any:
        """Add a pin feature to the scene.
        
        Args:
            node_name: Name of the node
            x: X coordinate in original image space
            y: Y coordinate in original image space
            properties: Additional properties for the pin
            
        Returns:
            The created graphics item
        """
        # Import here to avoid circular imports
        from .pin_graphics_item import PinGraphicsItem
        
        # Remove existing feature if present
        if node_name in self.features:
            self.remove_feature(node_name)
        
        # Create pin graphics item
        pin_item = PinGraphicsItem(
            target_node=node_name,
            x=x,
            y=y,
            config=self._get_config_dict()
        )
        
        # Set edit mode if currently enabled
        pin_item.set_edit_mode(self.edit_mode_enabled)
        
        # Add to scene and track
        self.scene.add_feature_item(node_name, pin_item)
        self.features[node_name] = pin_item
        self.feature_types[node_name] = 'pin'
        
        # Connect to signal bridge
        self.signal_bridge.connect_graphics_item(node_name, pin_item)
        
        self.feature_added.emit('pin', node_name)
        logger.info(f"Created pin feature: {node_name} at ({x}, {y})")
        
        return pin_item
    
    def add_line_feature(self, node_name: str, points: List[Tuple[int, int]],
                        properties: Optional[Dict[str, Any]] = None) -> Any:
        """Add a line feature to the scene.
        
        Args:
            node_name: Name of the node
            points: List of (x, y) coordinates in original image space
            properties: Additional properties for the line
            
        Returns:
            The created graphics item
        """
        # Import here to avoid circular imports
        from .line_graphics_item import LineGraphicsItem
        
        # Remove existing feature if present
        if node_name in self.features:
            self.remove_feature(node_name)
        
        # Create line graphics item
        logger.debug(f"Creating line graphics item for {node_name} with style properties: {properties}")
        line_item = LineGraphicsItem(
            target_node=node_name,
            points_or_branches=points,
            config=self._get_config_dict(),
            style_properties=properties
        )
        
        # Set edit mode if currently enabled
        line_item.set_edit_mode(self.edit_mode_enabled)
        
        # Add to scene and track
        self.scene.add_feature_item(node_name, line_item)
        self.features[node_name] = line_item
        self.feature_types[node_name] = 'line'
        
        # Connect to signal bridge
        self.signal_bridge.connect_graphics_item(node_name, line_item)
        
        self.feature_added.emit('line', node_name)
        logger.info(f"Created line feature: {node_name} with {len(points)} points")
        
        return line_item
    
    def add_branching_line_feature(self, node_name: str, branches: List[List[Tuple[int, int]]],
                                  properties: Optional[Dict[str, Any]] = None) -> Any:
        """Add a branching line feature to the scene.
        
        Args:
            node_name: Name of the node
            branches: List of branches, each containing (x, y) coordinates
            properties: Additional properties for the line
            
        Returns:
            The created graphics item
        """
        # Import here to avoid circular imports
        from .line_graphics_item import LineGraphicsItem
        
        # Remove existing feature if present
        if node_name in self.features:
            self.remove_feature(node_name)
        
        # Create branching line graphics item
        line_item = LineGraphicsItem(
            target_node=node_name,
            points_or_branches=branches,
            config=self._get_config_dict(),
            style_properties=properties
        )
        
        # Set edit mode if currently enabled
        line_item.set_edit_mode(self.edit_mode_enabled)
        
        # Add to scene and track
        self.scene.add_feature_item(node_name, line_item)
        self.features[node_name] = line_item
        self.feature_types[node_name] = 'branching_line'
        
        # Connect to signal bridge
        self.signal_bridge.connect_graphics_item(node_name, line_item)
        
        self.feature_added.emit('branching_line', node_name)
        logger.info(f"Created branching line feature: {node_name} with {len(branches)} branches")
        
        return line_item
    
    def remove_feature(self, node_name: str) -> None:
        """Remove a feature from the scene.
        
        Args:
            node_name: Name of the node to remove
        """
        if node_name in self.features:
            item = self.features[node_name]
            
            # Disconnect signals
            self.signal_bridge.disconnect_graphics_item(node_name)
            
            # Remove from scene
            self.scene.remove_feature_item(node_name)
            
            # Remove from tracking
            del self.features[node_name]
            if node_name in self.feature_types:
                del self.feature_types[node_name]
            
            self.feature_removed.emit(node_name)
            logger.debug(f"Removed feature: {node_name}")
    
    def clear_all_features(self) -> None:
        """Remove all features from the scene."""
        # Copy list to avoid modification during iteration
        node_names = list(self.features.keys())
        
        for node_name in node_names:
            self.remove_feature(node_name)
        
        self.signal_bridge.clear_all_connections()
        self.all_features_cleared.emit()
        logger.info("Cleared all features")
    
    def get_feature(self, node_name: str) -> Optional[Any]:
        """Get a feature by node name.
        
        Args:
            node_name: Name of the node
            
        Returns:
            The graphics item or None
        """
        return self.features.get(node_name)
    
    def get_feature_type(self, node_name: str) -> Optional[str]:
        """Get the type of a feature.
        
        Args:
            node_name: Name of the node
            
        Returns:
            Feature type string or None
        """
        return self.feature_types.get(node_name)
    
    def set_edit_mode(self, enabled: bool) -> None:
        """Enable or disable edit mode for all features.
        
        Args:
            enabled: Whether to enable edit mode
        """
        self.edit_mode_enabled = enabled
        self.signal_bridge.emit_edit_mode_changed(enabled)
        
        # Update all features
        for item in self.features.values():
            if hasattr(item, 'set_edit_mode'):
                item.set_edit_mode(enabled)
        
        logger.info(f"Edit mode {'enabled' if enabled else 'disabled'}")
    
    def update_feature_geometry(self, node_name: str, 
                               geometry: List[Tuple[int, int]]) -> None:
        """Update the geometry of a feature.
        
        Args:
            node_name: Name of the node
            geometry: New geometry as list of (x, y) tuples
        """
        if node_name in self.features:
            item = self.features[node_name]
            if hasattr(item, 'update_geometry'):
                item.update_geometry(geometry)
                logger.debug(f"Updated geometry for: {node_name}")
    
    def get_features_at_point(self, x: int, y: int) -> List[str]:
        """Get all features at a specific point.
        
        Args:
            x: X coordinate in original image space
            y: Y coordinate in original image space
            
        Returns:
            List of node names at that point
        """
        scene_point = self.coordinate_mapper.original_to_scene(x, y)
        items = self.scene.items(scene_point)
        
        result = []
        for item in items:
            # Find which feature this item belongs to
            for node_name, feature_item in self.features.items():
                if feature_item == item:
                    result.append(node_name)
                    break
        
        return result
    
    def get_all_features(self) -> Dict[str, Any]:
        """Get all features.
        
        Returns:
            Dictionary of node_name -> graphics item
        """
        return self.features.copy()
    
    def get_feature_count(self) -> int:
        """Get the number of features.
        
        Returns:
            Number of features
        """
        return len(self.features)