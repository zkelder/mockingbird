"""Multimodal Observation & Soundscape v1, Phase D: deterministic association
tiering. Pure function calls only -- no repository, no database."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from mockingbird.observation.multimodal_association import (
    AssociationCandidate,
    AssociationConfig,
    classify_taxon_agreement,
    evaluate_temporal_association,
)
from mockingbird.observation.temporal_evidence import event_evidence_interval

BASE = datetime(2026, 8, 22, 10, 0, 0, tzinfo=UTC)


def _interval(start_offset_s: float, end_offset_s: float, *, provenance: str = "visual_event_range"):
    return event_evidence_interval(
        started_at=BASE + timedelta(seconds=start_offset_s),
        ended_at=BASE + timedelta(seconds=end_offset_s),
        clock_provenance=provenance,
    )


def test_single_candidate_within_strict_window_is_associated() -> None:
    subject = _interval(10, 10, provenance="acoustic_event_range")  # acoustic instant at t=10s
    candidates = (AssociationCandidate(visit_id="visit-visual-1", interval=_interval(0, 8)),)  # ends at t=8s, gap=2s

    decisions = evaluate_temporal_association(subject, candidates)

    assert len(decisions) == 1
    assert decisions[0].visit_id == "visit-visual-1"
    assert decisions[0].tier == "associated"
    assert decisions[0].gap_ms == 2_000


def test_single_candidate_within_possible_but_not_strict_window_is_possible() -> None:
    subject = _interval(40, 40, provenance="acoustic_event_range")  # t=40s
    candidates = (AssociationCandidate(visit_id="visit-visual-1", interval=_interval(0, 8)),)  # gap = 32s (>15s strict, <=60s possible)

    decisions = evaluate_temporal_association(subject, candidates)

    assert len(decisions) == 1
    assert decisions[0].tier == "possible"
    assert decisions[0].gap_ms == 32_000


def test_candidate_outside_possible_window_is_dropped_entirely() -> None:
    subject = _interval(500, 500, provenance="acoustic_event_range")  # far away, gap = 492s
    candidates = (AssociationCandidate(visit_id="visit-visual-1", interval=_interval(0, 8)),)

    decisions = evaluate_temporal_association(subject, candidates)

    assert decisions == ()


def test_two_simultaneous_candidates_are_never_associated_only_possible() -> None:
    """Phase H, multi-subject downgrade: two visual siblings both close in
    time to one acoustic detection must never both -- or either -- claim
    the confident 'associated' tier, since the engine cannot honestly tell
    which sibling the sound belongs to."""

    subject = _interval(10, 10, provenance="acoustic_event_range")
    candidates = (
        AssociationCandidate(visit_id="visit-bird-a", interval=_interval(0, 8)),
        AssociationCandidate(visit_id="visit-bird-b", interval=_interval(1, 9)),
    )

    decisions = evaluate_temporal_association(subject, candidates)

    assert {d.visit_id for d in decisions} == {"visit-bird-a", "visit-bird-b"}
    assert all(d.tier == "possible" for d in decisions)


def test_overlapping_intervals_count_as_strict() -> None:
    subject = _interval(5, 9, provenance="acoustic_event_range")
    candidates = (AssociationCandidate(visit_id="visit-visual-1", interval=_interval(0, 8)),)  # overlaps 5-8s

    decisions = evaluate_temporal_association(subject, candidates)

    assert decisions[0].tier == "associated"
    assert decisions[0].overlap_ms == 3_000
    assert decisions[0].gap_ms == 0


def test_evaluate_is_order_independent_which_side_is_subject() -> None:
    """The engine must give the mirror-image answer regardless of which
    modality happens to be the one newly created (see
    ProductRepository._reconcile_multimodal_association_for_event calling
    this both directions)."""

    visual = _interval(0, 8)
    acoustic = _interval(10, 10, provenance="acoustic_event_range")

    forward = evaluate_temporal_association(acoustic, (AssociationCandidate("v1", visual),))
    backward = evaluate_temporal_association(visual, (AssociationCandidate("a1", acoustic),))

    assert forward[0].tier == backward[0].tier
    assert forward[0].gap_ms == backward[0].gap_ms


def test_custom_config_thresholds_are_honored() -> None:
    subject = _interval(20, 20, provenance="acoustic_event_range")
    candidates = (AssociationCandidate(visit_id="visit-visual-1", interval=_interval(0, 8)),)  # gap = 12s

    tight_config = AssociationConfig(strict_window_ms=5_000, possible_window_ms=15_000)
    decisions = evaluate_temporal_association(subject, candidates, config=tight_config)

    assert decisions[0].tier == "possible"  # 12s > 5s strict, but <= 15s possible


def test_classify_taxon_agreement_exact_match() -> None:
    assert classify_taxon_agreement("northern_cardinal", "northern_cardinal") == "agrees"


def test_classify_taxon_agreement_case_and_whitespace_insensitive() -> None:
    assert classify_taxon_agreement("Northern Cardinal", "  northern cardinal  ") == "agrees"


def test_classify_taxon_agreement_different_species_conflicts() -> None:
    assert classify_taxon_agreement("northern_cardinal", "carolina_wren") == "differs"


def test_classify_taxon_agreement_missing_label_is_not_comparable() -> None:
    assert classify_taxon_agreement(None, "northern_cardinal") == "not_comparable"
    assert classify_taxon_agreement("northern_cardinal", "") == "not_comparable"
    assert classify_taxon_agreement(None, None) == "not_comparable"
