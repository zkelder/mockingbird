"""Rejected / Suppressed Detection Attribution v1 (see
docs/rejected-detection-attribution-contract.md).

The precise question this module exists to let the system answer: when a
real bird is visible in source imagery but no corresponding Visit is
persisted, did the raw detector detect it and downstream logic suppress/
lose it, or did the detector never localize it at all?

Traced (see the contract doc "Where facts were lost, as traced"): a live
Camera Node session already computes every fact this diagnostic needs --
`ObservationResult.detection_observations` (every raw detector output, one
tuple per inferred frame), every `TrackUpdate` for every track generation
including one the tracker itself rejects before Visit assembly ever runs,
and every `AssembledVisitProposal`'s admission outcome -- but
`mockingbird.observation.engine_runtime._EngineSession` previously read only
`track_updates`/`evidence_candidates` off each `ObservationResult` and
collapsed every non-created admission outcome into one bare `{reason:
count}` in-memory dict (`_EngineSession._suppressed`), discarding the
proposal's own id, lineage, geometry, and confidence the moment that loop
iteration ended. This module is the bounded, structured, retained
replacement for that discarded detail -- never a parallel observability
system: every fact/vocabulary here is read from already-emitted
`contracts.py`/`visit_episode_assembler.py`/`candidate_visit_authority.py`/
`candidate_quality_gate.py` facts, never recomputed or invented.

Pure: no filesystem, network, CUDA/ONNX Runtime/OpenCV, product-repository,
or SQLAlchemy import -- the same structural convention every other Stage
6.x/7 decision module in this package follows
(`test_counterfactual_lineage_module_has_no_product_repository_import`).
Diagnostic accounting only, exactly like `detection_quality_accounting.py`
and `localization_attribution.py`: this module never creates, mutates, or
implies an Event, Visit, MediaAsset, ReviewLabel, or reviewed truth, and its
own output is evidence a report or an operator may read, never itself
observational authority (see "The truth boundary" in product-doctrine.md).

Bounded retention, not a permanent record: `CounterfactualLedger` retains a
small, structured, model-neutral fact per raw detection/track-generation-
outcome/proposal-outcome -- never full-resolution imagery, never an
unbounded per-session list -- evicted deterministically by capacity and age
(see `CounterfactualRetentionConfig`, `LedgerEvictionAccounting`). A missing
fact stays explicitly unknown/`insufficient_counterfactual_lineage`; nothing
here ever fabricates a value or claims `detector_miss` from an incompletely
-retained window (see `CounterfactualCoverage.complete_for`).
"""

from __future__ import annotations

import threading
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal, Protocol, Sequence, runtime_checkable

from mockingbird.observation.candidate_quality_gate import REJECTED_OUTCOMES as _QUALITY_REJECTED_OUTCOMES
from mockingbird.observation.candidate_visit_authority import BLOCKED_OUTCOMES as _AUTHORITY_BLOCKED_OUTCOMES
from mockingbird.observation.contracts import ConfidenceEvidenceSummary, DetectionObservation, FramePacket, ObservationResult, TrackUpdate
from mockingbird.observation.localization_attribution import geometry_source_from_support_state
from mockingbird.observation.visit_episode_assembler import confidence_evidence_from_terminal_update

COUNTERFACTUAL_LINEAGE_VERSION = "counterfactual-lineage-v1"

BoundingBox = tuple[float, float, float, float]

# Admission-attempt outcome codes that mean "the *authority* gate itself
# conservatively declined to persist this proposal" (rate/activation/
# lineage/ambiguity/continuation-boundary policy -- see
# candidate_visit_authority.py) versus outcome codes that mean "the proposal
# reached the *admission/evidence-quality* boundary and was actively
# evaluated and rejected there" (candidate_quality_gate.py's own reject_*
# codes, plus the repository-local checks `_create_candidate_visit_
# locked` performs only *after* authority already said "create":
# `blocked_missing_evidence`/`blocked_privacy_zone`/`blocked_scene_
# confusor_suspected` -- see their own docstring on
# `CandidateVisitCreationOutcome`). This module invents neither
# vocabulary; it only partitions the two already-existing ones so
# `detector_hit_then_suppressed` and `admission_rejected` stay
# distinguishable, non-overlapping outcomes, matching the task's own naming.
# `blocked_scene_confusor_suspected` (see docs/scene-confusor-suspicion-
# contract.md) is structurally identical in kind to `blocked_privacy_zone`:
# a repository-local check with its own Stream/geometry context neither
# `candidate_visit_authority` nor `candidate_quality_gate` can see.
ADMISSION_REJECTED_OUTCOMES: frozenset[str] = _QUALITY_REJECTED_OUTCOMES | frozenset({
    "blocked_missing_evidence", "blocked_privacy_zone", "blocked_scene_confusor_suspected", "failed",
})


