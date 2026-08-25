"""Pure computation tests for mockingbird.analytics.place_story.

No repository, no database -- matches the existing test_place_change_
summary.py/test_historical_baseline.py precedent for a pure sibling module.
See docs/place-story-seasonal-timeline-v1-report.md for the product contract
these tests enforce.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from mockingbird.analytics.historical_baseline import SpeciesHistoricalStatus
from mockingbird.analytics.place_activity_report import TaxonFact, VisitFact
from mockingbird.analytics.place_story import (
    DIVERSITY_MILESTONE_ORDINALS,
    PlaceStoryEvent,
    build_place_story,
    comparison_insight_event,
    compute_diversity_milestone_events,
    compute_first_seen_events,
    detect_overall_activity_events,
    detect_regularity_transition_events,
    feature_change_event_to_story_event,
    phenology_observation_to_story_event,
)

NORTHERN_CARDINAL = TaxonFact("northern_cardinal", "Northern Cardinal", "bird", True)
BLUE_JAY = TaxonFact("blue_jay", "Blue Jay", "bird", True)
HOUSE_FINCH = TaxonFact("house_finch", "House Finch", "bird", True)

EASTERN = ZoneInfo("America/New_York")


def _at(local_date: date, hour: int = 10, *, tz: ZoneInfo = EASTERN) -> datetime:
    return datetime(local_date.year, local_date.month, local_date.day, hour, tzinfo=tz).astimezone(UTC)


def _visit(visit_id: str, taxon: TaxonFact, local_date: date, *, hour: int = 10) -> VisitFact:
    return VisitFact(
        visit_id=visit_id, zone_id=None, zone_name=None, activity_started_at=_at(local_date, hour),
        resolution="reviewed", confirmed_taxon=taxon,
    )


def _daily_visits(taxon: TaxonFact, start: date, count: int, *, prefix: str) -> list[VisitFact]:
    return [_visit(f"{prefix}{i}", taxon, start + timedelta(days=i)) for i in range(count)]


def _every_other_day_visits(taxon: TaxonFact, start: date, count: int, *, prefix: str) -> list[VisitFact]:
    return [_visit(f"{prefix}{i}", taxon, start + timedelta(days=2 * i)) for i in range(count)]


def _full_usable_dates(start: date, end: date) -> set[date]:
    dates: set[date] = set()
    cursor = start
    while cursor <= end:
        dates.add(cursor)
        cursor += timedelta(days=1)
    return dates


# ---------------------------------------------------------------------------
# compute_first_seen_events / compute_diversity_milestone_events
# ---------------------------------------------------------------------------


def test_first_seen_event_only_for_taxa_whose_debut_falls_in_period() -> None:
    period_start = _at(date(2025, 3, 1))
    period_end = _at(date(2025, 3, 31))
    statuses = [
        SpeciesHistoricalStatus(
            taxon=NORTHERN_CARDINAL, first_confirmed_at=_at(date(2025, 3, 10)),
            last_confirmed_at=_at(date(2025, 3, 10)), distinct_confirmed_days=1,
            distinct_confirmed_usable_days=1, total_confirmed_count=1, status="new",
        ),
        SpeciesHistoricalStatus(
            taxon=BLUE_JAY, first_confirmed_at=_at(date(2024, 1, 1)),
            last_confirmed_at=_at(date(2025, 3, 15)), distinct_confirmed_days=5,
            distinct_confirmed_usable_days=5, total_confirmed_count=10, status="regular",
        ),
    ]
    events = compute_first_seen_events(
        statuses, period_start_at=period_start, period_end_at=period_end, local_timezone=EASTERN
    )
    assert len(events) == 1
    assert events[0].kind == "first_seen"
    assert events[0].taxon_label == "northern_cardinal"
    assert events[0].event_date == date(2025, 3, 10)
    assert events[0].importance == "major"
    assert events[0].information_class == "reviewed"


def test_first_record_status_is_notable_not_major() -> None:
    """`"first_record"` (baseline not yet established) is a real first
    observation but must not claim the same ecological-novelty confidence
    as `"new"` -- mirrors daily_digest.py's own identical distinction."""

    statuses = [
        SpeciesHistoricalStatus(
            taxon=HOUSE_FINCH, first_confirmed_at=_at(date(2025, 3, 10)),
            last_confirmed_at=_at(date(2025, 3, 10)), distinct_confirmed_days=1,
            distinct_confirmed_usable_days=1, total_confirmed_count=1, status="first_record",
        ),
    ]
    events = compute_first_seen_events(
        statuses, period_start_at=_at(date(2025, 3, 1)), period_end_at=_at(date(2025, 3, 31)),
        local_timezone=EASTERN,
    )
    assert events[0].importance == "notable"


