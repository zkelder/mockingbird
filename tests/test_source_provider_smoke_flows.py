from __future__ import annotations

import base64
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest

from mockingbird.api.main import app, configure_repository
from mockingbird.repository.product_repository import ProductRepository
from mockingbird.source_providers import external_url_preview
from mockingbird.source_providers.external_url_preview import ExternalUrlPreviewFetchResult

pytestmark = pytest.mark.anyio

SOURCE_ID = "source-backyard-demo"
STREAM_ID = "stream-backyard-feeder"
FEEDER_ZONE_ID = "zone-feeder"
PRIVATE_PREVIEW_URL = "http://192.168.1.50/camera/path/still.jpg"
MODEL_ARTIFACT_EXTENSIONS = {".onnx", ".pt", ".pth", ".weights", ".engine", ".ckpt"}
MEDIA_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".mp4", ".mov"}
MANIFEST_FILENAMES = {
    "manifest.jsonl",
    "manifest.csv",
    "labels.txt",
    "taxonomy.json",
    "skipped_records.jsonl",
    "summary.json",
    "classifier-training-manifest-preview.json",
}


class StubExternalPreviewFetch:
    def __init__(self, content: bytes = b"phase-14a-external-url-image") -> None:
        self.content = content
        self.calls: list[dict[str, Any]] = []

    def __call__(
        self,
        url: str,
        *,
        timeout_seconds: float | None,
        max_bytes: int | None,
    ) -> ExternalUrlPreviewFetchResult:
        self.calls.append(
            {
                "url": url,
                "timeout_seconds": timeout_seconds,
                "max_bytes": max_bytes,
            }
        )
        encoded = base64.b64encode(self.content).decode("ascii")
        return ExternalUrlPreviewFetchResult(
            status="available",
            message="Stubbed still-image preview fetched explicitly.",
            fetched_at=datetime(2026, 1, 2, tzinfo=UTC),
            content_type="image/jpeg",
            content_length=len(self.content),
            bytes_read=len(self.content),
            preview_data_url=f"data:image/jpeg;base64,{encoded}",
            fetched_bytes=self.content,
        )


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


def write_file(path: Path, content: bytes = b"image bytes") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def fail_if_external_url_fetch_is_called(*_args, **_kwargs) -> None:
    raise AssertionError("Read-only status routes must not fetch external URLs")


def fail_if_folder_scan_runs(*_args, **_kwargs) -> None:
    raise AssertionError("Read-only status routes must not scan folders")


def fail_if_detector_runtime_is_called(*_args, **_kwargs) -> None:
    raise AssertionError("Provider smoke flows must not call detector runtimes")


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


def assert_count_delta(
    before: dict[str, int],
    after: dict[str, int],
    **expected_delta: int,
) -> None:
    for key, before_value in before.items():
        assert after[key] == before_value + expected_delta.get(key, 0), key


async def dataset_truth_counts(client: httpx.AsyncClient) -> dict[str, int]:
    response = await client.get("/api/dataset-coverage/summary")
    assert response.status_code == 200
    coverage = response.json()
    return {
        "reviewed_record_count": coverage["reviewed_record_count"],
        "export_ready_count": coverage["export_ready_count"],
    }


async def analytics_species_count(client: httpx.AsyncClient, label: str) -> int:
    response = await client.get("/api/analytics/summary")
    assert response.status_code == 200
    return response.json()["species_counts"].get(label, 0)


async def configure_external_url(client: httpx.AsyncClient) -> None:
    response = await client.patch(
        f"/api/sources/{SOURCE_ID}/provider-configuration",
        json={"provider_key": "external_url", "config": {"url": PRIVATE_PREVIEW_URL}},
    )
    assert response.status_code == 200
    configuration = response.json()
    assert configuration["provider_key"] == "external_url"
    assert configuration["supports_live_playback"] is False
    assert configuration["supports_zone_editing"] is True


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
    configuration = response.json()
    assert configuration["provider_key"] == "folder_import_future"
    assert configuration["supports_live_playback"] is False
    assert configuration["supports_zone_editing"] is True
    assert str(folder) not in str(configuration)


