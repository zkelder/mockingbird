from pathlib import Path

import httpx
import pytest

from mockingbird.api.main import app, configure_repository
from mockingbird.repository.product_repository import (
    ProductRepository,
    SourceProviderConfigurationModel,
)

pytestmark = pytest.mark.anyio

SOURCE_ID = "source-backyard-demo"
STREAM_ID = "stream-backyard-feeder"


@pytest.fixture(autouse=True)
def isolated_repository(tmp_path: Path) -> ProductRepository:
    repository = ProductRepository(
        db_url=f"sqlite:///{tmp_path / 'mockingbird.sqlite3'}",
        media_root=tmp_path / "media",
    )
    configure_repository(repository)
    yield repository
    configure_repository(None)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as api_client:
        yield api_client


async def product_counts(client: httpx.AsyncClient) -> dict[str, int]:
    responses = {
        "events": await client.get("/api/events"),
        "visits": await client.get("/api/visits"),
        "review_labels": await client.get("/api/review-labels"),
        "motion_evidence": await client.get("/api/motion/evidence"),
        "species_suggestions": await client.get("/api/species-suggestions"),
        "detection_proposals": await client.get("/api/detection-proposals"),
        "dataset_exports": await client.get("/api/dataset-exports"),
    }
    assert all(response.status_code == 200 for response in responses.values())

    return {
        "events": len(responses["events"].json()),
        "visits": len(responses["visits"].json()),
        "review_labels": len(responses["review_labels"].json()),
        "motion_evidence": len(responses["motion_evidence"].json()["motion_evidence"]),
        "species_suggestions": len(responses["species_suggestions"].json()["species_suggestions"]),
        "detection_proposals": len(responses["detection_proposals"].json()),
        "dataset_exports": len(responses["dataset_exports"].json()),
    }


async def test_provider_definitions_return_contract_keys_and_field_metadata(
    client: httpx.AsyncClient,
) -> None:
    response = await client.get("/api/source-provider-definitions")

    assert response.status_code == 200
    definitions = response.json()
    keys = {definition["provider_key"] for definition in definitions}
    assert {
        "demo",
        "manual_media",
        "external_url",
        "local_usb",
        "rtsp_future",
        "esp32_future",
        "browser_camera_future",
        "folder_import_future",
        "webhook_future",
    }.issubset(keys)

    rtsp_definition = next(
        definition for definition in definitions if definition["provider_key"] == "rtsp_future"
    )
    assert rtsp_definition["status"] == "future_adapter"
    assert rtsp_definition["supports_live_playback"] is False
    assert any(field["required"] for field in rtsp_definition["fields"])
    assert any(field["secret"] for field in rtsp_definition["fields"])

    local_usb_definition = next(
        definition for definition in definitions if definition["provider_key"] == "local_usb"
    )
    assert local_usb_definition["status"] == "available_contract_only"
    assert local_usb_definition["supports_live_playback"] is True
    local_usb_fields = {field["key"]: field for field in local_usb_definition["fields"]}
    assert local_usb_fields["local_camera_device"]["required"] is False
    assert local_usb_fields["local_camera_device"]["placeholder"] == "/dev/video0"
    assert local_usb_fields["windows_camera_name"]["required"] is False
    assert local_usb_fields["windows_camera_name"]["placeholder"] == "EMEET SmartCam S600"
    assert local_usb_fields["ffmpeg_binary_path"]["placeholder"] == "/mnt/c/ffmpeg/bin/ffmpeg.exe"
    assert local_usb_fields["video_size"]["placeholder"] == "640x480"
    assert local_usb_fields["framerate"]["placeholder"] == "10"

    folder_definition = next(
        definition
        for definition in definitions
        if definition["provider_key"] == "folder_import_future"
    )
    assert folder_definition["display_name"] == "Folder / trail-cam import"
    folder_fields = {field["key"]: field for field in folder_definition["fields"]}
    assert folder_fields["folder_path"]["required"] is True
    assert folder_fields["folder_path"]["secret"] is True
    assert folder_fields["recursive"]["placeholder"] == "false"
    assert folder_fields["allowed_extensions"]["placeholder"] == "jpg,jpeg,png,webp"


async def test_known_source_provider_configuration_returns_safe_default(
    client: httpx.AsyncClient,
) -> None:
    response = await client.get(f"/api/sources/{SOURCE_ID}/provider-configuration")

    assert response.status_code == 200
    configuration = response.json()
    assert configuration["source_id"] == SOURCE_ID
    assert configuration["provider_key"] == "demo"
    assert configuration["configured_fields"] == ["demo_seed"]
    assert configuration["missing_fields"] == []
    assert configuration["safe_config_preview"]["demo_seed"] == "backyard-demo"
    assert configuration["supports_live_playback"] is False
    assert configuration["supports_zone_editing"] is True


async def test_unknown_source_provider_configuration_returns_404(
    client: httpx.AsyncClient,
) -> None:
    response = await client.get("/api/sources/source-missing/provider-configuration")

    assert response.status_code == 404
    assert response.json()["detail"] == "Source 'source-missing' was not found."


