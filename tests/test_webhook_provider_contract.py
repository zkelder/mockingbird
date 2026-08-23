from pathlib import Path

import httpx
import pytest

from mockingbird.api.main import app, configure_repository
from mockingbird.repository.product_repository import (
    ProductRepository,
    SourceProviderConfigurationModel,
)
from tests.conftest import LegacyAuthenticatedTestClient

pytestmark = pytest.mark.anyio

SOURCE_ID = "source-backyard-demo"
STREAM_ID = "stream-backyard-feeder"


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
    config: dict[str, str | None],
) -> dict:
    response = await client.patch(
        f"/api/sources/{SOURCE_ID}/provider-configuration",
        json={"provider_key": "webhook_future", "config": config},
    )
    assert response.status_code == 200
    return response.json()


async def test_webhook_provider_definition_is_metadata_only(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/source-provider-definitions")

    assert response.status_code == 200
    definitions = response.json()
    definition = next(
        item for item in definitions if item["provider_key"] == "webhook_future"
    )
    assert definition["display_name"] == "Generic webhook ingest"
    assert definition["status"] == "future_adapter"
    assert definition["supports_live_playback"] is False
    assert definition["supports_zone_editing"] is True

    fields = {field["key"]: field for field in definition["fields"]}
    assert list(fields) == [
        "endpoint_name",
        "shared_secret_configured",
        "allowed_source_name",
        "default_stream_id",
        "default_zone_id",
        "accept_media_uploads",
        "accept_media_urls",
        "notes",
    ]
    assert fields["endpoint_name"]["required"] is False
    assert fields["endpoint_name"]["secret"] is False
    assert fields["endpoint_name"]["placeholder"] == "backyard-webhook"
    assert fields["shared_secret_configured"]["required"] is True
    assert fields["shared_secret_configured"]["secret"] is True
    assert fields["shared_secret_configured"]["label"] == "Shared secret"
    assert "future signed webhook ingest" in fields["shared_secret_configured"]["description"]
    assert fields["accept_media_uploads"]["placeholder"] == "false"
    assert fields["accept_media_urls"]["placeholder"] == "false"


async def test_webhook_missing_shared_secret_reports_not_configured(
    client: httpx.AsyncClient,
) -> None:
    configuration = await configure_webhook_source(
        client,
        {"endpoint_name": "backyard-webhook"},
    )

    assert configuration["provider_key"] == "webhook_future"
    assert configuration["configured_fields"] == ["endpoint_name"]
    assert configuration["missing_fields"] == ["shared_secret_configured"]
    assert configuration["safe_config_preview"]["endpoint_name"] == "backyard-webhook"
    assert configuration["safe_config_preview"]["shared_secret_configured"] == "not_configured"
    assert configuration["supports_live_playback"] is False

    connection_response = await client.get(f"/api/sources/{SOURCE_ID}/connection")
    assert connection_response.status_code == 200
    connection = connection_response.json()
    assert connection["status"] == "not_configured"
    assert connection["provider_kind"] == "future_adapter"
    assert connection["supports_live_playback"] is False
    assert connection["supports_zone_editing"] is True
    assert "shared secret metadata" in connection["setup_hint"]
    assert "does not accept webhook payloads yet" in connection["setup_hint"]

    review_response = await client.get(f"/api/sources/{SOURCE_ID}/setup-review")
    assert review_response.status_code == 200
    review = review_response.json()
    assert review["readiness_level"] == "needs_setup"
    assert review["next_step"] == "Complete webhook shared secret metadata."
    assert review["supports_live_playback"] is False


async def test_webhook_configured_secret_is_redacted_and_future_adapter_required(
    client: httpx.AsyncClient,
    isolated_repository: ProductRepository,
) -> None:
    raw_secret = "never-return-this-webhook-secret"
    configuration = await configure_webhook_source(
        client,
        {
            "endpoint_name": "backyard-webhook",
            "shared_secret_configured": raw_secret,
            "allowed_source_name": "feeder-alerts",
            "default_stream_id": STREAM_ID,
            "default_zone_id": "zone-feeder",
            "accept_media_uploads": "false",
            "accept_media_urls": "false",
            "notes": "Local system will be mapped later.",
        },
    )

    assert configuration["provider_key"] == "webhook_future"
    assert configuration["missing_fields"] == []
    assert configuration["safe_config_preview"]["shared_secret_configured"] == "configured"
    assert raw_secret not in str(configuration)

    with isolated_repository.session_factory() as session:
        stored = session.get(SourceProviderConfigurationModel, SOURCE_ID)
        assert stored is not None
        assert raw_secret not in stored.config_json
        assert '"shared_secret_configured": "configured"' in stored.config_json

    connection_response = await client.get(f"/api/sources/{SOURCE_ID}/connection")
    assert connection_response.status_code == 200
    connection = connection_response.json()
    assert connection["status"] == "configured"
    assert connection["supports_live_playback"] is False
    assert connection["supports_zone_editing"] is True
    assert "explicit motion-evidence ingest" in connection["message"]
    assert "pending MotionEvidence only" in connection["setup_hint"]

    review_response = await client.get(f"/api/sources/{SOURCE_ID}/setup-review")
    assert review_response.status_code == 200
    review = review_response.json()
    assert review["readiness_level"] == "future_adapter_required"
    assert review["summary"] == (
        "Webhook metadata is present. Explicit confirmed motion payloads can "
        "create pending MotionEvidence only."
    )
    assert review["next_step"] == (
        "Review pending MotionEvidence after explicit webhook metadata ingest; "
        "media upload/download and reviewed truth remain future work."
    )
    assert review["supports_live_playback"] is False
    assert any(step["key"] == "webhook_future_ingest" for step in review["steps"])
    assert raw_secret not in str(review)


async def test_webhook_stream_playback_remains_placeholder_only(
    client: httpx.AsyncClient,
) -> None:
    await configure_webhook_source(
        client,
        {
            "endpoint_name": "backyard-webhook",
            "shared_secret_configured": "redact-me",
        },
    )

    response = await client.get(f"/api/streams/{STREAM_ID}/playback")

    assert response.status_code == 200
    playback = response.json()
    assert playback["adapter_key"] == "webhook_future"
    assert playback["status"] == "not_configured"
    assert playback["playback_kind"] == "placeholder"
    assert playback["supports_live_playback"] is False
    assert playback["supports_zone_editing"] is True
    assert playback["preview_media_asset_id"] is None
    assert playback["preview_url"] is None
    assert "does not provide live playback" in playback["message"]
    assert "pending evidence" in playback["setup_hint"]


async def test_webhook_provider_adds_no_webhook_ingest_routes() -> None:
    webhook_ingest_routes = [
        route.path
        for route in app.routes
        if getattr(route, "path", None)
        and "webhook" in route.path.lower()
        and "ingest" in route.path.lower()
    ]

    assert webhook_ingest_routes == []


async def test_webhook_configuration_and_status_create_no_product_records(
    client: httpx.AsyncClient,
) -> None:
    before = await product_counts(client)

    await configure_webhook_source(
        client,
        {
            "endpoint_name": "backyard-webhook",
            "shared_secret_configured": "redact-me",
            "default_stream_id": STREAM_ID,
            "accept_media_uploads": "false",
            "accept_media_urls": "false",
        },
    )
    connection_response = await client.get(f"/api/sources/{SOURCE_ID}/connection")
    setup_response = await client.get(f"/api/sources/{SOURCE_ID}/setup-review")
    playback_response = await client.get(f"/api/streams/{STREAM_ID}/playback")

    assert connection_response.status_code == 200
    assert setup_response.status_code == 200
    assert playback_response.status_code == 200
    assert await product_counts(client) == before


async def test_webhook_status_routes_do_not_call_model_runtime_hooks(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_if_called():
        raise AssertionError("Webhook provider status must not call detector adapter status")

    monkeypatch.setattr(
        "mockingbird.repository.product_repository.get_local_detector_status",
        fail_if_called,
    )
    monkeypatch.setattr(
        "mockingbird.repository.product_repository.get_megadetector_status",
        fail_if_called,
    )

    await configure_webhook_source(
        client,
        {
            "endpoint_name": "backyard-webhook",
            "shared_secret_configured": "redact-me",
        },
    )
    assert (await client.get(f"/api/sources/{SOURCE_ID}/connection")).status_code == 200
    assert (await client.get(f"/api/sources/{SOURCE_ID}/setup-review")).status_code == 200
    assert (await client.get(f"/api/streams/{STREAM_ID}/playback")).status_code == 200
