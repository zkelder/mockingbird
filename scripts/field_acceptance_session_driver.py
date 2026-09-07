#!/usr/bin/env python3
"""Field Acceptance Tooling Correctness & Preflight Closure v1: the
canonical field-session stop/finalization driver -- see docs/field-
acceptance-tooling-correctness-preflight-closure-v1-report.md.

## Why this exists

No tracked, tested driver for "how a field session decides when to stop,
and what happens immediately after" existed anywhere in this repository
before this milestone -- every real Gate A/Lane R field session (v4 through
Representative Daylight True-Latency Tail Convergence v3) drove this by
hand: an operator watched a ~5-minute status-report cadence and issued
`stop_observation` by eye once "close enough" to the accepted 45-minute
minimum / 75-minute maximum / >=12-sample-target session-bounds contract.
v3's own session (§8 of its report) landed at "75.2 minutes wall-clock,
called this 'at, not over' the maximum" -- a judgment call, not an
enforced deadline. Two more real gaps follow directly from that same
by-hand procedure:

- The stop *deadline* was never monotonic-clock-enforced, so it can drift
  with however often an operator happens to check, or with any real
  wall-clock adjustment during a 45-75 minute session.
- The *post-stop-finalization* ledger snapshot -- required to be taken only
  after Observation's own stop-finalization has genuinely settled, never
  before (a real, in-flight candidate can be rescued *during* finalization
  -- see v3's own candidate-012, `decided_at` after the stop request) --
  was likewise a manual operator judgment call: v3's own report (§7/§8)
  narrates the operator personally noticing a first corrective fetch had
  predated the rescue and taking a *second* one after settlement, purely
  because they happened to check. This module makes that the enforced
  default, not a vigilance-dependent manual step.

## What this is (and is not)

Two composable pieces, deliberately kept separate and independently
testable:

- `run_stop_timing_loop` (governing brief §5, 'Session stop contract'):
  polls, on its own bounded cadence (`config.poll_interval_seconds` --
  never the unrelated ~5-minute status-report tick a real session's
  monitoring output happens to use), until a hard, monotonic-clock-enforced
  stop decision (`decide_stop`, a pure function with no I/O of its own) is
  due. Continues to the minimum duration even if the sample target arrives
  early; stops at the maximum deadline regardless of sample count; never
  overshoots the maximum by more than one bounded poll interval; an
  operator's own daylight/safety judgment (`Ctrl+C`, or an injected
  `early_stop_check_fn`) can stop it earlier at any time.
- `stop_and_capture_final_snapshot` (governing brief §6, 'Post-finalization
  ledger contract'): calls `stop_observation`, polls `observation_status`
  until it genuinely settles to `state == "stopped"` (bounded by `config.
  stop_settlement_timeout_seconds`), and *only then* takes the one
  authenticated raw-ledger snapshot this function treats as final. Never
  takes a snapshot at all if settlement times out -- a caller must not
  treat an unsettled fetch as final (see `FinalizationResult.reason`).

Not a full field-session launcher (no deploy/pairing/credential-
provisioning orchestration, no acceptance-recorder wiring, no tmux) --
matches `field_acceptance_client.py`/`field_acceptance_ledger_snapshot.py`'s
own explicitly bounded scope, which this module builds on (via the same
`_fac()` `runpy.run_path` reuse convention) rather than duplicates. Not a
sample-validity classifier -- `sample_count_fn`'s own default reads the
live, in-session `candidates_created` running counter
(`ObservationSessionStatusResponse.counts`) as a bounded-effort *progress*
proxy only; the true procedurally-valid/invalid split is, as before this
milestone, computed after the fact by `run_gate_a_measurement_accounting.py`
against the reconciled ledger -- this module never re-implements that.

## Usage

    python scripts/field_acceptance_session_driver.py run \\
        --stream-id <id> --final-snapshot-output data/field-acceptance/<slug>/counterfactual-final.json \\
        --finalization-report-output data/field-acceptance/<slug>/finalization-report.json

Exit code 0 only when the session stopped and finalization settled with a
real final snapshot captured; 1 otherwise -- a non-zero exit means the
operator must investigate before treating the session's own evidence as
complete (see `field_acceptance_ledger_snapshot.py reconcile`, next).
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import runpy
import sys
import time
from typing import Any, Callable

ROOT = Path(__file__).resolve().parent.parent

_fac_module: dict[str, object] | None = None


def _fac() -> dict[str, object]:
    global _fac_module
    if _fac_module is None:
        _fac_module = runpy.run_path(str(ROOT / "scripts" / "field_acceptance_client.py"))
    return _fac_module


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


# ---------------------------------------------------------------------------
# Session stop contract (governing brief §5).
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SessionDriverConfig:
    """The accepted session-bounds contract, reused verbatim across every
    Representative Daylight field session's own governing directive:
    minimum 45 minutes, maximum 75 minutes, target >= 12 valid samples.
    Kept as named, overridable fields (never hardcoded literals inside
    `decide_stop`) so a future session with a different accepted contract
    never has to hand-edit this module's own logic."""

    minimum_duration_seconds: float = 45.0 * 60.0
    maximum_duration_seconds: float = 75.0 * 60.0
    target_sample_count: int = 12
    poll_interval_seconds: float = 60.0
    stop_settlement_timeout_seconds: float = 120.0
    stop_settlement_poll_interval_seconds: float = 2.0

    def __post_init__(self) -> None:
        if self.minimum_duration_seconds <= 0:
            raise ValueError("invalid_minimum_duration_seconds")
        if self.maximum_duration_seconds < self.minimum_duration_seconds:
            raise ValueError("maximum_duration_seconds_before_minimum")
        if self.target_sample_count < 0:
            raise ValueError("invalid_target_sample_count")
        if self.poll_interval_seconds <= 0:
            raise ValueError("invalid_poll_interval_seconds")
        if self.stop_settlement_timeout_seconds <= 0:
            raise ValueError("invalid_stop_settlement_timeout_seconds")
        if self.stop_settlement_poll_interval_seconds <= 0:
            raise ValueError("invalid_stop_settlement_poll_interval_seconds")


