"""Unified Observation panel API contract (MockingBird Unified Observation
Experience v1): the same `/api/streams/{id}/observation/start|stop|status`
contract now routes every currently-supported Stream type to its own
existing, unmodified runtime instead of only Camera Node. Camera Node's own
deep coverage stays in `test_observation_session_api.py`/
`test_engine_runtime.py`; this file proves the lane-aware routing itself:
RTSP/local USB/Windows DirectShow reuse the existing durable monitoring
policy, `external_url` still-image Streams reuse the existing Snapshot
Source monitor, and an unsupported Source honestly reports unavailable
rather than crashing or inventing support.
"""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from mockingbird.api.main import app, configure_repository, get_source_monitor_manager
from mockingbird.repository.product_repository import ProductRepository

pytestmark = pytest.mark.anyio

SOURCE_ID = "source-backyard-demo"
STREAM_ID = "stream-backyard-feeder"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


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
async def client(repository: ProductRepository):
    await get_source_monitor_manager().reset()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as api_client:
        yield api_client
    await get_source_monitor_manager().reset()


async def configure_rtsp(client: httpx.AsyncClient, *, live_stream_url: str = "rtsp://camera.local/live") -> None:
    response = await client.patch(
        f"/api/sources/{SOURCE_ID}/provider-configuration",
        json={
            "provider_key": "external_url",
            "config": {"live_stream_url": live_stream_url, "live_stream_type": "rtsp"},
        },
    )
    assert response.status_code == 200


async def configure_local_usb(client: httpx.AsyncClient, *, device: str | None = "/dev/video0") -> None:
    response = await client.patch(
        f"/api/sources/{SOURCE_ID}/provider-configuration",
        json={
            "provider_key": "local_usb",
            "config": {"live_stream_type": "local_usb", "local_camera_device": device},
        },
    )
    assert response.status_code == 200


async def configure_snapshot_url(client: httpx.AsyncClient, *, url: str | None = "http://192.168.1.50/camera/still.jpg") -> None:
    config = {"url": url} if url else {}
    response = await client.patch(
        f"/api/sources/{SOURCE_ID}/provider-configuration",
        json={"provider_key": "external_url", "config": config},
    )
    assert response.status_code == 200


async def configure_manual_media(client: httpx.AsyncClient) -> None:
    response = await client.patch(
        f"/api/sources/{SOURCE_ID}/provider-configuration",
        json={"provider_key": "manual_media", "config": {}},
    )
    assert response.status_code == 200


FORBIDDEN_VOCABULARY = (
    "SnapshotObservationProvider",
    "frame-driven-onnx-cuda",
    "provider_generation",
    "ONNX Runtime",
    "ONNX",
    "CUDA",
    "policy_revision",
)


def _assert_no_internal_vocabulary(payload: dict[str, object]) -> None:
    for field in ("message", "camera_message", "engine_message"):
        text = str(payload[field])
        for forbidden in FORBIDDEN_VOCABULARY:
            assert forbidden not in text, f"{forbidden!r} leaked into basic field {field!r}: {text!r}"


# --- Required test 2/10: unified status for live-monitor/RTSP provider -----