async def assert_external_status_is_honest(client: httpx.AsyncClient) -> None:
    responses = [
        await client.get(f"/api/sources/{SOURCE_ID}/connection"),
        await client.get(f"/api/sources/{SOURCE_ID}/setup-review"),
        await client.get(f"/api/streams/{STREAM_ID}/playback"),
    ]
    assert all(response.status_code == 200 for response in responses)

    connection, setup, playback = [response.json() for response in responses]
    assert connection["status"] == "configured"
    assert connection["provider_kind"] == "external_url"
    assert connection["adapter_key"] == "external_url"
    assert connection["supports_live_playback"] is False
    assert connection["supports_zone_editing"] is True
    assert PRIVATE_PREVIEW_URL not in str(connection)

    assert setup["provider_key"] == "external_url"
    assert setup["readiness_level"] == "metadata_ready"
    assert setup["supports_live_playback"] is False
    assert setup["supports_zone_editing"] is True
    assert setup["streams"][0]["supports_live_playback"] is False
    assert PRIVATE_PREVIEW_URL not in str(setup)

    assert playback["stream_id"] == STREAM_ID
    assert playback["source_id"] == SOURCE_ID
    assert playback["supports_live_playback"] is False
    assert playback["supports_zone_editing"] is True
    assert playback["preview_media_asset_id"] is None
    assert playback["preview_url"] is None


async def assert_folder_status_is_honest(client: httpx.AsyncClient, folder: Path) -> None:
    responses = [
        await client.get(f"/api/sources/{SOURCE_ID}/connection"),
        await client.get(f"/api/sources/{SOURCE_ID}/setup-review"),
        await client.get(f"/api/streams/{STREAM_ID}/playback"),
    ]
    assert all(response.status_code == 200 for response in responses)

    connection, setup, playback = [response.json() for response in responses]
    assert connection["status"] == "configured"
    assert connection["provider_kind"] == "future_adapter"
    assert connection["adapter_key"] == "folder_import_future"
    assert connection["supports_live_playback"] is False
    assert connection["supports_zone_editing"] is True

    assert setup["provider_key"] == "folder_import_future"
    assert setup["supports_live_playback"] is False
    assert setup["supports_zone_editing"] is True
    folder_step = next(step for step in setup["steps"] if step["key"] == "folder_import_preview")
    assert folder_step["status"] == "available"

    assert playback["stream_id"] == STREAM_ID
    assert playback["source_id"] == SOURCE_ID
    assert playback["playback_kind"] == "placeholder"
    assert playback["supports_live_playback"] is False
    assert playback["supports_zone_editing"] is True
    assert playback["preview_media_asset_id"] is None
    assert playback["preview_url"] is None
    assert str(folder) not in str(connection)
    assert str(folder) not in str(setup)
    assert str(folder) not in str(playback)


async def assert_media_under_root(
    client: httpx.AsyncClient,
    media_asset_id: str,
    media_root: Path,
) -> Path:
    response = await client.get(f"/api/media/{media_asset_id}")
    assert response.status_code == 200
    media_asset = response.json()
    local_path = Path(media_asset["local_path"]).resolve()
    assert local_path.is_file()
    assert local_path.is_relative_to(media_root.resolve())
    return local_path


def assert_no_model_or_dataset_artifacts(tmp_path: Path) -> None:
    artifacts = [
        path
        for path in tmp_path.rglob("*")
        if path.is_file()
        and (path.suffix.lower() in MODEL_ARTIFACT_EXTENSIONS or path.name in MANIFEST_FILENAMES)
    ]
    assert artifacts == []


