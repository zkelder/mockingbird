"""Place Intelligence & Reporting Foundation v1: pure, deterministic
current-period activity facts for a Place (today's single-site MockingBird
install; see docs/place-activity-report-contract.md).

This module computes structured report facts -- what wildlife appeared, how
often, when, and where -- from already-resolved per-Visit facts. It never
queries a database and never re-derives review truth: it is the aggregation
layer that sits *above* the existing canonical per-Visit resolver
(`ProductRepository._stream_visit_summary_from_models` /
`_visit_review_outcome`, see docs/review-decision-provenance-contract.md),
exactly the way `mockingbird.analytics.zone_insights` sits above
`ProductRepository.zone_insights`. A future repository-side adapter converts
real `StreamVisitSummary` rows (plus a taxonomy lookup) into `VisitFact`
before calling `compute_place_activity_report`; see the contract doc's
"Integration" section for the one remaining wiring step.

## Report truth precedence (do not re-derive this elsewhere)

Every Visit resolves to exactly one of three states, mirroring
`docs/review-decision-provenance-contract.md` and product-doctrine.md's
truth boundary -- human correction always wins, a provisional model
suggestion is usable only in truth's absence, and genuine abstention is
never silently discarded or fabricated into a species:

- **confirmed** -- an authority-eligible `ReviewLabel` exists
  (`resolution == "reviewed"`). This is reviewed truth and always wins over
  any suggestion, even a newer one.
- **provisional** -- no reviewed truth exists yet, but an automatic
  species-level `SpeciesSuggestion` does (`resolution == "needs_review"` and
  `provisional_taxon` is set). Usable, but never confused with truth.
- **unresolved** -- neither exists, or a reviewed Visit's label did not
  resolve to any known taxonomy row. Reported as its own honest count
  (`unresolved_visit_count`), never guessed into a species.

## Why Visit counts are not individual-animal counts

A Visit is a reviewable animal-centered activity session, not a unique
animal (see "Wildlife-native semantics" in product-doctrine.md): the same
bird can create several Visits across a day, and MockingBird has no
individual-animal identity model. Every count in `PlaceActivityReport` is a
Visit count -- "Northern Cardinal, 6 visits" is a valid fact; "6 Northern
Cardinals" is not something this module (or any caller of it) may claim.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, tzinfo
from enum import Enum, auto
from typing import Iterable, Literal

from mockingbird.analytics.zone_insights import (
    TimeInterval,
    interval_seconds,
    merge_intervals,
    subtract_intervals,
)
from mockingbird.wildlife_taxonomy import is_wildlife_category

# Display bucket for a Visit with no Zone context, matching the exact label
# the existing Dashboard Today aggregation already shows for the same case
# (`DashboardTodayZoneActivity.zone_name` default) -- reused for continuity,
# not reinvented.
NO_ZONE_LABEL = "No Zone"

# `category == "unknown"` in the current taxonomy means exactly two rows,
# "unknown_bird" and "unknown_animal" (see api/demo_data.py) -- a human
# explicitly confirming an animal was present while abstaining on species.
# That is confirmed wildlife activity with an unresolved taxon, not "not
# wildlife" and not a fabricated species; see `_Classification.
# CONFIRMED_SPECIES_UNRESOLVED`.
_UNKNOWN_CATEGORY = "unknown"
_FALSE_POSITIVE_CATEGORY = "false_positive"

# Matches `api.schemas.ReviewStatus` values by convention (this module
# stays dependency-free, so it does not import that Enum -- see the module
# docstring).
VisitResolution = Literal["needs_review", "reviewed", "rejected"]


@dataclass(frozen=True)
class TaxonFact:
    """One resolved taxonomy identification -- confirmed or provisional.

    Mirrors `api.schemas.TaxonomyLabel`'s reporting-relevant fields exactly
    (same `label`/`display_name`/`category`/`is_species` vocabulary) without
    importing it, so a future adapter can build this from a real
    `TaxonomyLabelModel` lookup with a direct field-for-field mapping.
    """

    label: str
    display_name: str
    category: str
    is_species: bool


@dataclass(frozen=True)
class VisitFact:
    """One Visit's already-resolved best-current-interpretation.

    This is an *adapted* fact, never a re-derived one: `resolution` and the
    two taxon fields must come from the existing canonical resolver
    (`ProductRepository._stream_visit_summary_from_models` /
    `_visit_review_outcome`), not from independently re-reading
    `ReviewLabel`/`SpeciesSuggestion` rows. See the module docstring.
    """

    visit_id: str
    zone_id: str | None
    zone_name: str | None
    activity_started_at: datetime
    resolution: VisitResolution
    # Populated only when `resolution == "reviewed"` and the reviewed label
    # resolved to a known taxonomy row; `None` with `resolution ==
    # "reviewed"` means a reviewed Visit whose label did not resolve to any
    # taxonomy row (for example a legacy free-text label) -- honestly
    # excluded, never guessed at.
    confirmed_taxon: TaxonFact | None = None
    # A species-level suggestion, when one exists. This mirrors the real
    # canonical `StreamVisitSummary`, which always carries its latest
    # suggestion independent of review status -- a Visit reviewed *after*
    # BioCLIP ran still has a `suggested_label` on file. `_classify` only
    # ever *consults* this when `resolution != "reviewed"`; a populated
    # `confirmed_taxon` always wins outright over a populated
    # `provisional_taxon` on the same fact, matching the truth boundary in
    # docs/review-decision-provenance-contract.md (never a blend of the
    # two). See `test_confirmed_truth_overrides_a_stale_provisional_
    # suggestion` in tests/test_place_activity_report.py.
    provisional_taxon: TaxonFact | None = None
    # Place / Yard Intelligence v2: which Source (camera) this Visit came
    # from, added so `source_activity.py` can group an already-gathered
    # `VisitFact` sequence by Source at zero additional queries -- mirrors
    # `zone_id`/`zone_name` above exactly (a real durable identifier plus a
    # display name, both optional so every pre-existing caller that never
    # populates them keeps working unchanged). `None` means "not resolved by
    # this caller," never "no Source" -- every real Visit has exactly one
    # Source in the current architecture.
    source_id: str | None = None
    source_name: str | None = None

    def __post_init__(self) -> None:
        if self.resolution != "reviewed" and self.confirmed_taxon is not None:
            raise ValueError(
                "VisitFact.confirmed_taxon is only meaningful when resolution == 'reviewed'"
            )


class _Classification(Enum):
    """Internal per-Visit resolution used only to accumulate report counts."""

    EXCLUDED = auto()
    NON_WILDLIFE = auto()
    UNRESOLVED = auto()
    CONFIRMED_SPECIES_UNRESOLVED = auto()
    PROVISIONAL_WILDLIFE = auto()
    CONFIRMED_WILDLIFE = auto()


def _classify(visit: VisitFact) -> _Classification:
    """Resolve one Visit's reporting bucket from already-resolved facts only.

    This never reads a database and never re-derives who is "right" --
    it only sorts an already-settled `VisitFact` into a report bucket.
    """

    if visit.resolution == "rejected":
        return _Classification.EXCLUDED

    if visit.resolution == "reviewed":
        taxon = visit.confirmed_taxon
        if taxon is None or taxon.category == _FALSE_POSITIVE_CATEGORY:
            # No resolvable taxon (data hygiene) or explicitly not activity
            # at all -- neither is a real Visit for reporting purposes.
            return _Classification.EXCLUDED
        if is_wildlife_category(taxon.category):
            return _Classification.CONFIRMED_WILDLIFE
        if taxon.category == _UNKNOWN_CATEGORY:
            return _Classification.CONFIRMED_SPECIES_UNRESOLVED
        # pet / person / vehicle / object / any other known non-wildlife
        # category -- see mockingbird.wildlife_taxonomy for the boundary.
        return _Classification.NON_WILDLIFE

    # resolution == "needs_review": no reviewed truth yet. A provisional
    # suggestion is usable only when it is itself species-level wildlife --
    # doctrine's "provisional model interpretation" boundary, not a license
    # to promote any suggestion to a report fact.
    taxon = visit.provisional_taxon
    if taxon is not None and is_wildlife_category(taxon.category) and taxon.is_species:
        return _Classification.PROVISIONAL_WILDLIFE
    return _Classification.UNRESOLVED


@dataclass
class _TaxonAccumulator:
    """Mutable, module-private accumulator; converted to a frozen
    `TaxonReportEntry` once accumulation finishes."""

    taxon: TaxonFact
    confirmed_visit_count: int = 0
    provisional_visit_count: int = 0
    first_activity_at: datetime | None = None
    last_activity_at: datetime | None = None

    def add(self, activity_started_at: datetime, *, is_confirmed: bool) -> None:
        if is_confirmed:
            self.confirmed_visit_count += 1
        else:
            self.provisional_visit_count += 1
        if self.first_activity_at is None or activity_started_at < self.first_activity_at:
            self.first_activity_at = activity_started_at
        if self.last_activity_at is None or activity_started_at > self.last_activity_at:
            self.last_activity_at = activity_started_at

    def to_entry(self) -> "TaxonReportEntry":
        assert self.first_activity_at is not None
        assert self.last_activity_at is not None
        return TaxonReportEntry(
            label=self.taxon.label,
            display_name=self.taxon.display_name,
            category=self.taxon.category,
            is_species=self.taxon.is_species,
            confirmed_visit_count=self.confirmed_visit_count,
            provisional_visit_count=self.provisional_visit_count,
            first_activity_at=self.first_activity_at,
            last_activity_at=self.last_activity_at,
        )


@dataclass(frozen=True)
class TaxonReportEntry:
    """One represented taxon (species-level or a coarser confirmed group
    such as "Squirrel" or generic "Bird") and its Visit-count backing.

    `confirmed_visit_count` and `provisional_visit_count` are kept separate
    -- never silently merged -- so a future UI can choose to show only
    confirmed activity, or both, without this module making that editorial
    call. See "confirmed vs provisional backing counts" in
    docs/place-activity-report-contract.md.
    """

    label: str
    display_name: str
    category: str
    is_species: bool
    confirmed_visit_count: int
    provisional_visit_count: int
    first_activity_at: datetime
    last_activity_at: datetime

    @property
    def total_visit_count(self) -> int:
        return self.confirmed_visit_count + self.provisional_visit_count


@dataclass(frozen=True)
class ZoneActivityEntry:
    zone_id: str | None
    zone_name: str
    wildlife_visit_count: int


@dataclass(frozen=True)
class HourActivityEntry:
    hour: int
    wildlife_visit_count: int


# Gate C -- Per-Species Zone + Time Pattern Intelligence v1 (see "Per-species
# Zone and time patterns" in docs/place-activity-report-contract.md). Reuses
# the exact 5-reviewed-Visit floor `mockingbird.analytics.zone_insights`
# already established for its own `busiest_supported_hour` claim -- one
# precedented "how much evidence before a 'most active' statement is
# trustworthy" judgment call, not a second, unrelated number invented here
# for a very similar claim. Below this floor, `zone_activity`/`hour_activity`
# still report their honest raw counts (a fact, never an overconfident
# claim); only `most_active_zone`/`most_active_hour` are withheld.
MIN_REVIEWED_VISITS_FOR_MOST_ACTIVE_PATTERN = 5


@dataclass(frozen=True)
class TaxonZoneActivityEntry:
    """One Zone's share of a single taxon's reviewed Visits. Deliberately a
    distinct type from `ZoneActivityEntry` above, even though the shape
    looks similar: that one's `wildlife_visit_count` mixes confirmed and
    provisional wildlife Visits of every taxon (the report-wide, truth-
    agnostic aggregate); `reviewed_visit_count` here is authoritatively-
    confirmed Visits of *this one taxon* only -- see `compute_taxon_place_
    patterns`'s truth contract. Reusing the older type's field name for a
    narrower meaning would silently blur that boundary for a future reader."""

    zone_id: str | None
    zone_name: str
    reviewed_visit_count: int


@dataclass(frozen=True)
class TaxonHourActivityEntry:
    local_hour: int
    reviewed_visit_count: int


@dataclass(frozen=True)
class TaxonPlacePattern:
    """Where and when one authoritatively-confirmed taxon has been reviewed
    at this Place -- an observational summary of MockingBird's own reviewed
    history ("7 reviewed visits at the Feeder, most often 7-8 AM"), never a
    behavioral or ecological claim ("prefers the feeder," "feeds at 7 AM").
    See "Per-species Zone and time patterns" in
    docs/place-activity-report-contract.md.

    `zone_activity`/`hour_activity` list only buckets that actually
    occurred (unlike `activity_by_hour` above, which always returns 24
    entries) -- a single taxon's reviewed history is typically sparse, so
    padding it with dozens of zero-count rows would obscure the real signal
    rather than clarify it.
    """

    reviewed_visit_count: int
    zone_activity: list[TaxonZoneActivityEntry]
    hour_activity: list[TaxonHourActivityEntry]
    # `None` below MIN_REVIEWED_VISITS_FOR_MOST_ACTIVE_PATTERN -- see
    # "Minimum support" in docs/place-activity-report-contract.md. Never the
    # "No Zone" bucket, mirroring `PlaceActivityReport.busiest_zone`'s
    # identical rule: only a real, user-drawn Zone can be "most active."
    most_active_zone: TaxonZoneActivityEntry | None
    most_active_hour: TaxonHourActivityEntry | None


@dataclass(frozen=True)
class CoverageGap:
    """One sub-window of the reporting period with no durable monitored
    evidence. Exposed as a raw fact, not a judgment: this module does not
    decide what counts as "material" -- see
    docs/place-activity-report-contract.md."""

    start_at: datetime
    end_at: datetime

    @property
    def duration_seconds(self) -> float:
        return (self.end_at - self.start_at).total_seconds()


@dataclass(frozen=True)
class CoverageSummary:
    """Monitoring coverage for the reporting period, built only from
    durable, already-persisted exposure history (see
    `MonitoringExposureIntervalModel`, the same durable ledger
    `ProductRepository._zone_insights_exposure` already reads) -- never
    inferred from armed policy, runtime checkpoints, or the calendar.
    `monitored_seconds` and `coverage_ratio` are `None` when no durable
    exposure history exists at all for the reported scope; that is an
    honest "cannot be computed yet" signal, never a fabricated zero or full
    coverage claim.
    """

    period_seconds: float
    monitored_seconds: float | None
    coverage_ratio: float | None
    history_available_from: datetime | None
    history_is_partial: bool
    gaps: list[CoverageGap]
    gaps_truncated: bool


# The smallest useful maturity classification a Daily Place Report needs:
# whether there is enough durable monitoring coverage behind it to trust a
# summary at all. Deliberately not "normal"/"unusual"/"declining" -- those
# require a historical baseline this module does not have (see "Baselines /
# trends" in the module docstring and docs/place-activity-report-contract.md).
ReportMaturity = Literal["no_data", "sparse", "usable"]

# Reuses the exact 2-hour boundary `mockingbird.analytics.zone_insights.
# quality_status` already established for its own "limited_monitoring"
# status (`healthy_monitored_seconds < 2 * 60 * 60`) -- one precedented
# product judgment call about "how much monitoring is enough to trust," not
# a second, unrelated threshold invented here.
_SPARSE_COVERAGE_THRESHOLD_SECONDS = 2 * 60 * 60


def compute_report_maturity(coverage: CoverageSummary | None) -> ReportMaturity:
    """Classify how much confidence a caller may place in this report.

    Purely a function of monitoring coverage, never of how much wildlife was
    recorded: a quiet, well-monitored day is "usable" with zero wildlife, and
    a busy-looking but barely-monitored window is "sparse" even with several
    Visits already counted, since a handful of Visits during two hours of
    real coverage says nothing trustworthy about the other twenty-two.

    - "no_data" -- no durable monitoring exposure history exists at all for
      the reported scope (`coverage` itself omitted, or its own
      `monitored_seconds` is `None`; see `CoverageSummary`'s docstring for
      why that is a distinct, honest "not yet computable" state, never a
      fabricated zero).
    - "sparse" -- real coverage exists but is below the threshold this
      codebase already uses elsewhere for "not enough to trust yet" (see
      `_SPARSE_COVERAGE_THRESHOLD_SECONDS`).
    - "usable" -- enough monitoring occurred to summarize the day.
    """

    if coverage is None or coverage.monitored_seconds is None:
        return "no_data"
    if coverage.monitored_seconds < _SPARSE_COVERAGE_THRESHOLD_SECONDS:
        return "sparse"
    return "usable"


@dataclass(frozen=True)
class PlaceActivityReport:
    """Deterministic current-period activity facts for a Place.

    Every count is a Visit count, not an individual-animal count (see the
    module docstring). "Observation" in product-doctrine.md's target
    vocabulary is today's reviewed Visit -- there is no separate persisted
    Observation record yet, so this report does not add a second set of
    fields for it.
    """

    period_start_at: datetime
    period_end_at: datetime
    generated_at: datetime

    # Honest accounting: these five buckets always sum to total_visit_count
    # (asserted by `compute_place_activity_report` and exercised by tests).
    total_visit_count: int
    confirmed_wildlife_visit_count: int
    provisional_wildlife_visit_count: int
    unresolved_visit_count: int
    non_wildlife_visit_count: int
    excluded_visit_count: int

    # Subset of confirmed_wildlife_visit_count with no resolvable taxon --
    # a human confirmed real wildlife but abstained on species/kind (an
    # "unknown_bird"/"unknown_animal" correction). Never folded into a
    # fabricated species entry; see "Unknown / unresolved" in
    # docs/place-activity-report-contract.md.
    confirmed_species_unresolved_visit_count: int

    # Headline count: confirmed + provisional wildlife Visits together.
    wildlife_visit_count: int

    distinct_taxa_count: int
    distinct_species_count: int
    taxa: list[TaxonReportEntry]

    first_activity_at: datetime | None
    last_activity_at: datetime | None

    activity_by_zone: list[ZoneActivityEntry]
    # Only a real, user-drawn Zone can be "busiest" -- the "No Zone" bucket
    # can appear in activity_by_zone but is never crowned busiest, since it
    # represents the absence of a Zone rather than a place the user defined.
    busiest_zone: ZoneActivityEntry | None
    # Always exactly 24 entries (hour 0-23), even when a hour had no
    # activity, so a caller can index/plot it directly without gap-filling.
    activity_by_hour: list[HourActivityEntry]

    # `None` when the caller did not supply monitoring coverage (see
    # `compute_coverage_summary`) -- distinct from a `CoverageSummary` whose
    # own `monitored_seconds` is `None` because no durable history exists.
    coverage: CoverageSummary | None

    # See `compute_report_maturity` -- the smallest useful classification of
    # whether this report's own monitoring coverage is sufficient to
    # summarize the day with any confidence. Purely a function of coverage,
    # never of activity counts.
    maturity: ReportMaturity


def compute_place_activity_report(
    visits: Iterable[VisitFact],
    *,
    period_start_at: datetime,
    period_end_at: datetime,
    local_timezone: tzinfo = UTC,
    coverage: CoverageSummary | None = None,
    generated_at: datetime | None = None,
) -> PlaceActivityReport:
    """Compute one deterministic Place activity report.

    `visits` may be a superset of the reporting period (any Visit outside
    `[period_start_at, period_end_at)` is dropped here) but must already be
    scoped to the correct Place/Streams/Zones by the caller -- this module
    has no Stream/Zone/Place membership concept of its own and never
    queries anything, so it cannot accidentally widen a caller's scope.
    Zone aggregation groups by `zone_id` (a real, globally unique key), not
    by `zone_name`, so two different Streams each having a same-named Zone
    are never merged into one bucket.
    """

    if period_end_at <= period_start_at:
        raise ValueError("period_end_at must be after period_start_at")

    in_period = [
        visit
        for visit in visits
        if period_start_at <= visit.activity_started_at < period_end_at
    ]

    confirmed_wildlife_with_taxon = 0
    confirmed_species_unresolved = 0
    provisional_wildlife = 0
    unresolved = 0
    non_wildlife = 0
    excluded = 0

    wildlife: list[VisitFact] = []
    taxa_accum: dict[str, _TaxonAccumulator] = {}

    for visit in in_period:
        classification = _classify(visit)

        if classification is _Classification.EXCLUDED:
            excluded += 1
            continue
        if classification is _Classification.NON_WILDLIFE:
            non_wildlife += 1
            continue
        if classification is _Classification.UNRESOLVED:
            unresolved += 1
            continue

        wildlife.append(visit)

        if classification is _Classification.CONFIRMED_SPECIES_UNRESOLVED:
            confirmed_species_unresolved += 1
            continue
        if classification is _Classification.PROVISIONAL_WILDLIFE:
            provisional_wildlife += 1
            taxon = visit.provisional_taxon
            assert taxon is not None
            taxa_accum.setdefault(taxon.label, _TaxonAccumulator(taxon)).add(
                visit.activity_started_at, is_confirmed=False
            )
            continue

        # CONFIRMED_WILDLIFE with a resolved taxon.
        confirmed_wildlife_with_taxon += 1
        taxon = visit.confirmed_taxon
        assert taxon is not None
        taxa_accum.setdefault(taxon.label, _TaxonAccumulator(taxon)).add(
            visit.activity_started_at, is_confirmed=True
        )

    confirmed_wildlife_visit_count = confirmed_wildlife_with_taxon + confirmed_species_unresolved
    wildlife_visit_count = confirmed_wildlife_visit_count + provisional_wildlife
    total_visit_count = len(in_period)
    assert total_visit_count == (
        confirmed_wildlife_visit_count
        + provisional_wildlife
        + unresolved
        + non_wildlife
        + excluded
    ), "internal accounting error: report buckets must sum to total_visit_count"

    zone_counts: dict[tuple[str | None, str], int] = {}
    hour_counts: dict[int, int] = {hour: 0 for hour in range(24)}
    first_activity_at: datetime | None = None
    last_activity_at: datetime | None = None
    for visit in wildlife:
        zone_key = (visit.zone_id, visit.zone_name or NO_ZONE_LABEL)
        zone_counts[zone_key] = zone_counts.get(zone_key, 0) + 1
        local_hour = visit.activity_started_at.astimezone(local_timezone).hour
        hour_counts[local_hour] += 1
        if first_activity_at is None or visit.activity_started_at < first_activity_at:
            first_activity_at = visit.activity_started_at
        if last_activity_at is None or visit.activity_started_at > last_activity_at:
            last_activity_at = visit.activity_started_at

    activity_by_zone = [
        ZoneActivityEntry(zone_id=zone_id, zone_name=zone_name, wildlife_visit_count=count)
        for (zone_id, zone_name), count in sorted(
            zone_counts.items(),
            key=lambda item: (-item[1], item[0][1], item[0][0] or ""),
        )
    ]
    busiest_zone = next(
        (entry for entry in activity_by_zone if entry.zone_id is not None), None
    )
    activity_by_hour = [
        HourActivityEntry(hour=hour, wildlife_visit_count=hour_counts[hour])
        for hour in range(24)
    ]

    taxa = sorted(
        (accumulator.to_entry() for accumulator in taxa_accum.values()),
        key=lambda entry: (-entry.total_visit_count, entry.display_name.lower(), entry.label),
    )

    return PlaceActivityReport(
        period_start_at=period_start_at,
        period_end_at=period_end_at,
        generated_at=generated_at or datetime.now(UTC),
        total_visit_count=total_visit_count,
        confirmed_wildlife_visit_count=confirmed_wildlife_visit_count,
        provisional_wildlife_visit_count=provisional_wildlife,
        unresolved_visit_count=unresolved,
        non_wildlife_visit_count=non_wildlife,
        excluded_visit_count=excluded,
        confirmed_species_unresolved_visit_count=confirmed_species_unresolved,
        wildlife_visit_count=wildlife_visit_count,
        distinct_taxa_count=len(taxa),
        distinct_species_count=sum(1 for entry in taxa if entry.is_species),
        taxa=taxa,
        first_activity_at=first_activity_at,
        last_activity_at=last_activity_at,
        activity_by_zone=activity_by_zone,
        busiest_zone=busiest_zone,
        activity_by_hour=activity_by_hour,
        coverage=coverage,
        maturity=compute_report_maturity(coverage),
    )


def compute_taxon_place_patterns(
    visits: Iterable[VisitFact],
    *,
    local_timezone: tzinfo = UTC,
) -> dict[str, TaxonPlacePattern]:
    """Compute each authoritatively-confirmed taxon's Zone/time-of-day
    pattern from already-resolved Visit facts (Gate C -- Per-Species Zone +
    Time Pattern Intelligence v1; see "Per-species Zone and time patterns"
    in docs/place-activity-report-contract.md). Keyed by taxon label.

    Truth contract: reuses `_classify` verbatim, so only a Visit `_classify`
    resolves to `CONFIRMED_WILDLIFE` (`resolution == "reviewed"` and a
    resolved, wildlife-category, non-"unknown" taxon) contributes. A
    provisional `SpeciesSuggestion`, an unresolved Visit, and a confirmed
    but taxonomically-unresolved ("unknown_bird"/"unknown_animal")
    abstention are all excluded -- the identical boundary `compute_place_
    activity_report`'s own per-taxon accumulation already enforces, so this
    can never independently drift from it. Callers wanting generic,
    truth-agnostic wildlife activity should read `PlaceActivityReport.
    activity_by_zone`/`activity_by_hour` instead; this function answers a
    narrower, per-species question those fields cannot.

    Zone attribution reuses each Visit's own `zone_id`/`zone_name` exactly
    as given -- unlike some callers of the canonical per-Visit resolver,
    this function never falls back to an Event-level Zone when a Visit's
    own is absent. That fallback exists for the single-subject Visit/Event
    history this product started with; Multi-Subject Visit Assembly
    (docs/multi-subject-visit-assembly-review-v1.md) can now put several
    independently-geometried sibling Visits on one Event, and an Event-level
    fallback would silently lend the Event-founding sibling's Zone to a
    later sibling that was genuinely never inside it (or was outside every
    drawn Zone entirely) -- exactly the "sibling evidence/geometry
    borrowing" this milestone forbids. A Visit with its own `zone_id ==
    None` is honestly "No Zone" here, full stop.

    Callers pass whichever bounded Visit set they want a pattern computed
    over (today's report period, a trailing historical window, or a
    per-label Bird Log scope) -- this function has no period/window concept
    of its own.
    """

    zone_counts: dict[str, dict[tuple[str | None, str], int]] = {}
    hour_counts: dict[str, dict[int, int]] = {}
    taxon_by_label: dict[str, TaxonFact] = {}

    for visit in visits:
        if _classify(visit) is not _Classification.CONFIRMED_WILDLIFE:
            continue
        taxon = visit.confirmed_taxon
        assert taxon is not None
        taxon_by_label.setdefault(taxon.label, taxon)

        zone_key = (visit.zone_id, visit.zone_name or NO_ZONE_LABEL)
        zone_bucket = zone_counts.setdefault(taxon.label, {})
        zone_bucket[zone_key] = zone_bucket.get(zone_key, 0) + 1

        local_hour = visit.activity_started_at.astimezone(local_timezone).hour
        hour_bucket = hour_counts.setdefault(taxon.label, {})
        hour_bucket[local_hour] = hour_bucket.get(local_hour, 0) + 1

    patterns: dict[str, TaxonPlacePattern] = {}
    for label in taxon_by_label:
        zone_entries = [
            TaxonZoneActivityEntry(zone_id=zone_id, zone_name=zone_name, reviewed_visit_count=count)
            for (zone_id, zone_name), count in sorted(
                zone_counts[label].items(),
                key=lambda item: (-item[1], item[0][1], item[0][0] or ""),
            )
        ]
        hour_entries = [
            TaxonHourActivityEntry(local_hour=hour, reviewed_visit_count=count)
            for hour, count in sorted(
                hour_counts[label].items(),
                key=lambda item: (-item[1], item[0]),
            )
        ]
        reviewed_visit_count = sum(zone_counts[label].values())
        has_support = reviewed_visit_count >= MIN_REVIEWED_VISITS_FOR_MOST_ACTIVE_PATTERN

        most_active_zone = next((entry for entry in zone_entries if entry.zone_id is not None), None)
        most_active_hour = hour_entries[0] if hour_entries else None

        patterns[label] = TaxonPlacePattern(
            reviewed_visit_count=reviewed_visit_count,
            zone_activity=zone_entries,
            hour_activity=hour_entries,
            most_active_zone=most_active_zone if has_support else None,
            most_active_hour=most_active_hour if has_support else None,
        )

    return patterns


def compute_coverage_summary(
    *,
    period_start_at: datetime,
    period_end_at: datetime,
    monitored_intervals: Iterable[TimeInterval],
    history_available_from: datetime | None,
    max_gaps: int = 20,
) -> CoverageSummary:
    """Compute monitoring coverage for one reporting period from durable
    healthy-frame intervals only (see `MonitoringExposureIntervalModel`).

    Reuses the exact interval math `mockingbird.analytics.zone_insights`
    already uses for the same underlying data (`merge_intervals`,
    `interval_seconds`, `subtract_intervals`) rather than a second
    implementation. `monitored_intervals` may extend outside the period;
    they are clipped here.

    A caller combining several Streams into one Place-level coverage figure
    is responsible for the same all-or-nothing honesty policy Zone Insights
    already applies (`ProductRepository.zone_insights`'s aggregate exposure
    construction): pass `history_available_from=None` when *any* in-scope
    Stream has no durable exposure history at all, rather than silently
    averaging a partial figure across Streams with and without history.
    """

    if period_end_at <= period_start_at:
        raise ValueError("period_end_at must be after period_start_at")

    period_seconds = (period_end_at - period_start_at).total_seconds()

    if history_available_from is None:
        return CoverageSummary(
            period_seconds=period_seconds,
            monitored_seconds=None,
            coverage_ratio=None,
            history_available_from=None,
            history_is_partial=False,
            gaps=[],
            gaps_truncated=False,
        )

    period = TimeInterval(period_start_at, period_end_at)
    clipped = [
        clipped_interval
        for interval in monitored_intervals
        if (clipped_interval := interval.clipped(period_start_at, period_end_at)) is not None
    ]
    merged = merge_intervals(clipped)
    monitored_seconds = interval_seconds(merged)
    coverage_ratio = min(1.0, monitored_seconds / period_seconds) if period_seconds > 0 else None

    gap_intervals = subtract_intervals([period], merged)
    gaps = [CoverageGap(gap.start_at, gap.end_at) for gap in gap_intervals[:max_gaps]]

    return CoverageSummary(
        period_seconds=period_seconds,
        monitored_seconds=monitored_seconds,
        coverage_ratio=coverage_ratio,
        history_available_from=history_available_from,
        history_is_partial=period_start_at < history_available_from,
        gaps=gaps,
        gaps_truncated=len(gap_intervals) > max_gaps,
    )
