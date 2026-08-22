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


def is_rtsps_url(url: str) -> bool:
    """Whether `url` uses the `rtsps://` (RTSP-over-TLS) scheme specifically,
    as opposed to plain `rtsp://`. See `RTSPS_TRANSPORT_SUPPORTED`'s
    docstring for why this distinction matters."""

    try:
        parts = urlsplit(url)
    except ValueError:
        return False
    return parts.scheme.lower() == "rtsps"


# v0.1 Acquisition/Ingest Interoperability Closure v1 ("II.6 RTSPS"): this
# bridge's ffmpeg invocation (`build_rtsp_mjpeg_command`, `-rtsp_transport
# tcp`) never constructs a TLS-secured lower transport for the RTSP
# control/data connection. Empirically verified against this deployment's
# ffmpeg build (6.1.1, configured `--enable-gnutls`): opening an
# `rtsps://` URL -- with or without an explicit `-rtsp_transport` flag --
# still starts a *plain* `tcp://` connection, identical to `rtsp://`;
# ffmpeg's RTSP demuxer does not upgrade transport based on URL scheme in
# this configuration. MockingBird must never accept an `rtsps://` URL and
# silently serve it over plaintext -- that would tell a user their camera
# connection is secure when it is not (the "do not silently downgrade
# rtsps:// to rtsp://" requirement). `False` is therefore a durable,
# evidence-based product fact about this codebase's current transport
# wiring, not a live runtime probe -- there is no safe way to probe
# genuine TLS support without a real TLS-terminating RTSP server to test
# against, and probing a user's actual camera at status-read time would
# violate this contract's own side-effect-free status guarantee (see
# docs/source-connection-provider-contract.md). Revisit only alongside a
# deliberate, reviewed change to how this bridge invokes ffmpeg (an
# explicit TLS lower-transport, or a dependency change), never by flipping
# this constant alone without new evidence.
RTSPS_TRANSPORT_SUPPORTED = False


class RtspsUnsupportedError(ValueError):
    """Raised when a caller asks this bridge to actually open an
    `rtsps://` URL while `RTSPS_TRANSPORT_SUPPORTED` is `False`. Product-
    level callers should check `is_rtsps_url`/`RTSPS_TRANSPORT_SUPPORTED`
    themselves first (see `_external_url_stream_playback_status`'s RTSP
    branch) to report an honest, actionable capability state instead of
    relying on this exception -- it exists as a defense-in-depth guard at
    the point ffmpeg would actually be invoked, not as the primary UX."""


def build_rtsp_mjpeg_command(
    url: str,
    *,
    ffmpeg_binary: str = "ffmpeg",
    frame_rate: int = 5,
    quality: int = 5,
) -> list[str]:
    if not validate_rtsp_url(url):
        raise ValueError("invalid_rtsp_url")
    if is_rtsps_url(url) and not RTSPS_TRANSPORT_SUPPORTED:
        raise RtspsUnsupportedError("rtsps_unsupported")
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
