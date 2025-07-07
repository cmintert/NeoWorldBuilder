"""Full integration test for Phase 4 - Graphics Mode Live Testing."""

import sys
from pathlib import Path

from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QPushButton, QHBoxLayout, QLabel, QTextEdit
from PyQt6.QtCore import Qt

# Import the actual MapTab to test integration
from ui.components.map_component.map_tab import MapTab


class TestIntegrationWindow(QMainWindow):
    """Test window for full graphics mode integration."""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Phase 4 Integration Test - Live Graphics Mode")
        self.setGeometry(100, 100, 1600, 1000)
        
        # Create central widget
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        
        # Create info area
        info_layout = QHBoxLayout()
        
        info_label = QLabel("🎉 Phase 4 Integration Test - Graphics Mode Should Be AUTO-ENABLED")
        info_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #2E8B57;")
        info_layout.addWidget(info_label)
        
        layout.addLayout(info_layout)
        
        # Create test controls
        controls = QWidget()
        controls_layout = QHBoxLayout(controls)
        
        self.status_label = QLabel("Initializing...")
        controls_layout.addWidget(self.status_label)
        
        test_features_btn = QPushButton("Test Feature Creation")
        test_features_btn.clicked.connect(self.test_feature_creation)
        controls_layout.addWidget(test_features_btn)
        
        check_mode_btn = QPushButton("Check Current Mode")
        check_mode_btn.clicked.connect(self.check_current_mode)
        controls_layout.addWidget(check_mode_btn)
        
        layout.addWidget(controls)
        
        # Create the actual MapTab (this should auto-enable graphics mode)
        try:
            # Mock controller for testing
            self.mock_controller = MockController()
            self.map_tab = MapTab(parent=self, controller=self.mock_controller)
            layout.addWidget(self.map_tab)
            
            # Check initial state
            self.check_current_mode()
            
        except Exception as e:
            error_label = QLabel(f"❌ Failed to create MapTab: {e}")
            error_label.setStyleSheet("color: red; font-weight: bold;")
            layout.addWidget(error_label)
            self.map_tab = None
        
        # Add log area
        self.log_area = QTextEdit()
        self.log_area.setMaximumHeight(200)
        self.log_area.setPlainText("=== Integration Test Log ===\n")
        layout.addWidget(self.log_area)
        
        self.statusBar().showMessage("Phase 4 Integration Test - Check graphics mode status")
    
    def log_message(self, message: str):
        """Add a message to the log area."""
        self.log_area.append(message)
        print(message)  # Also print to console
    
    def check_current_mode(self):
        """Check and display current mode status."""
        if not self.map_tab:
            self.status_label.setText("❌ MapTab not available")
            return
        
        try:
            is_graphics = self.map_tab.is_graphics_mode()
            
            if is_graphics:
                self.status_label.setText("✅ GRAPHICS MODE ACTIVE")
                self.status_label.setStyleSheet("color: green; font-weight: bold;")
                self.log_message("✅ Graphics mode is active - Phase 4 integration successful!")
                
                # Check if graphics adapter exists
                if hasattr(self.map_tab, 'graphics_adapter'):
                    self.log_message("✅ Graphics adapter found")
                    if hasattr(self.map_tab.graphics_adapter, 'feature_manager'):
                        self.log_message("✅ Graphics feature manager found")
                    else:
                        self.log_message("⚠️ Graphics feature manager not found")
                else:
                    self.log_message("⚠️ Graphics adapter not found")
                    
            else:
                self.status_label.setText("⚠️ Widget mode active")
                self.status_label.setStyleSheet("color: orange; font-weight: bold;")
                self.log_message("⚠️ Still in widget mode - graphics mode not activated")
                
        except Exception as e:
            self.status_label.setText(f"❌ Error checking mode: {e}")
            self.status_label.setStyleSheet("color: red; font-weight: bold;")
            self.log_message(f"❌ Error checking mode: {e}")
    
    def test_feature_creation(self):
        """Test creating features in graphics mode."""
        if not self.map_tab:
            self.log_message("❌ Cannot test - MapTab not available")
            return
        
        try:
            self.log_message("🧪 Testing feature creation...")
            
            # Check if we can access the graphics system
            if self.map_tab.is_graphics_mode():
                graphics_adapter = self.map_tab.graphics_adapter
                feature_manager = graphics_adapter.feature_manager
                
                # Test pin creation
                feature_manager.add_pin_feature("TestPin_1", 200, 150)
                self.log_message("✅ Test pin created successfully")
                
                # Test line creation
                feature_manager.add_line_feature("TestLine_1", [(100, 100), (300, 200), (500, 150)])
                self.log_message("✅ Test line created successfully")
                
                # Test branching line creation
                branches = [
                    [(400, 300), (400, 250)],  # Stem
                    [(400, 250), (350, 200)],  # Left branch
                    [(400, 250), (450, 200)]   # Right branch
                ]
                feature_manager.add_branching_line_feature("TestBranchingLine_1", branches)
                self.log_message("✅ Test branching line created successfully")
                
                # Check feature count
                feature_count = feature_manager.get_feature_count()
                self.log_message(f"✅ Total features in graphics system: {feature_count}")
                
                self.log_message("🎉 All feature creation tests passed!")
                
            else:
                self.log_message("⚠️ Cannot test features - not in graphics mode")
                
        except Exception as e:
            self.log_message(f"❌ Feature creation test failed: {e}")
            import traceback
            self.log_message(f"Full error: {traceback.format_exc()}")


class MockController:
    """Mock controller for testing."""
    
    def __init__(self):
        self.config = MockConfig()


class MockConfig:
    """Mock configuration for testing."""
    
    def __init__(self):
        self.map = MockMapConfig()


class MockMapConfig:
    """Mock map configuration."""
    
    def __init__(self):
        self.PIN_SVG_SOURCE = "src/resources/graphics/NWB_Map_Pin.svg"
        self.BASE_PIN_WIDTH = 24
        self.BASE_PIN_HEIGHT = 32
        self.MIN_PIN_WIDTH = 12
        self.MIN_PIN_HEIGHT = 16


def run_integration_test():
    """Run the full integration test."""
    app = QApplication(sys.argv)
    window = TestIntegrationWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    run_integration_test()