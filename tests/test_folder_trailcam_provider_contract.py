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
        "media_assets": await client.get("/api/media"),
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
        "media_assets": len(responses["media_assets"].json()),
        "motion_evidence": len(responses["motion_evidence"].json()["motion_evidence"]),
        "species_suggestions": len(responses["species_suggestions"].json()["species_suggestions"]),
        "detection_proposals": len(responses["detection_proposals"].json()),
        "dataset_exports": len(responses["dataset_exports"].json()),
    }


async def test_folder_trailcam_provider_definition_exposes_metadata_contract(
    client: httpx.AsyncClient,
) -> None:
    response = await client.get("/api/source-provider-definitions")

    assert response.status_code == 200
    definition = next(
        item for item in response.json() if item["provider_key"] == "folder_import_future"
    )
    assert definition["display_name"] == "Folder / trail-cam import"
    assert definition["status"] == "future_adapter"
    assert definition["supports_live_playback"] is False
    assert definition["supports_zone_editing"] is True

    fields = {field["key"]: field for field in definition["fields"]}
    assert set(fields) == {
        "folder_path",
        "display_name",
        "recursive",
        "allowed_extensions",
        "default_stream_id",
        "default_zone_id",
        "import_mode",
        "notes",
    }
    assert fields["folder_path"]["label"] == "Folder path"
    assert fields["folder_path"]["required"] is True
    assert fields["folder_path"]["secret"] is True
    assert fields["folder_path"]["placeholder"] == "/path/to/trailcam/folder"
    assert fields["recursive"]["placeholder"] == "false"
    assert fields["allowed_extensions"]["placeholder"] == "jpg,jpeg,png,webp"
    assert fields["import_mode"]["placeholder"] == "media_only"


async def test_missing_folder_path_reports_setup_needed_without_live_claim(
    client: httpx.AsyncClient,
) -> None:
    update_response = await client.patch(
        f"/api/sources/{SOURCE_ID}/provider-configuration",
        json={"provider_key": "folder_import_future", "config": {}},
    )

    assert update_response.status_code == 200
    configuration = update_response.json()
    assert configuration["missing_fields"] == ["folder_path"]
    assert configuration["safe_config_preview"]["folder_path"] == "not_configured"
    assert configuration["supports_live_playback"] is False
    assert "folder path metadata" in configuration["setup_hint"]

    connection_response = await client.get(f"/api/sources/{SOURCE_ID}/connection")
    assert connection_response.status_code == 200
    connection = connection_response.json()
    assert connection["status"] == "not_configured"
    assert connection["provider_kind"] == "future_adapter"
    assert connection["missing_fields"] == ["folder_path"]
    assert connection["supports_live_playback"] is False
    assert connection["supports_zone_editing"] is True
    assert "folder path metadata" in connection["setup_hint"]

    review_response = await client.get(f"/api/sources/{SOURCE_ID}/setup-review")
    assert review_response.status_code == 200
    review = review_response.json()
    assert review["readiness_level"] == "needs_setup"
    assert review["missing_fields"] == ["folder_path"]
    assert review["supports_live_playback"] is False
    assert "Folder path" in review["next_step"]


