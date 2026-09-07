"""Gate A Measurement Closure v1: focused, hardware-free tests for true
capture-to-visible Visit latency (see
docs/gate-a-measurement-closure-fragmentation-latency-v1-report.md "T0-T5
timeline"). Covers every regression case named in this milestone's own
governing brief §20/§21/§28.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from mockingbird.observation.capture_to_visible_latency import (
    DEFAULT_MAX_PLAUSIBLE_LATENCY_MS,
    build_latency_samples,
    build_latency_summary,
)
from mockingbird.observation.clock_calibration import RttClockCalibrationRecord
from mockingbird.observation.contracts import EMPTY_CONFIDENCE_EVIDENCE
from mockingbird.observation.counterfactual_lineage import ProposalOutcomeRecord, TrackGenerationRecord

STREAM_ID = "stream-a"
BOX = (0.47, 0.58, 0.51, 0.63)
NOW = datetime(2026, 8, 31, 19, 45, 11, tzinfo=UTC)


def test_capture_to_visible_latency_module_has_no_product_repository_import() -> None:
    source = Path("src/mockingbird/observation/capture_to_visible_latency.py").read_text(encoding="utf-8")
    forbidden = ("mockingbird.repository", "mockingbird.storage", "mockingbird.api", "sqlalchemy")
    for token in forbidden:
        assert token not in source, f"capture_to_visible_latency.py must not reference {token}"


def _generation(
    generation_id: str, *, start_captured_at: datetime | None, end_captured_at: datetime | None = None,
    start_ms: int = 0, end_ms: int = 2_000,
) -> TrackGenerationRecord:
    return TrackGenerationRecord(
        generation_id=generation_id, stream_id=STREAM_ID, broad_class="animal",
        track_ids=(f"{generation_id}-track",), start_offset_ms=start_ms, end_offset_ms=end_ms,
        start_bounding_box=BOX, end_bounding_box=BOX, geometry_envelope=BOX, confirmed=True,
        terminal_reason=None, terminal_support_state="weak_detector_supported",
        terminal_bounding_box_source_offset_ms=end_ms, confidence_evidence=EMPTY_CONFIDENCE_EVIDENCE,
        start_captured_at=start_captured_at, end_captured_at=end_captured_at or start_captured_at,
    )


def _outcome(
    proposal_id: str, *, generation_ids: tuple[str, ...], visit_id: str, decided_at: datetime,
    reason: str = "eligible_assembled_proposal", start_ms: int = 0, end_ms: int = 2_000,
) -> ProposalOutcomeRecord:
    return ProposalOutcomeRecord(
        proposal_id=proposal_id, stream_id=STREAM_ID, broad_class="animal", zone_id=None,
        start_offset_ms=start_ms, end_offset_ms=end_ms, constituent_generation_ids=generation_ids,
        constituent_track_ids=tuple(f"{gid}-track" for gid in generation_ids),
        outcome="created", reason=reason, admitted=True, visit_id=visit_id,
        confidence_evidence=None, decided_at=decided_at, decided_at_offset_ms=end_ms,
    )


# --- 1. fast ordinary Visit --------------------------------------------------


def test_fast_ordinary_visit_measures_capture_to_decision_latency() -> None:
    t0 = NOW
    generations = [_generation("gen-1", start_captured_at=t0)]
    decided_at = t0 + timedelta(seconds=8)
    outcomes = [_outcome("p-1", generation_ids=("gen-1",), visit_id="visit-1", decided_at=decided_at)]

    samples = build_latency_samples(outcomes, generations)
    assert len(samples) == 1
    sample = samples[0]
    assert sample.state == "measured"
    assert sample.t0_source == "earliest_constituent_generation_start_captured_at"
    assert sample.t0_captured_at == t0
    assert sample.latency_ms == 8_000.0
    assert sample.is_fallback is False
    assert sample.fallback_position is None


# --- 2. sustained activity / delayed arbitration ----------------------------


def test_sustained_activity_delayed_arbitration_still_measures_correctly() -> None:
    t0 = NOW
    generations = [_generation("gen-1", start_captured_at=t0)]
    decided_at = t0 + timedelta(minutes=6, seconds=30)  # a real, honestly slow resolution
    outcomes = [_outcome("p-1", generation_ids=("gen-1",), visit_id="visit-1", decided_at=decided_at)]

    samples = build_latency_samples(outcomes, generations)
    assert samples[0].state == "measured"
    assert samples[0].latency_ms == 390_000.0


# --- 3. fallback: latency traced from the *admitted* member's own capture --


def test_fallback_latency_uses_the_admitted_members_own_capture_time_not_the_failed_winners() -> None:
    """Directly exercises this milestone's own §21 concern: when fallback
    admits member N, latency must use *that* member's own evidence/capture
    time, never the failed winner's."""
    winner_t0 = NOW  # the higher-ranked member -- fails evidence availability
    fallback_t0 = NOW + timedelta(seconds=45)  # the actually-admitted member -- captured later
    generations = [
        _generation("gen-winner", start_captured_at=winner_t0),
        _generation("gen-fallback", start_captured_at=fallback_t0),
    ]
    decided_at = fallback_t0 + timedelta(seconds=5)
    outcomes = [
        # The winner's own failed attempt -- never admitted, contributes no sample.
        ProposalOutcomeRecord(
            proposal_id="p-winner", stream_id=STREAM_ID, broad_class="animal", zone_id=None,
            start_offset_ms=0, end_offset_ms=1_000, constituent_generation_ids=("gen-winner",),
            constituent_track_ids=("gen-winner-track",), outcome="blocked_missing_evidence",
            reason="reject_no_identification_or_context", admitted=False, visit_id=None,
            confidence_evidence=None, decided_at=winner_t0 + timedelta(seconds=1), decided_at_offset_ms=1_000,
        ),
        _outcome(
            "p-fallback", generation_ids=("gen-fallback",), visit_id="visit-fallback", decided_at=decided_at,
            reason="eligible_assembled_proposal_ambiguous_boundary_arbitration_winner:fallback_position_1",
        ),
    ]

    samples = build_latency_samples(outcomes, generations)
    assert len(samples) == 1  # only the admitted member ever produces a sample
    sample = samples[0]
    assert sample.visit_id == "visit-fallback"
    assert sample.t0_captured_at == fallback_t0
    assert sample.t0_captured_at != winner_t0
    assert sample.is_fallback is True
    assert sample.fallback_position == 1
    assert sample.latency_ms == 5_000.0


