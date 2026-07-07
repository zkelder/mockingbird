import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest

from mockingbird.api.main import (
    app,
    capture_stream_local_camera_frame,
    configure_repository,
    get_live_camera_session_manager,
    get_stream_live_camera_session_mjpeg,
    get_stream_local_mjpeg_bridge,
    get_stream_rtsp_mjpeg_bridge,
    get_stream_windows_dshow_mjpeg_bridge,
)
from mockingbird.api.schemas import SourceKind, SourceStatus
from mockingbird.playback import (
    live_frame_cache,
    local_camera_bridge,
    rtsp_bridge,
    windows_camera_bridge,
)
from mockingbird.repository.product_repository import ProductRepository
from mockingbird.sampler.saved_media_frames import SavedMediaFrame
from mockingbird.storage.models import CameraSourceModel, StreamModel

pytestmark = pytest.mark.anyio

SOURCE_ID = "source-backyard-demo"
STREAM_ID = "stream-backyard-feeder"


@pytest.fixture(autouse=True)
def isolated_repository(tmp_path: Path) -> ProductRepository:
    get_live_camera_session_manager().stop_all(reason="test_reset")
    live_frame_cache.clear_all_frames()
    repository = ProductRepository(
        db_url=f"sqlite:///{tmp_path / 'mockingbird.sqlite3'}",
        media_root=tmp_path / "media",
    )
    configure_repository(repository)
    yield repository
    get_live_camera_session_manager().stop_all(reason="test_reset")
    live_frame_cache.clear_all_frames()
    configure_repository(None)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as api_client:
        yield api_client


class FakeStdout:
    def __init__(self, chunks: list[bytes]) -> None:
        self._chunks = chunks

    def read(self, chunk_size: int) -> bytes:
        return self._chunks.pop(0) if self._chunks else b""


class FakeFfmpegProcess:
    def __init__(self, chunks: list[bytes]) -> None:
        self.stdout = FakeStdout(chunks)
        self.terminated = False
        self.killed = False
        self.waited = False

    def poll(self) -> int | None:
        return None

    def terminate(self) -> None:
        self.terminated = True

    def wait(self, timeout: float | None = None) -> int:
        self.waited = True
        return 0

    def kill(self) -> None:
        self.killed = True


def test_live_frame_cache_returns_fresh_latest_frame() -> None:
    captured_at = datetime.now(UTC)
    frame_bytes = b"\xff\xd8live-frame\xff\xd9"

    frame = live_frame_cache.store_latest_frame(
        STREAM_ID,
        frame_bytes,
        captured_at=captured_at,
    )

    cached = live_frame_cache.get_latest_frame(
        STREAM_ID,
        now=captured_at + timedelta(seconds=1),
    )
    assert cached == frame
    assert cached is not None
    assert cached.frame_bytes == frame_bytes
    assert cached.age_ms(captured_at + timedelta(seconds=1)) == 1000


def test_live_frame_cache_ignores_stale_frame() -> None:
    captured_at = datetime.now(UTC)
    live_frame_cache.store_latest_frame(
        STREAM_ID,
        b"\xff\xd8stale-frame\xff\xd9",
        captured_at=captured_at,
    )

    cached = live_frame_cache.get_latest_frame(
        STREAM_ID,
        max_age_seconds=5,
        now=captured_at + timedelta(seconds=6),
    )

    assert cached is None


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


def test_live_frame_cache_returns_bounded_recent_frames() -> None:
    captured_at = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    for index in range(live_frame_cache.DEFAULT_MAX_FRAMES + 3):
        live_frame_cache.store_latest_frame(
            STREAM_ID,
            f"\xff\xd8frame-{index}\xff\xd9".encode("latin1"),
            captured_at=captured_at + timedelta(seconds=index),
        )

    recent = live_frame_cache.get_recent_frames(
        STREAM_ID,
        max_age_seconds=120,
        now=captured_at + timedelta(seconds=30),
    )

    assert len(recent) == live_frame_cache.DEFAULT_MAX_FRAMES
    assert [frame.sequence for frame in recent] == list(range(4, 24))
    assert recent[-1].frame_bytes == b"\xff\xd8frame-22\xff\xd9"


def test_live_frame_cache_recent_frames_ignore_stale_frames() -> None:
    captured_at = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    live_frame_cache.store_latest_frame(
        STREAM_ID,
        b"\xff\xd8stale-frame\xff\xd9",
        captured_at=captured_at,
    )
    live_frame_cache.store_latest_frame(
        STREAM_ID,
        b"\xff\xd8fresh-frame\xff\xd9",
        captured_at=captured_at + timedelta(seconds=10),
    )

    recent = live_frame_cache.get_recent_frames(
        STREAM_ID,
        max_age_seconds=5,
        now=captured_at + timedelta(seconds=12),
    )

    assert [frame.frame_bytes for frame in recent] == [b"\xff\xd8fresh-frame\xff\xd9"]


def test_live_frame_cache_status_reports_recent_frame_diagnostics() -> None:
    captured_at = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    live_frame_cache.store_latest_frame(
        STREAM_ID,
        b"\xff\xd8frame-1\xff\xd9",
        captured_at=captured_at,
    )
    live_frame_cache.store_latest_frame(
        STREAM_ID,
        b"\xff\xd8frame-2\xff\xd9",
        captured_at=captured_at + timedelta(seconds=2),
    )
    newest = live_frame_cache.store_latest_frame(
        STREAM_ID,
        b"\xff\xd8frame-3\xff\xd9",
        captured_at=captured_at + timedelta(seconds=4),
    )

    status = live_frame_cache.get_cache_status(
        STREAM_ID,
        max_age_seconds=3,
        max_frames=3,
        now=captured_at + timedelta(seconds=5),
    )

    assert status.stream_id == STREAM_ID
    assert status.recent_frame_count == 2
    assert status.newest_frame_age_ms == 1000
    assert status.oldest_frame_age_ms == 5000
    assert status.newest_frame_sequence == newest.sequence
    assert status.buffer_capacity == 3
    assert status.fresh_enough is True
    assert status.last_frame_at == newest.captured_at


async def product_counts(client: httpx.AsyncClient) -> dict[str, int]:
    responses = {
        "events": await client.get("/api/events"),
        "visits": await client.get("/api/visits"),
        "media_assets": await client.get("/api/media"),
        "review_labels": await client.get("/api/review-labels"),
        "motion_evidence": await client.get("/api/motion/evidence"),
        "species_suggestions": await client.get("/api/species-suggestions"),
        "detection_proposals": await client.get("/api/detection-proposals"),
        "dataset_exports": await client.get("/api/dataset-exports"),
    }
    assert all(response.status_code == 200 for response in responses.values())

    return {
        "events": len(responses["events"].json()),
        "visits": len(responses["visits"].json()),
        "media_assets": len(responses["media_assets"].json()),
        "review_labels": len(responses["review_labels"].json()),
        "motion_evidence": len(responses["motion_evidence"].json()["motion_evidence"]),
        "species_suggestions": len(responses["species_suggestions"].json()["species_suggestions"]),
        "detection_proposals": len(responses["detection_proposals"].json()),
        "dataset_exports": len(responses["dataset_exports"].json()),
    }


async def dataset_coverage(client: httpx.AsyncClient) -> dict:
    response = await client.get("/api/dataset-coverage/summary")
    assert response.status_code == 200
    return response.json()


def patch_live_motion_decoder(
    monkeypatch: pytest.MonkeyPatch,
    frames_by_bytes: dict[bytes, list[list[int]]],
) -> None:
    def fake_load_image_frame_plane_bytes(
        frame_bytes: bytes,
        *,
        content_type: str,
        max_dimension: int = 32,
    ) -> SavedMediaFrame:
        frame = frames_by_bytes[frame_bytes]
        return SavedMediaFrame(width=len(frame[0]), height=len(frame), frame=frame)

    monkeypatch.setattr(
        "mockingbird.api.main.load_image_frame_plane_bytes",
        fake_load_image_frame_plane_bytes,
    )


