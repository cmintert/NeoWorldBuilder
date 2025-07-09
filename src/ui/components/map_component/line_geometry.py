"""Line geometry classes for handling coordinate management and transformations.

This module provides geometry classes for both simple lines and branching lines,
with shared functionality for scaling, bounds calculation, and point manipulation.
"""

from typing import Dict, List, Optional, Tuple, Union


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
        # Graphics-only scaling approach (no widget system)
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
        self._stable_branch_ids = []  # Stable IDs for each branch
        self._branch_assignments = {}  # Maps stable IDs to node assignments
        self.is_branching = True  # BranchingLineGeometry is always branching
        self._bounds_cache = None
        self._bounds_cache_valid = False
        self._generate_stable_branch_ids()
        self._update_shared_points()
        self._update_scaled_points()

    def _generate_stable_branch_ids(self) -> None:
        """Generate stable, deterministic IDs for each branch.

        This method creates meaningful, consistent IDs for branches that don't
        change when branches are reordered or modified. The IDs are generated
        based on branch geometry to ensure consistency across application sessions.
        """
        self._stable_branch_ids = []

        if not self.branches:
            return

        # Generate deterministic IDs based on branch structure
        if len(self.branches) == 1:
            # Single branch - this is the main line
            self._stable_branch_ids = ["main_line"]
        else:
            # Multiple branches - main stem plus numbered branches
            self._stable_branch_ids = ["main_stem"]

            # Sort remaining branches by their start points for consistent ordering
            remaining_branches = list(enumerate(self.branches[1:], 1))
            remaining_branches.sort(
                key=lambda x: (x[1][0][0], x[1][0][1]) if x[1] else (0, 0)
            )

            # Generate IDs for the sorted branches
            for i, (_, branch) in enumerate(remaining_branches):
                self._stable_branch_ids.append(f"branch_{i + 1}")

    @property
    def stable_branch_ids(self) -> List[str]:
        """Get the stable branch IDs."""
        return self._stable_branch_ids.copy()

    @property
    def branch_assignments(self) -> Dict[str, str]:
        """Get the current branch assignments (stable ID -> node ID)."""
        return self._branch_assignments.copy()

    def set_branch_assignment(self, stable_id: str, node_id: str) -> None:
        """Set a branch assignment using stable ID.

        Args:
            stable_id: Stable branch ID (e.g., "main_stem", "branch_1")
            node_id: Node ID to assign to this branch
        """
        if stable_id in self._stable_branch_ids:
            self._branch_assignments[stable_id] = node_id
        else:
            raise ValueError(f"Invalid stable branch ID: {stable_id}")

    def get_branch_assignment(self, stable_id: str) -> Optional[str]:
        """Get the node assignment for a stable branch ID.

        Args:
            stable_id: Stable branch ID

        Returns:
            Node ID if assigned, None otherwise
        """
        return self._branch_assignments.get(stable_id)

    def get_branch_display_name(self, stable_id: str) -> str:
        """Get a human-readable display name for a branch ID.

        Args:
            stable_id: Stable branch ID

        Returns:
            Display name (e.g., "Main Stem", "Branch 1")
        """
        if stable_id == "main_line":
            return "Main Line"
        elif stable_id == "main_stem":
            return "Main Stem"
        elif stable_id.startswith("branch_"):
            try:
                branch_num = stable_id.split("_")[1]
                return f"Branch {branch_num}"
            except (IndexError, ValueError):
                return stable_id.replace("_", " ").title()
        else:
            return stable_id.replace("_", " ").title()

    def get_branch_index_from_stable_id(self, stable_id: str) -> Optional[int]:
        """Get the branch index for a stable ID.

        Args:
            stable_id: Stable branch ID

        Returns:
            Branch index if valid, None otherwise
        """
        try:
            return self._stable_branch_ids.index(stable_id)
        except ValueError:
            return None

    def get_stable_id_from_branch_index(self, branch_index: int) -> Optional[str]:
        """Get the stable ID for a branch index.

        Args:
            branch_index: Branch index

        Returns:
            Stable ID if valid, None otherwise
        """
        if 0 <= branch_index < len(self._stable_branch_ids):
            return self._stable_branch_ids[branch_index]
        return None

    def load_branch_assignments_from_flat_properties(
        self, properties: Dict[str, str]
    ) -> None:
        """Load branch assignments from flat properties format.

        Args:
            properties: Dictionary containing flat properties where keys like
                       "branch_main_stem", "branch_branch_1" map to node IDs
        """
        self._branch_assignments = {}

        for key, value in properties.items():
            if key.startswith("branch_"):
                # Extract the stable ID from the property key
                stable_id = key[7:]  # Remove "branch_" prefix

                # Validate that this is a valid stable ID
                if stable_id in self._stable_branch_ids:
                    self._branch_assignments[stable_id] = value

    def get_flat_properties_for_storage(self) -> Dict[str, str]:
        """Get branch assignments as flat properties for database storage.

        Returns:
            Dictionary with keys like "branch_main_stem", "branch_branch_1"
            mapping to node IDs
        """
        flat_properties = {}

        for stable_id, node_id in self._branch_assignments.items():
            flat_properties[f"branch_{stable_id}"] = node_id

        return flat_properties

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

        self._shared_points = reclassified_shared_points

    @property
    def scaled_branches(self) -> List[List[Tuple[int, int]]]:
        """Get scaled branches."""
        return self._scaled_branches

    @property
    def original_branches(self) -> List[List[Tuple[int, int]]]:
        """Get original branches."""
        return self.branches

    def _update_shared_points(self):
        """Update mapping of shared points between branches with performance optimization."""
        # UX Enhancement: Skip expensive operations during drag
        if (
            hasattr(self, "_skip_shared_points_update")
            and self._skip_shared_points_update
        ):
            return

        self._shared_points = {}

        for branch_idx, branch in enumerate(self.branches):
            for point_idx, point in enumerate(branch):
                # Convert point to integer tuple to ensure it's hashable
                point_key = (int(point[0]), int(point[1]))
                if point_key not in self._shared_points:
                    self._shared_points[point_key] = []
                self._shared_points[point_key].append((branch_idx, point_idx))

        # Automatically reclassify points based on actual connections
        self._reclassify_points()

    def _update_scaled_points(self):
        """Update scaled branches based on current scale."""
        # Graphics-only scaling approach (no widget system)
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
        self._generate_stable_branch_ids()
        self._update_shared_points()
        self._update_scaled_points()

    def remove_branch(self, branch_idx: int) -> bool:
        """Remove a branch from the geometry."""
        if 0 <= branch_idx < len(self.branches) and len(self.branches) > 1:
            # Remove assignment for the branch being deleted
            stable_id = self.get_stable_id_from_branch_index(branch_idx)
            if stable_id and stable_id in self._branch_assignments:
                del self._branch_assignments[stable_id]

            self.branches.pop(branch_idx)
            self._generate_stable_branch_ids()
            self._update_shared_points()
            self._update_scaled_points()
            return True
        return False

    def _update_scaled_branches(self):
        """Update scaled branches - alias for _update_scaled_points for compatibility."""
        self._update_scaled_points()

    def delete_branch(self, branch_idx: int) -> bool:
        """Delete a branch from the geometry - alias for remove_branch for compatibility."""
        return self.remove_branch(branch_idx)

    def delete_point(self, branch_idx: int, point_idx: int) -> bool:
        """Delete a point from the geometry."""
        if branch_idx >= len(self.branches) or point_idx >= len(
            self.branches[branch_idx]
        ):
            return False

        # Don't allow deletion if it would make a branch too short
        if len(self.branches[branch_idx]) <= 2:
            return False

        point_to_delete = self.branches[branch_idx][point_idx]

        # Check if this is a shared point
        point_key = (int(point_to_delete[0]), int(point_to_delete[1]))
        if point_key in self._shared_points:
            shared_locations = self._shared_points[point_key]

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

    def insert_point(self, branch_idx: int, point_idx: int, new_point: Tuple[int, int]):
        """Insert a point into a specific branch."""
        if branch_idx >= len(self.branches):
            return

        self.branches[branch_idx].insert(point_idx, new_point)
        self._update_shared_points()
        self._update_scaled_points()

    def get_bounds(self) -> Tuple[int, int, int, int]:
        """Get geometry bounds (min_x, min_y, max_x, max_y)."""
        if not self._bounds_cache_valid:
            self._calculate_bounds()
        return self._bounds_cache

    def set_scale(self, scale: float) -> None:
        """Set the scale and update scaled points."""
        self._scale = scale
        self._update_scaled_points()
        self._invalidate_bounds()
