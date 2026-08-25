"""Pure computation tests for mockingbird.analytics.temporal_pattern.

No repository, no database -- matches the existing test_historical_baseline.py
precedent for this package's pure sibling modules. See
src/mockingbird/analytics/temporal_pattern.py's own module docstring for the
product context (a plain-language time-of-day band, a day/night daylight
association, and a single-Visit "was this timing typical for this taxon
here" comparison).
"""

from __future__ import annotations

import random
from datetime import UTC, datetime

import pytest

from mockingbird.analytics.place_activity_report import (
    MIN_REVIEWED_VISITS_FOR_MOST_ACTIVE_PATTERN,
    TaxonFact,
    VisitFact,
)
from mockingbird.analytics.temporal_pattern import (
    DaylightAssociation,
    TaxonTemporalPattern,
    TimeOfDayBand,
    compare_visit_timing,
    compute_taxon_temporal_patterns,
    time_of_day_band,
)

# Taxon fixtures mirror the exact label/category/is_species combinations
# used by the sibling place_activity_report / historical_baseline test
# files, without depending on them.
NORTHERN_CARDINAL = TaxonFact("northern_cardinal", "Northern Cardinal", "bird", True)
HOUSE_FINCH = TaxonFact("house_finch", "House Finch", "bird", True)


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


def _pattern(
    *,
    most_active_hour: int | None,
    hour_counts: tuple[tuple[int, int], ...] | None = None,
    reviewed_visit_count: int = 0,
    taxon: TaxonFact = NORTHERN_CARDINAL,
    dominant_band: TimeOfDayBand | None = None,
    day_count: int = 0,
    night_count: int = 0,
    unknown_daylight_count: int = 0,
    daylight_association: DaylightAssociation = "insufficient_data",
) -> TaxonTemporalPattern:
    """Build a `TaxonTemporalPattern` directly, for `compare_visit_timing`
    tests that need precise control over `most_active_hour`/`hour_counts`
    independent of `compute_taxon_temporal_patterns`'s own aggregation."""

    if hour_counts is None:
        hour_counts = tuple((hour, 0) for hour in range(24))
    return TaxonTemporalPattern(
        taxon=taxon,
        reviewed_visit_count=reviewed_visit_count,
        day_count=day_count,
        night_count=night_count,
        unknown_daylight_count=unknown_daylight_count,
        daylight_association=daylight_association,
        hour_counts=hour_counts,
        dominant_band=dominant_band,
        most_active_hour=most_active_hour,
    )


# ---------------------------------------------------------------------------
# time_of_day_band
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "local_hour,expected_band",
    [
        (4, "night"),
        (5, "early_morning"),
        (7, "early_morning"),
        (8, "morning"),
        (10, "morning"),
        (11, "midday"),
        (13, "midday"),
        (14, "afternoon"),
        (16, "afternoon"),
        (17, "evening"),
        (19, "evening"),
        (20, "night"),
        (23, "night"),
        (0, "night"),
        (3, "night"),
    ],
)
def test_time_of_day_band_boundaries(local_hour: int, expected_band: str) -> None:
    assert time_of_day_band(local_hour) == expected_band


@pytest.mark.parametrize("local_hour", [-1, 24])
def test_time_of_day_band_rejects_out_of_range_hour(local_hour: int) -> None:
    with pytest.raises(ValueError):
        time_of_day_band(local_hour)


# ---------------------------------------------------------------------------
# compute_taxon_temporal_patterns
# ---------------------------------------------------------------------------


def test_below_minimum_reviewed_visits_withholds_only_the_derived_most_active_claim() -> None:
    """Fewer than MIN_REVIEWED_VISITS_FOR_MOST_ACTIVE_PATTERN reviewed
    Visits for a taxon must still report honest raw counts -- only the
    "most active" derived claim is withheld."""

    assert MIN_REVIEWED_VISITS_FOR_MOST_ACTIVE_PATTERN == 5
    hours = [9, 9, 14, 20]  # 4 visits -- one short of the minimum
    visits = [
        _visit(f"v{i}", at=datetime(2026, 8, 10, hour, tzinfo=UTC), confirmed=NORTHERN_CARDINAL)
        for i, hour in enumerate(hours)
    ]
    daylight = {"v0": "day", "v1": "day", "v2": "night"}  # "v3" deliberately absent
    patterns = compute_taxon_temporal_patterns(visits, daylight_by_visit_id=daylight, local_timezone=UTC)
    pattern = patterns["northern_cardinal"]

    assert pattern.dominant_band is None
    assert pattern.most_active_hour is None
    assert pattern.reviewed_visit_count == 4
    assert pattern.day_count == 2
    assert pattern.night_count == 1
    assert pattern.unknown_daylight_count == 1
    assert len(pattern.hour_counts) == 24
    expected_hour_counts = {hour: 0 for hour in range(24)}
    expected_hour_counts[9] = 2
    expected_hour_counts[14] = 1
    expected_hour_counts[20] = 1
    assert dict(pattern.hour_counts) == expected_hour_counts


