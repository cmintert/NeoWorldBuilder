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
        # Get all line containers from feature manager
        line_containers = self.parent_widget.feature_manager.get_line_containers()

        if not line_containers:
            return None

        nearest_line = None
        min_distance = float("inf")

        # Convert original coordinates to scaled for hit testing
        scaled_x = x * self.parent_widget.current_scale
        scaled_y = y * self.parent_widget.current_scale

        for target_node, line_container in line_containers.items():

            # Get line geometry and test for proximity
            if hasattr(line_container, "geometry"):
                geometry = line_container.geometry

                # Check if geometry has scaled_branches attribute
                if not hasattr(geometry, "scaled_branches"):
                    continue

                # Debug what scaled_branches is
                scaled_branches = geometry.scaled_branches

                # Test if point is near any branch of this line
                for branch in scaled_branches:
                    if len(branch) < 2:
                        continue

                    for i in range(len(branch) - 1):
                        p1 = branch[i]
                        p2 = branch[i + 1]

                        # Calculate distance to line segment
                        distance = self.point_to_line_distance(
                            (scaled_x, scaled_y), p1, p2
                        )

                        if distance < min_distance:
                            min_distance = distance
                            nearest_line = target_node

        # Only return if within reasonable distance (e.g., 20 pixels)
        if min_distance <= 20:
            return nearest_line

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

        # Get all line containers from feature manager
        line_containers = self.parent_widget.feature_manager.get_line_containers()

        if not line_containers:
            return None

        nearest_info = None
        min_distance = float("inf")

        for target_node, line_container in line_containers.items():

            # Get line geometry
            if hasattr(line_container, "geometry"):
                geometry = line_container.geometry

                # Check if geometry has scaled_branches attribute
                if not hasattr(geometry, "scaled_branches"):
                    continue

                # Debug what scaled_branches is
                scaled_branches = geometry.scaled_branches

                # Test all control points in all branches
                for branch_idx, branch in enumerate(scaled_branches):
                    for point_idx, point in enumerate(branch):
                        # Calculate distance to control point
                        dx = scaled_x - point[0]
                        dy = scaled_y - point[1]
                        distance_sq = dx * dx + dy * dy

                        if distance_sq < min_distance:
                            min_distance = distance_sq
                            # Store original point (not scaled)
                            original_point = geometry.branches[branch_idx][point_idx]
                            nearest_info = (
                                target_node,
                                branch_idx,
                                point_idx,
                                original_point,
                            )

        # Only return if within reasonable distance (e.g., 20 pixels squared)
        if min_distance <= 400:  # 20 pixels squared
            target_node, branch_idx, point_idx, point = nearest_info
            return nearest_info

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