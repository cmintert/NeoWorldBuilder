import os
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QMouseEvent, QCursor
from PyQt6.QtSvgWidgets import QSvgWidget
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from utils.path_helper import get_resource_path


class PinContainer(QWidget):
    """Container widget that holds both a pin and its label.

    Attributes:
        pin_clicked (pyqtSignal): Signal emitted when the pin is clicked.
        _scale (float): Current scale factor for the pin.
        text_label (QLabel): Label showing the node name.
        pin_svg (QSvgWidget): The pin icon.
    """

    pin_clicked = pyqtSignal(str)

    def __init__(self, target_node: str, parent=None, config=None):
        """Initialize the pin container.

        Args:
            target_node: The node name this pin represents.
            parent: Parent widget.
            config: Configuration object with settings.
        """
        super().__init__(parent)
        self._scale = 1.0  # Initialize scale attribute
        self.config = config

        # Make mouse interactive
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.setMouseTracking(True)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        # Create layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        # Create SVG pin with error handling
        svg_path = get_resource_path(self.config.map.PIN_SVG_SOURCE)

        try:
            if not os.path.exists(svg_path):
                print(f"SVG file not found: {svg_path}")
                raise FileNotFoundError(f"SVG file not found: {svg_path}")

            self.pin_svg = QSvgWidget(self)
            self.pin_svg.load(svg_path)

            # Verify the widget has valid dimensions after loading
            if self.pin_svg.width() == 0 or self.pin_svg.height() == 0:
                print(f"Failed to load SVG properly: {svg_path}")
                raise RuntimeError(f"Failed to load SVG properly: {svg_path}")

            self.update_pin_size()

        except Exception as e:
            print(f"Error loading SVG, falling back to emoji: {e}")
            # Fallback to emoji if SVG fails
            self.pin_svg = QLabel("📍", self)
            self.pin_svg.setFixedSize(
                QSize(self.config.map.BASE_PIN_WIDTH, self.config.map.BASE_PIN_HEIGHT)
            )  # Set initial size for emoji

        # Create text label
        self.text_label = QLabel(target_node)
        self.update_label_style()

        # Add widgets to layout
        layout.addWidget(self.pin_svg)
        layout.addWidget(self.text_label)

        # Set container to be transparent
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # Adjust size
        self.adjustSize()

    def update_pin_size(self) -> None:
        """Update pin size based on current scale."""
        # Calculate size based on scale, but don't go below minimum
        width = max(
            int(self.config.map.BASE_PIN_WIDTH * self._scale),
            self.config.map.MIN_PIN_WIDTH,
        )
        height = max(
            int(self.config.map.BASE_PIN_HEIGHT * self._scale),
            self.config.map.MIN_PIN_HEIGHT,
        )

        # Check if we're using SVG or emoji fallback
        if isinstance(self.pin_svg, QSvgWidget):
            self.pin_svg.setFixedSize(QSize(width, height))
        else:
            # For emoji label, just update the font size
            font_size = max(int(14 * self._scale), 8)  # Minimum font size for emoji
            font = self.pin_svg.font()
            font.setPointSize(font_size)
            self.pin_svg.setFont(font)

    def update_label_style(self) -> None:
        """Update label style based on current scale."""
        # Adjust font size based on scale
        font_size = max(int(8 * self._scale), 6)  # Minimum font size of 6pt
        self.text_label.setStyleSheet(
            f"""
            QLabel {{
                background-color: rgba(0, 0, 0, 50);
                color: white;
                padding: {max(int(2 * self._scale), 1)}px {max(int(4 * self._scale), 2)}px;
                border-radius: 3px;
                font-size: {font_size}pt;
            }}
        """
        )

    def set_scale(self, scale: float) -> None:
        """Set the current scale and update sizes.

        Args:
            scale: The new scale factor.
        """
        self._scale = scale
        self.update_pin_size()
        self.update_label_style()
        self.adjustSize()

    @property
    def pin_height(self) -> int:
        """Get the height of the pin.

        Returns:
            The current height of the pin widget.
        """
        return self.pin_svg.height()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Handle mouse press events.

        Args:
            event: The mouse press event.
        """
        if event.button() == Qt.MouseButton.LeftButton:
            self.pin_clicked.emit(self.text_label.text())
        event.accept()  # Make sure we handle the event
