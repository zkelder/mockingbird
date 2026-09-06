"""Repository/integration tests for ProductRepository.place_year_over_year_
comparison -- real seeded SQLite data. Mirrors tests/test_place_story_
repository.py's fixture/seeding pattern (see that file for the established
precedent this one follows), extended with a second camera/stream for the
multi-camera dedup proofs (mirroring tests/test_multi_camera_place_
experience_scenario.py's own two-Source fixture shape).
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import event

from mockingbird.api.main import app, configure_repository
from mockingbird.api.schemas import CurrentUser, ReviewCorrectionCreate, UserRole
from mockingbird.repository.product_repository import (
    CrossCameraVisitAssociationModel,
    ProductRepository,
)
from mockingbird.storage.models import (
    CameraSourceModel,
    EventModel,
    MonitoringExposureIntervalModel,
    StreamModel,
    VisitModel,
    ZoneModel,
)
from tests.conftest import LegacyAuthenticatedSyncTestClient

SOURCE_A, STREAM_A, ZONE_A = "yoy-source-a", "yoy-stream-a", "yoy-zone-a"
SOURCE_B, STREAM_B, ZONE_B = "yoy-source-b", "yoy-stream-b", "yoy-zone-b"

# September, both years -- the milestone brief's own worked example period.
CURRENT_YEAR, CURRENT_MONTH = 2026, 9
PRIOR_YEAR = 2025


@pytest.fixture
def repository(tmp_path: Path) -> ProductRepository:
    repo = ProductRepository(db_url=f"sqlite:///{tmp_path / 'mockingbird.sqlite3'}", media_root=tmp_path / "media")
    configure_repository(repo)
    with repo.session_factory() as session:
        with session.begin():
            # Archive the auto-seeded demo Source (mirrors test_multi_
            # camera_place_experience_scenario.py's identical fixture
            # convention) so this test's own coverage/count assertions are
            # never polluted by an unrelated, unconfigured demo camera.
            demo = session.get(CameraSourceModel, "source-backyard-demo")
            if demo is not None:
                demo.status = "archived"
            for source_id, stream_id, zone_id, name in (
                (SOURCE_A, STREAM_A, ZONE_A, "Front Feeder"),
                (SOURCE_B, STREAM_B, ZONE_B, "Back Yard"),
            ):
                session.add(CameraSourceModel(
                    id=source_id, name=name, kind="manual_upload", status="connected",
                    description="Year-over-Year fixture.",
                ))
                session.add(StreamModel(
                    id=stream_id, source_id=source_id, name=name,
                    description="Year-over-Year fixture.", is_live=False,
                ))
                session.add(ZoneModel(
                    id=zone_id, stream_id=stream_id, name="Feeder", zone_type="feeder",
                    polygon_json="[]", is_active=True, monitoring_policy_json=None,
                ))
    yield repo
    configure_repository(None)
    repo.close()


def _acting_user() -> CurrentUser:
    return CurrentUser(
        id="user-test-admin", display_name="Test Admin", login_identity="test-admin",
        role=UserRole.administrator, enabled=True,
    )


def _add_visit(
    repository: ProductRepository, *, visit_id: str, at: datetime, stream_id: str = STREAM_A, zone_id: str = ZONE_A,
) -> None:
    event_id = f"event-{visit_id}"
    with repository.session_factory() as session:
        with session.begin():
            session.add(EventModel(
                id=event_id, stream_id=stream_id, title=f"YoY fixture {visit_id}",
                event_type="manual_media_import", started_at=at, ended_at=at + timedelta(seconds=20),
                primary_zone_id=zone_id, review_status="needs_review",
            ))
            session.add(VisitModel(
                id=visit_id, event_id=event_id, subject_label="unknown_bird", species_guess=None,
                confidence=None, reviewed_label=None, review_status="needs_review",
                representative_media_path=None, zone_id=zone_id, is_superseded=False,
            ))


def _confirm(repository: ProductRepository, *, visit_id: str, label: str = "northern_cardinal") -> None:
    repository.create_review_label(
        ReviewCorrectionCreate(target_type="visit", target_id=visit_id, label=label, review_origin="human")
    )


def _cover_days(
    repository: ProductRepository, *, start: date, days: int, stream_id: str = STREAM_A, source_id: str = SOURCE_A,
) -> None:
    """One full 23-hour-healthy exposure interval per day -- clears every
    usable-day floor this codebase uses. Mirrors test_place_story_
    repository.py's identical helper."""

    with repository.session_factory() as session:
        with session.begin():
            for offset in range(days):
                day = start + timedelta(days=offset)
                started_at = datetime(day.year, day.month, day.day, tzinfo=UTC)
                ended_at = started_at + timedelta(hours=23)
                session.add(MonitoringExposureIntervalModel(
                    id=f"exposure-{stream_id}-{day.isoformat()}", stream_id=stream_id, source_id=source_id,
                    runtime_generation_id=f"generation-{stream_id}-{day.isoformat()}", started_at=started_at,
                    last_confirmed_fresh_at=ended_at, ended_at=ended_at, close_reason="provider_failure",
                    created_at=started_at, updated_at=ended_at,
                ))


