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

## Camera Node <-> Host RTT-Bounded Clock Calibration v1

See docs/camera-node-host-rtt-bounded-clock-calibration-v1-report.md. The
one-way method above establishes cheap, frequent *relative* drift/jump
monitoring, but -- as this milestone's own governing brief opens by
stating -- `offset_ms = min(deltas)` is only ever a one-sided upper bound
on the true offset (`true_offset_ms <= min(deltas)` always; the true lower
bound is unknown, since one-way transit delay could in principle be
arbitrarily small). `uncertainty_ms` there is an honest *quality* signal
(how much worse the other samples were), never a defensible two-sided
error bound. This section adds the missing absolute anchor.

**Correction to this module's own "Why not a textbook NTP round trip"
section, above.** That section's own conclusion -- no round trip exists in
the analysis-stream protocol, which is a one-way push -- remains correct
for the analysis stream specifically. It was examined in isolation and its
conclusion was implicitly generalized to "no round trip exists anywhere in
the Camera Node protocol," which does not hold: a separate, pre-existing,
synchronous request/response operation already exists on the same Camera
Node <-> Host connection -- `GET /node/v1/health`
(`mockingbird_node.app.health`, called via `source_providers.camera_node.
CameraNodeClient.health`) -- simply never used for clock calibration until
this milestone. Per this milestone's own explicit instruction ("do not
invent a dedicated time-sync protocol if the existing transport can supply
the required measurement"), this reuses that existing envelope rather than
adding a new one: the Node's `/node/v1/health` response gained two
additive fields, `node_receive_time` (sampled at the top of the handler,
before any work) and `node_time` (sampled immediately before the response
is returned) -- see `mockingbird_node/app.py`. An old Node's response
simply lacks both keys; every consumer here treats that exactly like a
missing/malformed sample (see "Old Node compatibility" below), never a
crash and never a required protocol version bump.

### The interval bound (not a symmetric round-trip formula)

For one bracketed round trip: `host_send_at` (H0, Host clock, immediately
before dispatch), `node_receive_at` (Nrecv, Node clock, sampled at the top
of the Node's own handler -- `None` unless the four-timestamp form is
available), `node_response_at` (Nsend/N1, Node clock, sampled immediately
before the Node's response is returned), `host_receive_at` (H1, Host
clock, immediately on response receipt). Let `true_offset_ms` be the
value such that `host_time = node_time + true_offset_ms` at the same real
instant (matching the existing one-way estimator's own sign convention:
positive means the Node's clock reads behind the Host's).

Two honest, one-directional consequences of "a request/response can only
travel forward in time" (never an assumption of symmetric transit delay,
per this milestone's own explicit "do not blindly copy NTP formulas if
transport semantics differ"):

- The request cannot have reached the Node before it left the Host:
  `host_send_at <= node_receive_at + true_offset_ms`, i.e.
  `true_offset_ms >= host_send_at - node_receive_at`.
- The response cannot have reached the Host before the Node sent it:
  `host_receive_at >= node_response_at + true_offset_ms`, i.e.
  `true_offset_ms <= host_receive_at - node_response_at`.

