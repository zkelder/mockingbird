"""Multi-Camera Place Experience v2 -- Phase 39: one real, executable,
product-shaped scenario proving several cameras around one Place still add
up to ONE coherent observatory, not three separate camera apps. Follows
this codebase's own established convention for a milestone's capstone
integration proof (Ecological Interoperability's 12-Visit scenario, Calm
Attention's Monday-Sunday quiet-week test): real seeded SQLite state, the
same public repository methods a real API request would call, no mocking
of product logic.

Scenario (per the milestone's own Phase 39 brief):
  Camera A -- "Camera 1", later renamed "Front Feeder": busy, several
    confirmed Visits, including one that overlaps a Camera B encounter of
    the same species (a real, directly-seeded `CrossCameraVisitAssociation
    Model` "associated" row -- the already-accepted cross-camera engine
    from Camera/Source + Multi-Camera Maturity v1, reused unmodified, not
    rebuilt; see docs/camera-source-multi-camera-maturity-v1-contract.md).
  Camera B -- "Back Yard": lower but genuinely diverse activity (a non-bird
    wildlife Visit plus the overlapping cardinal above); archived partway
    through the scenario, after its Visits already happened.
  Camera C -- "Bird Bath": one early confirmed Visit, then no further
    activity -- a quieter, lower-yield camera, not archived.

Exercises: Today (`place_activity_report`, including the new per-camera
`activity_by_source` breakdown and cross-camera dedup), Bird Log overview
and per-species drilldown (including the new explicit-camera-filter
archived-history reach), Place Story (Place-level first-seen semantics,
not per-camera), Biodiversity (deliberately current-active-only, per its
own docstring), the camera roster (rename/archive coherence), and a
reviewed-truth correction propagating everywhere.

Deliberately NOT exercised here (out of this scenario's own bounded
scope, covered elsewhere or explicitly deferred -- see the milestone
report's "Remaining major PRODUCT opportunities"): live Camera Node
disconnect/reconnect state-machine transitions (that is an engine_runtime
concern, exercised in tests/test_engine_runtime.py and this milestone's own
tests/test_multi_camera_concurrent_runtime.py, not a static-fixture
concern); Place Feature multi-camera linking (deliberately not built this
pass -- the existing single-Source/Zone Feature association already covers
one Feature tied to one camera, exercised at the end of this file); mobile
viewport rendering (a Playwright/frontend concern, exercised separately in
e2e specs, not this backend-only repository-level test).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from mockingbird.api.schemas import (
    CameraSourceUpdate,
    CurrentUser,
    PlaceActivityReportRequest,
    PlaceFeatureCreate,
    ReviewCorrectionCreate,
    UserRole,
    VisitReviewRevisionCreate,
    WildlifeJournalHistoryRequest,
    WildlifeJournalOverviewRequest,
)
from mockingbird.repository.product_repository import (
    CrossCameraVisitAssociationModel,
    ProductRepository,
)
from mockingbird.api.main import configure_repository
from mockingbird.storage.models import CameraSourceModel, EventModel, StreamModel, VisitModel, ZoneModel

SOURCE_A, STREAM_A, ZONE_A = "source-scenario-a", "stream-scenario-a", "zone-scenario-a"
SOURCE_B, STREAM_B, ZONE_B = "source-scenario-b", "stream-scenario-b", "zone-scenario-b"
SOURCE_C, STREAM_C, ZONE_C = "source-scenario-c", "stream-scenario-c", "zone-scenario-c"
PERIOD_START = datetime(2026, 8, 20, 6, 0, tzinfo=UTC)
PERIOD_END = datetime(2026, 8, 20, 20, 0, tzinfo=UTC)


@pytest.fixture
def repository(tmp_path: Path) -> ProductRepository:
    repo = ProductRepository(db_url=f"sqlite:///{tmp_path / 'mockingbird.sqlite3'}", media_root=tmp_path / "media")
    configure_repository(repo)
    with repo.session_factory() as session:
        with session.begin():
            # Archive the auto-seeded demo Source (matching test_wildlife_
            # journal.py/test_zone_insights.py's own established fixture
            # convention) so this scenario's "exactly these 3 cameras"
            # assertions are not polluted by an unrelated 4th, demo-only
            # Source.
            demo = session.get(CameraSourceModel, "source-backyard-demo")
            if demo is not None:
                demo.status = "archived"
            for source_id, stream_id, zone_id, name, area, zone_type in (
                (SOURCE_A, STREAM_A, ZONE_A, "Camera 1", "Feeder", "feeder"),
                (SOURCE_B, STREAM_B, ZONE_B, "Back Yard", "Feeder", "yard"),
                (SOURCE_C, STREAM_C, ZONE_C, "Bird Bath", "Bird Bath", "birdbath"),
            ):
                session.add(CameraSourceModel(
                    id=source_id, name=name, kind="manual_upload", status="connected",
                    description="Multi-Camera Place Experience v2 scenario fixture.",
                ))
                session.add(StreamModel(
                    id=stream_id, source_id=source_id, name=name,
                    description="Multi-Camera Place Experience v2 scenario fixture.", is_live=False,
                ))
                session.add(ZoneModel(
                    id=zone_id, stream_id=stream_id, name=area, zone_type=zone_type,
                    polygon_json="[]", is_active=True, monitoring_policy_json=None,
                ))
    yield repo
    configure_repository(None)
    repo.close()


def _add_visit(
    repository: ProductRepository, *, visit_id: str, stream_id: str, zone_id: str, at: datetime,
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


def test_one_place_several_cameras_stays_one_coherent_observatory(repository: ProductRepository) -> None:
    # ---- Act 1: ordinary activity across three cameras ---------------
    # Camera A: busy, four confirmed Visits.
    _add_visit(repository, visit_id="a-cardinal-1", stream_id=STREAM_A, zone_id=ZONE_A, at=PERIOD_START + timedelta(hours=1))
    _confirm(repository, visit_id="a-cardinal-1", label="northern_cardinal")
    _add_visit(repository, visit_id="a-jay", stream_id=STREAM_A, zone_id=ZONE_A, at=PERIOD_START + timedelta(hours=2))
    _confirm(repository, visit_id="a-jay", label="blue_jay")
    _add_visit(repository, visit_id="a-finch", stream_id=STREAM_A, zone_id=ZONE_A, at=PERIOD_START + timedelta(hours=3))
    _confirm(repository, visit_id="a-finch", label="house_finch")
    _add_visit(repository, visit_id="a-cardinal-2", stream_id=STREAM_A, zone_id=ZONE_A, at=PERIOD_START + timedelta(hours=4))
    _confirm(repository, visit_id="a-cardinal-2", label="northern_cardinal")

    # Camera B: lower but genuinely diverse -- a non-bird wildlife Visit,
    # plus a cardinal Visit that overlaps Camera A's own first cardinal
    # (same Area name "Feeder", close in time) -- a real apparent
    # cross-camera encounter.
    _add_visit(repository, visit_id="b-squirrel", stream_id=STREAM_B, zone_id=ZONE_B, at=PERIOD_START + timedelta(hours=5))
    _confirm(repository, visit_id="b-squirrel", label="squirrel")
    _add_visit(
        repository, visit_id="b-cardinal-overlap", stream_id=STREAM_B, zone_id=ZONE_B,
        at=PERIOD_START + timedelta(hours=1, seconds=4),
    )
    _confirm(repository, visit_id="b-cardinal-overlap", label="northern_cardinal")

    # Camera C: one early confirmed Visit, then quiet for the rest of the
    # period -- a real, lower-yield camera, not archived.
    _add_visit(repository, visit_id="c-junco", stream_id=STREAM_C, zone_id=ZONE_C, at=PERIOD_START + timedelta(minutes=30))
    _confirm(repository, visit_id="c-junco", label="carolina_wren")

    # The cross-camera association engine (Camera/Source + Multi-Camera
    # Maturity v1) is reused unmodified, not rebuilt: this directly seeds
    # its own output shape exactly like test_place_activity_report_
    # repository.py's own established precedent for this same purpose,
    # standing in for the live admission-time reconciliation this
    # scenario's own hand-seeded Visits never go through.
    with repository.session_factory() as session:
        with session.begin():
            session.add(CrossCameraVisitAssociationModel(
                id="scenario-cross-camera-association-1",
                primary_visit_id=min("a-cardinal-1", "b-cardinal-overlap"),
                secondary_visit_id=max("a-cardinal-1", "b-cardinal-overlap"),
                tier="associated", overlap_ms=0, gap_ms=4_000, spatial_signal="matching_area_name",
                multi_subject=False, engine_version="cross-camera-association-v1",
                created_at=PERIOD_START, updated_at=PERIOD_START,
            ))

    # ---- Today: one coherent Place-wide report, camera-aware ----------
    today = repository.place_activity_report(
        PlaceActivityReportRequest(start_at=PERIOD_START, end_at=PERIOD_END)
    )
    cardinal = next(t for t in today.taxa if t.label == "northern_cardinal")
    assert cardinal.confirmed_visit_count == 2, (
        "3 real cardinal Visits (a-cardinal-1, a-cardinal-2, b-cardinal-overlap) -- "
        "a-cardinal-1/b-cardinal-overlap are a real, confirmed cross-camera 'associated' "
        "pair (one real encounter observed by two cameras) and must count once, leaving "
        "a-cardinal-2 as the only other independent cardinal Visit: 2 total, never 3."
    )
    # Per-camera breakdown (Multi-Camera Place Experience v2's own new
    # surfacing -- see TodayReportPanel.tsx's "By camera" section):
    # exactly the 3 real cameras, never duplicated, never a raw UUID label.
    source_names = {entry.source_name for entry in today.activity_by_source}
    assert source_names == {"Camera 1", "Back Yard", "Bird Bath"}
    by_name = {entry.source_name: entry for entry in today.activity_by_source}
    assert by_name["Camera 1"].confirmed_wildlife_visit_count == 4
    # Back Yard's own raw count is 1, not 2: the cross-camera exclusion-set
    # helper (`_associated_visit_ids_to_exclude_from_counting`) drops the
    # lexicographically-larger visit_id of an "associated" pair from the
    # counted set entirely -- "b-cardinal-overlap" > "a-cardinal-1", so that
    # one real, shared encounter's credit lands on Camera A's surviving
    # a-cardinal-1, leaving Back Yard's own per-camera count reflecting only
    # its unshared activity (b-squirrel). This is the honest, deterministic,
    # already-accepted "one real encounter, one credit" rule -- Place-wide
    # totals (`cardinal.confirmed_visit_count == 2`, above) stay correct
    # either way; per-camera attribution of a *shared* encounter is
    # necessarily a one-or-the-other choice, never both.
    assert by_name["Back Yard"].confirmed_wildlife_visit_count == 1
    assert by_name["Bird Bath"].confirmed_wildlife_visit_count == 1

    # ---- Bird Log: default is current-active, explicit filter reaches
    #      any one camera's own history -----------------------------
    overview_default = repository.wildlife_journal_overview(WildlifeJournalOverviewRequest())
    assert {row.label for row in overview_default.labels} == {
        "northern_cardinal", "blue_jay", "house_finch", "squirrel", "carolina_wren",
    }
    overview_camera_b_only = repository.wildlife_journal_overview(
        WildlifeJournalOverviewRequest(stream_id=STREAM_B)
    )
    assert {row.label for row in overview_camera_b_only.labels} == {"northern_cardinal", "squirrel"}

    # ---- Place Story stays Place-level: one first-seen cardinal event,
    #      never two just because two cameras saw it -------------------
    story = repository.place_story(start_at=PERIOD_START - timedelta(days=1), end_at=PERIOD_END)
    cardinal_first_seen = [e for e in story.entries if e.kind == "first_seen" and e.taxon_label == "northern_cardinal"]
    assert len(cardinal_first_seen) == 1, (
        "Camera B seeing a species Camera A already saw the same period is not a "
        "second Place-wide first-seen event (see product-doctrine.md's Place "
        "Intelligence semantics)."
    )

    # ---- Act 2: rename Camera A, archive Camera B ----------------------
    renamed = repository.update_camera_source(SOURCE_A, CameraSourceUpdate(name="Front Feeder"))
    assert renamed is not None and renamed.source.name == "Front Feeder"
    archived = repository.update_camera_source(SOURCE_B, CameraSourceUpdate(archived=True))
    assert archived is not None and archived.source.status.value == "archived"

    # ---- Today after rename/archive: rename is fully retroactive (no
    #      duplicate camera); the *unfiltered* default correctly goes quiet
    #      on the now-archived Camera B (the same current-active-
    #      observatory default every discovery surface uses -- see
    #      test_place_change_summary_repository.py's own pre-existing
    #      "archived stream confirmations are excluded" precedent), but its
    #      real past-period activity remains reachable by explicit
    #      `source_ids` -- archival never erases it, it just stops
    #      appearing in the default view ------------------------------
    today_after = repository.place_activity_report(
        PlaceActivityReportRequest(start_at=PERIOD_START, end_at=PERIOD_END)
    )
    source_names_after = {entry.source_name for entry in today_after.activity_by_source}
    assert source_names_after == {"Front Feeder", "Bird Bath"}, (
        "Renaming Camera A must not spawn a duplicate 'Camera 1' entry; the "
        "unfiltered default correctly drops the now-archived Back Yard camera."
    )
    cardinal_after = next(t for t in today_after.taxa if t.label == "northern_cardinal")
    assert cardinal_after.confirmed_visit_count == 2, (
        "Front Feeder's own 2 cardinals (a-cardinal-1, a-cardinal-2) -- Back Yard's "
        "b-cardinal-overlap is correctly out of the unfiltered default's scope now."
    )

    today_filtered_to_archived = repository.place_activity_report(
        PlaceActivityReportRequest(start_at=PERIOD_START, end_at=PERIOD_END, source_ids=[SOURCE_B])
    )
    assert {t.label for t in today_filtered_to_archived.taxa} == {"northern_cardinal", "squirrel"}, (
        "Explicitly naming the archived Back Yard camera still reaches its real "
        "activity from this same report period -- archival preserves history, it "
        "just stops appearing in the unfiltered default (camera-source-experience-"
        "v1-report.md: 'archive-only history preservation is correct')."
    )

    # ---- Bird Log after archival: default view goes quiet on Camera B
    #      (current-active-observatory framing, deliberate -- see
    #      test_wildlife_journal.py's own "archived-cardinal" precedent),
    #      but its real history remains reachable by explicit camera
    #      filter -- the actual gap this milestone closed -------------
    overview_after_archive = repository.wildlife_journal_overview(WildlifeJournalOverviewRequest())
    assert "squirrel" not in {row.label for row in overview_after_archive.labels}
    squirrel_default = repository.wildlife_journal_history("squirrel", WildlifeJournalHistoryRequest())
    assert squirrel_default is None or squirrel_default.observation_count == 0
    squirrel_via_camera_filter = repository.wildlife_journal_history(
        "squirrel", WildlifeJournalHistoryRequest(stream_id=STREAM_B)
    )
    assert squirrel_via_camera_filter is not None
    assert squirrel_via_camera_filter.observation_count == 1, (
        "Back Yard's own real, reviewed squirrel sighting must remain reachable "
        "by explicitly selecting that camera, even after archival."
    )

    # ---- Biodiversity stays deliberately current-active-only (its own
    #      docstring's contract, mirroring Bird Log's default) -- a
    #      species only ever seen on the now-archived camera correctly
    #      drops out of the *current* Place biodiversity headline, the
    #      same considered distinction Bird Log's explicit filter exists
    #      to bridge -----------------------------------------------------
    biodiversity = repository.place_biodiversity_summary()
    current_labels = {taxon.label for taxon in biodiversity.taxa}
    assert "squirrel" not in current_labels, (
        "Biodiversity is 'as of right now' by design (mirrors Bird Log's own "
        "unfiltered default) -- Back Yard's archival correctly removes its "
        "sole species from the *current* headline; its real history is not "
        "lost (see the Bird Log camera-filter proof above), just not part of "
        "'what does my Place currently host.'"
    )
    assert "northern_cardinal" in current_labels  # still seen on the active Front Feeder camera

    # ---- Act 3: a reviewed correction propagates everywhere -----------
    # `a-finch` is already reviewed (as "house_finch") -- correcting an
    # existing review is `revise_visit_review`, not `create_review_label`
    # (the initial-review-only path; see its own docstring).
    with repository.session_factory() as session:
        state_token = repository._review_state_token(session, "visit", "a-finch")
    repository.revise_visit_review(
        "a-finch",
        VisitReviewRevisionCreate(
            label="eastern_bluebird", expected_state_token=state_token,
            idempotency_key="scenario-correct-a-finch", review_origin="human",
        ),
    )
    overview_final = repository.wildlife_journal_overview(WildlifeJournalOverviewRequest())
    final_labels = {row.label for row in overview_final.labels}
    assert "house_finch" not in final_labels
    assert "eastern_bluebird" in final_labels
    biodiversity_final = repository.place_biodiversity_summary()
    assert "eastern_bluebird" in {taxon.label for taxon in biodiversity_final.taxa}

    # ---- Camera roster stays coherent: 3 real cameras, correct
    #      name/archived state, no raw UUIDs, no duplicates -------------
    health = repository.list_stream_camera_health()
    health_by_stream = {item.stream_id: item for item in health}
    assert health_by_stream[STREAM_A].source_name == "Front Feeder"
    assert health_by_stream[STREAM_B].source_name == "Back Yard"
    assert health_by_stream[STREAM_C].source_name == "Bird Bath"

    # ---- One Place Feature, tied to the still-active Front Feeder
    #      camera, unaffected by everything above ------------------------
    feature = repository.add_place_feature(
        PlaceFeatureCreate(feature_type="feeder", name="Sunflower Feeder", zone_id=ZONE_A),
        acting_user=CurrentUser(
            id="user-scenario-admin", display_name="Scenario Admin", login_identity="scenario-admin",
            role=UserRole.administrator, enabled=True,
        ),
    )
    assert feature.zone_id == ZONE_A
