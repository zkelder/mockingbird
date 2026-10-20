import asyncio
from pathlib import Path

import httpx
import pytest
from sqlalchemy import func, select

from mockingbird.api import main as api_main
from mockingbird.api.schemas import CameraSetupCompleteRequest, CameraSourceCreate, Point
from mockingbird.repository.product_repository import (
    MonitoringOperationConflictError,
    ProductRepository,
)
from mockingbird.storage.database import (
    CURRENT_DATABASE_SCHEMA_VERSION,
    create_database_engine,
    database_schema_version_is_compatible,
)
from mockingbird.storage.models import (
    CameraSourceModel,
    EventModel,
    MediaAssetModel,
    MonitoringExposureIntervalModel,
    ReviewLabelModel,
    StreamModel,
    StreamMonitoringPolicyModel,
    StreamRuntimeCheckpointModel,
    VisitModel,
    ZoneModel,
)
from tests.conftest import LegacyAuthenticatedSyncTestClient

STREAM_ID = "stream-backyard-feeder"


def _camera_node_stream(repository: ProductRepository, *, key: str) -> str:
    """Create a real paired-looking Camera Node Stream through the same
    completion path Add Camera uses, so the guard tests below exercise a
    genuine `provider_key == "camera_node"` Source rather than a hand-built
    row."""

    result = repository.complete_camera_setup(
        CameraSetupCompleteRequest(
            camera_name=f"Camera Node {key}",
            stream_name=f"Camera Node {key} view",
            provider_key="camera_node",
            config={
                "node_base_address": "http://192.168.1.23:8787",
                "node_credential": "test-credential",
                "node_camera_id": "opaque-camera-1",
                "node_id": "opaque-node-1",
            },
            zones=[
                {
                    "name": "Feeder",
                    "zone_type": "feeder",
                    "polygon": [
                        Point(x=0.2, y=0.2),
                        Point(x=0.8, y=0.2),
                        Point(x=0.8, y=0.8),
                        Point(x=0.2, y=0.8),
                    ],
                    "monitoring_policy": {"activity_sensitivity": "normal"},
                }
            ],
            enable_monitoring=False,
            idempotency_key=f"{key}-setup",
        )
    )
    return result.stream.id


@pytest.fixture
def repository(tmp_path: Path) -> ProductRepository:
    product_repository = ProductRepository(
        db_url=f"sqlite:///{tmp_path / 'mockingbird.sqlite3'}",
        media_root=tmp_path / "media",
    )
    api_main.configure_repository(product_repository)
    yield product_repository
    api_main.configure_repository(None)


def _persisted_contract_state(repository: ProductRepository) -> dict[str, object]:
    with repository.session_factory() as session:
        return {
            "policies": list(
                session.execute(
                    select(
                        StreamMonitoringPolicyModel.stream_id,
                        StreamMonitoringPolicyModel.mode,
                        StreamMonitoringPolicyModel.auto_create_review_candidates,
                        StreamMonitoringPolicyModel.policy_revision,
                        StreamMonitoringPolicyModel.updated_at,
                    ).order_by(StreamMonitoringPolicyModel.stream_id)
                ).all()
            ),
            "checkpoints": list(
                session.execute(
                    select(
                        StreamRuntimeCheckpointModel.stream_id,
                        StreamRuntimeCheckpointModel.actual_state,
                        StreamRuntimeCheckpointModel.last_stop_reason,
                        StreamRuntimeCheckpointModel.updated_at,
                    ).order_by(StreamRuntimeCheckpointModel.stream_id)
                ).all()
            ),
            "events": session.scalar(select(func.count(EventModel.id))),
            "visits": session.scalar(select(func.count(VisitModel.id))),
            "media_assets": session.scalar(select(func.count(MediaAssetModel.id))),
            "monitoring_exposure_intervals": session.scalar(select(func.count(MonitoringExposureIntervalModel.id))),
            "review_labels": session.scalar(select(func.count(ReviewLabelModel.id))),
        }


