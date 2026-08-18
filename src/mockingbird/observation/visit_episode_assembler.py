"""Provider-neutral, shadow-only Visit episode assembly from bounded tracklets.

Stage 6.19 (see docs/tracklet-visit-assembly-contract.md). Stage 6.18 proved
that making one low-level tracker generation equal one wildlife Visit is an
unsatisfiable tradeoff: attempt-3's real ~5-minute feeder visit fragments
badly under aggressive episode termination, while session-04's genuinely
separate ~16.2s-apart appearances merge under aggressive continuity -- the
same single mechanism cannot honestly serve both. This module is the fix:
**track lifetime and Visit lifetime are separate concepts.**

`frame_tracker.ProviderNeutralFrameTracker` remains completely unmodified in
its association/confirmation policy and stays deliberately conservative,
bounded, and allowed to fragment. This module sits *above* it: it consumes
only already-emitted `TrackUpdate` facts for CONFIRMED track generations
(never an implementation-specific tracker object, never species identity)
and decides, using bounded evidence, whether temporally-adjacent tracklets
belong to one sustained genuine appearance -- merging them into one bounded
shadow `AssembledVisitProposal` -- or must stay separate, or whether the
evidence cannot safely tell (`ambiguous_boundary`, conservatively kept
separate rather than guessed into a merge).

Pure: no filesystem, network, CUDA/ONNX Runtime/OpenCV, camera-provider, or
product-repository import, mirroring every other Stage 6.x decision module
(`reconnect_continuity`, `session_timeline`). Every semantic decision reads
only source/session-relative facts already carried on `Tracklet` -- never an
absolute filesystem path, one feeder geometry, a specific Visit id, species
identity, or wall-clock processing time. `shadow_only=True` on every
`AssembledVisitProposal`; this module has no product-write path and grants
no Stage 7 authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from math import hypot
from statistics import median
from typing import Literal

from mockingbird.observation.contracts import (
    EMPTY_CONFIDENCE_EVIDENCE,
    ConfidenceEvidenceSummary,
    TrackUpdate,
    VisitProposal,
    merge_confidence_evidence,
)

ASSEMBLER_VERSION = "tracklet-visit-assembler-v1"

BoundaryDecisionKind = Literal["merge_same_visit", "keep_separate", "ambiguous_boundary", "incompatible"]


def semantic_fingerprint(value: object) -> str:
    """Small, self-contained determinism helper -- deliberately duplicated
    from (never imported from) `replay.semantic_fingerprint` so this module
    stays independent of `replay.py`, matching every other Stage 6.x pure
    decision module's own dependency shape."""
    import json

    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    return sha256(encoded).hexdigest()


# --- Tracklet contract -------------------------------------------------------


@dataclass(frozen=True)
class Tracklet:
    """A provider-neutral, immutable, bounded summary of one *finalized,
    confirmed* track generation -- the only unit `assemble_visit_episodes`
    accepts.

    Contains only facts needed for Visit assembly: no implementation-
    specific tracker object (`frame_tracker._Track`/`TrackView` never leaks
    here), no species identity (only `broad_class`, exactly like every
    other Stage 6.x provider-neutral fact). Built exclusively by
    `build_tracklets` from already-emitted `TrackUpdate` facts for one
    `generation_id` in real use; tests construct it directly to exercise
    `classify_boundary`/`assemble_visit_episodes` against synthetic
    scenarios without needing a full tracker replay.
    """

    generation_id: str
    stream_id: str
    broad_class: str
    start_offset_ms: int
    end_offset_ms: int
    start_bounding_box: tuple[float, float, float, float]
    end_bounding_box: tuple[float, float, float, float]
    geometry_envelope: tuple[float, float, float, float]
    terminal_reason: str
    track_ids: tuple[str, ...]
    supporting_frame_ids: tuple[str, ...] = ()
    source_capture_frame_ids: tuple[str, ...] = ()
    connection_segment_ids: tuple[str, ...] = ()
    evidence_candidate_ids: tuple[str, ...] = ()
    strong_detector_frame_count: int = 0
    weak_detector_frame_count: int = 0
    tracker_supported_frame_count: int = 0
    # Genuine detector-negative frames: the detector actually ran
    # (`TrackUpdate.detector_ran=True`) and found nothing usable for this
    # track. Kept strictly separate from `detector_skipped_frame_count`
    # below -- an idle-cadence frame the detector never inspected is never
    # negative evidence (see `docs/tracklet-visit-assembly-contract.md`).
    negative_detector_frame_count: int = 0
    detector_skipped_frame_count: int = 0
    detector_confirmation_count: int = 0
    tracker_support_count: int = 0
    confidence: float | None = None
    # Stage 6.16's own anchor (`_Track.last_strong_detector_offset_ms`),
    # reused verbatim at this layer -- see `has_strong_evidence` and
    # `_graduated_and_stale` below.
    last_strong_detector_offset_ms: int | None = None
    zone_id: str | None = None
    ambiguous_start: bool = False
    # Detection Quality Accounting v1 (see
    # docs/detection-quality-accounting-contract.md). Defaulted to the
    # honestly-empty summary so every pre-existing direct `Tracklet(...)`
    # construction (this module's own tests build synthetic tracklets
    # without a full tracker replay) remains valid unchanged.
    confidence_evidence: ConfidenceEvidenceSummary = EMPTY_CONFIDENCE_EVIDENCE

    def __post_init__(self) -> None:
        if not self.generation_id or not self.stream_id or not self.broad_class:
            raise ValueError("invalid_tracklet_identity")
        if self.start_offset_ms < 0 or self.start_offset_ms > self.end_offset_ms:
            raise ValueError("invalid_tracklet_span")
        if not self.track_ids:
            raise ValueError("invalid_tracklet_lineage")
        for box in (self.start_bounding_box, self.end_bounding_box, self.geometry_envelope):
            if not _valid_box(box):
                raise ValueError("invalid_tracklet_geometry")

    @property
    def has_strong_evidence(self) -> bool:
        """Stage 6.16's own "graduated" concept, reused verbatim: whether
        this tracklet ever showed at least one genuinely strong detector
        hit at any point in its life."""
        return self.last_strong_detector_offset_ms is not None

    @property
    def duration_ms(self) -> int:
        return self.end_offset_ms - self.start_offset_ms


