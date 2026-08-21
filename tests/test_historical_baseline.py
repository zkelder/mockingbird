"""Pure computation tests for mockingbird.analytics.historical_baseline.

No repository, no database -- matches the existing test_place_activity_
report.py precedent for its own pure sibling module. See
docs/historical-baseline-maturity-contract.md for the product contract
these tests enforce.
"""

from __future__ import annotations

import random
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from mockingbird.analytics.historical_baseline import (
    MIN_DISTINCT_USABLE_DAYS_FOR_REGULAR,
    MIN_USABLE_DAYS_FOR_DEVELOPING_BASELINE,
    MIN_USABLE_DAYS_FOR_ESTABLISHED_BASELINE,
    USABLE_DAY_MONITORED_SECONDS_THRESHOLD,
    bucket_intervals_by_local_day,
    compute_baseline_maturity,
    compute_historical_place_baseline,
    compute_species_historical_statuses,
    is_usable_day,
    usable_dates_from_daily_monitored_seconds,
)
from mockingbird.analytics.place_activity_report import TaxonFact, VisitFact
from mockingbird.analytics.zone_insights import TimeInterval

NORTHERN_CARDINAL = TaxonFact("northern_cardinal", "Northern Cardinal", "bird", True)
HOUSE_FINCH = TaxonFact("house_finch", "House Finch", "bird", True)
BLUE_JAY = TaxonFact("blue_jay", "Blue Jay", "bird", True)
SQUIRREL = TaxonFact("squirrel", "Squirrel", "mammal", True)
UNKNOWN_BIRD = TaxonFact("unknown_bird", "Unknown Bird", "unknown", False)
FALSE_POSITIVE = TaxonFact("false_positive", "False Positive", "false_positive", False)

TAXA_BY_LABEL = {
    taxon.label: taxon
    for taxon in (NORTHERN_CARDINAL, HOUSE_FINCH, BLUE_JAY, SQUIRREL, UNKNOWN_BIRD, FALSE_POSITIVE)
}

# "Today" for status-computation purposes -- an ordinary UTC day, no DST
# involved (DST correctness is exercised separately, in the
# bucket_intervals_by_local_day section, mirroring test_place_activity_
# report.py's own split between ordinary-period and DST-transition tests).
PERIOD_START = datetime(2026, 8, 21, 0, tzinfo=UTC)
PERIOD_END = PERIOD_START + timedelta(days=1)
WINDOW_START = PERIOD_START - timedelta(days=366)


def _visit(
    visit_id: str,
    *,
    at: datetime,
    resolution: str = "reviewed",
    confirmed: TaxonFact | None = None,
    provisional: TaxonFact | None = None,
) -> VisitFact:
    return VisitFact(
        visit_id=visit_id,
        zone_id=None,
        zone_name=None,
        activity_started_at=at,
        resolution=resolution,  # type: ignore[arg-type]
        confirmed_taxon=confirmed,
        provisional_taxon=provisional,
    )


def _statuses(
    window_visits,
    *,
    labels: list[str],
    all_first: dict[str, datetime],
    all_last: dict[str, datetime] | None = None,
    usable_dates: set,
    baseline_maturity: str = "established",
    period_start_at: datetime = PERIOD_START,
    period_end_at: datetime = PERIOD_END,
    local_timezone=UTC,
):
    return compute_species_historical_statuses(
        window_visits,
        taxa={label: TAXA_BY_LABEL[label] for label in labels},
        all_time_first_confirmed_at=all_first,
        all_time_last_confirmed_at=all_last or all_first,
        usable_dates=usable_dates,
        local_timezone=local_timezone,
        period_start_at=period_start_at,
        period_end_at=period_end_at,
        baseline_maturity=baseline_maturity,  # type: ignore[arg-type]
    )


def _status_for(statuses, label: str):
    [entry] = [entry for entry in statuses if entry.taxon.label == label]
    return entry


# ---------------------------------------------------------------------------
# is_usable_day / usable_dates_from_daily_monitored_seconds
# ---------------------------------------------------------------------------


def test_usable_day_at_exactly_the_two_hour_threshold_is_usable() -> None:
    assert is_usable_day(USABLE_DAY_MONITORED_SECONDS_THRESHOLD) is True


def test_usable_day_just_under_the_two_hour_threshold_is_not_usable() -> None:
    assert is_usable_day(USABLE_DAY_MONITORED_SECONDS_THRESHOLD - 1) is False