def _valid_box(box: BoundingBox | None) -> bool:
    """Mirrors `visit_episode_assembler._valid_box`/`frame_tracker._valid_
    box` exactly -- deliberately duplicated, never imported, matching this
    package's own established "self-contained pure module" convention."""
    return (
        box is not None
        and len(box) == 4
        and all(0.0 <= value <= 1.0 for value in box)
        and box[0] < box[2] and box[1] < box[3]
    )


def _boxes_overlap(a: BoundingBox, b: BoundingBox) -> bool:
    left, top = max(a[0], b[0]), max(a[1], b[1])
    right, bottom = min(a[2], b[2]), min(a[3], b[3])
    return right > left and bottom > top


def _roi_matches(box: BoundingBox | None, roi: BoundingBox | None) -> bool:
    """`roi is None` means "no region filter" -- everything matches. A
    record with no geometry of its own (`box is None`, for example a raw
    "detector ran, found nothing" heartbeat) never matches a real ROI."""
    if roi is None:
        return True
    if box is None:
        return False
    return _boxes_overlap(box, roi)


def _union_box(a: BoundingBox, b: BoundingBox) -> BoundingBox:
    return (min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3]))


# --- Detection ---------------------------------------------------------------


@dataclass(frozen=True)
class RawDetectionRecord:
    """One raw detector-evaluation fact for one analysis frame the detector
    actually ran on -- either a genuine detection (`bounding_box` set,
    matched into a track or not: this ledger never filters by what the
    tracker later did with it) or an explicit "the detector ran here and
    found nothing usable" heartbeat (`bounding_box is None`). Both are
    recorded, deliberately: a frame the detector never evaluated at all (an
    idle-cadence gap) must stay distinguishable from one it evaluated and
    found nothing in -- exactly the "skipped vs. negative" distinction
    `TrackUpdate.detector_ran` already established for tracker-level
    accounting (see docs/tracklet-visit-assembly-contract.md), one layer
    earlier, before any track exists at all. Never reviewed truth, never a
    species/animal-presence judgment by itself.
    """

    stream_id: str
    source_offset_ms: int
    captured_at: datetime | None
    frame_id: str | None
    observation_id: str | None
    detector_id: str | None
    provider_id: str | None
    broad_class: str | None
    is_animal: bool | None
    confidence: float | None
    bounding_box: BoundingBox | None
    node_session_id: str | None = None
    provider_generation: str | None = None

    @property
    def has_detection(self) -> bool:
        return self.bounding_box is not None


# --- Tracking ------------------------------------------------------------


@dataclass(frozen=True)
class TrackGenerationRecord:
    """One finalized (started-and-ended) tracker generation's bounded
    summary -- confirmed *or* rejected. `visit_episode_assembler.
    build_tracklets` already discards every generation whose terminal
    `lifecycle_state != "ended"` (never confirmed by the tracker's own
    confirmation bar); this ledger retains exactly the fact that discards,
    so a track the tracker itself lost before Visit assembly ever ran stays
    reconstructable (see `detector_hit_then_tracker_lost`).

    Built from exactly the generation's first (`started`) and terminal
    (`ended`) `TrackUpdate` plus an incrementally-accumulated geometry
    envelope across every intermediate update this ledger actually observed
    -- deliberately not a full retained per-frame history (see
    docs/rejected-detection-attribution-contract.md "why two updates are
    enough"); `confidence_evidence` alone already carries the generation's
    own bounded per-detection sample history (Detection Quality Accounting
    v1), reused verbatim rather than duplicated here.

    Gate A Measurement Closure v1: `start_captured_at`/`end_captured_at` are
    the *wall-clock* twins of `start_offset_ms`/`end_offset_ms` -- always
    already available (`TrackUpdate.captured_at` is a required field, never
    itself a new capture-time read; see `_track_generation_record`), simply
    never previously copied onto this record. Node-domain (the Camera
    Node's own clock -- see "Clock-drift disposition" in
    docs/camera-node-live-shadow-contract.md): safe to compare against
    another Node-domain timestamp, *not* proven safe to subtract directly
    from a Host-domain timestamp (`ProposalOutcomeRecord.decided_at`)
    without disclosing that cross-domain uncertainty -- see
    `capture_to_visible_latency.py`. `None` only for a caller-constructed
    record that predates this field (for example a saved pre-existing
    ledger JSON snapshot replayed through `run_encounter_accounting.py`) --
    never fabricated.
    """

    generation_id: str
    stream_id: str
    broad_class: str
    track_ids: tuple[str, ...]
    start_offset_ms: int
    end_offset_ms: int
    start_bounding_box: BoundingBox
    end_bounding_box: BoundingBox
    geometry_envelope: BoundingBox
    confirmed: bool
    terminal_reason: str | None
    terminal_support_state: str | None
    terminal_bounding_box_source_offset_ms: int | None
    confidence_evidence: ConfidenceEvidenceSummary
    start_captured_at: datetime | None = None
    end_captured_at: datetime | None = None

    @property
    def terminal_geometry_source(self) -> Literal["detector", "tracker", "carried_forward"] | None:
        """Reuses `localization_attribution.geometry_source_from_support_
        state` verbatim -- the identical fact, one layer earlier: which kind
        of observation established this *generation's own last-known*
        geometry, independent of whether that geometry ever became any
        persisted candidate's evidence box."""
        return geometry_source_from_support_state(self.terminal_support_state)


