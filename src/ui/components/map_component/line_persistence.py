import json
from typing import Any, Dict

from PyQt6.QtWidgets import QLineEdit


class LineGeometryPersistence:
    """Handles saving line geometry to database."""

    def __init__(self, target_node: str):
        self.target_node = target_node

    def update_geometry(
        self,
        original_points_or_branches,
        controller,
        branch_assignments: Dict[str, str] = None,
    ) -> None:
        """Update geometry in the relationships table.

        Args:
            original_points_or_branches: List of points for simple line, or list of branches for branching line
            controller: The application controller
            branch_assignments: Optional dictionary mapping stable branch IDs to node IDs
        """
        try:
            # Convert updated points back to WKT
            from utils.geometry_handler import GeometryHandler

            # Validate and process the geometry data
            if not original_points_or_branches:
                return

            # Check if this is a simple line or branching line
            if isinstance(original_points_or_branches[0], list):
                # Branching line - list of branches
                # Validate that branches contain coordinate tuples
                valid_branches = []
                for branch in original_points_or_branches:
                    if branch and len(branch) >= 2:
                        # Ensure each point is a valid coordinate tuple
                        valid_branch = []
                        for point in branch:
                            if isinstance(point, (tuple, list)) and len(point) >= 2:
                                valid_branch.append((float(point[0]), float(point[1])))
                        if len(valid_branch) >= 2:
                            valid_branches.append(valid_branch)

                if not valid_branches:
                    return

                new_wkt = GeometryHandler.create_multi_line(valid_branches)
                original_points_or_branches = valid_branches  # Use validated data
            else:
                # Simple line - list of points
                # Validate that we have coordinate tuples
                valid_points = []
                for point in original_points_or_branches:
                    if isinstance(point, (tuple, list)) and len(point) >= 2:
                        valid_points.append((float(point[0]), float(point[1])))

                if len(valid_points) < 2:
                    return

                new_wkt = GeometryHandler.create_line(valid_points)
                original_points_or_branches = valid_points  # Use validated data

            # Find the parent map tab to access the controller
            if not controller:
                return

            relationships_table = controller.ui.relationships_table

            if not relationships_table:
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

                    # Update geometry type based on what we're storing
                    if original_points_or_branches and isinstance(
                        original_points_or_branches[0], list
                    ):
                        properties["geometry_type"] = "MultiLineString"
                        properties["branch_count"] = len(original_points_or_branches)

                        # Add branch assignments as flat properties
                        if branch_assignments:
                            # Remove any existing branch assignments
                            keys_to_remove = [
                                k for k in properties.keys() if k.startswith("branch_")
                            ]
                            for key in keys_to_remove:
                                del properties[key]

                            # Add new branch assignments
                            for stable_id, node_id in branch_assignments.items():
                                properties[f"branch_{stable_id}"] = node_id
                    else:
                        properties["geometry_type"] = "LineString"
                        # Remove branch_count if it exists
                        properties.pop("branch_count", None)

                        # Remove any branch assignments for simple lines
                        keys_to_remove = [
                            k for k in properties.keys() if k.startswith("branch_")
                        ]
                        for key in keys_to_remove:
                            del properties[key]

                    # Update the table item
                    props_item.setText(json.dumps(properties))

                    break

        except Exception as e:
            pass
            import traceback

            traceback.print_exc()

    def load_branch_assignments_from_database(self, controller) -> Dict[str, str]:
        """Load branch assignments from database properties.

        Args:
            controller: The application controller

        Returns:
            Dictionary mapping stable branch IDs to node IDs
        """
        branch_assignments = {}

        try:
            if not controller:
                return branch_assignments

            relationships_table = controller.ui.relationships_table
            if not relationships_table:
                return branch_assignments

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
                    # Found our row - extract branch assignments
                    properties = json.loads(props_item.text())

                    # Extract branch assignments from flat properties
                    for key, value in properties.items():
                        if key.startswith("branch_"):
                            stable_id = key[7:]  # Remove "branch_" prefix
                            branch_assignments[stable_id] = value

                    break

        except Exception as e:
            import traceback

            traceback.print_exc()

        return branch_assignments
