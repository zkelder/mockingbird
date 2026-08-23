from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest

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


PRIMARY_SOURCE_ID = "source-backyard-demo"
PRIMARY_STREAM_ID = "stream-backyard-feeder"
PRIMARY_ZONE_ID = "zone-feeder"
SECONDARY_SOURCE_ID = "source-library-secondary"
SECONDARY_STREAM_ID = "stream-library-secondary"
SECONDARY_ZONE_ID = "zone-library-secondary"

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


def add_secondary_stream(repository: ProductRepository) -> None:
    with repository.session_factory() as session:
        with session.begin():
            session.add(
                CameraSourceModel(
                    id=SECONDARY_SOURCE_ID,
                    name="Front yard camera",
                    kind="manual_upload",
                    status="connected",
                    description="Activity Library fixture source.",
                )
            )
            session.add(
                StreamModel(
                    id=SECONDARY_STREAM_ID,
                    source_id=SECONDARY_SOURCE_ID,
                    name="Front yard",
                    description="Activity Library fixture stream.",
                    is_live=False,
                )
            )
            session.add(
                ZoneModel(
                    id=SECONDARY_ZONE_ID,
                    stream_id=SECONDARY_STREAM_ID,
                    name="Driveway",
                    zone_type="driveway",
                    polygon_json="[]",
                    is_active=True,
                    monitoring_policy_json=None,
                )
            )


