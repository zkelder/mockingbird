"""Pure computation tests for mockingbird.analytics.place_change_summary.

No repository, no database -- matches the existing test_historical_
baseline.py precedent for its own pure sibling module. See
docs/meaningful-change-detection-contract.md for the product contract these
tests enforce, and docs/historical-baseline-maturity-contract.md for the
historical-baseline primitives this module builds on.
"""

from __future__ import annotations

import random
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from mockingbird.analytics.historical_baseline import MIN_USABLE_DAYS_FOR_ESTABLISHED_BASELINE
from mockingbird.analytics.place_activity_report import TaxonFact, VisitFact
from mockingbird.analytics.place_change_summary import (
    MIN_ABSOLUTE_PRESENCE_DAY_DIFFERENCE,
    MIN_PROPORTIONAL_DIFFERENCE,
    MIN_REFERENCE_PRESENCE_DAYS_FOR_COMPARISON,
    RECENT_WINDOW_FRESHNESS_CAP_DAYS,
    RECENT_WINDOW_USABLE_DAYS,
    REFERENCE_WINDOW_USABLE_DAYS,
    compute_place_change_summary,
    compute_place_change_windows,
)

NORTHERN_CARDINAL = TaxonFact("northern_cardinal", "Northern Cardinal", "bird", True)
HOUSE_FINCH = TaxonFact("house_finch", "House Finch", "bird", True)
UNKNOWN_BIRD = TaxonFact("unknown_bird", "Unknown Bird", "unknown", False)

assert RECENT_WINDOW_USABLE_DAYS == MIN_USABLE_DAYS_FOR_ESTABLISHED_BASELINE == 7
assert REFERENCE_WINDOW_USABLE_DAYS == 14

# "Today" for every scenario below -- an ordinary UTC instant, no DST
# involved (DST correctness is exercised separately). The most recent usable
# day in the default 21-day fixture below is this same date, so staleness is
# always zero unless a scenario deliberately introduces a gap.
WINDOW_END_AT = datetime(2026, 8, 21, 20, tzinfo=UTC)
TODAY = WINDOW_END_AT.date()


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


def _consecutive_dates(*, end_date: date, count: int) -> set[date]:
    """`count` consecutive calendar dates ending at (and including) `end_date`."""

    return {end_date - timedelta(days=offset) for offset in range(count)}


def _full_usable_dates(*, end_date: date = TODAY, gap_days: int = 0) -> set[date]:
    """A full, valid 7 + 14 usable-day set: the 7 most recent days ending at
    `end_date`, then 14 more immediately preceding them, optionally with a
    calendar `gap_days` of non-usable days spliced in between the two
    windows (still 21 usable dates total -- the gap is simply absent from
    the set, exactly as a real camera outage would leave no durable exposure
    interval at all for those days)."""

    recent = _consecutive_dates(end_date=end_date, count=RECENT_WINDOW_USABLE_DAYS)
    reference_end = end_date - timedelta(days=RECENT_WINDOW_USABLE_DAYS + gap_days)
    reference = _consecutive_dates(end_date=reference_end, count=REFERENCE_WINDOW_USABLE_DAYS)
    return recent | reference


def _summary(
    window_visits: list[VisitFact],
    *,
    taxa: dict[str, TaxonFact],
    usable_dates: set[date],
    window_end_at: datetime = WINDOW_END_AT,
    local_timezone=UTC,
):
    return compute_place_change_summary(
        window_visits,
        taxa=taxa,
        usable_dates=usable_dates,
        local_timezone=local_timezone,
        window_end_at=window_end_at,
    )


def _taxon_status_for(summary, label: str):
    [entry] = [entry for entry in summary.taxa if entry.taxon.label == label]
    return entry


def _visits_on_dates(taxon: TaxonFact, dates: set[date], *, prefix: str) -> list[VisitFact]:
    return [
        _visit(f"{prefix}-{day.isoformat()}", at=datetime(day.year, day.month, day.day, 12, tzinfo=UTC), confirmed=taxon)
        for day in dates
    ]


# ---------------------------------------------------------------------------
# compute_place_change_windows
# ---------------------------------------------------------------------------