# --- 4. stop finalization ----------------------------------------------------


def test_stop_finalized_pending_candidate_measures_latency_from_its_own_true_capture_time() -> None:
    """A proposal that stayed `blocked_continuation_pending` across many
    ticks and was only resolved at session stop must still measure latency
    from its own real first-capture time, not from the stop event."""
    t0 = NOW
    generations = [_generation("gen-1", start_captured_at=t0, start_ms=0, end_ms=500)]
    decided_at = t0 + timedelta(minutes=3)  # resolved only once the session stopped
    outcomes = [
        _outcome(
            "p-1", generation_ids=("gen-1",), visit_id="visit-1", decided_at=decided_at,
            reason="eligible_assembled_proposal", start_ms=0, end_ms=500,
        ),
    ]
    samples = build_latency_samples(outcomes, generations)
    assert samples[0].state == "measured"
    assert samples[0].t0_captured_at == t0
    assert samples[0].latency_ms == 180_000.0


# --- 5. multi-subject: siblings retain their own correct source timestamps -


def test_simultaneous_sibling_visits_each_retain_their_own_correct_capture_time() -> None:
    t0_feeder = NOW
    t0_perch = NOW + timedelta(seconds=2)
    generations = [
        _generation("gen-feeder", start_captured_at=t0_feeder, start_ms=0, end_ms=5_000),
        _generation("gen-perch", start_captured_at=t0_perch, start_ms=2_000, end_ms=6_000),
    ]
    outcomes = [
        _outcome(
            "p-feeder", generation_ids=("gen-feeder",), visit_id="visit-feeder",
            decided_at=t0_feeder + timedelta(seconds=6), start_ms=0, end_ms=5_000,
        ),
        _outcome(
            "p-perch", generation_ids=("gen-perch",), visit_id="visit-perch",
            decided_at=t0_perch + timedelta(seconds=7), start_ms=2_000, end_ms=6_000,
        ),
    ]
    samples = build_latency_samples(outcomes, generations)
    by_visit = {sample.visit_id: sample for sample in samples}
    assert by_visit["visit-feeder"].t0_captured_at == t0_feeder
    assert by_visit["visit-perch"].t0_captured_at == t0_perch
    assert by_visit["visit-feeder"].latency_ms == 6_000.0
    assert by_visit["visit-perch"].latency_ms == 7_000.0


# --- 6. clock-domain safety --------------------------------------------------


def test_missing_capture_time_is_unavailable_never_a_fabricated_number() -> None:
    """A ledger snapshot from before `start_captured_at` existed (v5/v6/v7's
    own preserved data) must report `unavailable_capture_time`, never
    silently compute a bogus/estimated latency."""
    generations = [_generation("gen-1", start_captured_at=None)]
    outcomes = [_outcome("p-1", generation_ids=("gen-1",), visit_id="visit-1", decided_at=NOW)]
    samples = build_latency_samples(outcomes, generations)
    assert samples[0].state == "unavailable_capture_time"
    assert samples[0].latency_ms is None
    assert samples[0].t0_captured_at is None


