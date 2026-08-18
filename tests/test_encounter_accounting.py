"""Hardware-free tests for encounter-level accounting (Admission Recall
Investigation + Conditional Fix v1; see "Ambiguous boundary arbitration" in
docs/tracklet-visit-assembly-contract.md). No product-repository or
database import anywhere in this test file's own import graph --
`encounter_accounting` must stay a pure decision module exactly like every
sibling Stage 6.x/7 module.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from mockingbird.observation.contracts import EMPTY_CONFIDENCE_EVIDENCE
from mockingbird.observation.counterfactual_lineage import ProposalOutcomeRecord, TrackGenerationRecord
from mockingbird.observation.encounter_accounting import (
    STRONG_CONFIDENCE_THRESHOLD,
    build_encounter_funnel_report,
    cluster_encounters,
)

STREAM_ID = "stream-a"
BOX = (0.47, 0.58, 0.51, 0.63)


def _generation(
    generation_id: str,
    *,
    start_ms: int,
    end_ms: int,
    confirmed: bool = True,
    broad_class: str = "animal",
    box: tuple[float, float, float, float] = BOX,
    start_box: tuple[float, float, float, float] | None = None,
    end_box: tuple[float, float, float, float] | None = None,
    max_confidence: float | None = 0.5,
) -> TrackGenerationRecord:
    resolved_start = start_box or box
    resolved_end = end_box or box
    return TrackGenerationRecord(
        generation_id=generation_id,
        stream_id=STREAM_ID,
        broad_class=broad_class,
        track_ids=(f"{generation_id}-track",),
        start_offset_ms=start_ms,
        end_offset_ms=end_ms,
        start_bounding_box=resolved_start,
        end_bounding_box=resolved_end,
        geometry_envelope=(
            min(resolved_start[0], resolved_end[0]), min(resolved_start[1], resolved_end[1]),
            max(resolved_start[2], resolved_end[2]), max(resolved_start[3], resolved_end[3]),
        ),
        confirmed=confirmed,
        terminal_reason="maximum_unsupported_duration",
        terminal_support_state="weak_detector_supported",
        terminal_bounding_box_source_offset_ms=end_ms,
        confidence_evidence=replace(
            EMPTY_CONFIDENCE_EVIDENCE, max_confidence=max_confidence,
            detection_count=1 if max_confidence is not None else 0,
        ),
    )


def _outcome(
    proposal_id: str,
    *,
    generation_ids: tuple[str, ...],
    outcome: str,
    admitted: bool,
    visit_id: str | None,
    start_ms: int = 0,
    end_ms: int = 1000,
) -> ProposalOutcomeRecord:
    return ProposalOutcomeRecord(
        proposal_id=proposal_id,
        stream_id=STREAM_ID,
        broad_class="animal",
        zone_id=None,
        start_offset_ms=start_ms,
        end_offset_ms=end_ms,
        constituent_generation_ids=generation_ids,
        constituent_track_ids=tuple(f"{gid}-track" for gid in generation_ids),
        outcome=outcome,
        reason="test_fixture",
        admitted=admitted,
        visit_id=visit_id,
        confidence_evidence=None,
        decided_at=None,  # type: ignore[arg-type]
        decided_at_offset_ms=end_ms,
    )


# --- Clustering -------------------------------------------------------------


def test_close_compatible_generations_form_one_cluster() -> None:
    a = _generation("gen-a", start_ms=0, end_ms=5_000)
    b = _generation("gen-b", start_ms=6_000, end_ms=9_000)
    clusters = cluster_encounters([a, b])
    assert len(clusters) == 1
    assert clusters[0].generation_ids == ("gen-a", "gen-b")
    assert clusters[0].is_fragmented


def test_generations_beyond_the_ambiguous_gap_form_separate_clusters() -> None:
    a = _generation("gen-a", start_ms=0, end_ms=5_000)
    b = _generation("gen-b", start_ms=5_000 + 45_001, end_ms=5_000 + 45_001 + 3_000)
    clusters = cluster_encounters([a, b])
    assert len(clusters) == 2


def test_spatially_incompatible_generations_form_separate_clusters() -> None:
    a = _generation("gen-a", start_ms=0, end_ms=5_000, end_box=(0.02, 0.02, 0.10, 0.10))
    b = _generation("gen-b", start_ms=6_000, end_ms=9_000, start_box=(0.85, 0.85, 0.95, 0.95))
    clusters = cluster_encounters([a, b])
    assert len(clusters) == 2


def test_different_broad_class_forms_separate_clusters_even_when_close() -> None:
    a = _generation("gen-a", start_ms=0, end_ms=5_000, broad_class="animal")
    b = _generation("gen-b", start_ms=6_000, end_ms=9_000, broad_class="vehicle")
    clusters = cluster_encounters([a, b])
    assert len(clusters) == 2


def test_temporally_overlapping_generations_never_merge() -> None:
    """Two confirmed generations active at once are two simultaneous
    subjects or a tracker artifact -- never one encounter, mirroring
    `classify_boundary`'s own "incompatible" rule exactly."""
    a = _generation("gen-a", start_ms=0, end_ms=5_000)
    b = _generation("gen-b", start_ms=2_000, end_ms=7_000)
    clusters = cluster_encounters([a, b])
    assert len(clusters) == 2


