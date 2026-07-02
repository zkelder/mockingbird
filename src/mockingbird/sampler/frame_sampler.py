"""Sampler abstraction for caller-supplied grayscale frame planes.

The sampler is an underneath-the-product boundary: it evaluates supplied frame
planes into motion candidates and can create pending MotionEvidence, but it does
not read media, connect streams, run detectors, or create review truth.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from math import isfinite
from numbers import Real
from typing import Protocol

from mockingbird.api.schemas import MotionEvidenceCreateRequest, MotionEvidenceResponse
from mockingbird.motion import (
    MotionCandidate,
    MotionFrameScore,
    MotionZone,
    extract_motion_candidates,
    score_frame_motion,
)
from mockingbird.motion.scoring import FramePlane


@dataclass(frozen=True)
class SamplerZone:
    """Normalized stream zone passed to motion scoring."""

    zone_id: str
    left: float
    top: float
    right: float
    bottom: float


@dataclass(frozen=True)
class SamplerConfig:
    """Evidence-only scoring and candidate creation settings."""

    pixel_delta_threshold: float = 25.0
    min_changed_ratio: float = 0.02
    min_triggered_frames: int = 2
    max_gap_frames: int = 1
    frame_index_start: int = 0
    create_motion_evidence: bool = False


@dataclass(frozen=True)
class SamplerContext:
    """Product context for optional pending MotionEvidence creation."""

    source_id: str | None = None
    stream_id: str | None = None
    notes: str | None = None


@dataclass(frozen=True)
class SamplerResult:
    """Motion candidates produced from supplied frame planes."""

    frame_scores: list[MotionFrameScore]
    candidates: list[MotionCandidate]
    created_evidence: list[MotionEvidenceResponse] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class MotionEvidenceRepository(Protocol):
    """Repository behavior needed to create pending MotionEvidence."""

    def create_motion_evidence(
        self,
        payload: MotionEvidenceCreateRequest,
    ) -> MotionEvidenceResponse:
        """Persist pending MotionEvidence without creating review truth."""
        ...


def evaluate_sampled_frame_sequence(
    frames: Sequence[FramePlane],
    zones: Sequence[SamplerZone],
    config: SamplerConfig | None = None,
) -> SamplerResult:
    """Evaluate supplied frame planes into evidence-only motion candidates."""

    active_config = config or SamplerConfig()
    _validate_sampler_inputs(frames=frames, zones=zones, config=active_config)

    motion_zones = [_motion_zone(zone) for zone in zones]
    frame_scores = [
        score_frame_motion(
            frames[pair_index],
            frames[pair_index + 1],
            motion_zones,
            frame_index=active_config.frame_index_start + pair_index + 1,
            pixel_delta_threshold=active_config.pixel_delta_threshold,
            min_changed_ratio=active_config.min_changed_ratio,
        )
        for pair_index in range(len(frames) - 1)
    ]
    candidates = extract_motion_candidates(
        frame_scores,
        min_triggered_frames=active_config.min_triggered_frames,
        max_gap_frames=active_config.max_gap_frames,
    )

    return SamplerResult(frame_scores=frame_scores, candidates=candidates)


def create_motion_evidence_from_sampler_result(
    repository: MotionEvidenceRepository,
    sampler_result: SamplerResult,
    context: SamplerContext | None = None,
    config: SamplerConfig | None = None,
) -> list[MotionEvidenceResponse]:
    """Create pending MotionEvidence from candidates when explicitly enabled."""

    active_config = config or SamplerConfig()
    _validate_sampler_config(active_config)
    if not active_config.create_motion_evidence:
        return []

    active_context = context or SamplerContext()
    created_evidence: list[MotionEvidenceResponse] = []
    for candidate in sampler_result.candidates:
        payload = MotionEvidenceCreateRequest(
            source_id=active_context.source_id,
            stream_id=active_context.stream_id,
            zone_id=candidate.zone_id,
            start_frame_index=candidate.start_frame_index,
            end_frame_index=candidate.end_frame_index,
            best_frame_index=candidate.best_frame_index,
            peak_changed_ratio=candidate.peak_changed_ratio,
            triggered_frame_count=candidate.triggered_frame_count,
            scoring_config=_scoring_config(active_config),
            notes=active_context.notes,
        )
        created_evidence.append(repository.create_motion_evidence(payload))

    return created_evidence


def _motion_zone(zone: SamplerZone) -> MotionZone:
    return MotionZone(
        zone_id=zone.zone_id,
        left=zone.left,
        top=zone.top,
        right=zone.right,
        bottom=zone.bottom,
    )


def _validate_sampler_inputs(
    *,
    frames: Sequence[FramePlane],
    zones: Sequence[SamplerZone],
    config: SamplerConfig,
) -> None:
    if isinstance(frames, (str, bytes)) or not isinstance(frames, Sequence):
        raise ValueError("frames must be a sequence of frame planes")
    if len(frames) < 2:
        raise ValueError("frames must contain at least 2 frame planes")

    if isinstance(zones, (str, bytes)) or not isinstance(zones, Sequence):
        raise ValueError("zones must be a sequence of sampler zones")
    if len(zones) < 1:
        raise ValueError("zones must contain at least 1 zone")

    _validate_sampler_config(config)


def _validate_sampler_config(config: SamplerConfig) -> None:
    if (
        not _is_number(config.pixel_delta_threshold)
        or config.pixel_delta_threshold < 0
    ):
        raise ValueError("pixel_delta_threshold must be a non-negative number")
    if (
        not _is_number(config.min_changed_ratio)
        or config.min_changed_ratio < 0.0
        or config.min_changed_ratio > 1.0
    ):
        raise ValueError("min_changed_ratio must be a number from 0.0 to 1.0")
    if not _is_int(config.min_triggered_frames) or config.min_triggered_frames < 1:
        raise ValueError("min_triggered_frames must be at least 1")
    if not _is_int(config.max_gap_frames) or config.max_gap_frames < 0:
        raise ValueError("max_gap_frames must be at least 0")
    if not _is_int(config.frame_index_start) or config.frame_index_start < 0:
        raise ValueError("frame_index_start must be a non-negative integer")


def _scoring_config(config: SamplerConfig) -> dict[str, str | int | float | bool]:
    return {
        "source": "sampler",
        "pixel_delta_threshold": config.pixel_delta_threshold,
        "min_changed_ratio": config.min_changed_ratio,
        "min_triggered_frames": config.min_triggered_frames,
        "max_gap_frames": config.max_gap_frames,
        "frame_index_start": config.frame_index_start,
    }


def _is_number(value: object) -> bool:
    return isinstance(value, Real) and not isinstance(value, bool) and isfinite(float(value))


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)
