"""Structural tests for scripts/field_acceptance_session_driver.py.

See docs/field-acceptance-tooling-correctness-preflight-closure-v1-report.md
for the governing milestone. Entirely hermetic -- every test drives the
module against a small in-memory fake client and a fake monotonic
clock/sleep, never a real HTTP call, a real Observation session, or a real
45-75 minute sleep.

Loaded via `runpy.run_path`, matching every other `scripts/` test file's
own established convention.
"""

from __future__ import annotations

from pathlib import Path
import runpy

import pytest

ROOT = Path(__file__).resolve().parents[1]
_MODULE = runpy.run_path(str(ROOT / "scripts" / "field_acceptance_session_driver.py"))

SessionDriverConfig = _MODULE["SessionDriverConfig"]
decide_stop = _MODULE["decide_stop"]
run_stop_timing_loop = _MODULE["run_stop_timing_loop"]
wait_for_stop_settlement = _MODULE["wait_for_stop_settlement"]
stop_and_capture_final_snapshot = _MODULE["stop_and_capture_final_snapshot"]


class _FakeClock:
    """A controllable monotonic clock -- `sleep` advances it directly, and
    may optionally raise `KeyboardInterrupt` on a scripted call to prove
    the loop treats that as an immediate, graceful early-stop signal (see
    `field_acceptance_ledger_snapshot.run_periodic_collection`'s own
    identical established convention)."""

    def __init__(self, *, interrupt_after: int | None = None) -> None:
        self.now = 0.0
        self._calls = 0
        self._interrupt_after = interrupt_after

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self._calls += 1
        if self._interrupt_after is not None and self._calls > self._interrupt_after:
            raise KeyboardInterrupt
        self.now += seconds


# ---------------------------------------------------------------------------
# decide_stop: pure, no clock/sleep/IO needed at all.
# ---------------------------------------------------------------------------


def test_decide_stop_continues_before_minimum_duration_even_with_target_already_met() -> None:
    """Governing brief §5: 'it continues to 45 minutes even if the sample
    target arrives early.'"""

    config = SessionDriverConfig(minimum_duration_seconds=2700, maximum_duration_seconds=4500, target_sample_count=12)

    assert decide_stop(elapsed_seconds=0.0, sample_count=12, config=config) is None
    assert decide_stop(elapsed_seconds=2699.9, sample_count=50, config=config) is None


def test_decide_stop_fires_at_the_minimum_once_target_is_met() -> None:
    config = SessionDriverConfig(minimum_duration_seconds=2700, maximum_duration_seconds=4500, target_sample_count=12)

    assert decide_stop(elapsed_seconds=2700.0, sample_count=12, config=config) == "target_reached_after_minimum_duration"


def test_decide_stop_continues_past_minimum_when_target_not_yet_met() -> None:
    """Governing brief §5: 'fewer than 12 at 75 minutes' must still run to the maximum."""

    config = SessionDriverConfig(minimum_duration_seconds=2700, maximum_duration_seconds=4500, target_sample_count=12)

    assert decide_stop(elapsed_seconds=4499.9, sample_count=5, config=config) is None


def test_decide_stop_fires_at_the_exact_maximum_regardless_of_sample_count() -> None:
    config = SessionDriverConfig(minimum_duration_seconds=2700, maximum_duration_seconds=4500, target_sample_count=12)

    assert decide_stop(elapsed_seconds=4500.0, sample_count=0, config=config) == "maximum_duration_reached"


def test_decide_stop_maximum_wins_even_if_target_is_also_met() -> None:
    config = SessionDriverConfig(minimum_duration_seconds=2700, maximum_duration_seconds=4500, target_sample_count=12)

    assert decide_stop(elapsed_seconds=4500.0, sample_count=999, config=config) == "maximum_duration_reached"


def test_decide_stop_early_stop_reason_wins_immediately_even_before_minimum() -> None:
    """Governing brief §5: 'daylight/safety deterioration can stop it earlier.'"""

    config = SessionDriverConfig(minimum_duration_seconds=2700, maximum_duration_seconds=4500, target_sample_count=12)

    assert (
        decide_stop(elapsed_seconds=10.0, sample_count=0, config=config, early_stop_reason="daylight_deteriorating")
        == "daylight_deteriorating"
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("minimum_duration_seconds", 0),
        ("target_sample_count", -1),
        ("poll_interval_seconds", 0),
        ("stop_settlement_timeout_seconds", 0),
        ("stop_settlement_poll_interval_seconds", 0),
    ],
)
def test_config_rejects_invalid_values(field: str, value: float) -> None:
    with pytest.raises(ValueError):
        SessionDriverConfig(**{field: value})


def test_config_rejects_maximum_before_minimum() -> None:
    with pytest.raises(ValueError, match="maximum_duration_seconds_before_minimum"):
        SessionDriverConfig(minimum_duration_seconds=100, maximum_duration_seconds=50)


