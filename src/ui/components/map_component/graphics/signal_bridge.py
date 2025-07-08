"""Signal bridging system for graphics-widget compatibility."""

from typing import Optional, Dict, Any

from PyQt6.QtCore import QObject, pyqtSignal
from structlog import get_logger

logger = get_logger(__name__)


class GraphicsSignalBridge(QObject):
    """Bridges signals between graphics items and the legacy widget system.
    
    This ensures that graphics items can emit the same signals that widgets
    did, maintaining compatibility with existing controllers and handlers.
    """
    
    # Feature interaction signals (matching existing FeatureManager)
    feature_clicked = pyqtSignal(str)  # node_name
    feature_created = pyqtSignal(str, str)  # feature_type, node_name
    feature_removed = pyqtSignal(str)  # node_name
    geometry_changed = pyqtSignal(str, list)  # node_name, geometry
    
    # Pin-specific signals
    pin_clicked = pyqtSignal(str)  # node_name
    pin_moved = pyqtSignal(str, int, int)  # node_name, x, y
    pin_context_menu_requested = pyqtSignal(str, int, int)  # node_name, x, y
    
    # Line-specific signals
    line_clicked = pyqtSignal(str)  # node_name
    line_geometry_changed = pyqtSignal(str, list)  # node_name, points
    control_point_moved = pyqtSignal(str, int, int, int, int)  # node, branch, point, x, y
    line_segment_inserted = pyqtSignal(str, int, int)  # node, branch, segment
    control_point_removed = pyqtSignal(str, int, int)  # node, branch, point
    
    # Edit mode signals
    edit_mode_changed = pyqtSignal(bool)  # enabled
    feature_selection_changed = pyqtSignal(str, bool)  # node_name, selected
    
    def __init__(self, parent=None):
        """Initialize the signal bridge.
        
        Args:
            parent: Parent object
        """
        super().__init__(parent)
        self.connected_items: Dict[str, Any] = {}  # Track connected graphics items
        
    def connect_graphics_item(self, node_name: str, graphics_item: Any) -> None:
        """Connect a graphics item's signals to the bridge.
        
        Args:
            node_name: Name of the node this item represents
            graphics_item: The QGraphicsItem with signals to connect
        """
        # Store reference
        self.connected_items[node_name] = graphics_item
        
        # Connect item signals to bridge signals based on item type
        if hasattr(graphics_item, 'clicked'):
            graphics_item.clicked.connect(lambda: self.feature_clicked.emit(node_name))
            
        if hasattr(graphics_item, 'geometry_changed'):
            graphics_item.geometry_changed.connect(
                lambda geom: self.geometry_changed.emit(node_name, geom)
            )
            
        # Type-specific connections
        item_type = getattr(graphics_item, 'feature_type', 'unknown')
        
        if item_type == 'pin':
            self._connect_pin_signals(node_name, graphics_item)
        elif item_type in ['line', 'branching_line']:
            self._connect_line_signals(node_name, graphics_item)
            
        logger.debug(f"Connected graphics item signals for: {node_name}")
    
    def _connect_pin_signals(self, node_name: str, pin_item: Any) -> None:
        """Connect pin-specific signals.
        
        Args:
            node_name: Node name
            pin_item: Pin graphics item
        """
        # PinGraphicsItem doesn't have Qt signals, it emits through the bridge directly
        # The signals are emitted from within the item's event handlers
        # So we just need to track the item for signal emission
        logger.debug(f"Pin item connected for signal routing: {node_name}")
    
    def _connect_line_signals(self, node_name: str, line_item: Any) -> None:
        """Connect line-specific signals.
        
        Args:
            node_name: Node name
            line_item: Line graphics item
        """
        if hasattr(line_item, 'clicked'):
            line_item.clicked.connect(lambda: self.line_clicked.emit(node_name))
            
        if hasattr(line_item, 'geometry_changed'):
            line_item.geometry_changed.connect(
                lambda points: self.line_geometry_changed.emit(node_name, points)
            )
            
        if hasattr(line_item, 'control_point_moved'):
            line_item.control_point_moved.connect(
                lambda b, p, x, y: self.control_point_moved.emit(node_name, b, p, x, y)
            )
            
        if hasattr(line_item, 'segment_point_inserted'):
            line_item.segment_point_inserted.connect(
                lambda b, s: self.line_segment_inserted.emit(node_name, b, s)
            )
            
        if hasattr(line_item, 'control_point_removed'):
            line_item.control_point_removed.connect(
                lambda b, p: self.control_point_removed.emit(node_name, b, p)
            )
    
    def disconnect_graphics_item(self, node_name: str) -> None:
        """Disconnect a graphics item from the bridge.
        
        Args:
            node_name: Name of the node to disconnect
        """
        if node_name in self.connected_items:
            # Qt automatically disconnects signals when object is deleted
            # Just remove from tracking
            del self.connected_items[node_name]
            logger.debug(f"Disconnected graphics item: {node_name}")
    
    def emit_feature_created(self, feature_type: str, node_name: str) -> None:
        """Emit feature created signal.
        
        Args:
            feature_type: Type of feature created
            node_name: Name of the node
        """
        self.feature_created.emit(feature_type, node_name)
    
    def emit_feature_removed(self, node_name: str) -> None:
        """Emit feature removed signal.
        
        Args:
            node_name: Name of the removed node
        """
        self.feature_removed.emit(node_name)
        self.disconnect_graphics_item(node_name)
    
    def emit_edit_mode_changed(self, enabled: bool) -> None:
        """Emit edit mode change signal.
        
        Args:
            enabled: Whether edit mode is enabled
        """
        self.edit_mode_changed.emit(enabled)
        # Notify all connected items about edit mode change
        for item in self.connected_items.values():
            if hasattr(item, 'set_edit_mode'):
                item.set_edit_mode(enabled)
    
    def get_connected_item(self, node_name: str) -> Optional[Any]:
        """Get a connected graphics item by node name.
        
        Args:
            node_name: Name of the node
            
        Returns:
            The graphics item or None
        """
        return self.connected_items.get(node_name)
    
    def clear_all_connections(self) -> None:
        """Clear all signal connections."""
        self.connected_items.clear()
        logger.info("Cleared all signal bridge connections")