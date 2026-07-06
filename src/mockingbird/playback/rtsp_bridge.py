"""Optional RTSP-to-browser playback bridge helpers."""

from __future__ import annotations

from collections.abc import Callable, Iterator
import shutil
import subprocess
from typing import BinaryIO
from urllib.parse import urlsplit, urlunsplit

MJPEG_BOUNDARY = "frame"


def is_ffmpeg_available(ffmpeg_binary: str = "ffmpeg") -> bool:
    return shutil.which(ffmpeg_binary) is not None


def redact_url(url: str) -> str:
    try:
        parts = urlsplit(url)
    except ValueError:
        return url
    if "@" not in parts.netloc:
        return url
    host_port = parts.netloc.rsplit("@", 1)[1]
    return urlunsplit((parts.scheme, f"***:***@{host_port}", parts.path, parts.query, parts.fragment))


def validate_rtsp_url(url: str) -> bool:
    try:
        parts = urlsplit(url)
    except ValueError:
        return False
    return parts.scheme.lower() in {"rtsp", "rtsps"} and bool(parts.netloc)


def build_rtsp_mjpeg_command(
    url: str,
    *,
    ffmpeg_binary: str = "ffmpeg",
    frame_rate: int = 5,
    quality: int = 5,
) -> list[str]:
    if not validate_rtsp_url(url):
        raise ValueError("invalid_rtsp_url")
    return [
        ffmpeg_binary,
        "-hide_banner",
        "-loglevel",
        "error",
        "-rtsp_transport",
        "tcp",
        "-i",
        url,
        "-an",
        "-f",
        "mjpeg",
        "-q:v",
        str(quality),
        "-r",
        str(frame_rate),
        "pipe:1",
    ]


PopenFactory = Callable[..., subprocess.Popen[bytes]]


def start_rtsp_mjpeg_process(
    url: str,
    *,
    popen_factory: PopenFactory = subprocess.Popen,
) -> subprocess.Popen[bytes]:
    command = build_rtsp_mjpeg_command(url)
    return popen_factory(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
    )


def iter_multipart_mjpeg(
    process: subprocess.Popen[bytes],
    *,
    boundary: str = MJPEG_BOUNDARY,
    chunk_size: int = 64 * 1024,
    on_frame: Callable[[bytes], None] | None = None,
) -> Iterator[bytes]:
    stdout = process.stdout
    if stdout is None:
        _stop_process(process)
        return

    buffer = bytearray()
    try:
        while True:
            chunk = _read_stdout(stdout, chunk_size)
            if not chunk:
                break
            buffer.extend(chunk)
            yield from _extract_multipart_frames(buffer, boundary, on_frame=on_frame)
    finally:
        _stop_process(process)


def _read_stdout(stdout: BinaryIO, chunk_size: int) -> bytes:
    return stdout.read(chunk_size)


def _extract_multipart_frames(
    buffer: bytearray,
    boundary: str,
    *,
    on_frame: Callable[[bytes], None] | None = None,
) -> Iterator[bytes]:
    while True:
        start = buffer.find(b"\xff\xd8")
        if start < 0:
            if len(buffer) > 1:
                del buffer[:-1]
            return
        end = buffer.find(b"\xff\xd9", start + 2)
        if end < 0:
            if start > 0:
                del buffer[:start]
            return

        frame = bytes(buffer[start : end + 2])
        del buffer[: end + 2]
        if on_frame is not None:
            on_frame(frame)
        header = (
            f"--{boundary}\r\n"
            "Content-Type: image/jpeg\r\n"
            f"Content-Length: {len(frame)}\r\n\r\n"
        ).encode("ascii")
        yield header + frame + b"\r\n"


def _stop_process(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=2)
