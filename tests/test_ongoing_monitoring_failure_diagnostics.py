"""Ongoing Monitoring Failure Diagnostics for RTSP / Local USB / Windows
DShow v1.

Lane G's remaining, previously-disclosed gap (see `camera-source-experience-
v1-report.md` section 7): once a non-Camera-Node Stream (RTSP, local USB,
Windows DirectShow) is armed and running, `_reader_loop`'s own failure
branch discards ffmpeg's stderr entirely (`capture_stderr` defaults `False`
on the long-running playback process) and every real cause -- auth,
network, codec, decode -- collapses to the single generic string "Camera
process ended before the session was stopped.". Setup-time validation
(`rtsp_bridge.probe_rtsp_stream`) already distinguishes these causes via
`classify_rtsp_failure_text`; this milestone reuses that exact function/
vocabulary for the ongoing path instead of inventing a second one (see
`docs/ongoing-monitoring-failure-diagnostics-rtsp-local-usb-windows-dshow-
v1-report.md`).

Camera Node is out of scope -- it has its own, separate `safe_failure_code`
mechanism (`camera_node_bridge.CameraNodeSnapshotProcess`), untouched here.

Fake processes below stand in for what `rtsp_bridge.start_rtsp_mjpeg_
process`/`local_camera_bridge.start_local_camera_mjpeg_process`/`windows_
camera_bridge.start_windows_dshow_mjpeg_process` return with
`capture_stderr=True`: a real OS pipe for `.stdout` (mirrors `tests/
test_live_camera_session.py`'s `_FakeCameraProcess`) *and* a real OS pipe
for `.stderr`, so the real `BoundedStderrDrain` thread can be exercised
end-to-end -- never a mocked drain.
"""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import threading
import time

import pytest

from mockingbird.playback import (
    live_camera_session,
    local_camera_bridge,
    rtsp_bridge,
    windows_camera_bridge,
)
from mockingbird.playback.stderr_drain import BoundedStderrDrain
from mockingbird.repository.product_repository import ProductRepository, StreamLivePlaybackConfig

_FRAME = b"\xff\xd8" + b"fixture-frame-bytes" + b"\xff\xd9"


@pytest.fixture
def repository(tmp_path: Path) -> ProductRepository:
    product_repository = ProductRepository(
        db_url=f"sqlite:///{tmp_path / 'mockingbird.sqlite3'}",
        media_root=tmp_path / "media",
    )
    yield product_repository
    product_repository.close()


class _FakeMonitoredProcess:
    """Popen-shaped fixture with *both* a real `.stdout` pipe and a real
    `.stderr` pipe -- unlike `test_live_camera_session._FakeCameraProcess`
    (Camera Node only, no `.stderr` at all), this exercises the real
    `BoundedStderrDrain` thread reading real bytes through a real pipe."""

    def __init__(self) -> None:
        out_read, self._out_write = os.pipe()
        err_read, self._err_write = os.pipe()
        self.stdout = os.fdopen(out_read, "rb", buffering=0)
        self.stderr = os.fdopen(err_read, "rb", buffering=0)
        self._returncode: int | None = None

    def push_frame(self, frame: bytes = _FRAME) -> None:
        os.write(self._out_write, frame)

    def push_stderr(self, text: bytes) -> None:
        os.write(self._err_write, text)

    def poll(self) -> int | None:
        return self._returncode

    def terminate(self) -> None:
        self._close(0)

    def kill(self) -> None:
        self._close(0)

    def wait(self, timeout: float | None = None) -> int:
        return self._returncode or 0

    def _close(self, code: int) -> None:
        if self._returncode is not None:
            return
        self._returncode = code
        for attr in ("_out_write", "_err_write"):
            try:
                os.close(getattr(self, attr))
            except OSError:
                pass


def _rtsp_config(stream_id: str = "stream-rtsp") -> StreamLivePlaybackConfig:
    return StreamLivePlaybackConfig(
        stream_id=stream_id,
        source_id=f"source-{stream_id}",
        provider_key="external_url",
        live_stream_url="rtsp://camera-user:UnmistakableSecret99@203.0.113.5:554/stream",
        live_stream_type="rtsp",
    )


