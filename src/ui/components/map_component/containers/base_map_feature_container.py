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
        print(f"BaseMapFeatureContainer._find_map_tab called")
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
        """Show label when mouse enters the feature area.
        
        Subclasses should call this method from their overridden implementation.
        """
        self.text_label.show()
        
    def leaveEvent(self, event):
        """Hide label when mouse leaves the feature area.
        
        Subclasses should call this method from their overridden implementation.
        """
        self.text_label.hide()
