"""Camera Node -> Host Clock Normalization & True Capture-to-Visible Latency
v1: focused, hardware-free tests for the pure calibration/normalization
module (see
docs/camera-node-host-clock-normalization-latency-v1-report.md). Covers
every case named in this milestone's own governing brief §24 "Test matrix"
(Calibration/Drift/Clock jump sections) plus the selection-epoch model
`active_calibration_for_offset` needs.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Sequence

import pytest

from mockingbird.observation.clock_calibration import (
    DEFAULT_CLOCK_JUMP_THRESHOLD_MS,
    DEFAULT_MAX_ACCEPTABLE_RTT_MS,
    MINIMUM_CALIBRATION_SAMPLES,
    MINIMUM_RTT_CALIBRATION_SAMPLES,
    ClockCalibrationRecord,
    RttClockCalibrationRecord,
    RttRoundTrip,
    active_calibration_for_offset,
    active_rtt_calibration_for_offset,
    compute_drift,
    detect_clock_jump,
    estimate_clock_calibration,
    estimate_rtt_clock_calibration,
    normalize_capture_time,
    normalize_capture_time_with_bound,
)

STREAM_ID = "stream-a"
NOW = datetime(2026, 8, 31, 19, 45, 11, tzinfo=UTC)


def test_clock_calibration_module_has_no_product_repository_import() -> None:
    source = Path("src/mockingbird/observation/clock_calibration.py").read_text(encoding="utf-8")
    forbidden = ("mockingbird.repository", "mockingbird.storage", "mockingbird.api", "sqlalchemy")
    for token in forbidden:
        assert token not in source, f"clock_calibration.py must not reference {token}"


def _pairs(offset_ms: float, jitter_ms: Sequence[float], *, base: datetime = NOW) -> list[tuple[datetime, datetime]]:
    """`jitter_ms[i]` is the *extra*, non-negative one-way transit delay on
    top of the true `offset_ms` for sample `i` -- `received_at = base +
    i*1s + offset_ms + jitter_ms[i]` (all in ms), `captured_at = base +
    i*1s`. The true offset is always recoverable as `min(jitter_ms)` away
    from `offset_ms` -- i.e. `estimate_clock_calibration` should report
    `offset_ms + min(jitter_ms)`."""

    pairs = []
    for index, jitter in enumerate(jitter_ms):
        captured_at = base + timedelta(seconds=index)
        received_at = captured_at + timedelta(milliseconds=offset_ms + jitter)
        pairs.append((captured_at, received_at))
    return pairs


# --- Calibration --------------------------------------------------------


def test_calibration_zero_offset() -> None:
    pairs = _pairs(0.0, [10.0, 25.0, 5.0, 40.0, 15.0])
    record = estimate_clock_calibration(pairs, stream_id=STREAM_ID, source_offset_ms=5_000, calibrated_at=NOW)
    assert record.state == "calibrated"
    assert record.sample_count == 5
    assert record.offset_ms == pytest.approx(5.0)  # 0.0 true offset + min jitter (5.0)
    assert record.uncertainty_ms == pytest.approx(35.0)  # spread: 40.0 - 5.0


def test_calibration_positive_offset() -> None:
    """Host clock reads *ahead* of the Node's -- a positive offset."""
    pairs = _pairs(2_500.0, [8.0, 12.0, 3.0, 20.0, 6.0])
    record = estimate_clock_calibration(pairs, stream_id=STREAM_ID, source_offset_ms=5_000, calibrated_at=NOW)
    assert record.state == "calibrated"
    assert record.offset_ms == pytest.approx(2_503.0)
    assert record.uncertainty_ms == pytest.approx(17.0)


def test_calibration_negative_offset() -> None:
    """Host clock reads *behind* the Node's -- a negative offset."""
    pairs = _pairs(-1_800.0, [4.0, 9.0, 1.0, 15.0, 7.0])
    record = estimate_clock_calibration(pairs, stream_id=STREAM_ID, source_offset_ms=5_000, calibrated_at=NOW)
    assert record.state == "calibrated"
    assert record.offset_ms == pytest.approx(-1_799.0)
    assert record.uncertainty_ms == pytest.approx(14.0)


def test_calibration_bounded_uncertainty_widens_with_jitter_spread() -> None:
    """This module's own honest, non-NTP analog of a round-trip bound: a
    wider observed one-way-delay spread must report wider uncertainty, not
    a falsely-confident fixed number."""
    tight = estimate_clock_calibration(
        _pairs(0.0, [2.0, 3.0, 2.5, 3.5, 2.0]), stream_id=STREAM_ID, source_offset_ms=5_000, calibrated_at=NOW,
    )
    loose = estimate_clock_calibration(
        _pairs(0.0, [2.0, 400.0, 15.0, 900.0, 5.0]), stream_id=STREAM_ID, source_offset_ms=5_000, calibrated_at=NOW,
    )
    assert tight.uncertainty_ms < loose.uncertainty_ms
    assert tight.uncertainty_ms == pytest.approx(1.5)
    assert loose.uncertainty_ms == pytest.approx(898.0)


def test_calibration_insufficient_samples_is_a_real_auditable_state_not_a_crash() -> None:
    pairs = _pairs(100.0, [1.0, 2.0])  # fewer than MINIMUM_CALIBRATION_SAMPLES
    record = estimate_clock_calibration(pairs, stream_id=STREAM_ID, source_offset_ms=5_000, calibrated_at=NOW)
    assert record.state == "insufficient_samples"
    assert record.sample_count == 2
    assert record.offset_ms is None
    assert record.uncertainty_ms is None


