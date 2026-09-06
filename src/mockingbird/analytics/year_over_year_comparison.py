"""Year-over-Year Seasonality & Long-Term Place Memory v1: pure, bounded
comparison of confirmed wildlife activity in one calendar period against the
same calendar period one year earlier -- "how does this season compare with
the same time last year," at this Place, never a population/ecological
trend claim (see product-doctrine.md's "Place Intelligence" and "External
ecological context").

## No new statistical primitive

Like `feature_change_comparison.py` and `habitat_association.py`, this
module invents no new threshold shape. Both the Place-level and per-species
comparison are a thin date-set builder around `conditional_association.
compute_conditional_association` -- the exact same presence-day-rate
primitive `place_change_summary`/`seasonal_pattern`/`habitat_association`/
`feature_change_comparison` already use, reused here with `condition_dates`
set to the current period's own calendar days and `usable_dates` narrowed to
exactly the two compared periods' own usable days, so `compute_conditional_
association`'s "in condition" / "out of condition" split becomes exactly
"current period" / "prior-year comparable period" with zero new math:

    usable_in_condition     = usable_dates & condition_dates     = current.usable_dates
    usable_out_of_condition = usable_dates - condition_dates     = prior.usable_dates

(true whenever the two periods share no calendar date, which a year-apart
comparable period always satisfies -- see `comparable_prior_period`). This
gives every threshold this milestone needs -- the minimum-usable-days floor
on each side, the minimum rate-difference gate -- from one already-accepted,
already-tested module, not a second one invented for this milestone. It also
means the verdict is a coverage-normalized *presence-day rate*, not a raw
Visit-count or Visits-per-hour ratio: comparing "on how many well-monitored
days did this happen at all" is structurally immune to the exact
over-counting trap product-doctrine.md's own worked example describes (100
Visits across a handful of very active hours is not "more active" than 90
Visits spread across a longer, calmer, well-monitored season) without this
module needing to separately reason about camera-hours at all -- the
underlying `usable_dates` set already encodes that (see
`historical_baseline.USABLE_DAY_MONITORED_SECONDS_THRESHOLD`).

## Reuse, not a second analytics/query path

This module never queries a database, never re-derives review truth, and
never computes a usable-day set of its own: callers (`ProductRepository.
place_year_over_year_comparison`) supply each period's own `PeriodInput`,
already built from the identical `_monitoring_exposure_intervals_and_
history` -> `bucket_intervals_by_local_day` -> `usable_dates_from_daily_
monitored_seconds` chain `_historical_usable_dates` already composes, and
already had any cross-camera-associated duplicate Visit excluded via
`_associated_visit_ids_to_exclude_from_counting` before this module ever
sees a presence date -- exactly the same discipline `source_activity.py`
documents for its own caller contract. `taxa`/presence-dates-by-taxon should
be gathered the same one-pass way `place_change_summary._presence_dates_by_
taxon_and_overall` and `seasonal_pattern.presence_dates_by_taxon` already
do, over each period's own bounded (not 366-day-trailing) Visit query --
this module has no Visit/database concept of its own.

## `current_period`/`prior_period`, not `pre`/`post`

`feature_change_comparison.py`'s `pre_start`/`post_end` naming fits its own
shape -- one instant (`effective_date`) splitting a single before/after
window. Year-over-year compares two independently-anchored *recurring*
calendar periods a year apart, not a split around one event; `current`/
`prior` (matching this milestone's own governing brief, section 22) is the
clearer vocabulary for that shape, so this module uses it deliberately
rather than forcing the `pre`/`post` convention onto a relationship it does
not describe.

## Comparable-period contract

`comparable_prior_period` shifts both boundary dates of `[current_start_
date, current_end_date)` back by exactly one calendar year independently
(`date.replace(year=...)`, not a fixed 365/366-day timedelta -- see its own
docstring for the deterministic Feb-29 rule). The two periods therefore
normally share the identical day-count span; the one disclosed exception is
a leap-day span mismatch (a current period crossing Feb 29 in a leap year
shifts to a same-shaped prior period one day shorter, since the prior
non-leap year has no Feb 29) -- accepted, not defended against, because the
underlying comparison is a *rate* (presence days / usable days) on each side
independently, never a raw count assumed to share one denominator, so a
one-day span difference in that narrow case does not bias the result.

## Partial-period honesty

`PeriodInput.is_complete` is a caller-supplied fact (this module never reads
a clock -- see "no wall-clock reads" below): `False` only for a current,
still-in-progress calendar period (a month not yet finished). Per this
milestone's own governing brief section 13 ("period not complete enough to
interpret" is a required abstention case), an incomplete current period
abstains with `"partial_period"` even when both sides already clear the
usable-day floor -- deliberately checked *after* the coverage-floor gates
below, so a period that is both incomplete *and* under-monitored reports the
more fundamental `insufficient_current_coverage` instead.

## No wall-clock reads

Like every pure module in this package, this module never calls
`datetime.now()`/`date.today()` -- `PeriodInput.is_complete` and every date
boundary are caller-supplied facts, so a comparison for a past month always
reproduces the same result regardless of when it is recomputed (see
product-doctrine.md's "Derived insights... must remain reproducible from
persisted facts", and `_historical_place_baseline_and_species_statuses`'s
identical discipline).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta, tzinfo
from typing import AbstractSet, Iterable, Literal, Mapping, Sequence

from mockingbird.analytics.conditional_association import (
    DEFAULT_MIN_RATE_DIFFERENCE,
    DEFAULT_MIN_USABLE_DAYS_IN_CONDITION,
    ConditionalAssociation,
    compute_conditional_association,
)
from mockingbird.analytics.place_activity_report import TaxonFact, VisitFact, _Classification, _classify

# Bumped whenever any threshold/window constant below changes, mirroring
# `place_change_summary.PLACE_CHANGE_POLICY_VERSION`'s identical precedent,
# so a caller/export can record which policy produced a given result.
YEAR_OVER_YEAR_POLICY_VERSION = 1

# Materiality/coverage floors are the *same* numbers `conditional_
# association` already established (imported, not reinvented -- see the
# module docstring's "No new statistical primitive"), re-exported here under
# this module's own name only for readability at call sites.
MIN_USABLE_DAYS_PER_PERIOD = DEFAULT_MIN_USABLE_DAYS_IN_CONDITION
MIN_RATE_DIFFERENCE = DEFAULT_MIN_RATE_DIFFERENCE

# Section 11 of the governing brief: "sparse monitoring before first
# detection must weaken or suppress the insight." A period's own first-
# observed date for a taxon is trusted as a timing signal only when at
# least this many *usable* days already elapsed earlier in that same period
# -- otherwise "first observed on day 2" may only mean "monitoring itself
# started on day 1," not that the taxon was genuinely absent before. Reuses
# the identical "5" numeral as MIN_USABLE_DAYS_PER_PERIOD for the same
# "enough of a sample before trusting a claim" judgment, applied to a
# different question (lead-in coverage, not overall period coverage).
MIN_USABLE_DAYS_BEFORE_FIRST_OBSERVATION_FOR_TIMING_CLAIM = 5

# A first-observed-date shift smaller than this many days is within
# ordinary week-to-week observation-timing noise (the same "a week is
# already a meaningful, explainable unit" judgment `place_change_summary.
# RECENT_WINDOW_USABLE_DAYS`/historical_baseline's "established" floor both
# make) and is not narrated as "earlier"/"later." A small, explicit,
# documented product contract per section 12 of the governing brief, since
# no existing threshold in this codebase answers this specific question.
MIN_MATERIAL_TIMING_DIFFERENCE_DAYS = 7

# Bounded maximum species-level insights returned by `select_notable_
# species_changes`, matching this milestone's own governing brief's
# suggested "2-5 strongest eligible species changes" (section 23) and this
# codebase's existing bounded-list precedents (DIVERSITY_MILESTONE_ORDINALS,
# `daily_digest`'s top-5 highlights).
MAX_SPECIES_CHANGES_RETURNED = 5

PlaceYoYStatus = Literal[
    "comparable",
    "no_material_difference",
    "insufficient_prior_history",
    "insufficient_current_coverage",
    "insufficient_prior_coverage",
    "partial_period",
]

ActivityDirection = Literal["higher", "lower", "similar"]

FirstObservedTimingStatus = Literal["comparable", "insufficient_data"]


def _shift_year(day: date, years: int) -> date:
    """Shift `day` by whole calendar years, deterministically. Feb 29 in a
    leap year maps to Feb 28 in a non-leap target year -- there is no Feb 29
    in a non-leap year, and silently rolling forward to Mar 1 would
    misrepresent a leap-day boundary as one calendar day later than
    intended. This is the one, documented, always-applied rule (never a
    per-call choice) -- see the module docstring's "Comparable-period
    contract"."""

    try:
        return day.replace(year=day.year + years)
    except ValueError:
        assert day.month == 2 and day.day == 29, f"unexpected replace() failure for {day!r}"
        return date(day.year + years, 2, 28)


