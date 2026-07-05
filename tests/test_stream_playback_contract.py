from pathlib import Path

import httpx
import pytest

from mockingbird.api.main import app, configure_repository
from mockingbird.api.schemas import SourceKind, SourceStatus
from mockingbird.repository.product_repository import ProductRepository
from mockingbird.storage.models import CameraSourceModel, StreamModel

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


async def test_known_demo_stream_returns_playback_contract(client: httpx.AsyncClient) -> None:
    response = await client.get(f"/api/streams/{STREAM_ID}/playback")

    assert response.status_code == 200
    playback = response.json()
    assert playback["stream_id"] == STREAM_ID
    assert playback["source_id"] == SOURCE_ID
    assert playback["status"] == "demo"
    assert playback["playback_kind"] == "demo_panel"
    assert playback["display_title"] == "Backyard feeder stream"
    assert "no real video playback" in playback["message"]
    assert playback["setup_hint"]
    assert playback["supports_zone_editing"] is True
    assert playback["supports_live_playback"] is False
    assert playback["adapter_key"] == "demo"
    assert playback["last_checked_at"] is None
    assert playback["preview_media_asset_id"] is None
    assert playback["preview_url"] is None


async def test_unknown_stream_playback_returns_404(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/streams/stream-missing/playback")

    assert response.status_code == 404
    assert response.json()["detail"] == "Stream 'stream-missing' was not found."


async def test_playback_contract_does_not_create_product_truth(client: httpx.AsyncClient) -> None:
    before = await product_counts(client)

    response = await client.get(f"/api/streams/{STREAM_ID}/playback")

    assert response.status_code == 200
    assert await product_counts(client) == before


async def test_playback_contract_does_not_claim_live_playback(client: httpx.AsyncClient) -> None:
    response = await client.get(f"/api/streams/{STREAM_ID}/playback")

    assert response.status_code == 200
    playback = response.json()
    assert playback["supports_live_playback"] is False
    assert playback["playback_kind"] in {"demo_panel", "placeholder"}


async def test_external_url_without_live_stream_reports_needs_stream_url(
    client: httpx.AsyncClient,
) -> None:
    update_response = await client.patch(
        f"/api/sources/{SOURCE_ID}/provider-configuration",
        json={
            "provider_key": "external_url",
            "config": {"url": "http://camera.local/still.jpg"},
        },
    )
    assert update_response.status_code == 200

    response = await client.get(f"/api/streams/{STREAM_ID}/playback")

    assert response.status_code == 200
    playback = response.json()
    assert playback["status"] == "needs_stream_url"
    assert playback["playback_kind"] == "external_url"
    assert playback["message"] == "No live stream URL configured."
    assert playback["supports_live_playback"] is False
    assert playback["preview_url"] is None
    assert playback["live_stream_type"] == "unknown"
    assert playback["live_stream_url_display"] is None


async def test_external_url_mjpeg_live_stream_reports_browser_ready_and_redacts_display(
    client: httpx.AsyncClient,
) -> None:
    live_url = "http://viewer:secret@camera.local/live.mjpg"
    update_response = await client.patch(
        f"/api/sources/{SOURCE_ID}/provider-configuration",
        json={
            "provider_key": "external_url",
            "config": {
                "url": "http://camera.local/still.jpg",
                "live_stream_url": live_url,
                "live_stream_type": "mjpeg",
            },
        },
    )
    assert update_response.status_code == 200
    configuration = update_response.json()
    assert configuration["supports_live_playback"] is True
    assert configuration["safe_config_preview"]["live_stream_url"] == (
        "http://***:***@camera.local/live.mjpg"
    )
    assert "secret" not in str(configuration)

    response = await client.get(f"/api/streams/{STREAM_ID}/playback")

    assert response.status_code == 200
    playback = response.json()
    assert playback["status"] == "live_ready"
    assert playback["playback_kind"] == "mjpeg"
    assert playback["supports_live_playback"] is True
    assert playback["preview_url"] == live_url
    assert playback["live_stream_type"] == "mjpeg"
    assert playback["live_stream_url_display"] == "http://***:***@camera.local/live.mjpg"
    assert "secret" not in playback["live_stream_url_display"]


async def test_external_url_rtsp_live_stream_reports_bridge_required(
    client: httpx.AsyncClient,
) -> None:
    update_response = await client.patch(
        f"/api/sources/{SOURCE_ID}/provider-configuration",
        json={
            "provider_key": "external_url",
            "config": {
                "url": "http://camera.local/still.jpg",
                "live_stream_url": "rtsp://camera.local/live",
                "live_stream_type": "rtsp",
            },
        },
    )
    assert update_response.status_code == 200

    response = await client.get(f"/api/streams/{STREAM_ID}/playback")

    assert response.status_code == 200
    playback = response.json()
    assert playback["status"] == "unsupported_rtsp_bridge_required"
    assert playback["playback_kind"] == "rtsp"
    assert playback["message"] == "RTSP requires a backend bridge/transcode in a later phase."
    assert playback["supports_live_playback"] is False
    assert playback["preview_url"] is None
    assert playback["live_stream_type"] == "rtsp"


async def test_external_url_unknown_live_stream_type_reports_unsupported(
    client: httpx.AsyncClient,
) -> None:
    update_response = await client.patch(
        f"/api/sources/{SOURCE_ID}/provider-configuration",
        json={
            "provider_key": "external_url",
            "config": {
                "url": "http://camera.local/still.jpg",
                "live_stream_url": "http://camera.local/custom-stream",
                "live_stream_type": "unknown",
            },
        },
    )
    assert update_response.status_code == 200

    response = await client.get(f"/api/streams/{STREAM_ID}/playback")

    assert response.status_code == 200
    playback = response.json()
    assert playback["status"] == "unsupported_stream_type"
    assert playback["playback_kind"] == "unknown"
    assert playback["supports_live_playback"] is False
    assert playback["preview_url"] is None
    assert playback["live_stream_type"] == "unknown"


async def test_not_configured_stream_returns_setup_hint(
    client: httpx.AsyncClient,
    isolated_repository: ProductRepository,
) -> None:
    with isolated_repository.session_factory() as session:
        with session.begin():
            session.add(
                CameraSourceModel(
                    id="source-future-local",
                    name="Future local source",
                    kind=SourceKind.local_folder.value,
                    status=SourceStatus.needs_setup.value,
                    description="Product metadata for a future local source.",
                )
            )
            session.add(
                StreamModel(
                    id="stream-future-local",
                    source_id="source-future-local",
                    name="Future source stream",
                    description="Placeholder stream for future playback.",
                    is_live=False,
                )
            )

    response = await client.get("/api/streams/stream-future-local/playback")

    assert response.status_code == 200
    playback = response.json()
    assert playback["status"] == "not_configured"
    assert playback["playback_kind"] == "placeholder"
    assert playback["setup_hint"]
    assert playback["supports_zone_editing"] is True
    assert playback["supports_live_playback"] is False
    assert playback["adapter_key"] == "local_folder"


async def test_playback_route_does_not_require_adapter_runtime_status(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_if_called():
        raise AssertionError("Playback status must not call detector adapter status")

    monkeypatch.setattr(
        "mockingbird.repository.product_repository.get_local_detector_status",
        fail_if_called,
    )
    monkeypatch.setattr(
        "mockingbird.repository.product_repository.get_megadetector_status",
        fail_if_called,
    )

    response = await client.get(f"/api/streams/{STREAM_ID}/playback")

    assert response.status_code == 200


async def test_playback_contract_creates_no_media_or_model_artifacts(
    client: httpx.AsyncClient,
    tmp_path: Path,
) -> None:
    response = await client.get(f"/api/streams/{STREAM_ID}/playback")

    assert response.status_code == 200
    artifact_extensions = {".onnx", ".pt", ".pth", ".weights", ".engine", ".ckpt"}
    assert [
        path
        for path in tmp_path.rglob("*")
        if path.is_file() and path.suffix.lower() in artifact_extensions
    ] == []
