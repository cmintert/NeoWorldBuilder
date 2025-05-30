from typing import List, Tuple, Dict, Any
from PyQt6.QtCore import Qt, pyqtSignal, QPoint
from PyQt6.QtGui import QPainter, QColor, QCursor
from PyQt6.QtWidgets import QWidget, QLabel, QMenu
from structlog import get_logger

from .edit_mode import UnifiedLineGeometry, UnifiedHitTester, UnifiedLineRenderer
from .line_persistence import LineGeometryPersistence
from .utils.coordinate_transformer import CoordinateTransformer

logger = get_logger(__name__)


class LineContainer(QWidget):
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
        super().__init__(parent)

        # Initialize unified components
        self.geometry = UnifiedLineGeometry(points_or_branches)
        self.hit_tester = UnifiedHitTester()
        self.renderer = UnifiedLineRenderer(config)
        self.persistence = LineGeometryPersistence(target_node)

        # Core properties
        self.target_node = target_node
        self.config = config

        # Visual style properties
        self.line_color = QColor(self.DEFAULT_LINE_COLOR)
        self.line_width = self.DEFAULT_LINE_WIDTH
        self.line_pattern = self.DEFAULT_LINE_PATTERN

        # Edit mode state
        self.edit_mode = False

        # Drag state
        self.dragging_control_point = False
        self.dragged_branch_index = 0  # For simple lines, always branch 0
        self.dragged_point_index = -1
        self.drag_start_pos = QPoint()

        self._setup_ui()
        self._update_geometry()

    def _setup_ui(self) -> None:
        """Setup UI components and styling."""
        # Make mouse interactive
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.setMouseTracking(True)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        # Track cursor state
        self._current_cursor = Qt.CursorShape.PointingHandCursor

        # Set container to be transparent
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # Create a label for the line (similar to pin label)
        self.text_label = QLabel(self.target_node)
        self.text_label.setParent(self)
        self.update_label_style()
        self.text_label.hide()  # Hide initially, show on hover

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

        # Add margin
        margin = max(
            int(self.WIDGET_MARGIN * self.geometry._scale), self.MIN_WIDGET_MARGIN
        )
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
        font_size = max(
            int(self.LABEL_FONT_SIZE_BASE * self.geometry._scale),
            self.MIN_LABEL_FONT_SIZE,
        )
        self.text_label.setStyleSheet(
            f"""
            QLabel {{
                background-color: rgba(0, 0, 0, 0);
                color: white;
                padding: {max(int(self.LABEL_PADDING_BASE * self.geometry._scale), self.MIN_LABEL_PADDING)}px {max(int(self.LABEL_PADDING_HORIZONTAL_BASE * self.geometry._scale), self.MIN_LABEL_PADDING_HORIZONTAL)}px;
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
        print(f"LineContainer.set_scale called with scale: {scale}")

        # Let the geometry handle all the scaling logic
        self.geometry.set_scale(scale)

        # No need to generate control points - unified renderer handles this

        # Update label style and geometry
        self.update_label_style()
        self._update_geometry()

        print(f"LineContainer.set_scale completed")

    def _find_map_tab(self):
        """Find the parent MapTab instance.

        Returns:
            MapTab instance or None if not found
        """
        print(f"LineContainer._find_map_tab called")
        parent_widget = self.parent()
        print(f"Initial parent: {parent_widget}")

        # Traverse up the widget hierarchy looking for MapTab
        level = 0
        while parent_widget:
            class_name = parent_widget.__class__.__name__
            print(f"Level {level}: {class_name} - {parent_widget}")

            # Direct check for MapTab
            if class_name == "MapTab":
                print(f"Found MapTab at level {level}")
                return parent_widget

            # Check for feature container's parent (which should be image_label)
            if class_name == "MapViewport" and hasattr(parent_widget, "parent_map_tab"):
                print(f"Found MapViewport with parent_map_tab at level {level}")
                return parent_widget.parent_map_tab

            # Move up the hierarchy
            parent_widget = parent_widget.parent()
            level += 1

            if level > 10:  # Safety break
                print("Too many levels, breaking")
                break

        print("No MapTab found through widget hierarchy")

        # Final fallback - try to find through controller chain
        controller = self._find_controller()
        if (
            controller
            and hasattr(controller, "ui")
            and hasattr(controller.ui, "map_tab")
        ):
            print("Found MapTab through controller")
            return controller.ui.map_tab

        print("No MapTab found anywhere")
        return None

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
        self.edit_mode = edit_mode
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
            "width": max(1, int(self.line_width * self.geometry._scale)),
            "pattern": self.line_pattern,
        }

    def _find_controller(self):
        """Find the parent controller for database operations."""
        parent_widget = self.parent()
        while parent_widget and not hasattr(parent_widget, "controller"):
            parent_widget = parent_widget.parent()

        if parent_widget and hasattr(parent_widget, "controller"):
            return parent_widget.controller
        return None

    # Event Handlers
    def enterEvent(self, event):
        """Show label when mouse enters the line area."""
        self.text_label.show()
        self.update()

    def leaveEvent(self, event):
        """Hide label when mouse leaves the line area."""
        self.text_label.hide()

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

        if self.edit_mode:
            self.renderer.draw_control_points(painter, self.geometry, widget_offset)

    def mousePressEvent(self, event):
        """Handle mouse press events for line selection and control point operations."""
        if event.button() == Qt.MouseButton.LeftButton and self.edit_mode:
            widget_offset = (self.x(), self.y())

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

        # Handle right-clicks for context menu
        elif event.button() == Qt.MouseButton.RightButton and self.edit_mode:
            widget_offset = (self.x(), self.y())
            branch_idx, point_idx = self.hit_tester.test_control_points(
                event.pos(), self.geometry, widget_offset
            )
            if branch_idx >= 0 and point_idx >= 0:
                self._show_control_point_context_menu(
                    branch_idx, point_idx, event.pos()
                )
                event.accept()
                return

        # Handle normal line clicks
        print(f"Line clicked: {self.target_node}")
        if not self.edit_mode:
            self.line_clicked.emit(self.target_node)
        else:
            print(f"Navigation blocked - in edit mode for {self.target_node}")

        event.accept()

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
            self.persistence.update_geometry(self.geometry.original_points, controller)

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
            self.persistence.update_geometry(self.geometry.original_points, controller)

        # Emit geometry changed signal for branching line compatibility
        self.geometry_changed.emit(self.target_node, self.geometry.original_branches)

        # Update widget and repaint
        self._update_geometry()
        self.update()

        print(f"Point deleted. Line now has {self.geometry.point_count()} points")