def test_transitive_chain_joins_one_cluster_even_without_a_direct_link() -> None:
    """Deliberate divergence from the assembler's own bounded per-episode
    ambiguity scope (see `cluster_encounters`'s own docstring): A-B
    compatible, B-C compatible, A-C never directly compared (too far apart
    on their own) -- all three still belong to one reconstructed candidate
    encounter, because encounter reconstruction is transitive by design."""
    a = _generation("gen-a", start_ms=0, end_ms=1_000)
    b = _generation("gen-b", start_ms=1_500, end_ms=2_500)
    c = _generation("gen-c", start_ms=3_000, end_ms=4_000)
    clusters = cluster_encounters([c, a, b])  # order-independent
    assert len(clusters) == 1
    assert clusters[0].generation_ids == ("gen-a", "gen-b", "gen-c")


def test_clustering_is_order_independent_and_deterministic() -> None:
    a = _generation("gen-a", start_ms=0, end_ms=5_000)
    b = _generation("gen-b", start_ms=6_000, end_ms=9_000)
    first = cluster_encounters([a, b])
    second = cluster_encounters([b, a])
    assert first == second


# --- Confirmed vs. unconfirmed tracking --------------------------------------


def test_unconfirmed_generation_still_joins_a_confirmed_neighbors_cluster() -> None:
    confirmed = _generation("gen-confirmed", start_ms=0, end_ms=5_000, confirmed=True)
    unconfirmed = _generation("gen-unconfirmed", start_ms=6_000, end_ms=7_000, confirmed=False)
    clusters = cluster_encounters([confirmed, unconfirmed])
    assert len(clusters) == 1
    assert clusters[0].has_confirmed_tracking
    assert clusters[0].confirmed_generation_ids == ("gen-confirmed",)


def test_all_unconfirmed_cluster_never_reaches_confirmed_tracking() -> None:
    only = _generation("gen-lost", start_ms=0, end_ms=1_000, confirmed=False)
    clusters = cluster_encounters([only])
    assert len(clusters) == 1
    assert not clusters[0].has_confirmed_tracking
    assert not clusters[0].has_viable_proposal


# --- Proposal-outcome wiring --------------------------------------------------


def test_proposal_outcomes_populate_cluster_lineage_deduplicated_by_proposal_id() -> None:
    """Mirrors the real field shape this milestone found: the identical
    `proposal_id` re-recorded on several retried ticks (`blocked_
    continuation_pending`) must count once, never once per attempt."""
    gen = _generation("gen-a", start_ms=0, end_ms=5_000)
    repeated = [
        _outcome("visit-episode:p1", generation_ids=("gen-a",), outcome="blocked_continuation_pending", admitted=False, visit_id=None)
        for _ in range(4)
    ] + [_outcome("visit-episode:p1", generation_ids=("gen-a",), outcome="created", admitted=True, visit_id="visit-1")]
    clusters = cluster_encounters([gen], repeated)
    assert len(clusters) == 1
    cluster = clusters[0]
    assert cluster.proposal_ids == ("visit-episode:p1",)
    assert cluster.has_viable_proposal
    assert cluster.has_visit
    assert cluster.admitted_visit_ids == ("visit-1",)


def test_multiple_proposals_for_one_cluster_are_all_retained() -> None:
    """The real ambiguous-pair shape: two confirmed, clustered generations
    each produce their own distinct proposal (the assembler keeps them
    separate); one is admitted, one stays blocked -- both outcomes must be
    visible on the same reconstructed encounter cluster."""
    a = _generation("gen-a", start_ms=0, end_ms=5_000)
    b = _generation("gen-b", start_ms=6_000, end_ms=9_000)
    outcomes = [
        _outcome("visit-episode:p-a", generation_ids=("gen-a",), outcome="created", admitted=True, visit_id="visit-1"),
        _outcome("visit-episode:p-b", generation_ids=("gen-b",), outcome="blocked_ambiguous_boundary", admitted=False, visit_id=None),
    ]
    clusters = cluster_encounters([a, b], outcomes)
    assert len(clusters) == 1
    cluster = clusters[0]
    assert cluster.has_multiple_proposals
    assert set(cluster.proposal_ids) == {"visit-episode:p-a", "visit-episode:p-b"}
    assert cluster.admitted_visit_ids == ("visit-1",)
    assert set(cluster.outcome_reasons) == {"created", "blocked_ambiguous_boundary"}


