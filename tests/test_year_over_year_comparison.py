"""Pure computation tests for mockingbird.analytics.year_over_year_comparison.

No repository, no database -- matches the established pure-module test
convention in tests/test_seasonal_pattern.py (itself following
tests/test_historical_baseline.py's own precedent for this package).
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest

from mockingbird.analytics.place_activity_report import TaxonFact, VisitFact
from mockingbird.analytics.year_over_year_comparison import (
    MAX_SPECIES_CHANGES_RETURNED,
    MIN_MATERIAL_TIMING_DIFFERENCE_DAYS,
    MIN_USABLE_DAYS_BEFORE_FIRST_OBSERVATION_FOR_TIMING_CLAIM,
    MIN_USABLE_DAYS_PER_PERIOD,
    YEAR_OVER_YEAR_POLICY_VERSION,
    PeriodInput,
    calendar_month_period,
    comparable_prior_period,
    compute_period_presence_facts,
    compute_place_year_over_year_comparison,
    compute_species_year_over_year_comparisons,
    select_notable_species_changes,
)

# One TaxonFact per test role, mirroring test_seasonal_pattern.py's own
# roster convention.
NORTHERN_CARDINAL = TaxonFact("northern_cardinal", "Northern Cardinal", "bird", True)
RUBY_THROATED_HUMMINGBIRD = TaxonFact("ruby_throated_hummingbird", "Ruby-throated Hummingbird", "bird", True)
HOUSE_FINCH = TaxonFact("house_finch", "House Finch", "bird", True)
BLUE_JAY = TaxonFact("blue_jay", "Blue Jay", "bird", True)
SONG_SPARROW = TaxonFact("song_sparrow", "Song Sparrow", "bird", True)

CURRENT_START = date(2026, 9, 1)
CURRENT_END = date(2026, 10, 1)  # exclusive -- September 2026
PRIOR_START = date(2025, 9, 1)
PRIOR_END = date(2025, 10, 1)  # exclusive -- September 2025


def _dates(start: date, count: int) -> set[date]:
    """`count` consecutive dates starting at `start`."""

    return {date.fromordinal(start.toordinal() + offset) for offset in range(count)}


def _period(
    *,
    start: date = CURRENT_START,
    end: date = CURRENT_END,
    is_complete: bool = True,
    usable_dates: set[date] | None = None,
    monitored_seconds: float | None = 200_000.0,
    confirmed_wildlife_visit_count: int = 0,
    has_any_monitoring_history: bool = True,
) -> PeriodInput:
    return PeriodInput(
        start_date=start,
        end_date=end,
        is_complete=is_complete,
        usable_dates=frozenset(usable_dates if usable_dates is not None else _dates(start, 20)),
        monitored_seconds=monitored_seconds,
        confirmed_wildlife_visit_count=confirmed_wildlife_visit_count,
        has_any_monitoring_history=has_any_monitoring_history,
    )


# 20 well-monitored days each period -- comfortably clears
# MIN_USABLE_DAYS_PER_PERIOD (5) on both sides for every Place-level test
# below unless a test deliberately narrows it.
CURRENT_WELL_MONITORED = _period(start=CURRENT_START, end=CURRENT_END, usable_dates=_dates(CURRENT_START, 20))
PRIOR_WELL_MONITORED = _period(start=PRIOR_START, end=PRIOR_END, usable_dates=_dates(PRIOR_START, 20))


class TestShiftYearAndComparablePeriod:
    def test_ordinary_month_shifts_back_one_calendar_year(self) -> None:
        start, end = comparable_prior_period(CURRENT_START, CURRENT_END)
        assert (start, end) == (PRIOR_START, PRIOR_END)

    def test_year_boundary_shifts_correctly(self) -> None:
        start, end = comparable_prior_period(date(2026, 1, 1), date(2026, 2, 1))
        assert (start, end) == (date(2025, 1, 1), date(2025, 2, 1))

    def test_leap_day_start_maps_to_feb_28_in_non_leap_prior_year(self) -> None:
        # 2028 is a leap year; 2027 is not.
        start, end = comparable_prior_period(date(2028, 2, 29), date(2028, 3, 15))
        assert start == date(2027, 2, 28)
        assert end == date(2027, 3, 15)

    def test_span_crossing_feb_29_is_one_day_shorter_in_the_prior_non_leap_year(self) -> None:
        # Documented, accepted exception (see the module docstring): a
        # current span crossing Feb 29 in a leap year shifts to a
        # same-shaped prior span one calendar day shorter.
        current_start, current_end = date(2028, 2, 25), date(2028, 3, 5)  # 9 days, includes Feb 29
        assert (current_end - current_start).days == 9
        prior_start, prior_end = comparable_prior_period(current_start, current_end)
        assert (prior_start, prior_end) == (date(2027, 2, 25), date(2027, 3, 5))
        assert (prior_end - prior_start).days == 8

    def test_end_not_after_start_raises(self) -> None:
        with pytest.raises(ValueError):
            comparable_prior_period(CURRENT_END, CURRENT_START)


class TestCalendarMonthPeriod:
    def test_ordinary_month(self) -> None:
        assert calendar_month_period(2026, 9) == (date(2026, 9, 1), date(2026, 10, 1))

    def test_december_wraps_to_next_year(self) -> None:
        assert calendar_month_period(2026, 12) == (date(2026, 12, 1), date(2027, 1, 1))

    @pytest.mark.parametrize("bad_month", [0, 13])
    def test_out_of_range_month_raises(self, bad_month: int) -> None:
        with pytest.raises(ValueError):
            calendar_month_period(2026, bad_month)


def _visit(
    visit_id: str, *, at: datetime, resolution: str = "reviewed", confirmed: TaxonFact | None = None
) -> VisitFact:
    return VisitFact(
        visit_id=visit_id,
        zone_id=None,
        zone_name=None,
        activity_started_at=at,
        resolution=resolution,  # type: ignore[arg-type]
        confirmed_taxon=confirmed,
    )


UNKNOWN_BIRD = TaxonFact("unknown_bird", "Unknown bird", "unknown", False)
PERSON = TaxonFact("person", "Person", "person", False)
FALSE_POSITIVE = TaxonFact("false_positive", "False positive", "false_positive", False)


class TestComputePeriodPresenceFacts:
    def test_confirmed_species_counts_toward_both_by_taxon_and_overall(self) -> None:
        visits = [_visit("v1", at=datetime(2026, 9, 5, 12, tzinfo=UTC), confirmed=NORTHERN_CARDINAL)]
        facts = compute_period_presence_facts(visits, local_timezone=UTC)
        assert facts.presence_dates_by_taxon == {"northern_cardinal": frozenset({date(2026, 9, 5)})}
        assert facts.overall_presence_dates == frozenset({date(2026, 9, 5)})
        assert facts.confirmed_wildlife_visit_count == 1
        assert facts.taxa == {"northern_cardinal": NORTHERN_CARDINAL}

    def test_unknown_bird_abstention_counts_toward_overall_only(self) -> None:
        visits = [_visit("v1", at=datetime(2026, 9, 5, 12, tzinfo=UTC), confirmed=UNKNOWN_BIRD)]
        facts = compute_period_presence_facts(visits, local_timezone=UTC)
        assert facts.presence_dates_by_taxon == {}
        assert facts.overall_presence_dates == frozenset({date(2026, 9, 5)})
        assert facts.confirmed_wildlife_visit_count == 1
        assert facts.taxa == {}

    def test_non_wildlife_and_false_positive_and_unreviewed_are_excluded_entirely(self) -> None:
        visits = [
            _visit("v1", at=datetime(2026, 9, 5, 12, tzinfo=UTC), confirmed=PERSON),
            _visit("v2", at=datetime(2026, 9, 6, 12, tzinfo=UTC), confirmed=FALSE_POSITIVE),
            _visit("v3", at=datetime(2026, 9, 7, 12, tzinfo=UTC), resolution="needs_review", confirmed=None),
        ]
        facts = compute_period_presence_facts(visits, local_timezone=UTC)
        assert facts.presence_dates_by_taxon == {}
        assert facts.overall_presence_dates == frozenset()
        assert facts.confirmed_wildlife_visit_count == 0

    def test_multiple_visits_same_taxon_same_day_collapse_to_one_presence_date_but_each_still_counts(
        self,
    ) -> None:
        visits = [
            _visit("v1", at=datetime(2026, 9, 5, 6, tzinfo=UTC), confirmed=NORTHERN_CARDINAL),
            _visit("v2", at=datetime(2026, 9, 5, 18, tzinfo=UTC), confirmed=NORTHERN_CARDINAL),
        ]
        facts = compute_period_presence_facts(visits, local_timezone=UTC)
        assert facts.presence_dates_by_taxon == {"northern_cardinal": frozenset({date(2026, 9, 5)})}
        assert facts.confirmed_wildlife_visit_count == 2


class TestPlaceLevelComparableAndDirection:
    def test_higher_current_activity_reads_higher(self) -> None:
        # 16 of 20 current days present (0.80) vs 4 of 20 prior (0.20) -- a
        # 0.60 rate difference, comfortably above the 0.25 floor.
        current_presence = _dates(CURRENT_START, 16)
        prior_presence = _dates(PRIOR_START, 4)
        result = compute_place_year_over_year_comparison(
            current=CURRENT_WELL_MONITORED,
            prior=PRIOR_WELL_MONITORED,
            current_presence_dates=current_presence,
            prior_presence_dates=prior_presence,
        )
        assert result.status == "comparable"
        assert result.overall_activity == "higher"
        assert result.policy_version == YEAR_OVER_YEAR_POLICY_VERSION
        assert result.association is not None
        assert result.current_period.usable_day_count == 20
        assert result.prior_period.usable_day_count == 20

    def test_lower_current_activity_reads_lower(self) -> None:
        current_presence = _dates(CURRENT_START, 4)
        prior_presence = _dates(PRIOR_START, 16)
        result = compute_place_year_over_year_comparison(
            current=CURRENT_WELL_MONITORED,
            prior=PRIOR_WELL_MONITORED,
            current_presence_dates=current_presence,
            prior_presence_dates=prior_presence,
        )
        assert result.status == "comparable"
        assert result.overall_activity == "lower"

    def test_materially_similar_activity_reads_no_material_difference(self) -> None:
        current_presence = _dates(CURRENT_START, 10)
        prior_presence = _dates(PRIOR_START, 9)  # 0.50 vs 0.45 -- below the 0.25 floor
        result = compute_place_year_over_year_comparison(
            current=CURRENT_WELL_MONITORED,
            prior=PRIOR_WELL_MONITORED,
            current_presence_dates=current_presence,
            prior_presence_dates=prior_presence,
        )
        assert result.status == "no_material_difference"
        assert result.overall_activity == "similar"


class TestUnequalEffortNormalization:
    """Section 8/25.A of the governing brief: raw monitored-hours totals
    must never skew the verdict -- only the binary usable-day threshold
    does. Mirrors the brief's own worked example (100 Visits/20 monitored
    hours must not read as "more active" than 90 Visits/200 monitored
    hours): here, one period is monitored far more intensively per day
    (many more raw hours) than the other, yet both clear the identical
    usable-day floor on the identical number of days -- the verdict must
    come out identical to the "effort was equal" case, proving `monitored_
    seconds` plays no role in the comparison itself (it is carried only as
    display/transparency metadata on `ComparablePeriod`)."""

    def test_higher_raw_monitored_hours_does_not_by_itself_change_the_verdict(self) -> None:
        usable_dates = _dates(CURRENT_START, 20)
        current_presence = _dates(CURRENT_START, 16)
        prior_presence = _dates(PRIOR_START, 4)

        equal_effort_current = _period(
            start=CURRENT_START, end=CURRENT_END, usable_dates=usable_dates, monitored_seconds=20 * 2.5 * 3600,
        )
        equal_effort_prior = _period(
            start=PRIOR_START, end=PRIOR_END, usable_dates=_dates(PRIOR_START, 20), monitored_seconds=20 * 2.5 * 3600,
        )
        baseline = compute_place_year_over_year_comparison(
            current=equal_effort_current, prior=equal_effort_prior,
            current_presence_dates=current_presence, prior_presence_dates=prior_presence,
        )

        # The *current* period is monitored far more intensively per day
        # (20 hours/day vs. 2.5 hours/day) -- the milestone brief's own
        # "100 Visits/20 hours" shape, generalized -- yet clears the exact
        # same 20 usable days, no more, no fewer.
        unequal_effort_current = _period(
            start=CURRENT_START, end=CURRENT_END, usable_dates=usable_dates, monitored_seconds=20 * 20 * 3600,
        )
        unequal_result = compute_place_year_over_year_comparison(
            current=unequal_effort_current, prior=equal_effort_prior,
            current_presence_dates=current_presence, prior_presence_dates=prior_presence,
        )

        assert unequal_result.status == baseline.status == "comparable"
        assert unequal_result.overall_activity == baseline.overall_activity == "higher"
        # The verdict is byte-identical regardless of the raw hours behind
        # it -- only usable_day_count (equal on both sides here) and
        # presence dates decided it.
        assert unequal_result.association == baseline.association

    def test_a_period_with_vastly_more_raw_hours_but_fewer_usable_days_is_not_favored(self) -> None:
        # The *prior* period racks up far more raw monitored hours (24
        # hours/day) than the current period (2 hours/day, barely clearing
        # the usable-day floor) -- but has only 4 usable days to the
        # current period's 20. Raw hours alone would make the prior period
        # look far better-monitored; usable-day count (what this module
        # actually gates on) correctly does not let that manufacture an
        # advantage for it.
        current = _period(
            start=CURRENT_START, end=CURRENT_END, usable_dates=_dates(CURRENT_START, 20),
            monitored_seconds=20 * 2 * 3600,
        )
        prior = _period(
            start=PRIOR_START, end=PRIOR_END, usable_dates=_dates(PRIOR_START, 4),
            monitored_seconds=4 * 24 * 3600,
        )
        result = compute_place_year_over_year_comparison(
            current=current, prior=prior,
            current_presence_dates=_dates(CURRENT_START, 16), prior_presence_dates=_dates(PRIOR_START, 2),
        )
        # The prior period's own 4 usable days fall below MIN_USABLE_DAYS_
        # PER_PERIOD (5) -- an honest abstention, never a rate computed
        # from its disproportionately larger raw-hours total.
        assert result.status == "insufficient_prior_coverage"
        assert result.overall_activity is None


class TestPlaceLevelAbstention:
    def test_insufficient_current_coverage(self) -> None:
        thin_current = _period(
            start=CURRENT_START, end=CURRENT_END, usable_dates=_dates(CURRENT_START, MIN_USABLE_DAYS_PER_PERIOD - 1)
        )
        result = compute_place_year_over_year_comparison(
            current=thin_current,
            prior=PRIOR_WELL_MONITORED,
            current_presence_dates=set(),
            prior_presence_dates=_dates(PRIOR_START, 10),
        )
        assert result.status == "insufficient_current_coverage"
        assert result.overall_activity is None

    def test_insufficient_prior_coverage_when_some_but_too_little_prior_history_exists(self) -> None:
        thin_prior = _period(
            start=PRIOR_START,
            end=PRIOR_END,
            usable_dates=_dates(PRIOR_START, MIN_USABLE_DAYS_PER_PERIOD - 1),
            has_any_monitoring_history=True,
        )
        result = compute_place_year_over_year_comparison(
            current=CURRENT_WELL_MONITORED,
            prior=thin_prior,
            current_presence_dates=_dates(CURRENT_START, 10),
            prior_presence_dates=set(),
        )
        assert result.status == "insufficient_prior_coverage"
        assert result.overall_activity is None

    def test_insufficient_prior_history_when_zero_usable_days_and_no_history_at_all(self) -> None:
        no_prior_history = _period(
            start=PRIOR_START, end=PRIOR_END, usable_dates=set(), has_any_monitoring_history=False
        )
        result = compute_place_year_over_year_comparison(
            current=CURRENT_WELL_MONITORED,
            prior=no_prior_history,
            current_presence_dates=_dates(CURRENT_START, 10),
            prior_presence_dates=set(),
        )
        assert result.status == "insufficient_prior_history"
        assert result.overall_activity is None

    def test_partial_current_period_abstains_even_with_a_real_difference_underneath(self) -> None:
        partial_current = _period(
            start=CURRENT_START, end=CURRENT_END, is_complete=False, usable_dates=_dates(CURRENT_START, 20)
        )
        result = compute_place_year_over_year_comparison(
            current=partial_current,
            prior=PRIOR_WELL_MONITORED,
            current_presence_dates=_dates(CURRENT_START, 16),
            prior_presence_dates=_dates(PRIOR_START, 4),
        )
        assert result.status == "partial_period"
        assert result.overall_activity is None
        assert result.current_period.is_complete is False

    def test_coverage_floor_takes_priority_over_partial_period(self) -> None:
        # Incomplete *and* under-monitored -- the more fundamental coverage
        # problem is reported, not the softer "not finished yet" state (see
        # the module docstring's "Partial-period honesty").
        partial_and_thin = _period(
            start=CURRENT_START,
            end=CURRENT_END,
            is_complete=False,
            usable_dates=_dates(CURRENT_START, MIN_USABLE_DAYS_PER_PERIOD - 1),
        )
        result = compute_place_year_over_year_comparison(
            current=partial_and_thin,
            prior=PRIOR_WELL_MONITORED,
            current_presence_dates=set(),
            prior_presence_dates=_dates(PRIOR_START, 10),
        )
        assert result.status == "insufficient_current_coverage"


class TestSpeciesLevelActivity:
    def test_tiny_denominator_does_not_produce_a_dramatic_insight(self) -> None:
        # 1 of 20 current days vs 0 of 20 prior -- a "100% increase" by raw
        # ratio, but the absolute evidence is far too thin to clear the
        # floor honestly: prior usable days meet the coverage floor, but
        # zero presence and one presence day are both too small a sample
        # for `conditional_association`'s own rate-difference gate to
        # register as material at this scale relative to the 20-day window.
        taxa = {"song_sparrow": SONG_SPARROW}
        results = compute_species_year_over_year_comparisons(
            taxa,
            current=CURRENT_WELL_MONITORED,
            prior=PRIOR_WELL_MONITORED,
            current_presence_dates_by_taxon={"song_sparrow": _dates(CURRENT_START, 1)},
            prior_presence_dates_by_taxon={"song_sparrow": set()},
        )
        assert results[0].status == "no_material_difference"
        assert results[0].activity_direction == "similar"

    def test_meaningful_increase_and_decrease(self) -> None:
        taxa = {"northern_cardinal": NORTHERN_CARDINAL, "blue_jay": BLUE_JAY}
        results = compute_species_year_over_year_comparisons(
            taxa,
            current=CURRENT_WELL_MONITORED,
            prior=PRIOR_WELL_MONITORED,
            current_presence_dates_by_taxon={
                "northern_cardinal": _dates(CURRENT_START, 16),
                "blue_jay": _dates(CURRENT_START, 4),
            },
            prior_presence_dates_by_taxon={
                "northern_cardinal": _dates(PRIOR_START, 4),
                "blue_jay": _dates(PRIOR_START, 16),
            },
        )
        by_label = {entry.taxon.label: entry for entry in results}
        assert by_label["northern_cardinal"].activity_direction == "higher"
        assert by_label["blue_jay"].activity_direction == "lower"

    def test_stable_species_reads_no_material_difference(self) -> None:
        taxa = {"house_finch": HOUSE_FINCH}
        results = compute_species_year_over_year_comparisons(
            taxa,
            current=CURRENT_WELL_MONITORED,
            prior=PRIOR_WELL_MONITORED,
            current_presence_dates_by_taxon={"house_finch": _dates(CURRENT_START, 10)},
            prior_presence_dates_by_taxon={"house_finch": _dates(PRIOR_START, 9)},
        )
        assert results[0].status == "no_material_difference"


class TestFirstObservedTiming:
    def test_materially_earlier_this_year(self) -> None:
        current_start_date = date(2026, 9, 10)  # 9 usable days into the period first
        prior_start_date = date(2025, 9, 21)  # 20 usable days into the period first
        current = _period(start=CURRENT_START, end=CURRENT_END, usable_dates=_dates(CURRENT_START, 20))
        prior = _period(start=PRIOR_START, end=PRIOR_END, usable_dates=_dates(PRIOR_START, 20))
        taxa = {"ruby_throated_hummingbird": RUBY_THROATED_HUMMINGBIRD}
        results = compute_species_year_over_year_comparisons(
            taxa,
            current=current,
            prior=prior,
            current_presence_dates_by_taxon={"ruby_throated_hummingbird": {current_start_date}},
            prior_presence_dates_by_taxon={"ruby_throated_hummingbird": {prior_start_date}},
        )
        entry = results[0]
        assert entry.first_observed_timing_status == "comparable"
        current_offset = (current_start_date - CURRENT_START).days
        prior_offset = (prior_start_date - PRIOR_START).days
        assert entry.first_observed_day_difference == current_offset - prior_offset
        assert entry.first_observed_day_difference is not None and entry.first_observed_day_difference < 0
        assert entry.first_observed_is_material is True

    def test_difference_smaller_than_material_threshold_is_not_flagged(self) -> None:
        current_first = date(2026, 9, 11)
        prior_first = date(2025, 9, 12)  # 1 day different -- below the material floor
        assert abs((current_first - CURRENT_START).days - (prior_first - PRIOR_START).days) < (
            MIN_MATERIAL_TIMING_DIFFERENCE_DAYS
        )
        taxa = {"ruby_throated_hummingbird": RUBY_THROATED_HUMMINGBIRD}
        results = compute_species_year_over_year_comparisons(
            taxa,
            current=CURRENT_WELL_MONITORED,
            prior=PRIOR_WELL_MONITORED,
            current_presence_dates_by_taxon={"ruby_throated_hummingbird": {current_first}},
            prior_presence_dates_by_taxon={"ruby_throated_hummingbird": {prior_first}},
        )
        entry = results[0]
        assert entry.first_observed_timing_status == "comparable"
        assert entry.first_observed_is_material is False

    def test_thin_lead_in_coverage_suppresses_the_timing_claim(self) -> None:
        # The taxon's first observation lands on the very first usable day
        # of the period -- no usable days exist *before* it to confirm
        # monitoring was already running, so "first observed" may only
        # mean "monitoring itself just started."
        current = _period(start=CURRENT_START, end=CURRENT_END, usable_dates=_dates(CURRENT_START, 20))
        prior = _period(start=PRIOR_START, end=PRIOR_END, usable_dates=_dates(PRIOR_START, 20))
        taxa = {"ruby_throated_hummingbird": RUBY_THROATED_HUMMINGBIRD}
        results = compute_species_year_over_year_comparisons(
            taxa,
            current=current,
            prior=prior,
            current_presence_dates_by_taxon={"ruby_throated_hummingbird": {CURRENT_START}},
            prior_presence_dates_by_taxon={"ruby_throated_hummingbird": {date(2025, 9, 21)}},
        )
        entry = results[0]
        assert entry.first_observed_timing_status == "insufficient_data"
        assert entry.first_observed_day_difference is None
        assert entry.first_observed_is_material is False

    def test_absent_from_one_period_suppresses_the_timing_claim(self) -> None:
        taxa = {"ruby_throated_hummingbird": RUBY_THROATED_HUMMINGBIRD}
        results = compute_species_year_over_year_comparisons(
            taxa,
            current=CURRENT_WELL_MONITORED,
            prior=PRIOR_WELL_MONITORED,
            current_presence_dates_by_taxon={"ruby_throated_hummingbird": {date(2026, 9, 15)}},
            prior_presence_dates_by_taxon={},
        )
        entry = results[0]
        assert entry.first_observed_timing_status == "insufficient_data"
        assert entry.first_observed_day_difference is None

    @pytest.mark.parametrize("floor", [MIN_USABLE_DAYS_BEFORE_FIRST_OBSERVATION_FOR_TIMING_CLAIM])
    def test_lead_in_floor_is_exactly_the_documented_constant(self, floor: int) -> None:
        # Exactly at the floor on both sides -- must be trusted, not
        # suppressed (a boundary-inclusive proof, not merely "some number
        # near the floor works").
        current_first = CURRENT_START + timedelta(days=floor)
        prior_first = PRIOR_START + timedelta(days=floor)
        current = _period(start=CURRENT_START, end=CURRENT_END, usable_dates=_dates(CURRENT_START, floor + 5))
        prior = _period(start=PRIOR_START, end=PRIOR_END, usable_dates=_dates(PRIOR_START, floor + 5))
        taxa = {"ruby_throated_hummingbird": RUBY_THROATED_HUMMINGBIRD}
        results = compute_species_year_over_year_comparisons(
            taxa,
            current=current,
            prior=prior,
            current_presence_dates_by_taxon={"ruby_throated_hummingbird": {current_first}},
            prior_presence_dates_by_taxon={"ruby_throated_hummingbird": {prior_first}},
        )
        assert results[0].first_observed_timing_status == "comparable"


class TestSelectNotableSpeciesChanges:
    def test_ranks_by_evidence_strength_not_raw_percent_change(self) -> None:
        # cardinal: a dramatic-looking ratio off a tiny sample (1 vs 0 of 20
        # -- an "infinite percent increase", but weak evidence, min=0).
        # blue_jay: a real, well-evidenced difference (16 vs 4 of 20, min=4).
        taxa = {"northern_cardinal": NORTHERN_CARDINAL, "blue_jay": BLUE_JAY}
        comparisons = compute_species_year_over_year_comparisons(
            taxa,
            current=CURRENT_WELL_MONITORED,
            prior=PRIOR_WELL_MONITORED,
            current_presence_dates_by_taxon={
                "northern_cardinal": _dates(CURRENT_START, 1),
                "blue_jay": _dates(CURRENT_START, 16),
            },
            prior_presence_dates_by_taxon={
                "northern_cardinal": set(),
                "blue_jay": _dates(PRIOR_START, 4),
            },
        )
        selected = select_notable_species_changes(comparisons)
        # cardinal's tiny-sample "increase" never clears the rate-difference
        # floor at all (no_material_difference, per TestSpeciesLevelActivity
        # above) -- so only blue_jay is eligible, confirming ranking never
        # even needs to compare them by percent.
        assert [entry.taxon.label for entry in selected] == ["blue_jay"]

    def test_bounded_to_max_count(self) -> None:
        taxa = {
            f"species_{i}": TaxonFact(f"species_{i}", f"Species {i}", "bird", True)
            for i in range(MAX_SPECIES_CHANGES_RETURNED + 3)
        }
        current_by_taxon = {label: _dates(CURRENT_START, 16) for label in taxa}
        prior_by_taxon = {label: _dates(PRIOR_START, 4) for label in taxa}
        comparisons = compute_species_year_over_year_comparisons(
            taxa,
            current=CURRENT_WELL_MONITORED,
            prior=PRIOR_WELL_MONITORED,
            current_presence_dates_by_taxon=current_by_taxon,
            prior_presence_dates_by_taxon=prior_by_taxon,
        )
        selected = select_notable_species_changes(comparisons)
        assert len(selected) == MAX_SPECIES_CHANGES_RETURNED

    def test_excludes_no_material_difference_and_abstentions(self) -> None:
        taxa = {"house_finch": HOUSE_FINCH}
        comparisons = compute_species_year_over_year_comparisons(
            taxa,
            current=CURRENT_WELL_MONITORED,
            prior=PRIOR_WELL_MONITORED,
            current_presence_dates_by_taxon={"house_finch": _dates(CURRENT_START, 10)},
            prior_presence_dates_by_taxon={"house_finch": _dates(PRIOR_START, 9)},
        )
        assert comparisons[0].status == "no_material_difference"
        assert select_notable_species_changes(comparisons) == []

    def test_a_material_timing_shift_alone_is_eligible_even_without_an_activity_difference(self) -> None:
        current_first = date(2026, 9, 10)
        prior_first = date(2025, 9, 25)
        # Full 30-day usable windows so every presence date below (including
        # the late-September ones) actually falls inside `usable_dates` on
        # both sides -- otherwise a presence date outside the usable window
        # can never contribute to its own side's rate at all.
        current = _period(start=CURRENT_START, end=CURRENT_END, usable_dates=_dates(CURRENT_START, 30))
        prior = _period(start=PRIOR_START, end=PRIOR_END, usable_dates=_dates(PRIOR_START, 30))
        taxa = {"ruby_throated_hummingbird": RUBY_THROATED_HUMMINGBIRD}
        # Identical, stable presence-day counts on both sides (6 of 30 days
        # each -- no activity difference) but a materially different single
        # first-observed date (Sept 10 vs. Sept 25).
        comparisons = compute_species_year_over_year_comparisons(
            taxa,
            current=current,
            prior=prior,
            current_presence_dates_by_taxon={
                "ruby_throated_hummingbird": {current_first} | _dates(date(2026, 9, 15), 5)
            },
            prior_presence_dates_by_taxon={
                "ruby_throated_hummingbird": {prior_first} | _dates(date(2025, 9, 26), 5)
            },
        )
        assert comparisons[0].status == "no_material_difference"
        assert comparisons[0].first_observed_is_material is True
        selected = select_notable_species_changes(comparisons)
        assert [entry.taxon.label for entry in selected] == ["ruby_throated_hummingbird"]


class TestDeterminism:
    def test_identical_inputs_give_an_identical_result(self) -> None:
        taxa = {"northern_cardinal": NORTHERN_CARDINAL}
        kwargs = dict(
            taxa=taxa,
            current=CURRENT_WELL_MONITORED,
            prior=PRIOR_WELL_MONITORED,
            current_presence_dates_by_taxon={"northern_cardinal": _dates(CURRENT_START, 16)},
            prior_presence_dates_by_taxon={"northern_cardinal": _dates(PRIOR_START, 4)},
        )
        first = compute_species_year_over_year_comparisons(**kwargs)
        second = compute_species_year_over_year_comparisons(**kwargs)
        assert first == second

        place_first = compute_place_year_over_year_comparison(
            current=CURRENT_WELL_MONITORED,
            prior=PRIOR_WELL_MONITORED,
            current_presence_dates=_dates(CURRENT_START, 16),
            prior_presence_dates=_dates(PRIOR_START, 4),
        )
        place_second = compute_place_year_over_year_comparison(
            current=CURRENT_WELL_MONITORED,
            prior=PRIOR_WELL_MONITORED,
            current_presence_dates=_dates(CURRENT_START, 16),
            prior_presence_dates=_dates(PRIOR_START, 4),
        )
        assert place_first == place_second


class TestEveryTaxonRepresented:
    def test_taxon_confirmed_only_a_year_ago_still_gets_an_honest_entry(self) -> None:
        taxa = {"house_finch": HOUSE_FINCH}
        results = compute_species_year_over_year_comparisons(
            taxa,
            current=CURRENT_WELL_MONITORED,
            prior=PRIOR_WELL_MONITORED,
            current_presence_dates_by_taxon={},
            prior_presence_dates_by_taxon={"house_finch": _dates(PRIOR_START, 16)},
        )
        assert len(results) == 1
        assert results[0].taxon.label == "house_finch"
        assert results[0].status == "comparable"
        assert results[0].activity_direction == "lower"

    def test_taxon_confirmed_only_this_period_still_gets_an_honest_entry(self) -> None:
        taxa = {"house_finch": HOUSE_FINCH}
        results = compute_species_year_over_year_comparisons(
            taxa,
            current=CURRENT_WELL_MONITORED,
            prior=PRIOR_WELL_MONITORED,
            current_presence_dates_by_taxon={"house_finch": _dates(CURRENT_START, 16)},
            prior_presence_dates_by_taxon={},
        )
        assert len(results) == 1
        assert results[0].status == "comparable"
        assert results[0].activity_direction == "higher"
