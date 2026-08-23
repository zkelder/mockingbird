from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
import asyncio

import httpx
import pytest
from sqlalchemy import create_engine, func, inspect, select

from mockingbird.api import main as api_main
from mockingbird.api.schemas import CameraHealthState
from mockingbird.api.main import _evidence_persistence_failed, app, configure_repository
from mockingbird.monitoring.durable_supervisor import DurableMonitoringCandidate
from mockingbird.repository import product_repository as product_repository_module
from mockingbird.repository.product_repository import ProductRepository
from mockingbird.storage.database import CURRENT_DATABASE_SCHEMA_VERSION, initialize_database
from mockingbird.storage.models import (
    CameraHealthIncidentModel,
    EventModel,
    MediaAssetModel,
    ProductAlertModel,
    ReviewLabelModel,
    StreamRuntimeCheckpointModel,
    VisitModel,
)


@pytest.fixture
def repository(tmp_path: Path) -> ProductRepository:
    product_repository = ProductRepository(
        db_url=f"sqlite:///{tmp_path / 'mockingbird.sqlite3'}",
        media_root=tmp_path / "media",
    )
    yield product_repository
    product_repository.close()


def _enable(repository: ProductRepository) -> DurableMonitoringCandidate:
    stream = repository.list_streams()[0]
    assert repository.set_stream_monitoring_enabled(
        stream.id,
        enabled=True,
        idempotency_key=f"enable-camera-health-{stream.id}",
    ) is False
    return repository.list_enabled_monitoring_candidates(limit=1)[0]


def _monitoring_alerts(repository: ProductRepository) -> list[ProductAlertModel]:
    with repository.session_factory() as session:
        return session.scalars(
            select(ProductAlertModel)
            .where(ProductAlertModel.category == "monitoring")
            .order_by(ProductAlertModel.created_at, ProductAlertModel.id)
        ).all()


def _incidents(repository: ProductRepository) -> list[CameraHealthIncidentModel]:
    with repository.session_factory() as session:
        return session.scalars(
            select(CameraHealthIncidentModel).order_by(
                CameraHealthIncidentModel.updated_at.desc(),
                CameraHealthIncidentModel.id.desc(),
            )
        ).all()


def test_recent_frame_is_healthy_without_wildlife_activity_or_truth(repository: ProductRepository) -> None:
    with repository.session_factory() as session:
        counts_before = (
            session.scalar(select(func.count(EventModel.id))),
            session.scalar(select(func.count(VisitModel.id))),
            session.scalar(select(func.count(MediaAssetModel.id))),
            session.scalar(select(func.count(ReviewLabelModel.id))),
        )
    candidate = _enable(repository)
    now = datetime.now(UTC)
    repository.mark_monitoring_running(
        candidate,
        app_instance_id="camera-health-test",
        healthy_at=now,
        now=now,
    )

    detail = repository.get_stream_camera_health(candidate.stream_id)
    assert detail is not None
    assert detail.health.state == CameraHealthState.healthy
    assert detail.health.open_activity_session_count == 0
    with repository.session_factory() as session:
        assert (
            session.scalar(select(func.count(EventModel.id))),
            session.scalar(select(func.count(VisitModel.id))),
            session.scalar(select(func.count(MediaAssetModel.id))),
            session.scalar(select(func.count(ReviewLabelModel.id))),
        ) == counts_before


def test_successful_evidence_reset_is_temporarily_recovering_until_monitoring_frame(
    repository: ProductRepository,
) -> None:
    candidate = _enable(repository)
    now = datetime.now(UTC)
    repository.mark_monitoring_running(
        candidate,
        app_instance_id="camera-health-test",
        healthy_at=now,
        now=now,
    )
    detail = repository.get_stream_camera_health(candidate.stream_id)
    assert detail is not None and detail.health.state == CameraHealthState.healthy

    class PendingRecovery:
        pending = True

        def monitoring_recovery_pending(self, stream_id: str) -> bool:
            assert stream_id == candidate.stream_id
            return self.pending

    manager = PendingRecovery()
    previous = api_main._live_camera_session_manager
    api_main._live_camera_session_manager = manager
    try:
        recovering = api_main._camera_health_with_pending_node_recovery(detail)
        assert recovering.health.state == CameraHealthState.recovering
        assert recovering.health.failure_reason == "provider_reset_required"

        manager.pending = False
        recovered = api_main._camera_health_with_pending_node_recovery(detail)
        assert recovered.health.state == CameraHealthState.healthy
    finally:
        api_main._live_camera_session_manager = previous