def _local_usb_config(stream_id: str = "stream-local-usb") -> StreamLivePlaybackConfig:
    return StreamLivePlaybackConfig(
        stream_id=stream_id,
        source_id=f"source-{stream_id}",
        provider_key="local_usb",
        live_stream_url=None,
        live_stream_type=local_camera_bridge.LOCAL_USB_STREAM_TYPE,
        local_camera_device="/dev/video0",
    )


def _windows_dshow_config(stream_id: str = "stream-windows-dshow") -> StreamLivePlaybackConfig:
    return StreamLivePlaybackConfig(
        stream_id=stream_id,
        source_id=f"source-{stream_id}",
        provider_key="local_usb",
        live_stream_url=None,
        live_stream_type=windows_camera_bridge.WINDOWS_DSHOW_STREAM_TYPE,
        windows_camera_name="Integrated Webcam",
    )


def _session_for(config, process) -> live_camera_session._LiveCameraSession:
    session = live_camera_session._LiveCameraSession(config=config, process=process, max_runtime_seconds=60)
    return session


def _wait_until(predicate, *, timeout: float = 5.0, interval: float = 0.02) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return predicate()


def _run_reader_loop_after_process_ended(session) -> None:
    """For tests that (like `tests/test_live_camera_session.py`'s existing
    `test_reader_loop_process_ended_is_logged` convention) call
    `_reader_loop()` directly and synchronously rather than driving a real
    async session through `.start()`, with a fake process whose stderr
    write-end is *already* closed (`push_stderr` + `_close()` already ran
    before the session was constructed): starts the real drain and waits
    for its thread to reach EOF on its own -- fast and deterministic, since
    every byte is already sitting in the closed pipe's kernel buffer --
    before running `_reader_loop()`, exactly mirroring what a real async
    drain thread would already have captured by the time production code's
    `_reader_loop` notices the process has ended."""

    if session._stderr_drain is not None:
        session._stderr_drain.start()
        assert _wait_until(lambda: not session._stderr_drain._thread.is_alive())
    session._reader_loop()


# ---------------------------------------------------------------------------
# RTSP ongoing classification -- reuses classify_rtsp_failure_text verbatim.
# ---------------------------------------------------------------------------


def test_rtsp_ongoing_authentication_failure_is_classified_not_generic() -> None:
    process = _FakeMonitoredProcess()
    process.push_stderr(b"[rtsp @ 0x0] method DESCRIBE failed: 401 Unauthorized")
    process._close(0)
    session = _session_for(_rtsp_config(), process)

    _run_reader_loop_after_process_ended(session)

    assert session.status == "failed"
    assert session.last_failure_code == "camera_setup_rtsp_authentication_failed"
    assert session.last_error != "Camera process ended before the session was stopped."
    assert "credential" in session.last_error.lower() or "rejected" in session.last_error.lower()


def test_rtsp_ongoing_network_unreachable_failure_is_classified() -> None:
    process = _FakeMonitoredProcess()
    process.push_stderr(b"[tcp @ 0x0] Connection timed out\n[rtsp @ 0x0] Connection timed out")
    process._close(0)
    session = _session_for(_rtsp_config(), process)

    _run_reader_loop_after_process_ended(session)

    assert session.last_failure_code == "camera_setup_rtsp_unreachable"
    assert "unreachable" in session.last_error.lower() or "reach" in session.last_error.lower()


def test_rtsp_ongoing_codec_failure_is_classified() -> None:
    process = _FakeMonitoredProcess()
    process.push_stderr(b"Unknown codec: this codec is not supported by this build")
    process._close(0)
    session = _session_for(_rtsp_config(), process)

    _run_reader_loop_after_process_ended(session)

    assert session.last_failure_code == "camera_setup_rtsp_unsupported_codec"
    assert "codec" in session.last_error.lower()


