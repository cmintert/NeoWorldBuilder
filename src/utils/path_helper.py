import os
import sys


def get_resource_path(relative_path: str) -> str:
    """Get absolute path to bundled resources, works both in development and PyInstaller bundle."""
    if getattr(sys, "frozen", False):
        # Running in PyInstaller bundle
        base_path = sys._MEIPASS
        # Remove 'src/' prefix if present when running from bundle
        if relative_path.startswith("src/"):
            relative_path = relative_path[4:]
    else:
        # Running in normal Python environment
        base_path = os.path.abspath(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        )

    return os.path.join(base_path, *relative_path.split("/"))