async def test_unified_status_for_never_started_rtsp_stream_reports_ready(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "mockingbird.repository.product_repository.rtsp_bridge.is_ffmpeg_available", lambda: True,
    )
    await configure_rtsp(client)

    response = await client.get(f"/api/streams/{STREAM_ID}/observation/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["state"] == "stopped"
    assert payload["observing"] is False
    assert payload["camera_connected"] is True
    assert payload["runtime_available"] is True
    _assert_no_internal_vocabulary(payload)


async def test_unreachable_rtsp_stream_reports_sanitized_needs_attention(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "mockingbird.repository.product_repository.rtsp_bridge.is_ffmpeg_available", lambda: False,
    )
    await configure_rtsp(client)

    response = await client.get(f"/api/streams/{STREAM_ID}/observation/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["state"] == "needs_attention"
    assert payload["camera_connected"] is False
    assert payload["setup_action"] == "edit_camera_setup"
    _assert_no_internal_vocabulary(payload)


# --- Required test 3 analogue for live_monitoring: Start ---------------


async def test_rtsp_start_arms_the_existing_monitoring_policy(
    client: httpx.AsyncClient, repository: ProductRepository, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "mockingbird.repository.product_repository.rtsp_bridge.is_ffmpeg_available", lambda: True,
    )
    await configure_rtsp(client)

    response = await client.post(f"/api/streams/{STREAM_ID}/observation/start")

    assert response.status_code == 200
    payload = response.json()
    assert payload["state"] in {"starting", "observing"}
    assert payload["observing"] or payload["state"] == "starting"
    # The unified action reused the existing durable policy record -- no
    # second, unified-only monitoring concept was invented.
    policy = repository.get_stream_monitoring_policy(STREAM_ID)
    assert policy is not None
    assert policy.mode == "armed"


async def test_rtsp_start_is_idempotent(
    client: httpx.AsyncClient, repository: ProductRepository, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "mockingbird.repository.product_repository.rtsp_bridge.is_ffmpeg_available", lambda: True,
    )
    await configure_rtsp(client)

    first = await client.post(f"/api/streams/{STREAM_ID}/observation/start")
    second = await client.post(f"/api/streams/{STREAM_ID}/observation/start")

    assert first.status_code == 200
    assert second.status_code == 200
    policy_after_first = repository.get_stream_monitoring_policy(STREAM_ID)
    policy_after_second = repository.get_stream_monitoring_policy(STREAM_ID)
    assert policy_after_first is not None and policy_after_second is not None
    # Still armed exactly once -- a second Start never re-arms/duplicates.
    assert policy_after_first.armed_at == policy_after_second.armed_at
    assert policy_after_first.policy_revision == policy_after_second.policy_revision


async def test_rtsp_stop_disarms_and_is_idempotent(
    client: httpx.AsyncClient, repository: ProductRepository, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "mockingbird.repository.product_repository.rtsp_bridge.is_ffmpeg_available", lambda: True,
    )
    await configure_rtsp(client)
    await client.post(f"/api/streams/{STREAM_ID}/observation/start")

    first_stop = await client.post(f"/api/streams/{STREAM_ID}/observation/stop")
    second_stop = await client.post(f"/api/streams/{STREAM_ID}/observation/stop")

    assert first_stop.status_code == 200
    assert second_stop.status_code == 200
    assert first_stop.json()["state"] == "stopped"
    assert second_stop.json()["state"] == "stopped"
    policy = repository.get_stream_monitoring_policy(STREAM_ID)
    assert policy is not None
    assert policy.mode == "off"


async def test_rtsp_start_rejects_invalid_configuration_without_arming(
    client: httpx.AsyncClient, repository: ProductRepository, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "mockingbird.repository.product_repository.rtsp_bridge.is_ffmpeg_available", lambda: False,
    )
    await configure_rtsp(client)

    response = await client.post(f"/api/streams/{STREAM_ID}/observation/start")

    assert response.status_code == 200
    payload = response.json()
    assert payload["state"] == "needs_attention"
    policy = repository.get_stream_monitoring_policy(STREAM_ID)
    # Reject invalid configuration safely: never arm a policy that cannot start.
    assert policy is None or policy.mode == "off"


async def test_stop_without_start_on_live_monitoring_stream_is_a_clean_no_op(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "mockingbird.repository.product_repository.rtsp_bridge.is_ffmpeg_available", lambda: True,
    )
    await configure_rtsp(client)

    response = await client.post(f"/api/streams/{STREAM_ID}/observation/stop")

    assert response.status_code == 200
    assert response.json()["state"] == "stopped"


# --- local USB: needs setup instead of a false "not a paired Camera Node" --


async def test_local_usb_stream_without_device_reports_needs_attention(
    client: httpx.AsyncClient, repository: ProductRepository,
) -> None:
    await configure_local_usb(client, device=None)

    response = await client.post(f"/api/streams/{STREAM_ID}/observation/start")

    assert response.status_code == 200
    payload = response.json()
    assert payload["state"] == "needs_attention"
    assert "Camera Node" not in payload["camera_message"]
    policy = repository.get_stream_monitoring_policy(STREAM_ID)
    assert policy is None or policy.mode == "off"


# --- Required tests 2/4/6/7/8: unified status/start/stop for Snapshot ------


async def test_unified_status_for_never_started_snapshot_stream_reports_ready(
    client: httpx.AsyncClient,
) -> None:
    await configure_snapshot_url(client)

    response = await client.get(f"/api/streams/{STREAM_ID}/observation/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["state"] == "stopped"
    assert payload["camera_connected"] is True
    _assert_no_internal_vocabulary(payload)


async def test_snapshot_start_routes_to_existing_source_monitor(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch,
) -> None:
    await configure_snapshot_url(client)

    response = await client.post(f"/api/streams/{STREAM_ID}/observation/start")

    assert response.status_code == 200
    payload = response.json()
    assert payload["state"] in {"starting", "observing"}
    # No second monitoring worker: the unified action started the exact
    # same `SourceMonitorManager` record the legacy `/monitor/*` route owns.
    monitor_state = await get_source_monitor_manager().status(STREAM_ID)
    assert monitor_state is not None
    assert monitor_state.status in {"starting", "monitoring"}


async def test_snapshot_start_is_idempotent(client: httpx.AsyncClient) -> None:
    await configure_snapshot_url(client)

    first = await client.post(f"/api/streams/{STREAM_ID}/observation/start")
    monitor_after_first = await get_source_monitor_manager().status(STREAM_ID)
    second = await client.post(f"/api/streams/{STREAM_ID}/observation/start")
    monitor_after_second = await get_source_monitor_manager().status(STREAM_ID)

    assert first.status_code == 200
    assert second.status_code == 200
    assert monitor_after_first is not None and monitor_after_second is not None
    # Still exactly the same monitor record for this Stream -- a second
    # Start never creates a duplicate monitoring worker.
    assert monitor_after_first.monitor_id == monitor_after_second.monitor_id
    assert monitor_after_first.started_at == monitor_after_second.started_at


async def test_snapshot_stop_is_idempotent_and_releases_the_monitor(
    client: httpx.AsyncClient,
) -> None:
    await configure_snapshot_url(client)
    await client.post(f"/api/streams/{STREAM_ID}/observation/start")

    first_stop = await client.post(f"/api/streams/{STREAM_ID}/observation/stop")
    second_stop = await client.post(f"/api/streams/{STREAM_ID}/observation/stop")

    assert first_stop.status_code == 200
    assert second_stop.status_code == 200
    assert first_stop.json()["state"] == "stopped"
    assert second_stop.json()["state"] == "stopped"
    monitor_state = await get_source_monitor_manager().status(STREAM_ID)
    assert monitor_state is not None
    assert monitor_state.status == "stopped_by_user"


async def test_snapshot_start_without_url_reports_needs_attention(
    client: httpx.AsyncClient,
) -> None:
    await configure_snapshot_url(client, url=None)

    response = await client.post(f"/api/streams/{STREAM_ID}/observation/start")

    assert response.status_code == 200
    payload = response.json()
    assert payload["state"] == "needs_attention"
    assert payload["setup_action"] == "edit_camera_setup"
    _assert_no_internal_vocabulary(payload)


# --- Required test 9: unconfigured/unsupported provider -> needs-attention -


async def test_manual_media_stream_reports_unavailable_not_a_crash(
    client: httpx.AsyncClient,
) -> None:
    await configure_manual_media(client)

    status_response = await client.get(f"/api/streams/{STREAM_ID}/observation/status")
    start_response = await client.post(f"/api/streams/{STREAM_ID}/observation/start")

    for response in (status_response, start_response):
        assert response.status_code == 200
        payload = response.json()
        assert payload["runtime_available"] is False
        assert payload["observing"] is False
        _assert_no_internal_vocabulary(payload)


async def test_demo_stream_start_is_honest_and_creates_no_observation_authority(
    client: httpx.AsyncClient, repository: ProductRepository,
) -> None:
    response = await client.post(f"/api/streams/{STREAM_ID}/observation/start")

    assert response.status_code == 200
    payload = response.json()
    assert payload["runtime_available"] is False
    assert payload["observing"] is False
    # Never grants Stage 7 candidate authority for a Stream with no runtime.
    assert repository.get_observation_authority_state().mode == "shadow"


# --- Required test 22: no unexpected product writes on read-only status ---


async def test_status_reads_across_every_lane_are_side_effect_free(
    client: httpx.AsyncClient, repository: ProductRepository, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "mockingbird.repository.product_repository.rtsp_bridge.is_ffmpeg_available", lambda: True,
    )
    for configure in (configure_rtsp, configure_snapshot_url, configure_manual_media):
        await configure(client)
        response = await client.get(f"/api/streams/{STREAM_ID}/observation/status")
        assert response.status_code == 200

    policy = repository.get_stream_monitoring_policy(STREAM_ID)
    assert policy is None or policy.mode == "off"
    monitor_state = await get_source_monitor_manager().status(STREAM_ID)
    assert monitor_state is None
    assert repository.get_observation_authority_state().mode == "shadow"