def test_rtsp_ongoing_unknown_process_exit_falls_back_to_negotiation_failed() -> None:
    """No stderr evidence at all -- must fall back to the same calibrated
    default `classify_rtsp_failure_text` already uses at setup time, never
    a fabricated specific cause."""

    process = _FakeMonitoredProcess()
    process._close(0)  # no stderr written at all
    session = _session_for(_rtsp_config(), process)

    _run_reader_loop_after_process_ended(session)

    assert session.last_failure_code == "camera_setup_rtsp_negotiation_failed"


# ---------------------------------------------------------------------------
# Setup / ongoing consistency (brief section 19 / 9): the same concrete
# stderr text must map to the same product failure code whether it is seen
# during setup validation (`probe_rtsp_stream`) or during ongoing monitoring
# (`_reader_loop`).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "stderr_text",
    [
        b"[rtsp @ 0x0] method DESCRIBE failed: 401 Unauthorized",
        b"[tcp @ 0x0] Connection refused",
        b"Unknown codec: this codec is not supported by this build",
        b"[rtsp @ 0x0] method DESCRIBE failed: 404 Not Found",
    ],
)
def test_setup_and_ongoing_rtsp_classification_agree(stderr_text: bytes) -> None:
    setup_code = rtsp_bridge.classify_rtsp_failure_text(
        stderr_text.decode(), any_bytes_received=False,
    )

    process = _FakeMonitoredProcess()
    process.push_stderr(stderr_text)
    process._close(0)
    session = _session_for(_rtsp_config(), process)
    _run_reader_loop_after_process_ended(session)

    assert session.last_failure_code == setup_code


# ---------------------------------------------------------------------------
# local_usb -- only evidence-backed categories (real ffmpeg V4L2 error text,
# see the milestone report's "local_usb result" section).
# ---------------------------------------------------------------------------


def test_local_usb_ongoing_device_missing_is_classified() -> None:
    process = _FakeMonitoredProcess()
    process.push_stderr(
        b"[video4linux2,v4l2 @ 0x0] Cannot open video device /dev/video0: "
        b"No such file or directory\n"
        b"Error opening input file /dev/video0.\n"
    )
    process._close(0)
    session = _session_for(_local_usb_config(), process)

    _run_reader_loop_after_process_ended(session)

    assert session.last_failure_code == "camera_monitoring_local_usb_device_missing"
    assert "connected" in session.last_error.lower() or "found" in session.last_error.lower()


def test_local_usb_ongoing_permission_denied_is_classified() -> None:
    process = _FakeMonitoredProcess()
    process.push_stderr(
        b"[video4linux2,v4l2 @ 0x0] Cannot open video device /dev/video0: Permission denied\n"
    )
    process._close(0)
    session = _session_for(_local_usb_config(), process)

    _run_reader_loop_after_process_ended(session)

    assert session.last_failure_code == "camera_monitoring_local_usb_permission_denied"
    assert "permission" in session.last_error.lower()


def test_local_usb_ongoing_unknown_cause_stays_honestly_generic() -> None:
    """No evidence-backed category applies (e.g. device busy/unsupported
    format -- not established by real evidence, see the milestone report) --
    must not invent a specific cause."""

    process = _FakeMonitoredProcess()
    process.push_stderr(b"[video4linux2,v4l2 @ 0x0] ioctl(VIDIOC_QUERYCAP): Inappropriate ioctl for device\n")
    process._close(0)
    session = _session_for(_local_usb_config(), process)

    _run_reader_loop_after_process_ended(session)

    assert session.last_failure_code == "camera_monitoring_local_usb_unavailable"


# ---------------------------------------------------------------------------
# windows_dshow -- only evidence-backed categories (real ffmpeg.exe 8.1.2
# DirectShow error text captured against the real Windows dev host).
# ---------------------------------------------------------------------------


def test_windows_dshow_ongoing_device_unavailable_is_classified() -> None:
    process = _FakeMonitoredProcess()
    process.push_stderr(
        b"[in#0 @ 0x0] Could not enumerate video devices (or none found).\n"
        b"[in#0 @ 0x0] Error opening input: I/O error\n"
    )
    process._close(0)
    session = _session_for(_windows_dshow_config(), process)

    _run_reader_loop_after_process_ended(session)

    assert session.last_failure_code == "camera_monitoring_windows_dshow_device_unavailable"
    assert "connected" in session.last_error.lower() or "found" in session.last_error.lower()


