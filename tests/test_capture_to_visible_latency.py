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
from mockingbird.observation.clock_calibration import ClockCalibrationRecord
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


# --- Camera Node -> Host Clock Normalization v1 -----------------------------
#
# Every test above exercises `clock_calibration_required=False` (the
# default) -- a same-clock-domain source (RTSP/local/USB/replay), where
# `t0_captured_at` is already Host-compatible and no mapping is needed. The
# tests below exercise `clock_calibration_required=True` -- a real Camera
# Node in the loop -- see this module's own docstring "Camera Node -> Host
# Clock Normalization v1" and docs/camera-node-host-clock-normalization
# -latency-v1-report.md.


def _calibration(
    offset_ms: float, *, source_offset_ms: int, calibrated_at: datetime, uncertainty_ms: float = 20.0,
    jump: bool = False,
) -> ClockCalibrationRecord:
    return ClockCalibrationRecord(
        stream_id=STREAM_ID, source_offset_ms=source_offset_ms, calibrated_at=calibrated_at,
        sample_count=5, state="calibrated", offset_ms=offset_ms, uncertainty_ms=uncertainty_ms,
        min_delta_ms=offset_ms, max_delta_ms=offset_ms + uncertainty_ms, clock_jump_detected=jump,
    )


def test_cross_domain_valid_calibration_produces_measured_latency_from_normalized_t0() -> None:
    t0 = NOW
    generations = [_generation("gen-1", start_captured_at=t0, start_ms=0, end_ms=2_000)]
    decided_at = t0 + timedelta(seconds=12)
    outcomes = [_outcome("p-1", generation_ids=("gen-1",), visit_id="visit-1", decided_at=decided_at)]
    calibrations = [_calibration(2_000.0, source_offset_ms=0, calibrated_at=t0)]

    samples = build_latency_samples(
        outcomes, generations, clock_calibrations=calibrations, clock_calibration_required=True,
    )
    sample = samples[0]
    assert sample.clock_calibration_state == "normalized"
    assert sample.t0_captured_at == t0  # raw value preserved unchanged
    assert sample.t0_captured_at_normalized == t0 + timedelta(seconds=2)
    assert sample.clock_offset_ms == pytest.approx(2_000.0)
    assert sample.clock_uncertainty_ms == pytest.approx(20.0)
    assert sample.state == "measured"
    assert sample.latency_ms == pytest.approx(10_000.0)  # 12s raw gap minus the 2s offset


def test_cross_domain_missing_calibration_is_invalid_clock_mapping_never_a_silent_subtraction() -> None:
    """This milestone's own §7/§11: a required mapping that does not exist
    must reject the sample, never silently fall back to raw subtraction."""
    t0 = NOW
    generations = [_generation("gen-1", start_captured_at=t0)]
    outcomes = [_outcome("p-1", generation_ids=("gen-1",), visit_id="visit-1", decided_at=t0 + timedelta(seconds=8))]

    samples = build_latency_samples(outcomes, generations, clock_calibrations=(), clock_calibration_required=True)
    sample = samples[0]
    assert sample.clock_calibration_state == "no_calibration"
    assert sample.state == "invalid_clock_mapping"
    assert sample.latency_ms is None
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
    calibrations = [_calibration(500.0, source_offset_ms=50_000, calibrated_at=t0 + timedelta(seconds=50))]

    samples = build_latency_samples(
        outcomes, generations, clock_calibrations=calibrations, clock_calibration_required=True,
    )
    assert samples[0].state == "invalid_clock_mapping"


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
        _calibration(1_000.0, source_offset_ms=0, calibrated_at=winner_t0),
        _calibration(9_000.0, source_offset_ms=30_000, calibrated_at=winner_t0 + timedelta(seconds=30), jump=True),
    ]

    samples = build_latency_samples(
        outcomes, generations, clock_calibrations=calibrations, clock_calibration_required=True,
    )
    assert len(samples) == 1  # only the admitted member ever produces a sample
    sample = samples[0]
    assert sample.visit_id == "visit-fallback"
    assert sample.t0_captured_at == fallback_t0
    assert sample.clock_offset_ms == pytest.approx(9_000.0)  # the fallback's own (post-jump) epoch, not the winner's 1_000.0
    assert sample.t0_captured_at_normalized == fallback_t0 + timedelta(seconds=9)
    assert sample.state == "measured"
    assert sample.latency_ms == pytest.approx(11_000.0)


def test_stop_finalized_candidate_still_normalizes_correctly_under_clock_calibration() -> None:
    t0 = NOW
    generations = [_generation("gen-1", start_captured_at=t0, start_ms=0, end_ms=500)]
    decided_at = t0 + timedelta(minutes=3)
    outcomes = [
        _outcome("p-1", generation_ids=("gen-1",), visit_id="visit-1", decided_at=decided_at, start_ms=0, end_ms=500),
    ]
    calibrations = [_calibration(3_000.0, source_offset_ms=0, calibrated_at=t0)]

    samples = build_latency_samples(
        outcomes, generations, clock_calibrations=calibrations, clock_calibration_required=True,
    )
    assert samples[0].state == "measured"
    assert samples[0].latency_ms == pytest.approx(177_000.0)  # 180s raw gap minus the 3s offset


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
    calibrations = [_calibration(1_000.0, source_offset_ms=0, calibrated_at=t0_feeder)]

    samples = build_latency_samples(
        outcomes, generations, clock_calibrations=calibrations, clock_calibration_required=True,
    )
    by_visit = {sample.visit_id: sample for sample in samples}
    assert by_visit["visit-feeder"].t0_captured_at_normalized == t0_feeder + timedelta(seconds=1)
    assert by_visit["visit-perch"].t0_captured_at_normalized == t0_perch + timedelta(seconds=1)
    assert by_visit["visit-feeder"].latency_ms == pytest.approx(5_000.0)  # 6s raw minus 1s offset
    assert by_visit["visit-perch"].latency_ms == pytest.approx(6_000.0)  # 7s raw minus 1s offset
    assert all(sample.state == "measured" for sample in by_visit.values())


def test_same_domain_default_matches_pre_normalization_behavior_exactly() -> None:
    """`clock_calibration_required` defaults to `False` -- an RTSP/local/USB
    source (or any caller that never opts in) gets exactly the pre
    -Camera-Node-Host-Clock-Normalization-v1 behavior, unaffected even when
    calibration data happens to be supplied (never consulted)."""
    t0 = NOW
    generations = [_generation("gen-1", start_captured_at=t0)]
    decided_at = t0 + timedelta(seconds=8)
    outcomes = [_outcome("p-1", generation_ids=("gen-1",), visit_id="visit-1", decided_at=decided_at)]
    calibrations = [_calibration(2_000.0, source_offset_ms=0, calibrated_at=t0)]

    samples = build_latency_samples(outcomes, generations, clock_calibrations=calibrations)
    sample = samples[0]
    assert sample.clock_calibration_state == "not_required"
    assert sample.t0_captured_at_normalized == t0
    assert sample.state == "measured"
    assert sample.latency_ms == 8_000.0  # unaffected by the (ignored) calibration data


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
