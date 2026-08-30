"""Lane C Sparse-State Honesty & First-Hour Narrative Closure v1: Defect A.

`test_dashboard_observation_engine_truth.py` already proves a *camera/
transport*-level failure (bounded reconnect exhausted, `camera_connected=
False`) correctly raises Dashboard/`ProductHealth` attention. It never
constructs the sibling case this milestone closes: the Camera Node itself
stays paired/reachable (`camera_connected=True`) while the primary visual
Observation Engine detector/model/GPU fails to load
(`engine_available=False`, `state="error"`) -- exactly what
`_EngineSession._run_async` produces for a real `onnx_cuda_unavailable`/
missing-model-bundle failure (see `_engine_failure_message`,
`engine_runtime.py`).

Root cause (see docs/lane-c-sparse-state-honesty-first-hour-narrative-
closure-v1-report.md "Root cause"): `_dashboard_runtime_by_stream`
(api/main.py) computed
``engine_unavailable_message = engine_status.camera_message or engine_status.message``.
`camera_message` is set unconditionally, early, before the engine load is
even attempted ("Camera Node is paired and configured.") and is never
cleared when the *engine* (not the camera) subsequently fails -- so it is
always truthy and the `or` always picks it, discarding the real failure
text `engine_status.message` already correctly resolved to (see
`_EngineSession.snapshot`'s own "headline whichever subsystem is actually
blocking" contract). The per-camera `CameraHealthState` itself already
correctly left the OK bucket (`camera_unavailable`), so `ready`/
`needs_attention_count` were not a false-all-clear -- only the message text
was, self-contradicting "unavailable" state next to "paired and
configured" wording that reads as reassuring, not alarming.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from tests.conftest import LegacyAuthenticatedSyncTestClient

from mockingbird.api.main import app, configure_repository
from mockingbird.api.demo_data import STREAM_ID as DEMO_STREAM_ID
from mockingbird.observation.engine_runtime import ObservationEngineSessionStatus
from mockingbird.repository.product_repository import ProductRepository

# Realistic text `_engine_failure_message` actually produces for an
# unsupported-GPU failure (`_UNSUPPORTED_GPU_CODES`) -- not a fabricated
# string, so a test relying on it stays honest about what production code
# really says.
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
    """Camera Node is paired/reachable; the Observation Engine's own
    provider/detector load failed (missing model bundle, or -- as modeled
    here -- an unsupported/absent GPU). Mirrors exactly what a real
    `_EngineSession._run_async` produces: `camera_connected=True` (the
    pairing guard already passed and `_camera_message` was already set to
    the "paired and configured" success text before the engine load was
    even attempted), `state="error"`, `engine_available=False`, and
    `message`/`engine_message` both correctly holding the real failure
    text (`_EngineSession.snapshot`'s own dict-based precedence already
    picks `_engine_message` here, since `camera_connected` is True)."""

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
    """Negative control: camera connected, detector loaded, genuinely
    observing -- the ordinary healthy path must stay unaffected."""

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


def test_dashboard_flags_detector_unavailable_while_camera_stays_healthy(
    client: LegacyAuthenticatedSyncTestClient, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The core RED scenario: primary detector/GPU unavailable, camera
    otherwise paired and reachable. Must fail before the fix -- production
    code, before this milestone, surfaced `_STALE_CAMERA_SUCCESS_TEXT`
    here instead of `_GPU_FAILURE_MESSAGE`."""

    _configure_camera_node(client)
    monkeypatch.setattr(
        "mockingbird.api.main.get_observation_engine_session_manager",
        lambda: _FakeDetectorUnavailableEngineManager(),
    )

    dashboard = client.get("/api/dashboard/summary").json()
    stream_summary = next(s for s in dashboard["streams"] if s["stream_id"] == DEMO_STREAM_ID)
    camera_health_message = stream_summary["camera_health"]["message"]

    # The state itself already left the OK bucket pre-fix (this is not the
    # broken half) -- kept here as a same-response regression guard.
    assert stream_summary["camera_health"]["state"] == "camera_unavailable"

    # The broken half: the current engine/model failure must win over the
    # stale "paired and configured" success text that was set before the
    # engine load was even attempted.
    assert "GPU" in camera_health_message or "graphics driver" in camera_health_message, (
        f"expected the real detector/GPU failure text, got: {camera_health_message!r}"
    )
    assert _STALE_CAMERA_SUCCESS_TEXT not in camera_health_message, (
        "a stale camera-paired success message must never mask a current detector failure"
    )

    health = client.get("/api/product/health").json()
    assert health["ready"] is False
    assert health["cameras"]["needs_attention_count"] == 1
    assert _STALE_CAMERA_SUCCESS_TEXT not in health["message"]


