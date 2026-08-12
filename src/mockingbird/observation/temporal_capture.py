"""Provider-neutral bounded temporal-capture contract and trigger logic.

Observation Engine v2 Stage 6.6, extended by Stage 6.8 with a reconnect-safe
session timeline. This module is pure: no CUDA, ONNX Runtime, OpenCV,
camera-provider, or filesystem type anywhere in its contract. It decides
*which already-processed frames to retain* and assembles the versioned
capture-session manifest; it never opens a network connection, decodes an
image, or writes a file (see `temporal_capture_io.py`/
`temporal_capture_cli.py`). Retention decisions consume only already-emitted
provider-neutral facts (`DetectionObservation`, `TrackUpdate`,
`EvidenceCandidate`) exactly the way `multi_scale_strategy`/
`motion_proposal_strategy` consume already-decoded detections -- this module
adds no new pixel-level or network-level behavior of its own.

A real paired Camera Node resets its own per-connection transport sequence
number and this codebase's source-relative offset bookkeeping on every HTTP
reconnection while `provider_generation` (the camera/provider identity)
stays unchanged -- reconnecting every few seconds is the *normal* case on
this transport (see docs/temporal-review-capture-contract.md), not a rare
failure. `RetainedFrameRecord` therefore carries both the original
source-local facts a connection supplied (`sequence`, `source_offset_ms`,
`provider_generation`, `source_capture_timestamp`) and a separate, derived
session-timeline coordinate (`session_sequence`, `session_offset_ms`,
`connection_segment_id`, ...) computed by
`mockingbird.observation.session_timeline`. See
docs/session-timeline-contract.md.

See docs/temporal-review-capture-contract.md.
"""
from __future__ import annotations

from dataclasses import dataclass
import re

from mockingbird.observation.contracts import DetectionObservation, TrackUpdate
from mockingbird.observation.replay import semantic_fingerprint
from mockingbird.observation.session_timeline import (
    INSUFFICIENT_TEMPORAL_PROVENANCE,
    NATIVE_SESSION_TIMELINE,
    SESSION_TIMELINE_CLASSIFICATIONS,
    SessionTimeline,
    SessionTimelineError,
    SourceFrameFact,
    derive_session_timeline,
)

CAPTURE_MANIFEST_SCHEMA_VERSION = 2
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

# --------------------------------------------------------------------------
# Multi-Scene Backyard Domain Acquisition v1: stable physical-scene identity
# and explicit capture purpose. A scene names one materially distinct
# camera view/environment (feeder close view, lawn, woods/tree line,
# deck/patio, ...) -- never inferred from a session id, a stream id, or a
# small camera nudge; always operator-supplied. Empty string means "not
# recorded" (every capture before this field existed, or a hand-built test
# fixture), never a fabricated scene -- see `RetainedFrameRecord.scene_id`/
# `CaptureSessionConfig.scene_id`. See docs/wildlife-detector-training-contract.md
# "Scene identity and multi-scene acquisition".
SCENE_ID_PATTERN = re.compile(r"^[a-z0-9]([a-z0-9-]{0,62}[a-z0-9])?$")