def test_calibration_zero_pairs_is_insufficient_never_a_crash() -> None:
    record = estimate_clock_calibration((), stream_id=STREAM_ID, source_offset_ms=0, calibrated_at=NOW)
    assert record.state == "insufficient_samples"
    assert record.sample_count == 0


def test_calibration_exactly_at_the_minimum_sample_boundary_calibrates() -> None:
    pairs = _pairs(50.0, [1.0] * MINIMUM_CALIBRATION_SAMPLES)
    record = estimate_clock_calibration(pairs, stream_id=STREAM_ID, source_offset_ms=1_000, calibrated_at=NOW)
    assert record.state == "calibrated"
    assert record.sample_count == MINIMUM_CALIBRATION_SAMPLES


def test_calibration_rejects_naive_timestamps() -> None:
    naive = datetime(2026, 8, 31, 19, 45, 11)  # no tzinfo
    with pytest.raises(ValueError):
        estimate_clock_calibration(
            [(naive, NOW)], stream_id=STREAM_ID, source_offset_ms=0, calibrated_at=NOW, minimum_samples=1,
        )


def test_calibration_record_raises_on_calibrated_state_missing_numbers() -> None:
    with pytest.raises(ValueError):
        ClockCalibrationRecord(
            stream_id=STREAM_ID, source_offset_ms=0, calibrated_at=NOW, sample_count=5, state="calibrated",
        )


# --- Drift ----------------------------------------------------------------


def _calibration(offset_ms: float, *, source_offset_ms: int, calibrated_at: datetime, jump: bool = False) -> ClockCalibrationRecord:
    return ClockCalibrationRecord(
        stream_id=STREAM_ID, source_offset_ms=source_offset_ms, calibrated_at=calibrated_at,
        sample_count=MINIMUM_CALIBRATION_SAMPLES, state="calibrated", offset_ms=offset_ms,
        uncertainty_ms=20.0, min_delta_ms=offset_ms, max_delta_ms=offset_ms + 20.0, clock_jump_detected=jump,
    )


def test_drift_stable_clock_reports_near_zero_rate_and_no_jump() -> None:
    first = _calibration(500.0, source_offset_ms=0, calibrated_at=NOW)
    second = _calibration(510.0, source_offset_ms=600_000, calibrated_at=NOW + timedelta(minutes=10))
    drift = compute_drift(first, second)
    assert drift is not None
    assert drift.offset_delta_ms == pytest.approx(10.0)
    assert drift.drift_rate_ms_per_minute == pytest.approx(1.0)
    assert detect_clock_jump(first, second) is False


def test_drift_modest_drift_over_a_long_session_stays_within_bound() -> None:
    """This milestone's own §18: calibration at session start, a second
    calibration after a logical 60 minutes, offset differs modestly --
    drift is measured, but no jump is declared and normalization keeps
    working."""
    first = _calibration(200.0, source_offset_ms=0, calibrated_at=NOW)
    second = _calibration(1_400.0, source_offset_ms=3_600_000, calibrated_at=NOW + timedelta(minutes=60))
    drift = compute_drift(first, second)
    assert drift is not None
    assert drift.offset_delta_ms == pytest.approx(1_200.0)
    assert drift.drift_rate_ms_per_minute == pytest.approx(20.0)
    assert abs(drift.offset_delta_ms) < DEFAULT_CLOCK_JUMP_THRESHOLD_MS
    assert detect_clock_jump(first, second) is False

    # A t0 near the second calibration's own offset must use the fresher
    # mapping -- no "multi-second artificial latency error" from reusing
    # the session-start offset across the whole hour.
    active = active_calibration_for_offset([first, second], source_offset_ms=3_600_500)
    assert active is second


def test_drift_excessive_drift_exceeds_the_bound_and_is_treated_as_a_boundary() -> None:
    """Drift large enough to exceed the trusted bound is indistinguishable,
    from discrete periodic calibration alone, from a genuine clock reset --
    this module deliberately treats both the same way (see
    clock_calibration.py's own docstring): everything before the boundary
    stays valid for offsets that precede it, but nothing may extrapolate
    across it."""
    first = _calibration(100.0, source_offset_ms=0, calibrated_at=NOW)
    second = _calibration(100.0 + DEFAULT_CLOCK_JUMP_THRESHOLD_MS + 1, source_offset_ms=600_000, calibrated_at=NOW + timedelta(minutes=10))
    assert detect_clock_jump(first, second) is True
    drift = compute_drift(first, second)
    assert drift is not None
    assert drift.offset_delta_ms == pytest.approx(DEFAULT_CLOCK_JUMP_THRESHOLD_MS + 1)


def test_compute_drift_is_none_for_non_positive_elapsed_time() -> None:
    first = _calibration(100.0, source_offset_ms=1_000, calibrated_at=NOW)
    same_time = _calibration(200.0, source_offset_ms=2_000, calibrated_at=NOW)
    earlier = _calibration(200.0, source_offset_ms=2_000, calibrated_at=NOW - timedelta(seconds=1))
    assert compute_drift(first, same_time) is None
    assert compute_drift(first, earlier) is None


