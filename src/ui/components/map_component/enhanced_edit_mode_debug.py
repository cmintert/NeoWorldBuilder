"""Enhanced edit mode debugging helper.

This module provides debugging functions to diagnose and fix issues with the enhanced edit mode.
"""

import json
from typing import List, Tuple, Dict, Any, Optional
from structlog import get_logger

logger = get_logger(__name__)

def diagnose_edit_mode_issues(map_tab_instance):
    """Diagnose issues with the enhanced edit mode.
    
    Args:
        map_tab_instance: MapTab instance to diagnose
    """
    logger.info("Starting edit mode diagnosis")
    
    # Check if enhanced feature manager exists
    if not hasattr(map_tab_instance, 'enhanced_feature_manager'):
        logger.error("Enhanced feature manager not found on MapTab instance")
        return "Enhanced feature manager not found"
    
    # Check if enhanced feature manager has branching lines
    branching_lines_count = len(map_tab_instance.enhanced_feature_manager.branching_lines)
    logger.info(f"Found {branching_lines_count} branching lines in enhanced feature manager")
    
    # Check if edit mode is active
    logger.info(f"Edit mode active: {map_tab_instance.edit_mode_active}")
    
    # Check if there are MultiLineString geometries in the database
    multi_line_count = 0
    relationship_count = 0
    
    if map_tab_instance.controller and map_tab_instance.controller.ui.relationships_table:
        relationships_table = map_tab_instance.controller.ui.relationships_table
        relationship_count = relationships_table.rowCount()
        
        for row in range(relationship_count):
            try:
                rel_type = relationships_table.item(row, 0)
                if not rel_type or rel_type.text() != "SHOWS":
                    continue
                
                props_item = relationships_table.item(row, 3)
                if not props_item:
                    continue
                
                properties = json.loads(props_item.text())
                if "geometry" not in properties:
                    continue
                
                if "geometry_type" in properties and properties["geometry_type"] == "MultiLineString":
                    multi_line_count += 1
                    
                    # Get target node for this MultiLineString
                    target_item = relationships_table.item(row, 1)
                    if target_item:
                        target_node = map_tab_instance._extract_target_node(target_item, relationships_table, row)
                        logger.info(f"Found MultiLineString for {target_node}")
                        
                        # Check if this MultiLineString is in the enhanced feature manager
                        if target_node in map_tab_instance.enhanced_feature_manager.branching_lines:
                            logger.info(f"MultiLineString {target_node} exists in enhanced feature manager")
                        else:
                            logger.error(f"MultiLineString {target_node} not found in enhanced feature manager")
            except Exception as e:
                logger.error(f"Error processing relationship row {row}: {e}")
    
    logger.info(f"Found {multi_line_count} MultiLineString geometries in {relationship_count} relationships")
    
    if multi_line_count == 0:
        logger.warning("No MultiLineString geometries found in database")
        return "No MultiLineString geometries found"
    
    if branching_lines_count == 0:
        logger.warning("No branching lines loaded in enhanced feature manager")
        return "No branching lines loaded"
    
    return f"Found {branching_lines_count} branching lines and {multi_line_count} MultiLineString geometries"

def fix_edit_mode_integration(map_tab_instance):
    """Fix issues with enhanced edit mode integration.
    
    Args:
        map_tab_instance: MapTab instance to fix
    """
    from .enhanced_edit_mode import EnhancedFeatureManager
    
    logger.info("Fixing edit mode integration")
    
    # Re-create enhanced feature manager if needed
    if not hasattr(map_tab_instance, 'enhanced_feature_manager'):
        logger.info("Creating new enhanced feature manager")
        map_tab_instance.enhanced_feature_manager = EnhancedFeatureManager(
            map_tab_instance.feature_container, map_tab_instance.config
        )
        
        # Connect signals
        map_tab_instance.enhanced_feature_manager.feature_clicked.connect(
            map_tab_instance._handle_feature_click
        )
    
    # Reload features to ensure all MultiLineString geometries are loaded
    logger.info("Reloading features to ensure proper loading of branching lines")
    
    # Store and clear existing features
    original_load_features = map_tab_instance.load_features
    
    # Import from enhanced_edit_mode
    from .enhanced_edit_mode import integrate_enhanced_edit_mode
    
    # Apply enhanced edit mode with fresh settings
    integrate_enhanced_edit_mode(map_tab_instance)
    
    # Force reload of features
    map_tab_instance.feature_manager.clear_all_features()
    if hasattr(map_tab_instance, 'enhanced_feature_manager'):
        map_tab_instance.enhanced_feature_manager.clear_all_features()
    
    # Run the enhanced load_features
    map_tab_instance.load_features()
    
    logger.info("Edit mode integration fixed")
    return "Edit mode integration fixed, features reloaded"
