from pathlib import Path

import httpx
import pytest

from mockingbird.api.main import app, configure_repository
from mockingbird.api.schemas import SourceKind, SourceStatus
from mockingbird.repository.product_repository import ProductRepository
from mockingbird.storage.models import CameraSourceModel, StreamModel, ZoneModel
from tests.conftest import LegacyAuthenticatedTestClient

pytestmark = pytest.mark.anyio

SOURCE_ID = "source-backyard-demo"
STREAM_ID = "stream-backyard-feeder"
FEEDER_ZONE_ID = "zone-feeder"
IGNORE_ZONE_ID = "zone-ignore-driveway-edge"
OTHER_SOURCE_ID = "source-other-webhook-smoke"
OTHER_STREAM_ID = "stream-other-webhook-smoke"
OTHER_ZONE_ID = "zone-other-webhook-smoke"
SIDE_STREAM_ID = "stream-side-webhook-smoke"
SIDE_ZONE_ID = "zone-side-webhook-smoke"


@pytest.fixture(autouse=True)
def isolated_repository(tmp_path: Path) -> ProductRepository:
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
    async with LegacyAuthenticatedTestClient(transport=transport, base_url="http://testserver") as api_client:
        yield api_client


def fail_if_runtime_is_called(*_args, **_kwargs) -> None:
    raise AssertionError("Webhook smoke flow must not call media/model runtimes")


async def configure_webhook_source(client: httpx.AsyncClient) -> dict:
    response = await client.patch(
        f"/api/sources/{SOURCE_ID}/provider-configuration",
        json={
            "provider_key": "webhook_future",
            "config": {
                "endpoint_name": "backyard-webhook",
                "shared_secret_configured": "redact-me",
                "default_stream_id": STREAM_ID,
                "default_zone_id": FEEDER_ZONE_ID,
                "allowed_source_name": "backyard-webhook",
            },
        },
    )
    assert response.status_code == 200
    return response.json()


def webhook_motion_payload(external_event_id: str = "webhook-smoke-motion-1") -> dict:
    return {
        "type": "motion",
        "source_name": "backyard-webhook",
        "external_event_id": external_event_id,
        "stream_id": STREAM_ID,
        "zone_id": FEEDER_ZONE_ID,
        "label": "northern_cardinal",
        "confidence": 0.84,
        "timestamp": "2026-07-04T12:00:00Z",
        "notes": "external payload note should not become truth",
    }


async def product_counts(client: httpx.AsyncClient) -> dict[str, int]:
    responses = {
        "events": await client.get("/api/events"),
        "visits": await client.get("/api/visits"),
        "review_labels": await client.get("/api/review-labels"),
        "motion_evidence": await client.get("/api/motion/evidence"),
        "species_suggestions": await client.get("/api/species-suggestions"),
        "detection_proposals": await client.get("/api/detection-proposals"),
        "dataset_exports": await client.get("/api/dataset-exports"),
        "media_assets": await client.get("/api/media"),
    }
    assert all(response.status_code == 200 for response in responses.values())

    return {
        "events": len(responses["events"].json()),
        "visits": len(responses["visits"].json()),
        "review_labels": len(responses["review_labels"].json()),
        "motion_evidence": len(responses["motion_evidence"].json()["motion_evidence"]),
        "species_suggestions": len(responses["species_suggestions"].json()["species_suggestions"]),
        "detection_proposals": len(responses["detection_proposals"].json()),
        "dataset_exports": len(responses["dataset_exports"].json()),
        "media_assets": len(responses["media_assets"].json()),
    }


def assert_count_delta(
    before: dict[str, int],
    after: dict[str, int],
    **expected_delta: int,
) -> None:
    for key, before_value in before.items():
        assert after[key] == before_value + expected_delta.get(key, 0), key


async def dataset_truth_counts(client: httpx.AsyncClient) -> dict[str, int]:
    response = await client.get("/api/dataset-coverage/summary")
    assert response.status_code == 200
    coverage = response.json()
    return {
        "reviewed_record_count": coverage["reviewed_record_count"],
        "export_ready_count": coverage["export_ready_count"],
    }


async def analytics_species_count(client: httpx.AsyncClient, label: str) -> int:
    response = await client.get("/api/analytics/summary")
    assert response.status_code == 200
    return response.json()["species_counts"].get(label, 0)


