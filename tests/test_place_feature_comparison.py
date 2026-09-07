"""Place Feature Comparison & Habitat Outcomes v1 (see docs/place-feature-
comparison-habitat-outcomes-v1-contract.md).

Covers the new, bounded, Place-wide comparison surface
(`ProductRepository.get_place_feature_comparison_overview`,
`GET /api/place/feature-comparison`). Deliberately does not re-test the
underlying primitives this milestone reuses unmodified (window escalation,
yield computation, cross-camera dedup, coverage union, environmental
composition, representative-evidence selection) -- those stay covered by
their own existing test files (`test_place_feature.py`,
`test_conditional_association.py`, `test_environmental_period_comparison.py`,
`test_representative_evidence.py`). This file instead proves: the overview
composes those primitives correctly across many Features at once; fairness
(insufficient-data Features/events stay visible, never hidden or zeroed);
correction/archival safety; Local Only; and that the batched composition is
actually cheaper than calling `get_place_feature_detail` independently once
per Feature.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import event
from starlette.testclient import TestClient

from mockingbird.api.main import app, configure_repository
from mockingbird.api.schemas import (
    CameraSourceUpdate,
    EnvironmentalContextSettingsUpdate,
    PlaceFeatureChangeEventCreate,
    PlaceFeatureChangeEventUpdate,
    PlaceFeatureCreate,
    PlaceFeatureObservationLinkCreate,
)
from mockingbird.environment import weather_provider
from mockingbird.repository.product_repository import ProductRepository
from mockingbird.storage.models import (
    CameraSourceModel,
    EnvironmentalContextRecordModel,
    EventModel,
    MediaAssetModel,
    MonitoringExposureIntervalModel,
    StreamModel,
    VisitEvidenceLinkModel,
    VisitModel,
    ZoneModel,
)
from tests.conftest import LegacyAuthenticatedSyncTestClient
from tests.test_place_feature import _acting_user

SOURCE_ID = "source-feature-comparison"
STREAM_ID = "stream-feature-comparison"
ZONE_ID = "zone-feature-comparison-feeder"
SOURCE_ID_2 = "source-feature-comparison-2"
STREAM_ID_2 = "stream-feature-comparison-2"
ZONE_ID_2 = "zone-feature-comparison-2"
WEATHER_LATITUDE = 40.7
WEATHER_LONGITUDE = -74.0


@pytest.fixture
def repository(tmp_path: Path) -> ProductRepository:
    repository = ProductRepository(
        db_url=f"sqlite:///{tmp_path / 'mockingbird.sqlite3'}",
        media_root=tmp_path / "media",
    )
    configure_repository(repository)
    with repository.session_factory() as session:
        with session.begin():
            session.add(
                CameraSourceModel(
                    id=SOURCE_ID, name="Comparison fixture camera", kind="manual_upload",
                    status="connected", description="Place Feature Comparison fixture.",
                )
            )
            session.add(
                StreamModel(
                    id=STREAM_ID, source_id=SOURCE_ID, name="Comparison fixture stream",
                    description="Place Feature Comparison fixture.", is_live=False,
                )
            )
            session.add(
                ZoneModel(
                    id=ZONE_ID, stream_id=STREAM_ID, name="Feeder", zone_type="feeder",
                    polygon_json="[]", is_active=True, monitoring_policy_json=None,
                )
            )
    yield repository
    configure_repository(None)


def _add_second_camera(repository: ProductRepository) -> None:
    with repository.session_factory() as session:
        with session.begin():
            session.add(
                CameraSourceModel(
                    id=SOURCE_ID_2, name="Comparison fixture camera 2", kind="manual_upload",
                    status="connected", description="Place Feature Comparison fixture (second camera).",
                )
            )
            session.add(
                StreamModel(
                    id=STREAM_ID_2, source_id=SOURCE_ID_2, name="Comparison fixture stream 2",
                    description="Place Feature Comparison fixture (second camera).", is_live=False,
                )
            )
            session.add(
                ZoneModel(
                    id=ZONE_ID_2, stream_id=STREAM_ID_2, name="Feeder (second view)", zone_type="feeder",
                    polygon_json="[]", is_active=True, monitoring_policy_json=None,
                )
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
                    id=event_id, stream_id=stream_id, title=f"Comparison fixture {visit_id}",
                    event_type="manual_media_import", started_at=at, ended_at=at + timedelta(seconds=20),
                    primary_zone_id=zone_id, review_status="needs_review",
                )
            )
            session.add(
                VisitModel(
                    id=visit_id, event_id=event_id, subject_label="unknown_bird", species_guess=None,
                    confidence=None, reviewed_label=None, review_status="needs_review",
                    representative_media_path=None, zone_id=zone_id, is_superseded=False,
                )
            )


def _confirm(repository: ProductRepository, *, visit_id: str, label: str = "northern_cardinal") -> None:
    from mockingbird.api.schemas import ReviewCorrectionCreate

    repository.create_review_label(
        ReviewCorrectionCreate(target_type="visit", target_id=visit_id, label=label, review_origin="human")
    )


def _add_exposure(
    repository: ProductRepository, *, interval_id: str, started_at: datetime, ended_at: datetime,
    stream_id: str = STREAM_ID, source_id: str = SOURCE_ID,
) -> None:
    with repository.session_factory() as session:
        with session.begin():
            session.add(
                MonitoringExposureIntervalModel(
                    id=interval_id, stream_id=stream_id, source_id=source_id,
                    runtime_generation_id=f"generation-{interval_id}", started_at=started_at,
                    last_confirmed_fresh_at=ended_at, ended_at=ended_at, close_reason="provider_failure",
                    created_at=started_at, updated_at=ended_at,
                )
            )


def _cover_days(
    repository: ProductRepository, *, start: date, days: int, stream_id: str = STREAM_ID,
    source_id: str = SOURCE_ID,
) -> None:
    for offset in range(days):
        day = start + timedelta(days=offset)
        started_at = datetime(day.year, day.month, day.day, tzinfo=UTC)
        _add_exposure(
            repository, interval_id=f"exposure-{stream_id}-{day.isoformat()}",
            started_at=started_at, ended_at=started_at + timedelta(hours=23),
            stream_id=stream_id, source_id=source_id,
        )


def _attach_primary_evidence(
    repository: ProductRepository, *, visit_id: str, captured_at: datetime,
    stream_id: str = STREAM_ID, source_id: str = SOURCE_ID, missing_file: bool = False,
) -> str:
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


def _enable_weather(
    repository: ProductRepository, *, latitude: float = WEATHER_LATITUDE, longitude: float = WEATHER_LONGITUDE,
) -> None:
    repository.update_environmental_context_settings(
        EnvironmentalContextSettingsUpdate(latitude=latitude, longitude=longitude, weather_enabled=True),
        acting_user=_acting_user(),
    )


def _insert_environmental_context_day(
    repository: ProductRepository, *, metric: str, for_date: date, value_numeric: float, unit: str,
) -> None:
    now = datetime.now(UTC)
    with repository.session_factory() as session:
        with session.begin():
            for hour in range(24):
                session.add(
                    EnvironmentalContextRecordModel(
                        id=f"envctx-comparison-{metric}-{for_date.isoformat()}-{hour:02d}",
                        source_id=None, provider_key=weather_provider.WEATHER_PROVIDER_KEY,
                        information_class=weather_provider.WEATHER_INFORMATION_CLASS, metric=metric,
                        value_numeric=value_numeric, value_text=None, unit=unit,
                        observed_at=datetime(for_date.year, for_date.month, for_date.day, hour, tzinfo=UTC),
                        observed_at_end=None, for_date=for_date, retrieved_at=now,
                        basis_latitude=WEATHER_LATITUDE, basis_longitude=WEATHER_LONGITUDE,
                        provenance_json=None, provenance_schema_version=1, created_at=now,
                    )
                )


def _seed_flat_temperature_baseline(repository: ProductRepository, *, before: date, days: int, temperature_c: float) -> None:
    for offset in range(1, days + 1):
        _insert_environmental_context_day(
            repository, metric="air_temperature", for_date=before - timedelta(days=offset),
            value_numeric=temperature_c, unit="celsius",
        )


def _seed_feature_with_higher_activity_after(
    repository: ProductRepository, *, name: str, effective: date, now: datetime, zone_id: str = ZONE_ID,
    stream_id: str = STREAM_ID, seed_coverage: bool = True,
) -> tuple[str, str]:
    """A Feature + one `"added"` change event with an unambiguous
    `"more_common_under_condition"`/`"comparable"` outcome at the smallest
    (7-day) window, plus enough recent activity for a sufficient yield rate.
    Returns `(feature_id, event_id)`. `seed_coverage=False` skips seeding
    this Stream's own exposure coverage -- for a caller seeding several
    Features that share one Stream (coverage is Stream-scoped, so seeding
    it more than once for the same Stream/day would collide), the first
    call seeds it and the rest pass `False`."""

    feature = repository.add_place_feature(
        PlaceFeatureCreate(feature_type="feeder", name=name, zone_id=zone_id), acting_user=_acting_user(),
    )
    change_event = repository.add_place_feature_change_event(
        PlaceFeatureChangeEventCreate(feature_id=feature.id, event_type="added", effective_date=effective),
        acting_user=_acting_user(),
    )
    if seed_coverage:
        _cover_days(repository, start=effective - timedelta(days=7), days=14, stream_id=stream_id)
    for offset in range(7):
        day = effective + timedelta(days=offset)
        visit_id = f"{feature.id}-visit-{offset}"
        _add_visit(
            repository, visit_id=visit_id, at=datetime(day.year, day.month, day.day, 10, tzinfo=UTC),
            stream_id=stream_id, zone_id=zone_id,
        )
        _confirm(repository, visit_id=visit_id)
    return feature.id, change_event.id


# --- Basic composition / reuse correctness ----------------------------------


def test_overview_empty_place_is_honest_empty_lists(repository: ProductRepository) -> None:
    overview = repository.get_place_feature_comparison_overview(now=datetime(2026, 6, 8, tzinfo=UTC), local_timezone=UTC)
    assert overview.features == []
    assert overview.change_outcomes == []


def test_overview_row_matches_detail_bundle_exactly(repository: ProductRepository) -> None:
    """The overview must never recompute a second, drifting answer -- its
    per-Feature figures must be byte-identical to what `get_place_feature_
    detail` independently returns for that same Feature."""

    now = datetime(2026, 6, 8, tzinfo=UTC)
    feature_id, event_id = _seed_feature_with_higher_activity_after(
        repository, name="Sunflower feeder", effective=date(2026, 6, 1), now=now,
    )
    _attach_primary_evidence(repository, visit_id=f"{feature_id}-visit-0", captured_at=datetime(2026, 6, 1, 10, tzinfo=UTC))

    overview = repository.get_place_feature_comparison_overview(now=now, local_timezone=UTC)
    detail = repository.get_place_feature_detail(feature_id, now=now, local_timezone=UTC)

    row = next(row for row in overview.features if row.feature.id == feature_id)
    assert row.feature == detail.feature
    assert row.recent_yield == detail.recent_yield
    assert row.representative_evidence == detail.representative_evidence
    latest_from_detail = next(c for c in detail.changes if c.event.id == event_id)
    assert row.latest_change == latest_from_detail


def test_overview_latest_change_is_most_recent_not_full_history(repository: ProductRepository) -> None:
    """Deliverable A's per-Feature row carries only the single most recent
    change event's comparison -- the Feature's full timeline stays reachable
    via `change_outcomes`/the Feature's own Story, never duplicated here."""

    feature = repository.add_place_feature(
        PlaceFeatureCreate(feature_type="feeder", name="Feeder", zone_id=ZONE_ID), acting_user=_acting_user(),
    )
    older = repository.add_place_feature_change_event(
        PlaceFeatureChangeEventCreate(feature_id=feature.id, event_type="added", effective_date=date(2026, 1, 1)),
        acting_user=_acting_user(),
    )
    newer = repository.add_place_feature_change_event(
        PlaceFeatureChangeEventCreate(
            feature_id=feature.id, event_type="food_changed", effective_date=date(2026, 5, 1),
        ),
        acting_user=_acting_user(),
    )
    now = datetime(2026, 6, 8, tzinfo=UTC)
    overview = repository.get_place_feature_comparison_overview(now=now, local_timezone=UTC)
    row = next(row for row in overview.features if row.feature.id == feature.id)
    assert row.latest_change.event.id == newer.id

    outcome_event_ids = {outcome.event.id for outcome in overview.change_outcomes}
    assert older.id in outcome_event_ids
    assert newer.id in outcome_event_ids


