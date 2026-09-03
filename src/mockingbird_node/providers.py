"""Bounded local camera providers for the Camera Node, below product contracts."""

from __future__ import annotations

from dataclasses import dataclass
import errno
import gc
from hashlib import sha1
from importlib import import_module
import re
import threading
from time import monotonic, sleep
from pathlib import Path
from typing import Any, Callable, Protocol

from .config import CameraNodeConfig


MAX_CAMERAS = 8
MAX_CAPTURE_PROFILES_PER_CAMERA = 12
CAPTURE_LOCK_TIMEOUT_SECONDS = 0.5
CAPTURE_TIMEOUT_SECONDS = 3.0
# Bounds one path's combined open+single-frame-read probe (see
# V4L2CameraProvider._is_capture_capable) -- deliberately tighter than
# CAPTURE_TIMEOUT_SECONDS's full-capture budget: a genuinely capture-capable
# device delivers a first frame quickly, and a short bound is itself part of
# the signal (Authenticated Camera Node Golden-Path Capture & Preview
# Acceptance v1: on the real reference Pi, a non-camera ISP pipeline-stage
# node can accept `isOpened()` while its `read()` blocks for ~10s before
# failing -- see that milestone's report).
V4L2_PROBE_TIMEOUT_SECONDS = 1.5
PICAMERA2_INITIALIZATION_TIMEOUT_SECONDS = 4.0
PICAMERA2_FRAME_TIMEOUT_SECONDS = 4.0
WARM_SESSION_READY_TIMEOUT_SECONDS = 5.0
WARM_MONITORING_TIMEOUT_SECONDS = 2.0
WARM_EVIDENCE_ACCEPTANCE_SECONDS = 1.5
WARM_EVIDENCE_TIMEOUT_SECONDS = 2.0
WARM_CANDIDATE_RECLAIM_SECONDS = 0.2
WARM_REQUIRED_PAIR_RETRY_DELAY_SECONDS = 0.2
MAX_ADVERTISED_CAPTURE_BYTES = 16_000_000
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


@dataclass(frozen=True)
class NodeCaptureProfile:
    """Safe, product-neutral capture metadata advertised by one Node camera."""

    profile_id: str
    purposes: tuple[str, ...]
    width: int
    height: int
    jpeg_supported: bool
    max_expected_bytes: int
    capture_class: str
    geometry_group: str | None
    orientation: str = "normal"
    mirrored: bool = False
    same_fov: bool = False

    def as_payload(self) -> dict[str, object]:
        return {
            "profile_id": self.profile_id,
            "purposes": list(self.purposes),
            "width": self.width,
            "height": self.height,
            "jpeg_supported": self.jpeg_supported,
            "max_expected_bytes": self.max_expected_bytes,
            "capture_class": self.capture_class,
            "geometry_group": self.geometry_group,
            "orientation": self.orientation,
            "mirrored": self.mirrored,
            "same_fov": self.same_fov,
        }


@dataclass(frozen=True)
class NodeCaptureResult:
    """One bounded JPEG plus the safe state of a profile restoration attempt."""

    image: bytes
    # ``None`` keeps legacy and warm-provider responses unchanged. A
    # reconfiguration capture may report only provider-neutral, safe outcomes.
    monitoring_recovery: str | None = None


@dataclass
class _ProfileCaptureTransaction:
    """Track one serialized profile transition without retaining camera details."""

    requested_profile_id: str
    active_profile_id: str | None
    state: str = "monitoring_ready"


@dataclass(frozen=True)
class _WarmConcurrentSession:
    """One provider-owned PiCamera2 session with two configured streams."""

    camera: Any
    monitoring_profile_id: str
    evidence_profile_id: str


@dataclass(frozen=True)
class _WarmCandidate:
    """One ordered, Node-local warm-session proof candidate."""

    monitoring: NodeCaptureProfile
    evidence: NodeCaptureProfile


@dataclass(frozen=True)
class _WarmCandidateStatus:
    """Sanitized outcome retained for one bounded warm-profile proof."""

    profile_id: str
    state: str

    def as_payload(self) -> dict[str, str]:
        return {"profile_id": self.profile_id, "state": self.state}


class _WarmCandidateFailure(ValueError):
    """An internal candidate rejection that is safe to classify, never expose."""

    def __init__(self, state: str) -> None:
        self.state = state
        super().__init__(state)


class CameraNodeProvider(Protocol):
    def cameras(self) -> list[NodeCamera]: ...
    def capture_profiles(self, camera_id: str) -> list[NodeCaptureProfile]: ...
    def snapshot(
        self, camera_id: str, *, profile_id: str | None = None
    ) -> bytes | NodeCaptureResult: ...
    def close(self) -> None: ...


CameraProvider = CameraNodeProvider


class UnavailableCameraProvider:
    def __init__(self, *, provider_key: str, reason: str) -> None:
        self.provider_key, self.reason = provider_key, reason

    def cameras(self) -> list[NodeCamera]:
        return [NodeCamera(f"{self.provider_key}-setup-required", f"{self.provider_key.upper()} setup required", "setup_required", self.reason, provider_type=self.provider_key)]

    def capture_profiles(self, camera_id: str) -> list[NodeCaptureProfile]:
        return []

    def snapshot(self, camera_id: str, *, profile_id: str | None = None) -> bytes:
        raise ValueError("camera_setup_required")

    def close(self) -> None:
        return None