async def test_patch_unknown_provider_key_is_rejected(client: httpx.AsyncClient) -> None:
    response = await client.patch(
        f"/api/sources/{SOURCE_ID}/provider-configuration",
        json={"provider_key": "camera_runtime_now", "config": {}},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Unknown source provider key."


async def test_patch_provider_configuration_saves_metadata_and_redacts_secret(
    client: httpx.AsyncClient,
    isolated_repository: ProductRepository,
) -> None:
    response = await client.patch(
        f"/api/sources/{SOURCE_ID}/provider-configuration",
        json={
            "provider_key": "rtsp_future",
            "config": {
                "url": "rtsp://example.local/backyard",
                "username": "viewer",
                "access_secret": "do-not-return-this",
            },
        },
    )

    assert response.status_code == 200
    configuration = response.json()
    assert configuration["provider_key"] == "rtsp_future"
    assert configuration["configured_fields"] == ["url", "username", "access_secret"]
    assert configuration["missing_fields"] == []
    assert configuration["safe_config_preview"]["url"] == "rtsp://example.local/backyard"
    assert configuration["safe_config_preview"]["username"] == "viewer"
    assert configuration["safe_config_preview"]["access_secret"] == "configured"
    assert "do-not-return-this" not in str(configuration)
    assert configuration["supports_live_playback"] is False
    assert "will not connect" in configuration["message"]

    with isolated_repository.session_factory() as session:
        stored = session.get(SourceProviderConfigurationModel, SOURCE_ID)
        assert stored is not None
        assert "do-not-return-this" not in stored.config_json
        assert '"access_secret": "configured"' in stored.config_json


async def test_future_provider_configuration_reflects_connection_without_live_claim(
    client: httpx.AsyncClient,
) -> None:
    update_response = await client.patch(
        f"/api/sources/{SOURCE_ID}/provider-configuration",
        json={
            "provider_key": "external_url",
            "config": {"url": "http://example.local/view"},
        },
    )
    assert update_response.status_code == 200

    connection_response = await client.get(f"/api/sources/{SOURCE_ID}/connection")

    assert connection_response.status_code == 200
    connection = connection_response.json()
    assert connection["status"] == "configured"
    assert connection["provider_kind"] == "external_url"
    assert connection["adapter_key"] == "external_url"
    assert connection["configured_fields"] == ["url"]
    assert connection["missing_fields"] == []
    assert connection["stream_ids"] == [STREAM_ID]
    assert connection["supports_live_playback"] is False
    assert connection["supports_zone_editing"] is True
    assert "still-image preview" in connection["message"]


async def test_missing_required_fields_reflect_in_configuration_and_connection(
    client: httpx.AsyncClient,
) -> None:
    response = await client.patch(
        f"/api/sources/{SOURCE_ID}/provider-configuration",
        json={"provider_key": "folder_import_future", "config": {}},
    )
    assert response.status_code == 200
    configuration = response.json()
    assert configuration["configured_fields"] == []
    assert configuration["missing_fields"] == ["folder_path"]
    assert configuration["safe_config_preview"]["folder_path"] == "not_configured"

    connection_response = await client.get(f"/api/sources/{SOURCE_ID}/connection")
    assert connection_response.status_code == 200
    connection = connection_response.json()
    assert connection["status"] == "not_configured"
    assert connection["adapter_key"] == "folder_import_future"
    assert connection["missing_fields"] == ["folder_path"]
    assert connection["supports_live_playback"] is False


async def test_stream_playback_remains_honest_after_provider_configuration(
    client: httpx.AsyncClient,
) -> None:
    response = await client.patch(
        f"/api/sources/{SOURCE_ID}/provider-configuration",
        json={
            "provider_key": "rtsp_future",
            "config": {"url": "rtsp://example.local/backyard"},
        },
    )
    assert response.status_code == 200

    playback_response = await client.get(f"/api/streams/{STREAM_ID}/playback")

    assert playback_response.status_code == 200
    playback = playback_response.json()
    assert playback["supports_live_playback"] is False
    assert playback["supports_zone_editing"] is True
    assert playback["playback_kind"] in {"demo_panel", "placeholder"}


async def test_provider_configuration_does_not_create_product_truth(
    client: httpx.AsyncClient,
) -> None:
    before = await product_counts(client)

    response = await client.patch(
        f"/api/sources/{SOURCE_ID}/provider-configuration",
        json={
            "provider_key": "webhook_future",
            "config": {
                "endpoint_name": "backyard-webhook",
                "shared_secret_configured": "redact-me",
            },
        },
    )

    assert response.status_code == 200
    assert await product_counts(client) == before


async def test_provider_configuration_route_does_not_require_adapter_runtime_status(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_if_called():
        raise AssertionError("Provider configuration must not call detector adapter status")

    monkeypatch.setattr(
        "mockingbird.repository.product_repository.get_local_detector_status",
        fail_if_called,
    )
    monkeypatch.setattr(
        "mockingbird.repository.product_repository.get_megadetector_status",
        fail_if_called,
    )

    response = await client.patch(
        f"/api/sources/{SOURCE_ID}/provider-configuration",
        json={"provider_key": "external_url", "config": {"url": "http://example.local/view"}},
    )

    assert response.status_code == 200


async def test_provider_configuration_creates_no_media_or_model_artifacts(
    client: httpx.AsyncClient,
    tmp_path: Path,
) -> None:
    response = await client.patch(
        f"/api/sources/{SOURCE_ID}/provider-configuration",
        json={"provider_key": "external_url", "config": {"url": "http://example.local/view"}},
    )

    assert response.status_code == 200
    artifact_extensions = {".onnx", ".pt", ".pth", ".weights", ".engine", ".ckpt"}
    assert [
        path
        for path in tmp_path.rglob("*")
        if path.is_file() and path.suffix.lower() in artifact_extensions
    ] == []