def assert_dry_run_creates_nothing(body: dict) -> None:
    assert body["dry_run"] is True
    assert body["would_create_media_asset"] is False
    assert body["would_create_motion_evidence"] is False
    assert body["would_create_event"] is False
    assert body["would_create_visit"] is False
    assert body["would_create_review_label"] is False
    assert body["would_create_species_suggestion"] is False
    assert body["would_create_detection_proposal"] is False
    assert body["would_create_truth"] is False


def assert_motion_response_creates_only_evidence(body: dict, creates: bool) -> None:
    assert body["creates_motion_evidence"] is creates
    assert body["creates_media_asset"] is False
    assert body["creates_event"] is False
    assert body["creates_visit"] is False
    assert body["creates_review_label"] is False
    assert body["creates_truth"] is False


async def assert_webhook_status_is_honest(client: httpx.AsyncClient) -> None:
    configuration_response = await client.get(f"/api/sources/{SOURCE_ID}/provider-configuration")
    connection_response = await client.get(f"/api/sources/{SOURCE_ID}/connection")
    setup_response = await client.get(f"/api/sources/{SOURCE_ID}/setup-review")
    playback_response = await client.get(f"/api/streams/{STREAM_ID}/playback")
    assert [
        configuration_response.status_code,
        connection_response.status_code,
        setup_response.status_code,
        playback_response.status_code,
    ] == [200, 200, 200, 200]

    configuration = configuration_response.json()
    connection = connection_response.json()
    setup = setup_response.json()
    playback = playback_response.json()

    assert configuration["provider_key"] == "webhook_future"
    assert configuration["supports_live_playback"] is False
    assert configuration["supports_zone_editing"] is True
    assert configuration["safe_config_preview"]["shared_secret_configured"] == "configured"
    assert "redact-me" not in str(configuration)

    assert connection["status"] == "configured"
    assert connection["provider_kind"] == "future_adapter"
    assert connection["adapter_key"] == "webhook_future"
    assert connection["supports_live_playback"] is False
    assert connection["supports_zone_editing"] is True
    assert "pending MotionEvidence only" in connection["setup_hint"]

    assert setup["provider_key"] == "webhook_future"
    assert setup["readiness_level"] == "future_adapter_required"
    assert setup["supports_live_playback"] is False
    assert setup["supports_zone_editing"] is True
    assert any(step["key"] == "webhook_future_ingest" for step in setup["steps"])

    assert playback["stream_id"] == STREAM_ID
    assert playback["source_id"] == SOURCE_ID
    assert playback["adapter_key"] == "webhook_future"
    assert playback["playback_kind"] == "placeholder"
    assert playback["supports_live_playback"] is False
    assert playback["supports_zone_editing"] is True
    assert playback["preview_media_asset_id"] is None
    assert playback["preview_url"] is None


def add_context_validation_records(repository: ProductRepository) -> None:
    with repository.session_factory() as session:
        with session.begin():
            session.add(
                CameraSourceModel(
                    id=OTHER_SOURCE_ID,
                    name="Other webhook smoke source",
                    kind=SourceKind.webhook.value,
                    status=SourceStatus.needs_setup.value,
                    description="Other source for webhook smoke context validation.",
                )
            )
            session.add(
                StreamModel(
                    id=OTHER_STREAM_ID,
                    source_id=OTHER_SOURCE_ID,
                    name="Other webhook smoke stream",
                    description="A stream on another source.",
                    is_live=False,
                )
            )
            session.add(
                ZoneModel(
                    id=OTHER_ZONE_ID,
                    stream_id=OTHER_STREAM_ID,
                    name="Other webhook smoke feeder",
                    zone_type="feeder",
                    polygon_json="[]",
                    is_active=True,
                )
            )
            session.add(
                StreamModel(
                    id=SIDE_STREAM_ID,
                    source_id=SOURCE_ID,
                    name="Side webhook smoke stream",
                    description="A second stream on the configured source.",
                    is_live=False,
                )
            )
            session.add(
                ZoneModel(
                    id=SIDE_ZONE_ID,
                    stream_id=SIDE_STREAM_ID,
                    name="Side webhook smoke feeder",
                    zone_type="feeder",
                    polygon_json="[]",
                    is_active=True,
                )
            )


