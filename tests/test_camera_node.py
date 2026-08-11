import json
from pathlib import Path
import tempfile
import threading

import httpx
import pytest
from sqlalchemy import func, select

from mockingbird.api import main as api_main
from mockingbird.api.main import app, configure_repository
from mockingbird.playback.camera_node_bridge import CameraNodeSnapshotProcess
from mockingbird.repository.product_repository import ProductRepository, SourceProviderConfigurationModel
from mockingbird.source_providers.camera_node import (
    CameraNodeCamera,
    CameraNodeCaptureProfile,
    CameraNodeClient,
    CameraNodeClientError,
    CameraNodePairing,
    normalize_camera_node_address,
)
from mockingbird.storage.database import CURRENT_DATABASE_SCHEMA_VERSION, create_database_engine, initialize_database
from mockingbird.storage.models import (
    CameraSourceModel,
    EventModel,
    MediaAssetModel,
    StreamModel,
    VisitModel,
)
from mockingbird_node.app import _PairingState, create_node_app
from mockingbird_node.config import CameraNodeConfig
from mockingbird_node.providers import (
    CompositeCameraProvider,
    NodeCamera,
    NodeCaptureProfile,
    NodeCaptureResult,
    PiCamera2Provider,
    SyntheticCameraProvider,
    V4L2CameraProvider,
    create_camera_provider,
)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class _FakeNodeRequester:
    def __init__(self) -> None:
        self.requests: list[tuple[str, str, dict[str, str]]] = []
        self.timings = []

    def request(self, *, method, url, headers, body, max_bytes, timing):
        self.requests.append((method, url, headers))
        self.timings.append(timing)
        if url.endswith("/health"):
            return 200, {"Content-Type": "application/json"}, json.dumps({"node_id": "node-test", "display_name": "Test node", "api_version": "v1"}).encode()
        if url.endswith("/pair"):
            assert body and b"pairing_code" in body
            return 200, {"Content-Type": "application/json"}, json.dumps({
                "node_id": "node-test",
                "display_name": "Test node",
                "api_version": "v1",
                "credential": "never-echo-node-credential",
                "cameras": [{"camera_id": "opaque-camera-1", "display_name": "Feeder view", "status": "available", "snapshot_supported": True}],
            }).encode()
        if url.endswith("/pair/revoke"):
            return 204, {}, b""
        if url.endswith("/capabilities"):
            return 200, {"Content-Type": "application/json"}, json.dumps({"recommended_snapshot_timeout_seconds": 8.0}).encode()
        if url.endswith("/cameras"):
            return 200, {"Content-Type": "application/json"}, json.dumps({"items": [{"camera_id": "opaque-camera-1", "display_name": "Feeder view", "status": "available", "snapshot_supported": True, "provider_type": "v4l2"}]}).encode()
        if "/snapshot" in url:
            return 200, {"Content-Type": "image/jpeg"}, b"\xff\xd8fake\xff\xd9"
        return 404, {"Content-Type": "application/json"}, b"{}"


def _repository(tmp_path) -> ProductRepository:
    return ProductRepository(
        db_url=f"sqlite:///{tmp_path / 'camera-node.sqlite3'}",
        media_root=tmp_path / "media",
    )


def _counts(repository: ProductRepository) -> tuple[int, int, int, int, int]:
    with repository.session_factory() as session:
        return tuple(
            session.scalar(select(func.count(model.id))) or 0
            for model in (CameraSourceModel, StreamModel, EventModel, VisitModel, MediaAssetModel)
        )


def test_camera_node_address_and_client_are_pinned_to_one_local_base_address() -> None:
    requester = _FakeNodeRequester()
    client = CameraNodeClient(requester=requester)
    assert normalize_camera_node_address("http://192.168.10.8:8787/") == "http://192.168.10.8:8787"
    with pytest.raises(CameraNodeClientError, match="node_address_requires_lan_ip"):
        client.health("http://camera-node.local:8787")
    with pytest.raises(CameraNodeClientError, match="node_address_not_local"):
        client.health("https://8.8.8.8")
    pairing = client.pair("http://127.0.0.1:8787", "correct-one-time-code")
    assert pairing.cameras[0].camera_id == "opaque-camera-1"
    assert pairing.cameras[0].capture_readiness == "not_initialized"
    assert pairing.cameras[0].capture_profile_status == ()
    assert "never-echo-node-credential" not in str(pairing.cameras)
    assert all(url.startswith("http://127.0.0.1:8787/node/v1/") for _, url, _ in requester.requests)
    assert all(
        "never-echo-node-credential" not in str(headers)
        for _, url, headers in requester.requests
        if not url.endswith("/capabilities")
    )
    assert any(url.endswith("/capabilities") and headers.get("Authorization") == "Bearer never-echo-node-credential" for _, url, headers in requester.requests)


def _node_config(*, provider_key: str = "v4l2", enabled_providers: tuple[str, ...] = ()) -> CameraNodeConfig:
    return CameraNodeConfig("Test Node", "127.0.0.1", 8787, provider_key, None, 1_500_000, 1920, 1080, 60, 2, testing=True, enabled_providers=enabled_providers)


def test_production_defaults_exclude_synthetic_and_unknown_provider_is_rejected(monkeypatch) -> None:
    monkeypatch.delenv("MOCKINGBIRD_NODE_PROVIDER", raising=False)
    monkeypatch.delenv("MOCKINGBIRD_NODE_PROVIDERS", raising=False)
    config = CameraNodeConfig.from_environment()
    assert config.enabled_providers == ("v4l2", "picamera2")
    assert "synthetic" not in config.enabled_providers
    monkeypatch.setenv("MOCKINGBIRD_NODE_PROVIDERS", "v4l2,not_a_provider")
    with pytest.raises(ValueError, match="provider_invalid"):
        CameraNodeConfig.from_environment()


def test_evidence_bounds_are_opt_in_and_never_smaller_than_monitoring(monkeypatch) -> None:
    monkeypatch.setenv("MOCKINGBIRD_NODE_PROVIDERS", "picamera2")
    monkeypatch.setenv("MOCKINGBIRD_NODE_EVIDENCE_MAX_IMAGE_BYTES", "16000000")
    monkeypatch.setenv("MOCKINGBIRD_NODE_EVIDENCE_MAX_IMAGE_WIDTH", "10000")
    monkeypatch.setenv("MOCKINGBIRD_NODE_EVIDENCE_MAX_IMAGE_HEIGHT", "8000")
    config = CameraNodeConfig.from_environment()
    assert config.max_image_width == 1920
    assert config.effective_evidence_max_image_width == 10000
    assert config.effective_evidence_max_image_height == 8000
    assert config.effective_evidence_max_image_bytes == 16_000_000

    monkeypatch.setenv("MOCKINGBIRD_NODE_EVIDENCE_MAX_IMAGE_WIDTH", "1000")
    with pytest.raises(ValueError, match="evidence_bounds_invalid"):
        CameraNodeConfig.from_environment()


def test_v4l2_enumeration_is_bounded_opaque_and_capture_releases_resources() -> None:
    class Capture:
        released = False
        def isOpened(self): return True
        def set(self, *_args): return True
        def read(self): return True, object()
        def release(self): self.released = True

    class Cv2:
        CAP_PROP_FRAME_WIDTH = 1
        CAP_PROP_FRAME_HEIGHT = 2
        def __init__(self): self.capture = Capture(); self.paths = []
        def VideoCapture(self, path): self.paths.append(path); return self.capture
        def imencode(self, _suffix, _frame): return True, bytearray(b"\xff\xd8\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x11\x00\xff\xd9")

    cv2 = Cv2()
    provider = V4L2CameraProvider(_node_config(), device_enumerator=lambda: [(index, f"/dev/video{index}") for index in range(10, -1, -1)], cv2_module=cv2)
    cameras = provider.cameras()
    assert [camera.camera_id for camera in cameras] == [f"v4l2-camera-{index}" for index in range(8)]
    assert "/dev/" not in str(cameras)
    assert provider.snapshot("v4l2-camera-0").startswith(b"\xff\xd8")
    assert cv2.capture.released is True
    assert cv2.paths == ["/dev/video0"]


def test_v4l2_busy_and_picamera2_missing_are_safe_setup_states() -> None:
    provider = V4L2CameraProvider(_node_config(), device_enumerator=lambda: [(0, "/dev/video0")], cv2_module=object())
    provider._lock.acquire()
    try:
        with pytest.raises(ValueError, match="camera_busy"):
            provider.snapshot("v4l2-camera-0")
    finally:
        provider._lock.release()
    pi = PiCamera2Provider(_node_config(provider_key="picamera2"), module=False, cv2_module=object())
    assert pi.cameras()[0].status == "setup_required"


