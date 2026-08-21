"""MockingBird Doctor: one bounded, structured operational self-check.

Answers "is this MockingBird installation healthy enough to observe
wildlife, and if not, what specifically needs attention?" -- see
docs/mockingbird-doctor-operational-health-contract.md and the "MockingBird
Doctor / self-check" entry under Gate D in docs/roadmap.md.

Design invariants
------------------
- **Never constructs `ProductRepository`.** `ProductRepository.__init__`
  unconditionally runs `initialize_database` (which can migrate a stale
  schema in place) and `seed_if_empty()` -- exactly the two side effects a
  read-only health check must never risk, and precisely the scenario
  ("schema is stale") Doctor most needs to observe honestly rather than
  silently "fix" as a side effect of merely checking. Every check below
  instead composes bare read-only engine queries (`storage.database`'s
  private-but-importable `_sqlite_integrity_check`/
  `_read_recorded_schema_version`, the same pattern
  `tests/test_persistence.py` already uses) and free functions/small direct
  SQLAlchemy Core reads against known models -- never a full repository.
- **Every check is a `(gather, interpret)` pair.** `_gather_*` functions do
  the real (bounded, isolated) I/O; `_interpret_*` functions are pure --
  they take already-gathered plain data and return a `DoctorCheckResult`,
  so they can be unit-tested with hand-built fixtures and no real database,
  camera, GPU, or network. `run_doctor` is the only place that wires a
  `_gather_*` call through a bounded timeout and hands its result to the
  matching `_interpret_*` call.
- **Only Database and Storage can fail "blocking."** Every other capability
  (backup, Camera Node, FFmpeg, detector model, species identification,
  GPU/CUDA) is optional/degradable by product doctrine -- an install with
  none of them configured, or one of them broken, remains a usable
  MockingBird install. See "Severity semantics" in the contract doc.
"""

from __future__ import annotations

import queue
import threading
import time
from collections.abc import Callable
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.engine import Engine

from mockingbird import __version__ as APP_VERSION
from mockingbird import runtime_state
from mockingbird.observation.engine_runtime import resolve_provider_config_path
from mockingbird.observation.frame_driven_provider import FrameDrivenProviderConfiguration
from mockingbird.observation.onnx_provider import OnnxCudaObservationProvider, OnnxModelBundle
from mockingbird.observation.replay import ReplayValidationError
from mockingbird.observation.unified_status import CAMERA_NODE_LAST_SEEN_STALE_AFTER_SECONDS
from mockingbird.playback.rtsp_bridge import is_ffmpeg_available
from mockingbird.runtime import resolve_runtime_home
from mockingbird.species.bioclip_adapter import BioClipAdapterConfig, get_bioclip_status
from mockingbird.species.bioclip_runtime import (
    resolve_bioclip_embedding_cache_path,
    resolve_bioclip_labels_path,
    resolve_bioclip_model_dir,
)
from mockingbird.storage.backup import BACKUP_ROOT_ENV_VAR, LocalBackupManager
from mockingbird.storage.database import (
    CURRENT_DATABASE_SCHEMA_VERSION,
    DB_URL_ENV_VAR,
    MEDIA_ROOT_ENV_VAR,
    _read_recorded_schema_version,  # noqa: PLC2701 - deliberate reuse; see module docstring
    _sqlite_integrity_check,  # noqa: PLC2701 - deliberate reuse; see module docstring
    create_database_engine,
    database_schema_version_is_compatible,
    probe_local_storage_disk,
    sqlite_database_path,
)
from mockingbird.storage.models import (
    CameraSourceModel,
    MonitoringExposureIntervalModel,
    StreamModel,
    StreamRuntimeCheckpointModel,
)
from mockingbird.time_utils import normalize_utc, resolve_host_local_timezone
from mockingbird.web_app import find_workspace_root

T = TypeVar("T")

# A Doctor-specific, disclosed threshold: no canonical backup-staleness
# policy exists anywhere in the product yet (unlike the storage low-disk
# thresholds below, which are reused, not invented). See "Backup" in the
# contract doc.
BACKUP_STALE_AFTER_DAYS = 30

DEFAULT_CHECK_TIMEOUT_SECONDS = 5.0
# The detector model bundle can be a large (~100s of MB) file; its bounded
# integrity check reads and hashes it once, so it gets a longer budget than
# every other check. Still bounded -- see "Timeouts" in the contract doc.
MODEL_CHECK_TIMEOUT_SECONDS = 15.0

_CAMERA_ATTENTION_CHECKPOINT_STATES = frozenset({"blocked", "interrupted"})
# `_camera_setup_source_kind` (product_repository.py) maps the `camera_node`
# provider to `SourceKind.integration`; no other currently-implemented
# provider maps there today, so this is a reasonably precise (not perfectly
# guaranteed-future-proof) signal that a Camera Node Stream is configured,
# without needing the provider-configuration table itself (see the contract
# doc's "Known v1 scope limits").
_CAMERA_NODE_SOURCE_KIND = "integration"
_FFMPEG_DEPENDENT_SOURCE_KINDS = frozenset({"rtsp", "local_camera"})
# Camera Node Connectivity & Recovery Diagnosis v1 (real 2026-08-20 field
# incident): comfortably longer than both the ~45s normal checkpoint cadence
# (Today Coverage Truth v1) and the default bounded reconnect budget (6
# attempts x 12s backoff = ~72s -- see `AnalysisStreamRetryPolicy`), so an
# ordinary, already-recovering reconnect never trips this WARN; a real,
# sustained Camera Node outage still surfaces within a few minutes. Shared
# with `unified_status.camera_node_facts` (Boot Identity + Autonomous
# Recovery v1) -- see that constant's own docstring; imported rather than
# duplicated so this judgment stays one number, not two.
_CAMERA_NODE_STALE_AFTER_SECONDS = CAMERA_NODE_LAST_SEEN_STALE_AFTER_SECONDS
# Boot Identity + Autonomous Recovery v1: bounded restart-instability
# suspicion, derived only from the bounded (<=5-entry) recent-boot-
# transition window `ProductRepository._record_camera_node_boot_observation`
# already caps -- never an unbounded historical ledger (milestone
# instruction #10). Three real reboots inside fifteen minutes is well
# outside any plausible deliberate maintenance action (a normal Pi reboot
# takes ~55s to recover -- see "Real hardware acceptance findings" in
# docs/camera-node-installer-design.md) and is the threshold this milestone
# treats as suspicious rather than coincidental.
_CAMERA_NODE_INSTABILITY_MINIMUM_TRANSITIONS = 3
_CAMERA_NODE_INSTABILITY_WINDOW_SECONDS = 900.0


class DoctorStatus(str, Enum):
    """Bounded, machine-readable per-check outcome."""

    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"
    SKIPPED = "SKIPPED"


class DoctorOverallStatus(str, Enum):
    """Bounded, deterministically-derived install-wide outcome."""

    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNHEALTHY = "UNHEALTHY"


class DoctorRecoverability(str, Enum):
    """How serious a non-PASS outcome is for the product's core loop.

    `BLOCKING` is reserved for Database/Storage failures that mean the
    install cannot observe wildlife at all. `DEGRADED` means a real problem
    exists but the core loop still works with a reduced capability.
    `INFORMATIONAL` means an optional capability was never configured in
    the first place -- not a problem to fix.
    """

    BLOCKING = "blocking"
    DEGRADED = "degraded"
    INFORMATIONAL = "informational"


