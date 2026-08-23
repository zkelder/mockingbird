from pathlib import Path

import httpx
import pytest

from mockingbird.api.main import app, configure_repository
from mockingbird.repository.product_repository import ProductRepository
from tests.conftest import LegacyAuthenticatedTestClient

pytestmark = pytest.mark.anyio

FEEDER_ZONE_ID = "zone-feeder"
GROUND_ZONE_ID = "zone-ground"


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
    async with LegacyAuthenticatedTestClient(transport=transport, base_url="http://testserver") as api_client:
        yield api_client


async def create_motion_evidence(
    client: httpx.AsyncClient,
    *,
    zone_id: str = FEEDER_ZONE_ID,
    note: str = "Bulk action candidate.",
) -> dict:
    response = await client.post(
        "/api/motion/evidence",
        json={
            "zone_id": zone_id,
            "start_frame_index": 10,
            "end_frame_index": 12,
            "best_frame_index": 11,
            "peak_changed_ratio": 0.42,
            "triggered_frame_count": 2,
            "scoring_config": {
                "pixel_delta_threshold": 25.0,
                "min_changed_ratio": 0.02,
                "source": "bulk_action_test",
            },
            "notes": note,
        },
    )
    assert response.status_code == 201
    return response.json()


async def product_counts(client: httpx.AsyncClient) -> dict[str, int]:
    events = await client.get("/api/events")
    visits = await client.get("/api/visits")
    review_labels = await client.get("/api/review-labels")
    exports = await client.get("/api/dataset-exports")

    assert events.status_code == 200
    assert visits.status_code == 200
    assert review_labels.status_code == 200
    assert exports.status_code == 200

    return {
        "events": len(events.json()),
        "visits": len(visits.json()),
        "review_labels": len(review_labels.json()),
        "exports": len(exports.json()),
    }


async def dataset_truth_counts(client: httpx.AsyncClient) -> dict[str, int]:
    response = await client.get("/api/dataset-coverage/summary")
    assert response.status_code == 200
    coverage = response.json()
    return {
        "export_ready_count": coverage["export_ready_count"],
        "reviewed_record_count": coverage["reviewed_record_count"],
    }


def results_by_status(body: dict, status: str) -> list[dict]:
    return [result for result in body["results"] if result["status"] == status]