def test_negative_latency_from_a_corrupted_clock_is_flagged_never_reported_as_real() -> None:
    """A malformed/misconfigured input where `decided_at` precedes its own
    `t0_captured_at` (impossible under a correct clock) must never surface
    as a real negative number -- this milestone's own §18."""
    t0 = NOW
    generations = [_generation("gen-1", start_captured_at=t0)]
    decided_at = t0 - timedelta(seconds=3)  # corrupted input: decision "before" capture
    outcomes = [_outcome("p-1", generation_ids=("gen-1",), visit_id="visit-1", decided_at=decided_at)]
    samples = build_latency_samples(outcomes, generations)
    assert samples[0].state == "invalid_negative"
    assert samples[0].latency_ms is None


def test_implausibly_large_latency_from_a_wall_monotonic_mix_is_flagged() -> None:
    """A gap far beyond any real session (this milestone's own §18
    "impossible multi-hour latency caused by wall/monotonic mix") is
    flagged `implausible`, not silently accepted as a real measurement."""
    t0 = NOW
    generations = [_generation("gen-1", start_captured_at=t0)]
    decided_at = t0 + timedelta(milliseconds=DEFAULT_MAX_PLAUSIBLE_LATENCY_MS + 1)
    outcomes = [_outcome("p-1", generation_ids=("gen-1",), visit_id="visit-1", decided_at=decided_at)]
    samples = build_latency_samples(outcomes, generations)
    assert samples[0].state == "implausible"
    assert samples[0].latency_ms is None


def test_blocked_proposal_never_produces_a_latency_sample() -> None:
    generations = [_generation("gen-1", start_captured_at=NOW)]
    outcomes = [
        ProposalOutcomeRecord(
            proposal_id="p-1", stream_id=STREAM_ID, broad_class="animal", zone_id=None,
            start_offset_ms=0, end_offset_ms=1_000, constituent_generation_ids=("gen-1",),
            constituent_track_ids=("gen-1-track",), outcome="blocked_ambiguous_boundary",
            reason="proposal_boundary_ambiguous_with_adjacent_proposal", admitted=False, visit_id=None,
            confidence_evidence=None, decided_at=NOW, decided_at_offset_ms=1_000,
        ),
    ]
    assert build_latency_samples(outcomes, generations) == ()


# --- summary statistics ------------------------------------------------------


def test_summary_excludes_non_measured_states_from_percentiles_but_still_counts_them() -> None:
    t0 = NOW
    generations = [
        _generation("gen-1", start_captured_at=t0),
        _generation("gen-2", start_captured_at=t0),
        _generation("gen-3", start_captured_at=None),
    ]
    outcomes = [
        _outcome("p-1", generation_ids=("gen-1",), visit_id="visit-1", decided_at=t0 + timedelta(seconds=4)),
        _outcome("p-2", generation_ids=("gen-2",), visit_id="visit-2", decided_at=t0 + timedelta(seconds=10)),
        _outcome("p-3", generation_ids=("gen-3",), visit_id="visit-3", decided_at=t0 + timedelta(seconds=99)),
    ]
    samples = build_latency_samples(outcomes, generations)
    summary = build_latency_summary(samples)
    assert summary.sample_count == 3
    assert summary.measured_count == 2
    assert summary.unavailable_capture_time_count == 1
    assert summary.invalid_negative_count == 0
    assert summary.implausible_count == 0
    assert summary.median_ms == 7_000.0
    assert summary.max_ms == 10_000.0
    assert summary.mean_ms == 7_000.0


# --- Camera Node <-> Host RTT-Bounded Clock Calibration v1 ------------------
#
# Every test above exercises `clock_calibration_required=False` (the
# default) -- a same-clock-domain source (RTSP/local/USB/replay), where
# `t0_captured_at` is already Host-compatible and no mapping is needed. The
# tests below exercise `clock_calibration_required=True` -- a real Camera
# Node in the loop -- see this module's own docstring "Camera Node <-> Host
# RTT-Bounded Clock Calibration v1" and docs/camera-node-host-rtt-bounded
# -clock-calibration-v1-report.md. `_rtt_calibration`'s own `offset_ms`/
# `uncertainty_ms` parameters produce a symmetric interval
# (`offset_min_ms = offset_ms - uncertainty_ms`, `offset_max_ms = offset_ms
# + uncertainty_ms`) matching exactly how `clock_calibration.
# estimate_rtt_clock_calibration` itself derives `offset_ms` as the
# interval's own midpoint -- so every numeric assertion below that predates
# this milestone (`t0_captured_at_normalized`, `clock_offset_ms`, `latency_
# ms`) remains valid unchanged; only the calibration record's own *type*
# changed (the one-way estimator can never supply a defensible bound -- see
# `build_latency_samples`'s own docstring).


