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

import json
import queue
import threading
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

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
from mockingbird.storage.backup import BACKUP_FORMAT_VERSION, BACKUP_ROOT_ENV_VAR, LocalBackupManager
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
from mockingbird.storage.camera_node_transport_ledger import (
    TRANSPORT_ROOT_ENV_VAR,
    TransportLedger,
    read_camera_node_transport_backlog_summary,
)
from mockingbird.storage.models import (
    CameraSourceModel,
    DatasetExportModel,
    MediaAssetModel,
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
# Reprovision / Replacement Recovery v1: a one-time operator reminder, not a
# live fault -- bounded so an old, already-reviewed replacement does not
# degrade Doctor's health forever with no way to clear it (see "Diagnostics"
# in docs/camera-node-reprovision-recovery-design.md). Seven days is ample
# time to notice and review Zones after a routine hardware swap without
# requiring a dedicated acknowledge action for this milestone's bounded scope.
_CAMERA_NODE_REPLACEMENT_REVIEW_WINDOW_SECONDS = 7 * 24 * 60 * 60.0
# First-Hour Onboarding + Whole-Product Observability Closure v1: a small,
# bounded recency window for the two checks below, matching this module's
# existing "recent, not all-time" bias (see the Camera Node boot-transition
# window above) -- a failure from months ago should not permanently degrade
# Doctor with no way to clear it, and scanning an unbounded row count on
# every Doctor run would violate "avoid expensive inference merely for
# diagnosis" (see docs/mockingbird-doctor-operational-health-contract.md).
_RECENT_RUN_SAMPLE_SIZE = 20

#: Acoustic Runtime & Quality v1: how long the oldest still-`queued`
#: acoustic segment may wait before Doctor treats the runtime as genuinely
#: falling behind (WARN) rather than merely busy -- generous relative to
#: BirdNET's own measured ~23x-real-time CPU throughput (see
#: `acoustic_runtime`'s own bounded-capacity constants), so this only fires
#: for a genuine stall, never ordinary bursty load.
_STALE_ACOUSTIC_QUEUE_AGE_SECONDS = 600.0


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
    CAMERA_NODE_TRANSPORT = "camera_node_transport"
    FFMPEG = "ffmpeg"
    DETECTOR_MODEL = "detector_model"
    SPECIES_IDENTIFICATION = "species_identification"
    GPU_CUDA = "gpu_cuda"
    CLOCK = "clock"
    OFFLINE_INGEST = "offline_ingest"
    RESEARCH_EXPORT = "research_export"
    ACOUSTIC_RUNTIME = "acoustic_runtime"
    MEDIA_INTEGRITY = "media_integrity"


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
    # First-Hour Onboarding + Whole-Product Observability Closure v1: the
    # two export output roots were previously never probed by Storage at
    # all (only the database directory, falling back to media_root -- see
    # `_gather_storage`), a real blind spot for an install with exports on
    # a different volume. No dedicated env var exists for either (confirmed
    # by this milestone's own compatibility inventory), so both are
    # anchored to `runtime_home` exactly like `media_root`/`backup_root`
    # above, matching `product_repository.py`'s own
    # `DEFAULT_RESEARCH_EXPORT_ROOT`/`DEFAULT_CLASSIFIER_MANIFEST_EXPORT_ROOT`
    # relative-path convention.
    research_export_root: Path
    classifier_manifest_export_root: Path
    # Remote / Intermittent-WAN Transport Foundation v1: same
    # runtime_home-anchored-default convention as `media_root`/
    # `backup_root` above, not `camera_node_transport_ledger`'s own
    # cwd-relative `resolve_transport_root()` default -- Doctor must work
    # from any starting working directory (see this class's own docstring).
    transport_root: Path


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
    research_export_root = home / "data" / "research_exports"
    classifier_manifest_export_root = home / "data" / "classifier_manifest_exports"
    transport_root = Path(os.getenv(TRANSPORT_ROOT_ENV_VAR) or str(home / "data" / "camera_node_transport"))
    return DoctorEnvironment(
        runtime_home=home,
        db_url=db_url,
        media_root=media_root,
        backup_root=backup_root,
        research_export_root=research_export_root,
        classifier_manifest_export_root=classifier_manifest_export_root,
        transport_root=transport_root,
    )


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

    Final Release Candidate Corrections v1: a raw peek at the marker file
    cannot tell "the previous run crashed" apart from "this very process is
    the current run, and simply has not shut down yet" -- `prepare_runtime_
    state` unconditionally rewrites the marker to `{"state": "starting"}` at
    boot, so both cases read identically for the *entire* lifetime of a
    running instance, not merely a brief window. Whenever `runtime_home` is
    the exact data directory this process itself booted against,
    `runtime_state.previous_shutdown_was_clean()` already holds the real
    answer -- computed once at boot, before the marker was overwritten --
    exactly the fact `GET /api/product/health`'s own `previous_shutdown_
    clean` field already reads this same way (see api/main.py). Prefer that
    live, correct fact for that case. A different `runtime_home` (Doctor
    examining a directory this process did not itself launch against) or a
    process that never called `prepare_runtime_state` at all (the
    separate-process CLI form, or a bare test) has no such in-memory fact
    available and keeps the original raw peek, unchanged.
    """

    if runtime_home == runtime_state.current_runtime_home():
        return runtime_state.previous_shutdown_was_clean()

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


# Appliance / Storage / Privacy / Recovery v1, Phase N: duplicated, not
# imported, exactly like this codebase's existing precedent for these same
# two values (`NODE_API_VERSION` already exists independently in both
# `source_providers.camera_node` and `mockingbird_node.app`;
# `TRANSPORT_PROTOCOL_VERSION` already exists independently in both
# `mockingbird_node.transport_client` and `api.camera_node_transport`) --
# `diagnostics.doctor` deliberately imports nothing from `api/` today (see
# this module's own design-invariant docstring), so a third duplicate here
# extends an already-accepted pattern rather than introducing a new
# api->diagnostics dependency for two short version strings. `BACKUP_
# FORMAT_VERSION` is imported directly instead: `storage.backup` is not
# `api/`, and this module already imports `LocalBackupManager` from it.
_DOCTOR_NODE_API_VERSION = "v1"
_DOCTOR_TRANSPORT_PROTOCOL_VERSION = "transport/v1"


def _gather_application(runtime_home: Path) -> dict[str, Any]:
    git_commit, build_id = runtime_state.resolve_build_identity()
    shutdown_clean = _peek_previous_shutdown_state(runtime_home)
    return {"git_commit": git_commit, "build_id": build_id, "shutdown_clean": shutdown_clean}


def _interpret_application(gathered: dict[str, Any]) -> DoctorCheckResult:
    context = {
        "git_commit": gathered.get("git_commit"),
        "build_id": gathered.get("build_id"),
        # Fixed constants, never a live re-check -- see "Compatibility
        # boundaries" in docs/appliance-storage-privacy-recovery-v1-contract.md.
        "backup_format_version": BACKUP_FORMAT_VERSION,
        "camera_node_api_version": _DOCTOR_NODE_API_VERSION,
        "transport_protocol_version": _DOCTOR_TRANSPORT_PROTOCOL_VERSION,
    }
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
    # Appliance / Storage / Privacy / Recovery v1, Phase O: a real,
    # reproduced `PRAGMA foreign_key_check` failure on this project's own
    # development database (a Stream-scoped settings row surviving a demo-
    # data reset that deleted its owning Stream -- fixed at the source in
    # `ProductRepository._delete_sample_graph`) blocked a real backup-
    # restore-with-rebind acceptance run. Distinct from, and never
    # escalated to, `integrity_check` above: a dangling foreign key on a
    # lazily-created settings row is not page-level corruption and must
    # never make an otherwise-healthy database read as BLOCKING, nor make
    # backup verification (which reuses `_sqlite_integrity_check` too, via
    # `_validate_database_file`) reject an otherwise-fine backup over it --
    # this is purely an additional, non-blocking Doctor signal so the
    # underlying data issue is at least visible before it surfaces as a
    # confusing restore failure.
    fk_violations: list[tuple[str, ...]] = []
    try:
        with engine.connect() as connection:
            fk_violations = [tuple(str(value) for value in row) for row in connection.execute(text("PRAGMA foreign_key_check")).fetchall()]
    except SQLAlchemyError:
        fk_violations = []
    return {
        "database_exists": True,
        "engine": engine,
        "integrity_check": integrity_check,
        "foreign_key_violation_count": len(fk_violations),
        "foreign_key_violation_tables": sorted({row[0] for row in fk_violations})[:10],
    }


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
    violation_count = gathered.get("foreign_key_violation_count", 0)
    if violation_count:
        context["foreign_key_violation_count"] = violation_count
        context["foreign_key_violation_tables"] = gathered.get("foreign_key_violation_tables", [])
        return DoctorCheckResult(
            code=DoctorCheckCode.DATABASE_CONNECTIVITY,
            component="Database",
            status=DoctorStatus.WARN,
            summary="The database is usable, but a background reference check found a stale internal link.",
            detail=(
                "This does not affect reviewed history or evidence; it can happen after removing sample "
                "walkthrough data. It may cause an advanced cross-install restore to be refused."
            ),
            recoverability=DoctorRecoverability.DEGRADED,
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


def _gather_export_root_status(
    export_roots: dict[str, Path], *, primary_device_id: int | None
) -> dict[str, dict[str, Any]]:
    """Probe each export output root independently, but only when it
    already exists -- like `media_root`, these are lazily created on first
    real export, so "does not exist yet" is a normal, non-alarming state
    for a fresh install, not a defect (see the module docstring's "never
    mutate" invariant: this must not create the folder merely by checking
    it). `primary_device_id` (the database directory's `st_dev`, when
    resolvable) lets the caller avoid a second, redundant low-space WARN
    for a root that turns out to share the exact same physical volume the
    primary Storage probe already reported on.
    """

    results: dict[str, dict[str, Any]] = {}
    for label, root in export_roots.items():
        if not root.is_dir():
            results[label] = {"exists": False}
            continue
        disk_status = probe_local_storage_disk(root)
        same_device = None
        if primary_device_id is not None:
            try:
                same_device = root.stat().st_dev == primary_device_id
            except OSError:  # pragma: no cover - defensive, matches probe's own tolerance
                same_device = None
        results[label] = {
            "exists": True,
            "is_writable": disk_status.is_writable,
            "is_low_space": disk_status.is_low_space,
            "free_bytes": disk_status.free_bytes,
            "same_device_as_database": same_device,
        }
    return results


# Mirrors `product_repository.demo_data.SOURCE_ID` exactly -- duplicated,
# not imported, matching this module's own already-established pattern
# just below (`_DOCTOR_NODE_API_VERSION`/`_DOCTOR_TRANSPORT_PROTOCOL_
# VERSION`): `diagnostics.doctor` deliberately imports nothing from `api/`
# today (see this module's own design-invariant docstring), and
# `demo_data` lives under `api/`. `ProductRepository.__init__` seeds
# exactly this one walkthrough Source on a brand-new database (see
# `seed_if_empty`/`_seed_session`) -- confirmed directly against a real
# bare construction, not assumed -- so counting it would make this check
# report "configured" on every fresh install, defeating its purpose.
# `remove_sample_data` already excludes it by this same id for the
# identical reason (a real Source existing "besides the demo one").
_DOCTOR_DEMO_SOURCE_ID = "source-backyard-demo"


def _gather_has_any_source_configured(engine: Engine | None) -> bool | None:
    """Whether at least one real Source (any kind -- Camera Node, RTSP,
    ONVIF, external URL, folder import, webhook, ...) has ever been
    configured by a user -- the seeded walkthrough demo Source does not
    count (see `_DOCTOR_DEMO_SOURCE_ID`, above).

    Release Reliability & First-Run Recovery v1: the real, previously
    missing signal that distinguishes "database exists but the first-run
    wizard has not reached Add a camera yet" from "database exists and this
    install has genuinely started using MockingBird" -- see
    `_interpret_storage`'s own docstring for why raw database-file
    existence alone conflated the two. A cheap `SELECT ... LIMIT 1`
    (existence, not a count) against the same `engine` `_gather_camera_node`
    already reads from, reusing that established "pass the already-open
    Engine in, never construct a `ProductRepository`" convention rather
    than adding a new database dependency to this read-only module.
    `None` when no engine is available at all (database unreachable/absent)
    -- `_interpret_storage` never needs to distinguish that from `False`
    here, since the database-existence check already covers that case.
    """

    if engine is None:
        return None
    with engine.connect() as connection:
        return (
            connection.execute(
                select(CameraSourceModel.id).where(
                    CameraSourceModel.id != _DOCTOR_DEMO_SOURCE_ID
                ).limit(1)
            ).first()
            is not None
        )


def _gather_storage(
    *,
    media_root: Path,
    database_directory: Path,
    export_roots: dict[str, Path] | None = None,
    engine: Engine | None = None,
) -> dict[str, Any]:
    media_root_exists = media_root.is_dir()
    probe_directory = database_directory if database_directory.is_dir() else media_root
    disk_status = probe_local_storage_disk(probe_directory) if probe_directory.is_dir() else None
    primary_device_id: int | None = None
    if probe_directory.is_dir():
        try:
            primary_device_id = probe_directory.stat().st_dev
        except OSError:  # pragma: no cover - defensive, matches probe's own tolerance
            primary_device_id = None
    return {
        "media_root_exists": media_root_exists,
        "media_root": str(media_root),
        "total_bytes": disk_status.total_bytes if disk_status else 0,
        "free_bytes": disk_status.free_bytes if disk_status else 0,
        "is_writable": disk_status.is_writable if disk_status else False,
        "is_low_space": disk_status.is_low_space if disk_status else False,
        # Appliance / Storage / Privacy / Recovery v1, Phase C: the graduated
        # tier behind the `is_low_space` boolean above -- see
        # `storage.database.LocalStorageDiskStatus.storage_health_tier`.
        "storage_health_tier": disk_status.storage_health_tier if disk_status else "healthy",
        "probed_directory": str(probe_directory),
        "export_roots": _gather_export_root_status(export_roots or {}, primary_device_id=primary_device_id),
        # Release Reliability & First-Run Recovery v1: see
        # `_gather_has_any_source_configured`'s own docstring.
        "has_any_source_configured": _gather_has_any_source_configured(engine),
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
        # lazily on first real media write. On a genuinely established
        # install (database exists *and* at least one Source has been
        # configured), a missing folder is a real problem; a not-yet-in-use
        # install is the same honest "not started yet" state the Database
        # check already reports as informational, not a defect.
        #
        # Release Reliability & First-Run Recovery v1: raw database-file
        # existence alone used to gate this branch, but the database file is
        # created at server-process startup itself (see
        # `runtime_state.prepare_runtime_state`), before the first-run
        # wizard's Storage step is ever reached -- not at wizard completion.
        # A brand-new participant who ran `doctor` mid-setup (exactly what
        # this product's own onboarding/participant materials ask them to
        # try) saw an alarming "genuine problem" `BLOCKING` message during
        # entirely normal first-run setup. Treating "no Source configured
        # yet" the same as "no database yet" closes that gap: nothing has
        # ever had a reason to write to the media root in either case, so
        # neither is a genuine problem. `has_any_source_configured is None`
        # (no engine reachable at all -- the database check itself already
        # reports this) is treated the same as `False`: never escalate to
        # BLOCKING on a fact this check could not actually confirm.
        if not database_exists or not gathered.get("has_any_source_configured"):
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
    storage_health_tier = gathered.get("storage_health_tier", "healthy")
    context["storage_health_tier"] = storage_health_tier
    if storage_health_tier == "critical":
        free_gb = gathered.get("free_bytes", 0) / 1_000_000_000
        return DoctorCheckResult(
            code=DoctorCheckCode.STORAGE,
            component="Storage",
            status=DoctorStatus.WARN,
            summary=f"Free disk space is critically low ({free_gb:.1f} GB free). New evidence may soon fail to save.",
            detail="Authoritative reviewed history and the database are not at risk from this alone, but new captures/backups may start failing.",
            recoverability=DoctorRecoverability.DEGRADED,
            user_action="Free up disk space now, or move MockingBird's data folder to a drive with more room.",
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
    if storage_health_tier == "getting_low":
        free_gb = gathered.get("free_bytes", 0) / 1_000_000_000
        return DoctorCheckResult(
            code=DoctorCheckCode.STORAGE,
            component="Storage",
            status=DoctorStatus.PASS,
            summary=f"Free disk space is getting low ({free_gb:.1f} GB free).",
            recoverability=DoctorRecoverability.INFORMATIONAL,
            diagnostic_context=context,
        )
    # First-Hour Onboarding + Whole-Product Observability Closure v1: an
    # export output root is never itself blocking (exports are an optional
    # capability, not the core "observe wildlife" loop), but a genuinely
    # separate, low-space/unwritable export volume was previously an
    # undetected blind spot -- see `_gather_export_root_status`. Only
    # surfaced when the root actually exists and is a genuinely different
    # device than the one just confirmed healthy above, so this can never
    # double-report the same physical disk as two separate problems.
    export_roots = gathered.get("export_roots") or {}
    problem_roots = [
        label
        for label, status in export_roots.items()
        if status.get("exists")
        and status.get("same_device_as_database") is False
        and (not status.get("is_writable") or status.get("is_low_space"))
    ]
    context["export_roots"] = export_roots
    if problem_roots:
        return DoctorCheckResult(
            code=DoctorCheckCode.STORAGE,
            component="Storage",
            status=DoctorStatus.WARN,
            summary=f"Export storage needs attention: {', '.join(problem_roots)}.",
            detail="An export output folder is low on space or not writable. Exports can fail until this is resolved.",
            recoverability=DoctorRecoverability.DEGRADED,
            user_action="Free up space on the export folder's drive, or check its permissions.",
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
        # Appliance / Storage / Privacy / Recovery v1, Phase G/O: a plain
        # file read, no mutation -- see `LocalBackupManager.detect_
        # interrupted_restore`'s own docstring.
        "interrupted_restore": manager.detect_interrupted_restore(),
    }


def _interpret_backup(gathered: dict[str, Any], *, now: datetime) -> DoctorCheckResult:
    context = {
        "backup_count": gathered.get("backup_count", 0),
        "unreadable_backup_count": gathered.get("unreadable_backup_count", 0),
        "most_recent_backup_at": gathered.get("most_recent_created_at"),
    }
    interrupted_restore = gathered.get("interrupted_restore")
    if interrupted_restore:
        # Appliance / Storage / Privacy / Recovery v1, Phase G/O: a
        # distinct, more urgent signal than ordinary backup staleness -- a
        # previous restore was interrupted by a hard process kill partway
        # through replacing live files (see `LocalBackupManager.replace_
        # live_files`'s sentinel). The recorded rollback paths are still on
        # disk, so nothing is silently lost, but the install must not be
        # treated as an ordinary healthy one until a human looks at this.
        return DoctorCheckResult(
            code=DoctorCheckCode.BACKUP,
            component="Backup",
            status=DoctorStatus.WARN,
            summary="A previous restore did not finish.",
            detail=(
                "MockingBird was stopped while replacing local data during a restore. "
                "The data now in place may be incomplete. Nothing was deleted -- the "
                "files from just before the restore are still on disk."
            ),
            recoverability=DoctorRecoverability.DEGRADED,
            user_action="Restore again from a known-good backup, or contact support with this diagnostic detail.",
            diagnostic_context={**context, "interrupted_restore": interrupted_restore},
        )
    unreadable_count = gathered.get("unreadable_backup_count", 0)
    if not gathered.get("backup_count"):
        if unreadable_count:
            # Appliance / Storage / Privacy / Recovery v1: every backup on
            # record is unreadable -- a real, degraded failure, not the calm
            # "nothing created yet" case this check previously could not
            # tell apart from it (see docs/appliance-storage-privacy-
            # recovery-v1-contract.md, "Backup diagnosability").
            return DoctorCheckResult(
                code=DoctorCheckCode.BACKUP,
                component="Backup",
                status=DoctorStatus.WARN,
                summary=f"{unreadable_count} backup file(s) exist but none can be read.",
                detail=(
                    "Every backup on record failed verification (an incompatible or "
                    "corrupted archive). None of them can currently be used to restore."
                ),
                recoverability=DoctorRecoverability.DEGRADED,
                user_action="Create a fresh backup from the Local Data page.",
                diagnostic_context=context,
            )
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
    if unreadable_count:
        # A mix of good and unreadable backups: restore is still possible,
        # but the unreadable ones are worth the user's attention -- surfaced
        # here rather than silently folded into a plain PASS.
        return DoctorCheckResult(
            code=DoctorCheckCode.BACKUP,
            component="Backup",
            status=DoctorStatus.WARN,
            summary=(
                f"{gathered['backup_count']} backup(s) found (most recent {age_days:.0f} day(s) old); "
                f"{unreadable_count} other backup file(s) cannot be read."
            ),
            recoverability=DoctorRecoverability.DEGRADED,
            user_action="Review backups on the Local Data page; unreadable files can be safely removed.",
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
                CameraSourceModel.camera_node_identity_replaced_at,
                CameraSourceModel.camera_node_replacement_reason,
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
    # Reprovision / Replacement Recovery v1: the single most-recently-
    # replaced camera_node Source's provenance, matching every other field
    # here's "pick the most-recent across sources" convention -- `reason` is
    # read from that *same* row below, never mixed across different sources.
    most_recently_replaced_source = max(
        (row for row in camera_node_sources if row[5] is not None),
        key=lambda row: row[5],
        default=None,
    )
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
        "camera_node_identity_replaced_at": (
            normalize_utc(most_recently_replaced_source[5]).isoformat()
            if most_recently_replaced_source
            else None
        ),
        "camera_node_replacement_reason": (
            most_recently_replaced_source[6] if most_recently_replaced_source else None
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
    # Reprovision / Replacement Recovery v1: lowest priority by design -- an
    # actively offline/unstable Node above is always the more urgent signal.
    # Bounded to a review window (see the constant's docstring) rather than
    # surfaced forever, so a routine hardware swap reviewed weeks ago does
    # not permanently degrade Doctor with no way to clear it.
    replaced_at_raw = gathered.get("camera_node_identity_replaced_at")
    if replaced_at_raw:
        replaced_at = datetime.fromisoformat(replaced_at_raw)
        replacement_age_seconds = (now - replaced_at).total_seconds()
        if 0 <= replacement_age_seconds <= _CAMERA_NODE_REPLACEMENT_REVIEW_WINDOW_SECONDS:
            context["camera_node_identity_replaced_at"] = replaced_at_raw
            reason = gathered.get("camera_node_replacement_reason")
            if reason:
                context["camera_node_replacement_reason"] = reason
            return DoctorCheckResult(
                code=DoctorCheckCode.CAMERA_NODE,
                component="Camera Node",
                status=DoctorStatus.WARN,
                summary=f"Camera Node hardware was replaced on {replaced_at.date().isoformat()}.",
                detail=(
                    "This camera's Place, Stream, Zones, and history stay attached to the "
                    "replacement hardware. MockingBird cannot verify the replacement camera's "
                    "framing/field of view matches the original."
                    + (f" Reason given: {reason}" if reason else "")
                ),
                recoverability=DoctorRecoverability.DEGRADED,
                user_action="Review this camera's Zones and confirm they still match what the camera actually sees.",
                diagnostic_context=context,
            )
    if camera_node_configured:
        # Host <-> Camera Node Release-Compatibility Preflight v1: Doctor
        # stays read-only and never live-probes a paired Node (this
        # module's own documented design invariant -- see the module
        # docstring -- would require touching `secret=True`-flagged
        # provider configuration), so it cannot itself confirm whether
        # this Node supports bounded RTT clock calibration. Points at the
        # one live tool that can, mirroring the `clock` check's own
        # established "not measurable from a standalone Doctor check: see
        # ... instead" precedent, rather than guessing from `camera_node_
        # service_version` alone (a package version, not a capability
        # signal -- see node_compatibility.py's own "Version-skew
        # behavior" docstring).
        context["field_acceptance_compatibility_check"] = (
            "Not measurable from a standalone Doctor check: run "
            "scripts/check_camera_node_compatibility.py for a live "
            "verdict before a true-latency acceptance session."
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
# Camera Node transport (Remote / Intermittent-WAN Transport Foundation v1)
# --------------------------------------------------------------------------

# A backlog summary older than this is presented as stale rather than
# current -- the Node only reports it as a side effect of an outbound
# transport call (see camera_node_transport.py's module docstring: Doctor
# never dials out itself), so a long silence here means "we don't know," not
# "the backlog is empty." Deliberately generous: an intermittently-connected
# remote Node over a slow/metered link should not read as broken just
# because it has not phoned home in the last few minutes.
CAMERA_NODE_TRANSPORT_STALE_AFTER_SECONDS = 3600.0

# Appliance / Storage / Privacy / Recovery v1, Phase E: a completed transport
# item is normally consumed into a MediaAsset synchronously, within the same
# request that acknowledged it (see `api.camera_node_transport`'s
# `on_item_completed` hook) -- so anything still sitting in a node's
# `completed/` directory this long suggests the consumption sweep itself is
# stuck, not merely "hasn't happened yet." Deliberately the same threshold
# as `CAMERA_NODE_TRANSPORT_STALE_AFTER_SECONDS`, not a second invented
# number, for a consistent "an hour of silence is worth a look" doctrine.
CAMERA_NODE_TRANSPORT_UNCONSUMED_WARN_AFTER_SECONDS = 3600.0

# Bounded, not a hard architectural limit: a home installation has a
# handful of Camera Nodes and consumption normally drains within one
# request, so a plain filesystem scan across every node's `completed/`
# directory never needs to look past a small number of files. Caps cost if
# something is ever genuinely stuck, rather than letting Doctor's own
# bounded-timeout budget (`_run_bounded`) be the only backstop.
_MAX_TRANSPORT_UNCONSUMED_ITEMS_SCANNED = 500


def _scan_camera_node_transport_unconsumed_backlog(transport_root: Path) -> dict[str, Any]:
    """Plain filesystem read, no repository/database involved (mirrors
    `read_camera_node_transport_backlog_summary`'s own "free function, no
    repository" pattern) -- how much completed transport evidence is
    currently sitting unconsumed on the host, across every Camera Node,
    regardless of which Source it will eventually attribute to. A properly
    consumed item's blob is deleted (see `ProductRepository.consume_camera_
    node_transport_item`), so anything this finds is, by construction,
    either mid-flight (about to be consumed) or genuinely stuck."""

    ledger = TransportLedger(transport_root)
    count = 0
    total_bytes = 0
    oldest_completed_at: float | None = None
    for node_id in ledger.list_node_ids():
        for item_id in ledger.list_completed_item_ids(node_id):
            if count >= _MAX_TRANSPORT_UNCONSUMED_ITEMS_SCANNED:
                break
            count += 1
            meta = ledger.completed_item_metadata(node_id, item_id) or {}
            total_bytes += int(meta.get("content_length") or 0)
            completed_at = meta.get("completed_at")
            if isinstance(completed_at, (int, float)) and (
                oldest_completed_at is None or completed_at < oldest_completed_at
            ):
                oldest_completed_at = completed_at
    return {
        "unconsumed_count": count,
        "unconsumed_bytes": total_bytes,
        "oldest_unconsumed_completed_at": oldest_completed_at,
    }


def _gather_camera_node_transport(engine: Engine, *, transport_root: Path) -> dict[str, Any]:
    # Raw SQL, not `select(SourceProviderConfigurationModel...)`: that ORM
    # class is defined in `repository.product_repository` (a much heavier
    # module `diagnostics.doctor` deliberately does not import today -- see
    # every other `_gather_*` here, which reads `storage.models` classes
    # only). The table itself (`source_provider_configurations`) is stable,
    # durable product schema; reading it by name avoids inventing that new
    # cross-module dependency for one bounded read.
    with engine.connect() as connection:
        rows = connection.execute(
            text(
                "SELECT camera_sources.id, camera_sources.name, source_provider_configurations.config_json "
                "FROM source_provider_configurations "
                "JOIN camera_sources ON camera_sources.id = source_provider_configurations.source_id "
                "WHERE source_provider_configurations.provider_key = 'camera_node'"
            )
        ).all()
    sources: list[dict[str, Any]] = []
    for source_id, name, config_json in rows:
        try:
            config = json.loads(config_json)
        except (TypeError, ValueError):
            config = {}
        node_id = config.get("node_id")
        transport_configured = bool(config.get("node_transport_credential"))
        summary = (
            read_camera_node_transport_backlog_summary(node_id, transport_root=transport_root)
            if node_id
            else None
        )
        sources.append(
            {
                "source_id": source_id,
                "name": name,
                "node_id": node_id,
                "transport_configured": transport_configured,
                "backlog_summary": summary,
            }
        )
    # Host-side, source-agnostic: how much completed transport evidence is
    # sitting unconsumed right now, regardless of whether it will eventually
    # attribute to a currently-configured Source (an unattributed item, for
    # example after a Camera Node replacement gone wrong, would otherwise
    # never appear in the per-Source list above at all).
    unconsumed_backlog = _scan_camera_node_transport_unconsumed_backlog(transport_root)
    return {"sources": sources, **unconsumed_backlog}


def _interpret_camera_node_transport(gathered: dict[str, Any], *, now: datetime) -> DoctorCheckResult:
    sources = gathered.get("sources", [])
    transport_sources = [item for item in sources if item.get("transport_configured")]
    if not transport_sources:
        unconsumed_count = gathered.get("unconsumed_count", 0)
        if unconsumed_count:
            # Real, if narrow, edge case: completed transport evidence with
            # no currently-configured Source claiming it (for example after
            # an interrupted Camera Node replacement) -- never silently
            # invisible just because no Source is "transport_configured"
            # right now.
            return DoctorCheckResult(
                code=DoctorCheckCode.CAMERA_NODE_TRANSPORT,
                component="Camera Node transport",
                status=DoctorStatus.WARN,
                summary=f"{unconsumed_count} completed transport item(s) are not attributed to any configured Source.",
                detail="These will keep being retried automatically if a matching Source is configured again.",
                recoverability=DoctorRecoverability.DEGRADED,
                diagnostic_context={"unconsumed_count": unconsumed_count, "unconsumed_bytes": gathered.get("unconsumed_bytes", 0)},
            )
        return DoctorCheckResult(
            code=DoctorCheckCode.CAMERA_NODE_TRANSPORT,
            component="Camera Node transport",
            status=DoctorStatus.PASS,
            summary="No paired Camera Node has remote transport configured.",
            recoverability=DoctorRecoverability.INFORMATIONAL,
            detail="Remote / Intermittent-WAN Transport Foundation v1 is available but not in use.",
        )
    context: dict[str, Any] = {"sources": []}
    worst_status = DoctorStatus.PASS
    summaries: list[str] = []
    for item in transport_sources:
        summary = item.get("backlog_summary")
        entry: dict[str, Any] = {"source_id": item["source_id"], "name": item["name"], "node_id": item["node_id"]}
        if summary is None:
            entry["state"] = "never_contacted"
            worst_status = DoctorStatus.WARN
            summaries.append(f"{item['name']}: no transport contact yet")
        else:
            reported_at = summary.get("reported_at")
            age_seconds = (now.timestamp() - reported_at) if isinstance(reported_at, (int, float)) else None
            stale = age_seconds is None or age_seconds > CAMERA_NODE_TRANSPORT_STALE_AFTER_SECONDS
            pending_count = summary.get("pending_count", 0)
            failed_terminal_count = summary.get("failed_terminal_count", 0)
            entry.update(
                state="stale" if stale else "reporting",
                age_seconds=age_seconds,
                pending_count=pending_count,
                pending_bytes=summary.get("pending_bytes", 0),
                failed_terminal_count=failed_terminal_count,
                last_error=summary.get("last_error"),
            )
            if stale:
                worst_status = DoctorStatus.WARN
                summaries.append(f"{item['name']}: last transport contact was over an hour ago")
            elif failed_terminal_count:
                worst_status = DoctorStatus.WARN
                summaries.append(f"{item['name']}: {failed_terminal_count} item(s) cannot be delivered (incompatible)")
            elif pending_count:
                summaries.append(f"{item['name']}: {pending_count} item(s) backlogged, draining")
            else:
                summaries.append(f"{item['name']}: backlog clear")
        context["sources"].append(entry)

    # Appliance / Storage / Privacy / Recovery v1, Phase E: a completed
    # transport item is normally consumed synchronously; anything still
    # sitting unconsumed past the stale-contact threshold suggests the
    # consumption sweep itself is stuck, not merely "hasn't run yet."
    unconsumed_count = gathered.get("unconsumed_count", 0)
    oldest_unconsumed_completed_at = gathered.get("oldest_unconsumed_completed_at")
    unconsumed_age_seconds = (
        now.timestamp() - oldest_unconsumed_completed_at
        if isinstance(oldest_unconsumed_completed_at, (int, float))
        else None
    )
    context["unconsumed_count"] = unconsumed_count
    context["unconsumed_bytes"] = gathered.get("unconsumed_bytes", 0)
    if unconsumed_count and (
        unconsumed_age_seconds is None or unconsumed_age_seconds > CAMERA_NODE_TRANSPORT_UNCONSUMED_WARN_AFTER_SECONDS
    ):
        worst_status = DoctorStatus.WARN
        summaries.append(f"{unconsumed_count} completed item(s) have not been consumed into evidence yet")

    return DoctorCheckResult(
        code=DoctorCheckCode.CAMERA_NODE_TRANSPORT,
        component="Camera Node transport",
        status=worst_status,
        summary="; ".join(summaries) if summaries else "Camera Node transport is healthy.",
        recoverability=DoctorRecoverability.DEGRADED if worst_status != DoctorStatus.PASS else None,
        user_action=(
            "Check host reachability from the Camera Node, or run the Node's own "
            "`/node/v1/transport/status` if the Node itself is reachable."
            if worst_status != DoctorStatus.PASS
            else None
        ),
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
            user_action=(
                "Install ffmpeg (https://ffmpeg.org/download.html) and make sure it is on "
                "PATH. A paired MockingBird Camera Node does not need this."
            ),
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
            # `get_bioclip_status()` deliberately checks configuration/labels/
            # runtime-version readiness without loading the model or hashing
            # model weights (see its own docstring) -- its `detail` already
            # discloses that scope honestly ("A run still validates the
            # precomputed embedding cache before returning suggestion
            # evidence"). Surface it here too rather than let this PASS read
            # as a stronger, unconditional guarantee than the underlying
            # check actually makes.
            detail=gathered.get("detail"),
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
            # `_gather_gpu_cuda` only checks that onnxruntime's own compiled
            # provider list includes CUDA -- it never attempts a real
            # session load, so it cannot by itself prove the driver/CUDA/
            # cuDNN stack actually initializes. Disclose that scope rather
            # than let a PASS here read as a stronger guarantee than the
            # underlying probe makes; a real session-load failure is still
            # caught and honestly reported by Observation health once a
            # Camera Node actually starts (see `engine_runtime.py`).
            detail=(
                "This confirms onnxruntime detects a CUDA execution provider on "
                "this host; it does not by itself prove a detector session will "
                "load. Observation health reports that outcome when a Camera "
                "Node is actually started."
            ),
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
            # Camera Node <-> Host RTT-Bounded Clock Calibration v1 (see
            # docs/camera-node-host-rtt-bounded-clock-calibration-v1
            # -report.md): a *live* Observation Engine session now computes
            # and bounds a real, defensible Node/Host offset *interval*
            # (`counterfactual_lineage.CounterfactualLedger.record_rtt_
            # clock_calibration`, surfaced via `GET .../observation/
            # counterfactual` `rtt_clock_calibrations`) -- but that state
            # lives only in that session's own in-memory ledger, never a
            # durable store. Doctor runs as a separate, standalone process
            # with no live session handle, so it genuinely still cannot
            # read a fact nothing durable persists -- disclosed rather than
            # fabricated, not a regression from before this milestone (only
            # the *reason* changed, from "never computed" to "computed
            # live, not durably readable from here"). The one-way `clock_
            # calibrations` key still exists for relative drift/jump
            # monitoring but was never itself a defensible bound, before or
            # after this milestone.
            "camera_node_clock_divergence": (
                "not measurable from a standalone Doctor check: see a running session's own "
                "GET .../observation/counterfactual response (rtt_clock_calibrations) instead"
            ),
        },
    )


# --------------------------------------------------------------------------
# Offline ingest
# --------------------------------------------------------------------------


def _gather_offline_ingest(engine: Engine) -> dict[str, Any]:
    # `RecordedMediaAnalysisRunModel` lives in `repository.product_repository`
    # (not `storage.models`) -- a lazy, function-local import so Doctor's
    # module-level import cost does not grow for every other check merely
    # because this one exists; importing the module does not construct
    # `ProductRepository` (see the module docstring's design invariant),
    # so this stays a bare, read-only query exactly like every other check.
    from sqlalchemy.exc import OperationalError

    from mockingbird.repository.product_repository import RecordedMediaAnalysisRunModel

    try:
        with engine.connect() as connection:
            rows = connection.execute(
                select(RecordedMediaAnalysisRunModel.status, RecordedMediaAnalysisRunModel.error_code)
                .order_by(RecordedMediaAnalysisRunModel.created_at.desc())
                .limit(_RECENT_RUN_SAMPLE_SIZE)
            ).all()
    except OperationalError:
        # A database whose recorded schema is older than this table's own
        # migration (schema 41) has no such table yet -- an honest "not
        # migrated to that point" fact, not an unexpected Doctor failure;
        # the Database Schema check above already reports the version gap
        # itself. Never surfaced as a raw exception here.
        return {"sampled_count": 0, "failed_count": 0, "table_available": False}
    statuses = [row[0] for row in rows]
    return {
        "sampled_count": len(statuses),
        "failed_count": sum(1 for status in statuses if status == "failed"),
        "most_recent_error_code": next((row[1] for row in rows if row[0] == "failed"), None),
        "table_available": True,
    }


def _interpret_offline_ingest(gathered: dict[str, Any]) -> DoctorCheckResult:
    sampled_count = gathered.get("sampled_count", 0)
    context = {"sampled_run_count": sampled_count, "failed_count": gathered.get("failed_count", 0)}
    if gathered.get("table_available") is False:
        return DoctorCheckResult(
            code=DoctorCheckCode.OFFLINE_INGEST,
            component="Offline ingest",
            status=DoctorStatus.PASS,
            summary="Recorded-media analysis history isn't available yet.",
            detail="This database has not been migrated to the schema version that added it. See the Database Schema check.",
            recoverability=DoctorRecoverability.INFORMATIONAL,
            diagnostic_context=context,
        )
    if sampled_count == 0:
        return DoctorCheckResult(
            code=DoctorCheckCode.OFFLINE_INGEST,
            component="Offline ingest",
            status=DoctorStatus.PASS,
            summary="No recorded-media analysis has been run yet.",
            detail="This is expected until a recorded video is analyzed from Import Media.",
            recoverability=DoctorRecoverability.INFORMATIONAL,
            diagnostic_context=context,
        )
    failed_count = gathered.get("failed_count", 0)
    if failed_count > 0:
        context["most_recent_error_code"] = gathered.get("most_recent_error_code")
        return DoctorCheckResult(
            code=DoctorCheckCode.OFFLINE_INGEST,
            component="Offline ingest",
            status=DoctorStatus.WARN,
            summary=f"{failed_count} of the last {sampled_count} recorded-media analysis run(s) failed.",
            detail="Live camera observation is unaffected; this only concerns imported recorded video.",
            recoverability=DoctorRecoverability.DEGRADED,
            user_action="Open the affected recording's analysis result for the specific reason, or try analyzing it again.",
            diagnostic_context=context,
        )
    return DoctorCheckResult(
        code=DoctorCheckCode.OFFLINE_INGEST,
        component="Offline ingest",
        status=DoctorStatus.PASS,
        summary=f"The last {sampled_count} recorded-media analysis run(s) completed without error.",
        diagnostic_context=context,
    )


# --------------------------------------------------------------------------
# Acoustic runtime (Acoustic Runtime & Quality v1)
# --------------------------------------------------------------------------


def _gather_acoustic_runtime(engine: Engine) -> dict[str, Any]:
    """Mirrors `_gather_offline_ingest`'s exact "lazy model import, bare
    read-only Core query, `OperationalError` means not-yet-migrated"
    discipline -- plus queue-depth/oldest-pending-age aggregates (Phase J's
    own bounded-runtime-information list) and whether the optional BirdNET
    runtime package is installed."""

    from sqlalchemy import func as sa_func
    from sqlalchemy.exc import OperationalError

    from mockingbird.repository.product_repository import AcousticAnalysisRunModel
    from mockingbird.species.birdnet_adapter import get_birdnet_status

    birdnet_status = get_birdnet_status()
    try:
        with engine.connect() as connection:
            rows = connection.execute(
                select(AcousticAnalysisRunModel.status, AcousticAnalysisRunModel.error_code)
                .order_by(AcousticAnalysisRunModel.created_at.desc())
                .limit(_RECENT_RUN_SAMPLE_SIZE)
            ).all()
            queued_count = connection.execute(
                select(sa_func.count(AcousticAnalysisRunModel.id)).where(
                    AcousticAnalysisRunModel.status == "queued",
                )
            ).scalar_one()
            processing_count = connection.execute(
                select(sa_func.count(AcousticAnalysisRunModel.id)).where(
                    AcousticAnalysisRunModel.status == "processing",
                )
            ).scalar_one()
            oldest_queued_created_at = connection.execute(
                select(AcousticAnalysisRunModel.created_at)
                .where(AcousticAnalysisRunModel.status == "queued")
                .order_by(AcousticAnalysisRunModel.created_at.asc())
                .limit(1)
            ).scalar_one_or_none()
            # 24h-windowed, matching `ProductRepository.acoustic_analysis_
            # queue_diagnostics`'s identical scoping exactly (found via
            # review: an earlier version counted all-time here, so this
            # check and the runtime's own `status()` snapshot silently
            # reported two different numbers for what looked like the same
            # fact).
            recent_cutoff = datetime.now(UTC) - timedelta(hours=24)
            capacity_evicted_count = connection.execute(
                select(sa_func.count(AcousticAnalysisRunModel.id)).where(
                    AcousticAnalysisRunModel.error_code == "acoustic_queue_capacity_exceeded",
                    AcousticAnalysisRunModel.completed_at.is_not(None),
                    AcousticAnalysisRunModel.completed_at >= recent_cutoff,
                )
            ).scalar_one()
    except OperationalError:
        # A database whose recorded schema predates schema 43 (this table's
        # own migration) has no such table yet -- an honest "not migrated to
        # that point" fact, not an unexpected Doctor failure; the Database
        # Schema check above already reports the version gap itself.
        return {
            "sampled_count": 0, "failed_count": 0, "table_available": False,
            "birdnet_runtime_available": birdnet_status.runtime_available,
        }
    statuses = [row[0] for row in rows]
    oldest_queued_age_seconds = None
    if oldest_queued_created_at is not None:
        oldest_queued_age_seconds = (
            datetime.now(UTC) - normalize_utc(oldest_queued_created_at)
        ).total_seconds()
    return {
        "sampled_count": len(statuses),
        "failed_count": sum(1 for status in statuses if status == "failed"),
        "most_recent_error_code": next((row[1] for row in rows if row[0] == "failed"), None),
        "table_available": True,
        "queued_count": queued_count,
        "processing_count": processing_count,
        "oldest_queued_age_seconds": oldest_queued_age_seconds,
        "capacity_evicted_count": capacity_evicted_count,
        "birdnet_runtime_available": birdnet_status.runtime_available,
    }


def _interpret_acoustic_runtime(gathered: dict[str, Any]) -> DoctorCheckResult:
    context = {
        "sampled_run_count": gathered.get("sampled_count", 0),
        "failed_count": gathered.get("failed_count", 0),
        "queued_count": gathered.get("queued_count"),
        "processing_count": gathered.get("processing_count"),
        "oldest_queued_age_seconds": gathered.get("oldest_queued_age_seconds"),
        "capacity_evicted_count": gathered.get("capacity_evicted_count"),
        "birdnet_runtime_available": gathered.get("birdnet_runtime_available"),
    }
    if gathered.get("table_available") is False:
        return DoctorCheckResult(
            code=DoctorCheckCode.ACOUSTIC_RUNTIME,
            component="Acoustic runtime",
            status=DoctorStatus.PASS,
            summary="Acoustic analysis history isn't available yet.",
            detail="This database has not been migrated to the schema version that added it. See the Database Schema check.",
            recoverability=DoctorRecoverability.INFORMATIONAL,
            diagnostic_context=context,
        )
    if not gathered.get("birdnet_runtime_available"):
        return DoctorCheckResult(
            code=DoctorCheckCode.ACOUSTIC_RUNTIME,
            component="Acoustic runtime",
            status=DoctorStatus.PASS,
            summary="The optional BirdNET acoustic runtime is not installed.",
            detail="Visual observation is unaffected; recorded-audio/microphone analysis is unavailable until it is installed.",
            recoverability=DoctorRecoverability.INFORMATIONAL,
            diagnostic_context=context,
        )
    if gathered.get("sampled_count", 0) == 0:
        return DoctorCheckResult(
            code=DoctorCheckCode.ACOUSTIC_RUNTIME,
            component="Acoustic runtime",
            status=DoctorStatus.PASS,
            summary="No acoustic analysis has been run yet.",
            detail="This is expected until a recorded audio clip is analyzed or live microphone capture is used.",
            recoverability=DoctorRecoverability.INFORMATIONAL,
            diagnostic_context=context,
        )
    oldest_queued_age_seconds = gathered.get("oldest_queued_age_seconds")
    if oldest_queued_age_seconds is not None and oldest_queued_age_seconds > _STALE_ACOUSTIC_QUEUE_AGE_SECONDS:
        return DoctorCheckResult(
            code=DoctorCheckCode.ACOUSTIC_RUNTIME,
            component="Acoustic runtime",
            status=DoctorStatus.WARN,
            summary=(
                f"Acoustic analysis has fallen behind: the oldest queued segment has been "
                f"waiting {oldest_queued_age_seconds / 60:.0f} minute(s)."
            ),
            detail="Visual observation is unaffected; this only concerns acoustic/microphone analysis.",
            recoverability=DoctorRecoverability.DEGRADED,
            user_action="Check that the application process is running and not overloaded.",
            diagnostic_context=context,
        )
    failed_count = gathered.get("failed_count", 0)
    if failed_count > 0:
        return DoctorCheckResult(
            code=DoctorCheckCode.ACOUSTIC_RUNTIME,
            component="Acoustic runtime",
            status=DoctorStatus.WARN,
            summary=f"{failed_count} of the last {gathered.get('sampled_count', 0)} acoustic analysis run(s) failed.",
            detail="Visual observation is unaffected; this only concerns acoustic/microphone analysis.",
            recoverability=DoctorRecoverability.DEGRADED,
            user_action="Check the most recent acoustic analysis error code, or try analyzing the recording again.",
            diagnostic_context=context,
        )
    return DoctorCheckResult(
        code=DoctorCheckCode.ACOUSTIC_RUNTIME,
        component="Acoustic runtime",
        status=DoctorStatus.PASS,
        summary=f"The last {gathered.get('sampled_count', 0)} acoustic analysis run(s) completed without error.",
        diagnostic_context=context,
    )


# --------------------------------------------------------------------------
# Research / export
# --------------------------------------------------------------------------


def _gather_research_export(engine: Engine) -> dict[str, Any]:
    from sqlalchemy.exc import OperationalError

    try:
        with engine.connect() as connection:
            rows = connection.execute(
                select(DatasetExportModel.status)
                .order_by(DatasetExportModel.created_at.desc())
                .limit(_RECENT_RUN_SAMPLE_SIZE)
            ).all()
    except OperationalError:
        # See `_gather_offline_ingest`'s identical guard: an honest "not
        # migrated that far yet" fact, never a raw exception here.
        return {"sampled_count": 0, "failed_count": 0, "table_available": False}
    statuses = [row[0] for row in rows]
    return {
        "sampled_count": len(statuses),
        "failed_count": sum(1 for status in statuses if status == "failed"),
        "table_available": True,
    }


def _interpret_research_export(gathered: dict[str, Any]) -> DoctorCheckResult:
    sampled_count = gathered.get("sampled_count", 0)
    context = {"sampled_export_count": sampled_count, "failed_count": gathered.get("failed_count", 0)}
    if gathered.get("table_available") is False:
        return DoctorCheckResult(
            code=DoctorCheckCode.RESEARCH_EXPORT,
            component="Research / export",
            status=DoctorStatus.PASS,
            summary="Export history isn't available yet.",
            detail="This database has not been migrated to a schema version that supports it.",
            recoverability=DoctorRecoverability.INFORMATIONAL,
            diagnostic_context=context,
        )
    if sampled_count == 0:
        return DoctorCheckResult(
            code=DoctorCheckCode.RESEARCH_EXPORT,
            component="Research / export",
            status=DoctorStatus.PASS,
            summary="No dataset export has been run yet.",
            recoverability=DoctorRecoverability.INFORMATIONAL,
            diagnostic_context=context,
        )
    failed_count = gathered.get("failed_count", 0)
    if failed_count > 0:
        return DoctorCheckResult(
            code=DoctorCheckCode.RESEARCH_EXPORT,
            component="Research / export",
            status=DoctorStatus.WARN,
            summary=f"{failed_count} of the last {sampled_count} export(s) failed.",
            detail="Reviewed history and Bird Log are unaffected; this only concerns dataset export runs.",
            recoverability=DoctorRecoverability.DEGRADED,
            user_action="Check available storage on the export folder's drive, then try the export again.",
            diagnostic_context=context,
        )
    return DoctorCheckResult(
        code=DoctorCheckCode.RESEARCH_EXPORT,
        component="Research / export",
        status=DoctorStatus.PASS,
        summary=f"The last {sampled_count} export(s) completed without error.",
        diagnostic_context=context,
    )


# --------------------------------------------------------------------------
# Media integrity
# --------------------------------------------------------------------------

# Bounded, cheap, stat-only -- never decodes/opens a media file's actual
# content (that would be real per-file I/O cost multiplied across a
# potentially large library, the opposite of Doctor's "single-digit
# milliseconds on a healthy install" budget). This can only ever find a
# *structural* problem (file missing, truncated, or zero bytes) -- never a
# claim about whether the image/video/audio decodes correctly. See
# docs/appliance-storage-privacy-recovery-v1-contract.md, "Doctor: media
# integrity."
_MEDIA_INTEGRITY_SAMPLE_SIZE = 25


def _gather_media_integrity(engine: Engine) -> dict[str, Any]:
    with engine.connect() as connection:
        rows = connection.execute(
            select(MediaAssetModel.local_path, MediaAssetModel.file_size_bytes)
            .order_by(MediaAssetModel.created_at.desc())
            .limit(_MEDIA_INTEGRITY_SAMPLE_SIZE)
        ).all()
    missing_count = 0
    size_mismatch_count = 0
    for local_path, expected_size in rows:
        try:
            actual_size = Path(local_path).stat().st_size
        except OSError:
            missing_count += 1
            continue
        if actual_size == 0 or (expected_size and actual_size != expected_size):
            size_mismatch_count += 1
    return {
        "sampled_count": len(rows),
        "missing_count": missing_count,
        "size_mismatch_count": size_mismatch_count,
    }


def _interpret_media_integrity(gathered: dict[str, Any]) -> DoctorCheckResult:
    sampled_count = gathered.get("sampled_count", 0)
    missing_count = gathered.get("missing_count", 0)
    size_mismatch_count = gathered.get("size_mismatch_count", 0)
    context = {
        "sampled_count": sampled_count,
        "missing_count": missing_count,
        "size_mismatch_count": size_mismatch_count,
    }
    if sampled_count == 0:
        return DoctorCheckResult(
            code=DoctorCheckCode.MEDIA_INTEGRITY,
            component="Media integrity",
            status=DoctorStatus.PASS,
            summary="No retained media to check yet.",
            recoverability=DoctorRecoverability.INFORMATIONAL,
            diagnostic_context=context,
        )
    problem_count = missing_count + size_mismatch_count
    if problem_count:
        return DoctorCheckResult(
            code=DoctorCheckCode.MEDIA_INTEGRITY,
            component="Media integrity",
            status=DoctorStatus.WARN,
            summary=f"{problem_count} of the last {sampled_count} retained media file(s) look incomplete or missing.",
            detail=(
                "This is a lightweight sample of the most recently created media, not a "
                "full library scan. Reviewed history and evidence relationships are unaffected."
            ),
            recoverability=DoctorRecoverability.DEGRADED,
            user_action="Restore from a recent backup if this evidence matters.",
            diagnostic_context=context,
        )
    return DoctorCheckResult(
        code=DoctorCheckCode.MEDIA_INTEGRITY,
        component="Media integrity",
        status=DoctorStatus.PASS,
        summary=f"The last {sampled_count} retained media file(s) checked out (present, correctly sized).",
        diagnostic_context=context,
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
                export_roots={
                    "research_exports": environment.research_export_root,
                    "classifier_manifest_exports": environment.classifier_manifest_export_root,
                },
                engine=engine,
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

    if engine is not None:
        checks.append(
            _execute_check(
                code=DoctorCheckCode.CAMERA_NODE_TRANSPORT,
                component="Camera Node transport",
                gather=lambda: _gather_camera_node_transport(engine, transport_root=environment.transport_root),
                interpret=lambda gathered: _interpret_camera_node_transport(gathered, now=current_time),
                timeout_seconds=timeout_seconds,
            )
        )
    else:
        checks.append(
            _execute_check(
                code=DoctorCheckCode.CAMERA_NODE_TRANSPORT,
                component="Camera Node transport",
                gather=None,
                interpret=lambda gathered: _interpret_camera_node_transport(gathered, now=current_time),
                skip_reason="Skipped because the database is unavailable.",
            )
        )

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
        checks.append(
            _execute_check(
                code=DoctorCheckCode.OFFLINE_INGEST,
                component="Offline ingest",
                gather=lambda: _gather_offline_ingest(engine),
                interpret=_interpret_offline_ingest,
                timeout_seconds=timeout_seconds,
            )
        )
        checks.append(
            _execute_check(
                code=DoctorCheckCode.RESEARCH_EXPORT,
                component="Research / export",
                gather=lambda: _gather_research_export(engine),
                interpret=_interpret_research_export,
                timeout_seconds=timeout_seconds,
            )
        )
        checks.append(
            _execute_check(
                code=DoctorCheckCode.ACOUSTIC_RUNTIME,
                component="Acoustic runtime",
                gather=lambda: _gather_acoustic_runtime(engine),
                interpret=_interpret_acoustic_runtime,
                timeout_seconds=timeout_seconds,
            )
        )
        checks.append(
            _execute_check(
                code=DoctorCheckCode.MEDIA_INTEGRITY,
                component="Media integrity",
                gather=lambda: _gather_media_integrity(engine),
                interpret=_interpret_media_integrity,
                timeout_seconds=timeout_seconds,
            )
        )
    else:
        checks.append(
            _execute_check(
                code=DoctorCheckCode.OFFLINE_INGEST,
                component="Offline ingest",
                gather=None,
                interpret=_interpret_offline_ingest,
                skip_reason="Skipped because the database is unavailable.",
            )
        )
        checks.append(
            _execute_check(
                code=DoctorCheckCode.RESEARCH_EXPORT,
                component="Research / export",
                gather=None,
                interpret=_interpret_research_export,
                skip_reason="Skipped because the database is unavailable.",
            )
        )
        checks.append(
            _execute_check(
                code=DoctorCheckCode.ACOUSTIC_RUNTIME,
                component="Acoustic runtime",
                gather=None,
                interpret=_interpret_acoustic_runtime,
                skip_reason="Skipped because the database is unavailable.",
            )
        )
        checks.append(
            _execute_check(
                code=DoctorCheckCode.MEDIA_INTEGRITY,
                component="Media integrity",
                gather=None,
                interpret=_interpret_media_integrity,
                skip_reason="Skipped because the database is unavailable.",
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
