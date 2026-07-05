"""Optional Windows DirectShow webcam playback bridge helpers."""

from __future__ import annotations

from collections.abc import Callable
import re
import shutil
import subprocess
import sys

from mockingbird.playback.frame_capture import read_one_jpeg_frame
from mockingbird.playback.rtsp_bridge import MJPEG_BOUNDARY, iter_multipart_mjpeg

WINDOWS_DSHOW_STREAM_TYPE = "windows_dshow"
DEFAULT_WINDOWS_FFMPEG_BINARY = "ffmpeg"

_DANGEROUS_NAME_PATTERN = re.compile(r"[\x00\r\n]")
_VIDEO_DEVICE_PATTERN = re.compile(r'"([^"]+)"\s+\(video\)', re.IGNORECASE)


def normalize_windows_ffmpeg_binary(ffmpeg_binary_path: str | None) -> str:
    return (
        (ffmpeg_binary_path or DEFAULT_WINDOWS_FFMPEG_BINARY).strip()
        or DEFAULT_WINDOWS_FFMPEG_BINARY
    )


def normalize_optional_text(value: str | None) -> str | None:
    normalized = (value or "").strip()
    return normalized or None


def validate_windows_camera_name(name: str | None) -> bool:
    normalized = (name or "").strip()
    return bool(normalized) and not _DANGEROUS_NAME_PATTERN.search(normalized)


def is_windows_ffmpeg_binary(ffmpeg_binary_path: str | None) -> bool:
    normalized = normalize_windows_ffmpeg_binary(ffmpeg_binary_path).lower().replace("\\", "/")
    return normalized.endswith(".exe") or normalized.startswith("/mnt/c/")


def is_windows_ffmpeg_available(ffmpeg_binary_path: str | None = None) -> bool:
    normalized = normalize_windows_ffmpeg_binary(ffmpeg_binary_path)
    if is_windows_ffmpeg_binary(normalized):
        return True
    return shutil.which(normalized) is not None


def windows_camera_status(
    *,
    camera_name: str | None,
    ffmpeg_binary_path: str | None = None,
    platform_name: str = sys.platform,
    ffmpeg_available: bool | None = None,
) -> str:
    if not validate_windows_camera_name(camera_name):
        return "camera_name_missing"
    if platform_name.startswith("linux") and not is_windows_ffmpeg_binary(ffmpeg_binary_path):
        return "unsupported_host"
    if is_windows_ffmpeg_binary(ffmpeg_binary_path):
        return "available"
    if ffmpeg_available is None:
        ffmpeg_available = is_windows_ffmpeg_available(ffmpeg_binary_path)
    if not ffmpeg_available:
        return "ffmpeg_missing"
    return "available"


def build_windows_dshow_list_devices_command(
    *,
    ffmpeg_binary_path: str | None = None,
) -> list[str]:
    return [
        normalize_windows_ffmpeg_binary(ffmpeg_binary_path),
        "-list_devices",
        "true",
        "-f",
        "dshow",
        "-i",
        "dummy",
    ]


def parse_windows_dshow_video_devices(output: str) -> list[str]:
    devices: list[str] = []
    for match in _VIDEO_DEVICE_PATTERN.finditer(output):
        name = match.group(1)
        if name not in devices:
            devices.append(name)
    return devices


def build_windows_dshow_mjpeg_command(
    camera_name: str,
    *,
    ffmpeg_binary_path: str | None = None,
    video_size: str | None = None,
    framerate: str | int | None = None,
    output_frame_rate: int = 5,
) -> list[str]:
    if not validate_windows_camera_name(camera_name):
        raise ValueError("invalid_windows_camera_name")
    command = [
        normalize_windows_ffmpeg_binary(ffmpeg_binary_path),
        "-f",
        "dshow",
    ]
    normalized_video_size = normalize_optional_text(video_size)
    normalized_framerate = normalize_optional_text(
        str(framerate) if framerate is not None else None
    )
    if normalized_video_size:
        command.extend(["-video_size", normalized_video_size])
    if normalized_framerate:
        command.extend(["-framerate", normalized_framerate])
    command.extend(
        [
            "-i",
            f"video={camera_name.strip()}",
            "-an",
            "-f",
            "image2pipe",
            "-vcodec",
            "mjpeg",
            "-r",
            str(output_frame_rate),
            "pipe:1",
        ]
    )
    return command


PopenFactory = Callable[..., subprocess.Popen[bytes]]


def start_windows_dshow_mjpeg_process(
    camera_name: str,
    *,
    ffmpeg_binary_path: str | None = None,
    video_size: str | None = None,
    framerate: str | int | None = None,
    popen_factory: PopenFactory = subprocess.Popen,
) -> subprocess.Popen[bytes]:
    command = build_windows_dshow_mjpeg_command(
        camera_name,
        ffmpeg_binary_path=ffmpeg_binary_path,
        video_size=video_size,
        framerate=framerate,
    )
    return popen_factory(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
    )


def build_windows_dshow_frame_capture_command(
    camera_name: str,
    *,
    ffmpeg_binary_path: str | None = None,
    video_size: str | None = None,
    framerate: str | int | None = None,
) -> list[str]:
    if not validate_windows_camera_name(camera_name):
        raise ValueError("invalid_windows_camera_name")
    command = [
        normalize_windows_ffmpeg_binary(ffmpeg_binary_path),
        "-f",
        "dshow",
    ]
    normalized_video_size = normalize_optional_text(video_size)
    normalized_framerate = normalize_optional_text(
        str(framerate) if framerate is not None else None
    )
    if normalized_video_size:
        command.extend(["-video_size", normalized_video_size])
    if normalized_framerate:
        command.extend(["-framerate", normalized_framerate])
    command.extend(
        [
            "-i",
            f"video={camera_name.strip()}",
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


def start_windows_dshow_frame_capture_process(
    camera_name: str,
    *,
    ffmpeg_binary_path: str | None = None,
    video_size: str | None = None,
    framerate: str | int | None = None,
    popen_factory: PopenFactory = subprocess.Popen,
) -> subprocess.Popen[bytes]:
    command = build_windows_dshow_frame_capture_command(
        camera_name,
        ffmpeg_binary_path=ffmpeg_binary_path,
        video_size=video_size,
        framerate=framerate,
    )
    return popen_factory(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
    )


def capture_windows_dshow_frame(
    camera_name: str,
    *,
    ffmpeg_binary_path: str | None = None,
    video_size: str | None = None,
    framerate: str | int | None = None,
    popen_factory: PopenFactory = subprocess.Popen,
) -> bytes:
    process = start_windows_dshow_frame_capture_process(
        camera_name,
        ffmpeg_binary_path=ffmpeg_binary_path,
        video_size=video_size,
        framerate=framerate,
        popen_factory=popen_factory,
    )
    return read_one_jpeg_frame(process)


__all__ = [
    "DEFAULT_WINDOWS_FFMPEG_BINARY",
    "MJPEG_BOUNDARY",
    "WINDOWS_DSHOW_STREAM_TYPE",
    "build_windows_dshow_frame_capture_command",
    "build_windows_dshow_list_devices_command",
    "build_windows_dshow_mjpeg_command",
    "capture_windows_dshow_frame",
    "is_windows_ffmpeg_available",
    "is_windows_ffmpeg_binary",
    "iter_multipart_mjpeg",
    "normalize_windows_ffmpeg_binary",
    "parse_windows_dshow_video_devices",
    "start_windows_dshow_frame_capture_process",
    "start_windows_dshow_mjpeg_process",
    "validate_windows_camera_name",
    "windows_camera_status",
]