def test_usable_day_none_is_not_usable() -> None:
    """A calendar day with zero durable monitoring exposure -- never
    inferred, never a fabricated zero -- must never count as usable."""

    assert is_usable_day(None) is False


def test_usable_dates_extracts_only_days_clearing_the_threshold() -> None:
    daily = {
        date(2026, 8, 1): USABLE_DAY_MONITORED_SECONDS_THRESHOLD,
        date(2026, 8, 2): USABLE_DAY_MONITORED_SECONDS_THRESHOLD - 1,
        date(2026, 8, 3): 3 * USABLE_DAY_MONITORED_SECONDS_THRESHOLD,
        date(2026, 8, 4): 0.0,
    }
    assert usable_dates_from_daily_monitored_seconds(daily) == {date(2026, 8, 1), date(2026, 8, 3)}


# ---------------------------------------------------------------------------
# compute_baseline_maturity
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("usable_day_count", [0, 1, MIN_USABLE_DAYS_FOR_DEVELOPING_BASELINE - 1])
def test_baseline_insufficient_below_the_developing_floor(usable_day_count: int) -> None:
    assert compute_baseline_maturity(usable_day_count) == "insufficient"


@pytest.mark.parametrize(
    "usable_day_count",
    [MIN_USABLE_DAYS_FOR_DEVELOPING_BASELINE, MIN_USABLE_DAYS_FOR_ESTABLISHED_BASELINE - 1],
)
def test_baseline_developing_between_the_two_floors(usable_day_count: int) -> None:
    assert compute_baseline_maturity(usable_day_count) == "developing"


def test_baseline_established_at_and_above_the_established_floor() -> None:
    assert compute_baseline_maturity(MIN_USABLE_DAYS_FOR_ESTABLISHED_BASELINE) == "established"
    assert compute_baseline_maturity(MIN_USABLE_DAYS_FOR_ESTABLISHED_BASELINE + 30) == "established"


# ---------------------------------------------------------------------------
# bucket_intervals_by_local_day
# ---------------------------------------------------------------------------


def test_single_interval_within_one_utc_day() -> None:
    interval = TimeInterval(
        datetime(2026, 8, 10, 12, tzinfo=UTC), datetime(2026, 8, 10, 15, tzinfo=UTC)
    )
    totals = bucket_intervals_by_local_day(
        [interval], window_start_at=WINDOW_START, window_end_at=PERIOD_END, local_timezone=UTC
    )
    assert totals == {date(2026, 8, 10): 3 * 3600.0}


def test_interval_spanning_local_midnight_splits_across_both_days() -> None:
    interval = TimeInterval(
        datetime(2026, 8, 10, 22, tzinfo=UTC), datetime(2026, 8, 11, 2, tzinfo=UTC)
    )
    totals = bucket_intervals_by_local_day(
        [interval], window_start_at=WINDOW_START, window_end_at=PERIOD_END, local_timezone=UTC
    )
    assert totals == {date(2026, 8, 10): 2 * 3600.0, date(2026, 8, 11): 2 * 3600.0}


def test_interval_spanning_several_full_days() -> None:
    interval = TimeInterval(
        datetime(2026, 8, 10, 0, tzinfo=UTC), datetime(2026, 8, 13, 0, tzinfo=UTC)
    )
    totals = bucket_intervals_by_local_day(
        [interval], window_start_at=WINDOW_START, window_end_at=PERIOD_END, local_timezone=UTC
    )
    assert totals == {
        date(2026, 8, 10): 86_400.0,
        date(2026, 8, 11): 86_400.0,
        date(2026, 8, 12): 86_400.0,
    }


def test_overlapping_intervals_from_different_streams_union_not_double_count() -> None:
    """Two Streams both monitoring the same hour must count that hour once,
    matching place_activity_report's own union (not sum) coverage policy."""

    stream_a = TimeInterval(datetime(2026, 8, 10, 8, tzinfo=UTC), datetime(2026, 8, 10, 12, tzinfo=UTC))
    stream_b = TimeInterval(datetime(2026, 8, 10, 10, tzinfo=UTC), datetime(2026, 8, 10, 14, tzinfo=UTC))
    totals = bucket_intervals_by_local_day(
        [stream_a, stream_b], window_start_at=WINDOW_START, window_end_at=PERIOD_END, local_timezone=UTC
    )
    assert totals == {date(2026, 8, 10): 6 * 3600.0}  # 08:00-14:00 union, not 4h + 4h = 8h