def test_startup_grace_and_capacity_wait_are_distinct(repository: ProductRepository) -> None:
    candidate = _enable(repository)
    now = datetime.now(UTC)
    repository.mark_monitoring_starting(
        candidate,
        app_instance_id="camera-health-test",
        now=now,
    )
    starting = repository.get_stream_camera_health(candidate.stream_id)
    assert starting is not None
    assert starting.health.state == CameraHealthState.starting
    assert starting.incidents == []
    assert _monitoring_alerts(repository) == []

    repository.mark_monitoring_waiting(candidate, now=now - timedelta(minutes=6))
    repository.mark_monitoring_waiting(candidate, now=now)
    waiting = repository.get_stream_camera_health(candidate.stream_id)
    assert waiting is not None
    assert waiting.health.state == CameraHealthState.waiting_for_capacity
    assert len(waiting.incidents) == 1
    assert waiting.incidents[0].category == "capacity_waiting"


def test_stale_frame_and_evidence_persistence_are_separate(repository: ProductRepository) -> None:
    candidate = _enable(repository)
    now = datetime.now(UTC)
    repository.mark_monitoring_running(
        candidate,
        app_instance_id="camera-health-test",
        healthy_at=now - timedelta(minutes=9),
        now=now,
    )
    stale_frame = repository.get_stream_camera_health(candidate.stream_id)
    assert stale_frame is not None
    assert stale_frame.health.state == CameraHealthState.no_recent_frame
    assert stale_frame.health.last_good_frame_at is not None

    repository.record_stream_health_observation(
        candidate.stream_id,
        last_evidence_persisted_at=None,
        evidence_persistence_failed=True,
        now=now,
    )
    degraded = repository.get_stream_camera_health(candidate.stream_id)
    assert degraded is not None
    assert degraded.health.state == CameraHealthState.evidence_storage_degraded
    assert degraded.health.failure_reason == "MockingBird could not safely persist required evidence."


def test_restore_hold_shows_a_calm_explicit_message_and_clears_on_explicit_retry(
    repository: ProductRepository,
) -> None:
    """v0.1 Release Hardening v1: `apply_restore_hold` (see
    docs/local-backup-recovery-design.md) must be visible and explicit, not
    a silent block a user has no way to discover or clear. The aggregate
    Dashboard state stays in the calm/OK bucket (`stopped`) -- a deliberate,
    safe pause is not an alarm -- but the message names exactly what
    happened and that an explicit resume exists; the existing `retry_
    stream_monitoring` explicit-resume action already clears
    `safety_hold_active` for any reason, including this one."""

    candidate = _enable(repository)
    repository.apply_restore_hold()

    held = repository.get_stream_camera_health(candidate.stream_id)
    assert held is not None
    assert held.health.state == CameraHealthState.stopped
    assert "restore" in held.health.message.lower()
    assert "resume" in held.health.message.lower()
    with repository.session_factory() as session:
        checkpoint = session.get(StreamRuntimeCheckpointModel, candidate.stream_id)
        assert checkpoint is not None
        assert checkpoint.safety_hold_active is True

    resumed = repository.retry_stream_monitoring(
        candidate.stream_id, idempotency_key="resume-after-restore"
    )
    assert resumed is False, "False means freshly applied, matching set_stream_monitoring_enabled's convention"
    with repository.session_factory() as session:
        checkpoint = session.get(StreamRuntimeCheckpointModel, candidate.stream_id)
        assert checkpoint is not None
        assert checkpoint.safety_hold_active is False
        assert checkpoint.last_stop_reason == "retry_requested"

    after_resume = repository.get_stream_camera_health(candidate.stream_id)
    assert after_resume is not None
    assert after_resume.health.state != CameraHealthState.stopped
    assert "restore" not in after_resume.health.message.lower()


