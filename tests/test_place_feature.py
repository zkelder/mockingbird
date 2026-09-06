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
from sqlalchemy import event, select
from starlette.testclient import TestClient

from mockingbird.analytics.conditional_association import compute_conditional_association
from mockingbird.analytics.feature_change_comparison import (
    CANDIDATE_WINDOW_DAYS,
    comparison_window_dates,
    compute_feature_change_comparison,
)
from mockingbird.analytics.feature_yield import compute_feature_yield
from mockingbird.analytics.place_activity_report import TaxonFact, VisitFact
from mockingbird.api.main import app, configure_repository
from mockingbird.api.schemas import (
    CameraSourceUpdate,
    CurrentUser,
    EnvironmentalContextSettingsUpdate,
    PlaceFeatureChangeEventCreate,
    PlaceFeatureChangeEventUpdate,
    PlaceFeatureCreate,
    PlaceFeatureObservationLinkCreate,
    PlaceFeatureUpdate,
    ReviewCorrectionCreate,
    UserRole,
)
from mockingbird.environment import weather_provider
from mockingbird.habitat.place_feature import (
    DERIVED_STATE_EVENT_TYPES,
    PLACE_FEATURE_CHANGE_EVENT_TYPES,
    PLACE_FEATURE_TYPES,
)
from mockingbird.repository.product_repository import (
    CrossCameraVisitAssociationModel,
    PlaceFeatureHasHistoryError,
    ProductRepository,
)
from mockingbird.storage.models import (
    CameraSourceModel,
    EnvironmentalContextRecordModel,
    EventModel,
    MediaAssetModel,
    MonitoringExposureIntervalModel,
    PlaceFeatureObservationLinkModel,
    StreamModel,
    VisitEvidenceLinkModel,
    VisitModel,
    ZoneModel,
)
from tests.conftest import LegacyAuthenticatedSyncTestClient

SOURCE_ID = "source-place-feature"
STREAM_ID = "stream-place-feature"
OTHER_STREAM_ID = "stream-place-feature-other"
ZONE_ID = "zone-place-feature-feeder"
OTHER_ZONE_ID = "zone-place-feature-other-source"

# Multi-Camera Place Feature Linking & Cross-View Habitat Context v1: a
# genuinely second camera (distinct Source), for cross-view/cross-camera
# tests -- `OTHER_STREAM_ID`/`OTHER_ZONE_ID` above are a second Stream/Zone
# on the *same* `SOURCE_ID`, not a second camera, so they cannot exercise
# cross-camera duplicate-encounter dedup (which requires two different
# Sources -- see `cross_camera_association.py`).
SOURCE_ID_2 = "source-place-feature-2"
STREAM_ID_2 = "stream-place-feature-2"
ZONE_ID_2 = "zone-place-feature-2"


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


def _add_second_camera(repository: ProductRepository) -> None:
    """Seeds a genuinely second camera (`SOURCE_ID_2`/`STREAM_ID_2`), with
    its own Zone (`ZONE_ID_2`) -- for multi-view/cross-camera tests. Not
    part of the shared `repository` fixture itself so every pre-existing,
    single-camera test's behavior is completely unaffected."""

    with repository.session_factory() as session:
        with session.begin():
            session.add(
                CameraSourceModel(
                    id=SOURCE_ID_2, name="Feature fixture camera 2", kind="manual_upload",
                    status="connected", description="Place Features fixture (second camera).",
                )
            )
            session.add(
                StreamModel(
                    id=STREAM_ID_2, source_id=SOURCE_ID_2, name="Feature fixture stream 2",
                    description="Place Features fixture (second camera).", is_live=False,
                )
            )
            session.add(
                ZoneModel(
                    id=ZONE_ID_2, stream_id=STREAM_ID_2, name="Feeder (second view)",
                    zone_type="feeder", polygon_json="[]", is_active=True, monitoring_policy_json=None,
                )
            )


def _associate_cross_camera(
    repository: ProductRepository, *, visit_id_a: str, visit_id_b: str, tier: str = "associated",
) -> None:
    """Directly seeds one `cross_camera_visit_associations` row for a pair
    of Visits from two different cameras -- mirrors `_reconcile_cross_
    camera_association_for_event`'s own canonical lexicographic-order
    convention rather than exercising the full live reconciliation
    pipeline (out of this test file's own scope; see
    `test_camera_source_multi_camera_maturity.py`/`test_multi_camera_
    place_experience_scenario.py` for that)."""

    primary_id, secondary_id = sorted((visit_id_a, visit_id_b))
    now = datetime.now(UTC)
    with repository.session_factory() as session:
        with session.begin():
            session.add(
                CrossCameraVisitAssociationModel(
                    id=f"assoc-{visit_id_a}-{visit_id_b}", primary_visit_id=primary_id,
                    secondary_visit_id=secondary_id, tier=tier, overlap_ms=1000, gap_ms=0,
                    spatial_signal="matching_area_name", multi_subject=False,
                    engine_version="cross-camera-association-v1", created_at=now, updated_at=now,
                )
            )


def _place_feature_observation_link_models(
    repository: ProductRepository, feature_id: str,
) -> list[PlaceFeatureObservationLinkModel]:
    """Raw link rows for one Feature, for direct assertions (e.g. proving a
    hard-deleted Feature's own links were cascaded, not orphaned) -- the
    repository's own public surface intentionally never exposes raw ORM
    rows."""

    with repository.session_factory() as session:
        return list(
            session.scalars(
                select(PlaceFeatureObservationLinkModel).where(
                    PlaceFeatureObservationLinkModel.feature_id == feature_id
                )
            ).all()
        )


# --- Environmental Context x Place Story & Habitat Change Composition v1 ---

WEATHER_LATITUDE = 40.7
WEATHER_LONGITUDE = -74.0


def _enable_weather(
    repository: ProductRepository, *, latitude: float = WEATHER_LATITUDE, longitude: float = WEATHER_LONGITUDE,
) -> None:
    repository.update_environmental_context_settings(
        EnvironmentalContextSettingsUpdate(latitude=latitude, longitude=longitude, weather_enabled=True),
        acting_user=_acting_user(),
    )


def _insert_environmental_context_day(
    repository: ProductRepository,
    *,
    metric: str,
    for_date: date,
    value_numeric: float,
    unit: str,
    latitude: float = WEATHER_LATITUDE,
    longitude: float = WEATHER_LONGITUDE,
) -> None:
    """Directly inserts one full day (24 hourly rows) of one weather metric
    at a fixed value -- bypasses the fetch path entirely, mirroring
    `test_environmental_context.py`'s own `_insert_air_temperature_day`
    helper, generalized to any metric (here, also `precipitation_amount`)."""

    now = datetime.now(UTC)
    with repository.session_factory() as session:
        with session.begin():
            for hour in range(24):
                session.add(
                    EnvironmentalContextRecordModel(
                        id=f"envctx-feature-test-{metric}-{for_date.isoformat()}-{hour:02d}",
                        source_id=None,
                        provider_key=weather_provider.WEATHER_PROVIDER_KEY,
                        information_class=weather_provider.WEATHER_INFORMATION_CLASS,
                        metric=metric,
                        value_numeric=value_numeric,
                        value_text=None,
                        unit=unit,
                        observed_at=datetime(for_date.year, for_date.month, for_date.day, hour, tzinfo=UTC),
                        observed_at_end=None,
                        for_date=for_date,
                        retrieved_at=now,
                        basis_latitude=latitude,
                        basis_longitude=longitude,
                        provenance_json=None,
                        provenance_schema_version=1,
                        created_at=now,
                    )
                )