def patch_camera_processes_to_fail(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_if_called(*args: object, **kwargs: object) -> object:
        raise AssertionError("Live motion evaluation must not start a camera process")

    monkeypatch.setattr(
        "mockingbird.api.main.local_camera_bridge.start_local_camera_mjpeg_process",
        fail_if_called,
    )
    monkeypatch.setattr(
        "mockingbird.api.main.local_camera_bridge.capture_local_camera_frame",
        fail_if_called,
    )
    monkeypatch.setattr(
        "mockingbird.api.main.windows_camera_bridge.start_windows_dshow_mjpeg_process",
        fail_if_called,
    )
    monkeypatch.setattr(
        "mockingbird.api.main.windows_camera_bridge.capture_windows_dshow_frame",
        fail_if_called,
    )
    monkeypatch.setattr(
        "mockingbird.api.main.rtsp_bridge.start_rtsp_mjpeg_process",
        fail_if_called,
    )


async def configure_external_url_live_stream(
    client: httpx.AsyncClient,
    *,
    live_stream_url: str,
    live_stream_type: str,
) -> None:
    response = await client.patch(
        f"/api/sources/{SOURCE_ID}/provider-configuration",
        json={
            "provider_key": "external_url",
            "config": {
                "url": "http://camera.local/still.jpg",
                "live_stream_url": live_stream_url,
                "live_stream_type": live_stream_type,
            },
        },
    )
    assert response.status_code == 200


async def configure_local_usb_camera(
    client: httpx.AsyncClient,
    *,
    device: str | None,
    camera_format: str = "v4l2",
    video_size: str | None = None,
    preview_video_size: str | None = None,
    capture_video_size: str | None = None,
    framerate: str | None = None,
    input_format: str | None = None,
    brightness: str | None = None,
    contrast: str | None = None,
    exposure: str | None = None,
    zoom_mode: str | None = None,
) -> None:
    response = await client.patch(
        f"/api/sources/{SOURCE_ID}/provider-configuration",
        json={
            "provider_key": "local_usb",
            "config": {
                "live_stream_type": "local_usb",
                "local_camera_device": device,
                "local_camera_format": camera_format,
                "video_size": video_size,
                "preview_video_size": preview_video_size,
                "capture_video_size": capture_video_size,
                "framerate": framerate,
                "input_format": input_format,
                "brightness": brightness,
                "contrast": contrast,
                "exposure": exposure,
                "zoom_mode": zoom_mode,
            },
        },
    )
    assert response.status_code == 200


async def configure_windows_dshow_camera(
    client: httpx.AsyncClient,
    *,
    camera_name: str | None,
    ffmpeg_binary_path: str | None = None,
    video_size: str | None = None,
    preview_video_size: str | None = None,
    capture_video_size: str | None = None,
    framerate: str | None = None,
    input_format: str | None = None,
) -> None:
    response = await client.patch(
        f"/api/sources/{SOURCE_ID}/provider-configuration",
        json={
            "provider_key": "local_usb",
            "config": {
                "live_stream_type": "windows_dshow",
                "windows_camera_name": camera_name,
                "ffmpeg_binary_path": ffmpeg_binary_path,
                "video_size": video_size,
                "preview_video_size": preview_video_size,
                "capture_video_size": capture_video_size,
                "framerate": framerate,
                "input_format": input_format,
            },
        },
    )
    assert response.status_code == 200


async def wait_for_live_session_frame_count(
    client: httpx.AsyncClient,
    stream_id: str,
    *,
    minimum: int,
) -> dict:
    last_status: dict | None = None
    for _index in range(40):
        response = await client.get(f"/api/streams/{stream_id}/live-session/status")
        assert response.status_code == 200
        last_status = response.json()
        if last_status["frame_count"] >= minimum:
            return last_status
        await asyncio.sleep(0.05)
    assert last_status is not None
    assert last_status["frame_count"] >= minimum
    return last_status


async def test_known_demo_stream_returns_playback_contract(client: httpx.AsyncClient) -> None:
    response = await client.get(f"/api/streams/{STREAM_ID}/playback")

    assert response.status_code == 200
    playback = response.json()
    assert playback["stream_id"] == STREAM_ID
    assert playback["source_id"] == SOURCE_ID
    assert playback["status"] == "demo"
    assert playback["playback_kind"] == "demo_panel"
    assert playback["display_title"] == "Backyard feeder stream"
    assert "no real video playback" in playback["message"]
    assert playback["setup_hint"]
    assert playback["supports_zone_editing"] is True
    assert playback["supports_live_playback"] is False
    assert playback["adapter_key"] == "demo"
    assert playback["last_checked_at"] is None
    assert playback["preview_media_asset_id"] is None
    assert playback["preview_url"] is None


async def test_unknown_stream_playback_returns_404(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/streams/stream-missing/playback")

    assert response.status_code == 404
    assert response.json()["detail"] == "Stream 'stream-missing' was not found."


async def test_playback_contract_does_not_create_product_truth(client: httpx.AsyncClient) -> None:
    before = await product_counts(client)

    response = await client.get(f"/api/streams/{STREAM_ID}/playback")

    assert response.status_code == 200
    assert await product_counts(client) == before


async def test_playback_contract_does_not_claim_live_playback(client: httpx.AsyncClient) -> None:
    response = await client.get(f"/api/streams/{STREAM_ID}/playback")

    assert response.status_code == 200
    playback = response.json()
    assert playback["supports_live_playback"] is False
    assert playback["playback_kind"] in {"demo_panel", "placeholder"}


async def test_live_motion_evaluation_waits_for_live_frames(client: httpx.AsyncClient) -> None:
    response = await client.post(f"/api/streams/{STREAM_ID}/live-motion/evaluate", json={})

    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "waiting_for_live_frames"
    assert result["session_status"] == "waiting_for_frames"
    assert result["activity_detected"] is False
    assert result["frames_available"] == 0
    assert result["frames_considered"] == 0
    assert result["recent_frame_count"] == 0
    assert result["fresh_enough"] is False
    assert result["evaluated_at"]
    assert result["last_evaluation_message"] == result["message"]
    assert result["best_media_asset_id"] is None
    assert result["creates_truth"] is False
    assert result["creates_export"] is False


async def test_live_motion_evaluation_requires_camera_session_for_backend_camera_stream(
    client: httpx.AsyncClient,
) -> None:
    await configure_local_usb_camera(
        client,
        device="/dev/video0",
        capture_video_size="1920x1080",
        framerate="15",
        input_format="mjpeg",
    )
    before = await product_counts(client)

    response = await client.post(f"/api/streams/{STREAM_ID}/live-motion/evaluate", json={})

    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "start_session_required"
    assert result["session_status"] == "waiting_for_session"
    assert result["activity_detected"] is False
    assert result["frames_available"] == 0
    assert result["frames_considered"] == 0
    assert result["camera_session_status"] == "stopped"
    assert result["camera_session_frame_count"] == 0
    assert result["message"] == "Start camera session before monitoring."
    assert result["creates_event"] is False
    assert result["creates_visit"] is False
    assert result["creates_truth"] is False
    assert result["creates_export"] is False
    assert await product_counts(client) == before


async def test_live_motion_evaluation_requires_two_fresh_frames(client: httpx.AsyncClient) -> None:
    live_frame_cache.store_latest_frame(STREAM_ID, b"\xff\xd8only-frame\xff\xd9")

    response = await client.post(f"/api/streams/{STREAM_ID}/live-motion/evaluate", json={})

    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "not_enough_frames"
    assert result["session_status"] == "waiting_for_frames"
    assert result["activity_detected"] is False
    assert result["frames_available"] == 1
    assert result["frames_considered"] == 1
    assert result["recent_frame_count"] == 1
    assert result["newest_frame_sequence"] == 1
    assert result["fresh_enough"] is False


async def test_live_motion_evaluation_reports_no_recent_frames_for_stale_cache(
    client: httpx.AsyncClient,
) -> None:
    live_frame_cache.store_latest_frame(
        STREAM_ID,
        b"\xff\xd8stale-live-frame\xff\xd9",
        captured_at=datetime.now(UTC) - timedelta(seconds=30),
    )

    response = await client.post(
        f"/api/streams/{STREAM_ID}/live-motion/evaluate",
        json={"max_age_seconds": 5},
    )

    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "no_recent_frames"
    assert result["session_status"] == "no_recent_frames"
    assert result["activity_detected"] is False
    assert result["frames_available"] == 0
    assert result["frames_considered"] == 0
    assert result["recent_frame_count"] == 0
    assert result["newest_frame_age_ms"] is not None
    assert result["newest_frame_age_ms"] >= 30000
    assert result["last_frame_at"] is not None


async def test_live_motion_evaluation_reports_decode_failed(
    client: httpx.AsyncClient,
) -> None:
    captured_at = datetime.now(UTC)
    live_frame_cache.store_latest_frame(STREAM_ID, b"not-an-image-1", captured_at=captured_at)
    live_frame_cache.store_latest_frame(
        STREAM_ID,
        b"not-an-image-2",
        captured_at=captured_at + timedelta(seconds=1),
    )

    response = await client.post(f"/api/streams/{STREAM_ID}/live-motion/evaluate", json={})

    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "decode_failed"
    assert result["session_status"] == "decode_failed"
    assert result["activity_detected"] is False
    assert result["frames_available"] == 2
    assert result["frames_considered"] == 2
    assert result["last_error"] == "Recent live frames could not be decoded for motion."
    assert result["last_evaluation_message"] == result["last_error"]


async def test_live_motion_evaluation_uses_cached_frames_and_saves_best_frame_only(
    client: httpx.AsyncClient,
    isolated_repository: ProductRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    frame_0 = b"\xff\xd8live-motion-0\xff\xd9"
    frame_1 = b"\xff\xd8live-motion-1\xff\xd9"
    captured_at = datetime.now(UTC)
    patch_camera_processes_to_fail(monkeypatch)
    patch_live_motion_decoder(
        monkeypatch,
        {
            frame_0: blank_frame(),
            frame_1: frame_with([(1, 1), (1, 2), (2, 1), (2, 2)]),
        },
    )
    live_frame_cache.store_latest_frame(STREAM_ID, frame_0, captured_at=captured_at)
    live_frame_cache.store_latest_frame(
        STREAM_ID,
        frame_1,
        captured_at=captured_at + timedelta(seconds=1),
    )
    before = await product_counts(client)

    response = await client.post(
        f"/api/streams/{STREAM_ID}/live-motion/evaluate",
        json={
            "save_best_frame": True,
            "create_review_activity": False,
            "min_changed_ratio": 0.1,
            "min_triggered_frames": 1,
        },
    )

    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "activity_detected"
    assert result["activity_detected"] is True
    assert result["evaluated_at"]
    assert result["frames_available"] == 2
    assert result["frames_considered"] == 2
    assert result["recent_frame_count"] == 2
    assert result["newest_frame_sequence"] == 2
    assert result["fresh_enough"] is True
    assert result["best_frame_sequence"] == 2
    assert result["best_media_asset_id"].startswith("media-asset-")
    assert result["can_create_review_activity"] is True
    assert result["review_activity_available"] is True
    assert result["review_activity_created"] is False
    assert result["created_evidence"] == []
    assert result["creates_event"] is False
    assert result["creates_visit"] is False
    assert result["creates_truth"] is False
    assert result["creates_export"] is False
    assert result["strongest_zone_id"] == "zone-feeder"
    assert result["strongest_zone_name"] == "Feeder"
    assert result["strongest_zone_type"] == "feeder"
    assert result["pixel_delta_threshold"] == 25.0
    assert result["min_changed_ratio"] == 0.1
    assert result["strongest_zone_min_changed_ratio"] == 0.05
    assert result["threshold_used"] == 0.05
    assert result["changed_pixels"] == 4
    assert result["total_pixels"] == 6
    assert result["mean_delta"] == 170.0
    assert result["frame_pair_sequences"] == [1, 2]
    assert result["feeder_threshold_applied"] is True
    assert result["focus_applied"] is False
    assert result["strongest_frame_start_sequence"] == 1
    assert result["strongest_frame_end_sequence"] == 2
    assert result["activity_summary"] == "Activity detected in Feeder."
    assert result["session_status"] == "activity_detected"
    assert result["last_evaluation_message"] == result["message"]
    assert result["suppressed_zone_summaries"] == []

    media_response = await client.get(f"/api/media/{result['best_media_asset_id']}")
    assert media_response.status_code == 200
    media_asset = media_response.json()
    assert media_asset["source_id"] == SOURCE_ID
    assert media_asset["stream_id"] == STREAM_ID
    assert media_asset["content_type"] == "image/jpeg"
    assert "Saved best live motion frame from active stream." in media_asset["notes"]
    assert "Creates no Events, Visits, ReviewLabels, exports, or truth." in media_asset["notes"]
    saved_path = Path(media_asset["local_path"]).resolve()
    assert saved_path.is_relative_to(isolated_repository.media_root.resolve())
    assert saved_path.read_bytes() == frame_1

    after = await product_counts(client)
    assert after["media_assets"] == before["media_assets"] + 1
    for key in before:
        if key != "media_assets":
            assert after[key] == before[key]


async def test_live_motion_evaluation_uses_backend_session_frames_without_browser_request(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    frame_0 = b"\xff\xd8session-motion-0\xff\xd9"
    frame_1 = b"\xff\xd8session-motion-1\xff\xd9"
    fake_process = FakeFfmpegProcess([frame_0, frame_1])

    monkeypatch.setattr(
        "mockingbird.playback.local_camera_bridge.is_ffmpeg_available",
        lambda: True,
    )
    monkeypatch.setattr(
        "mockingbird.api.main.local_camera_bridge.start_local_camera_mjpeg_process",
        lambda device, **kwargs: fake_process,
    )
    patch_live_motion_decoder(
        monkeypatch,
        {
            frame_0: blank_frame(),
            frame_1: frame_with([(1, 1), (1, 2), (2, 1), (2, 2)]),
        },
    )
    await configure_local_usb_camera(client, device="/dev/video0")
    start_response = await client.post(f"/api/streams/{STREAM_ID}/live-session/start")
    assert start_response.status_code == 200
    session_status = await wait_for_live_session_frame_count(client, STREAM_ID, minimum=2)
    assert session_status["status"] == "running"

    def fail_if_started(*args: object, **kwargs: object) -> object:
        raise AssertionError("Live motion evaluation must not start another camera process")

    monkeypatch.setattr(
        "mockingbird.api.main.local_camera_bridge.start_local_camera_mjpeg_process",
        fail_if_started,
    )
    monkeypatch.setattr(
        "mockingbird.api.main.local_camera_bridge.capture_local_camera_frame",
        fail_if_started,
    )
    before = await product_counts(client)

    response = await client.post(
        f"/api/streams/{STREAM_ID}/live-motion/evaluate",
        json={
            "save_best_frame": False,
            "create_review_activity": False,
            "min_changed_ratio": 0.1,
            "min_triggered_frames": 1,
        },
    )

    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "activity_detected"
    assert result["session_status"] == "activity_detected"
    assert result["activity_detected"] is True
    assert result["frames_available"] == 2
    assert result["frames_considered"] == 2
    assert result["camera_session_status"] == "running"
    assert result["camera_session_frame_count"] >= 2
    assert result["camera_session_latest_frame_age_ms"] >= 0
    assert result["camera_session_runtime_limit_seconds"] >= 1
    assert result["best_media_asset_id"] is None
    assert result["review_activity_created"] is False
    assert result["creates_event"] is False
    assert result["creates_visit"] is False
    assert result["creates_truth"] is False
    assert result["creates_export"] is False
    assert result["strongest_zone_id"] == "zone-feeder"
    assert result["activity_summary"] == "Activity detected in Feeder."
    assert await product_counts(client) == before


async def test_live_motion_evaluation_uses_strongest_recent_frame_pair(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    frames = [
        b"\xff\xd8live-middle-pair-0\xff\xd9",
        b"\xff\xd8live-middle-pair-1\xff\xd9",
        b"\xff\xd8live-middle-pair-2\xff\xd9",
        b"\xff\xd8live-middle-pair-3\xff\xd9",
    ]
    captured_at = datetime.now(UTC)
    patch_camera_processes_to_fail(monkeypatch)
    patch_live_motion_decoder(
        monkeypatch,
        {
            frames[0]: blank_frame(),
            frames[1]: blank_frame(),
            frames[2]: frame_with([(1, 1), (1, 2), (2, 1), (2, 2)]),
            frames[3]: frame_with([(1, 1), (1, 2), (2, 1), (2, 2)]),
        },
    )
    for index, frame in enumerate(frames):
        live_frame_cache.store_latest_frame(
            STREAM_ID,
            frame,
            captured_at=captured_at + timedelta(seconds=index),
        )
    before = await product_counts(client)

    response = await client.post(
        f"/api/streams/{STREAM_ID}/live-motion/evaluate",
        json={
            "save_best_frame": False,
            "create_review_activity": False,
            "min_changed_ratio": 0.1,
            "min_triggered_frames": 1,
        },
    )

    assert response.status_code == 200
    result = response.json()
    assert result["activity_detected"] is True
    assert result["frames_considered"] == 4
    assert len(result["frame_scores"]) == 3
    assert result["strongest_zone_id"] == "zone-feeder"
    assert result["strongest_frame_start_sequence"] == 2
    assert result["strongest_frame_end_sequence"] == 3
    assert result["best_frame_sequence"] == 3
    assert result["candidates"][0]["best_frame_index"] == 3
    assert result["best_media_asset_id"] is None
    assert result["review_activity_created"] is False
    assert result["creates_truth"] is False
    assert await product_counts(client) == before


async def test_live_motion_decodes_live_frames_at_fine_motion_resolution(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    frame_0 = b"\xff\xd8live-fine-resolution-0\xff\xd9"
    frame_1 = b"\xff\xd8live-fine-resolution-1\xff\xd9"
    captured_at = datetime.now(UTC)
    requested_max_dimensions: list[int] = []
    patch_camera_processes_to_fail(monkeypatch)

    def fake_load_image_frame_plane_bytes(
        frame_bytes: bytes,
        *,
        content_type: str,
        max_dimension: int = 32,
    ) -> SavedMediaFrame:
        requested_max_dimensions.append(max_dimension)
        assert frame_bytes in {frame_0, frame_1}
        return SavedMediaFrame(width=64, height=64, frame=blank_frame(width=64, height=64))

    monkeypatch.setattr(
        "mockingbird.api.main.load_image_frame_plane_bytes",
        fake_load_image_frame_plane_bytes,
    )
    live_frame_cache.store_latest_frame(STREAM_ID, frame_0, captured_at=captured_at)
    live_frame_cache.store_latest_frame(
        STREAM_ID,
        frame_1,
        captured_at=captured_at + timedelta(seconds=1),
    )

    response = await client.post(
        f"/api/streams/{STREAM_ID}/live-motion/evaluate",
        json={
            "save_best_frame": False,
            "create_review_activity": False,
            "min_changed_ratio": 0.003,
            "pixel_delta_threshold": 10,
            "min_triggered_frames": 1,
        },
    )

    assert response.status_code == 200
    assert requested_max_dimensions == [64, 64]


async def test_live_motion_high_sensitivity_detects_smaller_feeder_motion_than_normal(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    frame_0 = b"\xff\xd8live-small-feeder-0\xff\xd9"
    frame_1 = b"\xff\xd8live-small-feeder-1\xff\xd9"
    captured_at = datetime.now(UTC)
    patch_camera_processes_to_fail(monkeypatch)
    patch_live_motion_decoder(
        monkeypatch,
        {
            frame_0: blank_frame(width=100, height=100),
            frame_1: frame_with(
                [(30, 40), (30, 41), (31, 40), (31, 41)],
                width=100,
                height=100,
            ),
        },
    )
    live_frame_cache.store_latest_frame(STREAM_ID, frame_0, captured_at=captured_at)
    live_frame_cache.store_latest_frame(
        STREAM_ID,
        frame_1,
        captured_at=captured_at + timedelta(seconds=1),
    )
    before = await product_counts(client)

    normal_response = await client.post(
        f"/api/streams/{STREAM_ID}/live-motion/evaluate",
        json={
            "save_best_frame": False,
            "create_review_activity": False,
            "min_changed_ratio": 0.012,
            "pixel_delta_threshold": 18,
            "min_triggered_frames": 1,
        },
    )

    assert normal_response.status_code == 200
    normal = normal_response.json()
    assert normal["activity_detected"] is False
    assert normal["strongest_zone_name"] == "Feeder"
    assert normal["strongest_changed_ratio"] > 0
    assert normal["strongest_zone_min_changed_ratio"] == 0.006
    assert normal["requested_threshold"] == 0.012
    assert normal["effective_threshold_used"] == 0.006
    assert normal["threshold_source"] == "feeder_fine"
    assert normal["fine_motion_applied"] is True
    assert normal["changed_pixels"] == 4
    assert normal["total_scored_pixels"] == 924
    assert normal["near_miss"] is True
    assert normal["margin_to_threshold"] < 0
    assert "Near miss in Feeder" in normal["message"]
    assert normal["strongest_frame_start_sequence"] is None
    assert normal["strongest_frame_end_sequence"] is None
    assert normal["best_media_asset_id"] is None

    high_response = await client.post(
        f"/api/streams/{STREAM_ID}/live-motion/evaluate",
        json={
            "save_best_frame": False,
            "create_review_activity": False,
            "min_changed_ratio": 0.003,
            "pixel_delta_threshold": 10,
            "min_triggered_frames": 1,
        },
    )

    assert high_response.status_code == 200
    high = high_response.json()
    assert high["activity_detected"] is True
    assert high["strongest_zone_name"] == "Feeder"
    assert high["strongest_zone_type"] == "feeder"
    assert high["strongest_zone_min_changed_ratio"] == pytest.approx(0.001)
    assert high["requested_threshold"] == 0.003
    assert high["effective_threshold_used"] == pytest.approx(0.001)
    assert high["threshold_used"] == pytest.approx(0.001)
    assert high["threshold_source"] == "high_feeder_fine"
    assert high["fine_motion_applied"] is True
    assert high["changed_pixels"] == 4
    assert high["total_scored_pixels"] == 924
    assert high["near_miss"] is False
    assert high["margin_to_threshold"] > 0
    assert "Small feeder motion detected" in high["message"]
    assert high["strongest_frame_start_sequence"] == 1
    assert high["strongest_frame_end_sequence"] == 2
    assert high["best_frame_sequence"] == 2
    assert high["best_media_asset_id"] is None
    assert high["review_activity_created"] is False
    assert high["creates_truth"] is False
    assert await product_counts(client) == before


async def test_live_motion_does_not_broaden_small_yard_motion_thresholds(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    frame_0 = b"\xff\xd8live-small-ground-0\xff\xd9"
    frame_1 = b"\xff\xd8live-small-ground-1\xff\xd9"
    captured_at = datetime.now(UTC)
    patch_camera_processes_to_fail(monkeypatch)
    patch_live_motion_decoder(
        monkeypatch,
        {
            frame_0: blank_frame(width=100, height=100),
            frame_1: frame_with(
                [(70, 20), (70, 21), (71, 20), (71, 21)],
                width=100,
                height=100,
            ),
        },
    )
    live_frame_cache.store_latest_frame(STREAM_ID, frame_0, captured_at=captured_at)
    live_frame_cache.store_latest_frame(
        STREAM_ID,
        frame_1,
        captured_at=captured_at + timedelta(seconds=1),
    )
    before = await product_counts(client)

    normal_response = await client.post(
        f"/api/streams/{STREAM_ID}/live-motion/evaluate",
        json={
            "save_best_frame": False,
            "create_review_activity": False,
            "min_changed_ratio": 0.012,
            "pixel_delta_threshold": 18,
            "min_triggered_frames": 1,
        },
    )
    high_response = await client.post(
        f"/api/streams/{STREAM_ID}/live-motion/evaluate",
        json={
            "save_best_frame": False,
            "create_review_activity": False,
            "min_changed_ratio": 0.003,
            "pixel_delta_threshold": 10,
            "min_triggered_frames": 1,
        },
    )

    assert normal_response.status_code == 200
    normal = normal_response.json()
    assert normal["activity_detected"] is False
    assert normal["strongest_zone_name"] == "Ground below feeder"
    assert normal["strongest_zone_type"] == "ground"
    assert normal["threshold_source"] == "requested"
    assert normal["fine_motion_applied"] is False
    assert normal["effective_threshold_used"] == 0.012
    assert normal["changed_pixels"] == 4
    assert normal["total_scored_pixels"] == 2736

    assert high_response.status_code == 200
    high = high_response.json()
    assert high["activity_detected"] is False
    assert high["strongest_zone_name"] == "Ground below feeder"
    assert high["strongest_zone_type"] == "ground"
    assert high["threshold_source"] == "requested"
    assert high["fine_motion_applied"] is False
    assert high["effective_threshold_used"] == 0.003
    assert high["effective_threshold_used"] > 0.001
    assert await product_counts(client) == before


async def test_live_motion_focus_zone_limits_scoring_region(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    frame_0 = b"\xff\xd8live-focus-zone-0\xff\xd9"
    frame_1 = b"\xff\xd8live-focus-zone-1\xff\xd9"
    captured_at = datetime.now(UTC)
    patch_camera_processes_to_fail(monkeypatch)
    patch_live_motion_decoder(
        monkeypatch,
        {
            frame_0: blank_frame(),
            frame_1: frame_with([(3, 1), (3, 2), (3, 3)]),
        },
    )
    live_frame_cache.store_latest_frame(STREAM_ID, frame_0, captured_at=captured_at)
    live_frame_cache.store_latest_frame(
        STREAM_ID,
        frame_1,
        captured_at=captured_at + timedelta(seconds=1),
    )
    before = await product_counts(client)

    unfocused_response = await client.post(
        f"/api/streams/{STREAM_ID}/live-motion/evaluate",
        json={
            "save_best_frame": False,
            "create_review_activity": False,
            "min_changed_ratio": 0.1,
            "min_triggered_frames": 1,
        },
    )
    assert unfocused_response.status_code == 200
    unfocused = unfocused_response.json()
    assert unfocused["activity_detected"] is True
    assert unfocused["strongest_zone_id"] == "zone-ground"
    assert unfocused["focus_applied"] is False

    focused_response = await client.post(
        f"/api/streams/{STREAM_ID}/live-motion/evaluate",
        json={
            "save_best_frame": False,
            "create_review_activity": False,
            "min_changed_ratio": 0.1,
            "min_triggered_frames": 1,
            "focus_zone_id": "zone-feeder",
        },
    )
    assert focused_response.status_code == 200
    focused = focused_response.json()
    assert focused["activity_detected"] is False
    assert focused["focus_applied"] is True
    assert focused["focus_zone_id"] == "zone-feeder"
    assert focused["focus_zone_name"] == "Feeder"
    assert focused["strongest_zone_id"] == "zone-feeder"
    assert focused["threshold_used"] == 0.025
    assert focused["creates_truth"] is False
    assert await product_counts(client) == before


async def test_live_motion_reports_simple_image_quality_warnings(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    frame_0 = b"\xff\xd8live-overexposed-0\xff\xd9"
    frame_1 = b"\xff\xd8live-overexposed-1\xff\xd9"
    captured_at = datetime.now(UTC)
    overexposed_frame = [[250 for _x in range(8)] for _y in range(8)]
    patch_camera_processes_to_fail(monkeypatch)
    patch_live_motion_decoder(
        monkeypatch,
        {
            frame_0: overexposed_frame,
            frame_1: overexposed_frame,
        },
    )
    live_frame_cache.store_latest_frame(STREAM_ID, frame_0, captured_at=captured_at)
    live_frame_cache.store_latest_frame(
        STREAM_ID,
        frame_1,
        captured_at=captured_at + timedelta(seconds=1),
    )
    before = await product_counts(client)

    response = await client.post(
        f"/api/streams/{STREAM_ID}/live-motion/evaluate",
        json={
            "save_best_frame": False,
            "create_review_activity": False,
            "min_changed_ratio": 0.1,
            "min_triggered_frames": 1,
        },
    )

    assert response.status_code == 200
    result = response.json()
    assert result["activity_detected"] is False
    assert any("overexposed" in warning for warning in result["image_quality_warnings"])
    assert any("low contrast" in warning for warning in result["image_quality_warnings"])
    assert result["image_quality_warnings"][0] in result["warnings"]
    assert result["creates_truth"] is False
    assert await product_counts(client) == before


async def test_live_motion_review_handoff_creates_needs_review_candidate(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    frame_0 = b"\xff\xd8live-review-0\xff\xd9"
    frame_1 = b"\xff\xd8live-review-1\xff\xd9"
    captured_at = datetime.now(UTC)
    patch_camera_processes_to_fail(monkeypatch)
    patch_live_motion_decoder(
        monkeypatch,
        {
            frame_0: blank_frame(),
            frame_1: frame_with([(1, 1), (1, 2), (2, 1), (2, 2)]),
        },
    )
    live_frame_cache.store_latest_frame(STREAM_ID, frame_0, captured_at=captured_at)
    live_frame_cache.store_latest_frame(
        STREAM_ID,
        frame_1,
        captured_at=captured_at + timedelta(seconds=1),
    )
    before = await product_counts(client)
    before_coverage = await dataset_coverage(client)
    before_queue = (await client.get("/api/review-queue")).json()

    response = await client.post(
        f"/api/streams/{STREAM_ID}/live-motion/evaluate",
        json={
            "save_best_frame": True,
            "create_review_activity": True,
            "min_changed_ratio": 0.1,
            "min_triggered_frames": 1,
        },
    )

    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "activity_detected"
    assert result["activity_detected"] is True
    assert result["session_status"] == "activity_detected"
    assert result["review_activity_created"] is True
    assert result["review_activity_reused"] is False
    assert result["review_activity_already_exists"] is False
    assert result["review_activity_available"] is False
    assert result["motion_evidence_id"].startswith("motion-evidence-")
    assert result["event_id"].startswith("event-motion-")
    assert result["visit_id"].startswith("visit-motion-")
    assert result["review_queue_item_id"] == f"review-queue-{result['visit_id']}"
    assert result["review_status"] == "needs_review"
    assert result["suggested_label"] == "unknown_bird"
    assert result["suggestion_id"].startswith("species-suggestion-")
    assert result["suggestion_confidence"] == 0.30
    assert "Low-confidence live motion suggestion from Feeder Zone context" in (
        result["suggestion_reason"]
    )
    assert result["suggestion_creates_truth"] is False
    assert result["creates_event"] is True
    assert result["creates_visit"] is True
    assert result["creates_truth"] is False
    assert result["creates_export"] is False
    assert result["strongest_zone_name"] == "Feeder"
    assert result["strongest_zone_type"] == "feeder"
    assert result["pixel_delta_threshold"] == 25.0
    assert result["min_changed_ratio"] == 0.1
    assert result["strongest_zone_min_changed_ratio"] == 0.05
    assert result["strongest_frame_start_sequence"] == 1
    assert result["strongest_frame_end_sequence"] == 2
    assert result["activity_summary"] == "Activity detected in Feeder."
    assert "Review activity created for Feeder" in result["message"]
    assert len(result["created_evidence"]) == 1
    evidence = result["created_evidence"][0]
    assert evidence["id"] == result["motion_evidence_id"]
    assert evidence["status"] == "promoted"
    assert evidence["zone_id"] == "zone-feeder"
    assert evidence["snapshot_media_asset_id"] == result["best_media_asset_id"]
    assert evidence["promoted_event_id"] == result["event_id"]
    assert evidence["promoted_visit_id"] == result["visit_id"]

    queue_response = await client.get("/api/review-queue")
    assert queue_response.status_code == 200
    queue = queue_response.json()
    assert len(queue) == len(before_queue) + 1
    queue_item = next(item for item in queue if item["id"] == result["review_queue_item_id"])
    assert queue_item["item_type"] == "visit"
    assert queue_item["stream_id"] == STREAM_ID
    assert queue_item["event_id"] == result["event_id"]
    assert queue_item["visit_id"] == result["visit_id"]
    assert queue_item["primary_zone_id"] == "zone-feeder"
    assert queue_item["primary_zone_name"] == "Feeder"
    assert queue_item["primary_zone_type"] == "feeder"
    assert queue_item["suggested_label"] == "unknown_bird"
    assert queue_item["suggestion_id"] == result["suggestion_id"]
    assert queue_item["suggestion_confidence"] == 0.30
    assert "Confirm or correct in Review Queue" in queue_item["suggestion_reason"]
    assert queue_item["suggestion_creates_truth"] is False
    assert queue_item["review_status"] == "needs_review"
    assert queue_item["media_asset"]["id"] == result["best_media_asset_id"]

    suggestions_response = await client.get(
        "/api/species-suggestions",
        params={"visit_id": result["visit_id"]},
    )
    assert suggestions_response.status_code == 200
    suggestions = suggestions_response.json()["species_suggestions"]
    assert len(suggestions) == 1
    suggestion = suggestions[0]
    assert suggestion["id"] == result["suggestion_id"]
    assert suggestion["suggested_label"] == "unknown_bird"
    assert suggestion["confidence"] == 0.30
    assert suggestion["status"] == "pending"
    assert suggestion["media_asset_id"] == result["best_media_asset_id"]
    assert suggestion["motion_evidence_id"] == result["motion_evidence_id"]

    event_detail_response = await client.get(f"/api/events/{result['event_id']}/detail")
    assert event_detail_response.status_code == 200
    event_detail = event_detail_response.json()
    assert event_detail["event"]["title"] == "Live motion activity in Feeder"
    assert event_detail["primary_zone"]["name"] == "Feeder"
    assert event_detail["primary_zone"]["zone_type"] == "feeder"

    visit_detail_response = await client.get(f"/api/visits/{result['visit_id']}/detail")
    assert visit_detail_response.status_code == 200
    visit_detail = visit_detail_response.json()
    assert visit_detail["visit"]["subject_label"] == "unknown_bird"
    assert visit_detail["visit"]["confidence"] is None
    assert visit_detail["visit"]["reviewed_label"] is None
    assert visit_detail["visit"]["review_status"] == "needs_review"
    assert visit_detail["media_asset"]["id"] == result["best_media_asset_id"]

    after = await product_counts(client)
    assert after["media_assets"] == before["media_assets"] + 1
    assert after["motion_evidence"] == before["motion_evidence"] + 1
    assert after["events"] == before["events"] + 1
    assert after["visits"] == before["visits"] + 1
    assert after["species_suggestions"] == before["species_suggestions"] + 1
    assert after["review_labels"] == before["review_labels"]
    assert after["dataset_exports"] == before["dataset_exports"]
    after_coverage = await dataset_coverage(client)
    assert after_coverage["reviewed_record_count"] == before_coverage["reviewed_record_count"]

    correction_response = await client.post(
        "/api/review-labels",
        json={
            "target_type": "visit",
            "target_id": result["visit_id"],
            "label": "northern_cardinal",
            "notes": "Confirmed live motion review candidate.",
        },
    )

    assert correction_response.status_code == 201
    correction = correction_response.json()
    assert correction["review_label"]["target_id"] == result["visit_id"]
    assert correction["visit"]["review_status"] == "reviewed"
    assert correction["visit"]["reviewed_label"] == "northern_cardinal"
    corrected_visit_detail_response = await client.get(f"/api/visits/{result['visit_id']}/detail")
    assert corrected_visit_detail_response.status_code == 200
    corrected_visit_detail = corrected_visit_detail_response.json()
    assert corrected_visit_detail["primary_zone"]["name"] == "Feeder"
    assert corrected_visit_detail["primary_zone"]["zone_type"] == "feeder"
    assert corrected_visit_detail["media_asset"]["id"] == result["best_media_asset_id"]
    corrected_counts = await product_counts(client)
    assert corrected_counts["review_labels"] == after["review_labels"] + 1
    assert corrected_counts["species_suggestions"] == after["species_suggestions"]
    corrected_coverage = await dataset_coverage(client)
    assert (
        corrected_coverage["reviewed_record_count"]
        == before_coverage["reviewed_record_count"] + 1
    )
    corrected_queue = (await client.get("/api/review-queue")).json()
    assert all(item["id"] != result["review_queue_item_id"] for item in corrected_queue)


async def test_live_motion_review_handoff_suggests_unknown_animal_for_ground_zone(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    frame_0 = b"\xff\xd8live-ground-review-0\xff\xd9"
    frame_1 = b"\xff\xd8live-ground-review-1\xff\xd9"
    captured_at = datetime.now(UTC)
    patch_camera_processes_to_fail(monkeypatch)
    patch_live_motion_decoder(
        monkeypatch,
        {
            frame_0: blank_frame(),
            frame_1: frame_with([(3, 1), (3, 2)]),
        },
    )
    live_frame_cache.store_latest_frame(STREAM_ID, frame_0, captured_at=captured_at)
    live_frame_cache.store_latest_frame(
        STREAM_ID,
        frame_1,
        captured_at=captured_at + timedelta(seconds=1),
    )
    before = await product_counts(client)

    response = await client.post(
        f"/api/streams/{STREAM_ID}/live-motion/evaluate",
        json={
            "save_best_frame": True,
            "create_review_activity": True,
            "min_changed_ratio": 0.1,
            "min_triggered_frames": 1,
        },
    )

    assert response.status_code == 200
    result = response.json()
    assert result["review_activity_created"] is True
    assert result["strongest_zone_name"] == "Ground below feeder"
    assert result["strongest_zone_type"] == "ground"
    assert result["suggested_label"] == "unknown_animal"
    assert result["suggestion_confidence"] == 0.25
    assert result["suggestion_creates_truth"] is False

    queue = (await client.get("/api/review-queue")).json()
    queue_item = next(item for item in queue if item["id"] == result["review_queue_item_id"])
    assert queue_item["primary_zone_type"] == "ground"
    assert queue_item["suggested_label"] == "unknown_animal"
    assert queue_item["suggestion_id"] == result["suggestion_id"]
    assert queue_item["suggestion_confidence"] == 0.25
    assert queue_item["suggestion_creates_truth"] is False

    after = await product_counts(client)
    assert after["species_suggestions"] == before["species_suggestions"] + 1
    assert after["review_labels"] == before["review_labels"]
    assert after["dataset_exports"] == before["dataset_exports"]


async def test_live_motion_reports_ignored_zone_without_review_activity(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    frame_0 = b"\xff\xd8live-ignore-0\xff\xd9"
    frame_1 = b"\xff\xd8live-ignore-1\xff\xd9"
    captured_at = datetime.now(UTC)
    patch_camera_processes_to_fail(monkeypatch)
    patch_live_motion_decoder(
        monkeypatch,
        {
            frame_0: blank_frame(),
            frame_1: frame_with([(0, 0)]),
        },
    )
    live_frame_cache.store_latest_frame(STREAM_ID, frame_0, captured_at=captured_at)
    live_frame_cache.store_latest_frame(
        STREAM_ID,
        frame_1,
        captured_at=captured_at + timedelta(seconds=1),
    )
    before = await product_counts(client)

    response = await client.post(
        f"/api/streams/{STREAM_ID}/live-motion/evaluate",
        json={
            "save_best_frame": True,
            "create_review_activity": True,
            "min_changed_ratio": 0.1,
            "min_triggered_frames": 1,
        },
    )

    assert response.status_code == 200
    result = response.json()
    assert result["activity_detected"] is False
    assert result["status"] == "no_activity"
    assert result["review_activity_created"] is False
    assert result["review_activity_available"] is False
    assert result["best_media_asset_id"] is None
    assert result["motion_evidence_id"] is None
    assert result["event_id"] is None
    assert result["visit_id"] is None
    assert result["suggestion_id"] is None
    assert result["suggested_label"] is None
    assert result["suggestion_confidence"] is None
    assert result["suggestion_creates_truth"] is False
    assert result["creates_event"] is False
    assert result["creates_visit"] is False
    assert result["creates_truth"] is False
    assert result["creates_export"] is False
    assert result["activity_summary"] == "Motion ignored in Driveway edge ignore zone."
    assert result["message"] == "Motion ignored in Driveway edge ignore zone."
    assert len(result["suppressed_zone_summaries"]) == 1
    suppressed = result["suppressed_zone_summaries"][0]
    assert suppressed["zone_id"] == "zone-ignore-driveway-edge"
    assert suppressed["zone_name"] == "Driveway edge ignore zone"
    assert suppressed["zone_type"] == "ignore"
    assert suppressed["reason"] == "ignore_zone"
    assert await product_counts(client) == before


async def test_live_motion_review_handoff_reuses_existing_review_candidate(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    frame_0 = b"\xff\xd8live-review-duplicate-0\xff\xd9"
    frame_1 = b"\xff\xd8live-review-duplicate-1\xff\xd9"
    captured_at = datetime.now(UTC)
    patch_camera_processes_to_fail(monkeypatch)
    patch_live_motion_decoder(
        monkeypatch,
        {
            frame_0: blank_frame(),
            frame_1: frame_with([(1, 1), (1, 2), (2, 1), (2, 2)]),
        },
    )
    live_frame_cache.store_latest_frame(STREAM_ID, frame_0, captured_at=captured_at)
    live_frame_cache.store_latest_frame(
        STREAM_ID,
        frame_1,
        captured_at=captured_at + timedelta(seconds=1),
    )

    first_response = await client.post(
        f"/api/streams/{STREAM_ID}/live-motion/evaluate",
        json={
            "save_best_frame": True,
            "create_review_activity": True,
            "min_changed_ratio": 0.1,
            "min_triggered_frames": 1,
        },
    )
    assert first_response.status_code == 200
    first = first_response.json()
    after_first = await product_counts(client)
    queue_after_first = (await client.get("/api/review-queue")).json()

    duplicate_response = await client.post(
        f"/api/streams/{STREAM_ID}/live-motion/evaluate",
        json={
            "save_best_frame": True,
            "create_review_activity": True,
            "min_changed_ratio": 0.1,
            "min_triggered_frames": 1,
        },
    )

    assert duplicate_response.status_code == 200
    duplicate = duplicate_response.json()
    assert duplicate["review_activity_created"] is False
    assert duplicate["review_activity_reused"] is True
    assert duplicate["review_activity_already_exists"] is True
    assert duplicate["session_status"] == "cooldown"
    assert duplicate["existing_review_activity_reference"] == first["motion_evidence_id"]
    assert duplicate["cooldown_remaining_seconds"] is not None
    assert duplicate["best_media_asset_id"] is None
    assert duplicate["motion_evidence_id"] == first["motion_evidence_id"]
    assert duplicate["event_id"] == first["event_id"]
    assert duplicate["visit_id"] == first["visit_id"]
    assert duplicate["review_queue_item_id"] == first["review_queue_item_id"]
    assert duplicate["suggestion_id"] == first["suggestion_id"]
    assert duplicate["suggested_label"] == first["suggested_label"]
    assert duplicate["suggestion_confidence"] == first["suggestion_confidence"]
    assert duplicate["suggestion_creates_truth"] is False

    after_duplicate = await product_counts(client)
    assert after_duplicate["motion_evidence"] == after_first["motion_evidence"]
    assert after_duplicate["media_assets"] == after_first["media_assets"]
    assert after_duplicate["events"] == after_first["events"]
    assert after_duplicate["visits"] == after_first["visits"]
    assert after_duplicate["species_suggestions"] == after_first["species_suggestions"]
    assert after_duplicate["review_labels"] == after_first["review_labels"]
    queue_after_duplicate = (await client.get("/api/review-queue")).json()
    assert queue_after_duplicate == queue_after_first


async def test_external_url_without_live_stream_reports_needs_stream_url(
    client: httpx.AsyncClient,
) -> None:
    update_response = await client.patch(
        f"/api/sources/{SOURCE_ID}/provider-configuration",
        json={
            "provider_key": "external_url",
            "config": {"url": "http://camera.local/still.jpg"},
        },
    )
    assert update_response.status_code == 200

    response = await client.get(f"/api/streams/{STREAM_ID}/playback")

    assert response.status_code == 200
    playback = response.json()
    assert playback["status"] == "needs_stream_url"
    assert playback["playback_kind"] == "external_url"
    assert playback["message"] == "No live stream URL configured."
    assert playback["supports_live_playback"] is False
    assert playback["preview_url"] is None
    assert playback["live_stream_type"] == "unknown"
    assert playback["live_stream_url_display"] is None


async def test_external_url_mjpeg_live_stream_reports_browser_ready_and_redacts_display(
    client: httpx.AsyncClient,
) -> None:
    live_url = "http://viewer:secret@camera.local/live.mjpg"
    await configure_external_url_live_stream(
        client,
        live_stream_url=live_url,
        live_stream_type="mjpeg",
    )

    configuration_response = await client.get(f"/api/sources/{SOURCE_ID}/provider-configuration")
    assert configuration_response.status_code == 200
    configuration = configuration_response.json()
    assert configuration["supports_live_playback"] is True
    assert configuration["safe_config_preview"]["live_stream_url"] == (
        "http://***:***@camera.local/live.mjpg"
    )
    assert "secret" not in str(configuration)

    response = await client.get(f"/api/streams/{STREAM_ID}/playback")

    assert response.status_code == 200
    playback = response.json()
    assert playback["status"] == "live_ready"
    assert playback["playback_kind"] == "mjpeg"
    assert playback["supports_live_playback"] is True
    assert playback["preview_url"] == live_url
    assert playback["live_stream_type"] == "mjpeg"
    assert playback["live_stream_url_display"] == "http://***:***@camera.local/live.mjpg"
    assert "secret" not in playback["live_stream_url_display"]


async def test_external_url_rtsp_live_stream_reports_bridge_required(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "mockingbird.repository.product_repository.rtsp_bridge.is_ffmpeg_available",
        lambda: False,
    )
    await configure_external_url_live_stream(
        client,
        live_stream_url="rtsp://camera.local/live",
        live_stream_type="rtsp",
    )

    response = await client.get(f"/api/streams/{STREAM_ID}/playback")

    assert response.status_code == 200
    playback = response.json()
    assert playback["status"] == "unsupported_rtsp_bridge_required"
    assert playback["playback_kind"] == "rtsp"
    assert playback["message"] == "RTSP bridge unavailable - ffmpeg not found."
    assert playback["supports_live_playback"] is False
    assert playback["preview_url"] is None
    assert playback["live_stream_type"] == "rtsp"
    assert playback["rtsp_bridge_required"] is True
    assert playback["rtsp_bridge_available"] is False
    assert playback["rtsp_bridge_status"] == "ffmpeg_missing"


async def test_external_url_rtsp_live_stream_reports_bridge_available(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "mockingbird.repository.product_repository.rtsp_bridge.is_ffmpeg_available",
        lambda: True,
    )
    await configure_external_url_live_stream(
        client,
        live_stream_url="rtsp://viewer:secret@camera.local/live",
        live_stream_type="rtsp",
    )

    response = await client.get(f"/api/streams/{STREAM_ID}/playback")

    assert response.status_code == 200
    playback = response.json()
    assert playback["status"] == "live_ready"
    assert playback["playback_kind"] == "rtsp"
    assert playback["supports_live_playback"] is True
    assert playback["preview_url"] is None
    assert playback["live_stream_type"] == "rtsp"
    assert playback["live_stream_url_display"] == "rtsp://***:***@camera.local/live"
    assert playback["rtsp_bridge_required"] is True
    assert playback["rtsp_bridge_available"] is True
    assert playback["rtsp_bridge_status"] == "available"
    assert playback["bridged_mjpeg_url"] == f"/api/streams/{STREAM_ID}/live/rtsp-mjpeg"
    assert "secret" not in playback["live_stream_url_display"]


async def test_external_url_rtsp_live_stream_rejects_invalid_rtsp_url(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "mockingbird.repository.product_repository.rtsp_bridge.is_ffmpeg_available",
        lambda: True,
    )
    await configure_external_url_live_stream(
        client,
        live_stream_url="http://camera.local/not-rtsp",
        live_stream_type="rtsp",
    )

    response = await client.get(f"/api/streams/{STREAM_ID}/playback")

    assert response.status_code == 200
    playback = response.json()
    assert playback["status"] == "unsupported_rtsp_bridge_required"
    assert playback["supports_live_playback"] is False
    assert playback["rtsp_bridge_required"] is True
    assert playback["rtsp_bridge_available"] is False
    assert playback["rtsp_bridge_status"] == "unsupported_url"
    assert playback["bridged_mjpeg_url"] is None


async def test_rtsp_bridge_endpoint_rejects_non_rtsp_stream(
    client: httpx.AsyncClient,
) -> None:
    await configure_external_url_live_stream(
        client,
        live_stream_url="http://camera.local/live.mjpg",
        live_stream_type="mjpeg",
    )

    response = await client.get(f"/api/streams/{STREAM_ID}/live/rtsp-mjpeg")

    assert response.status_code == 400
    assert response.json()["detail"] == "RTSP bridge requires RTSP stream type."


async def test_rtsp_bridge_endpoint_rejects_missing_live_stream_url(
    client: httpx.AsyncClient,
) -> None:
    update_response = await client.patch(
        f"/api/sources/{SOURCE_ID}/provider-configuration",
        json={"provider_key": "external_url", "config": {"url": "http://camera.local/still.jpg"}},
    )
    assert update_response.status_code == 200

    response = await client.get(f"/api/streams/{STREAM_ID}/live/rtsp-mjpeg")

    assert response.status_code == 400
    assert response.json()["detail"] == "Live stream URL is not configured."


async def test_rtsp_bridge_endpoint_reports_ffmpeg_missing(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "mockingbird.api.main.rtsp_bridge.is_ffmpeg_available",
        lambda: False,
    )
    await configure_external_url_live_stream(
        client,
        live_stream_url="rtsp://camera.local/live",
        live_stream_type="rtsp",
    )

    response = await client.get(f"/api/streams/{STREAM_ID}/live/rtsp-mjpeg")

    assert response.status_code == 503
    assert response.json()["detail"] == "RTSP bridge unavailable: ffmpeg not found."


async def test_rtsp_bridge_endpoint_streams_mocked_mjpeg_without_creating_truth(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    jpeg_frame = b"\xff\xd8mock-jpeg\xff\xd9"
    fake_process = object()
    started_urls: list[str] = []

    monkeypatch.setattr(
        "mockingbird.api.main.rtsp_bridge.is_ffmpeg_available",
        lambda: True,
    )
    monkeypatch.setattr(
        "mockingbird.api.main.rtsp_bridge.start_rtsp_mjpeg_process",
        lambda url: started_urls.append(url) or fake_process,
    )
    monkeypatch.setattr(
        "mockingbird.api.main.rtsp_bridge.iter_multipart_mjpeg",
        lambda process, **kwargs: iter(
            [b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpeg_frame]
        ),
    )
    await configure_external_url_live_stream(
        client,
        live_stream_url="rtsp://viewer:secret@camera.local/live",
        live_stream_type="rtsp",
    )
    before = await product_counts(client)

    response = await get_stream_rtsp_mjpeg_bridge(STREAM_ID)

    assert response.status_code == 200
    assert response.media_type.startswith("multipart/x-mixed-replace")
    assert response.background is None
    assert response.headers["content-type"].startswith("multipart/x-mixed-replace")
    assert started_urls == ["rtsp://viewer:secret@camera.local/live"]
    assert await product_counts(client) == before


async def test_playback_status_does_not_start_rtsp_bridge_process(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "mockingbird.repository.product_repository.rtsp_bridge.is_ffmpeg_available",
        lambda: True,
    )

    def fail_if_started(url: str):  # noqa: ANN202
        raise AssertionError("Playback status must not start ffmpeg")

    monkeypatch.setattr(
        "mockingbird.api.main.rtsp_bridge.start_rtsp_mjpeg_process",
        fail_if_started,
    )
    await configure_external_url_live_stream(
        client,
        live_stream_url="rtsp://camera.local/live",
        live_stream_type="rtsp",
    )

    response = await client.get(f"/api/streams/{STREAM_ID}/playback")

    assert response.status_code == 200


def test_rtsp_bridge_command_and_redaction_do_not_drop_credentials() -> None:
    url = "rtsp://viewer:secret@camera.local/live"

    command = rtsp_bridge.build_rtsp_mjpeg_command(url)

    assert command[:7] == [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-rtsp_transport",
        "tcp",
        "-i",
    ]
    assert url in command
    assert rtsp_bridge.redact_url(url) == "rtsp://***:***@camera.local/live"
    assert rtsp_bridge.validate_rtsp_url(url) is True
    assert rtsp_bridge.validate_rtsp_url("rtsps://camera.local/live") is True
    assert rtsp_bridge.validate_rtsp_url("http://camera.local/live") is False


def test_rtsp_bridge_multipart_generator_stops_process() -> None:
    fake_process = FakeFfmpegProcess([b"noise", b"\xff\xd8frame-one\xff\xd9tail"])

    chunks = list(rtsp_bridge.iter_multipart_mjpeg(fake_process))

    assert len(chunks) == 1
    assert chunks[0].startswith(b"--frame\r\nContent-Type: image/jpeg")
    assert b"\xff\xd8frame-one\xff\xd9" in chunks[0]
    assert fake_process.terminated is True
    assert fake_process.waited is True
    assert fake_process.killed is False


def test_local_camera_multipart_generator_emits_two_frames_and_stops_process() -> None:
    fake_process = FakeFfmpegProcess(
        [
            b"noise\xff\xd8frame-one\xff\xd9middle\xff\xd8frame",
            b"-two\xff\xd9tail",
        ]
    )

    chunks = list(local_camera_bridge.iter_multipart_mjpeg(fake_process))

    assert len(chunks) == 2
    assert chunks[0].startswith(b"--frame\r\nContent-Type: image/jpeg")
    assert b"Content-Length: " in chunks[0]
    assert b"\xff\xd8frame-one\xff\xd9" in chunks[0]
    assert chunks[0].endswith(b"\r\n")
    assert chunks[1].startswith(b"--frame\r\nContent-Type: image/jpeg")
    assert b"\xff\xd8frame-two\xff\xd9" in chunks[1]
    assert fake_process.terminated is True
    assert fake_process.waited is True
    assert fake_process.killed is False


def test_local_camera_multipart_generator_cleans_up_when_no_frames_arrive() -> None:
    fake_process = FakeFfmpegProcess([b"not-a-jpeg-frame"])

    chunks = list(local_camera_bridge.iter_multipart_mjpeg(fake_process))

    assert chunks == []
    assert fake_process.terminated is True
    assert fake_process.waited is True
    assert fake_process.killed is False


def test_local_camera_multipart_generator_updates_latest_frame_cache() -> None:
    fake_process = FakeFfmpegProcess([b"noise\xff\xd8local-live-frame\xff\xd9"])

    chunks = list(
        local_camera_bridge.iter_multipart_mjpeg(
            fake_process,
            on_frame=lambda frame: live_frame_cache.store_latest_frame(STREAM_ID, frame),
        )
    )

    cached = live_frame_cache.get_latest_frame(STREAM_ID)
    assert len(chunks) == 1
    assert cached is not None
    assert cached.frame_bytes == b"\xff\xd8local-live-frame\xff\xd9"


async def test_local_usb_playback_reports_not_configured_without_device(
    client: httpx.AsyncClient,
) -> None:
    await configure_local_usb_camera(client, device=None)

    response = await client.get(f"/api/streams/{STREAM_ID}/playback")

    assert response.status_code == 200
    playback = response.json()
    assert playback["status"] == "not_configured"
    assert playback["playback_kind"] == "local_usb"
    assert playback["message"] == "Choose a local camera device such as /dev/video0."
    assert playback["supports_live_playback"] is False
    assert playback["live_stream_type"] == "local_usb"
    assert playback["local_camera_status"] == "device_missing"
    assert playback["local_camera_bridge_available"] is False
    assert playback["bridged_mjpeg_url"] is None


async def test_local_usb_playback_reports_ffmpeg_missing(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "mockingbird.playback.local_camera_bridge.is_ffmpeg_available",
        lambda: False,
    )
    await configure_local_usb_camera(client, device="/dev/video0")

    response = await client.get(f"/api/streams/{STREAM_ID}/playback")

    assert response.status_code == 200
    playback = response.json()
    assert playback["status"] == "unavailable"
    assert playback["playback_kind"] == "local_usb"
    assert playback["message"] == "Local camera bridge unavailable - ffmpeg not found."
    assert playback["local_camera_status"] == "ffmpeg_missing"
    assert playback["local_camera_bridge_available"] is False
    assert playback["local_camera_device_display"] == "/dev/video0"


async def test_local_usb_playback_rejects_invalid_device_path(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "mockingbird.playback.local_camera_bridge.is_ffmpeg_available",
        lambda: True,
    )
    await configure_local_usb_camera(client, device="/tmp/not-a-camera")

    response = await client.get(f"/api/streams/{STREAM_ID}/playback")

    assert response.status_code == 200
    playback = response.json()
    assert playback["status"] == "playback_error"
    assert playback["message"] == "Local camera device path must look like /dev/video0."
    assert playback["local_camera_status"] == "invalid_device"
    assert playback["supports_live_playback"] is False


async def test_local_usb_playback_reports_bridge_available(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "mockingbird.playback.local_camera_bridge.is_ffmpeg_available",
        lambda: True,
    )
    await configure_local_usb_camera(client, device="/dev/video0")

    response = await client.get(f"/api/streams/{STREAM_ID}/playback")

    assert response.status_code == 200
    playback = response.json()
    assert playback["status"] == "live_ready"
    assert playback["playback_kind"] == "local_usb"
    assert playback["supports_live_playback"] is True
    assert playback["local_camera_status"] == "available"
    assert playback["local_camera_bridge_available"] is True
    assert playback["local_camera_device_display"] == "/dev/video0"
    assert playback["bridged_mjpeg_url"] == f"/api/streams/{STREAM_ID}/live/local-mjpeg"


async def test_local_camera_bridge_endpoint_rejects_non_local_usb_stream(
    client: httpx.AsyncClient,
) -> None:
    await configure_external_url_live_stream(
        client,
        live_stream_url="http://camera.local/live.mjpg",
        live_stream_type="mjpeg",
    )

    response = await client.get(f"/api/streams/{STREAM_ID}/live/local-mjpeg")

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "Local camera bridge requires a local_usb Source provider."
    )


async def test_local_camera_bridge_endpoint_rejects_unsafe_device_path(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "mockingbird.playback.local_camera_bridge.is_ffmpeg_available",
        lambda: True,
    )
    await configure_local_usb_camera(client, device="/home/user/webcam")

    response = await client.get(f"/api/streams/{STREAM_ID}/live/local-mjpeg")

    assert response.status_code == 400
    assert response.json()["detail"] == "Local camera device path must look like /dev/video0."


async def test_local_camera_bridge_endpoint_reports_ffmpeg_missing(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "mockingbird.playback.local_camera_bridge.is_ffmpeg_available",
        lambda: False,
    )
    await configure_local_usb_camera(client, device="/dev/video0")

    response = await client.get(f"/api/streams/{STREAM_ID}/live/local-mjpeg")

    assert response.status_code == 503
    assert response.json()["detail"] == "Local camera bridge unavailable: ffmpeg not found."


async def test_local_camera_bridge_endpoint_streams_mocked_mjpeg_without_creating_truth(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_process = object()
    started_devices: list[str] = []

    monkeypatch.setattr(
        "mockingbird.playback.local_camera_bridge.is_ffmpeg_available",
        lambda: True,
    )
    monkeypatch.setattr(
        "mockingbird.api.main.local_camera_bridge.start_local_camera_mjpeg_process",
        lambda device, **kwargs: started_devices.append(device) or fake_process,
    )
    monkeypatch.setattr(
        "mockingbird.api.main.local_camera_bridge.iter_multipart_mjpeg",
        lambda process, **kwargs: iter(
            [b"--frame\r\nContent-Type: image/jpeg\r\n\r\njpeg"]
        ),
    )
    await configure_local_usb_camera(client, device="/dev/video0")
    before = await product_counts(client)

    response = await get_stream_local_mjpeg_bridge(STREAM_ID)

    assert response.status_code == 200
    assert response.media_type == (
        f"multipart/x-mixed-replace; boundary={local_camera_bridge.MJPEG_BOUNDARY}"
    )
    assert response.headers["content-type"] == (
        f"multipart/x-mixed-replace; boundary={local_camera_bridge.MJPEG_BOUNDARY}"
    )
    assert started_devices == ["/dev/video0"]
    assert await product_counts(client) == before


async def test_live_camera_session_start_reuses_single_reader_and_reports_status(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session_frame = b"\xff\xd8session-frame-one\xff\xd9"
    fake_process = FakeFfmpegProcess([b"noise" + session_frame])
    started_devices: list[str] = []
    started_kwargs: list[dict[str, object]] = []

    monkeypatch.setattr(
        "mockingbird.playback.local_camera_bridge.is_ffmpeg_available",
        lambda: True,
    )

    def fake_start(device: str, **kwargs: object) -> FakeFfmpegProcess:
        started_devices.append(device)
        started_kwargs.append(dict(kwargs))
        return fake_process

    monkeypatch.setattr(
        "mockingbird.api.main.local_camera_bridge.start_local_camera_mjpeg_process",
        fake_start,
    )
    await configure_local_usb_camera(
        client,
        device="/dev/video0",
        preview_video_size="1280x720",
        capture_video_size="1920x1080",
        framerate="15",
        input_format="mjpeg",
        brightness="driver-app",
    )
    before = await product_counts(client)

    response = await client.post(f"/api/streams/{STREAM_ID}/live-session/start")

    assert response.status_code == 200
    started = response.json()
    assert started["stream_id"] == STREAM_ID
    assert started["source_id"] == SOURCE_ID
    assert started["playback_kind"] == "local_usb"
    assert started["status"] == "running"
    assert started["persistent"] is False
    assert started["max_runtime_seconds"] >= 1
    assert started["camera_settings"]["input_format"] == "mjpeg"
    assert started["camera_settings"]["preview_video_size"] == "1280x720"
    assert started["camera_settings"]["capture_video_size"] == "1920x1080"
    assert started["camera_settings"]["brightness"] == "driver-app"
    assert started["message"] == (
        "Camera session is running. Live view, capture, and monitoring share these frames."
    )

    status = await wait_for_live_session_frame_count(client, STREAM_ID, minimum=1)
    assert status["status"] == "running"
    assert status["frame_count"] >= 1
    assert status["last_frame_at"] is not None
    assert status["latest_frame_age_ms"] >= 0
    assert status["clients_connected"] == 0
    assert status["persistent"] is False

    duplicate_response = await client.post(f"/api/streams/{STREAM_ID}/live-session/start")

    assert duplicate_response.status_code == 200
    duplicate = duplicate_response.json()
    assert duplicate["status"] == "running"
    assert duplicate["frame_count"] >= 1
    assert started_devices == ["/dev/video0"]
    assert started_kwargs[0]["input_format"] == "mjpeg"
    assert started_kwargs[0]["video_size"] == "1280x720"
    assert started_kwargs[0]["input_frame_rate"] == "15"

    stop_response = await client.post(f"/api/streams/{STREAM_ID}/live-session/stop")

    assert stop_response.status_code == 200
    stopped = stop_response.json()
    assert stopped["status"] == "stopped"
    assert stopped["stop_reason"] == "user_stopped"
    assert fake_process.terminated is True
    assert fake_process.waited is True
    assert await product_counts(client) == before


async def test_live_camera_session_mjpeg_uses_existing_session_without_new_reader(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session_frame = b"\xff\xd8session-frame-one\xff\xd9"
    fake_process = FakeFfmpegProcess([session_frame])
    start_count = 0

    monkeypatch.setattr(
        "mockingbird.playback.local_camera_bridge.is_ffmpeg_available",
        lambda: True,
    )

    def fake_start(device: str, **kwargs: object) -> FakeFfmpegProcess:
        nonlocal start_count
        start_count += 1
        return fake_process

    monkeypatch.setattr(
        "mockingbird.api.main.local_camera_bridge.start_local_camera_mjpeg_process",
        fake_start,
    )
    await configure_local_usb_camera(client, device="/dev/video0")
    before = await product_counts(client)

    start_response = await client.post(f"/api/streams/{STREAM_ID}/live-session/start")
    assert start_response.status_code == 200
    await wait_for_live_session_frame_count(client, STREAM_ID, minimum=1)

    def fail_if_started(*args: object, **kwargs: object) -> object:
        raise AssertionError("Session MJPEG must not start another camera reader")

    monkeypatch.setattr(
        "mockingbird.api.main.local_camera_bridge.start_local_camera_mjpeg_process",
        fail_if_started,
    )

    response = await get_stream_live_camera_session_mjpeg(STREAM_ID)

    assert response.status_code == 200
    assert response.media_type == (
        f"multipart/x-mixed-replace; boundary={local_camera_bridge.MJPEG_BOUNDARY}"
    )
    stream = get_live_camera_session_manager().iter_mjpeg(STREAM_ID)
    chunk = next(stream)
    stream.close()
    assert b"Content-Type: image/jpeg" in chunk
    assert session_frame in chunk
    status = await wait_for_live_session_frame_count(client, STREAM_ID, minimum=1)
    assert status["status"] == "running"
    assert status["clients_connected"] == 0
    assert start_count == 1
    assert await product_counts(client) == before


async def test_backend_monitor_survives_hidden_live_view_until_camera_stop(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    frame_0 = b"\xff\xd8monitor-no-activity-0\xff\xd9"
    frame_1 = b"\xff\xd8monitor-no-activity-1\xff\xd9"
    fake_process = FakeFfmpegProcess([frame_0, frame_1])
    start_count = 0

    monkeypatch.setattr(
        "mockingbird.playback.local_camera_bridge.is_ffmpeg_available",
        lambda: True,
    )

    def fake_start(device: str, **kwargs: object) -> FakeFfmpegProcess:
        nonlocal start_count
        start_count += 1
        return fake_process

    monkeypatch.setattr(
        "mockingbird.api.main.local_camera_bridge.start_local_camera_mjpeg_process",
        fake_start,
    )
    patch_live_motion_decoder(
        monkeypatch,
        {
            frame_0: blank_frame(),
            frame_1: blank_frame(),
        },
    )
    await configure_local_usb_camera(client, device="/dev/video0")
    before = await product_counts(client)

    start_response = await client.post(f"/api/streams/{STREAM_ID}/live-session/start")
    assert start_response.status_code == 200
    await wait_for_live_session_frame_count(client, STREAM_ID, minimum=2)

    monitor_response = await client.post(
        f"/api/streams/{STREAM_ID}/live-motion/start",
        json={
            "save_best_frame": False,
            "create_review_activity": False,
            "min_changed_ratio": 0.1,
            "min_triggered_frames": 1,
            "interval_seconds": 10,
        },
    )

    assert monitor_response.status_code == 200
    monitor = monitor_response.json()
    assert monitor["activity_detected"] is False
    assert monitor["status"] == "no_activity"

    stream = get_live_camera_session_manager().iter_mjpeg(STREAM_ID)
    chunk = next(stream)
    stream.close()
    assert frame_1 in chunk

    status_response = await client.get(f"/api/streams/{STREAM_ID}/live-session/status")
    assert status_response.status_code == 200
    status = status_response.json()
    assert status["status"] == "running"
    assert status["clients_connected"] == 0
    assert status["monitor_running"] is True
    assert status["last_motion_result"]["status"] == "no_activity"

    stop_monitor_response = await client.post(
        f"/api/streams/{STREAM_ID}/live-motion/stop"
    )
    assert stop_monitor_response.status_code == 200
    stopped_monitor = stop_monitor_response.json()
    assert stopped_monitor["status"] == "running"
    assert stopped_monitor["monitor_running"] is False
    assert fake_process.terminated is False

    restart_monitor_response = await client.post(
        f"/api/streams/{STREAM_ID}/live-motion/start",
        json={
            "save_best_frame": False,
            "create_review_activity": False,
            "min_changed_ratio": 0.1,
            "min_triggered_frames": 1,
            "interval_seconds": 10,
        },
    )
    assert restart_monitor_response.status_code == 200
    restarted_status = (await client.get(f"/api/streams/{STREAM_ID}/live-session/status")).json()
    assert restarted_status["status"] == "running"
    assert restarted_status["monitor_running"] is True

    stop_response = await client.post(f"/api/streams/{STREAM_ID}/live-session/stop")

    assert stop_response.status_code == 200
    stopped = stop_response.json()
    assert stopped["status"] == "stopped"
    assert stopped["monitor_running"] is False
    assert stopped["stop_reason"] == "user_stopped"
    assert fake_process.terminated is True
    assert fake_process.waited is True
    assert start_count == 1
    assert await product_counts(client) == before


async def test_stored_live_activity_review_handoff_keeps_camera_running_and_truth_reviewed_only(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    frame_0 = b"\xff\xd8session-review-activity-0\xff\xd9"
    frame_1 = b"\xff\xd8session-review-activity-1\xff\xd9"
    fake_process = FakeFfmpegProcess([frame_0, frame_1])

    monkeypatch.setattr(
        "mockingbird.playback.local_camera_bridge.is_ffmpeg_available",
        lambda: True,
    )
    monkeypatch.setattr(
        "mockingbird.api.main.local_camera_bridge.start_local_camera_mjpeg_process",
        lambda device, **kwargs: fake_process,
    )
    patch_live_motion_decoder(
        monkeypatch,
        {
            frame_0: blank_frame(),
            frame_1: frame_with([(1, 1), (1, 2), (2, 1), (2, 2)]),
        },
    )
    await configure_local_usb_camera(client, device="/dev/video0")
    start_response = await client.post(f"/api/streams/{STREAM_ID}/live-session/start")
    assert start_response.status_code == 200
    await wait_for_live_session_frame_count(client, STREAM_ID, minimum=2)

    def fail_if_camera_reader_starts(*args: object, **kwargs: object) -> object:
        raise AssertionError("Monitoring/review handoff must reuse the live session frames")

    monkeypatch.setattr(
        "mockingbird.api.main.local_camera_bridge.start_local_camera_mjpeg_process",
        fail_if_camera_reader_starts,
    )
    monkeypatch.setattr(
        "mockingbird.api.main.local_camera_bridge.capture_local_camera_frame",
        fail_if_camera_reader_starts,
    )

    before = await product_counts(client)
    before_queue = (await client.get("/api/review-queue")).json()
    before_labels = (await client.get("/api/review-labels")).json()

    monitor_response = await client.post(
        f"/api/streams/{STREAM_ID}/live-motion/start",
        json={
            "save_best_frame": True,
            "create_review_activity": False,
            "min_changed_ratio": 0.1,
            "min_triggered_frames": 1,
            "interval_seconds": 10,
        },
    )

    assert monitor_response.status_code == 200
    monitor = monitor_response.json()
    assert monitor["status"] == "activity_detected"
    assert monitor["activity_detected"] is True
    assert monitor["review_activity_available"] is True
    assert monitor["review_activity_created"] is False
    assert monitor["best_media_asset_id"] is None
    assert monitor["activity_session_id"].startswith("live-activity-")
    assert monitor["activity_detection_count"] == 1
    assert monitor["activity_best_frame_sequence"] == 2
    assert monitor["strongest_zone_name"] == "Feeder"
    assert monitor["creates_truth"] is False

    status_response = await client.get(f"/api/streams/{STREAM_ID}/live-session/status")
    assert status_response.status_code == 200
    status = status_response.json()
    assert status["status"] == "running"
    assert status["monitor_running"] is True
    assert status["current_activity_session_id"] == monitor["activity_session_id"]
    assert status["activity_detection_count"] == 1
    assert status["last_activity"]["best_media_asset_id"] is None
    assert status["last_activity"]["review_activity_created"] is False
    assert status["last_motion_result"]["review_activity_available"] is True

    create_response = await client.post(
        f"/api/streams/{STREAM_ID}/live-motion/review-activity"
    )

    assert create_response.status_code == 200
    created = create_response.json()
    assert created["status"] == "created"
    assert created["activity_detected"] is True
    assert created["review_activity_created"] is True
    assert created["review_activity_reused"] is False
    assert created["review_activity_already_exists"] is False
    assert created["activity_session_id"] == monitor["activity_session_id"]
    assert created["activity_detection_count"] == 1
    assert created["media_asset_id"].startswith("media-asset-")
    assert created["motion_evidence_id"].startswith("motion-evidence-")
    assert created["event_id"].startswith("event-motion-")
    assert created["visit_id"].startswith("visit-motion-")
    assert created["review_queue_item_id"] == f"review-queue-{created['visit_id']}"
    assert created["review_status"] == "needs_review"
    assert created["suggested_label"] == "unknown_bird"
    assert created["suggestion_id"].startswith("species-suggestion-")
    assert created["suggestion_confidence"] == 0.30
    assert created["creates_event"] is True
    assert created["creates_visit"] is True
    assert created["creates_truth"] is False
    assert created["creates_export"] is False

    cached = live_frame_cache.get_latest_frame(STREAM_ID)
    assert cached is not None
    assert cached.frame_bytes == frame_1
    post_create_status = (await client.get(f"/api/streams/{STREAM_ID}/live-session/status")).json()
    assert post_create_status["status"] == "running"
    assert post_create_status["monitor_running"] is True
    assert post_create_status["frame_count"] >= 2
    assert post_create_status["last_activity"]["motion_evidence_id"] == created[
        "motion_evidence_id"
    ]
    assert post_create_status["last_motion_result"]["review_activity_created"] is True
    assert post_create_status["last_motion_result"]["review_queue_item_id"] == created[
        "review_queue_item_id"
    ]

    queue = (await client.get("/api/review-queue")).json()
    assert len(queue) == len(before_queue) + 1
    queue_item = next(item for item in queue if item["id"] == created["review_queue_item_id"])
    assert queue_item["visit_id"] == created["visit_id"]
    assert queue_item["event_id"] == created["event_id"]
    assert queue_item["primary_zone_id"] == "zone-feeder"
    assert queue_item["suggested_label"] == "unknown_bird"
    assert queue_item["media_asset"]["id"] == created["media_asset_id"]

    after_create = await product_counts(client)
    assert after_create["media_assets"] == before["media_assets"] + 1
    assert after_create["motion_evidence"] == before["motion_evidence"] + 1
    assert after_create["events"] == before["events"] + 1
    assert after_create["visits"] == before["visits"] + 1
    assert after_create["species_suggestions"] == before["species_suggestions"] + 1
    assert after_create["review_labels"] == before["review_labels"]
    assert after_create["dataset_exports"] == before["dataset_exports"]
    labels_after_create = (await client.get("/api/review-labels")).json()
    assert labels_after_create == before_labels
    assert [
        label
        for label in labels_after_create
        if label["target_type"] == "visit" and label["target_id"] == created["visit_id"]
    ] == []

    duplicate_response = await client.post(
        f"/api/streams/{STREAM_ID}/live-motion/review-activity"
    )

    assert duplicate_response.status_code == 200
    duplicate = duplicate_response.json()
    assert duplicate["status"] == "already_exists"
    assert duplicate["review_activity_created"] is False
    assert duplicate["review_activity_reused"] is True
    assert duplicate["review_activity_already_exists"] is True
    assert duplicate["motion_evidence_id"] == created["motion_evidence_id"]
    assert duplicate["event_id"] == created["event_id"]
    assert duplicate["visit_id"] == created["visit_id"]
    assert duplicate["review_queue_item_id"] == created["review_queue_item_id"]
    assert await product_counts(client) == after_create

    correction_response = await client.post(
        "/api/review-labels",
        json={
            "target_type": "visit",
            "target_id": created["visit_id"],
            "label": "northern_cardinal",
            "notes": "Confirmed stored live activity.",
        },
    )

    assert correction_response.status_code == 201
    correction = correction_response.json()
    assert correction["review_label"]["target_id"] == created["visit_id"]
    assert correction["visit"]["review_status"] == "reviewed"
    labels_after_correction = (await client.get("/api/review-labels")).json()
    bird_log_labels = [
        label
        for label in labels_after_correction
        if label["target_type"] == "visit" and label["target_id"] == created["visit_id"]
    ]
    assert len(bird_log_labels) == 1
    assert bird_log_labels[0]["label"] == "northern_cardinal"
    corrected_counts = await product_counts(client)
    assert corrected_counts["review_labels"] == after_create["review_labels"] + 1


async def test_live_activity_session_groups_hits_and_promotes_one_best_frame(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    frame_0 = b"\xff\xd8session-grouping-0\xff\xd9"
    frame_1 = b"\xff\xd8session-grouping-1\xff\xd9"
    frame_2 = b"\xff\xd8session-grouping-2\xff\xd9"
    frame_3 = b"\xff\xd8session-grouping-3\xff\xd9"
    fake_process = FakeFfmpegProcess([frame_0, frame_1])

    monkeypatch.setattr(
        "mockingbird.playback.local_camera_bridge.is_ffmpeg_available",
        lambda: True,
    )
    monkeypatch.setattr(
        "mockingbird.api.main.local_camera_bridge.start_local_camera_mjpeg_process",
        lambda device, **kwargs: fake_process,
    )
    patch_live_motion_decoder(
        monkeypatch,
        {
            frame_0: blank_frame(width=100, height=100),
            frame_1: frame_with(
                [(30, 40), (30, 41), (31, 40), (31, 41)],
                width=100,
                height=100,
            ),
            frame_2: blank_frame(width=100, height=100),
            frame_3: frame_with(
                [
                    (30, 40),
                    (30, 41),
                    (30, 42),
                    (31, 40),
                    (31, 41),
                    (31, 42),
                    (32, 40),
                    (32, 41),
                    (32, 42),
                ],
                width=100,
                height=100,
            ),
        },
    )
    await configure_local_usb_camera(client, device="/dev/video0")
    start_response = await client.post(f"/api/streams/{STREAM_ID}/live-session/start")
    assert start_response.status_code == 200
    await wait_for_live_session_frame_count(client, STREAM_ID, minimum=2)

    before = await product_counts(client)
    first_response = await client.post(
        f"/api/streams/{STREAM_ID}/live-motion/start",
        json={
            "save_best_frame": True,
            "create_review_activity": False,
            "min_changed_ratio": 0.003,
            "pixel_delta_threshold": 10,
            "min_triggered_frames": 1,
            "interval_seconds": 10,
        },
    )

    assert first_response.status_code == 200
    first = first_response.json()
    assert first["activity_detected"] is True
    assert first["activity_session_id"].startswith("live-activity-")
    assert first["activity_detection_count"] == 1
    assert first["activity_best_frame_sequence"] == 2
    assert first["best_media_asset_id"] is None
    assert await product_counts(client) == before

    captured_at = datetime.now(UTC)
    live_frame_cache.store_latest_frame(
        STREAM_ID,
        frame_2,
        captured_at=captured_at + timedelta(seconds=1),
    )
    live_frame_cache.store_latest_frame(
        STREAM_ID,
        frame_3,
        captured_at=captured_at + timedelta(seconds=2),
    )
    second_response = await client.post(
        f"/api/streams/{STREAM_ID}/live-motion/evaluate",
        json={
            "save_best_frame": True,
            "create_review_activity": False,
            "min_changed_ratio": 0.003,
            "pixel_delta_threshold": 10,
            "min_triggered_frames": 1,
        },
    )

    assert second_response.status_code == 200
    second = second_response.json()
    assert second["activity_session_id"] == first["activity_session_id"]
    assert second["activity_detection_count"] == 2
    assert second["activity_best_frame_sequence"] == 4
    assert second["activity_best_score"] > first["activity_best_score"]
    assert second["best_media_asset_id"] is None
    assert await product_counts(client) == before

    status = (await client.get(f"/api/streams/{STREAM_ID}/live-session/status")).json()
    assert status["current_activity_session_id"] == first["activity_session_id"]
    assert status["activity_detection_count"] == 2
    assert status["activity_best_frame_sequence"] == 4
    assert status["activity_review_activity_created"] is False
    assert status["monitor_running"] is True

    create_response = await client.post(
        f"/api/streams/{STREAM_ID}/live-motion/review-activity"
    )

    assert create_response.status_code == 200
    created = create_response.json()
    assert created["status"] == "created"
    assert created["activity_session_id"] == first["activity_session_id"]
    assert created["activity_detection_count"] == 2
    assert created["media_asset_id"].startswith("media-asset-")
    assert created["motion_evidence_id"].startswith("motion-evidence-")
    assert created["review_queue_item_id"] == f"review-queue-{created['visit_id']}"
    assert created["creates_truth"] is False

    after_create = await product_counts(client)
    assert after_create["media_assets"] == before["media_assets"] + 1
    assert after_create["motion_evidence"] == before["motion_evidence"] + 1
    assert after_create["events"] == before["events"] + 1
    assert after_create["visits"] == before["visits"] + 1
    assert after_create["review_labels"] == before["review_labels"]
    assert after_create["dataset_exports"] == before["dataset_exports"]

    duplicate_response = await client.post(
        f"/api/streams/{STREAM_ID}/live-motion/review-activity"
    )
    assert duplicate_response.status_code == 200
    duplicate = duplicate_response.json()
    assert duplicate["status"] == "already_exists"
    assert duplicate["already_exists"] is True
    assert duplicate["activity_session_id"] == first["activity_session_id"]
    assert duplicate["motion_evidence_id"] == created["motion_evidence_id"]
    assert duplicate["review_queue_item_id"] == created["review_queue_item_id"]
    assert await product_counts(client) == after_create


async def test_small_feeder_activity_capture_and_review_handoff_keep_monitor_running(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    frame_0 = b"\xff\xd8session-small-feeder-0\xff\xd9"
    frame_1 = b"\xff\xd8session-small-feeder-1\xff\xd9"
    fake_process = FakeFfmpegProcess([frame_0, frame_1])

    monkeypatch.setattr(
        "mockingbird.playback.local_camera_bridge.is_ffmpeg_available",
        lambda: True,
    )
    monkeypatch.setattr(
        "mockingbird.api.main.local_camera_bridge.start_local_camera_mjpeg_process",
        lambda device, **kwargs: fake_process,
    )
    patch_live_motion_decoder(
        monkeypatch,
        {
            frame_0: blank_frame(width=100, height=100),
            frame_1: frame_with(
                [(30, 40), (30, 41), (31, 40), (31, 41)],
                width=100,
                height=100,
            ),
        },
    )
    await configure_local_usb_camera(client, device="/dev/video0")
    before = await product_counts(client)
    before_labels = (await client.get("/api/review-labels")).json()

    start_response = await client.post(f"/api/streams/{STREAM_ID}/live-session/start")
    assert start_response.status_code == 200
    await wait_for_live_session_frame_count(client, STREAM_ID, minimum=2)

    monitor_response = await client.post(
        f"/api/streams/{STREAM_ID}/live-motion/start",
        json={
            "save_best_frame": True,
            "create_review_activity": False,
            "min_changed_ratio": 0.003,
            "pixel_delta_threshold": 10,
            "min_triggered_frames": 1,
            "interval_seconds": 10,
        },
    )

    assert monitor_response.status_code == 200
    monitor = monitor_response.json()
    assert monitor["activity_detected"] is True
    assert monitor["strongest_zone_name"] == "Feeder"
    assert monitor["fine_motion_applied"] is True
    assert monitor["threshold_source"] == "high_feeder_fine"
    assert monitor["best_media_asset_id"] is None
    assert monitor["activity_session_id"].startswith("live-activity-")
    assert monitor["activity_detection_count"] == 1
    status_after_motion = (
        await client.get(f"/api/streams/{STREAM_ID}/live-session/status")
    ).json()
    assert status_after_motion["status"] == "running"
    assert status_after_motion["monitor_running"] is True
    assert status_after_motion["current_activity_session_id"] == monitor["activity_session_id"]
    assert status_after_motion["last_activity"]["best_media_asset_id"] is None

    def fail_if_one_shot_capture_runs(*args: object, **kwargs: object) -> bytes:
        raise AssertionError("Capture after small feeder activity must reuse session frames")

    monkeypatch.setattr(
        "mockingbird.api.main.local_camera_bridge.capture_local_camera_frame",
        fail_if_one_shot_capture_runs,
    )
    capture_response = await client.post(
        f"/api/streams/{STREAM_ID}/local-camera/capture-frame"
    )

    assert capture_response.status_code == 200
    capture = capture_response.json()
    assert capture["status"] == "saved"
    assert capture["capture_source"] == "live_camera_session"
    status_after_capture = (
        await client.get(f"/api/streams/{STREAM_ID}/live-session/status")
    ).json()
    assert status_after_capture["status"] == "running"
    assert status_after_capture["monitor_running"] is True
    assert status_after_capture["current_activity_session_id"] == monitor[
        "activity_session_id"
    ]
    assert status_after_capture["last_activity"]["best_media_asset_id"] is None

    create_response = await client.post(
        f"/api/streams/{STREAM_ID}/live-motion/review-activity"
    )

    assert create_response.status_code == 200
    created = create_response.json()
    assert created["review_activity_created"] is True
    assert created["activity_session_id"] == monitor["activity_session_id"]
    assert created["media_asset_id"].startswith("media-asset-")
    assert created["motion_evidence_id"].startswith("motion-evidence-")
    assert created["event_id"].startswith("event-motion-")
    assert created["visit_id"].startswith("visit-motion-")
    assert created["review_queue_item_id"] == f"review-queue-{created['visit_id']}"
    assert created["creates_truth"] is False
    status_after_handoff = (
        await client.get(f"/api/streams/{STREAM_ID}/live-session/status")
    ).json()
    assert status_after_handoff["status"] == "running"
    assert status_after_handoff["monitor_running"] is True
    assert status_after_handoff["last_motion_result"]["review_activity_created"] is True

    labels_after_handoff = (await client.get("/api/review-labels")).json()
    assert labels_after_handoff == before_labels
    after_handoff = await product_counts(client)
    assert after_handoff["media_assets"] == before["media_assets"] + 2
    assert after_handoff["motion_evidence"] == before["motion_evidence"] + 1
    assert after_handoff["events"] == before["events"] + 1
    assert after_handoff["visits"] == before["visits"] + 1
    assert after_handoff["review_labels"] == before["review_labels"]
    assert after_handoff["dataset_exports"] == before["dataset_exports"]

    correction_response = await client.post(
        "/api/review-labels",
        json={
            "target_type": "visit",
            "target_id": created["visit_id"],
            "label": "northern_cardinal",
            "notes": "Confirmed small feeder activity.",
        },
    )
    assert correction_response.status_code == 201
    corrected_counts = await product_counts(client)
    assert corrected_counts["review_labels"] == after_handoff["review_labels"] + 1


async def test_playback_status_does_not_start_local_camera_bridge_process(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "mockingbird.playback.local_camera_bridge.is_ffmpeg_available",
        lambda: True,
    )

    def fail_if_started(device: str, **kwargs: object):  # noqa: ANN202
        raise AssertionError("Playback status must not start local camera ffmpeg")

    monkeypatch.setattr(
        "mockingbird.api.main.local_camera_bridge.start_local_camera_mjpeg_process",
        fail_if_started,
    )
    await configure_local_usb_camera(client, device="/dev/video0")

    response = await client.get(f"/api/streams/{STREAM_ID}/playback")

    assert response.status_code == 200


def test_local_camera_command_uses_list_args_and_safe_device_validation() -> None:
    command = local_camera_bridge.build_local_camera_mjpeg_command("/dev/video0")

    assert command[:6] == [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-f",
        "v4l2",
    ]
    assert "-i" in command
    assert "/dev/video0" in command
    assert "-input_format" not in command
    assert "-video_size" not in command
    assert "-framerate" not in command
    assert "shell=True" not in command
    assert local_camera_bridge.validate_local_camera_device("/dev/video0") is True
    assert local_camera_bridge.validate_local_camera_device("/dev/video12") is True
    assert local_camera_bridge.validate_local_camera_device("/tmp/video0") is False
    assert (
        local_camera_bridge.local_camera_status(
            device="/dev/video0",
            platform_name="darwin",
            ffmpeg_available=True,
        )
        == "unsupported_platform"
    )


def test_local_camera_command_allows_explicit_input_options() -> None:
    command = local_camera_bridge.build_local_camera_mjpeg_command(
        "/dev/video1",
        input_format="mjpeg",
        video_size="640x480",
        input_frame_rate=10,
    )

    assert command[command.index("-input_format") + 1] == "mjpeg"
    assert command[command.index("-video_size") + 1] == "640x480"
    assert command[command.index("-framerate") + 1] == "10"
    assert "/dev/video1" in command


async def test_windows_dshow_configuration_requires_camera_name(
    client: httpx.AsyncClient,
) -> None:
    await configure_windows_dshow_camera(client, camera_name=None)

    response = await client.get(f"/api/sources/{SOURCE_ID}/provider-configuration")

    assert response.status_code == 200
    configuration = response.json()
    assert configuration["provider_key"] == "local_usb"
    assert configuration["missing_fields"] == ["windows_camera_name"]
    assert "Windows DirectShow camera name is required" in configuration["message"]
    assert "ffmpeg -list_devices true -f dshow -i dummy" in configuration["setup_hint"]


async def test_windows_dshow_playback_reports_missing_camera_name(
    client: httpx.AsyncClient,
) -> None:
    await configure_windows_dshow_camera(client, camera_name=None)

    response = await client.get(f"/api/streams/{STREAM_ID}/playback")

    assert response.status_code == 200
    playback = response.json()
    assert playback["status"] == "not_configured"
    assert playback["playback_kind"] == "windows_dshow"
    assert playback["supports_live_playback"] is False
    assert playback["windows_camera_status"] == "camera_name_missing"
    assert playback["windows_camera_bridge_available"] is False
    assert playback["bridged_mjpeg_url"] is None
    assert "ffmpeg -list_devices true -f dshow -i dummy" in playback["setup_hint"]


async def test_windows_dshow_playback_reports_unsupported_host_without_windows_ffmpeg(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "mockingbird.repository.product_repository.windows_camera_bridge.windows_camera_status",
        lambda **kwargs: "unsupported_host",
    )
    await configure_windows_dshow_camera(client, camera_name="EMEET SmartCam S600")

    response = await client.get(f"/api/streams/{STREAM_ID}/playback")

    assert response.status_code == 200
    playback = response.json()
    assert playback["status"] == "unsupported_stream_type"
    assert playback["playback_kind"] == "windows_dshow"
    assert playback["supports_live_playback"] is False
    assert playback["windows_camera_status"] == "unsupported_host"
    assert playback["windows_camera_bridge_available"] is False
    assert playback["message"] == (
        "Windows DirectShow requires Windows ffmpeg.exe or running the API on Windows."
    )
    assert "/mnt/c/ffmpeg/bin/ffmpeg.exe" in playback["setup_hint"]


async def test_windows_dshow_playback_reports_ffmpeg_missing(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "mockingbird.repository.product_repository.windows_camera_bridge.windows_camera_status",
        lambda **kwargs: "ffmpeg_missing",
    )
    await configure_windows_dshow_camera(client, camera_name="EMEET SmartCam S600")

    response = await client.get(f"/api/streams/{STREAM_ID}/playback")

    assert response.status_code == 200
    playback = response.json()
    assert playback["status"] == "unavailable"
    assert playback["playback_kind"] == "windows_dshow"
    assert playback["supports_live_playback"] is False
    assert playback["windows_camera_status"] == "ffmpeg_missing"
    assert playback["windows_camera_bridge_available"] is False
    assert playback["message"] == "Windows DirectShow bridge unavailable - ffmpeg not found."


async def test_windows_dshow_playback_reports_bridge_available_with_windows_ffmpeg_path(
    client: httpx.AsyncClient,
) -> None:
    await configure_windows_dshow_camera(
        client,
        camera_name="EMEET SmartCam S600",
        ffmpeg_binary_path="/mnt/c/ffmpeg/bin/ffmpeg.exe",
    )

    response = await client.get(f"/api/streams/{STREAM_ID}/playback")

    assert response.status_code == 200
    playback = response.json()
    assert playback["status"] == "live_ready"
    assert playback["playback_kind"] == "windows_dshow"
    assert playback["supports_live_playback"] is True
    assert playback["windows_camera_status"] == "available"
    assert playback["windows_camera_bridge_available"] is True
    assert playback["windows_camera_name_display"] == "EMEET SmartCam S600"
    assert playback["windows_ffmpeg_binary_display"] == "/mnt/c/ffmpeg/bin/ffmpeg.exe"
    assert playback["bridged_mjpeg_url"] == (
        f"/api/streams/{STREAM_ID}/live/windows-dshow-mjpeg"
    )


async def test_windows_dshow_bridge_endpoint_rejects_non_windows_dshow_stream(
    client: httpx.AsyncClient,
) -> None:
    await configure_local_usb_camera(client, device="/dev/video0")

    response = await client.get(f"/api/streams/{STREAM_ID}/live/windows-dshow-mjpeg")

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "Windows DirectShow bridge requires windows_dshow playback type."
    )


async def test_windows_dshow_bridge_endpoint_streams_mocked_mjpeg_without_creating_truth(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    jpeg_frame_one = b"\xff\xd8windows-frame-one\xff\xd9"
    jpeg_frame_two = b"\xff\xd8windows-frame-two\xff\xd9"
    fake_process = object()
    started: list[tuple[str, str | None, str | None, str | None, str | None]] = []

    def fake_start(
        camera_name: str,
        *,
        ffmpeg_binary_path: str | None = None,
        input_format: str | None = None,
        video_size: str | None = None,
        framerate: str | None = None,
    ) -> object:
        started.append((camera_name, ffmpeg_binary_path, input_format, video_size, framerate))
        return fake_process

    monkeypatch.setattr(
        "mockingbird.api.main.windows_camera_bridge.start_windows_dshow_mjpeg_process",
        fake_start,
    )
    monkeypatch.setattr(
        "mockingbird.api.main.windows_camera_bridge.iter_multipart_mjpeg",
        lambda process, **kwargs: iter(
            [
                b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpeg_frame_one,
                b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpeg_frame_two,
            ]
        ),
    )
    await configure_windows_dshow_camera(
        client,
        camera_name="EMEET SmartCam S600",
        ffmpeg_binary_path="/mnt/c/ffmpeg/bin/ffmpeg.exe",
        video_size="640x480",
        preview_video_size="1280x720",
        framerate="15",
        input_format="mjpeg",
    )
    before = await product_counts(client)

    response = await get_stream_windows_dshow_mjpeg_bridge(STREAM_ID)

    assert response.status_code == 200
    assert response.media_type == (
        f"multipart/x-mixed-replace; boundary={windows_camera_bridge.MJPEG_BOUNDARY}"
    )
    assert response.headers["content-type"] == (
        f"multipart/x-mixed-replace; boundary={windows_camera_bridge.MJPEG_BOUNDARY}"
    )
    assert started == [
        (
            "EMEET SmartCam S600",
            "/mnt/c/ffmpeg/bin/ffmpeg.exe",
            "mjpeg",
            "1280x720",
            "15",
        )
    ]
    assert await product_counts(client) == before


async def test_windows_dshow_capture_without_session_ignores_fresh_cache_and_uses_one_shot(
    client: httpx.AsyncClient,
    isolated_repository: ProductRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    live_frame = b"\xff\xd8cached-windows-live-frame\xff\xd9"
    fallback_frame = b"\xff\xd8fallback-windows-live-frame\xff\xd9"
    captured_args: list[str] = []

    def fake_capture(camera_name: str, **kwargs: object) -> bytes:
        captured_args.append(camera_name)
        return fallback_frame

    monkeypatch.setattr(
        "mockingbird.api.main.windows_camera_bridge.capture_windows_dshow_frame",
        fake_capture,
    )
    await configure_windows_dshow_camera(
        client,
        camera_name="EMEET SmartCam S600",
        ffmpeg_binary_path="/mnt/c/ffmpeg/bin/ffmpeg.exe",
    )
    live_frame_cache.store_latest_frame(STREAM_ID, live_frame)
    before = await product_counts(client)

    response = await client.post(f"/api/streams/{STREAM_ID}/local-camera/capture-frame")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "saved"
    assert body["message"] == (
        "Saved one local camera frame directly because Live view was not streaming. "
        "It will not appear in Bird Log until you create/review activity."
    )
    assert body["capture_source"] == "one_shot_ffmpeg"
    assert body["live_frame_age_ms"] is None
    assert body["content_type"] == "image/jpeg"
    assert body["bytes_written"] == len(fallback_frame)
    assert body["creates_event"] is False
    assert body["creates_visit"] is False
    assert body["creates_truth"] is False
    assert body["creates_export"] is False
    assert captured_args == ["EMEET SmartCam S600"]

    media_response = await client.get(f"/api/media/{body['media_asset_id']}")
    assert media_response.status_code == 200
    media_asset = media_response.json()
    assert "playback_type=windows_dshow" in media_asset["notes"]
    saved_path = Path(media_asset["local_path"]).resolve()
    assert saved_path.is_relative_to(isolated_repository.media_root.resolve())
    assert saved_path.read_bytes() == fallback_frame

    after = await product_counts(client)
    assert after["media_assets"] == before["media_assets"] + 1
    for key in before:
        if key != "media_assets":
            assert after[key] == before[key]


async def test_windows_dshow_capture_frame_ignores_stale_live_cache_and_falls_back(
    client: httpx.AsyncClient,
    isolated_repository: ProductRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stale_frame = b"\xff\xd8stale-windows-live-frame\xff\xd9"
    fallback_frame = b"\xff\xd8fallback-windows-frame\xff\xd9"
    captured_args: list[str] = []

    def fake_capture(camera_name: str, **kwargs: object) -> bytes:
        captured_args.append(camera_name)
        return fallback_frame

    monkeypatch.setattr(
        "mockingbird.api.main.windows_camera_bridge.capture_windows_dshow_frame",
        fake_capture,
    )
    await configure_windows_dshow_camera(
        client,
        camera_name="EMEET SmartCam S600",
        ffmpeg_binary_path="/mnt/c/ffmpeg/bin/ffmpeg.exe",
    )
    live_frame_cache.store_latest_frame(
        STREAM_ID,
        stale_frame,
        captured_at=datetime.now(UTC) - timedelta(seconds=30),
    )

    response = await client.post(f"/api/streams/{STREAM_ID}/local-camera/capture-frame")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "saved"
    assert body["capture_source"] == "one_shot_ffmpeg"
    assert body["live_frame_age_ms"] is None
    assert captured_args == ["EMEET SmartCam S600"]
    media_response = await client.get(f"/api/media/{body['media_asset_id']}")
    assert media_response.status_code == 200
    saved_path = Path(media_response.json()["local_path"]).resolve()
    assert saved_path.is_relative_to(isolated_repository.media_root.resolve())
    assert saved_path.read_bytes() == fallback_frame


async def test_windows_dshow_capture_frame_creates_one_media_asset_only(
    client: httpx.AsyncClient,
    isolated_repository: ProductRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    jpeg_frame = b"\xff\xd8captured-windows-frame\xff\xd9"
    captured_args: list[tuple[str, str | None, str | None, str | None, str | None]] = []

    def fake_capture(
        camera_name: str,
        *,
        ffmpeg_binary_path: str | None = None,
        input_format: str | None = None,
        video_size: str | None = None,
        framerate: str | None = None,
    ) -> bytes:
        captured_args.append((camera_name, ffmpeg_binary_path, input_format, video_size, framerate))
        return jpeg_frame

    monkeypatch.setattr(
        "mockingbird.api.main.windows_camera_bridge.capture_windows_dshow_frame",
        fake_capture,
    )
    await configure_windows_dshow_camera(
        client,
        camera_name="EMEET SmartCam S600",
        ffmpeg_binary_path="/mnt/c/ffmpeg/bin/ffmpeg.exe",
        video_size="1280x720",
        capture_video_size="1920x1080",
        framerate="10",
        input_format="mjpeg",
    )
    before = await product_counts(client)

    response = await client.post(f"/api/streams/{STREAM_ID}/local-camera/capture-frame")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "saved"
    assert body["message"] == (
        "Saved one local camera frame directly because Live view was not streaming. "
        "It will not appear in Bird Log until you create/review activity."
    )
    assert body["capture_source"] == "one_shot_ffmpeg"
    assert body["live_frame_age_ms"] is None
    assert body["stream_id"] == STREAM_ID
    assert body["source_id"] == SOURCE_ID
    assert body["media_asset_id"].startswith("media-asset-")
    assert body["content_type"] == "image/jpeg"
    assert body["bytes_written"] == len(jpeg_frame)
    assert body["file_name"].endswith(".jpg")
    assert body["relative_path"] == body["file_name"]
    assert body["creates_event"] is False
    assert body["creates_visit"] is False
    assert body["creates_truth"] is False
    assert body["creates_export"] is False
    assert captured_args == [
        (
            "EMEET SmartCam S600",
            "/mnt/c/ffmpeg/bin/ffmpeg.exe",
            "mjpeg",
            "1920x1080",
            "10",
        )
    ]

    media_response = await client.get(f"/api/media/{body['media_asset_id']}")
    assert media_response.status_code == 200
    media_asset = media_response.json()
    assert media_asset["source_id"] == SOURCE_ID
    assert media_asset["stream_id"] == STREAM_ID
    assert media_asset["content_type"] == "image/jpeg"
    assert media_asset["media_type"] == "image"
    assert "Saved explicit local camera frame capture." in media_asset["notes"]
    assert "playback_type=windows_dshow" in media_asset["notes"]
    assert "Creates no Events, Visits, ReviewLabels, exports, or truth." in media_asset["notes"]
    saved_path = Path(media_asset["local_path"]).resolve()
    assert saved_path.is_relative_to(isolated_repository.media_root.resolve())
    assert saved_path.read_bytes() == jpeg_frame

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


async def test_local_usb_capture_without_session_ignores_fresh_cache_and_uses_one_shot(
    client: httpx.AsyncClient,
    isolated_repository: ProductRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    live_frame = b"\xff\xd8cached-local-live-frame\xff\xd9"
    fallback_frame = b"\xff\xd8fallback-local-live-frame\xff\xd9"
    captured_args: list[str] = []

    monkeypatch.setattr(
        "mockingbird.api.main.local_camera_bridge.local_camera_status",
        lambda **kwargs: "available",
    )

    def fake_capture(device: str, **kwargs: object) -> bytes:
        captured_args.append(device)
        return fallback_frame

    monkeypatch.setattr(
        "mockingbird.api.main.local_camera_bridge.capture_local_camera_frame",
        fake_capture,
    )
    await configure_local_usb_camera(
        client,
        device="/dev/video0",
        capture_video_size="1920x1080",
        framerate="15",
        input_format="mjpeg",
    )
    live_frame_cache.store_latest_frame(STREAM_ID, live_frame)
    before = await product_counts(client)

    response = await client.post(f"/api/streams/{STREAM_ID}/local-camera/capture-frame")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "saved"
    assert body["message"] == (
        "Saved one local camera frame directly because Live view was not streaming. "
        "It will not appear in Bird Log until you create/review activity."
    )
    assert body["capture_source"] == "one_shot_ffmpeg"
    assert body["live_frame_age_ms"] is None
    assert body["content_type"] == "image/jpeg"
    assert body["bytes_written"] == len(fallback_frame)
    assert body["creates_event"] is False
    assert body["creates_visit"] is False
    assert body["creates_truth"] is False
    assert body["creates_export"] is False
    assert captured_args == ["/dev/video0"]

    media_response = await client.get(f"/api/media/{body['media_asset_id']}")
    assert media_response.status_code == 200
    media_asset = media_response.json()
    assert "playback_type=local_usb" in media_asset["notes"]
    saved_path = Path(media_asset["local_path"]).resolve()
    assert saved_path.is_relative_to(isolated_repository.media_root.resolve())
    assert saved_path.read_bytes() == fallback_frame

    after = await product_counts(client)
    assert after["media_assets"] == before["media_assets"] + 1
    for key in before:
        if key != "media_assets":
            assert after[key] == before[key]


async def test_local_usb_capture_frame_uses_running_session_frame_without_one_shot(
    client: httpx.AsyncClient,
    isolated_repository: ProductRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first_session_frame = b"\xff\xd8session-capture-frame-0\xff\xd9"
    session_frame = b"\xff\xd8session-capture-frame-1\xff\xd9"
    fake_process = FakeFfmpegProcess([first_session_frame, session_frame])

    monkeypatch.setattr(
        "mockingbird.playback.local_camera_bridge.is_ffmpeg_available",
        lambda: True,
    )
    monkeypatch.setattr(
        "mockingbird.api.main.local_camera_bridge.start_local_camera_mjpeg_process",
        lambda device, **kwargs: fake_process,
    )
    patch_live_motion_decoder(
        monkeypatch,
        {
            first_session_frame: blank_frame(),
            session_frame: blank_frame(),
        },
    )
    await configure_local_usb_camera(client, device="/dev/video0")
    start_response = await client.post(f"/api/streams/{STREAM_ID}/live-session/start")
    assert start_response.status_code == 200
    await wait_for_live_session_frame_count(client, STREAM_ID, minimum=2)

    monitor_response = await client.post(
        f"/api/streams/{STREAM_ID}/live-motion/start",
        json={
            "save_best_frame": False,
            "create_review_activity": False,
            "min_changed_ratio": 0.1,
            "min_triggered_frames": 1,
            "interval_seconds": 10,
        },
    )
    assert monitor_response.status_code == 200
    status_before_capture = (
        await client.get(f"/api/streams/{STREAM_ID}/live-session/status")
    ).json()
    assert status_before_capture["status"] == "running"
    assert status_before_capture["monitor_running"] is True
    last_activity = {"best_media_asset_id": "media-asset-existing-activity"}
    get_live_camera_session_manager().update_last_activity(STREAM_ID, last_activity)

    def fail_if_one_shot_capture_runs(*args: object, **kwargs: object) -> bytes:
        raise AssertionError("Capture must use the running camera session frame")

    monkeypatch.setattr(
        "mockingbird.api.main.local_camera_bridge.capture_local_camera_frame",
        fail_if_one_shot_capture_runs,
    )
    before = await product_counts(client)

    response = await client.post(f"/api/streams/{STREAM_ID}/local-camera/capture-frame")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "saved"
    assert body["message"] == "Captured current frame; camera and monitoring are still running."
    assert body["capture_source"] == "live_camera_session"
    assert body["live_frame_age_ms"] >= 0
    assert body["bytes_written"] == len(session_frame)
    assert body["creates_event"] is False
    assert body["creates_visit"] is False
    assert body["creates_truth"] is False
    assert body["creates_export"] is False

    media_response = await client.get(f"/api/media/{body['media_asset_id']}")
    assert media_response.status_code == 200
    saved_path = Path(media_response.json()["local_path"]).resolve()
    assert saved_path.is_relative_to(isolated_repository.media_root.resolve())
    assert saved_path.read_bytes() == session_frame

    cached = live_frame_cache.get_latest_frame(STREAM_ID)
    assert cached is not None
    assert cached.frame_bytes == session_frame
    status_after_capture = (
        await client.get(f"/api/streams/{STREAM_ID}/live-session/status")
    ).json()
    assert status_after_capture["status"] == "running"
    assert status_after_capture["monitor_running"] is True
    assert status_after_capture["frame_count"] >= 2
    assert status_after_capture["last_activity"] == last_activity

    after = await product_counts(client)
    assert after["media_assets"] == before["media_assets"] + 1
    for key in before:
        if key != "media_assets":
            assert after[key] == before[key]

    stop_response = await client.post(f"/api/streams/{STREAM_ID}/live-session/stop")
    assert stop_response.status_code == 200
    stopped = stop_response.json()
    assert stopped["status"] == "stopped"
    assert stopped["monitor_running"] is False


async def test_local_usb_capture_with_running_session_without_fresh_frame_skips_one_shot(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_process = FakeFfmpegProcess([])

    monkeypatch.setattr(
        "mockingbird.playback.local_camera_bridge.is_ffmpeg_available",
        lambda: True,
    )
    monkeypatch.setattr(
        "mockingbird.api.main.local_camera_bridge.start_local_camera_mjpeg_process",
        lambda device, **kwargs: fake_process,
    )
    await configure_local_usb_camera(client, device="/dev/video0")
    start_response = await client.post(f"/api/streams/{STREAM_ID}/live-session/start")
    assert start_response.status_code == 200

    monitor_response = await client.post(
        f"/api/streams/{STREAM_ID}/live-motion/start",
        json={
            "save_best_frame": False,
            "create_review_activity": False,
            "min_changed_ratio": 0.1,
            "min_triggered_frames": 1,
            "interval_seconds": 10,
        },
    )
    assert monitor_response.status_code == 200
    last_activity = {"best_media_asset_id": "media-asset-existing-stale-activity"}
    get_live_camera_session_manager().update_last_activity(STREAM_ID, last_activity)

    def fail_if_one_shot_capture_runs(*args: object, **kwargs: object) -> bytes:
        raise AssertionError("Capture must not start one-shot ffmpeg during a running session")

    monkeypatch.setattr(
        "mockingbird.api.main.local_camera_bridge.capture_local_camera_frame",
        fail_if_one_shot_capture_runs,
    )
    before = await product_counts(client)

    response = await client.post(f"/api/streams/{STREAM_ID}/local-camera/capture-frame")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "unavailable"
    assert body["message"] == "No fresh session frame available; camera session is still running."
    assert body["capture_source"] == "unavailable"
    assert body["media_asset_id"] is None
    assert body["bytes_written"] == 0
    assert body["creates_event"] is False
    assert body["creates_visit"] is False
    assert body["creates_truth"] is False
    assert body["creates_export"] is False
    assert await product_counts(client) == before

    assert live_frame_cache.get_latest_frame(STREAM_ID) is None
    status_after_capture = (
        await client.get(f"/api/streams/{STREAM_ID}/live-session/status")
    ).json()
    assert status_after_capture["status"] == "running"
    assert status_after_capture["monitor_running"] is True
    assert status_after_capture["frame_count"] == 0
    assert status_after_capture["last_activity"] == last_activity

    stop_response = await client.post(f"/api/streams/{STREAM_ID}/live-session/stop")
    assert stop_response.status_code == 200
    stopped = stop_response.json()
    assert stopped["status"] == "stopped"
    assert stopped["monitor_running"] is False


async def test_local_usb_capture_frame_creates_one_media_asset_only(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    jpeg_frame = b"\xff\xd8captured-local-frame\xff\xd9"
    captured_args: list[tuple[str, str | None, str | None, str | None, str | None]] = []

    monkeypatch.setattr(
        "mockingbird.api.main.local_camera_bridge.local_camera_status",
        lambda **kwargs: "available",
    )

    def fake_capture(
        device: str,
        *,
        camera_format: str | None = None,
        input_format: str | None = None,
        video_size: str | None = None,
        input_frame_rate: str | None = None,
    ) -> bytes:
        captured_args.append((device, camera_format, input_format, video_size, input_frame_rate))
        return jpeg_frame

    monkeypatch.setattr(
        "mockingbird.api.main.local_camera_bridge.capture_local_camera_frame",
        fake_capture,
    )
    await configure_local_usb_camera(
        client,
        device="/dev/video0",
        capture_video_size="1920x1080",
        framerate="15",
        input_format="mjpeg",
    )
    before = await product_counts(client)

    response = await client.post(f"/api/streams/{STREAM_ID}/local-camera/capture-frame")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "saved"
    assert body["message"] == (
        "Saved one local camera frame directly because Live view was not streaming. "
        "It will not appear in Bird Log until you create/review activity."
    )
    assert body["capture_source"] == "one_shot_ffmpeg"
    assert body["live_frame_age_ms"] is None
    assert body["content_type"] == "image/jpeg"
    assert body["bytes_written"] == len(jpeg_frame)
    assert body["creates_event"] is False
    assert body["creates_visit"] is False
    assert body["creates_truth"] is False
    assert body["creates_export"] is False
    assert captured_args == [("/dev/video0", "v4l2", "mjpeg", "1920x1080", "15")]

    media_response = await client.get(f"/api/media/{body['media_asset_id']}")
    assert media_response.status_code == 200
    media_asset = media_response.json()
    assert "playback_type=local_usb" in media_asset["notes"]
    after = await product_counts(client)
    assert after["media_assets"] == before["media_assets"] + 1
    for key in before:
        if key != "media_assets":
            assert after[key] == before[key]


async def test_local_camera_capture_reports_missing_windows_camera_name(
    client: httpx.AsyncClient,
) -> None:
    await configure_windows_dshow_camera(client, camera_name=None)
    before = await product_counts(client)

    response = await client.post(f"/api/streams/{STREAM_ID}/local-camera/capture-frame")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "camera_not_configured"
    assert body["media_asset_id"] is None
    assert "Windows DirectShow camera name" in body["message"]
    assert await product_counts(client) == before


async def test_local_camera_capture_reports_ffmpeg_missing(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "mockingbird.api.main.windows_camera_bridge.windows_camera_status",
        lambda **kwargs: "ffmpeg_missing",
    )
    await configure_windows_dshow_camera(client, camera_name="EMEET SmartCam S600")
    before = await product_counts(client)

    response = await client.post(f"/api/streams/{STREAM_ID}/local-camera/capture-frame")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ffmpeg_missing"
    assert body["bytes_written"] == 0
    assert await product_counts(client) == before


async def test_local_camera_capture_rejects_unsupported_stream_kind(
    client: httpx.AsyncClient,
) -> None:
    await configure_external_url_live_stream(
        client,
        live_stream_url="http://camera.local/live.mjpg",
        live_stream_type="mjpeg",
    )

    response = await client.post(f"/api/streams/{STREAM_ID}/local-camera/capture-frame")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "unsupported"
    assert "local camera Source provider" in body["message"]


async def test_local_camera_capture_reports_no_frame_as_capture_failed(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "mockingbird.api.main.windows_camera_bridge.capture_windows_dshow_frame",
        lambda *args, **kwargs: (_ for _ in ()).throw(ValueError("no_frame_captured")),
    )
    await configure_windows_dshow_camera(
        client,
        camera_name="EMEET SmartCam S600",
        ffmpeg_binary_path="/mnt/c/ffmpeg/bin/ffmpeg.exe",
    )
    before = await product_counts(client)

    response = await client.post(f"/api/streams/{STREAM_ID}/local-camera/capture-frame")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "capture_failed"
    assert body["message"] == (
        "Camera is busy or did not return a frame. Close other camera apps, "
        "or open Live view until a frame appears and retry capture."
    )
    assert body["capture_source"] == "one_shot_ffmpeg"
    assert body["live_frame_age_ms"] is None
    assert body["bytes_written"] == 0
    assert await product_counts(client) == before


def test_windows_dshow_command_uses_list_args_and_safe_camera_name() -> None:
    command = windows_camera_bridge.build_windows_dshow_mjpeg_command(
        "EMEET SmartCam S600",
        ffmpeg_binary_path="/mnt/c/ffmpeg/bin/ffmpeg.exe",
        input_format="mjpeg",
        video_size="640x480",
        framerate="10",
    )

    assert command == [
        "/mnt/c/ffmpeg/bin/ffmpeg.exe",
        "-f",
        "dshow",
        "-input_format",
        "mjpeg",
        "-video_size",
        "640x480",
        "-framerate",
        "10",
        "-i",
        "video=EMEET SmartCam S600",
        "-an",
        "-f",
        "image2pipe",
        "-vcodec",
        "mjpeg",
        "-r",
        "5",
        "pipe:1",
    ]
    assert windows_camera_bridge.build_windows_dshow_list_devices_command() == [
        "ffmpeg",
        "-list_devices",
        "true",
        "-f",
        "dshow",
        "-i",
        "dummy",
    ]
    assert windows_camera_bridge.validate_windows_camera_name("EMEET SmartCam S600") is True
    assert windows_camera_bridge.validate_windows_camera_name("Camera\nName") is False
    assert windows_camera_bridge.validate_windows_camera_name("") is False


def test_windows_dshow_frame_capture_command_uses_list_args() -> None:
    command = windows_camera_bridge.build_windows_dshow_frame_capture_command(
        "EMEET SmartCam S600",
        ffmpeg_binary_path="/mnt/c/ffmpeg/bin/ffmpeg.exe",
        input_format="mjpeg",
        video_size="1280x720",
        framerate="10",
    )

    assert command == [
        "/mnt/c/ffmpeg/bin/ffmpeg.exe",
        "-f",
        "dshow",
        "-input_format",
        "mjpeg",
        "-video_size",
        "1280x720",
        "-framerate",
        "10",
        "-i",
        "video=EMEET SmartCam S600",
        "-an",
        "-frames:v",
        "1",
        "-f",
        "image2pipe",
        "-vcodec",
        "mjpeg",
        "pipe:1",
    ]


def test_windows_dshow_start_uses_popen_list_without_shell() -> None:
    calls: list[tuple[list[str], dict[str, object]]] = []

    def fake_popen(command: list[str], **kwargs: object) -> FakeFfmpegProcess:
        calls.append((command, kwargs))
        return FakeFfmpegProcess([])

    process = windows_camera_bridge.start_windows_dshow_mjpeg_process(
        "EMEET SmartCam S600",
        ffmpeg_binary_path="C:\\ffmpeg\\bin\\ffmpeg.exe",
        popen_factory=fake_popen,
    )

    assert isinstance(process, FakeFfmpegProcess)
    assert calls[0][0][0] == "C:\\ffmpeg\\bin\\ffmpeg.exe"
    assert calls[0][0][calls[0][0].index("-i") + 1] == "video=EMEET SmartCam S600"
    assert calls[0][1].get("shell") is not True


def test_local_camera_frame_capture_command_uses_list_args() -> None:
    command = local_camera_bridge.build_local_camera_frame_capture_command(
        "/dev/video0",
        video_size="640x480",
        input_frame_rate="10",
    )

    assert command[:6] == [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-f",
        "v4l2",
    ]
    assert command[command.index("-video_size") + 1] == "640x480"
    assert command[command.index("-framerate") + 1] == "10"
    assert command[command.index("-i") + 1] == "/dev/video0"
    assert command[command.index("-frames:v") + 1] == "1"
    assert "shell=True" not in command


def test_frame_capture_reader_returns_one_jpeg_and_stops_process() -> None:
    fake_process = FakeFfmpegProcess(
        [
            b"noise\xff\xd8captured-frame",
            b"\xff\xd9ignored\xff\xd8second-frame\xff\xd9",
        ]
    )

    frame = windows_camera_bridge.capture_windows_dshow_frame(
        "EMEET SmartCam S600",
        ffmpeg_binary_path="/mnt/c/ffmpeg/bin/ffmpeg.exe",
        popen_factory=lambda *args, **kwargs: fake_process,
    )

    assert frame == b"\xff\xd8captured-frame\xff\xd9"
    assert fake_process.terminated is True
    assert fake_process.waited is True
    assert fake_process.killed is False


def test_frame_capture_reader_reports_no_jpeg() -> None:
    fake_process = FakeFfmpegProcess([b"not-a-jpeg"])

    with pytest.raises(ValueError, match="no_frame_captured"):
        windows_camera_bridge.capture_windows_dshow_frame(
            "EMEET SmartCam S600",
            ffmpeg_binary_path="/mnt/c/ffmpeg/bin/ffmpeg.exe",
            popen_factory=lambda *args, **kwargs: fake_process,
        )

    assert fake_process.terminated is True
    assert fake_process.waited is True
    assert fake_process.killed is False


def test_windows_dshow_status_is_wsl_aware() -> None:
    assert (
        windows_camera_bridge.windows_camera_status(
            camera_name="EMEET SmartCam S600",
            platform_name="linux",
            ffmpeg_binary_path=None,
            ffmpeg_available=True,
        )
        == "unsupported_host"
    )
    assert (
        windows_camera_bridge.windows_camera_status(
            camera_name="EMEET SmartCam S600",
            platform_name="win32",
            ffmpeg_binary_path="ffmpeg",
            ffmpeg_available=False,
        )
        == "ffmpeg_missing"
    )
    assert (
        windows_camera_bridge.windows_camera_status(
            camera_name="EMEET SmartCam S600",
            platform_name="linux",
            ffmpeg_binary_path="/mnt/c/ffmpeg/bin/ffmpeg.exe",
            ffmpeg_available=False,
        )
        == "available"
    )


def test_windows_dshow_multipart_generator_emits_two_frames_and_stops_process() -> None:
    fake_process = FakeFfmpegProcess(
        [
            b"noise\xff\xd8frame-one\xff\xd9middle\xff\xd8frame",
            b"-two\xff\xd9tail",
        ]
    )

    chunks = list(windows_camera_bridge.iter_multipart_mjpeg(fake_process))

    assert len(chunks) == 2
    assert chunks[0].startswith(b"--frame\r\nContent-Type: image/jpeg")
    assert b"\xff\xd8frame-one\xff\xd9" in chunks[0]
    assert chunks[1].startswith(b"--frame\r\nContent-Type: image/jpeg")
    assert b"\xff\xd8frame-two\xff\xd9" in chunks[1]
    assert fake_process.terminated is True
    assert fake_process.waited is True
    assert fake_process.killed is False


def test_windows_dshow_multipart_generator_updates_latest_frame_cache() -> None:
    fake_process = FakeFfmpegProcess([b"noise\xff\xd8windows-live-frame\xff\xd9"])

    chunks = list(
        windows_camera_bridge.iter_multipart_mjpeg(
            fake_process,
            on_frame=lambda frame: live_frame_cache.store_latest_frame(STREAM_ID, frame),
        )
    )

    cached = live_frame_cache.get_latest_frame(STREAM_ID)
    assert len(chunks) == 1
    assert cached is not None
    assert cached.frame_bytes == b"\xff\xd8windows-live-frame\xff\xd9"


async def test_external_url_unknown_live_stream_type_reports_unsupported(
    client: httpx.AsyncClient,
) -> None:
    update_response = await client.patch(
        f"/api/sources/{SOURCE_ID}/provider-configuration",
        json={
            "provider_key": "external_url",
            "config": {
                "url": "http://camera.local/still.jpg",
                "live_stream_url": "http://camera.local/custom-stream",
                "live_stream_type": "unknown",
            },
        },
    )
    assert update_response.status_code == 200

    response = await client.get(f"/api/streams/{STREAM_ID}/playback")

    assert response.status_code == 200
    playback = response.json()
    assert playback["status"] == "unsupported_stream_type"
    assert playback["playback_kind"] == "unknown"
    assert playback["supports_live_playback"] is False
    assert playback["preview_url"] is None
    assert playback["live_stream_type"] == "unknown"


async def test_not_configured_stream_returns_setup_hint(
    client: httpx.AsyncClient,
    isolated_repository: ProductRepository,
) -> None:
    with isolated_repository.session_factory() as session:
        with session.begin():
            session.add(
                CameraSourceModel(
                    id="source-future-local",
                    name="Future local source",
                    kind=SourceKind.local_folder.value,
                    status=SourceStatus.needs_setup.value,
                    description="Product metadata for a future local source.",
                )
            )
            session.add(
                StreamModel(
                    id="stream-future-local",
                    source_id="source-future-local",
                    name="Future source stream",
                    description="Placeholder stream for future playback.",
                    is_live=False,
                )
            )

    response = await client.get("/api/streams/stream-future-local/playback")

    assert response.status_code == 200
    playback = response.json()
    assert playback["status"] == "not_configured"
    assert playback["playback_kind"] == "placeholder"
    assert playback["setup_hint"]
    assert playback["supports_zone_editing"] is True
    assert playback["supports_live_playback"] is False
    assert playback["adapter_key"] == "local_folder"


async def test_playback_route_does_not_require_adapter_runtime_status(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_if_called():
        raise AssertionError("Playback status must not call detector adapter status")

    monkeypatch.setattr(
        "mockingbird.repository.product_repository.get_local_detector_status",
        fail_if_called,
    )
    monkeypatch.setattr(
        "mockingbird.repository.product_repository.get_megadetector_status",
        fail_if_called,
    )

    response = await client.get(f"/api/streams/{STREAM_ID}/playback")

    assert response.status_code == 200


async def test_playback_contract_creates_no_media_or_model_artifacts(
    client: httpx.AsyncClient,
    tmp_path: Path,
) -> None:
    response = await client.get(f"/api/streams/{STREAM_ID}/playback")

    assert response.status_code == 200
    artifact_extensions = {".onnx", ".pt", ".pth", ".weights", ".engine", ".ckpt"}
    assert [
        path
        for path in tmp_path.rglob("*")
        if path.is_file() and path.suffix.lower() in artifact_extensions
    ] == []
