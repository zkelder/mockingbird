"""Bounded, non-blocking Camera Node startup self-test.

Runs once at process startup, before `/node/v1/health` is ever answered --
never again on a timer. Every probe here is already fast by construction
(camera *enumeration* -- `provider.cameras()` -- never a full capture or
warm-session; see `mockingbird_node.providers`), but is still wrapped in a
short bounded timeout so a truly wedged driver call at startup cannot hang
the whole process before it ever binds its listening socket. See "Startup
self-test" in docs/camera-node-installer-design.md.

Self-test never blocks forever waiting for camera hardware, and a camera
being absent or unusable is `degraded`, never `failed`: the Node's own HTTP
surface (pairing, health, revocation) works regardless of camera state, so
there is no shape of camera trouble that should keep the process from
answering health or entering a restart loop over it.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import threading
from typing import Any, Callable

from . import hardware_health


#: Bounds `provider.cameras()` as a whole (every enabled provider, e.g. a
#: composite of `picamera2`+`v4l2`, enumerated sequentially -- see
#: `mockingbird_node.providers.CompositeCameraProvider`). Real, measured
#: evidence against the reference Pi (Authenticated Camera Node Golden-Path
#: Capture & Preview Acceptance v1): `V4L2CameraProvider.cameras()` alone,
#: bounding up to `MAX_CAMERAS` per-path open+read probes at
#: `V4L2_PROBE_TIMEOUT_SECONDS` each, measured 2.8s warm (more, cold, right
#: after a service restart, while `picamera2` is still loading tuning files)
#: even before `_is_capture_capable` also required a successful frame read
#: (a real defect this same milestone fixed -- see
#: `V4L2CameraProvider._is_capture_capable`); requiring that read makes any
#: non-camera-but-openable path cost close to the full per-path bound rather
#: than returning fast. The previous 4.0s budget under-covered this
#: real-hardware cost and produced a live, reproducible false "degraded"/
#: `provider_enumeration_timed_out` self-test reading for a Node whose
#: configured camera was, in live truth, genuinely available seconds later.
#: Still finite and still never blocks the process indefinitely (see the
#: module docstring) -- a Node with a truly wedged driver still degrades
#: within this bound rather than hanging startup.
DEFAULT_SELF_TEST_TIMEOUT_SECONDS = 10.0


@dataclass(frozen=True)
class StartupSelfTestResult:
    status: str  # "passed" | "degraded" -- see module docstring: never "failed"
    reasons: tuple[str, ...] = ()
    providers_initialized: bool = False
    camera_available: bool = False
    pairing_state_writable: bool | None = None

    def as_payload(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "reasons": list(self.reasons),
            "providers_initialized": self.providers_initialized,
            "camera_available": self.camera_available,
            "pairing_state_writable": self.pairing_state_writable,
        }


def _bounded(callback: Callable[[], Any], *, timeout_seconds: float) -> tuple[Any, str | None]:
    """Run `callback()` with a bounded wall-clock timeout, mirroring
    `providers._bounded_call`'s own shape at self-test scope: a daemon
    thread means an abandoned, truly-wedged probe can never block process
    startup or shutdown -- only this one self-test result degrades."""

    result: list[Any] = []
    errors: list[BaseException] = []

    def run() -> None:
        try:
            result.append(callback())
        except BaseException as error:  # noqa: BLE001 - isolate any provider probe failure, by design
            errors.append(error)

    worker = threading.Thread(target=run, daemon=True, name="mockingbird-camera-node-selftest")
    worker.start()
    worker.join(timeout_seconds)
    if worker.is_alive():
        return None, "timed_out"
    if errors:
        return None, "raised"
    return (result[0] if result else None), None


def _pairing_state_writable(pairing_state_path: Path | None) -> bool | None:
    """`None` when there is no configured state path to check at all
    (never observed in production -- `CameraNodeConfig.from_environment()`
    always resolves one -- but self-test must never assume a caller-built
    config did)."""

    if pairing_state_path is None:
        return None
    try:
        parent = pairing_state_path.parent
        parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        probe_path = parent / f".selftest-{threading.get_ident()}.tmp"
        probe_path.write_bytes(b"")
        probe_path.unlink()
        return True
    except OSError:
        return False


def run_startup_self_test(
    *,
    provider: Any,
    pairing_state_path: Path | None = None,
    timeout_seconds: float = DEFAULT_SELF_TEST_TIMEOUT_SECONDS,
    storage_directory: Path | None = None,
) -> StartupSelfTestResult:
    reasons: list[str] = []

    cameras, probe_failure = _bounded(provider.cameras, timeout_seconds=timeout_seconds)
    providers_initialized = probe_failure is None
    if probe_failure == "timed_out":
        reasons.append("provider_enumeration_timed_out")
    elif probe_failure == "raised":
        reasons.append("provider_enumeration_failed")

    camera_available = bool(
        providers_initialized
        and cameras
        and any(getattr(camera, "status", None) == "available" for camera in cameras)
    )
    if providers_initialized and not camera_available:
        reasons.append("no_camera_available")

    writable = _pairing_state_writable(pairing_state_path)
    if writable is False:
        reasons.append("pairing_state_path_unwritable")

    # Release Reliability & First-Run Recovery v1: the previously-missing
    # "does this Node's own local storage/hardware condition need
    # attention" signal -- see hardware_health.py's own module docstring.
    # `storage_directory=None` (no caller-supplied probe location) is
    # honestly "not checked," never a fabricated "healthy."
    storage_health_tier: str | None = None
    if storage_directory is not None:
        storage_health_tier = hardware_health.read_storage_health(storage_directory).storage_health_tier
        if storage_health_tier == "critical":
            reasons.append("storage_critically_low")
    hardware_quality = hardware_health.read_hardware_quality()
    if hardware_quality is not None and hardware_quality.is_critical:
        reasons.append("hardware_quality_critical")

    if (
        not providers_initialized
        or writable is False
        or not camera_available
        or storage_health_tier == "critical"
        or (hardware_quality is not None and hardware_quality.is_critical)
    ):
        status = "degraded"
    else:
        status = "passed"

    return StartupSelfTestResult(
        status=status,
        reasons=tuple(reasons),
        providers_initialized=providers_initialized,
        camera_available=camera_available,
        pairing_state_writable=writable,
    )
