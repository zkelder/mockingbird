from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest

from mockingbird.api.main import app, configure_repository
from mockingbird.repository.product_repository import ProductRepository
from mockingbird.source_providers import external_url_preview
from mockingbird.storage.models import MediaAssetModel
from tests.conftest import LegacyAuthenticatedTestClient

pytestmark = pytest.mark.anyio

SOURCE_ID = "source-backyard-demo"
STREAM_ID = "stream-backyard-feeder"
FEEDER_ZONE_ID = "zone-feeder"


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
    async with LegacyAuthenticatedTestClient(transport=transport, base_url="http://testserver") as api_client:
        yield api_client


def create_saved_preview_media(
    repository: ProductRepository,
    *,
    content: bytes = b"retention-image-bytes",
    note: str | None = None,
) -> str:
    media_asset = repository.create_external_url_preview_media_asset(
        source_id=SOURCE_ID,
        stream_id=STREAM_ID,
        content=content,
        content_type="image/jpeg",
        fetched_at=datetime(2026, 1, 2, 3, 4, tzinfo=UTC),
        url_host="192.168.1.50",
        note=note,
    )
    return media_asset.id


async def product_counts(client: httpx.AsyncClient) -> dict[str, int]:
    responses = {
        "events": await client.get("/api/events"),
        "visits": await client.get("/api/visits"),
        "review_labels": await client.get("/api/review-labels"),
        "motion_evidence": await client.get("/api/motion/evidence"),
        "species_suggestions": await client.get("/api/species-suggestions"),
        "detection_proposals": await client.get("/api/detection-proposals"),
        "dataset_exports": await client.get("/api/dataset-exports"),
        "media_assets": await client.get("/api/media"),
    }
    assert all(response.status_code == 200 for response in responses.values())

    return {
        "events": len(responses["events"].json()),
        "visits": len(responses["visits"].json()),
        "review_labels": len(responses["review_labels"].json()),
        "motion_evidence": len(responses["motion_evidence"].json()["motion_evidence"]),
        "species_suggestions": len(responses["species_suggestions"].json()["species_suggestions"]),
        "detection_proposals": len(responses["detection_proposals"].json()),
        "dataset_exports": len(responses["dataset_exports"].json()),
        "media_assets": len(responses["media_assets"].json()),
    }


def media_file_snapshot(repository: ProductRepository) -> dict[str, int]:
    if not repository.media_root.exists():
        return {}
    return {
        str(path.relative_to(repository.media_root)): path.stat().st_size
        for path in repository.media_root.rglob("*")
        if path.is_file()
    }


def fail_if_called(*_args: Any, **_kwargs: Any) -> None:
    raise AssertionError("Retention report/dry-run must not fetch URLs or run detector code")


def item_by_id(report: dict[str, Any], media_asset_id: str) -> dict[str, Any]:
    return next(item for item in report["items"] if item["media_asset_id"] == media_asset_id)


async def report(client: httpx.AsyncClient) -> dict[str, Any]:
    response = await client.get("/api/media/saved-preview-retention")
    assert response.status_code == 200
    return response.json()


