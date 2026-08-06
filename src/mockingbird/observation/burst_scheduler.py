"""Provider-neutral, bounded, recurrence-aware evidence burst scheduler.

Observation Engine v2 Stage 6.9. This module is pure: no GPU-accelerated
inference runtime, no vendor camera SDK, no camera-provider or
transport-library type, and no filesystem access anywhere in its contract,
and no product-repository import. It holds only bounded, temporary,
session-scoped in-memory state and never opens a product database.

Three concepts stay separate (see docs/burst-scheduler-contract.md):

- **Burst opportunity** (`BurstOpportunity`): a detector/track/operator event
  indicating that high-resolution evidence could be useful. Produced upstream
  by the existing tracker and live-shadow path; carries no authority.
- **Burst scheduler decision** (`BurstDecision`): `BurstScheduler.decide()` is
  the only place that decides whether to issue, suppress, defer, reject, or
  override a burst attempt.
- **Burst result**: reported back through `record_result()`; the scheduler
  never performs a capture itself and never decodes an image.

A new track generation is not, by itself, sufficient to guarantee a fresh
burst: recurring static geometry re-detected as a brand-new short-lived
generation is exactly the pattern this stage suppresses, while a genuinely
new or changed subject still gets a burst through recurrence grouping and
novelty rules. Every semantic decision uses source/session-relative time
(`BurstOpportunity.time_reference_ms`); wall-clock time never enters
`decide()`. This module never creates or mutates any reviewed, product, or
monitoring-policy record of any kind, and it never alters detector, tracker,
or shadow-proposal output -- it only decides whether to *attempt* a burst.
"""
from __future__ import annotations

from collections import OrderedDict, deque
from dataclasses import dataclass
import hashlib
import json
from typing import NamedTuple

SCHEDULER_VERSION = "burst-scheduler-v1"

# --------------------------------------------------------------------------
# Stable decision outcomes
# --------------------------------------------------------------------------

DECISION_BURST_ISSUED = "burst_issued"
DECISION_SUPPRESSED_SAME_TRACK_GENERATION = "suppressed_same_track_generation"
DECISION_SUPPRESSED_RECURRING_GEOMETRY = "suppressed_recurring_geometry"
DECISION_SUPPRESSED_ACTIVE_REQUEST = "suppressed_active_request"
DECISION_SUPPRESSED_SESSION_BUDGET = "suppressed_session_budget"
DECISION_SUPPRESSED_RATE_BUDGET = "suppressed_rate_budget"
DECISION_DEFERRED_COOLDOWN = "deferred_cooldown"
DECISION_OPERATOR_OVERRIDE_ISSUED = "operator_override_issued"
DECISION_ENGINEERING_OVERRIDE_ISSUED = "engineering_override_issued"
DECISION_RETRY_ISSUED = "retry_issued"
DECISION_BURST_UNAVAILABLE = "burst_unavailable"

SCHEDULER_DECISIONS: tuple[str, ...] = (
    DECISION_BURST_ISSUED,
    DECISION_SUPPRESSED_SAME_TRACK_GENERATION,
    DECISION_SUPPRESSED_RECURRING_GEOMETRY,
    DECISION_SUPPRESSED_ACTIVE_REQUEST,
    DECISION_SUPPRESSED_SESSION_BUDGET,
    DECISION_SUPPRESSED_RATE_BUDGET,
    DECISION_DEFERRED_COOLDOWN,
    DECISION_OPERATOR_OVERRIDE_ISSUED,
    DECISION_ENGINEERING_OVERRIDE_ISSUED,
    DECISION_RETRY_ISSUED,
    DECISION_BURST_UNAVAILABLE,
)

# Outcomes for which a caller must actually attempt the burst.
ISSUING_DECISIONS = frozenset((
    DECISION_BURST_ISSUED,
    DECISION_OPERATOR_OVERRIDE_ISSUED,
    DECISION_ENGINEERING_OVERRIDE_ISSUED,
    DECISION_RETRY_ISSUED,
))

# --------------------------------------------------------------------------
# Stable novelty signal codes
# --------------------------------------------------------------------------

NOVELTY_STRONGER_CONFIDENCE = "stronger_confidence"
NOVELTY_MOTION_CHANGE = "motion_change_evidence"
NOVELTY_TIME_GAP = "source_relative_time_gap"
NOVELTY_OPERATOR_MARKER = "operator_wildlife_marker"
NOVELTY_ENGINEERING_REQUEST = "engineering_validation_request"
NOVELTY_RETRY_PERMITTED = "bounded_retry_permitted"
NOVELTY_BETTER_TEMPORAL_SUPPORT = "stronger_temporal_support"

NOVELTY_SIGNALS: tuple[str, ...] = (
    NOVELTY_STRONGER_CONFIDENCE,
    NOVELTY_MOTION_CHANGE,
    NOVELTY_TIME_GAP,
    NOVELTY_OPERATOR_MARKER,
    NOVELTY_ENGINEERING_REQUEST,
    NOVELTY_RETRY_PERMITTED,
    NOVELTY_BETTER_TEMPORAL_SUPPORT,
)

