"""Bounded local camera providers for the Camera Node, below product contracts."""

from __future__ import annotations

from dataclasses import dataclass
import re
import threading
from pathlib import Path
from typing import Any, Callable, Protocol

from .config import CameraNodeConfig


MAX_CAMERAS = 8
CAPTURE_LOCK_TIMEOUT_SECONDS = 0.5
CAPTURE_TIMEOUT_SECONDS = 3.0
_VIDEO_DEVICE = re.compile(r"^video([0-9]{1,3})$")
_SYNTHETIC_JPEG = b"\xff\xd8\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x11\x00\xff\xd9"


@dataclass(frozen=True)
class NodeCamera:
    camera_id: str
    display_name: str
    status: str
    setup_hint: str | None = None
    snapshot_supported: bool = False
    provider_type: str = "local"


class CameraNodeProvider(Protocol):
    def cameras(self) -> list[NodeCamera]: ...
    def snapshot(self, camera_id: str) -> bytes: ...
    def close(self) -> None: ...


CameraProvider = CameraNodeProvider


class UnavailableCameraProvider:
    def __init__(self, *, provider_key: str, reason: str) -> None:
        self.provider_key, self.reason = provider_key, reason

    def cameras(self) -> list[NodeCamera]:
        return [NodeCamera(f"{self.provider_key}-setup-required", f"{self.provider_key.upper()} setup required", "setup_required", self.reason, provider_type=self.provider_key)]

    def snapshot(self, camera_id: str) -> bytes:
        raise ValueError("camera_setup_required")

    def close(self) -> None:
        return None


class SyntheticCameraProvider:
    CAMERA_ID = "synthetic-camera-1"

    def cameras(self) -> list[NodeCamera]:
        return [NodeCamera(self.CAMERA_ID, "Synthetic test camera", "available", snapshot_supported=True, provider_type="synthetic")]

    def snapshot(self, camera_id: str) -> bytes:
        if camera_id != self.CAMERA_ID:
            raise ValueError("camera_not_allowed")
        return _SYNTHETIC_JPEG

    def close(self) -> None:
        return None


def _cv2() -> Any | None:
    try:
        import cv2  # type: ignore[import-not-found]
    except ImportError:
        return None
    return cv2


def _bounded_call(callback: Callable[[], Any], *, failure_code: str) -> Any:
    """Bound one local provider operation; callers still release acquired handles."""

    result: list[Any] = []
    errors: list[BaseException] = []

    def run() -> None:
        try:
            result.append(callback())
        except BaseException as error:  # Provider exceptions stay Node-local.
            errors.append(error)

    worker = threading.Thread(target=run, daemon=True)
    worker.start()
    worker.join(CAPTURE_TIMEOUT_SECONDS)
    if worker.is_alive() or errors:
        raise ValueError(failure_code)
    return result[0] if result else None


def _v4l2_devices() -> list[tuple[int, str]]:
    try:
        entries = list(Path("/dev").iterdir())
    except OSError:
        return []
    devices = [(int(match.group(1)), str(entry)) for entry in entries if (match := _VIDEO_DEVICE.fullmatch(entry.name))]
    return sorted(devices)[:MAX_CAMERAS]


class V4L2CameraProvider:
    """Optional OpenCV-backed V4L2 snapshots with one lock and no retained handle."""

    def __init__(self, config: CameraNodeConfig, *, device_enumerator: Callable[[], list[tuple[int, str]]] = _v4l2_devices, cv2_module: Any | None = None) -> None:
        self._config, self._enumerate, self._cv2 = config, device_enumerator, cv2_module
        self._lock = threading.Lock()

    def _runtime(self) -> Any | None:
        return self._cv2 if self._cv2 is not None else _cv2()

    def _devices(self) -> dict[str, tuple[int, str]]:
        return {f"v4l2-camera-{index}": (index, path) for index, path in sorted(self._enumerate())[:MAX_CAMERAS]}

    def cameras(self) -> list[NodeCamera]:
        if self._runtime() is None:
            return UnavailableCameraProvider(provider_key="v4l2", reason="V4L2 snapshot support requires an already-installed local capture runtime.").cameras()
        return [NodeCamera(camera_id, f"Linux camera {index + 1}", "available", snapshot_supported=True, provider_type="v4l2") for camera_id, (index, _) in self._devices().items()] or [NodeCamera("v4l2-no-camera", "No Linux camera available", "unavailable", "Connect an allowed local V4L2 camera.", provider_type="v4l2")]

    def snapshot(self, camera_id: str) -> bytes:
        device = self._devices().get(camera_id)
        runtime = self._runtime()
        if device is None:
            raise ValueError("camera_not_allowed")
        if runtime is None:
            raise ValueError("camera_setup_required")
        if not self._lock.acquire(timeout=CAPTURE_LOCK_TIMEOUT_SECONDS):
            raise ValueError("camera_busy")
        capture: Any | None = None
        try:
            capture = runtime.VideoCapture(device[1])
            if not capture or not capture.isOpened():
                raise ValueError("camera_unavailable")
            capture.set(runtime.CAP_PROP_FRAME_WIDTH, self._config.max_image_width)
            capture.set(runtime.CAP_PROP_FRAME_HEIGHT, self._config.max_image_height)
            result = _bounded_call(capture.read, failure_code="camera_unusable_frame")
            if not result or not result[0]:
                raise ValueError("camera_unusable_frame")
            ok, encoded = runtime.imencode(".jpg", result[1])
            if not ok:
                raise ValueError("camera_unusable_frame")
            return encoded.tobytes() if hasattr(encoded, "tobytes") else bytes(encoded)
        except PermissionError as error:
            raise ValueError("camera_permission_denied") from error
        finally:
            if capture is not None:
                capture.release()
            self._lock.release()

    def close(self) -> None:
        return None


