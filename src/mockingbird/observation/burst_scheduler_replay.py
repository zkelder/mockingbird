"""Deterministic, shadow-only historical replay of Stage 6.9 burst-scheduler
decisions against an already-captured Stage 6.6/6.8 capture-session manifest.

This module is pure: it takes already-loaded manifest/annotation dicts (the
same shape `temporal_capture_io.load_capture_manifest`/
`temporal_review_io`'s annotation reader return) and produces a report; it
never opens a network connection, decodes an image, or writes a file (see
`burst_scheduler_replay_io.py`/`burst_scheduler_replay_cli.py`). It never
rewrites a historical capture or annotation artifact -- every input is read
only, and every output is a new, separate report.

It deliberately reuses `mockingbird.observation.temporal_capture.
upgrade_capture_manifest_timeline` unchanged for reconnect-safe chronological
ordering (a manifest's raw, connection-local `sequence` resets on every HTTP
reconnect and is not comparable across the whole session -- see
docs/session-timeline-contract.md) rather than reimplementing that ordering
logic; this stage adds no new session-timeline derivation of its own.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json

from mockingbird.observation.burst_scheduler import (
    ISSUING_DECISIONS,
    BurstDecision,
    BurstOpportunity,
    BurstScheduler,
    BurstSchedulerConfig,
)
from mockingbird.observation.temporal_capture import (
    TRIGGER_HIGH_RESOLUTION_BURST,
    TRIGGER_MOTION_PROPOSAL_GENERATED,
    TRIGGER_SHADOW_TRACK_EVENT,
    TemporalCaptureError,
    upgrade_capture_manifest_timeline,
)

REPORT_SCHEMA_VERSION = 1
REPLAY_VERSION = "burst-schedule-replay-v1"

MAX_FRAMES = 20_000
MAX_GENERATIONS_PER_FRAME = 64
MAX_ANNOTATION_FRAMES = 20_000
MAX_LOST_FRAME_IDS = 256


class BurstScheduleReplayError(ValueError):
    """A bounded burst-schedule-replay validation or execution failure code."""


def _fingerprint(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(encoded).hexdigest()


# --------------------------------------------------------------------------
# Reconstruction
# --------------------------------------------------------------------------


def reconstruct_opportunities(manifest: dict[str, object], *, session_id: str) -> tuple[BurstOpportunity, ...]:
    """Reconstruct one `BurstOpportunity` per retained triggering frame from
    an already-loaded capture-session-manifest dict, ordered by the
    reconnect-safe session timeline.

    The Stage 6.6/6.8 manifest schema records one flat `detection_boxes`
    list and one `track_generation_ids` set per retained frame -- not which
    box belongs to which generation, and not which generation a given box
    belongs to. Reconstructing one opportunity per (frame, generation) pair
    would multiply near-identical opportunities sharing the same substituted
    "best box" whenever several generations are simultaneously active on one
    frame (common during a busy real session), inflating opportunity volume
    well past what the live per-generation `TrackUpdate` path would ever
    raise. This function instead reconstructs the more conservative,
    honestly-disclosed one-opportunity-per-frame view: the frame's single
    highest-scoring detection box, attributed to one representative
    generation (the lexicographically first of the frame's active
    generation ids -- an arbitrary but deterministic choice, since the
    manifest cannot say which generation that box truly belongs to).
    `broad_class` is reconstructed as `"animal"` for every opportunity (the
    manifest does not persist a per-box class label). `motion_change_score`
    is reconstructed as `1.0`/`None` from whether a motion proposal fired on
    the frame, not a continuous score, since the manifest does not retain
    the underlying pixel-difference magnitude.
    """

    if not session_id:
        raise BurstScheduleReplayError("invalid_replay_session_id")
    try:
        upgraded = upgrade_capture_manifest_timeline(dict(manifest))
    except TemporalCaptureError as error:
        raise BurstScheduleReplayError(f"invalid_capture_manifest:{error}") from error

    raw_frames = upgraded.get("frames")
    if not isinstance(raw_frames, list) or len(raw_frames) > MAX_FRAMES:
        raise BurstScheduleReplayError("invalid_capture_manifest_frames")
    stream_id = "unknown-stream"
    config = upgraded.get("config")
    if isinstance(config, dict) and isinstance(config.get("stream_id"), str) and config["stream_id"]:
        stream_id = config["stream_id"]

    ordered = sorted(
        (item for item in raw_frames if isinstance(item, dict)),
        key=lambda item: (
            _int_or(item.get("session_sequence"), 0),
            _int_or(item.get("sequence"), 0),
            str(item.get("frame_id") or ""),
        ),
    )

    opportunities: list[BurstOpportunity] = []
    for frame in ordered:
        triggers = frame.get("trigger_reasons") or ()
        if not isinstance(triggers, (list, tuple)):
            continue
        if TRIGGER_SHADOW_TRACK_EVENT not in triggers and TRIGGER_HIGH_RESOLUTION_BURST not in triggers:
            continue
        generations = frame.get("track_generation_ids") or ()
        if not isinstance(generations, (list, tuple)) or not generations:
            continue
        generations = generations[:MAX_GENERATIONS_PER_FRAME]
        frame_id = str(frame.get("frame_id") or "")
        if not frame_id:
            continue

        boxes = frame.get("detection_boxes") or ()
        geometry: tuple[float, float, float, float] | None = None
        score: float | None = None
        if isinstance(boxes, (list, tuple)) and boxes:
            best = max((item for item in boxes if isinstance(item, (list, tuple)) and len(item) >= 5), key=lambda item: item[4], default=None)
            if best is not None:
                geometry = tuple(round(float(value), 6) for value in best[:4])  # type: ignore[assignment]
                score = round(float(best[4]), 6)
        if geometry is None:
            # `track_generation_ids` legitimately includes a generation with
            # only bounded tracker-support (no fresh detector confirmation)
            # on this exact frame, per RetainedFrameRecord's own contract --
            # but a geometry-less opportunity can never be matched against a
            # recurrence group, silently bypassing suppression entirely. Skip
            # it rather than reconstruct an opportunity this evaluator cannot
            # honestly evaluate for recurrence.
            continue

        session_offset = frame.get("session_offset_ms")
        session_offset_ms = int(session_offset) if isinstance(session_offset, (int, float)) else None
        source_offset = frame.get("source_offset_ms")
        source_offset_ms = int(source_offset) if isinstance(source_offset, (int, float)) else 0
        session_sequence = frame.get("session_sequence")
        session_sequence_value = int(session_sequence) if isinstance(session_sequence, (int, float)) else None
        provider_generation = frame.get("provider_generation")
        connection_segment_id = frame.get("connection_segment_id")
        marker_ids = frame.get("operator_marker_ids") or ()
        trigger_reason = TRIGGER_HIGH_RESOLUTION_BURST if TRIGGER_HIGH_RESOLUTION_BURST in triggers else TRIGGER_SHADOW_TRACK_EVENT
        motion_change_score = 1.0 if TRIGGER_MOTION_PROPOSAL_GENERATED in triggers else None

        representative_generation = min(str(item) for item in generations)
        opportunities.append(BurstOpportunity(
            opportunity_id=f"replay-opportunity:{frame_id}",
            stream_id=stream_id,
            session_id=session_id,
            track_generation_id=representative_generation,
            trigger_frame_id=frame_id,
            source_offset_ms=max(0, source_offset_ms),
            broad_class="animal",
            node_session_id=str(connection_segment_id) if connection_segment_id else None,
            provider_generation=str(provider_generation) if provider_generation else None,
            connection_segment_id=str(connection_segment_id) if connection_segment_id else None,
            session_sequence=session_sequence_value,
            session_offset_ms=session_offset_ms,
            subject_geometry=geometry,
            detector_score=score,
            # Fixed, neutral constants -- not reconstructed from a per-frame
            # box/generation count. The manifest's `animal_detection_count`
            # and active-generation count both reflect frame *busy-ness*
            # (how many things were on screen), not this one representative
            # generation's own real confirmation/support depth; using them
            # directly made the stronger-temporal-support novelty signal
            # fire on scene clutter rather than genuine per-track evidence.
            # A constant support value conservatively disables that one
            # signal in replay rather than reconstructing a misleading one.
            detector_confirmation_count=1,
            tracker_support_count=0,
            motion_change_score=motion_change_score,
            operator_marker_present=bool(marker_ids),
            trigger_reason=trigger_reason,
            requested_evidence_profile="",
        ))
    return tuple(opportunities)


def _int_or(value: object, default: int) -> int:
    return int(value) if isinstance(value, (int, float)) else default


# --------------------------------------------------------------------------
# Replay report
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class BurstScheduleReplayReport:
    schema_version: int
    session_id: str
    capture_manifest_fingerprint: str | None
    session_timeline_classification: str | None
    current_retained_frames: int
    current_high_resolution_frames: int
    current_track_generations: int
    reconstructed_opportunity_count: int
    proposed_issued_count: int
    proposed_suppressed_count: int
    proposed_suppression_reason_distribution: tuple[tuple[str, int], ...]
    proposed_recurrence_group_count: int
    proposed_operator_overrides: int
    proposed_engineering_overrides: int
    proposed_session_budget_used: int
    proposed_session_budget_configured: int
    high_resolution_frames_reduction: int
    high_resolution_frames_reduction_ratio: float | None
    static_recurrence_suppressions: int
    estimated_bytes_avoided: int
    genuine_appearance_reviewed: int | None
    genuine_appearance_retained: int | None
    genuine_appearance_lost: tuple[str, ...]
    operator_marked_appearance_reviewed: int | None
    operator_marked_appearance_retained: int | None
    operator_marked_appearance_lost: tuple[str, ...]
    # Finer-grained, more conservative diagnostic: every individual reviewed
    # whole_frame_truth="yes" frame (not just each appearance's span). A
    # confirmed visit often reviews several consecutive frames "yes" even
    # though only its genuinely novel moments should each receive their own
    # burst -- so this is expected to be a stricter, lower number than
    # genuine_appearance_retained/reviewed, not a discrepancy to resolve.
    reviewed_positive_frame_total: int | None
    reviewed_positive_frame_retained: int | None
    missed_useful_burst_risk: tuple[str, ...]
    limitations: tuple[str, ...]

    def to_semantic_dict(self) -> dict[str, object]:
        from dataclasses import asdict
        semantic = asdict(self)
        semantic["schema_version"] = REPORT_SCHEMA_VERSION
        semantic["replay_version"] = REPLAY_VERSION
        semantic["creates_truth"] = False
        semantic["shadow_only"] = True
        return semantic

    @property
    def fingerprint(self) -> str:
        return _fingerprint(self.to_semantic_dict())


_DEFAULT_LIMITATIONS: tuple[str, ...] = (
    "reconstruction treats every track-event-triggered retained frame as an opportunity, which "
    "is a broader (more inclusive) population than the live path's own strong-confidence-or-"
    "confirmed 'meaningful' gate; this may create replay opportunities the live path itself "
    "would never have raised, a conservative choice that never under-counts genuine-appearance "
    "retention",
    "one opportunity is reconstructed per retained triggering frame (not per generation active "
    "on that frame): the manifest does not record which detection box belongs to which "
    "generation, so this uses the frame's single highest-scoring box and one representative "
    "generation id (the lexicographically first active on that frame) rather than fabricating "
    "several near-identical opportunities that would inflate volume past what the live "
    "per-generation TrackUpdate path would ever raise",
    "broad_class is reconstructed as 'animal' for every opportunity; the manifest does not "
    "persist a per-detection class label",
    "motion_change_score is reconstructed as a binary 1.0/None from whether a motion proposal "
    "fired on the frame, not the underlying continuous pixel-difference magnitude",
    "detector_confirmation_count and tracker_support_count are fixed neutral constants (1 and 0) "
    "for every reconstructed opportunity, not derived from the manifest's per-frame detection/"
    "generation counts -- those reflect scene busy-ness (how many things were on screen), not "
    "this one representative generation's own confirmation depth, and using them directly made "
    "the stronger-temporal-support novelty signal fire on clutter; this conservatively disables "
    "that one novelty signal in replay rather than reconstructing a misleading version of it",
    "current_requests is not independently recorded by the capture manifest; only successful "
    "high-resolution captures are, so current behavior is reported as retained frames/track "
    "generations rather than a separate distinguishable request count",
    "replay assumes every scheduler-issued decision would have succeeded; it cannot replay real "
    "Camera Node capture success/failure, which is a live-only fact",
    "only frames the original bounded capture actually retained are visible to this "
    "reconstruction; a track update on a frame the capture loop did not retain for any reason "
    "is invisible here",
    "proposed_recurrence_group_count reflects state at the end of replay only: once the session "
    "budget is exhausted, later opportunities never reach group bookkeeping, so already-tracked "
    "groups are only purged (via ordinary expiry) and never refreshed for the remainder of the "
    "session -- a low or zero end-of-session count does not mean recurrence grouping was inactive "
    "earlier in a long, budget-constrained session",
    "genuine-appearance retention requires a supplied human-reviewed annotation set; without one "
    "those fields report None (not evaluated) rather than a false zero",
)


def replay_burst_schedule(
    manifest: dict[str, object],
    *,
    session_id: str,
    config: BurstSchedulerConfig | None = None,
    annotation: dict[str, object] | None = None,
) -> BurstScheduleReplayReport:
    """Replay every reconstructed opportunity through a fresh `BurstScheduler`
    in session-timeline order and compare against the manifest's own
    already-recorded current-behavior facts. Never rewrites `manifest` or
    `annotation`; both are read only."""

    opportunities = reconstruct_opportunities(manifest, session_id=session_id)
    upgraded = upgrade_capture_manifest_timeline(dict(manifest))
    raw_frames = [item for item in (upgraded.get("frames") or []) if isinstance(item, dict)]

    current_high_resolution = sum(1 for item in raw_frames if item.get("high_resolution"))
    generations: set[str] = set()
    for item in raw_frames:
        for generation_id in item.get("track_generation_ids") or ():
            generations.add(str(generation_id))

    scheduler = BurstScheduler(session_id=session_id, config=config or BurstSchedulerConfig())
    decisions: list[BurstDecision] = []
    for opportunity in opportunities:
        decision = scheduler.decide(opportunity)
        if decision.should_issue:
            # Replay cannot know whether a real Camera Node capture would
            # have succeeded; every issued decision is optimistically
            # resolved as captured so scheduler bookkeeping (concurrency,
            # byte-size sampling) stays internally consistent. See
            # `_DEFAULT_LIMITATIONS`.
            scheduler.record_result(decision.request_id, status="captured", byte_size=1_000_000, latency_ms=50)
        decisions.append(decision)

    diagnostics = scheduler.diagnostics()
    static_recurrence_suppressions = dict(diagnostics.suppression_reason_distribution).get(
        "suppressed_recurring_geometry", 0
    )
    reduction = current_high_resolution - diagnostics.issued_count
    reduction_ratio = (reduction / current_high_resolution) if current_high_resolution else None

    outcomes_by_frame: dict[str, list[str]] = {}
    for opportunity, decision in zip(opportunities, decisions):
        outcomes_by_frame.setdefault(opportunity.trigger_frame_id, []).append(decision.outcome)
    ordered_frame_ids = [str(item.get("frame_id")) for item in raw_frames]

    genuine_reviewed = genuine_retained = None
    genuine_lost: tuple[str, ...] = ()
    marked_reviewed = marked_retained = None
    marked_lost: tuple[str, ...] = ()
    positive_frame_total = positive_frame_retained = None
    missed_risk: tuple[str, ...] = ()
    if annotation is not None:
        (
            genuine_reviewed, genuine_retained, genuine_lost,
            marked_reviewed, marked_retained, marked_lost,
            positive_frame_total, positive_frame_retained,
            missed_risk,
        ) = _score_annotation(annotation, outcomes_by_frame, raw_frames, ordered_frame_ids)

    return BurstScheduleReplayReport(
        schema_version=REPORT_SCHEMA_VERSION,
        session_id=session_id,
        capture_manifest_fingerprint=upgraded.get("semantic_fingerprint") if isinstance(upgraded.get("semantic_fingerprint"), str) else None,
        session_timeline_classification=upgraded.get("session_timeline_classification") if isinstance(upgraded.get("session_timeline_classification"), str) else None,
        current_retained_frames=len(raw_frames),
        current_high_resolution_frames=current_high_resolution,
        current_track_generations=len(generations),
        reconstructed_opportunity_count=len(opportunities),
        proposed_issued_count=diagnostics.issued_count,
        proposed_suppressed_count=diagnostics.suppressed_count,
        proposed_suppression_reason_distribution=diagnostics.suppression_reason_distribution,
        proposed_recurrence_group_count=diagnostics.recurrence_group_count,
        proposed_operator_overrides=diagnostics.operator_overrides,
        proposed_engineering_overrides=diagnostics.engineering_overrides,
        proposed_session_budget_used=diagnostics.issued_count,
        proposed_session_budget_configured=scheduler.config.max_bursts_per_session,
        high_resolution_frames_reduction=reduction,
        high_resolution_frames_reduction_ratio=round(reduction_ratio, 4) if reduction_ratio is not None else None,
        static_recurrence_suppressions=static_recurrence_suppressions,
        estimated_bytes_avoided=diagnostics.estimated_bytes_avoided,
        genuine_appearance_reviewed=genuine_reviewed,
        genuine_appearance_retained=genuine_retained,
        genuine_appearance_lost=genuine_lost,
        operator_marked_appearance_reviewed=marked_reviewed,
        operator_marked_appearance_retained=marked_retained,
        operator_marked_appearance_lost=marked_lost,
        reviewed_positive_frame_total=positive_frame_total,
        reviewed_positive_frame_retained=positive_frame_retained,
        missed_useful_burst_risk=missed_risk,
        limitations=_DEFAULT_LIMITATIONS,
    )


def _score_annotation(
    annotation: dict[str, object],
    outcomes_by_frame: dict[str, list[str]],
    raw_frames: list[dict[str, object]],
    ordered_frame_ids: list[str],
) -> tuple[int, int, tuple[str, ...], int, int, tuple[str, ...], int, int, tuple[str, ...]]:
    """Score retention primarily by reviewed *appearance* (an `AppearanceInterval`
    -shaped `start_frame_id`/`end_frame_id` span -- the unit a human reviewer
    actually judged a genuine subject over), not by every individual
    whole_frame_truth="yes" frame: a single confirmed visit legitimately spans
    several consecutive reviewed-positive frames, and this scheduler is
    specifically designed to burst once for a genuinely novel moment rather
    than once per frame of the same moment. An appearance retains eligibility
    when *any* frame in its span was issued a burst."""

    frames = annotation.get("frames")
    if not isinstance(frames, list) or len(frames) > MAX_ANNOTATION_FRAMES:
        raise BurstScheduleReplayError("invalid_annotation_frames")
    high_res_by_frame = {str(item.get("frame_id")): bool(item.get("high_resolution")) for item in raw_frames}
    frame_index = {frame_id: position for position, frame_id in enumerate(ordered_frame_ids)}
    annotation_by_frame = {
        str(item.get("frame_id")): item for item in frames if isinstance(item, dict) and item.get("frame_id")
    }

    def _retained(frame_id: str) -> bool:
        return any(outcome in _ISSUING_OUTCOMES for outcome in outcomes_by_frame.get(frame_id, ()))

    def _span(start_id: str, end_id: str) -> tuple[str, ...]:
        start = frame_index.get(start_id)
        end = frame_index.get(end_id)
        if start is None or end is None:
            # Bounded, defensive fallback: an appearance referencing a frame
            # id absent from this manifest (should not happen for a
            # validated annotation) is scored on whichever endpoint is
            # resolvable rather than crashing the whole replay.
            return tuple(fid for fid in (start_id, end_id) if fid in frame_index)
        lo, hi = (start, end) if start <= end else (end, start)
        return tuple(ordered_frame_ids[lo:hi + 1])

    genuine_reviewed = genuine_retained = 0
    genuine_lost: list[str] = []
    marked_reviewed = marked_retained = 0
    marked_lost: list[str] = []
    missed_risk: list[str] = []

    for appearance in annotation.get("appearances") or ():
        if not isinstance(appearance, dict):
            continue
        appearance_id = str(appearance.get("appearance_id") or "")
        start_id = str(appearance.get("start_frame_id") or "")
        end_id = str(appearance.get("end_frame_id") or "")
        if not appearance_id or not start_id or not end_id:
            continue
        span = _span(start_id, end_id)
        if not span:
            continue
        genuine_reviewed += 1
        retained = any(_retained(fid) for fid in span)
        if retained:
            genuine_retained += 1
        elif len(genuine_lost) < MAX_LOST_FRAME_IDS:
            genuine_lost.append(appearance_id)

        is_operator_marked = any(
            (annotation_by_frame.get(fid, {}).get("provenance") or {}).get("truth_source") == "operator_marker"
            for fid in span
        )
        if is_operator_marked:
            marked_reviewed += 1
            if retained:
                marked_retained += 1
            elif len(marked_lost) < MAX_LOST_FRAME_IDS:
                marked_lost.append(appearance_id)

        if not retained and any(high_res_by_frame.get(fid) for fid in span) and len(missed_risk) < MAX_LOST_FRAME_IDS:
            missed_risk.append(appearance_id)

    positive_total = positive_retained = 0
    for entry in frames:
        if not isinstance(entry, dict) or entry.get("whole_frame_truth") != "yes":
            continue
        frame_id = str(entry.get("frame_id") or "")
        if not frame_id:
            continue
        positive_total += 1
        if _retained(frame_id):
            positive_retained += 1

    return (
        genuine_reviewed, genuine_retained, tuple(genuine_lost),
        marked_reviewed, marked_retained, tuple(marked_lost),
        positive_total, positive_retained,
        tuple(missed_risk),
    )


# Stage 6.12: reuse the scheduler module's own ISSUING_DECISIONS rather than
# a second, hand-maintained copy -- the earlier hardcoded duplicate silently
# missed DECISION_NOVELTY_RESERVE_ISSUED and under-reported genuine-
# appearance retention until this fix.
_ISSUING_OUTCOMES = ISSUING_DECISIONS


__all__ = [
    "MAX_ANNOTATION_FRAMES",
    "MAX_FRAMES",
    "MAX_GENERATIONS_PER_FRAME",
    "MAX_LOST_FRAME_IDS",
    "REPLAY_VERSION",
    "REPORT_SCHEMA_VERSION",
    "BurstScheduleReplayError",
    "BurstScheduleReplayReport",
    "reconstruct_opportunities",
    "replay_burst_schedule",
]
