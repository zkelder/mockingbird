from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from mockingbird.api.main import app, configure_repository
from mockingbird.repository.product_repository import ProductRepository
from mockingbird.storage.models import MediaAssetModel

pytestmark = pytest.mark.anyio

SOURCE_ID = "source-backyard-demo"
STREAM_ID = "stream-backyard-feeder"
FEEDER_ZONE_ID = "zone-feeder"
BIRD_EVENT_ID = "event-bird-feeder-001"
BIRD_VISIT_ID = "visit-bird-feeder-001"


@pytest.fixture(autouse=True)
def isolated_repository(tmp_path: Path) -> ProductRepository:
    repository = ProductRepository(db_url=f"sqlite:///{tmp_path / 'mockingbird.sqlite3'}")
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


def species_suggestion_payload(**overrides):
    payload = {
        "source_id": SOURCE_ID,
        "stream_id": STREAM_ID,
        "event_id": BIRD_EVENT_ID,
        "visit_id": BIRD_VISIT_ID,
        "adapter_id": "mock_species_adapter",
        "adapter_name": "Mock Species Adapter",
        "suggested_label": "northern_cardinal",
        "suggested_common_name": "Northern Cardinal",
        "suggested_scientific_name": "Cardinalis cardinalis",
        "confidence": 0.81,
        "rank": 1,
        "alternatives": [
            {"label": "house_finch", "confidence": 0.12},
            {"label": "unknown_bird", "confidence": 0.07},
        ],
        "evidence_region": {"x": 0.42, "y": 0.28, "width": 0.2, "height": 0.3},
        "notes": "Manual mock species suggestion evidence.",
    }
    payload.update(overrides)
    return payload


async def create_species_suggestion(client: httpx.AsyncClient, **overrides):
    return await client.post(
        "/api/species-suggestions",
        json=species_suggestion_payload(**overrides),
    )


async def create_mock_species_suggestion(client: httpx.AsyncClient, **overrides):
    payload = {"visit_id": BIRD_VISIT_ID}
    payload.update(overrides)
    return await client.post("/api/species-suggestions/mock", json=payload)


