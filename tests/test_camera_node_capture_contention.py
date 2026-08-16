"""Focused reproduction + regression coverage for physical-camera ownership.

Context: the preserved outage log
(node.log.outage-20260814-preserved) recorded 739 real, unhandled
``ValueError: camera_busy`` crashes, all from the exact same call chain:
``analysis_stream`` -> ``analysis_parts`` -> ``capture_analysis_frame`` ->
``PiCamera2Provider.snapshot``'s bounded lock timeout. The provider's
exclusive-ownership lock (``PiCamera2Provider._lock``) was already working
as designed -- bounded wait, then a deliberate ``camera_busy`` signal,
always released via ``finally`` -- but the analysis multipart stream never
caught that expected, transient signal, so it blew up the whole ASGI
response instead of just missing one frame.

These tests prove:
  1. the lock genuinely serializes concurrent physical-camera access and is
     always released (success, exception, or client disconnect);
  2. the analysis stream survives that same expected contention without an
     unhandled ASGI exception, matching how ``CameraNodeAnalysisSource``
     already tolerates sequence gaps as a normal, non-fatal signal;
  3. one narrower gap -- the warm-profile background proof thread touching
     the camera without the same lock -- is closed too.
"""

from __future__ import annotations

import asyncio
import threading

import pytest
from fastapi import HTTPException

from mockingbird_node.app import create_node_app
from mockingbird_node.config import CameraNodeConfig
from mockingbird_node.providers import (
    NodeCamera,
    NodeCaptureProfile,
    PiCamera2Provider,
)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


_JPEG = b"\xff\xd8\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x11\x00\xff\xd9"


def _node_config(tmp_path, *, provider_key: str = "picamera2") -> CameraNodeConfig:
    return CameraNodeConfig(
        "Test Node", "127.0.0.1", 8787, provider_key, None,
        1_500_000, 1920, 1440, 60, 2, testing=True,
        evidence_max_image_bytes=16_000_000,
        evidence_max_image_width=10_000,
        evidence_max_image_height=8_000,
        pairing_state_path=tmp_path / "pairing.json",
    )


class _ConnectedRequest:
    async def is_disconnected(self) -> bool:
        return False


# ---------------------------------------------------------------------------
# Provider-layer: the exclusive lock itself.
# ---------------------------------------------------------------------------


def test_picamera2_lock_serializes_concurrent_snapshot_and_releases_on_success(
    tmp_path,
) -> None:
    """Two real, concurrently-running snapshot() calls must never both touch
    the camera at once; the loser gets a bounded camera_busy, and the lock
    must still be free afterward."""

    holder_is_in_configure = threading.Event()
    release_holder = threading.Event()

    class Camera:
        def __init__(self) -> None:
            self.stopped = self.closed = False

        def create_still_configuration(self, **kwargs):
            return kwargs

        def configure(self, _configuration):
            holder_is_in_configure.set()
            release_holder.wait(timeout=2)

        def start(self):
            return None

        def capture_array(self, *_a, **_k):
            return object()

        def stop(self):
            self.stopped = True

        def close(self):
            self.closed = True

    class Picamera2:
        cameras: list[Camera] = []

        @staticmethod
        def global_camera_info():
            return [{}]

        def __new__(cls, _index):
            camera = Camera()
            cls.cameras.append(camera)
            return camera

    class Encoder:
        def imencode(self, _suffix, _frame, *_a):
            return True, bytearray(_JPEG)

    provider = PiCamera2Provider(
        _node_config(tmp_path),
        module=type("Module", (), {"Picamera2": Picamera2}),
        cv2_module=Encoder(),
    )

    results: dict[str, object] = {}

    def hold_the_camera() -> None:
        try:
            results["holder"] = provider.snapshot("picamera2-camera-0")
        except BaseException as error:  # pragma: no cover - failure path only
            results["holder"] = error

    holder = threading.Thread(target=hold_the_camera, daemon=True)
    holder.start()
    assert holder_is_in_configure.wait(timeout=2), "holder never reached the camera"

    # A second, concurrent request for the *same* physical camera must be
    # rejected quickly and cleanly -- never allowed to also touch the camera.
    with pytest.raises(ValueError, match="camera_busy"):
        provider.snapshot("picamera2-camera-0")
    assert len(Picamera2.cameras) == 1, "a second live camera session was created"

    release_holder.set()
    holder.join(timeout=2)
    assert not holder.is_alive()
    assert not isinstance(results.get("holder"), BaseException)

    # The lock must be free again: capture remains usable.
    third = provider.snapshot("picamera2-camera-0")
    assert (third.image if hasattr(third, "image") else third).startswith(b"\xff\xd8")
    provider.close()


