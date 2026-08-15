"""Place Intelligence & Reporting Foundation v1 (see
docs/place-activity-report-contract.md and
mockingbird.analytics.place_activity_report).

These tests exercise the pure computation layer directly with constructed
`VisitFact`/`TaxonFact` facts -- no repository, no database, matching the
existing `test_zone_insights.py` precedent for
`mockingbird.analytics.zone_insights`'s pure helpers. Real per-Visit facts
are adapted from `StreamVisitSummary` by a future integration step (see the
contract doc); this module's job is only to prove the deterministic
aggregation itself is correct.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

import pytest

from mockingbird.analytics.place_activity_report import (
    TaxonFact,
    VisitFact,
    compute_coverage_summary,
    compute_place_activity_report,
)
from mockingbird.analytics.zone_insights import TimeInterval

# Taxon fixtures mirror real seed taxonomy rows (api/demo_data.py) closely
# -- same label/category/is_species combinations -- without depending on
# them, so a test failure here means a real regression, not a fixture typo.
NORTHERN_CARDINAL = TaxonFact("northern_cardinal", "Northern Cardinal", "bird", True)
HOUSE_FINCH = TaxonFact("house_finch", "House Finch", "bird", True)
BLUE_JAY = TaxonFact("blue_jay", "Blue Jay", "bird", True)
GENERIC_BIRD = TaxonFact("bird", "Bird", "bird", False)
SQUIRREL = TaxonFact("squirrel", "Squirrel", "mammal", False)
CAT = TaxonFact("cat", "Cat", "pet", False)
PERSON = TaxonFact("person", "Person", "person", False)
UNKNOWN_ANIMAL = TaxonFact("unknown_animal", "Unknown Animal", "unknown", False)
FALSE_POSITIVE = TaxonFact("false_positive", "False Positive", "false_positive", False)

PERIOD_START = datetime(2026, 8, 14, 0, 0, tzinfo=UTC)
PERIOD_END = PERIOD_START + timedelta(days=1)


def _visit(
    visit_id: str,
    *,
    at: datetime,
    resolution: str = "reviewed",
    confirmed: TaxonFact | None = None,
    provisional: TaxonFact | None = None,
    zone_id: str | None = None,
    zone_name: str | None = None,
) -> VisitFact:
    return VisitFact(
        visit_id=visit_id,
        zone_id=zone_id,
        zone_name=zone_name,
        activity_started_at=at,
        resolution=resolution,  # type: ignore[arg-type]
        confirmed_taxon=confirmed,
        provisional_taxon=provisional,
    )


def _report(visits: list[VisitFact], **kwargs):
    kwargs.setdefault("period_start_at", PERIOD_START)
    kwargs.setdefault("period_end_at", PERIOD_END)
    return compute_place_activity_report(visits, **kwargs)


# 1. No activity ---------------------------------------------------------


def test_no_activity_returns_honest_zeroes_not_fabricated_facts() -> None:
    report = _report([])

    assert report.total_visit_count == 0
    assert report.wildlife_visit_count == 0
    assert report.confirmed_wildlife_visit_count == 0
    assert report.provisional_wildlife_visit_count == 0
    assert report.unresolved_visit_count == 0
    assert report.non_wildlife_visit_count == 0
    assert report.excluded_visit_count == 0
    assert report.taxa == []
    assert report.distinct_taxa_count == 0
    assert report.distinct_species_count == 0
    assert report.first_activity_at is None
    assert report.last_activity_at is None
    assert report.activity_by_zone == []
    assert report.busiest_zone is None
    # Always a full 24-hour histogram, even with nothing to show.
    assert [entry.hour for entry in report.activity_by_hour] == list(range(24))
    assert all(entry.wildlife_visit_count == 0 for entry in report.activity_by_hour)


# 2. One species / one Visit ---------------------------------------------


def test_one_confirmed_species_one_visit() -> None:
    report = _report(
        [_visit("v1", at=PERIOD_START + timedelta(hours=1), confirmed=NORTHERN_CARDINAL)]
    )

    assert report.total_visit_count == 1
    assert report.wildlife_visit_count == 1
    assert report.confirmed_wildlife_visit_count == 1
    assert report.distinct_taxa_count == 1
    assert report.distinct_species_count == 1
    [entry] = report.taxa
    assert entry.label == "northern_cardinal"
    assert entry.confirmed_visit_count == 1
    assert entry.provisional_visit_count == 0
    assert entry.total_visit_count == 1


# 3. Repeated Visits of the same species / #10 Visit counts, not animal counts


def test_repeated_visits_of_the_same_species_accumulate_as_visit_counts() -> None:
    """Five Visits of the same species is a Visit count of five -- MockingBird
    has no individual-animal identity, so this must never collapse to "1
    Northern Cardinal" the way a unique-animal claim would."""

    visits = [
        _visit(f"v{i}", at=PERIOD_START + timedelta(hours=i), confirmed=NORTHERN_CARDINAL)
        for i in range(5)
    ]

    report = _report(visits)

    assert report.confirmed_wildlife_visit_count == 5
    [entry] = report.taxa
    assert entry.confirmed_visit_count == 5
    assert entry.total_visit_count == 5