def test_compute_drift_is_none_when_either_sample_is_insufficient() -> None:
    calibrated = _calibration(100.0, source_offset_ms=0, calibrated_at=NOW)
    insufficient = ClockCalibrationRecord(
        stream_id=STREAM_ID, source_offset_ms=1_000, calibrated_at=NOW + timedelta(minutes=1),
        sample_count=1, state="insufficient_samples",
    )
    assert compute_drift(calibrated, insufficient) is None
    assert compute_drift(insufficient, calibrated) is None
    assert detect_clock_jump(calibrated, insufficient) is False


# --- Clock jump -------------------------------------------------------------


def test_clock_jump_forward_node_clock_jumps_ahead() -> None:
    """The Node's own wall clock suddenly jumps *forward* (e.g. +30s) --
    `captured_at` reads later than it should, so the observed
    `received_at - captured_at` offset drops sharply."""
    before = _calibration(50.0, source_offset_ms=0, calibrated_at=NOW)
    after = _calibration(50.0 - 30_000.0, source_offset_ms=100_000, calibrated_at=NOW + timedelta(seconds=100))
    assert detect_clock_jump(before, after) is True


def test_clock_jump_backward_node_clock_jumps_behind() -> None:
    """The Node's own wall clock suddenly jumps *backward* (e.g. -30s)."""
    before = _calibration(50.0, source_offset_ms=0, calibrated_at=NOW)
    after = _calibration(50.0 + 30_000.0, source_offset_ms=100_000, calibrated_at=NOW + timedelta(seconds=100))
    assert detect_clock_jump(before, after) is True


def test_clock_jump_invalidates_the_pre_jump_calibration_for_post_jump_offsets() -> None:
    """This milestone's own §17: subsequent latency samples become invalid
    until recalibrated -- `active_calibration_for_offset` must never let
    the pre-jump calibration answer for an offset at/after the jump."""
    pre_jump = _calibration(50.0, source_offset_ms=0, calibrated_at=NOW)
    post_jump = _calibration(30_050.0, source_offset_ms=100_000, calibrated_at=NOW + timedelta(seconds=100), jump=True)

    # An offset that occurred *before* the jump still safely uses the
    # pre-jump calibration -- nothing retroactively invalidated.
    assert active_calibration_for_offset([pre_jump, post_jump], source_offset_ms=50_000) is pre_jump
    # An offset at/after the jump uses the new (recalibrated) mapping.
    assert active_calibration_for_offset([pre_jump, post_jump], source_offset_ms=100_000) is post_jump
    assert active_calibration_for_offset([pre_jump, post_jump], source_offset_ms=250_000) is post_jump


def test_clock_jump_with_no_recalibration_yet_leaves_only_the_old_epoch_usable() -> None:
    """Immediately after a jump is detected but before any *further*
    calibration point exists beyond the jump sample itself, an offset at or
    after the jump still resolves to the jump sample (which *is* the
    recalibration) -- never silently reused from the invalidated epoch."""
    pre_jump = _calibration(50.0, source_offset_ms=0, calibrated_at=NOW)
    jump_sample = _calibration(30_050.0, source_offset_ms=100_000, calibrated_at=NOW + timedelta(seconds=100), jump=True)
    active = active_calibration_for_offset([pre_jump, jump_sample], source_offset_ms=150_000)
    assert active is jump_sample


# --- Selection / no-extrapolation-backward ----------------------------------


def test_no_calibration_at_all_returns_none_never_extrapolated() -> None:
    assert active_calibration_for_offset([], source_offset_ms=5_000) is None


def test_offset_preceding_the_first_calibration_is_none_never_extrapolated_backward() -> None:
    only = _calibration(75.0, source_offset_ms=10_000, calibrated_at=NOW)
    assert active_calibration_for_offset([only], source_offset_ms=9_999) is None
    assert active_calibration_for_offset([only], source_offset_ms=10_000) is only


def test_insufficient_samples_records_are_never_selected() -> None:
    insufficient = ClockCalibrationRecord(
        stream_id=STREAM_ID, source_offset_ms=0, calibrated_at=NOW, sample_count=1, state="insufficient_samples",
    )
    calibrated = _calibration(40.0, source_offset_ms=10_000, calibrated_at=NOW + timedelta(seconds=10))
    assert active_calibration_for_offset([insufficient, calibrated], source_offset_ms=5_000) is None
    assert active_calibration_for_offset([insufficient, calibrated], source_offset_ms=10_000) is calibrated


def test_selection_picks_the_latest_calibration_at_or_before_the_target_within_one_epoch() -> None:
    early = _calibration(10.0, source_offset_ms=0, calibrated_at=NOW)
    mid = _calibration(15.0, source_offset_ms=10_000, calibrated_at=NOW + timedelta(seconds=10))
    late = _calibration(20.0, source_offset_ms=20_000, calibrated_at=NOW + timedelta(seconds=20))
    calibrations = [late, early, mid]  # deliberately out of order -- selection must sort
    assert active_calibration_for_offset(calibrations, source_offset_ms=12_000) is mid
    assert active_calibration_for_offset(calibrations, source_offset_ms=25_000) is late
    assert active_calibration_for_offset(calibrations, source_offset_ms=0) is early


# --- normalize_capture_time --------------------------------------------------


def test_normalize_capture_time_applies_the_calibrated_offset() -> None:
    t0 = NOW
    calibration = _calibration(2_500.0, source_offset_ms=0, calibrated_at=NOW)
    result = normalize_capture_time(t0, [calibration], source_offset_ms=0)
    assert result.state == "normalized"
    assert result.host_domain_captured_at == t0 + timedelta(milliseconds=2_500.0)
    assert result.offset_ms == pytest.approx(2_500.0)
    assert result.uncertainty_ms == pytest.approx(20.0)


