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


async def test_camera_can_be_renamed_archived_and_restored_without_losing_stream(
    client: httpx.AsyncClient,
) -> None:
    created = (await client.post("/api/sources", json={"name": "Feeder camera"})).json()
    source_id = created["source"]["id"]
    stream_id = created["stream"]["id"]

    renamed = await client.patch(
        f"/api/sources/{source_id}",
        json={"name": "East feeder camera"},
    )

    assert renamed.status_code == 200
    assert renamed.json()["source"]["name"] == "East feeder camera"
    assert renamed.json()["streams"][0]["id"] == stream_id
    assert renamed.json()["streams"][0]["name"] == "East feeder camera stream"

    archived = await client.patch(
        f"/api/sources/{source_id}",
        json={"archived": True},
    )

    assert archived.status_code == 200
    assert archived.json()["source"]["status"] == "archived"
    playback = (await client.get(f"/api/streams/{stream_id}/playback")).json()
    assert playback["status"] == "offline"
    assert playback["supports_live_playback"] is False
    blocked_start = await client.post(f"/api/streams/{stream_id}/live-session/start")
    assert blocked_start.status_code == 409

    restored = await client.patch(
        f"/api/sources/{source_id}",
        json={"archived": False},
    )

    assert restored.status_code == 200
    assert restored.json()["source"]["status"] == "needs_setup"
    assert restored.json()["streams"][0]["id"] == stream_id


