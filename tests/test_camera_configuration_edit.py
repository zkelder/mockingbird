import json

import httpx
import pytest

from mockingbird.api.main import app, configure_repository
from mockingbird.api.schemas import (
    CameraConfigurationApplyRequest,
    CameraConfigurationImpactPreviewRequest,
    CameraConfigurationSecretAction,
    CameraSetupCompleteRequest,
    Point,
)
from mockingbird.repository.product_repository import (
    ProductRepository,
    SourceProviderConfigurationModel,
)
from mockingbird.storage.models import ZoneModel


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def _repository(tmp_path) -> ProductRepository:
    return ProductRepository(
        db_url=f"sqlite:///{tmp_path / 'camera-configuration.sqlite3'}",
        media_root=tmp_path / "media",
    )


def _complete_setup(repository: ProductRepository, *, monitoring: bool = False):
    return repository.complete_camera_setup(
        CameraSetupCompleteRequest(
            camera_name="Backyard feeder",
            stream_name="Feeder view",
            provider_key="external_url",
            config={
                "url": "https://camera.local/still.jpg",
                "auth_password": "initial-secret",
                "notes": "North feeder",
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
                }
            ],
            enable_monitoring=monitoring,
            idempotency_key="camera-configuration-setup-001",
        )
    )


def test_camera_configuration_edit_masks_values_previews_impact_and_preserves_product_graph(tmp_path) -> None:
    repository = _repository(tmp_path)
    try:
        completed = _complete_setup(repository)
        before = repository.get_camera_configuration_edit(completed.stream.id)
        assert before is not None
        rendered_before = before.model_dump_json()
        assert "https://camera.local/still.jpg" not in rendered_before
        assert "initial-secret" not in rendered_before
        assert before.field_states["url"] == "configured"
        assert before.field_states["auth_password"] == "configured"

        preview_request = CameraConfigurationImpactPreviewRequest(
            provider_key="external_url",
            config={
                "url": "https://camera.local/new-still.jpg",
                "auth_password": "replacement-secret",
            },
            secret_actions={"auth_password": CameraConfigurationSecretAction.replace},
            stream_name="Feeder view (updated)",
            expected_state_token=before.state_token,
        )
        preview = repository.preview_camera_configuration(completed.stream.id, preview_request)
        assert preview is not None
        assert preview.validation.can_apply is True
        assert preview.restart_required is True
        assert preview.requires_explicit_restart_choice is False
        assert set(preview.changed_fields) == {"Snapshot URL", "Auth password", "Stream name"}
        assert "replacement-secret" not in preview.model_dump_json()
        assert "new-still" not in preview.model_dump_json()
        assert "Zones" in preview.preservation_summary[1]
        assert repository.list_camera_configuration_history(completed.stream.id) == []

        request = CameraConfigurationApplyRequest(
            **preview_request.model_dump(),
            preview_token=preview.preview_token,
            idempotency_key="camera-configuration-apply-001",
            restart_monitoring=False,
        )
        applied = repository.apply_camera_configuration(completed.stream.id, request)
        assert applied is not None
        assert applied.idempotent is False
        assert applied.revision.restart_requested is False
        assert applied.revision.actual_state_after.value == "stopped"

        repeated = repository.apply_camera_configuration(completed.stream.id, request)
        assert repeated is not None
        assert repeated.idempotent is True
        assert repeated.revision.id == applied.revision.id

        after = repository.get_camera_configuration_edit(completed.stream.id)
        assert after is not None
        assert after.stream_name == "Feeder view (updated)"
        assert "replacement-secret" not in after.model_dump_json()
        assert "new-still" not in after.model_dump_json()
        assert after.field_states["auth_password"] == "configured"
        assert after.runtime.safety_hold_active is False

        with repository.session_factory() as session:
            stored = session.get(SourceProviderConfigurationModel, completed.source.id)
            assert stored is not None
            assert json.loads(stored.config_json)["auth_password"] == "replacement-secret"
            zones = session.query(ZoneModel).filter_by(stream_id=completed.stream.id).all()
            assert [zone.name for zone in zones] == ["Feeder"]

        history = repository.list_camera_configuration_history(completed.stream.id)
        assert history is not None and len(history) == 1
        assert "replacement-secret" not in history[0].model_dump_json()
        assert "new-still" not in history[0].model_dump_json()
    finally:
        repository.close()