def _rtt_calibration(
    offset_ms: float, *, source_offset_ms: int, calibrated_at: datetime, uncertainty_ms: float = 20.0,
    jump: bool = False,
) -> RttClockCalibrationRecord:
    return RttClockCalibrationRecord(
        stream_id=STREAM_ID, source_offset_ms=source_offset_ms, calibrated_at=calibrated_at,
        sample_count=5, valid_sample_count=5, state="calibrated", offset_ms=offset_ms,
        offset_min_ms=offset_ms - uncertainty_ms, offset_max_ms=offset_ms + uncertainty_ms,
        uncertainty_ms=uncertainty_ms, rtt_ms=2 * uncertainty_ms, clock_jump_detected=jump,
    )


def test_cross_domain_valid_calibration_produces_measured_latency_from_normalized_t0() -> None:
    t0 = NOW
    generations = [_generation("gen-1", start_captured_at=t0, start_ms=0, end_ms=2_000)]
    decided_at = t0 + timedelta(seconds=12)
    outcomes = [_outcome("p-1", generation_ids=("gen-1",), visit_id="visit-1", decided_at=decided_at)]
    calibrations = [_rtt_calibration(2_000.0, source_offset_ms=0, calibrated_at=t0, uncertainty_ms=20.0)]

    samples = build_latency_samples(
        outcomes, generations, rtt_calibrations=calibrations, clock_calibration_required=True,
    )
    sample = samples[0]
    assert sample.clock_calibration_state == "normalized"
    assert sample.t0_captured_at == t0  # raw value preserved unchanged
    assert sample.t0_captured_at_normalized == t0 + timedelta(seconds=2)
    assert sample.clock_offset_ms == pytest.approx(2_000.0)
    assert sample.clock_uncertainty_ms == pytest.approx(20.0)
    assert sample.state == "measured"
    assert sample.latency_ms == pytest.approx(10_000.0)  # 12s raw gap minus the 2s offset
    # Camera Node <-> Host RTT-Bounded Clock Calibration v1: the full
    # interval, never collapsed into the point estimate alone (this
    # milestone's own explicit §21 "do not collapse the interval into a
    # false single exact number").
    assert sample.clock_offset_min_ms == pytest.approx(1_980.0)
    assert sample.clock_offset_max_ms == pytest.approx(2_020.0)
    assert sample.t0_captured_at_normalized_min == t0 + timedelta(milliseconds=1_980.0)
    assert sample.t0_captured_at_normalized_max == t0 + timedelta(milliseconds=2_020.0)
    # The inversion: the earliest possible t0 (offset_min) yields the
    # *largest* possible latency, and vice versa (see `_resolve_latency`'s
    # own docstring) -- a concrete end-to-end regression against a
    # min/max sign-swap bug, not only the isolated clock_calibration.py
    # unit test.
    assert sample.latency_max_ms == pytest.approx(sample.latency_ms + 20.0)
    assert sample.latency_min_ms == pytest.approx(sample.latency_ms - 20.0)


def test_cross_domain_missing_calibration_is_invalid_clock_mapping_never_a_silent_subtraction() -> None:
    """This milestone's own §7/§11: a required mapping that does not exist
    must reject the sample, never silently fall back to raw subtraction."""
    t0 = NOW
    generations = [_generation("gen-1", start_captured_at=t0)]
    outcomes = [_outcome("p-1", generation_ids=("gen-1",), visit_id="visit-1", decided_at=t0 + timedelta(seconds=8))]

    samples = build_latency_samples(outcomes, generations, rtt_calibrations=(), clock_calibration_required=True)
    sample = samples[0]
    assert sample.clock_calibration_state == "no_calibration"
    assert sample.state == "invalid_clock_mapping"
    assert sample.latency_ms is None
    assert sample.latency_min_ms is None
    assert sample.latency_max_ms is None
    assert sample.t0_captured_at_normalized is None
    # The raw fact is still preserved for audit -- only the derived latency
    # number is withheld.
    assert sample.t0_captured_at == t0


def test_cross_domain_calibration_that_does_not_cover_this_t0_offset_is_also_invalid_clock_mapping() -> None:
    """A calibration exists for this stream, but only *after* this
    particular t0's own offset -- never extrapolated backward."""
    t0 = NOW
    generations = [_generation("gen-1", start_captured_at=t0, start_ms=0, end_ms=1_000)]
    outcomes = [
        _outcome("p-1", generation_ids=("gen-1",), visit_id="visit-1", decided_at=t0 + timedelta(seconds=5),
                  start_ms=0, end_ms=1_000),
    ]
    calibrations = [_rtt_calibration(500.0, source_offset_ms=50_000, calibrated_at=t0 + timedelta(seconds=50))]

    samples = build_latency_samples(
        outcomes, generations, rtt_calibrations=calibrations, clock_calibration_required=True,
    )
    assert samples[0].state == "invalid_clock_mapping"