def test_picamera2_fake_runtime_keeps_opaque_identity_warm_and_releases_on_close() -> None:
    class Camera:
        def __init__(self): self.stopped = self.closed = False; self.captures = 0
        def create_still_configuration(self, **_kwargs): return object()
        def configure(self, _configuration): return None
        def start(self): return None
        def capture_array(self): self.captures += 1; return object()
        def stop(self): self.stopped = True
        def close(self): self.closed = True
    class Picamera2:
        cameras = []
        @staticmethod
        def global_camera_info(): return [{"ignored": "not exposed"}]
        def __new__(cls, _index):
            camera = Camera()
            cls.cameras.append(camera)
            return camera
    module = type("Module", (), {"Picamera2": Picamera2})
    class Encoder:
        def imencode(self, _suffix, _frame): return True, bytearray(b"\xff\xd8\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x11\x00\xff\xd9")

    provider = PiCamera2Provider(_node_config(provider_key="picamera2"), module=module, cv2_module=Encoder())
    assert provider.cameras()[0].camera_id == "picamera2-camera-0"
    assert provider.snapshot("picamera2-camera-0").image.startswith(b"\xff\xd8")
    assert provider.snapshot("picamera2-camera-0").image.startswith(b"\xff\xd8")
    assert len(Picamera2.cameras) == 1
    assert Picamera2.cameras[0].captures == 2
    assert not Picamera2.cameras[0].stopped
    provider.close()
    assert Picamera2.cameras[0].stopped and Picamera2.cameras[0].closed


def test_picamera2_enables_continuous_autofocus_when_libcamera_supports_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Camera:
        def __init__(self):
            self.autofocus_controls: list[dict[str, object]] = []
        def create_still_configuration(self, **_kwargs): return object()
        def configure(self, _configuration): return None
        def set_controls(self, controls): self.autofocus_controls.append(controls)
        def start(self): return None
        def capture_array(self): return object()
        def stop(self): return None
        def close(self): return None

    class Picamera2:
        camera = Camera()
        @staticmethod
        def global_camera_info(): return [{}]
        def __new__(cls, _index): return cls.camera

    class Encoder:
        def imencode(self, _suffix, _frame):
            return True, bytearray(b"\xff\xd8\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x11\x00\xff\xd9")

    continuous = object()
    controls = type("Controls", (), {"AfModeEnum": type("AfModeEnum", (), {"Continuous": continuous})})
    monkeypatch.setattr(
        "mockingbird_node.providers.import_module",
        lambda name: type("Libcamera", (), {"controls": controls})(),
    )
    module = type("Module", (), {"Picamera2": Picamera2})

    provider = PiCamera2Provider(
        _node_config(provider_key="picamera2"), module=module, cv2_module=Encoder()
    )
    assert provider.snapshot("picamera2-camera-0").image.startswith(b"\xff\xd8")
    assert Picamera2.camera.autofocus_controls == [{"AfMode": continuous}]


def test_picamera2_autofocus_control_failure_keeps_camera_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Camera:
        def create_still_configuration(self, **_kwargs): return object()
        def configure(self, _configuration): return None
        def set_controls(self, _controls): raise RuntimeError("local control failure")
        def start(self): return None
        def capture_array(self): return object()
        def stop(self): return None
        def close(self): return None

    class Picamera2:
        camera = Camera()
        @staticmethod
        def global_camera_info(): return [{}]
        def __new__(cls, _index): return cls.camera

    class Encoder:
        def imencode(self, _suffix, _frame):
            return True, bytearray(b"\xff\xd8\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x11\x00\xff\xd9")

    monkeypatch.setattr(
        "mockingbird_node.providers.import_module", lambda name: object()
    )
    module = type("Module", (), {"Picamera2": Picamera2})
    provider = PiCamera2Provider(
        _node_config(provider_key="picamera2"), module=module, cv2_module=Encoder()
    )
    assert provider.snapshot("picamera2-camera-0").image.startswith(b"\xff\xd8")


def test_picamera2_failed_capture_resets_then_later_snapshot_reinitializes() -> None:
    class Camera:
        def __init__(self, *, fail_capture: bool): self.fail_capture = fail_capture; self.stopped = self.closed = False
        def create_still_configuration(self, **_kwargs): return object()
        def configure(self, _configuration): return None
        def start(self): return None
        def capture_array(self):
            if self.fail_capture:
                raise RuntimeError("driver text must stay local")
            return object()
        def stop(self): self.stopped = True
        def close(self): self.closed = True
    class Picamera2:
        cameras = []
        @staticmethod
        def global_camera_info(): return [{}]
        def __new__(cls, _index):
            camera = Camera(fail_capture=not cls.cameras)
            cls.cameras.append(camera)
            return camera
    module = type("Module", (), {"Picamera2": Picamera2})
    class Encoder:
        def imencode(self, _suffix, _frame): return True, bytearray(b"\xff\xd8\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x11\x00\xff\xd9")

    provider = PiCamera2Provider(_node_config(provider_key="picamera2"), module=module, cv2_module=Encoder())
    with pytest.raises(ValueError, match="camera_unusable_frame"):
        provider.snapshot("picamera2-camera-0")
    assert Picamera2.cameras[0].stopped and Picamera2.cameras[0].closed
    assert provider.snapshot("picamera2-camera-0").image.startswith(b"\xff\xd8")
    assert len(Picamera2.cameras) == 2
    provider.close()


def test_picamera2_advertises_real_still_modes_and_restores_monitoring_after_evidence_capture() -> None:
    class Camera:
        def __init__(self):
            self.stopped = self.closed = False
            self.configured_sizes: list[tuple[int, int]] = []
            self.sensor_modes = [
                {"size": (1920, 1080), "crop_limits": (0, 0, 9152, 6944)},
                {"size": (9152, 6944), "crop_limits": (0, 0, 9152, 6944)},
            ]

        def create_still_configuration(self, *, main):
            self.configured_sizes.append(main["size"])
            return object()

        def configure(self, _configuration): return None
        def start(self): return None
        def capture_array(self): return object()
        def stop(self): self.stopped = True
        def close(self): self.closed = True

    class Picamera2:
        cameras: list[Camera] = []

        @staticmethod
        def global_camera_info(): return [{}]

        def __new__(cls, _index):
            camera = Camera()
            cls.cameras.append(camera)
            return camera

    class Encoder:
        def imencode(self, _suffix, _frame):
            return True, bytearray(b"\xff\xd8\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x11\x00\xff\xd9")

    config = CameraNodeConfig(
        "Test Node", "127.0.0.1", 8787, "picamera2", None,
        1_500_000, 1920, 1080, 60, 2, testing=True,
        evidence_max_image_bytes=16_000_000,
        evidence_max_image_width=10_000,
        evidence_max_image_height=8_000,
    )
    module = type("Module", (), {"Picamera2": Picamera2})
    provider = PiCamera2Provider(config, module=module, cv2_module=Encoder())
    provider.capture_profiles("picamera2-camera-0")
    provider._warm_proofs["picamera2-camera-0"].join(timeout=1)
    profiles = provider.capture_profiles("picamera2-camera-0")

    monitoring = next(profile for profile in profiles if "monitoring" in profile.purposes)
    evidence = next(profile for profile in profiles if "evidence" in profile.purposes)
    assert (monitoring.width, monitoring.height) == (1920, 1080)
    assert (evidence.width, evidence.height) == (9152, 6944)
    assert monitoring.geometry_group == evidence.geometry_group
    assert evidence.capture_class == "reconfiguration_required"
    assert evidence.max_expected_bytes == 16_000_000

    provider.snapshot("picamera2-camera-0", profile_id=monitoring.profile_id)
    evidence_result = provider.snapshot("picamera2-camera-0", profile_id=evidence.profile_id)
    assert evidence_result.monitoring_recovery == "restored"
    assert provider._camera_profile_ids["picamera2-camera-0"] == monitoring.profile_id
    assert Picamera2.cameras[-1].configured_sizes == [(1920, 1080)]
    assert any((9152, 6944) in camera.configured_sizes for camera in Picamera2.cameras)
    provider.close()


