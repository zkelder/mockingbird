from __future__ import annotations

import base64
from datetime import UTC, datetime
from pathlib import Path
import struct
import zlib

import httpx
import pytest

from mockingbird.api.main import app, configure_repository
from mockingbird.monitoring import (
    MonitorMotionResult,
    MonitorSnapshotResult,
    SourceMonitorManager,
    SourceMonitorOptions,
)
from mockingbird.repository.product_repository import ProductRepository
from mockingbird.source_providers import external_url_preview
from mockingbird.source_providers.external_url_preview import ExternalUrlPreviewFetchResult

pytestmark = pytest.mark.anyio

SOURCE_ID = "source-backyard-demo"
STREAM_ID = "stream-backyard-feeder"
EXTERNAL_URL = "http://192.168.1.50/camera/still.jpg"


@pytest.fixture
def repository(tmp_path: Path) -> ProductRepository:
    active_repository = ProductRepository(
        db_url=f"sqlite:///{tmp_path / 'mockingbird.sqlite3'}",
        media_root=tmp_path / "media",
    )
    configure_repository(active_repository)
    yield active_repository
    configure_repository(None)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def client(repository: ProductRepository):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as api_client:
        yield api_client


def png_bytes(rows: list[list[int]] | None = None) -> bytes:
    rows = rows or [[0, 0], [0, 255]]
    height = len(rows)
    width = len(rows[0])
    raw = b"".join(bytes([0, *row]) for row in rows)

    def chunk(chunk_type: bytes, data: bytes) -> bytes:
        checksum = zlib.crc32(chunk_type + data) & 0xFFFFFFFF
        return (
            len(data).to_bytes(4, "big")
            + chunk_type
            + data
            + checksum.to_bytes(4, "big")
        )

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(
        b"IDAT",
        zlib.compress(raw),
    ) + chunk(b"IEND", b"")


async def configure_external_url(client: httpx.AsyncClient) -> None:
    response = await client.patch(
        f"/api/sources/{SOURCE_ID}/provider-configuration",
        json={"provider_key": "external_url", "config": {"url": EXTERNAL_URL}},
    )
    assert response.status_code == 200


def stub_preview_fetch(
    url: str,
    *,
    timeout_seconds: float | None,
    max_bytes: int | None,
) -> ExternalUrlPreviewFetchResult:
    content = png_bytes()
    encoded = base64.b64encode(content).decode("ascii")
    return ExternalUrlPreviewFetchResult(
        status="available",
        message=f"Fetched {url} for monitor test.",
        fetched_at=datetime(2026, 1, 2, tzinfo=UTC),
        content_type="image/png",
        content_length=len(content),
        bytes_read=len(content),
        preview_data_url=f"data:image/png;base64,{encoded}",
        fetched_bytes=content,
    )


async def product_truth_counts(client: httpx.AsyncClient) -> dict[str, int]:
    responses = {
        "review_labels": await client.get("/api/review-labels"),
        "dataset_exports": await client.get("/api/dataset-exports"),
        "events": await client.get("/api/events"),
        "visits": await client.get("/api/visits"),
    }
    assert all(response.status_code == 200 for response in responses.values())
    return {
        key: len(response.json())
        for key, response in responses.items()
    }


async def test_monitor_status_before_start_is_stopped(client: httpx.AsyncClient) -> None:
    response = await client.get(f"/api/streams/{STREAM_ID}/monitor/status")

    assert response.status_code == 200
    status = response.json()
    assert status["status"] == "stopped"
    assert status["stream_id"] == STREAM_ID
    assert status["persistent"] is False
    assert status["creates_truth"] is False


