from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest
from sqlalchemy import func, inspect, select

from mockingbird.api.main import app, configure_repository
from mockingbird.repository.product_repository import ProductRepository
from mockingbird.storage.database import CURRENT_DATABASE_SCHEMA_VERSION
from mockingbird.storage.models import (
    CameraSourceModel,
    EventModel,
    ReviewLabelModel,
    StreamModel,
    VisitModel,
    VisitTagMembershipModel,
    VisitTagModel,
    ZoneModel,
)
from tests.conftest import de_demo_seeded_source, LegacyAuthenticatedTestClient


VISIT_ID = "visit-bird-feeder-001"
SECOND_VISIT_ID = "visit-squirrel-ground-001"
# Pre-Release Trust & Correctness Correction v1 (UI-01): a real, non-demo
# fixture for the one test below that needs its Visit actually visible in
# Bird Log -- VISIT_ID/SECOND_VISIT_ID are the seeded *demo* Source's
# Visits, now correctly excluded from Bird Log like every other real-history
# surface (see `_real_source_condition` in product_repository.py).
REAL_SOURCE_ID = "source-visit-tags-real"
REAL_STREAM_ID = "stream-visit-tags-real"
REAL_ZONE_ID = "zone-visit-tags-real"
REAL_VISIT_ID = "visit-tags-real"

pytestmark = pytest.mark.anyio


def add_real_visit(repository: ProductRepository) -> None:
    """A Visit on a real (non-demo) Source, for a test that needs actual
    Bird Log visibility rather than just tag CRUD against any Visit id."""

    started_at = datetime(2026, 6, 1, 15, 0, tzinfo=UTC)
    with repository.session_factory() as session:
        with session.begin():
            session.add(
                CameraSourceModel(
                    id=REAL_SOURCE_ID, name="Visit tags fixture camera",
                    kind="manual_upload", status="connected", description="Visit tags test fixture source.",
                )
            )
            session.add(
                StreamModel(
                    id=REAL_STREAM_ID, source_id=REAL_SOURCE_ID, name="Visit tags fixture stream",
                    description="Visit tags test fixture stream.", is_live=False,
                )
            )
            session.add(
                ZoneModel(
                    id=REAL_ZONE_ID, stream_id=REAL_STREAM_ID, name="Feeder", zone_type="feeder",
                    polygon_json="[]", is_active=True, monitoring_policy_json=None,
                )
            )
            session.add(
                EventModel(
                    id=f"event-{REAL_VISIT_ID}", stream_id=REAL_STREAM_ID,
                    title="Visit tags fixture event", event_type="observation_engine_candidate",
                    started_at=started_at, ended_at=started_at + timedelta(seconds=5),
                    primary_zone_id=REAL_ZONE_ID, review_status="needs_review",
                )
            )
            session.add(
                VisitModel(
                    id=REAL_VISIT_ID, event_id=f"event-{REAL_VISIT_ID}", subject_label="bird",
                    species_guess=None, confidence=None, reviewed_label=None,
                    review_status="needs_review", zone_id=REAL_ZONE_ID, is_superseded=False,
                )
            )


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


