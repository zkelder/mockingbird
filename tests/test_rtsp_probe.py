"""Focused tests for `mockingbird.playback.rtsp_bridge.probe_rtsp_stream` --
Live Setup Validation v1 (Pre-Freeze Operability Gap Closure v1, Part B).

Manual RTSP setup must not claim a source is ready merely because its URL
is syntactically valid (B1). These tests exercise the bounded live probe's
own boundary/timeout/classification/credential-redaction contract directly,
using this repository's established fake-process convention (mirroring
`FakeFfmpegProcess`/`FakeStdout` in tests/test_stream_playback_contract.py
and `_FakeCameraProcess` in tests/test_live_camera_session.py) -- plus one
real local ffmpeg decode test (B8), since no RTSP server fixture exists in
this repository and building one would be heavy infrastructure for a
bounded validation probe.

Integration-level wiring through the real Camera Setup validation path
(the API/`ProductRepository.validate_camera_setup` layer, including the B6
credential-leak regression) lives in tests/test_camera_setup.py instead.
"""

from __future__ import annotations

import shutil
import subprocess
import time

import pytest

from mockingbird.playback import rtsp_bridge


class _FakeStream:
    """A readable, in-memory byte source standing in for a real process
    pipe. `delay_seconds` (applied once `delay_after` reads have already
    happened) lets a test exercise the probe's *real* threading/timeout
    logic deterministically -- short enough to keep the test fast, long
    enough to reliably exceed a tiny injected timeout."""

    def __init__(
        self, chunks: list[bytes], *, delay_seconds: float = 0.0, delay_after: int = 0,
    ) -> None:
        self._chunks = list(chunks)
        self._delay_seconds = delay_seconds
        self._delay_after = delay_after
        self._read_count = 0

    def read(self, size: int = -1) -> bytes:
        self._read_count += 1
        if self._delay_seconds and self._read_count > self._delay_after:
            time.sleep(self._delay_seconds)
        return self._chunks.pop(0) if self._chunks else b""


class _FakeProbeProcess:
    """Minimal Popen-shaped fixture -- exercises exactly the duck-typed
    contract `probe_rtsp_stream` actually uses (`.stdout`, `.stderr`,
    `.poll()`, `.terminate()`, `.kill()`, `.wait()`), never a real ffmpeg
    subprocess."""

    def __init__(
        self,
        *,
        stdout_chunks: list[bytes] | None = None,
        stdout_delay_seconds: float = 0.0,
        stdout_delay_after: int = 0,
        stderr_text: bytes = b"",
    ) -> None:
        self.stdout = _FakeStream(
            stdout_chunks or [], delay_seconds=stdout_delay_seconds, delay_after=stdout_delay_after,
        )
        self.stderr = _FakeStream([stderr_text] if stderr_text else [])
        self.returncode: int | None = None
        self.terminate_calls = 0
        self.kill_calls = 0

    def poll(self) -> int | None:
        return self.returncode

    def terminate(self) -> None:
        self.terminate_calls += 1
        self.returncode = 1

    def kill(self) -> None:
        self.kill_calls += 1
        self.returncode = -9

    def wait(self, timeout: float | None = None) -> int:
        return self.returncode if self.returncode is not None else 0


_VALID_URL = "rtsp://camera.local:554/stream"
_ONE_JPEG_FRAME = b"\xff\xd8" + b"fixture-frame-bytes" + b"\xff\xd9"


def _factory(process: _FakeProbeProcess):
    calls: list[list[str]] = []

    def _popen(command: list[str], **kwargs: object) -> _FakeProbeProcess:
        calls.append(command)
        return process

    return _popen, calls


# --- B1/B9#1: a real probe (not just syntax) must succeed on real evidence -


def test_probe_succeeds_and_decodes_one_real_frame(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rtsp_bridge, "is_ffmpeg_available", lambda *a, **k: True)
    process = _FakeProbeProcess(stdout_chunks=[_ONE_JPEG_FRAME])
    popen_factory, calls = _factory(process)

    result = rtsp_bridge.probe_rtsp_stream(_VALID_URL, popen_factory=popen_factory)

    assert result.ready is True
    assert result.code == "ready"
    assert result.detail is None
    assert len(calls) == 1
    assert _VALID_URL in calls[0]


# --- B9#2: syntax alone is not sufficient -- invalid input never spawns ----


