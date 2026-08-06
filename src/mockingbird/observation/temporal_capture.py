"""Provider-neutral bounded temporal-capture contract and trigger logic.

Observation Engine v2 Stage 6.6. This module is pure: no CUDA, ONNX Runtime,
OpenCV, camera-provider, or filesystem type anywhere in its contract. It
decides *which already-processed frames to retain* and assembles the
versioned capture-session manifest; it never opens a network connection,
decodes an image, or writes a file (see `temporal_capture_io.py`/
`temporal_capture_cli.py`). Retention decisions consume only already-emitted
provider-neutral facts (`DetectionObservation`, `TrackUpdate`,
`EvidenceCandidate`) exactly the way `multi_scale_strategy`/
`motion_proposal_strategy` consume already-decoded detections -- this module
adds no new pixel-level or network-level behavior of its own.

See docs/temporal-review-capture-contract.md.
"""
from __future__ import annotations

from dataclasses import dataclass

from mockingbird.observation.contracts import DetectionObservation, TrackUpdate
from mockingbird.observation.replay import semantic_fingerprint

CAPTURE_MANIFEST_SCHEMA_VERSION = 1
CAPTURE_MANIFEST_VERSION = "temporal-capture-session-v1"

# --------------------------------------------------------------------------
# Stable trigger and stop-condition reason codes
# --------------------------------------------------------------------------

TRIGGER_ANIMAL_ABOVE_OPERATING_POINT = "animal_above_operating_point"
TRIGGER_ANIMAL_BELOW_OPERATING_POINT_ABOVE_REVIEW_FLOOR = "animal_below_operating_point_above_review_floor"
TRIGGER_SHADOW_TRACK_EVENT = "shadow_track_event"
TRIGGER_MOTION_PROPOSAL_GENERATED = "motion_proposal_generated"
TRIGGER_HIGH_RESOLUTION_BURST = "high_resolution_burst"
TRIGGER_OPERATOR_MARKER = "operator_marker"
TRIGGER_PERIODIC_NEGATIVE_SAMPLE = "periodic_negative_sample"
TRIGGER_RECURRING_STATIC_GEOMETRY = "recurring_static_geometry"
TRIGGER_PRIVACY_IGNORE_INTERACTION = "privacy_ignore_interaction"
TRIGGER_GENERATION_OR_SEQUENCE_DISCONTINUITY = "generation_or_sequence_discontinuity"
TRIGGER_PRETRIGGER_CONTEXT = "pretrigger_context"
TRIGGER_POST_TRIGGER_CONTEXT = "post_trigger_context"

TRIGGER_REASONS: tuple[str, ...] = (
    TRIGGER_ANIMAL_ABOVE_OPERATING_POINT,
    TRIGGER_ANIMAL_BELOW_OPERATING_POINT_ABOVE_REVIEW_FLOOR,
    TRIGGER_SHADOW_TRACK_EVENT,
    TRIGGER_MOTION_PROPOSAL_GENERATED,
    TRIGGER_HIGH_RESOLUTION_BURST,
    TRIGGER_OPERATOR_MARKER,
    TRIGGER_PERIODIC_NEGATIVE_SAMPLE,
    TRIGGER_RECURRING_STATIC_GEOMETRY,
    TRIGGER_PRIVACY_IGNORE_INTERACTION,
    TRIGGER_GENERATION_OR_SEQUENCE_DISCONTINUITY,
    TRIGGER_PRETRIGGER_CONTEXT,
    TRIGGER_POST_TRIGGER_CONTEXT,
)

STOP_DURATION_ELAPSED = "duration_elapsed"
STOP_FRAME_LIMIT = "analysis_frame_limit"
STOP_BYTE_LIMIT = "byte_limit"
STOP_HIGH_RESOLUTION_LIMIT = "high_resolution_frame_limit"
STOP_MARKER_LIMIT = "operator_marker_limit"
STOP_OUTPUT_FILE_LIMIT = "output_file_limit"
STOP_ACTIVE_TRACK_LIMIT = "active_track_limit"
STOP_STREAM_ENDED = "stream_ended"
STOP_MANUAL = "manual_stop"
STOP_TRANSPORT_ERROR = "transport_error"