def test_picamera2_lock_releases_after_capture_exception(tmp_path) -> None:
    """An unexpected mid-capture failure must not leave the camera locked."""

    class Camera:
        def __init__(self) -> None:
            self.stopped = self.closed = False

        def create_still_configuration(self, **kwargs):
            return kwargs

        def configure(self, _configuration):
            return None

        def start(self):
            return None

        def capture_array(self, *_a, **_k):
            # Only the very first (soon-to-be-discarded) camera session
            # fails; a freshly reinitialized one must work normally.
            if self is Picamera2.cameras[0]:
                raise RuntimeError("simulated local capture failure")
            return object()

        def stop(self):
            self.stopped = True

        def close(self):
            self.closed = True

    class Picamera2:
        cameras: list[Camera] = []

        @staticmethod
        def global_camera_info():
            return [{}]

        def __new__(cls, _index):
            camera = Camera()
            cls.cameras.append(camera)
            return camera

    class Encoder:
        def imencode(self, _suffix, _frame, *_a):
            return True, bytearray(_JPEG)

    provider = PiCamera2Provider(
        _node_config(tmp_path),
        module=type("Module", (), {"Picamera2": Picamera2}),
        cv2_module=Encoder(),
    )

    with pytest.raises(ValueError, match="camera_unusable_frame"):
        provider.snapshot("picamera2-camera-0")

    # The lock must not be stuck: a fresh snapshot still works.
    result = provider.snapshot("picamera2-camera-0")
    assert result.image.startswith(b"\xff\xd8")
    provider.close()


def test_warm_profile_proof_waits_for_the_exclusive_camera_lock(tmp_path) -> None:
    """The background warm-profile proof must honor the same exclusive
    physical-camera ownership as snapshot() -- it must not construct its own,
    uncoordinated camera session while another operation already owns the
    hardware."""

    class Camera:
        def __init__(self) -> None:
            self.sensor_modes = [
                {"size": (1920, 1440), "crop_limits": (0, 0, 4624, 3472)},
                {"size": (4624, 3472), "crop_limits": (0, 0, 4624, 3472)},
            ]
            self.stopped = self.closed = False

        def create_still_configuration(self, **kwargs):
            return kwargs

        def configure(self, _configuration):
            return None

        def start(self):
            return None

        def capture_array(self, *_a, **_k):
            return object()

        def stop(self):
            self.stopped = True

        def close(self):
            self.closed = True

    class Picamera2:
        cameras: list[Camera] = []

        @staticmethod
        def global_camera_info():
            return [{}]

        def __new__(cls, _index):
            camera = Camera()
            cls.cameras.append(camera)
            return camera

    class Encoder:
        COLOR_YUV2BGR_I420 = 1

        def cvtColor(self, frame, _conversion):
            return frame

        def imencode(self, _suffix, _frame, *_a):
            return True, bytearray(_JPEG)

    provider = PiCamera2Provider(
        _node_config(tmp_path),
        module=type("Module", (), {"Picamera2": Picamera2}),
        cv2_module=Encoder(),
    )

    provider._lock.acquire()
    try:
        # Cold cache: computes sensor modes (a separate, already-bounded,
        # already-released probe -- see _sensor_modes -- not this test's
        # concern) then schedules the warm-profile background proof.
        provider.capture_profiles("picamera2-camera-0")
        sessions_from_the_mode_probe = len(Picamera2.cameras)
        worker = provider._warm_proofs["picamera2-camera-0"]
        worker.join(timeout=0.3)
        assert worker.is_alive(), (
            "warm-profile proof finished without ever needing the exclusive "
            "camera lock -- it must wait like every other camera operation"
        )
        assert len(Picamera2.cameras) == sessions_from_the_mode_probe, (
            "warm-profile proof constructed a second, uncoordinated camera "
            "session while another operation already owned the hardware"
        )
    finally:
        provider._lock.release()

    worker.join(timeout=2)
    assert not worker.is_alive()
    assert len(Picamera2.cameras) > sessions_from_the_mode_probe, (
        "warm-profile proof never proceeded once the lock was freed"
    )
    assert provider.capture_readiness("picamera2-camera-0") == "ready"
    provider.close()


