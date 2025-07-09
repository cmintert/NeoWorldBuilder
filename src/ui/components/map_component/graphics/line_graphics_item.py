"""Line graphics item for QGraphicsView-based map rendering.

This module provides a QGraphicsItem implementation for rendering and interacting with
line features on the map. It supports both simple lines (LineString) and branching
lines (MultiLineString) with full editing capabilities including control point
manipulation, snapping, and visual feedback.

Classes:
    LineGraphicsItem: Main graphics item class for line features

Example:
    Creating a simple line::

        points = [(100, 100), (200, 200), (300, 150)]
        line_item = LineGraphicsItem("Road1", points)
        scene.addItem(line_item)

    Creating a branching line::

        branches = [
            [(100, 100), (200, 200)],
            [(200, 200), (300, 150)],
            [(200, 200), (250, 300)]
        ]
        branching_line = LineGraphicsItem("River1", branches)
        scene.addItem(branching_line)
"""

from typing import Any, Dict, List, Optional, Tuple

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import (
    QBrush,
    QColor,
    QCursor,
    QPainter,
    QPainterPath,
    QPainterPathStroker,
    QPen,
)
from PyQt6.QtWidgets import (
    QGraphicsItem,
    QGraphicsTextItem,
    QStyleOptionGraphicsItem,
    QWidget,
)
from structlog import get_logger

# Import existing line components for reuse
from ui.components.map_component.edit_mode import (
    UnifiedLineGeometry,
    UnifiedLineRenderer,
)
from ui.components.map_component.snap_manager import SnapManager

logger = get_logger(__name__)


