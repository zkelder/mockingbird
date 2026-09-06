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

from datetime import date, datetime
from typing import Mapping, NamedTuple, Sequence

from mockingbird.analytics.daily_digest import (
    DailyDigest,
    DigestCoverageSummary,
    DigestOtherActivity,
    DigestOtherSpecies,
    DigestSpeciesHighlight,
    DigestTaxonFact,
    compute_daily_digest,
)
from mockingbird.analytics.historical_baseline import (
    HistoricalPlaceBaseline,
    SpeciesHistoricalStatus,
)
from mockingbird.analytics.place_biodiversity_summary import PlaceBiodiversitySummary
from mockingbird.analytics.place_activity_report import (
    CoverageSummary,
    HourActivityEntry,
    PlaceActivityReport,
    TaxonFact,
    TaxonHourActivityEntry,
    TaxonPlacePattern,
    TaxonReportEntry,
    TaxonZoneActivityEntry,
    VisitFact,
    VisitResolution,
    ZoneActivityEntry,
)
from mockingbird.analytics.place_change_summary import (
    PlaceChangeSummary,
    PlaceChangeWindows,
    PlaceOverallChangeStatus,
    TaxonChangeStatus,
)
from mockingbird.analytics.regularity_narrative import RegularityNarrative
from mockingbird.analytics.seasonal_pattern import MonthPresence, SeasonalPattern
from mockingbird.analytics.temporal_pattern import TaxonTemporalPattern
from mockingbird.analytics.habitat_association import TaxonHabitatAssociation
from mockingbird.analytics.weather_association import TaxonWeatherAssociation
from mockingbird.analytics.source_activity import SourceActivityEntry, SourceQualitySignal
from mockingbird.analytics.conditional_association import ConditionalAssociation
from mockingbird.analytics.year_over_year_comparison import (
    ComparablePeriod,
    TaxonYearOverYearComparison,
)
from mockingbird.analytics.year_over_year_comparison import (
    PlaceYearOverYearComparison as PlaceYearOverYearComparisonFact,
)
from mockingbird.api.schemas import (
    DashboardTodaySpecies,
    LabelCategory,
    PlaceActivityReportChangeWindows,
    PlaceActivityReportCoverage,
    PlaceActivityReportCoverageGap,
    PlaceActivityReportDigest,
    PlaceActivityReportDigestCoverage,
    PlaceActivityReportDigestOtherActivity,
    PlaceActivityReportDigestOtherSpecies,
    PlaceActivityReportDigestSpeciesHighlight,
    PlaceActivityReportHabitatAssociation,
    PlaceActivityReportHistoricalBaseline,
    PlaceActivityReportHourActivity,
    PlaceActivityReportMonthPresence,
    PlaceActivityReportOverallChangeStatus,
    PlaceActivityReportRegularityNarrative,
    PlaceActivityReportResponse,
    PlaceActivityReportSeasonalPattern,
    PlaceActivityReportSourceActivity,
    PlaceActivityReportSourceQualitySignal,
    PlaceActivityReportTaxonChangeStatus,
    PlaceActivityReportTaxonEntry,
    PlaceActivityReportTaxonHistoricalStatus,
    PlaceActivityReportTaxonHourActivity,
    PlaceActivityReportTaxonZoneActivity,
    PlaceActivityReportTemporalPattern,
    PlaceActivityReportWeatherAssociation,
    PlaceActivityReportZoneActivity,
    PlaceBiodiversitySummaryResponse,
    PlaceBiodiversityTaxonEntry,
    PlaceEnvironmentalContext,
    PlaceHabitatContext,
    RepresentativeEvidence,
    ReviewStatus,
    StreamVisitSummary,
    TaxonomyLabel,
    PlaceYearOverYearAssociation,
    PlaceYearOverYearPeriod,
    PlaceYearOverYearResponse,
    PlaceYearOverYearSpeciesEntry,
)
from mockingbird.api.schemas import PlaceYearOverYearComparison as PlaceYearOverYearComparisonResponse


