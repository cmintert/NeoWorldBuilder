import os
from typing import Optional, Dict

from PyQt6.QtCore import QThread, pyqtSignal, QTimer, Qt
from PyQt6.QtGui import QPixmap, QTransform

from structlog import get_logger

logger = get_logger(__name__)


class MapImageLoader(QThread):
    """Thread for loading map images asynchronously.

    Handles image loading in background to prevent UI freezing.
    """

    loaded = pyqtSignal(QPixmap)
    error = pyqtSignal(str)

    def __init__(self, image_path: str):
        """Initialize the map image loader.

        Args:
            image_path: Path to the image file to load.
        """
        super().__init__()
        self.image_path = image_path

    def run(self):
        """Load the image and emit appropriate signal."""
        try:
            if not os.path.exists(self.image_path):
                self.error.emit(f"Image file not found: {self.image_path}")
                return
                
            pixmap = QPixmap(self.image_path)
            if pixmap.isNull():
                self.error.emit(f"Failed to load image: {self.image_path}")
                return
                
            self.loaded.emit(pixmap)
            logger.debug(f"Successfully loaded image: {self.image_path}")
            
        except Exception as e:
            self.error.emit(f"Error loading image: {str(e)}")
            logger.error(f"Image loading failed: {e}")


class ImageManager:
    """Manages map image loading, caching, and scaling operations."""
    
    def __init__(self):
        """Initialize the image manager."""
        self.current_image_path: Optional[str] = None
        self.original_pixmap: Optional[QPixmap] = None
        self.current_scale = 1.0
        self._pixmap_cache: Dict[str, QPixmap] = {}
        self.current_loader: Optional[MapImageLoader] = None
        
    def load_image(self, image_path: Optional[str], success_callback, error_callback) -> None:
        """Load an image asynchronously.
        
        Args:
            image_path: Path to image file or None to clear
            success_callback: Callback for successful load (receives QPixmap)
            error_callback: Callback for load errors (receives error message)
        """
        self.current_image_path = image_path
        
        # Handle clearing image
        if not image_path:
            self.original_pixmap = None
            success_callback(QPixmap())  # Empty pixmap signals clear
            return
        
        # Check cache first
        if image_path in self._pixmap_cache:
            pixmap = self._pixmap_cache[image_path]
            self.original_pixmap = pixmap
            success_callback(pixmap)
            logger.debug(f"Loaded image from cache: {image_path}")
            return
        
        # Load asynchronously
        self.current_loader = MapImageLoader(image_path)
        
        def on_loaded(pixmap: QPixmap):
            self._pixmap_cache[image_path] = pixmap
            self.original_pixmap = pixmap
            success_callback(pixmap)
        
        def on_error(error_msg: str):
            logger.error(f"Failed to load image: {error_msg}")
            error_callback(error_msg)
        
        self.current_loader.loaded.connect(on_loaded)
        self.current_loader.error.connect(on_error)
        self.current_loader.start()
    
    def get_scaled_pixmap(self, scale: float) -> Optional[QPixmap]:
        """Get the current image scaled to the specified factor.
        
        Args:
            scale: Scale factor to apply
            
        Returns:
            Scaled QPixmap or None if no image loaded
        """
        if not self.original_pixmap:
            return None
            
        if scale == 1.0:
            return self.original_pixmap
            
        self.current_scale = scale
        
        # Create scaled pixmap
        scaled_pixmap = self.original_pixmap.transformed(
            QTransform().scale(scale, scale),
            Qt.TransformationMode.SmoothTransformation,
        )
        
        return scaled_pixmap
    
    def calculate_fit_to_width_scale(self, viewport_width: int) -> float:
        """Calculate scale to fit image to viewport width.
        
        Args:
            viewport_width: Width of the viewport
            
        Returns:
            Scale factor to fit width
        """
        if not self.original_pixmap:
            return 1.0
            
        image_width = self.original_pixmap.width()
        if image_width <= 0:
            return 1.0
            
        return viewport_width / image_width
    
    def get_image_info(self) -> Dict[str, any]:
        """Get information about the current image.
        
        Returns:
            Dictionary with image information
        """
        if not self.original_pixmap:
            return {"loaded": False}
            
        return {
            "loaded": True,
            "path": self.current_image_path,
            "width": self.original_pixmap.width(),
            "height": self.original_pixmap.height(),
            "current_scale": self.current_scale
        }
    
    def clear_cache(self) -> None:
        """Clear the image cache."""
        self._pixmap_cache.clear()
        logger.debug("Image cache cleared")
    
    def get_cache_size(self) -> int:
        """Get number of images in cache.
        
        Returns:
            Number of cached images
        """
        return len(self._pixmap_cache)
