"""GET /api/product/health: one bounded, basic-first status aggregate.

Exercises the aggregation logic added in api/main.py directly (via a minimal
stand-in for `dashboard_summary`'s return value, matching Python's duck
typing rather than constructing a full DashboardSummary), since the
underlying camera-health state machine and backup mechanics already have
their own focused test coverage in test_camera_health.py and
test_local_backup_recovery.py.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
import types

import httpx
import pytest

from mockingbird.api import main as api_main
from mockingbird.api.main import app
from mockingbird.api.schemas import CameraHealthState
from mockingbird.repository.product_repository import ProductRepository
from mockingbird import runtime_state


def _repository(tmp_path: Path) -> ProductRepository:
    return ProductRepository(
        db_url=f"sqlite:///{tmp_path / 'mockingbird.sqlite3'}",
        media_root=tmp_path / "media",
    )


def _get(path: str) -> httpx.Response:
    async def send() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.get(path)

    return asyncio.run(send())


def _fake_dashboard_summary(
    *, camera_states: list[CameraHealthState], configured: int, monitored: int, real: int | None = None,
):
    cameras = [types.SimpleNamespace(state=state) for state in camera_states]
    return types.SimpleNamespace(
        today=types.SimpleNamespace(observation_health=cameras),
        headline=types.SimpleNamespace(
            configured_stream_count=configured,
            # Defaults to `configured` (no demo stream in play) unless a
            # test explicitly wants to exercise the two counts diverging --
            # see test_stream_playback_contract.py's
            # test_real_stream_count_excludes_the_lingering_demo_stream for
            # that real-query-level coverage; this file only stubs the
            # aggregation `get_product_health` performs on top.
            real_stream_count=configured if real is None else real,
            monitored_stream_count=monitored,
        ),
    )


@pytest.fixture
def isolated_repository(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> ProductRepository:
    repository = _repository(tmp_path)
    monkeypatch.setattr(api_main, "_repository", repository)
    return repository


def test_product_health_ready_with_no_cameras_needing_attention(
    isolated_repository: ProductRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        isolated_repository,
        "dashboard_summary",
        lambda *_args, **_kwargs: _fake_dashboard_summary(
            camera_states=[CameraHealthState.healthy, CameraHealthState.stopped],
            configured=2,
            monitored=1,
        ),
    )

    response = _get("/api/product/health")

    assert response.status_code == 200
    body = response.json()
    assert body["ready"] is True
    assert body["cameras"]["needs_attention_count"] == 0
    assert body["observation"] == {"configured_stream_count": 2, "monitored_stream_count": 1}
    assert body["app_version"]
    assert body["database_schema_version"] >= 1
    assert "generated_at" in body


def test_product_health_counts_cameras_needing_attention(
    isolated_repository: ProductRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        isolated_repository,
        "dashboard_summary",
        lambda *_args, **_kwargs: _fake_dashboard_summary(
            camera_states=[
                CameraHealthState.healthy,
                CameraHealthState.camera_unavailable,
                CameraHealthState.no_recent_frame,
            ],
            configured=3,
            monitored=1,
        ),
    )

    response = _get("/api/product/health")

    body = response.json()
    assert body["ready"] is False
    assert body["cameras"]["needs_attention_count"] == 2
    assert "camera" in body["message"].lower()


def test_product_health_reports_storage_not_writable(
    isolated_repository: ProductRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        isolated_repository,
        "dashboard_summary",
        lambda *_args, **_kwargs: _fake_dashboard_summary(camera_states=[], configured=0, monitored=0),
    )
    original_storage_summary = isolated_repository.storage_summary

    def unwritable_storage_summary():
        summary = original_storage_summary()
        return summary.model_copy(update={"is_writable": False, "storage_warning": "not writable"})

    monkeypatch.setattr(isolated_repository, "storage_summary", unwritable_storage_summary)

    response = _get("/api/product/health")

    body = response.json()
    assert body["ready"] is False
    assert body["storage_writable"] is False


def test_product_health_reflects_backup_status(
    isolated_repository: ProductRepository,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from mockingbird.storage.backup import LocalBackupManager

    monkeypatch.setattr(
        isolated_repository,
        "dashboard_summary",
        lambda *_args, **_kwargs: _fake_dashboard_summary(camera_states=[], configured=0, monitored=0),
    )
    monkeypatch.setattr(
        api_main,
        "_local_backup_manager",
        lambda _repository=None: LocalBackupManager(
            db_url=isolated_repository.db_url,
            media_root=isolated_repository.media_root,
            backup_root=tmp_path / "backups",
        ),
    )

    before = _get("/api/product/health").json()
    assert before["backup"] == {
        "has_backup": False,
        "last_backup_at": None,
        "last_backup_verified": None,
        # A brand-new test database seeds setup_state.completed=False (see
        # AppSetupStateModel), so the nudge deliberately stays quiet during
        # onboarding even though no backup exists yet.
        "suggest_first_backup": False,
    }

    LocalBackupManager(
        db_url=isolated_repository.db_url,
        media_root=isolated_repository.media_root,
        backup_root=tmp_path / "backups",
    ).create_backup()

    after = _get("/api/product/health").json()
    assert after["backup"]["has_backup"] is True
    # `list_backups` deliberately reports "not_checked" for a plain listing
    # (re-verifying every archive's checksums on every list would be
    # expensive); explicit verification is its own existing action. This
    # widget must reflect that honestly rather than claim "verified".
    assert after["backup"]["last_backup_verified"] is False
    assert after["backup"]["last_backup_at"] is not None
    assert after["backup"]["suggest_first_backup"] is False


def test_product_health_suggests_a_first_backup_once_setup_is_complete_and_none_exists(
    isolated_repository: ProductRepository,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Calm, non-nagging backup-awareness nudge (v0.1 Release Hardening
    v1): a user could otherwise operate MockingBird for weeks without
    realizing backups exist (docs/local-backup-recovery-design.md). The
    nudge is a computed fact, not a persisted/scheduled alert -- it appears
    only once onboarding is genuinely finished (not mid-wizard) and no
    backup has ever been created, and disappears the moment one exists."""

    from mockingbird.api.schemas import SetupStateUpdate
    from mockingbird.storage.backup import LocalBackupManager

    monkeypatch.setattr(
        isolated_repository,
        "dashboard_summary",
        lambda *_args, **_kwargs: _fake_dashboard_summary(camera_states=[], configured=0, monitored=0),
    )
    monkeypatch.setattr(
        api_main,
        "_local_backup_manager",
        lambda _repository=None: LocalBackupManager(
            db_url=isolated_repository.db_url,
            media_root=isolated_repository.media_root,
            backup_root=tmp_path / "backups",
        ),
    )

    mid_onboarding = _get("/api/product/health").json()
    assert mid_onboarding["backup"]["suggest_first_backup"] is False, (
        "must not nag a user who has not even finished first-run setup yet"
    )

    isolated_repository.update_setup_state(
        SetupStateUpdate(current_step="done", completed=True, last_created_stream_id=None)
    )
    completed_no_backup = _get("/api/product/health").json()
    assert completed_no_backup["backup"]["suggest_first_backup"] is True

    LocalBackupManager(
        db_url=isolated_repository.db_url,
        media_root=isolated_repository.media_root,
        backup_root=tmp_path / "backups",
    ).create_backup()
    completed_with_backup = _get("/api/product/health").json()
    assert completed_with_backup["backup"]["suggest_first_backup"] is False, (
        "must stop suggesting the instant a backup actually exists"
    )


