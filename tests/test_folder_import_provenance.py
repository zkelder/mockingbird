"""v0.1 Acquisition/Ingest Interoperability Closure v1: folder-import
provenance regressions ("II.9 Camera-trap / media ingest", "II.10 Offline
vs monitoring coverage", "II.11 Imported timestamps", "II.12 Duplicate
protection", "II.15 Source-resolution evidence"). Reuses the exact fixture/
helper conventions tests/test_folder_import_media_assets.py already
establishes. Real image (Pillow-built, real EXIF) and real video (ffmpeg-
generated) files -- no network access, no live Camera Node.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import httpx
import pytest
from PIL import Image

from mockingbird.api.main import app, configure_repository
from mockingbird.repository.product_repository import ProductRepository
from mockingbird.storage.models import MonitoringExposureIntervalModel
from tests.conftest import LegacyAuthenticatedTestClient

pytestmark = pytest.mark.anyio

SOURCE_ID = "source-backyard-demo"
STREAM_ID = "stream-backyard-feeder"
FEEDER_ZONE_ID = "zone-feeder"


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


async def configure_folder_source(
    client: httpx.AsyncClient,
    folder: Path | str,
    *,
    allowed_extensions: str,
    default_stream_id: str = STREAM_ID,
    default_zone_id: str = FEEDER_ZONE_ID,
) -> None:
    response = await client.patch(
        f"/api/sources/{SOURCE_ID}/provider-configuration",
        json={
            "provider_key": "folder_import_future",
            "config": {
                "folder_path": str(folder),
                "allowed_extensions": allowed_extensions,
                "default_stream_id": default_stream_id,
                "default_zone_id": default_zone_id,
            },
        },
    )
    assert response.status_code == 200


async def import_folder(client: httpx.AsyncClient, payload: dict | None = None) -> httpx.Response:
    return await client.post(f"/api/sources/{SOURCE_ID}/folder-import", json=payload or {})


async def media_by_id(client: httpx.AsyncClient) -> dict[str, dict]:
    response = await client.get("/api/media")
    assert response.status_code == 200
    return {item["id"]: item for item in response.json()}


def _write_exif_image(path: Path, *, exif_datetime: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (8, 8), color="green")
    exif = image.getexif()
    exif.get_ifd(0x8769)[36867] = exif_datetime
    image.save(path, format="JPEG", exif=exif)


def _has_real_ffmpeg_suite() -> bool:
    return shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


def _write_real_video(path: Path, *, duration_seconds: int = 2, size: str = "320x240") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-f", "lavfi", "-i", f"color=c=blue:s={size}:d={duration_seconds}",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", str(path),
        ],
        check=True,
        timeout=30,
        capture_output=True,
    )


# -- II.11: capture timestamp stays separate from import time ---------------


async def test_exif_capture_timestamp_is_recorded_separately_from_import_time(
    client: httpx.AsyncClient, tmp_path: Path
) -> None:
    folder = tmp_path / "trailcam"
    _write_exif_image(folder / "cardinal.jpg", exif_datetime="2026:03:14 07:15:30")
    await configure_folder_source(client, folder, allowed_extensions="jpg")

    response = await import_folder(client)
    assert response.status_code == 201
    [imported] = response.json()["imported"]

    assets = await media_by_id(client)
    asset = assets[imported["media_asset_id"]]
    assert asset["captured_at"] is not None
    assert asset["captured_at"].startswith("2026-03-14T07:15:30")
    # Import time (created_at) is real "now," genuinely different from the
    # EXIF capture moment above -- never collapsed into one timestamp.
    assert not asset["created_at"].startswith("2026-03-14T07:15:30")


async def test_image_with_no_exif_leaves_captured_at_honestly_unknown(
    client: httpx.AsyncClient, tmp_path: Path
) -> None:
    folder = tmp_path / "trailcam"
    folder.mkdir(parents=True)
    Image.new("RGB", (8, 8), color="red").save(folder / "no_exif.jpg", format="JPEG")
    await configure_folder_source(client, folder, allowed_extensions="jpg")

    response = await import_folder(client)
    assert response.status_code == 201
    [imported] = response.json()["imported"]

    assets = await media_by_id(client)
    assert assets[imported["media_asset_id"]]["captured_at"] is None


# -- II.9 / II.15: video enters the ordinary pipeline with truthful metadata -


@pytest.mark.skipif(not _has_real_ffmpeg_suite(), reason="ffmpeg/ffprobe not available")
async def test_video_import_records_truthful_duration_and_resolution(
    client: httpx.AsyncClient, tmp_path: Path
) -> None:
    folder = tmp_path / "trailcam"
    _write_real_video(folder / "clip.mp4", duration_seconds=2, size="320x240")
    await configure_folder_source(client, folder, allowed_extensions="mp4")

    response = await import_folder(client)
    assert response.status_code == 201
    result = response.json()
    assert result["total_imported"] == 1
    [imported] = result["imported"]

    assets = await media_by_id(client)
    asset = assets[imported["media_asset_id"]]
    assert asset["media_type"] == "video"
    # Truthful, ffprobe-observed facts -- never a marketing/assumed
    # resolution (see "II.15 Source-resolution evidence").
    assert asset["duration_seconds"] == pytest.approx(2.0, abs=0.2)
    assert asset["image_width"] == 320
    assert asset["image_height"] == 240


@pytest.mark.skipif(not _has_real_ffmpeg_suite(), reason="ffmpeg/ffprobe not available")
async def test_video_and_image_can_be_imported_together_as_ordinary_media_assets(
    client: httpx.AsyncClient, tmp_path: Path
) -> None:
    folder = tmp_path / "trailcam"
    _write_exif_image(folder / "bird.jpg", exif_datetime="2026:05:01 06:00:00")
    _write_real_video(folder / "clip.mp4", duration_seconds=1)
    await configure_folder_source(client, folder, allowed_extensions="jpg,mp4")

    response = await import_folder(client)
    assert response.status_code == 201
    result = response.json()
    assert result["total_imported"] == 2
    assert result["creates_events"] is False
    assert result["creates_visits"] is False
    assert result["creates_truth"] is False


async def test_malformed_video_still_imports_cleanly_with_honestly_absent_metadata(
    client: httpx.AsyncClient, tmp_path: Path
) -> None:
    # v0.1 Acquisition/Ingest Interoperability Closure v1 ("II.22.21/22
    # malformed video / unsupported codec fail cleanly"): a corrupt/
    # unparseable file with a video extension must never break the whole
    # import batch, and must never fabricate duration/resolution it could
    # not actually observe. Deliberately does not require real ffmpeg/
    # ffprobe to be installed -- this proves the *bounded-failure*
    # behavior, not the (separately tested) real-ffprobe success path.
    folder = tmp_path / "trailcam"
    folder.mkdir(parents=True)
    (folder / "corrupt.mp4").write_bytes(b"this is not a real video file, just noise")
    _write_exif_image(folder / "good.jpg", exif_datetime="2026:07:04 09:00:00")
    await configure_folder_source(client, folder, allowed_extensions="jpg,mp4")

    response = await import_folder(client)

    assert response.status_code == 201
    result = response.json()
    # Both files import as ordinary MediaAssets -- a decode/probe failure
    # is not a reason to skip or reject the file itself.
    assert result["total_imported"] == 2
    assert result["skipped"] == []

    assets = await media_by_id(client)
    corrupt_asset = next(a for a in assets.values() if a["original_filename"] == "corrupt.mp4")
    assert corrupt_asset["media_type"] == "video"
    # Honestly absent, never a fabricated 0 or guessed resolution.
    assert corrupt_asset["duration_seconds"] is None
    assert corrupt_asset["image_width"] is None
    assert corrupt_asset["image_height"] is None


# -- II.10: importing media never fabricates continuous monitoring coverage -


@pytest.mark.skipif(not _has_real_ffmpeg_suite(), reason="ffmpeg/ffprobe not available")
async def test_importing_a_video_never_creates_monitoring_exposure_history(
    client: httpx.AsyncClient,
    isolated_repository: ProductRepository,
    tmp_path: Path,
) -> None:
    folder = tmp_path / "trailcam"
    _write_real_video(folder / "clip.mp4", duration_seconds=5)
    await configure_folder_source(client, folder, allowed_extensions="mp4")

    response = await import_folder(client)
    assert response.status_code == 201
    assert response.json()["total_imported"] == 1

    # The critical invariant: importing a recorded clip -- even one with a
    # known, honestly-recorded duration -- must never imply "this camera
    # monitored the yard continuously" (see "II.10 Offline vs monitoring
    # coverage"). MonitoringExposureIntervalModel is the sole durable
    # ledger Today's coverage/maturity math reads; it must stay untouched.
    with isolated_repository.session_factory() as session:
        exposure_rows = session.query(MonitoringExposureIntervalModel).count()
    assert exposure_rows == 0


# -- II.12: content-hash duplicate protection --------------------------------


async def test_reimporting_an_identical_file_under_a_new_name_is_detected_as_a_duplicate(
    client: httpx.AsyncClient, tmp_path: Path
) -> None:
    folder = tmp_path / "trailcam"
    _write_exif_image(folder / "original.jpg", exif_datetime="2026:06:01 08:00:00")
    await configure_folder_source(client, folder, allowed_extensions="jpg")

    first = await import_folder(client)
    assert first.status_code == 201
    assert first.json()["total_imported"] == 1

    # A byte-identical copy under a *different* relative path/name -- the
    # pre-existing path+size+mtime signal alone would not catch this; the
    # new content-hash check must.
    shutil.copyfile(folder / "original.jpg", folder / "renamed_copy.jpg")

    second = await import_folder(client)
    assert second.status_code == 201
    result = second.json()
    assert result["total_imported"] == 0
    # Both the original (path+size+mtime match) and the renamed byte-
    # identical copy (content-hash match) are correctly recognized as
    # already imported.
    assert len(result["skipped"]) == 2
    assert {"original.jpg", "renamed_copy.jpg"} == {item["relative_path"] for item in result["skipped"]}
    assert all(item["reason"] == "already_imported" for item in result["skipped"])


async def test_reimporting_the_same_folder_unchanged_is_fully_idempotent(
    client: httpx.AsyncClient, tmp_path: Path
) -> None:
    folder = tmp_path / "trailcam"
    _write_exif_image(folder / "cardinal.jpg", exif_datetime="2026:03:14 07:15:30")
    await configure_folder_source(client, folder, allowed_extensions="jpg")

    first = await import_folder(client)
    assert first.json()["total_imported"] == 1

    second = await import_folder(client)
    assert second.status_code == 201
    assert second.json()["total_imported"] == 0

    assets = await media_by_id(client)
    assert len(assets) == 1