def test_probe_rejects_invalid_url_without_spawning_a_process(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rtsp_bridge, "is_ffmpeg_available", lambda *a, **k: True)
    process = _FakeProbeProcess(stdout_chunks=[_ONE_JPEG_FRAME])
    popen_factory, calls = _factory(process)

    result = rtsp_bridge.probe_rtsp_stream("not a url", popen_factory=popen_factory)

    assert result.ready is False
    assert result.code == "camera_setup_invalid_url"
    assert calls == []


def test_probe_reports_ffmpeg_unavailable_without_spawning_a_process(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rtsp_bridge, "is_ffmpeg_available", lambda *a, **k: False)
    process = _FakeProbeProcess(stdout_chunks=[_ONE_JPEG_FRAME])
    popen_factory, calls = _factory(process)

    result = rtsp_bridge.probe_rtsp_stream(_VALID_URL, popen_factory=popen_factory)

    assert result.ready is False
    assert result.code == "camera_setup_rtsp_ffmpeg_unavailable"
    assert calls == []


# --- B5/B9#9: RTSPS stays genuinely unsupported, never downgraded ----------


def test_probe_never_downgrades_or_starts_a_process_for_rtsps(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rtsp_bridge, "is_ffmpeg_available", lambda *a, **k: True)
    process = _FakeProbeProcess(stdout_chunks=[_ONE_JPEG_FRAME])
    popen_factory, calls = _factory(process)

    result = rtsp_bridge.probe_rtsp_stream("rtsps://camera.local:322/stream", popen_factory=popen_factory)

    assert result.ready is False
    assert result.code == "camera_setup_rtsps_unsupported"
    assert calls == []  # never even attempted a plaintext fallback


# --- B3/B9#3: bounded connect timeout, honest when nothing ever responds ---


def test_probe_reports_unreachable_when_nothing_ever_responds(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rtsp_bridge, "is_ffmpeg_available", lambda *a, **k: True)
    process = _FakeProbeProcess(stdout_chunks=[], stdout_delay_seconds=0.3)
    popen_factory, _calls = _factory(process)

    result = rtsp_bridge.probe_rtsp_stream(
        _VALID_URL, popen_factory=popen_factory, connect_timeout_seconds=0.05, total_timeout_seconds=0.2,
    )

    assert result.ready is False
    assert result.code == "camera_setup_rtsp_unreachable"


# --- B3/B9#6: total-timeout distinct from connect-timeout, process cleaned -


def test_probe_reports_validation_timed_out_and_cleans_up_the_process(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rtsp_bridge, "is_ffmpeg_available", lambda *a, **k: True)
    # First read returns immediately (connects fine); the second stalls --
    # bytes were flowing, so this must be a distinct code from "unreachable".
    process = _FakeProbeProcess(stdout_chunks=[b"x"], stdout_delay_seconds=0.3, stdout_delay_after=1)
    popen_factory, _calls = _factory(process)

    result = rtsp_bridge.probe_rtsp_stream(
        _VALID_URL, popen_factory=popen_factory, connect_timeout_seconds=1.0, total_timeout_seconds=0.05,
    )

    assert result.ready is False
    assert result.code == "camera_setup_rtsp_validation_timed_out"
    # Bounded process cleanup (B3): the probe must never leak a running
    # process after giving up on it.
    assert process.terminate_calls >= 1


# --- B4: distinguish only where ffmpeg's own evidence supports it ----------


def test_probe_distinguishes_authentication_failure_from_stderr_evidence(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rtsp_bridge, "is_ffmpeg_available", lambda *a, **k: True)
    process = _FakeProbeProcess(
        stdout_chunks=[b"x"], stderr_text=b"[rtsp @ 0x0] method DESCRIBE failed: 401 Unauthorized",
    )
    popen_factory, _calls = _factory(process)

    result = rtsp_bridge.probe_rtsp_stream(_VALID_URL, popen_factory=popen_factory)

    assert result.ready is False
    assert result.code == "camera_setup_rtsp_authentication_failed"


def test_probe_distinguishes_unsupported_codec_from_stderr_evidence(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rtsp_bridge, "is_ffmpeg_available", lambda *a, **k: True)
    process = _FakeProbeProcess(
        stdout_chunks=[b"x"], stderr_text=b"Unknown codec: this codec is not supported by this build",
    )
    popen_factory, _calls = _factory(process)

    result = rtsp_bridge.probe_rtsp_stream(_VALID_URL, popen_factory=popen_factory)

    assert result.ready is False
    assert result.code == "camera_setup_rtsp_unsupported_codec"