def test_intervals_are_clipped_to_the_window_bounds() -> None:
    interval = TimeInterval(
        datetime(2026, 8, 9, 20, tzinfo=UTC), datetime(2026, 8, 10, 4, tzinfo=UTC)
    )
    totals = bucket_intervals_by_local_day(
        [interval],
        window_start_at=datetime(2026, 8, 10, 0, tzinfo=UTC),
        window_end_at=PERIOD_END,
        local_timezone=UTC,
    )
    # Only the portion from 2026-08-10 00:00 onward is in scope.
    assert totals == {date(2026, 8, 10): 4 * 3600.0}


def test_local_timezone_shifts_which_calendar_day_an_interval_counts_toward() -> None:
    """21:00-23:00 UTC is 17:00-19:00 in America/New_York (EDT, UTC-4) --
    the same local day as its UTC date here, but a later UTC evening hour
    (e.g. 02:00-04:00 UTC) would fall on the *previous* local date. Exercise
    both to prove local_timezone, not UTC, governs day assignment."""

    eastern = ZoneInfo("America/New_York")
    same_local_day = TimeInterval(
        datetime(2026, 8, 10, 21, tzinfo=UTC), datetime(2026, 8, 10, 23, tzinfo=UTC)
    )
    totals = bucket_intervals_by_local_day(
        [same_local_day], window_start_at=WINDOW_START, window_end_at=PERIOD_END, local_timezone=eastern
    )
    assert totals == {date(2026, 8, 10): 2 * 3600.0}

    previous_local_day = TimeInterval(
        datetime(2026, 8, 11, 2, tzinfo=UTC), datetime(2026, 8, 11, 4, tzinfo=UTC)
    )
    totals = bucket_intervals_by_local_day(
        [previous_local_day], window_start_at=WINDOW_START, window_end_at=PERIOD_END, local_timezone=eastern
    )
    # 02:00-04:00 UTC on the 11th is 22:00-00:00 EDT on the *10th*.
    assert totals == {date(2026, 8, 10): 2 * 3600.0}


def test_dst_spring_forward_local_day_boundaries_stay_correct() -> None:
    """2026-03-08 is a real US spring-forward date (America/New_York loses
    the 02:00-03:00 wall-clock hour). An interval spanning local midnight
    into that day must still split at the true local boundary, not a naive
    fixed-24h offset."""

    eastern = ZoneInfo("America/New_York")
    # 2026-03-07 23:00 EST (04:00 UTC) through 2026-03-08 04:00 EST (09:00 UTC).
    interval = TimeInterval(
        datetime(2026, 3, 8, 4, tzinfo=UTC), datetime(2026, 3, 8, 9, tzinfo=UTC)
    )
    totals = bucket_intervals_by_local_day(
        [interval],
        window_start_at=datetime(2026, 3, 7, tzinfo=UTC),
        window_end_at=datetime(2026, 3, 9, tzinfo=UTC),
        local_timezone=eastern,
    )
    assert totals.keys() == {date(2026, 3, 7), date(2026, 3, 8)}
    assert totals[date(2026, 3, 7)] == pytest.approx(3600.0)  # 23:00-00:00 EST
    assert totals[date(2026, 3, 8)] == pytest.approx(4 * 3600.0)  # 00:00-04:00 EST
    assert sum(totals.values()) == pytest.approx(5 * 3600.0)  # total wall time unaffected by the transition


def test_dst_fall_back_local_day_stays_a_single_bucket() -> None:
    """2026-11-01 is a real US fall-back date (the 01:00-02:00 EDT hour
    repeats as 01:00-02:00 EST). The whole calendar day's real elapsed
    duration is 25 hours; it must still resolve to exactly one bucket."""

    eastern = ZoneInfo("America/November".replace("November", "New_York"))
    interval = TimeInterval(
        datetime(2026, 11, 1, 4, tzinfo=UTC), datetime(2026, 11, 2, 5, tzinfo=UTC)
    )
    totals = bucket_intervals_by_local_day(
        [interval],
        window_start_at=datetime(2026, 11, 1, tzinfo=UTC),
        window_end_at=datetime(2026, 11, 3, tzinfo=UTC),
        local_timezone=eastern,
    )
    assert date(2026, 11, 1) in totals
    assert totals[date(2026, 11, 1)] == pytest.approx(25 * 3600.0)


# ---------------------------------------------------------------------------
# compute_historical_place_baseline
# ---------------------------------------------------------------------------


