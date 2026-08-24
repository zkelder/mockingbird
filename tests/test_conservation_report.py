"""Pure-module tests for `mockingbird.research.conservation_report` (see
docs/research-conservation-export-contract.md "Conservation report
semantics").
"""

from __future__ import annotations

from datetime import UTC, datetime

from mockingbird.analytics.place_activity_report import (
    TaxonFact,
    VisitFact,
    compute_coverage_summary,
    compute_place_activity_report,
)
from mockingbird.analytics.zone_insights import TimeInterval
from mockingbird.research.acquisition_effort import (
    OfflineAcquisitionEffort,
    RecordedVideoAcquisitionFact,
    compute_offline_acquisition_effort,
)
from mockingbird.research.conservation_report import (
    compute_conservation_report,
    format_occurrence_note,
)

CARDINAL = TaxonFact(label="northern_cardinal", display_name="Northern Cardinal", category="bird", is_species=True)
UNKNOWN_BIRD = TaxonFact(label="unknown_bird", display_name="Unknown Bird", category="unknown", is_species=False)
# Broader Wildlife Maturity v1 (see docs/broader-wildlife-maturity-v1-
# contract.md): this milestone's newly-seeded kind-level (is_species=False)
# mammal taxon, matching the real product taxonomy content exactly.
RACCOON = TaxonFact(label="raccoon", display_name="Raccoon", category="mammal", is_species=False)

PERIOD_START = datetime(2026, 8, 1, tzinfo=UTC)
PERIOD_END = datetime(2026, 8, 8, tzinfo=UTC)


def _visit(day: int, hour: int, taxon: TaxonFact, *, visit_id: str) -> VisitFact:
    return VisitFact(
        visit_id=visit_id,
        zone_id=None,
        zone_name=None,
        activity_started_at=datetime(2026, 8, day, hour, tzinfo=UTC),
        resolution="reviewed",
        confirmed_taxon=taxon,
    )


def _empty_offline_effort() -> OfflineAcquisitionEffort:
    return compute_offline_acquisition_effort()


def test_confirmed_species_reports_distinct_occurrence_days_not_bare_visit_count():
    visits = [
        _visit(1, 7, CARDINAL, visit_id="v1"),
        _visit(1, 8, CARDINAL, visit_id="v2"),  # same day as v1
        _visit(3, 9, CARDINAL, visit_id="v3"),  # a second distinct day
    ]
    report = compute_place_activity_report(visits, period_start_at=PERIOD_START, period_end_at=PERIOD_END)
    conservation = compute_conservation_report(
        report,
        visits=visits,
        offline_acquisition=_empty_offline_effort(),
        live_monitoring_usable_day_count=7,
        confirmed_wildlife_visits_with_evidence_count=3,
    )
    assert len(conservation.confirmed_species) == 1
    record = conservation.confirmed_species[0]
    assert record.confirmed_visit_count == 3
    assert record.occurrence_day_count == 2  # 3 visits, only 2 distinct days
    assert record.occurrence_note == "Northern Cardinal was confirmed on 2 of 7 usable monitored days."


def test_confirmed_unidentified_wildlife_counted_honestly_not_as_a_species():
    visits = [_visit(1, 7, UNKNOWN_BIRD, visit_id="v1")]
    report = compute_place_activity_report(visits, period_start_at=PERIOD_START, period_end_at=PERIOD_END)
    conservation = compute_conservation_report(
        report,
        visits=visits,
        offline_acquisition=_empty_offline_effort(),
        live_monitoring_usable_day_count=7,
        confirmed_wildlife_visits_with_evidence_count=1,
    )
    assert conservation.confirmed_species == []
    assert conservation.confirmed_unidentified_wildlife_visit_count == 1
    assert conservation.reviewed_wildlife_visit_count == 1


def test_scientific_name_is_included_when_available_and_null_when_not():
    visits = [_visit(1, 7, CARDINAL, visit_id="v1")]
    report = compute_place_activity_report(visits, period_start_at=PERIOD_START, period_end_at=PERIOD_END)

    with_name = compute_conservation_report(
        report, visits=visits, offline_acquisition=_empty_offline_effort(),
        live_monitoring_usable_day_count=1, confirmed_wildlife_visits_with_evidence_count=1,
        scientific_names_by_label={"northern_cardinal": "Cardinalis cardinalis"},
    )
    assert with_name.confirmed_species[0].scientific_name == "Cardinalis cardinalis"

    without_name = compute_conservation_report(
        report, visits=visits, offline_acquisition=_empty_offline_effort(),
        live_monitoring_usable_day_count=1, confirmed_wildlife_visits_with_evidence_count=1,
    )
    assert without_name.confirmed_species[0].scientific_name is None


