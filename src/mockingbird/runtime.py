"""User-facing local runtime for one-process MockingBird startup."""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass
import io
import json
import logging
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import threading
import time
from urllib.error import URLError
from urllib.request import urlopen
import webbrowser

import uvicorn

from mockingbird.runtime_state import (
    configure_file_logging,
    prepare_runtime_state,
    resolve_instance_id,
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
_logger = logging.getLogger(__name__)


def _ensure_console_streams() -> bool:
    """Return whether a real console/terminal was attached to this process.

    `pythonw.exe` (the packaged Windows launcher's runtime -- see
    `Start MockingBird.vbs`) has no console at all: CPython documents that
    `sys.stdin`/`stdout`/`stderr` are `None` there. An unguarded `print()`
    would otherwise crash the process before it ever binds a port --
    invisibly, since there is also no console to show the resulting
    traceback. Give every stream a safe sink either way, once, as early as
    possible, so nothing later in this process (this module's own
    messages, a library's stray `print()`, a default logging
    `StreamHandler`) can crash it.
    """

    has_console = sys.stdin is not None and sys.stdout is not None and sys.stderr is not None
    if sys.stdin is None:
        sys.stdin = io.StringIO()
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w", encoding="utf-8")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w", encoding="utf-8")
    return has_console


def _alert_failure(message: str, *, has_console: bool) -> None:
    """Make a startup failure impossible to miss.

    A console launch (a terminal, `python\\python.exe -m mockingbird`)
    already shows the printed line right there. A console-less launch
    (`pythonw.exe`, what the packaged `.vbs` launcher actually runs) cannot
    show one at all, so a real user would otherwise see nothing happen --
    pop up one native, no-dependency dialog instead. Never let the dialog
    mechanism itself become a new way to fail.
    """

    print(message)
    _logger.error(message)
    if has_console or os.name != "nt":
        return
    try:
        import ctypes

        ctypes.windll.user32.MessageBoxW(0, message, "MockingBird", 0x10)
    except Exception:
        pass


def _remote_instance_id(base_url: str, *, timeout_seconds: float = 0.5) -> str | None:
    """Bounded, tolerant read of another running MockingBird's own identity.

    Any failure -- an older version without this endpoint, a timeout, a
    malformed response -- returns `None`, meaning "cannot confirm this is
    the same installation," never a guess in either direction. See
    "Windows launcher defects" in docs/camera-node-pairing-persistence-design.md.
    """

    try:
        with urlopen(f"{base_url}/api/product/instance", timeout=timeout_seconds) as response:
            if response.status != 200:
                return None
            payload = json.loads(response.read(4096).decode("utf-8"))
    except (OSError, URLError, ValueError):
        return None
    instance_id = payload.get("instance_id") if isinstance(payload, dict) else None
    return instance_id if isinstance(instance_id, str) and instance_id else None


class RuntimePreflightError(RuntimeError):
    """Raised when the local app cannot start safely."""


@dataclass(frozen=True)
class RuntimePreflight:
    runtime_home: Path
    frontend_dist: Path
    database_schema_version: int
    database_integrity_check: str
    # Release Engineering Foundation v1: set only when this preflight call
    # actually performed an in-place schema upgrade -- see
    # `mockingbird.storage.database.DatabaseSchemaStatus`.
    database_migrated_from_version: int | None = None
    database_pre_migration_backup_id: str | None = None


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
        database_migrated_from_version=repository.schema_status.migrated_from_version,
        database_pre_migration_backup_id=repository.schema_status.pre_migration_backup_id,
    )


_WILDCARD_BIND_HOSTS = {"0.0.0.0", "::"}


def detect_local_network_address() -> str | None:
    """Best-effort discovery of this machine's own LAN-facing IP address,
    for `GET /api/product/connection` (Mobile & Remote Experience v1) to
    show a user "the address your phone would use on this WiFi" when
    MockingBird was started with `--host 0.0.0.0`/`--allow-network`.

    Uses the standard `connect()`-a-UDP-socket-then-read-its-own-address
    trick: `connect()` on `SOCK_DGRAM` never actually sends a packet or
    requires the target to be reachable, it only asks the OS routing table
    which local interface *would* be used to reach that address -- so this
    works offline and never contacts `8.8.8.8`. Returns `None` on any
    failure (no network interface, sandboxed/container networking, etc.)
    rather than ever fabricating an address -- a caller must treat `None`
    as "could not determine," never "no network.\""""

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.connect(("8.8.8.8", 80))
            address = probe.getsockname()[0]
    except OSError:
        return None
    return address or None


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
    if preflight.database_migrated_from_version is not None:
        print(
            "MockingBird is ready: "
            f"data format upgraded {preflight.database_migrated_from_version} -> "
            f"{preflight.database_schema_version} (safety backup "
            f"{preflight.database_pre_migration_backup_id}), "
            f"integrity {preflight.database_integrity_check}."
        )
        return
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