def assert_media_files_are_expected(tmp_path: Path, expected_paths: set[Path]) -> None:
    actual_paths = {
        path.resolve()
        for path in tmp_path.rglob("*")
        if path.is_file() and path.suffix.lower() in MEDIA_EXTENSIONS
    }
    assert actual_paths == {path.resolve() for path in expected_paths}


def block_detector_runtimes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "mockingbird.repository.product_repository.run_local_image_detector",
        fail_if_detector_runtime_is_called,
    )
    monkeypatch.setattr(
        "mockingbird.repository.product_repository.run_megadetector_on_image",
        fail_if_detector_runtime_is_called,
    )


async def promote_and_correct(
    client: httpx.AsyncClient,
    evidence_id: str,
    before_counts: dict[str, int],
    before_truth: dict[str, int],
    *,
    media_assets: int,
    motion_evidence: int,
) -> None:
    before_cardinal_count = await analytics_species_count(client, "northern_cardinal")

    promote_response = await client.post(
        f"/api/motion/evidence/{evidence_id}/promote",
        json={
            "event_title": "Phase 14A provider smoke activity",
            "visit_label_hint": "unknown_animal",
            "notes": "Promoted by explicit provider smoke-test action.",
        },
    )
    assert promote_response.status_code == 200
    promoted = promote_response.json()
    event_id = promoted["event_id"]
    visit_id = promoted["visit_id"]
    assert promoted["evidence"]["status"] == "promoted"
    assert promoted["evidence"]["promoted_event_id"] == event_id
    assert promoted["evidence"]["promoted_visit_id"] == visit_id
    assert_count_delta(
        before_counts,
        await product_counts(client),
        media_assets=media_assets,
        motion_evidence=motion_evidence,
        events=1,
        visits=1,
    )
    assert await dataset_truth_counts(client) == before_truth

    event_detail_response = await client.get(f"/api/events/{event_id}/detail")
    visit_detail_response = await client.get(f"/api/visits/{visit_id}/detail")
    review_queue_response = await client.get("/api/review-queue")
    assert [
        event_detail_response.status_code,
        visit_detail_response.status_code,
        review_queue_response.status_code,
    ] == [200, 200, 200]
    event_detail = event_detail_response.json()
    visit_detail = visit_detail_response.json()
    assert event_detail["event"]["review_status"] == "needs_review"
    assert event_detail["review_labels"] == []
    assert event_detail["dataset_ready"] is False
    assert visit_detail["visit"]["review_status"] == "needs_review"
    assert visit_detail["visit"]["reviewed_label"] is None
    assert visit_detail["review_labels"] == []
    assert visit_detail["dataset_ready"] is False
    assert any(item["visit_id"] == visit_id for item in review_queue_response.json())

    correction_response = await client.post(
        "/api/review-labels",
        json={"review_origin": "human", 
            "target_type": "visit",
            "target_id": visit_id,
            "label": "Northern Cardinal",
            "notes": "Phase 14A correction truth.",
        },
    )
    assert correction_response.status_code == 201
    correction = correction_response.json()
    assert correction["review_label"]["target_type"] == "visit"
    assert correction["review_label"]["target_id"] == visit_id
    assert correction["review_label"]["label"] == "northern_cardinal"
    assert correction["visit"]["review_status"] == "reviewed"
    assert correction["visit"]["reviewed_label"] == "northern_cardinal"
    assert correction["analytics"]["species_counts"]["northern_cardinal"] == (
        before_cardinal_count + 1
    )
    assert_count_delta(
        before_counts,
        await product_counts(client),
        media_assets=media_assets,
        motion_evidence=motion_evidence,
        events=1,
        visits=1,
        review_labels=1,
    )
    assert await dataset_truth_counts(client) == {
        "reviewed_record_count": before_truth["reviewed_record_count"] + 1,
        "export_ready_count": before_truth["export_ready_count"] + 1,
    }


