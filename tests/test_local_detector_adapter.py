from pathlib import Path

import httpx
import pytest

from mockingbird.api.main import app, configure_repository
from mockingbird.detectors.local_image_detector import (
    LOCAL_IMAGE_DETECTOR_ID,
    LocalDetectorBox,
    LocalDetectorProposal,
    LocalDetectorStatus,
)
from mockingbird.repository import product_repository
from mockingbird.repository.product_repository import ProductRepository

pytestmark = pytest.mark.anyio

STREAM_ID = "stream-backyard-feeder"
FEEDER_ZONE_ID = "zone-feeder"


@pytest.fixture(autouse=True)
def isolated_repository(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MOCKINGBIRD_LOCAL_DETECTOR_MODEL_PATH", raising=False)
    monkeypatch.delenv("MOCKINGBIRD_LOCAL_DETECTOR_LABELS_PATH", raising=False)
    repository = ProductRepository(
        db_url=f"sqlite:///{tmp_path / 'mockingbird.sqlite3'}",
        media_root=tmp_path / "media",
    )
    configure_repository(repository)
    yield
    configure_repository(None)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as api_client:
        yield api_client


async def import_image(client: httpx.AsyncClient):
    return await client.post(
        "/api/media/import",
        data={
            "stream_id": STREAM_ID,
            "zone_id": FEEDER_ZONE_ID,
            "title": "Local detector image",
            "subject_label": "unknown_bird",
            "species_guess": "unknown_bird",
            "notes": "Imported image for local detector adapter.",
        },
        files={"file": ("local-detector.png", b"local detector image bytes", "image/png")},
    )


async def import_video(client: httpx.AsyncClient):
    return await client.post(
        "/api/media/import",
        data={
            "stream_id": STREAM_ID,
            "zone_id": FEEDER_ZONE_ID,
            "title": "Local detector unsupported video",
            "subject_label": "unknown_animal",
            "notes": "Video should not run through local image detector.",
        },
        files={"file": ("local-detector.mp4", b"local detector video bytes", "video/mp4")},
    )


async def run_local_detector(client: httpx.AsyncClient, media_asset_id: str):
    return await client.post(
        f"/api/model-adapters/{LOCAL_IMAGE_DETECTOR_ID}/runs",
        json={
            "adapter_id": LOCAL_IMAGE_DETECTOR_ID,
            "media_asset_id": media_asset_id,
            "zone_ids": [FEEDER_ZONE_ID],
            "notes": "Local detector proposal evidence only.",
        },
    )


def mark_local_detector_available(
    monkeypatch: pytest.MonkeyPatch,
    *,
    labels_path: str | None = None,
) -> None:
    monkeypatch.setattr(
        product_repository,
        "get_local_detector_status",
        lambda: LocalDetectorStatus(
            status="available",
            configured=True,
            runtime_available=True,
            model_path="/tmp/mock-local-detector.onnx",
            labels_path=labels_path,
            detail="Mock local detector available for test.",
        ),
    )


async def test_local_detector_adapter_appears_not_configured_without_model(
    client: httpx.AsyncClient,
) -> None:
    health_response = await client.get("/health")
    response = await client.get("/api/model-adapters")

    assert health_response.status_code == 200
    assert response.status_code == 200
    adapter = next(item for item in response.json() if item["id"] == LOCAL_IMAGE_DETECTOR_ID)
    configuration_status = adapter["configuration_status"]
    assert adapter["name"] == "Local Image Detector"
    assert adapter["kind"] == "object_detector"
    assert adapter["status"] == "not_configured"
    assert adapter["creates_review_truth"] is False
    assert adapter["local_only"] is True
    assert {"image/jpeg", "image/png", "image/webp"}.issubset(adapter["supported_media_types"])
    assert "MOCKINGBIRD_LOCAL_DETECTOR_MODEL_PATH" in adapter["notes"]
    assert configuration_status["adapter_id"] == LOCAL_IMAGE_DETECTOR_ID
    assert configuration_status["model_path_configured"] is False
    assert configuration_status["labels_path_configured"] is False
    assert configuration_status["runtime_available"] is False
    assert configuration_status["can_run"] is False
    assert configuration_status["creates_review_truth"] is False
    assert configuration_status["local_only"] is True
    assert {"image/jpeg", "image/png", "image/webp"}.issubset(
        configuration_status["supported_media_types"]
    )
    assert "MOCKINGBIRD_LOCAL_DETECTOR_MODEL_PATH" in configuration_status["status_reason"]
    assert "MOCKINGBIRD_LOCAL_DETECTOR_MODEL_PATH" in configuration_status["setup_hint"]


async def test_local_detector_adapter_status_reports_configured_runtime_when_mocked(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mark_local_detector_available(monkeypatch, labels_path="/tmp/mock-labels.txt")

    response = await client.get(f"/api/model-adapters/{LOCAL_IMAGE_DETECTOR_ID}")

    assert response.status_code == 200
    adapter = response.json()
    configuration_status = adapter["configuration_status"]
    assert adapter["status"] == "available"
    assert configuration_status["model_path_configured"] is True
    assert configuration_status["labels_path_configured"] is True
    assert configuration_status["runtime_available"] is True
    assert configuration_status["can_run"] is True
    assert configuration_status["creates_review_truth"] is False


async def test_running_local_detector_without_model_config_returns_clear_error(
    client: httpx.AsyncClient,
) -> None:
    media_asset = (await import_image(client)).json()["media_asset"]

    response = await run_local_detector(client, media_asset["id"])

    assert response.status_code == 400
    assert "MOCKINGBIRD_LOCAL_DETECTOR_MODEL_PATH" in response.json()["detail"]


async def test_local_detector_errors_prefer_media_validation_before_config(
    client: httpx.AsyncClient,
) -> None:
    video_asset = (await import_video(client)).json()["media_asset"]

    missing_response = await run_local_detector(client, "media-asset-missing")
    unsupported_response = await run_local_detector(client, video_asset["id"])

    assert missing_response.status_code == 404
    assert "Media asset" in missing_response.json()["detail"]
    assert unsupported_response.status_code == 400
    assert "image/jpeg" in unsupported_response.json()["detail"]
    assert "image/png" in unsupported_response.json()["detail"]
    assert "image/webp" in unsupported_response.json()["detail"]


async def test_local_detector_proposals_are_evidence_only_until_conversion(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mark_local_detector_available(monkeypatch)
    monkeypatch.setattr(
        product_repository,
        "run_local_image_detector",
        lambda **_: [
            LocalDetectorProposal(
                label="bird",
                confidence=0.77,
                bbox=LocalDetectorBox(x=0.2, y=0.3, width=0.25, height=0.2),
            )
        ],
    )
    media_asset = (await import_image(client)).json()["media_asset"]
    initial_events = (await client.get("/api/events")).json()
    initial_visits = (await client.get("/api/visits")).json()
    coverage_before = (await client.get("/api/dataset-coverage/summary")).json()
    quality_before = (await client.get("/api/dataset-quality/summary")).json()

    response = await run_local_detector(client, media_asset["id"])

    coverage_after = (await client.get("/api/dataset-coverage/summary")).json()
    quality_after = (await client.get("/api/dataset-quality/summary")).json()
    assert response.status_code == 200
    result = response.json()
    proposal = result["proposals"][0]
    assert result["adapter"]["id"] == LOCAL_IMAGE_DETECTOR_ID
    assert result["adapter"]["creates_review_truth"] is False
    assert result["detection_run"]["source"] == "future_model"
    assert proposal["event_id"] is None
    assert proposal["visit_id"] is None
    assert proposal["status"] == "proposed"
    assert proposal["label"] == "bird"
    assert proposal["bbox"] == {"x": 0.2, "y": 0.3, "width": 0.25, "height": 0.2}
    assert len((await client.get("/api/events")).json()) == len(initial_events)
    assert len((await client.get("/api/visits")).json()) == len(initial_visits)
    assert coverage_after["export_ready_count"] == coverage_before["export_ready_count"]
    assert quality_after["export_ready_count"] == quality_before["export_ready_count"]


async def test_local_detector_empty_result_creates_run_without_truth(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mark_local_detector_available(monkeypatch)
    monkeypatch.setattr(product_repository, "run_local_image_detector", lambda **_: [])
    media_asset = (await import_image(client)).json()["media_asset"]

    response = await run_local_detector(client, media_asset["id"])

    assert response.status_code == 200
    result = response.json()
    assert result["detection_run"]["status"] == "completed"
    assert result["proposals"] == []
    assert "no proposal evidence" in result["local_first_note"]
