"""Backend-owned live camera sessions for MockingBird-served streams."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
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
    last_motion_evaluation_at: datetime | None
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
    ) -> LiveCameraSessionSnapshot | None:
        with self._lock:
            session = self._sessions.get(stream_id)
        if session is None:
            return None
        session.start_monitor(evaluate, interval_seconds=interval_seconds)
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
        self.last_motion_evaluation_at: datetime | None = None
        self.last_activity: dict[str, Any] | None = None
        self.last_motion_result: dict[str, Any] | None = None
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
    ) -> None:
        with self._lock:
            if self.status not in {"starting", "running"}:
                raise ValueError("camera_session_not_running")
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

    def increment_clients(self) -> None:
        with self._lock:
            self.clients_connected += 1

    def decrement_clients(self) -> None:
        with self._lock:
            self.clients_connected = max(0, self.clients_connected - 1)

    def snapshot(self) -> LiveCameraSessionSnapshot:
        with self._lock:
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
                last_motion_evaluation_at=self.last_motion_evaluation_at,
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
    "LiveCameraSessionManager",
    "LiveCameraSessionSnapshot",
    "is_session_supported",
]
