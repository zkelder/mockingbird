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
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as api_client:
        yield api_client


def saved_preview_notes(
    *,
    source_id: str = SOURCE_ID,
    stream_id: str = STREAM_ID,
    bytes_written: int = 19,
    content_type: str = "image/jpeg",
) -> str:
    return "\n".join(
        [
            "Saved explicit external_url still-image preview.",
            "Creates no Events, Visits, ReviewLabels, or truth.",
            "provider_key=external_url",
            f"source_id={source_id}",
            f"stream_id={stream_id}",
            "fetched_at=2026-01-02T03:04:00+00:00",
            f"content_type={content_type}",
            f"bytes_written={bytes_written}",
            "url_host=192.168.1.50",
        ]
    )


def create_saved_preview_media(
    repository: ProductRepository,
    *,
    content: bytes = b"cleanup-image-bytes",
) -> str:
    media_asset = repository.create_external_url_preview_media_asset(
        source_id=SOURCE_ID,
        stream_id=STREAM_ID,
        content=content,
        content_type="image/jpeg",
        fetched_at=datetime(2026, 1, 2, 3, 4, tzinfo=UTC),
        url_host="192.168.1.50",
    )
    return media_asset.id


def insert_media_asset(
    repository: ProductRepository,
    *,
    media_id: str,
    local_path: Path,
    notes: str | None,
    filename: str | None = None,
) -> str:
    with repository.session_factory() as session:
        with session.begin():
            session.add(
                MediaAssetModel(
                    id=media_id,
                    source_id=SOURCE_ID,
                    stream_id=STREAM_ID,
                    filename=filename or local_path.name,
                    content_type="image/jpeg",
                    media_type="image",
                    local_path=str(local_path),
                    original_filename=filename or local_path.name,
                    file_size_bytes=local_path.stat().st_size if local_path.exists() else 19,
                    created_at=datetime(2026, 1, 2, 3, 4, tzinfo=UTC),
                    notes=notes,
                )
            )
    return media_id


def media_path(repository: ProductRepository, media_id: str) -> Path:
    asset = repository.get_media_asset(media_id)
    assert asset is not None
    return Path(asset.local_path)


def media_file_snapshot(repository: ProductRepository) -> dict[str, int]:
    if not repository.media_root.exists():
        return {}
    return {
        str(path.relative_to(repository.media_root)): path.stat().st_size
        for path in repository.media_root.rglob("*")
        if path.is_file() and not path.is_symlink()
    }


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


def fail_if_called(*_args: Any, **_kwargs: Any) -> None:
    raise AssertionError("Saved media cleanup must not fetch URLs or run detector code")


async def cleanup(
    client: httpx.AsyncClient,
    media_asset_id: str,
    payload: dict[str, Any] | None = None,
) -> httpx.Response:
    return await client.post(
        f"/api/media/{media_asset_id}/cleanup-preview",
        json=payload or {"confirm": True},
    )


async def report_item(client: httpx.AsyncClient, media_asset_id: str) -> dict[str, Any]:
    response = await client.get("/api/media/saved-preview-retention")
    assert response.status_code == 200
    return next(item for item in response.json()["items"] if item["media_asset_id"] == media_asset_id)


async def test_cleanup_requires_confirmation_and_delete_file_only_mode(
    client: httpx.AsyncClient,
    isolated_repository: ProductRepository,
) -> None:
    media_asset_id = create_saved_preview_media(isolated_repository)
    path = media_path(isolated_repository, media_asset_id)

    missing_confirm = await cleanup(client, media_asset_id, {"mode": "delete_file_only"})
    assert missing_confirm.status_code == 400
    assert "Confirm this file-only cleanup" in missing_confirm.json()["detail"]

    unsupported_mode = await cleanup(
        client,
        media_asset_id,
        {"confirm": True, "mode": "archive"},
    )
    assert unsupported_mode.status_code == 400
    assert "Only delete_file_only cleanup" in unsupported_mode.json()["detail"]

    assert path.exists()
    assert isolated_repository.get_media_asset(media_asset_id) is not None


