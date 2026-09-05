#!/usr/bin/env python3
"""Field Acceptance Evidence Integrity & Storage Preflight Correctness v1:
a durable, committed periodic raw-ledger snapshot + end-of-run
reconciliation tool for long (beyond the ledger's own 60-minute
retention window) field-acceptance Observation sessions -- replacing the
ad hoc, uncommitted `snapshot.py` every real Gate A cohort since v9 has
hand-written fresh, each session, from scratch.

## Why this exists

`GET .../observation/counterfactual`'s own bounded raw-detection/track
-generation/proposal-outcome ledger evicts by both count and age (see
docs/rejected-detection-attribution-contract.md) -- a field session run
past that window needs periodic snapshots merged together to recover
full-session coverage, a methodology this codebase's own field
-acceptance reports have used since Representative Daylight Gate A Field
Acceptance v9 and explicitly recommended standardizing since v10
("simply adopt the periodic-snapshot procedure as standing acceptance
methodology ... since it is non-invasive, already proven, and needs no
product code change" -- representative-daylight-gate-a-field-acceptance
-v10-report.md, "Fragmentation"). Every session before this milestone
wrote that loop from scratch as a throwaway script -- Representative
Daylight Gate A Field Acceptance v12's own throwaway `snapshot.py` is
exactly what reproduced this milestone's own governing defect: its
`observation_counterfactual(..., end_offset_ms=None)` call silently
422'd on every one of 12 periodic snapshots (see
`FieldAcceptanceInvalidParameterError` in `field_acceptance_client.py`,
now fixed), and v12's own end-of-run reconciliation ("52.95% / 39.40% /
53.85% completeness by record type") was itself computed by hand, once,
after the fact -- not by any reusable tool.

## What this is (and is not)

Two subcommands:

- `collect`: the periodic loop itself. Every `--interval-seconds`,
  fetches the raw ledger (`observation_counterfactual` -- REQUIRED; a
  failure here makes the checkpoint `failed`, never silently
  `complete`), plus two auxiliary, best-effort artifact classes
  (`observation_status` for monitoring/recovery counters,
  `scene_confusor_learning_status` for scene-confusor state) via
  `FieldAcceptanceClient`. Writes one self-contained JSON file per
  checkpoint under `--output-dir` plus a running manifest, and prints a
  loud, explicit stderr warning the moment any checkpoint's required
  raw-ledger fetch fails -- never silent, never deferred until the
  session is already over.
- `reconcile`: deterministic end-of-run completeness accounting -- unions
  every checkpoint's raw-ledger payload (plus an optional final/post-stop
  corrective fetch), deduplicates by each record type's own natural
  identity, and reports per-artifact completeness precisely: `COMPLETE`
  (100%, zero gaps), or `PARTIAL` with the exact missing count and
  offset-window named -- never inferred merely because the session ended
  cleanly (see docs/field-acceptance-evidence-integrity-storage-preflight
  -correctness-v1-report.md, "End-of-run reconciliation"). Optionally
  also writes one merged, deduplicated `CounterfactualWindowResponse`
  -shaped JSON -- `scripts/run_gate_a_measurement_accounting.py --input
  <merged>`, unmodified, is the intended next step, never a second,
  competing accounting implementation.

  Proposal-Outcome Ledger Retention & Field-Reconciliation Completeness
  v1: `proposal_outcomes`' own "natural identity" is `(proposal_id,
  decided_at)`, not `proposal_id` alone -- a retryable `blocked_
  continuation_pending` proposal legitimately accumulates several
  independent decision events over a session's own life (see `_proposal_
  outcome_identity`'s own docstring). The prior milestone's documented
  contract used `proposal_id` alone for this artifact too (correct for
  `track_generations`, wrong here), which is precisely what made
  Representative Daylight Gate A Field Acceptance v13's own fully-intact,
  zero-data-loss session reconcile to a misleading 44.6% "PARTIAL" --
  independently reconstructed from that session's own archived
  checkpoints, all 350 of its real decision events (156 distinct
  proposals) are recoverable with zero gaps. Fixed here; see
  docs/proposal-outcome-ledger-retention-field-reconciliation
  -completeness-v1-report.md for the complete accounting. `reconcile`
  additionally reports each artifact's own `recovered_distinct_entity_
  count` (for `proposal_outcomes`: distinct `proposal_id`s among the
  recovered decision events) -- informational only, never part of the
  completeness ratio itself, which always compares events to events.

Not a full field-session launcher (no tmux orchestration, no Observation
start/stop, no acceptance-recorder wiring) -- matches
`field_acceptance_client.py`'s own explicitly bounded scope, which this
module builds on rather than duplicates. Not a generic monitoring
framework -- exactly the artifact classes the governing milestone brief
names (raw ledger, monitoring/recovery counters, scene-confusor state;
RTT/calibration state travels *inside* the raw-ledger payload itself, so
it is not a separate fetch), no plugin system, no configurable schema.

## Usage

    # During a live field session (run in the background, e.g. via the
    # packaged release's own embedded python.exe -- see docs/sandbox
    # -has-windows-gpu-interop for the WSL<->Windows invocation pattern):
    python scripts/field_acceptance_ledger_snapshot.py collect \\
        --stream-id <id> --output-dir data/field-acceptance/<slug>/raw-periodic-snapshots \\
        --interval-seconds 600

    # After the session stops (one corrective fetch against the still
    -live engine, exactly like every real Gate A cohort since v9 has
    # done by hand -- via field_acceptance_client.py directly, saved
    # alongside the periodic checkpoints as the "final snapshot"):
    python scripts/field_acceptance_client.py ... # (or a short ad hoc call)

    # Then, deterministic reconciliation:
    python scripts/field_acceptance_ledger_snapshot.py reconcile \\
        --snapshot-dir data/field-acceptance/<slug>/raw-periodic-snapshots \\
        --final-snapshot data/field-acceptance/<slug>/counterfactual-final.json \\
        --merged-output data/field-acceptance/<slug>/counterfactual-merged.json

Exit code for `collect` is 0 unless at least one checkpoint's required
raw-ledger fetch failed (1). Exit code for `reconcile` is 0 only when
every ledger artifact reconciles `COMPLETE` (1 for `PARTIAL`/`UNKNOWN`) --
safe to use directly in a field-acceptance shell sequence.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import runpy
import sys
import time
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]

_fac_module: dict[str, object] | None = None


def _fac() -> dict[str, object]:
    global _fac_module
    if _fac_module is None:
        _fac_module = runpy.run_path(str(ROOT / "scripts" / "field_acceptance_client.py"))
    return _fac_module


# ---------------------------------------------------------------------------
# Checkpoint contract (governing brief §6).
# ---------------------------------------------------------------------------

CHECKPOINT_COMPLETE = "complete"
CHECKPOINT_PARTIAL = "partial"
CHECKPOINT_FAILED = "failed"

# The raw ledger is the one artifact class whose failure makes a
# checkpoint FAILED outright (governing brief: "A checkpoint with a
# failed required raw-ledger fetch is FAILED/PARTIAL, never silently
# successful"). `monitoring_status`/`scene_confusor_state` are best
# -effort: a failure there degrades an otherwise-successful checkpoint to
# PARTIAL, never FAILED on its own.
REQUIRED_ARTIFACT = "raw_ledger"
AUXILIARY_ARTIFACTS = ("monitoring_status", "scene_confusor_state")
LEDGER_RECORD_KEYS = ("raw_detections", "track_generations", "proposal_outcomes")

# Proposal-Outcome Ledger Retention & Field-Reconciliation Completeness
# v1: the production ledger's own bounded age-retention window
# (`CounterfactualRetentionConfig.max_age_ms`, currently 60 minutes --
# `src/mockingbird/observation/counterfactual_lineage.py`) is not exposed
# by any API today, so this constant documents that known, out-of-band
# fact purely to let `collect` warn a caller whose own `--interval-
# seconds` leaves too little safety margin against it -- never to
# silently trust an arbitrarily long interval. Keep this in sync by hand
# if that production default ever changes; this tool has no way to read
# it live. `_RECOMMENDED_INTERVAL_SAFETY_FACTOR` is deliberately
# conservative, not tight: real-session churn (Representative Daylight
# Gate A Field Acceptance v13's own 350 decision-events/101.8 minutes)
# shows a 5-minute interval already leaves roughly 12x margin against the
# 60-minute retention window -- recommending at least 4x margin (an
# interval no larger than 1/4 of the known retention window) leaves
# headroom for a slow/degraded checkpoint or two without ever needing to
# rely on that full 12x.
_KNOWN_LEDGER_MAX_AGE_SECONDS = 60 * 60
_RECOMMENDED_INTERVAL_SAFETY_FACTOR = 4


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _write_json(path: Path, payload: Any) -> None:
    """The one place this module writes a JSON file -- every checkpoint,
    the manifest, and an optional merged-ledger output all go through
    this, matching the established per-script `_write_json`-style
    convention already used elsewhere in `scripts/` (e.g. `scripts/
    materialize_wildlife_stage2.py`, `scripts/build_wildlife_local_
    correction_queue.py`) rather than three independent inline `json.
    dumps(...).write_text(...)` call sites that could silently drift."""

    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")


@dataclass(frozen=True)
class ArtifactFetchResult:
    """One artifact class's own fetch outcome for one checkpoint --
    governing brief §6: 'explicit success/failure per artifact' plus
    'source/API error where applicable'."""

    name: str
    requested: bool
    success: bool
    record_count: int | None
    error: str | None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SnapshotCheckpoint:
    """One periodic snapshot's complete, self-describing accounting --
    governing brief §6: 'checkpoint timestamp, requested interval/bounds,
    record counts by artifact, explicit success/failure per artifact,
    source/API error where applicable, output file identity/path, enough
    metadata for end-of-run reconciliation.'"""

    index: int
    taken_at: str
    stream_id: str
    requested_start_offset_ms: int
    requested_end_offset_ms: int
    artifacts: dict[str, ArtifactFetchResult]
    status: str  # "complete" | "partial" | "failed"
    output_path: str | None

    def as_dict(self) -> dict[str, Any]:
        return {**asdict(self), "artifacts": {name: result.as_dict() for name, result in self.artifacts.items()}}


