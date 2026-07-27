"""Bounded foreground-region tracking for live outdoor activity.

The monitor owns one instance per Stream.  It deliberately returns observation
evidence instead of product records: the existing activity-session and review
handoff remain the only place that creates an Event or Visit, and correction
remains the truth boundary.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime
from hashlib import sha1
from math import hypot
from typing import Literal

import cv2
import numpy as np


AnalysisPreset = Literal["high_sensitivity", "normal", "low_noise"]

DEFAULT_ANALYSIS_WIDTH = 640
DEFAULT_ANALYSIS_HEIGHT = 360
DEFAULT_ANALYSIS_FPS = 5
MAX_TRACKS_PER_STREAM = 24
MAX_TRACK_HISTORY = 20
PRETRIGGER_FRAME_COUNT = 10
MAX_FRAME_GAP_SECONDS = 15.0
MAX_TRIGGER_FRAMES = 5
TRIGGER_HITS = 2
STATIONARY_MISSED_FRAMES = 15


@dataclass(frozen=True)
class TrackedZone:
    """Normalized product Zone geometry used only for analysis association."""

    zone_id: str
    zone_type: str
    points: tuple[tuple[float, float], ...]
    blocked: bool = False


@dataclass(frozen=True)
class FrameTelemetry:
    source_width: int
    source_height: int
    analysis_width: int
    analysis_height: int
    frame_identity: str
    captured_at: datetime
    frame_age_ms: int
    duplicate_frame_count: int
    dropped_frame_count: int
    frozen_frame_count: int
    accepted: bool
    ignored_reason: str | None = None
    zone_source_crop_width: int | None = None
    zone_source_crop_height: int | None = None
    analysis_zone_id: str | None = None


@dataclass(frozen=True)
class MotionRegion:
    left: float
    top: float
    right: float
    bottom: float
    centroid_x: float
    centroid_y: float
    pixel_area: int
    zone_relative_area: float
    mask_occupancy: float
    zone_id: str
    frame_identity: str
    captured_at: datetime

    def as_dict(self) -> dict[str, object]:
        return {
            "left": self.left,
            "top": self.top,
            "right": self.right,
            "bottom": self.bottom,
            "centroid_x": self.centroid_x,
            "centroid_y": self.centroid_y,
            "pixel_area": self.pixel_area,
            "zone_relative_area": self.zone_relative_area,
            "mask_occupancy": self.mask_occupancy,
            "zone_id": self.zone_id,
            "frame_identity": self.frame_identity,
            "captured_at": self.captured_at,
        }


@dataclass(frozen=True)
class TrackedObject:
    track_id: str
    state: Literal["active", "stationary", "disappeared"]
    first_seen_at: datetime
    last_seen_at: datetime
    hit_count: int
    missed_frame_count: int
    zone_ids: tuple[str, ...]
    left: float
    top: float
    right: float
    bottom: float
    centroid_path: tuple[tuple[float, float], ...]
    best_frame_identity: str | None
    triggered: bool
    verified_label: str | None = None
    verified_confidence: float | None = None

    def as_dict(self) -> dict[str, object]:
        return {
            "track_id": self.track_id,
            "state": self.state,
            "first_seen_at": self.first_seen_at,
            "last_seen_at": self.last_seen_at,
            "hit_count": self.hit_count,
            "missed_frame_count": self.missed_frame_count,
            "zone_ids": list(self.zone_ids),
            "left": self.left,
            "top": self.top,
            "right": self.right,
            "bottom": self.bottom,
            "centroid_path": [list(point) for point in self.centroid_path],
            "best_frame_identity": self.best_frame_identity,
            "triggered": self.triggered,
            "verified_label": self.verified_label,
            "verified_confidence": self.verified_confidence,
        }


@dataclass(frozen=True)
class TrackTrigger:
    track_id: str
    zone_id: str
    first_frame_identity: str | None
    best_frame_identity: str | None
    pretrigger_frame_identities: tuple[str, ...]
    reason: Literal["coherent_track", "verified_track"]
    verified: bool = False


@dataclass(frozen=True)
class TrackedActivityResult:
    telemetry: FrameTelemetry
    regions: tuple[MotionRegion, ...] = ()
    tracks: tuple[TrackedObject, ...] = ()
    triggers: tuple[TrackTrigger, ...] = ()
    foreground_mask: np.ndarray | None = None
    global_illumination_suppressed: bool = False
    foreground_model_state: Literal["warming", "ready", "reset"] = "warming"


@dataclass
class _Track:
    track_id: str
    first_seen_at: datetime
    last_seen_at: datetime
    first_sequence: int
    last_sequence: int
    region: MotionRegion
    hit_count: int = 1
    missed_frame_count: int = 0
    triggered: bool = False
    state: Literal["active", "stationary", "disappeared"] = "active"
    zone_ids: set[str] = field(default_factory=set)
    boxes: deque[MotionRegion] = field(
        default_factory=lambda: deque(maxlen=MAX_TRACK_HISTORY)
    )
    centroid_path: deque[tuple[float, float]] = field(
        default_factory=lambda: deque(maxlen=MAX_TRACK_HISTORY)
    )
    best_frame_identity: str | None = None

    @classmethod
    def from_region(
        cls,
        track_id: str,
        region: MotionRegion,
        sequence: int,
    ) -> "_Track":
        track = cls(
            track_id=track_id,
            first_seen_at=region.captured_at,
            last_seen_at=region.captured_at,
            first_sequence=sequence,
            last_sequence=sequence,
            region=region,
            zone_ids={region.zone_id},
            best_frame_identity=region.frame_identity,
        )
        track.boxes.append(region)
        track.centroid_path.append((region.centroid_x, region.centroid_y))
        return track

    def observe(self, region: MotionRegion, sequence: int) -> None:
        self.region = region
        self.last_seen_at = region.captured_at
        self.last_sequence = sequence
        self.hit_count += 1
        self.missed_frame_count = 0
        self.state = "active"
        self.zone_ids.add(region.zone_id)
        self.boxes.append(region)
        self.centroid_path.append((region.centroid_x, region.centroid_y))
        if self.best_frame_identity is None or region.pixel_area >= max(
            item.pixel_area for item in self.boxes
        ):
            self.best_frame_identity = region.frame_identity

    def snapshot(self) -> TrackedObject:
        region = self.region
        return TrackedObject(
            track_id=self.track_id,
            state=self.state,
            first_seen_at=self.first_seen_at,
            last_seen_at=self.last_seen_at,
            hit_count=self.hit_count,
            missed_frame_count=self.missed_frame_count,
            zone_ids=tuple(sorted(self.zone_ids)),
            left=region.left,
            top=region.top,
            right=region.right,
            bottom=region.bottom,
            centroid_path=tuple(self.centroid_path),
            best_frame_identity=self.best_frame_identity,
            triggered=self.triggered,
        )


@dataclass(frozen=True)
class _PresetSettings:
    var_threshold: float
    min_area_by_zone: dict[str, int]
    max_area_ratio: float


_PRESETS: dict[AnalysisPreset, _PresetSettings] = {
    "high_sensitivity": _PresetSettings(
        var_threshold=12.0,
        min_area_by_zone={
            "feeder": 8,
            "perch": 8,
            "birdbath": 10,
            "ground": 28,
            "yard": 36,
            "driveway": 72,
        },
        max_area_ratio=0.35,
    ),
    "normal": _PresetSettings(
        var_threshold=18.0,
        min_area_by_zone={
            "feeder": 12,
            "perch": 12,
            "birdbath": 14,
            "ground": 42,
            "yard": 56,
            "driveway": 110,
        },
        max_area_ratio=0.30,
    ),
    "low_noise": _PresetSettings(
        var_threshold=28.0,
        min_area_by_zone={
            "feeder": 22,
            "perch": 22,
            "birdbath": 26,
            "ground": 72,
            "yard": 96,
            "driveway": 160,
        },
        max_area_ratio=0.24,
    ),
}


class TrackedOutdoorActivityDetector:
    """One non-durable MOG2 foreground model and tracker for one Stream."""

    def __init__(
        self,
        stream_id: str,
        *,
        preset: AnalysisPreset = "normal",
        analysis_fps: int = DEFAULT_ANALYSIS_FPS,
    ) -> None:
        self.stream_id = stream_id
        self.preset = preset
        self.analysis_fps = analysis_fps
        self._settings = _PRESETS[preset]
        self._background = self._new_background_model()
        self._dimensions: tuple[int, int] | None = None
        self._last_sequence: int | None = None
        self._last_captured_at: datetime | None = None
        self._last_identity: str | None = None
        self._last_mean: float | None = None
        self._accepted_count = 0
        self._duplicate_count = 0
        self._dropped_count = 0
        self._frozen_count = 0
        self._next_track = 1
        self._tracks: dict[str, _Track] = {}
        self._ring: deque[tuple[str, int, datetime]] = deque(
            maxlen=PRETRIGGER_FRAME_COUNT
        )

    def reset(self) -> None:
        self._background = self._new_background_model()
        self._dimensions = None
        self._last_sequence = None
        self._last_captured_at = None
        self._last_identity = None
        self._last_mean = None
        self._accepted_count = 0
        self._tracks.clear()
        self._ring.clear()

    @property
    def last_sequence(self) -> int | None:
        """The last accepted cache sequence; callers must not replay history."""

        return self._last_sequence

    def observe(
        self,
        frame: np.ndarray,
        *,
        sequence: int,
        captured_at: datetime,
        source_width: int,
        source_height: int,
        frame_identity: str | None,
        zones: tuple[TrackedZone, ...],
        coordinate_box: tuple[float, float, float, float] = (0.0, 0.0, 1.0, 1.0),
        now: datetime | None = None,
    ) -> TrackedActivityResult:
        """Process exactly one fresh analysis frame.

        `frame` must already be a bounded luminance plane.  The original camera
        bytes stay in the existing live cache for later evidence selection.
        """

        captured_at = _utc(captured_at)
        observed_at = _utc(now or datetime.now(UTC))
        gray = _validate_luminance_frame(frame)
        height, width = gray.shape
        identity = frame_identity or _frame_identity(gray)
        frame_age_ms = max(0, int((observed_at - captured_at).total_seconds() * 1000))
        reset_required = (
            self._dimensions is not None and self._dimensions != (width, height)
        ) or (
            self._last_captured_at is not None
            and (captured_at - self._last_captured_at).total_seconds()
            > MAX_FRAME_GAP_SECONDS
        )
        if reset_required:
            self.reset()

        ignored_reason: str | None = None
        if self._last_sequence is not None and sequence <= self._last_sequence:
            ignored_reason = "non_monotonic_frame"
            self._dropped_count += 1
        elif self._last_identity == identity:
            ignored_reason = "duplicate_frame"
            self._duplicate_count += 1
            self._frozen_count += 1
        elif self._last_captured_at is not None and captured_at <= self._last_captured_at:
            ignored_reason = "non_monotonic_timestamp"
            self._dropped_count += 1

        telemetry = FrameTelemetry(
            source_width=source_width,
            source_height=source_height,
            analysis_width=width,
            analysis_height=height,
            frame_identity=identity,
            captured_at=captured_at,
            frame_age_ms=frame_age_ms,
            duplicate_frame_count=self._duplicate_count,
            dropped_frame_count=self._dropped_count,
            frozen_frame_count=self._frozen_count,
            accepted=ignored_reason is None,
            ignored_reason=ignored_reason,
        )
        if ignored_reason is not None:
            return TrackedActivityResult(
                telemetry=telemetry,
                tracks=tuple(track.snapshot() for track in self._tracks.values()),
                foreground_model_state="reset" if reset_required else self._model_state(),
            )

        if self._last_sequence is not None and sequence > self._last_sequence + 1:
            self._dropped_count += sequence - self._last_sequence - 1
            telemetry = FrameTelemetry(**{**telemetry.__dict__, "dropped_frame_count": self._dropped_count})

        self._dimensions = (width, height)
        self._last_sequence = sequence
        self._last_captured_at = captured_at
        self._last_identity = identity
        self._ring.append((identity, sequence, captured_at))
        self._accepted_count += 1

        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        mean_luminance = float(blurred.mean())
        global_change = (
            self._last_mean is not None and abs(mean_luminance - self._last_mean) >= 35.0
        )
        self._last_mean = mean_luminance
        raw_mask = self._background.apply(blurred)
        foreground = cv2.threshold(raw_mask, 200, 255, cv2.THRESH_BINARY)[1]
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        foreground = cv2.morphologyEx(foreground, cv2.MORPH_OPEN, kernel, iterations=1)
        foreground = cv2.morphologyEx(foreground, cv2.MORPH_CLOSE, kernel, iterations=2)
        foreground_ratio = float(np.count_nonzero(foreground)) / float(foreground.size)
        illumination_suppressed = global_change or foreground_ratio >= 0.60
        if illumination_suppressed or self._accepted_count <= 2:
            foreground.fill(0)
            regions: tuple[MotionRegion, ...] = ()
        else:
            regions = tuple(
                self._regions(
                    foreground,
                    zones,
                    identity,
                    captured_at,
                    coordinate_box=coordinate_box,
                )
            )
        triggers = self._update_tracks(regions, sequence)
        return TrackedActivityResult(
            telemetry=telemetry,
            regions=regions,
            tracks=tuple(track.snapshot() for track in self._tracks.values()),
            triggers=tuple(triggers),
            foreground_mask=foreground,
            global_illumination_suppressed=illumination_suppressed,
            foreground_model_state="reset" if reset_required else self._model_state(),
        )

    def _new_background_model(self) -> cv2.BackgroundSubtractor:
        return cv2.createBackgroundSubtractorMOG2(
            history=max(25, self.analysis_fps * 12),
            varThreshold=self._settings.var_threshold,
            detectShadows=True,
        )

    def _model_state(self) -> Literal["warming", "ready", "reset"]:
        return "ready" if self._accepted_count >= 3 else "warming"

    def _regions(
        self,
        foreground: np.ndarray,
        zones: tuple[TrackedZone, ...],
        identity: str,
        captured_at: datetime,
        *,
        coordinate_box: tuple[float, float, float, float],
    ) -> list[MotionRegion]:
        height, width = foreground.shape
        ordinary = tuple(zone for zone in zones if not zone.blocked)
        if not ordinary:
            return []
        allowed = np.zeros_like(foreground)
        blocked = np.zeros_like(foreground)
        for zone in ordinary:
            cv2.fillPoly(allowed, [_zone_polygon(zone, width, height)], 255)
        for zone in zones:
            if zone.blocked:
                cv2.fillPoly(blocked, [_zone_polygon(zone, width, height)], 255)
        mask = cv2.bitwise_and(foreground, allowed)
        mask[blocked > 0] = 0
        component_count, _labels, stats, centroids = cv2.connectedComponentsWithStats(
            mask, connectivity=8
        )
        regions: list[MotionRegion] = []
        for index in range(1, component_count):
            x, y, box_width, box_height, area = (int(item) for item in stats[index])
            if area <= 0:
                continue
            zone = _region_zone(ordinary, x, y, box_width, box_height, width, height)
            if zone is None:
                continue
            zone_pixels = max(1, _zone_area_pixels(zone, width, height))
            region_ratio = area / float(zone_pixels)
            min_area = self._settings.min_area_by_zone.get(zone.zone_type, 48)
            if area < min_area or region_ratio > self._settings.max_area_ratio:
                continue
            centroid_x, centroid_y = (float(item) for item in centroids[index])
            source_left, source_top, source_right, source_bottom = coordinate_box
            source_width = source_right - source_left
            source_height = source_bottom - source_top
            regions.append(
                MotionRegion(
                    left=source_left + (x / width) * source_width,
                    top=source_top + (y / height) * source_height,
                    right=source_left + ((x + box_width) / width) * source_width,
                    bottom=source_top + ((y + box_height) / height) * source_height,
                    centroid_x=source_left + (centroid_x / width) * source_width,
                    centroid_y=source_top + (centroid_y / height) * source_height,
                    pixel_area=area,
                    zone_relative_area=region_ratio,
                    mask_occupancy=area / float(max(1, box_width * box_height)),
                    zone_id=zone.zone_id,
                    frame_identity=identity,
                    captured_at=captured_at,
                )
            )
        return _merge_nearby_regions(regions)

    def _update_tracks(
        self,
        regions: tuple[MotionRegion, ...],
        sequence: int,
    ) -> list[TrackTrigger]:
        unmatched = set(range(len(regions)))
        for track in sorted(self._tracks.values(), key=lambda item: item.last_seen_at):
            if track.state == "disappeared":
                continue
            match_index = _best_track_match(track, regions, unmatched)
            if match_index is None:
                track.missed_frame_count += 1
                track.state = (
                    "stationary"
                    if track.triggered and track.missed_frame_count <= STATIONARY_MISSED_FRAMES
                    else "disappeared"
                )
                continue
            unmatched.remove(match_index)
            track.observe(regions[match_index], sequence)

        triggers: list[TrackTrigger] = []
        for index in sorted(unmatched):
            region = regions[index]
            track_id = f"track-{self._next_track:04d}"
            self._next_track += 1
            self._tracks[track_id] = _Track.from_region(track_id, region, sequence)

        for track in self._tracks.values():
            if track.triggered or track.state != "active":
                continue
            frame_span = track.last_sequence - track.first_sequence + 1
            elapsed = (track.last_seen_at - track.first_seen_at).total_seconds()
            if track.hit_count < TRIGGER_HITS or frame_span > MAX_TRIGGER_FRAMES or elapsed > 1.5:
                continue
            track.triggered = True
            pretrigger = tuple(identity for identity, _sequence, _at in list(self._ring)[:-1][-2:])
            triggers.append(
                TrackTrigger(
                    track_id=track.track_id,
                    zone_id=track.region.zone_id,
                    first_frame_identity=(track.boxes[0].frame_identity if track.boxes else None),
                    best_frame_identity=track.best_frame_identity,
                    pretrigger_frame_identities=pretrigger,
                    reason="coherent_track",
                    verified=False,
                )
            )
        if len(self._tracks) > MAX_TRACKS_PER_STREAM:
            stale = sorted(self._tracks.values(), key=lambda item: item.last_seen_at)[: -MAX_TRACKS_PER_STREAM]
            for track in stale:
                self._tracks.pop(track.track_id, None)
        return triggers


class TrackedOutdoorActivityDetectorManager:
    """In-memory Stream registry; no detector state is persisted across restart."""

    def __init__(self) -> None:
        self._detectors: dict[str, TrackedOutdoorActivityDetector] = {}

    def for_stream(
        self,
        stream_id: str,
        *,
        preset: AnalysisPreset = "normal",
    ) -> TrackedOutdoorActivityDetector:
        detector = self._detectors.get(stream_id)
        if detector is None or detector.preset != preset:
            detector = TrackedOutdoorActivityDetector(stream_id, preset=preset)
            self._detectors[stream_id] = detector
        return detector

    def for_zone(
        self,
        stream_id: str,
        zone_id: str,
        *,
        preset: AnalysisPreset = "normal",
    ) -> TrackedOutdoorActivityDetector:
        """Keep background and track state independent for each product Zone."""

        return self.for_stream(f"{stream_id}:zone:{zone_id}", preset=preset)

    def reset(self, stream_id: str) -> None:
        self._detectors.pop(stream_id, None)
        prefix = f"{stream_id}:zone:"
        for key in [key for key in self._detectors if key.startswith(prefix)]:
            self._detectors.pop(key, None)


def _validate_luminance_frame(frame: np.ndarray) -> np.ndarray:
    if not isinstance(frame, np.ndarray) or frame.ndim != 2 or frame.size == 0:
        raise ValueError("analysis_frame_invalid")
    if frame.dtype != np.uint8:
        return np.clip(frame, 0, 255).astype(np.uint8)
    return frame


def _frame_identity(frame: np.ndarray) -> str:
    return sha1(frame.tobytes()).hexdigest()[:20]


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _zone_polygon(zone: TrackedZone, width: int, height: int) -> np.ndarray:
    points = zone.points or ((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0))
    return np.asarray(
        [[round(max(0.0, min(1.0, x)) * (width - 1)), round(max(0.0, min(1.0, y)) * (height - 1))] for x, y in points],
        dtype=np.int32,
    )


def _zone_area_pixels(zone: TrackedZone, width: int, height: int) -> float:
    return abs(float(cv2.contourArea(_zone_polygon(zone, width, height))))


def _region_zone(
    zones: tuple[TrackedZone, ...], x: int, y: int, width: int, height: int, frame_width: int, frame_height: int
) -> TrackedZone | None:
    center = ((x + width / 2) / frame_width, (y + height / 2) / frame_height)
    for zone in zones:
        polygon = np.asarray(zone.points, dtype=np.float32)
        if len(polygon) >= 3 and cv2.pointPolygonTest(polygon, center, False) >= 0:
            return zone
    return None


def _merge_nearby_regions(regions: list[MotionRegion]) -> list[MotionRegion]:
    merged: list[MotionRegion] = []
    pending = list(regions)
    while pending:
        current = pending.pop(0)
        nearby = [current]
        rest: list[MotionRegion] = []
        for candidate in pending:
            if candidate.zone_id == current.zone_id and _boxes_near(current, candidate):
                nearby.append(candidate)
            else:
                rest.append(candidate)
        pending = rest
        if len(nearby) == 1:
            merged.append(current)
            continue
        area = sum(item.pixel_area for item in nearby)
        merged.append(
            MotionRegion(
                left=min(item.left for item in nearby),
                top=min(item.top for item in nearby),
                right=max(item.right for item in nearby),
                bottom=max(item.bottom for item in nearby),
                centroid_x=sum(item.centroid_x * item.pixel_area for item in nearby) / area,
                centroid_y=sum(item.centroid_y * item.pixel_area for item in nearby) / area,
                pixel_area=area,
                zone_relative_area=sum(item.zone_relative_area for item in nearby),
                mask_occupancy=max(item.mask_occupancy for item in nearby),
                zone_id=current.zone_id,
                frame_identity=current.frame_identity,
                captured_at=current.captured_at,
            )
        )
    return merged


def _boxes_near(left: MotionRegion, right: MotionRegion) -> bool:
    horizontal_gap = max(left.left - right.right, right.left - left.right, 0.0)
    vertical_gap = max(left.top - right.bottom, right.top - left.bottom, 0.0)
    return horizontal_gap <= 0.02 and vertical_gap <= 0.02


def _best_track_match(
    track: _Track,
    regions: tuple[MotionRegion, ...],
    unmatched: set[int],
) -> int | None:
    candidates: list[tuple[float, int]] = []
    for index in unmatched:
        region = regions[index]
        if region.zone_id not in track.zone_ids:
            continue
        overlap = _iou(track.region, region)
        distance = hypot(
            track.region.centroid_x - region.centroid_x,
            track.region.centroid_y - region.centroid_y,
        )
        if overlap < 0.08 and distance > 0.09:
            continue
        candidates.append((overlap - distance, index))
    return max(candidates, default=(0.0, None))[1]


def _iou(left: MotionRegion, right: MotionRegion) -> float:
    intersection_left = max(left.left, right.left)
    intersection_top = max(left.top, right.top)
    intersection_right = min(left.right, right.right)
    intersection_bottom = min(left.bottom, right.bottom)
    intersection = max(0.0, intersection_right - intersection_left) * max(0.0, intersection_bottom - intersection_top)
    union = (
        (left.right - left.left) * (left.bottom - left.top)
        + (right.right - right.left) * (right.bottom - right.top)
        - intersection
    )
    return intersection / union if union > 0 else 0.0
