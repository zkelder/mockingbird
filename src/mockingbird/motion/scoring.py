"""Pure zone-aware motion scoring for small grayscale frame planes.

This module is the deterministic scoring core for the stream -> zone -> motion
evidence path. Stream ingestion, frame sampling, media decoding, event creation,
and species suggestion are later layers. Motion scores are evidence only; user
review and correction remain the dataset truth.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from math import ceil, floor, isfinite
from numbers import Real

Number = int | float
FramePlane = Sequence[Sequence[Number]]


@dataclass(frozen=True)
class MotionZone:
    """Normalized rectangular zone drawn over a future stream frame."""

    zone_id: str
    left: float
    top: float
    right: float
    bottom: float


@dataclass(frozen=True)
class MotionScore:
    """Motion evidence for one zone in one pair of frame planes."""

    zone_id: str
    changed_pixels: int
    total_pixels: int
    changed_ratio: float
    mean_delta: float
    triggered: bool


@dataclass(frozen=True)
class MotionFrameScore:
    """Zone scores for a sampled frame pair, before any product record is made."""

    frame_index: int
    scores: list[MotionScore]
    triggered_zone_ids: list[str]
    strongest_zone_id: str | None
    strongest_changed_ratio: float


@dataclass(frozen=True)
class MotionCandidate:
    """Debounced motion evidence that can later point at a best frame."""

    zone_id: str
    start_frame_index: int
    end_frame_index: int
    best_frame_index: int
    peak_changed_ratio: float
    triggered_frame_count: int


def score_zone_motion(
    previous_frame: FramePlane,
    current_frame: FramePlane,
    zone: MotionZone,
    *,
    pixel_delta_threshold: float = 25.0,
    min_changed_ratio: float = 0.02,
) -> MotionScore:
    """Compare two frame planes inside one zone and return evidence-only motion."""

    width, height = _validate_frame_pair(previous_frame, current_frame)
    _validate_thresholds(
        pixel_delta_threshold=pixel_delta_threshold,
        min_changed_ratio=min_changed_ratio,
    )
    left, top, right, bottom = _zone_pixel_bounds(zone, width=width, height=height)

    changed_pixels = 0
    total_pixels = 0
    total_delta = 0.0

    for y in range(top, bottom):
        previous_row = previous_frame[y]
        current_row = current_frame[y]
        for x in range(left, right):
            delta = abs(float(current_row[x]) - float(previous_row[x]))
            total_delta += delta
            total_pixels += 1
            if delta >= pixel_delta_threshold:
                changed_pixels += 1

    changed_ratio = changed_pixels / total_pixels
    mean_delta = total_delta / total_pixels

    return MotionScore(
        zone_id=zone.zone_id,
        changed_pixels=changed_pixels,
        total_pixels=total_pixels,
        changed_ratio=changed_ratio,
        mean_delta=mean_delta,
        triggered=changed_ratio >= min_changed_ratio,
    )


def score_frame_motion(
    previous_frame: FramePlane,
    current_frame: FramePlane,
    zones: Sequence[MotionZone],
    *,
    frame_index: int,
    pixel_delta_threshold: float = 25.0,
    min_changed_ratio: float = 0.02,
) -> MotionFrameScore:
    """Score all zones for one sampled frame pair without creating product truth."""

    scores = [
        score_zone_motion(
            previous_frame,
            current_frame,
            zone,
            pixel_delta_threshold=pixel_delta_threshold,
            min_changed_ratio=min_changed_ratio,
        )
        for zone in zones
    ]
    triggered_zone_ids = [score.zone_id for score in scores if score.triggered]

    strongest_score = max(scores, key=lambda score: score.changed_ratio, default=None)

    return MotionFrameScore(
        frame_index=frame_index,
        scores=scores,
        triggered_zone_ids=triggered_zone_ids,
        strongest_zone_id=strongest_score.zone_id if strongest_score else None,
        strongest_changed_ratio=strongest_score.changed_ratio if strongest_score else 0.0,
    )


def extract_motion_candidates(
    frame_scores: Sequence[MotionFrameScore],
    *,
    min_triggered_frames: int = 2,
    max_gap_frames: int = 1,
) -> list[MotionCandidate]:
    """Debounce triggered zone scores into candidate evidence windows.

    The output supports a later ring-buffer/best-frame layer, but it does not
    read media, save evidence, or create events/visits.
    """

    if min_triggered_frames < 1:
        raise ValueError("min_triggered_frames must be at least 1")
    if max_gap_frames < 0:
        raise ValueError("max_gap_frames must be at least 0")

    triggered_by_zone: dict[str, list[tuple[int, float]]] = defaultdict(list)
    for frame_score in frame_scores:
        for score in frame_score.scores:
            if score.triggered:
                triggered_by_zone[score.zone_id].append(
                    (frame_score.frame_index, score.changed_ratio)
                )

    candidates: list[MotionCandidate] = []
    for zone_id, triggered_frames in triggered_by_zone.items():
        sorted_frames = sorted(triggered_frames)
        group: list[tuple[int, float]] = []

        for frame_index, changed_ratio in sorted_frames:
            if not group:
                group = [(frame_index, changed_ratio)]
                continue

            previous_frame_index = group[-1][0]
            gap_frames = frame_index - previous_frame_index - 1
            if gap_frames <= max_gap_frames:
                group.append((frame_index, changed_ratio))
                continue

            _append_candidate_if_ready(
                candidates,
                zone_id=zone_id,
                group=group,
                min_triggered_frames=min_triggered_frames,
            )
            group = [(frame_index, changed_ratio)]

        _append_candidate_if_ready(
            candidates,
            zone_id=zone_id,
            group=group,
            min_triggered_frames=min_triggered_frames,
        )

    return sorted(
        candidates,
        key=lambda candidate: (candidate.start_frame_index, candidate.zone_id),
    )


def _append_candidate_if_ready(
    candidates: list[MotionCandidate],
    *,
    zone_id: str,
    group: Sequence[tuple[int, float]],
    min_triggered_frames: int,
) -> None:
    if len(group) < min_triggered_frames:
        return

    best_frame_index, peak_changed_ratio = max(group, key=lambda item: item[1])
    candidates.append(
        MotionCandidate(
            zone_id=zone_id,
            start_frame_index=group[0][0],
            end_frame_index=group[-1][0],
            best_frame_index=best_frame_index,
            peak_changed_ratio=peak_changed_ratio,
            triggered_frame_count=len(group),
        )
    )


def _validate_frame_pair(
    previous_frame: FramePlane,
    current_frame: FramePlane,
) -> tuple[int, int]:
    previous_width, previous_height = _validate_frame(previous_frame, name="previous_frame")
    current_width, current_height = _validate_frame(current_frame, name="current_frame")
    if (previous_width, previous_height) != (current_width, current_height):
        raise ValueError("previous_frame and current_frame dimensions must match")
    return previous_width, previous_height


def _validate_frame(frame: FramePlane, *, name: str) -> tuple[int, int]:
    if isinstance(frame, (str, bytes)) or not isinstance(frame, Sequence):
        raise ValueError(f"{name} must be a non-empty rectangular 2D sequence")
    if len(frame) == 0:
        raise ValueError(f"{name} must be a non-empty rectangular 2D sequence")

    expected_width: int | None = None
    for row_index, row in enumerate(frame):
        if isinstance(row, (str, bytes)) or not isinstance(row, Sequence):
            raise ValueError(f"{name} rows must be non-empty sequences")
        if len(row) == 0:
            raise ValueError(f"{name} rows must be non-empty sequences")
        if expected_width is None:
            expected_width = len(row)
        elif len(row) != expected_width:
            raise ValueError(f"{name} must be rectangular")

        for value in row:
            if not _is_pixel_number(value):
                raise ValueError(f"{name} pixels must be numeric ints or floats")

    return expected_width or 0, row_index + 1


def _is_pixel_number(value: object) -> bool:
    return isinstance(value, Real) and not isinstance(value, bool) and isfinite(float(value))


def _validate_zone(zone: MotionZone) -> None:
    if not isinstance(zone.zone_id, str) or not zone.zone_id.strip():
        raise ValueError("zone_id must be a non-empty string")

    bounds = {
        "left": zone.left,
        "top": zone.top,
        "right": zone.right,
        "bottom": zone.bottom,
    }
    for name, value in bounds.items():
        if not _is_pixel_number(value):
            raise ValueError(f"zone {zone.zone_id!r} {name} must be a normalized number")
        if value < 0.0 or value > 1.0:
            raise ValueError(f"zone {zone.zone_id!r} bounds must be normalized 0.0 to 1.0")

    if zone.left >= zone.right or zone.top >= zone.bottom:
        raise ValueError(f"zone {zone.zone_id!r} must have left < right and top < bottom")


def _zone_pixel_bounds(
    zone: MotionZone,
    *,
    width: int,
    height: int,
) -> tuple[int, int, int, int]:
    _validate_zone(zone)

    left = _clamp_pixel_bound(floor(zone.left * width), maximum=width)
    top = _clamp_pixel_bound(floor(zone.top * height), maximum=height)
    right = _clamp_pixel_bound(ceil(zone.right * width), maximum=width)
    bottom = _clamp_pixel_bound(ceil(zone.bottom * height), maximum=height)

    if right <= left or bottom <= top:
        raise ValueError(f"zone {zone.zone_id!r} must overlap at least one frame pixel")

    return left, top, right, bottom


def _clamp_pixel_bound(value: int, *, maximum: int) -> int:
    return max(0, min(maximum, value))


def _validate_thresholds(
    *,
    pixel_delta_threshold: float,
    min_changed_ratio: float,
) -> None:
    if not _is_pixel_number(pixel_delta_threshold) or pixel_delta_threshold < 0:
        raise ValueError("pixel_delta_threshold must be a non-negative number")
    if (
        not _is_pixel_number(min_changed_ratio)
        or min_changed_ratio < 0.0
        or min_changed_ratio > 1.0
    ):
        raise ValueError("min_changed_ratio must be a number from 0.0 to 1.0")