class PiCamera2Provider:
    def __init__(self, config: CameraNodeConfig, *, module: Any | None = None, cv2_module: Any | None = None) -> None:
        self._config, self._module, self._cv2, self._lock = config, module, cv2_module, threading.Lock()

    def _runtime(self) -> tuple[Any | None, Any | None]:
        module = self._module
        if module is False:
            return None, None
        if module is None:
            try:
                import picamera2 as module  # type: ignore[import-not-found]
            except ImportError:
                return None, None
        return module, self._cv2 if self._cv2 is not None else _cv2()

    def cameras(self) -> list[NodeCamera]:
        module, encoder = self._runtime()
        if module is None or encoder is None:
            return UnavailableCameraProvider(provider_key="picamera2", reason="PiCamera2 and a local image encoder must already be installed for this Node.").cameras()
        try:
            count = min(len(module.Picamera2.global_camera_info()), MAX_CAMERAS)
        except Exception:
            return [NodeCamera("picamera2-unavailable", "Pi camera unavailable", "unavailable", "Check the local Pi camera stack.", provider_type="picamera2")]
        return [NodeCamera(f"picamera2-camera-{index}", f"Pi camera {index + 1}", "available", snapshot_supported=True, provider_type="picamera2") for index in range(count)] or [NodeCamera("picamera2-no-camera", "No Pi camera available", "unavailable", "Connect a supported local Pi camera.", provider_type="picamera2")]

    def snapshot(self, camera_id: str) -> bytes:
        cameras = {camera.camera_id for camera in self.cameras() if camera.status == "available"}
        if camera_id not in cameras:
            raise ValueError("camera_not_allowed")
        module, encoder = self._runtime()
        if module is None or encoder is None:
            raise ValueError("camera_setup_required")
        if not self._lock.acquire(timeout=CAPTURE_LOCK_TIMEOUT_SECONDS):
            raise ValueError("camera_busy")
        camera: Any | None = None
        try:
            index = int(camera_id.rsplit("-", 1)[1])
            camera = _bounded_call(lambda: module.Picamera2(index), failure_code="camera_initialization_failed")
            camera.configure(camera.create_still_configuration(main={"size": (self._config.max_image_width, self._config.max_image_height), "format": "RGB888"}))
            _bounded_call(camera.start, failure_code="camera_initialization_failed")
            frame = _bounded_call(camera.capture_array, failure_code="camera_unusable_frame")
            ok, encoded = encoder.imencode(".jpg", frame)
            if not ok:
                raise ValueError("camera_unusable_frame")
            return encoded.tobytes() if hasattr(encoded, "tobytes") else bytes(encoded)
        except PermissionError as error:
            raise ValueError("camera_permission_denied") from error
        except ValueError:
            raise
        except Exception as error:
            raise ValueError("camera_initialization_failed") from error
        finally:
            if camera is not None:
                try:
                    camera.stop(); camera.close()
                except Exception:
                    pass
            self._lock.release()

    def close(self) -> None:
        return None


class CompositeCameraProvider:
    def __init__(self, providers: list[CameraNodeProvider]) -> None:
        self._providers = providers

    def cameras(self) -> list[NodeCamera]:
        return [camera for provider in self._providers for camera in provider.cameras()][:MAX_CAMERAS]

    def snapshot(self, camera_id: str) -> bytes:
        for provider in self._providers:
            if any(camera.camera_id == camera_id for camera in provider.cameras()):
                return provider.snapshot(camera_id)
        raise ValueError("camera_not_allowed")

    def close(self) -> None:
        for provider in self._providers:
            provider.close()


def create_camera_provider(config: CameraNodeConfig) -> CameraNodeProvider:
    keys = config.enabled_providers or (config.provider_key,)
    providers: list[CameraNodeProvider] = []
    for key in keys:
        if key == "synthetic": providers.append(SyntheticCameraProvider())
        elif key == "v4l2": providers.append(V4L2CameraProvider(config))
        elif key == "picamera2": providers.append(PiCamera2Provider(config))
        else: raise ValueError("mockingbird_node_provider_invalid")
    return providers[0] if len(providers) == 1 else CompositeCameraProvider(providers)
