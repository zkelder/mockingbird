"""Focused lifecycle/concurrency tests for the Camera Node capture-ownership
handoff between Observation Engine and `LiveCameraSessionManager`'s own
legacy live-view/monitoring session -- the "Fix Observation camera session
collision" fix.

Root cause under test: starting Observation Engine used to open its own,
completely uncoordinated Node connection alongside an already-running
legacy live/monitoring camera session for the same physical camera. Both
funneled into the Node's single per-provider capture lock; the legacy
session's own bridge treats *any* transient Node error as fatal (no retry),
so the first bit of contention permanently flipped it to "failed" even
though nothing the user did was actually wrong.

The fix is an explicit, revocable hand-off at the `LiveCameraSessionManager`
layer: Observation Engine *pauses* an active legacy session before it starts
pulling frames (see `pause_for_observation`), and *resumes* it (a fresh
session, exactly like a normal Start) once Observation stops for any reason
(see `resume_after_observation`). This file exercises that hand-off in
isolation, with a fake camera process standing in for the real Camera Node
bridge/ffmpeg subprocess -- no real Camera Node, subprocess, or network
socket. See `tests/test_engine_runtime.py` for the Observation-Engine side
of this same contract (that it actually calls these two methods at the
right points, and that a coordinator failure never breaks Start/Stop).
"""

from __future__ import annotations

import os
import time

import pytest

from mockingbird.playback import live_camera_session
from mockingbird.repository.product_repository import StreamLivePlaybackConfig

STREAM_ID = "stream-camera-node-pause-fixture"
_FRAME = b"\xff\xd8" + b"fixture-frame-bytes" + b"\xff\xd9"


class _FakeCameraProcess:
    """Minimal Popen-shaped fixture standing in for the real
    `CameraNodeSnapshotProcess`/ffmpeg bridge `_start_process` normally
    returns -- exercises exactly the duck-typed contract
    `_LiveCameraSession`/`_stop_process` actually use (`.stdout`, `.poll()`,
    `.terminate()`, `.kill()`, `.wait()`), never a real Camera Node."""

    def __init__(self) -> None:
        read_fd, self._write_fd = os.pipe()
        self.stdout = os.fdopen(read_fd, "rb", buffering=0)
        self._returncode: int | None = None
        self.terminate_calls = 0

    def push_frame(self, frame: bytes = _FRAME) -> None:
        os.write(self._write_fd, frame)

    def poll(self) -> int | None:
        return self._returncode

    def terminate(self) -> None:
        self.terminate_calls += 1
        self._close(0)

    def kill(self) -> None:
        self._close(0)

    def wait(self, timeout: float | None = None) -> int:
        return self._returncode or 0

    def _close(self, code: int) -> None:
        if self._returncode is not None:
            return
        self._returncode = code
        try:
            os.close(self._write_fd)
        except OSError:
            pass


def _config(stream_id: str = STREAM_ID) -> StreamLivePlaybackConfig:
    return StreamLivePlaybackConfig(
        stream_id=stream_id,
        source_id=f"source-{stream_id}",
        provider_key="camera_node",
        live_stream_url=None,
        live_stream_type="camera_node",
        camera_node_base_address="http://192.168.1.50:8787",
        camera_node_credential="fixture-credential",
        camera_node_camera_id="cam-1",
        camera_node_id="node-1",
        camera_node_monitoring_profile_id="monitoring-profile",
        camera_node_evidence_profile_id="evidence-profile",
    )


@pytest.fixture
def fake_processes(monkeypatch: pytest.MonkeyPatch) -> list[_FakeCameraProcess]:
    """Every `_start_process` call during a test returns a new fake process,
    recorded here in call order -- a test reaches in to push frames through
    whichever generation is current, and asserts on how many were ever
    created (proving a paused session was reused/refused rather than a
    second one silently racing in)."""

    created: list[_FakeCameraProcess] = []

    def _fake_start_process(config: object) -> _FakeCameraProcess:
        process = _FakeCameraProcess()
        created.append(process)
        return process

    monkeypatch.setattr(live_camera_session, "_start_process", _fake_start_process)
    return created


