"""Provider-neutral deterministic tracking for ordered analysis frames.

The tracker owns only bounded transient geometry and temporal-support facts.  It
has no model, camera, repository, media, or product-write dependency.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from hashlib import sha256
from math import hypot
from typing import Literal, NamedTuple, Protocol

from mockingbird.observation.contracts import DetectionObservation, FramePacket, TrackUpdate


TRACKER_VERSION = "spatial-frame-tracker-v1"


@dataclass(frozen=True)
class TrackerConfiguration:
    strong_detection_threshold: float
    minimum_detector_confirmations: int
    minimum_tracker_support_frames: int
    maximum_missed_frames: int
    maximum_frame_gap_ms: int
    tracker_expiry_ms: int
    maximum_track_duration_ms: int
    maximum_active_tracks: int
    minimum_iou: float = 0.05
    maximum_centroid_distance: float = 0.22
    ambiguity_margin: float = 0.01
    maximum_unsupported_detector_ms: int = 5000
    negative_detector_frames_to_end: int = 2
    ambiguous_reentry_window_ms: int = 1500

    def __post_init__(self) -> None:
        if not 0.0 <= self.strong_detection_threshold <= 1.0:
            raise ValueError("invalid_strong_detection_threshold")
        if self.minimum_detector_confirmations < 1 or self.minimum_tracker_support_frames < 1:
            raise ValueError("invalid_confirmation_policy")
        if min(
            self.maximum_missed_frames,
            self.maximum_frame_gap_ms,
            self.tracker_expiry_ms,
            self.maximum_track_duration_ms,
            self.maximum_active_tracks,
            self.maximum_unsupported_detector_ms,
            self.negative_detector_frames_to_end,
            self.ambiguous_reentry_window_ms,
        ) < 1:
            raise ValueError("invalid_tracker_bound")


@dataclass(frozen=True)
class TrackView:
    track_id: str
    generation_id: str
    lifecycle_state: Literal["tentative", "confirmed", "temporarily_lost"]
    broad_class: str
    bounding_box: tuple[float, float, float, float]
    first_offset_ms: int
    last_offset_ms: int
    detector_confirmation_count: int
    tracker_support_count: int
    confidence: float | None
    supporting_frame_ids: tuple[str, ...]


class TrackerSupportResolver(Protocol):
    def __call__(
        self,
        frame: FramePacket,
        track: TrackView,
    ) -> tuple[float, float, float, float] | None: ...


@dataclass(frozen=True)
class TerminalTrack:
    view: TrackView
    terminal_reason: str
    confirmed: bool


class _RecentEnding(NamedTuple):
    """A small bounded record of one just-ended generation, kept only to detect
    and honestly report an ambiguous reentry.  It never revives a generation."""

    generation_id: str
    broad_class: str
    bounding_box: tuple[float, float, float, float]
    ended_offset_ms: int
    confident_split: bool


@dataclass(frozen=True)
class TrackerStep:
    updates: tuple[TrackUpdate, ...] = ()
    terminals: tuple[TerminalTrack, ...] = ()
    ambiguous_associations: int = 0
    ambiguous_reentries: int = 0


@dataclass
class _Track:
    track_id: str
    generation_id: str
    broad_class: str
    bounding_box: tuple[float, float, float, float]
    first_captured_at: datetime
    last_captured_at: datetime
    first_offset_ms: int
    last_offset_ms: int
    detector_confirmation_count: int
    tracker_support_count: int
    confidence: float | None
    detector_provenance: str | None
    last_detector_offset_ms: int
    lifecycle_state: Literal["tentative", "confirmed", "temporarily_lost"] = "tentative"
    confirmed: bool = False
    missed_frames: int = 0
    consecutive_negative_detector_frames: int = 0
    velocity: tuple[float, float] = (0.0, 0.0)
    supporting_frame_ids: list[str] = field(default_factory=list)
    seen_frame_ids: set[str] = field(default_factory=set)

    def view(self) -> TrackView:
        return TrackView(
            self.track_id,
            self.generation_id,
            self.lifecycle_state,
            self.broad_class,
            self.bounding_box,
            self.first_offset_ms,
            self.last_offset_ms,
            self.detector_confirmation_count,
            self.tracker_support_count,
            self.confidence,
            tuple(self.supporting_frame_ids),
        )


class ProviderNeutralFrameTracker:
    """A deterministic one-to-one spatial tracker behind provider-neutral facts."""

    def __init__(
        self,
        stream_id: str,
        configuration: TrackerConfiguration,
        *,
        support_resolver: TrackerSupportResolver | None = None,
    ) -> None:
        self.stream_id = stream_id
        self.configuration = configuration
        self._support_resolver = support_resolver or (lambda _frame, _track: None)
        self._tracks: dict[str, _Track] = {}
        self._next_track = 1
        self._seen_frames: set[str] = set()
        self._last_frame_offset_ms: int | None = None
        self._recent_endings: deque[_RecentEnding] = deque(maxlen=8)

    @property
    def active_count(self) -> int:
        return len(self._tracks)

    def reset(self) -> TrackerStep:
        step = self.finalize("provider_reset")
        self._tracks.clear()
        self._seen_frames.clear()
        self._last_frame_offset_ms = None
        self._recent_endings.clear()
        return step

    def observe(
        self,
        frame: FramePacket,
        detections: tuple[DetectionObservation, ...],
        *,
        detector_ran: bool = False,
    ) -> TrackerStep:
        """Advance the episode boundary by one analysis frame.

        ``detector_ran`` distinguishes an explicit animal-negative detector pass
        (the detector executed and found nothing usable for a track) from an
        idle-cadence frame the detector never inspected.  Only the former counts
        toward ``negative_detector_frames_to_end``; tracker-support alone (for
        example a bounded local patch match) can bridge a brief loss but can
        never by itself keep an episode "genuinely supported" indefinitely --
        ``maximum_unsupported_detector_ms`` bounds that regardless of cadence.
        """
        frame_id = frame.frame_id
        offset = frame.source_offset_ms
        captured_at = frame.captured_at
        if frame_id is None or offset is None or captured_at is None:
            raise ValueError("frame_tracking_metadata_required")
        if frame_id in self._seen_frames:
            return TrackerStep()
        if self._last_frame_offset_ms is not None and offset <= self._last_frame_offset_ms:
            raise ValueError("non_monotonic_tracking_frame")
        self._seen_frames.add(frame_id)
        self._last_frame_offset_ms = offset

        updates: list[TrackUpdate] = []
        terminals: list[TerminalTrack] = []
        for track in tuple(self._tracks.values()):
            if offset - track.first_offset_ms >= self.configuration.maximum_track_duration_ms:
                terminals.append(self._terminate(track, "maximum_duration", captured_at, frame))
            elif track.consecutive_negative_detector_frames >= self.configuration.negative_detector_frames_to_end:
                terminals.append(self._terminate(track, "negative_interval_reentry", captured_at, frame))
            elif offset - track.last_detector_offset_ms > self.configuration.maximum_unsupported_detector_ms:
                terminals.append(self._terminate(track, "maximum_unsupported_duration", captured_at, frame))
            elif offset - track.last_offset_ms > self.configuration.maximum_frame_gap_ms:
                terminals.append(self._terminate(track, "tracker_lost", captured_at, frame))

        animals = tuple(
            item
            for item in detections
            if item.is_animal is True and item.bounding_box is not None and item.frame_id == frame_id
        )
        assignments, ambiguous = self._assign(animals)
        matched_tracks = {track_id for track_id, _ in assignments}
        matched_detections = {index for _, index in assignments}

        for track_id, index in assignments:
            track = self._tracks[track_id]
            detection = animals[index]
            self._observe_detection(track, detection, frame)
            updates.append(self._update(track, captured_at, frame, "updated"))

        for track in tuple(self._tracks.values()):
            if track.track_id in matched_tracks:
                continue
            supported_box = self._support_resolver(frame, track.view())
            if supported_box is not None and _valid_box(supported_box):
                track.consecutive_negative_detector_frames = 0
                self._observe_tracker_support(track, supported_box, frame)
                updates.append(self._update(track, captured_at, frame, "updated"))
                continue
            if detector_ran:
                track.consecutive_negative_detector_frames += 1
            track.missed_frames += 1
            track.lifecycle_state = "temporarily_lost"
            if (
                track.missed_frames > self.configuration.maximum_missed_frames
                or offset - track.last_offset_ms > self.configuration.tracker_expiry_ms
            ):
                terminals.append(self._terminate(track, "tracker_lost", captured_at, frame))
            else:
                updates.append(self._update(track, captured_at, frame, "updated"))

        ambiguous_reentries = 0
        for index, detection in enumerate(animals):
            if index in matched_detections:
                continue
            if len(self._tracks) >= self.configuration.maximum_active_tracks:
                continue
            track, reentry_ambiguous = self._start(detection, frame)
            if reentry_ambiguous:
                ambiguous_reentries += 1
            updates.append(self._update(track, captured_at, frame, "started"))

        updates.extend(
            self._terminal_update(item, captured_at, frame) for item in terminals
        )
        return TrackerStep(tuple(updates), tuple(terminals), ambiguous, ambiguous_reentries)

    def finalize(self, reason: str = "end_of_replay") -> TrackerStep:
        updates: list[TrackUpdate] = []
        terminals: list[TerminalTrack] = []
        for track in sorted(self._tracks.values(), key=lambda item: item.generation_id):
            terminal_reason = reason
            captured_at = track.last_captured_at
            frame = FramePacket(
                self.stream_id,
                "",
                captured_at,
                track.supporting_frame_ids[-1] if track.supporting_frame_ids else None,
                track.last_offset_ms,
            )
            terminal = self._terminate(track, terminal_reason, captured_at, frame)
            terminals.append(terminal)
            updates.append(self._terminal_update(terminal, captured_at, frame))
        return TrackerStep(tuple(updates), tuple(terminals))

    def _start(self, detection: DetectionObservation, frame: FramePacket) -> tuple[_Track, bool]:
        assert detection.bounding_box is not None and frame.source_offset_ms is not None and frame.captured_at is not None
        counter = self._next_track
        self._next_track += 1
        seed = (
            f"{self.stream_id}|{frame.frame_id}|{frame.source_offset_ms}|"
            f"{detection.label}|{detection.bounding_box}|{counter}"
        )
        generation = f"{self.stream_id}:frame-track:{sha256(seed.encode()).hexdigest()[:20]}"
        ambiguous = self._is_ambiguous_reentry(detection, frame)
        track = _Track(
            f"frame-track-{counter:04d}",
            generation,
            detection.label,
            detection.bounding_box,
            frame.captured_at,
            frame.captured_at,
            frame.source_offset_ms,
            frame.source_offset_ms,
            1,
            0,
            detection.confidence,
            detection.detector_id,
            frame.source_offset_ms,
            supporting_frame_ids=[frame.frame_id or ""],
            seen_frame_ids={frame.frame_id or ""},
        )
        self._tracks[track.track_id] = track
        return track, ambiguous

    def _is_ambiguous_reentry(self, detection: DetectionObservation, frame: FramePacket) -> bool:
        """Report -- never revive -- a start that could plausibly be the same
        subject as a recently, but not confidently, ended generation."""
        assert detection.bounding_box is not None and frame.source_offset_ms is not None
        for ending in self._recent_endings:
            if ending.confident_split or ending.broad_class != detection.label:
                continue
            if frame.source_offset_ms - ending.ended_offset_ms > self.configuration.ambiguous_reentry_window_ms:
                continue
            distance = hypot(*(
                left - right for left, right in zip(_center(ending.bounding_box), _center(detection.bounding_box))
            ))
            if (
                _iou(ending.bounding_box, detection.bounding_box) >= self.configuration.minimum_iou
                or distance <= self.configuration.maximum_centroid_distance
            ):
                return True
        return False

    def _observe_detection(
        self,
        track: _Track,
        detection: DetectionObservation,
        frame: FramePacket,
    ) -> None:
        assert detection.bounding_box is not None and frame.source_offset_ms is not None and frame.captured_at is not None
        old_center = _center(track.bounding_box)
        new_center = _center(detection.bounding_box)
        track.velocity = (new_center[0] - old_center[0], new_center[1] - old_center[1])
        track.bounding_box = detection.bounding_box
        track.last_captured_at = frame.captured_at
        track.last_offset_ms = frame.source_offset_ms
        track.last_detector_offset_ms = frame.source_offset_ms
        track.missed_frames = 0
        track.consecutive_negative_detector_frames = 0
        track.detector_confirmation_count += 1
        track.confidence = max(track.confidence or 0.0, detection.confidence or 0.0)
        self._remember(track, frame.frame_id or "")
        self._confirm(track)

    def _observe_tracker_support(
        self,
        track: _Track,
        box: tuple[float, float, float, float],
        frame: FramePacket,
    ) -> None:
        assert frame.source_offset_ms is not None and frame.captured_at is not None
        old_center = _center(track.bounding_box)
        new_center = _center(box)
        track.velocity = (new_center[0] - old_center[0], new_center[1] - old_center[1])
        track.bounding_box = box
        track.last_captured_at = frame.captured_at
        track.last_offset_ms = frame.source_offset_ms
        track.missed_frames = 0
        track.tracker_support_count += 1
        self._remember(track, frame.frame_id or "")
        self._confirm(track)

    def _remember(self, track: _Track, frame_id: str) -> None:
        if frame_id and frame_id not in track.seen_frame_ids:
            track.seen_frame_ids.add(frame_id)
            track.supporting_frame_ids.append(frame_id)

    def _confirm(self, track: _Track) -> None:
        strong = (track.confidence or 0.0) >= self.configuration.strong_detection_threshold
        if (
            track.detector_confirmation_count >= self.configuration.minimum_detector_confirmations
            or (
                strong
                and track.tracker_support_count >= self.configuration.minimum_tracker_support_frames
            )
        ):
            track.confirmed = True
            track.lifecycle_state = "confirmed"
        elif track.lifecycle_state == "temporarily_lost":
            track.lifecycle_state = "confirmed" if track.confirmed else "tentative"

    def _assign(
        self,
        detections: tuple[DetectionObservation, ...],
    ) -> tuple[list[tuple[str, int]], int]:
        candidates: list[tuple[float, str, int]] = []
        by_detection: dict[int, list[tuple[float, str]]] = {}
        for track in self._tracks.values():
            predicted = _shift(track.bounding_box, track.velocity)
            for index, detection in enumerate(detections):
                if detection.label != track.broad_class or detection.bounding_box is None:
                    continue
                overlap = _iou(predicted, detection.bounding_box)
                distance = hypot(*(
                    left - right for left, right in zip(_center(predicted), _center(detection.bounding_box))
                ))
                if overlap < self.configuration.minimum_iou and distance > self.configuration.maximum_centroid_distance:
                    continue
                score = overlap - distance
                candidates.append((-score, track.track_id, index))
                by_detection.setdefault(index, []).append((score, track.track_id))
        ambiguous_indices = {
            index
            for index, values in by_detection.items()
            if len(values) > 1
            and sorted(values, reverse=True)[0][0] - sorted(values, reverse=True)[1][0]
            <= self.configuration.ambiguity_margin
        }
        assigned_tracks: set[str] = set()
        assigned_detections: set[int] = set()
        assignments: list[tuple[str, int]] = []
        for _negative_score, track_id, index in sorted(candidates):
            if index in ambiguous_indices or track_id in assigned_tracks or index in assigned_detections:
                continue
            assigned_tracks.add(track_id)
            assigned_detections.add(index)
            assignments.append((track_id, index))
        return assignments, len(ambiguous_indices)

    def _terminate(
        self,
        track: _Track,
        reason: str,
        captured_at: datetime,
        frame: FramePacket,
    ) -> TerminalTrack:
        self._tracks.pop(track.track_id, None)
        confirmed = track.confirmed
        uncertain_reasons = {
            "tracker_lost", "end_of_replay", "maximum_unsupported_duration", "negative_interval_reentry",
        }
        terminal_reason = reason if confirmed or reason not in uncertain_reasons else "insufficient_support"
        confident_split = reason in {"maximum_unsupported_duration", "negative_interval_reentry"}
        self._recent_endings.append(_RecentEnding(
            track.generation_id, track.broad_class, track.bounding_box, track.last_offset_ms, confident_split,
        ))
        return TerminalTrack(track.view(), terminal_reason, confirmed)

    def _update(
        self,
        track: _Track,
        captured_at: datetime,
        frame: FramePacket,
        status: Literal["started", "updated"],
    ) -> TrackUpdate:
        return TrackUpdate(
            track.track_id,
            track.generation_id,
            captured_at,
            status,
            track.lifecycle_state,
            frame.frame_id,
            frame.source_offset_ms,
            track.broad_class,
            track.bounding_box,
            tuple(track.supporting_frame_ids),
            track.detector_confirmation_count,
            track.tracker_support_count,
            track.confidence,
            track.detector_provenance,
            TRACKER_VERSION,
        )

    def _terminal_update(
        self,
        terminal: TerminalTrack,
        captured_at: datetime,
        frame: FramePacket,
    ) -> TrackUpdate:
        view = terminal.view
        return TrackUpdate(
            view.track_id,
            view.generation_id,
            captured_at,
            "ended",
            "ended" if terminal.confirmed else "rejected",
            frame.frame_id,
            frame.source_offset_ms,
            view.broad_class,
            view.bounding_box,
            view.supporting_frame_ids,
            view.detector_confirmation_count,
            view.tracker_support_count,
            view.confidence,
            None,
            TRACKER_VERSION,
            terminal.terminal_reason,
        )


def _center(box: tuple[float, float, float, float]) -> tuple[float, float]:
    return ((box[0] + box[2]) / 2.0, (box[1] + box[3]) / 2.0)


def _shift(
    box: tuple[float, float, float, float],
    velocity: tuple[float, float],
) -> tuple[float, float, float, float]:
    return tuple(
        max(0.0, min(1.0, value + velocity[index % 2]))
        for index, value in enumerate(box)
    )


def _valid_box(box: tuple[float, float, float, float]) -> bool:
    return (
        len(box) == 4
        and all(0.0 <= value <= 1.0 for value in box)
        and box[0] < box[2]
        and box[1] < box[3]
    )


def _iou(
    left: tuple[float, float, float, float],
    right: tuple[float, float, float, float],
) -> float:
    x0, y0 = max(left[0], right[0]), max(left[1], right[1])
    x1, y1 = min(left[2], right[2]), min(left[3], right[3])
    intersection = max(0.0, x1 - x0) * max(0.0, y1 - y0)
    left_area = (left[2] - left[0]) * (left[3] - left[1])
    right_area = (right[2] - right[0]) * (right[3] - right[1])
    union = left_area + right_area - intersection
    return intersection / union if union > 0 else 0.0
