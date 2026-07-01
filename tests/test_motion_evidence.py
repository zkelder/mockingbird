from pathlib import Path

import httpx
import pytest

from mockingbird.api.main import app, configure_repository
from mockingbird.api.schemas import MotionEvidenceCreateRequest
from mockingbird.repository.product_repository import ProductRepository

pytestmark = pytest.mark.anyio

SOURCE_ID = "source-backyard-demo"
STREAM_ID = "stream-backyard-feeder"
FEEDER_ZONE_ID = "zone-feeder"
GROUND_ZONE_ID = "zone-ground"


@pytest.fixture(autouse=True)
def isolated_repository(tmp_path: Path) -> None:
    repository = ProductRepository(db_url=f"sqlite:///{tmp_path / 'mockingbird.sqlite3'}")
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


def motion_evidence_payload(**overrides):
    payload = {
        "zone_id": FEEDER_ZONE_ID,
        "start_frame_index": 10,
        "end_frame_index": 12,
        "best_frame_index": 11,
        "peak_changed_ratio": 0.42,
        "triggered_frame_count": 2,
        "scoring_config": {
            "pixel_delta_threshold": 25.0,
            "min_changed_ratio": 0.02,
            "max_gap_frames": 1,
            "source": "manual_frame_plane_api",
        },
        "notes": "Candidate feeder motion evidence.",
    }
    payload.update(overrides)
    return payload


async def create_motion_evidence(client: httpx.AsyncClient, **overrides):
    return await client.post(
        "/api/motion/evidence",
        json=motion_evidence_payload(**overrides),
    )


async def product_counts(client: httpx.AsyncClient) -> dict[str, int]:
    events = await client.get("/api/events")
    visits = await client.get("/api/visits")
    review_labels = await client.get("/api/review-labels")
    exports = await client.get("/api/dataset-exports")

    assert events.status_code == 200
    assert visits.status_code == 200
    assert review_labels.status_code == 200
    assert exports.status_code == 200

    return {
        "events": len(events.json()),
        "visits": len(visits.json()),
        "review_labels": len(review_labels.json()),
        "exports": len(exports.json()),
    }


async def test_create_motion_evidence_returns_pending_evidence(
    client: httpx.AsyncClient,
) -> None:
    response = await create_motion_evidence(client)

    assert response.status_code == 201
    evidence = response.json()
    assert evidence["id"].startswith("motion-evidence-")
    assert evidence["source_id"] == SOURCE_ID
    assert evidence["stream_id"] == STREAM_ID
    assert evidence["zone_id"] == FEEDER_ZONE_ID
    assert evidence["status"] == "pending"
    assert evidence["promoted_event_id"] is None
    assert evidence["promoted_visit_id"] is None
    assert evidence["snapshot_media_asset_id"] is None
    assert evidence["peak_changed_ratio"] == 0.42
    assert evidence["triggered_frame_count"] == 2
    assert evidence["scoring_config"]["pixel_delta_threshold"] == 25.0


async def test_created_motion_evidence_can_be_listed(client: httpx.AsyncClient) -> None:
    created = (await create_motion_evidence(client)).json()

    response = await client.get("/api/motion/evidence")

    assert response.status_code == 200
    assert [item["id"] for item in response.json()["motion_evidence"]] == [created["id"]]


async def test_motion_evidence_detail_route_returns_evidence(client: httpx.AsyncClient) -> None:
    created = (await create_motion_evidence(client)).json()

    response = await client.get(f"/api/motion/evidence/{created['id']}")

    assert response.status_code == 200
    assert response.json()["id"] == created["id"]
    assert response.json()["zone_id"] == FEEDER_ZONE_ID


async def test_motion_evidence_list_filters_by_status(client: httpx.AsyncClient) -> None:
    pending = (await create_motion_evidence(client)).json()
    ignored = (await create_motion_evidence(client, zone_id=GROUND_ZONE_ID)).json()
    await client.post(f"/api/motion/evidence/{ignored['id']}/ignore")

    pending_response = await client.get("/api/motion/evidence", params={"status": "pending"})
    ignored_response = await client.get("/api/motion/evidence", params={"status": "ignored"})

    assert pending_response.status_code == 200
    assert ignored_response.status_code == 200
    assert [item["id"] for item in pending_response.json()["motion_evidence"]] == [pending["id"]]
    assert [item["id"] for item in ignored_response.json()["motion_evidence"]] == [ignored["id"]]


