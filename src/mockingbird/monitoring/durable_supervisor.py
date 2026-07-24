"""Bounded, app-owned continuity for explicitly enabled live Stream monitors.

The supervisor deliberately owns orchestration only. Camera sessions, motion
evaluation, evidence, Events, Visits, and review truth remain in their existing
boundaries. It persists operational metadata through a small store protocol so
the lifecycle policy can be tested without a camera, database, or web server.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import threading
from typing import Protocol
import uuid


DEFAULT_MAX_CONCURRENT_STREAMS = 2
DEFAULT_STARTUP_TIMEOUT_SECONDS = 30
DEFAULT_RETRY_DELAYS_SECONDS = (5, 30, 120)
DEFAULT_MAX_CONSECUTIVE_FAILURES = 3


@dataclass(frozen=True)
class DurableMonitoringCandidate:
    """Persisted desired state and last checkpoint required for reconciliation."""

    stream_id: str
    policy_revision: int
    evaluation_interval_seconds: float
    quiet_period_seconds: int
    minimum_detection_count: int
    auto_create_review_candidates: bool
    actual_state: str
    consecutive_failure_count: int
    next_retry_at: datetime | None
    last_start_attempt_at: datetime | None
    safety_hold_active: bool


@dataclass(frozen=True)
class ManagedCameraStatus:
    """A sanitized runtime view used to decide lifecycle state, never product truth."""

    state: str
    healthy_at: datetime | None = None
    monitor_running: bool = False


class DurableMonitoringStore(Protocol):
    def prepare_for_supervision(self, app_instance_id: str) -> None: ...

    def list_enabled_monitoring_candidates(
        self,
        *,
        limit: int,
    ) -> list[DurableMonitoringCandidate]: ...

    def mark_monitoring_starting(
        self,
        candidate: DurableMonitoringCandidate,
        *,
        app_instance_id: str,
        now: datetime,
    ) -> None: ...

    def mark_monitoring_running(
        self,
        candidate: DurableMonitoringCandidate,
        *,
        app_instance_id: str,
        healthy_at: datetime,
        now: datetime,
    ) -> None: ...

    def mark_monitoring_waiting(
        self,
        candidate: DurableMonitoringCandidate,
        *,
        now: datetime,
    ) -> None: ...

    def mark_monitoring_backoff(
        self,
        candidate: DurableMonitoringCandidate,
        *,
        app_instance_id: str,
        failure_count: int,
        retry_at: datetime,
        now: datetime,
    ) -> None: ...

    def mark_monitoring_blocked(
        self,
        candidate: DurableMonitoringCandidate,
        *,
        app_instance_id: str,
        failure_count: int,
        failure_code: str,
        now: datetime,
    ) -> None: ...

    def mark_monitoring_stopped(
        self,
        stream_id: str,
        *,
        reason: str,
        now: datetime,
    ) -> None: ...


CameraStarter = Callable[[DurableMonitoringCandidate], ManagedCameraStatus]
MonitorStarter = Callable[[DurableMonitoringCandidate], ManagedCameraStatus]
CameraStatusReader = Callable[[str], ManagedCameraStatus | None]
CameraStopper = Callable[[str, str], None]


class DurableMonitoringSupervisor:
    """Reconciles enabled Stream intent with one bounded local camera runtime."""

    def __init__(
        self,
        *,
        store: DurableMonitoringStore,
        start_camera: CameraStarter,
        start_monitor: MonitorStarter,
        camera_status: CameraStatusReader,
        stop_camera: CameraStopper,
        max_concurrent_streams: int = DEFAULT_MAX_CONCURRENT_STREAMS,
        startup_timeout_seconds: int = DEFAULT_STARTUP_TIMEOUT_SECONDS,
        retry_delays_seconds: tuple[int, ...] = DEFAULT_RETRY_DELAYS_SECONDS,
        max_consecutive_failures: int = DEFAULT_MAX_CONSECUTIVE_FAILURES,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if max_concurrent_streams < 1:
            raise ValueError("max_concurrent_streams_must_be_positive")
        if not retry_delays_seconds:
            raise ValueError("retry_delays_required")
        self._store = store
        self._start_camera = start_camera
        self._start_monitor = start_monitor
        self._camera_status = camera_status
        self._stop_camera = stop_camera
        self._max_concurrent_streams = max_concurrent_streams
        self._startup_timeout_seconds = startup_timeout_seconds
        self._retry_delays_seconds = retry_delays_seconds
        self._max_consecutive_failures = max_consecutive_failures
        self._clock = clock or (lambda: datetime.now(UTC))
        self._app_instance_id = uuid.uuid4().hex
        self._active_stream_ids: set[str] = set()
        self._reconcile_lock = threading.RLock()
        self._wake_event = threading.Event()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    @property
    def app_instance_id(self) -> str:
        return self._app_instance_id

    def start(self) -> None:
        """Start exactly one local loop after durable storage is ready."""

        with self._reconcile_lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._stop_event.clear()
            self._store.prepare_for_supervision(self._app_instance_id)
            self._thread = threading.Thread(
                target=self._run,
                name="mockingbird-durable-monitoring",
                daemon=True,
            )
            self._thread.start()
        self.wake()

    def wake(self) -> None:
        """Request a prompt reconciliation after an explicit user action."""

        self._wake_event.set()

    def stop_stream_for_configuration(self, stream_id: str) -> None:
        """Release one active slot before an explicit in-place camera configuration change.

        Desired policy remains untouched. The application service decides whether
        the already-armed Stream may be woken again after its transaction commits.
        """

        now = self._clock()
        with self._reconcile_lock:
            self._active_stream_ids.discard(stream_id)
        self._safe_stop(stream_id, "camera_configuration_changed")
        self._store.mark_monitoring_stopped(
            stream_id,
            reason="camera_configuration_changed",
            now=now,
        )

    def shutdown(self, *, reason: str) -> None:
        """Stop active runtime without changing the user's durable enabled intent."""

        self._stop_event.set()
        self._wake_event.set()
        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=3)

        now = self._clock()
        with self._reconcile_lock:
            active_stream_ids = tuple(self._active_stream_ids)
            self._active_stream_ids.clear()
            self._thread = None
        for stream_id in active_stream_ids:
            self._safe_stop(stream_id, reason)
            self._store.mark_monitoring_stopped(stream_id, reason=reason, now=now)

    def reconcile_once(self, *, now: datetime | None = None) -> None:
        """Run one deterministic scheduling pass; used by the loop and lifecycle tests."""

        if self._stop_event.is_set():
            return
        current_time = now or self._clock()
        with self._reconcile_lock:
            candidates = self._store.list_enabled_monitoring_candidates(
                limit=self._max_concurrent_streams * 25,
            )
            candidate_by_stream = {candidate.stream_id: candidate for candidate in candidates}

            for stream_id in tuple(self._active_stream_ids):
                if stream_id in candidate_by_stream:
                    continue
                self._safe_stop(stream_id, "policy_disabled")
                self._store.mark_monitoring_stopped(
                    stream_id,
                    reason="policy_disabled",
                    now=current_time,
                )
                self._active_stream_ids.discard(stream_id)

            for stream_id in tuple(self._active_stream_ids):
                candidate = candidate_by_stream.get(stream_id)
                if candidate is not None:
                    self._reconcile_active(candidate, current_time)

            for candidate in candidates:
                if candidate.stream_id in self._active_stream_ids:
                    continue
                self._reconcile_inactive(candidate, current_time)

    def _run(self) -> None:
        while not self._stop_event.is_set():
            self._wake_event.clear()
            self.reconcile_once()
            self._wake_event.wait(timeout=1.0)

    def _reconcile_active(
        self,
        candidate: DurableMonitoringCandidate,
        now: datetime,
    ) -> None:
        try:
            status = self._camera_status(candidate.stream_id)
        except Exception:
            status = None
        if status is None or status.state in {"failed", "stopped", "stopping"}:
            self._recover_from_failure(candidate, now)
            return

        if status.healthy_at is not None:
            if not status.monitor_running:
                try:
                    status = self._start_monitor(candidate)
                except Exception:
                    self._recover_from_failure(candidate, now)
                    return
            if status.monitor_running:
                self._store.mark_monitoring_running(
                    candidate,
                    app_instance_id=self._app_instance_id,
                    healthy_at=status.healthy_at,
                    now=now,
                )
                return

        started_at = candidate.last_start_attempt_at or now
        if now - started_at >= timedelta(seconds=self._startup_timeout_seconds):
            self._recover_from_failure(candidate, now)
            return
        self._store.mark_monitoring_starting(
            candidate,
            app_instance_id=self._app_instance_id,
            now=now,
        )

    def _reconcile_inactive(
        self,
        candidate: DurableMonitoringCandidate,
        now: datetime,
    ) -> None:
        if candidate.safety_hold_active:
            self._store.mark_monitoring_blocked(
                candidate,
                app_instance_id=self._app_instance_id,
                failure_count=candidate.consecutive_failure_count,
                failure_code="safety_hold",
                now=now,
            )
            return
        if candidate.next_retry_at is not None and candidate.next_retry_at > now:
            self._store.mark_monitoring_backoff(
                candidate,
                app_instance_id=self._app_instance_id,
                failure_count=candidate.consecutive_failure_count,
                retry_at=candidate.next_retry_at,
                now=now,
            )
            return
        if len(self._active_stream_ids) >= self._max_concurrent_streams:
            self._store.mark_monitoring_waiting(candidate, now=now)
            return

        self._active_stream_ids.add(candidate.stream_id)
        self._store.mark_monitoring_starting(
            candidate,
            app_instance_id=self._app_instance_id,
            now=now,
        )
        try:
            self._start_camera(candidate)
        except Exception:
            self._recover_from_failure(candidate, now)

    def _recover_from_failure(
        self,
        candidate: DurableMonitoringCandidate,
        now: datetime,
    ) -> None:
        self._safe_stop(candidate.stream_id, "runtime_unhealthy")
        self._active_stream_ids.discard(candidate.stream_id)
        failure_count = candidate.consecutive_failure_count + 1
        if failure_count >= self._max_consecutive_failures:
            self._store.mark_monitoring_blocked(
                candidate,
                app_instance_id=self._app_instance_id,
                failure_count=failure_count,
                failure_code="camera_unavailable",
                now=now,
            )
            return
        delay_seconds = self._retry_delays_seconds[
            min(failure_count - 1, len(self._retry_delays_seconds) - 1)
        ]
        self._store.mark_monitoring_backoff(
            candidate,
            app_instance_id=self._app_instance_id,
            failure_count=failure_count,
            retry_at=now + timedelta(seconds=delay_seconds),
            now=now,
        )

    def _safe_stop(self, stream_id: str, reason: str) -> None:
        try:
            self._stop_camera(stream_id, reason)
        except Exception:
            # A failed local process stop is visible through the persisted checkpoint;
            # it must never prevent the rest of shutdown/reconciliation from finishing.
            return
