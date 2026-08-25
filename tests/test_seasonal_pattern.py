"""Pure computation tests for mockingbird.analytics.seasonal_pattern.

No repository, no database -- matches the established pure-module test
convention in tests/test_historical_baseline.py (itself following
test_place_activity_report.py's own precedent for this package).
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Iterable

import pytest

from mockingbird.analytics.place_activity_report import TaxonFact, VisitFact
from mockingbird.analytics.seasonal_pattern import (
    SEASONAL_MIN_DISTINCT_USABLE_MONTHS,
    SEASONAL_MIN_PRESENCE_DAYS_FOR_PATTERN,
    SEASONAL_MIN_PRESENCE_DAYS_IN_FLAGGED_MONTH,
    SEASONAL_MIN_USABLE_DAYS_IN_MONTH,
    SEASONAL_MONTH_MIN_RATE_MULTIPLE,
    compute_seasonal_patterns,
    presence_dates_by_taxon,
)

# One TaxonFact per test role, reused consistently for that role across every
# test that needs it (mirrors test_historical_baseline.py's own roster).
NORTHERN_CARDINAL = TaxonFact("northern_cardinal", "Northern Cardinal", "bird", True)
HOUSE_FINCH = TaxonFact("house_finch", "House Finch", "bird", True)  # always zero presence
SONG_SPARROW = TaxonFact("song_sparrow", "Song Sparrow", "bird", True)  # always sparse/insufficient
BLUE_JAY = TaxonFact("blue_jay", "Blue Jay", "bird", True)  # always "just enough" presence
TUFTED_TITMOUSE = TaxonFact("tufted_titmouse", "Tufted Titmouse", "bird", True)  # always established_pattern
CAROLINA_WREN = TaxonFact("carolina_wren", "Carolina Wren", "bird", True)  # always no_pattern_detected
AMERICAN_ROBIN = TaxonFact("american_robin", "American Robin", "bird", True)  # always the lucky-day case
DARK_EYED_JUNCO = TaxonFact("dark_eyed_junco", "Dark-eyed Junco", "bird", True)  # always the low-usable-day case

YEAR = 2026

# The one calendar month TUFTED_TITMOUSE's presence is concentrated in,
# wherever `_established_pattern_dates` is used below.
ESTABLISHED_PATTERN_FLAGGED_MONTH = 6  # June


def _visit(visit_id: str, *, at: datetime, confirmed: TaxonFact | None = None) -> VisitFact:
    return VisitFact(
        visit_id=visit_id,
        zone_id=None,
        zone_name=None,
        activity_started_at=at,
        resolution="reviewed",  # type: ignore[arg-type]
        confirmed_taxon=confirmed,
    )


def _visits_for_dates(prefix: str, taxon: TaxonFact, dates: Iterable[date]) -> list[VisitFact]:
    """One reviewed Visit per distinct given calendar date, confirmed to
    `taxon`, at local noon UTC so `local_timezone=UTC` always lands on
    exactly that date."""

    return [
        _visit(f"{prefix}-{i}", at=datetime(d.year, d.month, d.day, 12, tzinfo=UTC), confirmed=taxon)
        for i, d in enumerate(sorted(set(dates)))
    ]


def _usable_dates_for_months(months: Iterable[int], *, days_per_month: int, year: int = YEAR) -> set[date]:
    """`days_per_month` usable dates (that month's 1st through Nth) for each
    given calendar month number."""

    return {date(year, month, day) for month in months for day in range(1, 1 + days_per_month)}


def _mature_usable_dates() -> set[date]:
    """All 12 months with 10 usable days apiece -- comfortably clears the
    Place-wide maturity gate (12 >= SEASONAL_MIN_DISTINCT_USABLE_MONTHS) and
    gives every month a clean, round denominator for rate arithmetic."""

    return _usable_dates_for_months(range(1, 13), days_per_month=10)


def _established_pattern_dates() -> set[date]:
    """ESTABLISHED_PATTERN_FLAGGED_MONTH (June) gets 8 presence days; every
    other month gets exactly 1. Against `_mature_usable_dates`'s 10
    usable-days-per-month, June's rate (0.8) is comfortably >=
    SEASONAL_MONTH_MIN_RATE_MULTIPLE times the taxon's own average
    qualifying-month rate, and June independently clears the
    SEASONAL_MIN_PRESENCE_DAYS_IN_FLAGGED_MONTH floor too -- while every
    other month's single day never can (1 < 2)."""

    dates = {date(YEAR, ESTABLISHED_PATTERN_FLAGGED_MONTH, day) for day in range(1, 9)}  # 8 days
    dates |= {date(YEAR, month, 1) for month in range(1, 13) if month != ESTABLISHED_PATTERN_FLAGGED_MONTH}
    return dates


def _even_spread_dates() -> set[date]:
    """Exactly SEASONAL_MIN_PRESENCE_DAYS_IN_FLAGGED_MONTH presence days in
    *every* one of the 12 qualifying months -- every month's rate is
    identical, so none can ever be >= SEASONAL_MONTH_MIN_RATE_MULTIPLE times
    the (identical) average, even though every month individually clears the
    flagged-month presence-day floor."""

    return {
        date(YEAR, month, day)
        for month in range(1, 13)
        for day in range(1, 1 + SEASONAL_MIN_PRESENCE_DAYS_IN_FLAGGED_MONTH)
    }


class TestPlaceWideMaturityGate:
    """A Place-wide gate, decided once from `usable_dates` alone and applied
    uniformly to every taxon -- it must override even a taxon with abundant
    presence of its own."""

    def test_immature_place_overrides_a_well_evidenced_taxon(self) -> None:
        # Exactly one month short of the Place-wide floor: months
        # 1..(SEASONAL_MIN_DISTINCT_USABLE_MONTHS - 1), each with
        # SEASONAL_MIN_USABLE_DAYS_IN_MONTH usable days.
        usable_dates = _usable_dates_for_months(
            range(1, SEASONAL_MIN_DISTINCT_USABLE_MONTHS), days_per_month=SEASONAL_MIN_USABLE_DAYS_IN_MONTH
        )
        assert len(usable_dates) == (SEASONAL_MIN_DISTINCT_USABLE_MONTHS - 1) * SEASONAL_MIN_USABLE_DAYS_IN_MONTH

        # 20 presence days, all concentrated in a single month -- a taxon
        # that would be extremely well-evidenced by any taxon-level measure.
        well_evidenced_dates = {date(YEAR, 1, day) for day in range(1, 21)}
        visits = _visits_for_dates("cardinal", NORTHERN_CARDINAL, well_evidenced_dates)

        taxa = {"northern_cardinal": NORTHERN_CARDINAL, "house_finch": HOUSE_FINCH}
        results = compute_seasonal_patterns(
            visits, taxa=taxa, usable_dates=usable_dates, local_timezone=UTC, reference_month=1
        )

        for label in taxa:
            pattern = results[label]
            assert pattern.status == "insufficient_history"
            assert pattern.typical_months == ()
            assert pattern.current_month_is_typical is None


class TestTaxonLevelGate:
    """On top of a mature Place, each taxon additionally needs its own
    SEASONAL_MIN_PRESENCE_DAYS_FOR_PATTERN total presence days before a
    per-month pattern is attempted for it specifically."""

    def test_taxon_below_its_own_presence_floor_still_reads_insufficient(self) -> None:
        usable_dates = _mature_usable_dates()

        # One day short of the taxon-level floor.
        sparse_dates = {date(YEAR, 1, day) for day in range(1, SEASONAL_MIN_PRESENCE_DAYS_FOR_PATTERN)}
        assert len(sparse_dates) == SEASONAL_MIN_PRESENCE_DAYS_FOR_PATTERN - 1

        # Exactly at the floor, spread across three different months.
        adequate_dates = {date(YEAR, 1, 1), date(YEAR, 2, 1), date(YEAR, 3, 1)}
        assert len(adequate_dates) == SEASONAL_MIN_PRESENCE_DAYS_FOR_PATTERN

        visits = _visits_for_dates("sparse", SONG_SPARROW, sparse_dates) + _visits_for_dates(
            "adequate", BLUE_JAY, adequate_dates
        )
        taxa = {"song_sparrow": SONG_SPARROW, "blue_jay": BLUE_JAY}
        results = compute_seasonal_patterns(
            visits, taxa=taxa, usable_dates=usable_dates, local_timezone=UTC, reference_month=1
        )

        sparse_result = results["song_sparrow"]
        assert sparse_result.status == "insufficient_history"
        assert sparse_result.typical_months == ()
        assert sparse_result.current_month_is_typical is None

        # 1 presence day in each of 3 distinct qualifying months, none of
        # which can clear the flagged-month presence-day floor alone: a
        # real progression past this gate into "no_pattern_detected".
        adequate_result = results["blue_jay"]
        assert adequate_result.status != "insufficient_history"
        assert adequate_result.status == "no_pattern_detected"


class TestEstablishedPattern:
    def test_concentrated_month_is_flagged_as_established(self) -> None:
        usable_dates = _mature_usable_dates()
        presence_dates = _established_pattern_dates()
        assert len(presence_dates) == 8 + 11  # 8 June days + 1 day in each of the other 11 months

        visits = _visits_for_dates("titmouse", TUFTED_TITMOUSE, presence_dates)
        results = compute_seasonal_patterns(
            visits,
            taxa={"tufted_titmouse": TUFTED_TITMOUSE},
            usable_dates=usable_dates,
            local_timezone=UTC,
            reference_month=ESTABLISHED_PATTERN_FLAGGED_MONTH,
        )
        pattern = results["tufted_titmouse"]
        assert pattern.status == "established_pattern"
        assert pattern.typical_months == (ESTABLISHED_PATTERN_FLAGGED_MONTH,)


class TestNoPatternDetected:
    def test_evenly_spread_presence_has_no_standout_month(self) -> None:
        usable_dates = _mature_usable_dates()
        presence_dates = _even_spread_dates()

        visits = _visits_for_dates("wren", CAROLINA_WREN, presence_dates)
        results = compute_seasonal_patterns(
            visits,
            taxa={"carolina_wren": CAROLINA_WREN},
            usable_dates=usable_dates,
            local_timezone=UTC,
            reference_month=1,
        )
        pattern = results["carolina_wren"]
        assert pattern.status == "no_pattern_detected"
        assert pattern.typical_months == ()


class TestCurrentMonthIsTypical:
    def test_true_when_reference_month_is_typical_false_otherwise_none_elsewhere(self) -> None:
        usable_dates = _mature_usable_dates()
        established_dates = _established_pattern_dates()
        no_pattern_dates = _even_spread_dates()

        taxa = {
            "tufted_titmouse": TUFTED_TITMOUSE,
            "carolina_wren": CAROLINA_WREN,
            "house_finch": HOUSE_FINCH,  # zero presence anywhere -> insufficient_history
        }
        visits = _visits_for_dates("titmouse", TUFTED_TITMOUSE, established_dates) + _visits_for_dates(
            "wren", CAROLINA_WREN, no_pattern_dates
        )

        typical_month_results = compute_seasonal_patterns(
            visits,
            taxa=taxa,
            usable_dates=usable_dates,
            local_timezone=UTC,
            reference_month=ESTABLISHED_PATTERN_FLAGGED_MONTH,
        )
        assert typical_month_results["tufted_titmouse"].status == "established_pattern"
        assert typical_month_results["tufted_titmouse"].current_month_is_typical is True
        assert typical_month_results["carolina_wren"].status == "no_pattern_detected"
        assert typical_month_results["carolina_wren"].current_month_is_typical is None
        assert typical_month_results["house_finch"].status == "insufficient_history"
        assert typical_month_results["house_finch"].current_month_is_typical is None

        non_typical_month_results = compute_seasonal_patterns(
            visits, taxa=taxa, usable_dates=usable_dates, local_timezone=UTC, reference_month=1
        )
        assert non_typical_month_results["tufted_titmouse"].current_month_is_typical is False
        assert non_typical_month_results["carolina_wren"].current_month_is_typical is None
        assert non_typical_month_results["house_finch"].current_month_is_typical is None


class TestMonthsShape:
    def test_months_always_has_12_entries_in_order_with_correct_counts(self) -> None:
        usable_dates = _mature_usable_dates()
        established_dates = _established_pattern_dates()

        visits = _visits_for_dates("titmouse", TUFTED_TITMOUSE, established_dates)
        results = compute_seasonal_patterns(
            visits,
            taxa={"tufted_titmouse": TUFTED_TITMOUSE, "house_finch": HOUSE_FINCH},
            usable_dates=usable_dates,
            local_timezone=UTC,
            reference_month=1,
        )

        for label in ("tufted_titmouse", "house_finch"):
            months = results[label].months
            assert len(months) == 12
            assert [m.month for m in months] == list(range(1, 13))
            assert all(m.usable_day_count == 10 for m in months)  # every month has 10 usable days here

        established_months = results["tufted_titmouse"].months
        january, june = established_months[0], established_months[5]
        assert (january.month, january.usable_day_count, january.presence_day_count) == (1, 10, 1)
        assert (june.month, june.usable_day_count, june.presence_day_count) == (6, 10, 8)

        # house_finch (zero presence anywhere, insufficient_history) still
        # gets an honest all-zero months breakdown, not an omitted entry.
        assert results["house_finch"].status == "insufficient_history"
        assert all(m.presence_day_count == 0 for m in results["house_finch"].months)


class TestLuckySingleDayFloor:
    def test_a_single_presence_day_never_alone_triggers_established_pattern(self) -> None:
        usable_dates = _mature_usable_dates()  # 10 usable days/month everywhere

        # Exactly SEASONAL_MIN_PRESENCE_DAYS_FOR_PATTERN total presence
        # days, as a single day each in 3 different months.
        lucky_months = [3, 7, 9]
        presence_dates = {date(YEAR, month, 1) for month in lucky_months}
        assert len(presence_dates) == SEASONAL_MIN_PRESENCE_DAYS_FOR_PATTERN

        visits = _visits_for_dates("robin", AMERICAN_ROBIN, presence_dates)
        results = compute_seasonal_patterns(
            visits,
            taxa={"american_robin": AMERICAN_ROBIN},
            usable_dates=usable_dates,
            local_timezone=UTC,
            reference_month=1,
        )
        pattern = results["american_robin"]

        # Sanity-check the premise: each lucky month's rate really would
        # have cleared the rate-multiple bar on rate alone (the exact same
        # arithmetic compute_seasonal_patterns itself performs).
        rate = 1 / 10
        average_rate = (rate * len(lucky_months)) / 12
        assert rate >= average_rate * SEASONAL_MONTH_MIN_RATE_MULTIPLE

        # ...yet none is flagged, because each has only 1 presence day --
        # below SEASONAL_MIN_PRESENCE_DAYS_IN_FLAGGED_MONTH (2).
        assert pattern.status == "no_pattern_detected"
        assert pattern.typical_months == ()
        for month in lucky_months:
            assert month not in pattern.typical_months


class TestUsableDayFloorExcludesFromRateComparison:
    def test_a_barely_monitored_month_never_enters_the_rate_comparison(self) -> None:
        # 11 months with 10 usable days each; May has only 1 -- below
        # SEASONAL_MIN_USABLE_DAYS_IN_MONTH. 11 qualifying months still
        # comfortably clears the Place-wide 9-month floor.
        usable_dates = _usable_dates_for_months([m for m in range(1, 13) if m != 5], days_per_month=10)
        usable_dates |= _usable_dates_for_months([5], days_per_month=1)

        # January: 3 presence days (rate 0.3 among the 11 qualifying
        # months). May: 2 presence days against its own single usable day --
        # a 2.0 (200%) rate *if* it were wrongly folded into the comparison,
        # which would both swamp the average and (on its own count/rate)
        # trivially clear the flagged-month bar too.
        presence_dates = {date(YEAR, 1, day) for day in range(1, 4)} | {date(YEAR, 5, 1), date(YEAR, 5, 2)}

        visits = _visits_for_dates("junco", DARK_EYED_JUNCO, presence_dates)
        results = compute_seasonal_patterns(
            visits,
            taxa={"dark_eyed_junco": DARK_EYED_JUNCO},
            usable_dates=usable_dates,
            local_timezone=UTC,
            reference_month=1,
        )
        pattern = results["dark_eyed_junco"]

        may = pattern.months[4]
        assert (may.month, may.usable_day_count, may.presence_day_count) == (5, 1, 2)

        # January is correctly flagged, and only because May's outlier rate
        # was excluded from the average -- if May had been wrongly folded
        # in, its outsized rate would swamp the average and change which
        # month(s), if any, get flagged.
        assert pattern.typical_months == (1,)
        assert 5 not in pattern.typical_months


class TestReferenceMonthValidation:
    @pytest.mark.parametrize("bad_month", [0, 13])
    def test_out_of_range_reference_month_raises(self, bad_month: int) -> None:
        with pytest.raises(ValueError):
            compute_seasonal_patterns([], taxa={}, usable_dates=set(), local_timezone=UTC, reference_month=bad_month)


class TestPresenceDatesByTaxon:
    def test_multiple_visits_same_taxon_same_day_collapse_to_one_date(self) -> None:
        same_day = date(YEAR, 8, 15)
        visits = [
            _visit("v1", at=datetime(YEAR, 8, 15, 6, tzinfo=UTC), confirmed=NORTHERN_CARDINAL),
            _visit("v2", at=datetime(YEAR, 8, 15, 12, tzinfo=UTC), confirmed=NORTHERN_CARDINAL),
            _visit("v3", at=datetime(YEAR, 8, 15, 23, tzinfo=UTC), confirmed=NORTHERN_CARDINAL),
        ]
        result = presence_dates_by_taxon(visits, local_timezone=UTC)
        assert result == {"northern_cardinal": {same_day}}

    def test_unconfirmed_visit_contributes_nothing(self) -> None:
        visits = [
            _visit("v1", at=datetime(YEAR, 8, 15, 6, tzinfo=UTC), confirmed=None),
            _visit("v2", at=datetime(YEAR, 8, 16, 6, tzinfo=UTC), confirmed=NORTHERN_CARDINAL),
        ]
        result = presence_dates_by_taxon(visits, local_timezone=UTC)
        assert result == {"northern_cardinal": {date(YEAR, 8, 16)}}


class TestDeterminism:
    def test_identical_inputs_give_an_identical_result(self) -> None:
        usable_dates = _mature_usable_dates()
        presence_dates = _established_pattern_dates()
        visits = _visits_for_dates("titmouse", TUFTED_TITMOUSE, presence_dates)
        taxa = {"tufted_titmouse": TUFTED_TITMOUSE, "house_finch": HOUSE_FINCH}

        first = compute_seasonal_patterns(
            visits, taxa=taxa, usable_dates=usable_dates, local_timezone=UTC, reference_month=6
        )
        second = compute_seasonal_patterns(
            visits, taxa=taxa, usable_dates=usable_dates, local_timezone=UTC, reference_month=6
        )
        assert first == second


class TestEveryTaxonRepresented:
    def test_zero_presence_taxon_still_gets_an_honest_all_zero_entry(self) -> None:
        usable_dates = _mature_usable_dates()
        results = compute_seasonal_patterns(
            [], taxa={"house_finch": HOUSE_FINCH}, usable_dates=usable_dates, local_timezone=UTC, reference_month=1
        )
        assert "house_finch" in results
        pattern = results["house_finch"]
        assert pattern.status == "insufficient_history"
        assert len(pattern.months) == 12
        assert all(m.presence_day_count == 0 for m in pattern.months)
