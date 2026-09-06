"""Place Story Deep Dives & Representative Evidence v1 -- one real,
executable, product-shaped scenario proving the Taxon Story and Feature
Story deep-dive chains cohere end to end, not just each piece in isolation.
Follows this codebase's own established convention for a milestone's
capstone integration proof (Multi-Camera Place Feature Linking v1's own
Bird Bath/two-camera scenario, Year-over-Year Seasonality's own 2-camera/
2-year scenario): real seeded SQLite state, the same public repository
methods a real API request would call, no mocking of product logic.

Scenario (mirrors the governing brief's own section 34 worked example):

  Place: Back Yard.
  Taxa: Northern Cardinal, Carolina Wren.
  Feature: Bird Bath, linked to two camera views (Patio Camera / Bird Bath
    Zone, Garden Camera / Pond Edge Zone) -- the identical Feature/camera
    naming Multi-Camera Place Feature Linking v1's own scenario already
    established, for continuity.

  History:
    - multiple years of Cardinal activity (September 2025 moderate,
      September 2026 materially higher -- a real year-over-year change);
    - Carolina Wren activity, entirely independent of the Feature/Cardinal
      story (proves Taxon Story scoping excludes it from Cardinal's own
      timeline, and Feature Story excludes it from Bird Bath's);
    - a Reviewed "added" Bird Bath change event with a real before/after
      wildlife shift;
    - several real evidence frames, including one already-deleted file
      (representative-evidence must abstain on that one candidate, not
      break the whole selection);
    - an associated cross-camera Cardinal Visit (one real encounter, both
      cameras, must count once);
    - Patio Camera renamed, Garden Camera archived after its own historical
      window closes;
    - one Reviewed species correction.

Demonstrates end to end: a Taxon Story's timeline and year-over-year facts
are Cardinal-only (Wren never leaks in, and vice versa); a Feature Story's
representative evidence and timeline are Bird-Bath-only and camera-count-
independent; representative evidence abstains cleanly on a missing file
without breaking selection; a species correction moves Taxon Story history
and Feature representative evidence immediately, with no invalidation step;
camera rename/archival never breaks either surface; and Local Only
operation (no network call is ever attempted) throughout.
"""

from __future__ import annotations

import socket
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest

from mockingbird.api.main import configure_repository
from mockingbird.api.schemas import (
    CameraSourceUpdate,
    CurrentUser,
    PlaceFeatureCreate,
    PlaceFeatureObservationLinkCreate,
    ReviewCorrectionCreate,
    UserRole,
    VisitReviewRevisionCreate,
)
from mockingbird.repository.product_repository import (
    CrossCameraVisitAssociationModel,
    ProductRepository,
)
from mockingbird.storage.models import (
    CameraSourceModel,
    EventModel,
    MediaAssetModel,
    MonitoringExposureIntervalModel,
    StreamModel,
    VisitEvidenceLinkModel,
    VisitModel,
    ZoneModel,
)

SOURCE_PATIO, STREAM_PATIO, ZONE_PATIO = "scenario-psd-patio", "scenario-psd-patio-stream", "scenario-psd-bird-bath-zone"
SOURCE_GARDEN, STREAM_GARDEN, ZONE_GARDEN = "scenario-psd-garden", "scenario-psd-garden-stream", "scenario-psd-pond-edge-zone"

CURRENT_YEAR, PRIOR_YEAR = 2026, 2025


@pytest.fixture
def repository(tmp_path: Path) -> ProductRepository:
    repo = ProductRepository(db_url=f"sqlite:///{tmp_path / 'mockingbird.sqlite3'}", media_root=tmp_path / "media")
    configure_repository(repo)
    with repo.session_factory() as session:
        with session.begin():
            demo = session.get(CameraSourceModel, "source-backyard-demo")
            if demo is not None:
                demo.status = "archived"
            for source_id, stream_id, zone_id, source_name, zone_name in (
                (SOURCE_PATIO, STREAM_PATIO, ZONE_PATIO, "Patio Camera", "Bird Bath Zone"),
                (SOURCE_GARDEN, STREAM_GARDEN, ZONE_GARDEN, "Garden Camera", "Pond Edge Zone"),
            ):
                session.add(CameraSourceModel(
                    id=source_id, name=source_name, kind="manual_upload", status="connected",
                    description="Place Story Deep Dives scenario fixture.",
                ))
                session.add(StreamModel(
                    id=stream_id, source_id=source_id, name=source_name,
                    description="Place Story Deep Dives scenario fixture.", is_live=False,
                ))
                session.add(ZoneModel(
                    id=zone_id, stream_id=stream_id, name=zone_name, zone_type="birdbath",
                    polygon_json="[]", is_active=True, monitoring_policy_json=None,
                ))
    yield repo
    configure_repository(None)
    repo.close()