@pytest.mark.anyio
async def test_camera_configuration_api_rejects_provider_changes_and_returns_redacted_history(tmp_path) -> None:
    repository = _repository(tmp_path)
    configure_repository(repository)
    try:
        completed = _complete_setup(repository, monitoring=True)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            edit = await client.get(
                f"/api/streams/{completed.stream.id}/camera-configuration"
            )
            assert edit.status_code == 200
            assert "camera.local" not in edit.text
            assert "initial-secret" not in edit.text

            incompatible = await client.post(
                f"/api/streams/{completed.stream.id}/camera-configuration/preview",
                json={
                    "provider_key": "local_usb",
                    "config": {},
                    "secret_actions": {},
                    "expected_state_token": edit.json()["state_token"],
                },
            )
            assert incompatible.status_code == 400

            preview = await client.post(
                f"/api/streams/{completed.stream.id}/camera-configuration/preview",
                json={
                    "provider_key": "external_url",
                    "config": {"notes": "Updated feeder note"},
                    "secret_actions": {},
                    "expected_state_token": edit.json()["state_token"],
                },
            )
            assert preview.status_code == 200
            assert preview.json()["restart_required"] is False
            assert "Updated feeder note" not in preview.text

            applied = await client.post(
                f"/api/streams/{completed.stream.id}/camera-configuration/apply",
                json={
                    "provider_key": "external_url",
                    "config": {"notes": "Updated feeder note"},
                    "secret_actions": {},
                    "expected_state_token": edit.json()["state_token"],
                    "preview_token": preview.json()["preview_token"],
                    "idempotency_key": "camera-configuration-api-apply-001",
                    "restart_monitoring": False,
                },
            )
            assert applied.status_code == 200
            assert applied.json()["revision"]["restart_required"] is False
            assert "Updated feeder note" not in applied.text

            refreshed = await client.get(
                f"/api/streams/{completed.stream.id}/camera-configuration"
            )
            assert refreshed.status_code == 200
            restart_preview = await client.post(
                f"/api/streams/{completed.stream.id}/camera-configuration/preview",
                json={
                    "provider_key": "external_url",
                    "config": {"url": "https://camera.local/changed-still.jpg"},
                    "secret_actions": {},
                    "expected_state_token": refreshed.json()["state_token"],
                },
            )
            assert restart_preview.status_code == 200
            assert restart_preview.json()["requires_explicit_restart_choice"] is True

            restarted = await client.post(
                f"/api/streams/{completed.stream.id}/camera-configuration/apply",
                json={
                    "provider_key": "external_url",
                    "config": {"url": "https://camera.local/changed-still.jpg"},
                    "secret_actions": {},
                    "expected_state_token": refreshed.json()["state_token"],
                    "preview_token": restart_preview.json()["preview_token"],
                    "idempotency_key": "camera-configuration-api-restart-001",
                    "restart_monitoring": True,
                },
            )
            assert restarted.status_code == 200
            assert restarted.json()["revision"]["restart_requested"] is True
            assert restarted.json()["configuration"]["monitoring_policy"]["mode"] == "armed"
            assert "changed-still" not in restarted.text

            history = await client.get(
                f"/api/streams/{completed.stream.id}/camera-configuration/history"
            )
            assert history.status_code == 200
            assert len(history.json()["items"]) == 2
            assert "Updated feeder note" not in history.text
    finally:
        configure_repository(None)
