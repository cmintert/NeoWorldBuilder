import json
from typing import List, Tuple
from PyQt6.QtWidgets import QLineEdit


class LineGeometryPersistence:
    """Handles saving line geometry to database."""
    
    def __init__(self, target_node: str):
        self.target_node = target_node
    
    def update_geometry(self, original_points: List[Tuple[int, int]], controller) -> None:
        """Update geometry in the relationships table.
        
        Args:
            original_points: List of original coordinate points
            controller: The application controller
        """
        try:
            # Convert updated points back to WKT
            from utils.geometry_handler import GeometryHandler
            
            new_wkt = GeometryHandler.create_line(original_points)
            
            # Find the parent map tab to access the controller
            if not controller:
                print("No controller provided to update geometry")
                return
            
            relationships_table = controller.ui.relationships_table
            
            if not relationships_table:
                print("No relationships table found")
                return
            
            # Find the row for this line feature
            for row in range(relationships_table.rowCount()):
                rel_type = relationships_table.item(row, 0)
                target_item = relationships_table.item(row, 1)
                props_item = relationships_table.item(row, 3)
                
                if not (rel_type and target_item and props_item):
                    continue
                
                # Check if this is our line
                target_node = ""
                if hasattr(target_item, "text"):
                    target_node = target_item.text()
                else:
                    target_widget = relationships_table.cellWidget(row, 1)
                    if isinstance(target_widget, QLineEdit):
                        target_node = target_widget.text()
                
                if rel_type.text() == "SHOWS" and target_node == self.target_node:
                    # Found our row - update the geometry
                    properties = json.loads(props_item.text())
                    properties["geometry"] = new_wkt
                    
                    # Update the table item
                    props_item.setText(json.dumps(properties))
                    
                    print(f"Updated geometry for {self.target_node}")
                    break
                    
        except Exception as e:
            print(f"Error updating line geometry: {e}")
            import traceback
            traceback.print_exc()
