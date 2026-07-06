from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest

from mockingbird.api.main import (
    app,
    capture_stream_local_camera_frame,
    configure_repository,
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
from mockingbird.storage.models import CameraSourceModel, StreamModel

pytestmark = pytest.mark.anyio

SOURCE_ID = "source-backyard-demo"
STREAM_ID = "stream-backyard-feeder"


@pytest.fixture(autouse=True)
def isolated_repository(tmp_path: Path) -> ProductRepository:
    live_frame_cache.clear_all_frames()
    repository = ProductRepository(
        db_url=f"sqlite:///{tmp_path / 'mockingbird.sqlite3'}",
        media_root=tmp_path / "media",
    )
    configure_repository(repository)
    yield repository
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
    captured_at = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
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
    captured_at = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
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
) -> None:
    response = await client.patch(
        f"/api/sources/{SOURCE_ID}/provider-configuration",
        json={
            "provider_key": "local_usb",
            "config": {
                "live_stream_type": "local_usb",
                "local_camera_device": device,
                "local_camera_format": camera_format,
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
    framerate: str | None = None,
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
                "framerate": framerate,
            },
        },
    )
    assert response.status_code == 200


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
        lambda device, camera_format=None: started_devices.append(device) or fake_process,
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


async def test_playback_status_does_not_start_local_camera_bridge_process(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "mockingbird.playback.local_camera_bridge.is_ffmpeg_available",
        lambda: True,
    )

    def fail_if_started(device: str, camera_format: str | None = None):  # noqa: ANN202
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
    started: list[tuple[str, str | None, str | None, str | None]] = []

    def fake_start(
        camera_name: str,
        *,
        ffmpeg_binary_path: str | None = None,
        video_size: str | None = None,
        framerate: str | None = None,
    ) -> object:
        started.append((camera_name, ffmpeg_binary_path, video_size, framerate))
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
        framerate="10",
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
            "640x480",
            "10",
        )
    ]
    assert await product_counts(client) == before


async def test_windows_dshow_capture_frame_uses_fresh_live_cache_without_ffmpeg(
    client: httpx.AsyncClient,
    isolated_repository: ProductRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    live_frame = b"\xff\xd8cached-windows-live-frame\xff\xd9"

    def fail_if_one_shot_capture_runs(*args: object, **kwargs: object) -> bytes:
        raise AssertionError("Cached live frame capture must not start one-shot ffmpeg")

    monkeypatch.setattr(
        "mockingbird.api.main.windows_camera_bridge.capture_windows_dshow_frame",
        fail_if_one_shot_capture_runs,
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
        "Saved current live frame as local media only. It will not appear "
        "in Bird Log until you create/review activity."
    )
    assert body["capture_source"] == "live_frame_cache"
    assert body["live_frame_age_ms"] >= 0
    assert body["content_type"] == "image/jpeg"
    assert body["bytes_written"] == len(live_frame)
    assert body["creates_event"] is False
    assert body["creates_visit"] is False
    assert body["creates_truth"] is False
    assert body["creates_export"] is False

    media_response = await client.get(f"/api/media/{body['media_asset_id']}")
    assert media_response.status_code == 200
    media_asset = media_response.json()
    assert "playback_type=windows_dshow" in media_asset["notes"]
    saved_path = Path(media_asset["local_path"]).resolve()
    assert saved_path.is_relative_to(isolated_repository.media_root.resolve())
    assert saved_path.read_bytes() == live_frame

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
    captured_args: list[tuple[str, str | None, str | None, str | None]] = []

    def fake_capture(
        camera_name: str,
        *,
        ffmpeg_binary_path: str | None = None,
        video_size: str | None = None,
        framerate: str | None = None,
    ) -> bytes:
        captured_args.append((camera_name, ffmpeg_binary_path, video_size, framerate))
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
        framerate="10",
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
            "1280x720",
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


async def test_local_usb_capture_frame_uses_fresh_live_cache_without_ffmpeg(
    client: httpx.AsyncClient,
    isolated_repository: ProductRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    live_frame = b"\xff\xd8cached-local-live-frame\xff\xd9"

    def fail_if_one_shot_capture_runs(*args: object, **kwargs: object) -> bytes:
        raise AssertionError("Cached live frame capture must not start one-shot ffmpeg")

    monkeypatch.setattr(
        "mockingbird.api.main.local_camera_bridge.capture_local_camera_frame",
        fail_if_one_shot_capture_runs,
    )
    await configure_local_usb_camera(client, device="/dev/video0")
    live_frame_cache.store_latest_frame(STREAM_ID, live_frame)
    before = await product_counts(client)

    response = await client.post(f"/api/streams/{STREAM_ID}/local-camera/capture-frame")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "saved"
    assert body["message"] == (
        "Saved current live frame as local media only. It will not appear "
        "in Bird Log until you create/review activity."
    )
    assert body["capture_source"] == "live_frame_cache"
    assert body["live_frame_age_ms"] >= 0
    assert body["content_type"] == "image/jpeg"
    assert body["bytes_written"] == len(live_frame)
    assert body["creates_event"] is False
    assert body["creates_visit"] is False
    assert body["creates_truth"] is False
    assert body["creates_export"] is False

    media_response = await client.get(f"/api/media/{body['media_asset_id']}")
    assert media_response.status_code == 200
    media_asset = media_response.json()
    assert "playback_type=local_usb" in media_asset["notes"]
    saved_path = Path(media_asset["local_path"]).resolve()
    assert saved_path.is_relative_to(isolated_repository.media_root.resolve())
    assert saved_path.read_bytes() == live_frame

    after = await product_counts(client)
    assert after["media_assets"] == before["media_assets"] + 1
    for key in before:
        if key != "media_assets":
            assert after[key] == before[key]


async def test_local_usb_capture_frame_creates_one_media_asset_only(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    jpeg_frame = b"\xff\xd8captured-local-frame\xff\xd9"
    captured_args: list[tuple[str, str | None, str | None, str | None]] = []

    monkeypatch.setattr(
        "mockingbird.api.main.local_camera_bridge.local_camera_status",
        lambda **kwargs: "available",
    )

    def fake_capture(
        device: str,
        *,
        camera_format: str | None = None,
        video_size: str | None = None,
        input_frame_rate: str | None = None,
    ) -> bytes:
        captured_args.append((device, camera_format, video_size, input_frame_rate))
        return jpeg_frame

    monkeypatch.setattr(
        "mockingbird.api.main.local_camera_bridge.capture_local_camera_frame",
        fake_capture,
    )
    await configure_local_usb_camera(client, device="/dev/video0")
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
    assert captured_args == [("/dev/video0", "v4l2", None, None)]

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
        video_size="640x480",
        framerate="10",
    )

    assert command == [
        "/mnt/c/ffmpeg/bin/ffmpeg.exe",
        "-f",
        "dshow",
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
        video_size="1280x720",
        framerate="10",
    )

    assert command == [
        "/mnt/c/ffmpeg/bin/ffmpeg.exe",
        "-f",
        "dshow",
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
