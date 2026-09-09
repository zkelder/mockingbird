"""Product Operations & First-Observation Completion v1: cross-surface
camera-health honesty.

`test_dashboard_detector_health_honesty.py` already proves the Dashboard
correctly reports a camera-connected-but-detector-failed Camera Node Stream
as `camera_unavailable` with the real engine failure message. It never
constructs the sibling regression this milestone found and fixed: three
*other* real, reachable surfaces read the identical underlying `CameraHealth
Summary` computation (`_camera_health_summary_from_models`) but, before this
fix, never received the `engine_terminally_unavailable`/`engine_unavailable_
message` bridge the Dashboard alone was given -- so for the exact same
Stream at the exact same moment, `GET /api/streams/{id}/camera-health`
(and the Camera Configuration ("Edit camera setup") page it also backs) and
`GET /api/yard-map` both showed the calm, OK-bucket `stopped` state instead
of the real `camera_unavailable` alert, one click away from the Dashboard
tile that already, correctly, alarmed.

See `_resolve_engine_terminal_status`'s docstring (api/main.py) for the full
mechanism this test proves is now shared across all four surfaces.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from tests.conftest import LegacyAuthenticatedSyncTestClient

from mockingbird.api.main import app, configure_repository
from mockingbird.api.demo_data import STREAM_ID as DEMO_STREAM_ID
from mockingbird.observation.engine_runtime import ObservationEngineSessionStatus
from mockingbird.repository.product_repository import ProductRepository

_GPU_FAILURE_MESSAGE = (
    "This PC's GPU/graphics driver does not meet Observation Engine "
    "requirements (a compatible NVIDIA GPU and driver are required). "
    "(onnx_cuda_unavailable)"
)
_STALE_CAMERA_SUCCESS_TEXT = "Camera Node is paired and configured."


@pytest.fixture
def repository(tmp_path: Path) -> ProductRepository:
    repository = ProductRepository(
        db_url=f"sqlite:///{tmp_path / 'mockingbird.sqlite3'}",
        media_root=tmp_path / "media",
    )
    configure_repository(repository)
    yield repository
    configure_repository(None)


@pytest.fixture
def client(repository: ProductRepository) -> LegacyAuthenticatedSyncTestClient:
    return LegacyAuthenticatedSyncTestClient(app)


def _configure_camera_node(client: LegacyAuthenticatedSyncTestClient, stream_id: str = DEMO_STREAM_ID) -> None:
    response = client.patch(
        "/api/sources/source-backyard-demo/provider-configuration",
        json={"provider_key": "camera_node", "config": {}},
    )
    assert response.status_code == 200


class _FakeDetectorUnavailableEngineManager:
    """Identical fixture shape to `test_dashboard_detector_health_honesty
    .py`'s own -- camera connected/paired, Observation Engine detector/GPU
    load failed."""

    def status(self, stream_id: str) -> ObservationEngineSessionStatus | None:
        return ObservationEngineSessionStatus(
            stream_id=stream_id,
            state="error",
            observing=False,
            message=_GPU_FAILURE_MESSAGE,
            camera_connected=True,
            camera_message=_STALE_CAMERA_SUCCESS_TEXT,
            engine_available=False,
            engine_message=_GPU_FAILURE_MESSAGE,
        )


class _FakeHealthyEngineManager:
    def status(self, stream_id: str) -> ObservationEngineSessionStatus | None:
        return ObservationEngineSessionStatus(
            stream_id=stream_id,
            state="observing",
            observing=True,
            message="MockingBird is watching this camera for wildlife.",
            camera_connected=True,
            camera_message="Camera Node is paired and configured.",
            engine_available=True,
            engine_message="Observation Engine is running.",
        )


def test_camera_health_route_matches_dashboard_on_detector_failure(
    client: LegacyAuthenticatedSyncTestClient, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The core RED scenario for this surface: before the fix, this route
    showed `stopped` (calm) for the identical Stream/moment the Dashboard
    already, correctly, showed `camera_unavailable` (alert) for."""

    _configure_camera_node(client)
    monkeypatch.setattr(
        "mockingbird.api.main.get_observation_engine_session_manager",
        lambda: _FakeDetectorUnavailableEngineManager(),
    )

    dashboard = client.get("/api/dashboard/summary").json()
    dashboard_stream = next(s for s in dashboard["streams"] if s["stream_id"] == DEMO_STREAM_ID)
    assert dashboard_stream["camera_health"]["state"] == "camera_unavailable"

    camera_health = client.get(f"/api/streams/{DEMO_STREAM_ID}/camera-health").json()
    assert camera_health["health"]["state"] == "camera_unavailable", (
        "GET .../camera-health must agree with the Dashboard about a "
        "genuinely terminal engine failure, not show a stale calm state"
    )
    assert "GPU" in camera_health["health"]["message"] or "graphics driver" in camera_health["health"]["message"]
    assert _STALE_CAMERA_SUCCESS_TEXT not in camera_health["health"]["message"]


def test_camera_configuration_edit_route_matches_dashboard_on_detector_failure(
    client: LegacyAuthenticatedSyncTestClient, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The Camera Configuration ("Edit camera setup") page's own backing
    route -- reachable one click from the very Dashboard tile that already
    shows the real alert."""

    _configure_camera_node(client)
    monkeypatch.setattr(
        "mockingbird.api.main.get_observation_engine_session_manager",
        lambda: _FakeDetectorUnavailableEngineManager(),
    )

    configuration = client.get(f"/api/streams/{DEMO_STREAM_ID}/camera-configuration").json()
    assert configuration["health"]["state"] == "camera_unavailable"
    assert _STALE_CAMERA_SUCCESS_TEXT not in configuration["health"]["message"]


def test_yard_map_matches_dashboard_on_detector_failure(
    client: LegacyAuthenticatedSyncTestClient, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The Yard & Camera Map -- structurally has no message field at all
    (only `camera_health_state`), so this test only asserts the state
    itself, which is exactly the fact this surface previously got wrong."""

    _configure_camera_node(client)
    monkeypatch.setattr(
        "mockingbird.api.main.get_observation_engine_session_manager",
        lambda: _FakeDetectorUnavailableEngineManager(),
    )

    yard_map = client.get("/api/yard-map").json()
    stream_item = next(s for s in yard_map["streams"] if s["id"] == DEMO_STREAM_ID)
    assert stream_item["activity"]["camera_health_state"] == "camera_unavailable"


def test_all_three_surfaces_stay_unaffected_on_the_healthy_path(
    client: LegacyAuthenticatedSyncTestClient, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Positive control: a genuinely healthy, observing Camera Node Stream
    must not be alarmed by this fix on any of the three surfaces."""

    _configure_camera_node(client)
    monkeypatch.setattr(
        "mockingbird.api.main.get_observation_engine_session_manager",
        lambda: _FakeHealthyEngineManager(),
    )

    ok_states = {"healthy", "stopped", "starting"}

    camera_health = client.get(f"/api/streams/{DEMO_STREAM_ID}/camera-health").json()
    assert camera_health["health"]["state"] in ok_states

    configuration = client.get(f"/api/streams/{DEMO_STREAM_ID}/camera-configuration").json()
    assert configuration["health"]["state"] in ok_states

    yard_map = client.get("/api/yard-map").json()
    stream_item = next(s for s in yard_map["streams"] if s["id"] == DEMO_STREAM_ID)
    assert stream_item["activity"]["camera_health_state"] in ok_states
