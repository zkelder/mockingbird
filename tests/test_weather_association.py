"""Pure computation tests for mockingbird.analytics.weather_association.

No repository, no database -- matches the existing
test_habitat_association.py precedent for a pure sibling module. See
docs/environmental-context-v2-contract.md "Phase 6/7" for the product
contract these bounded, association-only weather comparisons must honor
(association language only, never causal).
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from mockingbird.analytics.conditional_association import (
    DEFAULT_MIN_RATE_DIFFERENCE,
    DEFAULT_MIN_USABLE_DAYS_IN_CONDITION,
    DEFAULT_MIN_USABLE_DAYS_OUT_OF_CONDITION,
)
from mockingbird.analytics.place_activity_report import TaxonFact, VisitFact
from mockingbird.analytics.weather_association import (
    MIN_CONDITION_DAYS_FOR_ATTEMPT,
    compute_weather_associations,
)

CARDINAL = TaxonFact("northern_cardinal", "Northern Cardinal", "bird", True)
FINCH = TaxonFact("house_finch", "House Finch", "bird", True)

BASE = date(2026, 1, 1)

assert MIN_CONDITION_DAYS_FOR_ATTEMPT == 5
assert DEFAULT_MIN_USABLE_DAYS_IN_CONDITION == DEFAULT_MIN_USABLE_DAYS_OUT_OF_CONDITION == 5
assert DEFAULT_MIN_RATE_DIFFERENCE == 0.25


def _dates(start: date, count: int) -> set[date]:
    return {start + timedelta(days=offset) for offset in range(count)}


def _visit(visit_id: str, *, at: datetime, taxon: TaxonFact | None) -> VisitFact:
    return VisitFact(
        visit_id=visit_id, zone_id=None, zone_name=None, activity_started_at=at,
        resolution="reviewed", confirmed_taxon=taxon,
    )


def _visits_on_dates(taxon: TaxonFact, dates: set[date], *, prefix: str) -> list[VisitFact]:
    return [
        _visit(f"{prefix}-{day.isoformat()}", at=datetime(day.year, day.month, day.day, 12, tzinfo=UTC), taxon=taxon)
        for day in dates
    ]


def test_more_common_on_cooler_days_yields_one_association() -> None:
    usable = _dates(BASE, 20)
    cooler_days = _dates(BASE, 10)
    temperature_bands = {day: ("cooler_than_typical" if day in cooler_days else "typical") for day in usable}
    presence = _dates(BASE, 8) | _dates(BASE + timedelta(days=10), 2)  # 8/10 cooler, 2/10 not
    visits = _visits_on_dates(CARDINAL, presence, prefix="v")

    results = compute_weather_associations(
        visits, taxa={CARDINAL.label: CARDINAL}, usable_dates=usable, local_timezone=UTC,
        temperature_bands=temperature_bands, precipitation_bands={},
    )

    [cooler_result] = [r for r in results if r.condition == "cooler_than_typical"]
    assert cooler_result.taxon == CARDINAL
    assert cooler_result.condition_label == "cooler days"
    assert cooler_result.association.status == "more_common_under_condition"
    assert cooler_result.association.presence_days_in_condition == 8
    assert cooler_result.association.usable_days_in_condition == 10
    assert cooler_result.association.presence_days_out_of_condition == 2
    assert cooler_result.association.usable_days_out_of_condition == 10
    # No warmer_than_typical days exist in this fixture -- that condition
    # must simply be absent, never a fabricated empty-set comparison.
    assert not any(r.condition == "warmer_than_typical" for r in results)


def test_wet_vs_dry_axis_is_independent_of_temperature_axis() -> None:
    usable = _dates(BASE, 20)
    wet_days = _dates(BASE, 10)
    precipitation_bands = {day: ("wet_day" if day in wet_days else "dry_day") for day in usable}
    presence = _dates(BASE, 2) | _dates(BASE + timedelta(days=10), 8)  # more common when dry
    visits = _visits_on_dates(FINCH, presence, prefix="v")

    results = compute_weather_associations(
        visits, taxa={FINCH.label: FINCH}, usable_dates=usable, local_timezone=UTC,
        temperature_bands={}, precipitation_bands=precipitation_bands,
    )

    [wet_result] = results
    assert wet_result.condition == "wet_day"
    assert wet_result.condition_label == "wet periods"
    assert wet_result.association.status == "less_common_under_condition"


def test_a_date_missing_from_the_band_mapping_is_excluded_not_folded_into_out_of_condition() -> None:
    """A date with no environmental coverage at all must never silently
    count as "not cooler" -- see docs/environmental-context-v2-contract.md
    "Phase 8"."""

    usable = _dates(BASE, 20)
    covered_dates = _dates(BASE, 15)  # only 15 of the 20 usable dates have any weather data at all
    cooler_days = _dates(BASE, 10)
    temperature_bands = {
        day: ("cooler_than_typical" if day in cooler_days else "typical") for day in covered_dates
    }
    # Presence concentrated on the 5 uncovered dates -- if they were wrongly
    # folded into "out of condition", this would look like a strong
    # less-common-under-condition signal; correctly excluded, only 15 usable
    # dates remain for this axis (10 in, 5 out), both still >= the floor.
    presence = _dates(BASE + timedelta(days=15), 5)
    visits = _visits_on_dates(CARDINAL, presence, prefix="v")

    results = compute_weather_associations(
        visits, taxa={CARDINAL.label: CARDINAL}, usable_dates=usable, local_timezone=UTC,
        temperature_bands=temperature_bands, precipitation_bands={},
    )

    cooler_result = next(r for r in results if r.condition == "cooler_than_typical")
    assert cooler_result.association.usable_days_in_condition == 10
    assert cooler_result.association.usable_days_out_of_condition == 5
    assert cooler_result.association.presence_days_in_condition == 0
    assert cooler_result.association.presence_days_out_of_condition == 0


def test_too_few_condition_days_contributes_zero_entries() -> None:
    usable = _dates(BASE, 20)
    # Only 3 cooler days -- below MIN_CONDITION_DAYS_FOR_ATTEMPT (5).
    cooler_days = _dates(BASE, 3)
    temperature_bands = {day: ("cooler_than_typical" if day in cooler_days else "typical") for day in usable}
    visits = _visits_on_dates(CARDINAL, usable, prefix="v")  # present every day

    results = compute_weather_associations(
        visits, taxa={CARDINAL.label: CARDINAL}, usable_dates=usable, local_timezone=UTC,
        temperature_bands=temperature_bands, precipitation_bands={},
    )

    assert not any(r.condition == "cooler_than_typical" for r in results)


def test_taxon_with_zero_presence_contributes_no_entry() -> None:
    usable = _dates(BASE, 20)
    temperature_bands = {day: ("cooler_than_typical" if i < 10 else "typical") for i, day in enumerate(sorted(usable))}

    results = compute_weather_associations(
        [], taxa={CARDINAL.label: CARDINAL}, usable_dates=usable, local_timezone=UTC,
        temperature_bands=temperature_bands, precipitation_bands={},
    )

    assert results == []


def test_both_mappings_empty_returns_empty_list() -> None:
    usable = _dates(BASE, 20)
    visits = _visits_on_dates(CARDINAL, _dates(BASE, 10), prefix="v")

    results = compute_weather_associations(
        visits, taxa={CARDINAL.label: CARDINAL}, usable_dates=usable, local_timezone=UTC,
        temperature_bands={}, precipitation_bands={},
    )

    assert results == []


def test_multiple_taxa_evaluated_independently() -> None:
    usable = _dates(BASE, 20)
    cooler_days = _dates(BASE, 10)
    temperature_bands = {day: ("cooler_than_typical" if day in cooler_days else "typical") for day in usable}
    cardinal_visits = _visits_on_dates(CARDINAL, cooler_days, prefix="c")  # only on cooler days
    finch_visits = _visits_on_dates(FINCH, usable - cooler_days, prefix="f")  # only on typical days

    results = compute_weather_associations(
        cardinal_visits + finch_visits, taxa={CARDINAL.label: CARDINAL, FINCH.label: FINCH},
        usable_dates=usable, local_timezone=UTC,
        temperature_bands=temperature_bands, precipitation_bands={},
    )

    by_taxon = {(r.taxon.label, r.condition): r for r in results}
    assert by_taxon[(CARDINAL.label, "cooler_than_typical")].association.status == "more_common_under_condition"
    assert by_taxon[(FINCH.label, "cooler_than_typical")].association.status == "less_common_under_condition"


def test_deterministic_for_identical_inputs() -> None:
    usable = _dates(BASE, 20)
    temperature_bands = {day: ("cooler_than_typical" if i < 10 else "typical") for i, day in enumerate(sorted(usable))}
    visits = _visits_on_dates(CARDINAL, _dates(BASE, 8), prefix="v")

    def _run():
        return compute_weather_associations(
            list(visits), taxa={CARDINAL.label: CARDINAL}, usable_dates=set(usable), local_timezone=UTC,
            temperature_bands=dict(temperature_bands), precipitation_bands={},
        )

    assert _run() == _run()


def test_condition_labels_never_claim_a_time_of_day() -> None:
    """These bands classify whole calendar days, not a specific hour -- the
    label must say so honestly (see the module's own docstring for why it
    deliberately departs from the governing brief's "cooler mornings"
    phrasing)."""

    usable = _dates(BASE, 20)
    temperature_bands = {day: ("cooler_than_typical" if i < 10 else "warmer_than_typical") for i, day in enumerate(sorted(usable))}
    precipitation_bands = {day: ("wet_day" if i < 10 else "dry_day") for i, day in enumerate(sorted(usable))}
    visits = _visits_on_dates(CARDINAL, _dates(BASE, 8), prefix="v")

    results = compute_weather_associations(
        visits, taxa={CARDINAL.label: CARDINAL}, usable_dates=usable, local_timezone=UTC,
        temperature_bands=temperature_bands, precipitation_bands=precipitation_bands,
    )
    for result in results:
        for word in ("morning", "afternoon", "evening", "night"):
            assert word not in result.condition_label.lower()