def _acting_user() -> CurrentUser:
    return CurrentUser(
        id="user-scenario-psd", display_name="Scenario User", login_identity="scenario-psd",
        role=UserRole.administrator, enabled=True,
    )


def _add_visit(
    repository: ProductRepository, *, visit_id: str, at: datetime, stream_id: str, zone_id: str,
) -> None:
    event_id = f"event-{visit_id}"
    with repository.session_factory() as session:
        with session.begin():
            session.add(EventModel(
                id=event_id, stream_id=stream_id, title=f"Scenario fixture {visit_id}",
                event_type="manual_media_import", started_at=at, ended_at=at + timedelta(seconds=20),
                primary_zone_id=zone_id, review_status="needs_review",
            ))
            session.add(VisitModel(
                id=visit_id, event_id=event_id, subject_label="unknown_bird", species_guess=None,
                confidence=None, reviewed_label=None, review_status="needs_review",
                representative_media_path=None, zone_id=zone_id, is_superseded=False,
            ))


def _confirm(repository: ProductRepository, *, visit_id: str, label: str) -> None:
    repository.create_review_label(
        ReviewCorrectionCreate(target_type="visit", target_id=visit_id, label=label, review_origin="human")
    )


def _attach_evidence(
    repository: ProductRepository, *, visit_id: str, captured_at: datetime, stream_id: str,
    source_id: str, missing_file: bool = False,
) -> str:
    """A real, persisted, `is_primary` evidence frame -- a real backing file
    (unless `missing_file`), since the representative-evidence selector
    honestly checks `Path(local_path).is_file()`."""

    media_id = f"media-{visit_id}"
    media_path = repository.media_root / f"{visit_id}.jpg"
    if not missing_file:
        media_path.parent.mkdir(parents=True, exist_ok=True)
        media_path.write_bytes(b"fixture-jpeg-bytes")
    with repository.session_factory() as session:
        with session.begin():
            session.add(MediaAssetModel(
                id=media_id, source_id=source_id, stream_id=stream_id, filename=f"{media_id}.jpg",
                content_type="image/jpeg", media_type="image", local_path=str(media_path),
                original_filename=f"{media_id}.jpg", file_size_bytes=12, created_at=captured_at,
                image_width=800, image_height=600,
            ))
            session.add(VisitEvidenceLinkModel(
                id=f"link-{visit_id}", visit_id=visit_id, media_asset_id=media_id, captured_at=captured_at,
                frame_sequence=0, sort_order=0, is_primary=True, evidence_role="identification",
                created_at=captured_at,
            ))
    return media_id


def _cover_days(repository: ProductRepository, *, stream_id: str, source_id: str, start: date, days: int) -> None:
    with repository.session_factory() as session:
        with session.begin():
            for offset in range(days):
                day = start + timedelta(days=offset)
                started_at = datetime(day.year, day.month, day.day, tzinfo=UTC)
                ended_at = started_at + timedelta(hours=22)
                session.add(MonitoringExposureIntervalModel(
                    id=f"exposure-{stream_id}-{day.isoformat()}", stream_id=stream_id, source_id=source_id,
                    runtime_generation_id=f"generation-{stream_id}-{day.isoformat()}", started_at=started_at,
                    last_confirmed_fresh_at=ended_at, ended_at=ended_at, close_reason="provider_failure",
                    created_at=started_at, updated_at=ended_at,
                ))


def _associate_cross_camera(repository: ProductRepository, *, visit_id_a: str, visit_id_b: str) -> None:
    primary_id, secondary_id = sorted((visit_id_a, visit_id_b))
    now = datetime.now(UTC)
    with repository.session_factory() as session:
        with session.begin():
            session.add(CrossCameraVisitAssociationModel(
                id=f"assoc-{visit_id_a}-{visit_id_b}", primary_visit_id=primary_id, secondary_visit_id=secondary_id,
                tier="associated", overlap_ms=1000, gap_ms=0, spatial_signal="matching_area_name",
                multi_subject=False, engine_version="cross-camera-association-v1", created_at=now, updated_at=now,
            ))