def build_tracklets(
    track_updates: tuple[TrackUpdate, ...],
    *,
    stream_id: str,
    connection_segment_by_frame_id: dict[str, str] | None = None,
    evidence_candidate_ids_by_generation: dict[str, tuple[str, ...]] | None = None,
    zone_id_by_generation: dict[str, str] | None = None,
) -> tuple[Tracklet, ...]:
    """Group already-emitted `TrackUpdate`s by `generation_id` and summarize
    every *confirmed* generation into one bounded `Tracklet`.

    Every `track_updates` entry is assumed to belong to `stream_id` -- exactly
    matching how one `ProviderNeutralFrameTracker`/`ReplayInput` is already
    scoped to exactly one stream; a future multi-stream aggregation caller
    calls this once per stream (like it must already call the tracker once
    per stream) and concatenates the results. `connection_segment_by_frame_id`
    /`evidence_candidate_ids_by_generation`/`zone_id_by_generation` are
    optional, purely-additive lookups a caller (typically the replay
    integration layer, which already has the frame/evidence context) may
    supply; omitted, every tracklet honestly reports empty/`None` for those
    facts rather than fabricating them.

    A generation that never reached `lifecycle_state == "confirmed"`
    (terminal `lifecycle_state == "rejected"`) is out of scope for Visit
    assembly: the tracker's own confirmation bar already decided it was not
    durable evidence, and second-guessing that here would be exactly the
    "redesign tracker confirmation" this stage must not do. A generation
    with no terminal (`status == "ended"`) update at all -- an incomplete/
    truncated input -- is likewise skipped; there is nothing finalized to
    summarize yet.

    Deterministic and input-order-independent: groups purely by
    `generation_id` regardless of the input tuple's own order, and sorts
    each generation's own updates by `(source_offset_ms, ...)` before
    deriving any fact.
    """
    by_generation: dict[str, list[TrackUpdate]] = {}
    for update in track_updates:
        by_generation.setdefault(update.generation_id, []).append(update)

    tracklets: list[Tracklet] = []
    for generation_id in sorted(by_generation):
        ordered = sorted(
            by_generation[generation_id],
            key=lambda item: (
                item.source_offset_ms if item.source_offset_ms is not None else -(2**63),
                item.status != "started",
                item.status == "ended",
            ),
        )
        terminal = next((item for item in reversed(ordered) if item.status == "ended"), None)
        if terminal is None or terminal.lifecycle_state != "ended":
            continue
        first = ordered[0]
        if first.source_offset_ms is None or terminal.source_offset_ms is None:
            continue
        if first.bounding_box is None or terminal.bounding_box is None:
            continue

        boxes = [item.bounding_box for item in ordered if item.bounding_box is not None]
        strong_count = weak_count = tracker_count = negative_count = skipped_count = 0
        last_strong_offset: int | None = None
        for item in ordered:
            if item.support_state == "strong_detector_supported":
                strong_count += 1
                if item.source_offset_ms is not None:
                    last_strong_offset = item.source_offset_ms if last_strong_offset is None else max(last_strong_offset, item.source_offset_ms)
            elif item.support_state == "weak_detector_supported":
                weak_count += 1
            elif item.support_state == "tracker_supported":
                tracker_count += 1
            elif item.support_state == "temporarily_lost" and item.status != "started":
                if item.detector_ran:
                    negative_count += 1
                else:
                    skipped_count += 1

        supporting_frame_ids = tuple(dict.fromkeys(
            frame_id for item in ordered for frame_id in item.supporting_frame_ids
        ))
        source_capture_frame_ids = tuple(dict.fromkeys(
            frame_id for item in ordered for frame_id in item.supporting_source_capture_frame_ids
        ))
        segment_lookup = connection_segment_by_frame_id or {}
        connection_segment_ids = tuple(sorted({
            segment_lookup[frame_id] for frame_id in supporting_frame_ids if frame_id in segment_lookup
        }))
        confidences = [item.confidence for item in ordered if item.confidence is not None]
        track_ids = tuple(dict.fromkeys(item.track_id for item in ordered if item.track_id))
        resolved_broad_class = terminal.broad_class or first.broad_class or "animal"
        confidence_evidence = confidence_evidence_from_terminal_update(
            terminal,
            max_confidence=max(confidences) if confidences else None,
            broad_class=resolved_broad_class,
        )

        tracklets.append(Tracklet(
            generation_id=generation_id,
            stream_id=stream_id,
            broad_class=resolved_broad_class,
            start_offset_ms=first.source_offset_ms,
            end_offset_ms=terminal.source_offset_ms,
            start_bounding_box=first.bounding_box,
            end_bounding_box=terminal.bounding_box,
            geometry_envelope=_envelope(boxes) if boxes else terminal.bounding_box,
            terminal_reason=terminal.terminal_reason or "unknown",
            track_ids=track_ids,
            supporting_frame_ids=supporting_frame_ids,
            source_capture_frame_ids=source_capture_frame_ids,
            connection_segment_ids=connection_segment_ids,
            evidence_candidate_ids=tuple((evidence_candidate_ids_by_generation or {}).get(generation_id, ())),
            strong_detector_frame_count=strong_count,
            weak_detector_frame_count=weak_count,
            tracker_supported_frame_count=tracker_count,
            negative_detector_frame_count=negative_count,
            detector_skipped_frame_count=skipped_count,
            detector_confirmation_count=terminal.detector_confirmation_count,
            tracker_support_count=terminal.tracker_support_count,
            confidence=max(confidences) if confidences else None,
            last_strong_detector_offset_ms=last_strong_offset,
            zone_id=(zone_id_by_generation or {}).get(generation_id),
            ambiguous_start=any(item.ambiguous_start for item in ordered),
            confidence_evidence=confidence_evidence,
        ))
    return tuple(tracklets)


