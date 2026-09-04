#!/usr/bin/env python3
"""Field-Acceptance Instance Lifecycle & Storage Safety v1: identify a
disposable field-acceptance Windows dev-root, track its lifecycle
(active -> completed -> archived), assess whether it is safe to reclaim,
and -- only on explicit operator request -- remove it.

## Why this exists

Every real Representative Daylight Gate A field-acceptance session so far
(V4 through V9) deployed to a fresh, disposable ``--dev-root`` (see
``scripts/deploy_windows_dev.py``) and then left it running/retained
indefinitely after acceptance -- ``deploy_windows_dev.py`` has no
standalone "just stop it" command (only ``--rollback``, which relaunches
the *previous* release) and no concept of "this dev-root is disposable, it
is safe to delete." Two real, reproduced storage crises followed
(Representative Daylight Gate A Field Acceptance v8: 9.43GB free at start,
~3.5GB free after; v9: **1.37GB free** at start, requiring an operator to
manually stop a stale idle instance and delete ~65GB across four old
instance roots by hand before v9 could even be deployed). See
docs/field-acceptance-instance-lifecycle-storage-safety-v1-report.md for
the complete root-cause record.

This tool never re-implements ``deploy_windows_dev.py``'s own release
materialization, cache population, or process-safety primitives -- it
*reuses* them (via the same ``runpy.run_path`` sibling-script convention
``deploy_windows_dev.py`` already uses for ``build_local_product.py``) and
layers exactly one new concept on top: an explicit, durable, self
-verifying **disposable-instance marker** (``field_acceptance_manifest.json``,
sitting beside ``deploy_windows_dev.py``'s own ``deployments.json``/
``current.json``) plus the lifecycle/reclaimability/cleanup operations
built on it.

## What this is not

Not a general disk cleaner. It never scans or deletes an unmarked
directory (see ``refuse_unsafe_root``/§14 of the governing brief), never
touches the shared runtime/model/BioCLIP-model cache logic
``deploy_windows_dev.py --gc-cache`` already owns (each dev-root's own
cache tiers are private to it -- see the module docstring section "Cache
scope" below), and never deletes anything by default: every mutating
command requires an explicit verb (``init``, ``complete``,
``mark-archived``) or an explicit ``--destroy`` flag (``cleanup``).

## Lifecycle

    active -> completed -> archived  (stored in the manifest)
                              |
                              v
                      SAFE_TO_RECLAIM     (computed fresh at assess/cleanup
                                            time, never stored/trusted stale)

- **active**: created by ``init`` right after a field-acceptance deploy.
- **completed**: the operator has verified (via a fresh live re-check, not
  a stale recollection) that the deployed process is no longer running --
  see ``complete``. Stop it first with ``deploy_windows_dev.py --dev-root
  <root> --stop``.
- **archived**: the operator has pointed at an evidence-archive directory
  and this tool has verified it contains, at minimum, a written report/
  provenance record and some raw accounting/evidence data -- see
  ``mark-archived``/``verify_archive_contract``.
- **SAFE_TO_RECLAIM** is a verdict, not a fourth stored state: it is true
  only when a *fresh* re-check, right now, confirms archived-in-the-
  manifest AND still-not-running AND still-not-actively-observing. A
  manifest recording "archived" can never by itself authorize deletion --
  this is what stops a manually-relaunched process from being deleted out
  from under itself if the manifest happens to be stale.

### Crash / interrupted session

A field run that crashes (or is force-killed, or loses power) never
reaches ``complete``/``mark-archived`` -- the manifest simply stays at
whatever state an operator last explicitly set (``active``, if nothing
had happened yet). ``assess`` reports this precisely
(``NOT_RECLAIMABLE_UNARCHIVED``, distinguishing "never marked complete --
possible crash" from "completed, not yet archived" in its own reason
text) and it stays that way until an operator *deliberately* resolves
evidence disposition -- never inferred, never auto-promoted toward
reclaimable.

### Restart / recovery

A ``completed``-but-not-yet-``archived`` (or even ``active``) instance
remains fully restartable under the existing deployment model -- nothing
here disables or interferes with an ordinary
``deploy_windows_dev.py --dev-root <root> ...`` redeploy into the same
root. If an operator restarts it, the stored manifest can briefly say
"completed" while the process is, in fact, running again; this is
self-correcting, not a safety gap, because every lifecycle decision
(``assess``, ``complete``, ``cleanup``) always re-probes the live process
fresh rather than trusting the stored state alone -- the very next
``assess`` reports ``NOT_RECLAIMABLE_ACTIVE`` regardless of what the
manifest says.

## Usage

    # Right after `deploy_windows_dev.py --dev-root <root> ...` for a
    # disposable field-acceptance session:
    python scripts/field_acceptance_instance_lifecycle.py init --dev-root <root>

    # At any time, read-only:
    python scripts/field_acceptance_instance_lifecycle.py status --dev-root <root>
    python scripts/field_acceptance_instance_lifecycle.py assess --dev-root <root> --json

    # End of session, after `deploy_windows_dev.py --dev-root <root> --stop`:
    python scripts/field_acceptance_instance_lifecycle.py complete --dev-root <root>
    python scripts/field_acceptance_instance_lifecycle.py mark-archived --dev-root <root> \\
        --evidence-archive data/field-acceptance/<slug>

    # Dry-run (default) then explicit destructive cleanup:
    python scripts/field_acceptance_instance_lifecycle.py cleanup --dev-root <root>
    python scripts/field_acceptance_instance_lifecycle.py cleanup --dev-root <root> --destroy

    # Before starting a new session, across every known disposable instance:
    python scripts/field_acceptance_instance_lifecycle.py preflight --dev-root <new-root> \\
        --recorder-max-bytes 4000000000

Exit code is 0 for a successful/safe outcome (including an honest "not
reclaimable yet" ``assess``/dry-run ``cleanup`` -- those are correct
answers, not failures) and 1 for a real error or a fail-closed refusal --
safe to use directly in a field-acceptance shell sequence.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import runpy
import shutil
import sys
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]

# ---------------------------------------------------------------------------
# Reuse scripts/deploy_windows_dev.py and scripts/field_acceptance_client.py
# -- never a second implementation of release/process/HTTP-client logic.
# `scripts/` is deliberately not a package (matching both of those files'
# own established convention), so both are loaded via `runpy.run_path`
# rather than a normal import -- this keeps loading correct regardless of
# how *this* script itself is invoked or imported (a real CLI run, or a
# `runpy.run_path` load from a test file), exactly the reason
# `deploy_windows_dev.py` gives for loading `build_local_product.py` the
# same way (see its own `_blp()`).
# ---------------------------------------------------------------------------

_dwd_module: dict[str, object] | None = None
_fac_module: dict[str, object] | None = None


def _dwd() -> dict[str, object]:
    global _dwd_module
    if _dwd_module is None:
        _dwd_module = runpy.run_path(str(ROOT / "scripts" / "deploy_windows_dev.py"))
    return _dwd_module


def _fac() -> dict[str, object]:
    global _fac_module
    if _fac_module is None:
        _fac_module = runpy.run_path(str(ROOT / "scripts" / "field_acceptance_client.py"))
    return _fac_module


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MANIFEST_FILENAME = "field_acceptance_manifest.json"
MANIFEST_SCHEMA_VERSION = 1
PURPOSE_FIELD_ACCEPTANCE = "field_acceptance"

LIFECYCLE_ACTIVE = "active"
LIFECYCLE_COMPLETED = "completed"
LIFECYCLE_ARCHIVED = "archived"
LIFECYCLE_STATES = (LIFECYCLE_ACTIVE, LIFECYCLE_COMPLETED, LIFECYCLE_ARCHIVED)

SAFE_TO_RECLAIM = "SAFE_TO_RECLAIM"
NOT_RECLAIMABLE_ACTIVE = "NOT_RECLAIMABLE_ACTIVE"
NOT_RECLAIMABLE_UNARCHIVED = "NOT_RECLAIMABLE_UNARCHIVED"
NOT_RECLAIMABLE_UNKNOWN_INSTANCE = "NOT_RECLAIMABLE_UNKNOWN_INSTANCE"

# Mirrors `AcceptanceRecorderConfig.__post_init__`'s own upper bound
# exactly (`src/mockingbird/observation/acceptance_recorder.py`) --
# duplicated as a literal, not imported, the same "this module never
# depends on the product package's own namespace" convention
# `mockingbird.runtime_state`'s own `BUILD_INFO_FILENAME` comment already
# establishes (and `deploy_windows_dev.py` itself follows by never
# importing `mockingbird` at all -- see that file's module docstring).
# Keep this in sync if the product-side ceiling ever changes.
ACCEPTANCE_RECORDER_HARD_CEILING_BYTES = 5_000_000_000

# Mirrors `src/mockingbird/storage/database.py`'s own graduated
# healthy/getting_low/action_recommended/critical ladder exactly (same
# "duplicated as a literal" reasoning as above) -- this is the same,
# already-accepted, already-frozen (Lane M) disk-pressure contract the
# running product itself uses for `/api/product/health`, never a second,
# independently-invented threshold set.
GETTING_LOW_DISK_FREE_BYTES_THRESHOLD = 5_000_000_000
GETTING_LOW_DISK_FREE_RATIO_THRESHOLD = 0.15
LOW_DISK_FREE_BYTES_THRESHOLD = 1_000_000_000
LOW_DISK_FREE_RATIO_THRESHOLD = 0.05
CRITICAL_DISK_FREE_BYTES_THRESHOLD = 200_000_000
CRITICAL_DISK_FREE_RATIO_THRESHOLD = 0.01

# The minimum extra headroom (beyond the recorder budget itself) a session
# must leave behind -- reuses the exact same `action_recommended` boundary
# above, rather than a new arbitrary number: "enough that the *product
# itself*, running on this same volume, would not already consider this
# volume under storage pressure once the session's own budget is spent."
DEFAULT_RESERVE_BYTES = LOW_DISK_FREE_BYTES_THRESHOLD


class InstanceLifecycleError(RuntimeError):
    """Raised for a fail-closed refusal or a real operational failure.
    Every message is written to be printed directly to an operator."""


# ---------------------------------------------------------------------------
# Manifest: the smallest durable marker of "this dev-root is a disposable
# field-acceptance instance" -- see the module docstring's "Lifecycle"
# section. Deliberately a sidecar JSON file next to `deploy_windows_dev.py`'s
# own `deployments.json`/`current.json`, never a change to that file's own
# schema or code path.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class InstanceManifest:
    schema_version: int
    purpose: str
    dev_root: str  # canonical (resolved) path, as a string -- see `refuse_unsafe_root`
    created_at: str
    created_by_commit: str | None
    created_by_build_id: str | None
    lifecycle_state: str
    completed_at: str | None = None
    evidence_archive_path: str | None = None
    archived_at: str | None = None
    notes: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "purpose": self.purpose,
            "dev_root": self.dev_root,
            "created_at": self.created_at,
            "created_by_commit": self.created_by_commit,
            "created_by_build_id": self.created_by_build_id,
            "lifecycle_state": self.lifecycle_state,
            "completed_at": self.completed_at,
            "evidence_archive_path": self.evidence_archive_path,
            "archived_at": self.archived_at,
            "notes": self.notes,
        }

    @staticmethod
    def from_dict(payload: dict[str, Any]) -> "InstanceManifest":
        return InstanceManifest(
            schema_version=int(payload.get("schema_version", MANIFEST_SCHEMA_VERSION)),
            purpose=str(payload.get("purpose", PURPOSE_FIELD_ACCEPTANCE)),
            dev_root=str(payload["dev_root"]),
            created_at=str(payload.get("created_at", "")),
            created_by_commit=payload.get("created_by_commit"),
            created_by_build_id=payload.get("created_by_build_id"),
            lifecycle_state=str(payload.get("lifecycle_state", LIFECYCLE_ACTIVE)),
            completed_at=payload.get("completed_at"),
            evidence_archive_path=payload.get("evidence_archive_path"),
            archived_at=payload.get("archived_at"),
            notes=str(payload.get("notes", "")),
        )


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def manifest_path(dev_root: Path) -> Path:
    return dev_root / MANIFEST_FILENAME


def read_manifest(dev_root: Path) -> InstanceManifest | None:
    """`None` for "no manifest, corrupt manifest, or wrong shape" alike --
    every caller must treat all three identically (never eligible for any
    lifecycle operation this tool performs), mirroring
    `deploy_windows_dev.read_deployments`'s own "missing/corrupt reads as
    absent, never raises" convention."""

    try:
        payload = json.loads(manifest_path(dev_root).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(payload, dict) or not isinstance(payload.get("dev_root"), str):
        return None
    try:
        return InstanceManifest.from_dict(payload)
    except (KeyError, TypeError, ValueError):
        return None


def write_manifest(dev_root: Path, manifest: InstanceManifest) -> None:
    manifest_path(dev_root).write_text(
        json.dumps(manifest.as_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# Path safety (governing brief §34): resolve canonically, confirm the
# marker's own recorded identity matches the resolved target exactly (so a
# copied/relocated manifest or a symlink swap cannot claim a false
# identity), and refuse a small deny-list of "obviously not a disposable
# per-instance root" targets. Every function that can ever delete
# anything calls this first.
# ---------------------------------------------------------------------------


def _resolve(path: Path) -> Path:
    return Path(path).resolve()


def refuse_unsafe_root(resolved: Path, *, windows_host: Any, dwd: dict[str, object]) -> None:
    """Raise `InstanceLifecycleError` for every target this tool must never
    treat as a disposable field-acceptance instance root, regardless of
    what a manifest sitting inside it might claim. Called before trusting
    *anything* about `resolved`, including before reading its manifest for
    `init` (so `init` itself cannot mark an unsafe root disposable) and
    again, redundantly, immediately before any destructive removal."""

    if resolved == resolved.anchor or resolved.parent == resolved:
        raise InstanceLifecycleError(f"Refusing to operate on a filesystem root: {resolved}")
    try:
        home = Path(os.path.expanduser("~")).resolve()
    except OSError:
        home = None
    if home is not None and resolved == home:
        raise InstanceLifecycleError(f"Refusing to operate on a home directory: {resolved}")
    try:
        local_appdata = _resolve(windows_host.local_appdata())
    except Exception:  # noqa: BLE001 - a probe failure must never be treated as "safe"
        local_appdata = None
    if local_appdata is not None:
        if resolved == local_appdata:
            raise InstanceLifecycleError(f"Refusing to operate on %LOCALAPPDATA% itself: {resolved}")
        # The real production install (`%LOCALAPPDATA%\MockingBird`, never
        # `...\MockingBirdDev` or an operator-chosen disposable name) --
        # `deploy_windows_dev.py` never writes here; refusing it by name is
        # an extra, redundant guard on top of the ledger-file check below,
        # which would already fail for a real production install.
        if resolved == local_appdata / "MockingBird":
            raise InstanceLifecycleError(f"Refusing to operate on the real production install root: {resolved}")
        default_dev_root = local_appdata / dwd["DEV_ROOT_DIRNAME"]
        if resolved == default_dev_root:
            raise InstanceLifecycleError(
                f"Refusing to operate on the shared persistent dev root ({resolved}) through this tool -- "
                "a disposable field-acceptance instance must use a distinct --dev-root, never the operator's "
                "own long-lived MockingBirdDev identity (matching every real Gate A field-acceptance session's "
                "own established convention)."
            )


def _looks_like_deploy_tool_root(resolved: Path, dwd: dict[str, object]) -> bool:
    """Whether `resolved` is a directory `deploy_windows_dev.py` itself has
    actually deployed into at least once -- its own append-only ledger
    file must exist. Belt-and-suspenders alongside the manifest's own
    self-referential identity check below: a hand-crafted manifest dropped
    into an arbitrary directory still cannot pass both checks."""

    ledger_path = dwd["_ledger_path"](resolved)  # type: ignore[operator]
    return ledger_path.is_file()


def _find_escaping_links(root: Path) -> list[Path]:
    """Bounded (top-level entries only, matching this tool's own "not a
    general disk cleaner" scope) scan for a symlink/junction whose target
    resolves outside `root` -- see governing brief §34's "symlink/junction
    escape." Real, disclosed limitation: `deploy_windows_dev.py`'s own
    `_remove_junction_real` docstring already documents that WSL-side path
    resolution can, in this exact environment, silently resolve *through*
    a real Windows reparse point -- this scan is a best-effort pre-flight
    sanity check, not a substitute for the fact that the actual removal
    below always delegates to `deploy_windows_dev.py`'s own already
    -hardened `WindowsHost.remove_tree` (native `cmd.exe /c rmdir /s /q`,
    never a naive recursive Python delete), the same primitive
    `deploy_windows_dev.py` itself already trusts for this exact class of
    hazard."""

    escaping: list[Path] = []
    try:
        entries = list(root.iterdir())
    except OSError:
        return escaping
    for entry in entries:
        if entry.is_symlink():
            try:
                target = entry.resolve()
            except OSError:
                escaping.append(entry)
                continue
            if root not in target.parents and target != root:
                escaping.append(entry)
    return escaping


# ---------------------------------------------------------------------------
# init: mark a dev-root as a disposable field-acceptance instance.
# ---------------------------------------------------------------------------


def init_instance(
    *, dev_root: Path, windows_host: Any, notes: str = "", force: bool = False,
) -> InstanceManifest:
    dwd = _dwd()
    resolved = _resolve(dev_root)
    refuse_unsafe_root(resolved, windows_host=windows_host, dwd=dwd)
    if not _looks_like_deploy_tool_root(resolved, dwd):
        raise InstanceLifecycleError(
            f"{resolved} has no deployments.json -- it does not look like a directory "
            "scripts/deploy_windows_dev.py has ever deployed into. Deploy to it first "
            "(python scripts/deploy_windows_dev.py --dev-root <root> ...), then init."
        )
    existing = read_manifest(resolved)
    if existing is not None and not force:
        raise InstanceLifecycleError(
            f"{resolved} is already marked ({existing.lifecycle_state}, created {existing.created_at}) -- "
            "refusing to overwrite an existing manifest. Pass force=True/--force if you really intend to "
            "reset its lifecycle state back to active."
        )

    current_pointer = dwd["read_current"](resolved)  # type: ignore[operator]
    created_by_commit: str | None = None
    created_by_build_id: str | None = None
    if current_pointer is not None:
        for record in dwd["read_deployments"](resolved):  # type: ignore[operator]
            if record.sha == current_pointer.sha:
                created_by_commit, created_by_build_id = record.full_commit, record.build_id
                break

    manifest = InstanceManifest(
        schema_version=MANIFEST_SCHEMA_VERSION,
        purpose=PURPOSE_FIELD_ACCEPTANCE,
        dev_root=str(resolved),
        created_at=existing.created_at if existing is not None else _now_iso(),
        created_by_commit=created_by_commit,
        created_by_build_id=created_by_build_id,
        lifecycle_state=LIFECYCLE_ACTIVE,
        notes=notes,
    )
    write_manifest(resolved, manifest)
    return manifest


# ---------------------------------------------------------------------------
# assess: the dry-run reclaimability check (governing brief §11).
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AssessmentResult:
    dev_root: str
    verdict: str
    reason: str
    identity_confirmed: bool
    process_running: bool | None
    observation_active: bool | None
    lifecycle_state: str | None
    evidence_archive_path: str | None
    size_on_disk_bytes: int | None
    reclaimable_bytes: int | None
    created_at: str | None = None
    created_by_commit: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def directory_size_bytes(root: Path) -> int:
    """Plain recursive filesystem size -- a stat-only read, no different
    from any other "plain filesystem operation" this codebase already does
    directly rather than through a Windows-native process (see
    `deploy_windows_dev.real_windows_host`'s own docstring reasoning).
    Missing/unreadable entries are skipped rather than raising -- an
    approximate figure for observability, never a value anything
    safety-critical is computed from."""

    total = 0
    for current_dir, _subdirs, files in os.walk(root):
        for name in files:
            try:
                total += (Path(current_dir) / name).lstat().st_size
            except OSError:
                continue
    return total


def _probe_running(
    *, dev_root: Path, windows_host: Any, dwd: dict[str, object],
) -> tuple[bool, object | None, int | None]:
    """`(process_running, owning_release_or_None, port_or_None)`. Reads the
    port from this dev-root's own `current.json` (never a hardcoded
    default) -- `deploy_windows_dev.py` already records exactly this fact
    at deploy time; re-deriving it independently would risk drifting from
    what was actually launched. No recorded pointer at all means nothing
    has ever been launched here -- not running, by construction."""

    current_pointer = dwd["read_current"](dev_root)  # type: ignore[operator]
    if current_pointer is None:
        return False, None, None
    occupant = dwd["probe_port"](  # type: ignore[operator]
        dwd["DEFAULT_HOST"], current_pointer.port, windows_host=windows_host,
    )
    owning_release = dwd["verified_owning_release"](occupant, dev_root)  # type: ignore[operator]
    return owning_release is not None, owning_release, current_pointer.port


def _probe_observation_active(streams_client: Any) -> bool | None:
    """Best-effort only: `None` ("unknown") whenever this cannot be
    confirmed either way -- no field-acceptance credential configured, the
    instance unreachable, or any other failure -- never guessed. Does not
    change the reclaimability verdict either way (a running process alone
    already blocks reclamation, per the governing brief's own "active/
    running... fail closed" phrasing); this only enriches the
    human-readable diagnostic so a genuinely-idle-but-still-running stale
    process (governing brief §27) reads differently from one with a live
    session in progress."""

    try:
        streams = streams_client.list_streams()
    except Exception:  # noqa: BLE001 - any failure here means "unknown", not "not observing"
        return None
    if not isinstance(streams, list):
        return None
    active = False
    for stream in streams:
        stream_id = stream.get("id") if isinstance(stream, dict) else None
        if not stream_id:
            continue
        try:
            status = streams_client.observation_status(stream_id)
        except Exception:  # noqa: BLE001
            return None
        if isinstance(status, dict) and status.get("observing"):
            active = True
    return active


def assess_instance(
    *, dev_root: Path, windows_host: Any, check_observation: bool = True,
) -> AssessmentResult:
    dwd = _dwd()
    resolved = _resolve(dev_root)
    manifest = read_manifest(resolved)
    identity_confirmed = (
        manifest is not None
        and manifest.purpose == PURPOSE_FIELD_ACCEPTANCE
        and manifest.dev_root == str(resolved)
        and _looks_like_deploy_tool_root(resolved, dwd)
    )

    if not identity_confirmed:
        # Deliberately never computes `directory_size_bytes` here -- a
        # real-Windows proof of this exact tool found that doing so
        # unconditionally made a refusal against a large, long-lived,
        # many-release persistent dev-root (29GB+, accessed through the
        # slow WSL<->Windows filesystem bridge) take minutes to report a
        # decision that should be instant. Safety was never at risk (this
        # branch was always going to refuse regardless of size), only
        # performance -- a directory this tool does not recognize gets an
        # immediate, cheap answer, never a full byte-count walk first.
        return AssessmentResult(
            dev_root=str(resolved),
            verdict=NOT_RECLAIMABLE_UNKNOWN_INSTANCE,
            reason=(
                "No valid, self-identity-matching field-acceptance manifest found here -- either this is an "
                "ordinary/unmarked directory, a normal product instance, or the manifest's own recorded "
                "identity does not match this resolved path. This tool never treats an unmarked directory as "
                "a disposable instance; run 'init' first if this really is one."
            ),
            identity_confirmed=False,
            process_running=None,
            observation_active=None,
            lifecycle_state=None,
            evidence_archive_path=None,
            size_on_disk_bytes=None,
            reclaimable_bytes=None,
        )

    assert manifest is not None
    size_bytes = directory_size_bytes(resolved) if resolved.is_dir() else None
    process_running, _owning_release, port = _probe_running(dev_root=resolved, windows_host=windows_host, dwd=dwd)
    observation_active: bool | None = None
    if process_running and check_observation and port is not None:
        try:
            client_module = _fac()
            base_url = dwd["_local_base_url"](dwd["DEFAULT_HOST"], port)  # type: ignore[operator]
            client = client_module["FieldAcceptanceClient"](base_url=base_url)  # type: ignore[operator]
            observation_active = _probe_observation_active(client)
        except Exception:  # noqa: BLE001 - no credential configured, etc. -- stays "unknown"
            observation_active = None

    if process_running:
        detail = "" if observation_active is None else (
            " (actively observing right now)" if observation_active else " (running, but not currently observing)"
        )
        return AssessmentResult(
            dev_root=str(resolved),
            verdict=NOT_RECLAIMABLE_ACTIVE,
            reason=f"The deployed process is still running{detail} -- stop it first "
            "(python scripts/deploy_windows_dev.py --dev-root <root> --stop), then 'complete'.",
            identity_confirmed=True,
            process_running=True,
            observation_active=observation_active,
            lifecycle_state=manifest.lifecycle_state,
            evidence_archive_path=manifest.evidence_archive_path,
            size_on_disk_bytes=size_bytes,
            reclaimable_bytes=None,
            created_at=manifest.created_at,
            created_by_commit=manifest.created_by_commit,
        )

    if manifest.lifecycle_state != LIFECYCLE_ARCHIVED:
        if manifest.lifecycle_state == LIFECYCLE_ACTIVE:
            reason = (
                "The process is not running, but this session was never marked 'completed' -- this can mean "
                "a crash or an interrupted session. It stays non-reclaimable until an operator deliberately "
                "resolves evidence disposition ('complete' then 'mark-archived'), never inferred automatically."
            )
        else:
            reason = (
                "The session is completed but not yet archived -- run 'mark-archived --evidence-archive <path>' "
                "once the field report's required evidence is preserved."
            )
        return AssessmentResult(
            dev_root=str(resolved),
            verdict=NOT_RECLAIMABLE_UNARCHIVED,
            reason=reason,
            identity_confirmed=True,
            process_running=False,
            observation_active=observation_active,
            lifecycle_state=manifest.lifecycle_state,
            evidence_archive_path=manifest.evidence_archive_path,
            size_on_disk_bytes=size_bytes,
            reclaimable_bytes=None,
            created_at=manifest.created_at,
            created_by_commit=manifest.created_by_commit,
        )

    return AssessmentResult(
        dev_root=str(resolved),
        verdict=SAFE_TO_RECLAIM,
        reason="Stopped, archived, and re-verified just now -- safe to reclaim with 'cleanup --destroy'.",
        identity_confirmed=True,
        process_running=False,
        observation_active=observation_active,
        lifecycle_state=manifest.lifecycle_state,
        evidence_archive_path=manifest.evidence_archive_path,
        size_on_disk_bytes=size_bytes,
        reclaimable_bytes=size_bytes,
        created_at=manifest.created_at,
        created_by_commit=manifest.created_by_commit,
    )


# ---------------------------------------------------------------------------
# complete / mark-archived: the explicit, operator-driven lifecycle
# transitions (governing brief §7's "critical invariant" -- stopping a
# process is never, by itself, treated as "safe to delete").
# ---------------------------------------------------------------------------


def complete_instance(*, dev_root: Path, windows_host: Any) -> InstanceManifest:
    dwd = _dwd()
    resolved = _resolve(dev_root)
    manifest = read_manifest(resolved)
    if manifest is None or manifest.dev_root != str(resolved):
        raise InstanceLifecycleError(f"{resolved} has no matching field-acceptance manifest -- run 'init' first.")
    process_running, _owning_release, _port = _probe_running(dev_root=resolved, windows_host=windows_host, dwd=dwd)
    if process_running:
        raise InstanceLifecycleError(
            f"{resolved}'s deployed process is still running -- stop it first "
            "(python scripts/deploy_windows_dev.py --dev-root <root> --stop) before marking it complete."
        )
    if manifest.lifecycle_state == LIFECYCLE_ACTIVE:
        manifest = replace(manifest, lifecycle_state=LIFECYCLE_COMPLETED, completed_at=_now_iso())
        write_manifest(resolved, manifest)
    return manifest


_REQUIRED_ARCHIVE_CATEGORIES: dict[str, Callable[[str], bool]] = {
    # A written record (report/provenance) -- every real archived tranche
    # under data/field-acceptance/ carries at least one, named either
    # PROVENANCE.md or a *-report.md, but naming varies session to
    # session, so this matches any Markdown file rather than one exact
    # filename (see governing brief §10: "Do not invent a policy that
    # every byte ... must be archived" -- the flip side is also true, this
    # never assumes one exact filename either).
    "written_report_or_provenance": lambda name: name.lower().endswith(".md"),
    # Some raw accounting/ledger/evidence data alongside the prose --
    # counterfactual snapshots, accounting reports, or pixel-crop review
    # images all satisfy this; deliberately broad (any non-Markdown data
    # file) rather than a fixed filename list, for the same reason.
    "raw_evidence_or_accounting": lambda name: not name.lower().endswith(".md") and not name.startswith("."),
}


def verify_archive_contract(path: Path) -> tuple[bool, list[str]]:
    """Whether `path` looks like a genuine archived field-acceptance
    evidence tranche -- present, non-empty, and containing at least one
    file per category in `_REQUIRED_ARCHIVE_CATEGORIES`, checked
    recursively. Returns `(ok, missing_category_names)`."""

    if not path.is_dir():
        return False, list(_REQUIRED_ARCHIVE_CATEGORIES)
    found: set[str] = set()
    for current_dir, _subdirs, files in os.walk(path):
        for name in files:
            for category, predicate in _REQUIRED_ARCHIVE_CATEGORIES.items():
                if category not in found and predicate(name):
                    found.add(category)
        if len(found) == len(_REQUIRED_ARCHIVE_CATEGORIES):
            break
    missing = [category for category in _REQUIRED_ARCHIVE_CATEGORIES if category not in found]
    return not missing, missing


def mark_archived(*, dev_root: Path, evidence_archive: Path) -> InstanceManifest:
    resolved = _resolve(dev_root)
    manifest = read_manifest(resolved)
    if manifest is None or manifest.dev_root != str(resolved):
        raise InstanceLifecycleError(f"{resolved} has no matching field-acceptance manifest -- run 'init' first.")
    if manifest.lifecycle_state == LIFECYCLE_ACTIVE:
        raise InstanceLifecycleError(
            f"{resolved} has not been marked 'completed' yet -- stop the process and run 'complete' first."
        )
    archive_resolved = _resolve(evidence_archive)
    ok, missing = verify_archive_contract(archive_resolved)
    if not ok:
        raise InstanceLifecycleError(
            f"{archive_resolved} does not look like a complete evidence archive -- missing: {', '.join(missing)}. "
            "Refusing to mark this instance archived (see the governing report's own field-report archive "
            "contract) -- this never silently accepts an empty or placeholder directory."
        )
    manifest = replace(
        manifest, lifecycle_state=LIFECYCLE_ARCHIVED,
        evidence_archive_path=str(archive_resolved), archived_at=_now_iso(),
    )
    write_manifest(resolved, manifest)
    return manifest


# ---------------------------------------------------------------------------
# cleanup: dry-run by default; explicit --destroy required for removal.
# Cache scope (governing brief §15/§28): `RUNTIME_CACHE_DIRNAME`/
# `MODEL_CACHE_DIRNAME`/`BIOCLIP_MODEL_CACHE_DIRNAME` are always nested
# *inside* `dev_root` (`deploy_windows_dev.deploy`, confirmed by direct
# reading) and, per real field-session evidence (Representative Daylight
# Gate A Field Acceptance v8's own report: "confirmed NOT shared across
# separate --dev-root instances, only across multiple releases *within*
# one instance"), never shared with any *other* dev-root or the real
# production install. Removing this whole dev-root therefore removes only
# per-instance data -- there is no separate shared cache to preserve or
# delegate here. `deploy_windows_dev.py --cleanup`/`--keep`/`--gc-cache`
# remain the correct, unduplicated path for trimming an *active/persistent*
# dev-root's own internal release history without deleting the whole
# root; this command is orthogonal to, and does not reimplement, that.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CleanupPlan:
    dev_root: str
    blocked: bool
    reason: str
    will_remove: tuple[str, ...]
    total_bytes: int | None
    destroyed: bool = False

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def plan_cleanup(*, dev_root: Path, windows_host: Any) -> CleanupPlan:
    resolved = _resolve(dev_root)
    assessment = assess_instance(dev_root=resolved, windows_host=windows_host, check_observation=False)
    if assessment.verdict != SAFE_TO_RECLAIM:
        return CleanupPlan(
            dev_root=str(resolved), blocked=True, reason=assessment.reason,
            will_remove=(), total_bytes=assessment.size_on_disk_bytes,
        )
    try:
        entries = tuple(sorted(entry.name for entry in resolved.iterdir()))
    except OSError as error:
        return CleanupPlan(
            dev_root=str(resolved), blocked=True, reason=f"Could not list {resolved}: {error}",
            will_remove=(), total_bytes=None,
        )
    return CleanupPlan(
        dev_root=str(resolved), blocked=False,
        reason="Verified safe to reclaim -- pass --destroy to actually remove this.",
        will_remove=entries, total_bytes=assessment.size_on_disk_bytes,
    )


def execute_cleanup(*, dev_root: Path, windows_host: Any, destroy: bool) -> CleanupPlan:
    dwd = _dwd()
    resolved = _resolve(dev_root)
    plan = plan_cleanup(dev_root=resolved, windows_host=windows_host)
    if not destroy or plan.blocked:
        return plan

    # Full, redundant re-verification immediately before the only
    # destructive filesystem call in this whole tool -- never trust the
    # plan computed a moment ago alone (mirrors `verified_owning_release`'s
    # own "always re-probe fresh before acting" philosophy elsewhere in
    # this exact codebase).
    refuse_unsafe_root(resolved, windows_host=windows_host, dwd=dwd)
    if not _looks_like_deploy_tool_root(resolved, dwd):
        raise InstanceLifecycleError(f"{resolved} no longer looks like a deploy-tool root -- refusing to remove it.")
    manifest = read_manifest(resolved)
    if manifest is None or manifest.dev_root != str(resolved) or manifest.purpose != PURPOSE_FIELD_ACCEPTANCE:
        raise InstanceLifecycleError(f"{resolved}'s manifest identity no longer matches -- refusing to remove it.")
    if manifest.lifecycle_state != LIFECYCLE_ARCHIVED:
        raise InstanceLifecycleError(f"{resolved} is no longer archived -- refusing to remove it.")
    process_running, _owning_release, _port = _probe_running(dev_root=resolved, windows_host=windows_host, dwd=dwd)
    if process_running:
        raise InstanceLifecycleError(f"{resolved}'s process is running again -- refusing to remove it.")
    escaping = _find_escaping_links(resolved)
    if escaping:
        raise InstanceLifecycleError(
            f"{resolved} contains a top-level symlink/junction pointing outside itself "
            f"({[str(p) for p in escaping]}) -- refusing to remove it; investigate manually."
        )

    windows_host.remove_tree(resolved)
    return CleanupPlan(
        dev_root=plan.dev_root, blocked=False, reason="Removed.",
        will_remove=plan.will_remove, total_bytes=plan.total_bytes, destroyed=True,
    )


# ---------------------------------------------------------------------------
# preflight: storage headroom before an expensive deploy/session (§16/§17),
# including known reclaimable disposable instances found alongside this
# one dev-root's own parent directory (ordinarily %LOCALAPPDATA%).
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class StoragePreflightReport:
    """Field Acceptance Evidence Integrity & Storage Preflight
    Correctness v1: `requested_root`/`resolved_root`/`probed_root`/
    `resolution_method`/`platform`/`filesystem_device_id` are the
    provenance Representative Daylight Gate A Field Acceptance v12's own
    report disclosed as missing -- without them, a reviewer had no way to
    tell "requested Windows instance root -> measured Windows storage"
    apart from the dangerous "requested Windows root -> measured WSL
    virtual disk" this tool actually did. See `storage_preflight_report`
    and `deploy_windows_dev.resolve_storage_probe_target` (the shared
    resolver both this and `deploy_windows_dev.py`'s own pre-build
    `check_storage_headroom` call -- never two independent copies)."""

    requested_root: str
    resolved_root: str
    probed_root: str
    resolution_method: str  # "direct" | "translated_from_windows_drive_path"
    platform: str  # "windows" | "posix"
    filesystem_device_id: int | None
    free_bytes: int
    total_bytes: int
    storage_health_tier: str
    recorder_max_bytes: int
    reserve_bytes: int
    required_bytes: int
    known_reclaimable_bytes: int
    known_reclaimable_instances: tuple[str, ...]
    sufficient: bool
    reason: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def storage_health_tier(*, free_bytes: int, total_bytes: int) -> str:
    if total_bytes <= 0:
        return "healthy"
    free_ratio = free_bytes / total_bytes
    if free_bytes < CRITICAL_DISK_FREE_BYTES_THRESHOLD or free_ratio < CRITICAL_DISK_FREE_RATIO_THRESHOLD:
        return "critical"
    if free_bytes < LOW_DISK_FREE_BYTES_THRESHOLD or free_ratio < LOW_DISK_FREE_RATIO_THRESHOLD:
        return "action_recommended"
    if free_bytes < GETTING_LOW_DISK_FREE_BYTES_THRESHOLD or free_ratio < GETTING_LOW_DISK_FREE_RATIO_THRESHOLD:
        return "getting_low"
    return "healthy"


def scan_sibling_instances(parent: Path, *, windows_host: Any) -> list[AssessmentResult]:
    """Every direct child of `parent` that is itself a marked, identity
    -confirmed disposable field-acceptance instance -- read-only, bounded
    to one directory level (never a general recursive filesystem scan)."""

    results: list[AssessmentResult] = []
    try:
        children = [entry for entry in parent.iterdir() if entry.is_dir()]
    except OSError:
        return results
    for child in children:
        if read_manifest(child) is None:
            continue
        results.append(assess_instance(dev_root=child, windows_host=windows_host, check_observation=False))
    return results


def storage_preflight_report(
    *,
    dev_root: Path,
    windows_host: Any,
    recorder_max_bytes: int = ACCEPTANCE_RECORDER_HARD_CEILING_BYTES,
    reserve_bytes: int = DEFAULT_RESERVE_BYTES,
    scan_siblings: bool = True,
    disk_usage_fn: Callable[[str], Any] | None = None,
    is_native_windows: bool | None = None,
    wsl_translate_fn: Callable[[str], "str | None"] | None = None,
) -> StoragePreflightReport:
    """Field Acceptance Evidence Integrity & Storage Preflight
    Correctness v1: target resolution itself (`requested` -> `resolved`
    -> `probed`) is delegated entirely to `deploy_windows_dev.
    resolve_storage_probe_target` -- loaded via this module's own
    established `_dwd()` `runpy.run_path` convention, exactly like
    `read_current`/`probe_port`/every other `deploy_windows_dev.py`
    primitive this tool already reuses -- rather than a second,
    independently-drifting copy of that resolution logic. `is_native_
    windows`/`wsl_translate_fn` exist only as hermetic test seams
    (mirroring `disk_usage_fn` immediately below); real callers (the CLI)
    never pass them, so production always gets the real `os.name`/real
    `wslpath -u` behavior."""

    dwd = _dwd()
    if disk_usage_fn is None:
        disk_usage_fn = shutil.disk_usage
    if recorder_max_bytes > ACCEPTANCE_RECORDER_HARD_CEILING_BYTES:
        raise InstanceLifecycleError(
            f"--recorder-max-bytes {recorder_max_bytes} exceeds the acceptance recorder's own hard ceiling "
            f"({ACCEPTANCE_RECORDER_HARD_CEILING_BYTES}, mirrors AcceptanceRecorderConfig)."
        )
    try:
        probe_target = dwd["resolve_storage_probe_target"](  # type: ignore[operator]
            dev_root, is_native_windows=is_native_windows, wsl_translate_fn=wsl_translate_fn,
        )
    except dwd["DeploymentError"] as error:  # type: ignore[misc]
        raise InstanceLifecycleError(str(error)) from error

    probed_path = Path(probe_target.probed)
    usage = disk_usage_fn(probe_target.probed)
    free_bytes, total_bytes = int(usage.free), int(usage.total)
    try:
        filesystem_device_id: int | None = probed_path.stat().st_dev
    except OSError:
        filesystem_device_id = None

    known: list[AssessmentResult] = []
    if scan_siblings:
        try:
            parent = _resolve(windows_host.local_appdata())
        except Exception:  # noqa: BLE001
            parent = Path(probe_target.resolved).parent
        known = [result for result in scan_sibling_instances(parent, windows_host=windows_host) if result.verdict == SAFE_TO_RECLAIM]
    known_bytes = sum(result.reclaimable_bytes or 0 for result in known)
    known_names = tuple(result.dev_root for result in known)

    required = recorder_max_bytes + reserve_bytes
    sufficient = free_bytes >= required
    if sufficient:
        reason = (
            f"{free_bytes / 1e9:.1f}GB free >= {required / 1e9:.1f}GB required -- OK to proceed "
            f"(measured {probe_target.probed!r})."
        )
    else:
        reason = (
            f"Insufficient storage for the requested acceptance budget: {free_bytes / 1e9:.1f}GB free, "
            f"{required / 1e9:.1f}GB estimated required ({recorder_max_bytes / 1e9:.1f}GB recorder budget + "
            f"{reserve_bytes / 1e9:.1f}GB reserve) measured at {probe_target.probed!r}, "
            f"{known_bytes / 1e9:.1f}GB safely reclaimable from "
            f"{len(known_names)} completed disposable instance(s): {', '.join(known_names) or '(none)'}."
        )
    return StoragePreflightReport(
        requested_root=probe_target.requested, resolved_root=probe_target.resolved,
        probed_root=probe_target.probed, resolution_method=probe_target.resolution_method,
        platform=probe_target.platform, filesystem_device_id=filesystem_device_id,
        free_bytes=free_bytes, total_bytes=total_bytes,
        storage_health_tier=storage_health_tier(free_bytes=free_bytes, total_bytes=total_bytes),
        recorder_max_bytes=recorder_max_bytes, reserve_bytes=reserve_bytes, required_bytes=required,
        known_reclaimable_bytes=known_bytes, known_reclaimable_instances=known_names,
        sufficient=sufficient, reason=reason,
    )


# ---------------------------------------------------------------------------
# status: read-only combination of manifest + live assessment.
# ---------------------------------------------------------------------------


def status_report(*, dev_root: Path, windows_host: Any) -> dict[str, Any]:
    assessment = assess_instance(dev_root=dev_root, windows_host=windows_host)
    return assessment.as_dict()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _print(payload: Any, *, as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, indent=2, sort_keys=True, default=str))
    elif isinstance(payload, dict):
        for key, value in payload.items():
            print(f"{key}: {value}")
    else:
        print(payload)


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    subparsers = parser.add_subparsers(dest="command", required=True)

    def _with_dev_root(name: str, **kwargs: Any) -> argparse.ArgumentParser:
        sub = subparsers.add_parser(name, **kwargs)
        sub.add_argument("--dev-root", type=Path, required=True)
        sub.add_argument("--json", action="store_true", dest="as_json")
        return sub

    init_parser = _with_dev_root("init", help="Mark a dev-root as a disposable field-acceptance instance.")
    init_parser.add_argument("--notes", default="")
    init_parser.add_argument("--force", action="store_true")

    _with_dev_root("status", help="Read-only manifest + live assessment.")
    _with_dev_root("assess", help="Read-only reclaimability dry-run.")
    _with_dev_root("complete", help="Mark active -> completed (verifies the process is actually stopped).")

    archive_parser = _with_dev_root("mark-archived", help="Mark completed -> archived.")
    archive_parser.add_argument("--evidence-archive", type=Path, required=True)

    cleanup_parser = _with_dev_root("cleanup", help="Dry-run by default; --destroy actually removes.")
    cleanup_parser.add_argument("--destroy", action="store_true")

    preflight_parser = _with_dev_root("preflight", help="Storage headroom check before an expensive session.")
    preflight_parser.add_argument("--recorder-max-bytes", type=int, default=ACCEPTANCE_RECORDER_HARD_CEILING_BYTES)
    preflight_parser.add_argument("--no-scan-siblings", action="store_false", dest="scan_siblings")

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_argument_parser().parse_args(argv)
    dwd = _dwd()
    windows_host = dwd["real_windows_host"]()  # type: ignore[operator]
    as_json = bool(getattr(args, "as_json", False))
    try:
        if args.command == "init":
            result = init_instance(dev_root=args.dev_root, windows_host=windows_host, notes=args.notes, force=args.force)
            _print(result.as_dict(), as_json=as_json)
        elif args.command == "status":
            _print(status_report(dev_root=args.dev_root, windows_host=windows_host), as_json=as_json)
        elif args.command == "assess":
            # A determinate dry-run answer is success regardless of the verdict
            # (NOT_RECLAIMABLE_* is a correct answer, not a tool failure) --
            # falls through to `return 0` below.
            result = assess_instance(dev_root=args.dev_root, windows_host=windows_host)
            _print(result.as_dict(), as_json=as_json)
        elif args.command == "complete":
            result = complete_instance(dev_root=args.dev_root, windows_host=windows_host)
            _print(result.as_dict(), as_json=as_json)
        elif args.command == "mark-archived":
            result = mark_archived(dev_root=args.dev_root, evidence_archive=args.evidence_archive)
            _print(result.as_dict(), as_json=as_json)
        elif args.command == "cleanup":
            # A plain dry-run (no --destroy) reporting "not reclaimable yet"
            # is a correct, informative answer -- exit 0, matching `assess`'s
            # own "a determinate answer is success" convention. Exit 1 only
            # when --destroy was actually requested and correctly refused --
            # that distinction matters to a script/automation wrapping this
            # call ("did the destroy actually happen").
            result = execute_cleanup(dev_root=args.dev_root, windows_host=windows_host, destroy=args.destroy)
            _print(result.as_dict(), as_json=as_json)
            if args.destroy and result.blocked:
                return 1
        elif args.command == "preflight":
            result = storage_preflight_report(
                dev_root=args.dev_root, windows_host=windows_host,
                recorder_max_bytes=args.recorder_max_bytes, scan_siblings=args.scan_siblings,
            )
            _print(result.as_dict(), as_json=as_json)
            if not result.sufficient:
                return 1
        else:
            print(f"unknown command {args.command!r}", file=sys.stderr)
            return 2
        return 0
    except InstanceLifecycleError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
