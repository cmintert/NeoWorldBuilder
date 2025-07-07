"""Adapter to provide compatibility between MapTab and graphics-based implementation."""

from typing import Optional, Dict, Any

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QWidget, QVBoxLayout
from structlog import get_logger

from .map_graphics_view import MapGraphicsView
from .map_graphics_scene import MapGraphicsScene
from .graphics_feature_manager import GraphicsFeatureManager

logger = get_logger(__name__)


class MapTabGraphicsAdapter(QObject):
    """Provides backward compatibility during migration from widget to graphics system.
    
    This adapter bridges the interface between the existing MapTab implementation
    and the new graphics-based components, allowing for gradual migration.
    """
    
    # Mirror existing MapTab signals for compatibility
    map_image_changed = pyqtSignal(str)
    pin_mode_toggled = pyqtSignal(bool)
    pin_created = pyqtSignal(str, str, dict)
    pin_clicked = pyqtSignal(str)
    line_created = pyqtSignal(str, str, dict)
    
    def __init__(self, map_tab: QWidget, config: Optional[Dict[str, Any]] = None):
        """Initialize the adapter.
        
        Args:
            map_tab: The existing MapTab widget to adapt
            config: Configuration dictionary
        """
        super().__init__(map_tab)
        self.map_tab = map_tab
        self.config = config or {}
        
        # Create graphics components
        self.graphics_scene = MapGraphicsScene(self)
        self.graphics_view = MapGraphicsView(parent=map_tab, config=config)
        self.graphics_view.set_scene(self.graphics_scene)
        
        # Create feature manager for graphics system
        self.feature_manager = GraphicsFeatureManager(self.graphics_scene)
        
        # Connect drawing manager for temporary line preview
        self._connect_drawing_manager()
        
        # Replace the viewport in the existing layout if possible
        self._integrate_graphics_view()
        
        # Hide graphics view initially until migration is enabled
        self.graphics_view.hide()
        
        # Connect signals for compatibility
        self._setup_signal_forwarding()
        
        # Track adapter state
        self.is_migrated = False
        self.widget_viewport = None  # Store reference to old viewport
        
        logger.info("MapTabGraphicsAdapter initialized")
    
    def _integrate_graphics_view(self) -> None:
        """Integrate graphics view into existing MapTab layout."""
        # Try to find and replace the scroll area or viewport
        layout = self.map_tab.layout()
        if layout:
            # Look for the scroll area containing the old viewport
            for i in range(layout.count()):
                item = layout.itemAt(i)
                if item and item.widget():
                    widget = item.widget()
                    # Check if this is the scroll area with the map viewport
                    if hasattr(widget, 'widget') and hasattr(widget, 'setWidget'):  # QScrollArea
                        # Store reference to old viewport and scroll area
                        self.widget_viewport = widget.widget()
                        self.widget_scroll_area = widget
                        # Hide old widget instead of removing (for rollback capability)
                        widget.hide()
                        # Insert graphics view at same position
                        layout.insertWidget(i, self.graphics_view)
                        logger.info("Graphics view integrated into existing layout")
                        break
        else:
            # If no layout exists, create one
            layout = QVBoxLayout(self.map_tab)
            layout.addWidget(self.graphics_view)
            logger.info("Created new layout for graphics view")
    
    def _setup_signal_forwarding(self) -> None:
        """Set up signal forwarding between graphics and legacy systems."""
        # Forward view signals
        self.graphics_view.click_at_coordinates.connect(
            self._handle_click_at_coordinates
        )
        self.graphics_view.coordinates_changed.connect(
            self._handle_coordinates_changed
        )
        self.graphics_view.key_press_event.connect(
            self._handle_key_press_event
        )
        
        # Forward scene signals
        self.graphics_scene.image_loaded.connect(
            lambda path, w, h: self.map_image_changed.emit(path)
        )
        
        # Forward feature manager signals
        self.feature_manager.signal_bridge.pin_clicked.connect(self.pin_clicked.emit)
        self.feature_manager.signal_bridge.line_clicked.connect(
            lambda node: self.pin_clicked.emit(node)  # Use same signal for compatibility
        )
        self.feature_manager.signal_bridge.feature_created.connect(
            lambda ftype, node: self.pin_created.emit(ftype, node, {})  # Adapt signature
        )
        # Connect line geometry changes to database updates
        self.feature_manager.signal_bridge.line_geometry_changed.connect(
            self._handle_line_geometry_changed
        )
    
    def _handle_click_at_coordinates(self, x: int, y: int) -> None:
        """Handle click events from graphics view.
        
        Args:
            x: X coordinate in original image space
            y: Y coordinate in original image space
        """
        # Check if we're in a placement mode using individual mode flags
        if hasattr(self.map_tab, 'mode_manager'):
            mode_manager = self.map_tab.mode_manager
            if mode_manager.pin_placement_active:
                # Pin placement mode - forward to event handler
                if hasattr(self.map_tab, 'event_handler'):
                    self.map_tab.event_handler.handle_coordinate_click(x, y)
            elif mode_manager.line_drawing_active:
                # Line drawing mode - forward to event handler
                if hasattr(self.map_tab, 'event_handler'):
                    self.map_tab.event_handler.handle_coordinate_click(x, y)
            elif mode_manager.branching_line_drawing_active:
                # Branching line mode - forward to event handler
                if hasattr(self.map_tab, 'event_handler'):
                    self.map_tab.event_handler.handle_coordinate_click(x, y)
    
    def _handle_coordinates_changed(self, x: int, y: int) -> None:
        """Handle coordinate updates from graphics view.
        
        Args:
            x: X coordinate
            y: Y coordinate
        """
        # Update coordinate display if it exists
        if hasattr(self.map_tab, 'coordinate_utilities'):
            self.map_tab.coordinate_utilities.update_coordinate_display(x, y)
    
    def _handle_key_press_event(self, event) -> None:
        """Handle key press events from graphics view.
        
        Args:
            event: QKeyEvent from graphics view
        """
        logger.debug(f"Graphics adapter handling key press: {event.key()}")
        
        # Forward to event handler for line drawing functionality
        if hasattr(self.map_tab, 'event_handler'):
            # Convert QKeyEvent to the format expected by handle_viewport_key_press
            result = self.map_tab.event_handler.handle_viewport_key_press(event)
            logger.debug(f"Key press forwarding result: {result}")
        else:
            logger.warning("No event handler available for key press forwarding")
    
    def _connect_drawing_manager(self) -> None:
        """Connect the drawing manager to graphics view for temporary line preview."""
        try:
            if hasattr(self.map_tab, 'drawing_manager'):
                drawing_manager = self.map_tab.drawing_manager
                self.graphics_view.set_drawing_manager(drawing_manager)
                
                # Connect drawing manager signals to trigger view updates
                if hasattr(drawing_manager, 'drawing_updated'):
                    drawing_manager.drawing_updated.connect(self._update_temporary_line)
                    logger.debug("Connected drawing_updated signal to graphics view")
                else:
                    logger.warning("Drawing manager has no drawing_updated signal")
                
                logger.debug(f"Connected drawing manager to graphics view: {type(drawing_manager)}")
            else:
                logger.warning("No drawing manager found on map tab")
        except Exception as e:
            logger.error(f"Failed to connect drawing manager: {e}")
    
    def _update_temporary_line(self) -> None:
        """Update the graphics view when temporary line changes."""
        logger.debug("Updating temporary line in graphics view")
        self.graphics_view.update()  # Trigger repaint to show updated temporary line
        self.graphics_view.viewport().update()  # Force viewport repaint
    
    def _handle_line_geometry_changed(self, node_name: str, geometry_data: list) -> None:
        """Handle line geometry changes and update database.
        
        Args:
            node_name: Name of the node whose geometry changed
            geometry_data: New geometry data (list of points or branches)
        """
        logger.info(f"Line geometry changed for {node_name}")
        
        # Use the existing persistence layer to update the database
        from ui.components.map_component.line_persistence import LineGeometryPersistence
        persistence = LineGeometryPersistence(node_name)
        persistence.update_geometry(geometry_data, self.map_tab.controller)
        
        logger.debug(f"Updated database geometry for {node_name}")
    
    # Compatibility methods that mirror MapViewport interface
    def load_image(self, image_path: str) -> bool:
        """Load an image into the graphics scene.
        
        Args:
            image_path: Path to image file
            
        Returns:
            True if successful
        """
        return self.graphics_scene.load_map_image(image_path)
    
    def get_current_position(self) -> tuple[int, int]:
        """Get current mouse position in original coordinates.
        
        Returns:
            Tuple of (x, y) coordinates
        """
        # This would need to track from mouseMoveEvent
        return (0, 0)
    
    def fit_image_in_view(self) -> None:
        """Fit the entire image in the view."""
        self.graphics_view.fit_image_in_view()
    
    def center_on_coordinates(self, x: int, y: int) -> None:
        """Center view on specific coordinates.
        
        Args:
            x: X coordinate
            y: Y coordinate
        """
        self.graphics_view.center_on_coordinates(x, y)
    
    def set_image_opacity(self, opacity: float) -> None:
        """Set background image opacity.
        
        Args:
            opacity: Opacity value 0.0-1.0
        """
        self.graphics_scene.set_background_opacity(opacity)
    
    def enable_migration(self) -> None:
        """Enable the graphics-based system and hide widget-based components."""
        if not self.is_migrated:
            self.graphics_view.show()
            if hasattr(self, 'widget_scroll_area'):
                self.widget_scroll_area.hide()
            elif self.widget_viewport:
                self.widget_viewport.hide()
            
            # Migrate existing features to graphics system
            self._migrate_existing_features()
            
            # Ensure drawing manager is connected after migration
            self._connect_drawing_manager()
            
            # Test the drawing manager connection
            if hasattr(self.map_tab, 'drawing_manager') and hasattr(self.graphics_view, '_drawing_manager'):
                logger.info(f"Drawing manager connection verified: graphics view has drawing manager: {self.graphics_view._drawing_manager is not None}")
            else:
                logger.warning("Drawing manager connection failed - missing components")
            
            # Give graphics view focus to receive key events
            self.graphics_view.setFocus()
            
            self.is_migrated = True
            logger.info("Migration to graphics system enabled")
    
    def disable_migration(self) -> None:
        """Disable graphics system and restore widget-based components."""
        if self.is_migrated:
            self.graphics_view.hide()
            if self.widget_viewport:
                self.widget_viewport.show()
            self.is_migrated = False
            logger.info("Rolled back to widget system")
    
    def is_graphics_mode(self) -> bool:
        """Check if currently using graphics mode.
        
        Returns:
            True if in graphics mode
        """
        return self.is_migrated
    
    def _migrate_existing_features(self) -> None:
        """Migrate existing widget-based features to graphics system."""
        try:
            # Check if map tab has a feature manager with existing features
            if hasattr(self.map_tab, 'feature_manager'):
                widget_manager = self.map_tab.feature_manager
                
                # Get all existing features from widget system
                existing_features = getattr(widget_manager, 'features', {})
                
                logger.info(f"Migrating {len(existing_features)} existing features to graphics system")
                
                # Use existing graphics feature manager
                graphics_manager = self.feature_manager
                
                for node_name, widget_feature in existing_features.items():
                    try:
                        # Determine feature type and extract data
                        if hasattr(widget_feature, 'pin_svg'):  # Pin feature
                            # Get pin position
                            pos = widget_feature.pos()
                            x, y = pos.x(), pos.y()
                            
                            # Create graphics pin
                            graphics_manager.add_pin_feature(node_name, x, y)
                            logger.debug(f"Migrated pin: {node_name} at ({x}, {y})")
                            
                        elif hasattr(widget_feature, 'geometry'):  # Line feature
                            # Get line geometry
                            line_geometry = widget_feature.geometry
                            
                            # Extract points or branches
                            if hasattr(line_geometry, 'branches'):
                                if line_geometry.is_branching:
                                    # Branching line
                                    branches = [branch.copy() for branch in line_geometry.branches]
                                    graphics_manager.add_branching_line_feature(node_name, branches)
                                    logger.debug(f"Migrated branching line: {node_name}")
                                else:
                                    # Simple line
                                    points = line_geometry.branches[0].copy() if line_geometry.branches else []
                                    graphics_manager.add_line_feature(node_name, points)
                                    logger.debug(f"Migrated simple line: {node_name}")
                        
                    except Exception as e:
                        logger.warning(f"Failed to migrate feature {node_name}: {e}")
                
                logger.info("Feature migration completed")
                
        except Exception as e:
            logger.error(f"Error during feature migration: {e}")
    
    def get_graphics_feature_manager(self):
        """Get the graphics feature manager.
        
        Returns:
            Graphics feature manager instance
        """
        if hasattr(self, 'feature_manager'):
            return self.feature_manager
        else:
            # Create one if it doesn't exist
            from .graphics_feature_manager import GraphicsFeatureManager
            self.feature_manager = GraphicsFeatureManager(self.graphics_scene)
            return self.feature_manager