def confidence_evidence_from_terminal_update(
    terminal: TrackUpdate,
    *,
    max_confidence: float | None,
    broad_class: str,
) -> ConfidenceEvidenceSummary:
    """Build one generation's `ConfidenceEvidenceSummary` from its own
    terminal `TrackUpdate` -- which already carries this generation's full
    cumulative-so-far `confidence_samples`/`max_consecutive_detector_
    confirmed_frames` (see docs/detection-quality-accounting-contract.md).
    `max_confidence` is the exact value `build_tracklets` already computed
    for `Tracklet.confidence` -- reused, not recomputed, so the two can
    never disagree.

    Public (not module-private): a terminal `TrackUpdate`'s own cumulative
    fields are already sufficient to build a complete `ConfidenceEvidence
    Summary` with no other update needed (`terminal.confidence` is itself
    the generation's running max -- see `frame_tracker._observe_detection`'s
    `track.confidence = max(track.confidence or 0.0, ...)`), which is
    exactly why `mockingbird.observation.counterfactual_lineage` reuses this
    function verbatim for a *rejected* (never-confirmed) generation too,
    rather than duplicating this logic a second time (Rejected / Suppressed
    Detection Attribution v1, see docs/rejected-detection-attribution
    -contract.md).

    `strong_detection_count`/`weak_detection_count` are deliberately
    derived from `samples` (each one `is_strong`-tagged at the moment it was
    recorded) rather than reusing the existing frame-scanning `strong_count`/
    `weak_count` locals this function's caller also computes for `Tracklet.
    strong_detector_frame_count`/`weak_detector_frame_count`: those count
    *frames* (a track's synthetic `finalize()`/reconnect-boundary echo update
    can legitimately re-report the same already-counted `support_state` at
    the same offset as the last real one, so frame counts can exceed the
    real detection count -- proven by
    `test_track_metrics_expose_raw_fragmentation_independent_of_assembly`),
    while `samples` is appended exactly once per genuine matched detection
    and therefore never double-counts.

    A terminal update reconstructed from a pre-Detection-Quality-Accounting
    record (for example a legacy `replay-report.json` loaded through the
    Stage 6.17 `rescore_visit_truth.py` JSON-reconstruction pattern) simply
    has an empty `confidence_samples` tuple and a zero streak -- the dataclass
    defaults -- so this honestly reports no samples / no mean / no median /
    no strong-weak split rather than fabricating them, while `detection_
    count`/`max_confidence` remain exact because they were already recorded
    before this contract existed.
    """

    samples = terminal.confidence_samples
    sample_confidences = [sample.confidence for sample in samples]
    offsets = [sample.source_offset_ms for sample in samples if sample.source_offset_ms is not None]
    detection_count = terminal.detector_confirmation_count
    if samples:
        strong_detection_count: int | None = sum(1 for sample in samples if sample.is_strong)
        weak_detection_count: int | None = sum(1 for sample in samples if not sample.is_strong)
        max_consecutive: int | None = terminal.max_consecutive_detector_confirmed_frames
    elif detection_count > 0:
        # Detections genuinely happened (the exact, always-recorded count
        # proves it) but no per-detection sample survived to say which were
        # strong/weak, or how many were consecutive -- honestly unknown, not
        # zero (see the `strong_detection_count` docstring on
        # `ConfidenceEvidenceSummary`). A legacy-reconstructed `TrackUpdate`
        # (for example via the Stage 6.17 `rescore_visit_truth.py` JSON-
        # reconstruction pattern) has no `confidence_samples` at all and its
        # `max_consecutive_detector_confirmed_frames` is just that field's
        # own backward-compatible dataclass default (`0`), not a real
        # measurement.
        strong_detection_count = None
        weak_detection_count = None
        max_consecutive = None
    else:
        strong_detection_count = 0
        weak_detection_count = 0
        max_consecutive = 0
    return ConfidenceEvidenceSummary(
        detection_count=detection_count,
        max_confidence=max_confidence,
        mean_confidence=(sum(sample_confidences) / len(sample_confidences)) if sample_confidences else None,
        median_confidence=median(sample_confidences) if sample_confidences else None,
        strong_detection_count=strong_detection_count,
        weak_detection_count=weak_detection_count,
        max_consecutive_detector_confirmed_frames=max_consecutive,
        samples=samples,
        broad_class=broad_class,
        first_detection_offset_ms=min(offsets) if offsets else None,
        last_detection_offset_ms=max(offsets) if offsets else None,
        sample_truncated=len(samples) < detection_count,
    )


