"""Historical Baseline Maturity + New/Regular Species v1: pure, deterministic
Place-history facts (see docs/historical-baseline-maturity-contract.md).

This is the first slice of product-doctrine.md's "Place Intelligence" layer
that `place-activity-report-contract.md` deliberately left unimplemented
("Baselines / trends... requires sufficient history and explicit
baseline-readiness semantics this milestone does not define"). It answers
two bounded questions a single day's report cannot:

- Is this Place's accumulated monitoring history deep enough to make any
  new-vs-regular statement useful at all (`HistoricalPlaceBaseline`)?
- For one taxon, is today's confirmation its first-ever record, and has it
  recurred often enough across genuinely-monitored days to call it a
  regular visitor here (`SpeciesHistoricalStatus`)?

It deliberately does NOT implement anomaly/change detection, "more/less
than normal," seasonality, or ecological rarity -- see the contract doc's
"Explicit non-goals."

## Reuse, not a second analytics path

Like `mockingbird.analytics.place_activity_report`, this module never
queries a database and never re-derives review truth: it consumes the exact
same `VisitFact`/`TaxonFact`/`_classify` truth-precedence resolution that
module already owns (imported directly, not reimplemented), and the same
`TimeInterval`/`merge_intervals`/`interval_seconds` exposure-interval math
`mockingbird.analytics.zone_insights` already owns. A repository-side
adapter (`ProductRepository.historical_place_baseline`, see the contract
doc's "Integration" section) is the only place that touches the database.

## Every threshold here is reused, not invented

- `USABLE_DAY_MONITORED_SECONDS_THRESHOLD` is the exact 2-hour boundary
  `zone_insights.quality_status` and `place_activity_report.
  compute_report_maturity` already established for "enough monitoring to
  trust a period" -- the same judgment call, just applied per calendar day
  instead of per report period.
- `MIN_DISTINCT_USABLE_DAYS_FOR_REGULAR` (3) reuses the exact number
  `ProductRepository._dashboard_today_summary`'s pre-existing
  `recent_regulars` concept already uses for "distinct days, not raw Visit
  count, is what makes a pattern" -- see the contract doc for why that
  existing surface answers a different (recent-activity, not
  Place-baseline) question and is left untouched, not replaced, here.
- `MIN_USABLE_DAYS_FOR_DEVELOPING_BASELINE` reuses that same "3" for "is
  this more than a fluke."
- `HISTORICAL_BASELINE_WINDOW_DAYS` (366) reuses `PlaceActivityReportRequest`'s
  own existing maximum report span, not a new cap.

## Why a bounded window, plus a separate all-time lookup

Regularity and baseline maturity are scoped to a bounded, recent window
(`HISTORICAL_BASELINE_WINDOW_DAYS`) deliberately -- a species regular five
years ago but silent since should not still read "Regular here" forever,
and an unbounded per-day scan would not stay cheap as retained history
grows. But "no earlier authoritative Observation of this taxon exists for
the Place" (the "new" contract) is an all-time claim, not a windowed one:
narrowing it to the same bounded window would let a taxon that first
appeared just outside the window incorrectly read "new" again. Callers
therefore supply two different shapes of already-resolved fact: bounded
per-Visit facts for regularity, and a separate, cheap all-time
first/last-confirmed-per-taxon lookup (a `GROUP BY taxon` aggregate, not a
per-Visit scan) for the "new" determination. See `place_activity_report_
contract.md`'s "Historical window" section.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, tzinfo
from typing import AbstractSet, Iterable, Literal, Mapping

from mockingbird.analytics.place_activity_report import (
    TaxonFact,
    VisitFact,
    _Classification,
    _classify,
)
from mockingbird.analytics.zone_insights import TimeInterval, merge_intervals

# Reuses the exact 2-hour "enough monitoring to trust" boundary
# `zone_insights.quality_status` / `place_activity_report.
# compute_report_maturity` already established -- see the module docstring.
USABLE_DAY_MONITORED_SECONDS_THRESHOLD = 2 * 60 * 60

# A Place-wide baseline needs more than a fluke's worth of usable days
# before "regular"/"new" claims are useful at all -- reuses the same "3"
# `_dashboard_today_summary`'s existing regularity concept already uses.
MIN_USABLE_DAYS_FOR_DEVELOPING_BASELINE = 3

# "Established" is deliberately more than double the developing floor: a
# full week's worth of genuinely well-monitored (not just calendar) days --
# an intuitive, explainable product unit, and comfortably above what real
# retained field-testing history reaches early on (see the contract doc's
# real-data grounding).
MIN_USABLE_DAYS_FOR_ESTABLISHED_BASELINE = 7

# Coverage-aware upgrade of the same "3 distinct days" precedent: a species
# must recur on at least this many *usable* (not just any) monitored days
# within the bounded window before it is presented as a regular visitor.
MIN_DISTINCT_USABLE_DAYS_FOR_REGULAR = 3

# Reuses `PlaceActivityReportRequest`'s own existing 366-day maximum report
# span (see place_activity_report_contract.md) as the bounded historical
# window for regularity/baseline-maturity computation, not a new cap.
HISTORICAL_BASELINE_WINDOW_DAYS = 366

BaselineMaturity = Literal["insufficient", "developing", "established"]

# "new" and "first_record" are the SAME underlying fact (this taxon's
# all-time-earliest confirmed record falls within the current report
# period) presented with maturity-appropriate language -- never both, never
# neither, for the same taxon/period. "regular" and "seen_before" are the
# only other possibilities, and both are structurally exclusive with the
# first two (a taxon confirmed for the very first time this period cannot
# also have 3+ prior distinct usable days). See `compute_species_historical_
# statuses`.
SpeciesHistoricalStatusValue = Literal["new", "first_record", "regular", "seen_before"]


def is_usable_day(monitored_seconds: float | None) -> bool:
    """Whether one calendar day's monitored duration is enough to count
    toward baseline maturity or species regularity. `None` (no durable
    exposure that day) is never usable -- an honest absence, not a zero."""

    return monitored_seconds is not None and monitored_seconds >= USABLE_DAY_MONITORED_SECONDS_THRESHOLD


def usable_dates_from_daily_monitored_seconds(
    daily_monitored_seconds: Mapping[date, float],
) -> frozenset[date]:
    """The subset of `daily_monitored_seconds`'s keys that clear the usable
    threshold -- the single place that threshold is ever applied, so a
    caller never re-derives it independently for baseline maturity vs.
    per-species regularity (both must agree on the same usable-day set)."""

    return frozenset(day for day, seconds in daily_monitored_seconds.items() if is_usable_day(seconds))


def bucket_intervals_by_local_day(
    intervals: Iterable[TimeInterval],
    *,
    window_start_at: datetime,
    window_end_at: datetime,
    local_timezone: tzinfo,
) -> dict[date, float]:
    """Union durable monitoring exposure per Place-local calendar day.

    Reuses `zone_insights.merge_intervals` for the same overlap-safe union
    math `zone_insights`/`place_activity_report` already rely on for
    coverage, then splits at each Place-local midnight so a day spanning
    intervals from more than one Stream, or an interval spanning a local
    midnight, attributes each second to the correct local day -- the same
    per-instant `astimezone(local_timezone)` discipline `place_activity_
    report.compute_place_activity_report` already applies per-Visit (see
    "Local time and DST correctness" in place_activity_report_contract.md).
    Each local-midnight boundary is computed fresh via `datetime.combine`,
    never by adding a fixed 24-hour timedelta to a previous boundary, so a
    real DST transition inside the window still produces the correct
    wall-clock-local boundaries.
    """

    clipped = [
        clipped_interval
        for interval in intervals
        if (clipped_interval := interval.clipped(window_start_at, window_end_at)) is not None
    ]
    merged = merge_intervals(clipped)

    totals: dict[date, float] = {}
    for interval in merged:
        cursor = interval.start_at
        while cursor < interval.end_at:
            local_day = cursor.astimezone(local_timezone).date()
            next_local_midnight = datetime.combine(
                local_day + timedelta(days=1), time.min, tzinfo=local_timezone
            )
            segment_end = min(interval.end_at, next_local_midnight)
            totals[local_day] = totals.get(local_day, 0.0) + (segment_end - cursor).total_seconds()
            cursor = segment_end

    return totals


def compute_baseline_maturity(usable_day_count: int) -> BaselineMaturity:
    """Classify how much confidence a caller may place in a new/regular
    species statement -- purely a function of accumulated usable-day count,
    never of taxa/Visit counts (mirrors `compute_report_maturity`'s own
    discipline) and never of raw calendar age alone: a system installed 30
    days ago but monitored for 4 hours stays "insufficient" here, exactly as
    the milestone requires."""

    if usable_day_count >= MIN_USABLE_DAYS_FOR_ESTABLISHED_BASELINE:
        return "established"
    if usable_day_count >= MIN_USABLE_DAYS_FOR_DEVELOPING_BASELINE:
        return "developing"
    return "insufficient"


@dataclass(frozen=True)
class HistoricalPlaceBaseline:
    """Place-wide historical facts for the bounded window ending at
    `window_end_at`. Never claims more precision than it has: `total_
    monitored_seconds` is `None` specifically when no durable exposure
    history exists at all (mirrors `CoverageSummary.monitored_seconds`'s
    identical convention), distinct from a real, known zero."""

    window_start_at: datetime
    window_end_at: datetime
    usable_day_count: int
    total_monitored_seconds: float | None
    maturity: BaselineMaturity
    distinct_taxa_count: int
    earliest_authoritative_record_at: datetime | None
    latest_authoritative_record_at: datetime | None


def compute_historical_place_baseline(
    *,
    window_start_at: datetime,
    window_end_at: datetime,
    usable_dates: AbstractSet[date],
    has_any_monitoring_history: bool,
    total_monitored_seconds: float | None,
    distinct_taxa_count: int,
    earliest_authoritative_record_at: datetime | None,
    latest_authoritative_record_at: datetime | None,
) -> HistoricalPlaceBaseline:
    """Compute one deterministic Place-wide historical baseline.

    `usable_dates` should come from `usable_dates_from_daily_monitored_
    seconds` so baseline maturity and per-species regularity always agree
    on the same usable-day set. `has_any_monitoring_history` is a separate
    signal from an empty `usable_dates` set: a Place monitored heavily a
    year ago but not at all within this bounded window has real (zero)
    `total_monitored_seconds` for the window, not an honest "not yet
    computable" `None` -- that distinction is only knowable from the
    caller's own durable-history existence check (mirrors `CoverageSummary`/
    `_place_activity_coverage_summary`'s `history_available_from`), not from
    `usable_dates` alone.
    """

    usable_day_count = len(usable_dates)
    return HistoricalPlaceBaseline(
        window_start_at=window_start_at,
        window_end_at=window_end_at,
        usable_day_count=usable_day_count,
        total_monitored_seconds=total_monitored_seconds if has_any_monitoring_history else None,
        maturity=compute_baseline_maturity(usable_day_count),
        distinct_taxa_count=distinct_taxa_count,
        earliest_authoritative_record_at=earliest_authoritative_record_at,
        latest_authoritative_record_at=latest_authoritative_record_at,
    )


@dataclass(frozen=True)
class SpeciesHistoricalStatus:
    """One taxon's historical presence at this Place, as of `period_end_at`.

    `first_confirmed_at`/`last_confirmed_at` are all-time facts (never
    bounded to the regularity window -- see the module docstring). `distinct_
    confirmed_days`/`distinct_confirmed_usable_days`/`total_confirmed_count`
    are bounded to the historical window: how present this taxon has been
    *recently* (within `HISTORICAL_BASELINE_WINDOW_DAYS`), not cumulatively
    over the Place's entire lifetime.
    """

    taxon: TaxonFact
    first_confirmed_at: datetime
    last_confirmed_at: datetime
    distinct_confirmed_days: int
    distinct_confirmed_usable_days: int
    total_confirmed_count: int
    status: SpeciesHistoricalStatusValue


def compute_species_historical_statuses(
    window_visits: Iterable[VisitFact],
    *,
    taxa: Mapping[str, TaxonFact],
    all_time_first_confirmed_at: Mapping[str, datetime],
    all_time_last_confirmed_at: Mapping[str, datetime],
    usable_dates: AbstractSet[date],
    local_timezone: tzinfo,
    period_start_at: datetime,
    period_end_at: datetime,
    baseline_maturity: BaselineMaturity,
) -> list[SpeciesHistoricalStatus]:
    """One `SpeciesHistoricalStatus` per all-time-confirmed taxon.

    `taxa`, `all_time_first_confirmed_at`, and `all_time_last_confirmed_at`
    must share the same key set -- every taxon this Place has ever
    authoritatively confirmed, however long ago, so a taxon dormant for
    longer than the bounded window still gets an honest "seen_before" entry
    rather than silently vanishing. `window_visits` may be any mix of
    resolutions/classifications (this function applies the exact same
    `_classify` truth-precedence `place_activity_report` uses, so a
    provisional SpeciesSuggestion or an "unknown_bird"/"unknown_animal"
    abstention can never contribute to a named taxon's regularity here,
    matching the truth contract) and should already be scoped to the
    bounded historical window.

    Status assignment, in priority order:

    1. `"new"` / `"first_record"` -- this taxon's all-time-earliest confirmed
       record falls within `[period_start_at, period_end_at)`. The only
       difference is `baseline_maturity`: "new" only when "established"
       (implying real ecological novelty is a supportable claim);
       "first_record" otherwise (a true first record, without implying the
       Place's history is deep enough to call it ecologically novel).
    2. `"regular"` -- confirmed on at least `MIN_DISTINCT_USABLE_DAYS_FOR_
       REGULAR` distinct *usable* days within the window. Structurally
       impossible while `baseline_maturity == "insufficient"` (fewer than
       `MIN_USABLE_DAYS_FOR_DEVELOPING_BASELINE` usable days exist Place-wide
       at all) -- asserted explicitly below so a future threshold change
       cannot silently violate it.
    3. `"seen_before"` -- confirmed previously, neither new this period nor
       (yet) a regular.
    """

    if taxa.keys() != all_time_first_confirmed_at.keys() or taxa.keys() != all_time_last_confirmed_at.keys():
        raise ValueError(
            "taxa, all_time_first_confirmed_at, and all_time_last_confirmed_at must share the same taxon keys"
        )

    window_dates_by_taxon: dict[str, set[date]] = {}
    window_counts_by_taxon: dict[str, int] = {}
    for visit in window_visits:
        if _classify(visit) is not _Classification.CONFIRMED_WILDLIFE:
            # In particular, this already excludes CONFIRMED_SPECIES_
            # UNRESOLVED (an "unknown_bird"/"unknown_animal" abstention --
            # confirmed wildlife activity, but never a named taxon's
            # historical record, per the truth contract in the module
            # docstring) and PROVISIONAL_WILDLIFE (a SpeciesSuggestion with
            # no reviewed truth yet -- never eligible to create or extend
            # named-species history, per product-doctrine.md's truth
            # boundary).
            continue
        # `_classify` returning CONFIRMED_WILDLIFE already guarantees
        # `confirmed_taxon is not None` (see its own branching) -- mirrors
        # `compute_place_activity_report`'s identical `assert` at its own
        # CONFIRMED_WILDLIFE call site, not a second None-check-and-skip.
        taxon = visit.confirmed_taxon
        assert taxon is not None
        local_date = visit.activity_started_at.astimezone(local_timezone).date()
        window_dates_by_taxon.setdefault(taxon.label, set()).add(local_date)
        window_counts_by_taxon[taxon.label] = window_counts_by_taxon.get(taxon.label, 0) + 1

    statuses: list[SpeciesHistoricalStatus] = []
    for label, taxon in taxa.items():
        confirmed_dates = window_dates_by_taxon.get(label, set())
        distinct_confirmed_usable_days = len(confirmed_dates & usable_dates)
        first_confirmed_at = all_time_first_confirmed_at[label]
        is_first_in_period = period_start_at <= first_confirmed_at < period_end_at
        is_regular = distinct_confirmed_usable_days >= MIN_DISTINCT_USABLE_DAYS_FOR_REGULAR

        if is_regular and baseline_maturity == "insufficient":
            raise AssertionError(
                "regular status is structurally impossible while baseline maturity is insufficient: "
                f"{distinct_confirmed_usable_days} distinct usable days confirmed for {label!r} but "
                "fewer usable days than MIN_USABLE_DAYS_FOR_DEVELOPING_BASELINE exist Place-wide"
            )

        status: SpeciesHistoricalStatusValue
        if is_first_in_period:
            status = "new" if baseline_maturity == "established" else "first_record"
        elif is_regular:
            status = "regular"
        else:
            status = "seen_before"

        statuses.append(
            SpeciesHistoricalStatus(
                taxon=taxon,
                first_confirmed_at=first_confirmed_at,
                last_confirmed_at=all_time_last_confirmed_at[label],
                distinct_confirmed_days=len(confirmed_dates),
                distinct_confirmed_usable_days=distinct_confirmed_usable_days,
                total_confirmed_count=window_counts_by_taxon.get(label, 0),
                status=status,
            )
        )

    return sorted(statuses, key=lambda entry: (entry.taxon.display_name.lower(), entry.taxon.label))