# --- Proposal --------------------------------------------------------------


@runtime_checkable
class ProposalLineageFacts(Protocol):
    """The only shape this module needs from an assembled proposal --
    deliberately a structural `Protocol`, not an import of
    `visit_episode_assembler.AssembledVisitProposal`, mirroring
    `candidate_visit_authority.ProposalLineage`'s own established
    convention exactly (same rationale: this module stays product
    -repository/assembler-import-free while `AssembledVisitProposal`
    satisfies this shape unchanged)."""

    proposal_id: str
    stream_id: str
    broad_class: str
    zone_id: str | None
    start_offset_ms: int
    end_offset_ms: int
    constituent_generation_ids: tuple[str, ...]
    constituent_track_ids: tuple[str, ...]
    confidence_evidence: ConfidenceEvidenceSummary


@dataclass(frozen=True)
class ProposalOutcomeRecord:
    """One decided admission attempt for one assembled Visit proposal,
    recorded regardless of outcome (created, idempotent repeat, or any
    blocked/rejected/failed code) -- so both "why was this Visit created"
    and "why was this potential Visit not created" can be answered from the
    same bounded ledger (see "Detection Quality Accounting integration" in
    docs/rejected-detection-attribution-contract.md).

    `outcome`/`reason` reuse the existing, unmodified
    `candidate_visit_authority.AuthorityOutcome`/`candidate_quality_gate.
    QualityOutcome`/`product_repository.CandidateVisitCreationOutcome`
    vocabularies verbatim -- this ledger invents no new outcome code.
    """

    proposal_id: str
    stream_id: str
    broad_class: str
    zone_id: str | None
    start_offset_ms: int
    end_offset_ms: int
    constituent_generation_ids: tuple[str, ...]
    constituent_track_ids: tuple[str, ...]
    outcome: str
    reason: str
    admitted: bool
    visit_id: str | None
    confidence_evidence: ConfidenceEvidenceSummary | None
    decided_at: datetime
    # Best-known session-relative offset at decision time (the assembly
    # tick's own `known_horizon_ms`) -- `None` only for a caller that never
    # supplied one (never fabricated). Used for this record's own bounded
    # age-eviction; see `CounterfactualLedger`.
    decided_at_offset_ms: int | None


def proposal_outcome_record(
    proposal: ProposalLineageFacts,
    *,
    outcome: str,
    reason: str,
    visit_id: str | None,
    decided_at: datetime,
    known_horizon_ms: int | None,
) -> ProposalOutcomeRecord:
    return ProposalOutcomeRecord(
        proposal_id=proposal.proposal_id,
        stream_id=proposal.stream_id,
        broad_class=proposal.broad_class,
        zone_id=proposal.zone_id,
        start_offset_ms=proposal.start_offset_ms,
        end_offset_ms=proposal.end_offset_ms,
        constituent_generation_ids=proposal.constituent_generation_ids,
        constituent_track_ids=proposal.constituent_track_ids,
        outcome=outcome,
        reason=reason,
        admitted=outcome in ("created", "idempotent_repeat"),
        visit_id=visit_id,
        confidence_evidence=proposal.confidence_evidence,
        decided_at=decided_at,
        decided_at_offset_ms=known_horizon_ms,
    )


# --- Bounded retention -------------------------------------------------------