def decide_stop(
    *, elapsed_seconds: float, sample_count: int, config: SessionDriverConfig, early_stop_reason: str | None = None,
) -> str | None:
    """Pure -- no clock, no sleep, no I/O -- so the entire stop-timing
    contract is directly, trivially unit-testable against literal
    `elapsed_seconds`/`sample_count` values, with no fake-clock machinery
    needed for this piece specifically. Returns a stop reason once it is
    time to stop, else `None`. Checked in the order governing brief §5
    itself lists the requirements: an explicit early-stop reason (daylight/
    safety) always wins immediately; the hard maximum deadline is checked
    next (never skipped merely because the sample target was also met);
    only then does 'target reached, and at least the minimum has elapsed'
    apply -- so a target reached *before* the minimum never stops the
    session early on its own."""

    if early_stop_reason:
        return early_stop_reason
    if elapsed_seconds >= config.maximum_duration_seconds:
        return "maximum_duration_reached"
    if elapsed_seconds >= config.minimum_duration_seconds and sample_count >= config.target_sample_count:
        return "target_reached_after_minimum_duration"
    return None


@dataclass(frozen=True)
class StopTimingResult:
    stop_reason: str
    elapsed_seconds: float
    sample_count_at_stop: int
    poll_count: int

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def run_stop_timing_loop(
    *,
    config: SessionDriverConfig,
    sample_count_fn: Callable[[], int],
    early_stop_check_fn: "Callable[[], str | None] | None" = None,
    monotonic_fn: "Callable[[], float] | None" = None,
    sleep_fn: "Callable[[float], None] | None" = None,
) -> StopTimingResult:
    """The bounded polling loop that actually drives real time. Uses a
    monotonic clock (`monotonic_fn`, default `time.monotonic`) for elapsed
    time -- never wall-clock `datetime.now()` -- so a real-world clock
    adjustment during a 45-75 minute session can never perturb the
    deadline (governing brief §5: 'Use a monotonic deadline where
    appropriate'). Every sleep is clamped to never carry `elapsed_seconds`
    past `config.maximum_duration_seconds` -- the hard deadline is met
    *exactly*, never overshot merely because it fell between two ordinary
    poll ticks. `Ctrl+C` (or, in a test, `sleep_fn` raising
    `KeyboardInterrupt`) is treated as an immediate operator early-stop
    signal -- mirrors `field_acceptance_ledger_snapshot.run_periodic_
    collection`'s own established `KeyboardInterrupt` handling -- and
    still returns normally (never propagates), so a caller's own
    stop-and-finalize sequence always still runs afterward.

    `monotonic_fn`/`sleep_fn` default to real `time.monotonic`/`time.sleep`,
    late-bound fresh on every call (never captured at module-load/def
    time), matching this package's own established discipline."""

    if monotonic_fn is None:
        monotonic_fn = time.monotonic
    if sleep_fn is None:
        sleep_fn = time.sleep

    start = monotonic_fn()
    poll_count = 0
    while True:
        poll_count += 1
        elapsed = monotonic_fn() - start
        sample_count = sample_count_fn()
        early_reason = early_stop_check_fn() if early_stop_check_fn is not None else None
        reason = decide_stop(
            elapsed_seconds=elapsed, sample_count=sample_count, config=config, early_stop_reason=early_reason,
        )
        if reason is not None:
            return StopTimingResult(
                stop_reason=reason, elapsed_seconds=elapsed, sample_count_at_stop=sample_count, poll_count=poll_count,
            )
        remaining_to_max = config.maximum_duration_seconds - elapsed
        wait_seconds = min(config.poll_interval_seconds, remaining_to_max)
        try:
            sleep_fn(wait_seconds)
        except KeyboardInterrupt:
            elapsed = monotonic_fn() - start
            return StopTimingResult(
                stop_reason="operator_early_stop", elapsed_seconds=elapsed,
                sample_count_at_stop=sample_count_fn(), poll_count=poll_count,
            )


