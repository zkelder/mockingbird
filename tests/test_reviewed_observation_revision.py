from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
from sqlalchemy import select

from mockingbird.api.main import app, configure_repository
from mockingbird.repository.product_repository import ProductRepository
from mockingbird.storage.models import EventModel, ReviewLabelModel, VisitModel


STREAM_ID = "stream-backyard-feeder"
VISIT_ID = "visit-reviewed-revision"
EVENT_ID = "event-reviewed-revision"

pytestmark = pytest.mark.anyio


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


def add_reviewable_visit(repository: ProductRepository) -> None:
    now = datetime.now(UTC)
    with repository.session_factory() as session:
        with session.begin():
            session.add(
                EventModel(
                    id=EVENT_ID,
                    stream_id=STREAM_ID,
                    title="Reviewed revision fixture",
                    event_type="reviewed_revision_fixture",
                    started_at=now,
                    ended_at=now,
                    primary_zone_id="zone-feeder",
                    review_status="needs_review",
                )
            )
            session.add(
                VisitModel(
                    id=VISIT_ID,
                    event_id=EVENT_ID,
                    subject_label="bird",
                    species_guess="northern_cardinal",
                    confidence=None,
                    reviewed_label=None,
                    review_status="needs_review",
                    representative_media_path=None,
                )
            )


async def initial_correction(client: httpx.AsyncClient, label: str = "northern_cardinal") -> None:
    response = await client.post(
        "/api/review-labels",
        json={"review_origin": "human", "target_type": "visit", "target_id": VISIT_ID, "label": label},
    )
    assert response.status_code == 201


async def detail(client: httpx.AsyncClient) -> dict:
    response = await client.get(f"/api/visits/{VISIT_ID}/detail")
    assert response.status_code == 200
    return response.json()


async def test_revision_keeps_one_effective_truth_for_bird_log_dashboard_analytics_and_exports(
    client: httpx.AsyncClient,
    isolated_repository: ProductRepository,
) -> None:
    add_reviewable_visit(isolated_repository)
    await initial_correction(client)
    before = await detail(client)
    revision_payload = {
        "label": "house_finch",
        "notes": "Wing markings are clearer in the supporting frame.",
        "expected_state_token": before["review_state_token"],
        "idempotency_key": "revision-house-finch",
        "review_origin": "human",
    }

    revised = await client.post(f"/api/visits/{VISIT_ID}/revision", json=revision_payload)
    assert revised.status_code == 200
    assert revised.json()["idempotent"] is False
    repeated = await client.post(f"/api/visits/{VISIT_ID}/revision", json=revision_payload)
    assert repeated.status_code == 200
    assert repeated.json()["idempotent"] is True

    history = (await client.get(f"/api/visits/{VISIT_ID}/correction-history")).json()
    assert [entry["label"] for entry in history["entries"]] == ["house_finch", "northern_cardinal"]
    assert history["entries"][0]["action"] == "Revised identification"
    assert history["entries"][0]["is_current"] is True
    assert history["entries"][1]["is_current"] is False

    labels = await client.get("/api/review-labels")
    assert [
        label["label"]
        for label in labels.json()
        if label["target_type"] == "visit" and label["target_id"] == VISIT_ID
    ] == ["house_finch"]
    with isolated_repository.session_factory() as session:
        raw_labels = session.scalars(
            select(ReviewLabelModel)
            .where(ReviewLabelModel.target_type == "visit", ReviewLabelModel.target_id == VISIT_ID)
            .order_by(ReviewLabelModel.created_at, ReviewLabelModel.id)
        ).all()
        assert len(raw_labels) == 2
        assert raw_labels[1].supersedes_review_label_id == raw_labels[0].id

    dashboard = (await client.get("/api/dashboard/summary")).json()
    assert any(
        observation["label"] == "house_finch" and observation["observation_count"] == 1
        for observation in dashboard["today_observations"]
    )
    assert all(observation["label"] != "northern_cardinal" for observation in dashboard["today_observations"])
    analytics = (await client.get("/api/analytics/summary")).json()
    assert analytics["species_counts"]["house_finch"] == 1
    assert "northern_cardinal" not in analytics["species_counts"]
    export = await client.post(
        "/api/dataset-exports",
        json={"name": "Reviewed revision export", "reviewed_only": True},
    )
    assert export.status_code == 201
    assert [
        record["label"]
        for record in export.json()["manifest"]["records"]
        if record["visit_id"] == VISIT_ID
    ] == ["house_finch"]