async def test_tags_are_normalized_bounded_and_organization_only(
    client: httpx.AsyncClient,
    isolated_repository: ProductRepository,
) -> None:
    assert (await client.get("/api/tags")).json() == []
    with isolated_repository.session_factory() as session:
        review_count_before = session.scalar(select(func.count(ReviewLabelModel.id))) or 0
        assert session.scalar(select(VisitTagModel.id).limit(1)) is None
        assert session.scalar(select(VisitTagMembershipModel.visit_id).limit(1)) is None

    unsafe = await client.post(
        "/api/tags",
        json={"name": "unsafe\nname", "idempotency_key": "unsafe-tag"},
    )
    assert unsafe.status_code == 400
    created = await client.post(
        "/api/tags",
        json={"name": "  Poor   Lighting  ", "idempotency_key": "create-lighting"},
    )
    assert created.status_code == 201
    tag = created.json()
    assert tag["name"] == "Poor Lighting"
    duplicate = await client.post(
        "/api/tags",
        json={"name": "poor lighting", "idempotency_key": "duplicate-lighting"},
    )
    assert duplicate.status_code == 409
    renamed = await client.patch(
        f"/api/tags/{tag['id']}",
        json={
            "name": "Low light",
            "expected_state_token": tag["state_token"],
            "idempotency_key": "rename-lighting",
        },
    )
    assert renamed.status_code == 200
    tag = renamed.json()
    assert tag["name"] == "Low light"

    added = await client.post(
        f"/api/tags/{tag['id']}/visits/{VISIT_ID}",
        json={"expected_state_token": tag["state_token"], "idempotency_key": "add-lighting"},
    )
    assert added.status_code == 200
    assert added.json()["result"]["status"] == "updated"
    repeated = await client.post(
        f"/api/tags/{tag['id']}/visits/{VISIT_ID}",
        json={"expected_state_token": added.json()["tag"]["state_token"], "idempotency_key": "add-lighting-again"},
    )
    assert repeated.status_code == 200
    assert repeated.json()["result"]["status"] == "already_present"
    memberships = await client.get(f"/api/visits/{VISIT_ID}/tags")
    assert [item["name"] for item in memberships.json()["tags"]] == ["Low light"]

    filtered = await client.post(
        "/api/activity-library/search",
        json={"tag_id": tag["id"], "page_size": 50},
    )
    row = next(item for item in filtered.json()["visits"] if item["id"] == VISIT_ID)
    assert row["tags"] == ["Low light"]
    assert SECOND_VISIT_ID not in {item["id"] for item in filtered.json()["visits"]}

    bulk = await client.post(
        "/api/tags/memberships/bulk",
        json={
            "tag_id": tag["id"],
            "visit_ids": [VISIT_ID, SECOND_VISIT_ID],
            "action": "add",
            "expected_state_token": repeated.json()["tag"]["state_token"],
            "idempotency_key": "bulk-lighting",
        },
    )
    assert bulk.status_code == 200
    assert [item["status"] for item in bulk.json()["results"]] == ["already_present", "updated"]

    archived = await client.post(
        f"/api/tags/{tag['id']}/archive",
        json={
            "expected_state_token": bulk.json()["tag"]["state_token"],
            "idempotency_key": "archive-lighting",
        },
    )
    assert archived.status_code == 200
    assert archived.json()["archived_at"] is not None
    assert (await client.get("/api/tags")).json() == []
    assert (await client.get(f"/api/visits/{VISIT_ID}/tags")).json()["tags"] == []
    with isolated_repository.session_factory() as session:
        assert session.scalar(select(func.count(VisitTagMembershipModel.visit_id))) == 2
        assert (session.scalar(select(func.count(ReviewLabelModel.id))) or 0) == review_count_before


async def test_journal_tag_filter_changes_only_the_bounded_gallery(
    client: httpx.AsyncClient,
    isolated_repository: ProductRepository,
) -> None:
    add_real_visit(isolated_repository)
    reviewed = await client.post(
        "/api/review-labels",
        json={
            "review_origin": "human", "target_type": "visit",
            "target_id": REAL_VISIT_ID, "label": "northern_cardinal",
        },
    )
    assert reviewed.status_code == 201
    tag = await client.post(
        "/api/tags",
        json={"name": "Training candidate", "idempotency_key": "journal-tag-create"},
    )
    assert tag.status_code == 201
    added = await client.post(
        f"/api/tags/{tag.json()['id']}/visits/{REAL_VISIT_ID}",
        json={
            "expected_state_token": tag.json()["state_token"],
            "idempotency_key": "journal-tag-add",
        },
    )
    assert added.status_code == 200

    unfiltered = await client.get("/api/bird-log/journal/northern_cardinal")
    filtered = await client.get(f"/api/bird-log/journal/northern_cardinal?tag_id={tag.json()['id']}")
    assert unfiltered.status_code == 200
    assert filtered.status_code == 200
    assert filtered.json()["observation_count"] == unfiltered.json()["observation_count"]
    assert filtered.json()["scope"]["tag_id"] == tag.json()["id"]
    assert [row["visit_id"] for row in filtered.json()["gallery"]["observations"]] == [REAL_VISIT_ID]
    assert filtered.json()["gallery"]["observations"][0]["tags"] == ["Training candidate"]


def test_current_schema_creates_only_empty_tag_records(tmp_path: Path) -> None:
    repository = ProductRepository(
        db_url=f"sqlite:///{tmp_path / 'migration.sqlite3'}",
        media_root=tmp_path / "media",
    )
    de_demo_seeded_source(repository)
    assert CURRENT_DATABASE_SCHEMA_VERSION == 60
    table_names = set(inspect(repository.engine).get_table_names())
    assert {"visit_tags", "visit_tag_memberships"}.issubset(table_names)
    with repository.session_factory() as session:
        assert session.scalar(select(VisitTagModel.id).limit(1)) is None
        assert session.scalar(select(VisitTagMembershipModel.visit_id).limit(1)) is None