# --- Comparable Features with different monitoring effort -------------------


def test_overview_yield_rate_comparable_across_different_monitoring_effort(repository: ProductRepository) -> None:
    _add_second_camera(repository)
    now = datetime(2026, 6, 8, tzinfo=UTC)
    # Feature A: one camera, modest coverage.
    feature_a_id, _ = _seed_feature_with_higher_activity_after(
        repository, name="Feeder A", effective=date(2026, 6, 1), now=now,
    )
    # Feature B: a different camera, double the daily coverage window, but
    # the identical per-day Visit pattern -- a genuinely lower per-hour rate,
    # even though its raw Visit count is the same.
    feature_b = repository.add_place_feature(
        PlaceFeatureCreate(feature_type="water", name="Bird Bath B", zone_id=ZONE_ID_2), acting_user=_acting_user(),
    )
    _cover_days(repository, start=date(2026, 6, 1) - timedelta(days=1), days=8, stream_id=STREAM_ID_2, source_id=SOURCE_ID_2)
    for offset in range(7):
        day = date(2026, 6, 1) + timedelta(days=offset)
        visit_id = f"feature-b-visit-{offset}"
        _add_visit(
            repository, visit_id=visit_id, at=datetime(day.year, day.month, day.day, 10, tzinfo=UTC),
            stream_id=STREAM_ID_2, zone_id=ZONE_ID_2,
        )
        _confirm(repository, visit_id=visit_id)

    overview = repository.get_place_feature_comparison_overview(now=now, local_timezone=UTC)
    row_a = next(row for row in overview.features if row.feature.id == feature_a_id)
    row_b = next(row for row in overview.features if row.feature.id == feature_b.id)
    assert row_a.recent_yield.data_sufficient is True
    assert row_b.recent_yield.data_sufficient is True
    assert row_a.recent_yield.confirmed_wildlife_visit_count == row_b.recent_yield.confirmed_wildlife_visit_count == 7
    # Both rates are honest, independently-normalized figures -- safe to
    # sort/compare precisely because both cleared `data_sufficient`.
    assert row_a.recent_yield.visits_per_monitored_hour is not None
    assert row_b.recent_yield.visits_per_monitored_hour is not None


