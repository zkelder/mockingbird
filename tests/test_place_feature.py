"""Place Features & Habitat Change v2 (see docs/place-features-habitat-
change-v2-contract.md).

Covers: the pure before/after window-selection logic
(`mockingbird.analytics.feature_change_comparison`) and the pure yield
computation (`mockingbird.analytics.feature_yield`); the durable Place
Feature repository surface (add/list/update/remove, association resolution,
lifecycle); the durable Place Feature Change Event repository surface (add/
list/update/remove, dual-write reconciliation into the Feature's own
current-state columns); the full detail/summary read bundles, including a
real seeded before/after scenario; and the real HTTP surface (auth-required
mutations, 404s, 422s, 409).
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import select
from starlette.testclient import TestClient

from mockingbird.analytics.conditional_association import compute_conditional_association
from mockingbird.analytics.feature_change_comparison import (
    CANDIDATE_WINDOW_DAYS,
    compute_feature_change_comparison,
)
from mockingbird.analytics.feature_yield import compute_feature_yield
from mockingbird.analytics.place_activity_report import TaxonFact, VisitFact
from mockingbird.api.main import app, configure_repository
from mockingbird.api.schemas import (
    CurrentUser,
    PlaceFeatureChangeEventCreate,
    PlaceFeatureChangeEventUpdate,
    PlaceFeatureCreate,
    PlaceFeatureUpdate,
    ReviewCorrectionCreate,
    UserRole,
)
from mockingbird.habitat.place_feature import (
    DERIVED_STATE_EVENT_TYPES,
    PLACE_FEATURE_CHANGE_EVENT_TYPES,
    PLACE_FEATURE_TYPES,
)
from mockingbird.repository.product_repository import PlaceFeatureHasHistoryError, ProductRepository
from mockingbird.storage.models import (
    CameraSourceModel,
    EventModel,
    MonitoringExposureIntervalModel,
    StreamModel,
    VisitModel,
    ZoneModel,
)
from tests.conftest import LegacyAuthenticatedSyncTestClient

SOURCE_ID = "source-place-feature"
STREAM_ID = "stream-place-feature"
OTHER_STREAM_ID = "stream-place-feature-other"
ZONE_ID = "zone-place-feature-feeder"
OTHER_ZONE_ID = "zone-place-feature-other-source"


@pytest.fixture
def repository(tmp_path: Path) -> ProductRepository:
    repository = ProductRepository(
        db_url=f"sqlite:///{tmp_path / 'mockingbird.sqlite3'}",
        media_root=tmp_path / "media",
    )
    configure_repository(repository)
    with repository.session_factory() as session:
        with session.begin():
            session.add_all(
                [
                    CameraSourceModel(
                        id=SOURCE_ID,
                        name="Feature fixture camera",
                        kind="manual_upload",
                        status="connected",
                        description="Place Features fixture.",
                    ),
                ]
            )
            session.add_all(
                [
                    StreamModel(
                        id=STREAM_ID,
                        source_id=SOURCE_ID,
                        name="Feature fixture stream",
                        description="Place Features fixture.",
                        is_live=False,
                    ),
                    StreamModel(
                        id=OTHER_STREAM_ID,
                        source_id=SOURCE_ID,
                        name="Feature fixture stream (unlinked)",
                        description="Place Features fixture.",
                        is_live=False,
                    ),
                ]
            )
            session.add(
                ZoneModel(
                    id=ZONE_ID,
                    stream_id=STREAM_ID,
                    name="Feeder",
                    zone_type="feeder",
                    polygon_json="[]",
                    is_active=True,
                    monitoring_policy_json=None,
                )
            )
    yield repository
    configure_repository(None)


def _acting_user() -> CurrentUser:
    return CurrentUser(
        id="user-test-admin",
        display_name="Test Admin",
        login_identity="test-admin",
        role=UserRole.administrator,
        enabled=True,
    )


def _add_visit(
    repository: ProductRepository, *, visit_id: str, at: datetime, stream_id: str = STREAM_ID,
    zone_id: str | None = ZONE_ID,
) -> None:
    event_id = f"event-{visit_id}"
    with repository.session_factory() as session:
        with session.begin():
            session.add(
                EventModel(
                    id=event_id,
                    stream_id=stream_id,
                    title=f"Place Feature fixture {visit_id}",
                    event_type="manual_media_import",
                    started_at=at,
                    ended_at=at + timedelta(seconds=20),
                    primary_zone_id=zone_id,
                    review_status="needs_review",
                )
            )
            session.add(
                VisitModel(
                    id=visit_id,
                    event_id=event_id,
                    subject_label="unknown_bird",
                    species_guess=None,
                    confidence=None,
                    reviewed_label=None,
                    review_status="needs_review",
                    representative_media_path=None,
                    zone_id=zone_id,
                    is_superseded=False,
                )
            )


def _confirm(repository: ProductRepository, *, visit_id: str, label: str = "northern_cardinal") -> None:
    repository.create_review_label(
        ReviewCorrectionCreate(target_type="visit", target_id=visit_id, label=label, review_origin="human")
    )


def _add_exposure(
    repository: ProductRepository, *, interval_id: str, started_at: datetime, ended_at: datetime,
    stream_id: str = STREAM_ID,
) -> None:
    with repository.session_factory() as session:
        with session.begin():
            session.add(
                MonitoringExposureIntervalModel(
                    id=interval_id,
                    stream_id=stream_id,
                    source_id=SOURCE_ID,
                    runtime_generation_id=f"generation-{interval_id}",
                    started_at=started_at,
                    last_confirmed_fresh_at=ended_at,
                    ended_at=ended_at,
                    close_reason="provider_failure",
                    created_at=started_at,
                    updated_at=ended_at,
                )
            )


def _cover_days(repository: ProductRepository, *, start: date, days: int, stream_id: str = STREAM_ID) -> None:
    """Seed one full 24-hour-healthy exposure interval per day, comfortably
    clearing every "usable day" floor in this codebase."""

    for offset in range(days):
        day = start + timedelta(days=offset)
        started_at = datetime(day.year, day.month, day.day, tzinfo=UTC)
        _add_exposure(
            repository, interval_id=f"exposure-{stream_id}-{day.isoformat()}",
            started_at=started_at, ended_at=started_at + timedelta(hours=23),
            stream_id=stream_id,
        )


# --- Pure: feature_change_comparison ---------------------------------------


def _dates(*days: int, month: int = 1, year: int = 2026) -> set[date]:
    return {date(year, month, day) for day in days}


def test_compute_feature_change_comparison_too_soon_when_smallest_window_has_not_elapsed() -> None:
    effective = date(2026, 6, 10)
    today = effective + timedelta(days=3)  # fewer than 7 days have passed
    result = compute_feature_change_comparison(
        presence_dates=set(), usable_dates=set(), effective_date=effective, today=today,
    )
    assert result.maturity == "too_soon"
    assert result.window_days is None
    assert result.association is None


def test_compute_feature_change_comparison_comparable_at_smallest_window() -> None:
    effective = date(2026, 6, 10)
    today = effective + timedelta(days=7)
    pre = {effective - timedelta(days=offset) for offset in range(1, 8)}
    post = {effective + timedelta(days=offset) for offset in range(7)}
    usable_dates = pre | post
    # Presence every post-day, none pre-day -- an unambiguous "more common".
    result = compute_feature_change_comparison(
        presence_dates=post, usable_dates=usable_dates, effective_date=effective, today=today,
    )
    assert result.maturity == "comparable"
    assert result.window_days == 7
    assert result.association is not None
    assert result.association.status == "more_common_under_condition"


def test_compute_feature_change_comparison_escalates_to_larger_window_when_needed() -> None:
    """Only 3 usable days exist within the 7-day window on each side (below
    the 5-day floor) -- but the full 30-day windows clear it, coarsely
    covered -- so the comparison should escalate to window_days=30 and
    report "early_signal", never silently fail."""

    effective = date(2026, 6, 20)
    today = effective + timedelta(days=30)
    # Usable on only 3 days within the 7- and 14-day pre/post windows...
    thin_pre = {effective - timedelta(days=offset) for offset in range(1, 4)}
    thin_post = {effective + timedelta(days=offset) for offset in range(3)}
    # ...plus 6 more days each side, but only beyond day 14 -- outside the
    # 7- and 14-day candidate windows, inside only the 30-day one.
    wide_pre = {effective - timedelta(days=offset) for offset in range(15, 21)}
    wide_post = {effective + timedelta(days=offset) for offset in range(15, 21)}
    usable_dates = thin_pre | thin_post | wide_pre | wide_post
    result = compute_feature_change_comparison(
        presence_dates=set(), usable_dates=usable_dates, effective_date=effective, today=today,
    )
    assert result.maturity == "early_signal"
    assert result.window_days == 30


def test_compute_feature_change_comparison_insufficient_coverage_when_even_largest_window_fails() -> None:
    effective = date(2026, 6, 1)
    today = effective + timedelta(days=30)
    result = compute_feature_change_comparison(
        presence_dates=set(), usable_dates=set(), effective_date=effective, today=today,
    )
    assert result.maturity == "insufficient_coverage"
    assert result.association is None


def test_compute_feature_change_comparison_lower_after() -> None:
    effective = date(2026, 6, 10)
    today = effective + timedelta(days=7)
    pre = {effective - timedelta(days=offset) for offset in range(1, 8)}
    post = {effective + timedelta(days=offset) for offset in range(7)}
    result = compute_feature_change_comparison(
        presence_dates=pre, usable_dates=pre | post, effective_date=effective, today=today,
    )
    assert result.association.status == "less_common_under_condition"


def test_compute_feature_change_comparison_matches_conditional_association_primitive() -> None:
    """The engine must not reimplement its own statistics -- its
    `association` output for a chosen window is identical to calling the
    shared primitive directly with the same date sets."""

    effective = date(2026, 6, 10)
    today = effective + timedelta(days=7)
    pre = {effective - timedelta(days=offset) for offset in range(1, 8)}
    post = {effective + timedelta(days=offset) for offset in range(7)}
    presence = {effective + timedelta(days=1), effective + timedelta(days=2)}
    result = compute_feature_change_comparison(
        presence_dates=presence, usable_dates=pre | post, effective_date=effective, today=today,
    )
    direct = compute_conditional_association(presence, usable_dates=pre | post, condition_dates=post)
    assert result.association == direct


# --- Pure: feature_yield -----------------------------------------------------


def _taxon(label: str) -> TaxonFact:
    return TaxonFact(label=label, display_name=label.title(), category="bird", is_species=True)


def _visit(visit_id: str, *, at: datetime, label: str | None) -> VisitFact:
    return VisitFact(
        visit_id=visit_id,
        zone_id=ZONE_ID,
        zone_name="Feeder",
        activity_started_at=at,
        resolution="reviewed" if label else "needs_review",
        confirmed_taxon=_taxon(label) if label else None,
    )


def test_compute_feature_yield_insufficient_below_two_hours() -> None:
    result = compute_feature_yield([], monitored_seconds=3599.0)
    assert result.data_sufficient is False
    assert result.visits_per_monitored_hour is None


def test_compute_feature_yield_rate_and_diversity() -> None:
    base = datetime(2026, 6, 1, tzinfo=UTC)
    visits = [
        _visit("v1", at=base, label="northern_cardinal"),
        _visit("v2", at=base + timedelta(minutes=10), label="northern_cardinal"),
        _visit("v3", at=base + timedelta(minutes=20), label="blue_jay"),
        _visit("v4", at=base + timedelta(minutes=30), label=None),  # not confirmed -- excluded
    ]
    result = compute_feature_yield(visits, monitored_seconds=3600.0 * 3)
    assert result.confirmed_wildlife_visit_count == 3
    assert result.distinct_taxon_count == 2
    assert result.data_sufficient is True
    assert result.visits_per_monitored_hour == pytest.approx(1.0)


def test_compute_feature_yield_none_monitored_seconds_is_honest_absence() -> None:
    result = compute_feature_yield([], monitored_seconds=None)
    assert result.monitored_seconds is None
    assert result.data_sufficient is False


# --- Repository: Feature CRUD -------------------------------------------------


def test_add_and_list_place_features(repository: ProductRepository) -> None:
    repository.add_place_feature(
        PlaceFeatureCreate(feature_type="feeder", name="Sunflower feeder"), acting_user=_acting_user()
    )
    repository.add_place_feature(
        PlaceFeatureCreate(feature_type="water", name="Bird bath"), acting_user=_acting_user()
    )
    features = repository.list_place_features()
    assert {f.name for f in features} == {"Sunflower feeder", "Bird bath"}
    feeder = next(f for f in features if f.name == "Sunflower feeder")
    assert feeder.is_active is True
    assert feeder.information_class == "reviewed"
    assert feeder.provenance == "user_manual_entry"


def test_place_features_absence_is_an_empty_list(repository: ProductRepository) -> None:
    assert repository.list_place_features() == []


def test_add_place_feature_with_zone_resolves_source_id(repository: ProductRepository) -> None:
    feature = repository.add_place_feature(
        PlaceFeatureCreate(feature_type="feeder", name="Sunflower feeder", zone_id=ZONE_ID),
        acting_user=_acting_user(),
    )
    assert feature.zone_id == ZONE_ID
    assert feature.source_id == SOURCE_ID


def test_add_place_feature_with_mismatched_source_and_zone_is_rejected(repository: ProductRepository) -> None:
    with pytest.raises(ValueError):
        repository.add_place_feature(
            PlaceFeatureCreate(
                feature_type="feeder", name="Sunflower feeder", zone_id=ZONE_ID, source_id="not-the-real-source",
            ),
            acting_user=_acting_user(),
        )


def test_add_place_feature_with_unknown_zone_is_rejected(repository: ProductRepository) -> None:
    with pytest.raises(ValueError):
        repository.add_place_feature(
            PlaceFeatureCreate(feature_type="feeder", name="Sunflower feeder", zone_id="zone-does-not-exist"),
            acting_user=_acting_user(),
        )


def test_add_place_feature_with_installed_date_seeds_added_event(repository: ProductRepository) -> None:
    feature = repository.add_place_feature(
        PlaceFeatureCreate(feature_type="feeder", name="Sunflower feeder", installed_date=date(2026, 3, 15)),
        acting_user=_acting_user(),
    )
    events = repository.list_place_feature_change_events(feature_id=feature.id)
    assert len(events) == 1
    assert events[0].event_type == "added"
    assert events[0].effective_date == date(2026, 3, 15)


def test_add_place_feature_without_installed_date_seeds_no_event(repository: ProductRepository) -> None:
    feature = repository.add_place_feature(
        PlaceFeatureCreate(feature_type="feeder", name="Sunflower feeder"), acting_user=_acting_user()
    )
    assert repository.list_place_feature_change_events(feature_id=feature.id) == []


def test_update_place_feature_note_clearing_and_rename(repository: ProductRepository) -> None:
    feature = repository.add_place_feature(
        PlaceFeatureCreate(feature_type="feeder", name="Feeder", note="Original note"),
        acting_user=_acting_user(),
    )
    updated = repository.update_place_feature(
        feature.id, PlaceFeatureUpdate(name="Sunflower feeder", note=""), acting_user=_acting_user()
    )
    assert updated.name == "Sunflower feeder"
    assert updated.note is None


def test_update_place_feature_zone_id_wins_and_rederives_source(repository: ProductRepository) -> None:
    feature = repository.add_place_feature(
        PlaceFeatureCreate(feature_type="feeder", name="Feeder"), acting_user=_acting_user()
    )
    updated = repository.update_place_feature(
        feature.id, PlaceFeatureUpdate(zone_id=ZONE_ID), acting_user=_acting_user()
    )
    assert updated.zone_id == ZONE_ID
    assert updated.source_id == SOURCE_ID


def test_update_place_feature_bare_source_id_clears_existing_zone(repository: ProductRepository) -> None:
    feature = repository.add_place_feature(
        PlaceFeatureCreate(feature_type="feeder", name="Feeder", zone_id=ZONE_ID), acting_user=_acting_user()
    )
    updated = repository.update_place_feature(
        feature.id, PlaceFeatureUpdate(source_id=SOURCE_ID), acting_user=_acting_user()
    )
    assert updated.source_id == SOURCE_ID
    assert updated.zone_id is None


def test_update_place_feature_clear_source_id_clears_zone_too(repository: ProductRepository) -> None:
    feature = repository.add_place_feature(
        PlaceFeatureCreate(feature_type="feeder", name="Feeder", zone_id=ZONE_ID), acting_user=_acting_user()
    )
    updated = repository.update_place_feature(
        feature.id, PlaceFeatureUpdate(source_id=""), acting_user=_acting_user()
    )
    assert updated.source_id is None
    assert updated.zone_id is None


def test_update_missing_place_feature_returns_none(repository: ProductRepository) -> None:
    assert repository.update_place_feature(
        "feature-missing", PlaceFeatureUpdate(name="X"), acting_user=_acting_user()
    ) is None


def test_update_place_feature_installed_date_clear_flag(repository: ProductRepository) -> None:
    feature = repository.add_place_feature(
        PlaceFeatureCreate(feature_type="feeder", name="Feeder", installed_date=date(2026, 1, 1)),
        acting_user=_acting_user(),
    )
    updated = repository.update_place_feature(
        feature.id, PlaceFeatureUpdate(clear_installed_date=True), acting_user=_acting_user()
    )
    assert updated.installed_date is None


def test_remove_place_feature_without_history_succeeds(repository: ProductRepository) -> None:
    feature = repository.add_place_feature(
        PlaceFeatureCreate(feature_type="feeder", name="Feeder"), acting_user=_acting_user()
    )
    assert repository.remove_place_feature(feature.id, acting_user=_acting_user()) is True
    assert repository.list_place_features() == []


def test_remove_missing_place_feature_returns_false(repository: ProductRepository) -> None:
    assert repository.remove_place_feature("feature-missing", acting_user=_acting_user()) is False


def test_remove_place_feature_with_history_is_blocked(repository: ProductRepository) -> None:
    feature = repository.add_place_feature(
        PlaceFeatureCreate(feature_type="feeder", name="Feeder", installed_date=date(2026, 1, 1)),
        acting_user=_acting_user(),
    )
    with pytest.raises(PlaceFeatureHasHistoryError):
        repository.remove_place_feature(feature.id, acting_user=_acting_user())
    # Blocked deletion must not have partially removed anything.
    assert len(repository.list_place_features()) == 1


# --- Repository: Change Event CRUD + dual-write reconciliation --------------


def test_add_change_event_for_unknown_feature_is_rejected(repository: ProductRepository) -> None:
    with pytest.raises(ValueError):
        repository.add_place_feature_change_event(
            PlaceFeatureChangeEventCreate(
                feature_id="feature-does-not-exist", event_type="modified", effective_date=date(2026, 1, 1),
            ),
            acting_user=_acting_user(),
        )


def test_add_place_level_change_event_without_feature_id(repository: ProductRepository) -> None:
    event = repository.add_place_feature_change_event(
        PlaceFeatureChangeEventCreate(
            feature_id=None, event_type="vegetation_changed", effective_date=date(2026, 4, 2),
            note="Changed mowing practice",
        ),
        acting_user=_acting_user(),
    )
    assert event.feature_id is None
    all_events = repository.list_place_feature_change_events()
    assert any(e.id == event.id for e in all_events)


def test_removed_event_deactivates_feature(repository: ProductRepository) -> None:
    feature = repository.add_place_feature(
        PlaceFeatureCreate(feature_type="feeder", name="Feeder"), acting_user=_acting_user()
    )
    repository.add_place_feature_change_event(
        PlaceFeatureChangeEventCreate(feature_id=feature.id, event_type="removed", effective_date=date(2026, 5, 1)),
        acting_user=_acting_user(),
    )
    reloaded = repository.list_place_features()[0]
    assert reloaded.is_active is False
    assert reloaded.removed_date == date(2026, 5, 1)


def test_deleting_only_removed_event_does_not_reactivate(repository: ProductRepository) -> None:
    """Deliberate, documented one-directional behavior -- see
    `ProductRepository._recompute_feature_derived_state`."""

    feature = repository.add_place_feature(
        PlaceFeatureCreate(feature_type="feeder", name="Feeder"), acting_user=_acting_user()
    )
    event = repository.add_place_feature_change_event(
        PlaceFeatureChangeEventCreate(feature_id=feature.id, event_type="removed", effective_date=date(2026, 5, 1)),
        acting_user=_acting_user(),
    )
    repository.remove_place_feature_change_event(event.id, acting_user=_acting_user())
    reloaded = repository.list_place_features()[0]
    assert reloaded.is_active is False
    assert reloaded.removed_date == date(2026, 5, 1)


def test_food_changed_event_updates_feeder_food_type(repository: ProductRepository) -> None:
    feature = repository.add_place_feature(
        PlaceFeatureCreate(feature_type="feeder", name="Feeder"), acting_user=_acting_user()
    )
    repository.add_place_feature_change_event(
        PlaceFeatureChangeEventCreate(
            feature_id=feature.id, event_type="food_changed", effective_date=date(2026, 5, 1),
            new_value="Black-oil sunflower",
        ),
        acting_user=_acting_user(),
    )
    assert repository.list_place_features()[0].feeder_food_type == "Black-oil sunflower"

    repository.add_place_feature_change_event(
        PlaceFeatureChangeEventCreate(
            feature_id=feature.id, event_type="food_changed", effective_date=date(2026, 7, 1),
            new_value="Safflower",
        ),
        acting_user=_acting_user(),
    )
    assert repository.list_place_features()[0].feeder_food_type == "Safflower"


def test_correcting_food_changed_event_date_reorders_which_is_latest(repository: ProductRepository) -> None:
    feature = repository.add_place_feature(
        PlaceFeatureCreate(feature_type="feeder", name="Feeder"), acting_user=_acting_user()
    )
    early = repository.add_place_feature_change_event(
        PlaceFeatureChangeEventCreate(
            feature_id=feature.id, event_type="food_changed", effective_date=date(2026, 5, 1),
            new_value="Black-oil sunflower",
        ),
        acting_user=_acting_user(),
    )
    repository.add_place_feature_change_event(
        PlaceFeatureChangeEventCreate(
            feature_id=feature.id, event_type="food_changed", effective_date=date(2026, 7, 1), new_value="Safflower",
        ),
        acting_user=_acting_user(),
    )
    assert repository.list_place_features()[0].feeder_food_type == "Safflower"
    # Correcting the earlier event's date to be *after* July 1 makes it the
    # new latest -- derived state must recompute to reflect the correction.
    repository.update_place_feature_change_event(
        early.id, PlaceFeatureChangeEventUpdate(effective_date=date(2026, 8, 1)), acting_user=_acting_user()
    )
    assert repository.list_place_features()[0].feeder_food_type == "Black-oil sunflower"


def test_update_and_remove_change_event(repository: ProductRepository) -> None:
    feature = repository.add_place_feature(
        PlaceFeatureCreate(feature_type="feeder", name="Feeder"), acting_user=_acting_user()
    )
    event = repository.add_place_feature_change_event(
        PlaceFeatureChangeEventCreate(
            feature_id=feature.id, event_type="modified", effective_date=date(2026, 5, 1), note="Original",
        ),
        acting_user=_acting_user(),
    )
    updated = repository.update_place_feature_change_event(
        event.id, PlaceFeatureChangeEventUpdate(note="Corrected"), acting_user=_acting_user()
    )
    assert updated.note == "Corrected"
    assert repository.remove_place_feature_change_event(event.id, acting_user=_acting_user()) is True
    assert repository.list_place_feature_change_events(feature_id=feature.id) == []


def test_update_missing_change_event_returns_none(repository: ProductRepository) -> None:
    result = repository.update_place_feature_change_event(
        "event-missing", PlaceFeatureChangeEventUpdate(note="X"), acting_user=_acting_user()
    )
    assert result is None


def test_remove_missing_change_event_returns_false(repository: ProductRepository) -> None:
    assert repository.remove_place_feature_change_event("event-missing", acting_user=_acting_user()) is False


def test_all_feature_types_and_event_types_are_creatable(repository: ProductRepository) -> None:
    """Every value in the closed vocabularies must round-trip through the
    real repository/schema layer, not just exist as a Python constant."""

    for feature_type in PLACE_FEATURE_TYPES:
        feature = repository.add_place_feature(
            PlaceFeatureCreate(feature_type=feature_type, name=f"Test {feature_type}"),
            acting_user=_acting_user(),
        )
        for event_type in PLACE_FEATURE_CHANGE_EVENT_TYPES:
            repository.add_place_feature_change_event(
                PlaceFeatureChangeEventCreate(
                    feature_id=feature.id, event_type=event_type, effective_date=date(2026, 1, 1),
                ),
                acting_user=_acting_user(),
            )
    assert DERIVED_STATE_EVENT_TYPES == {"removed", "food_changed"}


# --- Repository: detail/summary bundles -------------------------------------


def test_feature_detail_missing_feature_is_none(repository: ProductRepository) -> None:
    assert repository.get_place_feature_detail("feature-missing") is None


def test_feature_detail_without_association_has_no_comparison_or_yield(repository: ProductRepository) -> None:
    feature = repository.add_place_feature(
        PlaceFeatureCreate(feature_type="feeder", name="Feeder", installed_date=date(2026, 1, 1)),
        acting_user=_acting_user(),
    )
    now = datetime(2026, 6, 1, tzinfo=UTC)
    detail = repository.get_place_feature_detail(feature.id, now=now, local_timezone=UTC)
    assert len(detail.changes) == 1
    assert detail.changes[0].comparison is None
    assert detail.recent_yield is None


def test_feature_detail_higher_activity_after_change(repository: ProductRepository) -> None:
    feature = repository.add_place_feature(
        PlaceFeatureCreate(feature_type="feeder", name="Sunflower feeder", zone_id=ZONE_ID),
        acting_user=_acting_user(),
    )
    effective = date(2026, 6, 1)
    now = datetime(2026, 6, 8, tzinfo=UTC)
    event = repository.add_place_feature_change_event(
        PlaceFeatureChangeEventCreate(feature_id=feature.id, event_type="added", effective_date=effective),
        acting_user=_acting_user(),
    )
    _cover_days(repository, start=effective - timedelta(days=7), days=14)
    # No confirmed activity before the change; one confirmed Visit on each
    # post-change day -- an unambiguous "more common after."
    for offset in range(7):
        day = effective + timedelta(days=offset)
        visit_id = f"visit-after-{offset}"
        _add_visit(repository, visit_id=visit_id, at=datetime(day.year, day.month, day.day, 10, tzinfo=UTC))
        _confirm(repository, visit_id=visit_id)

    detail = repository.get_place_feature_detail(feature.id, now=now, local_timezone=UTC)
    comparisons = [c for c in detail.changes if c.event.id == event.id]
    assert len(comparisons) == 1
    comparison = comparisons[0].comparison
    assert comparison is not None
    assert comparison.maturity == "comparable"
    assert comparison.status == "more_common_under_condition"
    assert detail.recent_yield is not None
    assert detail.recent_yield.confirmed_wildlife_visit_count > 0


def test_feature_detail_too_soon_before_window_elapses(repository: ProductRepository) -> None:
    feature = repository.add_place_feature(
        PlaceFeatureCreate(feature_type="feeder", name="Feeder", zone_id=ZONE_ID),
        acting_user=_acting_user(),
    )
    effective = date(2026, 6, 1)
    now = datetime(2026, 6, 3, tzinfo=UTC)  # only 2 days have elapsed
    repository.add_place_feature_change_event(
        PlaceFeatureChangeEventCreate(feature_id=feature.id, event_type="added", effective_date=effective),
        acting_user=_acting_user(),
    )
    detail = repository.get_place_feature_detail(feature.id, now=now, local_timezone=UTC)
    assert detail.changes[0].comparison.maturity == "too_soon"


def test_correcting_change_event_date_changes_comparison_on_next_read(repository: ProductRepository) -> None:
    """No cache to invalidate -- a correction is reflected on the very next
    call, matching `PlaceFeatureChangeEventModel`'s "Correction model"."""

    feature = repository.add_place_feature(
        PlaceFeatureCreate(feature_type="feeder", name="Feeder", zone_id=ZONE_ID),
        acting_user=_acting_user(),
    )
    now = datetime(2026, 6, 8, tzinfo=UTC)
    event = repository.add_place_feature_change_event(
        PlaceFeatureChangeEventCreate(feature_id=feature.id, event_type="added", effective_date=date(2026, 6, 1)),
        acting_user=_acting_user(),
    )
    _cover_days(repository, start=date(2026, 5, 20), days=20)
    before = repository.get_place_feature_detail(feature.id, now=now, local_timezone=UTC)
    assert before.changes[0].comparison.maturity == "comparable"

    # Move the effective date to 2 days ago -- now too soon to compare.
    repository.update_place_feature_change_event(
        event.id, PlaceFeatureChangeEventUpdate(effective_date=date(2026, 6, 6)), acting_user=_acting_user()
    )
    after = repository.get_place_feature_detail(feature.id, now=now, local_timezone=UTC)
    assert after.changes[0].comparison.maturity == "too_soon"