def test_diversity_milestones_use_all_time_first_confirmed_ordering() -> None:
    taxa = {"a": TaxonFact("a", "Species A", "bird", True), "b": TaxonFact("b", "Species B", "bird", True)}
    first_confirmed = {"a": _at(date(2025, 3, 5)), "b": _at(date(2025, 3, 1))}  # b debuted first
    events = compute_diversity_milestone_events(
        first_confirmed, taxa, local_timezone=EASTERN, ordinals=(1, 2)
    )
    by_ordinal = {int(event.id.rsplit(":", 1)[1]): event for event in events}
    assert by_ordinal[1].taxon_label == "b"
    assert by_ordinal[2].taxon_label == "a"
    assert all(event.importance == "major" for event in events)


def test_diversity_milestone_skipped_when_fewer_taxa_than_ordinal() -> None:
    taxa = {"a": TaxonFact("a", "Species A", "bird", True)}
    events = compute_diversity_milestone_events(
        {"a": _at(date(2025, 3, 5))}, taxa, local_timezone=EASTERN, ordinals=DIVERSITY_MILESTONE_ORDINALS
    )
    assert len(events) == 1
    assert events[0].id == "diversity-milestone:1"


# ---------------------------------------------------------------------------
# detect_regularity_transition_events -- the checkpoint scan
# ---------------------------------------------------------------------------


def _run_regularity_scan(
    visits: list[VisitFact], *, usable_dates: set[date], period_start: date, period_end: date
) -> list[PlaceStoryEvent]:
    taxa = {"northern_cardinal": NORTHERN_CARDINAL}
    first_confirmed = {"northern_cardinal": min(v.activity_started_at for v in visits)}
    last_confirmed = {"northern_cardinal": max(v.activity_started_at for v in visits)}
    return detect_regularity_transition_events(
        visits, taxa=taxa, all_time_first_confirmed_at=first_confirmed,
        all_time_last_confirmed_at=last_confirmed, usable_dates=usable_dates, local_timezone=EASTERN,
        period_start_at=_at(period_start), period_end_at=_at(period_end), baseline_window_days=366,
    )


def test_becoming_regular_fires_exactly_once_ever() -> None:
    """A taxon crossing the regular threshold, then oscillating between a
    real quiet stretch and the `"no_supported_change"` fallback once its
    reference window empties entirely, must not re-fire "became a regular
    presence" every time the fallback reappears -- regression test for the
    bug a first implementation had (see place_story.py's module docstring)."""

    start = date(2025, 3, 1)
    burst = _every_other_day_visits(NORTHERN_CARDINAL, start, 15, prefix="v")  # Mar1..Mar29
    end = start + timedelta(days=120)
    usable = _full_usable_dates(start - timedelta(days=5), end)
    events = _run_regularity_scan(burst, usable_dates=usable, period_start=start, period_end=end)

    regular_events = [e for e in events if e.kind == "regularity_change" and "became a regular" in e.title]
    assert len(regular_events) == 1, f"expected exactly one 'became regular' event, got {events}"