STOP_CONDITIONS: tuple[str, ...] = (
    STOP_DURATION_ELAPSED, STOP_FRAME_LIMIT, STOP_BYTE_LIMIT, STOP_HIGH_RESOLUTION_LIMIT,
    STOP_MARKER_LIMIT, STOP_OUTPUT_FILE_LIMIT, STOP_ACTIVE_TRACK_LIMIT, STOP_STREAM_ENDED,
    STOP_MANUAL, STOP_TRANSPORT_ERROR,
)

OPERATOR_MARKER_WILDLIFE_VISIBLE_NOW = "wildlife_visible_now"
OPERATOR_MARKER_WILDLIFE_RECENT = "wildlife_was_visible_recently"
OPERATOR_MARKER_UNCERTAIN_POSSIBLE = "uncertain_possible_wildlife"
OPERATOR_MARKER_KNOWN_EMPTY = "known_empty_scene"
OPERATOR_MARKER_ENVIRONMENTAL_CHANGE = "noteworthy_environmental_change"

OPERATOR_MARKER_KINDS: tuple[str, ...] = (
    OPERATOR_MARKER_WILDLIFE_VISIBLE_NOW,
    OPERATOR_MARKER_WILDLIFE_RECENT,
    OPERATOR_MARKER_UNCERTAIN_POSSIBLE,
    OPERATOR_MARKER_KNOWN_EMPTY,
    OPERATOR_MARKER_ENVIRONMENTAL_CHANGE,
)


class TemporalCaptureError(ValueError):
    """A bounded temporal-capture validation or execution failure code."""


# --------------------------------------------------------------------------
# Bounded resource contract
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class CaptureBounds:
    """Hard ceilings the runner must enforce; every field maps to one bullet
    of the Stage 6.6 "Bounded capture behavior" contract. Reaching any bound
    stops capture cleanly with a matching `STOP_*` reason -- it never grows
    a buffer past its ceiling."""

    max_duration_seconds: int = 600
    max_analysis_frames: int = 3_000
    max_bytes_stored: int = 500_000_000
    max_high_resolution_frames: int = 32
    max_detector_observations_per_frame: int = 50
    max_active_tracks: int = 24
    max_operator_markers: int = 64
    pretrigger_frame_count: int = 3
    post_trigger_frame_count: int = 3
    periodic_negative_interval_seconds: int = 30
    max_periodic_negative_samples: int = 40
    # Bounds the retroactive operator-marker rescue buffer: how many
    # recently-processed-but-not-yet-retained frames the runner keeps
    # available for a marker written *after* those frames already passed
    # through, since a marker only ever correlates backward in time (see
    # `markers_near`) and is discovered only at the next batch boundary.
    # 0 disables rescue outright (only frames processed after a marker is
    # already known can ever match it).
    adjacent_context_frame_count: int = 16
    max_pending_burst_requests: int = 4
    max_output_files: int = 6_000

    def __post_init__(self) -> None:
        bounds = (
            (self.max_duration_seconds, 1, 3600),
            (self.max_analysis_frames, 1, 20_000),
            (self.max_bytes_stored, 1_000_000, 5_000_000_000),
            (self.max_high_resolution_frames, 0, 500),
            (self.max_detector_observations_per_frame, 1, 500),
            (self.max_active_tracks, 1, 64),
            (self.max_operator_markers, 1, 500),
            (self.pretrigger_frame_count, 0, 16),
            (self.post_trigger_frame_count, 0, 16),
            (self.periodic_negative_interval_seconds, 1, 3600),
            (self.max_periodic_negative_samples, 0, 500),
            (self.adjacent_context_frame_count, 0, 16),
            (self.max_pending_burst_requests, 1, 16),
            (self.max_output_files, 1, 50_000),
        )
        if any(not (lo <= value <= hi) for value, lo, hi in bounds):
            raise TemporalCaptureError("invalid_capture_bounds")


