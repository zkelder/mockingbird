from __future__ import annotations

from httpx import AsyncClient, ASGITransport
import pytest

from mockingbird.api.main import app, get_source_monitor_manager

from mockingbird.monitoring import (
    MonitorMotionResult,
    MonitorSnapshotResult,
    SourceMonitorManager,
    SourceMonitorOptions,
)
from mockingbird.observation import (
    ObservationEngineRegistry,
    SnapshotObservationProvider,
)


pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


async def test_snapshot_provider_wraps_existing_monitor_as_evidence_only() -> None:
    saved_media_ids = ["media-before"]

    async def capture_snapshot(_source_id: str, _stream_id: str) -> MonitorSnapshotResult:
        saved_media_ids.append("media-snapshot")
        return MonitorSnapshotResult(
            media_asset_id="media-snapshot",
            status="saved",
            message="Saved snapshot.",
        )

    async def list_saved_images(_source_id: str, _stream_id: str) -> list[str]:
        return list(saved_media_ids)

    async def evaluate_saved_media(
        _stream_id: str,
        media_asset_ids: list[str],
        _create_review_activity: bool,
    ) -> MonitorMotionResult:
        return MonitorMotionResult(
            activity_detected=True,
            media_asset_ids=media_asset_ids,
            review_activity_available=True,
            best_snapshot_media_asset_id="media-snapshot",
        )

    provider = SnapshotObservationProvider(
        SourceMonitorManager(
            capture_snapshot=capture_snapshot,
            list_saved_images=list_saved_images,
            evaluate_saved_media=evaluate_saved_media,
        )
    )
    await provider.start(
        source_id="source-1",
        stream_id="stream-1",
        options=SourceMonitorOptions(max_runtime_seconds=60, max_snapshots=3),
        autostart=False,
    )

    result = await provider.observe_one_tick_for_tests("stream-1")

    assert result.provider_id == "snapshot"
    assert [frame.media_asset_id for frame in result.frame_packets] == ["media-snapshot"]
    assert [item.media_asset_id for item in result.evidence_candidates] == [
        "media-before",
        "media-snapshot",
    ]
    assert len(result.visit_proposals) == 1
    assert result.detection_observations == ()
    assert result.track_updates == ()
    assert result.creates_truth is False


async def test_snapshot_provider_capabilities_and_health_are_honest() -> None:
    async def capture_snapshot(_source_id: str, _stream_id: str) -> MonitorSnapshotResult:
        raise AssertionError("Health must not capture a snapshot.")

    async def list_saved_images(_source_id: str, _stream_id: str) -> list[str]:
        return []

    async def evaluate_saved_media(
        _stream_id: str,
        _media_asset_ids: list[str],
        _create_review_activity: bool,
    ) -> MonitorMotionResult:
        raise AssertionError("Health must not evaluate motion.")

    provider = SnapshotObservationProvider(
        SourceMonitorManager(
            capture_snapshot=capture_snapshot,
            list_saved_images=list_saved_images,
            evaluate_saved_media=evaluate_saved_media,
        )
    )

    health = await provider.health(stream_id="stream-1")

    assert provider.provider_id == "snapshot"
    assert provider.capabilities.timer_driven is True
    assert provider.capabilities.emits_frame_packets is True
    assert provider.capabilities.emits_detection_observations is False
    assert provider.capabilities.emits_track_updates is False
    assert health.state == "idle"
    assert health.healthy is True


async def test_registry_reports_the_active_provider_without_monitoring_work() -> None:
    await get_source_monitor_manager().reset()
    try:
        status = await ObservationEngineRegistry([get_source_monitor_manager()]).status()

        assert status.active_provider_id == "snapshot"
        assert status.provider.health.state == "idle"
        assert status.creates_truth is False
    finally:
        await get_source_monitor_manager().reset()


async def test_observation_engine_status_is_read_only_and_names_snapshot_provider() -> None:
    await get_source_monitor_manager().reset()
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.get("/api/observation-engine/status")

        assert response.status_code == 200
        payload = response.json()
        assert payload["active_provider_id"] == "snapshot"
        assert payload["provider_id"] == "snapshot"
        assert payload["capabilities"]["timer_driven"] is True
        assert payload["capabilities"]["emits_detection_observations"] is False
        assert payload["health"]["state"] == "idle"
        assert payload["creates_truth"] is False
    finally:
        await get_source_monitor_manager().reset()
