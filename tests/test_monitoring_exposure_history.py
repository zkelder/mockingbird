from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import func, select

from mockingbird.api.schemas import CameraSourceCreate, CameraSourceUpdate
from mockingbird.monitoring.durable_supervisor import (
    DurableMonitoringCandidate,
    DurableMonitoringSupervisor,
    ManagedCameraStatus,
)
from mockingbird.repository.product_repository import ProductRepository, SpeciesSuggestionModel
from mockingbird.storage.models import (
    EventModel,
    MonitoringExposureIntervalModel,
    ReviewLabelModel,
    VisitModel,
)


START = datetime(2026, 7, 20, 9, tzinfo=UTC)


@pytest.fixture
def repository(tmp_path: Path) -> ProductRepository:
    product_repository = ProductRepository(
        db_url=f"sqlite:///{tmp_path / 'mockingbird.sqlite3'}",
        media_root=tmp_path / 'media',
    )
    yield product_repository
    product_repository.close()


def _product_counts(repository: ProductRepository) -> tuple[int, int, int, int]:
    with repository.session_factory() as session:
        return (
            session.scalar(select(func.count(EventModel.id))) or 0,
            session.scalar(select(func.count(VisitModel.id))) or 0,
            session.scalar(select(func.count(ReviewLabelModel.id))) or 0,
            session.scalar(select(func.count(SpeciesSuggestionModel.id))) or 0,
        )


def _intervals(repository: ProductRepository) -> list[MonitoringExposureIntervalModel]:
    with repository.session_factory() as session:
        return session.query(MonitoringExposureIntervalModel).order_by(
            MonitoringExposureIntervalModel.started_at,
            MonitoringExposureIntervalModel.id,
        ).all()


def _enable_candidate(
    repository: ProductRepository,
    *,
    now: datetime = START,
    stream_id: str | None = None,
) -> DurableMonitoringCandidate:
    stream_id = stream_id or repository.list_streams()[0].id
    assert repository.set_stream_monitoring_enabled(
        stream_id,
        enabled=True,
        idempotency_key=f"enable-{now.isoformat()}",
        now=now,
    ) is False
    candidate = repository.list_enabled_monitoring_candidates(limit=1)[0]
    repository.mark_monitoring_starting(candidate, app_instance_id='test', now=now)
    return candidate


def _utc(value: datetime | None) -> datetime | None:
    return value.replace(tzinfo=UTC) if value is not None and value.tzinfo is None else value


def test_durable_exposure_records_two_healthy_intervals_and_excludes_recovery(
    repository: ProductRepository,
) -> None:
    stream_id = repository.list_streams()[0].id
    product_counts_before = _product_counts(repository)
    first = _enable_candidate(repository)
    repository.mark_monitoring_running(first, app_instance_id='test', healthy_at=START, now=START)
    repository.mark_monitoring_running(
        first,
        app_instance_id='test',
        healthy_at=START + timedelta(minutes=90),
        now=START + timedelta(minutes=90),
    )
    repository.mark_monitoring_backoff(
        repository.list_enabled_monitoring_candidates(limit=1)[0],
        app_instance_id='test',
        failure_count=1,
        retry_at=START + timedelta(minutes=120),
        now=START + timedelta(minutes=90),
        failure_code='provider_failure',
    )

    second = repository.list_enabled_monitoring_candidates(limit=1)[0]
    repository.mark_monitoring_starting(
        second, app_instance_id='test', now=START + timedelta(minutes=120)
    )
    repository.mark_monitoring_running(
        second,
        app_instance_id='test',
        healthy_at=START + timedelta(minutes=120),
        now=START + timedelta(minutes=120),
    )
    repository.mark_monitoring_running(
        second,
        app_instance_id='test',
        healthy_at=START + timedelta(minutes=180),
        now=START + timedelta(minutes=180),
    )
    assert len(_intervals(repository)) == 2

    assert repository.set_stream_monitoring_enabled(
        stream_id,
        enabled=False,
        idempotency_key='disable-two-intervals',
        now=START + timedelta(minutes=180),
    ) is False

    intervals = _intervals(repository)
    assert [interval.close_reason for interval in intervals] == [
        'provider_failure',
        'monitoring_disabled',
    ]
    assert all(interval.ended_at is not None for interval in intervals)
    assert sum(
        (interval.ended_at - interval.started_at).total_seconds()
        for interval in intervals
        if interval.ended_at is not None
    ) == 2.5 * 60 * 60
    assert intervals[1].started_at >= intervals[0].ended_at

    status = repository.get_stream_runtime_status(
        stream_id, now=START + timedelta(minutes=180)
    )
    assert status is not None
    assert status.exposure_interval_active is False
    assert status.exposure_history_available_from == START
    assert status.latest_confirmed_exposure_at == START + timedelta(minutes=180)
    assert status.most_recent_exposure_close_reason == 'monitoring_disabled'
    assert _product_counts(repository) == product_counts_before


