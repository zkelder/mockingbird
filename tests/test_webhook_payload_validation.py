from pathlib import Path

import httpx
import pytest

from mockingbird.api.main import app, configure_repository
from mockingbird.api.schemas import SourceKind, SourceStatus
from mockingbird.repository.product_repository import ProductRepository
from mockingbird.storage.models import CameraSourceModel, StreamModel
from tests.conftest import LegacyAuthenticatedTestClient

pytestmark = pytest.mark.anyio

SOURCE_ID = "source-backyard-demo"
STREAM_ID = "stream-backyard-feeder"
FEEDER_ZONE_ID = "zone-feeder"
IGNORE_ZONE_ID = "zone-ignore-driveway-edge"


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


async def validate_payload(
    client: httpx.AsyncClient,
    payload: dict,
    **overrides,
) -> httpx.Response:
    body = {"payload": payload, **overrides}
    return await client.post(f"/api/sources/{SOURCE_ID}/webhook/validate", json=body)


def assert_dry_run_no_creates(response_body: dict) -> None:
    assert response_body["dry_run"] is True
    assert response_body["would_create_media_asset"] is False
    assert response_body["would_create_motion_evidence"] is False
    assert response_body["would_create_event"] is False
    assert response_body["would_create_visit"] is False
    assert response_body["would_create_review_label"] is False
    assert response_body["would_create_species_suggestion"] is False
    assert response_body["would_create_detection_proposal"] is False
    assert response_body["would_create_truth"] is False


async def test_unknown_source_returns_404(client: httpx.AsyncClient) -> None:
    response = await client.post(
        "/api/sources/source-missing/webhook/validate",
        json={"payload": {"type": "heartbeat"}},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Source 'source-missing' was not found."


async def test_non_webhook_provider_returns_400(client: httpx.AsyncClient) -> None:
    response = await validate_payload(client, {"type": "heartbeat"})

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "Webhook validation requires a webhook_future Source provider."
    )


async def test_missing_shared_secret_metadata_returns_invalid_dry_run(
    client: httpx.AsyncClient,
) -> None:
    response = await client.patch(
        f"/api/sources/{SOURCE_ID}/provider-configuration",
        json={"provider_key": "webhook_future", "config": {"endpoint_name": "backyard-webhook"}},
    )
    assert response.status_code == 200
    before = await product_counts(client)

    validation_response = await validate_payload(client, {"type": "heartbeat"})

    assert validation_response.status_code == 200
    body = validation_response.json()
    assert body["valid"] is False
    assert body["skipped_reason"] == "not_configured"
    assert body["candidate"] is None
    assert_dry_run_no_creates(body)
    assert await product_counts(client) == before


async def test_heartbeat_payload_validates_as_metadata_only(client: httpx.AsyncClient) -> None:
    await configure_webhook_source(client)
    before = await product_counts(client)

    response = await validate_payload(
        client,
        {"type": "heartbeat", "external_event_id": "hb-1"},
        shared_secret_marker="not-real-auth",
    )

    assert response.status_code == 200
    body = response.json()
    assert body["valid"] is True
    assert body["skipped_reason"] is None
    assert body["candidate"]["candidate_type"] == "heartbeat"
    assert body["candidate"]["stream_id"] is None
    assert "authentication is not implemented" in " ".join(body["warnings"])
    assert "not-real-auth" not in str(body)
    assert_dry_run_no_creates(body)
    assert await product_counts(client) == before