async def test_bulk_ignore_marks_multiple_pending_evidence_without_truth(
    client: httpx.AsyncClient,
) -> None:
    first = await create_motion_evidence(client, note="First ignore candidate.")
    second = await create_motion_evidence(
        client,
        zone_id=GROUND_ZONE_ID,
        note="Second ignore candidate.",
    )
    before_counts = await product_counts(client)
    before_truth = await dataset_truth_counts(client)

    response = await client.post(
        "/api/motion-evidence/bulk-action",
        json={
            "motion_evidence_ids": [first["id"], second["id"]],
            "action": "ignore",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["action"] == "ignore"
    assert body["requested_count"] == 2
    assert body["succeeded_count"] == 2
    assert body["skipped_count"] == 0
    assert body["failed_count"] == 0
    assert {result["motion_evidence_id"] for result in body["results"]} == {
        first["id"],
        second["id"],
    }
    assert all(result["created_event_id"] is None for result in body["results"])
    assert all(result["created_visit_id"] is None for result in body["results"])

    for evidence_id in (first["id"], second["id"]):
        detail = await client.get(f"/api/motion/evidence/{evidence_id}")
        assert detail.status_code == 200
        assert detail.json()["status"] == "ignored"

    assert await product_counts(client) == before_counts
    assert await dataset_truth_counts(client) == before_truth


async def test_bulk_promote_creates_reviewable_event_visit_evidence_only(
    client: httpx.AsyncClient,
) -> None:
    first = await create_motion_evidence(client, note="First promote candidate.")
    second = await create_motion_evidence(
        client,
        zone_id=GROUND_ZONE_ID,
        note="Second promote candidate.",
    )
    before_counts = await product_counts(client)
    before_truth = await dataset_truth_counts(client)

    response = await client.post(
        "/api/motion-evidence/bulk-action",
        json={
            "motion_evidence_ids": [first["id"], second["id"]],
            "action": "promote",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["action"] == "promote"
    assert body["requested_count"] == 2
    assert body["succeeded_count"] == 2
    assert body["skipped_count"] == 0
    assert body["failed_count"] == 0

    after_counts = await product_counts(client)
    assert after_counts["events"] == before_counts["events"] + 2
    assert after_counts["visits"] == before_counts["visits"] + 2
    assert after_counts["review_labels"] == before_counts["review_labels"]
    assert after_counts["exports"] == before_counts["exports"]
    assert await dataset_truth_counts(client) == before_truth

    for result in body["results"]:
        assert result["status"] == "succeeded"
        assert result["created_event_id"] is not None
        assert result["created_visit_id"] is not None

        evidence = await client.get(f"/api/motion/evidence/{result['motion_evidence_id']}")
        event = await client.get(f"/api/events/{result['created_event_id']}")
        visit = await client.get(f"/api/visits/{result['created_visit_id']}")
        event_detail = await client.get(f"/api/events/{result['created_event_id']}/detail")
        visit_detail = await client.get(f"/api/visits/{result['created_visit_id']}/detail")

        assert evidence.status_code == 200
        assert event.status_code == 200
        assert visit.status_code == 200
        assert event_detail.status_code == 200
        assert visit_detail.status_code == 200

        evidence_body = evidence.json()
        assert evidence_body["status"] == "promoted"
        assert evidence_body["promoted_event_id"] == result["created_event_id"]
        assert evidence_body["promoted_visit_id"] == result["created_visit_id"]

        event_body = event.json()
        assert event_body["event_type"] == "motion_evidence"
        assert event_body["review_status"] == "needs_review"
        assert event_body["detections"] == []

        visit_body = visit.json()
        assert visit_body["subject_label"] == "unknown_animal"
        assert visit_body["species_guess"] is None
        assert visit_body["confidence"] is None
        assert visit_body["reviewed_label"] is None
        assert visit_body["review_status"] == "needs_review"
        assert event_detail.json()["dataset_ready"] is False
        assert visit_detail.json()["dataset_ready"] is False


async def test_bulk_promote_skips_unknown_duplicates_and_non_pending_evidence(
    client: httpx.AsyncClient,
) -> None:
    pending = await create_motion_evidence(client, note="Pending promote candidate.")
    ignored = await create_motion_evidence(client, note="Ignored promote candidate.")
    already_promoted = await create_motion_evidence(client, note="Already promoted candidate.")
    ignore_response = await client.post(f"/api/motion/evidence/{ignored['id']}/ignore")
    promote_response = await client.post(f"/api/motion/evidence/{already_promoted['id']}/promote")
    assert ignore_response.status_code == 200
    assert promote_response.status_code == 200
    before_counts = await product_counts(client)
    before_truth = await dataset_truth_counts(client)

    response = await client.post(
        "/api/motion-evidence/bulk-action",
        json={
            "motion_evidence_ids": [
                pending["id"],
                pending["id"],
                ignored["id"],
                already_promoted["id"],
                "motion-evidence-missing",
            ],
            "action": "promote",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["requested_count"] == 5
    assert body["succeeded_count"] == 1
    assert body["skipped_count"] == 4
    assert body["failed_count"] == 0

    succeeded = results_by_status(body, "succeeded")
    skipped = results_by_status(body, "skipped")
    assert [result["motion_evidence_id"] for result in succeeded] == [pending["id"]]
    assert sum(1 for result in skipped if result["motion_evidence_id"] == pending["id"]) == 1
    assert any(result["motion_evidence_id"] == ignored["id"] for result in skipped)
    assert any(result["motion_evidence_id"] == already_promoted["id"] for result in skipped)
    assert any(result["motion_evidence_id"] == "motion-evidence-missing" for result in skipped)

    after_counts = await product_counts(client)
    assert after_counts["events"] == before_counts["events"] + 1
    assert after_counts["visits"] == before_counts["visits"] + 1
    assert after_counts["review_labels"] == before_counts["review_labels"]
    assert after_counts["exports"] == before_counts["exports"]
    assert await dataset_truth_counts(client) == before_truth


async def test_bulk_ignore_skips_already_promoted_ignored_unknown_and_duplicates(
    client: httpx.AsyncClient,
) -> None:
    pending = await create_motion_evidence(client, note="Pending ignore candidate.")
    ignored = await create_motion_evidence(client, note="Already ignored candidate.")
    already_promoted = await create_motion_evidence(client, note="Promoted ignore candidate.")
    ignore_response = await client.post(f"/api/motion/evidence/{ignored['id']}/ignore")
    promote_response = await client.post(f"/api/motion/evidence/{already_promoted['id']}/promote")
    assert ignore_response.status_code == 200
    assert promote_response.status_code == 200
    before_counts = await product_counts(client)
    before_truth = await dataset_truth_counts(client)

    response = await client.post(
        "/api/motion-evidence/bulk-action",
        json={
            "motion_evidence_ids": [
                pending["id"],
                pending["id"],
                ignored["id"],
                already_promoted["id"],
                "motion-evidence-missing",
            ],
            "action": "ignore",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["requested_count"] == 5
    assert body["succeeded_count"] == 1
    assert body["skipped_count"] == 4
    assert body["failed_count"] == 0

    assert [result["motion_evidence_id"] for result in results_by_status(body, "succeeded")] == [
        pending["id"]
    ]
    detail = await client.get(f"/api/motion/evidence/{pending['id']}")
    assert detail.status_code == 200
    assert detail.json()["status"] == "ignored"
    assert await product_counts(client) == before_counts
    assert await dataset_truth_counts(client) == before_truth
