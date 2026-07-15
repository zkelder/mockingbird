import importlib
import os
from pathlib import Path
from types import SimpleNamespace
import tomllib

import httpx
import pytest

from mockingbird.api.main import app, configure_repository
from mockingbird.detectors import megadetector_adapter
from mockingbird.detectors.megadetector_adapter import (
    MEGADETECTOR_ADAPTER_ID,
    MEGADETECTOR_DEFAULT_CONFIDENCE_THRESHOLD,
    MEGADETECTOR_LABELS_PATH_ENV,
    MEGADETECTOR_MODEL_PATH_ENV,
    MEGADETECTOR_RUNTIME_CACHE_PATH_ENV,
    MEGADETECTOR_RUNTIME_EXTRA,
    MegaDetectorBox,
    MegaDetectorOutputError,
    MegaDetectorProposal,
    MegaDetectorRuntimeStatus,
)
from mockingbird.repository.product_repository import ProductRepository

pytestmark = pytest.mark.anyio

STREAM_ID = "stream-backyard-feeder"
FEEDER_ZONE_ID = "zone-feeder"
IGNORE_ZONE_ID = "zone-ignore-driveway-edge"


@pytest.fixture(autouse=True)
def isolated_repository(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MOCKINGBIRD_LOCAL_DETECTOR_MODEL_PATH", raising=False)
    monkeypatch.delenv("MOCKINGBIRD_LOCAL_DETECTOR_LABELS_PATH", raising=False)
    monkeypatch.delenv("MOCKINGBIRD_MEGADETECTOR_MODEL_PATH", raising=False)
    monkeypatch.delenv("MOCKINGBIRD_MEGADETECTOR_LABELS_PATH", raising=False)
    monkeypatch.delenv("MOCKINGBIRD_MEGADETECTOR_CONFIDENCE_THRESHOLD", raising=False)
    monkeypatch.setenv(
        MEGADETECTOR_RUNTIME_CACHE_PATH_ENV,
        str(tmp_path / "megadetector-runtime-cache"),
    )
    monkeypatch.delenv("YOLOV5_CONFIG_DIR", raising=False)
    monkeypatch.delenv("MPLCONFIGDIR", raising=False)
    monkeypatch.delenv("YOLOv5_AUTOINSTALL", raising=False)
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
            "title": "MegaDetector image",
            "subject_label": "unknown_animal",
            "notes": "Imported image for MegaDetector adapter wrapper.",
        },
        files={"file": ("megadetector.png", b"megadetector image bytes", "image/png")},
    )


async def import_video(client: httpx.AsyncClient):
    return await client.post(
        "/api/media/import",
        data={
            "stream_id": STREAM_ID,
            "zone_id": FEEDER_ZONE_ID,
            "title": "MegaDetector unsupported video",
            "subject_label": "unknown_animal",
            "notes": "Video should not run through MegaDetector wrapper.",
        },
        files={"file": ("megadetector.mp4", b"megadetector video bytes", "video/mp4")},
    )


async def run_megadetector(
    client: httpx.AsyncClient,
    media_asset_id: str,
    *,
    zone_id: str = FEEDER_ZONE_ID,
):
    return await client.post(
        f"/api/model-adapters/{MEGADETECTOR_ADAPTER_ID}/runs",
        json={
            "adapter_id": MEGADETECTOR_ADAPTER_ID,
            "media_asset_id": media_asset_id,
            "zone_ids": [zone_id],
            "notes": "MegaDetector-family proposal evidence only.",
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
            "notes": "User-reviewed truth for MegaDetector-family evidence.",
        },
    )
    assert response.status_code == 201
    return response.json()


def mark_megadetector_available(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    labels_path: str | None = None,
) -> Path:
    model_path = tmp_path / "mock-megadetector.pt"
    model_path.write_bytes(b"local model placeholder")
    monkeypatch.setenv(MEGADETECTOR_MODEL_PATH_ENV, str(model_path))
    if labels_path is not None:
        monkeypatch.setenv(MEGADETECTOR_LABELS_PATH_ENV, labels_path)
    monkeypatch.setattr(
        megadetector_adapter,
        "get_megadetector_runtime_status",
        lambda: MegaDetectorRuntimeStatus(
            available=True,
            detail="Mock MegaDetector runtime dependency is importable.",
        ),
    )
    return model_path


