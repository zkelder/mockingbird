from __future__ import annotations

import ipaddress
from pathlib import Path
from urllib.error import HTTPError, URLError

import httpx
import pytest

from mockingbird.api.main import app, configure_repository
from mockingbird.repository.product_repository import ProductRepository
from mockingbird.source_providers import external_url_preview

pytestmark = pytest.mark.anyio

SOURCE_ID = "source-backyard-demo"
STREAM_ID = "stream-backyard-feeder"
PRIVATE_PREVIEW_URL = "http://192.168.1.50/still.jpg"


class FakeResponse:
    def __init__(self, body: bytes, headers: dict[str, str] | None = None) -> None:
        self.body = body
        self.headers = headers or {}
        self.read_called = False

    def read(self, size: int = -1) -> bytes:
        self.read_called = True
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
    configure_repository(repository)
    yield repository
    configure_repository(None)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as api_client:
        yield api_client


@pytest.fixture(autouse=True)
def allow_private_lan_dns(monkeypatch: pytest.MonkeyPatch) -> None:
    def resolve(hostname: str):
        try:
            return [ipaddress.ip_address(hostname)]
        except ValueError:
            return [ipaddress.ip_address("192.168.1.50")]

    monkeypatch.setattr(
        external_url_preview,
        "_resolve_host_addresses",
        resolve,
    )


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


async def test_unknown_source_returns_404(client: httpx.AsyncClient) -> None:
    response = await client.post("/api/sources/source-missing/external-url/preview", json={})

    assert response.status_code == 404
    assert response.json()["detail"] == "Source 'source-missing' was not found."


async def test_non_external_url_source_returns_400(client: httpx.AsyncClient) -> None:
    response = await client.post(f"/api/sources/{SOURCE_ID}/external-url/preview", json={})

    assert response.status_code == 400
    assert response.json()["detail"] == "External URL preview requires an external_url Source provider."