@dataclass(frozen=True)
class CounterfactualRetentionConfig:
    """Bounded-by-capacity-and-age retention for the three ledgers below.
    Reused/derived defaults, not per-scene tuning: `max_age_ms` (60 minutes)
    comfortably exceeds the longest real bounded field session run to date
    (45m47s, see data/field-acceptance/2026-08-11-localization-attribution
    -live-evidence/), so an ordinary bounded session never evicts anything
    at all; the count caps are sized with generous headroom over the
    busiest real session measured so far (2,670 track updates / 727
    evidence candidates / 151 proposals / 149 suppressed over ~46 minutes).
    """

    max_raw_detection_records: int = 12_000
    max_track_generation_records: int = 2_000
    max_proposal_outcome_records: int = 1_000
    max_age_ms: int = 60 * 60 * 1000

    def __post_init__(self) -> None:
        if (
            self.max_raw_detection_records < 1
            or self.max_track_generation_records < 1
            or self.max_proposal_outcome_records < 1
            or self.max_age_ms < 1
        ):
            raise ValueError("invalid_counterfactual_retention_config")


@dataclass(frozen=True)
class LedgerEvictionAccounting:
    """Deterministic, read-only account of what one bounded ledger has
    evicted so far -- the "clear eviction accounting so an operator knows
    when older evidence is unavailable" fact. `evicted_count` is exact
    (`recorded_count - retained_count`), never estimated."""

    retained_count: int
    evicted_count: int
    recorded_count: int
    oldest_retained_offset_ms: int | None
    newest_retained_offset_ms: int | None


class _BoundedOffsetLedger:
    """Deterministic FIFO ledger, bounded by count *and* age relative to the
    most-recently-appended record's own offset -- oldest evicted first on
    both dimensions, exactly mirroring `camera_node_live.
    CameraNodeAnalysisSource._pop_latest`'s own age-eviction loop shape and
    `frame_tracker._Track.confidence_samples`'s own count-bound shape. Not
    part of this module's public contract; a small internal mechanism
    shared by the three concrete ledgers `CounterfactualLedger` owns."""

    def __init__(self, *, max_count: int, max_age_ms: int, offset_of) -> None:
        if max_count < 1 or max_age_ms < 1:
            raise ValueError("invalid_counterfactual_retention_bound")
        self._max_count = max_count
        self._max_age_ms = max_age_ms
        self._offset_of = offset_of
        self._records: deque = deque()
        self._recorded_count = 0

    def append(self, record: object) -> None:
        self._records.append(record)
        self._recorded_count += 1
        newest_offset = self._offset_of(record)
        while len(self._records) > self._max_count:
            self._records.popleft()
        while self._records and newest_offset - self._offset_of(self._records[0]) > self._max_age_ms:
            self._records.popleft()

    @property
    def records(self) -> tuple:
        return tuple(self._records)

    def accounting(self) -> LedgerEvictionAccounting:
        retained = self._records
        return LedgerEvictionAccounting(
            retained_count=len(retained),
            evicted_count=self._recorded_count - len(retained),
            recorded_count=self._recorded_count,
            oldest_retained_offset_ms=self._offset_of(retained[0]) if retained else None,
            newest_retained_offset_ms=self._offset_of(retained[-1]) if retained else None,
        )


@dataclass(frozen=True)
class CounterfactualCoverage:
    """Bounded, read-only account of what this ledger can honestly still
    answer for. `complete_for` is the specific guarantee a `detector_miss`
    conclusion requires; nothing else in this module may claim that outcome
    without it (see "Do not fabricate" in docs/rejected-detection-
    attribution-contract.md)."""

    session_first_offset_ms: int | None
    session_last_offset_ms: int | None
    raw_detection_retention: LedgerEvictionAccounting
    track_generation_retention: LedgerEvictionAccounting
    proposal_outcome_retention: LedgerEvictionAccounting

    def complete_for(self, start_offset_ms: int, end_offset_ms: int) -> bool:
        """Whether the *raw-detection* ledger alone retains complete history
        for the entire queried window. Track-generation/proposal-outcome
        retention never gates this: a `detector_miss` conclusion is
        specifically about the raw detector signal, never about what became
        of any track/proposal -- that is a separate, positive-evidence
        question the classifier only reaches once a raw detection was
        actually found (see `classify_rejection_attribution`)."""
        if self.session_first_offset_ms is None or self.session_last_offset_ms is None:
            return False
        if start_offset_ms < self.session_first_offset_ms or end_offset_ms > self.session_last_offset_ms:
            return False
        retention = self.raw_detection_retention
        if retention.evicted_count == 0:
            return True
        return retention.oldest_retained_offset_ms is not None and start_offset_ms >= retention.oldest_retained_offset_ms