# ---------------------------------------------------------------------------
# Post-finalization ledger contract (governing brief §6).
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class StopSettlementResult:
    settled: bool
    settled_at: str | None
    stopped_state: str | None
    poll_count: int
    elapsed_seconds: float

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def wait_for_stop_settlement(
    client: Any,
    *,
    stream_id: str,
    config: SessionDriverConfig,
    monotonic_fn: "Callable[[], float] | None" = None,
    sleep_fn: "Callable[[float], None] | None" = None,
    now_iso_fn: "Callable[[], str] | None" = None,
) -> StopSettlementResult:
    """Polls `observation_status(stream_id)` (`ObservationSessionStatus
    Response.state`, a `Literal["stopped", "starting", "observing",
    "stopping", "needs_attention"]`) until it genuinely settles to
    `"stopped"` -- never merely the *absence* of `observing`, and never
    merely one single check. `"stopping"` is a real, distinct, transient
    state a session can sit in for several seconds while an in-flight
    candidate rescue/finalization completes -- exactly what Representative
    Daylight True-Latency Tail Convergence v3's own candidate-012 (rescued
    during finalization, `decided_at` after the stop request) depended on.
    Bounded by `config.stop_settlement_timeout_seconds`; `settled=False`
    (never an exception) when that timeout elapses first -- the caller
    (`stop_and_capture_final_snapshot`) is responsible for refusing to
    treat that as ready for a final snapshot."""

    if monotonic_fn is None:
        monotonic_fn = time.monotonic
    if sleep_fn is None:
        sleep_fn = time.sleep
    if now_iso_fn is None:
        now_iso_fn = _now_iso

    start = monotonic_fn()
    poll_count = 0
    while True:
        poll_count += 1
        status = client.observation_status(stream_id)
        state = status.get("state") if isinstance(status, dict) else None
        elapsed = monotonic_fn() - start
        if state == "stopped":
            return StopSettlementResult(
                settled=True, settled_at=now_iso_fn(), stopped_state=state,
                poll_count=poll_count, elapsed_seconds=elapsed,
            )
        if elapsed >= config.stop_settlement_timeout_seconds:
            return StopSettlementResult(
                settled=False, settled_at=None, stopped_state=state,
                poll_count=poll_count, elapsed_seconds=elapsed,
            )
        remaining = config.stop_settlement_timeout_seconds - elapsed
        sleep_fn(min(config.stop_settlement_poll_interval_seconds, remaining))


