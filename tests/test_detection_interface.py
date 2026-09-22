from pathlib import Path

import httpx
import pytest

from mockingbird.api.main import app, configure_repository
from mockingbird.repository.product_repository import ProductRepository
from tests.conftest import LegacyAuthenticatedTestClient, de_demo_seeded_source

pytestmark = pytest.mark.anyio

STREAM_ID = "stream-backyard-feeder"
FEEDER_ZONE_ID = "zone-feeder"


@pytest.fixture(autouse=True)
def isolated_repository(tmp_path: Path) -> None:
    repository = ProductRepository(
        db_url=f"sqlite:///{tmp_path / 'mockingbird.sqlite3'}",
        media_root=tmp_path / "media",
    )
    de_demo_seeded_source(repository)
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
            "title": "Imported feeder observation",
            "subject_label": "unknown_bird",
            "species_guess": "unknown_bird",
            "notes": "Local media for detection proposal.",
        },
        files={"file": ("feeder-bird.png", b"proposal image bytes", "image/png")},
    )


async def create_proposal(
    client: httpx.AsyncClient,
    media_asset_id: str,
    data: dict[str, object] | None = None,
):
    return await client.post(
        "/api/detection-proposals",
        json={
            "media_asset_id": media_asset_id,
            "stream_id": STREAM_ID,
            "zone_id": FEEDER_ZONE_ID,
            "label": "animal_candidate",
            "confidence": 0.82,
            "bbox": {"x": 0.2, "y": 0.3, "width": 0.25, "height": 0.2},
            "suggested_event_type": "animal_visit",
            "suggested_subject_label": "unknown_bird",
            "suggested_species": "unknown_bird",
            "notes": "Detector-shaped proposal for review.",
            **(data or {}),
        },
    )


async def create_demo_run(
    client: httpx.AsyncClient,
    media_asset_id: str,
    data: dict[str, object] | None = None,
):
    return await client.post(
        "/api/detection-runs/demo",
        json={
            "media_asset_id": media_asset_id,
            "label": "bird",
            "confidence": 0.72,
            "suggested_subject_label": "unknown_bird",
            "suggested_species": "unknown_bird",
            "notes": "Demo detector proposal generation for review.",
            **(data or {}),
        },
    )


async def test_demo_detection_run_creates_completed_run_and_proposed_evidence(
    client: httpx.AsyncClient,
) -> None:
    media_asset = (await import_image(client)).json()["media_asset"]
    initial_events = (await client.get("/api/events")).json()
    initial_visits = (await client.get("/api/visits")).json()

    response = await create_demo_run(client, media_asset["id"], {"zone_id": None})

    assert response.status_code == 201
    result = response.json()
    run = result["detection_run"]
    proposal = result["proposals"][0]
    assert run["media_asset_id"] == media_asset["id"]
    assert run["source"] == "demo_rule"
    assert run["status"] == "completed"
    assert "without media analysis" in run["summary"]
    assert proposal["run_id"] == run["id"]
    assert proposal["media_asset_id"] == media_asset["id"]
    assert proposal["stream_id"] == STREAM_ID
    assert proposal["zone_id"] == FEEDER_ZONE_ID
    assert proposal["event_id"] is None
    assert proposal["visit_id"] is None
    assert proposal["label"] == "bird"
    assert proposal["confidence"] == 0.72
    assert proposal["suggested_subject_label"] == "unknown_bird"
    assert proposal["suggested_species"] == "unknown_bird"
    assert proposal["status"] == "proposed"
    assert proposal["bbox"] is None
    assert len((await client.get("/api/events")).json()) == len(initial_events)
    assert len((await client.get("/api/visits")).json()) == len(initial_visits)


async def test_demo_detection_run_requires_existing_media_asset(client: httpx.AsyncClient) -> None:
    response = await create_demo_run(client, "media-asset-missing")

    assert response.status_code == 404
    assert "Media asset" in response.json()["detail"]


async def test_demo_detection_run_requires_existing_zone_when_zone_is_supplied(
    client: httpx.AsyncClient,
) -> None:
    media_asset = (await import_image(client)).json()["media_asset"]

    response = await create_demo_run(client, media_asset["id"], {"zone_id": "zone-missing"})

    assert response.status_code == 404
    assert "Zone" in response.json()["detail"]


