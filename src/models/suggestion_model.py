from dataclasses import dataclass
from typing import Protocol, Dict, Any, Optional, List


@dataclass
class SuggestionResult:
    success: bool
    selected_suggestions: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None


class SuggestionUIHandler(Protocol):
    """Interface for UI operations needed by SuggestionService"""

    def show_loading(self, is_loading: bool) -> None:
        """Show/hide loading indicator"""
        ...

    def show_message(self, title: str, message: str) -> None:
        """Show message to user"""
        ...

    def show_suggestion_dialog(self, suggestions: Dict[str, Any]) -> SuggestionResult:
        """Show suggestion dialog and return user selection"""
        ...

    def update_tags(self, tags: List[str]) -> None:
        """Update UI tags"""
        ...

    def add_property(self, key: str, value: Any) -> None:
        """Add property to UI"""
        ...

    def add_relationship(
        self, rel_type: str, target: str, direction: str, props: Dict[str, Any]
    ) -> None:
        """Add relationship to UI"""
        ...