# ---------------------------------------------------------------------------
# App/ASGI-layer: the analysis stream must not crash on expected contention.
# ---------------------------------------------------------------------------


class _ContendedProvider:
    """A minimal provider whose monitoring snapshot fails on chosen calls,
    simulating a concurrent evidence/high-resolution capture holding
    PiCamera2Provider's bounded lock (see providers.py CAPTURE_LOCK_TIMEOUT_SECONDS)."""

    CAMERA_ID = "contended-camera-1"

    def __init__(
        self,
        *,
        fail_on: frozenset[int] = frozenset(),
        always_fail: bool = False,
        fail_value: str = "camera_busy",
    ) -> None:
        self._fail_on = fail_on
        self._always_fail = always_fail
        self._fail_value = fail_value
        self.calls = 0

    def cameras(self) -> list[NodeCamera]:
        return [
            NodeCamera(
                self.CAMERA_ID, "Contended camera", "available",
                snapshot_supported=True, provider_type="picamera2",
            )
        ]

    def capture_profiles(self, camera_id: str) -> list[NodeCaptureProfile]:
        if camera_id != self.CAMERA_ID:
            return []
        return [
            NodeCaptureProfile(
                profile_id="contended-monitoring",
                purposes=("monitoring", "preview"),
                width=8,
                height=8,
                jpeg_supported=True,
                max_expected_bytes=len(_JPEG),
                capture_class="warm_concurrent",
                geometry_group="contended-fov",
                same_fov=True,
            )
        ]

    def snapshot(self, camera_id: str, *, profile_id: str | None = None) -> bytes:
        self.calls += 1
        if self._always_fail or self.calls in self._fail_on:
            raise ValueError(self._fail_value)
        return _JPEG

    def close(self) -> None:
        return None


def _analysis_endpoint(app):
    routes = {getattr(route, "path", ""): route for route in app.routes}
    return routes["/node/v1/cameras/{camera_id}/analysis-stream"].endpoint


def _capture_endpoint(app):
    routes = {getattr(route, "path", ""): route for route in app.routes}
    return routes["/node/v1/cameras/{camera_id}/capture"].endpoint


@pytest.mark.anyio
async def test_analysis_stream_skips_transient_camera_busy_without_crashing(
    tmp_path,
) -> None:
    """This is the exact defect reproduced from the field: a monitoring
    profile.snapshot() call raising ValueError('camera_busy') mid-stream
    must not blow up the ASGI response. It must simply miss that frame."""

    provider = _ContendedProvider(fail_on=frozenset({2, 4}))
    app = create_node_app(_node_config(tmp_path), provider=provider)
    endpoint = _analysis_endpoint(app)

    stream = await endpoint(
        _ContendedProvider.CAMERA_ID, _ConnectedRequest(), "5", "paired"
    )
    # Before the fix this raised ValueError('camera_busy') out of the
    # generator, exactly like the unhandled ASGI ExceptionGroup in the
    # preserved outage log.
    parts = [part async for part in stream.body_iterator]
    content = b"".join(parts)
    assert content.count(b"Content-Type: image/jpeg") == 3
    assert provider.calls == 5
    assert content.endswith(b"--mockingbird-analysis-frame--\r\n")


