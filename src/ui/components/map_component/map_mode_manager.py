from typing import Optional
from PyQt6.QtCore import QObject, pyqtSignal
from structlog import get_logger

logger = get_logger(__name__)


class MapModeManager(QObject):
    """Manages the different modes for the map component.
    
    Handles pin placement, line drawing, branching line drawing, and edit modes.
    Ensures mode exclusivity and proper state transitions.
    """

    # Signals
    pin_mode_toggled = pyqtSignal(bool)

    def __init__(self, parent_widget, controller=None):
        """Initialize the mode manager.
        
        Args:
            parent_widget: The parent widget (MapTab instance)
            controller: Application controller
        """
        super().__init__()
        self.parent_widget = parent_widget
        self.controller = controller
        
        # Mode state flags
        self.pin_placement_active = False
        self.line_drawing_active = False
        self.edit_mode_active = False
        self.branching_line_drawing_active = False
        self.branch_creation_mode = False
        
        # Branch creation state
        self._branch_creation_target = None
        self._branch_creation_start_point = None
        self._branch_creation_point_indices = None
    
    def _get_active_viewport(self):
        """Get the currently active viewport widget (graphics view or image label).
        
        Returns:
            The active viewport widget that should receive cursor changes
        """
        # Check if graphics mode is enabled - simplified detection
        if (hasattr(self.parent_widget, 'graphics_adapter') and 
            self.parent_widget.graphics_adapter and
            hasattr(self.parent_widget.graphics_adapter, 'graphics_view')):
            # In graphics mode, use the graphics view
            logger.debug("Using graphics view for cursor")
            return self.parent_widget.graphics_adapter.graphics_view
        else:
            # In widget mode, use the image label
            logger.debug("Using image label for cursor")
            return self.parent_widget.image_label
    
    def _update_graphics_mode(self, mode: str) -> None:
        """Update the graphics adapter with the current mode.
        
        Args:
            mode: The current mode name
        """
        if hasattr(self.parent_widget, 'graphics_adapter') and self.parent_widget.is_graphics_mode():
            self.parent_widget.graphics_adapter.set_current_mode(mode)

    def _deactivate_other_modes(self, current_mode: str) -> None:
        """Deactivate all modes except the specified current mode.
        
        Args:
            current_mode: The mode to keep active ('pin_placement', 'line_drawing', 
                         'branching_line_drawing', 'edit', or None to deactivate all modes)
        """
        if current_mode is None:
            logger.info("Deactivating all modes")
        else:
            logger.info(f"Enforcing mode exclusivity - keeping {current_mode} active")
        
        # Deactivate pin placement
        if current_mode != 'pin_placement' and self.pin_placement_active:
            logger.debug("Deactivating pin placement mode")
            self.pin_placement_active = False
            self.parent_widget.toolbar_manager.pin_toggle_btn.setChecked(False)
            self.parent_widget.toolbar_manager.update_pin_button_style(False)
        
        # Deactivate line drawing
        if current_mode != 'line_drawing' and self.line_drawing_active:
            logger.debug("Deactivating line drawing mode")
            # Complete or cancel current drawing
            completing = self.parent_widget.drawing_manager.can_complete_line()
            self.parent_widget.drawing_manager.stop_line_drawing(complete=completing)
            
            self.line_drawing_active = False
            self.parent_widget.toolbar_manager.line_toggle_btn.setChecked(False)
            self.parent_widget.toolbar_manager.update_line_button_style(False)
        
        # Deactivate branching line drawing
        if current_mode != 'branching_line_drawing' and self.branching_line_drawing_active:
            logger.debug("Deactivating branching line drawing mode")
            # Complete or cancel current drawing
            completing = self.parent_widget.drawing_manager._can_complete_branching_line()
            self.parent_widget.drawing_manager.stop_branching_line_drawing(complete=completing)
            
            self.branching_line_drawing_active = False
            self.parent_widget.toolbar_manager.branching_line_toggle_btn.setChecked(False)
            self.parent_widget.toolbar_manager.update_branching_line_button_style(False)
        
        # Deactivate edit mode
        if current_mode != 'edit' and self.edit_mode_active:
            logger.debug("Deactivating edit mode")
            self.edit_mode_active = False
            self.parent_widget.toolbar_manager.edit_toggle_btn.setChecked(False)
            self.parent_widget.toolbar_manager.update_edit_button_style(False)
            
            # Disable edit mode on graphics system
            if hasattr(self.parent_widget, 'graphics_adapter'):
                self.parent_widget.graphics_adapter.feature_manager.set_edit_mode(False)
        
        # Always deactivate branch creation mode if switching to a different primary mode
        if current_mode != 'branch_creation' and self.branch_creation_mode:
            logger.debug("Deactivating branch creation mode")
            self.reset_branch_creation_mode()

    def toggle_pin_placement(self, active: bool) -> None:
        """Toggle pin placement mode with mutual exclusion."""
        if active:
            # Deactivate all other modes first
            self._deactivate_other_modes('pin_placement')
            
            self.pin_placement_active = True
            viewport = self._get_active_viewport()
            logger.info(f"Setting cursor on viewport: {type(viewport)} for pin_placement mode")
            viewport.set_cursor_for_mode("pin_placement")
            self.parent_widget.toolbar_manager.update_pin_button_style(True)
            self._update_graphics_mode("pin_placement")
            logger.info("Pin placement mode activated")
        else:
            self.pin_placement_active = False
            viewport = self._get_active_viewport()
            viewport.set_cursor_for_mode("default")
            self.parent_widget.toolbar_manager.update_pin_button_style(False)
            self._update_graphics_mode("default")
            logger.info("Pin placement mode deactivated")

        self.pin_mode_toggled.emit(active)

    def toggle_line_drawing(self, active: bool) -> None:
        """Toggle line drawing mode with mutual exclusion."""
        if active:
            # Deactivate all other modes first
            self._deactivate_other_modes('line_drawing')

            self.line_drawing_active = True
            self.parent_widget.drawing_manager.start_line_drawing()
            viewport = self._get_active_viewport()
            viewport.set_cursor_for_mode("line_drawing")
            self.parent_widget.toolbar_manager.update_line_button_style(True)
            viewport.setFocus()
            self._update_graphics_mode("line_drawing")
            logger.info("Line drawing mode activated")
        else:
            # Complete or cancel current drawing
            completing = self.parent_widget.drawing_manager.can_complete_line()
            self.parent_widget.drawing_manager.stop_line_drawing(complete=completing)

            self.line_drawing_active = False
            viewport = self._get_active_viewport()
            viewport.set_cursor_for_mode("default")
            self.parent_widget.toolbar_manager.update_line_button_style(False)
            self._update_graphics_mode("default")
            logger.info("Line drawing mode deactivated")

    def toggle_branching_line_drawing(self, active: bool) -> None:
        """Toggle branching line drawing mode with mutual exclusion."""
        if active:
            # Deactivate all other modes first
            self._deactivate_other_modes('branching_line_drawing')

            self.branching_line_drawing_active = True
            self.parent_widget.drawing_manager.start_branching_line_drawing()
            viewport = self._get_active_viewport()
            viewport.set_cursor_for_mode("branching_line_drawing")
            self.parent_widget.toolbar_manager.update_branching_line_button_style(True)
            viewport.setFocus()
            self._update_graphics_mode("branching_line_drawing")
            logger.info("Branching line drawing mode activated")
        else:
            # Complete or cancel current drawing
            completing = self.parent_widget.drawing_manager._can_complete_branching_line()
            self.parent_widget.drawing_manager.stop_branching_line_drawing(complete=completing)

            self.branching_line_drawing_active = False
            viewport = self._get_active_viewport()
            viewport.set_cursor_for_mode("default")
            self.parent_widget.toolbar_manager.update_branching_line_button_style(False)
            self._update_graphics_mode("default")
            logger.info("Branching line drawing mode deactivated")

    def toggle_edit_mode(self, active: bool) -> None:
        """Toggle edit mode for existing lines with mutual exclusion."""
        if active:
            # Deactivate all other modes first
            self._deactivate_other_modes('edit')

            self.edit_mode_active = True
            viewport = self._get_active_viewport()
            viewport.set_cursor_for_mode("edit")
            self.parent_widget.toolbar_manager.update_edit_button_style(True)
            self._update_graphics_mode("edit")

            # Activate edit mode in graphics system
            if hasattr(self.parent_widget, 'graphics_adapter'):
                self.parent_widget.graphics_adapter.feature_manager.set_edit_mode(True)
                logger.debug("Edit mode enabled on graphics feature manager")
            else:
                logger.warning("No graphics adapter available for edit mode")

            # Set focus to the viewport so it can receive key events
            viewport.setFocus()
            logger.info("Edit mode activated")
        else:
            self.edit_mode_active = False
            viewport = self._get_active_viewport()
            viewport.set_cursor_for_mode("default")
            self.parent_widget.toolbar_manager.update_edit_button_style(False)
            self._update_graphics_mode("default")

            # Deactivate edit mode in graphics system
            if hasattr(self.parent_widget, 'graphics_adapter'):
                self.parent_widget.graphics_adapter.feature_manager.set_edit_mode(False)
                logger.debug("Edit mode disabled on graphics feature manager")
            else:
                logger.warning("No graphics adapter available for edit mode")
            logger.info("Edit mode deactivated")

    def set_branch_creation_mode(self, active: bool) -> None:
        """Set branch creation mode state."""
        self.branch_creation_mode = active

    def reset_branch_creation_mode(self) -> None:
        """Reset branch creation mode state."""
        logger.info("Resetting branch creation mode")
        self.branch_creation_mode = False
        
        # Clear branch creation attributes
        self._branch_creation_target = None
        self._branch_creation_start_point = None
        self._branch_creation_point_indices = None

        # Reset cursor based on current mode
        viewport = self._get_active_viewport()
        if self.edit_mode_active:
            viewport.set_cursor_for_mode("edit")
            self._update_graphics_mode("edit")
        else:
            viewport.set_cursor_for_mode("default")
            self._update_graphics_mode("default")

        # Force redraw to remove any highlighted points
        # Graphics mode handles position updates automatically
        logger.debug("Position updates handled automatically (graphics mode)")

        # Force viewport update to clear branch creation feedback
        viewport.update()

    def handle_escape_key(self) -> bool:
        """Handle escape key press for all modes.
        
        Returns:
            True if escape was handled, False otherwise
        """
        # Check if any mode is active
        if self.is_any_mode_active():
            active_mode = self.get_active_mode()
            logger.info(f"Escape pressed - exiting {active_mode} mode")
            
            # Deactivate all modes
            self.deactivate_all_modes()
            return True
        
        return False

    def is_any_mode_active(self) -> bool:
        """Check if any mode is currently active."""
        return (self.pin_placement_active or 
                self.line_drawing_active or 
                self.edit_mode_active or 
                self.branching_line_drawing_active or 
                self.branch_creation_mode)

    def get_active_mode(self) -> Optional[str]:
        """Get the name of the currently active mode."""
        if self.branch_creation_mode:
            return "branch_creation"
        elif self.pin_placement_active:
            return "pin_placement"
        elif self.line_drawing_active:
            return "line_drawing"
        elif self.branching_line_drawing_active:
            return "branching_line_drawing"
        elif self.edit_mode_active:
            return "edit"
        else:
            return None

    def deactivate_all_modes(self) -> None:
        """Deactivate all modes using centralized system."""
        logger.info("Deactivating all modes")
        # Use centralized deactivation with no active mode
        self._deactivate_other_modes(None)
        
        # Reset cursor to default
        viewport = self._get_active_viewport()
        viewport.set_cursor_for_mode("default")
        self._update_graphics_mode("default")

    def set_branch_creation_target(self, target: str) -> None:
        """Set the branch creation target node."""
        self._branch_creation_target = target

    def get_branch_creation_target(self) -> Optional[str]:
        """Get the branch creation target node."""
        return self._branch_creation_target

    def set_branch_creation_start_point(self, point: tuple) -> None:
        """Set the branch creation start point."""
        self._branch_creation_start_point = point

    def get_branch_creation_start_point(self) -> Optional[tuple]:
        """Get the branch creation start point."""
        return self._branch_creation_start_point

    def set_branch_creation_point_indices(self, indices: tuple) -> None:
        """Set the branch creation point indices."""
        self._branch_creation_point_indices = indices

    def get_branch_creation_point_indices(self) -> Optional[tuple]:
        """Get the branch creation point indices."""
        return self._branch_creation_point_indices