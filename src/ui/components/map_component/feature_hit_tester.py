from typing import Any, Dict, List, Tuple

from PyQt6.QtCore import QPoint, QRect, QPointF
from PyQt6.QtGui import QPainterPath, QPolygon

from .containers.base_map_feature_container import BaseMapFeatureContainer


class FeatureHitTester:
    """Central hit testing class for all map features.

    This class provides a unified interface for hit testing different types of
    map features (pins, lines, polygons, multipoints, etc.) and can be extended
    for new feature types. It uses specific hit testing strategies based on feature type.
    """

    # Constants for line hit testing
    CONTROL_POINT_RADIUS = 6
    LINE_HIT_TOLERANCE = 8
    SHARED_POINT_RADIUS = 8

    def __init__(self):
        """Initialize the feature hit tester."""
        # Hit test configuration
        self.config = {
            'pin': {
                'hit_radius': 15,  # Radius in pixels for pin hit testing
                'label_padding': 5,  # Extra padding around pin labels
            },
            'line': {
                'segment_tolerance': 8,  # Tolerance for line segment hit testing
                'control_point_radius': 6,  # Radius for control point hit testing
            },
            'polygon': {
                'edge_tolerance': 8,  # Tolerance for polygon edge hit testing
                'vertex_radius': 6,  # Radius for polygon vertex hit testing
            },
            'multipoint': {
                'point_radius': 12,  # Radius for individual point hit testing
                'cluster_threshold': 20,  # Distance threshold for clustering points
                'label_padding': 5,  # Extra padding around point labels
            }
        }

    def test_control_points(self, pos: QPoint, geometry, 
                          widget_offset: Tuple[int, int]) -> Tuple[int, int]:
        """Test control point hits.
        
        Args:
            pos: Mouse position in widget coordinates
            geometry: Line geometry object with scaled_branches attribute
            widget_offset: Widget position offset (x, y)
            
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
                radius = (self.SHARED_POINT_RADIUS if 
                         hasattr(geometry, 'is_branching') and geometry.is_branching and self._is_shared_point(geometry, point)
                         else self.CONTROL_POINT_RADIUS)
                
                if distance_sq <= radius ** 2:
                    return branch_idx, point_idx
        
        return -1, -1
    
    def test_line_segments(self, pos: QPoint, geometry, 
                          widget_offset: Tuple[int, int]) -> Tuple[int, int, QPoint]:
        """Test line segment hits.
        
        Args:
            pos: Mouse position in widget coordinates
            geometry: Line geometry object with scaled_branches attribute
            widget_offset: Widget position offset (x, y)
            
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
                distance, closest_point = self._point_to_line_distance(
                    (map_x, map_y), p1, p2
                )
                
                if distance <= self.LINE_HIT_TOLERANCE:
                    return branch_idx, segment_idx, QPoint(int(closest_point[0]), int(closest_point[1]))
        
        return -1, -1, QPoint()
    
    def _is_shared_point(self, geometry, point: Tuple[int, int]) -> bool:
        """Check if a point is shared between branches.
        
        Args:
            geometry: Line geometry object
            point: Point coordinates to check
            
        Returns:
            True if point is shared between branches, False otherwise
        """
        if not hasattr(geometry, 'is_branching') or not geometry.is_branching:
            return False
        
        # Convert scaled point back to original coordinates to check sharing
        if hasattr(geometry, '_scale'):
            original_point = (int(point[0] / geometry._scale), int(point[1] / geometry._scale))
            return hasattr(geometry, '_shared_points') and original_point in geometry._shared_points and len(geometry._shared_points[original_point]) > 1
        
        return False

    def test_features(self,
                      pos: QPoint,
                      features: List[BaseMapFeatureContainer],
                      map_offset: Tuple[int, int] = (0, 0)) -> List[Dict[str, Any]]:
        """Test if a point hits any of a list of features.

        Args:
            pos: The point to test (in widget coordinates)
            features: List of features to test against
            map_offset: Optional offset to apply (typically widget position)

        Returns:
            List of hit test results, sorted by proximity (closest first)
        """
        results = []

        for feature in features:
            result = self.test_feature(pos, feature, map_offset)
            if result['hit']:
                results.append(result)

        # Sort results by proximity (if details contain distance)
        results.sort(key=lambda r: r.get('details', {}).get('distance', float('inf')))

        return results

    def _get_feature_type(self, feature: BaseMapFeatureContainer) -> str:
        """Determine the type of a feature.

        Args:
            feature: The feature to check

        Returns:
            String type identifier ('pin', 'line', 'polygon', 'multipoint', etc.)
        """
        class_name = feature.__class__.__name__.lower()

        if 'pin' in class_name:
            return 'pin'
        elif 'line' in class_name:
            return 'line'
        elif 'polygon' in class_name:
            return 'polygon'
        elif 'multipoint' in class_name or 'pointset' in class_name:
            return 'multipoint'
        else:
            # Generic fallback using widget geometry
            return 'generic'

    def _test_pin(self, map_pos: QPoint, feature) -> Dict[str, Any]:
        """Test if a point hits a pin feature.

        Args:
            map_pos: The point to test (in map coordinates)
            feature: The pin feature to test

        Returns:
            Dict with hit test results
        """
        # Default result
        result = {
            'hit': False,
            'details': {}
        }

        # Get pin position (center of the pin)
        pin_x = feature.x() + feature.width() // 2
        pin_y = feature.y() + feature.height()  # Pin anchor is at bottom

        # Calculate distance
        dx = map_pos.x() - pin_x
        dy = map_pos.y() - pin_y
        distance_sq = dx * dx + dy * dy

        # Check if within hit radius
        hit_radius = self.config['pin']['hit_radius']
        if distance_sq <= hit_radius * hit_radius:
            result['hit'] = True
            result['details'] = {
                'distance': distance_sq ** 0.5,
                'hit_type': 'pin_body',
                'pin_position': (pin_x, pin_y)
            }
            return result

        # Check label hit
        label_rect = feature.text_label.geometry()
        label_rect = QRect(
            feature.x() + label_rect.x() - self.config['pin']['label_padding'],
            feature.y() + label_rect.y() - self.config['pin']['label_padding'],
            label_rect.width() + 2 * self.config['pin']['label_padding'],
            label_rect.height() + 2 * self.config['pin']['label_padding']
        )

        if label_rect.contains(map_pos):
            result['hit'] = True
            result['details'] = {
                'distance': 0,  # Direct hit on label
                'hit_type': 'pin_label'
            }

        return result

    def _test_line(self, map_pos: QPoint, feature) -> Dict[str, Any]:
        """Test if a point hits a line feature.

        Args:
            map_pos: The point to test (in map coordinates)
            feature: The line feature to test

        Returns:
            Dict with hit test results
        """
        # Default result
        result = {
            'hit': False,
            'details': {}
        }

        # Widget offset for hit tester
        widget_offset = (feature.x(), feature.y())

        # Convert map position to widget-relative position
        widget_pos = QPoint(map_pos.x() - feature.x(), map_pos.y() - feature.y())

        # First check control point hits
        branch_idx, point_idx = self.test_control_points(
            widget_pos, feature.geometry, widget_offset
        )

        if branch_idx >= 0 and point_idx >= 0:
            result['hit'] = True
            result['details'] = {
                'hit_type': 'control_point',
                'branch_index': branch_idx,
                'point_index': point_idx
            }
            return result

        # Then check line segment hits
        branch_idx, segment_idx, insertion_point = self.test_line_segments(
            widget_pos, feature.geometry, widget_offset
        )

        if branch_idx >= 0 and segment_idx >= 0:
            # Calculate distance to insertion point
            dx = insertion_point.x() - widget_pos.x()
            dy = insertion_point.y() - widget_pos.y()
            distance = (dx * dx + dy * dy) ** 0.5

            result['hit'] = True
            result['details'] = {
                'hit_type': 'line_segment',
                'branch_index': branch_idx,
                'segment_index': segment_idx,
                'insertion_point': insertion_point,
                'distance': distance
            }
            return result

        # Check label hit
        label_rect = feature.text_label.geometry()
        label_rect = QRect(
            feature.x() + label_rect.x() - self.config['pin']['label_padding'],
            feature.y() + label_rect.y() - self.config['pin']['label_padding'],
            label_rect.width() + 2 * self.config['pin']['label_padding'],
            label_rect.height() + 2 * self.config['pin']['label_padding']
        )

        if label_rect.contains(map_pos):
            result['hit'] = True
            result['details'] = {
                'distance': 0,  # Direct hit on label
                'hit_type': 'line_label'
            }

        return result

    def _test_polygon(self, map_pos: QPoint, feature) -> Dict[str, Any]:
        """Test if a point hits a polygon feature.

        Args:
            map_pos: The point to test (in map coordinates)
            feature: The polygon feature to test

        Returns:
            Dict with hit test results
        """
        # Default result
        result = {
            'hit': False,
            'details': {}
        }

        # Get polygon vertices in map coordinates
        if hasattr(feature, 'get_vertices'):
            # Use feature's method if available
            vertices = feature.get_vertices()
        elif hasattr(feature, 'geometry') and hasattr(feature.geometry, 'vertices'):
            # Access geometry directly if available
            vertices = feature.geometry.vertices
        else:
            # Fallback - try to deduce from feature properties
            if hasattr(feature, 'polygon') and isinstance(feature.polygon, QPolygon):
                vertices = [(feature.polygon.point(i).x() + feature.x(),
                             feature.polygon.point(i).y() + feature.y())
                            for i in range(feature.polygon.count())]
            else:
                # Can't determine vertices
                return result

        # First check if any vertex is hit
        vertex_radius = self.config['polygon']['vertex_radius']
        for i, vertex in enumerate(vertices):
            v_x, v_y = vertex
            dx = map_pos.x() - v_x
            dy = map_pos.y() - v_y
            distance_sq = dx * dx + dy * dy

            if distance_sq <= vertex_radius * vertex_radius:
                result['hit'] = True
                result['details'] = {
                    'hit_type': 'polygon_vertex',
                    'vertex_index': i,
                    'vertex_position': vertex,
                    'distance': distance_sq ** 0.5
                }
                return result

        # Next check if any edge is hit
        edge_tolerance = self.config['polygon']['edge_tolerance']
        min_distance = float('inf')
        closest_edge = -1
        closest_point = None

        # Create polygon for point-in-polygon test
        polygon = QPolygon([QPoint(int(v[0]), int(v[1])) for v in vertices])

        # Check if inside polygon (use QPainterPath for precise check)
        path = QPainterPath()
        path.addPolygon(polygon)

        if path.contains(QPointF(map_pos.x(), map_pos.y())):
            result['hit'] = True
            result['details'] = {
                'hit_type': 'polygon_interior',
                'distance': 0  # Inside, so distance is 0
            }
            return result

        # Check edges
        for i in range(len(vertices)):
            v1 = vertices[i]
            v2 = vertices[(i + 1) % len(vertices)]  # Wrap around for last vertex

            # Calculate distance from point to line segment
            distance, closest = self._point_to_line_distance(
                (map_pos.x(), map_pos.y()), v1, v2
            )

            if distance < min_distance:
                min_distance = distance
                closest_edge = i
                closest_point = closest

        # Check if closest edge is within tolerance
        if min_distance <= edge_tolerance:
            result['hit'] = True
            result['details'] = {
                'hit_type': 'polygon_edge',
                'edge_index': closest_edge,
                'distance': min_distance,
                'closest_point': closest_point
            }
            return result

        # Check label hit
        if hasattr(feature, 'text_label'):
            label_rect = feature.text_label.geometry()
            label_rect = QRect(
                feature.x() + label_rect.x() - self.config['pin']['label_padding'],
                feature.y() + label_rect.y() - self.config['pin']['label_padding'],
                label_rect.width() + 2 * self.config['pin']['label_padding'],
                label_rect.height() + 2 * self.config['pin']['label_padding']
            )

            if label_rect.contains(map_pos):
                result['hit'] = True
                result['details'] = {
                    'distance': 0,  # Direct hit on label
                    'hit_type': 'polygon_label'
                }

        return result

    def _test_multipoint(self, map_pos: QPoint, feature) -> Dict[str, Any]:
        """Test if a point hits a multipoint feature.

        Args:
            map_pos: The point to test (in map coordinates)
            feature: The multipoint feature to test

        Returns:
            Dict with hit test results
        """
        # Default result
        result = {
            'hit': False,
            'details': {}
        }

        # Get point coordinates in map coordinates
        if hasattr(feature, 'get_points'):
            # Use feature's method if available
            points = feature.get_points()
        elif hasattr(feature, 'geometry') and hasattr(feature.geometry, 'points'):
            # Access geometry directly if available
            points = feature.geometry.points
        else:
            # Fallback - try to deduce from feature properties
            if hasattr(feature, 'points') and isinstance(feature.points, list):
                points = [(p[0] + feature.x(), p[1] + feature.y()) for p in feature.points]
            else:
                # Can't determine points
                return result

        # Check if any point is hit
        point_radius = self.config['multipoint']['point_radius']
        cluster_threshold = self.config['multipoint']['cluster_threshold']

        # Find all hits within radius
        hits = []
        for i, point in enumerate(points):
            p_x, p_y = point
            dx = map_pos.x() - p_x
            dy = map_pos.y() - p_y
            distance_sq = dx * dx + dy * dy

            if distance_sq <= point_radius * point_radius:
                hits.append({
                    'index': i,
                    'position': point,
                    'distance': distance_sq ** 0.5
                })

        if hits:
            # Sort hits by distance
            hits.sort(key=lambda h: h['distance'])

            # Check if we have a cluster
            if len(hits) > 1:
                # Find all points within cluster_threshold of the closest hit
                cluster = [hits[0]]
                for hit in hits[1:]:
                    if hit['distance'] - hits[0]['distance'] <= cluster_threshold:
                        cluster.append(hit)

                if len(cluster) > 1:
                    result['hit'] = True
                    result['details'] = {
                        'hit_type': 'multipoint_cluster',
                        'cluster_size': len(cluster),
                        'cluster_indices': [hit['index'] for hit in cluster],
                        'cluster_positions': [hit['position'] for hit in cluster],
                        'distance': hits[0]['distance']
                    }
                    return result

            # Single point hit
            result['hit'] = True
            result['details'] = {
                'hit_type': 'multipoint_point',
                'point_index': hits[0]['index'],
                'point_position': hits[0]['position'],
                'distance': hits[0]['distance']
            }
            return result

        # Check label hit (if multipoint has a label)
        if hasattr(feature, 'text_label'):
            label_rect = feature.text_label.geometry()
            label_rect = QRect(
                feature.x() + label_rect.x() - self.config['multipoint']['label_padding'],
                feature.y() + label_rect.y() - self.config['multipoint']['label_padding'],
                label_rect.width() + 2 * self.config['multipoint']['label_padding'],
                label_rect.height() + 2 * self.config['multipoint']['label_padding']
            )

            if label_rect.contains(map_pos):
                result['hit'] = True
                result['details'] = {
                    'distance': 0,  # Direct hit on label
                    'hit_type': 'multipoint_label'
                }

        return result

    def test_within_rect(self,
                         rect: QRect,
                         features: List[BaseMapFeatureContainer]) -> List[Dict[str, Any]]:
        """Test which features are within a rectangle (for selection).

        Args:
            rect: The rectangle to test (in map coordinates)
            features: List of features to test against

        Returns:
            List of hit test results for features within the rectangle
        """
        results = []

        for feature in features:
            feature_type = self._get_feature_type(feature)
            feature_rect = feature.geometry()

            # Basic result structure
            result = {
                'hit': False,
                'feature_type': feature_type,
                'feature': feature,
                'details': {}
            }

            # Check if feature intersects with selection rectangle
            if rect.intersects(feature_rect):
                # For polygons and multipoints, we need more precise intersection testing
                if feature_type == 'polygon':
                    if self._polygon_intersects_rect(feature, rect):
                        result['hit'] = True
                        result['details']['intersection_type'] = 'polygon_rect'
                        results.append(result)
                elif feature_type == 'multipoint':
                    points_in_rect = self._multipoint_intersects_rect(feature, rect)
                    if points_in_rect:
                        result['hit'] = True
                        result['details']['intersection_type'] = 'multipoint_rect'
                        result['details']['points_in_rect'] = points_in_rect
                        results.append(result)
                else:
                    # For other feature types, widget geometry intersection is sufficient
                    result['hit'] = True
                    results.append(result)

        return results

    def _polygon_intersects_rect(self, feature, rect: QRect) -> bool:
        """Test if a polygon feature intersects with a rectangle.

        Args:
            feature: The polygon feature to test
            rect: The rectangle to test against

        Returns:
            True if the polygon intersects with the rectangle
        """
        # Get polygon vertices
        if hasattr(feature, 'get_vertices'):
            vertices = feature.get_vertices()
        elif hasattr(feature, 'geometry') and hasattr(feature.geometry, 'vertices'):
            vertices = feature.geometry.vertices
        else:
            if hasattr(feature, 'polygon') and isinstance(feature.polygon, QPolygon):
                vertices = [(feature.polygon.point(i).x() + feature.x(),
                             feature.polygon.point(i).y() + feature.y())
                            for i in range(feature.polygon.count())]
            else:
                # Can't determine vertices, use widget geometry
                return True

        # Create polygon
        polygon = QPolygon([QPoint(int(v[0]), int(v[1])) for v in vertices])

        # Create path for intersection test
        polygon_path = QPainterPath()
        polygon_path.addPolygon(polygon)

        rect_path = QPainterPath()
        rect_path.addRect(rect)

        # Check for intersection
        return not polygon_path.intersects(rect_path)

    def _multipoint_intersects_rect(self, feature, rect: QRect) -> List[int]:
        """Test which points of a multipoint feature are within a rectangle.

        Args:
            feature: The multipoint feature to test
            rect: The rectangle to test against

        Returns:
            List of indices of points that are within the rectangle
        """
        # Get point coordinates
        if hasattr(feature, 'get_points'):
            points = feature.get_points()
        elif hasattr(feature, 'geometry') and hasattr(feature.geometry, 'points'):
            points = feature.geometry.points
        else:
            if hasattr(feature, 'points') and isinstance(feature.points, list):
                points = [(p[0] + feature.x(), p[1] + feature.y()) for p in feature.points]
            else:
                # Can't determine points, use widget geometry
                return [0]  # Assume at least one point is in rect

        # Check which points are in the rectangle
        points_in_rect = []
        for i, point in enumerate(points):
            p_x, p_y = point
            if rect.contains(QPoint(int(p_x), int(p_y))):
                points_in_rect.append(i)

        return points_in_rect

    def _point_to_line_distance(self, point: Tuple[float, float],
                               line_start: Tuple[int, int], 
                               line_end: Tuple[int, int]) -> Tuple[float, Tuple[float, float]]:
        """Calculate distance from point to line segment.

        Args:
            point: The point to test
            line_start: Start point of the line segment
            line_end: End point of the line segment

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
