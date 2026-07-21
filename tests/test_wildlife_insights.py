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
    VisitEvidenceLinkModel,
    VisitModel,
    ZoneModel,
)


SOURCE_A = "source-insights-a"
SOURCE_B = "source-insights-b"
ARCHIVED_SOURCE = "source-insights-archived"
STREAM_A = "stream-insights-a"
STREAM_B = "stream-insights-b"
ARCHIVED_STREAM = "stream-insights-archived"
ZONE_A = "zone-insights-a"
ZONE_B = "zone-insights-b"
ARCHIVED_ZONE = "zone-insights-archived"

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


def add_insights_graph(repository: ProductRepository) -> None:
    """Keep fixture history isolated from the seeded walkthrough and its source."""

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
                        description="Wildlife Insights fixture source.",
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
                        description="Wildlife Insights fixture stream.",
                        is_live=False,
                    )
                )
            for zone_id, stream_id, name in [
                (ZONE_A, STREAM_A, "Garden edge"),
                (ZONE_B, STREAM_B, "Feeder"),
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
    with_evidence: bool = False,
) -> None:
    event_id = f"event-{visit_id}"
    with repository.session_factory() as session:
        with session.begin():
            session.add(
                EventModel(
                    id=event_id,
                    stream_id=stream_id,
                    title=f"Wildlife Insights fixture {visit_id}",
                    event_type="manual_media_import",
                    started_at=started_at,
                    ended_at=started_at + timedelta(seconds=5),
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
                    representative_media_path=(f"fixture/{visit_id}.jpg" if with_evidence else None),
                    zone_id=zone_id,
                    is_superseded=is_superseded,
                )
            )
            if with_evidence:
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
                        notes="Wildlife Insights fixture evidence.",
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


async def review_visit(client: httpx.AsyncClient, visit_id: str, label: str) -> None:
    response = await client.post(
        "/api/review-labels",
        json={"target_type": "visit", "target_id": visit_id, "label": label},
    )
    assert response.status_code == 201


async def review_state_token(client: httpx.AsyncClient, visit_id: str) -> str:
    response = await client.get(f"/api/visits/{visit_id}/detail")
    assert response.status_code == 200
    return response.json()["review_state_token"]