# --- Assembly decision contract ----------------------------------------------


@dataclass(frozen=True)
class VisitAssemblyConfiguration:
    """Bounded, general-purpose policy for whether two temporally-adjacent
    confirmed tracklets belong to one sustained Visit. Every bound is either
    reused directly from an already-calibrated Stage 6.x constant, or an
    explicitly-derived multiple of one -- this codebase's own established
    convention (see docs/sustained-visit-continuity-contract.md) for not
    inventing new, scene-specific magic numbers. See
    docs/tracklet-visit-assembly-contract.md for the full derivation of each.
    """

    # Reuses `TrackerConfiguration.maximum_weak_support_span_ms`'s own
    # already-justified default (Stage 6.16: "long enough to bridge a real
    # subject's early confidence dips") as the gap bound within which,
    # combined with compatible geometry and no separation evidence, two
    # tracklets confidently belong to one Visit.
    merge_gap_ms: int = 15_000
    # An explicitly-derived 3x multiple of `merge_gap_ms`, mirroring the
    # exact derivation Stage 6.16 used for `maximum_weak_support_span_ms`
    # itself (3x `maximum_unsupported_detector_ms`): a gap this long, even
    # with compatible geometry, is not confidently one continuous Visit --
    # but is not confidently two separate ones either, absent stronger
    # evidence. See "Ambiguity" below.
    ambiguous_gap_ms: int = 45_000
    # Bounded-displacement-budget model for "compatible geometry across a
    # gap": a fixed base allowance (measurement/box jitter, the same shape
    # as the tracker's own per-frame `maximum_centroid_distance`) plus a
    # per-second allowance (an implied bounded motion speed), capped. Wider
    # than one frame-to-frame association step deliberately: this spans a
    # real multi-second gap, not one analysis frame.
    geometry_gap_tolerance_base: float = 0.12
    geometry_gap_tolerance_per_second: float = 0.05
    geometry_gap_tolerance_cap: float = 0.6
    # Reused from `ReconnectBridgeConfig.maximum_reconnect_size_change_
    # ratio`'s own sibling bound, widened slightly (0.5 -> 0.65) for the
    # same reason the centroid tolerance above is widened.
    maximum_size_change_ratio: float = 0.65
    # A tracklet that ever showed genuinely strong detector evidence
    # (`Tracklet.has_strong_evidence`, Stage 6.16's own "graduated" concept
    # reused verbatim) is normally a *more* trustworthy merge anchor --
    # unless its own strong claim has gone stale (no strong proof for a
    # while before it ended), meaning it is coasting on the tracker's own
    # widened bounded-tolerance mechanism rather than fresh confidence, and
    # a confident merge should not be built on stale credibility alone.
    # Reuses `TrackerConfiguration.maximum_unsupported_detector_ms`'s own
    # default (5000ms) as the staleness bound -- the tracker's own "how long
    # may a confirmed subject go with no fresh strong proof" number, reused
    # for an analogous purpose one layer up, not a new one.
    graduated_freshness_bound_ms: int = 5_000
    # Hard absolute safety cap on one assembled episode's total span,
    # independent of and much larger than any individual gap bound above --
    # guards against pathological unbounded chain growth. Generous enough
    # that it does not affect any real or synthetic scenario validated here
    # (the longest real reviewed Visit across the four acceptance sessions
    # is ~5 minutes).
    maximum_episode_duration_ms: int = 1_200_000

    def __post_init__(self) -> None:
        if min(
            self.merge_gap_ms, self.ambiguous_gap_ms, self.graduated_freshness_bound_ms,
            self.maximum_episode_duration_ms,
        ) < 1:
            raise ValueError("invalid_assembly_bound")
        if self.ambiguous_gap_ms < self.merge_gap_ms:
            raise ValueError("invalid_assembly_bound")
        if not 0.0 <= self.geometry_gap_tolerance_base <= self.geometry_gap_tolerance_cap:
            raise ValueError("invalid_assembly_bound")
        if self.geometry_gap_tolerance_per_second < 0.0:
            raise ValueError("invalid_assembly_bound")
        if not 0.0 < self.maximum_size_change_ratio <= 5.0:
            raise ValueError("invalid_assembly_bound")


@dataclass(frozen=True)
class BoundaryDecision:
    """One deterministic classification of whether tracklet `earlier` and
    tracklet `later` (temporally adjacent by construction: callers only ever
    ask about a pair where `earlier` does not start after `later`) belong to
    the same Visit episode."""

    earlier_generation_id: str
    later_generation_id: str
    decision: BoundaryDecisionKind
    reason: str
    gap_ms: int | None = None