def test_windows_dshow_ongoing_unknown_cause_stays_honestly_generic() -> None:
    process = _FakeMonitoredProcess()
    process._close(0)  # no stderr at all
    session = _session_for(_windows_dshow_config(), process)

    _run_reader_loop_after_process_ended(session)

    assert session.last_failure_code == "camera_monitoring_windows_dshow_unavailable"


# ---------------------------------------------------------------------------
# Camera Node must be completely unaffected (out of scope; separate
# mechanism).
# ---------------------------------------------------------------------------


def test_camera_node_ongoing_failure_path_is_unaffected() -> None:
    from tests.test_live_camera_session import _FakeCameraProcess, _config

    process = _FakeCameraProcess()
    process._close(0)
    session = _session_for(_config(), process)

    _run_reader_loop_after_process_ended(session)

    assert session.last_failure_code is None
    assert session.last_error == "Camera process ended before the session was stopped."


# ---------------------------------------------------------------------------
# Credential safety (brief section 8): raw stderr may echo the full RTSP
# URL/credentials; must never reach last_error/last_failure_code/logs raw.
# ---------------------------------------------------------------------------


def test_rtsp_ongoing_failure_never_leaks_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    logged: list[dict] = []
    monkeypatch.setattr(
        live_camera_session,
        "log_error_event",
        lambda component, event, **fields: logged.append({"component": component, "event": event, **fields}),
    )
    secret = "UnmistakableSecret99"
    process = _FakeMonitoredProcess()
    process.push_stderr(
        f"[rtsp @ 0x0] rtsp://camera-user:{secret}@203.0.113.5:554/stream: "
        f"method DESCRIBE failed: 401 Unauthorized".encode()
    )
    process._close(0)
    session = _session_for(_rtsp_config(), process)

    _run_reader_loop_after_process_ended(session)

    assert secret not in (session.last_error or "")
    assert secret not in (session.last_failure_code or "")
    for entry in logged:
        assert secret not in repr(entry)


# ---------------------------------------------------------------------------
# stderr drain: bounded memory, no deadlock, thread-safe, clean shutdown.
# ---------------------------------------------------------------------------


def test_stderr_drain_retains_only_a_bounded_tail() -> None:
    read_fd, write_fd = os.pipe()
    try:
        drain = BoundedStderrDrain(os.fdopen(read_fd, "rb", buffering=0), max_retained_bytes=256)
        drain.start()
        chunk = b"x" * 4096
        for _ in range(50):  # 200KB total, far exceeding the 256-byte cap
            os.write(write_fd, chunk)
        assert _wait_until(lambda: drain.bytes_seen >= 50 * len(chunk))
        text = drain.latest_text()
        assert text is not None
        assert len(text) <= 256
    finally:
        os.close(write_fd)
        drain.stop()


def test_stderr_drain_high_volume_producer_does_not_deadlock() -> None:
    """Deterministic stress proof: a real subprocess writes several MB to
    stderr with nothing draining stdout -- if stderr were still DEVNULL-less
    and undrained (the pre-fix architecture), a large enough write would
    block the child on a full OS pipe buffer forever. Bounded wall-clock:
    must complete well under the test's own timeout."""

    script = (
        "import sys\n"
        "for _ in range(20000):\n"
        "    sys.stderr.write('x' * 200 + chr(10))\n"
        "sys.stderr.flush()\n"
    )
    process = subprocess.Popen(
        [sys.executable, "-c", script],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        stdin=subprocess.DEVNULL,
    )
    drain = BoundedStderrDrain(process.stderr, max_retained_bytes=4096)
    drain.start()
    try:
        exit_code = process.wait(timeout=15)
    finally:
        drain.stop()
    assert exit_code == 0
    assert drain.bytes_seen >= 20000 * 201  # ~4MB actually drained, not stalled
    text = drain.latest_text()
    assert text is not None
    assert len(text) <= 4096


