"""Environmental Context v2: bounded, association-only wildlife-activity /
weather-condition associations -- "cardinal activity was higher on cooler
days," never a causal claim.

Mirrors `habitat_association.py`'s exact shape: a thin wrapper that prepares
date-sets from already-computed daily condition bands
(`mockingbird.environment.condition_bands`) and calls
`conditional_association`'s generic, gated primitive unmodified. See
docs/environmental-context-v2-contract.md "Phase 6/7" for why exactly two
condition axes are built (Place-relative temperature, physical-threshold
precipitation) and wind/cloud-cover associations are deliberately not.

Condition labels deliberately say "days," never "mornings" or any other
time-of-day word: `temperature_bands`/`precipitation_bands` classify whole
UTC calendar days, not a specific hour, so a label claiming morning-specific
timing would overstate what was actually computed -- even though the
governing milestone brief's own good-example text uses "cooler mornings,"
this module's honest granularity is daily, and it says so.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, tzinfo
from typing import AbstractSet, Iterable, Literal, Mapping

from mockingbird.analytics.conditional_association import (
    ConditionalAssociation,
    compute_conditional_association,
)
from mockingbird.analytics.place_activity_report import TaxonFact, VisitFact
from mockingbird.analytics.seasonal_pattern import presence_dates_by_taxon
from mockingbird.environment.condition_bands import PrecipitationBand, TemperatureBand

# Mirrors `conditional_association`'s own default sample floor (5) -- a
# pre-filter applied before ever calling the primitive, so a condition with
# too few days on either side is skipped silently rather than returned as a
# guaranteed `insufficient_data` result (Phase 30's product-value test: do
# not surface a result nobody can act on). Reuses the same number as the
# primitive's own default rather than inventing a second one with no
# principled reason to differ -- see `conditional_association.py`'s own
# docstring for this exact reasoning, applied here to a second domain.
MIN_CONDITION_DAYS_FOR_ATTEMPT = 5

WeatherCondition = Literal["cooler_than_typical", "warmer_than_typical", "wet_day"]

_CONDITION_LABELS: dict[WeatherCondition, str] = {
    "cooler_than_typical": "cooler days",
    "warmer_than_typical": "warmer days",
    "wet_day": "wet periods",
}


@dataclass(frozen=True)
class TaxonWeatherAssociation:
    """One taxon's presence-rate association with one weather condition
    axis."""

    taxon: TaxonFact
    condition: WeatherCondition
    condition_label: str
    association: ConditionalAssociation


def compute_weather_associations(
    window_visits: Iterable[VisitFact],
    *,
    taxa: Mapping[str, TaxonFact],
    usable_dates: AbstractSet[date],
    local_timezone: tzinfo,
    temperature_bands: Mapping[date, TemperatureBand],
    precipitation_bands: Mapping[date, PrecipitationBand],
) -> list[TaxonWeatherAssociation]:
    """Compute one `TaxonWeatherAssociation` per (taxon, condition) pair
    that has any realistic chance of clearing `conditional_association`'s
    own minimum-sample gate.

    `temperature_bands`/`precipitation_bands` should already be restricted
    to environmentally-usable dates (see `condition_bands.
    usable_environmental_dates`) -- a date absent from a mapping means "no
    usable weather data for that date," which this function keeps entirely
    separate from "present but not in this condition": a missing date is
    excluded from that axis's usable-date set altogether, never silently
    folded into the "out of condition" side (see the v2 contract's "Phase
    8 -- environmental coverage").

    Returns an empty list when both mappings are empty -- missing/disabled
    weather data must never break core Place intelligence, matching
    `compute_habitat_associations`'s identical coverage-safety discipline.
    """

    presence_by_taxon = presence_dates_by_taxon(window_visits, local_timezone=local_timezone)

    condition_date_sets: dict[WeatherCondition, set[date]] = {
        "cooler_than_typical": {
            day for day, band in temperature_bands.items() if band == "cooler_than_typical"
        },
        "warmer_than_typical": {
            day for day, band in temperature_bands.items() if band == "warmer_than_typical"
        },
        "wet_day": {day for day, band in precipitation_bands.items() if band == "wet_day"},
    }
    environmental_coverage: dict[WeatherCondition, AbstractSet[date]] = {
        "cooler_than_typical": temperature_bands.keys(),
        "warmer_than_typical": temperature_bands.keys(),
        "wet_day": precipitation_bands.keys(),
    }

    results: list[TaxonWeatherAssociation] = []
    for condition, condition_dates in condition_date_sets.items():
        axis_usable_dates = usable_dates & environmental_coverage[condition]
        if len(axis_usable_dates & condition_dates) < MIN_CONDITION_DAYS_FOR_ATTEMPT:
            continue
        if len(axis_usable_dates - condition_dates) < MIN_CONDITION_DAYS_FOR_ATTEMPT:
            continue

        for label, taxon in taxa.items():
            presence_dates = presence_by_taxon.get(label, set())
            if not presence_dates:
                continue
            association = compute_conditional_association(
                presence_dates, usable_dates=axis_usable_dates, condition_dates=condition_dates
            )
            if association.status == "insufficient_data":
                continue
            results.append(
                TaxonWeatherAssociation(
                    taxon=taxon,
                    condition=condition,
                    condition_label=_CONDITION_LABELS[condition],
                    association=association,
                )
            )

    return results


__all__ = [
    "MIN_CONDITION_DAYS_FOR_ATTEMPT",
    "WeatherCondition",
    "TaxonWeatherAssociation",
    "compute_weather_associations",
]