def comparable_prior_period(current_start_date: date, current_end_date: date) -> tuple[date, date]:
    """The prior-year comparable period for the half-open current period
    `[current_start_date, current_end_date)` -- both boundaries shifted
    back by exactly one calendar year, independently (see `_shift_year`).
    See the module docstring's "Comparable-period contract" for the
    disclosed one-day leap-year span exception."""

    if current_end_date <= current_start_date:
        raise ValueError("current_end_date must be after current_start_date")
    return _shift_year(current_start_date, -1), _shift_year(current_end_date, -1)


def calendar_month_period(year: int, month: int) -> tuple[date, date]:
    """The half-open `[start, end)` calendar-day range for one Place-local
    calendar month -- the primary comparable-period shape this milestone
    supports (see the module docstring; `seasonal_pattern.py` already
    established whole calendar months as this codebase's one real
    seasonality precedent)."""

    if not 1 <= month <= 12:
        raise ValueError("month must be 1..12")
    start = date(year, month, 1)
    end = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
    return start, end


def _date_range(start_date: date, end_date: date) -> frozenset[date]:
    span_days = (end_date - start_date).days
    return frozenset(start_date + timedelta(days=offset) for offset in range(span_days))


@dataclass(frozen=True)
class PeriodPresenceFacts:
    """One period's already-classified presence facts, gathered from a
    single bounded Visit query the caller (repository) issues once per
    period -- see `compute_period_presence_facts`."""

    presence_dates_by_taxon: Mapping[str, frozenset[date]]
    overall_presence_dates: frozenset[date]
    confirmed_wildlife_visit_count: int
    taxa: Mapping[str, TaxonFact]


