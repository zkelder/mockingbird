from __future__ import annotations

import base64
from datetime import UTC, datetime
from pathlib import Path
import struct
import zlib

import httpx
import pytest

from mockingbird.api.main import app, configure_repository, get_source_monitor_manager
from mockingbird.monitoring import (
    MonitorMotionResult,
    MonitorSnapshotResult,
    SourceMonitorManager,
    SourceMonitorOptions,
)
from mockingbird.repository.product_repository import ProductRepository
from mockingbird.source_providers import external_url_preview
from mockingbird.source_providers.external_url_preview import ExternalUrlPreviewFetchResult
from mockingbird.storage.models import StreamModel

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
    await get_source_monitor_manager().reset()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as api_client:
        yield api_client
    await get_source_monitor_manager().reset()


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


def blank_frame(*, width: int = 4, height: int = 4) -> list[list[int]]:
    return [[0 for _x in range(width)] for _y in range(height)]


def frame_with(
    points: list[tuple[int, int]],
    *,
    width: int = 4,
    height: int = 4,
) -> list[list[int]]:
    frame = blank_frame(width=width, height=height)
    for y, x in points:
        frame[y][x] = 255
    return frame


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


def stub_preview_fetch_with_frame(
    frame: list[list[int]],
):
    def fetch(
        url: str,
        *,
        timeout_seconds: float | None,
        max_bytes: int | None,
    ) -> ExternalUrlPreviewFetchResult:
        content = png_bytes(frame)
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

    return fetch


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


async def motion_evidence_count(client: httpx.AsyncClient) -> int:
    response = await client.get("/api/motion/evidence")
    assert response.status_code == 200
    return len(response.json()["motion_evidence"])


def seed_external_url_snapshot(
    repository: ProductRepository,
    *,
    frame: list[list[int]],
    stream_id: str = STREAM_ID,
    note: str = "Monitor review fixture.",
) -> str:
    media_asset = repository.create_external_url_preview_media_asset(
        source_id=SOURCE_ID,
        stream_id=stream_id,
        content=png_bytes(frame),
        content_type="image/png",
        fetched_at=datetime(2026, 1, 2, tzinfo=UTC),
        url_host="192.168.1.50",
        note=note,
    )
    return media_asset.id


def add_stream_without_zones(
    repository: ProductRepository,
    *,
    stream_id: str = "stream-monitor-auto-regions",
) -> str:
    with repository.session_factory() as session:
        with session.begin():
            if session.get(StreamModel, stream_id) is None:
                session.add(
                    StreamModel(
                        id=stream_id,
                        source_id=SOURCE_ID,
                        name="Monitor auto-region stream",
                        description="Synthetic monitor stream without named zones.",
                        is_live=False,
                    )
                )
    return stream_id


async def run_monitor_tick_for_seeded_frames(
    client: httpx.AsyncClient,
    repository: ProductRepository,
    monkeypatch: pytest.MonkeyPatch,
    *,
    stream_id: str = STREAM_ID,
    seed_frames: list[list[list[int]]],
    capture_frame: list[list[int]],
):
    await configure_external_url(client)
    await get_source_monitor_manager().reset()
    for index, frame in enumerate(seed_frames):
        seed_external_url_snapshot(
            repository,
            frame=frame,
            stream_id=stream_id,
            note=f"Monitor review fixture {index}.",
        )
    monkeypatch.setattr(
        external_url_preview,
        "fetch_external_url_preview",
        stub_preview_fetch_with_frame(capture_frame),
    )
    state = await get_source_monitor_manager().start(
        source_id=SOURCE_ID,
        stream_id=stream_id,
        options=SourceMonitorOptions(
            interval_seconds=30,
            max_runtime_seconds=60,
            max_snapshots=5,
            check_motion=True,
            create_review_activity=False,
        ),
        autostart=False,
    )
    assert state.status == "monitoring"
    tick_state = await get_source_monitor_manager().run_one_tick_for_tests(stream_id)
    assert tick_state is not None
    return tick_state


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