def test_returned_after_absence_detected_after_a_genuine_gap() -> None:
    """Headline scenario from the governing brief (Phase 5): a regular
    taxon goes quiet for well over the reference window, then returns with
    real recent presence -- must surface as `"return"`, dated at (or soon
    after) the actual day presence resumed, not silently dropped by the
    `place_change_summary` composition gap this module works around."""

    start = date(2025, 3, 1)
    burst = _every_other_day_visits(NORTHERN_CARDINAL, start, 15, prefix="v")  # through Mar29
    resume = start + timedelta(days=100)  # >70-day gap, comfortably clears both windows
    resumption = _daily_visits(NORTHERN_CARDINAL, resume, 30, prefix="r")
    visits = burst + resumption
    end = resume + timedelta(days=45)
    usable = _full_usable_dates(start - timedelta(days=5), end)

    events = _run_regularity_scan(visits, usable_dates=usable, period_start=start, period_end=end)
    returns = [e for e in events if e.kind == "return"]
    assert len(returns) == 1, f"expected exactly one return event, got {events}"
    assert returns[0].importance == "major"
    assert returns[0].taxon_label == "northern_cardinal"
    # Dated on or shortly after the real resumption date, never before it
    # and never more than a couple of weeks after (the detection floor is
    # 2 recent presence days, reachable within a few days of `resume`).
    assert resume <= returns[0].event_date <= resume + timedelta(days=14)


def test_returned_after_absence_not_claimed_for_a_brand_new_taxon() -> None:
    """A taxon whose first-ever sightings simply happen to cluster (e.g.
    two visits three days apart, right after its debut) must never be
    mistaken for "returning from absence" -- the reference window is empty
    because the taxon did not exist yet, not because it went quiet. Guarded
    by requiring `first_confirmed_at` to predate the reference window
    entirely (see `_effective_regularity_state`)."""

    start = date(2025, 6, 1)
    visits = [_visit("v0", NORTHERN_CARDINAL, start), _visit("v1", NORTHERN_CARDINAL, start + timedelta(days=1))]
    end = start + timedelta(days=10)
    usable = _full_usable_dates(start - timedelta(days=2), end)
    events = _run_regularity_scan(visits, usable_dates=usable, period_start=start, period_end=end)
    assert not any(e.kind == "return" for e in events), f"unexpected return event for a brand-new taxon: {events}"


def test_no_visits_produces_no_regularity_events() -> None:
    start, end = date(2025, 3, 1), date(2025, 3, 31)
    events = detect_regularity_transition_events(
        [], taxa={}, all_time_first_confirmed_at={}, all_time_last_confirmed_at={},
        usable_dates=_full_usable_dates(start, end), local_timezone=EASTERN,
        period_start_at=_at(start), period_end_at=_at(end), baseline_window_days=366,
    )
    assert events == []


def test_transitions_before_the_requested_period_are_not_emitted() -> None:
    """The lookback needed to seed `previous_states` correctly must never
    itself leak a visible entry for a transition that happened before the
    caller's own requested period started."""

    start = date(2025, 1, 1)
    burst = _every_other_day_visits(NORTHERN_CARDINAL, start, 15, prefix="v")  # regular by mid-Jan
    period_start = date(2025, 3, 1)  # well after the "became regular" transition
    period_end = date(2025, 3, 31)
    usable = _full_usable_dates(start - timedelta(days=5), period_end)
    events = _run_regularity_scan(burst, usable_dates=usable, period_start=period_start, period_end=period_end)
    assert events == []


# ---------------------------------------------------------------------------
# detect_overall_activity_events
# ---------------------------------------------------------------------------


def test_overall_activity_transitions_before_the_period_are_not_emitted() -> None:
    """Same seeding-range discipline as the per-taxon scan (see
    detect_regularity_transition_events's own regression test) applied to
    the Place-wide overall-activity pass."""

    start = date(2025, 1, 1)
    burst = _daily_visits(NORTHERN_CARDINAL, start, 40, prefix="v")
    quiet_period_start = start + timedelta(days=40)
    period_start, period_end = date(2025, 4, 1), date(2025, 4, 30)
    usable = _full_usable_dates(start - timedelta(days=5), period_end)
    events = detect_overall_activity_events(
        burst, usable_dates=usable, local_timezone=EASTERN,
        period_start_at=_at(period_start), period_end_at=_at(period_end), baseline_window_days=366,
    )
    assert events == [], f"a pre-period activity shift leaked into the requested period: {events}"


