"""Optional local USB/webcam playback bridge helpers."""

from __future__ import annotations

from collections.abc import Callable, Iterator
import re
import shutil
import subprocess
import sys

from mockingbird.playback.frame_capture import read_one_jpeg_frame
from mockingbird.playback.rtsp_bridge import MJPEG_BOUNDARY, iter_multipart_mjpeg

LOCAL_USB_STREAM_TYPE = "local_usb"
DEFAULT_CAMERA_FORMAT = "v4l2"

_LINUX_VIDEO_DEVICE_PATTERN = re.compile(r"^/dev/video\d+$")


def is_ffmpeg_available(ffmpeg_binary: str = "ffmpeg") -> bool:
    return shutil.which(ffmpeg_binary) is not None


def normalize_local_camera_format(raw_format: str | None) -> str:
    return (raw_format or DEFAULT_CAMERA_FORMAT).strip().lower() or DEFAULT_CAMERA_FORMAT


def validate_local_camera_device(device: str | None) -> bool:
    return bool(device and _LINUX_VIDEO_DEVICE_PATTERN.fullmatch(device.strip()))


def local_camera_status(
    *,
    device: str | None,
    camera_format: str | None = None,
    platform_name: str = sys.platform,
    ffmpeg_available: bool | None = None,
) -> str:
    if not device or not device.strip():
        return "device_missing"
    if not platform_name.startswith("linux"):
        return "unsupported_platform"
    if normalize_local_camera_format(camera_format) != DEFAULT_CAMERA_FORMAT:
        return "unsupported_platform"
    if not validate_local_camera_device(device):
        return "invalid_device"
    if ffmpeg_available is None:
        ffmpeg_available = is_ffmpeg_available()
    if not ffmpeg_available:
        return "ffmpeg_missing"
    return "available"


def build_local_camera_mjpeg_command(
    device: str,
    *,
    camera_format: str | None = None,
    input_format: str | None = None,
    ffmpeg_binary: str = "ffmpeg",
    video_size: str | None = None,
    input_frame_rate: str | int | None = None,
    output_frame_rate: int = 5,
    quality: int = 5,
) -> list[str]:
    if normalize_local_camera_format(camera_format) != DEFAULT_CAMERA_FORMAT:
        raise ValueError("unsupported_local_camera_format")
    if not validate_local_camera_device(device):
        raise ValueError("invalid_local_camera_device")
    command = [
        ffmpeg_binary,
        "-hide_banner",
        "-loglevel",
        "error",
        "-f",
        DEFAULT_CAMERA_FORMAT,
    ]
    normalized_input_format = (input_format or "").strip()
    if normalized_input_format:
        command.extend(["-input_format", normalized_input_format])
    if video_size:
        command.extend(["-video_size", video_size])
    normalized_framerate = (
        str(input_frame_rate).strip() if input_frame_rate is not None else ""
    )
    if normalized_framerate:
        command.extend(["-framerate", normalized_framerate])
    command.extend(
        [
            "-i",
            device.strip(),
            "-an",
            "-f",
            "mjpeg",
            "-q:v",
            str(quality),
            "-r",
            str(output_frame_rate),
            "pipe:1",
        ]
    )
    return command


PopenFactory = Callable[..., subprocess.Popen[bytes]]


def start_local_camera_mjpeg_process(
    device: str,
    *,
    camera_format: str | None = None,
    input_format: str | None = None,
    video_size: str | None = None,
    input_frame_rate: str | int | None = None,
    popen_factory: PopenFactory = subprocess.Popen,
    capture_stderr: bool = False,
) -> subprocess.Popen[bytes]:
    command = build_local_camera_mjpeg_command(
        device,
        camera_format=camera_format,
        input_format=input_format,
        video_size=video_size,
        input_frame_rate=input_frame_rate,
    )
    return popen_factory(
        command,
        stdout=subprocess.PIPE,
        # `capture_stderr` defaults `False` (unchanged for every other
        # caller) -- Ongoing Monitoring Failure Diagnostics v1: `_start_
        # process` (`playback.live_camera_session`) is the one caller that
        # opts in, pairing the resulting pipe with a `BoundedStderrDrain`
        # so a long-running local-USB failure can be classified instead of
        # collapsing to a generic message. Mirrors `rtsp_bridge.start_rtsp_
        # mjpeg_process`'s identical parameter exactly.
        stderr=subprocess.PIPE if capture_stderr else subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
    )


def build_local_camera_frame_capture_command(
    device: str,
    *,
    camera_format: str | None = None,
    input_format: str | None = None,
    ffmpeg_binary: str = "ffmpeg",
    video_size: str | None = None,
    input_frame_rate: str | int | None = None,
) -> list[str]:
    if normalize_local_camera_format(camera_format) != DEFAULT_CAMERA_FORMAT:
        raise ValueError("unsupported_local_camera_format")
    if not validate_local_camera_device(device):
        raise ValueError("invalid_local_camera_device")
    command = [
        ffmpeg_binary,
        "-hide_banner",
        "-loglevel",
        "error",
        "-f",
        DEFAULT_CAMERA_FORMAT,
    ]
    normalized_input_format = (input_format or "").strip()
    if normalized_input_format:
        command.extend(["-input_format", normalized_input_format])
    normalized_video_size = (video_size or "").strip()
    if normalized_video_size:
        command.extend(["-video_size", normalized_video_size])
    normalized_framerate = (
        str(input_frame_rate).strip() if input_frame_rate is not None else ""
    )
    if normalized_framerate:
        command.extend(["-framerate", normalized_framerate])
    command.extend(
        [
            "-i",
            device.strip(),
            "-an",
            "-frames:v",
            "1",
            "-f",
            "image2pipe",
            "-vcodec",
            "mjpeg",
            "pipe:1",
        ]
    )
    return command


