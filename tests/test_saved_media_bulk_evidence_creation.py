from __future__ import annotations

import ipaddress
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from mockingbird.api.main import app, configure_repository
from mockingbird.repository import product_repository as product_repository_module
from mockingbird.repository.product_repository import ProductRepository
from mockingbird.source_providers import external_url_preview
from mockingbird.storage.models import MediaAssetModel
from tests.conftest import LegacyAuthenticatedTestClient

pytestmark = pytest.mark.anyio

SOURCE_ID = "source-backyard-demo"
STREAM_ID = "stream-backyard-feeder"
FEEDER_ZONE_ID = "zone-feeder"
PRIVATE_PREVIEW_URL = "http://192.168.1.23/camera/path/still.jpg"


class FakeResponse:
    def __init__(self, body: bytes, headers: dict[str, str] | None = None) -> None:
        self.body = body
        self.headers = headers or {}

    def read(self, size: int = -1) -> bytes:
        return self.body if size < 0 else self.body[:size]

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *args) -> None:  # noqa: ANN002
        return None


class FakeOpener:
    def __init__(self, response: FakeResponse) -> None:
        self.response = response

    def open(self, request, timeout: float):  # noqa: ANN001
        return self.response


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


@pytest.fixture(autouse=True)
def allow_private_lan_dns(monkeypatch: pytest.MonkeyPatch) -> None:
    def resolve(hostname: str):
        try:
            return [ipaddress.ip_address(hostname)]
        except ValueError:
            return [ipaddress.ip_address("192.168.1.23")]

    monkeypatch.setattr(external_url_preview, "_resolve_host_addresses", resolve)


async def configure_external_url(client: httpx.AsyncClient) -> None:
    response = await client.patch(
        f"/api/sources/{SOURCE_ID}/provider-configuration",
        json={"provider_key": "external_url", "config": {"url": PRIVATE_PREVIEW_URL}},
    )
    assert response.status_code == 200


async def save_preview_media_asset(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    body: bytes = b"image-bytes",
) -> str:
    await configure_external_url(client)
    opener = FakeOpener(FakeResponse(body, {"Content-Type": "image/jpeg"}))
    monkeypatch.setattr(external_url_preview, "_build_no_redirect_opener", lambda: opener)

    response = await client.post(
        f"/api/sources/{SOURCE_ID}/external-url/preview/save",
        json={"stream_id": STREAM_ID, "note": "Saved preview for bulk triage."},
    )

    assert response.status_code == 200
    saved = response.json()
    assert saved["status"] == "saved"
    assert saved["media_asset_id"]
    return saved["media_asset_id"]


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
    events = responses["events"].json()
    visits = responses["visits"].json()

    return {
        "events": len(events),
        "visits": len(visits),
        "review_labels": len(responses["review_labels"].json()),
        "motion_evidence": len(responses["motion_evidence"].json()["motion_evidence"]),
        "species_suggestions": len(responses["species_suggestions"].json()["species_suggestions"]),
        "detection_proposals": len(responses["detection_proposals"].json()),
        "dataset_exports": len(responses["dataset_exports"].json()),
        "media_assets": len(responses["media_assets"].json()),
        "reviewed_events": sum(1 for event in events if event["review_status"] == "reviewed"),
        "reviewed_visits": sum(1 for visit in visits if visit["review_status"] == "reviewed"),
    }


async def dataset_truth_counts(client: httpx.AsyncClient) -> dict[str, int]:
    response = await client.get("/api/dataset-coverage/summary")
    assert response.status_code == 200
    summary = response.json()
    return {
        "reviewed_record_count": summary["reviewed_record_count"],
        "export_ready_count": summary["export_ready_count"],
        "needs_review_count": summary["needs_review_count"],
        "reviewed_species_count": summary["reviewed_species_count"],
    }


def assert_only_pending_motion_evidence_changed(
    before: dict[str, int],
    after: dict[str, int],
    expected_created_count: int,
) -> None:
    assert after["motion_evidence"] == before["motion_evidence"] + expected_created_count
    for key in (
        "events",
        "visits",
        "review_labels",
        "species_suggestions",
        "detection_proposals",
        "dataset_exports",
        "media_assets",
        "reviewed_events",
        "reviewed_visits",
    ):
        assert after[key] == before[key]


