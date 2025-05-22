from typing import List, Tuple, Optional


class LineGeometry:
    """Handles line coordinate management and transformations."""
    
    def __init__(self, original_points: List[Tuple[int, int]]):
        self.original_points = original_points.copy()
        self._scale = 1.0
        self._scaled_points = []
        self._bounds_cache = None
        self._bounds_cache_valid = False
        self._update_scaled_points()
    
    @property
    def scaled_points(self) -> List[Tuple[int, int]]:
        """Get the scaled points."""
        return self._scaled_points
    
    @property
    def scale(self) -> float:
        """Get the current scale."""
        return self._scale
    
    def set_scale(self, scale: float) -> None:
        """Set the scale and update scaled points."""
        self._scale = scale
        self._update_scaled_points()
        self._invalidate_bounds()
    
    def _update_scaled_points(self) -> None:
        """Update scaled points based on current scale."""
        self._scaled_points = [
            (int(p[0] * self._scale), int(p[1] * self._scale)) 
            for p in self.original_points
        ]
    
    def get_bounds(self) -> Tuple[int, int, int, int]:
        """Get line bounds (min_x, min_y, max_x, max_y)."""
        if not self._bounds_cache_valid:
            self._calculate_bounds()
        return self._bounds_cache
    
    def _calculate_bounds(self) -> None:
        """Calculate and cache line bounds."""
        if not self._scaled_points:
            self._bounds_cache = (0, 0, 0, 0)
        else:
            min_x = min(p[0] for p in self._scaled_points)
            min_y = min(p[1] for p in self._scaled_points)
            max_x = max(p[0] for p in self._scaled_points)
            max_y = max(p[1] for p in self._scaled_points)
            self._bounds_cache = (min_x, min_y, max_x, max_y)
        self._bounds_cache_valid = True
    
    def _invalidate_bounds(self) -> None:
        """Invalidate the bounds cache."""
        self._bounds_cache_valid = False
    
    def insert_point(self, index: int, point: Tuple[int, int]) -> None:
        """Insert a point at the specified index."""
        self.original_points.insert(index, point)
        self._update_scaled_points()
        self._invalidate_bounds()
    
    def delete_point(self, index: int) -> bool:
        """Delete a point at the specified index. Returns True if successful."""
        if len(self.original_points) <= 2:  # Minimum points for a line
            return False
        del self.original_points[index]
        self._update_scaled_points()
        self._invalidate_bounds()
        return True
    
    def update_point(self, index: int, original_point: Tuple[int, int]) -> None:
        """Update a point at the specified index."""
        if 0 <= index < len(self.original_points):
            self.original_points[index] = original_point
            self._update_scaled_points()
            self._invalidate_bounds()
    
    def get_center(self) -> Tuple[int, int]:
        """Get the center point of the line."""
        min_x, min_y, max_x, max_y = self.get_bounds()
        return ((min_x + max_x) // 2, (min_y + max_y) // 2)
    
    def point_count(self) -> int:
        """Get the number of points in the line."""
        return len(self.original_points)