def test_picamera2_restoration_failure_keeps_evidence_and_lazily_recovers_monitoring() -> None:
    class Camera:
        def __init__(self, *, fail_start: bool = False):
            self.fail_start = fail_start
            self.stopped = self.closed = False
            self.captures = 0
            self.configured_size: tuple[int, int] | None = None
            self.sensor_modes = [
                {"size": (1920, 1080), "crop_limits": (0, 0, 9152, 6944)},
                {"size": (3840, 2160), "crop_limits": (0, 0, 9152, 6944)},
            ]

        def create_still_configuration(self, *, main):
            self.configured_size = main["size"]
            return object()
        def configure(self, _configuration): return None
        def start(self):
            if self.fail_start:
                raise RuntimeError("local restore failed")
        def capture_array(self):
            self.captures += 1
            return object()
        def stop(self): self.stopped = True
        def close(self): self.closed = True

    class Picamera2:
        cameras: list[Camera] = []

        @staticmethod
        def global_camera_info(): return [{}]

        def __new__(cls, _index):
            # Mode enumeration, rejected warm probe, initial monitoring,
            # evidence, then the intentionally failing restore.
            camera = Camera(fail_start=len(cls.cameras) == 4)
            cls.cameras.append(camera)
            return camera

    class Encoder:
        COLOR_YUV2BGR_I420 = 1
        def cvtColor(self, frame, _conversion): return frame
        def imencode(self, _suffix, _frame, *_args):
            return True, bytearray(b"\xff\xd8\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x11\x00\xff\xd9")

    config = CameraNodeConfig(
        "Test Node", "127.0.0.1", 8787, "picamera2", None,
        1_500_000, 1920, 1080, 60, 2, testing=True,
        evidence_max_image_bytes=16_000_000,
        evidence_max_image_width=10_000,
        evidence_max_image_height=8_000,
    )
    module = type("Module", (), {"Picamera2": Picamera2})
    provider = PiCamera2Provider(config, module=module, cv2_module=Encoder())
    profiles = provider.capture_profiles("picamera2-camera-0")
    monitoring = next(profile for profile in profiles if "monitoring" in profile.purposes)
    evidence = next(profile for profile in profiles if "evidence" in profile.purposes)

    provider.snapshot("picamera2-camera-0", profile_id=monitoring.profile_id)
    captured = provider.snapshot("picamera2-camera-0", profile_id=evidence.profile_id)

    assert captured.image.startswith(b"\xff\xd8")
    assert captured.monitoring_recovery == "reset_required"
    assert provider._cameras == {}
    assert provider._camera_profile_ids == {}
    assert Picamera2.cameras[4].stopped and Picamera2.cameras[4].closed
    assert next(
        camera for camera in Picamera2.cameras if camera.configured_size == (3840, 2160)
    ).captures == 1

    recovered = provider.snapshot("picamera2-camera-0", profile_id=monitoring.profile_id)
    assert recovered.image.startswith(b"\xff\xd8")
    assert recovered.monitoring_recovery is None
    assert provider._camera_profile_ids["picamera2-camera-0"] == monitoring.profile_id
    assert sum(camera.captures for camera in Picamera2.cameras) == 3
    provider.close()


def test_picamera2_warm_dual_stream_uses_one_session_without_reconfiguration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Camera:
        def __init__(self):
            self.sensor_modes = [
                {"size": (1920, 1080), "crop_limits": (0, 0, 9152, 6944)},
                {"size": (3840, 2160), "crop_limits": (0, 0, 9152, 6944)},
            ]
            self.configurations: list[dict[str, object]] = []
            self.captures: list[str] = []
            self.controls: list[dict[str, object]] = []
            self.stopped = self.closed = False

        def create_still_configuration(self, **kwargs):
            self.configurations.append(kwargs)
            return object()
        def configure(self, _configuration): return None
        def set_controls(self, controls): self.controls.append(controls)
        def start(self): return None
        def capture_array(self, stream_name):
            self.captures.append(stream_name)
            return object()
        def stop(self): self.stopped = True
        def close(self): self.closed = True

    class Picamera2:
        cameras: list[Camera] = []
        @staticmethod
        def global_camera_info(): return [{}]
        def __new__(cls, _index):
            camera = Camera()
            cls.cameras.append(camera)
            return camera

    class Encoder:
        COLOR_YUV2BGR_I420 = 1
        def cvtColor(self, frame, _conversion): return frame
        def imencode(self, _suffix, _frame, *_args):
            return True, bytearray(b"\xff\xd8\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x11\x00\xff\xd9")

    continuous = object()
    controls = type("Controls", (), {"AfModeEnum": type("AfModeEnum", (), {"Continuous": continuous})})
    monkeypatch.setattr(
        "mockingbird_node.providers.import_module",
        lambda _name: type("Libcamera", (), {"controls": controls})(),
    )
    config = CameraNodeConfig(
        "Test Node", "127.0.0.1", 8787, "picamera2", None,
        1_500_000, 1920, 1080, 60, 2, testing=True,
        evidence_max_image_bytes=16_000_000,
        evidence_max_image_width=10_000,
        evidence_max_image_height=8_000,
    )
    provider = PiCamera2Provider(
        config, module=type("Module", (), {"Picamera2": Picamera2}), cv2_module=Encoder()
    )

    provider.capture_profiles("picamera2-camera-0")
    provider._warm_proofs["picamera2-camera-0"].join(timeout=1)
    profiles = provider.capture_profiles("picamera2-camera-0")
    monitoring = next(profile for profile in profiles if "monitoring" in profile.purposes)
    evidence = next(
        profile
        for profile in profiles
        if profile.capture_class == "warm_concurrent" and "evidence" in profile.purposes
    )
    assert monitoring.capture_class == evidence.capture_class == "warm_concurrent"
    assert provider.capture_readiness("picamera2-camera-0") == "ready"
    assert (evidence.width, evidence.height) == (3840, 2160)

    provider.snapshot("picamera2-camera-0", profile_id=monitoring.profile_id)
    provider.snapshot("picamera2-camera-0", profile_id=evidence.profile_id)
    session = Picamera2.cameras[-1]
    assert len(Picamera2.cameras) == 2
    assert session.configurations == [{
        "main": {"size": (3840, 2160), "format": "RGB888"},
        "lores": {"size": (1920, 1080), "format": "YUV420"},
        "buffer_count": 2,
    }]
    assert session.captures == ["lores", "main"] + ["lores", "main"] * 6
    assert session.controls == [{"AfMode": continuous}]
    provider.close()
    assert session.stopped and session.closed


def test_picamera2_warm_candidate_resource_rejection_promotes_next_profile_and_caches_proof() -> None:
    class Camera:
        def __init__(self):
            self.sensor_modes = [
                {"size": (1920, 1440), "crop_limits": (0, 0, 9248, 6944)},
                {"size": (3840, 2160), "crop_limits": (0, 0, 9248, 6944)},
                {"size": (4624, 3472), "crop_limits": (0, 0, 9248, 6944)},
                {"size": (9248, 6944), "crop_limits": (0, 0, 9248, 6944)},
            ]
            self.configurations: list[dict[str, object]] = []
            self.stopped = self.closed = False

        def create_still_configuration(self, **kwargs):
            return kwargs

        def configure(self, configuration):
            self.configurations.append(configuration)
            if configuration["main"]["size"] == (9248, 6944):
                raise OSError(12, "local allocation failure")

        def start(self): return None
        def capture_array(self, _stream_name): return object()
        def stop(self): self.stopped = True
        def close(self): self.closed = True

    class Picamera2:
        cameras: list[Camera] = []

        @staticmethod
        def global_camera_info(): return [{}]

        def __new__(cls, _index):
            camera = Camera()
            cls.cameras.append(camera)
            return camera

    class Encoder:
        COLOR_YUV2BGR_I420 = 1

        def cvtColor(self, frame, _conversion): return frame

        def imencode(self, _suffix, _frame, *_args):
            return True, bytearray(
                b"\xff\xd8\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x11\x00\xff\xd9"
            )

    provider = PiCamera2Provider(
        CameraNodeConfig(
            "Test Node", "127.0.0.1", 8787, "picamera2", None,
            1_500_000, 1920, 1440, 60, 2, testing=True,
            evidence_max_image_bytes=16_000_000,
            evidence_max_image_width=10_000,
            evidence_max_image_height=8_000,
        ),
        module=type("Module", (), {"Picamera2": Picamera2}),
        cv2_module=Encoder(),
    )

    provider.capture_profiles("picamera2-camera-0")
    provider._warm_proofs["picamera2-camera-0"].join(timeout=1)
    profiles = provider.capture_profiles("picamera2-camera-0")

    assert provider.capture_readiness("picamera2-camera-0") == "ready"
    statuses = {
        item["profile_id"]: item["state"]
        for item in provider.capture_profile_status("picamera2-camera-0")
    }
    assert statuses["picamera2-evidence-9248x6944"] == "rejected_resource"
    assert statuses["picamera2-evidence-4624x3472"] == "accepted"
    assert statuses["picamera2-evidence-3840x2160"] == "untested"
    assert "picamera2-evidence-9248x6944" not in {
        profile.profile_id for profile in profiles
    }
    selected_monitoring = next(
        profile for profile in profiles if profile.profile_id == "picamera2-monitoring-1920x1440"
    )
    selected_evidence = next(
        profile
        for profile in profiles
        if profile.profile_id == "picamera2-warm-evidence-4624x3472"
    )
    assert selected_monitoring.capture_class == selected_evidence.capture_class == "warm_concurrent"
    assert selected_monitoring.geometry_group == selected_evidence.geometry_group
    assert len(Picamera2.cameras) == 3
    assert Picamera2.cameras[1].stopped and Picamera2.cameras[1].closed
    assert all(
        configuration["main"]["size"] != (3840, 2160)
        for camera in Picamera2.cameras
        for configuration in camera.configurations
    )

    provider.snapshot("picamera2-camera-0", profile_id=selected_monitoring.profile_id)
    provider.snapshot("picamera2-camera-0", profile_id=selected_evidence.profile_id)
    provider.capture_profiles("picamera2-camera-0")
    assert len(Picamera2.cameras) == 3
    provider.close()