async def test_outcome_revisions_change_only_current_truth_and_reject_stale_writes(
    client: httpx.AsyncClient,
    isolated_repository: ProductRepository,
) -> None:
    add_reviewable_visit(isolated_repository)
    await initial_correction(client)
    first_detail = await detail(client)

    blank = await client.post(
        f"/api/visits/{VISIT_ID}/revision",
        json={"review_origin": "human", 
            "label": "blank",
            "expected_state_token": first_detail["review_state_token"],
            "idempotency_key": "revision-blank",
        },
    )
    assert blank.status_code == 200
    dashboard = (await client.get("/api/dashboard/summary")).json()
    assert all(observation["label"] != "northern_cardinal" for observation in dashboard["today_observations"])
    assert all(observation["label"] != "blank" for observation in dashboard["today_observations"])

    stale = await client.post(
        f"/api/visits/{VISIT_ID}/revision",
        json={"review_origin": "human", 
            "label": "blue_jay",
            "expected_state_token": first_detail["review_state_token"],
            "idempotency_key": "revision-stale",
        },
    )
    assert stale.status_code == 409

    blank_detail = await detail(client)
    bird = await client.post(
        f"/api/visits/{VISIT_ID}/revision",
        json={"review_origin": "human", 
            "label": "blue_jay",
            "expected_state_token": blank_detail["review_state_token"],
            "idempotency_key": "revision-blue-jay",
        },
    )
    assert bird.status_code == 200
    bird_detail = await detail(client)
    non_bird = await client.post(
        f"/api/visits/{VISIT_ID}/revision",
        json={"review_origin": "human", 
            "label": "non_bird",
            "expected_state_token": bird_detail["review_state_token"],
            "idempotency_key": "revision-non-bird",
        },
    )
    assert non_bird.status_code == 200
    dashboard = (await client.get("/api/dashboard/summary")).json()
    assert all(observation["label"] != "blue_jay" for observation in dashboard["today_observations"])
    assert any(observation["label"] == "non_bird" for observation in dashboard["reviewed_non_bird_activity"])


async def test_reopen_preserves_evidence_history_and_suggestions_without_duplicate_queue_item(
    client: httpx.AsyncClient,
    isolated_repository: ProductRepository,
) -> None:
    add_reviewable_visit(isolated_repository)
    await initial_correction(client)
    created_suggestion = await client.post(
        "/api/species-suggestions/mock",
        json={"visit_id": VISIT_ID, "suggested_label": "blue_jay"},
    )
    assert created_suggestion.status_code == 201
    before = await detail(client)
    suggestions_before = await client.get(f"/api/species-suggestions?visit_id={VISIT_ID}")

    reopen_payload = {
        "notes": "Need another look at the evidence.",
        "expected_state_token": before["review_state_token"],
        "idempotency_key": "reopen-for-review",
        "review_origin": "human",
    }
    reopened = await client.post(f"/api/visits/{VISIT_ID}/reopen", json=reopen_payload)
    assert reopened.status_code == 200
    repeated = await client.post(f"/api/visits/{VISIT_ID}/reopen", json=reopen_payload)
    assert repeated.status_code == 200
    assert repeated.json()["idempotent"] is True

    after = await detail(client)
    assert after["visit"]["review_status"] == "needs_review"
    assert after["visit"]["reviewed_label"] is None
    assert after["detections"] == before["detections"]
    assert after["evidence_frames"] == before["evidence_frames"]
    suggestions_after = await client.get(f"/api/species-suggestions?visit_id={VISIT_ID}")
    assert suggestions_after.json() == suggestions_before.json()
    assert all(not entry["is_current"] for entry in after["correction_history"])
    assert after["correction_history"][0]["action"] == "Reopened for review"

    queue = await client.get("/api/review-queue")
    matching = [
        item
        for item in queue.json()
        if item["target_type"] == "visit" and item["target_id"] == VISIT_ID
    ]
    assert len(matching) == 1
    assert matching[0]["review_status"] == "needs_review"
