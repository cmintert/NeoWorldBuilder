from typing import Dict, Tuple, List, Union

from shapely.geometry import Point, Polygon, LineString, MultiPoint
from shapely.wkt import loads, dumps


class GeometryHandler:
    """Handler for WKT format geometries on maps."""

    @staticmethod
    def create_point(x: int, y: int) -> str:
        """Convert x,y coordinates to WKT point string."""
        point = Point(x, y)
        return dumps(point)

    @staticmethod
    def create_point_cloud(coordinates: List[Tuple[int, int]]) -> str:
        """Convert list of coordinates to WKT multipoint string."""
        points = MultiPoint(coordinates)
        return dumps(points)

    @staticmethod
    def create_polygon(coordinates: List[Tuple[int, int]]) -> str:
        """Convert coordinate list to WKT polygon string."""
        polygon = Polygon(coordinates)
        return dumps(polygon)

    @staticmethod
    def create_line(coordinates: List[Tuple[int, int]]) -> str:
        """Convert coordinate list to WKT linestring."""
        line = LineString(coordinates)
        return dumps(line)

    @staticmethod
    def get_coordinates(wkt: str) -> Union[Tuple[int, int], List[Tuple[int, int]]]:
        """Extract coordinates from WKT string."""
        geometry = loads(wkt)
        if isinstance(geometry, Point):
            return (int(geometry.x), int(geometry.y))
        elif isinstance(geometry, MultiPoint):
            return [(int(x), int(y)) for x, y in geometry.coords]
        elif isinstance(geometry, (Polygon, LineString)):
            return [(int(x), int(y)) for x, y in geometry.coords]
        raise ValueError(
            "WKT string must represent Point, MultiPoint, LineString or Polygon geometry"
        )

    @staticmethod
    def validate_wkt(wkt: str) -> bool:
        """Validate if string is valid WKT format."""
        try:
            geometry = loads(wkt)
            return isinstance(geometry, (Point, MultiPoint, Polygon, LineString))
        except Exception:
            return False

    @staticmethod
    def create_geometry_properties(geometry_wkt: str) -> Dict[str, str]:
        """Create properties dictionary with WKT geometry."""
        return {"geometry": geometry_wkt}

    @staticmethod
    def get_geometry_type(wkt: str) -> str:
        """Get the type of geometry from WKT string."""
        geometry = loads(wkt)
        if isinstance(geometry, Point):
            return "Point"
        elif isinstance(geometry, MultiPoint):
            return "PointCloud"
        elif isinstance(geometry, Polygon):
            return "Polygon"
        elif isinstance(geometry, LineString):
            return "LineString"
        raise ValueError("Unsupported geometry type")