async def test_sample_camera_cannot_be_renamed_or_archived(client: httpx.AsyncClient) -> None:
    response = await client.patch(
        "/api/sources/source-backyard-demo",
        json={"archived": True},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "The sample camera cannot be renamed or archived."


async def test_unreferenced_zone_can_be_removed_but_review_context_is_protected(
    client: httpx.AsyncClient,
) -> None:
    created = (await client.post("/api/sources", json={"name": "Zone test camera"})).json()
    stream_id = created["stream"]["id"]
    zone = (
        await client.post(
            "/api/zones",
            json={
                "stream_id": stream_id,
                "name": "Mistaken feeder",
                "zone_type": "feeder",
                "polygon": [
                    {"x": 0.1, "y": 0.1},
                    {"x": 0.3, "y": 0.1},
                    {"x": 0.3, "y": 0.3},
                ],
            },
        )
    ).json()["zone"]

    removed = await client.delete(f"/api/zones/{zone['id']}")

    assert removed.status_code == 200
    assert removed.json()["zone"]["id"] == zone["id"]
    assert removed.json()["zones"] == []

    protected = await client.delete("/api/zones/zone-feeder")
    assert protected.status_code == 409
    assert "Deactivate it instead" in protected.json()["detail"]


async def test_remove_sample_data_requires_real_camera_and_preserves_real_graph(
    client: httpx.AsyncClient,
) -> None:
    without_real_camera = await client.post(
        "/api/settings/remove-sample-data",
        json={"confirm": True},
    )
    assert without_real_camera.status_code == 409

    created = (await client.post("/api/sources", json={"name": "Real feeder camera"})).json()
    source_id = created["source"]["id"]
    stream_id = created["stream"]["id"]
    zone = (
        await client.post(
            "/api/zones",
            json={
                "stream_id": stream_id,
                "name": "Real feeder",
                "zone_type": "feeder",
                "polygon": [
                    {"x": 0.2, "y": 0.2},
                    {"x": 0.4, "y": 0.2},
                    {"x": 0.4, "y": 0.4},
                ],
            },
        )
    ).json()["zone"]

    removed = await client.post(
        "/api/settings/remove-sample-data",
        json={"confirm": True},
    )

    assert removed.status_code == 200
    result = removed.json()
    assert result["removed"] is True
    assert result["status"]["seed_data_present"] is False
    assert result["preserved_source_count"] == 1
    assert (await client.get("/api/sources/source-backyard-demo")).status_code == 404
    assert (await client.get(f"/api/sources/{source_id}")).status_code == 200
    assert (await client.get(f"/api/zones/{zone['id']}")).status_code == 200


async def test_remove_sample_data_protects_added_sample_work(
    client: httpx.AsyncClient,
) -> None:
    await client.post("/api/sources", json={"name": "Real camera"})
    await client.post(
        "/api/zones",
        json={
            "stream_id": "stream-backyard-feeder",
            "name": "Added sample Zone",
            "zone_type": "yard",
            "polygon": [
                {"x": 0.1, "y": 0.1},
                {"x": 0.2, "y": 0.1},
                {"x": 0.2, "y": 0.2},
            ],
        },
    )

    response = await client.post(
        "/api/settings/remove-sample-data",
        json={"confirm": True},
    )

    assert response.status_code == 409
    assert "preserved to avoid deleting user data" in response.json()["detail"]
    assert (await client.get("/api/sources/source-backyard-demo")).status_code == 200


async def test_reset_sample_walkthrough_preserves_real_camera_and_zone(
    client: httpx.AsyncClient,
) -> None:
    created = (await client.post("/api/sources", json={"name": "Persistent camera"})).json()
    source_id = created["source"]["id"]
    stream_id = created["stream"]["id"]
    zone = (
        await client.post(
            "/api/zones",
            json={
                "stream_id": stream_id,
                "name": "Persistent feeder",
                "zone_type": "feeder",
                "polygon": [
                    {"x": 0.2, "y": 0.2},
                    {"x": 0.5, "y": 0.2},
                    {"x": 0.5, "y": 0.5},
                ],
            },
        )
    ).json()["zone"]

    reset = await client.post("/api/settings/reset-demo-data")

    assert reset.status_code == 200
    assert reset.json()["source_count"] == 2
    assert reset.json()["zone_count"] == 4
    assert (await client.get(f"/api/sources/{source_id}")).status_code == 200
    assert (await client.get(f"/api/zones/{zone['id']}")).status_code == 200


async def test_remove_sample_data_never_leaves_a_dangling_stream_scoped_settings_row(
    client: httpx.AsyncClient,
    isolated_repository: ProductRepository,
) -> None:
    """Appliance / Storage / Privacy / Recovery v1, Phase O: a real,
    reproduced `PRAGMA foreign_key_check` failure on this project's own
    development database traced to exactly this gap -- `_delete_sample_
    graph` deleted the demo Stream but not its lazily-created Stage 7
    `observation_authority_settings` row, leaving a dangling foreign key
    that later blocked a real backup-restore-with-rebind. Touch all three
    of the Stream-scoped tables `_delete_sample_graph` now also cleans up,
    then prove none of them survive as an orphan after the demo Stream is
    genuinely deleted (never reseeded -- `remove_sample_data`, unlike
    `reset_demo_data`, does not recreate it under the same id)."""

    from mockingbird.observation.candidate_visit_authority import ObservationAuthorityMode
    from mockingbird.repository.product_repository import (
        ObservationAuthoritySettingsModel,
        StreamSpeciesCandidatePackSelectionModel,
    )
    from mockingbird.storage.models import YardMapStreamPlacementModel

    demo_stream_id = "stream-backyard-feeder"
    isolated_repository.set_observation_authority_mode(
        ObservationAuthorityMode.shadow, stream_id=demo_stream_id
    )
    with isolated_repository.session_factory() as session:
        assert session.get(ObservationAuthoritySettingsModel, demo_stream_id) is not None

    await client.post("/api/sources", json={"name": "Real camera"})
    removed = await client.post("/api/settings/remove-sample-data", json={"confirm": True})
    assert removed.status_code == 200
    assert removed.json()["removed"] is True

    from sqlalchemy import select

    with isolated_repository.session_factory() as session:
        assert session.get(ObservationAuthoritySettingsModel, demo_stream_id) is None
        assert (
            session.get(StreamSpeciesCandidatePackSelectionModel, demo_stream_id) is None
        )
        # Composite primary key (map_id, stream_id) -- query by stream_id
        # alone rather than `session.get()`, which needs the full key.
        assert (
            session.scalar(
                select(YardMapStreamPlacementModel).where(
                    YardMapStreamPlacementModel.stream_id == demo_stream_id
                )
            )
            is None
        )

    with isolated_repository.engine.connect() as connection:
        from sqlalchemy import text

        assert connection.execute(text("PRAGMA foreign_key_check")).fetchall() == []
