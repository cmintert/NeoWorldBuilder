from typing import List, Tuple
from PyQt6.QtCore import QPoint


class LineHitTester:
    """Handles all hit testing logic for lines and control points."""
    
    LINE_SEGMENT_HIT_TOLERANCE = 5
    CONTROL_POINT_HIT_TOLERANCE = 5
    
    @staticmethod
    def test_control_point(pos: QPoint, control_points: List[dict], widget_offset: Tuple[int, int]) -> int:
        """Test if position hits a control point.
        
        Args:
            pos: Mouse position in widget coordinates
            control_points: List of control point dictionaries
            widget_offset: Widget's (x, y) offset
            
        Returns:
            Index of hit control point, or -1 if no hit
        """
        if not control_points:
            return -1
        
        widget_x, widget_y = widget_offset
        pos_x, pos_y = pos.x(), pos.y()
        
        for i, cp in enumerate(control_points):
            # Convert control point position to widget-relative coordinates
            cp_x = cp["pos"][0] - widget_x
            cp_y = cp["pos"][1] - widget_y
            
            # Quick Manhattan distance check first (cheaper than Euclidean)
            if abs(pos_x - cp_x) > cp["radius"] or abs(pos_y - cp_y) > cp["radius"]:
                continue
                
            # Only do expensive distance calculation if Manhattan check passes
            distance_sq = (pos_x - cp_x) ** 2 + (pos_y - cp_y) ** 2
            if distance_sq <= cp["radius"] ** 2:  # Avoid sqrt by comparing squares
                return i
        
        return -1
    
    @staticmethod
    def test_line_segment(pos: QPoint, scaled_points: List[Tuple[int, int]], widget_offset: Tuple[int, int]) -> Tuple[int, QPoint]:
        """Test if position hits a line segment between control points.
        
        Args:
            pos: Mouse position in widget coordinates
            scaled_points: List of scaled coordinate points
            widget_offset: Widget's (x, y) offset
            
        Returns:
            Tuple of (segment_index, insertion_point) or (-1, QPoint()) if no hit
            segment_index is the index AFTER which to insert the new point
        """
        if len(scaled_points) < 2:
            return -1, QPoint()
        
        # Convert mouse position to map coordinates
        widget_x, widget_y = widget_offset
        map_x = pos.x() + widget_x
        map_y = pos.y() + widget_y
        
        # Check each line segment
        for i in range(len(scaled_points) - 1):
            p1 = scaled_points[i]
            p2 = scaled_points[i + 1]
            
            # Calculate distance from point to line segment
            distance, closest_point = LineHitTester.point_to_line_distance(
                (map_x, map_y), p1, p2
            )
            
            # If close enough to the line (within tolerance)
            if distance <= LineHitTester.LINE_SEGMENT_HIT_TOLERANCE:
                return i, QPoint(int(closest_point[0]), int(closest_point[1]))
        
        return -1, QPoint()
    
    @staticmethod
    def point_to_line_distance(point: Tuple[float, float], line_start: Tuple[int, int], line_end: Tuple[int, int]) -> Tuple[float, Tuple[float, float]]:
        """Calculate distance from point to line segment.
        
        Args:
            point: Point coordinates (x, y)
            line_start: Line start coordinates (x, y)
            line_end: Line end coordinates (x, y)
            
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