# --- Insufficient coverage / immature changes remain visible -----------------


def test_overview_unlinked_feature_shows_no_yield_but_latest_change_is_still_visible(
    repository: ProductRepository,
) -> None:
    feature = repository.add_place_feature(PlaceFeatureCreate(feature_type="feeder", name="Unlinked feeder"), acting_user=_acting_user())
    event = repository.add_place_feature_change_event(
        PlaceFeatureChangeEventCreate(feature_id=feature.id, event_type="added", effective_date=date(2026, 6, 1)),
        acting_user=_acting_user(),
    )
    now = datetime(2026, 6, 8, tzinfo=UTC)
    overview = repository.get_place_feature_comparison_overview(now=now, local_timezone=UTC)
    row = next(row for row in overview.features if row.feature.id == feature.id)
    assert row.recent_yield is None
    assert row.latest_change is not None
    assert row.latest_change.event.id == event.id
    assert row.latest_change.comparison is None, "no monitoring scope exists -- honestly no comparison attempted"
    # An unlinked Feature's event was never attempted -- excluded from
    # change_outcomes (never a fabricated too_soon/insufficient entry).
    assert event.id not in {outcome.event.id for outcome in overview.change_outcomes}


def test_overview_low_coverage_yield_marked_insufficient_not_hidden(repository: ProductRepository) -> None:
    feature = repository.add_place_feature(
        PlaceFeatureCreate(feature_type="feeder", name="New feeder", zone_id=ZONE_ID), acting_user=_acting_user(),
    )
    now = datetime(2026, 6, 8, tzinfo=UTC)
    # Under 2 monitored hours in the recent 7-day window.
    _add_exposure(
        repository, interval_id="thin-exposure", started_at=now - timedelta(hours=1), ended_at=now,
    )
    overview = repository.get_place_feature_comparison_overview(now=now, local_timezone=UTC)
    row = next(row for row in overview.features if row.feature.id == feature.id)
    assert row.recent_yield is not None
    assert row.recent_yield.data_sufficient is False
    assert row.recent_yield.visits_per_monitored_hour is None