class HistoricalPlaceIntelligence(NamedTuple):
    """Place / Yard Intelligence v2: the bundled return of
    `ProductRepository._historical_place_baseline_and_species_statuses`,
    defined here (not in `product_repository.py`) so this adapter module
    can accept and reshape it without a circular import -- the repository
    already imports this module, never the reverse.

    A `NamedTuple` (not a bare tuple) deliberately: this method's several
    call sites access fields by name, not position -- a bare tuple that
    grew from 4 to 8 elements while every call site was being touched
    anyway was judged too easy to silently mis-order.
    """

    baseline: HistoricalPlaceBaseline
    species_historical_statuses: dict[str, SpeciesHistoricalStatus]
    change_summary: PlaceChangeSummary
    taxon_place_patterns: dict[str, TaxonPlacePattern]
    regularity_narratives: dict[str, RegularityNarrative]
    seasonal_patterns: dict[str, SeasonalPattern]
    temporal_patterns: dict[str, TaxonTemporalPattern]
    habitat_associations: dict[str, list[TaxonHabitatAssociation]]
    weather_associations: dict[str, list[TaxonWeatherAssociation]]
    # Place Story & Seasonal Timeline v1: the raw ingredients this method
    # already assembles internally to compute everything above, additively
    # exposed so `place_story`'s own checkpoint scan (which needs the raw
    # per-Visit/per-taxon facts, not this method's own single-`window_end_
    # at`-snapshot outputs) can reuse this one call's already-issued
    # queries instead of a second, duplicate fetch. Every existing caller
    # of this NamedTuple is unaffected -- purely additive fields.
    taxa: dict[str, TaxonFact]
    all_time_first_confirmed_at: dict[str, datetime]
    all_time_last_confirmed_at: dict[str, datetime]
    usable_dates: frozenset[date]
    window_visits: list[VisitFact]

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
    source_id: str | None = None,
    source_name: str | None = None,
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

    `source_id`/`source_name` (Place / Yard Intelligence v2): `StreamVisit
    Summary` itself carries no Source identity, so a caller that wants
    `source_activity.py`'s per-Source comparison must resolve and pass these
    itself (see `ProductRepository.place_activity_report`'s own
    `stream_source_index`) -- both default to `None`, so every pre-existing
    caller that has no reason to know a Visit's Source is unaffected.
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
        source_id=source_id,
        source_name=source_name,
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


def taxon_change_status_response(
    status: TaxonChangeStatus | None,
) -> PlaceActivityReportTaxonChangeStatus | None:
    """Public (not module-private) because Bird Log's own repository
    integration (`ProductRepository.wildlife_journal_overview`/
    `wildlife_journal_history`) needs this exact same conversion for its own
    `WildlifeJournalLabelSummary.change_status`/`WildlifeJournalHistory
    Response.change_status` fields -- see
    docs/meaningful-change-detection-contract.md."""

    if status is None:
        return None
    return PlaceActivityReportTaxonChangeStatus(
        recent_presence_days=status.recent_presence_days,
        recent_usable_day_count=status.recent_usable_day_count,
        reference_presence_days=status.reference_presence_days,
        reference_usable_day_count=status.reference_usable_day_count,
        status=status.status,
    )


def _change_windows_response(windows: PlaceChangeWindows) -> PlaceActivityReportChangeWindows:
    return PlaceActivityReportChangeWindows(
        policy_version=windows.policy_version,
        recent_window_start_at=windows.recent_window_start_at,
        recent_window_end_at=windows.recent_window_end_at,
        reference_window_start_at=windows.reference_window_start_at,
        reference_window_end_at=windows.reference_window_end_at,
        is_valid=windows.is_valid,
        invalid_reason=windows.invalid_reason,
    )


def _overall_change_status_response(
    overall: PlaceOverallChangeStatus,
) -> PlaceActivityReportOverallChangeStatus:
    return PlaceActivityReportOverallChangeStatus(
        recent_presence_days=overall.recent_presence_days,
        recent_usable_day_count=overall.recent_usable_day_count,
        reference_presence_days=overall.reference_presence_days,
        reference_usable_day_count=overall.reference_usable_day_count,
        status=overall.status,
    )


