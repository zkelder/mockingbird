"""Place-relative temperature banding, physical-threshold precipitation
classification, and a restrained plain-language conditions summary
(Environmental Context v2 -- see docs/environmental-context-v2-contract.md
"Phase 6/7/16"). Pure functions only: no database, no network access,
mirroring `mockingbird.environment.solar_context`'s "small pure function,
directly testable" shape.

Temperature is deliberately **Place-relative** (tertiles of this Place's
own recent daily-mean distribution), never an absolute threshold -- a 65
degF morning is not "cold" everywhere, and this module never claims
otherwise (see the governing milestone brief's own anti-example). Wet/dry
and cloud-cover bands are deliberately **not** Place-relative: "measurable
precipitation occurred" and "the sky was overcast" have stable physical
meaning independent of local climate, unlike temperature.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, tzinfo
from typing import AbstractSet, Iterable, Literal, Mapping

from mockingbird.environment.weather_provider import HourlyWeatherObservation, WeatherMetric

# A UTC calendar date needs at least this many of its 24 possible hourly
# readings present before its daily mean/sum is trusted for banding -- a
# partial fetch (e.g. 2 hours out of 24, from a mid-day provider outage)
# must never silently produce a skewed "daily" figure. Mirrors the house
# style of an explicit named completeness floor (e.g. `zone_insights`'s
# `>=2`-healthy-hour floor), chosen independently for this different unit
# (hours of a calendar day, not monitored seconds).
MIN_HOURLY_RECORDS_FOR_USABLE_ENVIRONMENTAL_DAY = 18

# Below this many distinct usable days, a Place-relative temperature
# baseline cannot be honestly computed -- `TemperatureBaseline.status`
# reports `"insufficient_baseline"` rather than fabricating a split from too
# few days.
MIN_DAYS_FOR_TEMPERATURE_BASELINE = 10

# Any measurable liquid-equivalent precipitation (rain or snow, combined --
# Open-Meteo's own `precipitation` field is already a combined total).
# Not a distinction between drizzle and a downpour; only "some precipitation
# occurred" vs. "none."
WET_DAY_PRECIPITATION_THRESHOLD_MM = 0.2

# A small nonzero floor so trace/instrument-noise snowfall does not flip an
# otherwise-dry, non-snowy hour into "snow".
SNOW_DAY_SNOWFALL_THRESHOLD_CM = 0.1

MOSTLY_CLEAR_MAX_CLOUD_COVER_PERCENT = 30.0
OVERCAST_MIN_CLOUD_COVER_PERCENT = 70.0

TemperatureBand = Literal["cooler_than_typical", "typical", "warmer_than_typical"]
TemperatureBaselineStatus = Literal["insufficient_baseline", "established"]
PrecipitationBand = Literal["wet_day", "dry_day"]
PrecipitationState = Literal["dry", "rain", "snow"]
CloudCoverBand = Literal["clear", "partly_cloudy", "overcast"]


@dataclass(frozen=True)
class TemperatureBaseline:
    """A Place's own recent daily-mean-temperature tertile split. `status`
    is always present and honest -- `"insufficient_baseline"` is a real,
    typed outcome, never a silently-omitted or fabricated one (matching
    `seasonal_pattern.py`'s "absence is a valid, honestly-represented
    outcome" convention)."""

    status: TemperatureBaselineStatus
    lower_tertile_c: float | None
    upper_tertile_c: float | None
    sample_day_count: int


def _quantile(sorted_values: list[float], q: float) -> float:
    """Linear interpolation between closest ranks (the same default method
    most statistics libraries use). `sorted_values` must be non-empty and
    already sorted ascending."""

    if len(sorted_values) == 1:
        return sorted_values[0]
    position = q * (len(sorted_values) - 1)
    lower_index = int(position)
    upper_index = min(lower_index + 1, len(sorted_values) - 1)
    fraction = position - lower_index
    return sorted_values[lower_index] + (sorted_values[upper_index] - sorted_values[lower_index]) * fraction


def compute_temperature_baseline(daily_mean_temperatures_c: Mapping[date, float]) -> TemperatureBaseline:
    """`daily_mean_temperatures_c` should already be restricted to usable
    dates (see `daily_mean`, below) -- this function does not itself judge
    per-day completeness."""

    sample_day_count = len(daily_mean_temperatures_c)
    if sample_day_count < MIN_DAYS_FOR_TEMPERATURE_BASELINE:
        return TemperatureBaseline(
            status="insufficient_baseline",
            lower_tertile_c=None,
            upper_tertile_c=None,
            sample_day_count=sample_day_count,
        )
    values = sorted(daily_mean_temperatures_c.values())
    return TemperatureBaseline(
        status="established",
        lower_tertile_c=_quantile(values, 1 / 3),
        upper_tertile_c=_quantile(values, 2 / 3),
        sample_day_count=sample_day_count,
    )


def classify_temperature_day(
    mean_temperature_c: float, baseline: TemperatureBaseline
) -> TemperatureBand | None:
    """`None` only when `baseline.status == "insufficient_baseline"` --
    never an absolute-threshold fallback classification (Phase 7: a
    Place-relative claim requires a Place-relative basis, or no claim at
    all)."""

    if baseline.status == "insufficient_baseline":
        return None
    assert baseline.lower_tertile_c is not None and baseline.upper_tertile_c is not None
    if mean_temperature_c < baseline.lower_tertile_c:
        return "cooler_than_typical"
    if mean_temperature_c > baseline.upper_tertile_c:
        return "warmer_than_typical"
    return "typical"


def classify_precipitation_day(total_precipitation_mm: float) -> PrecipitationBand:
    return "wet_day" if total_precipitation_mm >= WET_DAY_PRECIPITATION_THRESHOLD_MM else "dry_day"


def classify_precipitation_state(precipitation_mm: float, snowfall_cm: float) -> PrecipitationState:
    """Rain/snow/dry for a restrained plain-language description -- distinct
    from `classify_precipitation_day`'s coarser wet/dry statistical-
    association axis (see the v2 contract's "Phase 6/7" for why the
    association axis stays binary while the descriptive text can be more
    specific)."""

    if snowfall_cm >= SNOW_DAY_SNOWFALL_THRESHOLD_CM:
        return "snow"
    if precipitation_mm >= WET_DAY_PRECIPITATION_THRESHOLD_MM:
        return "rain"
    return "dry"


def classify_cloud_cover(cloud_cover_percent: float) -> CloudCoverBand:
    if cloud_cover_percent <= MOSTLY_CLEAR_MAX_CLOUD_COVER_PERCENT:
        return "clear"
    if cloud_cover_percent >= OVERCAST_MIN_CLOUD_COVER_PERCENT:
        return "overcast"
    return "partly_cloudy"


def _bucket_date(observation: HourlyWeatherObservation, *, local_timezone: tzinfo | None) -> date:
    """The calendar date one hourly observation is bucketed under.

    Defaults to `observation.for_date` (the UTC calendar date, matching how
    the record is stored/cached -- see weather_provider.py). When
    `local_timezone` is given, buckets by that timezone's calendar date
    instead: the existing wildlife-activity reporting pipeline
    (`presence_dates_by_taxon`, `usable_dates` from `historical_baseline`)
    already groups "day" by the report's own `local_timezone`, and a
    weather condition axis intersected against those date-sets must use the
    identical bucketing -- otherwise a Place far from UTC would see whole
    days of Visits and weather silently misaligned by the UTC/local offset,
    not merely a rare midnight-boundary rounding difference. This is the
    only place a local/civil-time concept enters this otherwise UTC-only
    module, and it is opt-in per call, never a default assumption baked
    into storage or fetching."""

    if local_timezone is None:
        return observation.for_date
    return observation.observed_at.astimezone(local_timezone).date()


def daily_hour_counts(
    observations: Iterable[HourlyWeatherObservation],
    *,
    metric: WeatherMetric,
    local_timezone: tzinfo | None = None,
) -> dict[date, int]:
    counts: dict[date, int] = {}
    for observation in observations:
        if observation.metric != metric:
            continue
        day = _bucket_date(observation, local_timezone=local_timezone)
        counts[day] = counts.get(day, 0) + 1
    return counts


def usable_environmental_dates(hour_counts: Mapping[date, int]) -> frozenset[date]:
    return frozenset(
        day
        for day, count in hour_counts.items()
        if count >= MIN_HOURLY_RECORDS_FOR_USABLE_ENVIRONMENTAL_DAY
    )


def daily_mean(
    observations: Iterable[HourlyWeatherObservation],
    *,
    metric: WeatherMetric,
    dates: AbstractSet[date] | None = None,
    local_timezone: tzinfo | None = None,
) -> dict[date, float]:
    """Mean of `metric`'s hourly values per calendar date (UTC by default;
    see `_bucket_date` for when/why to pass `local_timezone`). When `dates`
    is given, only those dates are considered eligible (typically the
    output of `usable_environmental_dates`, bucketed the same way) -- a
    date outside `dates` never appears in the result, even if some readings
    exist for it."""

    sums: dict[date, float] = {}
    counts: dict[date, int] = {}
    for observation in observations:
        if observation.metric != metric:
            continue
        day = _bucket_date(observation, local_timezone=local_timezone)
        if dates is not None and day not in dates:
            continue
        sums[day] = sums.get(day, 0.0) + observation.value_numeric
        counts[day] = counts.get(day, 0) + 1
    return {day: sums[day] / counts[day] for day in sums}


def daily_sum(
    observations: Iterable[HourlyWeatherObservation],
    *,
    metric: WeatherMetric,
    dates: AbstractSet[date] | None = None,
    local_timezone: tzinfo | None = None,
) -> dict[date, float]:
    totals: dict[date, float] = {}
    for observation in observations:
        if observation.metric != metric:
            continue
        day = _bucket_date(observation, local_timezone=local_timezone)
        if dates is not None and day not in dates:
            continue
        totals[day] = totals.get(day, 0.0) + observation.value_numeric
    return totals


def latest_observation(
    observations: Iterable[HourlyWeatherObservation], *, metric: WeatherMetric, at: datetime
) -> HourlyWeatherObservation | None:
    """The most recent `metric` reading at or before `at` -- used for
    "current conditions" (Phase 16), never a future-dated reading (this
    product never fetches or shows forecast data -- Phase 17)."""

    candidates = [
        observation
        for observation in observations
        if observation.metric == metric and observation.observed_at <= at
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda observation: observation.observed_at)


def describe_current_conditions(
    *,
    temperature_band: TemperatureBand | None,
    cloud_cover_band: CloudCoverBand | None,
    precipitation_state: PrecipitationState | None,
) -> str | None:
    """Composes a short, restrained phrase such as "Cool, overcast" or
    "Typical temperatures, light snow" for Today's summary line (Phase 16's
    "Cool, overcast morning" example). Deliberately never includes a
    "morning"/"afternoon"/"evening" time-of-day word: producing one would
    require a civil/local-time concept this product's temporal-semantics
    discipline has deliberately never introduced anywhere (see
    docs/environmental-context-foundation-v1-contract.md "Solar temporal
    semantics acceptance closure") -- a caller that already knows the
    viewer's local hour (the frontend, via the viewer's own device clock)
    may prepend a time-of-day word itself; this function never guesses one
    from coordinates. Returns `None` only when there is nothing at all to
    say (no temperature band and no sky/precipitation descriptor)."""

    words: list[str] = []
    if temperature_band == "cooler_than_typical":
        words.append("Cool")
    elif temperature_band == "warmer_than_typical":
        words.append("Warm")
    elif temperature_band == "typical":
        words.append("Typical temperatures")
    # `temperature_band is None` (insufficient baseline): say nothing
    # qualitative about temperature -- never an absolute "cold"/"warm"
    # claim without a Place-relative basis (Phase 7).

    descriptor: str | None = None
    if precipitation_state == "snow":
        descriptor = "snow"
    elif precipitation_state == "rain":
        descriptor = "rain"
    elif cloud_cover_band == "overcast":
        descriptor = "overcast"
    elif cloud_cover_band == "partly_cloudy":
        descriptor = "partly cloudy"
    elif cloud_cover_band == "clear":
        descriptor = "clear"
    if descriptor is not None:
        words.append(descriptor)

    if not words:
        return None
    return ", ".join(words)


__all__ = [
    "MIN_HOURLY_RECORDS_FOR_USABLE_ENVIRONMENTAL_DAY",
    "MIN_DAYS_FOR_TEMPERATURE_BASELINE",
    "WET_DAY_PRECIPITATION_THRESHOLD_MM",
    "SNOW_DAY_SNOWFALL_THRESHOLD_CM",
    "MOSTLY_CLEAR_MAX_CLOUD_COVER_PERCENT",
    "OVERCAST_MIN_CLOUD_COVER_PERCENT",
    "TemperatureBand",
    "TemperatureBaselineStatus",
    "PrecipitationBand",
    "PrecipitationState",
    "CloudCoverBand",
    "TemperatureBaseline",
    "compute_temperature_baseline",
    "classify_temperature_day",
    "classify_precipitation_day",
    "classify_precipitation_state",
    "classify_cloud_cover",
    "daily_hour_counts",
    "usable_environmental_dates",
    "daily_mean",
    "daily_sum",
    "latest_observation",
    "describe_current_conditions",
]