def test_product_health_reports_previous_shutdown_marker(
    isolated_repository: ProductRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        isolated_repository,
        "dashboard_summary",
        lambda *_args, **_kwargs: _fake_dashboard_summary(camera_states=[], configured=0, monitored=0),
    )
    monkeypatch.setattr(runtime_state, "_previous_shutdown_clean", False)

    response = _get("/api/product/health")

    assert response.json()["previous_shutdown_clean"] is False


def test_product_health_never_includes_credential_shaped_values(
    isolated_repository: ProductRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        isolated_repository,
        "dashboard_summary",
        lambda *_args, **_kwargs: _fake_dashboard_summary(camera_states=[], configured=0, monitored=0),
    )

    response_text = _get("/api/product/health").text.lower()

    for forbidden in ("credential", "bearer", "password", "api_key", "secret"):
        assert forbidden not in response_text


def test_product_health_reports_export_policy_versions_and_camera_node_service_version(
    isolated_repository: ProductRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """First-Hour Onboarding + Whole-Product Observability Closure v1
    ("C5 version reporting"): a support conversation needs one API
    response that answers "which export policy version, and which paired
    Camera Node software version, is this installation actually running,"
    reusing the already-accepted constants/durable column rather than a
    second implementation."""

    monkeypatch.setattr(
        isolated_repository,
        "dashboard_summary",
        lambda *_args, **_kwargs: _fake_dashboard_summary(camera_states=[], configured=0, monitored=0),
    )
    monkeypatch.setattr(isolated_repository, "most_recent_camera_node_service_version", lambda: "1.4.0")

    body = _get("/api/product/health").json()

    assert body["research_export_schema_version"] == "research-export-v1"
    assert body["camtrap_dp_profile_version"] == "1.0.2"
    assert body["camera_node_service_version"] == "1.4.0"


def test_most_recent_camera_node_service_version_is_none_when_never_reported(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    try:
        assert repository.most_recent_camera_node_service_version() is None
    finally:
        repository.close()


def test_most_recent_camera_node_service_version_reads_a_real_paired_camera_node(tmp_path: Path) -> None:
    from mockingbird.storage.models import CameraSourceModel

    repository = _repository(tmp_path)
    try:
        with repository.session_factory() as session, session.begin():
            session.add(
                CameraSourceModel(
                    id="source-real-camera-node",
                    name="Real Camera Node",
                    kind="integration",
                    status="connected",
                    description="Real paired Camera Node fixture.",
                    camera_node_service_version="1.4.0",
                )
            )
        assert repository.most_recent_camera_node_service_version() == "1.4.0"
    finally:
        repository.close()
