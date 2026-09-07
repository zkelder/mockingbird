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

Tracing the real production timeline (Gate A Measurement Closure v1's own
governing brief §13) found:

- **T0 (source capture)** now exists as a genuine wall-clock fact at the
  track-generation level -- `TrackGenerationRecord.start_captured_at` (Gate
  A Measurement Closure v1; see `counterfactual_lineage.py`), itself read
  straight off `TrackUpdate.captured_at`, which was already a required
  field on every tracker update the whole time, simply never previously
  copied onto the ledger's own output record. This is Node-domain (the
  Camera Node's own OS clock) -- see docs/camera-node-live-shadow-
  contract.md "Clock-drift disposition".
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
  and Gate A Measurement Closure v1's own report "Visibility boundary"
  section).

So this module measures **T0 -> decided_at** as the best-available direct
proxy for T0 -> T5 in the current architecture, and states that
substitution explicitly rather than silently relabeling it.

## Camera Node -> Host Clock Normalization v1

Gate A Measurement Closure v1 shipped this module with T0 left in its raw
Node-domain form, subtracted directly from Host-domain `decided_at` and
merely *disclosed* (a fixed `clock_domain_caveat` string) as
cross-domain -- never proven safe, and a real ~39-second discrepancy found
in v7's own preserved data (traced by this milestone -- see
docs/camera-node-host-clock-normalization-latency-v1-report.md "Root cause
of ~39s discrepancy" -- to a Node-internal `source_offset_ms`-vs-`captured_at`
divergence, *not* proof of a Node-Host offset, which no prior cohort ever
actually measured) sharpened exactly this risk into "the measurement itself
must become valid," not merely caveated.

This module now requires an actual, bounded clock-calibration mapping
(`clock_calibration.py`) before treating a cross-domain sample as
`"measured"`:

- `clock_calibration_required=False` (the default): T0 is already assumed
  Host-compatible (no Camera Node in the loop -- an RTSP/local/USB/replay
  source's `captured_at` is stamped by this same Host's own clock; see
  `contracts.FramePacket.received_at`, `None` for every non-Camera-Node
  source). Latency is computed exactly as before this milestone: direct
  subtraction, no calibration needed because there is only one clock
  domain to begin with. Every pre-existing test in this file exercises
  exactly this path, unchanged.
- `clock_calibration_required=True` (set by a caller that knows this
  session came from a real Camera Node -- `engine_runtime._EngineSession`
  when `provider_key == "camera_node"`, or the field-acceptance CLI when a
  saved ledger snapshot says so): T0 is normalized through an RTT-bounded
  anchor (see "Camera Node <-> Host RTT-Bounded Clock Calibration v1",
  below) before any subtraction. `state="invalid_clock_mapping"` (a new,
  distinct `LatencyState` -- never merged with `unavailable_capture_time`/
  `implausible`) replaces the old silent cross-domain subtraction whenever
  no trustworthy calibration covers this sample's own moment.

## Camera Node <-> Host RTT-Bounded Clock Calibration v1

The one-way calibration this module originally normalized T0 through
(`clock_calibration.estimate_clock_calibration`/`normalize_capture_time`)
only ever produced a one-sided upper bound on the true offset
(`true_offset_ms <= min(deltas)`), not a defensible two-sided error bound
-- disclosed honestly by that milestone's own report, closed by this one.
This module now normalizes T0 exclusively through the RTT-bounded anchor
(`clock_calibration.RttClockCalibrationRecord`/`normalize_capture_time_
with_bound`), which reuses the existing `/node/v1/health` request/response
operation to derive a rigorously justified `[offset_min_ms, offset_max_ms]`
interval -- see `clock_calibration.py`'s own docstring "Camera Node <->
Host RTT-Bounded Clock Calibration v1" for the full derivation and
docs/camera-node-host-rtt-bounded-clock-calibration-v1-report.md for the
complete record.

