"""API-surface tests for Offline / Recorded Observation Ingest v1's HTTP
routes (`POST /api/media/{id}/analyze-recorded`,
`GET /api/media/{id}/analysis-runs`). The real detection/tracking/assembly/
admission happy path is already exercised thoroughly, with an injected fake
detector, in `tests/test_offline_ingest.py`; these tests only cover request/
response wiring, error mapping, and the honest "no model bundle configured"
failure -- no real CUDA/model bundle is available in this environment,
matching `tests/test_observation_session_api.py`'s identical, established
precedent for the live `/observation/start` route.
"""

from __future__ import annotations

import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from mockingbird.api.main import app, configure_repository
from mockingbird.repository.product_repository import MediaAssetModel, ProductRepository
from tests.conftest import LegacyAuthenticatedTestClient

pytestmark = pytest.mark.anyio

STREAM_ID = "stream-backyard-feeder"
SOURCE_ID = "source-backyard-demo"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture(autouse=True)
def isolated_repository(tmp_path: Path) -> ProductRepository:
    repository = ProductRepository(db_url=f"sqlite:///{tmp_path / 'mockingbird.sqlite3'}", media_root=tmp_path / "media")
    configure_repository(repository)
    yield repository
    configure_repository(None)


@pytest.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with LegacyAuthenticatedTestClient(transport=transport, base_url="http://testserver") as api_client:
        yield api_client


def _has_real_ffmpeg_suite() -> bool:
    return shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


def _seed_video_asset(repository: ProductRepository, *, media_asset_id: str, tmp_path: Path) -> None:
    video_path = tmp_path / "seeded.mp4"
    if _has_real_ffmpeg_suite():
        subprocess.run(
            [
                "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                "-f", "lavfi", "-i", "color=c=blue:s=64x64:d=2", "-c:v", "libx264",
                "-pix_fmt", "yuv420p", str(video_path),
            ],
            check=True, timeout=30, capture_output=True,
        )
    else:
        video_path.write_bytes(b"not a real decodable video, just bytes for a MediaAsset row")
    with repository.session_factory() as session:
        with session.begin():
            session.add(
                MediaAssetModel(
                    id=media_asset_id, source_id=SOURCE_ID, stream_id=STREAM_ID, filename=video_path.name,
                    content_type="video/mp4", media_type="video", local_path=str(video_path),
                    original_filename=video_path.name, file_size_bytes=video_path.stat().st_size,
                    created_at=datetime.now(UTC), notes="API test fixture.",
                )
            )


async def test_analyze_recorded_media_returns_404_for_an_unknown_media_asset(client: httpx.AsyncClient) -> None:
    response = await client.post("/api/media/media-does-not-exist/analyze-recorded")
    assert response.status_code == 404


async def test_analyze_recorded_media_returns_400_for_a_non_video_media_asset(
    client: httpx.AsyncClient, isolated_repository: ProductRepository, tmp_path: Path,
) -> None:
    image_path = tmp_path / "photo.jpg"
    image_path.write_bytes(b"\xff\xd8\xff\xe0" + b"0" * 16 + b"\xff\xd9")
    with isolated_repository.session_factory() as session:
        with session.begin():
            session.add(
                MediaAssetModel(
                    id="media-image-not-video", source_id=SOURCE_ID, stream_id=STREAM_ID, filename=image_path.name,
                    content_type="image/jpeg", media_type="image", local_path=str(image_path),
                    original_filename=image_path.name, file_size_bytes=image_path.stat().st_size,
                    created_at=datetime.now(UTC),
                )
            )

    response = await client.post("/api/media/media-image-not-video/analyze-recorded")
    assert response.status_code == 400


async def test_analyze_recorded_media_reports_an_honest_engine_unavailable_failure(
    client: httpx.AsyncClient, isolated_repository: ProductRepository, tmp_path: Path,
) -> None:
    """No real ONNX-CUDA model bundle is configured in this test
    environment -- exactly like `test_observation_session_api.py`'s live
    `/observation/start` route, this must report a bounded, honest failure,
    never a 500 crash and never a fabricated Visit."""

    _seed_video_asset(isolated_repository, media_asset_id="media-video-under-test", tmp_path=tmp_path)

    response = await client.post("/api/media/media-video-under-test/analyze-recorded")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "failed"
    assert payload["visits_created"] == 0
    assert payload["creates_truth"] is False
    # Authority must never be left active after an engine-load failure.
    assert isolated_repository.get_observation_authority_state(stream_id=STREAM_ID).mode == "shadow"


async def test_analyze_recorded_media_response_never_leaks_a_local_filesystem_path(
    client: httpx.AsyncClient, isolated_repository: ProductRepository, tmp_path: Path,
) -> None:
    _seed_video_asset(isolated_repository, media_asset_id="media-video-under-test", tmp_path=tmp_path)

    response = await client.post("/api/media/media-video-under-test/analyze-recorded")
    assert str(tmp_path) not in response.text


async def test_list_recorded_media_analysis_runs_returns_404_for_an_unknown_media_asset(
    client: httpx.AsyncClient,
) -> None:
    response = await client.get("/api/media/media-does-not-exist/analysis-runs")
    assert response.status_code == 404


async def test_list_recorded_media_analysis_runs_reflects_a_completed_attempt(
    client: httpx.AsyncClient, isolated_repository: ProductRepository, tmp_path: Path,
) -> None:
    _seed_video_asset(isolated_repository, media_asset_id="media-video-under-test", tmp_path=tmp_path)

    await client.post("/api/media/media-video-under-test/analyze-recorded")
    response = await client.get("/api/media/media-video-under-test/analysis-runs")
    assert response.status_code == 200
    runs = response.json()
    assert len(runs) == 1
    assert runs[0]["media_asset_id"] == "media-video-under-test"
    assert runs[0]["status"] == "failed"
    assert runs[0]["error_code"] == "engine_unavailable"


async def test_analyze_recorded_media_accepts_explicit_sampling_overrides(
    client: httpx.AsyncClient, isolated_repository: ProductRepository, tmp_path: Path,
) -> None:
    _seed_video_asset(isolated_repository, media_asset_id="media-video-under-test", tmp_path=tmp_path)

    response = await client.post(
        "/api/media/media-video-under-test/analyze-recorded",
        json={"sample_fps": 1.0, "max_frames": 10, "pipeline_version": "offline-video-ingest-test"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["sample_fps"] == 1.0
    assert payload["pipeline_version"] == "offline-video-ingest-test"