def compute_period_presence_facts(
    window_visits: Iterable[VisitFact], *, local_timezone: tzinfo
) -> PeriodPresenceFacts:
    """One pass over already-resolved Visit facts for one period, applying
    the exact same `_classify` truth-precedence every sibling module in
    this package already uses: `presence_dates_by_taxon` is confirmed-
    species presence only (`CONFIRMED_WILDLIFE`); `overall_presence_dates`
    additionally includes a confirmed-but-species-unresolved
    ("unknown_bird"/"unknown_animal") abstention -- a human explicitly
    confirmed real wildlife presence, just not a named species. Mirrors
    `place_change_summary._presence_dates_by_taxon_and_overall`'s identical
    truth contract and shape; this module writes its own small copy rather
    than importing that module's private helper, matching this package's
    established per-module convention for this exact classification loop
    (see e.g. `source_activity.compute_source_activity`'s own independent
    version of the same pattern).

    `window_visits` should already have had any cross-camera-associated
    duplicate Visit excluded by the caller (via `_associated_visit_ids_to_
    exclude_from_counting`) before this function ever sees it -- this
    function performs no dedup of its own, mirroring `source_activity.
    compute_source_activity`'s identical caller contract, so
    `confirmed_wildlife_visit_count` never double-counts one physical
    encounter seen by two cameras.
    """

    by_taxon: dict[str, set[date]] = {}
    overall: set[date] = set()
    taxa: dict[str, TaxonFact] = {}
    confirmed_wildlife_visit_count = 0
    for visit in window_visits:
        classification = _classify(visit)
        if classification not in (
            _Classification.CONFIRMED_WILDLIFE,
            _Classification.CONFIRMED_SPECIES_UNRESOLVED,
        ):
            continue
        confirmed_wildlife_visit_count += 1
        local_date = visit.activity_started_at.astimezone(local_timezone).date()
        overall.add(local_date)
        if classification is _Classification.CONFIRMED_WILDLIFE:
            taxon = visit.confirmed_taxon
            assert taxon is not None
            by_taxon.setdefault(taxon.label, set()).add(local_date)
            taxa.setdefault(taxon.label, taxon)

    return PeriodPresenceFacts(
        presence_dates_by_taxon={label: frozenset(dates) for label, dates in by_taxon.items()},
        overall_presence_dates=frozenset(overall),
        confirmed_wildlife_visit_count=confirmed_wildlife_visit_count,
        taxa=taxa,
    )