def _cover_partial_hours(
    repository: ProductRepository, *, start: date, days: int, hours: float,
    stream_id: str = STREAM_A, source_id: str = SOURCE_A,
) -> None:
    """`hours` of coverage per day -- used to build a below-the-usable-day-
    floor (< 2h) monitoring history for the "insufficient coverage" cases."""

    with repository.session_factory() as session:
        with session.begin():
            for offset in range(days):
                day = start + timedelta(days=offset)
                started_at = datetime(day.year, day.month, day.day, tzinfo=UTC)
                ended_at = started_at + timedelta(hours=hours)
                session.add(MonitoringExposureIntervalModel(
                    id=f"exposure-partial-{stream_id}-{day.isoformat()}", stream_id=stream_id, source_id=source_id,
                    runtime_generation_id=f"generation-partial-{stream_id}-{day.isoformat()}", started_at=started_at,
                    last_confirmed_fresh_at=ended_at, ended_at=ended_at, close_reason="provider_failure",
                    created_at=started_at, updated_at=ended_at,
                ))


def _fully_monitored_september(repository: ProductRepository, *, year: int, stream_id: str = STREAM_A) -> None:
    _cover_days(repository, start=date(year, 9, 1), days=30, stream_id=stream_id)


def _confirmed_days(
    repository: ProductRepository, *, prefix: str, year: int, days: list[int], label: str = "northern_cardinal",
    stream_id: str = STREAM_A, zone_id: str = ZONE_A,
) -> None:
    for i, day in enumerate(days):
        visit_id = f"{prefix}-{i}"
        _add_visit(repository, visit_id=visit_id, at=datetime(year, 9, day, 10, tzinfo=UTC), stream_id=stream_id, zone_id=zone_id)
        _confirm(repository, visit_id=visit_id, label=label)


# ---------------------------------------------------------------------------
# A. Place comparison
# ---------------------------------------------------------------------------


class TestPlaceComparison:
    def test_current_higher_than_prior_after_effort_normalization(self, repository: ProductRepository) -> None:
        _fully_monitored_september(repository, year=CURRENT_YEAR)
        _fully_monitored_september(repository, year=PRIOR_YEAR)
        _confirmed_days(repository, prefix="cur", year=CURRENT_YEAR, days=list(range(1, 17)))  # 16 of 30 days
        _confirmed_days(repository, prefix="pri", year=PRIOR_YEAR, days=list(range(1, 5)))  # 4 of 30 days

        result = repository.place_year_over_year_comparison(
            now=datetime(CURRENT_YEAR, 10, 2, tzinfo=UTC), year=CURRENT_YEAR, month=CURRENT_MONTH,
        )
        assert result.place.status == "comparable"
        assert result.place.overall_activity == "higher"

    def test_current_lower_than_prior(self, repository: ProductRepository) -> None:
        _fully_monitored_september(repository, year=CURRENT_YEAR)
        _fully_monitored_september(repository, year=PRIOR_YEAR)
        _confirmed_days(repository, prefix="cur", year=CURRENT_YEAR, days=list(range(1, 5)))
        _confirmed_days(repository, prefix="pri", year=PRIOR_YEAR, days=list(range(1, 17)))

        result = repository.place_year_over_year_comparison(
            now=datetime(CURRENT_YEAR, 10, 2, tzinfo=UTC), year=CURRENT_YEAR, month=CURRENT_MONTH,
        )
        assert result.place.status == "comparable"
        assert result.place.overall_activity == "lower"

    def test_materially_similar_activity(self, repository: ProductRepository) -> None:
        _fully_monitored_september(repository, year=CURRENT_YEAR)
        _fully_monitored_september(repository, year=PRIOR_YEAR)
        _confirmed_days(repository, prefix="cur", year=CURRENT_YEAR, days=list(range(1, 11)))  # 10 of 30
        _confirmed_days(repository, prefix="pri", year=PRIOR_YEAR, days=list(range(1, 10)))  # 9 of 30

        result = repository.place_year_over_year_comparison(
            now=datetime(CURRENT_YEAR, 10, 2, tzinfo=UTC), year=CURRENT_YEAR, month=CURRENT_MONTH,
        )
        assert result.place.status == "no_material_difference"
        assert result.place.overall_activity == "similar"

    def test_overlapping_multi_camera_coverage_is_not_double_counted(self, repository: ProductRepository) -> None:
        """Two cameras both healthy for the same overlapping hours must
        union to the same usable-day set a single camera would produce --
        never double the effective monitored time (the exact Zone Insights
        bug this codebase already found and fixed once at Place scope; see
        `_usable_dates_for_window` -> `bucket_intervals_by_local_day` ->
        `merge_intervals`)."""

        _cover_days(repository, start=date(CURRENT_YEAR, 9, 1), days=30, stream_id=STREAM_A, source_id=SOURCE_A)
        _cover_days(repository, start=date(CURRENT_YEAR, 9, 1), days=30, stream_id=STREAM_B, source_id=SOURCE_B)
        _fully_monitored_september(repository, year=PRIOR_YEAR)
        _confirmed_days(repository, prefix="cur", year=CURRENT_YEAR, days=list(range(1, 17)))
        _confirmed_days(repository, prefix="pri", year=PRIOR_YEAR, days=list(range(1, 5)))

        result = repository.place_year_over_year_comparison(
            now=datetime(CURRENT_YEAR, 10, 2, tzinfo=UTC), year=CURRENT_YEAR, month=CURRENT_MONTH,
        )
        # 30 usable days, not 60 -- two fully-overlapping cameras union to
        # the same coverage a single one would give.
        assert result.place.current_period.usable_day_count == 30


