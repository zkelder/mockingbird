"""Local-only MockingBird Camera Node package.

The Node is intentionally a small edge adapter. It has no product database,
model runtime, retention policy, or review/truth concepts; the main application
owns those concerns.
"""

from .config import CameraNodeConfig


#: Development-checkout fallback only -- a real installed Node always has
#: proper wheel `.dist-info` metadata `identity.resolve_service_version()`
#: reads directly; see that function's own docstring. Keep in sync with
#: `pyproject.toml`'s `[project].version` (the artifact builder stamps the
#: same value into the wheel it produces from that same source of truth).
#: Final Release Candidate Corrections v1: restored to "0.1.0" -- see
#: `pyproject.toml`'s own comment for the reasoning. This is a
#: package-version change only; `NODE_API_VERSION`/`TRANSPORT_PROTOCOL_
#: VERSION` (mockingbird_node/app.py, transport_client.py) are separate,
#: unchanged wire-protocol literals never derived from this value.
__version__ = "0.1.0"


def create_node_app(*args: object, **kwargs: object):
    """Load the HTTP runtime only when a caller needs to start the Node."""

    from .app import create_node_app as build_node_app

    return build_node_app(*args, **kwargs)


__all__ = ["CameraNodeConfig", "create_node_app"]