async def test_demo_detection_run_rejects_invalid_confidence(client: httpx.AsyncClient) -> None:
    media_asset = (await import_image(client)).json()["media_asset"]

    response = await create_demo_run(client, media_asset["id"], {"confidence": 1.2})

    assert response.status_code == 422


async def test_demo_detection_run_can_convert_and_export_corrected_truth(
    client: httpx.AsyncClient,
) -> None:
    media_asset = (await import_image(client)).json()["media_asset"]
    demo_result = (
        await create_demo_run(
            client,
            media_asset["id"],
            {
                "label": "bird",
                "confidence": 0.72,
                "suggested_subject_label": "unknown_bird",
                "suggested_species": "northern_cardinal",
            },
        )
    ).json()
    proposal = demo_result["proposals"][0]

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
    queue_item = next(item for item in queue if item["visit_id"] == visit["id"])
    assert queue_item["media_asset"]["id"] == media_asset["id"]

    pre_correction_export = await client.post(
        "/api/dataset-exports",
        json={"name": "Demo proposal before correction"},
    )
    correction_response = await client.post(
        "/api/review-labels",
        json={"review_origin": "human", 
            "target_type": "visit",
            "target_id": visit["id"],
            "label": "blue_jay",
            "notes": "User-corrected demo proposal truth.",
        },
    )
    export_response = await client.post(
        "/api/dataset-exports",
        json={"name": "Demo proposal after correction"},
    )

    assert pre_correction_export.status_code == 201
    assert all(
        record["visit_id"] != visit["id"]
        for record in pre_correction_export.json()["manifest"]["records"]
    )
    assert correction_response.status_code == 201
    assert correction_response.json()["visit"]["reviewed_label"] == "blue_jay"
    assert export_response.status_code == 201
    record = next(
        record
        for record in export_response.json()["manifest"]["records"]
        if record["visit_id"] == visit["id"]
    )
    assert record["label"] == "blue_jay"
    assert record["label"] != "bird"
    assert record["detections"][0]["label"] == "bird"


async def test_local_image_smoke_path_creates_proposal_and_optional_conversion_without_truth(
    client: httpx.AsyncClient,
) -> None:
    initial_review_labels = (await client.get("/api/review-labels")).json()

    import_response = await import_image(client)

    assert import_response.status_code == 201
    import_result = import_response.json()
    media_asset = import_result["media_asset"]
    imported_event = import_result["event"]
    imported_visit = import_result["visit"]
    assert media_asset["id"]
    assert imported_event["review_status"] == "needs_review"
    assert imported_visit["review_status"] == "needs_review"

    demo_response = await create_demo_run(
        client,
        media_asset["id"],
        {
            "zone_id": FEEDER_ZONE_ID,
            "label": "bird",
            "confidence": 0.72,
            "suggested_subject_label": "unknown_bird",
            "suggested_species": "unknown_bird",
            "notes": (
                "Local image smoke demo detector evidence only. No model inspected "
                "the media and no reviewed truth was created."
            ),
        },
    )

    assert demo_response.status_code == 201
    demo_result = demo_response.json()
    detection_run = demo_result["detection_run"]
    proposal = demo_result["proposals"][0]
    media_lookup = await client.get(f"/api/media/{media_asset['id']}")
    run_lookup = await client.get(f"/api/detection-runs/{detection_run['id']}")
    run_proposals = await client.get(f"/api/detection-runs/{detection_run['id']}/proposals")

    assert media_lookup.status_code == 200
    assert media_lookup.json()["id"] == media_asset["id"]
    assert run_lookup.status_code == 200
    assert run_lookup.json()["id"] == detection_run["id"]
    assert run_lookup.json()["status"] == "completed"
    assert run_proposals.status_code == 200
    assert [item["id"] for item in run_proposals.json()] == [proposal["id"]]
    assert proposal["media_asset_id"] == media_asset["id"]
    assert proposal["zone_id"] == FEEDER_ZONE_ID
    assert proposal["status"] == "proposed"
    assert proposal["event_id"] is None
    assert proposal["visit_id"] is None
    assert proposal["label"] == "bird"
    assert proposal["suggested_subject_label"] == "unknown_bird"
    assert proposal["suggested_species"] == "unknown_bird"
    assert len((await client.get("/api/review-labels")).json()) == len(initial_review_labels)

    decision_response = await client.post(
        f"/api/detection-proposals/{proposal['id']}/decision",
        json={
            "decision": "convert_to_event",
            "event_title": "Local smoke review",
            "subject_label": "unknown_bird",
            "species_guess": "unknown_bird",
            "notes": "Optional smoke conversion still requires explicit correction.",
        },
    )

    assert decision_response.status_code == 200
    decision = decision_response.json()
    converted_event = decision["event"]
    converted_visit = decision["visit"]
    assert converted_event["review_status"] == "needs_review"
    assert converted_visit["review_status"] == "needs_review"
    assert decision["proposal"]["status"] == "converted"
    assert decision["proposal"]["event_id"] == converted_event["id"]
    assert decision["proposal"]["visit_id"] == converted_visit["id"]
    assert len((await client.get("/api/review-labels")).json()) == len(initial_review_labels)