def test_camera_health_normalizes_legacy_naive_checkpoint_timestamps(repository: ProductRepository) -> None:
    candidate = _enable(repository)
    now = datetime.now(UTC).replace(microsecond=0)
    with repository.session_factory() as session:
        with session.begin():
            checkpoint = session.get(StreamRuntimeCheckpointModel, candidate.stream_id)
            assert checkpoint is not None
            checkpoint.actual_state = "running"
            checkpoint.last_start_attempt_at = (now - timedelta(seconds=10)).replace(
                tzinfo=None
            )
            checkpoint.last_healthy_frame_at = (now - timedelta(seconds=3)).replace(
                tzinfo=None
            )
            checkpoint.last_evidence_persisted_at = (now - timedelta(seconds=2)).replace(
                tzinfo=None
            )
            checkpoint.last_evidence_failure_at = (now - timedelta(seconds=1)).replace(
                tzinfo=None
            )
            checkpoint.last_clean_stop_at = (now - timedelta(seconds=20)).replace(
                tzinfo=None
            )
            checkpoint.last_failure_at = (now - timedelta(seconds=15)).replace(
                tzinfo=None
            )
            checkpoint.next_retry_at = (now + timedelta(seconds=30)).replace(tzinfo=None)
            checkpoint.updated_at = now.replace(tzinfo=None)

    status = repository.get_stream_runtime_status(candidate.stream_id)
    detail = repository.get_stream_camera_health(candidate.stream_id)

    assert status is not None
    assert status.last_start_attempt_at is not None
    assert status.last_start_attempt_at.tzinfo == UTC
    assert status.next_retry_at is not None and status.next_retry_at.tzinfo == UTC
    assert status.model_dump(mode="json")["last_start_attempt_at"].endswith("Z")
    assert detail is not None
    assert detail.health.state == CameraHealthState.healthy
    assert detail.health.frame_age_seconds is not None
    assert detail.health.last_good_frame_at is not None
    assert detail.health.last_good_frame_at.tzinfo == UTC


def test_camera_node_credential_failure_is_redacted_and_actionable(repository: ProductRepository) -> None:
    candidate = _enable(repository)
    now = datetime.now(UTC)
    repository.mark_monitoring_backoff_with_failure_code(
        candidate,
        app_instance_id="camera-health-test",
        failure_count=2,
        retry_at=now + timedelta(seconds=30),
        failure_code="authentication_rejected",
        now=now,
    )

    health = repository.get_stream_camera_health(candidate.stream_id)

    assert health is not None
    assert health.health.state == CameraHealthState.recovering
    assert health.health.failure_reason == (
        "The paired Camera Node no longer accepts its local credential. Pair it again or revoke access."
    )
    assert health.incidents[0].category == "recovery_exhausted"
    assert health.incidents[0].reason_code == "authentication_rejected"


def test_node_failure_retry_updates_one_incident_and_alert_until_healthy(
    repository: ProductRepository,
) -> None:
    candidate = _enable(repository)
    now = datetime.now(UTC)
    repository.mark_monitoring_backoff_with_failure_code(
        candidate,
        app_instance_id="camera-health-test",
        failure_count=2,
        retry_at=now + timedelta(seconds=5),
        failure_code="authentication_rejected",
        now=now,
    )
    retry_candidate = repository.list_enabled_monitoring_candidates(limit=1)[0]
    repository.mark_monitoring_starting(
        retry_candidate,
        app_instance_id="camera-health-test",
        now=now + timedelta(seconds=5),
    )
    retry_candidate = repository.list_enabled_monitoring_candidates(limit=1)[0]
    repository.mark_monitoring_backoff_with_failure_code(
        retry_candidate,
        app_instance_id="camera-health-test",
        failure_count=3,
        retry_at=now + timedelta(seconds=35),
        failure_code="authentication_rejected",
        now=now + timedelta(seconds=6),
    )

    assert len(_incidents(repository)) == 1
    alerts = _monitoring_alerts(repository)
    assert len(alerts) == 1 and alerts[0].resolved_at is None

    repository.mark_monitoring_running(
        repository.list_enabled_monitoring_candidates(limit=1)[0],
        app_instance_id="camera-health-test",
        healthy_at=now + timedelta(seconds=7),
        now=now + timedelta(seconds=7),
    )
    assert _incidents(repository)[0].resolved_at is not None
    assert _monitoring_alerts(repository)[0].resolved_at is not None


