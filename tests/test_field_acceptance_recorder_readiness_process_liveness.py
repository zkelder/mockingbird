"""Field Acceptance End-to-End Integration Proof v1: proves the
`scripts/field_acceptance_recorder_readiness.py` CLI's `--dev-root`
process-liveness branch against a genuinely running disposable process --
the one gap *Field Acceptance Tooling Correctness & Preflight Closure v1*
explicitly disclosed and left open ("the 'genuinely running' branch ...
was not separately proven here").

The "genuinely running disposable process" is the same real, disposable
local fake HTTP service used throughout this milestone
(`tests/_field_acceptance_fake_service.py`) -- never the real MockingBird
product, and never a hermetic mock of `WindowsHost` -- driven through the
*real*, unmodified `deploy_windows_dev.real_windows_host()` (real
`powershell.exe`/`Get-NetTCPConnection`/`Invoke-WebRequest`, confirmed live
in this sandbox via WSL2 localhost-forwarding -- see the governing report's
own "Process-liveness proof" for the direct empirical confirmation). No
Camera Node, and no real hardware, is touched anywhere in this file.

Real subprocess + a real socket + real `powershell.exe` calls -- Tier C
(slow software-integration coverage), excluded from the Fast/Core gates.
See docs/test-suite-validation-tiers-contract.md.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time

import pytest

pytestmark = pytest.mark.slow

ROOT = Path(__file__).resolve().parents[1]
READINESS_SCRIPT = ROOT / "scripts" / "field_acceptance_recorder_readiness.py"
_CLI_TIMEOUT_SECONDS = 45.0  # generous: each real powershell.exe round trip costs a real process spawn

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _field_acceptance_fake_service import (  # noqa: E402
    FakeFieldAcceptanceService,
    FakeObservationState,
    write_fake_dev_root,
)

STREAM_ID = "stream-liveness"


def _spawn_frame_writer(session_dir: Path, *, frame_count: int, interval_seconds: float) -> threading.Thread:
    """A real background thread writing real, advancing frame evidence --
    the same two artifact classes `BoundedFrameSampleRecorder`/`tests/
    test_field_acceptance_recorder_readiness.py`'s own `_record_frame`
    write, driven by a real (not faked) clock, since this file proves the
    real subprocess CLI end to end."""

    def _write() -> None:
        for sequence in range(frame_count):
            session_dir.mkdir(parents=True, exist_ok=True)
            (session_dir / f"frame-{sequence:06d}.jpg").write_bytes(b"\xff\xd8\xff" + bytes(50))
            with (session_dir / "manifest.jsonl").open("a", encoding="utf-8") as handle:
                handle.write(json.dumps({"sequence": sequence}) + "\n")
            time.sleep(interval_seconds)

    thread = threading.Thread(target=_write, daemon=True)
    thread.start()
    return thread


def _run_readiness_cli(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(READINESS_SCRIPT), *args],
        cwd=str(ROOT), env={**os.environ}, capture_output=True, text=True, timeout=_CLI_TIMEOUT_SECONDS,
    )


@pytest.fixture
def fake_service():
    state = FakeObservationState(
        stream_id=STREAM_ID, bearer_token="unused-for-this-file", instance_id="instance-liveness",
        git_commit="1" * 40, build_id="build-liveness-0001",
    )
    service = FakeFieldAcceptanceService(state).start()
    try:
        yield service
    finally:
        service.stop()


# ---------------------------------------------------------------------------
# Positive: the dev-root's own ledger matches exactly what the genuinely
# running process reports over the real port -- correct process
# identification, correct intended instance, real advancing frame evidence.
# ---------------------------------------------------------------------------


def test_real_subprocess_confirms_liveness_for_the_matching_dev_root(fake_service, tmp_path: Path) -> None:
    dev_root = tmp_path / "MockingBirdFakeInstanceA"
    write_fake_dev_root(
        dev_root, sha="deadbeef", full_commit=fake_service.state.git_commit,
        build_id=fake_service.state.build_id, port=fake_service.port,
    )
    recording_root = tmp_path / "acceptance-recording"
    session_dir = recording_root / STREAM_ID / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    writer = _spawn_frame_writer(session_dir, frame_count=20, interval_seconds=0.5)
    try:
        result = _run_readiness_cli([
            "--recording-root", str(recording_root), "--stream-id", STREAM_ID,
            "--dev-root", str(dev_root), "--timeout-seconds", "20", "--poll-interval-seconds", "2",
            "--json",
        ])
    finally:
        writer.join(timeout=15.0)
        assert not writer.is_alive(), "the frame-writer thread must not be left running (no orphan)"

    assert result.returncode == 0, f"stdout={result.stdout}\nstderr={result.stderr}"
    payload = json.loads(result.stdout)
    assert payload["process_alive"] is True
    assert payload["ready"] is True


# ---------------------------------------------------------------------------
# Absent/stopped: once the real process is gone, liveness fails closed
# immediately -- no frame polling is even attempted.
# ---------------------------------------------------------------------------


def test_real_subprocess_reports_not_alive_once_the_process_has_stopped(tmp_path: Path) -> None:
    state = FakeObservationState(
        stream_id=STREAM_ID, bearer_token="unused", instance_id="instance-liveness-stopped",
        git_commit="2" * 40, build_id="build-liveness-0002",
    )
    service = FakeFieldAcceptanceService(state).start()
    dev_root = tmp_path / "MockingBirdFakeInstanceStopped"
    write_fake_dev_root(
        dev_root, sha="deadbeef", full_commit=state.git_commit, build_id=state.build_id, port=service.port,
    )
    service.stop()  # the disposable process is genuinely gone before the CLI ever runs

    recording_root = tmp_path / "acceptance-recording"  # never populated -- must never be consulted

    result = _run_readiness_cli([
        "--recording-root", str(recording_root), "--stream-id", STREAM_ID,
        "--dev-root", str(dev_root), "--timeout-seconds", "20", "--poll-interval-seconds", "2",
        "--json",
    ])

    assert result.returncode == 1, f"stdout={result.stdout}\nstderr={result.stderr}"
    payload = json.loads(result.stdout)
    assert payload["process_alive"] is False
    assert payload["ready"] is False
    assert payload["reason"].startswith("recorder_process_not_alive")
    assert payload["poll_count"] == 0, "no frame-evidence polling may occur once liveness already failed"
    assert not recording_root.exists() or not any(recording_root.rglob("*")), (
        "a dead-process check must never itself create/touch recording-root content"
    )


# ---------------------------------------------------------------------------
# Wrong instance / stale pointer: a genuinely running process answers the
# port, but this dev-root's own ledger never recorded that exact
# (git_commit, build_id) pair -- the precise "stale current.json reused by
# an unrelated instance after a restart" shape. Must never false-positive.
# ---------------------------------------------------------------------------


def test_real_subprocess_reports_not_alive_for_a_dev_root_with_a_non_matching_ledger(
    fake_service, tmp_path: Path,
) -> None:
    dev_root = tmp_path / "MockingBirdFakeInstanceStale"
    write_fake_dev_root(
        dev_root, sha="deadbeef", full_commit="f" * 40,  # deliberately does NOT match fake_service.state
        build_id="build-someone-elses-0099", port=fake_service.port,  # ... yet points at the real running port
    )
    recording_root = tmp_path / "acceptance-recording"

    result = _run_readiness_cli([
        "--recording-root", str(recording_root), "--stream-id", STREAM_ID,
        "--dev-root", str(dev_root), "--timeout-seconds", "20", "--poll-interval-seconds", "2",
        "--json",
    ])

    assert result.returncode == 1, f"stdout={result.stdout}\nstderr={result.stderr}"
    payload = json.loads(result.stdout)
    assert payload["process_alive"] is False, "a real, running, but unrelated process must never read as alive"
    assert payload["poll_count"] == 0


# ---------------------------------------------------------------------------
# No recorded launch pointer at all (a dev-root nothing was ever deployed
# into) -- the pre-existing hermetic short-circuit, re-confirmed here
# through the real CLI/subprocess boundary rather than only the direct
# function call tests/test_field_acceptance_recorder_readiness.py covers.
# ---------------------------------------------------------------------------


def test_real_subprocess_reports_not_alive_with_no_current_pointer_at_all(tmp_path: Path) -> None:
    dev_root = tmp_path / "MockingBirdNeverDeployed"
    dev_root.mkdir()
    recording_root = tmp_path / "acceptance-recording"

    result = _run_readiness_cli([
        "--recording-root", str(recording_root), "--stream-id", STREAM_ID,
        "--dev-root", str(dev_root), "--timeout-seconds", "20", "--poll-interval-seconds", "2",
        "--json",
    ])

    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["process_alive"] is False
    assert payload["poll_count"] == 0
