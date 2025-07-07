"""Test pin graphics implementation for Phase 2."""

import sys
from pathlib import Path

from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QPushButton, QHBoxLayout, QLabel
from PyQt6.QtCore import Qt

from .map_graphics_view import MapGraphicsView
from .map_graphics_scene import MapGraphicsScene
from .graphics_feature_manager import GraphicsFeatureManager
from .pin_graphics_item import PinGraphicsItem


class TestPinWindow(QMainWindow):
    """Test window for pin graphics implementation."""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Pin Graphics Test - Phase 2")
        self.setGeometry(100, 100, 1200, 900)
        
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
        controls_layout = QHBoxLayout(controls)
        
        # Image controls
        load_btn = QPushButton("Load Test Image")
        load_btn.clicked.connect(self.load_test_image)
        controls_layout.addWidget(load_btn)
        
        # Pin controls
        add_pin_btn = QPushButton("Add Test Pin")
        add_pin_btn.clicked.connect(self.add_test_pin)
        controls_layout.addWidget(add_pin_btn)
        
        edit_mode_btn = QPushButton("Toggle Edit Mode")
        edit_mode_btn.clicked.connect(self.toggle_edit_mode)
        controls_layout.addWidget(edit_mode_btn)
        
        clear_btn = QPushButton("Clear Pins")
        clear_btn.clicked.connect(self.clear_pins)
        controls_layout.addWidget(clear_btn)
        
        # Info label
        self.info_label = QLabel("Click 'Load Test Image' to start")
        controls_layout.addWidget(self.info_label)
        
        layout.addWidget(controls)
        
        # Test state
        self.pin_counter = 0
        self.edit_mode = False
        
        # Connect signals for testing
        self.view.click_at_coordinates.connect(self.on_click)
        self.scene.image_loaded.connect(self.on_image_loaded)
        self.feature_manager.signal_bridge.pin_clicked.connect(self.on_pin_clicked)
        self.feature_manager.signal_bridge.pin_moved.connect(self.on_pin_moved)
        
        self.statusBar().showMessage("Ready - Phase 2 Pin Test")
    
    def load_test_image(self):
        """Load a test image or create a simple test scene."""
        # For testing, create a simple colored background
        from PyQt6.QtGui import QPixmap, QPainter, QColor
        
        # Create a test image
        pixmap = QPixmap(800, 600)
        pixmap.fill(QColor(100, 150, 200))
        
        painter = QPainter(pixmap)
        painter.setPen(QColor(255, 255, 255))
        painter.drawText(50, 50, "Test Map - Click to Add Pins")
        painter.drawRect(10, 10, 780, 580)
        painter.end()
        
        # Add to scene
        if self.scene.background_item:
            self.scene.removeItem(self.scene.background_item)
        
        self.scene.background_item = self.scene.addPixmap(pixmap)
        self.scene.background_item.setZValue(-1000)
        self.scene.setSceneRect(0, 0, 800, 600)
        self.scene.image_width = 800
        self.scene.image_height = 600
        
        self.view.fit_image_in_view()
        self.info_label.setText("Test map loaded. Click to add pins.")
        self.statusBar().showMessage("Test image created (800x600)")
    
    def add_test_pin(self):
        """Add a test pin at a random location."""
        import random
        x = random.randint(50, 750)
        y = random.randint(50, 550)
        
        self.pin_counter += 1
        pin_name = f"TestPin_{self.pin_counter}"
        
        self.feature_manager.add_pin_feature(pin_name, x, y)
        self.info_label.setText(f"Added {pin_name} at ({x}, {y})")
        self.statusBar().showMessage(f"Pin added: {pin_name}")
    
    def toggle_edit_mode(self):
        """Toggle edit mode on all pins."""
        self.edit_mode = not self.edit_mode
        self.feature_manager.set_edit_mode(self.edit_mode)
        
        mode_text = "ENABLED" if self.edit_mode else "DISABLED"
        self.info_label.setText(f"Edit mode {mode_text}")
        self.statusBar().showMessage(f"Edit mode: {mode_text}")
    
    def clear_pins(self):
        """Clear all pins from the scene."""
        self.feature_manager.clear_all_features()
        self.pin_counter = 0
        self.info_label.setText("All pins cleared")
        self.statusBar().showMessage("Pins cleared")
    
    def on_click(self, x: int, y: int):
        """Handle click events."""
        if self.scene.image_width > 0:  # Only if image is loaded
            self.pin_counter += 1
            pin_name = f"ClickPin_{self.pin_counter}"
            
            self.feature_manager.add_pin_feature(pin_name, x, y)
            self.info_label.setText(f"Click-added {pin_name} at ({x}, {y})")
    
    def on_image_loaded(self, path: str, width: int, height: int):
        """Handle image loaded."""
        print(f"Image loaded: {path} ({width}x{height})")
    
    def on_pin_clicked(self, node_name: str):
        """Handle pin click signals."""
        self.info_label.setText(f"Pin clicked: {node_name}")
        self.statusBar().showMessage(f"Pin clicked: {node_name}")
        print(f"Pin clicked: {node_name}")
    
    def on_pin_moved(self, node_name: str, x: int, y: int):
        """Handle pin move signals."""
        self.info_label.setText(f"Pin moved: {node_name} to ({x}, {y})")
        self.statusBar().showMessage(f"Pin moved: {node_name}")
        print(f"Pin moved: {node_name} to ({x}, {y})")


def run_pin_test():
    """Run the pin test application."""
    app = QApplication(sys.argv)
    window = TestPinWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    run_pin_test()