def test_overview_too_soon_change_event_is_visible_in_change_outcomes(repository: ProductRepository) -> None:
    feature = repository.add_place_feature(
        PlaceFeatureCreate(feature_type="feeder", name="Feeder", zone_id=ZONE_ID), acting_user=_acting_user(),
    )
    event = repository.add_place_feature_change_event(
        PlaceFeatureChangeEventCreate(feature_id=feature.id, event_type="added", effective_date=date(2026, 6, 6)),
        acting_user=_acting_user(),
    )
    now = datetime(2026, 6, 8, tzinfo=UTC)  # only 2 days elapsed
    overview = repository.get_place_feature_comparison_overview(now=now, local_timezone=UTC)
    outcome = next(o for o in overview.change_outcomes if o.event.id == event.id)
    assert outcome.comparison.maturity == "too_soon"
    assert outcome.comparison.status is None


# --- No material difference / meaningful positive and negative associations -


def test_overview_change_outcomes_no_clear_association(repository: ProductRepository) -> None:
    feature = repository.add_place_feature(
        PlaceFeatureCreate(feature_type="feeder", name="Feeder", zone_id=ZONE_ID), acting_user=_acting_user(),
    )
    effective = date(2026, 6, 1)
    event = repository.add_place_feature_change_event(
        PlaceFeatureChangeEventCreate(feature_id=feature.id, event_type="added", effective_date=effective),
        acting_user=_acting_user(),
    )
    now = datetime(2026, 6, 8, tzinfo=UTC)
    _cover_days(repository, start=effective - timedelta(days=7), days=14)
    # Identical presence pattern before and after -- no supported difference.
    for offset in (1, 3, 5):
        for base in (effective - timedelta(days=7), effective):
            day = base + timedelta(days=offset)
            visit_id = f"nca-{day.isoformat()}"
            _add_visit(repository, visit_id=visit_id, at=datetime(day.year, day.month, day.day, 10, tzinfo=UTC))
            _confirm(repository, visit_id=visit_id)

    overview = repository.get_place_feature_comparison_overview(now=now, local_timezone=UTC)
    outcome = next(o for o in overview.change_outcomes if o.event.id == event.id)
    assert outcome.comparison.maturity == "comparable"
    assert outcome.comparison.status == "no_clear_association"


def test_overview_change_outcomes_include_positive_and_negative_associations(
    repository: ProductRepository,
) -> None:
    _add_second_camera(repository)
    now = datetime(2026, 6, 8, tzinfo=UTC)
    positive_feature_id, positive_event_id = _seed_feature_with_higher_activity_after(
        repository, name="More active after", effective=date(2026, 6, 1), now=now,
    )

    # A second Feature, on the second camera, with activity only *before*
    # its change -- an unambiguous "less_common_under_condition".
    negative_feature = repository.add_place_feature(
        PlaceFeatureCreate(feature_type="feeder", name="Less active after", zone_id=ZONE_ID_2),
        acting_user=_acting_user(),
    )
    negative_event = repository.add_place_feature_change_event(
        PlaceFeatureChangeEventCreate(feature_id=negative_feature.id, event_type="added", effective_date=date(2026, 6, 1)),
        acting_user=_acting_user(),
    )
    _cover_days(repository, start=date(2026, 6, 1) - timedelta(days=7), days=14, stream_id=STREAM_ID_2, source_id=SOURCE_ID_2)
    for offset in range(7):
        day = date(2026, 6, 1) - timedelta(days=7) + timedelta(days=offset)
        visit_id = f"neg-visit-{offset}"
        _add_visit(
            repository, visit_id=visit_id, at=datetime(day.year, day.month, day.day, 10, tzinfo=UTC),
            stream_id=STREAM_ID_2, zone_id=ZONE_ID_2,
        )
        _confirm(repository, visit_id=visit_id)

    overview = repository.get_place_feature_comparison_overview(now=now, local_timezone=UTC)
    outcomes_by_event = {o.event.id: o for o in overview.change_outcomes}
    assert outcomes_by_event[positive_event_id].comparison.status == "more_common_under_condition"
    assert outcomes_by_event[negative_event.id].comparison.status == "less_common_under_condition"