def test_normalize_capture_time_with_negative_offset() -> None:
    t0 = NOW
    calibration = _calibration(-1_200.0, source_offset_ms=0, calibrated_at=NOW)
    result = normalize_capture_time(t0, [calibration], source_offset_ms=0)
    assert result.host_domain_captured_at == t0 - timedelta(milliseconds=1_200.0)


def test_normalize_capture_time_no_calibration_never_fabricates_a_value() -> None:
    result = normalize_capture_time(NOW, [], source_offset_ms=5_000)
    assert result.state == "no_calibration"
    assert result.host_domain_captured_at is None
    assert result.offset_ms is None
    assert result.uncertainty_ms is None


# ===========================================================================
# Camera Node <-> Host RTT-Bounded Clock Calibration v1
# ===========================================================================
#
# Covers this milestone's own governing brief §31 "Test matrix" (RTT
# calibration / poor quality / epoch / semantics sections, as applicable to
# this pure module -- reconnect/fallback/stop-finalization/siblings are
# exercised in test_capture_to_visible_latency.py and test_engine_runtime.py
# instead, matching the existing split between this file and those).


def _round_trip(
    host_send_at: datetime,
    *,
    true_offset_ms: float,
    one_way_out_ms: float,
    one_way_back_ms: float,
    processing_ms: float = 0.0,
    four_timestamp: bool = True,
) -> RttRoundTrip:
    """Builds a *physically consistent* round trip for a given true
    Node->Host offset (`host_time = node_time + true_offset_ms`, matching
    the one-way estimator's own sign convention) and non-negative transit/
    processing legs -- mirrors `_pairs`'s own role above for the one-way
    estimator. `one_way_out_ms`/`one_way_back_ms`/`processing_ms` are all
    real, non-negative elapsed time, so the resulting sample's own interval
    is guaranteed to actually contain `true_offset_ms` -- exactly the
    property `_round_trip_bound`'s own inequality argument proves in
    general (see clock_calibration.py's own docstring "The interval
    bound")."""

    node_receive_at = host_send_at + timedelta(milliseconds=one_way_out_ms - true_offset_ms)
    node_response_at = node_receive_at + timedelta(milliseconds=processing_ms)
    host_receive_at = node_response_at + timedelta(milliseconds=true_offset_ms + one_way_back_ms)
    return RttRoundTrip(
        host_send_at=host_send_at,
        host_receive_at=host_receive_at,
        node_response_at=node_response_at,
        node_receive_at=node_receive_at if four_timestamp else None,
    )


def _symmetric_batch(
    true_offset_ms: float, *, count: int = 5, leg_ms: float = 1.0, base: datetime = NOW,
) -> list[RttRoundTrip]:
    """`count` samples, each with symmetric (`leg_ms` each way), tiny,
    varying-per-sample transit -- the ordinary "healthy LAN" shape."""

    return [
        _round_trip(
            base + timedelta(seconds=index),
            true_offset_ms=true_offset_ms, one_way_out_ms=leg_ms + index * 0.1, one_way_back_ms=leg_ms + index * 0.1,
        )
        for index in range(count)
    ]


# --- RTT calibration ---------------------------------------------------


def test_rtt_calibration_zero_offset_low_rtt() -> None:
    record = estimate_rtt_clock_calibration(
        _symmetric_batch(0.0), stream_id=STREAM_ID, source_offset_ms=5_000, calibrated_at=NOW,
    )
    assert record.state == "calibrated"
    assert record.valid_sample_count == 5
    assert record.offset_ms == pytest.approx(0.0, abs=1.0)
    assert record.offset_min_ms <= 0.0 <= record.offset_max_ms
    assert record.rtt_ms < 10.0  # tight LAN-shaped RTT
    assert record.uncertainty_ms < 5.0


def test_rtt_calibration_positive_offset() -> None:
    """Node clock reads *behind* the Host's -- a positive offset (matches
    the one-way estimator's own sign convention, `test_calibration_
    positive_offset`)."""
    record = estimate_rtt_clock_calibration(
        _symmetric_batch(2_500.0), stream_id=STREAM_ID, source_offset_ms=5_000, calibrated_at=NOW,
    )
    assert record.state == "calibrated"
    assert record.offset_ms == pytest.approx(2_500.0, abs=1.0)
    assert record.offset_min_ms <= 2_500.0 <= record.offset_max_ms


def test_rtt_calibration_negative_offset() -> None:
    record = estimate_rtt_clock_calibration(
        _symmetric_batch(-1_800.0), stream_id=STREAM_ID, source_offset_ms=5_000, calibrated_at=NOW,
    )
    assert record.state == "calibrated"
    assert record.offset_ms == pytest.approx(-1_800.0, abs=1.0)
    assert record.offset_min_ms <= -1_800.0 <= record.offset_max_ms