So `[host_send_at - node_receive_at, host_receive_at - node_response_at]`
is a rigorously justified two-sided bound on `true_offset_ms` -- narrower
than plain RTT/2 by exactly the Node's own disclosed processing time
(`node_response_at - node_receive_at`) when the four-timestamp form is
available (`Nrecv` present); when only `node_response_at` is available
(two-timestamp form, `Nrecv` defaults to `Nsend`), the bound reduces
exactly to `[H0, H1] - N1`, width `RTT = host_receive_at - host_send_at`,
matching the governing brief's own preferred `uncertainty >= RTT/2` floor
(radius = RTT/2 exactly). The point estimate reported (`offset_ms`) is the
bound's own midpoint -- reported for convenience, never represented as
exact (this milestone's own explicit "midpoint is not represented as
exact"; see `RttClockCalibrationRecord`'s own docstring). This is *not*
the classical symmetric-delay NTP offset formula (which assumes
`one_way_out ~= one_way_back`); it is a strictly weaker, honest inequality
that holds regardless of transit-delay asymmetry -- see "Asymmetry
limitation," below.

### Multi-sample selection

A calibration batch collects a small, bounded number of round trips (3-7;
see `MINIMUM_RTT_CALIBRATION_SAMPLES`). Each sample's own true offset must
satisfy its own interval; since it is the *same* true offset across a
short back-to-back batch (barring a clock jump mid-batch), the
*intersection* of every valid sample's own interval remains a correct,
and generally tighter, bound -- `combined_min = max(sample mins)`,
`combined_max = min(sample maxes)`. A sample whose own RTT exceeds
`DEFAULT_MAX_ACCEPTABLE_RTT_MS` is excluded before this step (a
too-poor-quality sample is dropped, never blended into a falsely precise
average -- this milestone's own explicit "do not average high-RTT samples
into a falsely precise estimate"); the surviving sample with the lowest
RTT is reported (`rtt_ms`/`node_processing_ms`) as the calibration's own
"best single sample," for diagnostics. If too few samples survive
filtering, `state="insufficient_samples"` (mirrors the one-way estimator's
own honest, auditable, never-fabricated outcome). If the surviving
samples' own intervals do not overlap at all (`combined_min >
combined_max`) -- which subsumes detecting a clock jump *during* the
batch itself, since a genuine jump mid-batch is exactly what produces
mutually-inconsistent per-sample intervals -- `state="inconsistent_
samples"`, a distinct, equally honest outcome; never silently resolved by
picking one sample's own interval over another's.

### Old Node compatibility

`node_response_at`/`node_receive_at` are `None` whenever the Node's own
`/node/v1/health` response predates this milestone (no new keys) or the
value fails to parse as a genuine tz-aware timestamp (a malformed
response). A round trip missing `node_response_at` cannot be bounded at
all and is excluded from the batch (contributes to `insufficient_samples`
if too many are like this) -- never a crash, and monitoring/the analysis
stream itself is entirely unaffected (see this milestone's own explicit
"do not turn latency instrumentation into a compatibility-breaking
requirement for basic observation").

### Asymmetry limitation

This bound does not, and cannot, prove that outbound and return transit
delay were equal -- no single-path measurement can. What it proves is
strictly weaker and fully honest: the true offset lies inside
`[combined_min, combined_max]`, because the request demonstrably left
before `node_receive_at`'s own real instant and the response demonstrably
arrived after `node_response_at`'s own real instant. The reported point
estimate (interval midpoint) is a convenient single number, not a claim
that transit was symmetric. A defensible bound, not perfect clock
synchronization, is this milestone's own explicit goal.

### Composing with the one-way per-frame monitor

Per this milestone's own explicit "do not discard the earlier
instrumentation": `active_calibration_for_offset`/`normalize_capture_time`
(one-way, above) are unchanged and continue to exist, but no longer feed
`capture_to_visible_latency.py`'s own T0 normalization (see that module's
own docstring) -- a one-way calibration alone can only ever produce a
one-sided bound, never the defensible two-sided one this milestone
requires. Their new role: cheap, ~10-second-cadence relative monitoring
that a live session (`engine_runtime._EngineSession`) uses to decide *when*
to spend the cost of a fresh RTT-bounded batch (session start; a bounded
periodic cadence; immediately after a detected reconnect; immediately
after the one-way monitor itself detects a jump) -- see this module's own
`detect_clock_jump`/`compute_drift`, now typed against a small structural
`_CalibrationSample` protocol so the *same* functions apply to either
calibration method's own record type without duplicating jump/drift
arithmetic twice.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal, Protocol, Sequence

CLOCK_CALIBRATION_VERSION = "clock-calibration-v1"
RTT_CLOCK_CALIBRATION_VERSION = "rtt-clock-calibration-v1"

CalibrationState = Literal["calibrated", "insufficient_samples"]

# Disclosed judgment calls -- see this module's own docstring "Session/
# stream scope, drift, and clock jumps" for the reasoning behind both.
MINIMUM_CALIBRATION_SAMPLES = 5
DEFAULT_CLOCK_JUMP_THRESHOLD_MS = 5_000.0

# Disclosed engineering sanity bounds for RTT-bounded calibration -- see
# this module's own docstring "Camera Node -> Host RTT-Bounded Clock
# Calibration v1". Deliberately conservative judgment calls, not release
# budgets (this milestone's own explicit "document them as engineering
# bounds; do not call them release budgets"):
#
# - `MINIMUM_RTT_CALIBRATION_SAMPLES` (3): the governing brief's own
#   "small bounded batch, for example 3-7 samples" lower bound -- fewer
#   than this is not enough to make the overlap-intersection check (see
#   "Multi-sample selection") meaningful at all.
# - `DEFAULT_MAX_ACCEPTABLE_RTT_MS` (1000ms): every real deployment is
#   LAN-local (product-doctrine.md; this milestone's own explicit "Local
#   Only" requirement) -- an ordinary LAN round trip to a Raspberry Pi
#   Camera Node is expected in the single-digit milliseconds. 1 second is
#   generously wide of that (comfortably absorbing real-world scheduling
#   jitter/GC pauses on a Pi) while still rejecting a genuinely wedged
#   Node, saturated Wi-Fi, or a request that silently traversed a slow
#   path -- an engineering ceiling to reject the obviously unusable, not a
#   tuned precision threshold. If exact limits ever need sharpening from
#   real field evidence, that is future work, not a claim made here.
MINIMUM_RTT_CALIBRATION_SAMPLES = 3
DEFAULT_MAX_ACCEPTABLE_RTT_MS = 1_000.0


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


class _CalibrationSample(Protocol):
    """Structural type satisfied by both `ClockCalibrationRecord` (one-way)
    and `RttClockCalibrationRecord` (RTT-bounded, below) -- `detect_clock_
    jump`/`compute_drift` operate on either calibration method's own record
    type without duplicating jump/drift arithmetic twice (see this module's
    own docstring "Composing with the one-way per-frame monitor")."""

    state: str
    offset_ms: float | None
    calibrated_at: datetime


def detect_clock_jump(
    previous: _CalibrationSample,
    current: _CalibrationSample,
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


def compute_drift(previous: _CalibrationSample, current: _CalibrationSample) -> DriftObservation | None:
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


class _EpochItem(Protocol):
    """Structural type shared by `ClockCalibrationRecord`/
    `RttClockCalibrationRecord` for `_select_governing_calibration`, below
    -- the epoch/jump-boundary selection model itself never needs to know
    which estimation method produced a record, only its offset-anchor,
    validity, and jump flag."""

    source_offset_ms: int
    state: str
    clock_jump_detected: bool


def _select_governing_calibration(items: Sequence[_EpochItem], *, source_offset_ms: int) -> _EpochItem | None:
    """The generic epoch-selection algorithm behind both `active_
    calibration_for_offset` and `active_rtt_calibration_for_offset` --
    identical logic, parameterized over which calibration method's own
    record type it is applied to (see `active_calibration_for_offset`'s own
    docstring for the full "epoch" model this implements)."""

    calibrated = sorted(
        (item for item in items if item.state == "calibrated"), key=lambda item: item.source_offset_ms,
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
    `None`, not an extrapolated guess (see this module's own docstring).

    Note (Camera Node <-> Host RTT-Bounded Clock Calibration v1): this
    one-way history is no longer consulted by `capture_to_visible_
    latency.py` for T0 normalization -- see this module's own docstring
    "Composing with the one-way per-frame monitor". It remains available
    for relative drift/jump monitoring and is otherwise unchanged."""

    return _select_governing_calibration(calibrations, source_offset_ms=source_offset_ms)


def active_rtt_calibration_for_offset(
    calibrations: Sequence["RttClockCalibrationRecord"],
    *,
    source_offset_ms: int,
) -> "RttClockCalibrationRecord | None":
    """The RTT-bounded anchor that governs `source_offset_ms` -- identical
    epoch/jump-boundary model to `active_calibration_for_offset`, applied to
    the bounded-absolute-anchor history instead of the one-way per-tick
    history. This is the function `capture_to_visible_latency.py` actually
    calls (via `normalize_capture_time_with_bound`) for T0 normalization."""

    return _select_governing_calibration(calibrations, source_offset_ms=source_offset_ms)


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


RttCalibrationState = Literal["calibrated", "insufficient_samples", "inconsistent_samples"]


@dataclass(frozen=True)
class RttRoundTrip:
    """One bracketed request/response measurement against an existing
    Camera Node round-trip-capable operation (`GET /node/v1/health` today
    -- see this module's own docstring "Camera Node <-> Host RTT-Bounded
    Clock Calibration v1"). Plain data only; the actual HTTP call lives in
    `source_providers.camera_node.CameraNodeClient.sample_clock_round_trip`,
    which constructs one of these per attempt -- this module never performs
    network I/O itself (see this module's own docstring "Pure").

    `host_send_at`/`host_receive_at` (H0/H1) are Host-clock reads,
    immediately around dispatch/receipt -- always required, always
    tz-aware by construction (the Host's own canonical clock). `node_
    response_at` (Nsend/N1) is the Node's own wall-clock reading, sampled
    immediately before its response was returned; `None` when an old
    Node's response predates this milestone (see "Old Node compatibility").
    `node_receive_at` (Nrecv) is the Node's own wall-clock reading at the
    top of its handler, before any processing -- optional; when absent
    (two-timestamp form) `node_response_at` stands in for it, and the
    bound widens to plain `RTT`/`RTT/2` (see "The interval bound")."""

    host_send_at: datetime
    host_receive_at: datetime
    node_response_at: datetime | None
    node_receive_at: datetime | None = None


def _round_trip_bound(sample: RttRoundTrip) -> tuple[float, float, float, float | None] | None:
    """`(offset_min_ms, offset_max_ms, rtt_ms, node_processing_ms)` derived
    from one bracketed round trip via the inequality argument in this
    module's own docstring "The interval bound" -- or `None` when the
    sample is structurally unusable: a missing `node_response_at` (old
    Node), a non-tz-aware Node timestamp (malformed response -- Host
    timestamps are trusted by construction and raise instead, matching
    `estimate_clock_calibration`'s own precedent), a response that
    measured before it was sent (`rtt_ms < 0`), or a Node-reported
    processing interval that exceeds the measured RTT itself (impossible
    under a correct clock -- see this module's own docstring "Old Node
    compatibility" for why this degrades rather than raises: an external
    Node's own bad data, never a caller bug)."""

    if sample.host_send_at.tzinfo is None or sample.host_receive_at.tzinfo is None:
        raise ValueError("invalid_rtt_calibration_timestamp")
    if sample.node_response_at is None:
        return None
    if sample.node_response_at.tzinfo is None:
        return None
    node_receive_at = sample.node_receive_at if sample.node_receive_at is not None else sample.node_response_at
    if node_receive_at.tzinfo is None:
        return None
    rtt_ms = (sample.host_receive_at - sample.host_send_at).total_seconds() * 1000.0
    if rtt_ms < 0:
        return None
    node_processing_ms = (
        (sample.node_response_at - node_receive_at).total_seconds() * 1000.0
        if sample.node_receive_at is not None else None
    )
    if node_processing_ms is not None and node_processing_ms < 0:
        return None
    offset_min_ms = (sample.host_send_at - node_receive_at).total_seconds() * 1000.0
    offset_max_ms = (sample.host_receive_at - sample.node_response_at).total_seconds() * 1000.0
    if offset_min_ms > offset_max_ms:
        # Impossible under a correct clock (this milestone's own explicit
        # §22 "impossible result policy") -- never clamp, never silently
        # pick an endpoint; the whole sample is unusable.
        return None
    return offset_min_ms, offset_max_ms, rtt_ms, node_processing_ms


@dataclass(frozen=True)
class RttClockCalibrationRecord:
    """One RTT-bounded calibration batch for one stream, anchored to the
    same Node-session-relative `source_offset_ms` coordinate `Clock
    CalibrationRecord` already keys off (see that class's own docstring --
    identical reasoning applies here). The defensible absolute anchor (see
    this module's own docstring): unlike the one-way estimator, `offset_
    min_ms`/`offset_max_ms` are a rigorously justified two-sided bound, not
    a one-sided upper bound with a fuzzy quality signal.

    `offset_ms` is the interval's own midpoint, reported for convenience
    and never represented as exact -- a consumer that needs the honest
    bound must read `offset_min_ms`/`offset_max_ms` (this milestone's own
    explicit "the midpoint estimate is not exact"). `uncertainty_ms` is the
    interval's own half-width (radius) -- at least `RTT/2` in the
    two-timestamp form, tighter when `node_processing_ms` narrows it (see
    "The interval bound").

    `state="insufficient_samples"` (too few valid, low-enough-RTT samples
    survived) and `state="inconsistent_samples"` (enough survived, but
    their own intervals do not overlap -- see "Multi-sample selection") are
    both real, auditable outcomes -- never silently dropped, never a
    fabricated number. `rtt_ms`/`node_processing_ms` describe the single
    lowest-RTT sample actually used to anchor the combined interval (the
    calibration's own "best sample," per this milestone's own explicit
    reporting requirement), not an average across the batch."""

    stream_id: str
    source_offset_ms: int
    calibrated_at: datetime
    sample_count: int
    valid_sample_count: int
    state: RttCalibrationState
    offset_ms: float | None = None
    offset_min_ms: float | None = None
    offset_max_ms: float | None = None
    uncertainty_ms: float | None = None
    rtt_ms: float | None = None
    node_processing_ms: float | None = None
    clock_jump_detected: bool = False

    def __post_init__(self) -> None:
        if not self.stream_id:
            raise ValueError("invalid_rtt_calibration_stream")
        if self.calibrated_at.tzinfo is None:
            raise ValueError("invalid_rtt_calibration_timestamp")
        if self.sample_count < 0 or self.valid_sample_count < 0 or self.valid_sample_count > self.sample_count:
            raise ValueError("invalid_rtt_calibration_sample_count")
        if self.state == "calibrated" and (
            self.offset_ms is None
            or self.offset_min_ms is None
            or self.offset_max_ms is None
            or self.uncertainty_ms is None
            or self.rtt_ms is None
        ):
            raise ValueError("invalid_rtt_calibration_state")


def estimate_rtt_clock_calibration(
    samples: Sequence[RttRoundTrip],
    *,
    stream_id: str,
    source_offset_ms: int,
    calibrated_at: datetime,
    minimum_samples: int = MINIMUM_RTT_CALIBRATION_SAMPLES,
    max_acceptable_rtt_ms: float = DEFAULT_MAX_ACCEPTABLE_RTT_MS,
) -> RttClockCalibrationRecord:
    """One RTT-bounded calibration attempt from a small bounded batch of
    `RttRoundTrip` samples -- see this module's own docstring "Multi-sample
    selection" for the exact combination rule (interval intersection over
    the RTT-filtered survivors; lowest-RTT sample reported for diagnostics)
    and "Old Node compatibility" for how a missing/malformed sample
    degrades. Never raises for a structurally invalid *batch* (too few
    samples, non-overlapping intervals) -- both are real, auditable states,
    not errors; only a naive Host timestamp raises (a caller bug, not an
    external-data problem -- see `_round_trip_bound`)."""

    if calibrated_at.tzinfo is None:
        raise ValueError("invalid_rtt_calibration_timestamp")
    bounds = [
        resolved
        for sample in samples
        if (resolved := _round_trip_bound(sample)) is not None and resolved[2] <= max_acceptable_rtt_ms
    ]
    if len(bounds) < minimum_samples:
        return RttClockCalibrationRecord(
            stream_id=stream_id, source_offset_ms=source_offset_ms, calibrated_at=calibrated_at,
            sample_count=len(samples), valid_sample_count=len(bounds), state="insufficient_samples",
        )
    combined_min = max(bound[0] for bound in bounds)
    combined_max = min(bound[1] for bound in bounds)
    if combined_min > combined_max:
        return RttClockCalibrationRecord(
            stream_id=stream_id, source_offset_ms=source_offset_ms, calibrated_at=calibrated_at,
            sample_count=len(samples), valid_sample_count=len(bounds), state="inconsistent_samples",
        )
    best = min(bounds, key=lambda bound: bound[2])
    return RttClockCalibrationRecord(
        stream_id=stream_id, source_offset_ms=source_offset_ms, calibrated_at=calibrated_at,
        sample_count=len(samples), valid_sample_count=len(bounds), state="calibrated",
        offset_ms=(combined_min + combined_max) / 2.0,
        offset_min_ms=combined_min, offset_max_ms=combined_max,
        uncertainty_ms=(combined_max - combined_min) / 2.0,
        rtt_ms=best[2], node_processing_ms=best[3],
    )


@dataclass(frozen=True)
class RttNormalizedCapture:
    """The result of mapping one Node-domain capture time into the Host
    -compatible domain via an RTT-bounded anchor -- the interval-aware
    counterpart to `NormalizedCapture`. `state="no_calibration"` means
    exactly that -- never a value computed from a stale, jumped, or
    nonexistent anchor; every field beyond `node_captured_at` stays `None`
    in that case."""

    node_captured_at: datetime
    host_domain_captured_at_estimate: datetime | None
    host_domain_captured_at_min: datetime | None
    host_domain_captured_at_max: datetime | None
    offset_estimate_ms: float | None
    offset_min_ms: float | None
    offset_max_ms: float | None
    uncertainty_ms: float | None
    state: NormalizedCaptureState
    calibration_source_offset_ms: int | None = None


def normalize_capture_time_with_bound(
    node_captured_at: datetime,
    calibrations: Sequence[RttClockCalibrationRecord],
    *,
    source_offset_ms: int,
) -> RttNormalizedCapture:
    """`node_captured_at + calibration.offset_{min,estimate,max}_ms`, using
    whichever RTT-bounded anchor `active_rtt_calibration_for_offset` finds
    safe for `source_offset_ms` -- `state="no_calibration"` (never a raw,
    unnormalized fallback, and never the one-way calibration as a silent
    substitute) when none is."""

    calibration = active_rtt_calibration_for_offset(calibrations, source_offset_ms=source_offset_ms)
    if calibration is None:
        return RttNormalizedCapture(
            node_captured_at=node_captured_at, host_domain_captured_at_estimate=None,
            host_domain_captured_at_min=None, host_domain_captured_at_max=None,
            offset_estimate_ms=None, offset_min_ms=None, offset_max_ms=None, uncertainty_ms=None,
            state="no_calibration",
        )
    assert calibration.offset_ms is not None
    assert calibration.offset_min_ms is not None
    assert calibration.offset_max_ms is not None
    return RttNormalizedCapture(
        node_captured_at=node_captured_at,
        host_domain_captured_at_estimate=node_captured_at + timedelta(milliseconds=calibration.offset_ms),
        host_domain_captured_at_min=node_captured_at + timedelta(milliseconds=calibration.offset_min_ms),
        host_domain_captured_at_max=node_captured_at + timedelta(milliseconds=calibration.offset_max_ms),
        offset_estimate_ms=calibration.offset_ms, offset_min_ms=calibration.offset_min_ms,
        offset_max_ms=calibration.offset_max_ms, uncertainty_ms=calibration.uncertainty_ms,
        state="normalized", calibration_source_offset_ms=calibration.source_offset_ms,
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
    "RTT_CLOCK_CALIBRATION_VERSION",
    "MINIMUM_RTT_CALIBRATION_SAMPLES",
    "DEFAULT_MAX_ACCEPTABLE_RTT_MS",
    "RttCalibrationState",
    "RttRoundTrip",
    "RttClockCalibrationRecord",
    "estimate_rtt_clock_calibration",
    "active_rtt_calibration_for_offset",
    "RttNormalizedCapture",
    "normalize_capture_time_with_bound",
]
