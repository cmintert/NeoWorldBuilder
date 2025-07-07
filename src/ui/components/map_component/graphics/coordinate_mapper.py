"""Coordinate mapping utilities for graphics-based map system."""

from typing import Tuple, List

from PyQt6.QtCore import QPointF, QRectF
from structlog import get_logger

logger = get_logger(__name__)


class GraphicsCoordinateMapper:
    """Handles coordinate transformations for the graphics system.
    
    Manages conversions between:
    - Original image coordinates (pixels in source image)
    - Scene coordinates (QGraphicsScene coordinate system)
    - View coordinates (QGraphicsView widget coordinates)
    - Item coordinates (local to QGraphicsItem)
    """
    
    def __init__(self, scene_width: int = 0, scene_height: int = 0):
        """Initialize the coordinate mapper.
        
        Args:
            scene_width: Width of the scene (typically image width)
            scene_height: Height of the scene (typically image height)
        """
        self.scene_width = scene_width
        self.scene_height = scene_height
        self.scale_factor = 1.0  # For future high-DPI support
    
    def update_scene_dimensions(self, width: int, height: int) -> None:
        """Update scene dimensions (usually when loading a new image).
        
        Args:
            width: New scene width
            height: New scene height
        """
        self.scene_width = width
        self.scene_height = height
        logger.debug(f"Updated scene dimensions: {width}x{height}")
    
    # Original <-> Scene conversions (currently 1:1 but abstracted for flexibility)
    def original_to_scene(self, x: int, y: int) -> QPointF:
        """Convert original image coordinates to scene coordinates.
        
        Args:
            x: X coordinate in original image
            y: Y coordinate in original image
            
        Returns:
            Point in scene coordinates
        """
        # Direct mapping with scale factor support
        scene_x = float(x) * self.scale_factor
        scene_y = float(y) * self.scale_factor
        return QPointF(scene_x, scene_y)
    
    def scene_to_original(self, scene_point: QPointF) -> Tuple[int, int]:
        """Convert scene coordinates to original image coordinates.
        
        Args:
            scene_point: Point in scene coordinates
            
        Returns:
            Tuple of (x, y) in original image coordinates
        """
        # Inverse mapping with bounds checking
        x = int(scene_point.x() / self.scale_factor)
        y = int(scene_point.y() / self.scale_factor)
        
        # Clamp to valid range
        x = max(0, min(x, self.scene_width - 1))
        y = max(0, min(y, self.scene_height - 1))
        
        return x, y
    
    def original_points_to_scene(self, points: List[Tuple[int, int]]) -> List[QPointF]:
        """Convert a list of original coordinates to scene coordinates.
        
        Args:
            points: List of (x, y) tuples in original coordinates
            
        Returns:
            List of QPointF in scene coordinates
        """
        return [self.original_to_scene(x, y) for x, y in points]
    
    def scene_points_to_original(self, points: List[QPointF]) -> List[Tuple[int, int]]:
        """Convert a list of scene points to original coordinates.
        
        Args:
            points: List of QPointF in scene coordinates
            
        Returns:
            List of (x, y) tuples in original coordinates
        """
        return [self.scene_to_original(point) for point in points]
    
    # Bounds checking utilities
    def is_point_in_scene(self, x: int, y: int) -> bool:
        """Check if a point is within scene bounds.
        
        Args:
            x: X coordinate in original space
            y: Y coordinate in original space
            
        Returns:
            True if point is within bounds
        """
        return 0 <= x < self.scene_width and 0 <= y < self.scene_height
    
    def clamp_to_scene(self, x: int, y: int) -> Tuple[int, int]:
        """Clamp coordinates to valid scene bounds.
        
        Args:
            x: X coordinate
            y: Y coordinate
            
        Returns:
            Clamped (x, y) tuple
        """
        x = max(0, min(x, self.scene_width - 1))
        y = max(0, min(y, self.scene_height - 1))
        return x, y
    
    def get_scene_bounds(self) -> QRectF:
        """Get the bounding rectangle of the scene.
        
        Returns:
            Rectangle representing scene bounds
        """
        return QRectF(0, 0, self.scene_width * self.scale_factor, 
                      self.scene_height * self.scale_factor)
    
    # Item-relative conversions
    def item_to_scene(self, item_point: QPointF, item_pos: QPointF) -> QPointF:
        """Convert item-local coordinates to scene coordinates.
        
        Args:
            item_point: Point in item's local coordinates
            item_pos: Item's position in scene
            
        Returns:
            Point in scene coordinates
        """
        return item_point + item_pos
    
    def scene_to_item(self, scene_point: QPointF, item_pos: QPointF) -> QPointF:
        """Convert scene coordinates to item-local coordinates.
        
        Args:
            scene_point: Point in scene coordinates
            item_pos: Item's position in scene
            
        Returns:
            Point in item's local coordinates
        """
        return scene_point - item_pos
    
    # Utility methods for common operations
    def offset_points(self, points: List[QPointF], offset: QPointF) -> List[QPointF]:
        """Offset a list of points by a given amount.
        
        Args:
            points: List of points to offset
            offset: Offset to apply
            
        Returns:
            List of offset points
        """
        return [point + offset for point in points]
    
    def scale_points(self, points: List[QPointF], scale: float, 
                     origin: QPointF = QPointF(0, 0)) -> List[QPointF]:
        """Scale a list of points around an origin.
        
        Args:
            points: List of points to scale
            scale: Scale factor
            origin: Origin point for scaling
            
        Returns:
            List of scaled points
        """
        scaled_points = []
        for point in points:
            relative = point - origin
            scaled = relative * scale
            scaled_points.append(origin + scaled)
        return scaled_points