CAPTURE_PURPOSE_TRAINING_CANDIDATE = "training_candidate"
CAPTURE_PURPOSE_HOLDOUT_V2_CANDIDATE = "holdout_v2_candidate"
CAPTURE_PURPOSES: tuple[str, ...] = (
    CAPTURE_PURPOSE_TRAINING_CANDIDATE,
    CAPTURE_PURPOSE_HOLDOUT_V2_CANDIDATE,
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
    exact_analysis_capture_enabled: bool = False
    # Multi-Scene Backyard Domain Acquisition v1: the physical scene this
    # whole session was captured for, and why (see `CAPTURE_PURPOSES`).
    # Recorded at the session level -- not only per-frame (`RetainedFrameRecord.
    # scene_id`) -- so a session that retains zero frames (a genuinely quiet
    # scene, still a useful signal) never loses which scene was checked.
    # Default empty/"training_candidate" preserves every pre-existing
    # hand-built `CaptureSessionConfig` fixture and any capture predating
    # this field; a real `temporal-capture` invocation always supplies both.
    scene_id: str = ""
    capture_purpose: str = CAPTURE_PURPOSE_TRAINING_CANDIDATE
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
        if self.scene_id and not SCENE_ID_PATTERN.fullmatch(self.scene_id):
            raise TemporalCaptureError("invalid_scene_id")
        if self.capture_purpose not in CAPTURE_PURPOSES:
            raise TemporalCaptureError("invalid_capture_purpose")


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


def correlate_markers_to_frames(
    frames: tuple[dict[str, object], ...], markers: tuple[OperatorMarker, ...],
) -> dict[str, tuple[str, ...]]:
    """Post-hoc, reconnect-safe operator-marker correlation over an entire
    retained-frame population -- not the bounded, memory-limited live rescue
    buffers `temporal_capture_cli._CaptureLoop` uses during capture.

    Every frame that carries a real host receive timestamp (`host_received_at`,
    populated for a native Stage 6.8 capture; absent for an un-upgraded
    legacy one) is checked against every marker's own bounded lookback via
    `markers_near`, exactly the same rule the live path uses -- correlation
    is host-time based, so it is unaffected by a connection-local `sequence`
    reset and freely crosses a reconnect boundary when timing genuinely
    supports it. This can run at review-build time, so a frame already
    retained for an unrelated trigger, or one whose marker was written after
    the live capture process's bounded rescue window already closed, can
    still receive its marker association.

    Returns each frame's complete, deterministically deduplicated
    `operator_marker_ids` tuple (already-recorded associations are always
    preserved and merged with, never replaced by, anything newly found), so
    a caller can simply overwrite the field with the result -- this never
    fabricates an association where timing does not support one, and a
    frame lacking `host_received_at` entirely is returned unchanged.
    """

    associations: dict[str, tuple[str, ...]] = {}
    for frame in frames:
        frame_id = str(frame["frame_id"])
        existing = tuple(frame.get("operator_marker_ids") or ())  # type: ignore[union-attr]
        received_at = frame.get("host_received_at")
        near: tuple[OperatorMarker, ...] = ()
        if received_at and markers:
            near = markers_near(markers, host_time_iso=str(received_at), default_lookback_seconds=20)
        associations[frame_id] = tuple(dict.fromkeys((*existing, *(item.marker_id for item in near))))
    return associations


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
    derived from `frame_id` (see `temporal_capture_io`).

    `sequence`/`source_offset_ms`/`provider_generation` are source-local
    facts supplied directly by one Camera Node transport connection --
    `sequence` resets and `source_offset_ms` re-zeroes on every HTTP
    reconnection, and this record never overwrites or "fixes" that. The
    `session_*`/`connection_segment_*`/`temporal_*` fields below are a
    *separate*, derived, reconnect-safe coordinate computed once per capture
    session by `mockingbird.observation.session_timeline` -- see
    docs/session-timeline-contract.md. They default to the first-frame-of-a-
    single-segment shape so hand-built records (tests, the one-off
    validation-burst frame) remain valid without every caller needing to
    know about timeline derivation; `temporal_capture_cli`/`temporal_review_io`
    are the only callers that compute real values for a multi-frame session.
    """

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
    # Stage-3 Holdout v2 groundwork: an explicit, capture-time-only reservation
    # that this frame belongs to a future evaluation-only holdout, never a
    # training-correction pool. Set once, by the operator, before capture
    # (`temporal-capture --holdout-v2-session`) -- never inferred from trigger
    # reasons or detector output, and never flipped after the fact by any
    # downstream selector. A Stage-3 (or later) tranche builder must treat
    # `True` here as a hard exclusion; see `wildlife_stage3_tranche.py`. This
    # milestone only adds the capability and its downstream guard -- it does
    # not collect or label a real Holdout v2 corpus.
    holdout_v2_candidate: bool = False
    # Multi-Scene Backyard Domain Acquisition v1: the stable physical-scene
    # identity this frame belongs to (see `SCENE_ID_PATTERN`), inherited
    # unchanged from the session-level `--scene-id` every frame in one
    # capture session shares -- never inferred per-frame, never re-derived
    # from pixels. Empty string means "not recorded" (every capture before
    # this field existed) -- honest absence, not a fabricated scene. See
    # `mockingbird.training.wildlife_multiscene`.
    scene_id: str = ""
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
    # Optional, explicit exact-analysis-frame diagnostic envelope. The exact
    # payload itself is the same bounded JPEG named by frame_id; this adds
    # provider outputs and lineage without creating truth or a product record.
    exact_analysis: dict[str, object] | None = None
    # Original per-frame provenance the live capture always has available
    # but the pre-Stage-6.8 schema never persisted: the host wall-clock
    # instant this frame was actually received (the anchor a reconnect-safe
    # session timeline is derived from) and the original Node capture
    # timestamp, both ISO 8601. Empty string means "not recorded" (a
    # pre-Stage-6.8 record being read back), never "recorded as zero".
    host_received_at: str = ""
    source_capture_timestamp: str | None = None
    # Derived, reconnect-safe session-timeline coordinate -- see the class
    # docstring. `connection_segment_id` deterministically identifies one
    # contiguous transport connection (the real per-connection Node session
    # id for a native capture; a reconstructed synthetic id for an upgraded
    # legacy one).
    connection_segment_id: str = ""
    connection_segment_ordinal: int = 0
    session_sequence: int = 0
    session_offset_ms: int = 0
    previous_frame_identity: str | None = None
    temporal_discontinuity: bool = False
    temporal_uncertainty_ms: int = 0

    def __post_init__(self) -> None:
        if not self.frame_id or self.sequence < 0 or self.source_offset_ms < 0:
            raise TemporalCaptureError("invalid_retained_frame")
        if not self.trigger_reasons or any(reason not in TRIGGER_REASONS for reason in self.trigger_reasons):
            raise TemporalCaptureError("invalid_retained_frame_trigger")
        if len(self.detection_boxes) > 500 or len(self.motion_proposal_boxes) > 32:
            raise TemporalCaptureError("retained_frame_detection_limit")
        if self.exact_analysis is not None:
            detector_input = self.exact_analysis.get("detector_input")
            if (
                self.high_resolution
                or self.exact_analysis.get("frame_id") != self.frame_id
                or self.exact_analysis.get("creates_truth") is not False
                or self.exact_analysis.get("creates_product_record") is not False
                or not isinstance(detector_input, dict)
                or detector_input.get("sha256") != self.content_hash
                or detector_input.get("byte_size") != self.byte_size
            ):
                raise TemporalCaptureError("invalid_exact_analysis_envelope")
        if self.session_sequence < 0 or self.session_offset_ms < 0 or self.temporal_uncertainty_ms < 0:
            raise TemporalCaptureError("invalid_session_timeline_fields")
        if self.scene_id and not SCENE_ID_PATTERN.fullmatch(self.scene_id):
            raise TemporalCaptureError("invalid_scene_id")


def attach_session_timeline(
    frames: tuple[RetainedFrameRecord, ...], *, session_id: str,
) -> tuple[tuple[RetainedFrameRecord, ...], SessionTimeline]:
    """Compute the Stage 6.8 session timeline once, over a fully assembled
    retained-frame set, and merge it back onto each record.

    This is deliberately a single post-processing pass over the *complete*
    session rather than incremental per-frame bookkeeping while capture is
    still running: `_CaptureLoop` already tracks everything a connection
    segment needs live (the real Node per-connection session id, host
    receive time) for its own bounded, real-time purposes (marker rescue,
    periodic sampling), but the *derived* monotonic coordinate only needs to
    be correct once, deterministically, over the finished frame list -- and
    computing it once here, instead of threading a running offset through
    the live loop, keeps that loop's own retention logic unchanged.

    Returns the frames with their `session_*`/`connection_segment_*`/
    `temporal_*` fields populated (order unchanged from the input) alongside
    the `SessionTimeline` used to populate them, so a caller can also record
    its session-level classification/limitations/upgrade provenance on the
    manifest. Source-local fields (`sequence`, `source_offset_ms`,
    `provider_generation`, `host_received_at`, `source_capture_timestamp`)
    are read, never modified.
    """

    from dataclasses import replace as _dataclasses_replace

    facts = tuple(
        SourceFrameFact(
            frame_id=item.frame_id, source_sequence=item.sequence, source_offset_ms=item.source_offset_ms,
            provider_generation=item.provider_generation,
            connection_segment_hint=item.connection_segment_id or None,
            host_received_at_iso=item.host_received_at or None,
            source_capture_timestamp_iso=item.source_capture_timestamp,
        )
        for item in frames
    )
    timeline = derive_session_timeline(facts, session_id=session_id)
    by_id = {item.frame_id: item for item in timeline.frames}
    updated = tuple(
        _dataclasses_replace(
            record,
            connection_segment_id=by_id[record.frame_id].connection_segment_id,
            connection_segment_ordinal=by_id[record.frame_id].connection_segment_ordinal,
            session_sequence=by_id[record.frame_id].session_sequence,
            session_offset_ms=by_id[record.frame_id].session_offset_ms,
            previous_frame_identity=by_id[record.frame_id].previous_frame_identity,
            temporal_discontinuity=by_id[record.frame_id].temporal_discontinuity,
            temporal_uncertainty_ms=by_id[record.frame_id].temporal_uncertainty_ms,
        )
        for record in frames
    )
    return updated, timeline


_TIMELINE_FRAME_FIELDS = (
    "connection_segment_id", "connection_segment_ordinal", "session_sequence", "session_offset_ms",
    "previous_frame_identity", "temporal_discontinuity", "temporal_uncertainty_ms",
)


def upgrade_capture_manifest_timeline(manifest: dict[str, object]) -> dict[str, object]:
    """Ensure a *loaded* capture-manifest dict (as `temporal_capture_io.
    load_capture_manifest` returns it) carries Stage 6.8 session-timeline
    fields on every frame.

    An already-native manifest (a Stage 6.8 `temporal-capture` output) is
    returned completely unchanged -- same object, same fingerprint, no
    recomputation -- since deriving it again would be redundant work with a
    real (if small) risk of an unstated precondition drifting the result.
    A pre-Stage-6.8 manifest, or one otherwise missing the fields, is
    upgraded via `session_timeline.derive_session_timeline` and returned as
    a *new* dict with every frame's timeline fields populated, a top-level
    `session_timeline_classification`, `timeline_upgrade_provenance`, and a
    freshly recomputed `semantic_fingerprint` covering the added fields.
    This never mutates its argument or touches a filesystem; the caller
    (`temporal_review_io.build_review_packet`) decides whether/where to
    persist the result, and the original capture directory's own manifest
    file is never touched.

    When even the minimum source-local provenance (`sequence`,
    `source_offset_ms`) required to derive *anything* is missing or
    malformed, this fails honestly rather than fabricating order: frames are
    returned unchanged (no session_* fields invented) and the manifest is
    classified `insufficient_temporal_provenance` so callers such as
    `validate_annotations`/`build_replay_export` can refuse cleanly instead
    of reading absent fields.
    """

    raw_frames = manifest.get("frames", [])
    if not isinstance(raw_frames, list):
        raise TemporalCaptureError("invalid_capture_manifest")
    if _manifest_already_has_native_timeline(manifest, raw_frames):
        return manifest

    facts: list[SourceFrameFact] = []
    try:
        for item in raw_frames:
            if not isinstance(item, dict):
                raise TemporalCaptureError("invalid_capture_manifest")
            facts.append(SourceFrameFact(
                frame_id=str(item["frame_id"]), source_sequence=int(item["sequence"]),
                source_offset_ms=int(item["source_offset_ms"]),
                provider_generation=str(item.get("provider_generation") or "unknown"),
                connection_segment_hint=str(item["connection_segment_id"]) if item.get("connection_segment_id") else None,
                host_received_at_iso=str(item["host_received_at"]) if item.get("host_received_at") else None,
                source_capture_timestamp_iso=(str(item["source_capture_timestamp"]) if item.get("source_capture_timestamp") else None),
            ))
    except (KeyError, TypeError, ValueError, SessionTimelineError) as error:
        return _insufficient_provenance_manifest(manifest, reason=str(error))

    session_id = str(manifest.get("session_id") or "unknown-session")
    try:
        timeline = derive_session_timeline(tuple(facts), session_id=session_id)
    except SessionTimelineError as error:
        return _insufficient_provenance_manifest(manifest, reason=str(error))

    by_id = {item.frame_id: item for item in timeline.frames}
    updated_frames = []
    for item in raw_frames:
        derived = by_id.get(str(item["frame_id"]))
        updated = dict(item)
        if derived is not None:
            updated["connection_segment_id"] = derived.connection_segment_id
            updated["connection_segment_ordinal"] = derived.connection_segment_ordinal
            updated["session_sequence"] = derived.session_sequence
            updated["session_offset_ms"] = derived.session_offset_ms
            updated["previous_frame_identity"] = derived.previous_frame_identity
            updated["temporal_discontinuity"] = derived.temporal_discontinuity
            updated["temporal_uncertainty_ms"] = derived.temporal_uncertainty_ms
        updated_frames.append(updated)
    # Written in session order, not whatever order the legacy manifest's
    # own (connection-local-sequence-sorted, cross-connection-scrambled)
    # array happened to store them in -- mirrors
    # CaptureSessionManifest.to_semantic_dict()'s own sort so a manifest
    # this function upgrades is ordered identically to one a native Stage
    # 6.8 capture wrote directly.
    updated_frames.sort(key=lambda item: item["session_sequence"])

    upgraded = {key: value for key, value in manifest.items() if key != "semantic_fingerprint"}
    upgraded["frames"] = updated_frames
    upgraded["session_timeline_classification"] = timeline.classification
    upgraded["timeline_upgrade_provenance"] = timeline.upgrade_provenance
    upgraded["semantic_fingerprint"] = semantic_fingerprint(upgraded)
    return upgraded


def _manifest_already_has_native_timeline(manifest: dict[str, object], frames: list) -> bool:
    if manifest.get("session_timeline_classification") != NATIVE_SESSION_TIMELINE:
        return False
    if not frames:
        return True
    return all(
        isinstance(item, dict) and item.get("connection_segment_id") and item.get("host_received_at")
        and all(key in item for key in _TIMELINE_FRAME_FIELDS)
        for item in frames
    )


def _insufficient_provenance_manifest(manifest: dict[str, object], *, reason: str) -> dict[str, object]:
    upgraded = {key: value for key, value in manifest.items() if key != "semantic_fingerprint"}
    upgraded["session_timeline_classification"] = INSUFFICIENT_TEMPORAL_PROVENANCE
    upgraded["timeline_upgrade_provenance"] = {
        "derivation_method": "none", "reason": reason,
        "limitation": "source-local provenance was insufficient to derive any session timeline; "
                      "frames are unchanged and carry no session_* fields",
    }
    upgraded["semantic_fingerprint"] = semantic_fingerprint(upgraded)
    return upgraded


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
    # Stage 6.8: which derivation produced the session-timeline fields above
    # on `frames`, plus an honest record of how a legacy upgrade got there.
    # Defaults to native because every field this class validates already
    # assumes one capture run computed them directly; a review-build upgrade
    # of an older manifest sets these explicitly (see temporal_review_io).
    session_timeline_classification: str = NATIVE_SESSION_TIMELINE
    timeline_upgrade_provenance: dict[str, object] | None = None

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
        if self.session_timeline_classification not in SESSION_TIMELINE_CLASSIFICATIONS:
            raise TemporalCaptureError("invalid_session_timeline_classification")
        # Defense-in-depth honesty check, mirroring `duplicate_frame_identity`
        # above: a frame that does carry its own explicit scene_id must agree
        # with the session's own declared scene -- never silently divergent.
        # A frame with an empty scene_id (predating this field, or a
        # hand-built fixture) is always compatible with any session value.
        if self.config.scene_id and any(
            item.scene_id and item.scene_id != self.config.scene_id for item in self.frames
        ):
            raise TemporalCaptureError("scene_id_mismatch_between_config_and_frame")
        # Same discipline for capture purpose: a session declared
        # `holdout_v2_candidate` must never persist a frame whose own
        # `holdout_v2_candidate` flag disagrees (see `_CaptureLoop._retain`,
        # which always derives both from the same session-level setting, so
        # this can only fire if a caller builds a manifest by hand incorrectly).
        if self.config.capture_purpose == CAPTURE_PURPOSE_HOLDOUT_V2_CANDIDATE and any(
            not item.holdout_v2_candidate for item in self.frames
        ):
            raise TemporalCaptureError("capture_purpose_mismatch_between_config_and_frame")

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
            # Ordered by the reconnect-safe session timeline, not the raw
            # per-connection `sequence` -- that value resets on every HTTP
            # reconnect, so sorting by it alone interleaves unrelated
            # connections' frames instead of preserving session order. A
            # manifest whose frames never went through timeline derivation
            # (every `session_sequence` still at its 0 default) degrades to
            # the tuple's own original order via Python's stable sort,
            # unchanged from single-connection/no-reconnect behavior.
            "frames": [asdict(item) for item in sorted(self.frames, key=lambda item: item.session_sequence)],
            "operator_markers": [asdict(item) for item in self.operator_markers],
            "stop_condition": self.stop_condition,
            "session_timeline_classification": self.session_timeline_classification,
            "timeline_upgrade_provenance": self.timeline_upgrade_provenance,
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
    "CAPTURE_PURPOSES",
    "CAPTURE_PURPOSE_HOLDOUT_V2_CANDIDATE",
    "CAPTURE_PURPOSE_TRAINING_CANDIDATE",
    "SCENE_ID_PATTERN",
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
    "attach_session_timeline",
    "classify_detection_triggers",
    "correlate_markers_to_frames",
    "has_track_event",
    "markers_near",
    "upgrade_capture_manifest_timeline",
]
