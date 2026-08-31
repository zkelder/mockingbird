"""Gate A Measurement Closure v1: focused, hardware-free tests for the
fragmentation-accounting review layer (see
docs/gate-a-measurement-closure-fragmentation-latency-v1-report.md
"Fragmentation truth contract"). Covers every regression case named in this
milestone's own governing brief §10, plus the RED/GREEN pair proving the old
"raw cluster signal == fragmentation/duplicate count" reading is wrong for
sustained activity, exactly as Representative Daylight Gate A Field
Acceptance v7 disclosed.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from mockingbird.observation.contracts import EMPTY_CONFIDENCE_EVIDENCE
from mockingbird.observation.counterfactual_lineage import ProposalOutcomeRecord, TrackGenerationRecord
from mockingbird.observation.encounter_accounting import build_encounter_funnel_report, cluster_encounters
from mockingbird.observation.fragmentation_accounting import (
    DenominatorUnit,
    ReviewerDisposition,
    apply_reviewer_dispositions,
    build_denominator_units,
    build_fragmentation_accounting_report,
    reviewer_denominator_unit,
)

STREAM_ID = "stream-a"
FEEDER_BOX = (0.47, 0.58, 0.51, 0.63)
PERCH_BOX = (0.05, 0.05, 0.15, 0.15)  # geometrically incompatible with FEEDER_BOX


def test_fragmentation_accounting_module_has_no_product_repository_import() -> None:
    source = Path("src/mockingbird/observation/fragmentation_accounting.py").read_text(encoding="utf-8")
    forbidden = ("mockingbird.repository", "mockingbird.storage", "mockingbird.api", "sqlalchemy")
    for token in forbidden:
        assert token not in source, f"fragmentation_accounting.py must not reference {token}"


# --- fixtures (mirrors tests/test_encounter_accounting.py's own convention) -


def _generation(
    generation_id: str, *, start_ms: int, end_ms: int, box: tuple[float, float, float, float] = FEEDER_BOX,
) -> TrackGenerationRecord:
    return TrackGenerationRecord(
        generation_id=generation_id, stream_id=STREAM_ID, broad_class="animal",
        track_ids=(f"{generation_id}-track",), start_offset_ms=start_ms, end_offset_ms=end_ms,
        start_bounding_box=box, end_bounding_box=box, geometry_envelope=box, confirmed=True,
        terminal_reason="maximum_unsupported_duration", terminal_support_state="weak_detector_supported",
        terminal_bounding_box_source_offset_ms=end_ms,
        confidence_evidence=replace(EMPTY_CONFIDENCE_EVIDENCE, max_confidence=0.6, detection_count=1),
    )


def _outcome(
    proposal_id: str, *, generation_ids: tuple[str, ...], visit_id: str | None, start_ms: int, end_ms: int,
) -> ProposalOutcomeRecord:
    return ProposalOutcomeRecord(
        proposal_id=proposal_id, stream_id=STREAM_ID, broad_class="animal", zone_id=None,
        start_offset_ms=start_ms, end_offset_ms=end_ms, constituent_generation_ids=generation_ids,
        constituent_track_ids=tuple(f"{gid}-track" for gid in generation_ids),
        outcome="created" if visit_id else "blocked_missing_evidence",
        reason="test_fixture", admitted=bool(visit_id), visit_id=visit_id,
        confidence_evidence=None, decided_at=None, decided_at_offset_ms=end_ms,  # type: ignore[arg-type]
    )


def _units_for(
    generations: list[TrackGenerationRecord], outcomes: list[ProposalOutcomeRecord],
    *, visit_event_ids: dict[str, str] | None = None,
) -> tuple[DenominatorUnit, ...]:
    clusters = cluster_encounters(generations, outcomes)
    return build_denominator_units(clusters, outcomes, visit_event_ids=visit_event_ids)


# --- 1. sparse: one clear encounter, one Visit -> not fragmented -----------


def test_sparse_single_encounter_is_correctly_represented_with_no_review_needed() -> None:
    generations = [_generation("gen-1", start_ms=0, end_ms=2_000)]
    outcomes = [_outcome("p-1", generation_ids=("gen-1",), visit_id="visit-1", start_ms=0, end_ms=2_000)]
    units = _units_for(generations, outcomes)

    assert len(units) == 1
    assert units[0].disposition == "correctly_represented"
    assert units[0].denominator_confidence == "confident"
    report = build_fragmentation_accounting_report(units)
    assert report.fragmentation_rate == {"state": "evaluated", "value": 0.0}


# --- 2. sparse fragmented: one clear encounter -> two unnecessary Visits ---


def test_sparse_fragmented_pair_is_ambiguous_until_a_reviewer_confirms_fragmentation() -> None:
    generations = [
        _generation("gen-1a", start_ms=0, end_ms=2_000),
        _generation("gen-1b", start_ms=2_010, end_ms=4_000),  # 10ms gap -- same real bird, artificially split
    ]
    outcomes = [
        _outcome("p-1a", generation_ids=("gen-1a",), visit_id="visit-1a", start_ms=0, end_ms=2_000),
        _outcome("p-1b", generation_ids=("gen-1b",), visit_id="visit-1b", start_ms=2_010, end_ms=4_000),
    ]
    units = _units_for(generations, outcomes)
    assert len(units) == 1  # one cluster -- tight gap, compatible geometry, same class
    unit = units[0]
    assert unit.disposition == "ambiguous"
    assert unit.denominator_confidence == "ambiguous"
    assert unit.auto_signals["reason"] == "multiple_admitted_visits_no_shared_evidence_no_confident_sibling_signal"

    reviewed = apply_reviewer_dispositions(
        units,
        [ReviewerDisposition(
            unit.denominator_unit_id, "fragmented",
            reviewer_note="Full-resolution recorder frames show one continuous bird, never leaving frame.",
        )],
    )
    assert reviewed[0].disposition == "fragmented"
    assert reviewed[0].denominator_confidence == "reviewed"
    report = build_fragmentation_accounting_report(reviewed)
    assert report.fragmentation_rate == {"state": "evaluated", "value": 1.0}


# --- 3. two genuine sequential encounters, large separation -> not fragmented


def test_two_sequential_encounters_with_large_separation_are_each_correctly_represented() -> None:
    generations = [
        _generation("gen-1", start_ms=0, end_ms=2_000),
        _generation("gen-2", start_ms=200_000, end_ms=202_000),  # >> ambiguous_gap_ms (45s): separate clusters
    ]
    outcomes = [
        _outcome("p-1", generation_ids=("gen-1",), visit_id="visit-1", start_ms=0, end_ms=2_000),
        _outcome("p-2", generation_ids=("gen-2",), visit_id="visit-2", start_ms=200_000, end_ms=202_000),
    ]
    units = _units_for(generations, outcomes)
    assert len(units) == 2  # never chained into one cluster -- no review needed at all
    assert all(unit.disposition == "correctly_represented" for unit in units)
    assert all(unit.denominator_confidence == "confident" for unit in units)


# --- 4/5. sustained activity: RED (naive signal) then GREEN (corrected) ----


def _sustained_feeder_fixture() -> tuple[list[TrackGenerationRecord], list[ProposalOutcomeRecord]]:
    """Four genuinely separate real House-Finch-style visits at one feeder,
    each ~20s apart (well inside `ambiguous_gap_ms`), spanning ~100s total
    -- the same shape v7's own real 26.9-minute/65-proposal mega-cluster
    disclosed, scaled down for a fast deterministic test. Disjoint
    constituent evidence throughout (four genuinely different visits, never
    the same tracker evidence admitted twice)."""
    generations = [_generation(f"gen-{i}", start_ms=i * 25_000, end_ms=i * 25_000 + 3_000) for i in range(4)]
    outcomes = [
        _outcome(
            f"p-{i}", generation_ids=(f"gen-{i}",), visit_id=f"visit-{i}",
            start_ms=i * 25_000, end_ms=i * 25_000 + 3_000,
        )
        for i in range(4)
    ]
    return generations, outcomes


def test_red_naive_duplicate_cluster_signal_wrongly_reads_as_a_defect_for_sustained_activity() -> None:
    """RED: taken at face value, the *raw* `cluster_encounters` funnel
    signal (`duplicate_visit_cluster_count`) fires on this fixture -- one
    cluster, four admitted Visits -- exactly the semantically wrong
    "fragmentation/duplication defect" reading Representative Daylight Gate
    A Field Acceptance v7 disclosed and corrected (see this test file's own
    module docstring)."""
    generations, outcomes = _sustained_feeder_fixture()
    clusters = cluster_encounters(generations, outcomes)
    assert len(clusters) == 1  # the mega-cluster shape
    report = build_encounter_funnel_report(clusters)
    assert report.duplicate_visit_cluster_count == 1
    assert report.admitted_visit_count == 4
    # This is the exact wrong inference the old, uncorrected reading
    # invites: "one duplicate-flagged cluster" naively read as "a
    # fragmentation/duplication defect occurred" -- ground truth here is
    # four genuinely separate, correctly-represented encounters.


def test_green_corrected_accounting_marks_sustained_activity_ambiguous_not_fragmented_or_duplicate() -> None:
    """GREEN: the corrected accounting never promotes the raw multi-Visit
    cluster signal straight to `fragmented`/`duplicate` -- no shared
    tracker evidence exists between any pair, so it is honestly
    `ambiguous`, deferring to review exactly as v7's own report did
    ("does not have a single correct granularity"), never silently
    resolved either way."""
    generations, outcomes = _sustained_feeder_fixture()
    units = _units_for(generations, outcomes)
    assert len(units) == 1
    assert units[0].disposition == "ambiguous"
    assert units[0].auto_signals["reason"] != "shared_constituent_generation_ids"

    # A reviewer confirms these are genuinely four separate real visits
    # (v7's own actual finding for its real equivalent scene) -- excluded
    # from the fragmentation numerator, not merely "not counted."
    reviewed = apply_reviewer_dispositions(
        units,
        [ReviewerDisposition(
            units[0].denominator_unit_id, "correctly_represented",
            reviewer_note="Recorder frames confirm four distinct House Finch visits, no continuous occupancy.",
        )],
    )
    report = build_fragmentation_accounting_report(reviewed)
    assert report.fragmented_count == 0
    assert report.correctly_represented_count == 1
    assert report.fragmentation_rate == {"state": "evaluated", "value": 0.0}


def test_sustained_over_fragmentation_reviewer_can_confirm_a_real_defect_too() -> None:
    """The mirror image of the above -- the corrected accounting does not
    default to "always innocent" either: when a reviewer genuinely
    confirms one activity unit was split into many unnecessary Visits, that
    is `fragmented`, counted in the rate, same mechanism as case 2 above."""
    generations, outcomes = _sustained_feeder_fixture()
    units = _units_for(generations, outcomes)
    reviewed = apply_reviewer_dispositions(
        units,
        [ReviewerDisposition(
            units[0].denominator_unit_id, "fragmented",
            reviewer_note="Recorder frames show one bird never leaving the feeder across all four Visits.",
        )],
    )
    report = build_fragmentation_accounting_report(reviewed)
    assert report.fragmented_count == 1
    assert report.fragmentation_rate == {"state": "evaluated", "value": 1.0}


# --- 6. simultaneous subjects: sibling Visits -> not fragmentation ---------


def test_simultaneous_siblings_sharing_one_event_are_confidently_correctly_represented() -> None:
    generations = [
        _generation("gen-feeder", start_ms=0, end_ms=5_000, box=FEEDER_BOX),
        _generation("gen-perch", start_ms=2_000, end_ms=6_000, box=PERCH_BOX),  # temporally overlapping
    ]
    outcomes = [
        _outcome("p-feeder", generation_ids=("gen-feeder",), visit_id="visit-feeder", start_ms=0, end_ms=5_000),
        _outcome("p-perch", generation_ids=("gen-perch",), visit_id="visit-perch", start_ms=2_000, end_ms=6_000),
    ]
    # Overlapping generations never join one cluster_encounters() cluster in
    # the first place (temporal-overlap exclusion) -- each Visit seeds its
    # own unit. The Event-sharing signal is what a caller supplies from a
    # Visits export to confidently mark this pattern, not detect it via
    # `cluster_encounters` alone.
    units = _units_for(
        generations, outcomes,
        visit_event_ids={"visit-feeder": "event-shared", "visit-perch": "event-shared"},
    )
    assert len(units) == 2
    assert all(unit.disposition == "correctly_represented" for unit in units)
    assert all(unit.denominator_confidence == "confident" for unit in units)


def test_different_event_ids_never_falsely_trigger_the_confident_sibling_signal() -> None:
    """The confident concurrent-siblings auto-classification requires every
    admitted Visit in the cluster to share *one* Event id -- distinct
    Event ids present (a caller's Visits export honestly shows these were
    never assembled as siblings) must fall back to `ambiguous`, exactly
    like no Event info being supplied at all, never a false
    `correctly_represented` or `fragmented`."""
    generations = [
        _generation("gen-a", start_ms=0, end_ms=2_000),
        _generation("gen-b", start_ms=2_500, end_ms=4_500),
    ]
    outcomes = [
        _outcome("p-a", generation_ids=("gen-a",), visit_id="visit-a", start_ms=0, end_ms=2_000),
        _outcome("p-b", generation_ids=("gen-b",), visit_id="visit-b", start_ms=2_500, end_ms=4_500),
    ]
    units = _units_for(
        generations, outcomes, visit_event_ids={"visit-a": "event-1", "visit-b": "event-2"},
    )
    assert len(units) == 1
    assert units[0].disposition == "ambiguous"


# --- 7. duplicate: same product representation emitted twice ---------------


def test_duplicate_shared_generation_evidence_is_confident_and_distinct_from_fragmented() -> None:
    generations = [_generation("gen-1", start_ms=0, end_ms=2_000)]
    outcomes = [
        _outcome("p-1", generation_ids=("gen-1",), visit_id="visit-1", start_ms=0, end_ms=2_000),
        # A second admission built from the *same* underlying tracker
        # evidence -- the genuine duplicate signature, never fragmentation.
        _outcome("p-1-retry", generation_ids=("gen-1",), visit_id="visit-1-retry", start_ms=0, end_ms=2_000),
    ]
    units = _units_for(generations, outcomes)
    assert len(units) == 1
    assert units[0].disposition == "duplicate"
    assert units[0].denominator_confidence == "confident"
    report = build_fragmentation_accounting_report(units)
    # A duplicate must never inflate the fragmentation rate's own numerator
    # or denominator -- distinct concepts, per this milestone's own
    # "Fragmentation principle."
    assert report.duplicate_count == 1
    assert report.fragmented_count == 0
    assert report.fragmentation_rate == {"state": "insufficient_data", "value": None}


# --- 8. ambiguous: review cannot honestly decide -> excluded from the rate -


def test_ambiguous_unit_is_excluded_from_the_fragmentation_rate_denominator() -> None:
    generations, outcomes = _sustained_feeder_fixture()
    units = _units_for(generations, outcomes)
    assert units[0].disposition == "ambiguous"
    report = build_fragmentation_accounting_report(units)
    assert report.ambiguous_count == 1
    assert report.needs_review_unit_ids == (units[0].denominator_unit_id,)
    # Zero confidently/reviewedly assessed units exist -- insufficient_data,
    # never a fabricated 0% or 100%.
    assert report.fragmentation_rate == {"state": "insufficient_data", "value": None}


# --- reviewer-authored units: missed / merged, and override safety ---------


def test_reviewer_denominator_unit_supports_missed_and_requires_a_note() -> None:
    unit = reviewer_denominator_unit(
        "denominator:reviewer-missed-1", start_offset_ms=0, end_offset_ms=3_000, disposition="missed",
        reviewer_note="Recorder frame at 00:42 shows a clear chipmunk the pipeline never proposed at all.",
    )
    assert unit.disposition == "missed"
    assert unit.denominator_confidence == "reviewed"
    with pytest.raises(ValueError):
        DenominatorUnit(
            denominator_unit_id="denominator:bad", start_offset_ms=0, end_offset_ms=1_000,
            admitted_visit_ids=(), disposition="fragmented", denominator_confidence="reviewed", reviewer_note="",
        )


def test_apply_reviewer_dispositions_rejects_an_unknown_unit_id() -> None:
    generations = [_generation("gen-1", start_ms=0, end_ms=2_000)]
    outcomes = [_outcome("p-1", generation_ids=("gen-1",), visit_id="visit-1", start_ms=0, end_ms=2_000)]
    units = _units_for(generations, outcomes)
    with pytest.raises(ValueError):
        apply_reviewer_dispositions(
            units, [ReviewerDisposition("denominator:does-not-exist", "fragmented", reviewer_note="typo'd id")],
        )
