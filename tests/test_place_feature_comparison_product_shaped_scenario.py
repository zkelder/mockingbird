"""Place Feature Comparison & Habitat Outcomes v1 -- one real, executable,
product-shaped scenario proving the whole comparison surface coheres end to
end, not just each piece in isolation. Follows this codebase's own
established convention for a milestone's capstone integration proof
(Multi-Camera Place Feature Linking v1's own Bird Bath scenario, Place Story
Deep Dives' own two-taxon/two-year scenario): real seeded SQLite state, the
same public repository methods a real API request would call, no mocking of
product logic.

Scenario (mirrors the governing brief's own section 15 worked example):

  Place: Back Yard.
  Cameras: Patio Camera (well-monitored, 20 days coverage) and Garden
    Camera (more lightly monitored, 10 days coverage) -- genuinely
    different monitoring effort.
  Features:
    1. Sunflower Feeder -- Patio Camera / Feeder Zone only. One "added"
       change event with an unambiguous before/after increase. Its
       representative evidence's own media file goes missing (an expired
       asset).
    2. Bird Bath -- linked to BOTH cameras (Patio's Bird Bath Zone and
       Garden's Bird Bath Zone). One "added" change event. Hosts a
       confirmed cross-camera duplicate encounter (one cardinal, both
       cameras, must count once) and a genuinely independent simultaneous
       pair (two chickadees, no association, must remain two).
    3. Wildflower Patch -- Garden Camera / Patch Zone only, added only two
       days before `now` -- its own before/after comparison is honestly
       "too_soon", the immature-change case.
  Environmental context: a real temperature drop around the Bird Bath's
    own change window.
  One species correction: a Bird Bath chickadee is later corrected to a
    different species after the fact.
  One archived camera: Garden Camera is archived once the historical
    window has closed -- Bird Bath's and Wildflower Patch's own linked
    views must stay reachable, never silently drop out.

Demonstrates end-to-end: three comparable Features shown honestly despite
different monitoring effort and different maturity; cross-camera duplicate
exclusion and independent-animal preservation composed correctly into the
Place-wide overview (not just a single Feature's own detail); coverage as a
real elapsed-time union; environmental context attached to exactly the
event it explains, non-causal; a missing/expired media file producing an
honest `None`, never a broken thumbnail; archived-camera history staying
reachable; a Reviewed correction propagating on the very next read with no
invalidation step; and Local Only operation (no network call is ever
attempted).
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
    EnvironmentalContextSettingsUpdate,
    PlaceFeatureCreate,
    PlaceFeatureObservationLinkCreate,
    ReviewCorrectionCreate,
    UserRole,
    VisitReviewRevisionCreate,
)
from mockingbird.environment import weather_provider
from mockingbird.repository.product_repository import (
    CrossCameraVisitAssociationModel,
    ProductRepository,
)
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

SOURCE_PATIO, STREAM_PATIO = "scenario-pfc-patio", "scenario-pfc-patio-stream"
ZONE_PATIO_FEEDER, ZONE_PATIO_BATH = "scenario-pfc-feeder-zone", "scenario-pfc-bath-zone-patio"
SOURCE_GARDEN, STREAM_GARDEN = "scenario-pfc-garden", "scenario-pfc-garden-stream"
ZONE_GARDEN_BATH, ZONE_GARDEN_PATCH = "scenario-pfc-bath-zone-garden", "scenario-pfc-patch-zone"

WEATHER_LATITUDE = 40.7
WEATHER_LONGITUDE = -74.0


def _acting_user() -> CurrentUser:
    return CurrentUser(
        id="user-scenario-pfc", display_name="Scenario User", login_identity="scenario-pfc",
        role=UserRole.administrator, enabled=True,
    )


@pytest.fixture
def repository(tmp_path: Path) -> ProductRepository:
    repo = ProductRepository(db_url=f"sqlite:///{tmp_path / 'mockingbird.sqlite3'}", media_root=tmp_path / "media")
    configure_repository(repo)
    with repo.session_factory() as session:
        with session.begin():
            demo = session.get(CameraSourceModel, "source-backyard-demo")
            if demo is not None:
                demo.status = "archived"
            session.add(CameraSourceModel(
                id=SOURCE_PATIO, name="Patio Camera", kind="manual_upload", status="connected",
                description="Place Feature Comparison scenario fixture.",
            ))
            session.add(StreamModel(
                id=STREAM_PATIO, source_id=SOURCE_PATIO, name="Patio Camera",
                description="Place Feature Comparison scenario fixture.", is_live=False,
            ))
            session.add(ZoneModel(
                id=ZONE_PATIO_FEEDER, stream_id=STREAM_PATIO, name="Feeder Zone", zone_type="feeder",
                polygon_json="[]", is_active=True, monitoring_policy_json=None,
            ))
            session.add(ZoneModel(
                id=ZONE_PATIO_BATH, stream_id=STREAM_PATIO, name="Bird Bath Zone (Patio)", zone_type="birdbath",
                polygon_json="[]", is_active=True, monitoring_policy_json=None,
            ))
            session.add(CameraSourceModel(
                id=SOURCE_GARDEN, name="Garden Camera", kind="manual_upload", status="connected",
                description="Place Feature Comparison scenario fixture.",
            ))
            session.add(StreamModel(
                id=STREAM_GARDEN, source_id=SOURCE_GARDEN, name="Garden Camera",
                description="Place Feature Comparison scenario fixture.", is_live=False,
            ))
            session.add(ZoneModel(
                id=ZONE_GARDEN_BATH, stream_id=STREAM_GARDEN, name="Bird Bath Zone (Garden)", zone_type="birdbath",
                polygon_json="[]", is_active=True, monitoring_policy_json=None,
            ))
            session.add(ZoneModel(
                id=ZONE_GARDEN_PATCH, stream_id=STREAM_GARDEN, name="Patch Zone", zone_type="yard",
                polygon_json="[]", is_active=True, monitoring_policy_json=None,
            ))
    yield repo
    configure_repository(None)
    repo.close()


def _add_visit(repository: ProductRepository, *, visit_id: str, at: datetime, stream_id: str, zone_id: str) -> None:
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


def _attach_primary_evidence(
    repository: ProductRepository, *, visit_id: str, captured_at: datetime, stream_id: str, source_id: str,
    missing_file: bool = False,
) -> None:
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


def _insert_environmental_context_day(repository: ProductRepository, *, for_date: date, value_numeric: float) -> None:
    now = datetime.now(UTC)
    with repository.session_factory() as session:
        with session.begin():
            for hour in range(24):
                session.add(EnvironmentalContextRecordModel(
                    id=f"envctx-pfc-scenario-{for_date.isoformat()}-{hour:02d}", source_id=None,
                    provider_key=weather_provider.WEATHER_PROVIDER_KEY,
                    information_class=weather_provider.WEATHER_INFORMATION_CLASS,
                    metric="air_temperature", value_numeric=value_numeric, value_text=None, unit="celsius",
                    observed_at=datetime(for_date.year, for_date.month, for_date.day, hour, tzinfo=UTC),
                    observed_at_end=None, for_date=for_date, retrieved_at=now,
                    basis_latitude=WEATHER_LATITUDE, basis_longitude=WEATHER_LONGITUDE,
                    provenance_json=None, provenance_schema_version=1, created_at=now,
                ))


def test_backyard_three_feature_two_camera_comparison_coheres_end_to_end(
    repository: ProductRepository, monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Local Only: any attempt to open a real network socket during this
    # entire scenario fails the test immediately.
    def _no_network(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("Place Feature Comparison must never open a network connection (Local Only)")

    monkeypatch.setattr(socket.socket, "connect", _no_network)

    effective = date(2026, 8, 1)
    now = datetime(2026, 8, 8, tzinfo=UTC)  # exactly 7 days after `effective`

    # ---- Act 1: three Features, different scope, different monitoring
    # effort ----------------------------------------------------------------
    repository.add_place_feature(
        PlaceFeatureCreate(
            feature_type="feeder", name="Sunflower Feeder", zone_id=ZONE_PATIO_FEEDER, installed_date=effective,
        ),
        acting_user=_acting_user(),
    )
    bird_bath = repository.add_place_feature(
        PlaceFeatureCreate(
            feature_type="water", name="Bird Bath", zone_id=ZONE_PATIO_BATH, installed_date=effective,
        ),
        acting_user=_acting_user(),
    )
    garden_bath_link = repository.add_place_feature_observation_link(
        bird_bath.id, PlaceFeatureObservationLinkCreate(zone_id=ZONE_GARDEN_BATH), acting_user=_acting_user(),
    )
    assert garden_bath_link is not None
    repository.add_place_feature(
        PlaceFeatureCreate(
            feature_type="vegetation_patch", name="Wildflower Patch", zone_id=ZONE_GARDEN_PATCH,
            installed_date=now.date() - timedelta(days=2),  # added only two days ago -- too soon to compare
        ),
        acting_user=_acting_user(),
    )

    # Patio Camera: well-monitored, full coverage across the entire
    # historical window plus the whole recent 7-day yield window. Garden
    # Camera: genuinely less monitoring effort -- only the last 4 of the
    # trailing 7 days are covered -- both linked Features must be shown
    # honestly, never compared as if equally monitored. (Bird Bath is
    # unaffected: its coverage is the *union* across both linked cameras,
    # and Patio alone already spans the whole window.)
    _cover_days(repository, stream_id=STREAM_PATIO, source_id=SOURCE_PATIO, start=effective - timedelta(days=10), days=20)
    _cover_days(repository, stream_id=STREAM_GARDEN, source_id=SOURCE_GARDEN, start=now.date() - timedelta(days=4), days=4)

    # ---- Act 2: Sunflower Feeder -- unambiguous "more common after",
    # daily presence across the smallest (7-day) post-window -----------------
    for offset in range(7):
        day = effective + timedelta(days=offset)
        visit_id = f"pfc-feeder-{offset}"
        _add_visit(
            repository, visit_id=visit_id, at=datetime(day.year, day.month, day.day, 9, tzinfo=UTC),
            stream_id=STREAM_PATIO, zone_id=ZONE_PATIO_FEEDER,
        )
        _confirm(repository, visit_id=visit_id, label="northern_cardinal")
    # This Visit's own evidence file will be deleted below (Act 7) -- the
    # expired-media case.
    _attach_primary_evidence(
        repository, visit_id="pfc-feeder-0", captured_at=datetime(effective.year, effective.month, effective.day, 9, tzinfo=UTC),
        stream_id=STREAM_PATIO, source_id=SOURCE_PATIO,
    )

    # ---- Act 3: Bird Bath -- a confirmed cross-camera duplicate (counts
    # once) plus a genuinely independent simultaneous pair (counts twice),
    # plus daily single-camera fills, all within the post-window -----------
    for offset in (1, 2, 4, 6):
        day = effective + timedelta(days=offset)
        visit_id = f"pfc-bath-fill-{offset}"
        _add_visit(
            repository, visit_id=visit_id, at=datetime(day.year, day.month, day.day, 10, tzinfo=UTC),
            stream_id=STREAM_PATIO, zone_id=ZONE_PATIO_BATH,
        )
        _confirm(repository, visit_id=visit_id, label="carolina_wren")

    cardinal_at = datetime(2026, 8, 3, 10, 0, tzinfo=UTC)
    _add_visit(repository, visit_id="pfc-bath-cardinal-patio", at=cardinal_at, stream_id=STREAM_PATIO, zone_id=ZONE_PATIO_BATH)
    _add_visit(repository, visit_id="pfc-bath-cardinal-garden", at=cardinal_at, stream_id=STREAM_GARDEN, zone_id=ZONE_GARDEN_BATH)
    _confirm(repository, visit_id="pfc-bath-cardinal-patio", label="northern_cardinal")
    _confirm(repository, visit_id="pfc-bath-cardinal-garden", label="northern_cardinal")
    _associate_cross_camera(repository, visit_id_a="pfc-bath-cardinal-patio", visit_id_b="pfc-bath-cardinal-garden")

    chickadee_at = datetime(2026, 8, 5, 10, 0, tzinfo=UTC)
    _add_visit(repository, visit_id="pfc-bath-chickadee-patio", at=chickadee_at, stream_id=STREAM_PATIO, zone_id=ZONE_PATIO_BATH)
    _add_visit(repository, visit_id="pfc-bath-chickadee-garden", at=chickadee_at, stream_id=STREAM_GARDEN, zone_id=ZONE_GARDEN_BATH)
    _confirm(repository, visit_id="pfc-bath-chickadee-patio", label="carolina_chickadee")
    _confirm(repository, visit_id="pfc-bath-chickadee-garden", label="carolina_chickadee")
    # Deliberately no `_associate_cross_camera` call -- two genuinely
    # independent birds, not one bird seen twice.

    # ---- Act 4: Wildflower Patch -- a little recent activity, irrelevant
    # to its maturity (its change is too_soon regardless) -------------------
    _add_visit(
        repository, visit_id="pfc-patch-visit", at=now - timedelta(hours=6), stream_id=STREAM_GARDEN,
        zone_id=ZONE_GARDEN_PATCH,
    )
    _confirm(repository, visit_id="pfc-patch-visit", label="carolina_wren")

    # ---- Act 5: environmental context around the Bird Bath's own change,
    # emitted once, non-causally ---------------------------------------------
    repository.update_environmental_context_settings(
        EnvironmentalContextSettingsUpdate(latitude=WEATHER_LATITUDE, longitude=WEATHER_LONGITUDE, weather_enabled=True),
        acting_user=_acting_user(),
    )
    pre_start = effective - timedelta(days=7)
    for offset in range(20):
        _insert_environmental_context_day(repository, for_date=pre_start - timedelta(days=offset + 1), value_numeric=15.0)
    for offset in range(7):
        _insert_environmental_context_day(repository, for_date=pre_start + timedelta(days=offset), value_numeric=15.0)
    for offset in range(7):
        _insert_environmental_context_day(repository, for_date=effective + timedelta(days=offset), value_numeric=0.0)

    # ---- Act 6: read the Place-wide comparison overview and check every
    # deliverable it must honor ----------------------------------------------
    overview = repository.get_place_feature_comparison_overview(now=now, local_timezone=UTC)
    assert len(overview.features) == 3
    rows_by_name = {row.feature.name: row for row in overview.features}

    feeder_row = rows_by_name["Sunflower Feeder"]
    assert feeder_row.recent_yield is not None
    assert feeder_row.recent_yield.confirmed_wildlife_visit_count == 7
    assert feeder_row.recent_yield.data_sufficient is True
    assert feeder_row.latest_change is not None
    assert feeder_row.latest_change.comparison.maturity == "comparable"
    assert feeder_row.latest_change.comparison.status == "more_common_under_condition"
    # Not yet deleted -- representative evidence is present for now.
    assert feeder_row.representative_evidence is not None

    bath_row = rows_by_name["Bird Bath"]
    assert len(bath_row.feature.observation_links) == 2
    assert bath_row.recent_yield is not None
    # 4 single-camera fills + 1 deduplicated cardinal pair + 2 independent
    # chickadees = 7 counted encounters from 8 raw Visit rows.
    assert bath_row.recent_yield.confirmed_wildlife_visit_count == 7
    assert bath_row.recent_yield.distinct_taxon_count == 3  # wren, cardinal, chickadee
    # Coverage is the real elapsed-time union of two fully-overlapping
    # cameras over the 7-day yield window, not their sum.
    assert bath_row.recent_yield.monitored_seconds == pytest.approx(7 * 22 * 3600.0, rel=0.05)
    assert bath_row.latest_change.comparison.maturity == "comparable"
    assert bath_row.latest_change.comparison.status == "more_common_under_condition"
    environmental = bath_row.latest_change.environmental_comparison
    assert environmental is not None
    assert environmental.status == "comparable"
    assert environmental.summary == "The after period was notably cooler."
    for forbidden in ("caused", "led to", "resulted in", "because of", "drove", "due to", "improved", "population"):
        assert forbidden not in environmental.summary.lower()

    patch_row = rows_by_name["Wildflower Patch"]
    assert patch_row.latest_change is not None
    assert patch_row.latest_change.comparison.maturity == "too_soon"
    assert patch_row.latest_change.comparison.status is None
    # Different, lighter monitoring effort than the Patio-linked Features --
    # visible honestly (a small, real monitored-seconds figure), never
    # hidden or silently equated with Patio's own heavier coverage.
    assert patch_row.recent_yield is not None
    assert patch_row.recent_yield.monitored_seconds is not None
    assert patch_row.recent_yield.monitored_seconds < feeder_row.recent_yield.monitored_seconds

    # Deliverable B: every event whose own Feature had a monitoring scope
    # at request time appears -- all three do.
    outcome_event_ids = {outcome.event.id for outcome in overview.change_outcomes}
    assert len(overview.change_outcomes) == 3
    assert {feeder_row.latest_change.event.id, bath_row.latest_change.event.id, patch_row.latest_change.event.id} == outcome_event_ids

    # ---- Act 7: the Feeder's own representative evidence file expires --
    # the overview must honestly abstain, never a broken thumbnail ----------
    (repository.media_root / "pfc-feeder-0.jpg").unlink()
    after_expiry = repository.get_place_feature_comparison_overview(now=now, local_timezone=UTC)
    assert next(r for r in after_expiry.features if r.feature.name == "Sunflower Feeder").representative_evidence is None
    # The Feeder's own before/after outcome is completely unaffected by an
    # unrelated missing image.
    assert next(r for r in after_expiry.features if r.feature.name == "Sunflower Feeder").latest_change.comparison.maturity == "comparable"

    # ---- Act 8: Garden Camera archived once the historical window has
    # closed -- Bird Bath's and Wildflower Patch's own Garden-linked views
    # stay reachable, never silently drop out --------------------------------
    repository.update_camera_source(SOURCE_GARDEN, CameraSourceUpdate(archived=True))
    after_archive = repository.get_place_feature_comparison_overview(now=now, local_timezone=UTC)
    bath_after_archive = next(r for r in after_archive.features if r.feature.name == "Bird Bath")
    garden_link_after = next(link for link in bath_after_archive.feature.observation_links if link.source_id == SOURCE_GARDEN)
    assert garden_link_after.source_archived is True
    assert bath_after_archive.recent_yield.confirmed_wildlife_visit_count == 7  # unchanged
    assert bath_after_archive.latest_change.comparison.maturity == "comparable"
    patch_after_archive = next(r for r in after_archive.features if r.feature.name == "Wildflower Patch")
    assert patch_after_archive.feature.observation_links[0].source_archived is True
    assert patch_after_archive.recent_yield is not None  # still reachable, not silently dropped

    # ---- Act 9: a Reviewed correction propagates through the Place-wide
    # overview immediately, with no invalidation step ------------------------
    with repository.session_factory() as session:
        state_token = repository._review_state_token(session, "visit", "pfc-bath-chickadee-garden")
    repository.revise_visit_review(
        "pfc-bath-chickadee-garden",
        VisitReviewRevisionCreate(
            label="blue_jay", expected_state_token=state_token,
            idempotency_key="scenario-pfc-correct-chickadee-garden", review_origin="human",
        ),
    )
    after_correction = repository.get_place_feature_comparison_overview(now=now, local_timezone=UTC)
    bath_after_correction = next(r for r in after_correction.features if r.feature.name == "Bird Bath")
    assert bath_after_correction.recent_yield.confirmed_wildlife_visit_count == 7  # unaffected -- still both independent birds
    assert bath_after_correction.recent_yield.distinct_taxon_count == 4  # wren, cardinal, chickadee, blue_jay -- was 3
