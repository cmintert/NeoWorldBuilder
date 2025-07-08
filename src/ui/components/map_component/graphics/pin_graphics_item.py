"""Pin graphics item for QGraphicsView-based map rendering."""

import os
from typing import Optional, Dict, Any

from PyQt6.QtCore import Qt, pyqtSignal, QRectF, QPointF, QObject, QTimer
from PyQt6.QtGui import QPainter, QCursor, QFont, QColor, QBrush, QPen
from PyQt6.QtSvgWidgets import QGraphicsSvgItem
from PyQt6.QtWidgets import QGraphicsItem, QGraphicsTextItem, QGraphicsRectItem, QStyleOptionGraphicsItem, QWidget
from structlog import get_logger

from utils.path_helper import get_resource_path

logger = get_logger(__name__)


class PinGraphicsItem(QGraphicsItem):
    """Graphics item representing a map pin with SVG rendering and interaction.
    
    This replaces the widget-based PinContainer with a QGraphicsItem
    implementation that works properly with overlapping elements.
    """
    
    feature_type = 'pin'
    
    def __init__(self, target_node: str, x: int, y: int, 
                 config: Optional[Dict[str, Any]] = None, parent=None):
        """Initialize the pin graphics item.
        
        Args:
            target_node: Name of the node this pin represents
            x: X coordinate in original image space
            y: Y coordinate in original image space
            config: Configuration object
            parent: Parent graphics item
        """
        super().__init__(parent)
        
        self.target_node = target_node
        self.config = config or {}
        self._scale = 1.0
        self.edit_mode = False
        self.dragging = False
        self.just_created = True  # Prevent immediate click signals after creation
        
        # Set up timer to clear just_created flag after short delay
        self.creation_timer = QTimer()
        self.creation_timer.setSingleShot(True)
        self.creation_timer.timeout.connect(self._clear_creation_flag)
        self.creation_timer.start(500)  # 500ms delay
        
        # Set item flags
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)  # Will enable in edit mode
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setAcceptHoverEvents(True)
        
        # Pin dimensions from config
        map_config = self.config.get('map', {})
        self.base_width = map_config.get('BASE_PIN_WIDTH', 24)
        self.base_height = map_config.get('BASE_PIN_HEIGHT', 32)
        self.min_width = map_config.get('MIN_PIN_WIDTH', 12)
        self.min_height = map_config.get('MIN_PIN_HEIGHT', 16)
        
        # Create SVG item for the pin
        self.svg_item = None
        self.fallback_text = None
        self._setup_pin_visual()
        
        # Create text label
        self.text_item = QGraphicsTextItem(self.target_node, self)
        self._setup_text_label()
        
        # Position the pin
        self.setPos(x, y)
        
        # Z-value for pins should be high
        self.setZValue(100)
        
        logger.debug(f"Created PinGraphicsItem for {target_node} at ({x}, {y})")
    
    def _setup_pin_visual(self) -> None:
        """Set up the visual representation of the pin (SVG or fallback)."""
        try:
            # Try to load SVG
            svg_path = self.config.get('map', {}).get('PIN_SVG_SOURCE', '')
            if svg_path:
                svg_path = get_resource_path(svg_path)
                
                if os.path.exists(svg_path):
                    self.svg_item = QGraphicsSvgItem(svg_path, self)
                    self._update_svg_size()
                    logger.debug(f"Loaded SVG pin from: {svg_path}")
                    return
            
            # Fallback to text-based pin
            self._create_fallback_pin()
            
        except Exception as e:
            logger.warning(f"Failed to load SVG pin: {e}")
            self._create_fallback_pin()
    
    def _create_fallback_pin(self) -> None:
        """Create a fallback text-based pin representation."""
        self.fallback_text = QGraphicsTextItem("📍", self)
        font = self.fallback_text.font()
        font.setPointSize(int(20 * self._scale))
        self.fallback_text.setFont(font)
        logger.debug("Created fallback emoji pin")
    
    def _setup_text_label(self) -> None:
        """Set up the text label for the pin."""
        # Position label below the pin
        label_y = self.base_height + 2
        self.text_item.setPos(0, label_y)
        
        # Style the text
        self._update_text_style()
    
    def _update_svg_size(self) -> None:
        """Update SVG size based on current scale."""
        if self.svg_item:
            width = max(int(self.base_width * self._scale), self.min_width)
            height = max(int(self.base_height * self._scale), self.min_height)
            
            # Scale the SVG item
            current_size = self.svg_item.boundingRect().size()
            if current_size.width() > 0 and current_size.height() > 0:
                scale_x = width / current_size.width()
                scale_y = height / current_size.height()
                self.svg_item.setScale(min(scale_x, scale_y))
    
    def _update_text_style(self) -> None:
        """Update text label styling based on scale."""
        font_size = max(int(8 * self._scale), 6)
        font = QFont()
        font.setPointSize(font_size)
        self.text_item.setFont(font)
        
        # Set text color to white for visibility
        self.text_item.setDefaultTextColor(QColor(255, 255, 255))
    
    def boundingRect(self) -> QRectF:
        """Return the bounding rectangle of the pin including label.
        
        Returns:
            Bounding rectangle in item coordinates
        """
        pin_width = max(int(self.base_width * self._scale), self.min_width)
        pin_height = max(int(self.base_height * self._scale), self.min_height)
        
        # Include text label in bounds
        text_bounds = self.text_item.boundingRect()
        total_height = pin_height + text_bounds.height() + 2
        total_width = max(pin_width, text_bounds.width())
        
        return QRectF(0, 0, total_width, total_height)
    
    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: Optional[QWidget] = None) -> None:
        """Paint the pin (SVG item and text item paint themselves).
        
        Args:
            painter: QPainter instance
            option: Style options
            widget: Widget being painted on
        """
        # Background for text label
        if self.text_item:
            text_rect = self.text_item.boundingRect()
            text_pos = self.text_item.pos()
            
            # Draw semi-transparent background behind text
            bg_rect = QRectF(
                text_pos.x() - 2,
                text_pos.y() - 1, 
                text_rect.width() + 4,
                text_rect.height() + 2
            )
            
            painter.setBrush(QBrush(QColor(0, 0, 0, 50)))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(bg_rect, 3, 3)
    
    def mousePressEvent(self, event) -> None:
        """Handle mouse press events.
        
        Args:
            event: Mouse press event
        """
        if event.button() == Qt.MouseButton.LeftButton:
            if self.edit_mode:
                # Start drag operation
                self.dragging = True
                self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
            else:
                # Only emit click signal if not just created
                if not self.just_created:
                    self._emit_click_signal()
                else:
                    logger.debug(f"Ignoring click on just-created pin: {self.target_node}")
            event.accept()
        else:
            super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event) -> None:
        """Handle mouse move events during drag.
        
        Args:
            event: Mouse move event
        """
        if self.dragging and self.edit_mode:
            super().mouseMoveEvent(event)
            # Position will be updated automatically by Qt
        else:
            super().mouseMoveEvent(event)
    
    def mouseReleaseEvent(self, event) -> None:
        """Handle mouse release events.
        
        Args:
            event: Mouse release event
        """
        if event.button() == Qt.MouseButton.LeftButton and self.dragging:
            self.dragging = False
            self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)
            
            # Emit position changed signal
            scene_pos = self.scenePos()
            self._emit_position_changed(int(scene_pos.x()), int(scene_pos.y()))
            
        super().mouseReleaseEvent(event)
    
    def hoverEnterEvent(self, event) -> None:
        """Handle hover enter events.
        
        Args:
            event: Hover event
        """
        # Check if we should override cursor based on current mode
        current_mode = self._get_current_mode()
        
        # Only set item-specific cursors in default or edit modes
        if current_mode in ["default", "edit", None]:
            if self.edit_mode:
                self.setCursor(QCursor(Qt.CursorShape.SizeAllCursor))
            else:
                self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        # Otherwise, let the mode's cursor remain active
        
        super().hoverEnterEvent(event)
    
    def hoverLeaveEvent(self, event) -> None:
        """Handle hover leave events.
        
        Args:
            event: Hover event
        """
        # Only reset cursor if we're not in a special mode
        current_mode = self._get_current_mode()
        if current_mode in ["default", None]:
            self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
        # Otherwise, let the mode's cursor remain active
        
        super().hoverLeaveEvent(event)
    
    def _get_current_mode(self) -> Optional[str]:
        """Get the current interaction mode from the adapter.
        
        Returns:
            Current mode string or None
        """
        scene = self.scene()
        if scene and hasattr(scene, 'views'):
            views = scene.views()
            if views:
                view = views[0]
                if hasattr(view, 'parent') and hasattr(view.parent(), 'graphics_adapter'):
                    adapter = view.parent().graphics_adapter
                    return getattr(adapter, 'current_mode', None)
        return None
    
    def set_scale(self, scale: float) -> None:
        """Set the display scale for the pin.
        
        Args:
            scale: Scale factor
        """
        self._scale = scale
        self._update_svg_size()
        self._update_text_style()
        self.update()
    
    def set_edit_mode(self, enabled: bool) -> None:
        """Enable or disable edit mode.
        
        Args:
            enabled: Whether edit mode should be enabled
        """
        self.edit_mode = enabled
        # Cursor will be updated on next hover event
    
    def update_text(self, text: str) -> None:
        """Update the text label.
        
        Args:
            text: New text for the label
        """
        self.text_item.setPlainText(text)
        self.update()
    
    def get_original_coordinates(self) -> tuple[int, int]:
        """Get coordinates in original image space.
        
        Returns:
            Tuple of (x, y) coordinates
        """
        scene_pos = self.scenePos()
        return int(scene_pos.x()), int(scene_pos.y())
    
    def _emit_click_signal(self) -> None:
        """Emit click signal through parent scene/view."""
        # Find signal bridge through scene's feature manager
        scene = self.scene()
        if scene and hasattr(scene, 'feature_items'):
            # The scene should have a reference to the feature manager
            # For now, emit through parent widget hierarchy
            parent_widget = scene.parent()
            while parent_widget:
                if hasattr(parent_widget, 'graphics_adapter'):
                    if hasattr(parent_widget.graphics_adapter, 'signal_bridge'):
                        parent_widget.graphics_adapter.signal_bridge.pin_clicked.emit(self.target_node)
                        break
                    elif hasattr(parent_widget.graphics_adapter, 'feature_manager'):
                        if hasattr(parent_widget.graphics_adapter.feature_manager, 'signal_bridge'):
                            parent_widget.graphics_adapter.feature_manager.signal_bridge.pin_clicked.emit(self.target_node)
                            break
                parent_widget = getattr(parent_widget, 'parent', lambda: None)()
        
        logger.debug(f"Pin clicked: {self.target_node}")
    
    def _clear_creation_flag(self) -> None:
        """Clear the just_created flag to allow normal click behavior."""
        self.just_created = False
        logger.debug(f"Pin {self.target_node} now accepts click events")
    
    def _emit_position_changed(self, x: int, y: int) -> None:
        """Emit position changed signal.
        
        Args:
            x: New X coordinate
            y: New Y coordinate
        """
        # Similar to click signal, find the bridge
        scene = self.scene()
        if scene and hasattr(scene, 'feature_items'):
            parent_widget = scene.parent()
            while parent_widget:
                if hasattr(parent_widget, 'graphics_adapter'):
                    if hasattr(parent_widget.graphics_adapter, 'signal_bridge'):
                        parent_widget.graphics_adapter.signal_bridge.pin_moved.emit(self.target_node, x, y)
                        break
                    elif hasattr(parent_widget.graphics_adapter, 'feature_manager'):
                        if hasattr(parent_widget.graphics_adapter.feature_manager, 'signal_bridge'):
                            parent_widget.graphics_adapter.feature_manager.signal_bridge.pin_moved.emit(self.target_node, x, y)
                            break
                parent_widget = getattr(parent_widget, 'parent', lambda: None)()
        
        logger.debug(f"Pin moved: {self.target_node} to ({x}, {y})")