async def test_motion_evidence_list_filters_by_zone_id(client: httpx.AsyncClient) -> None:
    feeder = (await create_motion_evidence(client)).json()
    await create_motion_evidence(client, zone_id=GROUND_ZONE_ID)

    response = await client.get(
        "/api/motion/evidence",
        params={"zone_id": FEEDER_ZONE_ID},
    )

    assert response.status_code == 200
    assert [item["id"] for item in response.json()["motion_evidence"]] == [feeder["id"]]


async def test_ignore_pending_motion_evidence_marks_ignored(
    client: httpx.AsyncClient,
) -> None:
    created = (await create_motion_evidence(client)).json()

    response = await client.post(f"/api/motion/evidence/{created['id']}/ignore")

    assert response.status_code == 200
    ignored = response.json()
    assert ignored["id"] == created["id"]
    assert ignored["status"] == "ignored"
    assert ignored["promoted_event_id"] is None
    assert ignored["promoted_visit_id"] is None


async def test_ignore_missing_motion_evidence_returns_404(client: httpx.AsyncClient) -> None:
    response = await client.post("/api/motion/evidence/motion-evidence-missing/ignore")

    assert response.status_code == 404
    assert "Motion Evidence" in response.json()["detail"]


async def test_ignoring_already_ignored_motion_evidence_returns_400(
    client: httpx.AsyncClient,
) -> None:
    created = (await create_motion_evidence(client)).json()
    await client.post(f"/api/motion/evidence/{created['id']}/ignore")

    response = await client.post(f"/api/motion/evidence/{created['id']}/ignore")

    assert response.status_code == 400
    assert "Only pending Motion Evidence can be ignored." == response.json()["detail"]


async def test_create_motion_evidence_does_not_create_product_truth(
    client: httpx.AsyncClient,
) -> None:
    before_counts = await product_counts(client)

    response = await create_motion_evidence(client)

    assert response.status_code == 201
    assert await product_counts(client) == before_counts


async def test_ignore_motion_evidence_does_not_create_or_delete_product_truth(
    client: httpx.AsyncClient,
) -> None:
    created = (await create_motion_evidence(client)).json()
    before_counts = await product_counts(client)

    response = await client.post(f"/api/motion/evidence/{created['id']}/ignore")

    assert response.status_code == 200
    assert await product_counts(client) == before_counts


async def test_no_motion_evidence_promote_endpoint_exists(client: httpx.AsyncClient) -> None:
    created = (await create_motion_evidence(client)).json()

    response = await client.post(f"/api/motion/evidence/{created['id']}/promote")

    assert response.status_code == 404


async def test_invalid_peak_changed_ratio_returns_422(client: httpx.AsyncClient) -> None:
    response = await create_motion_evidence(client, peak_changed_ratio=1.2)

    assert response.status_code == 422


async def test_invalid_frame_index_range_returns_422(client: httpx.AsyncClient) -> None:
    response = await create_motion_evidence(
        client,
        start_frame_index=12,
        end_frame_index=10,
        best_frame_index=11,
    )

    assert response.status_code == 422


async def test_motion_evidence_persists_after_repository_reload(tmp_path: Path) -> None:
    db_path = tmp_path / "motion-evidence.sqlite3"
    repository = ProductRepository(db_url=f"sqlite:///{db_path}")

    created = repository.create_motion_evidence(
        MotionEvidenceCreateRequest(
            zone_id=FEEDER_ZONE_ID,
            start_frame_index=20,
            end_frame_index=22,
            best_frame_index=21,
            peak_changed_ratio=0.55,
            triggered_frame_count=3,
            scoring_config={"pixel_delta_threshold": 25.0},
        )
    )

    reloaded_repository = ProductRepository(db_url=f"sqlite:///{db_path}")
    persisted = reloaded_repository.get_motion_evidence(created.id)

    assert persisted is not None
    assert persisted.id == created.id
    assert persisted.status == created.status
    assert persisted.zone_id == FEEDER_ZONE_ID
    assert persisted.peak_changed_ratio == 0.55
