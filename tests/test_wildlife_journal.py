from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest
from sqlalchemy import select

from mockingbird.api.main import app, configure_repository
from mockingbird.repository.product_repository import ProductRepository
from mockingbird.storage.models import (
    CameraSourceModel,
    EventModel,
    MediaAssetModel,
    StreamModel,
    VisitCurationHistoryModel,
    VisitEvidenceLinkModel,
    VisitModel,
    VisitRelationshipModel,
    ZoneModel,
)


SOURCE_A = "source-journal-a"
SOURCE_B = "source-journal-b"
ARCHIVED_SOURCE = "source-journal-archived"
STREAM_A = "stream-journal-a"
STREAM_B = "stream-journal-b"
ARCHIVED_STREAM = "stream-journal-archived"
ZONE_A = "zone-journal-a"
ZONE_B = "zone-journal-b"
ARCHIVED_ZONE = "zone-journal-archived"

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


def add_graph(repository: ProductRepository) -> None:
    with repository.session_factory() as session:
        with session.begin():
            sample_source = session.get(CameraSourceModel, "source-backyard-demo")
            assert sample_source is not None
            sample_source.status = "archived"
            for source_id, name, status in [
                (SOURCE_A, "Garden camera", "connected"),
                (SOURCE_B, "Feeder camera", "connected"),
                (ARCHIVED_SOURCE, "Retired camera", "archived"),
            ]:
                session.add(
                    CameraSourceModel(
                        id=source_id,
                        name=name,
                        kind="manual_upload",
                        status=status,
                        description="Wildlife Journal fixture source.",
                    )
                )
            for stream_id, source_id, name in [
                (STREAM_A, SOURCE_A, "Garden stream"),
                (STREAM_B, SOURCE_B, "Feeder stream"),
                (ARCHIVED_STREAM, ARCHIVED_SOURCE, "Retired stream"),
            ]:
                session.add(
                    StreamModel(
                        id=stream_id,
                        source_id=source_id,
                        name=name,
                        description="Wildlife Journal fixture stream.",
                        is_live=False,
                    )
                )
            for zone_id, stream_id, name in [
                (ZONE_A, STREAM_A, "Garden edge"),
                (ZONE_B, STREAM_A, "Water dish"),
                (ARCHIVED_ZONE, ARCHIVED_STREAM, "Retired zone"),
            ]:
                session.add(
                    ZoneModel(
                        id=zone_id,
                        stream_id=stream_id,
                        name=name,
                        zone_type="feeder",
                        polygon_json="[]",
                        is_active=True,
                        monitoring_policy_json=None,
                    )
                )


def add_visit(
    repository: ProductRepository,
    *,
    visit_id: str,
    started_at: datetime,
    stream_id: str = STREAM_A,
    source_id: str = SOURCE_A,
    zone_id: str = ZONE_A,
    is_superseded: bool = False,
    with_media: bool = False,
) -> None:
    event_id = f"event-{visit_id}"
    with repository.session_factory() as session:
        with session.begin():
            session.add(
                EventModel(
                    id=event_id,
                    stream_id=stream_id,
                    title=f"Wildlife Journal fixture {visit_id}",
                    event_type="manual_media_import",
                    started_at=started_at,
                    ended_at=started_at + timedelta(seconds=7),
                    primary_zone_id=zone_id,
                    review_status="needs_review",
                )
            )
            session.add(
                VisitModel(
                    id=visit_id,
                    event_id=event_id,
                    subject_label="bird",
                    species_guess="unknown_bird",
                    confidence=None,
                    reviewed_label=None,
                    review_status="needs_review",
                    representative_media_path=(f"fixture/{visit_id}.jpg" if with_media else None),
                    zone_id=zone_id,
                    is_superseded=is_superseded,
                )
            )
            if with_media:
                media_id = f"media-{visit_id}"
                session.add(
                    MediaAssetModel(
                        id=media_id,
                        source_id=source_id,
                        stream_id=stream_id,
                        filename=f"{media_id}.jpg",
                        content_type="image/jpeg",
                        media_type="image",
                        local_path=f"fixture/{visit_id}.jpg",
                        original_filename=f"{media_id}.jpg",
                        file_size_bytes=12,
                        created_at=started_at,
                        notes="Wildlife Journal fixture evidence.",
                    )
                )
                session.add(
                    VisitEvidenceLinkModel(
                        id=f"link-{visit_id}",
                        visit_id=visit_id,
                        media_asset_id=media_id,
                        captured_at=started_at,
                        frame_sequence=0,
                        sort_order=0,
                        is_primary=True,
                        created_at=started_at,
                    )
                )