def _fetch_artifact(name: str, fetch_fn: Callable[[], Any]) -> tuple[ArtifactFetchResult, dict | None]:
    """Never raises for an ordinary field-acceptance-client-shaped
    failure (a 4xx/5xx, an unreachable host, an invalid-locally-caught
    parameter) -- the entire point of a periodic checkpoint is to survive
    and *report* such a failure, not crash the loop mid-session. A bug
    unrelated to the HTTP/API layer still propagates (never silently
    swallowed as "the fetch failed")."""

    fac = _fac()
    client_error = fac["FieldAcceptanceClientError"]
    invalid_parameter_error = fac["FieldAcceptanceInvalidParameterError"]
    try:
        payload = fetch_fn()
    except invalid_parameter_error:
        # A caller-side precondition bug (e.g. this module itself passing
        # None for a required bound -- exactly the mistake this whole
        # milestone exists to make impossible) is never a routine
        # operational failure like a dropped connection or a 500 -- let
        # it crash loudly, here, at the exact call site, rather than
        # silently becoming just another "FAILED" artifact
        # indistinguishable from a real transient network/API error deep
        # in a background loop. Re-raising (not `except ... as error:
        # return ArtifactFetchResult(..., success=False, ...)`) is
        # deliberate: this is the one exception class `_fetch_artifact`
        # must never treat as "the fetch failed."
        raise
    except client_error as error:  # type: ignore[misc]
        return (
            ArtifactFetchResult(name=name, requested=True, success=False, record_count=None, error=str(error)),
            None,
        )
    count: int | None = None
    if isinstance(payload, list):
        count = len(payload)
    elif isinstance(payload, dict) and any(key in payload for key in LEDGER_RECORD_KEYS):
        count = sum(len(payload.get(key) or []) for key in LEDGER_RECORD_KEYS)
    return ArtifactFetchResult(name=name, requested=True, success=True, record_count=count, error=None), payload