`build_latency_samples`'s own `rtt_calibrations` parameter (replacing the
prior `clock_calibrations` parameter, which took the one-way estimator's
own record type) carries this RTT-bounded anchor history. The one-way
estimator itself is **not discarded** (per this milestone's own explicit
instruction) -- it continues to exist, unchanged, in `clock_calibration.py`
and continues to be fed by `engine_runtime._EngineSession`'s own ~10-second
per-tick loop, but its role is now exclusively *relative* monitoring
(drift/jump detection that decides when a live session should spend the
cost of a fresh RTT-bounded batch), never the source of an authoritative
T0 mapping -- a one-sided bound can never honestly become a defensible
two-sided one no matter how it is consumed downstream.

Every sample now carries the full interval, never only a collapsed point
estimate (this milestone's own explicit "do not collapse the interval into
a false single exact number"): `t0_captured_at_normalized`/`clock_
offset_ms` remain the point estimate (the RTT anchor's own interval
midpoint, for continuity with every existing consumer of those two field
names), and `t0_captured_at_normalized_min`/`_max` and `clock_offset_min_
ms`/`_max_ms` are new, additive fields carrying the honest bound.
`latency_ms` (point estimate), `latency_min_ms`, and `latency_max_ms`
follow the same pattern -- derived from the *same* interval, never treated
as three independent measurements.

Pure: no filesystem, network, CUDA/ONNX Runtime/OpenCV, product-repository,
or SQLAlchemy import, matching every sibling Stage 6.x/7 decision module in
this package.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import math
from typing import Literal, Mapping, Sequence

from mockingbird.observation.clock_calibration import RttClockCalibrationRecord, normalize_capture_time_with_bound
from mockingbird.observation.counterfactual_lineage import ProposalOutcomeRecord, TrackGenerationRecord

CAPTURE_TO_VISIBLE_LATENCY_VERSION = "capture-to-visible-latency-v2"

_FALLBACK_REASON_MARKER = ":fallback_position_"

# A clock-domain safety backstop only (Gate A Measurement Closure v1's own
# §18), never a real session-length bound: the counterfactual ledger's own
# *retention* is capped at 60 minutes, but a genuine session -- and
# therefore a genuine T0 -> decided_at gap for an early-session encounter
# re-evaluated late -- can honestly exceed that. This exists to catch a
# wall/monotonic-mix- or wrong-epoch-shaped bug (hours where seconds were
# meant), not to reject an unusually slow but real admission.
DEFAULT_MAX_PLAUSIBLE_LATENCY_MS = 6 * 60 * 60 * 1000  # 6 hours

LatencyState = Literal[
    "measured", "unavailable_capture_time", "invalid_negative", "implausible", "invalid_clock_mapping",
]

ClockCalibrationState = Literal["not_required", "normalized", "no_calibration"]

_CLOCK_DOMAIN_CAVEAT = (
    "t0_captured_at is Node-domain (the Camera Node's own OS clock) unless "
    "clock_calibration_state == 'not_required' (no Camera Node in this "
    "session's own capture path, e.g. RTSP/local/USB -- t0_captured_at is "
    "already Host-compatible). When clock_calibration_state == 'normalized', "
    "t0_captured_at_normalized/clock_offset_ms/clock_uncertainty_ms are the "
    "RTT-bounded anchor's own interval midpoint/radius (see clock_"
    "calibration.py 'Camera Node <-> Host RTT-Bounded Clock Calibration "
    "v1') -- never represented as exact; t0_captured_at_normalized_min/_max "
    "and clock_offset_min_ms/_max_ms carry the full, honest bound the "
    "point estimate was drawn from. When clock_calibration_state == "
    "'no_calibration', no trustworthy RTT-bounded anchor covered this "
    "sample and state is invalid_clock_mapping, never a silent cross-"
    "domain subtraction and never a substitution of the one-way per-frame "
    "estimator (which cannot itself produce a defensible two-sided bound)."
)


@dataclass(frozen=True)
class LatencySample:
    """One admitted candidate's own T0 -> decided_at measurement (see this
    module's own docstring for why `decided_at` is the best-available T5
    proxy today, and `t0_source` for exactly how `t0_captured_at` was
    resolved). `is_fallback`/`fallback_position` are read from the
    engine's own already-established `reason` suffix convention
    (`engine_runtime.py._attempt_resolved_component`) -- never
    recomputed/guessed.

    `t0_captured_at` is always the *raw* value (Node-domain, or already
    Host-compatible when `clock_calibration_state == "not_required"`).
    `t0_captured_at_normalized` is the point estimate actually used for
    `latency_ms` -- identical to `t0_captured_at` when not required, the
    RTT-bounded anchor's own interval midpoint when `"normalized"`, and
    `None` when `"no_calibration"` (in which case `state ==
    "invalid_clock_mapping"` and `latency_ms` is `None`, never a value
    computed from the raw, unnormalized subtraction).

    Camera Node <-> Host RTT-Bounded Clock Calibration v1 (additive):
    `t0_captured_at_normalized_min`/`_max` and `clock_offset_min_ms`/
    `_max_ms` carry the RTT-bounded anchor's own full, honest interval --
    `None` unless `clock_calibration_state == "normalized"`, mirroring the
    point-estimate fields' own gating exactly. `latency_min_ms`/`_max_ms`
    are the corresponding latency bounds -- note the *inversion*: the
    earliest possible T0 (`t0_captured_at_normalized_min`) yields the
    *largest* possible latency (`latency_max_ms`), and vice versa, since
    latency is `decided_at - t0` (see `_resolve_latency`'s own docstring).
    Never collapsed into the point estimate alone (this milestone's own
    explicit "do not collapse the interval into a false single exact
    number")."""

    proposal_id: str
    visit_id: str
    is_fallback: bool
    fallback_position: int | None
    t0_captured_at: datetime | None
    t0_source: Literal["earliest_constituent_generation_start_captured_at", "unavailable"]
    t0_captured_at_normalized: datetime | None
    clock_calibration_state: ClockCalibrationState
    clock_offset_ms: float | None
    clock_uncertainty_ms: float | None
    decided_at: datetime
    state: LatencyState
    latency_ms: float | None
    t0_captured_at_normalized_min: datetime | None = None
    t0_captured_at_normalized_max: datetime | None = None
    clock_offset_min_ms: float | None = None
    clock_offset_max_ms: float | None = None
    latency_min_ms: float | None = None
    latency_max_ms: float | None = None
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
) -> tuple[datetime | None, Literal["earliest_constituent_generation_start_captured_at", "unavailable"], int | None]:
    """The admitted candidate's own true capture anchor: the *earliest*
    `start_captured_at` among exactly the generations this specific
    admission was actually built from (`outcome.constituent_generation_ids`
    -- the already-admitted member's own facts, never a sibling's,
    critical for fallback safety; see this module's own fallback tests).
    Also returns that same winning generation's own `start_offset_ms` --
    the Node-session-relative anchor clock-calibration selection keys off
    (see `_normalize_t0`), never a wall-clock value.
    `(None, "unavailable", None)` only when every candidate is missing (a
    ledger snapshot saved before this field existed) -- never fabricated by
    falling back to an offset-derived estimate."""

    candidates = [
        (generations_by_id[generation_id].start_captured_at, generations_by_id[generation_id].start_offset_ms)
        for generation_id in outcome.constituent_generation_ids
        if generation_id in generations_by_id and generations_by_id[generation_id].start_captured_at is not None
    ]
    if not candidates:
        return None, "unavailable", None
    captured_at, offset_ms = min(candidates, key=lambda pair: pair[0])
    return captured_at, "earliest_constituent_generation_start_captured_at", offset_ms


@dataclass(frozen=True)
class _NormalizedT0:
    t0_captured_at_normalized: datetime | None
    clock_calibration_state: ClockCalibrationState
    clock_offset_ms: float | None
    clock_uncertainty_ms: float | None
    t0_captured_at_normalized_min: datetime | None = None
    t0_captured_at_normalized_max: datetime | None = None
    clock_offset_min_ms: float | None = None
    clock_offset_max_ms: float | None = None


_NOT_REQUIRED = _NormalizedT0(None, "not_required", None, None)


def _normalize_t0(
    t0_raw: datetime | None,
    t0_source_offset_ms: int | None,
    *,
    rtt_calibrations: Sequence[RttClockCalibrationRecord],
    clock_calibration_required: bool,
) -> _NormalizedT0:
    """`t0_captured_at_normalized` mirrors `t0_captured_at` unchanged
    (`clock_calibration_state="not_required"`) whenever calibration is not
    required at all, or `t0_raw` itself is missing (nothing to normalize --
    the caller's own `state` already becomes `unavailable_capture_time` in
    that case, so this function's own output is never consulted for it).
    Only when calibration is genuinely required and `t0_raw` exists does
    this call into `clock_calibration.normalize_capture_time_with_bound` --
    the RTT-bounded anchor, never the one-way per-frame estimator (see this
    module's own docstring "Camera Node <-> Host RTT-Bounded Clock
    Calibration v1")."""

    if not clock_calibration_required:
        # No cross-clock-domain risk to normalize away -- t0_raw (if any) is
        # already Host-compatible. Mirrors it unchanged.
        return _NormalizedT0(t0_raw, "not_required", None, None)
    if t0_raw is None:
        # Nothing to normalize; the caller's own `state` already becomes
        # `unavailable_capture_time` regardless of this value.
        return _NOT_REQUIRED
    assert t0_source_offset_ms is not None  # always set alongside a non-None t0_raw -- see `_resolve_t0`
    normalized = normalize_capture_time_with_bound(t0_raw, rtt_calibrations, source_offset_ms=t0_source_offset_ms)
    if normalized.state == "no_calibration":
        return _NormalizedT0(None, "no_calibration", None, None)
    return _NormalizedT0(
        normalized.host_domain_captured_at_estimate, "normalized",
        normalized.offset_estimate_ms, normalized.uncertainty_ms,
        normalized.host_domain_captured_at_min, normalized.host_domain_captured_at_max,
        normalized.offset_min_ms, normalized.offset_max_ms,
    )


def _resolve_latency(
    t0_raw: datetime | None, normalized: _NormalizedT0, decided_at: datetime, max_plausible_latency_ms: int,
) -> tuple[LatencyState, float | None, float | None, float | None]:
    """Returns `(state, latency_ms, latency_min_ms, latency_max_ms)`.

    Latency is `decided_at - t0` -- a *decreasing* function of t0, so the
    interval inverts: the earliest possible host-domain t0
    (`t0_captured_at_normalized_min`) yields the *largest* possible latency
    (`latency_max_ms`), and the latest possible t0
    (`t0_captured_at_normalized_max`) yields the *smallest* possible
    latency (`latency_min_ms`). Getting this backwards is exactly the kind
    of sign-inversion bug this milestone's own §34 self-review checklist
    names -- see `test_normalize_capture_time_with_bound_direction_is_not_
    inverted`/the analogous latency-level test in this module's own test
    file for the regression proof.

    Impossible-result policy (this milestone's own explicit §22): only
    `latency_max_ms < 0` (impossible even under the single most charitable
    -- fastest-t0 -- reading of the interval) is rejected as `invalid_
    negative`, and only `latency_min_ms > max_plausible_latency_ms` (still
    implausible even under the most charitable -- latest-t0 -- reading) is
    rejected as `implausible`. A point estimate or lower bound that happens
    to be slightly negative, while the upper bound remains non-negative, is
    *not* impossible -- it is an honestly wide-but-plausible interval, and
    is reported as `measured` with its true (possibly negative) bounds
    intact. Never clamped, never silently narrowed -- see this module's own
    §22 "do not clamp negatives; do not silently select a convenient
    endpoint; do not drop the error bound.\""""

    if t0_raw is None:
        return "unavailable_capture_time", None, None, None
    if normalized.clock_calibration_state == "no_calibration":
        # Never silently fall back to the raw, unnormalized subtraction, and
        # never silently substitute the one-way per-frame estimator (which
        # cannot itself produce a defensible two-sided bound) -- a distinct
        # state, never merged with unavailable_capture_time/implausible.
        return "invalid_clock_mapping", None, None, None
    host_domain_t0 = normalized.t0_captured_at_normalized
    assert host_domain_t0 is not None  # guaranteed by "not_required"/"normalized" above
    latency_ms = (decided_at - host_domain_t0).total_seconds() * 1000

    if normalized.clock_calibration_state == "normalized":
        assert normalized.t0_captured_at_normalized_min is not None
        assert normalized.t0_captured_at_normalized_max is not None
        latency_max_ms = (decided_at - normalized.t0_captured_at_normalized_min).total_seconds() * 1000
        latency_min_ms = (decided_at - normalized.t0_captured_at_normalized_max).total_seconds() * 1000
    else:
        # "not_required": a single-clock-domain source has no interval at
        # all -- the point estimate is the entire (degenerate, zero-width)
        # interval, exactly like every pre-existing test in this file
        # expects.
        latency_min_ms = latency_max_ms = latency_ms

    if latency_max_ms < 0:
        return "invalid_negative", None, None, None
    if latency_min_ms > max_plausible_latency_ms:
        return "implausible", None, None, None
    return "measured", latency_ms, latency_min_ms, latency_max_ms


def build_latency_samples(
    proposal_outcomes: Sequence[ProposalOutcomeRecord],
    track_generations: Sequence[TrackGenerationRecord],
    *,
    rtt_calibrations: Sequence[RttClockCalibrationRecord] = (),
    clock_calibration_required: bool = False,
    max_plausible_latency_ms: int = DEFAULT_MAX_PLAUSIBLE_LATENCY_MS,
) -> tuple[LatencySample, ...]:
    """One `LatencySample` per *admitted* proposal outcome (`outcome.
    admitted and outcome.visit_id`) -- a blocked/rejected proposal was
    never a user-visible Visit and has no latency to measure. Deduplicates
    nothing itself: pass the already-deduplicated, latest-state-per-
    proposal-id view a caller already has (`cluster_encounters`'s own
    established convention), not raw cumulative ledger records.

    `clock_calibration_required` defaults to `False` -- the pre-Camera-Node
    -Host-Clock-Normalization-v1 behavior, appropriate for any source whose
    `captured_at` is already Host-domain (no cross-clock-domain risk to
    normalize away). Pass `True`, with this same window's own
    `rtt_calibrations` (from `counterfactual_lineage.
    CounterfactualWindowResult.rtt_clock_calibrations`), for a session
    known to have used a real Camera Node -- see this module's own
    docstring "Camera Node <-> Host RTT-Bounded Clock Calibration v1".
    Replaces the prior `clock_calibrations` parameter (the one-way
    estimator's own record type), deliberately renamed rather than
    silently retyped -- the one-way estimator can never supply a
    defensible bound, so a caller migrating from the prior contract must
    consciously supply the new, stronger anchor type instead."""

    generations_by_id = {item.generation_id: item for item in track_generations}
    samples: list[LatencySample] = []
    for outcome in proposal_outcomes:
        if not (outcome.admitted and outcome.visit_id):
            continue
        t0, t0_source, t0_source_offset_ms = _resolve_t0(outcome, generations_by_id)
        normalized = _normalize_t0(
            t0, t0_source_offset_ms,
            rtt_calibrations=rtt_calibrations, clock_calibration_required=clock_calibration_required,
        )
        state, latency_ms, latency_min_ms, latency_max_ms = _resolve_latency(
            t0, normalized, outcome.decided_at, max_plausible_latency_ms,
        )
        is_fallback, fallback_position = _fallback_position(outcome.reason)
        samples.append(
            LatencySample(
                proposal_id=outcome.proposal_id, visit_id=outcome.visit_id, is_fallback=is_fallback,
                fallback_position=fallback_position, t0_captured_at=t0, t0_source=t0_source,
                t0_captured_at_normalized=normalized.t0_captured_at_normalized,
                clock_calibration_state=normalized.clock_calibration_state,
                clock_offset_ms=normalized.clock_offset_ms, clock_uncertainty_ms=normalized.clock_uncertainty_ms,
                decided_at=outcome.decided_at, state=state, latency_ms=latency_ms,
                t0_captured_at_normalized_min=normalized.t0_captured_at_normalized_min,
                t0_captured_at_normalized_max=normalized.t0_captured_at_normalized_max,
                clock_offset_min_ms=normalized.clock_offset_min_ms,
                clock_offset_max_ms=normalized.clock_offset_max_ms,
                latency_min_ms=latency_min_ms, latency_max_ms=latency_max_ms,
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
    invalid_clock_mapping_count: int
    fallback_measured_count: int
    median_ms: float | None
    p90_ms: float | None
    p95_ms: float | None
    max_ms: float | None
    mean_ms: float | None
    mean_uncertainty_ms: float | None = None


def build_latency_summary(samples: Sequence[LatencySample]) -> LatencySummary:
    """Summary statistics over exactly the `state == "measured"` samples --
    every other state is counted, never silently folded into the
    percentiles (an `unavailable_capture_time` sample contributes zero
    latency, not `None`-as-zero; an `invalid_negative`/`implausible`/
    `invalid_clock_mapping` sample is a flagged anomaly, never averaged in
    as if valid -- and never merged with each other: each has its own
    distinct count).

    `mean_uncertainty_ms` (Camera Node <-> Host RTT-Bounded Clock
    Calibration v1, additive): the mean per-sample latency-interval
    half-width (`(latency_max_ms - latency_min_ms) / 2`) across every
    `measured` sample whose interval is not degenerate (`clock_
    calibration_state == "normalized"`) -- a single number for "how tight
    was calibration across this whole window," for an auditor who does not
    want to read every sample's own bound individually (this milestone's
    own §23 reporting requirement). `None` when no such sample exists,
    never fabricated as zero.

    `fallback_measured_count` (Field Acceptance Tooling Correctness &
    Preflight Closure v1 -- terminology audit, no logic change): a strict
    *subset* of `measured_count`, never a state of its own and never a
    lesser/degraded kind of measurement. "Fallback" here means exactly one
    thing -- `LatencySample.is_fallback`, itself read straight from
    `outcome.reason`'s own `:fallback_position_N` suffix
    (`_fallback_position`, above) -- i.e. this admitted candidate won an
    ambiguous-boundary arbitration contest as a *non-top-ranked* member
    after the top-ranked member(s) failed, not that its *timestamp* is any
    kind of fallback/approximate value. There is no separate "fallback
    timestamp" concept anywhere in this module (or this codebase): every
    `fallback_measured` sample's own T0 was resolved by the exact same
    `_resolve_t0`/`_normalize_t0`/`_resolve_latency` path as every other
    sample, off the *admitted* member's own `constituent_generation_ids`
    (never a sibling's, never the failed original winner's -- see
    `_resolve_t0`'s own docstring and `test_fallback_latency_after_clock_
    normalization_uses_the_admitted_members_own_capture_time_not_the_
    failed_winners`) -- so a `fallback_measured` sample can be, and often
    is, `clock_calibration_state == "normalized"` (a genuine RTT-bounded
    anchor) exactly like any other measured sample, never silently
    promoted from some lesser calibration state. See representative-
    daylight-gate-a-field-acceptance-v9-report.md's own "Fallback
    admission" section for the same distinction, stated the same way, the
    first time this project reported this count."""

    measured = sorted(sample.latency_ms for sample in samples if sample.state == "measured")  # type: ignore[type-var]
    fallback_measured = sum(1 for sample in samples if sample.state == "measured" and sample.is_fallback)
    uncertainty_widths = [
        (sample.latency_max_ms - sample.latency_min_ms) / 2.0
        for sample in samples
        if sample.state == "measured" and sample.clock_calibration_state == "normalized"
        and sample.latency_min_ms is not None and sample.latency_max_ms is not None
    ]
    return LatencySummary(
        schema_version=3,
        sample_count=len(samples),
        measured_count=len(measured),
        unavailable_capture_time_count=sum(1 for s in samples if s.state == "unavailable_capture_time"),
        invalid_negative_count=sum(1 for s in samples if s.state == "invalid_negative"),
        implausible_count=sum(1 for s in samples if s.state == "implausible"),
        invalid_clock_mapping_count=sum(1 for s in samples if s.state == "invalid_clock_mapping"),
        fallback_measured_count=fallback_measured,
        median_ms=_percentile(measured, 0.5),
        p90_ms=_percentile(measured, 0.9),
        p95_ms=_percentile(measured, 0.95),
        max_ms=measured[-1] if measured else None,
        mean_ms=round(sum(measured) / len(measured), 3) if measured else None,
        mean_uncertainty_ms=round(sum(uncertainty_widths) / len(uncertainty_widths), 3) if uncertainty_widths else None,
    )
