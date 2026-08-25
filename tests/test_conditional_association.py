"""Pure computation tests for mockingbird.analytics.conditional_association.

No repository, no database -- matches the existing test_place_change_summary.py
precedent for a pure sibling module. See "Threshold policy" in
docs/meaningful-change-detection-contract.md for the shared minimum-sample /
minimum-rate-difference policy this generic date-set primitive reuses, and
docs/place-yard-intelligence-v2-contract.md section 3.3 for the one caller
(`habitat_association.py`) that builds on it today.
"""

from __future__ import annotations

from datetime import date, timedelta

from mockingbird.analytics.conditional_association import (
    ConditionalAssociation,
    compute_conditional_association,
)

# An arbitrary anchor date for every scenario below -- nothing in this module
# is timezone- or calendar-boundary-sensitive, so a fixed, unremarkable start
# date keeps every test's date arithmetic easy to verify by inspection.
BASE = date(2026, 1, 1)


def _dates(start: date, count: int) -> set[date]:
    """`count` consecutive calendar dates starting at (and including) `start`."""

    return {start + timedelta(days=offset) for offset in range(count)}


# ---------------------------------------------------------------------------
# insufficient_data
# ---------------------------------------------------------------------------


def test_insufficient_data_when_usable_days_in_condition_below_minimum() -> None:
    """3 usable days fall inside the condition; the default floor is 5."""

    usable = _dates(BASE, 20)
    condition = _dates(BASE, 3)
    presence = _dates(BASE, 3) | _dates(BASE + timedelta(days=10), 5)

    result = compute_conditional_association(presence, usable_dates=usable, condition_dates=condition)

    assert result.status == "insufficient_data"
    assert result.usable_days_in_condition == 3
    assert result.usable_days_out_of_condition == 17
    # Counts are still honestly reported even though no rate was trusted.
    assert result.presence_days_in_condition == 3
    assert result.presence_days_out_of_condition == 5


def test_insufficient_data_when_usable_days_out_of_condition_below_minimum() -> None:
    """Plenty of usable days (17) fall inside the condition, but only 3 --
    below the default floor of 5 -- remain outside it."""

    usable = _dates(BASE, 20)
    condition = _dates(BASE, 17)
    presence = _dates(BASE, 10)

    result = compute_conditional_association(presence, usable_dates=usable, condition_dates=condition)

    assert result.status == "insufficient_data"
    assert result.usable_days_in_condition == 17
    assert result.usable_days_out_of_condition == 3


# ---------------------------------------------------------------------------
# Threshold-gated verdicts
# ---------------------------------------------------------------------------


def test_more_common_under_condition_with_concrete_counts() -> None:
    usable = _dates(BASE, 20)
    condition = _dates(BASE, 10)
    presence = _dates(BASE, 8) | _dates(BASE + timedelta(days=10), 2)  # 8/10 inside, 2/10 outside

    result = compute_conditional_association(presence, usable_dates=usable, condition_dates=condition)

    assert result.presence_days_in_condition == 8
    assert result.usable_days_in_condition == 10
    assert result.presence_days_out_of_condition == 2
    assert result.usable_days_out_of_condition == 10
    assert result.status == "more_common_under_condition"


def test_less_common_under_condition_is_the_mirror_case() -> None:
    usable = _dates(BASE, 20)
    condition = _dates(BASE, 10)
    presence = _dates(BASE, 2) | _dates(BASE + timedelta(days=10), 8)  # 2/10 inside, 8/10 outside

    result = compute_conditional_association(presence, usable_dates=usable, condition_dates=condition)

    assert result.presence_days_in_condition == 2
    assert result.presence_days_out_of_condition == 8
    assert result.status == "less_common_under_condition"


def test_no_clear_association_when_rate_difference_is_below_threshold() -> None:
    usable = _dates(BASE, 20)
    condition = _dates(BASE, 10)
    presence = _dates(BASE, 5) | _dates(BASE + timedelta(days=10), 4)  # 5/10 vs 4/10, diff = 0.1

    result = compute_conditional_association(presence, usable_dates=usable, condition_dates=condition)

    assert result.status == "no_clear_association"


# ---------------------------------------------------------------------------
# Only the intersection with usable_dates is ever counted
# ---------------------------------------------------------------------------


def test_condition_day_outside_usable_dates_counts_toward_neither_side() -> None:
    """`condition_dates` need not be a subset of `usable_dates` -- a day that
    is nominally "inside the condition" but was never usable (unmonitored)
    must inflate neither the in-condition usable count nor its presence
    count."""

    usable = _dates(BASE, 20)
    unmonitored_day = date(2025, 12, 25)
    assert unmonitored_day not in usable

    condition = _dates(BASE, 10) | {unmonitored_day}
    presence = _dates(BASE, 8) | {unmonitored_day} | _dates(BASE + timedelta(days=10), 2)

    result = compute_conditional_association(presence, usable_dates=usable, condition_dates=condition)

    assert result.usable_days_in_condition == 10
    assert result.presence_days_in_condition == 8
    assert result.usable_days_out_of_condition == 10
    assert result.presence_days_out_of_condition == 2
    assert result.status == "more_common_under_condition"


