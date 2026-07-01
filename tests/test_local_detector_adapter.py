from pathlib import Path

import httpx
import pytest

from mockingbird.api.main import app, configure_repository
from mockingbird.detectors.local_image_detector import (
    LOCAL_IMAGE_DETECTOR_ID,
    LocalDetectorBox,
    LocalDetectorProposal,
    LocalDetectorStatus,
)
from mockingbird.repository import product_repository
from mockingbird.repository.product_repository import ProductRepository

pytestmark = pytest.mark.anyio

STREAM_ID = "stream-backyard-feeder"
FEEDER_ZONE_ID = "zone-feeder"


@pytest.fixture(autouse=True)
def isolated_repository(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MOCKINGBIRD_LOCAL_DETECTOR_MODEL_PATH", raising=False)
    monkeypatch.delenv("MOCKINGBIRD_LOCAL_DETECTOR_LABELS_PATH", raising=False)
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


async def import_image(client: httpx.AsyncClient):
    return await client.post(
        "/api/media/import",
        data={
            "stream_id": STREAM_ID,
            "zone_id": FEEDER_ZONE_ID,
            "title": "Local detector image",
            "subject_label": "unknown_bird",
            "species_guess": "unknown_bird",
            "notes": "Imported image for local detector adapter.",
        },
        files={"file": ("local-detector.png", b"local detector image bytes", "image/png")},
    )


async def import_video(client: httpx.AsyncClient):
    return await client.post(
        "/api/media/import",
        data={
            "stream_id": STREAM_ID,
            "zone_id": FEEDER_ZONE_ID,
            "title": "Local detector unsupported video",
            "subject_label": "unknown_animal",
            "notes": "Video should not run through local image detector.",
        },
        files={"file": ("local-detector.mp4", b"local detector video bytes", "video/mp4")},
    )


async def run_local_detector(client: httpx.AsyncClient, media_asset_id: str):
    return await client.post(
        f"/api/model-adapters/{LOCAL_IMAGE_DETECTOR_ID}/runs",
        json={
            "adapter_id": LOCAL_IMAGE_DETECTOR_ID,
            "media_asset_id": media_asset_id,
            "zone_ids": [FEEDER_ZONE_ID],
            "notes": "Local detector proposal evidence only.",
        },
    )


async def convert_proposal(client: httpx.AsyncClient, proposal_id: str):
    response = await client.post(
        f"/api/detection-proposals/{proposal_id}/decision",
        json={"decision": "convert_to_event"},
    )
    assert response.status_code == 200
    return response.json()


async def correct_visit(client: httpx.AsyncClient, visit_id: str, label: str):
    response = await client.post(
        "/api/review-labels",
        json={
            "target_type": "visit",
            "target_id": visit_id,
            "label": label,
            "notes": "User-reviewed truth for mocked local detector evidence.",
        },
    )
    assert response.status_code == 201
    return response.json()


def mark_local_detector_available(
    monkeypatch: pytest.MonkeyPatch,
    *,
    labels_path: str | None = None,
) -> None:
    monkeypatch.setattr(
        product_repository,
        "get_local_detector_status",
        lambda: LocalDetectorStatus(
            status="available",
            configured=True,
            runtime_available=True,
            model_path="/tmp/mock-local-detector.onnx",
            labels_path=labels_path,
            detail="Mock local detector available for test.",
        ),
    )


def mock_local_detector_output(
    monkeypatch: pytest.MonkeyPatch,
    proposals: list[LocalDetectorProposal],
) -> None:
    # This test seam proves the adapter contract without requiring model files.
    monkeypatch.setattr(product_repository, "run_local_image_detector", lambda **_: proposals)


async def test_local_detector_adapter_appears_not_configured_without_model(
    client: httpx.AsyncClient,
) -> None:
    health_response = await client.get("/health")
    response = await client.get("/api/model-adapters")

    assert health_response.status_code == 200
    assert response.status_code == 200
    adapter = next(item for item in response.json() if item["id"] == LOCAL_IMAGE_DETECTOR_ID)
    configuration_status = adapter["configuration_status"]
    assert adapter["name"] == "Local Image Detector"
    assert adapter["kind"] == "object_detector"
    assert adapter["status"] == "not_configured"
    assert adapter["creates_review_truth"] is False
    assert adapter["local_only"] is True
    assert {"image/jpeg", "image/png", "image/webp"}.issubset(adapter["supported_media_types"])
    assert "MOCKINGBIRD_LOCAL_DETECTOR_MODEL_PATH" in adapter["notes"]
    assert configuration_status["adapter_id"] == LOCAL_IMAGE_DETECTOR_ID
    assert configuration_status["model_path_configured"] is False
    assert configuration_status["labels_path_configured"] is False
    assert configuration_status["runtime_available"] is False
    assert configuration_status["can_run"] is False
    assert configuration_status["creates_review_truth"] is False
    assert configuration_status["local_only"] is True
    assert {"image/jpeg", "image/png", "image/webp"}.issubset(
        configuration_status["supported_media_types"]
    )
    assert "MOCKINGBIRD_LOCAL_DETECTOR_MODEL_PATH" in configuration_status["status_reason"]
    assert "MOCKINGBIRD_LOCAL_DETECTOR_MODEL_PATH" in configuration_status["setup_hint"]


async def test_local_detector_adapter_status_reports_configured_runtime_when_mocked(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mark_local_detector_available(monkeypatch, labels_path="/tmp/mock-labels.txt")

    response = await client.get(f"/api/model-adapters/{LOCAL_IMAGE_DETECTOR_ID}")

    assert response.status_code == 200
    adapter = response.json()
    configuration_status = adapter["configuration_status"]
    assert adapter["status"] == "available"
    assert configuration_status["model_path_configured"] is True
    assert configuration_status["labels_path_configured"] is True
    assert configuration_status["runtime_available"] is True
    assert configuration_status["can_run"] is True
    assert configuration_status["creates_review_truth"] is False


async def test_running_local_detector_without_model_config_returns_clear_error(
    client: httpx.AsyncClient,
) -> None:
    media_asset = (await import_image(client)).json()["media_asset"]

    response = await run_local_detector(client, media_asset["id"])

    assert response.status_code == 400
    assert "MOCKINGBIRD_LOCAL_DETECTOR_MODEL_PATH" in response.json()["detail"]


async def test_local_detector_errors_prefer_media_validation_before_config(
    client: httpx.AsyncClient,
) -> None:
    video_asset = (await import_video(client)).json()["media_asset"]

    missing_response = await run_local_detector(client, "media-asset-missing")
    unsupported_response = await run_local_detector(client, video_asset["id"])

    assert missing_response.status_code == 404
    assert "Media asset" in missing_response.json()["detail"]
    assert unsupported_response.status_code == 400
    assert "image/jpeg" in unsupported_response.json()["detail"]
    assert "image/png" in unsupported_response.json()["detail"]
    assert "image/webp" in unsupported_response.json()["detail"]


async def test_local_detector_proposals_are_evidence_only_until_conversion(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mark_local_detector_available(monkeypatch)
    mock_local_detector_output(
        monkeypatch,
        [
            LocalDetectorProposal(
                label="bird",
                confidence=0.77,
                bbox=LocalDetectorBox(x=0.2, y=0.3, width=0.25, height=0.2),
            )
        ],
    )
    media_asset = (await import_image(client)).json()["media_asset"]
    initial_events = (await client.get("/api/events")).json()
    initial_visits = (await client.get("/api/visits")).json()
    coverage_before = (await client.get("/api/dataset-coverage/summary")).json()
    quality_before = (await client.get("/api/dataset-quality/summary")).json()

    response = await run_local_detector(client, media_asset["id"])

    coverage_after = (await client.get("/api/dataset-coverage/summary")).json()
    quality_after = (await client.get("/api/dataset-quality/summary")).json()
    assert response.status_code == 200
    result = response.json()
    proposal = result["proposals"][0]
    assert result["adapter"]["id"] == LOCAL_IMAGE_DETECTOR_ID
    assert result["adapter"]["creates_review_truth"] is False
    assert result["detection_run"]["source"] == "future_model"
    assert proposal["event_id"] is None
    assert proposal["visit_id"] is None
    assert proposal["status"] == "proposed"
    assert proposal["label"] == "bird"
    assert proposal["bbox"] == {"x": 0.2, "y": 0.3, "width": 0.25, "height": 0.2}
    assert len((await client.get("/api/events")).json()) == len(initial_events)
    assert len((await client.get("/api/visits")).json()) == len(initial_visits)
    assert coverage_after["export_ready_count"] == coverage_before["export_ready_count"]
    assert quality_after["export_ready_count"] == quality_before["export_ready_count"]


async def test_local_detector_empty_result_creates_run_without_truth(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mark_local_detector_available(monkeypatch)
    mock_local_detector_output(monkeypatch, [])
    media_asset = (await import_image(client)).json()["media_asset"]

    response = await run_local_detector(client, media_asset["id"])

    assert response.status_code == 200
    result = response.json()
    assert result["detection_run"]["status"] == "completed"
    assert result["proposals"] == []
    assert "no proposal evidence" in result["local_first_note"]


async def test_mocked_local_detector_lifecycle_uses_corrections_as_truth(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mark_local_detector_available(monkeypatch)
    mock_local_detector_output(
        monkeypatch,
        [
            LocalDetectorProposal(
                label="blue_jay",
                confidence=0.82,
                bbox=LocalDetectorBox(x=0.1, y=0.15, width=0.3, height=0.25),
            ),
            LocalDetectorProposal(label="bird", confidence=0.76),
            LocalDetectorProposal(label="bird", confidence=0.64),
        ],
    )
    media_asset = (await import_image(client)).json()["media_asset"]
    before_run_status = (await client.get("/api/settings/local-data")).json()
    before_run_coverage = (await client.get("/api/dataset-coverage/summary")).json()
    before_run_quality = (await client.get("/api/dataset-quality/summary")).json()

    run_response = await run_local_detector(client, media_asset["id"])

    after_run_status = (await client.get("/api/settings/local-data")).json()
    after_run_coverage = (await client.get("/api/dataset-coverage/summary")).json()
    after_run_quality = (await client.get("/api/dataset-quality/summary")).json()
    assert run_response.status_code == 200
    run_result = run_response.json()
    proposals = run_result["proposals"]
    proposal_by_label = {proposal["label"]: proposal for proposal in proposals}
    bird_proposals = [proposal for proposal in proposals if proposal["label"] == "bird"]
    assert run_result["detection_run"]["status"] == "completed"
    assert run_result["detection_run"]["source"] == "future_model"
    assert run_result["adapter"]["id"] == LOCAL_IMAGE_DETECTOR_ID
    assert run_result["adapter"]["creates_review_truth"] is False
    assert [proposal["status"] for proposal in proposals] == ["proposed", "proposed", "proposed"]
    assert proposal_by_label["blue_jay"]["bbox"] == {
        "x": 0.1,
        "y": 0.15,
        "width": 0.3,
        "height": 0.25,
    }
    assert all(proposal["event_id"] is None and proposal["visit_id"] is None for proposal in proposals)
    assert after_run_status["detection_run_count"] == before_run_status["detection_run_count"] + 1
    assert after_run_status["detection_proposal_count"] == before_run_status["detection_proposal_count"] + 3
    assert after_run_status["event_count"] == before_run_status["event_count"]
    assert after_run_status["visit_count"] == before_run_status["visit_count"]
    assert after_run_status["review_label_count"] == before_run_status["review_label_count"]
    assert after_run_coverage["export_ready_count"] == before_run_coverage["export_ready_count"]
    assert after_run_coverage["reviewed_record_count"] == before_run_coverage["reviewed_record_count"]
    assert after_run_quality["export_ready_count"] == before_run_quality["export_ready_count"]
    assert after_run_quality["needs_review_count"] == before_run_quality["needs_review_count"]

    blue_jay_decision = await convert_proposal(client, proposal_by_label["blue_jay"]["id"])
    northern_cardinal_decision = await convert_proposal(client, bird_proposals[0]["id"])
    unknown_decision = await convert_proposal(client, bird_proposals[1]["id"])
    converted_visits = [
        blue_jay_decision["visit"],
        northern_cardinal_decision["visit"],
        unknown_decision["visit"],
    ]
    after_conversion_status = (await client.get("/api/settings/local-data")).json()
    after_conversion_quality = (await client.get("/api/dataset-quality/summary")).json()
    pre_correction_export = await client.post(
        "/api/dataset-exports",
        json={"name": "Mocked local detector before correction"},
    )
    review_queue = (await client.get("/api/review-queue")).json()
    evaluation_before_correction = await client.get(
        "/api/model-adapters/evaluation",
        params={"adapter_id": LOCAL_IMAGE_DETECTOR_ID},
    )

    assert after_conversion_status["event_count"] == after_run_status["event_count"] + 3
    assert after_conversion_status["visit_count"] == after_run_status["visit_count"] + 3
    assert after_conversion_status["review_label_count"] == after_run_status["review_label_count"]
    assert after_conversion_quality["needs_review_count"] == after_run_quality["needs_review_count"] + 3
    assert pre_correction_export.status_code == 201
    assert all(
        record["visit_id"] not in {visit["id"] for visit in converted_visits}
        for record in pre_correction_export.json()["manifest"]["records"]
    )
    assert {visit["id"] for visit in converted_visits}.issubset(
        {item["visit_id"] for item in review_queue}
    )
    assert blue_jay_decision["event"]["detections"][0]["label"] == "blue_jay"
    assert northern_cardinal_decision["event"]["detections"][0]["label"] == "bird"
    assert unknown_decision["event"]["detections"][0]["label"] == "bird"
    assert evaluation_before_correction.status_code == 200
    assert evaluation_before_correction.json()["converted_count"] == 3
    assert evaluation_before_correction.json()["reviewed_count"] == 0
    assert evaluation_before_correction.json()["match_rate"] is None

    blue_jay_correction = await correct_visit(client, blue_jay_decision["visit"]["id"], "Blue Jay")
    cardinal_correction = await correct_visit(
        client,
        northern_cardinal_decision["visit"]["id"],
        "Northern Cardinal",
    )
    unknown_correction = await correct_visit(client, unknown_decision["visit"]["id"], "unknown_bird")
    after_correction_coverage = (await client.get("/api/dataset-coverage/summary")).json()
    after_correction_quality = (await client.get("/api/dataset-quality/summary")).json()
    export_response = await client.post(
        "/api/dataset-exports",
        json={"name": "Mocked local detector after correction"},
    )
    evaluation_response = await client.get(
        "/api/model-adapters/evaluation",
        params={"adapter_id": LOCAL_IMAGE_DETECTOR_ID},
    )
    review_labels = (await client.get("/api/review-labels")).json()

    assert blue_jay_correction["visit"]["review_status"] == "reviewed"
    assert blue_jay_correction["review_label"]["label"] == "blue_jay"
    assert cardinal_correction["review_label"]["label"] == "northern_cardinal"
    assert unknown_correction["review_label"]["label"] == "unknown_bird"
    review_label_by_visit = {label["target_id"]: label["label"] for label in review_labels}
    assert review_label_by_visit[blue_jay_decision["visit"]["id"]] == "blue_jay"
    assert review_label_by_visit[northern_cardinal_decision["visit"]["id"]] == "northern_cardinal"
    assert review_label_by_visit[unknown_decision["visit"]["id"]] == "unknown_bird"
    assert after_correction_coverage["export_ready_count"] == after_run_coverage["export_ready_count"] + 3
    assert after_correction_coverage["reviewed_record_count"] == after_run_coverage["reviewed_record_count"] + 3
    assert after_correction_quality["export_ready_count"] == after_run_quality["export_ready_count"] + 3

    assert export_response.status_code == 201
    records = {
        record["visit_id"]: record
        for record in export_response.json()["manifest"]["records"]
        if record["visit_id"] in {visit["id"] for visit in converted_visits}
    }
    assert records[blue_jay_decision["visit"]["id"]]["label"] == "blue_jay"
    assert records[northern_cardinal_decision["visit"]["id"]]["label"] == "northern_cardinal"
    assert records[northern_cardinal_decision["visit"]["id"]]["detections"][0]["label"] == "bird"
    assert records[unknown_decision["visit"]["id"]]["label"] == "unknown_bird"

    assert evaluation_response.status_code == 200
    evaluation = evaluation_response.json()
    evaluation_items = {item["proposal_id"]: item for item in evaluation["items"]}
    assert evaluation["adapter_id"] == LOCAL_IMAGE_DETECTOR_ID
    assert evaluation["proposal_count"] == 3
    assert evaluation["reviewed_count"] == 3
    assert evaluation["matched_count"] == 1
    assert evaluation["mismatched_count"] == 1
    assert evaluation["unknown_reviewed_count"] == 1
    assert evaluation["match_rate"] == 0.5
    assert evaluation_items[proposal_by_label["blue_jay"]["id"]]["outcome"] == "matched_reviewed_truth"
    assert evaluation_items[proposal_by_label["blue_jay"]["id"]]["reviewed_label"] == "blue_jay"
    assert evaluation_items[bird_proposals[0]["id"]]["outcome"] == "mismatched_reviewed_truth"
    assert evaluation_items[bird_proposals[0]["id"]]["reviewed_label"] == "northern_cardinal"
    assert evaluation_items[bird_proposals[1]["id"]]["outcome"] == "unknown_reviewed_label"
