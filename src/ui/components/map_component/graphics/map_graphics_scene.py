"""Map graphics scene for managing map content and coordinate transformations."""

from typing import Optional, Tuple, Dict, Any

from PyQt6.QtCore import Qt, pyqtSignal, QPointF, QRectF
from PyQt6.QtGui import QPixmap, QImage, QPainter
from PyQt6.QtWidgets import QGraphicsScene, QGraphicsPixmapItem
from structlog import get_logger

logger = get_logger(__name__)


class MapGraphicsScene(QGraphicsScene):
    """Graphics scene for map content management.
    
    Handles:
    - Background image rendering
    - Coordinate system transformations
    - Feature item management
    - Scene bounds and scaling
    """
    
    # Scene signals
    image_loaded = pyqtSignal(str, int, int)  # path, width, height
    scene_cleared = pyqtSignal()
    
    def __init__(self, parent=None):
        """Initialize the map graphics scene.
        
        Args:
            parent: Parent object
        """
        super().__init__(parent)
        
        # Background image management
        self.background_item: Optional[QGraphicsPixmapItem] = None
        self.original_image: Optional[QImage] = None
        self.image_path: Optional[str] = None
        
        # Coordinate transformation state
        self.image_width = 0
        self.image_height = 0
        self.scene_scale = 1.0  # For high-DPI or custom scaling
        
        # Feature tracking
        self.feature_items: Dict[str, Any] = {}  # node_name -> graphics item
        
        logger.info("MapGraphicsScene initialized")
    
    def load_map_image(self, image_path: str) -> bool:
        """Load a map image as the scene background.
        
        Args:
            image_path: Path to the image file
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Load the image
            image = QImage(image_path)
            if image.isNull():
                logger.error(f"Failed to load image: {image_path}")
                return False
            
            # Store original image for reference
            self.original_image = image
            self.image_path = image_path
            self.image_width = image.width()
            self.image_height = image.height()
            
            # Create pixmap from image
            pixmap = QPixmap.fromImage(image)
            
            # Remove old background if exists
            if self.background_item:
                self.removeItem(self.background_item)
            
            # Add new background
            self.background_item = self.addPixmap(pixmap)
            self.background_item.setZValue(-1000)  # Ensure it's always behind
            
            # Update scene rect to match image
            self.setSceneRect(0, 0, self.image_width, self.image_height)
            
            logger.info(f"Loaded map image: {image_path} ({self.image_width}x{self.image_height})")
            self.image_loaded.emit(image_path, self.image_width, self.image_height)
            
            return True
            
        except Exception as e:
            logger.error(f"Error loading map image: {e}")
            return False
    
    def clear_map(self) -> None:
        """Clear all map content including background and features."""
        # Clear all items
        self.clear()
        
        # Reset state
        self.background_item = None
        self.original_image = None
        self.image_path = None
        self.image_width = 0
        self.image_height = 0
        self.feature_items.clear()
        
        self.scene_cleared.emit()
        logger.info("Map scene cleared")
    
    # Coordinate transformation methods
    def scene_to_original_coords(self, scene_point: QPointF) -> Tuple[int, int]:
        """Convert scene coordinates to original image coordinates.
        
        Args:
            scene_point: Point in scene coordinates
            
        Returns:
            Tuple of (x, y) in original image coordinates
        """
        # Scene coordinates are 1:1 with image pixels by design
        x = int(scene_point.x())
        y = int(scene_point.y())
        
        # Clamp to image bounds
        x = max(0, min(x, self.image_width - 1))
        y = max(0, min(y, self.image_height - 1))
        
        return x, y
    
    def original_to_scene_coords(self, x: int, y: int) -> QPointF:
        """Convert original image coordinates to scene coordinates.
        
        Args:
            x: X coordinate in original image
            y: Y coordinate in original image
            
        Returns:
            Point in scene coordinates
        """
        # Direct mapping since we use 1:1 scale
        return QPointF(float(x), float(y))
    
    def add_feature_item(self, node_name: str, item: Any) -> None:
        """Add a feature item to the scene and track it.
        
        Args:
            node_name: Name of the node this feature represents
            item: The graphics item to add
        """
        # Remove old item if exists
        if node_name in self.feature_items:
            old_item = self.feature_items[node_name]
            self.removeItem(old_item)
        
        # Add new item
        self.addItem(item)
        self.feature_items[node_name] = item
        
        logger.debug(f"Added feature item for node: {node_name}")
    
    def remove_feature_item(self, node_name: str) -> None:
        """Remove a feature item from the scene.
        
        Args:
            node_name: Name of the node to remove
        """
        if node_name in self.feature_items:
            item = self.feature_items[node_name]
            self.removeItem(item)
            del self.feature_items[node_name]
            logger.debug(f"Removed feature item for node: {node_name}")
    
    def get_feature_item(self, node_name: str) -> Optional[Any]:
        """Get a feature item by node name.
        
        Args:
            node_name: Name of the node
            
        Returns:
            The graphics item or None if not found
        """
        return self.feature_items.get(node_name)
    
    def set_background_opacity(self, opacity: float) -> None:
        """Set the opacity of the background image.
        
        Args:
            opacity: Opacity value between 0.0 and 1.0
        """
        if self.background_item:
            self.background_item.setOpacity(opacity)
    
    def get_image_bounds(self) -> QRectF:
        """Get the bounds of the loaded image.
        
        Returns:
            Rectangle representing image bounds in scene coordinates
        """
        if self.image_width > 0 and self.image_height > 0:
            return QRectF(0, 0, self.image_width, self.image_height)
        return QRectF()
    
    def is_point_in_bounds(self, x: int, y: int) -> bool:
        """Check if a point is within the image bounds.
        
        Args:
            x: X coordinate
            y: Y coordinate
            
        Returns:
            True if point is within bounds
        """
        return 0 <= x < self.image_width and 0 <= y < self.image_height