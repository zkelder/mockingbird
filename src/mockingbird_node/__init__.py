"""Local-only MockingBird Camera Node package.

The Node is intentionally a small edge adapter. It has no product database,
model runtime, retention policy, or review/truth concepts; the main application
owns those concerns.
"""

from .app import create_node_app
from .config import CameraNodeConfig

__all__ = ["CameraNodeConfig", "create_node_app"]
