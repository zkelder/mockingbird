from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
from sqlalchemy import func, select

from mockingbird.api.main import app, configure_repository
from mockingbird.repository.product_repository import ProductRepository
from mockingbird.storage.models import (
    CameraSourceModel,
    EventModel,
    ReviewLabelModel,
    StreamModel,
    VisitModel,
    ZoneModel,
)
from tests.conftest import LegacyAuthenticatedTestClient, de_demo_seeded_source


STREAM_ID = "stream-backyard-feeder"
SOURCE_ID = "source-backyard-demo"
ZONE_ID = "zone-feeder"

pytestmark = pytest.mark.anyio


@pytest.fixture(autouse=True)
def isolated_repository(tmp_path: Path) -> ProductRepository:
    repository = ProductRepository(
        db_url=f"sqlite:///{tmp_path / 'mockingbird.sqlite3'}",
        media_root=tmp_path / "media",
    )
    de_demo_seeded_source(repository)
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
    stream_id: str = STREAM_ID,
    zone_id: str | None = ZONE_ID,
    species_guess: str = "unknown_bird",
) -> None:
    with repository.session_factory() as session:
        with session.begin():
            session.add(
                EventModel(
                    id=event_id,
                    stream_id=stream_id,
                    title=f"Fast Review {event_id}",
                    event_type="fast_review_fixture",
                    started_at=datetime.now(UTC),
                    ended_at=datetime.now(UTC),
                    primary_zone_id=zone_id,
                    review_status="needs_review",
                )
            )
            session.add(
                VisitModel(
                    id=visit_id,
                    event_id=event_id,
                    subject_label="bird",
                    species_guess=species_guess,
                    confidence=None,
                    reviewed_label=None,
                    review_status="needs_review",
                    representative_media_path=None,
                )
            )


def add_second_stream(repository: ProductRepository) -> str:
    stream_id = "stream-fast-review-other"
    with repository.session_factory() as session:
        with session.begin():
            session.add(
                StreamModel(
                    id=stream_id,
                    source_id=SOURCE_ID,
                    name="Other review stream",
                    description="Fast Review scope fixture.",
                    is_live=False,
                )
            )
            session.add(
                ZoneModel(
                    id="zone-fast-review-other",
                    stream_id=stream_id,
                    name="Other feeder",
                    zone_type="feeder",
                    polygon_json="[]",
                    is_active=True,
                )
            )
    return stream_id


def add_real_stream(repository: ProductRepository) -> tuple[str, str]:
    """A Stream on a real (non-demo) Source, distinct from `add_second_
    stream`'s `stream-fast-review-other` (still on the seeded demo Source).
    Pre-Release Trust & Correctness Correction v1 (UI-01): needed by the one
    test that checks Dashboard visibility -- the demo Source's activity is
    now correctly excluded from Dashboard/Bird Log, like every other real-
    history surface (see `_real_source_condition` in product_repository.py)."""

    source_id = "source-fast-review-real"
    stream_id = "stream-fast-review-real"
    zone_id = "zone-fast-review-real"
    with repository.session_factory() as session:
        with session.begin():
            session.add(
                CameraSourceModel(
                    id=source_id, name="Fast Review real fixture camera",
                    kind="manual_upload", status="connected", description="Fast Review real-visibility fixture.",
                )
            )
            session.add(
                StreamModel(
                    id=stream_id, source_id=source_id, name="Fast Review real fixture stream",
                    description="Fast Review real-visibility fixture.", is_live=False,
                )
            )
            session.add(
                ZoneModel(
                    id=zone_id, stream_id=stream_id, name="Feeder", zone_type="feeder",
                    polygon_json="[]", is_active=True,
                )
            )
    return stream_id, zone_id


async def queue_item(client: httpx.AsyncClient, visit_id: str) -> dict:
    response = await client.get("/api/review-queue")
    assert response.status_code == 200
    return next(item for item in response.json() if item["target_type"] == "visit" and item["target_id"] == visit_id)


async def fast_save(
    client: httpx.AsyncClient,
    *,
    item: dict,
    label: str,
    session_id: str,
    idempotency_key: str,
) -> httpx.Response:
    return await client.post(
        "/api/review-queue/fast/correct",
        json={"review_origin": "human", 
            "target_type": "visit",
            "target_id": item["target_id"],
            "label": label,
            "review_session_id": session_id,
            "idempotency_key": idempotency_key,
            "expected_state_token": item["review_state_token"],
        },
    )


def active_review_label_count(repository: ProductRepository) -> int:
    with repository.session_factory() as session:
        return len(repository._effective_review_label_models(list(session.scalars(select(ReviewLabelModel)).all())))