def classify_boundary(earlier: Tracklet, later: Tracklet, config: VisitAssemblyConfiguration | None = None) -> BoundaryDecision:
    """Classify the boundary between two tracklets using only their own
    bounded facts -- never species identity, an absolute path, one feeder
    geometry, or wall-clock time. See docs/tracklet-visit-assembly-contract.md
    "Assembly decision" for the full evidence catalogue this implements.

    Order-independent: if `later` actually starts no later than `earlier`,
    the two are swapped first so the result is identical either way.
    """
    config = config or VisitAssemblyConfiguration()
    if later.start_offset_ms < earlier.start_offset_ms:
        earlier, later = later, earlier

    def _decision(kind: BoundaryDecisionKind, reason: str, *, gap_ms: int | None = None) -> BoundaryDecision:
        return BoundaryDecision(earlier.generation_id, later.generation_id, kind, reason, gap_ms)

    # --- structural incompatibility: never even a close call ---------------
    if earlier.stream_id != later.stream_id:
        return _decision("incompatible", "different_stream")
    if _temporal_overlap(earlier, later):
        # Two confirmed tracklets active at overlapping times are either two
        # genuinely simultaneous/crossing subjects, or an upstream tracker
        # association artifact -- either way, not this layer's decision to
        # make (see "Do not redesign tracker association").
        return _decision("incompatible", "temporal_overlap")
    if earlier.broad_class != later.broad_class:
        return _decision("incompatible", "broad_class_mismatch")
    if earlier.zone_id is not None and later.zone_id is not None and earlier.zone_id != later.zone_id:
        return _decision("incompatible", "zone_mismatch")

    gap_ms = later.start_offset_ms - earlier.end_offset_ms

    # --- separation evidence: checked before any positive-continuity path --
    if earlier.terminal_reason == "negative_interval_reentry":
        # The tracker itself already confirmed absence (genuine, repeated,
        # detector-evaluated negative frames) right at this tracklet's own
        # boundary -- direct, positive evidence of discontinuity.
        return _decision("keep_separate", "detector_confirmed_negative_interval", gap_ms=gap_ms)

    if not _geometry_compatible(earlier, later, gap_ms, config):
        return _decision("keep_separate", "spatial_discontinuity", gap_ms=gap_ms)

    if gap_ms > config.ambiguous_gap_ms:
        return _decision("keep_separate", "gap_exceeds_ambiguous_window", gap_ms=gap_ms)

    # --- positive continuity, bounded by evidence freshness -----------------
    if gap_ms <= config.merge_gap_ms and not _graduated_and_stale(earlier, config):
        return _decision("merge_same_visit", "bounded_gap_compatible_geometry", gap_ms=gap_ms)

    # Compatible geometry, no explicit separation evidence, but the gap is
    # beyond the confident-merge window or `earlier` is coasting on stale
    # graduated credibility: cannot safely tell. Preserve the ambiguity
    # rather than guessing -- see "Ambiguity" in the contract doc.
    reason = "stale_graduated_evidence" if _graduated_and_stale(earlier, config) else "gap_beyond_confident_merge_window"
    return _decision("ambiguous_boundary", reason, gap_ms=gap_ms)


def _temporal_overlap(earlier: Tracklet, later: Tracklet) -> bool:
    return later.start_offset_ms < earlier.end_offset_ms


def _geometry_compatible(
    earlier: Tracklet, later: Tracklet, gap_ms: int, config: VisitAssemblyConfiguration,
) -> bool:
    return boxes_geometry_compatible(earlier.end_bounding_box, later.start_bounding_box, gap_ms, config)


def boxes_geometry_compatible(
    earlier_box: tuple[float, float, float, float],
    later_box: tuple[float, float, float, float],
    gap_ms: int,
    config: VisitAssemblyConfiguration,
) -> bool:
    """The exact box-jitter/size-change tolerance test `classify_boundary`
    already applies between two tracklets' own end/start boxes -- promoted
    to a public, `Tracklet`-independent function (raw boxes only) so a
    sibling diagnostic can reuse the identical, already-calibrated policy
    rather than re-deriving a second copy of the same tolerance formula.
    Mirrors `confidence_evidence_from_terminal_update`'s own "promoted from
    module-private to shared for exactly this reuse" precedent (see
    docs/rejected-detection-attribution-contract.md)."""

    tolerance = geometry_gap_tolerance(gap_ms, config)
    if centroid_distance(earlier_box, later_box) > tolerance:
        return False
    earlier_area = box_area(earlier_box)
    later_area = box_area(later_box)
    if earlier_area <= 0.0 or later_area <= 0.0:
        return True  # a degenerate box fact must not veto on size alone
    return abs(later_area - earlier_area) / earlier_area <= config.maximum_size_change_ratio


def geometry_gap_tolerance(gap_ms: int, config: VisitAssemblyConfiguration) -> float:
    """The bounded-displacement-budget tolerance for a gap of `gap_ms`
    between two tracklets -- see `VisitAssemblyConfiguration`'s own
    `geometry_gap_tolerance_*` fields for the derivation. Extracted so
    `boxes_geometry_compatible` and a caller comparing raw boxes directly
    (for example `encounter_accounting.py`) share one formula."""

    return min(
        config.geometry_gap_tolerance_cap,
        config.geometry_gap_tolerance_base + config.geometry_gap_tolerance_per_second * (gap_ms / 1000.0),
    )


def _graduated_and_stale(tracklet: Tracklet, config: VisitAssemblyConfiguration) -> bool:
    if tracklet.last_strong_detector_offset_ms is None:
        return False  # provisional: never claimed strong confidence, nothing to go stale from
    return (tracklet.end_offset_ms - tracklet.last_strong_detector_offset_ms) > config.graduated_freshness_bound_ms


def centroid_distance(
    left: tuple[float, float, float, float], right: tuple[float, float, float, float],
) -> float:
    left_center = ((left[0] + left[2]) / 2.0, (left[1] + left[3]) / 2.0)
    right_center = ((right[0] + right[2]) / 2.0, (right[1] + right[3]) / 2.0)
    return hypot(left_center[0] - right_center[0], left_center[1] - right_center[1])