def test_no_monitoring_history_at_all_reports_insufficient_and_none_total() -> None:
    baseline = compute_historical_place_baseline(
        window_start_at=WINDOW_START,
        window_end_at=PERIOD_END,
        usable_dates=set(),
        has_any_monitoring_history=False,
        total_monitored_seconds=None,
        distinct_taxa_count=0,
        earliest_authoritative_record_at=None,
        latest_authoritative_record_at=None,
    )
    assert baseline.maturity == "insufficient"
    assert baseline.usable_day_count == 0
    assert baseline.total_monitored_seconds is None


def test_history_exists_but_zero_in_this_window_is_a_real_zero_not_none() -> None:
    """Distinct from the no-history case above: a Place monitored heavily a
    year ago but not at all within the bounded window has a real, known
    zero for this window, never a fabricated 'not yet computable' None."""

    baseline = compute_historical_place_baseline(
        window_start_at=WINDOW_START,
        window_end_at=PERIOD_END,
        usable_dates=set(),
        has_any_monitoring_history=True,
        total_monitored_seconds=0.0,
        distinct_taxa_count=2,
        earliest_authoritative_record_at=datetime(2024, 1, 1, tzinfo=UTC),
        latest_authoritative_record_at=datetime(2024, 1, 5, tzinfo=UTC),
    )
    assert baseline.total_monitored_seconds == 0.0
    assert baseline.maturity == "insufficient"


def test_maturity_reflects_usable_days_not_the_earliest_record_age() -> None:
    """A system with an old first record (or a long calendar span) but only
    a couple of genuinely usable days stays 'insufficient' -- baseline
    maturity is never a function of raw calendar age. See milestone
    requirement: 'a system installed 30 days ago but monitored only 4 hours
    should not have a mature baseline.'"""

    old_first_record = PERIOD_START - timedelta(days=200)
    baseline = compute_historical_place_baseline(
        window_start_at=WINDOW_START,
        window_end_at=PERIOD_END,
        usable_dates={date(2026, 8, 1), date(2026, 8, 2)},  # only 2 usable days
        has_any_monitoring_history=True,
        total_monitored_seconds=4 * 3600.0,
        distinct_taxa_count=1,
        earliest_authoritative_record_at=old_first_record,
        latest_authoritative_record_at=PERIOD_START,
    )
    assert baseline.maturity == "insufficient"


def test_maturity_becomes_established_once_enough_usable_days_accumulate() -> None:
    usable = {date(2026, 8, day) for day in range(1, 1 + MIN_USABLE_DAYS_FOR_ESTABLISHED_BASELINE)}
    baseline = compute_historical_place_baseline(
        window_start_at=WINDOW_START,
        window_end_at=PERIOD_END,
        usable_dates=usable,
        has_any_monitoring_history=True,
        total_monitored_seconds=len(usable) * USABLE_DAY_MONITORED_SECONDS_THRESHOLD,
        distinct_taxa_count=3,
        earliest_authoritative_record_at=datetime(2026, 8, 1, tzinfo=UTC),
        latest_authoritative_record_at=PERIOD_START,
    )
    assert baseline.maturity == "established"
    assert baseline.usable_day_count == MIN_USABLE_DAYS_FOR_ESTABLISHED_BASELINE


# ---------------------------------------------------------------------------
# compute_species_historical_statuses
# ---------------------------------------------------------------------------


def test_first_reviewed_species_record_with_immature_baseline_reads_first_record() -> None:
    """Requirement 1: a genuinely first-ever confirmed record, but the
    Place's own baseline is not yet established, must never claim
    ecological novelty -- 'First confirmed record so far,' not 'New.'"""

    confirmed_at = PERIOD_START + timedelta(hours=8)
    visits = [_visit("v1", at=confirmed_at, confirmed=NORTHERN_CARDINAL)]
    statuses = _statuses(
        visits,
        labels=["northern_cardinal"],
        all_first={"northern_cardinal": confirmed_at},
        usable_dates=set(),
        baseline_maturity="insufficient",
    )
    assert _status_for(statuses, "northern_cardinal").status == "first_record"


def test_first_reviewed_species_record_with_established_baseline_reads_new() -> None:
    """Requirement 2: the identical fact pattern, but with a deep enough
    baseline that 'New to your reviewed history' is a supportable claim."""

    confirmed_at = PERIOD_START + timedelta(hours=8)
    usable = {date(2026, 8, day) for day in range(1, 1 + MIN_USABLE_DAYS_FOR_ESTABLISHED_BASELINE)}
    visits = [_visit("v1", at=confirmed_at, confirmed=NORTHERN_CARDINAL)]
    statuses = _statuses(
        visits,
        labels=["northern_cardinal"],
        all_first={"northern_cardinal": confirmed_at},
        usable_dates=usable,
        baseline_maturity="established",
    )
    assert _status_for(statuses, "northern_cardinal").status == "new"


