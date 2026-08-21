"""Adapters between MockingBird's canonical durable product read model
(`StreamVisitSummary`, `TaxonomyLabel`) and the pure Place Activity Report
computation contract (`VisitFact`/`TaxonFact`/`PlaceActivityReport`) -- see
docs/place-activity-report-contract.md "Integration" and
`mockingbird.analytics.place_activity_report`.

`ProductRepository.place_activity_report` is the only caller: it owns every
database session/query and all truth resolution (reusing
`_stream_visit_summary_from_models`, the same canonical per-Visit resolver
`zone_insights`/`wildlife_insights` already use), then hands already-resolved
`StreamVisitSummary`/`TaxonomyLabel` objects to the pure functions below.
This module never opens a session, never queries anything, and never
re-derives review truth or report math itself -- it only reshapes already-
settled product-schema facts into the pure computation module's input
contract, and reshapes that module's typed output into the read-only API's
response schema. Kept separate from `product_repository.py` (already a very
large module) so this translation stays a small, independently readable and
testable unit, matching this milestone's architecture goals.
"""

from __future__ import annotations

from typing import Mapping

from mockingbird.analytics.historical_baseline import (
    HistoricalPlaceBaseline,
    SpeciesHistoricalStatus,
)
from mockingbird.analytics.place_activity_report import (
    CoverageSummary,
    HourActivityEntry,
    PlaceActivityReport,
    TaxonFact,
    TaxonReportEntry,
    VisitFact,
    VisitResolution,
    ZoneActivityEntry,
)
from mockingbird.api.schemas import (
    LabelCategory,
    PlaceActivityReportCoverage,
    PlaceActivityReportCoverageGap,
    PlaceActivityReportHistoricalBaseline,
    PlaceActivityReportHourActivity,
    PlaceActivityReportResponse,
    PlaceActivityReportTaxonEntry,
    PlaceActivityReportTaxonHistoricalStatus,
    PlaceActivityReportZoneActivity,
    ReviewStatus,
    StreamVisitSummary,
    TaxonomyLabel,
)

_RESOLUTION_BY_REVIEW_STATUS: dict[ReviewStatus, VisitResolution] = {
    ReviewStatus.needs_review: "needs_review",
    ReviewStatus.reviewed: "reviewed",
    ReviewStatus.rejected: "rejected",
}


def taxon_fact_from_taxonomy_label(label: TaxonomyLabel) -> TaxonFact:
    """Field-for-field mapping -- `TaxonFact` deliberately mirrors
    `TaxonomyLabel`'s reporting-relevant fields exactly (see its docstring
    in place_activity_report.py), so this never computes anything, only
    reshapes an already-resolved taxonomy row."""

    return TaxonFact(
        label=label.label,
        display_name=label.display_name,
        category=label.category.value,
        is_species=label.is_species,
    )


def visit_fact_from_stream_visit_summary(
    summary: StreamVisitSummary,
    *,
    confirmed_taxon: TaxonFact | None,
    provisional_taxon: TaxonFact | None,
) -> VisitFact:
    """Adapt one already-resolved `StreamVisitSummary` -- the same canonical
    per-Visit resolver output `ProductRepository.zone_insights` and
    `wildlife_insights` already reuse (`_stream_visit_summary_from_models`)
    -- into a `VisitFact`.

    The caller must already have resolved `confirmed_taxon`/
    `provisional_taxon` (a taxonomy lookup on `summary.reviewed_label`/
    `summary.suggested_label`); this function only reshapes already-settled
    facts, exactly like the rest of this module -- it never queries a
    taxonomy table itself. `confirmed_taxon` is dropped unless
    `summary.review_status == ReviewStatus.reviewed`: `VisitFact.
    __post_init__` enforces this invariant, so a caller bug elsewhere raises
    loudly instead of silently fabricating confirmed truth for an
    unreviewed Visit.
    """

    resolution = _RESOLUTION_BY_REVIEW_STATUS[summary.review_status]
    return VisitFact(
        visit_id=summary.id,
        zone_id=summary.zone_id,
        zone_name=summary.zone_name,
        activity_started_at=summary.activity_started_at,
        resolution=resolution,
        confirmed_taxon=confirmed_taxon if resolution == "reviewed" else None,
        provisional_taxon=provisional_taxon,
    )


def _species_historical_status_response(
    status: SpeciesHistoricalStatus,
) -> PlaceActivityReportTaxonHistoricalStatus:
    return PlaceActivityReportTaxonHistoricalStatus(
        first_confirmed_at=status.first_confirmed_at,
        last_confirmed_at=status.last_confirmed_at,
        distinct_confirmed_days=status.distinct_confirmed_days,
        distinct_confirmed_usable_days=status.distinct_confirmed_usable_days,
        total_confirmed_count=status.total_confirmed_count,
        status=status.status,
    )


def _taxon_entry_response(
    entry: TaxonReportEntry,
    *,
    historical_status: SpeciesHistoricalStatus | None,
) -> PlaceActivityReportTaxonEntry:
    return PlaceActivityReportTaxonEntry(
        label=entry.label,
        display_name=entry.display_name,
        category=LabelCategory(entry.category),
        is_species=entry.is_species,
        confirmed_visit_count=entry.confirmed_visit_count,
        provisional_visit_count=entry.provisional_visit_count,
        total_visit_count=entry.total_visit_count,
        first_activity_at=entry.first_activity_at,
        last_activity_at=entry.last_activity_at,
        historical_status=(
            _species_historical_status_response(historical_status)
            if historical_status is not None
            else None
        ),
    )