async def test_external_url_missing_url_returns_not_configured_without_fetch(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await configure_external_url(client)

    def fail_if_called(*args, **kwargs):  # noqa: ANN002, ANN003
        raise AssertionError("Missing URL must not fetch")

    monkeypatch.setattr(external_url_preview, "fetch_external_url_preview", fail_if_called)

    response = await client.post(f"/api/sources/{SOURCE_ID}/external-url/preview", json={})

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "not_configured"
    assert body["preview_data_url"] is None
    assert body["supports_live_playback"] is False
    assert body["creates_truth"] is False
    assert body["creates_media_asset"] is False


@pytest.mark.parametrize(
    ("url", "message_part"),
    [
        ("ftp://192.168.1.50/still.jpg", "http and https"),
        ("http://viewer:secret@192.168.1.50/still.jpg", "Credentials"),
        ("http://192.168.1.50/still.jpg#fragment", "fragments"),
        ("http://127.0.0.1/still.jpg", "Unsafe URL target"),
        ("http://169.254.169.254/latest/meta-data", "Link-local metadata"),
        ("http://169.254.1.10/still.jpg", "Unsafe URL target"),
    ],
)
async def test_unsafe_urls_are_rejected_before_fetch(
    client: httpx.AsyncClient,
    url: str,
    message_part: str,
) -> None:
    await configure_external_url(client, {"url": url})

    response = await client.post(f"/api/sources/{SOURCE_ID}/external-url/preview", json={})

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "unsupported"
    assert message_part in body["message"]
    assert body["preview_data_url"] is None


async def test_private_lan_url_is_allowed_by_validator(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await configure_external_url(client, {"url": PRIVATE_PREVIEW_URL})
    opener = install_fake_fetch(
        monkeypatch,
        FakeResponse(b"jpeg-bytes", {"Content-Type": "image/jpeg"}),
    )

    response = await client.post(f"/api/sources/{SOURCE_ID}/external-url/preview", json={})

    assert response.status_code == 200
    assert response.json()["status"] == "available"
    assert opener.requests[0].full_url == PRIVATE_PREVIEW_URL


@pytest.mark.parametrize(
    ("content_type", "prefix"),
    [
        ("image/jpeg", "data:image/jpeg;base64,"),
        ("image/png", "data:image/png;base64,"),
        ("image/webp", "data:image/webp;base64,"),
    ],
)
async def test_supported_still_image_fetch_returns_data_url(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    content_type: str,
    prefix: str,
) -> None:
    await configure_external_url(client, {"url": PRIVATE_PREVIEW_URL})
    opener = install_fake_fetch(
        monkeypatch,
        FakeResponse(b"image-bytes", {"Content-Type": f"{content_type}; charset=binary"}),
    )

    response = await client.post(
        f"/api/sources/{SOURCE_ID}/external-url/preview",
        json={"timeout_seconds": 20, "max_bytes": 100},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "available"
    assert body["content_type"] == content_type
    assert body["bytes_read"] == len(b"image-bytes")
    assert body["preview_data_url"].startswith(prefix)
    assert body["supports_live_playback"] is False
    assert body["creates_truth"] is False
    assert body["creates_media_asset"] is False
    assert opener.requests[0].get_method() == "GET"
    assert opener.requests[0].headers["User-agent"] == "MockingBird local preview"
    assert opener.timeouts == [10.0]


@pytest.mark.parametrize("content_type", ["text/html", "video/mp4", "multipart/x-mixed-replace"])
async def test_unsupported_content_types_are_rejected_safely(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    content_type: str,
) -> None:
    await configure_external_url(client, {"url": PRIVATE_PREVIEW_URL})
    install_fake_fetch(monkeypatch, FakeResponse(b"not-image", {"Content-Type": content_type}))

    response = await client.post(f"/api/sources/{SOURCE_ID}/external-url/preview", json={})

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "unsupported"
    assert body["content_type"] == content_type
    assert body["preview_data_url"] is None


async def test_content_length_over_max_bytes_rejected_before_body_read(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await configure_external_url(client, {"url": PRIVATE_PREVIEW_URL})
    response = FakeResponse(
        b"should-not-read",
        {"Content-Type": "image/jpeg", "Content-Length": "10"},
    )

    def fail_read(_size: int = -1) -> bytes:
        raise AssertionError("Body should not be read when Content-Length is over max_bytes")

    response.read = fail_read  # type: ignore[method-assign]
    install_fake_fetch(monkeypatch, response)

    result = await client.post(
        f"/api/sources/{SOURCE_ID}/external-url/preview",
        json={"max_bytes": 5},
    )

    assert result.status_code == 200
    body = result.json()
    assert body["status"] == "unsupported"
    assert body["content_length"] == 10
    assert body["bytes_read"] is None


async def test_body_over_max_bytes_rejected(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await configure_external_url(client, {"url": PRIVATE_PREVIEW_URL})
    install_fake_fetch(monkeypatch, FakeResponse(b"abcdef", {"Content-Type": "image/jpeg"}))

    response = await client.post(
        f"/api/sources/{SOURCE_ID}/external-url/preview",
        json={"max_bytes": 5},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "unsupported"
    assert body["bytes_read"] == 6
    assert body["preview_data_url"] is None


async def test_timeout_or_network_error_returns_unavailable(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await configure_external_url(client, {"url": PRIVATE_PREVIEW_URL})
    install_fake_fetch(monkeypatch, URLError("timed out"))

    response = await client.post(f"/api/sources/{SOURCE_ID}/external-url/preview", json={})

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "unavailable"
    assert "timed out" in body["message"]


async def test_redirects_are_not_followed(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await configure_external_url(client, {"url": PRIVATE_PREVIEW_URL})
    install_fake_fetch(monkeypatch, HTTPError(PRIVATE_PREVIEW_URL, 302, "Found", {}, None))

    response = await client.post(f"/api/sources/{SOURCE_ID}/external-url/preview", json={})

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "unsupported"
    assert "Redirects are not supported" in body["message"]


async def test_response_does_not_leak_secret_values(
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

    response = await client.post(f"/api/sources/{SOURCE_ID}/external-url/preview", json={})

    assert response.status_code == 200
    body_text = str(response.json())
    assert "viewer-secret" not in body_text
    assert "password-secret" not in body_text
    assert "authenticated preview fetch is not implemented" in body_text


async def test_preview_route_creates_no_product_truth_or_media_asset(
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


async def test_status_routes_do_not_fetch_external_url(
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