@dataclass(frozen=True)
class CounterfactualWindowResult:
    """One bounded, time-window-filtered (and, where noted, ROI-filtered)
    read from a `CounterfactualLedger`. `raw_detections`/`track_generations`/
    `proposal_outcomes` are every retained record whose own temporal span
    overlaps `[start_offset_ms, end_offset_ms]`, independent of `roi`; the
    `..._in_roi` tuples are the same records further filtered to those whose
    own geometry overlaps `roi` (identical to the un-filtered tuple when
    `roi is None`) -- directly answering "whether any lineage overlaps a
    supplied region of interest" per-record, not merely as one aggregate
    boolean."""

    stream_id: str
    start_offset_ms: int
    end_offset_ms: int
    roi: BoundingBox | None
    raw_detections: tuple[RawDetectionRecord, ...]
    track_generations: tuple[TrackGenerationRecord, ...]
    proposal_outcomes: tuple[ProposalOutcomeRecord, ...]
    raw_detections_in_roi: tuple[RawDetectionRecord, ...]
    track_generations_in_roi: tuple[TrackGenerationRecord, ...]
    coverage: CounterfactualCoverage


@dataclass
class _OpenGeneration:
    """Transient, mutable, per-currently-active-generation accumulator --
    naturally bounded by however many tracks the tracker's own `maximum_
    active_tracks` allows concurrently, never itself a historical ledger."""

    first: TrackUpdate
    envelope: BoundingBox


def _track_generation_record(
    first: TrackUpdate, terminal: TrackUpdate, envelope: BoundingBox, *, stream_id: str,
) -> TrackGenerationRecord | None:
    """`None` (never fabricated geometry) when the terminal update itself
    carries no box -- structurally should not happen for a real tracker
    -produced update (`frame_tracker._Track.bounding_box` is never null
    once a generation starts), kept as a defensive, honest skip rather than
    a crash, mirroring `build_tracklets`'s own identical guard."""
    if terminal.bounding_box is None or first.source_offset_ms is None or terminal.source_offset_ms is None:
        return None
    broad_class = terminal.broad_class or first.broad_class or "animal"
    return TrackGenerationRecord(
        generation_id=terminal.generation_id,
        stream_id=stream_id,
        broad_class=broad_class,
        track_ids=tuple(dict.fromkeys(item for item in (first.track_id, terminal.track_id) if item)),
        start_offset_ms=first.source_offset_ms,
        end_offset_ms=terminal.source_offset_ms,
        start_bounding_box=first.bounding_box or terminal.bounding_box,
        end_bounding_box=terminal.bounding_box,
        geometry_envelope=envelope,
        confirmed=(terminal.lifecycle_state == "ended"),
        terminal_reason=terminal.terminal_reason,
        terminal_support_state=terminal.support_state,
        terminal_bounding_box_source_offset_ms=terminal.bounding_box_source_offset_ms,
        confidence_evidence=confidence_evidence_from_terminal_update(
            terminal, max_confidence=terminal.confidence, broad_class=broad_class,
        ),
        # Gate A Measurement Closure v1: both already in scope on the two
        # `TrackUpdate`s this function already reads -- never a new wall
        # -clock read, never new I/O, never a behavior change for any
        # existing caller (see `TrackGenerationRecord`'s own docstring).
        start_captured_at=first.captured_at,
        end_captured_at=terminal.captured_at,
    )


def _raw_detection_from_observation(
    item: DetectionObservation, *, frame: FramePacket | None, stream_id: str, fallback_offset_ms: int,
) -> RawDetectionRecord:
    return RawDetectionRecord(
        stream_id=stream_id,
        source_offset_ms=(
            frame.source_offset_ms if frame is not None and frame.source_offset_ms is not None else fallback_offset_ms
        ),
        captured_at=item.captured_at,
        frame_id=item.frame_id,
        observation_id=item.observation_id,
        detector_id=item.detector_id,
        provider_id=item.provider_id,
        broad_class=item.label,
        is_animal=item.is_animal,
        confidence=item.confidence,
        bounding_box=item.bounding_box,
        node_session_id=frame.node_session_id if frame is not None else None,
        provider_generation=frame.provider_generation if frame is not None else None,
    )


def _raw_detection_heartbeat(*, frame: FramePacket | None, stream_id: str, offset_ms: int) -> RawDetectionRecord:
    """The explicit "the detector ran this frame and found nothing usable"
    fact -- see `RawDetectionRecord`'s own docstring for why this is
    recorded rather than left as a silent absence."""
    return RawDetectionRecord(
        stream_id=stream_id,
        source_offset_ms=offset_ms,
        captured_at=frame.captured_at if frame is not None else None,
        frame_id=frame.frame_id if frame is not None else None,
        observation_id=None,
        detector_id=None,
        provider_id=None,
        broad_class=None,
        is_animal=None,
        confidence=None,
        bounding_box=None,
        node_session_id=frame.node_session_id if frame is not None else None,
        provider_generation=frame.provider_generation if frame is not None else None,
    )