def take_checkpoint(
    client: Any, *, stream_id: str, index: int, start_offset_ms: int, end_offset_ms: int, output_dir: Path,
) -> SnapshotCheckpoint:
    """One periodic checkpoint: the required raw ledger plus two
    best-effort auxiliary reads, written to one self-contained JSON file
    immediately (so a crash on the very next checkpoint never loses this
    one). `end_offset_ms` is always an explicit, real int here -- never
    `None` -- see `FieldAcceptanceInvalidParameterError`; this function
    has no "omit the bound" mode at all, matching `observation_
    counterfactual`'s own contract."""

    artifacts: dict[str, ArtifactFetchResult] = {}
    payloads: dict[str, Any] = {}

    artifacts[REQUIRED_ARTIFACT], payloads[REQUIRED_ARTIFACT] = _fetch_artifact(
        REQUIRED_ARTIFACT,
        lambda: client.observation_counterfactual(
            stream_id, start_offset_ms=start_offset_ms, end_offset_ms=end_offset_ms,
        ),
    )
    artifacts["monitoring_status"], payloads["monitoring_status"] = _fetch_artifact(
        "monitoring_status", lambda: client.observation_status(stream_id),
    )
    artifacts["scene_confusor_state"], payloads["scene_confusor_state"] = _fetch_artifact(
        "scene_confusor_state", lambda: client.scene_confusor_learning_status(stream_id),
    )

    if not artifacts[REQUIRED_ARTIFACT].success:
        status = CHECKPOINT_FAILED
    elif not all(artifacts[name].success for name in AUXILIARY_ARTIFACTS):
        status = CHECKPOINT_PARTIAL
    else:
        status = CHECKPOINT_COMPLETE

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"checkpoint-{index:04d}.json"
    checkpoint = SnapshotCheckpoint(
        index=index, taken_at=_now_iso(), stream_id=stream_id,
        requested_start_offset_ms=start_offset_ms, requested_end_offset_ms=end_offset_ms,
        artifacts=artifacts, status=status, output_path=str(output_path),
    )
    _write_json(output_path, {"checkpoint": checkpoint.as_dict(), "payloads": payloads})
    return checkpoint


def _report_checkpoint(checkpoint: SnapshotCheckpoint, *, out: Any = None) -> None:
    if out is None:  # late-bound -- see run_periodic_collection's own docstring for why
        out = sys.stdout
    per_artifact = ", ".join(
        f"{name}={'OK' + (f'({result.record_count})' if result.record_count is not None else '') if result.success else 'FAILED'}"
        for name, result in checkpoint.artifacts.items()
    )
    print(f"checkpoint {checkpoint.index}: status={checkpoint.status.upper()} -- {per_artifact}", file=out)


def _write_manifest(output_dir: Path, checkpoints: list[SnapshotCheckpoint]) -> None:
    _write_json(output_dir / "checkpoints-manifest.json", [checkpoint.as_dict() for checkpoint in checkpoints])


def run_periodic_collection(
    client: Any,
    *,
    stream_id: str,
    output_dir: Path,
    interval_seconds: int,
    end_offset_ms: int,
    max_checkpoints: int | None = None,
    sleep_fn: Callable[[float], None] | None = None,
    stdout: Any = None,
    stderr: Any = None,
) -> list[SnapshotCheckpoint]:
    """The periodic loop (governing brief §8: 'surface evidence-integrity
    failure while the run is still recoverable' -- never silently, never
    only at the end). Does not stop a healthy Observation for one
    transient failure (this tool has no authority to stop one anyway --
    it never calls `stop_observation`); it only ever makes failure loud
    and immediately visible. `Ctrl+C` (or, in a test, `sleep_fn` raising
    `KeyboardInterrupt`) ends the loop gracefully -- the manifest is
    already up to date after every single checkpoint, never only at a
    clean exit. `max_checkpoints=0` takes none at all (not "one, then
    stop" -- checked before the loop body ever runs, not just at its end).

    `sleep_fn`/`stdout`/`stderr` default to `None`, resolved to the real
    `time.sleep`/`sys.stdout`/`sys.stderr` fresh on every call (never
    captured once into `__defaults__` at function-definition/module-load
    time) -- the same "late-bound default" discipline `deploy_windows_
    dev.check_storage_headroom`'s own `disk_usage_fn` already established
    elsewhere in this codebase, and for the identical reason: an
    early-bound default here would silently ignore a test's own
    `capsys`/`monkeypatch` replacement, since that swap happens long
    after this module's `def` line already ran."""

    if sleep_fn is None:
        sleep_fn = time.sleep
    if stdout is None:
        stdout = sys.stdout
    if stderr is None:
        stderr = sys.stderr
    checkpoints: list[SnapshotCheckpoint] = []
    if max_checkpoints is not None and max_checkpoints <= 0:
        return checkpoints
    consecutive_failures = 0
    index = 0
    try:
        while True:
            checkpoint = take_checkpoint(
                client, stream_id=stream_id, index=index, start_offset_ms=0,
                end_offset_ms=end_offset_ms, output_dir=output_dir,
            )
            checkpoints.append(checkpoint)
            _write_manifest(output_dir, checkpoints)
            _report_checkpoint(checkpoint, out=stdout)
            if checkpoint.status == CHECKPOINT_FAILED:
                consecutive_failures += 1
                print(
                    f"EVIDENCE INTEGRITY WARNING: checkpoint {index} FAILED to retrieve the required raw "
                    f"ledger ({checkpoint.artifacts[REQUIRED_ARTIFACT].error}). {consecutive_failures} "
                    "consecutive failure(s) so far this session -- raw-ledger evidence preservation is "
                    "degraded unless a later checkpoint or a final corrective fetch recovers this window. "
                    "This does not stop the Observation.",
                    file=stderr,
                )
            else:
                consecutive_failures = 0
            index += 1
            if max_checkpoints is not None and index >= max_checkpoints:
                break
            sleep_fn(interval_seconds)
    except KeyboardInterrupt:
        print(f"\nStopped after {len(checkpoints)} checkpoint(s) (Ctrl+C) -- manifest is up to date.", file=stderr)
    return checkpoints