class SyntheticCameraProvider:
    CAMERA_ID = "synthetic-camera-1"

    def cameras(self) -> list[NodeCamera]:
        return [NodeCamera(self.CAMERA_ID, "Synthetic test camera", "available", snapshot_supported=True, provider_type="synthetic")]

    def capture_profiles(self, camera_id: str) -> list[NodeCaptureProfile]:
        if camera_id != self.CAMERA_ID:
            return []
        return [
            NodeCaptureProfile(
                profile_id="synthetic-monitoring",
                purposes=("monitoring", "preview", "evidence"),
                width=1,
                height=1,
                jpeg_supported=True,
                max_expected_bytes=len(_SYNTHETIC_JPEG),
                capture_class="warm",
                geometry_group="synthetic-full-frame",
                same_fov=True,
            )
        ]

    def snapshot(self, camera_id: str, *, profile_id: str | None = None) -> bytes:
        if camera_id != self.CAMERA_ID:
            raise ValueError("camera_not_allowed")
        if profile_id not in {None, "synthetic-monitoring"}:
            raise ValueError("capture_profile_not_allowed")
        return _SYNTHETIC_JPEG

    def close(self) -> None:
        return None


def _cv2() -> Any | None:
    try:
        import cv2  # type: ignore[import-not-found]
    except ImportError:
        return None
    return cv2


def _encode_bounded_jpeg(encoder: Any, frame: Any, *, maximum_bytes: int) -> bytes:
    """Keep provider output inside the advertised profile bound without files."""

    for quality in (90, 82, 74, 66):
        try:
            ok, encoded = encoder.imencode(
                ".jpg",
                frame,
                [getattr(encoder, "IMWRITE_JPEG_QUALITY", 1), quality],
            )
        except TypeError:
            # Small test encoders and older local bindings may not accept JPEG
            # parameters; their response is still bounded before it leaves Node.
            ok, encoded = encoder.imencode(".jpg", frame)
        if not ok:
            continue
        image = encoded.tobytes() if hasattr(encoded, "tobytes") else bytes(encoded)
        if image and len(image) <= maximum_bytes:
            return image
    raise ValueError("camera_unusable_frame")


def _jpeg_frame(encoder: Any, frame: Any, *, yuv420: bool = False) -> Any:
    """Convert only the PiCamera2 low-cost YUV monitoring stream for JPEG."""

    if not yuv420:
        return frame
    conversion = getattr(encoder, "COLOR_YUV2BGR_I420", None)
    convert = getattr(encoder, "cvtColor", None)
    if conversion is None or not callable(convert):
        raise ValueError("camera_unusable_frame")
    return convert(frame, conversion)


