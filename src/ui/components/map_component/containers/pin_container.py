import os
from PyQt6.QtCore import Qt, pyqtSignal, QSize, QPoint
from PyQt6.QtGui import QMouseEvent, QCursor
from PyQt6.QtSvgWidgets import QSvgWidget
from PyQt6.QtWidgets import QVBoxLayout, QLabel
from utils.path_helper import get_resource_path
from ui.components.map_component.utils.coordinate_transformer import (
    CoordinateTransformer,
)
from .base_map_feature_container import BaseMapFeatureContainer


class PinContainer(BaseMapFeatureContainer):
    """Container widget that holds both a pin and its label.

    Attributes:
        pin_clicked (pyqtSignal): Signal emitted when the pin is clicked.
        position_changed (pyqtSignal): Signal emitted when pin position changes.
        pin_svg (QSvgWidget): The pin icon.
    """

    # Rename base class's feature_clicked signal for backward compatibility
    pin_clicked = pyqtSignal(str)
    position_changed = pyqtSignal(str, int, int)  # node_name, new_x, new_y

    def __init__(self, target_node: str, parent=None, config=None):
        """Initialize the pin container.

        Args:
            target_node: The node name this pin represents.
            parent: Parent widget.
            config: Configuration object with settings.
        """
        super().__init__(target_node, parent, config)

        # Drag state
        self.dragging = False
        self.drag_start_pos = QPoint()

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

        # Add widgets to layout
        layout.addWidget(self.pin_svg)
        layout.addWidget(self.text_label)

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
        # Update base class scale first
        super().set_scale(scale)

        # Then handle pin-specific scale updates
        self.update_pin_size()
        self.adjustSize()

    def set_edit_mode(self, edit_mode: bool) -> None:
        """Enable or disable edit mode for this pin.

        Args:
            edit_mode: Whether edit mode should be active.
        """
        super().set_edit_mode(edit_mode)
        # No additional behavior needed - cursor will be handled by enter/leave events

    @property
    def pin_height(self) -> int:
        """Get the height of the pin.

        Returns:
            The current height of the pin widget.
        """
        return self.pin_svg.height()

    def enterEvent(self, event) -> None:
        """Handle mouse enter events - change cursor based on edit mode."""
        super().enterEvent(event)
        if self.edit_mode:
            self.setCursor(QCursor(Qt.CursorShape.SizeAllCursor))
        else:
            self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

    def leaveEvent(self, event) -> None:
        """Handle mouse leave events - reset cursor."""
        super().leaveEvent(event)
        self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Handle mouse press events.

        Args:
            event: The mouse press event.
        """
        # Check if parent map tab is in branch creation mode - if so, ignore this event
        map_tab = self._find_map_tab()
        if map_tab and getattr(map_tab, "branch_creation_mode", False):
            event.ignore()  # Let the event pass through to parent handlers
            return

        if event.button() == Qt.MouseButton.LeftButton:
            if self.edit_mode:
                # Start dragging in edit mode
                self.dragging = True
                self.drag_start_pos = event.pos()
                print(f"Starting drag of pin {self.target_node}")
                event.accept()
                return
            else:
                # Normal click behavior
                self.pin_clicked.emit(self.target_node)
                event.accept()
                return
        
        # For non-left-click events, ignore them to allow propagation
        event.ignore()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """Handle mouse move events for pin dragging."""
        if self.dragging and self.edit_mode:
            # Calculate the new position for the pin
            new_pos = event.pos()

            # Calculate movement delta
            delta = new_pos - self.drag_start_pos

            # Get current pin position in map coordinates
            current_x = self.x() + self.width() // 2
            current_y = self.y() + self.height()  # Pin anchor is at bottom

            # Apply movement
            new_map_x = current_x + delta.x()
            new_map_y = current_y + delta.y()

            # Convert to original coordinates using coordinate transformer
            map_tab = self._find_map_tab()
            current_scale = self._scale

            if map_tab and hasattr(map_tab, "image_label"):
                current_pixmap = map_tab.image_label.pixmap()
                original_pixmap = None

                if (
                    hasattr(map_tab, "image_manager")
                    and map_tab.image_manager.original_pixmap
                ):
                    original_pixmap = map_tab.image_manager.original_pixmap

                if current_pixmap:
                    original_coords = (
                        CoordinateTransformer.scaled_to_original_coordinates(
                            new_map_x,
                            new_map_y,
                            current_pixmap,
                            original_pixmap,
                            current_scale,
                        )
                    )
                    original_x, original_y = original_coords
                else:
                    # Fallback to simple scaling if pixmap not available
                    original_x = int(new_map_x / current_scale)
                    original_y = int(new_map_y / current_scale)
            else:
                # Fallback to simple scaling if map tab not available
                original_x = int(new_map_x / current_scale)
                original_y = int(new_map_y / current_scale)

            # Move the pin widget to new position
            # Account for pin dimensions when positioning
            pin_x = new_map_x - self.width() // 2
            pin_y = new_map_y - self.height()

            self.move(int(pin_x), int(pin_y))

            print(
                f"Moving pin {self.target_node} to map({new_map_x}, {new_map_y}) -> original({original_x}, {original_y})"
            )

            # Reset drag start position for next movement
            self.drag_start_pos = new_pos

            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """Handle mouse release events to end pin dragging."""
        if event.button() == Qt.MouseButton.LeftButton and self.dragging:
            print(f"Finished dragging pin {self.target_node}")

            # Get final position and emit signal for database update
            final_x = self.x() + self.width() // 2
            final_y = self.y() + self.height()

            # Convert to original coordinates
            map_tab = self._find_map_tab()
            current_scale = self._scale

            if map_tab and hasattr(map_tab, "image_label"):
                current_pixmap = map_tab.image_label.pixmap()
                original_pixmap = None

                if (
                    hasattr(map_tab, "image_manager")
                    and map_tab.image_manager.original_pixmap
                ):
                    original_pixmap = map_tab.image_manager.original_pixmap

                if current_pixmap:
                    original_coords = (
                        CoordinateTransformer.scaled_to_original_coordinates(
                            final_x,
                            final_y,
                            current_pixmap,
                            original_pixmap,
                            current_scale,
                        )
                    )
                    original_x, original_y = original_coords
                else:
                    # Fallback to simple scaling
                    original_x = int(final_x / current_scale)
                    original_y = int(final_y / current_scale)
            else:
                # Fallback to simple scaling
                original_x = int(final_x / current_scale)
                original_y = int(final_y / current_scale)

            # Emit position changed signal
            self.position_changed.emit(self.target_node, original_x, original_y)

            # Update position in relationship table
            controller = self._find_controller()
            if (
                controller
                and hasattr(controller, "ui")
                and hasattr(controller.ui, "relationships_table")
            ):
                try:
                    import json
                    from utils.geometry_handler import GeometryHandler

                    relationships_table = controller.ui.relationships_table

                    # Find the SHOWS relationship for this pin
                    for row in range(relationships_table.rowCount()):
                        rel_type_item = relationships_table.item(row, 0)
                        target_item = relationships_table.item(row, 1)
                        props_item = relationships_table.item(row, 3)

                        if (
                            rel_type_item
                            and rel_type_item.text() == "SHOWS"
                            and target_item
                            and props_item
                        ):

                            # Extract target node from the target item
                            target_text = target_item.text()
                            if " -> " in target_text:
                                target_node = target_text.split(" -> ")[1]
                            else:
                                target_node = target_text

                            if target_node == self.target_node:
                                # Update the properties with new position
                                properties = json.loads(props_item.text())

                                # Create new Point geometry with updated coordinates
                                wkt_point = GeometryHandler.create_point(
                                    original_x, original_y
                                )
                                properties["geometry"] = wkt_point
                                properties["geometry_type"] = "Point"

                                # Update the table item
                                props_item.setText(json.dumps(properties))
                                print(
                                    f"Updated pin {self.target_node} position in relationship table: ({original_x}, {original_y})"
                                )

                                # Note: User needs to manually save to persist changes
                                break

                except Exception as e:
                    print(f"Error updating pin position in relationship table: {e}")

            # Reset drag state
            self.dragging = False
            self.drag_start_pos = QPoint()

            event.accept()
        else:
            super().mouseReleaseEvent(event)
