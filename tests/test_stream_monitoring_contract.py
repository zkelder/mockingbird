import asyncio
from pathlib import Path

import httpx
import pytest
from sqlalchemy import func, select

from mockingbird.api import main as api_main
from mockingbird.api.schemas import CameraSourceCreate
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
    EventModel,
    MediaAssetModel,
    ReviewLabelModel,
    StreamModel,
    StreamMonitoringPolicyModel,
    StreamRuntimeCheckpointModel,
    VisitModel,
)

STREAM_ID = "stream-backyard-feeder"


class ASGITestClient:
    def request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, object] | None = None,
    ) -> httpx.Response:
        async def send() -> httpx.Response:
            transport = httpx.ASGITransport(app=api_main.app)
            async with httpx.AsyncClient(
                transport=transport,
                base_url="http://testserver",
            ) as client:
                return await client.request(method, path, json=json)

        return asyncio.run(send())

    def get(self, path: str) -> httpx.Response:
        return self.request("GET", path)

    def post(self, path: str, *, json: dict[str, object]) -> httpx.Response:
        return self.request("POST", path, json=json)

    def put(self, path: str, *, json: dict[str, object]) -> httpx.Response:
        return self.request("PUT", path, json=json)


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
    client = ASGITestClient()
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
    assert status["creates_review_candidates"] is False
    assert status["creates_review_truth"] is False
    assert _persisted_contract_state(repository) == before
    assert api_main._live_camera_session_manager is None
    assert api_main._source_monitor_manager is None


def test_monitoring_contract_returns_404_for_unknown_stream(
    repository: ProductRepository,
) -> None:
    client = ASGITestClient()
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


def test_monitoring_api_exposes_idempotent_enable_and_bounded_status_read(
    repository: ProductRepository,
) -> None:
    client = ASGITestClient()

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


def test_backup_schema_compatibility_accepts_only_known_migration_paths() -> None:
    assert database_schema_version_is_compatible(CURRENT_DATABASE_SCHEMA_VERSION)
    assert database_schema_version_is_compatible(1)
    assert not database_schema_version_is_compatible(0)
    assert not database_schema_version_is_compatible(CURRENT_DATABASE_SCHEMA_VERSION + 1)