# --------------------------------------------------------------------------
# Stable reset reasons
# --------------------------------------------------------------------------

RESET_SESSION_STOP = "session_stop"
RESET_PROVIDER_RESET = "provider_reset"
RESET_GENERATION_REPLACEMENT = "camera_node_generation_replacement"
RESET_ENGINEERING_RESET = "engineering_reset"

RESET_REASONS: tuple[str, ...] = (
    RESET_SESSION_STOP, RESET_PROVIDER_RESET, RESET_GENERATION_REPLACEMENT, RESET_ENGINEERING_RESET,
)

_BURST_RESULT_STATUSES = ("captured", "failed", "stale")


class BurstSchedulerError(ValueError):
    """A bounded burst-scheduler validation or execution failure code."""


# --------------------------------------------------------------------------
# Geometry helpers (self-contained; mirrors the IoU/centroid convention
# already established by detector_benchmark.cluster_static_false_positives
# and temporal_capture.RecurringGeometryTracker).
# --------------------------------------------------------------------------


def _valid_box(box: tuple[float, float, float, float]) -> bool:
    return (
        len(box) == 4
        and all(isinstance(value, (int, float)) and not isinstance(value, bool) for value in box)
        and all(0.0 <= float(value) <= 1.0 for value in box)
        and box[0] < box[2]
        and box[1] < box[3]
    )


def _box_area(box: tuple[float, float, float, float]) -> float:
    left, top, right, bottom = box
    return max(0.0, right - left) * max(0.0, bottom - top)


def _iou(first: tuple[float, float, float, float], second: tuple[float, float, float, float]) -> float:
    left, top = max(first[0], second[0]), max(first[1], second[1])
    right, bottom = min(first[2], second[2]), min(first[3], second[3])
    intersection = max(0.0, right - left) * max(0.0, bottom - top)
    union = _box_area(first) + _box_area(second) - intersection
    return 0.0 if union <= 0.0 else intersection / union


def _centroid(box: tuple[float, float, float, float]) -> tuple[float, float]:
    return ((box[0] + box[2]) / 2.0, (box[1] + box[3]) / 2.0)


def _centroid_distance(first: tuple[float, float, float, float], second: tuple[float, float, float, float]) -> float:
    fx, fy = _centroid(first)
    sx, sy = _centroid(second)
    return ((fx - sx) ** 2 + (fy - sy) ** 2) ** 0.5


def _size_ratio_within(area_a: float, area_b: float, threshold: float) -> bool:
    if area_a <= 0.0 or area_b <= 0.0:
        return False
    ratio = min(area_a, area_b) / max(area_a, area_b)
    return ratio >= (1.0 - threshold)


def _fingerprint(value: object) -> str:
    """A local, dependency-free equivalent of replay.semantic_fingerprint --
    deliberately not imported, so this module stays independent of every
    other Observation Engine module and introduces no import coupling."""

    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(encoded).hexdigest()