# ---------------------------------------------------------------------------
# B. History sufficiency
# ---------------------------------------------------------------------------


class TestHistorySufficiency:
    def test_no_prior_year_history_at_all(self, repository: ProductRepository) -> None:
        _fully_monitored_september(repository, year=CURRENT_YEAR)
        _confirmed_days(repository, prefix="cur", year=CURRENT_YEAR, days=list(range(1, 11)))
        # No prior-year coverage/Visits seeded at all.

        result = repository.place_year_over_year_comparison(
            now=datetime(CURRENT_YEAR, 10, 2, tzinfo=UTC), year=CURRENT_YEAR, month=CURRENT_MONTH,
        )
        assert result.place.status == "insufficient_prior_history"
        assert result.place.overall_activity is None
        assert result.place.prior_period.usable_day_count == 0

    def test_low_prior_coverage(self, repository: ProductRepository) -> None:
        _fully_monitored_september(repository, year=CURRENT_YEAR)
        _cover_partial_hours(repository, start=date(PRIOR_YEAR, 9, 1), days=3, hours=1.0)  # < 2h/day -> unusable
        _confirmed_days(repository, prefix="cur", year=CURRENT_YEAR, days=list(range(1, 11)))

        result = repository.place_year_over_year_comparison(
            now=datetime(CURRENT_YEAR, 10, 2, tzinfo=UTC), year=CURRENT_YEAR, month=CURRENT_MONTH,
        )
        # Some durable history exists a year ago, just not enough of it --
        # a genuinely different, more honest state than "no history at all".
        assert result.place.status in ("insufficient_prior_coverage", "insufficient_prior_history")
        assert result.place.prior_period.usable_day_count == 0

    def test_low_current_coverage(self, repository: ProductRepository) -> None:
        _cover_partial_hours(repository, start=date(CURRENT_YEAR, 9, 1), days=3, hours=1.0)
        _fully_monitored_september(repository, year=PRIOR_YEAR)
        _confirmed_days(repository, prefix="pri", year=PRIOR_YEAR, days=list(range(1, 11)))

        result = repository.place_year_over_year_comparison(
            now=datetime(CURRENT_YEAR, 9, 6, tzinfo=UTC), year=CURRENT_YEAR, month=CURRENT_MONTH,
        )
        assert result.place.status == "insufficient_current_coverage"
        assert result.place.overall_activity is None

    def test_partial_current_period_abstains(self, repository: ProductRepository) -> None:
        _fully_monitored_september(repository, year=CURRENT_YEAR)  # coverage exists through the whole month...
        _fully_monitored_september(repository, year=PRIOR_YEAR)
        _confirmed_days(repository, prefix="cur", year=CURRENT_YEAR, days=list(range(1, 17)))
        _confirmed_days(repository, prefix="pri", year=PRIOR_YEAR, days=list(range(1, 5)))

        # ...but "now" is only Sept 15 -- the current month is still
        # genuinely in progress.
        result = repository.place_year_over_year_comparison(
            now=datetime(CURRENT_YEAR, 9, 15, 8, tzinfo=UTC), year=CURRENT_YEAR, month=CURRENT_MONTH,
        )
        assert result.place.status == "partial_period"
        assert result.place.current_period.is_complete is False
        assert result.place.current_period.end_date == date(CURRENT_YEAR, 9, 16)

    def test_default_period_is_the_current_place_local_month(self, repository: ProductRepository) -> None:
        _fully_monitored_september(repository, year=CURRENT_YEAR)
        _fully_monitored_september(repository, year=PRIOR_YEAR)

        result = repository.place_year_over_year_comparison(now=datetime(CURRENT_YEAR, 9, 20, 12, tzinfo=UTC))
        assert result.place.current_period.start_date == date(CURRENT_YEAR, 9, 1)
        assert result.place.prior_period.start_date == date(PRIOR_YEAR, 9, 1)

    def test_future_month_is_rejected(self, repository: ProductRepository) -> None:
        with pytest.raises(ValueError):
            repository.place_year_over_year_comparison(
                now=datetime(CURRENT_YEAR, 9, 6, tzinfo=UTC), year=CURRENT_YEAR, month=12,
            )


# ---------------------------------------------------------------------------
# C. Species
# ---------------------------------------------------------------------------


