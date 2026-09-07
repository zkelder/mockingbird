"""Structural tests for scripts/field_acceptance_recorder_readiness.py.

See docs/field-acceptance-tooling-correctness-preflight-closure-v1-report.md
for the governing milestone. Entirely hermetic -- every test drives the
module against a real (tmp_path) filesystem and a fake monotonic
clock/sleep, never a real live recorder process, a real Camera Node, or a
real timeout sleep.

Loaded via `runpy.run_path`, matching every other `scripts/` test file's
own established convention.
"""

from __future__ import annotations

from pathlib import Path
import runpy
from typing import Callable

ROOT = Path(__file__).resolve().parents[1]
_MODULE = runpy.run_path(str(ROOT / "scripts" / "field_acceptance_recorder_readiness.py"))

check_recorder_readiness = _MODULE["check_recorder_readiness"]


class _FakeClock:
    """A controllable monotonic clock -- `sleep` advances it directly and
    fires at most one scripted side effect (e.g. 'the recorder writes its
    next frame now'), FIFO, one per call -- so a test never needs a real
    sleep or a background thread to simulate concurrent recorder
    activity."""

    def __init__(self) -> None:
        self.now = 0.0
        self._on_tick: list[Callable[[], None]] = []

    def monotonic(self) -> float:
        return self.now

    def schedule(self, callback: Callable[[], None]) -> None:
        self._on_tick.append(callback)

    def sleep(self, seconds: float) -> None:
        self.now += seconds
        if self._on_tick:
            self._on_tick.pop(0)()


