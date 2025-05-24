from typing import List, Tuple, Optional
from PyQt6.QtCore import QObject, pyqtSignal, QPoint, QPointF
from PyQt6.QtGui import QPainter, QPen, QColor, QBrush
from PyQt6.QtCore import Qt
from structlog import get_logger

logger = get_logger(__name__)


class DrawingManager(QObject):
    """Manages drawing_decap operations (line drawing_decap, temporary visualizations).

    Handles temporary drawing_decap state and visual feedback during drawing_decap operations.
    """

    # Drawing signals
    line_completed = pyqtSignal(list)  # Emits list of points when line is complete
    drawing_updated = pyqtSignal()  # Signals that drawing_decap state changed
    branching_line_completed = pyqtSignal(list)  # Emits list of branches when complete

    def __init__(self):
        """Initialize the drawing_decap manager."""
        super().__init__()

        # Drawing state
        self.is_drawing_line = False
        self.current_line_points = []  # Original coordinates
        self.temp_line_coordinates = []  # Scaled coordinates for display

        # Branching line state
        self.is_drawing_branching_line = False
        self.current_branches = []  # List of branches, each branch is a list of points
        self.temp_branch_coordinates = []  # List of scaled coordinate lists for display
        self.current_branch_index = 0  # Which branch we're currently drawing_decap

        # Track last mouse position for branch creation
        self.last_mouse_position = (0, 0)  # Original coordinates
        self.last_mouse_position_scaled = (0, 0)  # Scaled coordinates

        # Drawing style
        self.temp_line_color = QColor("#3388FF")
        self.temp_line_width = 2
        self.temp_line_style = Qt.PenStyle.DashLine

    def start_line_drawing(self) -> None:
        """Start line drawing_decap mode."""
        self.is_drawing_line = True
        self.current_line_points = []
        self.temp_line_coordinates = []
        self.drawing_updated.emit()
        logger.debug("Started line drawing_decap mode")

    def stop_line_drawing(self, complete: bool = False) -> None:
        """Stop line drawing_decap mode.

        Args:
            complete: Whether to complete the line (emit signal) or just cancel
        """
        if self.is_drawing_line and complete and len(self.current_line_points) >= 2:
            # Complete the line
            points = self.current_line_points.copy()
            logger.debug(f"Completing line with {len(points)} points")
            self.line_completed.emit(points)

        # Reset drawing_decap state
        self.is_drawing_line = False
        self.current_line_points = []
        self.temp_line_coordinates = []
        self.drawing_updated.emit()

        if complete:
            logger.debug("Line drawing_decap completed")
        else:
            logger.debug("Line drawing_decap cancelled")

    def start_branching_line_drawing(self) -> None:
        """Start branching line drawing_decap mode."""
        self.is_drawing_branching_line = True
        self.current_branches = [[]]  # Start with first empty branch
        self.temp_branch_coordinates = [[]]
        self.current_branch_index = 0
        self.drawing_updated.emit()
        logger.debug("Started branching line drawing_decap mode")

    def start_branch_from_nearest_point(self) -> bool:
        """Start a new branch from the point closest to the current mouse position.

        Returns:
            True if a new branch was started, False if not in branching line mode
        """
        if not self.is_drawing_branching_line:
            logger.debug("Not in branching line mode")
            return False

        # Use the last known mouse position
        mouse_x, mouse_y = self.last_mouse_position

        logger.debug(f"Starting branch from mouse position at ({mouse_x}, {mouse_y})")

        # We'll find the point closest to the mouse position
        nearest_point = None
        nearest_branch_idx = -1
        nearest_point_idx = -1
        min_distance = float("inf")

        # Go through all branches and points
        for branch_idx, branch in enumerate(self.current_branches):
            for point_idx, point in enumerate(branch):
                # Calculate distance to the mouse position
                dx = point[0] - mouse_x
                dy = point[1] - mouse_y
                distance = dx * dx + dy * dy

                logger.debug(
                    f"Point in branch {branch_idx}, idx {point_idx}: {point}, distance: {distance}"
                )

                # Update if this is closer than our previous best
                if distance < min_distance:
                    min_distance = distance
                    nearest_point = point
                    nearest_branch_idx = branch_idx
                    nearest_point_idx = point_idx

        # If we found a nearby point
        if nearest_point:
            logger.debug(
                f"Found nearest point to mouse: {nearest_point} in branch {nearest_branch_idx}, point {nearest_point_idx}"
            )

            # Calculate current scale
            current_scale = 1.0
            if (
                self.temp_branch_coordinates
                and nearest_branch_idx < len(self.temp_branch_coordinates)
                and self.temp_branch_coordinates[nearest_branch_idx]
                and nearest_point_idx
                < len(self.temp_branch_coordinates[nearest_branch_idx])
            ):
                # Get the scaled version of the selected point
                temp_point = self.temp_branch_coordinates[nearest_branch_idx][
                    nearest_point_idx
                ]
                if nearest_point[0] != 0:
                    current_scale = temp_point[0] / nearest_point[0]
                elif nearest_point[1] != 0:
                    current_scale = temp_point[1] / nearest_point[1]

                logger.debug(f"Using scale: {current_scale}")

            # Create new branch starting from the nearest point
            new_branch = [nearest_point]
            self.current_branches.append(new_branch)

            # Create corresponding scaled coordinates
            new_temp_branch = [
                (nearest_point[0] * current_scale, nearest_point[1] * current_scale)
            ]
            self.temp_branch_coordinates.append(new_temp_branch)

            # Update current branch index to the newly created branch
            self.current_branch_index = len(self.current_branches) - 1

            logger.debug(
                f"Started new branch {self.current_branch_index} from point in branch {nearest_branch_idx}, point {nearest_point_idx}"
            )
            self.drawing_updated.emit()
            return True

        logger.debug("No suitable point found to branch from")
        return False

    def stop_branching_line_drawing(self, complete: bool = False) -> None:
        """Stop branching line drawing_decap mode.

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
            logger.debug("Branching line drawing_decap completed")
        else:
            logger.debug("Branching line drawing_decap cancelled")

    def _can_complete_branching_line(self) -> bool:
        """Check if branching line can be completed."""
        # Need at least one branch with at least 2 points
        return any(len(branch) >= 2 for branch in self.current_branches)

    def draw_temporary_branching_line(self, painter: QPainter) -> None:
        """Draw the temporary branching line being constructed with visual feedback.

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

        # Draw each branch with different styles to help with debugging
        for branch_idx, branch_coords in enumerate(self.temp_branch_coordinates):
            if len(branch_coords) < 2:
                # Just draw a point if only one point exists
                if len(branch_coords) == 1:
                    painter.setBrush(
                        QBrush(
                            QColor(
                                "#FF0000"
                                if branch_idx == self.current_branch_index
                                else "#0000FF"
                            )
                        )
                    )
                    painter.drawEllipse(
                        QPointF(branch_coords[0][0], branch_coords[0][1]), 5, 5
                    )
                continue

            # Use different colors for branches to distinguish them visually
            if branch_idx == self.current_branch_index:
                # Current branch is bright red
                painter.setPen(
                    QPen(
                        QColor("#FF0000"),
                        self.temp_line_width + 1,
                        self.temp_line_style,
                    )
                )
            else:
                # Other branches are blue
                painter.setPen(
                    QPen(QColor("#0000FF"), self.temp_line_width, self.temp_line_style)
                )

            # Draw line segments
            for i in range(len(branch_coords) - 1):
                p1 = branch_coords[i]
                p2 = branch_coords[i + 1]
                painter.drawLine(int(p1[0]), int(p1[1]), int(p2[0]), int(p2[1]))

                # Draw dots at each point with index numbers for debugging
                painter.setBrush(QBrush(QColor("#FFFF00")))  # Yellow points
                painter.drawEllipse(QPointF(p1[0], p1[1]), 3, 3)

                # For the last point in each segment
                if i == len(branch_coords) - 2:
                    painter.drawEllipse(QPointF(p2[0], p2[1]), 3, 3)

                    # Mark the last point of the current branch with a larger circle
                    if branch_idx == self.current_branch_index:
                        painter.setBrush(
                            QBrush(QColor("#FF0000"))
                        )  # Red for current branch endpoint
                        painter.drawEllipse(QPointF(p2[0], p2[1]), 6, 6)

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
            True if point was added, False if not in drawing_decap mode
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
            True if point was added, False if not in drawing_decap mode
        """
        if not self.is_drawing_branching_line:
            return False

        # Track last mouse position
        self.last_mouse_position = (original_x, original_y)
        self.last_mouse_position_scaled = (scaled_x, scaled_y)

        # Add point to the current branch
        self.current_branches[self.current_branch_index].append(
            (original_x, original_y)
        )
        self.temp_branch_coordinates[self.current_branch_index].append(
            (scaled_x, scaled_y)
        )

        logger.debug(
            f"Added point to branch {self.current_branch_index}: ({original_x}, {original_y}) - "
            f"Total points: {len(self.current_branches[self.current_branch_index])}"
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
            Number of points in current drawing_decap
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
        """Handle key press events for drawing_decap operations.

        Args:
            key: Qt key code

        Returns:
            True if key was handled, False otherwise
        """
        if key == Qt.Key.Key_Escape:
            if self.is_drawing_line:
                self.stop_line_drawing(complete=False)
                return True
            elif self.is_drawing_branching_line:
                self.stop_branching_line_drawing(complete=False)
                return True
        elif key == Qt.Key.Key_Return:
            if self.is_drawing_line and self.can_complete_line():
                self.stop_line_drawing(complete=True)
                return True
            elif self.is_drawing_branching_line and self._can_complete_branching_line():
                self.stop_branching_line_drawing(complete=True)
                return True

        # Removed B key handling since it's now handled in MapTab

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
        """Set the style for temporary drawing_decap.

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

    def start_branch_from_position(
        self, original_x: int, original_y: int, scaled_x: float, scaled_y: float
    ) -> bool:
        """Start a new branch from the point closest to the given position.

        Args:
            original_x: X coordinate in original image space
            original_y: Y coordinate in original image space
            scaled_x: X coordinate in scaled display space
            scaled_y: Y coordinate in scaled display space

        Returns:
            True if a branch was started, False otherwise
        """
        if not self.is_drawing_branching_line:
            logger.debug("Not in branching line mode")
            return False

        logger.debug(
            f"Attempting to start branch from position: ({original_x}, {original_y})"
        )

        # Find the nearest point in all branches
        nearest_point = None
        nearest_branch_idx = -1
        nearest_point_idx = -1
        min_distance = float("inf")

        # Go through all branches and points
        for branch_idx, branch in enumerate(self.current_branches):
            for point_idx, point in enumerate(branch):
                # Calculate distance to the mouse position
                dx = point[0] - original_x
                dy = point[1] - original_y
                distance = dx * dx + dy * dy

                logger.debug(f"Checking point: {point}, distance: {distance}")

                # Update if this is closer than our previous best
                if distance < min_distance:
                    min_distance = distance
                    nearest_point = point
                    nearest_branch_idx = branch_idx
                    nearest_point_idx = point_idx

        # If we found a nearby point
        if nearest_point:
            logger.debug(
                f"Found nearest point: {nearest_point} in branch {nearest_branch_idx}, point {nearest_point_idx}"
            )

            # Get current scale from temp coordinates
            if (
                self.temp_branch_coordinates
                and nearest_branch_idx < len(self.temp_branch_coordinates)
                and self.temp_branch_coordinates[nearest_branch_idx]
                and nearest_point_idx
                < len(self.temp_branch_coordinates[nearest_branch_idx])
            ):

                # Get scaled version of nearest point
                temp_point = self.temp_branch_coordinates[nearest_branch_idx][
                    nearest_point_idx
                ]

                # Create new branch starting from nearest point
                new_branch = [nearest_point]
                self.current_branches.append(new_branch)

                # Create corresponding scaled coordinates
                new_temp_branch = [temp_point]  # Use existing scaled point directly
                self.temp_branch_coordinates.append(new_temp_branch)

                # Update current branch index to the newly created branch
                self.current_branch_index = len(self.current_branches) - 1

                logger.debug(
                    f"Started new branch {self.current_branch_index} from point in branch {nearest_branch_idx}, point {nearest_point_idx}"
                )
                self.drawing_updated.emit()
                return True

        logger.debug("No suitable point found to branch from")
        return False