# 4. Multiple species ------------------------------------------------------


def test_multiple_species_are_each_represented_and_sorted_by_count() -> None:
    visits = [
        _visit("v1", at=PERIOD_START + timedelta(hours=1), confirmed=NORTHERN_CARDINAL),
        _visit("v2", at=PERIOD_START + timedelta(hours=2), confirmed=NORTHERN_CARDINAL),
        _visit("v3", at=PERIOD_START + timedelta(hours=3), confirmed=NORTHERN_CARDINAL),
        _visit("v4", at=PERIOD_START + timedelta(hours=4), confirmed=HOUSE_FINCH),
    ]

    report = _report(visits)

    assert report.distinct_taxa_count == 2
    assert report.distinct_species_count == 2
    assert [entry.label for entry in report.taxa] == ["northern_cardinal", "house_finch"]
    assert report.confirmed_wildlife_visit_count == 4


def test_non_species_taxon_counts_as_a_taxon_without_fabricating_a_species() -> None:
    """A confirmed "Squirrel" (mammal, not species-resolved) is a real,
    honest taxon entry -- distinct from both a fabricated species guess and
    from the confirmed-but-fully-unresolved "unknown_animal" bucket."""

    report = _report([_visit("v1", at=PERIOD_START + timedelta(hours=1), confirmed=SQUIRREL)])

    assert report.distinct_taxa_count == 1
    assert report.distinct_species_count == 0
    [entry] = report.taxa
    assert entry.label == "squirrel"
    assert entry.is_species is False
    assert report.confirmed_wildlife_visit_count == 1


# 5. Multiple Zones ---------------------------------------------------------


def test_multiple_zones_are_counted_and_ranked_independently() -> None:
    visits = [
        _visit(
            "v1",
            at=PERIOD_START + timedelta(hours=1),
            confirmed=NORTHERN_CARDINAL,
            zone_id="zone-feeder",
            zone_name="Feeder",
        ),
        _visit(
            "v2",
            at=PERIOD_START + timedelta(hours=2),
            confirmed=NORTHERN_CARDINAL,
            zone_id="zone-feeder",
            zone_name="Feeder",
        ),
        _visit(
            "v3",
            at=PERIOD_START + timedelta(hours=3),
            confirmed=HOUSE_FINCH,
            zone_id="zone-birdbath",
            zone_name="Birdbath",
        ),
        _visit("v4", at=PERIOD_START + timedelta(hours=4), confirmed=BLUE_JAY),  # no Zone
    ]

    report = _report(visits)

    counts = {entry.zone_name: entry.wildlife_visit_count for entry in report.activity_by_zone}
    assert counts == {"Feeder": 2, "Birdbath": 1, "No Zone": 1}
    assert report.busiest_zone is not None
    assert report.busiest_zone.zone_id == "zone-feeder"


def test_busiest_zone_never_crowns_the_no_zone_bucket() -> None:
    """A large amount of zone-less activity must not make "No Zone" the
    reported busiest Zone -- it is not a Zone the user drew."""

    visits = [
        _visit(f"no-zone-{i}", at=PERIOD_START + timedelta(hours=i), confirmed=NORTHERN_CARDINAL)
        for i in range(10)
    ] + [
        _visit(
            "one-real-zone",
            at=PERIOD_START + timedelta(hours=11),
            confirmed=HOUSE_FINCH,
            zone_id="zone-feeder",
            zone_name="Feeder",
        )
    ]

    report = _report(visits)

    assert report.busiest_zone is not None
    assert report.busiest_zone.zone_id == "zone-feeder"


# 6. Activity across multiple hours -----------------------------------------


