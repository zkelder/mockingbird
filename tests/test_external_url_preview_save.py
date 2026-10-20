from __future__ import annotations

import ipaddress
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import HTTPError, URLError

import httpx
import pytest

from mockingbird.api.main import app, configure_repository
from mockingbird.api.schemas import SourceKind, SourceStatus
from mockingbird.repository.product_repository import ProductRepository, SourceProviderConfigurationModel
from mockingbird.source_providers import external_url_preview
from mockingbird.storage.models import CameraSourceModel, StreamModel
from tests.conftest import LegacyAuthenticatedTestClient

pytestmark = pytest.mark.anyio

SOURCE_ID = "source-backyard-demo"
STREAM_ID = "stream-backyard-feeder"
OTHER_SOURCE_ID = "source-other-external"
OTHER_STREAM_ID = "stream-other-external"
PRIVATE_PREVIEW_URL = "http://192.168.1.23/camera/path/still.jpg"


class FakeResponse:
    def __init__(self, body: bytes, headers: dict[str, str] | None = None) -> None:
        self.body = body
        self.headers = headers or {}

    def read(self, size: int = -1) -> bytes:
        return self.body if size < 0 else self.body[:size]

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *args) -> None:
        return None


class FakeOpener:
    def __init__(self, response: FakeResponse | Exception) -> None:
        self.response = response
        self.requests = []
        self.timeouts = []

    def open(self, request, timeout: float):  # noqa: ANN001
        self.requests.append(request)
        self.timeouts.append(timeout)
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


@pytest.fixture(autouse=True)
def isolated_repository(tmp_path: Path) -> ProductRepository:
    repository = ProductRepository(
        db_url=f"sqlite:///{tmp_path / 'mockingbird.sqlite3'}",
        media_root=tmp_path / "media",
    )
    # Pre-Release Trust & Correctness Correction v1 (UI-01): this file's
    # fixtures build Visits on the seeded demo Source's own STREAM_ID, which
    # Dashboard/Bird Log now correctly exclude from real history like every
    # other surface (see `_real_source_condition` in product_repository.py).
    # "De-demo" the seeded Source in place -- the same real-product
    # mechanism (an effective, non-"demo" provider configuration)
    # `_real_source_condition` already recognizes for a Source repurposed
    # after creation.
    with repository.session_factory() as session:
        with session.begin():
            session.add(
                SourceProviderConfigurationModel(
                    source_id=SOURCE_ID, provider_key="manual_upload",
                    config_json="{}", updated_at=datetime.now(UTC),
                )
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


@pytest.fixture(autouse=True)
def allow_private_lan_dns(monkeypatch: pytest.MonkeyPatch) -> None:
    def resolve(hostname: str):
        try:
            return [ipaddress.ip_address(hostname)]
        except ValueError:
            return [ipaddress.ip_address("192.168.1.23")]

    monkeypatch.setattr(external_url_preview, "_resolve_host_addresses", resolve)


async def configure_external_url(
    client: httpx.AsyncClient,
    config: dict[str, str] | None = None,
) -> None:
    response = await client.patch(
        f"/api/sources/{SOURCE_ID}/provider-configuration",
        json={"provider_key": "external_url", "config": config or {}},
    )
    assert response.status_code == 200


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


def install_fake_fetch(
    monkeypatch: pytest.MonkeyPatch,
    response: FakeResponse | Exception,
) -> FakeOpener:
    opener = FakeOpener(response)
    monkeypatch.setattr(external_url_preview, "_build_no_redirect_opener", lambda: opener)
    return opener


def add_other_stream(repository: ProductRepository) -> None:
    with repository.session_factory() as session:
        with session.begin():
            session.add(
                CameraSourceModel(
                    id=OTHER_SOURCE_ID,
                    name="Other external source",
                    kind=SourceKind.webhook.value,
                    status=SourceStatus.connected.value,
                    description="Another source for stream ownership validation.",
                )
            )
            session.add(
                StreamModel(
                    id=OTHER_STREAM_ID,
                    source_id=OTHER_SOURCE_ID,
                    name="Other stream",
                    description="Belongs to another source.",
                    is_live=False,
                )
            )


async def test_unknown_source_returns_404(client: httpx.AsyncClient) -> None:
    response = await client.post("/api/sources/source-missing/external-url/preview/save", json={})

    assert response.status_code == 404
    assert response.json()["detail"] == "Source 'source-missing' was not found."


async def test_non_external_url_source_returns_400(client: httpx.AsyncClient) -> None:
    response = await client.post(f"/api/sources/{SOURCE_ID}/external-url/preview/save", json={})

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "External URL preview save requires an external_url Source provider."
    )