def test_overview_change_outcomes_can_have_different_window_days(repository: ProductRepository) -> None:
    """Two events legitimately resolving to different window sizes must
    both be surfaced with their own, honestly differing `window_days` --
    never silently treated as directly comparable magnitudes."""

    _add_second_camera(repository)
    now_seven = date(2026, 6, 20) + timedelta(days=7)
    now = datetime(now_seven.year, now_seven.month, now_seven.day, tzinfo=UTC)
    seven_day_feature_id, seven_day_event_id = _seed_feature_with_higher_activity_after(
        repository, name="Seven-day feeder", effective=date(2026, 6, 20), now=now,
    )

    # A second Feature whose 7- and 14-day windows are too thin, but whose
    # 30-day window clears the floor -- escalates to window_days=30.
    thin_feature = repository.add_place_feature(
        PlaceFeatureCreate(feature_type="feeder", name="Thirty-day feeder", zone_id=ZONE_ID_2),
        acting_user=_acting_user(),
    )
    effective = date(2026, 5, 24)
    thin_event = repository.add_place_feature_change_event(
        PlaceFeatureChangeEventCreate(feature_id=thin_feature.id, event_type="added", effective_date=effective),
        acting_user=_acting_user(),
    )
    # Coverage only within 3 days each side of the change (too thin for the
    # 7/14-day windows' 5-usable-day floor) plus a wide band only reachable
    # by the 30-day window.
    for offset in range(1, 4):
        day = effective - timedelta(days=offset)
        _add_exposure(
            repository, interval_id=f"thin-pre-{offset}", started_at=datetime(day.year, day.month, day.day, tzinfo=UTC),
            ended_at=datetime(day.year, day.month, day.day, 23, tzinfo=UTC), stream_id=STREAM_ID_2, source_id=SOURCE_ID_2,
        )
    for offset in range(3):
        day = effective + timedelta(days=offset)
        _add_exposure(
            repository, interval_id=f"thin-post-{offset}", started_at=datetime(day.year, day.month, day.day, tzinfo=UTC),
            ended_at=datetime(day.year, day.month, day.day, 23, tzinfo=UTC), stream_id=STREAM_ID_2, source_id=SOURCE_ID_2,
        )
    for offset in range(15, 21):
        pre_day = effective - timedelta(days=offset)
        post_day = effective + timedelta(days=offset)
        for day in (pre_day, post_day):
            _add_exposure(
                repository, interval_id=f"thin-wide-{day.isoformat()}",
                started_at=datetime(day.year, day.month, day.day, tzinfo=UTC),
                ended_at=datetime(day.year, day.month, day.day, 23, tzinfo=UTC), stream_id=STREAM_ID_2,
                source_id=SOURCE_ID_2,
            )
    now_thirty = datetime(effective.year, effective.month, effective.day, tzinfo=UTC) + timedelta(days=30)

    overview = repository.get_place_feature_comparison_overview(now=max(now, now_thirty), local_timezone=UTC)
    outcomes_by_event = {o.event.id: o for o in overview.change_outcomes}
    assert outcomes_by_event[seven_day_event_id].comparison.window_days == 7
    assert outcomes_by_event[seven_day_event_id].comparison.maturity == "comparable"
    assert outcomes_by_event[thin_event.id].comparison.window_days == 30
    assert outcomes_by_event[thin_event.id].comparison.maturity == "early_signal"
    assert (
        outcomes_by_event[seven_day_event_id].comparison.window_days
        != outcomes_by_event[thin_event.id].comparison.window_days
    )


# --- Multi-camera dedup and coverage union -----------------------------------


def test_overview_yield_dedupes_confirmed_cross_camera_pair(repository: ProductRepository) -> None:
    from mockingbird.repository.product_repository import CrossCameraVisitAssociationModel

    _add_second_camera(repository)
    feature = repository.add_place_feature(
        PlaceFeatureCreate(feature_type="water", name="Bird Bath", zone_id=ZONE_ID), acting_user=_acting_user(),
    )
    repository.add_place_feature_observation_link(
        feature.id, PlaceFeatureObservationLinkCreate(zone_id=ZONE_ID_2), acting_user=_acting_user(),
    )
    now = datetime(2026, 6, 8, tzinfo=UTC)
    at = now - timedelta(days=1)
    _add_visit(repository, visit_id="dedup-cam-a", at=at, stream_id=STREAM_ID, zone_id=ZONE_ID)
    _add_visit(repository, visit_id="dedup-cam-b", at=at, stream_id=STREAM_ID_2, zone_id=ZONE_ID_2)
    _confirm(repository, visit_id="dedup-cam-a")
    _confirm(repository, visit_id="dedup-cam-b")
    primary_id, secondary_id = sorted(("dedup-cam-a", "dedup-cam-b"))
    with repository.session_factory() as session:
        with session.begin():
            session.add(
                CrossCameraVisitAssociationModel(
                    id="assoc-dedup", primary_visit_id=primary_id, secondary_visit_id=secondary_id,
                    tier="associated", overlap_ms=1000, gap_ms=0, spatial_signal="matching_area_name",
                    multi_subject=False, engine_version="cross-camera-association-v1",
                    created_at=now, updated_at=now,
                )
            )

    overview = repository.get_place_feature_comparison_overview(now=now, local_timezone=UTC)
    row = next(row for row in overview.features if row.feature.id == feature.id)
    assert row.recent_yield.confirmed_wildlife_visit_count == 1


