from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from mockingbird.api.main import app, configure_repository
from mockingbird.repository import product_repository as product_repository_module
from mockingbird.repository.product_repository import ProductRepository
from mockingbird.storage.models import EventModel, VisitModel
from tests.conftest import LegacyAuthenticatedTestClient

pytestmark = pytest.mark.anyio

STREAM_ID = "stream-backyard-feeder"
FEEDER_ZONE_ID = "zone-feeder"
BIRD_EVENT_ID = "event-bird-feeder-001"
BIRD_VISIT_ID = "visit-bird-feeder-001"


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


def add_reviewable_visit(
    repository: ProductRepository,
    *,
    event_id: str,
    visit_id: str,
    species_guess: str = "unknown_bird",
) -> None:
    with repository.session_factory() as session:
        with session.begin():
            session.add(
                EventModel(
                    id=event_id,
                    stream_id=STREAM_ID,
                    title=f"Reviewable event {event_id}",
                    event_type="manual_review_fixture",
                    started_at=datetime.now(UTC),
                    ended_at=datetime.now(UTC),
                    primary_zone_id=FEEDER_ZONE_ID,
                    review_status="needs_review",
                )
            )
            session.add(
                VisitModel(
                    id=visit_id,
                    event_id=event_id,
                    subject_label="unknown_bird",
                    species_guess=species_guess,
                    confidence=None,
                    reviewed_label=None,
                    review_status="needs_review",
                    representative_media_path=None,
                )
            )