async def test_missing_url_returns_not_configured_without_fetch(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await configure_external_url(client)

    def fail_if_called(*args, **kwargs):  # noqa: ANN002, ANN003
        raise AssertionError("Missing URL must not fetch")

    monkeypatch.setattr(external_url_preview, "fetch_external_url_preview", fail_if_called)

    response = await client.post(f"/api/sources/{SOURCE_ID}/external-url/preview/save", json={})

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "not_configured"
    assert body["media_asset_id"] is None
    assert body["bytes_written"] == 0
    assert body["creates_event"] is False
    assert body["creates_visit"] is False
    assert body["creates_truth"] is False


@pytest.mark.parametrize(
    ("content_type", "extension"),
    [
        ("image/jpeg", ".jpg"),
        ("image/png", ".png"),
        ("image/webp", ".webp"),
    ],
)
async def test_supported_still_image_save_creates_one_media_asset_only(
    client: httpx.AsyncClient,
    isolated_repository: ProductRepository,
    monkeypatch: pytest.MonkeyPatch,
    content_type: str,
    extension: str,
) -> None:
    await configure_external_url(client, {"url": PRIVATE_PREVIEW_URL})
    before = await product_counts(client)
    opener = install_fake_fetch(
        monkeypatch,
        FakeResponse(b"image-bytes", {"Content-Type": f"{content_type}; charset=binary"}),
    )

    response = await client.post(
        f"/api/sources/{SOURCE_ID}/external-url/preview/save",
        json={"stream_id": STREAM_ID, "timeout_seconds": 20, "max_bytes": 100, "note": "Feeder"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "saved"
    assert body["source_id"] == SOURCE_ID
    assert body["stream_id"] == STREAM_ID
    assert body["media_asset_id"].startswith("media-asset-")
    assert body["content_type"] == content_type
    assert body["bytes_written"] == len(b"image-bytes")
    assert body["file_name"].endswith(extension)
    assert body["relative_path"] == body["file_name"]
    assert "still.jpg" not in body["file_name"]
    assert body["creates_event"] is False
    assert body["creates_visit"] is False
    assert body["creates_truth"] is False
    assert opener.requests[0].get_method() == "GET"
    assert opener.requests[0].full_url == PRIVATE_PREVIEW_URL
    assert opener.timeouts == [10.0]

    media_response = await client.get(f"/api/media/{body['media_asset_id']}")
    assert media_response.status_code == 200
    media_asset = media_response.json()
    assert media_asset["source_id"] == SOURCE_ID
    assert media_asset["stream_id"] == STREAM_ID
    assert media_asset["content_type"] == content_type
    assert media_asset["media_type"] == "image"
    assert media_asset["filename"] == body["file_name"]
    assert media_asset["file_size_bytes"] == len(b"image-bytes")
    assert "192.168.1.23" in media_asset["notes"]
    assert "Feeder" in media_asset["notes"]
    assert "Creates no Events, Visits, ReviewLabels, or truth." in media_asset["notes"]

    # SEC-2: GET /api/media/{id} now redacts local_path; real server-side
    # file placement is verified from the repository directly.
    real_asset = isolated_repository.get_media_asset(media_asset["id"])
    assert real_asset is not None
    saved_path = Path(real_asset.local_path).resolve()
    assert saved_path.is_relative_to(isolated_repository.media_root.resolve())
    assert saved_path.read_bytes() == b"image-bytes"

    after = await product_counts(client)
    assert after["media_assets"] == before["media_assets"] + 1
    for key in (
        "events",
        "visits",
        "review_labels",
        "motion_evidence",
        "species_suggestions",
        "detection_proposals",
        "dataset_exports",
    ):
        assert after[key] == before[key]


async def test_omitted_stream_id_uses_first_related_stream_deterministically(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await configure_external_url(client, {"url": PRIVATE_PREVIEW_URL})
    install_fake_fetch(monkeypatch, FakeResponse(b"image-bytes", {"Content-Type": "image/jpeg"}))

    response = await client.post(f"/api/sources/{SOURCE_ID}/external-url/preview/save", json={})

    assert response.status_code == 200
    assert response.json()["status"] == "saved"
    assert response.json()["stream_id"] == STREAM_ID


async def test_supplied_stream_id_must_belong_to_source(
    client: httpx.AsyncClient,
    isolated_repository: ProductRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    add_other_stream(isolated_repository)
    await configure_external_url(client, {"url": PRIVATE_PREVIEW_URL})

    def fail_if_called(*args, **kwargs):  # noqa: ANN002, ANN003
        raise AssertionError("Invalid stream must be rejected before fetch")

    monkeypatch.setattr(external_url_preview, "fetch_external_url_preview", fail_if_called)

    response = await client.post(
        f"/api/sources/{SOURCE_ID}/external-url/preview/save",
        json={"stream_id": OTHER_STREAM_ID},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Selected stream does not belong to the external URL Source."


async def test_missing_stream_id_returns_404_before_fetch(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await configure_external_url(client, {"url": PRIVATE_PREVIEW_URL})

    def fail_if_called(*args, **kwargs):  # noqa: ANN002, ANN003
        raise AssertionError("Missing stream must be rejected before fetch")

    monkeypatch.setattr(external_url_preview, "fetch_external_url_preview", fail_if_called)

    response = await client.post(
        f"/api/sources/{SOURCE_ID}/external-url/preview/save",
        json={"stream_id": "stream-missing"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Stream 'stream-missing' was not found."


@pytest.mark.parametrize("content_type", ["text/html", "video/mp4", "multipart/x-mixed-replace"])
async def test_unsupported_content_type_does_not_save(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    content_type: str,
) -> None:
    await configure_external_url(client, {"url": PRIVATE_PREVIEW_URL})
    before = await product_counts(client)
    install_fake_fetch(monkeypatch, FakeResponse(b"not-image", {"Content-Type": content_type}))

    response = await client.post(f"/api/sources/{SOURCE_ID}/external-url/preview/save", json={})

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "unsupported"
    assert body["media_asset_id"] is None
    assert body["content_type"] == content_type
    assert body["bytes_written"] == 0
    assert await product_counts(client) == before


async def test_content_length_over_max_bytes_does_not_save(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await configure_external_url(client, {"url": PRIVATE_PREVIEW_URL})
    before = await product_counts(client)
    response = FakeResponse(
        b"should-not-read",
        {"Content-Type": "image/jpeg", "Content-Length": "10"},
    )

    def fail_read(_size: int = -1) -> bytes:
        raise AssertionError("Body should not be read when Content-Length is over max_bytes")

    response.read = fail_read  # type: ignore[method-assign]
    install_fake_fetch(monkeypatch, response)

    result = await client.post(
        f"/api/sources/{SOURCE_ID}/external-url/preview/save",
        json={"max_bytes": 5},
    )

    assert result.status_code == 200
    assert result.json()["status"] == "unsupported"
    assert result.json()["bytes_written"] == 0
    assert await product_counts(client) == before


async def test_body_over_max_bytes_does_not_save(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await configure_external_url(client, {"url": PRIVATE_PREVIEW_URL})
    before = await product_counts(client)
    install_fake_fetch(monkeypatch, FakeResponse(b"abcdef", {"Content-Type": "image/jpeg"}))

    response = await client.post(
        f"/api/sources/{SOURCE_ID}/external-url/preview/save",
        json={"max_bytes": 5},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "unsupported"
    assert response.json()["bytes_written"] == 0
    assert await product_counts(client) == before


async def test_unsafe_url_does_not_fetch_or_save(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await configure_external_url(client, {"url": "http://127.0.0.1/still.jpg"})
    before = await product_counts(client)
    opener = install_fake_fetch(
        monkeypatch,
        FakeResponse(b"image-bytes", {"Content-Type": "image/jpeg"}),
    )

    response = await client.post(f"/api/sources/{SOURCE_ID}/external-url/preview/save", json={})

    assert response.status_code == 200
    assert response.json()["status"] == "unsupported"
    assert "Unsafe URL target" in response.json()["message"]
    assert opener.requests == []
    assert await product_counts(client) == before


async def test_redirect_does_not_save(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await configure_external_url(client, {"url": PRIVATE_PREVIEW_URL})
    before = await product_counts(client)
    install_fake_fetch(monkeypatch, HTTPError(PRIVATE_PREVIEW_URL, 302, "Found", {}, None))

    response = await client.post(f"/api/sources/{SOURCE_ID}/external-url/preview/save", json={})

    assert response.status_code == 200
    assert response.json()["status"] == "unsupported"
    assert "Redirects are not supported" in response.json()["message"]
    assert await product_counts(client) == before


async def test_timeout_or_network_error_does_not_save(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await configure_external_url(client, {"url": PRIVATE_PREVIEW_URL})
    before = await product_counts(client)
    install_fake_fetch(monkeypatch, URLError("timed out"))

    response = await client.post(f"/api/sources/{SOURCE_ID}/external-url/preview/save", json={})

    assert response.status_code == 200
    assert response.json()["status"] == "unavailable"
    assert response.json()["media_asset_id"] is None
    assert await product_counts(client) == before


async def test_save_response_and_notes_do_not_leak_raw_secrets(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await configure_external_url(
        client,
        {
            "url": PRIVATE_PREVIEW_URL,
            "auth_username": "viewer-secret",
            "auth_password": "password-secret",
        },
    )
    install_fake_fetch(monkeypatch, FakeResponse(b"image-bytes", {"Content-Type": "image/jpeg"}))

    response = await client.post(f"/api/sources/{SOURCE_ID}/external-url/preview/save", json={})

    assert response.status_code == 200
    body_text = str(response.json())
    assert "viewer-secret" not in body_text
    assert "password-secret" not in body_text
    media_response = await client.get(f"/api/media/{response.json()['media_asset_id']}")
    notes = media_response.json()["notes"]
    assert "viewer-secret" not in notes
    assert "password-secret" not in notes


async def test_existing_preview_route_still_creates_no_media_asset(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await configure_external_url(client, {"url": PRIVATE_PREVIEW_URL})
    before = await product_counts(client)
    install_fake_fetch(monkeypatch, FakeResponse(b"image-bytes", {"Content-Type": "image/jpeg"}))

    response = await client.post(f"/api/sources/{SOURCE_ID}/external-url/preview", json={})

    assert response.status_code == 200
    assert response.json()["status"] == "available"
    assert await product_counts(client) == before


async def test_status_routes_still_do_not_fetch_external_url(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await configure_external_url(client, {"url": PRIVATE_PREVIEW_URL})

    def fail_if_called(*args, **kwargs):  # noqa: ANN002, ANN003
        raise AssertionError("Status routes must not fetch external URLs")

    monkeypatch.setattr(external_url_preview, "fetch_external_url_preview", fail_if_called)

    responses = [
        await client.get(f"/api/sources/{SOURCE_ID}/connection"),
        await client.get(f"/api/sources/{SOURCE_ID}/setup-review"),
        await client.get(f"/api/streams/{STREAM_ID}/playback"),
    ]

    assert [response.status_code for response in responses] == [200, 200, 200]
