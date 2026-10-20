"""Attention Integrity & Health Reliability v1 (schema 62).

Per-user alert acknowledgement over observatory-global alert conditions,
the explicit legacy-acknowledgement upgrade rule, the sustained/self-
resolving model/runtime Observatory Health alert, and bounded attention-sync
diagnostics. See docs/attention-integrity-health-reliability-v1-report.md.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
import sqlite3
import threading

import httpx
import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import OperationalError

from mockingbird.api import main as api_main
from mockingbird.api.main import app, configure_repository
from mockingbird.api.schemas import (
    AdministratorBootstrapRequest,
    AlertActionType,
    AlertCategory,
    AlertSeverity,
    CurrentUser,
    UserRole,
)
from mockingbird.diagnostics.doctor import DoctorCheckCode, DoctorCheckResult, DoctorStatus
from mockingbird.monitoring.attention_sync_service import AttentionSyncService
from mockingbird.monitoring.model_runtime_health import (
    ModelRuntimeHealthFact,
    ModelRuntimeHealthKind,
    ModelRuntimeHealthMonitor,
)
from mockingbird.repository.product_repository import ProductRepository
from mockingbird.storage.database import (
    CURRENT_DATABASE_SCHEMA_VERSION,
    _SCHEMA_MIGRATIONS,
    database_schema_version_is_compatible,
)
from mockingbird.storage.models import (
    ProductAlertAcknowledgementModel,
    ProductAlertModel,
    UserModel,
)

NOW = datetime(2026, 9, 30, 12, 0, tzinfo=UTC)


@pytest.fixture
def repository(tmp_path: Path) -> ProductRepository:
    product_repository = ProductRepository(
        db_url=f"sqlite:///{tmp_path / 'mockingbird.sqlite3'}",
        media_root=tmp_path / "media",
    )
    yield product_repository
    product_repository.close()


def _make_user(repository: ProductRepository, user_id: str, role: UserRole = UserRole.administrator) -> CurrentUser:
    now = datetime.now(UTC)
    with repository.session_factory() as session:
        with session.begin():
            session.add(UserModel(
                id=user_id, display_name=user_id, login_identity=user_id, password_hash="scrypt$n=1,r=1,p=1$00$00",
                role=role.value, enabled=True, created_at=now, updated_at=now, password_updated_at=now,
            ))
    return CurrentUser(id=user_id, display_name=user_id, login_identity=user_id, role=role, enabled=True)


def _add_alert(
    repository: ProductRepository,
    key: str,
    *,
    category: AlertCategory = AlertCategory.storage,
    fingerprint: str = "condition-a",
    at: datetime = NOW,
) -> str:
    with repository.session_factory() as session:
        with session.begin():
            alert = repository._refresh_product_alert(  # noqa: SLF001 - the one real creation path
                session, category=category, severity=AlertSeverity.warning, title=f"Alert {key}",
                message="Fixture condition.", deduplication_key=key, condition_fingerprint=fingerprint,
                action_type=AlertActionType.open_storage_retention, action_parameters={}, now=at,
            )
            session.flush()
            return alert.id


def _alert_row(repository: ProductRepository, alert_id: str) -> ProductAlertModel:
    with repository.session_factory() as session:
        row = session.get(ProductAlertModel, alert_id)
        assert row is not None
        session.expunge(row)
        return row


def _status(repository: ProductRepository, viewer: CurrentUser, alert_id: str) -> str:
    items = repository.list_product_alerts(viewer=viewer, page_size=50).items
    return next(item.status for item in items if item.id == alert_id)


def _ack_count(repository: ProductRepository) -> int:
    with repository.session_factory() as session:
        return session.scalar(select(func.count()).select_from(ProductAlertAcknowledgementModel)) or 0


# ---------------------------------------------------------------------------
# Schema / migration / upgrade
# ---------------------------------------------------------------------------


def test_schema_62_registers_the_acknowledgement_migration() -> None:
    assert CURRENT_DATABASE_SCHEMA_VERSION == 62
    assert 62 in _SCHEMA_MIGRATIONS
    assert database_schema_version_is_compatible(1)
    assert database_schema_version_is_compatible(61)


def test_fresh_install_has_the_acknowledgement_table_and_no_rows(repository: ProductRepository) -> None:
    with repository.engine.connect() as connection:
        tables = set(connection.execute(text("SELECT name FROM sqlite_master WHERE type = 'table'")).scalars())
        assert "product_alert_acknowledgements" in tables
        primary_key = [
            row[1] for row in connection.execute(text("PRAGMA table_info(product_alert_acknowledgements)")) if row[5]
        ]
        assert sorted(primary_key) == ["alert_id", "user_id"]
        foreign_tables = {row[2] for row in connection.execute(text("PRAGMA foreign_key_list(product_alert_acknowledgements)"))}
        assert foreign_tables == {"product_alerts", "users"}
    assert _ack_count(repository) == 0


def _rewind_to_61_with_legacy_state(database_path: Path, tmp_path: Path, *, users: list[str]) -> dict[str, str]:
    repository = ProductRepository(db_url=f"sqlite:///{database_path}", media_root=tmp_path / "media")
    try:
        for user_id in users:
            _make_user(repository, user_id)
        ids = {
            "read": _add_alert(repository, "legacy:read"),
            "dismissed": _add_alert(repository, "legacy:dismissed"),
            "untouched": _add_alert(repository, "legacy:untouched"),
        }
        with repository.engine.begin() as connection:
            connection.exec_driver_sql("DROP TABLE product_alert_acknowledgements")
            connection.exec_driver_sql(
                "UPDATE product_alerts SET read_at = '2026-09-01 10:00:00.000000' WHERE id = ?", (ids["read"],)
            )
            connection.exec_driver_sql(
                "UPDATE product_alerts SET read_at = '2026-09-01 10:00:00.000000', "
                "dismissed_at = '2026-09-02 10:00:00.000000' WHERE id = ?",
                (ids["dismissed"],),
            )
            connection.exec_driver_sql("UPDATE mockingbird_schema SET version = 61 WHERE singleton_id = 1")
    finally:
        repository.close()
    return ids


def test_upgrade_from_61_gives_every_existing_user_the_legacy_state_then_stops_sharing(tmp_path: Path) -> None:
    database_path = tmp_path / "upgrade.sqlite3"
    ids = _rewind_to_61_with_legacy_state(database_path, tmp_path, users=["ada", "rae"])

    upgraded = ProductRepository(db_url=f"sqlite:///{database_path}", media_root=tmp_path / "media")
    try:
        assert upgraded.schema_status.version == 62
        assert upgraded.schema_status.migrated_from_version == 61
        ada = CurrentUser(id="ada", display_name="ada", login_identity="ada", role=UserRole.administrator, enabled=True)
        rae = CurrentUser(id="rae", display_name="rae", login_identity="rae", role=UserRole.administrator, enabled=True)
        for viewer in (ada, rae):
            assert _status(upgraded, viewer, ids["read"]) == "read"
            assert _status(upgraded, viewer, ids["dismissed"]) == "dismissed"
            assert _status(upgraded, viewer, ids["untouched"]) == "unread"
        # The shared legacy columns are cleared: nothing is shared any more.
        for alert_id in ids.values():
            row = _alert_row(upgraded, alert_id)
            assert row.legacy_global_read_at is None and row.legacy_global_dismissed_at is None
        with upgraded.session_factory() as session:
            ack = session.get(ProductAlertAcknowledgementModel, (ids["dismissed"], "ada"))
            assert ack is not None and ack.updated_at.replace(tzinfo=UTC) == datetime(2026, 9, 2, 10, tzinfo=UTC)

        # One user's later action no longer reaches the other.
        assert upgraded.mark_product_alert_read(ids["untouched"], user_id="ada")
        assert _status(upgraded, ada, ids["untouched"]) == "read"
        assert _status(upgraded, rae, ids["untouched"]) == "unread"
        # A user created after the upgrade inherits nothing.
        newcomer = _make_user(upgraded, "newcomer")
        assert _status(upgraded, newcomer, ids["read"]) == "unread"
        assert _status(upgraded, newcomer, ids["dismissed"]) == "unread"
    finally:
        upgraded.close()


def test_upgrade_with_no_users_keeps_legacy_state_for_the_bootstrap_administrator_only(tmp_path: Path) -> None:
    database_path = tmp_path / "pre-identity.sqlite3"
    ids = _rewind_to_61_with_legacy_state(database_path, tmp_path, users=[])

    upgraded = ProductRepository(db_url=f"sqlite:///{database_path}", media_root=tmp_path / "media")
    try:
        assert upgraded.schema_status.version == 62
        assert _ack_count(upgraded) == 0, "nobody existed to attribute the legacy state to"
        assert _alert_row(upgraded, ids["read"]).legacy_global_read_at is not None

        admin, _token = upgraded.create_first_administrator(
            AdministratorBootstrapRequest(display_name="Ada", login_identity="ada", password="correct horse battery")
        )
        assert _status(upgraded, admin, ids["read"]) == "read"
        assert _status(upgraded, admin, ids["dismissed"]) == "dismissed"
        assert _status(upgraded, admin, ids["untouched"]) == "unread"
        for alert_id in ids.values():
            row = _alert_row(upgraded, alert_id)
            assert row.legacy_global_read_at is None and row.legacy_global_dismissed_at is None

        second = _make_user(upgraded, "second", role=UserRole.reviewer)
        assert _status(upgraded, second, ids["read"]) == "unread", "adoption happens exactly once"
    finally:
        upgraded.close()


def test_the_migration_is_idempotent_when_the_table_already_exists(tmp_path: Path) -> None:
    database_path = tmp_path / "rerun.sqlite3"
    repository = ProductRepository(db_url=f"sqlite:///{database_path}", media_root=tmp_path / "media")
    try:
        user = _make_user(repository, "ada")
        alert_id = _add_alert(repository, "rerun")
        assert repository.dismiss_product_alert(alert_id, user_id=user.id)
        with repository.engine.begin() as connection:
            connection.exec_driver_sql("UPDATE mockingbird_schema SET version = 61 WHERE singleton_id = 1")
    finally:
        repository.close()
    reopened = ProductRepository(db_url=f"sqlite:///{database_path}", media_root=tmp_path / "media")
    try:
        assert reopened.schema_status.version == 62
        assert _ack_count(reopened) == 1
        assert _status(reopened, user, alert_id) == "dismissed"
    finally:
        reopened.close()


def test_backup_foreign_key_check_passes_with_acknowledgements(repository: ProductRepository) -> None:
    user = _make_user(repository, "ada")
    alert_id = _add_alert(repository, "fk")
    repository.mark_product_alert_read(alert_id, user_id=user.id)
    with repository.engine.connect() as connection:
        assert connection.execute(text("PRAGMA foreign_key_check(product_alert_acknowledgements)")).all() == []


# ---------------------------------------------------------------------------
# Multi-user isolation and preserved global lifecycle (repository)
# ---------------------------------------------------------------------------


def test_one_users_read_and_dismiss_never_change_another_users_view(repository: ProductRepository) -> None:
    ada = _make_user(repository, "ada")
    rae = _make_user(repository, "rae")
    first = _add_alert(repository, "iso:first")
    second = _add_alert(repository, "iso:second")
    before = _alert_row(repository, first)

    assert repository.product_alert_unread(viewer=ada).unread_count == 2
    assert repository.mark_product_alert_read(first, user_id=ada.id)
    assert repository.dismiss_product_alert(second, user_id=ada.id)

    ada_view = repository.product_alert_unread(viewer=ada)
    rae_view = repository.product_alert_unread(viewer=rae)
    assert ada_view.unread_count == 0
    assert [item.id for item in ada_view.recent] == [first], "dismissed leaves only this user's recent list"
    assert rae_view.unread_count == 2
    assert {item.id for item in rae_view.recent} == {first, second}
    assert all(item.status == "unread" and item.read_at is None for item in rae_view.recent)
    ada_first = next(item for item in ada_view.recent if item.id == first)
    assert ada_first.status == "read" and ada_first.read_at is not None

    # The shared alert row -- condition, timestamps, resolution -- is untouched.
    after = _alert_row(repository, first)
    assert (after.updated_at, after.resolved_at, after.condition_version, after.legacy_global_read_at) == (
        before.updated_at, before.resolved_at, before.condition_version, None,
    )


def test_acknowledgement_is_idempotent_and_bulk_read_is_bounded(repository: ProductRepository) -> None:
    ada = _make_user(repository, "ada")
    alert_id = _add_alert(repository, "idem")
    assert repository.mark_product_alert_read(alert_id, user_id=ada.id)
    with repository.session_factory() as session:
        first_read_at = session.get(ProductAlertAcknowledgementModel, (alert_id, ada.id)).read_at
    assert repository.mark_product_alert_read(alert_id, user_id=ada.id)
    with repository.session_factory() as session:
        assert session.get(ProductAlertAcknowledgementModel, (alert_id, ada.id)).read_at == first_read_at
    assert _ack_count(repository) == 1

    many = [_add_alert(repository, f"bulk:{index}") for index in range(55)]
    marked = repository.mark_product_alerts_read(many + ["missing-alert", " ", ""], user_id=ada.id)
    assert marked == 50
    assert repository.mark_product_alert_read("missing-alert", user_id=ada.id) is False
    assert repository.dismiss_product_alert("missing-alert", user_id=ada.id) is False
    with pytest.raises(ValueError, match="alert_acknowledgement_user_not_found"):
        repository.mark_product_alert_read(alert_id, user_id="no-such-user")


def test_reads_are_side_effect_free(repository: ProductRepository) -> None:
    ada = _make_user(repository, "ada")
    alert_id = _add_alert(repository, "readonly")
    before = _alert_row(repository, alert_id)
    repository.product_alert_unread(viewer=ada)
    repository.list_product_alerts(viewer=ada)
    repository.product_alert_unread()
    assert _ack_count(repository) == 0
    after = _alert_row(repository, alert_id)
    assert after.updated_at == before.updated_at


def test_global_dedup_version_and_resolution_semantics_are_preserved(repository: ProductRepository) -> None:
    ada = _make_user(repository, "ada")
    rae = _make_user(repository, "rae")
    first = _add_alert(repository, "life", fingerprint="v1")
    repository.mark_product_alert_read(first, user_id=ada.id)

    # Same fingerprint: refreshed in place, still one alert, Ada's read kept.
    assert _add_alert(repository, "life", fingerprint="v1", at=NOW + timedelta(minutes=5)) == first
    assert _status(repository, ada, first) == "read"

    # Changed fingerprint: the old version resolves for everyone; the new
    # version is a new condition and unread for everyone, Ada included.
    second = _add_alert(repository, "life", fingerprint="v2", at=NOW + timedelta(minutes=10))
    assert second != first
    assert _alert_row(repository, first).resolved_at is not None
    for viewer in (ada, rae):
        assert _status(repository, viewer, second) == "unread"
        assert _status(repository, viewer, first) == "resolved"
    # Resolved alerts never count as unread, whatever a user did.
    assert repository.product_alert_unread(viewer=rae).unread_count == 1

    # A dismissal still outranks resolution in that user's own view only.
    repository.dismiss_product_alert(first, user_id=rae.id)
    assert _status(repository, rae, first) == "dismissed"
    assert _status(repository, ada, first) == "resolved"


def test_viewer_role_ceiling_and_preferences_still_apply(repository: ProductRepository) -> None:
    viewer = _make_user(repository, "vic", role=UserRole.viewer)
    review = _add_alert(repository, "review:v", category=AlertCategory.review)
    storage = _add_alert(repository, "storage:v")
    unread = repository.product_alert_unread(viewer=viewer)
    assert {item.id for item in unread.recent} == {storage}
    assert review not in {item.id for item in repository.list_product_alerts(viewer=viewer).items}


def test_camera_health_open_alert_fact_is_global_not_acknowledgement(repository: ProductRepository) -> None:
    stream = repository.list_streams()[0]
    ada = _make_user(repository, "ada")
    with repository.session_factory() as session:
        with session.begin():
            alert = repository._refresh_product_alert(  # noqa: SLF001
                session, category=AlertCategory.monitoring, severity=AlertSeverity.warning, title="Camera",
                message="Camera needs attention.", deduplication_key=f"monitoring:{stream.id}:x",
                condition_fingerprint="x", action_type=AlertActionType.open_stream, action_parameters={},
                now=NOW, stream_id=stream.id, source_id=stream.source_id,
            )
            session.flush()
            alert_id = alert.id
    repository.dismiss_product_alert(alert_id, user_id=ada.id)
    health = repository.get_stream_camera_health(stream.id).health
    assert health.unread_alert is True, "one user's dismissal must not hide the open camera alert for others"


# ---------------------------------------------------------------------------
# API: authorization and per-user isolation over real HTTP
# ---------------------------------------------------------------------------


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def api_repository(tmp_path: Path) -> ProductRepository:
    product_repository = ProductRepository(
        db_url=f"sqlite:///{tmp_path / 'api.sqlite3'}",
        media_root=tmp_path / "media",
    )
    configure_repository(product_repository)
    yield product_repository
    configure_repository(None)
    product_repository.close()


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver")


@pytest.mark.anyio
async def test_alert_acknowledgement_over_http_is_per_signed_in_user(api_repository: ProductRepository) -> None:
    alert_id = _add_alert(api_repository, "http:iso")
    async with _client() as ada, _client() as vic, _client() as anonymous:
        assert (await ada.post(
            "/api/setup/administrator",
            json={"display_name": "Ada", "login_identity": "ada", "password": "correct horse battery"},
        )).status_code == 201
        created = await ada.post(
            "/api/admin/users",
            json={"display_name": "Vic", "login_identity": "vic", "password": "viewer-password-1", "role": "viewer"},
        )
        assert created.status_code == 201, created.text
        assert (await vic.post(
            "/api/auth/sign-in", json={"login_identity": "vic", "password": "viewer-password-1"}
        )).status_code == 200

        # Unauthenticated callers can neither read nor acknowledge.
        assert (await anonymous.get("/api/alerts/unread")).status_code == 401
        assert (await anonymous.post(f"/api/alerts/{alert_id}/read")).status_code == 401
        assert (await anonymous.post(f"/api/alerts/{alert_id}/dismiss")).status_code == 401
        assert (await anonymous.post("/api/alerts/read-visible", json={"alert_ids": [alert_id]})).status_code == 401

        assert (await vic.get("/api/alerts/unread")).json()["unread_count"] == 1
        read = await ada.post(f"/api/alerts/{alert_id}/read")
        assert read.status_code == 200
        assert read.json()["unread_count"] == 0, "the mutation returns the caller's own refreshed summary"
        assert (await vic.get("/api/alerts/unread")).json()["unread_count"] == 1

        # A Viewer can acknowledge their own attention (Viewer floor), and
        # it stays theirs.
        dismissed = await vic.post(f"/api/alerts/{alert_id}/dismiss")
        assert dismissed.status_code == 200
        assert dismissed.json()["recent"] == []
        ada_recent = (await ada.get("/api/alerts/unread")).json()["recent"]
        assert [item["status"] for item in ada_recent] == ["read"]

        assert (await ada.post("/api/alerts/does-not-exist/read")).status_code == 404
        assert (await ada.post("/api/alerts/does-not-exist/dismiss")).status_code == 404
        bulk = await ada.post("/api/alerts/read-visible", json={"alert_ids": [alert_id, "does-not-exist"]})
        assert bulk.status_code == 200

        listed = (await vic.get("/api/alerts?page_size=5")).json()["items"]
        assert [item["status"] for item in listed] == ["dismissed"]


@pytest.mark.anyio
async def test_field_acceptance_bearer_token_cannot_acknowledge_alerts(api_repository: ProductRepository) -> None:
    """The field-acceptance credential is not a human user, so it has no
    acknowledgement of its own to record; it must never write a shared one."""

    alert_id = _add_alert(api_repository, "http:bearer")
    async with _client() as ada:
        assert (await ada.post(
            "/api/setup/administrator",
            json={"display_name": "Ada", "login_identity": "ada", "password": "correct horse battery"},
        )).status_code == 201
        credential = await ada.post(
            "/api/admin/field-acceptance-credentials", json={"label": "Operator", "expires_in_hours": 1}
        )
        assert credential.status_code == 201, credential.text
        token = credential.json()["token"]
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver",
        headers={"Authorization": f"Bearer {token}"},
    ) as bearer:
        assert (await bearer.post(f"/api/alerts/{alert_id}/read")).status_code == 401
        assert (await bearer.post(f"/api/alerts/{alert_id}/dismiss")).status_code == 401
    assert _ack_count(api_repository) == 0


# ---------------------------------------------------------------------------
# Model/runtime Observatory Health alert
# ---------------------------------------------------------------------------


def _detector_missing() -> ModelRuntimeHealthFact:
    return ModelRuntimeHealthFact(
        kind=ModelRuntimeHealthKind.detector_model, code="doctor_detector_model",
        message="No detector model bundle is installed.",
    )


def test_monitor_requires_a_sustained_condition_and_resolves_on_a_clean_evaluation() -> None:
    monitor = ModelRuntimeHealthMonitor(sustain_seconds=120)
    first = monitor.evaluate([_detector_missing()], now=NOW)
    assert first.sustained == () and ModelRuntimeHealthKind.detector_model not in first.cleared
    too_soon = monitor.evaluate([_detector_missing()], now=NOW + timedelta(seconds=30))
    assert too_soon.sustained == ()
    sustained = monitor.evaluate([_detector_missing()], now=NOW + timedelta(seconds=150))
    assert [condition.kind for condition in sustained.sustained] == [ModelRuntimeHealthKind.detector_model]
    assert sustained.sustained[0].first_observed_at == NOW
    assert ModelRuntimeHealthKind.species_model in sustained.cleared

    clean = monitor.evaluate([], now=NOW + timedelta(seconds=200))
    assert clean.sustained == () and ModelRuntimeHealthKind.detector_model in clean.cleared
    # A single later blip does not immediately re-alert.
    assert monitor.evaluate([_detector_missing()], now=NOW + timedelta(hours=1)).sustained == ()


def test_monitor_prefers_the_stream_scoped_runtime_fact_within_a_kind() -> None:
    monitor = ModelRuntimeHealthMonitor(sustain_seconds=0)
    stream_fact = ModelRuntimeHealthFact(
        kind=ModelRuntimeHealthKind.detector_model, code="invalid_model_bundle",
        message="Feeder: model bundle missing.", stream_id="stream-b",
    )
    other_stream = ModelRuntimeHealthFact(
        kind=ModelRuntimeHealthKind.detector_model, code="invalid_model_bundle",
        message="Porch: model bundle missing.", stream_id="stream-z",
    )
    monitor.evaluate([_detector_missing(), other_stream, stream_fact], now=NOW)
    evaluation = monitor.evaluate([_detector_missing(), other_stream, stream_fact], now=NOW + timedelta(seconds=1))
    assert len(evaluation.sustained) == 1 and evaluation.sustained[0].stream_id == "stream-b"


def _health_alerts(repository: ProductRepository, kind: str = "detector_model") -> list[ProductAlertModel]:
    with repository.session_factory() as session:
        return list(session.scalars(
            select(ProductAlertModel)
            .where(ProductAlertModel.deduplication_key == f"observatory-health:model-runtime:{kind}")
            .order_by(ProductAlertModel.condition_version)
        ).all())


def _sync(repository: ProductRepository, monitor: ModelRuntimeHealthMonitor, facts, at: datetime) -> None:
    repository.sync_model_runtime_health_alerts(monitor.evaluate(facts, now=at), now=at)


def test_model_runtime_alert_is_sustained_deduplicated_versioned_and_self_resolving(
    repository: ProductRepository,
) -> None:
    monitor = ModelRuntimeHealthMonitor(sustain_seconds=60)
    with repository.engine.connect() as connection:
        labels_before = connection.execute(text("SELECT count(*) FROM review_labels")).scalar_one()
        visits_before = connection.execute(text("SELECT count(*) FROM visits")).scalar_one()
    admin = _make_user(repository, "ada")
    viewer = _make_user(repository, "vic", role=UserRole.viewer)

    _sync(repository, monitor, [_detector_missing()], NOW)
    assert _health_alerts(repository) == [], "one observation is not sustained"
    _sync(repository, monitor, [_detector_missing()], NOW + timedelta(minutes=15))
    _sync(repository, monitor, [_detector_missing()], NOW + timedelta(minutes=30))
    alerts = _health_alerts(repository)
    assert len(alerts) == 1 and alerts[0].resolved_at is None
    assert alerts[0].category == AlertCategory.monitoring.value
    assert alerts[0].severity == AlertSeverity.warning.value
    presented = next(
        item for item in repository.list_product_alerts(viewer=viewer).items if item.id == alerts[0].id
    )
    assert presented.action.action_type == AlertActionType.open_doctor
    assert presented.attention_category.value == "observatory_health"

    # The underlying problem changes to a real Stream failing to start:
    # a new condition version that opens that Stream, at high severity.
    stream = repository.list_streams()[0]
    runtime_fact = ModelRuntimeHealthFact(
        kind=ModelRuntimeHealthKind.detector_model, code="invalid_model_bundle",
        message=f"{stream.name}: The Observation Engine's model bundle is missing or invalid.", stream_id=stream.id,
    )
    _sync(repository, monitor, [_detector_missing(), runtime_fact], NOW + timedelta(minutes=45))
    alerts = _health_alerts(repository)
    assert len(alerts) == 2 and alerts[0].resolved_at is not None and alerts[1].resolved_at is None
    assert alerts[1].severity == AlertSeverity.high.value and alerts[1].stream_id == stream.id
    presented = next(
        item for item in repository.list_product_alerts(viewer=admin).items if item.id == alerts[1].id
    )
    assert presented.action.action_type == AlertActionType.open_stream and presented.action.stream_id == stream.id
    assert presented.urgency.value == "immediate"

    # If that Stream disappears, the action falls back to Doctor, not storage.
    with repository.engine.begin() as connection:
        connection.exec_driver_sql(
            "UPDATE product_alerts SET stream_id = 'stream-gone' WHERE id = ?", (alerts[1].id,)
        )
    fallback = next(item for item in repository.list_product_alerts(viewer=admin).items if item.id == alerts[1].id)
    assert fallback.action.action_type == AlertActionType.open_doctor

    # A clean evaluation resolves it automatically, for everyone.
    _sync(repository, monitor, [], NOW + timedelta(hours=1))
    assert all(alert.resolved_at is not None for alert in _health_alerts(repository))
    assert repository.product_alert_unread(viewer=admin).unread_count == 0

    # It is attention only: no review label or Visit was written.
    with repository.engine.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM review_labels")).scalar_one() == labels_before
        assert connection.execute(text("SELECT count(*) FROM visits")).scalar_one() == visits_before


def test_distinct_model_runtime_kinds_never_hide_each_other(repository: ProductRepository) -> None:
    monitor = ModelRuntimeHealthMonitor(sustain_seconds=0)
    species = ModelRuntimeHealthFact(
        kind=ModelRuntimeHealthKind.species_model, code="doctor_species_identification",
        message="BioCLIP runtime unavailable.",
    )
    for offset in (0, 1):
        _sync(repository, monitor, [_detector_missing(), species], NOW + timedelta(seconds=offset))
    assert len(_health_alerts(repository, "detector_model")) == 1
    assert len(_health_alerts(repository, "species_model")) == 1
    _sync(repository, monitor, [species], NOW + timedelta(seconds=2))
    assert _health_alerts(repository, "detector_model")[0].resolved_at is not None
    assert _health_alerts(repository, "species_model")[0].resolved_at is None


def _doctor_result(code: DoctorCheckCode, status: DoctorStatus, summary: str) -> DoctorCheckResult:
    return DoctorCheckResult(code=code, component=code.value, status=status, summary=summary)


def test_gather_reads_only_completed_non_passing_doctor_checks(
    repository: ProductRepository, monkeypatch: pytest.MonkeyPatch,
) -> None:
    checks = [
        (_doctor_result(DoctorCheckCode.DETECTOR_MODEL, DoctorStatus.WARN, "No detector model bundle is installed."), True),
        (_doctor_result(DoctorCheckCode.SPECIES_IDENTIFICATION, DoctorStatus.PASS, "BioCLIP available."), True),
        (_doctor_result(DoctorCheckCode.GPU_CUDA, DoctorStatus.PASS, "CUDA is not available."), True),
    ]
    monkeypatch.setattr(api_main, "model_runtime_health_checks", lambda **_: checks)
    monkeypatch.setattr(api_main, "_observation_engine_session_manager", None)
    facts = api_main._gather_model_runtime_health_facts(repository)
    assert [(fact.kind, fact.code) for fact in facts] == [
        (ModelRuntimeHealthKind.detector_model, "doctor_detector_model")
    ]

    # An incomplete check is never read as healthy: the pass fails instead,
    # so an existing alert is not wrongly resolved.
    checks[0] = (checks[0][0], False)
    with pytest.raises(RuntimeError, match="model_runtime_health_check_incomplete"):
        api_main._gather_model_runtime_health_facts(repository)


def test_gather_reads_observation_engine_start_failure_categories(
    repository: ProductRepository, monkeypatch: pytest.MonkeyPatch,
) -> None:
    stream = repository.list_streams()[0]

    class _Status:
        def __init__(self, state: str, category: str | None) -> None:
            self.state = state
            self.engine_message = "The Observation Engine could not start."
            self.advanced = {"engine_error_category": category, "engine_error_code": "onnx_cuda_unavailable"} if category else {}

    class _Manager:
        def __init__(self, status: _Status | None) -> None:
            self._status = status

        def status(self, stream_id: str) -> _Status | None:
            return self._status if stream_id == stream.id else None

    monkeypatch.setattr(api_main, "model_runtime_health_checks", lambda **_: [])
    monkeypatch.setattr(api_main, "_observation_engine_session_manager", _Manager(_Status("error", "unsupported_gpu")))
    facts = api_main._gather_model_runtime_health_facts(repository)
    assert [(fact.kind, fact.stream_id, fact.code) for fact in facts] == [
        (ModelRuntimeHealthKind.gpu_runtime, stream.id, "onnx_cuda_unavailable")
    ]
    # A generic failure or a non-error session is not a model/runtime fact.
    monkeypatch.setattr(api_main, "_observation_engine_session_manager", _Manager(_Status("error", "failed")))
    assert api_main._gather_model_runtime_health_facts(repository) == []
    monkeypatch.setattr(api_main, "_observation_engine_session_manager", _Manager(_Status("observing", None)))
    assert api_main._gather_model_runtime_health_facts(repository) == []


# ---------------------------------------------------------------------------
# Attention-sync diagnostics: failure and recovery
# ---------------------------------------------------------------------------


def test_sync_diagnostics_distinguish_failing_from_quiet_and_recover() -> None:
    clock = iter(NOW + timedelta(minutes=index) for index in range(20))
    outcomes: list[BaseException | None] = [None, OperationalError("SELECT", {}, sqlite3.OperationalError("locked")), RuntimeError("boom /secret/path"), None]

    def run_sync() -> None:
        outcome = outcomes.pop(0)
        if outcome is not None:
            raise outcome

    service = AttentionSyncService(run_sync=run_sync, clock=lambda: next(clock))
    pending = service.diagnostics()
    assert pending.last_attempt_at is None and pending.success_count == 0 and pending.failure_count == 0

    service.run_once()
    healthy = service.diagnostics()
    assert healthy.success_count == 1 and healthy.consecutive_failure_count == 0 and healthy.last_error_code is None

    service.run_once()
    service.run_once()
    failing = service.diagnostics()
    assert failing.consecutive_failure_count == 2 and failing.failure_count == 2
    assert failing.last_error_code == "attention_sync_failed"
    assert failing.last_error_type == "RuntimeError"
    assert "/secret/path" not in (failing.last_error_message or "")
    assert failing.last_success_at == healthy.last_success_at

    service.run_once()
    recovered = service.diagnostics()
    assert recovered.consecutive_failure_count == 0 and recovered.success_count == 2 and recovered.failure_count == 2
    assert recovered.last_error_code == "attention_sync_failed", "the last failure stays visible for support"


def test_database_errors_get_their_own_registered_code() -> None:
    def run_sync() -> None:
        raise OperationalError("SELECT", {}, sqlite3.OperationalError("database is locked"))

    service = AttentionSyncService(run_sync=run_sync)
    service.run_once()
    assert service.diagnostics().last_error_code == "attention_sync_database_error"
    assert "database" in (service.diagnostics().last_error_message or "")


def test_overlapping_tick_is_not_counted_as_an_attempt() -> None:
    entered, release = threading.Event(), threading.Event()

    def run_sync() -> None:
        entered.set()
        release.wait(timeout=2)

    service = AttentionSyncService(run_sync=run_sync)
    worker = threading.Thread(target=service.run_once)
    worker.start()
    assert entered.wait(timeout=2)
    service.run_once()
    release.set()
    worker.join(timeout=2)
    assert service.diagnostics().success_count == 1


def test_run_attention_sync_runs_both_steps_and_reraises_the_first_failure(
    repository: ProductRepository, monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    def failing_place_sync(*_args, **_kwargs) -> None:
        calls.append("place")
        raise RuntimeError("place story unavailable")

    monkeypatch.setattr(api_main, "get_repository", lambda: repository)
    monkeypatch.setattr(repository, "sync_attention_signals", failing_place_sync)
    monkeypatch.setattr(api_main, "_gather_model_runtime_health_facts", lambda _repo: calls.append("health") or [])
    with pytest.raises(RuntimeError, match="place story unavailable"):
        api_main._run_attention_sync()
    assert calls == ["place", "health"], "a place-sync failure must not starve the health step"


@pytest.mark.anyio
async def test_product_health_exposes_attention_sync_state_without_side_effects(
    api_repository: ProductRepository, monkeypatch: pytest.MonkeyPatch,
) -> None:
    def run_sync() -> None:
        raise RuntimeError("reconciliation failed")

    service = AttentionSyncService(run_sync=run_sync)
    monkeypatch.setattr(api_main, "_attention_sync_service", service)
    async with _client() as ada:
        assert (await ada.post(
            "/api/setup/administrator",
            json={"display_name": "Ada", "login_identity": "ada", "password": "correct horse battery"},
        )).status_code == 201
        pending = (await ada.get("/api/product/health")).json()["attention_sync"]
        assert pending["status"] == "pending" and pending["failure_count"] == 0
        service.run_once()
        failing = (await ada.get("/api/product/health")).json()["attention_sync"]
        assert failing["status"] == "failing"
        assert failing["consecutive_failure_count"] == 1
        assert failing["last_error_code"] == "attention_sync_failed"
        assert "last_error_type" not in failing
        # Reading health twice never triggered another sync attempt.
        again = (await ada.get("/api/product/health")).json()["attention_sync"]
        assert again["failure_count"] == 1 and again["last_attempt_at"] == failing["last_attempt_at"]