def _taxon_zone_activity_response(
    entry: TaxonZoneActivityEntry,
) -> PlaceActivityReportTaxonZoneActivity:
    return PlaceActivityReportTaxonZoneActivity(
        zone_id=entry.zone_id,
        display_name=entry.zone_name,
        reviewed_visit_count=entry.reviewed_visit_count,
    )


def _taxon_hour_activity_response(
    entry: TaxonHourActivityEntry,
) -> PlaceActivityReportTaxonHourActivity:
    return PlaceActivityReportTaxonHourActivity(
        local_hour=entry.local_hour,
        reviewed_visit_count=entry.reviewed_visit_count,
    )


def _regularity_narrative_response(
    narrative: RegularityNarrative | None,
) -> PlaceActivityReportRegularityNarrative | None:
    if narrative is None:
        return None
    return PlaceActivityReportRegularityNarrative(state=narrative.state, basis=narrative.basis)


def _month_presence_response(month: MonthPresence) -> PlaceActivityReportMonthPresence:
    return PlaceActivityReportMonthPresence(
        month=month.month,
        usable_day_count=month.usable_day_count,
        presence_day_count=month.presence_day_count,
    )


def _seasonal_pattern_response(
    pattern: SeasonalPattern | None,
) -> PlaceActivityReportSeasonalPattern | None:
    if pattern is None:
        return None
    return PlaceActivityReportSeasonalPattern(
        status=pattern.status,
        months=[_month_presence_response(month) for month in pattern.months],
        typical_months=list(pattern.typical_months),
        current_month_is_typical=pattern.current_month_is_typical,
    )


def _temporal_pattern_response(
    pattern: TaxonTemporalPattern | None,
) -> PlaceActivityReportTemporalPattern | None:
    if pattern is None:
        return None
    return PlaceActivityReportTemporalPattern(
        reviewed_visit_count=pattern.reviewed_visit_count,
        day_count=pattern.day_count,
        night_count=pattern.night_count,
        unknown_daylight_count=pattern.unknown_daylight_count,
        daylight_association=pattern.daylight_association,
        dominant_band=pattern.dominant_band,
        most_active_hour=pattern.most_active_hour,
    )


def _habitat_association_response(
    association: TaxonHabitatAssociation,
) -> PlaceActivityReportHabitatAssociation:
    return PlaceActivityReportHabitatAssociation(
        subject_label=association.subject_label,
        phenomenon=association.phenomenon,
        status=association.association.status,
        presence_days_in_condition=association.association.presence_days_in_condition,
        usable_days_in_condition=association.association.usable_days_in_condition,
        presence_days_out_of_condition=association.association.presence_days_out_of_condition,
        usable_days_out_of_condition=association.association.usable_days_out_of_condition,
    )


def _weather_association_response(
    association: TaxonWeatherAssociation,
) -> PlaceActivityReportWeatherAssociation:
    return PlaceActivityReportWeatherAssociation(
        condition=association.condition,
        condition_label=association.condition_label,
        status=association.association.status,
        presence_days_in_condition=association.association.presence_days_in_condition,
        usable_days_in_condition=association.association.usable_days_in_condition,
        presence_days_out_of_condition=association.association.presence_days_out_of_condition,
        usable_days_out_of_condition=association.association.usable_days_out_of_condition,
    )