def test_dashboard_healthy_detector_path_is_unaffected(
    client: LegacyAuthenticatedSyncTestClient, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Positive control: a genuinely healthy, observing Camera Node Stream
    must not be touched by the precedence fix."""

    _configure_camera_node(client)
    monkeypatch.setattr(
        "mockingbird.api.main.get_observation_engine_session_manager",
        lambda: _FakeHealthyEngineManager(),
    )

    dashboard = client.get("/api/dashboard/summary").json()
    stream_summary = next(s for s in dashboard["streams"] if s["stream_id"] == DEMO_STREAM_ID)
    assert stream_summary["camera_health"]["state"] in {"healthy", "stopped", "starting"}

    health = client.get("/api/product/health").json()
    assert health["ready"] is True
    assert health["cameras"]["needs_attention_count"] == 0
    assert health["message"] == "MockingBird is ready."


def test_camera_transport_failure_message_stays_distinct_from_detector_failure_message(
    client: LegacyAuthenticatedSyncTestClient, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A camera/transport-level failure (the Node itself unreachable) must
    keep reporting its own specific reason, never the detector/GPU wording
    -- the fix must not collapse the two distinct failure classes into one
    generic message in either direction. Reuses the exact terminally-
    unavailable-transport shape `test_dashboard_observation_engine_truth.py`
    already established, so this test fails loudly if a future change ever
    makes the two failure classes indistinguishable."""

    class _FakeCameraUnreachableEngineManager:
        def status(self, stream_id: str) -> ObservationEngineSessionStatus | None:
            return ObservationEngineSessionStatus(
                stream_id=stream_id,
                state="stopped",
                observing=False,
                message="Camera Node connection stopped: repeated failures.",
                camera_connected=False,
                camera_message="Camera Node connection stopped: repeated failures.",
                engine_available=True,
                engine_message="Ready",
                stopped_reason="camera_unavailable",
            )

    _configure_camera_node(client)
    monkeypatch.setattr(
        "mockingbird.api.main.get_observation_engine_session_manager",
        lambda: _FakeCameraUnreachableEngineManager(),
    )

    dashboard = client.get("/api/dashboard/summary").json()
    stream_summary = next(s for s in dashboard["streams"] if s["stream_id"] == DEMO_STREAM_ID)
    camera_health_message = stream_summary["camera_health"]["message"]

    assert stream_summary["camera_health"]["state"] == "camera_unavailable"
    assert "repeated failures" in camera_health_message
    assert "GPU" not in camera_health_message
    assert camera_health_message != _GPU_FAILURE_MESSAGE

    health = client.get("/api/product/health").json()
    assert health["ready"] is False
    assert health["cameras"]["needs_attention_count"] == 1


def test_acoustic_status_stays_independent_of_a_visual_detector_failure(
    client: LegacyAuthenticatedSyncTestClient, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Acoustic (BirdNET) health is a separate, optional surface
    (`ProductHealthAcousticSummary`) that must never be implied healthy or
    unhealthy by the primary visual detector's own state -- and must never
    itself be able to make `ready` false (acoustic is optional)."""

    _configure_camera_node(client)
    monkeypatch.setattr(
        "mockingbird.api.main.get_observation_engine_session_manager",
        lambda: _FakeDetectorUnavailableEngineManager(),
    )

    health = client.get("/api/product/health").json()
    # No microphone is configured for this fixture -- acoustic reports its
    # own honest, unrelated "not configured" state, never something that
    # reads as caused by the unrelated visual detector failure.
    assert health["acoustic"]["status"] == "not_configured"
    assert "GPU" not in health["acoustic"]["detail"]
    assert "detector" not in health["acoustic"]["detail"].lower()
    # The visual failure alone is sufficient to make the product not-ready;
    # acoustic's own independence does not change that top-level fact.
    assert health["ready"] is False
