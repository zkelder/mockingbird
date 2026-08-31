"""Gate A Measurement Closure v1: focused, hardware-free tests for true
capture-to-visible Visit latency (see
docs/gate-a-measurement-closure-fragmentation-latency-v1-report.md "T0-T5
timeline"). Covers every regression case named in this milestone's own
governing brief §20/§21/§28.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from mockingbird.observation.capture_to_visible_latency import (
    DEFAULT_MAX_PLAUSIBLE_LATENCY_MS,
    build_latency_samples,
    build_latency_summary,
)
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