def test_existing_and_new_streams_receive_persisted_off_records(
    repository: ProductRepository,
) -> None:
    seeded_policy = repository.get_stream_monitoring_policy(STREAM_ID)
    seeded_status = repository.get_stream_runtime_status(STREAM_ID)

    assert seeded_policy is not None
    assert seeded_policy.mode == "off"
    assert seeded_policy.persisted is True
    assert seeded_policy.auto_create_review_candidates is False
    assert seeded_policy.can_arm is True
    assert seeded_policy.continuity_available is True
    assert seeded_status is not None
    assert seeded_status.desired_mode == "off"
    assert seeded_status.actual_state == "stopped"
    assert seeded_status.checkpoint_present is True

    created = repository.create_camera_source(CameraSourceCreate(name="Feeder cam"))
    created_policy = repository.get_stream_monitoring_policy(created.stream.id)
    created_status = repository.get_stream_runtime_status(created.stream.id)
    assert created_policy is not None and created_policy.mode == "off"
    assert created_status is not None and created_status.actual_state == "stopped"

    with repository.session_factory() as session:
        stream_count = session.scalar(select(func.count(StreamModel.id)))
        policies = session.scalars(select(StreamMonitoringPolicyModel)).all()
        checkpoints = session.scalars(select(StreamRuntimeCheckpointModel)).all()
    assert len(policies) == stream_count
    assert len(checkpoints) == stream_count
    assert all(policy.mode == "off" for policy in policies)
    assert all(not policy.auto_create_review_candidates for policy in policies)
    assert all(checkpoint.actual_state == "stopped" for checkpoint in checkpoints)