# ---------------------------------------------------------------------------
# End-of-run reconciliation (governing brief §9).
# ---------------------------------------------------------------------------


def _raw_detection_identity(record: dict) -> tuple:
    """`CounterfactualRawDetectionResponse` carries no id field of its
    own -- its natural identity is the full fact tuple a genuine
    duplicate fetch would repeat exactly and a genuinely distinct
    detection never would."""

    bounding_box = record.get("bounding_box")
    return (
        record.get("source_offset_ms"), record.get("frame_id"), record.get("detector_id"),
        record.get("provider_id"), record.get("broad_class"),
        tuple(bounding_box) if bounding_box is not None else None,
    )


def _id_identity(field_name: str) -> Callable[[dict], Any]:
    return lambda record: record.get(field_name)


def _proposal_outcome_identity(record: dict) -> tuple:
    """Proposal-Outcome Ledger Retention & Field-Reconciliation
    Completeness v1: `proposal_outcomes` is an append-only decision
    -EVENT log, not a per-proposal state table -- `blocked_continuation_
    pending` is retryable (`candidate_visit_authority.RETRYABLE_
    OUTCOMES`), so a live session re-attempts the identical `proposal_id`
    on every ~10-second assembly tick it stays pending (`engine_runtime.
    _run_assembly_tick`), and each attempt is its own distinct,
    independently-recorded `record_proposal_outcome` call (see that
    method's own docstring: "recorded regardless of outcome... This is
    the exact proposal/geometry/confidence detail a retried blocked_
    continuation_pending re-evaluation on a later tick previously
    discarded completely on every attempt but the last"). `proposal_id`
    alone is therefore the wrong identity for this one artifact type
    specifically -- unlike `track_generations` (recorded exactly once per
    generation, at its own `ended` transition: `generation_id` alone
    really is that record's own natural, never-repeated identity) and
    unlike `raw_detections` (one independent fact per analyzed frame).

    This exact mismatch -- comparing a `proposal_id`-deduplicated
    recovered count against the ledger's own raw per-event `recorded_
    count` -- is precisely what made Representative Daylight Gate A Field
    Acceptance v13's own session reconcile to a misleading 44.6%
    "PARTIAL": independently reconstructed from that session's own
    archived periodic checkpoints, every one of its real 350 decision
    events (156 distinct proposals, 64 of them re-decided 2-5 times each)
    is recoverable with zero gaps -- a fully intact, zero-loss session
    that the old `proposal_id`-only identity nonetheless collapsed to
    156/350. `decided_at` (a fresh ISO-8601 instant stamped once per
    `record_proposal_outcome` call -- see `engine_runtime._run_assembly_
    tick._attempt`) is the natural per-event discriminator alongside
    `proposal_id`, mirroring `_raw_detection_identity`'s own "the
    record's own natural fact tuple" convention rather than inventing a
    synthetic counter. See docs/proposal-outcome-ledger-retention-field
    -reconciliation-completeness-v1-report.md."""
    return (record.get("proposal_id"), record.get("decided_at"))


_IDENTITY_FN: dict[str, Callable[[dict], Any]] = {
    "raw_detections": _raw_detection_identity,
    "track_generations": _id_identity("generation_id"),
    "proposal_outcomes": _proposal_outcome_identity,
}

# For an artifact type whose own recovered-record identity is a decision
# EVENT rather than a stable per-entity fact (currently only
# `proposal_outcomes` -- see `_proposal_outcome_identity`'s own
# docstring), the count of distinct underlying entities (here: distinct
# `proposal_id`s) is a separate, purely informational fact worth
# reporting -- never conflated into `completeness_fraction`, which must
# always compare events to events (the same unit `coverage.<type>.
# recorded_count` itself counts). `None` for an artifact type where
# identity already *is* the entity -- no separate count would be
# meaningful.
_ENTITY_FIELD: dict[str, str | None] = {
    "raw_detections": None,
    "track_generations": None,
    "proposal_outcomes": "proposal_id",
}

# (start_field, end_field) -- for raw_detections both are the same field
# (a point in time, not a span).
_OFFSET_FIELDS: dict[str, tuple[str, str]] = {
    "raw_detections": ("source_offset_ms", "source_offset_ms"),
    "track_generations": ("start_offset_ms", "end_offset_ms"),
    "proposal_outcomes": ("start_offset_ms", "end_offset_ms"),
}