@dataclass(frozen=True)
class PeriodInput:
    """One period's already-resolved facts, as gathered by the caller (see
    the module docstring's "Reuse, not a second analytics/query path") --
    this module performs no query, no usable-day computation, and no
    cross-camera dedup of its own.

    `has_any_monitoring_history` is `_monitoring_exposure_intervals_and_
    history`'s own `history_available_from is not None` -- a separate
    signal from an empty `usable_dates`, mirroring `HistoricalPlaceBaseline`'s
    identical "no durable exposure history at all" convention: it is what
    distinguishes "this Place did not exist / was never monitored a year
    ago" (`insufficient_prior_history`) from "it was monitored, just not
    enough" (`insufficient_prior_coverage`).
    """

    start_date: date
    end_date: date  # exclusive
    is_complete: bool
    usable_dates: AbstractSet[date]
    monitored_seconds: float | None
    confirmed_wildlife_visit_count: int
    has_any_monitoring_history: bool


@dataclass(frozen=True)
class ComparablePeriod:
    """One period's summary facts, for display/drill-down -- never a raw
    date set (see `PeriodInput`, the internal computation input this is
    derived from)."""

    start_date: date
    end_date: date  # exclusive
    is_complete: bool
    usable_day_count: int
    monitored_seconds: float | None
    confirmed_wildlife_visit_count: int


def _comparable_period(period: PeriodInput) -> ComparablePeriod:
    return ComparablePeriod(
        start_date=period.start_date,
        end_date=period.end_date,
        is_complete=period.is_complete,
        usable_day_count=len(period.usable_dates),
        monitored_seconds=period.monitored_seconds,
        confirmed_wildlife_visit_count=period.confirmed_wildlife_visit_count,
    )


def _run_association(
    *,
    current: PeriodInput,
    prior: PeriodInput,
    current_presence_dates: AbstractSet[date],
    prior_presence_dates: AbstractSet[date],
    min_usable_days_per_period: int,
    min_rate_difference: float,
) -> ConditionalAssociation:
    current_full_dates = _date_range(current.start_date, current.end_date)
    return compute_conditional_association(
        set(current_presence_dates) | set(prior_presence_dates),
        usable_dates=set(current.usable_dates) | set(prior.usable_dates),
        condition_dates=current_full_dates,
        min_usable_days_in_condition=min_usable_days_per_period,
        min_usable_days_out_of_condition=min_usable_days_per_period,
        min_rate_difference=min_rate_difference,
    )


def _status_from_association(
    association: ConditionalAssociation,
    *,
    current: PeriodInput,
    prior: PeriodInput,
    min_usable_days_per_period: int,
) -> PlaceYoYStatus:
    """Priority order, most-fundamental-blocker first -- see the module
    docstring's "Partial-period honesty" for why `partial_period` is
    checked only after both coverage floors pass."""

    if association.usable_days_out_of_condition == 0 and not prior.has_any_monitoring_history:
        return "insufficient_prior_history"
    if association.usable_days_in_condition < min_usable_days_per_period:
        return "insufficient_current_coverage"
    if association.usable_days_out_of_condition < min_usable_days_per_period:
        return "insufficient_prior_coverage"
    if not current.is_complete:
        return "partial_period"
    if association.status == "no_clear_association":
        return "no_material_difference"
    return "comparable"