def test_cross_domain_wide_uncertainty_still_measures_honestly_never_falsely_precise() -> None:
    """A deliberately poor (high-RTT-shaped) calibration -- this milestone's
    own §28 -- still produces a `measured` sample, but with a wide, honest
    interval, never a falsely precise point-only result."""
    t0 = NOW
    generations = [_generation("gen-1", start_captured_at=t0, start_ms=0, end_ms=1_000)]
    decided_at = t0 + timedelta(seconds=30)
    outcomes = [_outcome("p-1", generation_ids=("gen-1",), visit_id="visit-1", decided_at=decided_at)]
    calibrations = [_rtt_calibration(1_000.0, source_offset_ms=0, calibrated_at=t0, uncertainty_ms=4_000.0)]

    samples = build_latency_samples(
        outcomes, generations, rtt_calibrations=calibrations, clock_calibration_required=True,
    )
    sample = samples[0]
    assert sample.state == "measured"
    assert sample.latency_ms == pytest.approx(29_000.0)
    assert sample.latency_max_ms == pytest.approx(33_000.0)
    assert sample.latency_min_ms == pytest.approx(25_000.0)
    assert (sample.latency_max_ms - sample.latency_min_ms) == pytest.approx(8_000.0)


def test_cross_domain_impossible_interval_even_the_best_case_is_negative_is_rejected() -> None:
    """This milestone's own §22 "impossible result policy": when even the
    single most charitable (fastest-t0) reading of the interval still
    implies decision-before-capture, the sample is rejected outright --
    never clamped, never a convenient endpoint silently selected."""
    t0 = NOW
    generations = [_generation("gen-1", start_captured_at=t0, start_ms=0, end_ms=1_000)]
    decided_at = t0 - timedelta(seconds=1)  # decision "before" raw capture
    outcomes = [_outcome("p-1", generation_ids=("gen-1",), visit_id="visit-1", decided_at=decided_at)]
    # The most charitable (earliest-t0, largest-latency) reading uses
    # offset_min_ms=-500 -> normalized t0 = t0-500ms; decided_at (t0-1000ms)
    # is still 500ms *before* even that -- impossible under any reading.
    calibrations = [_rtt_calibration(0.0, source_offset_ms=0, calibrated_at=t0, uncertainty_ms=500.0)]

    samples = build_latency_samples(
        outcomes, generations, rtt_calibrations=calibrations, clock_calibration_required=True,
    )
    sample = samples[0]
    assert sample.state == "invalid_negative"
    assert sample.latency_ms is None
    assert sample.latency_min_ms is None
    assert sample.latency_max_ms is None


def test_cross_domain_interval_straddling_zero_is_still_measured_honestly() -> None:
    """Distinguishes "impossible" from "merely uncertain": the interval's
    *upper* bound remains non-negative, so this is a real, if imprecise,
    measurement -- not impossible ordering. The negative lower bound is
    reported honestly, never clamped to zero (this milestone's own explicit
    "do not clamp negatives")."""
    t0 = NOW
    generations = [_generation("gen-1", start_captured_at=t0, start_ms=0, end_ms=1_000)]
    decided_at = t0 + timedelta(milliseconds=100)
    outcomes = [_outcome("p-1", generation_ids=("gen-1",), visit_id="visit-1", decided_at=decided_at)]
    calibrations = [_rtt_calibration(0.0, source_offset_ms=0, calibrated_at=t0, uncertainty_ms=200.0)]

    samples = build_latency_samples(
        outcomes, generations, rtt_calibrations=calibrations, clock_calibration_required=True,
    )
    sample = samples[0]
    assert sample.state == "measured"
    assert sample.latency_min_ms == pytest.approx(-100.0)  # honestly negative, never clamped
    assert sample.latency_max_ms == pytest.approx(300.0)
    assert sample.latency_ms == pytest.approx(100.0)


