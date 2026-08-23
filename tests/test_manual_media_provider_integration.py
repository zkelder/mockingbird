from pathlib import Path

import httpx
import pytest

from mockingbird.api.main import app, configure_repository
from mockingbird.api.schemas import SourceKind, SourceStatus
from mockingbird.repository.product_repository import ProductRepository
from mockingbird.storage.models import CameraSourceModel, StreamModel
from tests.conftest import LegacyAuthenticatedTestClient

pytestmark = pytest.mark.anyio

MANUAL_SOURCE_ID = "source-manual-media"
MANUAL_STREAM_ID = "stream-manual-media"


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
    async with LegacyAuthenticatedTestClient(transport=transport, base_url="http://testserver") as api_client:
        yield api_client


def add_manual_media_source(repository: ProductRepository) -> None:
    with repository.session_factory() as session:
        with session.begin():
            session.add(
                CameraSourceModel(
                    id=MANUAL_SOURCE_ID,
                    name="Manual media source",
                    kind=SourceKind.manual_upload.value,
                    status=SourceStatus.connected.value,
                    description="Explicit local media import source.",
                )
            )
            session.add(
                StreamModel(
                    id=MANUAL_STREAM_ID,
                    source_id=MANUAL_SOURCE_ID,
                    name="Manual media stream",
                    description="Stream context for local media imports.",
                    is_live=False,
                )
            )


async def product_counts(client: httpx.AsyncClient) -> dict[str, int]:
    responses = {
        "events": await client.get("/api/events"),
        "visits": await client.get("/api/visits"),
        "review_labels": await client.get("/api/review-labels"),
        "motion_evidence": await client.get("/api/motion/evidence"),
        "species_suggestions": await client.get("/api/species-suggestions"),
        "detection_proposals": await client.get("/api/detection-proposals"),
        "dataset_exports": await client.get("/api/dataset-exports"),
        "media_assets": await client.get("/api/media"),
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
        "media_assets": len(responses["media_assets"].json()),
    }


async def test_manual_media_setup_review_points_to_import_flow(
    client: httpx.AsyncClient,
    isolated_repository: ProductRepository,
) -> None:
    add_manual_media_source(isolated_repository)

    response = await client.get(f"/api/sources/{MANUAL_SOURCE_ID}/setup-review")

    assert response.status_code == 200
    review = response.json()
    assert review["provider_key"] == "manual_media"
    assert review["provider_display_name"] == "Manual media"
    assert review["readiness_level"] == "metadata_ready"
    assert review["missing_fields"] == []
    assert review["supports_live_playback"] is False
    assert review["supports_zone_editing"] is True
    assert "Imported media can create reviewable Events/Visits" in review["summary"]
    assert "corrections remain the source of truth" in review["summary"]
    assert "Import media for this Source/Stream" in review["next_step"]
    assert "live playback" not in review["next_step"].lower()
    assert all("live playback" not in warning.lower() for warning in review["warnings"])
    assert any(step["key"] == "manual_media_import" for step in review["steps"])
    assert review["streams"][0]["stream_id"] == MANUAL_STREAM_ID


async def test_manual_media_connection_and_playback_remain_honest(
    client: httpx.AsyncClient,
    isolated_repository: ProductRepository,
) -> None:
    add_manual_media_source(isolated_repository)

    connection_response = await client.get(f"/api/sources/{MANUAL_SOURCE_ID}/connection")
    playback_response = await client.get(f"/api/streams/{MANUAL_STREAM_ID}/playback")

    assert connection_response.status_code == 200
    connection = connection_response.json()
    assert connection["provider_kind"] == "manual_media"
    assert connection["status"] == "configured"
    assert connection["supports_live_playback"] is False
    assert connection["supports_zone_editing"] is True
    assert "explicit local imports" in connection["message"]
    assert "review and correct" in connection["setup_hint"]

    assert playback_response.status_code == 200
    playback = playback_response.json()
    assert playback["playback_kind"] in {"placeholder", "media_preview", "demo_panel"}
    assert playback["supports_live_playback"] is False
    assert playback["supports_zone_editing"] is True


async def test_manual_media_setup_review_is_read_only(
    client: httpx.AsyncClient,
    isolated_repository: ProductRepository,
) -> None:
    add_manual_media_source(isolated_repository)
    before = await product_counts(client)

    response = await client.get(f"/api/sources/{MANUAL_SOURCE_ID}/setup-review")

    assert response.status_code == 200
    assert await product_counts(client) == before


async def test_manual_media_import_creates_reviewable_records_without_truth(
    client: httpx.AsyncClient,
    isolated_repository: ProductRepository,
) -> None:
    add_manual_media_source(isolated_repository)
    before = await product_counts(client)

    response = await client.post(
        "/api/media/import",
        data={
            "stream_id": MANUAL_STREAM_ID,
            "title": "Manual media observation",
            "subject_label": "unknown_bird",
            "species_guess": "unknown_bird",
            "notes": "Explicit local import for review.",
        },
        files={"file": ("manual-bird.png", b"manual image bytes", "image/png")},
    )

    assert response.status_code == 201
    result = response.json()
    assert result["media_asset"]["source_id"] == MANUAL_SOURCE_ID
    assert result["stream"]["id"] == MANUAL_STREAM_ID
    assert result["event"]["review_status"] == "needs_review"
    assert result["visit"]["review_status"] == "needs_review"
    assert result["visit"]["reviewed_label"] is None

    after = await product_counts(client)
    assert after["events"] == before["events"] + 1
    assert after["visits"] == before["visits"] + 1
    assert after["media_assets"] == before["media_assets"] + 1
    assert after["review_labels"] == before["review_labels"]
    assert after["motion_evidence"] == before["motion_evidence"]
    assert after["species_suggestions"] == before["species_suggestions"]
    assert after["detection_proposals"] == before["detection_proposals"]
    assert after["dataset_exports"] == before["dataset_exports"]
