"""Bounded local object inference and temporal tracks for live outdoor Zones.

This is deliberately a small bridge between the optional MegaDetector adapter
and the existing activity/session handoff. It owns neither a camera nor a
product record: callers provide already-captured, privacy/ignore-masked full
monitoring frames, and detections remain observational evidence until the
normal review flow creates a Visit.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from math import hypot
from uuid import uuid4
import multiprocessing
from time import monotonic, sleep
import threading
from typing import Any, Literal

from mockingbird.detectors.megadetector_adapter import (
    MegaDetectorBox,
    MegaDetectorProposal,
    get_megadetector_status,
    megadetector_model_provenance,
    megadetector_execution_device,
    run_megadetector_on_jpeg_bytes,
)


OBJECT_LABELS = {"animal", "person", "vehicle"}
MAX_PENDING_INFERENCE_JOBS = 1
MAX_OBJECT_TRACKS_PER_STREAM = 24
MAX_TRACK_MISSES = 15
STRONG_OBJECT_SCORE = 0.50
WEAK_OBJECT_SCORE = 0.20
# A detector score is evidence, not durable animal admission by itself.
MIN_ANIMAL_ADMISSION_OBSERVATIONS = 2
INFERENCE_TIMEOUT_SECONDS = 20.0
INITIAL_RUNTIME_LOAD_TIMEOUT_SECONDS = 60.0
RUNTIME_RECOVERY_BACKOFF_SECONDS = 0.25
RUNTIME_WORKER_START_TIMEOUT_SECONDS = 10.0
MAX_RUNTIME_RECOVERY_BACKOFF_SECONDS = 4.0
RUNTIME_STOP_GRACE_SECONDS = 1.0

# Admission diagnostics are operational evidence only. They intentionally retain
# no bytes and rotate with the in-memory detector generation.
MAX_ADMISSION_RECENT_OUTCOMES = 50
MAX_ADMISSION_FRAME_IDENTITIES_PER_CANDIDATE = 2
MAX_ADMISSION_DIAGNOSTIC_LENGTH = 96
MAX_ADMISSION_COUNTER = 1_000_000

AdmissionReason = Literal[
    "no_animal_detection",
    "duplicate_frame_ignored",
    "first_distinct_frame_recorded",
    "single_frame_candidate_expired",
    "spatial_coherence_rejected",
    "stale_generation_ignored",
    "detector_reset_interrupted",
    "admission_satisfied",
    "promotion_failed",
    "visit_promoted",
]

ADMISSION_COUNTER_KEYS = (
    "frames_submitted",
    "inferences_completed",
    "inferences_with_animal",
    "inferences_without_animal",
    "duplicate_frame_identities_ignored",
    "stale_generation_results_ignored",
    "candidate_tracks_started",
    "first_distinct_support_frames",
    "valid_second_distinct_frames",
    "spatial_coherence_rejected",
    "single_frame_candidates_expired",
    "reset_interrupted_candidates",
    "admissions_satisfied",
    "durable_promotion_attempts",
    "successful_visit_promotions",
    "failed_promotion_attempts",
)


def detector_interval_seconds(zone_type: str) -> float:
    """Return the initial local cadence; queue pressure still wins over cadence."""

    if zone_type in {"feeder", "perch", "birdbath"}:
        return 0.75
    if zone_type in {"yard", "ground", "whole_stream"}:
        return 1.5
    if zone_type == "driveway":
        return 2.0
    return 2.0


@dataclass(frozen=True)
class ObjectDetection:
    label: Literal["animal", "person", "vehicle"]
    score: float
    left: float
    top: float
    right: float
    bottom: float
    zone_id: str
    frame_identity: str
    captured_at: datetime

    @property
    def box(self) -> tuple[float, float, float, float]:
        return (self.left, self.top, self.right, self.bottom)

    def as_dict(self) -> dict[str, object]:
        return {
            "class": self.label,
            "score": self.score,
            "left": self.left,
            "top": self.top,
            "right": self.right,
            "bottom": self.bottom,
            "zone_id": self.zone_id,
            "frame_identity": self.frame_identity,
            "captured_at": self.captured_at,
        }


@dataclass(frozen=True)
class ObjectTrack:
    track_id: str
    track_generation_id: str
    label: Literal["animal", "person", "vehicle"]
    score: float
    state: Literal["active", "stationary", "disappeared"]
    first_seen_at: datetime
    last_seen_at: datetime
    hit_count: int
    missed_count: int
    zone_id: str
    box: tuple[float, float, float, float]
    frame_identity: str
    triggered: bool

    def as_dict(self) -> dict[str, object]:
        return {
            "track_id": self.track_id,
            "track_generation_id": self.track_generation_id,
            "class": self.label,
            "score": self.score,
            "state": self.state,
            "first_seen_at": self.first_seen_at,
            "last_seen_at": self.last_seen_at,
            "hit_count": self.hit_count,
            "missed_count": self.missed_count,
            "zone_id": self.zone_id,
            "left": self.box[0],
            "top": self.box[1],
            "right": self.box[2],
            "bottom": self.box[3],
            "frame_identity": self.frame_identity,
            "triggered": self.triggered,
        }


@dataclass(frozen=True)
class ObjectTrackTrigger:
    track_id: str
    track_generation_id: str
    zone_id: str
    label: Literal["animal", "person", "vehicle"]
    score: float
    box: tuple[float, float, float, float]
    frame_identity: str
    captured_at: datetime


@dataclass(frozen=True)
class AdmissionOutcome:
    occurred_at: datetime
    reason: AdmissionReason
    runtime_generation: int
    detector_generation: int
    track_generation_id: str | None = None
    frame_identities: tuple[str, ...] = ()
    label: Literal["animal", "person", "vehicle"] | None = None
    score: float | None = None
    box: tuple[float, float, float, float] | None = None
    zone_id: str | None = None
    distinct_support_frame_count: int = 0
    spatial_coherence: bool | None = None
    promotion_attempted: bool = False
    event_id: str | None = None
    visit_id: str | None = None
    error_category: str | None = None

    def as_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "occurred_at": self.occurred_at,
            "reason": self.reason,
            "runtime_generation": self.runtime_generation,
            "detector_generation": self.detector_generation,
            "track_generation_id": self.track_generation_id,
            "frame_identities": list(self.frame_identities),
            "class": self.label,
            "score": self.score,
            "zone_id": self.zone_id,
            "distinct_support_frame_count": self.distinct_support_frame_count,
            "spatial_coherence": self.spatial_coherence,
            "promotion_attempted": self.promotion_attempted,
            "event_id": self.event_id,
            "visit_id": self.visit_id,
            "error_category": self.error_category,
        }
        if self.box is not None:
            payload.update(
                {
                    "left": self.box[0],
                    "top": self.box[1],
                    "right": self.box[2],
                    "bottom": self.box[3],
                }
            )
        return payload


@dataclass
class _AdmissionTelemetry:
    detector_generation: int = 0
    counters: dict[str, int] = field(
        default_factory=lambda: {key: 0 for key in ADMISSION_COUNTER_KEYS}
    )
    recent_outcomes: deque[AdmissionOutcome] = field(
        default_factory=lambda: deque(maxlen=MAX_ADMISSION_RECENT_OUTCOMES)
    )
    last_decision_at: datetime | None = None
    last_successful_promotion_at: datetime | None = None

    def increment(self, key: str) -> None:
        self.counters[key] = min(MAX_ADMISSION_COUNTER, self.counters[key] + 1)


@dataclass(frozen=True)
class ObjectDetectorSnapshot:
    detections: tuple[ObjectDetection, ...] = ()
    tracks: tuple[ObjectTrack, ...] = ()
    triggers: tuple[ObjectTrackTrigger, ...] = ()
    cadence_seconds: float | None = None
    inference_latency_ms: int | None = None
    queue_depth: int = 0
    queue_capacity: int = MAX_PENDING_INFERENCE_JOBS
    dropped_frame_count: int = 0
    stale_frame_count: int = 0
    timed_out_count: int = 0
    runtime_state: str = "ready"
    model_configuration_state: str = "unknown"
    model_loaded: bool = False
    worker_alive: bool = False
    in_flight_job_identity: str | None = None
    in_flight_age_ms: int | None = None
    last_submitted_at: datetime | None = None
    last_completed_at: datetime | None = None
    last_completed_age_ms: int | None = None
    latest_successful_inference_latency_ms: int | None = None
    worker_reset_count: int = 0
    recovery_count: int = 0
    queue_replacement_count: int = 0
    execution_device: str | None = None
    last_safe_error_category: str | None = None
    runtime_generation: int = 0
    unavailable_reason: str | None = None
    completed_frame_identity: str | None = None
    admission_observability_available: bool = False
    admission_runtime_generation: int = 0
    admission_counters: dict[str, int] = field(default_factory=dict)
    current_admission_candidates: tuple[dict[str, object], ...] = ()
    recent_admission_outcomes: tuple[dict[str, object], ...] = ()
    last_admission_decision_at: datetime | None = None
    last_successful_promotion_at: datetime | None = None


@dataclass(frozen=True)
class _InferenceJob:
    stream_id: str
    zone_id: str
    zone_type: str
    frame_identity: str
    sequence: int
    captured_at: datetime
    submitted_at: datetime
    coordinate_box: tuple[float, float, float, float]
    image: bytes


@dataclass
class _TrackState:
    track_id: str
    track_generation_id: str
    detection: ObjectDetection
    first_seen_at: datetime
    last_seen_at: datetime
    hit_count: int = 1
    missed_count: int = 0
    triggered: bool = False
    state: Literal["active", "stationary", "disappeared"] = "active"
    _seen_frame_identities: set[str] = field(default_factory=set)
    _seen_frame_order: deque[str] = field(default_factory=deque)

    def __post_init__(self) -> None:
        self._remember_frame_identity(self.detection.frame_identity)

    def _remember_frame_identity(self, frame_identity: str) -> None:
        self._seen_frame_identities.add(frame_identity)
        self._seen_frame_order.append(frame_identity)
        while len(self._seen_frame_order) > MAX_ADMISSION_FRAME_IDENTITIES_PER_CANDIDATE:
            expired = self._seen_frame_order.popleft()
            self._seen_frame_identities.discard(expired)

    def observe(self, detection: ObjectDetection) -> bool:
        # A cached frame may be evaluated again before the camera advances.
        # Replaying it is not fresh temporal confirmation.
        if detection.frame_identity in self._seen_frame_identities:
            return False
        self._remember_frame_identity(detection.frame_identity)
        self.detection = detection
        self.last_seen_at = detection.captured_at
        self.hit_count += 1
        self.missed_count = 0
        self.state = "active"
        return True

    @property
    def frame_identities(self) -> tuple[str, ...]:
        return tuple(self._seen_frame_order)

    def snapshot(self) -> ObjectTrack:
        detection = self.detection
        return ObjectTrack(
            track_id=self.track_id,
            track_generation_id=self.track_generation_id,
            label=detection.label,
            score=detection.score,
            state=self.state,
            first_seen_at=self.first_seen_at,
            last_seen_at=self.last_seen_at,
            hit_count=self.hit_count,
            missed_count=self.missed_count,
            zone_id=detection.zone_id,
            box=detection.box,
            frame_identity=detection.frame_identity,
            triggered=self.triggered,
        )


@dataclass
class _StreamState:
    tracks: dict[str, _TrackState] = field(default_factory=dict)
    next_track: int = 1
    last_submitted_at: dict[str, datetime] = field(default_factory=dict)
    last_sequence: dict[str, int] = field(default_factory=dict)
    latest: ObjectDetectorSnapshot = field(default_factory=ObjectDetectorSnapshot)
    admission: _AdmissionTelemetry = field(default_factory=_AdmissionTelemetry)


class _RuntimeInferenceTimeout(Exception):
    pass


class _RuntimeInferenceFailure(Exception):
    pass


def _isolated_megadetector_runtime_worker(
    connection: Any,
    runner: Callable[[bytes, MegaDetectorBox], list[MegaDetectorProposal]] | None,
) -> None:
    """Run one model generation until its parent requests shutdown."""

    try:
        while True:
            try:
                message = connection.recv()
            except (EOFError, OSError):
                return
            if message is None:
                return
            if not isinstance(message, _InferenceJob):
                continue

            try:
                connection.send(("started",))
                coordinate_box = MegaDetectorBox(
                    x=message.coordinate_box[0],
                    y=message.coordinate_box[1],
                    width=message.coordinate_box[2] - message.coordinate_box[0],
                    height=message.coordinate_box[3] - message.coordinate_box[1],
                )
                if runner is None:
                    proposals = run_megadetector_on_jpeg_bytes(
                        image=message.image,
                        coordinate_box=coordinate_box,
                    )
                else:
                    proposals = runner(message.image, coordinate_box)
                connection.send(("success", proposals, megadetector_execution_device()))
            except Exception:
                try:
                    connection.send(("failure", "megadetector_unavailable"))
                except (BrokenPipeError, EOFError, OSError):
                    return
    finally:
        try:
            connection.close()
        except (OSError, ValueError):
            pass


class LiveObjectDetectorManager:
    """One local inference worker with a one-item latest-frame queue.

    The worker consumes only supplied JPEG crops.  A slow optional runtime
    therefore drops stale work instead of blocking the camera reader or growing
    an unbounded backlog.
    """

    def __init__(
        self,
        *,
        runner: Callable[[bytes, MegaDetectorBox], list[MegaDetectorProposal]] | None = None,
        isolated_runner: Callable[[bytes, MegaDetectorBox], list[MegaDetectorProposal]] | None = None,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._isolated_runner = isolated_runner
        self._uses_isolated_runtime = runner is None or isolated_runner is not None
        self._runner = runner
        self._now = now or (lambda: datetime.now(UTC))
        self._condition = threading.Condition()
        self._queue: deque[_InferenceJob] = deque()
        self._completed: deque[tuple[_InferenceJob, list[MegaDetectorProposal] | None, int, str | None]] = deque()
        self._active: tuple[_InferenceJob, datetime] | None = None
        self._track_generation_epoch = uuid4().hex[:12]
        self._expired_jobs: set[tuple[str, str, int]] = set()
        self._states: dict[str, _StreamState] = {}
        # The display counter resets with transient per-Stream state.  Capture
        # ownership must instead use this manager-lifetime token so a later
        # track can never inherit evidence from an earlier numeric track id.
        self._next_track_generation = 1
        self._dropped_frame_count = 0
        self._stale_frame_count = 0
        self._timed_out_count = 0
        self._queue_replacement_count = 0
        try:
            model_status = get_megadetector_status()
            self._model_configuration_state = (
                "configured" if model_status.status == "available" else model_status.status
            )
        except Exception:
            self._model_configuration_state = "unavailable"
        self._runtime_process: Any | None = None
        self._runtime_connection: Any | None = None
        self._runtime_generation = 0
        self._runtime_model_loaded = False
        self._runtime_state = "ready"
        self._runtime_recovery_count = 0
        self._runtime_worker_reset_count = 0
        self._runtime_consecutive_timeouts = 0
        self._runtime_recovery_not_before = 0.0
        self._runtime_last_success_latency_ms: int | None = None
        self._runtime_last_completed_at: datetime | None = None
        self._runtime_last_error_category: str | None = None
        self._runtime_execution_device: str | None = None
        self._shutdown = False
        self._worker = threading.Thread(
            target=self._run, name="mockingbird-object-detector", daemon=True
        )
        self._worker.start()

    def _record_admission_outcome_locked(
        self,
        state: _StreamState,
        reason: AdmissionReason,
        *,
        detection: ObjectDetection | None = None,
        track: _TrackState | None = None,
        frame_identities: tuple[str, ...] = (),
        spatial_coherence: bool | None = None,
        promotion_attempted: bool = False,
        event_id: str | None = None,
        visit_id: str | None = None,
        error_category: str | None = None,
    ) -> None:
        if track is not None and not frame_identities:
            frame_identities = track.frame_identities
        if detection is not None and not frame_identities:
            frame_identities = (detection.frame_identity,)
        diagnostic = _safe_admission_diagnostic(error_category)
        occurred_at = (
            detection.captured_at
            if detection is not None
            else track.last_seen_at
            if track is not None
            else self._now()
        )
        state.admission.recent_outcomes.append(
            AdmissionOutcome(
                occurred_at=occurred_at,
                reason=reason,
                runtime_generation=state.admission.detector_generation,
                detector_generation=self._runtime_generation,
                track_generation_id=(
                    track.track_generation_id if track is not None else None
                ),
                frame_identities=frame_identities[:MAX_ADMISSION_FRAME_IDENTITIES_PER_CANDIDATE],
                label=(detection.label if detection is not None else track.detection.label if track else None),
                score=(detection.score if detection is not None else track.detection.score if track else None),
                box=(detection.box if detection is not None else track.detection.box if track else None),
                zone_id=(detection.zone_id if detection is not None else track.detection.zone_id if track else None),
                distinct_support_frame_count=(track.hit_count if track is not None else 0),
                spatial_coherence=spatial_coherence,
                promotion_attempted=promotion_attempted,
                event_id=event_id,
                visit_id=visit_id,
                error_category=diagnostic,
            )
        )
        state.admission.last_decision_at = occurred_at

    def _rotate_admission_generation_locked(
        self, state: _StreamState, generation: int
    ) -> None:
        previous_generation = state.admission.detector_generation
        if previous_generation == generation:
            return
        if previous_generation == 0:
            # The first worker launch adopts submissions already accepted while
            # the lazy runtime was starting; it is not a reset.
            state.admission.detector_generation = generation
            return
        interrupted = [
            track
            for track in state.tracks.values()
            if track.detection.label == "animal" and not track.triggered
        ]
        state.admission = _AdmissionTelemetry(detector_generation=generation)
        for track in interrupted:
            state.admission.increment("reset_interrupted_candidates")
            self._record_admission_outcome_locked(
                state, "detector_reset_interrupted", track=track
            )
        state.tracks.clear()

    def _record_reset_for_all_streams_locked(self, generation: int) -> None:
        for state in self._states.values():
            self._rotate_admission_generation_locked(state, generation)

    def record_admission_promotion(
        self,
        *,
        stream_id: str,
        track_generation_id: str | None,
        event_id: str | None = None,
        visit_id: str | None = None,
        error_category: str | None = None,
    ) -> None:
        """Record a completed durable handoff without creating product state."""

        if track_generation_id is None:
            return
        with self._condition:
            state = self._states.get(stream_id)
            if state is None:
                return
            track = next(
                (
                    item
                    for item in state.tracks.values()
                    if item.track_generation_id == track_generation_id
                ),
                None,
            )
            state.admission.increment("durable_promotion_attempts")
            if visit_id is not None:
                state.admission.increment("successful_visit_promotions")
                self._record_admission_outcome_locked(
                    state,
                    "visit_promoted",
                    track=track,
                    promotion_attempted=True,
                    event_id=event_id,
                    visit_id=visit_id,
                )
                state.admission.last_successful_promotion_at = self._now()
            else:
                state.admission.increment("failed_promotion_attempts")
                self._record_admission_outcome_locked(
                    state,
                    "promotion_failed",
                    track=track,
                    promotion_attempted=True,
                    error_category=error_category or "promotion_failed",
                )

    def submit(
        self,
        *,
        stream_id: str,
        zone_id: str,
        zone_type: str,
        frame_identity: str,
        sequence: int,
        captured_at: datetime,
        coordinate_box: tuple[float, float, float, float],
        image: bytes,
    ) -> ObjectDetectorSnapshot:
        now = self._now()
        with self._condition:
            state = self._states.setdefault(stream_id, _StreamState())
            self._expire_active_locked(now)
            self._drain_completed_locked(stream_id)
            previous_sequence = state.last_sequence.get(zone_id)
            if previous_sequence is not None and sequence <= previous_sequence:
                self._stale_frame_count += 1
                return self._snapshot_locked(state, zone_type=zone_type)
            last_submitted = state.last_submitted_at.get(zone_id)
            cadence = detector_interval_seconds(zone_type)
            if last_submitted is not None and now - last_submitted < timedelta(seconds=cadence):
                return self._snapshot_locked(state, zone_type=zone_type)
            state.last_sequence[zone_id] = sequence
            state.last_submitted_at[zone_id] = now
            job = _InferenceJob(
                stream_id=stream_id,
                zone_id=zone_id,
                zone_type=zone_type,
                frame_identity=frame_identity,
                sequence=sequence,
                captured_at=captured_at,
                submitted_at=now,
                coordinate_box=coordinate_box,
                image=image,
            )
            if len(self._queue) >= MAX_PENDING_INFERENCE_JOBS:
                # Replace the waiting frame with the newest crop; never queue a
                # historical sequence behind an already-running inference.
                self._queue.clear()
                self._dropped_frame_count += 1
                self._queue_replacement_count += 1
            self._queue.append(job)
            state.admission.increment("frames_submitted")
            self._condition.notify()
            return self._snapshot_locked(state, zone_type=zone_type)

    def select_zone_id(
        self, stream_id: str, zones: list[tuple[str, str]]
    ) -> str | None:
        """Choose the least-recently sampled ordinary Zone for fair bounded work."""

        if not zones:
            return None
        with self._condition:
            state = self._states.setdefault(stream_id, _StreamState())
            return min(
                zones,
                key=lambda item: state.last_submitted_at.get(
                    item[0], datetime.min.replace(tzinfo=UTC)
                ),
            )[0]

    def poll(self, stream_id: str) -> ObjectDetectorSnapshot:
        with self._condition:
            state = self._states.setdefault(stream_id, _StreamState())
            self._expire_active_locked(self._now())
            self._drain_completed_locked(stream_id)
            return self._snapshot_locked(state)

    def reset(self, stream_id: str) -> None:
        with self._condition:
            self._states.pop(stream_id, None)
            self._queue = deque(job for job in self._queue if job.stream_id != stream_id)
            self._completed = deque(
                item for item in self._completed if item[0].stream_id != stream_id
            )
            self._expired_jobs = {
                item for item in self._expired_jobs if item[0] != stream_id
            }

    def shutdown(self) -> None:
        """Release the current generation before the application reports shutdown."""

        with self._condition:
            self._shutdown = True
            self._active = None
            self._queue.clear()
            self._completed.clear()
            self._expired_jobs.clear()
            self._stop_isolated_runtime_locked()
            self._condition.notify_all()
        self._worker.join(timeout=RUNTIME_STOP_GRACE_SECONDS)
        with self._condition:
            # The isolated worker may have reported its connection failure while
            # shutdown was joining it. Never retain that crop or result after the
            # application has begun teardown.
            self._active = None
            self._queue.clear()
            self._completed.clear()
            self._expired_jobs.clear()
            # Application shutdown is a lifecycle boundary, not a diagnostic
            # archive. Release every candidate and bounded outcome ring.
            self._states.clear()

    def _ensure_isolated_runtime_locked(self) -> None:
        process = self._runtime_process
        connection = self._runtime_connection
        if process is not None and process.is_alive() and connection is not None:
            return
        self._stop_isolated_runtime_locked()
        context = multiprocessing.get_context("spawn")
        parent_connection, child_connection = context.Pipe(duplex=True)
        process = context.Process(
            target=_isolated_megadetector_runtime_worker,
            args=(child_connection, self._isolated_runner),
            name="mockingbird-megadetector-runtime",
            daemon=True,
        )
        try:
            process.start()
        except (OSError, RuntimeError, TypeError, AttributeError) as error:
            child_connection.close()
            parent_connection.close()
            raise _RuntimeInferenceFailure("worker_start_failed") from error
        child_connection.close()
        self._runtime_process = process
        self._runtime_connection = parent_connection
        self._runtime_generation += 1
        self._record_reset_for_all_streams_locked(self._runtime_generation)
        self._runtime_model_loaded = False
        self._runtime_state = "loading"

    def _stop_isolated_runtime_locked(self) -> None:
        connection = self._runtime_connection
        process = self._runtime_process
        self._runtime_connection = None
        self._runtime_process = None
        if connection is not None:
            try:
                connection.send(None)
            except (BrokenPipeError, EOFError, OSError):
                pass
            try:
                connection.close()
            except (OSError, ValueError):
                pass
        if process is None:
            return
        if process.is_alive():
            process.terminate()
            process.join(RUNTIME_STOP_GRACE_SECONDS)
        if process.is_alive():
            process.kill()
            process.join(RUNTIME_STOP_GRACE_SECONDS)
        try:
            process.close()
        except (OSError, ValueError):
            pass

    def _recover_isolated_runtime_locked(
        self,
        *,
        error_category: str = "inference_timeout",
        counts_as_timeout: bool = True,
    ) -> None:
        # A replaced worker cannot safely continue an incomplete animal candidate.
        # Rotate that bounded evidence immediately, before a late result can arrive.
        self._record_reset_for_all_streams_locked(self._runtime_generation + 1)
        self._stop_isolated_runtime_locked()
        self._runtime_recovery_count += 1
        self._runtime_worker_reset_count += 1
        if counts_as_timeout:
            self._runtime_consecutive_timeouts += 1
        else:
            self._runtime_consecutive_timeouts = 0
        backoff_exponent = max(0, self._runtime_consecutive_timeouts - 1)
        backoff = min(
            RUNTIME_RECOVERY_BACKOFF_SECONDS * 2**backoff_exponent,
            MAX_RUNTIME_RECOVERY_BACKOFF_SECONDS,
        )
        self._runtime_recovery_not_before = monotonic() + backoff
        self._runtime_state = "recovering"
        self._runtime_last_error_category = error_category
    def _wait_for_runtime_recovery(self) -> None:
        with self._condition:
            remaining = max(0.0, self._runtime_recovery_not_before - monotonic())
        if remaining:
            sleep(remaining)

    def _run_isolated_runtime(self, job: _InferenceJob, on_started: Callable[[], None]) -> list[MegaDetectorProposal]:
        with self._condition:
            self._ensure_isolated_runtime_locked()
            connection = self._runtime_connection
            generation = self._runtime_generation
            timeout_seconds = (
                INITIAL_RUNTIME_LOAD_TIMEOUT_SECONDS
                if not self._runtime_model_loaded
                else INFERENCE_TIMEOUT_SECONDS
            )
            self._runtime_state = (
                "loading" if not self._runtime_model_loaded else "running"
            )
        if connection is None:
            raise _RuntimeInferenceFailure("worker_unavailable")
        try:
            connection.send(job)
        except (BrokenPipeError, EOFError, OSError) as error:
            with self._condition:
                self._recover_isolated_runtime_locked(
                    error_category="worker_connection_failed", counts_as_timeout=False
                )
            raise _RuntimeInferenceFailure("worker_connection_failed") from error
        try:
            started = connection.poll(RUNTIME_WORKER_START_TIMEOUT_SECONDS)
        except (EOFError, OSError) as error:
            with self._condition:
                self._recover_isolated_runtime_locked(
                    error_category="worker_connection_failed", counts_as_timeout=False
                )
            raise _RuntimeInferenceFailure("worker_connection_failed") from error
        if not started:
            with self._condition:
                self._recover_isolated_runtime_locked(
                    error_category="worker_start_timeout", counts_as_timeout=False
                )
            raise _RuntimeInferenceFailure("worker_start_timeout")
        try:
            started_message = connection.recv()
        except (EOFError, OSError) as error:
            with self._condition:
                self._recover_isolated_runtime_locked(
                    error_category="worker_connection_failed", counts_as_timeout=False
                )
            raise _RuntimeInferenceFailure("worker_connection_failed") from error
        if started_message != ("started",):
            with self._condition:
                self._recover_isolated_runtime_locked(
                    error_category="worker_start_failed", counts_as_timeout=False
                )
            raise _RuntimeInferenceFailure("worker_start_failed")
        on_started()
        try:
            ready = connection.poll(timeout_seconds)
        except (EOFError, OSError) as error:
            with self._condition:
                self._recover_isolated_runtime_locked(
                    error_category="worker_connection_failed", counts_as_timeout=False
                )
            raise _RuntimeInferenceFailure("worker_connection_failed") from error
        if not ready:
            with self._condition:
                self._recover_isolated_runtime_locked()
            raise _RuntimeInferenceTimeout()
        try:
            result = connection.recv()
        except (EOFError, OSError) as error:
            with self._condition:
                self._recover_isolated_runtime_locked(
                    error_category="worker_connection_failed", counts_as_timeout=False
                )
            raise _RuntimeInferenceFailure("worker_connection_failed") from error
        if isinstance(result, tuple) and len(result) in {2, 3} and result[0] == "success":
            proposals = result[1]
            if isinstance(proposals, list):
                with self._condition:
                    if (
                        self._shutdown
                        or connection is not self._runtime_connection
                        or generation != self._runtime_generation
                    ):
                        raise _RuntimeInferenceFailure("stale_generation")
                    self._runtime_model_loaded = True
                    self._runtime_last_error_category = None
                    if len(result) == 3 and (result[2] is None or isinstance(result[2], str)):
                        self._runtime_execution_device = result[2]
                return proposals
        with self._condition:
            self._runtime_state = "unavailable"
            self._runtime_last_error_category = "megadetector_unavailable"
        raise _RuntimeInferenceFailure("megadetector_unavailable")

    def _run(self) -> None:
        while True:
            with self._condition:
                while not self._shutdown and not self._queue:
                    self._condition.wait()
                if self._shutdown:
                    return
                job = self._queue.popleft()
            if self._uses_isolated_runtime:
                self._wait_for_runtime_recovery()

            started_at: datetime | None = None

            def mark_started() -> None:
                nonlocal started_at
                with self._condition:
                    started_at = self._now()
                    self._active = (job, started_at)

            if not self._uses_isolated_runtime:
                mark_started()
            proposals: list[MegaDetectorProposal] | None = None
            failure: str | None = None
            try:
                if self._uses_isolated_runtime:
                    proposals = self._run_isolated_runtime(job, mark_started)
                else:
                    runner = self._runner
                    if runner is None:
                        raise _RuntimeInferenceFailure("worker_unavailable")
                    proposals = runner(
                        job.image,
                        MegaDetectorBox(
                            x=job.coordinate_box[0],
                            y=job.coordinate_box[1],
                            width=job.coordinate_box[2] - job.coordinate_box[0],
                            height=job.coordinate_box[3] - job.coordinate_box[1],
                        ),
                    )
            except _RuntimeInferenceTimeout:
                failure = "inference_timeout"
            except _RuntimeInferenceFailure:
                failure = "megadetector_unavailable"
            except Exception:
                failure = "megadetector_unavailable"
            completed_at = self._now()
            effective_started_at = started_at or completed_at
            latency_ms = max(0, int((completed_at - effective_started_at).total_seconds() * 1000))
            with self._condition:
                self._active = None
                if self._shutdown:
                    # Do not leave a late worker failure/result retaining the
                    # current crop after shutdown has already detached it.
                    return
                job_key = (job.stream_id, job.zone_id, job.sequence)
                if failure == "inference_timeout" or (
                    not self._uses_isolated_runtime
                    and latency_ms > int(INFERENCE_TIMEOUT_SECONDS * 1000)
                ):
                    if job_key not in self._expired_jobs:
                        self._expired_jobs.add(job_key)
                        self._timed_out_count += 1
                        self._stale_frame_count += 1
                    self._completed.append((job, None, latency_ms, "inference_timeout"))
                else:
                    self._completed.append((job, proposals, latency_ms, failure))
                self._runtime_last_completed_at = completed_at
                if failure is None and proposals is not None:
                    self._runtime_last_success_latency_ms = latency_ms
                    self._runtime_consecutive_timeouts = 0
                    self._runtime_state = "ready"
                    self._runtime_last_error_category = None


    def _drain_completed_locked(self, stream_id: str) -> None:
        remaining: deque[tuple[_InferenceJob, list[MegaDetectorProposal] | None, int, str | None]] = deque()
        while self._completed:
            job, proposals, latency_ms, failure = self._completed.popleft()
            if job.stream_id != stream_id:
                remaining.append((job, proposals, latency_ms, failure))
                continue
            state = self._states.setdefault(stream_id, _StreamState())
            job_key = (job.stream_id, job.zone_id, job.sequence)
            if job_key in self._expired_jobs:
                self._expired_jobs.discard(job_key)
                state.latest = ObjectDetectorSnapshot(
                    tracks=tuple(track.snapshot() for track in state.tracks.values()),
                    cadence_seconds=detector_interval_seconds(job.zone_type),
                    inference_latency_ms=latency_ms,
                    queue_depth=len(self._queue),
                    dropped_frame_count=self._dropped_frame_count,
                    stale_frame_count=self._stale_frame_count,
                    timed_out_count=self._timed_out_count,
                    unavailable_reason="inference_timeout",
                    completed_frame_identity=job.frame_identity,
                )
                continue
            if failure is not None or proposals is None:
                if failure == "stale_generation":
                    state.admission.increment("stale_generation_results_ignored")
                    self._record_admission_outcome_locked(
                        state,
                        "stale_generation_ignored",
                        frame_identities=(job.frame_identity,),
                    )
                state.latest = ObjectDetectorSnapshot(
                    tracks=tuple(track.snapshot() for track in state.tracks.values()),
                    cadence_seconds=detector_interval_seconds(job.zone_type),
                    inference_latency_ms=latency_ms,
                    queue_depth=len(self._queue),
                    dropped_frame_count=self._dropped_frame_count,
                    stale_frame_count=self._stale_frame_count,
                    timed_out_count=self._timed_out_count,
                    unavailable_reason=failure,
                    completed_frame_identity=job.frame_identity,
                )
                continue
            try:
                detections = tuple(_observations_for_job(job, proposals))
                state.admission.increment("inferences_completed")
                if any(item.label == "animal" for item in detections):
                    state.admission.increment("inferences_with_animal")
                else:
                    state.admission.increment("inferences_without_animal")
                    self._record_admission_outcome_locked(
                        state,
                        "no_animal_detection",
                        frame_identities=(job.frame_identity,),
                    )
                triggers = self._update_tracks(state, detections)
            except Exception:
                self._runtime_state = "unavailable"
                self._runtime_last_error_category = "result_processing_failed"
                state.latest = ObjectDetectorSnapshot(
                    tracks=tuple(track.snapshot() for track in state.tracks.values()),
                    cadence_seconds=detector_interval_seconds(job.zone_type),
                    inference_latency_ms=latency_ms,
                    queue_depth=len(self._queue),
                    dropped_frame_count=self._dropped_frame_count,
                    stale_frame_count=self._stale_frame_count,
                    timed_out_count=self._timed_out_count,
                    unavailable_reason="megadetector_unavailable",
                    completed_frame_identity=job.frame_identity,
                )
                continue
            state.latest = ObjectDetectorSnapshot(
                detections=detections,
                tracks=tuple(track.snapshot() for track in state.tracks.values()),
                triggers=tuple(triggers),
                cadence_seconds=detector_interval_seconds(job.zone_type),
                inference_latency_ms=latency_ms,
                queue_depth=len(self._queue),
                dropped_frame_count=self._dropped_frame_count,
                stale_frame_count=self._stale_frame_count,
                timed_out_count=self._timed_out_count,
                completed_frame_identity=job.frame_identity,
            )
        self._completed = remaining

    def _expire_active_locked(self, now: datetime) -> None:
        """Stop accepting a late result without trying to kill native inference.

        Python cannot safely terminate an in-flight optional runtime.  Once its
        bounded deadline passes, this method makes the result ineligible for
        tracking and keeps the one-slot queue from accumulating history.
        """

        if self._active is None:
            return
        job, started_at = self._active
        timeout_seconds = (
            INITIAL_RUNTIME_LOAD_TIMEOUT_SECONDS
            if self._uses_isolated_runtime and not self._runtime_model_loaded
            else INFERENCE_TIMEOUT_SECONDS
        )
        if now - started_at <= timedelta(seconds=timeout_seconds):
            return
        job_key = (job.stream_id, job.zone_id, job.sequence)
        if job_key not in self._expired_jobs:
            self._expired_jobs.add(job_key)
            self._timed_out_count += 1
            self._stale_frame_count += 1
            state = self._states.setdefault(job.stream_id, _StreamState())
            state.latest = ObjectDetectorSnapshot(
                tracks=tuple(track.snapshot() for track in state.tracks.values()),
                cadence_seconds=detector_interval_seconds(job.zone_type),
                inference_latency_ms=max(0, int((now - started_at).total_seconds() * 1000)),
                queue_depth=len(self._queue),
                dropped_frame_count=self._dropped_frame_count,
                stale_frame_count=self._stale_frame_count,
                timed_out_count=self._timed_out_count,
                unavailable_reason="inference_timeout",
                completed_frame_identity=job.frame_identity,
            )
            self._runtime_state = "timed_out"
            self._runtime_last_error_category = "inference_timeout"

    def _update_tracks(
        self, state: _StreamState, detections: tuple[ObjectDetection, ...]
    ) -> list[ObjectTrackTrigger]:
        unmatched = set(range(len(detections)))
        for track in tuple(state.tracks.values()):
            if track.state == "disappeared":
                continue
            match_index = _best_match(track, detections, unmatched)
            if match_index is None:
                if (
                    track.detection.label == "animal"
                    and not track.triggered
                    and track.hit_count == 1
                ):
                    for index in unmatched:
                        detection = detections[index]
                        if _is_spatially_incoherent(track, detection):
                            state.admission.increment("spatial_coherence_rejected")
                            self._record_admission_outcome_locked(
                                state,
                                "spatial_coherence_rejected",
                                detection=detection,
                                track=track,
                                frame_identities=(
                                    track.detection.frame_identity,
                                    detection.frame_identity,
                                ),
                                spatial_coherence=False,
                            )
                            break
                    state.admission.increment("single_frame_candidates_expired")
                    self._record_admission_outcome_locked(
                        state, "single_frame_candidate_expired", track=track
                    )
                    track._seen_frame_identities.clear()
                    track._seen_frame_order.clear()
                    track.state = "disappeared"
                else:
                    track.missed_count += 1
                    track.state = (
                        "stationary"
                        if track.triggered and track.missed_count <= MAX_TRACK_MISSES
                        else "disappeared"
                    )
                continue
            unmatched.remove(match_index)
            detection = detections[match_index]
            fresh_observation = track.observe(detection)
            if track.detection.label != "animal":
                continue
            if not fresh_observation:
                state.admission.increment("duplicate_frame_identities_ignored")
                self._record_admission_outcome_locked(
                    state,
                    "duplicate_frame_ignored",
                    detection=detection,
                    track=track,
                )
            elif track.hit_count == MIN_ANIMAL_ADMISSION_OBSERVATIONS:
                state.admission.increment("valid_second_distinct_frames")

        for index in sorted(unmatched):
            detection = detections[index]
            track_id = f"object-track-{state.next_track:04d}"
            state.next_track += 1
            track_generation_id = (
                f"{detection.zone_id}:object-generation-"
                f"{self._track_generation_epoch}-"
                f"{self._next_track_generation:08d}"
            )
            self._next_track_generation += 1
            track = _TrackState(
                track_id=track_id,
                track_generation_id=track_generation_id,
                detection=detection,
                first_seen_at=detection.captured_at,
                last_seen_at=detection.captured_at,
            )
            state.tracks[track_id] = track
            if detection.label == "animal":
                state.admission.increment("candidate_tracks_started")
                state.admission.increment("first_distinct_support_frames")
                self._record_admission_outcome_locked(
                    state, "first_distinct_frame_recorded", detection=detection, track=track
                )

        triggers: list[ObjectTrackTrigger] = []
        for track in state.tracks.values():
            if track.triggered or track.state != "active":
                continue
            detection = track.detection
            if detection.label == "animal":
                admission_ready = (
                    track.hit_count >= MIN_ANIMAL_ADMISSION_OBSERVATIONS
                )
            else:
                admission_ready = detection.score >= STRONG_OBJECT_SCORE or (
                    detection.score >= WEAK_OBJECT_SCORE and track.hit_count >= 2
                )
            if admission_ready:
                if detection.label == "animal":
                    state.admission.increment("admissions_satisfied")
                    self._record_admission_outcome_locked(
                        state,
                        "admission_satisfied",
                        detection=detection,
                        track=track,
                        spatial_coherence=True,
                    )
                track.triggered = True
                triggers.append(
                    ObjectTrackTrigger(
                        track_id=track.track_id,
                        track_generation_id=track.track_generation_id,
                        zone_id=detection.zone_id,
                        label=detection.label,
                        score=detection.score,
                        box=detection.box,
                        frame_identity=detection.frame_identity,
                        captured_at=detection.captured_at,
                    )
                )
        if len(state.tracks) > MAX_OBJECT_TRACKS_PER_STREAM:
            stale = sorted(state.tracks.values(), key=lambda item: item.last_seen_at)[
                : -MAX_OBJECT_TRACKS_PER_STREAM
            ]
            for track in stale:
                state.tracks.pop(track.track_id, None)
        return triggers

    def _snapshot_locked(
        self, state: _StreamState, *, zone_type: str | None = None
    ) -> ObjectDetectorSnapshot:
        latest = state.latest
        active = self._active
        in_flight_age_ms: int | None = None
        runtime_state = self._runtime_state
        if active is not None:
            active_job, started_at = active
            in_flight_age_ms = max(
                0, int((self._now() - started_at).total_seconds() * 1000)
            )
            timeout_seconds = (
                INITIAL_RUNTIME_LOAD_TIMEOUT_SECONDS
                if self._uses_isolated_runtime and not self._runtime_model_loaded
                else INFERENCE_TIMEOUT_SECONDS
            )
            if runtime_state not in {"recovering", "timed_out", "unavailable"}:
                runtime_state = (
                    "delayed"
                    if in_flight_age_ms >= int(timeout_seconds * 750)
                    else "loading" if not self._runtime_model_loaded else "running"
                )
        else:
            active_job = None
            if runtime_state in {"running", "delayed"}:
                runtime_state = "ready"
        process = self._runtime_process
        worker_alive = (
            process is not None and process.is_alive()
            if self._uses_isolated_runtime
            else self._worker.is_alive()
        )
        last_submitted_at = max(state.last_submitted_at.values(), default=None)
        last_completed_age_ms = None
        if self._runtime_last_completed_at is not None:
            last_completed_age_ms = max(
                0,
                int((self._now() - self._runtime_last_completed_at).total_seconds() * 1000),
            )
        return ObjectDetectorSnapshot(
            detections=latest.detections,
            tracks=latest.tracks,
            triggers=latest.triggers,
            cadence_seconds=(
                detector_interval_seconds(zone_type)
                if zone_type is not None
                else latest.cadence_seconds
            ),
            inference_latency_ms=latest.inference_latency_ms,
            queue_depth=len(self._queue),
            queue_capacity=MAX_PENDING_INFERENCE_JOBS,
            dropped_frame_count=self._dropped_frame_count,
            stale_frame_count=self._stale_frame_count,
            timed_out_count=self._timed_out_count,
            runtime_state=runtime_state,
            model_configuration_state=self._model_configuration_state,
            model_loaded=self._runtime_model_loaded,
            worker_alive=worker_alive,
            in_flight_job_identity=(
                active_job.frame_identity if active_job is not None else None
            ),
            in_flight_age_ms=in_flight_age_ms,
            last_submitted_at=last_submitted_at,
            last_completed_at=self._runtime_last_completed_at,
            last_completed_age_ms=last_completed_age_ms,
            latest_successful_inference_latency_ms=(
                self._runtime_last_success_latency_ms
            ),
            worker_reset_count=self._runtime_worker_reset_count,
            recovery_count=self._runtime_recovery_count,
            queue_replacement_count=self._queue_replacement_count,
            execution_device=self._runtime_execution_device,
            last_safe_error_category=self._runtime_last_error_category,
            runtime_generation=self._runtime_generation,
            unavailable_reason=latest.unavailable_reason,
            completed_frame_identity=latest.completed_frame_identity,
            admission_observability_available=not self._shutdown,
            admission_runtime_generation=state.admission.detector_generation,
            admission_counters=dict(state.admission.counters),
            current_admission_candidates=tuple(
                _admission_candidate_summary(track)
                for track in state.tracks.values()
                if track.detection.label == "animal"
                and not track.triggered
                and track.state == "active"
            )[:MAX_OBJECT_TRACKS_PER_STREAM],
            recent_admission_outcomes=tuple(
                outcome.as_dict() for outcome in state.admission.recent_outcomes
            ),
            last_admission_decision_at=state.admission.last_decision_at,
            last_successful_promotion_at=state.admission.last_successful_promotion_at,
        )


def _admission_candidate_summary(track: _TrackState) -> dict[str, object]:
    return {
        "track_generation_id": track.track_generation_id,
        "class": track.detection.label,
        "score": track.detection.score,
        "zone_id": track.detection.zone_id,
        "frame_identities": list(track.frame_identities),
        "distinct_support_frame_count": track.hit_count,
        "left": track.detection.left,
        "top": track.detection.top,
        "right": track.detection.right,
        "bottom": track.detection.bottom,
    }


def _safe_admission_diagnostic(value: str | None) -> str | None:
    if not value:
        return None
    sanitized = "".join(
        character if character.isalnum() or character in {"_", "-", ":"} else "_"
        for character in value
    )
    return sanitized[:MAX_ADMISSION_DIAGNOSTIC_LENGTH]


def _observations_for_job(
    job: _InferenceJob, proposals: list[MegaDetectorProposal]
) -> list[ObjectDetection]:
    observations: list[ObjectDetection] = []
    allowed_labels = _allowed_labels_for_zone(job.zone_type)
    for proposal in proposals:
        if proposal.label not in allowed_labels or proposal.bbox is None:
            continue
        box = proposal.bbox
        observations.append(
            ObjectDetection(
                label=proposal.label,  # type: ignore[arg-type]
                score=proposal.confidence,
                left=box.x,
                top=box.y,
                right=box.x + box.width,
                bottom=box.y + box.height,
                zone_id=job.zone_id,
                frame_identity=job.frame_identity,
                captured_at=job.captured_at,
            )
        )
    return observations


def _allowed_labels_for_zone(zone_type: str) -> set[str]:
    """Keep primary wildlife Zones animal-led without hiding outdoor context."""

    if zone_type in {"feeder", "perch", "birdbath"}:
        return {"animal"}
    if zone_type == "driveway":
        return OBJECT_LABELS
    if zone_type in {"yard", "ground"}:
        return {"animal", "person"}
    if zone_type == "whole_stream":
        return OBJECT_LABELS
    return {"animal"}


def _best_match(
    track: _TrackState,
    detections: tuple[ObjectDetection, ...],
    unmatched: set[int],
) -> int | None:
    candidates: list[tuple[float, int]] = []
    for index in unmatched:
        detection = detections[index]
        current = track.detection
        if detection.zone_id != current.zone_id or detection.label != current.label:
            continue
        overlap, distance = _spatial_match_metrics(current, detection)
        if overlap < 0.10 and distance > 0.12:
            continue
        candidates.append((overlap - distance, index))
    return max(candidates, default=(0.0, None))[1]


def _is_spatially_incoherent(track: _TrackState, detection: ObjectDetection) -> bool:
    current = track.detection
    if (
        current.label != "animal"
        or detection.label != "animal"
        or current.zone_id != detection.zone_id
        or detection.frame_identity == current.frame_identity
    ):
        return False
    overlap, distance = _spatial_match_metrics(current, detection)
    return overlap < 0.10 and distance > 0.12


def _spatial_match_metrics(
    current: ObjectDetection, detection: ObjectDetection
) -> tuple[float, float]:
    return (
        _iou(current.box, detection.box),
        hypot(
            (current.left + current.right) / 2 - (detection.left + detection.right) / 2,
            (current.top + current.bottom) / 2 - (detection.top + detection.bottom) / 2,
        ),
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


def detector_provenance() -> dict[str, str]:
    """Return only static approved-model provenance for observational evidence."""

    return {"provider": "megadetector", **megadetector_model_provenance()}
