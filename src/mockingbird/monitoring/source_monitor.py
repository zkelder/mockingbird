"""Explicit in-process monitoring for configured source streams."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Literal
from uuid import uuid4

MonitorStatus = Literal[
    "stopped",
    "starting",
    "monitoring",
    "error",
    "completed",
    "stopped_by_user",
]

StopReason = Literal[
    "user_stopped",
    "max_runtime_reached",
    "max_snapshots_reached",
    "repeated_failures",
    "storage_guardrail",
    "source_not_ready",
    "error",
]

CaptureSnapshot = Callable[[str, str], Awaitable["MonitorSnapshotResult"]]
ListSavedImages = Callable[[str, str], Awaitable[list[str]]]
EvaluateSavedMedia = Callable[
    [str, list[str], bool],
    Awaitable["MonitorMotionResult"],
]

DEFAULT_INTERVAL_SECONDS = 15
DEFAULT_MAX_RUNTIME_SECONDS = 30 * 60
DEFAULT_MAX_SNAPSHOTS = 100
DEFAULT_STORAGE_IMAGE_LIMIT = 100
DEFAULT_MAX_FAILURES = 3


@dataclass(frozen=True)
class SourceMonitorOptions:
    interval_seconds: int = DEFAULT_INTERVAL_SECONDS
    max_runtime_seconds: int = DEFAULT_MAX_RUNTIME_SECONDS
    max_snapshots: int = DEFAULT_MAX_SNAPSHOTS
    check_motion: bool = True
    create_review_activity: bool = False


@dataclass(frozen=True)
class MonitorSnapshotResult:
    media_asset_id: str | None
    status: str
    message: str


@dataclass(frozen=True)
class MonitorMotionResult:
    activity_detected: bool
    activity_area: dict[str, Any] | None = None
    session_status: str | None = None
    best_media_asset_id: str | None = None
    error: str | None = None


@dataclass
class SourceMonitorState:
    monitor_id: str
    source_id: str
    stream_id: str
    status: MonitorStatus
    started_at: datetime | None = None
    stopped_at: datetime | None = None
    last_tick_at: datetime | None = None
    next_tick_at: datetime | None = None
    interval_seconds: int = DEFAULT_INTERVAL_SECONDS
    max_runtime_seconds: int = DEFAULT_MAX_RUNTIME_SECONDS
    max_snapshots: int = DEFAULT_MAX_SNAPSHOTS
    snapshots_attempted: int = 0
    snapshots_saved: int = 0
    motion_checks_run: int = 0
    last_snapshot_media_asset_id: str | None = None
    last_activity_detected: bool | None = None
    last_activity_area: dict[str, Any] | None = None
    last_session_status: str | None = None
    last_error: str | None = None
    consecutive_failures: int = 0
    stop_reason: StopReason | None = None
    check_motion: bool = True
    create_review_activity: bool = False

    def copy(self) -> "SourceMonitorState":
        return SourceMonitorState(**self.__dict__)


@dataclass
class _MonitorRecord:
    state: SourceMonitorState
    stop_event: asyncio.Event = field(default_factory=asyncio.Event)
    task: asyncio.Task[None] | None = None


class SourceMonitorManager:
    """Owns bounded monitor loops; state is intentionally process-local."""

    def __init__(
        self,
        *,
        capture_snapshot: CaptureSnapshot,
        list_saved_images: ListSavedImages,
        evaluate_saved_media: EvaluateSavedMedia,
        storage_image_limit: int = DEFAULT_STORAGE_IMAGE_LIMIT,
        max_failures: int = DEFAULT_MAX_FAILURES,
    ) -> None:
        self._capture_snapshot = capture_snapshot
        self._list_saved_images = list_saved_images
        self._evaluate_saved_media = evaluate_saved_media
        self._storage_image_limit = storage_image_limit
        self._max_failures = max_failures
        self._records: dict[str, _MonitorRecord] = {}
        self._lock = asyncio.Lock()

    async def start(
        self,
        *,
        source_id: str,
        stream_id: str,
        options: SourceMonitorOptions,
        autostart: bool = True,
    ) -> SourceMonitorState:
        async with self._lock:
            existing = self._records.get(stream_id)
            if existing and existing.state.status in {"starting", "monitoring"}:
                return existing.state.copy()

            now = _utcnow()
            state = SourceMonitorState(
                monitor_id=f"source-monitor-{uuid4().hex[:12]}",
                source_id=source_id,
                stream_id=stream_id,
                status="starting",
                started_at=now,
                interval_seconds=options.interval_seconds,
                max_runtime_seconds=options.max_runtime_seconds,
                max_snapshots=options.max_snapshots,
                check_motion=options.check_motion,
                create_review_activity=options.create_review_activity,
            )
            record = _MonitorRecord(state=state)
            self._records[stream_id] = record
            if autostart:
                record.task = asyncio.create_task(self._run(record))
            else:
                state.status = "monitoring"
            return state.copy()

    async def status(self, stream_id: str) -> SourceMonitorState | None:
        async with self._lock:
            record = self._records.get(stream_id)
            return record.state.copy() if record else None

    async def stop(self, stream_id: str) -> SourceMonitorState | None:
        async with self._lock:
            record = self._records.get(stream_id)
            if record is None:
                return None
            record.stop_event.set()
            if record.state.status in {"starting", "monitoring"}:
                self._finish(record.state, status="stopped_by_user", reason="user_stopped")
            return record.state.copy()

    async def run_one_tick_for_tests(self, stream_id: str) -> SourceMonitorState | None:
        record = self._records.get(stream_id)
        if record is None:
            return None
        await self._run_tick(record)
        return record.state.copy()

    async def reset(self) -> None:
        async with self._lock:
            self.cancel_all()
            self._records = {}

    def cancel_all(self) -> None:
        for record in self._records.values():
            record.stop_event.set()
            if record.task and not record.task.done():
                record.task.cancel()

    async def _run(self, record: _MonitorRecord) -> None:
        record.state.status = "monitoring"
        try:
            while record.state.status == "monitoring" and not record.stop_event.is_set():
                await self._run_tick(record)
                if record.state.status != "monitoring" or record.stop_event.is_set():
                    break
                record.state.next_tick_at = _utcnow() + timedelta(
                    seconds=record.state.interval_seconds,
                )
                try:
                    await asyncio.wait_for(
                        record.stop_event.wait(),
                        timeout=record.state.interval_seconds,
                    )
                except TimeoutError:
                    continue
            if record.stop_event.is_set() and record.state.status == "monitoring":
                self._finish(record.state, status="stopped_by_user", reason="user_stopped")
        except asyncio.CancelledError:
            raise
        except Exception as error:  # pragma: no cover - defensive loop boundary
            record.state.last_error = str(error) or "Monitor failed."
            self._finish(record.state, status="error", reason="error")

    async def _run_tick(self, record: _MonitorRecord) -> None:
        state = record.state
        if state.status not in {"starting", "monitoring"}:
            return
        state.status = "monitoring"
        state.next_tick_at = None

        if self._should_stop_before_tick(state):
            return

        saved_image_ids = await self._list_saved_images(state.source_id, state.stream_id)
        if len(saved_image_ids) >= self._storage_image_limit:
            self._finish(state, status="completed", reason="storage_guardrail")
            return

        state.snapshots_attempted += 1
        state.last_tick_at = _utcnow()
        try:
            snapshot = await self._capture_snapshot(state.source_id, state.stream_id)
            if snapshot.status != "saved" or not snapshot.media_asset_id:
                self._note_failure(state, snapshot.message or "Snapshot capture failed.")
                return

            state.snapshots_saved += 1
            state.last_snapshot_media_asset_id = snapshot.media_asset_id
            state.consecutive_failures = 0
            state.last_error = None

            saved_image_ids = await self._list_saved_images(state.source_id, state.stream_id)
            if len(saved_image_ids) >= self._storage_image_limit:
                self._finish(state, status="completed", reason="storage_guardrail")
                return

            if state.check_motion and len(saved_image_ids) >= 2:
                motion = await self._evaluate_saved_media(
                    state.stream_id,
                    saved_image_ids,
                    state.create_review_activity,
                )
                state.motion_checks_run += 1
                if motion.error:
                    self._note_failure(state, motion.error)
                    return
                state.last_activity_detected = motion.activity_detected
                state.last_activity_area = motion.activity_area
                state.last_session_status = motion.session_status
                state.consecutive_failures = 0
                state.last_error = None
            elif state.check_motion:
                state.last_activity_detected = None
                state.last_session_status = "needs_more_snapshots"

            if self._should_stop_after_tick(state):
                return
        except Exception as error:
            self._note_failure(state, str(error) or "Monitor tick failed.")

    def _should_stop_before_tick(self, state: SourceMonitorState) -> bool:
        if _runtime_elapsed(state):
            self._finish(state, status="completed", reason="max_runtime_reached")
            return True
        if state.snapshots_attempted >= state.max_snapshots:
            self._finish(state, status="completed", reason="max_snapshots_reached")
            return True
        if state.consecutive_failures >= self._max_failures:
            self._finish(state, status="error", reason="repeated_failures")
            return True
        return False

    def _should_stop_after_tick(self, state: SourceMonitorState) -> bool:
        if _runtime_elapsed(state):
            self._finish(state, status="completed", reason="max_runtime_reached")
            return True
        if state.snapshots_attempted >= state.max_snapshots:
            self._finish(state, status="completed", reason="max_snapshots_reached")
            return True
        return False

    def _note_failure(self, state: SourceMonitorState, message: str) -> None:
        state.consecutive_failures += 1
        state.last_error = message
        if state.consecutive_failures >= self._max_failures:
            self._finish(state, status="error", reason="repeated_failures")

    @staticmethod
    def _finish(
        state: SourceMonitorState,
        *,
        status: MonitorStatus,
        reason: StopReason,
    ) -> None:
        state.status = status
        state.stop_reason = reason
        state.stopped_at = _utcnow()
        state.next_tick_at = None


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _runtime_elapsed(state: SourceMonitorState) -> bool:
    if state.started_at is None:
        return False
    return (_utcnow() - state.started_at).total_seconds() >= state.max_runtime_seconds
