from pathlib import Path

import httpx
import pytest

from mockingbird.api.main import app, configure_repository
from mockingbird.detectors.local_image_detector import (
    LOCAL_IMAGE_DETECTOR_ID,
    LocalDetectorBox,
    LocalDetectorOutputError,
    LocalDetectorProposal,
    LocalDetectorStatus,
)
from mockingbird.repository import product_repository
from mockingbird.repository.product_repository import ProductRepository

pytestmark = pytest.mark.anyio

SOURCE_ID = "source-backyard-demo"
STREAM_ID = "stream-backyard-feeder"
FEEDER_ZONE_ID = "zone-feeder"
DEMO_ADAPTER_ID = "demo_rule_detector"


@pytest.fixture(autouse=True)
def isolated_repository(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MOCKINGBIRD_LOCAL_DETECTOR_MODEL_PATH", raising=False)
    monkeypatch.delenv("MOCKINGBIRD_LOCAL_DETECTOR_LABELS_PATH", raising=False)
    monkeypatch.delenv("MOCKINGBIRD_MEGADETECTOR_MODEL_PATH", raising=False)
    repository = ProductRepository(
        db_url=f"sqlite:///{tmp_path / 'mockingbird.sqlite3'}",
        media_root=tmp_path / "media",
    )
    configure_repository(repository)
    yield
    configure_repository(None)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as api_client:
        yield api_client


async def import_review_image(
    client: httpx.AsyncClient,
    *,
    title: str = "Review assist image",
    zone_id: str = FEEDER_ZONE_ID,
):
    response = await client.post(
        "/api/media/import",
        data={
            "stream_id": STREAM_ID,
            "zone_id": zone_id,
            "title": title,
            "subject_label": "unknown_bird",
            "species_guess": "unknown_bird",
            "notes": "Local image for Review Queue identification assist.",
        },
        files={"file": ("review-assist.png", b"review assist image bytes", "image/png")},
    )
    assert response.status_code == 201
    return response.json()


async def import_review_video(client: httpx.AsyncClient, *, title: str = "Review assist video"):
    response = await client.post(
        "/api/media/import",
        data={
            "stream_id": STREAM_ID,
            "zone_id": FEEDER_ZONE_ID,
            "title": title,
            "subject_label": "unknown_bird",
            "species_guess": "unknown_bird",
            "notes": "Unsupported video media for Review Queue identification assist.",
        },
        files={"file": ("review-assist.mp4", b"review assist video bytes", "video/mp4")},
    )
    assert response.status_code == 201
    return response.json()


async def truth_snapshot(client: httpx.AsyncClient) -> dict[str, object]:
    status = (await client.get("/api/settings/local-data")).json()
    coverage = (await client.get("/api/dataset-coverage/summary")).json()
    analytics = (await client.get("/api/analytics/summary")).json()
    return {
        "event_count": status["event_count"],
        "visit_count": status["visit_count"],
        "review_label_count": status["review_label_count"],
        "export_ready_count": coverage["export_ready_count"],
        "reviewed_record_count": coverage["reviewed_record_count"],
        "needs_review_count": analytics["needs_review_count"],
        "species_counts": analytics["species_counts"],
    }


async def detector_counts(client: httpx.AsyncClient) -> dict[str, int]:
    status = (await client.get("/api/settings/local-data")).json()
    return {
        "detection_run_count": status["detection_run_count"],
        "detection_proposal_count": status["detection_proposal_count"],
    }


async def review_queue_item_for_visit(client: httpx.AsyncClient, visit_id: str) -> dict[str, object]:
    response = await client.get("/api/review-queue")
    assert response.status_code == 200
    return next(item for item in response.json() if item["visit_id"] == visit_id)


async def test_review_queue_item_exposes_zone_focus_crop_metadata_without_truth(
    client: httpx.AsyncClient,
) -> None:
    imported = await import_review_image(client, title="Review assist focus image")
    visit_id = imported["visit"]["id"]
    media_asset_id = imported["media_asset"]["id"]
    before_truth = await truth_snapshot(client)

    queue_item = await review_queue_item_for_visit(client, visit_id)
    focus_box = queue_item["focus_crop_box_normalized"]

    assert queue_item["best_media_asset_id"] == media_asset_id
    assert queue_item["focus_crop_available"] is True
    assert queue_item["focus_crop_source"] == "zone"
    assert queue_item["focus_crop_label"] == "Feeder activity focus"
    assert focus_box["x"] == pytest.approx(0.22)
    assert focus_box["y"] == pytest.approx(0.08)
    assert focus_box["width"] == pytest.approx(0.56)
    assert focus_box["height"] == pytest.approx(0.64)
    assert queue_item["focus_crop_box_pixels"] is None
    assert "focus_crop_pixels_unavailable" in queue_item["focus_crop_warnings"]
    assert queue_item["identification"]["focus_crop_available"] is True
    assert queue_item["identification"]["focus_crop_box_normalized"] == focus_box
    assert queue_item["identification"]["focus_crop_box_pixels"] is None
    assert queue_item["identification"]["creates_truth"] is False
    assert await truth_snapshot(client) == before_truth


async def test_review_queue_focus_crop_suppressed_for_ignore_and_privacy_zones(
    client: httpx.AsyncClient,
) -> None:
    privacy_response = await client.post(
        "/api/zones",
        json={
            "stream_id": STREAM_ID,
            "name": "Privacy porch",
            "zone_type": "privacy",
            "polygon": [
                {"x": 0.7, "y": 0.0},
                {"x": 1.0, "y": 0.0},
                {"x": 1.0, "y": 0.4},
                {"x": 0.7, "y": 0.4},
            ],
        },
    )
    assert privacy_response.status_code == 201
    privacy_zone_id = privacy_response.json()["zone"]["id"]

    ignored = await import_review_image(
        client,
        title="Review assist ignore-zone image",
        zone_id="zone-ignore-driveway-edge",
    )
    private = await import_review_image(
        client,
        title="Review assist privacy-zone image",
        zone_id=privacy_zone_id,
    )

    ignored_item = await review_queue_item_for_visit(client, ignored["visit"]["id"])
    private_item = await review_queue_item_for_visit(client, private["visit"]["id"])

    assert ignored_item["focus_crop_available"] is False
    assert ignored_item["focus_crop_source"] == "none"
    assert ignored_item["focus_crop_box_normalized"] is None
    assert ignored_item["focus_crop_box_pixels"] is None
    assert "focus_crop_suppressed_for_ignore_zone" in ignored_item["focus_crop_warnings"]
    assert ignored_item["identification"]["focus_crop_available"] is False

    assert private_item["focus_crop_available"] is False
    assert private_item["focus_crop_source"] == "none"
    assert private_item["focus_crop_box_normalized"] is None
    assert private_item["focus_crop_box_pixels"] is None
    assert "focus_crop_suppressed_for_privacy_zone" in private_item["focus_crop_warnings"]
    assert private_item["identification"]["focus_crop_available"] is False


def mark_local_detector_available(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        product_repository,
        "get_local_detector_status",
        lambda: LocalDetectorStatus(
            status="available",
            configured=True,
            runtime_available=True,
            model_path="/tmp/mock-local-detector.onnx",
            labels_path=None,
            detail="Mock local detector available for review identification test.",
        ),
    )


def mock_local_detector_output(
    monkeypatch: pytest.MonkeyPatch,
    proposals: list[LocalDetectorProposal],
) -> None:
    # Existing adapter seam; no model file or optional detector runtime is required.
    monkeypatch.setattr(product_repository, "run_local_image_detector", lambda **_: proposals)


async def test_review_identification_setup_required_without_adapter_creates_no_truth_or_detection(
    client: httpx.AsyncClient,
) -> None:
    imported = await import_review_image(client)
    visit_id = imported["visit"]["id"]
    media_asset_id = imported["media_asset"]["id"]
    before_truth = await truth_snapshot(client)
    before_detection = await detector_counts(client)

    queue_item = await review_queue_item_for_visit(client, visit_id)
    identification = queue_item["identification"]
    assert queue_item["best_media_asset_id"] == media_asset_id
    assert identification["status"] == "setup_required"
    assert identification["adapter_id"] == LOCAL_IMAGE_DETECTOR_ID
    assert identification["can_run"] is False
    assert identification["can_run_on_best_frame"] is False
    assert identification["creates_truth"] is False
    assert identification["local_only"] is True
    assert "image/png" in identification["supported_media_types"]
    assert "MOCKINGBIRD_LOCAL_DETECTOR_MODEL_PATH" in identification["setup_hint"]
    assert "MOCKINGBIRD_LOCAL_DETECTOR_MODEL_PATH" in identification["unavailable_reason"]

    response = await client.post(f"/api/review-queue/visit/{visit_id}/identify", json={})

    assert response.status_code == 200
    result = response.json()
    assert result["identification"]["status"] == "setup_required"
    assert result["identification"]["can_run"] is False
    assert result["identification"]["created_proposal_ids"] == []
    assert result["created_proposal_ids"] == []
    assert result["proposals"] == []
    assert result["detection_run"] is None
    assert result["creates_truth"] is False
    assert result["creates_export"] is False
    assert result["creates_review_label"] is False
    assert await truth_snapshot(client) == before_truth
    assert await detector_counts(client) == before_detection


async def test_review_identification_unsupported_best_frame_returns_clean_state(
    client: httpx.AsyncClient,
) -> None:
    imported = await import_review_video(client)
    visit_id = imported["visit"]["id"]
    before_truth = await truth_snapshot(client)
    before_detection = await detector_counts(client)

    queue_item = await review_queue_item_for_visit(client, visit_id)
    identification = queue_item["identification"]
    assert identification["status"] == "unsupported_media"
    assert identification["can_run_on_best_frame"] is False
    assert identification["unavailable_reason"] == "unsupported_media_type:video/mp4"

    response = await client.post(f"/api/review-queue/visit/{visit_id}/identify", json={})

    assert response.status_code == 200
    result = response.json()
    assert result["identification"]["status"] == "unsupported_media"
    assert result["identification"]["can_run"] is False
    assert result["proposals"] == []
    assert result["detection_run"] is None
    assert result["creates_truth"] is False
    assert await truth_snapshot(client) == before_truth
    assert await detector_counts(client) == before_detection


async def test_review_identification_species_suggestion_summary_reuses_pending_suggestion_only(
    client: httpx.AsyncClient,
) -> None:
    imported = await import_review_image(client, title="Review assist suggestion image")
    visit_id = imported["visit"]["id"]
    event_id = imported["event"]["id"]
    media_asset_id = imported["media_asset"]["id"]
    before_truth = await truth_snapshot(client)

    suggestion_response = await client.post(
        "/api/species-suggestions",
        json={
            "source_id": SOURCE_ID,
            "stream_id": STREAM_ID,
            "event_id": event_id,
            "visit_id": visit_id,
            "media_asset_id": media_asset_id,
            "adapter_id": "mock_species_suggester",
            "adapter_name": "Mock species suggester",
            "suggested_label": "blue_jay",
            "confidence": 0.64,
            "rank": 1,
            "notes": "Mock/demo suggestion evidence only.",
        },
    )
    assert suggestion_response.status_code == 201
    suggestion = suggestion_response.json()

    queue_item = await review_queue_item_for_visit(client, visit_id)
    identification = queue_item["identification"]

    assert identification["status"] == "suggestion_present"
    assert identification["suggestion"]["id"] == suggestion["id"]
    assert identification["suggestion"]["suggested_label"] == "blue_jay"
    assert identification["suggestion_count"] == 1
    assert identification["proposal_count"] == 0
    assert identification["can_run_on_best_frame"] is False
    assert identification["creates_truth"] is False
    assert await truth_snapshot(client) == before_truth


async def test_review_identification_explicit_demo_adapter_creates_placeholder_proposal_not_truth(
    client: httpx.AsyncClient,
) -> None:
    imported = await import_review_image(client, title="Review assist demo image")
    visit_id = imported["visit"]["id"]
    media_asset_id = imported["media_asset"]["id"]
    before_truth = await truth_snapshot(client)
    before_detection = await detector_counts(client)

    response = await client.post(
        f"/api/review-queue/visit/{visit_id}/identify",
        json={
            "adapter_id": DEMO_ADAPTER_ID,
            "notes": "Explicit demo assist from Review Queue.",
        },
    )

    after_detection = await detector_counts(client)
    assert response.status_code == 200
    result = response.json()
    proposal = result["proposals"][0]
    assert result["identification"]["status"] == "proposal_created"
    assert result["identification"]["adapter_id"] == DEMO_ADAPTER_ID
    assert result["identification"]["adapter_is_demo"] is True
    assert result["identification"]["local_only"] is True
    assert result["identification"]["can_run_on_best_frame"] is True
    assert result["identification"]["supported_media_types"] == ["image", "video"]
    assert result["identification"]["created_proposal_ids"] == [proposal["id"]]
    assert result["created_proposal_ids"] == [proposal["id"]]
    assert "Placeholder analyzer" in result["identification"]["message"]
    assert result["detection_run"]["source"] == "demo_rule"
    assert proposal["media_asset_id"] == media_asset_id
    assert proposal["event_id"] is None
    assert proposal["visit_id"] is None
    assert proposal["status"] == "proposed"
    assert proposal["label"] == "unknown_bird"
    assert proposal["confidence"] == 0
    assert "Explicit demo assist from Review Queue." in proposal["notes"]
    assert "Identification focus context: Feeder activity focus" in proposal["notes"]
    assert "source=zone" in proposal["notes"]
    assert "normalized_box=x=0.2200,y=0.0800,width=0.5600,height=0.6400" in proposal[
        "notes"
    ]
    assert "original best frame preserved" in proposal["notes"]
    assert result["review_queue_item"]["focus_crop_available"] is True
    assert result["identification"]["focus_crop_available"] is True
    assert result["identification"]["focus_crop_label"] == "Feeder activity focus"
    assert result["creates_truth"] is False
    assert after_detection["detection_run_count"] == before_detection["detection_run_count"] + 1
    assert (
        after_detection["detection_proposal_count"]
        == before_detection["detection_proposal_count"] + 1
    )
    assert await truth_snapshot(client) == before_truth

    refreshed_item = await review_queue_item_for_visit(client, visit_id)
    assert refreshed_item["identification"]["status"] == "proposal_present"
    assert refreshed_item["identification"]["adapter_is_demo"] is True
    assert refreshed_item["identification"]["proposal"]["id"] == proposal["id"]

    export_response = await client.post(
        "/api/dataset-exports",
        json={"name": "Review identification demo before correction"},
    )
    assert export_response.status_code == 201
    assert all(
        record["visit_id"] != visit_id
        for record in export_response.json()["manifest"]["records"]
    )


async def test_review_identification_available_detection_adapter_then_correction_creates_truth(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mark_local_detector_available(monkeypatch)
    mock_local_detector_output(
        monkeypatch,
        [
            LocalDetectorProposal(
                label="bird",
                confidence=0.81,
                bbox=LocalDetectorBox(x=0.1, y=0.2, width=0.3, height=0.25),
            )
        ],
    )
    imported = await import_review_image(client, title="Review assist local detector image")
    visit_id = imported["visit"]["id"]
    before_truth = await truth_snapshot(client)

    queue_item = await review_queue_item_for_visit(client, visit_id)
    assert queue_item["identification"]["status"] == "configured_available"
    assert queue_item["identification"]["adapter_id"] == LOCAL_IMAGE_DETECTOR_ID
    assert queue_item["identification"]["can_run"] is True
    assert queue_item["identification"]["can_run_on_best_frame"] is True
    assert "image/png" in queue_item["identification"]["supported_media_types"]

    response = await client.post(f"/api/review-queue/visit/{visit_id}/identify", json={})

    assert response.status_code == 200
    result = response.json()
    proposal = result["proposals"][0]
    assert result["identification"]["status"] == "proposal_created"
    assert result["identification"]["adapter_id"] == LOCAL_IMAGE_DETECTOR_ID
    assert result["identification"]["created_proposal_ids"] == [proposal["id"]]
    assert result["detection_run"]["source"] == "future_model"
    assert proposal["label"] == "bird"
    assert proposal["bbox"] == {"x": 0.1, "y": 0.2, "width": 0.3, "height": 0.25}
    assert proposal["event_id"] is None
    assert proposal["visit_id"] is None
    assert await truth_snapshot(client) == before_truth

    correction_response = await client.post(
        "/api/review-labels",
        json={
            "target_type": "visit",
            "target_id": visit_id,
            "label": "northern_cardinal",
            "notes": "Accepted after reviewing identification assist evidence.",
        },
    )

    after_truth = await truth_snapshot(client)
    assert correction_response.status_code == 201
    assert correction_response.json()["review_label"]["label"] == "northern_cardinal"
    assert after_truth["review_label_count"] == before_truth["review_label_count"] + 1
    assert after_truth["export_ready_count"] == before_truth["export_ready_count"] + 1
    assert after_truth["species_counts"]["northern_cardinal"] == (
        before_truth["species_counts"].get("northern_cardinal", 0) + 1
    )

    corrected_queue = (await client.get("/api/review-queue")).json()
    assert all(item["visit_id"] != visit_id for item in corrected_queue)


async def test_review_identification_adapter_failure_is_clean_and_truth_safe(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mark_local_detector_available(monkeypatch)

    def fail_detector(**_: object) -> list[LocalDetectorProposal]:
        raise LocalDetectorOutputError("local_detector_failed")

    monkeypatch.setattr(product_repository, "run_local_image_detector", fail_detector)
    imported = await import_review_image(client, title="Review assist failure image")
    visit_id = imported["visit"]["id"]
    before_truth = await truth_snapshot(client)
    before_detection = await detector_counts(client)

    response = await client.post(f"/api/review-queue/visit/{visit_id}/identify", json={})

    assert response.status_code == 200
    result = response.json()
    assert result["identification"]["status"] == "failed"
    assert result["identification"]["unavailable_reason"] == "local_detector_failed"
    assert result["proposals"] == []
    assert result["detection_run"] is None
    assert result["creates_truth"] is False
    assert result["creates_review_label"] is False
    assert await truth_snapshot(client) == before_truth
    assert await detector_counts(client) == before_detection