# ---------------------------------------------------------------------------
# run_stop_timing_loop: the real, clock-driven polling loop.
# ---------------------------------------------------------------------------


def test_loop_continues_to_minimum_duration_before_stopping_on_an_early_target(tmp_path: Path) -> None:
    config = SessionDriverConfig(
        minimum_duration_seconds=120, maximum_duration_seconds=300, target_sample_count=3, poll_interval_seconds=30,
    )
    clock = _FakeClock()

    result = run_stop_timing_loop(
        config=config, sample_count_fn=lambda: 5,  # target already met from t=0
        monotonic_fn=clock.monotonic, sleep_fn=clock.sleep,
    )

    assert result.stop_reason == "target_reached_after_minimum_duration"
    assert result.elapsed_seconds == 120.0  # not a moment before the minimum, despite being sample-ready since t=0


def test_loop_runs_to_the_maximum_when_target_is_never_reached(tmp_path: Path) -> None:
    config = SessionDriverConfig(
        minimum_duration_seconds=120, maximum_duration_seconds=300, target_sample_count=12, poll_interval_seconds=30,
    )
    clock = _FakeClock()

    result = run_stop_timing_loop(
        config=config, sample_count_fn=lambda: 2,  # never reaches the target
        monotonic_fn=clock.monotonic, sleep_fn=clock.sleep,
    )

    assert result.stop_reason == "maximum_duration_reached"
    assert result.elapsed_seconds == 300.0
    assert result.sample_count_at_stop == 2


def test_loop_hits_the_exact_deadline_with_no_polling_overshoot_for_a_non_dividing_interval() -> None:
    """Governing brief §5: 'stops at the 75-minute deadline... it does not
    wait for the next five-minute status tick.' A poll interval that does
    *not* evenly divide the remaining time must still land exactly on the
    deadline, never overshoot by a full ordinary poll_interval_seconds."""

    config = SessionDriverConfig(
        minimum_duration_seconds=100, maximum_duration_seconds=100, target_sample_count=999, poll_interval_seconds=37,
    )
    clock = _FakeClock()

    result = run_stop_timing_loop(config=config, sample_count_fn=lambda: 0, monotonic_fn=clock.monotonic, sleep_fn=clock.sleep)

    assert result.elapsed_seconds == 100.0  # exact -- never 111 (3 * 37) or any other overshoot


def test_loop_early_stop_check_fn_stops_immediately_before_the_minimum() -> None:
    config = SessionDriverConfig(minimum_duration_seconds=2700, maximum_duration_seconds=4500, poll_interval_seconds=30)
    clock = _FakeClock()
    calls = {"n": 0}

    def _early_stop() -> str | None:
        calls["n"] += 1
        return "daylight_deteriorating" if calls["n"] >= 3 else None

    result = run_stop_timing_loop(
        config=config, sample_count_fn=lambda: 0, early_stop_check_fn=_early_stop,
        monotonic_fn=clock.monotonic, sleep_fn=clock.sleep,
    )

    assert result.stop_reason == "daylight_deteriorating"
    assert result.elapsed_seconds == 60.0  # two ordinary polls elapsed before the third one triggered the stop


def test_loop_treats_keyboard_interrupt_as_a_graceful_early_stop_never_a_crash() -> None:
    config = SessionDriverConfig(minimum_duration_seconds=2700, maximum_duration_seconds=4500, poll_interval_seconds=30)
    clock = _FakeClock(interrupt_after=2)  # Ctrl+C lands on the third sleep

    result = run_stop_timing_loop(config=config, sample_count_fn=lambda: 0, monotonic_fn=clock.monotonic, sleep_fn=clock.sleep)

    assert result.stop_reason == "operator_early_stop"
    assert result.elapsed_seconds == 60.0  # the clock never advanced past the interrupted sleep


# ---------------------------------------------------------------------------
# Post-finalization ledger contract: settlement polling + final snapshot.
# ---------------------------------------------------------------------------


class _FakeClient:
    def __init__(self, *, status_sequence: list[dict], snapshot_payload: dict) -> None:
        self._status_sequence = list(status_sequence)
        self._snapshot_payload = snapshot_payload
        self.stop_calls = 0
        self.snapshot_calls: list[tuple[int, int]] = []

    def stop_observation(self, _stream_id: str) -> None:
        self.stop_calls += 1

    def observation_status(self, _stream_id: str) -> dict:
        if len(self._status_sequence) > 1:
            return self._status_sequence.pop(0)
        return self._status_sequence[0]  # holds at the last scripted value once exhausted

    def observation_counterfactual(self, _stream_id: str, *, start_offset_ms: int, end_offset_ms: int) -> dict:
        self.snapshot_calls.append((start_offset_ms, end_offset_ms))
        return self._snapshot_payload


