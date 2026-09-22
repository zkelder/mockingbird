"""Pure computation tests for mockingbird.analytics.place_biodiversity_summary.

No repository, no database -- matches test_historical_baseline.py's own
precedent for its pure sibling module. See docs/biodiversity-place-
intelligence-v1-contract.md for the product contract these tests enforce.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from mockingbird.analytics.historical_baseline import HistoricalPlaceBaseline, SpeciesHistoricalStatus
from mockingbird.analytics.place_activity_report import TaxonFact
from mockingbird.analytics.place_biodiversity_summary import (
    RECENTLY_OBSERVED_WINDOW_DAYS,
    compute_place_biodiversity_summary,
)

NORTHERN_CARDINAL = TaxonFact("northern_cardinal", "Northern Cardinal", "bird", True)
HOUSE_FINCH = TaxonFact("house_finch", "House Finch", "bird", True)
BLUE_JAY = TaxonFact("blue_jay", "Blue Jay", "bird", True)
SQUIRREL = TaxonFact("squirrel", "Squirrel", "mammal", False)  # kind-level, not species-level (see roadmap gap)

GENERATED_AT = datetime(2026, 8, 24, 12, 0, tzinfo=UTC)


def _status(
    taxon: TaxonFact,
    *,
    status: str,
    last_confirmed_at: datetime,
    first_confirmed_at: datetime | None = None,
    distinct_confirmed_days: int = 1,
    distinct_confirmed_usable_days: int = 1,
    total_confirmed_count: int = 1,
) -> SpeciesHistoricalStatus:
    return SpeciesHistoricalStatus(
        taxon=taxon,
        first_confirmed_at=first_confirmed_at or last_confirmed_at,
        last_confirmed_at=last_confirmed_at,
        distinct_confirmed_days=distinct_confirmed_days,
        distinct_confirmed_usable_days=distinct_confirmed_usable_days,
        total_confirmed_count=total_confirmed_count,
        status=status,  # type: ignore[arg-type]
    )


def _baseline(
    *,
    maturity: str = "established",
    total_monitored_seconds: float | None = 500_000.0,
    distinct_taxa_count: int = 0,
    usable_day_count: int = 10,
) -> HistoricalPlaceBaseline:
    return HistoricalPlaceBaseline(
        window_start_at=GENERATED_AT - timedelta(days=366),
        window_end_at=GENERATED_AT,
        usable_day_count=usable_day_count,
        total_monitored_seconds=total_monitored_seconds,
        maturity=maturity,  # type: ignore[arg-type]
        distinct_taxa_count=distinct_taxa_count,
        earliest_authoritative_record_at=GENERATED_AT - timedelta(days=200),
        latest_authoritative_record_at=GENERATED_AT,
    )


class TestBucketing:
    def test_new_and_first_record_both_land_in_new_taxa(self) -> None:
        new = _status(NORTHERN_CARDINAL, status="new", last_confirmed_at=GENERATED_AT)
        first_record = _status(HOUSE_FINCH, status="first_record", last_confirmed_at=GENERATED_AT)
        summary = compute_place_biodiversity_summary(
            [new, first_record], historical_baseline=_baseline(), generated_at=GENERATED_AT
        )
        assert {status.taxon.label for status in summary.new_taxa} == {"northern_cardinal", "house_finch"}
        assert summary.regular_taxa == ()

    def test_regular_lands_only_in_regular_taxa(self) -> None:
        regular = _status(BLUE_JAY, status="regular", last_confirmed_at=GENERATED_AT)
        summary = compute_place_biodiversity_summary(
            [regular], historical_baseline=_baseline(), generated_at=GENERATED_AT
        )
        assert [s.taxon.label for s in summary.regular_taxa] == ["blue_jay"]
        assert summary.new_taxa == ()

    def test_seen_before_lands_in_neither_new_nor_regular(self) -> None:
        seen_before = _status(HOUSE_FINCH, status="seen_before", last_confirmed_at=GENERATED_AT)
        summary = compute_place_biodiversity_summary(
            [seen_before], historical_baseline=_baseline(), generated_at=GENERATED_AT
        )
        assert summary.new_taxa == ()
        assert summary.regular_taxa == ()
        # But it is never dropped from the full roster -- "seen before" is a
        # real, useful fact, not a reason to hide the taxon.
        assert [s.taxon.label for s in summary.taxa] == ["house_finch"]

    def test_all_input_statuses_survive_into_taxa_unfiltered(self) -> None:
        statuses = [
            _status(NORTHERN_CARDINAL, status="new", last_confirmed_at=GENERATED_AT),
            _status(HOUSE_FINCH, status="regular", last_confirmed_at=GENERATED_AT),
            _status(BLUE_JAY, status="seen_before", last_confirmed_at=GENERATED_AT),
        ]
        summary = compute_place_biodiversity_summary(
            statuses, historical_baseline=_baseline(), generated_at=GENERATED_AT
        )
        assert len(summary.taxa) == 3


class TestRecentlyObserved:
    def test_within_window_is_included(self) -> None:
        recent = _status(
            NORTHERN_CARDINAL, status="seen_before", last_confirmed_at=GENERATED_AT - timedelta(days=1)
        )
        summary = compute_place_biodiversity_summary(
            [recent], historical_baseline=_baseline(), generated_at=GENERATED_AT
        )
        assert [s.taxon.label for s in summary.recently_observed_taxa] == ["northern_cardinal"]

    def test_outside_window_is_excluded(self) -> None:
        stale = _status(
            NORTHERN_CARDINAL,
            status="regular",
            last_confirmed_at=GENERATED_AT - timedelta(days=RECENTLY_OBSERVED_WINDOW_DAYS + 1),
        )
        summary = compute_place_biodiversity_summary(
            [stale], historical_baseline=_baseline(), generated_at=GENERATED_AT
        )
        assert summary.recently_observed_taxa == ()
        # Absence from recently_observed_taxa is silent -- the taxon is not
        # demoted, hidden, or flagged "absent" anywhere else in the summary.
        assert [s.taxon.label for s in summary.regular_taxa] == ["northern_cardinal"]

    def test_exact_boundary_is_inclusive(self) -> None:
        boundary = _status(
            NORTHERN_CARDINAL,
            status="seen_before",
            last_confirmed_at=GENERATED_AT - timedelta(days=RECENTLY_OBSERVED_WINDOW_DAYS),
        )
        summary = compute_place_biodiversity_summary(
            [boundary], historical_baseline=_baseline(), generated_at=GENERATED_AT
        )
        assert [s.taxon.label for s in summary.recently_observed_taxa] == ["northern_cardinal"]

    def test_a_taxon_can_be_both_new_and_recently_observed(self) -> None:
        new_and_recent = _status(NORTHERN_CARDINAL, status="new", last_confirmed_at=GENERATED_AT)
        summary = compute_place_biodiversity_summary(
            [new_and_recent], historical_baseline=_baseline(), generated_at=GENERATED_AT
        )
        assert [s.taxon.label for s in summary.new_taxa] == ["northern_cardinal"]
        assert [s.taxon.label for s in summary.recently_observed_taxa] == ["northern_cardinal"]


class TestDistinctSpeciesCount:
    def test_counts_only_is_species_true(self) -> None:
        species = _status(NORTHERN_CARDINAL, status="seen_before", last_confirmed_at=GENERATED_AT)
        kind_level = _status(SQUIRREL, status="seen_before", last_confirmed_at=GENERATED_AT)
        summary = compute_place_biodiversity_summary(
            [species, kind_level], historical_baseline=_baseline(), generated_at=GENERATED_AT
        )
        assert summary.distinct_species_count == 1
        assert len(summary.taxa) == 2

    def test_empty_input_gives_zero_everywhere(self) -> None:
        summary = compute_place_biodiversity_summary(
            [], historical_baseline=_baseline(distinct_taxa_count=0), generated_at=GENERATED_AT
        )
        assert summary.distinct_species_count == 0
        assert summary.taxa == ()
        assert summary.new_taxa == ()
        assert summary.regular_taxa == ()
        assert summary.recently_observed_taxa == ()


class TestSortOrder:
    def test_most_recently_confirmed_first(self) -> None:
        older = _status(NORTHERN_CARDINAL, status="seen_before", last_confirmed_at=GENERATED_AT - timedelta(days=5))
        newer = _status(HOUSE_FINCH, status="seen_before", last_confirmed_at=GENERATED_AT - timedelta(days=1))
        summary = compute_place_biodiversity_summary(
            [older, newer], historical_baseline=_baseline(), generated_at=GENERATED_AT
        )
        assert [s.taxon.label for s in summary.taxa] == ["house_finch", "northern_cardinal"]

    def test_ties_broken_by_label_ascending(self) -> None:
        same_instant = GENERATED_AT - timedelta(days=1)
        a = _status(BLUE_JAY, status="seen_before", last_confirmed_at=same_instant)
        b = _status(NORTHERN_CARDINAL, status="seen_before", last_confirmed_at=same_instant)
        summary = compute_place_biodiversity_summary(
            [b, a], historical_baseline=_baseline(), generated_at=GENERATED_AT
        )
        assert [s.taxon.label for s in summary.taxa] == ["blue_jay", "northern_cardinal"]

    def test_recently_observed_taxa_inherits_the_same_order(self) -> None:
        older = _status(NORTHERN_CARDINAL, status="regular", last_confirmed_at=GENERATED_AT - timedelta(days=2))
        newer = _status(HOUSE_FINCH, status="regular", last_confirmed_at=GENERATED_AT - timedelta(days=1))
        summary = compute_place_biodiversity_summary(
            [older, newer], historical_baseline=_baseline(), generated_at=GENERATED_AT
        )
        assert [s.taxon.label for s in summary.recently_observed_taxa] == ["house_finch", "northern_cardinal"]


class TestWarnings:
    def test_no_monitoring_history_at_all(self) -> None:
        summary = compute_place_biodiversity_summary(
            [], historical_baseline=_baseline(total_monitored_seconds=None, maturity="insufficient"),
            generated_at=GENERATED_AT,
        )
        assert len(summary.warnings) == 1
        assert "No camera has spent time observing yet" in summary.warnings[0]

    def test_insufficient_but_some_monitoring_gets_a_different_warning(self) -> None:
        summary = compute_place_biodiversity_summary(
            [], historical_baseline=_baseline(total_monitored_seconds=3600.0, maturity="insufficient"),
            generated_at=GENERATED_AT,
        )
        assert len(summary.warnings) == 1
        assert "Not enough monitored history" in summary.warnings[0]

    def test_developing_gets_a_softer_warning(self) -> None:
        summary = compute_place_biodiversity_summary(
            [], historical_baseline=_baseline(maturity="developing"), generated_at=GENERATED_AT
        )
        assert len(summary.warnings) == 1
        assert "still developing" in summary.warnings[0]

    def test_established_has_no_warnings(self) -> None:
        summary = compute_place_biodiversity_summary(
            [], historical_baseline=_baseline(maturity="established"), generated_at=GENERATED_AT
        )
        assert summary.warnings == ()

    def test_at_most_one_warning_ever_fires(self) -> None:
        for maturity in ("insufficient", "developing", "established"):
            for monitored_seconds in (None, 0.0, 3600.0):
                summary = compute_place_biodiversity_summary(
                    [],
                    historical_baseline=_baseline(maturity=maturity, total_monitored_seconds=monitored_seconds),
                    generated_at=GENERATED_AT,
                )
                assert len(summary.warnings) <= 1


class TestDeterminism:
    def test_identical_input_gives_identical_output(self) -> None:
        statuses = [
            _status(NORTHERN_CARDINAL, status="new", last_confirmed_at=GENERATED_AT),
            _status(HOUSE_FINCH, status="regular", last_confirmed_at=GENERATED_AT - timedelta(days=3)),
        ]
        baseline = _baseline(distinct_taxa_count=2)
        first = compute_place_biodiversity_summary(statuses, historical_baseline=baseline, generated_at=GENERATED_AT)
        second = compute_place_biodiversity_summary(statuses, historical_baseline=baseline, generated_at=GENERATED_AT)
        assert first == second

    def test_historical_baseline_passed_through_unmodified(self) -> None:
        baseline = _baseline(distinct_taxa_count=7, usable_day_count=42)
        summary = compute_place_biodiversity_summary([], historical_baseline=baseline, generated_at=GENERATED_AT)
        assert summary.historical_baseline is baseline