def test_overview_coverage_is_union_not_sum(repository: ProductRepository) -> None:
    _add_second_camera(repository)
    feature = repository.add_place_feature(
        PlaceFeatureCreate(feature_type="water", name="Bird Bath", zone_id=ZONE_ID), acting_user=_acting_user(),
    )
    repository.add_place_feature_observation_link(
        feature.id, PlaceFeatureObservationLinkCreate(zone_id=ZONE_ID_2), acting_user=_acting_user(),
    )
    now = datetime(2026, 6, 8, tzinfo=UTC)
    window_start = now - timedelta(days=1)
    # Fully overlapping 20-hour exposure on both cameras -- a union should
    # report ~20 hours, never ~40.
    _add_exposure(repository, interval_id="cov-a", started_at=window_start, ended_at=window_start + timedelta(hours=20))
    _add_exposure(
        repository, interval_id="cov-b", started_at=window_start, ended_at=window_start + timedelta(hours=20),
        stream_id=STREAM_ID_2, source_id=SOURCE_ID_2,
    )
    overview = repository.get_place_feature_comparison_overview(now=now, local_timezone=UTC)
    row = next(row for row in overview.features if row.feature.id == feature.id)
    assert row.recent_yield.monitored_seconds == pytest.approx(20 * 3600, rel=0.01)


def test_overview_multi_link_feature_shows_all_observation_links(repository: ProductRepository) -> None:
    _add_second_camera(repository)
    feature = repository.add_place_feature(
        PlaceFeatureCreate(feature_type="water", name="Bird Bath", zone_id=ZONE_ID), acting_user=_acting_user(),
    )
    repository.add_place_feature_observation_link(
        feature.id, PlaceFeatureObservationLinkCreate(zone_id=ZONE_ID_2), acting_user=_acting_user(),
    )
    now = datetime(2026, 6, 8, tzinfo=UTC)
    overview = repository.get_place_feature_comparison_overview(now=now, local_timezone=UTC)
    row = next(row for row in overview.features if row.feature.id == feature.id)
    assert len(row.feature.observation_links) == 2
    assert row.feature.source_id is None and row.feature.zone_id is None, "NULL/NULL compatibility mirror for multi-link"


# --- Archived-camera history --------------------------------------------------


def test_overview_archived_camera_feature_still_shows_comparison(repository: ProductRepository) -> None:
    now = datetime(2026, 6, 8, tzinfo=UTC)
    feature_id, event_id = _seed_feature_with_higher_activity_after(
        repository, name="Feeder", effective=date(2026, 6, 1), now=now,
    )
    repository.update_camera_source(SOURCE_ID, CameraSourceUpdate(archived=True))

    overview = repository.get_place_feature_comparison_overview(now=now, local_timezone=UTC)
    row = next(row for row in overview.features if row.feature.id == feature_id)
    assert row.latest_change.comparison.maturity == "comparable"
    assert row.latest_change.comparison.status == "more_common_under_condition"
    assert row.feature.observation_links[0].source_archived is True
    outcome = next(o for o in overview.change_outcomes if o.event.id == event_id)
    assert outcome.comparison.maturity == "comparable"


# --- Correction/history safety -----------------------------------------------


def test_overview_reflects_change_event_date_correction_on_next_read(repository: ProductRepository) -> None:
    feature = repository.add_place_feature(
        PlaceFeatureCreate(feature_type="feeder", name="Feeder", zone_id=ZONE_ID), acting_user=_acting_user(),
    )
    now = datetime(2026, 6, 8, tzinfo=UTC)
    event = repository.add_place_feature_change_event(
        PlaceFeatureChangeEventCreate(feature_id=feature.id, event_type="added", effective_date=date(2026, 6, 1)),
        acting_user=_acting_user(),
    )
    _cover_days(repository, start=date(2026, 5, 20), days=20)

    before = repository.get_place_feature_comparison_overview(now=now, local_timezone=UTC)
    before_outcome = next(o for o in before.change_outcomes if o.event.id == event.id)
    assert before_outcome.comparison.maturity == "comparable"

    repository.update_place_feature_change_event(
        event.id, PlaceFeatureChangeEventUpdate(effective_date=date(2026, 6, 6)), acting_user=_acting_user(),
    )
    after = repository.get_place_feature_comparison_overview(now=now, local_timezone=UTC)
    after_outcome = next(o for o in after.change_outcomes if o.event.id == event.id)
    assert after_outcome.comparison.maturity == "too_soon"