def test_wait_for_stop_settlement_polls_through_a_transient_stopping_state() -> None:
    """'stopping' is a real, distinct, transient state -- must not be
    mistaken for settled, but must not time out for it either."""

    client = _FakeClient(
        status_sequence=[{"state": "stopping"}, {"state": "stopping"}, {"state": "stopped"}],
        snapshot_payload={},
    )
    config = SessionDriverConfig(stop_settlement_timeout_seconds=30, stop_settlement_poll_interval_seconds=2)
    clock = _FakeClock()

    result = wait_for_stop_settlement(
        client, stream_id="s1", config=config, monotonic_fn=clock.monotonic, sleep_fn=clock.sleep,
    )

    assert result.settled is True
    assert result.stopped_state == "stopped"
    assert result.poll_count == 3


def test_wait_for_stop_settlement_times_out_when_never_stopped() -> None:
    client = _FakeClient(status_sequence=[{"state": "stopping"}], snapshot_payload={})
    config = SessionDriverConfig(stop_settlement_timeout_seconds=10, stop_settlement_poll_interval_seconds=2)
    clock = _FakeClock()

    result = wait_for_stop_settlement(
        client, stream_id="s1", config=config, monotonic_fn=clock.monotonic, sleep_fn=clock.sleep,
    )

    assert result.settled is False
    assert result.settled_at is None
    assert result.elapsed_seconds == 10.0


def test_stop_and_capture_final_snapshot_orders_stop_then_settle_then_snapshot() -> None:
    """Governing brief §6's required ordering: Observation stop ->
    finalization settled -> final raw-ledger snapshot -- captures a
    candidate that was only rescued during finalization, proving the
    snapshot really is taken after settlement, not before or during it."""

    rescued_payload = {
        "proposal_outcomes": [
            {"proposal_id": "p1", "decided_at": "2026-09-07T14:00:00Z"},
            {"proposal_id": "p2-rescued-during-finalization", "decided_at": "2026-09-07T14:03:45Z"},
        ],
    }
    client = _FakeClient(
        status_sequence=[{"state": "stopping"}, {"state": "stopping"}, {"state": "stopped"}],
        snapshot_payload=rescued_payload,
    )
    config = SessionDriverConfig(stop_settlement_timeout_seconds=30, stop_settlement_poll_interval_seconds=2)
    clock = _FakeClock()

    result = stop_and_capture_final_snapshot(
        client, stream_id="s1", end_offset_ms=86_400_000, config=config,
        monotonic_fn=clock.monotonic, sleep_fn=clock.sleep,
    )

    assert result.ready is True
    assert client.stop_calls == 1
    assert len(client.snapshot_calls) == 1  # exactly one fetch -- taken only after settlement, never a pre-settlement one
    assert result.final_snapshot == rescued_payload
    proposal_ids = {item["proposal_id"] for item in result.final_snapshot["proposal_outcomes"]}
    assert "p2-rescued-during-finalization" in proposal_ids


def test_stop_and_capture_final_snapshot_never_fetches_when_settlement_times_out() -> None:
    """Never treats a pre-settlement/still-finalizing state as final --
    the exact ordering violation governing brief §6 forbids."""

    client = _FakeClient(status_sequence=[{"state": "stopping"}], snapshot_payload={"proposal_outcomes": []})
    config = SessionDriverConfig(stop_settlement_timeout_seconds=10, stop_settlement_poll_interval_seconds=2)
    clock = _FakeClock()

    result = stop_and_capture_final_snapshot(
        client, stream_id="s1", end_offset_ms=86_400_000, config=config,
        monotonic_fn=clock.monotonic, sleep_fn=clock.sleep,
    )

    assert result.ready is False
    assert result.final_snapshot is None
    assert client.snapshot_calls == []  # never fetched at all
    assert "stop_settlement_timed_out" in result.reason


def test_stop_and_capture_final_snapshot_always_calls_stop_exactly_once() -> None:
    client = _FakeClient(status_sequence=[{"state": "stopped"}], snapshot_payload={"proposal_outcomes": []})
    config = SessionDriverConfig()
    clock = _FakeClock()

    stop_and_capture_final_snapshot(
        client, stream_id="s1", end_offset_ms=86_400_000, config=config,
        monotonic_fn=clock.monotonic, sleep_fn=clock.sleep,
    )

    assert client.stop_calls == 1


# ---------------------------------------------------------------------------
# Process-hygiene structural invariant (governing brief §8: 'cleanup leaves
# no orphaned collector/driver process'). This driver runs synchronously,
# in-process, to completion -- it never spawns a background/detached child
# process of its own, so there is nothing it could orphan by construction.
# The historical `fa_driver.py` polling process Representative Daylight
# True-Latency Tail Convergence v3 found and cleaned up (a leftover,
# unattended, hand-written throwaway script from an *earlier* milestone --
# see that report's own §1) is exactly the shape this module replaces.
# ---------------------------------------------------------------------------


def test_module_never_spawns_a_subprocess() -> None:
    source = Path(ROOT / "scripts" / "field_acceptance_session_driver.py").read_text(encoding="utf-8")
    assert "subprocess" not in source
    assert "os.fork" not in source
    assert "Popen" not in source