def test_probe_falls_back_to_negotiation_failed_without_any_evidence(monkeypatch: pytest.MonkeyPatch) -> None:
    """B4: never guess a specific code (e.g. authentication_failed) from a
    generic failure -- an immediate, evidence-free exit gets the honest,
    less-specific code."""

    monkeypatch.setattr(rtsp_bridge, "is_ffmpeg_available", lambda *a, **k: True)
    process = _FakeProbeProcess(stdout_chunks=[], stderr_text=b"")
    popen_factory, _calls = _factory(process)

    result = rtsp_bridge.probe_rtsp_stream(_VALID_URL, popen_factory=popen_factory)

    assert result.ready is False
    assert result.code == "camera_setup_rtsp_negotiation_failed"


def test_probe_falls_back_to_decode_failed_when_bytes_flow_without_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The one non-text signal available (B4's own "any_bytes_received"):
    real stdout bytes arrived (negotiation succeeded) but no frame ever
    assembled and stderr gives no specific reason -- reads as a decode
    problem, not a negotiation/connection one."""

    monkeypatch.setattr(rtsp_bridge, "is_ffmpeg_available", lambda *a, **k: True)
    process = _FakeProbeProcess(stdout_chunks=[b"not-a-jpeg-frame"], stderr_text=b"")
    popen_factory, _calls = _factory(process)

    result = rtsp_bridge.probe_rtsp_stream(_VALID_URL, popen_factory=popen_factory)

    assert result.ready is False
    assert result.code == "camera_setup_rtsp_decode_failed"


# --- B6 (mandatory): credentials never leak into any diagnostic ------------


def test_redact_credentials_in_text_scrubs_only_the_credential_portion() -> None:
    assert rtsp_bridge.redact_credentials_in_text("no url in this text at all") == (
        "no url in this text at all"
    )

    leaky = "rtsp://setup-user:UnmistakableSecret99@camera.local:554/stream: 404 Not Found"
    scrubbed = rtsp_bridge.redact_credentials_in_text(leaky)
    assert "UnmistakableSecret99" not in scrubbed
    assert scrubbed == "rtsp://***:***@camera.local:554/stream: 404 Not Found"

    two_urls = f"{leaky} (retried at rtsp://other:UnmistakableSecret99@camera.local:554/stream)"
    assert "UnmistakableSecret99" not in rtsp_bridge.redact_credentials_in_text(two_urls)


def test_probe_redacts_credentials_from_the_returned_diagnostic_detail(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rtsp_bridge, "is_ffmpeg_available", lambda *a, **k: True)
    password = "UnmistakableFakePassword77"
    process = _FakeProbeProcess(
        stdout_chunks=[b"x"],
        stderr_text=f"rtsp://user:{password}@camera.local:554/stream: Server returned 404 Not Found".encode(),
    )
    popen_factory, _calls = _factory(process)

    result = rtsp_bridge.probe_rtsp_stream(_VALID_URL, popen_factory=popen_factory)

    assert result.ready is False
    assert password not in (result.detail or "")


# --- B8: at least one real local ffmpeg media decode test ------------------


def _has_real_ffmpeg() -> bool:
    return shutil.which("ffmpeg") is not None


@pytest.mark.skipif(not _has_real_ffmpeg(), reason="ffmpeg not available in this environment")
def test_real_ffmpeg_mjpeg_output_decodes_through_the_same_frame_parser() -> None:
    """No RTSP server fixture exists in this repository, and building one
    would be heavy infrastructure for a bounded setup-validation probe
    (B8) -- so this proves the *real* mechanism `probe_rtsp_stream` itself
    uses (`iter_multipart_mjpeg`'s buffer-scan/frame-extraction) against
    genuine ffmpeg MJPEG output from a local synthetic test pattern, the
    same primitive already relied on (unmodified) for live RTSP playback
    and recorded-media decode."""

    command = [
        "ffmpeg", "-hide_banner", "-loglevel", "error",
        "-f", "lavfi", "-i", "color=c=blue:s=64x64:d=1",
        "-an", "-f", "mjpeg", "-q:v", "5", "-r", "2", "pipe:1",
    ]
    process = subprocess.Popen(  # noqa: S603 -- fixed argv, no shell, local synthetic input
        command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL,
    )
    try:
        frames = []
        for payload in rtsp_bridge.iter_multipart_mjpeg(process, on_frame=frames.append):
            if frames:
                break
        assert len(frames) == 1
        frame = frames[0]
        assert frame.startswith(b"\xff\xd8")
        assert frame.endswith(b"\xff\xd9")
        assert len(frame) > 100  # a genuinely decoded image, not a stub
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