@pytest.mark.anyio
async def test_analysis_stream_ends_cleanly_when_camera_never_recovers(
    tmp_path,
) -> None:
    """A camera that is *never* available must still end the stream cleanly
    -- no crash, no hang -- so the client's existing reconnect logic can
    take over, exactly as it already does at the natural max-frames bound."""

    provider = _ContendedProvider(always_fail=True)
    app = create_node_app(_node_config(tmp_path), provider=provider)
    endpoint = _analysis_endpoint(app)

    stream = await endpoint(
        _ContendedProvider.CAMERA_ID, _ConnectedRequest(), "4", "paired"
    )
    parts = [part async for part in stream.body_iterator]
    content = b"".join(parts)
    assert content.count(b"Content-Type: image/jpeg") == 0
    assert content == b"--mockingbird-analysis-frame--\r\n"
    assert provider.calls == 4


@pytest.mark.anyio
async def test_analysis_stream_does_not_swallow_unrelated_value_error(
    tmp_path,
) -> None:
    """Only the specific, expected-transient ``camera_busy`` signal may miss
    a frame and continue. Any other ValueError code -- e.g. a real
    configuration failure such as ``analysis_profile_unavailable`` or
    ``camera_permission_denied`` -- must still propagate out of the stream
    instead of silently degrading every frame forever with zero signal."""

    provider = _ContendedProvider(
        fail_on=frozenset({2}), fail_value="camera_permission_denied"
    )
    app = create_node_app(_node_config(tmp_path), provider=provider)
    endpoint = _analysis_endpoint(app)

    stream = await endpoint(
        _ContendedProvider.CAMERA_ID, _ConnectedRequest(), "5", "paired"
    )
    with pytest.raises(ValueError, match="camera_permission_denied"):
        [part async for part in stream.body_iterator]
    # The first frame (call 1) must have already been yielded before the
    # second call's unrelated failure ends the stream -- this proves the
    # propagation happens at the failing frame, not before the stream ever
    # starts producing output.
    assert provider.calls == 2


@pytest.mark.anyio
async def test_analysis_stream_disconnect_during_inflight_capture_releases_camera_lock(
    tmp_path,
) -> None:
    """A client disconnect while a real capture is in flight must not leave
    the physical camera permanently owned."""

    release_capture = threading.Event()
    capture_started = threading.Event()

    class Camera:
        def __init__(self) -> None:
            self.stopped = self.closed = False

        def create_still_configuration(self, **kwargs):
            return kwargs

        def configure(self, _configuration):
            return None

        def start(self):
            return None

        def capture_array(self, *_a, **_k):
            capture_started.set()
            release_capture.wait(timeout=2)
            return object()

        def stop(self):
            self.stopped = True

        def close(self):
            self.closed = True

    class Picamera2:
        cameras: list[Camera] = []

        @staticmethod
        def global_camera_info():
            return [{}]

        def __new__(cls, _index):
            camera = Camera()
            cls.cameras.append(camera)
            return camera

    class Encoder:
        def imencode(self, _suffix, _frame, *_a):
            return True, bytearray(_JPEG)

    provider = PiCamera2Provider(
        _node_config(tmp_path),
        module=type("Module", (), {"Picamera2": Picamera2}),
        cv2_module=Encoder(),
    )
    app = create_node_app(_node_config(tmp_path), provider=provider)
    endpoint = _analysis_endpoint(app)

    stream = await endpoint("picamera2-camera-0", _ConnectedRequest(), "1200", "paired")
    task = asyncio.ensure_future(anext(stream.body_iterator))
    # threading.Event.wait() is blocking; run it off-thread so the event loop
    # stays free to actually advance `task` up to the in-flight capture.
    started = await asyncio.to_thread(capture_started.wait, 2)
    assert started, "capture never started"

    # Simulate the client disconnecting (Starlette cancels the task driving
    # body_iterator) while the capture is still in flight.
    task.cancel()
    with pytest.raises((asyncio.CancelledError, StopAsyncIteration)):
        await task

    release_capture.set()
    # Give the (uncancellable, real-thread) capture a moment to finish and
    # release the provider's lock via its own finally.
    for _ in range(50):
        if provider._lock.acquire(timeout=0.1):
            provider._lock.release()
            break
    else:  # pragma: no cover - failure path only
        pytest.fail("camera lock was never released after client disconnect")

    # The provider -- and a fresh stream -- must both still work.
    result = provider.snapshot("picamera2-camera-0")
    assert result.image.startswith(b"\xff\xd8")
    replacement = await endpoint("picamera2-camera-0", _ConnectedRequest(), "1", "paired")
    replacement_content = b"".join([part async for part in replacement.body_iterator])
    assert replacement_content.count(b"Content-Type: image/jpeg") == 1
    provider.close()