def test_exposure_waits_for_first_fresh_frame_and_checkpoints_writes(
    repository: ProductRepository,
) -> None:
    candidate = _enable_candidate(repository)
    assert _intervals(repository) == []

    repository.mark_monitoring_running(candidate, app_instance_id='test', healthy_at=START, now=START)
    first = _intervals(repository)[0]
    assert _utc(first.started_at) == START
    assert _utc(first.last_confirmed_fresh_at) == START
    first_updated_at = first.updated_at

    repository.mark_monitoring_running(
        candidate,
        app_instance_id='test',
        healthy_at=START + timedelta(seconds=30),
        now=START + timedelta(seconds=30),
    )
    unchanged = _intervals(repository)[0]
    assert _utc(unchanged.last_confirmed_fresh_at) == START
    assert unchanged.updated_at == first_updated_at

    repository.mark_monitoring_running(
        candidate,
        app_instance_id='test',
        healthy_at=START + timedelta(seconds=45),
        now=START + timedelta(seconds=45),
    )
    checkpointed = _intervals(repository)[0]
    assert _utc(checkpointed.last_confirmed_fresh_at) == START + timedelta(seconds=45)
    assert _utc(checkpointed.updated_at) == START + timedelta(seconds=45)


def test_zero_length_interval_is_not_preserved_and_duplicate_callbacks_do_not_duplicate(
    repository: ProductRepository,
) -> None:
    stream_id = repository.list_streams()[0].id
    candidate = _enable_candidate(repository)
    repository.mark_monitoring_running(candidate, app_instance_id='test', healthy_at=START, now=START)
    repository.mark_monitoring_running(candidate, app_instance_id='test', healthy_at=START, now=START)
    assert len(_intervals(repository)) == 1
    assert repository.set_stream_monitoring_enabled(
        stream_id,
        enabled=False,
        idempotency_key='disable-zero-length',
        now=START,
    ) is False
    assert _intervals(repository) == []


def test_unclean_restart_closes_at_last_fresh_frame_and_new_generation_reopens(
    repository: ProductRepository,
) -> None:
    candidate = _enable_candidate(repository)
    repository.mark_monitoring_running(candidate, app_instance_id='test', healthy_at=START, now=START)
    repository.mark_monitoring_running(
        candidate,
        app_instance_id='test',
        healthy_at=START + timedelta(minutes=2),
        now=START + timedelta(minutes=2),
    )

    repository.prepare_for_supervision('next-process')
    first = _intervals(repository)
    assert len(first) == 1
    assert _utc(first[0].ended_at) == START + timedelta(minutes=2)
    assert first[0].close_reason == 'unclean_restart'

    recovered = repository.list_enabled_monitoring_candidates(limit=1)[0]
    repository.mark_monitoring_starting(
        recovered, app_instance_id='next-process', now=START + timedelta(minutes=10)
    )
    repository.mark_monitoring_running(
        recovered,
        app_instance_id='next-process',
        healthy_at=START + timedelta(minutes=10),
        now=START + timedelta(minutes=10),
    )
    repository.mark_monitoring_running(
        recovered,
        app_instance_id='next-process',
        healthy_at=START + timedelta(minutes=11),
        now=START + timedelta(minutes=11),
    )
    intervals = _intervals(repository)
    assert len(intervals) == 2
    assert intervals[1].runtime_generation_id != intervals[0].runtime_generation_id
    assert intervals[1].started_at >= intervals[0].ended_at