def box_area(box: tuple[float, float, float, float]) -> float:
    return max(0.0, box[2] - box[0]) * max(0.0, box[3] - box[1])


def _envelope(boxes: list[tuple[float, float, float, float]]) -> tuple[float, float, float, float]:
    return (
        min(box[0] for box in boxes), min(box[1] for box in boxes),
        max(box[2] for box in boxes), max(box[3] for box in boxes),
    )


def _valid_box(box: tuple[float, float, float, float]) -> bool:
    # Mirrors `frame_tracker._valid_box`/`replay._valid_box` exactly (strict
    # positive area) -- every real tracker-produced box already satisfies
    # this; kept strict here too rather than loosened for convenience.
    return len(box) == 4 and all(0.0 <= value <= 1.0 for value in box) and box[0] < box[2] and box[1] < box[3]


# --- VisitProposal lineage ----------------------------------------------------


@dataclass(frozen=True)
class AssembledVisitProposal:
    """One bounded shadow Visit proposal assembled from one or more
    confirmed tracklets genuinely believed to belong to the same sustained
    appearance. `shadow_only=True` always -- no product-write path, no
    Stage 7 authority (see docs/tracklet-visit-assembly-contract.md)."""

    proposal_id: str
    stream_id: str
    broad_class: str
    start_offset_ms: int
    end_offset_ms: int
    constituent_generation_ids: tuple[str, ...]
    constituent_track_ids: tuple[str, ...]
    supporting_frame_ids: tuple[str, ...]
    source_capture_frame_ids: tuple[str, ...]
    evidence_candidate_ids: tuple[str, ...]
    # Assembly decision provenance: one `BoundaryDecision` per internal
    # tracklet-to-tracklet merge that built this proposal up (empty for a
    # singleton, `len(constituent_generation_ids) - 1` entries for a chain).
    assembly_decisions: tuple[BoundaryDecision, ...]
    zone_id: str | None = None
    # Ambiguity/limitation facts: other proposals this one shares an
    # `ambiguous_boundary` with (conservatively kept separate, but the
    # relationship is not silently discarded), plus honest, general
    # disclosure facts about the evidence this proposal was built from.
    ambiguous_adjacent_proposal_ids: tuple[str, ...] = ()
    limitation_facts: tuple[str, ...] = ()
    shadow_only: bool = True
    # Detection Quality Accounting v1 (see
    # docs/detection-quality-accounting-contract.md): the merged confidence/
    # evidence accounting across every constituent tracklet -- evidence for
    # a quality-accounting pass or a *shadow* admission-policy evaluator,
    # never itself observational authority (see "The truth boundary" in
    # product-doctrine.md). Defaulted so every pre-existing direct
    # `AssembledVisitProposal(...)` construction remains valid unchanged.
    confidence_evidence: ConfidenceEvidenceSummary = EMPTY_CONFIDENCE_EVIDENCE
    # Visit Continuity / Provisional Admission Fix v1 (see
    # docs/tracklet-visit-assembly-contract.md "Episode finality"): whether
    # this proposal's own *tail* boundary is not yet safe to treat as final
    # -- a same-encounter continuation tracklet could still be assembled
    # onto it later, which would change `constituent_generation_ids` (and
    # therefore `proposal_id`) to a larger, more complete set. `False`
    # unless the caller explicitly supplies `known_horizon_ms` to
    # `assemble_visit_episodes` (every pre-existing caller -- `replay.py`,
    # every existing test, an offline/already-complete recording -- omits
    # it, so this field defaults to `False` and every prior behavior is
    # unchanged). Only a caller re-running assembly incrementally over a
    # still-live stream (`engine_runtime.py`, `candidate_visit_authority_cli.py`)
    # ever sets it `True`, and only for as long as the episode's own
    # continuation window (`VisitAssemblyConfiguration.ambiguous_gap_ms`,
    # the exact bound the assembler's own merge algorithm already uses to
    # decide whether a later tracklet could still attach) remains open.
    continuation_pending: bool = False

    def __post_init__(self) -> None:
        if not self.shadow_only:
            raise ValueError("assembled_visit_proposal_must_be_shadow_only")
        if not self.constituent_generation_ids:
            raise ValueError("assembled_visit_proposal_requires_constituents")
        if len(self.assembly_decisions) != len(self.constituent_generation_ids) - 1:
            raise ValueError("assembled_visit_proposal_decision_count_mismatch")


@dataclass(frozen=True)
class VisitAssemblyResult:
    """Bounded assembly-stage metrics plus the assembled proposals
    themselves -- kept separate from tracker-level metrics deliberately
    (see replay.py's Track/Assembly/Visit-truth metrics sections): tracker
    fragmentation must never be hidden merely because assembly repairs it."""

    proposals: tuple[AssembledVisitProposal, ...]
    boundary_decisions: tuple[BoundaryDecision, ...]
    tracklets_input: int
    episode_merges: int
    separate_decisions: int
    ambiguous_decisions: int
    incompatible_decisions: int

    @property
    def assembled_proposal_count(self) -> int:
        return len(self.proposals)


