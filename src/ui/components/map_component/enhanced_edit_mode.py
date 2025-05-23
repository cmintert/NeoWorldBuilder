"""Enhanced edit mode with robust branching line support.

This module provides a more robust edit mode system that handles:
1. Improved hit testing without bounding box conflicts
2. Proper branching line persistence and editing
3. Non-destructive editing of branch points
4. Consistent coordinate transformation handling
5. Better visual feedback and user experience
"""

import json
from typing import List, Tuple, Dict, Any, Optional, Set
from PyQt6.QtCore import Qt, pyqtSignal, QPoint, QObject
from PyQt6.QtGui import QPainter, QColor, QCursor, QPen, QBrush
from PyQt6.QtWidgets import QWidget, QLabel, QMenu
from structlog import get_logger

logger = get_logger(__name__)


class BranchingLineGeometry:
    """Manages geometry for branching lines as a single logical entity."""
    
    def __init__(self, branches: List[List[Tuple[int, int]]]):
        """Initialize with a list of branches.
        
        Args:
            branches: List of branches, each branch is a list of coordinate points
        """
        self.branches = [branch.copy() for branch in branches]
        self._scale = 1.0
        self._scaled_branches = []
        self._shared_points = {}  # Maps point coordinates to list of (branch_idx, point_idx)
        self._bounds_cache = None
        self._bounds_cache_valid = False
        self._update_shared_points()
        self._update_scaled_branches()
    
    def _update_shared_points(self):
        """Update mapping of shared points between branches."""
        self._shared_points = {}
        
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
    
    def update_point(self, branch_idx: int, point_idx: int, new_point: Tuple[int, int]):
        """Update a point, handling shared points across branches."""
        if branch_idx >= len(self.branches) or point_idx >= len(self.branches[branch_idx]):
            return
        
        old_point = self.branches[branch_idx][point_idx]
        
        # Check if this point is shared with other branches
        if old_point in self._shared_points:
            shared_locations = self._shared_points[old_point]
            
            # Update all instances of this shared point
            for shared_branch_idx, shared_point_idx in shared_locations:
                if shared_branch_idx < len(self.branches) and shared_point_idx < len(self.branches[shared_branch_idx]):
                    self.branches[shared_branch_idx][shared_point_idx] = new_point
        else:
            # Update just this point
            self.branches[branch_idx][point_idx] = new_point
        
        # Rebuild shared points mapping and scaled branches
        self._update_shared_points()
        self._update_scaled_branches()
    
    def insert_point(self, branch_idx: int, point_idx: int, new_point: Tuple[int, int]):
        """Insert a point into a specific branch."""
        if branch_idx >= len(self.branches):
            return
        
        self.branches[branch_idx].insert(point_idx, new_point)
        self._update_shared_points()
        self._update_scaled_branches()
    
    def delete_point(self, branch_idx: int, point_idx: int) -> bool:
        """Delete a point, handling shared points carefully."""
        if branch_idx >= len(self.branches) or point_idx >= len(self.branches[branch_idx]):
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
        self._update_scaled_branches()
        return True
    
    def get_center(self) -> Tuple[int, int]:
        """Get center point of all branches."""
        min_x, min_y, max_x, max_y = self.get_bounds()
        return ((min_x + max_x) // 2, (min_y + max_y) // 2)
    
    @property
    def scaled_branches(self) -> List[List[Tuple[int, int]]]:
        """Get scaled branches."""
        return self._scaled_branches
    
    @property
    def original_branches(self) -> List[List[Tuple[int, int]]]:
        """Get original branches."""
        return self.branches


class EnhancedLineHitTester:
    """Enhanced hit tester that handles both simple and branching lines."""
    
    CONTROL_POINT_RADIUS = 6
    LINE_HIT_TOLERANCE = 8
    SHARED_POINT_RADIUS = 8
    
    @staticmethod
    def test_control_points(pos: QPoint, geometry, widget_offset: Tuple[int, int]) -> Tuple[int, int]:
        """Test control point hits for branching lines.
        
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
                
                # Check if within hit radius
                if distance_sq <= EnhancedLineHitTester.CONTROL_POINT_RADIUS ** 2:
                    return branch_idx, point_idx
        
        return -1, -1
    
    @staticmethod
    def test_line_segments(pos: QPoint, geometry, widget_offset: Tuple[int, int]) -> Tuple[int, int, QPoint]:
        """Test line segment hits for branching lines.
        
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
                distance, closest_point = EnhancedLineHitTester._point_to_line_distance(
                    (map_x, map_y), p1, p2
                )
                
                if distance <= EnhancedLineHitTester.LINE_HIT_TOLERANCE:
                    return branch_idx, segment_idx, QPoint(int(closest_point[0]), int(closest_point[1]))
        
        return -1, -1, QPoint()
    
    @staticmethod
    def _point_to_line_distance(point: Tuple[float, float], line_start: Tuple[int, int], line_end: Tuple[int, int]) -> Tuple[float, Tuple[float, float]]:
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


class EnhancedLineRenderer:
    """Enhanced renderer for both simple and branching lines."""
    
    def __init__(self, config=None):
        self.config = config
    
    def draw_branching_line(self, painter: QPainter, geometry: BranchingLineGeometry, 
                          style_config: Dict[str, Any], widget_offset: Tuple[int, int]):
        """Draw a branching line with all its branches."""
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
    
    def draw_edit_controls(self, painter: QPainter, geometry: BranchingLineGeometry, 
                          widget_offset: Tuple[int, int]):
        """Draw edit controls for branching line."""
        widget_x, widget_y = widget_offset
        
        # Track shared points to draw them differently
        shared_points = set()
        point_counts = {}
        
        # Count point occurrences
        for branch in geometry.scaled_branches:
            for point in branch:
                if point not in point_counts:
                    point_counts[point] = 0
                point_counts[point] += 1
        
        # Identify shared points
        for point, count in point_counts.items():
            if count > 1:
                shared_points.add(point)
        
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
                    radius = EnhancedLineHitTester.SHARED_POINT_RADIUS
                else:
                    # Regular points are blue
                    painter.setBrush(QBrush(QColor("#0000FF")))
                    painter.setPen(QPen(QColor("#FFFFFF"), 1))
                    radius = EnhancedLineHitTester.CONTROL_POINT_RADIUS
                
                painter.drawEllipse(x - radius, y - radius, 2 * radius, 2 * radius)


class EnhancedBranchingLineContainer(QWidget):
    """Enhanced container for branching lines with robust edit mode."""
    
    line_clicked = pyqtSignal(str)
    geometry_changed = pyqtSignal(str, list)  # target_node, branches
    
    def __init__(self, target_node: str, branches: List[List[Tuple[int, int]]], 
                 parent=None, config=None):
        """Initialize enhanced branching line container.
        
        Args:
            target_node: Node name this line represents
            branches: List of branches, each branch is a list of coordinate points
            parent: Parent widget
            config: Configuration object
        """
        super().__init__(parent)
        
        self.target_node = target_node
        self.config = config
        
        # Initialize geometry and components
        self.geometry = BranchingLineGeometry(branches)
        self.hit_tester = EnhancedLineHitTester()
        self.renderer = EnhancedLineRenderer(config)
        
        # Visual style
        self.line_color = QColor("#FF0000")
        self.line_width = 2
        self.line_pattern = Qt.PenStyle.SolidLine
        
        # Edit mode state
        self.edit_mode = False
        self.dragging_point = False
        self.dragged_branch_idx = -1
        self.dragged_point_idx = -1
        self.drag_start_pos = QPoint()
        
        # UI setup
        self._setup_ui()
        self._update_geometry()
    
    def _setup_ui(self):
        """Setup UI components."""
        self.setMouseTracking(True)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # Create label
        self.text_label = QLabel(self.target_node, self)
        self.text_label.setStyleSheet("""
            QLabel {
                background-color: rgba(0, 0, 0, 150);
                color: white;
                padding: 2px 4px;
                border-radius: 3px;
                font-size: 8pt;
            }
        """)
        self.text_label.hide()
    
    def _update_geometry(self):
        """Update widget geometry based on line bounds."""
        min_x, min_y, max_x, max_y = self.geometry.get_bounds()
        
        if min_x == max_x and min_y == max_y:
            return
        
        # Add margin for control points
        margin = 15
        self.setGeometry(
            min_x - margin,
            min_y - margin,
            max_x - min_x + (2 * margin),
            max_y - min_y + (2 * margin)
        )
        
        # Position label at center
        center_x, center_y = self.geometry.get_center()
        rel_x = center_x - (min_x - margin)
        rel_y = center_y - (min_y - margin)
        
        self.text_label.adjustSize()
        self.text_label.move(
            rel_x - self.text_label.width() // 2,
            rel_y - self.text_label.height() // 2
        )
    
    def set_scale(self, scale: float):
        """Set scale and update display."""
        self.geometry.set_scale(scale)
        self._update_geometry()
        self.update()
    
    def set_style(self, color: str = None, width: int = None, pattern: str = None):
        """Set line style."""
        if color:
            self.line_color = QColor(color)
        if width is not None:
            self.line_width = int(width)
        if pattern:
            pattern_map = {
                "solid": Qt.PenStyle.SolidLine,
                "dash": Qt.PenStyle.DashLine,
                "dot": Qt.PenStyle.DotLine,
                "dashdot": Qt.PenStyle.DashDotLine,
            }
            self.line_pattern = pattern_map.get(pattern.lower(), Qt.PenStyle.SolidLine)
        self.update()
    
    def set_edit_mode(self, edit_mode: bool):
        """Enable/disable edit mode."""
        self.edit_mode = edit_mode
        self.update()
    
    def paintEvent(self, event):
        """Custom painting for the branching line."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        widget_offset = (self.x(), self.y())
        
        # Draw the line
        style_config = {
            "color": self.line_color,
            "width": self.line_width,
            "pattern": self.line_pattern,
        }
        self.renderer.draw_branching_line(painter, self.geometry, style_config, widget_offset)
        
        # Draw edit controls if in edit mode
        if self.edit_mode:
            self.renderer.draw_edit_controls(painter, self.geometry, widget_offset)
    
    def mousePressEvent(self, event):
        """Handle mouse press for editing operations."""
        if event.button() == Qt.MouseButton.LeftButton and self.edit_mode:
            widget_offset = (self.x(), self.y())
            
            # Test control point hits
            branch_idx, point_idx = self.hit_tester.test_control_points(
                event.pos(), self.geometry, widget_offset
            )
            
            if branch_idx >= 0 and point_idx >= 0:
                # Start dragging control point
                self.dragging_point = True
                self.dragged_branch_idx = branch_idx
                self.dragged_point_idx = point_idx
                self.drag_start_pos = event.pos()
                event.accept()
                return
            
            # Test line segment hits for point insertion
            branch_idx, segment_idx, insertion_point = self.hit_tester.test_line_segments(
                event.pos(), self.geometry, widget_offset
            )
            
            if branch_idx >= 0 and segment_idx >= 0:
                # Insert new point
                self._insert_point(branch_idx, segment_idx + 1, insertion_point)
                event.accept()
                return
        
        elif event.button() == Qt.MouseButton.RightButton and self.edit_mode:
            # Context menu for point operations
            widget_offset = (self.x(), self.y())
            branch_idx, point_idx = self.hit_tester.test_control_points(
                event.pos(), self.geometry, widget_offset
            )
            
            if branch_idx >= 0 and point_idx >= 0:
                self._show_context_menu(branch_idx, point_idx, event.pos())
                event.accept()
                return
        
        # Regular line click
        if not self.edit_mode:
            self.line_clicked.emit(self.target_node)
        
        event.accept()
    
    def mouseMoveEvent(self, event):
        """Handle mouse movement for point dragging."""
        if self.dragging_point:
            # Convert to map coordinates
            widget_offset = (self.x(), self.y())
            map_x = event.pos().x() + widget_offset[0]
            map_y = event.pos().y() + widget_offset[1]
            
            # Convert to original coordinates (simplified)
            original_x = int(map_x / self.geometry._scale)
            original_y = int(map_y / self.geometry._scale)
            
            # Update point
            self.geometry.update_point(
                self.dragged_branch_idx, self.dragged_point_idx, 
                (original_x, original_y)
            )
            
            # Update display
            self._update_geometry()
            self.update()
            
            event.accept()
        else:
            super().mouseMoveEvent(event)
    
    def mouseReleaseEvent(self, event):
        """Handle mouse release to end dragging."""
        if event.button() == Qt.MouseButton.LeftButton and self.dragging_point:
            # Emit geometry changed signal
            self.geometry_changed.emit(self.target_node, self.geometry.original_branches)
            
            # Reset drag state
            self.dragging_point = False
            self.dragged_branch_idx = -1
            self.dragged_point_idx = -1
            
            event.accept()
        else:
            super().mouseReleaseEvent(event)
    
    def _insert_point(self, branch_idx: int, point_idx: int, insertion_point: QPoint):
        """Insert a new point into the specified branch."""
        # Convert to original coordinates
        widget_offset = (self.x(), self.y())
        map_x = insertion_point.x()
        map_y = insertion_point.y()
        
        original_x = int(map_x / self.geometry._scale)
        original_y = int(map_y / self.geometry._scale)
        
        # Insert point
        self.geometry.insert_point(branch_idx, point_idx, (original_x, original_y))
        
        # Update display
        self._update_geometry()
        self.update()
        
        # Emit change signal
        self.geometry_changed.emit(self.target_node, self.geometry.original_branches)
    
    def _show_context_menu(self, branch_idx: int, point_idx: int, pos: QPoint):
        """Show context menu for point operations."""
        # Check if point can be deleted
        branch = self.geometry.branches[branch_idx]
        if len(branch) <= 2:
            return  # Can't delete, would make branch too short
        
        menu = QMenu(self)
        delete_action = menu.addAction("Delete Point")
        delete_action.triggered.connect(
            lambda: self._delete_point(branch_idx, point_idx)
        )
        
        global_pos = self.mapToGlobal(pos)
        menu.exec(global_pos)
    
    def _delete_point(self, branch_idx: int, point_idx: int):
        """Delete a point from the specified branch."""
        if self.geometry.delete_point(branch_idx, point_idx):
            # Update display
            self._update_geometry()
            self.update()
            
            # Emit change signal
            self.geometry_changed.emit(self.target_node, self.geometry.original_branches)
    
    def enterEvent(self, event):
        """Show label on mouse enter."""
        self.text_label.show()
        super().enterEvent(event)
    
    def leaveEvent(self, event):
        """Hide label on mouse leave."""
        self.text_label.hide()
        super().leaveEvent(event)


class EnhancedFeatureManager(QObject):
    """Enhanced feature manager with robust branching line support."""
    
    feature_clicked = pyqtSignal(str)
    geometry_changed = pyqtSignal(str, list)  # For persistence
    
    def __init__(self, parent_container: QWidget, config=None):
        """Initialize enhanced feature manager."""
        super().__init__()
        self.parent_container = parent_container
        self.config = config
        
        # Feature storage - now separates simple and branching lines
        self.pins = {}  # Regular pins
        self.simple_lines = {}  # Simple lines (single branch)
        self.branching_lines = {}  # Branching lines (multiple branches)
        
        self.current_scale = 1.0
    
    def create_branching_line(self, target_node: str, branches: List[List[Tuple[int, int]]], 
                            style_config: Optional[Dict[str, Any]] = None):
        """Create a branching line feature."""
        # Remove existing if present
        if target_node in self.branching_lines:
            self.branching_lines[target_node].deleteLater()
            del self.branching_lines[target_node]
        
        # Create new branching line container
        line_container = EnhancedBranchingLineContainer(
            target_node, branches, self.parent_container, self.config
        )
        
        # Connect signals
        line_container.line_clicked.connect(self.feature_clicked.emit)
        line_container.geometry_changed.connect(self.geometry_changed.emit)
        
        # Apply style if provided
        if style_config:
            line_container.set_style(
                color=style_config.get("color"),
                width=style_config.get("width"),
                pattern=style_config.get("pattern"),
            )
        
        # Set scale and show
        line_container.set_scale(self.current_scale)
        self.branching_lines[target_node] = line_container
        line_container.show()
        line_container.raise_()
    
    def set_edit_mode(self, active: bool):
        """Set edit mode for all features."""
        # Set edit mode for simple lines
        for line_container in self.simple_lines.values():
            if hasattr(line_container, 'set_edit_mode'):
                line_container.set_edit_mode(active)
        
        # Set edit mode for branching lines
        for line_container in self.branching_lines.values():
            line_container.set_edit_mode(active)
    
    def set_scale(self, scale: float):
        """Update scale for all features."""
        self.current_scale = scale
        
        # Update simple lines
        for line_container in self.simple_lines.values():
            if hasattr(line_container, 'set_scale'):
                line_container.set_scale(scale)
        
        # Update branching lines
        for line_container in self.branching_lines.values():
            line_container.set_scale(scale)
    
    def clear_all_features(self):
        """Clear all features."""
        # Clear simple lines
        for line_container in self.simple_lines.values():
            line_container.deleteLater()
        self.simple_lines.clear()
        
        # Clear branching lines
        for line_container in self.branching_lines.values():
            line_container.deleteLater()
        self.branching_lines.clear()
        
        # Clear pins (if you have them)
        for pin_container in self.pins.values():
            pin_container.deleteLater()
        self.pins.clear()


def integrate_enhanced_edit_mode(map_tab_instance):
    """Integrate enhanced edit mode into existing MapTab instance.
    
    Args:
        map_tab_instance: Existing MapTab instance to enhance
    """
    # Add enhanced components
    map_tab_instance.enhanced_feature_manager = EnhancedFeatureManager(
        map_tab_instance.feature_container, map_tab_instance.config
    )
    
    # Connect signals
    map_tab_instance.enhanced_feature_manager.feature_clicked.connect(
        map_tab_instance._handle_feature_click
    )
    
    # Handle geometry changes from enhanced features
    def handle_geometry_change(target_node: str, branches: List[List[Tuple[int, int]]]):
        """Handle geometry changes from enhanced features."""
        if map_tab_instance.controller:
            try:
                from utils.geometry_handler import GeometryHandler
                
                # Create WKT MultiLineString from branches
                wkt_multiline = GeometryHandler.create_multi_line(branches)
                
                # Find and update the relationship
                relationships_table = map_tab_instance.controller.ui.relationships_table
                
                for row in range(relationships_table.rowCount()):
                    rel_type_item = relationships_table.item(row, 0)
                    target_item = relationships_table.item(row, 1)
                    
                    if (rel_type_item and rel_type_item.text() == "SHOWS" and 
                        target_item and map_tab_instance._extract_target_node(target_item, relationships_table, row) == target_node):
                        
                        # Update properties
                        props_item = relationships_table.item(row, 3)
                        if props_item:
                            properties = json.loads(props_item.text())
                            properties["geometry"] = wkt_multiline
                            properties["geometry_type"] = "MultiLineString"
                            properties["branch_count"] = len(branches)
                            
                            props_item.setText(json.dumps(properties))
                            map_tab_instance.controller.save_data()
                            logger.info(f"Updated geometry for {target_node} with {len(branches)} branches")
                            break
                
            except Exception as e:
                logger.error(f"Error updating geometry: {e}")
    
    map_tab_instance.enhanced_feature_manager.geometry_changed.connect(handle_geometry_change)
    
    # Replace edit mode toggle method
    original_toggle = map_tab_instance.toggle_edit_mode
    
    def enhanced_toggle_edit_mode(active: bool):
        """Enhanced edit mode toggle that handles both systems."""
        # Call original method to maintain compatibility
        original_toggle(active)
        
        # Also set edit mode on enhanced manager
        if hasattr(map_tab_instance, 'enhanced_feature_manager'):
            map_tab_instance.enhanced_feature_manager.set_edit_mode(active)
    
    map_tab_instance.toggle_edit_mode = enhanced_toggle_edit_mode
    
    # Update the map image display to also handle enhanced features
    original_update_display = map_tab_instance._update_map_image_display
    
    def enhanced_update_map_image_display():
        """Enhanced display update that handles both feature managers."""
        # Call original method
        original_update_display()
        
        # Update enhanced feature manager scale
        if hasattr(map_tab_instance, 'enhanced_feature_manager'):
            map_tab_instance.enhanced_feature_manager.set_scale(map_tab_instance.current_scale)
    
    map_tab_instance._update_map_image_display = enhanced_update_map_image_display
    
    # Enhance the load_features method to properly handle branching lines
    original_load_features = map_tab_instance.load_features
    
    def enhanced_load_features():
        """Enhanced feature loading that handles branching lines properly."""
        if not map_tab_instance.controller or not map_tab_instance.controller.ui.relationships_table:
            return
        
        # Collect feature data
        branching_line_data = {}  # Group by target_node
        simple_line_data = []
        pin_data = []
        
        relationships_table = map_tab_instance.controller.ui.relationships_table
        logger.info(f"Starting enhanced_load_features with {relationships_table.rowCount()} relationships")
        
        for row in range(relationships_table.rowCount()):
            try:
                rel_type = relationships_table.item(row, 0)
                if not rel_type or rel_type.text() != "SHOWS":
                    continue
                
                target_item = relationships_table.item(row, 1)
                props_item = relationships_table.item(row, 3)
                
                if not (target_item and props_item):
                    continue
                
                properties = json.loads(props_item.text())
                if "geometry" not in properties:
                    continue
                
                from utils.geometry_handler import GeometryHandler
                if not GeometryHandler.validate_wkt(properties["geometry"]):
                    logger.warning(f"Invalid WKT geometry at row {row}")
                    continue
                
                geometry_type = properties.get("geometry_type", GeometryHandler.get_geometry_type(properties["geometry"]))
                target_node = map_tab_instance._extract_target_node(target_item, relationships_table, row)
                
                logger.info(f"Found {geometry_type} for {target_node}")
                
                if geometry_type == "MultiLineString":
                    # Handle as branching line
                    branches = GeometryHandler.get_coordinates(properties["geometry"])
                    logger.info(f"MultiLineString has {len(branches)} branches")
                    
                    style_config = {
                        "color": properties.get("style_color", "#FF0000"),
                        "width": properties.get("style_width", 2),
                        "pattern": properties.get("style_pattern", "solid"),
                    }
                    
                    if target_node not in branching_line_data:
                        branching_line_data[target_node] = {"branches": [], "style": style_config}
                    
                    branching_line_data[target_node]["branches"] = branches  # Directly assign, don't extend
                
                elif geometry_type == "LineString":
                    # Handle as simple line
                    points = GeometryHandler.get_coordinates(properties["geometry"])
                    style_config = {
                        "color": properties.get("style_color", "#FF0000"),
                        "width": properties.get("style_width", 2),
                        "pattern": properties.get("style_pattern", "solid"),
                    }
                    simple_line_data.append((target_node, points, style_config))
                
                elif geometry_type == "Point":
                    # Handle pins
                    x, y = GeometryHandler.get_coordinates(properties["geometry"])
                    pin_data.append((target_node, x, y))
                
            except Exception as e:
                logger.error(f"Error loading enhanced feature: {e}")
                import traceback
                logger.error(traceback.format_exc())
                continue
        
        logger.info(f"Found features: {len(pin_data)} pins, {len(simple_line_data)} simple lines, {len(branching_line_data)} branching lines")
        
        # Create pins using existing feature manager
        if pin_data:
            map_tab_instance.feature_manager.batch_create_pins(pin_data)
        
        # Create simple lines using existing feature manager
        if simple_line_data:
            map_tab_instance.feature_manager.batch_create_lines(simple_line_data)
        
        # Create enhanced branching lines
        for target_node, data in branching_line_data.items():
            logger.info(f"Creating enhanced branching line for {target_node} with {len(data['branches'])} branches")
            map_tab_instance.enhanced_feature_manager.create_branching_line(
                target_node, data["branches"], data["style"]
            )
    
    map_tab_instance.load_features = enhanced_load_features
    
    # Return the enhanced instance
    return map_tab_instance