class TestSpeciesComparison:
    def test_meaningful_increase_and_decrease_both_appear_as_notable(self, repository: ProductRepository) -> None:
        _fully_monitored_september(repository, year=CURRENT_YEAR)
        _fully_monitored_september(repository, year=PRIOR_YEAR)
        _confirmed_days(repository, prefix="cardinal-cur", year=CURRENT_YEAR, days=list(range(1, 17)), label="northern_cardinal")
        _confirmed_days(repository, prefix="cardinal-pri", year=PRIOR_YEAR, days=list(range(1, 5)), label="northern_cardinal")
        _confirmed_days(repository, prefix="jay-cur", year=CURRENT_YEAR, days=list(range(1, 5)), label="blue_jay")
        _confirmed_days(repository, prefix="jay-pri", year=PRIOR_YEAR, days=list(range(1, 17)), label="blue_jay")

        result = repository.place_year_over_year_comparison(
            now=datetime(CURRENT_YEAR, 10, 2, tzinfo=UTC), year=CURRENT_YEAR, month=CURRENT_MONTH,
        )
        by_label = {entry.label: entry for entry in result.notable_species_changes}
        assert by_label["northern_cardinal"].activity_direction == "higher"
        assert by_label["blue_jay"].activity_direction == "lower"

    def test_stable_species_is_not_notable(self, repository: ProductRepository) -> None:
        _fully_monitored_september(repository, year=CURRENT_YEAR)
        _fully_monitored_september(repository, year=PRIOR_YEAR)
        _confirmed_days(repository, prefix="cur", year=CURRENT_YEAR, days=list(range(1, 11)), label="house_finch")
        _confirmed_days(repository, prefix="pri", year=PRIOR_YEAR, days=list(range(1, 10)), label="house_finch")

        result = repository.place_year_over_year_comparison(
            now=datetime(CURRENT_YEAR, 10, 2, tzinfo=UTC), year=CURRENT_YEAR, month=CURRENT_MONTH,
        )
        assert "house_finch" not in {entry.label for entry in result.notable_species_changes}

    def test_tiny_denominator_does_not_produce_a_dramatic_notable_insight(self, repository: ProductRepository) -> None:
        _fully_monitored_september(repository, year=CURRENT_YEAR)
        _fully_monitored_september(repository, year=PRIOR_YEAR)
        # A single confirmed Visit this year, none a year ago -- a
        # "limitless percent increase" by raw ratio, but far too thin a
        # sample to narrate.
        _confirmed_days(repository, prefix="cur", year=CURRENT_YEAR, days=[5], label="song_sparrow")

        result = repository.place_year_over_year_comparison(
            now=datetime(CURRENT_YEAR, 10, 2, tzinfo=UTC), year=CURRENT_YEAR, month=CURRENT_MONTH,
        )
        assert "song_sparrow" not in {entry.label for entry in result.notable_species_changes}

    def test_first_observed_timing_comparison(self, repository: ProductRepository) -> None:
        _fully_monitored_september(repository, year=CURRENT_YEAR)
        _fully_monitored_september(repository, year=PRIOR_YEAR)
        # First observed Sept 10 this year (9 usable days of lead-in);
        # Sept 25 a year ago (24 usable days of lead-in) -- a real,
        # well-supported, materially-earlier-this-year timing claim.
        _confirmed_days(
            repository, prefix="hb-cur", year=CURRENT_YEAR,
            days=[10, 15, 16, 17, 18, 19], label="eastern_bluebird",
        )
        _confirmed_days(
            repository, prefix="hb-pri", year=PRIOR_YEAR,
            days=[25, 26, 27, 28, 29, 30], label="eastern_bluebird",
        )

        result = repository.place_year_over_year_comparison(
            now=datetime(CURRENT_YEAR, 10, 2, tzinfo=UTC), year=CURRENT_YEAR, month=CURRENT_MONTH,
        )
        entry = next(e for e in result.notable_species_changes if e.label == "eastern_bluebird")
        assert entry.first_observed_timing_status == "comparable"
        assert entry.current_first_observed_date == date(CURRENT_YEAR, 9, 10)
        assert entry.prior_first_observed_date == date(PRIOR_YEAR, 9, 25)
        assert entry.first_observed_day_difference is not None and entry.first_observed_day_difference < 0
        assert entry.first_observed_is_material is True

    def test_inadequate_early_season_coverage_suppresses_the_timing_claim(self, repository: ProductRepository) -> None:
        _fully_monitored_september(repository, year=CURRENT_YEAR)
        _fully_monitored_september(repository, year=PRIOR_YEAR)
        # First observation lands on day 1 of the current period itself --
        # no usable days exist before it, so "first observed" cannot
        # honestly be distinguished from "monitoring just started". A real,
        # well-evidenced *activity* increase (10 of 30 presence days vs. 2
        # of 30 -- an 8/30 ~ 0.27 rate difference, clearing the 0.25 floor)
        # makes this taxon eligible for `notable_species_changes` on
        # activity grounds alone, so the timing suppression below is a
        # genuine, non-vacuous check, not merely absence from a bounded list.
        _confirmed_days(
            repository, prefix="hb-cur", year=CURRENT_YEAR,
            days=list(range(1, 11)), label="eastern_bluebird",
        )
        _confirmed_days(
            repository, prefix="hb-pri", year=PRIOR_YEAR, days=[20, 21], label="eastern_bluebird",
        )

        result = repository.place_year_over_year_comparison(
            now=datetime(CURRENT_YEAR, 10, 2, tzinfo=UTC), year=CURRENT_YEAR, month=CURRENT_MONTH,
        )
        entry = next(e for e in result.notable_species_changes if e.label == "eastern_bluebird")
        assert entry.activity_direction == "higher"  # confirms this is a non-vacuous, activity-eligible entry
        assert entry.current_first_observed_date == date(CURRENT_YEAR, 9, 1)
        assert entry.first_observed_timing_status == "insufficient_data"
        assert entry.first_observed_day_difference is None
        assert entry.first_observed_is_material is False


# ---------------------------------------------------------------------------
# C2. Single-taxon comparison (Place Story Deep Dives & Representative
# Evidence v1) -- a Taxon Story header needs one taxon's own comparison even
# when it does not clear `notable_species_changes`'s bounded top-5 ranking.
# Reuses `compute_species_year_over_year_comparisons`'s already-computed,
# unranked result -- never a second per-taxon computation.
# ---------------------------------------------------------------------------


