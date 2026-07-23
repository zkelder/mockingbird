from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
import asyncio

import httpx
import pytest
from sqlalchemy import select

from mockingbird.api.schemas import (
    ReviewCorrectionCreate,
    StorageRetentionFrequency,
    StorageRetentionSettingsUpdate,
)
from mockingbird.api.main import app, configure_repository
from mockingbird.monitoring.durable_supervisor import DurableMonitoringCandidate
from mockingbird.repository.product_repository import ProductRepository
from mockingbird.storage.models import EventModel, MediaAssetModel, ProductAlertModel, StreamModel, VisitModel


@pytest.fixture
def repository(tmp_path: Path) -> ProductRepository:
    product_repository = ProductRepository(
        db_url=f"sqlite:///{tmp_path / 'mockingbird.sqlite3'}",
        media_root=tmp_path / "media",
    )
    yield product_repository
    product_repository.close()


def _add_reviewable_visit(repository: ProductRepository, visit_id: str = "visit-alert") -> None:
    with repository.session_factory() as session:
        with session.begin():
            stream = session.scalar(select(StreamModel).order_by(StreamModel.id))
            assert stream is not None
            now = datetime.now(UTC)
            event = EventModel(
                id=f"event-{visit_id}", stream_id=stream.id, title="Alert fixture",
                event_type="manual", started_at=now, ended_at=now, primary_zone_id=None,
                review_status="needs_review",
            )
            visit = VisitModel(
                id=visit_id, event_id=event.id, subject_label="bird", species_guess="unknown_bird",
                confidence=None, reviewed_label=None, review_status="needs_review",
                representative_media_path=None, zone_id=None, is_superseded=False,
            )
            session.add_all((event, visit))
            session.flush()
            repository._sync_review_alert(session, visit, now)


def _alerts(repository: ProductRepository, category: str) -> list[ProductAlertModel]:
    with repository.session_factory() as session:
        return session.scalars(
            select(ProductAlertModel).where(ProductAlertModel.category == category).order_by(ProductAlertModel.created_at)
        ).all()


def test_review_alert_is_deduplicated_resolved_and_reopened(repository: ProductRepository) -> None:
    _add_reviewable_visit(repository)
    first = _alerts(repository, "review")
    assert len(first) == 1 and first[0].resolved_at is None

    with repository.session_factory() as session:
        with session.begin():
            visit = session.get(VisitModel, "visit-alert")
            assert visit is not None
            repository._sync_review_alert(session, visit, datetime.now(UTC))
    assert len(_alerts(repository, "review")) == 1

    repository.create_review_label(ReviewCorrectionCreate(
        target_type="visit", target_id="visit-alert", label="northern_cardinal", notes=None,
    ))
    assert _alerts(repository, "review")[0].resolved_at is not None
    assert len(_alerts(repository, "journal")) == 1

    with repository.session_factory() as session:
        with session.begin():
            visit = session.get(VisitModel, "visit-alert")
            assert visit is not None
            visit.review_status, visit.reviewed_label = "needs_review", None
            repository._sync_review_alert(session, visit, datetime.now(UTC))
    assert len(_alerts(repository, "review")) == 2
    assert _alerts(repository, "journal")[0].deduplication_key == "journal:first-label:northern_cardinal"


def test_monitoring_retries_share_one_alert_and_recovery_resolves(repository: ProductRepository) -> None:
    stream = repository.list_streams()[0]
    assert repository.set_stream_monitoring_enabled(stream.id, enabled=True, idempotency_key="enable-alert-stream") is False
    candidate = repository.list_enabled_monitoring_candidates(limit=1)[0]
    now = datetime.now(UTC)
    repository.mark_monitoring_backoff(candidate, app_instance_id="test", failure_count=2, retry_at=now + timedelta(minutes=1), now=now)
    repository.mark_monitoring_backoff(candidate, app_instance_id="test", failure_count=3, retry_at=now + timedelta(minutes=2), now=now)
    alerts = _alerts(repository, "monitoring")
    assert len(alerts) == 1 and alerts[0].resolved_at is None
    repository.mark_monitoring_running(candidate, app_instance_id="test", healthy_at=now, now=now)
    assert _alerts(repository, "monitoring")[0].resolved_at is not None


def test_storage_warning_and_inbox_actions_are_bounded_and_idempotent(repository: ProductRepository) -> None:
    _add_reviewable_visit(repository, "visit-alert-storage")
    stream = repository.list_streams()[0]
    path = repository.media_root / "over-target.bin"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x" * 1_100_000)
    with repository.session_factory() as session:
        with session.begin():
            session.add(MediaAssetModel(
                id="alert-storage-media", source_id=stream.source_id, stream_id=stream.id,
                filename=path.name, content_type="application/octet-stream", media_type="image",
                local_path=str(path), original_filename=path.name, file_size_bytes=1_100_000,
                created_at=datetime.now(UTC), notes="alert fixture",
            ))
    settings = StorageRetentionSettingsUpdate(
        automatic_cleanup_enabled=False, cleanup_frequency=StorageRetentionFrequency.weekly,
        retain_unresolved_visit_evidence=True, retain_reviewed_bird_wildlife_evidence=True,
        reviewed_non_bird_age_days=180, superseded_evidence_age_days=90, orphaned_media_age_days=30,
        maximum_managed_media_bytes=1_048_576, idempotency_key="storage-alert-settings",
    )
    repository.update_storage_retention_settings(settings)
    storage_alert = _alerts(repository, "storage")
    assert len(storage_alert) == 1 and storage_alert[0].action_type == "open_storage_retention"
    inbox = repository.list_product_alerts(page_size=1)
    assert len(inbox.items) == 1 and inbox.next_offset is not None
    assert repository.mark_product_alert_read(storage_alert[0].id)
    assert repository.mark_product_alert_read(storage_alert[0].id)
    assert repository.dismiss_product_alert(storage_alert[0].id)
    assert repository.dismiss_product_alert(storage_alert[0].id)
    assert repository.product_alert_unread().unread_count == 1


def test_empty_inbox_is_valid(repository: ProductRepository) -> None:
    assert repository.list_product_alerts().items == []
    assert repository.product_alert_unread().unread_count == 0


def test_alert_api_is_empty_then_accepts_idempotent_read_and_dismiss(repository: ProductRepository) -> None:
    _add_reviewable_visit(repository, "visit-alert-api")
    configure_repository(repository)

    async def request(method: str, path: str) -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.request(method, path)

    try:
        unread = asyncio.run(request("GET", "/api/alerts/unread"))
        assert unread.status_code == 200
        alert_id = unread.json()["recent"][0]["id"]
        assert asyncio.run(request("POST", f"/api/alerts/{alert_id}/read")).status_code == 200
        assert asyncio.run(request("POST", f"/api/alerts/{alert_id}/read")).status_code == 200
        assert asyncio.run(request("POST", f"/api/alerts/{alert_id}/dismiss")).status_code == 200
        assert asyncio.run(request("GET", "/api/alerts?page_size=1&offset=0")).status_code == 200
    finally:
        configure_repository(None)