def add_visit(
    repository: ProductRepository,
    *,
    visit_id: str,
    event_id: str,
    started_at: datetime,
    stream_id: str = PRIMARY_STREAM_ID,
    source_id: str = PRIMARY_SOURCE_ID,
    zone_id: str = PRIMARY_ZONE_ID,
    is_superseded: bool = False,
    with_media: bool = True,
) -> None:
    media_id = f"media-{visit_id}"
    with repository.session_factory() as session:
        with session.begin():
            session.add(
                EventModel(
                    id=event_id,
                    stream_id=stream_id,
                    title=f"Activity fixture {visit_id}",
                    event_type="manual_media_import",
                    started_at=started_at,
                    ended_at=started_at + timedelta(seconds=8),
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
                    representative_media_path=(f"fixtures/{media_id}.jpg" if with_media else None),
                    zone_id=zone_id,
                    is_superseded=is_superseded,
                )
            )
            if with_media:
                session.add(
                    MediaAssetModel(
                        id=media_id,
                        source_id=source_id,
                        stream_id=stream_id,
                        filename=f"{media_id}.jpg",
                        content_type="image/jpeg",
                        media_type="image",
                        local_path=f"fixtures/{media_id}.jpg",
                        original_filename=f"{media_id}.jpg",
                        file_size_bytes=12,
                        created_at=started_at,
                        notes="Activity Library fixture evidence.",
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
        json={"review_origin": "human", "target_type": "visit", "target_id": visit_id, "label": label},
    )
    assert response.status_code == 201


async def test_activity_search_resolves_active_current_truth_and_evidence_only_suggestions(
    client: httpx.AsyncClient,
    isolated_repository: ProductRepository,
) -> None:
    add_secondary_stream(isolated_repository)
    start = datetime(2026, 7, 10, 12, tzinfo=UTC)
    add_visit(isolated_repository, visit_id="visit-old", event_id="event-old", started_at=start)
    add_visit(
        isolated_repository,
        visit_id="visit-new",
        event_id="event-new",
        started_at=start + timedelta(days=2),
        with_media=False,
    )
    add_visit(
        isolated_repository,
        visit_id="visit-front-yard",
        event_id="event-front-yard",
        started_at=start + timedelta(days=1),
        stream_id=SECONDARY_STREAM_ID,
        source_id=SECONDARY_SOURCE_ID,
        zone_id=SECONDARY_ZONE_ID,
    )
    add_visit(
        isolated_repository,
        visit_id="visit-superseded",
        event_id="event-superseded",
        started_at=start + timedelta(days=3),
        is_superseded=True,
    )
    await review_visit(client, "visit-old", "northern_cardinal")
    old_detail = (await client.get("/api/visits/visit-old/detail")).json()
    revised = await client.post(
        "/api/visits/visit-old/revision",
        json={"review_origin": "human", 
            "label": "blank",
            "expected_state_token": old_detail["review_state_token"],
            "idempotency_key": "activity-library-revise-old",
        },
    )
    assert revised.status_code == 200
    await review_visit(client, "visit-superseded", "northern_cardinal")
    suggestion = await client.post(
        "/api/species-suggestions",
        json={
            "visit_id": "visit-new",
            "stream_id": PRIMARY_STREAM_ID,
            "source_id": PRIMARY_SOURCE_ID,
            "adapter_id": "fixture",
            "adapter_name": "Fixture suggester",
            "suggested_label": "blue_jay",
        },
    )
    assert suggestion.status_code == 201

    default_search = await client.post("/api/activity-library/search", json={"page_size": 50})
    assert default_search.status_code == 200
    rows = default_search.json()["visits"]
    ids = [row["id"] for row in rows]
    # The default Library scope is all active product history, including the
    # seeded local sample records. The fixture rows remain newest-first.
    assert ids == [
        "visit-new",
        "visit-front-yard",
        "visit-old",
        "visit-squirrel-ground-001",
        "visit-bird-feeder-001",
    ]
    assert "visit-superseded" not in ids
    new_row = next(row for row in rows if row["id"] == "visit-new")
    assert new_row["has_suggestion"] is True
    assert new_row["reviewed_label"] is None
    assert new_row["primary_evidence"] is None

    blank_rows = await client.post(
        "/api/activity-library/search",
        json={"review_filter": "blank_false", "page_size": 50},
    )
    assert [row["id"] for row in blank_rows.json()["visits"]] == ["visit-old"]
    old_label_search = await client.post(
        "/api/activity-library/search",
        json={"confirmed_label": "northern_cardinal", "page_size": 50},
    )
    assert old_label_search.json()["visits"] == []
    suggestion_rows = await client.post(
        "/api/activity-library/search",
        json={"has_suggestion": True, "search": "blue_jay", "page_size": 50},
    )
    assert [row["id"] for row in suggestion_rows.json()["visits"]] == ["visit-new"]

    stream_zone_rows = await client.post(
        "/api/activity-library/search",
        json={
            "stream_id": SECONDARY_STREAM_ID,
            "source_id": SECONDARY_SOURCE_ID,
            "zone_id": SECONDARY_ZONE_ID,
            "page_size": 50,
        },
    )
    assert [row["id"] for row in stream_zone_rows.json()["visits"]] == ["visit-front-yard"]
    safe_preview_row = next(row for row in rows if row["id"] == "visit-front-yard")
    assert safe_preview_row["primary_evidence"]["preview_url"].startswith("/api/media/")
    assert "fixtures" not in safe_preview_row["primary_evidence"]["preview_url"]


async def test_activity_pagination_saved_views_fast_review_scope_and_export_selection(
    client: httpx.AsyncClient,
    isolated_repository: ProductRepository,
) -> None:
    start = datetime(2026, 7, 1, 9, tzinfo=UTC)
    for index in range(3):
        add_visit(
            isolated_repository,
            visit_id=f"visit-page-{index}",
            event_id=f"event-page-{index}",
            started_at=start + timedelta(days=index),
        )
    await review_visit(client, "visit-page-1", "northern_cardinal")
    with isolated_repository.session_factory() as session:
        with session.begin():
            session.get(VisitModel, "visit-page-2").is_superseded = True

    first_page = await client.post(
        "/api/activity-library/search",
        json={"page_size": 1, "start_at": "2026-07-01T00:00:00Z", "end_at": "2026-07-04T00:00:00Z"},
    )
    assert first_page.status_code == 200
    assert [row["id"] for row in first_page.json()["visits"]] == ["visit-page-1"]
    assert first_page.json()["has_more"] is True
    second_page = await client.post(
        "/api/activity-library/search",
        json={"page_size": 1, "offset": 1, "start_at": "2026-07-01T00:00:00Z", "end_at": "2026-07-04T00:00:00Z"},
    )
    assert [row["id"] for row in second_page.json()["visits"]] == ["visit-page-0"]

    invalid_saved_view = await client.post(
        "/api/activity-library/saved-views",
        json={"name": "Invalid", "filters": {"unknown_filter": True}},
    )
    assert invalid_saved_view.status_code == 422
    created_view = await client.post(
        "/api/activity-library/saved-views",
        json={"name": "Reviewed feeder", "filters": {"review_filter": "reviewed_observation"}},
    )
    assert created_view.status_code == 201
    saved_view_id = created_view.json()["id"]
    renamed_view = await client.patch(
        f"/api/activity-library/saved-views/{saved_view_id}",
        json={"name": "Cardinals"},
    )
    assert renamed_view.json()["name"] == "Cardinals"
    assert (await client.delete(f"/api/activity-library/saved-views/{saved_view_id}")).status_code == 204

    fast_review = await client.post(
        "/api/review-queue/fast/navigate",
        json={
            "ordered_targets": [{"target_type": "visit", "target_id": "visit-page-0"}],
            "direction": "next",
        },
    )
    assert fast_review.status_code == 200
    assert fast_review.json()["item"]["visit_id"] == "visit-page-0"
    assert fast_review.json()["unresolved_count"] == 1

    exported = await client.post(
        "/api/activity-library/export-selection",
        json={"name": "Selected reviewed", "visit_ids": ["visit-page-1", "visit-page-0", "visit-page-2"]},
    )
    assert exported.status_code == 200
    response = exported.json()
    assert response["included_visit_ids"] == ["visit-page-1"]
    assert {item["reason"] for item in response["excluded"]} == {"needs_review", "superseded"}
    assert [record["visit_id"] for record in response["export"]["manifest"]["records"]] == [
        "visit-page-1"
    ]


async def test_activity_search_confirmed_wildlife_includes_non_bird_wildlife(
    client: httpx.AsyncClient,
    isolated_repository: ProductRepository,
) -> None:
    """Everyday Discovery / Product Experience v2 (Phase K): the
    `confirmed_wildlife` review filter previously behaved as birds-only
    (`TaxonomyLabelModel.category == bird`), silently excluding a confirmed
    non-bird wildlife record despite wildlife-native product semantics. It
    must now match the same canonical `is_wildlife_category` boundary Bird
    Log/Today already use: confirmed squirrels/deer/etc. included, confirmed
    non-wildlife (blank/false-positive/person/vehicle) still excluded.
    """

    start = datetime(2026, 7, 10, 12, tzinfo=UTC)
    add_visit(isolated_repository, visit_id="visit-blank", event_id="event-blank", started_at=start)
    await review_visit(client, "visit-blank", "blank")
    add_visit(
        isolated_repository,
        visit_id="visit-confirmed-bird",
        event_id="event-confirmed-bird",
        started_at=start + timedelta(hours=1),
    )
    await review_visit(client, "visit-confirmed-bird", "northern_cardinal")

    wildlife_rows = await client.post(
        "/api/activity-library/search",
        json={"review_filter": "confirmed_wildlife", "page_size": 50},
    )
    assert wildlife_rows.status_code == 200
    wildlife_ids = {row["id"] for row in wildlife_rows.json()["visits"]}
    # A freshly-confirmed bird and the seeded confirmed non-bird wildlife
    # (squirrel) record must both be present.
    assert "visit-confirmed-bird" in wildlife_ids
    assert "visit-squirrel-ground-001" in wildlife_ids
    assert "visit-blank" not in wildlife_ids

    all_wildlife_are_actually_wildlife = await client.post(
        "/api/activity-library/search",
        json={"review_filter": "confirmed_wildlife", "page_size": 50},
    )
    for row in all_wildlife_are_actually_wildlife.json()["visits"]:
        assert row["reviewed_label"] not in {"blank", "false_positive", "person", "vehicle"}