async def test_configured_folder_path_is_redacted_and_reports_future_import_status(
    client: httpx.AsyncClient,
    isolated_repository: ProductRepository,
) -> None:
    raw_folder_path = "/Users/example/Pictures/backyard trail cam"

    update_response = await client.patch(
        f"/api/sources/{SOURCE_ID}/provider-configuration",
        json={
            "provider_key": "folder_import_future",
            "config": {
                "folder_path": raw_folder_path,
                "display_name": "North fence trail cam",
                "recursive": "false",
                "allowed_extensions": "jpg,jpeg,png,webp",
                "default_stream_id": STREAM_ID,
                "default_zone_id": "zone-feeder",
                "import_mode": "media_only",
                "notes": "Metadata-only setup for later import planning.",
            },
        },
    )

    assert update_response.status_code == 200
    configuration = update_response.json()
    assert configuration["configured_fields"] == [
        "folder_path",
        "display_name",
        "recursive",
        "allowed_extensions",
        "default_stream_id",
        "default_zone_id",
        "import_mode",
        "notes",
    ]
    assert configuration["missing_fields"] == []
    assert configuration["safe_config_preview"]["folder_path"] == "configured"
    assert configuration["safe_config_preview"]["display_name"] == "North fence trail cam"
    assert raw_folder_path not in str(configuration)

    with isolated_repository.session_factory() as session:
        stored = session.get(SourceProviderConfigurationModel, SOURCE_ID)
        assert stored is not None
        assert raw_folder_path in stored.config_json

    connection_response = await client.get(f"/api/sources/{SOURCE_ID}/connection")
    assert connection_response.status_code == 200
    connection = connection_response.json()
    assert connection["status"] == "configured"
    assert connection["provider_kind"] == "future_adapter"
    assert connection["supports_live_playback"] is False
    assert connection["supports_zone_editing"] is True
    assert "explicit dry-run preview" in connection["message"]
    assert "does not import folders" in connection["message"]
    assert raw_folder_path not in str(connection)

    review_response = await client.get(f"/api/sources/{SOURCE_ID}/setup-review")
    assert review_response.status_code == 200
    review = review_response.json()
    assert review["readiness_level"] == "future_adapter_required"
    assert review["supports_live_playback"] is False
    assert review["supports_zone_editing"] is True
    assert "Explicit dry-run preview is available" in review["summary"]
    assert "future import work" in review["next_step"]
    folder_step = next(step for step in review["steps"] if step["key"] == "folder_import_preview")
    assert folder_step["status"] == "available"
    assert "creates no media or truth" in folder_step["message"]
    assert raw_folder_path not in str(review)


async def test_folder_provider_stream_playback_stays_placeholder_without_preview_or_live_claim(
    client: httpx.AsyncClient,
) -> None:
    update_response = await client.patch(
        f"/api/sources/{SOURCE_ID}/provider-configuration",
        json={
            "provider_key": "folder_import_future",
            "config": {"folder_path": "/mnt/trailcam"},
        },
    )
    assert update_response.status_code == 200

    response = await client.get(f"/api/streams/{STREAM_ID}/playback")

    assert response.status_code == 200
    playback = response.json()
    assert playback["status"] == "not_configured"
    assert playback["playback_kind"] == "placeholder"
    assert playback["adapter_key"] == "folder_import_future"
    assert playback["supports_live_playback"] is False
    assert playback["supports_zone_editing"] is True
    assert playback["preview_media_asset_id"] is None
    assert playback["preview_url"] is None
    assert "does not provide live playback" in playback["message"]


async def test_folder_provider_status_does_not_scan_import_or_create_truth(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    before = await product_counts(client)

    def fail_if_folder_io_runs(*_args, **_kwargs):
        raise AssertionError("Folder provider status must not run folder preview/import paths")

    monkeypatch.setattr(
        "mockingbird.repository.product_repository._folder_path",
        fail_if_folder_io_runs,
    )
    monkeypatch.setattr(
        ProductRepository,
        "_preview_folder_import_for_path",
        fail_if_folder_io_runs,
    )
    monkeypatch.setattr(
        ProductRepository,
        "import_folder_media",
        fail_if_folder_io_runs,
    )

    update_response = await client.patch(
        f"/api/sources/{SOURCE_ID}/provider-configuration",
        json={
            "provider_key": "folder_import_future",
            "config": {
                "folder_path": "/mnt/trailcam",
                "display_name": "Trail cam",
                "allowed_extensions": "jpg,jpeg,png,webp",
                "import_mode": "media_only",
            },
        },
    )
    assert update_response.status_code == 200

    responses = [
        await client.get(f"/api/sources/{SOURCE_ID}/provider-configuration"),
        await client.get(f"/api/sources/{SOURCE_ID}/connection"),
        await client.get(f"/api/sources/{SOURCE_ID}/setup-review"),
        await client.get(f"/api/streams/{STREAM_ID}/playback"),
    ]

    assert all(response.status_code == 200 for response in responses)
    assert await product_counts(client) == before