async def review(client: httpx.AsyncClient, visit_id: str, label: str) -> None:
    response = await client.post(
        "/api/review-labels",
        json={"review_origin": "human", "target_type": "visit", "target_id": visit_id, "label": label},
    )
    assert response.status_code == 201


async def token(client: httpx.AsyncClient, visit_id: str) -> str:
    response = await client.get(f"/api/visits/{visit_id}/detail")
    assert response.status_code == 200
    return response.json()["review_state_token"]


async def revise(client: httpx.AsyncClient, visit_id: str, label: str, key: str) -> None:
    response = await client.post(
        f"/api/visits/{visit_id}/revision",
        json={"review_origin": "human", 
            "label": label,
            "expected_state_token": await token(client, visit_id),
            "idempotency_key": key,
        },
    )
    assert response.status_code == 200


async def test_journal_resolves_current_reviewed_truth_and_combines_scope_filters(
    client: httpx.AsyncClient,
    isolated_repository: ProductRepository,
) -> None:
    add_graph(isolated_repository)
    add_visit(
        isolated_repository,
        visit_id="cardinal-first",
        started_at=datetime(2026, 7, 1, 12, tzinfo=UTC),
        with_media=True,
    )
    add_visit(
        isolated_repository,
        visit_id="revised-to-blue-jay",
        started_at=datetime(2026, 7, 2, 12, tzinfo=UTC),
        with_media=True,
    )
    add_visit(
        isolated_repository,
        visit_id="blank-to-blue-jay",
        started_at=datetime(2026, 7, 3, 12, tzinfo=UTC),
    )
    add_visit(
        isolated_repository,
        visit_id="cardinal-to-blank",
        started_at=datetime(2026, 7, 3, 14, tzinfo=UTC),
    )
    add_visit(
        isolated_repository,
        visit_id="reopened-blue-jay",
        started_at=datetime(2026, 7, 4, 12, tzinfo=UTC),
    )
    add_visit(
        isolated_repository,
        visit_id="moved-cardinal",
        started_at=datetime(2026, 7, 5, 12, tzinfo=UTC),
        with_media=True,
    )
    add_visit(
        isolated_repository,
        visit_id="latest-without-media",
        started_at=datetime(2026, 7, 6, 12, tzinfo=UTC),
    )
    add_visit(
        isolated_repository,
        visit_id="squirrel-reviewed",
        started_at=datetime(2026, 7, 5, 13, tzinfo=UTC),
    )
    add_visit(
        isolated_repository,
        visit_id="suggestion-only",
        started_at=datetime(2026, 7, 5, 14, tzinfo=UTC),
    )
    add_visit(
        isolated_repository,
        visit_id="superseded-cardinal",
        started_at=datetime(2026, 7, 5, 15, tzinfo=UTC),
        is_superseded=True,
    )
    add_visit(
        isolated_repository,
        visit_id="archived-cardinal",
        started_at=datetime(2026, 7, 5, 16, tzinfo=UTC),
        stream_id=ARCHIVED_STREAM,
        source_id=ARCHIVED_SOURCE,
        zone_id=ARCHIVED_ZONE,
    )

    for visit_id, label in [
        ("cardinal-first", "northern_cardinal"),
        ("revised-to-blue-jay", "northern_cardinal"),
        ("blank-to-blue-jay", "blank"),
        ("cardinal-to-blank", "northern_cardinal"),
        ("reopened-blue-jay", "blue_jay"),
        ("moved-cardinal", "northern_cardinal"),
        ("latest-without-media", "northern_cardinal"),
        ("squirrel-reviewed", "squirrel"),
        ("superseded-cardinal", "northern_cardinal"),
        ("archived-cardinal", "northern_cardinal"),
    ]:
        await review(client, visit_id, label)
    await revise(client, "revised-to-blue-jay", "blue_jay", "journal-revise-blue-jay")
    await revise(client, "blank-to-blue-jay", "blue_jay", "journal-blank-to-blue-jay")
    await revise(client, "cardinal-to-blank", "blank", "journal-cardinal-to-blank")
    reopened = await client.post(
        "/api/visits/reopened-blue-jay/reopen",
        json={
            "expected_state_token": await token(client, "reopened-blue-jay"),
            "idempotency_key": "journal-reopen",
            "review_origin": "human",
        },
    )
    assert reopened.status_code == 200
    moved = await client.post(
        "/api/visits/moved-cardinal/zone",
        json={
            "zone_id": ZONE_B,
            "expected_state_token": await token(client, "moved-cardinal"),
            "idempotency_key": "journal-move-zone",
        },
    )
    assert moved.status_code == 200
    suggestion = await client.post(
        "/api/species-suggestions",
        json={
            "visit_id": "suggestion-only",
            "stream_id": STREAM_A,
            "source_id": SOURCE_A,
            "adapter_id": "fixture",
            "adapter_name": "Fixture suggestion",
            "suggested_label": "blue_jay",
        },
    )
    assert suggestion.status_code == 201

    overview = await client.get("/api/bird-log/journal?order=alphabetical")
    assert overview.status_code == 200
    labels = overview.json()["labels"]
    assert [(row["label"], row["observation_count"]) for row in labels] == [
        ("blue_jay", 2),
        ("northern_cardinal", 3),
    ]
    cardinal = next(row for row in labels if row["label"] == "northern_cardinal")
    assert cardinal["representative"]["visit_id"] == "moved-cardinal"
    assert cardinal["representative"]["primary_evidence"]["preview_url"] == (
        "/api/media/media-moved-cardinal/file"
    )

    history = await client.get(
        "/api/bird-log/journal/northern_cardinal?"
        "preset=custom&start_date=2026-07-01&end_date=2026-07-06&"
        "stream_id=stream-journal-a&zone_id=zone-journal-b"
    )
    assert history.status_code == 200
    payload = history.json()
    assert payload["observation_count"] == 1
    assert [row["visit_id"] for row in payload["gallery"]["observations"]] == ["moved-cardinal"]
    observation = payload["gallery"]["observations"][0]
    assert observation["zone_id"] == ZONE_B
    assert observation["has_curation_history"] is True
    assert observation["is_first_in_zone"] is True
    assert observation["primary_evidence"]["preview_url"].startswith("/api/media/")
    assert "fixture" not in str(observation)
    assert payload["activity_library_drilldown"] == {
        "review_filter": "confirmed_wildlife",
        "confirmed_label": "northern_cardinal",
        "start_date": "2026-07-01",
        "end_date": "2026-07-06",
        "stream_id": STREAM_A,
        "zone_id": ZONE_B,
    }

    library = await client.post(
        "/api/activity-library/search",
        json={
            "review_filter": "confirmed_wildlife",
            "confirmed_label": "northern_cardinal",
            "zone_id": ZONE_B,
            "start_at": "2026-07-01T00:00:00Z",
            "end_at": "2026-07-06T23:59:59Z",
            "page_size": 24,
        },
    )
    assert library.status_code == 200
    assert [row["id"] for row in library.json()["visits"]] == ["moved-cardinal"]