async def test_wildlife_insights_aggregate_only_current_active_reviewed_truth(
    client: httpx.AsyncClient,
    isolated_repository: ProductRepository,
) -> None:
    add_insights_graph(isolated_repository)
    previous_day = datetime(2026, 6, 30, 12, tzinfo=UTC)
    add_visit(isolated_repository, visit_id="previous-cardinal", started_at=previous_day)
    add_visit(
        isolated_repository,
        visit_id="garden-cardinal",
        started_at=datetime(2026, 7, 1, 9, tzinfo=UTC),
        with_evidence=True,
    )
    add_visit(
        isolated_repository,
        visit_id="revised-blue-jay",
        started_at=datetime(2026, 7, 2, 14, tzinfo=UTC),
        stream_id=STREAM_B,
        source_id=SOURCE_B,
        zone_id=ZONE_B,
        with_evidence=True,
    )
    add_visit(
        isolated_repository,
        visit_id="cardinal-no-thumbnail",
        started_at=datetime(2026, 7, 2, 18, tzinfo=UTC),
    )
    add_visit(
        isolated_repository,
        visit_id="squirrel-activity",
        started_at=datetime(2026, 7, 3, 10, tzinfo=UTC),
    )
    add_visit(
        isolated_repository,
        visit_id="unreviewed",
        started_at=datetime(2026, 7, 4, 8, tzinfo=UTC),
    )
    add_visit(
        isolated_repository,
        visit_id="suggestion-only",
        started_at=datetime(2026, 7, 5, 9, tzinfo=UTC),
    )
    add_visit(
        isolated_repository,
        visit_id="reopened",
        started_at=datetime(2026, 7, 6, 9, tzinfo=UTC),
        stream_id=STREAM_B,
        source_id=SOURCE_B,
        zone_id=ZONE_B,
    )
    add_visit(
        isolated_repository,
        visit_id="superseded-cardinal",
        started_at=datetime(2026, 7, 2, 10, tzinfo=UTC),
        is_superseded=True,
    )
    add_visit(
        isolated_repository,
        visit_id="archived-cardinal",
        started_at=datetime(2026, 7, 3, 11, tzinfo=UTC),
        stream_id=ARCHIVED_STREAM,
        source_id=ARCHIVED_SOURCE,
        zone_id=ARCHIVED_ZONE,
    )
    add_visit(
        isolated_repository,
        visit_id="range-end-excluded",
        started_at=datetime(2026, 7, 8, 12, tzinfo=UTC),
    )

    for visit_id, label in [
        ("previous-cardinal", "northern_cardinal"),
        ("garden-cardinal", "northern_cardinal"),
        ("revised-blue-jay", "northern_cardinal"),
        ("cardinal-no-thumbnail", "northern_cardinal"),
        ("squirrel-activity", "squirrel"),
        ("reopened", "blue_jay"),
        ("superseded-cardinal", "northern_cardinal"),
        ("archived-cardinal", "northern_cardinal"),
        ("range-end-excluded", "northern_cardinal"),
    ]:
        await review_visit(client, visit_id, label)

    revised = await client.post(
        "/api/visits/revised-blue-jay/revision",
        json={
            "label": "blue_jay",
            "expected_state_token": await review_state_token(client, "revised-blue-jay"),
            "idempotency_key": "insights-revise-blue-jay",
        },
    )
    assert revised.status_code == 200
    reopened = await client.post(
        "/api/visits/reopened/reopen",
        json={
            "expected_state_token": await review_state_token(client, "reopened"),
            "idempotency_key": "insights-reopen",
        },
    )
    assert reopened.status_code == 200
    suggestion = await client.post(
        "/api/species-suggestions",
        json={
            "visit_id": "suggestion-only",
            "stream_id": STREAM_A,
            "source_id": SOURCE_A,
            "adapter_id": "fixture",
            "adapter_name": "Fixture suggester",
            "suggested_label": "blue_jay",
        },
    )
    assert suggestion.status_code == 201

    response = await client.post(
        "/api/analytics/wildlife-insights",
        json={"preset": "custom", "start_date": "2026-07-01", "end_date": "2026-07-07"},
    )
    assert response.status_code == 200
    summary = response.json()

    assert summary["period"] == {
        "preset": "custom",
        "start_date": "2026-07-01",
        "end_date": "2026-07-07",
        "previous_start_date": "2026-06-24",
        "previous_end_date": "2026-06-30",
        "timezone_name": summary["period"]["timezone_name"],
    }
    assert summary["headline"]["active_stream_count"] == 2
    assert summary["headline"]["active_visit_count"] == 7
    assert summary["headline"]["reviewed_wildlife_observation_count"] == 3
    assert summary["headline"]["unique_confirmed_label_count"] == 2
    assert summary["headline"]["unresolved_visit_count"] == 3
    assert summary["headline"]["reviewed_non_bird_activity_count"] == 1
    # Hour buckets intentionally use the host's local display time, not UTC.
    assert summary["headline"]["peak_activity_hour"] == 5
    assert summary["headline"]["first_observation"]["visit_id"] == "garden-cardinal"
    assert summary["headline"]["first_observation"]["primary_evidence"]["media_asset_id"] == (
        "media-garden-cardinal"
    )
    assert summary["headline"]["latest_observation"]["visit_id"] == "cardinal-no-thumbnail"
    assert summary["headline"]["latest_observation"]["primary_evidence"] is None

    assert summary["comparison"] == {
        "previous_reviewed_wildlife_observation_count": 1,
        "reviewed_wildlife_observation_change": 2,
        "new_labels": ["Blue Jay"],
        "labels_not_seen": [],
    }
    assert [(row["name"], row["count"], row["previous_count"]) for row in summary["leading_labels"]] == [
        ("Northern Cardinal", 2, 1),
        ("Blue Jay", 1, 0),
    ]
    assert [(row["local_date"], row["count"]) for row in summary["daily_trend"]] == [
        ("2026-07-01", 1),
        ("2026-07-02", 2),
        ("2026-07-03", 0),
        ("2026-07-04", 0),
        ("2026-07-05", 0),
        ("2026-07-06", 0),
        ("2026-07-07", 0),
    ]
    assert summary["activity_by_hour"][14] == {"hour": 14, "count": 1}
    assert [(row["id"], row["count"]) for row in summary["stream_breakdown"]] == [
        (STREAM_A, 2),
        (STREAM_B, 1),
    ]
    assert [(row["id"], row["count"]) for row in summary["zone_breakdown"]] == [
        (ZONE_A, 2),
        (ZONE_B, 1),
    ]
    assert summary["review_context"] == {
        "blank_or_false_count": 0,
        "ambiguous_or_unknown_count": 0,
        "rejected_count": 0,
        "unclassified_reviewed_count": 0,
        "pending_suggestion_evidence_count": 1,
    }
    assert summary["confirmed_activity_drilldown"] == {
        "review_filter": "confirmed_wildlife",
        "start_date": "2026-07-01",
        "end_date": "2026-07-07",
        "stream_id": None,
        "zone_id": None,
        "confirmed_label": None,
    }
    assert summary["unresolved_activity_drilldown"]["review_filter"] == "needs_review"
    assert "visits" not in summary

    confirmed_garden = await client.post(
        "/api/activity-library/search",
        json={
            "review_filter": "confirmed_wildlife",
            "source_id": SOURCE_A,
            "start_at": "2026-07-01T00:00:00Z",
            "end_at": "2026-07-07T23:59:59Z",
            "page_size": 20,
        },
    )
    assert confirmed_garden.status_code == 200
    assert [visit["id"] for visit in confirmed_garden.json()["visits"]] == [
        "cardinal-no-thumbnail",
        "garden-cardinal",
    ]


async def test_wildlife_insights_validate_ranges_and_return_an_empty_active_state(
    client: httpx.AsyncClient,
    isolated_repository: ProductRepository,
) -> None:
    invalid = await client.post(
        "/api/analytics/wildlife-insights",
        json={"preset": "custom", "start_date": "2026-07-02", "end_date": "2026-07-01"},
    )
    assert invalid.status_code == 422

    with isolated_repository.session_factory() as session:
        with session.begin():
            for source in session.scalars(select(CameraSourceModel)).all():
                source.status = "archived"

    empty = await client.post(
        "/api/analytics/wildlife-insights",
        json={"preset": "today"},
    )
    assert empty.status_code == 200
    assert empty.json()["headline"] == {
        "active_stream_count": 0,
        "active_visit_count": 0,
        "reviewed_wildlife_observation_count": 0,
        "unique_confirmed_label_count": 0,
        "unresolved_visit_count": 0,
        "reviewed_non_bird_activity_count": 0,
        "busiest_stream": None,
        "busiest_zone": None,
        "peak_activity_hour": None,
        "first_observation": None,
        "latest_observation": None,
    }
