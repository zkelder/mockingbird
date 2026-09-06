"""Multi-Camera Place Feature Linking & Cross-View Habitat Context v1 -- one
real, executable, product-shaped scenario proving the whole chain coheres
end to end, not just each piece in isolation. Follows this codebase's own
established convention for a milestone's capstone integration proof
(Multi-Camera Place Experience v2's own 3-camera scenario, Year-over-Year
Seasonality's own 2-camera/2-year scenario): real seeded SQLite state, the
same public repository methods a real API request would call, no mocking of
product logic.

Scenario (mirrors the governing brief's own section 30 worked example):

  Place: Back Yard.
  Feature: Bird Bath (one canonical Place Feature).
  Views:
    1. Patio Camera / Bird Bath Zone
    2. Garden Camera / Pond Edge Zone

  History:
    - one Reviewed "added" change event for Bird Bath;
    - one associated cross-camera cardinal encounter (the same real bird
      seen by both cameras within seconds) -- must count once, not twice;
    - one simultaneous, genuinely independent chickadee pair (no
      association at all) -- must remain two;
    - environmental context around the change (a real temperature delta);
    - Patio Camera renamed mid-scenario;
    - Garden Camera archived after the historical window closes;
    - one species label corrected via the real revision path.

Demonstrates end-to-end: one canonical Feature with two observation links;
cross-camera duplicate-encounter deduplication; independent-animal
preservation; coverage as a real elapsed-time union, not a sum; coherent
before/after analytics across both linked views; exactly one Place Story
Feature-change entry (never one per camera); environmental context emitted
once; camera-rename safety; archived-camera historical reachability;
Reviewed-correction propagation; and Local Only operation (no network call
is ever attempted).
"""

from __future__ import annotations

import socket
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest

from mockingbird.api.main import configure_repository
from mockingbird.api.schemas import (
    CameraSourceUpdate,
    EnvironmentalContextSettingsUpdate,
    PlaceFeatureChangeEventCreate,
    PlaceFeatureCreate,
    PlaceFeatureObservationLinkCreate,
    ReviewCorrectionCreate,
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
    MonitoringExposureIntervalModel,
    StreamModel,
    VisitModel,
    ZoneModel,
)

SOURCE_PATIO, STREAM_PATIO, ZONE_PATIO = "scenario-mcpf-patio", "scenario-mcpf-patio-stream", "scenario-mcpf-bird-bath-zone"
SOURCE_GARDEN, STREAM_GARDEN, ZONE_GARDEN = "scenario-mcpf-garden", "scenario-mcpf-garden-stream", "scenario-mcpf-pond-edge-zone"