def _record_frame(session_dir: Path, *, sequence: int) -> None:
    """Writes the same two artifact classes the real
    `BoundedFrameSampleRecorder.maybe_record` writes together, per saved
    frame -- a manifest line and a frame file -- so `check_recorder_
    readiness` sees exactly the shape it would against a real recorder."""

    session_dir.mkdir(parents=True, exist_ok=True)
    (session_dir / f"frame-{sequence:06d}-offset{sequence * 3000:09d}ms.jpg").write_bytes(b"\xff\xd8\xff" + bytes(100))
    with (session_dir / "manifest.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(f'{{"sequence": {sequence}}}\n')


# ---------------------------------------------------------------------------
# Ready: real, advancing evidence.
# ---------------------------------------------------------------------------


def test_ready_when_manifest_and_frames_advance_across_polls(tmp_path: Path) -> None:
    recording_root = tmp_path / "acceptance-recording"
    session_dir = recording_root / "stream-1" / "20260907T124555Z"
    _record_frame(session_dir, sequence=0)  # already one frame present when polling begins

    clock = _FakeClock()
    clock.schedule(lambda: _record_frame(session_dir, sequence=1))  # a real write lands on the first sleep

    result = check_recorder_readiness(
        recording_root=recording_root, stream_id="stream-1",
        timeout_seconds=30.0, poll_interval_seconds=5.0,
        monotonic_fn=clock.monotonic, sleep_fn=clock.sleep,
    )

    assert result.ready is True
    assert result.session_dir == str(session_dir)
    assert result.last_snapshot.manifest_line_count == 2
    assert result.poll_count == 2
    assert "Confirmed advancing" in result.reason


def test_session_dir_writable_reflects_a_real_writable_directory(tmp_path: Path) -> None:
    recording_root = tmp_path / "acceptance-recording"
    session_dir = recording_root / "stream-1" / "20260907T124555Z"
    _record_frame(session_dir, sequence=0)
    clock = _FakeClock()
    clock.schedule(lambda: _record_frame(session_dir, sequence=1))

    result = check_recorder_readiness(
        recording_root=recording_root, stream_id="stream-1",
        timeout_seconds=20.0, poll_interval_seconds=5.0,
        monotonic_fn=clock.monotonic, sleep_fn=clock.sleep,
    )

    assert result.session_dir_writable is True


def test_picks_up_a_fresh_session_directory_that_appears_after_a_stale_one(tmp_path: Path) -> None:
    """Governing brief §4 'corresponds to the intended camera/session': a
    leftover, static directory from a *prior* session for the same Stream
    must never be mistaken for live evidence -- this proves the checker
    re-resolves the newest correctly-named directory on every poll and
    correctly tracks advancement against the fresh one once it appears,
    never the stale one it started with."""

    recording_root = tmp_path / "acceptance-recording"
    stale_dir = recording_root / "stream-1" / "20260907T090000Z"  # an old, static leftover
    _record_frame(stale_dir, sequence=0)
    fresh_dir = recording_root / "stream-1" / "20260907T124555Z"

    clock = _FakeClock()
    clock.schedule(lambda: _record_frame(fresh_dir, sequence=0))  # the real session starts
    clock.schedule(lambda: _record_frame(fresh_dir, sequence=1))  # ... and keeps writing

    result = check_recorder_readiness(
        recording_root=recording_root, stream_id="stream-1",
        timeout_seconds=30.0, poll_interval_seconds=5.0,
        monotonic_fn=clock.monotonic, sleep_fn=clock.sleep,
    )

    assert result.ready is True
    assert result.session_dir == str(fresh_dir)  # never the stale directory


# ---------------------------------------------------------------------------
# Not ready: every distinct failure reason governing brief §4 names.
# ---------------------------------------------------------------------------


def test_not_ready_when_session_directory_never_appears(tmp_path: Path) -> None:
    recording_root = tmp_path / "acceptance-recording"  # never created at all
    clock = _FakeClock()

    result = check_recorder_readiness(
        recording_root=recording_root, stream_id="stream-1",
        timeout_seconds=20.0, poll_interval_seconds=5.0,
        monotonic_fn=clock.monotonic, sleep_fn=clock.sleep,
    )

    assert result.ready is False
    assert result.reason.startswith("recorder_session_directory_not_found")
    assert result.session_dir is None


def test_not_ready_when_recording_exists_only_for_a_different_stream(tmp_path: Path) -> None:
    """Proves stream/session correspondence the other way: real, advancing
    evidence for a *different* Stream must never satisfy this Stream's own
    readiness check."""

    recording_root = tmp_path / "acceptance-recording"
    other_session_dir = recording_root / "stream-OTHER" / "20260907T124555Z"
    _record_frame(other_session_dir, sequence=0)
    clock = _FakeClock()
    clock.schedule(lambda: _record_frame(other_session_dir, sequence=1))

    result = check_recorder_readiness(
        recording_root=recording_root, stream_id="stream-1",
        timeout_seconds=20.0, poll_interval_seconds=5.0,
        monotonic_fn=clock.monotonic, sleep_fn=clock.sleep,
    )

    assert result.ready is False
    assert result.reason.startswith("recorder_session_directory_not_found")


def test_not_ready_when_no_frames_are_ever_written(tmp_path: Path) -> None:
    recording_root = tmp_path / "acceptance-recording"
    session_dir = recording_root / "stream-1" / "20260907T124555Z"
    session_dir.mkdir(parents=True)  # the directory exists -- but stays empty
    clock = _FakeClock()

    result = check_recorder_readiness(
        recording_root=recording_root, stream_id="stream-1",
        timeout_seconds=20.0, poll_interval_seconds=5.0,
        monotonic_fn=clock.monotonic, sleep_fn=clock.sleep,
    )

    assert result.ready is False
    assert result.reason.startswith("no_frames_written")


def test_not_ready_when_frames_stop_advancing(tmp_path: Path) -> None:
    recording_root = tmp_path / "acceptance-recording"
    session_dir = recording_root / "stream-1" / "20260907T124555Z"
    _record_frame(session_dir, sequence=0)
    clock = _FakeClock()  # nothing scheduled -- the one frame just sits there, unchanged

    result = check_recorder_readiness(
        recording_root=recording_root, stream_id="stream-1",
        timeout_seconds=20.0, poll_interval_seconds=5.0,
        monotonic_fn=clock.monotonic, sleep_fn=clock.sleep,
    )

    assert result.ready is False
    assert result.reason.startswith("frames_not_advancing")
    assert result.last_snapshot.manifest_line_count == 1


def test_process_alive_true_still_requires_real_advancing_evidence(tmp_path: Path) -> None:
    """Governing brief §4: 'A process existing is not sufficient proof.'
    A confirmed-alive process with a real but non-advancing recording
    directory must still fail readiness."""

    recording_root = tmp_path / "acceptance-recording"
    session_dir = recording_root / "stream-1" / "20260907T124555Z"
    _record_frame(session_dir, sequence=0)
    clock = _FakeClock()

    result = check_recorder_readiness(
        recording_root=recording_root, stream_id="stream-1",
        timeout_seconds=20.0, poll_interval_seconds=5.0, process_alive_fn=lambda: True,
        monotonic_fn=clock.monotonic, sleep_fn=clock.sleep,
    )

    assert result.ready is False
    assert result.process_alive is True
    assert result.reason.startswith("frames_not_advancing")


def test_fails_immediately_when_process_alive_fn_reports_dead(tmp_path: Path) -> None:
    """No point waiting out a full bounded timeout for frame evidence from
    a process that is already confirmed not running -- fails on the very
    first check, before any polling."""

    recording_root = tmp_path / "acceptance-recording"
    clock = _FakeClock()

    result = check_recorder_readiness(
        recording_root=recording_root, stream_id="stream-1", timeout_seconds=20.0,
        process_alive_fn=lambda: False, monotonic_fn=clock.monotonic, sleep_fn=clock.sleep,
    )

    assert result.ready is False
    assert result.reason.startswith("recorder_process_not_alive")
    assert result.poll_count == 0
    assert result.process_alive is False


def test_process_alive_fn_omitted_reports_unknown_never_guessed(tmp_path: Path) -> None:
    recording_root = tmp_path / "acceptance-recording"
    session_dir = recording_root / "stream-1" / "20260907T124555Z"
    _record_frame(session_dir, sequence=0)
    clock = _FakeClock()
    clock.schedule(lambda: _record_frame(session_dir, sequence=1))

    result = check_recorder_readiness(
        recording_root=recording_root, stream_id="stream-1",
        timeout_seconds=20.0, poll_interval_seconds=5.0,
        monotonic_fn=clock.monotonic, sleep_fn=clock.sleep,
    )

    assert result.process_alive is None  # never guessed either True or False


def test_stops_within_the_bounded_timeout_never_polls_forever(tmp_path: Path) -> None:
    recording_root = tmp_path / "acceptance-recording"  # never appears
    clock = _FakeClock()

    result = check_recorder_readiness(
        recording_root=recording_root, stream_id="stream-1",
        timeout_seconds=12.0, poll_interval_seconds=5.0,
        monotonic_fn=clock.monotonic, sleep_fn=clock.sleep,
    )

    assert result.ready is False
    assert result.poll_count == 4
    assert result.elapsed_seconds == 15.0  # bounded overshoot: < one extra poll_interval_seconds beyond 12.0


# ---------------------------------------------------------------------------
# --dev-root process-liveness wiring (governing brief §4: 'recorder process
# is alive'). Reuses field_acceptance_instance_lifecycle.py's own already
# -established _probe_running/_resolve_dev_root -- never a second,
# independently-drifting liveness check. Exercised only against a dev-root
# with no recorded launch pointer, which _probe_running itself documents as
# an honest 'not running' short-circuit with zero real Windows/PowerShell
# I/O -- safe to run hermetically in this sandbox.
# ---------------------------------------------------------------------------


def test_dev_root_process_alive_wiring_reflects_no_running_process(tmp_path: Path) -> None:
    dev_root = tmp_path / "MockingBirdFieldAcceptanceX"
    dev_root.mkdir()

    process_alive_fn = _MODULE["_process_alive_fn_for_dev_root"](dev_root)

    assert process_alive_fn() is False


def test_check_recorder_readiness_fails_fast_when_dev_root_process_wiring_reports_dead(tmp_path: Path) -> None:
    dev_root = tmp_path / "MockingBirdFieldAcceptanceX"
    dev_root.mkdir()
    recording_root = tmp_path / "acceptance-recording"  # would never even be consulted
    clock = _FakeClock()

    process_alive_fn = _MODULE["_process_alive_fn_for_dev_root"](dev_root)
    result = check_recorder_readiness(
        recording_root=recording_root, stream_id="stream-1", timeout_seconds=20.0,
        process_alive_fn=process_alive_fn, monotonic_fn=clock.monotonic, sleep_fn=clock.sleep,
    )

    assert result.ready is False
    assert result.reason.startswith("recorder_process_not_alive")
    assert result.poll_count == 0