def raw_review_label_count(repository: ProductRepository) -> int:
    with repository.session_factory() as session:
        return int(session.scalar(select(func.count()).select_from(ReviewLabelModel)) or 0)


async def test_fast_navigation_stays_in_stream_filter_skips_reviewed_and_ends_cleanly(
    client: httpx.AsyncClient,
    isolated_repository: ProductRepository,
) -> None:
    add_reviewable_visit(
        isolated_repository,
        event_id="event-fast-first",
        visit_id="visit-fast-first",
    )
    add_reviewable_visit(
        isolated_repository,
        event_id="event-fast-reviewed",
        visit_id="visit-fast-reviewed",
    )
    add_reviewable_visit(
        isolated_repository,
        event_id="event-fast-second",
        visit_id="visit-fast-second",
    )
    other_stream = add_second_stream(isolated_repository)
    add_reviewable_visit(
        isolated_repository,
        event_id="event-fast-other",
        visit_id="visit-fast-other",
        stream_id=other_stream,
        zone_id="zone-fast-review-other",
    )

    reviewed = await queue_item(client, "visit-fast-reviewed")
    reviewed_response = await fast_save(
        client,
        item=reviewed,
        label="squirrel",
        session_id="session-reviewed",
        idempotency_key="save-reviewed",
    )
    assert reviewed_response.status_code == 200

    first = await queue_item(client, "visit-fast-first")
    second = await queue_item(client, "visit-fast-second")
    first_response = await fast_save(
        client,
        item=first,
        label="northern_cardinal",
        session_id="session-navigation",
        idempotency_key="save-first",
    )
    assert first_response.status_code == 200
    navigation_payload = {
        "ordered_targets": [
            {"target_type": "visit", "target_id": "visit-fast-first"},
            {"target_type": "visit", "target_id": "visit-fast-reviewed"},
            {"target_type": "visit", "target_id": "visit-fast-other"},
            {"target_type": "visit", "target_id": "visit-fast-second"},
        ],
        "current_target": {"target_type": "visit", "target_id": first["target_id"]},
        "direction": "next",
        "stream_id": STREAM_ID,
    }
    next_response = await client.post("/api/review-queue/fast/navigate", json=navigation_payload)
    assert next_response.status_code == 200
    assert next_response.json()["item"]["target_id"] == second["target_id"]

    second_response = await fast_save(
        client,
        item=second,
        label="blue_jay",
        session_id="session-navigation",
        idempotency_key="save-second",
    )
    assert second_response.status_code == 200

    final_payload = {
        **navigation_payload,
        "current_target": {"target_type": "visit", "target_id": second["target_id"]},
    }
    final_response = await client.post("/api/review-queue/fast/navigate", json=final_payload)
    assert final_response.status_code == 200
    assert final_response.json()["item"] is None
    assert final_response.json()["message"] == "No unresolved Visit remains in this filtered queue."


async def test_fast_save_is_explicit_idempotent_and_updates_reviewed_exports(
    client: httpx.AsyncClient,
    isolated_repository: ProductRepository,
) -> None:
    item = await queue_item(client, "visit-bird-feeder-001")
    payload = {
        "target_type": "visit",
        "target_id": item["target_id"],
        "label": "northern_cardinal",
        "notes": "Fast Review explicit confirmation.",
        "review_session_id": "session-save",
        "idempotency_key": "fast-save-idempotency",
        "expected_state_token": item["review_state_token"],
        "review_origin": "human",
    }

    before = active_review_label_count(isolated_repository)
    saved = await client.post("/api/review-queue/fast/correct", json=payload)
    assert saved.status_code == 200
    assert saved.json()["idempotent"] is False
    assert active_review_label_count(isolated_repository) == before + 1

    repeated = await client.post("/api/review-queue/fast/correct", json=payload)
    assert repeated.status_code == 200
    assert repeated.json()["idempotent"] is True
    assert active_review_label_count(isolated_repository) == before + 1

    analytics = (await client.get("/api/analytics/summary")).json()
    assert analytics["species_counts"]["northern_cardinal"] == 1
    export = await client.post(
        "/api/dataset-exports",
        json={"name": "Fast Review export", "reviewed_only": True},
    )
    assert export.status_code == 201
    assert any(
        record["visit_id"] == "visit-bird-feeder-001"
        and record["label"] == "northern_cardinal"
        and record["reviewed"] is True
        for record in export.json()["manifest"]["records"]
    )