def test_provisional_suggestion_never_creates_or_extends_historical_presence() -> None:
    """Requirement 3: a needs_review Visit carrying only a provisional
    SpeciesSuggestion -- even several of them, even the one that would
    otherwise be the earliest-looking sighting -- can never contribute a
    distinct confirmed day, a confirmed count, or a first/last-confirmed
    timestamp. Only the one genuinely reviewed Visit does."""

    truly_confirmed_at = PERIOD_START - timedelta(days=10)
    visits = [
        # Five provisional-only sightings on five different days, one of
        # them earlier than the real confirmation -- none of this may count.
        _visit(
            f"suggested-{offset}",
            at=truly_confirmed_at - timedelta(days=offset + 1),
            resolution="needs_review",
            provisional=NORTHERN_CARDINAL,
        )
        for offset in range(5)
    ] + [_visit("confirmed", at=truly_confirmed_at, confirmed=NORTHERN_CARDINAL)]

    statuses = _statuses(
        visits,
        labels=["northern_cardinal"],
        all_first={"northern_cardinal": truly_confirmed_at},
        usable_dates={truly_confirmed_at.date()},
        baseline_maturity="developing",
    )
    entry = _status_for(statuses, "northern_cardinal")
    assert entry.distinct_confirmed_days == 1
    assert entry.total_confirmed_count == 1
    assert entry.first_confirmed_at == truly_confirmed_at
    assert entry.status != "regular"  # only 1 distinct usable confirmed day


def test_reviewed_truth_supersedes_a_stale_provisional_suggestion_on_the_same_visit() -> None:
    """Requirement 13: a Visit carrying both a (now-stale) automatic
    suggestion and a later disagreeing human correction -- exactly the
    real reviewed-after-BioCLIP shape -- must be counted under the
    confirmed label only, never both, never the suggestion."""

    at = PERIOD_START + timedelta(hours=1)
    visit = _visit("v1", at=at, confirmed=NORTHERN_CARDINAL, provisional=HOUSE_FINCH)
    statuses = _statuses(
        [visit],
        labels=["northern_cardinal", "house_finch"],
        all_first={"northern_cardinal": at, "house_finch": at - timedelta(days=100)},
        usable_dates={at.date()},
        baseline_maturity="developing",
    )
    assert _status_for(statuses, "northern_cardinal").total_confirmed_count == 1
    assert _status_for(statuses, "house_finch").total_confirmed_count == 0


def test_species_seen_many_times_in_one_day_does_not_automatically_become_regular() -> None:
    """Requirement 5: thirty Visits on one busy afternoon is still exactly
    one distinct (usable) day -- nowhere near the regularity bar."""

    one_day = date(2026, 8, 15)
    base = datetime(2026, 8, 15, 12, tzinfo=UTC)
    visits = [
        _visit(f"v{i}", at=base + timedelta(minutes=i), confirmed=NORTHERN_CARDINAL) for i in range(30)
    ]
    statuses = _statuses(
        visits,
        labels=["northern_cardinal"],
        all_first={"northern_cardinal": base},
        usable_dates={one_day},
        baseline_maturity="developing",
    )
    entry = _status_for(statuses, "northern_cardinal")
    assert entry.total_confirmed_count == 30
    assert entry.distinct_confirmed_days == 1
    assert entry.distinct_confirmed_usable_days == 1
    assert entry.status != "regular"


def test_species_seen_across_enough_usable_days_becomes_regular() -> None:
    """Requirement 6: real recurrence across distinct, genuinely-monitored
    days is what regularity means."""

    days = [date(2026, 8, 1), date(2026, 8, 5), date(2026, 8, 12)]
    visits = [
        _visit(f"v{i}", at=datetime(day.year, day.month, day.day, 9, tzinfo=UTC), confirmed=NORTHERN_CARDINAL)
        for i, day in enumerate(days)
    ]
    statuses = _statuses(
        visits,
        labels=["northern_cardinal"],
        all_first={"northern_cardinal": datetime(2026, 8, 1, 9, tzinfo=UTC)},
        usable_dates=set(days),
        baseline_maturity="developing",
    )
    entry = _status_for(statuses, "northern_cardinal")
    assert entry.distinct_confirmed_usable_days == MIN_DISTINCT_USABLE_DAYS_FOR_REGULAR
    assert entry.status == "regular"


