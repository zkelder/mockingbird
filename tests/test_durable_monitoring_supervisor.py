from dataclasses import replace
from datetime import UTC, datetime, timedelta

from mockingbird.monitoring.durable_supervisor import (
    DurableMonitoringCandidate,
    DurableMonitoringSupervisor,
    ManagedCameraStatus,
)


def _candidate(stream_id: str) -> DurableMonitoringCandidate:
    return DurableMonitoringCandidate(
        stream_id=stream_id,
        policy_revision=1,
        evaluation_interval_seconds=1.5,
        quiet_period_seconds=30,
        minimum_detection_count=1,
        auto_create_review_candidates=False,
        actual_state="stopped",
        consecutive_failure_count=0,
        next_retry_at=None,
        last_start_attempt_at=None,
        safety_hold_active=False,
    )


class FakeStore:
    def __init__(self, candidates: list[DurableMonitoringCandidate]) -> None:
        self.candidates = {candidate.stream_id: candidate for candidate in candidates}
        self.events: list[tuple[str, str]] = []
        self.running_healthy_at: list[datetime] = []

    def prepare_for_supervision(self, app_instance_id: str) -> None:
        self.events.append(("prepare", app_instance_id))

    def list_enabled_monitoring_candidates(self, *, limit: int):
        return list(sorted(self.candidates.values(), key=lambda item: item.stream_id))[:limit]

    def mark_monitoring_starting(self, candidate, *, app_instance_id, now) -> None:
        self.candidates[candidate.stream_id] = replace(
            candidate,
            actual_state="starting",
            last_start_attempt_at=candidate.last_start_attempt_at or now,
        )
        self.events.append(("starting", candidate.stream_id))

    def mark_monitoring_running(self, candidate, *, app_instance_id, healthy_at, now) -> None:
        self.candidates[candidate.stream_id] = replace(
            candidate,
            actual_state="running",
            consecutive_failure_count=0,
            next_retry_at=None,
        )
        self.running_healthy_at.append(healthy_at)
        self.events.append(("running", candidate.stream_id))

    def mark_monitoring_waiting(self, candidate, *, now) -> None:
        self.candidates[candidate.stream_id] = replace(
            candidate,
            actual_state="blocked",
        )
        self.events.append(("waiting", candidate.stream_id))

    def mark_monitoring_backoff(
        self,
        candidate,
        *,
        app_instance_id,
        failure_count,
        retry_at,
        now,
    ) -> None:
        self.candidates[candidate.stream_id] = replace(
            candidate,
            actual_state="backoff",
            consecutive_failure_count=failure_count,
            next_retry_at=retry_at,
        )
        self.events.append(("backoff", candidate.stream_id))

    def mark_monitoring_blocked(
        self,
        candidate,
        *,
        app_instance_id,
        failure_count,
        failure_code,
        now,
    ) -> None:
        self.candidates[candidate.stream_id] = replace(
            candidate,
            actual_state="blocked",
            consecutive_failure_count=failure_count,
            next_retry_at=None,
        )
        self.events.append(("blocked", candidate.stream_id))

    def mark_monitoring_stopped(self, stream_id, *, reason, now) -> None:
        candidate = self.candidates.get(stream_id)
        if candidate is not None:
            self.candidates[stream_id] = replace(candidate, actual_state="stopped")
        self.events.append(("stopped", stream_id))


class FakeCamera:
    def __init__(self) -> None:
        self.statuses: dict[str, ManagedCameraStatus] = {}
        self.start_calls: list[str] = []
        self.monitor_calls: list[str] = []
        self.stop_calls: list[str] = []
        self.fail_starts = False

    def start(self, candidate: DurableMonitoringCandidate) -> ManagedCameraStatus:
        self.start_calls.append(candidate.stream_id)
        if self.fail_starts:
            raise RuntimeError("camera unavailable")
        status = ManagedCameraStatus(state="running")
        self.statuses[candidate.stream_id] = status
        return status

    def start_monitor(self, candidate: DurableMonitoringCandidate) -> ManagedCameraStatus:
        self.monitor_calls.append(candidate.stream_id)
        previous = self.statuses[candidate.stream_id]
        status = replace(previous, monitor_running=True)
        self.statuses[candidate.stream_id] = status
        return status

    def status(self, stream_id: str) -> ManagedCameraStatus | None:
        return self.statuses.get(stream_id)

    def stop(self, stream_id: str, reason: str) -> None:
        self.stop_calls.append(stream_id)
        self.statuses[stream_id] = ManagedCameraStatus(state="stopped")


def _supervisor(store: FakeStore, camera: FakeCamera, *, capacity: int = 2):
    return DurableMonitoringSupervisor(
        store=store,
        start_camera=camera.start,
        start_monitor=camera.start_monitor,
        camera_status=camera.status,
        stop_camera=camera.stop,
        max_concurrent_streams=capacity,
    )