def test_duplicate_visits_for_one_cluster_are_counted() -> None:
    """The real candidate-004/005 shape this codebase already fixed once
    (Visit Continuity / Provisional Admission Fix v1): if a caller's own
    lineage somehow shows two distinct admitted Visit ids for generations
    that cluster together, that is a directly-measurable duplicate."""
    a = _generation("gen-a", start_ms=0, end_ms=5_000)
    b = _generation("gen-b", start_ms=6_000, end_ms=9_000)
    outcomes = [
        _outcome("visit-episode:p-a", generation_ids=("gen-a",), outcome="created", admitted=True, visit_id="visit-1"),
        _outcome("visit-episode:p-b", generation_ids=("gen-a", "gen-b"), outcome="created", admitted=True, visit_id="visit-2"),
    ]
    clusters = cluster_encounters([a, b], outcomes)
    report = build_encounter_funnel_report(clusters)
    assert report.duplicate_visit_cluster_count == 1


# --- Plausibility tiers -------------------------------------------------------


@pytest.mark.parametrize(
    ("max_confidence", "expected"),
    [
        (None, "insufficient_evidence"),
        (0.8, "strong_confidence"),
        (STRONG_CONFIDENCE_THRESHOLD, "strong_confidence"),
        (0.5, "moderate_confidence"),
        (0.1, "weak_confidence"),
        (0.0, "weak_confidence"),
    ],
)
def test_plausibility_tiers_are_disclosed_not_guessed(max_confidence: float | None, expected: str) -> None:
    gen = _generation("gen-a", start_ms=0, end_ms=1_000, max_confidence=max_confidence)
    clusters = cluster_encounters([gen])
    assert clusters[0].plausibility == expected


# --- Funnel report -------------------------------------------------------------


def test_funnel_report_on_empty_input_is_honestly_insufficient_data() -> None:
    report = build_encounter_funnel_report(())
    assert report.total_encounter_clusters == 0
    assert report.tracking_recall == {"state": "insufficient_data", "value": None}
    assert report.proposal_recall == {"state": "insufficient_data", "value": None}
    assert report.admission_recall == {"state": "insufficient_data", "value": None}


def test_funnel_report_computes_stage_to_stage_recall() -> None:
    detected_only = _generation("gen-lost", start_ms=0, end_ms=1_000, confirmed=False)
    tracked_no_proposal = _generation("gen-tracked", start_ms=50_000, end_ms=51_000, confirmed=True)
    admitted = _generation("gen-admitted", start_ms=100_000, end_ms=101_000, confirmed=True)
    outcomes = [
        _outcome("visit-episode:p-admitted", generation_ids=("gen-admitted",), outcome="created", admitted=True, visit_id="visit-1"),
    ]
    clusters = cluster_encounters([detected_only, tracked_no_proposal, admitted], outcomes)
    report = build_encounter_funnel_report(clusters)
    assert report.total_encounter_clusters == 3
    assert report.clusters_with_confirmed_tracking == 2
    assert report.clusters_with_viable_proposal == 1
    assert report.clusters_with_visit == 1
    assert report.tracking_recall == {"state": "evaluated", "value": pytest.approx(2 / 3)}
    assert report.proposal_recall == {"state": "evaluated", "value": pytest.approx(1 / 2)}
    assert report.admission_recall == {"state": "evaluated", "value": pytest.approx(1 / 1)}


def test_encounter_accounting_module_has_no_product_repository_import() -> None:
    """Structural guard mirroring every sibling Stage 6.x/7 pure module's
    own equivalent test."""
    from pathlib import Path

    source = Path("src/mockingbird/observation/encounter_accounting.py").read_text(encoding="utf-8")
    forbidden = (
        "mockingbird.repository", "mockingbird.storage", "mockingbird.api", "sqlalchemy",
        "import socket", "import requests", "ReviewLabel", "MotionEvidence", "MediaAsset",
    )
    for token in forbidden:
        assert token not in source, f"encounter_accounting.py must not reference {token}"