def test_low_coverage_days_do_not_count_toward_regularity() -> None:
    """Requirement 7: a species confirmed on three different calendar days
    is not 'regular' if only one of those days actually cleared the usable
    monitoring bar -- the other two might have been a 3-minute glance."""

    days = [date(2026, 8, 1), date(2026, 8, 5), date(2026, 8, 12)]
    visits = [
        _visit(f"v{i}", at=datetime(day.year, day.month, day.day, 9, tzinfo=UTC), confirmed=NORTHERN_CARDINAL)
        for i, day in enumerate(days)
    ]
    statuses = _statuses(
        visits,
        labels=["northern_cardinal"],
        all_first={"northern_cardinal": datetime(2026, 8, 1, 9, tzinfo=UTC)},
        usable_dates={days[0]},  # only one of the three days was actually well-monitored
        baseline_maturity="developing",
    )
    entry = _status_for(statuses, "northern_cardinal")
    assert entry.distinct_confirmed_days == 3
    assert entry.distinct_confirmed_usable_days == 1
    assert entry.status != "regular"


def test_zero_monitoring_days_do_not_count_as_usable_even_with_a_sighting() -> None:
    """Requirement 8: a day the species was seen on, but that had no
    durable monitoring exposure recorded at all (never in the
    usable_dates set), must not silently count as usable."""

    the_day = date(2026, 8, 9)
    visit = _visit("v1", at=datetime(2026, 8, 9, 9, tzinfo=UTC), confirmed=NORTHERN_CARDINAL)
    statuses = _statuses(
        [visit],
        labels=["northern_cardinal"],
        all_first={"northern_cardinal": datetime(2026, 8, 9, 9, tzinfo=UTC)},
        usable_dates=set(),  # the_day is absent -- no durable exposure that day
        baseline_maturity="developing",
    )
    entry = _status_for(statuses, "northern_cardinal")
    assert the_day not in set()  # sanity: the fixture itself never claims it usable
    assert entry.distinct_confirmed_usable_days == 0


def test_unresolved_wildlife_unknown_bird_creates_no_named_history() -> None:
    """Requirement 9: an 'unknown_bird' abstention is confirmed wildlife
    activity, never a named taxon's historical record, and must not
    contaminate any other taxon's counts either."""

    visits = [
        _visit("unknown-1", at=PERIOD_START + timedelta(hours=1), confirmed=UNKNOWN_BIRD),
        _visit("cardinal-1", at=PERIOD_START + timedelta(hours=2), confirmed=NORTHERN_CARDINAL),
    ]
    # "unknown_bird" is deliberately absent from `labels`/`all_first` here,
    # exactly as a correct repository adapter would never populate an
    # all-time first-confirmed lookup for a non-taxon abstention label.
    statuses = _statuses(
        visits,
        labels=["northern_cardinal"],
        all_first={"northern_cardinal": PERIOD_START + timedelta(hours=2)},
        usable_dates={PERIOD_START.date()},
        baseline_maturity="developing",
    )
    assert [entry.taxon.label for entry in statuses] == ["northern_cardinal"]
    assert _status_for(statuses, "northern_cardinal").total_confirmed_count == 1


def test_a_reviewed_visit_with_no_resolvable_taxon_is_excluded_not_unresolved_wildlife() -> None:
    """A reviewed Visit whose label did not resolve to any taxonomy row at
    all (confirmed_taxon=None) is a different, data-hygiene case from an
    explicit 'unknown_bird' abstention -- see VisitFact's own docstring.
    Both must stay out of named-species history, but neither should raise."""

    visits = [_visit("bad-label", at=PERIOD_START + timedelta(hours=1), confirmed=None)]
    statuses = _statuses(
        visits,
        labels=["northern_cardinal"],
        all_first={"northern_cardinal": PERIOD_START - timedelta(days=1)},
        usable_dates=set(),
        baseline_maturity="insufficient",
    )
    assert _status_for(statuses, "northern_cardinal").total_confirmed_count == 0


def test_false_positive_confirmation_creates_no_named_history() -> None:
    visits = [_visit("fp-1", at=PERIOD_START + timedelta(hours=1), confirmed=FALSE_POSITIVE)]
    statuses = _statuses(
        visits,
        labels=["northern_cardinal"],
        all_first={"northern_cardinal": PERIOD_START - timedelta(days=1)},
        usable_dates=set(),
        baseline_maturity="insufficient",
    )
    assert _status_for(statuses, "northern_cardinal").total_confirmed_count == 0


