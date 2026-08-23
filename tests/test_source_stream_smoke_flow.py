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
from tests.conftest import LegacyAuthenticatedTestClient

pytestmark = pytest.mark.anyio

SOURCE_ID = "source-backyard-demo"
STREAM_ID = "stream-backyard-feeder"
FEEDER_ZONE_ID = "zone-feeder"
PRIVATE_PREVIEW_URL = "http://192.168.1.50/camera/path/still.jpg"

MODEL_ARTIFACT_EXTENSIONS = {
    ".onnx",
    ".pt",
    ".pth",
    ".weights",
    ".engine",
    ".ckpt",
}
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
    def __init__(self, content: bytes = b"phase-12a-image-bytes") -> None:
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
    async with LegacyAuthenticatedTestClient(transport=transport, base_url="http://testserver") as api_client:
        yield api_client


async def configure_external_url(client: httpx.AsyncClient) -> None:
    response = await client.patch(
        f"/api/sources/{SOURCE_ID}/provider-configuration",
        json={"provider_key": "external_url", "config": {"url": PRIVATE_PREVIEW_URL}},
    )
    assert response.status_code == 200
    configuration = response.json()
    assert configuration["provider_key"] == "external_url"
    assert configuration["configured_fields"] == ["url"]
    assert configuration["supports_live_playback"] is False
    assert configuration["supports_zone_editing"] is True


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


def fail_if_external_url_fetch_is_called(*args, **kwargs) -> None:  # noqa: ANN002, ANN003
    raise AssertionError("Read-only status/detail routes must not fetch external URLs")


def fail_if_detector_runtime_is_called(*args, **kwargs) -> None:  # noqa: ANN002, ANN003
    raise AssertionError("Source/stream smoke flow must not call detector runtimes")


async def assert_source_stream_status_is_preview_ready(client: httpx.AsyncClient) -> None:
    connection_response = await client.get(f"/api/sources/{SOURCE_ID}/connection")
    setup_response = await client.get(f"/api/sources/{SOURCE_ID}/setup-review")
    playback_response = await client.get(f"/api/streams/{STREAM_ID}/playback")

    assert [response.status_code for response in (connection_response, setup_response)] == [
        200,
        200,
    ]
    assert playback_response.status_code == 200

    connection = connection_response.json()
    assert connection["status"] == "configured"
    assert connection["provider_kind"] == "external_url"
    assert connection["adapter_key"] == "external_url"
    assert connection["configured_fields"] == ["url"]
    assert connection["supports_live_playback"] is False
    assert connection["supports_zone_editing"] is True
    assert connection["stream_ids"] == [STREAM_ID]

    setup = setup_response.json()
    assert setup["provider_key"] == "external_url"
    assert setup["readiness_level"] == "metadata_ready"
    assert setup["supports_live_playback"] is False
    assert setup["supports_zone_editing"] is True
    assert setup["configured_fields"] == ["url"]
    assert setup["stream_count"] == 1
    assert setup["streams"][0]["stream_id"] == STREAM_ID
    assert setup["streams"][0]["supports_live_playback"] is False
    assert setup["streams"][0]["supports_zone_editing"] is True
    preview_step = next(step for step in setup["steps"] if step["key"] == "external_url_preview")
    assert preview_step["status"] == "available"
    assert "creates no truth" in preview_step["message"]

    playback = playback_response.json()
    assert playback["stream_id"] == STREAM_ID
    assert playback["source_id"] == SOURCE_ID
    assert playback["supports_live_playback"] is False
    assert playback["supports_zone_editing"] is True
    assert playback["playback_kind"] in {"demo_panel", "placeholder", "external_url", "media_preview"}
    assert playback["preview_media_asset_id"] is None
    assert playback["preview_url"] is None


def assert_no_generated_artifacts_outside_media_root(
    tmp_path: Path,
    media_root: Path,
    expected_saved_media_path: Path,
) -> None:
    media_root = media_root.resolve()
    expected_saved_media_path = expected_saved_media_path.resolve()
    assert expected_saved_media_path.is_relative_to(media_root)

    model_or_manifest_artifacts = [
        path
        for path in tmp_path.rglob("*")
        if path.is_file()
        and (path.name in MANIFEST_FILENAMES or path.suffix.lower() in MODEL_ARTIFACT_EXTENSIONS)
    ]
    assert model_or_manifest_artifacts == []

    media_files = [
        path.resolve()
        for path in tmp_path.rglob("*")
        if path.is_file() and path.suffix.lower() in MEDIA_EXTENSIONS
    ]
    assert media_files == [expected_saved_media_path]