@pytest.mark.anyio
async def test_capture_endpoint_still_returns_clean_busy_response_when_provider_is_locked(
    tmp_path,
) -> None:
    """No regression: the existing single-shot capture/evidence endpoints
    already translate a busy provider into a clean HTTP error -- confirm
    that established, correct behavior is unchanged."""

    class AlwaysBusyProvider(_ContendedProvider):
        def snapshot(self, camera_id: str, *, profile_id: str | None = None) -> bytes:
            raise ValueError("camera_busy")

        def capture_profiles(self, camera_id):
            return [
                NodeCaptureProfile(
                    profile_id="contended-monitoring",
                    purposes=("monitoring", "preview", "evidence"),
                    width=8, height=8, jpeg_supported=True,
                    max_expected_bytes=len(_JPEG),
                    capture_class="warm", geometry_group=None,
                )
            ]

    provider = AlwaysBusyProvider()
    app = create_node_app(_node_config(tmp_path), provider=provider)
    endpoint = _capture_endpoint(app)
    from mockingbird_node.app import CaptureRequest

    with pytest.raises(HTTPException) as excinfo:
        endpoint(
            _ContendedProvider.CAMERA_ID,
            CaptureRequest(profile_id="contended-monitoring"),
            "paired",
        )
    assert excinfo.value.status_code == 409
    assert excinfo.value.headers["X-MockingBird-Node-Error"] == "node_camera_unavailable"


@pytest.mark.anyio
async def test_rapid_live_and_observation_transitions_do_not_crash(tmp_path) -> None:
    """A quick Live -> Start Observing -> Live cycle (plain snapshot polling
    interleaved with opening/closing an analysis stream) must never crash,
    matching the real product's ownership transition."""

    provider = _ContendedProvider(fail_on=frozenset({3}))
    app = create_node_app(_node_config(tmp_path), provider=provider)
    routes = {getattr(route, "path", ""): route for route in app.routes}
    snapshot_endpoint = routes["/node/v1/cameras/{camera_id}/snapshot"].endpoint
    analysis_endpoint = _analysis_endpoint(app)

    # Live: plain polling snapshot.
    first = snapshot_endpoint(_ContendedProvider.CAMERA_ID, "paired")
    assert first.status_code == 200

    # Start Observing: open the analysis stream and consume a couple frames.
    stream = await analysis_endpoint(
        _ContendedProvider.CAMERA_ID, _ConnectedRequest(), "4", "paired"
    )
    content = b"".join([part async for part in stream.body_iterator])
    assert content.endswith(b"--mockingbird-analysis-frame--\r\n")

    # Live again: plain polling snapshot resumes cleanly.
    last = snapshot_endpoint(_ContendedProvider.CAMERA_ID, "paired")
    assert last.status_code == 200
