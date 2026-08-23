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
GROUND_ZONE_ID = "zone-ground"
IGNORE_ZONE_ID = "zone-ignore-driveway-edge"
OTHER_SOURCE_ID = "source-other-webhook"
OTHER_STREAM_ID = "stream-other-webhook"
OTHER_ZONE_ID = "zone-other-webhook"
SIDE_STREAM_ID = "stream-side-webhook"
SIDE_ZONE_ID = "zone-side-webhook"


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


async def configure_webhook_source(
    client: httpx.AsyncClient,
    config: dict[str, str | None] | None = None,
) -> dict:
    response = await client.patch(
        f"/api/sources/{SOURCE_ID}/provider-configuration",
        json={
            "provider_key": "webhook_future",
            "config": {
                "endpoint_name": "backyard-webhook",
                "shared_secret_configured": "redact-me",
                **(config or {}),
            },
        },
    )
    assert response.status_code == 200
    return response.json()


async def create_webhook_motion_evidence(
    client: httpx.AsyncClient,
    payload: dict | None = None,
    **overrides,
) -> httpx.Response:
    body = {
        "payload": {
            "type": "motion",
            "external_event_id": "motion-1",
            "stream_id": STREAM_ID,
            "zone_id": FEEDER_ZONE_ID,
            **(payload or {}),
        },
        "confirm": True,
        **overrides,
    }
    return await client.post(f"/api/sources/{SOURCE_ID}/webhook/motion-evidence", json=body)


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


def assert_only_motion_evidence_changed(before: dict[str, int], after: dict[str, int]) -> None:
    assert after["motion_evidence"] == before["motion_evidence"] + 1
    for key in (
        "events",
        "visits",
        "review_labels",
        "species_suggestions",
        "detection_proposals",
        "dataset_exports",
        "media_assets",
    ):
        assert after[key] == before[key]


def assert_no_product_counts_changed(before: dict[str, int], after: dict[str, int]) -> None:
    assert after == before


def assert_response_creates_only_motion_evidence(body: dict, creates: bool) -> None:
    assert body["creates_motion_evidence"] is creates
    assert body["creates_media_asset"] is False
    assert body["creates_event"] is False
    assert body["creates_visit"] is False
    assert body["creates_review_label"] is False
    assert body["creates_truth"] is False


