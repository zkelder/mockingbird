"""Manual Camera Node launcher; it never installs or manages an OS service."""

from __future__ import annotations

import argparse
import sys

from .config import CameraNodeConfig


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Start the local-only MockingBird Camera Node.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="validate local Node configuration without opening a listener",
    )
    arguments = parser.parse_args(argv)
    try:
        config = CameraNodeConfig.from_environment()
    except ValueError as error:
        # A clean, one-line, log-level-independent failure -- `systemctl
        # status`/`journalctl` show this immediately as "why startup
        # failed" instead of a raw traceback. See "Diagnostics
        # implementation" in docs/camera-node-installer-design.md.
        print(f"Camera Node configuration error: {error}", file=sys.stderr)
        raise SystemExit(1) from None
    if arguments.check:
        print("MockingBird Camera Node configuration is valid.")
        return
    from .app import create_node_app
    import uvicorn

    app = create_node_app(config)
    print(f"MockingBird Camera Node pairing code: {app.state.pairing_code}", file=sys.stderr)
    print(f"Pairing code expires at: {app.state.pairing_expires_at.isoformat()}", file=sys.stderr)
    uvicorn.run(app, host=config.bind_host, port=config.port, log_level=config.log_level)


if __name__ == "__main__":
    main()
