"""Consolidated edit mode system for both simple and branching lines.

This module provides a unified edit mode system that handles:
1. Simple LineString geometries
2. Complex MultiLineString (branching) geometries
3. Consistent coordinate transformation using CoordinateTransformer
4. Shared point handling between branches
5. Unified visual feedback and user experience
"""

from typing import List, Tuple, Dict, Any

from PyQt6.QtGui import QPainter, QColor, QPen, QBrush
from structlog import get_logger

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
        """Update mapping of shared points between branches with performance optimization."""
        # UX Enhancement: Skip expensive operations during drag
        if hasattr(self, '_skip_shared_points_update') and self._skip_shared_points_update:
            return
            
        self._shared_points = {}

        if not self.is_branching:
            return  # No shared points for simple lines

        for branch_idx, branch in enumerate(self.branches):
            for point_idx, point in enumerate(branch):
                # Convert point to integer tuple to ensure it's hashable
                point_key = (int(point[0]), int(point[1]))
                if point_key not in self._shared_points:
                    self._shared_points[point_key] = []
                self._shared_points[point_key].append((branch_idx, point_idx))
        
        # Automatically reclassify points based on actual connections
        self._reclassify_points()
        
    def set_performance_mode(self, enabled: bool):
        """Enable/disable performance mode to skip expensive updates during dragging.
        
        Args:
            enabled: True to skip expensive updates, False to re-enable them
        """
        self._skip_shared_points_update = enabled

    def _count_point_connections(self, point_key: Tuple[int, int]) -> int:
        """Count the number of line segments that connect to a point.
        
        Args:
            point_key: The point coordinate as (x, y) tuple
            
        Returns:
            Number of line segments connected to this point
        """
        connection_count = 0
        
        # Check each branch for segments connecting to this point
        for branch in self.branches:
            for i, point in enumerate(branch):
                current_point_key = (int(point[0]), int(point[1]))
                
                if current_point_key == point_key:
                    # Count segments before this point (if not first)
                    if i > 0:
                        connection_count += 1
                    # Count segments after this point (if not last)  
                    if i < len(branch) - 1:
                        connection_count += 1
        
        return connection_count

    def _reclassify_points(self):
        """Reclassify shared points based on actual line segment connections.
        
        Points are only considered "shared" (branching points) if they have 3 or more 
        line segments connecting to them. Points with only 2 connections are inline
        points and should not be marked as shared.
        """
        if not self.is_branching:
            return
        
        # Create new shared points mapping with only true branching points
        reclassified_shared_points = {}
        
        for point_key, locations in self._shared_points.items():
            # Count actual line segment connections to this point
            connection_count = self._count_point_connections(point_key)
            
            # Only keep as shared if it has 3+ connections (true branching point)
            if connection_count >= 3:
                reclassified_shared_points[point_key] = locations
        
        # Update the shared points mapping
        self._shared_points = reclassified_shared_points
        
        logger.debug(f"Reclassified points: {len(reclassified_shared_points)} true branching points remaining")

    def _update_scaled_branches(self):
        """Update scaled branches based on current scale."""
        self._scaled_branches = []
        for branch in self.branches:
            scaled_branch = [
                (int(p[0] * self._scale), int(p[1] * self._scale)) for p in branch
            ]
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
        if branch_idx >= len(self.branches) or point_idx >= len(
            self.branches[branch_idx]
        ):
            return

        old_point = self.branches[branch_idx][point_idx]
        old_point_key = (int(old_point[0]), int(old_point[1]))

        # For branching lines, check if this point is shared
        if self.is_branching and old_point_key in self._shared_points:
            shared_locations = self._shared_points[old_point_key]

            # Update all instances of this shared point
            for shared_branch_idx, shared_point_idx in shared_locations:
                if shared_branch_idx < len(self.branches) and shared_point_idx < len(
                    self.branches[shared_branch_idx]
                ):
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
        if branch_idx >= len(self.branches) or point_idx >= len(
            self.branches[branch_idx]
        ):
            return False

        # Don't allow deletion if it would make a branch too short
        if len(self.branches[branch_idx]) <= 2:
            return False

        self.branches[branch_idx].pop(point_idx)

        if self.is_branching:
            self._update_shared_points()
        self._update_scaled_branches()
        return True

    def delete_branch(self, branch_idx: int) -> bool:
        """Delete a branch, with safety checks.
        
        Args:
            branch_idx: Index of the branch to delete
            
        Returns:
            True if branch was deleted, False otherwise
        """
        # Can't delete if not a branching line
        if not self.is_branching:
            logger.warning("Cannot delete branch from non-branching line")
            return False
            
        # Can't delete the main branch (index 0)
        if branch_idx <= 0:
            logger.warning("Cannot delete the main branch (index 0)")
            return False
            
        # Check valid index
        if branch_idx >= len(self.branches):
            logger.warning(f"Invalid branch index {branch_idx}")
            return False
            
        # Must have at least 2 branches to delete one
        if len(self.branches) <= 2:
            logger.warning("Cannot delete branch - would convert to simple line")
            return False
            
        # Delete the branch
        del self.branches[branch_idx]
        
        # Update internal state
        self._update_shared_points()
        self._update_scaled_branches()
        self._invalidate_bounds()
        
        logger.info(f"Deleted branch {branch_idx}, now have {len(self.branches)} branches")
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

    def create_branch_from_point(
        self, branch_idx: int, point_idx: int, end_point: Tuple[int, int]
    ) -> bool:
        """Create a new branch starting from an existing point.

        Args:
            branch_idx: Index of branch containing the start point
            point_idx: Index of point within the branch
            end_point: End point for the new branch

        Returns:
            True if branch was created successfully, False otherwise
        """
        if branch_idx >= len(self.branches) or point_idx >= len(
            self.branches[branch_idx]
        ):
            return False

        # Get the starting point
        start_point = self.branches[branch_idx][point_idx]

        # Create new branch
        new_branch = [start_point, end_point]
        self.branches.append(new_branch)

        # Mark as branching line
        self.is_branching = True

        # Update shared points and scaled branches
        self._update_shared_points()
        self._update_scaled_branches()

        return True

    def create_branch_from_position(
        self, start_point: Tuple[int, int], end_point: Tuple[int, int]
    ) -> bool:
        """Create a new branch starting from a position (may insert point if needed).

        Args:
            start_point: Starting point for the new branch
            end_point: End point for the new branch

        Returns:
            True if branch was created successfully, False otherwise
        """
        # Find the nearest existing point to start_point
        nearest_point = None
        nearest_distance = float("inf")

        for branch in self.branches:
            for point in branch:
                dx = point[0] - start_point[0]
                dy = point[1] - start_point[1]
                distance = dx * dx + dy * dy

                if distance < nearest_distance:
                    nearest_distance = distance
                    nearest_point = point

        # If we have a nearby point (within 10 pixels), use it
        if nearest_point and nearest_distance <= 100:  # 10 pixels squared
            start_point = nearest_point
        else:
            # Insert the start point into the nearest line segment
            if not self._insert_point_at_position(start_point):
                # If insertion failed, ensure we have at least one branch
                if not self.branches:
                    self.branches.append([])

                # Add the point to the first branch if it exists and has points
                if self.branches and len(self.branches[0]) > 0:
                    self.branches[0].append(start_point)
                else:
                    # Initialize the first branch with the start point
                    self.branches[0] = [start_point]

        # Create new branch
        new_branch = [start_point, end_point]
        self.branches.append(new_branch)

        # Mark as branching line
        self.is_branching = True

        # Update shared points and scaled branches
        self._update_shared_points()
        self._update_scaled_branches()

        return True

    def _insert_point_at_position(self, point: Tuple[int, int]) -> bool:
        """Insert a point at the nearest position on an existing line segment.

        Args:
            point: Point to insert

        Returns:
            True if point was inserted, False otherwise
        """
        min_distance = float("inf")
        best_branch_idx = -1
        best_segment_idx = -1

        # Find the nearest line segment
        for branch_idx, branch in enumerate(self.branches):
            if len(branch) < 2:
                continue

            for segment_idx in range(len(branch) - 1):
                p1 = branch[segment_idx]
                p2 = branch[segment_idx + 1]

                # Calculate distance to line segment
                distance, _ = self._point_to_line_distance(point, p1, p2)

                if distance < min_distance:
                    min_distance = distance
                    best_branch_idx = branch_idx
                    best_segment_idx = segment_idx

        # If we found a nearby segment (within 20 pixels), insert the point
        if min_distance <= 20 and best_branch_idx >= 0:
            insert_idx = best_segment_idx + 1
            self.branches[best_branch_idx].insert(insert_idx, point)
            return True

        return False

    def _point_to_line_distance(
        self,
        point: Tuple[float, float],
        line_start: Tuple[float, float],
        line_end: Tuple[float, float],
    ) -> Tuple[float, Tuple[float, float]]:
        """Calculate distance from point to line segment.

        Returns:
            Tuple of (distance, closest_point_on_line)
        """
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

    # Constants for rendering control points
    CONTROL_POINT_RADIUS = 6
    SHARED_POINT_RADIUS = 8

    def __init__(self, config=None):
        self.config = config

    def draw_line(
        self,
        painter: QPainter,
        geometry: UnifiedLineGeometry,
        style_config: Dict[str, Any],
        widget_offset: Tuple[int, int],
    ):
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

    def draw_control_points(
        self,
        painter: QPainter,
        geometry: UnifiedLineGeometry,
        widget_offset: Tuple[int, int],
        highlight_point=None,
    ):
        """Draw control points with visual distinction for shared points.

        Args:
            painter: QPainter instance to draw with
            geometry: Line geometry to render
            widget_offset: Offset of widget (x, y)
            highlight_point: Optional tuple of (branch_idx, point_idx) to highlight
        """
        widget_x, widget_y = widget_offset

        # Use pre-computed shared points from geometry for branching lines
        shared_points = set()
        if geometry.is_branching and hasattr(geometry, '_shared_points'):
            # Convert shared points (in original coordinates) to scaled coordinates
            for original_point, locations in geometry._shared_points.items():
                if len(locations) > 1:  # Only include points shared between multiple branches
                    scaled_point = (
                        int(original_point[0] * geometry._scale),
                        int(original_point[1] * geometry._scale),
                    )
                    shared_points.add(scaled_point)

        # Draw control points
        for branch_idx, branch in enumerate(geometry.scaled_branches):
            for point_idx, point in enumerate(branch):
                # Convert to widget coordinates
                x = point[0] - widget_x
                y = point[1] - widget_y

                # Check if this is the point to highlight (for branch creation)
                is_highlight = (
                    highlight_point is not None
                    and highlight_point[0] == branch_idx
                    and highlight_point[1] == point_idx
                )

                # Different colors for shared vs regular points
                if is_highlight:
                    # Highlighted point (selected for branch creation) is larger and bright red
                    painter.setBrush(QBrush(QColor("#FF0000")))
                    painter.setPen(QPen(QColor("#FFFFFF"), 2))
                    radius = self.SHARED_POINT_RADIUS + 2  # Slightly larger
                elif point in shared_points:
                    # Shared points are larger and red
                    painter.setBrush(QBrush(QColor("#FF0000")))
                    painter.setPen(QPen(QColor("#FFFFFF"), 2))
                    radius = self.SHARED_POINT_RADIUS
                else:
                    # Regular points are blue
                    painter.setBrush(QBrush(QColor("#0000FF")))
                    painter.setPen(QPen(QColor("#FFFFFF"), 1))
                    radius = self.CONTROL_POINT_RADIUS

                painter.drawEllipse(x - radius, y - radius, 2 * radius, 2 * radius)
