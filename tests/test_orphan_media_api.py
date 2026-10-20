"""API surface for orphan media integrity (contract: docs/orphan-media-integrity-recovery-contract.md)."""

from __future__ import annotations

import os
import time
from pathlib import Path

import httpx
import pytest
from sqlalchemy import text

from mockingbird.api.main import app, configure_repository
from mockingbird.repository.product_repository import ProductRepository
from tests.conftest import LegacyAuthenticatedTestClient

pytestmark = pytest.mark.anyio

BASE = "/api/settings/storage-retention/orphan-media"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def repository(tmp_path: Path) -> ProductRepository:
    active = ProductRepository(
        db_url=f"sqlite:///{tmp_path / 'mockingbird.sqlite3'}", media_root=tmp_path / "media"
    )
    configure_repository(active)
    yield active
    configure_repository(None)


@pytest.fixture
async def client(repository: ProductRepository):
    transport = httpx.ASGITransport(app=app)
    async with LegacyAuthenticatedTestClient(transport=transport, base_url="http://testserver") as api_client:
        yield api_client


def _orphan(repository: ProductRepository, relative: str, content: bytes = b"orphan") -> Path:
    path = repository.media_root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    old = time.time() - 3 * 3600
    os.utime(path, (old, old))
    return path


async def test_scan_is_report_only_and_hides_the_absolute_root(client: httpx.AsyncClient, repository: ProductRepository) -> None:
    orphan = _orphan(repository, "stray.jpg")
    response = await client.post(f"{BASE}/scan")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "orphans_found" and body["orphan_count"] == 1
    assert body["findings"][0]["relative_path"] == "stray.jpg"
    assert body["changed_anything"] is False and body["creates_review_truth"] is False
    assert str(repository.media_root) not in response.text
    assert orphan.exists()


async def test_scan_reports_incomplete_not_clean_when_the_database_cannot_be_read(
    client: httpx.AsyncClient, repository: ProductRepository
) -> None:
    _orphan(repository, "stray.jpg")
    with repository.engine.begin() as connection:
        connection.execute(text("ALTER TABLE media_assets RENAME TO media_assets_gone"))
    body = (await client.post(f"{BASE}/scan")).json()
    assert body["status"] == "incomplete" and body["complete"] is False
    assert body["orphan_count"] == 0 and "could not finish" in body["message"]


async def test_quarantine_requires_confirmation_then_moves_and_restores(
    client: httpx.AsyncClient, repository: ProductRepository
) -> None:
    orphan = _orphan(repository, "lost/one.jpg", b"payload")
    unconfirmed = await client.post(f"{BASE}/quarantine", json={"relative_paths": ["lost/one.jpg"]})
    assert unconfirmed.status_code == 400 and orphan.exists()

    moved = await client.post(f"{BASE}/quarantine", json={"confirm": True, "relative_paths": ["lost/one.jpg"]})
    assert moved.status_code == 200
    body = moved.json()
    assert body["status"] == "completed" and body["moved_count"] == 1
    assert str(repository.media_root) not in moved.text
    assert not orphan.exists()

    history = (await client.get(f"{BASE}/quarantine-history")).json()
    assert [b["batch_id"] for b in history["batches"]] == [body["batch_id"]]

    restored = await client.post(f"{BASE}/quarantine-history/{body['batch_id']}/restore")
    assert restored.status_code == 200 and restored.json()["restored_count"] == 1
    assert orphan.read_bytes() == b"payload"
    assert (await client.post(f"{BASE}/quarantine-history/orphan-20200101T000000Z-deadbeef/restore")).status_code == 404


async def test_quarantine_rejects_traversal_selection_and_invalid_sizes(
    client: httpx.AsyncClient, repository: ProductRepository
) -> None:
    outside = repository.media_root.parent / "outside.jpg"
    outside.write_bytes(b"x")
    response = await client.post(f"{BASE}/quarantine", json={"confirm": True, "relative_paths": ["../outside.jpg"]})
    assert response.status_code == 200
    assert response.json()["status"] == "nothing_to_move" and response.json()["items"][0]["code"] == "unsafe_path"
    assert outside.exists()
    assert (await client.post(f"{BASE}/quarantine", json={"confirm": True, "relative_paths": []})).status_code == 422


async def test_quarantine_is_refused_with_a_safe_message_when_the_scan_is_incomplete(
    client: httpx.AsyncClient, repository: ProductRepository
) -> None:
    orphan = _orphan(repository, "lost.jpg")
    with repository.engine.begin() as connection:
        connection.execute(text("ALTER TABLE media_assets RENAME TO media_assets_gone"))
    response = await client.post(f"{BASE}/quarantine", json={"confirm": True, "relative_paths": ["lost.jpg"]})
    assert response.status_code == 409
    assert "nothing was moved" in response.json()["detail"] and str(repository.media_root) not in response.text
    assert orphan.exists()


def test_mutating_orphan_routes_are_administrator_only() -> None:
    from mockingbird.api.auth import ROUTE_POLICY, PolicyTier

    for path in (
        f"{BASE}/scan",
        f"{BASE}/quarantine",
        f"{BASE}/quarantine-history/{{batch_id}}/restore",
    ):
        assert ROUTE_POLICY[("POST", path)] == PolicyTier.administrator
