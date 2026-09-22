from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from mockingbird.api.main import app, configure_repository
from mockingbird.repository.product_repository import ProductRepository
from tests.conftest import de_demo_seeded_source, LegacyAuthenticatedTestClient


VISIT_ID = "visit-bird-feeder-001"

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


async def test_organization_is_private_idempotent_and_filterable(client: httpx.AsyncClient) -> None:
    initial = await client.get(f"/api/visits/{VISIT_ID}/organization")
    assert initial.status_code == 200
    assert initial.json() == {
        "visit_id": VISIT_ID,
        "is_favorite": False,
        "note": "",
        "inherited_from_visit_id": None,
        "created_at": None,
        "updated_at": None,
        "state_token": f"organization:{VISIT_ID}:0",
    }

    payload = {
        "is_favorite": True,
        "note": "Seen near the feeder.\nKeep an eye on this Visit.",
        "expected_state_token": initial.json()["state_token"],
        "idempotency_key": "visit-organization-first-save",
    }
    updated = await client.put(f"/api/visits/{VISIT_ID}/organization", json=payload)
    assert updated.status_code == 200
    assert updated.json()["is_favorite"] is True
    assert updated.json()["note"] == payload["note"]
    assert updated.json()["created_at"] == updated.json()["updated_at"]

    repeated = await client.put(f"/api/visits/{VISIT_ID}/organization", json=payload)
    assert repeated.status_code == 200
    assert repeated.json()["state_token"] == updated.json()["state_token"]

    stale = await client.put(
        f"/api/visits/{VISIT_ID}/organization",
        json={
            "note": "A stale replacement",
            "expected_state_token": initial.json()["state_token"],
            "idempotency_key": "visit-organization-stale-save",
        },
    )
    assert stale.status_code == 409

    unsafe = await client.put(
        f"/api/visits/{VISIT_ID}/organization",
        json={
            "note": "not\u0000safe",
            "expected_state_token": updated.json()["state_token"],
            "idempotency_key": "visit-organization-unsafe-save",
        },
    )
    assert unsafe.status_code == 400

    favorites = await client.post(
        "/api/activity-library/search",
        json={"favorites_only": True, "page_size": 50},
    )
    favorite_row = next(row for row in favorites.json()["visits"] if row["id"] == VISIT_ID)
    assert favorite_row["is_favorite"] is True

    notes = await client.post(
        "/api/activity-library/search",
        json={"has_note": True, "page_size": 50},
    )
    note_row = next(row for row in notes.json()["visits"] if row["id"] == VISIT_ID)
    assert note_row["has_note"] is True