def test_fewer_than_recent_target_usable_days_total_is_insufficient_baseline() -> None:
    """Requirement 1 and 17: the real installation's own current ~6-usable-
    day history (fewer than the 7-day recent-window target) must yield
    `insufficient_baseline`, never a comparison."""

    usable = _consecutive_dates(end_date=TODAY, count=6)
    windows = compute_place_change_windows(usable, window_end_at=WINDOW_END_AT, local_timezone=UTC)
    assert windows.is_valid is False
    assert windows.invalid_reason == "insufficient_baseline"


def test_recent_window_full_but_reference_too_short_is_insufficient_baseline() -> None:
    """Requirement 2: a Place with an "established" (>= 7 usable days)
    historical_baseline is not automatically deep enough for THIS module's
    own stricter 7 + 14 = 21-day requirement."""

    usable = _consecutive_dates(end_date=TODAY, count=RECENT_WINDOW_USABLE_DAYS + 10)  # 17 total, not 21
    windows = compute_place_change_windows(usable, window_end_at=WINDOW_END_AT, local_timezone=UTC)
    assert windows.is_valid is False
    assert windows.invalid_reason == "insufficient_baseline"
    assert len(windows.recent_usable_dates) == RECENT_WINDOW_USABLE_DAYS  # recent itself was fully populated


def test_exactly_21_fresh_consecutive_usable_days_is_valid() -> None:
    usable = _full_usable_dates()
    windows = compute_place_change_windows(usable, window_end_at=WINDOW_END_AT, local_timezone=UTC)
    assert windows.is_valid is True
    assert windows.invalid_reason is None
    assert windows.recent_usable_dates == _consecutive_dates(end_date=TODAY, count=7)
    assert windows.reference_usable_dates == _consecutive_dates(end_date=TODAY - timedelta(days=7), count=14)
    # Reference ends exactly where recent begins -- contiguous, non-overlapping.
    assert windows.reference_window_end_at == windows.recent_window_start_at


def test_stale_recent_window_is_insufficient_recent_coverage() -> None:
    """Requirement 8: plenty of total historical depth exists, but the
    single most-recent usable day is stale (monitoring recently lapsed) --
    a materially different, more honest state than "still building a
    baseline"."""

    old_end = TODAY - timedelta(days=RECENT_WINDOW_FRESHNESS_CAP_DAYS + 5)
    usable = _full_usable_dates(end_date=old_end)
    windows = compute_place_change_windows(usable, window_end_at=WINDOW_END_AT, local_timezone=UTC)
    assert windows.is_valid is False
    assert windows.invalid_reason == "insufficient_recent_coverage"


def test_freshness_cap_boundary_is_inclusive() -> None:
    boundary_end = TODAY - timedelta(days=RECENT_WINDOW_FRESHNESS_CAP_DAYS)
    usable = _full_usable_dates(end_date=boundary_end)
    windows = compute_place_change_windows(usable, window_end_at=WINDOW_END_AT, local_timezone=UTC)
    assert windows.is_valid is True

    one_day_staler = _full_usable_dates(end_date=boundary_end - timedelta(days=1))
    stale_windows = compute_place_change_windows(one_day_staler, window_end_at=WINDOW_END_AT, local_timezone=UTC)
    assert stale_windows.is_valid is False
    assert stale_windows.invalid_reason == "insufficient_recent_coverage"


def test_calendar_gap_between_windows_is_invisible_to_the_walk() -> None:
    """Requirement 9: a real outage between the recent and reference windows
    (days with no durable exposure at all, so absent from `usable_dates`)
    must still be skipped over correctly -- the walk reaches past however
    large a gap to find the next 14 usable days, never stopping short and
    never treating the gap itself as an unusable/absent reference day."""

    no_gap = compute_place_change_windows(_full_usable_dates(gap_days=0), window_end_at=WINDOW_END_AT, local_timezone=UTC)
    small_gap = compute_place_change_windows(_full_usable_dates(gap_days=30), window_end_at=WINDOW_END_AT, local_timezone=UTC)
    large_gap = compute_place_change_windows(_full_usable_dates(gap_days=90), window_end_at=WINDOW_END_AT, local_timezone=UTC)

    for windows in (no_gap, small_gap, large_gap):
        assert windows.is_valid is True
        assert len(windows.reference_usable_dates) == REFERENCE_WINDOW_USABLE_DAYS
        # The recent window is anchored to "today" and is never affected by
        # how much unmonitored time sits further back in history.
        assert windows.recent_usable_dates == no_gap.recent_usable_dates

    # A larger real gap simply pushes the (still fully-populated) reference
    # window further back in calendar time -- it does not shrink it.
    assert max(small_gap.reference_usable_dates) < max(no_gap.reference_usable_dates)
    assert max(large_gap.reference_usable_dates) < max(small_gap.reference_usable_dates)