def test_cross_domain_implausible_even_the_most_charitable_bound_is_too_slow() -> None:
    """The symmetric counterpart to the negative-interval test above: even
    the *latest* possible t0 (the smallest possible latency) still exceeds
    the plausibility ceiling."""
    t0 = NOW
    generations = [_generation("gen-1", start_captured_at=t0, start_ms=0, end_ms=1_000)]
    decided_at = t0 + timedelta(milliseconds=DEFAULT_MAX_PLAUSIBLE_LATENCY_MS + 10_000)
    outcomes = [_outcome("p-1", generation_ids=("gen-1",), visit_id="visit-1", decided_at=decided_at)]
    calibrations = [_rtt_calibration(0.0, source_offset_ms=0, calibrated_at=t0, uncertainty_ms=1_000.0)]

    samples = build_latency_samples(
        outcomes, generations, rtt_calibrations=calibrations, clock_calibration_required=True,
    )
    sample = samples[0]
    assert sample.state == "implausible"
    assert sample.latency_ms is None
    assert sample.latency_min_ms is None
    assert sample.latency_max_ms is None


def test_old_ledger_snapshot_with_no_calibration_metadata_degrades_gracefully_not_a_crash() -> None:
    """Compatibility (this milestone's own §13/§24): a saved ledger
    snapshot from before Camera Node -> Host Clock Normalization v1 existed
    carries no `clock_calibrations` at all. Replaying it with
    `clock_calibration_required=True` (a caller that knows this was a real
    Camera Node session) must not crash -- it honestly reports every sample
    unavailable for true latency, exactly matching how v6/v7's own replayed
    ledgers already honestly report `unavailable_capture_time` for missing
    `start_captured_at` (see Gate A Measurement Closure v1)."""
    generations = [_generation(f"gen-{i}", start_captured_at=NOW + timedelta(seconds=i)) for i in range(3)]
    outcomes = [
        _outcome(f"p-{i}", generation_ids=(f"gen-{i}",), visit_id=f"visit-{i}", decided_at=NOW + timedelta(seconds=i + 10))
        for i in range(3)
    ]
    samples = build_latency_samples(outcomes, generations, clock_calibration_required=True)
    assert len(samples) == 3
    assert all(sample.state == "invalid_clock_mapping" for sample in samples)
    summary = build_latency_summary(samples)
    assert summary.invalid_clock_mapping_count == 3
    assert summary.measured_count == 0


def test_fallback_latency_after_clock_normalization_uses_the_admitted_members_own_capture_time_not_the_failed_winners() -> None:
    """This milestone's own §16 regression: canonical winner fails, fallback
    member succeeds, winner and fallback have different capture timestamps
    *and* fall in different clock-calibration epochs (a jump separates
    them) -- normalized latency must use the fallback member's own capture
    time *and* its own governing calibration, never the winner's. If the
    implementation ever selected calibration by the winner's own offset
    instead of the admitted member's, this test's asserted latency value
    would be wrong (18s, computed from the pre-jump epoch), not the correct
    11s from the fallback's own post-jump epoch."""
    winner_t0 = NOW
    fallback_t0 = NOW + timedelta(seconds=45)
    generations = [
        _generation("gen-winner", start_captured_at=winner_t0, start_ms=0, end_ms=1_000),
        _generation("gen-fallback", start_captured_at=fallback_t0, start_ms=45_000, end_ms=46_000),
    ]
    decided_at = fallback_t0 + timedelta(seconds=20)
    outcomes = [
        ProposalOutcomeRecord(
            proposal_id="p-winner", stream_id=STREAM_ID, broad_class="animal", zone_id=None,
            start_offset_ms=0, end_offset_ms=1_000, constituent_generation_ids=("gen-winner",),
            constituent_track_ids=("gen-winner-track",), outcome="blocked_missing_evidence",
            reason="reject_no_identification_or_context", admitted=False, visit_id=None,
            confidence_evidence=None, decided_at=winner_t0 + timedelta(seconds=1), decided_at_offset_ms=1_000,
        ),
        _outcome(
            "p-fallback", generation_ids=("gen-fallback",), visit_id="visit-fallback", decided_at=decided_at,
            reason="eligible_assembled_proposal_ambiguous_boundary_arbitration_winner:fallback_position_1",
            start_ms=45_000, end_ms=46_000,
        ),
    ]
    # A clock jump between the winner's own epoch (offset 0) and the
    # fallback's own epoch (offset 45_000) -- large enough that using the
    # wrong epoch produces a materially different, wrong latency.
    calibrations = [
        _rtt_calibration(1_000.0, source_offset_ms=0, calibrated_at=winner_t0),
        _rtt_calibration(9_000.0, source_offset_ms=30_000, calibrated_at=winner_t0 + timedelta(seconds=30), jump=True),
    ]

    samples = build_latency_samples(
        outcomes, generations, rtt_calibrations=calibrations, clock_calibration_required=True,
    )
    assert len(samples) == 1  # only the admitted member ever produces a sample
    sample = samples[0]
    assert sample.visit_id == "visit-fallback"
    assert sample.t0_captured_at == fallback_t0
    assert sample.clock_offset_ms == pytest.approx(9_000.0)  # the fallback's own (post-jump) epoch, not the winner's 1_000.0
    assert sample.t0_captured_at_normalized == fallback_t0 + timedelta(seconds=9)
    assert sample.state == "measured"
    assert sample.latency_ms == pytest.approx(11_000.0)
    # This milestone's own explicit §24 "produces the fallback member's
    # latency interval" -- not only its point estimate. The fallback's own
    # post-jump calibration carries the default uncertainty_ms=20.0 (see
    # `_rtt_calibration`); a bug that picked the winner's own epoch instead
    # would produce a materially different interval too (centered on 18s),
    # not merely a different point estimate.
    assert sample.clock_offset_min_ms == pytest.approx(8_980.0)
    assert sample.clock_offset_max_ms == pytest.approx(9_020.0)
    assert sample.latency_max_ms == pytest.approx(11_020.0)
    assert sample.latency_min_ms == pytest.approx(10_980.0)