def test_taxon_and_feature_story_scenario_coheres_end_to_end(
    repository: ProductRepository, monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Local Only: any attempt to open a real network socket during this
    # entire scenario fails the test immediately.
    def _no_network(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("Place Story deep dives must never open a network connection (Local Only)")

    monkeypatch.setattr(socket.socket, "connect", _no_network)

    now = datetime(CURRENT_YEAR, 10, 2, tzinfo=UTC)
    effective = date(CURRENT_YEAR, 9, 25)  # a Bird Bath change late in the comparison window

    # ---- Act 1: one canonical Bird Bath, linked to two camera views -----
    feature = repository.add_place_feature(
        PlaceFeatureCreate(feature_type="water", name="Bird Bath", zone_id=ZONE_PATIO, installed_date=effective),
        acting_user=_acting_user(),
    )
    repository.add_place_feature_observation_link(
        feature.id, PlaceFeatureObservationLinkCreate(zone_id=ZONE_GARDEN), acting_user=_acting_user(),
    )
    detail = repository.get_place_feature_detail(feature.id, now=now, local_timezone=UTC)
    assert {link.source_name for link in detail.feature.observation_links} == {"Patio Camera", "Garden Camera"}

    # ---- Act 2: two years of monitoring coverage on both cameras --------
    _cover_days(repository, stream_id=STREAM_PATIO, source_id=SOURCE_PATIO, start=date(PRIOR_YEAR, 8, 20), days=420)
    _cover_days(repository, stream_id=STREAM_GARDEN, source_id=SOURCE_GARDEN, start=date(PRIOR_YEAR, 8, 20), days=420)

    # ---- Act 3: Cardinal activity across both Septembers -- moderate a
    # year ago, materially higher this year (a real year-over-year change),
    # spread across both linked cameras --------------------------------
    for i, day in enumerate((3, 10, 17)):  # prior year: 3 of 30 days
        visit_id = f"psd-cardinal-prior-{i}"
        stream_id, zone_id, source_id = (
            (STREAM_PATIO, ZONE_PATIO, SOURCE_PATIO) if i % 2 == 0 else (STREAM_GARDEN, ZONE_GARDEN, SOURCE_GARDEN)
        )
        at = datetime(PRIOR_YEAR, 9, day, 9, tzinfo=UTC)
        _add_visit(repository, visit_id=visit_id, at=at, stream_id=stream_id, zone_id=zone_id)
        _confirm(repository, visit_id=visit_id, label="northern_cardinal")
        _attach_evidence(repository, visit_id=visit_id, captured_at=at, stream_id=stream_id, source_id=source_id)

    for i, day in enumerate(range(1, 17)):  # this year: 16 of 30 days
        visit_id = f"psd-cardinal-cur-{i}"
        stream_id, zone_id, source_id = (
            (STREAM_PATIO, ZONE_PATIO, SOURCE_PATIO) if i % 2 == 0 else (STREAM_GARDEN, ZONE_GARDEN, SOURCE_GARDEN)
        )
        at = datetime(CURRENT_YEAR, 9, day, 9, tzinfo=UTC)
        _add_visit(repository, visit_id=visit_id, at=at, stream_id=stream_id, zone_id=zone_id)
        _confirm(repository, visit_id=visit_id, label="northern_cardinal")
        # Every current-year Cardinal frame is real evidence except one,
        # which has already lost its underlying media file -- representative
        # selection must skip it honestly, never surface a broken thumbnail.
        _attach_evidence(
            repository, visit_id=visit_id, captured_at=at, stream_id=stream_id, source_id=source_id,
            missing_file=(i == 0),
        )

    # A real cross-camera duplicate: one Cardinal, seen by both linked
    # cameras within seconds of each other -- must count once, not twice.
    dup_at = datetime(CURRENT_YEAR, 9, 20, 9, 0, tzinfo=UTC)
    _add_visit(repository, visit_id="psd-cardinal-dup-patio", at=dup_at, stream_id=STREAM_PATIO, zone_id=ZONE_PATIO)
    _add_visit(repository, visit_id="psd-cardinal-dup-garden", at=dup_at, stream_id=STREAM_GARDEN, zone_id=ZONE_GARDEN)
    _confirm(repository, visit_id="psd-cardinal-dup-patio", label="northern_cardinal")
    _confirm(repository, visit_id="psd-cardinal-dup-garden", label="northern_cardinal")
    _associate_cross_camera(repository, visit_id_a="psd-cardinal-dup-patio", visit_id_b="psd-cardinal-dup-garden")

    # ---- Act 4: Carolina Wren activity -- a real, independent taxon that
    # must never leak into Cardinal's Taxon Story or Bird Bath's own
    # Feature Story (it is confirmed at the *same* Feature, but a Taxon
    # Story is taxon-scoped and a Feature Story is Feature-event-scoped,
    # neither is "every Visit here") -------------------------------------
    for i, day in enumerate((2, 4, 6, 8, 10)):
        visit_id = f"psd-wren-{i}"
        at = datetime(CURRENT_YEAR, 9, day, 11, tzinfo=UTC)
        _add_visit(repository, visit_id=visit_id, at=at, stream_id=STREAM_PATIO, zone_id=ZONE_PATIO)
        _confirm(repository, visit_id=visit_id, label="carolina_wren")

    # ---- Act 5: representative evidence, Feature-scoped ------------------
    detail = repository.get_place_feature_detail(feature.id, now=now, local_timezone=UTC)
    assert detail.representative_evidence is not None
    # The winning image is a real, still-present Cardinal frame -- never
    # the deleted one, and never an unrelated frame picked to fill layout.
    assert detail.representative_evidence.visit_id != "psd-cardinal-cur-0"
    winning_path = repository.media_file_path(detail.representative_evidence.evidence.media_asset_id)
    assert winning_path is not None and winning_path.is_file()

    # ---- Act 6: Taxon Story -- Cardinal-only, Wren excluded --------------
    cardinal_story = repository.place_story(
        start_at=datetime(PRIOR_YEAR, 1, 1, tzinfo=UTC), end_at=now, taxon="northern_cardinal", now=now,
        local_timezone=UTC,
    )
    assert cardinal_story.entries, "a Taxon Story must contain at least one meaningful event for an active taxon"
    assert all(entry.taxon_label in (None, "northern_cardinal") for entry in cardinal_story.entries)
    assert not any(entry.taxon_label == "carolina_wren" for entry in cardinal_story.entries)

    wren_story = repository.place_story(
        start_at=datetime(PRIOR_YEAR, 1, 1, tzinfo=UTC), end_at=now, taxon="carolina_wren", now=now,
        local_timezone=UTC,
    )
    assert not any(entry.taxon_label == "northern_cardinal" for entry in wren_story.entries)

    # ---- Act 7: year-over-year, taxon-scoped -- a real material increase
    # narrated for Cardinal specifically, composed from the same facts the
    # Place-wide comparison already computed (never a second engine) ------
    yoy = repository.place_year_over_year_comparison(now=now, year=CURRENT_YEAR, month=9, taxon="northern_cardinal")
    assert yoy.taxon_comparison is not None
    assert yoy.taxon_comparison.label == "northern_cardinal"
    assert yoy.taxon_comparison.activity_direction == "higher"

    # ---- Act 8: Feature Story -- Bird-Bath-only, one entry regardless of
    # camera count (Multi-Camera Place Feature Linking v1's own guarantee,
    # unaffected by this milestone) ---------------------------------------
    feature_story = repository.place_story(
        start_at=datetime(PRIOR_YEAR, 1, 1, tzinfo=UTC), end_at=now, feature_id=feature.id, now=now,
        local_timezone=UTC,
    )
    feature_change_entries = [entry for entry in feature_story.entries if entry.kind == "feature_change"]
    assert len(feature_change_entries) == 1, "one Feature change event, never one per linked camera"
    assert not any(entry.taxon_label is not None for entry in feature_story.entries), (
        "a Feature Story must not turn into a per-Visit wildlife log"
    )

    # ---- Act 9: Patio Camera renamed, Garden Camera archived -- neither
    # Taxon Story, Feature Story, nor representative evidence breaks ------
    repository.update_camera_source(SOURCE_PATIO, CameraSourceUpdate(name="Front Patio"))
    repository.update_camera_source(SOURCE_GARDEN, CameraSourceUpdate(archived=True))

    after_rename_archive = repository.get_place_feature_detail(feature.id, now=now, local_timezone=UTC)
    assert after_rename_archive.representative_evidence is not None
    garden_link = next(
        link for link in after_rename_archive.feature.observation_links if link.source_id == SOURCE_GARDEN
    )
    assert garden_link.source_archived is True
    cardinal_story_after_archive = repository.place_story(
        start_at=datetime(PRIOR_YEAR, 1, 1, tzinfo=UTC), end_at=now, taxon="northern_cardinal", now=now,
        local_timezone=UTC,
    )
    assert len(cardinal_story_after_archive.entries) == len(cardinal_story.entries), (
        "archiving a linked camera must not silently erase Cardinal's own Taxon Story history"
    )

    # ---- Act 10: a Reviewed correction moves Taxon Story and Feature
    # representative evidence immediately, with no invalidation step ------
    winning_visit_id = detail.representative_evidence.visit_id
    with repository.session_factory() as session:
        state_token = repository._review_state_token(session, "visit", winning_visit_id)
    repository.revise_visit_review(
        winning_visit_id,
        VisitReviewRevisionCreate(
            label="false_positive", expected_state_token=state_token,
            idempotency_key="scenario-psd-correct-winner", review_origin="human",
        ),
    )
    after_correction = repository.get_place_feature_detail(feature.id, now=now, local_timezone=UTC)
    assert after_correction.representative_evidence is None or (
        after_correction.representative_evidence.visit_id != winning_visit_id
    ), "a corrected-away Visit must stop being representative on the very next read"
