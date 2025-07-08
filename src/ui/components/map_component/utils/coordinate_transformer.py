from typing import Tuple, Optional
from PyQt6.QtCore import QPoint


class CoordinateTransformer:
    """Utility class for coordinate transformations in map components."""

    @staticmethod
    def widget_to_scaled_coordinates(
        widget_pos: QPoint, pixmap, widget_width: int, widget_height: int
    ) -> Optional[Tuple[int, int]]:
        """Convert widget position to scaled image coordinates.

        Args:
            widget_pos: Position in widget coordinates
            pixmap: Current pixmap being displayed
            widget_width: Width of the widget
            widget_height: Height of the widget

        Returns:
            Tuple of (scaled_x, scaled_y) or None if outside image bounds
        """
        # Get image display parameters
        pixmap_size = pixmap.size()
        
        # Calculate centering offsets
        offset_x, offset_y = CoordinateTransformer.calculate_centering_offsets(
            widget_width, widget_height, pixmap_size.width(), pixmap_size.height()
        )

        # Calculate image-relative position
        scaled_x = widget_pos.x() - offset_x
        scaled_y = widget_pos.y() - offset_y

        # Check if within image bounds
        if not CoordinateTransformer.is_within_image_bounds(scaled_x, scaled_y, pixmap_size):
            return None

        return scaled_x, scaled_y

    @staticmethod
    def calculate_centering_offsets(
        widget_width: int, widget_height: int, image_width: int, image_height: int
    ) -> Tuple[int, int]:
        """Calculate offsets for centering image in widget.

        Args:
            widget_width: Width of the widget
            widget_height: Height of the widget
            image_width: Width of the displayed image
            image_height: Height of the displayed image

        Returns:
            Tuple of (offset_x, offset_y)
        """
        offset_x = max(0, (widget_width - image_width) // 2)
        offset_y = max(0, (widget_height - image_height) // 2)
        return offset_x, offset_y

    @staticmethod
    def is_within_image_bounds(
        scaled_x: int, scaled_y: int, pixmap_size
    ) -> bool:
        """Check if scaled coordinates are within image bounds.

        Args:
            scaled_x: X coordinate in scaled image space
            scaled_y: Y coordinate in scaled image space
            pixmap_size: Size of the current pixmap

        Returns:
            True if coordinates are within bounds, False otherwise
        """
        return (
            0 <= scaled_x < pixmap_size.width() 
            and 0 <= scaled_y < pixmap_size.height()
        )

    @staticmethod
    def scaled_to_original_coordinates(
        scaled_x: int, scaled_y: int, pixmap, original_pixmap=None, current_scale: float = 1.0
    ) -> Tuple[int, int]:
        """Convert scaled image coordinates to original image coordinates.

        Args:
            scaled_x: X coordinate in scaled image space
            scaled_y: Y coordinate in scaled image space
            pixmap: Current pixmap being displayed
            original_pixmap: Original pixmap (if available)
            current_scale: Current scale factor (fallback)

        Returns:
            Tuple of (original_x, original_y)
        """
        # Use original pixmap if available
        if original_pixmap is not None:
            return CoordinateTransformer.convert_using_original_dimensions(
                scaled_x, scaled_y, pixmap, original_pixmap
            )
        else:
            return CoordinateTransformer.convert_using_scale_fallback(
                scaled_x, scaled_y, current_scale
            )

    @staticmethod
    def convert_using_original_dimensions(
        scaled_x: int, scaled_y: int, pixmap, original_pixmap
    ) -> Tuple[int, int]:
        """Convert coordinates using original pixmap dimensions.

        Args:
            scaled_x: X coordinate in scaled image space
            scaled_y: Y coordinate in scaled image space
            pixmap: Current pixmap being displayed
            original_pixmap: Original pixmap

        Returns:
            Tuple of (original_x, original_y)
        """
        # Get original image dimensions
        original_width = original_pixmap.width()
        original_height = original_pixmap.height()

        # Calculate scaling ratios
        x_ratio, y_ratio = CoordinateTransformer.calculate_scaling_ratios(
            original_width, original_height, pixmap.size()
        )

        # Convert to original coordinates using the ratios
        original_x = int(scaled_x * x_ratio)
        original_y = int(scaled_y * y_ratio)

        return original_x, original_y

    @staticmethod
    def calculate_scaling_ratios(
        original_width: int, original_height: int, pixmap_size
    ) -> Tuple[float, float]:
        """Calculate scaling ratios between original and current image dimensions.

        Args:
            original_width: Width of original image
            original_height: Height of original image
            pixmap_size: Size of current pixmap

        Returns:
            Tuple of (x_ratio, y_ratio)
        """
        x_ratio = original_width / pixmap_size.width()
        y_ratio = original_height / pixmap_size.height()
        return x_ratio, y_ratio

    @staticmethod
    def convert_using_scale_fallback(
        scaled_x: int, scaled_y: int, current_scale: float
    ) -> Tuple[int, int]:
        """Convert coordinates using current scale as fallback method.

        Args:
            scaled_x: X coordinate in scaled image space
            scaled_y: Y coordinate in scaled image space
            current_scale: Current scale factor

        Returns:
            Tuple of (original_x, original_y)
        """
        original_x = int(scaled_x / current_scale)
        original_y = int(scaled_y / current_scale)
        return original_x, original_y

    @staticmethod
    def widget_to_original_coordinates(
        widget_pos: QPoint, pixmap, widget_width: int, widget_height: int,
        original_pixmap=None, current_scale: float = 1.0
    ) -> Optional[Tuple[int, int]]:
        """Convert widget position directly to original image coordinates.

        Args:
            widget_pos: Position in widget coordinates
            pixmap: Current pixmap being displayed
            widget_width: Width of the widget
            widget_height: Height of the widget
            original_pixmap: Original pixmap (if available)
            current_scale: Current scale factor (fallback)

        Returns:
            Tuple of (original_x, original_y) or None if outside image
        """
        # Convert widget position to scaled image coordinates
        scaled_coords = CoordinateTransformer.widget_to_scaled_coordinates(
            widget_pos, pixmap, widget_width, widget_height
        )
        if scaled_coords is None:
            return None

        scaled_x, scaled_y = scaled_coords

        # Convert scaled coordinates to original image coordinates
        return CoordinateTransformer.scaled_to_original_coordinates(
            scaled_x, scaled_y, pixmap, original_pixmap, current_scale
        )

    @staticmethod
    def original_to_widget_coordinates(
        original_x: int, original_y: int, pixmap, widget_width: int, widget_height: int,
        original_pixmap=None, current_scale: float = 1.0
    ) -> Optional[Tuple[int, int]]:
        """Convert original image coordinates to widget position.

        Args:
            original_x: X coordinate in original image space
            original_y: Y coordinate in original image space
            pixmap: Current pixmap being displayed
            widget_width: Width of the widget
            widget_height: Height of the widget
            original_pixmap: Original pixmap (if available)
            current_scale: Current scale factor (fallback)

        Returns:
            Tuple of (widget_x, widget_y) or None if outside bounds
        """
        # For logging
        import logging
        logger = logging.getLogger(__name__)
        logger.debug(f"Converting original coordinates ({original_x}, {original_y}) to widget coordinates")
        logger.debug(f"Widget dimensions: {widget_width}x{widget_height}, scale: {current_scale}")
        
        if original_pixmap:
            logger.debug(f"Original pixmap size: {original_pixmap.width()}x{original_pixmap.height()}")
        else:
            logger.debug("No original pixmap provided")
            
        if pixmap:
            logger.debug(f"Current pixmap size: {pixmap.width()}x{pixmap.height()}")
        else:
            logger.debug("No current pixmap provided")

        # Convert original coordinates to scaled coordinates
        scaled_x, scaled_y = CoordinateTransformer.original_to_scaled_coordinates(
            original_x, original_y, pixmap, original_pixmap, current_scale
        )
        logger.debug(f"Scaled coordinates: ({scaled_x}, {scaled_y})")

        # Calculate centering offsets
        pixmap_size = pixmap.size()
        offset_x, offset_y = CoordinateTransformer.calculate_centering_offsets(
            widget_width, widget_height, pixmap_size.width(), pixmap_size.height()
        )
        logger.debug(f"Centering offsets: ({offset_x}, {offset_y})")

        # Convert scaled coordinates to widget coordinates
        widget_x = int(scaled_x + offset_x)
        widget_y = int(scaled_y + offset_y)
        logger.debug(f"Widget coordinates: ({widget_x}, {widget_y})")

        # Check if within widget bounds
        if not (0 <= widget_x < widget_width and 0 <= widget_y < widget_height):
            logger.debug(f"Widget coordinates outside bounds - returning None")
            return None

        return widget_x, widget_y

    @staticmethod
    def original_to_scaled_coordinates(
        original_x: int, original_y: int, pixmap, original_pixmap=None, current_scale: float = 1.0
    ) -> Tuple[int, int]:
        """Convert original image coordinates to scaled image coordinates.

        Args:
            original_x: X coordinate in original image space
            original_y: Y coordinate in original image space
            pixmap: Current pixmap being displayed
            original_pixmap: Original pixmap (if available)
            current_scale: Current scale factor (fallback)

        Returns:
            Tuple of (scaled_x, scaled_y)
        """
        # Use original pixmap if available
        if original_pixmap is not None:
            # Get original image dimensions
            original_width = original_pixmap.width()
            original_height = original_pixmap.height()

            # Calculate scaling ratios (inverse of scaled_to_original)
            x_ratio, y_ratio = CoordinateTransformer.calculate_scaling_ratios(
                original_width, original_height, pixmap.size()
            )

            # Convert to scaled coordinates using the inverse ratios
            scaled_x = int(original_x / x_ratio)
            scaled_y = int(original_y / y_ratio)
        else:
            # Use scale factor as fallback
            scaled_x = int(original_x * current_scale)
            scaled_y = int(original_y * current_scale)

        return scaled_x, scaled_y