async def test_start_monitor_returns_state_and_duplicate_start_reuses_monitor(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await configure_external_url(client)
    monkeypatch.setattr(external_url_preview, "fetch_external_url_preview", stub_preview_fetch)

    first_response = await client.post(
        f"/api/streams/{STREAM_ID}/monitor/start",
        json={"interval_seconds": 30, "max_runtime_minutes": 1, "max_snapshots": 5},
    )
    second_response = await client.post(
        f"/api/streams/{STREAM_ID}/monitor/start",
        json={"interval_seconds": 30, "max_runtime_minutes": 1, "max_snapshots": 5},
    )

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    first = first_response.json()
    second = second_response.json()
    assert first["status"] in {"starting", "monitoring"}
    assert second["status"] in {"starting", "monitoring"}
    assert second["monitor_id"] == first["monitor_id"]
    assert second["persistent"] is False
    assert second["creates_truth"] is False

    stop_response = await client.post(f"/api/streams/{STREAM_ID}/monitor/stop")
    assert stop_response.status_code == 200
    assert stop_response.json()["status"] == "stopped_by_user"


async def test_monitor_start_validates_interval_and_external_url_source(
    client: httpx.AsyncClient,
) -> None:
    too_fast = await client.post(
        f"/api/streams/{STREAM_ID}/monitor/start",
        json={"interval_seconds": 4},
    )
    assert too_fast.status_code == 422

    unsupported = await client.post(
        f"/api/streams/{STREAM_ID}/monitor/start",
        json={"interval_seconds": 5},
    )
    assert unsupported.status_code == 400
    assert "external URL Sources only" in unsupported.json()["detail"]


async def test_monitor_start_blocks_when_external_url_missing(
    client: httpx.AsyncClient,
) -> None:
    response = await client.patch(
        f"/api/sources/{SOURCE_ID}/provider-configuration",
        json={"provider_key": "external_url", "config": {}},
    )
    assert response.status_code == 200

    start_response = await client.post(
        f"/api/streams/{STREAM_ID}/monitor/start",
        json={"interval_seconds": 5},
    )

    assert start_response.status_code == 400
    assert "Add an external URL" in start_response.json()["detail"]


async def test_storage_guardrail_blocks_monitor_start(
    client: httpx.AsyncClient,
    repository: ProductRepository,
) -> None:
    await configure_external_url(client)
    for _index in range(100):
        repository.create_external_url_preview_media_asset(
            source_id=SOURCE_ID,
            stream_id=STREAM_ID,
            content=png_bytes(),
            content_type="image/png",
            fetched_at=datetime(2026, 1, 2, tzinfo=UTC),
            url_host="192.168.1.50",
            note="Storage guardrail fixture.",
        )

    response = await client.post(
        f"/api/streams/{STREAM_ID}/monitor/start",
        json={"interval_seconds": 5},
    )

    assert response.status_code == 400
    assert "Storage guardrails" in response.json()["detail"]


async def test_monitor_does_not_create_review_truth_or_exports(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await configure_external_url(client)
    monkeypatch.setattr(external_url_preview, "fetch_external_url_preview", stub_preview_fetch)
    before = await product_truth_counts(client)

    start_response = await client.post(
        f"/api/streams/{STREAM_ID}/monitor/start",
        json={
            "interval_seconds": 30,
            "max_runtime_minutes": 1,
            "max_snapshots": 5,
            "create_review_activity": True,
        },
    )
    assert start_response.status_code == 200
    stop_response = await client.post(f"/api/streams/{STREAM_ID}/monitor/stop")
    assert stop_response.status_code == 200

    assert await product_truth_counts(client) == before
    assert stop_response.json()["create_review_activity"] is False
    assert stop_response.json()["creates_exports"] is False


async def test_monitor_manager_tick_is_deterministic_without_sleep() -> None:
    captured: list[str] = []
    saved_ids: list[str] = ["media-asset-old"]

    async def capture_snapshot(source_id: str, stream_id: str) -> MonitorSnapshotResult:
        captured.append(f"{source_id}:{stream_id}")
        saved_ids.append("media-asset-new")
        return MonitorSnapshotResult(
            media_asset_id="media-asset-new",
            status="saved",
            message="Saved.",
        )

    async def list_saved_images(source_id: str, stream_id: str) -> list[str]:
        return list(saved_ids)

    async def evaluate_saved_media(
        stream_id: str,
        media_asset_ids: list[str],
        create_review_activity: bool,
    ) -> MonitorMotionResult:
        assert create_review_activity is False
        return MonitorMotionResult(
            activity_detected=True,
            activity_area={"area_id": "activity-area-1", "label": "Activity area 1"},
            session_status="new_activity",
            best_media_asset_id=media_asset_ids[-1],
        )

    manager = SourceMonitorManager(
        capture_snapshot=capture_snapshot,
        list_saved_images=list_saved_images,
        evaluate_saved_media=evaluate_saved_media,
    )
    state = await manager.start(
        source_id="source-test",
        stream_id="stream-test",
        options=SourceMonitorOptions(
            interval_seconds=30,
            max_runtime_seconds=60,
            max_snapshots=3,
            check_motion=True,
            create_review_activity=False,
        ),
        autostart=False,
    )
    assert state.status == "monitoring"

    tick_state = await manager.run_one_tick_for_tests("stream-test")

    assert captured == ["source-test:stream-test"]
    assert tick_state is not None
    assert tick_state.snapshots_attempted == 1
    assert tick_state.snapshots_saved == 1
    assert tick_state.motion_checks_run == 1
    assert tick_state.last_activity_detected is True
    assert tick_state.last_activity_area == {
        "area_id": "activity-area-1",
        "label": "Activity area 1",
    }
    assert tick_state.last_session_status == "new_activity"