def mock_megadetector_output(
    monkeypatch: pytest.MonkeyPatch,
    proposals: list[MegaDetectorProposal],
) -> None:
    def execute_runtime(**kwargs) -> list[MegaDetectorProposal]:
        assert Path(kwargs["media_local_path"]).is_file()
        assert Path(kwargs["model_path"]).is_file()
        focus_box = kwargs["focus_box"]
        assert focus_box is not None
        assert focus_box.x == pytest.approx(0.22)
        assert focus_box.y == pytest.approx(0.08)
        assert focus_box.width == pytest.approx(0.56)
        assert focus_box.height == pytest.approx(0.64)
        return proposals

    monkeypatch.setattr(megadetector_adapter, "_execute_megadetector_runtime", execute_runtime)


def test_pyproject_keeps_megadetector_runtime_optional_and_out_of_core() -> None:
    pyproject = tomllib.loads(Path("pyproject.toml").read_text())

    core_dependencies = "\n".join(pyproject["project"].get("dependencies", [])).lower()
    optional_dependencies = pyproject["project"].get("optional-dependencies", {})
    optional_dependency_text = "\n".join(
        dependency.lower()
        for dependencies in optional_dependencies.values()
        for dependency in dependencies
    )

    assert optional_dependencies["detector-megadetector"] == [
        "megadetector>=10.0.22,<11.0; python_version < '3.14'"
    ]
    assert "pytorchwildlife" not in core_dependencies
    assert "torch" not in core_dependencies
    assert "pytorchwildlife" not in optional_dependency_text
    assert "torch" not in optional_dependency_text
    assert "ultralytics" not in optional_dependency_text
    assert "yolov5" not in optional_dependency_text
    assert "soundfile" not in optional_dependency_text
    assert "librosa" not in optional_dependency_text


