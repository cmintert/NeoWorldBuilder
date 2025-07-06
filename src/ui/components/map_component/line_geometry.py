"""Line geometry classes for handling coordinate management and transformations.

This module provides geometry classes for both simple lines and branching lines,
with shared functionality for scaling, bounds calculation, and point manipulation.
"""

from typing import List, Tuple, Optional, Union


class BaseLineGeometry:
    """Base class for line geometry operations.

    Provides common functionality for scaling, bounds calculation, and caching
    that can be shared between simple and branching line geometries.
    """

    def __init__(self):
        self._scale = 1.0
        self._bounds_cache = None
        self._bounds_cache_valid = False
        self._parent_container = None

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
        """Update scaled points based on current scale. Must be overridden by subclasses."""
        raise NotImplementedError("Subclasses must implement _update_scaled_points")

    def _find_parent_map_tab(self):
        """Find parent map tab for access to image manager.

        Returns:
            MapTab instance or None if not found
        """
        if hasattr(self, "_parent_container") and self._parent_container:
            return self._parent_container._find_map_tab()
        return None

    def set_parent_container(self, parent_container):
        """Set reference to parent container for accessing MapTab.

        Args:
            parent_container: The container that owns this geometry
        """
        self._parent_container = parent_container

    def get_bounds(self) -> Tuple[int, int, int, int]:
        """Get geometry bounds (min_x, min_y, max_x, max_y)."""
        if not self._bounds_cache_valid:
            self._calculate_bounds()
        return self._bounds_cache

    def _calculate_bounds(self) -> None:
        """Calculate and cache geometry bounds. Must be overridden by subclasses."""
        raise NotImplementedError("Subclasses must implement _calculate_bounds")

    def _invalidate_bounds(self) -> None:
        """Invalidate the bounds cache."""
        self._bounds_cache_valid = False

    def get_center(self) -> Tuple[int, int]:
        """Get the center point of the geometry."""
        min_x, min_y, max_x, max_y = self.get_bounds()
        return ((min_x + max_x) // 2, (min_y + max_y) // 2)


class LineGeometry(BaseLineGeometry):
    """Handles simple line coordinate management and transformations."""

    def __init__(self, original_points: List[Tuple[int, int]]):
        super().__init__()
        self.original_points = original_points.copy()
        self._scaled_points = []
        self._update_scaled_points()

    @property
    def scaled_points(self) -> List[Tuple[int, int]]:
        """Get the scaled points."""
        return self._scaled_points

    def _update_scaled_points(self) -> None:
        """Update scaled points based on current scale."""
        parent_map_tab = self._find_parent_map_tab()

        if (
            parent_map_tab
            and hasattr(parent_map_tab, "image_manager")
            and parent_map_tab.image_manager.original_pixmap
        ):
            try:
                # Get original and current dimensions
                original_width = parent_map_tab.image_manager.original_pixmap.width()
                original_height = parent_map_tab.image_manager.original_pixmap.height()

                current_pixmap = parent_map_tab.image_label.pixmap()
                if current_pixmap and original_width > 0 and original_height > 0:
                    current_width = current_pixmap.width()
                    current_height = current_pixmap.height()

                    # Calculate scale ratios
                    width_ratio = current_width / original_width
                    height_ratio = current_height / original_height


                    # Scale points using dimension ratios
                    self._scaled_points = [
                        (int(p[0] * width_ratio), int(p[1] * height_ratio))
                        for p in self.original_points
                    ]
                    return
            except (AttributeError, ZeroDivisionError) as e:
                # Log the error but continue with fallback
                pass

        # Fallback to simple scaling if image manager not available
        self._scaled_points = [
            (int(p[0] * self._scale), int(p[1] * self._scale))
            for p in self.original_points
        ]

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

    def point_count(self) -> int:
        """Get the number of points in the line."""
        return len(self.original_points)


class BranchingLineGeometry(BaseLineGeometry):
    """Handles branching line coordinate management and transformations.

    This class manages multiple line branches that can share points and provides
    operations for scaling, bounds calculation, and point manipulation across
    all branches.
    """

    def __init__(self, branches: List[List[Tuple[int, int]]]):
        """Initialize with a list of branches.

        Args:
            branches: List of branches, each branch is a list of coordinate points
        """
        super().__init__()
        self.branches = [branch.copy() for branch in branches]
        self._scaled_branches = []
        self._shared_points = (
            {}
        )  # Maps point coordinates to list of (branch_idx, point_idx)
        self._update_shared_points()
        self._update_scaled_points()

    @property
    def scaled_branches(self) -> List[List[Tuple[int, int]]]:
        """Get scaled branches."""
        return self._scaled_branches

    @property
    def original_branches(self) -> List[List[Tuple[int, int]]]:
        """Get original branches."""
        return self.branches

    def _update_shared_points(self):
        """Update mapping of shared points between branches."""
        self._shared_points = {}

        for branch_idx, branch in enumerate(self.branches):
            for point_idx, point in enumerate(branch):
                if point not in self._shared_points:
                    self._shared_points[point] = []
                self._shared_points[point].append((branch_idx, point_idx))

    def _update_scaled_points(self):
        """Update scaled branches based on current scale."""
        parent_map_tab = self._find_parent_map_tab()

        if (
            parent_map_tab
            and hasattr(parent_map_tab, "image_manager")
            and parent_map_tab.image_manager.original_pixmap
        ):
            try:
                # Get original and current dimensions
                original_width = parent_map_tab.image_manager.original_pixmap.width()
                original_height = parent_map_tab.image_manager.original_pixmap.height()

                current_pixmap = parent_map_tab.image_label.pixmap()
                if current_pixmap and original_width > 0 and original_height > 0:
                    current_width = current_pixmap.width()
                    current_height = current_pixmap.height()

                    # Calculate scale ratios
                    width_ratio = current_width / original_width
                    height_ratio = current_height / original_height

                    # Scale all branches using dimension ratios
                    self._scaled_branches = []
                    for branch in self.branches:
                        scaled_branch = [
                            (int(p[0] * width_ratio), int(p[1] * height_ratio))
                            for p in branch
                        ]
                        self._scaled_branches.append(scaled_branch)
                    self._invalidate_bounds()
                    return
            except (AttributeError, ZeroDivisionError) as e:
                # Log the error but continue with fallback
                pass

        # Fallback to simple scaling if image manager not available
        self._scaled_branches = []
        for branch in self.branches:
            scaled_branch = [
                (int(p[0] * self._scale), int(p[1] * self._scale)) for p in branch
            ]
            self._scaled_branches.append(scaled_branch)
        self._invalidate_bounds()

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

    def update_point(self, branch_idx: int, point_idx: int, new_point: Tuple[int, int]):
        """Update a point, handling shared points across branches."""
        if branch_idx >= len(self.branches) or point_idx >= len(
            self.branches[branch_idx]
        ):
            return

        old_point = self.branches[branch_idx][point_idx]

        # Check if this point is shared with other branches
        if old_point in self._shared_points:
            shared_locations = self._shared_points[old_point]

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
        self._update_shared_points()
        self._update_scaled_points()

    def insert_point(self, branch_idx: int, point_idx: int, new_point: Tuple[int, int]):
        """Insert a point into a specific branch."""
        if branch_idx >= len(self.branches):
            return

        self.branches[branch_idx].insert(point_idx, new_point)
        self._update_shared_points()
        self._update_scaled_points()

    def delete_point(self, branch_idx: int, point_idx: int) -> bool:
        """Delete a point, handling shared points carefully."""
        if branch_idx >= len(self.branches) or point_idx >= len(
            self.branches[branch_idx]
        ):
            return False

        # Don't allow deletion if it would make a branch too short
        if len(self.branches[branch_idx]) <= 2:
            return False

        point_to_delete = self.branches[branch_idx][point_idx]

        # Check if this is a shared point
        if point_to_delete in self._shared_points:
            shared_locations = self._shared_points[point_to_delete]

            # If shared with multiple branches, only delete from this branch
            if len(shared_locations) > 1:
                self.branches[branch_idx].pop(point_idx)
            else:
                # Not actually shared, safe to delete
                self.branches[branch_idx].pop(point_idx)
        else:
            self.branches[branch_idx].pop(point_idx)

        self._update_shared_points()
        self._update_scaled_points()
        return True

    def point_count(self) -> int:
        """Get the total number of points across all branches."""
        return sum(len(branch) for branch in self.branches)

    def branch_count(self) -> int:
        """Get the number of branches."""
        return len(self.branches)

    def get_branch_points(self, branch_idx: int) -> Optional[List[Tuple[int, int]]]:
        """Get points for a specific branch."""
        if 0 <= branch_idx < len(self.branches):
            return self.branches[branch_idx].copy()
        return None

    def add_branch(self, points: List[Tuple[int, int]]) -> None:
        """Add a new branch to the geometry."""
        self.branches.append(points.copy())
        self._update_shared_points()
        self._update_scaled_points()

    def remove_branch(self, branch_idx: int) -> bool:
        """Remove a branch from the geometry."""
        if 0 <= branch_idx < len(self.branches) and len(self.branches) > 1:
            self.branches.pop(branch_idx)
            self._update_shared_points()
            self._update_scaled_points()
            return True
        return False
