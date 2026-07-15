from pathlib import Path

import httpx
import pytest

from mockingbird.api.main import app, configure_repository
from mockingbird.repository.product_repository import ProductRepository


pytestmark = pytest.mark.anyio


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


async def test_add_camera_creates_one_source_and_default_stream_only(
    client: httpx.AsyncClient,
) -> None:
    before_sources = (await client.get("/api/sources")).json()
    before_streams = (await client.get("/api/streams")).json()
    before_review_queue = (await client.get("/api/review-queue")).json()

    response = await client.post(
        "/api/sources",
        json={"name": "Backyard feeder camera"},
    )

    assert response.status_code == 201
    result = response.json()
    assert result["source"]["name"] == "Backyard feeder camera"
    assert result["source"]["kind"] == "local_camera"
    assert result["source"]["status"] == "needs_setup"
    assert result["stream"]["source_id"] == result["source"]["id"]
    assert result["stream"]["name"] == "Backyard feeder camera stream"
    assert result["stream"]["is_live"] is True

    after_sources = (await client.get("/api/sources")).json()
    after_streams = (await client.get("/api/streams")).json()
    after_review_queue = (await client.get("/api/review-queue")).json()
    configuration = (
        await client.get(
            f"/api/sources/{result['source']['id']}/provider-configuration"
        )
    ).json()

    assert len(after_sources) == len(before_sources) + 1
    assert len(after_streams) == len(before_streams) + 1
    assert after_review_queue == before_review_queue
    assert configuration["provider_key"] == "local_usb"
    assert configuration["configured_fields"] == []


async def test_add_camera_rejects_duplicate_name(client: httpx.AsyncClient) -> None:
    first = await client.post("/api/sources", json={"name": "Feeder camera"})
    duplicate = await client.post("/api/sources", json={"name": " feeder CAMERA "})

    assert first.status_code == 201
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"] == "A camera with that name already exists."


async def test_add_camera_rejects_blank_name(client: httpx.AsyncClient) -> None:
    response = await client.post("/api/sources", json={"name": "   "})

    assert response.status_code == 422
