from typing import List, Tuple, Optional
from PyQt6.QtCore import QObject, pyqtSignal, QPoint
from PyQt6.QtGui import QPainter, QPen, QColor
from PyQt6.QtCore import Qt
from structlog import get_logger

logger = get_logger(__name__)


class DrawingManager(QObject):
    """Manages drawing operations (line drawing, temporary visualizations).

    Handles temporary drawing state and visual feedback during drawing operations.
    """

    # Drawing signals
    line_completed = pyqtSignal(list)  # Emits list of points when line is complete
    drawing_updated = pyqtSignal()  # Signals that drawing state changed
    branching_line_completed = pyqtSignal(list)  # Emits list of branches when complete

    def __init__(self):
        """Initialize the drawing manager."""
        super().__init__()

        # Drawing state
        self.is_drawing_line = False
        self.current_line_points = []  # Original coordinates
        self.temp_line_coordinates = []  # Scaled coordinates for display

        # Branching line state
        self.is_drawing_branching_line = False
        self.current_branches = []  # List of branches, each branch is a list of points
        self.temp_branch_coordinates = []  # List of scaled coordinate lists for display
        self.current_branch_index = 0  # Which branch we're currently drawing

        # Drawing style
        self.temp_line_color = QColor("#3388FF")
        self.temp_line_width = 2
        self.temp_line_style = Qt.PenStyle.DashLine

    def start_line_drawing(self) -> None:
        """Start line drawing mode."""
        self.is_drawing_line = True
        self.current_line_points = []
        self.temp_line_coordinates = []
        self.drawing_updated.emit()
        logger.debug("Started line drawing mode")

    def stop_line_drawing(self, complete: bool = False) -> None:
        """Stop line drawing mode.

        Args:
            complete: Whether to complete the line (emit signal) or just cancel
        """
        if self.is_drawing_line and complete and len(self.current_line_points) >= 2:
            # Complete the line
            points = self.current_line_points.copy()
            logger.debug(f"Completing line with {len(points)} points")
            self.line_completed.emit(points)

        # Reset drawing state
        self.is_drawing_line = False
        self.current_line_points = []
        self.temp_line_coordinates = []
        self.drawing_updated.emit()

        if complete:
            logger.debug("Line drawing completed")
        else:
            logger.debug("Line drawing cancelled")

    def start_branching_line_drawing(self) -> None:
        """Start branching line drawing mode."""
        self.is_drawing_branching_line = True
        self.current_branches = [[]]  # Start with first empty branch
        self.temp_branch_coordinates = [[]]
        self.current_branch_index = 0
        self.drawing_updated.emit()
        logger.debug("Started branching line drawing mode")

    def stop_branching_line_drawing(self, complete: bool = False) -> None:
        """Stop branching line drawing mode.

        Args:
            complete: Whether to complete the branching line (emit signal) or just cancel
        """
        if (
            self.is_drawing_branching_line
            and complete
            and self._can_complete_branching_line()
        ):
            # Complete the branching line
            branches = [
                branch.copy() for branch in self.current_branches if len(branch) >= 2
            ]
            logger.debug(f"Completing branching line with {len(branches)} branches")
            self.branching_line_completed.emit(branches)

        # Reset branching state
        self.is_drawing_branching_line = False
        self.current_branches = []
        self.temp_branch_coordinates = []
        self.current_branch_index = 0
        self.drawing_updated.emit()

        if complete:
            logger.debug("Branching line drawing completed")
        else:
            logger.debug("Branching line drawing cancelled")

    def _can_complete_branching_line(self) -> bool:
        """Check if branching line can be completed."""
        # Need at least one branch with at least 2 points
        return any(len(branch) >= 2 for branch in self.current_branches)

    def draw_temporary_branching_line(self, painter: QPainter) -> None:
        """Draw the temporary branching line being constructed.

        Args:
            painter: QPainter instance to draw with
        """
        if not self.is_drawing_branching_line:
            return

        # Set up pen for temporary line
        pen = QPen(self.temp_line_color)
        pen.setWidth(self.temp_line_width)
        pen.setStyle(self.temp_line_style)
        painter.setPen(pen)

        # Draw each branch
        for branch_coords in self.temp_branch_coordinates:
            if len(branch_coords) < 2:
                continue

            # Draw line segments
            for i in range(len(branch_coords) - 1):
                p1 = branch_coords[i]
                p2 = branch_coords[i + 1]
                painter.drawLine(int(p1[0]), int(p1[1]), int(p2[0]), int(p2[1]))

    def add_point(
        self, original_x: int, original_y: int, scaled_x: float, scaled_y: float
    ) -> bool:
        """Add a point to the current line being drawn.

        Args:
            original_x: X coordinate in original image space
            original_y: Y coordinate in original image space
            scaled_x: X coordinate in scaled display space
            scaled_y: Y coordinate in scaled display space

        Returns:
            True if point was added, False if not in drawing mode
        """
        if not self.is_drawing_line:
            return False

        self.current_line_points.append((original_x, original_y))
        self.temp_line_coordinates.append((scaled_x, scaled_y))

        logger.debug(
            f"Added point to line: ({original_x}, {original_y}) - "
            f"Total points: {len(self.current_line_points)}"
        )

        self.drawing_updated.emit()
        return True

    def add_branching_point(
        self, original_x: int, original_y: int, scaled_x: float, scaled_y: float
    ) -> bool:
        """Add a point to the current branch being drawn.

        Args:
            original_x: X coordinate in original image space
            original_y: Y coordinate in original image space
            scaled_x: X coordinate in scaled display space
            scaled_y: Y coordinate in scaled display space

        Returns:
            True if point was added, False if not in drawing mode
        """
        if not self.is_drawing_branching_line:
            return False

        # Add point to the current branch
        self.current_branches[self.current_branch_index].append(
            (original_x, original_y)
        )
        self.temp_branch_coordinates[self.current_branch_index].append(
            (scaled_x, scaled_y)
        )

        logger.debug(
            f"Added point to branch {self.current_branch_index}: ({original_x}, {original_y}) - Total points: {len(self.current_branches[self.current_branch_index])}"
        )

        self.drawing_updated.emit()
        return True

    def can_complete_line(self) -> bool:
        """Check if the current line can be completed.

        Returns:
            True if line has at least 2 points
        """
        return len(self.current_line_points) >= 2

    def get_point_count(self) -> int:
        """Get number of points in current line.

        Returns:
            Number of points in current drawing
        """
        return len(self.current_line_points)

    def draw_temporary_line(self, painter: QPainter) -> None:
        """Draw the temporary line being constructed.

        Args:
            painter: QPainter instance to draw with
        """
        if not self.is_drawing_line or len(self.temp_line_coordinates) < 2:
            return

        # Set up pen for temporary line
        pen = QPen(self.temp_line_color)
        pen.setWidth(self.temp_line_width)
        pen.setStyle(self.temp_line_style)
        painter.setPen(pen)

        # Draw line segments
        for i in range(len(self.temp_line_coordinates) - 1):
            p1 = self.temp_line_coordinates[i]
            p2 = self.temp_line_coordinates[i + 1]
            painter.drawLine(int(p1[0]), int(p1[1]), int(p2[0]), int(p2[1]))

    def handle_key_press(self, key: int) -> bool:
        """Handle key press events for drawing operations.

        Args:
            key: Qt key code

        Returns:
            True if key was handled, False otherwise
        """
        if key == Qt.Key.Key_Escape and self.is_drawing_line:
            self.stop_line_drawing(complete=False)
            return True
        elif key == Qt.Key.Key_Return and self.can_complete_line():
            self.stop_line_drawing(complete=True)
            return True

        return False

    def update_scale(self, scale: float) -> None:
        """Update temp coordinates when scale changes.

        Args:
            scale: New scale factor
        """
        if self.is_drawing_line:
            # Recalculate temp coordinates from original points
            self.temp_line_coordinates = [
                (point[0] * scale, point[1] * scale)
                for point in self.current_line_points
            ]
            self.drawing_updated.emit()

        if self.is_drawing_branching_line:
            # Recalculate temp coordinates for each branch
            for i, branch in enumerate(self.current_branches):
                self.temp_branch_coordinates[i] = [
                    (point[0] * scale, point[1] * scale) for point in branch
                ]
            self.drawing_updated.emit()

    def set_drawing_style(
        self,
        color: Optional[str] = None,
        width: Optional[int] = None,
        style: Optional[Qt.PenStyle] = None,
    ) -> None:
        """Set the style for temporary drawing.

        Args:
            color: Hex color string
            width: Line width
            style: Qt pen style
        """
        if color:
            self.temp_line_color = QColor(color)
        if width is not None:
            self.temp_line_width = width
        if style is not None:
            self.temp_line_style = style

        if self.is_drawing_line:
            self.drawing_updated.emit()