def test_stderr_drain_stop_is_idempotent_and_bounded() -> None:
    read_fd, write_fd = os.pipe()
    try:
        stream = os.fdopen(read_fd, "rb", buffering=0)
        drain = BoundedStderrDrain(stream)
        drain.start()
        os.write(write_fd, b"one line\n")
        os.close(write_fd)  # EOF -- mirrors the process having already been stopped
        started = time.monotonic()
        drain.stop(timeout=2.0)
        drain.stop(timeout=2.0)  # must not raise or hang on a second call
        assert time.monotonic() - started < 3.0
    finally:
        try:
            os.close(write_fd)
        except OSError:
            pass


def test_session_stop_joins_the_drain_thread_cleanly() -> None:
    process = _FakeMonitoredProcess()
    session = _session_for(_rtsp_config(), process)
    session.start()
    assert _wait_until(lambda: session._stderr_drain is not None)
    drain_thread_name = "mockingbird-stderr-drain"

    session.stop("user_stopped")

    def _no_drain_threads_left() -> bool:
        return not any(
            t.name == drain_thread_name and t.is_alive() for t in threading.enumerate()
        )

    assert _wait_until(_no_drain_threads_left, timeout=3.0)


def test_repeated_stop_after_process_ended_is_safe() -> None:
    process = _FakeMonitoredProcess()
    process.push_stderr(b"[rtsp @ 0x0] Connection refused")
    process._close(0)  # the process has already ended before Start is even called
    session = _session_for(_rtsp_config(), process)
    session.start()
    assert _wait_until(lambda: session.status == "failed", timeout=3.0)

    session.stop("user_stopped")
    session.stop("user_stopped")  # repeated stop must be safe


# ---------------------------------------------------------------------------
# Retry / recovery: failure classified -> retry -> healthy recovery clears
# stale code/message (brief section 14).
# ---------------------------------------------------------------------------


def test_recovery_after_ongoing_failure_clears_stale_state(repository: ProductRepository) -> None:
    from datetime import UTC, datetime, timedelta

    stream_id = repository.list_streams()[0].id
    repository.set_stream_monitoring_enabled(
        stream_id, enabled=True, idempotency_key=f"enable-{stream_id}",
    )
    candidate = repository.list_enabled_monitoring_candidates(limit=1)[0]
    now = datetime.now(UTC)

    repository.mark_monitoring_backoff_with_failure_code(
        candidate,
        app_instance_id="ongoing-diagnostics-test",
        failure_count=1,
        retry_at=now + timedelta(seconds=5),
        failure_code="camera_setup_rtsp_authentication_failed",
        now=now,
    )
    failing_health = repository.get_stream_camera_health(stream_id)
    assert failing_health is not None
    assert failing_health.health.failure_reason is not None
    assert "credential" in failing_health.health.failure_reason.lower()

    repository.mark_monitoring_running(
        candidate,
        app_instance_id="ongoing-diagnostics-test",
        healthy_at=now + timedelta(seconds=10),
        now=now + timedelta(seconds=10),
    )
    recovered_health = repository.get_stream_camera_health(stream_id)
    assert recovered_health is not None
    assert recovered_health.health.failure_reason is None
    assert recovered_health.health.state.value == "healthy"


# ---------------------------------------------------------------------------
# Multi-Stream isolation (brief section 16): independent diagnostics, no
# shared/global state.
# ---------------------------------------------------------------------------


def test_multiple_streams_retain_independent_ongoing_diagnostics() -> None:
    process_a = _FakeMonitoredProcess()
    process_a.push_stderr(b"[rtsp @ 0x0] method DESCRIBE failed: 401 Unauthorized")
    process_a._close(0)
    session_a = _session_for(_rtsp_config("stream-a"), process_a)
    _run_reader_loop_after_process_ended(session_a)

    process_b = _FakeMonitoredProcess()
    session_b = _session_for(_rtsp_config("stream-b"), process_b)
    session_b.start()
    session_b.stop("user_stopped")

    process_c = _FakeMonitoredProcess()
    process_c.push_stderr(b"[tcp @ 0x0] Connection refused")
    process_c._close(0)
    session_c = _session_for(_rtsp_config("stream-c"), process_c)
    _run_reader_loop_after_process_ended(session_c)

    assert session_a.last_failure_code == "camera_setup_rtsp_authentication_failed"
    assert session_b.last_failure_code is None
    assert session_b.status == "stopped"
    assert session_c.last_failure_code == "camera_setup_rtsp_unreachable"


