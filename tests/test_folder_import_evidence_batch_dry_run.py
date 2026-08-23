from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from mockingbird.api.main import app, configure_repository
from mockingbird.api.schemas import SourceKind, SourceStatus
from mockingbird.repository.product_repository import ProductRepository
from mockingbird.storage.models import (
    CameraSourceModel,
    MediaAssetModel,
    StreamModel,
    ZoneModel,
)
from tests.conftest import LegacyAuthenticatedTestClient

pytestmark = pytest.mark.anyio

SOURCE_ID = "source-backyard-demo"
STREAM_ID = "stream-backyard-feeder"
FEEDER_ZONE_ID = "zone-feeder"
IGNORE_ZONE_ID = "zone-ignore-driveway-edge"
PRIVACY_ZONE_ID = "zone-folder-batch-privacy"
OTHER_SOURCE_ID = "source-other-folder-batch"
OTHER_STREAM_ID = "stream-other-folder-batch"
OTHER_ZONE_ID = "zone-other-folder-batch"


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


def write_file(path: Path, content: bytes = b"image bytes") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


async def configure_folder_source(client: httpx.AsyncClient, folder: Path) -> None:
    response = await client.patch(
        f"/api/sources/{SOURCE_ID}/provider-configuration",
        json={
            "provider_key": "folder_import_future",
            "config": {
                "folder_path": str(folder),
                "allowed_extensions": "jpg,jpeg,png,webp",
                "default_stream_id": STREAM_ID,
                "default_zone_id": FEEDER_ZONE_ID,
            },
        },
    )
    assert response.status_code == 200