async def test_low_risk_unlinked_cleanup_is_retired_without_changing_media_or_truth(
    client: httpx.AsyncClient,
    isolated_repository: ProductRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    media_asset_id = create_saved_preview_media(isolated_repository, content=b"delete-me")
    path = media_path(isolated_repository, media_asset_id)
    untouched_path = isolated_repository.media_root / "untouched-local-file.txt"
    untouched_path.write_bytes(b"do-not-delete")

    export_response = await client.post(
        "/api/dataset-exports",
        json={"name": "Cleanup boundary export"},
    )
    assert export_response.status_code == 201

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

    response = await cleanup(
        client,
        media_asset_id,
        {
            "confirm": True,
            "mode": "delete_file_only",
            "reason": "low-risk cleanup test",
        },
    )
    assert response.status_code == 200
    body = response.json()

    assert body["status"] == "rejected"
    assert body["risk_level"] == "low"
    assert body["media_state"] == "saved_unlinked"
    assert body["file_deleted"] is False
    assert body["record_deleted"] is False
    assert body["creates_truth"] is False
    assert body["deletes_truth"] is False
    assert body["file_name"] == path.name
    assert str(path) not in str(body)
    assert str(isolated_repository.media_root) not in str(body)

    assert "no longer available" in body["message"]
    assert path.exists()
    assert untouched_path.exists()
    assert isolated_repository.get_media_asset(media_asset_id) is not None

    assert media_file_snapshot(isolated_repository) == before_files
    assert await product_counts(client) == before_counts

    current_item = await report_item(client, media_asset_id)
    assert current_item["risk_level"] == "low"
    assert current_item["media_state"] == "saved_unlinked"


async def test_cleanup_missing_low_risk_file_is_retired_without_deleting_record(
    client: httpx.AsyncClient,
    isolated_repository: ProductRepository,
) -> None:
    media_asset_id = create_saved_preview_media(isolated_repository)
    path = media_path(isolated_repository, media_asset_id)
    path.unlink()
    before_counts = await product_counts(client)

    response = await cleanup(client, media_asset_id)
    assert response.status_code == 200
    body = response.json()

    assert body["status"] == "rejected"
    assert body["file_deleted"] is False
    assert body["record_deleted"] is False
    assert body["creates_truth"] is False
    assert body["deletes_truth"] is False
    assert "no longer available" in body["message"]
    assert isolated_repository.get_media_asset(media_asset_id) is not None
    assert await product_counts(client) == before_counts


async def test_cleanup_rejects_linked_and_reviewed_saved_preview_media(
    client: httpx.AsyncClient,
    isolated_repository: ProductRepository,
) -> None:
    medium_media_id = create_saved_preview_media(isolated_repository, content=b"pending")
    medium_evidence_response = await client.post(
        f"/api/media/{medium_media_id}/create-motion-evidence",
        json={"zone_id": FEEDER_ZONE_ID},
    )
    assert medium_evidence_response.status_code == 201

    high_media_id = create_saved_preview_media(isolated_repository, content=b"promoted")
    high_evidence_response = await client.post(
        f"/api/media/{high_media_id}/create-motion-evidence",
        json={"zone_id": FEEDER_ZONE_ID},
    )
    assert high_evidence_response.status_code == 201
    high_promote_response = await client.post(
        f"/api/motion/evidence/{high_evidence_response.json()['motion_evidence_id']}/promote",
    )
    assert high_promote_response.status_code == 200

    protected_media_id = create_saved_preview_media(isolated_repository, content=b"protected")
    protected_evidence_response = await client.post(
        f"/api/media/{protected_media_id}/create-motion-evidence",
        json={"zone_id": FEEDER_ZONE_ID},
    )
    assert protected_evidence_response.status_code == 201
    protected_promote_response = await client.post(
        f"/api/motion/evidence/{protected_evidence_response.json()['motion_evidence_id']}/promote",
    )
    assert protected_promote_response.status_code == 200
    correction_response = await client.post(
        "/api/review-labels",
        json={"review_origin": "human", 
            "target_type": "visit",
            "target_id": protected_promote_response.json()["visit_id"],
            "label": "Northern Cardinal",
        },
    )
    assert correction_response.status_code == 201

    before_counts = await product_counts(client)
    before_files = media_file_snapshot(isolated_repository)

    expected_states = {
        medium_media_id: ("medium", "linked_pending_evidence"),
        high_media_id: ("high", "linked_event_visit"),
        protected_media_id: ("protected", "reviewed_truth_context"),
    }
    for media_asset_id, (risk_level, media_state) in expected_states.items():
        response = await cleanup(client, media_asset_id)
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "rejected"
        assert body["risk_level"] == risk_level
        assert body["media_state"] == media_state
        assert body["file_deleted"] is False
        assert body["record_deleted"] is False
        assert body["creates_truth"] is False
        assert body["deletes_truth"] is False
        assert media_path(isolated_repository, media_asset_id).exists()

    assert await product_counts(client) == before_counts
    assert media_file_snapshot(isolated_repository) == before_files


async def test_cleanup_rejects_non_saved_preview_media_and_unknown_ids(
    client: httpx.AsyncClient,
    isolated_repository: ProductRepository,
) -> None:
    isolated_repository.media_root.mkdir(parents=True, exist_ok=True)
    manual_path = isolated_repository.media_root / "manual-media.jpg"
    manual_path.write_bytes(b"manual")
    media_asset_id = insert_media_asset(
        isolated_repository,
        media_id="media-asset-manual-cleanup-test",
        local_path=manual_path,
        notes="Imported manual media, not saved external_url preview.",
    )
    before_counts = await product_counts(client)

    response = await cleanup(client, media_asset_id)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "rejected"
    assert body["risk_level"] == "unknown"
    assert body["media_state"] == "unknown"
    assert body["file_deleted"] is False
    assert body["record_deleted"] is False
    assert manual_path.exists()
    assert await product_counts(client) == before_counts

    missing_response = await cleanup(client, "media-asset-does-not-exist")
    assert missing_response.status_code == 404


async def test_cleanup_rejects_paths_outside_media_root(
    client: httpx.AsyncClient,
    isolated_repository: ProductRepository,
    tmp_path: Path,
) -> None:
    outside_path = tmp_path / "outside-preview.jpg"
    outside_path.write_bytes(b"outside")
    media_asset_id = insert_media_asset(
        isolated_repository,
        media_id="media-asset-outside-cleanup-test",
        local_path=outside_path,
        notes=saved_preview_notes(bytes_written=len(b"outside")),
    )
    before_counts = await product_counts(client)

    response = await cleanup(client, media_asset_id)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "rejected"
    assert body["file_deleted"] is False
    assert body["record_deleted"] is False
    assert "no longer available" in body["message"]
    assert str(outside_path) not in str(body)
    assert outside_path.exists()
    assert await product_counts(client) == before_counts


async def test_cleanup_rejects_symlink_media_path(
    client: httpx.AsyncClient,
    isolated_repository: ProductRepository,
) -> None:
    isolated_repository.media_root.mkdir(parents=True, exist_ok=True)
    target_path = isolated_repository.media_root / "target-preview.jpg"
    target_path.write_bytes(b"target")
    symlink_path = isolated_repository.media_root / "symlink-preview.jpg"
    try:
        symlink_path.symlink_to(target_path)
    except OSError as error:
        pytest.skip(f"Symlinks are unavailable in this environment: {error}")
    media_asset_id = insert_media_asset(
        isolated_repository,
        media_id="media-asset-symlink-cleanup-test",
        local_path=symlink_path,
        notes=saved_preview_notes(bytes_written=len(b"target")),
    )
    before_counts = await product_counts(client)

    response = await cleanup(client, media_asset_id)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "rejected"
    assert body["file_deleted"] is False
    assert body["record_deleted"] is False
    assert "no longer available" in body["message"]
    assert target_path.exists()
    assert symlink_path.is_symlink()
    assert await product_counts(client) == before_counts
