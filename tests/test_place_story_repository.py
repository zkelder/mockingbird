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
    PlaceFeatureChangeEventCreate,
    PlaceFeatureCreate,
    PlacePhenologyObservationCreate,
    PlacePhenologyObservationUpdate,
    ReviewCorrectionCreate,
    UserRole,
)
from mockingbird.repository.product_repository import ProductRepository
from mockingbird.storage.models import (
    CameraSourceModel,
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
