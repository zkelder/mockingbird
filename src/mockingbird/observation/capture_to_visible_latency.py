"""Gate A Measurement Closure v1: true capture-to-visible Visit latency (see
docs/gate-a-measurement-closure-fragmentation-latency-v1-report.md "T0-T5
timeline").

Every prior field cohort measured latency as activity-end (a proposal's own
`end_offset_ms`) to arbitration decision (`decided_at`) -- v6's own metric,
reused verbatim by v7 "matching v6's own established metric exactly" (see
"Latency" in representative-daylight-gate-a-field-acceptance-v7-report.md).
That is proposal-*resolution* latency, not capture-to-visible latency: it
starts counting from the *last* frame of the activity that already produced
a proposal, never from the real-world moment a bird was first captured, and
both endpoints stayed in the same Host-domain wall clock -- a materially
different, smaller, and easier number than what a user actually experiences
("how long from when this bird first appeared until I can see it").

Tracing the real production timeline (this milestone's own governing brief
§13) found:

- **T0 (source capture)** now exists as a genuine wall-clock fact at the
  track-generation level -- `TrackGenerationRecord.start_captured_at` (Gate
  A Measurement Closure v1; see `counterfactual_lineage.py`), itself read
  straight off `TrackUpdate.captured_at`, which was already a required
  field on every tracker update the whole time, simply never previously
  copied onto the ledger's own output record. This is Node-domain (the
  Camera Node's own OS clock) -- see docs/camera-node-live-shadow-
  contract.md "Clock-drift disposition": `node_to_host_clock_offset_ms` is
  already computed per frame but never surfaced downstream; alignment is
  "uncertain unless externally synchronized." Every sample this module
  produces carries an explicit `clock_domain_caveat` disclosing this,
  rather than presenting a cross-domain subtraction as an unqualified fact.
- **T1 (proposal creation)** does not exist as a wall clock anywhere in the
  live pipeline -- `AssembledVisitProposal` carries only source-relative
  offsets, by design (the assembler is a pure, wall-clock-free module).
- **T2 (arbitration decision) and T3 (candidate admission)** collapse into
  one Host-domain value, `ProposalOutcomeRecord.decided_at` -- a single
  `datetime.now(UTC)` read in `engine_runtime.py`'s own `_attempt()`
  closure, reused for both.
- **T4 (Visit persistence commit)** is stamped with the *same* T3 value,
  written *before* the repository transaction actually commits -- so it is
  not a true "commit completed" timestamp, only "decision was made"
  (disclosed, not silently treated as more precise than it is).
- **T5 (query-visible)** is structurally proven equivalent to T4 in this
  codebase's current, fully-synchronous read/write design -- no cache,
  materialized view, or async index sits between a committed Visit and the
  next `GET /api/visits` (see
  `tests/test_candidate_visit_repository.py::
  test_a_freshly_created_candidate_visit_is_immediately_query_visible_through_the_same_repository_read_path`
  and this milestone's own report "Visibility boundary" section).

So this module measures **T0 -> decided_at** as the best-available direct
proxy for T0 -> T5 in the current architecture, and states that
substitution explicitly rather than silently relabeling it -- a materially
different, and correctly *larger*, number than every prior cohort's own
activity-end-to-decision proxy, because it starts from the true first
capture instead of the activity's own last frame.

Pure: no filesystem, network, CUDA/ONNX Runtime/OpenCV, product-repository,
or SQLAlchemy import, matching every sibling Stage 6.x/7 decision module in
this package.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import math
from typing import Literal, Mapping, Sequence

from mockingbird.observation.counterfactual_lineage import ProposalOutcomeRecord, TrackGenerationRecord

CAPTURE_TO_VISIBLE_LATENCY_VERSION = "capture-to-visible-latency-v1"

_FALLBACK_REASON_MARKER = ":fallback_position_"

# A clock-domain safety backstop only (this milestone's own §18), never a
# real session-length bound: the counterfactual ledger's own *retention* is
# capped at 60 minutes, but a genuine session -- and therefore a genuine
# T0 -> decided_at gap for an early-session encounter re-evaluated late --
# can honestly exceed that. This exists to catch a wall/monotonic-mix- or
# wrong-epoch-shaped bug (hours where seconds were meant), not to reject an
# unusually slow but real admission.
DEFAULT_MAX_PLAUSIBLE_LATENCY_MS = 6 * 60 * 60 * 1000  # 6 hours

LatencyState = Literal["measured", "unavailable_capture_time", "invalid_negative", "implausible"]

_CLOCK_DOMAIN_CAVEAT = (
    "t0_captured_at is Node-domain (the Camera Node's own OS clock); "
    "decided_at is Host-domain (this Host's own OS clock). Cross-domain "
    "subtraction is not proven safe absent external clock synchronization "
    "-- see docs/camera-node-live-shadow-contract.md 'Clock-drift "
    "disposition' (node_to_host_clock_offset_ms is computed per frame but "
    "not yet wired into this figure)."
)


@dataclass(frozen=True)
class LatencySample:
    """One admitted candidate's own T0 -> decided_at measurement (see this
    module's own docstring for why `decided_at` is the best-available T5
    proxy today, and `t0_source` for exactly how `t0_captured_at` was
    resolved). `is_fallback`/`fallback_position` are read from the
    engine's own already-established `reason` suffix convention
    (`engine_runtime.py._attempt_resolved_component`) -- never
    recomputed/guessed."""

    proposal_id: str
    visit_id: str
    is_fallback: bool
    fallback_position: int | None
    t0_captured_at: datetime | None
    t0_source: Literal["earliest_constituent_generation_start_captured_at", "unavailable"]
    decided_at: datetime
    state: LatencyState
    latency_ms: float | None
    clock_domain_caveat: str = _CLOCK_DOMAIN_CAVEAT


def _fallback_position(reason: str) -> tuple[bool, int | None]:
    if _FALLBACK_REASON_MARKER not in reason:
        return False, None
    suffix = reason.rsplit(_FALLBACK_REASON_MARKER, 1)[1]
    try:
        return True, int(suffix)
    except ValueError:
        # A malformed suffix is still honestly "this was a fallback
        # attempt" -- never silently reclassified as an ordinary one --
        # just without a parsed position.
        return True, None


def _resolve_t0(
    outcome: ProposalOutcomeRecord, generations_by_id: Mapping[str, TrackGenerationRecord],
) -> tuple[datetime | None, Literal["earliest_constituent_generation_start_captured_at", "unavailable"]]:
    """The admitted candidate's own true capture anchor: the *earliest*
    `start_captured_at` among exactly the generations this specific
    admission was actually built from (`outcome.constituent_generation_ids`
    -- the already-admitted member's own facts, never a sibling's,
    critical for fallback safety; see this module's own fallback tests).
    `None`/`"unavailable"` only when every candidate is missing (a ledger
    snapshot saved before this field existed) -- never fabricated by
    falling back to an offset-derived estimate."""

    candidates = [
        generations_by_id[generation_id].start_captured_at
        for generation_id in outcome.constituent_generation_ids
        if generation_id in generations_by_id and generations_by_id[generation_id].start_captured_at is not None
    ]
    if not candidates:
        return None, "unavailable"
    return min(candidates), "earliest_constituent_generation_start_captured_at"


def _resolve_latency(
    t0: datetime | None, decided_at: datetime, max_plausible_latency_ms: int,
) -> tuple[LatencyState, float | None]:
    if t0 is None:
        return "unavailable_capture_time", None
    delta_ms = (decided_at - t0).total_seconds() * 1000
    if delta_ms < 0:
        # Never reported as a real negative number -- see this milestone's
        # own §18 "Prevent negative latency."
        return "invalid_negative", None
    if delta_ms > max_plausible_latency_ms:
        return "implausible", None
    return "measured", delta_ms


def build_latency_samples(
    proposal_outcomes: Sequence[ProposalOutcomeRecord],
    track_generations: Sequence[TrackGenerationRecord],
    *,
    max_plausible_latency_ms: int = DEFAULT_MAX_PLAUSIBLE_LATENCY_MS,
) -> tuple[LatencySample, ...]:
    """One `LatencySample` per *admitted* proposal outcome (`outcome.
    admitted and outcome.visit_id`) -- a blocked/rejected proposal was
    never a user-visible Visit and has no latency to measure. Deduplicates
    nothing itself: pass the already-deduplicated, latest-state-per-
    proposal-id view a caller already has (`cluster_encounters`'s own
    established convention), not raw cumulative ledger records."""

    generations_by_id = {item.generation_id: item for item in track_generations}
    samples: list[LatencySample] = []
    for outcome in proposal_outcomes:
        if not (outcome.admitted and outcome.visit_id):
            continue
        t0, t0_source = _resolve_t0(outcome, generations_by_id)
        state, latency_ms = _resolve_latency(t0, outcome.decided_at, max_plausible_latency_ms)
        is_fallback, fallback_position = _fallback_position(outcome.reason)
        samples.append(
            LatencySample(
                proposal_id=outcome.proposal_id, visit_id=outcome.visit_id, is_fallback=is_fallback,
                fallback_position=fallback_position, t0_captured_at=t0, t0_source=t0_source,
                decided_at=outcome.decided_at, state=state, latency_ms=latency_ms,
            )
        )
    return tuple(samples)


def _percentile(values: list[float], fraction: float) -> float | None:
    """Mirrors `onnx_provider._percentile` exactly -- deliberately
    duplicated, never imported, matching this package's own established
    "self-contained pure module" convention (a detector-provider module is
    also the wrong layer for an observation-accounting module to import
    from). `values` must already be sorted ascending."""
    if not values:
        return None
    position = (len(values) - 1) * fraction
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return round(values[lower], 3)
    interpolated = values[lower] + (values[upper] - values[lower]) * (position - lower)
    return round(interpolated, 3)


@dataclass(frozen=True)
class LatencySummary:
    schema_version: int
    sample_count: int
    measured_count: int
    unavailable_capture_time_count: int
    invalid_negative_count: int
    implausible_count: int
    fallback_measured_count: int
    median_ms: float | None
    p90_ms: float | None
    p95_ms: float | None
    max_ms: float | None
    mean_ms: float | None


def build_latency_summary(samples: Sequence[LatencySample]) -> LatencySummary:
    """Summary statistics over exactly the `state == "measured"` samples --
    every other state is counted, never silently folded into the
    percentiles (an `unavailable_capture_time` sample contributes zero
    latency, not `None`-as-zero; an `invalid_negative`/`implausible` sample
    is a flagged clock-domain anomaly, never averaged in as if valid)."""

    measured = sorted(sample.latency_ms for sample in samples if sample.state == "measured")  # type: ignore[type-var]
    fallback_measured = sum(1 for sample in samples if sample.state == "measured" and sample.is_fallback)
    return LatencySummary(
        schema_version=1,
        sample_count=len(samples),
        measured_count=len(measured),
        unavailable_capture_time_count=sum(1 for s in samples if s.state == "unavailable_capture_time"),
        invalid_negative_count=sum(1 for s in samples if s.state == "invalid_negative"),
        implausible_count=sum(1 for s in samples if s.state == "implausible"),
        fallback_measured_count=fallback_measured,
        median_ms=_percentile(measured, 0.5),
        p90_ms=_percentile(measured, 0.9),
        p95_ms=_percentile(measured, 0.95),
        max_ms=measured[-1] if measured else None,
        mean_ms=round(sum(measured) / len(measured), 3) if measured else None,
    )