@dataclass(frozen=True)
class CaptureSessionConfig:
    """The explicit, provider-neutral capture-session contract. No absolute
    path, hostname, credential, or bearer token belongs on this type or any
    value it carries into the manifest -- those stay in the caller's own
    connection configuration (see `temporal_capture_io.CameraNodeConnectionConfig`)."""

    schema_version: int
    capture_version: str
    stream_id: str
    transport_key: str
    provider_key: str
    analysis_width: int
    analysis_height: int
    nominal_fps: float
    review_score_threshold: float
    shadow_operating_point: float
    review_floor: float
    evidence_profile_id: str
    bounds: CaptureBounds
    privacy_ignore_regions: tuple[tuple[float, float, float, float], ...] = ()
    limitations: tuple[str, ...] = (
        "engineering acquisition tool only; creates no product record or reviewed truth",
        "analysis/host clock alignment is uncertain unless externally synchronized",
        "retained frames are review candidates, not automatic truth of any kind",
        "a Visit-level false_positive label from the product database, if ever attached as "
        "context, must never be treated as whole-frame negative truth by downstream review",
    )

    def __post_init__(self) -> None:
        if self.schema_version != CAPTURE_MANIFEST_SCHEMA_VERSION:
            raise TemporalCaptureError("unsupported_capture_schema_version")
        if not self.stream_id or not self.transport_key or not self.provider_key or not self.evidence_profile_id:
            raise TemporalCaptureError("invalid_capture_session_identity")
        if self.analysis_width < 1 or self.analysis_height < 1 or self.nominal_fps <= 0:
            raise TemporalCaptureError("invalid_capture_dimensions")
        if not 0.0 < self.review_score_threshold <= 1.0:
            raise TemporalCaptureError("invalid_review_score_threshold")
        if not 0.0 < self.review_floor <= self.shadow_operating_point <= 1.0:
            raise TemporalCaptureError("invalid_operating_point_bounds")
        if self.review_score_threshold > self.review_floor:
            raise TemporalCaptureError("review_threshold_above_review_floor")


# --------------------------------------------------------------------------
# Operator markers
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class OperatorMarker:
    """One engineering-only, unreviewed operator observation. Never a
    species claim, ReviewLabel, or Observation -- correlation to nearby
    frames is advisory context for the human reviewer, not detector truth."""

    marker_id: str
    kind: str
    host_time_iso: str
    note: str = ""
    lookback_seconds: int = 20

    def __post_init__(self) -> None:
        if not self.marker_id or self.kind not in OPERATOR_MARKER_KINDS:
            raise TemporalCaptureError("invalid_operator_marker")
        if not 0 <= self.lookback_seconds <= 300:
            raise TemporalCaptureError("invalid_operator_marker_lookback")
        if len(self.note) > 500:
            raise TemporalCaptureError("invalid_operator_marker_note")


def markers_near(
    markers: tuple[OperatorMarker, ...], *, host_time_iso: str, default_lookback_seconds: int,
) -> tuple[OperatorMarker, ...]:
    """Bounded lookback correlation: a marker is "near" a frame when the
    frame's own host time falls within [marker_time, marker_time +
    marker.lookback_seconds] -- markers are logged after the fact ("wildlife
    was visible"), so lookback always looks backward from the marker to
    earlier frames, never forward past it."""

    from datetime import datetime

    try:
        frame_time = datetime.fromisoformat(host_time_iso)
    except ValueError:
        return ()
    near: list[OperatorMarker] = []
    for marker in markers:
        try:
            marker_time = datetime.fromisoformat(marker.host_time_iso)
        except ValueError:
            continue
        lookback = marker.lookback_seconds or default_lookback_seconds
        if marker_time - _seconds(lookback) <= frame_time <= marker_time:
            near.append(marker)
    return tuple(near)


def _seconds(value: int):
    from datetime import timedelta
    return timedelta(seconds=value)


# --------------------------------------------------------------------------
# Recurring static geometry (live, bounded clustering)
# --------------------------------------------------------------------------

