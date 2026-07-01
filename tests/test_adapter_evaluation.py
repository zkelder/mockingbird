from pathlib import Path

import httpx
import pytest

from mockingbird.api.main import app, configure_repository
from mockingbird.repository.product_repository import ProductRepository

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
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as api_client:
        yield api_client


async def import_image(client: httpx.AsyncClient, filename: str = "adapter-evaluation.png"):
    return await client.post(
        "/api/media/import",
        data={
            "stream_id": STREAM_ID,
            "zone_id": FEEDER_ZONE_ID,
            "title": "Adapter evaluation media",
            "subject_label": "unknown_bird",
            "species_guess": "unknown_bird",
            "notes": "Local media for adapter evaluation.",
        },
        files={"file": (filename, b"adapter evaluation image bytes", "image/png")},
    )


async def run_adapter(
    client: httpx.AsyncClient,
    media_asset_id: str,
    label: str = "bird",
):
    response = await client.post(
        f"/api/model-adapters/{ADAPTER_ID}/runs",
        json={
            "adapter_id": ADAPTER_ID,
            "media_asset_id": media_asset_id,
            "zone_ids": [FEEDER_ZONE_ID],
            "requested_labels": [label],
            "notes": "Adapter evaluation proposal evidence.",
        },
    )
    assert response.status_code == 200
    return response.json()["proposals"][0]


async def create_adapter_proposal(client: httpx.AsyncClient, label: str = "bird"):
    media_asset = (await import_image(client, f"{label}.png")).json()["media_asset"]
    return await run_adapter(client, media_asset["id"], label)


async def create_manual_proposal(client: httpx.AsyncClient, media_asset_id: str):
    return await client.post(
        "/api/detection-proposals",
        json={
            "media_asset_id": media_asset_id,
            "stream_id": STREAM_ID,
            "zone_id": FEEDER_ZONE_ID,
            "label": "squirrel",
            "confidence": 0.63,
            "suggested_event_type": "animal_visit",
            "suggested_subject_label": "squirrel",
            "notes": "Manual proposal should not be included in adapter filter.",
        },
    )


async def convert_proposal(client: httpx.AsyncClient, proposal_id: str):
    response = await client.post(
        f"/api/detection-proposals/{proposal_id}/decision",
        json={"decision": "convert_to_event"},
    )
    assert response.status_code == 200
    return response.json()


async def reject_proposal(client: httpx.AsyncClient, proposal_id: str):
    response = await client.post(
        f"/api/detection-proposals/{proposal_id}/decision",
        json={"decision": "reject", "notes": "Not useful adapter evidence."},
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
            "notes": "Reviewed truth for adapter evaluation.",
        },
    )
    assert response.status_code == 201
    return response.json()


async def test_adapter_evaluation_counts_raw_rejected_and_converted_unreviewed(
    client: httpx.AsyncClient,
) -> None:
    raw_proposal = await create_adapter_proposal(client, "bird")
    rejected_proposal = await create_adapter_proposal(client, "squirrel")
    converted_proposal = await create_adapter_proposal(client, "cat")
    await reject_proposal(client, rejected_proposal["id"])
    await convert_proposal(client, converted_proposal["id"])

    response = await client.get("/api/model-adapters/evaluation")

    assert response.status_code == 200
    summary = response.json()
    outcomes = {item["proposal_id"]: item["outcome"] for item in summary["items"]}
    assert summary["proposal_count"] == 3
    assert summary["reviewed_count"] == 0
    assert summary["unreviewed_count"] == 2
    assert summary["rejected_count"] == 1
    assert summary["converted_count"] == 1
    assert summary["match_rate"] is None
    assert outcomes[raw_proposal["id"]] == "awaiting_review"
    assert outcomes[rejected_proposal["id"]] == "rejected_evidence"
    assert outcomes[converted_proposal["id"]] == "converted_needs_review"
    assert "not a deployment score" in summary["local_first_note"]


async def test_adapter_evaluation_compares_reviewed_truth_and_match_rate(
    client: httpx.AsyncClient,
) -> None:
    matched = await create_adapter_proposal(client, "blue_jay")
    mismatched = await create_adapter_proposal(client, "bird")
    unknown = await create_adapter_proposal(client, "bird")

    matched_visit = (await convert_proposal(client, matched["id"]))["visit"]
    mismatched_visit = (await convert_proposal(client, mismatched["id"]))["visit"]
    unknown_visit = (await convert_proposal(client, unknown["id"]))["visit"]
    await correct_visit(client, matched_visit["id"], "Blue Jay")
    await correct_visit(client, mismatched_visit["id"], "squirrel")
    await correct_visit(client, unknown_visit["id"], "unknown_bird")

    response = await client.get("/api/model-adapters/evaluation")

    assert response.status_code == 200
    summary = response.json()
    items = {item["proposal_id"]: item for item in summary["items"]}
    assert summary["proposal_count"] == 3
    assert summary["reviewed_count"] == 3
    assert summary["unreviewed_count"] == 0
    assert summary["matched_count"] == 1
    assert summary["mismatched_count"] == 1
    assert summary["unknown_reviewed_count"] == 1
    assert summary["match_rate"] == 0.5
    assert items[matched["id"]]["outcome"] == "matched_reviewed_truth"
    assert items[matched["id"]]["reviewed_label"] == "blue_jay"
    assert items[matched["id"]]["reviewed_display_name"] == "Blue Jay"
    assert items[mismatched["id"]]["outcome"] == "mismatched_reviewed_truth"
    assert items[unknown["id"]]["outcome"] == "unknown_reviewed_label"


async def test_adapter_evaluation_handles_freeform_truth_and_adapter_filter(
    client: httpx.AsyncClient,
) -> None:
    adapter_proposal = await create_adapter_proposal(client, "bird")
    adapter_visit = (await convert_proposal(client, adapter_proposal["id"]))["visit"]
    await correct_visit(client, adapter_visit["id"], "mystery feeder guest")
    manual_media = (await import_image(client, "manual-proposal.png")).json()["media_asset"]
    manual_response = await create_manual_proposal(client, manual_media["id"])

    all_response = await client.get("/api/model-adapters/evaluation")
    filtered_response = await client.get(
        "/api/model-adapters/evaluation",
        params={"adapter_id": ADAPTER_ID},
    )

    assert manual_response.status_code == 201
    assert all_response.status_code == 200
    assert filtered_response.status_code == 200
    assert all_response.json()["proposal_count"] == 2
    filtered = filtered_response.json()
    assert filtered["adapter_id"] == ADAPTER_ID
    assert filtered["adapter_name"] == "Demo Rule Detector"
    assert filtered["proposal_count"] == 1
    item = filtered["items"][0]
    assert item["adapter_id"] == ADAPTER_ID
    assert item["outcome"] == "mismatched_reviewed_truth"
    assert item["reviewed_label"] == "mystery_feeder_guest"
    assert item["reviewed_display_name"] == "Mystery Feeder Guest"
