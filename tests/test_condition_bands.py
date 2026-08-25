"""Pure computation tests for mockingbird.environment.condition_bands.

No repository, no database, no network -- matches the existing
test_habitat_association.py precedent for a pure sibling module.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta, timezone

import pytest

from mockingbird.environment.condition_bands import (
    MIN_DAYS_FOR_TEMPERATURE_BASELINE,
    MIN_HOURLY_RECORDS_FOR_USABLE_ENVIRONMENTAL_DAY,
    SNOW_DAY_SNOWFALL_THRESHOLD_CM,
    WET_DAY_PRECIPITATION_THRESHOLD_MM,
    classify_cloud_cover,
    classify_precipitation_day,
    classify_precipitation_state,
    classify_temperature_day,
    compute_temperature_baseline,
    daily_hour_counts,
    daily_mean,
    daily_sum,
    describe_current_conditions,
    latest_observation,
    usable_environmental_dates,
)
from mockingbird.environment.weather_provider import HourlyWeatherObservation

BASE = date(2026, 1, 1)


def _obs(day: date, hour: int, metric: str, value: float, unit: str = "") -> HourlyWeatherObservation:
    return HourlyWeatherObservation(
        metric=metric,
        value_numeric=value,
        unit=unit,
        observed_at=datetime(day.year, day.month, day.day, hour, tzinfo=UTC),
        for_date=day,
    )


def _full_day(day: date, metric: str, value: float) -> list[HourlyWeatherObservation]:
    return [_obs(day, hour, metric, value) for hour in range(24)]


# ---------------------------------------------------------------------------
# Temperature baseline / banding
# ---------------------------------------------------------------------------


def test_baseline_insufficient_below_minimum_day_count() -> None:
    means = {BASE + timedelta(days=i): 15.0 + i for i in range(MIN_DAYS_FOR_TEMPERATURE_BASELINE - 1)}
    baseline = compute_temperature_baseline(means)
    assert baseline.status == "insufficient_baseline"
    assert baseline.lower_tertile_c is None
    assert baseline.upper_tertile_c is None
    assert baseline.sample_day_count == MIN_DAYS_FOR_TEMPERATURE_BASELINE - 1


def test_baseline_established_at_minimum_day_count() -> None:
    means = {BASE + timedelta(days=i): float(i) for i in range(MIN_DAYS_FOR_TEMPERATURE_BASELINE)}
    baseline = compute_temperature_baseline(means)
    assert baseline.status == "established"
    assert baseline.lower_tertile_c is not None
    assert baseline.upper_tertile_c is not None
    assert baseline.lower_tertile_c < baseline.upper_tertile_c


def test_classify_temperature_day_is_none_when_baseline_insufficient() -> None:
    baseline = compute_temperature_baseline({BASE: 10.0})
    assert classify_temperature_day(10.0, baseline) is None


def test_classify_temperature_day_bands_relative_to_place_own_distribution() -> None:
    # 30 days evenly spread 0..29 degC -- a clean, evenly-spaced
    # distribution so tertile boundaries are unambiguous.
    means = {BASE + timedelta(days=i): float(i) for i in range(30)}
    baseline = compute_temperature_baseline(means)
    assert classify_temperature_day(0.0, baseline) == "cooler_than_typical"
    assert classify_temperature_day(29.0, baseline) == "warmer_than_typical"
    assert classify_temperature_day(14.5, baseline) == "typical"


def test_temperature_band_is_place_relative_not_absolute() -> None:
    """The governing brief's own anti-example: a 65degF (~18.3degC) morning
    must not be universally "cold" -- it depends entirely on this Place's
    own recent distribution."""

    cold_place_means = {BASE + timedelta(days=i): -10.0 + i * 0.1 for i in range(30)}  # around -10..-7
    warm_place_means = {BASE + timedelta(days=i): 25.0 + i * 0.1 for i in range(30)}  # around 25..28
    cold_place_baseline = compute_temperature_baseline(cold_place_means)
    warm_place_baseline = compute_temperature_baseline(warm_place_means)

    # 18.3 degC is warmer than everything in the cold place's distribution...
    assert classify_temperature_day(18.3, cold_place_baseline) == "warmer_than_typical"
    # ...but cooler than everything in the warm place's distribution.
    assert classify_temperature_day(18.3, warm_place_baseline) == "cooler_than_typical"


# ---------------------------------------------------------------------------
# Precipitation
# ---------------------------------------------------------------------------


def test_classify_precipitation_day_threshold() -> None:
    assert classify_precipitation_day(0.0) == "dry_day"
    assert classify_precipitation_day(WET_DAY_PRECIPITATION_THRESHOLD_MM - 0.01) == "dry_day"
    assert classify_precipitation_day(WET_DAY_PRECIPITATION_THRESHOLD_MM) == "wet_day"
    assert classify_precipitation_day(10.0) == "wet_day"


def test_classify_precipitation_state_dry_rain_snow() -> None:
    assert classify_precipitation_state(0.0, 0.0) == "dry"
    assert classify_precipitation_state(2.0, 0.0) == "rain"
    assert classify_precipitation_state(2.0, SNOW_DAY_SNOWFALL_THRESHOLD_CM) == "snow"
    assert classify_precipitation_state(0.0, SNOW_DAY_SNOWFALL_THRESHOLD_CM) == "snow"


def test_snow_takes_priority_over_rain_when_both_present() -> None:
    # A mixed-precipitation hour with both liquid and snow water-equivalent
    # is described as snow, not rain -- see the module's own docstring for
    # why the association axis stays a simpler binary while this
    # descriptive text can be more specific.
    assert classify_precipitation_state(5.0, 1.0) == "snow"


# ---------------------------------------------------------------------------
# Cloud cover
# ---------------------------------------------------------------------------


def test_classify_cloud_cover_bands() -> None:
    assert classify_cloud_cover(0.0) == "clear"
    assert classify_cloud_cover(30.0) == "clear"
    assert classify_cloud_cover(50.0) == "partly_cloudy"
    assert classify_cloud_cover(70.0) == "overcast"
    assert classify_cloud_cover(100.0) == "overcast"


# ---------------------------------------------------------------------------
# Aggregation: daily_hour_counts / usable_environmental_dates / daily_mean /
# daily_sum
# ---------------------------------------------------------------------------


def test_daily_hour_counts_counts_only_the_requested_metric() -> None:
    observations = _full_day(BASE, "air_temperature", 10.0) + _full_day(BASE, "cloud_cover", 50.0)
    counts = daily_hour_counts(observations, metric="air_temperature")
    assert counts == {BASE: 24}


def test_usable_environmental_dates_requires_the_completeness_floor() -> None:
    counts = {
        BASE: MIN_HOURLY_RECORDS_FOR_USABLE_ENVIRONMENTAL_DAY,
        BASE + timedelta(days=1): MIN_HOURLY_RECORDS_FOR_USABLE_ENVIRONMENTAL_DAY - 1,
    }
    assert usable_environmental_dates(counts) == frozenset({BASE})


def test_daily_mean_ignores_dates_outside_the_given_set() -> None:
    observations = _full_day(BASE, "air_temperature", 10.0) + _full_day(
        BASE + timedelta(days=1), "air_temperature", 20.0
    )
    means = daily_mean(observations, metric="air_temperature", dates=frozenset({BASE}))
    assert means == {BASE: 10.0}


def test_daily_mean_a_partial_day_is_excluded_when_dates_restricts_to_usable() -> None:
    partial = [_obs(BASE, hour, "air_temperature", 5.0) for hour in range(3)]  # only 3 of 24 hours
    hour_counts = daily_hour_counts(partial, metric="air_temperature")
    usable = usable_environmental_dates(hour_counts)
    assert usable == frozenset()  # below the completeness floor
    means = daily_mean(partial, metric="air_temperature", dates=usable)
    assert means == {}  # never a skewed 3-hour "daily" mean


def test_daily_sum_accumulates_across_hours() -> None:
    observations = [_obs(BASE, hour, "precipitation_amount", 0.5) for hour in range(24)]
    sums = daily_sum(observations, metric="precipitation_amount")
    assert sums[BASE] == pytest.approx(12.0)


def test_local_timezone_bucketing_shifts_a_late_utc_hour_to_the_next_local_day() -> None:
    """A Place west of UTC (e.g. US Pacific, UTC-8) sees a UTC 22:00 hour as
    the *next* civil day locally is wrong; a Place *east* of UTC sees an
    early UTC hour fall on the *previous* local day. Use UTC+9 (JST) so a
    UTC 20:00 hour (for_date=BASE) becomes 05:00 the next *local* day --
    proving bucketing genuinely follows the given timezone, not always UTC.
    """

    jst = timezone(timedelta(hours=9))
    observation = _obs(BASE, 20, "air_temperature", 15.0)  # UTC 2026-01-01 20:00
    utc_counts = daily_hour_counts([observation], metric="air_temperature")
    local_counts = daily_hour_counts([observation], metric="air_temperature", local_timezone=jst)
    assert utc_counts == {BASE: 1}
    assert local_counts == {BASE + timedelta(days=1): 1}  # 2026-01-01 20:00 UTC == 2026-01-02 05:00 JST


# ---------------------------------------------------------------------------
# latest_observation
# ---------------------------------------------------------------------------


def test_latest_observation_picks_the_most_recent_at_or_before_instant() -> None:
    observations = [_obs(BASE, hour, "air_temperature", float(hour)) for hour in range(24)]
    result = latest_observation(observations, metric="air_temperature", at=datetime(2026, 1, 1, 10, 30, tzinfo=UTC))
    assert result is not None
    assert result.observed_at == datetime(2026, 1, 1, 10, tzinfo=UTC)
    assert result.value_numeric == 10.0


def test_latest_observation_never_returns_a_future_reading() -> None:
    # Phase 17: this product never surfaces forecast data. Even if a future
    # row were somehow present in the input, `at` must bound the result.
    observations = [
        _obs(BASE, 5, "air_temperature", 5.0),
        _obs(BASE, 23, "air_temperature", 99.0),
    ]
    result = latest_observation(observations, metric="air_temperature", at=datetime(2026, 1, 1, 6, 0, tzinfo=UTC))
    assert result is not None
    assert result.value_numeric == 5.0


def test_latest_observation_none_when_nothing_at_or_before_instant() -> None:
    observations = [_obs(BASE, 12, "air_temperature", 10.0)]
    result = latest_observation(observations, metric="air_temperature", at=datetime(2026, 1, 1, 6, 0, tzinfo=UTC))
    assert result is None


# ---------------------------------------------------------------------------
# describe_current_conditions
# ---------------------------------------------------------------------------


def test_describe_current_conditions_combines_temperature_and_sky() -> None:
    text = describe_current_conditions(
        temperature_band="cooler_than_typical", cloud_cover_band="overcast", precipitation_state="dry"
    )
    assert text == "Cool, overcast"


def test_describe_current_conditions_precipitation_overrides_cloud_descriptor() -> None:
    text = describe_current_conditions(
        temperature_band="warmer_than_typical", cloud_cover_band="clear", precipitation_state="rain"
    )
    assert text == "Warm, rain"


def test_describe_current_conditions_omits_temperature_word_when_baseline_insufficient() -> None:
    text = describe_current_conditions(temperature_band=None, cloud_cover_band="clear", precipitation_state="dry")
    assert text == "clear"
    assert "cold" not in text.lower() and "warm" not in text.lower() and "cool" not in text.lower()


def test_describe_current_conditions_never_includes_a_time_of_day_word() -> None:
    text = describe_current_conditions(
        temperature_band="cooler_than_typical", cloud_cover_band="overcast", precipitation_state="dry"
    )
    for word in ("morning", "afternoon", "evening", "night"):
        assert word not in (text or "").lower()


def test_describe_current_conditions_none_when_nothing_to_say() -> None:
    assert describe_current_conditions(temperature_band=None, cloud_cover_band=None, precipitation_state=None) is None