def test_a_confirmed_kind_level_mammal_is_reported_alongside_a_bird_honestly():
    """Broader Wildlife Maturity v1 (see docs/broader-wildlife-maturity-v1-
    contract.md). A confirmed raccoon (real, kind-level wildlife -- not
    unresolved the way UNKNOWN_BIRD is) must appear in the conservation
    report's taxon roster next to a confirmed bird, carrying its own honest
    `is_species=False` and no fabricated scientific name -- never folded
    into "confirmed_unidentified_wildlife" (that bucket is for genuinely
    unresolved taxon, not every non-bird)."""

    visits = [
        _visit(1, 7, CARDINAL, visit_id="v1"),
        _visit(2, 8, RACCOON, visit_id="v2"),
    ]
    report = compute_place_activity_report(visits, period_start_at=PERIOD_START, period_end_at=PERIOD_END)
    conservation = compute_conservation_report(
        report, visits=visits, offline_acquisition=_empty_offline_effort(),
        live_monitoring_usable_day_count=2, confirmed_wildlife_visits_with_evidence_count=2,
        scientific_names_by_label={"northern_cardinal": "Cardinalis cardinalis"},
    )
    labels = {record.label: record for record in conservation.confirmed_species}
    assert set(labels) == {"northern_cardinal", "raccoon"}
    assert labels["raccoon"].is_species is False
    assert labels["raccoon"].scientific_name is None
    assert labels["northern_cardinal"].scientific_name == "Cardinalis cardinalis"
    assert conservation.confirmed_unidentified_wildlife_visit_count == 0
    assert conservation.reviewed_wildlife_visit_count == 2


def test_offline_acquisition_effort_reported_separately_from_live_coverage():
    visits = [_visit(1, 7, CARDINAL, visit_id="v1")]
    report = compute_place_activity_report(
        visits,
        period_start_at=PERIOD_START,
        period_end_at=PERIOD_END,
        coverage=compute_coverage_summary(
            period_start_at=PERIOD_START,
            period_end_at=PERIOD_END,
            monitored_intervals=[TimeInterval(PERIOD_START, PERIOD_START.replace(hour=3))],
            history_available_from=PERIOD_START,
        ),
    )
    offline_effort = compute_offline_acquisition_effort(
        recorded_videos=[
            RecordedVideoAcquisitionFact("media-1", "stream-1", 90.0, 45, PERIOD_START),
        ],
    )
    conservation = compute_conservation_report(
        report, visits=visits, offline_acquisition=offline_effort,
        live_monitoring_usable_day_count=1, confirmed_wildlife_visits_with_evidence_count=1,
    )
    # Live monitoring and offline acquisition remain two distinct facts --
    # never summed into one "coverage" number.
    assert conservation.live_monitoring_monitored_seconds == 3 * 3600
    assert conservation.offline_acquisition.recorded_video_analyzed_seconds == 90.0
    assert conservation.offline_acquisition is offline_effort


def test_unresolved_and_provisional_counts_are_disclosed_as_review_backlog():
    visits = [
        _visit(1, 7, CARDINAL, visit_id="v1"),
        VisitFact(
            visit_id="v2", zone_id=None, zone_name=None,
            activity_started_at=datetime(2026, 8, 2, tzinfo=UTC), resolution="needs_review",
        ),
    ]
    report = compute_place_activity_report(visits, period_start_at=PERIOD_START, period_end_at=PERIOD_END)
    conservation = compute_conservation_report(
        report, visits=visits, offline_acquisition=_empty_offline_effort(),
        live_monitoring_usable_day_count=1, confirmed_wildlife_visits_with_evidence_count=1,
    )
    assert conservation.unresolved_visit_count == 1
    assert conservation.total_visit_count == 2


def test_report_never_claims_a_population_or_percentage_figure():
    # Structural guarantee, not a string-content check: ConservationReport
    # and ConservationSpeciesRecord carry no such field at all.
    visits = [_visit(1, 7, CARDINAL, visit_id="v1")]
    report = compute_place_activity_report(visits, period_start_at=PERIOD_START, period_end_at=PERIOD_END)
    conservation = compute_conservation_report(
        report, visits=visits, offline_acquisition=_empty_offline_effort(),
        live_monitoring_usable_day_count=1, confirmed_wildlife_visits_with_evidence_count=1,
    )
    forbidden_fields = {"population", "abundance", "occupancy", "biodiversity_index", "percentage", "trend"}
    record_fields = set(conservation.confirmed_species[0].__dataclass_fields__)
    report_fields = set(conservation.__dataclass_fields__)
    assert forbidden_fields.isdisjoint(record_fields)
    assert forbidden_fields.isdisjoint(report_fields)


def test_occurrence_note_omitted_when_usable_day_count_unknown():
    assert format_occurrence_note("Blue Jay", 2, None) is None
    assert format_occurrence_note("Blue Jay", 0, 0) is None


def test_occurrence_note_uses_singular_day_wording():
    assert format_occurrence_note("Blue Jay", 1, 1) == "Blue Jay was confirmed on 1 of 1 usable monitored day."