async def create_motion_evidence(client: httpx.AsyncClient) -> str:
    response = await client.post(
        "/api/motion/evidence",
        json={
            "zone_id": FEEDER_ZONE_ID,
            "start_frame_index": 10,
            "end_frame_index": 12,
            "best_frame_index": 11,
            "peak_changed_ratio": 0.42,
            "triggered_frame_count": 2,
            "scoring_config": {"source": "species_suggestion_test"},
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def add_test_media_asset(
    repository: ProductRepository,
    media_id: str = "media_species_suggestion_001",
    local_path: str | None = None,
) -> MediaAssetModel:
    asset = MediaAssetModel(
        id=media_id,
        source_id=SOURCE_ID,
        stream_id=STREAM_ID,
        filename=f"{media_id}.jpg",
        content_type="image/jpeg",
        media_type="image",
        local_path=local_path or f"demo://species-suggestion/{media_id}.jpg",
        original_filename=f"{media_id}.jpg",
        file_size_bytes=128,
        created_at=datetime.now(UTC),
        notes="Test-only local media reference for species suggestion evidence.",
    )
    with repository.session_factory() as session:
        with session.begin():
            session.add(asset)
    return asset


async def product_truth_snapshot(client: httpx.AsyncClient) -> dict[str, int | str | None]:
    events = await client.get("/api/events")
    visits = await client.get("/api/visits")
    visit = await client.get(f"/api/visits/{BIRD_VISIT_ID}")
    review_labels = await client.get("/api/review-labels")
    exports = await client.get("/api/dataset-exports")
    coverage = await client.get("/api/dataset-coverage/summary")

    assert events.status_code == 200
    assert visits.status_code == 200
    assert visit.status_code == 200
    assert review_labels.status_code == 200
    assert exports.status_code == 200
    assert coverage.status_code == 200

    visit_payload = visit.json()
    coverage_payload = coverage.json()
    return {
        "events": len(events.json()),
        "visits": len(visits.json()),
        "review_labels": len(review_labels.json()),
        "exports": len(exports.json()),
        "visit_review_status": visit_payload["review_status"],
        "visit_reviewed_label": visit_payload["reviewed_label"],
        "reviewed_record_count": coverage_payload["reviewed_record_count"],
        "export_ready_count": coverage_payload["export_ready_count"],
    }


async def test_create_species_suggestion_returns_pending_evidence(
    client: httpx.AsyncClient,
) -> None:
    response = await create_species_suggestion(client)

    assert response.status_code == 201
    suggestion = response.json()
    assert suggestion["id"].startswith("species-suggestion-")
    assert suggestion["source_id"] == SOURCE_ID
    assert suggestion["stream_id"] == STREAM_ID
    assert suggestion["event_id"] == BIRD_EVENT_ID
    assert suggestion["visit_id"] == BIRD_VISIT_ID
    assert suggestion["adapter_id"] == "mock_species_adapter"
    assert suggestion["suggested_label"] == "northern_cardinal"
    assert suggestion["confidence"] == 0.81
    assert suggestion["rank"] == 1
    assert suggestion["alternatives"][0]["label"] == "house_finch"
    assert suggestion["evidence_region"]["width"] == 0.2
    assert suggestion["status"] == "pending"


async def test_create_species_suggestion_can_reference_media_and_motion_evidence(
    client: httpx.AsyncClient,
    isolated_repository: ProductRepository,
) -> None:
    asset = add_test_media_asset(isolated_repository)
    motion_evidence_id = await create_motion_evidence(client)

    response = await create_species_suggestion(
        client,
        media_asset_id=asset.id,
        motion_evidence_id=motion_evidence_id,
    )

    assert response.status_code == 201
    suggestion = response.json()
    assert suggestion["media_asset_id"] == asset.id
    assert suggestion["motion_evidence_id"] == motion_evidence_id
    assert suggestion["status"] == "pending"


async def test_mock_species_suggestion_for_visit_creates_pending_default_evidence(
    client: httpx.AsyncClient,
) -> None:
    response = await create_mock_species_suggestion(client)

    assert response.status_code == 201
    suggestion = response.json()
    assert suggestion["id"].startswith("species-suggestion-")
    assert suggestion["source_id"] == SOURCE_ID
    assert suggestion["stream_id"] == STREAM_ID
    assert suggestion["event_id"] == BIRD_EVENT_ID
    assert suggestion["visit_id"] == BIRD_VISIT_ID
    assert suggestion["media_asset_id"] is None
    assert suggestion["adapter_id"] == "mock_species_suggester"
    assert suggestion["adapter_name"] == "Mock species suggester"
    assert suggestion["suggested_label"] == "unknown_bird"
    assert suggestion["confidence"] == 0.72
    assert suggestion["rank"] == 1
    assert suggestion["alternatives"] == []
    assert suggestion["status"] == "pending"
    assert "No model runtime or media inspection" in suggestion["notes"]


async def test_mock_species_suggestion_respects_label_and_infers_existing_media(
    client: httpx.AsyncClient,
    isolated_repository: ProductRepository,
) -> None:
    asset = add_test_media_asset(
        isolated_repository,
        media_id="media_mock_species_visit",
        local_path="demo://backyard-feeder/bird-feeder-001.jpg",
    )

    response = await create_mock_species_suggestion(
        client,
        suggested_label="blue_jay",
        confidence=0.64,
        notes="Mock blue jay suggestion for review.",
    )

    assert response.status_code == 201
    suggestion = response.json()
    assert suggestion["suggested_label"] == "blue_jay"
    assert suggestion["confidence"] == 0.64
    assert suggestion["media_asset_id"] == asset.id
    assert suggestion["event_id"] == BIRD_EVENT_ID
    assert suggestion["stream_id"] == STREAM_ID
    assert suggestion["source_id"] == SOURCE_ID
    assert suggestion["notes"] == "Mock blue jay suggestion for review."


async def test_mock_species_suggestion_validates_visit_and_confidence(
    client: httpx.AsyncClient,
) -> None:
    missing_visit = await create_mock_species_suggestion(
        client,
        visit_id="visit-missing",
    )
    invalid_confidence = await create_mock_species_suggestion(
        client,
        confidence=1.2,
    )

    assert missing_visit.status_code == 404
    assert "Visit" in missing_visit.json()["detail"]
    assert invalid_confidence.status_code == 422


async def test_mock_species_suggestion_does_not_create_product_truth(
    client: httpx.AsyncClient,
    isolated_repository: ProductRepository,
) -> None:
    add_test_media_asset(
        isolated_repository,
        media_id="media_mock_species_truth",
        local_path="demo://backyard-feeder/bird-feeder-001.jpg",
    )
    before_truth = await product_truth_snapshot(client)

    response = await create_mock_species_suggestion(client)

    assert response.status_code == 201
    assert response.json()["status"] == "pending"
    assert await product_truth_snapshot(client) == before_truth


async def test_species_suggestion_list_and_filters(
    client: httpx.AsyncClient,
    isolated_repository: ProductRepository,
) -> None:
    asset = add_test_media_asset(isolated_repository)
    cardinal = (
        await create_species_suggestion(
            client,
            media_asset_id=asset.id,
            suggested_label="northern_cardinal",
        )
    ).json()
    blue_jay = (
        await create_species_suggestion(
            client,
            event_id=None,
            visit_id=None,
            media_asset_id=None,
            suggested_label="blue_jay",
            confidence=0.64,
        )
    ).json()
    await client.post(
        f"/api/species-suggestions/{blue_jay['id']}/status",
        json={"status": "rejected"},
    )

    list_response = await client.get("/api/species-suggestions")
    pending_response = await client.get(
        "/api/species-suggestions",
        params={"status": "pending"},
    )
    visit_response = await client.get(
        "/api/species-suggestions",
        params={"visit_id": BIRD_VISIT_ID},
    )
    event_response = await client.get(
        "/api/species-suggestions",
        params={"event_id": BIRD_EVENT_ID},
    )
    media_response = await client.get(
        "/api/species-suggestions",
        params={"media_asset_id": asset.id},
    )
    label_response = await client.get(
        "/api/species-suggestions",
        params={"suggested_label": "blue_jay"},
    )

    assert list_response.status_code == 200
    assert pending_response.status_code == 200
    assert visit_response.status_code == 200
    assert event_response.status_code == 200
    assert media_response.status_code == 200
    assert label_response.status_code == 200
    assert [item["id"] for item in list_response.json()["species_suggestions"]] == [
        cardinal["id"],
        blue_jay["id"],
    ]
    assert [item["id"] for item in pending_response.json()["species_suggestions"]] == [
        cardinal["id"],
    ]
    assert [item["id"] for item in visit_response.json()["species_suggestions"]] == [
        cardinal["id"],
    ]
    assert [item["id"] for item in event_response.json()["species_suggestions"]] == [
        cardinal["id"],
    ]
    assert [item["id"] for item in media_response.json()["species_suggestions"]] == [
        cardinal["id"],
    ]
    assert [item["id"] for item in label_response.json()["species_suggestions"]] == [
        blue_jay["id"],
    ]


async def test_species_suggestion_detail_and_missing_detail(
    client: httpx.AsyncClient,
) -> None:
    created = (await create_species_suggestion(client)).json()

    response = await client.get(f"/api/species-suggestions/{created['id']}")
    missing = await client.get("/api/species-suggestions/species-suggestion-missing")

    assert response.status_code == 200
    assert response.json()["id"] == created["id"]
    assert missing.status_code == 404
    assert "SpeciesSuggestion" in missing.json()["detail"]


@pytest.mark.parametrize("status", ["accepted", "rejected", "superseded"])
async def test_species_suggestion_status_update(
    client: httpx.AsyncClient,
    status: str,
) -> None:
    created = (await create_species_suggestion(client)).json()

    response = await client.post(
        f"/api/species-suggestions/{created['id']}/status",
        json={"status": status},
    )

    assert response.status_code == 200
    assert response.json()["id"] == created["id"]
    assert response.json()["status"] == status


async def test_terminal_species_suggestion_status_cannot_change_again(
    client: httpx.AsyncClient,
) -> None:
    created = (await create_species_suggestion(client)).json()
    accepted = await client.post(
        f"/api/species-suggestions/{created['id']}/status",
        json={"status": "accepted"},
    )

    response = await client.post(
        f"/api/species-suggestions/{created['id']}/status",
        json={"status": "rejected"},
    )

    assert accepted.status_code == 200
    assert response.status_code == 400
    assert "pending SpeciesSuggestion" in response.json()["detail"]


async def test_missing_species_suggestion_status_update_returns_404(
    client: httpx.AsyncClient,
) -> None:
    response = await client.post(
        "/api/species-suggestions/species-suggestion-missing/status",
        json={"status": "accepted"},
    )

    assert response.status_code == 404
    assert "SpeciesSuggestion" in response.json()["detail"]


async def test_invalid_species_suggestion_inputs_return_validation_errors(
    client: httpx.AsyncClient,
) -> None:
    invalid_status = await client.post(
        "/api/species-suggestions/species-suggestion-missing/status",
        json={"status": "confirmed"},
    )
    invalid_confidence = await create_species_suggestion(client, confidence=1.2)
    blank_label = await create_species_suggestion(client, suggested_label="   ")

    assert invalid_status.status_code == 422
    assert invalid_confidence.status_code == 422
    assert blank_label.status_code == 422


@pytest.mark.parametrize(
    ("field", "value", "expected_detail"),
    [
        ("event_id", "event-missing", "Event"),
        ("visit_id", "visit-missing", "Visit"),
        ("media_asset_id", "media-asset-missing", "Media asset"),
        ("motion_evidence_id", "motion-evidence-missing", "Motion Evidence"),
    ],
)
async def test_missing_species_suggestion_references_fail_safely(
    client: httpx.AsyncClient,
    field: str,
    value: str,
    expected_detail: str,
) -> None:
    response = await create_species_suggestion(client, **{field: value})

    assert response.status_code == 404
    assert expected_detail in response.json()["detail"]


async def test_species_suggestion_creation_does_not_create_product_truth(
    client: httpx.AsyncClient,
    isolated_repository: ProductRepository,
) -> None:
    asset = add_test_media_asset(isolated_repository, media_id="media_species_truth_create")
    motion_evidence_id = await create_motion_evidence(client)
    before_truth = await product_truth_snapshot(client)

    response = await create_species_suggestion(
        client,
        media_asset_id=asset.id,
        motion_evidence_id=motion_evidence_id,
    )

    assert response.status_code == 201
    assert response.json()["status"] == "pending"
    assert await product_truth_snapshot(client) == before_truth


async def test_species_suggestion_status_update_does_not_create_product_truth(
    client: httpx.AsyncClient,
) -> None:
    created = (await create_species_suggestion(client)).json()
    before_truth = await product_truth_snapshot(client)

    response = await client.post(
        f"/api/species-suggestions/{created['id']}/status",
        json={"status": "accepted"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "accepted"
    assert await product_truth_snapshot(client) == before_truth