def add_reviewable_event(repository: ProductRepository, event_id: str) -> None:
    with repository.session_factory() as session:
        with session.begin():
            session.add(
                EventModel(
                    id=event_id,
                    stream_id=STREAM_ID,
                    title=f"Reviewable event {event_id}",
                    event_type="manual_review_fixture",
                    started_at=datetime.now(UTC),
                    ended_at=datetime.now(UTC),
                    primary_zone_id=FEEDER_ZONE_ID,
                    review_status="needs_review",
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


def assert_only_review_labels_changed(
    before: dict[str, int],
    after: dict[str, int],
    expected_created_count: int,
) -> None:
    assert after["review_labels"] == before["review_labels"] + expected_created_count
    for key in (
        "events",
        "visits",
        "motion_evidence",
        "species_suggestions",
        "detection_proposals",
        "dataset_exports",
        "media_assets",
    ):
        assert after[key] == before[key]


def install_runtime_tripwires(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_if_called(*args, **kwargs):  # noqa: ANN002, ANN003
        raise AssertionError("Bulk review correction must not call model or suggestion runtimes")

    monkeypatch.setattr(product_repository_module, "run_local_image_detector", fail_if_called)
    monkeypatch.setattr(product_repository_module, "run_megadetector_on_image", fail_if_called)
    monkeypatch.setattr(ProductRepository, "create_species_suggestion", fail_if_called)


async def review_label_by_id(client: httpx.AsyncClient, review_label_id: str) -> dict:
    response = await client.get("/api/review-labels")
    assert response.status_code == 200
    return next(label for label in response.json() if label["id"] == review_label_id)


async def test_bulk_corrects_multiple_review_queue_visits_as_user_truth(
    client: httpx.AsyncClient,
    isolated_repository: ProductRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    add_reviewable_visit(
        isolated_repository,
        event_id="event-bulk-review-visit-001",
        visit_id="visit-bulk-review-001",
    )
    add_reviewable_visit(
        isolated_repository,
        event_id="event-bulk-review-visit-002",
        visit_id="visit-bulk-review-002",
    )
    before = await product_counts(client)
    install_runtime_tripwires(monkeypatch)

    response = await client.post(
        "/api/review-queue/bulk-correct",
        json={"review_origin": "human", 
            "target_type": "visit",
            "target_ids": ["visit-bulk-review-001", "visit-bulk-review-002"],
            "label": "blue_jay",
            "notes": "Bulk user correction.",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["requested_count"] == 2
    assert body["succeeded_count"] == 2
    assert body["skipped_count"] == 0
    assert body["failed_count"] == 0
    assert set(body) == {
        "requested_count",
        "succeeded_count",
        "skipped_count",
        "failed_count",
        "results",
    }

    created_ids = [result["created_review_label_id"] for result in body["results"]]
    assert all(review_label_id is not None for review_label_id in created_ids)
    for result, visit_id in zip(body["results"], ["visit-bulk-review-001", "visit-bulk-review-002"]):
        assert result["target_id"] == visit_id
        assert result["status"] == "succeeded"
        assert result["message"] == "Correction saved as ReviewLabel truth."
        review_label = await review_label_by_id(client, result["created_review_label_id"])
        assert review_label["target_type"] == "visit"
        assert review_label["target_id"] == visit_id
        assert review_label["label"] == "blue_jay"
        assert review_label["notes"] == "Bulk user correction."

        visit_response = await client.get(f"/api/visits/{visit_id}")
        assert visit_response.status_code == 200
        visit = visit_response.json()
        assert visit["review_status"] == "reviewed"
        assert visit["reviewed_label"] == "blue_jay"

    queue = (await client.get("/api/review-queue")).json()
    assert all(item["visit_id"] not in {"visit-bulk-review-001", "visit-bulk-review-002"} for item in queue)
    assert_only_review_labels_changed(before, await product_counts(client), expected_created_count=2)


async def test_bulk_correction_skips_duplicate_unknown_and_already_reviewed_visits(
    client: httpx.AsyncClient,
    isolated_repository: ProductRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    add_reviewable_visit(
        isolated_repository,
        event_id="event-bulk-review-eligible",
        visit_id="visit-bulk-review-eligible",
    )
    add_reviewable_visit(
        isolated_repository,
        event_id="event-bulk-review-reviewed",
        visit_id="visit-bulk-review-reviewed",
    )
    reviewed_response = await client.post(
        "/api/review-labels",
        json={"review_origin": "human", 
            "target_type": "visit",
            "target_id": "visit-bulk-review-reviewed",
            "label": "northern_cardinal",
        },
    )
    assert reviewed_response.status_code == 201
    before = await product_counts(client)
    install_runtime_tripwires(monkeypatch)

    response = await client.post(
        "/api/review-queue/bulk-correct",
        json={"review_origin": "human", 
            "target_type": "visit",
            "target_ids": [
                "visit-bulk-review-eligible",
                "visit-bulk-review-eligible",
                "visit-bulk-review-reviewed",
                "visit-missing",
            ],
            "label": "squirrel",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["requested_count"] == 4
    assert body["succeeded_count"] == 1
    assert body["skipped_count"] == 3
    assert body["failed_count"] == 0
    assert [result["status"] for result in body["results"]] == [
        "succeeded",
        "skipped",
        "skipped",
        "skipped",
    ]
    assert body["results"][1]["message"] == (
        "Duplicate target id in request; only the first occurrence was processed."
    )
    assert body["results"][2]["message"] == (
        "Visit is already reviewed or not eligible for Review Queue correction."
    )
    assert body["results"][3]["message"] == "Visit was not found."

    assert_only_review_labels_changed(before, await product_counts(client), expected_created_count=1)


async def test_bulk_correction_handles_event_targets_and_ineligible_events(
    client: httpx.AsyncClient,
    isolated_repository: ProductRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    add_reviewable_event(isolated_repository, "event-bulk-review-event-only")
    before = await product_counts(client)
    install_runtime_tripwires(monkeypatch)

    response = await client.post(
        "/api/review-queue/bulk-correct",
        json={"review_origin": "human", 
            "target_type": "event",
            "target_ids": [
                "event-bulk-review-event-only",
                BIRD_EVENT_ID,
                BIRD_VISIT_ID,
            ],
            "label": "cat",
            "notes": "Bulk event correction.",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["requested_count"] == 3
    assert body["succeeded_count"] == 1
    assert body["skipped_count"] == 2
    assert body["failed_count"] == 0
    assert body["results"][0]["status"] == "succeeded"
    assert body["results"][1]["message"] == "Event has reviewable Visits; correct Visits first."
    assert body["results"][2]["message"] == "Event was not found."

    review_label = await review_label_by_id(client, body["results"][0]["created_review_label_id"])
    assert review_label["target_type"] == "event"
    assert review_label["target_id"] == "event-bulk-review-event-only"
    assert review_label["label"] == "cat"
    event = (await client.get("/api/events/event-bulk-review-event-only")).json()
    assert event["review_status"] == "reviewed"
    assert_only_review_labels_changed(before, await product_counts(client), expected_created_count=1)


async def test_bulk_correction_requires_explicit_label(
    client: httpx.AsyncClient,
) -> None:
    before = await product_counts(client)

    response = await client.post(
        "/api/review-queue/bulk-correct",
        json={"review_origin": "human", 
            "target_type": "visit",
            "target_ids": [BIRD_VISIT_ID],
            "label": " ",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "A correction label is required."
    assert await product_counts(client) == before