def test_summary_fallback_measured_count_is_a_subset_of_measured_never_a_lesser_calibration_state() -> None:
    """Field Acceptance Tooling Correctness & Preflight Closure v1
    (governing brief §7): `fallback_measured_count` is a strict *subset*
    accounting of `measured_count` -- an admitted ambiguous-boundary
    -arbitration fallback member, never a fallback/approximate timestamp
    of its own. Proven at the `LatencySummary` level (not merely per
    -sample, see `test_fallback_latency_after_clock_normalization_...`
    above): one ordinary and one fallback-admitted sample, both under real
    RTT-bounded clock calibration, must both count as `measured`, only the
    fallback one counts toward `fallback_measured_count`, and the fallback
    one's own `clock_calibration_state` is genuinely `"normalized"` --
    never silently promoted from, or conflated with, some lesser/
    uncalibrated state merely because its *admission* used a fallback
    arbitration path."""

    ordinary_generation = _generation("gen-ordinary", start_captured_at=NOW, start_ms=0, end_ms=1_000)
    fallback_generation = _generation(
        "gen-fallback", start_captured_at=NOW + timedelta(seconds=100), start_ms=100_000, end_ms=101_000,
    )
    ordinary_outcome = _outcome(
        "p-ordinary", generation_ids=("gen-ordinary",), visit_id="visit-ordinary",
        decided_at=NOW + timedelta(seconds=4), start_ms=0, end_ms=1_000,
    )
    fallback_outcome = _outcome(
        "p-fallback", generation_ids=("gen-fallback",), visit_id="visit-fallback",
        decided_at=NOW + timedelta(seconds=120),
        reason="eligible_assembled_proposal_ambiguous_boundary_arbitration_winner:fallback_position_1",
        start_ms=100_000, end_ms=101_000,
    )
    calibrations = [
        _rtt_calibration(1_000.0, source_offset_ms=0, calibrated_at=NOW),
        _rtt_calibration(2_000.0, source_offset_ms=100_000, calibrated_at=NOW + timedelta(seconds=90)),
    ]

    samples = build_latency_samples(
        [ordinary_outcome, fallback_outcome], [ordinary_generation, fallback_generation],
        rtt_calibrations=calibrations, clock_calibration_required=True,
    )
    summary = build_latency_summary(samples)

    assert summary.sample_count == 2
    assert summary.measured_count == 2  # both -- fallback admission is never a reason to exclude a sample
    assert summary.fallback_measured_count == 1  # a strict subset of measured_count, never a separate state

    fallback_sample = next(sample for sample in samples if sample.is_fallback)
    assert fallback_sample.state == "measured"
    assert fallback_sample.clock_calibration_state == "normalized"  # a genuine RTT-bounded anchor, never degraded
    assert fallback_sample.latency_ms is not None


def test_stop_finalized_candidate_still_normalizes_correctly_under_clock_calibration() -> None:
    t0 = NOW
    generations = [_generation("gen-1", start_captured_at=t0, start_ms=0, end_ms=500)]
    decided_at = t0 + timedelta(minutes=3)
    outcomes = [
        _outcome("p-1", generation_ids=("gen-1",), visit_id="visit-1", decided_at=decided_at, start_ms=0, end_ms=500),
    ]
    calibrations = [_rtt_calibration(3_000.0, source_offset_ms=0, calibrated_at=t0)]

    samples = build_latency_samples(
        outcomes, generations, rtt_calibrations=calibrations, clock_calibration_required=True,
    )
    sample = samples[0]
    assert sample.state == "measured"
    assert sample.latency_ms == pytest.approx(177_000.0)  # 180s raw gap minus the 3s offset
    # This milestone's own explicit §25 "latency interval reflects the real
    # wait" -- resolved only at session stop, still carries the full,
    # honest bound, not merely a point estimate.
    assert sample.latency_min_ms == pytest.approx(176_980.0)
    assert sample.latency_max_ms == pytest.approx(177_020.0)