def test_multiple_simultaneous_subject_visits_count_independently_per_taxon() -> None:
    """Requirement 10: a three-bird Event's independent sibling Visits
    (Multi-Subject Visit Assembly) must each contribute to their own
    taxon's history -- never collapsed into one occurrence, and never
    inflating an unrelated taxon's count."""

    simultaneous = PERIOD_START + timedelta(hours=8)
    visits = [
        _visit("nuthatch-sibling", at=simultaneous, confirmed=BLUE_JAY),
        _visit("finch-sibling-1", at=simultaneous, confirmed=HOUSE_FINCH),
        _visit("finch-sibling-2", at=simultaneous, confirmed=HOUSE_FINCH),
    ]
    statuses = _statuses(
        visits,
        labels=["blue_jay", "house_finch"],
        all_first={"blue_jay": simultaneous, "house_finch": simultaneous},
        usable_dates={simultaneous.date()},
        baseline_maturity="developing",
    )
    assert _status_for(statuses, "blue_jay").total_confirmed_count == 1
    assert _status_for(statuses, "house_finch").total_confirmed_count == 2
    # Both siblings share one calendar day -- still just 1 distinct day.
    assert _status_for(statuses, "house_finch").distinct_confirmed_days == 1


def test_local_midnight_boundary_assigns_the_correct_distinct_day() -> None:
    """Requirement 11: two confirmations either side of local midnight (not
    UTC midnight) in a non-UTC Place timezone must land on two distinct
    local dates."""

    eastern = ZoneInfo("America/New_York")
    # 2026-08-15 03:30 UTC = 2026-08-14 23:30 EDT (before local midnight).
    just_before = datetime(2026, 8, 15, 3, 30, tzinfo=UTC)
    # 2026-08-15 04:30 UTC = 2026-08-15 00:30 EDT (after local midnight).
    just_after = datetime(2026, 8, 15, 4, 30, tzinfo=UTC)
    visits = [
        _visit("before", at=just_before, confirmed=NORTHERN_CARDINAL),
        _visit("after", at=just_after, confirmed=NORTHERN_CARDINAL),
    ]
    statuses = _statuses(
        visits,
        labels=["northern_cardinal"],
        all_first={"northern_cardinal": just_before},
        usable_dates={date(2026, 8, 14), date(2026, 8, 15)},
        baseline_maturity="developing",
        local_timezone=eastern,
    )
    entry = _status_for(statuses, "northern_cardinal")
    assert entry.distinct_confirmed_days == 2


def test_period_boundary_is_half_open_like_the_rest_of_the_codebase() -> None:
    """A confirmation exactly at period_start_at counts as 'in period';
    one exactly at period_end_at does not -- matching `compute_place_
    activity_report`'s identical `[period_start_at, period_end_at)`
    convention."""

    at_start = _statuses(
        [_visit("v1", at=PERIOD_START, confirmed=NORTHERN_CARDINAL)],
        labels=["northern_cardinal"],
        all_first={"northern_cardinal": PERIOD_START},
        usable_dates=set(),
        baseline_maturity="established",
    )
    assert _status_for(at_start, "northern_cardinal").status == "new"

    at_end = _statuses(
        [_visit("v1", at=PERIOD_END, confirmed=NORTHERN_CARDINAL)],
        labels=["northern_cardinal"],
        all_first={"northern_cardinal": PERIOD_END},
        usable_dates=set(),
        baseline_maturity="established",
    )
    assert _status_for(at_end, "northern_cardinal").status != "new"


def test_deterministic_regardless_of_input_order() -> None:
    """Requirement 12: shuffling Visit order and taxon-map insertion order
    must never change the result."""

    days = [date(2026, 8, 1), date(2026, 8, 5), date(2026, 8, 12)]
    visits = [
        _visit(f"cardinal-{i}", at=datetime(d.year, d.month, d.day, 9, tzinfo=UTC), confirmed=NORTHERN_CARDINAL)
        for i, d in enumerate(days)
    ] + [_visit("finch-1", at=PERIOD_START + timedelta(hours=1), confirmed=HOUSE_FINCH)]

    all_first = {"northern_cardinal": datetime(2026, 8, 1, 9, tzinfo=UTC), "house_finch": PERIOD_START + timedelta(hours=1)}
    usable = set(days) | {PERIOD_START.date()}

    baseline_result = _statuses(
        visits, labels=["northern_cardinal", "house_finch"], all_first=all_first, usable_dates=usable, baseline_maturity="established"
    )

    rng = random.Random(1234)
    for _ in range(5):
        shuffled_visits = list(visits)
        rng.shuffle(shuffled_visits)
        shuffled_labels = list(all_first.keys())
        rng.shuffle(shuffled_labels)
        reshuffled = _statuses(
            shuffled_visits,
            labels=shuffled_labels,
            all_first=dict(all_first),
            usable_dates=set(usable),
            baseline_maturity="established",
        )
        assert reshuffled == baseline_result


