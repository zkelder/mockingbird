"""API-surface tests for Acoustic / BirdNET Observation Foundation v1's
HTTP routes (`POST /api/media/{id}/analyze-audio`,
`GET /api/media/{id}/audio-analysis-runs`, `GET /api/birdnet/status`,
`/api/streams/{id}/audio-capture/*`). Mirrors
`tests/test_recorded_media_analysis_api.py`'s structure and division of
labor: the real detection/admission happy path (with an injected fake
recording) is already exercised thoroughly in `tests/test_acoustic_
ingest.py`; these tests only cover request/response wiring, error mapping,
and honest failure behavior with no test-only injection available at the
HTTP boundary (correctly so -- production code has no test hook here)."""

from __future__ import annotations

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


def _seed_audio_asset(
    repository: ProductRepository, *, media_asset_id: str, tmp_path: Path, content_type: str = "audio/wav",
) -> None:
    audio_path = tmp_path / "seeded.wav"
    audio_path.write_bytes(b"not a real decodable audio file, just bytes for a MediaAsset row")
    with repository.session_factory() as session:
        with session.begin():
            session.add(
                MediaAssetModel(
                    id=media_asset_id, source_id=SOURCE_ID, stream_id=STREAM_ID, filename=audio_path.name,
                    content_type=content_type, media_type="audio", local_path=str(audio_path),
                    original_filename=audio_path.name, file_size_bytes=audio_path.stat().st_size,
                    created_at=datetime.now(UTC), notes="API test fixture.",
                )
            )


async def test_analyze_recorded_audio_returns_404_for_an_unknown_media_asset(client: httpx.AsyncClient) -> None:
    response = await client.post("/api/media/media-does-not-exist/analyze-audio")
    assert response.status_code == 404


async def test_analyze_recorded_audio_returns_400_for_a_non_audio_media_asset(
    client: httpx.AsyncClient, isolated_repository: ProductRepository, tmp_path: Path,
) -> None:
    image_path = tmp_path / "photo.jpg"
    image_path.write_bytes(b"\xff\xd8\xff\xe0" + b"0" * 16 + b"\xff\xd9")
    with isolated_repository.session_factory() as session:
        with session.begin():
            session.add(
                MediaAssetModel(
                    id="media-image-not-audio", source_id=SOURCE_ID, stream_id=STREAM_ID, filename=image_path.name,
                    content_type="image/jpeg", media_type="image", local_path=str(image_path),
                    original_filename=image_path.name, file_size_bytes=image_path.stat().st_size,
                    created_at=datetime.now(UTC),
                )
            )

    response = await client.post("/api/media/media-image-not-audio/analyze-audio")
    assert response.status_code == 400


async def test_analyze_recorded_audio_reports_an_honest_decode_failure(
    client: httpx.AsyncClient, isolated_repository: ProductRepository, tmp_path: Path,
) -> None:
    """The seeded file is not real audio -- decode fails before BirdNET is
    ever reached, so this test needs no model/dependency at all and stays
    a fast, unconditional API-boundary test."""

    _seed_audio_asset(isolated_repository, media_asset_id="media-audio-under-test", tmp_path=tmp_path)

    response = await client.post("/api/media/media-audio-under-test/analyze-audio")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "failed"
    assert payload["visits_created"] == 0
    assert payload["creates_truth"] is False
    assert payload["error_code"] is not None


async def test_analyze_recorded_audio_response_never_leaks_a_local_filesystem_path(
    client: httpx.AsyncClient, isolated_repository: ProductRepository, tmp_path: Path,
) -> None:
    _seed_audio_asset(isolated_repository, media_asset_id="media-audio-under-test", tmp_path=tmp_path)

    response = await client.post("/api/media/media-audio-under-test/analyze-audio")
    assert str(tmp_path) not in response.text