def _bounded_call(
    callback: Callable[[], Any],
    *,
    failure_code: str,
    timeout_seconds: float = CAPTURE_TIMEOUT_SECONDS,
    timeout_code: str | None = None,
    late_cleanup: Callable[[Any], None] | None = None,
) -> Any:
    """Bound a local operation while eventually releasing a late-created resource."""

    result: list[Any] = []
    errors: list[BaseException] = []
    abandoned = threading.Event()

    def run() -> None:
        try:
            value = callback()
            if abandoned.is_set():
                if late_cleanup is not None:
                    late_cleanup(value)
            else:
                result.append(value)
        except BaseException as error:  # Provider exceptions stay Node-local.
            errors.append(error)

    worker = threading.Thread(target=run, daemon=True)
    worker.start()
    worker.join(timeout_seconds)
    if worker.is_alive():
        abandoned.set()
        raise ValueError(timeout_code or failure_code)
    if errors:
        if isinstance(errors[0], _WarmCandidateFailure):
            raise errors[0]
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
        self._capture_capable_cache: dict[str, bool] = {}

    def _runtime(self) -> Any | None:
        return self._cv2 if self._cv2 is not None else _cv2()

    def _devices(self) -> dict[str, tuple[int, str]]:
        return {f"v4l2-camera-{index}": (index, path) for index, path in sorted(self._enumerate())[:MAX_CAMERAS]}

    def _is_capture_capable(self, runtime: Any, path: str) -> bool:
        """Cheap, bounded, one-time-cached-per-path ground truth for whether
        `path` is a real, directly openable V4L2 *capture* device -- not
        merely a `/dev/videoN` character device that happens to exist.

        Camera Node diagnostic-truth defect (Camera / Source Release
        Hardware Validation Closure v1, reproduced against the real
        reference Camera Node): a Raspberry Pi's own internal ISP/codec/
        HEVC-decoder pipeline stages (`bcm2835-isp`, `bcm2835-codec-decode`,
        `rpi-hevc-dec`) -- and even its CSI sensor's own raw `unicam`
        capture node, which requires libcamera/picamera2, not plain V4L2 --
        register real `/dev/videoN` nodes unconditionally whenever the
        kernel driver stack is loaded, regardless of whether any
        independently V4L2-openable camera is attached. Device-node
        existence alone is therefore not evidence of camera availability;
        `self_test.camera_available` (`mockingbird_node.selftest`) trusted
        exactly this unconditional list, so a Node with `v4l2` enabled
        (the packaged installer default) could report a phantom camera
        "available" even while its real, specifically-configured camera was
        physically undetected -- the required invariant is that "some
        camera capability exists" must never silently become "the
        configured camera is currently available."

        Reuses the exact `VideoCapture(...).isOpened()` + `.read()` checks
        `snapshot()` already trusts as ground truth for a live capture
        (never a second, divergent openability signal) -- just performed
        once per path instead of only at actual-capture time, and wrapped in
        the same bounded-background-thread pattern (`_bounded_call`)
        already used elsewhere in this module so one truly wedged device
        cannot block enumeration for every other one, or for any caller of
        `cameras()`.

        Authenticated Camera Node Golden-Path Capture & Preview Acceptance
        v1: `isOpened()` alone is not sufficient. Reproduced live against
        this exact reference Pi immediately after deploying the
        `isOpened()`-only version of this fix: its `bcm2835-isp` pipeline
        -stage output nodes (internal ISP buffers `picamera2`/`libcamera`
        use while a real capture session is active, never independent
        cameras -- see the class docstring) can transiently accept a V4L2
        `open()` call while *no* frame is ever delivered -- `isOpened()`
        true, `read()` blocking for several seconds before failing. A path
        must now pass both checks -- matching the *full* ground truth
        `snapshot()` itself already required (it already raises
        `camera_unusable_frame` on exactly this same failed-read shape) --
        to be reported "available".

        Cached per path for this provider instance's lifetime: the
        capture-vs-pipeline-stage distinction being tested is a static
        kernel-driver/hardware fact, not one that changes while the process
        runs. (A genuine camera that is only transiently busy at the exact
        moment of this provider's first-ever `cameras()` call could be
        under-cached as not-capture-capable for the rest of the process
        lifetime -- a narrow, disclosed residual, and still strictly better
        than every enumerated path being unconditionally "available"
        forever, which was the prior behavior.)
        """

        cached = self._capture_capable_cache.get(path)
        if cached is not None:
            return cached

        def probe() -> bool:
            capture = runtime.VideoCapture(path)
            try:
                if not capture or not capture.isOpened():
                    return False
                result = capture.read()
                return bool(result and result[0])
            finally:
                if capture is not None:
                    capture.release()

        try:
            capable = bool(
                _bounded_call(
                    probe,
                    failure_code="camera_probe_failed",
                    timeout_seconds=V4L2_PROBE_TIMEOUT_SECONDS,
                )
            )
        except ValueError:
            capable = False
        self._capture_capable_cache[path] = capable
        return capable

    def cameras(self) -> list[NodeCamera]:
        runtime = self._runtime()
        if runtime is None:
            return UnavailableCameraProvider(provider_key="v4l2", reason="V4L2 snapshot support requires an already-installed local capture runtime.").cameras()
        cameras = [
            NodeCamera(camera_id, f"Linux camera {index + 1}", "available", snapshot_supported=True, provider_type="v4l2")
            for camera_id, (index, path) in self._devices().items()
            if self._is_capture_capable(runtime, path)
        ]
        return cameras or [NodeCamera("v4l2-no-camera", "No Linux camera available", "unavailable", "Connect an allowed local V4L2 camera.", provider_type="v4l2")]

    def capture_profiles(self, camera_id: str) -> list[NodeCaptureProfile]:
        if camera_id not in self._devices() or self._runtime() is None:
            return []
        return [
            NodeCaptureProfile(
                profile_id="v4l2-bounded-jpeg",
                purposes=("monitoring", "preview", "evidence"),
                width=self._config.max_image_width,
                height=self._config.max_image_height,
                jpeg_supported=True,
                max_expected_bytes=min(
                    self._config.max_image_bytes, MAX_ADVERTISED_CAPTURE_BYTES
                ),
                capture_class="warm",
                geometry_group=f"v4l2-{camera_id}-default",
                same_fov=True,
            )
        ]

    def snapshot(self, camera_id: str, *, profile_id: str | None = None) -> bytes:
        device = self._devices().get(camera_id)
        runtime = self._runtime()
        if device is None:
            raise ValueError("camera_not_allowed")
        if runtime is None:
            raise ValueError("camera_setup_required")
        profiles = {profile.profile_id: profile for profile in self.capture_profiles(camera_id)}
        if profile_id is not None and profile_id not in profiles:
            raise ValueError("capture_profile_not_allowed")
        profile = profiles.get(profile_id) if profile_id else next(iter(profiles.values()), None)
        if profile is None:
            raise ValueError("capture_profile_not_allowed")
        if not self._lock.acquire(timeout=CAPTURE_LOCK_TIMEOUT_SECONDS):
            raise ValueError("camera_busy")
        capture: Any | None = None
        try:
            capture = runtime.VideoCapture(device[1])
            if not capture or not capture.isOpened():
                raise ValueError("camera_unavailable")
            capture.set(runtime.CAP_PROP_FRAME_WIDTH, profile.width)
            capture.set(runtime.CAP_PROP_FRAME_HEIGHT, profile.height)
            result = _bounded_call(capture.read, failure_code="camera_unusable_frame")
            if not result or not result[0]:
                raise ValueError("camera_unusable_frame")
            return _encode_bounded_jpeg(
                runtime,
                result[1],
                maximum_bytes=profile.max_expected_bytes,
            )
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
        self._cameras: dict[str, Any] = {}
        self._camera_profile_ids: dict[str, str] = {}
        self._profile_cache: dict[str, tuple[NodeCaptureProfile, ...]] = {}
        self._warm_sessions: dict[str, _WarmConcurrentSession] = {}
        self._warm_readiness: dict[str, str] = {}
        self._warm_proofs: dict[str, threading.Thread] = {}
        self._warm_candidate_statuses: dict[
            str, tuple[_WarmCandidateStatus, ...]
        ] = {}

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

    @staticmethod
    def _enable_continuous_autofocus(camera: Any) -> None:
        """Apply a safe default focus policy without making it a Node dependency."""

        try:
            controls = getattr(import_module("libcamera"), "controls", None)
            autofocus = getattr(
                getattr(controls, "AfModeEnum", None), "Continuous", None
            )
            if autofocus is not None:
                camera.set_controls({"AfMode": autofocus})
        except Exception:
            # Camera Node remains usable on fixed-focus cameras and older
            # libcamera runtimes; the optional focus control must not block it.
            return

    def cameras(self) -> list[NodeCamera]:
        module, encoder = self._runtime()
        if module is None or encoder is None:
            return UnavailableCameraProvider(provider_key="picamera2", reason="PiCamera2 and a local image encoder must already be installed for this Node.").cameras()
        try:
            count = min(len(module.Picamera2.global_camera_info()), MAX_CAMERAS)
        except Exception:
            return [NodeCamera("picamera2-unavailable", "Pi camera unavailable", "unavailable", "Check the local Pi camera stack.", provider_type="picamera2")]
        return [NodeCamera(f"picamera2-camera-{index}", f"Pi camera {index + 1}", "available", snapshot_supported=True, provider_type="picamera2") for index in range(count)] or [NodeCamera("picamera2-no-camera", "No Pi camera available", "unavailable", "Connect a supported local Pi camera.", provider_type="picamera2")]

    def _sensor_modes(self, module: Any, camera_id: str) -> list[dict[str, Any]]:
        index = int(camera_id.rsplit("-", 1)[1])

        def read_modes() -> list[dict[str, Any]]:
            camera = module.Picamera2(index)
            try:
                raw_modes = getattr(camera, "sensor_modes", ())
                return [dict(item) for item in raw_modes if isinstance(item, dict)]
            finally:
                self._release_camera(camera)

        try:
            return _bounded_call(
                read_modes,
                failure_code="camera_initialization_failed",
                timeout_seconds=PICAMERA2_INITIALIZATION_TIMEOUT_SECONDS,
                timeout_code="camera_warmup_timeout",
            ) or []
        except ValueError:
            return []

    @staticmethod
    def _mode_size(mode: dict[str, Any]) -> tuple[int, int] | None:
        size = mode.get("size")
        if (
            isinstance(size, (tuple, list))
            and len(size) == 2
            and all(isinstance(item, int) and item > 0 for item in size)
        ):
            return int(size[0]), int(size[1])
        return None

    @staticmethod
    def _mode_geometry_group(camera_id: str, mode: dict[str, Any]) -> str | None:
        crop = mode.get("crop_limits")
        if not (
            isinstance(crop, (tuple, list))
            and len(crop) == 4
            and all(isinstance(item, int) for item in crop)
        ):
            return None
        digest = sha1(
            f"{camera_id}:{','.join(str(item) for item in crop)}".encode("ascii")
        ).hexdigest()[:12]
        return f"picamera2-fov-{digest}"

    def capture_profiles(self, camera_id: str) -> list[NodeCaptureProfile]:
        cached = self._profile_cache.get(camera_id)
        if cached is not None:
            self._schedule_warm_proof(camera_id)
            return list(cached)
        module, encoder = self._runtime()
        if module is None or encoder is None:
            return []
        available = {item.camera_id for item in self.cameras() if item.status == "available"}
        if camera_id not in available:
            return []
        modes = [
            (mode, size)
            for mode in self._sensor_modes(module, camera_id)
            if (size := self._mode_size(mode)) is not None
            and size[0] <= self._config.effective_evidence_max_image_width
            and size[1] <= self._config.effective_evidence_max_image_height
        ]
        if not modes:
            fallback = NodeCaptureProfile(
                profile_id="picamera2-bounded-jpeg",
                purposes=("monitoring", "preview", "evidence"),
                width=self._config.max_image_width,
                height=self._config.max_image_height,
                jpeg_supported=True,
                max_expected_bytes=min(
                    self._config.max_image_bytes, MAX_ADVERTISED_CAPTURE_BYTES
                ),
                capture_class="warm",
                geometry_group=None,
                same_fov=False,
            )
            self._profile_cache[camera_id] = (fallback,)
            return [fallback]
        modes.sort(key=lambda item: item[1][0] * item[1][1])
        monitoring_candidates = [
            item
            for item in modes
            if item[1][0] <= self._config.max_image_width
            and item[1][1] <= self._config.max_image_height
        ]
        monitoring_mode, monitoring_size = (
            monitoring_candidates[-1] if monitoring_candidates else modes[0]
        )
        monitoring_group = self._mode_geometry_group(camera_id, monitoring_mode)
        monitoring = NodeCaptureProfile(
            profile_id=f"picamera2-monitoring-{monitoring_size[0]}x{monitoring_size[1]}",
            purposes=("monitoring", "preview"),
            width=monitoring_size[0],
            height=monitoring_size[1],
            jpeg_supported=True,
            max_expected_bytes=min(
                self._config.max_image_bytes, MAX_ADVERTISED_CAPTURE_BYTES
            ),
            capture_class="warm",
            geometry_group=monitoring_group,
            same_fov=monitoring_group is not None,
        )
        profiles = [
            monitoring
        ]
        for mode, size in reversed(modes):
            profile_id = f"picamera2-evidence-{size[0]}x{size[1]}"
            if size == monitoring_size:
                continue
            geometry_group = self._mode_geometry_group(camera_id, mode)
            profiles.append(
                NodeCaptureProfile(
                    profile_id=profile_id,
                    purposes=("evidence",),
                    width=size[0],
                    height=size[1],
                    jpeg_supported=True,
                    max_expected_bytes=min(
                        self._config.effective_evidence_max_image_bytes,
                        MAX_ADVERTISED_CAPTURE_BYTES,
                    ),
                    capture_class="reconfiguration_required",
                    geometry_group=geometry_group,
                    same_fov=(
                        geometry_group is not None
                        and geometry_group == monitoring_group
                    ),
                )
            )
        bounded = tuple(profiles[:MAX_CAPTURE_PROFILES_PER_CAMERA])
        self._profile_cache[camera_id] = bounded
        self._warm_readiness[camera_id] = "not_initialized"
        self._warm_candidate_statuses.pop(camera_id, None)
        self._schedule_warm_proof(camera_id)
        return list(bounded)

    def capture_readiness(self, camera_id: str) -> str:
        return self._warm_readiness.get(camera_id, "not_initialized")

    def capture_profile_status(self, camera_id: str) -> list[dict[str, str]]:
        """Return only bounded proof states, never camera or driver diagnostics."""

        return [
            status.as_payload()
            for status in self._warm_candidate_statuses.get(camera_id, ())
        ]

    def _schedule_warm_proof(self, camera_id: str) -> None:
        if self._warm_readiness.get(camera_id) in {"warming", "ready", "degraded"}:
            return
        module, encoder = self._runtime()
        if module is None or encoder is None:
            self._warm_readiness[camera_id] = "unavailable"
            return
        self._warm_readiness[camera_id] = "warming"
        worker = threading.Thread(
            target=self._prove_warm_profiles,
            args=(module, encoder, camera_id),
            daemon=True,
            name=f"mockingbird-camera-warm-{camera_id}",
        )
        self._warm_proofs[camera_id] = worker
        worker.start()

    def _warm_candidates(
        self, profiles: list[NodeCaptureProfile]
    ) -> list[_WarmCandidate]:
        """Order each safe warm proof once, from the best aligned mode down."""

        candidates: list[_WarmCandidate] = []
        seen: set[str] = set()

        def add(monitoring: NodeCaptureProfile, evidence: NodeCaptureProfile) -> None:
            key = evidence.profile_id
            if key not in seen:
                seen.add(key)
                candidates.append(_WarmCandidate(monitoring, evidence))

        for evidence in profiles:
            if "evidence" not in evidence.purposes:
                continue
            # Full-sensor 4:3 modes use one explicitly bounded low-cost
            # stream. The pair is constructed by the provider, never caller
            # supplied sensor settings.
            if abs((evidence.width / evidence.height) - (4 / 3)) <= 0.01 and (
                self._config.max_image_width >= 1920
                and self._config.max_image_height >= 1440
            ):
                add(
                    NodeCaptureProfile(
                        profile_id="picamera2-monitoring-1920x1440",
                        purposes=("monitoring", "preview"),
                        width=1920,
                        height=1440,
                        jpeg_supported=True,
                        max_expected_bytes=min(
                            self._config.max_image_bytes,
                            MAX_ADVERTISED_CAPTURE_BYTES,
                        ),
                        capture_class="warm_concurrent",
                        geometry_group=evidence.geometry_group,
                        same_fov=True,
                    ),
                    evidence,
                )
        monitoring = next(
            (item for item in profiles if "monitoring" in item.purposes), None
        )
        if monitoring is not None:
            for evidence in profiles:
                if "evidence" in evidence.purposes and evidence.same_fov:
                    add(monitoring, evidence)
        return candidates

    def _set_warm_candidate_state(
        self, camera_id: str, profile_id: str, state: str
    ) -> None:
        statuses = self._warm_candidate_statuses.get(camera_id, ())
        self._warm_candidate_statuses[camera_id] = tuple(
            _WarmCandidateStatus(status.profile_id, state)
            if status.profile_id == profile_id
            else status
            for status in statuses
        )

    def _prove_warm_profiles(self, module: Any, encoder: Any, camera_id: str) -> None:
        # This background proof constructs and drives its own live Picamera2
        # session (see _start_highest_warm_session/_initialize_warm_camera)
        # entirely independently of snapshot()'s call path. Without the same
        # exclusive lock, it could run concurrently with a snapshot() call
        # that is also (re)constructing a camera session for this camera_id,
        # putting two uncoordinated live sessions on the same physical
        # hardware at once. Holding the lock for the whole bounded proof is
        # safe here: this method only ever runs on its own dedicated
        # background thread (see _schedule_warm_proof), so it never blocks a
        # request-handling thread -- at worst it delays this best-effort
        # upgrade, which callers already treat as a normal "warming" state.
        with self._lock:
            profiles = list(self._profile_cache.get(camera_id, ()))
            candidates = self._warm_candidates(profiles)
            self._warm_candidate_statuses[camera_id] = tuple(
                _WarmCandidateStatus(candidate.evidence.profile_id, "untested")
                for candidate in candidates
            )
            warm = self._start_highest_warm_session(module, encoder, camera_id, candidates)
            if warm is None:
                # Cold monitoring remains usable, so failure to prove an
                # optional warm pair is degraded rather than a terminal
                # provider failure.
                self._warm_readiness[camera_id] = "degraded"
                return
            warm_monitoring, warm_evidence, accepted_profile_id = warm
            rejected_resource_profiles = {
                status.profile_id
                for status in self._warm_candidate_statuses.get(camera_id, ())
                if status.state == "rejected_resource"
            }
            self._profile_cache[camera_id] = tuple(
                [
                    warm_monitoring,
                    warm_evidence,
                    *[
                        item
                        for item in profiles
                        if item.profile_id != accepted_profile_id
                        and item.profile_id != warm_monitoring.profile_id
                        and item.profile_id != warm_evidence.profile_id
                        and item.profile_id not in rejected_resource_profiles
                    ],
                ][:MAX_CAPTURE_PROFILES_PER_CAMERA]
            )
            self._warm_readiness[camera_id] = "ready"

    def _start_highest_warm_session(
        self,
        module: Any,
        encoder: Any,
        camera_id: str,
        candidates: list[_WarmCandidate],
    ) -> tuple[NodeCaptureProfile, NodeCaptureProfile, str] | None:
        """Keep the highest aligned candidate that proves fast enough in one session."""

        resource_rejection_seen = False
        retried_required_profiles: set[str] = set()

        def reject_warm_candidate(
            camera: Any | None,
            profile_id: str,
            state: str,
            monitoring: NodeCaptureProfile,
            evidence: NodeCaptureProfile,
        ) -> bool:
            nonlocal resource_rejection_seen
            self._set_warm_candidate_state(camera_id, profile_id, state)
            self._reclaim_warm_candidate(camera)
            if state == "rejected_resource":
                resource_rejection_seen = True
                sleep(WARM_CANDIDATE_RECLAIM_SECONDS)
            if (
                resource_rejection_seen
                and self._is_required_warm_pair(monitoring, evidence)
                and profile_id not in retried_required_profiles
            ):
                retried_required_profiles.add(profile_id)
                sleep(WARM_REQUIRED_PAIR_RETRY_DELAY_SECONDS)
                return True
            return False

        for candidate in candidates:
            monitoring, cold_evidence = candidate.monitoring, candidate.evidence
            self._set_warm_candidate_state(
                camera_id, cold_evidence.profile_id, "testing"
            )
            warm_monitoring = NodeCaptureProfile(
                **{**monitoring.__dict__, "capture_class": "warm_concurrent"}
            )
            warm_evidence = NodeCaptureProfile(
                profile_id=f"picamera2-warm-evidence-{cold_evidence.width}x{cold_evidence.height}",
                purposes=cold_evidence.purposes,
                width=cold_evidence.width,
                height=cold_evidence.height,
                jpeg_supported=True,
                max_expected_bytes=cold_evidence.max_expected_bytes,
                capture_class="warm_concurrent",
                geometry_group=cold_evidence.geometry_group,
                orientation=cold_evidence.orientation,
                mirrored=cold_evidence.mirrored,
                same_fov=True,
            )
            camera: Any | None = None
            try:
                started_at = monotonic()
                camera = self._initialize_warm_camera(
                    module, camera_id, warm_monitoring, warm_evidence
                )
                monitoring_frame = _bounded_call(
                    lambda: camera.capture_array("lores"),
                    failure_code="camera_unusable_frame",
                    timeout_seconds=PICAMERA2_FRAME_TIMEOUT_SECONDS,
                    timeout_code="camera_capture_timeout",
                )
                if monotonic() - started_at > WARM_SESSION_READY_TIMEOUT_SECONDS:
                    raise ValueError("camera_warmup_timeout")
                evidence_frame = _bounded_call(
                    lambda: camera.capture_array("main"),
                    failure_code="camera_unusable_frame",
                    timeout_seconds=PICAMERA2_FRAME_TIMEOUT_SECONDS,
                    timeout_code="camera_capture_timeout",
                )
                _encode_bounded_jpeg(
                    encoder,
                    _jpeg_frame(encoder, monitoring_frame, yuv420=True),
                    maximum_bytes=warm_monitoring.max_expected_bytes,
                )
                _encode_bounded_jpeg(
                    encoder,
                    evidence_frame,
                    maximum_bytes=warm_evidence.max_expected_bytes,
                )
                for _ in range(5):
                    monitoring_started = monotonic()
                    frame = _bounded_call(
                        lambda: camera.capture_array("lores"),
                        failure_code="camera_unusable_frame",
                        timeout_seconds=WARM_MONITORING_TIMEOUT_SECONDS,
                        timeout_code="camera_capture_timeout",
                    )
                    _encode_bounded_jpeg(
                        encoder,
                        _jpeg_frame(encoder, frame, yuv420=True),
                        maximum_bytes=warm_monitoring.max_expected_bytes,
                    )
                    if monotonic() - monitoring_started > WARM_MONITORING_TIMEOUT_SECONDS:
                        raise ValueError("camera_capture_timeout")
                    evidence_started = monotonic()
                    frame = _bounded_call(
                        lambda: camera.capture_array("main"),
                        failure_code="camera_unusable_frame",
                        timeout_seconds=WARM_EVIDENCE_TIMEOUT_SECONDS,
                        timeout_code="camera_capture_timeout",
                    )
                    _encode_bounded_jpeg(
                        encoder,
                        frame,
                        maximum_bytes=warm_evidence.max_expected_bytes,
                    )
                    if monotonic() - evidence_started > WARM_EVIDENCE_ACCEPTANCE_SECONDS:
                        raise ValueError("camera_capture_timeout")
            except _WarmCandidateFailure as error:
                if reject_warm_candidate(
                    camera,
                    cold_evidence.profile_id,
                    error.state,
                    warm_monitoring,
                    warm_evidence,
                ):
                    candidates.insert(candidates.index(candidate) + 1, candidate)
                continue
            except ValueError as error:
                state = {
                    "camera_warmup_timeout": "rejected_latency",
                    "camera_capture_timeout": "rejected_latency",
                    "camera_unusable_frame": "rejected_capture",
                    "camera_initialization_failed": "rejected_configuration",
                }.get(str(error), "rejected_capture")
                if reject_warm_candidate(
                    camera,
                    cold_evidence.profile_id,
                    state,
                    warm_monitoring,
                    warm_evidence,
                ):
                    candidates.insert(candidates.index(candidate) + 1, candidate)
                continue
            except Exception:
                if reject_warm_candidate(
                    camera,
                    cold_evidence.profile_id,
                    "rejected_capture",
                    warm_monitoring,
                    warm_evidence,
                ):
                    candidates.insert(candidates.index(candidate) + 1, candidate)
                continue
            self._cameras[camera_id] = camera
            self._camera_profile_ids[camera_id] = warm_monitoring.profile_id
            self._warm_sessions[camera_id] = _WarmConcurrentSession(
                camera=camera,
                monitoring_profile_id=warm_monitoring.profile_id,
                evidence_profile_id=warm_evidence.profile_id,
            )
            self._set_warm_candidate_state(
                camera_id, cold_evidence.profile_id, "accepted"
            )
            return warm_monitoring, warm_evidence, cold_evidence.profile_id
        return None

    @staticmethod
    def _is_required_warm_pair(
        monitoring: NodeCaptureProfile, evidence: NodeCaptureProfile
    ) -> bool:
        """Allow one fresh proof only for the required full-sensor warm pair."""

        return (
            (monitoring.width, monitoring.height) == (1920, 1440)
            and (evidence.width, evidence.height) == (4624, 3472)
        )

    def _reclaim_warm_candidate(self, camera: Any | None) -> None:
        """Discard one failed owner before the next bounded candidate attempt."""

        if camera is not None:
            self._release_camera(camera)
        gc.collect()

    @staticmethod
    def _release_camera(camera: Any) -> bool:
        try:
            camera.stop()
        except Exception:
            pass
        try:
            camera.close()
        except Exception:
            return False
        return True

    def _reset_camera(self, camera_id: str, *, fallback: Any | None = None) -> bool:
        camera = self._cameras.pop(camera_id, fallback)
        self._camera_profile_ids.pop(camera_id, None)
        self._warm_sessions.pop(camera_id, None)
        return True if camera is None else self._release_camera(camera)

    def _initialize_warm_camera(
        self,
        module: Any,
        camera_id: str,
        monitoring: NodeCaptureProfile,
        evidence: NodeCaptureProfile,
    ) -> Any:
        index = int(camera_id.rsplit("-", 1)[1])

        def initialize() -> Any:
            camera: Any | None = None
            try:
                camera = module.Picamera2(index)
                camera.configure(
                    camera.create_still_configuration(
                        main={"size": (evidence.width, evidence.height), "format": "RGB888"},
                        lores={"size": (monitoring.width, monitoring.height), "format": "YUV420"},
                        buffer_count=2,
                    )
                )
                self._enable_continuous_autofocus(camera)
                camera.start()
                return camera
            except BaseException as error:
                if camera is not None:
                    self._release_camera(camera)
                if isinstance(error, MemoryError) or (
                    isinstance(error, OSError) and error.errno == errno.ENOMEM
                ):
                    raise _WarmCandidateFailure("rejected_resource") from error
                raise

        return _bounded_call(
            initialize,
            failure_code="camera_initialization_failed",
            timeout_seconds=PICAMERA2_INITIALIZATION_TIMEOUT_SECONDS,
            timeout_code="camera_warmup_timeout",
            late_cleanup=self._release_camera,
        )

    def _initialize_camera(
        self,
        module: Any,
        camera_id: str,
        profile: NodeCaptureProfile,
    ) -> Any:
        index = int(camera_id.rsplit("-", 1)[1])

        def initialize() -> Any:
            camera: Any | None = None
            try:
                camera = module.Picamera2(index)
                camera.configure(
                    camera.create_still_configuration(
                        main={
                            "size": (profile.width, profile.height),
                            "format": "RGB888",
                        }
                    )
                )
                self._enable_continuous_autofocus(camera)
                camera.start()
                return camera
            except BaseException:
                if camera is not None:
                    self._release_camera(camera)
                raise

        return _bounded_call(
            initialize,
            failure_code="camera_initialization_failed",
            timeout_seconds=PICAMERA2_INITIALIZATION_TIMEOUT_SECONDS,
            timeout_code="camera_warmup_timeout",
            late_cleanup=self._release_camera,
        )

    def _camera_for_snapshot(
        self,
        module: Any,
        camera_id: str,
        profile: NodeCaptureProfile,
    ) -> Any:
        camera = self._cameras.get(camera_id)
        if camera is None:
            camera = self._initialize_camera(module, camera_id, profile)
            self._cameras[camera_id] = camera
        return camera

    def _reopen_accepted_warm_session(
        self,
        module: Any,
        camera_id: str,
    ) -> None:
        """Replace one failed warm owner without repeating candidate selection."""

        profiles = self._profile_cache.get(camera_id, ())
        monitoring = next(
            (
                profile
                for profile in profiles
                if profile.capture_class == "warm_concurrent"
                and "monitoring" in profile.purposes
            ),
            None,
        )
        evidence = next(
            (
                profile
                for profile in profiles
                if profile.capture_class == "warm_concurrent"
                and "evidence" in profile.purposes
            ),
            None,
        )
        if (
            monitoring is None
            or evidence is None
            or not monitoring.same_fov
            or monitoring.geometry_group != evidence.geometry_group
        ):
            raise ValueError("provider_session_failed")

        self._reset_camera(camera_id)
        try:
            camera = self._initialize_warm_camera(
                module, camera_id, monitoring, evidence
            )
        except Exception as error:
            self._reset_camera(camera_id)
            raise ValueError("provider_session_failed") from error
        self._cameras[camera_id] = camera
        self._camera_profile_ids[camera_id] = monitoring.profile_id
        self._warm_sessions[camera_id] = _WarmConcurrentSession(
            camera=camera,
            monitoring_profile_id=monitoring.profile_id,
            evidence_profile_id=evidence.profile_id,
        )

    def _camera_for_profile(
        self,
        module: Any,
        camera_id: str,
        profile: NodeCaptureProfile,
        transaction: _ProfileCaptureTransaction,
    ) -> Any:
        """Reuse only a known matching warm session; profile changes reset first."""

        if profile.capture_class == "warm_concurrent":
            session = self._warm_sessions.get(camera_id)
            if session is None or profile.profile_id not in {
                session.monitoring_profile_id,
                session.evidence_profile_id,
            }:
                raise ValueError("provider_session_missing")
            return session.camera
        if (
            camera_id in self._cameras
            and transaction.active_profile_id != profile.profile_id
        ):
            self._reset_camera(camera_id)
        camera = self._camera_for_snapshot(module, camera_id, profile)
        self._camera_profile_ids[camera_id] = profile.profile_id
        return camera

    def _monitoring_profile(self, camera_id: str) -> NodeCaptureProfile | None:
        return next(
            (
                profile
                for profile in self.capture_profiles(camera_id)
                if "monitoring" in profile.purposes
            ),
            None,
        )

    def _restore_monitoring_after_evidence_capture(
        self,
        *,
        module: Any,
        camera_id: str,
        profile: NodeCaptureProfile,
        image: bytes,
        transaction: _ProfileCaptureTransaction,
    ) -> NodeCaptureResult:
        """Retain valid evidence even when the monitoring restore must be reset."""

        monitoring = self._monitoring_profile(camera_id)
        if monitoring is None or monitoring.profile_id == profile.profile_id:
            return NodeCaptureResult(image=image)

        transaction.state = "restoring_monitoring"
        try:
            self._reset_camera(camera_id)
            restored = self._initialize_camera(module, camera_id, monitoring)
            self._cameras[camera_id] = restored
            self._camera_profile_ids[camera_id] = monitoring.profile_id
        except Exception:
            # Clear ownership before returning. The next monitoring request can
            # lazily create exactly one fresh provider session.
            self._reset_camera(camera_id)
            transaction.state = "reset_required"
            return NodeCaptureResult(image=image, monitoring_recovery="reset_required")

        transaction.state = "monitoring_ready"
        return NodeCaptureResult(image=image, monitoring_recovery="restored")

    def snapshot(
        self, camera_id: str, *, profile_id: str | None = None
    ) -> NodeCaptureResult:
        cameras = {camera.camera_id for camera in self.cameras() if camera.status == "available"}
        if camera_id not in cameras:
            raise ValueError("camera_not_allowed")
        module, encoder = self._runtime()
        if module is None or encoder is None:
            raise ValueError("camera_setup_required")
        if profile_id is None:
            # Legacy snapshot callers retain the original bounded behaviour
            # without probing provider-specific still modes on every frame.
            profile = NodeCaptureProfile(
                profile_id="picamera2-legacy-snapshot",
                purposes=("monitoring", "preview"),
                width=self._config.max_image_width,
                height=self._config.max_image_height,
                jpeg_supported=True,
                max_expected_bytes=min(
                    self._config.max_image_bytes, MAX_ADVERTISED_CAPTURE_BYTES
                ),
                capture_class="warm",
                geometry_group=None,
            )
        else:
            profiles = {
                profile.profile_id: profile
                for profile in self.capture_profiles(camera_id)
            }
            profile = profiles.get(profile_id)
        if profile is None:
            raise ValueError("capture_profile_not_allowed")
        if not self._lock.acquire(timeout=CAPTURE_LOCK_TIMEOUT_SECONDS):
            raise ValueError("camera_busy")
        try:
            transaction = _ProfileCaptureTransaction(
                requested_profile_id=profile.profile_id,
                active_profile_id=self._camera_profile_ids.get(camera_id),
                state=(
                    "switching_to_evidence"
                    if profile.capture_class == "reconfiguration_required"
                    else "monitoring_ready"
                ),
            )
            stream_name = (
                "main"
                if profile.capture_class == "warm_concurrent"
                and "evidence" in profile.purposes
                else "lores"
                if profile.capture_class == "warm_concurrent"
                else None
            )
            recovered_warm_session = False
            while True:
                try:
                    camera = self._camera_for_profile(
                        module, camera_id, profile, transaction
                    )
                    frame = _bounded_call(
                        (lambda: camera.capture_array(stream_name))
                        if stream_name
                        else camera.capture_array,
                        failure_code="camera_unusable_frame",
                        timeout_seconds=PICAMERA2_FRAME_TIMEOUT_SECONDS,
                        timeout_code="camera_capture_timeout",
                        late_cleanup=(
                            None
                            if profile.capture_class == "warm_concurrent"
                            else lambda _frame: self._reset_camera(
                                camera_id, fallback=camera
                            )
                        ),
                    )
                    image = _encode_bounded_jpeg(
                        encoder,
                        _jpeg_frame(
                            encoder,
                            frame,
                            yuv420=(stream_name == "lores"),
                        ),
                        maximum_bytes=profile.max_expected_bytes,
                    )
                    if profile.capture_class != "reconfiguration_required":
                        return NodeCaptureResult(
                            image=image,
                            monitoring_recovery=(
                                "restored" if recovered_warm_session else None
                            ),
                        )
                    transaction.state = "evidence_captured"
                    return self._restore_monitoring_after_evidence_capture(
                        module=module,
                        camera_id=camera_id,
                        profile=profile,
                        image=image,
                        transaction=transaction,
                    )
                except PermissionError as error:
                    self._reset_camera(camera_id)
                    raise ValueError("camera_permission_denied") from error
                except ValueError as error:
                    if profile.capture_class != "warm_concurrent":
                        if not self._reset_camera(camera_id):
                            raise ValueError("provider_reset_required") from error
                        raise
                    if recovered_warm_session:
                        self._reset_camera(camera_id)
                        raise ValueError("provider_session_failed") from error
                except Exception as error:
                    if profile.capture_class != "warm_concurrent":
                        reset = self._reset_camera(camera_id)
                        code = (
                            "camera_initialization_failed"
                            if reset
                            else "provider_reset_required"
                        )
                        raise ValueError(code) from error
                    if recovered_warm_session:
                        self._reset_camera(camera_id)
                        raise ValueError("provider_session_failed") from error

                try:
                    self._reopen_accepted_warm_session(module, camera_id)
                except Exception as recovery_error:
                    self._reset_camera(camera_id)
                    raise ValueError("provider_session_failed") from recovery_error
                recovered_warm_session = True
        finally:
            self._lock.release()

    def close(self) -> None:
        with self._lock:
            cameras = list(self._cameras.values())
            self._cameras.clear()
            self._camera_profile_ids.clear()
            self._profile_cache.clear()
            self._warm_sessions.clear()
            self._warm_readiness.clear()
            self._warm_proofs.clear()
            self._warm_candidate_statuses.clear()
        for camera in cameras:
            self._release_camera(camera)


