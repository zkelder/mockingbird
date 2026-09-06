"""Year-over-Year Seasonality & Long-Term Place Memory v1 -- one real,
executable, product-shaped scenario proving the whole chain coheres end to
end, not just each piece in isolation. Follows this codebase's own
established convention for a milestone's capstone integration proof
(Multi-Camera Place Experience v2's own 3-camera scenario, Ecological
Interoperability's 12-Visit scenario): real seeded SQLite state, the same
public repository methods a real API request would call, no mocking of
product logic.

Scenario (mirrors the milestone's own governing brief, section 26):

  Place with 2 cameras (Front Feeder, Back Yard).

  September 2025 (prior year):
    - known monitoring coverage on both cameras;
    - several species, including a moderate-regularity Northern Cardinal
      (6 of 30 days) and Eastern Bluebird first observed September 25;
    - one Visit later reclassified from an initial (incorrect) label.

  September 2026 (current year):
    - different (but still adequate) monitoring coverage;
    - Northern Cardinal genuinely higher normalized activity (16 of 30
      days -- an 8 of 30 unnormalized display difference clears the 0.25
      rate-difference floor even after normalization);
    - Eastern Bluebird first observed materially earlier (September 8,
      vs. September 25 a year ago);
    - one cross-camera associated encounter (the same real bird seen by
      both cameras within seconds) that must count once, not twice;
    - Back Yard (one of the two cameras) is archived partway through the
      scenario -- its real September 2025/2026 history must remain
      reachable, unlike Today/Bird Log's own deliberate current-active-
      observatory default.

Demonstrates end-to-end: normalized Place comparison; correct historical
inclusion across an archived camera; no cross-camera duplicate inflation;
Reviewed-correction propagation; a calm Place Story insight; Local Only
operation (no network call is ever attempted).
"""

from __future__ import annotations

import socket
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest

from mockingbird.api.main import configure_repository
from mockingbird.api.schemas import ReviewCorrectionCreate
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

SOURCE_A, STREAM_A, ZONE_A = "scenario-yoy-source-a", "scenario-yoy-stream-a", "scenario-yoy-zone-a"
SOURCE_B, STREAM_B, ZONE_B = "scenario-yoy-source-b", "scenario-yoy-stream-b", "scenario-yoy-zone-b"

CURRENT_YEAR = 2026
PRIOR_YEAR = 2025


