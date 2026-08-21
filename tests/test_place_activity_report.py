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
from zoneinfo import ZoneInfo

import pytest

from mockingbird.analytics.place_activity_report import (
    TaxonFact,
    VisitFact,
    compute_coverage_summary,
    compute_place_activity_report,
    compute_report_maturity,
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
    # No coverage was supplied at all -- honestly "no_data," never "usable"
    # merely because there also happens to be no wildlife to report.
    assert report.maturity == "no_data"
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


def test_a_taxonomy_category_outside_todays_bird_mammal_pair_still_counts_as_wildlife() -> None:
    """MockingBird is bird-first but wildlife-native (product-doctrine.md):
    a confirmed taxon in a category this report's fixture vocabulary has
    never seen before (a stand-in for a future "reptile"/"amphibian"/"bat"
    taxonomy category) must still be counted as real, confirmed wildlife
    activity -- not silently dropped to non-wildlife -- proving the
    wildlife boundary (`mockingbird.wildlife_taxonomy.is_wildlife_category`)
    is not hardcoded to `{"bird", "mammal"}`. See
    tests/test_wildlife_taxonomy.py for the predicate's own direct
    coverage; this is the end-to-end proof through `compute_place_activity_
    report` itself."""

    future_category_taxon = TaxonFact("box_turtle", "Box Turtle", "reptile", True)

    report = _report(
        [_visit("v1", at=PERIOD_START + timedelta(hours=1), confirmed=future_category_taxon)]
    )

    assert report.confirmed_wildlife_visit_count == 1
    assert report.non_wildlife_visit_count == 0
    [entry] = report.taxa
    assert entry.label == "box_turtle"
    assert entry.category == "reptile"


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


# Report maturity ---------------------------------------------------------
#
# The smallest useful classification of whether a report's own coverage is
# sufficient to trust a summary at all -- purely a function of `coverage`,
# never of Visit/wildlife counts. See `compute_report_maturity`.


def test_maturity_is_no_data_when_coverage_is_omitted_entirely() -> None:
    assert compute_report_maturity(None) == "no_data"


def test_maturity_is_no_data_when_no_durable_history_exists() -> None:
    summary = compute_coverage_summary(
        period_start_at=PERIOD_START,
        period_end_at=PERIOD_END,
        monitored_intervals=[],
        history_available_from=None,
    )

    assert summary.monitored_seconds is None
    assert compute_report_maturity(summary) == "no_data"


def test_maturity_is_sparse_just_under_the_two_hour_threshold() -> None:
    summary = compute_coverage_summary(
        period_start_at=PERIOD_START,
        period_end_at=PERIOD_END,
        monitored_intervals=[TimeInterval(PERIOD_START, PERIOD_START + timedelta(hours=2) - timedelta(seconds=1))],
        history_available_from=PERIOD_START,
    )

    assert compute_report_maturity(summary) == "sparse"


def test_maturity_is_usable_at_exactly_the_two_hour_threshold() -> None:
    summary = compute_coverage_summary(
        period_start_at=PERIOD_START,
        period_end_at=PERIOD_END,
        monitored_intervals=[TimeInterval(PERIOD_START, PERIOD_START + timedelta(hours=2))],
        history_available_from=PERIOD_START,
    )

    assert compute_report_maturity(summary) == "usable"


def test_maturity_is_usable_well_past_the_threshold() -> None:
    summary = compute_coverage_summary(
        period_start_at=PERIOD_START,
        period_end_at=PERIOD_END,
        monitored_intervals=[TimeInterval(PERIOD_START, PERIOD_END)],
        history_available_from=PERIOD_START,
    )

    assert compute_report_maturity(summary) == "usable"


def test_maturity_ignores_wildlife_activity_and_only_reflects_coverage() -> None:
    """A handful of Visits during two sparsely-monitored hours says nothing
    trustworthy about the other twenty-two -- maturity must not be swayed
    by how much (or how little) wildlife was recorded."""

    sparse_coverage = compute_coverage_summary(
        period_start_at=PERIOD_START,
        period_end_at=PERIOD_END,
        monitored_intervals=[TimeInterval(PERIOD_START, PERIOD_START + timedelta(minutes=30))],
        history_available_from=PERIOD_START,
    )

    busy_report = _report(
        [
            _visit("v1", at=PERIOD_START + timedelta(minutes=5), confirmed=NORTHERN_CARDINAL),
            _visit("v2", at=PERIOD_START + timedelta(minutes=10), confirmed=NORTHERN_CARDINAL),
            _visit("v3", at=PERIOD_START + timedelta(minutes=15), confirmed=HOUSE_FINCH),
        ],
        coverage=sparse_coverage,
    )

    assert busy_report.total_visit_count == 3
    assert busy_report.maturity == "sparse"


# DST-correct local-time bucketing ---------------------------------------
#
# `compute_place_activity_report` converts each Visit with its own
# `visit.activity_started_at.astimezone(local_timezone)` call, inside the
# per-Visit loop -- never once for the whole batch. That means it is
# already DST-correct *as long as it is given a real variable-offset
# `tzinfo`* (a `zoneinfo.ZoneInfo`, which resolves the historically-correct
# UTC offset independently for each timestamp) rather than a fixed-offset
# `datetime.timezone` snapshot resolved once from a single moment (the
# repository-layer bug `ProductRepository.place_activity_report` fixed --
# see docs/place-activity-report-contract.md and
# tests/test_place_activity_report_repository.py for the real end-to-end
# proof). These tests lock in that per-Visit correctness directly against
# the pure computation module, using a real US zone so a future refactor
# that "simplifies" this into one offset resolved outside the loop fails
# loudly here first.

NY = ZoneInfo("America/New_York")

# 2026 US spring-forward: clocks jump from 01:59:59 EST directly to
# 03:00:00 EDT at 2026-03-08T07:00:00Z (2am local). 2026 US fall-back:
# clocks fall from 01:59:59 EDT back to 01:00:00 EST at
# 2026-11-01T06:00:00Z (2am EDT local), so local 01:00-01:59 occurs twice.
SPRING_FORWARD_INSTANT = datetime(2026, 3, 8, 7, 0, tzinfo=UTC)
FALL_BACK_INSTANT = datetime(2026, 11, 1, 6, 0, tzinfo=UTC)


def test_ordinary_non_dst_period_buckets_by_the_real_zone() -> None:
    """A period nowhere near a transition: the historically-correct EST
    offset (UTC-5) applies uniformly, exactly like a fixed offset would --
    this is the baseline every DST-transition test below is contrasted
    against."""

    period_start = datetime(2026, 1, 12, 0, 0, tzinfo=UTC)
    period_end = period_start + timedelta(days=1)
    # 2026-01-12T18:30:00Z is 13:30 EST (UTC-5), not UTC-4.
    at = period_start + timedelta(hours=18, minutes=30)

    report = _report(
        [_visit("v1", at=at, confirmed=NORTHERN_CARDINAL)],
        period_start_at=period_start,
        period_end_at=period_end,
        local_timezone=NY,
    )

    by_hour = {entry.hour: entry.wildlife_visit_count for entry in report.activity_by_hour}
    assert by_hour[13] == 1
    assert by_hour[18] == 0


def test_us_spring_forward_transition_buckets_each_side_correctly() -> None:
    """One Visit just before the jump (EST, UTC-5) and one just after (EDT,
    UTC-4) must each resolve to the offset that genuinely applied at its
    own timestamp, not a single offset borrowed from the other."""

    before = SPRING_FORWARD_INSTANT - timedelta(minutes=30)  # 01:30 EST
    after = SPRING_FORWARD_INSTANT + timedelta(minutes=30)  # 03:30 EDT

    report = _report(
        [
            _visit("before", at=before, confirmed=NORTHERN_CARDINAL),
            _visit("after", at=after, confirmed=HOUSE_FINCH),
        ],
        period_start_at=SPRING_FORWARD_INSTANT - timedelta(hours=2),
        period_end_at=SPRING_FORWARD_INSTANT + timedelta(hours=2),
        local_timezone=NY,
    )

    by_hour = {entry.hour: entry.wildlife_visit_count for entry in report.activity_by_hour}
    assert by_hour[1] == 1  # the EST Visit, correctly not shifted to EDT
    assert by_hour[3] == 1  # the EDT Visit, correctly not shifted to EST
    assert by_hour[2] == 0  # the hour that never happened locally that day


def test_us_fall_back_transition_maps_two_instants_to_the_repeated_local_hour() -> None:
    """The defining fall-back case: two genuinely different UTC instants,
    one before and one after the actual transition, both land in local
    hour 1 -- the hour that happens twice. A fixed offset resolved from
    only one of the two would misplace the other by a full hour."""

    first_1am = FALL_BACK_INSTANT - timedelta(minutes=30)  # 01:30 EDT (first occurrence)
    second_1am = FALL_BACK_INSTANT + timedelta(minutes=30)  # 01:30 EST (second occurrence)

    report = _report(
        [
            _visit("first-1am", at=first_1am, confirmed=NORTHERN_CARDINAL),
            _visit("second-1am", at=second_1am, confirmed=HOUSE_FINCH),
        ],
        period_start_at=FALL_BACK_INSTANT - timedelta(hours=2),
        period_end_at=FALL_BACK_INSTANT + timedelta(hours=2),
        local_timezone=NY,
    )

    by_hour = {entry.hour: entry.wildlife_visit_count for entry in report.activity_by_hour}
    # Both real, distinct Visits count -- neither is dropped nor merged --
    # they simply share one local-hour bucket, honestly reflecting that the
    # local calendar itself repeats this hour once a year.
    assert by_hour[1] == 2
    assert report.total_visit_count == 2


def test_report_period_spanning_the_spring_forward_transition() -> None:
    """A period whose own boundaries straddle the transition (not just a
    Visit timestamp within an unrelated period) -- the realistic "this
    week" report shape. Every Visit across the two days must bucket by its
    own historically-correct offset."""

    period_start = SPRING_FORWARD_INSTANT - timedelta(days=1)
    period_end = SPRING_FORWARD_INSTANT + timedelta(days=1)
    day_before = SPRING_FORWARD_INSTANT - timedelta(hours=20)  # previous day, deep in EST
    just_after = SPRING_FORWARD_INSTANT + timedelta(minutes=30)  # EDT, right after the jump

    report = _report(
        [
            _visit("day-before", at=day_before, confirmed=NORTHERN_CARDINAL),
            _visit("just-after", at=just_after, confirmed=HOUSE_FINCH),
        ],
        period_start_at=period_start,
        period_end_at=period_end,
        local_timezone=NY,
    )

    assert report.total_visit_count == 2
    by_hour = {entry.hour: entry.wildlife_visit_count for entry in report.activity_by_hour}
    # day_before = SPRING_FORWARD_INSTANT - 20h = 2026-03-07T11:00:00Z = 06:00 EST.
    assert by_hour[6] == 1
    # just_after = SPRING_FORWARD_INSTANT + 30m = 2026-03-08T07:30:00Z = 03:30 EDT.
    assert by_hour[3] == 1
