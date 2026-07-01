import importlib
from pathlib import Path
import tomllib

import httpx
import pytest

from mockingbird.api.main import app, configure_repository
from mockingbird.detectors import megadetector_adapter
from mockingbird.detectors.megadetector_adapter import (
    MEGADETECTOR_ADAPTER_ID,
    MEGADETECTOR_LABELS_PATH_ENV,
    MEGADETECTOR_MODEL_PATH_ENV,
    MEGADETECTOR_RUNTIME_EXTRA,
    MegaDetectorBox,
    MegaDetectorProposal,
    MegaDetectorRuntimeStatus,
)
from mockingbird.repository.product_repository import ProductRepository

pytestmark = pytest.mark.anyio

STREAM_ID = "stream-backyard-feeder"
FEEDER_ZONE_ID = "zone-feeder"


@pytest.fixture(autouse=True)
def isolated_repository(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MOCKINGBIRD_LOCAL_DETECTOR_MODEL_PATH", raising=False)
    monkeypatch.delenv("MOCKINGBIRD_LOCAL_DETECTOR_LABELS_PATH", raising=False)
    monkeypatch.delenv("MOCKINGBIRD_MEGADETECTOR_MODEL_PATH", raising=False)
    monkeypatch.delenv("MOCKINGBIRD_MEGADETECTOR_LABELS_PATH", raising=False)
    monkeypatch.delenv("MOCKINGBIRD_MEGADETECTOR_CONFIDENCE_THRESHOLD", raising=False)
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


async def run_megadetector(client: httpx.AsyncClient, media_asset_id: str):
    return await client.post(
        f"/api/model-adapters/{MEGADETECTOR_ADAPTER_ID}/runs",
        json={
            "adapter_id": MEGADETECTOR_ADAPTER_ID,
            "media_asset_id": media_asset_id,
            "zone_ids": [FEEDER_ZONE_ID],
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
        return proposals

    monkeypatch.setattr(megadetector_adapter, "_execute_megadetector_runtime", execute_runtime)


def test_pyproject_declares_optional_megadetector_extra_without_core_dependency() -> None:
    pyproject = tomllib.loads(Path("pyproject.toml").read_text())

    core_dependencies = "\n".join(pyproject["project"].get("dependencies", [])).lower()
    optional_dependencies = pyproject["project"]["optional-dependencies"]
    detector_extra = optional_dependencies["detector-megadetector"]

    assert any(dependency.startswith("PytorchWildlife>=") for dependency in detector_extra)
    assert "pytorchwildlife" not in core_dependencies
    assert "torch" not in core_dependencies


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
                bbox=MegaDetectorBox(x=0.2, y=0.3, width=0.25, height=0.2),
            ),
            MegaDetectorProposal(label="person", confidence=0.72),
            MegaDetectorProposal(label="vehicle", confidence=0.66),
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
        "x": 0.2,
        "y": 0.3,
        "width": 0.25,
        "height": 0.2,
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
                bbox=MegaDetectorBox(x=0.1, y=0.12, width=0.3, height=0.24),
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