def _direction_for(status: PlaceYoYStatus, association: ConditionalAssociation) -> ActivityDirection | None:
    if status == "comparable":
        return "higher" if association.status == "more_common_under_condition" else "lower"
    if status == "no_material_difference":
        return "similar"
    return None


@dataclass(frozen=True)
class PlaceYearOverYearComparison:
    """One Place-wide year-over-year comparison, as of `current_period`'s
    own end. `overall_activity` is populated exactly when `status` is
    `"comparable"` (a real difference) or `"no_material_difference"`
    (`"similar"`) -- `None` for every abstention status, never a fabricated
    direction (see product-doctrine.md's "Measured, Inferred, and Reviewed":
    an inference must never manufacture certainty from sparse data).
    `association` carries the underlying rate/count facts for drill-down --
    never just a final verdict, mirroring every sibling comparison module's
    identical "explain the verdict" discipline."""

    policy_version: int
    current_period: ComparablePeriod
    prior_period: ComparablePeriod
    status: PlaceYoYStatus
    overall_activity: ActivityDirection | None
    association: ConditionalAssociation | None
    information_class: Literal["inferred"] = "inferred"


def compute_place_year_over_year_comparison(
    *,
    current: PeriodInput,
    prior: PeriodInput,
    current_presence_dates: AbstractSet[date],
    prior_presence_dates: AbstractSet[date],
    min_usable_days_per_period: int = MIN_USABLE_DAYS_PER_PERIOD,
    min_rate_difference: float = MIN_RATE_DIFFERENCE,
) -> PlaceYearOverYearComparison:
    """Compare Place-wide confirmed-wildlife presence-day rate in `current`
    against `prior`. `current_presence_dates`/`prior_presence_dates` should
    be each period's own set of local dates with at least one confirmed
    wildlife Visit (named-species or an "unknown_bird"/"unknown_animal"
    abstention alike -- mirrors `place_change_summary`'s identical `overall`
    truth contract: a human confirmed real wildlife presence, just not
    necessarily a named species)."""

    association = _run_association(
        current=current,
        prior=prior,
        current_presence_dates=current_presence_dates,
        prior_presence_dates=prior_presence_dates,
        min_usable_days_per_period=min_usable_days_per_period,
        min_rate_difference=min_rate_difference,
    )
    status = _status_from_association(
        association, current=current, prior=prior, min_usable_days_per_period=min_usable_days_per_period
    )
    return PlaceYearOverYearComparison(
        policy_version=YEAR_OVER_YEAR_POLICY_VERSION,
        current_period=_comparable_period(current),
        prior_period=_comparable_period(prior),
        status=status,
        overall_activity=_direction_for(status, association),
        association=association,
    )


@dataclass(frozen=True)
class TaxonYearOverYearComparison:
    """One taxon's year-over-year activity comparison, plus an optional
    first-observed-timing comparison (Deliverable B of the governing
    brief) -- kept as two independently-gated sub-verdicts on one entry,
    since a taxon can have a trustworthy activity comparison with no
    trustworthy timing claim (or vice versa): they answer different
    questions from different evidence (a whole-period rate vs. one single
    date each side)."""

    taxon: TaxonFact
    status: PlaceYoYStatus
    activity_direction: ActivityDirection | None
    association: ConditionalAssociation | None

    current_first_observed_date: date | None
    prior_first_observed_date: date | None
    first_observed_timing_status: FirstObservedTimingStatus
    # Current minus prior, both measured as "days into the period" (offset
    # from that period's own start_date) -- never a raw calendar-date
    # subtraction, which would be biased by the leap-year one-day span
    # exception `comparable_prior_period` discloses. Negative means earlier
    # this year. Populated only when `first_observed_timing_status ==
    # "comparable"`.
    first_observed_day_difference: int | None
    # Whether `first_observed_day_difference` clears
    # MIN_MATERIAL_TIMING_DIFFERENCE_DAYS -- a presentation layer should
    # narrate timing only when this is True (see `select_notable_species_
    # changes`), matching every other "do not narrate a tiny difference"
    # rule in this codebase.
    first_observed_is_material: bool