def test_deterministic_regardless_of_usable_dates_construction_order() -> None:
    dates = list(_full_usable_dates())
    shuffled = list(dates)
    random.Random(99).shuffle(shuffled)
    a = compute_place_change_windows(set(dates), window_end_at=WINDOW_END_AT, local_timezone=UTC)
    b = compute_place_change_windows(set(shuffled), window_end_at=WINDOW_END_AT, local_timezone=UTC)
    assert a == b


# ---------------------------------------------------------------------------
# compute_place_change_summary -- threshold policy
# ---------------------------------------------------------------------------


def test_similar_recent_and_reference_presence_is_no_supported_change() -> None:
    usable = _full_usable_dates()
    recent_dates = set(list(windows_recent(usable))[:4])
    reference_dates = set(list(windows_reference(usable))[:8])  # a proportionally similar rate (4/7 vs 8/14 = 50% both)
    visits = _visits_on_dates(NORTHERN_CARDINAL, recent_dates, prefix="r") + _visits_on_dates(
        NORTHERN_CARDINAL, reference_dates, prefix="h"
    )
    summary = _summary(visits, taxa={"northern_cardinal": NORTHERN_CARDINAL}, usable_dates=usable)
    assert _taxon_status_for(summary, "northern_cardinal").status == "no_supported_change"


def windows_recent(usable: set[date]) -> set[date]:
    return compute_place_change_windows(usable, window_end_at=WINDOW_END_AT, local_timezone=UTC).recent_usable_dates


def windows_reference(usable: set[date]) -> set[date]:
    return compute_place_change_windows(usable, window_end_at=WINDOW_END_AT, local_timezone=UTC).reference_usable_dates


def test_clearly_higher_recent_presence_matches_the_milestones_own_example() -> None:
    """Recent: 5 of 7 usable days. Reference: 3 of 14 usable days -- the
    exact example the milestone instructions themselves give for a
    supported "higher" result."""

    usable = _full_usable_dates()
    recent_dates = set(list(windows_recent(usable))[:5])
    reference_dates = set(list(windows_reference(usable))[:3])
    visits = _visits_on_dates(NORTHERN_CARDINAL, recent_dates, prefix="r") + _visits_on_dates(
        NORTHERN_CARDINAL, reference_dates, prefix="h"
    )
    summary = _summary(visits, taxa={"northern_cardinal": NORTHERN_CARDINAL}, usable_dates=usable)
    status = _taxon_status_for(summary, "northern_cardinal")
    assert status.recent_presence_days == 5
    assert status.recent_usable_day_count == 7
    assert status.reference_presence_days == 3
    assert status.reference_usable_day_count == 14
    assert status.status == "higher_recent_presence"


def test_clearly_lower_recent_presence_is_the_symmetric_case() -> None:
    usable = _full_usable_dates()
    recent_dates = set(list(windows_recent(usable))[:1])
    reference_dates = set(list(windows_reference(usable))[:10])
    visits = _visits_on_dates(NORTHERN_CARDINAL, recent_dates, prefix="r") + _visits_on_dates(
        NORTHERN_CARDINAL, reference_dates, prefix="h"
    )
    summary = _summary(visits, taxa={"northern_cardinal": NORTHERN_CARDINAL}, usable_dates=usable)
    assert _taxon_status_for(summary, "northern_cardinal").status == "lower_recent_presence"