def test_multi_subject_siblings_each_get_their_own_correctly_normalized_capture_time() -> None:
    t0_feeder = NOW
    t0_perch = NOW + timedelta(seconds=2)
    generations = [
        _generation("gen-feeder", start_captured_at=t0_feeder, start_ms=0, end_ms=5_000),
        _generation("gen-perch", start_captured_at=t0_perch, start_ms=2_000, end_ms=6_000),
    ]
    outcomes = [
        _outcome(
            "p-feeder", generation_ids=("gen-feeder",), visit_id="visit-feeder",
            decided_at=t0_feeder + timedelta(seconds=6), start_ms=0, end_ms=5_000,
        ),
        _outcome(
            "p-perch", generation_ids=("gen-perch",), visit_id="visit-perch",
            decided_at=t0_perch + timedelta(seconds=7), start_ms=2_000, end_ms=6_000,
        ),
    ]
    calibrations = [_rtt_calibration(1_000.0, source_offset_ms=0, calibrated_at=t0_feeder)]

    samples = build_latency_samples(
        outcomes, generations, rtt_calibrations=calibrations, clock_calibration_required=True,
    )
    by_visit = {sample.visit_id: sample for sample in samples}
    assert by_visit["visit-feeder"].t0_captured_at_normalized == t0_feeder + timedelta(seconds=1)
    assert by_visit["visit-perch"].t0_captured_at_normalized == t0_perch + timedelta(seconds=1)
    assert by_visit["visit-feeder"].latency_ms == pytest.approx(5_000.0)  # 6s raw minus 1s offset
    assert by_visit["visit-perch"].latency_ms == pytest.approx(6_000.0)  # 7s raw minus 1s offset
    assert all(sample.state == "measured" for sample in by_visit.values())
    # This milestone's own §26 "independent latency samples": each sibling
    # carries its own correctly-shifted interval (both drawn from the same
    # shared stream calibration, per §26's own "same stream calibration
    # where appropriate") -- never a shared or cross-contaminated bound.
    assert by_visit["visit-feeder"].latency_min_ms == pytest.approx(4_980.0)
    assert by_visit["visit-feeder"].latency_max_ms == pytest.approx(5_020.0)
    assert by_visit["visit-perch"].latency_min_ms == pytest.approx(5_980.0)
    assert by_visit["visit-perch"].latency_max_ms == pytest.approx(6_020.0)


def test_same_domain_default_matches_pre_normalization_behavior_exactly() -> None:
    """`clock_calibration_required` defaults to `False` -- an RTSP/local/USB
    source (or any caller that never opts in) gets exactly the pre
    -Camera-Node-Host-Clock-Normalization-v1 behavior, unaffected even when
    calibration data happens to be supplied (never consulted)."""
    t0 = NOW
    generations = [_generation("gen-1", start_captured_at=t0)]
    decided_at = t0 + timedelta(seconds=8)
    outcomes = [_outcome("p-1", generation_ids=("gen-1",), visit_id="visit-1", decided_at=decided_at)]
    calibrations = [_rtt_calibration(2_000.0, source_offset_ms=0, calibrated_at=t0)]

    samples = build_latency_samples(outcomes, generations, rtt_calibrations=calibrations)
    sample = samples[0]
    assert sample.clock_calibration_state == "not_required"
    assert sample.t0_captured_at_normalized == t0
    assert sample.state == "measured"
    assert sample.latency_ms == 8_000.0  # unaffected by the (ignored) calibration data
    assert sample.latency_min_ms == 8_000.0
    assert sample.latency_max_ms == 8_000.0


def test_summary_counts_invalid_clock_mapping_separately_never_merged_with_other_states() -> None:
    t0 = NOW
    generations = [
        _generation("gen-1", start_captured_at=t0),
        _generation("gen-2", start_captured_at=None),
    ]
    outcomes = [
        _outcome("p-1", generation_ids=("gen-1",), visit_id="visit-1", decided_at=t0 + timedelta(seconds=5)),
        _outcome("p-2", generation_ids=("gen-2",), visit_id="visit-2", decided_at=t0 + timedelta(seconds=9)),
    ]
    samples = build_latency_samples(outcomes, generations, clock_calibration_required=True)
    summary = build_latency_summary(samples)
    # gen-1 has a real t0 but no calibration -> invalid_clock_mapping;
    # gen-2 has no t0 at all -> unavailable_capture_time. Distinct counts.
    assert summary.invalid_clock_mapping_count == 1
    assert summary.unavailable_capture_time_count == 1
    assert summary.measured_count == 0