def test_overview_reflects_change_event_removal_on_next_read(repository: ProductRepository) -> None:
    feature = repository.add_place_feature(
        PlaceFeatureCreate(feature_type="feeder", name="Feeder"), acting_user=_acting_user(),
    )
    event = repository.add_place_feature_change_event(
        PlaceFeatureChangeEventCreate(feature_id=feature.id, event_type="food_changed", effective_date=date(2026, 6, 1)),
        acting_user=_acting_user(),
    )
    now = datetime(2026, 6, 8, tzinfo=UTC)
    before = repository.get_place_feature_comparison_overview(now=now, local_timezone=UTC)
    row_before = next(row for row in before.features if row.feature.id == feature.id)
    assert row_before.latest_change.event.id == event.id

    repository.remove_place_feature_change_event(event.id, acting_user=_acting_user())
    after = repository.get_place_feature_comparison_overview(now=now, local_timezone=UTC)
    row_after = next(row for row in after.features if row.feature.id == feature.id)
    assert row_after.latest_change is None


def test_overview_reflects_species_correction_on_next_read(repository: ProductRepository) -> None:
    feature = repository.add_place_feature(
        PlaceFeatureCreate(feature_type="water", name="Bird Bath", zone_id=ZONE_ID), acting_user=_acting_user(),
    )
    at = datetime(2026, 6, 1, 10, tzinfo=UTC)
    _add_visit(repository, visit_id="corrected-visit", at=at)
    _attach_primary_evidence(repository, visit_id="corrected-visit", captured_at=at)
    _confirm(repository, visit_id="corrected-visit", label="northern_cardinal")

    now = at + timedelta(days=1)
    before = repository.get_place_feature_comparison_overview(now=now, local_timezone=UTC)
    row_before = next(row for row in before.features if row.feature.id == feature.id)
    assert row_before.representative_evidence is not None
    assert row_before.recent_yield.confirmed_wildlife_visit_count == 1

    _confirm(repository, visit_id="corrected-visit", label="false_positive")
    after = repository.get_place_feature_comparison_overview(now=now, local_timezone=UTC)
    row_after = next(row for row in after.features if row.feature.id == feature.id)
    assert row_after.representative_evidence is None
    assert row_after.recent_yield.confirmed_wildlife_visit_count == 0


# --- Environmental context: once, non-causal ---------------------------------


def test_overview_environmental_comparison_present_once_and_non_causal(repository: ProductRepository) -> None:
    now = datetime(2026, 6, 27, tzinfo=UTC)
    feature_id, event_id = _seed_feature_with_higher_activity_after(
        repository, name="Feeder", effective=date(2026, 6, 20), now=now,
    )
    _enable_weather(repository)
    pre_start = date(2026, 6, 13)
    _seed_flat_temperature_baseline(repository, before=pre_start, days=20, temperature_c=15.0)
    for offset in range(7):
        _insert_environmental_context_day(
            repository, metric="air_temperature", for_date=pre_start + timedelta(days=offset),
            value_numeric=15.0, unit="celsius",
        )
    for offset in range(7):
        _insert_environmental_context_day(
            repository, metric="air_temperature", for_date=date(2026, 6, 20) + timedelta(days=offset),
            value_numeric=0.0, unit="celsius",
        )

    overview = repository.get_place_feature_comparison_overview(now=now, local_timezone=UTC)
    outcome = next(o for o in overview.change_outcomes if o.event.id == event_id)
    assert outcome.environmental_comparison is not None
    assert outcome.environmental_comparison.status == "comparable"
    assert outcome.environmental_comparison.summary == "The after period was notably cooler."
    for forbidden in ("caused", "led to", "resulted in", "because of", "drove", "due to", "improved"):
        assert forbidden not in outcome.environmental_comparison.summary.lower()
    # Present exactly once for this event -- the per-Feature row's own
    # latest_change and the change_outcomes entry are the identical object.
    row = next(row for row in overview.features if row.feature.id == feature_id)
    assert row.latest_change.environmental_comparison == outcome.environmental_comparison


# --- Missing/expired representative evidence ---------------------------------


def test_overview_representative_evidence_none_when_media_file_missing(repository: ProductRepository) -> None:
    feature = repository.add_place_feature(
        PlaceFeatureCreate(feature_type="water", name="Bird Bath", zone_id=ZONE_ID), acting_user=_acting_user(),
    )
    at = datetime(2026, 6, 1, 10, tzinfo=UTC)
    _add_visit(repository, visit_id="expired-media-visit", at=at)
    _attach_primary_evidence(repository, visit_id="expired-media-visit", captured_at=at, missing_file=True)
    _confirm(repository, visit_id="expired-media-visit", label="northern_cardinal")

    overview = repository.get_place_feature_comparison_overview(now=at + timedelta(days=1), local_timezone=UTC)
    row = next(row for row in overview.features if row.feature.id == feature.id)
    assert row.representative_evidence is None, "a missing media file must abstain, never a broken thumbnail"


# --- Local Only ---------------------------------------------------------------


class _AlwaysFailsWeatherRequester:
    def __init__(self) -> None:
        self.call_count = 0

    def get(self, url: str, *, timeout_seconds: float) -> bytes:
        self.call_count += 1
        raise weather_provider.WeatherProviderUnavailableError("simulated: no internet route")


