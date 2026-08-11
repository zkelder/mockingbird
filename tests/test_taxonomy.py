from pathlib import Path

import httpx
import pytest

from mockingbird.api.main import app, configure_repository
from mockingbird.repository.product_repository import ProductRepository

pytestmark = pytest.mark.anyio

VISIT_ID = "visit-bird-feeder-001"
STREAM_ID = "stream-backyard-feeder"
FEEDER_ZONE_ID = "zone-feeder"


@pytest.fixture(autouse=True)
def isolated_repository(tmp_path: Path) -> None:
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
            "title": "Imported feeder observation",
            "subject_label": "unknown_bird",
            "species_guess": "unknown_bird",
            "notes": "Local media for taxonomy proposal boundary.",
        },
        files={"file": ("feeder-bird.png", b"taxonomy image bytes", "image/png")},
    )


async def test_taxonomy_labels_are_seeded_and_initialization_is_idempotent(
    tmp_path: Path,
) -> None:
    db_url = f"sqlite:///{tmp_path / 'idempotent.sqlite3'}"
    first_repository = ProductRepository(db_url=db_url, media_root=tmp_path / "media")
    first_count = len(first_repository.list_taxonomy_labels())

    second_repository = ProductRepository(db_url=db_url, media_root=tmp_path / "media")
    second_labels = second_repository.list_taxonomy_labels()

    assert first_count == len(second_labels)
    assert first_count >= 23
    assert [label.label for label in second_labels].count("northern_cardinal") == 1


async def test_taxonomy_label_routes_and_suggestions(client: httpx.AsyncClient) -> None:
    labels_response = await client.get("/api/taxonomy/labels")
    detail_response = await client.get("/api/taxonomy/labels/northern_cardinal")
    display_name_response = await client.get("/api/taxonomy/labels/Northern%20Cardinal")
    suggestions_response = await client.get(
        "/api/taxonomy/suggestions",
        params={"query": "cardinal"},
    )
    bird_suggestions_response = await client.get(
        "/api/taxonomy/suggestions",
        params={"query": "cardinal", "category": "bird"},
    )
    species_suggestions_response = await client.get(
        "/api/taxonomy/suggestions",
        params={"query": "cardinal", "category": "species"},
    )

    assert labels_response.status_code == 200
    labels = labels_response.json()
    assert "unknown_bird" in {label["label"] for label in labels}
    assert "false_positive" in {label["label"] for label in labels}
    assert detail_response.status_code == 200
    assert detail_response.json()["display_name"] == "Northern Cardinal"
    assert display_name_response.status_code == 200
    assert display_name_response.json()["label"] == "northern_cardinal"
    assert [item["label"] for item in suggestions_response.json()] == ["northern_cardinal"]
    assert [item["label"] for item in bird_suggestions_response.json()] == ["northern_cardinal"]
    assert [item["label"] for item in species_suggestions_response.json()] == [
        "northern_cardinal"
    ]


async def test_review_correction_normalizes_taxonomy_display_name(
    client: httpx.AsyncClient,
) -> None:
    response = await client.post(
        "/api/review-labels",
        json={"review_origin": "human", 
            "target_type": "visit",
            "target_id": VISIT_ID,
            "label": "Northern Cardinal",
            "notes": "Confirmed species from review.",
        },
    )

    assert response.status_code == 201
    result = response.json()
    assert result["review_label"]["label"] == "northern_cardinal"
    assert result["visit"]["reviewed_label"] == "northern_cardinal"
    assert result["analytics"]["species_counts"]["northern_cardinal"] >= 1
    assert result["analytics"]["label_display_names"]["northern_cardinal"] == "Northern Cardinal"
    assert result["analytics"]["label_categories"]["northern_cardinal"] == "bird"


async def test_review_correction_allows_freeform_labels(client: httpx.AsyncClient) -> None:
    response = await client.post(
        "/api/review-labels",
        json={"review_origin": "human", 
            "target_type": "visit",
            "target_id": VISIT_ID,
            "label": "mystery feeder guest",
            "notes": "User local label before taxonomy exists.",
        },
    )

    assert response.status_code == 201
    result = response.json()
    assert result["review_label"]["label"] == "mystery_feeder_guest"
    assert result["visit"]["reviewed_label"] == "mystery_feeder_guest"
    assert "mystery_feeder_guest" in result["analytics"]["species_counts"]


async def test_normalized_correction_appears_in_export_manifest(
    client: httpx.AsyncClient,
) -> None:
    correction_response = await client.post(
        "/api/review-labels",
        json={"review_origin": "human", 
            "target_type": "visit",
            "target_id": VISIT_ID,
            "label": "Northern Cardinal",
            "notes": "Confirmed export species.",
        },
    )
    export_response = await client.post(
        "/api/dataset-exports",
        json={"name": "Taxonomy reviewed export"},
    )

    assert correction_response.status_code == 201
    assert export_response.status_code == 201
    record = next(
        record
        for record in export_response.json()["manifest"]["records"]
        if record["visit_id"] == VISIT_ID
    )
    assert record["label"] == "northern_cardinal"
    assert record["label_display_name"] == "Northern Cardinal"
    assert record["label_category"] == "bird"
    assert record["is_species"] is True


async def test_detection_proposal_label_remains_evidence_until_review(
    client: httpx.AsyncClient,
) -> None:
    media_asset = (await import_image(client)).json()["media_asset"]

    response = await client.post(
        "/api/detection-runs/demo",
        json={
            "media_asset_id": media_asset["id"],
            "label": "candidate hawk",
            "suggested_subject_label": "unknown_bird",
            "notes": "Proposal evidence is not taxonomy truth.",
        },
    )
    analytics_response = await client.get("/api/analytics/summary")

    assert response.status_code == 201
    proposal = response.json()["proposals"][0]
    assert proposal["label"] == "candidate hawk"
    assert proposal["event_id"] is None
    assert proposal["visit_id"] is None
    assert "candidate_hawk" not in analytics_response.json()["species_counts"]