async def test_detection_proposal_can_be_created_and_listed_for_media(
    client: httpx.AsyncClient,
) -> None:
    media_asset = (await import_image(client)).json()["media_asset"]

    response = await create_proposal(client, media_asset["id"])

    assert response.status_code == 201
    proposal = response.json()
    assert proposal["media_asset_id"] == media_asset["id"]
    assert proposal["stream_id"] == STREAM_ID
    assert proposal["zone_id"] == FEEDER_ZONE_ID
    assert proposal["label"] == "animal_candidate"
    assert proposal["confidence"] == 0.82
    assert proposal["bbox"]["width"] == 0.25
    assert proposal["status"] == "proposed"
    assert proposal["event_id"] is None
    assert proposal["visit_id"] is None

    assert (await client.get(f"/api/detection-runs/{proposal['run_id']}")).status_code == 200
    run_proposals = await client.get(f"/api/detection-runs/{proposal['run_id']}/proposals")
    all_proposals = await client.get("/api/detection-proposals")
    local_status = await client.get("/api/settings/local-data")

    assert run_proposals.status_code == 200
    assert [item["id"] for item in run_proposals.json()] == [proposal["id"]]
    assert any(item["id"] == proposal["id"] for item in all_proposals.json())
    assert local_status.json()["detection_run_count"] == 1
    assert local_status.json()["detection_proposal_count"] == 1


async def test_detection_proposal_requires_existing_media_asset(client: httpx.AsyncClient) -> None:
    response = await create_proposal(client, "media-asset-missing")

    assert response.status_code == 404
    assert "Media asset" in response.json()["detail"]


async def test_detection_proposal_requires_existing_zone_when_zone_is_supplied(
    client: httpx.AsyncClient,
) -> None:
    media_asset = (await import_image(client)).json()["media_asset"]

    response = await create_proposal(client, media_asset["id"], {"zone_id": "zone-missing"})

    assert response.status_code == 404
    assert "Zone" in response.json()["detail"]


async def test_detection_proposal_rejects_invalid_confidence(
    client: httpx.AsyncClient,
) -> None:
    media_asset = (await import_image(client)).json()["media_asset"]

    response = await create_proposal(client, media_asset["id"], {"confidence": 1.2})

    assert response.status_code == 422


async def test_detection_proposal_can_be_rejected_without_creating_review_records(
    client: httpx.AsyncClient,
) -> None:
    media_asset = (await import_image(client)).json()["media_asset"]
    proposal = (await create_proposal(client, media_asset["id"])).json()

    response = await client.post(
        f"/api/detection-proposals/{proposal['id']}/decision",
        json={"decision": "reject", "notes": "Not outdoor activity."},
    )

    assert response.status_code == 200
    result = response.json()
    assert result["proposal"]["status"] == "rejected"
    assert result["proposal"]["event_id"] is None
    assert result["proposal"]["visit_id"] is None
    assert result["event"] is None
    assert result["visit"] is None