def test_activity_by_hour_buckets_in_local_time_across_a_full_day() -> None:
    visits = [
        _visit("v-06", at=PERIOD_START + timedelta(hours=6), confirmed=NORTHERN_CARDINAL),
        _visit("v-06b", at=PERIOD_START + timedelta(hours=6, minutes=30), confirmed=HOUSE_FINCH),
        _visit("v-14", at=PERIOD_START + timedelta(hours=14), confirmed=BLUE_JAY),
    ]

    report = _report(visits)

    by_hour = {entry.hour: entry.wildlife_visit_count for entry in report.activity_by_hour}
    assert by_hour[6] == 2
    assert by_hour[14] == 1
    assert sum(by_hour.values()) == 3
    assert len(report.activity_by_hour) == 24


def test_activity_by_hour_uses_the_supplied_local_timezone_not_utc() -> None:
    # 2026-08-14T23:30:00Z is 2026-08-14T18:30:00-05:00 -- hour 18 locally,
    # not hour 23. Getting this wrong would misplace evening activity into
    # the next UTC day's early-morning bucket.
    local = timezone(timedelta(hours=-5))
    at = PERIOD_START + timedelta(hours=23, minutes=30)

    report = _report(
        [_visit("v1", at=at, confirmed=NORTHERN_CARDINAL)],
        local_timezone=local,
    )

    by_hour = {entry.hour: entry.wildlife_visit_count for entry in report.activity_by_hour}
    assert by_hour[18] == 1
    assert by_hour[23] == 0


# 7. Human-confirmed truth overrides provisional suggestion -----------------


def test_confirmed_truth_overrides_a_stale_provisional_suggestion() -> None:
    """A Visit can carry both a (now-superseded) automatic suggestion and a
    later human correction at once -- exactly how a real
    `StreamVisitSummary` looks, since its suggestion is fetched independent
    of review status. Reviewed truth must win outright, not blend."""

    visit = _visit(
        "v1",
        at=PERIOD_START + timedelta(hours=1),
        resolution="reviewed",
        confirmed=NORTHERN_CARDINAL,
        provisional=HOUSE_FINCH,  # the suggestion the human correction overrode
    )

    report = _report([visit])

    assert report.confirmed_wildlife_visit_count == 1
    assert report.provisional_wildlife_visit_count == 0
    assert [entry.label for entry in report.taxa] == ["northern_cardinal"]


# 8. Provisional suggestion remains usable absent human truth ---------------


def test_provisional_suggestion_usable_when_no_human_truth_exists() -> None:
    visit = _visit(
        "v1",
        at=PERIOD_START + timedelta(hours=1),
        resolution="needs_review",
        provisional=HOUSE_FINCH,
    )

    report = _report([visit])

    assert report.provisional_wildlife_visit_count == 1
    assert report.confirmed_wildlife_visit_count == 0
    assert report.wildlife_visit_count == 1
    [entry] = report.taxa
    assert entry.label == "house_finch"
    assert entry.provisional_visit_count == 1
    assert entry.confirmed_visit_count == 0


# 9. Genuinely unresolved evidence stays unresolved --------------------------


def test_visit_with_no_truth_and_no_suggestion_is_unresolved_not_fabricated() -> None:
    visit = _visit("v1", at=PERIOD_START + timedelta(hours=1), resolution="needs_review")

    report = _report([visit])

    assert report.unresolved_visit_count == 1
    assert report.wildlife_visit_count == 0
    assert report.taxa == []
    assert report.first_activity_at is None  # unresolved activity isn't "wildlife activity" yet


def test_non_species_suggestion_does_not_count_as_provisional_wildlife() -> None:
    """A suggestion that isn't itself species-level wildlife (for example a
    non-species or non-wildlife candidate) must not be promoted into a
    report fact -- it stays unresolved rather than guessed."""

    visit = _visit(
        "v1",
        at=PERIOD_START + timedelta(hours=1),
        resolution="needs_review",
        provisional=GENERIC_BIRD,  # is_species=False
    )

    report = _report([visit])

    assert report.unresolved_visit_count == 1
    assert report.provisional_wildlife_visit_count == 0


def test_confirmed_abstention_counts_as_wildlife_but_not_a_species() -> None:
    """A human explicitly confirming "an animal was here, species unknown"
    (unknown_animal/unknown_bird) is real, confirmed wildlife activity --
    it must count toward wildlife totals without being fabricated into a
    species entry. See "Unknown / unresolved" in
    docs/place-activity-report-contract.md."""

    visit = _visit("v1", at=PERIOD_START + timedelta(hours=1), confirmed=UNKNOWN_ANIMAL)

    report = _report([visit])

    assert report.confirmed_wildlife_visit_count == 1
    assert report.confirmed_species_unresolved_visit_count == 1
    assert report.wildlife_visit_count == 1
    assert report.taxa == []  # never fabricated into a species/taxon entry
    # Still real wildlife activity chronologically:
    assert report.first_activity_at == PERIOD_START + timedelta(hours=1)