def test_rtt_calibration_interval_always_contains_the_true_offset_even_under_asymmetric_transit() -> None:
    """The bound is honest under transit asymmetry (this module's own
    docstring "Asymmetry limitation") -- the midpoint need not equal the
    true offset exactly, but the interval must still contain it."""
    sample = _round_trip(NOW, true_offset_ms=1_000.0, one_way_out_ms=2.0, one_way_back_ms=40.0)
    batch = [sample] * MINIMUM_RTT_CALIBRATION_SAMPLES  # identical samples -- still a valid, if uninformative, batch
    record = estimate_rtt_clock_calibration(batch, stream_id=STREAM_ID, source_offset_ms=0, calibrated_at=NOW)
    assert record.state == "calibrated"
    assert record.offset_min_ms <= 1_000.0 <= record.offset_max_ms
    # Asymmetric transit means the midpoint is *not* the true offset --
    # this is expected and honestly reflected, never silently corrected.
    assert record.offset_ms != pytest.approx(1_000.0, abs=0.01)


def test_rtt_calibration_multiple_samples_intersection_tightens_the_bound() -> None:
    """This module's own docstring "Multi-sample selection": the combined
    interval is the *intersection* of every valid sample's own interval --
    strictly tighter than the single loosest sample alone."""
    base = NOW
    tight = _round_trip(base, true_offset_ms=500.0, one_way_out_ms=1.0, one_way_back_ms=1.0)
    loose = _round_trip(base + timedelta(seconds=1), true_offset_ms=500.0, one_way_out_ms=50.0, one_way_back_ms=50.0)
    third = _round_trip(base + timedelta(seconds=2), true_offset_ms=500.0, one_way_out_ms=2.0, one_way_back_ms=2.0)

    combined = estimate_rtt_clock_calibration(
        [tight, loose, third], stream_id=STREAM_ID, source_offset_ms=0, calibrated_at=NOW,
    )
    tight_only = estimate_rtt_clock_calibration(
        [tight, tight, tight], stream_id=STREAM_ID, source_offset_ms=0, calibrated_at=NOW,
    )
    assert combined.state == "calibrated"
    # The intersection can only be as wide as (never wider than) the
    # tightest single sample's own interval.
    assert (combined.offset_max_ms - combined.offset_min_ms) <= (tight_only.offset_max_ms - tight_only.offset_min_ms) + 1e-9


def test_rtt_calibration_reports_the_lowest_rtt_sample_never_an_average() -> None:
    """This milestone's own explicit "do not average high-RTT samples into
    a falsely precise estimate" -- `rtt_ms`/`node_processing_ms` on the
    resulting record must be the single best (lowest-RTT) sample's own
    values, not a blended average across the batch."""
    base = NOW
    best = _round_trip(base, true_offset_ms=100.0, one_way_out_ms=1.0, one_way_back_ms=1.0, processing_ms=3.0)
    others = [
        _round_trip(base + timedelta(seconds=i), true_offset_ms=100.0, one_way_out_ms=20.0 + i, one_way_back_ms=20.0 + i)
        for i in range(1, 4)
    ]
    record = estimate_rtt_clock_calibration(
        [best, *others], stream_id=STREAM_ID, source_offset_ms=0, calibrated_at=NOW,
    )
    assert record.state == "calibrated"
    assert record.rtt_ms == pytest.approx(5.0)  # best's own RTT: 1 + 3 + 1
    assert record.node_processing_ms == pytest.approx(3.0)  # best's own processing time, not another sample's


def test_rtt_calibration_four_timestamp_form_tightens_using_node_processing_time() -> None:
    """This milestone's own §7/§8: preserving a measurable Node processing
    delay narrows the bound below plain `RTT/2` -- never discarded."""
    base = NOW
    four_timestamp = [
        _round_trip(base + timedelta(seconds=i), true_offset_ms=0.0, one_way_out_ms=1.0, one_way_back_ms=1.0, processing_ms=200.0)
        for i in range(MINIMUM_RTT_CALIBRATION_SAMPLES)
    ]
    two_timestamp = [
        _round_trip(
            base + timedelta(seconds=i), true_offset_ms=0.0, one_way_out_ms=1.0, one_way_back_ms=1.0,
            processing_ms=200.0, four_timestamp=False,
        )
        for i in range(MINIMUM_RTT_CALIBRATION_SAMPLES)
    ]
    four_record = estimate_rtt_clock_calibration(four_timestamp, stream_id=STREAM_ID, source_offset_ms=0, calibrated_at=NOW)
    two_record = estimate_rtt_clock_calibration(two_timestamp, stream_id=STREAM_ID, source_offset_ms=0, calibrated_at=NOW)
    assert four_record.state == "calibrated" and two_record.state == "calibrated"
    # Same physical RTT (202ms) in both cases -- the four-timestamp form's
    # own uncertainty must be strictly tighter, by exactly the disclosed
    # 200ms processing time (RTT/2 = 101 vs (RTT-processing)/2 = 1).
    assert four_record.rtt_ms == pytest.approx(two_record.rtt_ms)
    assert four_record.uncertainty_ms == pytest.approx(1.0)
    assert two_record.uncertainty_ms == pytest.approx(101.0)
    assert four_record.node_processing_ms == pytest.approx(200.0)
    assert two_record.node_processing_ms is None


def test_rtt_calibration_two_timestamp_form_matches_the_governing_brief_floor() -> None:
    """Two-timestamp form: uncertainty is exactly `RTT/2`, matching the
    governing brief's own explicit floor for the minimum form."""
    batch = [
        _round_trip(NOW + timedelta(seconds=i), true_offset_ms=50.0, one_way_out_ms=4.0, one_way_back_ms=4.0, four_timestamp=False)
        for i in range(MINIMUM_RTT_CALIBRATION_SAMPLES)
    ]
    record = estimate_rtt_clock_calibration(batch, stream_id=STREAM_ID, source_offset_ms=0, calibrated_at=NOW)
    assert record.state == "calibrated"
    assert record.uncertainty_ms == pytest.approx(record.rtt_ms / 2.0)