def add_context_validation_records(repository: ProductRepository) -> None:
    with repository.session_factory() as session:
        with session.begin():
            session.add(
                CameraSourceModel(
                    id=OTHER_SOURCE_ID,
                    name="Other webhook source",
                    kind=SourceKind.webhook.value,
                    status=SourceStatus.needs_setup.value,
                    description="Other source for webhook context validation.",
                )
            )
            session.add(
                StreamModel(
                    id=OTHER_STREAM_ID,
                    source_id=OTHER_SOURCE_ID,
                    name="Other webhook stream",
                    description="A stream on another source.",
                    is_live=False,
                )
            )
            session.add(
                ZoneModel(
                    id=OTHER_ZONE_ID,
                    stream_id=OTHER_STREAM_ID,
                    name="Other webhook feeder",
                    zone_type="feeder",
                    polygon_json="[]",
                    is_active=True,
                )
            )
            session.add(
                StreamModel(
                    id=SIDE_STREAM_ID,
                    source_id=SOURCE_ID,
                    name="Side yard webhook stream",
                    description="A second stream on the webhook source.",
                    is_live=False,
                )
            )
            session.add(
                ZoneModel(
                    id=SIDE_ZONE_ID,
                    stream_id=SIDE_STREAM_ID,
                    name="Side yard feeder",
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
            "name": "Webhook privacy zone",
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


async def test_unknown_source_returns_404(client: httpx.AsyncClient) -> None:
    response = await client.post(
        "/api/sources/source-missing/webhook/motion-evidence",
        json={"payload": {"type": "motion"}, "confirm": True},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Source 'source-missing' was not found."


async def test_non_webhook_provider_returns_400(client: httpx.AsyncClient) -> None:
    response = await create_webhook_motion_evidence(client)

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "Webhook motion evidence requires a webhook_future Source provider."
    )


async def test_confirm_false_is_rejected(client: httpx.AsyncClient) -> None:
    await configure_webhook_source(client)
    before = await product_counts(client)

    response = await create_webhook_motion_evidence(client, confirm=False)

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "Confirm this webhook motion payload before creating pending MotionEvidence."
    )
    assert_no_product_counts_changed(before, await product_counts(client))


async def test_missing_shared_secret_metadata_rejects_without_records(
    client: httpx.AsyncClient,
) -> None:
    response = await client.patch(
        f"/api/sources/{SOURCE_ID}/provider-configuration",
        json={"provider_key": "webhook_future", "config": {"endpoint_name": "backyard-webhook"}},
    )
    assert response.status_code == 200
    before = await product_counts(client)

    evidence_response = await create_webhook_motion_evidence(client)

    assert evidence_response.status_code == 200
    body = evidence_response.json()
    assert body["status"] == "rejected"
    assert body["message"] == "not_configured"
    assert_response_creates_only_motion_evidence(body, creates=False)
    assert_no_product_counts_changed(before, await product_counts(client))


async def test_valid_motion_payload_creates_pending_motion_evidence_only(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("Webhook motion evidence must not call media/model runtimes")

    monkeypatch.setattr(
        "mockingbird.source_providers.external_url_preview.fetch_external_url_preview",
        fail_if_called,
    )
    monkeypatch.setattr(
        "mockingbird.repository.product_repository.run_local_image_detector",
        fail_if_called,
    )
    monkeypatch.setattr(
        "mockingbird.repository.product_repository.run_megadetector_on_image",
        fail_if_called,
    )
    await configure_webhook_source(client)
    before = await product_counts(client)

    response = await create_webhook_motion_evidence(
        client,
        {
            "external_event_id": "motion-webhook-1",
            "label": "northern_cardinal",
            "confidence": 0.82,
            "timestamp": "2026-07-04T12:00:00Z",
            "notes": "payload note should not become truth",
        },
        note="Operator review note.",
        reason="Local webhook metadata candidate.",
        shared_secret_marker="not-real-auth",
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "created"
    assert body["motion_evidence_id"].startswith("motion-evidence-")
    assert body["candidate_type"] == "motion_event"
    assert body["source_id"] == SOURCE_ID
    assert body["stream_id"] == STREAM_ID
    assert body["zone_id"] == FEEDER_ZONE_ID
    assert body["external_event_id"] == "motion-webhook-1"
    assert body["duplicate_skipped"] is False
    assert body["existing_motion_evidence_id"] is None
    assert "not-real-auth" not in str(body)
    assert_response_creates_only_motion_evidence(body, creates=True)

    detail = await client.get(f"/api/motion/evidence/{body['motion_evidence_id']}")
    assert detail.status_code == 200
    evidence = detail.json()
    assert evidence["source_id"] == SOURCE_ID
    assert evidence["stream_id"] == STREAM_ID
    assert evidence["zone_id"] == FEEDER_ZONE_ID
    assert evidence["status"] == "pending"
    assert evidence["snapshot_media_asset_id"] is None
    assert evidence["promoted_event_id"] is None
    assert evidence["promoted_visit_id"] is None
    assert evidence["scoring_config"] == {
        "candidate_type": "motion_event",
        "external_confidence_untrusted": 0.82,
        "external_event_id": "motion-webhook-1",
        "external_label_untrusted": "northern_cardinal",
        "external_timestamp": "2026-07-04T12:00:00Z",
        "motion_score_available": False,
        "provider_key": "webhook_future",
        "requires_review": True,
        "source": "webhook_metadata_motion_event",
        "source_id": SOURCE_ID,
        "stream_id": STREAM_ID,
        "zone_id": FEEDER_ZONE_ID,
    }
    assert "External label (untrusted): northern_cardinal" in evidence["notes"]
    assert "Operator review note." in evidence["notes"]
    assert "Local webhook metadata candidate." in evidence["notes"]
    assert "payload note should not become truth" not in evidence["notes"]

    assert_only_motion_evidence_changed(before, await product_counts(client))


@pytest.mark.parametrize("payload_type", ["heartbeat", "object", "species", "media", "unknown"])
async def test_non_motion_payloads_create_no_motion_evidence(
    client: httpx.AsyncClient,
    payload_type: str,
) -> None:
    await configure_webhook_source(client)
    before = await product_counts(client)

    response = await create_webhook_motion_evidence(
        client,
        {"type": payload_type, "media_id": "media-ref-1"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "rejected"
    assert_response_creates_only_motion_evidence(body, creates=False)
    assert_no_product_counts_changed(before, await product_counts(client))


async def test_stream_and_zone_context_are_validated(
    client: httpx.AsyncClient,
    isolated_repository: ProductRepository,
) -> None:
    add_context_validation_records(isolated_repository)
    await configure_webhook_source(client)
    before = await product_counts(client)

    wrong_stream = await create_webhook_motion_evidence(
        client,
        {"stream_id": OTHER_STREAM_ID, "zone_id": OTHER_ZONE_ID},
    )
    wrong_zone = await create_webhook_motion_evidence(
        client,
        {"stream_id": STREAM_ID, "zone_id": SIDE_ZONE_ID},
    )

    assert wrong_stream.status_code == 200
    assert wrong_stream.json()["status"] == "rejected"
    assert wrong_stream.json()["message"] == "stream_source_mismatch"
    assert wrong_zone.status_code == 200
    assert wrong_zone.json()["status"] == "rejected"
    assert wrong_zone.json()["message"] == "zone_stream_mismatch"
    assert_no_product_counts_changed(before, await product_counts(client))


async def test_privacy_and_ignore_zones_are_rejected(client: httpx.AsyncClient) -> None:
    await configure_webhook_source(client)
    privacy_zone_id = await create_privacy_zone(client)
    before = await product_counts(client)

    privacy = await create_webhook_motion_evidence(
        client,
        {"stream_id": STREAM_ID, "zone_id": privacy_zone_id},
    )
    ignore = await create_webhook_motion_evidence(
        client,
        {"stream_id": STREAM_ID, "zone_id": IGNORE_ZONE_ID},
    )

    assert privacy.status_code == 200
    assert privacy.json()["status"] == "rejected"
    assert privacy.json()["message"] == "privacy_zone"
    assert ignore.status_code == 200
    assert ignore.json()["status"] == "rejected"
    assert ignore.json()["message"] == "ignore_zone"
    assert_no_product_counts_changed(before, await product_counts(client))


async def test_missing_stream_or_zone_context_is_rejected(client: httpx.AsyncClient) -> None:
    await configure_webhook_source(client)
    before = await product_counts(client)

    missing_stream = await client.post(
        f"/api/sources/{SOURCE_ID}/webhook/motion-evidence",
        json={"payload": {"type": "motion", "zone_id": FEEDER_ZONE_ID}, "confirm": True},
    )
    missing_zone = await client.post(
        f"/api/sources/{SOURCE_ID}/webhook/motion-evidence",
        json={"payload": {"type": "motion", "stream_id": STREAM_ID}, "confirm": True},
    )

    assert missing_stream.status_code == 200
    assert missing_stream.json()["status"] == "created"
    assert missing_stream.json()["stream_id"] == STREAM_ID
    assert missing_zone.status_code == 200
    assert missing_zone.json()["status"] == "rejected"
    assert missing_zone.json()["message"] == "missing_zone_context"
    after = await product_counts(client)
    assert after["motion_evidence"] == before["motion_evidence"] + 1
    for key in after:
        if key != "motion_evidence":
            assert after[key] == before[key]


async def test_default_stream_and_zone_context_can_create_evidence(
    client: httpx.AsyncClient,
) -> None:
    await configure_webhook_source(
        client,
        {"default_stream_id": STREAM_ID, "default_zone_id": GROUND_ZONE_ID},
    )
    before = await product_counts(client)

    response = await client.post(
        f"/api/sources/{SOURCE_ID}/webhook/motion-evidence",
        json={
            "payload": {"type": "motion", "external_event_id": "default-context-1"},
            "confirm": True,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "created"
    assert body["stream_id"] == STREAM_ID
    assert body["zone_id"] == GROUND_ZONE_ID
    assert_only_motion_evidence_changed(before, await product_counts(client))


async def test_duplicate_external_event_id_is_skipped_by_default(
    client: httpx.AsyncClient,
) -> None:
    await configure_webhook_source(client)
    created = await create_webhook_motion_evidence(
        client,
        {"external_event_id": "duplicate-motion-1"},
    )
    assert created.status_code == 200
    evidence_id = created.json()["motion_evidence_id"]
    before_duplicate = await product_counts(client)

    duplicate = await create_webhook_motion_evidence(
        client,
        {"external_event_id": "duplicate-motion-1"},
    )

    assert duplicate.status_code == 200
    body = duplicate.json()
    assert body["status"] == "skipped"
    assert body["duplicate_skipped"] is True
    assert body["motion_evidence_id"] == evidence_id
    assert body["existing_motion_evidence_id"] == evidence_id
    assert "external_event_id" in body["message"]
    assert_no_product_counts_changed(before_duplicate, await product_counts(client))


async def test_duplicate_policy_allow_duplicate_creates_another_pending_evidence(
    client: httpx.AsyncClient,
) -> None:
    await configure_webhook_source(client)
    created = await create_webhook_motion_evidence(
        client,
        {"external_event_id": "duplicate-motion-allowed"},
    )
    assert created.status_code == 200
    before_duplicate = await product_counts(client)

    duplicate = await create_webhook_motion_evidence(
        client,
        {"external_event_id": "duplicate-motion-allowed"},
        duplicate_policy="allow_duplicate",
    )

    assert duplicate.status_code == 200
    body = duplicate.json()
    assert body["status"] == "created"
    assert body["duplicate_skipped"] is False
    assert body["existing_motion_evidence_id"] is None
    assert body["motion_evidence_id"] != created.json()["motion_evidence_id"]
    assert any("duplicate creation was allowed" in warning for warning in body["warnings"])
    assert_only_motion_evidence_changed(before_duplicate, await product_counts(client))


async def test_missing_external_event_id_warns_and_creates_without_duplicate_inference(
    client: httpx.AsyncClient,
) -> None:
    await configure_webhook_source(client)
    before = await product_counts(client)

    response = await create_webhook_motion_evidence(
        client,
        {"external_event_id": None},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "created"
    assert body["external_event_id"] is None
    assert any("duplicate detection is limited" in warning for warning in body["warnings"])
    assert_only_motion_evidence_changed(before, await product_counts(client))


async def test_labels_are_not_truth_and_validation_dry_run_still_creates_nothing(
    client: httpx.AsyncClient,
) -> None:
    await configure_webhook_source(client)
    before = await product_counts(client)

    validation = await client.post(
        f"/api/sources/{SOURCE_ID}/webhook/validate",
        json={
            "payload": {
                "type": "motion",
                "stream_id": STREAM_ID,
                "zone_id": FEEDER_ZONE_ID,
                "label": "northern_cardinal",
                "confidence": 0.9,
            }
        },
    )

    assert validation.status_code == 200
    assert validation.json()["would_create_motion_evidence"] is False
    assert_no_product_counts_changed(before, await product_counts(client))

    created = await create_webhook_motion_evidence(
        client,
        {"label": "northern_cardinal", "confidence": 0.9},
    )

    assert created.status_code == 200
    assert_only_motion_evidence_changed(before, await product_counts(client))


async def test_webhook_motion_evidence_does_not_return_or_store_secrets(
    client: httpx.AsyncClient,
) -> None:
    await configure_webhook_source(client)

    response = await create_webhook_motion_evidence(
        client,
        {
            "external_event_id": "secret-check-1",
            "auth_token": "payload-token-should-not-return",
            "secret": "payload-secret-should-not-return",
        },
        shared_secret_marker="request-secret-should-not-return",
    )

    assert response.status_code == 200
    body_text = str(response.json())
    assert "payload-token-should-not-return" not in body_text
    assert "payload-secret-should-not-return" not in body_text
    assert "request-secret-should-not-return" not in body_text

    detail = await client.get(f"/api/motion/evidence/{response.json()['motion_evidence_id']}")
    evidence_text = str(detail.json())
    assert "payload-token-should-not-return" not in evidence_text
    assert "payload-secret-should-not-return" not in evidence_text
    assert "request-secret-should-not-return" not in evidence_text


async def test_status_routes_do_not_process_webhook_motion_payloads(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("Status routes must not process webhook payloads")

    monkeypatch.setattr(
        "mockingbird.repository.product_repository.classify_webhook_payload",
        fail_if_called,
    )
    await configure_webhook_source(client)

    assert (await client.get(f"/api/sources/{SOURCE_ID}/connection")).status_code == 200
    assert (await client.get(f"/api/sources/{SOURCE_ID}/setup-review")).status_code == 200
    assert (await client.get(f"/api/streams/{STREAM_ID}/playback")).status_code == 200