def _taxon_entry_response(
    entry: TaxonReportEntry,
    *,
    historical_status: SpeciesHistoricalStatus | None,
    change_status: TaxonChangeStatus | None,
    place_pattern: TaxonPlacePattern | None,
    representative_evidence: RepresentativeEvidence | None,
    regularity_narrative: RegularityNarrative | None = None,
    seasonal_pattern: SeasonalPattern | None = None,
    temporal_pattern: TaxonTemporalPattern | None = None,
    habitat_associations: list[TaxonHabitatAssociation] | None = None,
    weather_associations: list[TaxonWeatherAssociation] | None = None,
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
        change_status=taxon_change_status_response(change_status),
        # `place_pattern` is `None` under the identical truth-contract
        # condition as `historical_status` above (a purely-provisional
        # taxon was never authoritatively confirmed anywhere in the
        # historical window, so it has no reviewed Zone/hour pattern to
        # report) -- see docs/place-activity-report-contract.md.
        zone_activity=(
            [_taxon_zone_activity_response(zone) for zone in place_pattern.zone_activity]
            if place_pattern is not None
            else []
        ),
        hour_activity=(
            [_taxon_hour_activity_response(hour) for hour in place_pattern.hour_activity]
            if place_pattern is not None
            else []
        ),
        most_active_zone=(
            _taxon_zone_activity_response(place_pattern.most_active_zone)
            if place_pattern is not None and place_pattern.most_active_zone is not None
            else None
        ),
        most_active_hour=(
            _taxon_hour_activity_response(place_pattern.most_active_hour)
            if place_pattern is not None and place_pattern.most_active_hour is not None
            else None
        ),
        representative_evidence=representative_evidence,
        # Place / Yard Intelligence v2: all four `None`/`[]` under the
        # identical truth-contract condition as `historical_status` above.
        regularity_narrative=_regularity_narrative_response(regularity_narrative),
        seasonal_pattern=_seasonal_pattern_response(seasonal_pattern),
        temporal_pattern=_temporal_pattern_response(temporal_pattern),
        habitat_associations=(
            [_habitat_association_response(association) for association in habitat_associations]
            if habitat_associations is not None
            else []
        ),
        weather_associations=(
            [_weather_association_response(association) for association in weather_associations]
            if weather_associations is not None
            else []
        ),
    )


def _digest_taxon_fact(
    entry: TaxonReportEntry,
    *,
    historical_status: SpeciesHistoricalStatus | None,
    change_status: TaxonChangeStatus | None,
    place_pattern: TaxonPlacePattern | None,
    representative_evidence: RepresentativeEvidence | None,
    regularity_narrative: RegularityNarrative | None = None,
    seasonal_pattern: SeasonalPattern | None = None,
    unusual_timing_in_period: bool = False,
) -> DigestTaxonFact:
    """Gate C -- Calm Daily Digest v1: build one `DigestTaxonFact` from the
    exact same per-taxon facts `_taxon_entry_response` above already
    assembles into a `PlaceActivityReportTaxonEntry` -- never a second,
    independently-derived set of facts (see the digest module's own
    docstring)."""

    return DigestTaxonFact(
        label=entry.label,
        display_name=entry.display_name,
        category=entry.category,
        is_species=entry.is_species,
        confirmed_visit_count=entry.confirmed_visit_count,
        provisional_visit_count=entry.provisional_visit_count,
        first_activity_at=entry.first_activity_at,
        last_activity_at=entry.last_activity_at,
        historical_status=historical_status.status if historical_status is not None else None,
        change_status=change_status.status if change_status is not None else None,
        most_active_zone_name=(
            place_pattern.most_active_zone.zone_name
            if place_pattern is not None and place_pattern.most_active_zone is not None
            else None
        ),
        most_active_hour=(
            place_pattern.most_active_hour.local_hour
            if place_pattern is not None and place_pattern.most_active_hour is not None
            else None
        ),
        has_representative_evidence=representative_evidence is not None,
        # "Strong" mirrors `representative_evidence.EvidenceCandidateFact.
        # is_native_resolution`'s own definition exactly (a genuinely
        # proven, separate higher-resolution capture) -- never inferred
        # from pixel counts or evidence presence alone.
        has_strong_representative_evidence=(
            representative_evidence is not None
            and representative_evidence.evidence.resolution_provenance == "synchronized"
        ),
        # Place / Yard Intelligence v2: same truth-contract condition as
        # `historical_status`/`change_status` above.
        regularity_state=regularity_narrative.state if regularity_narrative is not None else None,
        unusual_timing_in_period=unusual_timing_in_period,
        seasonal_status=seasonal_pattern.status if seasonal_pattern is not None else None,
        is_in_typical_season=(
            seasonal_pattern.current_month_is_typical if seasonal_pattern is not None else None
        ),
    )


