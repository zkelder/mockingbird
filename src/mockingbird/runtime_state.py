"""Bounded local runtime-lifecycle facts: previous-shutdown and log location.

Kept in its own module so neither `runtime.py` nor `api/main.py` needs to
import the other to reach these facts. `runtime.py` already imports from
`api.main` (deferred, inside function bodies, to avoid a real import cycle);
adding a second edge the other direction would make that fragile. This module
imports from neither, so both can depend on it safely.

Product intent: a normal user should be able to answer "did MockingBird close
cleanly last time" and "where are the logs" without knowing this is a Python
process at all. Both facts are local-only, bounded, and best-effort -- a
failure to write the marker file or open the log file never blocks startup.
"""

from __future__ import annotations

import copy
import json
import logging
import logging.handlers
from pathlib import Path
import secrets
from typing import Any

import uvicorn.config

RUNTIME_STATE_FILENAME = "runtime_state.json"
INSTANCE_IDENTITY_FILENAME = "instance_identity.json"
LOG_SUBDIRECTORY = "logs"
LOG_FILENAME = "mockingbird.log"
_MAX_LOG_BYTES = 5_000_000
_LOG_BACKUP_COUNT = 3

# Mirrors `scripts/build_local_product.py`'s `PACKAGED_BUILD_INFO_FILENAME`
# exactly -- duplicated as a literal (like `engine_runtime.py`'s own
# `PACKAGED_OBSERVATION_RUNTIME_DIRNAME` convention) rather than imported, so
# this module never depends on the build script's own module namespace.
# Keep the two values in sync.
BUILD_INFO_FILENAME = "build_info.json"

# Module-level, not per-request: these facts are fixed for the lifetime of one
# running MockingBird process and are set exactly once at startup.
_runtime_home: Path | None = None
_previous_shutdown_clean: bool | None = None
_log_path: Path | None = None


def _marker_path(runtime_home: Path) -> Path:
    return runtime_home / RUNTIME_STATE_FILENAME


def prepare_runtime_state(runtime_home: Path) -> bool | None:
    """Read the previous run's shutdown marker, then mark this run as starting.

    Returns whether the previous run using this data directory shut down
    cleanly: `True` (its normal shutdown path completed), `False` (the marker
    still says "starting" -- MockingBird did not reach its own shutdown code
    last time, for example a crash, a forced kill, or a host power loss), or
    `None` the first time MockingBird ever runs against this data directory.

    Only the real launch path should call this -- not `--check`, which must
    stay side-effect-light and must not overwrite this signal for the next
    real launch.
    """

    global _runtime_home, _previous_shutdown_clean
    _runtime_home = runtime_home
    previous_clean: bool | None = None
    try:
        raw = _marker_path(runtime_home).read_text(encoding="utf-8")
        previous_clean = json.loads(raw).get("state") == "clean"
    except (OSError, ValueError):
        previous_clean = None
    _previous_shutdown_clean = previous_clean
    try:
        _marker_path(runtime_home).write_text(
            json.dumps({"state": "starting"}), encoding="utf-8"
        )
    except OSError:
        pass
    return previous_clean


def mark_clean_shutdown() -> None:
    """Record that this run reached its normal shutdown path.

    Uses the `runtime_home` remembered from `prepare_runtime_state`, so
    callers (the API shutdown path) never need to re-resolve that directory
    themselves -- re-resolving it independently risks landing on a different
    default path than the one the running process actually started from.
    A process that never called `prepare_runtime_state` (every existing
    ASGI-transport test, which never goes through `runtime.py`) is a no-op.
    """

    if _runtime_home is None:
        return
    try:
        _marker_path(_runtime_home).write_text(
            json.dumps({"state": "clean"}), encoding="utf-8"
        )
    except OSError:
        pass


def previous_shutdown_was_clean() -> bool | None:
    return _previous_shutdown_clean


def current_runtime_home() -> Path | None:
    """The data directory the real launch path resolved, if any.

    `None` for any process that never went through `prepare_runtime_state`
    (every ASGI-transport test, a bare development server) -- exactly the
    processes for which "which local installation is this" cannot be
    answered, so callers should treat that as "not confirmed," never guess.
    """

    return _runtime_home


def resolve_instance_id(runtime_home: Path) -> str:
    """A stable identity for one local installation's own data directory.

    Created once per `runtime_home` and reused after -- the basis for
    telling "an already-running copy of this exact installation" apart from
    an unrelated service, a different MockingBird install, or one
    forwarded from another environment (for example WSL) that merely
    answers the same `/health` shape on the same port. See "Windows
    launcher defects" in docs/camera-node-pairing-persistence-design.md.

    Deliberately never derived from hostname, PID, or process name: those
    are exactly the kind of guessable, spoofable, or environment-specific
    signal a same-machine WSL/native collision would still share. A random
    token written inside the data directory itself is the smallest fact
    that is true only for "the process that already owns this directory."
    """

    path = runtime_home / INSTANCE_IDENTITY_FILENAME
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        value = payload.get("instance_id") if isinstance(payload, dict) else None
        if (
            isinstance(value, str)
            and len(value) == 32
            and all(character in "0123456789abcdef" for character in value)
        ):
            return value
    except (OSError, ValueError):
        pass
    instance_id = secrets.token_hex(16)
    try:
        runtime_home.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"instance_id": instance_id}), encoding="utf-8")
    except OSError:
        pass
    return instance_id


