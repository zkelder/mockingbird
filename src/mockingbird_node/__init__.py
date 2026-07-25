"""Local-only MockingBird Camera Node package.

The Node is intentionally a small edge adapter. It has no product database,
model runtime, retention policy, or review/truth concepts; the main application
owns those concerns.
"""

from .config import CameraNodeConfig


def create_node_app(*args: object, **kwargs: object):
    """Load the HTTP runtime only when a caller needs to start the Node."""

    from .app import create_node_app as build_node_app

    return build_node_app(*args, **kwargs)


__all__ = ["CameraNodeConfig", "create_node_app"]