class TestTaxonComparison:
    def test_taxon_param_returns_comparison_even_when_not_notable(self, repository: ProductRepository) -> None:
        _fully_monitored_september(repository, year=CURRENT_YEAR)
        _fully_monitored_september(repository, year=PRIOR_YEAR)
        # Six real, well-evidenced species changes so house_finch's own
        # genuinely stable presence is crowded out of the bounded top-5
        # `notable_species_changes` list purely by `MAX_SPECIES_CHANGES_
        # RETURNED`, not because it lacks a real comparison of its own.
        for label in (
            "blue_jay", "carolina_wren", "american_robin",
            "carolina_chickadee", "tufted_titmouse", "downy_woodpecker",
        ):
            _confirmed_days(repository, prefix=f"{label}-cur", year=CURRENT_YEAR, days=list(range(1, 17)), label=label)
            _confirmed_days(repository, prefix=f"{label}-pri", year=PRIOR_YEAR, days=list(range(1, 5)), label=label)
        _confirmed_days(repository, prefix="stable-cur", year=CURRENT_YEAR, days=list(range(1, 11)), label="house_finch")
        _confirmed_days(repository, prefix="stable-pri", year=PRIOR_YEAR, days=list(range(1, 10)), label="house_finch")

        result = repository.place_year_over_year_comparison(
            now=datetime(CURRENT_YEAR, 10, 2, tzinfo=UTC), year=CURRENT_YEAR, month=CURRENT_MONTH,
            taxon="house_finch",
        )
        assert "house_finch" not in {entry.label for entry in result.notable_species_changes}, (
            "fixture invariant broken: house_finch must NOT be notable for this test to be non-vacuous"
        )
        assert result.taxon_comparison is not None
        assert result.taxon_comparison.label == "house_finch"
        assert result.taxon_comparison.status == "no_material_difference"

    def test_taxon_param_accepts_display_name_input(self, repository: ProductRepository) -> None:
        _fully_monitored_september(repository, year=CURRENT_YEAR)
        _fully_monitored_september(repository, year=PRIOR_YEAR)
        _confirmed_days(repository, prefix="cur", year=CURRENT_YEAR, days=list(range(1, 17)), label="northern_cardinal")
        _confirmed_days(repository, prefix="pri", year=PRIOR_YEAR, days=list(range(1, 5)), label="northern_cardinal")

        result = repository.place_year_over_year_comparison(
            now=datetime(CURRENT_YEAR, 10, 2, tzinfo=UTC), year=CURRENT_YEAR, month=CURRENT_MONTH,
            taxon="Northern Cardinal",
        )
        assert result.taxon_comparison is not None
        assert result.taxon_comparison.label == "northern_cardinal"
        assert result.taxon_comparison.activity_direction == "higher"

    def test_taxon_with_no_data_in_either_period_abstains_honestly(self, repository: ProductRepository) -> None:
        _fully_monitored_september(repository, year=CURRENT_YEAR)
        _fully_monitored_september(repository, year=PRIOR_YEAR)

        result = repository.place_year_over_year_comparison(
            now=datetime(CURRENT_YEAR, 10, 2, tzinfo=UTC), year=CURRENT_YEAR, month=CURRENT_MONTH,
            taxon="northern_cardinal",
        )
        assert result.taxon_comparison is None

    def test_unknown_taxon_input_abstains_rather_than_erroring(self, repository: ProductRepository) -> None:
        result = repository.place_year_over_year_comparison(
            now=datetime(CURRENT_YEAR, 10, 2, tzinfo=UTC), year=CURRENT_YEAR, month=CURRENT_MONTH,
            taxon="not-a-real-taxonomy-label",
        )
        assert result.taxon_comparison is None

    def test_omitting_taxon_leaves_taxon_comparison_none(self, repository: ProductRepository) -> None:
        _fully_monitored_september(repository, year=CURRENT_YEAR)
        _fully_monitored_september(repository, year=PRIOR_YEAR)
        _confirmed_days(repository, prefix="cur", year=CURRENT_YEAR, days=list(range(1, 17)))
        _confirmed_days(repository, prefix="pri", year=PRIOR_YEAR, days=list(range(1, 5)))

        result = repository.place_year_over_year_comparison(
            now=datetime(CURRENT_YEAR, 10, 2, tzinfo=UTC), year=CURRENT_YEAR, month=CURRENT_MONTH,
        )
        assert result.taxon_comparison is None


# ---------------------------------------------------------------------------
# D. Truth / correction safety
# ---------------------------------------------------------------------------


