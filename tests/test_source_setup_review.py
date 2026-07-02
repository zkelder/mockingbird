from pathlib import Path

import httpx
import pytest

from mockingbird.api.main import app, configure_repository
from mockingbird.repository.product_repository import ProductRepository

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


async def test_known_source_returns_setup_review(client: httpx.AsyncClient) -> None:
    response = await client.get(f"/api/sources/{SOURCE_ID}/setup-review")

    assert response.status_code == 200
    review = response.json()
    assert review["source_id"] == SOURCE_ID
    assert review["provider_key"] == "demo"
    assert review["provider_display_name"] == "Demo source"
    assert review["source_status"] == "demo"
    assert review["readiness_level"] == "demo_ready"
    assert review["display_title"] == "Backyard demo source"
    assert "Demo setup metadata" in review["summary"]
    assert "Draw zones" in review["next_step"]
    assert review["supports_live_playback"] is False
    assert review["supports_zone_editing"] is True
    assert review["configured_fields"] == ["demo_seed"]
    assert review["missing_fields"] == []
    assert review["stream_count"] == 1
    assert review["streams"][0]["stream_id"] == STREAM_ID
    assert review["streams"][0]["playback_status"] == "demo"
    assert review["streams"][0]["playback_kind"] == "demo_panel"


async def test_unknown_source_setup_review_returns_404(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/sources/source-missing/setup-review")

    assert response.status_code == 404
    assert response.json()["detail"] == "Source 'source-missing' was not found."


async def test_future_provider_missing_fields_reports_needs_setup(
    client: httpx.AsyncClient,
) -> None:
    update_response = await client.patch(
        f"/api/sources/{SOURCE_ID}/provider-configuration",
        json={"provider_key": "folder_import_future", "config": {}},
    )
    assert update_response.status_code == 200

    response = await client.get(f"/api/sources/{SOURCE_ID}/setup-review")

    assert response.status_code == 200
    review = response.json()
    assert review["provider_key"] == "folder_import_future"
    assert review["readiness_level"] == "needs_setup"
    assert review["missing_fields"] == ["folder_label"]
    assert "Folder label" in review["next_step"]
    assert any(step["status"] == "missing" for step in review["steps"])
    assert review["supports_live_playback"] is False


async def test_future_provider_configured_requires_future_adapter(
    client: httpx.AsyncClient,
) -> None:
    update_response = await client.patch(
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
    assert update_response.status_code == 200

    response = await client.get(f"/api/sources/{SOURCE_ID}/setup-review")

    assert response.status_code == 200
    review = response.json()
    assert review["provider_key"] == "rtsp_future"
    assert review["readiness_level"] == "future_adapter_required"
    assert review["configured_fields"] == ["url", "username", "access_secret"]
    assert review["missing_fields"] == []
    assert review["supports_live_playback"] is False
    assert "Future provider implementation required" in review["next_step"]
    assert "do-not-return-this" not in str(review)


async def test_manual_media_provider_reports_metadata_ready_without_live_claim(
    client: httpx.AsyncClient,
) -> None:
    update_response = await client.patch(
        f"/api/sources/{SOURCE_ID}/provider-configuration",
        json={"provider_key": "manual_media", "config": {"source_label": "Backyard imports"}},
    )
    assert update_response.status_code == 200

    response = await client.get(f"/api/sources/{SOURCE_ID}/setup-review")

    assert response.status_code == 200
    review = response.json()
    assert review["provider_key"] == "manual_media"
    assert review["readiness_level"] == "metadata_ready"
    assert review["supports_live_playback"] is False
    assert "Manual media import" in review["summary"]
    assert "Import media for this Source/Stream" in review["next_step"]


async def test_setup_review_does_not_create_product_truth(client: httpx.AsyncClient) -> None:
    before = await product_counts(client)

    response = await client.get(f"/api/sources/{SOURCE_ID}/setup-review")

    assert response.status_code == 200
    assert await product_counts(client) == before


async def test_setup_review_route_does_not_call_model_runtime_hooks(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_if_called():
        raise AssertionError("Source setup review must not call detector adapter status")

    monkeypatch.setattr(
        "mockingbird.repository.product_repository.get_local_detector_status",
        fail_if_called,
    )
    monkeypatch.setattr(
        "mockingbird.repository.product_repository.get_megadetector_status",
        fail_if_called,
    )

    response = await client.get(f"/api/sources/{SOURCE_ID}/setup-review")

    assert response.status_code == 200


async def test_setup_review_creates_no_media_model_or_generated_artifacts(
    client: httpx.AsyncClient,
    tmp_path: Path,
) -> None:
    response = await client.get(f"/api/sources/{SOURCE_ID}/setup-review")

    assert response.status_code == 200
    forbidden_names = {
        "manifest.jsonl",
        "manifest.csv",
        "labels.txt",
        "taxonomy.json",
        "skipped_records.jsonl",
        "summary.json",
        "classifier-training-manifest-preview.json",
    }
    forbidden_extensions = {
        ".onnx",
        ".pt",
        ".pth",
        ".weights",
        ".engine",
        ".ckpt",
        ".jpg",
        ".jpeg",
        ".png",
        ".webp",
        ".mp4",
        ".mov",
    }
    assert [
        path
        for path in tmp_path.rglob("*")
        if path.is_file()
        and (path.name in forbidden_names or path.suffix.lower() in forbidden_extensions)
    ] == []
