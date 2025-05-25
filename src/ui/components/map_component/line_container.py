from typing import List, Tuple, Dict, Any
from PyQt6.QtCore import Qt, pyqtSignal, QPoint
from PyQt6.QtGui import QPainter, QColor, QCursor
from PyQt6.QtWidgets import QWidget, QLabel, QMenu
from structlog import get_logger

from .line_geometry import LineGeometry
from .line_hit_tester import LineHitTester
from .line_renderer import LineRenderer
from .line_persistence import LineGeometryPersistence

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

    def __init__(
        self, target_node: str, points: List[Tuple[int, int]], parent=None, config=None
    ):
        """Initialize the line container.

        Args:
            target_node (str): The node name this line represents.
            points (List[Tuple[int, int]]): List of coordinate points making up the line.
            parent (QWidget, optional): Parent widget. Defaults to None.
            config (Config, optional): App configuration. Defaults to None.
        """
        super().__init__(parent)

        # Initialize separated concerns
        self.geometry = LineGeometry(points)
        self.geometry.set_parent_container(self)
        self.hit_tester = LineHitTester()
        self.renderer = LineRenderer(config)
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
        self.control_points = []

        # Drag state
        self.dragging_control_point = False
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
            int(self.WIDGET_MARGIN * self.geometry.scale), self.MIN_WIDGET_MARGIN
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
            int(self.LABEL_FONT_SIZE_BASE * self.geometry.scale),
            self.MIN_LABEL_FONT_SIZE,
        )
        self.text_label.setStyleSheet(
            f"""
            QLabel {{
                background-color: rgba(0, 0, 0, 0);
                color: white;
                padding: {max(int(self.LABEL_PADDING_BASE * self.geometry.scale), self.MIN_LABEL_PADDING)}px {max(int(self.LABEL_PADDING_HORIZONTAL_BASE * self.geometry.scale), self.MIN_LABEL_PADDING_HORIZONTAL)}px;
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

        # Update control points if in edit mode
        if self.edit_mode:
            self._generate_control_points()

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
        
    def get_style(self) -> Dict[str, Any]:
        """Get the current line style as a dictionary.
        
        Returns:
            Dict with color, width, and pattern
        """
        pattern_str = "solid"  # Default
        if self.line_pattern == Qt.PenStyle.DashLine:
            pattern_str = "dash"
        elif self.line_pattern == Qt.PenStyle.DotLine:
            pattern_str = "dot"
        elif self.line_pattern == Qt.PenStyle.DashDotLine:
            pattern_str = "dashdot"
            
        return {
            "color": self.line_color.name(),
            "width": self.line_width,
            "pattern": pattern_str
        }
        
    def get_points(self) -> List[Tuple[int, int]]:
        """Get the original points of this line.
        
        Returns:
            List of (x, y) tuples in original coordinates
        """
        return self.geometry.original_points.copy()
        
    def hit_test_point(self, pos: QPoint) -> int:
        """Test if position hits a control point on this line.
        
        Args:
            pos: Mouse position in viewport coordinates
            
        Returns:
            Index of hit point, or -1 if no hit
        """
        # Convert to widget-relative coordinates
        widget_pos = self.mapFromGlobal(self.parent().mapToGlobal(pos))
        
        # Generate control points if needed
        if not self.control_points:
            self._generate_control_points()
            
        # Test hits
        return self.hit_tester.test_control_point(
            widget_pos, self.control_points, (self.x(), self.y())
        )

    def set_edit_mode(self, edit_mode: bool) -> None:
        """Enable or disable edit mode for this line.

        Args:
            edit_mode: Whether edit mode should be active.
        """
        self.edit_mode = edit_mode
        print(f"Line {self.target_node}: Edit mode = {edit_mode}")

        if edit_mode:
            self._generate_control_points()
        else:
            self.control_points = []

        self.update()  # Redraw to show any visual changes

    def _generate_control_points(self) -> None:
        """Generate control points for all line vertices."""
        self.control_points = []

        # Create a control point for each vertex
        for i, point in enumerate(self.geometry.scaled_points):
            control_point = {
                "pos": point,
                "index": i,
                "radius": max(
                    int(self.BASE_CONTROL_POINT_RADIUS * self.geometry.scale),
                    self.MIN_CONTROL_POINT_RADIUS,
                ),
            }
            self.control_points.append(control_point)

    def _get_style_config(self) -> Dict[str, Any]:
        """Get current style configuration for rendering."""
        return {
            "color": self.line_color,
            "width": max(1, int(self.line_width * self.geometry.scale)),
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
        self.update()

    def paintEvent(self, event):
        """Custom painting for the line."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        widget_offset = (self.x(), self.y())

        # Delegate rendering to renderer
        self.renderer.draw_line(
            painter,
            self.geometry.scaled_points,
            self._get_style_config(),
            widget_offset,
        )

        if self.edit_mode and self.control_points:
            self.renderer.draw_control_points(
                painter, self.control_points, widget_offset
            )

    def mousePressEvent(self, event):
        """Handle mouse press events for line selection and control point operations."""
        if event.button() == Qt.MouseButton.LeftButton and self.edit_mode:
            widget_offset = (self.x(), self.y())

            # First check control point hits
            hit_index = self.hit_tester.test_control_point(
                event.pos(), self.control_points, widget_offset
            )
            if hit_index >= 0:
                self.dragging_control_point = True
                self.dragged_point_index = hit_index
                self.drag_start_pos = event.pos()
                print(f"Starting drag of control point {hit_index}")
                event.accept()
                return

            # Then check line segment hits for point insertion
            segment_index, insertion_point = self.hit_tester.test_line_segment(
                event.pos(), self.geometry.scaled_points, widget_offset
            )
            if segment_index >= 0:
                self._insert_point_at_segment(segment_index, insertion_point)
                event.accept()
                return

        # Handle right-clicks for context menu
        elif event.button() == Qt.MouseButton.RightButton and self.edit_mode:
            widget_offset = (self.x(), self.y())
            hit_index = self.hit_tester.test_control_point(
                event.pos(), self.control_points, widget_offset
            )
            if hit_index >= 0:
                self._show_control_point_context_menu(hit_index, event.pos())
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
        """Handle mouse move events for control point dragging."""
        if self.dragging_control_point and self.dragged_point_index >= 0:
            # Calculate the new position for the control point
            new_pos = event.pos()

            # Convert widget-relative position back to map coordinates
            map_x = new_pos.x() + self.x()
            map_y = new_pos.y() + self.y()

            # Update the control point position
            self.control_points[self.dragged_point_index]["pos"] = (map_x, map_y)

            # Find map tab to get proper scaling ratios
            map_tab = self._find_map_tab()

            if (
                map_tab
                and hasattr(map_tab, "image_manager")
                and map_tab.image_manager.original_pixmap
            ):
                # Get original and current dimensions for more accurate scaling
                original_width = map_tab.image_manager.original_pixmap.width()
                original_height = map_tab.image_manager.original_pixmap.height()

                current_pixmap = map_tab.image_label.pixmap()
                if current_pixmap:
                    current_width = current_pixmap.width()
                    current_height = current_pixmap.height()

                    # Calculate inverse ratios to convert from scaled to original coordinates
                    width_ratio = original_width / current_width
                    height_ratio = original_height / current_height

                    # Convert to original coordinates using the proper ratios
                    original_x = int(map_x * width_ratio)
                    original_y = int(map_y * height_ratio)

                    # Update the geometry with the new point
                    self.geometry.update_point(
                        self.dragged_point_index, (original_x, original_y)
                    )
            else:
                # Fallback to simple scaling if image manager not available
                original_x = int(map_x / self.geometry.scale)
                original_y = int(map_y / self.geometry.scale)
                self.geometry.update_point(
                    self.dragged_point_index, (original_x, original_y)
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

            # Reset drag state
            self.dragging_control_point = False
            self.dragged_point_index = -1
            self.drag_start_pos = QPoint()

            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def _insert_point_at_segment(
        self, segment_index: int, insertion_point: QPoint
    ) -> None:
        """Insert a new control point at the specified segment."""
        # Convert insertion point from map coordinates to original coordinates
        map_x = insertion_point.x()
        map_y = insertion_point.y()

        # Find map tab to get proper scaling ratios
        map_tab = self._find_map_tab()

        if (
            map_tab
            and hasattr(map_tab, "image_manager")
            and map_tab.image_manager.original_pixmap
        ):
            # Get original and current dimensions for more accurate scaling
            original_width = map_tab.image_manager.original_pixmap.width()
            original_height = map_tab.image_manager.original_pixmap.height()

            current_pixmap = map_tab.image_label.pixmap()
            if current_pixmap:
                current_width = current_pixmap.width()
                current_height = current_pixmap.height()

                # Calculate inverse ratios to convert from scaled to original coordinates
                width_ratio = original_width / current_width
                height_ratio = original_height / current_height

                # Convert to original coordinates using the proper ratios
                original_x = int(map_x * width_ratio)
                original_y = int(map_y * height_ratio)
        else:
            # Fallback to simple scaling if image manager not available
            original_x = int(map_x / self.geometry.scale)
            original_y = int(map_y / self.geometry.scale)

        print(
            f"Inserting point at segment {segment_index}: ({original_x}, {original_y})"
        )

        # Insert into geometry
        insert_index = segment_index + 1
        self.geometry.insert_point(insert_index, (original_x, original_y))

        # Regenerate control points if in edit mode
        if self.edit_mode:
            self._generate_control_points()

        # Update geometry in database
        controller = self._find_controller()
        if controller:
            self.persistence.update_geometry(self.geometry.original_points, controller)

        # Update the widget geometry and trigger repaint
        self._update_geometry()
        self.update()

        print(f"Point inserted. Line now has {self.geometry.point_count()} points")

    def _show_control_point_context_menu(self, point_index: int, pos: QPoint) -> None:
        """Show context menu for control point operations."""
        menu = QMenu(self)

        # Only allow deletion if we have enough points
        if self.geometry.point_count() > self.MIN_LINE_POINTS:
            delete_action = menu.addAction(f"Delete Point {point_index}")
            delete_action.triggered.connect(lambda: self._delete_control_point(point_index))

        # Add branch option
        add_branch_action = menu.addAction("Add Branch")
        add_branch_action.triggered.connect(lambda: self._request_add_branch(point_index))

        # Show menu at the clicked position
        global_pos = self.mapToGlobal(pos)
        menu.exec(global_pos)
        
    def _request_add_branch(self, point_index: int) -> None:
        """Request to add a branch at the specified point.
        
        This will convert this simple line to a branching line.
        """
        print(f"Requesting to add branch at point {point_index} for line {self.target_node}")
        
        # Find parent controller and feature manager
        parent = self.parent()
        while parent and not hasattr(parent, "unified_manager") and not hasattr(parent, "feature_manager"):
            parent = parent.parent()
            
        if parent:
            feature_manager = getattr(parent, "unified_manager", None) or getattr(parent, "feature_manager", None)
            if feature_manager and hasattr(feature_manager, "_convert_simple_to_branching"):
                # Convert to branching line
                feature_manager._convert_simple_to_branching(self.target_node, point_index)
                print(f"Converted {self.target_node} to branching line with branch at point {point_index}")
            else:
                print("Feature manager not found or doesn't support conversion")
        else:
            print("Could not find parent with feature manager")

    def _delete_control_point(self, point_index: int) -> None:
        """Delete a control point."""
        if not self.geometry.delete_point(point_index):
            print(
                f"Cannot delete point - line must have at least {self.MIN_LINE_POINTS} points"
            )
            return

        print(f"Deleting control point {point_index}")

        # Regenerate control points
        if self.edit_mode:
            self._generate_control_points()

        # Update geometry in database
        controller = self._find_controller()
        if controller:
            self.persistence.update_geometry(self.geometry.original_points, controller)

        # Update widget and repaint
        self._update_geometry()
        self.update()

        print(f"Point deleted. Line now has {self.geometry.point_count()} points")
