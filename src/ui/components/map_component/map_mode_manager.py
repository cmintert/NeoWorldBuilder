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

    def toggle_pin_placement(self, active: bool) -> None:
        """Toggle pin placement mode."""
        self.pin_placement_active = active

        if active:
            self.parent_widget.image_label.set_cursor_for_mode("crosshair")
            self.parent_widget.toolbar_manager.update_pin_button_style(True)
        else:
            self.parent_widget.image_label.set_cursor_for_mode("default")
            self.parent_widget.toolbar_manager.update_pin_button_style(False)

        self.pin_mode_toggled.emit(active)

    def toggle_line_drawing(self, active: bool) -> None:
        """Toggle line drawing mode."""
        self.line_drawing_active = active

        if active:
            # Disable other modes
            if self.parent_widget.toolbar_manager.pin_toggle_btn.isChecked():
                self.parent_widget.toolbar_manager.pin_toggle_btn.setChecked(False)

            self.parent_widget.drawing_manager.start_line_drawing()
            self.parent_widget.image_label.set_cursor_for_mode("crosshair")
            self.parent_widget.toolbar_manager.update_line_button_style(True)
            self.parent_widget.image_label.setFocus()
        else:
            # Complete or cancel current drawing
            completing = self.parent_widget.drawing_manager.can_complete_line()
            self.parent_widget.drawing_manager.stop_line_drawing(complete=completing)

            self.parent_widget.image_label.set_cursor_for_mode("default")
            self.parent_widget.toolbar_manager.update_line_button_style(False)

    def toggle_branching_line_drawing(self, active: bool) -> None:
        """Toggle branching line drawing mode."""
        self.branching_line_drawing_active = active

        if active:
            # Disable other modes
            if self.parent_widget.toolbar_manager.pin_toggle_btn.isChecked():
                self.parent_widget.toolbar_manager.pin_toggle_btn.setChecked(False)
            if self.parent_widget.toolbar_manager.line_toggle_btn.isChecked():
                self.parent_widget.toolbar_manager.line_toggle_btn.setChecked(False)
            if self.parent_widget.toolbar_manager.edit_toggle_btn.isChecked():
                self.parent_widget.toolbar_manager.edit_toggle_btn.setChecked(False)

            self.parent_widget.drawing_manager.start_branching_line_drawing()
            self.parent_widget.image_label.set_cursor_for_mode("crosshair")
            self.parent_widget.toolbar_manager.update_branching_line_button_style(True)
            self.parent_widget.image_label.setFocus()
            pass
        else:
            # Complete or cancel current drawing
            completing = self.parent_widget.drawing_manager._can_complete_branching_line()
            self.parent_widget.drawing_manager.stop_branching_line_drawing(complete=completing)

            self.parent_widget.image_label.set_cursor_for_mode("default")
            self.parent_widget.toolbar_manager.update_branching_line_button_style(False)
            pass

    def toggle_edit_mode(self, active: bool) -> None:
        """Toggle edit mode for existing lines."""
        self.edit_mode_active = active
        logger.info(f"Toggle edit mode: {active}")

        if active:
            # Disable other modes
            if self.parent_widget.toolbar_manager.pin_toggle_btn.isChecked():
                self.parent_widget.toolbar_manager.pin_toggle_btn.setChecked(False)
            if self.parent_widget.toolbar_manager.line_toggle_btn.isChecked():
                self.parent_widget.toolbar_manager.line_toggle_btn.setChecked(False)

            self.parent_widget.image_label.set_cursor_for_mode("pointing")
            self.parent_widget.toolbar_manager.update_edit_button_style(True)

            # Set edit mode on feature manager
            self.parent_widget.feature_manager.set_edit_mode(True)
            logger.info("Edit mode activated on feature manager")

            # Set focus to the viewport so it can receive key events
            self.parent_widget.image_label.setFocus()
            logger.info("Set focus to viewport for key events")
        else:
            self.parent_widget.image_label.set_cursor_for_mode("default")
            self.parent_widget.toolbar_manager.update_edit_button_style(False)

            # Disable edit mode on feature manager
            self.parent_widget.feature_manager.set_edit_mode(False)
            logger.info("Edit mode deactivated on feature manager")

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
        if self.edit_mode_active:
            self.parent_widget.image_label.set_cursor_for_mode("pointing")
        else:
            self.parent_widget.image_label.set_cursor_for_mode("default")

        # Force redraw to remove any highlighted points
        self.parent_widget.feature_manager.update_positions(self.parent_widget)

        # Force viewport update to clear branch creation feedback
        self.parent_widget.image_label.update()

    def handle_escape_key(self) -> bool:
        """Handle escape key press for all modes.
        
        Returns:
            True if escape was handled, False otherwise
        """
        if self.branch_creation_mode:
            logger.info("Escape pressed - exiting branch creation mode")
            self.reset_branch_creation_mode()
            return True
        elif self.pin_placement_active:
            logger.info("Escape pressed - exiting pin placement mode")
            self.parent_widget.toolbar_manager.pin_toggle_btn.setChecked(False)
            return True
        elif self.line_drawing_active:
            logger.info("Escape pressed - exiting line drawing mode")
            self.parent_widget.toolbar_manager.line_toggle_btn.setChecked(False)
            return True
        elif self.edit_mode_active:
            logger.info("Escape pressed - exiting edit mode")
            self.parent_widget.toolbar_manager.edit_toggle_btn.setChecked(False)
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
        """Deactivate all modes."""
        if self.pin_placement_active:
            self.parent_widget.toolbar_manager.pin_toggle_btn.setChecked(False)
        if self.line_drawing_active:
            self.parent_widget.toolbar_manager.line_toggle_btn.setChecked(False)
        if self.branching_line_drawing_active:
            self.parent_widget.toolbar_manager.branching_line_toggle_btn.setChecked(False)
        if self.edit_mode_active:
            self.parent_widget.toolbar_manager.edit_toggle_btn.setChecked(False)
        if self.branch_creation_mode:
            self.reset_branch_creation_mode()

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