def _wait_until(predicate, *, timeout: float = 5.0, interval: float = 0.02) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return predicate()


# --- pause_for_observation ---------------------------------------------


def test_pause_transitions_running_session_to_paused_not_failed(fake_processes) -> None:
    manager = live_camera_session.LiveCameraSessionManager()
    manager.start(_config())
    fake_processes[0].push_frame()
    assert _wait_until(lambda: manager.status(STREAM_ID).frame_count >= 1)

    paused = manager.pause_for_observation(STREAM_ID)

    assert paused is not None
    assert paused.status == "paused"
    assert paused.stop_reason == "observation_started"
    assert paused.last_error is None
    assert paused.frame_count >= 1  # history preserved, not reset by the pause
    event_types = {event["event_type"] for event in paused.diagnostic_events}
    assert "camera_paused" in event_types
    assert "camera_failed" not in event_types
    # The underlying process is genuinely released, not merely marked idle.
    assert fake_processes[0].terminate_calls == 1


def test_pause_is_a_safe_noop_with_no_session_running(fake_processes) -> None:
    manager = live_camera_session.LiveCameraSessionManager()
    assert manager.pause_for_observation("stream-never-started") is None
    assert manager.status("stream-never-started") is None
    assert fake_processes == []


def test_pause_is_idempotent(fake_processes) -> None:
    manager = live_camera_session.LiveCameraSessionManager()
    manager.start(_config())

    first = manager.pause_for_observation(STREAM_ID)
    second = manager.pause_for_observation(STREAM_ID)

    assert first is not None and second is not None
    assert first.status == second.status == "paused"
    assert len(fake_processes) == 1  # no second session/process spun up


def test_paused_session_reports_no_frame_rather_than_a_stale_one(fake_processes) -> None:
    manager = live_camera_session.LiveCameraSessionManager()
    manager.start(_config())
    fake_processes[0].push_frame()
    assert _wait_until(lambda: manager.get_latest_frame_for_capture(STREAM_ID) is not None)

    manager.pause_for_observation(STREAM_ID)

    # Honest "not capturing right now", never the last frame served as if live.
    assert manager.get_latest_frame_for_capture(STREAM_ID) is None


# --- start() must not fight a paused session for the camera -------------


def test_start_refuses_to_compete_with_a_paused_session(fake_processes) -> None:
    manager = live_camera_session.LiveCameraSessionManager()
    config = _config()
    manager.start(config)
    manager.pause_for_observation(STREAM_ID)

    started_again = manager.start(config)

    assert started_again.status == "paused"
    assert started_again.stop_reason == "observation_started"
    assert len(fake_processes) == 1  # a manual Start never opens a second capture


# --- resume_after_observation --------------------------------------------


def test_resume_restarts_a_fresh_session(fake_processes) -> None:
    manager = live_camera_session.LiveCameraSessionManager()
    config = _config()
    manager.start(config)
    fake_processes[0].push_frame()
    assert _wait_until(lambda: manager.status(STREAM_ID).frame_count >= 1)
    manager.pause_for_observation(STREAM_ID)

    resumed = manager.resume_after_observation(config)

    assert resumed is not None
    assert resumed.status in {"starting", "running"}
    assert len(fake_processes) == 2  # a genuinely new capture, not the paused one reused
    assert resumed.frame_count == 0  # a fresh session, not the paused one's stale history
    fake_processes[1].push_frame()
    assert _wait_until(lambda: manager.status(STREAM_ID).frame_count >= 1)


def test_resume_is_a_noop_when_never_paused(fake_processes) -> None:
    manager = live_camera_session.LiveCameraSessionManager()
    config = _config()
    manager.start(config)

    assert manager.resume_after_observation(config) is None
    assert len(fake_processes) == 1
    assert manager.status(STREAM_ID).status == "running"


def test_resume_is_a_noop_with_no_session_at_all(fake_processes) -> None:
    manager = live_camera_session.LiveCameraSessionManager()
    assert manager.resume_after_observation(_config()) is None
    assert fake_processes == []


