"""User-facing local runtime for one-process MockingBird startup."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import threading
import time
from urllib.error import URLError
from urllib.request import urlopen
import webbrowser

import uvicorn

from mockingbird.runtime_state import (
    configure_file_logging,
    prepare_runtime_state,
    uvicorn_log_config,
)
from mockingbird.storage.database import DatabaseSchemaCompatibilityError
from mockingbird.web_app import (
    WEB_DIST_ENV_VAR,
    find_workspace_root,
    frontend_build_status,
)


APP_HOME_ENV_VAR = "MOCKINGBIRD_HOME"
_LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}


class RuntimePreflightError(RuntimeError):
    """Raised when the local app cannot start safely."""


@dataclass(frozen=True)
class RuntimePreflight:
    runtime_home: Path
    frontend_dist: Path
    database_schema_version: int
    database_integrity_check: str


def resolve_runtime_home(workspace_root: Path | None = None) -> Path:
    configured_home = os.getenv(APP_HOME_ENV_VAR)
    if configured_home:
        return Path(configured_home).expanduser().resolve()
    if workspace_root is not None:
        return workspace_root.resolve()
    if os.name == "nt":
        local_app_data = os.getenv("LOCALAPPDATA")
        if local_app_data:
            return Path(local_app_data) / "MockingBird"
        return Path.home() / "AppData" / "Local" / "MockingBird"
    xdg_data_home = os.getenv("XDG_DATA_HOME")
    if xdg_data_home:
        return Path(xdg_data_home) / "mockingbird"
    return Path.home() / ".local" / "share" / "mockingbird"


def _npm_executable() -> str | None:
    preferred = "npm.cmd" if os.name == "nt" else "npm"
    return shutil.which(preferred) or shutil.which("npm")


def ensure_frontend_build(
    workspace_root: Path | None,
    *,
    build_if_missing: bool,
) -> Path:
    status = frontend_build_status()
    if status.available:
        return status.dist_path
    if not build_if_missing or workspace_root is None:
        raise RuntimePreflightError(
            "The MockingBird interface is not available in this installation."
        )

    web_root = workspace_root / "web"
    if not (web_root / "node_modules").is_dir():
        raise RuntimePreflightError(
            "The MockingBird interface needs its local web dependencies before the first launch."
        )
    npm = _npm_executable()
    if npm is None:
        raise RuntimePreflightError(
            "The MockingBird interface is not built and the local web builder is unavailable."
        )

    completed = subprocess.run(
        [npm, "run", "build"],
        cwd=web_root,
        check=False,
    )
    if completed.returncode != 0 or not frontend_build_status().available:
        raise RuntimePreflightError("MockingBird could not prepare its local interface.")
    return frontend_build_status().dist_path


def run_preflight(*, build_frontend: bool = True) -> RuntimePreflight:
    workspace_root = find_workspace_root()
    runtime_home = resolve_runtime_home(workspace_root)
    runtime_home.mkdir(parents=True, exist_ok=True)
    os.chdir(runtime_home)

    frontend_dist = ensure_frontend_build(
        workspace_root,
        build_if_missing=build_frontend,
    )
    os.environ[WEB_DIST_ENV_VAR] = str(frontend_dist)

    # Import only after the runtime home is stable so default database/media
    # paths cannot drift with the shortcut or terminal working directory.
    from mockingbird.api.main import get_repository

    repository = get_repository()
    return RuntimePreflight(
        runtime_home=runtime_home,
        frontend_dist=frontend_dist,
        database_schema_version=repository.schema_status.version,
        database_integrity_check=repository.schema_status.integrity_check,
    )


def local_base_url(host: str, port: int) -> str:
    browser_host = "127.0.0.1" if host in {"0.0.0.0", "::"} else host
    if ":" in browser_host and not browser_host.startswith("["):
        browser_host = f"[{browser_host}]"
    return f"http://{browser_host}:{port}"


def healthy_mockingbird_at(base_url: str, *, timeout_seconds: float = 0.4) -> bool:
    try:
        with urlopen(f"{base_url}/health", timeout=timeout_seconds) as response:
            if response.status != 200:
                return False
            payload = json.loads(response.read().decode("utf-8"))
        if payload != {"status": "ok"}:
            return False
        with urlopen(f"{base_url}/", timeout=timeout_seconds) as response:
            content_type = response.headers.get("Content-Type", "")
            app_shell = response.read(64 * 1024).decode("utf-8", errors="replace")
    except (OSError, URLError, ValueError):
        return False
    return (
        response.status == 200
        and content_type.startswith("text/html")
        and "<title>MockingBird</title>" in app_shell
    )


def _print_preflight(preflight: RuntimePreflight) -> None:
    print(
        "MockingBird is ready: "
        f"data format {preflight.database_schema_version}, "
        f"integrity {preflight.database_integrity_check}."
    )


def port_is_available(host: str, port: int) -> bool:
    bind_host = "127.0.0.1" if host == "localhost" else host
    family = socket.AF_INET6 if ":" in bind_host else socket.AF_INET
    try:
        with socket.socket(family, socket.SOCK_STREAM) as probe:
            probe.bind((bind_host, port))
    except OSError:
        return False
    return True


def open_browser_when_ready(base_url: str, *, timeout_seconds: float = 20.0) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if healthy_mockingbird_at(base_url):
            webbrowser.open(base_url)
            return
        time.sleep(0.2)


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Start the local MockingBird application.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8000, type=int)
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--check", action="store_true", help="Validate startup and exit.")
    parser.add_argument("--skip-frontend-build", action="store_true")
    parser.add_argument(
        "--allow-network",
        action="store_true",
        help="Allow binding beyond this device. No production authentication is provided.",
    )
    return parser


def run(argv: list[str] | None = None) -> int:
    args = build_argument_parser().parse_args(argv)
    if not 1 <= args.port <= 65535:
        print("Choose a port between 1 and 65535.")
        return 2
    if args.host not in _LOOPBACK_HOSTS and not args.allow_network:
        print("MockingBird stays on this device unless network access is explicitly allowed.")
        return 2

    if args.check:
        try:
            preflight = run_preflight(build_frontend=not args.skip_frontend_build)
        except (DatabaseSchemaCompatibilityError, OSError, RuntimePreflightError) as error:
            print(str(error))
            return 2
        _print_preflight(preflight)
        return 0

    base_url = local_base_url(args.host, args.port)
    if healthy_mockingbird_at(base_url):
        print(f"MockingBird is already running at {base_url}")
        if not args.no_browser and not args.check:
            webbrowser.open(base_url)
        return 0
    if not port_is_available(args.host, args.port):
        print(f"Port {args.port} is already in use by another application.")
        return 2

    try:
        preflight = run_preflight(build_frontend=not args.skip_frontend_build)
    except (DatabaseSchemaCompatibilityError, OSError, RuntimePreflightError) as error:
        print(str(error))
        return 2

    _print_preflight(preflight)

    # Only the real launch path touches the crash marker/log file -- `--check`
    # above returns before this point so repeated validation runs never make
    # the *next* real launch think the previous one crashed.
    log_path = configure_file_logging(preflight.runtime_home)
    if prepare_runtime_state(preflight.runtime_home) is False:
        print("Note: MockingBird did not shut down cleanly last time. Your local data is unaffected.")

    if not args.no_browser:
        threading.Thread(
            target=open_browser_when_ready,
            args=(base_url,),
            daemon=True,
            name="mockingbird-browser-opener",
        ).start()

    from mockingbird.api.main import app

    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        log_level="info",
        log_config=uvicorn_log_config(log_path),
    )
    return 0


def main() -> None:
    raise SystemExit(run())
