from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional


@dataclass
class StyleConfig:
    """Configuration for a single style theme."""

    name: str
    path: Path
    variables: Dict[str, str]
    description: str = ""
    parent: Optional[str] = None