@dataclass(frozen=True)
class ArtifactReconciliation:
    artifact: str
    recovered_unique_count: int
    final_recorded_count: int | None
    completeness_fraction: float | None
    earliest_recovered_offset_ms: int | None
    latest_recovered_offset_ms: int | None
    gaps_ms: list[tuple[int, int]]
    status: str  # "COMPLETE" | "PARTIAL" | "UNKNOWN"
    reason: str
    # Proposal-Outcome Ledger Retention & Field-Reconciliation
    # Completeness v1 (additive): distinct underlying entities among the
    # records this reconciliation actually recovered -- see `_ENTITY_
    # FIELD`. `None` for an artifact type whose own identity already is
    # the entity (`raw_detections`/`track_generations`); a real, honestly
    # possibly-smaller-than-`recovered_unique_count` integer for
    # `proposal_outcomes` (distinct `proposal_id`s among the recovered
    # decision events) -- informational only, never part of `completeness_
    # fraction`.
    recovered_distinct_entity_count: int | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ReconciliationReport:
    stream_id: str | None
    payloads_considered: int
    included_final_snapshot: bool
    artifacts: dict[str, ArtifactReconciliation]
    overall_status: str  # "COMPLETE" | "PARTIAL"

    def as_dict(self) -> dict[str, Any]:
        return {**asdict(self), "artifacts": {name: result.as_dict() for name, result in self.artifacts.items()}}


def _merge_intervals(intervals: list[tuple[int, int]]) -> list[tuple[int, int]]:
    # A malformed interval (end before start -- a corrupted/hand-edited
    # checkpoint file, never produced by a real server response) is
    # dropped rather than merged/sorted incorrectly; real callers here
    # only ever pass intervals already filtered the same way by
    # `_accumulate_artifact`, but this utility stays correct on its own.
    valid = [(start, end) for start, end in intervals if end >= start]
    if not valid:
        return []
    ordered = sorted(valid)
    merged = [ordered[0]]
    for start, end in ordered[1:]:
        last_start, last_end = merged[-1]
        if start <= last_end:
            merged[-1] = (last_start, max(last_end, end))
        else:
            merged.append((start, end))
    return merged


def _gaps_in(intervals: list[tuple[int, int]], *, window_start: int, window_end: int) -> list[tuple[int, int]]:
    """Every sub-window of `[window_start, window_end]` not covered by
    any of `intervals` -- the precise 'exact missing interval' governing
    brief §9 requires, not a vague 'some data may be missing.'"""

    gaps: list[tuple[int, int]] = []
    cursor = window_start
    for start, end in _merge_intervals(intervals):
        if start > cursor:
            gaps.append((cursor, start))
        cursor = max(cursor, end)
    if cursor < window_end:
        gaps.append((cursor, window_end))
    return gaps


@dataclass(frozen=True)
class _ArtifactAccumulation:
    """One artifact type's own facts accumulated across every payload --
    computed once by `_accumulate_artifact` and shared by `reconcile_
    ledger` and `build_merged_counterfactual_window` so the two can never
    silently diverge on which record wins for a given identity, or on
    what the session's true `recorded_count` is (a real gap the first
    version of this module had: the merged-output builder independently
    re-derived its own dedup pass and simply asserted `recorded_count ==
    however much we recovered`, silently claiming perfect retention even
    for a payload set `reconcile_ledger` itself reports as `PARTIAL`)."""

    unique_records: dict[Any, dict]
    retained_intervals: list[tuple[int, int]]
    final_recorded_count: int | None


