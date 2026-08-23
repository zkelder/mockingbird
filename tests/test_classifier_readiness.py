from pathlib import Path

import httpx
import pytest

from mockingbird.api.main import app, configure_repository
from mockingbird.repository.product_repository import ProductRepository
from tests.conftest import LegacyAuthenticatedTestClient

pytestmark = pytest.mark.anyio

SOURCE_ID = "source-backyard-demo"
STREAM_ID = "stream-backyard-feeder"
FEEDER_ZONE_ID = "zone-feeder"
BIRD_VISIT_ID = "visit-bird-feeder-001"


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
    async with LegacyAuthenticatedTestClient(transport=transport, base_url="http://testserver") as api_client:
        yield api_client


async def classifier_readiness(client: httpx.AsyncClient) -> dict:
    response = await client.get("/api/classifier-readiness")
    assert response.status_code == 200
    return response.json()


async def import_bird_media(client: httpx.AsyncClient, *, title: str = "Classifier bird") -> dict:
    response = await client.post(
        "/api/media/import",
        data={
            "stream_id": STREAM_ID,
            "zone_id": FEEDER_ZONE_ID,
            "title": title,
            "subject_label": "unknown_bird",
            "species_guess": "unknown_bird",
            "notes": "Tiny local media for classifier readiness tests.",
        },
        files={"file": ("classifier-bird.png", b"classifier readiness image", "image/png")},
    )
    assert response.status_code == 201
    return response.json()


async def correct_visit(client: httpx.AsyncClient, visit_id: str, label: str) -> dict:
    response = await client.post(
        "/api/review-labels",
        json={"review_origin": "human", 
            "target_type": "visit",
            "target_id": visit_id,
            "label": label,
            "notes": "Classifier readiness correction truth.",
        },
    )
    assert response.status_code == 201
    return response.json()


async def create_accepted_species_suggestion(
    client: httpx.AsyncClient,
    *,
    imported: dict,
) -> dict:
    suggestion_response = await client.post(
        "/api/species-suggestions",
        json={
            "source_id": SOURCE_ID,
            "stream_id": STREAM_ID,
            "event_id": imported["event"]["id"],
            "visit_id": imported["visit"]["id"],
            "media_asset_id": imported["media_asset"]["id"],
            "adapter_id": "mock_species_adapter",
            "adapter_name": "Mock Species Adapter",
            "suggested_label": "northern_cardinal",
            "suggested_common_name": "Northern Cardinal",
            "suggested_scientific_name": "Cardinalis cardinalis",
            "confidence": 0.84,
            "rank": 1,
            "alternatives": [],
            "notes": "Accepted suggestion remains evidence only.",
        },
    )
    assert suggestion_response.status_code == 201
    suggestion = suggestion_response.json()

    accepted_response = await client.post(
        f"/api/species-suggestions/{suggestion['id']}/status",
        json={"status": "accepted"},
    )
    assert accepted_response.status_code == 200
    return accepted_response.json()


async def create_motion_evidence(client: httpx.AsyncClient) -> dict:
    response = await client.post(
        "/api/motion/evidence",
        json={
            "zone_id": FEEDER_ZONE_ID,
            "start_frame_index": 4,
            "end_frame_index": 6,
            "best_frame_index": 5,
            "peak_changed_ratio": 0.31,
            "triggered_frame_count": 2,
            "scoring_config": {"source": "classifier_readiness_test"},
        },
    )
    assert response.status_code == 201
    return response.json()


async def local_truth_snapshot(client: httpx.AsyncClient) -> dict:
    responses = {
        "events": await client.get("/api/events"),
        "visits": await client.get("/api/visits"),
        "review_labels": await client.get("/api/review-labels"),
        "exports": await client.get("/api/dataset-exports"),
        "detection_runs": await client.get("/api/detection-runs"),
        "coverage": await client.get("/api/dataset-coverage/summary"),
    }
    for response in responses.values():
        assert response.status_code == 200

    coverage = responses["coverage"].json()
    return {
        "events": len(responses["events"].json()),
        "visits": len(responses["visits"].json()),
        "review_labels": len(responses["review_labels"].json()),
        "exports": len(responses["exports"].json()),
        "detection_runs": len(responses["detection_runs"].json()),
        "reviewed_record_count": coverage["reviewed_record_count"],
        "export_ready_count": coverage["export_ready_count"],
    }


def skipped_by_reason(report: dict) -> dict[str, int]:
    return {item["reason"]: item["count"] for item in report["skipped"]}


def species_by_label(report: dict) -> dict[str, dict]:
    return {item["label"]: item for item in report["species"]}


async def test_classifier_readiness_report_shape_and_read_only_behavior(
    client: httpx.AsyncClient,
) -> None:
    truth_before = await local_truth_snapshot(client)

    first = await classifier_readiness(client)
    second = await classifier_readiness(client)

    assert second == first
    assert await local_truth_snapshot(client) == truth_before
    assert first["ready_for_manifest_export"] is False
    assert first["reviewed_examples"] == 1
    assert first["media_backed_reviewed_examples"] == 0
    assert first["export_ready_examples"] == 0
    assert first["missing_target_labels"]
    assert skipped_by_reason(first)["unreviewed"] == 1
    assert skipped_by_reason(first)["missing_media"] == 1
    assert first["unknown_label_count"] == 0
    assert first["false_positive_count"] == 0
    assert first["out_of_taxonomy_count"] == 0
    assert "No reviewed media-backed examples" in first["warnings"][0]


