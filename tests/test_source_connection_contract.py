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


async def test_known_demo_source_returns_connection_contract(client: httpx.AsyncClient) -> None:
    response = await client.get(f"/api/sources/{SOURCE_ID}/connection")

    assert response.status_code == 200
    connection = response.json()
    assert connection["source_id"] == SOURCE_ID
    assert connection["status"] == "demo"
    assert connection["provider_kind"] == "demo"
    assert connection["display_title"] == "Backyard demo source"
    assert "no real playback provider" in connection["message"]
    assert connection["setup_hint"]
    assert connection["supports_streams"] is True
    assert connection["supports_live_playback"] is False
    assert connection["supports_zone_editing"] is True
    assert connection["adapter_key"] == "demo"
    assert connection["configured_fields"] == ["source_kind", "demo_seed"]
    assert connection["missing_fields"] == []
    assert connection["stream_ids"] == [STREAM_ID]
    assert connection["last_checked_at"] is None


async def test_unknown_source_connection_returns_404(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/sources/source-missing/connection")

    assert response.status_code == 404
    assert response.json()["detail"] == "Source 'source-missing' was not found."


async def test_source_connection_contract_does_not_create_product_truth(
    client: httpx.AsyncClient,
) -> None:
    before = await product_counts(client)

    response = await client.get(f"/api/sources/{SOURCE_ID}/connection")

    assert response.status_code == 200
    assert await product_counts(client) == before


async def test_not_configured_source_returns_safe_field_lists(
    client: httpx.AsyncClient,
    isolated_repository: ProductRepository,
) -> None:
    with isolated_repository.session_factory() as session:
        with session.begin():
            session.add(
                CameraSourceModel(
                    id="source-future-provider",
                    name="Future provider source",
                    kind=SourceKind.integration.value,
                    status=SourceStatus.needs_setup.value,
                    description="Product metadata for a future source provider.",
                )
            )
            session.add(
                StreamModel(
                    id="stream-future-provider",
                    source_id="source-future-provider",
                    name="Future provider stream",
                    description="Stream metadata awaiting a future provider.",
                    is_live=False,
                )
            )

    response = await client.get("/api/sources/source-future-provider/connection")

    assert response.status_code == 200
    connection = response.json()
    assert connection["status"] == "not_configured"
    assert connection["provider_kind"] == "future_adapter"
    assert connection["supports_streams"] is True
    assert connection["supports_live_playback"] is False
    assert connection["supports_zone_editing"] is True
    assert connection["configured_fields"] == ["source_kind"]
    assert connection["missing_fields"] == ["provider_configuration"]
    assert connection["stream_ids"] == ["stream-future-provider"]
    unsafe_terms = ("frame", "poll", "capture", "heartbeat", "secret", "password")
    field_text = " ".join(connection["configured_fields"] + connection["missing_fields"]).lower()
    assert not any(term in field_text for term in unsafe_terms)


async def test_source_connection_route_does_not_require_adapter_runtime_status(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_if_called():
        raise AssertionError("Source connection status must not call detector adapter status")

    monkeypatch.setattr(
        "mockingbird.repository.product_repository.get_local_detector_status",
        fail_if_called,
    )
    monkeypatch.setattr(
        "mockingbird.repository.product_repository.get_megadetector_status",
        fail_if_called,
    )

    response = await client.get(f"/api/sources/{SOURCE_ID}/connection")

    assert response.status_code == 200


async def test_source_connection_contract_creates_no_media_or_model_artifacts(
    client: httpx.AsyncClient,
    tmp_path: Path,
) -> None:
    response = await client.get(f"/api/sources/{SOURCE_ID}/connection")

    assert response.status_code == 200
    artifact_extensions = {".onnx", ".pt", ".pth", ".weights", ".engine", ".ckpt"}
    assert [
        path
        for path in tmp_path.rglob("*")
        if path.is_file() and path.suffix.lower() in artifact_extensions
    ] == []