def _accumulate_artifact(payloads: list[dict], artifact_type: str) -> _ArtifactAccumulation:
    """`payloads` may include `None`/falsy entries (a failed fetch) --
    skipped, never a `None`-attribute crash. `final_recorded_count` takes
    the largest `recorded_count` seen across every payload: the
    session's own true total only ever grows, so an earlier/stale
    checkpoint's smaller count is never more authoritative than a later
    one's.

    Proposal-Outcome Ledger Retention & Field-Reconciliation Completeness
    v1 -- proven-coverage gap refinement. A naturally sparse/bursty
    artifact (`proposal_outcomes` above all: no proposal is ever decided
    before the first candidate encounter, and none after the last one)
    always looked "gapped" before its own first and after its own last
    real record, even under perfect, continuous checkpointing throughout
    the *whole* session -- exactly what made Representative Daylight
    Gate A Field Acceptance v13's own real archive still reconcile to a
    misleading PARTIAL even after the `(proposal_id, decided_at)`
    identity fix alone (see the governing report's "First irreversible
    loss"). Two cases give a payload PROVEN interval coverage from
    session start up to its own fetch position (`coverage.session_last_
    offset_ms`, populated by every successful payload from the first
    analyzed frame onward -- see `CounterfactualLedger._observe_result_
    locked` -- regardless of whether *this* artifact specifically had any
    activity), independent of its own `oldest`/`newest_retained_offset_
    ms`:

    1. `recorded_count == 0`: definitively nothing existed for this
       artifact yet, as of this payload's own fetch -- always trustworthy
       on its own, regardless of how many other payloads exist.
    2. `recorded_count == final_recorded_count` (the session-wide max),
       but *only* when independently corroborated by at least one other,
       separately-fetched payload also reporting that same final value --
       otherwise a single, lone late/corrective fetch (the historical
       v12 shape this tool's own governing contract already protects
       against) could trivially "confirm" its own count as final with no
       independent evidence at all, silently masking a real, uncaptured
       tail the collector simply stopped watching for. Two or more
       independent payloads agreeing (matching v13's own real shape: its
       21st periodic checkpoint and its separate final corrective fetch
       both independently reported the identical final count) is
       genuine, repeated corroboration that the true session-wide total
       had already stabilized -- not merely the single artifact of
       whichever payload happens to be last.

    Every other payload (genuinely partial, mid-range `recorded_count`,
    or an uncorroborated lone final-count payload) is unaffected --
    contributes its own real `[oldest, newest]` retained window exactly
    as before this milestone.
    """

    identity_fn = _IDENTITY_FN[artifact_type]
    unique: dict[Any, dict] = {}
    final_recorded_count: int | None = None
    per_payload: list[tuple[dict, int | None, int | None]] = []
    for payload in payloads:
        if not payload:
            continue
        for record in payload.get(artifact_type) or []:
            unique[identity_fn(record)] = record
        type_coverage = (payload.get("coverage") or {}).get(artifact_type) or {}
        recorded_count = type_coverage.get("recorded_count")
        if isinstance(recorded_count, int):
            final_recorded_count = max(final_recorded_count or 0, recorded_count)
        session_position = (payload.get("coverage") or {}).get("session_last_offset_ms")
        per_payload.append((type_coverage, recorded_count, session_position if isinstance(session_position, int) else None))

    final_count_confirmations = sum(1 for _coverage, count, _pos in per_payload if count == final_recorded_count)
    trailing_rule_corroborated = final_recorded_count is not None and final_count_confirmations >= 2

    retained_intervals: list[tuple[int, int]] = []
    for type_coverage, recorded_count, session_position in per_payload:
        proven_from_session_start = session_position is not None and (
            recorded_count == 0 or (recorded_count == final_recorded_count and trailing_rule_corroborated)
        )
        if proven_from_session_start:
            retained_intervals.append((0, session_position))
            continue
        oldest = type_coverage.get("oldest_retained_offset_ms")
        newest = type_coverage.get("newest_retained_offset_ms")
        if isinstance(oldest, int) and isinstance(newest, int) and newest >= oldest:
            retained_intervals.append((oldest, newest))
    return _ArtifactAccumulation(unique, retained_intervals, final_recorded_count)


def reconcile_ledger(
    payloads: list[dict], *, stream_id: str | None = None, included_final_snapshot: bool = False,
) -> ReconciliationReport:
    """`payloads`: every successfully-fetched raw-ledger
    (`CounterfactualWindowResponse`-shaped) payload across the session, in
    any order -- typically every periodic checkpoint's own successful
    raw-ledger payload plus, if taken, one final/post-stop corrective
    fetch. Deterministic: the same input set always produces the same
    report, regardless of order (governing brief §10: 'duplicate/overlap
    snapshots reconcile deterministically') -- every union/merge step
    here is order-independent (set/dict union, sorted-interval merge)."""

    successful = [payload for payload in payloads if payload]

    session_last_offset_ms = 0
    for payload in successful:
        coverage = payload.get("coverage") or {}
        last = coverage.get("session_last_offset_ms")
        if isinstance(last, int):
            session_last_offset_ms = max(session_last_offset_ms, last)
        for artifact_type in LEDGER_RECORD_KEYS:
            newest = (coverage.get(artifact_type) or {}).get("newest_retained_offset_ms")
            if isinstance(newest, int):
                session_last_offset_ms = max(session_last_offset_ms, newest)

    artifacts: dict[str, ArtifactReconciliation] = {}
    overall_complete = True
    for artifact_type in LEDGER_RECORD_KEYS:
        accumulation = _accumulate_artifact(successful, artifact_type)
        recovered_unique_count = len(accumulation.unique_records)
        final_recorded_count = accumulation.final_recorded_count
        start_field, end_field = _OFFSET_FIELDS[artifact_type]
        offsets = [
            value
            for record in accumulation.unique_records.values()
            for value in (record.get(start_field), record.get(end_field))
            if isinstance(value, int)
        ]
        # Proposal-Outcome Ledger Retention & Field-Reconciliation
        # Completeness v1: purely informational, computed for every
        # branch below alongside `recovered_unique_count` -- see
        # `_ENTITY_FIELD`'s own docstring for why this must never enter
        # `completeness_fraction` itself.
        entity_field = _ENTITY_FIELD[artifact_type]
        recovered_distinct_entity_count = (
            len({record.get(entity_field) for record in accumulation.unique_records.values()})
            if entity_field is not None else None
        )
        entity_suffix = (
            f" ({recovered_distinct_entity_count} distinct {entity_field}s)"
            if entity_field is not None else ""
        )

        if final_recorded_count is None:
            status = "UNKNOWN"
            reason = "No coverage.recorded_count reported by any payload for this artifact."
            completeness_fraction = None
            gaps: list[tuple[int, int]] = []
            overall_complete = False
        elif final_recorded_count == 0:
            # A genuine, honest zero: nothing was ever recorded for this
            # artifact type all session (the real API reports oldest/
            # newest_retained_offset_ms=None whenever recorded_count==0
            # -- see CounterfactualLedgerAccountingResponse -- so there is
            # no "retained window" to gap-check at all). 0/0 is trivially,
            # completely reconciled -- never reported as a "missing"
            # full-session gap merely because nothing was ever retained.
            status = "COMPLETE"
            reason = "100% -- 0 records recorded for this artifact this session (a genuine zero, not a gap)."
            completeness_fraction = 1.0
            gaps = []
        else:
            gaps = _gaps_in(accumulation.retained_intervals, window_start=0, window_end=session_last_offset_ms)
            completeness_fraction = recovered_unique_count / final_recorded_count
            if recovered_unique_count >= final_recorded_count and not gaps:
                status = "COMPLETE"
                reason = (
                    f"100% -- {recovered_unique_count}/{final_recorded_count} unique records recovered"
                    f"{entity_suffix}, zero gaps."
                )
            else:
                missing = max(final_recorded_count - recovered_unique_count, 0)
                status = "PARTIAL"
                reason = (
                    f"PARTIAL -- {recovered_unique_count}/{final_recorded_count} unique records recovered"
                    f"{entity_suffix} ({missing} missing); uncovered offset window(s) (ms): "
                    f"{gaps or 'none identified'}."
                )
                overall_complete = False

        artifacts[artifact_type] = ArtifactReconciliation(
            artifact=artifact_type,
            recovered_unique_count=recovered_unique_count,
            final_recorded_count=final_recorded_count,
            completeness_fraction=completeness_fraction,
            earliest_recovered_offset_ms=min(offsets) if offsets else None,
            latest_recovered_offset_ms=max(offsets) if offsets else None,
            gaps_ms=gaps, status=status, reason=reason,
            recovered_distinct_entity_count=recovered_distinct_entity_count,
        )

    return ReconciliationReport(
        stream_id=stream_id, payloads_considered=len(payloads), included_final_snapshot=included_final_snapshot,
        artifacts=artifacts, overall_status="COMPLETE" if overall_complete else "PARTIAL",
    )