async def test_external_url_provider_smoke_flow_preserves_truth_boundaries(
    client: httpx.AsyncClient,
    isolated_repository: ProductRepository,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    before = await product_counts(client)
    before_truth = await dataset_truth_counts(client)

    await configure_external_url(client)
    assert await product_counts(client) == before

    monkeypatch.setattr(
        external_url_preview,
        "fetch_external_url_preview",
        fail_if_external_url_fetch_is_called,
    )
    await assert_external_status_is_honest(client)
    assert await product_counts(client) == before

    fetch_stub = StubExternalPreviewFetch()
    monkeypatch.setattr(external_url_preview, "fetch_external_url_preview", fetch_stub)

    preview_response = await client.post(
        f"/api/sources/{SOURCE_ID}/external-url/preview",
        json={"timeout_seconds": 1.5, "max_bytes": 1024},
    )
    assert preview_response.status_code == 200
    preview = preview_response.json()
    assert preview["status"] == "available"
    assert preview["preview_data_url"].startswith("data:image/jpeg;base64,")
    assert preview["supports_live_playback"] is False
    assert preview["creates_media_asset"] is False
    assert preview["creates_truth"] is False
    assert fetch_stub.calls == [
        {"url": PRIVATE_PREVIEW_URL, "timeout_seconds": 1.5, "max_bytes": 1024}
    ]
    assert await product_counts(client) == before
    assert await dataset_truth_counts(client) == before_truth

    save_response = await client.post(
        f"/api/sources/{SOURCE_ID}/external-url/preview/save",
        json={
            "stream_id": STREAM_ID,
            "timeout_seconds": 2.0,
            "max_bytes": 2048,
            "note": "Phase 14A provider smoke saved preview.",
        },
    )
    assert save_response.status_code == 200
    saved = save_response.json()
    assert saved["status"] == "saved"
    assert saved["media_asset_id"].startswith("media-asset-")
    assert saved["creates_event"] is False
    assert saved["creates_visit"] is False
    assert saved["creates_truth"] is False
    assert_count_delta(before, await product_counts(client), media_assets=1)
    assert await dataset_truth_counts(client) == before_truth

    saved_path = await assert_media_under_root(
        client,
        saved["media_asset_id"],
        isolated_repository.media_root,
    )
    assert saved_path.read_bytes() == fetch_stub.content

    monkeypatch.setattr(
        external_url_preview,
        "fetch_external_url_preview",
        fail_if_external_url_fetch_is_called,
    )
    block_detector_runtimes(monkeypatch)

    evidence_response = await client.post(
        f"/api/media/{saved['media_asset_id']}/create-motion-evidence",
        json={
            "zone_id": FEEDER_ZONE_ID,
            "reason": "Visible outdoor activity in explicit saved preview.",
            "note": "Phase 14A provider smoke evidence.",
        },
    )
    assert evidence_response.status_code == 201
    evidence_result = evidence_response.json()
    evidence_id = evidence_result["motion_evidence_id"]
    assert evidence_result["media_asset_id"] == saved["media_asset_id"]
    assert evidence_result["status"] == "pending"
    assert evidence_result["creates_event"] is False
    assert evidence_result["creates_visit"] is False
    assert evidence_result["creates_truth"] is False
    assert_count_delta(before, await product_counts(client), media_assets=1, motion_evidence=1)
    assert await dataset_truth_counts(client) == before_truth

    evidence_detail_response = await client.get(f"/api/motion/evidence/{evidence_id}")
    assert evidence_detail_response.status_code == 200
    evidence_detail = evidence_detail_response.json()
    assert evidence_detail["snapshot_media_asset_id"] == saved["media_asset_id"]
    assert evidence_detail["promoted_event_id"] is None
    assert evidence_detail["promoted_visit_id"] is None
    assert evidence_detail["scoring_config"]["source"] == "saved_preview_media_asset"

    await promote_and_correct(
        client,
        evidence_id,
        before,
        before_truth,
        media_assets=1,
        motion_evidence=1,
    )
    assert_no_model_or_dataset_artifacts(tmp_path)
    assert_media_files_are_expected(tmp_path, {saved_path})


async def test_folder_import_provider_smoke_flow_preserves_truth_boundaries(
    client: httpx.AsyncClient,
    isolated_repository: ProductRepository,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    folder = tmp_path / "trailcam"
    source_files = {
        "bird-a.jpg": b"folder image a",
        "bird-b.png": b"folder image b",
    }
    for name, content in source_files.items():
        write_file(folder / name, content)
    write_file(folder / "clip.mp4", b"not imported")

    before = await product_counts(client)
    before_truth = await dataset_truth_counts(client)

    await configure_folder_source(client, folder)
    assert await product_counts(client) == before

    monkeypatch.setattr(
        "mockingbird.repository.product_repository.folder_import_preview.preview_folder_import",
        fail_if_folder_scan_runs,
    )
    await assert_folder_status_is_honest(client, folder)
    assert await product_counts(client) == before

    monkeypatch.undo()

    preview_response = await client.post(
        f"/api/sources/{SOURCE_ID}/folder-import/preview",
        json={"allowed_extensions": ["jpg", "png"]},
    )
    assert preview_response.status_code == 200
    preview = preview_response.json()
    assert preview["dry_run"] is True
    assert preview["creates_media_assets"] is False
    assert preview["creates_events"] is False
    assert preview["creates_visits"] is False
    assert preview["creates_truth"] is False
    assert {candidate["relative_path"] for candidate in preview["candidates"]} == set(source_files)
    assert {item["relative_path"]: item["reason"] for item in preview["skipped"]} == {
        "clip.mp4": "unsupported_extension"
    }
    assert str(folder) not in str(preview)
    assert await product_counts(client) == before
    assert await dataset_truth_counts(client) == before_truth

    import_response = await client.post(
        f"/api/sources/{SOURCE_ID}/folder-import",
        json={
            "relative_paths": list(source_files),
            "default_stream_id": STREAM_ID,
            "default_zone_id": FEEDER_ZONE_ID,
            "note": "Phase 14A provider smoke folder import.",
        },
    )
    assert import_response.status_code == 201
    imported = import_response.json()
    assert imported["total_imported"] == 2
    assert imported["creates_media_assets"] is True
    assert imported["creates_motion_evidence"] is False
    assert imported["creates_events"] is False
    assert imported["creates_visits"] is False
    assert imported["creates_truth"] is False
    assert_count_delta(before, await product_counts(client), media_assets=2)
    assert await dataset_truth_counts(client) == before_truth

    media_asset_ids = [item["media_asset_id"] for item in imported["imported"]]
    copied_paths = {
        media_asset_id: await assert_media_under_root(
            client,
            media_asset_id,
            isolated_repository.media_root,
        )
        for media_asset_id in media_asset_ids
    }
    for item in imported["imported"]:
        assert copied_paths[item["media_asset_id"]].read_bytes() == source_files[
            item["relative_source_path"]
        ]
    assert all((folder / name).read_bytes() == content for name, content in source_files.items())

    block_detector_runtimes(monkeypatch)

    single_evidence_response = await client.post(
        f"/api/media/{media_asset_ids[0]}/create-motion-evidence",
        json={
            "zone_id": FEEDER_ZONE_ID,
            "reason": "Visible outdoor activity in imported media.",
            "note": "Phase 14A single evidence handoff.",
        },
    )
    assert single_evidence_response.status_code == 201
    single_evidence = single_evidence_response.json()
    assert single_evidence["status"] == "pending"
    assert single_evidence["provenance_kind"] == "folder_import"
    assert single_evidence["creates_event"] is False
    assert single_evidence["creates_visit"] is False
    assert single_evidence["creates_truth"] is False
    assert_count_delta(before, await product_counts(client), media_assets=2, motion_evidence=1)
    assert await dataset_truth_counts(client) == before_truth

    dry_run_response = await client.post(
        "/api/folder-import/evidence/dry-run",
        json={"media_asset_ids": media_asset_ids},
    )
    assert dry_run_response.status_code == 200
    dry_run = dry_run_response.json()
    assert dry_run["dry_run"] is True
    assert dry_run["creates_motion_evidence"] is False
    assert dry_run["creates_events"] is False
    assert dry_run["creates_visits"] is False
    assert dry_run["creates_truth"] is False
    assert dry_run["would_create_count"] == 1
    assert dry_run["duplicate_skipped_count"] == 1
    assert await product_counts(client) == {
        **before,
        "media_assets": before["media_assets"] + 2,
        "motion_evidence": before["motion_evidence"] + 1,
    }

    batch_response = await client.post(
        "/api/folder-import/evidence/batch",
        json={
            "media_asset_ids": media_asset_ids,
            "confirm": True,
            "zone_id": FEEDER_ZONE_ID,
            "reason": "User confirmed eligible folder media.",
            "note": "Phase 14A batch evidence handoff.",
        },
    )
    assert batch_response.status_code == 200
    batch = batch_response.json()
    assert batch["created_count"] == 1
    assert batch["duplicate_skipped_count"] == 1
    assert batch["creates_motion_evidence"] is True
    assert batch["creates_events"] is False
    assert batch["creates_visits"] is False
    assert batch["creates_truth"] is False
    batch_evidence_id = next(item["motion_evidence_id"] for item in batch["items"] if item["created"])
    assert_count_delta(before, await product_counts(client), media_assets=2, motion_evidence=2)
    assert await dataset_truth_counts(client) == before_truth

    detail_response = await client.get(f"/api/motion/evidence/{batch_evidence_id}")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["status"] == "pending"
    assert detail["promoted_event_id"] is None
    assert detail["promoted_visit_id"] is None
    assert detail["scoring_config"]["source"] == "folder_import_media_asset"

    await promote_and_correct(
        client,
        batch_evidence_id,
        before,
        before_truth,
        media_assets=2,
        motion_evidence=2,
    )
    assert_no_model_or_dataset_artifacts(tmp_path)
    assert_media_files_are_expected(
        tmp_path,
        {folder / name for name in source_files}
        | {folder / "clip.mp4"}
        | set(copied_paths.values()),
    )


async def test_source_provider_read_only_status_routes_do_not_run_provider_work(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    await configure_external_url(client)
    before_external = await product_counts(client)
    monkeypatch.setattr(
        external_url_preview,
        "fetch_external_url_preview",
        fail_if_external_url_fetch_is_called,
    )
    for route in (
        f"/api/sources/{SOURCE_ID}/setup-review",
        f"/api/sources/{SOURCE_ID}/connection",
        f"/api/streams/{STREAM_ID}/playback",
    ):
        response = await client.get(route)
        assert response.status_code == 200
    assert await product_counts(client) == before_external

    monkeypatch.undo()

    folder = tmp_path / "trailcam-status"
    write_file(folder / "bird.jpg", b"folder image")
    await configure_folder_source(client, folder)
    before_folder = await product_counts(client)
    monkeypatch.setattr(
        "mockingbird.repository.product_repository.folder_import_preview.preview_folder_import",
        fail_if_folder_scan_runs,
    )
    monkeypatch.setattr(
        "mockingbird.repository.product_repository.folder_import_preview.preview_folder_import_relative_paths",
        fail_if_folder_scan_runs,
    )
    for route in (
        f"/api/sources/{SOURCE_ID}/setup-review",
        f"/api/sources/{SOURCE_ID}/connection",
        f"/api/streams/{STREAM_ID}/playback",
    ):
        response = await client.get(route)
        assert response.status_code == 200
        assert str(folder) not in str(response.json())
    assert await product_counts(client) == before_folder