def test_explicit_stop_while_paused_wins_over_a_later_resume(fake_processes) -> None:
    """Requirement: an explicit Stop always supersedes a pending pause --
    Observation Engine finishing later must never resurrect a session the
    user deliberately turned off in the meantime."""

    manager = live_camera_session.LiveCameraSessionManager()
    config = _config()
    manager.start(config)
    manager.pause_for_observation(STREAM_ID)

    stopped = manager.stop(STREAM_ID, reason="user_stopped")
    assert stopped is not None
    assert stopped.status == "stopped"
    assert stopped.stop_reason == "user_stopped"

    assert manager.resume_after_observation(config) is None
    assert manager.status(STREAM_ID).status == "stopped"
    assert len(fake_processes) == 1  # resume never restarted it


# --- idempotent repeated Start/Stop-observing cycles ---------------------


def test_repeated_pause_resume_cycles_remain_stable(fake_processes) -> None:
    """Mirrors repeated Start observing / Stop observing against one
    already-healthy live session: each cycle must land back on a genuinely
    running session, never Failed, never a duplicate/competing capture."""

    manager = live_camera_session.LiveCameraSessionManager()
    config = _config()
    manager.start(config)

    for _ in range(3):
        paused = manager.pause_for_observation(STREAM_ID)
        assert paused is not None
        assert paused.status == "paused"

        resumed = manager.resume_after_observation(config)
        assert resumed is not None
        assert resumed.status in {"starting", "running"}

    assert len(fake_processes) == 4  # 1 initial start + 3 resumes
    assert manager.status(STREAM_ID).status in {"starting", "running"}
    assert manager.status(STREAM_ID).last_error is None


# --- last_error stays user-safe on an unexpected monitor failure ---------
# (First-Hour Onboarding + Whole-Product Observability Closure v1, "B8 user-
# safe actions": a confirmed, live, traced defect -- a raw `str(error)` used
# to reach StreamsPage.tsx's "Last error:" text verbatim, no curation.)


def test_monitor_loop_failure_sets_a_safe_message_not_the_raw_exception_text() -> None:
    process = _FakeCameraProcess()
    session = live_camera_session._LiveCameraSession(config=_config(), process=process, max_runtime_seconds=60)

    def _raising_evaluate() -> dict:
        raise RuntimeError("a very specific internal detail that must never reach the user")

    session._monitor_loop(_raising_evaluate, interval_seconds=0.0)

    assert session.last_error == (
        "Camera monitoring stopped unexpectedly. Check this camera's health details."
    )
    assert "very specific internal detail" not in session.last_error
    assert "RuntimeError" not in session.last_error
    assert session.monitor_running is False


def test_reader_loop_process_ended_is_logged(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pre-Freeze Operability Gap Closure v1 ("A2 frame-decode failures --
    RTSP/live playback/acquisition"): disclosed as absent in
    docs/observability-error-taxonomy-contract.md. The sibling `except
    Exception` path in `_reader_loop` already logs via `log_error_event`
    (see the test above's own module); this proves the "process ended on
    its own" branch -- reached when ffmpeg simply exits with no Python
    exception at all, before any Stop was requested -- now does too."""

    logged: list[dict] = []
    monkeypatch.setattr(
        live_camera_session,
        "log_error_event",
        lambda component, event, **fields: logged.append({"component": component, "event": event, **fields}),
    )

    process = _FakeCameraProcess()
    process._close(0)  # ffmpeg exits on its own -- no Stop, no exception.
    session = live_camera_session._LiveCameraSession(config=_config(), process=process, max_runtime_seconds=60)

    session._reader_loop()

    assert session.status == "failed"
    assert session.stop_reason == "process_ended"
    process_events = [entry for entry in logged if entry["event"] == "live_stream_process_ended"]
    assert len(process_events) == 1
    assert process_events[0]["component"] == "acquisition_provider"
    assert process_events[0]["code"] == "camera_process_ended"
    assert process_events[0]["stream_id"] == STREAM_ID