def _seed_flat_temperature_baseline(
    repository: ProductRepository, *, before: date, days: int, temperature_c: float,
) -> None:
    """Establishes a Place-relative temperature baseline entirely *outside*
    a comparison's own pre/post windows, at a stable value, so the windows
    under test can be judged against a genuine, independent baseline rather
    than the circular case of only the two windows being compared."""

    for offset in range(1, days + 1):
        _insert_environmental_context_day(
            repository, metric="air_temperature", for_date=before - timedelta(days=offset),
            value_numeric=temperature_c, unit="celsius",
        )


def _insert_precipitation_day(repository: ProductRepository, *, for_date: date, total_mm: float) -> None:
    """`condition_bands.daily_sum` sums every hourly value for the day (real
    Open-Meteo hourly precipitation, unlike temperature, is summed, not
    averaged) -- spreading `total_mm` evenly across the day's 24 hourly rows
    reconstructs the intended daily total exactly, rather than
    `_insert_environmental_context_day`'s own flat-per-hour convention
    (correct for temperature's daily *mean*) silently producing 24x too
    much rain."""

    _insert_environmental_context_day(
        repository, metric="precipitation_amount", for_date=for_date, value_numeric=total_mm / 24, unit="mm",
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


def test_comparison_window_dates_reconstructs_the_exact_windows_used() -> None:
    """Environmental Context x Place Story & Habitat Change Composition v1:
    a caller reconstructing pre/post date-sets from only a `FeatureChangeComparison`'s
    own `pre_start`/`post_end`/`window_days` (never `effective_date` itself) must get
    byte-identical sets to the ones `compute_feature_change_comparison` actually used
    to produce that result -- otherwise an environmental-context composition could
    silently judge a different period than the wildlife comparison it explains."""

    effective = date(2026, 6, 10)
    today = effective + timedelta(days=30)
    pre = {effective - timedelta(days=offset) for offset in range(1, 8)}
    post = {effective + timedelta(days=offset) for offset in range(7)}
    presence = {effective + timedelta(days=1), effective + timedelta(days=2)}
    result = compute_feature_change_comparison(
        presence_dates=presence, usable_dates=pre | post, effective_date=effective, today=today,
    )
    assert result.maturity == "comparable"
    assert result.pre_start is not None and result.post_end is not None and result.window_days is not None
    reconstructed_pre, reconstructed_post = comparison_window_dates(
        result.pre_start, result.post_end, result.window_days
    )
    assert reconstructed_pre == pre
    assert reconstructed_post == post


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


# --- Repository: Multi-view observation links (Multi-Camera Place Feature
# Linking & Cross-View Habitat Context v1) ------------------------------------


def test_add_observation_link_creates_second_view(repository: ProductRepository) -> None:
    _add_second_camera(repository)
    feature = repository.add_place_feature(
        PlaceFeatureCreate(feature_type="water", name="Bird Bath", zone_id=ZONE_ID), acting_user=_acting_user()
    )
    assert len(feature.observation_links) == 1
    assert feature.source_id == SOURCE_ID and feature.zone_id == ZONE_ID

    link = repository.add_place_feature_observation_link(
        feature.id, PlaceFeatureObservationLinkCreate(zone_id=ZONE_ID_2), acting_user=_acting_user()
    )
    assert link.source_id == SOURCE_ID_2
    assert link.zone_id == ZONE_ID_2
    assert link.zone_name == "Feeder (second view)"
    assert link.source_archived is False

    refreshed = repository.get_place_feature_detail(feature.id).feature
    assert len(refreshed.observation_links) == 2
    assert {(link.source_id, link.zone_id) for link in refreshed.observation_links} == {
        (SOURCE_ID, ZONE_ID), (SOURCE_ID_2, ZONE_ID_2),
    }
    # Honest absence, not an arbitrary "first" link, once there is more
    # than one -- see `PlaceFeatureModel`'s own updated docstring.
    assert refreshed.source_id is None
    assert refreshed.zone_id is None


def test_add_observation_link_via_bare_source(repository: ProductRepository) -> None:
    _add_second_camera(repository)
    feature = repository.add_place_feature(
        PlaceFeatureCreate(feature_type="feeder", name="Feeder"), acting_user=_acting_user()
    )
    link = repository.add_place_feature_observation_link(
        feature.id, PlaceFeatureObservationLinkCreate(source_id=SOURCE_ID_2), acting_user=_acting_user()
    )
    assert link.source_id == SOURCE_ID_2
    assert link.zone_id is None
    assert link.zone_name is None


def test_add_observation_link_to_missing_feature_returns_none(repository: ProductRepository) -> None:
    assert repository.add_place_feature_observation_link(
        "feature-missing", PlaceFeatureObservationLinkCreate(source_id=SOURCE_ID), acting_user=_acting_user()
    ) is None


def test_add_observation_link_with_unknown_zone_is_rejected(repository: ProductRepository) -> None:
    feature = repository.add_place_feature(
        PlaceFeatureCreate(feature_type="feeder", name="Feeder"), acting_user=_acting_user()
    )
    with pytest.raises(ValueError):
        repository.add_place_feature_observation_link(
            feature.id, PlaceFeatureObservationLinkCreate(zone_id="zone-does-not-exist"),
            acting_user=_acting_user(),
        )


def test_add_observation_link_with_mismatched_source_and_zone_is_rejected(repository: ProductRepository) -> None:
    _add_second_camera(repository)
    feature = repository.add_place_feature(
        PlaceFeatureCreate(feature_type="feeder", name="Feeder"), acting_user=_acting_user()
    )
    with pytest.raises(ValueError):
        repository.add_place_feature_observation_link(
            feature.id, PlaceFeatureObservationLinkCreate(zone_id=ZONE_ID, source_id=SOURCE_ID_2),
            acting_user=_acting_user(),
        )


def test_observation_link_create_requires_source_or_zone() -> None:
    with pytest.raises(ValueError):
        PlaceFeatureObservationLinkCreate()


def test_add_duplicate_observation_link_is_rejected(repository: ProductRepository) -> None:
    feature = repository.add_place_feature(
        PlaceFeatureCreate(feature_type="feeder", name="Feeder", zone_id=ZONE_ID), acting_user=_acting_user()
    )
    with pytest.raises(ValueError):
        repository.add_place_feature_observation_link(
            feature.id, PlaceFeatureObservationLinkCreate(zone_id=ZONE_ID), acting_user=_acting_user()
        )


def test_add_duplicate_bare_source_observation_link_is_rejected(repository: ProductRepository) -> None:
    """The nullable-`zone_id` case specifically -- SQLite's own NULL-is-
    distinct semantics would let this slip past a naive unique index (see
    `PlaceFeatureObservationLinkModel`'s docstring); the app-level check
    must catch it too."""

    feature = repository.add_place_feature(
        PlaceFeatureCreate(feature_type="feeder", name="Feeder", source_id=SOURCE_ID), acting_user=_acting_user()
    )
    with pytest.raises(ValueError):
        repository.add_place_feature_observation_link(
            feature.id, PlaceFeatureObservationLinkCreate(source_id=SOURCE_ID), acting_user=_acting_user()
        )


def test_feature_can_link_two_different_zones_on_the_same_source(repository: ProductRepository) -> None:
    """Not a duplicate: two different Zones on one camera can both
    genuinely show part of the same physical Feature (e.g. a vegetation
    patch crossing two drawn Zones on one wide-angle view)."""

    with repository.session_factory() as session:
        with session.begin():
            session.add(
                ZoneModel(
                    id=OTHER_ZONE_ID, stream_id=STREAM_ID, name="Back hedge (west end)",
                    zone_type="habitat_area", polygon_json="[]", is_active=True, monitoring_policy_json=None,
                )
            )
    feature = repository.add_place_feature(
        PlaceFeatureCreate(feature_type="vegetation_patch", name="Back hedge", zone_id=ZONE_ID),
        acting_user=_acting_user(),
    )
    link = repository.add_place_feature_observation_link(
        feature.id, PlaceFeatureObservationLinkCreate(zone_id=OTHER_ZONE_ID),
        acting_user=_acting_user(),
    )
    assert link is not None
    refreshed = repository.get_place_feature_detail(feature.id).feature
    assert len(refreshed.observation_links) == 2


def test_remove_observation_link_recomputes_mirror(repository: ProductRepository) -> None:
    _add_second_camera(repository)
    feature = repository.add_place_feature(
        PlaceFeatureCreate(feature_type="water", name="Bird Bath", zone_id=ZONE_ID), acting_user=_acting_user()
    )
    link = repository.add_place_feature_observation_link(
        feature.id, PlaceFeatureObservationLinkCreate(zone_id=ZONE_ID_2), acting_user=_acting_user()
    )
    assert repository.get_place_feature_detail(feature.id).feature.source_id is None  # 2 links: honest absence

    assert repository.remove_place_feature_observation_link(feature.id, link.id, acting_user=_acting_user()) is True
    refreshed = repository.get_place_feature_detail(feature.id).feature
    assert len(refreshed.observation_links) == 1
    # Exactly one link again -- the mirror repopulates, byte-identical to
    # a Feature that was only ever linked once.
    assert refreshed.source_id == SOURCE_ID
    assert refreshed.zone_id == ZONE_ID


def test_remove_last_observation_link_does_not_delete_feature(repository: ProductRepository) -> None:
    feature = repository.add_place_feature(
        PlaceFeatureCreate(feature_type="water", name="Bird Bath", zone_id=ZONE_ID), acting_user=_acting_user()
    )
    [link] = feature.observation_links
    assert repository.remove_place_feature_observation_link(feature.id, link.id, acting_user=_acting_user()) is True
    refreshed = repository.get_place_feature_detail(feature.id)
    assert refreshed is not None  # the Feature itself still exists
    assert refreshed.feature.observation_links == []
    assert refreshed.feature.source_id is None
    assert refreshed.feature.zone_id is None


def test_remove_missing_observation_link_returns_false(repository: ProductRepository) -> None:
    feature = repository.add_place_feature(
        PlaceFeatureCreate(feature_type="feeder", name="Feeder"), acting_user=_acting_user()
    )
    assert repository.remove_place_feature_observation_link(
        feature.id, "feature-link-missing", acting_user=_acting_user()
    ) is False


def test_remove_observation_link_belonging_to_a_different_feature_returns_false(
    repository: ProductRepository,
) -> None:
    feature_a = repository.add_place_feature(
        PlaceFeatureCreate(feature_type="feeder", name="Feeder A", zone_id=ZONE_ID), acting_user=_acting_user()
    )
    feature_b = repository.add_place_feature(
        PlaceFeatureCreate(feature_type="feeder", name="Feeder B"), acting_user=_acting_user()
    )
    [link] = feature_a.observation_links
    assert repository.remove_place_feature_observation_link(
        feature_b.id, link.id, acting_user=_acting_user()
    ) is False
    # The link on Feature A must remain untouched.
    assert len(repository.get_place_feature_detail(feature_a.id).feature.observation_links) == 1


def test_hard_deleting_feature_cascades_observation_links(repository: ProductRepository) -> None:
    feature = repository.add_place_feature(
        PlaceFeatureCreate(feature_type="feeder", name="Feeder", zone_id=ZONE_ID), acting_user=_acting_user()
    )
    assert len(_place_feature_observation_link_models(repository, feature.id)) == 1
    assert repository.remove_place_feature(feature.id, acting_user=_acting_user()) is True
    # The link row is gone, not orphaned.
    assert _place_feature_observation_link_models(repository, feature.id) == []


def test_update_place_feature_source_id_replaces_entire_link_set(repository: ProductRepository) -> None:
    """Legacy singular-field compatibility: `PlaceFeatureUpdate` is a
    full-replacement operation on the link set, documented as such, not a
    silent data-loss surprise -- see `PlaceFeatureUpdate`'s own docstring."""

    _add_second_camera(repository)
    feature = repository.add_place_feature(
        PlaceFeatureCreate(feature_type="feeder", name="Feeder", zone_id=ZONE_ID), acting_user=_acting_user()
    )
    repository.add_place_feature_observation_link(
        feature.id, PlaceFeatureObservationLinkCreate(zone_id=ZONE_ID_2), acting_user=_acting_user()
    )
    assert len(repository.get_place_feature_detail(feature.id).feature.observation_links) == 2

    updated = repository.update_place_feature(
        feature.id, PlaceFeatureUpdate(source_id=SOURCE_ID_2), acting_user=_acting_user()
    )
    assert updated.source_id == SOURCE_ID_2
    assert updated.zone_id is None
    assert len(updated.observation_links) == 1
    assert updated.observation_links[0].source_id == SOURCE_ID_2


def test_zone_deletion_blocked_when_linked_to_a_feature(repository: ProductRepository) -> None:
    """A real, pre-existing gap this milestone found and closed: `delete_
    zone` previously had no guard at all for a Zone referenced only by a
    Place Feature's observation link -- see the governing brief's "Zone
    correction / deletion"."""

    repository.add_place_feature(
        PlaceFeatureCreate(feature_type="feeder", name="Feeder", zone_id=ZONE_ID), acting_user=_acting_user()
    )
    with pytest.raises(ValueError, match="zone_has_review_context"):
        repository.delete_zone(ZONE_ID)


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


# --- Cross-view analytics: duplicate safety + coverage union (Multi-Camera
# Place Feature Linking & Cross-View Habitat Context v1) ----------------------


def test_multi_view_yield_dedupes_a_confirmed_cross_camera_pair(repository: ProductRepository) -> None:
    """The hard correctness requirement: one cardinal seen by two linked
    cameras, already confirmed as the same biological encounter by the
    accepted cross-camera association engine, must count once -- not
    twice -- in this Feature's own recent yield."""

    _add_second_camera(repository)
    feature = repository.add_place_feature(
        PlaceFeatureCreate(feature_type="water", name="Bird Bath", zone_id=ZONE_ID), acting_user=_acting_user()
    )
    repository.add_place_feature_observation_link(
        feature.id, PlaceFeatureObservationLinkCreate(zone_id=ZONE_ID_2), acting_user=_acting_user()
    )
    now = datetime(2026, 6, 8, tzinfo=UTC)
    at = now - timedelta(days=1)
    _add_visit(repository, visit_id="visit-cam-a", at=at, stream_id=STREAM_ID, zone_id=ZONE_ID)
    _add_visit(repository, visit_id="visit-cam-b", at=at, stream_id=STREAM_ID_2, zone_id=ZONE_ID_2)
    _confirm(repository, visit_id="visit-cam-a")
    _confirm(repository, visit_id="visit-cam-b")
    _associate_cross_camera(repository, visit_id_a="visit-cam-a", visit_id_b="visit-cam-b", tier="associated")

    yield_summary = repository.get_place_feature_detail(feature.id, now=now, local_timezone=UTC).recent_yield
    assert yield_summary.confirmed_wildlife_visit_count == 1


def test_multi_view_yield_counts_independent_simultaneous_visits_twice(repository: ProductRepository) -> None:
    """The other half of the same requirement: two genuinely independent
    birds observed simultaneously by two linked cameras -- with no
    cross-camera association recorded -- must remain two, not collapse to
    one merely because they share a Feature and a moment in time."""

    _add_second_camera(repository)
    feature = repository.add_place_feature(
        PlaceFeatureCreate(feature_type="water", name="Bird Bath", zone_id=ZONE_ID), acting_user=_acting_user()
    )
    repository.add_place_feature_observation_link(
        feature.id, PlaceFeatureObservationLinkCreate(zone_id=ZONE_ID_2), acting_user=_acting_user()
    )
    now = datetime(2026, 6, 8, tzinfo=UTC)
    at = now - timedelta(days=1)
    _add_visit(repository, visit_id="visit-cam-a2", at=at, stream_id=STREAM_ID, zone_id=ZONE_ID)
    _add_visit(repository, visit_id="visit-cam-b2", at=at, stream_id=STREAM_ID_2, zone_id=ZONE_ID_2)
    _confirm(repository, visit_id="visit-cam-a2", label="carolina_chickadee")
    _confirm(repository, visit_id="visit-cam-b2", label="carolina_chickadee")
    # Deliberately no `_associate_cross_camera` call -- no association row
    # at all is the honest "independent" outcome (see `cross_camera_
    # association.py`'s own "no row is persisted for an out-of-range or
    # confirmed-differing-Area pair" convention).

    yield_summary = repository.get_place_feature_detail(feature.id, now=now, local_timezone=UTC).recent_yield
    assert yield_summary.confirmed_wildlife_visit_count == 2


def test_multi_view_yield_does_not_dedupe_a_merely_possible_pair(repository: ProductRepository) -> None:
    """A `"possible"` (not `"associated"`) cross-camera pair is genuine,
    disclosed ambiguity -- not confident enough to exclude either side
    from a count, matching `_associated_visit_ids_to_exclude_from_
    counting`'s own "confirmed `associated` pairs only" contract."""

    _add_second_camera(repository)
    feature = repository.add_place_feature(
        PlaceFeatureCreate(feature_type="water", name="Bird Bath", zone_id=ZONE_ID), acting_user=_acting_user()
    )
    repository.add_place_feature_observation_link(
        feature.id, PlaceFeatureObservationLinkCreate(zone_id=ZONE_ID_2), acting_user=_acting_user()
    )
    now = datetime(2026, 6, 8, tzinfo=UTC)
    at = now - timedelta(days=1)
    _add_visit(repository, visit_id="visit-cam-a3", at=at, stream_id=STREAM_ID, zone_id=ZONE_ID)
    _add_visit(repository, visit_id="visit-cam-b3", at=at, stream_id=STREAM_ID_2, zone_id=ZONE_ID_2)
    _confirm(repository, visit_id="visit-cam-a3")
    _confirm(repository, visit_id="visit-cam-b3")
    _associate_cross_camera(repository, visit_id_a="visit-cam-a3", visit_id_b="visit-cam-b3", tier="possible")

    yield_summary = repository.get_place_feature_detail(feature.id, now=now, local_timezone=UTC).recent_yield
    assert yield_summary.confirmed_wildlife_visit_count == 2


def test_multi_view_coverage_is_union_not_sum(repository: ProductRepository) -> None:
    """The other hard correctness requirement: two linked cameras
    overlapping in wall-clock time must not make a Feature appear twice
    as well monitored for the same interval -- mirrors the identical
    Zone Insights aggregate-coverage fix from Multi-Camera Place
    Experience v2, reapplied here."""

    _add_second_camera(repository)
    feature = repository.add_place_feature(
        PlaceFeatureCreate(feature_type="water", name="Bird Bath", zone_id=ZONE_ID), acting_user=_acting_user()
    )
    repository.add_place_feature_observation_link(
        feature.id, PlaceFeatureObservationLinkCreate(zone_id=ZONE_ID_2), acting_user=_acting_user()
    )
    now = datetime(2026, 6, 8, tzinfo=UTC)
    window_start = now - timedelta(days=7)
    # Camera A: monitored for the first 2 of the last 3 hours before `now`.
    _add_exposure(
        repository, interval_id="exposure-union-a", started_at=now - timedelta(hours=3),
        ended_at=now - timedelta(hours=1), stream_id=STREAM_ID,
    )
    # Camera B: monitored for the full last 3 hours -- a real 2-hour
    # overlap with Camera A, not independent time.
    _add_exposure(
        repository, interval_id="exposure-union-b", started_at=now - timedelta(hours=3),
        ended_at=now, stream_id=STREAM_ID_2,
    )
    yield_summary = repository.get_place_feature_detail(feature.id, now=now, local_timezone=UTC).recent_yield
    assert yield_summary is not None
    # Union of [now-3h, now-1h] and [now-3h, now] is exactly [now-3h, now]
    # -- 3 hours, never the naive 5-hour sum (2h + 3h) of two independently
    # summed, overlapping intervals.
    assert yield_summary.monitored_seconds == pytest.approx(3 * 3600.0)
    del window_start  # documents the 7-day yield window this fixture stays well inside of


def test_multi_view_comparison_scopes_across_both_linked_views(repository: ProductRepository) -> None:
    """Before/after comparison must see confirmed activity from *either*
    linked camera, not only the one originally linked at creation time."""

    _add_second_camera(repository)
    feature = repository.add_place_feature(
        PlaceFeatureCreate(feature_type="feeder", name="Feeder", zone_id=ZONE_ID), acting_user=_acting_user()
    )
    repository.add_place_feature_observation_link(
        feature.id, PlaceFeatureObservationLinkCreate(zone_id=ZONE_ID_2), acting_user=_acting_user()
    )
    effective = date(2026, 6, 1)
    now = datetime(2026, 6, 8, tzinfo=UTC)
    event = repository.add_place_feature_change_event(
        PlaceFeatureChangeEventCreate(feature_id=feature.id, event_type="added", effective_date=effective),
        acting_user=_acting_user(),
    )
    _cover_days(repository, start=effective - timedelta(days=7), days=14, stream_id=STREAM_ID)
    _cover_days(repository, start=effective - timedelta(days=7), days=14, stream_id=STREAM_ID_2)
    # Confirmed activity after the change, split across BOTH cameras --
    # neither camera alone would clear a real "more common after" signal.
    for offset in range(7):
        day = effective + timedelta(days=offset)
        at = datetime(day.year, day.month, day.day, 10, tzinfo=UTC)
        if offset % 2 == 0:
            _add_visit(repository, visit_id=f"visit-split-a-{offset}", at=at, stream_id=STREAM_ID, zone_id=ZONE_ID)
            _confirm(repository, visit_id=f"visit-split-a-{offset}")
        else:
            _add_visit(
                repository, visit_id=f"visit-split-b-{offset}", at=at, stream_id=STREAM_ID_2, zone_id=ZONE_ID_2,
            )
            _confirm(repository, visit_id=f"visit-split-b-{offset}")

    detail = repository.get_place_feature_detail(feature.id, now=now, local_timezone=UTC)
    comparison = next(c for c in detail.changes if c.event.id == event.id).comparison
    assert comparison.maturity == "comparable"
    assert comparison.status == "more_common_under_condition"


def test_archived_camera_link_preserves_historical_comparison(repository: ProductRepository) -> None:
    """Archiving preserves history (see docs/product-doctrine.md): a
    Feature's own linked view stays reachable for historical before/after
    comparison even after the camera it names is archived -- this
    milestone found and closed a real inconsistency where a bare-Source
    link (unlike a Zone-linked one) previously went silently quiet on
    archival instead."""

    feature = repository.add_place_feature(
        PlaceFeatureCreate(feature_type="feeder", name="Feeder", source_id=SOURCE_ID), acting_user=_acting_user()
    )
    effective = date(2026, 6, 1)
    now = datetime(2026, 6, 8, tzinfo=UTC)
    event = repository.add_place_feature_change_event(
        PlaceFeatureChangeEventCreate(feature_id=feature.id, event_type="added", effective_date=effective),
        acting_user=_acting_user(),
    )
    _cover_days(repository, start=effective - timedelta(days=7), days=14)
    for offset in range(7):
        day = effective + timedelta(days=offset)
        visit_id = f"visit-archived-cam-{offset}"
        _add_visit(repository, visit_id=visit_id, at=datetime(day.year, day.month, day.day, 10, tzinfo=UTC))
        _confirm(repository, visit_id=visit_id)

    repository.update_camera_source(SOURCE_ID, CameraSourceUpdate(archived=True))

    detail = repository.get_place_feature_detail(feature.id, now=now, local_timezone=UTC)
    comparison = next(c for c in detail.changes if c.event.id == event.id).comparison
    assert comparison is not None
    assert comparison.maturity == "comparable"
    assert comparison.status == "more_common_under_condition"
    assert detail.feature.observation_links[0].source_archived is True


# --- Representative evidence (Place Story Deep Dives & Representative
# Evidence v1) -- reuses the canonical Gate C selector unmodified; these
# tests exercise the Feature-scoped candidate-gathering this milestone adds,
# not the selector's own ranking logic (already covered by tests/test_
# representative_evidence.py and test_place_activity_report_repository.py).


def _attach_primary_evidence(
    repository: ProductRepository, *, visit_id: str, captured_at: datetime,
    stream_id: str = STREAM_ID, source_id: str = SOURCE_ID, missing_file: bool = False,
) -> str:
    """Attach one real, persisted, `is_primary` evidence frame to an
    already-created Visit -- mirrors test_place_activity_report_
    repository.py's identical `_attach_primary_evidence` helper (a real
    backing file, since the representative-evidence selector honestly
    checks `Path(local_path).is_file()`). Returns the created `media_asset_
    id`."""

    media_id = f"media-{visit_id}"
    media_path = repository.media_root / f"{visit_id}.jpg"
    if not missing_file:
        media_path.parent.mkdir(parents=True, exist_ok=True)
        media_path.write_bytes(b"fixture-jpeg-bytes")
    with repository.session_factory() as session:
        with session.begin():
            session.add(
                MediaAssetModel(
                    id=media_id, source_id=source_id, stream_id=stream_id, filename=f"{media_id}.jpg",
                    content_type="image/jpeg", media_type="image", local_path=str(media_path),
                    original_filename=f"{media_id}.jpg", file_size_bytes=12, created_at=captured_at,
                    image_width=800, image_height=600,
                )
            )
            session.add(
                VisitEvidenceLinkModel(
                    id=f"link-{visit_id}", visit_id=visit_id, media_asset_id=media_id, captured_at=captured_at,
                    frame_sequence=0, sort_order=0, is_primary=True, evidence_role="identification",
                    created_at=captured_at,
                )
            )
    return media_id


def test_feature_representative_evidence_selects_confirmed_visit(repository: ProductRepository) -> None:
    feature = repository.add_place_feature(
        PlaceFeatureCreate(feature_type="water", name="Bird Bath", zone_id=ZONE_ID), acting_user=_acting_user()
    )
    at = datetime(2026, 6, 1, 10, tzinfo=UTC)
    _add_visit(repository, visit_id="bath-visit", at=at)
    _attach_primary_evidence(repository, visit_id="bath-visit", captured_at=at)
    _confirm(repository, visit_id="bath-visit", label="northern_cardinal")

    detail = repository.get_place_feature_detail(feature.id, now=at + timedelta(days=1), local_timezone=UTC)
    assert detail.representative_evidence is not None
    assert detail.representative_evidence.visit_id == "bath-visit"
    assert detail.representative_evidence.evidence.media_asset_id == "media-bath-visit"


def test_feature_representative_evidence_none_without_observation_links(repository: ProductRepository) -> None:
    feature = repository.add_place_feature(
        PlaceFeatureCreate(feature_type="water", name="Bird Bath"), acting_user=_acting_user()
    )
    detail = repository.get_place_feature_detail(feature.id, now=datetime(2026, 6, 1, tzinfo=UTC), local_timezone=UTC)
    assert detail.representative_evidence is None


def test_feature_representative_evidence_none_when_no_confirmed_wildlife_visit(
    repository: ProductRepository,
) -> None:
    feature = repository.add_place_feature(
        PlaceFeatureCreate(feature_type="water", name="Bird Bath", zone_id=ZONE_ID), acting_user=_acting_user()
    )
    at = datetime(2026, 6, 1, 10, tzinfo=UTC)
    _add_visit(repository, visit_id="unreviewed", at=at)
    _attach_primary_evidence(repository, visit_id="unreviewed", captured_at=at)
    # Never confirmed -- an ordinary needs-review Visit must not become a
    # Feature's representative evidence merely because it has an image.
    detail = repository.get_place_feature_detail(feature.id, now=at + timedelta(days=1), local_timezone=UTC)
    assert detail.representative_evidence is None


def test_feature_representative_evidence_ignores_visits_outside_feature_scope(
    repository: ProductRepository,
) -> None:
    """A confirmed Visit with real evidence on an *unlinked* Zone of the
    same camera must never leak into this Feature's own representative
    evidence -- Feature scope, not Place-wide scope."""

    feature = repository.add_place_feature(
        PlaceFeatureCreate(feature_type="water", name="Bird Bath", zone_id=ZONE_ID), acting_user=_acting_user()
    )
    at = datetime(2026, 6, 1, 10, tzinfo=UTC)
    _add_visit(repository, visit_id="elsewhere", at=at, zone_id=OTHER_ZONE_ID)
    _attach_primary_evidence(repository, visit_id="elsewhere", captured_at=at)
    _confirm(repository, visit_id="elsewhere", label="northern_cardinal")

    detail = repository.get_place_feature_detail(feature.id, now=at + timedelta(days=1), local_timezone=UTC)
    assert detail.representative_evidence is None


def test_feature_representative_evidence_abstains_when_media_file_missing(repository: ProductRepository) -> None:
    feature = repository.add_place_feature(
        PlaceFeatureCreate(feature_type="water", name="Bird Bath", zone_id=ZONE_ID), acting_user=_acting_user()
    )
    at = datetime(2026, 6, 1, 10, tzinfo=UTC)
    _add_visit(repository, visit_id="deleted-media", at=at)
    _attach_primary_evidence(repository, visit_id="deleted-media", captured_at=at, missing_file=True)
    _confirm(repository, visit_id="deleted-media", label="northern_cardinal")

    detail = repository.get_place_feature_detail(feature.id, now=at + timedelta(days=1), local_timezone=UTC)
    assert detail.representative_evidence is None, "a missing media file must abstain, never a broken thumbnail"


def test_feature_representative_evidence_spans_every_linked_camera_view(repository: ProductRepository) -> None:
    """Multi-Camera Place Feature Linking v1: representative evidence must
    consider every one of a Feature's linked views, not only its first."""

    _add_second_camera(repository)
    feature = repository.add_place_feature(
        PlaceFeatureCreate(feature_type="water", name="Bird Bath", zone_id=ZONE_ID), acting_user=_acting_user()
    )
    repository.add_place_feature_observation_link(
        feature.id, PlaceFeatureObservationLinkCreate(zone_id=ZONE_ID_2), acting_user=_acting_user()
    )
    at = datetime(2026, 6, 1, 10, tzinfo=UTC)
    _add_visit(repository, visit_id="second-camera-visit", at=at, stream_id=STREAM_ID_2, zone_id=ZONE_ID_2)
    _attach_primary_evidence(
        repository, visit_id="second-camera-visit", captured_at=at, stream_id=STREAM_ID_2, source_id=SOURCE_ID_2,
    )
    _confirm(repository, visit_id="second-camera-visit", label="northern_cardinal")

    detail = repository.get_place_feature_detail(feature.id, now=at + timedelta(days=1), local_timezone=UTC)
    assert detail.representative_evidence is not None
    assert detail.representative_evidence.visit_id == "second-camera-visit"
    assert detail.representative_evidence.stream_id == STREAM_ID_2


def test_feature_representative_evidence_survives_camera_archival(repository: ProductRepository) -> None:
    """Archiving preserves history (see docs/product-doctrine.md) --
    mirrors test_archived_camera_link_preserves_historical_comparison for
    representative evidence specifically."""

    feature = repository.add_place_feature(
        PlaceFeatureCreate(feature_type="water", name="Bird Bath", source_id=SOURCE_ID), acting_user=_acting_user()
    )
    at = datetime(2026, 6, 1, 10, tzinfo=UTC)
    _add_visit(repository, visit_id="pre-archive-visit", at=at)
    _attach_primary_evidence(repository, visit_id="pre-archive-visit", captured_at=at)
    _confirm(repository, visit_id="pre-archive-visit", label="northern_cardinal")

    repository.update_camera_source(SOURCE_ID, CameraSourceUpdate(archived=True))

    detail = repository.get_place_feature_detail(feature.id, now=at + timedelta(days=1), local_timezone=UTC)
    assert detail.representative_evidence is not None
    assert detail.representative_evidence.visit_id == "pre-archive-visit"


def test_feature_representative_evidence_reflects_correction_on_next_read(repository: ProductRepository) -> None:
    """No cache to invalidate -- a correction away from a confirmed taxon
    is reflected on the very next `get_place_feature_detail` call, mirroring
    test_reviewed_correction_moves_representative_eligibility_to_the_
    corrected_taxon's Today/Bird Log precedent at Feature scope."""

    feature = repository.add_place_feature(
        PlaceFeatureCreate(feature_type="water", name="Bird Bath", zone_id=ZONE_ID), acting_user=_acting_user()
    )
    at = datetime(2026, 6, 1, 10, tzinfo=UTC)
    _add_visit(repository, visit_id="corrected-visit", at=at)
    _attach_primary_evidence(repository, visit_id="corrected-visit", captured_at=at)
    _confirm(repository, visit_id="corrected-visit", label="northern_cardinal")

    before = repository.get_place_feature_detail(feature.id, now=at + timedelta(days=1), local_timezone=UTC)
    assert before.representative_evidence is not None
    assert before.representative_evidence.visit_id == "corrected-visit"

    _confirm(repository, visit_id="corrected-visit", label="false_positive")

    after = repository.get_place_feature_detail(feature.id, now=at + timedelta(days=1), local_timezone=UTC)
    assert after.representative_evidence is None, "a corrected-away Visit must stop being representative immediately"


def test_feature_detail_http_round_trip_includes_representative_evidence(repository: ProductRepository) -> None:
    feature = repository.add_place_feature(
        PlaceFeatureCreate(feature_type="water", name="Bird Bath", zone_id=ZONE_ID), acting_user=_acting_user()
    )
    at = datetime(2026, 6, 1, 10, tzinfo=UTC)
    _add_visit(repository, visit_id="http-visit", at=at)
    _attach_primary_evidence(repository, visit_id="http-visit", captured_at=at)
    _confirm(repository, visit_id="http-visit", label="northern_cardinal")

    client = LegacyAuthenticatedSyncTestClient(app)
    response = client.get(f"/api/place/features/{feature.id}/detail")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["representative_evidence"]["visit_id"] == "http-visit"
    assert body["representative_evidence"]["evidence"]["media_asset_id"] == "media-http-visit"


# --- Environmental Context x Place Story & Habitat Change Composition v1:
# Feature before/after environmental-context composition ------------------


def _feature_with_comparable_change(
    repository: ProductRepository, *, effective: date = date(2026, 6, 20),
) -> tuple[str, str, datetime]:
    """A Feature + change event whose wildlife-side comparison is guaranteed
    to reach `maturity in ("early_signal", "comparable")` at the smallest
    (7-day) window -- full exposure coverage on both sides clears
    `conditional_association`'s own usable-day floor regardless of presence,
    so no Visit needs to be seeded at all for these environmental-focused
    tests. Returns `(feature_id, event_id, now)`."""

    feature = repository.add_place_feature(
        PlaceFeatureCreate(feature_type="feeder", name="Feeder", zone_id=ZONE_ID), acting_user=_acting_user(),
    )
    event = repository.add_place_feature_change_event(
        PlaceFeatureChangeEventCreate(feature_id=feature.id, event_type="added", effective_date=effective),
        acting_user=_acting_user(),
    )
    now = datetime(effective.year, effective.month, effective.day, tzinfo=UTC) + timedelta(days=7)
    _cover_days(repository, start=effective - timedelta(days=7), days=14)
    return feature.id, event.id, now


def test_feature_environmental_comparison_not_configured_without_location(
    repository: ProductRepository,
) -> None:
    feature_id, _event_id, now = _feature_with_comparable_change(repository)
    detail = repository.get_place_feature_detail(feature_id, now=now, local_timezone=UTC)
    comparison = detail.changes[0]
    assert comparison.comparison.maturity == "comparable"
    assert comparison.environmental_comparison is not None
    assert comparison.environmental_comparison.status == "not_configured"
    assert comparison.environmental_comparison.summary is None
    # The window is still stated honestly even though nothing could be said
    # about it -- mirrors `PlaceFeatureAssociation`'s own window fields.
    assert comparison.environmental_comparison.window_days == 7


def test_feature_environmental_comparison_insufficient_coverage_without_cached_weather(
    repository: ProductRepository,
) -> None:
    effective = date(2026, 6, 20)
    feature_id, _event_id, now = _feature_with_comparable_change(repository, effective=effective)
    _enable_weather(repository)  # configured + enabled, but zero rows ever cached
    detail = repository.get_place_feature_detail(feature_id, now=now, local_timezone=UTC)
    environmental = detail.changes[0].environmental_comparison
    assert environmental is not None
    assert environmental.status == "insufficient_coverage"
    assert environmental.summary is None


def test_feature_environmental_comparison_notably_cooler_after(repository: ProductRepository) -> None:
    effective = date(2026, 6, 20)
    feature_id, _event_id, now = _feature_with_comparable_change(repository, effective=effective)
    _enable_weather(repository)
    pre_start = effective - timedelta(days=7)  # 2026-06-13
    post_end = effective + timedelta(days=7)  # 2026-06-27 (exclusive)
    # A broad, independent baseline at 15C, well outside [pre_start, post_end).
    _seed_flat_temperature_baseline(repository, before=pre_start, days=20, temperature_c=15.0)
    for offset in range(7):  # pre window: typical (15C)
        _insert_environmental_context_day(
            repository, metric="air_temperature", for_date=pre_start + timedelta(days=offset),
            value_numeric=15.0, unit="celsius",
        )
    for offset in range(7):  # post window: much colder
        _insert_environmental_context_day(
            repository, metric="air_temperature", for_date=effective + timedelta(days=offset),
            value_numeric=0.0, unit="celsius",
        )
    detail = repository.get_place_feature_detail(feature_id, now=now, local_timezone=UTC)
    environmental = detail.changes[0].environmental_comparison
    assert environmental is not None
    assert environmental.status == "comparable"
    assert environmental.summary == "The after period was notably cooler."
    assert environmental.pre_mean_temperature_c == pytest.approx(15.0)
    assert environmental.post_mean_temperature_c == pytest.approx(0.0)
    assert environmental.information_class == "inferred"
    assert environmental.provider_key == weather_provider.WEATHER_PROVIDER_KEY
    assert environmental.pre_start == pre_start
    assert environmental.post_end == post_end
    # Never a causal claim.
    for forbidden in ("caused", "led to", "resulted in", "because of", "drove", "due to"):
        assert forbidden not in environmental.summary.lower()


def test_feature_environmental_comparison_broadly_similar(repository: ProductRepository) -> None:
    effective = date(2026, 6, 20)
    feature_id, _event_id, now = _feature_with_comparable_change(repository, effective=effective)
    _enable_weather(repository)
    pre_start = effective - timedelta(days=7)
    _seed_flat_temperature_baseline(repository, before=pre_start, days=20, temperature_c=15.0)
    for offset in range(7):
        _insert_environmental_context_day(
            repository, metric="air_temperature", for_date=pre_start + timedelta(days=offset),
            value_numeric=15.0, unit="celsius",
        )
    for offset in range(7):  # post window: also typical -- nothing meaningfully different
        _insert_environmental_context_day(
            repository, metric="air_temperature", for_date=effective + timedelta(days=offset),
            value_numeric=15.0, unit="celsius",
        )
    detail = repository.get_place_feature_detail(feature_id, now=now, local_timezone=UTC)
    environmental = detail.changes[0].environmental_comparison
    assert environmental is not None
    assert environmental.status == "comparable"
    assert environmental.summary == "Conditions were broadly similar across the two periods."


def test_feature_environmental_comparison_is_none_when_wildlife_maturity_too_soon(
    repository: ProductRepository,
) -> None:
    feature = repository.add_place_feature(
        PlaceFeatureCreate(feature_type="feeder", name="Feeder", zone_id=ZONE_ID), acting_user=_acting_user(),
    )
    effective = date(2026, 6, 1)
    now = datetime(2026, 6, 3, tzinfo=UTC)  # only 2 days have elapsed
    repository.add_place_feature_change_event(
        PlaceFeatureChangeEventCreate(feature_id=feature.id, event_type="added", effective_date=effective),
        acting_user=_acting_user(),
    )
    _enable_weather(repository)
    detail = repository.get_place_feature_detail(feature.id, now=now, local_timezone=UTC)
    assert detail.changes[0].comparison.maturity == "too_soon"
    assert detail.changes[0].environmental_comparison is None


def test_correcting_change_event_date_also_collapses_environmental_comparison(
    repository: ProductRepository,
) -> None:
    """Correction safety (Phase 12 of the governing brief): moving a change
    event's own date so the wildlife comparison is no longer mature must
    also retract the environmental comparison it was aligned to -- no stale
    "notably cooler" claim may survive judging a period that is no longer
    the one actually being compared. Computed fresh at read time, exactly
    like `test_correcting_change_event_date_changes_comparison_on_next_read`."""

    feature = repository.add_place_feature(
        PlaceFeatureCreate(feature_type="feeder", name="Feeder", zone_id=ZONE_ID), acting_user=_acting_user(),
    )
    now = datetime(2026, 6, 8, tzinfo=UTC)
    event = repository.add_place_feature_change_event(
        PlaceFeatureChangeEventCreate(feature_id=feature.id, event_type="added", effective_date=date(2026, 6, 1)),
        acting_user=_acting_user(),
    )
    _cover_days(repository, start=date(2026, 5, 20), days=20)
    _enable_weather(repository)
    _seed_flat_temperature_baseline(repository, before=date(2026, 5, 25), days=20, temperature_c=15.0)
    for offset in range(7):
        _insert_environmental_context_day(
            repository, metric="air_temperature", for_date=date(2026, 5, 25) + timedelta(days=offset),
            value_numeric=15.0, unit="celsius",
        )
    for offset in range(7):
        _insert_environmental_context_day(
            repository, metric="air_temperature", for_date=date(2026, 6, 1) + timedelta(days=offset),
            value_numeric=0.0, unit="celsius",
        )
    before = repository.get_place_feature_detail(feature.id, now=now, local_timezone=UTC)
    assert before.changes[0].comparison.maturity == "comparable"
    assert before.changes[0].environmental_comparison is not None
    assert before.changes[0].environmental_comparison.status == "comparable"
    assert before.changes[0].environmental_comparison.summary == "The after period was notably cooler."

    repository.update_place_feature_change_event(
        event.id, PlaceFeatureChangeEventUpdate(effective_date=date(2026, 6, 6)), acting_user=_acting_user()
    )
    after = repository.get_place_feature_detail(feature.id, now=now, local_timezone=UTC)
    assert after.changes[0].comparison.maturity == "too_soon"
    assert after.changes[0].environmental_comparison is None


def test_feature_environmental_comparison_higher_rainfall_after(repository: ProductRepository) -> None:
    effective = date(2026, 6, 20)
    feature_id, _event_id, now = _feature_with_comparable_change(repository, effective=effective)
    _enable_weather(repository)
    pre_start = effective - timedelta(days=7)
    for offset in range(7):
        _insert_precipitation_day(repository, for_date=pre_start + timedelta(days=offset), total_mm=0.0)
    for offset in range(7):
        _insert_precipitation_day(repository, for_date=effective + timedelta(days=offset), total_mm=5.0)
    detail = repository.get_place_feature_detail(feature_id, now=now, local_timezone=UTC)
    environmental = detail.changes[0].environmental_comparison
    assert environmental is not None
    assert environmental.status == "comparable"
    assert environmental.summary == "Rainfall was higher during the after period."
    assert environmental.pre_total_precipitation_mm == pytest.approx(0.0)
    assert environmental.post_total_precipitation_mm == pytest.approx(35.0)


class _AlwaysFailsWeatherRequester:
    """Mirrors `test_local_only_privacy.py`'s identical fake -- always
    raises, and counts calls, so a test can prove a code path never even
    attempts a live fetch (not merely that it tolerates one failing)."""

    def __init__(self) -> None:
        self.call_count = 0

    def get(self, url: str, *, timeout_seconds: float) -> bytes:
        self.call_count += 1
        raise weather_provider.WeatherProviderUnavailableError("simulated: no internet route")


def test_feature_environmental_comparison_never_calls_the_network(tmp_path: Path) -> None:
    """Local Only (Phase 13 of the governing brief): composing environmental
    context onto a Feature comparison reads only already-persisted rows --
    it must never itself attempt a live provider fetch, even when weather is
    enabled and coordinates are configured. Proven, not assumed: a requester
    that always raises is injected, and its `call_count` stays exactly `0`
    after a full comparable-with-a-meaningful-difference read."""

    isolated_repository = ProductRepository(
        db_url=f"sqlite:///{tmp_path / 'mockingbird.sqlite3'}",
        media_root=tmp_path / "media",
        weather_requester=_AlwaysFailsWeatherRequester(),
    )
    configure_repository(isolated_repository)
    try:
        with isolated_repository.session_factory() as session:
            with session.begin():
                session.add(
                    CameraSourceModel(
                        id=SOURCE_ID, name="Feature fixture camera", kind="manual_upload",
                        status="connected", description="Place Features fixture.",
                    )
                )
                session.add(
                    StreamModel(
                        id=STREAM_ID, source_id=SOURCE_ID, name="Feature fixture stream",
                        description="Place Features fixture.", is_live=False,
                    )
                )
                session.add(
                    ZoneModel(
                        id=ZONE_ID, stream_id=STREAM_ID, name="Feeder", zone_type="feeder",
                        polygon_json="[]", is_active=True, monitoring_policy_json=None,
                    )
                )
        effective = date(2026, 6, 20)
        feature_id, _event_id, now = _feature_with_comparable_change(isolated_repository, effective=effective)
        _enable_weather(isolated_repository)
        pre_start = effective - timedelta(days=7)
        _seed_flat_temperature_baseline(isolated_repository, before=pre_start, days=20, temperature_c=15.0)
        for offset in range(7):
            _insert_environmental_context_day(
                isolated_repository, metric="air_temperature", for_date=pre_start + timedelta(days=offset),
                value_numeric=15.0, unit="celsius",
            )
        for offset in range(7):
            _insert_environmental_context_day(
                isolated_repository, metric="air_temperature", for_date=effective + timedelta(days=offset),
                value_numeric=0.0, unit="celsius",
            )

        detail = isolated_repository.get_place_feature_detail(feature_id, now=now, local_timezone=UTC)
        environmental = detail.changes[0].environmental_comparison
        assert environmental is not None
        assert environmental.status == "comparable"
        assert environmental.summary == "The after period was notably cooler."
        assert isolated_repository._weather_requester.call_count == 0, (
            "environmental-context composition attempted a live fetch -- Local Only violated"
        )
    finally:
        configure_repository(None)


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


def test_place_feature_observation_link_crud_over_http(repository: ProductRepository) -> None:
    _add_second_camera(repository)
    client = LegacyAuthenticatedSyncTestClient(app)
    created = client.post(
        "/api/place/features", json={"feature_type": "water", "name": "Bird Bath", "zone_id": ZONE_ID}
    )
    feature_id = created.json()["id"]

    link_response = client.post(
        f"/api/place/features/{feature_id}/observation-links", json={"zone_id": ZONE_ID_2}
    )
    assert link_response.status_code == 201
    link_id = link_response.json()["id"]
    assert link_response.json()["source_id"] == SOURCE_ID_2

    detail = client.get(f"/api/place/features/{feature_id}/detail").json()
    assert len(detail["feature"]["observation_links"]) == 2

    removed = client.delete(f"/api/place/features/{feature_id}/observation-links/{link_id}")
    assert removed.status_code == 204

    detail_after = client.get(f"/api/place/features/{feature_id}/detail").json()
    assert len(detail_after["feature"]["observation_links"]) == 1


def test_place_feature_observation_link_mutations_require_authentication(
    repository: ProductRepository,
) -> None:
    plain_client = TestClient(app)
    assert plain_client.post(
        "/api/place/features/feature-missing/observation-links", json={"source_id": SOURCE_ID}
    ).status_code == 401
    assert plain_client.delete(
        "/api/place/features/feature-missing/observation-links/link-missing"
    ).status_code == 401


def test_place_feature_observation_link_duplicate_is_422_over_http(repository: ProductRepository) -> None:
    client = LegacyAuthenticatedSyncTestClient(app)
    created = client.post(
        "/api/place/features", json={"feature_type": "feeder", "name": "Feeder", "zone_id": ZONE_ID}
    )
    feature_id = created.json()["id"]
    response = client.post(
        f"/api/place/features/{feature_id}/observation-links", json={"zone_id": ZONE_ID}
    )
    assert response.status_code == 422


def test_place_feature_observation_link_missing_feature_is_404_over_http(
    repository: ProductRepository,
) -> None:
    client = LegacyAuthenticatedSyncTestClient(app)
    response = client.post(
        "/api/place/features/feature-missing/observation-links", json={"source_id": SOURCE_ID}
    )
    assert response.status_code == 404


def test_place_feature_observation_link_missing_link_is_404_over_http(
    repository: ProductRepository,
) -> None:
    client = LegacyAuthenticatedSyncTestClient(app)
    created = client.post("/api/place/features", json={"feature_type": "feeder", "name": "Feeder"})
    feature_id = created.json()["id"]
    response = client.delete(f"/api/place/features/{feature_id}/observation-links/link-missing")
    assert response.status_code == 404


def test_place_features_summary_over_http(repository: ProductRepository) -> None:
    client = LegacyAuthenticatedSyncTestClient(app)
    response = client.get("/api/place/features-summary")
    assert response.status_code == 200
    body = response.json()
    assert body == {"active_feature_count": 0, "recent_change_count": 0, "highlight": None}


# --- Performance (Place Story Deep Dives & Representative Evidence v1,
# governing brief section 32): representative-evidence gathering must not
# grow with unrelated Place history depth -- mirrors test_year_over_year_
# comparison_repository.py's own `_count_queries` harness and identical
# "query count does not grow with unrelated historical depth" methodology.


def _count_queries(engine, fn) -> int:  # type: ignore[no-untyped-def]
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


def test_representative_evidence_query_count_does_not_grow_with_unrelated_history(
    repository: ProductRepository,
) -> None:
    feature = repository.add_place_feature(
        PlaceFeatureCreate(feature_type="water", name="Bird Bath", zone_id=ZONE_ID), acting_user=_acting_user()
    )
    at = datetime(2026, 6, 1, 10, tzinfo=UTC)
    _add_visit(repository, visit_id="perf-bath-visit", at=at)
    _attach_primary_evidence(repository, visit_id="perf-bath-visit", captured_at=at)
    _confirm(repository, visit_id="perf-bath-visit", label="northern_cardinal")

    def _read_detail() -> None:
        detail = repository.get_place_feature_detail(feature.id, now=at + timedelta(days=1), local_timezone=UTC)
        assert detail.representative_evidence is not None

    small_history_query_count = _count_queries(repository.engine, _read_detail)

    # A large amount of *unrelated* Place history: 100 confirmed Visits on
    # a completely different, unlinked camera/Zone -- must never be scanned
    # while resolving this Feature's own representative evidence.
    _add_second_camera(repository)
    for i in range(100):
        visit_id = f"perf-unrelated-{i}"
        unrelated_at = at - timedelta(days=i + 1)
        _add_visit(repository, visit_id=visit_id, at=unrelated_at, stream_id=STREAM_ID_2, zone_id=ZONE_ID_2)
        _attach_primary_evidence(repository, visit_id=visit_id, captured_at=unrelated_at, stream_id=STREAM_ID_2)
        _confirm(repository, visit_id=visit_id, label="carolina_wren")

    large_history_query_count = _count_queries(repository.engine, _read_detail)

    assert large_history_query_count == small_history_query_count, (
        f"query count grew with unrelated history: {small_history_query_count} -> {large_history_query_count}"
    )


def test_representative_evidence_query_count_does_not_grow_with_own_visit_count(
    repository: ProductRepository,
) -> None:
    """The bounded `MAX_REPRESENTATIVE_EVIDENCE_CANDIDATES` cap (20, the
    identical constant Today/Bird Log already use) means even this
    Feature's *own* confirmed-Visit count does not change the query count
    once it exceeds that bound -- proportional, never unbounded."""

    feature = repository.add_place_feature(
        PlaceFeatureCreate(feature_type="water", name="Bird Bath", zone_id=ZONE_ID), acting_user=_acting_user()
    )
    base_at = datetime(2026, 1, 1, tzinfo=UTC)

    def _seed_confirmed_visits(count: int, prefix: str) -> None:
        for i in range(count):
            visit_id = f"{prefix}-{i}"
            at = base_at + timedelta(days=i)
            _add_visit(repository, visit_id=visit_id, at=at)
            _attach_primary_evidence(repository, visit_id=visit_id, captured_at=at)
            _confirm(repository, visit_id=visit_id, label="northern_cardinal")

    def _read_detail() -> None:
        detail = repository.get_place_feature_detail(
            feature.id, now=base_at + timedelta(days=200), local_timezone=UTC,
        )
        assert detail.representative_evidence is not None

    _seed_confirmed_visits(25, "perf-many-a")
    query_count_at_25 = _count_queries(repository.engine, _read_detail)

    _seed_confirmed_visits(25, "perf-many-b")
    query_count_at_50 = _count_queries(repository.engine, _read_detail)

    assert query_count_at_50 == query_count_at_25, (
        f"query count grew with this Feature's own Visit count past the bound: "
        f"{query_count_at_25} -> {query_count_at_50}"
    )