class TestCorrectionSafety:
    def test_reviewed_species_correction_changes_the_very_next_call(self, repository: ProductRepository) -> None:
        _fully_monitored_september(repository, year=CURRENT_YEAR)
        _fully_monitored_september(repository, year=PRIOR_YEAR)
        _confirmed_days(repository, prefix="cur", year=CURRENT_YEAR, days=list(range(1, 17)), label="northern_cardinal")
        _confirmed_days(repository, prefix="pri", year=PRIOR_YEAR, days=list(range(1, 5)), label="northern_cardinal")

        before = repository.place_year_over_year_comparison(
            now=datetime(CURRENT_YEAR, 10, 2, tzinfo=UTC), year=CURRENT_YEAR, month=CURRENT_MONTH,
        )
        before_labels = {entry.label for entry in before.notable_species_changes}
        assert "northern_cardinal" in before_labels

        # A reviewer corrects every current-year cardinal Visit to blue_jay.
        for i in range(16):
            _confirm(repository, visit_id=f"cur-{i}", label="blue_jay")

        after = repository.place_year_over_year_comparison(
            now=datetime(CURRENT_YEAR, 10, 2, tzinfo=UTC), year=CURRENT_YEAR, month=CURRENT_MONTH,
        )
        after_labels = {entry.label for entry in after.notable_species_changes}
        assert "northern_cardinal" not in after_labels, "correction did not propagate off the old label"
        assert "blue_jay" in after_labels, "correction did not propagate onto the new label"

    def test_rejecting_a_visit_removes_it_from_the_comparison(self, repository: ProductRepository) -> None:
        _fully_monitored_september(repository, year=CURRENT_YEAR)
        _fully_monitored_september(repository, year=PRIOR_YEAR)
        _confirmed_days(repository, prefix="cur", year=CURRENT_YEAR, days=list(range(1, 17)))
        _confirmed_days(repository, prefix="pri", year=PRIOR_YEAR, days=list(range(1, 5)))

        before = repository.place_year_over_year_comparison(
            now=datetime(CURRENT_YEAR, 10, 2, tzinfo=UTC), year=CURRENT_YEAR, month=CURRENT_MONTH,
        )
        assert before.place.current_period.confirmed_wildlife_visit_count == 16

        for i in range(16):
            _confirm(repository, visit_id=f"cur-{i}", label="false_positive")

        after = repository.place_year_over_year_comparison(
            now=datetime(CURRENT_YEAR, 10, 2, tzinfo=UTC), year=CURRENT_YEAR, month=CURRENT_MONTH,
        )
        assert after.place.current_period.confirmed_wildlife_visit_count == 0

    def test_archived_stream_history_remains_reachable(self, repository: ProductRepository) -> None:
        """Long-term Place memory must not silently lose legitimate
        history merely because a Stream is now archived (see `place_story`'s
        identical, deliberate default -- this milestone reuses it, not
        Today/Bird Log's current-active-observatory one)."""

        _fully_monitored_september(repository, year=CURRENT_YEAR)
        _fully_monitored_september(repository, year=PRIOR_YEAR)
        _confirmed_days(repository, prefix="cur", year=CURRENT_YEAR, days=list(range(1, 17)))
        _confirmed_days(repository, prefix="pri", year=PRIOR_YEAR, days=list(range(1, 5)))

        before = repository.place_year_over_year_comparison(
            now=datetime(CURRENT_YEAR, 10, 2, tzinfo=UTC), year=CURRENT_YEAR, month=CURRENT_MONTH,
        )
        assert before.place.status == "comparable"

        with repository.session_factory() as session:
            with session.begin():
                source = session.get(CameraSourceModel, SOURCE_A)
                assert source is not None
                source.status = "archived"

        after = repository.place_year_over_year_comparison(
            now=datetime(CURRENT_YEAR, 10, 2, tzinfo=UTC), year=CURRENT_YEAR, month=CURRENT_MONTH,
        )
        assert after.place.status == before.place.status
        assert after.place.overall_activity == before.place.overall_activity
        assert after.place.current_period.confirmed_wildlife_visit_count == before.place.current_period.confirmed_wildlife_visit_count


# ---------------------------------------------------------------------------
# E. Multi-camera duplicate safety
# ---------------------------------------------------------------------------