def install_external_work_tripwires(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_if_called(*args, **kwargs):  # noqa: ANN002, ANN003
        raise AssertionError("Bulk saved-media evidence creation must not fetch or scan sources")

    monkeypatch.setattr(external_url_preview, "fetch_external_url_preview", fail_if_called)
    monkeypatch.setattr(
        "mockingbird.api.main.external_url_preview.fetch_external_url_preview",
        fail_if_called,
    )
    monkeypatch.setattr(
        product_repository_module.folder_import_preview,
        "preview_folder_import",
        fail_if_called,
    )
    monkeypatch.setattr(
        product_repository_module.folder_import_preview,
        "preview_folder_import_relative_paths",
        fail_if_called,
    )
    monkeypatch.setattr(product_repository_module, "classify_webhook_payload", fail_if_called)
    monkeypatch.setattr(product_repository_module, "run_local_image_detector", fail_if_called)
    monkeypatch.setattr(product_repository_module, "run_megadetector_on_image", fail_if_called)


def add_ineligible_video_media_asset(repository: ProductRepository, tmp_path: Path) -> str:
    media_id = "media-asset-bulk-video-ineligible"
    local_path = tmp_path / "ineligible-video.mp4"
    local_path.write_bytes(b"video bytes")

    with repository.session_factory() as session:
        with session.begin():
            session.add(
                MediaAssetModel(
                    id=media_id,
                    source_id=SOURCE_ID,
                    stream_id=STREAM_ID,
                    filename="ineligible-video.mp4",
                    content_type="video/mp4",
                    media_type="video",
                    local_path=str(local_path),
                    original_filename="ineligible-video.mp4",
                    file_size_bytes=local_path.stat().st_size,
                    created_at=datetime.now(UTC),
                    notes="Bulk MotionEvidence ineligible media fixture.",
                )
            )

    return media_id


async def test_bulk_saved_media_create_creates_pending_motion_evidence_only(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first_media_id = await save_preview_media_asset(client, monkeypatch, b"first-image")
    second_media_id = await save_preview_media_asset(client, monkeypatch, b"second-image")
    before_counts = await product_counts(client)
    before_truth = await dataset_truth_counts(client)
    install_external_work_tripwires(monkeypatch)

    response = await client.post(
        "/api/media/bulk-create-motion-evidence",
        json={"media_asset_ids": [first_media_id, second_media_id]},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["requested_count"] == 2
    assert body["succeeded_count"] == 2
    assert body["skipped_count"] == 0
    assert body["failed_count"] == 0

    for result, media_asset_id in zip(body["results"], [first_media_id, second_media_id]):
        assert result["media_asset_id"] == media_asset_id
        assert result["status"] == "succeeded"
        assert result["message"] == (
            "Created pending MotionEvidence from media. "
            "No Events, Visits, labels, or truth were created."
        )
        assert result["created_motion_evidence_id"].startswith("motion-evidence-")

        evidence_response = await client.get(
            f"/api/motion/evidence/{result['created_motion_evidence_id']}",
        )
        assert evidence_response.status_code == 200
        evidence = evidence_response.json()
        assert evidence["snapshot_media_asset_id"] == media_asset_id
        assert evidence["status"] == "pending"
        assert evidence["zone_id"] == FEEDER_ZONE_ID
        assert evidence["promoted_event_id"] is None
        assert evidence["promoted_visit_id"] is None

    assert_only_pending_motion_evidence_changed(
        before_counts,
        await product_counts(client),
        expected_created_count=2,
    )
    assert await dataset_truth_counts(client) == before_truth


async def test_bulk_saved_media_create_skips_duplicate_unknown_and_existing_evidence(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    existing_media_id = await save_preview_media_asset(client, monkeypatch, b"existing-image")
    eligible_media_id = await save_preview_media_asset(client, monkeypatch, b"eligible-image")
    existing_response = await client.post(
        f"/api/media/{existing_media_id}/create-motion-evidence",
        json={},
    )
    assert existing_response.status_code == 201
    before_counts = await product_counts(client)
    before_truth = await dataset_truth_counts(client)
    install_external_work_tripwires(monkeypatch)

    response = await client.post(
        "/api/media/bulk-create-motion-evidence",
        json={
            "media_asset_ids": [
                eligible_media_id,
                eligible_media_id,
                existing_media_id,
                "media-asset-missing",
            ],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["requested_count"] == 4
    assert body["succeeded_count"] == 1
    assert body["skipped_count"] == 3
    assert body["failed_count"] == 0
    assert [result["status"] for result in body["results"]] == [
        "succeeded",
        "skipped",
        "skipped",
        "skipped",
    ]
    assert body["results"][0]["created_motion_evidence_id"].startswith("motion-evidence-")
    assert body["results"][1]["message"] == (
        "Duplicate MediaAsset id in request; only the first occurrence was processed."
    )
    assert body["results"][2]["message"] == (
        "Existing MotionEvidence already references this media. "
        "No duplicate evidence was created."
    )
    assert body["results"][3]["message"] == "MediaAsset was not found."

    assert_only_pending_motion_evidence_changed(
        before_counts,
        await product_counts(client),
        expected_created_count=1,
    )
    assert await dataset_truth_counts(client) == before_truth


async def test_bulk_saved_media_create_skips_ineligible_media_without_truth(
    client: httpx.AsyncClient,
    isolated_repository: ProductRepository,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    media_asset_id = add_ineligible_video_media_asset(isolated_repository, tmp_path)
    before_counts = await product_counts(client)
    before_truth = await dataset_truth_counts(client)
    install_external_work_tripwires(monkeypatch)

    response = await client.post(
        "/api/media/bulk-create-motion-evidence",
        json={"media_asset_ids": [media_asset_id]},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["requested_count"] == 1
    assert body["succeeded_count"] == 0
    assert body["skipped_count"] == 1
    assert body["failed_count"] == 0
    assert body["results"] == [
        {
            "media_asset_id": media_asset_id,
            "status": "skipped",
            "message": "MediaAsset is not eligible for Motion Evidence creation.",
            "created_motion_evidence_id": None,
        }
    ]

    assert_only_pending_motion_evidence_changed(
        before_counts,
        await product_counts(client),
        expected_created_count=0,
    )
    assert await dataset_truth_counts(client) == before_truth