async def test_analyze_recorded_audio_accepts_explicit_overrides(
    client: httpx.AsyncClient, isolated_repository: ProductRepository, tmp_path: Path,
) -> None:
    _seed_audio_asset(isolated_repository, media_asset_id="media-audio-under-test", tmp_path=tmp_path)

    response = await client.post(
        "/api/media/media-audio-under-test/analyze-audio",
        json={"min_confidence": 0.75, "pipeline_version": "acoustic-ingest-test"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["min_confidence"] == 0.75
    assert payload["pipeline_version"] == "acoustic-ingest-test"


async def test_analyze_recorded_audio_rejects_invalid_min_confidence(
    client: httpx.AsyncClient, isolated_repository: ProductRepository, tmp_path: Path,
) -> None:
    _seed_audio_asset(isolated_repository, media_asset_id="media-audio-under-test", tmp_path=tmp_path)

    response = await client.post(
        "/api/media/media-audio-under-test/analyze-audio", json={"min_confidence": 1.5},
    )
    assert response.status_code == 422  # rejected by the request schema's own Field(ge=0, le=1)


async def test_list_acoustic_analysis_runs_returns_404_for_an_unknown_media_asset(
    client: httpx.AsyncClient,
) -> None:
    response = await client.get("/api/media/media-does-not-exist/audio-analysis-runs")
    assert response.status_code == 404


async def test_list_acoustic_analysis_runs_reflects_a_failed_attempt(
    client: httpx.AsyncClient, isolated_repository: ProductRepository, tmp_path: Path,
) -> None:
    _seed_audio_asset(isolated_repository, media_asset_id="media-audio-under-test", tmp_path=tmp_path)

    await client.post("/api/media/media-audio-under-test/analyze-audio")
    response = await client.get("/api/media/media-audio-under-test/audio-analysis-runs")
    assert response.status_code == 200
    runs = response.json()
    assert len(runs) == 1
    assert runs[0]["media_asset_id"] == "media-audio-under-test"
    assert runs[0]["status"] == "failed"


async def test_birdnet_status_is_side_effect_free_and_bounded(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/birdnet/status")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] in ("available", "unavailable")
    assert isinstance(payload["runtime_available"], bool)
    assert payload["detail"]


class TestMicrophoneCaptureRoutes:
    async def test_status_for_unconfigured_stream_shows_no_consent(
        self, client: httpx.AsyncClient,
    ) -> None:
        response = await client.get(f"/api/streams/{STREAM_ID}/audio-capture/status")
        assert response.status_code == 200
        payload = response.json()
        assert payload["consent_granted"] is False
        assert payload["is_running"] is False

    async def test_start_refuses_without_explicit_consent(self, client: httpx.AsyncClient) -> None:
        response = await client.post(f"/api/streams/{STREAM_ID}/audio-capture/start")
        assert response.status_code == 403

    async def test_start_refuses_for_unknown_stream(self, client: httpx.AsyncClient) -> None:
        response = await client.post("/api/streams/stream-does-not-exist/audio-capture/start")
        assert response.status_code == 404

    async def test_consent_and_device_are_read_from_the_generic_provider_configuration(
        self, client: httpx.AsyncClient,
    ) -> None:
        """Acoustic / BirdNET Observation Foundation v1 deliberately reuses
        the existing, generic Source provider-configuration mechanism --
        no new audio-specific consent persistence path."""

        config_response = await client.patch(
            f"/api/sources/{SOURCE_ID}/provider-configuration",
            json={"provider_key": "microphone", "config": {"device": "default", "capture_consent": "true"}},
        )
        assert config_response.status_code == 200

        status_response = await client.get(f"/api/streams/{STREAM_ID}/audio-capture/status")
        payload = status_response.json()
        assert payload["consent_granted"] is True
        assert payload["device"] == "default"

    async def test_start_refuses_without_a_configured_device_even_with_consent(
        self, client: httpx.AsyncClient,
    ) -> None:
        await client.patch(
            f"/api/sources/{SOURCE_ID}/provider-configuration",
            json={"provider_key": "microphone", "config": {"capture_consent": "true"}},
        )
        response = await client.post(f"/api/streams/{STREAM_ID}/audio-capture/start")
        assert response.status_code == 400

    async def test_stop_is_a_no_op_for_a_never_started_stream(self, client: httpx.AsyncClient) -> None:
        response = await client.post(f"/api/streams/{STREAM_ID}/audio-capture/stop")
        assert response.status_code == 200
        assert response.json()["is_running"] is False
