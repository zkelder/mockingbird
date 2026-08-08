"""Deterministic, shadow-only ordered-frame Observation Engine replay."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from hashlib import sha256
import json
from typing import Protocol

from mockingbird.observation.contracts import (
    DetectionObservation, EvidenceCandidate, FramePacket, ObservationResult, TrackUpdate, VisitProposal,
)
from mockingbird.observation.evidence_scoring import EvidenceSelection, score_proposal_evidence

MANIFEST_VERSION = 1
FRAME_IDENTITY_VERSION = "ordered-frame-v1"
MATCHER_VERSION = "temporal-zone-v1"
REPORT_SCHEMA_VERSION = 3
PROVIDER_ERROR_LIMIT = 25
MAX_FRAMES = 10_000
MAX_APPEARANCES = 1_000
MAX_VISITS = 1_000
MAX_PROPOSALS = 2_000


class ReplayValidationError(ValueError):
    """A bounded replay validation or execution failure code."""


def semantic_fingerprint(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    return sha256(encoded).hexdigest()


def _replay_frame_timeline_facts(frame: "ReplayFrame") -> dict[str, object]:
    """The Stage 6.8 reconnect-safe provenance fields present on one
    `ReplayFrame`, keyed only when actually set. Shared by `ReplayInput.
    fingerprint` (so the semantic fingerprint includes deterministic
    timeline/discontinuity facts once they exist, per the session-timeline
    contract) and kept in lockstep with `packets()`'s own reading of the
    same fields."""

    facts: dict[str, object] = {}
    if frame.captured_at_iso is not None:
        facts["captured_at_iso"] = frame.captured_at_iso
    if frame.source_sequence is not None:
        facts["source_sequence"] = frame.source_sequence
    if frame.original_source_offset_ms is not None:
        facts["original_source_offset_ms"] = frame.original_source_offset_ms
    if frame.connection_segment_id is not None:
        facts["connection_segment_id"] = frame.connection_segment_id
    if frame.connection_segment_ordinal is not None:
        facts["connection_segment_ordinal"] = frame.connection_segment_ordinal
    if frame.provider_generation is not None:
        facts["provider_generation"] = frame.provider_generation
    if frame.temporal_discontinuity:
        facts["temporal_discontinuity"] = True
    if frame.temporal_uncertainty_ms is not None:
        facts["temporal_uncertainty_ms"] = frame.temporal_uncertainty_ms
    return facts


def _replay_frame_source_lineage_facts(frame: "ReplayFrame") -> dict[str, object]:
    """The Stage 6.14 reviewed-source-lineage fields present on one
    `ReplayFrame`, keyed only when actually set -- see
    docs/reviewed-replay-lineage-contract.md. Source lineage is semantic (it
    identifies *what was replayed*, not merely how), so it is included in
    `ReplayInput.fingerprint` exactly like Stage 6.8's timeline facts above;
    a pre-Stage-6.14 input never sets these, which keeps its fingerprint
    byte-identical to before. `session_offset_ms` is deliberately not
    duplicated here: a reconnect-safe temporal-review export already feeds
    the session-relative offset into this frame's own required
    `source_offset_ms` (see `temporal_annotation.build_replay_export`), and
    `content_hash` is already a required top-level fingerprint input for
    every `ReplayFrame`, lineage or not."""

    facts: dict[str, object] = {}
    if frame.source_capture_frame_id is not None:
        facts["source_capture_frame_id"] = frame.source_capture_frame_id
    if frame.source_capture_session_id is not None:
        facts["source_capture_session_id"] = frame.source_capture_session_id
    if frame.session_sequence is not None:
        facts["session_sequence"] = frame.session_sequence
    return facts


@dataclass(frozen=True)
class ReplayFrame:
    index: int
    source_offset_ms: int
    content_hash: str
    source_path: str | None = None
    analysis_excluded_regions: tuple[tuple[float, float, float, float], ...] = ()
    # Stage 6.8 reconnect-safe provenance, all optional and additive: an
    # export built by the older Stage 6.6 pipeline (or any other caller that
    # predates this) never sets them, and `source_offset_ms` above keeps its
    # original meaning for that input. A reconnect-safe export instead feeds
    # `source_offset_ms` the *session-relative* offset (see
    # docs/session-timeline-contract.md) so the ordering/monotonicity check
    # below passes on ordinary reconnect resets, and preserves the true
    # original source-local facts here rather than discarding them.
    captured_at_iso: str | None = None
    source_sequence: int | None = None
    original_source_offset_ms: int | None = None
    connection_segment_id: str | None = None
    connection_segment_ordinal: int | None = None
    provider_generation: str | None = None
    temporal_discontinuity: bool = False
    temporal_uncertainty_ms: int | None = None
    # Stage 6.14 reviewed-source lineage: all optional and additive, exactly
    # like the Stage 6.8 fields above. Set only when this frame was replayed
    # from reviewed Stage 6.6/6.8 temporal-review capture data (see
    # `temporal_annotation.build_replay_export` and
    # docs/reviewed-replay-lineage-contract.md); `None` for a generic Stage 2
    # replay input, which never requires reviewed provenance to work.
    # `source_capture_frame_id` is the original retained Camera Node/review
    # frame's own stable identity -- what a human reviewer's annotation
    # actually refers to -- kept distinct from this dataclass's own `index`/
    # `source_offset_ms`/`content_hash` replay identity.
    source_capture_frame_id: str | None = None
    source_capture_session_id: str | None = None
    session_sequence: int | None = None


@dataclass(frozen=True)
class ReplayInput:
    input_id: str
    stream_id: str
    width: int
    height: int
    nominal_fps: float
    frames: tuple[ReplayFrame, ...]

    def __post_init__(self) -> None:
        if not self.frames or len(self.frames) > MAX_FRAMES:
            raise ReplayValidationError("frame_limit")
        if self.width < 1 or self.height < 1 or self.nominal_fps <= 0:
            raise ReplayValidationError("invalid_source_metadata")
        if any(frame.index != index for index, frame in enumerate(self.frames)):
            raise ReplayValidationError("frame_indices")
        if any(
            not frame.content_hash
            or frame.source_offset_ms < 0
            or any(not _valid_box(box) for box in frame.analysis_excluded_regions)
            for frame in self.frames
        ):
            raise ReplayValidationError("invalid_frame")
        if any(a.source_offset_ms >= b.source_offset_ms for a, b in zip(self.frames, self.frames[1:])):
            raise ReplayValidationError("ordered_timestamps")
        # Stage 6.14: within one replay input, one reviewed source frame may
        # be referenced at most once -- a duplicate almost always means a
        # corrupted or hand-edited export, and silently accepting it would
        # let two different replay frames both claim to *be* the one frame a
        # human reviewer annotated. See docs/reviewed-replay-lineage-contract.md.
        source_ids = [frame.source_capture_frame_id for frame in self.frames if frame.source_capture_frame_id]
        if len(source_ids) != len(set(source_ids)):
            raise ReplayValidationError("duplicate_source_capture_frame_id")

    @property
    def fingerprint(self) -> str:
        frames = []
        for item in self.frames:
            frame = {
                "index": item.index,
                "source_offset_ms": item.source_offset_ms,
                "content_hash": item.content_hash,
            }
            if item.analysis_excluded_regions:
                frame["analysis_excluded_regions"] = [list(box) for box in item.analysis_excluded_regions]
            # Only present (and only affects the fingerprint) when a
            # reconnect-safe export actually populated it, so an input
            # built by any pre-Stage-6.8 caller keeps an identical
            # fingerprint to before -- the deterministic timeline and
            # discontinuity facts genuinely become part of the semantic
            # fingerprint only once they exist at all.
            timeline_facts = _replay_frame_timeline_facts(item)
            if timeline_facts:
                frame["timeline"] = timeline_facts
            source_lineage_facts = _replay_frame_source_lineage_facts(item)
            if source_lineage_facts:
                frame["source_lineage"] = source_lineage_facts
            frames.append(frame)
        return semantic_fingerprint({"version": MANIFEST_VERSION, "input_id": self.input_id,
            "stream_id": self.stream_id, "width": self.width, "height": self.height,
            "nominal_fps": self.nominal_fps,
            "frames": frames})

    def packets(self) -> tuple[FramePacket, ...]:
        root = self.fingerprint
        packets = []
        for frame in self.frames:
            timing_facts: list[tuple[str, str | int | float | bool | None]] = []
            if frame.original_source_offset_ms is not None:
                timing_facts.append(("original_source_offset_ms", frame.original_source_offset_ms))
            if frame.connection_segment_id is not None:
                timing_facts.append(("connection_segment_id", frame.connection_segment_id))
            if frame.connection_segment_ordinal is not None:
                timing_facts.append(("connection_segment_ordinal", frame.connection_segment_ordinal))
            if frame.temporal_discontinuity:
                timing_facts.append(("temporal_discontinuity", True))
            if frame.temporal_uncertainty_ms is not None:
                timing_facts.append(("temporal_uncertainty_ms", frame.temporal_uncertainty_ms))
            captured_at = None
            if frame.captured_at_iso is not None:
                try:
                    captured_at = datetime.fromisoformat(frame.captured_at_iso)
                except ValueError:
                    captured_at = None
            packets.append(FramePacket(
                stream_id=self.stream_id,
                media_asset_id=f"replay:{frame.index}",
                captured_at=captured_at,
                frame_id=semantic_fingerprint((FRAME_IDENTITY_VERSION, root, frame.index, frame.source_offset_ms, frame.content_hash)),
                source_offset_ms=frame.source_offset_ms,
                width=self.width,
                height=self.height,
                source_path=frame.source_path,
                analysis_excluded_regions=frame.analysis_excluded_regions,
                frame_sequence=frame.source_sequence,
                provider_generation=frame.provider_generation,
                timing_facts=tuple(timing_facts),
                # Stage 6.14: additive reviewed-source provenance, never a
                # replacement for the replay-local `frame_id` fingerprint
                # just above -- see docs/reviewed-replay-lineage-contract.md.
                source_capture_frame_id=frame.source_capture_frame_id,
                source_content_hash=frame.content_hash,
            ))
        return tuple(packets)


@dataclass(frozen=True)
class ExpectedAppearance:
    appearance_id: str
    start_offset_ms: int
    end_offset_ms: int
    outcome: str | None = None
    ambiguous: bool = False


@dataclass(frozen=True)
class ExpectedVisit:
    visit_id: str
    appearance_ids: tuple[str, ...]
    start_offset_ms: int
    end_offset_ms: int
    outcome: str | None = None
    zone_id: str | None = None
    ambiguous: bool = False
    # Stage 6.17: optional, additive reviewed-Visit-truth provenance that a
    # deterministic `AppearanceInterval` -> `ExpectedVisit` conversion
    # populates -- see docs/reviewed-visit-truth-contract.md. Absent/default
    # for any manifest that predates this stage or was built by a different
    # caller (for example the hand-authored manifests throughout this
    # module's own tests), which keeps every existing positional/keyword
    # construction, `BenchmarkManifest.fingerprint`, and matcher behavior
    # unaffected until a caller actually sets them.
    broad_class: str | None = None
    entry_uncertain: bool = False
    exit_uncertain: bool = False
    source_capture_frame_ids: tuple[str, ...] = ()
    reviewer: str | None = None


@dataclass(frozen=True)
class ExpectedDetection:
    annotation_id: str
    frame_index: int
    broad_class: str
    bounding_box: tuple[float, float, float, float]


@dataclass(frozen=True)
class ExpectedEvidence:
    candidate_id: str
    subject_visible: bool | None = None
    subject_geometry: tuple[float, float, float, float] | None = None
    useful_animal_confirmation: bool | None = None
    useful_identification: bool | None = None
    useful_context: bool | None = None
    preferred_context: bool | None = None
    ambiguous: bool = False
    obstruction: bool | None = None
    motion_blur: bool | None = None
    clipping: bool | None = None
    subject_absent: bool | None = None


@dataclass(frozen=True)
class BenchmarkManifest:
    version: int
    benchmark_id: str
    input_fingerprint: str
    appearances: tuple[ExpectedAppearance, ...]
    visits: tuple[ExpectedVisit, ...]
    detections: tuple[ExpectedDetection, ...] = ()
    evidence: tuple[ExpectedEvidence, ...] = ()

    def validate(self, replay: ReplayInput) -> None:
        if self.version != MANIFEST_VERSION:
            raise ReplayValidationError("unsupported_manifest_version")
        if self.input_fingerprint != replay.fingerprint:
            raise ReplayValidationError("input_fingerprint_mismatch")
        if len(self.appearances) > MAX_APPEARANCES or len(self.visits) > MAX_VISITS:
            raise ReplayValidationError("manifest_limit")
        duration = replay.frames[-1].source_offset_ms
        appearance_ids = [item.appearance_id for item in self.appearances]
        if len(appearance_ids) != len(set(appearance_ids)):
            raise ReplayValidationError("duplicate_appearance_id")
        for item in self.appearances:
            if item.start_offset_ms > item.end_offset_ms:
                raise ReplayValidationError("appearance_time_order")
            if item.start_offset_ms < 0 or item.end_offset_ms > duration:
                raise ReplayValidationError("appearance_outside_duration")
        available = set(appearance_ids)
        visit_ids = [item.visit_id for item in self.visits]
        if len(visit_ids) != len(set(visit_ids)):
            raise ReplayValidationError("duplicate_visit_id")
        for item in self.visits:
            if not item.appearance_ids or not set(item.appearance_ids) <= available:
                raise ReplayValidationError("invalid_visit_membership")
            if item.start_offset_ms > item.end_offset_ms or item.start_offset_ms < 0 or item.end_offset_ms > duration:
                raise ReplayValidationError("visit_time_order")
        annotation_ids = [item.annotation_id for item in self.detections]
        if len(annotation_ids) != len(set(annotation_ids)):
            raise ReplayValidationError("duplicate_detection_annotation_id")
        for item in self.detections:
            if item.frame_index < 0 or item.frame_index >= len(replay.frames) or not item.broad_class:
                raise ReplayValidationError("invalid_detection_annotation")
            if not _valid_box(item.bounding_box):
                raise ReplayValidationError("invalid_detection_annotation")
        evidence_ids = [item.candidate_id for item in self.evidence]
        if len(evidence_ids) != len(set(evidence_ids)):
            raise ReplayValidationError("duplicate_evidence_annotation_id")
        for item in self.evidence:
            if not item.candidate_id or (item.subject_geometry is not None and not _valid_box(item.subject_geometry)):
                raise ReplayValidationError("invalid_evidence_annotation")

    @property
    def fingerprint(self) -> str:
        return semantic_fingerprint(asdict(self))


class ReplayProvider(Protocol):
    provider_id: str
    async def describe(self, *, stream_id: str | None = None): ...
    async def replay_frames(self, frames: tuple[FramePacket, ...]) -> tuple[ObservationResult, ...]: ...


@dataclass(frozen=True)
class Match:
    expected_visit_id: str | None
    proposal_key: str | None
    status: str


@dataclass(frozen=True)
class ReplayReport:
    frames: tuple[FramePacket, ...]
    proposals: tuple[VisitProposal, ...]
    matches: tuple[Match, ...]
    metrics: dict[str, object]
    semantic_fingerprint: str
    threshold_results: tuple[dict[str, object], ...] = ()
    errors: tuple[str, ...] = ()
    detections: tuple[DetectionObservation, ...] = ()
    track_updates: tuple[TrackUpdate, ...] = ()
    evidence_candidates: tuple[EvidenceCandidate, ...] = ()
    pipeline_facts: dict[str, object] | None = None
    creates_truth: bool = False
    evidence_selections: tuple[EvidenceSelection, ...] = ()
    evidence_fingerprint: str | None = None


class ReplayRunner:
    def __init__(self, providers: dict[str, ReplayProvider]) -> None:
        self.providers = dict(sorted(providers.items()))

    async def run(self, replay: ReplayInput, manifest: BenchmarkManifest, *, provider_key: str,
                  thresholds: dict[str, float] | None = None) -> ReplayReport:
        manifest.validate(replay)
        provider = self.providers.get(provider_key)
        if provider is None:
            raise ReplayValidationError("unsupported_provider")
        frames = replay.packets()
        try:
            results = await provider.replay_frames(frames)
        except ReplayValidationError:
            raise
        except Exception as error:
            raise ReplayValidationError("provider_failure") from error
        detections = tuple(sorted(
            (item for result in results for item in result.detection_observations),
            key=lambda item: (
                item.frame_id or "", -(item.confidence or 0), item.label,
                item.bounding_box or (), item.observation_id or "",
            ),
        ))
        track_updates = tuple(sorted(
            (item for result in results for item in result.track_updates),
            key=lambda item: (
                item.source_offset_ms if item.source_offset_ms is not None else 2**63,
                item.generation_id, item.status, item.lifecycle_state, item.frame_id or "",
            ),
        ))
        evidence_candidates = tuple(sorted(
            (item for result in results for item in result.evidence_candidates),
            key=lambda item: (
                item.source_offset_ms if item.source_offset_ms is not None else 2**63,
                item.track_generation_id or "", item.role, item.frame_id or "",
            ),
        ))
        facts_reader = getattr(provider, "replay_semantic_facts", None)
        pipeline_facts = facts_reader() if callable(facts_reader) else {}
        if not isinstance(pipeline_facts, dict):
            raise ReplayValidationError("provider_failure")
        pipeline_facts = dict(sorted(pipeline_facts.items()))
        if any(result.creates_truth for result in results):
            raise ReplayValidationError("production_authority")
        proposals = tuple(sorted(
            (proposal for result in results for proposal in result.visit_proposals),
            key=lambda item: item.proposal_key,
        ))
        capabilities = getattr(provider, "capabilities", None)
        visit_supported = bool(capabilities and capabilities.emits_visit_proposals)
        detection_supported = bool(capabilities and capabilities.emits_detection_observations)
        track_supported = bool(capabilities and capabilities.emits_track_updates)
        if len(proposals) > MAX_PROPOSALS or any(not proposal.shadow_only for proposal in proposals):
            raise ReplayValidationError("production_authority")
        if not visit_supported and proposals:
            raise ReplayValidationError("production_authority")
        matches = _match(manifest.visits, proposals) if visit_supported else ()
        media = {
            frame.media_asset_id: source.source_path
            for frame, source in zip(frames, replay.frames)
            if source.source_path is not None
        }
        evidence_selections = tuple(
            score_proposal_evidence(proposal, evidence_candidates, media=media)
            for proposal in proposals
        )
        evidence_fingerprint = semantic_fingerprint([
            item.semantic_fingerprint for item in evidence_selections
        ])
        metrics = _metrics(
            manifest, proposals, matches, frames, results,
            visit_supported=visit_supported, detection_supported=detection_supported,
            track_supported=track_supported,
        )
        metrics.update(_pipeline_metrics(
            manifest, frames, proposals, track_updates, evidence_candidates,
            evidence_selections, pipeline_facts, matches,
            track_supported=track_supported, visit_supported=visit_supported,
        ))
        metrics = dict(sorted(metrics.items()))
        threshold_results = _threshold_results(metrics, thresholds or {})
        semantic = {
            "schema_version": REPORT_SCHEMA_VERSION,
            "input_fingerprint": replay.fingerprint,
            "manifest_fingerprint": manifest.fingerprint,
            "detections": [asdict(item) for item in detections],
            "track_updates": [asdict(item) for item in track_updates],
            "evidence_candidates": [asdict(item) for item in evidence_candidates],
            "evidence_selections": [asdict(item) for item in evidence_selections],
            "evidence_fingerprint": evidence_fingerprint,
            "pipeline_facts": pipeline_facts,
            "provider_key": provider_key,
            "frame_ids": [frame.frame_id for frame in frames],
            "proposals": [asdict(item) for item in proposals],
            "matches": [asdict(item) for item in matches],
            "metrics": metrics,
            "threshold_results": threshold_results,
        }
        return ReplayReport(
            frames=frames,
            proposals=proposals,
            matches=matches,
            metrics=metrics,
            semantic_fingerprint=semantic_fingerprint(semantic),
            threshold_results=tuple(threshold_results),
            detections=detections,
            track_updates=track_updates,
            evidence_candidates=evidence_candidates,
            pipeline_facts=pipeline_facts,
            evidence_selections=evidence_selections,
            evidence_fingerprint=evidence_fingerprint,
        )


def _pipeline_metrics(
    manifest: BenchmarkManifest,
    frames: tuple[FramePacket, ...],
    proposals: tuple[VisitProposal, ...],
    track_updates: tuple[TrackUpdate, ...],
    evidence: tuple[EvidenceCandidate, ...],
    evidence_selections: tuple[EvidenceSelection, ...],
    facts: dict[str, object],
    matches: tuple[Match, ...],
    *,
    track_supported: bool,
    visit_supported: bool,
) -> dict[str, object]:
    if not track_supported:
        unavailable = {
            name: _metric(None, "not_evaluated")
            for name in (
                "frames_inferred", "detector_inference_cadence", "tracks_started",
                "tracks_confirmed", "tracks_lost_or_rejected",
                "average_tracker_support_frames", "average_detector_confirmations_per_track",
                "ambiguous_association_count",
            )
        }
    else:
        terminal = [item for item in track_updates if item.status == "ended"]
        confirmed_generations = {
            item.generation_id for item in track_updates if item.lifecycle_state == "confirmed"
        }
        inferred = facts.get("frames_inferred")
        inferred_value = inferred if isinstance(inferred, int) and not isinstance(inferred, bool) else None
        unavailable = {
            "frames_inferred": _metric(inferred_value, "evaluated" if inferred_value is not None else "not_evaluated"),
            "detector_inference_cadence": _metric(
                inferred_value / len(frames) if inferred_value is not None and frames else None,
                "evaluated" if inferred_value is not None and frames else "not_evaluated",
            ),
            "tracks_started": _metric(sum(item.status == "started" for item in track_updates), "evaluated"),
            "tracks_confirmed": _metric(len(confirmed_generations), "evaluated"),
            "tracks_lost_or_rejected": _metric(
                sum(item.lifecycle_state == "rejected" or item.terminal_reason == "tracker_lost" for item in terminal),
                "evaluated",
            ),
            "average_tracker_support_frames": _metric(
                sum(item.tracker_support_count for item in terminal) / len(terminal) if terminal else None,
                "evaluated" if terminal else "not_evaluated",
            ),
            "average_detector_confirmations_per_track": _metric(
                sum(item.detector_confirmation_count for item in terminal) / len(terminal) if terminal else None,
                "evaluated" if terminal else "not_evaluated",
            ),
            "ambiguous_association_count": _metric(facts.get("ambiguous_associations", 0), "evaluated"),
        }
    proposal_generations = {item.track_generation_id for item in proposals if item.track_generation_id}
    evidence_generations = {item.track_generation_id for item in evidence if item.track_generation_id}
    evidence_state = "evaluated" if visit_supported else "not_evaluated"
    evidence_metrics = _evidence_metrics(manifest, evidence, evidence_selections, visit_supported=visit_supported)
    boundary_metrics = _boundary_metrics(track_updates, facts, track_supported=track_supported)
    reconnect_metrics = _reconnect_metrics(
        frames, track_updates, proposals, matches, facts,
        track_supported=track_supported, visit_supported=visit_supported,
    )
    support_metrics = _support_metrics(track_updates, facts, track_supported=track_supported)
    return unavailable | evidence_metrics | boundary_metrics | reconnect_metrics | support_metrics | {
        "evidence_candidate_count": _metric(len(evidence) if visit_supported else None, evidence_state),
        "proposals_with_evidence": _metric(
            len(proposal_generations & evidence_generations) if visit_supported else None, evidence_state,
        ),
        "track_duration_error_ms": _metric(None, "insufficient_truth" if track_supported else "not_evaluated"),
    }


_CONFIDENT_EPISODE_SPLIT_REASONS = {"maximum_unsupported_duration", "negative_interval_reentry"}
_BOUNDARY_METRICS = (
    "episode_temporary_loss_count", "episode_rejected_count", "episode_confirmed_split_count",
    "episode_ambiguous_reentry_count", "boundary_reason_distribution",
)


def _boundary_metrics(
    track_updates: tuple[TrackUpdate, ...],
    facts: dict[str, object],
    *,
    track_supported: bool,
) -> dict[str, object]:
    """Deterministic episode-boundary counts derived only from already-emitted
    ``TrackUpdate`` facts; no new provider contract fields are required."""
    if not track_supported:
        return {name: _metric(None, "not_evaluated") for name in _BOUNDARY_METRICS}
    terminal = [item for item in track_updates if item.status == "ended"]
    reasons: dict[str, int] = {}
    for item in terminal:
        reason = item.terminal_reason or "unknown"
        reasons[reason] = reasons.get(reason, 0) + 1
    confident_splits = sum(reasons.get(reason, 0) for reason in _CONFIDENT_EPISODE_SPLIT_REASONS)
    rejected = sum(item.lifecycle_state == "rejected" for item in terminal)
    return {
        "episode_temporary_loss_count": _metric(
            sum(item.lifecycle_state == "temporarily_lost" for item in track_updates), "evaluated",
        ),
        "episode_rejected_count": _metric(rejected, "evaluated"),
        "episode_confirmed_split_count": _metric(confident_splits, "evaluated"),
        "episode_ambiguous_reentry_count": _metric(facts.get("ambiguous_reentries", 0), "evaluated"),
        "boundary_reason_distribution": _metric(dict(sorted(reasons.items())), "evaluated"),
    }


_RECONNECT_METRICS = (
    "reconnect_boundary_count", "reconnect_bridges_attempted", "reconnect_bridges_continued",
    "reconnect_bridges_expired", "reconnect_resets_true_source_change",
    "reconnect_resets_insufficient_provenance", "reconnect_ambiguous_association_count",
    "tracks_spanning_multiple_connection_segments", "proposals_spanning_multiple_connection_segments",
    "reconnect_fragmentation_avoided", "reconnect_related_incorrect_merge_count",
)


def _reconnect_metrics(
    frames: tuple[FramePacket, ...],
    track_updates: tuple[TrackUpdate, ...],
    proposals: tuple[VisitProposal, ...],
    matches: tuple[Match, ...],
    facts: dict[str, object],
    *,
    track_supported: bool,
    visit_supported: bool,
) -> dict[str, object]:
    """Stage 6.11 reconnect-continuity counts, kept separate from ordinary
    detector-miss episode-boundary metrics above. The scalar counters
    (`reconnect_boundary_count` through `reconnect_ambiguous_association_
    count`) are read directly from already-emitted `FrameDrivenObservation
    Provider` semantic facts (see `frame_driven_provider._reset_facts`);
    the segment-membership and merge metrics below are derived only from
    already-emitted `TrackUpdate.supporting_frame_ids`/`VisitProposal.
    track_generation_id` plus each frame's own additive `timing_facts`
    `connection_segment_id` -- no new provider contract field is required.
    """
    if not track_supported:
        return {name: _metric(None, "not_evaluated") for name in _RECONNECT_METRICS}
    segment_by_frame: dict[str | None, str] = {}
    for frame in frames:
        segment = dict(frame.timing_facts).get("connection_segment_id")
        if isinstance(segment, str) and segment and frame.frame_id is not None:
            segment_by_frame[frame.frame_id] = segment
    segments_by_generation: dict[str, set[str]] = {}
    for update in track_updates:
        segments = segments_by_generation.setdefault(update.generation_id, set())
        for frame_id in update.supporting_frame_ids:
            segment = segment_by_frame.get(frame_id)
            if segment is not None:
                segments.add(segment)
    multi_segment_generations = {
        generation for generation, segments in segments_by_generation.items() if len(segments) > 1
    }
    evaluated = "evaluated" if visit_supported else "not_evaluated"
    proposals_multi_segment = sum(
        1 for proposal in proposals if proposal.track_generation_id in multi_segment_generations
    )
    incorrectly_merged_keys = {item.proposal_key for item in matches if item.status == "incorrectly_merged"}
    reconnect_merge_errors = sum(
        1
        for proposal in proposals
        if proposal.proposal_key in incorrectly_merged_keys
        and proposal.track_generation_id in multi_segment_generations
    )
    return {
        "reconnect_boundary_count": _metric(facts.get("reconnect_boundaries", 0), "evaluated"),
        "reconnect_bridges_attempted": _metric(facts.get("reconnect_bridges_attempted", 0), "evaluated"),
        "reconnect_bridges_continued": _metric(facts.get("reconnect_bridges_continued", 0), "evaluated"),
        "reconnect_bridges_expired": _metric(facts.get("reconnect_bridges_expired", 0), "evaluated"),
        "reconnect_resets_true_source_change": _metric(facts.get("resets_true_source_change", 0), "evaluated"),
        "reconnect_resets_insufficient_provenance": _metric(
            facts.get("resets_insufficient_provenance", 0), "evaluated",
        ),
        "reconnect_ambiguous_association_count": _metric(
            facts.get("reconnect_ambiguous_associations", 0), "evaluated",
        ),
        "tracks_spanning_multiple_connection_segments": _metric(len(multi_segment_generations), evaluated),
        "proposals_spanning_multiple_connection_segments": _metric(proposals_multi_segment, evaluated),
        # Every bridge that ended in reacquisition is one episode that a
        # pre-Stage-6.11 tracker would have fragmented at that same
        # boundary -- a direct, non-speculative count, not an estimate.
        "reconnect_fragmentation_avoided": _metric(facts.get("reconnect_bridges_continued", 0), "evaluated"),
        "reconnect_related_incorrect_merge_count": _metric(reconnect_merge_errors, evaluated),
    }


_SUPPORT_METRICS = (
    "strong_detector_support_frame_count", "weak_detector_support_frame_count",
    "tracker_only_support_frame_count", "confidence_dip_bridge_count",
    "terminations_after_weak_support_count", "maximum_weak_support_span_ms",
    "maximum_tracker_only_support_span_ms",
)


def _support_metrics(
    track_updates: tuple[TrackUpdate, ...],
    facts: dict[str, object],
    *,
    track_supported: bool,
) -> dict[str, object]:
    """Stage 6.16 bounded evidence-hierarchy counts (see
    docs/sustained-visit-continuity-contract.md). The five scalar counters
    are read directly from already-emitted `FrameDrivenObservationProvider`
    semantic facts, exactly like `_reconnect_metrics` above; the two
    maximum-span facts are derived only from already-emitted `TrackUpdate.
    support_state`, grouped by generation in already-sorted replay order --
    no new provider contract field is required."""
    if not track_supported:
        return {name: _metric(None, "not_evaluated") for name in _SUPPORT_METRICS}
    by_generation: dict[str, list[TrackUpdate]] = {}
    for update in track_updates:
        by_generation.setdefault(update.generation_id, []).append(update)
    max_weak_span = 0
    max_tracker_span = 0
    for updates in by_generation.values():
        max_weak_span = max(max_weak_span, _longest_support_span_ms(updates, "weak_detector_supported"))
        max_tracker_span = max(max_tracker_span, _longest_support_span_ms(updates, "tracker_supported"))
    return {
        "strong_detector_support_frame_count": _metric(facts.get("strong_detector_support_frames", 0), "evaluated"),
        "weak_detector_support_frame_count": _metric(facts.get("weak_detector_support_frames", 0), "evaluated"),
        "tracker_only_support_frame_count": _metric(facts.get("tracker_only_support_frames", 0), "evaluated"),
        "confidence_dip_bridge_count": _metric(facts.get("confidence_dip_bridges", 0), "evaluated"),
        "terminations_after_weak_support_count": _metric(
            facts.get("terminations_after_weak_support", 0), "evaluated",
        ),
        "maximum_weak_support_span_ms": _metric(max_weak_span, "evaluated"),
        "maximum_tracker_only_support_span_ms": _metric(max_tracker_span, "evaluated"),
    }


def _longest_support_span_ms(updates: list[TrackUpdate], support_state: str) -> int:
    """The longest contiguous run (by replay order, in ms from its first to
    its last update) of one generation's own updates carrying exactly the
    given `support_state`. A single matching update contributes a span of
    0ms (it has no duration by itself yet); this reports duration, not
    frame count, so it stays meaningful across an uneven real cadence."""
    longest = 0
    run_start: int | None = None
    run_end: int | None = None
    for update in updates:
        offset = update.source_offset_ms
        if update.support_state == support_state and offset is not None:
            if run_start is None:
                run_start = offset
            run_end = offset
        else:
            if run_start is not None and run_end is not None:
                longest = max(longest, run_end - run_start)
            run_start = None
            run_end = None
    if run_start is not None and run_end is not None:
        longest = max(longest, run_end - run_start)
    return longest


def _evidence_metrics(
    manifest: BenchmarkManifest,
    evidence: tuple[EvidenceCandidate, ...],
    selections: tuple[EvidenceSelection, ...],
    *,
    visit_supported: bool,
) -> dict[str, object]:
    if not visit_supported:
        return {name: _metric(None, "not_evaluated") for name in _EVIDENCE_METRICS}
    scores = [score for selection in selections for score in selection.candidate_scores]
    eligible = [score for score in scores if score.eligible]
    selected_identification = [selection.identification_candidate_id for selection in selections]
    selected_context = [selection.context_candidate_id for selection in selections]
    annotations = {item.candidate_id: item for item in manifest.evidence}
    if not annotations:
        truth_state = "not_evaluated"
    elif all(item.ambiguous for item in annotations.values()):
        truth_state = "insufficient_truth"
    else:
        truth_state = "evaluated"
    usable_truth = {key: item for key, item in annotations.items() if not item.ambiguous}
    identification_truth = [usable_truth[item] for item in selected_identification if item in usable_truth]
    context_truth = [usable_truth[item] for item in selected_context if item in usable_truth]
    aligned = [score for score in scores if score.temporal_status == "aligned"]
    clipped = [score for score in scores if score.edge_clipping_status == "edge_clipped"]
    high_resolution = [score for score in scores if score.role == "high_resolution_burst"]
    latencies = []
    for candidate in evidence:
        latency = dict(candidate.quality_facts).get("request_to_capture_ms")
        if isinstance(latency, (int, float)) and not isinstance(latency, bool):
            latencies.append(float(latency))
    roles: dict[str, int] = {}
    for selection in selections:
        if selection.identification_candidate_id is None:
            continue
        selected = next(score for score in selection.candidate_scores if score.candidate_id == selection.identification_candidate_id)
        roles[selected.role] = roles.get(selected.role, 0) + 1
    evaluated_count = len(identification_truth)
    useful_identification = sum(
        item.useful_identification is True or item.useful_animal_confirmation is True
        for item in identification_truth
    )
    useful_context = sum(item.useful_context is True or item.preferred_context is True for item in context_truth)
    return {
        "evidence_candidates_eligible": _metric(len(eligible), "evaluated"),
        "useful_identification_evidence": _metric(useful_identification if truth_state == "evaluated" else None, truth_state),
        "useful_context_evidence": _metric(useful_context if truth_state == "evaluated" else None, truth_state),
        "useful_primary_rate": _metric(useful_identification / evaluated_count if truth_state == "evaluated" and evaluated_count else None,
                                       truth_state if truth_state != "evaluated" or evaluated_count else "insufficient_truth"),
        "evidence_subject_containment": _metric(sum(score.containment_status == "contained" for score in scores) / len(scores) if scores else None,
                                                 "evaluated" if scores else "not_evaluated"),
        "evidence_clipping_rate": _metric(len(clipped) / len(scores) if scores else None, "evaluated" if scores else "not_evaluated"),
        "evidence_temporal_alignment_rate": _metric(len(aligned) / len(scores) if scores else None, "evaluated" if scores else "not_evaluated"),
        "evidence_latency_ms": _metric(sum(latencies) / len(latencies) if latencies else None, "evaluated" if latencies else "not_evaluated"),
        "high_resolution_availability": _metric(len(high_resolution) / len(selections) if selections else None,
                                                 "evaluated" if selections else "not_evaluated"),
        "selected_identification_role_distribution": _metric(dict(sorted(roles.items())), "evaluated" if selections else "not_evaluated"),
    }


_EVIDENCE_METRICS = (
    "evidence_candidates_eligible", "useful_identification_evidence", "useful_context_evidence",
    "useful_primary_rate", "evidence_subject_containment", "evidence_clipping_rate",
    "evidence_temporal_alignment_rate", "evidence_latency_ms", "high_resolution_availability",
    "selected_identification_role_distribution",
)


_COMPARISON_METRICS = (
    "expected_appearance_count", "captured_appearance_count", "missed_appearance_count",
    "appearance_recall", "proposed_visit_count", "matched_visit_count", "proposal_precision",
    "false_proposal_count", "duplicate_count", "duplicate_rate", "fragmentation_count",
    "fragmentation_rate", "incorrect_merge_count", "incorrect_merge_rate",
    "zone_attribution_accuracy", "proposals_with_evidence", "useful_identification_evidence",
    "useful_context_evidence", "useful_primary_rate", "evidence_subject_containment",
    "evidence_clipping_rate", "evidence_temporal_alignment_rate", "evidence_latency_ms",
    "high_resolution_availability", "evidence_candidate_count", "evidence_candidates_eligible",
    "selected_identification_role_distribution", "frames_supplied", "frames_processed",
    "frames_inferred", "track_update_count", "provider_error_count",
    "episode_temporary_loss_count", "episode_rejected_count", "episode_confirmed_split_count",
    "episode_ambiguous_reentry_count", "boundary_reason_distribution",
)


def compare_replay_reports(left: ReplayReport, right: ReplayReport) -> dict[str, object]:
    """Return a deterministic semantic comparison without inventing unavailable values."""

    comparisons: list[dict[str, object]] = []
    for name in _COMPARISON_METRICS:
        left_metric = left.metrics.get(name)
        right_metric = right.metrics.get(name)
        left_state = left_metric.get("state") if isinstance(left_metric, dict) else "not_evaluated"
        right_state = right_metric.get("state") if isinstance(right_metric, dict) else "not_evaluated"
        left_value = left_metric.get("value") if isinstance(left_metric, dict) else None
        right_value = right_metric.get("value") if isinstance(right_metric, dict) else None
        difference = (
            right_value - left_value
            if left_state == right_state == "evaluated"
            and isinstance(left_value, (int, float))
            and isinstance(right_value, (int, float))
            else None
        )
        if left_state == "insufficient_truth" or right_state == "insufficient_truth":
            classification = "insufficient truth"
        elif left_state != "evaluated" or right_state != "evaluated":
            classification = "unsupported for one provider"
        elif left_value == right_value:
            classification = "equivalent"
        elif isinstance(left_value, (int, float)) and isinstance(right_value, (int, float)):
            lower_is_better = name in {
                "fragmentation_rate", "duplicate_rate", "incorrect_merge_rate",
                "evidence_clipping_rate", "evidence_latency_ms", "frames_inferred",
            }
            right_better = right_value < left_value if lower_is_better else right_value > left_value
            classification = "frame-driven better" if right_better else "snapshot better"
        else:
            classification = "unsupported for one provider"
        comparisons.append({
            "metric": name,
            "left": {"state": left_state, "value": left_value},
            "right": {"state": right_state, "value": right_value},
            "difference": difference,
            "classification": classification,
        })
    semantic = {"comparison_version": "observation-provider-comparison-v2", "metrics": comparisons}
    return {**semantic, "semantic_fingerprint": semantic_fingerprint(semantic)}


def _overlap_ms(visit: ExpectedVisit, proposal: VisitProposal) -> int:
    if proposal.start_offset_ms is None or proposal.end_offset_ms is None:
        return 0
    return max(0, min(visit.end_offset_ms, proposal.end_offset_ms) - max(visit.start_offset_ms, proposal.start_offset_ms) + 1)


def _zone_score(visit: ExpectedVisit, proposal: VisitProposal) -> int:
    if visit.zone_id is None or proposal.zone_id is None:
        return 0
    return 1 if visit.zone_id == proposal.zone_id else -1


def _proposal_signature(proposal: VisitProposal) -> tuple[object, ...]:
    return (proposal.source_id, proposal.stream_id, proposal.evidence_media_asset_ids,
            proposal.start_offset_ms, proposal.end_offset_ms, proposal.zone_id, proposal.reason)


def _match(expected: tuple[ExpectedVisit, ...], proposals: tuple[VisitProposal, ...]) -> tuple[Match, ...]:
    remaining = set(range(len(proposals)))
    matches: list[Match] = []
    for visit in sorted(expected, key=lambda item: (item.start_offset_ms, item.visit_id)):
        if visit.ambiguous:
            matches.append(Match(visit.visit_id, None, "ambiguous"))
            continue
        candidates = [index for index in remaining if _overlap_ms(visit, proposals[index]) > 0 and _zone_score(visit, proposals[index]) >= 0]
        if not candidates:
            matches.append(Match(visit.visit_id, None, "missed"))
            continue
        candidates.sort(key=lambda index: (-_overlap_ms(visit, proposals[index]), -_zone_score(visit, proposals[index]), proposals[index].start_offset_ms if proposals[index].start_offset_ms is not None else 2**63, proposals[index].proposal_key))
        chosen = candidates[0]
        remaining.remove(chosen)
        matches.append(Match(visit.visit_id, proposals[chosen].proposal_key, "matched"))
        signature = _proposal_signature(proposals[chosen])
        for index in candidates[1:]:
            matches.append(Match(visit.visit_id, proposals[index].proposal_key,
                                 "duplicate" if _proposal_signature(proposals[index]) == signature else "fragmented"))
            remaining.remove(index)
    for index in sorted(remaining, key=lambda item: proposals[item].proposal_key):
        matches.append(Match(None, proposals[index].proposal_key, "false"))
    for proposal in proposals:
        supported = [visit for visit in expected if not visit.ambiguous and _overlap_ms(visit, proposal) > 0 and _zone_score(visit, proposal) >= 0]
        if len(supported) > 1:
            matches.append(Match(None, proposal.proposal_key, "incorrectly_merged"))
    return tuple(matches)


def _metric(value: object, state: str) -> dict[str, object]:
    return {"state": state, "value": value}


def _zone_attribution_metric(
    manifest: BenchmarkManifest, proposals: tuple[VisitProposal, ...], matches: tuple[Match, ...],
    *, visit_supported: bool,
) -> dict[str, object]:
    """Stage 6.17: honest Zone-attribution accuracy among matched Visits that
    actually carry reviewed Zone truth (`ExpectedVisit.zone_id`, populated
    only when a reviewer explicitly established it -- see
    docs/reviewed-visit-truth-contract.md). `insufficient_truth` -- exactly
    like every other truth-dependent metric in this module -- when no
    `ExpectedVisit` in the manifest carries a `zone_id` at all, or none of
    those matched a proposal that itself declared a `zone_id`. Reads only
    already-computed matches/proposals; the matcher itself is unchanged."""

    if not visit_supported:
        return {"zone_attribution_accuracy": _metric(None, "not_evaluated")}
    visits_with_zone_truth = {item.visit_id: item.zone_id for item in manifest.visits if item.zone_id is not None}
    if not visits_with_zone_truth:
        return {"zone_attribution_accuracy": _metric(None, "insufficient_truth")}
    proposals_by_key = {item.proposal_key: item for item in proposals}
    evaluated = correct = 0
    for match in matches:
        if match.status != "matched" or match.expected_visit_id not in visits_with_zone_truth:
            continue
        proposal = proposals_by_key.get(match.proposal_key) if match.proposal_key else None
        if proposal is None or proposal.zone_id is None:
            continue
        evaluated += 1
        correct += proposal.zone_id == visits_with_zone_truth[match.expected_visit_id]
    if not evaluated:
        return {"zone_attribution_accuracy": _metric(None, "insufficient_truth")}
    return {"zone_attribution_accuracy": _metric(correct / evaluated, "evaluated")}


def _metrics(
    manifest: BenchmarkManifest,
    proposals: tuple[VisitProposal, ...],
    matches: tuple[Match, ...],
    frames: tuple[FramePacket, ...],
    results: tuple[ObservationResult, ...],
    *,
    visit_supported: bool,
    detection_supported: bool,
    track_supported: bool,
) -> dict[str, object]:
    matched_ids = {item.expected_visit_id for item in matches if item.status == "matched"}
    captured = {
        appearance
        for visit in manifest.visits
        if visit.visit_id in matched_ids
        for appearance in visit.appearance_ids
    }
    counts = {
        status: sum(item.status == status for item in matches)
        for status in (
            "matched", "missed", "false", "duplicate", "fragmented",
            "incorrectly_merged", "ambiguous",
        )
    }
    expected_count = len(manifest.visits)
    proposal_count = len(proposals)
    if visit_supported:
        appearance_state = "evaluated" if manifest.appearances else "insufficient_truth"
        precision_state = "evaluated" if proposals else "not_evaluated"
        visit_count_state = "evaluated"
    else:
        appearance_state = precision_state = visit_count_state = "not_evaluated"
    metrics: dict[str, object] = {
        "expected_appearance_count": _metric(len(manifest.appearances), "evaluated"),
        "captured_appearance_count": _metric(len(captured) if visit_supported else None, appearance_state),
        "missed_appearance_count": _metric(
            len(manifest.appearances) - len(captured) if visit_supported else None, appearance_state,
        ),
        "appearance_recall": _metric(
            len(captured) / len(manifest.appearances)
            if visit_supported and manifest.appearances else None,
            appearance_state,
        ),
        "expected_visit_count": _metric(expected_count, "evaluated"),
        "proposed_visit_count": _metric(proposal_count if visit_supported else None, visit_count_state),
        "matched_visit_count": _metric(counts["matched"] if visit_supported else None, visit_count_state),
        "proposal_precision": _metric(
            counts["matched"] / proposal_count if visit_supported and proposal_count else None,
            precision_state,
        ),
        "false_proposal_count": _metric(counts["false"] if visit_supported else None, visit_count_state),
        "missed_visit_count": _metric(counts["missed"] if visit_supported else None, visit_count_state),
        "duplicate_count": _metric(counts["duplicate"] if visit_supported else None, visit_count_state),
        "duplicate_rate": _metric(
            counts["duplicate"] / proposal_count if visit_supported and proposal_count else None,
            precision_state,
        ),
        "fragmentation_count": _metric(counts["fragmented"] if visit_supported else None, visit_count_state),
        "fragmentation_rate": _metric(
            counts["fragmented"] / expected_count if visit_supported and expected_count else None,
            "evaluated" if visit_supported and expected_count else appearance_state,
        ),
        "incorrect_merge_count": _metric(counts["incorrectly_merged"] if visit_supported else None, visit_count_state),
        "incorrect_merge_rate": _metric(
            counts["incorrectly_merged"] / proposal_count if visit_supported and proposal_count else None,
            precision_state,
        ),
        **_zone_attribution_metric(manifest, proposals, matches, visit_supported=visit_supported),
        "evidence_candidate_coverage": _metric(
            sum(bool(item.evidence_media_asset_ids) for item in proposals) / proposal_count
            if visit_supported and proposal_count else None,
            precision_state,
        ),
        "useful_evidence_coverage": _metric(None, "insufficient_truth" if visit_supported else "not_evaluated"),
        "primary_evidence_usefulness": _metric(None, "insufficient_truth" if visit_supported else "not_evaluated"),
        "frames_supplied": _metric(len(frames), "evaluated"),
        "frames_processed": _metric(sum(len(result.frame_packets) for result in results), "evaluated"),
        "track_update_count": _metric(
            sum(len(result.track_updates) for result in results) if track_supported else None,
            "evaluated" if track_supported else "not_evaluated",
        ),
        "proposal_count": _metric(proposal_count if visit_supported else None, visit_count_state),
        "provider_error_count": _metric(0, "evaluated"),
    }
    metrics.update(_detection_metrics(manifest, frames, results, detection_supported=detection_supported))
    # Compatibility aliases remain additive during the Observation Engine strangler migration.
    metrics.update({
        "expected_appearances": len(manifest.appearances),
        "captured_appearances": len(captured) if visit_supported else None,
        "appearance_recall_state": appearance_state,
        "appearance_recall_value": metrics["appearance_recall"]["value"],
        "proposal_precision_state": precision_state,
        "proposal_precision_value": metrics["proposal_precision"]["value"],
    })
    return dict(sorted(metrics.items()))


DETECTION_IOU_THRESHOLD = 0.5


def _detection_metrics(
    manifest: BenchmarkManifest,
    frames: tuple[FramePacket, ...],
    results: tuple[ObservationResult, ...],
    *,
    detection_supported: bool,
) -> dict[str, object]:
    detections = tuple(item for result in results for item in result.detection_observations)
    animal_detections = tuple(item for item in detections if item.is_animal is True)
    if not detection_supported:
        return {
            name: _metric(None, "not_evaluated")
            for name in (
                "detector_observation_count", "animal_detector_observation_count",
                "detector_observations_per_frame",
                "annotated_animal_frame_count", "animal_positive_inference_frame_count",
                "frame_level_animal_recall", "false_animal_positive_frame_count",
                "matched_annotated_box_count", "missed_annotated_box_count",
                "box_precision", "box_recall", "broad_class_agreement",
            )
        } | {"detection_iou_threshold": _metric(DETECTION_IOU_THRESHOLD, "not_evaluated")}

    frame_index_by_id = {frame.frame_id: index for index, frame in enumerate(frames)}
    predicted_by_frame: dict[int, list[DetectionObservation]] = {}
    for detection in animal_detections:
        frame_index = frame_index_by_id.get(detection.frame_id)
        if frame_index is not None:
            predicted_by_frame.setdefault(frame_index, []).append(detection)
    positive_frames = set(predicted_by_frame)
    base = {
        "detector_observation_count": _metric(len(detections), "evaluated"),
        "animal_detector_observation_count": _metric(len(animal_detections), "evaluated"),
        "detector_observations_per_frame": _metric(len(detections) / len(frames) if frames else None, "evaluated"),
        "animal_positive_inference_frame_count": _metric(len(positive_frames), "evaluated"),
        "detection_iou_threshold": _metric(DETECTION_IOU_THRESHOLD, "evaluated"),
    }
    if not manifest.detections:
        return base | {
            name: _metric(None, "insufficient_truth")
            for name in (
                "annotated_animal_frame_count", "frame_level_animal_recall",
                "false_animal_positive_frame_count", "matched_annotated_box_count",
                "missed_annotated_box_count", "box_precision", "box_recall",
                "broad_class_agreement",
            )
        }

    truth_frames = {item.frame_index for item in manifest.detections}
    remaining_predictions = {
        frame_index: set(range(len(items))) for frame_index, items in predicted_by_frame.items()
    }
    matched = 0
    class_matches = 0
    for truth in sorted(manifest.detections, key=lambda item: (item.frame_index, item.annotation_id)):
        candidates = []
        for index in remaining_predictions.get(truth.frame_index, set()):
            prediction = predicted_by_frame[truth.frame_index][index]
            if prediction.bounding_box is None:
                continue
            overlap = _iou(truth.bounding_box, prediction.bounding_box)
            if overlap >= DETECTION_IOU_THRESHOLD:
                candidates.append((-overlap, prediction.label, prediction.observation_id or "", index))
        if not candidates:
            continue
        _, _, _, selected = min(candidates)
        remaining_predictions[truth.frame_index].remove(selected)
        matched += 1
        if predicted_by_frame[truth.frame_index][selected].label == truth.broad_class:
            class_matches += 1
    predicted_boxes = sum(item.bounding_box is not None for item in animal_detections)
    truth_count = len(manifest.detections)
    return base | {
        "annotated_animal_frame_count": _metric(len(truth_frames), "evaluated"),
        "frame_level_animal_recall": _metric(len(truth_frames & positive_frames) / len(truth_frames), "evaluated"),
        "false_animal_positive_frame_count": _metric(len(positive_frames - truth_frames), "evaluated"),
        "matched_annotated_box_count": _metric(matched, "evaluated"),
        "missed_annotated_box_count": _metric(truth_count - matched, "evaluated"),
        "box_precision": _metric(matched / predicted_boxes if predicted_boxes else None,
                                  "evaluated" if predicted_boxes else "not_evaluated"),
        "box_recall": _metric(matched / truth_count, "evaluated"),
        "broad_class_agreement": _metric(class_matches / matched if matched else None,
                                           "evaluated" if matched else "not_evaluated"),
    }


def _valid_box(box: tuple[float, float, float, float]) -> bool:
    return len(box) == 4 and all(0.0 <= value <= 1.0 for value in box) and box[0] < box[2] and box[1] < box[3]


def _iou(first: tuple[float, float, float, float], second: tuple[float, float, float, float]) -> float:
    left, top = max(first[0], second[0]), max(first[1], second[1])
    right, bottom = min(first[2], second[2]), min(first[3], second[3])
    intersection = max(0.0, right - left) * max(0.0, bottom - top)
    first_area = (first[2] - first[0]) * (first[3] - first[1])
    second_area = (second[2] - second[0]) * (second[3] - second[1])
    union = first_area + second_area - intersection
    return intersection / union if union > 0 else 0.0


_THRESHOLD_RULES = {
    "minimum_appearance_recall": ("appearance_recall", "minimum"),
    "minimum_proposal_precision": ("proposal_precision", "minimum"),
    "maximum_duplicate_rate": ("duplicate_rate", "maximum"),
    "maximum_fragmentation_rate": ("fragmentation_rate", "maximum"),
    "maximum_incorrect_merge_rate": ("incorrect_merge_rate", "maximum"),
    "minimum_evidence_coverage": ("evidence_candidate_coverage", "minimum"),
    "minimum_primary_evidence_usefulness": ("primary_evidence_usefulness", "minimum"),
    "minimum_frame_level_animal_recall": ("frame_level_animal_recall", "minimum"),
    "maximum_false_animal_positive_frames": ("false_animal_positive_frame_count", "maximum"),
    "minimum_box_precision": ("box_precision", "minimum"),
    "minimum_box_recall": ("box_recall", "minimum"),
    "minimum_broad_class_agreement": ("broad_class_agreement", "minimum"),
}


def _threshold_results(metrics: dict[str, object], thresholds: dict[str, float]) -> list[dict[str, object]]:
    results: list[dict[str, object]] = []
    for threshold_name, target in sorted(thresholds.items()):
        metric_name, direction = _THRESHOLD_RULES.get(threshold_name, (threshold_name, "minimum"))
        metric = metrics.get(metric_name)
        if not isinstance(metric, dict) or metric.get("state") != "evaluated" or not isinstance(metric.get("value"), (int, float)):
            state = "unscorable"
            value = metric.get("value") if isinstance(metric, dict) else None
        else:
            value = metric["value"]
            passed = value >= target if direction == "minimum" else value <= target
            state = "pass" if passed else "fail"
        results.append({"threshold": threshold_name, "metric": metric_name, "direction": direction,
                        "target": target, "value": value, "state": state})
    return results
