"""Multi-Camera Attribution & Filter Consolidation v1 -- backend contract tests.

Covers the two backend halves of the milestone against real seeded SQLite
rows (see docs/multi-camera-attribution-filter-consolidation-contract.md):

* Place Story keeps camera/Visit attribution for entries anchored to a
  concrete encounter, never fabricates one for Place-level entries, and
  represents a confidently-associated multi-camera encounter honestly.
* Calm Attention presents an `associated` cross-camera pair as one attention
  item without merging Visits, resolving anything, or collapsing per-user
  acknowledgement.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest

from mockingbird.api.schemas import (
    ActivityLibrarySearchRequest,
    AlertCategory,
    CurrentUser,
    PlaceFeatureChangeEventCreate,
    PlaceFeatureCreate,
    ReviewCorrectionCreate,
    UserRole,
)
from mockingbird.repository.product_repository import (
    CrossCameraVisitAssociationModel,
    ProductAlertModel,
    ProductRepository,
)
from mockingbird.storage.models import (
    CameraSourceModel,
    EventModel,
    MonitoringExposureIntervalModel,
    StreamModel,
    UserModel,
    VisitModel,
)

SOURCE_A, STREAM_A = "src-feeder-cam", "stream-feeder-cam"
SOURCE_B, STREAM_B = "src-fence-cam", "stream-fence-cam"
DAY = datetime(2025, 3, 3, tzinfo=UTC)


@pytest.fixture
def repository(tmp_path: Path) -> ProductRepository:
    repo = ProductRepository(db_url=f"sqlite:///{tmp_path / 'mockingbird.sqlite3'}", media_root=tmp_path / "media")
    with repo.session_factory() as session:
        with session.begin():
            for source_id, stream_id, name in (
                (SOURCE_A, STREAM_A, "Feeder cam"),
                (SOURCE_B, STREAM_B, "Fence cam"),
            ):
                session.add(
                    CameraSourceModel(
                        id=source_id, name=name, kind="manual_upload", status="connected", description="fixture",
                    )
                )
                session.add(
                    StreamModel(id=stream_id, source_id=source_id, name=f"{name} stream", description="x", is_live=False)
                )
    _cover(repo, STREAM_A, SOURCE_A)
    _cover(repo, STREAM_B, SOURCE_B)
    yield repo
    repo.close()


def _cover(repository: ProductRepository, stream_id: str, source_id: str) -> None:
    with repository.session_factory() as session:
        with session.begin():
            for offset in range(-2, 8):
                day = (DAY + timedelta(days=offset)).date()
                started = datetime(day.year, day.month, day.day, tzinfo=UTC)
                ended = started + timedelta(hours=23)
                session.add(
                    MonitoringExposureIntervalModel(
                        id=f"exposure-{stream_id}-{day.isoformat()}", stream_id=stream_id, source_id=source_id,
                        runtime_generation_id=f"generation-{stream_id}-{day.isoformat()}", started_at=started,
                        last_confirmed_fresh_at=ended, ended_at=ended, close_reason="provider_failure",
                        created_at=started, updated_at=ended,
                    )
                )


def _visit(
    repository: ProductRepository, *, visit_id: str, stream_id: str, at: datetime, label: str | None = None,
) -> None:
    event_id = f"event-{visit_id}"
    with repository.session_factory() as session:
        with session.begin():
            session.add(
                EventModel(
                    id=event_id, stream_id=stream_id, title=visit_id, event_type="manual_media_import",
                    started_at=at, ended_at=at + timedelta(seconds=20), primary_zone_id=None,
                    review_status="needs_review",
                )
            )
            session.add(
                VisitModel(
                    id=visit_id, event_id=event_id, subject_label="unknown_bird", species_guess=None,
                    confidence=None, reviewed_label=None, review_status="needs_review",
                    representative_media_path=None, zone_id=None, is_superseded=False,
                )
            )
    if label is not None:
        repository.create_review_label(
            ReviewCorrectionCreate(target_type="visit", target_id=visit_id, label=label, review_origin="human")
        )


def _associate(repository: ProductRepository, first: str, second: str, *, tier: str = "associated") -> None:
    primary, secondary = sorted((first, second))
    now = datetime.now(UTC)
    with repository.session_factory() as session:
        with session.begin():
            session.add(
                CrossCameraVisitAssociationModel(
                    id=f"assoc-{primary}-{secondary}", primary_visit_id=primary, secondary_visit_id=secondary,
                    tier=tier, overlap_ms=0, gap_ms=4000, spatial_signal="matching_area_name",
                    multi_subject=False, engine_version="test", created_at=now, updated_at=now,
                )
            )


def _story(repository: ProductRepository):
    return repository.place_story(
        start_at=datetime(2025, 3, 1, tzinfo=UTC), end_at=datetime(2025, 3, 8, tzinfo=UTC),
        now=datetime(2025, 3, 8, tzinfo=UTC), local_timezone=UTC,
    )


def _first_seen(response, taxon: str):
    matches = [e for e in response.entries if e.kind == "first_seen" and e.taxon_label == taxon]
    assert len(matches) == 1, taxon
    return matches[0]


def _two_camera_day(repository: ProductRepository) -> None:
    """One cardinal encounter seen by both cameras (associated), one unrelated
    sparrow on the fence camera a few seconds later, one unrelated jay later."""

    _visit(repository, visit_id="v-a-cardinal", stream_id=STREAM_A, at=DAY.replace(hour=10), label="northern_cardinal")
    _visit(
        repository, visit_id="v-b-cardinal", stream_id=STREAM_B,
        at=DAY.replace(hour=10, second=4), label="northern_cardinal",
    )
    _associate(repository, "v-a-cardinal", "v-b-cardinal")
    _visit(
        repository, visit_id="v-b-finch", stream_id=STREAM_B,
        at=DAY.replace(hour=10, second=6), label="house_finch",
    )
    _visit(repository, visit_id="v-a-jay", stream_id=STREAM_A, at=DAY.replace(hour=15), label="blue_jay")


def test_associated_encounter_is_one_multi_source_story_entry(repository: ProductRepository) -> None:
    _two_camera_day(repository)

    entry = _first_seen(_story(repository), "northern_cardinal")

    assert entry.source_scope == "multiple_sources"
    assert {c.source_id for c in entry.contributions} == {SOURCE_A, SOURCE_B}
    # Each contributing camera keeps its own Visit for drill-down; no camera is
    # arbitrarily chosen as "the" source (the legacy scalar stays empty).
    assert {c.visit_id for c in entry.contributions} == {"v-a-cardinal", "v-b-cardinal"}
    assert entry.source_id is None
    assert entry.visit_id == "v-a-cardinal"  # earliest contributing encounter


def test_unrelated_simultaneous_wildlife_is_attributed_to_its_own_camera_only(
    repository: ProductRepository,
) -> None:
    _two_camera_day(repository)
    response = _story(repository)

    sparrow = _first_seen(response, "house_finch")
    jay = _first_seen(response, "blue_jay")

    assert sparrow.source_scope == "single_source"
    assert [c.source_id for c in sparrow.contributions] == [SOURCE_B]
    assert jay.source_scope == "single_source"
    assert [c.source_id for c in jay.contributions] == [SOURCE_A]
    # Species and time similarity alone never merged anything.
    assert [c.visit_id for c in sparrow.contributions] == ["v-b-finch"]


def test_possible_tier_pair_is_not_merged_into_one_encounter(repository: ProductRepository) -> None:
    _visit(repository, visit_id="v-a-1", stream_id=STREAM_A, at=DAY.replace(hour=10), label="northern_cardinal")
    _visit(repository, visit_id="v-b-1", stream_id=STREAM_B, at=DAY.replace(hour=10, second=4), label="northern_cardinal")
    _associate(repository, "v-a-1", "v-b-1", tier="possible")

    entry = _first_seen(_story(repository), "northern_cardinal")

    assert entry.source_scope == "single_source"
    assert [c.source_id for c in entry.contributions] == [SOURCE_A]


def test_partner_reviewed_as_a_different_taxon_is_never_folded_in(repository: ProductRepository) -> None:
    _visit(repository, visit_id="v-a-1", stream_id=STREAM_A, at=DAY.replace(hour=10), label="northern_cardinal")
    _visit(repository, visit_id="v-b-1", stream_id=STREAM_B, at=DAY.replace(hour=10, second=4), label="blue_jay")
    _associate(repository, "v-a-1", "v-b-1")

    response = _story(repository)

    assert [c.source_id for c in _first_seen(response, "northern_cardinal").contributions] == [SOURCE_A]
    assert [c.source_id for c in _first_seen(response, "blue_jay").contributions] == [SOURCE_B]


def test_place_level_entries_never_gain_a_fabricated_camera(repository: ProductRepository) -> None:
    _two_camera_day(repository)
    feature = repository.add_place_feature(
        PlaceFeatureCreate(feature_type="feeder", name="Sunflower Feeder", zone_id=None),
        acting_user=_admin(),
    )
    repository.add_place_feature_change_event(
        PlaceFeatureChangeEventCreate(
            feature_id=feature.id, event_type="added", effective_date=date(2025, 3, 4),
        ),
        acting_user=_admin(),
    )

    response = _story(repository)
    attributable = {"first_seen", "diversity_milestone", "return"}
    unattributed = [e for e in response.entries if e.kind not in attributable]

    assert unattributed  # the Feature change at least
    assert all(e.source_scope == "place_level" and e.contributions == [] for e in unattributed)


def test_archived_camera_is_flagged_but_stays_attributed(repository: ProductRepository) -> None:
    _two_camera_day(repository)
    with repository.session_factory() as session:
        with session.begin():
            session.get(CameraSourceModel, SOURCE_B).status = "archived"

    sparrow = _first_seen(_story(repository), "house_finch")

    assert sparrow.contributions[0].source_archived is True
    assert sparrow.contributions[0].source_id == SOURCE_B


def _admin() -> CurrentUser:
    return CurrentUser(
        id="user-test-admin", display_name="Test Admin", login_identity="test-admin",
        role=UserRole.administrator, enabled=True,
    )


# ---------------------------------------------------------------------------
# Calm Attention: cross-camera grouping
# ---------------------------------------------------------------------------


def _user(repository: ProductRepository, user_id: str) -> CurrentUser:
    with repository.session_factory() as session:
        with session.begin():
            if session.get(UserModel, user_id) is None:
                session.add(
                    UserModel(
                        id=user_id, login_identity=user_id, display_name=user_id,
                        role=UserRole.administrator.value, enabled=True,
                        password_hash="x", created_at=datetime.now(UTC), updated_at=datetime.now(UTC),
                        password_updated_at=datetime.now(UTC),
                    )
                )
    return CurrentUser(
        id=user_id, display_name=user_id, login_identity=user_id, role=UserRole.administrator, enabled=True,
    )


def _review_alert_visit_ids(repository: ProductRepository, viewer: CurrentUser) -> list[str]:
    page = repository.list_product_alerts(category=AlertCategory.review, viewer=viewer)
    return sorted(item.visit_id for item in page.items if item.visit_id and item.status == "unread")


def _needs_review_pair(repository: ProductRepository) -> None:
    """Two un-reviewed Visits on two cameras (an associated pair) plus one
    unrelated simultaneous Visit, each with its own review alert."""

    _visit(repository, visit_id="v-a-1", stream_id=STREAM_A, at=DAY.replace(hour=10))
    _visit(repository, visit_id="v-b-1", stream_id=STREAM_B, at=DAY.replace(hour=10, second=4))
    _visit(repository, visit_id="v-b-2", stream_id=STREAM_B, at=DAY.replace(hour=10, second=6))
    for visit_id in ("v-a-1", "v-b-1", "v-b-2"):
        with repository.session_factory() as session:
            with session.begin():
                repository._sync_review_alert(session, session.get(VisitModel, visit_id), datetime.now(UTC))


def test_associated_pair_is_one_attention_item_with_both_cameras_reachable(repository: ProductRepository) -> None:
    viewer = _user(repository, "user-one")
    _needs_review_pair(repository)
    before = _review_alert_visit_ids(repository, viewer)
    assert before == ["v-a-1", "v-b-1", "v-b-2"]

    _associate(repository, "v-a-1", "v-b-1")

    assert _review_alert_visit_ids(repository, viewer) == ["v-a-1", "v-b-2"]
    group = next(
        item for item in repository.list_product_alerts(category=AlertCategory.review, viewer=viewer).items
        if item.visit_id == "v-a-1"
    )
    assert [(m.visit_id, m.source_id) for m in group.grouped_visits] == [("v-b-1", SOURCE_B)]
    assert repository.product_alert_unread(viewer=viewer).unread_count == 2
    # Visits themselves are untouched: the hidden camera's alert and Visit
    # both still exist and remain independently reviewable.
    with repository.session_factory() as session:
        assert session.query(ProductAlertModel).filter(ProductAlertModel.visit_id == "v-b-1").count() == 1
        assert session.get(VisitModel, "v-b-1").review_status == "needs_review"


def test_possible_pair_and_unrelated_simultaneous_visit_are_not_grouped(repository: ProductRepository) -> None:
    viewer = _user(repository, "user-one")
    _needs_review_pair(repository)
    _associate(repository, "v-a-1", "v-b-1", tier="possible")

    assert _review_alert_visit_ids(repository, viewer) == ["v-a-1", "v-b-1", "v-b-2"]
    assert repository.product_alert_unread(viewer=viewer).unread_count == 3


def test_acknowledgement_stays_per_user_and_covers_the_whole_encounter(repository: ProductRepository) -> None:
    first, second = _user(repository, "user-one"), _user(repository, "user-two")
    _needs_review_pair(repository)
    _associate(repository, "v-a-1", "v-b-1")
    representative = next(
        item for item in repository.list_product_alerts(category=AlertCategory.review, viewer=first).items
        if item.visit_id == "v-a-1"
    )

    assert repository.dismiss_product_alert(representative.id, user_id=first.id)

    assert repository.product_alert_unread(viewer=first).unread_count == 1  # only the unrelated v-b-2
    assert repository.product_alert_unread(viewer=second).unread_count == 2  # user two untouched
    # When the representative's Visit is reviewed, the partner camera's still-
    # unreviewed Visit does not resurface as fresh noise for the user who
    # already dismissed this encounter -- but another user still sees it.
    repository.create_review_label(
        ReviewCorrectionCreate(target_type="visit", target_id="v-a-1", label="northern_cardinal", review_origin="human")
    )
    assert _review_alert_visit_ids(repository, first) == ["v-b-2"]
    assert _review_alert_visit_ids(repository, second) == ["v-b-1", "v-b-2"]


def test_resolving_the_representative_surfaces_the_partner_for_a_user_who_never_acknowledged(
    repository: ProductRepository,
) -> None:
    viewer = _user(repository, "user-one")
    _needs_review_pair(repository)
    _associate(repository, "v-a-1", "v-b-1")

    repository.create_review_label(
        ReviewCorrectionCreate(target_type="visit", target_id="v-a-1", label="northern_cardinal", review_origin="human")
    )

    # Resolution is global and honest: the other camera's Visit still needs
    # its own review, so its alert is no longer hidden behind a resolved one.
    assert _review_alert_visit_ids(repository, viewer) == ["v-b-1", "v-b-2"]


# ---------------------------------------------------------------------------
# One deterministic multi-camera product scenario
# ---------------------------------------------------------------------------


def test_two_camera_place_scenario_story_filter_attention_and_drill_down_cohere(
    repository: ProductRepository,
) -> None:
    """Two cameras at one Place. One cardinal encounter is seen by both (an
    `associated` pair); an unrelated finch is seen only by the fence camera a
    couple of seconds later. Every surface tells the same story: Story
    attributes honestly, the camera filter scopes by stable Source id,
    Attention shows one item for the shared encounter and a separate one for
    the unrelated sighting, and each camera's own Visit stays reachable."""

    viewer = _user(repository, "user-one")
    # Needs-review versions of the same two-camera moment: shared encounter on
    # both cameras plus an unrelated sighting on the fence camera.
    _visit(repository, visit_id="n-a-shared", stream_id=STREAM_A, at=DAY.replace(hour=11))
    _visit(repository, visit_id="n-b-shared", stream_id=STREAM_B, at=DAY.replace(hour=11, second=3))
    _visit(repository, visit_id="n-b-unrelated", stream_id=STREAM_B, at=DAY.replace(hour=11, second=5))
    for visit_id in ("n-a-shared", "n-b-shared", "n-b-unrelated"):
        with repository.session_factory() as session:
            with session.begin():
                repository._sync_review_alert(session, session.get(VisitModel, visit_id), datetime.now(UTC))
    # Reviewed history for Story (also raises its own Bird Log discovery alerts).
    _two_camera_day(repository)
    unread_before_grouping = repository.product_alert_unread(viewer=viewer).unread_count
    _associate(repository, "n-a-shared", "n-b-shared")

    # 1. Story: shared encounter -> both cameras, none arbitrarily chosen;
    #    unrelated finch -> only its own camera; trend entries stay Place-level.
    story = _story(repository)
    shared = _first_seen(story, "northern_cardinal")
    unrelated = _first_seen(story, "house_finch")
    assert shared.source_scope == "multiple_sources"
    assert unrelated.source_scope == "single_source"
    assert {c.source_id for c in unrelated.contributions} == {SOURCE_B}

    # 2. Camera filtering by stable Source id scopes the same Visits.
    only_fence = repository.search_activity_library(ActivityLibrarySearchRequest(source_id=SOURCE_B))
    only_feeder = repository.search_activity_library(ActivityLibrarySearchRequest(source_id=SOURCE_A))
    fence_ids = {v.id for v in only_fence.visits}
    feeder_ids = {v.id for v in only_feeder.visits}
    assert {"v-b-cardinal", "v-b-finch", "n-b-shared", "n-b-unrelated"} <= fence_ids
    assert fence_ids.isdisjoint(feeder_ids)
    assert "v-a-cardinal" in feeder_ids

    # 3. Calm Attention: one item for the shared encounter, one for the
    #    unrelated sighting -- never two for the same bird, never one merged
    #    with the unrelated bird.
    assert _review_alert_visit_ids(repository, viewer) == ["n-a-shared", "n-b-unrelated"]
    # The badge drops by exactly the one duplicated camera, nothing else.
    assert repository.product_alert_unread(viewer=viewer).unread_count == unread_before_grouping - 1

    # 4. Drill-down: the grouped item still reaches the other camera's Visit,
    #    and the Story reaches each contributing camera's reviewed Visit.
    group = next(
        item for item in repository.list_product_alerts(category=AlertCategory.review, viewer=viewer).items
        if item.visit_id == "n-a-shared"
    )
    assert [m.visit_id for m in group.grouped_visits] == ["n-b-shared"]
    assert {c.visit_id for c in shared.contributions} == {"v-a-cardinal", "v-b-cardinal"}
    # Truth is untouched by presentation grouping: both Visits still need review.
    with repository.session_factory() as session:
        assert session.get(VisitModel, "n-b-shared").review_status == "needs_review"
        assert session.get(VisitModel, "n-b-unrelated").review_status == "needs_review"
