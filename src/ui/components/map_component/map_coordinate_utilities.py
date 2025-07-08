from typing import Optional, Tuple, List, Dict
from structlog import get_logger

logger = get_logger(__name__)


class MapCoordinateUtilities:
    """Utilities for coordinate calculations and finding operations.
    
    Handles distance calculations, nearest point/line finding, and other
    geometric operations for the map component.
    """

    def __init__(self, parent_widget):
        """Initialize the coordinate utilities.
        
        Args:
            parent_widget: The parent widget (MapTab instance)
        """
        self.parent_widget = parent_widget

    def find_nearest_line_at_position(self, x: int, y: int) -> Optional[str]:
        """Find the nearest line container to the specified position.

        Args:
            x: X coordinate in original image space
            y: Y coordinate in original image space

        Returns:
            Target node of nearest line, or None if no line found
        """
        # Graphics system implementation
        if hasattr(self.parent_widget, 'graphics_adapter'):
            try:
                graphics_view = self.parent_widget.graphics_adapter.graphics_view
                scene = graphics_view.scene()
                
                # Convert original coordinates to scene coordinates
                scene_pos = scene.original_to_scene_coords(x, y)
                
                # Find items at this position
                items = scene.items(scene_pos)
                
                # Look for line graphics items
                from ui.components.map_component.graphics.line_graphics_item import LineGraphicsItem
                
                for item in items:
                    if isinstance(item, LineGraphicsItem):
                        logger.debug(f"Found line at position ({x}, {y}): {item.target_node}")
                        return item.target_node
                
                # If no direct hit, find the nearest line within a reasonable distance
                search_radius = 20  # pixels
                nearby_items = scene.items(scene_pos.x() - search_radius, scene_pos.y() - search_radius, 
                                         search_radius * 2, search_radius * 2)
                
                nearest_line = None
                min_distance = float('inf')
                
                for item in nearby_items:
                    if isinstance(item, LineGraphicsItem):
                        # Calculate distance to the line
                        item_center = item.boundingRect().center()
                        distance = ((scene_pos.x() - item_center.x()) ** 2 + 
                                   (scene_pos.y() - item_center.y()) ** 2) ** 0.5
                        
                        if distance < min_distance:
                            min_distance = distance
                            nearest_line = item.target_node
                
                if nearest_line:
                    logger.debug(f"Found nearest line within {search_radius}px: {nearest_line}")
                    return nearest_line
                
                logger.debug(f"No line found at position ({x}, {y})")
                return None
                
            except Exception as e:
                logger.error(f"Error finding line at position: {e}")
                return None
        
        # Fallback - TODO: Migrate to graphics system - old widget feature manager removed
        logger.warning("No graphics adapter available for line finding")
        return None

    def find_nearest_control_point(
        self, scaled_x: float, scaled_y: float
    ) -> Optional[Tuple[str, int, int, Tuple[int, int]]]:
        """Find the nearest control point to the specified position.

        Args:
            scaled_x: X coordinate in scaled image space
            scaled_y: Y coordinate in scaled image space

        Returns:
            Tuple of (target_node, branch_idx, point_idx, point) or None if no point found
        """

        # TODO: Migrate to graphics system - old widget feature manager removed
        logger.warning("Line container operations not yet implemented for graphics mode")
        return None

    def point_to_line_distance(
        self,
        point: Tuple[float, float],
        line_start: Tuple[int, int],
        line_end: Tuple[int, int],
    ) -> float:
        """Calculate distance from point to line segment."""
        px, py = point
        x1, y1 = line_start
        x2, y2 = line_end

        # Vector from line_start to line_end
        dx = x2 - x1
        dy = y2 - y1

        # If line segment has zero length
        if dx == 0 and dy == 0:
            return ((px - x1) ** 2 + (py - y1) ** 2) ** 0.5

        # Parameter t represents position along line segment (0 to 1)
        t = max(0, min(1, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))

        # Closest point on line segment
        closest_x = x1 + t * dx
        closest_y = y1 + t * dy

        # Distance from point to closest point on line
        return ((px - closest_x) ** 2 + (py - closest_y) ** 2) ** 0.5

    def find_nearest_to_mouse(
        self, mouse_pos, 
        pixmap, 
        viewport_width: int, 
        viewport_height: int
    ) -> Dict[str, any]:
        """Find the nearest feature to the current mouse position.
        
        Args:
            mouse_pos: Mouse position from QCursor
            pixmap: Current image pixmap
            viewport_width: Width of viewport
            viewport_height: Height of viewport
            
        Returns:
            Dictionary with nearest feature info
        """
        from .utils.coordinate_transformer import CoordinateTransformer
        
        original_pixmap = None
        current_scale = self.parent_widget.current_scale

        if (
            hasattr(self.parent_widget, "image_manager")
            and self.parent_widget.image_manager.original_pixmap
        ):
            original_pixmap = self.parent_widget.image_manager.original_pixmap

        coordinates = CoordinateTransformer.widget_to_original_coordinates(
            mouse_pos,
            pixmap,
            viewport_width,
            viewport_height,
            original_pixmap,
            current_scale,
        )

        if not coordinates:
            return None

        original_x, original_y = coordinates
        scaled_x = original_x * current_scale
        scaled_y = original_y * current_scale

        # Try to find nearest control point first
        nearest_point = self.find_nearest_control_point(scaled_x, scaled_y)
        if nearest_point:
            target_node, branch_idx, point_idx, point = nearest_point
            return {
                "type": "control_point",
                "target_node": target_node,
                "branch_idx": branch_idx,
                "point_idx": point_idx,
                "point": point,
                "original_coords": (original_x, original_y),
                "scaled_coords": (scaled_x, scaled_y)
            }

        # If no control point found, try line segments
        nearest_line = self.find_nearest_line_at_position(original_x, original_y)
        if nearest_line:
            return {
                "type": "line_segment",
                "target_node": nearest_line,
                "original_coords": (original_x, original_y),
                "scaled_coords": (scaled_x, scaled_y)
            }

        return None