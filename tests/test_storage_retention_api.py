from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest
from sqlalchemy import select

from mockingbird.api.main import app, configure_repository
from mockingbird.repository.product_repository import ProductRepository
from mockingbird.storage.models import (
    EventModel,
    MediaAssetModel,
    StreamModel,
    VisitEvidenceLinkModel,
    VisitModel,
)
from tests.conftest import LegacyAuthenticatedTestClient


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
    async with LegacyAuthenticatedTestClient(transport=transport, base_url="http://testserver") as api_client:
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


# --- Manual Import Evidence Integrity v1: end-to-end over the real HTTP API -


async def test_storage_summary_endpoint_does_not_orphan_a_real_manual_import(
    client: httpx.AsyncClient,
) -> None:
    """The exact user-facing symptom, proven over the real API a browser
    actually calls: a manually imported Visit's media must not appear
    orphaned in `GET /api/settings/storage-retention/summary` (the Local
    Data page's data source)."""
    import_response = await client.post(
        "/api/media/import",
        files={"file": ("evidence-integrity.jpg", b"manual-import-api-bytes", "image/jpeg")},
        data={"subject_label": "unknown_bird"},
    )
    assert import_response.status_code == 201

    summary_response = await client.get("/api/settings/storage-retention/summary")
    assert summary_response.status_code == 200
    summary = summary_response.json()
    assert summary["orphaned_managed_media_count"] == 0
    assert summary["active_visit_media_count"] == 1


async def test_evidence_link_repair_endpoints_report_then_require_confirm_then_apply(
    client: httpx.AsyncClient,
    repository: ProductRepository,
) -> None:
    path = _add_orphaned_media(repository, "repair-api-media")
    with repository.session_factory() as session:
        with session.begin():
            asset = session.get(MediaAssetModel, "repair-api-media")
            assert asset is not None
            session.add(
                EventModel(
                    id="repair-api-event",
                    stream_id=asset.stream_id,
                    title="legacy imported media (API repair test)",
                    event_type="manual_media_import",
                    started_at=asset.created_at,
                    ended_at=asset.created_at,
                    primary_zone_id=None,
                    review_status="needs_review",
                )
            )
            session.add(
                VisitModel(
                    id="repair-api-visit",
                    event_id="repair-api-event",
                    subject_label="unknown_animal",
                    species_guess=None,
                    confidence=None,
                    reviewed_label=None,
                    review_status="needs_review",
                    representative_media_path=asset.local_path,
                    zone_id=None,
                    is_superseded=False,
                )
            )

    report_response = await client.get("/api/media/evidence-link-repair-report")
    assert report_response.status_code == 200
    report = report_response.json()
    entry = next(e for e in report["entries"] if e["visit_id"] == "repair-api-visit")
    assert entry["outcome"] == "would_repair"

    unconfirmed = await client.post("/api/media/evidence-link-repair", json={"confirm": False})
    assert unconfirmed.status_code == 400

    applied_response = await client.post("/api/media/evidence-link-repair", json={"confirm": True})
    assert applied_response.status_code == 200
    applied = applied_response.json()
    applied_entry = next(e for e in applied["entries"] if e["visit_id"] == "repair-api-visit")
    assert applied_entry["outcome"] == "repaired"

    with repository.session_factory() as session:
        links = session.scalars(
            select(VisitEvidenceLinkModel).where(VisitEvidenceLinkModel.visit_id == "repair-api-visit")
        ).all()
        assert len(links) == 1
    assert path.exists()
