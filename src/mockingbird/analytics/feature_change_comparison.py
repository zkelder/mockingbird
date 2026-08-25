"""Place Features & Habitat Change v2: bounded, association-only before/after
comparison around one Reviewed Place Feature Change Event -- "was confirmed
wildlife activity more or less common in the monitored window after this
change than in the monitored window before it," never a causal claim (see
Phase 10/23 of the governing brief and "External ecological context" in
product-doctrine.md).

No new statistical primitive: this module is a thin date-set builder around
`conditional_association.compute_conditional_association`, exactly the
shape `habitat_association.py` already is for phenology intervals (see that
module's own docstring, which explicitly names this exact "before/after
change-event" case as the thing it does *not* build). The one genuinely new
piece -- confirmed absent from every existing wrapper by direct inspection
of `habitat_association.py` and `weather_association.py` -- is a date-set
builder for "N days before and after one instant," rather than an interval
or a per-day condition band.

Window selection (Phase 11 of the governing brief): try the smallest
canonical window first (7 days each side), escalate to 14 then 30 only if
the smaller window's usable dates cannot clear `conditional_association`'s
own default sample floor -- reused verbatim, never a new number, per "do
not create a second exposure system." A window is only attempted once its
*entire* post-period has already elapsed relative to `today`: comparing a
partial, still-accumulating post-period against a complete pre-period would
understate the post side's own true rate, never an honest comparison.
Bounding the largest window to 30 days also keeps seasonality from
confounding the comparison (never January vs. June).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import AbstractSet, Literal

from mockingbird.analytics.conditional_association import (
    ConditionalAssociation,
    compute_conditional_association,
)

# Smallest-first: a fresher, shorter window is preferred whenever it already
# has enough monitored history to say something. Bounded to three sizes so
# a comparison can never silently widen until it happens to clear the floor
# regardless of season -- see "Comparison window safety" in the governing
# brief.
CANDIDATE_WINDOW_DAYS: tuple[int, ...] = (7, 14, 30)

# Mirrors the governing brief's own three-state sketch ("Too soon to tell /
# Early signal / Enough history for comparison," Phase 19) with one further
# honest split: "not enough elapsed time yet" and "enough time has passed
# but camera coverage was too thin" are different, differently-actionable
# facts (Phase 10 lists them as separate possible outcomes), so this module
# keeps them as two distinct values rather than collapsing both into one
# generic "too soon" -- a caller that wants the brief's exact three-state
# vocabulary may still treat both as "not yet comparable."
FeatureComparisonMaturity = Literal[
    "too_soon", "insufficient_coverage", "early_signal", "comparable"
]


@dataclass(frozen=True)
class FeatureChangeComparison:
    """One change event's before/after outcome, plus enough of the
    underlying window shape to explain it honestly on drill-down -- never
    just a final verdict. `window_days`/`pre_start`/`post_end`/`association`
    are all `None` exactly when `maturity` is `"too_soon"` or
    `"insufficient_coverage"` (no window produced a trustworthy
    comparison)."""

    maturity: FeatureComparisonMaturity
    window_days: int | None
    pre_start: date | None
    post_end: date | None
    association: ConditionalAssociation | None


def _window_dates(effective_date: date, window_days: int) -> tuple[set[date], set[date], date]:
    """The `window_days` dates immediately before `effective_date`, and the
    `window_days` dates starting at (and including) `effective_date` --
    `effective_date` itself always counts as "after," matching
    `phenology_interval_covers`'s own start-date-inclusive convention."""

    pre_start = effective_date - timedelta(days=window_days)
    pre_dates = {pre_start + timedelta(days=offset) for offset in range(window_days)}
    post_dates = {effective_date + timedelta(days=offset) for offset in range(window_days)}
    return pre_dates, post_dates, pre_start


def compute_feature_change_comparison(
    presence_dates: AbstractSet[date],
    *,
    usable_dates: AbstractSet[date],
    effective_date: date,
    today: date,
    candidate_window_days: tuple[int, ...] = CANDIDATE_WINDOW_DAYS,
) -> FeatureChangeComparison:
    """Compare confirmed-wildlife presence-day rate in the monitored window
    before `effective_date` against the monitored window after it, at the
    smallest candidate window size whose usable-day counts clear
    `compute_conditional_association`'s own default floor.

    `usable_dates`/`presence_dates` must already be scoped to whatever the
    change event's own Feature is associated with (its Zone's Stream, or
    its Source's Streams) -- this function has no camera/Zone concept of
    its own, mirroring `habitat_association.compute_habitat_associations`'s
    identical "the caller has already scoped the date sets" contract.
    `usable_dates` need not itself be pre-restricted to the candidate
    windows -- this function only ever reads the intersection.
    """

    any_window_elapsed = False
    for window_days in candidate_window_days:
        post_end = effective_date + timedelta(days=window_days)
        if post_end > today:
            # This and every larger candidate window's post-period extends
            # past today -- nothing further to try.
            break
        any_window_elapsed = True
        pre_dates, post_dates, pre_start = _window_dates(effective_date, window_days)
        window_usable_dates = usable_dates & (pre_dates | post_dates)
        association = compute_conditional_association(
            presence_dates, usable_dates=window_usable_dates, condition_dates=post_dates,
        )
        if association.status == "insufficient_data":
            continue
        maturity: FeatureComparisonMaturity = (
            "comparable" if window_days == candidate_window_days[0] else "early_signal"
        )
        return FeatureChangeComparison(
            maturity=maturity,
            window_days=window_days,
            pre_start=pre_start,
            post_end=post_end,
            association=association,
        )

    if any_window_elapsed:
        # At least one window's post-period had fully elapsed, but even the
        # largest attempted window never cleared the floor -- genuinely not
        # enough comparable monitoring, a different honest message from
        # "too soon."
        return FeatureChangeComparison(
            maturity="insufficient_coverage", window_days=None, pre_start=None, post_end=None, association=None,
        )
    return FeatureChangeComparison(
        maturity="too_soon", window_days=None, pre_start=None, post_end=None, association=None,
    )


__all__ = [
    "CANDIDATE_WINDOW_DAYS",
    "FeatureComparisonMaturity",
    "FeatureChangeComparison",
    "compute_feature_change_comparison",
]