class TestMultiCameraDuplicateSafety:
    def test_associated_cross_camera_encounter_counts_once(self, repository: ProductRepository) -> None:
        _cover_days(repository, start=date(CURRENT_YEAR, 9, 1), days=30, stream_id=STREAM_A, source_id=SOURCE_A)
        _cover_days(repository, start=date(CURRENT_YEAR, 9, 1), days=30, stream_id=STREAM_B, source_id=SOURCE_B)
        _fully_monitored_september(repository, year=PRIOR_YEAR)

        # One real bird, seen by both cameras seconds apart at the same
        # Area -- the cross-camera association engine's own established
        # "associated" shape, directly seeded exactly like test_multi_
        # camera_place_experience_scenario.py's own precedent.
        _add_visit(repository, visit_id="a-cardinal", at=datetime(CURRENT_YEAR, 9, 5, 10, 0, 0, tzinfo=UTC), stream_id=STREAM_A, zone_id=ZONE_A)
        _confirm(repository, visit_id="a-cardinal", label="northern_cardinal")
        _add_visit(repository, visit_id="b-cardinal", at=datetime(CURRENT_YEAR, 9, 5, 10, 0, 4, tzinfo=UTC), stream_id=STREAM_B, zone_id=ZONE_B)
        _confirm(repository, visit_id="b-cardinal", label="northern_cardinal")
        with repository.session_factory() as session:
            with session.begin():
                session.add(CrossCameraVisitAssociationModel(
                    id="yoy-cross-camera-association-1",
                    primary_visit_id=min("a-cardinal", "b-cardinal"),
                    secondary_visit_id=max("a-cardinal", "b-cardinal"),
                    tier="associated", overlap_ms=0, gap_ms=4_000, spatial_signal="matching_area_name",
                    multi_subject=False, engine_version="cross-camera-association-v1",
                    created_at=datetime(CURRENT_YEAR, 9, 5, tzinfo=UTC), updated_at=datetime(CURRENT_YEAR, 9, 5, tzinfo=UTC),
                ))
        _confirmed_days(repository, prefix="pri", year=PRIOR_YEAR, days=list(range(1, 5)))

        result = repository.place_year_over_year_comparison(
            now=datetime(CURRENT_YEAR, 10, 2, tzinfo=UTC), year=CURRENT_YEAR, month=CURRENT_MONTH,
        )
        assert result.place.current_period.confirmed_wildlife_visit_count == 1, (
            "one real encounter seen by two cameras must count once, not twice"
        )

    def test_independent_simultaneous_animals_both_count(self, repository: ProductRepository) -> None:
        _cover_days(repository, start=date(CURRENT_YEAR, 9, 1), days=30, stream_id=STREAM_A, source_id=SOURCE_A)
        _cover_days(repository, start=date(CURRENT_YEAR, 9, 1), days=30, stream_id=STREAM_B, source_id=SOURCE_B)
        _fully_monitored_september(repository, year=PRIOR_YEAR)

        # Two different species, same instant, different cameras, no
        # cross-camera association row -- two real, independent encounters.
        _add_visit(repository, visit_id="a-cardinal", at=datetime(CURRENT_YEAR, 9, 5, 10, tzinfo=UTC), stream_id=STREAM_A, zone_id=ZONE_A)
        _confirm(repository, visit_id="a-cardinal", label="northern_cardinal")
        _add_visit(repository, visit_id="b-jay", at=datetime(CURRENT_YEAR, 9, 5, 10, tzinfo=UTC), stream_id=STREAM_B, zone_id=ZONE_B)
        _confirm(repository, visit_id="b-jay", label="blue_jay")
        _confirmed_days(repository, prefix="pri", year=PRIOR_YEAR, days=list(range(1, 5)))

        result = repository.place_year_over_year_comparison(
            now=datetime(CURRENT_YEAR, 10, 2, tzinfo=UTC), year=CURRENT_YEAR, month=CURRENT_MONTH,
        )
        assert result.place.current_period.confirmed_wildlife_visit_count == 2


# ---------------------------------------------------------------------------
# G. Real HTTP surface
# ---------------------------------------------------------------------------


