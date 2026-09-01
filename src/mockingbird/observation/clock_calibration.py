"""Camera Node -> Host Clock Normalization & True Capture-to-Visible Latency
v1 (see docs/camera-node-host-clock-normalization-latency-v1-report.md).

Gate A Measurement Closure v1 (`capture_to_visible_latency.py`) proved a
capture-to-visible latency *definition* (T0 -> `decided_at`) but disclosed,
rather than solved, a real problem: T0 (`TrackGenerationRecord.
start_captured_at`) is Node-domain (the Camera Node's own OS clock) while
`decided_at` is Host-domain (this Host's own OS clock), and
docs/camera-node-live-shadow-contract.md "Clock-drift disposition" already
documents that these two clocks are not assumed synchronized. Subtracting
them directly is not proven safe.

This module supplies the missing piece: a bounded, session-scoped,
honestly-uncertain mapping from Node-domain capture time to a Host
-compatible estimate, built entirely from an already-existing timestamp
pair -- never a new network-time protocol (per this milestone's own
explicit instruction, "do not invent a new network time protocol if an
existing timestamp pair already solves the problem").

## Why not a textbook NTP round trip

The governing brief's own preferred method (Host send `H0` -> Node reply
`N` -> Host receive `H1`; offset ~= `(H0+H1)/2 - N`; uncertainty >=
`(H1-H0)/2`) requires a request/response exchange. The Camera Node analysis
-stream protocol has no such exchange -- it is a one-way push: the Node
captures a frame, stamps it with its own wall clock
(`AnalysisFrameEnvelope.captured_at`), and streams it; the Host stamps its
own wall clock the moment it finishes receiving it
(`camera_node_live.CameraNodeAnalysisSource._pop_latest`'s `received_at`,
already carried on every delivered `contracts.FramePacket`). This
one-way-delivery pair is the "existing timestamp pair" this module reuses,
not a new mechanism.

## The one-way estimator (a bounded, honest, non-NTP method)

For one delivered frame, `delta_ms = received_at - captured_at`. Because a
frame can only travel forward in time (capture always precedes receipt),
`delta_ms = true_clock_offset_ms + one_way_transit_ms`, and
`one_way_transit_ms >= 0` always. Therefore, across a window of `N`
samples:

- `true_clock_offset_ms <= min(delta_ms for all samples)` always holds --
  the minimum observed delta is the tightest achievable, least-transit
  -contaminated estimate of the true offset (a well-known one-way-delay
  estimation technique: the sample least polluted by queueing/encoding/
  network transit is the one that traveled fastest). This module reports
  `offset_ms = min(deltas)` as the point estimate.
- `uncertainty_ms = max(deltas) - min(deltas)` -- the empirically observed
  jitter spread across the same window. This is deliberately conservative
  and asymmetric in what it proves: it does **not** claim the two-sided
  statistical guarantee a real round-trip bound would (this module never
  claims that), only that the point estimate could plausibly be off by up
  to this much transit-delay variance, honestly disclosed rather than
  invented as zero (per this milestone's own explicit "do not pretend
  network latency is zero").

A calibration attempt with fewer than `MINIMUM_CALIBRATION_SAMPLES` samples
still produces a record (`state="insufficient_samples"`) rather than being
silently dropped -- every attempt stays auditable (see
`docs/camera-node-host-clock-normalization-latency-v1-report.md`
"Calibration method").

## Session/stream scope, drift, and clock jumps

A calibration is meaningful only for the stream and time window it was
computed from (see this milestone's own governing brief SS8: "do not assume
yesterday's Node/Host offset remains valid today"). A long session is
expected to accumulate *several* `ClockCalibrationRecord`s over time
(refreshed periodically by the live session, see `engine_runtime.
_EngineSession._refresh_clock_calibration`), each anchored to the
Node-session-relative `source_offset_ms` of the window it summarizes --
the same domain-safe coordinate every other counterfactual-ledger record
already keys off, so selecting "the calibration that governed this
particular capture" never itself requires comparing two wall clocks.

`compute_drift` reports the measured offset change between two calibrated
samples of the same stream, informational only -- it never gates whether a
sample is usable. `detect_clock_jump`/`active_calibration_for_offset`
instead enforce the actual safety property: once a new calibration sample
reveals an offset change larger than `DEFAULT_CLOCK_JUMP_THRESHOLD_MS`
relative to the immediately-preceding calibrated sample (a discontinuity --
a Node reboot to a wrong time, a manual clock change, an NTP step
correction -- categorically different from ordinary jitter or gradual
drift), every sample governed by the *pre-jump* calibration for an offset
at or after the jump point becomes unreachable: `active_calibration_for_
offset` will not let a pre-jump calibration answer for a post-jump offset,
or vice versa. This module never interpolates across a detected jump and
never extrapolates backward past the very first calibration a stream ever
recorded -- an offset with no governing calibration is honestly
`state="no_calibration"`, never silently computed from a guess (see this
milestone's own SS11 "invalid sample policy").

`DEFAULT_CLOCK_JUMP_THRESHOLD_MS` (5 seconds) and
`MINIMUM_CALIBRATION_SAMPLES` (5) are disclosed, deliberate judgment calls,
not derived constants -- 5 seconds comfortably exceeds ordinary LAN jitter
and ordinary inter-calibration drift (both expected to stay well under a
second between ~10-second-cadence refreshes) while comfortably staying
below a genuine clock reset (this milestone's own SS17 example: +-30s).
Mirrors the precedent already set by `mockingbird_doctor_operational_
health_contract.md`'s own disclosed 30-day backup-staleness threshold: a
documented choice, not a derivation from first principles, changeable if
real evidence ever calls for it.

## Local Only

Every function in this module operates only on timestamp pairs the Camera
Node <-> Host protocol already exchanges during ordinary operation -- no
external NTP server, no internet reachability, no cloud service is read or
required. The Node and Host may each independently run NTP against their
own configured servers (that is a system-administration concern, entirely
outside this module), but calibration *correctness* here never depends on
either one reaching the internet.

Pure: no filesystem, network, CUDA/ONNX Runtime/OpenCV, product-repository,
or SQLAlchemy import -- the same structural convention every other Stage
6.x/7 decision module in this package follows.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal, Sequence

CLOCK_CALIBRATION_VERSION = "clock-calibration-v1"

CalibrationState = Literal["calibrated", "insufficient_samples"]

# Disclosed judgment calls -- see this module's own docstring "Session/
# stream scope, drift, and clock jumps" for the reasoning behind both.
MINIMUM_CALIBRATION_SAMPLES = 5
DEFAULT_CLOCK_JUMP_THRESHOLD_MS = 5_000.0


@dataclass(frozen=True)
class ClockCalibrationRecord:
    """One calibration attempt for one stream, anchored to the Node
    -session-relative `source_offset_ms` of the window it summarizes (the
    same domain-safe coordinate `TrackGenerationRecord`/`ProposalOutcomeRecord`
    already key off -- never a wall-clock anchor, so ordering calibrations
    against track/proposal offsets never itself compares two clocks).

    `state="insufficient_samples"` is a real, auditable outcome (never
    silently dropped) -- `offset_ms`/`uncertainty_ms`/`min_delta_ms`/
    `max_delta_ms` stay `None` in that case, never a fabricated number from
    too few samples. `clock_jump_detected` is set by whichever caller
    sequences calibrations over time (`counterfactual_lineage.
    CounterfactualLedger.record_clock_calibration`) after comparing this
    sample against its own immediately-preceding calibrated sample -- never
    computed from this record alone.
    """

    stream_id: str
    source_offset_ms: int
    calibrated_at: datetime
    sample_count: int
    state: CalibrationState
    offset_ms: float | None = None
    uncertainty_ms: float | None = None
    min_delta_ms: float | None = None
    max_delta_ms: float | None = None
    clock_jump_detected: bool = False

    def __post_init__(self) -> None:
        if not self.stream_id:
            raise ValueError("invalid_clock_calibration_stream")
        if self.calibrated_at.tzinfo is None:
            raise ValueError("invalid_clock_calibration_timestamp")
        if self.sample_count < 0:
            raise ValueError("invalid_clock_calibration_sample_count")
        if self.state == "calibrated" and (self.offset_ms is None or self.uncertainty_ms is None):
            raise ValueError("invalid_clock_calibration_state")


def estimate_clock_calibration(
    pairs: Sequence[tuple[datetime, datetime]],
    *,
    stream_id: str,
    source_offset_ms: int,
    calibrated_at: datetime,
    minimum_samples: int = MINIMUM_CALIBRATION_SAMPLES,
) -> ClockCalibrationRecord:
    """One calibration attempt from `pairs` of `(node_captured_at,
    host_received_at)` -- exactly the two already-populated fields every
    Camera Node `contracts.FramePacket` carries
    (`camera_node_live.CameraNodeAnalysisSource._pop_latest` sets both on
    every delivered packet today; this function is the first consumer of
    the pair together). See this module's own docstring "The one-way
    estimator" for the `min`/`spread` method and why no round trip is used.

    Never raises for too few samples (`state="insufficient_samples"`,
    auditable, not silently dropped) -- only raises for a structurally
    invalid input (a naive/tz-less timestamp)."""

    for node_captured_at, host_received_at in pairs:
        if node_captured_at.tzinfo is None or host_received_at.tzinfo is None:
            raise ValueError("invalid_clock_calibration_pair")
    if len(pairs) < minimum_samples:
        return ClockCalibrationRecord(
            stream_id=stream_id,
            source_offset_ms=source_offset_ms,
            calibrated_at=calibrated_at,
            sample_count=len(pairs),
            state="insufficient_samples",
        )
    deltas_ms = [
        (host_received_at - node_captured_at).total_seconds() * 1000.0
        for node_captured_at, host_received_at in pairs
    ]
    lowest, highest = min(deltas_ms), max(deltas_ms)
    return ClockCalibrationRecord(
        stream_id=stream_id,
        source_offset_ms=source_offset_ms,
        calibrated_at=calibrated_at,
        sample_count=len(pairs),
        state="calibrated",
        offset_ms=lowest,
        uncertainty_ms=highest - lowest,
        min_delta_ms=lowest,
        max_delta_ms=highest,
    )


def detect_clock_jump(
    previous: ClockCalibrationRecord,
    current: ClockCalibrationRecord,
    *,
    max_jump_ms: float = DEFAULT_CLOCK_JUMP_THRESHOLD_MS,
) -> bool:
    """Whether `current`'s own offset differs from `previous`'s by more than
    `max_jump_ms` -- a discontinuity, categorically different from ordinary
    jitter/drift (see this module's own docstring). `False` whenever either
    sample is not itself `state="calibrated"`: there is nothing numeric to
    compare, and an insufficient-samples attempt is never treated as
    evidence of a jump one way or the other."""

    if previous.state != "calibrated" or current.state != "calibrated":
        return False
    assert previous.offset_ms is not None and current.offset_ms is not None
    return abs(current.offset_ms - previous.offset_ms) > max_jump_ms


@dataclass(frozen=True)
class DriftObservation:
    """Informational only -- never gates whether a calibration/sample is
    usable (`detect_clock_jump` is the safety gate). Positive
    `drift_rate_ms_per_minute` means the Node clock is running *behind* the
    Host's (per-sample offset is growing); negative means it is running
    ahead."""

    elapsed_ms: float
    offset_delta_ms: float
    drift_rate_ms_per_minute: float


def compute_drift(previous: ClockCalibrationRecord, current: ClockCalibrationRecord) -> DriftObservation | None:
    """`None` (never fabricated) when either sample is not `state=
    "calibrated"`, or `current` was not calibrated strictly after
    `previous` -- a drift rate requires a real, positive elapsed interval."""

    if previous.state != "calibrated" or current.state != "calibrated":
        return None
    elapsed_ms = (current.calibrated_at - previous.calibrated_at).total_seconds() * 1000.0
    if elapsed_ms <= 0:
        return None
    assert previous.offset_ms is not None and current.offset_ms is not None
    offset_delta_ms = current.offset_ms - previous.offset_ms
    return DriftObservation(
        elapsed_ms=elapsed_ms,
        offset_delta_ms=offset_delta_ms,
        drift_rate_ms_per_minute=offset_delta_ms / elapsed_ms * 60_000.0,
    )


def active_calibration_for_offset(
    calibrations: Sequence[ClockCalibrationRecord],
    *,
    source_offset_ms: int,
) -> ClockCalibrationRecord | None:
    """The calibration that governs `source_offset_ms`, honoring clock-jump
    boundaries and never extrapolating backward past the first calibration
    a stream ever recorded.

    Model: a stream's own `state="calibrated"` history (ordered by
    `source_offset_ms`) is divided into "epochs" -- a new epoch begins at
    index 0 and at every sample whose own `clock_jump_detected` is `True`.
    Within one epoch, no jump ever occurred, so any of its samples may
    safely govern any offset from its own `source_offset_ms` up to (but not
    across) the next epoch's own start. An offset preceding the very first
    epoch's own first sample has no governing calibration at all --
    `None`, not an extrapolated guess (see this module's own docstring)."""

    calibrated = sorted(
        (item for item in calibrations if item.state == "calibrated"), key=lambda item: item.source_offset_ms,
    )
    if not calibrated:
        return None
    epoch_starts = [0] + [index for index, item in enumerate(calibrated) if index > 0 and item.clock_jump_detected]
    governing_start = None
    for start in epoch_starts:
        if calibrated[start].source_offset_ms <= source_offset_ms:
            governing_start = start
        else:
            break
    if governing_start is None:
        return None
    next_start = next((start for start in epoch_starts if start > governing_start), len(calibrated))
    epoch_candidates = [
        item for item in calibrated[governing_start:next_start] if item.source_offset_ms <= source_offset_ms
    ]
    return epoch_candidates[-1] if epoch_candidates else None


NormalizedCaptureState = Literal["normalized", "no_calibration"]


@dataclass(frozen=True)
class NormalizedCapture:
    """The result of mapping one Node-domain capture time into the Host
    -compatible domain. `state="no_calibration"` means exactly that --
    never a value computed from a stale, jumped, or nonexistent
    calibration; `host_domain_captured_at`/`offset_ms`/`uncertainty_ms` stay
    `None` in that case."""

    node_captured_at: datetime
    host_domain_captured_at: datetime | None
    offset_ms: float | None
    uncertainty_ms: float | None
    state: NormalizedCaptureState
    calibration_source_offset_ms: int | None = None


def normalize_capture_time(
    node_captured_at: datetime,
    calibrations: Sequence[ClockCalibrationRecord],
    *,
    source_offset_ms: int,
) -> NormalizedCapture:
    """`node_captured_at + calibration.offset_ms`, using whichever
    calibration `active_calibration_for_offset` finds safe for
    `source_offset_ms` -- `state="no_calibration"` (never a raw,
    unnormalized fallback) when none is."""

    calibration = active_calibration_for_offset(calibrations, source_offset_ms=source_offset_ms)
    if calibration is None:
        return NormalizedCapture(
            node_captured_at=node_captured_at, host_domain_captured_at=None, offset_ms=None,
            uncertainty_ms=None, state="no_calibration",
        )
    assert calibration.offset_ms is not None
    host_domain_captured_at = node_captured_at + timedelta(milliseconds=calibration.offset_ms)
    return NormalizedCapture(
        node_captured_at=node_captured_at, host_domain_captured_at=host_domain_captured_at,
        offset_ms=calibration.offset_ms, uncertainty_ms=calibration.uncertainty_ms, state="normalized",
        calibration_source_offset_ms=calibration.source_offset_ms,
    )


__all__ = [
    "CLOCK_CALIBRATION_VERSION",
    "MINIMUM_CALIBRATION_SAMPLES",
    "DEFAULT_CLOCK_JUMP_THRESHOLD_MS",
    "CalibrationState",
    "ClockCalibrationRecord",
    "estimate_clock_calibration",
    "detect_clock_jump",
    "DriftObservation",
    "compute_drift",
    "active_calibration_for_offset",
    "NormalizedCaptureState",
    "NormalizedCapture",
    "normalize_capture_time",
]