def test_at_minimum_reviewed_visits_computes_most_active_hour_and_dominant_band() -> None:
    """Exactly 5 visits (the minimum): hour 9 has the single highest
    per-hour count (2), but hours 14/15/16 together (the afternoon band)
    outweigh it (3 total) -- proving `dominant_band` is a true per-band
    aggregate, not simply "the band containing most_active_hour."""

    hours = [9, 9, 14, 15, 16]
    visits = [
        _visit(f"v{i}", at=datetime(2026, 8, 10, hour, tzinfo=UTC), confirmed=NORTHERN_CARDINAL)
        for i, hour in enumerate(hours)
    ]
    patterns = compute_taxon_temporal_patterns(visits, daylight_by_visit_id={}, local_timezone=UTC)
    pattern = patterns["northern_cardinal"]

    assert pattern.reviewed_visit_count == 5
    assert pattern.most_active_hour == 9
    assert pattern.dominant_band == "afternoon"


def test_hour_counts_always_reports_all_24_hours_including_zero_counts() -> None:
    visits = [_visit("v0", at=datetime(2026, 8, 10, 6, tzinfo=UTC), confirmed=NORTHERN_CARDINAL)]
    patterns = compute_taxon_temporal_patterns(visits, daylight_by_visit_id={}, local_timezone=UTC)
    pattern = patterns["northern_cardinal"]

    assert [hour for hour, _ in pattern.hour_counts] == list(range(24))
    assert dict(pattern.hour_counts)[6] == 1
    assert dict(pattern.hour_counts)[0] == 0  # a genuinely zero hour is still present, not omitted


def test_daylight_buckets_split_correctly_and_absence_means_unknown_not_a_guess() -> None:
    visits = [
        _visit("day-visit", at=datetime(2026, 8, 10, 9, tzinfo=UTC), confirmed=NORTHERN_CARDINAL),
        _visit("night-visit", at=datetime(2026, 8, 10, 22, tzinfo=UTC), confirmed=NORTHERN_CARDINAL),
        _visit("unknown-visit", at=datetime(2026, 8, 10, 12, tzinfo=UTC), confirmed=NORTHERN_CARDINAL),
    ]
    daylight = {"day-visit": "day", "night-visit": "night"}  # "unknown-visit" absent entirely
    patterns = compute_taxon_temporal_patterns(visits, daylight_by_visit_id=daylight, local_timezone=UTC)
    pattern = patterns["northern_cardinal"]

    assert pattern.day_count == 1
    assert pattern.night_count == 1
    assert pattern.unknown_daylight_count == 1
    assert pattern.reviewed_visit_count == 3


def _daylight_split_pattern(day_count: int, night_count: int) -> TaxonTemporalPattern:
    """Build `day_count` + `night_count` confirmed Visits (all at arbitrary,
    irrelevant hours) split precisely between the "day" and "night"
    buckets, for exercising `daylight_association`'s thresholds."""

    visits = []
    daylight: dict[str, str] = {}
    for i in range(day_count):
        visit_id = f"day-{i}"
        visits.append(_visit(visit_id, at=datetime(2026, 8, 10, 9, tzinfo=UTC), confirmed=NORTHERN_CARDINAL))
        daylight[visit_id] = "day"
    for i in range(night_count):
        visit_id = f"night-{i}"
        visits.append(_visit(visit_id, at=datetime(2026, 8, 10, 22, tzinfo=UTC), confirmed=NORTHERN_CARDINAL))
        daylight[visit_id] = "night"
    patterns = compute_taxon_temporal_patterns(visits, daylight_by_visit_id=daylight, local_timezone=UTC)
    return patterns["northern_cardinal"]


