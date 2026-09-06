"""Environmental Context x Place Story & Habitat Change Composition v1:
pure-module tests for `mockingbird.analytics.environmental_period_comparison`.
No database, no repository -- see `tests/test_place_feature.py`/
`tests/test_place_story_repository.py` for the composed API-level proofs."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from mockingbird.analytics.environmental_period_comparison import (
    MIN_USABLE_DAYS_PER_PERIOD,
    compute_environmental_period_comparison,
    summarize_environmental_period_comparison,
)
from mockingbird.environment.condition_bands import TemperatureBaseline

PRE_START = date(2026, 5, 1)
POST_END = date(2026, 5, 15)
WINDOW_DAYS = 7


def _dates(start: date, count: int) -> set[date]:
    return {start + timedelta(days=offset) for offset in range(count)}


PRE_DATES = _dates(PRE_START, WINDOW_DAYS)
POST_DATES = _dates(PRE_START + timedelta(days=WINDOW_DAYS), WINDOW_DAYS)

ESTABLISHED_BASELINE = TemperatureBaseline(
    status="established", lower_tertile_c=10.0, upper_tertile_c=20.0, sample_day_count=30
)
INSUFFICIENT_BASELINE = TemperatureBaseline(
    status="insufficient_baseline", lower_tertile_c=None, upper_tertile_c=None, sample_day_count=3
)


def _flat_means(period_dates: set[date], value_c: float) -> dict[date, float]:
    return {day: value_c for day in period_dates}


def _flat_precipitation(period_dates: set[date], total_mm: float) -> dict[date, float]:
    return {day: total_mm for day in period_dates}


class TestMeaningfulTemperatureDifference:
    def test_notably_cooler_after(self):
        daily_means = {**_flat_means(PRE_DATES, 15.0), **_flat_means(POST_DATES, 5.0)}
        result = compute_environmental_period_comparison(
            pre_dates=PRE_DATES,
            post_dates=POST_DATES,
            temperature_baseline=ESTABLISHED_BASELINE,
            daily_mean_temperatures_c=daily_means,
            daily_total_precipitation_mm={},
        )
        assert result.status == "comparable"
        assert result.temperature_note == "The after period was notably cooler."
        assert result.pre_mean_temperature_c == 15.0
        assert result.post_mean_temperature_c == 5.0

    def test_notably_warmer_after(self):
        daily_means = {**_flat_means(PRE_DATES, 15.0), **_flat_means(POST_DATES, 25.0)}
        result = compute_environmental_period_comparison(
            pre_dates=PRE_DATES,
            post_dates=POST_DATES,
            temperature_baseline=ESTABLISHED_BASELINE,
            daily_mean_temperatures_c=daily_means,
            daily_total_precipitation_mm={},
        )
        assert result.temperature_note == "The after period was notably warmer."

    def test_both_periods_typical_produces_no_temperature_note(self):
        daily_means = {**_flat_means(PRE_DATES, 14.0), **_flat_means(POST_DATES, 16.0)}
        result = compute_environmental_period_comparison(
            pre_dates=PRE_DATES,
            post_dates=POST_DATES,
            temperature_baseline=ESTABLISHED_BASELINE,
            daily_mean_temperatures_c=daily_means,
            daily_total_precipitation_mm={},
        )
        assert result.status == "comparable"
        assert result.temperature_note is None

    def test_both_periods_cooler_than_typical_is_not_a_difference(self):
        # Both periods land in the *same* band (cooler_than_typical) --
        # conservative abstention, even though this is a real-world case a
        # human glancing at raw numbers might call "different."
        daily_means = {**_flat_means(PRE_DATES, 4.0), **_flat_means(POST_DATES, 2.0)}
        result = compute_environmental_period_comparison(
            pre_dates=PRE_DATES,
            post_dates=POST_DATES,
            temperature_baseline=ESTABLISHED_BASELINE,
            daily_mean_temperatures_c=daily_means,
            daily_total_precipitation_mm={},
        )
        assert result.temperature_note is None

    def test_insufficient_baseline_abstains_on_temperature_only(self):
        daily_means = {**_flat_means(PRE_DATES, 15.0), **_flat_means(POST_DATES, 5.0)}
        daily_precip = {**_flat_precipitation(PRE_DATES, 0.0), **_flat_precipitation(POST_DATES, 5.0)}
        result = compute_environmental_period_comparison(
            pre_dates=PRE_DATES,
            post_dates=POST_DATES,
            temperature_baseline=INSUFFICIENT_BASELINE,
            daily_mean_temperatures_c=daily_means,
            daily_total_precipitation_mm=daily_precip,
        )
        # Temperature never claims a *band* without a Place-relative basis --
        # but the raw measured means are still honest, legitimate data (the
        # day-count floor was cleared; only the baseline was thin), so they
        # remain populated as provenance even though no note is produced.
        # Precipitation (a fixed physical threshold, no baseline needed) is
        # unaffected: neither metric blocks or degrades the other.
        assert result.temperature_note is None
        assert result.pre_mean_temperature_c == 15.0
        assert result.post_mean_temperature_c == 5.0
        assert result.status == "comparable"
        assert result.precipitation_note == "Rainfall was higher during the after period."


class TestMeaningfulPrecipitationDifference:
    def test_higher_rainfall_after(self):
        daily_precip = {**_flat_precipitation(PRE_DATES, 0.0), **_flat_precipitation(POST_DATES, 5.0)}
        result = compute_environmental_period_comparison(
            pre_dates=PRE_DATES,
            post_dates=POST_DATES,
            temperature_baseline=ESTABLISHED_BASELINE,
            daily_mean_temperatures_c={},
            daily_total_precipitation_mm=daily_precip,
        )
        assert result.precipitation_note == "Rainfall was higher during the after period."

    def test_lower_rainfall_after(self):
        daily_precip = {**_flat_precipitation(PRE_DATES, 5.0), **_flat_precipitation(POST_DATES, 0.0)}
        result = compute_environmental_period_comparison(
            pre_dates=PRE_DATES,
            post_dates=POST_DATES,
            temperature_baseline=ESTABLISHED_BASELINE,
            daily_mean_temperatures_c={},
            daily_total_precipitation_mm=daily_precip,
        )
        assert result.precipitation_note == "Rainfall was lower during the after period."

    def test_both_periods_mostly_dry_produces_no_precipitation_note(self):
        daily_precip = {**_flat_precipitation(PRE_DATES, 0.0), **_flat_precipitation(POST_DATES, 0.0)}
        result = compute_environmental_period_comparison(
            pre_dates=PRE_DATES,
            post_dates=POST_DATES,
            temperature_baseline=ESTABLISHED_BASELINE,
            daily_mean_temperatures_c={},
            daily_total_precipitation_mm=daily_precip,
        )
        assert result.precipitation_note is None

    def test_exact_half_wet_days_is_not_a_majority(self):
        # `pre` is entirely dry (0 of 7 wet -- a clear dry majority). `post`
        # deliberately caches only 6 of its 7 dates (still clearing the
        # 5-day floor), split exactly 3 wet / 3 dry -- an exact tie must
        # count as "not predominantly wet," i.e. the same dry majority as
        # `pre`, producing no note at all.
        pre = _flat_precipitation(PRE_DATES, 0.0)
        post_subset = sorted(POST_DATES)[:6]
        post = {day: (5.0 if index < 3 else 0.0) for index, day in enumerate(post_subset)}
        result = compute_environmental_period_comparison(
            pre_dates=PRE_DATES,
            post_dates=POST_DATES,
            temperature_baseline=ESTABLISHED_BASELINE,
            daily_mean_temperatures_c={},
            daily_total_precipitation_mm={**pre, **post},
        )
        assert result.post_usable_precipitation_days == 6
        assert result.precipitation_note is None


class TestCoverageFloor:
    def test_insufficient_coverage_when_neither_metric_has_enough_days(self):
        thin_pre = set(list(PRE_DATES)[: MIN_USABLE_DAYS_PER_PERIOD - 1])
        thin_post = set(list(POST_DATES)[: MIN_USABLE_DAYS_PER_PERIOD - 1])
        daily_means = {**_flat_means(thin_pre, 5.0), **_flat_means(thin_post, 25.0)}
        result = compute_environmental_period_comparison(
            pre_dates=PRE_DATES,
            post_dates=POST_DATES,
            temperature_baseline=ESTABLISHED_BASELINE,
            daily_mean_temperatures_c=daily_means,
            daily_total_precipitation_mm={},
        )
        assert result.status == "insufficient_coverage"
        assert result.temperature_note is None
        assert result.pre_mean_temperature_c is None

    def test_comparable_when_only_one_metric_clears_the_floor(self):
        # Temperature is thin (below floor) but precipitation has full
        # coverage -- overall status is still "comparable": one metric
        # succeeding is enough, per "neither field blocks the other."
        thin_pre = set(list(PRE_DATES)[: MIN_USABLE_DAYS_PER_PERIOD - 1])
        daily_means = _flat_means(thin_pre, 5.0)
        daily_precip = {**_flat_precipitation(PRE_DATES, 0.0), **_flat_precipitation(POST_DATES, 5.0)}
        result = compute_environmental_period_comparison(
            pre_dates=PRE_DATES,
            post_dates=POST_DATES,
            temperature_baseline=ESTABLISHED_BASELINE,
            daily_mean_temperatures_c=daily_means,
            daily_total_precipitation_mm=daily_precip,
        )
        assert result.status == "comparable"
        assert result.pre_mean_temperature_c is None
        assert result.precipitation_note == "Rainfall was higher during the after period."

    def test_exactly_at_the_floor_is_sufficient(self):
        pre = set(list(PRE_DATES)[:MIN_USABLE_DAYS_PER_PERIOD])
        post = set(list(POST_DATES)[:MIN_USABLE_DAYS_PER_PERIOD])
        daily_means = {**_flat_means(pre, 5.0), **_flat_means(post, 25.0)}
        result = compute_environmental_period_comparison(
            pre_dates=PRE_DATES,
            post_dates=POST_DATES,
            temperature_baseline=ESTABLISHED_BASELINE,
            daily_mean_temperatures_c=daily_means,
            daily_total_precipitation_mm={},
        )
        assert result.status == "comparable"
        assert result.temperature_note == "The after period was notably warmer."


class TestSummarize:
    def test_include_neutral_true_states_similar_when_nothing_differs(self):
        daily_means = {**_flat_means(PRE_DATES, 14.0), **_flat_means(POST_DATES, 16.0)}
        result = compute_environmental_period_comparison(
            pre_dates=PRE_DATES,
            post_dates=POST_DATES,
            temperature_baseline=ESTABLISHED_BASELINE,
            daily_mean_temperatures_c=daily_means,
            daily_total_precipitation_mm={},
        )
        assert (
            summarize_environmental_period_comparison(result, include_neutral=True)
            == "Conditions were broadly similar across the two periods."
        )

    def test_include_neutral_false_stays_silent_when_nothing_differs(self):
        daily_means = {**_flat_means(PRE_DATES, 14.0), **_flat_means(POST_DATES, 16.0)}
        result = compute_environmental_period_comparison(
            pre_dates=PRE_DATES,
            post_dates=POST_DATES,
            temperature_baseline=ESTABLISHED_BASELINE,
            daily_mean_temperatures_c=daily_means,
            daily_total_precipitation_mm={},
        )
        assert summarize_environmental_period_comparison(result, include_neutral=False) is None

    def test_insufficient_coverage_is_silent_regardless_of_include_neutral(self):
        daily_means = _flat_means(set(list(PRE_DATES)[:1]), 5.0)
        result = compute_environmental_period_comparison(
            pre_dates=PRE_DATES,
            post_dates=POST_DATES,
            temperature_baseline=ESTABLISHED_BASELINE,
            daily_mean_temperatures_c=daily_means,
            daily_total_precipitation_mm={},
        )
        assert result.status == "insufficient_coverage"
        assert summarize_environmental_period_comparison(result, include_neutral=True) is None
        assert summarize_environmental_period_comparison(result, include_neutral=False) is None

    def test_both_metrics_differing_join_into_one_compact_sentence(self):
        daily_means = {**_flat_means(PRE_DATES, 15.0), **_flat_means(POST_DATES, 5.0)}
        daily_precip = {**_flat_precipitation(PRE_DATES, 0.0), **_flat_precipitation(POST_DATES, 5.0)}
        result = compute_environmental_period_comparison(
            pre_dates=PRE_DATES,
            post_dates=POST_DATES,
            temperature_baseline=ESTABLISHED_BASELINE,
            daily_mean_temperatures_c=daily_means,
            daily_total_precipitation_mm=daily_precip,
        )
        summary = summarize_environmental_period_comparison(result, include_neutral=True)
        assert summary == (
            "The after period was notably cooler. Rainfall was higher during the after period."
        )

    @pytest.mark.parametrize(
        "forbidden",
        ["caused", "led to", "resulted in", "because of", "drove", "due to", "may explain"],
    )
    def test_no_producible_sentence_ever_uses_causal_language(self, forbidden):
        scenarios = [
            ({**_flat_means(PRE_DATES, 15.0), **_flat_means(POST_DATES, 5.0)}, {}),
            ({**_flat_means(PRE_DATES, 15.0), **_flat_means(POST_DATES, 25.0)}, {}),
            ({}, {**_flat_precipitation(PRE_DATES, 0.0), **_flat_precipitation(POST_DATES, 5.0)}),
            ({}, {**_flat_precipitation(PRE_DATES, 5.0), **_flat_precipitation(POST_DATES, 0.0)}),
            ({**_flat_means(PRE_DATES, 14.0), **_flat_means(POST_DATES, 16.0)}, {}),
        ]
        for daily_means, daily_precip in scenarios:
            result = compute_environmental_period_comparison(
                pre_dates=PRE_DATES,
                post_dates=POST_DATES,
                temperature_baseline=ESTABLISHED_BASELINE,
                daily_mean_temperatures_c=daily_means,
                daily_total_precipitation_mm=daily_precip,
            )
            for include_neutral in (True, False):
                summary = summarize_environmental_period_comparison(result, include_neutral=include_neutral)
                if summary:
                    assert forbidden not in summary.lower()


class TestDeterminism:
    def test_same_inputs_produce_identical_output(self):
        daily_means = {**_flat_means(PRE_DATES, 15.0), **_flat_means(POST_DATES, 5.0)}
        first = compute_environmental_period_comparison(
            pre_dates=PRE_DATES,
            post_dates=POST_DATES,
            temperature_baseline=ESTABLISHED_BASELINE,
            daily_mean_temperatures_c=daily_means,
            daily_total_precipitation_mm={},
        )
        second = compute_environmental_period_comparison(
            pre_dates=PRE_DATES,
            post_dates=POST_DATES,
            temperature_baseline=ESTABLISHED_BASELINE,
            daily_mean_temperatures_c=daily_means,
            daily_total_precipitation_mm={},
        )
        assert first == second
