from typing import Optional, Dict, Any

from ui.components.map_component.map_tab import MapTab


class MapService:
    def __init__(self, ui):
        self.ui = ui

    def populate_map_tab(self, node_data: Dict[str, Any]) -> None:
        is_map_node = "MAP" in {label.upper() for label in node_data["labels"]}
        if is_map_node:
            self.ensure_map_tab_exists()
            self.update_map_image(node_data["properties"].get("mapimage"))
        else:
            self.remove_map_tab()

    def ensure_map_tab_exists(self) -> None:
        if not self.ui.map_tab:
            self.ui.map_tab = MapTab()
            self.ui.map_tab.map_image_changed.connect(self.ui._handle_map_image_changed)
            self.ui.tabs.addTab(self.ui.map_tab, "Map")

    def remove_map_tab(self) -> None:
        if self.ui.map_tab:
            map_tab_index = self.ui.tabs.indexOf(self.ui.map_tab)
            if map_tab_index != -1:
                self.ui.tabs.removeTab(map_tab_index)
                self.ui.map_tab = None

    def update_map_image(self, image_path: Optional[str]) -> None:
        if self.ui.map_tab:
            self.ui.map_tab.set_map_image(image_path)
