"""Deterministic, shadow-only ordered-frame Observation Engine replay."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from typing import Protocol

from mockingbird.observation.contracts import FramePacket, ObservationResult, VisitProposal

MANIFEST_VERSION = 1
FRAME_IDENTITY_VERSION = "ordered-frame-v1"
MATCHER_VERSION = "temporal-zone-v1"
REPORT_SCHEMA_VERSION = 1
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
        if any(not frame.content_hash or frame.source_offset_ms < 0 for frame in self.frames):
            raise ReplayValidationError("invalid_frame")
        if any(a.source_offset_ms >= b.source_offset_ms for a, b in zip(self.frames, self.frames[1:])):
            raise ReplayValidationError("ordered_timestamps")

    @property
    def fingerprint(self) -> str:
        return semantic_fingerprint({"version": MANIFEST_VERSION, **asdict(self)})

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
class BenchmarkManifest:
    version: int
    benchmark_id: str
    input_fingerprint: str
    appearances: tuple[ExpectedAppearance, ...]
    visits: tuple[ExpectedVisit, ...]

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
        if any(result.creates_truth for result in results):
            raise ReplayValidationError("production_authority")
        proposals = tuple(sorted((proposal for result in results for proposal in result.visit_proposals), key=lambda item: item.proposal_key))
        if len(proposals) > MAX_PROPOSALS or any(not proposal.shadow_only for proposal in proposals):
            raise ReplayValidationError("production_authority")
        matches = _match(manifest.visits, proposals)
        metrics = _metrics(manifest, proposals, matches, frames, results)
        threshold_results = _threshold_results(metrics, thresholds or {})
        semantic = {
            "schema_version": REPORT_SCHEMA_VERSION,
            "input_fingerprint": replay.fingerprint,
            "manifest_fingerprint": manifest.fingerprint,
            "provider_key": provider_key,
            "frame_ids": [frame.frame_id for frame in frames],
            "proposals": [asdict(item) for item in proposals],
            "matches": [asdict(item) for item in matches],
            "metrics": metrics,
            "threshold_results": threshold_results,
        }
        return ReplayReport(frames, proposals, matches, metrics, semantic_fingerprint(semantic), tuple(threshold_results))


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


def _metrics(manifest: BenchmarkManifest, proposals: tuple[VisitProposal, ...], matches: tuple[Match, ...],
             frames: tuple[FramePacket, ...], results: tuple[ObservationResult, ...]) -> dict[str, object]:
    matched_ids = {item.expected_visit_id for item in matches if item.status == "matched"}
    captured = {appearance for visit in manifest.visits if visit.visit_id in matched_ids for appearance in visit.appearance_ids}
    counts = {status: sum(item.status == status for item in matches) for status in ("matched", "missed", "false", "duplicate", "fragmented", "incorrectly_merged", "ambiguous")}
    expected_count = len(manifest.visits)
    proposal_count = len(proposals)
    appearance_state = "evaluated" if manifest.appearances else "insufficient_truth"
    precision_state = "evaluated" if proposals else "not_evaluated"
    metrics: dict[str, object] = {
        "expected_appearance_count": _metric(len(manifest.appearances), "evaluated"),
        "captured_appearance_count": _metric(len(captured), appearance_state),
        "appearance_recall": _metric(len(captured) / len(manifest.appearances) if manifest.appearances else None, appearance_state),
        "expected_visit_count": _metric(expected_count, "evaluated"),
        "proposed_visit_count": _metric(proposal_count, "evaluated"),
        "matched_visit_count": _metric(counts["matched"], "evaluated"),
        "proposal_precision": _metric(counts["matched"] / proposal_count if proposal_count else None, precision_state),
        "false_proposal_count": _metric(counts["false"], "evaluated"),
        "missed_visit_count": _metric(counts["missed"], "evaluated"),
        "duplicate_count": _metric(counts["duplicate"], "evaluated"),
        "duplicate_rate": _metric(counts["duplicate"] / proposal_count if proposal_count else None, precision_state),
        "fragmentation_count": _metric(counts["fragmented"], "evaluated"),
        "fragmentation_rate": _metric(counts["fragmented"] / expected_count if expected_count else None, "evaluated" if expected_count else "insufficient_truth"),
        "incorrect_merge_count": _metric(counts["incorrectly_merged"], "evaluated"),
        "incorrect_merge_rate": _metric(counts["incorrectly_merged"] / proposal_count if proposal_count else None, precision_state),
        "zone_attribution_accuracy": _metric(None, "insufficient_truth"),
        "evidence_candidate_coverage": _metric(sum(bool(item.evidence_media_asset_ids) for item in proposals) / proposal_count if proposal_count else None, precision_state),
        "useful_evidence_coverage": _metric(None, "insufficient_truth"),
        "primary_evidence_usefulness": _metric(None, "insufficient_truth"),
        "frames_supplied": _metric(len(frames), "evaluated"),
        "frames_processed": _metric(sum(len(result.frame_packets) for result in results), "evaluated"),
        "detector_observation_count": _metric(sum(len(result.detection_observations) for result in results), "not_evaluated"),
        "track_update_count": _metric(sum(len(result.track_updates) for result in results), "not_evaluated"),
        "proposal_count": _metric(proposal_count, "evaluated"),
        "provider_error_count": _metric(0, "evaluated"),
    }
    # Compatibility aliases remain additive during the Stage 1 strangler migration.
    metrics.update({"expected_appearances": len(manifest.appearances), "captured_appearances": len(captured),
                    "appearance_recall_state": appearance_state,
                    "appearance_recall_value": metrics["appearance_recall"]["value"],
                    "proposal_precision_state": precision_state,
                    "proposal_precision_value": metrics["proposal_precision"]["value"]})
    return dict(sorted(metrics.items()))


_THRESHOLD_RULES = {
    "minimum_appearance_recall": ("appearance_recall", "minimum"),
    "minimum_proposal_precision": ("proposal_precision", "minimum"),
    "maximum_duplicate_rate": ("duplicate_rate", "maximum"),
    "maximum_fragmentation_rate": ("fragmentation_rate", "maximum"),
    "maximum_incorrect_merge_rate": ("incorrect_merge_rate", "maximum"),
    "minimum_evidence_coverage": ("evidence_candidate_coverage", "minimum"),
    "minimum_primary_evidence_usefulness": ("primary_evidence_usefulness", "minimum"),
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