async def test_source_stream_status_routes_do_not_fetch_external_url(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await configure_external_url(client)
    before = await product_counts(client)
    monkeypatch.setattr(
        external_url_preview,
        "fetch_external_url_preview",
        fail_if_external_url_fetch_is_called,
    )

    await assert_source_stream_status_is_preview_ready(client)

    assert await product_counts(client) == before


async def test_external_url_to_correction_truth_smoke_flow(
    client: httpx.AsyncClient,
    isolated_repository: ProductRepository,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    before_configuration = await product_counts(client)
    before_truth = await dataset_truth_counts(client)
    before_cardinal_count = await analytics_species_count(client, "northern_cardinal")

    await configure_external_url(client)
    assert await product_counts(client) == before_configuration

    monkeypatch.setattr(
        external_url_preview,
        "fetch_external_url_preview",
        fail_if_external_url_fetch_is_called,
    )
    await assert_source_stream_status_is_preview_ready(client)
    assert await product_counts(client) == before_configuration

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
        {
            "url": PRIVATE_PREVIEW_URL,
            "timeout_seconds": 1.5,
            "max_bytes": 1024,
        }
    ]
    assert await product_counts(client) == before_configuration
    assert await dataset_truth_counts(client) == before_truth
    assert await analytics_species_count(client, "northern_cardinal") == before_cardinal_count

    save_response = await client.post(
        f"/api/sources/{SOURCE_ID}/external-url/preview/save",
        json={
            "stream_id": STREAM_ID,
            "timeout_seconds": 2.0,
            "max_bytes": 2048,
            "note": "Phase 12A smoke saved preview.",
        },
    )

    assert save_response.status_code == 200
    saved = save_response.json()
    assert saved["status"] == "saved"
    assert saved["source_id"] == SOURCE_ID
    assert saved["stream_id"] == STREAM_ID
    assert saved["media_asset_id"].startswith("media-asset-")
    assert saved["content_type"] == "image/jpeg"
    assert saved["bytes_written"] == len(fetch_stub.content)
    assert saved["creates_event"] is False
    assert saved["creates_visit"] is False
    assert saved["creates_truth"] is False
    assert fetch_stub.calls[-1] == {
        "url": PRIVATE_PREVIEW_URL,
        "timeout_seconds": 2.0,
        "max_bytes": 2048,
    }
    assert_count_delta(
        before_configuration,
        await product_counts(client),
        media_assets=1,
    )
    assert await dataset_truth_counts(client) == before_truth

    media_response = await client.get(f"/api/media/{saved['media_asset_id']}")
    assert media_response.status_code == 200
    media_asset = media_response.json()
    saved_path = Path(media_asset["local_path"]).resolve()
    assert saved_path.is_relative_to(isolated_repository.media_root.resolve())
    assert saved_path.read_bytes() == fetch_stub.content
    assert "Creates no Events, Visits, ReviewLabels, or truth." in media_asset["notes"]

    monkeypatch.setattr(
        external_url_preview,
        "fetch_external_url_preview",
        fail_if_external_url_fetch_is_called,
    )
    monkeypatch.setattr(
        "mockingbird.repository.product_repository.run_local_image_detector",
        fail_if_detector_runtime_is_called,
    )
    monkeypatch.setattr(
        "mockingbird.repository.product_repository.run_megadetector_on_image",
        fail_if_detector_runtime_is_called,
    )

    evidence_response = await client.post(
        f"/api/media/{saved['media_asset_id']}/create-motion-evidence",
        json={
            "zone_id": FEEDER_ZONE_ID,
            "reason": "Visible outdoor activity in explicit saved preview.",
            "note": "Phase 12A smoke evidence.",
        },
    )

    assert evidence_response.status_code == 201
    evidence_result = evidence_response.json()
    assert evidence_result["media_asset_id"] == saved["media_asset_id"]
    assert evidence_result["source_id"] == SOURCE_ID
    assert evidence_result["stream_id"] == STREAM_ID
    assert evidence_result["zone_id"] == FEEDER_ZONE_ID
    assert evidence_result["status"] == "pending"
    assert evidence_result["creates_event"] is False
    assert evidence_result["creates_visit"] is False
    assert evidence_result["creates_truth"] is False
    assert_count_delta(
        before_configuration,
        await product_counts(client),
        media_assets=1,
        motion_evidence=1,
    )
    assert await dataset_truth_counts(client) == before_truth

    evidence_id = evidence_result["motion_evidence_id"]
    list_evidence_response = await client.get("/api/motion/evidence")
    detail_evidence_response = await client.get(f"/api/motion/evidence/{evidence_id}")
    assert [list_evidence_response.status_code, detail_evidence_response.status_code] == [200, 200]
    evidence_detail = detail_evidence_response.json()
    assert evidence_detail["snapshot_media_asset_id"] == saved["media_asset_id"]
    assert evidence_detail["status"] == "pending"
    assert evidence_detail["promoted_event_id"] is None
    assert evidence_detail["promoted_visit_id"] is None
    assert evidence_detail["scoring_config"]["source"] == "saved_preview_media_asset"

    promote_response = await client.post(
        f"/api/motion/evidence/{evidence_id}/promote",
        json={
            "event_title": "Phase 12A saved preview activity",
            "visit_label_hint": "unknown_animal",
            "notes": "Promoted by explicit smoke-test action.",
        },
    )

    assert promote_response.status_code == 200
    promoted = promote_response.json()
    event_id = promoted["event_id"]
    visit_id = promoted["visit_id"]
    assert event_id is not None
    assert visit_id is not None
    assert promoted["evidence"]["status"] == "promoted"
    assert promoted["evidence"]["snapshot_media_asset_id"] == saved["media_asset_id"]
    assert promoted["evidence"]["promoted_event_id"] == event_id
    assert promoted["evidence"]["promoted_visit_id"] == visit_id
    assert_count_delta(
        before_configuration,
        await product_counts(client),
        media_assets=1,
        motion_evidence=1,
        events=1,
        visits=1,
    )
    assert await dataset_truth_counts(client) == before_truth
    assert await analytics_species_count(client, "northern_cardinal") == before_cardinal_count

    pre_correction_export_response = await client.post(
        "/api/dataset-exports",
        json={"name": "Primary flow before correction"},
    )
    assert pre_correction_export_response.status_code == 201
    pre_correction_manifest = pre_correction_export_response.json()["manifest"]
    assert all(record["visit_id"] != visit_id for record in pre_correction_manifest["records"])
    assert pre_correction_manifest["skipped_reasons"]["needs_review"] >= 1
    assert_count_delta(
        before_configuration,
        await product_counts(client),
        media_assets=1,
        motion_evidence=1,
        events=1,
        visits=1,
        dataset_exports=1,
    )

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
    assert event_detail["media_asset"]["id"] == saved["media_asset_id"]
    assert event_detail["review_labels"] == []
    assert event_detail["dataset_ready"] is False
    assert visit_detail["visit"]["review_status"] == "needs_review"
    assert visit_detail["visit"]["reviewed_label"] is None
    assert visit_detail["media_asset"]["id"] == saved["media_asset_id"]
    assert visit_detail["review_labels"] == []
    assert visit_detail["dataset_ready"] is False
    assert any(item["visit_id"] == visit_id for item in review_queue_response.json())

    correction_response = await client.post(
        "/api/review-labels",
        json={"review_origin": "human", 
            "target_type": "visit",
            "target_id": visit_id,
            "label": "Northern Cardinal",
            "notes": "Phase 12A correction truth.",
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
        before_configuration,
        await product_counts(client),
        media_assets=1,
        motion_evidence=1,
        events=1,
        visits=1,
        review_labels=1,
        dataset_exports=1,
    )
    assert await dataset_truth_counts(client) == {
        "reviewed_record_count": before_truth["reviewed_record_count"] + 1,
        "export_ready_count": before_truth["export_ready_count"] + 1,
    }

    corrected_visit_detail_response = await client.get(f"/api/visits/{visit_id}/detail")
    corrected_event_detail_response = await client.get(f"/api/events/{event_id}/detail")
    corrected_queue_response = await client.get("/api/review-queue")
    assert [
        corrected_visit_detail_response.status_code,
        corrected_event_detail_response.status_code,
        corrected_queue_response.status_code,
    ] == [200, 200, 200]
    corrected_visit_detail = corrected_visit_detail_response.json()
    corrected_event_detail = corrected_event_detail_response.json()
    assert corrected_visit_detail["visit"]["review_status"] == "reviewed"
    assert corrected_visit_detail["dataset_ready"] is True
    assert corrected_visit_detail["review_labels"][0]["label"] == "northern_cardinal"
    assert corrected_event_detail["event"]["review_status"] == "reviewed"
    assert corrected_event_detail["dataset_ready"] is True
    assert corrected_event_detail["review_labels"][0]["label"] == "northern_cardinal"
    assert all(item["visit_id"] != visit_id for item in corrected_queue_response.json())

    bird_log_labels_response = await client.get("/api/review-labels")
    assert bird_log_labels_response.status_code == 200
    bird_log_label = next(
        label
        for label in reversed(bird_log_labels_response.json())
        if label["target_type"] == "visit" and label["target_id"] == visit_id
    )
    assert bird_log_label["label"] == "northern_cardinal"
    assert corrected_visit_detail["media_asset"]["id"] == saved["media_asset_id"]

    reviewed_export_response = await client.post(
        "/api/dataset-exports",
        json={"name": "Primary flow after correction"},
    )
    assert reviewed_export_response.status_code == 201
    reviewed_manifest = reviewed_export_response.json()["manifest"]
    reviewed_record = next(
        record for record in reviewed_manifest["records"] if record["visit_id"] == visit_id
    )
    assert reviewed_record["label"] == "northern_cardinal"
    assert reviewed_record["reviewed"] is True
    assert reviewed_record["dataset_ready"] is True
    assert reviewed_record["source_id"] == SOURCE_ID
    assert reviewed_record["stream_id"] == STREAM_ID
    assert reviewed_record["zone_id"] == FEEDER_ZONE_ID
    assert reviewed_record["media_path"] == media_asset["local_path"]
    assert_count_delta(
        before_configuration,
        await product_counts(client),
        media_assets=1,
        motion_evidence=1,
        events=1,
        visits=1,
        review_labels=1,
        dataset_exports=2,
    )

    assert_no_generated_artifacts_outside_media_root(
        tmp_path,
        isolated_repository.media_root,
        saved_path,
    )