_CLUSTER_IOU_THRESHOLD = 0.3
_CLUSTER_CENTROID_THRESHOLD = 0.05
_CLUSTER_MIN_RECURRENCE = 2
_MAX_TRACKED_CLUSTERS = 64


def _iou(first: tuple[float, float, float, float], second: tuple[float, float, float, float]) -> float:
    left, top = max(first[0], second[0]), max(first[1], second[1])
    right, bottom = min(first[2], second[2]), min(first[3], second[3])
    intersection = max(0.0, right - left) * max(0.0, bottom - top)
    first_area = (first[2] - first[0]) * (first[3] - first[1])
    second_area = (second[2] - second[0]) * (second[3] - second[1])
    union = first_area + second_area - intersection
    return 0.0 if union <= 0.0 else intersection / union


def _centroid(box: tuple[float, float, float, float]) -> tuple[float, float]:
    return ((box[0] + box[2]) / 2.0, (box[1] + box[3]) / 2.0)


def _centroid_distance(first: tuple[float, float, float, float], second: tuple[float, float, float, float]) -> float:
    fx, fy = _centroid(first)
    sx, sy = _centroid(second)
    return ((fx - sx) ** 2 + (fy - sy) ** 2) ** 0.5


class RecurringGeometryTracker:
    """Bounded, deterministic, in-session clustering of untracked detection
    boxes -- the same IoU/centroid grouping rule
    `detector_benchmark.cluster_static_false_positives` already applies
    after the fact, applied live so a recurring shape can be flagged as a
    capture trigger while the session is still running. Never creates or
    implies an Ignore region."""

    def __init__(self, *, iou_threshold: float = _CLUSTER_IOU_THRESHOLD, centroid_threshold: float = _CLUSTER_CENTROID_THRESHOLD) -> None:
        self._iou_threshold = iou_threshold
        self._centroid_threshold = centroid_threshold
        self._clusters: list[dict[str, object]] = []

    def observe(self, box: tuple[float, float, float, float]) -> bool:
        """Record one untracked detection box; return True once its cluster
        has recurred `_CLUSTER_MIN_RECURRENCE` or more times."""

        for cluster in self._clusters:
            representative = cluster["representative_box"]
            if (
                _iou(box, representative) >= self._iou_threshold  # type: ignore[arg-type]
                and _centroid_distance(box, representative) <= self._centroid_threshold  # type: ignore[arg-type]
            ):
                cluster["count"] = int(cluster["count"]) + 1  # type: ignore[arg-type]
                return int(cluster["count"]) >= _CLUSTER_MIN_RECURRENCE  # type: ignore[arg-type]
        if len(self._clusters) < _MAX_TRACKED_CLUSTERS:
            self._clusters.append({"representative_box": box, "count": 1})
        return False


class PeriodicNegativeScheduler:
    """Bounded periodic sampling: fires at most once per
    `interval_seconds` of source-relative time, up to `max_samples` total."""

    def __init__(self, *, interval_seconds: int, max_samples: int) -> None:
        if interval_seconds < 1 or max_samples < 0:
            raise TemporalCaptureError("invalid_periodic_negative_schedule")
        self._interval_ms = interval_seconds * 1000
        self._max_samples = max_samples
        self._last_offset_ms: int | None = None
        self._emitted = 0

    def due(self, source_offset_ms: int) -> bool:
        if self._emitted >= self._max_samples:
            return False
        if self._last_offset_ms is not None and source_offset_ms - self._last_offset_ms < self._interval_ms:
            return False
        self._last_offset_ms = source_offset_ms
        self._emitted += 1
        return True


# --------------------------------------------------------------------------
# Per-frame trigger classification
# --------------------------------------------------------------------------


def classify_detection_triggers(
    detections: tuple[DetectionObservation, ...], *, operating_point: float, review_floor: float,
) -> tuple[str, ...]:
    triggers: list[str] = []
    animal_scores = [item.confidence or 0.0 for item in detections if item.is_animal]
    if any(score >= operating_point for score in animal_scores):
        triggers.append(TRIGGER_ANIMAL_ABOVE_OPERATING_POINT)
    if any(review_floor <= score < operating_point for score in animal_scores):
        triggers.append(TRIGGER_ANIMAL_BELOW_OPERATING_POINT_ABOVE_REVIEW_FLOOR)
    return tuple(triggers)


