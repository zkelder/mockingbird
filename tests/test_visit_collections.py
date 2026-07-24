from __future__ import annotations

from pathlib import Path

import httpx
import pytest
from sqlalchemy import func, inspect, select

from mockingbird.api.main import app, configure_repository
from mockingbird.repository.product_repository import ProductRepository
from mockingbird.storage.database import CURRENT_DATABASE_SCHEMA_VERSION
from mockingbird.storage.models import ReviewLabelModel, VisitCollectionMembershipModel, VisitCollectionModel


VISIT_ID = "visit-bird-feeder-001"
SECOND_VISIT_ID = "visit-squirrel-ground-001"

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


async def test_collections_are_normalized_bounded_and_organization_only(
    client: httpx.AsyncClient,
    isolated_repository: ProductRepository,
) -> None:
    assert (await client.get("/api/collections")).json() == []
    with isolated_repository.session_factory() as session:
        review_count_before = session.scalar(select(func.count(ReviewLabelModel.id))) or 0
        assert session.scalar(select(VisitCollectionModel.id).limit(1)) is None
        assert session.scalar(select(VisitCollectionMembershipModel.visit_id).limit(1)) is None

    created = await client.post(
        "/api/collections",
        json={"name": "  Favorites  ", "description": "A private gallery", "idempotency_key": "create-favorites"},
    )
    assert created.status_code == 201
    collection = created.json()
    assert collection["name"] == "Favorites"
    duplicate = await client.post(
        "/api/collections",
        json={"name": "favorites", "idempotency_key": "create-favorites-duplicate"},
    )
    assert duplicate.status_code == 409

    added = await client.post(
        f"/api/collections/{collection['id']}/visits/{VISIT_ID}",
        json={"expected_state_token": collection["state_token"], "idempotency_key": "add-first-visit"},
    )
    assert added.status_code == 200
    assert added.json()["result"]["status"] == "updated"
    repeated = await client.post(
        f"/api/collections/{collection['id']}/visits/{VISIT_ID}",
        json={"expected_state_token": added.json()["collection"]["state_token"], "idempotency_key": "add-first-visit-again"},
    )
    assert repeated.status_code == 200
    assert repeated.json()["result"]["status"] == "already_present"
    cleared_description = await client.patch(
        f"/api/collections/{collection['id']}",
        json={
            "description": None,
            "expected_state_token": repeated.json()["collection"]["state_token"],
            "idempotency_key": "clear-description",
        },
    )
    assert cleared_description.status_code == 200
    assert cleared_description.json()["description"] is None

    second_collection = await client.post(
        "/api/collections",
        json={"name": "Spring feeder activity", "idempotency_key": "create-spring"},
    )
    assert second_collection.status_code == 201
    added_twice = await client.post(
        f"/api/collections/{second_collection.json()['id']}/visits/{VISIT_ID}",
        json={"expected_state_token": second_collection.json()["state_token"], "idempotency_key": "add-to-second-collection"},
    )
    assert added_twice.status_code == 200
    memberships = await client.get(f"/api/visits/{VISIT_ID}/collections")
    assert [item["name"] for item in memberships.json()["collections"]] == ["Favorites", "Spring feeder activity"]

    filtered = await client.post(
        "/api/activity-library/search",
        json={"collection_id": collection["id"], "page_size": 50},
    )
    row = next(item for item in filtered.json()["visits"] if item["id"] == VISIT_ID)
    assert row["collection_count"] == 2

    archived = await client.post(
        f"/api/collections/{collection['id']}/archive",
        json={"expected_state_token": cleared_description.json()["state_token"], "idempotency_key": "archive-favorites"},
    )
    assert archived.status_code == 200
    assert archived.json()["archived_at"] is not None
    assert collection["id"] not in {item["id"] for item in (await client.get("/api/collections")).json()}
    assert (await client.get(f"/api/collections/{collection['id']}")).json()["archived_at"] is not None
    assert (await client.get(f"/api/visits/{VISIT_ID}/collections")).json()["collections"][0]["id"] == second_collection.json()["id"]
    with isolated_repository.session_factory() as session:
        assert (session.scalar(select(func.count(ReviewLabelModel.id))) or 0) == review_count_before


def test_current_schema_creates_only_empty_collection_records(tmp_path: Path) -> None:
    repository = ProductRepository(
        db_url=f"sqlite:///{tmp_path / 'migration.sqlite3'}",
        media_root=tmp_path / "media",
    )
    assert CURRENT_DATABASE_SCHEMA_VERSION == 23
    table_names = set(inspect(repository.engine).get_table_names())
    assert {"visit_collections", "visit_collection_memberships"}.issubset(table_names)
    with repository.session_factory() as session:
        assert session.scalar(select(VisitCollectionModel.id).limit(1)) is None
        assert session.scalar(select(VisitCollectionMembershipModel.visit_id).limit(1)) is None
