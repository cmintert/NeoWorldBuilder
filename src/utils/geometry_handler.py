from typing import Dict, Tuple, List, Union

from shapely.geometry import Point, Polygon, LineString, MultiPoint, MultiLineString
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
    def create_multi_line(coordinates: List[List[Tuple[int, int]]]) -> str:
        """Convert list of coordinate lists to WKT multipolygon string."""
        lines = MultiLineString([LineString(coords) for coords in coordinates])
        return dumps(lines)

    @staticmethod
    def is_branching_line(wkt: str) -> bool:
        """Check if WKT represents a branching line (MultiLineString)."""
        try:
            geometry = loads(wkt)
            return isinstance(geometry, MultiLineString)
        except Exception:
            return False

    @staticmethod
    def get_branch_count(wkt: str) -> int:
        """Get number of branches in a MultiLineString."""
        if GeometryHandler.is_branching_line(wkt):
            geometry = loads(wkt)
            return len(geometry.geoms)
        return 1  # Single line

    @staticmethod
    def get_coordinates(
        wkt: str,
    ) -> tuple[int, int] | list[tuple[int, int]] | list[list[tuple[int, int]]]:
        """Extract coordinates from WKT string."""
        geometry = loads(wkt)
        if isinstance(geometry, Point):
            return (int(geometry.x), int(geometry.y))
        elif isinstance(geometry, MultiPoint):
            return [(int(x), int(y)) for x, y in geometry.coords]
        elif isinstance(geometry, (Polygon, LineString)):
            return [(int(x), int(y)) for x, y in geometry.coords]
        elif isinstance(geometry, MultiLineString):
            return [
                [(int(x), int(y)) for x, y in line.coords] for line in geometry.geoms
            ]
        raise ValueError(
            "WKT string must represent Point, MultiPoint, LineString, MultiLineString, or Polygon geometry"
        )

    @staticmethod
    def validate_wkt(wkt: str) -> bool:
        """Validate if string is valid WKT format."""
        try:
            geometry = loads(wkt)
            return isinstance(
                geometry, (Point, MultiPoint, Polygon, LineString, MultiLineString)
            )
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
        elif isinstance(geometry, MultiLineString):
            return "MultiLineString"

        raise ValueError("Unsupported geometry type")
