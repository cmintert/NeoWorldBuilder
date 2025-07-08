"""Test integration for Phase 1 graphics foundation."""

import sys
from pathlib import Path

from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QPushButton, QFileDialog
from PyQt6.QtCore import Qt

from .map_graphics_view import MapGraphicsView
from .map_graphics_scene import MapGraphicsScene
from .graphics_feature_manager import GraphicsFeatureManager


class TestGraphicsWindow(QMainWindow):
    """Test window for graphics integration."""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Graphics Map Test - Phase 1")
        self.setGeometry(100, 100, 1200, 800)
        
        # Create central widget
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        
        # Create graphics components
        self.scene = MapGraphicsScene()
        self.view = MapGraphicsView()
        self.view.set_scene(self.scene)
        self.feature_manager = GraphicsFeatureManager(self.scene)
        
        # Add view to layout
        layout.addWidget(self.view)
        
        # Add test controls
        controls = QWidget()
        controls_layout = QVBoxLayout(controls)
        
        load_btn = QPushButton("Load Image")
        load_btn.clicked.connect(self.load_test_image)
        controls_layout.addWidget(load_btn)
        
        fit_btn = QPushButton("Fit Image")
        fit_btn.clicked.connect(self.view.fit_image_in_view)
        controls_layout.addWidget(fit_btn)
        
        test_coords_btn = QPushButton("Test Coordinates")
        test_coords_btn.clicked.connect(self.test_coordinates)
        controls_layout.addWidget(test_coords_btn)
        
        layout.addWidget(controls)
        
        # Connect signals for testing
        self.view.coordinates_changed.connect(self.on_coordinates_changed)
        self.view.click_at_coordinates.connect(self.on_click)
        self.scene.image_loaded.connect(self.on_image_loaded)
        
        self.statusBar().showMessage("Ready")
    
    def load_test_image(self):
        """Load a test image."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Map Image", "", "Images (*.png *.jpg *.jpeg)"
        )
        if file_path:
            success = self.scene.load_map_image(file_path)
            if success:
                self.statusBar().showMessage(f"Loaded: {Path(file_path).name}")
            else:
                self.statusBar().showMessage("Failed to load image")
    
    def test_coordinates(self):
        """Test coordinate conversions."""
        if self.scene.image_width > 0:
            # Test some conversions
            test_x, test_y = 100, 100
            scene_point = self.scene.original_to_scene_coords(test_x, test_y)
            back_x, back_y = self.scene.scene_to_original_coords(scene_point)
            
            print(f"Coordinate test: ({test_x}, {test_y}) -> {scene_point} -> ({back_x}, {back_y})")
            self.statusBar().showMessage(f"Coord test: ({test_x},{test_y}) -> ({back_x},{back_y})")
    
    def on_coordinates_changed(self, x: int, y: int):
        """Handle coordinate updates."""
        self.statusBar().showMessage(f"Mouse at: ({x}, {y})")
    
    def on_click(self, x: int, y: int):
        """Handle clicks."""
        print(f"Clicked at: ({x}, {y})")
        # Test adding features (placeholders for now)
        self.feature_manager.add_pin_feature(f"test_pin_{x}_{y}", x, y)
    
    def on_image_loaded(self, path: str, width: int, height: int):
        """Handle image loaded."""
        print(f"Image loaded: {path} ({width}x{height})")


def run_test():
    """Run the test application."""
    app = QApplication(sys.argv)
    window = TestGraphicsWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    run_test()