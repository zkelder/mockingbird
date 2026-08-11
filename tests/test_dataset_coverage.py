from pathlib import Path

import httpx
import pytest

from mockingbird.api.main import app, configure_repository
from mockingbird.repository.product_repository import ProductRepository

pytestmark = pytest.mark.anyio

STREAM_ID = "stream-backyard-feeder"
FEEDER_ZONE_ID = "zone-feeder"
VISIT_ID = "visit-bird-feeder-001"


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


async def import_unknown_bird(client: httpx.AsyncClient):
    return await client.post(
        "/api/media/import",
        data={
            "stream_id": STREAM_ID,
            "zone_id": FEEDER_ZONE_ID,
            "title": "Unknown bird import",
            "subject_label": "unknown_bird",
            "species_guess": "unknown_bird",
            "notes": "Local media for dataset coverage.",
        },
        files={"file": ("unknown-bird.png", b"coverage image bytes", "image/png")},
    )


def species_by_label(summary: dict) -> dict[str, dict]:
    return {species["label"]: species for species in summary["species"]}


async def test_dataset_coverage_summary_shape_and_target_species_gaps(
    client: httpx.AsyncClient,
) -> None:
    response = await client.get("/api/dataset-coverage/summary")

    assert response.status_code == 200
    summary = response.json()
    assert summary["target_species_count"] >= 14
    assert summary["covered_target_species_count"] == 0
    assert summary["missing_target_species_count"] == summary["target_species_count"]
    assert summary["export_ready_count"] == 1
    assert summary["needs_review_count"] == 1
    assert "future model work" in summary["local_first_note"]
    assert "does not run training or classification" in summary["local_first_note"]

    species = species_by_label(summary)
    assert species["northern_cardinal"]["display_name"] == "Northern Cardinal"
    assert species["northern_cardinal"]["reviewed_record_count"] == 0
    assert species["northern_cardinal"]["needs_review_count"] == 1
    assert any(
        gap["label"] == "northern_cardinal"
        and gap["reason"] == "missing_reviewed_examples"
        for gap in summary["gaps"]
    )


async def test_correcting_unknown_bird_updates_species_coverage(
    client: httpx.AsyncClient,
) -> None:
    imported = (await import_unknown_bird(client)).json()
    before = (await client.get("/api/dataset-coverage/summary")).json()

    correction_response = await client.post(
        "/api/review-labels",
        json={"review_origin": "human", 
            "target_type": "visit",
            "target_id": imported["visit"]["id"],
            "label": "Northern Cardinal",
            "notes": "Confirmed species for local dataset coverage.",
        },
    )
    after = (await client.get("/api/dataset-coverage/summary")).json()
    species = species_by_label(after)

    assert correction_response.status_code == 201
    assert after["unknown_bird_count"] == before["unknown_bird_count"] - 1
    assert after["covered_target_species_count"] == before["covered_target_species_count"] + 1
    assert after["missing_target_species_count"] == before["missing_target_species_count"] - 1
    assert species["northern_cardinal"]["reviewed_record_count"] == 1
    assert species["northern_cardinal"]["export_ready_count"] == 1
    assert species["northern_cardinal"]["media_asset_count"] == 1


async def test_freeform_custom_labels_appear_in_dataset_coverage(
    client: httpx.AsyncClient,
) -> None:
    response = await client.post(
        "/api/review-labels",
        json={"review_origin": "human", 
            "target_type": "visit",
            "target_id": VISIT_ID,
            "label": "mystery feeder guest",
            "notes": "User local label before taxonomy exists.",
        },
    )
    summary = (await client.get("/api/dataset-coverage/summary")).json()
    species = species_by_label(summary)

    assert response.status_code == 201
    assert species["mystery_feeder_guest"]["display_name"] == "Mystery Feeder Guest"
    assert species["mystery_feeder_guest"]["category"] == "custom"
    assert species["mystery_feeder_guest"]["is_species"] is False
    assert species["mystery_feeder_guest"]["reviewed_record_count"] == 1


async def test_proposal_labels_do_not_count_as_reviewed_truth_before_correction(
    client: httpx.AsyncClient,
) -> None:
    media_asset = (await import_unknown_bird(client)).json()["media_asset"]
    before = (await client.get("/api/dataset-coverage/summary")).json()

    demo_response = await client.post(
        "/api/detection-runs/demo",
        json={
            "media_asset_id": media_asset["id"],
            "label": "blue_jay",
            "confidence": 0.72,
            "suggested_subject_label": "unknown_bird",
            "suggested_species": "blue_jay",
            "notes": "Proposal evidence should not become truth before review.",
        },
    )
    proposal = demo_response.json()["proposals"][0]
    decision_response = await client.post(
        f"/api/detection-proposals/{proposal['id']}/decision",
        json={"decision": "convert_to_event"},
    )
    after = (await client.get("/api/dataset-coverage/summary")).json()
    species = species_by_label(after)

    assert demo_response.status_code == 201
    assert decision_response.status_code == 200
    assert after["covered_target_species_count"] == before["covered_target_species_count"]
    assert species["blue_jay"]["reviewed_record_count"] == 0
    assert species["blue_jay"]["needs_review_count"] >= 1


async def test_dataset_coverage_aligns_with_dataset_export_readiness(
    client: httpx.AsyncClient,
) -> None:
    coverage = (await client.get("/api/dataset-coverage/summary")).json()
    export_response = await client.post(
        "/api/dataset-exports",
        json={"name": "Coverage alignment export"},
    )
    manifest = export_response.json()["manifest"]

    assert export_response.status_code == 201
    assert coverage["export_ready_count"] == len(manifest["records"])
    assert coverage["needs_review_count"] == manifest["skipped_reasons"]["needs_review"]