def test_picamera2_warm_required_pair_retries_once_after_resource_rejections() -> None:
    """One fresh required-pair retry must not silently promote a smaller mode."""

    class Camera:
        def __init__(self):
            self.sensor_modes = [
                {"size": (1920, 1440), "crop_limits": (0, 0, 9248, 6944)},
                {"size": (3840, 2160), "crop_limits": (0, 0, 9248, 6944)},
                {"size": (4624, 3472), "crop_limits": (0, 0, 9248, 6944)},
                {"size": (8000, 6000), "crop_limits": (0, 0, 9248, 6944)},
                {"size": (9248, 6944), "crop_limits": (0, 0, 9248, 6944)},
            ]
            self.stopped = self.closed = False

        def create_still_configuration(self, **kwargs): return kwargs

        def configure(self, configuration):
            size = configuration["main"]["size"]
            Picamera2.configured_sizes.append(size)
            if size in {(9248, 6944), (8000, 6000)}:
                raise OSError(12, "bounded local allocation failure")
            if size == (4624, 3472):
                Picamera2.required_attempts += 1
                if Picamera2.required_attempts == 1:
                    raise RuntimeError("candidate cleanup still settling")
            if size == (3840, 2160):
                raise AssertionError("must not substitute a smaller warm evidence mode")

        def start(self): return None
        def capture_array(self, _stream_name): return object()
        def stop(self): self.stopped = True
        def close(self): self.closed = True

    class Picamera2:
        cameras: list[Camera] = []
        configured_sizes: list[tuple[int, int]] = []
        required_attempts = 0

        @staticmethod
        def global_camera_info(): return [{}]

        def __new__(cls, _index):
            camera = Camera()
            cls.cameras.append(camera)
            return camera

    class Encoder:
        COLOR_YUV2BGR_I420 = 1

        def cvtColor(self, frame, _conversion): return frame
        def imencode(self, _suffix, _frame, *_args): return True, bytearray(b"jpg")

    provider = PiCamera2Provider(
        CameraNodeConfig(
            "Test Node", "127.0.0.1", 8787, "picamera2", None,
            1_500_000, 1920, 1440, 60, 2, testing=True,
            evidence_max_image_bytes=16_000_000,
            evidence_max_image_width=10_000,
            evidence_max_image_height=8_000,
        ),
        module=type("Module", (), {"Picamera2": Picamera2}),
        cv2_module=Encoder(),
    )

    provider.capture_profiles("picamera2-camera-0")
    provider._warm_proofs["picamera2-camera-0"].join(timeout=1)

    assert provider.capture_readiness("picamera2-camera-0") == "ready"
    assert Picamera2.configured_sizes == [
        (9248, 6944), (8000, 6000), (4624, 3472), (4624, 3472),
    ]
    assert provider.capture_profile_status("picamera2-camera-0") == [
        {"profile_id": "picamera2-evidence-9248x6944", "state": "rejected_resource"},
        {"profile_id": "picamera2-evidence-8000x6000", "state": "rejected_resource"},
        {"profile_id": "picamera2-evidence-4624x3472", "state": "accepted"},
        {"profile_id": "picamera2-evidence-3840x2160", "state": "untested"},
    ]
    assert all(camera.stopped and camera.closed for camera in Picamera2.cameras[:-1])
    provider.close()


