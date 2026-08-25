"""Pure computation tests for mockingbird.analytics.source_activity.

No repository, no database -- matches the existing test_place_activity_
report.py / test_historical_baseline.py precedent for a pure sibling
module. See docs/place-yard-intelligence-v2-contract.md for the product
contract these tests enforce.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from mockingbird.analytics.place_activity_report import TaxonFact, VisitFact
from mockingbird.analytics.source_activity import (
    DEFAULT_MIN_CANDIDATES_ATTEMPTED_FOR_YIELD_SIGNAL,
    DEFAULT_YIELD_RATIO_THRESHOLD,
    MIN_MONITORED_HOURS_FOR_RATE,
    MIN_QUALIFYING_SOURCES_FOR_COMPARISON,
    SourceActivityEntry,
    SourceAuthorityCounters,
    SourceCoverageFact,
    SourceQualitySignal,
    compute_source_activity,
    compute_source_quality_signals,
)

NORTHERN_CARDINAL = TaxonFact("northern_cardinal", "Northern Cardinal", "bird", True)
FALSE_POSITIVE = TaxonFact("false_positive", "False Positive", "false_positive", False)

AT = datetime(2026, 8, 21, 12, tzinfo=UTC)


def _visit(
    visit_id: str,
    *,
    at: datetime = AT,
    source_id: str | None = None,
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
        source_id=source_id,
        source_name=None,
    )


def _confirmed_visits(prefix: str, count: int, *, source_id: str) -> list[VisitFact]:
    """`count` distinct confirmed-wildlife Visits for one Source."""

    return [
        _visit(
            f"{prefix}-{i}",
            at=AT + timedelta(minutes=i),
            source_id=source_id,
            confirmed=NORTHERN_CARDINAL,
        )
        for i in range(count)
    ]


def _coverage(source_id: str, source_name: str, monitored_seconds: float | None) -> SourceCoverageFact:
    return SourceCoverageFact(source_id=source_id, source_name=source_name, monitored_seconds=monitored_seconds)


def _counters(
    source_id: str,
    source_name: str,
    *,
    attempted: int,
    created: int,
    suppressed: int = 0,
) -> SourceAuthorityCounters:
    return SourceAuthorityCounters(
        source_id=source_id,
        source_name=source_name,
        candidates_attempted_count=attempted,
        candidates_created_count=created,
        suppressed_count=suppressed,
    )


def _entry_for(entries: list[SourceActivityEntry], source_id: str) -> SourceActivityEntry:
    [entry] = [entry for entry in entries if entry.source_id == source_id]
    return entry


def _signal_for(signals: list[SourceQualitySignal], source_id: str) -> SourceQualitySignal:
    [signal] = [signal for signal in signals if signal.source_id == source_id]
    return signal


# ---------------------------------------------------------------------------
# compute_source_activity
# ---------------------------------------------------------------------------


def test_two_sufficient_sources_get_correct_rates_and_sort_by_rate_descending() -> None:
    """Different confirmed counts and different monitored hours (both
    >= MIN_MONITORED_HOURS_FOR_RATE) -> both data_sufficient, correct
    count/hours rate rounded to 4 decimals, sorted by rate descending."""

    coverage = {
        "cam_forest": _coverage("cam_forest", "Forest Cam", 3 * 3600.0),  # 3h, 5 visits -> 1.6667/h
        "cam_yard": _coverage("cam_yard", "Yard Cam", 2 * 3600.0),  # 2h, 3 visits -> 1.5/h
    }
    visits = _confirmed_visits("forest", 5, source_id="cam_forest") + _confirmed_visits(
        "yard", 3, source_id="cam_yard"
    )

    entries = compute_source_activity(visits, coverage_by_source=coverage)

    assert [entry.source_id for entry in entries] == ["cam_forest", "cam_yard"]

    forest = _entry_for(entries, "cam_forest")
    assert forest.data_sufficient is True
    assert forest.confirmed_wildlife_visit_count == 5
    assert forest.monitored_seconds == 3 * 3600.0
    assert forest.visits_per_monitored_hour == pytest.approx(round(5 / 3, 4))

    yard = _entry_for(entries, "cam_yard")
    assert yard.data_sufficient is True
    assert yard.confirmed_wildlife_visit_count == 3
    assert yard.visits_per_monitored_hour == pytest.approx(1.5)


def test_insufficient_coverage_sorts_after_sufficient_regardless_of_raw_count() -> None:
    """A Source with < MIN_MONITORED_HOURS_FOR_RATE of monitored seconds is
    data_sufficient=False with visits_per_monitored_hour=None, and always
    sorts after every sufficient entry -- even one with a much higher raw
    confirmed count."""

    insufficient_hours = MIN_MONITORED_HOURS_FOR_RATE - 1.0
    sufficient_hours = MIN_MONITORED_HOURS_FOR_RATE + 1.0

    coverage = {
        "cam_attic": _coverage("cam_attic", "Attic Cam", insufficient_hours * 3600.0),
        "cam_porch": _coverage("cam_porch", "Porch Cam", sufficient_hours * 3600.0),
    }
    # The insufficient Source has a far higher raw confirmed count.
    visits = _confirmed_visits("attic", 50, source_id="cam_attic") + _confirmed_visits(
        "porch", 1, source_id="cam_porch"
    )

    entries = compute_source_activity(visits, coverage_by_source=coverage)

    assert [entry.source_id for entry in entries] == ["cam_porch", "cam_attic"]

    attic = _entry_for(entries, "cam_attic")
    assert attic.confirmed_wildlife_visit_count == 50
    assert attic.data_sufficient is False
    assert attic.visits_per_monitored_hour is None

    porch = _entry_for(entries, "cam_porch")
    assert porch.data_sufficient is True
    assert porch.visits_per_monitored_hour == pytest.approx(round(1 / sufficient_hours, 4))


def test_no_durable_exposure_history_is_data_insufficient_and_seconds_stays_none() -> None:
    """monitored_seconds=None (no durable exposure history at all) ->
    data_sufficient=False, visits_per_monitored_hour is None, and
    monitored_seconds is never coerced to 0 in the output."""

    coverage = {"cam_new": _coverage("cam_new", "New Cam", None)}
    visits = _confirmed_visits("new", 2, source_id="cam_new")

    [entry] = compute_source_activity(visits, coverage_by_source=coverage)

    assert entry.confirmed_wildlife_visit_count == 2
    assert entry.data_sufficient is False
    assert entry.visits_per_monitored_hour is None
    assert entry.monitored_seconds is None


def test_only_confirmed_wildlife_visits_count_toward_the_confirmed_count() -> None:
    """A needs_review (provisional-only) Visit and a reviewed
    false_positive-category Visit must not contribute to
    confirmed_wildlife_visit_count -- only genuinely CONFIRMED_WILDLIFE
    Visits (see _classify) do."""

    coverage = {"cam_deck": _coverage("cam_deck", "Deck Cam", 3 * 3600.0)}
    visits = [
        _visit("confirmed-1", source_id="cam_deck", confirmed=NORTHERN_CARDINAL),
        _visit("confirmed-2", source_id="cam_deck", confirmed=NORTHERN_CARDINAL),
        # Provisional-only: no reviewed truth yet.
        _visit("provisional-only", source_id="cam_deck", resolution="needs_review", provisional=NORTHERN_CARDINAL),
        # Reviewed, but explicitly not real activity.
        _visit("false-positive", source_id="cam_deck", confirmed=FALSE_POSITIVE),
    ]

    [entry] = compute_source_activity(visits, coverage_by_source=coverage)

    assert entry.confirmed_wildlife_visit_count == 2


def test_visit_with_unrecognized_source_id_is_silently_ignored() -> None:
    """A Visit whose source_id is not a key of coverage_by_source is
    ignored: no error, does not appear anywhere in the output, and does
    not affect any other Source's count."""

    coverage = {"cam_a": _coverage("cam_a", "Cam A", 3 * 3600.0)}
    visits = _confirmed_visits("a", 1, source_id="cam_a") + _confirmed_visits(
        "ghost", 5, source_id="cam_ghost"
    )

    entries = compute_source_activity(visits, coverage_by_source=coverage)

    assert [entry.source_id for entry in entries] == ["cam_a"]
    assert entries[0].confirmed_wildlife_visit_count == 1