def _median(values: list[int]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return float(ordered[middle])
    return (ordered[middle - 1] + ordered[middle]) / 2.0


def _sanitize_failure_code(value: str | None) -> str | None:
    if not value:
        return None
    trimmed = "".join(ch for ch in value[:80] if ch.isalnum() or ch == "_")
    return trimmed or None


# --------------------------------------------------------------------------
# Burst opportunity contract
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class BurstOpportunity:
    """Bounded, provider-neutral facts describing one moment a burst could be
    useful. No accelerator, camera-provider, or transport-library object can
    enter this type -- enforced by a structural source-grep test."""

    opportunity_id: str
    stream_id: str
    session_id: str
    track_generation_id: str
    trigger_frame_id: str
    source_offset_ms: int
    broad_class: str
    node_session_id: str | None = None
    provider_generation: str | None = None
    connection_segment_id: str | None = None
    session_sequence: int | None = None
    session_offset_ms: int | None = None
    subject_geometry: tuple[float, float, float, float] | None = None
    detector_score: float | None = None
    detector_confirmation_count: int = 0
    tracker_support_count: int = 0
    # Bounded 0..1 normalized change/novelty signal; `None` when unavailable.
    # This stage does not define how the signal is computed -- it only
    # consumes an already-produced, bounded value (for example an adaptive
    # motion-proposal score) exactly as it consumes detector_score.
    motion_change_score: float | None = None
    operator_marker_present: bool = False
    trigger_reason: str = "detector_track_update"
    requested_evidence_profile: str = ""
    shadow_only: bool = True
    engineering_validation_request: bool = False
    estimated_burst_bytes: int | None = None

    def __post_init__(self) -> None:
        if not self.opportunity_id or len(self.opportunity_id) > 200:
            raise BurstSchedulerError("invalid_opportunity_id")
        if not self.stream_id or not self.session_id or not self.track_generation_id or not self.trigger_frame_id:
            raise BurstSchedulerError("invalid_opportunity_identity")
        if not self.broad_class or len(self.broad_class) > 64:
            raise BurstSchedulerError("invalid_opportunity_broad_class")
        if self.source_offset_ms < 0:
            raise BurstSchedulerError("invalid_opportunity_offset")
        if self.session_offset_ms is not None and self.session_offset_ms < 0:
            raise BurstSchedulerError("invalid_opportunity_offset")
        if self.session_sequence is not None and self.session_sequence < 0:
            raise BurstSchedulerError("invalid_opportunity_sequence")
        if self.subject_geometry is not None and not _valid_box(self.subject_geometry):
            raise BurstSchedulerError("invalid_opportunity_geometry")
        if self.detector_score is not None and not 0.0 <= self.detector_score <= 1.0:
            raise BurstSchedulerError("invalid_opportunity_score")
        if self.detector_confirmation_count < 0 or self.tracker_support_count < 0:
            raise BurstSchedulerError("invalid_opportunity_support")
        if self.motion_change_score is not None and not 0.0 <= self.motion_change_score <= 1.0:
            raise BurstSchedulerError("invalid_opportunity_motion_score")
        if not self.trigger_reason or len(self.trigger_reason) > 80:
            raise BurstSchedulerError("invalid_opportunity_trigger_reason")
        if len(self.requested_evidence_profile) > 120:
            raise BurstSchedulerError("invalid_opportunity_evidence_profile")
        if not self.shadow_only:
            raise BurstSchedulerError("invalid_opportunity_shadow_only")
        if self.estimated_burst_bytes is not None and not 0 < self.estimated_burst_bytes <= 50_000_000:
            raise BurstSchedulerError("invalid_opportunity_byte_estimate")

    @property
    def time_reference_ms(self) -> int:
        """Prefer the reconnect-safe session-relative coordinate; fall back
        to the bare source-relative offset when no session timeline has been
        attached (a pre-upgrade capture, or a synthetic/unit-test fixture)."""

        return self.session_offset_ms if self.session_offset_ms is not None else self.source_offset_ms


# --------------------------------------------------------------------------
# Bounded configuration
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class BurstSchedulerConfig:
    minimum_burst_interval_ms: int = 1_000
    # A recurring static structure is often visible on a large share of
    # analysis frames (session-02: recurring geometry on ~71% of retained
    # frames), so a short cooldown lets it re-escape via source_relative_
    # time_gap every single window, all session long -- see
    # docs/burst-scheduler-contract.md's real-session tuning note. One
    # minute meaningfully bounds "the same static thing" to at most one
    # fresh burst per minute of session time.
    recurrence_group_cooldown_ms: int = 60_000
    recurrence_group_expiry_ms: int = 120_000
    min_recurrence_to_suppress: int = 2
    # A real, busy multi-structure scene can legitimately produce several
    # simultaneous "first sighting of a new recurrence group" issuances
    # within the first few seconds of a session; a tight per-minute cap
    # (this was originally 6) starves out every later genuine opportunity
    # for the rest of that rolling window regardless of novelty. 30/minute
    # remains a real, bounded safety ceiling against pathological detector
    # noise while not fighting the recurrence-group mechanism that does the
    # actual reduction work.
    max_bursts_per_minute: int = 30
    rate_window_ms: int = 60_000
    max_bursts_per_session: int = 50
    operator_override_reserved_bursts: int = 6
    max_concurrent_requests: int = 1
    max_retries_per_opportunity: int = 1
    max_decision_history: int = 256
    max_recurrence_groups: int = 64
    max_tracked_generations: int = 512
    geometry_iou_threshold: float = 0.3
    geometry_centroid_threshold: float = 0.05
    size_change_ratio_threshold: float = 0.35
    stronger_confidence_delta: float = 0.15
    motion_change_threshold: float = 0.15
    temporal_support_delta: int = 2
    default_estimated_burst_bytes: int = 1_000_000

    def __post_init__(self) -> None:
        bounds = (
            (self.minimum_burst_interval_ms, 0, 300_000),
            (self.recurrence_group_cooldown_ms, 0, 600_000),
            (self.recurrence_group_expiry_ms, 1_000, 3_600_000),
            (self.min_recurrence_to_suppress, 1, 100),
            (self.max_bursts_per_minute, 1, 1_000),
            (self.rate_window_ms, 1_000, 600_000),
            (self.max_bursts_per_session, 1, 10_000),
            (self.operator_override_reserved_bursts, 0, 1_000),
            (self.max_concurrent_requests, 1, 10_000),
            (self.max_retries_per_opportunity, 0, 10),
            (self.max_decision_history, 1, 5_000),
            (self.max_recurrence_groups, 1, 1_000),
            (self.max_tracked_generations, 1, 10_000),
            (self.temporal_support_delta, 0, 1_000),
            (self.default_estimated_burst_bytes, 1, 50_000_000),
        )
        if any(not (lo <= value <= hi) for value, lo, hi in bounds):
            raise BurstSchedulerError("invalid_burst_scheduler_config")
        ratios = (
            self.geometry_iou_threshold, self.geometry_centroid_threshold, self.size_change_ratio_threshold,
            self.stronger_confidence_delta, self.motion_change_threshold,
        )
        if any(not 0.0 <= value <= 1.0 for value in ratios):
            raise BurstSchedulerError("invalid_burst_scheduler_config")
        # No cross-field cooldown/expiry ordering constraint: `decide()`
        # always purges an expired group before ever evaluating its
        # cooldown, so a cooldown configured longer than expiry is merely
        # inert for that group once expired, not unsafe or contradictory.


# --------------------------------------------------------------------------
# Decision, group, diagnostics, and health contracts
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class BurstDecision:
    """Enough provenance to explain why a burst was or was not issued
    without re-deriving it. `shadow_only` is always True; this type never
    carries a truth-write flag of any kind (structurally enforced by tests:
    it declares no such field)."""

    request_id: str
    opportunity_id: str
    outcome: str
    should_issue: bool
    recurrence_group_id: str | None
    novelty_signals: tuple[str, ...]
    track_generation_id: str
    stream_id: str
    provider_generation: str | None
    time_reference_ms: int
    decision_sequence: int
    is_override: bool = False
    is_retry: bool = False
    shadow_only: bool = True


@dataclass(frozen=True)
class RecurrenceGroupSnapshot:
    group_id: str
    broad_class: str
    stream_id: str
    provider_generation: str | None
    representative_geometry: tuple[float, float, float, float]
    occurrence_count: int
    issued_count: int
    suppressed_count: int
    first_seen_offset_ms: int
    last_seen_offset_ms: int
    last_issued_offset_ms: int | None


@dataclass(frozen=True)
class BurstSchedulerDiagnostics:
    opportunity_count: int
    issued_count: int
    suppressed_count: int
    suppression_reason_distribution: tuple[tuple[str, int], ...]
    recurrence_group_count: int
    operator_overrides: int
    engineering_overrides: int
    successful_bursts: int
    failed_bursts: int
    stale_bursts: int
    median_burst_latency_ms: float | None
    estimated_bytes_avoided: int
    evidence_candidates_retained: int
    subjects_suppressed_without_burst: int
    limitations: tuple[str, ...]


@dataclass(frozen=True)
class BurstSchedulerHealth:
    state: str
    active_requests: int
    recent_burst_rate_per_minute: float
    session_budget_remaining: int
    recurrence_groups_active: int
    suppression_counters: tuple[tuple[str, int], ...]
    degraded: bool
    burst_capability_available: bool
    last_sanitized_failure: str | None


# --------------------------------------------------------------------------
# Internal bounded state
# --------------------------------------------------------------------------


class _GenerationState:
    __slots__ = ("last_issue_offset_ms", "active_request_id", "retry_attempts_used", "retry_eligible", "ever_issued", "ever_suppressed")

    def __init__(self) -> None:
        self.last_issue_offset_ms: int | None = None
        self.active_request_id: str | None = None
        self.retry_attempts_used: int = 0
        self.retry_eligible: bool = False
        self.ever_issued: bool = False
        self.ever_suppressed: bool = False


@dataclass
class _RecurrenceGroup:
    group_id: str
    broad_class: str
    stream_id: str
    provider_generation: str | None
    representative_box: tuple[float, float, float, float]
    representative_area: float
    occurrence_count: int = 0
    issued_count: int = 0
    suppressed_count: int = 0
    first_seen_offset_ms: int = 0
    last_seen_offset_ms: int = 0
    last_issued_offset_ms: int | None = None
    # The group's own historic *minimum* observed score/support -- its noise
    # floor -- updated from every occurrence (issued or suppressed), never
    # just the most recent issuance. Comparing a new opportunity against this
    # floor is order-independent: two genuine sightings close together both
    # read as clearly stronger than recurring static clutter, whereas
    # comparing only against "whatever last happened to issue" can under-
    # count novelty when an earlier, weaker novelty-driven issuance already
    # raised that single reference point.
    score_floor: float | None = None
    support_floor: int | None = None


class _ActiveRequest(NamedTuple):
    track_generation_id: str
    recurrence_group_id: str | None
    issued_offset_ms: int


# --------------------------------------------------------------------------
# Scheduler
# --------------------------------------------------------------------------


class BurstScheduler:
    """Bounded, session-scoped, advisory burst-scheduling decision engine.

    One instance owns state for one shadow capture session. Every field is
    reset to a fresh, empty state by `reset()`. No durable product state is
    ever held; `decide()`/`record_result()` are the only mutators, and every
    read (`diagnostics`, `health`, `recurrence_groups`, `decision_history`)
    is a pure snapshot that starts nothing.
    """

    def __init__(self, *, session_id: str, config: BurstSchedulerConfig | None = None) -> None:
        if not session_id:
            raise BurstSchedulerError("invalid_scheduler_session_id")
        self.session_id = session_id
        self.config = config or BurstSchedulerConfig()
        self._groups: "OrderedDict[str, _RecurrenceGroup]" = OrderedDict()
        self._generations: "OrderedDict[str, _GenerationState]" = OrderedDict()
        self._active_requests: dict[str, _ActiveRequest] = {}
        self._history: deque[BurstDecision] = deque(maxlen=self.config.max_decision_history)
        self._rate_window: deque[int] = deque(maxlen=4096)
        self._observed_byte_sizes: deque[int] = deque(maxlen=32)
        self._latencies_ms: deque[int] = deque(maxlen=128)
        self._suppression_counters: dict[str, int] = {}
        self._call_index = 0
        self._issue_index = 0
        self._issued_count = 0
        self._successful_bursts = 0
        self._failed_bursts = 0
        self._stale_bursts = 0
        self._operator_overrides = 0
        self._engineering_overrides = 0
        self._estimated_bytes_avoided = 0
        self._consecutive_failures = 0
        self._last_sanitized_failure: str | None = None
        self._latest_time_reference_ms: int | None = None
        self._burst_available = True
        self._reset_count = 0
        self._last_reset_reason: str | None = None

    # -- capability -------------------------------------------------------

    def mark_burst_unavailable(self, reason: str) -> None:
        self._burst_available = False
        self._last_sanitized_failure = _sanitize_failure_code(reason) or "burst_capability_unavailable"

    def mark_burst_available(self) -> None:
        self._burst_available = True

    # -- decision -----------------------------------------------------------

    def decide(self, opportunity: BurstOpportunity) -> BurstDecision:
        if not isinstance(opportunity, BurstOpportunity):
            raise BurstSchedulerError("invalid_burst_opportunity")
        now_ms = opportunity.time_reference_ms
        self._latest_time_reference_ms = now_ms
        self._purge_expired_groups(now_ms)
        generation_state = self._generation_state(opportunity.track_generation_id)
        self._call_index += 1

        if not self._burst_available:
            return self._log(opportunity, self._decision(opportunity, DECISION_BURST_UNAVAILABLE, should_issue=False, now_ms=now_ms))

        is_operator = opportunity.operator_marker_present
        is_engineering = opportunity.engineering_validation_request
        is_override = is_operator or is_engineering
        is_retry_eligible = generation_state.retry_eligible and generation_state.retry_attempts_used < self.config.max_retries_per_opportunity

        if generation_state.active_request_id is not None:
            return self._log(opportunity, self._decision(opportunity, DECISION_DEFERRED_COOLDOWN, should_issue=False, now_ms=now_ms))

        if len(self._active_requests) >= self.config.max_concurrent_requests:
            return self._log(opportunity, self._decision(opportunity, DECISION_SUPPRESSED_ACTIVE_REQUEST, should_issue=False, now_ms=now_ms))

        hard_cap = self.config.max_bursts_per_session + (self.config.operator_override_reserved_bursts if is_override else 0)
        if self._issued_count >= hard_cap:
            return self._log(opportunity, self._decision(opportunity, DECISION_SUPPRESSED_SESSION_BUDGET, should_issue=False, now_ms=now_ms))

        if not is_override and self._rate_window_count(now_ms) >= self.config.max_bursts_per_minute:
            return self._log(opportunity, self._decision(opportunity, DECISION_SUPPRESSED_RATE_BUDGET, should_issue=False, now_ms=now_ms))

        if not is_override and not is_retry_eligible and generation_state.last_issue_offset_ms is not None:
            elapsed = now_ms - generation_state.last_issue_offset_ms
            if elapsed < self.config.minimum_burst_interval_ms:
                return self._log(opportunity, self._decision(opportunity, DECISION_SUPPRESSED_SAME_TRACK_GENERATION, should_issue=False, now_ms=now_ms))

        group, is_new_group = self._find_or_create_group(opportunity, now_ms=now_ms)
        novelty: tuple[str, ...] = ()
        recurrence_group_id = group.group_id if group is not None else None
        if is_operator:
            novelty = (NOVELTY_OPERATOR_MARKER,)
        elif is_engineering:
            novelty = (NOVELTY_ENGINEERING_REQUEST,)
        elif is_retry_eligible:
            novelty = (NOVELTY_RETRY_PERMITTED,)
        elif group is not None and not is_new_group:
            suppress, signals = self._evaluate_recurrence(group, opportunity, now_ms=now_ms)
            if suppress:
                group.suppressed_count += 1
                return self._log(opportunity, self._decision(
                    opportunity, DECISION_SUPPRESSED_RECURRING_GEOMETRY, should_issue=False, now_ms=now_ms,
                    recurrence_group_id=recurrence_group_id,
                ))
            novelty = signals

        outcome = (
            DECISION_OPERATOR_OVERRIDE_ISSUED if is_operator else
            DECISION_ENGINEERING_OVERRIDE_ISSUED if is_engineering else
            DECISION_RETRY_ISSUED if is_retry_eligible else
            DECISION_BURST_ISSUED
        )
        self._issue_index += 1
        request_id = "burst-schedule:" + _fingerprint(
            (self.session_id, opportunity.opportunity_id, opportunity.track_generation_id, self._issue_index)
        )[:24]

        generation_state.last_issue_offset_ms = now_ms
        generation_state.active_request_id = request_id
        if is_retry_eligible:
            generation_state.retry_attempts_used += 1
            generation_state.retry_eligible = False
        self._generations.move_to_end(opportunity.track_generation_id)

        self._active_requests[request_id] = _ActiveRequest(opportunity.track_generation_id, recurrence_group_id, now_ms)
        self._issued_count += 1
        self._rate_window.append(now_ms)
        if is_operator:
            self._operator_overrides += 1
        if is_engineering:
            self._engineering_overrides += 1
        if group is not None:
            group.issued_count += 1
            group.last_issued_offset_ms = now_ms

        return self._log(opportunity, self._decision(
            opportunity, outcome, should_issue=True, now_ms=now_ms, recurrence_group_id=recurrence_group_id,
            novelty_signals=novelty, request_id=request_id, is_override=is_override, is_retry=is_retry_eligible,
        ))

    def record_result(
        self, request_id: str, *, status: str, byte_size: int | None = None,
        latency_ms: int | None = None, failure_code: str | None = None,
    ) -> None:
        if status not in _BURST_RESULT_STATUSES:
            raise BurstSchedulerError("invalid_burst_result_status")
        active = self._active_requests.pop(request_id, None)
        if active is None:
            raise BurstSchedulerError("unknown_or_already_resolved_request_id")
        generation_state = self._generations.get(active.track_generation_id)
        if generation_state is not None and generation_state.active_request_id == request_id:
            generation_state.active_request_id = None

        if status == "captured":
            self._successful_bursts += 1
            self._consecutive_failures = 0
            if generation_state is not None:
                generation_state.retry_eligible = False
            if byte_size is not None and byte_size > 0:
                self._observed_byte_sizes.append(byte_size)
            if latency_ms is not None and latency_ms >= 0:
                self._latencies_ms.append(latency_ms)
            return

        if status == "failed":
            self._failed_bursts += 1
            self._consecutive_failures += 1
            if generation_state is not None and generation_state.retry_attempts_used < self.config.max_retries_per_opportunity:
                generation_state.retry_eligible = True
        else:  # stale
            self._stale_bursts += 1
            self._consecutive_failures += 1
        self._last_sanitized_failure = _sanitize_failure_code(failure_code) or ("stale_result" if status == "stale" else "unspecified_failure")

    def reset(self, reason: str) -> None:
        if reason not in RESET_REASONS:
            raise BurstSchedulerError("invalid_reset_reason")
        self._groups.clear()
        self._generations.clear()
        self._active_requests.clear()
        self._history.clear()
        self._rate_window.clear()
        self._observed_byte_sizes.clear()
        self._latencies_ms.clear()
        self._suppression_counters.clear()
        self._call_index = 0
        self._issue_index = 0
        self._issued_count = 0
        self._successful_bursts = 0
        self._failed_bursts = 0
        self._stale_bursts = 0
        self._operator_overrides = 0
        self._engineering_overrides = 0
        self._estimated_bytes_avoided = 0
        self._consecutive_failures = 0
        self._last_sanitized_failure = None
        self._latest_time_reference_ms = None
        self._reset_count += 1
        self._last_reset_reason = reason
        # Burst-capability availability reflects a live external fact (the
        # Camera Node's own evidence-burst capability), not per-session
        # bookkeeping, so it deliberately survives a reset.

    # -- read-only reporting (pure snapshots; start nothing) ---------------

    def diagnostics(self) -> BurstSchedulerDiagnostics:
        limitations = (
            "estimated_bytes_avoided uses an observed running sample of real captured burst sizes "
            "and falls back to a documented default until at least one real sample exists",
            "evidence_candidates_retained is a bounded proxy (one per successful burst); this "
            "scheduler does not itself track downstream evidence-candidate objects",
            "usefulness of an issued or suppressed opportunity is a downstream evidence-scoring "
            "and human-review question this module does not answer",
        )
        return BurstSchedulerDiagnostics(
            opportunity_count=self._call_index,
            issued_count=self._issued_count,
            suppressed_count=self._call_index - self._issued_count,
            suppression_reason_distribution=tuple(sorted(self._suppression_counters.items())),
            recurrence_group_count=len(self._groups),
            operator_overrides=self._operator_overrides,
            engineering_overrides=self._engineering_overrides,
            successful_bursts=self._successful_bursts,
            failed_bursts=self._failed_bursts,
            stale_bursts=self._stale_bursts,
            median_burst_latency_ms=_median(list(self._latencies_ms)),
            estimated_bytes_avoided=self._estimated_bytes_avoided,
            evidence_candidates_retained=self._successful_bursts,
            subjects_suppressed_without_burst=sum(
                1 for state in self._generations.values() if state.ever_suppressed and not state.ever_issued
            ),
            limitations=limitations,
        )

    def health(self) -> BurstSchedulerHealth:
        reference = self._latest_time_reference_ms or 0
        rate_count = self._rate_window_count(reference)
        per_minute = rate_count * (60_000 / self.config.rate_window_ms)
        degraded = self._degraded()
        return BurstSchedulerHealth(
            state="degraded" if degraded else ("running" if self._call_index else "idle"),
            active_requests=len(self._active_requests),
            recent_burst_rate_per_minute=round(per_minute, 3),
            session_budget_remaining=max(0, self.config.max_bursts_per_session - self._issued_count),
            recurrence_groups_active=len(self._groups),
            suppression_counters=tuple(sorted(self._suppression_counters.items())),
            degraded=degraded,
            burst_capability_available=self._burst_available,
            last_sanitized_failure=self._last_sanitized_failure,
        )

    def recurrence_groups(self) -> tuple[RecurrenceGroupSnapshot, ...]:
        return tuple(
            RecurrenceGroupSnapshot(
                group_id=group.group_id, broad_class=group.broad_class, stream_id=group.stream_id,
                provider_generation=group.provider_generation, representative_geometry=group.representative_box,
                occurrence_count=group.occurrence_count, issued_count=group.issued_count,
                suppressed_count=group.suppressed_count, first_seen_offset_ms=group.first_seen_offset_ms,
                last_seen_offset_ms=group.last_seen_offset_ms, last_issued_offset_ms=group.last_issued_offset_ms,
            )
            for group in self._groups.values()
        )

    def decision_history(self) -> tuple[BurstDecision, ...]:
        return tuple(self._history)

    @property
    def active_request_count(self) -> int:
        return len(self._active_requests)

    # -- internal helpers ---------------------------------------------------

    def _degraded(self) -> bool:
        return (not self._burst_available) or self._consecutive_failures >= 3

    def _decision(
        self, opportunity: BurstOpportunity, outcome: str, *, should_issue: bool, now_ms: int,
        recurrence_group_id: str | None = None, novelty_signals: tuple[str, ...] = (), request_id: str = "",
        is_override: bool = False, is_retry: bool = False,
    ) -> BurstDecision:
        return BurstDecision(
            request_id=request_id, opportunity_id=opportunity.opportunity_id, outcome=outcome,
            should_issue=should_issue, recurrence_group_id=recurrence_group_id, novelty_signals=novelty_signals,
            track_generation_id=opportunity.track_generation_id, stream_id=opportunity.stream_id,
            provider_generation=opportunity.provider_generation, time_reference_ms=now_ms,
            decision_sequence=self._call_index, is_override=is_override, is_retry=is_retry,
        )

    def _log(self, opportunity: BurstOpportunity, decision: BurstDecision) -> BurstDecision:
        self._history.append(decision)
        state = self._generations.get(opportunity.track_generation_id)
        if state is not None:
            if decision.should_issue:
                state.ever_issued = True
            else:
                state.ever_suppressed = True
        if not decision.should_issue:
            self._suppression_counters[decision.outcome] = self._suppression_counters.get(decision.outcome, 0) + 1
            self._estimated_bytes_avoided += opportunity.estimated_burst_bytes or self._current_byte_estimate()
        return decision

    def _current_byte_estimate(self) -> int:
        if self._observed_byte_sizes:
            return int(sum(self._observed_byte_sizes) / len(self._observed_byte_sizes))
        return self.config.default_estimated_burst_bytes

    def _generation_state(self, generation_id: str) -> _GenerationState:
        state = self._generations.get(generation_id)
        if state is None:
            state = _GenerationState()
            self._generations[generation_id] = state
        self._generations.move_to_end(generation_id)
        while len(self._generations) > self.config.max_tracked_generations:
            self._generations.popitem(last=False)
        return state

    def _rate_window_count(self, now_ms: int) -> int:
        threshold = now_ms - self.config.rate_window_ms
        while self._rate_window and self._rate_window[0] < threshold:
            self._rate_window.popleft()
        return len(self._rate_window)

    def _purge_expired_groups(self, now_ms: int) -> None:
        expired = [
            group_id for group_id, group in self._groups.items()
            if now_ms - group.last_seen_offset_ms >= self.config.recurrence_group_expiry_ms
        ]
        for group_id in expired:
            del self._groups[group_id]

    def _matches(self, group: _RecurrenceGroup, opportunity: BurstOpportunity, box: tuple[float, float, float, float]) -> bool:
        if group.broad_class != opportunity.broad_class:
            return False
        if group.stream_id != opportunity.stream_id:
            return False
        if group.provider_generation != opportunity.provider_generation:
            return False
        if _iou(box, group.representative_box) < self.config.geometry_iou_threshold:
            return False
        if _centroid_distance(box, group.representative_box) > self.config.geometry_centroid_threshold:
            return False
        if not _size_ratio_within(_box_area(box), group.representative_area, self.config.size_change_ratio_threshold):
            return False
        return True

    def _new_group_id(self, opportunity: BurstOpportunity, box: tuple[float, float, float, float]) -> str:
        payload = (
            self.session_id, opportunity.stream_id, opportunity.provider_generation,
            opportunity.broad_class, [round(value, 3) for value in box],
        )
        return "recurrence:" + _fingerprint(payload)[:16]

    def _find_or_create_group(self, opportunity: BurstOpportunity, *, now_ms: int) -> tuple[_RecurrenceGroup | None, bool]:
        box = opportunity.subject_geometry
        if box is None:
            return None, True
        for group in self._groups.values():
            if self._matches(group, opportunity, box):
                self._touch_group(group, box, opportunity, now_ms=now_ms)
                self._groups.move_to_end(group.group_id)
                return group, False
        if len(self._groups) >= self.config.max_recurrence_groups:
            self._groups.popitem(last=False)
        group = _RecurrenceGroup(
            group_id=self._new_group_id(opportunity, box), broad_class=opportunity.broad_class,
            stream_id=opportunity.stream_id, provider_generation=opportunity.provider_generation,
            representative_box=box, representative_area=_box_area(box),
            first_seen_offset_ms=now_ms, last_seen_offset_ms=now_ms,
        )
        self._touch_group(group, box, opportunity, now_ms=now_ms, is_new=True)
        self._groups[group.group_id] = group
        return group, True

    @staticmethod
    def _touch_group(
        group: _RecurrenceGroup, box: tuple[float, float, float, float], opportunity: BurstOpportunity, *,
        now_ms: int, is_new: bool = False,
    ) -> None:
        if not is_new:
            count = group.occurrence_count
            group.representative_box = tuple(
                round((group.representative_box[index] * count + box[index]) / (count + 1), 6) for index in range(4)
            )  # type: ignore[assignment]
            group.representative_area = _box_area(group.representative_box)
        group.occurrence_count += 1
        group.last_seen_offset_ms = now_ms
        if opportunity.detector_score is not None:
            group.score_floor = opportunity.detector_score if group.score_floor is None else min(group.score_floor, opportunity.detector_score)
        support = opportunity.detector_confirmation_count + opportunity.tracker_support_count
        group.support_floor = support if group.support_floor is None else min(group.support_floor, support)

    def _evaluate_recurrence(
        self, group: _RecurrenceGroup, opportunity: BurstOpportunity, *, now_ms: int,
    ) -> tuple[bool, tuple[str, ...]]:
        """Return (suppress, novelty_signals). A recurrence is suppressed
        only when it has genuinely recurred, a prior burst was actually
        issued for the group, that issue is still within the group's own
        cooldown, and no novelty signal applies. Confidence/support novelty
        compares against the group's own historic *floor* (its established
        noise baseline), not merely its most recent issuance -- otherwise an
        earlier, weaker novelty-driven burst can silently raise the bar for
        the very next genuine sighting moments later."""

        if group.occurrence_count < self.config.min_recurrence_to_suppress:
            return False, ()
        if group.last_issued_offset_ms is None:
            return False, ()
        elapsed = now_ms - group.last_issued_offset_ms
        if elapsed >= self.config.recurrence_group_cooldown_ms:
            return False, (NOVELTY_TIME_GAP,)
        signals: list[str] = []
        if (
            opportunity.detector_score is not None and group.score_floor is not None
            and opportunity.detector_score - group.score_floor >= self.config.stronger_confidence_delta
        ):
            signals.append(NOVELTY_STRONGER_CONFIDENCE)
        if opportunity.motion_change_score is not None and opportunity.motion_change_score >= self.config.motion_change_threshold:
            signals.append(NOVELTY_MOTION_CHANGE)
        support = opportunity.detector_confirmation_count + opportunity.tracker_support_count
        if group.support_floor is not None and support - group.support_floor >= self.config.temporal_support_delta:
            signals.append(NOVELTY_BETTER_TEMPORAL_SUPPORT)
        if signals:
            return False, tuple(signals)
        return True, ()


__all__ = [
    "DECISION_BURST_ISSUED",
    "DECISION_BURST_UNAVAILABLE",
    "DECISION_DEFERRED_COOLDOWN",
    "DECISION_ENGINEERING_OVERRIDE_ISSUED",
    "DECISION_OPERATOR_OVERRIDE_ISSUED",
    "DECISION_RETRY_ISSUED",
    "DECISION_SUPPRESSED_ACTIVE_REQUEST",
    "DECISION_SUPPRESSED_RATE_BUDGET",
    "DECISION_SUPPRESSED_RECURRING_GEOMETRY",
    "DECISION_SUPPRESSED_SAME_TRACK_GENERATION",
    "DECISION_SUPPRESSED_SESSION_BUDGET",
    "ISSUING_DECISIONS",
    "NOVELTY_BETTER_TEMPORAL_SUPPORT",
    "NOVELTY_ENGINEERING_REQUEST",
    "NOVELTY_MOTION_CHANGE",
    "NOVELTY_OPERATOR_MARKER",
    "NOVELTY_RETRY_PERMITTED",
    "NOVELTY_SIGNALS",
    "NOVELTY_STRONGER_CONFIDENCE",
    "NOVELTY_TIME_GAP",
    "RESET_ENGINEERING_RESET",
    "RESET_GENERATION_REPLACEMENT",
    "RESET_PROVIDER_RESET",
    "RESET_REASONS",
    "RESET_SESSION_STOP",
    "SCHEDULER_DECISIONS",
    "SCHEDULER_VERSION",
    "BurstDecision",
    "BurstOpportunity",
    "BurstScheduler",
    "BurstSchedulerConfig",
    "BurstSchedulerDiagnostics",
    "BurstSchedulerError",
    "BurstSchedulerHealth",
    "RecurrenceGroupSnapshot",
]