# Native-Windows Runtime Shutdown & Listener Resilience Correction v1 (F-2,
# and F-1's trigger). On Windows, uvicorn's own default is the Proactor event
# loop, and the bundled CPython 3.12's Proactor has two socket-lifecycle
# defects proven on real hardware: its accept loop *closes the listening
# socket* on one `WinError 64` from an abortive client (the product stays
# alive but unreachable), and its connection-lost path raises `WinError
# 10054` before `Server._detach()`, leaking the server's connection count so
# graceful shutdown waits forever. The selector loop's accept path logs and
# keeps serving on the same errors, and its connection-lost path detaches in
# a `finally`. Nothing on this server loop needs Proactor: MockingBird
# starts no asyncio subprocesses or pipes (camera/ffmpeg bridges use
# blocking `subprocess.Popen` on their own threads), and other components'
# own `asyncio.run(...)` loops on their own threads are untouched because
# this chooses the loop for the uvicorn server only, never the process-wide
# policy. The selector loop's `select()` limit (512 sockets on Windows) is
# far above a loopback/LAN product's concurrent connections. Other platforms
# keep uvicorn's own choice unchanged.
_SERVE_ON_SELECTOR_LOOP = sys.platform == "win32"

# F-1 defense in depth: uvicorn's default (`None`) waits forever for open
# connections and `asyncio.Server.wait_closed()` before it ever runs the
# FastAPI lifespan teardown (which ends in `mark_clean_shutdown()`), so one
# leaked connection -- the Proactor bug above, or a response that never ends,
# such as an open MJPEG live view -- hung *Shut down MockingBird* forever.
# Measured on native Windows with the selector loop, a real shutdown's whole
# drain + lifespan teardown completed in 0.45-0.59 s (process exit
# 0.83-1.06 s), with and without prior connection resets; 5 s is ~8x that
# while staying well short of a user concluding the stop hung. When it
# fires, uvicorn cancels the remaining request tasks and still runs the
# teardown; a blocking handler already running on a worker thread is not
# interrupted and finishes before the process exits.
GRACEFUL_SHUTDOWN_TIMEOUT_SECONDS = 5


def build_uvicorn_server(app, *, host: str, port: int, log_config) -> uvicorn.Server:
    config = uvicorn.Config(
        app,
        host=host,
        port=port,
        log_level="info",
        log_config=log_config,
        timeout_graceful_shutdown=GRACEFUL_SHUTDOWN_TIMEOUT_SECONDS,
    )
    return uvicorn.Server(config)


def serve_until_stopped(server: uvicorn.Server) -> None:
    """Run `server` until it stops, on the event loop this platform needs.

    `Server.serve()` is uvicorn's public programmatic entry point, and
    `asyncio.Runner` is exactly what uvicorn's own `Server.run()` uses on
    Python 3.11+, so signal handling, lifespan and shutdown order are
    uvicorn's own -- only the loop class differs.
    """

    if not _SERVE_ON_SELECTOR_LOOP:
        server.run()
        return
    with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as runner:
        runner.run(server.serve())


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
        # Local Identity, Multi-User & Organization Access v1 added real
        # sign-in for every /api/ route (this help text used to say "No
        # production authentication is provided," written before that
        # shipped -- see docs/mobile-remote-experience-v1-report.md). The
        # honest remaining caveat is transport, not authentication: without
        # a reverse proxy terminating TLS, traffic on this network segment
        # -- including the session cookie -- is plain HTTP.
        help=(
            "Allow binding beyond this device (for example your home network). "
            "Sign-in is required either way; traffic stays plain HTTP unless you "
            "add a reverse proxy for TLS."
        ),
    )
    return parser


