from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from mockingbird.api.main import app, configure_repository
from mockingbird.api.schemas import MotionEvidenceCreateRequest
from mockingbird.repository.product_repository import ProductRepository
from mockingbird.storage.models import MediaAssetModel
from tests.conftest import LegacyAuthenticatedTestClient, de_demo_seeded_source

pytestmark = pytest.mark.anyio

SOURCE_ID = "source-backyard-demo"
STREAM_ID = "stream-backyard-feeder"
FEEDER_ZONE_ID = "zone-feeder"
GROUND_ZONE_ID = "zone-ground"
IGNORE_ZONE_ID = "zone-ignore-driveway-edge"


@pytest.fixture(autouse=True)
def isolated_repository(tmp_path: Path) -> ProductRepository:
    repository = ProductRepository(db_url=f"sqlite:///{tmp_path / 'mockingbird.sqlite3'}")
    de_demo_seeded_source(repository)
    configure_repository(repository)
    yield repository
    configure_repository(None)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with LegacyAuthenticatedTestClient(transport=transport, base_url="http://testserver") as api_client:
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


async def create_privacy_zone(client: httpx.AsyncClient) -> str:
    response = await client.post(
        "/api/zones",
        json={
            "stream_id": STREAM_ID,
            "name": "Test privacy zone",
            "zone_type": "privacy",
            "polygon": [
                {"x": 0.1, "y": 0.1},
                {"x": 0.2, "y": 0.1},
                {"x": 0.2, "y": 0.2},
            ],
            "is_active": True,
        },
    )
    assert response.status_code == 201
    return response.json()["zone"]["id"]


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


async def dataset_coverage(client: httpx.AsyncClient) -> dict:
    response = await client.get("/api/dataset-coverage/summary")
    assert response.status_code == 200
    return response.json()


def coverage_truth_counts(coverage: dict) -> dict[str, int]:
    return {
        "export_ready_count": coverage["export_ready_count"],
        "reviewed_record_count": coverage["reviewed_record_count"],
    }


def add_test_media_asset(
    repository: ProductRepository,
    media_id: str = "media_best_frame_001",
    stream_id: str = STREAM_ID,
    source_id: str | None = SOURCE_ID,
) -> MediaAssetModel:
    asset = MediaAssetModel(
        id=media_id,
        source_id=source_id,
        stream_id=stream_id,
        filename=f"{media_id}.jpg",
        content_type="image/jpeg",
        media_type="image",
        local_path=f"demo://motion-evidence/{media_id}.jpg",
        original_filename=f"{media_id}.jpg",
        file_size_bytes=128,
        created_at=datetime.now(UTC),
        notes="Test-only local media reference.",
    )
    with repository.session_factory() as session:
        with session.begin():
            session.add(asset)
    return asset


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


async def test_zone_optional_motion_evidence_promotes_to_review_without_truth(
    client: httpx.AsyncClient,
    isolated_repository: ProductRepository,
) -> None:
    asset = add_test_media_asset(
        isolated_repository,
        media_id="media_zone_optional_activity",
    )
    before_counts = await product_counts(client)

    created_response = await create_motion_evidence(
        client,
        zone_id=None,
        stream_id=STREAM_ID,
        snapshot_media_asset_id=asset.id,
        scoring_config={
            "source": "automatic_activity_test",
            "activity_region_kind": "auto_area",
            "activity_region_id": "auto-region:test",
            "activity_left": 0.2,
            "activity_top": 0.3,
            "activity_right": 0.4,
            "activity_bottom": 0.5,
            "best_frame_width": 100,
            "best_frame_height": 100,
        },
    )

    assert created_response.status_code == 201
    evidence = created_response.json()
    assert evidence["zone_id"] is None
    assert evidence["status"] == "pending"

    promoted_response = await client.post(
        f"/api/motion/evidence/{evidence['id']}/promote",
        json={"create_event": True, "create_visit": True},
    )

    assert promoted_response.status_code == 200
    promoted = promoted_response.json()
    assert promoted["evidence"]["zone_id"] is None
    assert promoted["event_id"].startswith("event-motion-")
    assert promoted["visit_id"].startswith("visit-motion-")

    queue_response = await client.get("/api/review-queue")
    assert queue_response.status_code == 200
    queue_item = next(
        item
        for item in queue_response.json()
        if item["visit_id"] == promoted["visit_id"]
    )
    assert queue_item["primary_zone_id"] is None
    assert queue_item["zone_id"] is None
    assert queue_item["focus_crop_source"] == "activity"
    assert queue_item["review_status"] == "needs_review"

    after_counts = await product_counts(client)
    assert after_counts["events"] == before_counts["events"] + 1
    assert after_counts["visits"] == before_counts["visits"] + 1
    assert after_counts["review_labels"] == before_counts["review_labels"]
    assert after_counts["exports"] == before_counts["exports"]