def test_features_summary_counts_and_highlight(repository: ProductRepository) -> None:
    now = datetime(2026, 6, 8, tzinfo=UTC)
    active = repository.add_place_feature(
        PlaceFeatureCreate(feature_type="feeder", name="Sunflower feeder", zone_id=ZONE_ID),
        acting_user=_acting_user(),
    )
    repository.add_place_feature(
        PlaceFeatureCreate(feature_type="water", name="Bird bath", is_active=False), acting_user=_acting_user(),
    )
    repository.add_place_feature_change_event(
        PlaceFeatureChangeEventCreate(feature_id=active.id, event_type="replenished", effective_date=date(2026, 6, 7)),
        acting_user=_acting_user(),
    )
    _cover_days(repository, start=now.date() - timedelta(days=7), days=7)
    for offset in range(3):
        day = now.date() - timedelta(days=offset)
        visit_id = f"visit-summary-{offset}"
        _add_visit(repository, visit_id=visit_id, at=datetime(day.year, day.month, day.day, 9, tzinfo=UTC))
        _confirm(repository, visit_id=visit_id)

    summary = repository.get_place_features_summary(now=now, local_timezone=UTC)
    assert summary.active_feature_count == 1
    assert summary.recent_change_count == 1
    assert summary.highlight == "Sunflower feeder has been especially active this week."