def _zone_entry_response(entry: ZoneActivityEntry) -> PlaceActivityReportZoneActivity:
    return PlaceActivityReportZoneActivity(
        zone_id=entry.zone_id,
        zone_name=entry.zone_name,
        wildlife_visit_count=entry.wildlife_visit_count,
    )


def _hour_entry_response(entry: HourActivityEntry) -> PlaceActivityReportHourActivity:
    return PlaceActivityReportHourActivity(
        hour=entry.hour,
        wildlife_visit_count=entry.wildlife_visit_count,
    )


def _coverage_response(coverage: CoverageSummary) -> PlaceActivityReportCoverage:
    return PlaceActivityReportCoverage(
        period_seconds=coverage.period_seconds,
        monitored_seconds=coverage.monitored_seconds,
        coverage_ratio=coverage.coverage_ratio,
        history_available_from=coverage.history_available_from,
        history_is_partial=coverage.history_is_partial,
        gaps=[
            PlaceActivityReportCoverageGap(
                start_at=gap.start_at,
                end_at=gap.end_at,
                duration_seconds=gap.duration_seconds,
            )
            for gap in coverage.gaps
        ],
        gaps_truncated=coverage.gaps_truncated,
    )


def _historical_baseline_response(
    baseline: HistoricalPlaceBaseline,
) -> PlaceActivityReportHistoricalBaseline:
    return PlaceActivityReportHistoricalBaseline(
        window_start_at=baseline.window_start_at,
        window_end_at=baseline.window_end_at,
        usable_day_count=baseline.usable_day_count,
        total_monitored_seconds=baseline.total_monitored_seconds,
        maturity=baseline.maturity,
        distinct_taxa_count=baseline.distinct_taxa_count,
        earliest_authoritative_record_at=baseline.earliest_authoritative_record_at,
        latest_authoritative_record_at=baseline.latest_authoritative_record_at,
    )


def place_activity_report_response(
    report: PlaceActivityReport,
    *,
    timezone_name: str,
    warnings: list[str],
    historical_baseline: HistoricalPlaceBaseline,
    species_historical_statuses: Mapping[str, SpeciesHistoricalStatus],
) -> PlaceActivityReportResponse:
    """Adapt one pure `PlaceActivityReport` into its typed API response.
    Field-for-field only -- see the module docstring. `report.coverage` is
    required here: `ProductRepository.place_activity_report` always supplies
    a `CoverageSummary` (its own `monitored_seconds`/`coverage_ratio` are
    `None` when durable history is unavailable, which is a different,
    honest fact from the caller omitting coverage entirely -- see
    `CoverageSummary`'s docstring).

    `historical_baseline`/`species_historical_statuses` are required for the
    same reason: `ProductRepository.place_activity_report` always computes
    them (Historical Baseline Maturity + New/Regular Species v1; see
    docs/historical-baseline-maturity-contract.md). `species_historical_
    statuses` is keyed by taxon label; a `report.taxa` entry with no match
    (a purely-provisional taxon, never authoritatively confirmed) correctly
    gets `historical_status=None` -- see `_taxon_entry_response`.
    """

    if report.coverage is None:
        raise ValueError(
            "place_activity_report_response requires a coverage summary; "
            "ProductRepository.place_activity_report must always compute one."
        )

    return PlaceActivityReportResponse(
        period_start_at=report.period_start_at,
        period_end_at=report.period_end_at,
        timezone_name=timezone_name,
        generated_at=report.generated_at,
        total_visit_count=report.total_visit_count,
        confirmed_wildlife_visit_count=report.confirmed_wildlife_visit_count,
        provisional_wildlife_visit_count=report.provisional_wildlife_visit_count,
        unresolved_visit_count=report.unresolved_visit_count,
        non_wildlife_visit_count=report.non_wildlife_visit_count,
        excluded_visit_count=report.excluded_visit_count,
        confirmed_species_unresolved_visit_count=report.confirmed_species_unresolved_visit_count,
        wildlife_visit_count=report.wildlife_visit_count,
        distinct_taxa_count=report.distinct_taxa_count,
        distinct_species_count=report.distinct_species_count,
        taxa=[
            _taxon_entry_response(
                entry, historical_status=species_historical_statuses.get(entry.label)
            )
            for entry in report.taxa
        ],
        first_activity_at=report.first_activity_at,
        last_activity_at=report.last_activity_at,
        activity_by_zone=[_zone_entry_response(entry) for entry in report.activity_by_zone],
        busiest_zone=(
            _zone_entry_response(report.busiest_zone) if report.busiest_zone is not None else None
        ),
        activity_by_hour=[_hour_entry_response(entry) for entry in report.activity_by_hour],
        coverage=_coverage_response(report.coverage),
        maturity=report.maturity,
        historical_baseline=_historical_baseline_response(historical_baseline),
        warnings=warnings,
    )