@pytest.mark.parametrize(
    ("payload_type", "candidate_type"),
    [
        ("motion", "motion_event"),
        ("object", "object_detection"),
        ("species", "species_suggestion"),
    ],
)
async def test_activity_payloads_validate_as_untrusted_candidates(
    client: httpx.AsyncClient,
    payload_type: str,
    candidate_type: str,
) -> None:
    await configure_webhook_source(client)
    before = await product_counts(client)

    response = await validate_payload(
        client,
        {
            "type": payload_type,
            "external_event_id": f"{payload_type}-1",
            "stream_id": STREAM_ID,
            "zone_id": FEEDER_ZONE_ID,
            "label": "northern_cardinal",
            "confidence": 0.87,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["valid"] is True
    assert body["candidate"]["candidate_type"] == candidate_type
    assert body["candidate"]["stream_id"] == STREAM_ID
    assert body["candidate"]["zone_id"] == FEEDER_ZONE_ID
    assert body["candidate"]["external_label"] == "northern_cardinal"
    assert body["candidate"]["external_confidence"] == 0.87
    assert "untrusted" in " ".join(body["candidate"]["warnings"])
    assert_dry_run_no_creates(body)
    assert await product_counts(client) == before


async def test_media_payload_with_media_url_is_reference_only(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_if_called(*args, **kwargs):
        raise AssertionError("Webhook validation must not fetch external media URLs")

    monkeypatch.setattr(
        "mockingbird.source_providers.external_url_preview.fetch_external_url_preview",
        fail_if_called,
    )
    await configure_webhook_source(client)
    before = await product_counts(client)

    response = await validate_payload(
        client,
        {
            "type": "media",
            "stream_id": STREAM_ID,
            "media_url": "http://example.local/candidate.jpg",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["valid"] is True
    assert body["candidate"]["candidate_type"] == "media_reference"
    assert body["candidate"]["media_reference"] == "http://example.local/candidate.jpg"
    assert "not fetched" in " ".join(body["candidate"]["warnings"])
    assert_dry_run_no_creates(body)
    assert await product_counts(client) == before


async def test_local_file_like_media_url_is_not_returned_as_trusted_path(
    client: httpx.AsyncClient,
) -> None:
    await configure_webhook_source(client)

    response = await validate_payload(
        client,
        {"type": "media", "stream_id": STREAM_ID, "media_url": "/tmp/private.jpg"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["candidate"]["media_reference"] == "local_path_reference"
    assert "/tmp/private.jpg" not in str(body)
    assert "not trusted as paths" in " ".join(body["candidate"]["warnings"])


async def test_unknown_type_returns_invalid_unknown_candidate(client: httpx.AsyncClient) -> None:
    await configure_webhook_source(client)
    before = await product_counts(client)

    response = await validate_payload(client, {"type": "frobnicate", "stream_id": STREAM_ID})

    assert response.status_code == 200
    body = response.json()
    assert body["valid"] is False
    assert body["skipped_reason"] == "unknown_type"
    assert body["candidate"]["candidate_type"] == "unknown"
    assert "Unknown webhook payload type" in " ".join(body["candidate"]["warnings"])
    assert_dry_run_no_creates(body)
    assert await product_counts(client) == before


async def test_stream_id_must_belong_to_source(
    client: httpx.AsyncClient,
    isolated_repository: ProductRepository,
) -> None:
    await configure_webhook_source(client)
    with isolated_repository.session_factory() as session:
        with session.begin():
            session.add(
                CameraSourceModel(
                    id="source-other-webhook",
                    name="Other webhook source",
                    kind=SourceKind.webhook.value,
                    status=SourceStatus.needs_setup.value,
                    description="Other source for stream mismatch validation.",
                )
            )
            session.add(
                StreamModel(
                    id="stream-other-webhook",
                    source_id="source-other-webhook",
                    name="Other webhook stream",
                    description="A stream on another source.",
                    is_live=False,
                )
            )

    response = await validate_payload(client, {"type": "motion", "stream_id": "stream-other-webhook"})

    assert response.status_code == 200
    body = response.json()
    assert body["valid"] is False
    assert body["skipped_reason"] == "stream_source_mismatch"
    assert_dry_run_no_creates(body)


async def test_zone_id_must_belong_to_selected_stream(
    client: httpx.AsyncClient,
    isolated_repository: ProductRepository,
) -> None:
    await configure_webhook_source(client, {"default_stream_id": STREAM_ID})
    with isolated_repository.session_factory() as session:
        with session.begin():
            session.add(
                StreamModel(
                    id="stream-side-yard",
                    source_id=SOURCE_ID,
                    name="Side yard stream",
                    description="Second stream for zone mismatch validation.",
                    is_live=False,
                )
            )
    zone_response = await client.post(
        "/api/zones",
        json={
            "stream_id": "stream-side-yard",
            "name": "Validation yard zone",
            "zone_type": "yard",
            "polygon": [
                {"x": 0.1, "y": 0.1},
                {"x": 0.2, "y": 0.1},
                {"x": 0.2, "y": 0.2},
            ],
            "is_active": True,
        },
    )
    assert zone_response.status_code == 201
    zone_id = zone_response.json()["zone"]["id"]

    response = await validate_payload(
        client,
        {"type": "motion", "stream_id": STREAM_ID, "zone_id": zone_id},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["valid"] is False
    assert body["skipped_reason"] == "zone_stream_mismatch"
    assert_dry_run_no_creates(body)


async def test_privacy_zone_is_rejected(client: httpx.AsyncClient) -> None:
    await configure_webhook_source(client)
    zone_response = await client.post(
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
    assert zone_response.status_code == 201
    zone_id = zone_response.json()["zone"]["id"]
    before = await product_counts(client)

    response = await validate_payload(client, {"type": "motion", "zone_id": zone_id})

    assert response.status_code == 200
    body = response.json()
    assert body["valid"] is False
    assert body["skipped_reason"] == "privacy_zone"
    assert body["candidate"]["stream_id"] == STREAM_ID
    assert body["candidate"]["zone_id"] == zone_id
    assert_dry_run_no_creates(body)
    assert await product_counts(client) == before


async def test_ignore_zone_is_rejected(client: httpx.AsyncClient) -> None:
    await configure_webhook_source(client)
    before = await product_counts(client)

    response = await validate_payload(
        client,
        {"type": "motion", "stream_id": STREAM_ID, "zone_id": IGNORE_ZONE_ID},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["valid"] is False
    assert body["skipped_reason"] == "ignore_zone"
    assert body["candidate"]["zone_id"] == IGNORE_ZONE_ID
    assert_dry_run_no_creates(body)
    assert await product_counts(client) == before


async def test_allowed_source_name_mismatch_is_rejected(client: httpx.AsyncClient) -> None:
    await configure_webhook_source(client, {"allowed_source_name": "allowed-camera"})
    before = await product_counts(client)

    response = await validate_payload(
        client,
        {"type": "motion", "source_name": "wrong-camera", "stream_id": STREAM_ID},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["valid"] is False
    assert body["skipped_reason"] == "source_name_not_allowed"
    assert_dry_run_no_creates(body)
    assert await product_counts(client) == before


async def test_missing_stream_context_warns_without_creating_records(
    client: httpx.AsyncClient,
) -> None:
    await configure_webhook_source(client)
    before = await product_counts(client)

    response = await validate_payload(client, {"type": "object", "label": "squirrel"})

    assert response.status_code == 200
    body = response.json()
    assert body["valid"] is True
    assert body["candidate"]["stream_id"] is None
    assert "unanchored" in " ".join(body["warnings"])
    assert_dry_run_no_creates(body)
    assert await product_counts(client) == before


async def test_validation_does_not_return_secrets_or_payload_tokens(
    client: httpx.AsyncClient,
) -> None:
    await configure_webhook_source(client)

    response = await validate_payload(
        client,
        {
            "type": "heartbeat",
            "auth_token": "payload-token-should-not-return",
            "secret": "payload-secret-should-not-return",
        },
        shared_secret_marker="request-secret-should-not-return",
    )

    assert response.status_code == 200
    response_text = str(response.json())
    assert "payload-token-should-not-return" not in response_text
    assert "payload-secret-should-not-return" not in response_text
    assert "request-secret-should-not-return" not in response_text


async def test_validation_does_not_call_model_runtime_hooks(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_if_called():
        raise AssertionError("Webhook validation must not call detector adapter status")

    monkeypatch.setattr(
        "mockingbird.repository.product_repository.get_local_detector_status",
        fail_if_called,
    )
    monkeypatch.setattr(
        "mockingbird.repository.product_repository.get_megadetector_status",
        fail_if_called,
    )
    await configure_webhook_source(client)

    response = await validate_payload(client, {"type": "object", "stream_id": STREAM_ID})

    assert response.status_code == 200
    assert response.json()["valid"] is True


async def test_status_routes_do_not_parse_webhook_payloads(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_if_called(payload):
        raise AssertionError("Status routes must not parse webhook payloads")

    monkeypatch.setattr(
        "mockingbird.repository.product_repository.classify_webhook_payload",
        fail_if_called,
    )
    await configure_webhook_source(client)

    assert (await client.get(f"/api/sources/{SOURCE_ID}/connection")).status_code == 200
    assert (await client.get(f"/api/sources/{SOURCE_ID}/setup-review")).status_code == 200
    assert (await client.get(f"/api/streams/{STREAM_ID}/playback")).status_code == 200