def test_features_summary_empty_state(repository: ProductRepository) -> None:
    summary = repository.get_place_features_summary()
    assert summary.active_feature_count == 0
    assert summary.recent_change_count == 0
    assert summary.highlight is None


# --- HTTP surface -------------------------------------------------------------


def test_place_feature_mutations_require_authentication(repository: ProductRepository) -> None:
    plain_client = TestClient(app)
    assert plain_client.get("/api/place/features").status_code == 401
    assert plain_client.post(
        "/api/place/features", json={"feature_type": "feeder", "name": "Feeder"}
    ).status_code == 401
    assert plain_client.get("/api/place/feature-changes").status_code == 401


def test_place_feature_crud_over_http(repository: ProductRepository) -> None:
    client = LegacyAuthenticatedSyncTestClient(app)
    created = client.post(
        "/api/place/features", json={"feature_type": "feeder", "name": "Sunflower feeder"}
    )
    assert created.status_code == 201
    feature_id = created.json()["id"]

    listed = client.get("/api/place/features")
    assert listed.status_code == 200
    assert any(f["id"] == feature_id for f in listed.json())

    updated = client.patch(f"/api/place/features/{feature_id}", json={"name": "Renamed feeder"})
    assert updated.status_code == 200
    assert updated.json()["name"] == "Renamed feeder"

    detail = client.get(f"/api/place/features/{feature_id}/detail")
    assert detail.status_code == 200
    assert detail.json()["feature"]["id"] == feature_id

    deleted = client.delete(f"/api/place/features/{feature_id}")
    assert deleted.status_code == 204
    assert client.get(f"/api/place/features/{feature_id}/detail").status_code == 404