WEATHER_LATITUDE = 40.7
WEATHER_LONGITUDE = -74.0


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
                    description="Multi-Camera Place Feature Linking scenario fixture.",
                ))
                session.add(StreamModel(
                    id=stream_id, source_id=source_id, name=source_name,
                    description="Multi-Camera Place Feature Linking scenario fixture.", is_live=False,
                ))
                session.add(ZoneModel(
                    id=zone_id, stream_id=stream_id, name=zone_name, zone_type="birdbath",
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


def _insert_environmental_context_day(
    repository: ProductRepository, *, for_date: date, value_numeric: float,
) -> None:
    now = datetime.now(UTC)
    with repository.session_factory() as session:
        with session.begin():
            for hour in range(24):
                session.add(EnvironmentalContextRecordModel(
                    id=f"envctx-mcpf-scenario-{for_date.isoformat()}-{hour:02d}", source_id=None,
                    provider_key=weather_provider.WEATHER_PROVIDER_KEY,
                    information_class=weather_provider.WEATHER_INFORMATION_CLASS,
                    metric="air_temperature", value_numeric=value_numeric, value_text=None, unit="celsius",
                    observed_at=datetime(for_date.year, for_date.month, for_date.day, hour, tzinfo=UTC),
                    observed_at_end=None, for_date=for_date, retrieved_at=now,
                    basis_latitude=WEATHER_LATITUDE, basis_longitude=WEATHER_LONGITUDE,
                    provenance_json=None, provenance_schema_version=1, created_at=now,
                ))


def test_bird_bath_two_camera_scenario_coheres_end_to_end(
    repository: ProductRepository, monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Local Only: any attempt to open a real network socket during this
    # entire scenario fails the test immediately.
    def _no_network(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("Multi-Camera Place Feature Linking must never open a network connection (Local Only)")

    monkeypatch.setattr(socket.socket, "connect", _no_network)

    effective = date(2026, 7, 1)
    # `now` sits exactly at the smallest candidate window's own `post_end`
    # (7 days after `effective`) -- far enough past the change for the
    # before/after comparison to mature, and close enough that the same
    # week's activity also falls inside `recent_yield`'s own trailing
    # 7-day window, so one scenario narrative can prove both.
    now = datetime(2026, 7, 8, tzinfo=UTC)

    # ---- Act 1: one canonical Bird Bath, created on Patio, then also
    # linked to Garden -- "these cameras are different views of the same
    # thing," never two Features -----------------------------------------
    feature = repository.add_place_feature(
        PlaceFeatureCreate(
            feature_type="water", name="Bird Bath", zone_id=ZONE_PATIO, installed_date=effective,
        ),
        acting_user=_acting_user(),
    )
    garden_link = repository.add_place_feature_observation_link(
        feature.id, PlaceFeatureObservationLinkCreate(zone_id=ZONE_GARDEN), acting_user=_acting_user(),
    )
    assert garden_link is not None
    detail = repository.get_place_feature_detail(feature.id, now=now, local_timezone=UTC)
    assert len(detail.feature.observation_links) == 2
    assert {link.source_name for link in detail.feature.observation_links} == {"Patio Camera", "Garden Camera"}
    # Exactly one "added" change event was seeded by creation -- adding the
    # second observation link must not have created a second one, and must
    # not itself read as a physical habitat change (Phase 15).
    changes = repository.list_place_feature_change_events(feature_id=feature.id)
    assert len(changes) == 1
    assert changes[0].event_type == "added"

    # ---- Act 2: monitoring coverage on both cameras, overlapping in time,
    # spanning well before and after the change --------------------------
    _cover_days(repository, stream_id=STREAM_PATIO, source_id=SOURCE_PATIO, start=effective - timedelta(days=10), days=20)
    _cover_days(repository, stream_id=STREAM_GARDEN, source_id=SOURCE_GARDEN, start=effective - timedelta(days=10), days=20)

    # ---- Act 3: one confirmed visitor every day of the change's own
    # 7-day post-window [effective, effective+7) -- an unambiguous "more
    # common after," entirely inside both `recent_yield`'s own trailing
    # window and the before/after comparison's own smallest window -------
    for offset in (0, 1, 3, 5, 6):  # July 1, 2, 4, 6, 7 -- one camera each, alternating
        stream_id, zone_id = (STREAM_PATIO, ZONE_PATIO) if offset % 2 == 0 else (STREAM_GARDEN, ZONE_GARDEN)
        day = effective + timedelta(days=offset)
        visit_id = f"mcpf-fill-{offset}"
        _add_visit(repository, visit_id=visit_id, at=datetime(day.year, day.month, day.day, 9, tzinfo=UTC), stream_id=stream_id, zone_id=zone_id)
        _confirm(repository, visit_id=visit_id, label="northern_cardinal")

    # July 3: a genuine cross-camera duplicate -- one cardinal, seen by
    # both linked cameras within seconds -- must count once, not twice.
    cardinal_at = datetime(2026, 7, 3, 9, 0, tzinfo=UTC)
    _add_visit(repository, visit_id="mcpf-cardinal-patio", at=cardinal_at, stream_id=STREAM_PATIO, zone_id=ZONE_PATIO)
    _add_visit(repository, visit_id="mcpf-cardinal-garden", at=cardinal_at, stream_id=STREAM_GARDEN, zone_id=ZONE_GARDEN)
    _confirm(repository, visit_id="mcpf-cardinal-patio", label="northern_cardinal")
    _confirm(repository, visit_id="mcpf-cardinal-garden", label="northern_cardinal")
    _associate_cross_camera(repository, visit_id_a="mcpf-cardinal-patio", visit_id_b="mcpf-cardinal-garden")

    # ---- Act 4: two genuinely independent chickadees, simultaneous, no
    # association -- must remain two -------------------------------------
    chickadee_at = datetime(2026, 7, 5, 9, 0, tzinfo=UTC)
    _add_visit(repository, visit_id="mcpf-chickadee-patio", at=chickadee_at, stream_id=STREAM_PATIO, zone_id=ZONE_PATIO)
    _add_visit(repository, visit_id="mcpf-chickadee-garden", at=chickadee_at, stream_id=STREAM_GARDEN, zone_id=ZONE_GARDEN)
    _confirm(repository, visit_id="mcpf-chickadee-patio", label="carolina_chickadee")
    _confirm(repository, visit_id="mcpf-chickadee-garden", label="carolina_chickadee")
    # Deliberately no `_associate_cross_camera` call for this pair.

    recent_yield = repository.get_place_feature_detail(feature.id, now=now, local_timezone=UTC).recent_yield
    assert recent_yield is not None
    # 5 (single-camera fill days) + 1 (deduped cardinal pair) + 2 (independent
    # chickadees) = 8 raw visits collapse to 8 counted encounters (only the
    # cardinal PAIR itself collapses from 2 rows to 1).
    assert recent_yield.confirmed_wildlife_visit_count == 8
    assert recent_yield.distinct_taxon_count == 2  # cardinal, chickadee
    # Coverage is the real elapsed-time union of two fully-overlapping
    # cameras over `FEATURE_YIELD_WINDOW_DAYS` (7 days), not their sum.
    assert recent_yield.monitored_seconds == pytest.approx(7 * 22 * 3600.0, rel=0.05)

    # ---- Act 5: environmental context around the change, emitted once --
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

    detail = repository.get_place_feature_detail(feature.id, now=now, local_timezone=UTC)
    comparison = detail.changes[0].comparison
    assert comparison is not None
    assert comparison.maturity == "comparable"
    assert comparison.status == "more_common_under_condition"
    environmental = detail.changes[0].environmental_comparison
    assert environmental is not None
    assert environmental.summary == "The after period was notably cooler."

    story = repository.place_story(
        start_at=datetime(2026, 1, 1, tzinfo=UTC), end_at=now, feature_id=feature.id, now=now, local_timezone=UTC,
    )
    feature_change_entries = [entry for entry in story.entries if entry.kind == "feature_change"]
    comparison_entries = [entry for entry in story.entries if entry.kind == "comparison_insight"]
    assert len(feature_change_entries) == 1, "one Feature change event, never one per linked camera"
    assert len(comparison_entries) == 1, "environmental context composed once, never duplicated per view"

    # ---- Act 6: Patio Camera renamed -- the link survives untouched ----
    repository.update_camera_source(SOURCE_PATIO, CameraSourceUpdate(name="Front Patio"))
    renamed_links = repository.get_place_feature_detail(feature.id, now=now, local_timezone=UTC).feature.observation_links
    assert {link.source_name for link in renamed_links} == {"Front Patio", "Garden Camera"}
    assert len(renamed_links) == 2

    # ---- Act 7: Garden Camera archived -- historical comparison for the
    # window above (entirely before archival) remains fully reachable ----
    repository.update_camera_source(SOURCE_GARDEN, CameraSourceUpdate(archived=True))
    after_archive = repository.get_place_feature_detail(feature.id, now=now, local_timezone=UTC)
    garden_link_after = next(link for link in after_archive.feature.observation_links if link.source_id == SOURCE_GARDEN)
    assert garden_link_after.source_archived is True
    comparison_after_archive = after_archive.changes[0].comparison
    assert comparison_after_archive is not None
    assert comparison_after_archive.maturity == "comparable"
    assert comparison_after_archive.status == "more_common_under_condition"
    assert after_archive.recent_yield is not None
    assert after_archive.recent_yield.confirmed_wildlife_visit_count == 8

    # ---- Act 8: a reviewed correction propagates through cross-view
    # analytics immediately, with no invalidation step ---------------------
    with repository.session_factory() as session:
        state_token = repository._review_state_token(session, "visit", "mcpf-chickadee-garden")
    repository.revise_visit_review(
        "mcpf-chickadee-garden",
        VisitReviewRevisionCreate(
            label="blue_jay", expected_state_token=state_token,
            idempotency_key="scenario-mcpf-correct-chickadee-garden", review_origin="human",
        ),
    )
    corrected = repository.get_place_feature_detail(feature.id, now=now, local_timezone=UTC).recent_yield
    assert corrected is not None
    assert corrected.confirmed_wildlife_visit_count == 8  # count unaffected, still both independent birds
    assert corrected.distinct_taxon_count == 3  # cardinal, chickadee, blue_jay -- was 2 before the correction


def _acting_user():
    from mockingbird.api.schemas import CurrentUser, UserRole

    return CurrentUser(
        id="user-scenario-mcpf", display_name="Scenario User", login_identity="scenario-mcpf",
        role=UserRole.administrator, enabled=True,
    )