def test_monitoring_contract_gets_are_side_effect_free_and_start_no_runtime(
    repository: ProductRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = LegacyAuthenticatedSyncTestClient(api_main.app)
    before = _persisted_contract_state(repository)

    def fail_if_runtime_is_constructed():
        raise AssertionError("A read-only continuity route constructed camera runtime.")

    monkeypatch.setattr(
        api_main.live_camera_session,
        "LiveCameraSessionManager",
        fail_if_runtime_is_constructed,
    )

    policy_response = client.get(f"/api/streams/{STREAM_ID}/monitoring-policy")
    status_response = client.get(f"/api/streams/{STREAM_ID}/runtime-status")
    live_status_response = client.get(f"/api/streams/{STREAM_ID}/live-session/status")
    diagnostics_response = client.get(
        f"/api/streams/{STREAM_ID}/live-session/diagnostics"
    )

    assert policy_response.status_code == 200
    assert status_response.status_code == 200
    assert live_status_response.status_code == 200
    assert diagnostics_response.status_code == 200
    policy = policy_response.json()
    status = status_response.json()
    assert policy["mode"] == "off"
    assert policy["read_only"] is False
    assert policy["can_arm"] is True
    assert policy["creates_review_candidates"] is False
    assert policy["creates_review_truth"] is False
    assert status["desired_mode"] == "off"
    assert status["actual_state"] == "stopped"
    assert status["camera_start_requested"] is False
    assert status["monitor_start_requested"] is False
    assert status["exposure_interval_active"] is False
    assert status["current_healthy_duration_seconds"] is None
    assert status["durable_exposure_today_seconds"] == 0
    assert status["exposure_history_available_from"] is None
    assert status["latest_confirmed_exposure_at"] is None
    assert status["most_recent_exposure_close_reason"] is None
    assert status["creates_review_candidates"] is False
    assert status["creates_review_truth"] is False
    assert _persisted_contract_state(repository) == before
    assert api_main._live_camera_session_manager is None
    assert api_main._source_monitor_manager is None


def test_monitoring_contract_returns_404_for_unknown_stream(
    repository: ProductRepository,
) -> None:
    client = LegacyAuthenticatedSyncTestClient(api_main.app)
    assert client.get("/api/streams/missing/monitoring-policy").status_code == 404
    assert client.get("/api/streams/missing/runtime-status").status_code == 404


def test_schema_one_migrates_all_existing_streams_to_safe_off(tmp_path: Path) -> None:
    database_path = tmp_path / "mockingbird.sqlite3"
    original = ProductRepository(db_url=f"sqlite:///{database_path}")
    original.close()

    engine = create_database_engine(f"sqlite:///{database_path}")
    with engine.begin() as connection:
        connection.exec_driver_sql("DROP TABLE stream_runtime_checkpoints")
        connection.exec_driver_sql("DROP TABLE stream_monitoring_policies")
        connection.exec_driver_sql(
            "UPDATE mockingbird_schema SET version = 1 WHERE singleton_id = 1"
        )
    engine.dispose()

    migrated = ProductRepository(db_url=f"sqlite:///{database_path}")
    try:
        assert migrated.schema_status.version == CURRENT_DATABASE_SCHEMA_VERSION
        with migrated.session_factory() as session:
            stream_count = session.scalar(select(func.count(StreamModel.id)))
            policies = session.scalars(select(StreamMonitoringPolicyModel)).all()
            checkpoints = session.scalars(select(StreamRuntimeCheckpointModel)).all()
        assert len(policies) == stream_count
        assert len(checkpoints) == stream_count
        assert all(policy.mode == "off" for policy in policies)
        assert all(not policy.auto_create_review_candidates for policy in policies)
        assert all(checkpoint.actual_state == "stopped" for checkpoint in checkpoints)
    finally:
        migrated.close()


def test_runtime_checkpoint_read_preserves_last_known_runtime_without_mutation(
    repository: ProductRepository,
) -> None:
    with repository.engine.begin() as connection:
        connection.exec_driver_sql(
            "UPDATE stream_runtime_checkpoints "
            "SET actual_state = 'running', app_instance_id = 'old-process' "
            "WHERE stream_id = ?",
            (STREAM_ID,),
        )

    status = repository.get_stream_runtime_status(STREAM_ID)
    assert status is not None
    assert status.actual_state == "running"

    with repository.engine.connect() as connection:
        stored_state = connection.exec_driver_sql(
            "SELECT actual_state FROM stream_runtime_checkpoints WHERE stream_id = ?",
            (STREAM_ID,),
        ).scalar_one()
    assert stored_state == "running"


def test_runtime_status_api_serializes_legacy_naive_checkpoint_as_utc(
    repository: ProductRepository,
) -> None:
    from datetime import UTC, datetime

    timestamp = datetime(2026, 7, 20, 12, 0, 0)
    with repository.session_factory() as session:
        with session.begin():
            checkpoint = session.get(StreamRuntimeCheckpointModel, STREAM_ID)
            assert checkpoint is not None
            checkpoint.last_start_attempt_at = timestamp
            checkpoint.last_healthy_frame_at = timestamp
            checkpoint.updated_at = timestamp

    response = LegacyAuthenticatedSyncTestClient(api_main.app).get(f"/api/streams/{STREAM_ID}/runtime-status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["last_start_attempt_at"].endswith("Z")
    assert payload["last_healthy_frame_at"].endswith("Z")
    assert payload["checkpoint_updated_at"].endswith("Z")


def test_monitoring_enable_disable_and_retry_are_durable_and_idempotent(
    repository: ProductRepository,
) -> None:
    before = _persisted_contract_state(repository)

    assert (
        repository.set_stream_monitoring_enabled(
            STREAM_ID,
            enabled=True,
            idempotency_key="enable-monitoring-001",
        )
        is False
    )
    enabled_policy = repository.get_stream_monitoring_policy(STREAM_ID)
    enabled_status = repository.get_stream_runtime_status(STREAM_ID)
    assert enabled_policy is not None and enabled_policy.mode == "armed"
    assert enabled_status is not None and enabled_status.actual_state == "stopped"

    assert (
        repository.set_stream_monitoring_enabled(
            STREAM_ID,
            enabled=True,
            idempotency_key="enable-monitoring-001",
        )
        is True
    )
    with pytest.raises(MonitoringOperationConflictError):
        repository.set_stream_monitoring_enabled(
            STREAM_ID,
            enabled=False,
            idempotency_key="enable-monitoring-001",
        )

    assert (
        repository.retry_stream_monitoring(
            STREAM_ID,
            idempotency_key="retry-monitoring-001",
        )
        is False
    )
    retry_status = repository.get_stream_runtime_status(STREAM_ID)
    assert retry_status is not None and retry_status.next_retry_at is not None

    after = _persisted_contract_state(repository)
    assert after["events"] == before["events"]
    assert after["visits"] == before["visits"]
    assert after["media_assets"] == before["media_assets"]
    assert after["review_labels"] == before["review_labels"]


def test_auto_create_setting_is_durable_for_backend_reconstruction(
    repository: ProductRepository,
) -> None:
    assert (
        repository.set_stream_monitoring_enabled(
            STREAM_ID,
            enabled=True,
            idempotency_key="enable-monitoring-auto-create-001",
        )
        is False
    )
    initial = repository.get_stream_monitoring_policy(STREAM_ID)
    assert initial is not None and initial.auto_create_review_candidates is False

    updated = repository.set_stream_monitoring_auto_create_review_candidates(
        STREAM_ID,
        enabled=True,
    )
    repeated = repository.set_stream_monitoring_auto_create_review_candidates(
        STREAM_ID,
        enabled=True,
    )
    candidates = repository.list_enabled_monitoring_candidates(limit=10)

    assert updated is not None and updated.auto_create_review_candidates is True
    assert repeated is not None
    assert repeated.policy_revision == updated.policy_revision
    assert updated.policy_revision == initial.policy_revision + 1
    assert [(item.stream_id, item.auto_create_review_candidates) for item in candidates] == [
        (STREAM_ID, True)
    ]


def test_live_motion_settings_persist_auto_create_without_auto_identification(
    repository: ProductRepository,
) -> None:
    response = LegacyAuthenticatedSyncTestClient(api_main.app).post(
        f"/api/streams/{STREAM_ID}/live-motion/settings",
        json={
            "auto_create_review_candidates": True,
            "auto_identify_review_candidates": False,
            "auto_review_quiet_seconds": 30,
            "auto_review_min_detections": 1,
        },
    )

    assert response.status_code == 200
    assert response.json()["auto_create_review_candidates"] is False
    assert response.json()["auto_identify_review_candidates"] is False
    policy = repository.get_stream_monitoring_policy(STREAM_ID)
    assert policy is not None and policy.auto_create_review_candidates is True

    omitted = LegacyAuthenticatedSyncTestClient(api_main.app).post(
        f"/api/streams/{STREAM_ID}/live-motion/settings",
        json={"auto_identify_review_candidates": False},
    )
    assert omitted.status_code == 200
    preserved = repository.get_stream_monitoring_policy(STREAM_ID)
    assert preserved is not None and preserved.auto_create_review_candidates is True


def test_monitoring_api_exposes_idempotent_enable_and_bounded_status_read(
    repository: ProductRepository,
) -> None:
    client = LegacyAuthenticatedSyncTestClient(api_main.app)

    enabled = client.put(
        f"/api/streams/{STREAM_ID}/monitoring-policy",
        json={"enabled": True, "idempotency_key": "api-enable-monitoring-001"},
    )
    replay = client.put(
        f"/api/streams/{STREAM_ID}/monitoring-policy",
        json={"enabled": True, "idempotency_key": "api-enable-monitoring-001"},
    )
    statuses = client.get("/api/streams/monitoring-status?limit=1")
    retry = client.post(
        f"/api/streams/{STREAM_ID}/runtime/retry",
        json={"idempotency_key": "api-retry-monitoring-001"},
    )

    assert enabled.status_code == 200
    assert enabled.json()["policy"]["mode"] == "armed"
    assert enabled.json()["idempotent"] is False
    assert replay.status_code == 200
    assert replay.json()["idempotent"] is True
    assert statuses.status_code == 200
    assert statuses.json()["limit"] == 1
    assert len(statuses.json()["items"]) == 1
    assert retry.status_code == 200


def test_camera_node_stream_cannot_enable_legacy_monitoring(
    repository: ProductRepository,
) -> None:
    """Milestone: CAMERA NODE LEGACY-MONITORING BACKEND GUARD v1, scenarios 1-3.

    A paired Camera Node Stream uses the Observation Engine; enabling the
    legacy durable zone-motion policy for it must fail explicitly, leave the
    policy/checkpoint untouched, and never appear as durable-supervisor work.
    """

    stream_id = _camera_node_stream(repository, key="guard-enable")
    before = _persisted_contract_state(repository)

    with pytest.raises(ValueError, match="camera_node_legacy_monitoring_unsupported"):
        repository.set_stream_monitoring_enabled(
            stream_id,
            enabled=True,
            idempotency_key="camera-node-enable-attempt",
        )

    policy = repository.get_stream_monitoring_policy(stream_id)
    status = repository.get_stream_runtime_status(stream_id)
    assert policy is not None and policy.mode == "off"
    assert status is not None and status.actual_state == "stopped"
    assert _persisted_contract_state(repository) == before
    assert stream_id not in {
        candidate.stream_id
        for candidate in repository.list_enabled_monitoring_candidates(limit=50)
    }
    # The rejected attempt never consumed the idempotency key, so a genuine
    # retry with the same key deterministically fails the same way rather
    # than silently replaying a stale "success."
    with pytest.raises(ValueError, match="camera_node_legacy_monitoring_unsupported"):
        repository.set_stream_monitoring_enabled(
            stream_id,
            enabled=True,
            idempotency_key="camera-node-enable-attempt",
        )


def test_camera_node_monitoring_disable_stays_safe_and_idempotent(
    repository: ProductRepository,
) -> None:
    """Scenario 4: disabling must never be blocked, including recovery from a
    stale pre-fix `armed` row (simulated here by writing the policy directly,
    bypassing the now-guarded repository methods -- exactly the "historical
    database" case the milestone calls out)."""

    stream_id = _camera_node_stream(repository, key="guard-disable")
    with repository.engine.begin() as connection:
        connection.exec_driver_sql(
            "UPDATE stream_monitoring_policies SET mode = 'armed' WHERE stream_id = ?",
            (stream_id,),
        )

    assert (
        repository.set_stream_monitoring_enabled(
            stream_id,
            enabled=False,
            idempotency_key="camera-node-disable-stale",
        )
        is False
    )
    policy = repository.get_stream_monitoring_policy(stream_id)
    assert policy is not None and policy.mode == "off"

    # Idempotent: disabling an already-off camera_node policy is a no-op, not
    # an error.
    assert (
        repository.set_stream_monitoring_enabled(
            stream_id,
            enabled=False,
            idempotency_key="camera-node-disable-already-off",
        )
        is False
    )


def test_stale_armed_camera_node_policy_excluded_from_durable_supervisor(
    repository: ProductRepository,
) -> None:
    """Runtime fail-safe: even if a stale/corrupt `armed` row for a
    camera_node Stream exists (pre-fix data, or a direct database edit that
    bypasses the repository guard), the durable supervisor must never see it
    as work -- `LiveCameraSessionManager` genuinely supports `camera_node`
    for Live view, so nothing else would stop a real legacy session from
    starting against it."""

    stream_id = _camera_node_stream(repository, key="guard-stale")
    with repository.engine.begin() as connection:
        connection.exec_driver_sql(
            "UPDATE stream_monitoring_policies SET mode = 'armed' WHERE stream_id = ?",
            (stream_id,),
        )

    candidates = repository.list_enabled_monitoring_candidates(limit=50)
    assert stream_id not in {candidate.stream_id for candidate in candidates}


def test_non_camera_node_provider_can_still_enable_legacy_monitoring(
    repository: ProductRepository,
) -> None:
    """Scenario 5: the guard is provider-specific, not a general lockdown --
    a supported non-camera_node provider (external_url) must keep arming
    exactly as before, and must still appear as durable-supervisor work."""

    result = repository.complete_camera_setup(
        CameraSetupCompleteRequest(
            camera_name="External still camera",
            stream_name="External still camera view",
            provider_key="external_url",
            config={"url": "https://camera.local/still.jpg"},
            zones=[
                {
                    "name": "Feeder",
                    "zone_type": "feeder",
                    "polygon": [
                        Point(x=0.2, y=0.2),
                        Point(x=0.8, y=0.2),
                        Point(x=0.8, y=0.8),
                        Point(x=0.2, y=0.8),
                    ],
                    "monitoring_policy": {"activity_sensitivity": "normal"},
                }
            ],
            enable_monitoring=False,
            idempotency_key="external-url-setup",
        )
    )
    stream_id = result.stream.id

    assert (
        repository.set_stream_monitoring_enabled(
            stream_id,
            enabled=True,
            idempotency_key="external-url-enable",
        )
        is False
    )
    policy = repository.get_stream_monitoring_policy(stream_id)
    assert policy is not None and policy.mode == "armed"
    assert stream_id in {
        candidate.stream_id
        for candidate in repository.list_enabled_monitoring_candidates(limit=50)
    }


def test_camera_node_setup_completion_rejects_enable_monitoring(
    repository: ProductRepository,
) -> None:
    """The second authoritative mutation site: Add Camera's guided setup can
    also request `enable_monitoring=True` in the same call that creates the
    Stream. For camera_node that must fail before anything is persisted --
    no Source, Stream, Zone, or policy row -- not just silently ignore the
    flag."""

    before = _persisted_contract_state(repository)
    with repository.session_factory() as session:
        counts_before = (
            session.scalar(select(func.count(CameraSourceModel.id))),
            session.scalar(select(func.count(StreamModel.id))),
            session.scalar(select(func.count(ZoneModel.id))),
        )

    with pytest.raises(ValueError, match="camera_node_legacy_monitoring_unsupported"):
        repository.complete_camera_setup(
            CameraSetupCompleteRequest(
                camera_name="Camera Node reject-me",
                stream_name="Camera Node reject-me view",
                provider_key="camera_node",
                config={
                    "node_base_address": "http://192.168.1.51:8787",
                    "node_credential": "test-credential",
                    "node_camera_id": "opaque-camera-2",
                    "node_id": "opaque-node-2",
                },
                zones=[
                    {
                        "name": "Feeder",
                        "zone_type": "feeder",
                        "polygon": [
                            Point(x=0.2, y=0.2),
                            Point(x=0.8, y=0.2),
                            Point(x=0.8, y=0.8),
                            Point(x=0.2, y=0.8),
                        ],
                        "monitoring_policy": {"activity_sensitivity": "normal"},
                    }
                ],
                enable_monitoring=True,
                idempotency_key="camera-node-setup-reject",
            )
        )

    assert _persisted_contract_state(repository) == before
    with repository.session_factory() as session:
        counts_after = (
            session.scalar(select(func.count(CameraSourceModel.id))),
            session.scalar(select(func.count(StreamModel.id))),
            session.scalar(select(func.count(ZoneModel.id))),
        )
    assert counts_after == counts_before


def test_camera_node_monitoring_guard_api_returns_stable_conflict(
    repository: ProductRepository,
) -> None:
    """Scenario 8: the HTTP surface returns a clear 409 with an actionable
    message, never an unhandled 500, for a raw API call bypassing the UI."""

    stream_id = _camera_node_stream(repository, key="guard-api")
    client = LegacyAuthenticatedSyncTestClient(api_main.app)

    response = client.put(
        f"/api/streams/{stream_id}/monitoring-policy",
        json={"enabled": True, "idempotency_key": "api-camera-node-enable"},
    )

    assert response.status_code == 409
    assert "Observation Engine" in response.json()["detail"]
    policy = repository.get_stream_monitoring_policy(stream_id)
    assert policy is not None and policy.mode == "off"


def test_backup_schema_compatibility_accepts_only_known_migration_paths() -> None:
    assert database_schema_version_is_compatible(CURRENT_DATABASE_SCHEMA_VERSION)
    assert database_schema_version_is_compatible(1)
    assert not database_schema_version_is_compatible(0)
    assert not database_schema_version_is_compatible(CURRENT_DATABASE_SCHEMA_VERSION + 1)
