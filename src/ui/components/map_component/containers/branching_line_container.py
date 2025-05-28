"""Branching line container for map component.

This module provides the BranchingLineContainer class for handling branching line features
in the map component. It serves as a specialized container that leverages the unified
LineContainer implementation for branching line functionality.
"""

from typing import List, Tuple, Dict, Any, Optional
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QWidget

from .line_container import LineContainer


class BranchingLineContainer(QWidget):
    """Container widget for branching lines.

    This container acts as a specialized wrapper around LineContainer,
    providing a dedicated interface for branching line functionality while
    leveraging the unified line implementation.
    
    The BranchingLineContainer delegates all actual functionality to an internal
    LineContainer instance, which handles both simple and branching line geometries
    through its unified architecture.
    """

    # Signals
    line_clicked = pyqtSignal(str)  # target_node
    geometry_changed = pyqtSignal(str, list)  # target_node, branches

    def __init__(
        self,
        target_node: str,
        branches: List[List[Tuple[int, int]]],
        parent: Optional[QWidget] = None,
        config: Optional[Any] = None,
    ):
        """Initialize branching line container.

        Args:
            target_node: Node name this line represents
            branches: List of branches, each branch is a list of coordinate points
            parent: Parent widget
            config: Configuration object
        """
        super().__init__(parent)

        # Create the actual container implementation using unified system
        self._container = LineContainer(target_node, branches, parent, config)

        # Connect signals from the internal container to our interface
        self._container.line_clicked.connect(self.line_clicked)
        self._container.geometry_changed.connect(self.geometry_changed)

        # Forward essential methods to provide a clean interface
        # These methods delegate to the internal LineContainer
        self.set_scale = self._container.set_scale
        self.set_style = self._container.set_style
        self.set_edit_mode = self._container.set_edit_mode
        self.show = self._container.show
        self.raise_ = self._container.raise_
        
        # Override deleteLater to ensure proper cleanup
        self._original_deleteLater = super().deleteLater

    def deleteLater(self) -> None:
        """Override deleteLater to clean up internal container."""
        if hasattr(self, '_container') and self._container:
            self._container.deleteLater()
        self._original_deleteLater()

    @property
    def target_node(self) -> str:
        """Get the target node name."""
        return self._container.target_node

    @property
    def geometry(self):
        """Get the internal geometry object."""
        return self._container.geometry

    def create_branch_from_point(
        self, start_x: int, start_y: int, end_x: int, end_y: int
    ) -> None:
        """Create a new branch from an existing point.

        This method delegates to the internal LineContainer's branch creation
        functionality.

        Args:
            start_x: X coordinate of branch start point
            start_y: Y coordinate of branch start point
            end_x: X coordinate of branch end point
            end_y: Y coordinate of branch end point
        """
        self._container.create_branch_from_point(start_x, start_y, end_x, end_y)

    def get_line_container(self) -> LineContainer:
        """Get the internal LineContainer instance.
        
        This method provides access to the underlying LineContainer for
        cases where direct access to the unified implementation is needed.
        
        Returns:
            The internal LineContainer instance
        """
        return self._container