def test_a_new_health_incident_is_logged_once_not_on_every_routine_refresh(
    repository: ProductRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    """First-Hour Onboarding + Whole-Product Observability Closure v1 ("B4
    structured logging" -- Camera Node health transitions): fires exactly
    once for the genuinely new incident condition below, not again for the
    routine occurrence_count/severity refresh a second backoff of the
    *same* condition performs (mirrors test_node_failure_retry_updates_
    one_incident_and_alert_until_healthy's own "one incident, updated
    twice" fixture)."""

    logged: list[dict] = []
    monkeypatch.setattr(
        product_repository_module,
        "log_event",
        lambda component, event, **fields: logged.append({"component": component, "event": event, **fields}),
    )

    candidate = _enable(repository)
    now = datetime.now(UTC)
    repository.mark_monitoring_backoff_with_failure_code(
        candidate,
        app_instance_id="camera-health-test",
        failure_count=2,
        retry_at=now + timedelta(seconds=5),
        failure_code="authentication_rejected",
        now=now,
    )
    retry_candidate = repository.list_enabled_monitoring_candidates(limit=1)[0]
    repository.mark_monitoring_starting(
        retry_candidate,
        app_instance_id="camera-health-test",
        now=now + timedelta(seconds=5),
    )
    retry_candidate = repository.list_enabled_monitoring_candidates(limit=1)[0]
    repository.mark_monitoring_backoff_with_failure_code(
        retry_candidate,
        app_instance_id="camera-health-test",
        failure_count=3,
        retry_at=now + timedelta(seconds=35),
        failure_code="authentication_rejected",
        now=now + timedelta(seconds=6),
    )

    incident_events = [entry for entry in logged if entry["event"] == "health_incident_opened"]
    assert len(incident_events) == 1
    assert incident_events[0]["component"] == "camera_node"
    assert incident_events[0]["reason_code"] == "authentication_rejected"


def test_a_resolved_health_incident_is_logged_once_with_duration(
    repository: ProductRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Pre-Freeze Operability Gap Closure v1 ("A4 Camera Node incident
    resolution"): the prior milestone logged an incident *opening* but
    never its resolution -- disclosed as a known gap in
    docs/observability-error-taxonomy-contract.md. Reuses the exact same
    failure-then-healthy fixture as test_node_failure_retry_updates_one_
    incident_and_alert_until_healthy above, which already proves
    `resolved_at` itself gets set by this same sequence."""

    logged: list[dict] = []
    monkeypatch.setattr(
        product_repository_module,
        "log_event",
        lambda component, event, **fields: logged.append({"component": component, "event": event, **fields}),
    )

    candidate = _enable(repository)
    now = datetime.now(UTC)
    repository.mark_monitoring_backoff_with_failure_code(
        candidate,
        app_instance_id="camera-health-test",
        failure_count=2,
        retry_at=now + timedelta(seconds=5),
        failure_code="authentication_rejected",
        now=now,
    )
    incident_id = _incidents(repository)[0].id
    assert not [entry for entry in logged if entry["event"] == "health_incident_resolved"]

    repository.mark_monitoring_running(
        repository.list_enabled_monitoring_candidates(limit=1)[0],
        app_instance_id="camera-health-test",
        healthy_at=now + timedelta(seconds=30),
        now=now + timedelta(seconds=30),
    )

    resolved_events = [entry for entry in logged if entry["event"] == "health_incident_resolved"]
    assert len(resolved_events) == 1
    assert resolved_events[0]["component"] == "camera_node"
    assert resolved_events[0]["incident_id"] == incident_id
    assert resolved_events[0]["reason_code"] == "authentication_rejected"
    assert resolved_events[0]["resolved_health_state"] == "healthy"
    assert resolved_events[0]["duration_seconds"] == 30

    # Never fires again on a later, routine healthy poll -- one transition,
    # one record, not "healthy" logged on every poll.
    repository.mark_monitoring_running(
        repository.list_enabled_monitoring_candidates(limit=1)[0],
        app_instance_id="camera-health-test",
        healthy_at=now + timedelta(seconds=60),
        now=now + timedelta(seconds=60),
    )
    assert len([entry for entry in logged if entry["event"] == "health_incident_resolved"]) == 1


def test_disarming_monitoring_resolves_an_open_incident_as_monitoring_disarmed(
    repository: ProductRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The other `_resolve_camera_health_state` call site (policy no longer
    armed) is a real, distinct resolution transition too -- but it must
    never claim the camera itself became healthy again."""

    logged: list[dict] = []
    monkeypatch.setattr(
        product_repository_module,
        "log_event",
        lambda component, event, **fields: logged.append({"component": component, "event": event, **fields}),
    )

    candidate = _enable(repository)
    now = datetime.now(UTC)
    repository.mark_monitoring_backoff_with_failure_code(
        candidate,
        app_instance_id="camera-health-test",
        failure_count=2,
        retry_at=now + timedelta(seconds=5),
        failure_code="authentication_rejected",
        now=now,
    )
    assert len(_incidents(repository)) == 1

    assert repository.set_stream_monitoring_enabled(
        candidate.stream_id,
        enabled=False,
        idempotency_key=f"disable-camera-health-{candidate.stream_id}",
    ) is False

    resolved_events = [entry for entry in logged if entry["event"] == "health_incident_resolved"]
    assert len(resolved_events) == 1
    assert resolved_events[0]["resolved_health_state"] == "monitoring_disarmed"


def test_camera_node_session_recovery_is_operational_only(
    repository: ProductRepository,
) -> None:
    candidate = _enable(repository)
    now = datetime.now(UTC)
    with repository.session_factory() as session:
        counts_before = (
            session.scalar(select(func.count(EventModel.id))),
            session.scalar(select(func.count(VisitModel.id))),
            session.scalar(select(func.count(MediaAssetModel.id))),
            session.scalar(select(func.count(ReviewLabelModel.id))),
        )

    repository.mark_monitoring_backoff_with_failure_code(
        candidate,
        app_instance_id="camera-health-test",
        failure_count=1,
        retry_at=now + timedelta(seconds=5),
        failure_code="provider_session_failed",
        now=now,
    )

    health = repository.get_stream_camera_health(candidate.stream_id)

    assert health is not None
    assert health.health.state == CameraHealthState.recovering
    assert health.health.failure_reason == (
        "The paired Camera Node is reopening its selected camera session."
    )
    with repository.session_factory() as session:
        assert (
            session.scalar(select(func.count(EventModel.id))),
            session.scalar(select(func.count(VisitModel.id))),
            session.scalar(select(func.count(MediaAssetModel.id))),
            session.scalar(select(func.count(ReviewLabelModel.id))),
        ) == counts_before
def test_recovery_updates_one_incident_and_alert_then_resolves(repository: ProductRepository) -> None:
    candidate = _enable(repository)
    now = datetime.now(UTC)
    repository.mark_monitoring_backoff(
        candidate,
        app_instance_id="camera-health-test",
        failure_count=2,
        retry_at=now + timedelta(minutes=1),
        now=now,
    )
    repository.mark_monitoring_backoff(
        candidate,
        app_instance_id="camera-health-test",
        failure_count=3,
        retry_at=now + timedelta(minutes=2),
        now=now + timedelta(seconds=1),
    )
    incidents = _incidents(repository)
    alerts = _monitoring_alerts(repository)
    assert len(incidents) == 1
    assert incidents[0].resolved_at is None
    assert len(alerts) == 1
    assert alerts[0].resolved_at is None

    repository.mark_monitoring_running(
        candidate,
        app_instance_id="camera-health-test",
        healthy_at=now + timedelta(seconds=2),
        now=now + timedelta(seconds=2),
    )
    assert _incidents(repository)[0].resolved_at is not None
    assert _monitoring_alerts(repository)[0].resolved_at is not None


def test_health_reads_are_safe_retry_is_idempotent_and_disabled_is_not_an_alert(
    repository: ProductRepository,
) -> None:
    stream = repository.list_streams()[0]
    before = repository.get_stream_runtime_status(stream.id)
    assert before is not None and before.desired_mode == "off"
    detail = repository.get_stream_camera_health(stream.id)
    assert detail is not None and detail.health.state == CameraHealthState.stopped
    after = repository.get_stream_runtime_status(stream.id)
    assert after is not None and after.desired_mode == "off"
    assert _incidents(repository) == []
    assert _monitoring_alerts(repository) == []

    candidate = _enable(repository)
    assert repository.retry_stream_monitoring(candidate.stream_id, idempotency_key="retry-health-once") is False
    assert repository.retry_stream_monitoring(candidate.stream_id, idempotency_key="retry-health-once") is True
    assert repository.set_stream_monitoring_enabled(
        candidate.stream_id,
        enabled=False,
        idempotency_key="disable-camera-health",
    ) is False
    disabled = repository.get_stream_camera_health(candidate.stream_id)
    assert disabled is not None and disabled.health.state == CameraHealthState.stopped
    assert all(alert.resolved_at is not None for alert in _monitoring_alerts(repository))


def test_history_is_bounded_newest_first_and_safe_responses_hide_runtime_details(
    repository: ProductRepository,
) -> None:
    candidate = _enable(repository)
    started = datetime.now(UTC)
    for index in range(25):
        now = started + timedelta(minutes=index)
        repository.mark_monitoring_backoff(
            candidate,
            app_instance_id="camera-health-test",
            failure_count=2,
            retry_at=now + timedelta(seconds=30),
            now=now,
        )
        repository.mark_monitoring_running(
            candidate,
            app_instance_id="camera-health-test",
            healthy_at=now + timedelta(seconds=1),
            now=now + timedelta(seconds=1),
        )
    detail = repository.get_stream_camera_health(candidate.stream_id)
    assert detail is not None
    assert len(_incidents(repository)) <= 20
    assert detail.incidents == sorted(
        detail.incidents,
        key=lambda incident: (incident.updated_at, incident.id),
        reverse=True,
    )

    # A future unknown failure code must fall back to a generic product message,
    # never a driver command, path, camera URL, or exception string.
    with repository.session_factory() as session:
        with session.begin():
            checkpoint = session.get(StreamRuntimeCheckpointModel, candidate.stream_id)
            assert checkpoint is not None
            checkpoint.failure_code = "ffmpeg /private/camera-url password=secret"
            checkpoint.actual_state = "blocked"
            checkpoint.updated_at = datetime.now(UTC)
    safe = repository.get_stream_camera_health(candidate.stream_id)
    assert safe is not None
    rendered = safe.model_dump_json()
    assert "ffmpeg" not in rendered
    assert "camera-url" not in rendered
    assert "password" not in rendered


def test_schema_v27_contains_empty_bounded_incident_configuration_and_exposure_storage(repository: ProductRepository) -> None:
    assert CURRENT_DATABASE_SCHEMA_VERSION == 47
    tables = set(inspect(repository.engine).get_table_names())
    assert "camera_health_incidents" in tables
    assert "camera_configuration_revisions" in tables
    assert "monitoring_exposure_intervals" in tables
    assert _incidents(repository) == []


def test_v20_runtime_checkpoint_migrates_through_v27_exposure_storage(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'v20.sqlite3'}")
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TABLE mockingbird_schema (singleton_id INTEGER PRIMARY KEY, version INTEGER NOT NULL, updated_at DATETIME NOT NULL)"
        )
        connection.exec_driver_sql(
            "INSERT INTO mockingbird_schema (singleton_id, version, updated_at) VALUES (1, 20, '2026-01-01 00:00:00')"
        )
        connection.exec_driver_sql("CREATE TABLE streams (id VARCHAR PRIMARY KEY)")
        connection.exec_driver_sql(
            "CREATE TABLE stream_runtime_checkpoints ("
            "stream_id VARCHAR PRIMARY KEY, observed_policy_revision INTEGER NOT NULL, actual_state VARCHAR NOT NULL, "
            "app_instance_id VARCHAR, runtime_generation_id VARCHAR, last_start_attempt_at DATETIME, "
            "last_healthy_frame_at DATETIME, last_clean_stop_at DATETIME, last_failure_at DATETIME, "
            "failure_code VARCHAR, consecutive_failure_count INTEGER NOT NULL, next_retry_at DATETIME, "
            "last_stop_reason VARCHAR, start_count INTEGER NOT NULL, failure_count INTEGER NOT NULL, "
            "evidence_handoff_count INTEGER NOT NULL, safety_hold_active BOOLEAN NOT NULL, updated_at DATETIME NOT NULL)"
        )

    status = initialize_database(engine)
    columns = {column["name"] for column in inspect(engine).get_columns("stream_runtime_checkpoints")}
    assert status.version == CURRENT_DATABASE_SCHEMA_VERSION
    assert {"last_evidence_persisted_at", "last_evidence_failure_at", "evidence_failure_code"}.issubset(columns)
    media_columns = {column["name"] for column in inspect(engine).get_columns("media_assets")}
    assert {"parent_media_asset_id", "normalized_track_box_json", "alignment_status"}.issubset(media_columns)
    assert "camera_health_incidents" in inspect(engine).get_table_names()
    assert "camera_configuration_revisions" in inspect(engine).get_table_names()
    assert "monitoring_exposure_intervals" in inspect(engine).get_table_names()


def test_v21_configuration_metadata_is_preserved_through_v27_exposure_storage(
    tmp_path: Path,
) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'v21.sqlite3'}")
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TABLE mockingbird_schema (singleton_id INTEGER PRIMARY KEY, version INTEGER NOT NULL, updated_at DATETIME NOT NULL)"
        )
        connection.exec_driver_sql(
            "INSERT INTO mockingbird_schema (singleton_id, version, updated_at) VALUES (1, 21, '2026-01-01 00:00:00')"
        )
        connection.exec_driver_sql(
            "CREATE TABLE source_provider_configurations (source_id VARCHAR PRIMARY KEY, provider_key VARCHAR NOT NULL, config_json TEXT NOT NULL, updated_at DATETIME NOT NULL)"
        )
        connection.exec_driver_sql(
            "INSERT INTO source_provider_configurations (source_id, provider_key, config_json, updated_at) VALUES ('source-preserved', 'external_url', '{\"url\": \"https://camera.local/still.jpg\"}', '2026-01-01 00:00:00')"
        )

    status = initialize_database(engine)
    with engine.connect() as connection:
        preserved = connection.exec_driver_sql(
            "SELECT config_json FROM source_provider_configurations WHERE source_id = 'source-preserved'"
        ).scalar_one()
    assert status.version == CURRENT_DATABASE_SCHEMA_VERSION
    assert preserved == '{"url": "https://camera.local/still.jpg"}'
    assert "camera_configuration_revisions" in inspect(engine).get_table_names()
    assert "monitoring_exposure_intervals" in inspect(engine).get_table_names()