def has_track_event(track_updates: tuple[TrackUpdate, ...]) -> bool:
    return bool(track_updates)


# --------------------------------------------------------------------------
# Retained-frame record and manifest assembly
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class RetainedFrameRecord:
    """One retained analysis frame's manifest entry. Deliberately carries no
    absolute path -- the caller stores the JPEG under a stable relative name
    derived from `frame_id` (see `temporal_capture_io`)."""

    frame_id: str
    sequence: int
    source_offset_ms: int
    provider_generation: str
    content_hash: str
    byte_size: int
    trigger_reasons: tuple[str, ...]
    detector_observation_count: int
    animal_detection_count: int
    max_animal_score: float | None
    active_track_count: int
    motion_proposal_count: int
    high_resolution: bool = False
    privacy_ignore_interaction: bool = False
    operator_marker_ids: tuple[str, ...] = ()
    # Raw animal-class detector observations at the low review-capture
    # threshold, retained so the review packet can draw real detector-box
    # crops and so active-learning classification can IoU-match against
    # reviewed truth instead of guessing from counts alone. (left, top,
    # right, bottom, score) in source-normalized space.
    detection_boxes: tuple[tuple[float, float, float, float, float], ...] = ()
    # Motion/adaptive-proposal window boxes accepted for this frame (source-
    # normalized), for the same reason.
    motion_proposal_boxes: tuple[tuple[float, float, float, float], ...] = ()
    # Track generation ids with any support on this frame, for tracker-
    # failure/episode-boundary active-learning classification.
    track_generation_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.frame_id or self.sequence < 0 or self.source_offset_ms < 0:
            raise TemporalCaptureError("invalid_retained_frame")
        if not self.trigger_reasons or any(reason not in TRIGGER_REASONS for reason in self.trigger_reasons):
            raise TemporalCaptureError("invalid_retained_frame_trigger")
        if len(self.detection_boxes) > 500 or len(self.motion_proposal_boxes) > 32:
            raise TemporalCaptureError("retained_frame_detection_limit")


@dataclass(frozen=True)
class CaptureSessionManifest:
    config: CaptureSessionConfig
    session_id: str
    node_session_id: str
    start_host_time_iso: str
    end_host_time_iso: str
    start_source_offset_ms: int
    end_source_offset_ms: int
    first_sequence: int
    last_sequence: int
    sequence_gap_count: int
    dropped_frame_count: int
    coalesced_frame_count: int
    stale_frame_count: int
    generation_reset_count: int
    provider_generations: tuple[str, ...]
    model_fingerprint: str
    tracker_proposal_config_fingerprint: str
    frames: tuple[RetainedFrameRecord, ...]
    operator_markers: tuple[OperatorMarker, ...]
    stop_condition: str

    def __post_init__(self) -> None:
        if not self.session_id or not self.node_session_id:
            raise TemporalCaptureError("invalid_capture_session_identity")
        if self.stop_condition not in STOP_CONDITIONS:
            raise TemporalCaptureError("invalid_stop_condition")
        frame_ids = [item.frame_id for item in self.frames]
        if len(frame_ids) != len(set(frame_ids)):
            raise TemporalCaptureError("duplicate_frame_identity")
        if len(self.frames) > self.config.bounds.max_analysis_frames:
            raise TemporalCaptureError("analysis_frame_limit_exceeded")
        if sum(1 for item in self.frames if item.high_resolution) > self.config.bounds.max_high_resolution_frames:
            raise TemporalCaptureError("high_resolution_frame_limit_exceeded")
        if len(self.operator_markers) > self.config.bounds.max_operator_markers:
            raise TemporalCaptureError("operator_marker_limit_exceeded")

    def to_semantic_dict(self) -> dict[str, object]:
        """The versioned, fingerprintable manifest payload. Absolute paths,
        hostnames, credentials, and bearer tokens are structurally excluded:
        this function only ever reads fields already declared on the pure
        dataclasses above, none of which carries one."""

        from dataclasses import asdict

        semantic: dict[str, object] = {
            "schema_version": CAPTURE_MANIFEST_SCHEMA_VERSION,
            "capture_version": CAPTURE_MANIFEST_VERSION,
            "session_id": self.session_id,
            "node_session_id": self.node_session_id,
            "config": asdict(self.config),
            "start_host_time": self.start_host_time_iso,
            "end_host_time": self.end_host_time_iso,
            "start_source_offset_ms": self.start_source_offset_ms,
            "end_source_offset_ms": self.end_source_offset_ms,
            "first_sequence": self.first_sequence,
            "last_sequence": self.last_sequence,
            "sequence_gap_count": self.sequence_gap_count,
            "dropped_frame_count": self.dropped_frame_count,
            "coalesced_frame_count": self.coalesced_frame_count,
            "stale_frame_count": self.stale_frame_count,
            "generation_reset_count": self.generation_reset_count,
            "provider_generations": list(self.provider_generations),
            "model_fingerprint": self.model_fingerprint,
            "tracker_proposal_config_fingerprint": self.tracker_proposal_config_fingerprint,
            "frames": [asdict(item) for item in sorted(self.frames, key=lambda item: item.sequence)],
            "operator_markers": [asdict(item) for item in self.operator_markers],
            "stop_condition": self.stop_condition,
            "creates_truth": False,
            "shadow_only": True,
            "production_proposal_authority": False,
        }
        return semantic

    @property
    def fingerprint(self) -> str:
        return semantic_fingerprint(self.to_semantic_dict())


