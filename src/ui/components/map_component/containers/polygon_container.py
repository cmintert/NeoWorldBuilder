"""
Polygon container for managing polygon features on the map.
"""

from typing import Dict, List, Optional, Tuple

from PyQt6.QtCore import pyqtSignal

from .base_map_feature_container import BaseMapFeatureContainer
from ..utils.map_logger import get_map_logger

logger = get_map_logger(__name__)


class PolygonContainer(BaseMapFeatureContainer):
    """Container for managing polygon features on the map."""
    
    # Polygon-specific signals
    polygon_clicked = pyqtSignal(str, str)  # feature_id, node_name
    polygon_modified = pyqtSignal(str, list)  # feature_id, new_vertices
    
    def __init__(self, parent=None):
        """
        Initialize the polygon container.
        
        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        
        # Polygon-specific data
        self.polygon_vertices: Dict[str, List[Tuple[float, float]]] = {}
        self.polygon_styles: Dict[str, Dict] = {}
        
        logger.debug("Polygon container initialized")
    
    def add_polygon(
        self,
        feature_id: str,
        node_name: str,
        vertices: List[Tuple[float, float]],
        style: Optional[Dict] = None,
    ) -> None:
        """
        Add a polygon to the container.
        
        Args:
            feature_id: Unique identifier for the polygon
            node_name: Name of the associated node
            vertices: List of (x, y) coordinates defining the polygon
            style: Visual style properties
        """
        # Store polygon data
        self.polygon_vertices[feature_id] = vertices.copy()
        self.polygon_styles[feature_id] = style or {}
        
        # Add to base container tracking
        self.feature_data[feature_id] = {
            'node_name': node_name,
            'vertices': vertices,
            'style': style or {}
        }
        
        logger.debug(
            "Added polygon to container",
            feature_id=feature_id,
            node_name=node_name,
            vertex_count=len(vertices)
        )
    
    def remove_polygon(self, feature_id: str) -> bool:
        """
        Remove a polygon from the container.
        
        Args:
            feature_id: ID of the polygon to remove
            
        Returns:
            True if polygon was removed, False if not found
        """
        if feature_id not in self.polygon_vertices:
            return False
        
        # Remove polygon-specific data
        del self.polygon_vertices[feature_id]
        del self.polygon_styles[feature_id]
        
        # Remove from base container
        if feature_id in self.feature_data:
            del self.feature_data[feature_id]
        
        logger.debug("Removed polygon from container", feature_id=feature_id)
        return True
    
    def get_polygon_vertices(self, feature_id: str) -> Optional[List[Tuple[float, float]]]:
        """
        Get the vertices of a polygon.
        
        Args:
            feature_id: ID of the polygon
            
        Returns:
            List of vertices or None if not found
        """
        return self.polygon_vertices.get(feature_id)
    
    def update_polygon_vertices(
        self,
        feature_id: str,
        vertices: List[Tuple[float, float]]
    ) -> bool:
        """
        Update the vertices of a polygon.
        
        Args:
            feature_id: ID of the polygon
            vertices: New vertices
            
        Returns:
            True if updated, False if polygon not found
        """
        if feature_id not in self.polygon_vertices:
            return False
        
        self.polygon_vertices[feature_id] = vertices.copy()
        
        # Update base container data
        if feature_id in self.feature_data:
            self.feature_data[feature_id]['vertices'] = vertices
        
        # Emit modification signal
        self.polygon_modified.emit(feature_id, vertices)
        
        logger.debug(
            "Updated polygon vertices",
            feature_id=feature_id,
            vertex_count=len(vertices)
        )
        return True
    
    def get_polygon_style(self, feature_id: str) -> Optional[Dict]:
        """
        Get the style of a polygon.
        
        Args:
            feature_id: ID of the polygon
            
        Returns:
            Style dictionary or None if not found
        """
        return self.polygon_styles.get(feature_id)
    
    def update_polygon_style(self, feature_id: str, style: Dict) -> bool:
        """
        Update the style of a polygon.
        
        Args:
            feature_id: ID of the polygon
            style: New style properties
            
        Returns:
            True if updated, False if polygon not found
        """
        if feature_id not in self.polygon_styles:
            return False
        
        self.polygon_styles[feature_id].update(style)
        
        # Update base container data
        if feature_id in self.feature_data:
            self.feature_data[feature_id]['style'].update(style)
        
        logger.debug("Updated polygon style", feature_id=feature_id, style=style)
        return True
    
    def get_polygons_containing_point(
        self,
        x: float,
        y: float
    ) -> List[str]:
        """
        Get all polygons that contain the specified point.
        
        Args:
            x: X coordinate
            y: Y coordinate
            
        Returns:
            List of feature IDs of polygons containing the point
        """
        containing_polygons = []
        
        for feature_id, vertices in self.polygon_vertices.items():
            if self._point_in_polygon(x, y, vertices):
                containing_polygons.append(feature_id)
        
        return containing_polygons
    
    def _point_in_polygon(
        self,
        x: float,
        y: float,
        vertices: List[Tuple[float, float]]
    ) -> bool:
        """
        Check if a point is inside a polygon using ray casting algorithm.
        
        Args:
            x: X coordinate of the point
            y: Y coordinate of the point
            vertices: List of polygon vertices
            
        Returns:
            True if point is inside polygon, False otherwise
        """
        if len(vertices) < 3:
            return False
        
        n = len(vertices)
        inside = False
        
        p1x, p1y = vertices[0]
        for i in range(1, n + 1):
            p2x, p2y = vertices[i % n]
            if y > min(p1y, p2y):
                if y <= max(p1y, p2y):
                    if x <= max(p1x, p2x):
                        if p1y != p2y:
                            xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                        if p1x == p2x or x <= xinters:
                            inside = not inside
            p1x, p1y = p2x, p2y
        
        return inside
    
    def get_polygon_count(self) -> int:
        """
        Get the number of polygons in the container.
        
        Returns:
            Number of polygons
        """
        return len(self.polygon_vertices)
    
    def get_all_polygon_ids(self) -> List[str]:
        """
        Get all polygon feature IDs.
        
        Returns:
            List of all polygon feature IDs
        """
        return list(self.polygon_vertices.keys())
    
    def clear_all_polygons(self) -> None:
        """Clear all polygons from the container."""
        self.polygon_vertices.clear()
        self.polygon_styles.clear()
        self.feature_data.clear()
        
        logger.debug("Cleared all polygons from container")
    
    def emit_polygon_click(self, feature_id: str, node_name: str) -> None:
        """
        Emit polygon click signal.
        
        Args:
            feature_id: ID of the clicked polygon
            node_name: Name of the associated node
        """
        self.polygon_clicked.emit(feature_id, node_name)
        logger.debug("Emitted polygon click", feature_id=feature_id, node_name=node_name)