async def test_detection_proposal_converts_to_reviewable_visit_and_detection_evidence(
    client: httpx.AsyncClient,
) -> None:
    media_asset = (await import_image(client)).json()["media_asset"]
    proposal = (await create_proposal(client, media_asset["id"])).json()

    response = await client.post(
        f"/api/detection-proposals/{proposal['id']}/decision",
        json={
            "decision": "convert_to_event",
            "event_title": "Review proposed feeder visitor",
            "subject_label": "unknown_bird",
            "species_guess": "unknown_bird",
            "notes": "Needs user correction before export.",
        },
    )

    assert response.status_code == 200
    result = response.json()
    event = result["event"]
    visit = result["visit"]
    assert result["proposal"]["status"] == "converted"
    assert result["proposal"]["event_id"] == event["id"]
    assert result["proposal"]["visit_id"] == visit["id"]
    assert event["review_status"] == "needs_review"
    assert event["primary_zone_id"] == FEEDER_ZONE_ID
    assert event["detections"][0]["label"] == "animal_candidate"
    assert event["detections"][0]["bbox"]["height"] == 0.2
    assert visit["review_status"] == "needs_review"
    assert visit["representative_media_path"] == media_asset["local_path"]

    queue = (await client.get("/api/review-queue")).json()
    queue_item = next(item for item in queue if item["visit_id"] == visit["id"])
    assert queue_item["media_asset"]["id"] == media_asset["id"]


async def test_converted_proposal_appears_as_detail_provenance(
    client: httpx.AsyncClient,
) -> None:
    media_asset = (await import_image(client)).json()["media_asset"]
    proposal = (await create_demo_run(client, media_asset["id"])).json()["proposals"][0]
    decision = (
        await client.post(
            f"/api/detection-proposals/{proposal['id']}/decision",
            json={"decision": "convert_to_event"},
        )
    ).json()
    event = decision["event"]
    visit = decision["visit"]

    event_detail = (await client.get(f"/api/events/{event['id']}/detail")).json()
    visit_detail = (await client.get(f"/api/visits/{visit['id']}/detail")).json()

    assert [item["id"] for item in event_detail["detection_proposals"]] == [proposal["id"]]
    assert [item["id"] for item in visit_detail["detection_proposals"]] == [proposal["id"]]
    assert [item["source"] for item in event_detail["detection_runs"]] == ["demo_rule"]
    assert [item["source"] for item in visit_detail["detection_runs"]] == ["demo_rule"]
    assert event_detail["detection_proposals"][0]["status"] == "converted"
    assert event_detail["detection_proposals"][0]["label"] == "bird"
    assert visit_detail["detection_proposals"][0]["confidence"] == 0.72
    assert visit_detail["review_summary"].startswith("Needs review")


async def test_converted_proposal_uses_correction_as_dataset_truth(
    client: httpx.AsyncClient,
) -> None:
    media_asset = (await import_image(client)).json()["media_asset"]
    proposal = (await create_proposal(client, media_asset["id"])).json()
    decision = (await client.post(
        f"/api/detection-proposals/{proposal['id']}/decision",
        json={"decision": "convert_to_event"},
    )).json()
    visit = decision["visit"]

    pre_correction_export = await client.post(
        "/api/dataset-exports",
        json={"name": "Proposal before correction"},
    )
    correction_response = await client.post(
        "/api/review-labels",
        json={"review_origin": "human", 
            "target_type": "visit",
            "target_id": visit["id"],
            "label": "blue_jay",
            "notes": "User-corrected proposal truth.",
        },
    )
    export_response = await client.post(
        "/api/dataset-exports",
        json={"name": "Proposal after correction"},
    )

    assert pre_correction_export.status_code == 201
    assert all(
        record["visit_id"] != visit["id"]
        for record in pre_correction_export.json()["manifest"]["records"]
    )
    assert correction_response.status_code == 201
    assert correction_response.json()["visit"]["reviewed_label"] == "blue_jay"
    assert export_response.status_code == 201
    record = next(
        record
        for record in export_response.json()["manifest"]["records"]
        if record["visit_id"] == visit["id"]
    )
    assert record["label"] == "blue_jay"
    assert record["label"] != "animal_candidate"
    assert record["detections"][0]["label"] == "animal_candidate"
