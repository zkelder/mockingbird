"""Repository/integration tests for ProductRepository.place_story -- real
seeded SQLite data, real HTTP surface. Mirrors tests/test_place_feature.py's
fixture/seeding pattern (see that file for the established precedent this
one follows).
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest

from mockingbird.api.main import app, configure_repository
from mockingbird.api.schemas import (
    CurrentUser,
    EnvironmentalContextSettingsUpdate,
    PlaceFeatureChangeEventCreate,
    PlaceFeatureCreate,
    PlacePhenologyObservationCreate,
    PlacePhenologyObservationUpdate,
    ReviewCorrectionCreate,
    UserRole,
)
from mockingbird.environment import weather_provider
from mockingbird.repository.product_repository import ProductRepository
from mockingbird.storage.models import (
    CameraSourceModel,
    EnvironmentalContextRecordModel,
    EventModel,
    MonitoringExposureIntervalModel,
    StreamModel,
    VisitModel,
    ZoneModel,
)
from tests.conftest import LegacyAuthenticatedSyncTestClient

SOURCE_ID = "story-fixture-source"
STREAM_ID = "story-fixture-stream"
ZONE_ID = "story-fixture-zone"


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
                    id=SOURCE_ID, name="Story fixture camera", kind="manual_upload",
                    status="connected", description="Place Story fixture.",
                )
            )
            session.add(
                StreamModel(
                    id=STREAM_ID, source_id=SOURCE_ID, name="Story fixture stream",
                    description="Place Story fixture.", is_live=False,
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


def _acting_user() -> CurrentUser:
    return CurrentUser(
        id="user-test-admin", display_name="Test Admin", login_identity="test-admin",
        role=UserRole.administrator, enabled=True,
    )


def _add_visit(repository: ProductRepository, *, visit_id: str, at: datetime) -> None:
    event_id = f"event-{visit_id}"
    with repository.session_factory() as session:
        with session.begin():
            session.add(
                EventModel(
                    id=event_id, stream_id=STREAM_ID, title=f"Story fixture {visit_id}",
                    event_type="manual_media_import", started_at=at, ended_at=at + timedelta(seconds=20),
                    primary_zone_id=ZONE_ID, review_status="needs_review",
                )
            )
            session.add(
                VisitModel(
                    id=visit_id, event_id=event_id, subject_label="unknown_bird", species_guess=None,
                    confidence=None, reviewed_label=None, review_status="needs_review",
                    representative_media_path=None, zone_id=ZONE_ID, is_superseded=False,
                )
            )


def _confirm(repository: ProductRepository, *, visit_id: str, label: str = "northern_cardinal") -> None:
    repository.create_review_label(
        ReviewCorrectionCreate(target_type="visit", target_id=visit_id, label=label, review_origin="human")
    )


def _cover_days(repository: ProductRepository, *, start: date, days: int) -> None:
    """One full 24-hour-healthy exposure interval per day -- clears every
    usable-day floor this codebase uses."""

    with repository.session_factory() as session:
        with session.begin():
            for offset in range(days):
                day = start + timedelta(days=offset)
                started_at = datetime(day.year, day.month, day.day, tzinfo=UTC)
                ended_at = started_at + timedelta(hours=23)
                session.add(
                    MonitoringExposureIntervalModel(
                        id=f"exposure-{day.isoformat()}", stream_id=STREAM_ID, source_id=SOURCE_ID,
                        runtime_generation_id=f"generation-{day.isoformat()}", started_at=started_at,
                        last_confirmed_fresh_at=ended_at, ended_at=ended_at, close_reason="provider_failure",
                        created_at=started_at, updated_at=ended_at,
                    )
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


def _insert_air_temperature_day(
    repository: ProductRepository,
    *,
    for_date: date,
    temperature_c: float,
    latitude: float = WEATHER_LATITUDE,
    longitude: float = WEATHER_LONGITUDE,
) -> None:
    """Directly inserts one full day (24 hourly rows) of `air_temperature` --
    bypasses the fetch path entirely, mirroring `test_environmental_context.
    py`'s own `_insert_air_temperature_day` helper."""

    now = datetime.now(UTC)
    with repository.session_factory() as session:
        with session.begin():
            for hour in range(24):
                session.add(
                    EnvironmentalContextRecordModel(
                        id=f"envctx-story-test-{for_date.isoformat()}-{hour:02d}",
                        source_id=None,
                        provider_key=weather_provider.WEATHER_PROVIDER_KEY,
                        information_class=weather_provider.WEATHER_INFORMATION_CLASS,
                        metric="air_temperature",
                        value_numeric=temperature_c,
                        value_text=None,
                        unit="celsius",
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
    for offset in range(1, days + 1):
        _insert_air_temperature_day(repository, for_date=before - timedelta(days=offset), temperature_c=temperature_c)


def _feeder_with_higher_activity_after_change(
    repository: ProductRepository, *, effective: date,
) -> tuple[str, str]:
    """A Feature change event whose wildlife-side `comparison_insight` is
    guaranteed to fire at the smallest (7-day) window: full exposure
    coverage on both sides, confirmed presence every post-change day, none
    before -- an unambiguous `more_common_under_condition`. Returns
    `(feature_id, change_event_id)`."""

    feature = repository.add_place_feature(
        PlaceFeatureCreate(feature_type="feeder", name="Sunflower Feeder", zone_id=ZONE_ID),
        acting_user=_acting_user(),
    )
    change = repository.add_place_feature_change_event(
        PlaceFeatureChangeEventCreate(feature_id=feature.id, event_type="added", effective_date=effective),
        acting_user=_acting_user(),
    )
    _cover_days(repository, start=effective - timedelta(days=7), days=14)
    for offset in range(7):
        day = effective + timedelta(days=offset)
        visit_id = f"visit-story-comparison-{effective.isoformat()}-{offset}"
        _add_visit(repository, visit_id=visit_id, at=datetime(day.year, day.month, day.day, 10, tzinfo=UTC))
        _confirm(repository, visit_id=visit_id)
    return feature.id, change.id


def test_first_visit_ever_produces_a_first_seen_entry(repository: ProductRepository) -> None:
    start = date(2025, 3, 1)
    _cover_days(repository, start=start, days=10)
    _add_visit(repository, visit_id="v1", at=datetime(2025, 3, 3, 10, tzinfo=UTC))
    _confirm(repository, visit_id="v1")

    response = repository.place_story(
        start_at=datetime(2025, 3, 1, tzinfo=UTC), end_at=datetime(2025, 3, 10, tzinfo=UTC),
    )
    first_seen = [e for e in response.entries if e.kind == "first_seen"]
    assert len(first_seen) == 1
    assert first_seen[0].taxon_label == "northern_cardinal"
    assert first_seen[0].event_date == date(2025, 3, 3)
    assert first_seen[0].information_class == "reviewed"


def test_feature_added_produces_a_reviewed_feature_change_entry(repository: ProductRepository) -> None:
    feature = repository.add_place_feature(
        PlaceFeatureCreate(feature_type="feeder", name="Sunflower Feeder", zone_id=ZONE_ID),
        acting_user=_acting_user(),
    )
    repository.add_place_feature_change_event(
        PlaceFeatureChangeEventCreate(
            feature_id=feature.id, event_type="added", effective_date=date(2025, 4, 2),
        ),
        acting_user=_acting_user(),
    )

    response = repository.place_story(
        start_at=datetime(2025, 4, 1, tzinfo=UTC), end_at=datetime(2025, 4, 30, tzinfo=UTC),
    )
    feature_changes = [e for e in response.entries if e.kind == "feature_change"]
    assert len(feature_changes) == 1
    assert feature_changes[0].feature_name == "Sunflower Feeder"
    assert feature_changes[0].event_date == date(2025, 4, 2)
    assert feature_changes[0].importance == "major"


def test_phenology_observation_produces_a_reviewed_entry(repository: ProductRepository) -> None:
    repository.add_place_phenology_observation(
        PlacePhenologyObservationCreate(
            subject_label="Azaleas", phenomenon="Flowering",
            observed_start_date=date(2025, 4, 1), observed_end_date=date(2025, 4, 20),
        ),
        acting_user=_acting_user(),
    )

    response = repository.place_story(
        start_at=datetime(2025, 3, 25, tzinfo=UTC), end_at=datetime(2025, 4, 30, tzinfo=UTC),
    )
    phenology = [e for e in response.entries if e.kind == "phenology"]
    assert len(phenology) == 1
    assert phenology[0].event_date == date(2025, 4, 1)
    assert phenology[0].event_end_date == date(2025, 4, 20)


def test_removed_feature_change_event_disappears_from_the_story(repository: ProductRepository) -> None:
    feature = repository.add_place_feature(
        PlaceFeatureCreate(feature_type="feeder", name="Sunflower Feeder"), acting_user=_acting_user(),
    )
    change = repository.add_place_feature_change_event(
        PlaceFeatureChangeEventCreate(feature_id=feature.id, event_type="added", effective_date=date(2025, 4, 2)),
        acting_user=_acting_user(),
    )

    before = repository.place_story(start_at=datetime(2025, 4, 1, tzinfo=UTC), end_at=datetime(2025, 4, 30, tzinfo=UTC))
    assert any(e.kind == "feature_change" for e in before.entries)

    repository.remove_place_feature_change_event(change.id, acting_user=_acting_user())

    after = repository.place_story(start_at=datetime(2025, 4, 1, tzinfo=UTC), end_at=datetime(2025, 4, 30, tzinfo=UTC))
    assert not any(e.kind == "feature_change" for e in after.entries), "removed change event still appeared"


# --- Environmental Context x Place Story & Habitat Change Composition v1:
# comparison_insight's weather_caveat composition -----------------------


def test_comparison_insight_gains_environmental_caveat_when_meaningfully_different(
    repository: ProductRepository,
) -> None:
    effective = date(2025, 6, 20)
    _feeder_with_higher_activity_after_change(repository, effective=effective)
    _enable_weather(repository)
    pre_start = effective - timedelta(days=7)
    _seed_flat_temperature_baseline(repository, before=pre_start, days=20, temperature_c=15.0)
    for offset in range(7):
        _insert_air_temperature_day(repository, for_date=pre_start + timedelta(days=offset), temperature_c=15.0)
    for offset in range(7):
        _insert_air_temperature_day(repository, for_date=effective + timedelta(days=offset), temperature_c=0.0)

    response = repository.place_story(
        start_at=datetime(2025, 6, 1, tzinfo=UTC), end_at=datetime(2025, 7, 10, tzinfo=UTC),
        now=datetime(effective.year, effective.month, effective.day, tzinfo=UTC) + timedelta(days=7),
        local_timezone=UTC,
    )
    insights = [e for e in response.entries if e.kind == "comparison_insight"]
    assert len(insights) == 1
    assert "Confirmed wildlife activity was higher" in insights[0].summary
    assert "The after period was notably cooler." in insights[0].summary
    assert insights[0].information_class == "inferred"
    for forbidden in ("caused", "led to", "resulted in", "because of", "drove", "due to"):
        assert forbidden not in insights[0].summary.lower()


def test_comparison_insight_has_no_weather_caveat_without_configured_weather(
    repository: ProductRepository,
) -> None:
    """Missing/unconfigured environmental context leaves the Story entry
    valid -- the wildlife `comparison_insight` still appears, with exactly
    its own base sentence and no trailing caveat, never a broken card."""

    effective = date(2025, 6, 20)
    _feeder_with_higher_activity_after_change(repository, effective=effective)

    response = repository.place_story(
        start_at=datetime(2025, 6, 1, tzinfo=UTC), end_at=datetime(2025, 7, 10, tzinfo=UTC),
        now=datetime(effective.year, effective.month, effective.day, tzinfo=UTC) + timedelta(days=7),
        local_timezone=UTC,
    )
    insights = [e for e in response.entries if e.kind == "comparison_insight"]
    assert len(insights) == 1
    assert insights[0].summary == (
        "Confirmed wildlife activity was higher during the monitored period after "
        "Sunflower Feeder was added, compared with the monitored period before."
    )


def test_comparison_insight_has_no_weather_caveat_when_conditions_are_similar(
    repository: ProductRepository,
) -> None:
    """An ordinary Story entry must not become a weather log: a genuinely
    evaluated-but-unremarkable environmental comparison stays silent here
    (unlike Place Feature's own dedicated comparison surface, which *does*
    state "broadly similar" -- see `summarize_environmental_period_
    comparison`'s `include_neutral` split)."""

    effective = date(2025, 6, 20)
    _feeder_with_higher_activity_after_change(repository, effective=effective)
    _enable_weather(repository)
    pre_start = effective - timedelta(days=7)
    _seed_flat_temperature_baseline(repository, before=pre_start, days=20, temperature_c=15.0)
    for offset in range(7):
        _insert_air_temperature_day(repository, for_date=pre_start + timedelta(days=offset), temperature_c=15.0)
    for offset in range(7):
        _insert_air_temperature_day(repository, for_date=effective + timedelta(days=offset), temperature_c=15.0)

    response = repository.place_story(
        start_at=datetime(2025, 6, 1, tzinfo=UTC), end_at=datetime(2025, 7, 10, tzinfo=UTC),
        now=datetime(effective.year, effective.month, effective.day, tzinfo=UTC) + timedelta(days=7),
        local_timezone=UTC,
    )
    insights = [e for e in response.entries if e.kind == "comparison_insight"]
    assert len(insights) == 1
    assert insights[0].summary == (
        "Confirmed wildlife activity was higher during the monitored period after "
        "Sunflower Feeder was added, compared with the monitored period before."
    )
    assert "similar" not in insights[0].summary.lower()


def test_corrected_phenology_date_moves_the_story_entry(repository: ProductRepository) -> None:
    observation = repository.add_place_phenology_observation(
        PlacePhenologyObservationCreate(
            subject_label="Azaleas", phenomenon="Flowering", observed_start_date=date(2025, 4, 1),
        ),
        acting_user=_acting_user(),
    )

    april = repository.place_story(start_at=datetime(2025, 4, 1, tzinfo=UTC), end_at=datetime(2025, 4, 30, tzinfo=UTC))
    assert any(e.kind == "phenology" and e.event_date == date(2025, 4, 1) for e in april.entries)

    repository.update_place_phenology_observation(
        observation.id,
        PlacePhenologyObservationUpdate(observed_start_date=date(2025, 5, 15)),
        acting_user=_acting_user(),
    )

    april_after = repository.place_story(start_at=datetime(2025, 4, 1, tzinfo=UTC), end_at=datetime(2025, 4, 30, tzinfo=UTC))
    assert not any(e.kind == "phenology" for e in april_after.entries), "stale April phenology entry remained"

    may = repository.place_story(start_at=datetime(2025, 5, 1, tzinfo=UTC), end_at=datetime(2025, 5, 31, tzinfo=UTC))
    assert any(e.kind == "phenology" and e.event_date == date(2025, 5, 15) for e in may.entries)


def test_correction_is_reflected_on_the_very_next_call(repository: ProductRepository) -> None:
    """Phase 15: no stale narrative truth -- a species correction changes
    the very next Place Story read, with no cache/invalidation step."""

    start = date(2025, 3, 1)
    _cover_days(repository, start=start, days=10)
    _add_visit(repository, visit_id="v1", at=datetime(2025, 3, 3, 10, tzinfo=UTC))
    _confirm(repository, visit_id="v1", label="northern_cardinal")

    before = repository.place_story(start_at=datetime(2025, 3, 1, tzinfo=UTC), end_at=datetime(2025, 3, 10, tzinfo=UTC))
    assert any(e.taxon_label == "northern_cardinal" for e in before.entries if e.kind == "first_seen")

    _confirm(repository, visit_id="v1", label="blue_jay")  # reviewer corrects the species

    after = repository.place_story(start_at=datetime(2025, 3, 1, tzinfo=UTC), end_at=datetime(2025, 3, 10, tzinfo=UTC))
    after_first_seen_labels = {e.taxon_label for e in after.entries if e.kind == "first_seen"}
    assert after_first_seen_labels == {"blue_jay"}, f"correction did not propagate: {after_first_seen_labels}"


def test_fresh_place_with_only_demo_seed_data_is_early_experience(repository: ProductRepository) -> None:
    """`ProductRepository.__init__` unconditionally seeds bounded demo data
    into any empty database (`seed_if_empty`) -- a fresh repository is
    never literally content-free, so this asserts the actual early-
    experience contract (baseline maturity is "insufficient" with no real
    monitoring-exposure history) rather than a bare `entries == []` that
    would not reflect real repository construction."""

    response = repository.place_story()
    assert response.is_early_experience is True


def test_pagination_and_kind_filter_via_real_http(repository: ProductRepository) -> None:
    start = date(2025, 3, 1)
    _cover_days(repository, start=start, days=10)
    for i, label in enumerate(["northern_cardinal", "blue_jay", "house_finch"]):
        visit_id = f"v{i}"
        _add_visit(repository, visit_id=visit_id, at=datetime(2025, 3, 1 + i, 10, tzinfo=UTC))
        _confirm(repository, visit_id=visit_id, label=label)
    repository.add_place_feature(
        PlaceFeatureCreate(feature_type="feeder", name="Sunflower Feeder"), acting_user=_acting_user(),
    )

    auth_client = LegacyAuthenticatedSyncTestClient(app)
    response = auth_client.get(
        "/api/place/story",
        params={"start_at": "2025-03-01T00:00:00Z", "end_at": "2025-03-10T00:00:00Z", "kind": "first_seen"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total_matched"] == 3
    assert all(entry["kind"] == "first_seen" for entry in body["entries"])

    page1 = auth_client.get(
        "/api/place/story",
        params={
            "start_at": "2025-03-01T00:00:00Z", "end_at": "2025-03-10T00:00:00Z",
            "kind": "first_seen", "page_size": 2, "offset": 0,
        },
    ).json()
    page2 = auth_client.get(
        "/api/place/story",
        params={
            "start_at": "2025-03-01T00:00:00Z", "end_at": "2025-03-10T00:00:00Z",
            "kind": "first_seen", "page_size": 2, "offset": 2,
        },
    ).json()
    all_ids = [e["id"] for e in page1["entries"]] + [e["id"] for e in page2["entries"]]
    assert len(all_ids) == len(set(all_ids)) == 3
    assert page1["has_more"] is True
    assert page2["has_more"] is False


def test_archiving_the_camera_afterward_does_not_erase_its_story_entry(
    repository: ProductRepository,
) -> None:
    """Multi-Camera Place Experience v2: Place Story is explicitly "A
    Living History of the Place" -- unlike Bird Log's own deliberate
    current-active-observatory default (see test_wildlife_journal.py),
    hiding a real past event just because its recording camera was later
    retired would falsify the timeline's own "living history" promise.
    Archive-only removal never deletes the underlying Visit (see
    camera-source-experience-v1-report.md); this proves the Story entry it
    produced survives that archival too."""

    start = date(2025, 3, 1)
    _cover_days(repository, start=start, days=10)
    _add_visit(repository, visit_id="v-before-archive", at=datetime(2025, 3, 3, 10, tzinfo=UTC))
    _confirm(repository, visit_id="v-before-archive")

    before_archive = repository.place_story(
        start_at=datetime(2025, 3, 1, tzinfo=UTC), end_at=datetime(2025, 3, 10, tzinfo=UTC),
    )
    assert [e.kind for e in before_archive.entries if e.kind == "first_seen"] == ["first_seen"]

    with repository.session_factory() as session:
        with session.begin():
            source = session.get(CameraSourceModel, SOURCE_ID)
            assert source is not None
            source.status = "archived"

    after_archive = repository.place_story(
        start_at=datetime(2025, 3, 1, tzinfo=UTC), end_at=datetime(2025, 3, 10, tzinfo=UTC),
    )
    first_seen_after = [e for e in after_archive.entries if e.kind == "first_seen"]
    assert len(first_seen_after) == 1
    assert first_seen_after[0].taxon_label == "northern_cardinal"
    assert first_seen_after[0].event_date == date(2025, 3, 3)


# --- Year-over-Year Seasonality & Long-Term Place Memory v1 ---


def test_year_over_year_insight_appears_when_the_requested_range_includes_now(
    repository: ProductRepository,
) -> None:
    """A Story request whose own range spans "now" gets a `year_over_year`
    entry when a real, material difference exists; see `ProductRepository.
    place_story`'s own gating comment for why a deep historical-archive
    browse never attempts this at all."""

    _cover_days(repository, start=date(2026, 9, 1), days=30)
    _cover_days(repository, start=date(2025, 9, 1), days=30)
    for i, day in enumerate(range(1, 17)):
        visit_id = f"cur-{i}"
        _add_visit(repository, visit_id=visit_id, at=datetime(2026, 9, day, 10, tzinfo=UTC))
        _confirm(repository, visit_id=visit_id, label="northern_cardinal")
    for i, day in enumerate(range(1, 5)):
        visit_id = f"pri-{i}"
        _add_visit(repository, visit_id=visit_id, at=datetime(2025, 9, day, 10, tzinfo=UTC))
        _confirm(repository, visit_id=visit_id, label="northern_cardinal")

    # `now` lands on the current period's own last day (comfortably inside
    # `[start_at, end_at)`, so the range-includes-now gate fires) and
    # `local_timezone=UTC` is passed explicitly so "today" resolves
    # deterministically against the UTC dates this test seeds -- no
    # dependency on the host's own real timezone.
    response = repository.place_story(
        start_at=datetime(2026, 9, 1, tzinfo=UTC),
        end_at=datetime(2026, 10, 1, tzinfo=UTC),
        now=datetime(2026, 9, 30, 12, tzinfo=UTC),
        local_timezone=UTC,
    )
    yoy_entries = [e for e in response.entries if e.kind == "year_over_year"]
    assert len(yoy_entries) >= 1
    assert any(e.taxon_label == "northern_cardinal" for e in yoy_entries) or any(
        e.taxon_label is None for e in yoy_entries
    )
    for entry in yoy_entries:
        assert entry.information_class == "inferred"
        assert entry.group == "context"


def test_year_over_year_insight_is_skipped_for_a_historical_archive_range(
    repository: ProductRepository,
) -> None:
    """A request whose own range does not include "now" never attempts a
    year-over-year computation at all -- zero cost, and structurally
    correct (there is no "current period" to anchor to)."""

    _cover_days(repository, start=date(2026, 9, 1), days=30)
    _cover_days(repository, start=date(2025, 9, 1), days=30)
    for i, day in enumerate(range(1, 17)):
        visit_id = f"cur-{i}"
        _add_visit(repository, visit_id=visit_id, at=datetime(2026, 9, day, 10, tzinfo=UTC))
        _confirm(repository, visit_id=visit_id, label="northern_cardinal")

    response = repository.place_story(
        start_at=datetime(2025, 3, 1, tzinfo=UTC),
        end_at=datetime(2025, 3, 10, tzinfo=UTC),
        now=datetime(2026, 10, 2, tzinfo=UTC),
    )
    assert [e for e in response.entries if e.kind == "year_over_year"] == []
