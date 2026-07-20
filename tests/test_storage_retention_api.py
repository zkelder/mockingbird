from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest
from sqlalchemy import select

from mockingbird.api.main import app, configure_repository
from mockingbird.repository.product_repository import ProductRepository
from mockingbird.storage.models import MediaAssetModel, StreamModel


pytestmark = pytest.mark.anyio


@pytest.fixture
def repository(tmp_path: Path) -> ProductRepository:
    active_repository = ProductRepository(
        db_url=f"sqlite:///{tmp_path / 'mockingbird.sqlite3'}",
        media_root=tmp_path / "media",
    )
    configure_repository(active_repository)
    yield active_repository
    configure_repository(None)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def client(repository: ProductRepository):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as api_client:
        yield api_client


def _add_orphaned_media(repository: ProductRepository, media_id: str) -> Path:
    path = repository.media_root / f"{media_id}.bin"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"retention-api-test")
    with repository.session_factory() as session:
        with session.begin():
            stream = session.scalar(select(StreamModel).order_by(StreamModel.id))
            assert stream is not None
            session.add(
                MediaAssetModel(
                    id=media_id,
                    source_id=stream.source_id,
                    stream_id=stream.id,
                    filename=path.name,
                    content_type="application/octet-stream",
                    media_type="image",
                    local_path=str(path),
                    original_filename=path.name,
                    file_size_bytes=path.stat().st_size,
                    created_at=datetime.now(UTC) - timedelta(days=60),
                    notes="retention API test media",
                )
            )
    return path


async def test_storage_retention_preview_is_server_owned_and_stale_execution_is_rejected(
    client: httpx.AsyncClient,
    repository: ProductRepository,
) -> None:
    first_path = _add_orphaned_media(repository, "storage-api-first")

    summary = await client.get("/api/settings/storage-retention/summary")
    assert summary.status_code == 200
    assert summary.json()["total_managed_media_count"] == 1
    assert str(repository.media_root) not in summary.text

    preview_response = await client.post("/api/settings/storage-retention/cleanup-preview")
    assert preview_response.status_code == 200
    preview = preview_response.json()
    assert preview["eligible_media_count"] == 1
    assert first_path.exists()

    _add_orphaned_media(repository, "storage-api-second")
    execute = await client.post(
        "/api/settings/storage-retention/cleanup",
        json={
            "preview_token": preview["preview_token"],
            "confirm": True,
            "idempotency_key": "storage-api-stale-preview",
        },
    )

    assert execute.status_code == 409
    assert "Generate a new preview" in execute.json()["detail"]
    assert first_path.exists()