@dataclass(frozen=True)
class FinalizationResult:
    stop_requested_at: str
    settlement: StopSettlementResult
    final_snapshot: dict | None
    final_snapshot_taken_at: str | None
    ready: bool
    reason: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "stop_requested_at": self.stop_requested_at, "settlement": self.settlement.as_dict(),
            "final_snapshot_taken_at": self.final_snapshot_taken_at, "ready": self.ready, "reason": self.reason,
            "final_snapshot_included": self.final_snapshot is not None,
        }


def stop_and_capture_final_snapshot(
    client: Any,
    *,
    stream_id: str,
    end_offset_ms: int,
    config: SessionDriverConfig,
    monotonic_fn: "Callable[[], float] | None" = None,
    sleep_fn: "Callable[[float], None] | None" = None,
    now_iso_fn: "Callable[[], str] | None" = None,
) -> FinalizationResult:
    """Governing brief §6's required ordering, enforced rather than left
    to an operator's own manual timing judgment: Observation stop ->
    finalization settled -> final authenticated raw-ledger snapshot,
    strictly in that order, every time. `client.observation_counterfactual`
    is called *at most once*, and only after `wait_for_stop_settlement`
    reports `settled=True` -- never before, never speculatively, never as
    a fallback. A settlement timeout returns `ready=False` with `final_
    snapshot=None`; the caller must not substitute an earlier (pre-stop or
    mid-finalization) fetch for this one."""

    if now_iso_fn is None:
        now_iso_fn = _now_iso
    stop_requested_at = now_iso_fn()
    client.stop_observation(stream_id)
    settlement = wait_for_stop_settlement(
        client, stream_id=stream_id, config=config,
        monotonic_fn=monotonic_fn, sleep_fn=sleep_fn, now_iso_fn=now_iso_fn,
    )
    if not settlement.settled:
        return FinalizationResult(
            stop_requested_at=stop_requested_at, settlement=settlement, final_snapshot=None,
            final_snapshot_taken_at=None, ready=False,
            reason=(
                f"stop_settlement_timed_out after {settlement.elapsed_seconds:.1f}s "
                f"(last observed state={settlement.stopped_state!r}) -- refusing to treat a pre-settlement "
                "fetch as final (governing brief §6). Investigate the deployed process directly before "
                "trusting any ledger snapshot from this session as complete."
            ),
        )
    final_snapshot = client.observation_counterfactual(stream_id, start_offset_ms=0, end_offset_ms=end_offset_ms)
    return FinalizationResult(
        stop_requested_at=stop_requested_at, settlement=settlement, final_snapshot=final_snapshot,
        final_snapshot_taken_at=now_iso_fn(), ready=True,
        reason="settled_before_snapshot -- final raw-ledger snapshot taken after stop-finalization settled.",
    )


# ---------------------------------------------------------------------------
# CLI: ties the two pieces together into one real field-session run.
# ---------------------------------------------------------------------------


def _default_sample_count_fn(client: Any, stream_id: str) -> Callable[[], int]:
    """Production default for `run_stop_timing_loop`'s own `sample_count_
    fn`: the live, in-session `candidates_created` running counter
    (`ObservationSessionStatusResponse.counts.candidates_created`) -- a
    bounded-effort *progress* proxy only (candidates created, not yet
    split into procedurally valid/invalid), matching this project's own
    established "informational, never the final truth" convention (see
    `field_acceptance_ledger_snapshot._ENTITY_FIELD`'s own docstring for
    the identical distinction elsewhere in this same tooling family). The
    true valid/invalid split is computed after the fact, as before this
    milestone, by `run_gate_a_measurement_accounting.py` against the
    reconciled ledger."""

    def _read() -> int:
        status = client.observation_status(stream_id)
        counts = status.get("counts") if isinstance(status, dict) else None
        value = (counts or {}).get("candidates_created")
        return int(value) if isinstance(value, (int, float)) else 0

    return _read