async def test_zone_optional_motion_evidence_requires_stream_context(
    client: httpx.AsyncClient,
) -> None:
    before_counts = await product_counts(client)

    response = await create_motion_evidence(
        client,
        zone_id=None,
        stream_id=None,
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Stream 'motion evidence stream' was not found."
    assert await product_counts(client) == before_counts


async def test_created_motion_evidence_can_be_listed(client: httpx.AsyncClient) -> None:
    created = (await create_motion_evidence(client)).json()

    response = await client.get("/api/motion/evidence")

    assert response.status_code == 200
    assert [item["id"] for item in response.json()["motion_evidence"]] == [created["id"]]


async def test_motion_evidence_snapshot_media_reference_survives_list_and_detail(
    client: httpx.AsyncClient,
    isolated_repository: ProductRepository,
) -> None:
    asset = add_test_media_asset(isolated_repository)
    before_counts = await product_counts(client)
    before_coverage = await dataset_coverage(client)

    response = await create_motion_evidence(client, snapshot_media_asset_id=asset.id)

    assert response.status_code == 201
    created = response.json()
    assert created["status"] == "pending"
    assert created["snapshot_media_asset_id"] == asset.id

    list_response = await client.get("/api/motion/evidence")
    detail_response = await client.get(f"/api/motion/evidence/{created['id']}")

    assert list_response.status_code == 200
    assert detail_response.status_code == 200
    assert list_response.json()["motion_evidence"][0]["snapshot_media_asset_id"] == asset.id
    assert detail_response.json()["snapshot_media_asset_id"] == asset.id
    assert await product_counts(client) == before_counts
    assert coverage_truth_counts(await dataset_coverage(client)) == coverage_truth_counts(
        before_coverage
    )


async def test_create_motion_evidence_with_existing_media_asset_stays_pending_without_truth(
    client: httpx.AsyncClient,
    isolated_repository: ProductRepository,
) -> None:
    asset = add_test_media_asset(isolated_repository, media_id="media_best_frame_create_001")
    before_counts = await product_counts(client)
    before_coverage = await dataset_coverage(client)

    response = await create_motion_evidence(client, snapshot_media_asset_id=asset.id)

    assert response.status_code == 201
    created = response.json()
    assert created["status"] == "pending"
    assert created["snapshot_media_asset_id"] == asset.id
    assert created["promoted_event_id"] is None
    assert created["promoted_visit_id"] is None

    detail_response = await client.get(f"/api/motion/evidence/{created['id']}")
    assert detail_response.status_code == 200
    assert detail_response.json()["snapshot_media_asset_id"] == asset.id
    assert await product_counts(client) == before_counts
    assert coverage_truth_counts(await dataset_coverage(client)) == coverage_truth_counts(
        before_coverage
    )


async def test_create_motion_evidence_rejects_media_from_another_stream(
    client: httpx.AsyncClient,
    isolated_repository: ProductRepository,
) -> None:
    asset = add_test_media_asset(
        isolated_repository,
        media_id="media_best_frame_other_stream",
        stream_id="stream-other-local-media",
    )
    before_counts = await product_counts(client)
    before_coverage = await dataset_coverage(client)

    response = await create_motion_evidence(client, snapshot_media_asset_id=asset.id)

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "Motion evidence snapshot media must belong to the selected stream."
    )
    assert await product_counts(client) == before_counts
    assert coverage_truth_counts(await dataset_coverage(client)) == coverage_truth_counts(
        before_coverage
    )


async def test_attach_existing_media_asset_to_pending_motion_evidence(
    client: httpx.AsyncClient,
    isolated_repository: ProductRepository,
) -> None:
    asset = add_test_media_asset(isolated_repository)
    created = (await create_motion_evidence(client)).json()
    before_counts = await product_counts(client)
    before_coverage = await dataset_coverage(client)

    response = await client.post(
        f"/api/motion/evidence/{created['id']}/attach-media",
        json={"snapshot_media_asset_id": asset.id},
    )

    assert response.status_code == 200
    attached = response.json()
    assert attached["id"] == created["id"]
    assert attached["status"] == "pending"
    assert attached["snapshot_media_asset_id"] == asset.id

    list_response = await client.get("/api/motion/evidence")
    detail_response = await client.get(f"/api/motion/evidence/{created['id']}")

    assert list_response.status_code == 200
    assert detail_response.status_code == 200
    assert list_response.json()["motion_evidence"][0]["snapshot_media_asset_id"] == asset.id
    assert detail_response.json()["snapshot_media_asset_id"] == asset.id
    assert await product_counts(client) == before_counts
    assert coverage_truth_counts(await dataset_coverage(client)) == coverage_truth_counts(
        before_coverage
    )