class CompositeCameraProvider:
    def __init__(self, providers: list[CameraNodeProvider]) -> None:
        self._providers = providers

    def cameras(self) -> list[NodeCamera]:
        return [camera for provider in self._providers for camera in provider.cameras()][:MAX_CAMERAS]

    def capture_profiles(self, camera_id: str) -> list[NodeCaptureProfile]:
        for provider in self._providers:
            if any(camera.camera_id == camera_id for camera in provider.cameras()):
                return provider.capture_profiles(camera_id)
        return []

    def capture_readiness(self, camera_id: str) -> str:
        for provider in self._providers:
            if any(camera.camera_id == camera_id for camera in provider.cameras()):
                method = getattr(provider, "capture_readiness", None)
                return method(camera_id) if callable(method) else "ready"
        return "unavailable"

    def capture_profile_status(self, camera_id: str) -> list[dict[str, str]]:
        for provider in self._providers:
            if any(camera.camera_id == camera_id for camera in provider.cameras()):
                method = getattr(provider, "capture_profile_status", None)
                return method(camera_id) if callable(method) else []
        return []

    def snapshot(self, camera_id: str, *, profile_id: str | None = None) -> bytes:
        for provider in self._providers:
            if any(camera.camera_id == camera_id for camera in provider.cameras()):
                return provider.snapshot(camera_id, profile_id=profile_id)
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
