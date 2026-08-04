"""Deterministic, shadow-only ordered-frame Observation Engine replay."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from typing import Protocol

from mockingbird.observation.contracts import (
    DetectionObservation, EvidenceCandidate, FramePacket, ObservationResult, TrackUpdate, VisitProposal,
)

MANIFEST_VERSION = 1
FRAME_IDENTITY_VERSION = "ordered-frame-v1"
MATCHER_VERSION = "temporal-zone-v1"
REPORT_SCHEMA_VERSION = 2
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


@dataclass(frozen=True)
class ReplayFrame:
    index: int
    source_offset_ms: int
    content_hash: str
    source_path: str | None = None
    analysis_excluded_regions: tuple[tuple[float, float, float, float], ...] = ()


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
            frames.append(frame)
        return semantic_fingerprint({"version": MANIFEST_VERSION, "input_id": self.input_id,
            "stream_id": self.stream_id, "width": self.width, "height": self.height,
            "nominal_fps": self.nominal_fps,
            "frames": frames})

    def packets(self) -> tuple[FramePacket, ...]:
        root = self.fingerprint
        return tuple(FramePacket(
            stream_id=self.stream_id,
            media_asset_id=f"replay:{frame.index}",
            captured_at=None,
            frame_id=semantic_fingerprint((FRAME_IDENTITY_VERSION, root, frame.index, frame.source_offset_ms, frame.content_hash)),
            source_offset_ms=frame.source_offset_ms,
            width=self.width,
            height=self.height,
            source_path=frame.source_path,
            analysis_excluded_regions=frame.analysis_excluded_regions,
        ) for frame in self.frames)


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


@dataclass(frozen=True)
class ExpectedDetection:
    annotation_id: str
    frame_index: int
    broad_class: str
    bounding_box: tuple[float, float, float, float]


@dataclass(frozen=True)
class BenchmarkManifest:
    version: int
    benchmark_id: str
    input_fingerprint: str
    appearances: tuple[ExpectedAppearance, ...]
    visits: tuple[ExpectedVisit, ...]
    detections: tuple[ExpectedDetection, ...] = ()

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
        metrics = _metrics(
            manifest, proposals, matches, frames, results,
            visit_supported=visit_supported, detection_supported=detection_supported,
            track_supported=track_supported,
        )
        metrics.update(_pipeline_metrics(
            frames, proposals, track_updates, evidence_candidates, pipeline_facts,
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
            "pipeline_facts": pipeline_facts,
            "provider_key": provider_key,
            "frame_ids": [frame.frame_id for frame in frames],
            "proposals": [asdict(item) for item in proposals],
            "matches": [asdict(item) for item in matches],
            "metrics": metrics,
            "threshold_results": threshold_results,
        }
        return ReplayReport(
            frames, proposals, matches, metrics, semantic_fingerprint(semantic),
            tuple(threshold_results), (), detections, track_updates,
            evidence_candidates, pipeline_facts,
        )


def _pipeline_metrics(
    frames: tuple[FramePacket, ...],
    proposals: tuple[VisitProposal, ...],
    track_updates: tuple[TrackUpdate, ...],
    evidence: tuple[EvidenceCandidate, ...],
    facts: dict[str, object],
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
    return unavailable | {
        "evidence_candidate_count": _metric(len(evidence) if visit_supported else None, evidence_state),
        "proposals_with_evidence": _metric(
            len(proposal_generations & evidence_generations) if visit_supported else None, evidence_state,
        ),
        "evidence_subject_containment": _metric(None, "insufficient_truth" if visit_supported else "not_evaluated"),
        "evidence_temporal_offset_ms": _metric(None, "insufficient_truth" if visit_supported else "not_evaluated"),
        "track_duration_error_ms": _metric(None, "insufficient_truth" if track_supported else "not_evaluated"),
    }


_COMPARISON_METRICS = (
    "appearance_recall", "proposal_precision", "fragmentation_rate",
    "duplicate_rate", "incorrect_merge_rate", "evidence_candidate_coverage",
    "frames_inferred",
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
        comparisons.append({
            "metric": name,
            "left": {"state": left_state, "value": left_value},
            "right": {"state": right_state, "value": right_value},
            "difference": difference,
        })
    semantic = {"comparison_version": "observation-provider-comparison-v1", "metrics": comparisons}
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
        "zone_attribution_accuracy": _metric(None, "insufficient_truth" if visit_supported else "not_evaluated"),
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