class CounterfactualLedger:
    """The one bounded, deterministic, local-only, thread-safe standing
    record of rejected/suppressed detection activity for one live
    Observation Engine session. Owns three independently bounded ledgers
    (raw detections, track-generation outcomes, proposal outcomes) plus the
    session's own observed source-offset span. Internally locked so it is
    safe to mutate from one session's own processing loop while a
    concurrent status/query read happens from a different thread (the
    product API request thread) -- mirroring every other cross-thread
    boundary this package already protects (`_EngineSession._state_lock`).

    Never imports a product repository, filesystem path, network
    connection, or CUDA/ONNX Runtime/OpenCV runtime; never creates an
    Event, Visit, MediaAsset, ReviewLabel, or reviewed truth.
    """

    def __init__(self, *, stream_id: str, config: CounterfactualRetentionConfig | None = None) -> None:
        if not stream_id:
            raise ValueError("invalid_counterfactual_ledger_stream")
        self.stream_id = stream_id
        self._config = config or CounterfactualRetentionConfig()
        self._lock = threading.Lock()
        self._raw_detections = _BoundedOffsetLedger(
            max_count=self._config.max_raw_detection_records,
            max_age_ms=self._config.max_age_ms,
            offset_of=lambda record: record.source_offset_ms,
        )
        self._track_generations = _BoundedOffsetLedger(
            max_count=self._config.max_track_generation_records,
            max_age_ms=self._config.max_age_ms,
            offset_of=lambda record: record.end_offset_ms,
        )
        self._proposal_outcomes = _BoundedOffsetLedger(
            max_count=self._config.max_proposal_outcome_records,
            max_age_ms=self._config.max_age_ms,
            offset_of=lambda record: (
                record.decided_at_offset_ms if record.decided_at_offset_ms is not None else record.end_offset_ms
            ),
        )
        self._open_generations: dict[str, _OpenGeneration] = {}
        self._session_first_offset_ms: int | None = None
        self._session_last_offset_ms: int | None = None

    def observe_result(self, result: ObservationResult) -> None:
        """Feed one already-emitted `ObservationResult` -- exactly the fact
        a live session's own processing loop already has in scope every
        batch (`engine_runtime._EngineSession._run_async`), previously read
        only for `track_updates`/`evidence_candidates` and never for
        `detection_observations`/`detector_ran` at all. Idempotent-safe to
        call once per result in arrival order; never re-derives anything
        from an earlier result."""
        with self._lock:
            self._observe_result_locked(result)

    def _observe_result_locked(self, result: ObservationResult) -> None:
        frame = result.frame_packets[0] if result.frame_packets else None
        offset = frame.source_offset_ms if frame is not None else None
        if offset is not None:
            self._session_first_offset_ms = (
                offset if self._session_first_offset_ms is None else min(self._session_first_offset_ms, offset)
            )
            self._session_last_offset_ms = (
                offset if self._session_last_offset_ms is None else max(self._session_last_offset_ms, offset)
            )
        if result.detector_ran and offset is not None:
            if result.detection_observations:
                for item in result.detection_observations:
                    self._raw_detections.append(
                        _raw_detection_from_observation(
                            item, frame=frame, stream_id=self.stream_id, fallback_offset_ms=offset,
                        )
                    )
            else:
                self._raw_detections.append(
                    _raw_detection_heartbeat(frame=frame, stream_id=self.stream_id, offset_ms=offset)
                )
        for update in result.track_updates:
            self._observe_track_update_locked(update)

    def _observe_track_update_locked(self, update: TrackUpdate) -> None:
        if update.bounding_box is None:
            return
        generation_id = update.generation_id
        if update.status == "started":
            self._open_generations[generation_id] = _OpenGeneration(update, update.bounding_box)
        else:
            open_generation = self._open_generations.get(generation_id)
            if open_generation is None:
                # A generation whose own `started` update predates this
                # ledger's own observation window (should not happen in
                # practice -- the ledger is created fresh with its session
                # -- kept as a defensive, honest reconstruction rather than
                # a dropped record).
                open_generation = _OpenGeneration(update, update.bounding_box)
                self._open_generations[generation_id] = open_generation
            else:
                open_generation.envelope = _union_box(open_generation.envelope, update.bounding_box)
        if update.status == "ended":
            open_generation = self._open_generations.pop(generation_id, None)
            if open_generation is None:
                return
            record = _track_generation_record(
                open_generation.first, update, open_generation.envelope, stream_id=self.stream_id,
            )
            if record is not None:
                self._track_generations.append(record)

    def record_proposal_outcome(
        self,
        proposal: ProposalLineageFacts,
        *,
        outcome: str,
        reason: str,
        visit_id: str | None,
        decided_at: datetime,
        known_horizon_ms: int | None,
    ) -> None:
        """Record one already-decided admission attempt -- called once per
        `adapter.attempt_candidate(...)` result, replacing/augmenting the
        prior bare `_suppressed[outcome] += 1` bookkeeping with full,
        reconstructable lineage. Recorded regardless of outcome (including
        `created`/`idempotent_repeat`), so `classify_rejection_attribution`
        can also honestly report `visit_created` rather than force a real
        admission into a rejection bucket."""
        record = proposal_outcome_record(
            proposal, outcome=outcome, reason=reason, visit_id=visit_id,
            decided_at=decided_at, known_horizon_ms=known_horizon_ms,
        )
        with self._lock:
            self._proposal_outcomes.append(record)

    def coverage(self) -> CounterfactualCoverage:
        with self._lock:
            return CounterfactualCoverage(
                session_first_offset_ms=self._session_first_offset_ms,
                session_last_offset_ms=self._session_last_offset_ms,
                raw_detection_retention=self._raw_detections.accounting(),
                track_generation_retention=self._track_generations.accounting(),
                proposal_outcome_retention=self._proposal_outcomes.accounting(),
            )

    def query(
        self, *, start_offset_ms: int, end_offset_ms: int, roi: BoundingBox | None = None,
    ) -> CounterfactualWindowResult:
        """Side-effect-free, bounded read: reconstruct what happened around
        one source-relative time window (and, optionally, one region of
        interest) from currently-retained lineage. Never raises for an
        empty/uncovered window -- an honest, empty result with `coverage`
        describing exactly what is/is not still retained is always
        returned; only a structurally invalid window/ROI raises."""
        if end_offset_ms < start_offset_ms:
            raise ValueError("invalid_counterfactual_query_window")
        if roi is not None and not _valid_box(roi):
            raise ValueError("invalid_counterfactual_query_roi")
        with self._lock:
            raw = tuple(
                item for item in self._raw_detections.records
                if start_offset_ms <= item.source_offset_ms <= end_offset_ms
            )
            generations = tuple(
                item for item in self._track_generations.records
                if item.start_offset_ms <= end_offset_ms and item.end_offset_ms >= start_offset_ms
            )
            proposals = tuple(
                item for item in self._proposal_outcomes.records
                if item.start_offset_ms <= end_offset_ms and item.end_offset_ms >= start_offset_ms
            )
            coverage = CounterfactualCoverage(
                session_first_offset_ms=self._session_first_offset_ms,
                session_last_offset_ms=self._session_last_offset_ms,
                raw_detection_retention=self._raw_detections.accounting(),
                track_generation_retention=self._track_generations.accounting(),
                proposal_outcome_retention=self._proposal_outcomes.accounting(),
            )
        raw_in_roi = tuple(item for item in raw if _roi_matches(item.bounding_box, roi))
        generations_in_roi = tuple(
            item for item in generations if _roi_matches(item.geometry_envelope, roi)
        )
        return CounterfactualWindowResult(
            stream_id=self.stream_id,
            start_offset_ms=start_offset_ms,
            end_offset_ms=end_offset_ms,
            roi=roi,
            raw_detections=raw,
            track_generations=generations,
            proposal_outcomes=proposals,
            raw_detections_in_roi=raw_in_roi,
            track_generations_in_roi=generations_in_roi,
            coverage=coverage,
        )