def build_merged_counterfactual_window(payloads: list[dict], *, stream_id: str) -> dict:
    """A single, deduplicated `CounterfactualWindowResponse`-shaped dict
    combining every given payload -- feed directly to
    `scripts/run_gate_a_measurement_accounting.py --input <this>`,
    unmodified: reuse, never a second, competing accounting
    implementation. `attribution`/`attribution_reason` are honest,
    fixed placeholders naming this file's own synthetic origin (that
    script never reads either field). Uses the exact same `_accumulate_
    artifact` dedup pass `reconcile_ledger` uses on the same payloads --
    its own `coverage.<artifact>.recorded_count` reports the true session
    total (never just "however much this merge happens to contain"), so
    a PARTIAL merge honestly shows itself as partial here too, agreeing
    with `reconcile_ledger`'s own verdict rather than silently asserting
    perfect retention."""

    accumulations = {artifact_type: _accumulate_artifact(payloads, artifact_type) for artifact_type in LEDGER_RECORD_KEYS}
    clock_calibrations: dict[Any, dict] = {}
    rtt_clock_calibrations: dict[Any, dict] = {}
    clock_calibration_required = False
    session_first: int | None = None
    session_last: int | None = None

    for payload in payloads:
        if not payload:
            continue
        for record in payload.get("clock_calibrations") or []:
            clock_calibrations[(record.get("source_offset_ms"), record.get("calibrated_at"))] = record
        for record in payload.get("rtt_clock_calibrations") or []:
            rtt_clock_calibrations[(record.get("source_offset_ms"), record.get("calibrated_at"))] = record
        clock_calibration_required = clock_calibration_required or bool(payload.get("clock_calibration_required"))
        coverage = payload.get("coverage") or {}
        first, last = coverage.get("session_first_offset_ms"), coverage.get("session_last_offset_ms")
        if isinstance(first, int):
            session_first = first if session_first is None else min(session_first, first)
        if isinstance(last, int):
            session_last = last if session_last is None else max(session_last, last)

    def _sort_key(artifact_type: str) -> Callable[[dict], tuple]:
        start_field, _end_field = _OFFSET_FIELDS[artifact_type]
        return lambda record: (record.get(start_field) if record.get(start_field) is not None else -1,)

    def _coverage_for(artifact_type: str) -> dict:
        accumulation = accumulations[artifact_type]
        retained_count = len(accumulation.unique_records)
        recorded_count = (
            accumulation.final_recorded_count if accumulation.final_recorded_count is not None else retained_count
        )
        return {
            "retained_count": retained_count,
            "evicted_count": max(recorded_count - retained_count, 0),
            "recorded_count": recorded_count,
        }

    return {
        "stream_id": stream_id,
        "start_offset_ms": 0,
        "end_offset_ms": session_last if session_last is not None else 0,
        "roi": None,
        "raw_detections": sorted(accumulations["raw_detections"].unique_records.values(), key=_sort_key("raw_detections")),
        "track_generations": sorted(
            accumulations["track_generations"].unique_records.values(), key=_sort_key("track_generations")
        ),
        "proposal_outcomes": sorted(
            accumulations["proposal_outcomes"].unique_records.values(), key=_sort_key("proposal_outcomes")
        ),
        "raw_detection_count_in_roi": 0,
        "track_generation_count_in_roi": 0,
        "coverage": {
            "session_first_offset_ms": session_first,
            "session_last_offset_ms": session_last,
            "raw_detections": _coverage_for("raw_detections"),
            "track_generations": _coverage_for("track_generations"),
            "proposal_outcomes": _coverage_for("proposal_outcomes"),
        },
        "attribution": "merged_periodic_snapshots",
        "attribution_reason": "field_acceptance_ledger_snapshot.py reconcile -- deduplicated union, not a live query",
        "clock_calibrations": sorted(clock_calibrations.values(), key=lambda r: r.get("source_offset_ms") or 0),
        "clock_calibration_required": clock_calibration_required,
        "rtt_clock_calibrations": sorted(rtt_clock_calibrations.values(), key=lambda r: r.get("source_offset_ms") or 0),
    }


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