def test_zero_reference_presence_with_trivial_recent_presence_stays_no_supported_change() -> None:
    """A single stray recent day against zero reference presence still must
    not claim a directional change -- `MIN_ABSOLUTE_PRESENCE_DAY_DIFFERENCE`
    (2) governs this exactly like every other input, not a separate rule.
    (Mobile & Remote Experience v1: this scenario used to be covered by
    `test_zero_reference_presence_never_claims_a_directional_change`, which
    asserted *all* zero-reference inputs -- including a real 7-of-7 run --
    stay `no_supported_change`; that was the reproduced defect this
    milestone fixed, see the sibling test below.)"""

    usable = _full_usable_dates()
    recent_dates = set(list(windows_recent(usable))[:1])
    visits = _visits_on_dates(NORTHERN_CARDINAL, recent_dates, prefix="r")
    summary = _summary(visits, taxa={"northern_cardinal": NORTHERN_CARDINAL}, usable_dates=usable)
    status = _taxon_status_for(summary, "northern_cardinal")
    assert status.recent_presence_days == 1
    assert status.reference_presence_days == 0
    assert status.status == "no_supported_change"


def test_zero_reference_presence_with_real_recent_run_is_higher_recent_presence() -> None:
    """Mobile & Remote Experience v1 Phase 0: reproduces, then proves fixed,
    the defect recorded at this milestone's own release-execution-state.md
    checkpoint -- an established taxon present on every one of the last 7
    usable days, after zero presence anywhere in the prior 14-usable-day
    reference window, is exactly the "returned after a real absence" case
    `regularity_narrative.compute_regularity_narrative`'s own
    `"returned_after_absence"` branch depends on `_presence_status` being
    able to report -- and previously never could, at any recent-presence
    count, purely because `reference_presence_days == 0` short-circuited
    before the shared rate/absolute-difference math ever ran (see
    `docs/mobile-remote-experience-v1-report.md`)."""

    usable = _full_usable_dates()
    recent_dates = windows_recent(usable)
    visits = _visits_on_dates(NORTHERN_CARDINAL, recent_dates, prefix="r")
    summary = _summary(visits, taxa={"northern_cardinal": NORTHERN_CARDINAL}, usable_dates=usable)
    status = _taxon_status_for(summary, "northern_cardinal")
    assert status.recent_presence_days == 7
    assert status.reference_presence_days == 0
    assert status.status == "higher_recent_presence"


@pytest.mark.parametrize(
    "recent_count,reference_count",
    [
        (1, 1),  # rate diff = 1/7 - 1/14 = 0.071 -- well under MIN_PROPORTIONAL_DIFFERENCE
        (2, 1),  # rate diff = 2/7 - 1/14 = 0.214 -- still under 0.25
    ],
)
def test_small_swings_stay_below_threshold_and_read_no_supported_change(
    recent_count: int, reference_count: int
) -> None:
    usable = _full_usable_dates()
    recent_dates = set(list(windows_recent(usable))[:recent_count])
    reference_dates = set(list(windows_reference(usable))[:reference_count])
    visits = _visits_on_dates(NORTHERN_CARDINAL, recent_dates, prefix="r") + _visits_on_dates(
        NORTHERN_CARDINAL, reference_dates, prefix="h"
    )
    summary = _summary(visits, taxa={"northern_cardinal": NORTHERN_CARDINAL}, usable_dates=usable)
    assert _taxon_status_for(summary, "northern_cardinal").status == "no_supported_change"


def test_one_busy_recent_day_does_not_imply_a_persistent_increase() -> None:
    """Requirement 6: thirty Visits confirmed on a single recent-window day
    must still read as exactly one recent presence day -- nowhere near
    "higher" against an otherwise-quiet reference window."""

    usable = _full_usable_dates()
    busy_day = next(iter(windows_recent(usable)))
    visits = [
        _visit(f"cardinal-{i}", at=datetime(busy_day.year, busy_day.month, busy_day.day, 8, i % 59, tzinfo=UTC), confirmed=NORTHERN_CARDINAL)
        for i in range(30)
    ]
    summary = _summary(visits, taxa={"northern_cardinal": NORTHERN_CARDINAL}, usable_dates=usable)
    status = _taxon_status_for(summary, "northern_cardinal")
    assert status.recent_presence_days == 1
    assert status.status == "no_supported_change"