def test_visit_with_source_id_none_is_silently_ignored() -> None:
    """A Visit with source_id=None is ignored the same way as an
    unrecognized source_id -- never a crash, never counted anywhere."""

    coverage = {"cam_a": _coverage("cam_a", "Cam A", 3 * 3600.0)}
    visits = _confirmed_visits("a", 1, source_id="cam_a") + [
        _visit(f"no-source-{i}", source_id=None, confirmed=NORTHERN_CARDINAL) for i in range(3)
    ]

    entries = compute_source_activity(visits, coverage_by_source=coverage)

    assert [entry.source_id for entry in entries] == ["cam_a"]
    assert entries[0].confirmed_wildlife_visit_count == 1


def test_every_coverage_source_appears_exactly_once_even_with_zero_confirmed_visits() -> None:
    """Every Source key present in coverage_by_source appears exactly once
    in the output, even one with zero confirmed Visits -- which still gets
    data_sufficient=True (enough monitored hours) and a real 0.0 rate, not
    None."""

    coverage = {
        "cam_full": _coverage("cam_full", "Full Cam", 3 * 3600.0),
        "cam_quiet": _coverage("cam_quiet", "Quiet Cam", 5 * 3600.0),
    }
    visits = _confirmed_visits("full", 4, source_id="cam_full")  # cam_quiet gets nothing

    entries = compute_source_activity(visits, coverage_by_source=coverage)

    assert {entry.source_id for entry in entries} == {"cam_full", "cam_quiet"}
    assert len(entries) == 2

    quiet = _entry_for(entries, "cam_quiet")
    assert quiet.confirmed_wildlife_visit_count == 0
    assert quiet.data_sufficient is True
    assert quiet.visits_per_monitored_hour == 0.0


