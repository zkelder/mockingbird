"""Biodiversity & Place Intelligence v1: pure composition over already-
accepted Place Intelligence primitives (see docs/biodiversity-place-
intelligence-v1-contract.md).

This module computes **no** new truth. It takes the exact `HistoricalPlace
Baseline`/`dict[str, SpeciesHistoricalStatus]` pair `ProductRepository.
_historical_place_baseline_and_species_statuses` already produces on every
one of its four existing call sites (Today, Bird Log overview, Bird Log
history, and now this module too) and buckets/sorts it into a Place-wide,
"live view" summary -- the one composition none of those callers perform,
because each narrows the same result to a report period, a single day, or
a single label. See `historical-baseline-maturity-contract.md` for what
`SpeciesHistoricalStatus.status` means and `canonical-new-regular-species-
contract.md` for why every surface must read it through this exact value,
never re-derive it.

## Reuse, not a second analytics path

Like every sibling module in this package, this file never opens a
database session and never re-derives review-truth precedence, wildlife
eligibility, or the new/regular/first_record/seen_before determination
itself. `ProductRepository.place_biodiversity_summary` is the only caller;
it owns every query (reusing `_historical_place_baseline_and_species_
statuses`, `list_likely_species_overview`, `get_place_habitat_context`,
`get_place_environmental_context_today` unmodified) and hands this module
only already-resolved facts.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Iterable

from mockingbird.analytics.historical_baseline import (
    HistoricalPlaceBaseline,
    SpeciesHistoricalStatus,
)

# "Recently observed" reuses the exact 14-day window already established in
# three other places in this codebase: `WildlifeJournalLabelSummary.
# recent_activity`'s sparkline, `_dashboard_today_summary`'s legacy
# `recent_regulars` lookback, and `place_change_summary.
# RECENT_WINDOW_FRESHNESS_CAP_DAYS`. Not a fourth, independently-chosen
# number -- see "New / Regular / Recent semantics" in the contract doc for
# why this is deliberately *not* coverage-gated the way "regular" is.
RECENTLY_OBSERVED_WINDOW_DAYS = 14


@dataclass(frozen=True)
class PlaceBiodiversitySummary:
    """A Place-wide, "as of right now" biodiversity summary. Every field
    here derives entirely from `statuses`/`historical_baseline` -- this
    dataclass adds bucketing and honest-state warnings, never a new fact.
    """

    generated_at: datetime
    historical_baseline: HistoricalPlaceBaseline
    distinct_species_count: int
    # Every all-time-confirmed wildlife taxon, most-recently-confirmed
    # first. Unbounded -- see the contract doc's "Known limitations" for
    # why (bounded only by distinct confirmed-label count, reusing
    # `historical_baseline`'s own already-accepted reasoning).
    taxa: tuple[SpeciesHistoricalStatus, ...]
    # Convenience subsets of `taxa` -- not mutually exclusive, and not a
    # partition (a taxon can be `new_taxa` and `recently_observed_taxa`
    # simultaneously; a taxon can be `regular_taxa` and absent from
    # `recently_observed_taxa` simultaneously, which is never itself
    # surfaced as an "absent"/"gone" claim -- see the contract doc).
    new_taxa: tuple[SpeciesHistoricalStatus, ...]
    regular_taxa: tuple[SpeciesHistoricalStatus, ...]
    recently_observed_taxa: tuple[SpeciesHistoricalStatus, ...]
    warnings: tuple[str, ...]


def _warnings_for_baseline(historical_baseline: HistoricalPlaceBaseline) -> tuple[str, ...]:
    """Calm, honest, mutually-exclusive-by-construction (never more than
    one fires) qualification of the headline counts -- mirrors `place_
    activity_report`'s own `warnings` convention. `total_monitored_seconds
    is None` is `HistoricalPlaceBaseline`'s own established "no durable
    exposure history exists at all" signal (see historical_baseline.py),
    distinct from a real zero for a Place monitored heavily outside the
    366-day window."""

    if historical_baseline.total_monitored_seconds is None:
        return (
            "No monitoring history recorded yet -- biodiversity facts here "
            "will fill in once a Stream has been observing.",
        )
    if historical_baseline.maturity == "insufficient":
        return (
            "Not enough monitored history yet to say what's new or regular "
            "at this Place -- confirmed sightings are still shown below.",
        )
    if historical_baseline.maturity == "developing":
        return (
            "Monitoring history here is still developing -- \"regular\" and "
            "\"new\" labels will get more reliable as more history accumulates.",
        )
    return ()


def compute_place_biodiversity_summary(
    statuses: Iterable[SpeciesHistoricalStatus],
    *,
    historical_baseline: HistoricalPlaceBaseline,
    generated_at: datetime,
) -> PlaceBiodiversitySummary:
    """`statuses` is every entry of the `dict[str, SpeciesHistoricalStatus]`
    `_historical_place_baseline_and_species_statuses` already returns
    (`.values()`, in any order) -- this function performs no filtering of
    its own beyond the bucketing described on `PlaceBiodiversitySummary`.
    `generated_at` must be timezone-aware and is the sole clock reference
    (never `datetime.now()` internally), matching every other pure function
    in this package's "reproducible from persisted facts" discipline.
    """

    # Mirrors `wildlife_journal_overview`'s own sort idiom (negate the
    # timestamp to combine a descending-datetime, ascending-string key in
    # one pass) -- most-recently-confirmed first, ties broken by label.
    ordered = tuple(
        sorted(
            statuses,
            key=lambda status: (-status.last_confirmed_at.timestamp(), status.taxon.label),
        )
    )
    recently_observed_cutoff = generated_at - timedelta(days=RECENTLY_OBSERVED_WINDOW_DAYS)
    return PlaceBiodiversitySummary(
        generated_at=generated_at,
        historical_baseline=historical_baseline,
        distinct_species_count=sum(1 for status in ordered if status.taxon.is_species),
        taxa=ordered,
        new_taxa=tuple(status for status in ordered if status.status in ("new", "first_record")),
        regular_taxa=tuple(status for status in ordered if status.status == "regular"),
        recently_observed_taxa=tuple(
            status for status in ordered if status.last_confirmed_at >= recently_observed_cutoff
        ),
        warnings=_warnings_for_baseline(historical_baseline),
    )
