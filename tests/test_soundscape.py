"""Multimodal Observation & Soundscape v1, Phase K: pure soundscape-summary
aggregation tests. No database -- every fact is constructed directly."""

from __future__ import annotations

from datetime import UTC, datetime

from mockingbird.analytics.place_activity_report import TaxonFact
from mockingbird.analytics.soundscape import SoundscapeVisitFact, compute_soundscape_summary

PERIOD_START = datetime(2026, 8, 22, 0, 0, tzinfo=UTC)
PERIOD_END = datetime(2026, 8, 23, 0, 0, tzinfo=UTC)

CARDINAL = TaxonFact(label="northern_cardinal", display_name="Northern Cardinal", category="bird", is_species=True)
CHICKADEE = TaxonFact(label="black_capped_chickadee", display_name="Black-capped Chickadee", category="bird", is_species=True)


def _fact(
    visit_id: str, modality: str, hour: int, *, tier: str = "none", taxon: TaxonFact | None = None,
) -> SoundscapeVisitFact:
    return SoundscapeVisitFact(
        visit_id=visit_id, evidence_modality=modality,
        activity_started_at=datetime(2026, 8, 22, hour, 0, tzinfo=UTC),
        multimodal_tier=tier, effective_taxon=taxon,
    )


def test_empty_period_reports_honest_zeros() -> None:
    summary = compute_soundscape_summary((), period_start=PERIOD_START, period_end=PERIOD_END)
    assert summary.acoustic_encounter_count == 0
    assert summary.species_heard == ()
    assert summary.hourly_acoustic_activity == ()
    assert summary.visual_only_count == 0
    assert summary.acoustic_only_count == 0
    assert summary.multimodal_count == 0


def test_species_heard_counts_distinct_acoustic_species() -> None:
    visits = (
        _fact("a1", "acoustic", 9, taxon=CARDINAL),
        _fact("a2", "acoustic", 10, taxon=CARDINAL),
        _fact("a3", "acoustic", 11, taxon=CHICKADEE),
    )
    summary = compute_soundscape_summary(visits, period_start=PERIOD_START, period_end=PERIOD_END)
    by_label = {entry.label: entry for entry in summary.species_heard}
    assert by_label["northern_cardinal"].encounter_count == 2
    assert by_label["black_capped_chickadee"].encounter_count == 1
    assert summary.acoustic_encounter_count == 3


def test_unresolved_acoustic_visit_contributes_no_species_but_counts_as_an_encounter() -> None:
    visits = (_fact("a1", "acoustic", 9, taxon=None),)
    summary = compute_soundscape_summary(visits, period_start=PERIOD_START, period_end=PERIOD_END)
    assert summary.species_heard == ()
    assert summary.acoustic_encounter_count == 1


def test_visual_only_acoustic_only_and_multimodal_breakdown() -> None:
    visits = (
        _fact("v1", "visual", 9, tier="none"),
        _fact("a1", "acoustic", 9, tier="none", taxon=CARDINAL),
        _fact("v2", "visual", 10, tier="associated"),
        _fact("a2", "acoustic", 10, tier="associated", taxon=CARDINAL),
        _fact("v3", "visual", 11, tier="possible"),
        _fact("a3", "acoustic", 11, tier="possible", taxon=CHICKADEE),
    )
    summary = compute_soundscape_summary(visits, period_start=PERIOD_START, period_end=PERIOD_END)
    assert summary.visual_only_count == 1
    assert summary.acoustic_only_count == 1
    assert summary.multimodal_count == 4  # v2, a2, v3, a3 -- each side counts once


def test_hourly_acoustic_activity_buckets_by_hour_and_ignores_visual() -> None:
    visits = (
        _fact("a1", "acoustic", 6, taxon=CARDINAL),
        _fact("a2", "acoustic", 6, taxon=CARDINAL),
        _fact("a3", "acoustic", 18, taxon=CHICKADEE),
        _fact("v1", "visual", 6),
    )
    summary = compute_soundscape_summary(visits, period_start=PERIOD_START, period_end=PERIOD_END)
    by_hour = {entry.hour: entry.encounter_count for entry in summary.hourly_acoustic_activity}
    assert by_hour == {6: 2, 18: 1}


def test_species_heard_sorted_by_count_then_label_deterministically() -> None:
    visits = (
        _fact("a1", "acoustic", 9, taxon=CHICKADEE),
        _fact("a2", "acoustic", 9, taxon=CARDINAL),
        _fact("a3", "acoustic", 9, taxon=CARDINAL),
    )
    summary = compute_soundscape_summary(visits, period_start=PERIOD_START, period_end=PERIOD_END)
    assert [entry.label for entry in summary.species_heard] == ["northern_cardinal", "black_capped_chickadee"]