def _digest_highlight_response(
    highlight: DigestSpeciesHighlight,
    *,
    representative_evidence: RepresentativeEvidence | None,
) -> PlaceActivityReportDigestSpeciesHighlight:
    return PlaceActivityReportDigestSpeciesHighlight(
        label=highlight.label,
        display_name=highlight.display_name,
        category=LabelCategory(highlight.category),
        is_species=highlight.is_species,
        confirmed_visit_count=highlight.confirmed_visit_count,
        provisional_visit_count=highlight.provisional_visit_count,
        first_activity_at=highlight.first_activity_at,
        last_activity_at=highlight.last_activity_at,
        reason=highlight.reason,
        historical_note=highlight.historical_note,
        change_note=highlight.change_note,
        pattern_note=highlight.pattern_note,
        # Reused unmodified from the same `representative_evidence` mapping
        # `_taxon_entry_response` already draws from -- the digest never
        # selects or ranks evidence itself; see "I.8 Representative
        # evidence" in the milestone brief.
        representative_evidence=representative_evidence,
    )


def _digest_other_species_response(
    entry: DigestOtherSpecies,
) -> PlaceActivityReportDigestOtherSpecies:
    return PlaceActivityReportDigestOtherSpecies(
        label=entry.label,
        display_name=entry.display_name,
        category=LabelCategory(entry.category),
        is_species=entry.is_species,
        confirmed_visit_count=entry.confirmed_visit_count,
    )


def _digest_coverage_response(
    coverage: DigestCoverageSummary,
) -> PlaceActivityReportDigestCoverage:
    return PlaceActivityReportDigestCoverage(
        state=coverage.state,
        maturity=coverage.maturity,
        message=coverage.message,
    )


