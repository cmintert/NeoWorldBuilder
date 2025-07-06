"""Branching line container for map component.

This module provides the BranchingLineContainer class for handling branching line features
in the map component. It serves as a specialized container that leverages the unified
LineContainer implementation for branching line functionality.
"""

from typing import List, Tuple, Any, Optional

from PyQt6.QtWidgets import QWidget

from .line_container import LineContainer


class BranchingLineContainer(LineContainer):
    """Container widget for branching lines.

    This container inherits from LineContainer (which already inherits from
    BaseMapFeatureContainer), providing a clean inheritance hierarchy while
    maintaining architectural consistency.

    By inheriting directly from LineContainer, we eliminate the complexity
    of maintaining two separate widget hierarchies and delegate patterns,
    while still satisfying the requirement to inherit from BaseMapFeatureContainer
    (indirectly through LineContainer).
    """

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
        # Initialize with branching line data through LineContainer's constructor
        # LineContainer already inherits from BaseMapFeatureContainer, so this
        # satisfies the architectural requirement
        super().__init__(target_node, branches, parent, config)

        # No need to create a separate internal container or handle complex delegation
        # since we're directly inheriting all functionality from LineContainer


    def create_branch_from_point(
        self, start_x: int, start_y: int, end_x: int, end_y: int
    ) -> None:
        """Create a new branch from an existing point.

        Implements the branch creation functionality directly through the parent class.

        Args:
            start_x: X coordinate of branch start point
            start_y: Y coordinate of branch start point
            end_x: X coordinate of branch end point
            end_y: Y coordinate of branch end point
        """
        # Call the parent class implementation directly
        super().create_branch_from_point(start_x, start_y, end_x, end_y)

    def get_line_container(self) -> LineContainer:
        """Get the line container instance.

        For backward compatibility with code that expects a separate container.
        Since BranchingLineContainer now directly inherits from LineContainer,
        this method simply returns self.

        Returns:
            The container instance (self)
        """
        return self