def test_overall_activity_event_requires_a_real_transition() -> None:
    start = date(2025, 3, 1)
    steady = _daily_visits(NORTHERN_CARDINAL, start, 60, prefix="v")
    end = start + timedelta(days=60)
    usable = _full_usable_dates(start - timedelta(days=5), end)
    events = detect_overall_activity_events(
        steady, usable_dates=usable, local_timezone=EASTERN,
        period_start_at=_at(start), period_end_at=_at(end), baseline_window_days=366,
    )
    # Steady, unchanging daily activity should never manufacture a
    # "notably higher/lower" claim.
    assert events == []


# ---------------------------------------------------------------------------
# Place-fact projections (feature change / comparison insight / phenology)
# ---------------------------------------------------------------------------


def test_feature_change_event_projection_is_a_direct_dated_fact() -> None:
    event = feature_change_event_to_story_event(
        change_event_id="evt-1", feature_id="feat-1", feature_name="Sunflower Feeder",
        event_type="added", effective_date=date(2025, 4, 2), note=None, prior_value=None,
        new_value=None, zone_id="zone-1", source_id="src-1",
    )
    assert event.kind == "feature_change"
    assert event.information_class == "reviewed"
    assert event.importance == "major"  # "added" is in _MAJOR_FEATURE_CHANGE_TYPES
    assert event.event_date == date(2025, 4, 2)
    assert event.detail_refs["change_event_id"] == "evt-1"


def test_food_changed_event_is_notable_not_major() -> None:
    event = feature_change_event_to_story_event(
        change_event_id="evt-2", feature_id="feat-1", feature_name="Sunflower Feeder",
        event_type="food_changed", effective_date=date(2025, 5, 1), note=None,
        prior_value="mixed seed", new_value="black-oil sunflower", zone_id=None, source_id=None,
    )
    assert event.importance == "notable"
    assert "mixed seed" in event.summary and "black-oil sunflower" in event.summary


def test_comparison_insight_is_separate_and_dated_at_window_close() -> None:
    event = comparison_insight_event(
        change_event_id="evt-1", feature_id="feat-1", feature_name="Sunflower Feeder",
        event_type="added", maturity="comparable", window_days=7, post_end=date(2025, 4, 9),
        association_status="more_common_under_condition",
    )
    assert event.kind == "comparison_insight"
    assert event.information_class == "inferred"  # never "reviewed" -- Phase 8
    assert event.event_date == date(2025, 4, 9)
    assert event.id != "feature-change:evt-1"  # distinct id from its parent fact
    assert "higher" in event.summary


def test_comparison_insight_never_fuses_weather_into_a_causal_claim() -> None:
    event = comparison_insight_event(
        change_event_id="evt-1", feature_id="feat-1", feature_name="Sunflower Feeder",
        event_type="added", maturity="comparable", window_days=7, post_end=date(2025, 4, 9),
        association_status="more_common_under_condition",
        weather_caveat="The post-change period was also cooler than typical.",
    )
    # Two separate sentences/clauses, not one merged causal statement.
    assert "compared with the monitored period before" in event.summary
    assert event.summary.strip().endswith("cooler than typical.")


def test_phenology_projection_carries_the_interval() -> None:
    event = phenology_observation_to_story_event(
        observation_id="obs-1", subject_label="Azaleas", phenomenon="Flowering",
        observed_start_date=date(2025, 4, 1), observed_end_date=date(2025, 4, 20), note=None,
    )
    assert event.kind == "phenology"
    assert event.event_date == date(2025, 4, 1)
    assert event.event_end_date == date(2025, 4, 20)
    assert event.information_class == "reviewed"


# ---------------------------------------------------------------------------
# build_place_story: merge, sort, filter, paginate
# ---------------------------------------------------------------------------


def _make_event(event_id: str, event_date: date, *, importance: str = "notable", kind: str = "phenology") -> PlaceStoryEvent:
    return PlaceStoryEvent(
        id=event_id, kind=kind, group="place", event_date=event_date, event_end_date=None,
        title=event_id, summary=event_id, information_class="reviewed", importance=importance,
    )


