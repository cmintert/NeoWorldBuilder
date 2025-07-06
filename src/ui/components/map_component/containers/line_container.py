from typing import List, Tuple, Dict, Any, Optional
from PyQt6.QtCore import Qt, pyqtSignal, QPoint
from PyQt6.QtGui import QPainter, QColor, QCursor, QPen, QBrush
from PyQt6.QtWidgets import QLabel, QMenu
from structlog import get_logger

from .base_map_feature_container import BaseMapFeatureContainer
from ui.components.map_component.edit_mode import (
    UnifiedLineGeometry,
    UnifiedLineRenderer,
)
from ui.components.map_component.feature_hit_tester import FeatureHitTester
from ui.components.map_component.line_persistence import LineGeometryPersistence
from ui.components.map_component.utils.coordinate_transformer import (
    CoordinateTransformer,
)

logger = get_logger(__name__)


class LineContainer(BaseMapFeatureContainer):
    """Container widget that handles line visualization and interaction.

    This widget coordinates between geometry, rendering, hit testing, and persistence
    components to provide a complete line editing experience.
    """

    # Line appearance constants
    DEFAULT_LINE_COLOR = "#FF0000"
    DEFAULT_LINE_WIDTH = 2
    DEFAULT_LINE_PATTERN = Qt.PenStyle.SolidLine

    # Control point constants
    BASE_CONTROL_POINT_RADIUS = 4
    MIN_CONTROL_POINT_RADIUS = 3

    # Layout and styling constants
    WIDGET_MARGIN = 5
    MIN_WIDGET_MARGIN = 3
    LABEL_FONT_SIZE_BASE = 8
    MIN_LABEL_FONT_SIZE = 6
    LABEL_PADDING_BASE = 2
    MIN_LABEL_PADDING = 1
    LABEL_PADDING_HORIZONTAL_BASE = 4
    MIN_LABEL_PADDING_HORIZONTAL = 2

    # Minimum line requirements
    MIN_LINE_POINTS = 2

    # Rename feature_clicked to line_clicked for backward compatibility
    line_clicked = pyqtSignal(str)
    geometry_changed = pyqtSignal(
        str, list
    )  # target_node, branches (for compatibility)

    def __init__(self, target_node: str, points_or_branches, parent=None, config=None):
        """Initialize the line container.

        Args:
            target_node (str): The node name this line represents.
            points_or_branches: List of coordinate points for simple lines, or list of branches for branching lines.
            parent (QWidget, optional): Parent widget. Defaults to None.
            config (Config, optional): App configuration. Defaults to None.
        """
        super().__init__(target_node, parent, config)

        # Initialize unified components
        self.geometry = UnifiedLineGeometry(points_or_branches)
        self.hit_tester = FeatureHitTester()
        self.renderer = UnifiedLineRenderer(config)
        self.persistence = LineGeometryPersistence(target_node)

        # Visual style properties
        self.line_color = QColor(self.DEFAULT_LINE_COLOR)
        self.line_width = self.DEFAULT_LINE_WIDTH
        self.line_pattern = self.DEFAULT_LINE_PATTERN

        # Drag state
        self.dragging_control_point = False
        self.dragged_branch_index = 0  # For simple lines, always branch 0
        self.dragged_point_index = -1
        self.drag_start_pos = QPoint()

        self._setup_ui()
        self._update_geometry()

    def _setup_ui(self) -> None:
        """Setup UI components and styling."""
        # Track cursor state
        self._current_cursor = Qt.CursorShape.PointingHandCursor

        # Labels are now always visible (handled by base class)

    def _update_geometry(self) -> None:
        """Update widget geometry based on line points and label size."""
        min_x, min_y, max_x, max_y = self.geometry.get_bounds()

        if min_x == max_x and min_y == max_y:  # No valid bounds
            return

        # Calculate label size requirements
        label_width = self.text_label.width()
        label_height = self.text_label.height()

        # Calculate line center for label positioning
        mid_x, mid_y = self.geometry.get_center()

        # Expand bounds to ensure label fits completely
        label_left = mid_x - label_width // 2
        label_right = mid_x + label_width // 2
        label_top = mid_y - label_height // 2
        label_bottom = mid_y + label_height // 2

        # Use the larger of line bounds or label bounds
        final_min_x = min(min_x, label_left)
        final_max_x = max(max_x, label_right)
        final_min_y = min(min_y, label_top)
        final_max_y = max(max_y, label_bottom)

        # Add margin - use the base class scale
        margin = max(int(self.WIDGET_MARGIN * self._scale), self.MIN_WIDGET_MARGIN)
        self.setGeometry(
            final_min_x - margin,
            final_min_y - margin,
            final_max_x - final_min_x + (2 * margin),
            final_max_y - final_min_y + (2 * margin),
        )

        # Position label (now guaranteed to fit)
        rel_x = mid_x - (final_min_x - margin)
        rel_y = mid_y - (final_min_y - margin)

        self.text_label.move(rel_x - label_width // 2, rel_y - label_height // 2)

    def update_label_style(self) -> None:
        """Update label style based on current scale."""
        # Make sure we're using the base class's _scale property, not the geometry's
        font_size = max(
            int(self.LABEL_FONT_SIZE_BASE * self._scale),
            self.MIN_LABEL_FONT_SIZE,
        )
        self.text_label.setStyleSheet(
            f"""
            QLabel {{
                background-color: rgba(0, 0, 0, 0);
                color: white;
                padding: {max(int(self.LABEL_PADDING_BASE * self._scale), self.MIN_LABEL_PADDING)}px {max(int(self.LABEL_PADDING_HORIZONTAL_BASE * self._scale), self.MIN_LABEL_PADDING_HORIZONTAL)}px;
                border-radius: 3px;
                font-size: {font_size}pt;
            }}
            """
        )
        self.text_label.adjustSize()

    def set_scale(self, scale: float) -> None:
        """Set the current scale and update sizes.

        Args:
            scale (float): The new scale factor.
        """
        # First update the base class scale
        super().set_scale(scale)

        print(f"LineContainer.set_scale called with scale: {scale}")

        # Then update the geometry's scale
        self.geometry.set_scale(scale)

        # Update geometry
        self._update_geometry()

        print(f"LineContainer.set_scale completed")

    def _draw_branch_creation_preview(self, painter, map_tab, widget_offset):
        """Draw branch creation preview with orange line and start point indicator."""
        logger.debug(f"_draw_branch_creation_preview called for {self.target_node}")
        start_point = map_tab._branch_creation_start_point
        if not start_point:
            logger.debug("No start point found")
            return
            
        # Get current mouse position from viewport
        if not hasattr(map_tab, 'image_label'):
            return
            
        viewport = map_tab.image_label
        mouse_pos = viewport.current_mouse_pos
        
        # Convert start point (in original coordinates) to widget coordinates
        # We need to account for scaling and the line container's position
        scale = map_tab.current_scale
        start_x = start_point[0] * scale - widget_offset[0]
        start_y = start_point[1] * scale - widget_offset[1]
        
        # Mouse position needs to be converted relative to this widget
        mouse_widget_pos = self.mapFromGlobal(viewport.mapToGlobal(mouse_pos))
        
        # Draw dashed orange line from start point to mouse position
        pen = QPen(QColor("#FF8800"))  # Orange color
        pen.setWidth(3)
        pen.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.drawLine(
            int(start_x), int(start_y),
            mouse_widget_pos.x(), mouse_widget_pos.y()
        )
        
        # Draw orange circle with white border at start point
        painter.setBrush(QBrush(QColor("#FF8800")))
        painter.setPen(QPen(QColor("#FFFFFF"), 2))
        painter.drawEllipse(int(start_x - 6), int(start_y - 6), 12, 12)
    
    def _find_map_tab(self):
        """Find the parent MapTab instance."""
        return super()._find_map_tab()

    def set_style(
        self, color: str = None, width: int = None, pattern: str = None
    ) -> None:
        """Set the line style properties.

        Args:
            color (str, optional): Hex color code. Defaults to None.
            width (int, optional): Line width. Defaults to None.
            pattern (str, optional): Line pattern name. Defaults to None.
        """
        if color:
            self.line_color = QColor(color)

        if width is not None:
            try:
                self.line_width = int(width) if isinstance(width, str) else width
            except (ValueError, TypeError):
                logger.warning(f"Invalid line width value: {width}, using default")
                self.line_width = self.DEFAULT_LINE_WIDTH

        if pattern:
            pattern_map = {
                "solid": Qt.PenStyle.SolidLine,
                "dash": Qt.PenStyle.DashLine,
                "dot": Qt.PenStyle.DotLine,
                "dashdot": Qt.PenStyle.DashDotLine,
            }
            self.line_pattern = pattern_map.get(pattern.lower(), Qt.PenStyle.SolidLine)

        self.update()  # Redraw with new style

    def set_edit_mode(self, edit_mode: bool) -> None:
        """Enable or disable edit mode for this line.

        Args:
            edit_mode: Whether edit mode should be active.
        """
        super().set_edit_mode(edit_mode)
        print(f"Line {self.target_node}: Edit mode = {edit_mode}")

        # Update cursor based on edit mode
        if edit_mode:
            self.setCursor(QCursor(Qt.CursorShape.CrossCursor))
            self._current_cursor = Qt.CursorShape.CrossCursor
        else:
            self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            self._current_cursor = Qt.CursorShape.PointingHandCursor

        self.update()  # Redraw to show any visual changes

    def _get_style_config(self) -> Dict[str, Any]:
        """Get current style configuration for rendering."""
        return {
            "color": self.line_color,
            "width": max(1, int(self.line_width * self._scale)),
            "pattern": self.line_pattern,
        }

    def _find_controller(self):
        """Find the parent controller for database operations."""
        return super()._find_controller()

    # Event Handlers
    def enterEvent(self, event):
        """Handle mouse enter events."""
        super().enterEvent(event)
        self.update()

    def leaveEvent(self, event):
        """Handle mouse leave events - reset cursor."""
        super().leaveEvent(event)

        # Reset cursor when leaving the line area
        if self.edit_mode:
            self.setCursor(QCursor(Qt.CursorShape.CrossCursor))
            self._current_cursor = Qt.CursorShape.CrossCursor
        else:
            self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            self._current_cursor = Qt.CursorShape.PointingHandCursor

        self.update()

    def paintEvent(self, event):
        """Custom painting for the line."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        widget_offset = (self.x(), self.y())

        # Delegate rendering to unified renderer
        self.renderer.draw_line(
            painter,
            self.geometry,
            self._get_style_config(),
            widget_offset,
        )

        map_tab = self._find_map_tab()
        
        if self.edit_mode:
            # Check if we're in branch creation mode with this line as the target
            highlight_point = None
            if (
                map_tab
                and map_tab.branch_creation_mode
                and hasattr(map_tab, "_branch_creation_target")
                and map_tab._branch_creation_target == self.target_node
                and hasattr(map_tab, "_branch_creation_point_indices")
            ):
                highlight_point = map_tab._branch_creation_point_indices
                print(
                    f"Highlighting point {highlight_point} for branch creation in {self.target_node}"
                )

            # Draw control points with optional highlighting
            self.renderer.draw_control_points(
                painter, self.geometry, widget_offset, highlight_point
            )
        
        # Draw branch creation preview LAST so it appears on top of everything
        if (
            map_tab
            and map_tab.branch_creation_mode
            and hasattr(map_tab, "_branch_creation_target")
            and map_tab._branch_creation_target == self.target_node
            and hasattr(map_tab, "_branch_creation_start_point")
        ):
            self._draw_branch_creation_preview(painter, map_tab, widget_offset)

    def mousePressEvent(self, event):
        """Handle mouse press events for line selection and control point operations."""
        # Check if parent map tab is in branch creation mode - if so, ignore this event
        map_tab = self._find_map_tab()
        if map_tab and getattr(map_tab, "branch_creation_mode", False):
            event.ignore()  # Let the event pass through to parent handlers
            return

        widget_offset = (self.x(), self.y())
        
        if event.button() == Qt.MouseButton.LeftButton and self.edit_mode:
            # First check control point hits using unified hit tester
            branch_idx, point_idx = self.hit_tester.test_control_points(
                event.pos(), self.geometry, widget_offset
            )
            if branch_idx >= 0 and point_idx >= 0:
                self.dragging_control_point = True
                self.dragged_branch_index = branch_idx
                self.dragged_point_index = point_idx
                self.drag_start_pos = event.pos()
                print(f"Starting drag of control point {branch_idx}, {point_idx}")
                event.accept()
                return

            # Then check line segment hits for point insertion
            branch_idx, segment_idx, insertion_point = (
                self.hit_tester.test_line_segments(
                    event.pos(), self.geometry, widget_offset
                )
            )
            if branch_idx >= 0 and segment_idx >= 0:
                self._insert_point_at_segment(branch_idx, segment_idx, insertion_point)
                event.accept()
                return
                
            # If we didn't hit anything in edit mode, ignore the event
            event.ignore()
            return

        # Handle right-clicks for context menu
        elif event.button() == Qt.MouseButton.RightButton and self.edit_mode:
            branch_idx, point_idx = self.hit_tester.test_control_points(
                event.pos(), self.geometry, widget_offset
            )
            if branch_idx >= 0 and point_idx >= 0:
                self._show_control_point_context_menu(
                    branch_idx, point_idx, event.pos()
                )
                event.accept()
                return
            else:
                # Test if we're on a line segment to get branch info
                branch_idx, segment_idx, _ = self.hit_tester.test_line_segments(
                    event.pos(), self.geometry, widget_offset
                )
                if branch_idx >= 0 and segment_idx >= 0:
                    # Show general line context menu with branch info if available
                    self._show_line_context_menu(event.pos(), branch_idx)
                    event.accept()
                    return
                    
            # If we didn't hit anything, ignore the event
            event.ignore()
            return

        # Handle normal line clicks (non-edit mode)
        elif event.button() == Qt.MouseButton.LeftButton and not self.edit_mode:
            # Check if we actually hit the line
            branch_idx, segment_idx, _ = self.hit_tester.test_line_segments(
                event.pos(), self.geometry, widget_offset
            )
            if branch_idx >= 0 and segment_idx >= 0:
                print(f"Line clicked: {self.target_node}")
                self.line_clicked.emit(self.target_node)
                event.accept()
                return
        
        # If none of the above conditions matched, ignore the event
        event.ignore()

    def mouseMoveEvent(self, event):
        """Handle mouse move events for control point dragging and cursor changes."""
        # Handle cursor changes for hovering over control points in edit mode
        if self.edit_mode and not self.dragging_control_point:
            widget_offset = (self.x(), self.y())
            branch_idx, point_idx = self.hit_tester.test_control_points(
                event.pos(), self.geometry, widget_offset
            )

            if branch_idx >= 0 and point_idx >= 0:
                # Hovering over a control point
                if self._current_cursor != Qt.CursorShape.SizeAllCursor:
                    self.setCursor(QCursor(Qt.CursorShape.SizeAllCursor))
                    self._current_cursor = Qt.CursorShape.SizeAllCursor
            else:
                # Not hovering over a control point
                desired_cursor = (
                    Qt.CursorShape.PointingHandCursor
                    if not self.edit_mode
                    else Qt.CursorShape.CrossCursor
                )
                if self._current_cursor != desired_cursor:
                    self.setCursor(QCursor(desired_cursor))
                    self._current_cursor = desired_cursor

        # Handle dragging
        if self.dragging_control_point and self.dragged_point_index >= 0:
            # Calculate the new position for the control point
            new_pos = event.pos()

            # Convert widget-relative position back to map coordinates
            map_x = new_pos.x() + self.x()
            map_y = new_pos.y() + self.y()

            # Convert to original coordinates using coordinate transformer
            map_tab = self._find_map_tab()
            original_pixmap = None
            current_scale = self.geometry._scale

            if (
                map_tab
                and hasattr(map_tab, "image_manager")
                and map_tab.image_manager.original_pixmap
            ):
                original_pixmap = map_tab.image_manager.original_pixmap

            # Use coordinate transformer to convert scaled coordinates to original
            if map_tab and hasattr(map_tab, "image_label"):
                current_pixmap = map_tab.image_label.pixmap()
                if current_pixmap:
                    original_coords = (
                        CoordinateTransformer.scaled_to_original_coordinates(
                            map_x, map_y, current_pixmap, original_pixmap, current_scale
                        )
                    )
                    original_x, original_y = original_coords

                    # Update the geometry with the new point
                    self.geometry.update_point(
                        self.dragged_branch_index,
                        self.dragged_point_index,
                        (original_x, original_y),
                    )
                else:
                    # Fallback to simple scaling if pixmap not available
                    original_x = int(map_x / current_scale)
                    original_y = int(map_y / current_scale)
                    self.geometry.update_point(
                        self.dragged_branch_index,
                        self.dragged_point_index,
                        (original_x, original_y),
                    )
            else:
                # Fallback to simple scaling if map tab not available
                original_x = int(map_x / current_scale)
                original_y = int(map_y / current_scale)
                self.geometry.update_point(
                    self.dragged_branch_index,
                    self.dragged_point_index,
                    (original_x, original_y),
                )

            # Update widget geometry and trigger repaint
            self._update_geometry()
            self.update()

            print(
                f"Dragging point {self.dragged_point_index} to ({original_x}, {original_y})"
            )
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        """Handle mouse release events to end control point dragging."""
        if event.button() == Qt.MouseButton.LeftButton and self.dragging_control_point:
            print(f"Finished dragging control point {self.dragged_point_index}")

            # Update geometry in database
            controller = self._find_controller()
            if controller:
                # Pass the correct geometry based on line type
                if self.geometry.is_branching:
                    self.persistence.update_geometry(
                        self.geometry.original_branches, controller
                    )
                else:
                    self.persistence.update_geometry(
                        self.geometry.original_points, controller
                    )

            # Emit geometry changed signal for branching line compatibility
            self.geometry_changed.emit(
                self.target_node, self.geometry.original_branches
            )

            # Reset drag state
            self.dragging_control_point = False
            self.dragged_point_index = -1
            self.drag_start_pos = QPoint()

            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def _insert_point_at_segment(
        self, branch_index: int, segment_index: int, insertion_point: QPoint
    ) -> None:
        """Insert a new control point at the specified segment."""
        # Convert insertion point from map coordinates to original coordinates
        map_x = insertion_point.x()
        map_y = insertion_point.y()

        # Convert to original coordinates using coordinate transformer
        map_tab = self._find_map_tab()
        original_pixmap = None
        current_scale = self.geometry._scale

        if (
            map_tab
            and hasattr(map_tab, "image_manager")
            and map_tab.image_manager.original_pixmap
        ):
            original_pixmap = map_tab.image_manager.original_pixmap

        # Use coordinate transformer to convert scaled coordinates to original
        if map_tab and hasattr(map_tab, "image_label"):
            current_pixmap = map_tab.image_label.pixmap()
            if current_pixmap:
                original_coords = CoordinateTransformer.scaled_to_original_coordinates(
                    map_x, map_y, current_pixmap, original_pixmap, current_scale
                )
                original_x, original_y = original_coords
            else:
                # Fallback to simple scaling if pixmap not available
                original_x = int(map_x / current_scale)
                original_y = int(map_y / current_scale)
        else:
            # Fallback to simple scaling if map tab not available
            original_x = int(map_x / current_scale)
            original_y = int(map_y / current_scale)

        print(
            f"Inserting point at branch {branch_index}, segment {segment_index}: ({original_x}, {original_y})"
        )

        # Insert into geometry
        insert_index = segment_index + 1
        self.geometry.insert_point(branch_index, insert_index, (original_x, original_y))

        # Update geometry in database
        controller = self._find_controller()
        if controller:
            # Pass the correct geometry based on line type
            if self.geometry.is_branching:
                self.persistence.update_geometry(
                    self.geometry.original_branches, controller
                )
            else:
                self.persistence.update_geometry(
                    self.geometry.original_points, controller
                )

        # Emit geometry changed signal for branching line compatibility
        self.geometry_changed.emit(self.target_node, self.geometry.original_branches)

        # Update the widget geometry and trigger repaint
        self._update_geometry()
        self.update()

        print(f"Point inserted. Line now has {self.geometry.point_count()} points")

    def _show_control_point_context_menu(
        self, branch_index: int, point_index: int, pos: QPoint
    ) -> None:
        """Show context menu for control point operations."""
        # Don't allow deletion if we only have minimum required points
        if self.geometry.point_count() <= self.MIN_LINE_POINTS:
            print(
                f"Cannot delete point - line must have at least {self.MIN_LINE_POINTS} points"
            )
            return

        menu = QMenu(self)

        delete_action = menu.addAction(f"Delete Point {point_index}")
        delete_action.triggered.connect(
            lambda: self._delete_control_point(branch_index, point_index)
        )

        # Add branch creation option if this is a branching line or could become one
        create_branch_action = menu.addAction(f"Create Branch from Point {point_index}")
        create_branch_action.triggered.connect(
            lambda: self._start_branch_creation_from_point(
                branch_index, point_index, pos
            )
        )

        # Show menu at the clicked position
        global_pos = self.mapToGlobal(pos)
        menu.exec(global_pos)

    def _delete_control_point(self, branch_index: int, point_index: int) -> None:
        """Delete a control point."""
        if not self.geometry.delete_point(branch_index, point_index):
            print(
                f"Cannot delete point - line must have at least {self.MIN_LINE_POINTS} points"
            )
            return

        print(f"Deleting control point {branch_index}, {point_index}")

        # Update geometry in database
        controller = self._find_controller()
        if controller:
            # Pass the correct geometry based on line type
            if self.geometry.is_branching:
                self.persistence.update_geometry(
                    self.geometry.original_branches, controller
                )
            else:
                self.persistence.update_geometry(
                    self.geometry.original_points, controller
                )

        # Emit geometry changed signal for branching line compatibility
        self.geometry_changed.emit(self.target_node, self.geometry.original_branches)

        # Update widget and repaint
        self._update_geometry()
        self.update()

        print(f"Point deleted. Line now has {self.geometry.point_count()} points")

    def _show_line_context_menu(self, pos: QPoint, branch_idx: Optional[int] = None) -> None:
        """Show context menu for general line operations.
        
        Args:
            pos: Click position in widget coordinates
            branch_idx: Index of the branch that was clicked (None if not on a specific branch)
        """
        menu = QMenu(self)

        # Add branch creation option
        create_branch_action = menu.addAction("Create Branch Here")
        create_branch_action.triggered.connect(
            lambda: self._start_branch_creation_from_position(pos)
        )
        
        # Add delete branch option if this is a branching line and not the first branch
        if (self.geometry.is_branching and 
            branch_idx is not None and 
            branch_idx > 0 and 
            branch_idx < len(self.geometry.branches)):
            menu.addSeparator()
            delete_branch_action = menu.addAction(f"Delete Branch {branch_idx}")
            delete_branch_action.triggered.connect(
                lambda: self._delete_branch(branch_idx)
            )

        # Show menu at the clicked position
        global_pos = self.mapToGlobal(pos)
        menu.exec(global_pos)

    def _delete_branch(self, branch_idx: int) -> None:
        """Delete a branch from the line.
        
        Args:
            branch_idx: Index of the branch to delete (must be > 0)
        """
        # Safety checks
        if not self.geometry.is_branching:
            logger.warning("Cannot delete branch from non-branching line")
            return
            
        if branch_idx <= 0:
            logger.warning("Cannot delete the main branch (index 0)")
            return
            
        if branch_idx >= len(self.geometry.branches):
            logger.warning(f"Invalid branch index {branch_idx}")
            return
            
        logger.info(f"Deleting branch {branch_idx} from line {self.target_node}")
        
        # Delete the branch from geometry
        if not self.geometry.delete_branch(branch_idx):
            logger.error(f"Failed to delete branch {branch_idx}")
            return
        
        # Update geometry in database
        controller = self._find_controller()
        if controller:
            self.persistence.update_geometry(
                self.geometry.original_branches, controller
            )
        
        # Emit geometry changed signal
        self.geometry_changed.emit(self.target_node, self.geometry.original_branches)
        
        # Update widget and repaint
        self._update_geometry()
        self.update()
        
        logger.info(f"Branch deleted. Line now has {len(self.geometry.branches)} branches")
    
    def _start_branch_creation_from_point(
        self, branch_index: int, point_index: int, pos: QPoint
    ) -> None:
        """Start branch creation from a specific control point."""
        if branch_index >= len(self.geometry.branches) or point_index >= len(
            self.geometry.branches[branch_index]
        ):
            return

        # Get the point coordinates
        point = self.geometry.branches[branch_index][point_index]

        print(
            f"Starting branch creation from point {point_index} in branch {branch_index}: {point}"
        )

        # Trigger branch creation mode in MapTab
        map_tab = self._find_map_tab()
        if map_tab:
            map_tab.branch_creation_mode = True
            map_tab._branch_creation_target = self.target_node
            map_tab._branch_creation_start_point = point
            map_tab.image_label.set_cursor_for_mode("crosshair")

            print(f"Branch creation mode activated for {self.target_node}")

    def _start_branch_creation_from_position(self, pos: QPoint) -> None:
        """Start branch creation from a position on the line."""
        widget_offset = (self.x(), self.y())

        # Find the nearest point on the line to the clicked position
        branch_idx, segment_idx, insertion_point = self.hit_tester.test_line_segments(
            pos, self.geometry, widget_offset
        )

        if branch_idx >= 0 and segment_idx >= 0:
            # Convert insertion point to original coordinates
            map_x = insertion_point.x()
            map_y = insertion_point.y()

            # Convert to original coordinates using coordinate transformer
            map_tab = self._find_map_tab()
            original_pixmap = None
            current_scale = self.geometry._scale

            if (
                map_tab
                and hasattr(map_tab, "image_manager")
                and map_tab.image_manager.original_pixmap
            ):
                original_pixmap = map_tab.image_manager.original_pixmap

            # Use coordinate transformer to convert scaled coordinates to original
            if map_tab and hasattr(map_tab, "image_label"):
                current_pixmap = map_tab.image_label.pixmap()
                if current_pixmap:
                    from .utils.coordinate_transformer import CoordinateTransformer

                    original_coords = (
                        CoordinateTransformer.scaled_to_original_coordinates(
                            map_x, map_y, current_pixmap, original_pixmap, current_scale
                        )
                    )
                    original_x, original_y = original_coords
                else:
                    # Fallback to simple scaling if pixmap not available
                    original_x = int(map_x / current_scale)
                    original_y = int(map_y / current_scale)
            else:
                # Fallback to simple scaling if map tab not available
                original_x = int(map_x / current_scale)
                original_y = int(map_y / current_scale)

            print(
                f"Starting branch creation from line position: ({original_x}, {original_y})"
            )

            # Trigger branch creation mode in MapTab
            if map_tab:
                map_tab.branch_creation_mode = True
                map_tab._branch_creation_target = self.target_node
                map_tab._branch_creation_start_point = (original_x, original_y)
                map_tab.image_label.set_cursor_for_mode("crosshair")

                print(f"Branch creation mode activated for {self.target_node}")

    def create_branch_from_point(
        self, start_x: int, start_y: int, end_x: int, end_y: int
    ) -> None:
        """Create a new branch from an existing point.

        Args:
            start_x: X coordinate of branch start point
            start_y: Y coordinate of branch start point
            end_x: X coordinate of branch end point
            end_y: Y coordinate of branch end point
        """
        print(f"Creating branch from ({start_x}, {start_y}) to ({end_x}, {end_y})")

        # Use the geometry's branch creation method
        if self.geometry.create_branch_from_position(
            (start_x, start_y), (end_x, end_y)
        ):
            # Update geometry in database
            controller = self._find_controller()
            if controller:
                self.persistence.update_geometry(
                    self.geometry.original_branches, controller
                )

            # Emit geometry changed signal
            self.geometry_changed.emit(
                self.target_node, self.geometry.original_branches
            )

            # Update the widget geometry and trigger repaint
            self._update_geometry()
            self.update()

            print(
                f"Branch created. Line now has {len(self.geometry.branches)} branches"
            )
        else:
            print(
                f"Failed to create branch from ({start_x}, {start_y}) to ({end_x}, {end_y})"
            )
