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
        stderr=subprocess.DEVNULL,
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


__all__ = [
    "LOCAL_USB_STREAM_TYPE",
    "MJPEG_BOUNDARY",
    "build_local_camera_frame_capture_command",
    "build_local_camera_mjpeg_command",
    "capture_local_camera_frame",
    "is_ffmpeg_available",
    "iter_multipart_mjpeg",
    "local_camera_status",
    "normalize_local_camera_format",
    "start_local_camera_frame_capture_process",
    "start_local_camera_mjpeg_process",
    "validate_local_camera_device",
]
