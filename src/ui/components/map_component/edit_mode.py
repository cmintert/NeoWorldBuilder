"""Consolidated edit mode system for both simple and branching lines.

This module provides a unified edit mode system that handles:
1. Simple LineString geometries
2. Complex MultiLineString (branching) geometries  
3. Consistent coordinate transformation using CoordinateTransformer
4. Shared point handling between branches
5. Unified visual feedback and user experience
"""

from typing import List, Tuple, Dict, Any, Optional, Set
from PyQt6.QtCore import Qt, pyqtSignal, QPoint
from PyQt6.QtGui import QPainter, QColor, QCursor, QPen, QBrush
from PyQt6.QtWidgets import QWidget, QLabel, QMenu
from structlog import get_logger

from .utils.coordinate_transformer import CoordinateTransformer

logger = get_logger(__name__)


class UnifiedLineGeometry:
    """Manages geometry for both simple and branching lines."""
    
    def __init__(self, points_or_branches):
        """Initialize with either simple points or branches.
        
        Args:
            points_or_branches: List of points for simple line, or list of branches for branching line
        """
        if points_or_branches and isinstance(points_or_branches[0], list):
            # Branching line - list of branches
            self.is_branching = True
            self.branches = [branch.copy() for branch in points_or_branches]
        else:
            # Simple line - list of points
            self.is_branching = False
            self.branches = [points_or_branches.copy()] if points_or_branches else [[]]
        
        self._scale = 1.0
        self._scaled_branches = []
        self._shared_points = {}
        self._bounds_cache = None
        self._bounds_cache_valid = False
        self._update_shared_points()
        self._update_scaled_branches()
    
    def _update_shared_points(self):
        """Update mapping of shared points between branches."""
        self._shared_points = {}
        
        if not self.is_branching:
            return  # No shared points for simple lines
        
        for branch_idx, branch in enumerate(self.branches):
            for point_idx, point in enumerate(branch):
                if point not in self._shared_points:
                    self._shared_points[point] = []
                self._shared_points[point].append((branch_idx, point_idx))
    
    def _update_scaled_branches(self):
        """Update scaled branches based on current scale."""
        self._scaled_branches = []
        for branch in self.branches:
            scaled_branch = [(int(p[0] * self._scale), int(p[1] * self._scale)) 
                           for p in branch]
            self._scaled_branches.append(scaled_branch)
        self._invalidate_bounds()
    
    def set_scale(self, scale: float):
        """Set the scale and update all branches."""
        self._scale = scale
        self._update_scaled_branches()
    
    def get_bounds(self) -> Tuple[int, int, int, int]:
        """Get bounds encompassing all branches."""
        if not self._bounds_cache_valid:
            self._calculate_bounds()
        return self._bounds_cache
    
    def _calculate_bounds(self):
        """Calculate bounds across all branches."""
        if not self._scaled_branches:
            self._bounds_cache = (0, 0, 0, 0)
            return
        
        all_points = []
        for branch in self._scaled_branches:
            all_points.extend(branch)
        
        if not all_points:
            self._bounds_cache = (0, 0, 0, 0)
            return
        
        min_x = min(p[0] for p in all_points)
        min_y = min(p[1] for p in all_points)
        max_x = max(p[0] for p in all_points)
        max_y = max(p[1] for p in all_points)
        
        self._bounds_cache = (min_x, min_y, max_x, max_y)
        self._bounds_cache_valid = True
    
    def _invalidate_bounds(self):
        """Invalidate bounds cache."""
        self._bounds_cache_valid = False
    
    def get_center(self) -> Tuple[int, int]:
        """Get center point of all branches."""
        min_x, min_y, max_x, max_y = self.get_bounds()
        return ((min_x + max_x) // 2, (min_y + max_y) // 2)
    
    def update_point(self, branch_idx: int, point_idx: int, new_point: Tuple[int, int]):
        """Update a point, handling shared points for branching lines."""
        if branch_idx >= len(self.branches) or point_idx >= len(self.branches[branch_idx]):
            return
        
        old_point = self.branches[branch_idx][point_idx]
        
        # For branching lines, check if this point is shared
        if self.is_branching and old_point in self._shared_points:
            shared_locations = self._shared_points[old_point]
            
            # Update all instances of this shared point
            for shared_branch_idx, shared_point_idx in shared_locations:
                if (shared_branch_idx < len(self.branches) and 
                    shared_point_idx < len(self.branches[shared_branch_idx])):
                    self.branches[shared_branch_idx][shared_point_idx] = new_point
        else:
            # Update just this point
            self.branches[branch_idx][point_idx] = new_point
        
        # Rebuild shared points mapping and scaled branches
        if self.is_branching:
            self._update_shared_points()
        self._update_scaled_branches()
    
    def insert_point(self, branch_idx: int, point_idx: int, new_point: Tuple[int, int]):
        """Insert a point into a specific branch."""
        if branch_idx >= len(self.branches):
            return
        
        self.branches[branch_idx].insert(point_idx, new_point)
        if self.is_branching:
            self._update_shared_points()
        self._update_scaled_branches()
    
    def delete_point(self, branch_idx: int, point_idx: int) -> bool:
        """Delete a point, with safety checks."""
        if (branch_idx >= len(self.branches) or 
            point_idx >= len(self.branches[branch_idx])):
            return False
        
        # Don't allow deletion if it would make a branch too short
        if len(self.branches[branch_idx]) <= 2:
            return False
        
        self.branches[branch_idx].pop(point_idx)
        
        if self.is_branching:
            self._update_shared_points()
        self._update_scaled_branches()
        return True
    
    def point_count(self) -> int:
        """Get total point count across all branches."""
        return sum(len(branch) for branch in self.branches)
    
    @property
    def scaled_branches(self) -> List[List[Tuple[int, int]]]:
        """Get scaled branches."""
        return self._scaled_branches
    
    @property
    def original_branches(self) -> List[List[Tuple[int, int]]]:
        """Get original branches."""
        return self.branches
    
    @property
    def scaled_points(self) -> List[Tuple[int, int]]:
        """Get scaled points for simple lines (first branch only)."""
        return self._scaled_branches[0] if self._scaled_branches else []
    
    @property 
    def original_points(self) -> List[Tuple[int, int]]:
        """Get original points for simple lines (first branch only)."""
        return self.branches[0] if self.branches else []


class UnifiedHitTester:
    """Unified hit tester for both simple and branching lines."""
    
    CONTROL_POINT_RADIUS = 6
    LINE_HIT_TOLERANCE = 8
    SHARED_POINT_RADIUS = 8
    
    @staticmethod
    def test_control_points(pos: QPoint, geometry: UnifiedLineGeometry, 
                          widget_offset: Tuple[int, int]) -> Tuple[int, int]:
        """Test control point hits.
        
        Returns:
            Tuple of (branch_idx, point_idx) or (-1, -1) if no hit
        """
        widget_x, widget_y = widget_offset
        pos_x, pos_y = pos.x(), pos.y()
        
        # Convert to map coordinates
        map_x = pos_x + widget_x
        map_y = pos_y + widget_y
        
        # Test all control points in all branches
        for branch_idx, branch in enumerate(geometry.scaled_branches):
            for point_idx, point in enumerate(branch):
                # Calculate distance to control point
                dx = map_x - point[0]
                dy = map_y - point[1]
                distance_sq = dx * dx + dy * dy
                
                # Use appropriate radius for shared vs regular points
                radius = (UnifiedHitTester.SHARED_POINT_RADIUS if 
                         geometry.is_branching and UnifiedHitTester._is_shared_point(geometry, point)
                         else UnifiedHitTester.CONTROL_POINT_RADIUS)
                
                if distance_sq <= radius ** 2:
                    return branch_idx, point_idx
        
        return -1, -1
    
    @staticmethod
    def test_line_segments(pos: QPoint, geometry: UnifiedLineGeometry, 
                          widget_offset: Tuple[int, int]) -> Tuple[int, int, QPoint]:
        """Test line segment hits.
        
        Returns:
            Tuple of (branch_idx, segment_idx, insertion_point) or (-1, -1, QPoint()) if no hit
        """
        widget_x, widget_y = widget_offset
        pos_x, pos_y = pos.x(), pos.y()
        
        # Convert to map coordinates
        map_x = pos_x + widget_x
        map_y = pos_y + widget_y
        
        # Test all line segments in all branches
        for branch_idx, branch in enumerate(geometry.scaled_branches):
            if len(branch) < 2:
                continue
                
            for segment_idx in range(len(branch) - 1):
                p1 = branch[segment_idx]
                p2 = branch[segment_idx + 1]
                
                # Calculate distance to line segment
                distance, closest_point = UnifiedHitTester._point_to_line_distance(
                    (map_x, map_y), p1, p2
                )
                
                if distance <= UnifiedHitTester.LINE_HIT_TOLERANCE:
                    return branch_idx, segment_idx, QPoint(int(closest_point[0]), int(closest_point[1]))
        
        return -1, -1, QPoint()
    
    @staticmethod
    def _is_shared_point(geometry: UnifiedLineGeometry, point: Tuple[int, int]) -> bool:
        """Check if a point is shared between branches."""
        if not geometry.is_branching:
            return False
        
        # Convert scaled point back to original coordinates to check sharing
        original_point = (int(point[0] / geometry._scale), int(point[1] / geometry._scale))
        return original_point in geometry._shared_points and len(geometry._shared_points[original_point]) > 1
    
    @staticmethod
    def _point_to_line_distance(point: Tuple[float, float], line_start: Tuple[int, int], 
                               line_end: Tuple[int, int]) -> Tuple[float, Tuple[float, float]]:
        """Calculate distance from point to line segment."""
        px, py = point
        x1, y1 = line_start
        x2, y2 = line_end
        
        # Vector from line_start to line_end
        dx = x2 - x1
        dy = y2 - y1
        
        # If line segment has zero length
        if dx == 0 and dy == 0:
            return ((px - x1) ** 2 + (py - y1) ** 2) ** 0.5, (x1, y1)
        
        # Parameter t represents position along line segment (0 to 1)
        t = max(0, min(1, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))
        
        # Closest point on line segment
        closest_x = x1 + t * dx
        closest_y = y1 + t * dy
        
        # Distance from point to closest point on line
        distance = ((px - closest_x) ** 2 + (py - closest_y) ** 2) ** 0.5
        
        return distance, (closest_x, closest_y)


class UnifiedLineRenderer:
    """Unified renderer for both simple and branching lines."""
    
    def __init__(self, config=None):
        self.config = config
    
    def draw_line(self, painter: QPainter, geometry: UnifiedLineGeometry, 
                  style_config: Dict[str, Any], widget_offset: Tuple[int, int]):
        """Draw line(s) with consistent styling."""
        widget_x, widget_y = widget_offset
        
        # Set up pen
        pen = QPen(style_config["color"])
        pen.setWidth(style_config["width"])
        pen.setStyle(style_config["pattern"])
        painter.setPen(pen)
        
        # Draw each branch
        for branch in geometry.scaled_branches:
            if len(branch) < 2:
                continue
                
            # Draw line segments
            for i in range(len(branch) - 1):
                p1 = branch[i]
                p2 = branch[i + 1]
                
                # Convert to widget coordinates
                x1 = p1[0] - widget_x
                y1 = p1[1] - widget_y
                x2 = p2[0] - widget_x
                y2 = p2[1] - widget_y
                
                painter.drawLine(x1, y1, x2, y2)
    
    def draw_control_points(self, painter: QPainter, geometry: UnifiedLineGeometry, 
                           widget_offset: Tuple[int, int]):
        """Draw control points with visual distinction for shared points."""
        widget_x, widget_y = widget_offset
        
        # Track shared points for branching lines
        shared_points = set()
        if geometry.is_branching:
            point_counts = {}
            
            # Count point occurrences
            for branch in geometry.scaled_branches:
                for point in branch:
                    # Convert to original coordinates for comparison
                    original_point = (int(point[0] / geometry._scale), int(point[1] / geometry._scale))
                    if original_point not in point_counts:
                        point_counts[original_point] = 0
                    point_counts[original_point] += 1
            
            # Identify shared points
            for point, count in point_counts.items():
                if count > 1:
                    # Convert back to scaled coordinates
                    scaled_point = (int(point[0] * geometry._scale), int(point[1] * geometry._scale))
                    shared_points.add(scaled_point)
        
        # Draw control points
        for branch_idx, branch in enumerate(geometry.scaled_branches):
            for point_idx, point in enumerate(branch):
                # Convert to widget coordinates
                x = point[0] - widget_x
                y = point[1] - widget_y
                
                # Different colors for shared vs regular points
                if point in shared_points:
                    # Shared points are larger and red
                    painter.setBrush(QBrush(QColor("#FF0000")))
                    painter.setPen(QPen(QColor("#FFFFFF"), 2))
                    radius = UnifiedHitTester.SHARED_POINT_RADIUS
                else:
                    # Regular points are blue
                    painter.setBrush(QBrush(QColor("#0000FF")))
                    painter.setPen(QPen(QColor("#FFFFFF"), 1))
                    radius = UnifiedHitTester.CONTROL_POINT_RADIUS
                
                painter.drawEllipse(x - radius, y - radius, 2 * radius, 2 * radius)