async def test_fast_undo_restores_prior_state_and_is_idempotent(
    client: httpx.AsyncClient,
    isolated_repository: ProductRepository,
) -> None:
    item = await queue_item(client, "visit-bird-feeder-001")
    saved = await fast_save(
        client,
        item=item,
        label="blue_jay",
        session_id="session-undo",
        idempotency_key="save-undo",
    )
    assert saved.status_code == 200
    body = saved.json()
    undo_payload = {
        "review_label_id": body["result"]["review_label"]["id"],
        "review_session_id": "session-undo",
        "idempotency_key": "undo-idempotency",
        "expected_state_token": body["undo_state_token"],
    }

    undone = await client.post("/api/review-queue/fast/undo", json=undo_payload)
    assert undone.status_code == 200
    assert undone.json()["idempotent"] is False
    visit = (await client.get("/api/visits/visit-bird-feeder-001")).json()
    assert visit["review_status"] == "needs_review"
    assert visit["reviewed_label"] is None
    assert active_review_label_count(isolated_repository) == 1
    assert raw_review_label_count(isolated_repository) == 3

    repeated = await client.post("/api/review-queue/fast/undo", json=undo_payload)
    assert repeated.status_code == 200
    assert repeated.json()["idempotent"] is True
    assert raw_review_label_count(isolated_repository) == 3
    assert (await queue_item(client, "visit-bird-feeder-001"))["review_status"] == "needs_review"


async def test_fast_undo_rejects_a_correction_replaced_elsewhere(
    client: httpx.AsyncClient,
) -> None:
    item = await queue_item(client, "visit-bird-feeder-001")
    saved = await fast_save(
        client,
        item=item,
        label="blue_jay",
        session_id="session-replaced",
        idempotency_key="save-replaced",
    )
    assert saved.status_code == 200
    body = saved.json()
    replacement = await client.post(
        "/api/review-labels",
        json={"review_origin": "human", 
            "target_type": "visit",
            "target_id": "visit-bird-feeder-001",
            "label": "northern_cardinal",
        },
    )
    assert replacement.status_code == 201

    undo = await client.post(
        "/api/review-queue/fast/undo",
        json={
            "review_label_id": body["result"]["review_label"]["id"],
            "review_session_id": "session-replaced",
            "idempotency_key": "undo-replaced",
            "expected_state_token": body["undo_state_token"],
        },
    )
    assert undo.status_code == 409
    assert (await client.get("/api/visits/visit-bird-feeder-001")).json()["reviewed_label"] == "northern_cardinal"


async def test_fast_outcomes_and_navigation_never_accept_suggestions_automatically(
    client: httpx.AsyncClient,
    isolated_repository: ProductRepository,
) -> None:
    real_stream_id, real_zone_id = add_real_stream(isolated_repository)
    add_reviewable_visit(
        isolated_repository,
        event_id="event-fast-blank",
        visit_id="visit-fast-blank",
        stream_id=real_stream_id,
        zone_id=real_zone_id,
    )
    add_reviewable_visit(
        isolated_repository,
        event_id="event-fast-non-bird",
        visit_id="visit-fast-non-bird",
        stream_id=real_stream_id,
        zone_id=real_zone_id,
    )
    add_reviewable_visit(
        isolated_repository,
        event_id="event-fast-ambiguous",
        visit_id="visit-fast-ambiguous",
        stream_id=real_stream_id,
        zone_id=real_zone_id,
    )
    before = active_review_label_count(isolated_repository)
    blank = await queue_item(client, "visit-fast-blank")
    navigate = await client.post(
        "/api/review-queue/fast/navigate",
        json={
            "ordered_targets": [{"target_type": "visit", "target_id": blank["target_id"]}],
            "direction": "next",
            "stream_id": real_stream_id,
        },
    )
    assert navigate.status_code == 200
    assert navigate.json()["item"]["suggested_label"] == "unknown_bird"
    assert active_review_label_count(isolated_repository) == before

    for visit_id, label in (
        ("visit-fast-blank", "blank"),
        ("visit-fast-non-bird", "non_bird"),
        ("visit-fast-ambiguous", "ambiguous"),
    ):
        saved = await fast_save(
            client,
            item=await queue_item(client, visit_id),
            label=label,
            session_id="session-outcomes",
            idempotency_key="save-" + visit_id,
        )
        assert saved.status_code == 200

    dashboard = (await client.get("/api/dashboard/summary")).json()
    confirmed_bird_labels = {
        observation["label"] for observation in dashboard["today_observations"]
    }
    assert "blank" not in confirmed_bird_labels
    assert "ambiguous" not in confirmed_bird_labels
    assert "non_bird" not in confirmed_bird_labels
    assert any(
        observation["label"] == "non_bird"
        for observation in dashboard["reviewed_non_bird_activity"]
    )