def run(argv: list[str] | None = None) -> int:
    has_console = _ensure_console_streams()
    args = build_argument_parser().parse_args(argv)
    if not 1 <= args.port <= 65535:
        _alert_failure("Choose a port between 1 and 65535.", has_console=has_console)
        return 2
    if args.host not in _LOOPBACK_HOSTS and not args.allow_network:
        _alert_failure(
            "MockingBird stays on this device unless network access is explicitly allowed.",
            has_console=has_console,
        )
        return 2

    if args.check:
        try:
            preflight = run_preflight(build_frontend=not args.skip_frontend_build)
        except (DatabaseSchemaCompatibilityError, OSError, RuntimePreflightError) as error:
            _alert_failure(str(error), has_console=has_console)
            return 2
        _print_preflight(preflight)
        return 0

    base_url = local_base_url(args.host, args.port)
    # Resolved before any reuse decision: comparing "is that other instance
    # really me" requires knowing this process's own identity first, and a
    # brand-new data directory (never launched before) has nothing to
    # compare yet either way. Also doubles as the earliest safe point to
    # start file logging, so a failure anywhere below -- including a
    # rejected reuse decision -- leaves a discoverable trail even with no
    # console at all. `--check` above already returned, so this never runs
    # for a validate-only invocation.
    own_runtime_home = resolve_runtime_home(find_workspace_root())
    own_runtime_home.mkdir(parents=True, exist_ok=True)
    log_path = configure_file_logging(own_runtime_home)

    try:
        if healthy_mockingbird_at(base_url):
            own_instance_id = resolve_instance_id(own_runtime_home)
            remote_instance_id = _remote_instance_id(base_url)
            if remote_instance_id is not None and remote_instance_id == own_instance_id:
                print(f"MockingBird is already running at {base_url}")
                if not args.no_browser:
                    webbrowser.open(base_url)
                return 0
            # Something answers a healthy MockingBird `/health` on this port,
            # but it is not confirmed to be *this* installation -- for
            # example a different native install, or one forwarded from a
            # different environment such as WSL. Never silently attach to
            # it and never kill it; explain the conflict and stop.
            _alert_failure(
                f"Port {args.port} is already used by a different MockingBird "
                "installation, or another service (for example one forwarded "
                "from WSL) -- not this one. Close it, or start MockingBird "
                "with a different --port.",
                has_console=has_console,
            )
            return 2
        if not port_is_available(args.host, args.port):
            _alert_failure(
                f"Port {args.port} is already in use by another application.",
                has_console=has_console,
            )
            return 2

        try:
            preflight = run_preflight(build_frontend=not args.skip_frontend_build)
        except (DatabaseSchemaCompatibilityError, OSError, RuntimePreflightError) as error:
            _alert_failure(str(error), has_console=has_console)
            return 2

        _print_preflight(preflight)

        # Only the real launch path touches the crash marker -- `--check`
        # above returns before this point so repeated validation runs never
        # make the *next* real launch think the previous one crashed.
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

        # Mobile & Remote Experience v1: `GET /api/product/connection` (see
        # api/main.py) reads these back -- set once, here, at the one place
        # that actually knows what was launched; a bare `python -m
        # mockingbird`-free test/dev import of `api.main.app` (this
        # function never runs then) simply never sets them, and that
        # endpoint's own `getattr(..., default)` reads treat that as
        # "loopback-only, unknown otherwise," never a crash.
        app.state.bind_host = args.host
        app.state.bind_port = args.port
        app.state.network_access_allowed = args.host not in _LOOPBACK_HOSTS

        # Release Reliability & First-Run Recovery v1: `uvicorn.run(...)`
        # (the prior form here) is itself only a convenience wrapper around
        # exactly this `Config`+`Server` construction -- it never exposes
        # the `Server` it builds internally. Keeping our own reference and
        # publishing it on `app.state` (mirroring `bind_host`/`bind_port`
        # immediately above -- the one place that actually knows the real
        # running server) is what lets `POST /api/product/shutdown` (see
        # api/main.py) ask this *same* process to stop itself gracefully
        # from inside a request handler: flipping `Server.should_exit` is
        # uvicorn's own documented in-process stop mechanism, noticed by
        # its main loop on its very next iteration, and drives the exact
        # same graceful shutdown sequence (including the FastAPI `lifespan`
        # teardown that already calls `mark_clean_shutdown()` last) that an
        # interactive terminal's Ctrl+C already triggers today -- never a
        # second, parallel shutdown path. This is the only reason a
        # `Server` reference is kept at all; nothing else here reads it.
        server = build_uvicorn_server(
            app, host=args.host, port=args.port, log_config=uvicorn_log_config(log_path)
        )
        app.state.uvicorn_server = server
        serve_until_stopped(server)
        return 0
    except Exception:
        _logger.exception("MockingBird failed to start.")
        _alert_failure(
            "MockingBird could not start because of an unexpected error."
            + (f" See {log_path} for details." if log_path else ""),
            has_console=has_console,
        )
        return 2


def main() -> None:
    raise SystemExit(run())
