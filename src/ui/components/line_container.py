from typing import List, Tuple
from PyQt6.QtCore import Qt, pyqtSignal, QPoint
from PyQt6.QtGui import QPainter, QPen, QColor, QPainterPath, QCursor
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from structlog import get_logger

logger = get_logger(__name__)


class LineContainer(QWidget):
    """Container widget that handles line visualization.

    This widget renders a line feature on the map with proper scaling and interaction.
    """

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
        self.line_color = QColor("#FF0000")  # Default color
        self.line_width = 2  # Default width
        self.line_pattern = Qt.PenStyle.SolidLine  # Default pattern

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
        """Update widget geometry based on line points."""
        if not self.scaled_points:
            return

        # Calculate bounds
        min_x = min(p[0] for p in self.scaled_points)
        min_y = min(p[1] for p in self.scaled_points)
        max_x = max(p[0] for p in self.scaled_points)
        max_y = max(p[1] for p in self.scaled_points)

        # Add margin
        margin = max(int(5 * self._scale), 3)
        self.setGeometry(
            min_x - margin,
            min_y - margin,
            max_x - min_x + (2 * margin),
            max_y - min_y + (2 * margin),
        )

        # Position label in the middle of the line
        mid_x = (min_x + max_x) // 2
        mid_y = (min_y + max_y) // 2

        # Calculate relative position within the widget
        rel_x = mid_x - min_x + margin
        rel_y = mid_y - min_y + margin

        # Position the label
        self.text_label.move(
            rel_x - self.text_label.width() // 2, rel_y - self.text_label.height() // 2
        )

    def update_label_style(self) -> None:
        """Update label style based on current scale."""
        # Match the pin label style
        font_size = max(int(8 * self._scale), 6)  # Minimum font size of 6pt
        self.text_label.setStyleSheet(
            f"""
            QLabel {{
                background-color: rgba(0, 0, 0, 0);
                color: white;
                padding: {max(int(2 * self._scale), 1)}px {max(int(4 * self._scale), 2)}px;
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

    def mousePressEvent(self, event):
        """Handle mouse press events for line selection.

        Args:
            event: Mouse event object.
        """
        if event.button() == Qt.MouseButton.LeftButton:
            # Debug output to verify signal emission
            print(f"Line clicked: {self.target_node}")
            self.line_clicked.emit(self.target_node)
            event.accept()
