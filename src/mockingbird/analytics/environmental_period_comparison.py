"""Environmental Context x Place Story & Habitat Change Composition v1: a
small, pure comparison of already-cached local weather across two
calendar-day windows -- the identical before/after periods `mockingbird.
analytics.feature_change_comparison` already establishes for one Place
Feature change event (see `feature_change_comparison.comparison_window_dates`).
Context only, never a cause: this module never claims the weather caused a
wildlife change, only that conditions differed (or did not) between the two
periods being compared -- see "External ecological context" in
product-doctrine.md and this milestone's own governing brief, Phase 5/10.

## No new statistical primitive

Materiality is decided entirely by reusing `mockingbird.environment.
condition_bands`'s own already-accepted classifiers -- the identical
Place-relative temperature-tertile banding and physical wet/dry
precipitation threshold Environmental Context v2's `weather_association.py`
already applies to single days -- applied here to a whole period's own
mean/majority instead. Two periods are "meaningfully different" only when
they classify into *different* bands under those unmodified classifiers,
never a newly-invented degrees/percentage cutoff:

- **Temperature**: each period's own mean daily temperature is classified
  against the Place's existing `TemperatureBaseline` (unmodified
  `classify_temperature_day`). A note is produced only when the two periods
  land in genuinely different bands -- both landing in the same band (even
  "both cooler than typical") stays silent, an intentional conservative
  bias toward abstention over a borderline claim.
- **Precipitation**: each period's own per-day wet/dry classification
  (unmodified `classify_precipitation_day`, a fixed physical threshold, not
  Place-relative) is rolled up into a period-level wet-majority/dry-majority
  verdict. A note is produced only when the two periods' majorities differ.

A period that lacks `MIN_USABLE_DAYS_PER_PERIOD` cached, hourly-complete
days of its own (reusing `conditional_association`'s own default per-side
sample floor, not a new number -- "do not create a second exposure system")
abstains honestly on that metric rather than guessing from a thin sample;
`status` is `"insufficient_coverage"` only when *neither* metric could be
evaluated at all.

## Reuse across Deliverable A and B

This module is called from exactly one place,
`ProductRepository._feature_environmental_period_comparison`, shared by
Place Feature before/after (`get_place_feature_detail`) and Place Story's
`comparison_insight` events (`_place_story_feature_events`) -- one weather-
period-comparison path, not two. `summarize_environmental_period_comparison`
is the one place English wording is produced, so the two surfaces can never
phrase the same comparison differently.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import AbstractSet, Literal, Mapping

from mockingbird.analytics.conditional_association import DEFAULT_MIN_USABLE_DAYS_IN_CONDITION
from mockingbird.environment.condition_bands import (
    TemperatureBaseline,
    classify_precipitation_day,
    classify_temperature_day,
)

# Reuses `conditional_association`'s own default per-side sample floor
# rather than inventing a second one -- see the module docstring's "No new
# statistical primitive."
MIN_USABLE_DAYS_PER_PERIOD = DEFAULT_MIN_USABLE_DAYS_IN_CONDITION

EnvironmentalPeriodComparisonStatus = Literal["comparable", "insufficient_coverage"]


def _period_mean(daily_values: Mapping[date, float], period_dates: AbstractSet[date]) -> tuple[float | None, int]:
    values = [value for day, value in daily_values.items() if day in period_dates]
    if not values:
        return None, 0
    return sum(values) / len(values), len(values)


def _period_total(daily_values: Mapping[date, float], period_dates: AbstractSet[date]) -> tuple[float | None, int]:
    values = [value for day, value in daily_values.items() if day in period_dates]
    if not values:
        return None, 0
    return sum(values), len(values)


@dataclass(frozen=True)
class EnvironmentalPeriodComparison:
    """One before/after environmental comparison over two already-fixed
    calendar-day windows. `status` is `"insufficient_coverage"` only when
    *neither* temperature nor precipitation could be evaluated at all (each
    period lacked `MIN_USABLE_DAYS_PER_PERIOD` cached days) -- one metric
    succeeding while the other abstains is still `"comparable"` overall,
    mirroring `TaxonPlaceContext`'s "neither field ever blocks or degrades
    the other" convention. `pre_mean_temperature_c`/`post_mean_temperature_c`
    are `None` exactly when that period had too few usable temperature days
    to trust a mean; `..._total_precipitation_mm` mirrors this for
    precipitation. Either note may be `None` independently of `status`: a
    metric can be evaluated (enough days, in `status="comparable"`) and
    still find nothing meaningfully different to say."""

    status: EnvironmentalPeriodComparisonStatus
    pre_mean_temperature_c: float | None
    post_mean_temperature_c: float | None
    pre_usable_temperature_days: int
    post_usable_temperature_days: int
    pre_total_precipitation_mm: float | None
    post_total_precipitation_mm: float | None
    pre_usable_precipitation_days: int
    post_usable_precipitation_days: int
    temperature_note: str | None
    precipitation_note: str | None


def compute_environmental_period_comparison(
    *,
    pre_dates: AbstractSet[date],
    post_dates: AbstractSet[date],
    temperature_baseline: TemperatureBaseline,
    daily_mean_temperatures_c: Mapping[date, float],
    daily_total_precipitation_mm: Mapping[date, float],
    min_usable_days_per_period: int = MIN_USABLE_DAYS_PER_PERIOD,
) -> EnvironmentalPeriodComparison:
    """`daily_mean_temperatures_c`/`daily_total_precipitation_mm` should
    already be restricted to hourly-complete ("usable") dates -- see
    `condition_bands.usable_environmental_dates` -- this function does not
    itself judge per-day completeness, only per-period sample size."""

    pre_mean_c, pre_temp_days = _period_mean(daily_mean_temperatures_c, pre_dates)
    post_mean_c, post_temp_days = _period_mean(daily_mean_temperatures_c, post_dates)
    pre_precip_total, pre_precip_days = _period_total(daily_total_precipitation_mm, pre_dates)
    post_precip_total, post_precip_days = _period_total(daily_total_precipitation_mm, post_dates)

    temp_available = pre_temp_days >= min_usable_days_per_period and post_temp_days >= min_usable_days_per_period
    precip_available = (
        pre_precip_days >= min_usable_days_per_period and post_precip_days >= min_usable_days_per_period
    )

    temperature_note: str | None = None
    temp_classified = False
    if temp_available:
        assert pre_mean_c is not None and post_mean_c is not None
        pre_band = classify_temperature_day(pre_mean_c, temperature_baseline)
        post_band = classify_temperature_day(post_mean_c, temperature_baseline)
        temp_classified = pre_band is not None and post_band is not None
        if temp_classified and pre_band != post_band:
            direction = "cooler" if post_mean_c < pre_mean_c else "warmer"
            temperature_note = f"The after period was notably {direction}."

    precipitation_note: str | None = None
    if precip_available:
        assert pre_precip_total is not None and post_precip_total is not None
        pre_wet_days = sum(
            1
            for day, total_mm in daily_total_precipitation_mm.items()
            if day in pre_dates and classify_precipitation_day(total_mm) == "wet_day"
        )
        post_wet_days = sum(
            1
            for day, total_mm in daily_total_precipitation_mm.items()
            if day in post_dates and classify_precipitation_day(total_mm) == "wet_day"
        )
        # A clear majority, not merely more wet days than dry -- a tie
        # (exactly half) counts as "not predominantly wet," the same
        # "requires a clear majority" discipline `conditional_association`'s
        # own rate-difference floor already applies elsewhere.
        pre_wet_majority = pre_wet_days > pre_precip_days / 2
        post_wet_majority = post_wet_days > post_precip_days / 2
        if pre_wet_majority != post_wet_majority:
            direction = "higher" if post_wet_majority else "lower"
            precipitation_note = f"Rainfall was {direction} during the after period."

    status: EnvironmentalPeriodComparisonStatus = (
        "comparable" if (temp_classified or precip_available) else "insufficient_coverage"
    )

    return EnvironmentalPeriodComparison(
        status=status,
        pre_mean_temperature_c=pre_mean_c if temp_available else None,
        post_mean_temperature_c=post_mean_c if temp_available else None,
        pre_usable_temperature_days=pre_temp_days,
        post_usable_temperature_days=post_temp_days,
        pre_total_precipitation_mm=pre_precip_total if precip_available else None,
        post_total_precipitation_mm=post_precip_total if precip_available else None,
        pre_usable_precipitation_days=pre_precip_days,
        post_usable_precipitation_days=post_precip_days,
        temperature_note=temperature_note,
        precipitation_note=precipitation_note,
    )


def summarize_environmental_period_comparison(
    comparison: EnvironmentalPeriodComparison, *, include_neutral: bool
) -> str | None:
    """Compose `comparison`'s notes into one compact, non-causal sentence
    (never "caused"/"led to"/"because of" -- association language only, per
    product-doctrine.md "External ecological context"). Returns `None`
    whenever `comparison.status != "comparable"` (nothing to say at all).

    `include_neutral=True` (Place Feature before/after -- a dedicated
    comparison surface the user is already looking at, mirroring
    `featureAssociationSentence`'s own "Activity looked similar..." neutral
    case) always returns a sentence once `status == "comparable"`, including
    the neutral "broadly similar" case when neither metric found a
    meaningful difference. `include_neutral=False` (Place Story's
    `comparison_insight` caveat) returns `None` whenever there is nothing
    notable to add, so environmental context never turns an ordinary Story
    entry into a weather log (Phase 9 of the governing brief)."""

    if comparison.status != "comparable":
        return None
    notes = [note for note in (comparison.temperature_note, comparison.precipitation_note) if note]
    if notes:
        return " ".join(notes)
    if include_neutral:
        return "Conditions were broadly similar across the two periods."
    return None


__all__ = [
    "MIN_USABLE_DAYS_PER_PERIOD",
    "EnvironmentalPeriodComparisonStatus",
    "EnvironmentalPeriodComparison",
    "compute_environmental_period_comparison",
    "summarize_environmental_period_comparison",
]
