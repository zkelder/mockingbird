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
            "title": "Adapter contract media",
            "subject_label": "unknown_bird",
            "species_guess": "unknown_bird",
            "notes": "Local media for model adapter contract.",
        },
        files={"file": ("adapter-bird.png", b"adapter contract image bytes", "image/png")},
    )


async def run_adapter(
    client: httpx.AsyncClient,
    media_asset_id: str,
    payload: dict[str, object] | None = None,
):
    return await client.post(
        f"/api/model-adapters/{ADAPTER_ID}/runs",
        json={
            "adapter_id": ADAPTER_ID,
            "media_asset_id": media_asset_id,
            "zone_ids": [FEEDER_ZONE_ID],
            "requested_labels": ["bird"],
            "notes": "Contract run evidence only.",
            **(payload or {}),
        },
    )


async def test_model_adapters_list_returns_demo_adapter(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/model-adapters")

    assert response.status_code == 200
    adapters = response.json()
    demo_adapter = next(adapter for adapter in adapters if adapter["id"] == ADAPTER_ID)
    assert demo_adapter["name"] == "Demo Rule Detector"
    assert demo_adapter["kind"] == "demo"
    assert demo_adapter["status"] == "available"
    assert demo_adapter["creates_review_truth"] is False
    assert demo_adapter["local_only"] is True
    assert {"image", "video"}.issubset(set(demo_adapter["supported_media_types"]))


async def test_model_adapter_run_creates_detection_run_and_proposed_evidence(
    client: httpx.AsyncClient,
) -> None:
    media_asset = (await import_image(client)).json()["media_asset"]
    initial_events = (await client.get("/api/events")).json()
    initial_visits = (await client.get("/api/visits")).json()

    response = await run_adapter(client, media_asset["id"])

    assert response.status_code == 200
    result = response.json()
    run = result["detection_run"]
    proposal = result["proposals"][0]
    assert result["adapter"]["creates_review_truth"] is False
    assert "proposal evidence, not review truth" in result["local_first_note"]
    assert run["media_asset_id"] == media_asset["id"]
    assert run["source"] == "demo_rule"
    assert run["status"] == "completed"
    assert proposal["media_asset_id"] == media_asset["id"]
    assert proposal["zone_id"] == FEEDER_ZONE_ID
    assert proposal["event_id"] is None
    assert proposal["visit_id"] is None
    assert proposal["status"] == "proposed"
    assert proposal["label"] == "bird"
    assert len((await client.get("/api/events")).json()) == len(initial_events)
    assert len((await client.get("/api/visits")).json()) == len(initial_visits)


async def test_model_adapter_run_error_cases(client: httpx.AsyncClient) -> None:
    media_asset = (await import_image(client)).json()["media_asset"]

    unknown_adapter = await client.post(
        "/api/model-adapters/missing-adapter/runs",
        json={
            "adapter_id": "missing-adapter",
            "media_asset_id": media_asset["id"],
        },
    )
    unknown_media = await run_adapter(client, "media-asset-missing")
    unknown_zone = await run_adapter(
        client,
        media_asset["id"],
        {"zone_ids": ["zone-missing"]},
    )

    assert unknown_adapter.status_code == 404
    assert "Model adapter" in unknown_adapter.json()["detail"]
    assert unknown_media.status_code == 404
    assert "Media asset" in unknown_media.json()["detail"]
    assert unknown_zone.status_code == 404
    assert "Zone" in unknown_zone.json()["detail"]


async def test_adapter_proposal_converts_through_existing_review_flow(
    client: httpx.AsyncClient,
) -> None:
    media_asset = (await import_image(client)).json()["media_asset"]
    proposal = (await run_adapter(client, media_asset["id"])).json()["proposals"][0]

    decision_response = await client.post(
        f"/api/detection-proposals/{proposal['id']}/decision",
        json={"decision": "convert_to_event"},
    )

    assert decision_response.status_code == 200
    decision = decision_response.json()
    event = decision["event"]
    visit = decision["visit"]
    assert decision["proposal"]["status"] == "converted"
    assert decision["proposal"]["event_id"] == event["id"]
    assert decision["proposal"]["visit_id"] == visit["id"]
    assert event["detections"][0]["label"] == "bird"
    assert visit["review_status"] == "needs_review"

    queue = (await client.get("/api/review-queue")).json()
    assert any(item["visit_id"] == visit["id"] for item in queue)


async def test_corrected_adapter_visit_exports_user_truth_not_adapter_label(
    client: httpx.AsyncClient,
) -> None:
    media_asset = (await import_image(client)).json()["media_asset"]
    proposal = (await run_adapter(client, media_asset["id"])).json()["proposals"][0]
    visit = (
        await client.post(
            f"/api/detection-proposals/{proposal['id']}/decision",
            json={"decision": "convert_to_event"},
        )
    ).json()["visit"]

    pre_correction_export = await client.post(
        "/api/dataset-exports",
        json={"name": "Adapter contract before correction"},
    )
    correction_response = await client.post(
        "/api/review-labels",
        json={"review_origin": "human", 
            "target_type": "visit",
            "target_id": visit["id"],
            "label": "blue_jay",
            "notes": "Corrected adapter proposal truth.",
        },
    )
    export_response = await client.post(
        "/api/dataset-exports",
        json={"name": "Adapter contract after correction"},
    )

    assert pre_correction_export.status_code == 201
    assert all(
        record["visit_id"] != visit["id"]
        for record in pre_correction_export.json()["manifest"]["records"]
    )
    assert correction_response.status_code == 201
    assert correction_response.json()["visit"]["reviewed_label"] == "blue_jay"
    record = next(
        record
        for record in export_response.json()["manifest"]["records"]
        if record["visit_id"] == visit["id"]
    )
    assert record["label"] == "blue_jay"
    assert record["label"] != proposal["label"]
    assert record["detections"][0]["label"] == proposal["label"]


async def test_raw_adapter_proposal_does_not_change_coverage_or_qa_truth(
    client: httpx.AsyncClient,
) -> None:
    media_asset = (await import_image(client)).json()["media_asset"]
    coverage_before = (await client.get("/api/dataset-coverage/summary")).json()
    quality_before = (await client.get("/api/dataset-quality/summary")).json()

    response = await run_adapter(
        client,
        media_asset["id"],
        {"requested_labels": ["blue_jay"]},
    )

    coverage_after = (await client.get("/api/dataset-coverage/summary")).json()
    quality_after = (await client.get("/api/dataset-quality/summary")).json()

    assert response.status_code == 200
    assert coverage_after["covered_target_species_count"] == coverage_before["covered_target_species_count"]
    assert coverage_after["reviewed_species_count"] == coverage_before["reviewed_species_count"]
    assert quality_after["export_ready_count"] == quality_before["export_ready_count"]
    assert quality_after["needs_review_count"] == quality_before["needs_review_count"]


async def test_converted_adapter_proposal_is_qa_review_needed_until_correction(
    client: httpx.AsyncClient,
) -> None:
    media_asset = (await import_image(client)).json()["media_asset"]
    proposal = (await run_adapter(client, media_asset["id"])).json()["proposals"][0]
    before_quality = (await client.get("/api/dataset-quality/summary")).json()

    decision_response = await client.post(
        f"/api/detection-proposals/{proposal['id']}/decision",
        json={"decision": "convert_to_event"},
    )
    after_quality = (await client.get("/api/dataset-quality/summary")).json()

    assert decision_response.status_code == 200
    assert after_quality["needs_review_count"] == before_quality["needs_review_count"] + 1
    assert after_quality["high_count"] >= before_quality["high_count"] + 1
