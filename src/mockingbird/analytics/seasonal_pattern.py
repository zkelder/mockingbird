"""Place / Yard Intelligence v2: a restrained seasonality foundation --
month-of-year presence-rate bucketing over the same trailing 366-day window
`historical_baseline`/`place_change_summary` already use.

No prior seasonality concept exists anywhere in this codebase (confirmed by
exhaustive grep across every `mockingbird.analytics` module -- the only hit
is `historical_baseline`'s own docstring naming it as an explicit non-goal
of *that* module). This module reuses `window_visits`/`usable_dates`/`taxa`
-- the exact same facts the shared historical-intelligence bundle already
fetches -- so a caller pays zero additional database queries to add this.

Deliberately a **single trailing-year window**, not a multi-year
accumulation: the 366-day window resets forward every time it is computed,
so it can show "this taxon's presence this year skews toward month X," but
never true year-over-year seasonality (that needs a different,
non-resetting historical-accumulation strategy -- an explicitly recorded
future dependency, not built here). See
docs/place-yard-intelligence-v2-contract.md section 3.2.

Given this product's typical real installation has only a handful of usable
days of history so far, `SeasonalPatternStatus.insufficient_history` is
expected to be the honest, common result today -- exactly mirroring
`historical_baseline`'s own disclosed real-database verification. The
product must remain useful while that is true (see product-doctrine.md:
"Do not imply... a short history establishes a mature seasonal pattern.").
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, tzinfo
from typing import AbstractSet, Iterable, Literal, Mapping, Sequence

from mockingbird.analytics.place_activity_report import TaxonFact, VisitFact

# Of the 12 calendar months, how many must have at least
# `SEASONAL_MIN_USABLE_DAYS_IN_MONTH` usable days somewhere in the 366-day
# window before *any* taxon's seasonal pattern is attempted. This is a
# Place-wide gate, decided once and applied uniformly -- mirrors
# `place_change_summary.PlaceChangeWindows.is_valid`'s own "decided once,
# applied to every taxon" discipline. 9 of 12 (three-quarters of the year)
# is deliberately stricter than a bare "some months have data": a real
# calendar year always has some usable days in nearly every month once
# monitoring has run for a year, so this floor mostly excludes an
# installation that is only a few weeks/months old, which is exactly the
# honest state such an installation should report.
SEASONAL_MIN_DISTINCT_USABLE_MONTHS = 9

# A calendar month needs at least this many usable days counted toward it
# before it contributes to any rate comparison -- guards against a single
# usable day in an otherwise-unmonitored month producing a 0% or 100% rate
# for that month.
SEASONAL_MIN_USABLE_DAYS_IN_MONTH = 2

# A taxon needs at least this many total presence days across the whole
# window before a per-month pattern is attempted for *it* specifically,
# even when the Place-wide gate above has already passed.
SEASONAL_MIN_PRESENCE_DAYS_FOR_PATTERN = 3

# A month's own presence-rate must be at least this multiple of the taxon's
# own average rate (across every qualifying month) to be flagged as
# "typical" for that taxon -- a simple, explainable robust-deviation rule
# (Phase 18), not a statistical test.
SEASONAL_MONTH_MIN_RATE_MULTIPLE = 2.0

# A flagged month additionally needs at least this many presence days
# itself, so one lucky single-day sighting in an otherwise-quiet month can
# never alone clear the multiple-of-average bar above.
SEASONAL_MIN_PRESENCE_DAYS_IN_FLAGGED_MONTH = 2

SeasonalPatternStatus = Literal[
    "insufficient_history", "no_pattern_detected", "developing_pattern", "established_pattern"
]


@dataclass(frozen=True)
class MonthPresence:
    """One calendar month's usable-day and presence-day counts within the
    366-day window. Always present for all 12 months, even at zero, so a
    drill-down view can show the whole year's shape honestly (see Phase 14
    -- explainability) rather than only the months with a nonzero count."""

    month: int  # 1-12
    usable_day_count: int
    presence_day_count: int

    @property
    def presence_rate(self) -> float | None:
        if self.usable_day_count == 0:
            return None
        return self.presence_day_count / self.usable_day_count


@dataclass(frozen=True)
class SeasonalPattern:
    """One taxon's seasonal pattern over the trailing 366-day window."""

    taxon: TaxonFact
    status: SeasonalPatternStatus
    months: tuple[MonthPresence, ...]  # always 12 entries, ordered 1..12
    typical_months: tuple[int, ...]  # only non-empty when status == "established_pattern"
    current_month_is_typical: bool | None  # None unless status == "established_pattern"