def test_supervisor_waits_for_a_healthy_frame_and_never_duplicates_a_session() -> None:
    now = datetime(2026, 7, 20, tzinfo=UTC)
    store = FakeStore([_candidate("stream-one")])
    camera = FakeCamera()
    supervisor = _supervisor(store, camera)

    supervisor.reconcile_once(now=now)
    assert camera.start_calls == ["stream-one"]
    assert camera.monitor_calls == []

    camera.statuses["stream-one"] = ManagedCameraStatus(
        state="running",
        healthy_at=now + timedelta(seconds=1),
    )
    supervisor.reconcile_once(now=now + timedelta(seconds=1))
    supervisor.reconcile_once(now=now + timedelta(seconds=2))

    assert camera.start_calls == ["stream-one"]
    assert camera.monitor_calls == ["stream-one"]
    assert store.candidates["stream-one"].actual_state == "running"


def test_supervisor_normalizes_legacy_naive_startup_timestamp_before_subtraction() -> None:
    """Regression for aware runtime UTC minus naive SQLite startup checkpoint."""

    now = datetime(2026, 7, 20, tzinfo=UTC)
    store = FakeStore([_candidate("stream-one")])
    camera = FakeCamera()
    supervisor = _supervisor(store, camera)

    supervisor.reconcile_once(now=now)
    store.candidates["stream-one"] = replace(
        store.candidates["stream-one"],
        last_start_attempt_at=now.replace(tzinfo=None),
    )

    supervisor.reconcile_once(now=now + timedelta(seconds=1))

    assert camera.start_calls == ["stream-one"]
    assert store.candidates["stream-one"].actual_state == "starting"
    assert ("backoff", "stream-one") not in store.events


def test_supervisor_normalizes_legacy_naive_retry_timestamp_without_duplicate_start() -> None:
    now = datetime(2026, 7, 20, tzinfo=UTC)
    retry_at = now + timedelta(minutes=1)
    store = FakeStore(
        [replace(_candidate("stream-one"), next_retry_at=retry_at.replace(tzinfo=None))]
    )
    camera = FakeCamera()
    supervisor = _supervisor(store, camera)

    supervisor.reconcile_once(now=now)
    assert camera.start_calls == []
    assert store.candidates["stream-one"].next_retry_at == retry_at

    supervisor.reconcile_once(now=retry_at)
    supervisor.reconcile_once(now=retry_at + timedelta(seconds=1))

    assert camera.start_calls == ["stream-one"]


def test_supervisor_normalizes_legacy_naive_healthy_timestamp_before_persisting() -> None:
    now = datetime(2026, 7, 20, tzinfo=UTC)
    store = FakeStore([_candidate("stream-one")])
    camera = FakeCamera()
    supervisor = _supervisor(store, camera)

    supervisor.reconcile_once(now=now)
    camera.statuses["stream-one"] = ManagedCameraStatus(
        state="running",
        healthy_at=(now + timedelta(seconds=1)).replace(tzinfo=None),
    )
    supervisor.reconcile_once(now=now + timedelta(seconds=1))

    assert store.running_healthy_at == [now + timedelta(seconds=1)]


def test_supervisor_blocks_one_malformed_timestamp_without_stopping_other_streams() -> None:
    now = datetime(2026, 7, 20, tzinfo=UTC)
    malformed = replace(_candidate("stream-malformed"), next_retry_at="not-a-timestamp")
    store = FakeStore([malformed, _candidate("stream-healthy")])
    camera = FakeCamera()
    supervisor = _supervisor(store, camera)

    supervisor.reconcile_once(now=now)

    assert store.candidates["stream-malformed"].actual_state == "blocked"
    assert ("blocked", "stream-malformed") in store.events
    assert camera.start_calls == ["stream-healthy"]


def test_supervisor_applies_bounded_backoff_then_blocks_failed_camera() -> None:
    now = datetime(2026, 7, 20, tzinfo=UTC)
    store = FakeStore([_candidate("stream-one")])
    camera = FakeCamera()
    camera.fail_starts = True
    supervisor = _supervisor(store, camera)

    supervisor.reconcile_once(now=now)
    first_retry = store.candidates["stream-one"].next_retry_at
    assert first_retry == now + timedelta(seconds=5)

    supervisor.reconcile_once(now=first_retry)
    second_retry = store.candidates["stream-one"].next_retry_at
    assert second_retry == first_retry + timedelta(seconds=30)

    supervisor.reconcile_once(now=second_retry)
    assert store.candidates["stream-one"].actual_state == "blocked"
    assert store.candidates["stream-one"].consecutive_failure_count == 3


def test_supervisor_marks_overflow_waiting_until_capacity_is_released() -> None:
    now = datetime(2026, 7, 20, tzinfo=UTC)
    store = FakeStore([_candidate("stream-a"), _candidate("stream-b")])
    camera = FakeCamera()
    supervisor = _supervisor(store, camera, capacity=1)

    supervisor.reconcile_once(now=now)
    assert camera.start_calls == ["stream-a"]
    assert store.candidates["stream-b"].actual_state == "blocked"
    assert ("waiting", "stream-b") in store.events

    del store.candidates["stream-a"]
    supervisor.reconcile_once(now=now + timedelta(seconds=1))
    assert camera.start_calls == ["stream-a", "stream-b"]