def test_many_visits_on_one_reference_day_do_not_multiply_presence_frequency() -> None:
    """Requirement 7: the symmetric case on the reference side -- twenty
    Visits on one reference-window day is still exactly one reference
    presence day, never inflated into a "many prior days" baseline."""

    usable = _full_usable_dates()
    quiet_day = next(iter(windows_reference(usable)))
    visits = [
        _visit(f"cardinal-{i}", at=datetime(quiet_day.year, quiet_day.month, quiet_day.day, 8, i % 59, tzinfo=UTC), confirmed=NORTHERN_CARDINAL)
        for i in range(20)
    ]
    summary = _summary(visits, taxa={"northern_cardinal": NORTHERN_CARDINAL}, usable_dates=usable)
    status = _taxon_status_for(summary, "northern_cardinal")
    assert status.reference_presence_days == 1
    assert status.status == "no_supported_change"  # 1 of 14 reference vs. 0 of 7 recent -- no claim either way


def test_recent_period_with_insufficient_monitoring_forces_insufficient_recent_coverage_on_every_taxon() -> None:
    """Requirement 8, exercised through the full summary (not just windows):
    an invalid window forces every taxon's status uniformly -- comparison
    validity is a Place-wide property, never decided per taxon."""

    stale_usable = _full_usable_dates(end_date=TODAY - timedelta(days=RECENT_WINDOW_FRESHNESS_CAP_DAYS + 5))
    visits = _visits_on_dates(NORTHERN_CARDINAL, windows_reference(_full_usable_dates()), prefix="irrelevant")
    summary = _summary(
        visits,
        taxa={"northern_cardinal": NORTHERN_CARDINAL, "house_finch": HOUSE_FINCH},
        usable_dates=stale_usable,
    )
    assert _taxon_status_for(summary, "northern_cardinal").status == "insufficient_recent_coverage"
    assert _taxon_status_for(summary, "house_finch").status == "insufficient_recent_coverage"
    assert summary.overall.status == "insufficient_recent_coverage"


def test_offline_days_are_excluded_not_counted_as_absences() -> None:
    """Requirement 9, exercised end to end: the same *relative* presence
    (5 of the 7 recent usable days, 3 of the 14 reference usable days)
    must produce the identical status and counts regardless of how large a
    real calendar outage separates the two windows -- an offline stretch is
    invisible to the comparison, never a silent penalty."""

    for gap_days in (0, 45):
        usable = _full_usable_dates(gap_days=gap_days)
        recent_dates = set(list(windows_recent(usable))[:5])
        reference_dates = set(list(windows_reference(usable))[:3])
        visits = _visits_on_dates(NORTHERN_CARDINAL, recent_dates, prefix=f"r{gap_days}") + _visits_on_dates(
            NORTHERN_CARDINAL, reference_dates, prefix=f"h{gap_days}"
        )
        status = _taxon_status_for(
            _summary(visits, taxa={"northern_cardinal": NORTHERN_CARDINAL}, usable_dates=usable),
            "northern_cardinal",
        )
        assert status.recent_presence_days == 5
        assert status.reference_presence_days == 3
        assert status.status == "higher_recent_presence"


def test_provisional_suggestion_does_not_change_status() -> None:
    """Requirement 10: a needs_review Visit carrying only a provisional
    SpeciesSuggestion, even on every single reference-window day, must
    never contribute a reference presence day -- the actual claim this test
    makes, and unaffected by Mobile & Remote Experience v1's Phase 0 fix.

    `.status` itself is now `"higher_recent_presence"` rather than
    `"no_supported_change"` (flipped by that same fix, exactly like
    `test_zero_reference_presence_with_real_recent_run_is_higher_recent_
    presence` above): from `_presence_status`'s honest perspective, a
    reference window with only unreviewed provisional suggestions and one
    with nothing recorded at all are the identical zero-confirmed-presence
    input -- correctly indistinguishable, since a provisional suggestion
    must never be treated as if it happened for this comparison either way.
    """

    usable = _full_usable_dates()
    recent_dates = set(list(windows_recent(usable))[:5])
    provisional_visits = [
        _visit(f"suggested-{day.isoformat()}", at=datetime(day.year, day.month, day.day, 9, tzinfo=UTC), resolution="needs_review", provisional=NORTHERN_CARDINAL)
        for day in windows_reference(usable)
    ]
    visits = _visits_on_dates(NORTHERN_CARDINAL, recent_dates, prefix="r") + provisional_visits
    summary = _summary(visits, taxa={"northern_cardinal": NORTHERN_CARDINAL}, usable_dates=usable)
    status = _taxon_status_for(summary, "northern_cardinal")
    assert status.reference_presence_days == 0
    assert status.status == "higher_recent_presence"