# --- Poor quality --------------------------------------------------------


def test_rtt_calibration_insufficient_samples_is_a_real_auditable_state_not_a_crash() -> None:
    batch = _symmetric_batch(0.0, count=MINIMUM_RTT_CALIBRATION_SAMPLES - 1)
    record = estimate_rtt_clock_calibration(batch, stream_id=STREAM_ID, source_offset_ms=0, calibrated_at=NOW)
    assert record.state == "insufficient_samples"
    assert record.sample_count == MINIMUM_RTT_CALIBRATION_SAMPLES - 1
    assert record.valid_sample_count == MINIMUM_RTT_CALIBRATION_SAMPLES - 1
    assert record.offset_ms is None
    assert record.offset_min_ms is None
    assert record.uncertainty_ms is None


def test_rtt_calibration_zero_samples_is_insufficient_never_a_crash() -> None:
    record = estimate_rtt_clock_calibration((), stream_id=STREAM_ID, source_offset_ms=0, calibrated_at=NOW)
    assert record.state == "insufficient_samples"
    assert record.sample_count == 0
    assert record.valid_sample_count == 0


def test_rtt_calibration_high_rtt_samples_are_excluded_never_averaged_in() -> None:
    """A deliberately poor calibration (this milestone's own §28): a
    high-RTT sample is dropped, not blended into a falsely precise
    estimate -- enough good samples remain here, so calibration still
    succeeds, unaffected by the bad one."""
    good = _symmetric_batch(500.0, count=MINIMUM_RTT_CALIBRATION_SAMPLES)
    poor = _round_trip(
        NOW + timedelta(seconds=99), true_offset_ms=500.0,
        one_way_out_ms=DEFAULT_MAX_ACCEPTABLE_RTT_MS, one_way_back_ms=DEFAULT_MAX_ACCEPTABLE_RTT_MS,
    )
    record = estimate_rtt_clock_calibration(
        [*good, poor], stream_id=STREAM_ID, source_offset_ms=0, calibrated_at=NOW,
    )
    assert record.state == "calibrated"
    assert record.valid_sample_count == len(good)  # the poor sample never counted
    assert record.sample_count == len(good) + 1
    assert record.rtt_ms < DEFAULT_MAX_ACCEPTABLE_RTT_MS


def test_rtt_calibration_all_high_rtt_samples_degrades_to_insufficient() -> None:
    poor = [
        _round_trip(
            NOW + timedelta(seconds=i), true_offset_ms=0.0,
            one_way_out_ms=DEFAULT_MAX_ACCEPTABLE_RTT_MS, one_way_back_ms=DEFAULT_MAX_ACCEPTABLE_RTT_MS,
        )
        for i in range(5)
    ]
    record = estimate_rtt_clock_calibration(poor, stream_id=STREAM_ID, source_offset_ms=0, calibrated_at=NOW)
    assert record.state == "insufficient_samples"
    assert record.valid_sample_count == 0
    assert record.sample_count == 5


def test_rtt_calibration_inconsistent_samples_do_not_overlap() -> None:
    """Simulates a clock jump *mid-batch* (this milestone's own §13 "Node
    clock jumps during the batch") -- non-overlapping per-sample intervals,
    detected without a second, dedicated jump-during-batch mechanism (see
    clock_calibration.py's own docstring "Multi-sample selection")."""
    before_jump = _symmetric_batch(0.0, count=3, base=NOW)
    after_jump = _symmetric_batch(30_000.0, count=3, base=NOW + timedelta(seconds=10))
    record = estimate_rtt_clock_calibration(
        [*before_jump, *after_jump], stream_id=STREAM_ID, source_offset_ms=0, calibrated_at=NOW,
    )
    assert record.state == "inconsistent_samples"
    assert record.offset_ms is None
    assert record.valid_sample_count == 6


def test_rtt_calibration_missing_node_timestamp_old_node_degrades_to_insufficient() -> None:
    """Old Node compatibility (this milestone's own §19): a response
    predating this milestone has no `node_time` at all."""
    old_node = [
        RttRoundTrip(host_send_at=NOW + timedelta(seconds=i), host_receive_at=NOW + timedelta(seconds=i, milliseconds=5), node_response_at=None)
        for i in range(5)
    ]
    record = estimate_rtt_clock_calibration(old_node, stream_id=STREAM_ID, source_offset_ms=0, calibrated_at=NOW)
    assert record.state == "insufficient_samples"
    assert record.valid_sample_count == 0
    assert record.sample_count == 5


def test_rtt_calibration_mixed_old_and_new_node_samples_uses_only_the_valid_ones() -> None:
    old_node = RttRoundTrip(host_send_at=NOW, host_receive_at=NOW + timedelta(milliseconds=5), node_response_at=None)
    modern = _symmetric_batch(200.0, count=MINIMUM_RTT_CALIBRATION_SAMPLES, base=NOW + timedelta(seconds=1))
    record = estimate_rtt_clock_calibration(
        [old_node, *modern], stream_id=STREAM_ID, source_offset_ms=0, calibrated_at=NOW,
    )
    assert record.state == "calibrated"
    assert record.valid_sample_count == MINIMUM_RTT_CALIBRATION_SAMPLES