def _build_info_path() -> Path:
    """Where a packaged MockingBird install ships this exact build's own
    identity -- populated by `scripts/build_local_product.py`'s
    `write_build_identity`, mirroring `web_app.resolve_frontend_dist`'s
    (`web_dist`) and `engine_runtime.packaged_observation_runtime_root`'s
    (`observation_runtime`) own "packaged asset next to this installed
    package" convention exactly. Resolved from *this module's own
    installed location* (`Path(__file__)`), never `os.getcwd()`, so it
    keeps resolving correctly regardless of the process working directory
    or how MockingBird was launched. Its own function (rather than inlined
    into `resolve_build_identity`) purely so tests can redirect it the same
    way `test_engine_runtime.py` redirects `packaged_observation_runtime_
    root` -- never by writing a fixture file into this real installed
    package's own source tree."""

    return Path(__file__).resolve().parent / BUILD_INFO_FILENAME


def resolve_build_identity() -> tuple[str | None, str | None]:
    """`(git_commit, build_id)` for *this exact installed build*, if this
    process is actually running from a packaged bundle.

    `(None, None)` for anything that never went through that build step -- a
    bare development checkout, every ASGI-transport test, `pip install .`
    without the Windows packaging pipeline: the conservative "cannot confirm
    a build identity" default, matching `resolve_instance_id`'s own
    never-guess philosophy, rather than inventing one. A developer/dev-
    deployment tool (see docs/windows-dev-deployment-design.md) uses this,
    via `GET /api/product/instance`, to prove a running instance's exact
    source commit and build -- never process name, PID, or a folder name,
    none of which a caller can trust without asking the process itself.
    """

    try:
        payload = json.loads(_build_info_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None, None
    if not isinstance(payload, dict):
        return None, None
    git_commit = payload.get("git_commit")
    build_id = payload.get("build_id")
    return (
        git_commit if isinstance(git_commit, str) and git_commit else None,
        build_id if isinstance(build_id, str) and build_id else None,
    )


def configure_file_logging(runtime_home: Path) -> Path | None:
    """Prepare one fixed local log file and route ordinary app logging to it.

    A normal user should have exactly one predictable place to find logs
    regardless of how MockingBird was launched -- a terminal, a double-clicked
    packaged-bundle launcher with no console at all, or a development
    `--reload` session. This adds a root-logger handler for MockingBird's own
    `logging.getLogger(...)` calls; it never removes an existing handler.

    It deliberately does **not** capture uvicorn's own startup/access/error
    output -- uvicorn's `uvicorn`/`uvicorn.access` loggers set
    `propagate=False` (each already owns a console handler, to avoid duplicate
    output), so records never reach a root-attached handler no matter when it
    is added. `uvicorn_log_config` below is the separate, correct way to
    capture those: it must be passed to `uvicorn.run(log_config=...)` so the
    file handler is wired into uvicorn's own logger config directly.
    """

    global _log_path
    log_path = runtime_home / LOG_SUBDIRECTORY / LOG_FILENAME
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        handler = logging.handlers.RotatingFileHandler(
            log_path,
            maxBytes=_MAX_LOG_BYTES,
            backupCount=_LOG_BACKUP_COUNT,
            encoding="utf-8",
        )
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
        )
        root_logger = logging.getLogger()
        already_attached = any(
            isinstance(existing, logging.handlers.RotatingFileHandler)
            and getattr(existing, "baseFilename", None) == str(log_path)
            for existing in root_logger.handlers
        )
        if not already_attached:
            root_logger.addHandler(handler)
        # Only ever make logging *more* visible than the Python default
        # (WARNING); never quiet down a level a caller deliberately set lower.
        if root_logger.getEffectiveLevel() > logging.INFO:
            root_logger.setLevel(logging.INFO)
    except OSError:
        _log_path = None
        return None
    _log_path = log_path
    return log_path


def uvicorn_log_config(log_path: Path | None) -> dict[str, Any]:
    """Uvicorn's own default logging config, plus a file handler wired into
    its loggers.

    Pass the result to `uvicorn.run(log_config=...)`. `log_path=None` (the
    log file/directory could not be created) returns uvicorn's unmodified
    default so startup never depends on this succeeding.

    Only `uvicorn` and `uvicorn.access` need the handler added directly: both
    set `propagate=False` in uvicorn's own default config (each already owns
    a console handler, to avoid duplicate console output), so they are true
    dead ends a root-attached handler could never reach. `uvicorn.error` is a
    plain child of `uvicorn` with no handlers of its own and default
    `propagate=True`; its records already reach `uvicorn`'s handlers (now
    including this one) by that existing propagation. Adding the handler to
    `uvicorn.error` directly as well would double-write every line it logs.
    """

    config = copy.deepcopy(uvicorn.config.LOGGING_CONFIG)
    if log_path is None:
        return config
    config["handlers"]["file"] = {
        "()": "logging.handlers.RotatingFileHandler",
        "formatter": "default",
        "filename": str(log_path),
        "maxBytes": _MAX_LOG_BYTES,
        "backupCount": _LOG_BACKUP_COUNT,
        "encoding": "utf-8",
    }
    for logger_name in ("uvicorn", "uvicorn.access"):
        logger_config = config["loggers"].setdefault(logger_name, {})
        handlers = logger_config.setdefault("handlers", [])
        if "file" not in handlers:
            handlers.append("file")
    return config


def current_log_path() -> Path | None:
    return _log_path