def test_sort_order_is_newest_first_then_major_before_notable() -> None:
    events = [
        _make_event("a", date(2025, 1, 1), importance="notable"),
        _make_event("b", date(2025, 1, 5)),
        _make_event("c", date(2025, 1, 5), importance="major"),
        _make_event("d", date(2025, 1, 3)),
    ]
    page = build_place_story([events], page_size=10)
    assert [e.id for e in page.events] == ["c", "b", "d", "a"]


def test_pagination_has_no_duplicates_or_gaps_across_pages() -> None:
    events = [_make_event(f"e{i}", date(2025, 1, 1) + timedelta(days=i)) for i in range(25)]
    page1 = build_place_story([events], page_size=10, offset=0)
    page2 = build_place_story([events], page_size=10, offset=10)
    page3 = build_place_story([events], page_size=10, offset=20)
    all_ids = [e.id for e in page1.events] + [e.id for e in page2.events] + [e.id for e in page3.events]
    assert len(all_ids) == len(set(all_ids)) == 25
    assert page1.has_more is True
    assert page2.has_more is True
    assert page3.has_more is False
    assert page3.next_offset is None


def test_filters_by_kind_taxon_and_feature() -> None:
    events = [
        PlaceStoryEvent(
            id="w1", kind="first_seen", group="wildlife", event_date=date(2025, 1, 1), event_end_date=None,
            title="w1", summary="w1", information_class="reviewed", importance="major", taxon_label="a",
        ),
        PlaceStoryEvent(
            id="f1", kind="feature_change", group="place", event_date=date(2025, 1, 2), event_end_date=None,
            title="f1", summary="f1", information_class="reviewed", importance="major", feature_id="feat-1",
        ),
    ]
    only_wildlife = build_place_story([events], kinds={"first_seen"})
    assert [e.id for e in only_wildlife.events] == ["w1"]

    only_taxon_a = build_place_story([events], taxon_label="a")
    assert [e.id for e in only_taxon_a.events] == ["w1"]

    only_feature = build_place_story([events], feature_id="feat-1")
    assert [e.id for e in only_feature.events] == ["f1"]


def test_date_range_filter_excludes_events_outside_the_window() -> None:
    events = [_make_event("jan", date(2025, 1, 15)), _make_event("mar", date(2025, 3, 15))]
    page = build_place_story([events], event_date_start=date(2025, 3, 1), event_date_end=date(2025, 3, 31))
    assert [e.id for e in page.events] == ["mar"]


def test_date_range_filter_keeps_an_interval_event_still_overlapping_the_window() -> None:
    """A phenology-style interval that started before the requested window
    but is still ongoing within it must not disappear (Phase 11/19)."""

    ongoing = PlaceStoryEvent(
        id="ongoing", kind="phenology", group="place", event_date=date(2025, 2, 20),
        event_end_date=date(2025, 3, 10), title="t", summary="s", information_class="reviewed",
        importance="notable",
    )
    page = build_place_story([[ongoing]], event_date_start=date(2025, 3, 1), event_date_end=date(2025, 3, 31))
    assert [e.id for e in page.events] == ["ongoing"]


def test_identical_id_from_two_sources_deduplicates_silently() -> None:
    event = _make_event("dup", date(2025, 1, 1))
    page = build_place_story([[event], [event]], page_size=10)
    assert len(page.events) == 1


def test_same_id_with_divergent_content_raises() -> None:
    a = _make_event("dup", date(2025, 1, 1))
    b = _make_event("dup", date(2025, 1, 2))  # same id, different event_date
    with pytest.raises(AssertionError):
        build_place_story([[a], [b]], page_size=10)


def test_event_end_date_before_event_date_is_rejected() -> None:
    with pytest.raises(ValueError):
        PlaceStoryEvent(
            id="bad", kind="phenology", group="place", event_date=date(2025, 4, 10),
            event_end_date=date(2025, 4, 1), title="t", summary="s", information_class="reviewed",
            importance="notable",
        )
