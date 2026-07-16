from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from mockingbird.api.main import app, configure_repository
from mockingbird.api.schemas import Point, ZoneCreate, ZoneType
from mockingbird.detectors.local_image_detector import (
    LOCAL_IMAGE_DETECTOR_ID,
    LocalDetectorBox,
    LocalDetectorOutputError,
    LocalDetectorProposal,
    LocalDetectorStatus,
)
from mockingbird.detectors.megadetector_adapter import (
    MEGADETECTOR_ADAPTER_ID,
    MegaDetectorBox,
    MegaDetectorProposal,
)
from mockingbird.repository import product_repository
from mockingbird.repository.product_repository import ProductRepository
from mockingbird.species.bioclip_adapter import (
    BIOCLIP_ADAPTER_ID,
    BIOCLIP_ADAPTER_NAME,
    BIOCLIP_PROMPT_RECIPE_ID,
    BIOCLIP_PROMPT_RECIPE_SHA256,
    BIOCLIP_SCORE_KIND,
    BioClipBusyError,
    BioClipOutputError,
    BioClipPrediction,
    BioClipProvenance,
    BioClipRankedSuggestion,
)

pytestmark = pytest.mark.anyio

SOURCE_ID = "source-backyard-demo"
STREAM_ID = "stream-backyard-feeder"
FEEDER_ZONE_ID = "zone-feeder"
DEMO_ADAPTER_ID = "demo_rule_detector"


