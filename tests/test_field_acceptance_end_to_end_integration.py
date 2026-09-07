"""Field Acceptance End-to-End Integration Proof v1: one bounded, simulated
end-to-end scenario proving the complete accepted field-tooling sequence
works together --

    lifecycle init -> recorder setup/readiness -> authenticated Observation
    start -> monotonic session driver -> stop -> finalization settled ->
    final raw-ledger snapshot -> collector shutdown -> reconciliation ->
    latency accounting -> cleanup

-- using the actual, accepted tooling throughout: real subprocess CLI
invocations wherever they are fast (lifecycle init/complete/mark-archived/
cleanup, ledger reconciliation, latency accounting), and the real,
accepted driver/collector functions directly, with a fake monotonic clock
standing in for the 45/75-minute Observation contract (per the governing
report's own explicit "use fake time ... so the test does not consume a
real field window") while every HTTP call underneath is genuinely made,
over a real socket, to the same real, disposable local fake HTTP service
used throughout this milestone (`tests/_field_acceptance_fake_service.py`).

No production framework is introduced solely for this proof -- this file
*is* the small test harness the governing report's own §5 explicitly
permits ("If the existing tools do not provide a single orchestration
entry point, use a small test harness").

Real subprocess + real sockets + real `powershell.exe` calls -- Tier C
(slow software-integration coverage), excluded from the Fast/Core gates.
See docs/test-suite-validation-tiers-contract.md.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import runpy
import subprocess
import sys
import threading
import time

import pytest

pytestmark = pytest.mark.slow

ROOT = Path(__file__).resolve().parents[1]
LIFECYCLE_SCRIPT = ROOT / "scripts" / "field_acceptance_instance_lifecycle.py"
READINESS_SCRIPT = ROOT / "scripts" / "field_acceptance_recorder_readiness.py"
LEDGER_SCRIPT = ROOT / "scripts" / "field_acceptance_ledger_snapshot.py"
ACCOUNTING_SCRIPT = ROOT / "scripts" / "run_gate_a_measurement_accounting.py"
_CLI_TIMEOUT_SECONDS = 45.0

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _field_acceptance_fake_service import (  # noqa: E402
    FakeFieldAcceptanceService,
    FakeObservationState,
    write_fake_dev_root,
)

_CLIENT_MODULE = runpy.run_path(str(ROOT / "scripts" / "field_acceptance_client.py"))
FieldAcceptanceClient = _CLIENT_MODULE["FieldAcceptanceClient"]

_DRIVER_MODULE = runpy.run_path(str(ROOT / "scripts" / "field_acceptance_session_driver.py"))
SessionDriverConfig = _DRIVER_MODULE["SessionDriverConfig"]
run_stop_timing_loop = _DRIVER_MODULE["run_stop_timing_loop"]
stop_and_capture_final_snapshot = _DRIVER_MODULE["stop_and_capture_final_snapshot"]

_LEDGER_MODULE = runpy.run_path(str(ROOT / "scripts" / "field_acceptance_ledger_snapshot.py"))
run_periodic_collection = _LEDGER_MODULE["run_periodic_collection"]

STREAM_ID = "stream-e2e"
TOKEN = "fake-e2e-token"


class _FakeClock:
    """Deterministic monotonic clock -- mirrors `test_field_acceptance_
    session_driver.py`'s own established `_FakeClock` convention exactly,
    so the 45/75-minute Observation contract resolves instantly while
    every HTTP call it triggers underneath is still genuinely made."""

    def __init__(self) -> None:
        self.now = 0.0

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds


def _run_cli(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, *args], cwd=str(ROOT), env={**os.environ},
        capture_output=True, text=True, timeout=_CLI_TIMEOUT_SECONDS,
    )


def _spawn_frame_writer(session_dir: Path, *, frame_count: int, interval_seconds: float) -> threading.Thread:
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


def _session_dir_for(recording_root: Path) -> Path:
    return recording_root / STREAM_ID / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


# ---------------------------------------------------------------------------
# Recorder failure prevents Observation start -- the harness's own gate,
# never bypassed. No production code enforces this ordering by itself
# (the readiness check is a separate, deliberately independent tool); this
# proves the accepted *procedure* -- never call start until readiness is
# confirmed -- holds when actually driven end to end.
# ---------------------------------------------------------------------------


def test_recorder_failure_prevents_observation_start(tmp_path: Path) -> None:
    state = FakeObservationState(
        stream_id=STREAM_ID, bearer_token=TOKEN, instance_id="instance-gate",
        git_commit="a" * 40, build_id="build-gate-0001",
    )
    service = FakeFieldAcceptanceService(state).start()
    try:
        recording_root = tmp_path / "acceptance-recording"  # deliberately never written to

        readiness_result = _run_cli([
            str(READINESS_SCRIPT), "--recording-root", str(recording_root), "--stream-id", STREAM_ID,
            "--timeout-seconds", "2", "--poll-interval-seconds", "1", "--json",
        ])
        readiness_payload = json.loads(readiness_result.stdout)

        assert readiness_result.returncode == 1
        assert readiness_payload["ready"] is False

        # The harness's own gate: Observation start is never even attempted.
        if readiness_payload["ready"]:
            FieldAcceptanceClient(base_url=service.base_url, token=TOKEN).start_observation(STREAM_ID)

        assert state.phase == "not_started", "a failed recorder-readiness check must prevent Observation start"
    finally:
        service.stop()


# ---------------------------------------------------------------------------
# The complete, bounded, simulated sequence -- every real accepted tool,
# chained end to end.
# ---------------------------------------------------------------------------


def test_complete_field_acceptance_sequence_end_to_end(tmp_path: Path) -> None:
    state = FakeObservationState(
        stream_id=STREAM_ID, bearer_token=TOKEN, instance_id="instance-e2e",
        git_commit="b" * 40, build_id="build-e2e-0001", stopping_polls_to_settle=2,
    )
    service = FakeFieldAcceptanceService(state).start()
    dev_root = tmp_path / "MockingBirdE2E"
    recording_root = tmp_path / "acceptance-recording"
    checkpoints_dir = tmp_path / "raw-periodic-snapshots"
    writer: "threading.Thread | None" = None

    try:
        # 1. lifecycle init -- real subprocess. Requires a real deploy_
        # windows_dev.py ledger to already exist (never a real deploy;
        # hand-built, per the governing directive's own "Do not deploy the
        # real product" bound).
        write_fake_dev_root(
            dev_root, sha="e2eSHA", full_commit=state.git_commit, build_id=state.build_id, port=service.port,
        )
        init_result = _run_cli([str(LIFECYCLE_SCRIPT), "init", "--dev-root", str(dev_root), "--json"])
        assert init_result.returncode == 0, f"stdout={init_result.stdout}\nstderr={init_result.stderr}"
        assert json.loads(init_result.stdout)["lifecycle_state"] == "active"

        # 2. recorder setup/readiness -- real subprocess, real advancing
        # frame evidence, and the real --dev-root process-liveness branch
        # (the genuinely running fake service).
        session_dir = _session_dir_for(recording_root)
        writer = _spawn_frame_writer(session_dir, frame_count=20, interval_seconds=0.5)
        readiness_result = _run_cli([
            str(READINESS_SCRIPT), "--recording-root", str(recording_root), "--stream-id", STREAM_ID,
            "--dev-root", str(dev_root), "--timeout-seconds", "20", "--poll-interval-seconds", "2", "--json",
        ])
        readiness_payload = json.loads(readiness_result.stdout)
        assert readiness_result.returncode == 0, f"stdout={readiness_result.stdout}\nstderr={readiness_result.stderr}"
        assert readiness_payload["ready"] is True
        assert readiness_payload["process_alive"] is True
        writer.join(timeout=15.0)
        assert not writer.is_alive()

        # 3. authenticated Observation start -- the real, accepted client.
        client = FieldAcceptanceClient(base_url=service.base_url, token=TOKEN)
        client.start_observation(STREAM_ID)
        assert state.phase == "observing"

        # 4-8 use one shared fake clock: the driver's own stop-timing loop,
        # then a bounded periodic collector, then stop/finalization -- the
        # collector runs *while* still observing (the real, accepted
        # sequence: field_acceptance_ledger_snapshot.py's own docstring),
        # so its own periodic checkpoints see only the two ordinary
        # candidates, never the one only rescued during finalization.
        # The real, accepted 45min/75min/12-sample contract, unmodified --
        # only poll_interval_seconds is overridden, to a value that does
        # not evenly divide either bound, so the assertions below prove
        # "does not wait for a polling tick" concretely within this same
        # integration test rather than relying on a separate unit test's
        # own non-dividing-interval coverage elsewhere.
        config = SessionDriverConfig(poll_interval_seconds=37.0)

        # Early sample quota does not bypass the minimum duration -- checked
        # in isolation first, on its own throwaway clock: the target is
        # already met from t=0, yet the loop must still wait the full
        # 45-minute minimum before stopping.
        early_quota_clock = _FakeClock()
        early_quota_timing = run_stop_timing_loop(
            config=config, sample_count_fn=lambda: 999,
            monotonic_fn=early_quota_clock.monotonic, sleep_fn=early_quota_clock.sleep,
        )
        assert early_quota_timing.stop_reason == "target_reached_after_minimum_duration"
        # The minimum is a floor, not a target of its own -- with a
        # non-dividing poll interval the loop wakes at whatever tick first
        # reaches it (never before, never by more than one poll interval
        # late); only the hard maximum below is clamped to land exactly.
        assert config.minimum_duration_seconds <= early_quota_timing.elapsed_seconds
        assert early_quota_timing.elapsed_seconds < config.minimum_duration_seconds + config.poll_interval_seconds

        # The main sequence's own timing decision: the 12-sample target is
        # never reached, so the hard 75-minute maximum must fire on its own.
        clock = _FakeClock()
        timing = run_stop_timing_loop(
            config=config, sample_count_fn=lambda: 0,
            monotonic_fn=clock.monotonic, sleep_fn=clock.sleep,
        )
        assert timing.stop_reason == "maximum_duration_reached"
        assert timing.elapsed_seconds == 75 * 60.0, "the 75-minute deadline must fire exactly, never late"

        checkpoints = run_periodic_collection(
            client, stream_id=STREAM_ID, output_dir=checkpoints_dir, interval_seconds=600,
            end_offset_ms=86_400_000, max_checkpoints=2, sleep_fn=lambda _seconds: None,
        )
        assert len(checkpoints) == 2  # collector shutdown: a clean, bounded stop, never left running
        for checkpoint in checkpoints:
            payload = json.loads(Path(checkpoint.output_path).read_text())["payloads"]["raw_ledger"]
            assert {item["proposal_id"] for item in payload["proposal_outcomes"]} == {"proposal-1", "proposal-2"}

        finalization = stop_and_capture_final_snapshot(
            client, stream_id=STREAM_ID, end_offset_ms=86_400_000, config=config,
            monotonic_fn=clock.monotonic, sleep_fn=clock.sleep,
        )
        assert finalization.ready is True
        assert finalization.settlement.settled is True
        # Finalization timing is kept entirely separate from the
        # Observation's own 75-minute figure -- never blended into one
        # combined "session duration."
        assert finalization.settlement.elapsed_seconds < config.stop_settlement_timeout_seconds
        assert timing.elapsed_seconds == 75 * 60.0  # unchanged by finalization -- never extended

        rescued_ids = {item["proposal_id"] for item in finalization.final_snapshot["proposal_outcomes"]}
        assert "proposal-3-rescued" in rescued_ids, "a candidate rescued during finalization must reach the final snapshot"

        # 9. reconciliation -- real subprocess.
        final_snapshot_path = tmp_path / "counterfactual-final.json"
        final_snapshot_path.write_text(json.dumps(finalization.final_snapshot))
        merged_path = tmp_path / "counterfactual-merged.json"
        reconcile_result = _run_cli([
            str(LEDGER_SCRIPT), "reconcile", "--snapshot-dir", str(checkpoints_dir),
            "--final-snapshot", str(final_snapshot_path), "--merged-output", str(merged_path), "--json",
        ])
        # stdout is the JSON report followed by one plain "Wrote merged
        # ledger ..." line (see _cmd_reconcile) -- raw_decode reads just
        # the leading JSON value and ignores the trailing text.
        reconciliation, _ = json.JSONDecoder().raw_decode(reconcile_result.stdout)
        assert reconciliation["overall_status"] == "PARTIAL", (
            "a structurally-unavoidable boundary gap must stay honestly PARTIAL, never rounded up to COMPLETE"
        )
        assert reconciliation["artifacts"]["proposal_outcomes"]["status"] == "PARTIAL"
        assert reconcile_result.returncode == 1  # matches "0 only when every artifact reconciles COMPLETE"

        # 10. latency accounting -- real subprocess, fed the merged ledger
        # `reconcile` just produced (never a second, hand-built input).
        accounting_output_dir = tmp_path / "accounting-out"
        accounting_result = _run_cli([
            str(ACCOUNTING_SCRIPT), "--input", str(merged_path), "--output", str(accounting_output_dir),
        ])
        assert accounting_result.returncode == 0, f"stdout={accounting_result.stdout}\nstderr={accounting_result.stderr}"
        latency_report = json.loads((accounting_output_dir / "latency-report.json").read_text())
        summary = latency_report["summary"]
        assert summary["measured_count"] == 2
        assert summary["unavailable_capture_time_count"] == 1, "an honest non-measured classification must survive intact"
        assert summary["fallback_measured_count"] == 1
        sample_by_id = {sample["proposal_id"]: sample for sample in latency_report["samples"]}
        assert sample_by_id["proposal-3-rescued"]["state"] == "measured"
        assert sample_by_id["proposal-3-rescued"]["is_fallback"] is True
        assert sample_by_id["proposal-2"]["state"] == "unavailable_capture_time"

        # 11. cleanup -- real subprocess. The deployed process must be
        # genuinely stopped first (the accepted lifecycle convention --
        # `complete` refuses otherwise), then complete -> mark-archived ->
        # a dry-run cleanup verifies SAFE_TO_RECLAIM, run twice to prove
        # idempotency (a read-only verdict, never a second mutation).
        service.stop()

        complete_result = _run_cli([str(LIFECYCLE_SCRIPT), "complete", "--dev-root", str(dev_root), "--json"])
        assert complete_result.returncode == 0, f"stdout={complete_result.stdout}\nstderr={complete_result.stderr}"
        assert json.loads(complete_result.stdout)["lifecycle_state"] == "completed"

        evidence_archive = tmp_path / "evidence-archive"
        evidence_archive.mkdir()
        (evidence_archive / "report.md").write_text("# Fake field-acceptance report\n")
        (evidence_archive / "counterfactual-merged.json").write_text(json.dumps(finalization.final_snapshot))
        mark_archived_result = _run_cli([
            str(LIFECYCLE_SCRIPT), "mark-archived", "--dev-root", str(dev_root),
            "--evidence-archive", str(evidence_archive), "--json",
        ])
        assert mark_archived_result.returncode == 0, f"stdout={mark_archived_result.stdout}\nstderr={mark_archived_result.stderr}"
        assert json.loads(mark_archived_result.stdout)["lifecycle_state"] == "archived"

        cleanup_result_1 = _run_cli([str(LIFECYCLE_SCRIPT), "cleanup", "--dev-root", str(dev_root), "--json"])
        cleanup_result_2 = _run_cli([str(LIFECYCLE_SCRIPT), "cleanup", "--dev-root", str(dev_root), "--json"])
        assert cleanup_result_1.returncode == 0
        assert cleanup_result_2.returncode == 0
        plan_1, plan_2 = json.loads(cleanup_result_1.stdout), json.loads(cleanup_result_2.stdout)
        assert plan_1["blocked"] is False and plan_2["blocked"] is False
        assert plan_1["will_remove"] == plan_2["will_remove"], "a dry-run plan must be idempotent -- never mutates state"
        assert dev_root.exists(), "a dry-run (no --destroy) cleanup must never actually remove anything"
    finally:
        if writer is not None:
            writer.join(timeout=15.0)
        service.stop()
        # No orphaned process anywhere: the fake service's own background
        # thread is confirmed stopped, and every subprocess above already
        # completed (reaped) via subprocess.run's own bounded timeout.
        assert not service._thread.is_alive()