def test_rtt_calibration_naive_node_timestamp_is_malformed_not_a_crash() -> None:
    """A malformed response (this milestone's own §13) -- a non-tz-aware
    Node timestamp -- degrades exactly like a missing one, never raises
    (unlike a naive *Host* timestamp; Host timestamps are trusted by
    construction, see the next test)."""
    naive = datetime(2026, 8, 31, 19, 45, 11)  # no tzinfo
    batch = [
        RttRoundTrip(host_send_at=NOW + timedelta(seconds=i), host_receive_at=NOW + timedelta(seconds=i, milliseconds=5), node_response_at=naive)
        for i in range(5)
    ]
    record = estimate_rtt_clock_calibration(batch, stream_id=STREAM_ID, source_offset_ms=0, calibrated_at=NOW)
    assert record.state == "insufficient_samples"
    assert record.valid_sample_count == 0


def test_rtt_calibration_rejects_naive_host_timestamps() -> None:
    naive = datetime(2026, 8, 31, 19, 45, 11)
    batch = [RttRoundTrip(host_send_at=naive, host_receive_at=NOW, node_response_at=NOW)] * MINIMUM_RTT_CALIBRATION_SAMPLES
    with pytest.raises(ValueError):
        estimate_rtt_clock_calibration(batch, stream_id=STREAM_ID, source_offset_ms=0, calibrated_at=NOW)


def test_rtt_calibration_rejects_naive_calibrated_at() -> None:
    naive = datetime(2026, 8, 31, 19, 45, 11)
    with pytest.raises(ValueError):
        estimate_rtt_clock_calibration(
            _symmetric_batch(0.0), stream_id=STREAM_ID, source_offset_ms=0, calibrated_at=naive,
        )


def test_rtt_calibration_negative_measured_rtt_is_treated_as_malformed() -> None:
    """A structurally impossible sample (response bracketed as arriving
    before it was sent) -- never a crash, never a fabricated negative RTT."""
    backwards = [
        RttRoundTrip(
            host_send_at=NOW + timedelta(seconds=i, milliseconds=10),
            host_receive_at=NOW + timedelta(seconds=i),  # H1 before H0
            node_response_at=NOW + timedelta(seconds=i),
        )
        for i in range(5)
    ]
    record = estimate_rtt_clock_calibration(backwards, stream_id=STREAM_ID, source_offset_ms=0, calibrated_at=NOW)
    assert record.state == "insufficient_samples"
    assert record.valid_sample_count == 0


def test_rtt_calibration_impossible_node_processing_time_is_treated_as_malformed() -> None:
    """This milestone's own §22 "impossible result policy": a Node that
    (falsely) claims to have processed for longer than the measured RTT
    itself produces `offset_min_ms > offset_max_ms` -- excluded, never
    clamped, never a silently-selected endpoint."""
    impossible = [
        RttRoundTrip(
            host_send_at=NOW + timedelta(seconds=i),
            host_receive_at=NOW + timedelta(seconds=i, milliseconds=5),
            node_receive_at=NOW + timedelta(seconds=i),
            node_response_at=NOW + timedelta(seconds=i, milliseconds=500),  # claims 500ms processing inside a 5ms RTT
        )
        for i in range(5)
    ]
    record = estimate_rtt_clock_calibration(impossible, stream_id=STREAM_ID, source_offset_ms=0, calibrated_at=NOW)
    assert record.state == "insufficient_samples"
    assert record.valid_sample_count == 0


def test_rtt_calibration_node_reported_negative_processing_time_is_malformed() -> None:
    """Nsend before Nrecv -- impossible under a correct clock."""
    batch = [
        RttRoundTrip(
            host_send_at=NOW + timedelta(seconds=i),
            host_receive_at=NOW + timedelta(seconds=i, milliseconds=10),
            node_receive_at=NOW + timedelta(seconds=i, milliseconds=8),
            node_response_at=NOW + timedelta(seconds=i, milliseconds=2),  # sent before it was received
        )
        for i in range(5)
    ]
    record = estimate_rtt_clock_calibration(batch, stream_id=STREAM_ID, source_offset_ms=0, calibrated_at=NOW)
    assert record.state == "insufficient_samples"
    assert record.valid_sample_count == 0


def test_rtt_calibration_record_raises_on_calibrated_state_missing_numbers() -> None:
    with pytest.raises(ValueError):
        RttClockCalibrationRecord(
            stream_id=STREAM_ID, source_offset_ms=0, calibrated_at=NOW, sample_count=5, valid_sample_count=5,
            state="calibrated",
        )


def test_rtt_calibration_record_raises_on_valid_count_exceeding_total() -> None:
    with pytest.raises(ValueError):
        RttClockCalibrationRecord(
            stream_id=STREAM_ID, source_offset_ms=0, calibrated_at=NOW, sample_count=2, valid_sample_count=5,
            state="insufficient_samples",
        )


# --- Epoch selection / clock jump / drift (RTT-bounded) -------------------


def _rtt_calibration(
    offset_ms: float, *, source_offset_ms: int, calibrated_at: datetime, jump: bool = False, uncertainty_ms: float = 20.0,
) -> RttClockCalibrationRecord:
    return RttClockCalibrationRecord(
        stream_id=STREAM_ID, source_offset_ms=source_offset_ms, calibrated_at=calibrated_at,
        sample_count=MINIMUM_RTT_CALIBRATION_SAMPLES, valid_sample_count=MINIMUM_RTT_CALIBRATION_SAMPLES,
        state="calibrated", offset_ms=offset_ms, offset_min_ms=offset_ms - uncertainty_ms,
        offset_max_ms=offset_ms + uncertainty_ms, uncertainty_ms=uncertainty_ms, rtt_ms=2 * uncertainty_ms,
        clock_jump_detected=jump,
    )