def _load_checkpoint_ledger_payloads(snapshot_dir: Path) -> list[dict]:
    payloads: list[dict] = []
    for path in sorted(snapshot_dir.glob("checkpoint-*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        ledger_payload = (data.get("payloads") or {}).get(REQUIRED_ARTIFACT)
        if ledger_payload:
            payloads.append(ledger_payload)
    return payloads


def _cmd_collect(args: argparse.Namespace) -> int:
    fac = _fac()
    client = fac["FieldAcceptanceClient"](base_url=args.base_url)  # type: ignore[operator]
    max_safe_interval_seconds = _KNOWN_LEDGER_MAX_AGE_SECONDS // _RECOMMENDED_INTERVAL_SAFETY_FACTOR
    if args.interval_seconds > max_safe_interval_seconds:
        print(
            f"WARNING: --interval-seconds {args.interval_seconds} leaves less than "
            f"{_RECOMMENDED_INTERVAL_SAFETY_FACTOR}x safety margin against the production ledger's own "
            f"known ~{_KNOWN_LEDGER_MAX_AGE_SECONDS // 60}-minute proposal-outcome retention window "
            "(CounterfactualRetentionConfig.max_age_ms) under high proposal churn -- a real decision "
            "event could, in principle, be recorded and evicted between two consecutive checkpoints. "
            f"Consider --interval-seconds {max_safe_interval_seconds} or shorter for a long/high-churn "
            "session.",
            file=sys.stderr,
        )
    checkpoints = run_periodic_collection(
        client, stream_id=args.stream_id, output_dir=args.output_dir,
        interval_seconds=args.interval_seconds, end_offset_ms=args.end_offset_ms,
        max_checkpoints=args.max_checkpoints,
    )
    failed = sum(1 for checkpoint in checkpoints if checkpoint.status == CHECKPOINT_FAILED)
    print(f"\n{len(checkpoints)} checkpoint(s) written to {args.output_dir} ({failed} FAILED).")
    return 1 if failed else 0


def _cmd_reconcile(args: argparse.Namespace) -> int:
    payloads = _load_checkpoint_ledger_payloads(args.snapshot_dir)
    included_final = args.final_snapshot is not None
    if included_final:
        payloads.append(json.loads(args.final_snapshot.read_text(encoding="utf-8")))

    stream_id = next((payload.get("stream_id") for payload in payloads if payload.get("stream_id")), None)
    report = reconcile_ledger(payloads, stream_id=stream_id, included_final_snapshot=included_final)
    _print(report.as_dict(), as_json=args.as_json)

    if args.merged_output is not None:
        merged = build_merged_counterfactual_window(payloads, stream_id=stream_id or "unknown")
        args.merged_output.parent.mkdir(parents=True, exist_ok=True)
        args.merged_output.write_text(json.dumps(merged, indent=2, sort_keys=True, default=str), encoding="utf-8")
        print(f"Wrote merged ledger ({sum(len(merged[k]) for k in LEDGER_RECORD_KEYS)} unique records) to {args.merged_output}")

    return 0 if report.overall_status == "COMPLETE" else 1


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base-url", default=_fac()["DEFAULT_BASE_URL"])
    subparsers = parser.add_subparsers(dest="command", required=True)

    collect_parser = subparsers.add_parser("collect", help="Run the periodic raw-ledger snapshot loop.")
    collect_parser.add_argument("--stream-id", required=True)
    collect_parser.add_argument("--output-dir", type=Path, required=True)
    collect_parser.add_argument(
        "--interval-seconds", type=int, default=600,
        help="Seconds between periodic checkpoints (default: 600/10min). A value leaving less than "
        f"{_RECOMMENDED_INTERVAL_SAFETY_FACTOR}x safety margin against the production ledger's own known "
        f"~{_KNOWN_LEDGER_MAX_AGE_SECONDS // 60}-minute proposal-outcome retention window prints a "
        "non-fatal WARNING, never a hard failure -- this tool cannot verify the live server's own "
        "retention config.",
    )
    collect_parser.add_argument(
        "--end-offset-ms", type=int, default=86_400_000,
        help="Explicit, real end bound for every periodic fetch (default: 86400000ms/24h -- "
        "'everything retained so far'). Never None/omitted -- see FieldAcceptanceInvalidParameterError.",
    )
    collect_parser.add_argument(
        "--max-checkpoints", type=int, default=None,
        help="Stop after this many checkpoints instead of running until Ctrl+C (mainly for a bounded smoke "
        "proof; a real field session normally omits this and stops the loop with Ctrl+C at session end).",
    )

    reconcile_parser = subparsers.add_parser("reconcile", help="Deterministic end-of-run completeness accounting.")
    reconcile_parser.add_argument("--snapshot-dir", type=Path, required=True)
    reconcile_parser.add_argument(
        "--final-snapshot", type=Path, default=None,
        help="Optional saved GET .../observation/counterfactual response from one corrective fetch taken "
        "with the engine still live post-stop (the established convention since v9).",
    )
    reconcile_parser.add_argument(
        "--merged-output", type=Path, default=None,
        help="Optional path to also write a merged, deduplicated CounterfactualWindowResponse-shaped JSON "
        "-- feed directly to run_gate_a_measurement_accounting.py --input.",
    )
    reconcile_parser.add_argument("--json", action="store_true", dest="as_json")

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_argument_parser().parse_args(argv)
    fac = _fac()
    try:
        if args.command == "collect":
            return _cmd_collect(args)
        if args.command == "reconcile":
            return _cmd_reconcile(args)
        print(f"unknown command {args.command!r}", file=sys.stderr)
        return 2
    except fac["FieldAcceptanceClientError"] as error:  # type: ignore[misc]
        print(f"ERROR: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