class DoctorCheckCode(str, Enum):
    """The smallest local, stable Doctor check-code namespace.

    No pre-existing shared error/diagnostic-code taxonomy covers this
    surface (every MockingBird subsystem defines its own bare
    ``XxxError(ValueError)`` with free-form string "codes" -- confirmed by
    direct code archaeology; see the contract doc's "Reuse the error
    taxonomy"). This enum is Doctor's own, deliberately small and closed.
    """

    APPLICATION = "application"
    DATABASE_CONNECTIVITY = "database_connectivity"
    DATABASE_SCHEMA = "database_schema"
    STORAGE = "storage"
    BACKUP = "backup"
    CAMERA_NODE = "camera_node"
    FFMPEG = "ffmpeg"
    DETECTOR_MODEL = "detector_model"
    SPECIES_IDENTIFICATION = "species_identification"
    GPU_CUDA = "gpu_cuda"
    CLOCK = "clock"


class DoctorCheckResult(BaseModel):
    """One bounded, independently-run Doctor check outcome."""

    model_config = ConfigDict(use_enum_values=False)

    code: DoctorCheckCode
    component: str
    status: DoctorStatus
    summary: str
    detail: str | None = None
    recoverability: DoctorRecoverability | None = None
    user_action: str | None = None
    diagnostic_context: dict[str, Any] | None = None
    duration_ms: float = 0.0


class DoctorReport(BaseModel):
    """One complete MockingBird Doctor run."""

    overall_status: DoctorOverallStatus
    generated_at: datetime
    app_version: str
    duration_ms: float
    checks: list[DoctorCheckResult] = Field(default_factory=list)