async def test_clear_motion_evidence_media_attachment(
    client: httpx.AsyncClient,
    isolated_repository: ProductRepository,
) -> None:
    asset = add_test_media_asset(isolated_repository)
    created = (
        await create_motion_evidence(
            client,
            snapshot_media_asset_id=asset.id,
        )
    ).json()

    response = await client.post(
        f"/api/motion/evidence/{created['id']}/attach-media",
        json={"snapshot_media_asset_id": None},
    )

    assert response.status_code == 200
    assert response.json()["snapshot_media_asset_id"] is None
    detail_response = await client.get(f"/api/motion/evidence/{created['id']}")
    assert detail_response.status_code == 200
    assert detail_response.json()["snapshot_media_asset_id"] is None


async def test_attach_missing_media_asset_to_motion_evidence_fails_safely(
    client: httpx.AsyncClient,
) -> None:
    created = (await create_motion_evidence(client)).json()
    before_counts = await product_counts(client)
    before_coverage = await dataset_coverage(client)

    response = await client.post(
        f"/api/motion/evidence/{created['id']}/attach-media",
        json={"snapshot_media_asset_id": "media_best_frame_missing"},
    )

    assert response.status_code == 404
    assert "Media asset" in response.json()["detail"]
    detail_response = await client.get(f"/api/motion/evidence/{created['id']}")
    assert detail_response.status_code == 200
    assert detail_response.json()["snapshot_media_asset_id"] is None
    assert await product_counts(client) == before_counts
    assert coverage_truth_counts(await dataset_coverage(client)) == coverage_truth_counts(
        before_coverage
    )


async def test_attach_media_to_missing_motion_evidence_returns_404(
    client: httpx.AsyncClient,
    isolated_repository: ProductRepository,
) -> None:
    asset = add_test_media_asset(isolated_repository)

    response = await client.post(
        "/api/motion/evidence/motion-evidence-missing/attach-media",
        json={"snapshot_media_asset_id": asset.id},
    )

    assert response.status_code == 404
    assert "Motion Evidence" in response.json()["detail"]


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


async def test_ignore_preserves_snapshot_media_reference(
    client: httpx.AsyncClient,
    isolated_repository: ProductRepository,
) -> None:
    asset = add_test_media_asset(isolated_repository)
    created = (
        await create_motion_evidence(
            client,
            snapshot_media_asset_id=asset.id,
        )
    ).json()
    before_counts = await product_counts(client)
    before_coverage = await dataset_coverage(client)

    response = await client.post(f"/api/motion/evidence/{created['id']}/ignore")

    assert response.status_code == 200
    ignored = response.json()
    assert ignored["status"] == "ignored"
    assert ignored["snapshot_media_asset_id"] == asset.id
    detail_response = await client.get(f"/api/motion/evidence/{created['id']}")
    assert detail_response.status_code == 200
    assert detail_response.json()["snapshot_media_asset_id"] == asset.id
    assert await product_counts(client) == before_counts
    assert coverage_truth_counts(await dataset_coverage(client)) == coverage_truth_counts(
        before_coverage
    )