def test_daylight_association_insufficient_data_when_all_daylight_is_unknown() -> None:
    visits = [_visit("v0", at=datetime(2026, 8, 10, 9, tzinfo=UTC), confirmed=NORTHERN_CARDINAL)]
    patterns = compute_taxon_temporal_patterns(visits, daylight_by_visit_id={}, local_timezone=UTC)
    assert patterns["northern_cardinal"].daylight_association == "insufficient_data"


def test_daylight_association_mostly_daytime_at_the_dominance_threshold() -> None:
    pattern = _daylight_split_pattern(day_count=3, night_count=1)  # day fraction == 0.75 exactly
    assert pattern.daylight_association == "mostly_daytime"


def test_daylight_association_mostly_nighttime_at_the_dominance_threshold() -> None:
    pattern = _daylight_split_pattern(day_count=1, night_count=3)  # night fraction == 0.75 exactly
    assert pattern.daylight_association == "mostly_nighttime"


def test_daylight_association_spans_day_and_night_for_a_60_40_split() -> None:
    pattern = _daylight_split_pattern(day_count=3, night_count=2)  # 0.6 / 0.4 -- neither dominant
    assert pattern.daylight_association == "spans_day_and_night"


def test_visit_with_unresolved_confirmed_taxon_contributes_to_no_pattern() -> None:
    visits = [
        _visit("bad-label", at=datetime(2026, 8, 10, 9, tzinfo=UTC), confirmed=None),
        _visit("real", at=datetime(2026, 8, 10, 10, tzinfo=UTC), confirmed=NORTHERN_CARDINAL),
    ]
    patterns = compute_taxon_temporal_patterns(visits, daylight_by_visit_id={}, local_timezone=UTC)

    assert list(patterns.keys()) == ["northern_cardinal"]
    assert patterns["northern_cardinal"].reviewed_visit_count == 1


def test_two_taxa_in_the_same_visits_get_independent_patterns() -> None:
    cardinal_visits = [
        _visit(f"cardinal-{i}", at=datetime(2026, 8, 10, hour, tzinfo=UTC), confirmed=NORTHERN_CARDINAL)
        for i, hour in enumerate([6, 6, 6, 7, 7])
    ]
    finch_visits = [
        _visit(f"finch-{i}", at=datetime(2026, 8, 10, hour, tzinfo=UTC), confirmed=HOUSE_FINCH)
        for i, hour in enumerate([18, 18, 19, 19, 19])
    ]
    patterns = compute_taxon_temporal_patterns(
        cardinal_visits + finch_visits, daylight_by_visit_id={}, local_timezone=UTC
    )

    assert set(patterns.keys()) == {"northern_cardinal", "house_finch"}
    cardinal = patterns["northern_cardinal"]
    finch = patterns["house_finch"]
    assert cardinal.reviewed_visit_count == 5
    assert finch.reviewed_visit_count == 5
    assert cardinal.most_active_hour == 6
    assert finch.most_active_hour == 19
    assert cardinal.dominant_band == "early_morning"
    assert finch.dominant_band == "evening"
    assert dict(cardinal.hour_counts)[18] == 0  # no cross-contamination from the finch's hours
    assert dict(finch.hour_counts)[6] == 0


def test_taxon_appearing_only_as_a_provisional_suggestion_never_becomes_a_key() -> None:
    """Unlike `seasonal_pattern`'s `compute_taxon_seasonal_patterns` (which
    takes a `taxa` map and pre-seeds every key), `compute_taxon_temporal_
    patterns` has no such parameter -- confirmed by its signature, which
    takes only `visits`, `daylight_by_visit_id`, and `local_timezone`. A
    taxon with zero *confirmed* Visits simply never appears in the result,
    even when it is present in `visits` as a provisional suggestion on an
    unreviewed Visit."""

    visits = [
        _visit(
            "needs-review",
            at=datetime(2026, 8, 10, 9, tzinfo=UTC),
            resolution="needs_review",
            confirmed=None,
            provisional=HOUSE_FINCH,
        ),
        _visit("real", at=datetime(2026, 8, 10, 10, tzinfo=UTC), confirmed=NORTHERN_CARDINAL),
    ]
    patterns = compute_taxon_temporal_patterns(visits, daylight_by_visit_id={}, local_timezone=UTC)

    assert list(patterns.keys()) == ["northern_cardinal"]
    assert "house_finch" not in patterns