def test_runtime_status_inspects_official_megadetector_package(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inspected: list[str] = []

    def find_spec(package_name: str):
        inspected.append(package_name)
        return SimpleNamespace()

    monkeypatch.setattr(megadetector_adapter.util, "find_spec", find_spec)

    status = megadetector_adapter.get_megadetector_runtime_status()

    assert status.available is True
    assert inspected == ["megadetector"]


def test_runtime_executes_explicit_local_model_and_maps_official_output(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    model_path = tmp_path / "mdv5.pt"
    image_path = tmp_path / "feeder.jpg"
    model_path.write_bytes(b"local model")
    image_path.write_bytes(b"local image")
    calls: dict[str, object] = {}

    class FakeDetector:
        def generate_detections_one_image(
            self,
            image,
            *,
            image_id: str,
            detection_threshold: float,
        ):
            calls["image"] = image
            calls["image_id"] = image_id
            calls["threshold"] = detection_threshold
            return {
                "detections": [
                    {"category": "2", "conf": 0.75, "bbox": [0.1, 0.2, 0.3, 0.4]},
                    {"category": "1", "conf": 0.91, "bbox": [0.2, 0.3, 0.2, 0.2]},
                    {"category": "3", "conf": 0.05, "bbox": [0.0, 0.0, 0.1, 0.1]},
                    {"category": "99", "conf": 0.99, "bbox": [0.0, 0.0, 0.1, 0.1]},
                ]
            }

    def load_detector(path: str, *, force_model_download: bool):
        calls["model_path"] = path
        calls["force_model_download"] = force_model_download
        return FakeDetector()

    def load_image(path: str):
        calls["loaded_image_path"] = path
        return "decoded image"

    modules = {
        "megadetector.detection.run_detector": SimpleNamespace(
            load_detector=load_detector
        ),
        "megadetector.visualization.visualization_utils": SimpleNamespace(
            load_image=load_image
        ),
    }
    monkeypatch.setattr(
        megadetector_adapter,
        "_load_megadetector_runtime",
        lambda: SimpleNamespace(),
    )
    monkeypatch.setattr(
        megadetector_adapter,
        "import_module",
        lambda module_name: modules[module_name],
    )

    proposals = megadetector_adapter._execute_megadetector_runtime(
        media_local_path=str(image_path),
        model_path=str(model_path),
        labels_path=None,
        confidence_threshold=None,
        zone_context=FEEDER_ZONE_ID,
    )

    assert calls["model_path"] == str(model_path.resolve())
    assert calls["force_model_download"] is False
    assert calls["loaded_image_path"] == str(image_path)
    assert calls["image"] == "decoded image"
    assert calls["image_id"] == str(image_path)
    assert calls["threshold"] == MEGADETECTOR_DEFAULT_CONFIDENCE_THRESHOLD
    cache_root = Path(os.environ[MEGADETECTOR_RUNTIME_CACHE_PATH_ENV]).resolve()
    assert os.environ["YOLOV5_CONFIG_DIR"] == str(cache_root / "yolov5")
    assert os.environ["MPLCONFIGDIR"] == str(cache_root / "matplotlib")
    assert os.environ["YOLOv5_AUTOINSTALL"] == "False"
    assert (cache_root / "yolov5").is_dir()
    assert (cache_root / "matplotlib").is_dir()
    assert [proposal.label for proposal in proposals] == ["animal", "person"]
    assert proposals[0].bbox == MegaDetectorBox(
        x=0.2,
        y=0.3,
        width=0.2,
        height=0.2,
    )


def test_focus_crop_remaps_boxes_to_original_frame() -> None:
    crop_calls: list[tuple[int, int, int, int]] = []

    class FakeImage:
        size = (1000, 500)

        def crop(self, box):
            crop_calls.append(box)
            return "focused image"

    focus_box = MegaDetectorBox(x=0.2, y=0.1, width=0.5, height=0.6)
    focused_image, applied_box = megadetector_adapter._focused_image(
        FakeImage(),
        focus_box,
    )
    remapped = megadetector_adapter._remap_focused_proposals(
        [
            MegaDetectorProposal(
                label="animal",
                confidence=0.9,
                bbox=MegaDetectorBox(x=0.1, y=0.2, width=0.3, height=0.4),
            )
        ],
        applied_box,
    )

    assert focused_image == "focused image"
    assert crop_calls == [(200, 50, 700, 350)]
    assert remapped[0].bbox == MegaDetectorBox(
        x=0.25,
        y=0.22,
        width=0.15,
        height=0.24,
    )


def test_runtime_rejects_malformed_output() -> None:
    with pytest.raises(MegaDetectorOutputError, match="unsupported_detector_output"):
        megadetector_adapter._parse_megadetector_output(
            {
                "detections": [
                    {
                        "category": "1",
                        "conf": 0.8,
                        "bbox": [0.9, 0.9, 0.2, 0.2],
                    }
                ]
            },
            threshold=0.1,
        )


def test_api_app_imports_without_optional_megadetector_runtime() -> None:
    module = importlib.import_module("mockingbird.api.main")

    assert module.app.title == "MockingBird API"


async def test_megadetector_adapter_appears_not_configured_without_model(
    client: httpx.AsyncClient,
) -> None:
    health_response = await client.get("/health")
    response = await client.get("/api/model-adapters")

    assert health_response.status_code == 200
    assert response.status_code == 200
    adapter = next(item for item in response.json() if item["id"] == MEGADETECTOR_ADAPTER_ID)
    configuration_status = adapter["configuration_status"]
    assert adapter["name"] == "MegaDetector"
    assert adapter["kind"] == "object_detector"
    assert adapter["status"] == "not_configured"
    assert adapter["creates_review_truth"] is False
    assert adapter["local_only"] is True
    assert {"image/jpeg", "image/png", "image/webp"}.issubset(adapter["supported_media_types"])
    assert {"animal", "person", "vehicle", "unknown_animal"}.issubset(
        adapter["supported_labels"]
    )
    assert "MOCKINGBIRD_MEGADETECTOR_MODEL_PATH" in adapter["notes"]
    assert configuration_status["adapter_id"] == MEGADETECTOR_ADAPTER_ID
    assert configuration_status["model_path_configured"] is False
    assert configuration_status["labels_path_configured"] is False
    assert configuration_status["runtime_available"] is False
    assert configuration_status["can_run"] is False
    assert configuration_status["creates_review_truth"] is False
    assert configuration_status["local_only"] is True
    assert {"image/jpeg", "image/png", "image/webp"}.issubset(
        configuration_status["supported_media_types"]
    )
    assert "MOCKINGBIRD_MEGADETECTOR_MODEL_PATH" in configuration_status["status_reason"]
    assert "MOCKINGBIRD_MEGADETECTOR_MODEL_PATH" in configuration_status["setup_hint"]


async def test_megadetector_status_reports_dependency_missing_with_model_file(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    model_path = tmp_path / "megadetector.pt"
    model_path.write_bytes(b"local model placeholder")
    monkeypatch.setenv(MEGADETECTOR_MODEL_PATH_ENV, str(model_path))
    monkeypatch.setattr(
        megadetector_adapter,
        "get_megadetector_runtime_status",
        lambda: MegaDetectorRuntimeStatus(
            available=False,
            detail=(
                "Optional MegaDetector runtime dependency is not installed. "
                f"Install the {MEGADETECTOR_RUNTIME_EXTRA} extra only when ready."
            ),
        ),
    )

    response = await client.get(f"/api/model-adapters/{MEGADETECTOR_ADAPTER_ID}")

    assert response.status_code == 200
    adapter = response.json()
    configuration_status = adapter["configuration_status"]
    assert adapter["status"] == "unavailable"
    assert adapter["creates_review_truth"] is False
    assert configuration_status["model_path_configured"] is True
    assert configuration_status["runtime_available"] is False
    assert configuration_status["can_run"] is False
    assert MEGADETECTOR_RUNTIME_EXTRA in configuration_status["status_reason"]


async def test_megadetector_status_reports_missing_model_file_before_runtime(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv(MEGADETECTOR_MODEL_PATH_ENV, str(tmp_path / "missing-model.pt"))
    monkeypatch.setattr(
        megadetector_adapter,
        "get_megadetector_runtime_status",
        lambda: MegaDetectorRuntimeStatus(
            available=True,
            detail="Runtime should not be inspected after missing model file.",
        ),
    )

    response = await client.get(f"/api/model-adapters/{MEGADETECTOR_ADAPTER_ID}")

    assert response.status_code == 200
    adapter = response.json()
    configuration_status = adapter["configuration_status"]
    assert adapter["status"] == "unavailable"
    assert configuration_status["model_path_configured"] is True
    assert configuration_status["runtime_available"] is False
    assert configuration_status["can_run"] is False
    assert "model file was not found" in configuration_status["status_reason"]


async def test_megadetector_rejects_non_mdv5_model_without_runtime_or_download(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    model_path = tmp_path / "megadetector.onnx"
    model_path.write_bytes(b"unsupported local model placeholder")
    monkeypatch.setenv(MEGADETECTOR_MODEL_PATH_ENV, str(model_path))
    media_asset = (await import_image(client)).json()["media_asset"]

    status_response = await client.get(
        f"/api/model-adapters/{MEGADETECTOR_ADAPTER_ID}"
    )
    run_response = await run_megadetector(client, media_asset["id"])

    assert status_response.status_code == 200
    assert status_response.json()["status"] == "unavailable"
    assert ".pt model file only" in status_response.json()["notes"]
    assert run_response.status_code == 400
    assert "MDv5 .pt model file" in run_response.json()["detail"]
    assert "automatic model downloads are not accepted" in run_response.json()["detail"]


async def test_megadetector_status_reports_available_with_runtime_and_model_file(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    mark_megadetector_available(monkeypatch, tmp_path)

    response = await client.get(f"/api/model-adapters/{MEGADETECTOR_ADAPTER_ID}")

    assert response.status_code == 200
    adapter = response.json()
    configuration_status = adapter["configuration_status"]
    assert adapter["status"] == "available"
    assert configuration_status["model_path_configured"] is True
    assert configuration_status["runtime_available"] is True
    assert configuration_status["can_run"] is True
    assert adapter["creates_review_truth"] is False


async def test_running_megadetector_without_model_config_returns_clear_error(
    client: httpx.AsyncClient,
) -> None:
    media_asset = (await import_image(client)).json()["media_asset"]

    response = await run_megadetector(client, media_asset["id"])

    assert response.status_code == 400
    assert "MOCKINGBIRD_MEGADETECTOR_MODEL_PATH" in response.json()["detail"]


async def test_running_megadetector_without_runtime_returns_optional_dependency_error(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    model_path = tmp_path / "megadetector.pt"
    model_path.write_bytes(b"local model placeholder")
    monkeypatch.setenv(MEGADETECTOR_MODEL_PATH_ENV, str(model_path))
    monkeypatch.setattr(
        megadetector_adapter,
        "get_megadetector_runtime_status",
        lambda: MegaDetectorRuntimeStatus(
            available=False,
            detail=(
                "Optional MegaDetector runtime dependency is not installed. "
                f"Install the {MEGADETECTOR_RUNTIME_EXTRA} extra only when ready."
            ),
        ),
    )
    media_asset = (await import_image(client)).json()["media_asset"]

    response = await run_megadetector(client, media_asset["id"])

    assert response.status_code == 400
    assert MEGADETECTOR_RUNTIME_EXTRA in response.json()["detail"]


async def test_running_megadetector_with_missing_model_file_returns_clear_error(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv(MEGADETECTOR_MODEL_PATH_ENV, str(tmp_path / "missing-model.pt"))
    media_asset = (await import_image(client)).json()["media_asset"]

    response = await run_megadetector(client, media_asset["id"])

    assert response.status_code == 404
    assert "model file was not found" in response.json()["detail"]


async def test_runtime_failure_returns_clean_error_without_partial_records(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    mark_megadetector_available(monkeypatch, tmp_path)

    def fail_runtime(**kwargs):
        raise MegaDetectorOutputError("megadetector_failed")

    monkeypatch.setattr(
        megadetector_adapter,
        "_execute_megadetector_runtime",
        fail_runtime,
    )
    media_asset = (await import_image(client)).json()["media_asset"]
    before_status = (await client.get("/api/settings/local-data")).json()

    response = await run_megadetector(client, media_asset["id"])

    after_status = (await client.get("/api/settings/local-data")).json()
    assert response.status_code == 400
    assert "could not analyze this image" in response.json()["detail"]
    assert after_status["detection_run_count"] == before_status["detection_run_count"]
    assert (
        after_status["detection_proposal_count"]
        == before_status["detection_proposal_count"]
    )
    assert after_status["review_label_count"] == before_status["review_label_count"]


async def test_megadetector_errors_prefer_media_validation_before_config(
    client: httpx.AsyncClient,
) -> None:
    video_asset = (await import_video(client)).json()["media_asset"]

    missing_response = await run_megadetector(client, "media-asset-missing")
    unsupported_response = await run_megadetector(client, video_asset["id"])

    assert missing_response.status_code == 404
    assert "Media asset" in missing_response.json()["detail"]
    assert unsupported_response.status_code == 400
    assert "image/jpeg" in unsupported_response.json()["detail"]
    assert "image/png" in unsupported_response.json()["detail"]
    assert "image/webp" in unsupported_response.json()["detail"]


async def test_mocked_megadetector_proposals_are_evidence_only_until_conversion(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    mark_megadetector_available(monkeypatch, tmp_path)
    mock_megadetector_output(
        monkeypatch,
        [
            MegaDetectorProposal(
                label="animal",
                confidence=0.81,
                bbox=MegaDetectorBox(x=0.4, y=0.3, width=0.1, height=0.1),
            ),
            MegaDetectorProposal(
                label="person",
                confidence=0.72,
                bbox=MegaDetectorBox(x=0.5, y=0.35, width=0.08, height=0.1),
            ),
            MegaDetectorProposal(
                label="vehicle",
                confidence=0.66,
                bbox=MegaDetectorBox(x=0.55, y=0.4, width=0.08, height=0.1),
            ),
        ],
    )
    media_asset = (await import_image(client)).json()["media_asset"]
    before_run_status = (await client.get("/api/settings/local-data")).json()
    before_run_coverage = (await client.get("/api/dataset-coverage/summary")).json()
    before_run_quality = (await client.get("/api/dataset-quality/summary")).json()

    response = await run_megadetector(client, media_asset["id"])

    after_run_status = (await client.get("/api/settings/local-data")).json()
    after_run_coverage = (await client.get("/api/dataset-coverage/summary")).json()
    after_run_quality = (await client.get("/api/dataset-quality/summary")).json()
    assert response.status_code == 200
    result = response.json()
    proposals = result["proposals"]
    proposal_by_label = {proposal["label"]: proposal for proposal in proposals}
    assert result["adapter"]["id"] == MEGADETECTOR_ADAPTER_ID
    assert result["adapter"]["creates_review_truth"] is False
    assert result["detection_run"]["source"] == "future_model"
    assert result["detection_run"]["status"] == "completed"
    assert {proposal["label"] for proposal in proposals} == {
        "unknown_animal",
        "person",
        "vehicle",
    }
    assert [proposal["status"] for proposal in proposals] == ["proposed", "proposed", "proposed"]
    assert proposal_by_label["unknown_animal"]["bbox"] == {
        "x": 0.4,
        "y": 0.3,
        "width": 0.1,
        "height": 0.1,
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


async def test_megadetector_drops_background_proposals_outside_selected_zone(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    mark_megadetector_available(monkeypatch, tmp_path)
    mock_megadetector_output(
        monkeypatch,
        [
            MegaDetectorProposal(
                label="animal",
                confidence=0.8,
                bbox=MegaDetectorBox(x=0.42, y=0.3, width=0.08, height=0.1),
            ),
            MegaDetectorProposal(
                label="vehicle",
                confidence=0.95,
                bbox=MegaDetectorBox(x=0.8, y=0.7, width=0.1, height=0.1),
            ),
        ],
    )
    media_asset = (await import_image(client)).json()["media_asset"]

    response = await run_megadetector(client, media_asset["id"])

    assert response.status_code == 200
    proposals = response.json()["proposals"]
    assert len(proposals) == 1
    assert proposals[0]["label"] == "unknown_animal"
    assert proposals[0]["bbox"] == {
        "x": 0.42,
        "y": 0.3,
        "width": 0.08,
        "height": 0.1,
    }


async def test_megadetector_never_runs_for_privacy_or_ignore_zones(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    mark_megadetector_available(monkeypatch, tmp_path)

    def fail_if_invoked(**kwargs):
        raise AssertionError("MegaDetector runtime must not run for an Ignore zone.")

    monkeypatch.setattr(
        megadetector_adapter,
        "_execute_megadetector_runtime",
        fail_if_invoked,
    )
    media_asset = (await import_image(client)).json()["media_asset"]

    response = await run_megadetector(
        client,
        media_asset["id"],
        zone_id=IGNORE_ZONE_ID,
    )

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "MegaDetector analysis is disabled for Privacy and Ignore zones. "
        "No inference, proposal evidence, reviewed truth, or export data was created."
    )
    assert (await client.get("/api/detection-proposals")).json() == []


async def test_mocked_megadetector_conversion_exports_corrected_truth(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    mark_megadetector_available(monkeypatch, tmp_path)
    mock_megadetector_output(
        monkeypatch,
        [
            MegaDetectorProposal(
                label="animal",
                confidence=0.84,
                bbox=MegaDetectorBox(x=0.45, y=0.3, width=0.1, height=0.1),
            )
        ],
    )
    media_asset = (await import_image(client)).json()["media_asset"]
    proposal = (await run_megadetector(client, media_asset["id"])).json()["proposals"][0]

    decision = await convert_proposal(client, proposal["id"])
    pre_correction_export = await client.post(
        "/api/dataset-exports",
        json={"name": "MegaDetector before correction"},
    )
    correction = await correct_visit(client, decision["visit"]["id"], "squirrel")
    export_response = await client.post(
        "/api/dataset-exports",
        json={"name": "MegaDetector after correction"},
    )
    evaluation_response = await client.get(
        "/api/model-adapters/evaluation",
        params={"adapter_id": MEGADETECTOR_ADAPTER_ID},
    )

    assert decision["proposal"]["status"] == "converted"
    assert decision["event"]["detections"][0]["label"] == "unknown_animal"
    assert pre_correction_export.status_code == 201
    assert all(
        record["visit_id"] != decision["visit"]["id"]
        for record in pre_correction_export.json()["manifest"]["records"]
    )
    assert correction["visit"]["reviewed_label"] == "squirrel"
    record = next(
        record
        for record in export_response.json()["manifest"]["records"]
        if record["visit_id"] == decision["visit"]["id"]
    )
    assert record["label"] == "squirrel"
    assert record["label"] != proposal["label"]
    assert record["detections"][0]["label"] == proposal["label"]
    assert evaluation_response.status_code == 200
    evaluation = evaluation_response.json()
    assert evaluation["adapter_id"] == MEGADETECTOR_ADAPTER_ID
    assert evaluation["proposal_count"] == 1
    assert evaluation["reviewed_count"] == 1
    assert evaluation["mismatched_count"] == 1
    assert evaluation["items"][0]["outcome"] == "mismatched_reviewed_truth"
