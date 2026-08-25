"""Optional RTSP-to-browser playback bridge helpers."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass
import re
import shutil
import subprocess
import threading
import time
from typing import BinaryIO
from urllib.parse import quote, urlsplit, urlunsplit

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


# Matches a `scheme://user:pass@` credential prefix anywhere inside a longer
# text blob -- unlike `redact_url` (which requires the *entire* string to be
# one clean URL), this scrubs a credentialed URL that ffmpeg has echoed back
# as a *substring* of a longer diagnostic sentence (a real, observed ffmpeg
# behavior for several RTSP I/O error paths -- it is not consistent about
# never printing the `-i` input verbatim). Live Setup Validation v1 ("B6
# credential safety"): this is the one place raw subprocess stderr is ever
# read, so it is also the one place that text must be scrubbed before it can
# reach a log line, an API response, or any other bounded diagnostic.
_CREDENTIALED_URL_PATTERN = re.compile(r"([a-zA-Z][a-zA-Z0-9+.\-]*://)[^\s/@]+:[^\s/@]+@")


def redact_credentials_in_text(text: str) -> str:
    """A safe no-op for text with no embedded `scheme://user:pass@` --
    scrubs every match it does find, not just the first."""

    return _CREDENTIALED_URL_PATTERN.sub(r"\1***:***@", text)


def embed_rtsp_credentials(url: str, *, username: str | None, password: str | None) -> str:
    """Embed a separately-entered username/password as URL userinfo
    (`rtsp://host/path` -> `rtsp://user:pass@host/path`) so manual RTSP
    setup's own "Auth username"/"Auth password" fields actually take
    effect, instead of a user typing credentials that are silently
    ignored -- ffmpeg parses URL userinfo for RTSP Basic/Digest auth
    natively, so no MockingBird-side auth handling is needed beyond this.

    Camera / Source Experience & First-Hour Setup Closure v1: prior to
    this, `auth_username`/`auth_password` were collected in the Add
    Camera UI (their own field descriptions honestly disclosed "Not used
    for preview fetch yet") but never reached any connection attempt --
    only a URL with credentials already hand-embedded by the user ever
    worked. This closes that gap the same way `onvif_client.
    embed_credentials_in_uri` already closes it for an ONVIF-resolved
    stream URI, so manually-typed RTSP gets the identical, already-proven
    mechanism rather than a second one.

    A URL that already carries embedded credentials is left unmodified
    (the URL wins, never double-embedded). A safe no-op when the URL
    isn't parseable or neither credential is set."""

    if not username and not password:
        return url
    try:
        parts = urlsplit(url)
    except ValueError:
        return url
    if "@" in parts.netloc:
        return url
    userinfo = f"{quote(username or '', safe='')}:{quote(password or '', safe='')}@"
    return urlunsplit((parts.scheme, f"{userinfo}{parts.netloc}", parts.path, parts.query, parts.fragment))


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
    capture_stderr: bool = False,
) -> subprocess.Popen[bytes]:
    command = build_rtsp_mjpeg_command(url)
    return popen_factory(
        command,
        stdout=subprocess.PIPE,
        # `capture_stderr` defaults to `False` (unchanged: every existing
        # live-playback caller keeps discarding ffmpeg's stderr) -- Live
        # Setup Validation v1 ("B4 error distinctions") is the one caller
        # that opts in, to classify a probe failure from ffmpeg's own
        # (bounded, redacted-before-use) error text instead of guessing.
        stderr=subprocess.PIPE if capture_stderr else subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
    )


