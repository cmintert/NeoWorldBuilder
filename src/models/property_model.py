from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class PropertyItem:
    key: str
    value: Any

    @classmethod
    def from_table_item(
        cls, key_item: "QTableWidgetItem", value_item: "QTableWidgetItem"
    ) -> Optional["PropertyItem"]:
        """Create PropertyItem from table items"""
        if not key_item or not key_item.text().strip():
            return None

        key = key_item.text().strip()
        value_text = value_item.text().strip() if value_item else ""

        return cls(key=key, value=value_text)