def test_deterministic_for_identical_inputs() -> None:
    visits = [
        _visit(f"cardinal-{i}", at=datetime(2026, 8, 10, hour, tzinfo=UTC), confirmed=NORTHERN_CARDINAL)
        for i, hour in enumerate([6, 6, 6, 7, 7])
    ] + [
        _visit(f"finch-{i}", at=datetime(2026, 8, 10, hour, tzinfo=UTC), confirmed=HOUSE_FINCH)
        for i, hour in enumerate([18, 19])
    ]
    daylight = {"cardinal-0": "day", "cardinal-1": "night"}

    first = compute_taxon_temporal_patterns(visits, daylight_by_visit_id=daylight, local_timezone=UTC)
    second = compute_taxon_temporal_patterns(visits, daylight_by_visit_id=dict(daylight), local_timezone=UTC)

    assert first == second


def test_deterministic_regardless_of_visit_order() -> None:
    visits = [
        _visit(f"cardinal-{i}", at=datetime(2026, 8, 10, hour, tzinfo=UTC), confirmed=NORTHERN_CARDINAL)
        for i, hour in enumerate([6, 6, 6, 7, 7])
    ] + [
        _visit(f"finch-{i}", at=datetime(2026, 8, 10, hour, tzinfo=UTC), confirmed=HOUSE_FINCH)
        for i, hour in enumerate([18, 19])
    ]
    baseline = compute_taxon_temporal_patterns(visits, daylight_by_visit_id={}, local_timezone=UTC)

    rng = random.Random(99)
    for _ in range(5):
        shuffled = list(visits)
        rng.shuffle(shuffled)
        assert compute_taxon_temporal_patterns(shuffled, daylight_by_visit_id={}, local_timezone=UTC) == baseline


# ---------------------------------------------------------------------------
# compare_visit_timing
# ---------------------------------------------------------------------------


def test_insufficient_data_when_pattern_has_no_most_active_hour() -> None:
    pattern = _pattern(most_active_hour=None, reviewed_visit_count=2)
    assert compare_visit_timing(10, pattern) == "insufficient_data"


@pytest.mark.parametrize(
    "most_active_hour,queried_hour",
    [
        (10, 13),  # +3 hours, exactly at the tolerance boundary
        (10, 7),  # -3 hours, exactly at the tolerance boundary
        (23, 1),  # midnight wraparound: raw distance 22, wrapped distance 2
    ],
)
def test_typical_within_tolerance_of_most_active_hour(most_active_hour: int, queried_hour: int) -> None:
    """Hour counts are concentrated entirely at `most_active_hour`, so the
    90%-coverage set contains only that one hour -- isolating the
    tolerance rule as the sole reason a nearby-but-uncovered hour still
    reads "typical"."""

    hour_counts = tuple((hour, 10 if hour == most_active_hour else 0) for hour in range(24))
    pattern = _pattern(most_active_hour=most_active_hour, hour_counts=hour_counts, reviewed_visit_count=10)
    assert compare_visit_timing(queried_hour, pattern) == "typical"


def test_unusual_when_far_from_most_active_hour_and_outside_the_90_percent_band() -> None:
    """Activity concentrated in an 8-10 band only (3 visits at 8, 5 at 9, 2
    at 10 -- the smallest set covering 90% of the 10 reviewed Visits is
    exactly {8, 9, 10}); hour 20 is both outside the +/-3 tolerance window
    around most_active_hour (9) and outside that band."""

    hour_counts = tuple((hour, {8: 3, 9: 5, 10: 2}.get(hour, 0)) for hour in range(24))
    pattern = _pattern(most_active_hour=9, hour_counts=hour_counts, reviewed_visit_count=10)
    assert compare_visit_timing(20, pattern) == "unusual"


@pytest.mark.parametrize("local_hour", [-1, 24])
def test_compare_visit_timing_rejects_out_of_range_hour(local_hour: int) -> None:
    pattern = _pattern(most_active_hour=9, hour_counts=None, reviewed_visit_count=10)
    with pytest.raises(ValueError):
        compare_visit_timing(local_hour, pattern)
