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


def test_product_health_singular_camera_message_is_grammatical(
    isolated_repository: ProductRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Regression test for a real subject-verb agreement bug: the singular
    # branch (exactly one camera needing attention) previously read "1
    # camera need attention." -- the noun pluralized correctly but the verb
    # never did. Only reachable when the count is exactly 1, so the
    # multi-camera test above (which asserts only a loose substring) never
    # caught it.
    monkeypatch.setattr(
        isolated_repository,
        "dashboard_summary",
        lambda *_args, **_kwargs: _fake_dashboard_summary(
            camera_states=[CameraHealthState.healthy, CameraHealthState.camera_unavailable],
            configured=2,
            monitored=1,
        ),
    )

    response = _get("/api/product/health")

    body = response.json()
    assert body["cameras"]["needs_attention_count"] == 1
    assert body["message"] == "1 camera needs attention."


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
    # Appliance / Storage / Privacy / Recovery v1: `create_backup` already
    # ran a real, full verification internally and durably recorded that
    # fact (see `LocalBackupManager._write_verified_marker`) -- `list_
    # backups` now reads that back honestly instead of always claiming
    # "not_checked" regardless of whether this backup was ever verified.
    # This still costs no re-hashing on every list call.
    assert after["backup"]["last_backup_verified"] is True
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
    # Appliance / Storage / Privacy / Recovery v1, Phase N: fixed
    # compatibility constants, not live re-checks -- see
    # docs/appliance-storage-privacy-recovery-v1-contract.md.
    assert body["backup_format_version"] == 1
    assert body["camera_node_api_version"] == "v1"
    assert body["transport_protocol_version"] == "transport/v1"


def test_most_recent_camera_node_service_version_is_none_when_never_reported(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    try:
        assert repository.most_recent_camera_node_service_version() is None
    finally:
        repository.close()


def _add_microphone_source(
    repository: ProductRepository, *, device: str | None, capture_consent: str | None,
) -> None:
    """Configures a real `microphone` Source provider via the same
    `update_source_provider_configuration` path Settings uses -- not a raw
    model insert -- so this exercises the real config-sanitization/storage
    shape `_microphone_config_for_stream` reads back."""

    from mockingbird.api.schemas import SourceKind, SourceProviderConfigurationUpdate, SourceStatus
    from mockingbird.storage.models import CameraSourceModel, StreamModel

    source_id, stream_id = "source-acoustic-health", "stream-acoustic-health"
    with repository.session_factory() as session, session.begin():
        session.add(
            CameraSourceModel(
                id=source_id,
                name="Acoustic Health Fixture",
                kind=SourceKind.manual_upload.value,
                status=SourceStatus.connected.value,
                description="Fixture source for GET /api/product/health acoustic status.",
            )
        )
        session.add(
            StreamModel(
                id=stream_id, source_id=source_id, name="Acoustic Health Fixture Stream",
                description="Fixture stream", is_live=False,
            )
        )
    config: dict[str, str] = {}
    if device is not None:
        config["device"] = device
    if capture_consent is not None:
        config["capture_consent"] = capture_consent
    repository.update_source_provider_configuration(
        source_id,
        SourceProviderConfigurationUpdate(provider_key="microphone", config=config),
    )


def test_product_health_acoustic_not_configured_by_default(
    isolated_repository: ProductRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Whole-Product UI / Accessibility / Performance Closure v1: baseline
    state with no microphone Source configured anywhere."""

    monkeypatch.setattr(
        isolated_repository, "dashboard_summary",
        lambda *_args, **_kwargs: _fake_dashboard_summary(camera_states=[], configured=0, monitored=0),
    )

    body = _get("/api/product/health").json()

    assert body["acoustic"] == {
        "configured": False,
        "status": "not_configured",
        "detail": (
            "No microphone is configured for any camera. Acoustic identification is "
            "optional -- visual observation is unaffected."
        ),
    }
    # Never a factor in overall readiness -- acoustic is optional.
    assert body["ready"] is True


def test_product_health_acoustic_microphone_unavailable_without_consent(
    isolated_repository: ProductRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        isolated_repository, "dashboard_summary",
        lambda *_args, **_kwargs: _fake_dashboard_summary(camera_states=[], configured=0, monitored=0),
    )
    _add_microphone_source(isolated_repository, device="default", capture_consent=None)

    body = _get("/api/product/health").json()

    assert body["acoustic"]["configured"] is True
    assert body["acoustic"]["status"] == "microphone_unavailable"
    assert "consent" in body["acoustic"]["detail"].lower()
    assert body["ready"] is True


def test_product_health_acoustic_model_unavailable(
    isolated_repository: ProductRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        isolated_repository, "dashboard_summary",
        lambda *_args, **_kwargs: _fake_dashboard_summary(camera_states=[], configured=0, monitored=0),
    )
    _add_microphone_source(isolated_repository, device="default", capture_consent="true")
    monkeypatch.setattr(
        api_main, "get_birdnet_status",
        lambda: types.SimpleNamespace(
            status="unavailable", runtime_available=False, detail="Optional BirdNET runtime dependencies are unavailable.",
        ),
    )

    body = _get("/api/product/health").json()

    assert body["acoustic"]["configured"] is True
    assert body["acoustic"]["status"] == "model_unavailable"
    assert "BirdNET" in body["acoustic"]["detail"]
    assert body["ready"] is True


def test_product_health_acoustic_healthy(
    isolated_repository: ProductRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        isolated_repository, "dashboard_summary",
        lambda *_args, **_kwargs: _fake_dashboard_summary(camera_states=[], configured=0, monitored=0),
    )
    _add_microphone_source(isolated_repository, device="default", capture_consent="true")
    monkeypatch.setattr(
        api_main, "get_birdnet_status",
        lambda: types.SimpleNamespace(status="available", runtime_available=True, detail="ready"),
    )

    body = _get("/api/product/health").json()

    assert body["acoustic"] == {
        "configured": True,
        "status": "healthy",
        "detail": "A microphone and the BirdNET model are both available.",
    }
    assert body["ready"] is True


def test_product_health_acoustic_degraded_after_recent_analysis_failures(
    isolated_repository: ProductRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reuses the existing `acoustic_analysis_queue_diagnostics` 24h-failure
    signal (already covered by its own dedicated tests) -- this test only
    proves `_acoustic_health_summary` reacts to it correctly, so a synthetic
    stand-in for its return value is appropriate here, mirroring how this
    file already stands in for `dashboard_summary`."""

    from mockingbird.repository.product_repository import AcousticQueueDiagnostics

    monkeypatch.setattr(
        isolated_repository, "dashboard_summary",
        lambda *_args, **_kwargs: _fake_dashboard_summary(camera_states=[], configured=0, monitored=0),
    )
    _add_microphone_source(isolated_repository, device="default", capture_consent="true")
    monkeypatch.setattr(
        api_main, "get_birdnet_status",
        lambda: types.SimpleNamespace(status="available", runtime_available=True, detail="ready"),
    )
    monkeypatch.setattr(
        isolated_repository,
        "acoustic_analysis_queue_diagnostics",
        lambda *_args, **_kwargs: AcousticQueueDiagnostics(
            queued_count=0, processing_count=0, oldest_queued_age_seconds=None,
            recent_failure_count_24h=3, recent_capacity_evicted_count_24h=0,
        ),
    )

    body = _get("/api/product/health").json()

    assert body["acoustic"]["configured"] is True
    assert body["acoustic"]["status"] == "degraded"
    assert body["ready"] is True


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