def test_unresolved_wildlife_does_not_affect_named_species_comparison_but_does_count_overall() -> None:
    """Requirement 12: an "unknown_bird" confirmation is real, counted
    wildlife activity for the Place-wide `overall` aggregate, but must
    never contribute to any named taxon's presence-day count."""

    usable = _full_usable_dates()
    recent_dates = windows_recent(usable)
    visits = _visits_on_dates(UNKNOWN_BIRD, recent_dates, prefix="unknown")
    summary = _summary(visits, taxa={"northern_cardinal": NORTHERN_CARDINAL}, usable_dates=usable)

    cardinal_status = _taxon_status_for(summary, "northern_cardinal")
    assert cardinal_status.recent_presence_days == 0
    assert cardinal_status.reference_presence_days == 0

    assert summary.overall is not None
    assert summary.overall.recent_presence_days == len(recent_dates)


def test_multiple_simultaneous_subject_visits_count_one_taxon_presence_day() -> None:
    """Requirement 13: several sibling Visits under one Multi-Subject Visit
    Assembly Event, same taxon, same day, must still count as exactly one
    presence day for that taxon -- never one per sibling."""

    usable = _full_usable_dates()
    simultaneous_day = next(iter(windows_recent(usable)))
    simultaneous_at = datetime(simultaneous_day.year, simultaneous_day.month, simultaneous_day.day, 9, tzinfo=UTC)
    visits = [
        _visit("sibling-1", at=simultaneous_at, confirmed=NORTHERN_CARDINAL),
        _visit("sibling-2", at=simultaneous_at, confirmed=NORTHERN_CARDINAL),
        _visit("sibling-3", at=simultaneous_at, confirmed=NORTHERN_CARDINAL),
    ]
    summary = _summary(visits, taxa={"northern_cardinal": NORTHERN_CARDINAL}, usable_dates=usable)
    assert _taxon_status_for(summary, "northern_cardinal").recent_presence_days == 1


def test_local_midnight_boundary_assigns_the_correct_distinct_day() -> None:
    """Requirement 14: two confirmations either side of local midnight (not
    UTC midnight) in a non-UTC Place timezone must land on two distinct
    local presence days."""

    eastern = ZoneInfo("America/New_York")
    usable = _full_usable_dates()
    recent_dates = sorted(windows_recent(usable))
    day_a, day_b = recent_dates[0], recent_dates[1]
    # 03:30 UTC on day_b is 23:30 EDT the evening before (day_a); 04:30 UTC
    # on day_b is 00:30 EDT, just after local midnight, on day_b itself.
    just_before = datetime(day_b.year, day_b.month, day_b.day, 3, 30, tzinfo=UTC)
    just_after = datetime(day_b.year, day_b.month, day_b.day, 4, 30, tzinfo=UTC)
    visits = [
        _visit("before", at=just_before, confirmed=NORTHERN_CARDINAL),
        _visit("after", at=just_after, confirmed=NORTHERN_CARDINAL),
    ]
    summary = _summary(
        visits, taxa={"northern_cardinal": NORTHERN_CARDINAL}, usable_dates=usable, local_timezone=eastern
    )
    assert _taxon_status_for(summary, "northern_cardinal").recent_presence_days == 2
    assert day_a in recent_dates and day_b in recent_dates  # sanity: both are genuinely distinct usable days


def test_dst_spring_forward_does_not_shift_the_window_end_local_date() -> None:
    """Requirement 15: 2026-03-08 is a real US spring-forward date. Anchoring
    `window_end_at` right after the transition must still resolve to the
    correct local calendar date, keeping the freshest usable day's staleness
    at zero rather than an off-by-one."""

    eastern = ZoneInfo("America/New_York")
    transition_day = date(2026, 3, 8)
    window_end_at = datetime(2026, 3, 8, 20, tzinfo=UTC)  # 15:00 EDT, well after the 2 AM transition
    usable = _full_usable_dates(end_date=transition_day)
    windows = compute_place_change_windows(usable, window_end_at=window_end_at, local_timezone=eastern)
    assert windows.is_valid is True
    assert transition_day in windows.recent_usable_dates