class TestHttpRoundTrip:
    def test_api_round_trip(self, repository: ProductRepository) -> None:
        # Uses PRIOR_YEAR/PRIOR_YEAR-1 (not CURRENT_YEAR/PRIOR_YEAR) so both
        # compared Septembers are guaranteed fully elapsed regardless of the
        # real wall-clock date this test happens to run on -- the API route
        # has no `now=` override seam (unlike the repository-level tests
        # above), so it always resolves "is this month complete" against
        # real `datetime.now()`.
        request_year, comparison_prior_year = PRIOR_YEAR, PRIOR_YEAR - 1
        _fully_monitored_september(repository, year=request_year)
        _fully_monitored_september(repository, year=comparison_prior_year)
        _confirmed_days(repository, prefix="cur", year=request_year, days=list(range(1, 17)))
        _confirmed_days(repository, prefix="pri", year=comparison_prior_year, days=list(range(1, 5)))

        client = LegacyAuthenticatedSyncTestClient(app)
        response = client.get("/api/place/year-over-year", params={"year": request_year, "month": CURRENT_MONTH})
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["place"]["status"] == "comparable"
        assert body["place"]["overall_activity"] == "higher"
        assert body["place"]["current_period"]["start_date"] == f"{request_year}-09-01"
        assert body["place"]["prior_period"]["start_date"] == f"{comparison_prior_year}-09-01"
        labels = {entry["label"] for entry in body["notable_species_changes"]}
        assert "northern_cardinal" in labels

    def test_api_rejects_a_future_month_with_400(self, repository: ProductRepository) -> None:
        client = LegacyAuthenticatedSyncTestClient(app)
        response = client.get("/api/place/year-over-year", params={"year": CURRENT_YEAR + 5, "month": 1})
        assert response.status_code == 400

    def test_api_requires_year_and_month_together(self, repository: ProductRepository) -> None:
        client = LegacyAuthenticatedSyncTestClient(app)
        response = client.get("/api/place/year-over-year", params={"year": CURRENT_YEAR})
        assert response.status_code == 400

    def test_api_taxon_param_round_trip(self, repository: ProductRepository) -> None:
        request_year, comparison_prior_year = PRIOR_YEAR, PRIOR_YEAR - 1
        _fully_monitored_september(repository, year=request_year)
        _fully_monitored_september(repository, year=comparison_prior_year)
        _confirmed_days(repository, prefix="cur", year=request_year, days=list(range(1, 17)), label="northern_cardinal")
        _confirmed_days(repository, prefix="pri", year=comparison_prior_year, days=list(range(1, 5)), label="northern_cardinal")

        client = LegacyAuthenticatedSyncTestClient(app)
        response = client.get(
            "/api/place/year-over-year",
            params={"year": request_year, "month": CURRENT_MONTH, "taxon": "Northern Cardinal"},
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["taxon_comparison"] is not None
        assert body["taxon_comparison"]["label"] == "northern_cardinal"
        assert body["taxon_comparison"]["activity_direction"] == "higher"

    def test_api_omits_taxon_comparison_when_taxon_not_requested(self, repository: ProductRepository) -> None:
        client = LegacyAuthenticatedSyncTestClient(app)
        response = client.get("/api/place/year-over-year")
        assert response.status_code == 200, response.text
        assert response.json()["taxon_comparison"] is None

    def test_api_defaults_to_the_current_month_with_no_params(self, repository: ProductRepository) -> None:
        # No fixture history seeded beyond whatever this repository's own
        # unconditional demo seed provides -- this test only proves the
        # endpoint resolves a default period and returns a well-formed,
        # honest response, never a crash; it deliberately does not assert
        # which specific status that resolves to (demo-seed dates are not
        # this test's concern -- see TestPlaceComparison/TestHistorySufficiency
        # for the specific-status proofs, which fully control their own
        # fixture history).
        client = LegacyAuthenticatedSyncTestClient(app)
        response = client.get("/api/place/year-over-year")
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["place"]["status"] in (
            "comparable", "no_material_difference", "insufficient_prior_history",
            "insufficient_current_coverage", "insufficient_prior_coverage", "partial_period",
        )
        assert body["place"]["current_period"]["start_date"] is not None


# ---------------------------------------------------------------------------
# Performance: bounded query count, independent of unrelated history depth
# ---------------------------------------------------------------------------


def _count_queries(engine, fn) -> int:  # type: ignore[no-untyped-def]
    """Mirrors tests/test_place_activity_report_repository.py's own
    `_count_taxonomy_queries` harness shape."""

    count = 0

    def _before_cursor_execute(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        nonlocal count
        count += 1

    event.listen(engine, "before_cursor_execute", _before_cursor_execute)
    try:
        fn()
    finally:
        event.remove(engine, "before_cursor_execute", _before_cursor_execute)
    return count


class TestPerformance:
    def test_query_count_does_not_grow_with_unrelated_historical_depth(self, repository: ProductRepository) -> None:
        _fully_monitored_september(repository, year=CURRENT_YEAR)
        _fully_monitored_september(repository, year=PRIOR_YEAR)
        _confirmed_days(repository, prefix="cur", year=CURRENT_YEAR, days=list(range(1, 17)))
        _confirmed_days(repository, prefix="pri", year=PRIOR_YEAR, days=list(range(1, 5)))

        engine = repository.session_factory().get_bind()  # type: ignore[attr-defined]
        small_count = _count_queries(
            engine,
            lambda: repository.place_year_over_year_comparison(
                now=datetime(CURRENT_YEAR, 10, 2, tzinfo=UTC), year=CURRENT_YEAR, month=CURRENT_MONTH,
            ),
        )

        # Three unrelated years of monthly monitoring plus a confirmed
        # Visit in every one of those months -- history this milestone's
        # own comparison never needs to touch (it only ever queries the
        # two ~30-day compared periods, per `_year_over_year_window_visit_
        # facts`'s own bounded-by-period-length contract).
        for year in (2022, 2023, 2024):
            for month in range(1, 13):
                _cover_days(repository, start=date(year, month, 1), days=28)
                visit_id = f"noise-{year}-{month}"
                _add_visit(repository, visit_id=visit_id, at=datetime(year, month, 2, 10, tzinfo=UTC))
                _confirm(repository, visit_id=visit_id, label="house_finch")
        large_count = _count_queries(
            engine,
            lambda: repository.place_year_over_year_comparison(
                now=datetime(CURRENT_YEAR, 10, 2, tzinfo=UTC), year=CURRENT_YEAR, month=CURRENT_MONTH,
            ),
        )
        assert small_count == large_count, (
            f"query count grew with unrelated historical depth: {small_count} -> {large_count}"
        )

    def test_taxon_param_adds_zero_extra_queries(self, repository: ProductRepository) -> None:
        """Place Story Deep Dives & Representative Evidence v1: `taxon=`
        reuses `compute_species_year_over_year_comparisons`'s own already-
        computed, already-in-memory `species_comparisons` list -- a pure
        Python filter, never a second query."""

        _fully_monitored_september(repository, year=CURRENT_YEAR)
        _fully_monitored_september(repository, year=PRIOR_YEAR)
        _confirmed_days(repository, prefix="cur", year=CURRENT_YEAR, days=list(range(1, 17)), label="northern_cardinal")
        _confirmed_days(repository, prefix="pri", year=PRIOR_YEAR, days=list(range(1, 5)), label="northern_cardinal")

        engine = repository.session_factory().get_bind()  # type: ignore[attr-defined]
        without_taxon = _count_queries(
            engine,
            lambda: repository.place_year_over_year_comparison(
                now=datetime(CURRENT_YEAR, 10, 2, tzinfo=UTC), year=CURRENT_YEAR, month=CURRENT_MONTH,
            ),
        )
        with_taxon = _count_queries(
            engine,
            lambda: repository.place_year_over_year_comparison(
                now=datetime(CURRENT_YEAR, 10, 2, tzinfo=UTC), year=CURRENT_YEAR, month=CURRENT_MONTH,
                taxon="northern_cardinal",
            ),
        )
        assert with_taxon == without_taxon, (
            f"taxon= added extra queries: {without_taxon} -> {with_taxon}"
        )
