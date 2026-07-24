"""Manual Camera Node launcher; it never installs or manages an OS service."""

from __future__ import annotations

import sys
import uvicorn

from .app import create_node_app
from .config import CameraNodeConfig


def main() -> None:
    config = CameraNodeConfig.from_environment()
    app = create_node_app(config)
    print(f"MockingBird Camera Node pairing code: {app.state.pairing_code}", file=sys.stderr)
    print(f"Pairing code expires at: {app.state.pairing_expires_at.isoformat()}", file=sys.stderr)
    uvicorn.run(app, host=config.bind_host, port=config.port, log_level="warning")


if __name__ == "__main__":
    main()