def start_local_camera_frame_capture_process(
    device: str,
    *,
    camera_format: str | None = None,
    input_format: str | None = None,
    video_size: str | None = None,
    input_frame_rate: str | int | None = None,
    popen_factory: PopenFactory = subprocess.Popen,
) -> subprocess.Popen[bytes]:
    command = build_local_camera_frame_capture_command(
        device,
        camera_format=camera_format,
        input_format=input_format,
        video_size=video_size,
        input_frame_rate=input_frame_rate,
    )
    return popen_factory(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
    )


def capture_local_camera_frame(
    device: str,
    *,
    camera_format: str | None = None,
    input_format: str | None = None,
    video_size: str | None = None,
    input_frame_rate: str | int | None = None,
    popen_factory: PopenFactory = subprocess.Popen,
) -> bytes:
    process = start_local_camera_frame_capture_process(
        device,
        camera_format=camera_format,
        input_format=input_format,
        video_size=video_size,
        input_frame_rate=input_frame_rate,
        popen_factory=popen_factory,
    )
    return read_one_jpeg_frame(process)


# ---------------------------------------------------------------------------
# Ongoing Monitoring Failure Diagnostics v1 ("local_usb result"): unlike
# RTSP, this bridge had zero prior text-based failure classification of any
# kind (`local_camera_status` above is a purely static/config-time check --
# device path regex, platform, ffmpeg-binary presence -- never runtime
# process-failure text). Only two categories are backed by real,
# deterministic evidence (real ffmpeg 6.1.1 stderr against `/dev/video*`
# paths on this project's own Linux dev sandbox -- see the milestone
# report's "local_usb result" section for the exact captured text):
# device-missing (`ENOENT`, "No such file or directory") and permission-
# denied (`EACCES`, "Permission denied"). Deliberately does NOT attempt to
# distinguish device-busy, unsupported-format, or a generic decode failure
# -- no real V4L2 hardware or kernel module (e.g. v4l2loopback) was
# available to establish those signatures, and inventing them without
# evidence would violate this milestone's own explicit "no false
# precision" bar. Everything else -- including the real, reproduced
# `ioctl(VIDIOC_QUERYCAP): Inappropriate ioctl for device` text a
# non-V4L2-device path produces -- honestly falls back to the generic
# `camera_monitoring_local_usb_unavailable` code.
# ---------------------------------------------------------------------------


def classify_local_camera_failure_text(detail: str | None) -> str:
    """Distinguish a local-USB/V4L2 ongoing-monitoring failure only where
    real ffmpeg stderr text gives concrete evidence -- see the module-level
    comment above for exactly which categories are evidence-backed."""

    text = (detail or "").lower()
    if "no such file or directory" in text:
        return "camera_monitoring_local_usb_device_missing"
    if "permission denied" in text:
        return "camera_monitoring_local_usb_permission_denied"
    return "camera_monitoring_local_usb_unavailable"


#: Every code `classify_local_camera_failure_text` can return.
LOCAL_USB_ONGOING_FAILURE_CODES = frozenset(
    {
        "camera_monitoring_local_usb_device_missing",
        "camera_monitoring_local_usb_permission_denied",
        "camera_monitoring_local_usb_unavailable",
    }
)

#: Calm, actionable, basic-tier sentences for `_LiveCameraSession.last_
#: error` -- see `rtsp_bridge.RTSP_ONGOING_FAILURE_MESSAGES`'s docstring
#: for the same convention.
LOCAL_USB_ONGOING_FAILURE_MESSAGES: dict[str, str] = {
    "camera_monitoring_local_usb_device_missing": (
        "This camera's device could not be found. Check that it's connected."
    ),
    "camera_monitoring_local_usb_permission_denied": (
        "MockingBird doesn't have permission to access this camera device."
    ),
    "camera_monitoring_local_usb_unavailable": (
        "This local camera stopped responding."
    ),
}


__all__ = [
    "LOCAL_USB_ONGOING_FAILURE_CODES",
    "LOCAL_USB_ONGOING_FAILURE_MESSAGES",
    "LOCAL_USB_STREAM_TYPE",
    "MJPEG_BOUNDARY",
    "build_local_camera_frame_capture_command",
    "build_local_camera_mjpeg_command",
    "capture_local_camera_frame",
    "classify_local_camera_failure_text",
    "is_ffmpeg_available",
    "iter_multipart_mjpeg",
    "local_camera_status",
    "normalize_local_camera_format",
    "start_local_camera_frame_capture_process",
    "start_local_camera_mjpeg_process",
    "validate_local_camera_device",
]