async def create_privacy_zone(client: httpx.AsyncClient) -> str:
    response = await client.post(
        "/api/zones",
        json={
            "stream_id": STREAM_ID,
            "name": "Webhook smoke privacy zone",
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


async def test_webhook_metadata_smoke_flow_preserves_truth_boundaries(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "mockingbird.source_providers.external_url_preview.fetch_external_url_preview",
        fail_if_runtime_is_called,
    )
    monkeypatch.setattr(
        "mockingbird.repository.product_repository.run_local_image_detector",
        fail_if_runtime_is_called,
    )
    monkeypatch.setattr(
        "mockingbird.repository.product_repository.run_megadetector_on_image",
        fail_if_runtime_is_called,
    )

    await configure_webhook_source(client)
    before_counts = await product_counts(client)
    before_truth = await dataset_truth_counts(client)
    before_cardinal_count = await analytics_species_count(client, "northern_cardinal")

    await assert_webhook_status_is_honest(client)
    assert await product_counts(client) == before_counts

    validation_response = await client.post(
        f"/api/sources/{SOURCE_ID}/webhook/validate",
        json={
            "payload": webhook_motion_payload(),
            "shared_secret_marker": "dry-run-marker",
        },
    )
    assert validation_response.status_code == 200
    validation = validation_response.json()
    assert validation["valid"] is True
    assert validation["candidate"]["candidate_type"] == "motion_event"
    assert validation["candidate"]["stream_id"] == STREAM_ID
    assert validation["candidate"]["zone_id"] == FEEDER_ZONE_ID
    assert validation["candidate"]["external_label"] == "northern_cardinal"
    assert "untrusted" in " ".join(validation["candidate"]["warnings"])
    assert "dry-run-marker" not in str(validation)
    assert_dry_run_creates_nothing(validation)
    assert await product_counts(client) == before_counts
    assert await dataset_truth_counts(client) == before_truth
    assert await analytics_species_count(client, "northern_cardinal") == before_cardinal_count

    evidence_response = await client.post(
        f"/api/sources/{SOURCE_ID}/webhook/motion-evidence",
        json={
            "payload": webhook_motion_payload(),
            "shared_secret_marker": "confirm-marker",
            "note": "Operator reviewed local webhook metadata.",
            "reason": "Phase 14H smoke-test evidence handoff.",
            "confirm": True,
        },
    )
    assert evidence_response.status_code == 200
    evidence_result = evidence_response.json()
    assert evidence_result["status"] == "created"
    assert evidence_result["candidate_type"] == "motion_event"
    assert evidence_result["source_id"] == SOURCE_ID
    assert evidence_result["stream_id"] == STREAM_ID
    assert evidence_result["zone_id"] == FEEDER_ZONE_ID
    assert evidence_result["external_event_id"] == "webhook-smoke-motion-1"
    assert evidence_result["duplicate_skipped"] is False
    assert "confirm-marker" not in str(evidence_result)
    assert_motion_response_creates_only_evidence(evidence_result, creates=True)
    assert_count_delta(
        before_counts,
        await product_counts(client),
        motion_evidence=1,
    )
    assert await dataset_truth_counts(client) == before_truth
    assert await analytics_species_count(client, "northern_cardinal") == before_cardinal_count

    evidence_id = evidence_result["motion_evidence_id"]
    detail_response = await client.get(f"/api/motion/evidence/{evidence_id}")
    assert detail_response.status_code == 200
    evidence_detail = detail_response.json()
    assert evidence_detail["source_id"] == SOURCE_ID
    assert evidence_detail["stream_id"] == STREAM_ID
    assert evidence_detail["zone_id"] == FEEDER_ZONE_ID
    assert evidence_detail["status"] == "pending"
    assert evidence_detail["snapshot_media_asset_id"] is None
    assert evidence_detail["promoted_event_id"] is None
    assert evidence_detail["promoted_visit_id"] is None
    assert evidence_detail["scoring_config"]["source"] == "webhook_metadata_motion_event"
    assert evidence_detail["scoring_config"]["provider_key"] == "webhook_future"
    assert evidence_detail["scoring_config"]["external_label_untrusted"] == "northern_cardinal"
    assert evidence_detail["scoring_config"]["external_confidence_untrusted"] == 0.84
    assert "External label (untrusted): northern_cardinal" in evidence_detail["notes"]
    assert "external payload note should not become truth" not in evidence_detail["notes"]

    promote_response = await client.post(
        f"/api/motion/evidence/{evidence_id}/promote",
        json={
            "event_title": "Webhook smoke motion candidate",
            "visit_label_hint": "unknown_animal",
            "notes": "Explicit smoke-test promotion.",
        },
    )
    assert promote_response.status_code == 200
    promoted = promote_response.json()
    event_id = promoted["event_id"]
    visit_id = promoted["visit_id"]
    assert promoted["evidence"]["status"] == "promoted"
    assert promoted["evidence"]["promoted_event_id"] == event_id
    assert promoted["evidence"]["promoted_visit_id"] == visit_id
    assert_count_delta(
        before_counts,
        await product_counts(client),
        motion_evidence=1,
        events=1,
        visits=1,
    )
    assert await dataset_truth_counts(client) == before_truth
    assert await analytics_species_count(client, "northern_cardinal") == before_cardinal_count

    event_detail_response = await client.get(f"/api/events/{event_id}/detail")
    visit_detail_response = await client.get(f"/api/visits/{visit_id}/detail")
    review_queue_response = await client.get("/api/review-queue")
    assert [
        event_detail_response.status_code,
        visit_detail_response.status_code,
        review_queue_response.status_code,
    ] == [200, 200, 200]
    event_detail = event_detail_response.json()
    visit_detail = visit_detail_response.json()
    assert event_detail["event"]["review_status"] == "needs_review"
    assert event_detail["motion_evidence"]["id"] == evidence_id
    assert event_detail["motion_evidence"]["status"] == "promoted"
    assert event_detail["motion_evidence"]["scoring_config"]["provider_key"] == "webhook_future"
    assert (
        event_detail["motion_evidence"]["scoring_config"]["external_label_untrusted"]
        == "northern_cardinal"
    )
    assert (
        event_detail["motion_evidence"]["scoring_config"]["external_confidence_untrusted"]
        == 0.84
    )
    assert event_detail["review_labels"] == []
    assert event_detail["dataset_ready"] is False
    assert visit_detail["visit"]["review_status"] == "needs_review"
    assert visit_detail["motion_evidence"]["id"] == evidence_id
    assert visit_detail["motion_evidence"]["status"] == "promoted"
    assert visit_detail["motion_evidence"]["scoring_config"]["provider_key"] == "webhook_future"
    assert (
        visit_detail["motion_evidence"]["scoring_config"]["external_label_untrusted"]
        == "northern_cardinal"
    )
    assert (
        visit_detail["motion_evidence"]["scoring_config"]["external_confidence_untrusted"]
        == 0.84
    )
    assert visit_detail["visit"]["reviewed_label"] is None
    assert visit_detail["review_labels"] == []
    assert visit_detail["dataset_ready"] is False
    assert any(item["visit_id"] == visit_id for item in review_queue_response.json())

    correction_response = await client.post(
        "/api/review-labels",
        json={"review_origin": "human", 
            "target_type": "visit",
            "target_id": visit_id,
            "label": "Northern Cardinal",
            "notes": "Phase 14H correction truth.",
        },
    )
    assert correction_response.status_code == 201
    correction = correction_response.json()
    assert correction["review_label"]["target_type"] == "visit"
    assert correction["review_label"]["target_id"] == visit_id
    assert correction["review_label"]["label"] == "northern_cardinal"
    assert correction["visit"]["review_status"] == "reviewed"
    assert correction["visit"]["reviewed_label"] == "northern_cardinal"
    assert correction["analytics"]["species_counts"]["northern_cardinal"] == (
        before_cardinal_count + 1
    )
    assert_count_delta(
        before_counts,
        await product_counts(client),
        motion_evidence=1,
        events=1,
        visits=1,
        review_labels=1,
    )
    assert await dataset_truth_counts(client) == {
        "reviewed_record_count": before_truth["reviewed_record_count"] + 1,
        "export_ready_count": before_truth["export_ready_count"] + 1,
    }


async def test_webhook_read_only_and_validation_routes_create_no_records(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await configure_webhook_source(client)
    before_counts = await product_counts(client)

    with monkeypatch.context() as patch:
        patch.setattr(
            "mockingbird.repository.product_repository.classify_webhook_payload",
            fail_if_runtime_is_called,
        )
        await assert_webhook_status_is_honest(client)

    assert await product_counts(client) == before_counts

    validation_response = await client.post(
        f"/api/sources/{SOURCE_ID}/webhook/validate",
        json={"payload": webhook_motion_payload("webhook-smoke-dry-run-only")},
    )
    assert validation_response.status_code == 200
    assert_dry_run_creates_nothing(validation_response.json())
    assert await product_counts(client) == before_counts


async def test_webhook_duplicate_external_event_id_skips_by_default(
    client: httpx.AsyncClient,
) -> None:
    await configure_webhook_source(client)
    before_counts = await product_counts(client)

    first_response = await client.post(
        f"/api/sources/{SOURCE_ID}/webhook/motion-evidence",
        json={
            "payload": webhook_motion_payload("webhook-smoke-duplicate-1"),
            "confirm": True,
        },
    )
    assert first_response.status_code == 200
    first = first_response.json()
    assert first["status"] == "created"
    assert_motion_response_creates_only_evidence(first, creates=True)

    duplicate_response = await client.post(
        f"/api/sources/{SOURCE_ID}/webhook/motion-evidence",
        json={
            "payload": webhook_motion_payload("webhook-smoke-duplicate-1"),
            "confirm": True,
        },
    )
    assert duplicate_response.status_code == 200
    duplicate = duplicate_response.json()
    assert duplicate["status"] == "skipped"
    assert duplicate["duplicate_skipped"] is True
    assert duplicate["motion_evidence_id"] == first["motion_evidence_id"]
    assert duplicate["existing_motion_evidence_id"] == first["motion_evidence_id"]
    assert_motion_response_creates_only_evidence(duplicate, creates=False)
    assert_count_delta(before_counts, await product_counts(client), motion_evidence=1)


async def test_webhook_context_rejections_create_no_records(
    client: httpx.AsyncClient,
    isolated_repository: ProductRepository,
) -> None:
    add_context_validation_records(isolated_repository)
    await configure_webhook_source(client)
    privacy_zone_id = await create_privacy_zone(client)
    before_counts = await product_counts(client)

    wrong_stream = await client.post(
        f"/api/sources/{SOURCE_ID}/webhook/motion-evidence",
        json={
            "payload": {
                **webhook_motion_payload("webhook-smoke-wrong-stream"),
                "stream_id": OTHER_STREAM_ID,
                "zone_id": OTHER_ZONE_ID,
            },
            "confirm": True,
        },
    )
    wrong_zone = await client.post(
        f"/api/sources/{SOURCE_ID}/webhook/motion-evidence",
        json={
            "payload": {
                **webhook_motion_payload("webhook-smoke-wrong-zone"),
                "stream_id": STREAM_ID,
                "zone_id": SIDE_ZONE_ID,
            },
            "confirm": True,
        },
    )
    privacy_zone = await client.post(
        f"/api/sources/{SOURCE_ID}/webhook/motion-evidence",
        json={
            "payload": {
                **webhook_motion_payload("webhook-smoke-privacy-zone"),
                "zone_id": privacy_zone_id,
            },
            "confirm": True,
        },
    )
    ignore_zone = await client.post(
        f"/api/sources/{SOURCE_ID}/webhook/motion-evidence",
        json={
            "payload": {
                **webhook_motion_payload("webhook-smoke-ignore-zone"),
                "zone_id": IGNORE_ZONE_ID,
            },
            "confirm": True,
        },
    )

    assert wrong_stream.status_code == 200
    assert wrong_stream.json()["status"] == "rejected"
    assert wrong_stream.json()["message"] == "stream_source_mismatch"
    assert wrong_zone.status_code == 200
    assert wrong_zone.json()["status"] == "rejected"
    assert wrong_zone.json()["message"] == "zone_stream_mismatch"
    assert privacy_zone.status_code == 200
    assert privacy_zone.json()["status"] == "rejected"
    assert privacy_zone.json()["message"] == "privacy_zone"
    assert ignore_zone.status_code == 200
    assert ignore_zone.json()["status"] == "rejected"
    assert ignore_zone.json()["message"] == "ignore_zone"
    assert await product_counts(client) == before_counts