def _first_observed_timing(
    *,
    current: PeriodInput,
    prior: PeriodInput,
    current_first: date | None,
    prior_first: date | None,
    min_usable_days_before_first_observation: int,
    min_material_timing_difference_days: int,
) -> tuple[FirstObservedTimingStatus, int | None, bool]:
    """Section 11 of the governing brief: "first observed" is trusted as a
    timing signal only when monitoring was already meaningfully running
    before it, on *both* sides -- otherwise "first observed on day 2" may
    only mean monitoring itself began on day 1. Requires a first-observed
    date on *both* sides: a taxon absent from one period entirely has no
    "N days earlier/later" to report (its historical_baseline "new"/
    "first_record"/"seen_before" status already covers that case honestly;
    this module does not re-claim it as a timing comparison)."""

    if current_first is None or prior_first is None:
        return "insufficient_data", None, False

    current_lead_in = sum(1 for day in current.usable_dates if day < current_first)
    prior_lead_in = sum(1 for day in prior.usable_dates if day < prior_first)
    if (
        current_lead_in < min_usable_days_before_first_observation
        or prior_lead_in < min_usable_days_before_first_observation
    ):
        return "insufficient_data", None, False

    current_offset = (current_first - current.start_date).days
    prior_offset = (prior_first - prior.start_date).days
    difference = current_offset - prior_offset
    is_material = abs(difference) >= min_material_timing_difference_days
    return "comparable", difference, is_material


def compute_species_year_over_year_comparisons(
    taxa: Mapping[str, TaxonFact],
    *,
    current: PeriodInput,
    prior: PeriodInput,
    current_presence_dates_by_taxon: Mapping[str, AbstractSet[date]],
    prior_presence_dates_by_taxon: Mapping[str, AbstractSet[date]],
    min_usable_days_per_period: int = MIN_USABLE_DAYS_PER_PERIOD,
    min_rate_difference: float = MIN_RATE_DIFFERENCE,
    min_usable_days_before_first_observation: int = MIN_USABLE_DAYS_BEFORE_FIRST_OBSERVATION_FOR_TIMING_CLAIM,
    min_material_timing_difference_days: int = MIN_MATERIAL_TIMING_DIFFERENCE_DAYS,
) -> list[TaxonYearOverYearComparison]:
    """One `TaxonYearOverYearComparison` per taxon confirmed in *either*
    period (the union of both maps' keys) -- a taxon confirmed only a year
    ago and entirely absent this period still gets an honest, potentially
    `"lower"`/`"comparable"` entry (never silently dropped), and a taxon
    confirmed only this period naturally reads as `"higher"` once its prior
    rate of zero clears the floor (or an honest `insufficient_prior_
    coverage`/`insufficient_prior_history` otherwise) -- exactly mirroring
    `place_change_summary.compute_place_change_summary`'s identical
    "a taxon dormant in both windows still gets an honest entry" discipline.

    `taxa` must contain every label appearing in either presence map (a
    `KeyError` on a missing label is a caller bug, not a data condition this
    function silently tolerates -- mirrors `TaxonPlacePattern`'s equivalent
    contract)."""

    labels = set(current_presence_dates_by_taxon) | set(prior_presence_dates_by_taxon)
    results: list[TaxonYearOverYearComparison] = []
    for label in labels:
        taxon = taxa[label]
        current_dates = current_presence_dates_by_taxon.get(label, frozenset())
        prior_dates = prior_presence_dates_by_taxon.get(label, frozenset())

        association = _run_association(
            current=current,
            prior=prior,
            current_presence_dates=current_dates,
            prior_presence_dates=prior_dates,
            min_usable_days_per_period=min_usable_days_per_period,
            min_rate_difference=min_rate_difference,
        )
        status = _status_from_association(
            association, current=current, prior=prior, min_usable_days_per_period=min_usable_days_per_period
        )

        current_first = min(current_dates) if current_dates else None
        prior_first = min(prior_dates) if prior_dates else None
        timing_status, day_difference, is_material = _first_observed_timing(
            current=current,
            prior=prior,
            current_first=current_first,
            prior_first=prior_first,
            min_usable_days_before_first_observation=min_usable_days_before_first_observation,
            min_material_timing_difference_days=min_material_timing_difference_days,
        )

        results.append(
            TaxonYearOverYearComparison(
                taxon=taxon,
                status=status,
                activity_direction=_direction_for(status, association),
                association=association,
                current_first_observed_date=current_first,
                prior_first_observed_date=prior_first,
                first_observed_timing_status=timing_status,
                first_observed_day_difference=day_difference,
                first_observed_is_material=is_material,
            )
        )

    return sorted(results, key=lambda entry: (entry.taxon.display_name.lower(), entry.taxon.label))