# --- Attribution outcome ------------------------------------------------


RejectionAttributionCode = Literal[
    "detector_miss",
    "detector_hit_then_tracker_lost",
    "detector_hit_then_suppressed",
    "tracker_drift",
    "admission_rejected",
    "visit_created",
    "insufficient_counterfactual_lineage",
]


@dataclass(frozen=True)
class RejectionAttributionResult:
    """One deterministic classification of what happened to detector
    activity in one region/time window that has no persisted Visit. Reason
    strings are stable, sanitized codes -- never raw exception text.
    `visit_created` is not itself a rejection outcome; it is the honest
    result when the queried region/window turns out to correspond to a
    proposal that *was* admitted -- included so this classifier never
    forces an admitted case into a rejection bucket just to stay inside a
    fixed vocabulary (see docs/rejected-detection-attribution-contract.md)."""

    attribution: RejectionAttributionCode
    reason: str
    supporting_generation_id: str | None = None
    supporting_proposal_id: str | None = None


def classify_rejection_attribution(window: CounterfactualWindowResult) -> RejectionAttributionResult:
    """Classify why a queried region/time window has no persisted Visit,
    using only already-retained counterfactual lineage -- never pixel
    content, never a species/animal-presence judgment, never a guess past
    what the ledger actually retained. Deterministic: identical inputs
    always produce an identical result.

    Decision order (most decidable/specific fact first, mirroring
    `localization_attribution.classify_localization_attribution`'s own
    style; see "Attribution decision order" in docs/rejected-detection
    -attribution-contract.md):

    1. No raw detector activity overlaps the region in the queried window.
       `detector_miss` only when the raw-detection ledger's own retention
       provably covers the entire window (`coverage.complete_for`);
       otherwise `insufficient_counterfactual_lineage` -- an evicted/
       partial window must never be read as a proven absence.
    2. A raw detection overlaps the region, but no retained track
       -generation record's own geometry does either -- the detector fired
       here but this ledger holds no corresponding tracker lineage (either
       the detection was non-animal-class/excluded from tracking, or the
       corresponding generation record has itself since been evicted).
       `insufficient_counterfactual_lineage`.
    3. Among the track generations whose geometry overlaps the region: any
       that the tracker itself never confirmed -> `detector_hit_then_
       tracker_lost` (checked before every outcome below -- an unconfirmed
       generation never reached Visit assembly at all, the single most
       decidable fact available).
    4. Among the (now all-confirmed) overlapping generations: any whose own
       region-overlapping geometry was established by tracker-support
       (patch) matching rather than a genuine detection at that moment ->
       `tracker_drift`.
    5. Among the remaining confirmed, detector-anchored generations: the
       proposal outcome recorded for its constituent generation, if any --
       `visit_created` (admitted), `detector_hit_then_suppressed` (the
       authority gate's own conservative policy), `admission_rejected` (the
       evidence-quality/admission boundary), or `insufficient_counterfactual
       _lineage` (no admission decision retained yet, or an outcome code
       this classifier does not recognize -- never guessed).
    """

    if not window.raw_detections_in_roi:
        if window.coverage.complete_for(window.start_offset_ms, window.end_offset_ms):
            return RejectionAttributionResult(
                "detector_miss", "no_raw_detector_activity_overlapping_region_in_covered_window",
            )
        return RejectionAttributionResult(
            "insufficient_counterfactual_lineage",
            "queried_window_not_fully_covered_by_retained_raw_detection_lineage",
        )

    generations = window.track_generations_in_roi
    if not generations:
        return RejectionAttributionResult(
            "insufficient_counterfactual_lineage",
            "raw_detector_activity_present_but_no_corresponding_track_generation_retained",
        )

    for generation in generations:
        if not generation.confirmed:
            return RejectionAttributionResult(
                "detector_hit_then_tracker_lost",
                f"track_generation_never_confirmed_terminal_reason_{generation.terminal_reason or 'unknown'}",
                supporting_generation_id=generation.generation_id,
            )

    for generation in generations:
        if generation.terminal_geometry_source == "tracker":
            return RejectionAttributionResult(
                "tracker_drift",
                "region_overlapping_geometry_supplied_by_tracker_support_not_a_genuine_detection",
                supporting_generation_id=generation.generation_id,
            )

    proposals_by_generation: dict[str, ProposalOutcomeRecord] = {}
    for proposal in window.proposal_outcomes:
        for generation_id in proposal.constituent_generation_ids:
            proposals_by_generation.setdefault(generation_id, proposal)

    for generation in generations:
        proposal = proposals_by_generation.get(generation.generation_id)
        if proposal is None:
            continue
        if proposal.admitted:
            return RejectionAttributionResult(
                "visit_created", "constituent_track_generation_was_admitted_as_a_candidate_visit",
                supporting_generation_id=generation.generation_id, supporting_proposal_id=proposal.proposal_id,
            )
        if proposal.outcome in _AUTHORITY_BLOCKED_OUTCOMES:
            return RejectionAttributionResult(
                "detector_hit_then_suppressed", f"authority_gate_outcome_{proposal.outcome}",
                supporting_generation_id=generation.generation_id, supporting_proposal_id=proposal.proposal_id,
            )
        if proposal.outcome in ADMISSION_REJECTED_OUTCOMES:
            return RejectionAttributionResult(
                "admission_rejected", f"admission_gate_outcome_{proposal.outcome}",
                supporting_generation_id=generation.generation_id, supporting_proposal_id=proposal.proposal_id,
            )
        return RejectionAttributionResult(
            "insufficient_counterfactual_lineage", f"unrecognized_proposal_outcome_{proposal.outcome}",
            supporting_generation_id=generation.generation_id, supporting_proposal_id=proposal.proposal_id,
        )

    return RejectionAttributionResult(
        "insufficient_counterfactual_lineage",
        "confirmed_track_generation_present_but_no_admission_decision_retained_yet",
        supporting_generation_id=generations[0].generation_id,
    )
