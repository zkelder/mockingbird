"""Gate C -- Meaningful Change Detection / Baseline Comparison v1: pure,
deterministic comparison of recent reviewed wildlife activity against an
established, coverage-aware historical baseline (see
docs/meaningful-change-detection-contract.md).

This is the second bounded slice of product-doctrine.md's "Place
Intelligence" layer, built directly on top of the first
(`mockingbird.analytics.historical_baseline`). It answers one further
question neither `place_activity_report` nor `historical_baseline` answers:
*has* a taxon's (or the Place's overall) presence recently been higher,
lower, or about the same as its own recent history -- never "the population
increased," "the species is declining," or any other ecological/statistical
claim (see "Explicit non-goals" below).

## Reuse, not a second analytics path

This module never queries a database and never re-derives review truth or
usable-day accounting: it consumes the exact same `VisitFact`/`TaxonFact`/
`_classify` truth-precedence resolution `place_activity_report` and
`historical_baseline` already own (imported directly), and the exact same
`usable_dates` set `historical_baseline.compute_historical_place_baseline`
already computes (via `ProductRepository._historical_usable_dates`) --
never a second definition of "usable day." A repository-side adapter
(`ProductRepository._historical_place_baseline_and_species_statuses`, see
the contract doc's "Integration" section) is the only place that touches
the database, and it computes this module's inputs alongside historical
baseline's own, from the same underlying query results.

## Why presence-days, not Visit counts

A busy feeder afternoon (thirty Visits in one day) must never look like
"more common now" than three quiet days spread across two weeks (see
"Busy-day protection" in the contract doc). Every count in this module is a
*distinct usable day a taxon was confirmed on*, exactly the same discipline
`historical_baseline.compute_species_historical_statuses` already applies
to its own `distinct_confirmed_usable_days` -- this module only adds the
recent-vs-reference window split on top of that existing metric.

## Window design: usable days, not raw calendar days

`RECENT_WINDOW_USABLE_DAYS` (7, reusing `historical_baseline.
MIN_USABLE_DAYS_FOR_ESTABLISHED_BASELINE` directly -- "a full week's worth
of genuinely well-monitored days" is already an accepted, explainable
product unit) and `REFERENCE_WINDOW_USABLE_DAYS` (14, exactly double) define
the two windows by *usable-day count*, not raw calendar span: "the last 7
usable days" may span more than 7 calendar days if some of the intervening
days were not well-monitored, and "the preceding 14 usable days" continues
counting backward from there, however far back that reaches (bounded by
`historical_baseline.HISTORICAL_BASELINE_WINDOW_DAYS`, the same 366-day cap
every other historical computation in this codebase already uses). This
directly avoids comparing "8 monitored hours" against "15 monitored
minutes" as if they were equivalent days.

`RECENT_WINDOW_FRESHNESS_CAP_DAYS` (14, reusing the exact "recent" calendar
window `ProductRepository._dashboard_today_summary`'s `recent_regulars`/
`new_today` and `wildlife_journal_overview`'s own `recent_activity`
sparkline already established elsewhere in this codebase) is a *separate*
concept from the two counts above: even once 7 usable days are found
somewhere in history, if the single most recent one is older than this many
calendar days before `window_end_at`, real monitoring has recently lapsed
(a camera outage, a long gap) and the "recent" picture would be stale, not
actually recent -- see `insufficient_recent_coverage` below.

## Baseline prerequisite, restated in window terms

`historical_baseline`'s own "established" threshold (>= 7 usable days) is a
*necessary but not sufficient* condition for this module's comparison: a
Place needs a full 7 + 14 = 21 usable days to populate both windows, more
than the 7-day "established" floor alone guarantees. Consequently, whenever
`compute_place_change_windows` reports `is_valid=True`, `historical_
baseline.maturity` is *always* "established" too (asserted explicitly
below, mirroring `compute_species_historical_statuses`'s own defensive
"regular is structurally impossible while insufficient" assertion) -- but
the reverse does not hold, and this module's own, stricter gate is what
actually governs whether a comparison may be shown, never the coarser
Place-wide maturity alone.

## Threshold policy (versioned)

A status of `higher_recent_presence`/`lower_recent_presence` requires *all*
of:

- at least `MIN_REFERENCE_PRESENCE_DAYS_FOR_COMPARISON` (1) reference-window
  presence days -- a taxon never seen in the reference window has no
  historical rate to compare against (see "new"/"first_record" in
  `historical_baseline` for that already-covered case; this module reports
  `no_supported_change` rather than fabricating a directional claim);
- a rate difference (`recent_presence_days / RECENT_WINDOW_USABLE_DAYS`
  minus `reference_presence_days / REFERENCE_WINDOW_USABLE_DAYS`) of at
  least `MIN_PROPORTIONAL_DIFFERENCE` (0.25, i.e. 25 percentage points);
  and
- an absolute difference (the recent count minus the reference count
  rescaled to the recent window's own length, so both are compared "per 7
  days") of at least `MIN_ABSOLUTE_PRESENCE_DAY_DIFFERENCE` (2 days) --
  this guards against a rate swing driven by tiny numbers (a single extra
  day out of a 14-day reference window is already a large percentage).

`PLACE_CHANGE_POLICY_VERSION` is bumped whenever any of these numbers
changes, so a caller/export can record which policy produced a given
result (see "Explainability" in the contract doc).

## Explicit non-goals

This module never claims population increase/decrease, ecological decline,
migration timing, regional rarity, or statistical significance -- it
measures only a bounded, coverage-aware change in what was *recorded* at
this Place, under comparable monitoring, exactly the doctrine boundary
product-doctrine.md's "Place Intelligence" section and Phase 5 describe.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time, tzinfo
from typing import AbstractSet, Iterable, Literal, Mapping

from mockingbird.analytics.historical_baseline import MIN_USABLE_DAYS_FOR_ESTABLISHED_BASELINE
from mockingbird.analytics.place_activity_report import TaxonFact, VisitFact, _Classification, _classify

# See the module docstring's "Window design" section for the reuse
# rationale behind every constant below.
RECENT_WINDOW_USABLE_DAYS = MIN_USABLE_DAYS_FOR_ESTABLISHED_BASELINE  # 7
REFERENCE_WINDOW_USABLE_DAYS = 2 * RECENT_WINDOW_USABLE_DAYS  # 14

# How many calendar days before `window_end_at` the single most-recent
# usable day may fall before the "recent" picture is considered stale --
# reuses the exact "recent" calendar span already established elsewhere in
# this codebase (`_dashboard_today_summary`'s 14-day `recent_regulars`/
# `new_today`, `wildlife_journal_overview`'s 14-entry `recent_activity`),
# not a new invented number. Deliberately the same numeral as
# REFERENCE_WINDOW_USABLE_DAYS above by coincidence of precedent, not
# because the two concepts are the same thing -- kept as two separately
# named constants so a future change to one never silently drags the other.
RECENT_WINDOW_FRESHNESS_CAP_DAYS = 14

# Threshold policy -- see the module docstring's "Threshold policy" section.
MIN_REFERENCE_PRESENCE_DAYS_FOR_COMPARISON = 1
MIN_ABSOLUTE_PRESENCE_DAY_DIFFERENCE = 2
MIN_PROPORTIONAL_DIFFERENCE = 0.25

# Bumped whenever any threshold/window constant above changes, so a
# consumer can record which policy produced a given comparison result.
PLACE_CHANGE_POLICY_VERSION = 1

TaxonChangeStatusValue = Literal[
    "insufficient_baseline",
    "insufficient_recent_coverage",
    "no_supported_change",
    "higher_recent_presence",
    "lower_recent_presence",
]

# The Place-level counterpart vocabulary is deliberately worded differently
# from the per-taxon one above (matching the milestone's own distinct
# wording), even though the underlying computation is the same shape -- see
# `_OVERALL_STATUS_BY_PRESENCE_STATUS`.
PlaceChangeStatusValue = Literal[
    "building_baseline",
    "insufficient_recent_coverage",
    "no_supported_change",
    "more_activity_recorded",
    "less_activity_recorded",
]

_InvalidReason = Literal["insufficient_baseline", "insufficient_recent_coverage"]


def _local_midnight(day: date, local_timezone: tzinfo) -> datetime:
    return datetime.combine(day, time.min, tzinfo=local_timezone)


@dataclass(frozen=True)
class PlaceChangeWindows:
    """The bounded recent/reference comparison windows for one Place, as of
    `window_end_at`. `is_valid=False` means no per-taxon/overall comparison
    may be shown at all -- every status downstream is forced to
    `invalid_reason` regardless of any presence-day count.

    `recent_usable_dates`/`reference_usable_dates` hold whatever partial set
    was found even when `is_valid` is `False` (never fabricated, never
    padded) -- useful for provenance/debugging, but callers must gate on
    `is_valid`, never infer validity from set size themselves.
    """

    policy_version: int
    window_end_at: datetime
    recent_usable_dates: frozenset[date]
    recent_window_start_at: datetime | None
    recent_window_end_at: datetime
    reference_usable_dates: frozenset[date]
    reference_window_start_at: datetime | None
    reference_window_end_at: datetime | None
    is_valid: bool
    invalid_reason: _InvalidReason | None


def compute_place_change_windows(
    usable_dates: AbstractSet[date],
    *,
    window_end_at: datetime,
    local_timezone: tzinfo,
) -> PlaceChangeWindows:
    """Split accumulated usable days into a recent window (the last
    `RECENT_WINDOW_USABLE_DAYS` usable days) and a reference window (the
    `REFERENCE_WINDOW_USABLE_DAYS` usable days immediately preceding it),
    walking backward from `window_end_at`'s own local date.

    `usable_dates` should come from the same `usable_dates_from_daily_
    monitored_seconds` set `historical_baseline.compute_historical_place_
    baseline` already computes for this Place -- see the module docstring.
    Non-usable calendar days are never in this set at all, so they are
    structurally skipped over (never counted as an absence) when the walk
    reaches back past them -- see "Coverage-aware zero semantics" in the
    contract doc.
    """

    window_end_local_date = window_end_at.astimezone(local_timezone).date()
    sorted_desc = sorted(usable_dates, reverse=True)

    recent_dates = sorted_desc[:RECENT_WINDOW_USABLE_DAYS]
    if len(recent_dates) < RECENT_WINDOW_USABLE_DAYS:
        # Fewer than 7 usable days exist anywhere in the bounded lookback --
        # historical_baseline.maturity cannot be "established" either (see
        # the module docstring's "Baseline prerequisite" section), so there
        # is not yet enough accumulated history to even attempt a
        # comparison.
        return PlaceChangeWindows(
            policy_version=PLACE_CHANGE_POLICY_VERSION,
            window_end_at=window_end_at,
            recent_usable_dates=frozenset(recent_dates),
            recent_window_start_at=_local_midnight(recent_dates[-1], local_timezone) if recent_dates else None,
            recent_window_end_at=window_end_at,
            reference_usable_dates=frozenset(),
            reference_window_start_at=None,
            reference_window_end_at=None,
            is_valid=False,
            invalid_reason="insufficient_baseline",
        )

    recent_window_start_at = _local_midnight(recent_dates[-1], local_timezone)
    most_recent_usable_date = recent_dates[0]
    staleness_days = (window_end_local_date - most_recent_usable_date).days

    if staleness_days > RECENT_WINDOW_FRESHNESS_CAP_DAYS:
        # Enough usable days exist somewhere in history, but the freshest
        # one is stale -- monitoring has recently lapsed (an outage, a long
        # gap), so whatever "recent" data exists is not actually recent.
        # Deeper reference-window history may or may not exist; it is
        # irrelevant once the recent picture itself cannot be trusted.
        return PlaceChangeWindows(
            policy_version=PLACE_CHANGE_POLICY_VERSION,
            window_end_at=window_end_at,
            recent_usable_dates=frozenset(recent_dates),
            recent_window_start_at=recent_window_start_at,
            recent_window_end_at=window_end_at,
            reference_usable_dates=frozenset(),
            reference_window_start_at=None,
            reference_window_end_at=None,
            is_valid=False,
            invalid_reason="insufficient_recent_coverage",
        )

    remaining = sorted_desc[RECENT_WINDOW_USABLE_DAYS:]
    reference_dates = remaining[:REFERENCE_WINDOW_USABLE_DAYS]
    if len(reference_dates) < REFERENCE_WINDOW_USABLE_DAYS:
        # The recent window is fine, but not enough additional historical
        # depth exists beyond it to populate a fair reference window.
        return PlaceChangeWindows(
            policy_version=PLACE_CHANGE_POLICY_VERSION,
            window_end_at=window_end_at,
            recent_usable_dates=frozenset(recent_dates),
            recent_window_start_at=recent_window_start_at,
            recent_window_end_at=window_end_at,
            reference_usable_dates=frozenset(reference_dates),
            reference_window_start_at=(
                _local_midnight(reference_dates[-1], local_timezone) if reference_dates else None
            ),
            reference_window_end_at=recent_window_start_at,
            is_valid=False,
            invalid_reason="insufficient_baseline",
        )

    windows = PlaceChangeWindows(
        policy_version=PLACE_CHANGE_POLICY_VERSION,
        window_end_at=window_end_at,
        recent_usable_dates=frozenset(recent_dates),
        recent_window_start_at=recent_window_start_at,
        recent_window_end_at=window_end_at,
        reference_usable_dates=frozenset(reference_dates),
        reference_window_start_at=_local_midnight(reference_dates[-1], local_timezone),
        reference_window_end_at=recent_window_start_at,
        is_valid=True,
        invalid_reason=None,
    )
    assert len(windows.recent_usable_dates) == RECENT_WINDOW_USABLE_DAYS
    assert len(windows.reference_usable_dates) == REFERENCE_WINDOW_USABLE_DAYS
    return windows


def _presence_status(
    recent_presence_days: int, reference_presence_days: int
) -> Literal["no_supported_change", "higher_recent_presence", "lower_recent_presence"]:
    """The threshold-policy decision shared by both per-taxon and Place-
    overall comparison -- see the module docstring's "Threshold policy"
    section. Never called unless `PlaceChangeWindows.is_valid` -- an invalid
    window forces `insufficient_baseline`/`insufficient_recent_coverage`
    directly, bypassing this function entirely."""

    if reference_presence_days < MIN_REFERENCE_PRESENCE_DAYS_FOR_COMPARISON:
        # No (or negligible) reference-window presence to compare against --
        # see "new"/"first_record" in historical_baseline for the adjacent,
        # already-covered "first ever" case this deliberately does not
        # re-claim as a directional change.
        return "no_supported_change"

    recent_rate = recent_presence_days / RECENT_WINDOW_USABLE_DAYS
    reference_rate = reference_presence_days / REFERENCE_WINDOW_USABLE_DAYS
    # Rescale the reference rate onto the recent window's own length so the
    # absolute-difference guard compares "presence days per 7 days" on both
    # sides, rather than raw counts from windows of different lengths.
    reference_count_scaled_to_recent = reference_rate * RECENT_WINDOW_USABLE_DAYS
    absolute_difference = recent_presence_days - reference_count_scaled_to_recent
    rate_difference = recent_rate - reference_rate

    if (
        abs(absolute_difference) < MIN_ABSOLUTE_PRESENCE_DAY_DIFFERENCE
        or abs(rate_difference) < MIN_PROPORTIONAL_DIFFERENCE
    ):
        return "no_supported_change"
    return "higher_recent_presence" if rate_difference > 0 else "lower_recent_presence"


_OVERALL_STATUS_BY_PRESENCE_STATUS: dict[str, PlaceChangeStatusValue] = {
    "no_supported_change": "no_supported_change",
    "higher_recent_presence": "more_activity_recorded",
    "lower_recent_presence": "less_activity_recorded",
}
_OVERALL_STATUS_BY_INVALID_REASON: dict[_InvalidReason, PlaceChangeStatusValue] = {
    "insufficient_baseline": "building_baseline",
    "insufficient_recent_coverage": "insufficient_recent_coverage",
}


@dataclass(frozen=True)
class TaxonChangeStatus:
    """One taxon's recent-vs-reference presence comparison. Present only for
    an authoritatively-confirmed taxon (mirrors `historical_baseline.
    SpeciesHistoricalStatus`'s identical truth-contract gate) -- a
    provisional SpeciesSuggestion can never establish or extend either
    window's presence-day count."""

    taxon: TaxonFact
    recent_presence_days: int
    recent_usable_day_count: int
    reference_presence_days: int
    reference_usable_day_count: int
    status: TaxonChangeStatusValue


@dataclass(frozen=True)
class PlaceOverallChangeStatus:
    """The Place-wide aggregate comparison: any confirmed wildlife activity
    (named-species and "unknown_bird"/"unknown_animal" abstentions alike --
    see product-doctrine.md's truth boundary and the contract doc's
    "Coverage-aware zero semantics"), never per-species. This is a single,
    honest aggregate rather than a forced blend of potentially conflicting
    per-species signals -- see "Place-level change summary" in the contract
    doc for why this construction avoids that trap."""

    recent_presence_days: int
    recent_usable_day_count: int
    reference_presence_days: int
    reference_usable_day_count: int
    status: PlaceChangeStatusValue


@dataclass(frozen=True)
class PlaceChangeSummary:
    """One deterministic comparison of recent vs. reference reviewed
    wildlife activity for a Place, as of `windows.window_end_at`."""

    windows: PlaceChangeWindows
    taxa: list[TaxonChangeStatus] = field(default_factory=list)
    overall: PlaceOverallChangeStatus | None = None


def _presence_dates_by_taxon_and_overall(
    window_visits: Iterable[VisitFact], *, local_timezone: tzinfo
) -> tuple[dict[str, set[date]], set[date]]:
    """One pass over already-resolved Visit facts, matching `historical_
    baseline.compute_species_historical_statuses`'s own single-pass
    accumulation shape. `overall` additionally includes confirmed-but-
    species-unresolved wildlife ("unknown_bird"/"unknown_animal") -- a
    human explicitly confirmed real wildlife presence, just not a named
    species -- per the milestone's explicit invitation to let unresolved
    wildlife contribute to a generic wildlife-activity comparison where the
    semantics are explicit (this is that explicit place); `by_taxon` never
    does, matching the identical named-species truth contract `historical_
    baseline` already enforces."""

    by_taxon: dict[str, set[date]] = {}
    overall: set[date] = set()
    for visit in window_visits:
        classification = _classify(visit)
        if classification not in (
            _Classification.CONFIRMED_WILDLIFE,
            _Classification.CONFIRMED_SPECIES_UNRESOLVED,
        ):
            continue
        local_date = visit.activity_started_at.astimezone(local_timezone).date()
        overall.add(local_date)
        if classification is _Classification.CONFIRMED_WILDLIFE:
            taxon = visit.confirmed_taxon
            assert taxon is not None
            by_taxon.setdefault(taxon.label, set()).add(local_date)
    return by_taxon, overall


def compute_place_change_summary(
    window_visits: Iterable[VisitFact],
    *,
    taxa: Mapping[str, TaxonFact],
    usable_dates: AbstractSet[date],
    local_timezone: tzinfo,
    window_end_at: datetime,
) -> PlaceChangeSummary:
    """Compute one deterministic `PlaceChangeSummary`.

    `taxa` should be the exact same all-time-confirmed-taxon dict `historical_
    baseline.compute_species_historical_statuses` already receives (every
    taxon this Place has ever authoritatively confirmed) -- a taxon dormant
    in both windows still gets an honest `no_supported_change` entry (zero
    reference presence never becomes a fabricated directional claim; see
    "Threshold policy" above) rather than silently vanishing. `window_visits`
    should already be scoped to the same bounded historical window `usable_
    dates` covers.
    """

    windows = compute_place_change_windows(
        usable_dates, window_end_at=window_end_at, local_timezone=local_timezone
    )
    by_taxon_dates, overall_dates = _presence_dates_by_taxon_and_overall(
        window_visits, local_timezone=local_timezone
    )

    taxon_statuses: list[TaxonChangeStatus] = []
    for label, taxon in taxa.items():
        dates = by_taxon_dates.get(label, set())
        recent_presence_days = len(dates & windows.recent_usable_dates)
        reference_presence_days = len(dates & windows.reference_usable_dates)
        status: TaxonChangeStatusValue
        if not windows.is_valid:
            assert windows.invalid_reason is not None
            status = windows.invalid_reason
        else:
            status = _presence_status(recent_presence_days, reference_presence_days)
        taxon_statuses.append(
            TaxonChangeStatus(
                taxon=taxon,
                recent_presence_days=recent_presence_days,
                recent_usable_day_count=len(windows.recent_usable_dates),
                reference_presence_days=reference_presence_days,
                reference_usable_day_count=len(windows.reference_usable_dates),
                status=status,
            )
        )
    taxon_statuses.sort(key=lambda entry: (entry.taxon.display_name.lower(), entry.taxon.label))

    overall_recent_presence_days = len(overall_dates & windows.recent_usable_dates)
    overall_reference_presence_days = len(overall_dates & windows.reference_usable_dates)
    overall_status: PlaceChangeStatusValue
    if not windows.is_valid:
        assert windows.invalid_reason is not None
        overall_status = _OVERALL_STATUS_BY_INVALID_REASON[windows.invalid_reason]
    else:
        overall_status = _OVERALL_STATUS_BY_PRESENCE_STATUS[
            _presence_status(overall_recent_presence_days, overall_reference_presence_days)
        ]

    overall = PlaceOverallChangeStatus(
        recent_presence_days=overall_recent_presence_days,
        recent_usable_day_count=len(windows.recent_usable_dates),
        reference_presence_days=overall_reference_presence_days,
        reference_usable_day_count=len(windows.reference_usable_dates),
        status=overall_status,
    )

    return PlaceChangeSummary(windows=windows, taxa=taxon_statuses, overall=overall)


__all__ = [
    "MIN_ABSOLUTE_PRESENCE_DAY_DIFFERENCE",
    "MIN_PROPORTIONAL_DIFFERENCE",
    "MIN_REFERENCE_PRESENCE_DAYS_FOR_COMPARISON",
    "PLACE_CHANGE_POLICY_VERSION",
    "RECENT_WINDOW_FRESHNESS_CAP_DAYS",
    "RECENT_WINDOW_USABLE_DAYS",
    "REFERENCE_WINDOW_USABLE_DAYS",
    "PlaceChangeStatusValue",
    "PlaceChangeSummary",
    "PlaceChangeWindows",
    "PlaceOverallChangeStatus",
    "TaxonChangeStatus",
    "TaxonChangeStatusValue",
    "compute_place_change_summary",
    "compute_place_change_windows",
]