class LineGraphicsItem(QGraphicsItem):
    """Graphics item representing a map line with interactive control points.

    This class provides a complete implementation for rendering and interacting with
    line features in a QGraphicsScene. It supports both simple lines (single branch)
    and complex branching lines (multiple branches) with shared points.

    Features:
        - Interactive control point editing in edit mode
        - Point-to-point and point-to-line snapping
        - Visual feedback for dragging, snapping, and selection
        - Automatic bounds calculation and updates
        - Support for line styling (color, width, pattern)
        - Context menu for branch operations
        - Optimized performance during drag operations

    Attributes:
        feature_type (str): Always 'line' for line features
        target_node (str): Name of the node this line represents
        geometry (UnifiedLineGeometry): Line geometry manager
        snap_manager (SnapManager): Handles snapping behavior
        edit_mode (bool): Whether edit mode is active

    Note:
        This class replaces the widget-based LineContainer with a more
        efficient QGraphicsItem implementation that integrates seamlessly
        with the existing line geometry system.
    """

    feature_type = "line"

    # Line appearance constants (from LineContainer)
    DEFAULT_LINE_COLOR = "#FF0000"
    DEFAULT_LINE_WIDTH = 2
    DEFAULT_LINE_PATTERN = Qt.PenStyle.SolidLine

    # Control point constants
    BASE_CONTROL_POINT_RADIUS = 4
    MIN_CONTROL_POINT_RADIUS = 3

    # Label styling
    LABEL_FONT_SIZE_BASE = 8
    MIN_LABEL_FONT_SIZE = 6

    def __init__(
        self,
        target_node: str,
        points_or_branches: List,
        config: Optional[Dict[str, Any]] = None,
        style_properties: Optional[Dict[str, Any]] = None,
        parent=None,
    ):
        """Initialize the line graphics item.

        Creates a new line graphics item with the specified geometry and styling.
        The line can be either a simple line (list of points) or a branching line
        (list of branches, where each branch is a list of points).

        Args:
            target_node: Name of the node this line represents. This should match
                the node name in the Neo4j database.
            points_or_branches: Either a list of (x, y) tuples for a simple line,
                or a list of branches for a branching line. Each branch should be
                a list of (x, y) tuples with at least 2 points.
            config: Optional configuration dictionary containing application settings.
                If not provided, an empty dict will be used.
            style_properties: Optional dictionary containing visual style properties:
                - 'color': Line color as hex string (default: "#FF0000")
                - 'width': Line width in pixels (default: 2)
                - 'pattern': Line pattern ('solid', 'dashed', 'dotted')
            parent: Optional parent QGraphicsItem. Typically None for top-level items.

        Example:
            Simple line::

                line = LineGraphicsItem("Road1", [(0, 0), (100, 100), (200, 50)])

            Branching line::

                branches = [[(0, 0), (100, 100)], [(100, 100), (200, 50)]]
                line = LineGraphicsItem("River1", branches)
        """
        super().__init__(parent)

        self.target_node = target_node
        self.config = config or {}
        self._scale = 1.0
        self.edit_mode = False

        # UX Enhancement: Performance optimization flags
        self._is_being_dragged = False
        self._pending_updates = False

        # UX Enhancement: Visual feedback states
        self._is_highlighted = False
        self._preview_branch = None
        self._snap_preview = None

        # Initialize geometry and rendering components
        self.geometry = UnifiedLineGeometry(points_or_branches)
        self.renderer = UnifiedLineRenderer(self.config)
        # Hit testing handled natively by QGraphicsItem

        # Initialize snap manager
        self.snap_manager = SnapManager()
        self._snap_indicator_pos = None  # Position to show snap indicator

        # Visual style properties - use style_properties if provided
        style_props = style_properties or {}
        logger.debug(f"LineGraphicsItem received style properties: {style_props}")

        self.line_color = QColor(style_props.get("color", self.DEFAULT_LINE_COLOR))
        # Handle width - convert to int if it's a string or empty
        width_value = style_props.get("width", self.DEFAULT_LINE_WIDTH)
        if isinstance(width_value, str):
            if width_value.strip():
                try:
                    self.line_width = int(width_value)
                except ValueError:
                    self.line_width = self.DEFAULT_LINE_WIDTH
            else:
                self.line_width = self.DEFAULT_LINE_WIDTH
        else:
            self.line_width = width_value
        # Convert pattern string to Qt enum if needed
        pattern_str = style_props.get("pattern", "solid")
        if pattern_str == "dashed":
            self.line_pattern = Qt.PenStyle.DashLine
        elif pattern_str == "dotted":
            self.line_pattern = Qt.PenStyle.DotLine
        else:
            self.line_pattern = Qt.PenStyle.SolidLine

        logger.debug(
            f"LineGraphicsItem using color: {self.line_color.name()}, width: {self.line_width}, pattern: {self.line_pattern}"
        )

        # Drag state for control points
        self.dragging_control_point = False
        self.dragged_branch_index = 0
        self.dragged_point_index = -1
        self.drag_start_pos = QPointF()

        # Set item flags
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setAcceptHoverEvents(True)

        # Create text label
        self.text_item = QGraphicsTextItem(self.target_node, self)
        self._setup_text_label()

        # Set Z-value for lines (below pins but above background)
        self.setZValue(50)

        # Update geometry
        self._update_bounds()

        logger.debug(
            f"Created LineGraphicsItem for {target_node} with {len(points_or_branches)} elements"
        )

    def _setup_text_label(self) -> None:
        """Set up the text label for the line.

        Positions the text label at the midpoint of the first branch and applies
        initial styling. The label displays the target node name.
        """
        # Position label at the midpoint of the first branch
        if self.geometry.branches and self.geometry.branches[0]:
            midpoint = self._get_line_midpoint()
            self.text_item.setPos(midpoint.x(), midpoint.y())

        # Style the text
        self._update_text_style()

    def _get_line_midpoint(self) -> QPointF:
        """Get the midpoint of the line for label positioning.

        Calculates the midpoint along the entire line path, not just the geometric
        center. This ensures the label appears on the line itself rather than
        potentially floating in space for curved lines.

        Returns:
            QPointF: The midpoint coordinates along the line path. If the line
                has no points, returns QPointF(0, 0).

        Note:
            For branching lines, only considers the first branch for label placement.
        """
        if not self.geometry.branches or not self.geometry.branches[0]:
            return QPointF(0, 0)

        points = self.geometry.branches[0]
        if len(points) < 2:
            return QPointF(points[0][0] if points else 0, points[0][1] if points else 0)

        # Find the midpoint along the line path
        total_length = 0
        segment_lengths = []

        for i in range(len(points) - 1):
            p1 = QPointF(points[i][0], points[i][1])
            p2 = QPointF(points[i + 1][0], points[i + 1][1])
            length = (p2 - p1).manhattanLength()
            segment_lengths.append(length)
            total_length += length

        if total_length == 0:
            return QPointF(points[0][0], points[0][1])

        # Find the segment containing the midpoint
        target_length = total_length / 2
        current_length = 0

        for i, segment_length in enumerate(segment_lengths):
            if current_length + segment_length >= target_length:
                # Midpoint is in this segment
                ratio = (target_length - current_length) / segment_length
                p1 = QPointF(points[i][0], points[i][1])
                p2 = QPointF(points[i + 1][0], points[i + 1][1])
                return p1 + ratio * (p2 - p1)
            current_length += segment_length

        # Fallback to last point
        return QPointF(points[-1][0], points[-1][1])

    def _update_text_style(self) -> None:
        """Update text label styling based on scale."""
        font_size = max(
            int(self.LABEL_FONT_SIZE_BASE * self._scale), self.MIN_LABEL_FONT_SIZE
        )
        font = self.text_item.font()
        font.setPointSize(font_size)
        self.text_item.setFont(font)

        # Set text color to white for visibility
        self.text_item.setDefaultTextColor(QColor(255, 255, 255))

    def _update_bounds(self) -> None:
        """Update the item's bounds based on line geometry."""
        if not self.geometry.branches:
            return

        # Get bounds from geometry
        min_x, min_y, max_x, max_y = self.geometry.get_bounds()

        if min_x == max_x and min_y == max_y:
            # Single point or no valid bounds
            return

        # Tell Qt that the geometry is about to change
        self.prepareGeometryChange()

        # Add padding for control points and labels
        padding = max(self.BASE_CONTROL_POINT_RADIUS * 2, 10)
        self._bounds = QRectF(
            min_x - padding,
            min_y - padding,
            max_x - min_x + 2 * padding,
            max_y - min_y + 2 * padding,
        )

        logger.debug(f"Updated bounds for {self.target_node}: {self._bounds}")

    def boundingRect(self) -> QRectF:
        """Return the bounding rectangle of the line.

        This method is required by QGraphicsItem and is used by the graphics
        framework for item culling, hit testing, and scene updates. The bounds
        include padding for control points and labels.

        Returns:
            QRectF: Bounding rectangle in item coordinates that encompasses
                all line segments, control points, and labels. Returns a small
                default rectangle if bounds haven't been calculated yet.

        Note:
            The bounds are cached and only recalculated when the geometry changes.
            This is critical for performance in scenes with many items.
        """
        if hasattr(self, "_bounds"):
            return self._bounds

        # Fallback bounds
        return QRectF(-10, -10, 20, 20)

    def shape(self) -> QPainterPath:
        """Return the precise shape for hit testing.

        This method defines the exact clickable area of the line. Unlike boundingRect(),
        which returns a simple rectangle, shape() returns the actual line path with
        a stroke width for easier clicking. This is used for precise mouse interaction.

        Returns:
            QPainterPath: The precise shape of the line including stroke width.
                Returns an empty path if the line has no valid geometry.

        Note:
            The path includes all branches and uses a minimum stroke width of 5 pixels
            to ensure lines are easily clickable even when drawn with thin strokes.
        """
        path = QPainterPath()

        if not self.geometry.branches:
            return path

        # Create path for all branches
        for branch in self.geometry.branches:
            if len(branch) < 2:
                continue

            branch_path = QPainterPath()
            branch_path.moveTo(branch[0][0], branch[0][1])

            for point in branch[1:]:
                branch_path.lineTo(point[0], point[1])

            # Create stroke path for better hit testing
            # Use QPainterPathStroker for creating hit area
            stroker = QPainterPathStroker()
            stroker.setWidth(max(self.line_width, 5))  # Minimum hit area
            stroke_path = stroker.createStroke(branch_path)
            path.addPath(stroke_path)

        return path

    def _draw_selection_outline(self, painter: QPainter) -> None:
        """Draw GIS-standard selection outline around the line.

        Args:
            painter: QPainter instance
        """
        # GIS Enhancement: Draw selection halo
        for branch in self.geometry.branches:
            if len(branch) < 2:
                continue

            # Create selection outline pen
            outline_pen = QPen(QColor(0, 120, 255, 180))  # Blue selection color
            outline_pen.setWidth(self.line_width + 4)  # Wider than main line
            outline_pen.setStyle(Qt.PenStyle.SolidLine)

            painter.setPen(outline_pen)

            # Draw outline path
            path = QPainterPath()
            path.moveTo(branch[0][0], branch[0][1])

            for point in branch[1:]:
                path.lineTo(point[0], point[1])

            painter.drawPath(path)

    def _draw_preview_branch(self, painter: QPainter) -> None:
        """Draw preview branch during creation mode.

        Args:
            painter: QPainter instance
        """
        if not self._preview_branch:
            return

        start_point, end_point = self._preview_branch

        # GIS Enhancement: Dashed preview line
        preview_pen = QPen(QColor(255, 165, 0, 200))  # Orange preview color
        preview_pen.setWidth(max(2, self.line_width))
        preview_pen.setStyle(Qt.PenStyle.DashLine)

        painter.setPen(preview_pen)
        painter.drawLine(start_point, end_point)

        # Draw preview endpoints
        endpoint_brush = QBrush(QColor(255, 165, 0, 150))
        painter.setBrush(endpoint_brush)
        painter.setPen(Qt.PenStyle.NoPen)

        # Use the center point and radius overload
        painter.drawEllipse(start_point, 4.0, 4.0)
        painter.drawEllipse(end_point, 4.0, 4.0)

    def _draw_snap_preview(self, painter: QPainter) -> None:
        """Draw snap point preview for precise positioning.

        Args:
            painter: QPainter instance
        """
        if not self._snap_preview:
            return

        # GIS Enhancement: Snap indicator circle
        snap_pen = QPen(QColor(255, 0, 255, 200))  # Magenta snap color
        snap_pen.setWidth(2)

        painter.setPen(snap_pen)
        painter.setBrush(QBrush(QColor(255, 0, 255, 50)))

        # Draw snap circle
        snap_radius = 6
        painter.drawEllipse(
            int(self._snap_preview.x() - snap_radius),
            int(self._snap_preview.y() - snap_radius),
            snap_radius * 2,
            snap_radius * 2,
        )

    def _draw_snap_indicator(
        self, painter: QPainter, snap_pos: Tuple[float, float]
    ) -> None:
        """Draw snap indicator when a point is snapping.

        Args:
            painter: QPainter instance
            snap_pos: Position where snapping is occurring
        """
        # Visual feedback for active snapping
        snap_pen = QPen(QColor(0, 255, 0, 255))  # Bright green for active snap
        snap_pen.setWidth(3)

        painter.setPen(snap_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        # Draw crosshair at snap position
        x, y = int(snap_pos[0]), int(snap_pos[1])
        cross_size = 8

        # Horizontal line
        painter.drawLine(x - cross_size, y, x + cross_size, y)
        # Vertical line
        painter.drawLine(x, y - cross_size, x, y + cross_size)

        # Draw a circle around the snap point
        painter.drawEllipse(
            x - cross_size, y - cross_size, cross_size * 2, cross_size * 2
        )

    def _get_branch_color(self, branch_idx: int) -> QColor:
        """Get a consistent color for a branch based on its stable ID.

        Args:
            branch_idx: Index of the branch

        Returns:
            QColor for the branch
        """
        # Define a palette of distinct colors for branches
        branch_colors = [
            QColor(255, 100, 100),  # Red - Main stem
            QColor(100, 150, 255),  # Blue - Branch 1
            QColor(100, 255, 100),  # Green - Branch 2
            QColor(255, 255, 100),  # Yellow - Branch 3
            QColor(255, 100, 255),  # Magenta - Branch 4
            QColor(100, 255, 255),  # Cyan - Branch 5
            QColor(255, 150, 100),  # Orange - Branch 6
            QColor(150, 100, 255),  # Purple - Branch 7
        ]

        # Get stable ID for this branch if available
        if hasattr(self.geometry, "get_stable_id_from_branch_index"):
            stable_id = self.geometry.get_stable_id_from_branch_index(branch_idx)
            if stable_id:
                # Use stable ID to ensure consistent colors
                if stable_id == "main_line" or stable_id == "main_stem":
                    return branch_colors[0]  # Always red for main
                elif stable_id.startswith("branch_"):
                    try:
                        branch_num = int(stable_id.split("_")[1])
                        return branch_colors[min(branch_num, len(branch_colors) - 1)]
                    except (ValueError, IndexError):
                        pass

        # Fallback to index-based color
        return branch_colors[branch_idx % len(branch_colors)]

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget: Optional[QWidget] = None,
    ) -> None:
        """Paint the line with enhanced GIS-standard visual feedback.

        Args:
            painter: QPainter instance
            option: Style options
            widget: Widget being painted on
        """
        if not self.geometry.branches:
            return

        # GIS Enhancement: Selection/highlight outline
        if self._is_highlighted:
            self._draw_selection_outline(painter)

        # Draw all branches
        for branch_idx, branch in enumerate(self.geometry.branches):
            if len(branch) < 2:
                continue

            # Set up pen with enhanced styling
            if self.edit_mode and hasattr(self.geometry, "stable_branch_ids"):
                # Use different colors for each branch in edit mode
                branch_color = self._get_branch_color(branch_idx)
                pen = QPen(branch_color)
            else:
                # Use default color in normal mode
                pen = QPen(self.line_color)

            pen.setWidth(self.line_width)
            pen.setStyle(self.line_pattern)

            # GIS Enhancement: Anti-aliasing for smooth lines
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            painter.setPen(pen)

            # Draw the line
            path = QPainterPath()
            path.moveTo(branch[0][0], branch[0][1])

            for point in branch[1:]:
                path.lineTo(point[0], point[1])

            painter.drawPath(path)

        # GIS Enhancement: Draw preview branch during creation
        if self._preview_branch:
            self._draw_preview_branch(painter)

        # GIS Enhancement: Draw snap preview
        if self._snap_preview:
            self._draw_snap_preview(painter)

        # Draw snap indicator if we're snapping
        if self._snap_indicator_pos and self.dragging_control_point:
            self._draw_snap_indicator(painter, self._snap_indicator_pos)

        # Draw control points in edit mode
        if self.edit_mode:
            self._draw_control_points(painter)

        # Draw text background
        if self.text_item:
            text_rect = self.text_item.boundingRect()
            text_pos = self.text_item.pos()

            # Enhanced text background with better visibility
            bg_rect = QRectF(
                text_pos.x() - 3,
                text_pos.y() - 2,
                text_rect.width() + 6,
                text_rect.height() + 4,
            )

            # GIS Enhancement: Better contrast background
            painter.setBrush(QBrush(QColor(0, 0, 0, 120)))
            painter.setPen(QPen(QColor(255, 255, 255, 80), 1))
            painter.drawRoundedRect(bg_rect, 4, 4)

    def _draw_control_points(self, painter: QPainter) -> None:
        """Draw enhanced GIS-style control points for edit mode.

        Args:
            painter: QPainter instance
        """
        # GIS Enhancement: Scale-responsive control points
        base_radius = max(
            int(self.BASE_CONTROL_POINT_RADIUS * self._scale),
            self.MIN_CONTROL_POINT_RADIUS,
        )

        # Draw control points for all branches
        for branch_idx, branch in enumerate(self.geometry.branches):
            # Get branch color for this branch
            branch_color = (
                self._get_branch_color(branch_idx)
                if hasattr(self.geometry, "stable_branch_ids")
                else QColor(255, 255, 255)
            )

            for point_idx, point in enumerate(branch):
                x, y = point[0], point[1]

                # Check if this is a shared point (branching point)
                is_shared = self._is_shared_point(point, branch_idx, point_idx)

                # GIS Enhancement: Different styles for different point types
                if is_shared:
                    # Branching points: Diamond shape with blue color
                    self._draw_branching_point(painter, x, y, base_radius + 2)
                elif point_idx == 0 or point_idx == len(branch) - 1:
                    # Endpoints: Square with branch color
                    self._draw_endpoint(painter, x, y, base_radius, branch_color)
                else:
                    # Regular control points: Circle with branch color
                    self._draw_regular_point(
                        painter, x, y, base_radius - 1, branch_color
                    )

    def _draw_branching_point(
        self, painter: QPainter, x: float, y: float, radius: int
    ) -> None:
        """Draw a diamond-shaped branching point."""
        # GIS Enhancement: Diamond shape for branching points
        diamond_pen = QPen(QColor(0, 100, 200), 2)
        diamond_brush = QBrush(QColor(100, 150, 255, 200))

        painter.setPen(diamond_pen)
        painter.setBrush(diamond_brush)

        # Create diamond path
        diamond = QPainterPath()
        diamond.moveTo(x, y - radius)  # Top
        diamond.lineTo(x + radius, y)  # Right
        diamond.lineTo(x, y + radius)  # Bottom
        diamond.lineTo(x - radius, y)  # Left
        diamond.closeSubpath()

        painter.drawPath(diamond)

    def _draw_endpoint(
        self,
        painter: QPainter,
        x: float,
        y: float,
        radius: int,
        branch_color: QColor = None,
    ) -> None:
        """Draw a square-shaped endpoint."""
        # Use branch color if provided, otherwise default green
        if branch_color:
            # Make the branch color darker for the border
            darker_color = branch_color.darker(150)
            endpoint_pen = QPen(darker_color, 2)
            # Make the branch color semi-transparent for the fill
            fill_color = QColor(branch_color)
            fill_color.setAlpha(180)
            endpoint_brush = QBrush(fill_color)
        else:
            # Default green for endpoints
            endpoint_pen = QPen(QColor(0, 150, 0), 2)
            endpoint_brush = QBrush(QColor(100, 255, 100, 180))

        painter.setPen(endpoint_pen)
        painter.setBrush(endpoint_brush)

        # Draw square
        # Convert to int only for drawing
        painter.drawRect(int(x - radius), int(y - radius), radius * 2, radius * 2)

    def _draw_regular_point(
        self,
        painter: QPainter,
        x: float,
        y: float,
        radius: int,
        branch_color: QColor = None,
    ) -> None:
        """Draw a circular regular control point."""
        # Use branch color if provided, otherwise default white
        if branch_color:
            # Make the branch color darker for the border
            darker_color = branch_color.darker(150)
            point_pen = QPen(darker_color, 1)
            # Make the branch color semi-transparent for the fill
            fill_color = QColor(branch_color)
            fill_color.setAlpha(200)
            point_brush = QBrush(fill_color)
        else:
            # Default white for regular points
            point_pen = QPen(QColor(100, 100, 100), 1)
            point_brush = QBrush(QColor(255, 255, 255, 200))

        painter.setPen(point_pen)
        painter.setBrush(point_brush)

        # Draw circle with subtle shadow effect
        # Convert to int only for drawing
        painter.drawEllipse(int(x - radius), int(y - radius), radius * 2, radius * 2)

    def _is_shared_point(
        self, point: Tuple[int, int], branch_idx: int, point_idx: int
    ) -> bool:
        """Check if a point is shared between branches.

        Args:
            point: The point coordinates
            branch_idx: Branch index
            point_idx: Point index within branch

        Returns:
            True if the point is shared
        """
        if not self.geometry.is_branching:
            return False

        point_key = (round(point[0]), round(point[1]))
        return point_key in self.geometry._shared_points

    def mousePressEvent(self, event) -> None:
        """Handle mouse press events with enhanced UX feedback.

        Processes mouse clicks on the line, handling different behaviors based
        on edit mode and click modifiers. In edit mode, supports control point
        manipulation and line editing. In normal mode, emits click signals for
        navigation.

        Args:
            event: QMouseEvent containing click information including button,
                position, and keyboard modifiers.

        Behavior:
            - Left click in edit mode on control point: Start dragging
            - Left click in edit mode on line: Add new control point
            - Left click in normal mode: Navigate to target node
            - Right click: Show context menu
            - Shift+Left click on control point: Delete control point

        Note:
            This method handles the start of drag operations and sets up
            the necessary state for mouseMoveEvent and mouseReleaseEvent.
        """
        if event.button() == Qt.MouseButton.LeftButton:
            if self.edit_mode:
                # Check if clicking on a control point
                hit_result = self._test_control_point_hit(event.pos())
                if hit_result:
                    # Shift+click on control point = delete point
                    if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                        self._delete_control_point(hit_result[0], hit_result[1])
                        event.accept()
                        return
                    else:
                        # Regular click on control point = start dragging
                        self.dragging_control_point = True
                        self.dragged_branch_index = hit_result[0]
                        self.dragged_point_index = hit_result[1]
                        self.drag_start_pos = event.pos()

                        # UX Enhancement: Set visual feedback for drag start
                        self._is_being_dragged = True
                        # Only change cursor in edit mode
                        current_mode = self._get_current_mode()
                        if current_mode in ["edit", None]:
                            self.setCursor(QCursor(Qt.CursorShape.ClosedHandCursor))

                        event.accept()
                        return
                else:
                    # Click on line (not control point) = add new point
                    self._add_point(event.pos())
                    event.accept()
                    return

            # Not in edit mode, emit click signal for node navigation
            self._emit_click_signal()
            event.accept()
        elif event.button() == Qt.MouseButton.RightButton:
            # Handle right-click for context menu
            self._show_context_menu(event.pos())
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        """Handle mouse move events.

        Processes mouse movement over the line, updating control point positions
        during drag operations and providing visual feedback through cursor changes.

        Args:
            event: QMouseEvent containing the current mouse position and state.

        Behavior:
            - During control point drag: Updates point position with snapping
            - During hover: Updates cursor to indicate interactive areas
            - Triggers snap target updates and visual feedback

        Note:
            This method is called frequently during mouse movement and is
            optimized for performance. Expensive operations are deferred
            until mouseReleaseEvent.
        """
        if self.edit_mode:
            if self.dragging_control_point:
                # Update control point position
                self._update_control_point_position(event.pos())
                event.accept()
                return
            else:
                # Update cursor based on hover
                self._update_hover_cursor(event.pos())

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        """Handle mouse release events with deferred expensive operations.

        Completes drag operations by performing expensive calculations that were
        deferred during mouseMoveEvent for performance. This includes updating
        shared points, recalculating bounds, and emitting geometry change signals.

        Args:
            event: QMouseEvent containing release information including button
                and final position.

        Behavior:
            - Completes control point drag operations
            - Performs deferred expensive calculations
            - Updates shared points for branching lines
            - Emits geometry change signals
            - Clears performance mode and visual indicators

        Note:
            This method ensures that all expensive operations are performed
            only once at the end of a drag operation, maintaining smooth
            interaction during the drag itself.
        """
        if event.button() == Qt.MouseButton.LeftButton and self.dragging_control_point:
            self.dragging_control_point = False
            self._is_being_dragged = False
            self._snap_indicator_pos = None  # Clear snap indicator

            # UX Enhancement: Now perform expensive operations that were deferred
            if self._pending_updates:
                # Re-enable expensive operations
                self.geometry.set_performance_mode(False)

                # Update shared points if this is a branching line (expensive operation)
                if self.geometry.is_branching:
                    self.geometry._update_shared_points()

                # Final bounds update after drag completion
                logger.debug(f"Drag completed for {self.target_node}, updating bounds")
                self._update_bounds()
                self.update()

                # Emit geometry changed signal
                self._emit_geometry_changed()

                self._pending_updates = False

            # Reset cursor only if in default mode
            current_mode = self._get_current_mode()
            if current_mode in ["default", None]:
                self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))

            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def hoverMoveEvent(self, event) -> None:
        """Handle hover move events with enhanced visual feedback.

        Args:
            event: Hover event
        """
        if self.edit_mode and not self._is_being_dragged:
            self._update_hover_cursor(event.pos())

            # UX Enhancement: Show snap preview for branch creation
            self._update_snap_preview(event.pos())

        super().hoverMoveEvent(event)

    def hoverLeaveEvent(self, event) -> None:
        """Handle hover leave events to clear visual feedback.

        Args:
            event: Hover event
        """
        # Clear snap preview when cursor leaves the line
        if self._snap_preview is not None:
            self._snap_preview = None
            self.update()  # Trigger repaint to remove snap preview

        super().hoverLeaveEvent(event)

    def _test_control_point_hit(self, pos: QPointF) -> Optional[Tuple[int, int]]:
        """Test if position hits a control point.

        Args:
            pos: Position to test

        Returns:
            Tuple of (branch_index, point_index) if hit, None otherwise
        """
        radius = max(
            int(self.BASE_CONTROL_POINT_RADIUS * self._scale),
            self.MIN_CONTROL_POINT_RADIUS,
        )
        hit_distance = radius + 2  # Small tolerance

        for branch_idx, branch in enumerate(self.geometry.branches):
            for point_idx, point in enumerate(branch):
                point_pos = QPointF(point[0], point[1])
                distance = (pos - point_pos).manhattanLength()

                if distance <= hit_distance:
                    return (branch_idx, point_idx)

        return None

    def _update_control_point_position(self, pos: QPointF) -> None:
        """Update control point position during drag with optimized performance and snapping.

        Args:
            pos: New position
        """
        if (
            self.dragged_branch_index >= 0
            and self.dragged_point_index >= 0
            and self.dragged_branch_index < len(self.geometry.branches)
            and self.dragged_point_index
            < len(self.geometry.branches[self.dragged_branch_index])
        ):
            # Get the test position
            test_pos = (pos.x(), pos.y())

            # Check for snap targets
            snapped_pos = test_pos
            if self.snap_manager.enabled:
                # Update snap targets from all line features in the scene
                self._update_snap_targets()

                # Get snapped position
                snapped_pos = self.snap_manager.get_snapped_position(test_pos)

                # Update snap indicator position
                if snapped_pos != test_pos:
                    self._snap_indicator_pos = snapped_pos
                else:
                    self._snap_indicator_pos = None

            # Use the geometry's update_point method to properly handle shared points
            # Keep coordinates as floats for smooth dragging
            new_point = (snapped_pos[0], snapped_pos[1])
            self.geometry.update_point(
                self.dragged_branch_index, self.dragged_point_index, new_point
            )

            # UX Enhancement: Defer expensive operations during drag
            if not self._is_being_dragged:
                self._is_being_dragged = True
                # Enable performance mode to skip expensive shared point updates
                self.geometry.set_performance_mode(True)

            # Mark that we need updates but don't do them during drag
            self._pending_updates = True

            # Update bounds during drag for proper visual feedback
            self._update_bounds()

            # Minimal update for real-time feedback
            self.update()

    def _update_snap_targets(self) -> None:
        """Update snap targets from all line features in the scene."""
        scene = self.scene()
        if not scene:
            return

        # Clear existing targets
        self.snap_manager.clear_targets()

        # Add excluded point (the one being dragged)
        if self.dragging_control_point:
            self.snap_manager.add_excluded_point(
                self.dragged_branch_index, self.dragged_point_index
            )

        # Collect all line features from the scene
        line_features = []
        for item in scene.items():
            if isinstance(item, LineGraphicsItem):
                line_features.append(item)

        # Add all features as snap targets
        self.snap_manager.add_all_line_features(
            line_features,
            current_feature=self,
            current_branch_idx=self.dragged_branch_index,
            current_point_idx=self.dragged_point_index,
            scale=1.0,  # Graphics items use actual coordinates
        )

    def _update_hover_cursor(self, pos: QPointF) -> None:
        """Update cursor based on hover position with GIS-standard cursors.

        Args:
            pos: Mouse position
        """
        # Check current mode first
        current_mode = self._get_current_mode()

        # Only set item-specific cursors in default or edit modes
        if current_mode in ["default", "edit", None]:
            if self._test_control_point_hit(pos):
                # GIS standard: Open hand for draggable elements
                self.setCursor(QCursor(Qt.CursorShape.OpenHandCursor))
            else:
                # GIS standard: Pointing hand for clickable lines
                self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        # Otherwise, let the mode's cursor remain active

    def _get_current_mode(self) -> Optional[str]:
        """Get the current interaction mode from the adapter.

        Returns:
            Current mode string or None
        """
        scene = self.scene()
        if scene and hasattr(scene, "views"):
            views = scene.views()
            if views:
                view = views[0]
                if hasattr(view, "parent") and hasattr(
                    view.parent(), "graphics_adapter"
                ):
                    adapter = view.parent().graphics_adapter
                    return getattr(adapter, "current_mode", None)
        return None

    def set_scale(self, scale: float) -> None:
        """Set the display scale for the line.

        Updates the line's geometry scale and visual elements to match the
        new scale factor. This is typically called when the user zooms
        in or out of the map view.

        Args:
            scale: Scale factor to apply. Values > 1.0 make the line appear
                larger, values < 1.0 make it appear smaller. Must be positive.

        Note:
            This affects control point sizes, text labels, and geometry
            calculations. The line width itself is not scaled.
        """
        self._scale = scale
        self.geometry.set_scale(scale)
        self._update_text_style()
        self._update_bounds()
        self.update()

    def set_edit_mode(self, enabled: bool) -> None:
        """Enable or disable edit mode.

        When edit mode is enabled, the line displays interactive control points
        that can be dragged to modify the line's shape. When disabled, the line
        is read-only and only responds to click events for navigation.

        Args:
            enabled: True to enable edit mode (show control points and allow
                editing), False to disable edit mode (read-only).

        Note:
            Edit mode affects mouse interaction behavior, visual appearance,
            and available context menu options.
        """
        self.edit_mode = enabled
        self.update()  # Redraw to show/hide control points

    def update_geometry(self, points_or_branches: List) -> None:
        """Update the line geometry.

        Replaces the current line geometry with new data. This is typically
        called when the line is modified externally or loaded from the database.

        Args:
            points_or_branches: New geometry data. Can be either:
                - List of (x, y) tuples for a simple line
                - List of branches for a branching line, where each branch
                  is a list of (x, y) tuples

        Note:
            This method updates the bounds, repositions the text label, and
            triggers a visual update. It does not emit geometry change signals.
        """
        self.geometry = UnifiedLineGeometry(points_or_branches)
        self._update_bounds()

        # Update label position
        midpoint = self._get_line_midpoint()
        self.text_item.setPos(midpoint.x(), midpoint.y())

        self.update()

    def get_geometry_data(self) -> List:
        """Get the current geometry data.

        Returns the current line geometry in the same format as provided
        to the constructor. This is used for persistence and serialization.

        Returns:
            List: Current geometry data. Format depends on line type:
                - For simple lines: List of (x, y) tuples
                - For branching lines: List of branches, where each branch
                  is a list of (x, y) tuples

        Note:
            The returned data is a copy and can be safely modified without
            affecting the line's internal state.
        """
        if self.geometry.is_branching:
            return [branch.copy() for branch in self.geometry.branches]
        else:
            return self.geometry.branches[0].copy() if self.geometry.branches else []

    def _emit_click_signal(self) -> None:
        """Emit click signal through signal bridge."""
        # Find signal bridge through scene's feature manager
        scene = self.scene()
        if scene and hasattr(scene, "feature_items"):
            parent_widget = scene.parent()
            while parent_widget:
                if hasattr(parent_widget, "graphics_adapter"):
                    if hasattr(parent_widget.graphics_adapter, "signal_bridge"):
                        parent_widget.graphics_adapter.signal_bridge.line_clicked.emit(
                            self.target_node
                        )
                        break
                    elif hasattr(parent_widget.graphics_adapter, "feature_manager"):
                        if hasattr(
                            parent_widget.graphics_adapter.feature_manager,
                            "signal_bridge",
                        ):
                            parent_widget.graphics_adapter.feature_manager.signal_bridge.line_clicked.emit(
                                self.target_node
                            )
                            break
                parent_widget = getattr(parent_widget, "parent", lambda: None)()

        logger.debug(f"Line clicked: {self.target_node}")

    def _emit_geometry_changed(self) -> None:
        """Emit geometry changed signal."""
        geometry_data = self.get_geometry_data()

        # Get branch assignments if this is a branching line
        branch_assignments = {}
        if hasattr(self.geometry, "is_branching") and self.geometry.is_branching:
            # Convert to BranchingLineGeometry to get stable IDs
            from ui.components.map_component.line_geometry import BranchingLineGeometry

            branching_geometry = BranchingLineGeometry(geometry_data)
            branch_assignments = branching_geometry.get_flat_properties_for_storage()

        # Find signal bridge
        scene = self.scene()
        if scene and hasattr(scene, "feature_items"):
            parent_widget = scene.parent()
            while parent_widget:
                if hasattr(parent_widget, "graphics_adapter"):
                    if hasattr(parent_widget.graphics_adapter, "signal_bridge"):
                        parent_widget.graphics_adapter.signal_bridge.line_geometry_changed.emit(
                            self.target_node, geometry_data
                        )
                        break
                    elif hasattr(parent_widget.graphics_adapter, "feature_manager"):
                        if hasattr(
                            parent_widget.graphics_adapter.feature_manager,
                            "signal_bridge",
                        ):
                            parent_widget.graphics_adapter.feature_manager.signal_bridge.line_geometry_changed.emit(
                                self.target_node, geometry_data
                            )
                            break
                parent_widget = getattr(parent_widget, "parent", lambda: None)()

        # Also update line persistence with branch assignments
        if branch_assignments:
            try:
                from ui.components.map_component.line_persistence import (
                    LineGeometryPersistence,
                )

                persistence = LineGeometryPersistence(self.target_node)

                # Find the controller through the scene
                controller = None
                if scene:
                    parent_widget = scene.parent()
                    while parent_widget:
                        if hasattr(parent_widget, "controller"):
                            controller = parent_widget.controller
                            break
                        parent_widget = getattr(parent_widget, "parent", lambda: None)()

                if controller:
                    persistence.update_geometry(
                        geometry_data, controller, branch_assignments
                    )

            except Exception as e:
                logger.error(f"Error updating branch assignments: {e}")

        logger.debug(f"Line geometry changed: {self.target_node}")

    def _show_context_menu(self, pos) -> None:
        """Show enhanced context menu with GIS-standard operations.

        Args:
            pos: Position where right-click occurred
        """
        from PyQt6.QtGui import QAction, QIcon
        from PyQt6.QtWidgets import QMenu

        menu = QMenu()

        # GIS Enhancement: Add icons and keyboard shortcuts
        if self.geometry.is_branching:
            # MultiLineString - can create branches
            create_branch_action = QAction("🔀 Create Branch", menu)
            create_branch_action.setShortcut("B")
            create_branch_action.setStatusTip("Create a new branch from this point (B)")
            create_branch_action.triggered.connect(
                lambda: self._start_branch_creation(pos)
            )
            menu.addAction(create_branch_action)

            # Add branch management options
            menu.addSeparator()

            delete_branch_action = QAction("🗑️ Delete Branch", menu)
            delete_branch_action.setShortcut("Del")
            delete_branch_action.setStatusTip("Delete the selected branch")
            delete_branch_action.setEnabled(
                len(self.geometry.branches) > 1
            )  # Can't delete if only one branch
            delete_branch_action.triggered.connect(lambda: self._delete_branch(pos))
            menu.addAction(delete_branch_action)

        else:
            # LineString - offer conversion option
            convert_action = QAction("🔄 Convert to Branching Line", menu)
            convert_action.setStatusTip("Convert this simple line to support branching")
            convert_action.triggered.connect(lambda: self._convert_to_branching_line())
            menu.addAction(convert_action)

            menu.addSeparator()

            # Show create branch action but disabled with explanation
            create_branch_action = QAction("🔀 Create Branch (convert first)", menu)
            create_branch_action.setEnabled(False)
            create_branch_action.setStatusTip(
                "This simple line must be converted to support branching"
            )
            menu.addAction(create_branch_action)

        # Common operations
        menu.addSeparator()

        add_point_action = QAction("➕ Add Point", menu)
        add_point_action.setStatusTip("Add a control point at this position")
        add_point_action.triggered.connect(lambda: self._add_point(pos))
        menu.addAction(add_point_action)

        # Check if right-click is on a control point
        hit_result = self._test_control_point_hit(pos)
        if hit_result:
            branch_idx, point_idx = hit_result
            branch = (
                self.geometry.branches[branch_idx]
                if branch_idx < len(self.geometry.branches)
                else []
            )

            # Only show delete option if branch has more than 2 points
            if len(branch) > 2:
                delete_point_action = QAction("🗑️ Delete Point", menu)
                delete_point_action.setShortcut("Shift+Click")
                delete_point_action.setStatusTip(
                    "Delete this control point (Shift+Click)"
                )
                delete_point_action.triggered.connect(
                    lambda: self._delete_control_point(branch_idx, point_idx)
                )
                menu.addAction(delete_point_action)

        properties_action = QAction("⚙️ Properties", menu)
        properties_action.setStatusTip("Edit line properties and styling")
        menu.addAction(properties_action)

        # Convert item position to global position for menu
        global_pos = self.mapToScene(pos)
        scene = self.scene()
        if scene:
            views = scene.views()
            if views:
                view = views[0]
                view_pos = view.mapFromScene(global_pos)
                global_pos = view.mapToGlobal(view_pos)

                # Show menu
                menu.exec(global_pos)

    def _start_branch_creation(self, pos) -> None:
        """Start branch creation from the clicked position.

        Args:
            pos: Position where the branch should start
        """
        logger.info(f"Starting branch creation from context menu at {pos}")

        # Check if this line supports branching (Option A enforcement)
        if not self.geometry.is_branching:
            logger.warning(
                f"Cannot create branch on LineString geometry {self.target_node}"
            )
            return

        # Convert position to original coordinates
        scene_pos = self.mapToScene(pos)
        scene = self.scene()
        if scene and hasattr(scene, "scene_to_original_coords"):
            original_coords = scene.scene_to_original_coords(scene_pos)

            # Find the parent widget to set branch creation mode
            parent_widget = scene.parent()
            while parent_widget:
                if hasattr(parent_widget, "graphics_adapter"):
                    # Get the actual map tab
                    map_tab = parent_widget.graphics_adapter.map_tab

                    # Set branch creation mode
                    map_tab.mode_manager.branch_creation_mode = True
                    map_tab.mode_manager.set_branch_creation_target(self.target_node)
                    map_tab.mode_manager.set_branch_creation_start_point(
                        original_coords
                    )

                    # Update cursor
                    if hasattr(map_tab, "image_label"):
                        map_tab.image_label.set_cursor_for_mode("crosshair")

                    logger.info(
                        f"Branch creation mode activated for {self.target_node} at {original_coords}"
                    )
                    break
                parent_widget = getattr(parent_widget, "parent", lambda: None)()

    def _convert_to_branching_line(self) -> None:
        """Convert this LineString to MultiLineString geometry to support branching.

        This method converts the current simple line to a branching line format
        in both the visual representation and the database.
        """
        logger.info(f"Converting {self.target_node} from LineString to MultiLineString")

        if self.geometry.is_branching:
            logger.warning(f"Line {self.target_node} is already a branching line")
            return

        # Get current geometry
        current_points = self.get_geometry_data()
        if not current_points or len(current_points) < 2:
            logger.error(f"Cannot convert line {self.target_node}: insufficient points")
            return

        # Convert to branching format (list of branches)
        branching_geometry = [current_points]

        # Update the visual geometry
        self.update_geometry(branching_geometry)

        # Mark as branching
        self.geometry.is_branching = True
        self.geometry._update_shared_points()
        self.geometry._update_scaled_branches()

        # Update the visual
        self._update_bounds()
        self.update()

        # Emit geometry changed signal to update database
        self._emit_geometry_changed()

        logger.info(f"Successfully converted {self.target_node} to branching line")

    def _update_snap_preview(self, pos: QPointF) -> None:
        """Update snap preview for potential branch creation points.

        Args:
            pos: Mouse position
        """
        # GIS Enhancement: Show potential snap points during hover
        if not self.edit_mode:
            return

        # Find nearest line segment for snapping
        min_distance = float("inf")
        snap_point = None

        for branch in self.geometry.branches:
            if len(branch) < 2:
                continue

            for i in range(len(branch) - 1):
                p1 = QPointF(branch[i][0], branch[i][1])
                p2 = QPointF(branch[i + 1][0], branch[i + 1][1])

                # Calculate closest point on line segment
                line_vec = p2 - p1
                point_vec = pos - p1

                if line_vec.manhattanLength() == 0:
                    continue

                # Project point onto line (manual dot product for compatibility)
                dot_pv_lv = point_vec.x() * line_vec.x() + point_vec.y() * line_vec.y()
                dot_lv_lv = line_vec.x() * line_vec.x() + line_vec.y() * line_vec.y()

                if dot_lv_lv == 0:
                    continue

                t = max(0, min(1, dot_pv_lv / dot_lv_lv))
                closest_point = p1 + t * line_vec

                distance = (pos - closest_point).manhattanLength()

                # GIS standard: 10 pixel snap tolerance
                if distance < 10 and distance < min_distance:
                    min_distance = distance
                    snap_point = closest_point

        # Update snap preview if we found a good snap point
        if snap_point != self._snap_preview:
            self._snap_preview = snap_point
            self.update()  # Trigger repaint to show/hide snap preview

    def set_highlighted(self, highlighted: bool) -> None:
        """Set highlight state for this line (GIS standard selection feedback).

        Args:
            highlighted: Whether the line should be highlighted
        """
        if self._is_highlighted != highlighted:
            self._is_highlighted = highlighted
            self.update()

    def set_preview_branch(self, start_point: QPointF, end_point: QPointF) -> None:
        """Set preview branch for branch creation mode.

        Args:
            start_point: Branch start coordinates
            end_point: Branch end coordinates
        """
        self._preview_branch = (start_point, end_point)
        self.update()

    def _delete_branch(self, pos) -> None:
        """Delete a branch from the branching line.

        Args:
            pos: Position where the delete was requested
        """
        logger.info(f"Deleting branch from context menu at {pos}")

        if not self.geometry.is_branching:
            logger.warning(
                f"Cannot delete branch from non-branching line {self.target_node}"
            )
            return

        # Find which branch is closest to the click position
        scene_pos = self.mapToScene(pos)
        branch_to_delete = self._find_nearest_branch(scene_pos)

        if branch_to_delete is None:
            logger.warning("Could not determine which branch to delete")
            return

        # Don't allow deleting the main branch (index 0)
        if branch_to_delete == 0:
            logger.warning("Cannot delete the main branch")
            return

        # Attempt to delete the branch
        if self.geometry.delete_branch(branch_to_delete):
            logger.info(
                f"Successfully deleted branch {branch_to_delete} from {self.target_node}"
            )

            # Update visual representation
            self._update_bounds()
            self.update()

            # Emit geometry changed signal to update database
            self._emit_geometry_changed()
        else:
            logger.warning(f"Failed to delete branch {branch_to_delete}")

    def _add_point(self, pos) -> None:
        """Add a point to the line at the clicked position.

        Args:
            pos: Position where the point should be added
        """
        logger.info(f"Adding point from context menu at {pos}")

        # Convert position to scene coordinates, then to original coordinates
        scene_pos = self.mapToScene(pos)
        scene = self.scene()
        if not scene or not hasattr(scene, "scene_to_original_coords"):
            logger.error("Cannot convert coordinates for point insertion")
            return

        original_coords = scene.scene_to_original_coords(scene_pos)
        new_point = (int(original_coords[0]), int(original_coords[1]))

        # Find the best insertion point
        insertion_info = self._find_insertion_point(scene_pos)

        if insertion_info is None:
            logger.warning("Could not determine where to insert the point")
            return

        branch_idx, insert_idx = insertion_info

        # Insert the point
        self.geometry.insert_point(branch_idx, insert_idx, new_point)

        logger.info(
            f"Successfully added point {new_point} to branch {branch_idx} at index {insert_idx}"
        )

        # Update visual representation
        self._update_bounds()
        self.update()

        # Emit geometry changed signal to update database
        self._emit_geometry_changed()

    def _find_nearest_branch(self, scene_pos: QPointF) -> Optional[int]:
        """Find the branch closest to the given scene position.

        Args:
            scene_pos: Position in scene coordinates

        Returns:
            Index of the nearest branch, or None if not found
        """
        min_distance = float("inf")
        nearest_branch = None

        for branch_idx, branch in enumerate(self.geometry.scaled_branches):
            if len(branch) < 2:
                continue

            # Calculate distance to each segment in this branch
            for i in range(len(branch) - 1):
                p1 = QPointF(branch[i][0], branch[i][1])
                p2 = QPointF(branch[i + 1][0], branch[i + 1][1])

                # Find closest point on line segment
                line_vec = p2 - p1
                point_vec = scene_pos - p1

                if line_vec.manhattanLength() == 0:
                    continue

                # Manual dot product calculation for compatibility
                dot_pv_lv = point_vec.x() * line_vec.x() + point_vec.y() * line_vec.y()
                dot_lv_lv = line_vec.x() * line_vec.x() + line_vec.y() * line_vec.y()

                if dot_lv_lv == 0:
                    continue

                t = max(0, min(1, dot_pv_lv / dot_lv_lv))
                closest_point = p1 + t * line_vec

                distance = (scene_pos - closest_point).manhattanLength()

                if distance < min_distance:
                    min_distance = distance
                    nearest_branch = branch_idx

        # Only return a branch if it's reasonably close (within 20 pixels)
        return nearest_branch if min_distance < 20 else None

    def _find_insertion_point(self, scene_pos: QPointF) -> Optional[Tuple[int, int]]:
        """Find the best location to insert a new point.

        Args:
            scene_pos: Position in scene coordinates where point should be added

        Returns:
            Tuple of (branch_idx, insert_idx) or None if not found
        """
        min_distance = float("inf")
        best_insertion = None

        for branch_idx, branch in enumerate(self.geometry.scaled_branches):
            if len(branch) < 2:
                continue

            # Check each line segment in this branch
            for i in range(len(branch) - 1):
                p1 = QPointF(branch[i][0], branch[i][1])
                p2 = QPointF(branch[i + 1][0], branch[i + 1][1])

                # Find closest point on line segment
                line_vec = p2 - p1
                point_vec = scene_pos - p1

                if line_vec.manhattanLength() == 0:
                    continue

                # Manual dot product calculation for compatibility
                dot_pv_lv = point_vec.x() * line_vec.x() + point_vec.y() * line_vec.y()
                dot_lv_lv = line_vec.x() * line_vec.x() + line_vec.y() * line_vec.y()

                if dot_lv_lv == 0:
                    continue

                t = max(0, min(1, dot_pv_lv / dot_lv_lv))
                closest_point = p1 + t * line_vec

                distance = (scene_pos - closest_point).manhattanLength()

                if distance < min_distance:
                    min_distance = distance
                    # Insert after the first point of this segment
                    best_insertion = (branch_idx, i + 1)

        # Only return insertion point if it's reasonably close (within 20 pixels)
        return best_insertion if min_distance < 20 else None

    def _delete_control_point(self, branch_idx: int, point_idx: int) -> None:
        """Delete a control point from the line.

        Args:
            branch_idx: Index of the branch containing the point
            point_idx: Index of the point within the branch
        """
        logger.info(f"Deleting control point at branch {branch_idx}, point {point_idx}")

        # Safety checks
        if branch_idx >= len(self.geometry.branches):
            logger.warning(f"Invalid branch index {branch_idx}")
            return

        branch = self.geometry.branches[branch_idx]
        if point_idx >= len(branch):
            logger.warning(f"Invalid point index {point_idx}")
            return

        # Don't allow deletion if it would make the branch too short
        if len(branch) <= 2:
            logger.warning(
                "Cannot delete point - would make branch too short (need at least 2 points)"
            )
            return

        # For branching lines, check if this is a shared point
        if self.geometry.is_branching:
            point = branch[point_idx]
            point_key = (round(point[0]), round(point[1]))

            # If it's a shared point, warn user but allow deletion
            if point_key in self.geometry._shared_points:
                locations = self.geometry._shared_points[point_key]
                if len(locations) > 1:
                    logger.info(
                        f"Deleting shared point used by {len(locations)} branches"
                    )

        # Attempt to delete the point
        if self.geometry.delete_point(branch_idx, point_idx):
            logger.info(f"Successfully deleted point from branch {branch_idx}")

            # Update visual representation
            self._update_bounds()
            self.update()

            # Emit geometry changed signal to update database
            self._emit_geometry_changed()
        else:
            logger.warning(f"Failed to delete point from branch {branch_idx}")