def test_active_rtt_calibration_for_offset_selects_the_latest_governing_epoch() -> None:
    early = _rtt_calibration(10.0, source_offset_ms=0, calibrated_at=NOW)
    late = _rtt_calibration(20.0, source_offset_ms=300_000, calibrated_at=NOW + timedelta(minutes=5))
    assert active_rtt_calibration_for_offset([late, early], source_offset_ms=150_000) is early
    assert active_rtt_calibration_for_offset([late, early], source_offset_ms=300_000) is late


def test_active_rtt_calibration_for_offset_honors_clock_jump_boundaries() -> None:
    pre_jump = _rtt_calibration(50.0, source_offset_ms=0, calibrated_at=NOW)
    post_jump = _rtt_calibration(30_050.0, source_offset_ms=300_000, calibrated_at=NOW + timedelta(minutes=5), jump=True)
    assert active_rtt_calibration_for_offset([pre_jump, post_jump], source_offset_ms=100_000) is pre_jump
    assert active_rtt_calibration_for_offset([pre_jump, post_jump], source_offset_ms=300_000) is post_jump


def test_active_rtt_calibration_for_offset_never_selects_insufficient_or_inconsistent_records() -> None:
    insufficient = RttClockCalibrationRecord(
        stream_id=STREAM_ID, source_offset_ms=0, calibrated_at=NOW, sample_count=1, valid_sample_count=1,
        state="insufficient_samples",
    )
    inconsistent = RttClockCalibrationRecord(
        stream_id=STREAM_ID, source_offset_ms=10_000, calibrated_at=NOW + timedelta(seconds=10),
        sample_count=6, valid_sample_count=6, state="inconsistent_samples",
    )
    good = _rtt_calibration(5.0, source_offset_ms=20_000, calibrated_at=NOW + timedelta(seconds=20))
    assert active_rtt_calibration_for_offset([insufficient, inconsistent], source_offset_ms=15_000) is None
    assert active_rtt_calibration_for_offset([insufficient, inconsistent, good], source_offset_ms=20_000) is good


def test_detect_clock_jump_and_compute_drift_are_reused_for_rtt_records() -> None:
    """The shared `_CalibrationSample` protocol (clock_calibration.py's own
    docstring "Composing with the one-way per-frame monitor") -- the exact
    same `detect_clock_jump`/`compute_drift` functions already tested above
    for the one-way estimator apply unchanged to RTT-bounded records."""
    stable_first = _rtt_calibration(500.0, source_offset_ms=0, calibrated_at=NOW)
    stable_second = _rtt_calibration(510.0, source_offset_ms=600_000, calibrated_at=NOW + timedelta(minutes=10))
    assert detect_clock_jump(stable_first, stable_second) is False
    drift = compute_drift(stable_first, stable_second)
    assert drift is not None
    assert drift.offset_delta_ms == pytest.approx(10.0)

    jumped = _rtt_calibration(500.0 + DEFAULT_CLOCK_JUMP_THRESHOLD_MS + 1, source_offset_ms=600_000, calibrated_at=NOW + timedelta(minutes=10))
    assert detect_clock_jump(stable_first, jumped) is True


# --- normalize_capture_time_with_bound ------------------------------------


def test_normalize_capture_time_with_bound_applies_the_full_interval() -> None:
    t0 = NOW
    calibration = _rtt_calibration(2_500.0, source_offset_ms=0, calibrated_at=NOW, uncertainty_ms=30.0)
    result = normalize_capture_time_with_bound(t0, [calibration], source_offset_ms=0)
    assert result.state == "normalized"
    assert result.host_domain_captured_at_estimate == t0 + timedelta(milliseconds=2_500.0)
    assert result.host_domain_captured_at_min == t0 + timedelta(milliseconds=2_470.0)
    assert result.host_domain_captured_at_max == t0 + timedelta(milliseconds=2_530.0)
    assert result.offset_min_ms == pytest.approx(2_470.0)
    assert result.offset_max_ms == pytest.approx(2_530.0)
    assert result.uncertainty_ms == pytest.approx(30.0)


def test_normalize_capture_time_with_bound_direction_is_not_inverted() -> None:
    """A concrete regression against the exact sign-inversion bug this
    milestone's own self-review checklist names ("RTT midpoint treated as
    exact" / a min<->max swap): the *lower* offset bound must map to the
    *earlier* host-domain time, never the reverse."""
    t0 = NOW
    calibration = _rtt_calibration(0.0, source_offset_ms=0, calibrated_at=NOW, uncertainty_ms=100.0)
    result = normalize_capture_time_with_bound(t0, [calibration], source_offset_ms=0)
    assert result.host_domain_captured_at_min < result.host_domain_captured_at_estimate < result.host_domain_captured_at_max


def test_normalize_capture_time_with_bound_no_calibration_never_fabricates_a_value() -> None:
    result = normalize_capture_time_with_bound(NOW, [], source_offset_ms=5_000)
    assert result.state == "no_calibration"
    assert result.host_domain_captured_at_estimate is None
    assert result.host_domain_captured_at_min is None
    assert result.host_domain_captured_at_max is None
    assert result.offset_min_ms is None
    assert result.offset_max_ms is None