def assemble_visit_episodes(
    tracklets: tuple[Tracklet, ...],
    config: VisitAssemblyConfiguration | None = None,
    *,
    known_horizon_ms: int | None = None,
) -> VisitAssemblyResult:
    """Given a deterministic (but arbitrarily-ordered) sequence of finalized,
    confirmed tracklets, decide which adjacent ones belong to one sustained
    genuine appearance and assemble one bounded shadow `AssembledVisitProposal`
    per resulting episode.

    Deterministic and product-write-free: never opens a database, a
    filesystem path beyond what the caller already supplied as bounded
    facts, or a network connection; every decision is a pure function of the
    supplied `Tracklet`s, `config`, and `known_horizon_ms`.

    Algorithm (see docs/tracklet-visit-assembly-contract.md for the full
    rationale): tracklets are first sorted into one deterministic total
    order, independent of the caller's own input order. Processing them in
    that order, each tracklet is compared only against the *tail* tracklet
    of every still-"open" episode sharing its `(stream_id, broad_class)` --
    never against a closed one, and never against an episode currently
    overlapping it in time (that comparison is `incompatible` by
    construction and never touches the episode). An episode's tail closes to
    further comparison once the gap since its own end exceeds
    `config.ambiguous_gap_ms` (nothing later could ever be closer -- a
    bounded, monotonic argument, not a heuristic). This lets two genuinely
    separate simultaneous/crossing subjects each keep accumulating their own
    fragments correctly even while interleaved in time with each other.

    `known_horizon_ms` (Visit Continuity / Provisional Admission Fix v1, see
    docs/tracklet-visit-assembly-contract.md "Episode finality"): an
    optional, purely-additive, source-offset-relative fact -- never a
    wall-clock read, matching every other bound in this module -- naming the
    latest point in the stream the caller has actually observed so far
    (live or replay, but only meaningful for a caller that may still receive
    *more* tracklets later; an offline pass over an already-complete
    recording correctly omits it). When supplied, every resulting
    proposal's own `continuation_pending` reuses exactly the same
    `config.ambiguous_gap_ms` bound the algorithm above already uses to
    decide whether a later tracklet could still attach to that proposal's
    tail -- so a caller re-running this function incrementally over a still
    -live stream can tell "this proposal's boundary is final" apart from
    "a same-encounter continuation could still arrive and change this
    proposal's own constituent set." Omitted (the default), every proposal
    reports `continuation_pending=False`, exactly the prior (pre-fix)
    behavior -- every existing caller (`replay.py`, every pre-existing
    test) is unaffected.
    """
    config = config or VisitAssemblyConfiguration()
    ordered = sorted(
        tracklets,
        key=lambda item: (item.stream_id, item.broad_class, item.start_offset_ms, item.end_offset_ms, item.generation_id),
    )

    episodes: list[list[Tracklet]] = []
    episode_decisions: list[list[BoundaryDecision]] = []
    open_by_class: dict[tuple[str, str], list[int]] = {}
    ambiguous_links: dict[int, set[int]] = {}
    all_decisions: list[BoundaryDecision] = []
    merges = separates = ambiguous_count = incompatible_count = 0

    for tracklet in ordered:
        key = (tracklet.stream_id, tracklet.broad_class)
        open_indices = open_by_class.get(key, [])
        still_open = [
            index for index in open_indices
            if tracklet.start_offset_ms - episodes[index][-1].end_offset_ms <= config.ambiguous_gap_ms
        ]
        open_by_class[key] = still_open

        merge_candidates: list[tuple[int, BoundaryDecision]] = []
        ambiguous_candidates: list[tuple[int, BoundaryDecision]] = []
        for index in still_open:
            decision = classify_boundary(episodes[index][-1], tracklet, config)
            all_decisions.append(decision)
            if decision.decision == "incompatible":
                incompatible_count += 1
            elif decision.decision == "keep_separate":
                separates += 1
            elif decision.decision == "ambiguous_boundary":
                ambiguous_candidates.append((index, decision))
            else:
                merge_candidates.append((index, decision))

        chosen: tuple[int, BoundaryDecision] | None = None
        if merge_candidates:
            merge_candidates.sort(key=lambda pair: (
                pair[1].gap_ms if pair[1].gap_ms is not None else 2**63, episodes[pair[0]][-1].generation_id,
            ))
            chosen = merge_candidates[0]
            # A genuine multi-way merge tie is exactly "cannot safely
            # distinguish which prior episode this continues" -- one
            # candidate must still be picked to stay deterministic and
            # bounded, but every other equally-eligible one is recorded as
            # an ambiguous cross-link rather than silently dropped.
            for other_index, _ in merge_candidates[1:]:
                ambiguous_links.setdefault(other_index, set()).add(chosen[0])
                ambiguous_links.setdefault(chosen[0], set()).add(other_index)

        if chosen is not None:
            index, decision = chosen
            prospective_span = tracklet.end_offset_ms - episodes[index][0].start_offset_ms
            if prospective_span <= config.maximum_episode_duration_ms:
                episodes[index].append(tracklet)
                episode_decisions[index].append(decision)
                merges += 1
                continue
            # Bounded safety cap reached: do not extend this episode
            # further, even though the pairwise boundary itself qualified --
            # start a new one instead (see `maximum_episode_duration_ms`).
            separates += 1

        new_index = len(episodes)
        episodes.append([tracklet])
        episode_decisions.append([])
        open_by_class[key].append(new_index)
        if ambiguous_candidates:
            ambiguous_count += len(ambiguous_candidates)
            for index, _ in ambiguous_candidates:
                ambiguous_links.setdefault(new_index, set()).add(index)
                ambiguous_links.setdefault(index, set()).add(new_index)

    proposal_ids = [_proposal_id(members) for members in episodes]
    proposals = tuple(
        _build_proposal(
            members, episode_decisions[index], proposal_ids, ambiguous_links.get(index, set()),
            known_horizon_ms=known_horizon_ms, ambiguous_gap_ms=config.ambiguous_gap_ms,
        )
        for index, members in enumerate(episodes)
    )
    return VisitAssemblyResult(
        proposals=proposals,
        boundary_decisions=tuple(all_decisions),
        tracklets_input=len(tracklets),
        episode_merges=merges,
        separate_decisions=separates,
        ambiguous_decisions=ambiguous_count,
        incompatible_decisions=incompatible_count,
    )