def test_overview_never_calls_the_network(tmp_path: Path) -> None:
    isolated_repository = ProductRepository(
        db_url=f"sqlite:///{tmp_path / 'mockingbird.sqlite3'}", media_root=tmp_path / "media",
        weather_requester=_AlwaysFailsWeatherRequester(),
    )
    configure_repository(isolated_repository)
    try:
        with isolated_repository.session_factory() as session:
            with session.begin():
                session.add(
                    CameraSourceModel(
                        id=SOURCE_ID, name="Comparison fixture camera", kind="manual_upload",
                        status="connected", description="fixture",
                    )
                )
                session.add(
                    StreamModel(
                        id=STREAM_ID, source_id=SOURCE_ID, name="Comparison fixture stream",
                        description="fixture", is_live=False,
                    )
                )
                session.add(
                    ZoneModel(
                        id=ZONE_ID, stream_id=STREAM_ID, name="Feeder", zone_type="feeder",
                        polygon_json="[]", is_active=True, monitoring_policy_json=None,
                    )
                )
        now = datetime(2026, 6, 27, tzinfo=UTC)
        feature_id, _event_id = _seed_feature_with_higher_activity_after(
            isolated_repository, name="Feeder", effective=date(2026, 6, 20), now=now,
        )
        _enable_weather(isolated_repository)
        pre_start = date(2026, 6, 13)
        _seed_flat_temperature_baseline(isolated_repository, before=pre_start, days=20, temperature_c=15.0)
        for offset in range(7):
            _insert_environmental_context_day(
                isolated_repository, metric="air_temperature", for_date=pre_start + timedelta(days=offset),
                value_numeric=15.0, unit="celsius",
            )
        for offset in range(7):
            _insert_environmental_context_day(
                isolated_repository, metric="air_temperature", for_date=date(2026, 6, 20) + timedelta(days=offset),
                value_numeric=0.0, unit="celsius",
            )

        overview = isolated_repository.get_place_feature_comparison_overview(now=now, local_timezone=UTC)
        assert len(overview.features) == 1
        assert isolated_repository._weather_requester.call_count == 0, (
            "the comparison overview attempted a live network fetch -- Local Only violated"
        )
    finally:
        configure_repository(None)


# --- HTTP surface --------------------------------------------------------------


def test_place_feature_comparison_overview_requires_authentication(repository: ProductRepository) -> None:
    plain_client = TestClient(app)
    assert plain_client.get("/api/place/feature-comparison").status_code == 401


def test_place_feature_comparison_overview_over_http(repository: ProductRepository) -> None:
    client = LegacyAuthenticatedSyncTestClient(app)
    created = client.post("/api/place/features", json={"feature_type": "feeder", "name": "Sunflower feeder"})
    feature_id = created.json()["id"]

    response = client.get("/api/place/feature-comparison")
    assert response.status_code == 200, response.text
    body = response.json()
    assert "generated_at" in body
    assert any(row["feature"]["id"] == feature_id for row in body["features"])
    assert body["change_outcomes"] == []


def test_place_feature_comparison_overview_empty_state_over_http(repository: ProductRepository) -> None:
    client = LegacyAuthenticatedSyncTestClient(app)
    response = client.get("/api/place/feature-comparison")
    assert response.status_code == 200
    assert response.json() == {"generated_at": response.json()["generated_at"], "features": [], "change_outcomes": []}


# --- Performance: batched, not N+1 -------------------------------------------


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


def test_comparison_overview_query_count_beats_independent_per_feature_detail_calls(
    repository: ProductRepository,
) -> None:
    """The exact regression the governing brief names: calling the
    equivalent of `get_place_feature_detail` independently once per Feature
    must cost more than the batched overview covering the same Features --
    proving the shared, up-front link/event batching actually pays off,
    not merely that it exists in the source."""

    now = datetime(2026, 6, 8, tzinfo=UTC)
    feature_ids = []
    for index in range(5):
        # Five Features share one Stream but each get their own Zone --
        # exposure coverage is Stream-scoped (seeded once, on the first
        # Feature only) while Visit scoping stays cleanly per-Feature.
        zone_id = ZONE_ID if index == 0 else f"{ZONE_ID}-{index}"
        if index > 0:
            with repository.session_factory() as session:
                with session.begin():
                    session.add(
                        ZoneModel(
                            id=zone_id, stream_id=STREAM_ID, name=f"Feeder zone {index}", zone_type="feeder",
                            polygon_json="[]", is_active=True, monitoring_policy_json=None,
                        )
                    )
        feature_id, _event_id = _seed_feature_with_higher_activity_after(
            repository, name=f"Feeder {index}", effective=date(2026, 6, 1), now=now,
            zone_id=zone_id, seed_coverage=(index == 0),
        )
        feature_ids.append(feature_id)

    def _read_overview() -> None:
        overview = repository.get_place_feature_comparison_overview(now=now, local_timezone=UTC)
        assert len(overview.features) == 5

    def _read_each_detail_independently() -> None:
        for feature_id in feature_ids:
            repository.get_place_feature_detail(feature_id, now=now, local_timezone=UTC)

    overview_query_count = _count_queries(repository.engine, _read_overview)
    independent_query_count = _count_queries(repository.engine, _read_each_detail_independently)
    print(
        f"\n[perf] 5 Features: overview={overview_query_count} queries, "
        f"5x independent get_place_feature_detail={independent_query_count} queries"
    )

    assert overview_query_count < independent_query_count, (
        f"batched overview ({overview_query_count} queries) was not cheaper than "
        f"{len(feature_ids)} independent get_place_feature_detail calls ({independent_query_count} queries)"
    )