def iter_multipart_mjpeg(
    process: subprocess.Popen[bytes],
    *,
    boundary: str = MJPEG_BOUNDARY,
    chunk_size: int = 64 * 1024,
    on_frame: Callable[[bytes], None] | None = None,
    on_chunk: Callable[[], None] | None = None,
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
            # `on_chunk` fires on any bytes at all, before a full frame is
            # necessarily assembled -- Live Setup Validation v1 ("B3 probe
            # contract") uses this as its "did the source respond at all"
            # signal, distinct from (and earlier than) `on_frame`'s "one
            # full usable frame decoded" signal.
            if on_chunk is not None:
                on_chunk()
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


# ---------------------------------------------------------------------------
# Live RTSP Setup Validation v1 ("bounded live probe" -- see the Pre-Freeze
# Operability Gap Closure v1 milestone, Part B). Manual RTSP setup must not
# claim a source is ready merely because its URL is syntactically valid
# (B1); this reuses this module's own ffmpeg RTSP-to-MJPEG bridge above --
# never a second decoder -- to connect, let RTSP negotiate, and decode one
# real frame before ever reporting "ready".
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RtspProbeResult:
    """One bounded outcome of a live RTSP setup probe. `ready=True` means a
    connection was established, RTSP negotiated a stream, and one real JPEG
    frame was decoded from it -- never merely that the URL parsed. `code`
    is `"ready"` on success, otherwise a stable `acquisition_provider` code
    from `diagnostics.error_taxonomy`. `detail` is a short, already
    credential-redacted, advanced-only diagnostic (a trimmed ffmpeg stderr
    tail); `None` on success or when no distinguishing evidence was
    available. Never contains credentials, a stream URL, or image bytes."""

    ready: bool
    code: str
    detail: str | None
    elapsed_seconds: float


#: Bounded wait for the very first byte of any kind back from ffmpeg (stdout
#: data, or the process simply exiting) -- exceeding this with genuinely
#: nothing back is reported as "source unreachable / connection timed out".
RTSP_PROBE_CONNECT_TIMEOUT_SECONDS = 4.0

#: Bounded wall-clock ceiling for the whole probe (connect + negotiate +
#: decode one frame), measured from the same start point as the connect
#: timeout above -- comfortably under this product's own frontend
#: `VALIDATE_TIMEOUT_MS` (10s, `CameraSetupPage.tsx`), leaving margin for
#: the surrounding request/DB overhead.
RTSP_PROBE_TOTAL_TIMEOUT_SECONDS = 8.0

_PROBE_MAX_STDERR_BYTES = 4096
_PROBE_POLL_INTERVAL_SECONDS = 0.02


def probe_rtsp_stream(
    url: str,
    *,
    connect_timeout_seconds: float = RTSP_PROBE_CONNECT_TIMEOUT_SECONDS,
    total_timeout_seconds: float = RTSP_PROBE_TOTAL_TIMEOUT_SECONDS,
    ffmpeg_binary: str = "ffmpeg",
    popen_factory: PopenFactory = subprocess.Popen,
) -> RtspProbeResult:
    """Bounded, one-shot live RTSP setup probe.

    Never builds a second RTSP decoder or a standing background monitoring
    service: this starts exactly one ffmpeg process through
    `start_rtsp_mjpeg_process`/`iter_multipart_mjpeg` (the same primitive
    live playback already uses), reads for one real decoded frame, and
    always tears the process down before returning -- bounded by process
    cleanup (`_stop_process`'s existing terminate-then-kill discipline) on
    every exit path, never a leaked/zombie decode process.

    Bounded by two independent wall-clock ceilings: `connect_timeout_seconds`
    for the first byte of any kind back from ffmpeg, `total_timeout_seconds`
    for the whole probe including decoding one frame. Both are enforced by
    polling a background reader thread rather than `select()` on the pipe --
    `select()` does not work on pipe file descriptors on Windows, and this
    product runs on both platforms.

    Never downgrades `rtsps://` to `rtsp://` and never starts a process for
    one at all (see `RTSPS_TRANSPORT_SUPPORTED`'s own docstring).
    """

    started = time.monotonic()

    def _elapsed() -> float:
        return time.monotonic() - started

    if not validate_rtsp_url(url):
        return RtspProbeResult(False, "camera_setup_invalid_url", None, _elapsed())
    if is_rtsps_url(url) and not RTSPS_TRANSPORT_SUPPORTED:
        return RtspProbeResult(False, "camera_setup_rtsps_unsupported", None, _elapsed())
    if not is_ffmpeg_available(ffmpeg_binary):
        return RtspProbeResult(False, "camera_setup_rtsp_ffmpeg_unavailable", None, _elapsed())

    try:
        process = start_rtsp_mjpeg_process(url, popen_factory=popen_factory, capture_stderr=True)
    except OSError:
        # A TOCTOU race against the `is_ffmpeg_available` check just above
        # (the binary vanished between the check and the actual spawn) --
        # mirrors `recorded_video_source.sample_recorded_video_frames`'s
        # identical `FileNotFoundError` handling for the same race.
        return RtspProbeResult(False, "camera_setup_rtsp_ffmpeg_unavailable", None, _elapsed())

    first_byte_event = threading.Event()
    frame_box: list[bytes] = []

    def _capture(payload: bytes) -> None:
        if not frame_box:
            frame_box.append(payload)

    def _drain() -> None:
        generator = iter_multipart_mjpeg(process, on_frame=_capture, on_chunk=first_byte_event.set)
        try:
            for _ in generator:
                if frame_box:
                    break
        finally:
            # Unwinds `iter_multipart_mjpeg`'s own `finally: _stop_process`
            # as soon as one frame is captured -- the probe never keeps
            # ffmpeg running a moment longer than proving usability needs.
            generator.close()

    reader = threading.Thread(target=_drain, daemon=True)
    reader.start()

    responded = _wait_until(
        lambda: first_byte_event.is_set() or not reader.is_alive(),
        timeout_seconds=connect_timeout_seconds,
    )
    if not responded:
        # Truly nothing back at all -- not one byte, and ffmpeg is still
        # trying -- within the connect window.
        _stop_process(process)
        reader.join(timeout=2)
        return RtspProbeResult(
            False, "camera_setup_rtsp_unreachable", _redacted_stderr(process), _elapsed(),
        )

    reader.join(timeout=max(0.0, total_timeout_seconds - _elapsed()))
    if reader.is_alive():
        # Bytes were flowing (or the process was still starting) but no
        # complete frame assembled within the total bound -- deliberately a
        # distinct, less committal code than "unreachable" (B4).
        _stop_process(process)
        reader.join(timeout=2)
        return RtspProbeResult(
            False, "camera_setup_rtsp_validation_timed_out", _redacted_stderr(process), _elapsed(),
        )

    if frame_box:
        return RtspProbeResult(True, "ready", None, _elapsed())

    detail = _redacted_stderr(process)
    code = _classify_probe_failure(detail, any_bytes_received=first_byte_event.is_set())
    return RtspProbeResult(False, code, detail, _elapsed())


# ---------------------------------------------------------------------------
# Camera / Source Experience & First-Hour Setup Closure v1: a bounded,
# transient "check the picture" preview -- an explicit user action during
# Add Camera, distinct from `probe_rtsp_stream` above (whose own
# `RtspProbeResult` docstring deliberately never carries image bytes).
# Mirrors the already-accepted Camera Node preview's contract exactly: one
# real frame, never persisted, never Visit/Evidence/Observation truth. This
# duplicates `probe_rtsp_stream`'s connect/negotiate/decode-one-frame
# orchestration rather than reshaping that function's tested, documented
# no-image-bytes contract -- the two are kept deliberately separate.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RtspPreviewCapture:
    """One bounded, transient RTSP setup-preview outcome. `ok=True` means
    `frame_jpeg` holds one real decoded JPEG frame; otherwise `code` is a
    stable code from the same vocabulary `probe_rtsp_stream` uses and
    `frame_jpeg` is `None`. Never persisted by any caller."""

    ok: bool
    code: str
    frame_jpeg: bytes | None


def capture_rtsp_preview_frame(
    url: str,
    *,
    connect_timeout_seconds: float = RTSP_PROBE_CONNECT_TIMEOUT_SECONDS,
    total_timeout_seconds: float = RTSP_PROBE_TOTAL_TIMEOUT_SECONDS,
    ffmpeg_binary: str = "ffmpeg",
    popen_factory: PopenFactory = subprocess.Popen,
) -> RtspPreviewCapture:
    """Bounded, one-shot preview-frame capture for Add Camera. Reuses the
    exact same primitives `probe_rtsp_stream` does (`start_rtsp_mjpeg_
    process`/`iter_multipart_mjpeg`) -- never a second RTSP decoder --
    connects, lets RTSP negotiate, decodes one real frame, and always
    tears the ffmpeg process down before returning. Never downgrades
    `rtsps://` to `rtsp://` (see `RTSPS_TRANSPORT_SUPPORTED`)."""

    started = time.monotonic()

    def _elapsed() -> float:
        return time.monotonic() - started

    if not validate_rtsp_url(url):
        return RtspPreviewCapture(False, "camera_setup_invalid_url", None)
    if is_rtsps_url(url) and not RTSPS_TRANSPORT_SUPPORTED:
        return RtspPreviewCapture(False, "camera_setup_rtsps_unsupported", None)
    if not is_ffmpeg_available(ffmpeg_binary):
        return RtspPreviewCapture(False, "camera_setup_rtsp_ffmpeg_unavailable", None)

    try:
        process = start_rtsp_mjpeg_process(url, popen_factory=popen_factory, capture_stderr=True)
    except OSError:
        # Same TOCTOU race `probe_rtsp_stream` guards against.
        return RtspPreviewCapture(False, "camera_setup_rtsp_ffmpeg_unavailable", None)

    first_byte_event = threading.Event()
    frame_box: list[bytes] = []

    def _capture(payload: bytes) -> None:
        if not frame_box:
            frame_box.append(payload)

    def _drain() -> None:
        generator = iter_multipart_mjpeg(process, on_frame=_capture, on_chunk=first_byte_event.set)
        try:
            for _ in generator:
                if frame_box:
                    break
        finally:
            generator.close()

    reader = threading.Thread(target=_drain, daemon=True)
    reader.start()

    responded = _wait_until(
        lambda: first_byte_event.is_set() or not reader.is_alive(),
        timeout_seconds=connect_timeout_seconds,
    )
    if not responded:
        _stop_process(process)
        reader.join(timeout=2)
        return RtspPreviewCapture(False, "camera_setup_rtsp_unreachable", None)

    reader.join(timeout=max(0.0, total_timeout_seconds - _elapsed()))
    if reader.is_alive():
        _stop_process(process)
        reader.join(timeout=2)
        return RtspPreviewCapture(False, "camera_setup_rtsp_validation_timed_out", None)

    if frame_box:
        return RtspPreviewCapture(True, "ready", frame_box[0])

    detail = _redacted_stderr(process)
    code = _classify_probe_failure(detail, any_bytes_received=first_byte_event.is_set())
    return RtspPreviewCapture(False, code, None)


def _wait_until(condition: Callable[[], bool], *, timeout_seconds: float) -> bool:
    """Portable bounded wait for `condition()` -- avoids `select()` on a
    pipe (unsupported on Windows) while still returning as soon as
    `condition` becomes true, rather than always blocking the full
    timeout."""

    deadline = time.monotonic() + timeout_seconds
    while True:
        if condition():
            return True
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return False
        time.sleep(min(_PROBE_POLL_INTERVAL_SECONDS, remaining))


def _redacted_stderr(
    process: subprocess.Popen[bytes], *, max_bytes: int = _PROBE_MAX_STDERR_BYTES,
) -> str | None:
    """Bounded, credential-redacted ffmpeg stderr tail -- only ever read
    after the process is confirmed stopped (mirrors `recorded_video_source.
    sample_recorded_video_frames`'s identical post-mortem-only stderr read),
    so this can never block waiting on a still-running process."""

    stderr = process.stderr
    if stderr is None:
        return None
    try:
        raw = stderr.read(max_bytes)
    except (OSError, ValueError):  # pragma: no cover - defensive, closed pipe
        return None
    if not raw:
        return None
    text = raw.decode("utf-8", errors="replace").strip()
    if not text:
        return None
    return redact_credentials_in_text(text)[:max_bytes]


def _classify_probe_failure(detail: str | None, *, any_bytes_received: bool) -> str:
    """Distinguish a probe failure only where ffmpeg's own stderr text
    gives real evidence (B4) -- falls back to a deliberately less-specific,
    still-truthful code otherwise, never a guess. `any_bytes_received` is
    the one non-text signal available: real stdout bytes arrived (RTSP
    negotiated and ffmpeg began emitting decoded video), so a failure past
    that point reads as a decode problem, not a negotiation/connection
    one."""

    text = (detail or "").lower()
    if any(marker in text for marker in ("401", "unauthorized", "403", "forbidden")):
        return "camera_setup_rtsp_authentication_failed"
    if any(
        marker in text
        for marker in (
            "connection refused",
            "connection timed out",
            "no route to host",
            "network is unreachable",
            "could not resolve",
            "name or service not known",
            "host is down",
        )
    ):
        return "camera_setup_rtsp_unreachable"
    if "codec" in text and ("not supported" in text or "unsupported" in text):
        return "camera_setup_rtsp_unsupported_codec"
    if any(
        marker in text
        for marker in ("404", "not found", "method setup failed", "method describe failed")
    ):
        return "camera_setup_rtsp_negotiation_failed"
    if any_bytes_received:
        return "camera_setup_rtsp_decode_failed"
    return "camera_setup_rtsp_negotiation_failed"
