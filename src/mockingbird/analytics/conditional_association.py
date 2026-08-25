"""Place / Yard Intelligence v2: a generic, domain-agnostic primitive
answering one question -- "was presence more or less common on the subset of
usable days a named condition held, versus the rest?" -- from two plain date
sets and a set of presence dates.

This module has **no** taxon, Visit, habitat, or weather concept at all: it
is pure date-set arithmetic, deliberately kept that free of domain meaning
so any future date-scoped condition (a phenology phase today, an
external-weather-provider's "cold morning" day tomorrow) can reuse it
without a new threshold policy being invented per domain. Today it backs
only `habitat_association.py` -- see
docs/place-yard-intelligence-v2-contract.md section 3.3.

The threshold shape (a minimum-sample floor on both sides, a minimum
proportional-difference gate) deliberately mirrors
`place_change_summary`'s own policy for the same reason that module gives:
small denominators must not produce a dramatic-looking percentage. See
"Threshold policy" in docs/meaningful-change-detection-contract.md.

Association language only -- never causal. A caller must never render
"X causes Y" from this module's output; see product-doctrine.md's
"External ecological context" and the milestone's own Phase 10/11
instructions.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import AbstractSet, Literal

AssociationStatus = Literal[
    "insufficient_data",
    "no_clear_association",
    "more_common_under_condition",
    "less_common_under_condition",
]

# A condition-window needs at least this many usable days on *each* side
# (inside and outside the condition) before any ratio is trusted -- the
# exact same shape as `place_change_summary.MIN_REFERENCE_PRESENCE_DAYS_FOR_
# COMPARISON`'s intent, generalized: never divide by a near-zero denominator
# and call the result a pattern.
DEFAULT_MIN_USABLE_DAYS_IN_CONDITION = 5
DEFAULT_MIN_USABLE_DAYS_OUT_OF_CONDITION = 5

# A rate difference below this (as a fraction, e.g. 0.25 = 25 percentage
# points) is not called out as an association -- mirrors
# `place_change_summary.MIN_PROPORTIONAL_DIFFERENCE` exactly, reused for
# consistency across every threshold-gated claim in this milestone rather
# than inventing a second number with no principled reason to differ.
DEFAULT_MIN_RATE_DIFFERENCE = 0.25


@dataclass(frozen=True)
class ConditionalAssociation:
    """One condition's presence-rate comparison, with every count needed to
    explain it on drill-down (Phase 14) -- never just the final verdict."""

    status: AssociationStatus
    presence_days_in_condition: int
    usable_days_in_condition: int
    presence_days_out_of_condition: int
    usable_days_out_of_condition: int

    @property
    def rate_in_condition(self) -> float | None:
        if self.usable_days_in_condition == 0:
            return None
        return self.presence_days_in_condition / self.usable_days_in_condition

    @property
    def rate_out_of_condition(self) -> float | None:
        if self.usable_days_out_of_condition == 0:
            return None
        return self.presence_days_out_of_condition / self.usable_days_out_of_condition


def compute_conditional_association(
    presence_dates: AbstractSet[date],
    *,
    usable_dates: AbstractSet[date],
    condition_dates: AbstractSet[date],
    min_usable_days_in_condition: int = DEFAULT_MIN_USABLE_DAYS_IN_CONDITION,
    min_usable_days_out_of_condition: int = DEFAULT_MIN_USABLE_DAYS_OUT_OF_CONDITION,
    min_rate_difference: float = DEFAULT_MIN_RATE_DIFFERENCE,
) -> ConditionalAssociation:
    """Compare presence-day rate on usable days *inside* `condition_dates`
    against usable days *outside* it.

    `condition_dates` need not be a subset of `usable_dates` -- a condition
    active on an insufficiently-monitored day contributes nothing either
    way, exactly like `historical_baseline`'s own "insufficiently monitored"
    discipline: only the intersection with `usable_dates` is ever counted,
    so an unmonitored day can never manufacture a false association in
    either direction. `presence_dates` not in `usable_dates` at all (should
    not happen for correctly-gathered input, but defensively) are likewise
    only ever counted through their intersection with `usable_dates`.

    Returns `"insufficient_data"` whenever either side's usable-day count
    falls short of its floor -- before any rate is even computed, so a
    near-empty condition window can never produce a fabricated ratio.
    """

    usable_in_condition = usable_dates & condition_dates
    usable_out_of_condition = usable_dates - condition_dates
    presence_in_condition = presence_dates & usable_in_condition
    presence_out_of_condition = presence_dates & usable_out_of_condition

    usable_in_count = len(usable_in_condition)
    usable_out_count = len(usable_out_of_condition)
    presence_in_count = len(presence_in_condition)
    presence_out_count = len(presence_out_of_condition)

    if (
        usable_in_count < min_usable_days_in_condition
        or usable_out_count < min_usable_days_out_of_condition
    ):
        return ConditionalAssociation(
            status="insufficient_data",
            presence_days_in_condition=presence_in_count,
            usable_days_in_condition=usable_in_count,
            presence_days_out_of_condition=presence_out_count,
            usable_days_out_of_condition=usable_out_count,
        )

    rate_in = presence_in_count / usable_in_count
    rate_out = presence_out_count / usable_out_count
    difference = rate_in - rate_out

    if difference >= min_rate_difference:
        status: AssociationStatus = "more_common_under_condition"
    elif -difference >= min_rate_difference:
        status = "less_common_under_condition"
    else:
        status = "no_clear_association"

    return ConditionalAssociation(
        status=status,
        presence_days_in_condition=presence_in_count,
        usable_days_in_condition=usable_in_count,
        presence_days_out_of_condition=presence_out_count,
        usable_days_out_of_condition=usable_out_count,
    )