# Non-wildlife and excluded accounting ---------------------------------------


def test_confirmed_non_wildlife_is_excluded_from_wildlife_counts() -> None:
    visit = _visit("v1", at=PERIOD_START + timedelta(hours=1), confirmed=PERSON)

    report = _report([visit])

    assert report.non_wildlife_visit_count == 1
    assert report.wildlife_visit_count == 0
    assert report.total_visit_count == 1


def test_rejected_and_false_positive_visits_are_excluded() -> None:
    visits = [
        _visit("rejected", at=PERIOD_START + timedelta(hours=1), resolution="rejected"),
        _visit(
            "false-positive",
            at=PERIOD_START + timedelta(hours=2),
            confirmed=FALSE_POSITIVE,
        ),
    ]

    report = _report(visits)

    assert report.excluded_visit_count == 2
    assert report.wildlife_visit_count == 0
    assert report.total_visit_count == 2


def test_honest_accounting_buckets_always_sum_to_total() -> None:
    visits = [
        _visit("confirmed", at=PERIOD_START + timedelta(hours=1), confirmed=NORTHERN_CARDINAL),
        _visit(
            "provisional",
            at=PERIOD_START + timedelta(hours=2),
            resolution="needs_review",
            provisional=HOUSE_FINCH,
        ),
        _visit("unresolved", at=PERIOD_START + timedelta(hours=3), resolution="needs_review"),
        _visit("non-wildlife", at=PERIOD_START + timedelta(hours=4), confirmed=CAT),
        _visit("rejected", at=PERIOD_START + timedelta(hours=5), resolution="rejected"),
    ]

    report = _report(visits)

    assert report.total_visit_count == 5
    assert (
        report.confirmed_wildlife_visit_count
        + report.provisional_wildlife_visit_count
        + report.unresolved_visit_count
        + report.non_wildlife_visit_count
        + report.excluded_visit_count
    ) == report.total_visit_count


# 11. First/last timestamps ---------------------------------------------------


def test_first_and_last_activity_timestamps_are_correct() -> None:
    middle = PERIOD_START + timedelta(hours=12)
    earliest = PERIOD_START + timedelta(hours=1)
    latest = PERIOD_START + timedelta(hours=20)
    visits = [
        _visit("middle", at=middle, confirmed=NORTHERN_CARDINAL),
        _visit("earliest", at=earliest, confirmed=NORTHERN_CARDINAL),
        _visit("latest", at=latest, confirmed=HOUSE_FINCH),
    ]

    report = _report(visits)

    assert report.first_activity_at == earliest
    assert report.last_activity_at == latest
    cardinal = next(entry for entry in report.taxa if entry.label == "northern_cardinal")
    assert cardinal.first_activity_at == earliest
    assert cardinal.last_activity_at == middle


def test_activity_outside_the_period_does_not_leak_into_first_last_or_counts() -> None:
    before_period = _visit(
        "before", at=PERIOD_START - timedelta(minutes=1), confirmed=NORTHERN_CARDINAL
    )
    at_start = _visit("at-start", at=PERIOD_START, confirmed=NORTHERN_CARDINAL)
    at_end_exclusive = _visit("at-end", at=PERIOD_END, confirmed=NORTHERN_CARDINAL)
    after_period = _visit("after", at=PERIOD_END + timedelta(minutes=1), confirmed=NORTHERN_CARDINAL)

    report = _report([before_period, at_start, at_end_exclusive, after_period])

    # Half-open period: [start, end) -- start is included, end is not.
    assert report.total_visit_count == 1
    assert report.first_activity_at == PERIOD_START
    assert report.last_activity_at == PERIOD_START


def test_invalid_period_is_rejected() -> None:
    with pytest.raises(ValueError):
        _report([], period_start_at=PERIOD_END, period_end_at=PERIOD_START)


# 12. Aggregation cannot mix Places/Streams/Zones incorrectly -----------------