def _evidence_strength(comparison: TaxonYearOverYearComparison) -> int:
    """Ranking signal for `select_notable_species_changes`: the *smaller*
    of the two sides' presence-day counts, never the larger -- a taxon with
    9 presence days this period and 1 a year ago is weaker evidence than one
    with 6 and 5, even though the first has a larger raw count and a more
    dramatic-looking ratio (section 18 of the governing brief: "Do not rank
    solely by raw percent change, which explodes on tiny denominators")."""

    if comparison.association is None:
        return 0
    return min(
        comparison.association.presence_days_in_condition,
        comparison.association.presence_days_out_of_condition,
    )


def select_notable_species_changes(
    comparisons: Sequence[TaxonYearOverYearComparison],
    *,
    max_count: int = MAX_SPECIES_CHANGES_RETURNED,
) -> list[TaxonYearOverYearComparison]:
    """The bounded, calmly-ranked subset of `comparisons` worth narrating --
    never every species, never ranked by raw percent change (section 18).
    Eligible: a real activity difference (`status == "comparable"`) or a
    material first-observed timing shift (`first_observed_is_material`) --
    `"no_material_difference"`/abstention-only entries carry nothing to
    narrate and are excluded here (a caller wanting the full, unranked list
    for drill-down should read `compute_species_year_over_year_comparisons`'s
    own return value directly, not this function).

    Ranked by evidence strength (`_evidence_strength`, descending) first,
    then alphabetically for a deterministic, explainable order -- never by
    the raw rate difference itself, which a tiny denominator can make
    arbitrarily large."""

    eligible = [
        comparison
        for comparison in comparisons
        if comparison.status == "comparable" or comparison.first_observed_is_material
    ]
    ranked = sorted(
        eligible,
        key=lambda comparison: (
            -_evidence_strength(comparison),
            comparison.taxon.display_name.lower(),
            comparison.taxon.label,
        ),
    )
    return ranked[:max_count]


__all__ = [
    "MAX_SPECIES_CHANGES_RETURNED",
    "MIN_MATERIAL_TIMING_DIFFERENCE_DAYS",
    "MIN_RATE_DIFFERENCE",
    "MIN_USABLE_DAYS_BEFORE_FIRST_OBSERVATION_FOR_TIMING_CLAIM",
    "MIN_USABLE_DAYS_PER_PERIOD",
    "YEAR_OVER_YEAR_POLICY_VERSION",
    "ActivityDirection",
    "ComparablePeriod",
    "FirstObservedTimingStatus",
    "PeriodInput",
    "PeriodPresenceFacts",
    "PlaceYearOverYearComparison",
    "PlaceYoYStatus",
    "TaxonYearOverYearComparison",
    "calendar_month_period",
    "comparable_prior_period",
    "compute_period_presence_facts",
    "compute_place_year_over_year_comparison",
    "compute_species_year_over_year_comparisons",
    "select_notable_species_changes",
]