def _proposal_id(members: list[Tracklet]) -> str:
    ordered_ids = tuple(item.generation_id for item in sorted(members, key=lambda item: (item.start_offset_ms, item.generation_id)))
    return "visit-episode:" + sha256("|".join((ASSEMBLER_VERSION, *ordered_ids)).encode()).hexdigest()[:24]


def _build_proposal(
    members: list[Tracklet],
    decisions: list[BoundaryDecision],
    proposal_ids: list[str],
    ambiguous_with: set[int],
    *,
    known_horizon_ms: int | None,
    ambiguous_gap_ms: int,
) -> AssembledVisitProposal:
    ordered_members = sorted(members, key=lambda item: (item.start_offset_ms, item.generation_id))
    limitation_facts: list[str] = []
    if any(item.ambiguous_start for item in ordered_members):
        limitation_facts.append("contains_ambiguous_start_tracklet")
    if any(not item.has_strong_evidence for item in ordered_members):
        limitation_facts.append("contains_provisional_only_tracklet")
    if len(ordered_members) > 1:
        limitation_facts.append("assembled_from_multiple_tracklets")
    end_offset_ms = max(item.end_offset_ms for item in ordered_members)
    return AssembledVisitProposal(
        proposal_id=_proposal_id(members),
        stream_id=ordered_members[0].stream_id,
        broad_class=ordered_members[0].broad_class,
        start_offset_ms=ordered_members[0].start_offset_ms,
        end_offset_ms=end_offset_ms,
        constituent_generation_ids=tuple(item.generation_id for item in ordered_members),
        constituent_track_ids=tuple(dict.fromkeys(
            track_id for item in ordered_members for track_id in item.track_ids
        )),
        supporting_frame_ids=tuple(dict.fromkeys(
            frame_id for item in ordered_members for frame_id in item.supporting_frame_ids
        )),
        source_capture_frame_ids=tuple(dict.fromkeys(
            frame_id for item in ordered_members for frame_id in item.source_capture_frame_ids
        )),
        evidence_candidate_ids=tuple(dict.fromkeys(
            candidate_id for item in ordered_members for candidate_id in item.evidence_candidate_ids
        )),
        assembly_decisions=tuple(decisions),
        zone_id=next((item.zone_id for item in ordered_members if item.zone_id is not None), None),
        ambiguous_adjacent_proposal_ids=tuple(sorted({proposal_ids[index] for index in ambiguous_with})),
        limitation_facts=tuple(limitation_facts),
        confidence_evidence=merge_confidence_evidence(
            tuple(item.confidence_evidence for item in ordered_members)
        ),
        # `<=`, mirroring the exact "still open" comparison `assemble_visit_
        # episodes` itself already uses (`gap since episode end <=
        # config.ambiguous_gap_ms`): stays pending until the caller's own
        # observed horizon has moved strictly past the last point at which a
        # later tracklet could still have been compared against this
        # proposal's tail and found mergeable.
        continuation_pending=(
            known_horizon_ms is not None and (known_horizon_ms - end_offset_ms) <= ambiguous_gap_ms
        ),
    )


def project_to_visit_proposal(assembled: AssembledVisitProposal, *, source_id: str = "shadow-visit-assembly") -> VisitProposal:
    """A pragmatic, intentionally lossy projection onto the existing,
    unmodified `contracts.VisitProposal`/`replay.ReplayRunner` shape, used
    only so the already-proven, unmodified Stage 6.17 Visit-truth matcher
    (`replay._match`) can score an assembled proposal exactly like any other
    -- never a replacement for `AssembledVisitProposal`, which remains the
    authoritative lineage record. `track_generation_id` carries only the
    *first* constituent generation for informational continuity with
    existing per-generation tooling; the full set lives on
    `AssembledVisitProposal.constituent_generation_ids`."""
    return VisitProposal(
        proposal_key=assembled.proposal_id,
        source_id=source_id,
        stream_id=assembled.stream_id,
        evidence_media_asset_ids=assembled.evidence_candidate_ids,
        reason="assembled_visit_episode",
        start_offset_ms=assembled.start_offset_ms,
        end_offset_ms=assembled.end_offset_ms,
        zone_id=assembled.zone_id,
        shadow_only=True,
        idempotency_key=assembled.proposal_id,
        broad_subject_class=assembled.broad_class,
        track_generation_id=assembled.constituent_generation_ids[0],
        detector_provenance=None,
        tracker_provenance=ASSEMBLER_VERSION,
        supporting_frame_ids=assembled.supporting_frame_ids,
        terminal_reason=None,
        provider_key=None,
        provider_version=ASSEMBLER_VERSION,
        supporting_source_capture_frame_ids=assembled.source_capture_frame_ids,
        confidence_evidence=assembled.confidence_evidence,
    )
