"""Pure computation tests for mockingbird.analytics.habitat_association.

No repository, no database -- matches the existing test_place_change_summary.py
precedent for a pure sibling module. See the module docstring of
`habitat_association.py` and docs/place-yard-intelligence-v2-contract.md
section 3.3/6 for the product contract these bounded, association-only
phenology comparisons must honor (association language only, never causal).
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from mockingbird.analytics import habitat_association, seasonal_pattern
from mockingbird.analytics.conditional_association import (
    DEFAULT_MIN_RATE_DIFFERENCE,
    DEFAULT_MIN_USABLE_DAYS_IN_CONDITION,
    DEFAULT_MIN_USABLE_DAYS_OUT_OF_CONDITION,
)
from mockingbird.analytics.habitat_association import (
    MIN_CONDITION_INTERVAL_DAYS,
    PhenologyIntervalFact,
    TaxonHabitatAssociation,
    compute_habitat_associations,
    presence_dates_by_taxon,
)
from mockingbird.analytics.place_activity_report import TaxonFact, VisitFact

SPARROW = TaxonFact("song_sparrow", "Song Sparrow", "bird", True)
FINCH = TaxonFact("house_finch", "House Finch", "bird", True)

# An arbitrary anchor date for every scenario below.
BASE = date(2026, 1, 1)

# The scenarios below are built around the specific numeric floors these
# modules currently document; a silent change to any of them would silently
# invalidate the arithmetic baked into the fixtures rather than failing
# loudly, so guard it explicitly (mirrors test_place_change_summary.py's own
# `test_thresholds_are_the_documented_constants` precedent).
assert MIN_CONDITION_INTERVAL_DAYS == 5
assert DEFAULT_MIN_USABLE_DAYS_IN_CONDITION == DEFAULT_MIN_USABLE_DAYS_OUT_OF_CONDITION == 5
assert DEFAULT_MIN_RATE_DIFFERENCE == 0.25


def _dates(start: date, count: int) -> set[date]:
    """`count` consecutive calendar dates starting at (and including) `start`."""

    return {start + timedelta(days=offset) for offset in range(count)}


def _visit(
    visit_id: str,
    *,
    at: datetime,
    taxon: TaxonFact | None = None,
    resolution: str = "reviewed",
) -> VisitFact:
    return VisitFact(
        visit_id=visit_id,
        zone_id=None,
        zone_name=None,
        activity_started_at=at,
        resolution=resolution,  # type: ignore[arg-type]
        confirmed_taxon=taxon,
    )


def _visits_on_dates(taxon: TaxonFact, dates: set[date], *, prefix: str) -> list[VisitFact]:
    return [
        _visit(f"{prefix}-{day.isoformat()}", at=datetime(day.year, day.month, day.day, 12, tzinfo=UTC), taxon=taxon)
        for day in dates
    ]


# ---------------------------------------------------------------------------
# compute_habitat_associations
# ---------------------------------------------------------------------------


def test_taxon_more_common_while_phenomenon_current_yields_one_association() -> None:
    usable = _dates(BASE, 20)  # Jan 1 -- Jan 20
    lilac_flowering = PhenologyIntervalFact(
        subject_label="Lilac",
        phenomenon="flowering",
        observed_start_date=BASE,
        observed_end_date=BASE + timedelta(days=9),  # Jan 1 -- Jan 10, 10 usable days
    )
    presence = _dates(BASE, 8) | _dates(BASE + timedelta(days=10), 2)  # 8/10 inside, 2/10 outside
    visits = _visits_on_dates(SPARROW, presence, prefix="v")

    [result] = compute_habitat_associations(
        visits,
        taxa={SPARROW.label: SPARROW},
        usable_dates=usable,
        local_timezone=UTC,
        phenology_observations=[lilac_flowering],
        window_end_at=datetime(2026, 1, 25, 12, tzinfo=UTC),
    )

    assert result.taxon == SPARROW
    assert result.subject_label == "Lilac"
    assert result.phenomenon == "flowering"
    assert result.association.status == "more_common_under_condition"
    assert result.association.presence_days_in_condition == 8
    assert result.association.usable_days_in_condition == 10
    assert result.association.presence_days_out_of_condition == 2
    assert result.association.usable_days_out_of_condition == 10


def test_phenomenon_interval_too_short_contributes_zero_entries() -> None:
    """A 2-day interval can never clear `MIN_CONDITION_INTERVAL_DAYS` (5) on
    its own "inside" side, however long the surrounding usable window is --
    the phenomenon must be skipped silently, not surfaced as
    `insufficient_data`."""

    usable = _dates(BASE, 20)
    brief_bloom = PhenologyIntervalFact(
        subject_label="Crocus",
        phenomenon="flowering",
        observed_start_date=BASE + timedelta(days=5),
        observed_end_date=BASE + timedelta(days=6),  # a 2-day interval
    )
    # Presence on every usable day -- so an empty result can only be because
    # of the interval-length gate, never because of missing presence.
    visits = _visits_on_dates(SPARROW, usable, prefix="v")

    results = compute_habitat_associations(
        visits,
        taxa={SPARROW.label: SPARROW},
        usable_dates=usable,
        local_timezone=UTC,
        phenology_observations=[brief_bloom],
        window_end_at=datetime(2026, 1, 25, 12, tzinfo=UTC),
    )

    assert results == []


def test_taxon_with_zero_presence_contributes_no_entry() -> None:
    usable = _dates(BASE, 20)
    long_bloom = PhenologyIntervalFact(
        subject_label="Lilac",
        phenomenon="flowering",
        observed_start_date=BASE,
        observed_end_date=BASE + timedelta(days=9),  # a comfortably long 10-day interval
    )

    results = compute_habitat_associations(
        [],  # no Visits at all -- the taxon has zero presence anywhere
        taxa={SPARROW.label: SPARROW},
        usable_dates=usable,
        local_timezone=UTC,
        phenology_observations=[long_bloom],
        window_end_at=datetime(2026, 1, 25, 12, tzinfo=UTC),
    )

    assert results == []


def test_ongoing_interval_is_current_through_window_end_ats_local_date() -> None:
    """`observed_end_date=None` means "still ongoing" -- its condition dates
    must extend through whatever local date `window_end_at` resolves to.
    Two calls differing only in `window_end_at` prove the extension is
    real: presence recorded well after the interval's start only counts as
    "in condition" once `window_end_at` reaches far enough to make it
    current."""

    usable = _dates(BASE, 25)  # Jan 1 -- Jan 25
    presence = _dates(BASE, 5) | _dates(BASE + timedelta(days=15), 5)  # Jan 1-5 and Jan 16-20
    visits = _visits_on_dates(SPARROW, presence, prefix="v")
    taxa = {SPARROW.label: SPARROW}
    ongoing_bloom = PhenologyIntervalFact(
        subject_label="Lilac", phenomenon="flowering", observed_start_date=BASE, observed_end_date=None
    )

    [early_result] = compute_habitat_associations(
        visits,
        taxa=taxa,
        usable_dates=usable,
        local_timezone=UTC,
        phenology_observations=[ongoing_bloom],
        window_end_at=datetime(2026, 1, 10, 12, tzinfo=UTC),  # "today" is still early -- condition is Jan 1-10
    )
    assert early_result.association.usable_days_in_condition == 10
    assert early_result.association.presence_days_in_condition == 5  # only Jan 1-5 falls within Jan 1-10
    assert early_result.association.status == "no_clear_association"

    [later_result] = compute_habitat_associations(
        visits,
        taxa=taxa,
        usable_dates=usable,
        local_timezone=UTC,
        phenology_observations=[ongoing_bloom],
        window_end_at=datetime(2026, 1, 20, 12, tzinfo=UTC),  # "today" has moved on -- condition is now Jan 1-20
    )
    assert later_result.association.usable_days_in_condition == 20
    assert later_result.association.presence_days_in_condition == 10  # Jan 16-20 is now current too
    assert later_result.association.status == "more_common_under_condition"


def test_multiple_phenomena_and_taxa_are_evaluated_independently() -> None:
    usable = _dates(BASE, 20)  # Jan 1 -- Jan 20
    flowering = PhenologyIntervalFact(
        subject_label="Lilac",
        phenomenon="flowering",
        observed_start_date=BASE,
        observed_end_date=BASE + timedelta(days=9),  # Jan 1-10
    )
    fruiting = PhenologyIntervalFact(
        subject_label="Dogwood",
        phenomenon="fruiting",
        observed_start_date=BASE + timedelta(days=10),
        observed_end_date=BASE + timedelta(days=19),  # Jan 11-20
    )
    # SPARROW is only ever seen in the first half of the window; FINCH only
    # in the second half -- opposite presence patterns relative to each
    # phenomenon's own condition window.
    sparrow_visits = _visits_on_dates(SPARROW, _dates(BASE, 8), prefix="sp")
    finch_visits = _visits_on_dates(FINCH, _dates(BASE + timedelta(days=10), 8), prefix="fi")

    results = compute_habitat_associations(
        sparrow_visits + finch_visits,
        taxa={SPARROW.label: SPARROW, FINCH.label: FINCH},
        usable_dates=usable,
        local_timezone=UTC,
        phenology_observations=[flowering, fruiting],
        window_end_at=datetime(2026, 1, 25, 12, tzinfo=UTC),
    )

    by_pair = {(entry.taxon.label, entry.phenomenon): entry for entry in results}
    assert len(results) == 4
    assert set(by_pair) == {
        (SPARROW.label, "flowering"),
        (SPARROW.label, "fruiting"),
        (FINCH.label, "flowering"),
        (FINCH.label, "fruiting"),
    }

    sparrow_flowering = by_pair[(SPARROW.label, "flowering")]
    assert sparrow_flowering.subject_label == "Lilac"
    assert sparrow_flowering.association.status == "more_common_under_condition"
    assert sparrow_flowering.association.presence_days_in_condition == 8
    assert sparrow_flowering.association.presence_days_out_of_condition == 0

    sparrow_fruiting = by_pair[(SPARROW.label, "fruiting")]
    assert sparrow_fruiting.subject_label == "Dogwood"
    assert sparrow_fruiting.association.status == "less_common_under_condition"
    assert sparrow_fruiting.association.presence_days_in_condition == 0
    assert sparrow_fruiting.association.presence_days_out_of_condition == 8

    finch_flowering = by_pair[(FINCH.label, "flowering")]
    assert finch_flowering.association.status == "less_common_under_condition"
    assert finch_flowering.association.presence_days_in_condition == 0
    assert finch_flowering.association.presence_days_out_of_condition == 8

    finch_fruiting = by_pair[(FINCH.label, "fruiting")]
    assert finch_fruiting.association.status == "more_common_under_condition"
    assert finch_fruiting.association.presence_days_in_condition == 8
    assert finch_fruiting.association.presence_days_out_of_condition == 0


def test_empty_phenology_observations_returns_empty_list() -> None:
    usable = _dates(BASE, 20)
    visits = _visits_on_dates(SPARROW, _dates(BASE, 10), prefix="v")

    results = compute_habitat_associations(
        visits,
        taxa={SPARROW.label: SPARROW},
        usable_dates=usable,
        local_timezone=UTC,
        phenology_observations=[],
        window_end_at=datetime(2026, 1, 25, 12, tzinfo=UTC),
    )

    assert results == []


def test_deterministic_for_identical_inputs() -> None:
    usable = _dates(BASE, 20)
    flowering = PhenologyIntervalFact(
        subject_label="Lilac",
        phenomenon="flowering",
        observed_start_date=BASE,
        observed_end_date=BASE + timedelta(days=9),
    )
    fruiting = PhenologyIntervalFact(
        subject_label="Dogwood",
        phenomenon="fruiting",
        observed_start_date=BASE + timedelta(days=10),
        observed_end_date=BASE + timedelta(days=19),
    )
    sparrow_visits = _visits_on_dates(SPARROW, _dates(BASE, 8), prefix="sp")
    finch_visits = _visits_on_dates(FINCH, _dates(BASE + timedelta(days=10), 8), prefix="fi")
    window_end_at = datetime(2026, 1, 25, 12, tzinfo=UTC)

    def _run() -> list[TaxonHabitatAssociation]:
        return compute_habitat_associations(
            list(sparrow_visits) + list(finch_visits),
            taxa={SPARROW.label: SPARROW, FINCH.label: FINCH},
            usable_dates=set(usable),
            local_timezone=UTC,
            phenology_observations=[flowering, fruiting],
            window_end_at=window_end_at,
        )

    assert _run() == _run()


# ---------------------------------------------------------------------------
# presence_dates_by_taxon (defined in seasonal_pattern.py, re-exported here)
# ---------------------------------------------------------------------------


def test_presence_dates_by_taxon_is_the_shared_seasonal_pattern_function() -> None:
    assert habitat_association.presence_dates_by_taxon is seasonal_pattern.presence_dates_by_taxon


def test_presence_dates_by_taxon_groups_confirmed_visits_by_taxon_and_local_date() -> None:
    day_one = datetime(2026, 1, 1, 9, tzinfo=UTC)
    day_two = datetime(2026, 1, 2, 9, tzinfo=UTC)
    visits = [
        _visit("a", at=day_one, taxon=SPARROW),
        _visit("b", at=day_two, taxon=SPARROW),
        _visit("c", at=day_one, taxon=FINCH),
        # No confirmed_taxon -- must never contribute.
        _visit("unresolved", at=day_one, resolution="needs_review"),
    ]

    grouped = presence_dates_by_taxon(visits, local_timezone=UTC)

    assert grouped == {
        SPARROW.label: {day_one.date(), day_two.date()},
        FINCH.label: {day_one.date()},
    }