async def test_attach_media_to_ignored_motion_evidence_returns_400(
    client: httpx.AsyncClient,
    isolated_repository: ProductRepository,
) -> None:
    asset = add_test_media_asset(isolated_repository)
    created = (await create_motion_evidence(client)).json()
    await client.post(f"/api/motion/evidence/{created['id']}/ignore")

    response = await client.post(
        f"/api/motion/evidence/{created['id']}/attach-media",
        json={"snapshot_media_asset_id": asset.id},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Ignored Motion Evidence cannot change media attachment."
    detail_response = await client.get(f"/api/motion/evidence/{created['id']}")
    assert detail_response.status_code == 200
    assert detail_response.json()["snapshot_media_asset_id"] is None


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


async def test_missing_snapshot_media_reference_fails_safely(
    client: httpx.AsyncClient,
) -> None:
    before_counts = await product_counts(client)
    before_coverage = await dataset_coverage(client)

    response = await create_motion_evidence(
        client,
        snapshot_media_asset_id="media_best_frame_missing",
    )

    assert response.status_code == 404
    assert "Media asset" in response.json()["detail"]
    assert await product_counts(client) == before_counts
    assert coverage_truth_counts(await dataset_coverage(client)) == coverage_truth_counts(
        before_coverage
    )


async def test_ignore_motion_evidence_does_not_create_or_delete_product_truth(
    client: httpx.AsyncClient,
) -> None:
    created = (await create_motion_evidence(client)).json()
    before_counts = await product_counts(client)

    response = await client.post(f"/api/motion/evidence/{created['id']}/ignore")

    assert response.status_code == 200
    assert await product_counts(client) == before_counts


async def test_promote_pending_motion_evidence_creates_unreviewed_event_visit(
    client: httpx.AsyncClient,
) -> None:
    created = (await create_motion_evidence(client)).json()
    before_counts = await product_counts(client)
    before_coverage = await dataset_coverage(client)

    response = await client.post(
        f"/api/motion/evidence/{created['id']}/promote",
        json={
            "event_title": "Motion evidence at feeder",
            "visit_label_hint": "unknown_bird",
        },
    )

    assert response.status_code == 200
    result = response.json()
    evidence = result["evidence"]
    assert evidence["id"] == created["id"]
    assert evidence["status"] == "promoted"
    assert result["event_id"] == evidence["promoted_event_id"]
    assert result["visit_id"] == evidence["promoted_visit_id"]

    after_counts = await product_counts(client)
    assert after_counts["events"] == before_counts["events"] + 1
    assert after_counts["visits"] == before_counts["visits"] + 1
    assert after_counts["review_labels"] == before_counts["review_labels"]
    assert after_counts["exports"] == before_counts["exports"]

    event_response = await client.get(f"/api/events/{result['event_id']}")
    visit_response = await client.get(f"/api/visits/{result['visit_id']}")
    evidence_response = await client.get(f"/api/motion/evidence/{created['id']}")
    event_detail_response = await client.get(f"/api/events/{result['event_id']}/detail")
    visit_detail_response = await client.get(f"/api/visits/{result['visit_id']}/detail")

    assert event_response.status_code == 200
    assert visit_response.status_code == 200
    assert evidence_response.status_code == 200
    assert event_detail_response.status_code == 200
    assert visit_detail_response.status_code == 200

    event = event_response.json()
    visit = visit_response.json()
    assert event["title"] == "Motion evidence at feeder"
    assert event["event_type"] == "motion_evidence"
    assert event["primary_zone_id"] == FEEDER_ZONE_ID
    assert event["review_status"] == "needs_review"
    assert event["detections"] == []
    assert visit["event_id"] == event["id"]
    assert visit["subject_label"] == "unknown_bird"
    assert visit["species_guess"] is None
    assert visit["confidence"] is None
    assert visit["reviewed_label"] is None
    assert visit["review_status"] == "needs_review"
    assert visit["representative_media_path"] is None
    assert event_detail_response.json()["dataset_ready"] is False
    assert visit_detail_response.json()["dataset_ready"] is False
    assert evidence_response.json()["status"] == "promoted"

    after_coverage = await dataset_coverage(client)
    assert after_coverage["export_ready_count"] == before_coverage["export_ready_count"]
    assert after_coverage["reviewed_record_count"] == before_coverage["reviewed_record_count"]


async def test_promote_motion_evidence_can_create_event_without_visit(
    client: httpx.AsyncClient,
) -> None:
    created = (await create_motion_evidence(client)).json()
    before_counts = await product_counts(client)

    response = await client.post(
        f"/api/motion/evidence/{created['id']}/promote",
        json={"create_visit": False},
    )

    assert response.status_code == 200
    result = response.json()
    assert result["event_id"] is not None
    assert result["visit_id"] is None
    assert result["evidence"]["promoted_event_id"] == result["event_id"]
    assert result["evidence"]["promoted_visit_id"] is None

    after_counts = await product_counts(client)
    assert after_counts["events"] == before_counts["events"] + 1
    assert after_counts["visits"] == before_counts["visits"]
    assert after_counts["review_labels"] == before_counts["review_labels"]
    assert after_counts["exports"] == before_counts["exports"]


async def test_attach_media_to_promoted_motion_evidence_returns_400(
    client: httpx.AsyncClient,
    isolated_repository: ProductRepository,
) -> None:
    asset = add_test_media_asset(isolated_repository)
    created = (await create_motion_evidence(client)).json()
    promote_response = await client.post(f"/api/motion/evidence/{created['id']}/promote")
    assert promote_response.status_code == 200

    response = await client.post(
        f"/api/motion/evidence/{created['id']}/attach-media",
        json={"snapshot_media_asset_id": asset.id},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Promoted Motion Evidence cannot change media attachment."
    detail_response = await client.get(f"/api/motion/evidence/{created['id']}")
    assert detail_response.status_code == 200
    assert detail_response.json()["snapshot_media_asset_id"] is None


async def test_repeated_motion_evidence_promotion_is_rejected_without_duplicates(
    client: httpx.AsyncClient,
) -> None:
    created = (await create_motion_evidence(client)).json()
    first_response = await client.post(f"/api/motion/evidence/{created['id']}/promote")
    assert first_response.status_code == 200
    counts_after_first_promotion = await product_counts(client)

    response = await client.post(f"/api/motion/evidence/{created['id']}/promote")

    assert response.status_code == 400
    assert response.json()["detail"] == "Motion Evidence has already been promoted."
    assert await product_counts(client) == counts_after_first_promotion


async def test_ignored_motion_evidence_promotion_is_rejected(
    client: httpx.AsyncClient,
) -> None:
    created = (await create_motion_evidence(client)).json()
    await client.post(f"/api/motion/evidence/{created['id']}/ignore")
    before_counts = await product_counts(client)

    response = await client.post(f"/api/motion/evidence/{created['id']}/promote")

    assert response.status_code == 400
    assert response.json()["detail"] == "Ignored Motion Evidence cannot be promoted."
    assert await product_counts(client) == before_counts


async def test_missing_motion_evidence_promotion_returns_404(client: httpx.AsyncClient) -> None:
    response = await client.post("/api/motion/evidence/motion-evidence-missing/promote")

    assert response.status_code == 404
    assert "Motion Evidence" in response.json()["detail"]


async def test_empty_motion_evidence_promotion_request_returns_400(
    client: httpx.AsyncClient,
) -> None:
    created = (await create_motion_evidence(client)).json()
    before_counts = await product_counts(client)

    response = await client.post(
        f"/api/motion/evidence/{created['id']}/promote",
        json={"create_event": False, "create_visit": False},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Promotion must create an Event or Visit."
    assert await product_counts(client) == before_counts


async def test_motion_evidence_promotion_rejects_visit_without_event(
    client: httpx.AsyncClient,
) -> None:
    created = (await create_motion_evidence(client)).json()

    response = await client.post(
        f"/api/motion/evidence/{created['id']}/promote",
        json={"create_event": False, "create_visit": True},
    )

    assert response.status_code == 400
    assert (
        response.json()["detail"]
        == "Motion Evidence promotion cannot create a Visit without an Event."
    )


async def test_ignore_zone_motion_evidence_promotion_is_rejected(
    client: httpx.AsyncClient,
) -> None:
    created = (await create_motion_evidence(client, zone_id=IGNORE_ZONE_ID)).json()
    before_counts = await product_counts(client)

    response = await client.post(f"/api/motion/evidence/{created['id']}/promote")

    assert response.status_code == 400
    assert (
        response.json()["detail"]
        == "Motion Evidence in privacy or ignore zones cannot be promoted."
    )
    assert await product_counts(client) == before_counts
    evidence_response = await client.get(f"/api/motion/evidence/{created['id']}")
    assert evidence_response.json()["status"] == "pending"


async def test_privacy_zone_motion_evidence_promotion_is_rejected(
    client: httpx.AsyncClient,
) -> None:
    privacy_zone_id = await create_privacy_zone(client)
    created = (await create_motion_evidence(client, zone_id=privacy_zone_id)).json()
    before_counts = await product_counts(client)

    response = await client.post(f"/api/motion/evidence/{created['id']}/promote")

    assert response.status_code == 400
    assert (
        response.json()["detail"]
        == "Motion Evidence in privacy or ignore zones cannot be promoted."
    )
    assert await product_counts(client) == before_counts


async def test_motion_evidence_promotion_preserves_snapshot_media_reference(
    client: httpx.AsyncClient,
    isolated_repository: ProductRepository,
) -> None:
    asset = add_test_media_asset(isolated_repository)
    created = (
        await create_motion_evidence(
            client,
            snapshot_media_asset_id=asset.id,
        )
    ).json()
    before_counts = await product_counts(client)
    before_coverage = await dataset_coverage(client)

    response = await client.post(f"/api/motion/evidence/{created['id']}/promote")

    assert response.status_code == 200
    result = response.json()
    assert result["evidence"]["snapshot_media_asset_id"] == asset.id
    assert result["evidence"]["status"] == "promoted"

    evidence_response = await client.get(f"/api/motion/evidence/{created['id']}")
    visit_response = await client.get(f"/api/visits/{result['visit_id']}")
    event_detail_response = await client.get(f"/api/events/{result['event_id']}/detail")
    visit_detail_response = await client.get(f"/api/visits/{result['visit_id']}/detail")

    assert evidence_response.status_code == 200
    assert visit_response.status_code == 200
    assert event_detail_response.status_code == 200
    assert visit_detail_response.status_code == 200
    assert evidence_response.json()["snapshot_media_asset_id"] == asset.id
    # Everyday Product / Discovery UX Closure v1: `representative_media_path`
    # is now redacted on every API response (it is a server-local filesystem
    # path -- see api/schemas.py's "Never expose its local path" contract on
    # its sibling VisitEvidenceFrame). Verify the underlying Visit->MediaAsset
    # link directly against the repository instead of the now-redacted field.
    assert visit_response.json()["representative_media_path"] is None
    assert isolated_repository.get_visit(result["visit_id"]).representative_media_path == asset.local_path
    assert event_detail_response.json()["media_asset"]["id"] == asset.id
    assert visit_detail_response.json()["media_asset"]["id"] == asset.id
    assert event_detail_response.json()["dataset_ready"] is False
    assert visit_detail_response.json()["dataset_ready"] is False

    after_counts = await product_counts(client)
    assert after_counts["events"] == before_counts["events"] + 1
    assert after_counts["visits"] == before_counts["visits"] + 1
    assert after_counts["review_labels"] == before_counts["review_labels"]
    assert after_counts["exports"] == before_counts["exports"]

    after_coverage = await dataset_coverage(client)
    assert after_coverage["export_ready_count"] == before_coverage["export_ready_count"]
    assert after_coverage["reviewed_record_count"] == before_coverage["reviewed_record_count"]


async def test_attached_motion_evidence_media_is_preserved_on_promotion(
    client: httpx.AsyncClient,
    isolated_repository: ProductRepository,
) -> None:
    asset = add_test_media_asset(isolated_repository, media_id="media_best_frame_003")
    created = (await create_motion_evidence(client)).json()

    attach_response = await client.post(
        f"/api/motion/evidence/{created['id']}/attach-media",
        json={"snapshot_media_asset_id": asset.id},
    )
    assert attach_response.status_code == 200

    response = await client.post(f"/api/motion/evidence/{created['id']}/promote")

    assert response.status_code == 200
    result = response.json()
    assert result["evidence"]["snapshot_media_asset_id"] == asset.id
    evidence_response = await client.get(f"/api/motion/evidence/{created['id']}")
    visit_detail_response = await client.get(f"/api/visits/{result['visit_id']}/detail")
    assert evidence_response.status_code == 200
    assert visit_detail_response.status_code == 200
    assert evidence_response.json()["snapshot_media_asset_id"] == asset.id
    assert visit_detail_response.json()["media_asset"]["id"] == asset.id


async def test_motion_evidence_promotion_can_attach_snapshot_media_reference(
    client: httpx.AsyncClient,
    isolated_repository: ProductRepository,
) -> None:
    asset = add_test_media_asset(isolated_repository, media_id="media_best_frame_002")
    created = (await create_motion_evidence(client)).json()

    response = await client.post(
        f"/api/motion/evidence/{created['id']}/promote",
        json={"attach_snapshot_media_asset_id": asset.id},
    )

    assert response.status_code == 200
    result = response.json()
    assert result["evidence"]["snapshot_media_asset_id"] == asset.id
    visit_response = await client.get(f"/api/visits/{result['visit_id']}")
    visit_detail_response = await client.get(f"/api/visits/{result['visit_id']}/detail")
    assert visit_response.status_code == 200
    assert visit_detail_response.status_code == 200
    # Everyday Product / Discovery UX Closure v1: see the identical comment in
    # test_motion_evidence_promotion_preserves_snapshot_media_reference above.
    assert visit_response.json()["representative_media_path"] is None
    assert isolated_repository.get_visit(result["visit_id"]).representative_media_path == asset.local_path
    assert visit_detail_response.json()["media_asset"]["id"] == asset.id


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