def test_picamera2_warm_session_failure_reopens_the_accepted_pair(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A lost warm owner is runtime recovery, not an unavailable profile."""

    class Camera:
        def __init__(self) -> None:
            self.sensor_modes = [
                {"size": (1920, 1440), "crop_limits": (0, 0, 9248, 6944)},
                {"size": (4624, 3472), "crop_limits": (0, 0, 9248, 6944)},
            ]
            self.controls: list[dict[str, object]] = []
            self.fail_next_capture = False
            self.stopped = self.closed = False

        def create_still_configuration(self, **kwargs):
            return kwargs

        def configure(self, _configuration):
            return None

        def set_controls(self, controls):
            self.controls.append(controls)

        def start(self):
            return None

        def capture_array(self, _stream_name):
            if self.fail_next_capture:
                self.fail_next_capture = False
                raise RuntimeError("local camera session failure")
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

        def imencode(self, _suffix, _frame, *_args):
            return True, bytearray(
                b"\xff\xd8\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x11\x00\xff\xd9"
            )

    continuous = object()
    controls = type(
        "Controls",
        (),
        {"AfModeEnum": type("AfModeEnum", (), {"Continuous": continuous})},
    )
    monkeypatch.setattr(
        "mockingbird_node.providers.import_module",
        lambda _name: type("Libcamera", (), {"controls": controls})(),
    )
    provider = PiCamera2Provider(
        CameraNodeConfig(
            "Test Node", "127.0.0.1", 8787, "picamera2", None,
            1_500_000, 1920, 1440, 60, 2, testing=True,
            evidence_max_image_bytes=16_000_000,
            evidence_max_image_width=10_000,
            evidence_max_image_height=8_000,
        ),
        module=type("Module", (), {"Picamera2": Picamera2}),
        cv2_module=Encoder(),
    )
    try:
        provider.capture_profiles("picamera2-camera-0")
        provider._warm_proofs["picamera2-camera-0"].join(timeout=1)
        profiles = provider.capture_profiles("picamera2-camera-0")
        monitoring = next(profile for profile in profiles if "monitoring" in profile.purposes)
        evidence = next(profile for profile in profiles if "evidence" in profile.purposes)
        first_session = provider._warm_sessions["picamera2-camera-0"].camera
        first_session.fail_next_capture = True

        recovered = provider.snapshot(
            "picamera2-camera-0", profile_id=monitoring.profile_id
        )

        assert recovered.image.startswith(b"\xff\xd8")
        assert first_session.stopped and first_session.closed
        assert [profile.profile_id for profile in provider.capture_profiles("picamera2-camera-0")][:2] == [
            monitoring.profile_id,
            evidence.profile_id,
        ]
        assert provider.capture_profile_status("picamera2-camera-0") == [{
            "profile_id": "picamera2-evidence-4624x3472",
            "state": "accepted",
        }]
        recovered_session = provider._warm_sessions["picamera2-camera-0"].camera
        assert recovered_session is not first_session
        assert recovered_session.controls == [{"AfMode": continuous}]
    finally:
        provider.close()


def test_picamera2_all_warm_candidates_rejected_keeps_cold_monitoring_degraded() -> None:
    class Camera:
        def __init__(self):
            self.sensor_modes = [
                {"size": (1920, 1080), "crop_limits": (0, 0, 9152, 6944)},
                {"size": (3840, 2160), "crop_limits": (0, 0, 9152, 6944)},
            ]
            self.stopped = self.closed = False

        def create_still_configuration(self, **kwargs): return kwargs
        def configure(self, _configuration): raise OSError(12, "local allocation failure")
        def start(self): return None
        def stop(self): self.stopped = True
        def close(self): self.closed = True

    class Picamera2:
        cameras: list[Camera] = []

        @staticmethod
        def global_camera_info(): return [{}]

        def __new__(cls, _index):
            camera = Camera()
            cls.cameras.append(camera)
            return camera

    class Encoder:
        COLOR_YUV2BGR_I420 = 1

        def cvtColor(self, frame, _conversion): return frame
        def imencode(self, _suffix, _frame, *_args): return True, bytearray(b"jpg")

    provider = PiCamera2Provider(
        CameraNodeConfig(
            "Test Node", "127.0.0.1", 8787, "picamera2", None,
            1_500_000, 1920, 1080, 60, 2, testing=True,
            evidence_max_image_bytes=16_000_000,
            evidence_max_image_width=10_000,
            evidence_max_image_height=8_000,
        ),
        module=type("Module", (), {"Picamera2": Picamera2}),
        cv2_module=Encoder(),
    )

    provider.capture_profiles("picamera2-camera-0")
    provider._warm_proofs["picamera2-camera-0"].join(timeout=1)

    assert provider.capture_readiness("picamera2-camera-0") == "degraded"
    assert provider._cameras == {}
    assert provider._warm_sessions == {}
    assert all(camera.stopped and camera.closed for camera in Picamera2.cameras)
    assert provider.capture_profile_status("picamera2-camera-0") == [{
        "profile_id": "picamera2-evidence-3840x2160",
        "state": "rejected_resource",
    }]
    assert all(
        profile.capture_class != "warm_concurrent"
        for profile in provider.capture_profiles("picamera2-camera-0")
    )
    provider.close()


@pytest.mark.anyio
async def test_pairing_returns_while_picamera2_warm_proof_runs() -> None:
    started = threading.Event()
    release = threading.Event()

    class Camera:
        sensor_modes = [
            {"size": (1920, 1080), "crop_limits": (0, 0, 9152, 6944)},
            {"size": (3840, 2160), "crop_limits": (0, 0, 9152, 6944)},
        ]

        def create_still_configuration(self, **kwargs): return kwargs
        def configure(self, _configuration): return None
        def start(self):
            started.set()
            assert release.wait(timeout=1)
        def capture_array(self, _stream_name): return object()
        def stop(self): return None
        def close(self): return None

    class Picamera2:
        @staticmethod
        def global_camera_info(): return [{}]
        def __new__(cls, _index): return Camera()

    class Encoder:
        COLOR_YUV2BGR_I420 = 1

        def cvtColor(self, frame, _conversion): return frame
        def imencode(self, _suffix, _frame, *_args):
            return True, bytearray(
                b"\xff\xd8\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x11\x00\xff\xd9"
            )

    provider = PiCamera2Provider(
        CameraNodeConfig(
            "Test Node", "127.0.0.1", 8787, "picamera2", None,
            1_500_000, 1920, 1080, 60, 2, testing=True,
            evidence_max_image_bytes=16_000_000,
            evidence_max_image_width=10_000,
            evidence_max_image_height=8_000,
        ),
        module=type("Module", (), {"Picamera2": Picamera2}),
        cv2_module=Encoder(),
    )
    node = create_node_app(_node_config(provider_key="picamera2"), provider=provider)
    transport = httpx.ASGITransport(app=node)
    async with httpx.AsyncClient(transport=transport, base_url="http://node") as client:
        paired = await client.post(
            "/node/v1/pair", json={"pairing_code": node.state.pairing_code}
        )

    assert paired.status_code == 200
    assert paired.json()["cameras"][0]["capture_readiness"] == "warming"
    assert started.wait(timeout=1)
    release.set()
    provider._warm_proofs["picamera2-camera-0"].join(timeout=1)
    assert provider.capture_readiness("picamera2-camera-0") == "ready"
    provider.close()


def test_pending_setup_refreshes_only_transient_advertised_camera_metadata(tmp_path) -> None:
    """Replaces the previous in-memory `CameraNodePairingStore` unit test: the
    same "refresh advertised cameras without touching the credential" contract
    now lives on the durable repository-backed pending setup instead -- see
    docs/camera-node-pairing-persistence-design.md."""

    repository = _repository(tmp_path)
    try:
        pairing = CameraNodePairing(
            base_address="http://192.168.1.112:8787",
            node_id="node-test",
            display_name="Test node",
            api_version="v1",
            credential="local-only-credential",
            cameras=[CameraNodeCamera("picamera2-camera-0", "Pi camera", "available", True)],
            capability_fingerprint="fingerprint",
        )
        pending = repository.create_camera_node_pending_setup(pairing)
        refreshed = CameraNodeCamera(
            camera_id="picamera2-camera-0",
            display_name="Pi camera",
            status="available",
            snapshot_supported=True,
            capture_profiles=(
                CameraNodeCaptureProfile(
                    profile_id="opaque-monitoring",
                    purposes=("monitoring",),
                    width=1920,
                    height=1440,
                    jpeg_supported=True,
                    max_expected_bytes=1_500_000,
                    capture_class="warm_concurrent",
                    geometry_group="same-fov",
                    orientation="normal",
                    mirrored=False,
                    same_fov=True,
                ),
            ),
        )
        assert (
            repository.refresh_camera_node_pending_setup_cameras(
                pending.pairing_token, [refreshed]
            )
            is True
        )
        selected = repository.resolve_camera_node_pending_pairing(
            pending.pairing_token, camera_id="picamera2-camera-0"
        )
        assert selected is not None
        assert selected.cameras[0].capture_profiles[0].profile_id == "opaque-monitoring"
        assert selected.credential == "local-only-credential"
        assert "local-only-credential" not in str(selected.cameras)
    finally:
        repository.close()


def test_profile_refresh_waits_for_a_proven_warm_concurrent_pair() -> None:
    pending_monitoring = CameraNodeCaptureProfile(
        profile_id="opaque-monitoring",
        purposes=("monitoring",),
        width=1920,
        height=1080,
        jpeg_supported=True,
        max_expected_bytes=1_500_000,
        capture_class="warm",
        geometry_group="same-fov",
        orientation="normal",
        mirrored=False,
        same_fov=True,
    )
    pending_evidence = CameraNodeCaptureProfile(
        profile_id="opaque-evidence",
        purposes=("evidence",),
        width=4624,
        height=3472,
        jpeg_supported=True,
        max_expected_bytes=16_000_000,
        capture_class="reconfiguration_required",
        geometry_group="same-fov",
        orientation="normal",
        mirrored=False,
        same_fov=True,
    )
    selected = api_main._camera_node_profile_selection(
        CameraNodeCamera(
            "picamera2-camera-0", "Pi camera", "available", True,
            capture_profiles=(pending_monitoring, pending_evidence),
        )
    )
    assert selected[0] is pending_monitoring
    assert selected[1] is pending_evidence
    assert api_main._camera_node_has_warm_profile_pair(
        CameraNodeCamera(
            "picamera2-camera-0", "Pi camera", "available", True,
            capture_profiles=(pending_monitoring, pending_evidence),
        )
    ) is False


def test_picamera2_failed_initialization_releases_partial_camera_and_concurrent_capture_is_bounded() -> None:
    class Camera:
        def __init__(self): self.stopped = self.closed = False
        def create_still_configuration(self, **_kwargs): return object()
        def configure(self, _configuration): raise RuntimeError("raw setup text")
        def stop(self): self.stopped = True
        def close(self): self.closed = True
    class Picamera2:
        camera = Camera()
        @staticmethod
        def global_camera_info(): return [{}]
        def __new__(cls, _index): return cls.camera
    module = type("Module", (), {"Picamera2": Picamera2})
    provider = PiCamera2Provider(_node_config(provider_key="picamera2"), module=module, cv2_module=object())
    with pytest.raises(ValueError, match="camera_initialization_failed"):
        provider.snapshot("picamera2-camera-0")
    assert Picamera2.camera.stopped and Picamera2.camera.closed
    provider._lock.acquire()
    try:
        with pytest.raises(ValueError, match="camera_busy"):
            provider.snapshot("picamera2-camera-0")
    finally:
        provider._lock.release()


def test_composite_provider_keeps_other_camera_available_when_one_fails() -> None:
    class Failing:
        def cameras(self): return [NodeCamera("v4l2-camera-0", "Linux camera 1", "unavailable", provider_type="v4l2")]
        def snapshot(self, _camera_id): raise ValueError("camera_unavailable")
        def close(self): return None
    provider = CompositeCameraProvider([Failing(), SyntheticCameraProvider()])
    assert provider.snapshot("synthetic-camera-1").startswith(b"\xff\xd8")
    assert provider.cameras()[1].provider_type == "synthetic"


def test_node_snapshot_failure_stops_for_durable_bounded_recovery() -> None:
    class UnavailableClient:
        def snapshot(self, **_kwargs):
            raise CameraNodeClientError("authentication_rejected")

    class Configuration:
        stream_id = "node-stream"
        camera_node_base_address = "http://127.0.0.1:8787"
        camera_node_credential = "masked-local-only"
        camera_node_camera_id = "opaque-camera-1"

    process = CameraNodeSnapshotProcess(Configuration(), client=UnavailableClient())
    assert process.wait(timeout=1) == 1
    assert process.safe_failure_code == "authentication_rejected"
    assert process.stdout.read() == b""


def test_monitoring_bridge_waits_for_a_warming_selected_profile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    jpeg = b"\xff\xd8\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x11\x00\xff\xd9"
    profile = CameraNodeCaptureProfile(
        profile_id="monitoring-opaque",
        purposes=("monitoring",),
        width=1920,
        height=1440,
        jpeg_supported=True,
        max_expected_bytes=1_500_000,
        capture_class="warm_concurrent",
        geometry_group="same-fov",
        orientation="normal",
        mirrored=False,
        same_fov=True,
    )

    class WarmingClient:
        def __init__(self) -> None:
            self.camera_calls = 0
            self.captured = threading.Event()

        def cameras(self, **_kwargs):
            self.camera_calls += 1
            profiles = () if self.camera_calls == 1 else (profile,)
            readiness = "warming" if self.camera_calls == 1 else "ready"
            return [
                CameraNodeCamera(
                    "opaque-camera-1",
                    "Feeder view",
                    "available",
                    True,
                    capture_profiles=profiles,
                    capture_readiness=readiness,
                )
            ]

        def capture(self, **kwargs):
            assert kwargs["profile"].profile_id == "monitoring-opaque"
            self.captured.set()
            return type("Capture", (), {"image": jpeg})()

    class Configuration:
        stream_id = "node-stream"
        camera_node_base_address = "http://127.0.0.1:8787"
        camera_node_credential = "masked-local-only"
        camera_node_camera_id = "opaque-camera-1"
        camera_node_monitoring_profile_id = "monitoring-opaque"

    monkeypatch.setattr(
        "mockingbird.playback.camera_node_bridge.PROFILE_LOOKUP_RETRY_DELAY_SECONDS",
        0.01,
        raising=False,
    )
    client = WarmingClient()
    process = CameraNodeSnapshotProcess(Configuration(), client=client)
    assert client.captured.wait(timeout=1)
    process.terminate()
    assert process.wait(timeout=1) == 0
    assert process.safe_failure_code is None
    assert client.camera_calls == 2
    assert process.stdout.read() == jpeg
def test_client_clamps_optional_snapshot_hint_and_old_nodes_keep_the_default() -> None:
    requester = _FakeNodeRequester()
    client = CameraNodeClient(requester=requester)
    pairing = client.pair("http://127.0.0.1:8787", "correct-one-time-code")
    assert pairing.recommended_snapshot_timeout_seconds == 8.0
    client.snapshot(
        base_address=pairing.base_address,
        credential=pairing.credential,
        camera_id="opaque-camera-1",
        recommended_timeout_seconds=99.0,
    )
    assert requester.timings[-1].connect_timeout_seconds == 2.0
    assert requester.timings[-1].response_timeout_seconds == 10.0
    assert requester.timings[-1].maximum_seconds == 10.0

    class OldNodeRequester(_FakeNodeRequester):
        def request(self, **kwargs):
            if kwargs["url"].endswith("/capabilities"):
                self.requests.append((kwargs["method"], kwargs["url"], kwargs["headers"]))
                self.timings.append(kwargs["timing"])
                return 404, {"Content-Type": "application/json"}, b"{}"
            return super().request(**kwargs)

    old_requester = OldNodeRequester()
    old_pairing = CameraNodeClient(requester=old_requester).pair("http://127.0.0.1:8787", "correct-one-time-code")
    assert old_pairing.recommended_snapshot_timeout_seconds is None


def test_monitoring_bridge_uses_the_same_default_snapshot_timing() -> None:
    class RecordingRequester(_FakeNodeRequester):
        def __init__(self):
            super().__init__()
            self.snapshot_requested = threading.Event()
        def request(self, **kwargs):
            result = super().request(**kwargs)
            if "/snapshot" in kwargs["url"]:
                self.snapshot_requested.set()
            return result

    class Configuration:
        stream_id = "node-stream"
        camera_node_base_address = "http://127.0.0.1:8787"
        camera_node_credential = "masked-local-only"
        camera_node_camera_id = "opaque-camera-1"

    requester = RecordingRequester()
    process = CameraNodeSnapshotProcess(Configuration(), client=CameraNodeClient(requester=requester))
    assert requester.snapshot_requested.wait(timeout=1)
    process.terminate()
    assert process.wait(timeout=1) == 0
    timing = next(item for item, request in zip(requester.timings, requester.requests) if "/snapshot" in request[1])
    assert timing.response_timeout_seconds == 8.0
    assert timing.maximum_seconds == 10.0


@pytest.mark.anyio
async def test_node_requires_authentication_and_one_time_pairing_is_bounded() -> None:
    config = CameraNodeConfig(
        display_name="Synthetic Node",
        bind_host="127.0.0.1",
        port=8787,
        provider_key="synthetic",
        camera_identifier=None,
        max_image_bytes=1_500_000,
        max_image_width=1920,
        max_image_height=1080,
        pairing_ttl_seconds=60,
        max_preview_viewers=0,
        testing=True,
    )
    node = create_node_app(config, provider=SyntheticCameraProvider())
    transport = httpx.ASGITransport(app=node)
    async with httpx.AsyncClient(transport=transport, base_url="http://node") as client:
        unauthenticated = await client.get("/node/v1/cameras")
        assert unauthenticated.status_code == 401
        paired = await client.post("/node/v1/pair", json={"pairing_code": node.state.pairing_code})
        assert paired.status_code == 200
        credential = paired.json()["credential"]
        assert credential not in (await client.get("/node/v1/health")).text
        repeated = await client.post("/node/v1/pair", json={"pairing_code": node.state.pairing_code})
        assert repeated.status_code == 409
        snapshot = await client.get(
            "/node/v1/cameras/synthetic-camera-1/snapshot",
            headers={"Authorization": f"Bearer {credential}"},
        )
        assert snapshot.status_code == 200
        assert snapshot.headers["content-type"].startswith("image/jpeg")
        revoked = await client.post("/node/v1/pair/revoke", headers={"Authorization": f"Bearer {credential}"})
        assert revoked.status_code == 204
        assert (await client.get("/node/v1/cameras", headers={"Authorization": f"Bearer {credential}"})).status_code == 401


@pytest.mark.anyio
async def test_pairing_verifier_survives_node_restart_without_storing_bearer(tmp_path) -> None:
    state_path = tmp_path / "pairing.json"
    config = CameraNodeConfig(
        display_name="Persistent Synthetic Node",
        bind_host="127.0.0.1",
        port=8787,
        provider_key="synthetic",
        camera_identifier=None,
        max_image_bytes=1_500_000,
        max_image_width=1920,
        max_image_height=1080,
        pairing_ttl_seconds=60,
        max_preview_viewers=0,
        testing=True,
        pairing_state_path=state_path,
    )
    first_node = create_node_app(config, provider=SyntheticCameraProvider())
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=first_node),
        base_url="http://node",
    ) as client:
        paired = await client.post(
            "/node/v1/pair", json={"pairing_code": first_node.state.pairing_code}
        )
        assert paired.status_code == 200
        credential = paired.json()["credential"]
        assert (await client.get("/node/v1/health")).json()["pairing_required"] is False

    persisted = state_path.read_text(encoding="utf-8")
    assert credential not in persisted
    assert len(json.loads(persisted)["credential_sha256"]) == 64

    restarted_node = create_node_app(config, provider=SyntheticCameraProvider())
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=restarted_node),
        base_url="http://node",
    ) as client:
        preserved = await client.get(
            "/node/v1/cameras", headers={"Authorization": f"Bearer {credential}"}
        )
        assert preserved.status_code == 200
        assert (await client.get("/node/v1/health")).json()["pairing_required"] is False
        replacement = await client.post(
            "/node/v1/pair", json={"pairing_code": restarted_node.state.pairing_code}
        )
        assert replacement.status_code == 409
        revoked = await client.post(
            "/node/v1/pair/revoke", headers={"Authorization": f"Bearer {credential}"}
        )
        assert revoked.status_code == 204

    revoked_node = create_node_app(config, provider=SyntheticCameraProvider())
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=revoked_node),
        base_url="http://node",
    ) as client:
        assert (
            await client.get(
                "/node/v1/cameras", headers={"Authorization": f"Bearer {credential}"}
            )
        ).status_code == 401
        assert (await client.get("/node/v1/health")).json()["pairing_required"] is True
        repaired = await client.post(
            "/node/v1/pair", json={"pairing_code": revoked_node.state.pairing_code}
        )
        assert repaired.status_code == 200
        replacement_credential = repaired.json()["credential"]
        assert replacement_credential != credential
        assert (
            await client.get(
                "/node/v1/cameras",
                headers={"Authorization": f"Bearer {replacement_credential}"},
            )
        ).status_code == 200
        assert (
            await client.get(
                "/node/v1/cameras", headers={"Authorization": f"Bearer {credential}"}
            )
        ).status_code == 401


def test_pairing_verifier_file_is_private_and_hash_only() -> None:
    with tempfile.TemporaryDirectory(dir="/tmp") as temporary_directory:
        state_path = Path(temporary_directory) / "pairing.json"
        pairing = _PairingState(60, state_path=state_path)
        credential = pairing.pair(pairing.code)
        persisted = state_path.read_text(encoding="utf-8")
        assert credential not in persisted
        assert len(json.loads(persisted)["credential_sha256"]) == 64
        assert state_path.stat().st_mode & 0o777 == 0o600


@pytest.mark.anyio
async def test_capture_profiles_are_advertised_and_capture_rejects_unlisted_profile_ids() -> None:
    jpeg = b"\xff\xd8\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x11\x00\xff\xd9"

    class ProfiledProvider:
        captured_profile_ids: list[str] = []

        def cameras(self):
            return [
                NodeCamera(
                    "opaque-camera-1",
                    "Feeder view",
                    "available",
                    snapshot_supported=True,
                    provider_type="test",
                )
            ]

        def capture_profiles(self, camera_id):
            assert camera_id == "opaque-camera-1"
            return [
                NodeCaptureProfile(
                    profile_id="monitoring-opaque",
                    purposes=("monitoring", "preview"),
                    width=1920,
                    height=1080,
                    jpeg_supported=True,
                    max_expected_bytes=1_500_000,
                    capture_class="warm",
                    geometry_group="same-fov",
                    same_fov=True,
                ),
                NodeCaptureProfile(
                    profile_id="evidence-opaque",
                    purposes=("evidence",),
                    width=9152,
                    height=6944,
                    jpeg_supported=True,
                    max_expected_bytes=16_000_000,
                    capture_class="reconfiguration",
                    geometry_group="same-fov",
                    same_fov=True,
                ),
            ]

        def capture_readiness(self, _camera_id):
            return "ready"

        def capture_profile_status(self, _camera_id):
            return [
                {
                    "profile_id": "candidate-opaque",
                    "state": "rejected_resource",
                    "raw_error": "must-not-leave-node",
                }
            ]

        def snapshot(self, camera_id, *, profile_id=None):
            assert camera_id == "opaque-camera-1"
            assert profile_id is not None
            self.captured_profile_ids.append(profile_id)
            return NodeCaptureResult(jpeg, monitoring_recovery="reset_required")

        def close(self):
            return None

    node = create_node_app(_node_config(), provider=ProfiledProvider())
    transport = httpx.ASGITransport(app=node)
    async with httpx.AsyncClient(transport=transport, base_url="http://node") as client:
        paired = await client.post("/node/v1/pair", json={"pairing_code": node.state.pairing_code})
        credential = paired.json()["credential"]
        headers = {"Authorization": f"Bearer {credential}"}
        cameras = await client.get("/node/v1/cameras", headers=headers)
        camera_payload = cameras.json()["items"][0]
        profiles = camera_payload["capture_profiles"]
        assert {profile["profile_id"] for profile in profiles} == {
            "monitoring-opaque",
            "evidence-opaque",
        }
        assert camera_payload["capture_readiness"] == "ready"
        assert camera_payload["capture_profile_status"] == [{
            "profile_id": "candidate-opaque",
            "state": "rejected_resource",
        }]
        rejected = await client.post(
            "/node/v1/cameras/opaque-camera-1/capture",
            headers=headers,
            json={"profile_id": "not-allowed"},
        )
        assert rejected.status_code == 409
        captured = await client.post(
            "/node/v1/cameras/opaque-camera-1/capture",
            headers=headers,
            json={"profile_id": "evidence-opaque"},
        )
    assert captured.status_code == 200
    assert captured.headers["x-mockingbird-capture-profile"] == "evidence-opaque"
    assert captured.headers["x-mockingbird-monitoring-recovery"] == "reset_required"
    assert ProfiledProvider.captured_profile_ids == ["evidence-opaque"]


@pytest.mark.anyio
async def test_capture_distinguishes_an_unadvertised_profile_from_session_failure() -> None:
    class FailingWarmSessionProvider:
        def cameras(self):
            return [
                NodeCamera(
                    "opaque-camera-1",
                    "Feeder view",
                    "available",
                    snapshot_supported=True,
                    provider_type="test",
                )
            ]

        def capture_profiles(self, _camera_id):
            return [
                NodeCaptureProfile(
                    profile_id="monitoring-opaque",
                    purposes=("monitoring",),
                    width=1920,
                    height=1440,
                    jpeg_supported=True,
                    max_expected_bytes=1_500_000,
                    capture_class="warm_concurrent",
                    geometry_group="same-fov",
                    same_fov=True,
                )
            ]

        def snapshot(self, _camera_id, *, profile_id=None):
            assert profile_id == "monitoring-opaque"
            raise ValueError("provider_session_failed")

        def close(self):
            return None

    node = create_node_app(
        _node_config(), provider=FailingWarmSessionProvider()
    )
    transport = httpx.ASGITransport(app=node)
    async with httpx.AsyncClient(transport=transport, base_url="http://node") as client:
        paired = await client.post(
            "/node/v1/pair", json={"pairing_code": node.state.pairing_code}
        )
        headers = {"Authorization": f"Bearer {paired.json()['credential']}"}
        unknown = await client.post(
            "/node/v1/cameras/opaque-camera-1/capture",
            headers=headers,
            json={"profile_id": "not-advertised"},
        )
        failed_session = await client.post(
            "/node/v1/cameras/opaque-camera-1/capture",
            headers=headers,
            json={"profile_id": "monitoring-opaque"},
        )

    assert unknown.status_code == 409
    assert unknown.headers["x-mockingbird-node-error"] == "profile_not_advertised"
    assert failed_session.status_code == 503
    assert (
        failed_session.headers["x-mockingbird-node-error"]
        == "provider_session_failed"
    )

@pytest.mark.anyio
async def test_capture_rejects_invalid_jpeg_even_when_provider_reports_recovery() -> None:
    class InvalidProvider:
        def cameras(self):
            return [
                NodeCamera(
                    "opaque-camera-1", "Feeder view", "available",
                    snapshot_supported=True, provider_type="test",
                )
            ]

        def capture_profiles(self, _camera_id):
            return [
                NodeCaptureProfile(
                    profile_id="evidence-opaque", purposes=("evidence",),
                    width=3840, height=2160, jpeg_supported=True,
                    max_expected_bytes=16_000_000,
                    capture_class="reconfiguration", geometry_group="same-fov",
                    same_fov=True,
                )
            ]

        def snapshot(self, _camera_id, *, profile_id=None):
            assert profile_id == "evidence-opaque"
            return NodeCaptureResult(b"not-a-jpeg", monitoring_recovery="reset_required")

        def close(self): return None

    node = create_node_app(_node_config(), provider=InvalidProvider())
    transport = httpx.ASGITransport(app=node)
    async with httpx.AsyncClient(transport=transport, base_url="http://node") as client:
        paired = await client.post("/node/v1/pair", json={"pairing_code": node.state.pairing_code})
        response = await client.post(
            "/node/v1/cameras/opaque-camera-1/capture",
            headers={"Authorization": f"Bearer {paired.json()['credential']}"},
            json={"profile_id": "evidence-opaque"},
        )
    assert response.status_code == 503
    assert response.headers["x-mockingbird-node-error"] == "node_snapshot_invalid"
    assert response.content != b"not-a-jpeg"


def test_client_accepts_old_capture_response_without_recovery_metadata() -> None:
    jpeg = b"\xff\xd8\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x11\x00\xff\xd9"

    class OldNodeRequester(_FakeNodeRequester):
        def request(self, **kwargs):
            if kwargs["url"].endswith("/capture"):
                return (
                    200,
                    {
                        "Content-Type": "image/jpeg",
                        "X-MockingBird-Capture-Profile": "evidence-opaque",
                    },
                    jpeg,
                )
            return super().request(**kwargs)

    capture = CameraNodeClient(requester=OldNodeRequester()).capture(
        base_address="http://127.0.0.1:8787",
        credential="local-only",
        camera_id="opaque-camera-1",
        profile=CameraNodeCaptureProfile(
            profile_id="evidence-opaque",
            purposes=("evidence",),
            width=3840,
            height=2160,
            jpeg_supported=True,
            max_expected_bytes=16_000_000,
            capture_class="reconfiguration",
            geometry_group="same-fov",
            orientation="normal",
            mirrored=False,
            same_fov=True,
        ),
    )
    assert capture.image == jpeg
    assert capture.monitoring_recovery is None

    class RecoveringNodeRequester(OldNodeRequester):
        def request(self, **kwargs):
            status, headers, data = super().request(**kwargs)
            if kwargs["url"].endswith("/capture"):
                headers["X-MockingBird-Monitoring-Recovery"] = "reset_required"
            return status, headers, data

    recovered_capture = CameraNodeClient(requester=RecoveringNodeRequester()).capture(
        base_address="http://127.0.0.1:8787",
        credential="local-only",
        camera_id="opaque-camera-1",
        profile=CameraNodeCaptureProfile(
            profile_id="evidence-opaque",
            purposes=("evidence",),
            width=3840,
            height=2160,
            jpeg_supported=True,
            max_expected_bytes=16_000_000,
            capture_class="reconfiguration",
            geometry_group="same-fov",
            orientation="normal",
            mirrored=False,
            same_fov=True,
        ),
    )
    assert recovered_capture.monitoring_recovery == "reset_required"


@pytest.mark.anyio
async def test_unauthenticated_snapshot_never_initializes_a_picamera2_instance() -> None:
    class Picamera2:
        initialized = 0
        @staticmethod
        def global_camera_info(): return [{}]
        def __new__(cls, _index):
            cls.initialized += 1
            return object.__new__(cls)
    module = type("Module", (), {"Picamera2": Picamera2})
    provider = PiCamera2Provider(_node_config(provider_key="picamera2"), module=module, cv2_module=object())
    node = create_node_app(_node_config(provider_key="picamera2"), provider=provider)
    transport = httpx.ASGITransport(app=node)
    async with httpx.AsyncClient(transport=transport, base_url="http://node") as client:
        response = await client.get("/node/v1/cameras/picamera2-camera-0/snapshot")
    assert response.status_code == 401
    assert Picamera2.initialized == 0


@pytest.mark.anyio
async def test_node_snapshot_errors_are_sanitized_and_include_only_safe_codes() -> None:
    class FailingProvider:
        def cameras(self): return [NodeCamera("opaque-camera-1", "Pi camera 1", "available", snapshot_supported=True, provider_type="picamera2")]
        def snapshot(self, _camera_id): raise ValueError("camera_capture_timeout")
        def close(self): return None

    node = create_node_app(_node_config(), provider=FailingProvider())
    transport = httpx.ASGITransport(app=node)
    async with httpx.AsyncClient(transport=transport, base_url="http://node") as client:
        paired = await client.post("/node/v1/pair", json={"pairing_code": node.state.pairing_code})
        credential = paired.json()["credential"]
        snapshot = await client.get("/node/v1/cameras/opaque-camera-1/snapshot", headers={"Authorization": f"Bearer {credential}"})
    assert snapshot.status_code == 503
    assert snapshot.headers["x-mockingbird-node-error"] == "node_snapshot_timeout"
    assert "camera_capture_timeout" not in snapshot.text
    assert "/dev/" not in snapshot.text


@pytest.mark.anyio
async def test_pairing_guided_setup_keeps_credential_masked_and_creates_no_truth(tmp_path) -> None:
    repository = _repository(tmp_path)
    requester = _FakeNodeRequester()
    api_main._camera_node_client = CameraNodeClient(requester=requester)
    configure_repository(repository)
    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            before = _counts(repository)
            pair = await client.post("/api/camera-nodes/pair", json={"base_address": "http://127.0.0.1:8787", "pairing_code": "correct-one-time-code"})
            assert pair.status_code == 200
            assert "never-echo-node-credential" not in pair.text
            token = pair.json()["pairing_token"]
            assert _counts(repository) == before

            preview = await client.post(
                "/api/camera-nodes/preview",
                json={"pairing_token": token, "camera_id": "opaque-camera-1"},
            )
            assert preview.status_code == 200
            assert preview.headers["content-type"].startswith("image/jpeg")
            assert preview.headers["cache-control"] == "no-store"
            assert _counts(repository) == before

            validation = await client.post("/api/camera-setup/validate", json={
                "provider_key": "camera_node",
                "config": {"node_camera_id": "opaque-camera-1"},
                "node_pairing_token": token,
            })
            assert validation.status_code == 200
            assert validation.json()["can_continue"] is True
            assert "127.0.0.1" not in validation.text
            assert "never-echo-node-credential" not in validation.text
            assert _counts(repository) == before

            complete_payload = {
                "camera_name": "Node feeder camera",
                "stream_name": "Node feeder view",
                "provider_key": "camera_node",
                "config": {"node_camera_id": "opaque-camera-1"},
                "node_pairing_token": token,
                "zones": [{"name": "Feeder", "zone_type": "feeder", "polygon": [{"x": 0.2, "y": 0.2}, {"x": 0.8, "y": 0.2}, {"x": 0.8, "y": 0.8}, {"x": 0.2, "y": 0.8}]}],
                "enable_monitoring": False,
                "idempotency_key": "camera-node-setup-001",
            }
            completed = await client.post("/api/camera-setup/complete", json=complete_payload)
            assert completed.status_code == 200
            assert completed.json()["monitoring_policy"]["mode"] == "off"
            assert "never-echo-node-credential" not in completed.text
            stream_id = completed.json()["stream"]["id"]
            playback = await client.get(f"/api/streams/{stream_id}/playback")
            assert playback.status_code == 200
            assert playback.json()["supports_live_playback"] is True
            assert "127.0.0.1" not in playback.text

            with repository.session_factory() as session:
                stored = session.scalar(select(SourceProviderConfigurationModel))
                assert stored is not None
                config = json.loads(stored.config_json)
                assert config["node_credential"] == "never-echo-node-credential"
                assert config["node_pairing_state"] == "paired"
    finally:
        configure_repository(None)
        api_main._camera_node_client = None


@pytest.mark.anyio
async def test_timed_out_node_preview_creates_no_product_records_or_truth(tmp_path) -> None:
    class TimeoutRequester(_FakeNodeRequester):
        def request(self, **kwargs):
            if "/snapshot" in kwargs["url"]:
                self.requests.append((kwargs["method"], kwargs["url"], kwargs["headers"]))
                self.timings.append(kwargs["timing"])
                return 503, {"X-MockingBird-Node-Error": "node_snapshot_timeout"}, b'{"detail":"Camera snapshot timed out."}'
            return super().request(**kwargs)

    repository = _repository(tmp_path)
    api_main._camera_node_client = CameraNodeClient(requester=TimeoutRequester())
    configure_repository(repository)
    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            before = _counts(repository)
            pairing = await client.post("/api/camera-nodes/pair", json={"base_address": "http://127.0.0.1:8787", "pairing_code": "correct-one-time-code"})
            preview = await client.post("/api/camera-nodes/preview", json={"pairing_token": pairing.json()["pairing_token"], "camera_id": "opaque-camera-1"})
            assert preview.status_code == 502
            assert "timed out" in preview.json()["detail"].lower()
            assert "never-echo-node-credential" not in preview.text
            assert _counts(repository) == before
    finally:
        configure_repository(None)
        api_main._camera_node_client = None


@pytest.mark.anyio
async def test_disappeared_camera_cannot_complete_node_setup(tmp_path) -> None:
    class DisappearedRequester(_FakeNodeRequester):
        def request(self, **kwargs):
            if kwargs["url"].endswith("/cameras"):
                return 200, {"Content-Type": "application/json"}, b'{"items": []}'
            return super().request(**kwargs)

    repository = _repository(tmp_path)
    api_main._camera_node_client = CameraNodeClient(requester=DisappearedRequester())
    configure_repository(repository)
    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            paired = await client.post("/api/camera-nodes/pair", json={"base_address": "http://127.0.0.1:8787", "pairing_code": "correct-one-time-code"})
            before = _counts(repository)
            completed = await client.post("/api/camera-setup/complete", json={
                "camera_name": "Missing Node camera", "stream_name": "Missing Node view", "provider_key": "camera_node",
                "config": {"node_camera_id": "opaque-camera-1"}, "node_pairing_token": paired.json()["pairing_token"],
                "zones": [{"name": "Yard", "zone_type": "yard", "polygon": [{"x": 0.2, "y": 0.2}, {"x": 0.8, "y": 0.2}, {"x": 0.8, "y": 0.8}, {"x": 0.2, "y": 0.8}]}],
                "enable_monitoring": False, "idempotency_key": "camera-node-disappeared-camera",
            })
            assert completed.status_code == 400
            assert _counts(repository) == before
    finally:
        configure_repository(None)
        api_main._camera_node_client = None


@pytest.mark.anyio
async def test_node_repair_uses_in_place_preview_and_explicit_revocation(tmp_path) -> None:
    repository = _repository(tmp_path)
    api_main._camera_node_client = CameraNodeClient(requester=_FakeNodeRequester())
    configure_repository(repository)
    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            pairing = await client.post("/api/camera-nodes/pair", json={"base_address": "http://127.0.0.1:8787", "pairing_code": "first-code"})
            token = pairing.json()["pairing_token"]
            created = await client.post("/api/camera-setup/complete", json={
                "camera_name": "Repairable Node camera", "stream_name": "Node view", "provider_key": "camera_node",
                "config": {"node_camera_id": "opaque-camera-1"}, "node_pairing_token": token,
                "zones": [{"name": "Yard", "zone_type": "yard", "polygon": [{"x": 0.2, "y": 0.2}, {"x": 0.8, "y": 0.2}, {"x": 0.8, "y": 0.8}, {"x": 0.2, "y": 0.8}]}],
                "enable_monitoring": False, "idempotency_key": "camera-node-repair-setup",
            })
            assert created.status_code == 200
            stream_id = created.json()["stream"]["id"]
            source_id = created.json()["source"]["id"]
            edit = await client.get(f"/api/streams/{stream_id}/camera-configuration")
            repair_pairing = await client.post("/api/camera-nodes/pair", json={"base_address": "http://127.0.0.1:8787", "pairing_code": "repair-code"})
            repair_token = repair_pairing.json()["pairing_token"]
            preview = await client.post(f"/api/streams/{stream_id}/camera-configuration/preview", json={
                "provider_key": "camera_node", "config": {"node_camera_id": "opaque-camera-1"}, "secret_actions": {},
                "node_pairing_token": repair_token, "expected_state_token": edit.json()["state_token"],
            })
            assert preview.status_code == 200
            # Re-pairing to the same advertised Node/camera leaves the existing
            # runtime configuration intact; a changed credential would require restart.
            assert preview.json()["restart_required"] is False
            assert "127.0.0.1" not in preview.text
            applied = await client.post(f"/api/streams/{stream_id}/camera-configuration/apply", json={
                "provider_key": "camera_node", "config": {"node_camera_id": "opaque-camera-1"}, "secret_actions": {},
                "node_pairing_token": repair_token, "expected_state_token": edit.json()["state_token"],
                "preview_token": preview.json()["preview_token"], "idempotency_key": "camera-node-repair-apply", "restart_monitoring": False,
            })
            assert applied.status_code == 200
            assert applied.json()["configuration"]["source_id"] == source_id
            assert "never-echo-node-credential" not in applied.text
            revoked = await client.post("/api/camera-nodes/pair/revoke", json={"stream_id": stream_id})
            assert revoked.status_code == 204
            after = await client.get(f"/api/streams/{stream_id}/camera-configuration")
            assert after.status_code == 200
            assert after.json()["field_states"]["node_credential"] == "not_configured"
            assert "never-echo-node-credential" not in after.text
    finally:
        configure_repository(None)
        api_main._camera_node_client = None


def test_schema_v24_adds_no_camera_node_configuration_to_existing_sources(tmp_path) -> None:
    database_path = tmp_path / "migration.sqlite3"
    engine = create_database_engine(f"sqlite:///{database_path}")
    try:
        status = initialize_database(engine)
        assert status.version == CURRENT_DATABASE_SCHEMA_VERSION == 32
        with engine.connect() as connection:
            count = connection.exec_driver_sql("SELECT COUNT(*) FROM source_provider_configurations WHERE provider_key = 'camera_node'").scalar_one()
        assert count == 0
    finally:
        engine.dispose()
