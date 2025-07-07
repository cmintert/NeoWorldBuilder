"""Test line graphics implementation for Phase 3."""

import sys
from typing import List, Tuple
from pathlib import Path

from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QPushButton, QHBoxLayout, QLabel
from PyQt6.QtCore import Qt

from .map_graphics_view import MapGraphicsView
from .map_graphics_scene import MapGraphicsScene
from .graphics_feature_manager import GraphicsFeatureManager
from .line_graphics_item import LineGraphicsItem


class TestLineWindow(QMainWindow):
    """Test window for line graphics implementation."""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Line Graphics Test - Phase 3")
        self.setGeometry(100, 100, 1400, 1000)
        
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
        
        # Row 1: Basic controls
        row1 = QWidget()
        row1_layout = QHBoxLayout(row1)
        
        load_btn = QPushButton("Load Test Image")
        load_btn.clicked.connect(self.load_test_image)
        row1_layout.addWidget(load_btn)
        
        simple_line_btn = QPushButton("Add Simple Line")
        simple_line_btn.clicked.connect(self.add_simple_line)
        row1_layout.addWidget(simple_line_btn)
        
        complex_line_btn = QPushButton("Add Complex Line")
        complex_line_btn.clicked.connect(self.add_complex_line)
        row1_layout.addWidget(complex_line_btn)
        
        branching_line_btn = QPushButton("Add Branching Line")
        branching_line_btn.clicked.connect(self.add_branching_line)
        row1_layout.addWidget(branching_line_btn)
        
        controls_layout.addWidget(row1)
        
        # Row 2: Mode controls
        row2 = QWidget()
        row2_layout = QHBoxLayout(row2)
        
        edit_mode_btn = QPushButton("Toggle Edit Mode")
        edit_mode_btn.clicked.connect(self.toggle_edit_mode)
        row2_layout.addWidget(edit_mode_btn)
        
        clear_btn = QPushButton("Clear Lines")
        clear_btn.clicked.connect(self.clear_lines)
        row2_layout.addWidget(clear_btn)
        
        test_all_btn = QPushButton("Test All Features")
        test_all_btn.clicked.connect(self.test_all_features)
        row2_layout.addWidget(test_all_btn)
        
        controls_layout.addWidget(row2)
        
        # Info label
        self.info_label = QLabel("Click 'Load Test Image' to start testing line features")
        controls_layout.addWidget(self.info_label)
        
        layout.addWidget(controls)
        
        # Test state
        self.line_counter = 0
        self.edit_mode = False
        
        # Connect signals for testing
        self.view.click_at_coordinates.connect(self.on_click)
        self.scene.image_loaded.connect(self.on_image_loaded)
        self.feature_manager.signal_bridge.line_clicked.connect(self.on_line_clicked)
        self.feature_manager.signal_bridge.line_geometry_changed.connect(self.on_geometry_changed)
        
        self.statusBar().showMessage("Ready - Phase 3 Line Test")
    
    def load_test_image(self):
        """Load a test image or create a simple test scene."""
        from PyQt6.QtGui import QPixmap, QPainter, QColor, QPen
        
        # Create a test image with grid
        pixmap = QPixmap(1000, 800)
        pixmap.fill(QColor(240, 240, 250))
        
        painter = QPainter(pixmap)
        
        # Draw grid
        painter.setPen(QPen(QColor(200, 200, 220), 1))
        for x in range(0, 1000, 50):
            painter.drawLine(x, 0, x, 800)
        for y in range(0, 800, 50):
            painter.drawLine(0, y, 1000, y)
        
        # Draw main axes
        painter.setPen(QPen(QColor(150, 150, 180), 2))
        painter.drawLine(500, 0, 500, 800)  # Vertical center
        painter.drawLine(0, 400, 1000, 400)  # Horizontal center
        
        # Add labels
        painter.setPen(QColor(50, 50, 100))
        painter.drawText(50, 50, "Line Graphics Test - Phase 3")
        painter.drawText(50, 80, "Grid: 50px spacing")
        painter.drawText(50, 110, "Test different line types and edit mode")
        
        painter.end()
        
        # Add to scene
        if self.scene.background_item:
            self.scene.removeItem(self.scene.background_item)
        
        self.scene.background_item = self.scene.addPixmap(pixmap)
        self.scene.background_item.setZValue(-1000)
        self.scene.setSceneRect(0, 0, 1000, 800)
        self.scene.image_width = 1000
        self.scene.image_height = 800
        
        self.view.fit_image_in_view()
        self.info_label.setText("Test map loaded. Try different line creation buttons.")
        self.statusBar().showMessage("Test image created (1000x800)")
    
    def add_simple_line(self):
        """Add a simple straight line."""
        self.line_counter += 1
        line_name = f"SimpleLine_{self.line_counter}"
        
        # Create a simple diagonal line
        points = [(200, 200), (400, 300)]
        
        self.feature_manager.add_line_feature(line_name, points)
        self.info_label.setText(f"Added {line_name} with {len(points)} points")
        self.statusBar().showMessage(f"Simple line added: {line_name}")
    
    def add_complex_line(self):
        """Add a complex multi-segment line."""
        self.line_counter += 1
        line_name = f"ComplexLine_{self.line_counter}"
        
        # Create a zigzag line
        points = [
            (100, 150),
            (200, 250),
            (300, 150),
            (400, 250),
            (500, 150),
            (600, 250),
            (700, 150)
        ]
        
        self.feature_manager.add_line_feature(line_name, points)
        self.info_label.setText(f"Added {line_name} with {len(points)} points")
        self.statusBar().showMessage(f"Complex line added: {line_name}")
    
    def add_branching_line(self):
        """Add a branching line with multiple branches."""
        self.line_counter += 1
        line_name = f"BranchingLine_{self.line_counter}"
        
        # Create a Y-shaped branching line
        branches = [
            [(500, 600), (500, 500), (500, 400)],  # Main stem
            [(500, 400), (400, 300)],               # Left branch
            [(500, 400), (600, 300)]                # Right branch
        ]
        
        self.feature_manager.add_branching_line_feature(line_name, branches)
        self.info_label.setText(f"Added {line_name} with {len(branches)} branches")
        self.statusBar().showMessage(f"Branching line added: {line_name}")
    
    def toggle_edit_mode(self):
        """Toggle edit mode on all lines."""
        self.edit_mode = not self.edit_mode
        self.feature_manager.set_edit_mode(self.edit_mode)
        
        mode_text = "ENABLED" if self.edit_mode else "DISABLED"
        self.info_label.setText(f"Edit mode {mode_text} - {'Drag control points' if self.edit_mode else 'Click lines to select'}")
        self.statusBar().showMessage(f"Edit mode: {mode_text}")
    
    def clear_lines(self):
        """Clear all lines from the scene."""
        self.feature_manager.clear_all_features()
        self.line_counter = 0
        self.info_label.setText("All lines cleared")
        self.statusBar().showMessage("Lines cleared")
    
    def test_all_features(self):
        """Test all line features systematically."""
        # Clear existing
        self.clear_lines()
        
        # Add various test lines
        test_lines = [
            ("Horizontal", [(100, 100), (300, 100)]),
            ("Vertical", [(400, 100), (400, 300)]),
            ("Diagonal", [(500, 100), (700, 300)]),
            ("Curved", [(100, 400), (150, 350), (200, 400), (250, 350), (300, 400)]),
            ("Rectangle", [(500, 400), (700, 400), (700, 600), (500, 600), (500, 400)]),
        ]
        
        for name, points in test_lines:
            self.feature_manager.add_line_feature(f"Test_{name}", points)
        
        # Add a branching line
        star_branches = [
            [(400, 500), (400, 450)],  # Top
            [(400, 500), (450, 500)],  # Right
            [(400, 500), (400, 550)],  # Bottom
            [(400, 500), (350, 500)]   # Left
        ]
        self.feature_manager.add_branching_line_feature("Test_Star", star_branches)
        
        self.info_label.setText("All test features created. Toggle edit mode to test interaction.")
        self.statusBar().showMessage("Comprehensive test completed")
    
    def on_click(self, x: int, y: int):
        """Handle click events."""
        if self.scene.image_width > 0 and not self.edit_mode:
            # In non-edit mode, create a simple line from click
            self.line_counter += 1
            line_name = f"ClickLine_{self.line_counter}"
            
            # Create a small cross at click point
            points = [
                (x - 20, y),
                (x + 20, y),
                (x, y - 20),
                (x, y + 20)
            ]
            
            # Note: This creates 4 separate line segments, not a connected path
            # For a connected cross, we'd need a branching line
            self.feature_manager.add_line_feature(line_name, [(x - 20, y), (x + 20, y)])
            self.info_label.setText(f"Click-added {line_name} at ({x}, {y})")
    
    def on_image_loaded(self, path: str, width: int, height: int):
        """Handle image loaded."""
        print(f"Image loaded: {path} ({width}x{height})")
    
    def on_line_clicked(self, node_name: str):
        """Handle line click signals."""
        line_item = self.feature_manager.get_feature(node_name)
        if line_item:
            geometry = line_item.get_geometry_data()
            if isinstance(geometry[0], list):  # Branching line
                point_count = sum(len(branch) for branch in geometry)
                self.info_label.setText(f"Line clicked: {node_name} (branching, {point_count} total points)")
            else:  # Simple line
                self.info_label.setText(f"Line clicked: {node_name} ({len(geometry)} points)")
        else:
            self.info_label.setText(f"Line clicked: {node_name}")
        
        self.statusBar().showMessage(f"Line clicked: {node_name}")
        print(f"Line clicked: {node_name}")
    
    def on_geometry_changed(self, node_name: str, geometry: List):
        """Handle line geometry change signals."""
        if isinstance(geometry, list) and geometry and isinstance(geometry[0], list):
            # Branching line
            point_count = sum(len(branch) for branch in geometry)
            self.info_label.setText(f"Geometry changed: {node_name} (branching, {point_count} total points)")
        else:
            # Simple line
            point_count = len(geometry) if geometry else 0
            self.info_label.setText(f"Geometry changed: {node_name} ({point_count} points)")
        
        self.statusBar().showMessage(f"Geometry updated: {node_name}")
        print(f"Line geometry changed: {node_name}, new geometry: {geometry}")


def run_line_test():
    """Run the line test application."""
    app = QApplication(sys.argv)
    window = TestLineWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    run_line_test()