async def test_reviewed_media_backed_species_example_updates_readiness(
    client: httpx.AsyncClient,
) -> None:
    before = await classifier_readiness(client)
    imported = await import_bird_media(client)

    await correct_visit(client, imported["visit"]["id"], "Northern Cardinal")
    after = await classifier_readiness(client)
    species = species_by_label(after)

    assert after["reviewed_examples"] == before["reviewed_examples"] + 1
    assert after["media_backed_reviewed_examples"] == before["media_backed_reviewed_examples"] + 1
    assert after["export_ready_examples"] == before["export_ready_examples"] + 1
    assert after["ready_for_manifest_export"] is True
    assert "northern_cardinal" not in after["missing_target_labels"]
    assert species["northern_cardinal"]["reviewed_examples"] == 1
    assert species["northern_cardinal"]["media_backed_examples"] == 1
    assert species["northern_cardinal"]["export_ready_examples"] == 1
    assert "low_example_count" in species["northern_cardinal"]["warnings"]


async def test_unreviewed_media_backed_visit_is_not_training_truth(
    client: httpx.AsyncClient,
) -> None:
    before = await classifier_readiness(client)

    await import_bird_media(client)
    after = await classifier_readiness(client)

    assert after["reviewed_examples"] == before["reviewed_examples"]
    assert after["media_backed_reviewed_examples"] == before["media_backed_reviewed_examples"]
    assert after["export_ready_examples"] == before["export_ready_examples"]
    assert skipped_by_reason(after)["unreviewed"] == skipped_by_reason(before)["unreviewed"] + 1


async def test_accepted_species_suggestion_alone_is_not_training_truth(
    client: httpx.AsyncClient,
) -> None:
    imported = await import_bird_media(client)
    before = await classifier_readiness(client)

    suggestion = await create_accepted_species_suggestion(client, imported=imported)
    after = await classifier_readiness(client)

    assert suggestion["status"] == "accepted"
    assert after == before


async def test_motion_evidence_alone_is_not_training_truth(
    client: httpx.AsyncClient,
) -> None:
    before = await classifier_readiness(client)

    evidence = await create_motion_evidence(client)
    after = await classifier_readiness(client)

    assert evidence["status"] == "pending"
    assert after == before


async def test_unknown_and_false_positive_labels_are_counted_separately(
    client: httpx.AsyncClient,
) -> None:
    unknown_import = await import_bird_media(client, title="Unknown reviewed bird")
    false_import = await import_bird_media(client, title="False positive reviewed bird")

    await correct_visit(client, unknown_import["visit"]["id"], "unknown_bird")
    await correct_visit(client, false_import["visit"]["id"], "false_positive")
    report = await classifier_readiness(client)
    skipped = skipped_by_reason(report)

    assert report["unknown_label_count"] == 1
    assert report["false_positive_count"] == 1
    assert skipped["unknown_label"] == 1
    assert skipped["false_positive_policy_excluded"] == 1
    assert report["export_ready_examples"] == 0
    assert report["ready_for_manifest_export"] is False


async def test_missing_media_reviewed_species_is_not_manifest_ready(
    client: httpx.AsyncClient,
) -> None:
    before = await classifier_readiness(client)

    await correct_visit(client, BIRD_VISIT_ID, "Northern Cardinal")
    after = await classifier_readiness(client)
    species = species_by_label(after)

    assert after["reviewed_examples"] == before["reviewed_examples"] + 1
    assert after["media_backed_reviewed_examples"] == before["media_backed_reviewed_examples"]
    assert after["export_ready_examples"] == before["export_ready_examples"]
    assert after["ready_for_manifest_export"] is False
    assert skipped_by_reason(after)["missing_media"] == skipped_by_reason(before)["missing_media"] + 1
    assert species["northern_cardinal"]["media_backed_examples"] == 0
    assert "northern_cardinal" in after["missing_target_labels"]


async def test_out_of_taxonomy_reviewed_label_is_flagged_not_export_ready(
    client: httpx.AsyncClient,
) -> None:
    imported = await import_bird_media(client)

    await correct_visit(client, imported["visit"]["id"], "mystery feeder guest")
    report = await classifier_readiness(client)

    assert report["out_of_taxonomy_count"] == 1
    assert skipped_by_reason(report)["out_of_taxonomy"] == 1
    assert report["media_backed_reviewed_examples"] == 1
    assert report["export_ready_examples"] == 0
    assert "mystery_feeder_guest" not in species_by_label(report)


async def test_classifier_readiness_does_not_create_review_export_or_model_truth(
    client: httpx.AsyncClient,
) -> None:
    imported = await import_bird_media(client)
    await correct_visit(client, imported["visit"]["id"], "Blue Jay")
    truth_before = await local_truth_snapshot(client)

    report = await classifier_readiness(client)

    assert report["ready_for_manifest_export"] is True
    assert await local_truth_snapshot(client) == truth_before