async def import_folder_media_assets(
    client: httpx.AsyncClient,
    tmp_path: Path,
    file_names: list[str],
) -> list[str]:
    folder = tmp_path / "trailcam"
    for index, file_name in enumerate(file_names):
        write_file(folder / file_name, f"folder import image {index}".encode())
    await configure_folder_source(client, folder)

    response = await client.post(
        f"/api/sources/{SOURCE_ID}/folder-import",
        json={
            "relative_paths": file_names,
            "default_stream_id": STREAM_ID,
            "default_zone_id": FEEDER_ZONE_ID,
            "note": "Folder import batch dry-run fixture.",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["total_imported"] == len(file_names)
    assert body["creates_motion_evidence"] is False
    assert body["creates_events"] is False
    assert body["creates_visits"] is False
    assert body["creates_truth"] is False
    return [item["media_asset_id"] for item in body["imported"]]


async def product_counts(client: httpx.AsyncClient) -> dict[str, int]:
    responses = {
        "events": await client.get("/api/events"),
        "visits": await client.get("/api/visits"),
        "review_labels": await client.get("/api/review-labels"),
        "media_assets": await client.get("/api/media"),
        "motion_evidence": await client.get("/api/motion/evidence"),
        "species_suggestions": await client.get("/api/species-suggestions"),
        "detection_proposals": await client.get("/api/detection-proposals"),
        "dataset_exports": await client.get("/api/dataset-exports"),
    }
    assert all(response.status_code == 200 for response in responses.values())
    return {
        "events": len(responses["events"].json()),
        "visits": len(responses["visits"].json()),
        "review_labels": len(responses["review_labels"].json()),
        "media_assets": len(responses["media_assets"].json()),
        "motion_evidence": len(responses["motion_evidence"].json()["motion_evidence"]),
        "species_suggestions": len(responses["species_suggestions"].json()["species_suggestions"]),
        "detection_proposals": len(responses["detection_proposals"].json()),
        "dataset_exports": len(responses["dataset_exports"].json()),
    }


def add_stream_validation_records(repository: ProductRepository) -> None:
    with repository.session_factory() as session:
        with session.begin():
            session.add(
                CameraSourceModel(
                    id=OTHER_SOURCE_ID,
                    name="Other folder source",
                    kind=SourceKind.webhook.value,
                    status=SourceStatus.connected.value,
                    description="Other source for folder batch dry-run validation.",
                )
            )
            session.add(
                StreamModel(
                    id=OTHER_STREAM_ID,
                    source_id=OTHER_SOURCE_ID,
                    name="Other stream",
                    description="Belongs to another source.",
                    is_live=False,
                )
            )
            session.add(
                ZoneModel(
                    id=OTHER_ZONE_ID,
                    stream_id=OTHER_STREAM_ID,
                    name="Other feeder",
                    zone_type="feeder",
                    polygon_json="[]",
                    is_active=True,
                )
            )
            session.add(
                ZoneModel(
                    id=PRIVACY_ZONE_ID,
                    stream_id=STREAM_ID,
                    name="Folder batch privacy zone",
                    zone_type="privacy",
                    polygon_json="[]",
                    is_active=True,
                )
            )


def add_non_folder_media_asset(repository: ProductRepository, tmp_path: Path) -> str:
    media_id = "media-asset-non-folder-batch"
    local_path = tmp_path / "manual-media.jpg"
    write_file(local_path, b"manual media bytes")
    with repository.session_factory() as session:
        with session.begin():
            session.add(
                MediaAssetModel(
                    id=media_id,
                    source_id=SOURCE_ID,
                    stream_id=STREAM_ID,
                    filename="manual-media.jpg",
                    content_type="image/jpeg",
                    media_type="image",
                    local_path=str(local_path),
                    original_filename="manual-media.jpg",
                    file_size_bytes=local_path.stat().st_size,
                    created_at=datetime.now(UTC),
                    notes="Manual media fixture, not folder import provenance.",
                )
            )
    return media_id


def point_media_asset_to_missing_file(
    repository: ProductRepository,
    media_asset_id: str,
    tmp_path: Path,
) -> None:
    with repository.session_factory() as session:
        with session.begin():
            asset = session.get(MediaAssetModel, media_asset_id)
            assert asset is not None
            asset.local_path = str(tmp_path / "missing-media" / f"{media_asset_id}.jpg")


async def test_folder_import_evidence_batch_dry_run_requires_selection(
    client: httpx.AsyncClient,
) -> None:
    response = await client.post("/api/folder-import/evidence/dry-run", json={})

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "Choose MediaAssets, Source, or Stream for this folder evidence dry run."
    )


async def test_folder_import_evidence_batch_dry_run_by_media_ids_is_read_only(
    client: httpx.AsyncClient,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    media_asset_ids = await import_folder_media_assets(client, tmp_path, ["bird-a.jpg", "bird-b.jpg"])
    before = await product_counts(client)

    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("Folder evidence dry-run must not call model runtimes")

    monkeypatch.setattr(
        "mockingbird.repository.product_repository.run_local_image_detector",
        fail_if_called,
    )
    monkeypatch.setattr(
        "mockingbird.repository.product_repository.run_megadetector_on_image",
        fail_if_called,
    )

    response = await client.post(
        "/api/folder-import/evidence/dry-run",
        json={"media_asset_ids": media_asset_ids},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["dry_run"] is True
    assert body["creates_motion_evidence"] is False
    assert body["creates_events"] is False
    assert body["creates_visits"] is False
    assert body["creates_truth"] is False
    assert body["total_items"] == 2
    assert body["eligible_count"] == 2
    assert body["would_create_count"] == 2
    assert body["duplicate_skipped_count"] == 0
    assert body["skipped_count"] == 0
    assert {item["media_asset_id"] for item in body["items"]} == set(media_asset_ids)
    assert all(item["would_create_motion_evidence"] is True for item in body["items"])
    assert all(item["zone_id"] == FEEDER_ZONE_ID for item in body["items"])
    assert await product_counts(client) == before


async def test_folder_import_evidence_batch_dry_run_by_source_or_stream_uses_existing_assets(
    client: httpx.AsyncClient,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    media_asset_ids = await import_folder_media_assets(client, tmp_path, ["bird-a.jpg", "bird-b.jpg"])

    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("Folder evidence dry-run must not rescan folders")

    monkeypatch.setattr(
        "mockingbird.repository.product_repository.folder_import_preview.preview_folder_import",
        fail_if_called,
    )

    source_response = await client.post(
        "/api/folder-import/evidence/dry-run",
        json={"source_id": SOURCE_ID},
    )
    stream_response = await client.post(
        "/api/folder-import/evidence/dry-run",
        json={"stream_id": STREAM_ID},
    )

    assert source_response.status_code == 200
    assert stream_response.status_code == 200
    assert {item["media_asset_id"] for item in source_response.json()["items"]} == set(
        media_asset_ids
    )
    assert {item["media_asset_id"] for item in stream_response.json()["items"]} == set(
        media_asset_ids
    )


async def test_folder_import_evidence_batch_dry_run_reports_duplicates_without_creating_more(
    client: httpx.AsyncClient,
    tmp_path: Path,
) -> None:
    [media_asset_id] = await import_folder_media_assets(client, tmp_path, ["bird.jpg"])
    created = await client.post(
        f"/api/media/{media_asset_id}/create-motion-evidence",
        json={"zone_id": FEEDER_ZONE_ID},
    )
    assert created.status_code == 201
    evidence_id = created.json()["motion_evidence_id"]
    before = await product_counts(client)

    duplicate_response = await client.post(
        "/api/folder-import/evidence/dry-run",
        json={"media_asset_ids": [media_asset_id]},
    )
    allowed_response = await client.post(
        "/api/folder-import/evidence/dry-run",
        json={"media_asset_ids": [media_asset_id], "duplicate_policy": "allow_duplicate"},
    )

    assert duplicate_response.status_code == 200
    duplicate_body = duplicate_response.json()
    assert duplicate_body["would_create_count"] == 0
    assert duplicate_body["duplicate_skipped_count"] == 1
    assert duplicate_body["items"][0]["skip_reason"] == "duplicate_evidence"
    assert duplicate_body["items"][0]["existing_motion_evidence_id"] == evidence_id

    assert allowed_response.status_code == 200
    allowed_body = allowed_response.json()
    assert allowed_body["would_create_count"] == 1
    assert allowed_body["duplicate_skipped_count"] == 0
    assert allowed_body["items"][0]["existing_motion_evidence_id"] == evidence_id
    assert await product_counts(client) == before


async def test_folder_import_evidence_batch_dry_run_reports_skip_reasons(
    client: httpx.AsyncClient,
    isolated_repository: ProductRepository,
    tmp_path: Path,
) -> None:
    add_stream_validation_records(isolated_repository)
    missing_file_id, mismatch_id = await import_folder_media_assets(
        client,
        tmp_path,
        ["missing-file.jpg", "mismatch.jpg"],
    )
    point_media_asset_to_missing_file(isolated_repository, missing_file_id, tmp_path)
    non_folder_id = add_non_folder_media_asset(isolated_repository, tmp_path)
    before = await product_counts(client)

    mixed_response = await client.post(
        "/api/folder-import/evidence/dry-run",
        json={"media_asset_ids": [missing_file_id, non_folder_id, "media-asset-unknown"]},
    )
    mismatch_response = await client.post(
        "/api/folder-import/evidence/dry-run",
        json={"media_asset_ids": [mismatch_id], "stream_id": OTHER_STREAM_ID},
    )

    assert mixed_response.status_code == 200
    reasons = {
        item["media_asset_id"]: item["skip_reason"] for item in mixed_response.json()["items"]
    }
    assert reasons[missing_file_id] == "missing_local_file"
    assert reasons[non_folder_id] == "not_folder_import_media"
    assert reasons["media-asset-unknown"] == "unknown_media_asset"

    assert mismatch_response.status_code == 200
    assert mismatch_response.json()["items"][0]["skip_reason"] == "stream_source_mismatch"
    assert await product_counts(client) == before


async def test_folder_import_evidence_batch_dry_run_reports_zone_blocks(
    client: httpx.AsyncClient,
    isolated_repository: ProductRepository,
    tmp_path: Path,
) -> None:
    add_stream_validation_records(isolated_repository)
    [media_asset_id] = await import_folder_media_assets(client, tmp_path, ["bird.jpg"])
    before = await product_counts(client)

    invalid = await client.post(
        "/api/folder-import/evidence/dry-run",
        json={"media_asset_ids": [media_asset_id], "zone_id": "zone-missing"},
    )
    privacy = await client.post(
        "/api/folder-import/evidence/dry-run",
        json={"media_asset_ids": [media_asset_id], "zone_id": PRIVACY_ZONE_ID},
    )
    ignore = await client.post(
        "/api/folder-import/evidence/dry-run",
        json={"media_asset_ids": [media_asset_id], "zone_id": IGNORE_ZONE_ID},
    )

    assert invalid.status_code == 200
    assert privacy.status_code == 200
    assert ignore.status_code == 200
    assert invalid.json()["items"][0]["skip_reason"] == "invalid_zone"
    assert privacy.json()["items"][0]["skip_reason"] == "privacy_zone"
    assert ignore.json()["items"][0]["skip_reason"] == "ignore_zone"
    assert await product_counts(client) == before


async def test_folder_import_evidence_batch_dry_run_truncates_max_items(
    client: httpx.AsyncClient,
    tmp_path: Path,
) -> None:
    media_asset_ids = await import_folder_media_assets(
        client,
        tmp_path,
        ["bird-a.jpg", "bird-b.jpg", "bird-c.jpg"],
    )
    before = await product_counts(client)

    response = await client.post(
        "/api/folder-import/evidence/dry-run",
        json={"media_asset_ids": media_asset_ids, "max_items": 2},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total_items"] == 3
    assert body["would_create_count"] == 2
    assert body["skipped_count"] == 1
    assert body["items"][2]["media_asset_id"] == media_asset_ids[2]
    assert body["items"][2]["skip_reason"] == "max_items_exceeded"
    assert body["warnings"] == ["Dry run truncated at 2 items."]
    assert await product_counts(client) == before