def test_deterministic_with_name_as_the_final_tiebreak() -> None:
    """Identical inputs twice give an identical (==) result list. When two
    Sources tie on rate (and raw count), the module's own sort key breaks
    the tie by source_name."""

    coverage = {
        # Inserted in reverse-alphabetical order to prove the final order
        # comes from the sort key, not from dict/input order.
        "cam_zebra": _coverage("cam_zebra", "Zebra Cam", 3 * 3600.0),
        "cam_alpha": _coverage("cam_alpha", "Alpha Cam", 3 * 3600.0),
    }
    visits = _confirmed_visits("zebra", 3, source_id="cam_zebra") + _confirmed_visits(
        "alpha", 3, source_id="cam_alpha"
    )

    result_a = compute_source_activity(visits, coverage_by_source=coverage)
    result_b = compute_source_activity(visits, coverage_by_source=coverage)

    assert result_a == result_b
    assert [entry.source_name for entry in result_a] == ["Alpha Cam", "Zebra Cam"]


# ---------------------------------------------------------------------------
# compute_source_quality_signals
# ---------------------------------------------------------------------------


def test_fewer_than_min_qualifying_sources_yields_insufficient_data_for_all() -> None:
    """Fewer than MIN_QUALIFYING_SOURCES_FOR_COMPARISON Sources meeting
    min_candidates_attempted -> every Source's signal is
    "insufficient_data", even one that individually has plenty of
    attempts: there is nothing to compare it against."""

    counters = [
        _counters("cam_a", "Cam A", attempted=1000, created=100),  # plenty, but alone
        _counters("cam_b", "Cam B", attempted=DEFAULT_MIN_CANDIDATES_ATTEMPTED_FOR_YIELD_SIGNAL - 1, created=3),
    ]
    assert MIN_QUALIFYING_SOURCES_FOR_COMPARISON >= 2  # sanity: this scenario only has 1 qualifier

    results = compute_source_quality_signals(counters)

    assert all(signal.signal == "insufficient_data" for signal in results)
    assert all(signal.place_average_yield_ratio is None for signal in results)


def test_place_average_is_attempted_weighted_not_a_naive_average() -> None:
    """place_average_yield_ratio is sum(created)/sum(attempted) across
    qualifying Sources -- not a naive average of their individual ratios,
    which would badly overweight a low-volume Source."""

    counters = [
        _counters("cam_a", "Cam A", attempted=1000, created=100),  # ratio 0.1
        _counters(
            "cam_b", "Cam B", attempted=DEFAULT_MIN_CANDIDATES_ATTEMPTED_FOR_YIELD_SIGNAL, created=18
        ),  # ratio 0.9
    ]
    naive_average = (100 / 1000 + 18 / DEFAULT_MIN_CANDIDATES_ATTEMPTED_FOR_YIELD_SIGNAL) / 2
    weighted_average = (100 + 18) / (1000 + DEFAULT_MIN_CANDIDATES_ATTEMPTED_FOR_YIELD_SIGNAL)

    results = compute_source_quality_signals(counters)

    for signal in results:
        assert signal.place_average_yield_ratio == pytest.approx(round(weighted_average, 4))
        assert signal.place_average_yield_ratio != pytest.approx(round(naive_average, 4))


def test_source_at_or_below_threshold_fraction_is_flagged_lower_yield() -> None:
    """A Source whose own ratio is <= place_average * yield_ratio_threshold
    is flagged "lower_yield_than_place_average"."""

    counters = [
        _counters("cam_high", "High Cam", attempted=100, created=50),  # ratio 0.5
        _counters("cam_low", "Low Cam", attempted=100, created=10),  # ratio 0.1
    ]
    weighted_average = (50 + 10) / (100 + 100)  # 0.3
    bar = weighted_average * DEFAULT_YIELD_RATIO_THRESHOLD  # 0.15
    assert 0.1 <= bar  # sanity: cam_low's own ratio really is at/under the bar

    results = compute_source_quality_signals(counters)

    assert _signal_for(results, "cam_low").signal == "lower_yield_than_place_average"


