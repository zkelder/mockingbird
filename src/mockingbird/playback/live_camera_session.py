"""Backend-owned live camera sessions for MockingBird-served streams."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha1
import re
import subprocess
import threading
import time
from collections import deque
from collections.abc import Callable, Mapping
from typing import Any

from mockingbird.playback import (
    live_frame_cache,
    local_camera_bridge,
    rtsp_bridge,
    windows_camera_bridge,
)

MJPEG_BOUNDARY = "frame"
DEFAULT_MAX_RUNTIME_SECONDS = 30 * 60
DEFAULT_AUTO_REVIEW_QUIET_SECONDS = 30
DEFAULT_AUTO_REVIEW_MIN_DETECTIONS = 1
DEFAULT_ACTIVITY_MAX_CANDIDATE_FRAMES = 30
# A completed visit keeps a deliberately small sample rather than a recording.
# The selector accepts a lower caller-configured limit, but never exceeds this cap.
DEFAULT_ACTIVITY_MAX_VISIT_EVIDENCE_FRAMES = 4
DEFAULT_ACTIVITY_MAX_SAVED_CANDIDATES = DEFAULT_ACTIVITY_MAX_VISIT_EVIDENCE_FRAMES
DEFAULT_ACTIVITY_MAX_SESSION_SECONDS = 5 * 60
DEFAULT_MAX_DIAGNOSTIC_EVENTS = 100
SUPPORTED_SESSION_TYPES = {
    "rtsp",
    local_camera_bridge.LOCAL_USB_STREAM_TYPE,
    windows_camera_bridge.WINDOWS_DSHOW_STREAM_TYPE,
}

_DIAGNOSTIC_EVENT_TYPES = {
    "activity_confirmed",
    "activity_ready_for_review",
    "activity_started",
    "auto_review_failed",
    "best_frame_saved",
    "camera_failed",
    "camera_started",
    "camera_stopped",
    "monitor_settings_changed",
    "monitor_started",
    "monitor_stopped",
    "motion_status_changed",
    "near_miss_started",
    "quality_warning",
    "review_candidate_created",
}
_DIAGNOSTIC_TOKEN_PATTERN = re.compile(r"^[a-z0-9_]{1,80}$")


@dataclass(frozen=True)
class LiveCameraDiagnosticEvent:
    """Bounded, metadata-only transition evidence for field validation."""

    sequence: int
    recorded_at: datetime
    event_type: str
    status: str | None = None
    reason: str | None = None
    activity_session_id: str | None = None
    frame_count: int = 0
    detection_count: int = 0
    near_miss_count: int = 0
    candidate_frame_count: int = 0
    quality_warning_codes: tuple[str, ...] = ()
    creates_truth: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "sequence": self.sequence,
            "recorded_at": self.recorded_at,
            "event_type": self.event_type,
            "status": self.status,
            "reason": self.reason,
            "activity_session_id": self.activity_session_id,
            "frame_count": self.frame_count,
            "detection_count": self.detection_count,
            "near_miss_count": self.near_miss_count,
            "candidate_frame_count": self.candidate_frame_count,
            "quality_warning_codes": list(self.quality_warning_codes),
            "creates_truth": self.creates_truth,
        }


@dataclass(frozen=True)
class LiveCameraSessionSnapshot:
    stream_id: str
    source_id: str | None
    playback_kind: str | None
    status: str
    started_at: datetime | None
    last_frame_at: datetime | None
    frame_count: int
    clients_connected: int
    monitor_running: bool
    auto_create_review_candidates: bool
    auto_review_quiet_seconds: int
    auto_review_min_detections: int
    auto_review_created_count: int
    last_auto_review_created_at: datetime | None
    auto_review_last_error: str | None
    last_auto_review_motion_evidence_id: str | None
    last_auto_review_event_id: str | None
    last_auto_review_visit_id: str | None
    last_auto_review_queue_item_id: str | None
    last_motion_evaluation_at: datetime | None
    current_activity_session: dict[str, Any] | None
    open_activity_session_count: int
    open_activity_zone_names: list[str]
    ready_activity_session_count: int
    latest_activity_review_queue_item_id: str | None
    last_activity: dict[str, Any] | None
    last_motion_result: dict[str, Any] | None
    last_error: str | None
    stop_reason: str | None
    max_runtime_seconds: int
    camera_settings: dict[str, Any]
    diagnostic_events: list[dict[str, Any]]
    diagnostic_events_truncated: bool
    persistent: bool = False

    @property
    def latest_frame_age_ms(self) -> int | None:
        if self.last_frame_at is None:
            return None
        return max(
            0,
            int((datetime.now(UTC) - self.last_frame_at).total_seconds() * 1000),
        )


@dataclass(frozen=True)
class LiveActivitySessionSnapshot:
    # Live activity sessions group repeated hits before review creates product evidence.
    activity_session_id: str
    stream_id: str
    source_id: str | None
    region_key: str
    region_kind: str
    region_id: str | None
    zone_id: str | None
    zone_name: str | None
    zone_type: str | None
    started_at: datetime
    last_seen_at: datetime
    detection_count: int
    near_miss_count: int
    frames_evaluated_count: int
    candidate_frame_count: int
    saved_candidate_count: int
    completed_at: datetime | None
    ready_for_review: bool
    review_state: str
    start_frame_sequence: int | None
    end_frame_sequence: int | None
    best_frame_sequence: int | None
    best_frame_captured_at: datetime | None
    best_frame_content_type: str | None
    best_frame_size_bytes: int | None
    best_frame_width: int | None
    best_frame_height: int | None
    activity_left: float | None
    activity_top: float | None
    activity_right: float | None
    activity_bottom: float | None
    activity_changed_pixel_count: int | None
    best_media_asset_id: str | None
    best_score: float | None
    best_changed_ratio: float | None
    best_changed_pixels: int | None
    best_total_scored_pixels: int | None
    current_changed_ratio: float | None
    current_changed_pixels: int | None
    current_total_scored_pixels: int | None
    effective_threshold_used: float | None
    threshold_source: str | None
    fine_motion_applied: bool
    image_quality_warnings: list[str]
    near_miss: bool
    margin_to_threshold: float | None
    review_activity_created: bool
    motion_evidence_id: str | None
    event_id: str | None
    visit_id: str | None
    review_queue_item_id: str | None
    suggested_label: str | None
    suggestion_id: str | None
    suggestion_confidence: float | None
    session_duration_seconds: float
    manual_review_needed: bool
    notification_event: str | None
    creates_truth: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "activity_session_id": self.activity_session_id,
            "stream_id": self.stream_id,
            "source_id": self.source_id,
            "region_key": self.region_key,
            "region_kind": self.region_kind,
            "region_id": self.region_id,
            "zone_id": self.zone_id,
            "zone_name": self.zone_name,
            "zone_type": self.zone_type,
            "started_at": self.started_at,
            "last_seen_at": self.last_seen_at,
            "detection_count": self.detection_count,
            "near_miss_count": self.near_miss_count,
            "frames_evaluated_count": self.frames_evaluated_count,
            "candidate_frame_count": self.candidate_frame_count,
            "saved_candidate_count": self.saved_candidate_count,
            "completed_at": self.completed_at,
            "ready_for_review": self.ready_for_review,
            "review_state": self.review_state,
            "start_frame_sequence": self.start_frame_sequence,
            "end_frame_sequence": self.end_frame_sequence,
            "best_frame_sequence": self.best_frame_sequence,
            "best_frame_captured_at": self.best_frame_captured_at,
            "best_frame_content_type": self.best_frame_content_type,
            "best_frame_size_bytes": self.best_frame_size_bytes,
            "best_frame_width": self.best_frame_width,
            "best_frame_height": self.best_frame_height,
            "activity_left": self.activity_left,
            "activity_top": self.activity_top,
            "activity_right": self.activity_right,
            "activity_bottom": self.activity_bottom,
            "activity_changed_pixel_count": self.activity_changed_pixel_count,
            "best_media_asset_id": self.best_media_asset_id,
            "best_score": self.best_score,
            "best_changed_ratio": self.best_changed_ratio,
            "best_changed_pixels": self.best_changed_pixels,
            "best_total_scored_pixels": self.best_total_scored_pixels,
            "current_changed_ratio": self.current_changed_ratio,
            "current_changed_pixels": self.current_changed_pixels,
            "current_total_scored_pixels": self.current_total_scored_pixels,
            "effective_threshold_used": self.effective_threshold_used,
            "threshold_source": self.threshold_source,
            "fine_motion_applied": self.fine_motion_applied,
            "image_quality_warnings": list(self.image_quality_warnings),
            "near_miss": self.near_miss,
            "margin_to_threshold": self.margin_to_threshold,
            "review_activity_created": self.review_activity_created,
            "motion_evidence_id": self.motion_evidence_id,
            "event_id": self.event_id,
            "visit_id": self.visit_id,
            "review_queue_item_id": self.review_queue_item_id,
            "suggested_label": self.suggested_label,
            "suggestion_id": self.suggestion_id,
            "suggestion_confidence": self.suggestion_confidence,
            "session_duration_seconds": self.session_duration_seconds,
            "manual_review_needed": self.manual_review_needed,
            "notification_event": self.notification_event,
            "creates_truth": self.creates_truth,
        }


@dataclass(frozen=True)
class LiveActivityBestFrame:
    activity_session_id: str
    frame_bytes: bytes | None
    content_type: str | None
    captured_at: datetime | None
    sequence: int | None


@dataclass(frozen=True)
class LiveActivityEvidenceFrame:
    """One bounded, in-memory frame selected for a completed activity Visit."""

    activity_session_id: str
    frame_key: str
    media_asset_id: str | None
    sequence: int | None
    captured_at: datetime
    frame_bytes: bytes
    content_type: str | None
    width: int | None
    height: int | None
    is_primary: bool


@dataclass(frozen=True)
class _LiveActivityCandidateFrame:
    sequence: int | None
    captured_at: datetime
    score: float | None
    changed_ratio: float | None
    changed_pixels: int | None
    total_scored_pixels: int | None
    near_miss: bool
    activity_detected: bool
    frame_bytes: bytes | None
    content_type: str | None
    width: int | None
    height: int | None


class LiveCameraSessionManager:
    """Owns bounded in-memory camera reader sessions started by the user."""

    def __init__(
        self,
        *,
        max_runtime_seconds: int = DEFAULT_MAX_RUNTIME_SECONDS,
        poll_interval_seconds: float = 0.1,
    ) -> None:
        self.max_runtime_seconds = max_runtime_seconds
        self.poll_interval_seconds = poll_interval_seconds
        self._sessions: dict[str, _LiveCameraSession] = {}
        self._lock = threading.RLock()

    def start(
        self,
        config: Any,
        *,
        max_runtime_seconds: int | None = None,
    ) -> LiveCameraSessionSnapshot:
        runtime_limit = max_runtime_seconds or self.max_runtime_seconds
        with self._lock:
            existing = self._sessions.get(config.stream_id)
            if existing is not None and existing.is_active:
                return existing.snapshot()
            if existing is not None:
                existing.stop("replaced")

            process = _start_process(config)
            session = _LiveCameraSession(
                config=config,
                process=process,
                max_runtime_seconds=runtime_limit,
            )
            self._sessions[config.stream_id] = session
            session.start()
            return session.snapshot()

    def stop(self, stream_id: str, *, reason: str = "user_stopped") -> LiveCameraSessionSnapshot | None:
        with self._lock:
            session = self._sessions.get(stream_id)
        if session is None:
            return None
        session.stop(reason)
        return session.snapshot()

    def status(self, stream_id: str) -> LiveCameraSessionSnapshot | None:
        with self._lock:
            session = self._sessions.get(stream_id)
        return session.snapshot() if session is not None else None

    def get_latest_frame_for_capture(
        self,
        stream_id: str,
        *,
        max_age_seconds: float = live_frame_cache.DEFAULT_MAX_AGE_SECONDS,
    ) -> live_frame_cache.LiveFrame | None:
        with self._lock:
            session = self._sessions.get(stream_id)
        if session is None or not session.is_active:
            return None
        return live_frame_cache.get_latest_frame(
            stream_id,
            max_age_seconds=max_age_seconds,
        )

    def capture_latest_frame(
        self,
        stream_id: str,
        *,
        max_age_seconds: float = live_frame_cache.DEFAULT_MAX_AGE_SECONDS,
    ) -> live_frame_cache.LiveFrame | None:
        return self.get_latest_frame_for_capture(
            stream_id,
            max_age_seconds=max_age_seconds,
        )

    def start_monitor(
        self,
        stream_id: str,
        evaluate: Callable[[], Mapping[str, Any]],
        *,
        interval_seconds: float,
        auto_create_review_candidates: bool = False,
        auto_review_quiet_seconds: int = DEFAULT_AUTO_REVIEW_QUIET_SECONDS,
        auto_review_min_detections: int = DEFAULT_AUTO_REVIEW_MIN_DETECTIONS,
    ) -> LiveCameraSessionSnapshot | None:
        with self._lock:
            session = self._sessions.get(stream_id)
        if session is None:
            return None
        session.start_monitor(
            evaluate,
            interval_seconds=interval_seconds,
            auto_create_review_candidates=auto_create_review_candidates,
            auto_review_quiet_seconds=auto_review_quiet_seconds,
            auto_review_min_detections=auto_review_min_detections,
        )
        return session.snapshot()

    def stop_monitor(self, stream_id: str) -> LiveCameraSessionSnapshot | None:
        with self._lock:
            session = self._sessions.get(stream_id)
        if session is None:
            return None
        session.stop_monitor()
        return session.snapshot()

    def update_monitor_settings(
        self,
        stream_id: str,
        *,
        auto_create_review_candidates: bool,
        auto_review_quiet_seconds: int = DEFAULT_AUTO_REVIEW_QUIET_SECONDS,
        auto_review_min_detections: int = DEFAULT_AUTO_REVIEW_MIN_DETECTIONS,
    ) -> LiveCameraSessionSnapshot | None:
        with self._lock:
            session = self._sessions.get(stream_id)
        if session is None:
            return None
        session.update_monitor_settings(
            auto_create_review_candidates=auto_create_review_candidates,
            auto_review_quiet_seconds=auto_review_quiet_seconds,
            auto_review_min_detections=auto_review_min_detections,
        )
        return session.snapshot()

    def record_motion_result(
        self,
        stream_id: str,
        result: Mapping[str, Any],
        *,
        last_activity: Mapping[str, Any] | None = None,
    ) -> LiveCameraSessionSnapshot | None:
        with self._lock:
            session = self._sessions.get(stream_id)
        if session is None:
            return None
        session.record_motion_result(result, last_activity=last_activity)
        return session.snapshot()

    def record_activity_detection(
        self,
        stream_id: str,
        values: Mapping[str, Any],
        *,
        frame_bytes: bytes | None,
        frame_content_type: str | None,
        quiet_window_seconds: int,
    ) -> LiveActivitySessionSnapshot | None:
        with self._lock:
            session = self._sessions.get(stream_id)
        if session is None:
            return None
        return session.record_activity_detection(
            values,
            frame_bytes=frame_bytes,
            frame_content_type=frame_content_type,
            quiet_window_seconds=quiet_window_seconds,
        )

    def get_activity_session(
        self,
        stream_id: str,
        activity_session_id: str | None = None,
    ) -> LiveActivitySessionSnapshot | None:
        with self._lock:
            session = self._sessions.get(stream_id)
        if session is None:
            return None
        return session.get_activity_session(activity_session_id)

    def get_activity_best_frame(
        self,
        stream_id: str,
        activity_session_id: str | None = None,
    ) -> LiveActivityBestFrame | None:
        with self._lock:
            session = self._sessions.get(stream_id)
        if session is None:
            return None
        return session.get_activity_best_frame(activity_session_id)

    def get_activity_evidence_frames(
        self,
        stream_id: str,
        activity_session_id: str,
        *,
        max_frames: int = DEFAULT_ACTIVITY_MAX_VISIT_EVIDENCE_FRAMES,
    ) -> list[LiveActivityEvidenceFrame]:
        with self._lock:
            session = self._sessions.get(stream_id)
        if session is None:
            return []
        return session.get_activity_evidence_frames(
            activity_session_id,
            max_frames=max_frames,
        )

    def mark_activity_media_asset(
        self,
        stream_id: str,
        activity_session_id: str,
        media_asset_id: str,
    ) -> LiveActivitySessionSnapshot | None:
        with self._lock:
            session = self._sessions.get(stream_id)
        if session is None:
            return None
        return session.mark_activity_media_asset(activity_session_id, media_asset_id)

    def mark_activity_evidence_media_asset(
        self,
        stream_id: str,
        activity_session_id: str,
        frame_key: str,
        media_asset_id: str,
    ) -> LiveActivitySessionSnapshot | None:
        with self._lock:
            session = self._sessions.get(stream_id)
        if session is None:
            return None
        return session.mark_activity_evidence_media_asset(
            activity_session_id,
            frame_key,
            media_asset_id,
        )

    def mark_activity_review_created(
        self,
        stream_id: str,
        activity_session_id: str,
        values: Mapping[str, Any],
    ) -> LiveActivitySessionSnapshot | None:
        with self._lock:
            session = self._sessions.get(stream_id)
        if session is None:
            return None
        return session.mark_activity_review_created(activity_session_id, values)

    def mark_activity_ready_for_review(
        self,
        stream_id: str,
        activity_session_id: str,
        *,
        quiet_seconds: int,
    ) -> LiveActivitySessionSnapshot | None:
        with self._lock:
            session = self._sessions.get(stream_id)
        if session is None:
            return None
        return session.mark_activity_ready_for_review(
            activity_session_id,
            quiet_seconds=quiet_seconds,
        )

    def mark_quiet_activity_sessions_ready_for_review(
        self,
        stream_id: str,
        *,
        quiet_seconds: int,
    ) -> list[LiveActivitySessionSnapshot]:
        """Close elapsed zone sessions during a monitor tick, never a status read."""

        with self._lock:
            session = self._sessions.get(stream_id)
        if session is None:
            return []
        return session.mark_quiet_activity_sessions_ready_for_review(
            quiet_seconds=quiet_seconds,
        )

    def record_auto_review_created(
        self,
        stream_id: str,
        values: Mapping[str, Any],
    ) -> LiveCameraSessionSnapshot | None:
        with self._lock:
            session = self._sessions.get(stream_id)
        if session is None:
            return None
        session.record_auto_review_created(values)
        return session.snapshot()

    def record_auto_review_error(
        self,
        stream_id: str,
        error: str | None,
    ) -> LiveCameraSessionSnapshot | None:
        with self._lock:
            session = self._sessions.get(stream_id)
        if session is None:
            return None
        session.record_auto_review_error(error)
        return session.snapshot()

    def update_last_activity(
        self,
        stream_id: str,
        values: Mapping[str, Any],
    ) -> LiveCameraSessionSnapshot | None:
        with self._lock:
            session = self._sessions.get(stream_id)
        if session is None:
            return None
        session.update_last_activity(values)
        return session.snapshot()

    def iter_mjpeg(self, stream_id: str, *, boundary: str = MJPEG_BOUNDARY):
        with self._lock:
            session = self._sessions.get(stream_id)
        if session is None:
            return

        session.increment_clients()
        last_sequence: int | None = None
        try:
            while session.is_active:
                frame = live_frame_cache.get_latest_frame(
                    stream_id,
                    max_age_seconds=live_frame_cache.DEFAULT_RECENT_MAX_AGE_SECONDS,
                )
                if frame is not None and frame.sequence != last_sequence:
                    last_sequence = frame.sequence
                    yield _multipart_frame(frame.frame_bytes, boundary=boundary)
                    continue
                time.sleep(self.poll_interval_seconds)
        finally:
            session.decrement_clients()

    def stop_all(self, *, reason: str = "api_shutdown") -> None:
        with self._lock:
            sessions = list(self._sessions.values())
        for session in sessions:
            session.stop(reason)


class _LiveCameraSession:
    def __init__(
        self,
        *,
        config: Any,
        process: subprocess.Popen[bytes],
        max_runtime_seconds: int,
    ) -> None:
        self.stream_id = config.stream_id
        self.source_id = config.source_id
        self.playback_kind = config.live_stream_type
        self.process = process
        self.max_runtime_seconds = max_runtime_seconds
        self.started_at = datetime.now(UTC)
        self.last_frame_at: datetime | None = None
        self.frame_count = 0
        self.clients_connected = 0
        self.monitor_running = False
        self.auto_create_review_candidates = False
        self.auto_review_quiet_seconds = DEFAULT_AUTO_REVIEW_QUIET_SECONDS
        self.auto_review_min_detections = DEFAULT_AUTO_REVIEW_MIN_DETECTIONS
        self.auto_review_created_count = 0
        self.last_auto_review_created_at: datetime | None = None
        self.auto_review_last_error: str | None = None
        self.last_auto_review_motion_evidence_id: str | None = None
        self.last_auto_review_event_id: str | None = None
        self.last_auto_review_visit_id: str | None = None
        self.last_auto_review_queue_item_id: str | None = None
        self.last_motion_evaluation_at: datetime | None = None
        self.last_activity: dict[str, Any] | None = None
        self.last_motion_result: dict[str, Any] | None = None
        self.current_activity_session_id: str | None = None
        self.activity_sessions: dict[str, _LiveActivitySession] = {}
        self.last_error: str | None = None
        self.stop_reason: str | None = None
        self.camera_settings = _camera_settings_from_config(config)
        self.status = "starting"
        self.diagnostic_events: deque[LiveCameraDiagnosticEvent] = deque(
            maxlen=DEFAULT_MAX_DIAGNOSTIC_EVENTS
        )
        self._diagnostic_sequence = 0
        self._last_motion_diagnostic_status: tuple[str | None, str | None] | None = None
        self._last_quality_warning_codes: tuple[str, ...] = ()
        self._stop_event = threading.Event()
        self._monitor_stop_event = threading.Event()
        self._monitor_thread: threading.Thread | None = None
        self._lock = threading.RLock()
        self._thread = threading.Thread(
            target=self._reader_loop,
            name=f"mockingbird-live-camera-{self.stream_id}",
            daemon=True,
        )

    @property
    def is_active(self) -> bool:
        with self._lock:
            return self.status in {"starting", "running"}

    def start(self) -> None:
        with self._lock:
            self.status = "running"
            self._record_diagnostic_event_locked(
                "camera_started",
                status=self.status,
            )
        self._thread.start()

    def stop(self, reason: str) -> None:
        with self._lock:
            if self.status in {"stopped", "failed"}:
                if self.stop_reason is None:
                    self.stop_reason = reason
                return
            monitor_was_running = self.monitor_running
            self.status = "stopping"
            self.stop_reason = reason
            self.monitor_running = False
            if monitor_was_running:
                self._record_diagnostic_event_locked(
                    "monitor_stopped",
                    status="stopped",
                    reason="camera_stopping",
                )
        self._stop_event.set()
        self._monitor_stop_event.set()
        _stop_process(self.process)
        monitor_thread = self._monitor_thread
        if monitor_thread is not None and monitor_thread.is_alive():
            monitor_thread.join(timeout=2)
        if self._thread.is_alive() and threading.current_thread() is not self._thread:
            self._thread.join(timeout=2)
        with self._lock:
            if self.status == "stopping":
                self.status = "stopped"
            self._record_diagnostic_event_locked(
                "camera_stopped",
                status=self.status,
                reason=reason,
            )

    def start_monitor(
        self,
        evaluate: Callable[[], Mapping[str, Any]],
        *,
        interval_seconds: float,
        auto_create_review_candidates: bool = False,
        auto_review_quiet_seconds: int = DEFAULT_AUTO_REVIEW_QUIET_SECONDS,
        auto_review_min_detections: int = DEFAULT_AUTO_REVIEW_MIN_DETECTIONS,
    ) -> None:
        with self._lock:
            if self.status not in {"starting", "running"}:
                raise ValueError("camera_session_not_running")
            self.auto_create_review_candidates = bool(auto_create_review_candidates)
            self.auto_review_quiet_seconds = max(1, int(auto_review_quiet_seconds))
            self.auto_review_min_detections = max(1, int(auto_review_min_detections))
            self.auto_review_last_error = None
            if self.monitor_running:
                return
            self.monitor_running = True
            self._record_diagnostic_event_locked(
                "monitor_started",
                status="running",
            )
            self._monitor_stop_event.clear()
            self._monitor_thread = threading.Thread(
                target=self._monitor_loop,
                args=(evaluate, interval_seconds),
                name=f"mockingbird-live-monitor-{self.stream_id}",
                daemon=True,
            )
            self._monitor_thread.start()

    def update_monitor_settings(
        self,
        *,
        auto_create_review_candidates: bool,
        auto_review_quiet_seconds: int = DEFAULT_AUTO_REVIEW_QUIET_SECONDS,
        auto_review_min_detections: int = DEFAULT_AUTO_REVIEW_MIN_DETECTIONS,
    ) -> None:
        with self._lock:
            previous_settings = (
                self.auto_create_review_candidates,
                self.auto_review_quiet_seconds,
                self.auto_review_min_detections,
            )
            self.auto_create_review_candidates = bool(auto_create_review_candidates)
            self.auto_review_quiet_seconds = max(1, int(auto_review_quiet_seconds))
            self.auto_review_min_detections = max(1, int(auto_review_min_detections))
            self.auto_review_last_error = None
            current_settings = (
                self.auto_create_review_candidates,
                self.auto_review_quiet_seconds,
                self.auto_review_min_detections,
            )
            if current_settings != previous_settings:
                self._record_diagnostic_event_locked(
                    "monitor_settings_changed",
                    status="running" if self.monitor_running else "stopped",
                )

    def stop_monitor(self) -> None:
        with self._lock:
            monitor_was_running = self.monitor_running
            self.monitor_running = False
            if monitor_was_running:
                self._record_diagnostic_event_locked(
                    "monitor_stopped",
                    status="stopped",
                    reason="user_stopped",
                )
        self._monitor_stop_event.set()
        monitor_thread = self._monitor_thread
        if (
            monitor_thread is not None
            and monitor_thread.is_alive()
            and threading.current_thread() is not monitor_thread
        ):
            monitor_thread.join(timeout=2)

    def record_motion_result(
        self,
        result: Mapping[str, Any],
        *,
        last_activity: Mapping[str, Any] | None = None,
    ) -> None:
        with self._lock:
            self.last_motion_result = dict(result)
            evaluated_at = result.get("evaluated_at")
            self.last_motion_evaluation_at = (
                evaluated_at if isinstance(evaluated_at, datetime) else datetime.now(UTC)
            )
            if last_activity is not None:
                self.last_activity = dict(last_activity)
            status = _safe_diagnostic_token(result.get("status"))
            reason = _safe_diagnostic_token(result.get("session_status"))
            motion_state = (status, reason)
            if motion_state != self._last_motion_diagnostic_status:
                self._last_motion_diagnostic_status = motion_state
                self._record_diagnostic_event_locked(
                    "motion_status_changed",
                    status=status,
                    reason=reason,
                )
            self._record_quality_warning_transition_locked(
                result.get("image_quality_warnings")
            )

    def update_last_activity(self, values: Mapping[str, Any]) -> None:
        with self._lock:
            activity = dict(self.last_activity or {})
            activity.update(values)
            self.last_activity = activity

    def record_activity_detection(
        self,
        values: Mapping[str, Any],
        *,
        frame_bytes: bytes | None,
        frame_content_type: str | None,
        quiet_window_seconds: int,
    ) -> LiveActivitySessionSnapshot:
        with self._lock:
            now = _coerce_datetime(values.get("last_seen_at")) or datetime.now(UTC)
            region_key = str(values.get("region_key") or "unknown-region")
            existing = self.activity_sessions.get(region_key)
            starts_new_session = (
                existing is None
                or (now - existing.last_seen_at).total_seconds() > quiet_window_seconds
                or (now - existing.started_at).total_seconds()
                > DEFAULT_ACTIVITY_MAX_SESSION_SECONDS
            )
            previous_detection_count = existing.detection_count if existing is not None else 0
            previous_near_miss_count = existing.near_miss_count if existing is not None else 0
            if starts_new_session:
                existing = _LiveActivitySession.from_detection(
                    values,
                    stream_id=self.stream_id,
                    source_id=self.source_id,
                    region_key=region_key,
                    now=now,
                    frame_bytes=frame_bytes,
                    frame_content_type=frame_content_type,
                )
                self.activity_sessions[region_key] = existing
            else:
                existing.record_detection(
                    values,
                    now=now,
                    frame_bytes=frame_bytes,
                    frame_content_type=frame_content_type,
                )
            snapshot = existing.snapshot()
            self.current_activity_session_id = snapshot.activity_session_id
            self.last_activity = snapshot.as_dict()
            if starts_new_session:
                self._record_diagnostic_event_locked(
                    "activity_started"
                    if snapshot.detection_count > 0
                    else "near_miss_started",
                    status=snapshot.review_state,
                    activity=snapshot,
                )
            elif previous_detection_count == 0 and snapshot.detection_count > 0:
                self._record_diagnostic_event_locked(
                    "activity_confirmed",
                    status=snapshot.review_state,
                    activity=snapshot,
                )
            elif (
                previous_near_miss_count == 0
                and snapshot.near_miss_count > 0
                and snapshot.detection_count == 0
            ):
                self._record_diagnostic_event_locked(
                    "near_miss_started",
                    status=snapshot.review_state,
                    activity=snapshot,
                )
            self._record_quality_warning_transition_locked(
                snapshot.image_quality_warnings,
                activity=snapshot,
            )
            return snapshot

    def get_activity_session(
        self,
        activity_session_id: str | None = None,
    ) -> LiveActivitySessionSnapshot | None:
        with self._lock:
            activity = self._activity_session(activity_session_id)
            return activity.snapshot() if activity is not None else None

    def get_activity_best_frame(
        self,
        activity_session_id: str | None = None,
    ) -> LiveActivityBestFrame | None:
        with self._lock:
            activity = self._activity_session(activity_session_id)
            if activity is None:
                return None
            return LiveActivityBestFrame(
                activity_session_id=activity.activity_session_id,
                frame_bytes=activity.best_frame_bytes,
                content_type=activity.best_frame_content_type,
                captured_at=activity.best_frame_captured_at,
                sequence=activity.best_frame_sequence,
            )

    def get_activity_evidence_frames(
        self,
        activity_session_id: str,
        *,
        max_frames: int,
    ) -> list[LiveActivityEvidenceFrame]:
        with self._lock:
            activity = self._activity_session(activity_session_id)
            if activity is None:
                return []
            return activity.evidence_frames(max_frames=max_frames)

    def mark_activity_media_asset(
        self,
        activity_session_id: str,
        media_asset_id: str,
    ) -> LiveActivitySessionSnapshot | None:
        with self._lock:
            activity = self._activity_session(activity_session_id)
            if activity is None:
                return None
            already_saved = activity.best_media_asset_id is not None
            activity.best_media_asset_id = media_asset_id
            activity.saved_candidate_count = min(
                DEFAULT_ACTIVITY_MAX_SAVED_CANDIDATES,
                max(activity.saved_candidate_count, 1),
            )
            snapshot = activity.snapshot()
            self.last_activity = snapshot.as_dict()
            if not already_saved:
                self._record_diagnostic_event_locked(
                    "best_frame_saved",
                    status=snapshot.review_state,
                    activity=snapshot,
                )
            return snapshot

    def mark_activity_evidence_media_asset(
        self,
        activity_session_id: str,
        frame_key: str,
        media_asset_id: str,
    ) -> LiveActivitySessionSnapshot | None:
        with self._lock:
            activity = self._activity_session(activity_session_id)
            if activity is None:
                return None
            activity.evidence_media_asset_ids[frame_key] = media_asset_id
            activity.saved_candidate_count = min(
                DEFAULT_ACTIVITY_MAX_SAVED_CANDIDATES,
                len(activity.evidence_media_asset_ids)
                + (1 if activity.best_media_asset_id is not None else 0),
            )
            snapshot = activity.snapshot()
            self.last_activity = snapshot.as_dict()
            return snapshot

    def mark_activity_review_created(
        self,
        activity_session_id: str,
        values: Mapping[str, Any],
    ) -> LiveActivitySessionSnapshot | None:
        with self._lock:
            activity = self._activity_session(activity_session_id)
            if activity is None:
                return None
            already_created = activity.review_activity_created
            activity.mark_review_created(values)
            snapshot = activity.snapshot()
            self.last_activity = snapshot.as_dict()
            if not already_created:
                self._record_diagnostic_event_locked(
                    "review_candidate_created",
                    status=snapshot.review_state,
                    activity=snapshot,
                )
            return snapshot

    def mark_activity_ready_for_review(
        self,
        activity_session_id: str,
        *,
        quiet_seconds: int,
    ) -> LiveActivitySessionSnapshot | None:
        with self._lock:
            activity = self._activity_session(activity_session_id)
            if activity is None:
                return None
            already_ready = activity.ready_for_review
            activity.mark_ready_for_review(quiet_seconds=quiet_seconds)
            snapshot = activity.snapshot()
            self.last_activity = snapshot.as_dict()
            if not already_ready and snapshot.ready_for_review:
                self._record_diagnostic_event_locked(
                    "activity_ready_for_review",
                    status=snapshot.review_state,
                    activity=snapshot,
                )
            return snapshot

    def mark_quiet_activity_sessions_ready_for_review(
        self,
        *,
        quiet_seconds: int,
    ) -> list[LiveActivitySessionSnapshot]:
        """Mark elapsed activity bursts ready without creating product records.

        The monitor owns this transition so a status read remains side-effect free.
        Sessions are keyed by Stream and zone/activity region, allowing a quiet
        feeder burst to close even while motion continues elsewhere on the Stream.
        """

        with self._lock:
            now = datetime.now(UTC)
            ready: list[LiveActivitySessionSnapshot] = []
            for activity in self.activity_sessions.values():
                if activity.review_activity_created or activity.detection_count <= 0:
                    continue
                elapsed_seconds = (now - activity.last_seen_at).total_seconds()
                if elapsed_seconds < quiet_seconds:
                    continue
                was_ready = activity.ready_for_review
                activity.mark_ready_for_review(quiet_seconds=quiet_seconds)
                snapshot = activity.snapshot()
                ready.append(snapshot)
                if not was_ready:
                    self.last_activity = snapshot.as_dict()
                    self._record_diagnostic_event_locked(
                        "activity_ready_for_review",
                        status=snapshot.review_state,
                        activity=snapshot,
                    )
            return sorted(
                ready,
                key=lambda activity: (activity.last_seen_at, activity.activity_session_id),
            )

    def record_auto_review_created(self, values: Mapping[str, Any]) -> None:
        with self._lock:
            created_at = _coerce_datetime(values.get("created_at")) or datetime.now(UTC)
            self.auto_review_created_count += 1
            self.last_auto_review_created_at = created_at
            self.auto_review_last_error = None
            self.last_auto_review_motion_evidence_id = _optional_str(
                values.get("motion_evidence_id")
            )
            self.last_auto_review_event_id = _optional_str(values.get("event_id"))
            self.last_auto_review_visit_id = _optional_str(values.get("visit_id"))
            self.last_auto_review_queue_item_id = _optional_str(
                values.get("review_queue_item_id")
            )
            if self.last_motion_result is not None:
                self.last_motion_result.update(
                    {
                        "auto_review_created": True,
                        "auto_review_created_count": self.auto_review_created_count,
                        "last_auto_review_created_at": created_at,
                        "auto_review_last_error": None,
                        "last_auto_review_motion_evidence_id": (
                            self.last_auto_review_motion_evidence_id
                        ),
                        "last_auto_review_event_id": self.last_auto_review_event_id,
                        "last_auto_review_visit_id": self.last_auto_review_visit_id,
                        "last_auto_review_queue_item_id": (
                            self.last_auto_review_queue_item_id
                        ),
                    }
                )

    def record_auto_review_error(self, error: str | None) -> None:
        with self._lock:
            self.auto_review_last_error = error
            if self.last_motion_result is not None:
                self.last_motion_result["auto_review_last_error"] = error
            if error:
                self._record_diagnostic_event_locked(
                    "auto_review_failed",
                    status="failed",
                    reason="auto_review_failed",
                )

    def _record_quality_warning_transition_locked(
        self,
        warnings: Any,
        *,
        activity: LiveActivitySessionSnapshot | None = None,
    ) -> None:
        warning_codes = _diagnostic_quality_warning_codes(warnings)
        if warning_codes == self._last_quality_warning_codes:
            return
        self._last_quality_warning_codes = warning_codes
        if warning_codes:
            self._record_diagnostic_event_locked(
                "quality_warning",
                status="warning",
                activity=activity,
                quality_warning_codes=warning_codes,
            )

    def _record_diagnostic_event_locked(
        self,
        event_type: str,
        *,
        status: str | None = None,
        reason: str | None = None,
        activity: LiveActivitySessionSnapshot | None = None,
        quality_warning_codes: tuple[str, ...] = (),
    ) -> None:
        if event_type not in _DIAGNOSTIC_EVENT_TYPES:
            raise ValueError("unsupported_diagnostic_event_type")
        normalized_status = _safe_diagnostic_token(status)
        normalized_reason = _safe_diagnostic_token(reason)
        normalized_warning_codes = tuple(
            code
            for code in (_safe_diagnostic_token(value) for value in quality_warning_codes)
            if code is not None
        )
        activity_session_id = activity.activity_session_id if activity is not None else None
        candidate_key = (
            event_type,
            normalized_status,
            normalized_reason,
            activity_session_id,
            normalized_warning_codes,
        )
        if self.diagnostic_events:
            previous = self.diagnostic_events[-1]
            previous_key = (
                previous.event_type,
                previous.status,
                previous.reason,
                previous.activity_session_id,
                previous.quality_warning_codes,
            )
            if candidate_key == previous_key:
                return
        self._diagnostic_sequence += 1
        self.diagnostic_events.append(
            LiveCameraDiagnosticEvent(
                sequence=self._diagnostic_sequence,
                recorded_at=datetime.now(UTC),
                event_type=event_type,
                status=normalized_status,
                reason=normalized_reason,
                activity_session_id=activity_session_id,
                frame_count=self.frame_count,
                detection_count=activity.detection_count if activity is not None else 0,
                near_miss_count=activity.near_miss_count if activity is not None else 0,
                candidate_frame_count=(
                    activity.candidate_frame_count if activity is not None else 0
                ),
                quality_warning_codes=normalized_warning_codes,
                creates_truth=False,
            )
        )

    def _activity_session(
        self,
        activity_session_id: str | None,
    ) -> "_LiveActivitySession | None":
        selected_id = activity_session_id or self.current_activity_session_id
        if selected_id is None:
            return None
        return next(
            (
                session
                for session in self.activity_sessions.values()
                if session.activity_session_id == selected_id
            ),
            None,
        )

    def increment_clients(self) -> None:
        with self._lock:
            self.clients_connected += 1

    def decrement_clients(self) -> None:
        with self._lock:
            self.clients_connected = max(0, self.clients_connected - 1)

    def snapshot(self) -> LiveCameraSessionSnapshot:
        with self._lock:
            current_activity = self._activity_session(self.current_activity_session_id)
            activity_snapshots = [activity.snapshot() for activity in self.activity_sessions.values()]
            open_activity_sessions = [
                activity
                for activity in activity_snapshots
                if activity.detection_count > 0
                and not activity.ready_for_review
                and not activity.review_activity_created
            ]
            ready_activity_sessions = [
                activity
                for activity in activity_snapshots
                if activity.detection_count > 0
                and activity.ready_for_review
                and not activity.review_activity_created
            ]
            reviewed_activity_sessions = [
                activity
                for activity in activity_snapshots
                if activity.review_activity_created and activity.review_queue_item_id
            ]
            latest_reviewed_activity = max(
                reviewed_activity_sessions,
                key=lambda activity: (activity.last_seen_at, activity.activity_session_id),
                default=None,
            )
            open_zone_names = list(
                dict.fromkeys(
                    activity.zone_name or activity.region_id or "Activity area"
                    for activity in sorted(
                        open_activity_sessions,
                        key=lambda activity: (activity.started_at, activity.activity_session_id),
                    )
                )
            )[:5]
            return LiveCameraSessionSnapshot(
                stream_id=self.stream_id,
                source_id=self.source_id,
                playback_kind=self.playback_kind,
                status=self.status,
                started_at=self.started_at,
                last_frame_at=self.last_frame_at,
                frame_count=self.frame_count,
                clients_connected=self.clients_connected,
                monitor_running=self.monitor_running,
                auto_create_review_candidates=self.auto_create_review_candidates,
                auto_review_quiet_seconds=self.auto_review_quiet_seconds,
                auto_review_min_detections=self.auto_review_min_detections,
                auto_review_created_count=self.auto_review_created_count,
                last_auto_review_created_at=self.last_auto_review_created_at,
                auto_review_last_error=self.auto_review_last_error,
                last_auto_review_motion_evidence_id=(
                    self.last_auto_review_motion_evidence_id
                ),
                last_auto_review_event_id=self.last_auto_review_event_id,
                last_auto_review_visit_id=self.last_auto_review_visit_id,
                last_auto_review_queue_item_id=self.last_auto_review_queue_item_id,
                last_motion_evaluation_at=self.last_motion_evaluation_at,
                current_activity_session=(
                    current_activity.snapshot().as_dict()
                    if current_activity is not None
                    else None
                ),
                open_activity_session_count=len(open_activity_sessions),
                open_activity_zone_names=open_zone_names,
                ready_activity_session_count=len(ready_activity_sessions),
                latest_activity_review_queue_item_id=(
                    latest_reviewed_activity.review_queue_item_id
                    if latest_reviewed_activity is not None
                    else None
                ),
                last_activity=dict(self.last_activity) if self.last_activity else None,
                last_motion_result=(
                    dict(self.last_motion_result) if self.last_motion_result else None
                ),
                last_error=self.last_error,
                stop_reason=self.stop_reason,
                max_runtime_seconds=self.max_runtime_seconds,
                camera_settings=dict(self.camera_settings),
                diagnostic_events=[
                    event.as_dict() for event in self.diagnostic_events
                ],
                diagnostic_events_truncated=(
                    self._diagnostic_sequence > len(self.diagnostic_events)
                ),
                persistent=False,
            )

    def _monitor_loop(
        self,
        evaluate: Callable[[], Mapping[str, Any]],
        interval_seconds: float,
    ) -> None:
        try:
            while not self._monitor_stop_event.is_set() and self.is_active:
                if self._monitor_stop_event.wait(interval_seconds):
                    break
                result = dict(evaluate())
                if result.get("activity_detected") is True:
                    # Activity is evidence state; only explicit stop/session stop ends monitoring.
                    continue
        except Exception as error:  # pragma: no cover - defensive around monitor callbacks.
            with self._lock:
                self.last_error = str(error)
                self.monitor_running = False
                self._record_diagnostic_event_locked(
                    "monitor_stopped",
                    status="failed",
                    reason="evaluation_failed",
                )
            return
        with self._lock:
            self.monitor_running = False

    def _reader_loop(self) -> None:
        buffer = bytearray()
        try:
            stdout = self.process.stdout
            if stdout is None:
                raise ValueError("camera process did not expose stdout")

            while not self._stop_event.is_set():
                if self._runtime_elapsed():
                    self.stop_reason = "runtime_limit_reached"
                    self._stop_event.set()
                    break
                chunk = stdout.read(64 * 1024)
                if not chunk:
                    poll = getattr(self.process, "poll", None)
                    if callable(poll) and poll() is None:
                        time.sleep(0.05)
                        continue
                    break
                buffer.extend(chunk)
                for frame in _extract_jpeg_frames(buffer):
                    stored = live_frame_cache.store_latest_frame(self.stream_id, frame)
                    with self._lock:
                        self.frame_count += 1
                        self.last_frame_at = stored.captured_at
                        self.status = "running"

            if self._stop_event.is_set():
                _stop_process(self.process)
                with self._lock:
                    if self.status not in {"stopped", "failed"}:
                        self.status = "stopped"
                    if self.stop_reason is None:
                        self.stop_reason = "stopped"
                    self._record_diagnostic_event_locked(
                        "camera_stopped",
                        status=self.status,
                        reason=self.stop_reason,
                    )
                return

            with self._lock:
                self.status = "failed"
                self.stop_reason = "process_ended"
                if self.last_error is None:
                    self.last_error = "Camera process ended before the session was stopped."
                self._record_diagnostic_event_locked(
                    "camera_failed",
                    status=self.status,
                    reason=self.stop_reason,
                )
        except Exception as error:  # pragma: no cover - defensive around OS process IO.
            _stop_process(self.process)
            with self._lock:
                self.status = "failed"
                self.stop_reason = "process_error"
                self.last_error = str(error)
                self._record_diagnostic_event_locked(
                    "camera_failed",
                    status=self.status,
                    reason=self.stop_reason,
                )

    def _runtime_elapsed(self) -> bool:
        elapsed = (datetime.now(UTC) - self.started_at).total_seconds()
        return elapsed >= self.max_runtime_seconds


@dataclass
class _LiveActivitySession:
    activity_session_id: str
    stream_id: str
    source_id: str | None
    region_key: str
    region_kind: str
    region_id: str | None
    zone_id: str | None
    zone_name: str | None
    zone_type: str | None
    started_at: datetime
    last_seen_at: datetime
    detection_count: int
    near_miss_count: int
    frames_evaluated_count: int
    completed_at: datetime | None
    ready_for_review: bool
    start_frame_sequence: int | None
    end_frame_sequence: int | None
    best_frame_sequence: int | None
    best_frame_captured_at: datetime | None
    best_frame_content_type: str | None
    best_frame_bytes: bytes | None
    best_frame_width: int | None
    best_frame_height: int | None
    activity_left: float | None
    activity_top: float | None
    activity_right: float | None
    activity_bottom: float | None
    activity_changed_pixel_count: int | None
    best_media_asset_id: str | None
    best_score: float | None
    best_changed_ratio: float | None
    best_changed_pixels: int | None
    best_total_scored_pixels: int | None
    current_changed_ratio: float | None
    current_changed_pixels: int | None
    current_total_scored_pixels: int | None
    effective_threshold_used: float | None
    threshold_source: str | None
    fine_motion_applied: bool
    image_quality_warnings: list[str]
    near_miss: bool
    margin_to_threshold: float | None
    candidate_frames: deque[_LiveActivityCandidateFrame]
    first_candidate_frame: _LiveActivityCandidateFrame | None
    evidence_media_asset_ids: dict[str, str]
    saved_candidate_count: int = 0
    notification_event: str | None = None
    _emitted_notification_events: set[str] | None = None
    review_activity_created: bool = False
    motion_evidence_id: str | None = None
    event_id: str | None = None
    visit_id: str | None = None
    review_queue_item_id: str | None = None
    suggested_label: str | None = None
    suggestion_id: str | None = None
    suggestion_confidence: float | None = None
    creates_truth: bool = False

    @classmethod
    def from_detection(
        cls,
        values: Mapping[str, Any],
        *,
        stream_id: str,
        source_id: str | None,
        region_key: str,
        now: datetime,
        frame_bytes: bytes | None,
        frame_content_type: str | None,
    ) -> "_LiveActivitySession":
        session = cls(
            activity_session_id=_activity_session_id(stream_id, region_key, now),
            stream_id=stream_id,
            source_id=source_id,
            region_key=region_key,
            region_kind=str(values.get("region_kind") or "zone"),
            region_id=_optional_str(values.get("region_id")),
            zone_id=_optional_str(values.get("zone_id")),
            zone_name=_optional_str(values.get("zone_name")),
            zone_type=_optional_str(values.get("zone_type")),
            started_at=now,
            last_seen_at=now,
            detection_count=0,
            near_miss_count=0,
            frames_evaluated_count=0,
            completed_at=None,
            ready_for_review=False,
            start_frame_sequence=None,
            end_frame_sequence=None,
            best_frame_sequence=None,
            best_frame_captured_at=None,
            best_frame_content_type=None,
            best_frame_bytes=None,
            best_frame_width=None,
            best_frame_height=None,
            activity_left=None,
            activity_top=None,
            activity_right=None,
            activity_bottom=None,
            activity_changed_pixel_count=None,
            best_media_asset_id=None,
            best_score=None,
            best_changed_ratio=None,
            best_changed_pixels=None,
            best_total_scored_pixels=None,
            current_changed_ratio=None,
            current_changed_pixels=None,
            current_total_scored_pixels=None,
            effective_threshold_used=None,
            threshold_source=None,
            fine_motion_applied=False,
            image_quality_warnings=[],
            near_miss=False,
            margin_to_threshold=None,
            candidate_frames=deque(maxlen=DEFAULT_ACTIVITY_MAX_CANDIDATE_FRAMES),
            first_candidate_frame=None,
            evidence_media_asset_ids={},
            _emitted_notification_events=set(),
        )
        session.record_detection(
            values,
            now=now,
            frame_bytes=frame_bytes,
            frame_content_type=frame_content_type,
        )
        return session

    def record_detection(
        self,
        values: Mapping[str, Any],
        *,
        now: datetime,
        frame_bytes: bytes | None,
        frame_content_type: str | None,
    ) -> None:
        activity_detected = bool(values.get("activity_detected", True))
        near_miss = bool(values.get("near_miss"))
        if activity_detected:
            if self.detection_count == 0:
                self._emit_notification_once("activity_started")
            else:
                self.notification_event = None
            self.detection_count += 1
        elif near_miss:
            self.near_miss_count += 1
            self.notification_event = None
        else:
            self.notification_event = None
        self.frames_evaluated_count += max(1, int(values.get("frames_evaluated_count") or 1))
        self.last_seen_at = now
        self.completed_at = None
        self.ready_for_review = False
        self.current_changed_ratio = _optional_float(values.get("changed_ratio"))
        self.current_changed_pixels = _optional_int(values.get("changed_pixels"))
        self.current_total_scored_pixels = _optional_int(
            values.get("total_scored_pixels")
        )
        self.effective_threshold_used = _optional_float(
            values.get("effective_threshold_used")
        )
        self.threshold_source = _optional_str(values.get("threshold_source"))
        self.fine_motion_applied = bool(values.get("fine_motion_applied"))
        self.image_quality_warnings = list(values.get("image_quality_warnings") or [])
        self.near_miss = near_miss
        self.margin_to_threshold = _optional_float(values.get("margin_to_threshold"))
        candidate_score = _optional_float(values.get("best_score"))
        candidate_frame = _LiveActivityCandidateFrame(
            sequence=_optional_int(values.get("best_frame_sequence")),
            captured_at=_coerce_datetime(values.get("best_frame_captured_at")) or now,
            score=candidate_score,
            changed_ratio=self.current_changed_ratio,
            changed_pixels=self.current_changed_pixels,
            total_scored_pixels=self.current_total_scored_pixels,
            near_miss=near_miss,
            activity_detected=activity_detected,
            frame_bytes=frame_bytes,
            content_type=frame_content_type,
            width=_optional_int(values.get("best_frame_width")),
            height=_optional_int(values.get("best_frame_height")),
        )
        if self.first_candidate_frame is None and candidate_frame.frame_bytes is not None:
            # Preserve the true beginning with one reference while the normal
            # candidate deque remains a capped rolling buffer.
            self.first_candidate_frame = candidate_frame
        self._append_candidate_frame(candidate_frame)
        if self.best_score is None or (
            candidate_score is not None and candidate_score > self.best_score
        ):
            self.best_score = candidate_score
            self.best_changed_ratio = self.current_changed_ratio
            self.best_changed_pixels = self.current_changed_pixels
            self.best_total_scored_pixels = self.current_total_scored_pixels
            self.start_frame_sequence = _optional_int(values.get("start_frame_sequence"))
            self.end_frame_sequence = _optional_int(values.get("end_frame_sequence"))
            self.best_frame_sequence = _optional_int(values.get("best_frame_sequence"))
            self.best_frame_captured_at = _coerce_datetime(
                values.get("best_frame_captured_at")
            )
            self.best_frame_content_type = frame_content_type
            self.best_frame_bytes = frame_bytes
            self.best_frame_width = _optional_int(values.get("best_frame_width"))
            self.best_frame_height = _optional_int(values.get("best_frame_height"))
            self.activity_left = _optional_float(values.get("activity_left"))
            self.activity_top = _optional_float(values.get("activity_top"))
            self.activity_right = _optional_float(values.get("activity_right"))
            self.activity_bottom = _optional_float(values.get("activity_bottom"))
            self.activity_changed_pixel_count = _optional_int(
                values.get("activity_changed_pixel_count")
            )

    def _append_candidate_frame(self, candidate: _LiveActivityCandidateFrame) -> None:
        # Burst candidates are in-memory evidence only and capped per activity session.
        self.candidate_frames.append(candidate)

    def evidence_frames(
        self,
        *,
        max_frames: int,
    ) -> list[LiveActivityEvidenceFrame]:
        """Select a stable beginning/middle/best/end sample from the capped burst."""

        limit = max(1, min(int(max_frames), DEFAULT_ACTIVITY_MAX_VISIT_EVIDENCE_FRAMES))
        primary = self._primary_evidence_candidate()
        if primary is None:
            return []

        candidates = sorted(
            (
                candidate
                for candidate in (self.first_candidate_frame, *self.candidate_frames)
                if candidate is not None and candidate.frame_bytes is not None
            ),
            key=lambda candidate: (candidate.captured_at, candidate.sequence or -1),
        )
        deduplicated: list[tuple[str, _LiveActivityCandidateFrame]] = []
        seen_keys: set[str] = set()
        seen_content: set[str] = set()

        def add(candidate: _LiveActivityCandidateFrame) -> None:
            if candidate.frame_bytes is None:
                return
            frame_key = self._candidate_frame_key(candidate)
            content_key = sha1(candidate.frame_bytes).hexdigest()
            if frame_key in seen_keys or content_key in seen_content:
                return
            seen_keys.add(frame_key)
            seen_content.add(content_key)
            deduplicated.append((frame_key, candidate))

        # Add the best frame first so an exact duplicate can never displace the
        # primary thumbnail. The final response is still chronological.
        add(primary)
        for candidate in candidates:
            add(candidate)

        if not deduplicated:
            return []

        ordered = sorted(
            deduplicated,
            key=lambda item: (item[1].captured_at, item[1].sequence or -1),
        )
        primary_key = self._candidate_frame_key(primary)
        selected_keys: list[str] = []

        def select(frame_key: str) -> None:
            if frame_key not in selected_keys and len(selected_keys) < limit:
                selected_keys.append(frame_key)

        if limit == 1:
            select(primary_key)
        else:
            # The primary thumbnail is mandatory even when a caller chooses a
            # smaller cap than the default four-frame beginning/middle/best/end set.
            select(primary_key)
            select(ordered[0][0])
            select(ordered[len(ordered) // 2][0])
            select(ordered[-1][0])
            if len(selected_keys) < limit:
                for frame_key, _candidate in ordered:
                    select(frame_key)

        selected = [item for item in ordered if item[0] in selected_keys]
        return [
            LiveActivityEvidenceFrame(
                activity_session_id=self.activity_session_id,
                frame_key=frame_key,
                media_asset_id=(
                    self.best_media_asset_id
                    if frame_key == primary_key
                    else self.evidence_media_asset_ids.get(frame_key)
                ),
                sequence=candidate.sequence,
                captured_at=candidate.captured_at,
                frame_bytes=candidate.frame_bytes or b"",
                content_type=candidate.content_type,
                width=candidate.width,
                height=candidate.height,
                is_primary=frame_key == primary_key,
            )
            for frame_key, candidate in selected
        ]

    def _primary_evidence_candidate(self) -> _LiveActivityCandidateFrame | None:
        if self.best_frame_bytes is None or self.best_frame_captured_at is None:
            return None
        return _LiveActivityCandidateFrame(
            sequence=self.best_frame_sequence,
            captured_at=self.best_frame_captured_at,
            score=self.best_score,
            changed_ratio=self.best_changed_ratio,
            changed_pixels=self.best_changed_pixels,
            total_scored_pixels=self.best_total_scored_pixels,
            near_miss=False,
            activity_detected=True,
            frame_bytes=self.best_frame_bytes,
            content_type=self.best_frame_content_type,
            width=self.best_frame_width,
            height=self.best_frame_height,
        )

    @staticmethod
    def _candidate_frame_key(candidate: _LiveActivityCandidateFrame) -> str:
        if candidate.sequence is not None:
            return f"sequence:{candidate.sequence}"
        digest = sha1(candidate.frame_bytes or b"").hexdigest()[:16]
        return f"captured:{candidate.captured_at.isoformat()}:{digest}"

    def _emit_notification_once(self, event: str) -> None:
        emitted = self._emitted_notification_events
        if emitted is None:
            emitted = set()
            self._emitted_notification_events = emitted
        if event in emitted:
            self.notification_event = None
            return
        emitted.add(event)
        self.notification_event = event

    def mark_review_created(self, values: Mapping[str, Any]) -> None:
        self.review_activity_created = True
        self.ready_for_review = True
        if self.completed_at is None:
            self.completed_at = self.last_seen_at
        self.motion_evidence_id = _optional_str(values.get("motion_evidence_id"))
        self.event_id = _optional_str(values.get("event_id"))
        self.visit_id = _optional_str(values.get("visit_id"))
        self.review_queue_item_id = _optional_str(values.get("review_queue_item_id"))
        self.suggested_label = _optional_str(values.get("suggested_label"))
        self.suggestion_id = _optional_str(values.get("suggestion_id"))
        self.suggestion_confidence = _optional_float(values.get("suggestion_confidence"))
        self.creates_truth = False
        self.saved_candidate_count = min(
            DEFAULT_ACTIVITY_MAX_SAVED_CANDIDATES,
            max(self.saved_candidate_count, 1 if self.best_media_asset_id else 0),
        )
        self._emit_notification_once("review_candidate_ready")

    def mark_ready_for_review(self, *, quiet_seconds: int) -> None:
        if self.review_activity_created:
            self.ready_for_review = True
            if self.completed_at is None:
                self.completed_at = self.last_seen_at
            return
        self.ready_for_review = True
        self.completed_at = self.last_seen_at + _timedelta_seconds(quiet_seconds)

    @property
    def review_state(self) -> str:
        if self.review_activity_created:
            return "review_candidate_created"
        if self.detection_count == 0 and self.near_miss_count > 0:
            return "tentative_burst"
        if self.ready_for_review:
            return "ready_for_review"
        return "waiting_for_quiet"

    def snapshot(self) -> LiveActivitySessionSnapshot:
        return LiveActivitySessionSnapshot(
            activity_session_id=self.activity_session_id,
            stream_id=self.stream_id,
            source_id=self.source_id,
            region_key=self.region_key,
            region_kind=self.region_kind,
            region_id=self.region_id,
            zone_id=self.zone_id,
            zone_name=self.zone_name,
            zone_type=self.zone_type,
            started_at=self.started_at,
            last_seen_at=self.last_seen_at,
            detection_count=self.detection_count,
            near_miss_count=self.near_miss_count,
            frames_evaluated_count=self.frames_evaluated_count,
            candidate_frame_count=len(self.candidate_frames),
            saved_candidate_count=self.saved_candidate_count,
            completed_at=self.completed_at,
            ready_for_review=self.ready_for_review,
            review_state=self.review_state,
            start_frame_sequence=self.start_frame_sequence,
            end_frame_sequence=self.end_frame_sequence,
            best_frame_sequence=self.best_frame_sequence,
            best_frame_captured_at=self.best_frame_captured_at,
            best_frame_content_type=self.best_frame_content_type,
            best_frame_size_bytes=(
                len(self.best_frame_bytes) if self.best_frame_bytes is not None else None
            ),
            best_frame_width=self.best_frame_width,
            best_frame_height=self.best_frame_height,
            activity_left=self.activity_left,
            activity_top=self.activity_top,
            activity_right=self.activity_right,
            activity_bottom=self.activity_bottom,
            activity_changed_pixel_count=self.activity_changed_pixel_count,
            best_media_asset_id=self.best_media_asset_id,
            best_score=self.best_score,
            best_changed_ratio=self.best_changed_ratio,
            best_changed_pixels=self.best_changed_pixels,
            best_total_scored_pixels=self.best_total_scored_pixels,
            current_changed_ratio=self.current_changed_ratio,
            current_changed_pixels=self.current_changed_pixels,
            current_total_scored_pixels=self.current_total_scored_pixels,
            effective_threshold_used=self.effective_threshold_used,
            threshold_source=self.threshold_source,
            fine_motion_applied=self.fine_motion_applied,
            image_quality_warnings=list(self.image_quality_warnings),
            near_miss=self.near_miss,
            margin_to_threshold=self.margin_to_threshold,
            review_activity_created=self.review_activity_created,
            motion_evidence_id=self.motion_evidence_id,
            event_id=self.event_id,
            visit_id=self.visit_id,
            review_queue_item_id=self.review_queue_item_id,
            suggested_label=self.suggested_label,
            suggestion_id=self.suggestion_id,
            suggestion_confidence=self.suggestion_confidence,
            session_duration_seconds=max(
                0.0,
                (self.last_seen_at - self.started_at).total_seconds(),
            ),
            manual_review_needed=(
                self.ready_for_review
                and self.detection_count > 0
                and not self.review_activity_created
            ),
            notification_event=self.notification_event,
            creates_truth=False,
        )


def _activity_session_id(stream_id: str, region_key: str, started_at: datetime) -> str:
    digest = sha1(
        f"{stream_id}|{region_key}|{started_at.isoformat()}".encode("utf-8")
    ).hexdigest()[:16]
    return f"live-activity-{digest}"


def _optional_str(value: Any) -> str | None:
    return str(value) if value is not None else None


def _optional_int(value: Any) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str) and re.fullmatch(r"-?\d+", value):
        return int(value)
    return None


def _optional_float(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _timedelta_seconds(seconds: int) -> timedelta:
    return timedelta(seconds=max(1, int(seconds)))


def _coerce_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    return None


def _start_process(config: Any) -> subprocess.Popen[bytes]:
    if config.live_stream_type == "rtsp":
        return rtsp_bridge.start_rtsp_mjpeg_process(config.live_stream_url or "")
    if config.live_stream_type == local_camera_bridge.LOCAL_USB_STREAM_TYPE:
        return local_camera_bridge.start_local_camera_mjpeg_process(
            config.local_camera_device or "",
            camera_format=config.local_camera_format,
            input_format=config.input_format,
            video_size=config.preview_video_size or config.camera_video_size,
            input_frame_rate=config.windows_framerate or config.camera_framerate,
        )
    if config.live_stream_type == windows_camera_bridge.WINDOWS_DSHOW_STREAM_TYPE:
        return windows_camera_bridge.start_windows_dshow_mjpeg_process(
            config.windows_camera_name or "",
            ffmpeg_binary_path=config.windows_ffmpeg_binary_path,
            input_format=config.input_format,
            video_size=config.windows_video_size,
            framerate=config.windows_framerate,
        )
    raise ValueError("unsupported_live_camera_session_type")


def _camera_settings_from_config(config: Any) -> dict[str, Any]:
    keys = (
        "input_format",
        "preview_video_size",
        "capture_video_size",
        "windows_video_size",
        "windows_framerate",
        "camera_video_size",
        "camera_framerate",
        "brightness",
        "contrast",
        "exposure",
        "zoom_mode",
    )
    return {
        key: value
        for key in keys
        if (value := getattr(config, key, None)) is not None
    }


def _extract_jpeg_frames(buffer: bytearray) -> list[bytes]:
    frames: list[bytes] = []
    while True:
        start = buffer.find(b"\xff\xd8")
        if start < 0:
            if len(buffer) > 1:
                del buffer[:-1]
            return frames
        end = buffer.find(b"\xff\xd9", start + 2)
        if end < 0:
            if start > 0:
                del buffer[:start]
            return frames
        frames.append(bytes(buffer[start : end + 2]))
        del buffer[: end + 2]


def _multipart_frame(frame: bytes, *, boundary: str) -> bytes:
    header = (
        f"--{boundary}\r\n"
        "Content-Type: image/jpeg\r\n"
        f"Content-Length: {len(frame)}\r\n\r\n"
    ).encode("ascii")
    return header + frame + b"\r\n"


def _stop_process(process: subprocess.Popen[bytes]) -> None:
    poll = getattr(process, "poll", None)
    terminate = getattr(process, "terminate", None)
    wait = getattr(process, "wait", None)
    kill = getattr(process, "kill", None)
    if not callable(poll) or not callable(terminate) or not callable(wait):
        return
    if poll() is not None:
        return
    terminate()
    try:
        wait(timeout=2)
    except subprocess.TimeoutExpired:
        if callable(kill):
            kill()
        wait(timeout=2)


def is_session_supported(config: Any) -> bool:
    return config.live_stream_type in SUPPORTED_SESSION_TYPES


def _safe_diagnostic_token(value: Any) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip().lower().replace("-", "_").replace(" ", "_")
    return normalized if _DIAGNOSTIC_TOKEN_PATTERN.fullmatch(normalized) else None


def _diagnostic_quality_warning_codes(values: Any) -> tuple[str, ...]:
    if not isinstance(values, (list, tuple, set)):
        return ()
    codes: list[str] = []
    for value in values:
        warning = str(value).lower()
        if "overexposed" in warning:
            code = "overexposed"
        elif "underexposed" in warning:
            code = "underexposed"
        elif "low contrast" in warning:
            code = "low_contrast"
        elif "small in frame" in warning:
            code = "small_zone_in_frame"
        elif "stale" in warning:
            code = "stale_frame"
        elif "decode" in warning:
            code = "decode_failed"
        else:
            code = "frame_quality"
        if code not in codes:
            codes.append(code)
    return tuple(codes)


__all__ = [
    "DEFAULT_MAX_DIAGNOSTIC_EVENTS",
    "DEFAULT_MAX_RUNTIME_SECONDS",
    "MJPEG_BOUNDARY",
    "LiveActivityBestFrame",
    "LiveActivitySessionSnapshot",
    "LiveCameraDiagnosticEvent",
    "LiveCameraSessionManager",
    "LiveCameraSessionSnapshot",
    "is_session_supported",
]