# ---------------------------------------------------------------------------
# Plumbing: codes survive through ManagedCameraStatus / _managed_camera_status.
# ---------------------------------------------------------------------------


def test_managed_camera_status_forwards_the_specific_ongoing_failure_code() -> None:
    from mockingbird.api.main import _managed_camera_status

    process = _FakeMonitoredProcess()
    process.push_stderr(b"Unknown codec: this codec is not supported by this build")
    process._close(0)
    session = _session_for(_rtsp_config(), process)
    _run_reader_loop_after_process_ended(session)

    status = _managed_camera_status(session.snapshot())

    assert status.failure_code == "camera_setup_rtsp_unsupported_codec"


def test_stream_runtime_status_response_forwards_the_failure_code(repository: ProductRepository) -> None:
    """`StreamRuntimeStatusResponse.failure_code` (`get_stream_runtime_
    status`) is a direct, unconditional passthrough of `checkpoint.
    failure_code` -- proves the new codes survive that hop too, not only
    the `CameraHealthSummary`/`ManagedCameraStatus` hops already covered
    above."""

    from datetime import UTC, datetime, timedelta

    stream_id = repository.list_streams()[0].id
    repository.set_stream_monitoring_enabled(
        stream_id, enabled=True, idempotency_key=f"enable-runtime-status-{stream_id}",
    )
    candidate = repository.list_enabled_monitoring_candidates(limit=1)[0]
    now = datetime.now(UTC)

    repository.mark_monitoring_backoff_with_failure_code(
        candidate,
        app_instance_id="ongoing-diagnostics-test",
        failure_count=1,
        retry_at=now + timedelta(seconds=5),
        failure_code="camera_monitoring_local_usb_device_missing",
        now=now,
    )

    status = repository.get_stream_runtime_status(stream_id)

    assert status.failure_code == "camera_monitoring_local_usb_device_missing"


# ---------------------------------------------------------------------------
# Long-run safety: repeated start/stop cycles must never accumulate drain
# threads (brief section 15/17 "no thread leak").
# ---------------------------------------------------------------------------


def test_repeated_start_stop_cycles_leave_no_drain_threads_behind() -> None:
    def _drain_thread_count() -> int:
        return sum(1 for t in threading.enumerate() if t.name == "mockingbird-stderr-drain")

    baseline = _drain_thread_count()
    for i in range(10):
        process = _FakeMonitoredProcess()
        session = _session_for(_rtsp_config(f"stream-cycle-{i}"), process)
        session.start()
        process.push_frame()
        assert _wait_until(lambda s=session: s.frame_count >= 1)
        session.stop("user_stopped")

    assert _wait_until(lambda: _drain_thread_count() == baseline, timeout=5.0)


# ---------------------------------------------------------------------------
# Performance (brief section 22): the stderr drain must not block or slow
# the main frame (`stdout`) path -- frames keep flowing at full speed while
# stderr is simultaneously flooded on a real, independent thread.
# ---------------------------------------------------------------------------


def test_high_volume_stderr_does_not_block_concurrent_frame_delivery() -> None:
    process = _FakeMonitoredProcess()
    session = _session_for(_rtsp_config(), process)
    session.start()

    def _flood_stderr() -> None:
        chunk = b"harmless noisy debug line\n" * 100
        for _ in range(200):  # ~2.7MB total
            process.push_stderr(chunk)

    flooder = threading.Thread(target=_flood_stderr, daemon=True)
    started = time.monotonic()
    flooder.start()
    for _ in range(20):
        process.push_frame()
    flooder.join(timeout=10.0)
    assert not flooder.is_alive()

    assert _wait_until(lambda: session.frame_count >= 20, timeout=5.0)
    elapsed = time.monotonic() - started
    assert elapsed < 5.0  # frames were never stalled behind the stderr flood

    session.stop("user_stopped")
