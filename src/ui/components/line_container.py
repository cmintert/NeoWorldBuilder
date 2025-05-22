from typing import List, Tuple
from PyQt6.QtCore import Qt, pyqtSignal, QPoint
from PyQt6.QtGui import QPainter, QPen, QColor, QPainterPath, QCursor
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QLineEdit, QMenu
from structlog import get_logger

logger = get_logger(__name__)


class LineContainer(QWidget):
    """Container widget that handles line visualization.

    This widget renders a line feature on the map with proper scaling and interaction.
    """

    # Line appearance constants
    DEFAULT_LINE_COLOR = "#FF0000"
    DEFAULT_LINE_WIDTH = 2
    DEFAULT_LINE_PATTERN = Qt.PenStyle.SolidLine
    
    # Control point constants
    BASE_CONTROL_POINT_RADIUS = 4
    MIN_CONTROL_POINT_RADIUS = 3
    CONTROL_POINT_OUTLINE_COLOR = "#FF4444"
    CONTROL_POINT_OUTLINE_WIDTH = 2
    CONTROL_POINT_FILL_COLOR = QColor(255, 255, 255, 180)
    
    # Hit testing constants
    CONTROL_POINT_HIT_TOLERANCE = 5  # pixels
    LINE_SEGMENT_HIT_TOLERANCE = 5   # pixels
    
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
        self._scale = 1.0
        self.config = config
        self.target_node = target_node
        self.original_points = points
        self.scaled_points = points.copy()
        self.line_color = QColor(self.DEFAULT_LINE_COLOR)
        self.line_width = self.DEFAULT_LINE_WIDTH
        self.line_pattern = self.DEFAULT_LINE_PATTERN
        self.edit_mode = False
        self.control_points = []

        self.dragging_control_point = False
        self.dragged_point_index = -1
        self.drag_start_pos = QPoint()

        # Make mouse interactive
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.setMouseTracking(True)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        # Set container to be transparent
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # Create a label for the line (similar to pin label)
        self.text_label = QLabel(target_node)
        self.text_label.setParent(self)
        self.update_label_style()
        self.text_label.hide()  # Hide initially, show on hover

        self._update_geometry()

    def _update_geometry(self):
        """Update widget geometry based on line points and label size."""
        if not self.scaled_points:
            return

        # Calculate line bounds
        min_x = min(p[0] for p in self.scaled_points)
        min_y = min(p[1] for p in self.scaled_points)
        max_x = max(p[0] for p in self.scaled_points)
        max_y = max(p[1] for p in self.scaled_points)

        # Calculate label size requirements
        label_width = self.text_label.width()
        label_height = self.text_label.height()

        # Calculate line center for label positioning
        mid_x = (min_x + max_x) // 2
        mid_y = (min_y + max_y) // 2

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

    def _update_line_geometry(self):
        """Update the line geometry in the properties table."""
        try:
            # Convert updated points back to WKT
            from utils.geometry_handler import GeometryHandler

            new_wkt = GeometryHandler.create_line(self.original_points)

            # Find the parent map tab to access the controller
            parent_widget = self.parent()
            while parent_widget and not hasattr(parent_widget, "controller"):
                parent_widget = parent_widget.parent()

            if not parent_widget or not parent_widget.controller:
                print("Could not find controller to update geometry")
                return

            controller = parent_widget.controller
            relationships_table = controller.ui.relationships_table

            if not relationships_table:
                print("No relationships table found")
                return

            # Find the row for this line feature
            for row in range(relationships_table.rowCount()):
                rel_type = relationships_table.item(row, 0)
                target_item = relationships_table.item(row, 1)
                props_item = relationships_table.item(row, 3)

                if not (rel_type and target_item and props_item):
                    continue

                # Check if this is our line
                target_node = ""
                if hasattr(target_item, "text"):
                    target_node = target_item.text()
                else:
                    target_widget = relationships_table.cellWidget(row, 1)
                    if isinstance(target_widget, QLineEdit):
                        target_node = target_widget.text()

                if rel_type.text() == "SHOWS" and target_node == self.target_node:
                    # Found our row - update the geometry
                    import json

                    properties = json.loads(props_item.text())
                    properties["geometry"] = new_wkt

                    # Update the table item
                    props_item.setText(json.dumps(properties))

                    print(f"Updated geometry for {self.target_node}")

                    break

        except Exception as e:
            print(f"Error updating line geometry: {e}")
            import traceback

            traceback.print_exc()

    def update_label_style(self) -> None:
        """Update label style based on current scale."""
        # Match the pin label style
        font_size = max(int(self.LABEL_FONT_SIZE_BASE * self._scale), self.MIN_LABEL_FONT_SIZE)
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
        self._scale = scale

        # Update scaled points
        self.scaled_points = [
            (int(p[0] * scale), int(p[1] * scale)) for p in self.original_points
        ]

        # Update control points if in edit mode
        if self.edit_mode:
            self._generate_control_points()

        # Update label style and geometry
        self.update_label_style()
        self._update_geometry()

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
            self.line_width = width

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

        if edit_mode:
            self._generate_control_points()
        else:
            self.control_points = []
        # TODO: Handle click behavior changes

        self.update()  # Redraw to show any visual changes

    def _generate_control_points(self) -> None:
        """Generate control points for all line vertices."""
        self.control_points = []

        # Create a control point for each vertex
        for i, point in enumerate(self.scaled_points):
            control_point = {
                "pos": point,
                "index": i,
                "radius": max(int(self.BASE_CONTROL_POINT_RADIUS * self._scale), self.MIN_CONTROL_POINT_RADIUS),
            }
            self.control_points.append(control_point)

    def enterEvent(self, event):
        """Show label when mouse enters the line area."""
        self.text_label.show()
        self.update()

    def leaveEvent(self, event):
        """Hide label when mouse leaves the line area."""
        self.text_label.hide()
        self.update()

    def paintEvent(self, event):
        """Custom painting for the line.

        Args:
            event: Paint event object.
        """
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Set up pen (line style)
        pen = QPen(self.line_color)
        pen.setWidth(max(1, int(self.line_width * self._scale)))
        pen.setStyle(self.line_pattern)
        painter.setPen(pen)

        # Draw line segments
        if len(self.scaled_points) >= 2:
            # Adjust points to widget's coordinate system
            adjusted_points = [
                (p[0] - self.x(), p[1] - self.y()) for p in self.scaled_points
            ]

            # Create path from points
            path = QPainterPath()
            path.moveTo(adjusted_points[0][0], adjusted_points[0][1])

            for point in adjusted_points[1:]:
                path.lineTo(point[0], point[1])

            painter.drawPath(path)

        if self.edit_mode and self.control_points:
            self._draw_control_points(painter)

    def _draw_control_points(self, painter: QPainter) -> None:
        """Draw control points for editing."""
        # Set up control point style
        control_pen = QPen(QColor(self.CONTROL_POINT_OUTLINE_COLOR))
        control_pen.setWidth(self.CONTROL_POINT_OUTLINE_WIDTH)
        painter.setPen(control_pen)
        painter.setBrush(self.CONTROL_POINT_FILL_COLOR)

        for cp in self.control_points:
            # Convert to widget-relative coordinates
            x = cp["pos"][0] - self.x()
            y = cp["pos"][1] - self.y()
            radius = cp["radius"]

            painter.drawEllipse(x - radius, y - radius, radius * 2, radius * 2)

    def mousePressEvent(self, event):
        """Handle mouse press events for line selection and control point operations."""
        if event.button() == Qt.MouseButton.LeftButton and self.edit_mode:
            # First check control point hits (existing code)
            hit_index = self._hit_test_control_point(event.pos())
            if hit_index >= 0:
                self.dragging_control_point = True
                self.dragged_point_index = hit_index
                self.drag_start_pos = event.pos()
                print(f"Starting drag of control point {hit_index}")
                event.accept()
                return

            # Then check line segment hits for point insertion
            segment_index, insertion_point = self._hit_test_line_segment(event.pos())
            if segment_index >= 0:
                self._insert_point_at_segment(segment_index, insertion_point)
                event.accept()
                return

        # Handle right-clicks for context menu
        elif event.button() == Qt.MouseButton.RightButton and self.edit_mode:
            hit_index = self._hit_test_control_point(event.pos())
            if hit_index >= 0:
                self._show_control_point_context_menu(hit_index, event.pos())
                event.accept()
                return

            # Debug output to verify signal emission
            print(f"Line clicked: {self.target_node}")
            # NEW: Don't navigate if in edit mode
            if not getattr(self, "edit_mode", False):
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

            # Update the corresponding scaled_points entry
            self.scaled_points[self.dragged_point_index] = (map_x, map_y)

            # Also update the original_points (convert back from scaled)
            original_x = int(map_x / self._scale)
            original_y = int(map_y / self._scale)
            self.original_points[self.dragged_point_index] = (original_x, original_y)

            self._update_geometry()

            print(
                f"Dragging point {self.dragged_point_index} to ({original_x}, {original_y})"
            )

            # Trigger a repaint to show the updated line
            self.update()

            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        """Handle mouse release events to end control point dragging."""
        if event.button() == Qt.MouseButton.LeftButton and self.dragging_control_point:
            print(f"Finished dragging control point {self.dragged_point_index}")

            self._update_line_geometry()

            # Reset drag state
            self.dragging_control_point = False
            self.dragged_point_index = -1
            self.drag_start_pos = QPoint()

            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def _hit_test_control_point(self, pos: QPoint) -> int:
        """Test if a position hits a control point.

        Args:
            pos: Mouse position in widget coordinates

        Returns:
            Index of the hit control point, or -1 if no hit
        """
        if not self.edit_mode or not self.control_points:
            return -1

        for i, cp in enumerate(self.control_points):
            # Convert control point position to widget-relative coordinates
            cp_x = cp["pos"][0] - self.x()
            cp_y = cp["pos"][1] - self.y()

            # Calculate distance from mouse to control point center
            dx = pos.x() - cp_x
            dy = pos.y() - cp_y
            distance = (dx * dx + dy * dy) ** 0.5

            # Check if within the control point's radius
            if distance <= cp["radius"]:
                return i

        return -1

    def _hit_test_line_segment(self, pos: QPoint) -> Tuple[int, QPoint]:
        """Test if a position hits a line segment between control points.

        Args:
            pos: Mouse position in widget coordinates

        Returns:
            Tuple of (segment_index, insertion_point) or (-1, QPoint()) if no hit
            segment_index is the index AFTER which to insert the new point
        """
        if not self.edit_mode or len(self.scaled_points) < 2:
            return -1, QPoint()

        # Convert mouse position to map coordinates
        map_x = pos.x() + self.x()
        map_y = pos.y() + self.y()

        # Check each line segment
        for i in range(len(self.scaled_points) - 1):
            p1 = self.scaled_points[i]
            p2 = self.scaled_points[i + 1]

            # Calculate distance from point to line segment
            distance, closest_point = self._point_to_line_distance(
                (map_x, map_y), p1, p2
            )

            # If close enough to the line (within tolerance)
            if distance <= self.LINE_SEGMENT_HIT_TOLERANCE:
                return i, QPoint(int(closest_point[0]), int(closest_point[1]))

        return -1, QPoint()

    def _point_to_line_distance(self, point, line_start, line_end):
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

    def _insert_point_at_segment(
        self, segment_index: int, insertion_point: QPoint
    ) -> None:
        """Insert a new control point at the specified segment.

        Args:
            segment_index: Index after which to insert the new point
            insertion_point: Map coordinates where to insert the point
        """
        # Convert insertion point from map coordinates to original coordinates
        original_x = int(insertion_point.x() / self._scale)
        original_y = int(insertion_point.y() / self._scale)

        print(
            f"Inserting point at segment {segment_index}: ({original_x}, {original_y})"
        )

        # Insert into original_points (this is the master data)
        insert_index = segment_index + 1
        self.original_points.insert(insert_index, (original_x, original_y))

        # Regenerate scaled_points from original_points
        self.scaled_points = [
            (int(p[0] * self._scale), int(p[1] * self._scale))
            for p in self.original_points
        ]

        # Regenerate control points if in edit mode
        if self.edit_mode:
            self._generate_control_points()

        # Update geometry in the properties table
        self._update_line_geometry()

        # Update the widget geometry and trigger repaint
        self._update_geometry()
        self.update()

        print(f"Point inserted. Line now has {len(self.original_points)} points")

    def _show_control_point_context_menu(self, point_index: int, pos: QPoint) -> None:
        """Show context menu for control point operations.

        Args:
            point_index: Index of the control point
            pos: Position where to show the menu (widget coordinates)
        """
        # Don't allow deletion if we only have minimum required points
        if len(self.original_points) <= self.MIN_LINE_POINTS:
            print(f"Cannot delete point - line must have at least {self.MIN_LINE_POINTS} points")
            return

        menu = QMenu(self)

        delete_action = menu.addAction(f"Delete Point {point_index}")
        delete_action.triggered.connect(lambda: self._delete_control_point(point_index))

        # Show menu at the clicked position
        global_pos = self.mapToGlobal(pos)
        menu.exec(global_pos)

    def _delete_control_point(self, point_index: int) -> None:
        """Delete a control point.

        Args:
            point_index: Index of the point to delete
        """
        if len(self.original_points) <= self.MIN_LINE_POINTS:
            print(f"Cannot delete point - line must have at least {self.MIN_LINE_POINTS} points")
            return

        print(f"Deleting control point {point_index}")

        # Remove from original_points
        del self.original_points[point_index]

        # Regenerate scaled_points
        self.scaled_points = [
            (int(p[0] * self._scale), int(p[1] * self._scale))
            for p in self.original_points
        ]

        # Regenerate control points
        if self.edit_mode:
            self._generate_control_points()

        # Update geometry in properties table
        self._update_line_geometry()

        # Update widget and repaint
        self._update_geometry()
        self.update()

        print(f"Point deleted. Line now has {len(self.original_points)} points")
