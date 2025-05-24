"""Simple test script for the enhanced edit mode.

This script can be run to verify that the enhanced edit mode is working correctly.
"""

import sys
import os
import json
from PyQt6.QtWidgets import QApplication
from structlog import get_logger

# Add src directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../')))

from ui.components.map_component.map_tab import MapTab
from ui.components.map_component.enhanced_edit_mode_debug import diagnose_edit_mode_issues, fix_edit_mode_integration

logger = get_logger(__name__)

def test_enhanced_edit_mode():
    """Test the enhanced edit mode integration."""
    app = QApplication(sys.argv)
    
    # Create a test MapTab
    map_tab = MapTab()
    
    # Check if enhanced feature manager exists
    if hasattr(map_tab, 'enhanced_feature_manager'):
        logger.info("Enhanced feature manager exists")
    else:
        logger.error("Enhanced feature manager does not exist")
    
    # Try to create a branching line
    if hasattr(map_tab, 'enhanced_feature_manager'):
        # Create a test branching line
        branches = [
            [(0, 0), (100, 100), (200, 0)],
            [(100, 100), (100, 200)],
        ]
        style_config = {
            "color": "#FF0000",
            "width": 2,
            "pattern": "solid",
        }
        map_tab.enhanced_feature_manager.create_branching_line("test_node", branches, style_config)
        logger.info("Created test branching line")
    
    # Test edit mode
    map_tab.toggle_edit_mode(True)
    logger.info(f"Edit mode active: {map_tab.edit_mode_active}")
    
    # Check if the edit mode is also set on the enhanced feature manager
    if hasattr(map_tab, 'enhanced_feature_manager'):
        # Check if any branching lines exist
        branching_lines_count = len(map_tab.enhanced_feature_manager.branching_lines)
        logger.info(f"Branching lines count: {branching_lines_count}")
        
        # Check if edit mode is set on any of the branching lines
        for target_node, line_container in map_tab.enhanced_feature_manager.branching_lines.items():
            logger.info(f"Branching line {target_node} edit mode: {line_container.edit_mode}")
    
    logger.info("Enhanced edit mode test completed")

if __name__ == "__main__":
    test_enhanced_edit_mode()