@pytest.fixture(autouse=True)
def isolated_repository(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("MOCKINGBIRD_LOCAL_DETECTOR_MODEL_PATH", raising=False)
    monkeypatch.delenv("MOCKINGBIRD_LOCAL_DETECTOR_LABELS_PATH", raising=False)
    monkeypatch.delenv("MOCKINGBIRD_MEGADETECTOR_MODEL_PATH", raising=False)
    monkeypatch.delenv("MOCKINGBIRD_BIOCLIP_MODEL_PATH", raising=False)
    monkeypatch.delenv("MOCKINGBIRD_BIOCLIP_LABELS_PATH", raising=False)
    monkeypatch.delenv("MOCKINGBIRD_BIOCLIP_EMBEDDING_CACHE_PATH", raising=False)
    monkeypatch.delenv("MOCKINGBIRD_BIOCLIP_DEVICE", raising=False)
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


async def create_activity_review_item(
    client: httpx.AsyncClient,
    *,
    media_asset_id: str,
) -> tuple[str, str]:
    evidence_response = await client.post(
        "/api/motion/evidence",
        json={
            "source_id": SOURCE_ID,
            "stream_id": STREAM_ID,
            "zone_id": FEEDER_ZONE_ID,
            "start_frame_index": 10,
            "end_frame_index": 12,
            "best_frame_index": 11,
            "peak_changed_ratio": 0.24,
            "triggered_frame_count": 2,
            "scoring_config": {
                "source": "test_activity_motion",
                "activity_left": 0.45,
                "activity_top": 0.35,
                "activity_right": 0.55,
                "activity_bottom": 0.45,
                "activity_changed_pixel_count": 24,
                "best_frame_width": 1000,
                "best_frame_height": 500,
            },
            "snapshot_media_asset_id": media_asset_id,
        },
    )
    assert evidence_response.status_code == 201
    evidence_id = evidence_response.json()["id"]
    promote_response = await client.post(
        f"/api/motion/evidence/{evidence_id}/promote",
        json={
            "event_title": "Measured outdoor activity",
            "visit_label_hint": "unknown_animal",
            "create_event": True,
            "create_visit": True,
            "attach_snapshot_media_asset_id": media_asset_id,
        },
    )
    assert promote_response.status_code == 200
    return promote_response.json()["visit_id"], evidence_id


async def test_review_queue_does_not_derive_focus_from_zone_without_activity(
    client: httpx.AsyncClient,
) -> None:
    imported = await import_review_image(client, title="Review assist focus image")
    visit_id = imported["visit"]["id"]
    media_asset_id = imported["media_asset"]["id"]
    before_truth = await truth_snapshot(client)

    queue_item = await review_queue_item_for_visit(client, visit_id)
    assert queue_item["best_media_asset_id"] == media_asset_id
    assert queue_item["focus_crop_available"] is False
    assert queue_item["focus_crop_source"] == "none"
    assert queue_item["focus_crop_label"] is None
    assert queue_item["focus_crop_box_normalized"] is None
    assert queue_item["focus_crop_box_pixels"] is None
    assert "focus_crop_activity_bounds_unavailable" in queue_item["focus_crop_warnings"]
    assert queue_item["identification"]["focus_crop_available"] is False
    assert queue_item["identification"]["focus_crop_box_normalized"] is None
    assert queue_item["identification"]["focus_crop_box_pixels"] is None
    assert queue_item["identification"]["creates_truth"] is False
    assert await truth_snapshot(client) == before_truth


async def test_review_queue_item_exposes_measured_activity_focus_without_truth(
    client: httpx.AsyncClient,
) -> None:
    imported = await import_review_image(client, title="Measured activity image")
    media_asset_id = imported["media_asset"]["id"]
    visit_id, _evidence_id = await create_activity_review_item(
        client,
        media_asset_id=media_asset_id,
    )
    before_truth = await truth_snapshot(client)

    queue_item = await review_queue_item_for_visit(client, visit_id)
    focus_box = queue_item["focus_crop_box_normalized"]

    assert queue_item["focus_crop_available"] is True
    assert queue_item["focus_crop_source"] == "activity"
    assert queue_item["focus_crop_label"] == "Detected activity focus"
    assert focus_box == pytest.approx(
        {"x": 0.4, "y": 0.3, "width": 0.2, "height": 0.2}
    )
    assert queue_item["focus_crop_box_pixels"] == {
        "x": 400,
        "y": 149,
        "width": 201,
        "height": 101,
    }
    assert "focus_crop_small_activity_expanded" in queue_item["focus_crop_warnings"]
    assert queue_item["identification"]["focus_crop_source"] == "activity"
    assert queue_item["identification"]["focus_crop_box_normalized"] == focus_box
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
    before_truth = await truth_snapshot(client)
    before_detection = await detector_counts(client)

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

    for visit_id in (ignored["visit"]["id"], private["visit"]["id"]):
        blocked = await client.post(
            f"/api/review-queue/visit/{visit_id}/identify",
            json={"adapter_id": DEMO_ADAPTER_ID},
        )
        assert blocked.status_code == 200
        assert blocked.json()["identification"]["status"] == "unsupported_media"
        assert blocked.json()["identification"]["unavailable_reason"] == (
            "identification_zone_suppressed"
        )
        assert blocked.json()["detection_run"] is None
        assert blocked.json()["proposals"] == []
    assert await detector_counts(client) == before_detection
    assert await truth_snapshot(client) == before_truth


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


def mark_bioclip_available(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    model_dir = tmp_path / "bioclip-model"
    labels_path = tmp_path / "bioclip-labels.txt"
    cache_path = tmp_path / "bioclip-embeddings.npz"
    monkeypatch.setenv("MOCKINGBIRD_BIOCLIP_MODEL_PATH", str(model_dir))
    monkeypatch.setenv("MOCKINGBIRD_BIOCLIP_LABELS_PATH", str(labels_path))
    monkeypatch.setenv("MOCKINGBIRD_BIOCLIP_EMBEDDING_CACHE_PATH", str(cache_path))
    monkeypatch.setattr(
        product_repository,
        "get_bioclip_status",
        lambda _config: SimpleNamespace(
            status="available",
            configured=True,
            runtime_available=True,
            detail="Mock BioCLIP is available for Review Queue seam tests.",
            model_dir=str(model_dir),
            labels_path=str(labels_path),
            embedding_cache_path=str(cache_path),
            device="cpu",
            labels_sha256="a" * 64,
        ),
    )


def bioclip_prediction(
    *ranked: tuple[str, str | None, str | None, float],
) -> BioClipPrediction:
    suggestions = tuple(
        BioClipRankedSuggestion(
            rank=index,
            label=label,
            common_name=common_name,
            scientific_name=scientific_name,
            score=score,
        )
        for index, (label, common_name, scientific_name, score) in enumerate(
            ranked,
            start=1,
        )
    )
    return BioClipPrediction(
        suggestions=suggestions,
        provenance=BioClipProvenance(
            adapter_id=BIOCLIP_ADAPTER_ID,
            adapter_name=BIOCLIP_ADAPTER_NAME,
            model_name="BioCLIP 2 local test",
            device="cpu",
            open_clip_version="3.3.0",
            torch_version="2.13.0+cpu",
            label_count=245,
            labels_sha256="a" * 64,
            embedding_cache_sha256="b" * 64,
            model_config_sha256="c" * 64,
            model_weights_name="open_clip_model.safetensors",
            model_weights_sha256="d" * 64,
            prompt_recipe_id=BIOCLIP_PROMPT_RECIPE_ID,
            prompt_recipe_sha256=BIOCLIP_PROMPT_RECIPE_SHA256,
            score_kind=BIOCLIP_SCORE_KIND,
            calibrated=False,
        ),
    )


def mock_bioclip_run(
    monkeypatch: pytest.MonkeyPatch,
    prediction: BioClipPrediction,
    *,
    repository: ProductRepository | None = None,
) -> list[product_repository._ReviewSpeciesCropContext]:
    crops: list[product_repository._ReviewSpeciesCropContext] = []

    def load_image(**kwargs: object) -> object:
        crop = kwargs["crop"]
        assert isinstance(crop, product_repository._ReviewSpeciesCropContext)
        crops.append(crop)
        return object()

    def run_image(
        image_loader: object,
        _config: object,
        top_k: int = 5,
    ) -> BioClipPrediction:
        assert top_k == 5
        assert callable(image_loader)
        image_loader()
        if repository is not None and hasattr(repository.engine.pool, "checkedout"):
            assert repository.engine.pool.checkedout() == 0
        return prediction

    monkeypatch.setattr(product_repository, "_load_bioclip_input_image", load_image)
    monkeypatch.setattr(product_repository, "run_bioclip_from_image_loader", run_image)
    return crops


def mark_megadetector_available(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        product_repository,
        "get_megadetector_status",
        lambda: SimpleNamespace(
            status="available",
            configured=True,
            runtime_available=True,
            model_path="/tmp/mock-megadetector.pt",
            labels_path=None,
            detail="Mock MegaDetector is available for crop evidence.",
        ),
    )


async def test_review_identification_setup_points_to_species_classifier_without_truth_or_detection(
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
    assert identification["adapter_id"] == BIOCLIP_ADAPTER_ID
    assert identification["adapter_kind"] == "species_classifier"
    assert identification["setup_status"] == "setup_required"
    assert identification["can_run"] is False
    assert identification["can_run_on_best_frame"] is False
    assert identification["creates_truth"] is False
    assert identification["local_only"] is True
    assert identification["required_env_var"] == "MOCKINGBIRD_BIOCLIP_MODEL_PATH"
    assert identification["model_path_hint"] == (
        "Set MOCKINGBIRD_BIOCLIP_MODEL_PATH to a local BioCLIP model directory, "
        "MOCKINGBIRD_BIOCLIP_LABELS_PATH to the frozen candidate labels, and "
        "MOCKINGBIRD_BIOCLIP_EMBEDDING_CACHE_PATH to their precomputed embedding cache."
    )
    assert "image/png" in identification["supported_media_types"]
    assert "MOCKINGBIRD_BIOCLIP_MODEL_PATH" in identification["setup_hint"]
    assert "precomputed embedding cache" in identification["setup_hint"]
    assert "No artifacts are downloaded or generated" in identification["unavailable_reason"]

    response = await client.post(f"/api/review-queue/visit/{visit_id}/identify", json={})

    assert response.status_code == 200
    result = response.json()
    assert result["identification"]["status"] == "setup_required"
    assert result["identification"]["setup_status"] == "setup_required"
    assert result["identification"]["can_run"] is False
    assert result["identification"]["required_env_var"] == (
        "MOCKINGBIRD_BIOCLIP_MODEL_PATH"
    )
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


async def test_review_identification_does_not_reuse_another_visits_same_media_suggestion(
    client: httpx.AsyncClient,
) -> None:
    imported = await import_review_image(
        client,
        title="Shared media suggestion association",
    )
    first_visit_id = imported["visit"]["id"]
    media_asset_id = imported["media_asset"]["id"]
    second_visit_id, _evidence_id = await create_activity_review_item(
        client,
        media_asset_id=media_asset_id,
    )
    suggestion_response = await client.post(
        "/api/species-suggestions",
        json={
            "source_id": SOURCE_ID,
            "stream_id": STREAM_ID,
            "visit_id": first_visit_id,
            "media_asset_id": media_asset_id,
            "adapter_id": "visit_specific_species_adapter",
            "adapter_name": "Visit-specific species adapter",
            "suggested_label": "blue_jay",
            "confidence": 0.64,
        },
    )
    assert suggestion_response.status_code == 201

    first_item = await review_queue_item_for_visit(client, first_visit_id)
    second_item = await review_queue_item_for_visit(client, second_visit_id)

    assert first_item["identification"]["suggestion"]["id"] == (
        suggestion_response.json()["id"]
    )
    assert second_item["identification"]["suggestion"] is None
    assert second_item["suggestion_id"] is None
    assert second_item["suggested_label"] != "blue_jay"


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
    assert result["identification"]["setup_status"] == "demo"
    assert result["identification"]["local_only"] is True
    assert result["identification"]["can_run_on_best_frame"] is True
    assert result["identification"]["required_env_var"] is None
    assert "placeholder evidence" in result["identification"]["setup_hint"]
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
    assert "Identification focus context" not in proposal["notes"]
    assert result["review_queue_item"]["focus_crop_available"] is False
    assert result["identification"]["focus_crop_available"] is False
    assert result["identification"]["focus_crop_label"] is None
    assert result["creates_truth"] is False
    assert after_detection["detection_run_count"] == before_detection["detection_run_count"] + 1
    assert (
        after_detection["detection_proposal_count"]
        == before_detection["detection_proposal_count"] + 1
    )
    assert await truth_snapshot(client) == before_truth

    refreshed_item = await review_queue_item_for_visit(client, visit_id)
    assert refreshed_item["identification"]["status"] == "proposal_present"
    assert refreshed_item["identification"]["adapter_id"] == BIOCLIP_ADAPTER_ID
    assert refreshed_item["identification"]["adapter_is_demo"] is False
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
    deactivate_ignore = await client.patch(
        "/api/zones/zone-ignore-driveway-edge",
        json={"is_active": False},
    )
    assert deactivate_ignore.status_code == 200
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
    assert queue_item["identification"]["setup_status"] == "available"
    assert queue_item["identification"]["can_run"] is True
    assert queue_item["identification"]["can_run_on_best_frame"] is True
    assert queue_item["identification"]["required_env_var"] == (
        "MOCKINGBIRD_LOCAL_DETECTOR_MODEL_PATH"
    )
    assert "image/png" in queue_item["identification"]["supported_media_types"]

    response = await client.post(f"/api/review-queue/visit/{visit_id}/identify", json={})

    assert response.status_code == 200
    result = response.json()
    proposal = result["proposals"][0]
    assert result["identification"]["status"] == "proposal_created"
    assert result["identification"]["adapter_id"] == LOCAL_IMAGE_DETECTOR_ID
    assert result["identification"]["setup_status"] == "available"
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


async def test_review_identification_prefers_bioclip_and_uses_padded_megadetector_animal_crop(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    isolated_repository: ProductRepository,
) -> None:
    mark_megadetector_available(monkeypatch)
    monkeypatch.setattr(
        product_repository,
        "run_megadetector_on_image",
        lambda **_: [
            MegaDetectorProposal(
                label="animal",
                confidence=0.88,
                bbox=MegaDetectorBox(x=0.4, y=0.3, width=0.1, height=0.1),
            ),
            MegaDetectorProposal(
                label="vehicle",
                confidence=0.96,
                bbox=MegaDetectorBox(x=0.7, y=0.6, width=0.2, height=0.2),
            ),
        ],
    )
    imported = await import_review_image(client, title="BioCLIP MD crop image")
    visit_id = imported["visit"]["id"]
    media_asset_id = imported["media_asset"]["id"]
    md_response = await client.post(
        f"/api/model-adapters/{MEGADETECTOR_ADAPTER_ID}/runs",
        json={
            "adapter_id": MEGADETECTOR_ADAPTER_ID,
            "media_asset_id": media_asset_id,
            "zone_ids": [FEEDER_ZONE_ID],
        },
    )
    assert md_response.status_code == 200
    animal_proposal = next(
        proposal
        for proposal in md_response.json()["proposals"]
        if proposal["label"] == "unknown_animal"
    )
    before_truth = await truth_snapshot(client)
    before_detection = await detector_counts(client)

    monkeypatch.setattr(
        product_repository,
        "get_megadetector_status",
        lambda: SimpleNamespace(
            status="not_configured",
            configured=False,
            runtime_available=False,
            model_path=None,
            labels_path=None,
            detail="Mock prior MD evidence remains, but its runtime is no longer configured.",
        ),
    )
    stale_proposal_item = await review_queue_item_for_visit(client, visit_id)
    assert stale_proposal_item["identification"]["status"] == "proposal_present"
    assert stale_proposal_item["identification"]["adapter_id"] == BIOCLIP_ADAPTER_ID
    assert stale_proposal_item["identification"]["setup_status"] == "setup_required"

    mark_megadetector_available(monkeypatch)
    mark_bioclip_available(monkeypatch, tmp_path)
    prediction = bioclip_prediction(
        ("northern cardinal (Cardinalis cardinalis)", None, None, 0.61),
        ("blue jay (Cyanocitta cristata)", None, None, 0.19),
        ("song sparrow (Melospiza melodia)", None, None, 0.09),
        ("bird", "bird", None, 0.07),
        ("vehicle", "vehicle", None, 0.04),
    )
    crops = mock_bioclip_run(
        monkeypatch,
        prediction,
        repository=isolated_repository,
    )

    queue_item = await review_queue_item_for_visit(client, visit_id)
    assert queue_item["identification"]["adapter_id"] == BIOCLIP_ADAPTER_ID
    assert queue_item["identification"]["adapter_kind"] == "species_classifier"
    assert queue_item["identification"]["can_run"] is True
    assert queue_item["identification"]["proposal_count"] == 2

    response = await client.post(f"/api/review-queue/visit/{visit_id}/identify", json={})

    assert response.status_code == 200
    result = response.json()
    suggestion = result["species_suggestion"]
    assert result["identification"]["status"] == "suggestion_created"
    assert result["identification"]["adapter_id"] == BIOCLIP_ADAPTER_ID
    assert result["identification"]["adapter_name"] == BIOCLIP_ADAPTER_NAME
    assert result["identification"]["focus_crop_source"] == "detector"
    assert result["identification"]["created_suggestion_ids"] == [suggestion["id"]]
    assert result["created_suggestion_ids"] == [suggestion["id"]]
    assert result["created_proposal_ids"] == []
    assert result["detection_run"] is None
    assert result["proposals"] == []
    assert suggestion["status"] == "pending"
    assert suggestion["suggested_label"] == "northern_cardinal"
    assert suggestion["suggested_common_name"] == "northern cardinal"
    assert suggestion["suggested_scientific_name"] == "Cardinalis cardinalis"
    assert suggestion["confidence"] == pytest.approx(0.61)
    assert suggestion["rank"] == 1
    assert [item["rank"] for item in suggestion["alternatives"]] == [2, 3, 4, 5]
    assert suggestion["alternatives"][0] == {
        "rank": 2,
        "label": "blue jay (Cyanocitta cristata)",
        "suggested_label": "blue_jay",
        "common_name": "blue jay",
        "scientific_name": "Cyanocitta cristata",
        "score": 0.19,
        "score_kind": BIOCLIP_SCORE_KIND,
        "calibrated": False,
    }
    assert suggestion["alternatives"][-1]["label"] == "vehicle"
    assert suggestion["alternatives"][-1]["suggested_label"] == "vehicle"
    assert suggestion["alternatives"][-1]["scientific_name"] is None
    assert "candidate-relative and uncalibrated" in suggestion["notes"]
    assert "embedding_cache_sha256" in suggestion["notes"]
    assert "local_path" not in suggestion["notes"]
    evidence_region = suggestion["evidence_region"]
    assert {
        key: evidence_region[key]
        for key in ("x", "y", "width", "height")
    } == pytest.approx(
        {
            "x": 0.35,
            "y": 0.25,
            "width": 0.2,
            "height": 0.2,
        }
    )
    assert evidence_region["source"] == "megadetector"
    assert evidence_region["coordinate_space"] == "full_frame_normalized"
    assert evidence_region["detection_proposal_id"] == animal_proposal["id"]
    assert evidence_region["score_semantics"] == BIOCLIP_SCORE_KIND
    assert evidence_region["calibrated"] is False
    assert evidence_region["model_provenance"]["adapter_id"] == BIOCLIP_ADAPTER_ID
    assert "model_dir" not in evidence_region["model_provenance"]
    assert crops[0].source == "megadetector"
    assert crops[0].detection_proposal_id == animal_proposal["id"]
    assert await detector_counts(client) == before_detection
    assert await truth_snapshot(client) == before_truth

    refreshed = await review_queue_item_for_visit(client, visit_id)
    assert refreshed["identification"]["status"] == "suggestion_present"
    assert refreshed["identification"]["adapter_id"] == BIOCLIP_ADAPTER_ID
    assert refreshed["identification"]["proposal_count"] == 2
    assert refreshed["identification"]["focus_crop_source"] == "detector"


async def test_review_identification_bioclip_activity_crop_supersedes_only_prior_bioclip(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    imported = await import_review_image(client, title="BioCLIP activity crop image")
    media_asset_id = imported["media_asset"]["id"]
    visit_id, _evidence_id = await create_activity_review_item(
        client,
        media_asset_id=media_asset_id,
    )
    mark_megadetector_available(monkeypatch)
    monkeypatch.setattr(
        product_repository,
        "run_megadetector_on_image",
        lambda **_: [
            MegaDetectorProposal(
                label="animal",
                confidence=0.91,
                bbox=MegaDetectorBox(x=0.8, y=0.75, width=0.1, height=0.1),
            )
        ],
    )
    md_response = await client.post(
        f"/api/model-adapters/{MEGADETECTOR_ADAPTER_ID}/runs",
        json={
            "adapter_id": MEGADETECTOR_ADAPTER_ID,
            "media_asset_id": media_asset_id,
            "zone_ids": [FEEDER_ZONE_ID],
        },
    )
    assert md_response.status_code == 200
    other_adapter = await client.post(
        "/api/species-suggestions",
        json={
            "source_id": SOURCE_ID,
            "stream_id": STREAM_ID,
            "visit_id": visit_id,
            "media_asset_id": media_asset_id,
            "adapter_id": "other_species_adapter",
            "adapter_name": "Other species adapter",
            "suggested_label": "bird",
            "confidence": 0.2,
        },
    )
    assert other_adapter.status_code == 201
    mark_bioclip_available(monkeypatch, tmp_path)
    crops = mock_bioclip_run(
        monkeypatch,
        bioclip_prediction(
            ("northern cardinal (Cardinalis cardinalis)", None, None, 0.55),
            ("blue jay (Cyanocitta cristata)", None, None, 0.25),
        ),
    )
    before_truth = await truth_snapshot(client)
    before_detection = await detector_counts(client)

    first = await client.post(f"/api/review-queue/visit/{visit_id}/identify", json={})
    assert first.status_code == 200
    assert first.json()["species_suggestion"]["suggested_label"] == "northern_cardinal"
    # The high-confidence animal proposal is elsewhere in the frame, so the
    # measured activity that created this Visit remains the classifier input.
    assert crops[0].source == "activity"
    assert crops[0].box_normalized.model_dump() == pytest.approx(
        {"x": 0.4, "y": 0.3, "width": 0.2, "height": 0.2}
    )

    mock_bioclip_run(
        monkeypatch,
        bioclip_prediction(
            ("blue jay (Cyanocitta cristata)", None, None, 0.64),
            ("northern cardinal (Cardinalis cardinalis)", None, None, 0.24),
        ),
    )
    second = await client.post(f"/api/review-queue/visit/{visit_id}/identify", json={})
    assert second.status_code == 200
    assert second.json()["species_suggestion"]["suggested_label"] == "blue_jay"

    suggestions = (
        await client.get("/api/species-suggestions", params={"visit_id": visit_id})
    ).json()["species_suggestions"]
    bioclip = [item for item in suggestions if item["adapter_id"] == BIOCLIP_ADAPTER_ID]
    other = [item for item in suggestions if item["adapter_id"] == "other_species_adapter"]
    assert [item["status"] for item in bioclip] == ["superseded", "pending"]
    assert [item["status"] for item in other] == ["pending"]
    assert await detector_counts(client) == before_detection
    assert await truth_snapshot(client) == before_truth


async def test_review_identification_bioclip_full_frame_is_blocked_by_separate_privacy_zone(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    deactivate_ignore = await client.patch(
        "/api/zones/zone-ignore-driveway-edge",
        json={"is_active": False},
    )
    assert deactivate_ignore.status_code == 200
    privacy = await client.post(
        "/api/zones",
        json={
            "stream_id": STREAM_ID,
            "name": "Separate privacy corner",
            "zone_type": "privacy",
            "polygon": [
                {"x": 0.8, "y": 0.0},
                {"x": 1.0, "y": 0.0},
                {"x": 1.0, "y": 0.2},
                {"x": 0.8, "y": 0.2},
            ],
        },
    )
    assert privacy.status_code == 201
    imported = await import_review_image(client, title="BioCLIP privacy fallback image")
    visit_id = imported["visit"]["id"]
    mark_bioclip_available(monkeypatch, tmp_path)
    called = False

    def should_not_load(**_: object) -> object:
        nonlocal called
        called = True
        raise AssertionError("Privacy-blocked full-frame input must not be decoded.")

    monkeypatch.setattr(product_repository, "_load_bioclip_input_image", should_not_load)
    before_truth = await truth_snapshot(client)
    before_detection = await detector_counts(client)

    response = await client.post(f"/api/review-queue/visit/{visit_id}/identify", json={})

    assert response.status_code == 200
    result = response.json()
    assert result["identification"]["status"] == "unsupported_media"
    assert result["identification"]["unavailable_reason"] == (
        "identification_zone_suppressed"
    )
    assert "Privacy or Ignore Zone" in result["identification"]["message"]
    assert result["species_suggestion"] is None
    assert result["detection_run"] is None
    assert result["proposals"] == []
    assert called is False
    assert await detector_counts(client) == before_detection
    assert await truth_snapshot(client) == before_truth


async def test_review_identification_bioclip_uses_full_frame_without_restricted_zones(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    deactivate_ignore = await client.patch(
        "/api/zones/zone-ignore-driveway-edge",
        json={"is_active": False},
    )
    assert deactivate_ignore.status_code == 200
    imported = await import_review_image(client, title="BioCLIP full-frame fallback")
    visit_id = imported["visit"]["id"]
    mark_bioclip_available(monkeypatch, tmp_path)
    crops = mock_bioclip_run(
        monkeypatch,
        bioclip_prediction(
            ("blue jay (Cyanocitta cristata)", None, None, 0.48),
            ("bird", "bird", None, 0.22),
        ),
    )
    before_truth = await truth_snapshot(client)
    before_detection = await detector_counts(client)

    response = await client.post(
        f"/api/review-queue/visit/{visit_id}/identify",
        json={},
    )

    assert response.status_code == 200
    result = response.json()
    assert result["identification"]["status"] == "suggestion_created"
    assert result["identification"]["focus_crop_available"] is False
    assert result["identification"]["focus_crop_source"] == "none"
    assert result["species_suggestion"]["suggested_label"] == "blue_jay"
    evidence_region = result["species_suggestion"]["evidence_region"]
    assert evidence_region["source"] == "full_frame"
    assert {
        key: evidence_region[key]
        for key in ("x", "y", "width", "height")
    } == {
        "x": 0.0,
        "y": 0.0,
        "width": 1.0,
        "height": 1.0,
    }
    assert crops[0].source == "full_frame"
    assert await detector_counts(client) == before_detection
    assert await truth_snapshot(client) == before_truth


async def test_review_identification_bioclip_rechecks_late_privacy_zone_before_write(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    isolated_repository: ProductRepository,
) -> None:
    deactivate_ignore = await client.patch(
        "/api/zones/zone-ignore-driveway-edge",
        json={"is_active": False},
    )
    assert deactivate_ignore.status_code == 200
    imported = await import_review_image(client, title="BioCLIP late privacy race")
    visit_id = imported["visit"]["id"]
    mark_bioclip_available(monkeypatch, tmp_path)
    prediction = bioclip_prediction(
        ("northern cardinal (Cardinalis cardinalis)", None, None, 0.58),
    )

    monkeypatch.setattr(
        product_repository,
        "_load_bioclip_input_image",
        lambda **_: object(),
    )

    def add_privacy_during_inference(
        image_loader: object,
        _config: object,
        top_k: int = 5,
    ) -> BioClipPrediction:
        assert top_k == 5
        assert callable(image_loader)
        image_loader()
        isolated_repository.create_zone(
            ZoneCreate(
                stream_id=STREAM_ID,
                name="Privacy added during classifier run",
                zone_type=ZoneType.privacy,
                polygon=[
                    Point(x=0.8, y=0.0),
                    Point(x=1.0, y=0.0),
                    Point(x=1.0, y=0.2),
                    Point(x=0.8, y=0.2),
                ],
            )
        )
        return prediction

    monkeypatch.setattr(
        product_repository,
        "run_bioclip_from_image_loader",
        add_privacy_during_inference,
    )
    before_truth = await truth_snapshot(client)
    before_detection = await detector_counts(client)

    response = await client.post(
        f"/api/review-queue/visit/{visit_id}/identify",
        json={},
    )

    assert response.status_code == 200
    result = response.json()
    assert result["identification"]["status"] == "unsupported_media"
    assert result["identification"]["unavailable_reason"] == (
        "identification_zone_suppressed"
    )
    assert result["species_suggestion"] is None
    assert result["created_suggestion_ids"] == []
    assert await detector_counts(client) == before_detection
    assert await truth_snapshot(client) == before_truth


async def test_review_identification_bioclip_rechecks_media_file_before_write(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    deactivate_ignore = await client.patch(
        "/api/zones/zone-ignore-driveway-edge",
        json={"is_active": False},
    )
    assert deactivate_ignore.status_code == 200
    imported = await import_review_image(client, title="BioCLIP media race")
    visit_id = imported["visit"]["id"]
    media_path = Path(imported["media_asset"]["local_path"])
    mark_bioclip_available(monkeypatch, tmp_path)
    prediction = bioclip_prediction(
        ("northern cardinal (Cardinalis cardinalis)", None, None, 0.58),
    )
    monkeypatch.setattr(
        product_repository,
        "_load_bioclip_input_image",
        lambda **_: object(),
    )

    def remove_media_during_inference(
        image_loader: object,
        _config: object,
        top_k: int = 5,
    ) -> BioClipPrediction:
        assert top_k == 5
        assert callable(image_loader)
        image_loader()
        media_path.unlink()
        return prediction

    monkeypatch.setattr(
        product_repository,
        "run_bioclip_from_image_loader",
        remove_media_during_inference,
    )
    before_truth = await truth_snapshot(client)
    before_detection = await detector_counts(client)

    response = await client.post(
        f"/api/review-queue/visit/{visit_id}/identify",
        json={},
    )

    assert response.status_code == 200
    result = response.json()
    assert result["identification"]["status"] == "unsupported_media"
    assert result["identification"]["unavailable_reason"] == "bioclip_media_changed"
    assert result["species_suggestion"] is None
    assert result["created_suggestion_ids"] == []
    assert await detector_counts(client) == before_detection
    assert await truth_snapshot(client) == before_truth


async def test_review_identification_bioclip_rejects_unrelated_same_stream_media(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    deactivate_ignore = await client.patch(
        "/api/zones/zone-ignore-driveway-edge",
        json={"is_active": False},
    )
    assert deactivate_ignore.status_code == 200
    first = await import_review_image(client, title="BioCLIP target visit")
    unrelated = await import_review_image(client, title="Different same-stream visit")
    visit_id = first["visit"]["id"]
    unrelated_media_id = unrelated["media_asset"]["id"]
    mark_bioclip_available(monkeypatch, tmp_path)
    decoded = False

    def should_not_decode(**_: object) -> object:
        nonlocal decoded
        decoded = True
        raise AssertionError("Unrelated same-stream media must not reach inference.")

    monkeypatch.setattr(
        product_repository,
        "_load_bioclip_input_image",
        should_not_decode,
    )
    before_truth = await truth_snapshot(client)
    before_detection = await detector_counts(client)

    response = await client.post(
        f"/api/review-queue/visit/{visit_id}/identify",
        json={"media_asset_id": unrelated_media_id},
    )

    assert response.status_code == 200
    result = response.json()
    assert result["identification"]["status"] == "unsupported_media"
    assert result["identification"]["unavailable_reason"] == (
        "bioclip_media_not_review_frame"
    )
    assert result["species_suggestion"] is None
    assert result["detection_run"] is None
    assert result["proposals"] == []
    assert decoded is False
    assert await detector_counts(client) == before_detection
    assert await truth_snapshot(client) == before_truth


async def test_review_identification_bioclip_failure_is_atomic_and_keeps_pending_result(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    imported = await import_review_image(client, title="BioCLIP atomic failure image")
    media_asset_id = imported["media_asset"]["id"]
    visit_id, _evidence_id = await create_activity_review_item(
        client,
        media_asset_id=media_asset_id,
    )
    mark_bioclip_available(monkeypatch, tmp_path)
    mock_bioclip_run(
        monkeypatch,
        bioclip_prediction(
            ("northern cardinal (Cardinalis cardinalis)", None, None, 0.62),
        ),
    )
    successful = await client.post(
        f"/api/review-queue/visit/{visit_id}/identify",
        json={},
    )
    assert successful.status_code == 200
    pending_id = successful.json()["species_suggestion"]["id"]
    before_truth = await truth_snapshot(client)
    before_detection = await detector_counts(client)

    monkeypatch.setattr(
        product_repository,
        "_load_bioclip_input_image",
        lambda **_: object(),
    )

    def fail_bioclip(*_: object, **__: object) -> BioClipPrediction:
        raise BioClipOutputError("mock inference failure")

    monkeypatch.setattr(
        product_repository,
        "run_bioclip_from_image_loader",
        fail_bioclip,
    )
    failed = await client.post(
        f"/api/review-queue/visit/{visit_id}/identify",
        json={},
    )

    assert failed.status_code == 200
    assert failed.json()["identification"]["status"] == "failed"
    assert failed.json()["identification"]["unavailable_reason"] == "bioclip_failed"
    suggestions = (
        await client.get("/api/species-suggestions", params={"visit_id": visit_id})
    ).json()["species_suggestions"]
    pending = [item for item in suggestions if item["status"] == "pending"]
    assert [item["id"] for item in pending] == [pending_id]
    assert await detector_counts(client) == before_detection
    assert await truth_snapshot(client) == before_truth


async def test_review_identification_bioclip_busy_fails_fast_without_writes(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    imported = await import_review_image(client, title="BioCLIP busy image")
    media_asset_id = imported["media_asset"]["id"]
    visit_id, _evidence_id = await create_activity_review_item(
        client,
        media_asset_id=media_asset_id,
    )
    mark_bioclip_available(monkeypatch, tmp_path)
    monkeypatch.setattr(
        product_repository,
        "_load_bioclip_input_image",
        lambda **_: object(),
    )

    def report_busy(*_args: object, **_kwargs: object) -> BioClipPrediction:
        raise BioClipBusyError("another run is active")

    monkeypatch.setattr(
        product_repository,
        "run_bioclip_from_image_loader",
        report_busy,
    )
    before_truth = await truth_snapshot(client)
    before_detection = await detector_counts(client)

    response = await client.post(
        f"/api/review-queue/visit/{visit_id}/identify",
        json={},
    )

    assert response.status_code == 200
    result = response.json()
    assert result["identification"]["status"] == "running"
    assert result["identification"]["unavailable_reason"] == "bioclip_busy"
    assert "already running" in result["identification"]["message"]
    assert result["created_suggestion_ids"] == []
    assert result["detection_run"] is None
    assert result["proposals"] == []
    assert await detector_counts(client) == before_detection
    assert await truth_snapshot(client) == before_truth


async def test_review_identification_bioclip_persistence_failure_rolls_back_supersede(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    imported = await import_review_image(
        client,
        title="BioCLIP persistence rollback image",
    )
    media_asset_id = imported["media_asset"]["id"]
    visit_id, _evidence_id = await create_activity_review_item(
        client,
        media_asset_id=media_asset_id,
    )
    mark_bioclip_available(monkeypatch, tmp_path)
    mock_bioclip_run(
        monkeypatch,
        bioclip_prediction(
            ("northern cardinal (Cardinalis cardinalis)", None, None, 0.62),
        ),
    )
    successful = await client.post(
        f"/api/review-queue/visit/{visit_id}/identify",
        json={},
    )
    assert successful.status_code == 200
    pending_id = successful.json()["species_suggestion"]["id"]
    before_truth = await truth_snapshot(client)
    before_detection = await detector_counts(client)

    mock_bioclip_run(
        monkeypatch,
        bioclip_prediction(
            ("blue jay (Cyanocitta cristata)", None, None, 0.66),
        ),
    )

    def fail_after_supersede(
        _repository: ProductRepository,
        _session: object,
        _payload: object,
    ) -> object:
        raise ValueError("bioclip_persistence_failed")

    monkeypatch.setattr(
        ProductRepository,
        "_create_species_suggestion_in_session",
        fail_after_supersede,
    )
    failed = await client.post(
        f"/api/review-queue/visit/{visit_id}/identify",
        json={},
    )

    assert failed.status_code == 200
    assert failed.json()["identification"]["status"] == "failed"
    assert failed.json()["identification"]["unavailable_reason"] == (
        "bioclip_persistence_failed"
    )
    suggestions = (
        await client.get("/api/species-suggestions", params={"visit_id": visit_id})
    ).json()["species_suggestions"]
    assert [(item["id"], item["status"]) for item in suggestions] == [
        (pending_id, "pending")
    ]
    assert await detector_counts(client) == before_detection
    assert await truth_snapshot(client) == before_truth


async def test_bioclip_generic_model_run_is_blocked_from_detector_records(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    mark_bioclip_available(monkeypatch, tmp_path)
    imported = await import_review_image(client, title="BioCLIP generic route guard")
    media_asset_id = imported["media_asset"]["id"]
    before_detection = await detector_counts(client)

    response = await client.post(
        f"/api/model-adapters/{BIOCLIP_ADAPTER_ID}/runs",
        json={
            "adapter_id": BIOCLIP_ADAPTER_ID,
            "media_asset_id": media_asset_id,
            "zone_ids": [FEEDER_ZONE_ID],
        },
    )

    assert response.status_code == 400
    assert await detector_counts(client) == before_detection


async def test_review_identification_adapter_failure_is_clean_and_truth_safe(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    deactivate_ignore = await client.patch(
        "/api/zones/zone-ignore-driveway-edge",
        json={"is_active": False},
    )
    assert deactivate_ignore.status_code == 200
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
    assert result["identification"]["setup_status"] == "available"
    assert result["identification"]["required_env_var"] == (
        "MOCKINGBIRD_LOCAL_DETECTOR_MODEL_PATH"
    )
    assert result["proposals"] == []
    assert result["detection_run"] is None
    assert result["creates_truth"] is False
    assert result["creates_review_label"] is False
    assert await truth_snapshot(client) == before_truth
    assert await detector_counts(client) == before_detection
