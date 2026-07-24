"""Small local camera-provider boundary for the Camera Node.

Providers advertise opaque IDs only. The built-in real-device providers fail
closed when their optional host runtime is absent; this package never installs
drivers, invokes a shell, or accepts a device path over HTTP.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .config import CameraNodeConfig


# A deliberately tiny JPEG-shaped fixture with a bounded 1x1 SOF marker. The
# synthetic provider exists only for API/permission contract tests; it is not a
# stand-in for a physical-camera or motion-decoder test.
_SYNTHETIC_JPEG = b"\xff\xd8\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x11\x00\xff\xd9"


@dataclass(frozen=True)
class NodeCamera:
    camera_id: str
    display_name: str
    status: str
    setup_hint: str | None = None
    snapshot_supported: bool = False


class CameraProvider(Protocol):
    def cameras(self) -> list[NodeCamera]: ...
    def snapshot(self, camera_id: str) -> bytes: ...
    def close(self) -> None: ...


class UnavailableCameraProvider:
    def __init__(self, *, provider_key: str, reason: str) -> None:
        self.provider_key = provider_key
        self.reason = reason

    def cameras(self) -> list[NodeCamera]:
        return [NodeCamera(f"{self.provider_key}-setup-required", "Local camera setup required", "setup_required", self.reason)]

    def snapshot(self, camera_id: str) -> bytes:
        raise ValueError("camera_setup_required")

    def close(self) -> None:
        return None


class SyntheticCameraProvider:
    """Test-only provider; it never accesses a physical device or filesystem."""

    CAMERA_ID = "synthetic-camera-1"

    def cameras(self) -> list[NodeCamera]:
        return [NodeCamera(self.CAMERA_ID, "Synthetic test camera", "available", snapshot_supported=True)]

    def snapshot(self, camera_id: str) -> bytes:
        if camera_id != self.CAMERA_ID:
            raise ValueError("camera_not_allowed")
        return _SYNTHETIC_JPEG

    def close(self) -> None:
        return None


def create_camera_provider(config: CameraNodeConfig) -> CameraProvider:
    if config.provider_key == "synthetic":
        return SyntheticCameraProvider()
    if config.provider_key == "picamera2":
        try:
            import picamera2  # type: ignore[import-not-found]  # noqa: F401
        except ImportError:
            return UnavailableCameraProvider(provider_key="picamera2", reason="Raspberry Pi camera runtime is not installed on this Node.")
        return UnavailableCameraProvider(provider_key="picamera2", reason="Raspberry Pi camera capture is not enabled in this bounded Node build.")
    return UnavailableCameraProvider(provider_key="v4l2", reason="V4L2 capture setup is required; no camera command or driver is run by the Node.")