class DoctorEnvironment(BaseModel):
    """Resolved local paths Doctor checks run against.

    Deliberately resolved independently of `storage.database`'s own
    cwd-relative defaults (`DEFAULT_DB_URL`/`DEFAULT_MEDIA_ROOT` are plain
    relative strings, only ever anchored correctly today because
    `runtime.run_preflight` `os.chdir()`s the whole process into
    `runtime_home` first). Doctor must work from any starting working
    directory without mutating global process state, so it anchors every
    default to `runtime_home` explicitly instead.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    runtime_home: Path
    db_url: str
    media_root: Path
    backup_root: Path


def resolve_doctor_environment(*, runtime_home: Path | None = None) -> DoctorEnvironment:
    import os

    # Mirrors `runtime.run_preflight`'s own resolution
    # (`resolve_runtime_home(find_workspace_root())`) exactly: without this,
    # a real development checkout with no `MOCKINGBIRD_HOME` set would
    # silently resolve to the platform XDG/AppData default instead of the
    # checkout's own `data/` directory a normal `python -m mockingbird`
    # launch actually uses -- pointing Doctor at an empty location that
    # happens to exist rather than the real installation being diagnosed.
    home = runtime_home or resolve_runtime_home(find_workspace_root())
    db_url = os.getenv(DB_URL_ENV_VAR) or f"sqlite:///{home / 'data' / 'mockingbird.sqlite3'}"
    media_root = Path(os.getenv(MEDIA_ROOT_ENV_VAR) or str(home / "data" / "media" / "imports"))
    backup_root = Path(os.getenv(BACKUP_ROOT_ENV_VAR) or str(home / "data" / "backups"))
    return DoctorEnvironment(runtime_home=home, db_url=db_url, media_root=media_root, backup_root=backup_root)


# --------------------------------------------------------------------------
# Bounded execution
# --------------------------------------------------------------------------


def _run_bounded(fn: Callable[[], T], *, timeout_seconds: float) -> tuple[T | None, BaseException | None, bool]:
    """Run `fn()` with a bounded wall-clock timeout.

    Returns `(result, error, timed_out)`. Uses a daemon `threading.Thread`
    rather than `concurrent.futures.ThreadPoolExecutor`: a pool's worker
    threads are joined by an `atexit` hook
    (`concurrent.futures.thread._python_exit`), so a genuinely wedged
    synchronous call would still block *process* exit even after
    `.result(timeout=...)` gave up -- silently defeating "Doctor must not
    hang forever." A daemon thread can never block interpreter shutdown,
    so an abandoned, still-running check cannot keep the Doctor process
    (or its test) alive past this function's own return.
    """

    result_queue: queue.Queue[tuple[str, Any]] = queue.Queue(maxsize=1)

    def _worker() -> None:
        try:
            result_queue.put(("ok", fn()))
        except BaseException as error:  # noqa: BLE001 - isolate any probe failure, by design
            result_queue.put(("error", error))

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()
    try:
        outcome, payload = result_queue.get(timeout=timeout_seconds)
    except queue.Empty:
        return None, None, True
    if outcome == "error":
        return None, payload, False
    return payload, None, False


def _bounded_exception_detail(error: BaseException, *, max_length: int = 200) -> str:
    """A short, advanced-use-only diagnostic string for `diagnostic_context`.

    Never used for `summary`/`detail` (the always-shown fields) -- see
    "Actionability" in the contract doc: a raw Python exception must never
    be the normal user-facing message.
    """

    text = f"{type(error).__name__}: {error}"
    return text if len(text) <= max_length else text[: max_length - 1] + "…"


def _execute_check_returning_gathered(
    *,
    code: DoctorCheckCode,
    component: str,
    gather: Callable[[], dict[str, Any]] | None,
    interpret: Callable[[dict[str, Any]], DoctorCheckResult],
    timeout_seconds: float = DEFAULT_CHECK_TIMEOUT_SECONDS,
    skip_reason: str | None = None,
    blocking_on_failure: bool = False,
) -> tuple[DoctorCheckResult, dict[str, Any] | None]:
    """Run one check's gather (bounded) + interpret (pure) pair.

    Timeout and unexpected-exception handling live here, once, so every
    check gets identical isolation (item 11: "one broken check must not
    prevent the rest") without each `_interpret_*` needing its own
    try/except for the unexpected case. Also returns the raw gathered dict
    (or `None` on skip/timeout/error) so a caller that needs a side artifact
    the interpret step doesn't surface (for example, an already-open
    database `Engine` other checks can reuse) doesn't have to re-run the
    gather a second time outside the bounded/isolated path.

    `blocking_on_failure` must be `True` only for Database/Storage: an
    *unexpected* exception or timeout while gathering one of those two
    still means "this install's core loop cannot be trusted to work,"
    exactly as much as the interpret-level failures those checks already
    report as `BLOCKING` -- see "Only Database and Storage can fail
    blocking" in the module docstring. Every other check's own gather
    failing unexpectedly stays `DEGRADED`: an optional capability that
    broke in a way its own interpret function didn't anticipate is still
    only a degradation, never a reason to call the whole install unhealthy.
    """

    if skip_reason is not None:
        return DoctorCheckResult(code=code, component=component, status=DoctorStatus.SKIPPED, summary=skip_reason), None

    failure_recoverability = DoctorRecoverability.BLOCKING if blocking_on_failure else DoctorRecoverability.DEGRADED

    started = time.monotonic()
    if gather is None:
        gathered: dict[str, Any] | None = {}
        error: BaseException | None = None
        timed_out = False
    else:
        gathered, error, timed_out = _run_bounded(gather, timeout_seconds=timeout_seconds)
    duration_ms = (time.monotonic() - started) * 1000

    if timed_out:
        result = DoctorCheckResult(
            code=code,
            component=component,
            status=DoctorStatus.FAIL if blocking_on_failure else DoctorStatus.WARN,
            summary=f"{component} check did not finish within {timeout_seconds:.0f}s and was abandoned.",
            recoverability=failure_recoverability,
            user_action="Re-run MockingBird Doctor. If this keeps happening, check for a stuck disk, network, or process.",
        )
    elif error is not None:
        result = DoctorCheckResult(
            code=code,
            component=component,
            status=DoctorStatus.FAIL,
            summary=f"{component} check failed unexpectedly.",
            recoverability=failure_recoverability,
            diagnostic_context={"exception": _bounded_exception_detail(error)},
        )
    else:
        result = interpret(gathered or {})

    return result.model_copy(update={"duration_ms": duration_ms}), gathered


def _execute_check(
    *,
    code: DoctorCheckCode,
    component: str,
    gather: Callable[[], dict[str, Any]] | None,
    interpret: Callable[[dict[str, Any]], DoctorCheckResult],
    timeout_seconds: float = DEFAULT_CHECK_TIMEOUT_SECONDS,
    skip_reason: str | None = None,
    blocking_on_failure: bool = False,
) -> DoctorCheckResult:
    """`_execute_check_returning_gathered`, for the common case that only needs the result."""

    result, _gathered = _execute_check_returning_gathered(
        code=code,
        component=component,
        gather=gather,
        interpret=interpret,
        timeout_seconds=timeout_seconds,
        skip_reason=skip_reason,
        blocking_on_failure=blocking_on_failure,
    )
    return result


# --------------------------------------------------------------------------
# Application / runtime identity
# --------------------------------------------------------------------------


def _peek_previous_shutdown_state(runtime_home: Path) -> bool | None:
    """Read-only peek at the previous-run marker file.

    Deliberately does NOT call `runtime_state.prepare_runtime_state`, which
    both reads *and* unconditionally overwrites the marker with
    `{"state": "starting"}` -- exactly the side effect `runtime.run()`'s
    `--check` path already avoids for the identical reason (see
    `prepare_runtime_state`'s own docstring). Doctor must stay read-only, so
    it duplicates only the read half, using the module's own public
    filename constant.
    """

    import json

    marker_path = runtime_home / runtime_state.RUNTIME_STATE_FILENAME
    try:
        payload = json.loads(marker_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    state = payload.get("state") if isinstance(payload, dict) else None
    if state == "clean":
        return True
    if state == "starting":
        return False
    return None


def _gather_application(runtime_home: Path) -> dict[str, Any]:
    git_commit, build_id = runtime_state.resolve_build_identity()
    shutdown_clean = _peek_previous_shutdown_state(runtime_home)
    return {"git_commit": git_commit, "build_id": build_id, "shutdown_clean": shutdown_clean}


def _interpret_application(gathered: dict[str, Any]) -> DoctorCheckResult:
    context = {"git_commit": gathered.get("git_commit"), "build_id": gathered.get("build_id")}
    if gathered.get("shutdown_clean") is False:
        return DoctorCheckResult(
            code=DoctorCheckCode.APPLICATION,
            component="Application",
            status=DoctorStatus.WARN,
            summary="The previous MockingBird run did not shut down cleanly.",
            detail="This can happen after a crash, a forced quit, or a power loss.",
            recoverability=DoctorRecoverability.DEGRADED,
            user_action="Check the log file for the previous session's error, then restart MockingBird normally.",
            diagnostic_context=context,
        )
    return DoctorCheckResult(
        code=DoctorCheckCode.APPLICATION,
        component="Application",
        status=DoctorStatus.PASS,
        summary=f"MockingBird {APP_VERSION} is running.",
        diagnostic_context=context,
    )


# --------------------------------------------------------------------------
# Database
# --------------------------------------------------------------------------


def _gather_database_connectivity(db_url: str) -> dict[str, Any]:
    # Check file existence *before* ever calling `create_database_engine`:
    # SQLite auto-creates an empty file the moment anything actually
    # connects to a `sqlite:///` URL whose file does not yet exist. A
    # never-launched install (no database created yet) is an honest,
    # calm, non-alarming state Doctor must be able to report without
    # itself becoming the thing that creates the file -- see the module
    # docstring's "never mutate" invariant.
    db_path = sqlite_database_path(db_url)
    if not db_path.is_file():
        return {"database_exists": False}
    engine = create_database_engine(db_url)
    integrity_check = _sqlite_integrity_check(engine)
    return {"database_exists": True, "engine": engine, "integrity_check": integrity_check}


def _interpret_database_connectivity(gathered: dict[str, Any], *, database_path: Path) -> DoctorCheckResult:
    context = {"database_path": str(database_path), "database_exists": gathered.get("database_exists", False)}
    if not gathered.get("database_exists"):
        return DoctorCheckResult(
            code=DoctorCheckCode.DATABASE_CONNECTIVITY,
            component="Database",
            status=DoctorStatus.PASS,
            summary="No database has been created yet.",
            detail="This is expected before MockingBird's first launch.",
            recoverability=DoctorRecoverability.INFORMATIONAL,
            diagnostic_context=context,
        )
    integrity_check = gathered.get("integrity_check")
    if integrity_check != "ok":
        return DoctorCheckResult(
            code=DoctorCheckCode.DATABASE_CONNECTIVITY,
            component="Database",
            status=DoctorStatus.FAIL,
            summary="The database failed a basic integrity check.",
            detail=f"SQLite integrity check reported: {integrity_check}",
            recoverability=DoctorRecoverability.BLOCKING,
            user_action="Restore from a recent backup (Local Data page), or contact support with this report.",
            diagnostic_context=context,
        )
    return DoctorCheckResult(
        code=DoctorCheckCode.DATABASE_CONNECTIVITY,
        component="Database",
        status=DoctorStatus.PASS,
        summary="Database is reachable and passed a basic integrity check.",
        diagnostic_context=context,
    )


def _gather_database_schema(engine: Engine) -> dict[str, Any]:
    version = _read_recorded_schema_version(engine)
    return {"version": version}


def _interpret_database_schema(gathered: dict[str, Any]) -> DoctorCheckResult:
    version = gathered.get("version")
    context = {"schema_version": version, "current_schema_version": CURRENT_DATABASE_SCHEMA_VERSION}
    if version is None or not database_schema_version_is_compatible(version):
        return DoctorCheckResult(
            code=DoctorCheckCode.DATABASE_SCHEMA,
            component="Database",
            status=DoctorStatus.FAIL,
            summary="The database schema is not compatible with this version of MockingBird.",
            detail=(
                "The database was created by a different, incompatible MockingBird version."
                if version is not None
                else "No schema version record was found."
            ),
            recoverability=DoctorRecoverability.BLOCKING,
            user_action="Run the migration/upgrade for your installed MockingBird version, or restore a compatible backup.",
            diagnostic_context=context,
        )
    if version < CURRENT_DATABASE_SCHEMA_VERSION:
        return DoctorCheckResult(
            code=DoctorCheckCode.DATABASE_SCHEMA,
            component="Database",
            status=DoctorStatus.WARN,
            summary="The database schema is older than this MockingBird version expects.",
            detail="It will be migrated automatically the next time the application starts normally.",
            recoverability=DoctorRecoverability.DEGRADED,
            user_action="Start MockingBird normally once to complete the migration.",
            diagnostic_context=context,
        )
    return DoctorCheckResult(
        code=DoctorCheckCode.DATABASE_SCHEMA,
        component="Database",
        status=DoctorStatus.PASS,
        summary="Database schema is current.",
        diagnostic_context=context,
    )


# --------------------------------------------------------------------------
# Storage
# --------------------------------------------------------------------------


def _gather_storage(*, media_root: Path, database_directory: Path) -> dict[str, Any]:
    media_root_exists = media_root.is_dir()
    probe_directory = database_directory if database_directory.is_dir() else media_root
    disk_status = probe_local_storage_disk(probe_directory) if probe_directory.is_dir() else None
    return {
        "media_root_exists": media_root_exists,
        "media_root": str(media_root),
        "total_bytes": disk_status.total_bytes if disk_status else 0,
        "free_bytes": disk_status.free_bytes if disk_status else 0,
        "is_writable": disk_status.is_writable if disk_status else False,
        "is_low_space": disk_status.is_low_space if disk_status else False,
        "probed_directory": str(probe_directory),
    }


def _interpret_storage(gathered: dict[str, Any], *, database_exists: bool) -> DoctorCheckResult:
    context = {
        "media_root": gathered.get("media_root"),
        "disk_total_bytes": gathered.get("total_bytes"),
        "disk_free_bytes": gathered.get("free_bytes"),
    }
    if not gathered.get("media_root_exists"):
        # `ProductRepository.__init__` does not eagerly create the media
        # root either -- confirmed directly, not assumed -- it is created
        # lazily on first real media write. On an established install
        # (database already exists) a missing folder is a genuine problem;
        # on a never-launched install (no database yet either) it is the
        # same honest "not started yet" state the Database check already
        # reports as informational, not a defect.
        if not database_exists:
            return DoctorCheckResult(
                code=DoctorCheckCode.STORAGE,
                component="Storage",
                status=DoctorStatus.PASS,
                summary="The media storage folder has not been created yet.",
                detail="This is expected before MockingBird's first launch or before any camera has been added.",
                recoverability=DoctorRecoverability.INFORMATIONAL,
                diagnostic_context=context,
            )
        return DoctorCheckResult(
            code=DoctorCheckCode.STORAGE,
            component="Storage",
            status=DoctorStatus.FAIL,
            summary="The configured media storage folder does not exist.",
            recoverability=DoctorRecoverability.BLOCKING,
            user_action="Create the configured storage folder, or check the MOCKINGBIRD_MEDIA_ROOT/MOCKINGBIRD_HOME setting.",
            diagnostic_context=context,
        )
    if not gathered.get("is_writable"):
        return DoctorCheckResult(
            code=DoctorCheckCode.STORAGE,
            component="Storage",
            status=DoctorStatus.FAIL,
            summary="The storage folder is not writable.",
            recoverability=DoctorRecoverability.BLOCKING,
            user_action="Check folder permissions for the configured MockingBird data folder.",
            diagnostic_context=context,
        )
    if gathered.get("is_low_space"):
        free_gb = gathered.get("free_bytes", 0) / 1_000_000_000
        return DoctorCheckResult(
            code=DoctorCheckCode.STORAGE,
            component="Storage",
            status=DoctorStatus.WARN,
            summary=f"Free disk space is low ({free_gb:.1f} GB free).",
            recoverability=DoctorRecoverability.DEGRADED,
            user_action="Free up disk space, or move MockingBird's data folder to a drive with more room.",
            diagnostic_context=context,
        )
    return DoctorCheckResult(
        code=DoctorCheckCode.STORAGE,
        component="Storage",
        status=DoctorStatus.PASS,
        summary="Storage is writable with sufficient free space.",
        diagnostic_context=context,
    )


# --------------------------------------------------------------------------
# Backup
# --------------------------------------------------------------------------


def _gather_backup(*, db_url: str, media_root: Path, backup_root: Path) -> dict[str, Any]:
    manager = LocalBackupManager(db_url=db_url, media_root=media_root, backup_root=backup_root)
    library = manager.list_backups()
    most_recent = library.backups[0] if library.backups else None
    return {
        "backup_count": len(library.backups),
        "unreadable_backup_count": library.unreadable_backup_count,
        "most_recent_created_at": most_recent.created_at.isoformat() if most_recent else None,
    }


def _interpret_backup(gathered: dict[str, Any], *, now: datetime) -> DoctorCheckResult:
    context = {
        "backup_count": gathered.get("backup_count", 0),
        "unreadable_backup_count": gathered.get("unreadable_backup_count", 0),
        "most_recent_backup_at": gathered.get("most_recent_created_at"),
    }
    if not gathered.get("backup_count"):
        return DoctorCheckResult(
            code=DoctorCheckCode.BACKUP,
            component="Backup",
            status=DoctorStatus.PASS,
            summary="No backups have been created yet.",
            recoverability=DoctorRecoverability.INFORMATIONAL,
            user_action="Create your first backup from the Local Data page.",
            diagnostic_context=context,
        )
    most_recent_at = datetime.fromisoformat(gathered["most_recent_created_at"])
    age_days = (now - most_recent_at).total_seconds() / 86400
    context["most_recent_backup_age_days"] = round(age_days, 1)
    if age_days > BACKUP_STALE_AFTER_DAYS:
        return DoctorCheckResult(
            code=DoctorCheckCode.BACKUP,
            component="Backup",
            status=DoctorStatus.WARN,
            summary=f"The most recent backup is {age_days:.0f} days old.",
            recoverability=DoctorRecoverability.DEGRADED,
            user_action="Create a fresh backup from the Local Data page.",
            diagnostic_context=context,
        )
    return DoctorCheckResult(
        code=DoctorCheckCode.BACKUP,
        component="Backup",
        status=DoctorStatus.PASS,
        summary=f"{gathered['backup_count']} backup(s) found; most recent is {age_days:.0f} day(s) old.",
        diagnostic_context=context,
    )


# --------------------------------------------------------------------------
# Camera Node / Streams
# --------------------------------------------------------------------------


def _gather_camera_node(engine: Engine) -> dict[str, Any]:
    with engine.connect() as connection:
        sources = connection.execute(select(CameraSourceModel.id, CameraSourceModel.kind)).all()
        stream_count = len(connection.execute(select(StreamModel.id)).all())
        # Boot Identity + Autonomous Recovery v1: the durable, session-
        # independent facts `ProductRepository.record_observation_exposure_
        # frame` now checkpoints on `CameraSourceModel` -- read here purely
        # to let Doctor answer honestly during the exact gap its own prior
        # milestone (Camera Node Connectivity & Recovery Diagnosis v1)
        # disclosed as open: "the gap between a session giving up entirely
        # and the next Start," where no open `MonitoringExposureInterval`
        # exists at all for the staleness check above to read.
        camera_node_sources = connection.execute(
            select(
                CameraSourceModel.id,
                CameraSourceModel.camera_node_last_seen_at,
                CameraSourceModel.camera_node_boot_id,
                CameraSourceModel.camera_node_service_version,
                CameraSourceModel.camera_node_recent_boot_transitions_json,
            ).where(CameraSourceModel.kind == _CAMERA_NODE_SOURCE_KIND)
        ).all()
        open_interval_stream_ids = {
            row[0]
            for row in connection.execute(
                select(MonitoringExposureIntervalModel.stream_id).where(
                    MonitoringExposureIntervalModel.ended_at.is_(None)
                )
            ).all()
        }
        checkpoint_states = [
            row[0] for row in connection.execute(select(StreamRuntimeCheckpointModel.actual_state)).all()
        ]
        # `StreamRuntimeCheckpointModel` above belongs exclusively to the
        # legacy live_monitoring lane -- the accepted camera_node
        # Observation Engine lane never writes it (confirmed: `engine_
        # runtime.py` has no reference to that model at all), so Doctor was
        # completely blind to a camera_node Stream's own runtime health.
        # That lane DOES already checkpoint `MonitoringExposureInterval
        # Model.last_confirmed_fresh_at` on every healthy analysis-stream
        # batch (Today Coverage Truth v1); the single stalest still-open
        # camera_node interval is a real, durable, read-only signal of
        # "Camera Node unavailable / last frame N minutes ago" -- exactly
        # what the real 2026-08-20 field incident showed Doctor could not
        # answer. Raw timestamp only, matching `_gather_backup`'s own
        # convention: all datetime math stays in `_interpret_camera_node`,
        # which stays pure and unit-testable with a fixed `now`.
        stalest_camera_node_interval = connection.execute(
            select(
                MonitoringExposureIntervalModel.stream_id,
                MonitoringExposureIntervalModel.last_confirmed_fresh_at,
            )
            .join(
                CameraSourceModel,
                CameraSourceModel.id == MonitoringExposureIntervalModel.source_id,
            )
            .where(
                MonitoringExposureIntervalModel.ended_at.is_(None),
                CameraSourceModel.kind == _CAMERA_NODE_SOURCE_KIND,
            )
            .order_by(MonitoringExposureIntervalModel.last_confirmed_fresh_at.asc())
            .limit(1)
        ).first()
    return {
        "source_count": len(sources),
        "source_kinds": [row[1] for row in sources],
        "stream_count": stream_count,
        "currently_monitored_count": len(open_interval_stream_ids),
        "attention_count": sum(1 for state in checkpoint_states if state in _CAMERA_ATTENTION_CHECKPOINT_STATES),
        "stalest_camera_node_stream_id": stalest_camera_node_interval[0] if stalest_camera_node_interval else None,
        # SQLite's `DateTime(timezone=True)` does not itself preserve tzinfo
        # across a write/read round trip (see product_repository.py's own
        # documented convention for this exact column) -- a raw read here
        # comes back naive, which would otherwise later fail to subtract
        # against `_interpret_camera_node`'s aware `now` the instant any
        # camera_node Stream had a real, currently-open exposure interval
        # (the ordinary actively-observing state, not only a stale one).
        "stalest_camera_node_fresh_at": (
            normalize_utc(stalest_camera_node_interval[1]).isoformat() if stalest_camera_node_interval else None
        ),
        # Boot Identity + Autonomous Recovery v1: durable, session-
        # independent facts -- valid (and often the *only* evidence
        # available) even when no Observation Engine session has run
        # recently enough to leave an open exposure interval above. Picks
        # the single most-recently-seen camera_node Source when more than
        # one is configured (today's supported shape is one Camera Node per
        # Source, but this stays correct if that ever changes); raw
        # timestamps only, matching `stalest_camera_node_fresh_at`'s own
        # convention -- all datetime math stays in `_interpret_camera_node`.
        "camera_node_last_seen_at": (
            normalize_utc(
                max((row[1] for row in camera_node_sources if row[1] is not None), default=None)
            ).isoformat()
            if any(row[1] is not None for row in camera_node_sources)
            else None
        ),
        "camera_node_boot_id": next((row[2] for row in camera_node_sources if row[2]), None),
        "camera_node_service_version": next((row[3] for row in camera_node_sources if row[3]), None),
        "camera_node_recent_boot_transitions_json": next(
            (row[4] for row in camera_node_sources if row[4]), None
        ),
    }


def _recent_camera_node_boot_transitions(
    transitions_json: str | None, *, now: datetime
) -> list[dict[str, Any]]:
    """Parse the bounded (<=5-entry) recent-boot-transition JSON and return
    only the entries within `_CAMERA_NODE_INSTABILITY_WINDOW_SECONDS` of
    `now`. Never raises on malformed/legacy data -- an unreadable or absent
    history is honestly "no instability evidence available," not a Doctor
    failure."""

    if not transitions_json:
        return []
    import json

    try:
        entries = json.loads(transitions_json)
    except (TypeError, ValueError):
        return []
    if not isinstance(entries, list):
        return []
    recent: list[dict[str, Any]] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        first_seen_at_raw = entry.get("first_seen_at")
        if not isinstance(first_seen_at_raw, str):
            continue
        try:
            first_seen_at = normalize_utc(datetime.fromisoformat(first_seen_at_raw))
        except ValueError:
            continue
        if (now - first_seen_at).total_seconds() <= _CAMERA_NODE_INSTABILITY_WINDOW_SECONDS:
            recent.append(entry)
    return recent


def _interpret_camera_node(gathered: dict[str, Any], *, now: datetime) -> DoctorCheckResult:
    source_count = gathered.get("source_count", 0)
    camera_node_configured = _CAMERA_NODE_SOURCE_KIND in (gathered.get("source_kinds") or [])
    context = {
        "configured_source_count": source_count,
        "configured_stream_count": gathered.get("stream_count", 0),
        "currently_monitored_stream_count": gathered.get("currently_monitored_count", 0),
        "camera_node_configured": camera_node_configured,
    }
    if source_count == 0:
        return DoctorCheckResult(
            code=DoctorCheckCode.CAMERA_NODE,
            component="Camera Node",
            status=DoctorStatus.PASS,
            summary="No cameras are configured yet.",
            detail="Add a camera from the Streams page to start observing.",
            diagnostic_context=context,
        )
    attention_count = gathered.get("attention_count", 0)
    if attention_count > 0:
        return DoctorCheckResult(
            code=DoctorCheckCode.CAMERA_NODE,
            component="Camera Node",
            status=DoctorStatus.WARN,
            summary=f"{attention_count} of {gathered.get('stream_count', 0)} configured Stream(s) need attention.",
            detail="A Stream's last-known runtime state is blocked or interrupted.",
            recoverability=DoctorRecoverability.DEGRADED,
            user_action="Open the affected Stream's camera health details, check its network/cable connection, or restart its Camera Node.",
            diagnostic_context=context,
        )
    if gathered.get("camera_node_boot_id"):
        context["camera_node_boot_id"] = gathered["camera_node_boot_id"]
    if gathered.get("camera_node_service_version"):
        context["camera_node_service_version"] = gathered["camera_node_service_version"]
    # Boot Identity + Autonomous Recovery v1: bounded (<=5-entry) recent
    # boot-transition evidence -- see `ProductRepository._record_camera_
    # node_boot_observation`. Checked ahead of the staleness branches below:
    # a Node that keeps coming back only to reboot again can show a
    # deceptively *recent* last-seen timestamp while still being genuinely
    # unstable, so this must be distinguishable from plain "offline" --
    # exactly the gap named in "Boot loop / repeated restart" in
    # docs/camera-node-installer-design.md.
    recent_transitions = _recent_camera_node_boot_transitions(
        gathered.get("camera_node_recent_boot_transitions_json"), now=now,
    )
    if len(recent_transitions) >= _CAMERA_NODE_INSTABILITY_MINIMUM_TRANSITIONS:
        context["recent_boot_transition_count"] = len(recent_transitions)
        return DoctorCheckResult(
            code=DoctorCheckCode.CAMERA_NODE,
            component="Camera Node",
            status=DoctorStatus.WARN,
            summary=(
                f"Camera Node restart/boot instability suspected -- "
                f"{len(recent_transitions)} reboots observed recently."
            ),
            detail="The Node's boot identity has changed several times in a short window.",
            recoverability=DoctorRecoverability.DEGRADED,
            user_action="Check the Camera Node's power supply, boot media, and journal (journalctl -u mockingbird-camera-node) for a repeated startup failure.",
            diagnostic_context=context,
        )
    # Camera Node Connectivity & Recovery Diagnosis v1: the camera_node
    # Observation Engine lane's own honest freshness signal, independent of
    # `StreamRuntimeCheckpointModel` above (that lane never writes it -- see
    # `_gather_camera_node`). A currently-open exposure interval whose last
    # confirmed-fresh checkpoint has gone stale well past both the normal
    # checkpoint cadence and the bounded reconnect budget means the Camera
    # Node has stopped delivering frames. Read-only: this never initiates,
    # arms, or otherwise touches monitoring itself -- it only reads a
    # timestamp an already-running session already recorded. Known v1 scope
    # limit, disclosed rather than solved here: if more than one Stream
    # needs attention across the two lanes at once, only one WARN surfaces
    # per Doctor run (the `attention_count` branch above takes precedence) --
    # matching how every other Doctor check already reports one status per
    # component, not a fix this milestone's small integration attempts.
    stalest_fresh_at_raw = gathered.get("stalest_camera_node_fresh_at")
    if stalest_fresh_at_raw:
        stalest_fresh_at = datetime.fromisoformat(stalest_fresh_at_raw)
        staleness_seconds = (now - stalest_fresh_at).total_seconds()
        context["stalest_camera_node_staleness_minutes"] = round(staleness_seconds / 60, 1)
        if staleness_seconds > _CAMERA_NODE_STALE_AFTER_SECONDS:
            staleness_minutes = max(1, round(staleness_seconds / 60))
            return DoctorCheckResult(
                code=DoctorCheckCode.CAMERA_NODE,
                component="Camera Node",
                status=DoctorStatus.WARN,
                summary=f"Camera Node unavailable -- last frame ~{staleness_minutes} minute(s) ago.",
                detail="A Stream is still marked as observing, but no fresh frame has arrived recently.",
                recoverability=DoctorRecoverability.DEGRADED,
                user_action="Check the affected Stream's camera health details, its network/cable connection, or restart its Camera Node.",
                diagnostic_context=context,
            )
    elif gathered.get("camera_node_last_seen_at"):
        # Boot Identity + Autonomous Recovery v1: closes the gap the prior
        # milestone explicitly disclosed as open -- "the gap between a
        # session giving up entirely... and the next Start," where no open
        # exposure interval exists at all for the branch above to read.
        # `camera_node_last_seen_at` is durable and session-independent
        # (see `_gather_camera_node`), so it remains valid evidence exactly
        # in that gap. Never fabricates a specific cause (SD corruption,
        # power failure) from mere unreachability -- only "offline, last
        # seen" -- see "Product-health semantics" in
        # docs/camera-node-installer-design.md.
        last_seen_at = datetime.fromisoformat(gathered["camera_node_last_seen_at"])
        staleness_seconds = (now - last_seen_at).total_seconds()
        context["camera_node_last_seen_staleness_minutes"] = round(staleness_seconds / 60, 1)
        if staleness_seconds > _CAMERA_NODE_STALE_AFTER_SECONDS:
            staleness_minutes = max(1, round(staleness_seconds / 60))
            return DoctorCheckResult(
                code=DoctorCheckCode.CAMERA_NODE,
                component="Camera Node",
                status=DoctorStatus.WARN,
                summary=f"Camera Node offline -- last seen ~{staleness_minutes} minute(s) ago.",
                detail="No Observation Engine session is currently open for this Camera Node, and its last confirmed contact has gone stale.",
                recoverability=DoctorRecoverability.DEGRADED,
                user_action="Check the Camera Node's power, network connection, and journal (journalctl -u mockingbird-camera-node).",
                diagnostic_context=context,
            )
    return DoctorCheckResult(
        code=DoctorCheckCode.CAMERA_NODE,
        component="Camera Node",
        status=DoctorStatus.PASS,
        summary=f"{gathered.get('stream_count', 0)} configured Stream(s); no attention needed.",
        detail=f"{gathered.get('currently_monitored_count', 0)} currently being monitored.",
        diagnostic_context=context,
    )


# --------------------------------------------------------------------------
# FFmpeg
# --------------------------------------------------------------------------


def _gather_ffmpeg(engine: Engine | None) -> dict[str, Any]:
    available = is_ffmpeg_available()
    likely_needed: bool | None = None
    if engine is not None:
        with engine.connect() as connection:
            kinds = {row[0] for row in connection.execute(select(CameraSourceModel.kind)).all()}
        likely_needed = bool(kinds & _FFMPEG_DEPENDENT_SOURCE_KINDS)
    return {"available": available, "likely_needed": likely_needed}


def _interpret_ffmpeg(gathered: dict[str, Any]) -> DoctorCheckResult:
    if gathered.get("available"):
        return DoctorCheckResult(
            code=DoctorCheckCode.FFMPEG,
            component="FFmpeg",
            status=DoctorStatus.PASS,
            summary="ffmpeg is available.",
        )
    if gathered.get("likely_needed"):
        return DoctorCheckResult(
            code=DoctorCheckCode.FFMPEG,
            component="FFmpeg",
            status=DoctorStatus.WARN,
            summary="ffmpeg was not found.",
            detail="A configured Stream (RTSP, USB, or DirectShow) may need it for live playback.",
            recoverability=DoctorRecoverability.DEGRADED,
            user_action="Install ffmpeg and make sure it is on PATH.",
        )
    return DoctorCheckResult(
        code=DoctorCheckCode.FFMPEG,
        component="FFmpeg",
        status=DoctorStatus.PASS,
        summary="ffmpeg was not found.",
        detail="It is only required for RTSP, USB, or DirectShow live camera bridges.",
        recoverability=DoctorRecoverability.INFORMATIONAL,
    )


# --------------------------------------------------------------------------
# Detector model
# --------------------------------------------------------------------------


def _gather_detector_model() -> dict[str, Any]:
    config_path = resolve_provider_config_path()
    if not config_path.is_file():
        return {"configured": False}
    try:
        frame_driven_config = FrameDrivenProviderConfiguration.load(config_path)
        OnnxModelBundle.load(frame_driven_config.model_bundle_path)
    except ReplayValidationError as error:
        return {"configured": True, "valid": False, "reason": str(error)}
    return {"configured": True, "valid": True, "model_bundle_path": str(frame_driven_config.model_bundle_path)}


def _interpret_detector_model(gathered: dict[str, Any], *, camera_node_configured: bool | None) -> DoctorCheckResult:
    if not gathered.get("configured"):
        if camera_node_configured:
            return DoctorCheckResult(
                code=DoctorCheckCode.DETECTOR_MODEL,
                component="Detector model",
                status=DoctorStatus.WARN,
                summary="No detector model bundle is installed.",
                detail="A Camera Node is configured, but the Observation Engine cannot start without a detector model bundle.",
                recoverability=DoctorRecoverability.DEGRADED,
                user_action="Install the accepted detector model bundle (see docs/megadetector-local-setup.md) and restart MockingBird.",
            )
        return DoctorCheckResult(
            code=DoctorCheckCode.DETECTOR_MODEL,
            component="Detector model",
            status=DoctorStatus.PASS,
            summary="No detector model bundle is configured.",
            detail="No Camera Node is configured yet, so a detector model is not required.",
            recoverability=DoctorRecoverability.INFORMATIONAL,
        )
    if not gathered.get("valid"):
        return DoctorCheckResult(
            code=DoctorCheckCode.DETECTOR_MODEL,
            component="Detector model",
            status=DoctorStatus.WARN,
            summary="The detector model bundle failed validation.",
            detail="The paired Camera Node's Observation Engine cannot start until this is resolved; other MockingBird features are unaffected.",
            recoverability=DoctorRecoverability.DEGRADED,
            user_action="Reinstall the detector model bundle (see docs/megadetector-local-setup.md).",
            diagnostic_context={"reason": gathered.get("reason")},
        )
    return DoctorCheckResult(
        code=DoctorCheckCode.DETECTOR_MODEL,
        component="Detector model",
        status=DoctorStatus.PASS,
        summary="Detector model bundle is present and verified.",
        diagnostic_context={"model_bundle_path": gathered.get("model_bundle_path")},
    )


# --------------------------------------------------------------------------
# Species identification (BioCLIP)
# --------------------------------------------------------------------------


def _gather_species_identification() -> dict[str, Any]:
    config = BioClipAdapterConfig(
        model_dir=resolve_bioclip_model_dir(),
        labels_path=resolve_bioclip_labels_path(),
        embedding_cache_path=resolve_bioclip_embedding_cache_path(),
    )
    status = get_bioclip_status(config)
    return {"status": status.status, "detail": status.detail}


def _interpret_species_identification(gathered: dict[str, Any]) -> DoctorCheckResult:
    status = gathered.get("status")
    if status == "available":
        return DoctorCheckResult(
            code=DoctorCheckCode.SPECIES_IDENTIFICATION,
            component="Species identification",
            status=DoctorStatus.PASS,
            summary="BioCLIP species-suggestion runtime is available.",
        )
    if status == "not_configured":
        return DoctorCheckResult(
            code=DoctorCheckCode.SPECIES_IDENTIFICATION,
            component="Species identification",
            status=DoctorStatus.PASS,
            summary="BioCLIP species suggestions are not configured.",
            detail="Wildlife Visits can still be created; species suggestions are unavailable until BioCLIP is set up.",
            recoverability=DoctorRecoverability.INFORMATIONAL,
        )
    return DoctorCheckResult(
        code=DoctorCheckCode.SPECIES_IDENTIFICATION,
        component="Species identification",
        status=DoctorStatus.WARN,
        summary="BioCLIP runtime unavailable.",
        detail="Wildlife Visits can still be created; species suggestions are unavailable.",
        recoverability=DoctorRecoverability.DEGRADED,
        user_action="Check the configured BioCLIP model/labels files, or see docs/species-suggestion-adapter-design.md.",
        diagnostic_context={"detail": gathered.get("detail")},
    )


# --------------------------------------------------------------------------
# GPU / CUDA
# --------------------------------------------------------------------------


def _gather_gpu_cuda() -> dict[str, Any]:
    probe = OnnxCudaObservationProvider.unconfigured().probe()
    return {
        "cuda_available": bool(probe.get("cuda_available")),
        "available_execution_providers": probe.get("available_execution_providers"),
    }


def _interpret_gpu_cuda(gathered: dict[str, Any], *, camera_node_configured: bool | None) -> DoctorCheckResult:
    context = {"available_execution_providers": gathered.get("available_execution_providers")}
    if gathered.get("cuda_available"):
        return DoctorCheckResult(
            code=DoctorCheckCode.GPU_CUDA,
            component="GPU / CUDA",
            status=DoctorStatus.PASS,
            summary="CUDA execution provider is available.",
            diagnostic_context=context,
        )
    if camera_node_configured:
        return DoctorCheckResult(
            code=DoctorCheckCode.GPU_CUDA,
            component="GPU / CUDA",
            status=DoctorStatus.WARN,
            summary="CUDA is not available on this host.",
            detail="A Camera Node is configured, but GPU-accelerated wildlife detection requires CUDA; CPU fallback is not supported for this path.",
            recoverability=DoctorRecoverability.DEGRADED,
            user_action="Verify a compatible NVIDIA GPU, driver, and CUDA runtime are installed.",
            diagnostic_context=context,
        )
    return DoctorCheckResult(
        code=DoctorCheckCode.GPU_CUDA,
        component="GPU / CUDA",
        status=DoctorStatus.PASS,
        summary="CUDA is not available.",
        detail="No Camera Node is currently configured, so GPU acceleration is not required.",
        recoverability=DoctorRecoverability.INFORMATIONAL,
        diagnostic_context=context,
    )


# --------------------------------------------------------------------------
# Clock
# --------------------------------------------------------------------------


def _gather_clock() -> dict[str, Any]:
    tz = resolve_host_local_timezone()
    return {"zone_key": getattr(tz, "key", None)}


def _interpret_clock(gathered: dict[str, Any]) -> DoctorCheckResult:
    zone_key = gathered.get("zone_key")
    detail = (
        f"Host local timezone resolved to {zone_key}."
        if zone_key
        else "Host local timezone could not be resolved to a named zone; using a fixed UTC-offset fallback."
    )
    return DoctorCheckResult(
        code=DoctorCheckCode.CLOCK,
        component="Clock",
        status=DoctorStatus.PASS,
        summary="Local clock is readable.",
        detail=detail,
        diagnostic_context={
            "resolved_timezone": zone_key,
            # See "Clock/time" in the contract doc: the analysis-to-host
            # offset a live session computes per frame
            # (`node_to_host_clock_offset_ms`) is not persisted or exposed
            # by any status surface today, so a standalone Doctor run
            # genuinely cannot measure Camera Node clock divergence -- this
            # is disclosed rather than fabricated.
            "camera_node_clock_divergence": "not measurable: not currently persisted or exposed by any status surface",
        },
    )


# --------------------------------------------------------------------------
# Orchestrator
# --------------------------------------------------------------------------


def _derive_overall_status(checks: list[DoctorCheckResult]) -> DoctorOverallStatus:
    """Deterministic derivation from constituent checks.

    `BLOCKING` recoverability (only ever set by Database/Storage's own
    interpret functions) is the sole path to `UNHEALTHY` -- a check that
    merely raised an unexpected exception is `DEGRADED`, not blocking, so
    one broken optional probe can never make the whole install read as
    unhealthy. `SKIPPED` never affects overall status by itself.
    """

    if any(check.recoverability == DoctorRecoverability.BLOCKING for check in checks):
        return DoctorOverallStatus.UNHEALTHY
    if any(check.status in (DoctorStatus.WARN, DoctorStatus.FAIL) for check in checks):
        return DoctorOverallStatus.DEGRADED
    return DoctorOverallStatus.HEALTHY


def run_doctor(
    *,
    runtime_home: Path | None = None,
    timeout_seconds: float = DEFAULT_CHECK_TIMEOUT_SECONDS,
    now: datetime | None = None,
) -> DoctorReport:
    """Run the complete MockingBird Doctor self-check and return one report."""

    started = time.monotonic()
    current_time = now or datetime.now(UTC)
    environment = resolve_doctor_environment(runtime_home=runtime_home)
    checks: list[DoctorCheckResult] = []

    checks.append(
        _execute_check(
            code=DoctorCheckCode.APPLICATION,
            component="Application",
            gather=lambda: _gather_application(environment.runtime_home),
            interpret=_interpret_application,
            timeout_seconds=timeout_seconds,
        )
    )

    connectivity_check, connectivity_gathered = _execute_check_returning_gathered(
        code=DoctorCheckCode.DATABASE_CONNECTIVITY,
        component="Database",
        gather=lambda: _gather_database_connectivity(environment.db_url),
        interpret=lambda gathered: _interpret_database_connectivity(
            gathered, database_path=sqlite_database_path(environment.db_url)
        ),
        timeout_seconds=timeout_seconds,
        blocking_on_failure=True,
    )
    checks.append(connectivity_check)

    # Reuse the *same* `Engine` the connectivity gather already opened
    # (only present when a real database file existed and opened cleanly --
    # see `_gather_database_connectivity`) rather than opening a second one:
    # avoids a redundant connection and, more importantly, avoids ever
    # calling `create_database_engine` a second time against a path that
    # deliberately was *not* opened because no database file exists yet.
    engine: Engine | None = (connectivity_gathered or {}).get("engine")

    if engine is not None:
        checks.append(
            _execute_check(
                code=DoctorCheckCode.DATABASE_SCHEMA,
                component="Database",
                gather=lambda: _gather_database_schema(engine),
                interpret=_interpret_database_schema,
                timeout_seconds=timeout_seconds,
                blocking_on_failure=True,
            )
        )
    else:
        checks.append(
            _execute_check(
                code=DoctorCheckCode.DATABASE_SCHEMA,
                component="Database",
                gather=None,
                interpret=_interpret_database_schema,
                skip_reason="Skipped because the database is unavailable.",
            )
        )

    # A direct, cheap file check rather than reading `connectivity_gathered`:
    # that dict is only populated when the connectivity *gather* returned
    # normally, but a corrupt (as opposed to merely absent) database file
    # makes the gather raise instead -- still correctly `FAIL`/`BLOCKING` on
    # the connectivity check itself, but it must not also make the Storage
    # check mistake a corrupt-and-therefore-`database_exists`-unknown
    # install for a never-launched one.
    database_exists = sqlite_database_path(environment.db_url).is_file()
    checks.append(
        _execute_check(
            code=DoctorCheckCode.STORAGE,
            component="Storage",
            gather=lambda: _gather_storage(
                media_root=environment.media_root,
                database_directory=sqlite_database_path(environment.db_url).parent,
            ),
            interpret=lambda gathered: _interpret_storage(gathered, database_exists=database_exists),
            timeout_seconds=timeout_seconds,
            blocking_on_failure=True,
        )
    )

    checks.append(
        _execute_check(
            code=DoctorCheckCode.BACKUP,
            component="Backup",
            gather=lambda: _gather_backup(
                db_url=environment.db_url,
                media_root=environment.media_root,
                backup_root=environment.backup_root,
            ),
            interpret=lambda gathered: _interpret_backup(gathered, now=current_time),
            timeout_seconds=timeout_seconds,
        )
    )

    camera_node_configured: bool | None = None
    if engine is not None:
        camera_check = _execute_check(
            code=DoctorCheckCode.CAMERA_NODE,
            component="Camera Node",
            gather=lambda: _gather_camera_node(engine),
            interpret=lambda gathered: _interpret_camera_node(gathered, now=current_time),
            timeout_seconds=timeout_seconds,
        )
        if camera_check.diagnostic_context:
            camera_node_configured = camera_check.diagnostic_context.get("camera_node_configured")
    else:
        camera_check = _execute_check(
            code=DoctorCheckCode.CAMERA_NODE,
            component="Camera Node",
            gather=None,
            interpret=lambda gathered: _interpret_camera_node(gathered, now=current_time),
            skip_reason="Skipped because the database is unavailable.",
        )
    checks.append(camera_check)

    checks.append(
        _execute_check(
            code=DoctorCheckCode.FFMPEG,
            component="FFmpeg",
            gather=lambda: _gather_ffmpeg(engine),
            interpret=_interpret_ffmpeg,
            timeout_seconds=timeout_seconds,
        )
    )

    checks.append(
        _execute_check(
            code=DoctorCheckCode.DETECTOR_MODEL,
            component="Detector model",
            gather=_gather_detector_model,
            interpret=lambda gathered: _interpret_detector_model(
                gathered, camera_node_configured=camera_node_configured
            ),
            timeout_seconds=MODEL_CHECK_TIMEOUT_SECONDS,
        )
    )

    checks.append(
        _execute_check(
            code=DoctorCheckCode.SPECIES_IDENTIFICATION,
            component="Species identification",
            gather=_gather_species_identification,
            interpret=_interpret_species_identification,
            timeout_seconds=timeout_seconds,
        )
    )

    checks.append(
        _execute_check(
            code=DoctorCheckCode.GPU_CUDA,
            component="GPU / CUDA",
            gather=_gather_gpu_cuda,
            interpret=lambda gathered: _interpret_gpu_cuda(gathered, camera_node_configured=camera_node_configured),
            timeout_seconds=timeout_seconds,
        )
    )

    checks.append(
        _execute_check(
            code=DoctorCheckCode.CLOCK,
            component="Clock",
            gather=_gather_clock,
            interpret=_interpret_clock,
            timeout_seconds=timeout_seconds,
        )
    )

    if engine is not None:
        try:
            engine.dispose()
        except Exception:  # noqa: BLE001 - best-effort cleanup only
            pass

    duration_ms = (time.monotonic() - started) * 1000
    return DoctorReport(
        overall_status=_derive_overall_status(checks),
        generated_at=current_time,
        app_version=APP_VERSION,
        duration_ms=duration_ms,
        checks=checks,
    )


EXIT_CODE_BY_OVERALL_STATUS: dict[DoctorOverallStatus, int] = {
    DoctorOverallStatus.HEALTHY: 0,
    DoctorOverallStatus.DEGRADED: 1,
    DoctorOverallStatus.UNHEALTHY: 2,
}


def doctor_exit_code(report: DoctorReport) -> int:
    """Stable exit code for scripts/support: 0 healthy, 1 degraded, 2 blocking failure."""

    return EXIT_CODE_BY_OVERALL_STATUS[report.overall_status]