def test_presence_date_outside_usable_dates_does_not_leak_into_either_bucket() -> None:
    """A presence date that was never a usable day at all (should not happen
    for correctly-gathered input, but defensively) must not be counted
    toward either side."""

    usable = _dates(BASE, 20)
    condition = _dates(BASE, 10)
    stray_presence_day = date(2025, 11, 1)
    assert stray_presence_day not in usable and stray_presence_day not in condition

    presence = _dates(BASE, 8) | _dates(BASE + timedelta(days=10), 2) | {stray_presence_day}

    result = compute_conditional_association(presence, usable_dates=usable, condition_dates=condition)

    assert result.presence_days_in_condition == 8
    assert result.presence_days_out_of_condition == 2
    assert result.usable_days_in_condition == 10
    assert result.usable_days_out_of_condition == 10


# ---------------------------------------------------------------------------
# ConditionalAssociation.rate_in_condition / rate_out_of_condition
# ---------------------------------------------------------------------------


class TestRateProperties:
    def test_rate_in_condition_is_none_when_its_denominator_is_zero(self) -> None:
        association = ConditionalAssociation(
            status="insufficient_data",
            presence_days_in_condition=0,
            usable_days_in_condition=0,
            presence_days_out_of_condition=5,
            usable_days_out_of_condition=10,
        )
        assert association.rate_in_condition is None
        assert association.rate_out_of_condition == 0.5

    def test_rate_out_of_condition_is_none_when_its_denominator_is_zero(self) -> None:
        association = ConditionalAssociation(
            status="insufficient_data",
            presence_days_in_condition=3,
            usable_days_in_condition=10,
            presence_days_out_of_condition=0,
            usable_days_out_of_condition=0,
        )
        assert association.rate_in_condition == 0.3
        assert association.rate_out_of_condition is None

    def test_both_rates_are_correct_floats_when_denominators_are_nonzero(self) -> None:
        association = ConditionalAssociation(
            status="more_common_under_condition",
            presence_days_in_condition=8,
            usable_days_in_condition=10,
            presence_days_out_of_condition=2,
            usable_days_out_of_condition=10,
        )
        assert association.rate_in_condition == 0.8
        assert association.rate_out_of_condition == 0.2


# ---------------------------------------------------------------------------
# Custom thresholds
# ---------------------------------------------------------------------------


class TestCustomThresholds:
    def test_loosening_min_usable_days_in_condition_turns_insufficient_data_into_a_verdict(self) -> None:
        usable = _dates(BASE, 20)
        condition = _dates(BASE, 3)  # below the default floor of 5
        presence = _dates(BASE, 3)  # every in-condition usable day has presence, none outside

        default_result = compute_conditional_association(presence, usable_dates=usable, condition_dates=condition)
        assert default_result.status == "insufficient_data"

        loosened_result = compute_conditional_association(
            presence, usable_dates=usable, condition_dates=condition, min_usable_days_in_condition=3
        )
        assert loosened_result.status == "more_common_under_condition"

    def test_loosening_min_usable_days_out_of_condition_turns_insufficient_data_into_a_verdict(self) -> None:
        usable = _dates(BASE, 20)
        condition = _dates(BASE, 17)  # only 3 usable days remain outside -- below the default floor of 5
        presence = _dates(BASE, 17)  # every in-condition usable day has presence, none outside

        default_result = compute_conditional_association(presence, usable_dates=usable, condition_dates=condition)
        assert default_result.status == "insufficient_data"

        loosened_result = compute_conditional_association(
            presence, usable_dates=usable, condition_dates=condition, min_usable_days_out_of_condition=3
        )
        assert loosened_result.status == "more_common_under_condition"

    def test_loosening_min_rate_difference_turns_no_clear_association_into_a_verdict(self) -> None:
        usable = _dates(BASE, 20)
        condition = _dates(BASE, 10)
        presence = _dates(BASE, 5) | _dates(BASE + timedelta(days=10), 4)  # 5/10 vs 4/10, diff = 0.1

        default_result = compute_conditional_association(presence, usable_dates=usable, condition_dates=condition)
        assert default_result.status == "no_clear_association"

        loosened_result = compute_conditional_association(
            presence, usable_dates=usable, condition_dates=condition, min_rate_difference=0.05
        )
        assert loosened_result.status == "more_common_under_condition"


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


def test_deterministic_for_identical_inputs() -> None:
    usable = _dates(BASE, 20)
    condition = _dates(BASE, 10)
    presence = _dates(BASE, 8) | _dates(BASE + timedelta(days=10), 2)

    first = compute_conditional_association(presence, usable_dates=usable, condition_dates=condition)
    second = compute_conditional_association(
        set(presence), usable_dates=set(usable), condition_dates=set(condition)
    )

    assert first == second