def test_source_above_threshold_fraction_is_typical_yield() -> None:
    """A Source whose own ratio is above the threshold fraction of the
    place average is flagged "typical_yield"."""

    counters = [
        _counters("cam_high", "High Cam", attempted=100, created=50),  # ratio 0.5
        _counters("cam_low", "Low Cam", attempted=100, created=10),  # ratio 0.1
    ]
    weighted_average = (50 + 10) / (100 + 100)  # 0.3
    bar = weighted_average * DEFAULT_YIELD_RATIO_THRESHOLD  # 0.15
    assert 0.5 > bar  # sanity: cam_high's own ratio really clears the bar

    results = compute_source_quality_signals(counters)

    assert _signal_for(results, "cam_high").signal == "typical_yield"


def test_source_below_its_own_min_attempted_stays_insufficient_even_when_others_qualify() -> None:
    """A Source below min_candidates_attempted itself keeps
    signal="insufficient_data" even when >= MIN_QUALIFYING_SOURCES_FOR_
    COMPARISON other Sources qualify and a place_average_yield_ratio IS
    computed -- though admission_yield_ratio may still be populated
    because candidates_attempted_count > 0."""

    counters = [
        _counters("cam_high", "High Cam", attempted=100, created=50),  # qualifies
        _counters("cam_low", "Low Cam", attempted=100, created=10),  # qualifies
        _counters(
            "cam_tiny",
            "Tiny Cam",
            attempted=DEFAULT_MIN_CANDIDATES_ATTEMPTED_FOR_YIELD_SIGNAL - 1,
            created=3,
        ),  # below the floor
    ]

    results = compute_source_quality_signals(counters)

    tiny = _signal_for(results, "cam_tiny")
    assert tiny.place_average_yield_ratio is not None  # a comparison value does exist...
    assert tiny.signal == "insufficient_data"  # ...but cam_tiny itself is still unqualified
    assert tiny.admission_yield_ratio == pytest.approx(
        round(3 / (DEFAULT_MIN_CANDIDATES_ATTEMPTED_FOR_YIELD_SIGNAL - 1), 4)
    )


def test_zero_attempted_never_produces_a_fabricated_or_divide_by_zero_ratio() -> None:
    """A Source with candidates_attempted_count == 0 gets
    admission_yield_ratio=None -- never a division-by-zero error, never a
    fabricated ratio."""

    counters = [_counters("cam_zero", "Zero Cam", attempted=0, created=0)]

    [signal] = compute_source_quality_signals(counters)

    assert signal.admission_yield_ratio is None
    assert signal.signal == "insufficient_data"


def test_custom_min_candidates_attempted_changes_which_sources_qualify() -> None:
    """Passing a lower min_candidates_attempted can turn two
    otherwise-unqualified Sources into a qualifying, comparable pair."""

    counters = [
        _counters("cam_a", "Cam A", attempted=15, created=3),  # ratio 0.2
        _counters("cam_b", "Cam B", attempted=15, created=12),  # ratio 0.8
    ]

    default_results = compute_source_quality_signals(counters)
    assert all(signal.signal == "insufficient_data" for signal in default_results)

    custom_results = compute_source_quality_signals(counters, min_candidates_attempted=10)
    assert _signal_for(custom_results, "cam_a").signal == "lower_yield_than_place_average"
    assert _signal_for(custom_results, "cam_b").signal == "typical_yield"


def test_custom_yield_ratio_threshold_changes_which_sources_are_flagged() -> None:
    """Passing a different yield_ratio_threshold moves the bar a Source's
    own ratio is compared against, changing which Sources get flagged."""

    counters = [
        _counters("cam_a", "Cam A", attempted=15, created=3),  # ratio 0.2
        _counters("cam_b", "Cam B", attempted=15, created=12),  # ratio 0.8
    ]

    default_bar_results = compute_source_quality_signals(counters, min_candidates_attempted=10)
    assert _signal_for(default_bar_results, "cam_b").signal == "typical_yield"

    # A much higher threshold raises the bar until even cam_b's 0.8 ratio
    # falls at/under it (weighted average 0.5 * 2.0 == 1.0).
    high_bar_results = compute_source_quality_signals(
        counters, min_candidates_attempted=10, yield_ratio_threshold=2.0
    )
    assert _signal_for(high_bar_results, "cam_a").signal == "lower_yield_than_place_average"
    assert _signal_for(high_bar_results, "cam_b").signal == "lower_yield_than_place_average"


def test_deterministic_and_preserves_input_order() -> None:
    """Identical inputs twice give an identical (==) result list, in the
    same order as the input counters -- the function never resorts."""

    counters = [
        _counters("cam_c", "Cam C", attempted=50, created=10, suppressed=2),
        _counters("cam_a", "Cam A", attempted=200, created=150, suppressed=1),
        _counters("cam_b", "Cam B", attempted=30, created=5, suppressed=0),
    ]

    result_a = compute_source_quality_signals(counters)
    result_b = compute_source_quality_signals(counters)

    assert result_a == result_b
    assert [signal.source_id for signal in result_a] == ["cam_c", "cam_a", "cam_b"]