def presence_dates_by_taxon(
    window_visits: Iterable[VisitFact], *, local_timezone: tzinfo
) -> dict[str, set[date]]:
    """Group already-confirmed `VisitFact`s into a set of distinct local
    presence dates per taxon label.

    Shared, small helper reused by `habitat_association.py` -- both modules
    need exactly this grouping from the same `window_visits` sequence
    `historical_baseline`/`place_change_summary` already consume, so it is
    written once here rather than re-derived per module. Only Visits with a
    `confirmed_taxon` contribute (the same reviewed-only truth contract
    every sibling module in this package applies); this function does not
    itself filter by category (wildlife vs. non-wildlife) -- callers pass
    already-appropriately-scoped `window_visits`, exactly like
    `place_change_summary._presence_dates_by_taxon_and_overall`'s own
    calling convention.
    """

    presence_by_taxon: dict[str, set[date]] = {}
    for visit in window_visits:
        if visit.confirmed_taxon is None:
            continue
        local_date = visit.activity_started_at.astimezone(local_timezone).date()
        presence_by_taxon.setdefault(visit.confirmed_taxon.label, set()).add(local_date)
    return presence_by_taxon


def _month_skeleton(usable_dates: AbstractSet[date]) -> list[MonthPresence]:
    usable_count_by_month = [0] * 13  # index 0 unused, 1..12 real
    for usable_date in usable_dates:
        usable_count_by_month[usable_date.month] += 1
    return [
        MonthPresence(month=month, usable_day_count=usable_count_by_month[month], presence_day_count=0)
        for month in range(1, 13)
    ]


def _place_wide_seasonal_maturity(months: Sequence[MonthPresence]) -> bool:
    distinct_usable_months = sum(
        1 for month in months if month.usable_day_count >= SEASONAL_MIN_USABLE_DAYS_IN_MONTH
    )
    return distinct_usable_months >= SEASONAL_MIN_DISTINCT_USABLE_MONTHS


def compute_seasonal_patterns(
    window_visits: Iterable[VisitFact],
    *,
    taxa: Mapping[str, TaxonFact],
    usable_dates: AbstractSet[date],
    local_timezone: tzinfo,
    reference_month: int,
) -> dict[str, SeasonalPattern]:
    """Compute one `SeasonalPattern` per taxon in `taxa`.

    `reference_month` is the caller's own "current" local month (1-12) --
    a test-only-overridable, explicit parameter rather than this module
    calling `datetime.now()` itself, matching every other pure module in
    this package's "no wall-clock reads" discipline. It only decides
    `current_month_is_typical`; it plays no role in the maturity gate or
    per-month rate computation.

    Every taxon present in `taxa` gets an entry, even one with zero
    presence in the window (a `SeasonalPattern` with `status=
    "insufficient_history"` and every `MonthPresence.presence_day_count`
    at 0) -- absence is a valid, honestly-represented outcome, never
    silently omitted (see product-doctrine.md's abstention discipline).
    """

    if not 1 <= reference_month <= 12:
        raise ValueError("reference_month must be 1..12")

    base_months = _month_skeleton(usable_dates)
    place_is_mature = _place_wide_seasonal_maturity(base_months)
    presence_by_taxon = presence_dates_by_taxon(window_visits, local_timezone=local_timezone)

    results: dict[str, SeasonalPattern] = {}
    for label, taxon in taxa.items():
        presence_dates = presence_by_taxon.get(label, set())
        months = _months_for_taxon(base_months, presence_dates)
        total_presence_days = len(presence_dates)

        if not place_is_mature or total_presence_days < SEASONAL_MIN_PRESENCE_DAYS_FOR_PATTERN:
            results[label] = SeasonalPattern(
                taxon=taxon,
                status="insufficient_history",
                months=tuple(months),
                typical_months=(),
                current_month_is_typical=None,
            )
            continue

        qualifying = [month for month in months if month.usable_day_count >= SEASONAL_MIN_USABLE_DAYS_IN_MONTH]
        rates = [month.presence_rate for month in qualifying if month.presence_rate is not None]
        average_rate = sum(rates) / len(rates) if rates else 0.0

        typical_months = tuple(
            month.month
            for month in qualifying
            if month.presence_rate is not None
            and month.presence_day_count >= SEASONAL_MIN_PRESENCE_DAYS_IN_FLAGGED_MONTH
            and average_rate > 0
            and month.presence_rate >= average_rate * SEASONAL_MONTH_MIN_RATE_MULTIPLE
        )

        if typical_months:
            status = "established_pattern"
        elif len(qualifying) >= 2 and sum(1 for month in qualifying if month.presence_day_count > 0) >= 2:
            # Presence spans at least two well-monitored months without any
            # of them standing out -- a real, honestly year-round pattern,
            # not a lack of data.
            status = "no_pattern_detected"
        else:
            # Some signal exists (enough total presence days to pass the
            # taxon-level gate above) but not enough distinct qualifying
            # months to say anything confident about its shape yet.
            status = "developing_pattern"

        results[label] = SeasonalPattern(
            taxon=taxon,
            status=status,
            months=tuple(months),
            typical_months=typical_months,
            current_month_is_typical=(reference_month in typical_months) if status == "established_pattern" else None,
        )

    return results


def _months_for_taxon(
    base_months: Sequence[MonthPresence], presence_dates: AbstractSet[date]
) -> list[MonthPresence]:
    presence_count_by_month = [0] * 13
    for presence_date in presence_dates:
        presence_count_by_month[presence_date.month] += 1
    return [
        MonthPresence(
            month=month.month,
            usable_day_count=month.usable_day_count,
            presence_day_count=presence_count_by_month[month.month],
        )
        for month in base_months
    ]