async def test_journal_lineage_pagination_and_deterministic_ordering(
    client: httpx.AsyncClient,
    isolated_repository: ProductRepository,
) -> None:
    add_graph(isolated_repository)
    base = datetime(2026, 7, 1, 12, tzinfo=UTC)
    for index in range(5):
        add_visit(
            isolated_repository,
            visit_id=f"page-cardinal-{index}",
            started_at=base + timedelta(days=index),
            with_media=index == 0,
        )
        await review(client, f"page-cardinal-{index}", "northern_cardinal")
    add_visit(
        isolated_repository,
        visit_id="split-source",
        started_at=base + timedelta(days=5),
        is_superseded=True,
    )
    add_visit(
        isolated_repository,
        visit_id="split-result",
        started_at=base + timedelta(days=5),
    )
    add_visit(
        isolated_repository,
        visit_id="merge-left",
        started_at=base + timedelta(days=6),
        is_superseded=True,
    )
    add_visit(
        isolated_repository,
        visit_id="merge-right",
        started_at=base + timedelta(days=6, seconds=1),
        is_superseded=True,
    )
    add_visit(
        isolated_repository,
        visit_id="merge-result",
        started_at=base + timedelta(days=6, seconds=2),
    )
    for visit_id in ["split-source", "split-result", "merge-left", "merge-right", "merge-result"]:
        await review(client, visit_id, "blue_jay")
    with isolated_repository.session_factory() as session:
        with session.begin():
            session.add_all(
                [
                    VisitRelationshipModel(
                        id="relationship-split",
                        source_visit_id="split-source",
                        result_visit_id="split-result",
                        relationship_type="split",
                        created_at=base,
                    ),
                    VisitRelationshipModel(
                        id="relationship-merge-left",
                        source_visit_id="merge-left",
                        result_visit_id="merge-result",
                        relationship_type="merge",
                        created_at=base,
                    ),
                    VisitRelationshipModel(
                        id="relationship-merge-right",
                        source_visit_id="merge-right",
                        result_visit_id="merge-result",
                        relationship_type="merge",
                        created_at=base,
                    ),
                ]
            )
            session.add(
                VisitCurationHistoryModel(
                    id="curation-page-0",
                    visit_id="page-cardinal-0",
                    action="Evidence curated",
                    prior_zone_id=None,
                    result_visit_ids_json=None,
                    details_json=None,
                    idempotency_key="journal-curation-page-0",
                    created_at=base,
                )
            )

    first_page = await client.get(
        "/api/bird-log/journal/northern_cardinal?page_size=2&offset=0&gallery_order=newest"
    )
    assert first_page.status_code == 200
    first = first_page.json()
    assert first["observation_count"] == 5
    assert [row["visit_id"] for row in first["gallery"]["observations"]] == [
        "page-cardinal-4",
        "page-cardinal-3",
    ]
    assert first["gallery"]["has_more"] is True
    assert first["gallery"]["next_offset"] == 2
    second_page = await client.get(
        "/api/bird-log/journal/northern_cardinal?page_size=2&offset=2&gallery_order=newest"
    )
    assert [row["visit_id"] for row in second_page.json()["gallery"]["observations"]] == [
        "page-cardinal-2",
        "page-cardinal-1",
    ]
    oldest = await client.get(
        "/api/bird-log/journal/northern_cardinal?page_size=2&gallery_order=oldest"
    )
    assert [row["visit_id"] for row in oldest.json()["gallery"]["observations"]] == [
        "page-cardinal-0",
        "page-cardinal-1",
    ]
    blue_jay = await client.get("/api/bird-log/journal/blue_jay")
    assert blue_jay.status_code == 200
    assert blue_jay.json()["observation_count"] == 2
    assert {row["visit_id"] for row in blue_jay.json()["gallery"]["observations"]} == {
        "split-result",
        "merge-result",
    }
    ordered = await client.get("/api/bird-log/journal?order=most_observed")
    assert [(row["label"], row["observation_count"]) for row in ordered.json()["labels"]] == [
        ("northern_cardinal", 5),
        ("blue_jay", 2),
    ]


async def test_journal_handles_empty_valid_and_malformed_labels_safely(
    client: httpx.AsyncClient,
    isolated_repository: ProductRepository,
) -> None:
    with isolated_repository.session_factory() as session:
        with session.begin():
            for source in session.scalars(select(CameraSourceModel)).all():
                source.status = "archived"

    overview = await client.get("/api/bird-log/journal")
    assert overview.status_code == 200
    assert overview.json()["labels"] == []
    valid_empty = await client.get("/api/bird-log/journal/northern_cardinal")
    assert valid_empty.status_code == 200
    assert valid_empty.json()["observation_count"] == 0
    assert valid_empty.json()["gallery"]["observations"] == []
    malformed = await client.get("/api/bird-log/journal/not-a-taxonomy-label")
    assert malformed.status_code == 404
    invalid_range = await client.get("/api/bird-log/journal/northern_cardinal?preset=custom")
    assert invalid_range.status_code == 422