def test_camera_health_api_routes_are_bounded_and_read_only(repository: ProductRepository) -> None:
    stream = repository.list_streams()[0]
    before = repository.get_stream_runtime_status(stream.id)
    assert before is not None
    configure_repository(repository)

    async def request(path: str) -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.get(path)

    try:
        summary = asyncio.run(request("/api/camera-health?limit=1"))
        detail = asyncio.run(request(f"/api/streams/{stream.id}/camera-health"))
        history = asyncio.run(request(f"/api/streams/{stream.id}/camera-health/incidents?limit=1"))
    finally:
        configure_repository(None)

    assert summary.status_code == 200
    assert len(summary.json()["items"]) <= 1
    assert detail.status_code == 200
    assert detail.json()["health"]["stream_id"] == stream.id
    assert history.status_code == 200
    assert len(history.json()["items"]) <= 1
    after = repository.get_stream_runtime_status(stream.id)
    assert after is not None and after.desired_mode == before.desired_mode


def test_evidence_storage_health_ignores_unrelated_auto_review_errors() -> None:
    assert _evidence_persistence_failed("Managed storage could not persist evidence")
    assert not _evidence_persistence_failed(
        "Auto-create requires completed activity in a named reviewable Zone."
    )


# Camera / Source + Multi-Camera Maturity v1, Phase F/K: honest WAN-vs-camera
# disambiguation and normal-UX backlog surfacing, both reusing the existing
# Remote/Intermittent-WAN Transport backlog fact -------------------------------