def _cmd_run(args: argparse.Namespace) -> int:
    fac = _fac()
    client = fac["FieldAcceptanceClient"](base_url=args.base_url)  # type: ignore[operator]
    config = SessionDriverConfig(
        minimum_duration_seconds=args.minimum_duration_seconds,
        maximum_duration_seconds=args.maximum_duration_seconds,
        target_sample_count=args.target_sample_count,
        poll_interval_seconds=args.poll_interval_seconds,
        stop_settlement_timeout_seconds=args.stop_settlement_timeout_seconds,
    )

    print(
        f"Driving Stream {args.stream_id}: minimum={config.minimum_duration_seconds/60:.1f}min, "
        f"maximum={config.maximum_duration_seconds/60:.1f}min, target={config.target_sample_count} samples, "
        f"polling every {config.poll_interval_seconds:.0f}s (Ctrl+C for an early daylight/safety stop)."
    )
    timing = run_stop_timing_loop(config=config, sample_count_fn=_default_sample_count_fn(client, args.stream_id))
    print(
        f"Stop decision: {timing.stop_reason} at {timing.elapsed_seconds/60:.1f}min "
        f"({timing.sample_count_at_stop} candidates created, {timing.poll_count} poll(s))."
    )

    print("Stopping Observation and waiting for finalization to settle...")
    finalization = stop_and_capture_final_snapshot(
        client, stream_id=args.stream_id, end_offset_ms=args.end_offset_ms, config=config,
    )
    print(f"Finalization: {finalization.reason}")

    args.finalization_report_output.parent.mkdir(parents=True, exist_ok=True)
    _write_json(
        args.finalization_report_output,
        {"stop_timing": timing.as_dict(), "finalization": finalization.as_dict(), "stream_id": args.stream_id},
    )
    print(f"Wrote {args.finalization_report_output}")

    if finalization.final_snapshot is not None:
        args.final_snapshot_output.parent.mkdir(parents=True, exist_ok=True)
        _write_json(args.final_snapshot_output, finalization.final_snapshot)
        print(f"Wrote {args.final_snapshot_output}")

    return 0 if finalization.ready else 1


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base-url", default=None)
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Drive one session's stop timing, then stop/finalize/snapshot.")
    run_parser.add_argument("--stream-id", required=True)
    run_parser.add_argument("--minimum-duration-seconds", type=float, default=SessionDriverConfig().minimum_duration_seconds)
    run_parser.add_argument("--maximum-duration-seconds", type=float, default=SessionDriverConfig().maximum_duration_seconds)
    run_parser.add_argument("--target-sample-count", type=int, default=SessionDriverConfig().target_sample_count)
    run_parser.add_argument("--poll-interval-seconds", type=float, default=SessionDriverConfig().poll_interval_seconds)
    run_parser.add_argument(
        "--stop-settlement-timeout-seconds", type=float, default=SessionDriverConfig().stop_settlement_timeout_seconds,
    )
    run_parser.add_argument("--end-offset-ms", type=int, default=86_400_000)
    run_parser.add_argument("--final-snapshot-output", type=Path, required=True)
    run_parser.add_argument("--finalization-report-output", type=Path, required=True)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_argument_parser().parse_args(argv)
    fac = _fac()
    if args.base_url is None:
        args.base_url = fac["DEFAULT_BASE_URL"]
    try:
        if args.command == "run":
            return _cmd_run(args)
        print(f"unknown command {args.command!r}", file=sys.stderr)
        return 2
    except fac["FieldAcceptanceClientError"] as error:  # type: ignore[misc]
        print(f"ERROR: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
