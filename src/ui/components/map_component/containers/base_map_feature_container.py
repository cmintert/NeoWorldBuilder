from typing import Any, Dict, Optional, Tuple
from PyQt6.QtCore import Qt, pyqtSignal, QPoint
from PyQt6.QtGui import QCursor
from PyQt6.QtWidgets import QWidget, QLabel
from structlog import get_logger

logger = get_logger(__name__)


class BaseMapFeatureContainer(QWidget):
    """Base class for map feature containers (pins, lines, etc.).

    This abstract base class provides common functionality for all map feature
    containers, reducing code duplication and providing a consistent interface.

    Attributes:
        feature_clicked (pyqtSignal): Signal emitted when the feature is clicked.
        target_node (str): The node name this feature represents.
        config: App configuration object.
        edit_mode (bool): Whether this feature is in edit mode.
        text_label (QLabel): Label showing the node name.
    """

    # Signal emitted when feature is clicked - subclasses should define their own signal
    # but maintain this naming and signature convention
    feature_clicked = pyqtSignal(str)

    def __init__(self, target_node: str, parent=None, config=None):
        """Initialize the base container.

        Args:
            target_node (str): The node name this feature represents.
            parent (QWidget, optional): Parent widget. Defaults to None.
            config: App configuration object. Defaults to None.
        """
        super().__init__(parent)
        self.target_node = target_node
        self.config = config
        self._scale = 1.0

        # Edit mode state
        self.edit_mode = False

        # Make mouse interactive
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.setMouseTracking(True)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        # Set container to be transparent
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # Create text label - subclasses should position it appropriately
        self.text_label = QLabel(self.target_node)
        self.text_label.setParent(self)
        self.update_label_style()

        # Make label clickable by enabling mouse events and setting cursor
        self.text_label.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents, False
        )
        self.text_label.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        # Override label's mousePressEvent to handle clicks
        original_mouse_press = self.text_label.mousePressEvent

        def label_mouse_press_event(event):
            if event.button() == Qt.MouseButton.LeftButton:
                # Emit the appropriate signal based on container type
                self._emit_container_click_signal()
                event.accept()
            else:
                original_mouse_press(event)

        self.text_label.mousePressEvent = label_mouse_press_event

        # Show labels by default (instead of only on hover)
        self.text_label.show()

    def _emit_container_click_signal(self) -> None:
        """Emit the appropriate click signal based on container type."""
        # Check what type of container this is and emit the correct signal
        if hasattr(self, 'pin_clicked'):
            # PinContainer has pin_clicked signal
            self.pin_clicked.emit(self.target_node)
        elif hasattr(self, 'line_clicked'):
            # LineContainer has line_clicked signal  
            self.line_clicked.emit(self.target_node)
        else:
            # Fallback to base signal
            self.feature_clicked.emit(self.target_node)

    def update_label_style(self) -> None:
        """Update label style based on current scale.

        This method should be implemented by subclasses to apply appropriate
        styling to the text label based on the current scale.
        """
        raise NotImplementedError("Subclasses must implement update_label_style")

    def set_scale(self, scale: float) -> None:
        """Set the current scale and update sizes.

        Args:
            scale (float): The new scale factor.
        """
        self._scale = scale
        self.update_label_style()

    def set_edit_mode(self, edit_mode: bool) -> None:
        """Enable or disable edit mode for this feature.

        Args:
            edit_mode (bool): Whether edit mode should be active.
        """
        self.edit_mode = edit_mode

        # Set appropriate cursor based on edit mode
        # Subclasses may override this with more specific cursor behavior
        if edit_mode:
            self.setCursor(QCursor(Qt.CursorShape.CrossCursor))
        else:
            self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

    def _find_map_tab(self):
        """Find the parent MapTab instance.

        Returns:
            MapTab instance or None if not found
        """

        parent_widget = self.parent()

        # Traverse up the widget hierarchy looking for MapTab
        level = 0
        while parent_widget:
            class_name = parent_widget.__class__.__name__

            # Direct check for MapTab
            if class_name == "MapTab":

                return parent_widget

            # Check for feature container's parent (which should be image_label)
            if class_name == "MapViewport" and hasattr(parent_widget, "parent_map_tab"):

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

    def _find_controller(self):
        """Find the parent controller for database operations.

        Returns:
            Controller instance or None if not found
        """
        parent_widget = self.parent()
        while parent_widget and not hasattr(parent_widget, "controller"):
            parent_widget = parent_widget.parent()

        if parent_widget and hasattr(parent_widget, "controller"):
            return parent_widget.controller
        return None

    def enterEvent(self, event):
        """Handle mouse enter events.

        Labels are now always visible, so this just provides a hook for subclasses.
        Subclasses should call this method from their overridden implementation.
        """
        pass

    def leaveEvent(self, event):
        """Handle mouse leave events.

        Labels are now always visible, so this just provides a hook for subclasses.
        Subclasses should call this method from their overridden implementation.
        """
        pass
