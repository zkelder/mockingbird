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
    MINIMUM_CALIBRATION_SAMPLES,
    ClockCalibrationRecord,
    active_calibration_for_offset,
    compute_drift,
    detect_clock_jump,
    estimate_clock_calibration,
    normalize_capture_time,
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