def test_unreachable_host_with_fresh_transport_backlog_reads_host_unreachable(
    repository: ProductRepository, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The exact Phase F failure mode this milestone's own archaeology
    found: `node_unavailable` alone cannot tell "camera hardware failed"
    from "WAN down, Node alive and backlogging." When there is *positive,
    recent* Remote Transport evidence the Node is alive, the health summary
    must say so -- and the same read must surface the honest pending-item
    count for Phase K's normal UX, never transport/protocol jargon."""

    from mockingbird.storage.camera_node_transport_ledger import TRANSPORT_ROOT_ENV_VAR, TransportLedger

    monkeypatch.setenv(TRANSPORT_ROOT_ENV_VAR, str(tmp_path / "transport"))
    candidate = _enable(repository)
    node_id = "node-camera-health-transport-test"
    with repository.session_factory() as session:
        with session.begin():
            # `provider_key="demo"` (not "camera_node") deliberately: the
            # default seeded Stream's Source is `kind="demo"`, and claiming
            # a real `camera_node` provider config here (with no actual
            # pairing/camera-selection fields) would make `readiness_status`
            # correctly, but unhelpfully for this focused test, read as
            # `setup_incomplete` -- which overrides `failure_code` before
            # this test's own `node_unavailable` scenario is ever reached.
            # `_camera_node_transport_backlog_facts` itself never reads
            # `provider_key` at all, only `node_id`/`node_transport_
            # credential` from `config_json`, so this is a safe, narrow
            # fixture choice, not a workaround for a real bug.
            session.add(
                product_repository_module.SourceProviderConfigurationModel(
                    source_id=repository.get_stream(candidate.stream_id).source_id,
                    provider_key="demo",
                    config_json=(
                        '{"node_id": "' + node_id + '", "node_transport_credential": "configured"}'
                    ),
                    updated_at=datetime.now(UTC),
                )
            )
    TransportLedger(tmp_path / "transport").record_backlog_summary(
        node_id=node_id, summary={"pending_count": 14, "pending_bytes": 4096, "failed_terminal_count": 0},
    )

    now = datetime.now(UTC)
    repository.mark_monitoring_backoff_with_failure_code(
        candidate,
        app_instance_id="camera-health-transport-test",
        failure_count=5,
        retry_at=now + timedelta(seconds=30),
        failure_code="node_unavailable",
        now=now,
    )

    health = repository.get_stream_camera_health(candidate.stream_id)

    assert health is not None
    assert health.health.connectivity_reason == "host_unreachable"
    assert health.health.backlog_pending_count == 14
    assert health.health.backlog_last_synced_at is not None


def test_unreachable_host_without_transport_configured_stays_honestly_unset(
    repository: ProductRepository,
) -> None:
    """Control: no Remote Transport configured at all for this Source -> no
    positive evidence exists, so `connectivity_reason` stays unset rather
    than guessing either direction. This is the ordinary, unchanged case for
    every installation that never set up remote transport."""

    candidate = _enable(repository)
    now = datetime.now(UTC)
    repository.mark_monitoring_backoff_with_failure_code(
        candidate,
        app_instance_id="camera-health-no-transport-test",
        failure_count=5,
        retry_at=now + timedelta(seconds=30),
        failure_code="node_unavailable",
        now=now,
    )

    health = repository.get_stream_camera_health(candidate.stream_id)

    assert health is not None
    assert health.health.connectivity_reason is None
    assert health.health.backlog_pending_count is None
    assert health.health.backlog_last_synced_at is None


def test_authentication_failure_never_reads_host_unreachable_even_with_fresh_backlog(
    repository: ProductRepository, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The disambiguation is scoped to the one failure class it can
    genuinely speak to. A rejected credential is a real, different problem
    (pair the Node again) -- fresh transport evidence must never relabel it
    as a connectivity issue."""

    from mockingbird.storage.camera_node_transport_ledger import TRANSPORT_ROOT_ENV_VAR, TransportLedger

    monkeypatch.setenv(TRANSPORT_ROOT_ENV_VAR, str(tmp_path / "transport"))
    candidate = _enable(repository)
    node_id = "node-camera-health-auth-test"
    with repository.session_factory() as session:
        with session.begin():
            # `provider_key="demo"` (not "camera_node") deliberately: the
            # default seeded Stream's Source is `kind="demo"`, and claiming
            # a real `camera_node` provider config here (with no actual
            # pairing/camera-selection fields) would make `readiness_status`
            # correctly, but unhelpfully for this focused test, read as
            # `setup_incomplete` -- which overrides `failure_code` before
            # this test's own `node_unavailable` scenario is ever reached.
            # `_camera_node_transport_backlog_facts` itself never reads
            # `provider_key` at all, only `node_id`/`node_transport_
            # credential` from `config_json`, so this is a safe, narrow
            # fixture choice, not a workaround for a real bug.
            session.add(
                product_repository_module.SourceProviderConfigurationModel(
                    source_id=repository.get_stream(candidate.stream_id).source_id,
                    provider_key="demo",
                    config_json=(
                        '{"node_id": "' + node_id + '", "node_transport_credential": "configured"}'
                    ),
                    updated_at=datetime.now(UTC),
                )
            )
    TransportLedger(tmp_path / "transport").record_backlog_summary(
        node_id=node_id, summary={"pending_count": 3, "pending_bytes": 512, "failed_terminal_count": 0},
    )

    now = datetime.now(UTC)
    repository.mark_monitoring_backoff_with_failure_code(
        candidate,
        app_instance_id="camera-health-auth-test",
        failure_count=2,
        retry_at=now + timedelta(seconds=30),
        failure_code="authentication_rejected",
        now=now,
    )

    health = repository.get_stream_camera_health(candidate.stream_id)

    assert health is not None
    assert health.health.connectivity_reason is None
    # The backlog count itself is still honestly surfaced (Phase K) even
    # though it does not apply to *this* failure's own explanation.
    assert health.health.backlog_pending_count == 3