def _digest_other_activity_response(
    other_activity: DigestOtherActivity,
) -> PlaceActivityReportDigestOtherActivity:
    return PlaceActivityReportDigestOtherActivity(
        provisional_visit_count=other_activity.provisional_visit_count,
        unresolved_visit_count=other_activity.unresolved_visit_count,
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


def _source_activity_response(entry: SourceActivityEntry) -> PlaceActivityReportSourceActivity:
    return PlaceActivityReportSourceActivity(
        source_id=entry.source_id,
        source_name=entry.source_name,
        confirmed_wildlife_visit_count=entry.confirmed_wildlife_visit_count,
        monitored_seconds=entry.monitored_seconds,
        visits_per_monitored_hour=entry.visits_per_monitored_hour,
        data_sufficient=entry.data_sufficient,
    )


def _source_quality_signal_response(
    signal: SourceQualitySignal,
) -> PlaceActivityReportSourceQualitySignal:
    return PlaceActivityReportSourceQualitySignal(
        source_id=signal.source_id,
        source_name=signal.source_name,
        candidates_attempted_count=signal.candidates_attempted_count,
        candidates_created_count=signal.candidates_created_count,
        suppressed_count=signal.suppressed_count,
        admission_yield_ratio=signal.admission_yield_ratio,
        place_average_yield_ratio=signal.place_average_yield_ratio,
        signal=signal.signal,
    )


def place_activity_report_response(
    report: PlaceActivityReport,
    *,
    timezone_name: str,
    warnings: list[str],
    historical_place_intelligence: HistoricalPlaceIntelligence,
    representative_evidence: Mapping[str, RepresentativeEvidence],
    unusual_timing_by_label: Mapping[str, bool] = {},
    activity_by_source: Sequence[SourceActivityEntry] = (),
    source_quality_signals: Sequence[SourceQualitySignal] = (),
    weekly_report: PlaceActivityReport | None = None,
) -> PlaceActivityReportResponse:
    """Adapt one pure `PlaceActivityReport` into its typed API response.
    Field-for-field only -- see the module docstring. `report.coverage` is
    required here: `ProductRepository.place_activity_report` always supplies
    a `CoverageSummary` (its own `monitored_seconds`/`coverage_ratio` are
    `None` when durable history is unavailable, which is a different,
    honest fact from the caller omitting coverage entirely -- see
    `CoverageSummary`'s docstring).

    `historical_place_intelligence` bundles everything `ProductRepository.
    _historical_place_baseline_and_species_statuses` always computes
    (Historical Baseline Maturity + New/Regular Species v1; Gate C --
    Meaningful Change Detection v1; Gate C -- Per-Species Zone + Time
    Pattern Intelligence v1; and, Place / Yard Intelligence v2, per-taxon
    regularity/seasonal/temporal/habitat facts -- see
    docs/place-yard-intelligence-v2-contract.md), every field keyed by
    taxon label. A `report.taxa` entry with no match in any of these
    mappings (a purely-provisional taxon, never authoritatively confirmed)
    correctly gets `None`/`[]` for that fact -- see `_taxon_entry_response`.

    `representative_evidence` (Gate C -- Representative Species Evidence v1;
    see docs/representative-species-evidence-contract.md) is keyed by taxon
    label the same way; a `report.taxa` entry with no match (no confirmed
    Visit this period had safe, present evidence -- including every
    purely-provisional taxon) correctly gets `representative_evidence=None`,
    never an error and never a dropped taxon.

    `unusual_timing_by_label`/`activity_by_source`/`source_quality_signals`
    (Place / Yard Intelligence v2, Phases 6/7/8) are all optional and
    default to "nothing computed" -- a caller that does not compute them
    (there is none today; `ProductRepository.place_activity_report` always
    does) gets a completely valid, honest response with those facts simply
    absent, never an error.

    `weekly_report` (Phase 13): an already-computed `PlaceActivityReport`
    for the 7-usable-day recent window (built the identical way `report`
    itself was, just over different period bounds -- see
    `ProductRepository.place_activity_report`'s own weekly-window query),
    or `None` when that window is not valid yet (mirrors `change_summary.
    windows.is_valid`). Reuses the *same* per-taxon historical/change/
    pattern/regularity/seasonal facts and `compute_daily_digest` -- no
    second ranking module -- with `period_label="this week"` so a week's
    worth of activity is never worded as "today."
    """

    if report.coverage is None:
        raise ValueError(
            "place_activity_report_response requires a coverage summary; "
            "ProductRepository.place_activity_report must always compute one."
        )

    species_historical_statuses = historical_place_intelligence.species_historical_statuses
    change_summary = historical_place_intelligence.change_summary
    taxon_place_patterns = historical_place_intelligence.taxon_place_patterns
    regularity_narratives = historical_place_intelligence.regularity_narratives
    seasonal_patterns = historical_place_intelligence.seasonal_patterns
    temporal_patterns = historical_place_intelligence.temporal_patterns
    habitat_associations = historical_place_intelligence.habitat_associations
    weather_associations = historical_place_intelligence.weather_associations
    change_status_by_label = {status.taxon.label: status for status in change_summary.taxa}
    assert change_summary.overall is not None

    # Gate C -- Calm Daily Digest v1 / Place / Yard Intelligence v2, Phase
    # 13: one shared builder so "today" and "this week" can never diverge
    # in how a taxon's historical/change/pattern/regularity/seasonal facts
    # are looked up -- only which report's own taxa/counts/period feed it.
    def build_digest(source_report: PlaceActivityReport, *, period_label: str) -> DailyDigest:
        return compute_daily_digest(
            [
                _digest_taxon_fact(
                    entry,
                    historical_status=species_historical_statuses.get(entry.label),
                    change_status=change_status_by_label.get(entry.label),
                    place_pattern=taxon_place_patterns.get(entry.label),
                    representative_evidence=representative_evidence.get(entry.label),
                    regularity_narrative=regularity_narratives.get(entry.label),
                    seasonal_pattern=seasonal_patterns.get(entry.label),
                    unusual_timing_in_period=unusual_timing_by_label.get(entry.label, False),
                )
                for entry in source_report.taxa
            ],
            period_start_at=source_report.period_start_at,
            period_end_at=source_report.period_end_at,
            generated_at=source_report.generated_at,
            maturity=source_report.maturity,
            confirmed_wildlife_visit_count=source_report.confirmed_wildlife_visit_count,
            provisional_wildlife_visit_count=source_report.provisional_wildlife_visit_count,
            unresolved_visit_count=source_report.unresolved_visit_count,
            first_activity_at=source_report.first_activity_at,
            last_activity_at=source_report.last_activity_at,
            place_change_status=change_summary.overall.status,
            period_label=period_label,
        )

    def digest_response(digest: DailyDigest) -> PlaceActivityReportDigest:
        return PlaceActivityReportDigest(
            coverage=_digest_coverage_response(digest.coverage),
            primary_highlights=[
                _digest_highlight_response(
                    highlight, representative_evidence=representative_evidence.get(highlight.label)
                )
                for highlight in digest.primary_highlights
            ],
            other_species=[_digest_other_species_response(entry) for entry in digest.other_species],
            other_activity=_digest_other_activity_response(digest.other_activity),
            place_change_note=digest.place_change_note,
            first_activity_at=digest.first_activity_at,
            last_activity_at=digest.last_activity_at,
            confirmed_wildlife_visit_count=digest.confirmed_wildlife_visit_count,
        )

    digest = build_digest(report, period_label="today")
    weekly_digest_response = (
        digest_response(build_digest(weekly_report, period_label="this week"))
        if weekly_report is not None
        else None
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
                entry,
                historical_status=species_historical_statuses.get(entry.label),
                change_status=change_status_by_label.get(entry.label),
                place_pattern=taxon_place_patterns.get(entry.label),
                representative_evidence=representative_evidence.get(entry.label),
                regularity_narrative=regularity_narratives.get(entry.label),
                seasonal_pattern=seasonal_patterns.get(entry.label),
                temporal_pattern=temporal_patterns.get(entry.label),
                habitat_associations=habitat_associations.get(entry.label),
                weather_associations=weather_associations.get(entry.label),
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
        historical_baseline=_historical_baseline_response(historical_place_intelligence.baseline),
        change_windows=_change_windows_response(change_summary.windows),
        overall_change_status=_overall_change_status_response(change_summary.overall),
        warnings=warnings,
        digest=digest_response(digest),
        weekly_digest=weekly_digest_response,
        activity_by_source=[_source_activity_response(entry) for entry in activity_by_source],
        source_quality_signals=[
            _source_quality_signal_response(signal) for signal in source_quality_signals
        ],
    )


def _place_biodiversity_taxon_entry_response(
    status: SpeciesHistoricalStatus,
) -> PlaceBiodiversityTaxonEntry:
    return PlaceBiodiversityTaxonEntry(
        label=status.taxon.label,
        display_name=status.taxon.display_name,
        category=status.taxon.category,
        is_species=status.taxon.is_species,
        historical_status=_species_historical_status_response(status),
    )


def place_biodiversity_summary_response(
    summary: PlaceBiodiversitySummary,
    *,
    provisional_taxa: list[DashboardTodaySpecies],
    habitat_context: PlaceHabitatContext,
    environmental_context: PlaceEnvironmentalContext,
) -> PlaceBiodiversitySummaryResponse:
    """See docs/biodiversity-place-intelligence-v1-contract.md. `summary`
    carries every authoritative taxon fact already; `provisional_taxa`/
    `habitat_context`/`environmental_context` are threaded in separately
    because they come from three other already-existing repository reads
    (`list_likely_species_overview`/`get_place_habitat_context`/
    `get_place_environmental_context_today`) this module has no reason to
    know how to produce itself."""

    return PlaceBiodiversitySummaryResponse(
        generated_at=summary.generated_at,
        historical_baseline=_historical_baseline_response(summary.historical_baseline),
        distinct_species_count=summary.distinct_species_count,
        taxa=[_place_biodiversity_taxon_entry_response(status) for status in summary.taxa],
        new_taxa=[_place_biodiversity_taxon_entry_response(status) for status in summary.new_taxa],
        regular_taxa=[_place_biodiversity_taxon_entry_response(status) for status in summary.regular_taxa],
        recently_observed_taxa=[
            _place_biodiversity_taxon_entry_response(status) for status in summary.recently_observed_taxa
        ],
        provisional_taxa=provisional_taxa,
        habitat_context=habitat_context,
        environmental_context=environmental_context,
        warnings=list(summary.warnings),
    )


# ---------------------------------------------------------------------------
# Year-over-Year Seasonality & Long-Term Place Memory v1 -- see
# `mockingbird.analytics.year_over_year_comparison`. `ProductRepository.
# place_year_over_year_comparison` is the only caller; it owns every
# database query and hands this module only already-resolved `PeriodInput`/
# `PeriodPresenceFacts`/comparison dataclasses, mirroring every other
# reshaping function in this module.
# ---------------------------------------------------------------------------


def _year_over_year_period_response(period: ComparablePeriod) -> PlaceYearOverYearPeriod:
    return PlaceYearOverYearPeriod(
        start_date=period.start_date,
        end_date=period.end_date,
        is_complete=period.is_complete,
        usable_day_count=period.usable_day_count,
        monitored_seconds=period.monitored_seconds,
        confirmed_wildlife_visit_count=period.confirmed_wildlife_visit_count,
    )


def _year_over_year_association_response(
    association: ConditionalAssociation | None,
) -> PlaceYearOverYearAssociation | None:
    if association is None:
        return None
    return PlaceYearOverYearAssociation(
        status=association.status,
        presence_days_in_condition=association.presence_days_in_condition,
        usable_days_in_condition=association.usable_days_in_condition,
        presence_days_out_of_condition=association.presence_days_out_of_condition,
        usable_days_out_of_condition=association.usable_days_out_of_condition,
    )


def place_year_over_year_comparison_response(
    comparison: PlaceYearOverYearComparisonFact,
) -> PlaceYearOverYearComparisonResponse:
    return PlaceYearOverYearComparisonResponse(
        policy_version=comparison.policy_version,
        current_period=_year_over_year_period_response(comparison.current_period),
        prior_period=_year_over_year_period_response(comparison.prior_period),
        status=comparison.status,
        overall_activity=comparison.overall_activity,
        association=_year_over_year_association_response(comparison.association),
        information_class=comparison.information_class,
    )


def _year_over_year_species_entry_response(
    entry: TaxonYearOverYearComparison,
) -> PlaceYearOverYearSpeciesEntry:
    return PlaceYearOverYearSpeciesEntry(
        label=entry.taxon.label,
        display_name=entry.taxon.display_name,
        category=entry.taxon.category,
        is_species=entry.taxon.is_species,
        status=entry.status,
        activity_direction=entry.activity_direction,
        association=_year_over_year_association_response(entry.association),
        current_first_observed_date=entry.current_first_observed_date,
        prior_first_observed_date=entry.prior_first_observed_date,
        first_observed_timing_status=entry.first_observed_timing_status,
        first_observed_day_difference=entry.first_observed_day_difference,
        first_observed_is_material=entry.first_observed_is_material,
    )


def place_year_over_year_response(
    *,
    generated_at: datetime,
    place: PlaceYearOverYearComparisonFact,
    notable_species_changes: Sequence[TaxonYearOverYearComparison],
) -> PlaceYearOverYearResponse:
    """`place` carries the Place-wide comparison; `notable_species_changes`
    should already be `select_notable_species_changes`'s own bounded,
    ranked output -- this function performs no ranking/filtering of its
    own, only reshaping."""

    return PlaceYearOverYearResponse(
        generated_at=generated_at,
        place=place_year_over_year_comparison_response(place),
        notable_species_changes=[
            _year_over_year_species_entry_response(entry) for entry in notable_species_changes
        ],
    )