@pytest.fixture
def repository(tmp_path: Path) -> ProductRepository:
    repo = ProductRepository(db_url=f"sqlite:///{tmp_path / 'mockingbird.sqlite3'}", media_root=tmp_path / "media")
    configure_repository(repo)
    with repo.session_factory() as session:
        with session.begin():
            demo = session.get(CameraSourceModel, "source-backyard-demo")
            if demo is not None:
                demo.status = "archived"
            for source_id, stream_id, zone_id, name in (
                (SOURCE_A, STREAM_A, ZONE_A, "Front Feeder"),
                (SOURCE_B, STREAM_B, ZONE_B, "Back Yard"),
            ):
                session.add(CameraSourceModel(
                    id=source_id, name=name, kind="manual_upload", status="connected",
                    description="Year-over-Year product-shaped scenario fixture.",
                ))
                session.add(StreamModel(
                    id=stream_id, source_id=source_id, name=name,
                    description="Year-over-Year product-shaped scenario fixture.", is_live=False,
                ))
                session.add(ZoneModel(
                    id=zone_id, stream_id=stream_id, name="Feeder", zone_type="feeder",
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


def test_two_camera_year_over_year_scenario_coheres_end_to_end(
    repository: ProductRepository, monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Local Only: any attempt to open a real network socket during this
    # entire scenario fails the test immediately -- proving this feature
    # never depends on network access, not merely asserting it by reading
    # the source. Mirrors this codebase's own "an always-fails requester
    # proves the new code paths never attempt a live fetch" precedent
    # (Environmental Context x Place Story & Habitat Change Composition v1),
    # generalized to the socket layer so it catches any HTTP client, not
    # just one specific library.
    def _no_network(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("Year-over-Year Seasonality must never open a network connection (Local Only)")

    monkeypatch.setattr(socket.socket, "connect", _no_network)

    # ---- Act 1: both cameras, both Septembers, ordinary activity -------
    _cover_days(repository, stream_id=STREAM_A, source_id=SOURCE_A, start=date(PRIOR_YEAR, 9, 1), days=30)
    _cover_days(repository, stream_id=STREAM_B, source_id=SOURCE_B, start=date(PRIOR_YEAR, 9, 1), days=30)
    _cover_days(repository, stream_id=STREAM_A, source_id=SOURCE_A, start=date(CURRENT_YEAR, 9, 1), days=30)
    _cover_days(repository, stream_id=STREAM_B, source_id=SOURCE_B, start=date(CURRENT_YEAR, 9, 1), days=30)

    # September 2025: Cardinal moderate regularity (6 of 30 days), split
    # across both cameras -- proves Place-level counting is camera-agnostic.
    for i, day in enumerate([2, 6, 10, 14, 18, 22]):
        stream_id, zone_id = (STREAM_A, ZONE_A) if i % 2 == 0 else (STREAM_B, ZONE_B)
        visit_id = f"cardinal-{PRIOR_YEAR}-{i}"
        _add_visit(repository, visit_id=visit_id, at=datetime(PRIOR_YEAR, 9, day, 9, tzinfo=UTC), stream_id=stream_id, zone_id=zone_id)
        _confirm(repository, visit_id=visit_id, label="northern_cardinal")

    # September 2025: Eastern Bluebird first observed the 25th, with real
    # lead-in coverage before it (comfortably clears the 5-usable-day floor).
    for i, day in enumerate([25, 26, 27]):
        visit_id = f"bluebird-{PRIOR_YEAR}-{i}"
        _add_visit(repository, visit_id=visit_id, at=datetime(PRIOR_YEAR, 9, day, 8, tzinfo=UTC), stream_id=STREAM_A, zone_id=ZONE_A)
        _confirm(repository, visit_id=visit_id, label="eastern_bluebird")

    # September 2025: one Visit initially (incorrectly) reviewed as a
    # House Finch -- corrected to Carolina Wren in Act 3, below.
    _add_visit(repository, visit_id="reclassified-2025", at=datetime(PRIOR_YEAR, 9, 12, 11, tzinfo=UTC), stream_id=STREAM_B, zone_id=ZONE_B)
    _confirm(repository, visit_id="reclassified-2025", label="house_finch")

    # September 2026: Cardinal genuinely higher activity (16 of 30 days).
    for i, day in enumerate(range(1, 17)):
        stream_id, zone_id = (STREAM_A, ZONE_A) if i % 2 == 0 else (STREAM_B, ZONE_B)
        visit_id = f"cardinal-{CURRENT_YEAR}-{i}"
        _add_visit(repository, visit_id=visit_id, at=datetime(CURRENT_YEAR, 9, day, 9, tzinfo=UTC), stream_id=stream_id, zone_id=zone_id)
        _confirm(repository, visit_id=visit_id, label="northern_cardinal")

    # September 2026: Eastern Bluebird first observed materially earlier
    # (the 8th, with 7 real lead-in usable days -- still clears the floor).
    for i, day in enumerate([8, 12, 16, 20]):
        visit_id = f"bluebird-{CURRENT_YEAR}-{i}"
        _add_visit(repository, visit_id=visit_id, at=datetime(CURRENT_YEAR, 9, day, 8, tzinfo=UTC), stream_id=STREAM_A, zone_id=ZONE_A)
        _confirm(repository, visit_id=visit_id, label="eastern_bluebird")

    # September 2026: Carolina Wren, real and well-evidenced (10 of 30
    # days), with *zero* 2025 presence so far -- set up so Act 4's
    # correction (reclassifying a 2025 House Finch Visit to Carolina Wren)
    # has a precise, directly observable effect on this exact taxon's own
    # prior-period presence count, not a vacuous one.
    for i, day in enumerate([1, 3, 5, 7, 9, 11, 13, 15, 17, 19]):
        visit_id = f"wren-{CURRENT_YEAR}-{i}"
        _add_visit(repository, visit_id=visit_id, at=datetime(CURRENT_YEAR, 9, day, 15, tzinfo=UTC), stream_id=STREAM_A, zone_id=ZONE_A)
        _confirm(repository, visit_id=visit_id, label="carolina_wren")

    # September 2026: one real cross-camera associated encounter -- the
    # same bird, seen by both cameras seconds apart at the same Area. Must
    # count once in the Place-level total, not twice.
    _add_visit(repository, visit_id="dup-a", at=datetime(CURRENT_YEAR, 9, 28, 14, 0, 0, tzinfo=UTC), stream_id=STREAM_A, zone_id=ZONE_A)
    _confirm(repository, visit_id="dup-a", label="blue_jay")
    _add_visit(repository, visit_id="dup-b", at=datetime(CURRENT_YEAR, 9, 28, 14, 0, 3, tzinfo=UTC), stream_id=STREAM_B, zone_id=ZONE_B)
    _confirm(repository, visit_id="dup-b", label="blue_jay")
    with repository.session_factory() as session:
        with session.begin():
            session.add(CrossCameraVisitAssociationModel(
                id="scenario-cross-camera-association-1",
                primary_visit_id=min("dup-a", "dup-b"), secondary_visit_id=max("dup-a", "dup-b"),
                tier="associated", overlap_ms=0, gap_ms=3_000, spatial_signal="matching_area_name",
                multi_subject=False, engine_version="cross-camera-association-v1",
                created_at=datetime(CURRENT_YEAR, 9, 28, tzinfo=UTC), updated_at=datetime(CURRENT_YEAR, 9, 28, tzinfo=UTC),
            ))

    now = datetime(CURRENT_YEAR, 9, 30, 12, tzinfo=UTC)  # last day of the current period, so it resolves complete, and within any Story range ending Oct 1

    # ---- Act 2: the Place-level and species-level comparison -----------
    before_correction = repository.place_year_over_year_comparison(now=now, year=CURRENT_YEAR, month=9, local_timezone=UTC)

    assert before_correction.place.status == "comparable"
    assert before_correction.place.overall_activity == "higher"
    assert before_correction.place.current_period.usable_day_count == 30
    assert before_correction.place.prior_period.usable_day_count == 30

    # The cross-camera associated pair counts once: 16 Cardinal + 4
    # Bluebird + 10 Wren + 1 (deduplicated) Blue Jay = 31 confirmed
    # Visits, never 32.
    assert before_correction.place.current_period.confirmed_wildlife_visit_count == 16 + 4 + 10 + 1

    by_label = {entry.label: entry for entry in before_correction.notable_species_changes}
    assert by_label["northern_cardinal"].activity_direction == "higher"
    assert by_label["eastern_bluebird"].first_observed_timing_status == "comparable"
    assert by_label["eastern_bluebird"].first_observed_is_material is True
    assert by_label["eastern_bluebird"].first_observed_day_difference is not None
    assert by_label["eastern_bluebird"].first_observed_day_difference < 0  # earlier this year
    assert by_label["eastern_bluebird"].current_first_observed_date == date(CURRENT_YEAR, 9, 8)
    assert by_label["eastern_bluebird"].prior_first_observed_date == date(PRIOR_YEAR, 9, 25)

    # Carolina Wren is already real and well-evidenced from 2026 activity
    # alone (10 of 30 days vs. 0 of 30 a year ago) -- the *before*-correction
    # baseline this Act's own correction proof needs.
    wren_before = by_label["carolina_wren"]
    assert wren_before.activity_direction == "higher"
    assert wren_before.association is not None
    assert wren_before.association.presence_days_out_of_condition == 0

    # ---- Act 3: archive Back Yard -- history must remain reachable -----
    with repository.session_factory() as session:
        with session.begin():
            source = session.get(CameraSourceModel, SOURCE_B)
            assert source is not None
            source.status = "archived"

    after_archive = repository.place_year_over_year_comparison(now=now, year=CURRENT_YEAR, month=9, local_timezone=UTC)
    assert after_archive.place.status == "comparable"
    assert after_archive.place.overall_activity == "higher"
    # Identical facts to before archival -- Back Yard's own real history
    # (both years) remains fully counted, unlike Today/Bird Log's own
    # deliberate current-active-observatory default.
    assert after_archive.place.current_period.confirmed_wildlife_visit_count == (
        before_correction.place.current_period.confirmed_wildlife_visit_count
    )
    assert after_archive.place.prior_period.confirmed_wildlife_visit_count == (
        before_correction.place.prior_period.confirmed_wildlife_visit_count
    )

    # ---- Act 4: a Reviewed correction changes the very next read -------
    # Reclassify the one 2025 Visit originally (incorrectly) reviewed as
    # House Finch to Carolina Wren -- the same taxon already established as
    # real and well-evidenced in Act 2, so the effect is precise and
    # directly observable, not merely "some entry changed somewhere".
    _confirm(repository, visit_id="reclassified-2025", label="carolina_wren")

    after_correction = repository.place_year_over_year_comparison(now=now, year=CURRENT_YEAR, month=9, local_timezone=UTC)
    wren_after = {e.label: e for e in after_correction.notable_species_changes}["carolina_wren"]
    assert wren_after.association is not None
    # The correction propagated on the very next read, with no
    # invalidation step: Carolina Wren's own prior-period presence moved
    # from 0 to exactly 1 -- the identical Visit, now counted under its
    # corrected label instead of its stale one.
    assert wren_after.association.presence_days_out_of_condition == 1
    assert wren_after.activity_direction == "higher"  # still higher: 10 vs. 1 of 30 days

    # ---- Act 5: the same story is calmly reflected in Place Story -------
    story = repository.place_story(
        start_at=datetime(CURRENT_YEAR, 9, 1, tzinfo=UTC),
        end_at=datetime(CURRENT_YEAR, 10, 1, tzinfo=UTC),
        now=now,
        local_timezone=UTC,
    )
    yoy_story_entries = [e for e in story.entries if e.kind == "year_over_year"]
    assert len(yoy_story_entries) >= 1
    for entry in yoy_story_entries:
        assert entry.information_class == "inferred"
        assert entry.group == "context"
        summary_lower = entry.summary.lower()
        for forbidden in ("caused", "led to", "resulted in", "because of", "drove", "due to", "arrived", "population"):
            assert forbidden not in summary_lower, f"{forbidden!r} found in Story summary: {entry.summary}"
    # Bounded, not a wall of every species -- at most the Place insight plus
    # the same small notable-species set the API surfaces.
    assert len(yoy_story_entries) <= 1 + len(after_correction.notable_species_changes)