def test_regular_status_is_structurally_impossible_under_insufficient_baseline() -> None:
    """Defensive guard: MIN_DISTINCT_USABLE_DAYS_FOR_REGULAR (3) can never
    be reached while fewer than MIN_USABLE_DAYS_FOR_DEVELOPING_BASELINE (3)
    usable days exist Place-wide -- but if a caller ever passes
    contradictory facts (a bug elsewhere), this must fail loudly rather
    than silently present an impossible 'Regular here' claim."""

    days = [date(2026, 8, 1), date(2026, 8, 5), date(2026, 8, 12)]
    visits = [
        _visit(f"v{i}", at=datetime(d.year, d.month, d.day, 9, tzinfo=UTC), confirmed=NORTHERN_CARDINAL)
        for i, d in enumerate(days)
    ]
    with pytest.raises(AssertionError):
        _statuses(
            visits,
            labels=["northern_cardinal"],
            all_first={"northern_cardinal": datetime(2026, 8, 1, 9, tzinfo=UTC)},
            usable_dates=set(days),  # 3 usable days confirmed...
            baseline_maturity="insufficient",  # ...but the caller claims baseline is insufficient. Contradiction.
        )


def test_mismatched_taxon_key_sets_raise_value_error() -> None:
    with pytest.raises(ValueError):
        compute_species_historical_statuses(
            [],
            taxa={"northern_cardinal": NORTHERN_CARDINAL},
            all_time_first_confirmed_at={"house_finch": PERIOD_START},
            all_time_last_confirmed_at={"northern_cardinal": PERIOD_START},
            usable_dates=set(),
            local_timezone=UTC,
            period_start_at=PERIOD_START,
            period_end_at=PERIOD_END,
            baseline_maturity="insufficient",
        )


def test_new_and_regular_are_mutually_exclusive_by_construction() -> None:
    """A taxon confirmed for the first time ever, this period, cannot also
    have 3+ prior distinct usable confirmed days -- 'new'/'first_record'
    always takes priority and 'regular' is never assigned alongside it."""

    at = PERIOD_START + timedelta(hours=1)
    statuses = _statuses(
        [_visit("v1", at=at, confirmed=NORTHERN_CARDINAL)],
        labels=["northern_cardinal"],
        all_first={"northern_cardinal": at},
        usable_dates={at.date()},
        baseline_maturity="established",
    )
    entry = _status_for(statuses, "northern_cardinal")
    assert entry.status == "new"
    assert entry.distinct_confirmed_usable_days < MIN_DISTINCT_USABLE_DAYS_FOR_REGULAR


def test_species_confirmed_before_but_not_regular_or_new_reads_seen_before() -> None:
    at = PERIOD_START - timedelta(days=30)
    statuses = _statuses(
        [_visit("v1", at=at, confirmed=NORTHERN_CARDINAL)],
        labels=["northern_cardinal"],
        all_first={"northern_cardinal": at},
        usable_dates={at.date()},
        baseline_maturity="developing",
    )
    assert _status_for(statuses, "northern_cardinal").status == "seen_before"


def test_dormant_taxon_absent_from_the_window_still_gets_an_honest_entry() -> None:
    """A taxon confirmed only long before the bounded window (e.g. for
    Bird Log's all-time label list) must still produce a status entry --
    'seen_before', zero window presence -- rather than silently vanishing."""

    long_ago = PERIOD_START - timedelta(days=500)
    statuses = _statuses(
        [],  # nothing in the current bounded window at all
        labels=["northern_cardinal"],
        all_first={"northern_cardinal": long_ago},
        all_last={"northern_cardinal": long_ago},
        usable_dates=set(),
        baseline_maturity="insufficient",
    )
    entry = _status_for(statuses, "northern_cardinal")
    assert entry.status == "seen_before"
    assert entry.distinct_confirmed_days == 0
    assert entry.total_confirmed_count == 0
    assert entry.first_confirmed_at == long_ago
