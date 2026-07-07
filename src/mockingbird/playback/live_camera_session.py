"""Backend-owned live camera sessions for MockingBird-served streams."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha1
import re
import subprocess
import threading
import time
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
SUPPORTED_SESSION_TYPES = {
    "rtsp",
    local_camera_bridge.LOCAL_USB_STREAM_TYPE,
    windows_camera_bridge.WINDOWS_DSHOW_STREAM_TYPE,
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
    last_activity: dict[str, Any] | None
    last_motion_result: dict[str, Any] | None
    last_error: str | None
    stop_reason: str | None
    max_runtime_seconds: int
    camera_settings: dict[str, Any]
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
    completed_at: datetime | None
    ready_for_review: bool
    review_state: str
    start_frame_sequence: int | None
    end_frame_sequence: int | None
    best_frame_sequence: int | None
    best_frame_captured_at: datetime | None
    best_frame_content_type: str | None
    best_frame_size_bytes: int | None
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
            "completed_at": self.completed_at,
            "ready_for_review": self.ready_for_review,
            "review_state": self.review_state,
            "start_frame_sequence": self.start_frame_sequence,
            "end_frame_sequence": self.end_frame_sequence,
            "best_frame_sequence": self.best_frame_sequence,
            "best_frame_captured_at": self.best_frame_captured_at,
            "best_frame_content_type": self.best_frame_content_type,
            "best_frame_size_bytes": self.best_frame_size_bytes,
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
            "creates_truth": self.creates_truth,
        }


@dataclass(frozen=True)
class LiveActivityBestFrame:
    activity_session_id: str
    frame_bytes: bytes | None
    content_type: str | None
    captured_at: datetime | None
    sequence: int | None


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
        self._thread.start()

    def stop(self, reason: str) -> None:
        with self._lock:
            if self.status in {"stopped", "failed"}:
                if self.stop_reason is None:
                    self.stop_reason = reason
                return
            self.status = "stopping"
            self.stop_reason = reason
            self.monitor_running = False
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
            self._monitor_stop_event.clear()
            self._monitor_thread = threading.Thread(
                target=self._monitor_loop,
                args=(evaluate, interval_seconds),
                name=f"mockingbird-live-monitor-{self.stream_id}",
                daemon=True,
            )
            self._monitor_thread.start()

    def stop_monitor(self) -> None:
        with self._lock:
            self.monitor_running = False
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
            if (
                existing is None
                or (now - existing.last_seen_at).total_seconds() > quiet_window_seconds
            ):
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

    def mark_activity_media_asset(
        self,
        activity_session_id: str,
        media_asset_id: str,
    ) -> LiveActivitySessionSnapshot | None:
        with self._lock:
            activity = self._activity_session(activity_session_id)
            if activity is None:
                return None
            activity.best_media_asset_id = media_asset_id
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
            activity.mark_review_created(values)
            snapshot = activity.snapshot()
            self.last_activity = snapshot.as_dict()
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
            activity.mark_ready_for_review(quiet_seconds=quiet_seconds)
            snapshot = activity.snapshot()
            self.last_activity = snapshot.as_dict()
            return snapshot

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
                last_activity=dict(self.last_activity) if self.last_activity else None,
                last_motion_result=(
                    dict(self.last_motion_result) if self.last_motion_result else None
                ),
                last_error=self.last_error,
                stop_reason=self.stop_reason,
                max_runtime_seconds=self.max_runtime_seconds,
                camera_settings=dict(self.camera_settings),
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
                return

            with self._lock:
                self.status = "failed"
                self.stop_reason = "process_ended"
                if self.last_error is None:
                    self.last_error = "Camera process ended before the session was stopped."
        except Exception as error:  # pragma: no cover - defensive around OS process IO.
            _stop_process(self.process)
            with self._lock:
                self.status = "failed"
                self.stop_reason = "process_error"
                self.last_error = str(error)

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
    completed_at: datetime | None
    ready_for_review: bool
    start_frame_sequence: int | None
    end_frame_sequence: int | None
    best_frame_sequence: int | None
    best_frame_captured_at: datetime | None
    best_frame_content_type: str | None
    best_frame_bytes: bytes | None
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
            completed_at=None,
            ready_for_review=False,
            start_frame_sequence=None,
            end_frame_sequence=None,
            best_frame_sequence=None,
            best_frame_captured_at=None,
            best_frame_content_type=None,
            best_frame_bytes=None,
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
        self.detection_count += 1
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
        self.near_miss = bool(values.get("near_miss"))
        self.margin_to_threshold = _optional_float(values.get("margin_to_threshold"))
        candidate_score = _optional_float(values.get("best_score"))
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


__all__ = [
    "DEFAULT_MAX_RUNTIME_SECONDS",
    "MJPEG_BOUNDARY",
    "LiveActivityBestFrame",
    "LiveActivitySessionSnapshot",
    "LiveCameraSessionManager",
    "LiveCameraSessionSnapshot",
    "is_session_supported",
]