def test_same_named_zones_on_different_streams_are_never_merged() -> None:
    """Two different Streams can each have a Zone literally named "Yard".
    Grouping must key off the globally-unique zone_id, never the display
    name, or these would silently collapse into one bucket."""

    visits = [
        _visit(
            "stream-a-yard",
            at=PERIOD_START + timedelta(hours=1),
            confirmed=NORTHERN_CARDINAL,
            zone_id="zone-a-yard",
            zone_name="Yard",
        ),
        _visit(
            "stream-b-yard",
            at=PERIOD_START + timedelta(hours=2),
            confirmed=HOUSE_FINCH,
            zone_id="zone-b-yard",
            zone_name="Yard",
        ),
    ]

    report = _report(visits)

    yard_entries = [entry for entry in report.activity_by_zone if entry.zone_name == "Yard"]
    assert len(yard_entries) == 2
    assert {entry.zone_id for entry in yard_entries} == {"zone-a-yard", "zone-b-yard"}
    assert all(entry.wildlife_visit_count == 1 for entry in yard_entries)


def test_caller_scoped_visit_list_never_widens_to_include_other_scopes() -> None:
    """This module has no Stream/Zone/Place membership concept of its own --
    it only ever reports on exactly the Visits it was given. A caller that
    scopes its input to one Stream/Zone must see only that scope back."""

    only_this_scope = [
        _visit(
            "in-scope",
            at=PERIOD_START + timedelta(hours=1),
            confirmed=NORTHERN_CARDINAL,
            zone_id="zone-a",
            zone_name="A",
        )
    ]

    report = _report(only_this_scope)

    assert report.total_visit_count == 1
    assert [entry.zone_id for entry in report.activity_by_zone] == ["zone-a"]


# Coverage --------------------------------------------------------------------


def test_coverage_unavailable_without_any_durable_history() -> None:
    summary = compute_coverage_summary(
        period_start_at=PERIOD_START,
        period_end_at=PERIOD_END,
        monitored_intervals=[],
        history_available_from=None,
    )

    assert summary.monitored_seconds is None
    assert summary.coverage_ratio is None
    assert summary.gaps == []


def test_coverage_full_period_monitored_has_no_gaps() -> None:
    summary = compute_coverage_summary(
        period_start_at=PERIOD_START,
        period_end_at=PERIOD_END,
        monitored_intervals=[TimeInterval(PERIOD_START, PERIOD_END)],
        history_available_from=PERIOD_START - timedelta(days=30),
    )

    assert summary.monitored_seconds == pytest.approx((PERIOD_END - PERIOD_START).total_seconds())
    assert summary.coverage_ratio == pytest.approx(1.0)
    assert summary.gaps == []
    assert summary.history_is_partial is False


def test_coverage_partial_monitoring_reports_ratio_and_gap() -> None:
    monitored_end = PERIOD_START + timedelta(hours=6)
    summary = compute_coverage_summary(
        period_start_at=PERIOD_START,
        period_end_at=PERIOD_END,
        monitored_intervals=[TimeInterval(PERIOD_START, monitored_end)],
        history_available_from=PERIOD_START,
    )

    assert summary.monitored_seconds == pytest.approx(6 * 3600)
    assert summary.coverage_ratio == pytest.approx(6 / 24)
    assert len(summary.gaps) == 1
    assert summary.gaps[0].start_at == monitored_end
    assert summary.gaps[0].end_at == PERIOD_END
    assert summary.gaps[0].duration_seconds == pytest.approx(18 * 3600)


def test_coverage_marks_history_partial_when_period_predates_it() -> None:
    history_start = PERIOD_START + timedelta(hours=2)
    summary = compute_coverage_summary(
        period_start_at=PERIOD_START,
        period_end_at=PERIOD_END,
        monitored_intervals=[TimeInterval(history_start, PERIOD_END)],
        history_available_from=history_start,
    )

    assert summary.history_is_partial is True
    # Only the portion after history began can honestly count as monitored.
    assert summary.monitored_seconds == pytest.approx((PERIOD_END - history_start).total_seconds())


def test_coverage_gaps_are_bounded_with_a_truncation_flag() -> None:
    # Many short monitored slivers separated by gaps -- more than max_gaps.
    intervals = [
        TimeInterval(
            PERIOD_START + timedelta(hours=2 * i),
            PERIOD_START + timedelta(hours=2 * i, minutes=1),
        )
        for i in range(10)
    ]

    summary = compute_coverage_summary(
        period_start_at=PERIOD_START,
        period_end_at=PERIOD_END,
        monitored_intervals=intervals,
        history_available_from=PERIOD_START,
        max_gaps=3,
    )

    assert len(summary.gaps) == 3
    assert summary.gaps_truncated is True