def test_dst_fall_back_does_not_shift_the_window_end_local_date() -> None:
    """Requirement 15: 2026-11-01 is a real US fall-back date (a real 25-hour
    local day). The same anchoring must stay correct across it."""

    eastern = ZoneInfo("America/New_York")
    transition_day = date(2026, 11, 1)
    window_end_at = datetime(2026, 11, 2, 4, tzinfo=UTC)  # 23:00 EST on transition_day
    usable = _full_usable_dates(end_date=transition_day)
    windows = compute_place_change_windows(usable, window_end_at=window_end_at, local_timezone=eastern)
    assert windows.is_valid is True
    assert transition_day in windows.recent_usable_dates


def test_deterministic_regardless_of_visit_and_taxon_ordering() -> None:
    """Requirement 16: shuffling Visit order and taxon-map insertion order
    must never change the result."""

    usable = _full_usable_dates()
    recent_dates = set(list(windows_recent(usable))[:5])
    reference_dates = set(list(windows_reference(usable))[:3])
    visits = (
        _visits_on_dates(NORTHERN_CARDINAL, recent_dates, prefix="r")
        + _visits_on_dates(NORTHERN_CARDINAL, reference_dates, prefix="h")
        + _visits_on_dates(HOUSE_FINCH, set(list(windows_recent(usable))[:1]), prefix="finch")
    )
    taxa = {"northern_cardinal": NORTHERN_CARDINAL, "house_finch": HOUSE_FINCH}

    baseline_result = _summary(visits, taxa=taxa, usable_dates=usable)

    rng = random.Random(4321)
    for _ in range(5):
        shuffled_visits = list(visits)
        rng.shuffle(shuffled_visits)
        shuffled_taxa = dict(taxa)
        reshuffled = _summary(shuffled_visits, taxa=shuffled_taxa, usable_dates=set(usable))
        assert reshuffled == baseline_result


def test_dormant_taxon_absent_from_both_windows_still_gets_an_honest_entry() -> None:
    """Mirrors historical_baseline's own "dormant taxon" precedent: a taxon
    with zero presence in either window still gets a real, honest
    `no_supported_change` entry rather than silently vanishing."""

    usable = _full_usable_dates()
    summary = _summary([], taxa={"northern_cardinal": NORTHERN_CARDINAL}, usable_dates=usable)
    status = _taxon_status_for(summary, "northern_cardinal")
    assert status.recent_presence_days == 0
    assert status.reference_presence_days == 0
    assert status.status == "no_supported_change"


def test_overall_status_uses_its_own_distinct_wording() -> None:
    usable = _full_usable_dates()
    recent_dates = set(list(windows_recent(usable))[:5])
    reference_dates = set(list(windows_reference(usable))[:3])
    visits = _visits_on_dates(NORTHERN_CARDINAL, recent_dates, prefix="r") + _visits_on_dates(
        NORTHERN_CARDINAL, reference_dates, prefix="h"
    )
    summary = _summary(visits, taxa={"northern_cardinal": NORTHERN_CARDINAL}, usable_dates=usable)
    assert _taxon_status_for(summary, "northern_cardinal").status == "higher_recent_presence"
    assert summary.overall.status == "more_activity_recorded"

    insufficient_summary = _summary(
        [], taxa={"northern_cardinal": NORTHERN_CARDINAL}, usable_dates=_consecutive_dates(end_date=TODAY, count=3)
    )
    assert insufficient_summary.overall.status == "building_baseline"


def test_thresholds_are_the_documented_constants() -> None:
    """A guard against silent threshold drift -- these numbers are product
    policy, not implementation detail; a change to any of them must be a
    deliberate, reviewed edit here."""

    assert MIN_REFERENCE_PRESENCE_DAYS_FOR_COMPARISON == 1
    assert MIN_ABSOLUTE_PRESENCE_DAY_DIFFERENCE == 2
    assert MIN_PROPORTIONAL_DIFFERENCE == 0.25