__all__ = [
    "CAPTURE_MANIFEST_SCHEMA_VERSION",
    "CAPTURE_MANIFEST_VERSION",
    "OPERATOR_MARKER_ENVIRONMENTAL_CHANGE",
    "OPERATOR_MARKER_KINDS",
    "OPERATOR_MARKER_KNOWN_EMPTY",
    "OPERATOR_MARKER_UNCERTAIN_POSSIBLE",
    "OPERATOR_MARKER_WILDLIFE_RECENT",
    "OPERATOR_MARKER_WILDLIFE_VISIBLE_NOW",
    "STOP_ACTIVE_TRACK_LIMIT",
    "STOP_BYTE_LIMIT",
    "STOP_CONDITIONS",
    "STOP_DURATION_ELAPSED",
    "STOP_FRAME_LIMIT",
    "STOP_HIGH_RESOLUTION_LIMIT",
    "STOP_MANUAL",
    "STOP_MARKER_LIMIT",
    "STOP_OUTPUT_FILE_LIMIT",
    "STOP_STREAM_ENDED",
    "STOP_TRANSPORT_ERROR",
    "TRIGGER_ANIMAL_ABOVE_OPERATING_POINT",
    "TRIGGER_ANIMAL_BELOW_OPERATING_POINT_ABOVE_REVIEW_FLOOR",
    "TRIGGER_GENERATION_OR_SEQUENCE_DISCONTINUITY",
    "TRIGGER_HIGH_RESOLUTION_BURST",
    "TRIGGER_MOTION_PROPOSAL_GENERATED",
    "TRIGGER_OPERATOR_MARKER",
    "TRIGGER_PERIODIC_NEGATIVE_SAMPLE",
    "TRIGGER_POST_TRIGGER_CONTEXT",
    "TRIGGER_PRETRIGGER_CONTEXT",
    "TRIGGER_PRIVACY_IGNORE_INTERACTION",
    "TRIGGER_RECURRING_STATIC_GEOMETRY",
    "TRIGGER_REASONS",
    "TRIGGER_SHADOW_TRACK_EVENT",
    "CaptureBounds",
    "CaptureSessionConfig",
    "CaptureSessionManifest",
    "OperatorMarker",
    "PeriodicNegativeScheduler",
    "RecurringGeometryTracker",
    "RetainedFrameRecord",
    "TemporalCaptureError",
    "classify_detection_triggers",
    "has_track_event",
    "markers_near",
]
