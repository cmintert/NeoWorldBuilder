"""Snapping system for map line features.

This module provides snapping functionality for line editing, allowing points to snap
to other points or line segments within a configurable distance threshold.
"""

from typing import Dict, List, Optional, Set, Tuple

from PyQt6.QtCore import QPointF
from structlog import get_logger

logger = get_logger(__name__)


class SnapTarget:
    """Represents a potential snap target."""

    def __init__(
        self,
        position: Tuple[float, float],
        target_type: str,
        source_info: Optional[Dict] = None,
    ):
        """Initialize snap target.

        Args:
            position: The (x, y) position to snap to
            target_type: Type of target ('point' or 'line')
            source_info: Optional info about the source (e.g., branch_idx, point_idx)
        """
        self.position = position
        self.target_type = target_type
        self.source_info = source_info or {}

    def __repr__(self):
        return f"SnapTarget({self.position}, {self.target_type})"


class SnapManager:
    """Manages snapping behavior for line editing."""

    # Default snap threshold in pixels
    DEFAULT_SNAP_THRESHOLD = 15

    # Snap priorities (lower number = higher priority)
    SNAP_PRIORITY = {
        "point": 1,  # Points have highest priority
        "line": 2,  # Lines have lower priority
    }

    def __init__(self, snap_threshold: Optional[int] = None):
        """Initialize snap manager.

        Args:
            snap_threshold: Distance threshold for snapping in pixels
        """
        self.snap_threshold = snap_threshold or self.DEFAULT_SNAP_THRESHOLD
        self.snap_threshold_squared = self.snap_threshold**2
        self.enabled = True
        self._snap_targets: List[SnapTarget] = []
        self._excluded_points: Set[Tuple[int, int]] = set()

    def set_enabled(self, enabled: bool):
        """Enable or disable snapping."""
        self.enabled = enabled
        logger.debug(f"Snapping {'enabled' if enabled else 'disabled'}")

    def set_threshold(self, threshold: int):
        """Set snap distance threshold."""
        self.snap_threshold = threshold
        self.snap_threshold_squared = threshold**2
        logger.debug(f"Snap threshold set to {threshold} pixels")

    def clear_targets(self):
        """Clear all snap targets."""
        self._snap_targets.clear()
        self._excluded_points.clear()

    def add_excluded_point(self, branch_idx: int, point_idx: int):
        """Add a point to exclude from snapping (e.g., the point being dragged).

        Args:
            branch_idx: Branch index of point to exclude
            point_idx: Point index within branch to exclude
        """
        self._excluded_points.add((branch_idx, point_idx))

    def add_point_targets(self, geometry, scale: float = 1.0):
        """Add all control points from a geometry as snap targets.

        Args:
            geometry: UnifiedLineGeometry instance
            scale: Scale factor for coordinates
        """
        for branch_idx, branch in enumerate(geometry.branches):
            for point_idx, point in enumerate(branch):
                # Skip excluded points
                if (branch_idx, point_idx) in self._excluded_points:
                    continue

                # Scale the point coordinates
                scaled_point = (point[0] * scale, point[1] * scale)

                target = SnapTarget(
                    scaled_point,
                    "point",
                    {"branch_idx": branch_idx, "point_idx": point_idx},
                )
                self._snap_targets.append(target)

    def add_line_targets(self, geometry, scale: float = 1.0):
        """Add line segments from a geometry as snap targets.

        Args:
            geometry: UnifiedLineGeometry instance
            scale: Scale factor for coordinates
        """
        for branch_idx, branch in enumerate(geometry.branches):
            if len(branch) < 2:
                continue

            for i in range(len(branch) - 1):
                # Don't add segments that include excluded points
                if (branch_idx, i) in self._excluded_points or (
                    branch_idx,
                    i + 1,
                ) in self._excluded_points:
                    continue

                # Scale the segment endpoints
                p1 = (branch[i][0] * scale, branch[i][1] * scale)
                p2 = (branch[i + 1][0] * scale, branch[i + 1][1] * scale)

                # Store segment info for line snapping
                target = SnapTarget(
                    p1,  # We'll calculate actual snap point later
                    "line",
                    {
                        "branch_idx": branch_idx,
                        "segment_start": i,
                        "segment_end": i + 1,
                        "p1": p1,
                        "p2": p2,
                    },
                )
                self._snap_targets.append(target)

    def add_all_line_features(
        self,
        line_features: List,
        current_feature=None,
        current_branch_idx: Optional[int] = None,
        current_point_idx: Optional[int] = None,
        scale: float = 1.0,
    ):
        """Add snap targets from all line features in the scene.

        Args:
            line_features: List of line feature objects (graphics items or containers)
            current_feature: The feature currently being edited (to exclude current point)
            current_branch_idx: Branch index of point being dragged
            current_point_idx: Point index being dragged
            scale: Scale factor for coordinates
        """
        self.clear_targets()

        # If we have a current point being dragged, exclude it
        if (
            current_feature
            and current_branch_idx is not None
            and current_point_idx is not None
        ):
            self.add_excluded_point(current_branch_idx, current_point_idx)

        # Add targets from all line features
        for feature in line_features:
            # Get geometry from the feature (handle both graphics items and containers)
            geometry = None

            if hasattr(feature, "geometry"):
                geometry = feature.geometry
            elif hasattr(feature, "get_geometry"):
                geometry = feature.get_geometry()

            if geometry:
                # Add point targets
                self.add_point_targets(geometry, scale)

                # Add line targets (for snapping to line segments)
                self.add_line_targets(geometry, scale)

        logger.debug(f"Added {len(self._snap_targets)} snap targets")

    def find_snap_point(self, test_point: Tuple[float, float]) -> Optional[SnapTarget]:
        """Find the best snap target for a given point.

        Args:
            test_point: The point to test for snapping

        Returns:
            Best snap target within threshold, or None if no snap
        """
        if not self.enabled or not self._snap_targets:
            return None

        best_target = None
        best_distance_sq = self.snap_threshold_squared

        for target in self._snap_targets:
            if target.target_type == "point":
                # Point-to-point distance
                dx = test_point[0] - target.position[0]
                dy = test_point[1] - target.position[1]
                distance_sq = dx * dx + dy * dy

                if distance_sq <= best_distance_sq:
                    # Check priority - prefer points over lines
                    if (
                        best_target is None
                        or self.SNAP_PRIORITY[target.target_type]
                        < self.SNAP_PRIORITY[best_target.target_type]
                    ):
                        best_target = target
                        best_distance_sq = distance_sq

            elif target.target_type == "line":
                # Point-to-line distance
                p1 = target.source_info["p1"]
                p2 = target.source_info["p2"]

                closest_point = self._closest_point_on_segment(test_point, p1, p2)
                dx = test_point[0] - closest_point[0]
                dy = test_point[1] - closest_point[1]
                distance_sq = dx * dx + dy * dy

                if distance_sq <= best_distance_sq:
                    # Only use line snap if we don't have a point snap
                    if best_target is None or best_target.target_type != "point":
                        # Create a new target with the actual snap position
                        line_target = SnapTarget(
                            closest_point, "line", target.source_info
                        )
                        best_target = line_target
                        best_distance_sq = distance_sq

        return best_target

    def _closest_point_on_segment(
        self,
        point: Tuple[float, float],
        p1: Tuple[float, float],
        p2: Tuple[float, float],
    ) -> Tuple[float, float]:
        """Find the closest point on a line segment to a given point.

        Args:
            point: Test point
            p1: Start of line segment
            p2: End of line segment

        Returns:
            Closest point on the segment
        """
        px, py = point
        x1, y1 = p1
        x2, y2 = p2

        # Vector from p1 to p2
        dx = x2 - x1
        dy = y2 - y1

        # If segment has zero length, return p1
        if dx == 0 and dy == 0:
            return p1

        # Parameter t represents position along segment (0 to 1)
        t = max(0, min(1, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))

        # Closest point on segment
        closest_x = x1 + t * dx
        closest_y = y1 + t * dy

        return (closest_x, closest_y)

    def get_snapped_position(
        self, original_pos: Tuple[float, float]
    ) -> Tuple[float, float]:
        """Get the snapped position for a point, or original if no snap.

        Args:
            original_pos: Original position to potentially snap

        Returns:
            Snapped position if within threshold, otherwise original position
        """
        snap_target = self.find_snap_point(original_pos)

        if snap_target:
            logger.debug(
                f"Snapping to {snap_target.target_type} at {snap_target.position}"
            )
            return snap_target.position

        return original_pos

    def has_snap_target(self, test_point: Tuple[float, float]) -> bool:
        """Check if a point has a valid snap target.

        Args:
            test_point: Point to test

        Returns:
            True if point would snap to something
        """
        return self.find_snap_point(test_point) is not None