def test_source_archive_closes_open_exposure_as_unusable(
    repository: ProductRepository,
) -> None:
    created = repository.create_camera_source(CameraSourceCreate(name="Archive fixture"))
    candidate = _enable_candidate(repository, stream_id=created.stream.id)
    repository.mark_monitoring_running(candidate, app_instance_id="test", healthy_at=START, now=START)
    repository.mark_monitoring_running(
        candidate,
        app_instance_id="test",
        healthy_at=START + timedelta(minutes=1),
        now=START + timedelta(minutes=1),
    )
    result = repository.update_camera_source(
        created.source.id, CameraSourceUpdate(archived=True)
    )
    assert result is not None
    interval = _intervals(repository)[0]
    assert interval.close_reason == "source_unusable"
    assert _utc(interval.ended_at) == START + timedelta(minutes=1)


class _SupervisorCamera:
    def __init__(self, status: ManagedCameraStatus) -> None:
        self.status = status
        self.stop_calls: list[tuple[str, str]] = []

    def start_camera(self, candidate: DurableMonitoringCandidate) -> ManagedCameraStatus:
        return self.status

    def start_monitor(self, candidate: DurableMonitoringCandidate) -> ManagedCameraStatus:
        return self.status

    def read_status(self, stream_id: str) -> ManagedCameraStatus:
        return self.status

    def stop_camera(self, stream_id: str, reason: str) -> None:
        self.stop_calls.append((stream_id, reason))


def _supervisor(
    repository: ProductRepository,
    camera: _SupervisorCamera,
    *,
    shutdown_at: datetime,
) -> DurableMonitoringSupervisor:
    return DurableMonitoringSupervisor(
        store=repository,
        start_camera=camera.start_camera,
        start_monitor=camera.start_monitor,
        camera_status=camera.read_status,
        stop_camera=camera.stop_camera,
        clock=lambda: shutdown_at,
    )


def test_supervisor_closes_stale_exposure_at_last_confirmed_frame(
    repository: ProductRepository,
) -> None:
    _enable_candidate(repository)
    camera = _SupervisorCamera(
        ManagedCameraStatus(state="running", healthy_at=START, monitor_running=True)
    )
    supervisor = _supervisor(repository, camera, shutdown_at=START + timedelta(minutes=4))
    supervisor.reconcile_once(now=START)
    supervisor.reconcile_once(now=START + timedelta(minutes=1))
    camera.status = ManagedCameraStatus(
        state="running", healthy_at=START + timedelta(minutes=1), monitor_running=True
    )
    supervisor.reconcile_once(now=START + timedelta(minutes=1))
    supervisor.reconcile_once(now=START + timedelta(minutes=3, seconds=1))

    stale = _intervals(repository)[0]
    assert stale.close_reason == "fresh_frame_stale"
    assert _utc(stale.ended_at) == START + timedelta(minutes=1)


def test_supervisor_graceful_shutdown_closes_at_in_memory_fresh_frame(
    repository: ProductRepository,
) -> None:
    stream_id = repository.list_streams()[0].id
    _enable_candidate(repository)
    camera = _SupervisorCamera(
        ManagedCameraStatus(state="running", healthy_at=START, monitor_running=True)
    )
    supervisor = _supervisor(repository, camera, shutdown_at=START + timedelta(minutes=2))
    supervisor.reconcile_once(now=START)
    supervisor.reconcile_once(now=START + timedelta(minutes=1))
    camera.status = ManagedCameraStatus(
        state="running", healthy_at=START + timedelta(minutes=1), monitor_running=True
    )
    supervisor.reconcile_once(now=START + timedelta(minutes=1))
    supervisor.shutdown(reason="api_shutdown")

    closed = _intervals(repository)[0]
    assert closed.close_reason == "application_shutdown"
    assert _utc(closed.ended_at) == START + timedelta(minutes=1)
    assert stream_id == closed.stream_id
