from pathlib import Path

import httpx
import pytest

from mockingbird.api.main import app, configure_repository
from mockingbird.repository.product_repository import ProductRepository
from tests.conftest import LegacyAuthenticatedTestClient

pytestmark = pytest.mark.anyio

ADAPTER_ID = "demo_rule_detector"
STREAM_ID = "stream-backyard-feeder"
FEEDER_ZONE_ID = "zone-feeder"
VISIT_ID = "visit-bird-feeder-001"


@pytest.fixture(autouse=True)
def isolated_repository(tmp_path: Path) -> None:
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
    async with LegacyAuthenticatedTestClient(transport=transport, base_url="http://testserver") as api_client:
        yield api_client


async def import_image(client: httpx.AsyncClient):
    return await client.post(
        "/api/media/import",
        data={
            "stream_id": STREAM_ID,
            "zone_id": FEEDER_ZONE_ID,
            "title": "Readiness media",
            "subject_label": "unknown_bird",
            "species_guess": "unknown_bird",
            "notes": "Local media for pre-model readiness.",
        },
        files={"file": ("readiness-bird.png", b"readiness image bytes", "image/png")},
    )


async def run_adapter(client: httpx.AsyncClient, media_asset_id: str, label: str = "bird"):
    response = await client.post(
        f"/api/model-adapters/{ADAPTER_ID}/runs",
        json={
            "adapter_id": ADAPTER_ID,
            "media_asset_id": media_asset_id,
            "zone_ids": [FEEDER_ZONE_ID],
            "requested_labels": [label],
            "notes": "Readiness adapter evidence.",
        },
    )
    assert response.status_code == 200
    return response.json()["proposals"][0]


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
        json={"review_origin": "human", 
            "target_type": "visit",
            "target_id": visit_id,
            "label": label,
            "notes": "Readiness correction truth.",
        },
    )
    assert response.status_code == 201
    return response.json()


def checklist_by_id(summary: dict) -> dict[str, dict]:
    return {item["id"]: item for item in summary["checklist"]}


async def test_model_readiness_summary_shape_and_read_only_behavior(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("MOCKINGBIRD_LOCAL_DETECTOR_MODEL_PATH", raising=False)
    monkeypatch.delenv("MOCKINGBIRD_MEGADETECTOR_MODEL_PATH", raising=False)
    runs_before = (await client.get("/api/detection-runs")).json()
    labels_before = (await client.get("/api/review-labels")).json()

    response = await client.get("/api/model-readiness/summary")

    runs_after = (await client.get("/api/detection-runs")).json()
    labels_after = (await client.get("/api/review-labels")).json()
    assert response.status_code == 200
    assert runs_after == runs_before
    assert labels_after == labels_before
    summary = response.json()
    checklist = checklist_by_id(summary)
    setup_by_id = {item["adapter_id"]: item for item in summary["adapter_setup"]}
    assert summary["reviewed_record_count"] == 1
    assert summary["export_ready_count"] == 1
    assert summary["dataset_quality_issue_count"] == 1
    assert summary["high_quality_issue_count"] == 1
    assert summary["ready_for_first_detector_spike"] is False
    assert "does not run ML or inspect media" in summary["local_first_note"]
    assert "DetectionProposal evidence" in summary["local_first_note"]
    assert {"demo_rule_detector", "local_image_detector", "megadetector"}.issubset(
        setup_by_id
    )
    assert setup_by_id["demo_rule_detector"]["status"] == "demo"
    assert setup_by_id["demo_rule_detector"]["is_demo"] is True
    assert setup_by_id["demo_rule_detector"]["can_run_on_review_best_frame"] is True
    assert setup_by_id["demo_rule_detector"]["creates_truth"] is False
    assert setup_by_id["local_image_detector"]["status"] == "setup_required"
    assert setup_by_id["local_image_detector"]["required_env_var"] == (
        "MOCKINGBIRD_LOCAL_DETECTOR_MODEL_PATH"
    )
    assert "local model file" in setup_by_id["local_image_detector"]["model_path_hint"]
    assert "No model files are bundled or downloaded" in setup_by_id[
        "local_image_detector"
    ]["setup_hint"]
    assert setup_by_id["local_image_detector"]["can_run"] is False
    assert setup_by_id["local_image_detector"]["creates_truth"] is False
    assert setup_by_id["megadetector"]["status"] == "setup_required"
    assert setup_by_id["megadetector"]["required_env_var"] == (
        "MOCKINGBIRD_MEGADETECTOR_MODEL_PATH"
    )
    assert setup_by_id["megadetector"]["creates_truth"] is False
    assert {"reviewed-local-dataset", "dataset-qa-high-issues", "adapter-evidence-contract"}.issubset(
        checklist
    )
    assert checklist["dataset-qa-high-issues"]["status"] == "blocked"


async def test_high_qa_issues_prevent_first_detector_spike(client: httpx.AsyncClient) -> None:
    summary = (await client.get("/api/model-readiness/summary")).json()

    assert summary["high_quality_issue_count"] == 1
    assert summary["ready_for_first_detector_spike"] is False
    assert "Resolve high-priority dataset QA issues" in summary["recommended_next_step"]


async def test_corrected_export_ready_records_improve_model_readiness(
    client: httpx.AsyncClient,
) -> None:
    before = (await client.get("/api/model-readiness/summary")).json()

    await correct_visit(client, VISIT_ID, "Northern Cardinal")
    after = (await client.get("/api/model-readiness/summary")).json()
    checklist = checklist_by_id(after)

    assert before["ready_for_first_detector_spike"] is False
    assert after["high_quality_issue_count"] == 0
    assert after["reviewed_record_count"] == before["reviewed_record_count"] + 1
    assert after["export_ready_count"] == before["export_ready_count"] + 1
    assert after["covered_target_species_count"] == before["covered_target_species_count"] + 1
    assert after["ready_for_first_detector_spike"] is True
    assert "Ready for first detector spike" in after["recommended_next_step"]
    assert checklist["export-ready-records"]["status"] == "ready"
    assert checklist["species-coverage"]["status"] == "attention"


async def test_raw_adapter_proposals_do_not_count_as_readiness_truth(
    client: httpx.AsyncClient,
) -> None:
    media_asset = (await import_image(client)).json()["media_asset"]
    before = (await client.get("/api/model-readiness/summary")).json()

    await run_adapter(client, media_asset["id"], "blue_jay")
    after = (await client.get("/api/model-readiness/summary")).json()

    assert after["adapter_proposal_count"] == before["adapter_proposal_count"] + 1
    assert after["adapter_reviewed_count"] == before["adapter_reviewed_count"]
    assert after["reviewed_record_count"] == before["reviewed_record_count"]
    assert after["export_ready_count"] == before["export_ready_count"]
    assert after["ready_for_first_detector_spike"] is False


async def test_reviewed_adapter_evidence_updates_readiness_signal(
    client: httpx.AsyncClient,
) -> None:
    media_asset = (await import_image(client)).json()["media_asset"]
    proposal = await run_adapter(client, media_asset["id"], "blue_jay")
    visit = (await convert_proposal(client, proposal["id"]))["visit"]

    await correct_visit(client, visit["id"], "Blue Jay")
    summary = (await client.get("/api/model-readiness/summary")).json()

    assert summary["adapter_proposal_count"] == 1
    assert summary["adapter_reviewed_count"] == 1
    assert summary["adapter_match_rate"] == 1
    assert checklist_by_id(summary)["adapter-evaluation-signal"]["status"] == "ready"