async def test_retention_report_lists_unlinked_saved_preview_and_default_dry_run_deletes_nothing(
    client: httpx.AsyncClient,
    isolated_repository: ProductRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    media_asset_id = create_saved_preview_media(
        isolated_repository,
        content=b"image-bytes",
        note="operator note includes password-secret but is not retention provenance",
    )
    before_counts = await product_counts(client)
    before_files = media_file_snapshot(isolated_repository)

    monkeypatch.setattr(external_url_preview, "fetch_external_url_preview", fail_if_called)
    monkeypatch.setattr(
        "mockingbird.repository.product_repository.run_local_image_detector",
        fail_if_called,
    )
    monkeypatch.setattr(
        "mockingbird.repository.product_repository.run_megadetector_on_image",
        fail_if_called,
    )

    body = await report(client)
    item = item_by_id(body, media_asset_id)

    assert body["dry_run_only"] is True
    assert body["summary"]["total_items"] == 1
    assert body["summary"]["total_known_bytes"] == len(b"image-bytes")
    assert body["summary"]["low_risk_count"] == 1
    assert item["risk_level"] == "low"
    assert item["media_state"] == "saved_unlinked"
    assert item["provider_key"] == "external_url"
    assert item["size_bytes"] == len(b"image-bytes")
    assert item["linked_motion_evidence_count"] == 0
    assert item["reviewed_truth_count"] == 0
    assert "url_host=192.168.1.50" in item["provenance"]
    assert "password-secret" not in str(body)

    dry_run_response = await client.post(
        "/api/media/saved-preview-retention/dry-run-cleanup",
        json={},
    )
    assert dry_run_response.status_code == 200
    dry_run = dry_run_response.json()
    assert dry_run["dry_run"] is True
    assert dry_run["creates_truth"] is False
    assert dry_run["deletes_truth"] is False
    assert dry_run["total_would_delete_files"] == 1
    assert dry_run["total_would_delete_records"] == 0
    assert dry_run["total_known_bytes_to_delete"] == len(b"image-bytes")
    assert dry_run["items"] == [
        {
            "media_asset_id": media_asset_id,
            "risk_level": "low",
            "would_delete_file": True,
            "would_delete_record": False,
            "would_skip": False,
            "skip_reason": None,
            "file_name": item["file_name"],
            "size_bytes": len(b"image-bytes"),
            "warnings": [],
        }
    ]

    assert await product_counts(client) == before_counts
    assert media_file_snapshot(isolated_repository) == before_files


async def test_retention_risk_tracks_motion_promotion_and_review_truth(
    client: httpx.AsyncClient,
    isolated_repository: ProductRepository,
) -> None:
    pending_media_id = create_saved_preview_media(isolated_repository, content=b"pending")
    pending_response = await client.post(
        f"/api/media/{pending_media_id}/create-motion-evidence",
        json={"zone_id": FEEDER_ZONE_ID},
    )
    assert pending_response.status_code == 201
    pending_evidence_id = pending_response.json()["motion_evidence_id"]

    pending_item = item_by_id(await report(client), pending_media_id)
    assert pending_item["risk_level"] == "medium"
    assert pending_item["media_state"] == "linked_pending_evidence"
    assert pending_item["linked_motion_evidence_count"] == 1

    ignored_response = await client.post(f"/api/motion/evidence/{pending_evidence_id}/ignore")
    assert ignored_response.status_code == 200
    ignored_item = item_by_id(await report(client), pending_media_id)
    assert ignored_item["risk_level"] == "medium"
    assert ignored_item["media_state"] == "linked_ignored_evidence"

    promoted_media_id = create_saved_preview_media(isolated_repository, content=b"promoted")
    promoted_evidence_response = await client.post(
        f"/api/media/{promoted_media_id}/create-motion-evidence",
        json={"zone_id": FEEDER_ZONE_ID},
    )
    assert promoted_evidence_response.status_code == 201
    promoted_evidence_id = promoted_evidence_response.json()["motion_evidence_id"]
    promote_response = await client.post(f"/api/motion/evidence/{promoted_evidence_id}/promote")
    assert promote_response.status_code == 200
    promoted = promote_response.json()
    promoted_item = item_by_id(await report(client), promoted_media_id)
    assert promoted_item["risk_level"] == "high"
    assert promoted_item["media_state"] == "linked_event_visit"
    assert promoted_item["linked_event_count"] == 1
    assert promoted_item["linked_visit_count"] == 1

    correction_response = await client.post(
        "/api/review-labels",
        json={"review_origin": "human", 
            "target_type": "visit",
            "target_id": promoted["visit_id"],
            "label": "Northern Cardinal",
            "notes": "Retention truth boundary test.",
        },
    )
    assert correction_response.status_code == 201
    protected_item = item_by_id(await report(client), promoted_media_id)
    assert protected_item["risk_level"] == "protected"
    assert protected_item["media_state"] == "reviewed_truth_context"
    assert protected_item["reviewed_truth_count"] >= 1

    before_counts = await product_counts(client)
    before_files = media_file_snapshot(isolated_repository)
    dry_run_response = await client.post(
        "/api/media/saved-preview-retention/dry-run-cleanup",
        json={"media_asset_ids": [promoted_media_id]},
    )
    assert dry_run_response.status_code == 200
    dry_run = dry_run_response.json()
    assert dry_run["items"][0]["risk_level"] == "protected"
    assert dry_run["items"][0]["would_skip"] is True
    assert dry_run["items"][0]["skip_reason"] == "protected_media_skipped"
    assert dry_run["protected_skipped_count"] == 1
    assert dry_run["total_would_delete_files"] == 0
    assert dry_run["creates_truth"] is False
    assert dry_run["deletes_truth"] is False
    assert await product_counts(client) == before_counts
    assert media_file_snapshot(isolated_repository) == before_files


async def test_retention_report_handles_stale_saved_preview_reference_safely(
    client: httpx.AsyncClient,
    isolated_repository: ProductRepository,
) -> None:
    missing_path = isolated_repository.media_root / "missing-preview.jpg"
    notes = "\n".join(
        [
            "Saved explicit external_url still-image preview.",
            "Creates no Events, Visits, ReviewLabels, or truth.",
            "provider_key=external_url",
            f"source_id={SOURCE_ID}",
            f"stream_id={STREAM_ID}",
            "fetched_at=2026-01-02T03:04:00+00:00",
            "content_type=image/jpeg",
            "bytes_written=19",
            "url_host=192.168.1.50",
            "note=password-secret should not be exposed as provenance",
        ]
    )
    with isolated_repository.session_factory() as session:
        with session.begin():
            session.add(
                MediaAssetModel(
                    id="media-asset-stale-preview",
                    source_id=SOURCE_ID,
                    stream_id=STREAM_ID,
                    filename="missing-preview.jpg",
                    content_type="image/jpeg",
                    media_type="image",
                    local_path=str(missing_path),
                    original_filename="external-url-preview-stale.jpg",
                    file_size_bytes=19,
                    created_at=datetime(2026, 1, 2, 3, 4, tzinfo=UTC),
                    notes=notes,
                )
            )

    assert not missing_path.exists()
    body = await report(client)
    item = item_by_id(body, "media-asset-stale-preview")

    assert item["risk_level"] == "low"
    assert item["media_state"] == "saved_unlinked"
    assert item["size_bytes"] == 19
    assert any("missing or stale" in warning for warning in item["warnings"])
    assert body["summary"]["warnings"] == [
        "Some saved preview media has retention warnings; inspect item warnings."
    ]
    assert "password-secret" not in str(body)

    dry_run_response = await client.post(
        "/api/media/saved-preview-retention/dry-run-cleanup",
        json={"media_asset_ids": ["media-asset-stale-preview"]},
    )
    assert dry_run_response.status_code == 200
    dry_run_item = dry_run_response.json()["items"][0]
    assert dry_run_item["would_skip"] is True
    assert dry_run_item["skip_reason"] == "stale_media_reference"
    assert dry_run_item["would_delete_file"] is False
    assert dry_run_item["would_delete_record"] is False
    assert not missing_path.exists()
