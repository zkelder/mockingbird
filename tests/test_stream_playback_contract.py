from pathlib import Path

import httpx
import pytest

from mockingbird.api.main import (
    app,
    configure_repository,
    get_stream_local_mjpeg_bridge,
    get_stream_rtsp_mjpeg_bridge,
)
from mockingbird.api.schemas import SourceKind, SourceStatus
from mockingbird.playback import local_camera_bridge, rtsp_bridge
from mockingbird.repository.product_repository import ProductRepository
from mockingbird.storage.models import CameraSourceModel, StreamModel

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


async def product_counts(client: httpx.AsyncClient) -> dict[str, int]:
    responses = {
        "events": await client.get("/api/events"),
        "visits": await client.get("/api/visits"),
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
        lambda process: iter([b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpeg_frame]),
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
        lambda process: iter([b"--frame\r\nContent-Type: image/jpeg\r\n\r\njpeg"]),
    )
    await configure_local_usb_camera(client, device="/dev/video0")
    before = await product_counts(client)

    response = await get_stream_local_mjpeg_bridge(STREAM_ID)

    assert response.status_code == 200
    assert response.media_type.startswith("multipart/x-mixed-replace")
    assert response.headers["content-type"].startswith("multipart/x-mixed-replace")
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

    assert command[:13] == [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-f",
        "v4l2",
        "-input_format",
        "mjpeg",
        "-video_size",
        "640x480",
        "-framerate",
        "10",
        "-i",
    ]
    assert "/dev/video0" in command
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