def test_place_feature_invalid_zone_association_is_422_over_http(repository: ProductRepository) -> None:
    client = LegacyAuthenticatedSyncTestClient(app)
    response = client.post(
        "/api/place/features",
        json={"feature_type": "feeder", "name": "Feeder", "zone_id": "zone-does-not-exist"},
    )
    assert response.status_code == 422


def test_update_missing_place_feature_is_404_over_http(repository: ProductRepository) -> None:
    client = LegacyAuthenticatedSyncTestClient(app)
    response = client.patch("/api/place/features/feature-missing", json={"name": "X"})
    assert response.status_code == 404


def test_delete_place_feature_with_history_is_409_over_http(repository: ProductRepository) -> None:
    client = LegacyAuthenticatedSyncTestClient(app)
    created = client.post(
        "/api/place/features",
        json={"feature_type": "feeder", "name": "Feeder", "installed_date": "2026-01-01"},
    )
    feature_id = created.json()["id"]
    response = client.delete(f"/api/place/features/{feature_id}")
    assert response.status_code == 409


def test_place_feature_change_event_crud_over_http(repository: ProductRepository) -> None:
    client = LegacyAuthenticatedSyncTestClient(app)
    created = client.post(
        "/api/place/features", json={"feature_type": "feeder", "name": "Feeder"}
    )
    feature_id = created.json()["id"]

    event_response = client.post(
        "/api/place/feature-changes",
        json={"feature_id": feature_id, "event_type": "food_changed", "effective_date": "2026-05-01", "new_value": "Safflower"},
    )
    assert event_response.status_code == 201
    event_id = event_response.json()["id"]

    listed = client.get("/api/place/feature-changes", params={"feature_id": feature_id})
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    feature_after = client.get(f"/api/place/features/{feature_id}/detail").json()
    assert feature_after["feature"]["feeder_food_type"] == "Safflower"

    updated = client.patch(f"/api/place/feature-changes/{event_id}", json={"note": "Switched brands"})
    assert updated.status_code == 200
    assert updated.json()["note"] == "Switched brands"

    deleted = client.delete(f"/api/place/feature-changes/{event_id}")
    assert deleted.status_code == 204
    assert client.get("/api/place/feature-changes", params={"feature_id": feature_id}).json() == []


def test_place_feature_change_event_unknown_feature_is_422_over_http(repository: ProductRepository) -> None:
    client = LegacyAuthenticatedSyncTestClient(app)
    response = client.post(
        "/api/place/feature-changes",
        json={"feature_id": "feature-missing", "event_type": "modified", "effective_date": "2026-01-01"},
    )
    assert response.status_code == 422


def test_place_features_summary_over_http(repository: ProductRepository) -> None:
    client = LegacyAuthenticatedSyncTestClient(app)
    response = client.get("/api/place/features-summary")
    assert response.status_code == 200
    body = response.json()
    assert body == {"active_feature_count": 0, "recent_change_count": 0, "highlight": None}
