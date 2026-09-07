"""Field Acceptance End-to-End Integration Proof v1: proves the actual
`scripts/field_acceptance_session_driver.py run` entry point -- argument
parsing through to final JSON output and process exit status -- via a real
`subprocess`, against a real, disposable local fake HTTP service
(`tests/_field_acceptance_fake_service.py`), never only the direct
function-level calls `tests/test_field_acceptance_session_driver.py`
already covers hermetically.

See docs/field-acceptance-end-to-end-integration-proof-v1-report.md
"Real CLI / fake HTTP proof" for the governing scope: this closes exactly
the one gap *Field Acceptance Tooling Correctness & Preflight Closure v1*
disclosed and left open ("`field_acceptance_session_driver.py run` was
never dry-run against a live (even disposable-simulated) HTTP server").

Real subprocess + real sockets -- Tier C (slow software-integration
coverage), excluded from the Fast/Core gates. See
docs/test-suite-validation-tiers-contract.md.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import runpy
import subprocess
import sys

import pytest

pytestmark = pytest.mark.slow

ROOT = Path(__file__).resolve().parents[1]
DRIVER_SCRIPT = ROOT / "scripts" / "field_acceptance_session_driver.py"
_CLIENT_MODULE = runpy.run_path(str(ROOT / "scripts" / "field_acceptance_client.py"))
FieldAcceptanceClient = _CLIENT_MODULE["FieldAcceptanceClient"]

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _field_acceptance_fake_service import (  # noqa: E402
    FakeFieldAcceptanceService,
    FakeObservationState,
)

STREAM_ID = "stream-real-cli"
TOKEN = "fake-field-acceptance-token"
_SUBPROCESS_TIMEOUT_SECONDS = 60.0


@pytest.fixture
def fake_service():
    state = FakeObservationState(
        stream_id=STREAM_ID, bearer_token=TOKEN, instance_id="instance-real-cli",
        git_commit="c" * 40, build_id="build-real-cli-0001",
    )
    service = FakeFieldAcceptanceService(state).start()
    try:
        yield service
    finally:
        service.stop()


def _base_env(*, token: "str | None" = TOKEN) -> dict[str, str]:
    env = {**os.environ}
    if token is None:
        env.pop("MOCKINGBIRD_ACCEPTANCE_TOKEN", None)
    else:
        env["MOCKINGBIRD_ACCEPTANCE_TOKEN"] = token
    return env


def _run_driver(args: list[str], *, env: dict[str, str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(DRIVER_SCRIPT), *args],
        cwd=str(ROOT), env=env, capture_output=True, text=True, timeout=_SUBPROCESS_TIMEOUT_SECONDS,
    )


# ---------------------------------------------------------------------------
# Happy path: the target sample count is reached after the (tiny, real)
# minimum duration, finalization settles, and a candidate rescued during
# stop-finalization appears in the final snapshot.
# ---------------------------------------------------------------------------


def test_real_subprocess_run_reaches_target_and_captures_a_rescued_candidate(
    fake_service, tmp_path: Path,
) -> None:
    client = FieldAcceptanceClient(base_url=fake_service.base_url, token=TOKEN)
    client.start_observation(STREAM_ID)  # the real client class -- "authenticated Observation start"

    final_snapshot_path = tmp_path / "counterfactual-final.json"
    finalization_report_path = tmp_path / "finalization-report.json"

    result = _run_driver(
        [
            "--base-url", fake_service.base_url, "run", "--stream-id", STREAM_ID,
            "--minimum-duration-seconds", "1", "--maximum-duration-seconds", "30",
            "--target-sample-count", "2", "--poll-interval-seconds", "1",
            "--stop-settlement-timeout-seconds", "30",
            "--final-snapshot-output", str(final_snapshot_path),
            "--finalization-report-output", str(finalization_report_path),
        ],
        env=_base_env(),
    )

    assert result.returncode == 0, f"stdout={result.stdout}\nstderr={result.stderr}"
    assert "Stop decision: target_reached_after_minimum_duration" in result.stdout
    assert "Finalization: settled_before_snapshot" in result.stdout
    assert f"Wrote {finalization_report_path}" in result.stdout
    assert f"Wrote {final_snapshot_path}" in result.stdout

    report = json.loads(finalization_report_path.read_text())
    assert report["stop_timing"]["stop_reason"] == "target_reached_after_minimum_duration"
    assert report["finalization"]["ready"] is True
    assert report["finalization"]["settlement"]["settled"] is True
    assert report["finalization"]["final_snapshot_included"] is True

    snapshot = json.loads(final_snapshot_path.read_text())
    proposal_ids = {item["proposal_id"] for item in snapshot["proposal_outcomes"]}
    assert "proposal-3-rescued" in proposal_ids, (
        "the candidate created during stop-finalization must appear in the final snapshot"
    )


# ---------------------------------------------------------------------------
# The hard maximum deadline fires even though the sample target is never
# reached -- exercised through the real CLI's own argument parsing, not
# only run_stop_timing_loop() directly.
# ---------------------------------------------------------------------------


def test_real_subprocess_run_stops_at_the_maximum_when_target_never_reached(
    fake_service, tmp_path: Path,
) -> None:
    client = FieldAcceptanceClient(base_url=fake_service.base_url, token=TOKEN)
    client.start_observation(STREAM_ID)

    final_snapshot_path = tmp_path / "counterfactual-final.json"
    finalization_report_path = tmp_path / "finalization-report.json"

    result = _run_driver(
        [
            "--base-url", fake_service.base_url, "run", "--stream-id", STREAM_ID,
            "--minimum-duration-seconds", "1", "--maximum-duration-seconds", "3",
            "--target-sample-count", "999", "--poll-interval-seconds", "1",
            "--stop-settlement-timeout-seconds", "30",
            "--final-snapshot-output", str(final_snapshot_path),
            "--finalization-report-output", str(finalization_report_path),
        ],
        env=_base_env(),
    )

    assert result.returncode == 0, f"stdout={result.stdout}\nstderr={result.stderr}"
    assert "Stop decision: maximum_duration_reached" in result.stdout


# ---------------------------------------------------------------------------
# Finalization never treats a stuck "stopping" state as settled -- a
# settlement timeout is an honest, non-zero-exit outcome, and no final
# snapshot is ever written for it.
# ---------------------------------------------------------------------------


def test_real_subprocess_run_reports_settlement_timeout_and_exits_nonzero(tmp_path: Path) -> None:
    state = FakeObservationState(
        stream_id=STREAM_ID, bearer_token=TOKEN, instance_id="instance-real-cli-stuck",
        git_commit="d" * 40, build_id="build-real-cli-0002",
        stopping_polls_to_settle=1_000_000,  # never genuinely settles within any bounded test timeout
    )
    service = FakeFieldAcceptanceService(state).start()
    try:
        client = FieldAcceptanceClient(base_url=service.base_url, token=TOKEN)
        client.start_observation(STREAM_ID)

        final_snapshot_path = tmp_path / "counterfactual-final.json"
        finalization_report_path = tmp_path / "finalization-report.json"

        result = _run_driver(
            [
                "--base-url", service.base_url, "run", "--stream-id", STREAM_ID,
                "--minimum-duration-seconds", "0.5", "--maximum-duration-seconds", "5",
                "--target-sample-count", "1", "--poll-interval-seconds", "0.5",
                "--stop-settlement-timeout-seconds", "3",
                "--final-snapshot-output", str(final_snapshot_path),
                "--finalization-report-output", str(finalization_report_path),
            ],
            env=_base_env(),
        )
    finally:
        service.stop()

    assert result.returncode == 1, f"stdout={result.stdout}\nstderr={result.stderr}"
    assert "stop_settlement_timed_out" in result.stdout
    assert f"Wrote {finalization_report_path}" in result.stdout  # always written
    assert not final_snapshot_path.exists(), "a pre-settlement fetch must never be written as the final snapshot"

    report = json.loads(finalization_report_path.read_text())
    assert report["finalization"]["ready"] is False
    assert report["finalization"]["final_snapshot_included"] is False


# ---------------------------------------------------------------------------
# Authenticated requests: the real client's own error taxonomy over a real
# 401/local precondition, surfaced through the CLI's own exit status.
# ---------------------------------------------------------------------------


def test_real_subprocess_run_fails_clearly_with_an_invalid_credential(
    fake_service, tmp_path: Path,
) -> None:
    client = FieldAcceptanceClient(base_url=fake_service.base_url, token=TOKEN)
    client.start_observation(STREAM_ID)

    result = _run_driver(
        [
            "--base-url", fake_service.base_url, "run", "--stream-id", STREAM_ID,
            "--minimum-duration-seconds", "1", "--maximum-duration-seconds", "5",
            "--target-sample-count", "1", "--poll-interval-seconds", "1",
            "--final-snapshot-output", str(tmp_path / "final.json"),
            "--finalization-report-output", str(tmp_path / "report.json"),
        ],
        env=_base_env(token="a-completely-wrong-token"),
    )

    assert result.returncode == 1
    assert "ERROR:" in result.stderr
    assert "invalid" in result.stderr.lower() or "missing" in result.stderr.lower() or "revoked" in result.stderr.lower()


def test_real_subprocess_run_fails_clearly_with_no_credential_configured(
    fake_service, tmp_path: Path,
) -> None:
    result = _run_driver(
        [
            "--base-url", fake_service.base_url, "run", "--stream-id", STREAM_ID,
            "--minimum-duration-seconds", "1", "--maximum-duration-seconds", "5",
            "--target-sample-count", "1", "--poll-interval-seconds", "1",
            "--final-snapshot-output", str(tmp_path / "final.json"),
            "--finalization-report-output", str(tmp_path / "report.json"),
        ],
        env=_base_env(token=None),
    )

    assert result.returncode == 1
    assert "ERROR:" in result.stderr
    assert "MOCKINGBIRD_ACCEPTANCE_TOKEN" in result.stderr


# ---------------------------------------------------------------------------
# --help stays a real, zero-dependency argparse smoke path (no server, no
# credential needed at all) -- cheap, real-subprocess confirmation that the
# CLI's own argument parsing is independently sound.
# ---------------------------------------------------------------------------


def test_real_subprocess_help_exits_zero_with_no_server_or_credential() -> None:
    result = subprocess.run(
        [sys.executable, str(DRIVER_SCRIPT), "run", "--help"],
        cwd=str(ROOT), env={**os.environ}, capture_output=True, text=True, timeout=15.0,
    )

    assert result.returncode == 0
    assert "--stream-id" in result.stdout
    assert "--final-snapshot-output" in result.stdout