async def test_monitor_status_reports_review_activity_available_for_user_zone_activity(
    client: httpx.AsyncClient,
    repository: ProductRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tick_state = await run_monitor_tick_for_seeded_frames(
        client,
        repository,
        monkeypatch,
        seed_frames=[
            blank_frame(),
            frame_with([(1, 1)]),
        ],
        capture_frame=frame_with([(1, 1), (1, 2), (2, 1), (2, 2)]),
    )

    response = await client.get(f"/api/streams/{STREAM_ID}/monitor/status")

    assert response.status_code == 200
    status = response.json()
    assert tick_state.last_activity_detected is True
    assert status["last_activity_detected"] is True
    assert status["last_activity_area"]["zone_id"] == "zone-feeder"
    assert status["last_activity_area"]["zone_name"] == "Feeder"
    assert status["last_activity_area"]["zone_type"] == "feeder"
    assert status["last_activity_area"]["activity_summary"] == "Activity detected in Feeder."
    assert status["review_activity_available"] is True
    assert status["review_activity_created"] is False
    assert status["review_activity_unavailable_reason"] is None
    assert status["review_activity_motion_evidence_id"] is None
    assert len(status["last_motion_media_asset_ids"]) == 3
    assert status["best_snapshot_media_asset_id"] == status["last_motion_media_asset_ids"][-1]
    assert status["crop_plan"]["source_media_asset_id"] == status["best_snapshot_media_asset_id"]
    assert status["message"] == "Activity detected in Feeder. Create review activity when ready."


async def test_monitor_review_activity_create_is_explicit_pending_evidence_only(
    client: httpx.AsyncClient,
    repository: ProductRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await run_monitor_tick_for_seeded_frames(
        client,
        repository,
        monkeypatch,
        seed_frames=[
            blank_frame(),
            frame_with([(1, 1)]),
        ],
        capture_frame=frame_with([(1, 1), (1, 2), (2, 1), (2, 2)]),
    )
    before_truth = await product_truth_counts(client)
    before_evidence_count = await motion_evidence_count(client)

    create_response = await client.post(
        f"/api/streams/{STREAM_ID}/monitor/review-activity",
    )

    assert create_response.status_code == 200
    created_status = create_response.json()
    evidence_id = created_status["review_activity_motion_evidence_id"]
    assert created_status["review_activity_created"] is True
    assert created_status["review_activity_available"] is False
    assert created_status["review_activity_unavailable_reason"] is None
    assert evidence_id
    assert created_status["review_activity_event_id"] is None
    assert created_status["review_activity_visit_id"] is None
    assert created_status["message"] == "Review activity is ready."
    assert await motion_evidence_count(client) == before_evidence_count + 1
    assert await product_truth_counts(client) == before_truth

    evidence_response = await client.get("/api/motion/evidence")
    assert evidence_response.status_code == 200
    evidence = next(
        item
        for item in evidence_response.json()["motion_evidence"]
        if item["id"] == evidence_id
    )
    assert evidence["status"] == "pending"
    assert evidence["stream_id"] == STREAM_ID
    assert evidence["zone_id"] == "zone-feeder"
    assert evidence["snapshot_media_asset_id"] == created_status["best_snapshot_media_asset_id"]
    assert evidence["promoted_event_id"] is None
    assert evidence["promoted_visit_id"] is None

    repeated_response = await client.post(
        f"/api/streams/{STREAM_ID}/monitor/review-activity",
    )

    assert repeated_response.status_code == 200
    repeated_status = repeated_response.json()
    assert repeated_status["review_activity_motion_evidence_id"] == evidence_id
    assert await motion_evidence_count(client) == before_evidence_count + 1
    assert await product_truth_counts(client) == before_truth


async def test_monitor_review_activity_duplicate_session_does_not_create_duplicate(
    client: httpx.AsyncClient,
    repository: ProductRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await run_monitor_tick_for_seeded_frames(
        client,
        repository,
        monkeypatch,
        seed_frames=[
            blank_frame(),
            frame_with([(1, 1)]),
        ],
        capture_frame=frame_with([(1, 1), (1, 2), (2, 1), (2, 2)]),
    )
    first_response = await client.post(
        f"/api/streams/{STREAM_ID}/monitor/review-activity",
    )
    assert first_response.status_code == 200
    first_status = first_response.json()
    evidence_id = first_status["review_activity_motion_evidence_id"]
    evidence_count = await motion_evidence_count(client)
    before_truth = await product_truth_counts(client)

    monkeypatch.setattr(
        external_url_preview,
        "fetch_external_url_preview",
        stub_preview_fetch_with_frame(frame_with([(1, 1), (1, 2), (2, 1), (2, 2)])),
    )
    tick_state = await get_source_monitor_manager().run_one_tick_for_tests(STREAM_ID)
    assert tick_state is not None
    assert tick_state.last_session_status == "ongoing_activity"

    status_response = await client.get(f"/api/streams/{STREAM_ID}/monitor/status")
    assert status_response.status_code == 200
    status = status_response.json()
    assert status["review_activity_available"] is False
    assert status["review_activity_unavailable_reason"] == "already_exists"
    assert status["review_activity_motion_evidence_id"] == evidence_id

    duplicate_response = await client.post(
        f"/api/streams/{STREAM_ID}/monitor/review-activity",
    )

    assert duplicate_response.status_code == 200
    duplicate_status = duplicate_response.json()
    assert duplicate_status["review_activity_created"] is False
    assert duplicate_status["review_activity_unavailable_reason"] == "already_exists"
    assert duplicate_status["review_activity_motion_evidence_id"] == evidence_id
    assert await motion_evidence_count(client) == evidence_count
    assert await product_truth_counts(client) == before_truth


async def test_monitor_review_activity_auto_region_creates_zone_optional_evidence(
    client: httpx.AsyncClient,
    repository: ProductRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    auto_stream_id = add_stream_without_zones(repository)
    await run_monitor_tick_for_seeded_frames(
        client,
        repository,
        monkeypatch,
        stream_id=auto_stream_id,
        seed_frames=[
            blank_frame(),
            frame_with([(1, 1), (1, 2), (2, 1), (2, 2)]),
        ],
        capture_frame=blank_frame(),
    )
    before_truth = await product_truth_counts(client)
    before_evidence_count = await motion_evidence_count(client)

    create_response = await client.post(
        f"/api/streams/{auto_stream_id}/monitor/review-activity",
    )

    assert create_response.status_code == 200
    status = create_response.json()
    assert status["last_activity_detected"] is True
    assert status["last_activity_area"]["source"] == "auto_region"
    assert status["review_activity_available"] is False
    assert status["review_activity_created"] is True
    assert status["review_activity_unavailable_reason"] is None
    assert status["review_activity_motion_evidence_id"].startswith("motion-evidence-")
    evidence_response = await client.get(
        f"/api/motion/evidence/{status['review_activity_motion_evidence_id']}"
    )
    assert evidence_response.status_code == 200
    evidence = evidence_response.json()
    assert evidence["zone_id"] is None
    assert evidence["stream_id"] == auto_stream_id
    assert evidence["status"] == "pending"
    assert await motion_evidence_count(client) == before_evidence_count + 1
    assert await product_truth_counts(client) == before_truth

    zones_response = await client.get(f"/api/streams/{auto_stream_id}/zones")
    assert zones_response.status_code == 200
    assert zones_response.json() == []


async def test_monitor_review_activity_no_activity_cannot_create_review_item(
    client: httpx.AsyncClient,
    repository: ProductRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await run_monitor_tick_for_seeded_frames(
        client,
        repository,
        monkeypatch,
        seed_frames=[
            blank_frame(),
            blank_frame(),
        ],
        capture_frame=blank_frame(),
    )
    before_truth = await product_truth_counts(client)
    before_evidence_count = await motion_evidence_count(client)

    create_response = await client.post(
        f"/api/streams/{STREAM_ID}/monitor/review-activity",
    )

    assert create_response.status_code == 200
    status = create_response.json()
    assert status["last_activity_detected"] is False
    assert status["review_activity_available"] is False
    assert status["review_activity_created"] is False
    assert status["review_activity_unavailable_reason"] == "no_activity_detected"
    assert status["review_activity_motion_evidence_id"] is None
    assert await motion_evidence_count(client) == before_evidence_count
    assert await product_truth_counts(client) == before_truth
