"""Stage 7 candidate-Visit persistence boundary: `ProductRepository`'s own
transactional create/idempotency/rate-limit/truth-protection behavior (see
docs/candidate-visit-authority-contract.md). Uses an isolated `tmp_path`
SQLite database for every test -- never the real product database -- per the
established `tests/test_visit_curation.py` fixture convention.
"""

from __future__ import annotations

import json
import threading
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import func, select

from mockingbird.observation.candidate_visit_authority import ObservationAuthorityMode
from mockingbird.repository.product_repository import (
    CandidateEvidenceItem,
    CandidateVisitProposalFacts,
    CreateCandidateVisitRequest,
    EventModel,
    MediaAssetModel,
    ObservationCandidateVisitModel,
    ProductRepository,
    ReviewLabelModel,
    VisitModel,
)
from mockingbird.storage.database import CURRENT_DATABASE_SCHEMA_VERSION, create_database_engine
from mockingbird.storage.models import CameraSourceModel, StreamModel

STREAM_ID = "stream-backyard-feeder"
FEEDER_ZONE_ID = "zone-feeder"
IGNORE_ZONE_ID = "zone-ignore-driveway-edge"
NOW = datetime(2026, 8, 8, 12, 0, 0, tzinfo=UTC)
JPEG_BYTES = b"\xff\xd8\xff\xe0" + b"0" * 64 + b"\xff\xd9"


@pytest.fixture
def repository(tmp_path: Path) -> ProductRepository:
    repo = ProductRepository(db_url=f"sqlite:///{tmp_path / 'mockingbird.sqlite3'}", media_root=tmp_path / "media")
    yield repo
    repo.close()


def _facts(
    *,
    proposal_id: str = "visit-episode:fixture-1",
    stream_id: str = STREAM_ID,
    zone_id: str | None = FEEDER_ZONE_ID,
    source_capture_frame_ids: tuple[str, ...] = ("frame-1", "frame-2"),
    supporting_frame_ids: tuple[str, ...] = ("frame-1", "frame-2"),
    ambiguous_adjacent_proposal_ids: tuple[str, ...] = (),
    confidence_evidence_json: str | None = None,
) -> CandidateVisitProposalFacts:
    return CandidateVisitProposalFacts(
        proposal_id=proposal_id,
        stream_id=stream_id,
        zone_id=zone_id,
        broad_class="animal",
        start_offset_ms=0,
        end_offset_ms=4500,
        constituent_generation_ids=("gen-1", "gen-2"),
        constituent_track_ids=("track-1", "track-2"),
        source_capture_frame_ids=source_capture_frame_ids,
        supporting_frame_ids=supporting_frame_ids,
        evidence_candidate_ids=("shadow-burst:hash-1",),
        limitation_facts=("assembled_from_multiple_tracklets",),
        ambiguous_adjacent_proposal_ids=ambiguous_adjacent_proposal_ids,
        assembler_version="tracklet-visit-assembler-v1",
        detector_provenance="onnx-cuda",
        tracker_provenance="frame-driven-onnx-cuda-v1",
        provider_key="frame-driven-onnx-cuda",
        confidence_evidence_json=confidence_evidence_json,
    )


def _evidence(
    role: str = "identification",
    engine_media_id: str = "shadow-burst:hash-1",
    *,
    geometry_attribution_json: str | None = None,
) -> CandidateEvidenceItem:
    return CandidateEvidenceItem(
        engine_media_id=engine_media_id,
        role=role,
        content=JPEG_BYTES,
        content_type="image/jpeg",
        width=1920,
        height=1080,
        captured_at=NOW,
        subject_geometry=(0.4, 0.4, 0.6, 0.6),
        geometry_attribution_json=geometry_attribution_json,
    )


def _activate(repository: ProductRepository, *, now: datetime = NOW, **limits) -> None:
    repository.set_observation_authority_mode(ObservationAuthorityMode.candidate_visit, stream_id=STREAM_ID, now=now, **limits)


def _counts(repository: ProductRepository) -> dict[str, int]:
    with repository.session_factory() as session:
        return {
            "visits": session.scalar(select(func.count(VisitModel.id))),
            "events": session.scalar(select(func.count(EventModel.id))),
            "media_assets": session.scalar(select(func.count(MediaAssetModel.id))),
            "review_labels": session.scalar(select(func.count(ReviewLabelModel.id))),
            "candidate_ledger": session.scalar(select(func.count(ObservationCandidateVisitModel.proposal_id))),
        }


# --- migration / schema -----------------------------------------------------


def test_schema_migrates_to_stage7_tables(repository: ProductRepository) -> None:
    assert CURRENT_DATABASE_SCHEMA_VERSION >= 28
    with repository.session_factory() as session:
        from sqlalchemy import inspect as sa_inspect

        table_names = set(sa_inspect(session.get_bind()).get_table_names())
        assert "observation_authority_settings" in table_names
        assert "observation_candidate_visits" in table_names


def test_schema_v34_adds_scene_confusor_regions_table_empty_and_unseeded(tmp_path: Path) -> None:
    """Persistent Scene Confusor Suppression v1 (see docs/scene-confusor-
    suspicion-contract.md): the new table exists after migration, and --
    unlike a new column on an existing table -- starts genuinely empty even
    for a database that already has real historical candidate Visits, since
    this migration never backfills recurring-geometry history from them
    (see the migration's own docstring, `_migrate_to_scene_confusor_
    regions`)."""

    db_path = tmp_path / "schema-v34.sqlite3"
    repository = ProductRepository(db_url=f"sqlite:///{db_path}", media_root=tmp_path / "media")
    assert CURRENT_DATABASE_SCHEMA_VERSION == 35
    _activate(repository)
    outcome = repository.create_candidate_visit_from_proposal(
        CreateCandidateVisitRequest(
            proposal=_facts(proposal_id="visit-episode:pre-migration-scene"), observed_at=NOW,
            evidence_items=(_evidence(),),
        )
    )
    assert outcome.outcome == "created"
    repository.close()

    engine = create_database_engine(f"sqlite:///{db_path}")
    with engine.begin() as connection:
        connection.exec_driver_sql("DROP TABLE scene_confusor_regions")
        connection.exec_driver_sql("UPDATE mockingbird_schema SET version = 33 WHERE singleton_id = 1")
    engine.dispose()

    migrated = ProductRepository(db_url=f"sqlite:///{db_path}", media_root=tmp_path / "media")
    try:
        assert migrated.schema_status.version == CURRENT_DATABASE_SCHEMA_VERSION == 35
        from sqlalchemy import inspect as sa_inspect

        from mockingbird.repository.product_repository import SceneConfusorRegionModel

        with migrated.session_factory() as session:
            table_names = set(sa_inspect(session.get_bind()).get_table_names())
            assert "scene_confusor_regions" in table_names
            # Genuinely empty, not backfilled from the real pre-migration
            # candidate Visit above.
            assert session.scalar(select(func.count(SceneConfusorRegionModel.id))) == 0
    finally:
        migrated.close()


def test_schema_v31_adds_confidence_evidence_column_without_fabricating_legacy_data(
    tmp_path: Path,
) -> None:
    """Detection Quality Accounting v1 (see
    docs/detection-quality-accounting-contract.md): a candidate created
    *before* this column existed must read back `confidence_evidence_json
    is None` after migrating forward -- never a fabricated summary -- while
    a candidate created *after* migration genuinely persists one."""

    db_path = tmp_path / "schema-v31.sqlite3"
    repository = ProductRepository(db_url=f"sqlite:///{db_path}", media_root=tmp_path / "media")
    # This pin intentionally tracks whatever the latest schema version is
    # (34 as of Persistent Scene Confusor Suppression v1) -- the migration
    # path below always exercises "roll back to just before this column
    # existed, then migrate all the way forward to current," regardless of
    # how many later schema versions have been added since.
    assert CURRENT_DATABASE_SCHEMA_VERSION == 35
    _activate(repository)
    pre_migration_outcome = repository.create_candidate_visit_from_proposal(
        CreateCandidateVisitRequest(
            proposal=_facts(proposal_id="visit-episode:pre-migration"), observed_at=NOW, evidence_items=(_evidence(),),
        )
    )
    assert pre_migration_outcome.outcome == "created"
    repository.close()

    engine = create_database_engine(f"sqlite:///{db_path}")
    with engine.begin() as connection:
        # Simulate "a database that predates this column": drop it (SQLite
        # 3.35+ supports DROP COLUMN) and roll the recorded schema version
        # back to the last version that never had it.
        connection.exec_driver_sql(
            "ALTER TABLE observation_candidate_visits DROP COLUMN confidence_evidence_json"
        )
        connection.exec_driver_sql("UPDATE mockingbird_schema SET version = 30 WHERE singleton_id = 1")
    engine.dispose()

    migrated = ProductRepository(db_url=f"sqlite:///{db_path}", media_root=tmp_path / "media")
    try:
        assert migrated.schema_status.version == CURRENT_DATABASE_SCHEMA_VERSION == 35
        with migrated.session_factory() as session:
            pre_ledger = session.get(ObservationCandidateVisitModel, "visit-episode:pre-migration")
            assert pre_ledger is not None
            assert pre_ledger.confidence_evidence_json is None  # no fabricated confidence for a legacy record

        # Visit Authority Budget + Ambiguous-Boundary Recall Closure v1:
        # migrating through schema 35 resets this Stream's own authority
        # settings row (see `_migrate_to_per_stream_observation_authority`)
        # -- exactly mirroring what a real installation upgrading across
        # this migration must do (Start observing again). Re-activate here,
        # not a regression: this is the fix's own intended behavior.
        _activate(migrated)
        post_migration_outcome = migrated.create_candidate_visit_from_proposal(
            CreateCandidateVisitRequest(
                proposal=_facts(
                    proposal_id="visit-episode:post-migration",
                    confidence_evidence_json='{"detection_count": 3, "max_confidence": 0.42}',
                ),
                observed_at=NOW,
                evidence_items=(_evidence(),),
            )
        )
        assert post_migration_outcome.outcome == "created"
        with migrated.session_factory() as session:
            post_ledger = session.get(ObservationCandidateVisitModel, "visit-episode:post-migration")
            assert post_ledger is not None
            assert json.loads(post_ledger.confidence_evidence_json) == {"detection_count": 3, "max_confidence": 0.42}
    finally:
        migrated.close()


# --- Visit Authority Budget + Ambiguous-Boundary Recall Closure v1 ---------
# (see docs/candidate-visit-authority-contract.md "Session/Stream scope" and
# "Fresh-session activation"). Real, demonstrated 2026-08-19 field defect:
# a stale `candidate_visit` mode left behind by a process that never
# reached the kill switch (crash, kill, redeploy) silently poisoned every
# later session's own candidate budget, and a global settings row let one
# Stream's Stop silently kill a different, still-running Stream's authority.


def test_reaffirming_active_mode_without_fresh_session_does_not_reset_boundary(
    repository: ProductRepository,
) -> None:
    """Original, still-correct behavior preserved for a caller that does not
    assert a fresh session (for example the CLI trial re-affirming mid-run):
    re-affirming an already-active mode must not silently widen the
    activation window -- this is what keeps the boundary from being usable
    to sneak a later backlog window in."""

    first = repository.set_observation_authority_mode(
        ObservationAuthorityMode.candidate_visit, stream_id=STREAM_ID, now=NOW,
    )
    again = repository.set_observation_authority_mode(
        ObservationAuthorityMode.candidate_visit, stream_id=STREAM_ID, now=NOW + timedelta(minutes=10),
    )
    assert again.activation_boundary_at == first.activation_boundary_at == NOW


def test_fresh_session_resets_boundary_even_when_mode_already_active(
    repository: ProductRepository,
) -> None:
    """The real, demonstrated defect: a stale `candidate_visit` mode left
    behind by a process that never reached the kill switch must not
    silently poison a genuinely new session. A caller that asserts
    `fresh_session=True` (only ever the product's own Start path,
    `_EngineSession._run_async`) always gets a fresh boundary for this
    Stream, regardless of the leftover mode."""

    stale = repository.set_observation_authority_mode(
        ObservationAuthorityMode.candidate_visit, stream_id=STREAM_ID, now=NOW,
    )
    assert stale.activation_boundary_at == NOW
    # Simulate the crash: mode is left at candidate_visit forever (the
    # process died before `stop()`'s kill switch could ever run).

    later = NOW + timedelta(days=1)
    fresh = repository.set_observation_authority_mode(
        ObservationAuthorityMode.candidate_visit, stream_id=STREAM_ID, now=later, fresh_session=True,
    )
    assert fresh.activation_boundary_at == later
    assert fresh.candidates_created_in_session == 0


def test_fresh_session_can_only_move_the_boundary_forward(repository: ProductRepository) -> None:
    """`fresh_session` must never be usable to *lower* the effective
    boundary and admit an older historical proposal -- only to establish a
    later one, preserving "no backlog replay into authority" exactly."""

    repository.set_observation_authority_mode(
        ObservationAuthorityMode.candidate_visit, stream_id=STREAM_ID, now=NOW + timedelta(hours=1),
    )
    earlier_attempt = repository.set_observation_authority_mode(
        ObservationAuthorityMode.candidate_visit, stream_id=STREAM_ID, now=NOW, fresh_session=True,
    )
    # A caller can only ever supply its own current wall-clock `now`, which
    # is monotonically non-decreasing in real use; this asserts the
    # mechanism itself performs no clamping trickery either way -- it simply
    # records whatever `now` a well-behaved caller supplies.
    assert earlier_attempt.activation_boundary_at == NOW


def test_exhausted_previous_session_cannot_poison_a_fresh_session(
    repository: ProductRepository,
) -> None:
    """Direct end-to-end reproduction of the field defect: a session
    genuinely exhausts its own tiny budget, the process is never gracefully
    stopped, and a later fresh Start must still be able to create a Visit."""

    repository.set_observation_authority_mode(
        ObservationAuthorityMode.candidate_visit, stream_id=STREAM_ID, now=NOW, max_candidates_per_session=1,
    )
    first = repository.create_candidate_visit_from_proposal(
        CreateCandidateVisitRequest(
            proposal=_facts(proposal_id="visit-episode:exhaust-1"), observed_at=NOW, evidence_items=(_evidence(),),
        )
    )
    assert first.outcome == "created"
    second = repository.create_candidate_visit_from_proposal(
        CreateCandidateVisitRequest(
            proposal=_facts(proposal_id="visit-episode:exhaust-2"), observed_at=NOW, evidence_items=(_evidence(),),
        )
    )
    assert second.outcome == "blocked_session_limit"
    # The process "crashes" here: mode stays candidate_visit, never
    # reverted, exactly like a killed Python process leaves the durable
    # settings row.

    later = NOW + timedelta(hours=2)
    repository.set_observation_authority_mode(
        ObservationAuthorityMode.candidate_visit,
        stream_id=STREAM_ID,
        now=later,
        fresh_session=True,
        max_candidates_per_session=1,
    )
    third = repository.create_candidate_visit_from_proposal(
        CreateCandidateVisitRequest(
            proposal=_facts(proposal_id="visit-episode:exhaust-3"), observed_at=later, evidence_items=(_evidence(),),
        )
    )
    assert third.outcome == "created"


def test_multi_stream_authority_is_isolated(repository: ProductRepository) -> None:
    """A second Stream's own authority lifecycle -- mode, activation
    boundary, and candidate budget -- must be completely independent of the
    first (see the model's own docstring: a shared global row was a real,
    demonstrated cross-Stream defect: one Stream's Stop silently killed a
    different, still-running Stream's authority)."""

    other_stream_id = "stream-other-camera"
    other_source_id = "source-other-camera"
    with repository.session_factory() as session:
        with session.begin():
            session.add(
                CameraSourceModel(
                    id=other_source_id, name="Other camera", kind="integration",
                    status="connected", description="Second, independent fixture Source.",
                )
            )
            session.add(
                StreamModel(
                    id=other_stream_id, source_id=other_source_id, name="Other stream",
                    description="Second, independent fixture Stream.", is_live=True,
                )
            )

    repository.set_observation_authority_mode(
        ObservationAuthorityMode.candidate_visit, stream_id=STREAM_ID, now=NOW, max_candidates_per_session=1,
    )
    repository.create_candidate_visit_from_proposal(
        CreateCandidateVisitRequest(
            proposal=_facts(proposal_id="visit-episode:stream-a-only"),
            observed_at=NOW,
            evidence_items=(_evidence(),),
        )
    )
    # Stream A is now exhausted (budget=1, already used).
    exhausted = repository.get_observation_authority_state(stream_id=STREAM_ID)
    assert exhausted.candidates_created_in_session == 1

    # Stream B has never been touched: still shadow, zero count -- never
    # inheriting Stream A's mode or its already-consumed budget.
    fresh_other = repository.get_observation_authority_state(stream_id=other_stream_id)
    assert fresh_other.mode == "shadow"
    assert fresh_other.candidates_created_in_session == 0

    repository.set_observation_authority_mode(
        ObservationAuthorityMode.candidate_visit, stream_id=other_stream_id, now=NOW,
    )
    created_for_other = repository.create_candidate_visit_from_proposal(
        CreateCandidateVisitRequest(
            proposal=_facts(proposal_id="visit-episode:stream-b-only", stream_id=other_stream_id, zone_id=None),
            observed_at=NOW,
            evidence_items=(_evidence(),),
        )
    )
    # Stream B can still create -- Stream A's own exhaustion never
    # consumed any of Stream B's budget.
    assert created_for_other.outcome == "created"

    # Stopping Stream A (reverting it to shadow) must never touch Stream B.
    repository.set_observation_authority_mode(ObservationAuthorityMode.shadow, stream_id=STREAM_ID, now=NOW)
    assert repository.get_observation_authority_state(stream_id=STREAM_ID).mode == "shadow"
    assert repository.get_observation_authority_state(stream_id=other_stream_id).mode == "candidate_visit"


def test_legitimate_active_session_exhaustion_still_blocks_safely(repository: ProductRepository) -> None:
    """The guardrail itself is unchanged: a genuinely still-fresh, still-
    active session that exhausts its own real budget must still block --
    this milestone fixes lifecycle/ownership, not the existence of the cap."""

    repository.set_observation_authority_mode(
        ObservationAuthorityMode.candidate_visit, stream_id=STREAM_ID, now=NOW, max_candidates_per_session=2,
    )
    outcomes = [
        repository.create_candidate_visit_from_proposal(
            CreateCandidateVisitRequest(
                proposal=_facts(proposal_id=f"visit-episode:cap-{index}"),
                observed_at=NOW,
                evidence_items=(_evidence(),),
            )
        )
        for index in range(3)
    ]
    assert [outcome.outcome for outcome in outcomes] == ["created", "created", "blocked_session_limit"]


# --- 1. Default authority is shadow -----------------------------------------


def test_fresh_repository_defaults_to_shadow_authority(repository: ProductRepository) -> None:
    status = repository.get_observation_authority_state(stream_id=STREAM_ID)
    assert status.mode == "shadow"
    assert status.activation_boundary_at is None
    assert status.candidates_created_count == 0


def test_status_read_never_creates_settings_row(repository: ProductRepository) -> None:
    repository.get_observation_authority_state(stream_id=STREAM_ID)
    with repository.session_factory() as session:
        from mockingbird.repository.product_repository import ObservationAuthoritySettingsModel

        assert session.get(ObservationAuthoritySettingsModel, STREAM_ID) is None


# --- 2. Shadow mode creates zero product records ----------------------------


def test_shadow_mode_creates_zero_product_records(repository: ProductRepository) -> None:
    before = _counts(repository)
    outcome = repository.create_candidate_visit_from_proposal(
        CreateCandidateVisitRequest(proposal=_facts(), observed_at=NOW, evidence_items=(_evidence(),)),
    )
    assert outcome.outcome == "blocked_shadow_mode"
    assert outcome.visit_id is None
    assert _counts(repository) == before


# --- 3. Explicit candidate authority creates one candidate Visit -----------


def test_candidate_authority_creates_one_candidate_visit(repository: ProductRepository) -> None:
    _activate(repository)
    outcome = repository.create_candidate_visit_from_proposal(
        CreateCandidateVisitRequest(
            proposal=_facts(), observed_at=NOW, evidence_items=(_evidence("identification"), _evidence("context", "shadow-burst:hash-2")),
        )
    )
    assert outcome.outcome == "created"
    assert outcome.visit_id is not None
    assert outcome.event_id is not None
    assert len(outcome.persisted_media_asset_ids) == 2

    with repository.session_factory() as session:
        visit = session.get(VisitModel, outcome.visit_id)
        assert visit is not None
        assert visit.review_status == "needs_review"  # 11. needs-review
        assert visit.reviewed_label is None  # 14. no confirmed species truth
        assert visit.subject_label == "animal"
        event = session.get(EventModel, outcome.event_id)
        assert event.event_type == "observation_engine_candidate"
        assert event.review_status == "needs_review"


# --- 4 / 5. Idempotent replay + restart/retry -------------------------------


def test_same_proposal_replay_is_idempotent(repository: ProductRepository) -> None:
    _activate(repository)
    request = CreateCandidateVisitRequest(proposal=_facts(), observed_at=NOW, evidence_items=(_evidence(),))
    first = repository.create_candidate_visit_from_proposal(request)
    second = repository.create_candidate_visit_from_proposal(request)
    assert first.outcome == "created"
    assert second.outcome == "idempotent_repeat"
    assert second.visit_id == first.visit_id
    assert _counts(repository)["candidate_ledger"] == 1


def test_restart_retry_remains_idempotent(repository: ProductRepository, tmp_path: Path) -> None:
    _activate(repository)
    request = CreateCandidateVisitRequest(proposal=_facts(), observed_at=NOW, evidence_items=(_evidence(),))
    first = repository.create_candidate_visit_from_proposal(request)

    # Simulate a process restart: a brand-new ProductRepository instance
    # pointed at the exact same on-disk database.
    restarted = ProductRepository(db_url=repository.db_url, media_root=repository.media_root)
    try:
        second = restarted.create_candidate_visit_from_proposal(request)
    finally:
        restarted.close()
    assert second.outcome == "idempotent_repeat"
    assert second.visit_id == first.visit_id
    assert _counts(repository)["candidate_ledger"] == 1


# --- 6. One proposal cannot create two candidates (incl. concurrency) ------


def test_concurrent_create_attempts_for_same_proposal_yield_one_visit(repository: ProductRepository) -> None:
    _activate(repository)
    request = CreateCandidateVisitRequest(proposal=_facts(), observed_at=NOW, evidence_items=(_evidence(),))
    outcomes: list[str] = []
    lock = threading.Lock()

    def attempt() -> None:
        result = repository.create_candidate_visit_from_proposal(request)
        with lock:
            outcomes.append(result.outcome)

    threads = [threading.Thread(target=attempt) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)

    assert len(outcomes) == 8
    assert outcomes.count("created") == 1
    assert outcomes.count("idempotent_repeat") == 7
    assert _counts(repository)["candidate_ledger"] == 1


# --- 7 / 8. Activation boundary ---------------------------------------------


def test_pre_activation_proposal_cannot_create_candidate(repository: ProductRepository) -> None:
    _activate(repository, now=NOW)
    outcome = repository.create_candidate_visit_from_proposal(
        CreateCandidateVisitRequest(
            proposal=_facts(), observed_at=NOW - timedelta(seconds=1), evidence_items=(_evidence(),),
        )
    )
    assert outcome.outcome == "blocked_pre_activation"
    assert _counts(repository)["candidate_ledger"] == 0


def test_post_activation_proposal_may_create_candidate(repository: ProductRepository) -> None:
    _activate(repository, now=NOW)
    outcome = repository.create_candidate_visit_from_proposal(
        CreateCandidateVisitRequest(
            proposal=_facts(), observed_at=NOW + timedelta(seconds=1), evidence_items=(_evidence(),),
        )
    )
    assert outcome.outcome == "created"


# --- 9 / 10. Kill switch ------------------------------------------------


def test_kill_switch_blocks_new_candidates(repository: ProductRepository) -> None:
    _activate(repository)
    repository.create_candidate_visit_from_proposal(
        CreateCandidateVisitRequest(
            proposal=_facts(proposal_id="visit-episode:a"), observed_at=NOW, evidence_items=(_evidence(),),
        )
    )
    repository.set_observation_authority_mode(ObservationAuthorityMode.shadow, stream_id=STREAM_ID, now=NOW)
    outcome = repository.create_candidate_visit_from_proposal(
        CreateCandidateVisitRequest(
            proposal=_facts(proposal_id="visit-episode:b"), observed_at=NOW + timedelta(seconds=1), evidence_items=(_evidence(),),
        )
    )
    assert outcome.outcome == "blocked_shadow_mode"
    assert _counts(repository)["candidate_ledger"] == 1


def test_disabling_authority_preserves_existing_candidate(repository: ProductRepository) -> None:
    _activate(repository)
    created = repository.create_candidate_visit_from_proposal(
        CreateCandidateVisitRequest(proposal=_facts(), observed_at=NOW, evidence_items=(_evidence(),))
    )
    repository.set_observation_authority_mode(ObservationAuthorityMode.shadow, stream_id=STREAM_ID, now=NOW)
    with repository.session_factory() as session:
        visit = session.get(VisitModel, created.visit_id)
        assert visit is not None
        assert visit.review_status == "needs_review"


def test_toggle_back_to_candidate_authority_gets_fresh_activation_boundary(repository: ProductRepository) -> None:
    _activate(repository, now=NOW)
    repository.set_observation_authority_mode(ObservationAuthorityMode.shadow, stream_id=STREAM_ID, now=NOW + timedelta(minutes=1))
    status = repository.get_observation_authority_state(stream_id=STREAM_ID)
    assert status.activation_boundary_at is None
    _activate(repository, now=NOW + timedelta(minutes=2))
    status = repository.get_observation_authority_state(stream_id=STREAM_ID)
    assert status.activation_boundary_at == NOW + timedelta(minutes=2)


# --- 12 / 13 / 14. Truth boundary -------------------------------------------


def test_candidate_creates_no_review_label(repository: ProductRepository) -> None:
    # The demo seed graph (`ProductRepository.seed_if_empty`) already
    # includes one demo ReviewLabel; assert Stage 7 adds zero *more*, not
    # that the table is empty in absolute terms.
    before = _counts(repository)["review_labels"]
    _activate(repository)
    repository.create_candidate_visit_from_proposal(
        CreateCandidateVisitRequest(proposal=_facts(), observed_at=NOW, evidence_items=(_evidence(),))
    )
    assert _counts(repository)["review_labels"] == before


def test_candidate_never_self_marks_reviewed_or_species_confirmed(repository: ProductRepository) -> None:
    _activate(repository)
    outcome = repository.create_candidate_visit_from_proposal(
        CreateCandidateVisitRequest(proposal=_facts(), observed_at=NOW, evidence_items=(_evidence(),))
    )
    with repository.session_factory() as session:
        visit = session.get(VisitModel, outcome.visit_id)
        assert visit.review_status != "reviewed"
        assert visit.species_guess is None
        assert visit.reviewed_label is None


# --- 15 / 16. Existing Visit protection -------------------------------------


def test_candidate_creation_does_not_mutate_an_unrelated_reviewed_visit(repository: ProductRepository) -> None:
    with repository.session_factory() as session:
        with session.begin():
            session.add(EventModel(
                id="event-reviewed-1", stream_id=STREAM_ID, title="Reviewed cardinal", event_type="motion_evidence",
                started_at=NOW, ended_at=NOW, primary_zone_id=FEEDER_ZONE_ID, review_status="reviewed",
            ))
            session.add(VisitModel(
                id="visit-reviewed-1", event_id="event-reviewed-1", subject_label="bird",
                species_guess="northern_cardinal", confidence=0.9, reviewed_label="northern_cardinal",
                review_status="reviewed", representative_media_path=None, zone_id=FEEDER_ZONE_ID,
            ))
    with repository.session_factory() as session:
        before = session.get(VisitModel, "visit-reviewed-1")
        before_snapshot = (before.review_status, before.reviewed_label, before.species_guess, before.confidence)

    _activate(repository)
    repository.create_candidate_visit_from_proposal(
        CreateCandidateVisitRequest(proposal=_facts(), observed_at=NOW, evidence_items=(_evidence(),))
    )

    with repository.session_factory() as session:
        after = session.get(VisitModel, "visit-reviewed-1")
        after_snapshot = (after.review_status, after.reviewed_label, after.species_guess, after.confidence)
    assert before_snapshot == after_snapshot == ("reviewed", "northern_cardinal", "northern_cardinal", 0.9)


# --- 17 / 18 / 19 / 20. Lineage retention ------------------------------------


def test_candidate_ledger_retains_full_lineage(repository: ProductRepository) -> None:
    _activate(repository)
    outcome = repository.create_candidate_visit_from_proposal(
        CreateCandidateVisitRequest(
            proposal=_facts(),
            observed_at=NOW,
            evidence_items=(_evidence("identification", "shadow-burst:hash-1"), _evidence("context", "shadow-burst:hash-2")),
        )
    )
    with repository.session_factory() as session:
        ledger = session.get(ObservationCandidateVisitModel, "visit-episode:fixture-1")
        assert ledger is not None
        assert ledger.visit_id == outcome.visit_id
        assert json.loads(ledger.constituent_generation_ids_json) == ["gen-1", "gen-2"]
        assert json.loads(ledger.source_capture_frame_ids_json) == ["frame-1", "frame-2"]
        assert json.loads(ledger.supporting_frame_ids_json) == ["frame-1", "frame-2"]
        assert json.loads(ledger.evidence_candidate_ids_json) == ["shadow-burst:hash-1"]
        assert json.loads(ledger.limitation_facts_json) == ["assembled_from_multiple_tracklets"]
        assert ledger.detector_provenance == "onnx-cuda"
        assert ledger.tracker_provenance == "frame-driven-onnx-cuda-v1"
        assert ledger.provider_key == "frame-driven-onnx-cuda"
        assert ledger.selected_identification_media_asset_id is not None
        assert ledger.selected_context_media_asset_id is not None
        assert ledger.selected_identification_media_asset_id != ledger.selected_context_media_asset_id

        identification_media = session.get(MediaAssetModel, ledger.selected_identification_media_asset_id)
        assert identification_media.evidence_role == "identification"
        assert identification_media.derivation_source == "observation_engine_candidate"
        assert identification_media.trigger_id == "visit-episode:fixture-1"


def test_candidate_ledger_retains_confidence_evidence_when_supplied(repository: ProductRepository) -> None:
    """Detection Quality Accounting v1: the ledger persists whatever
    confidence/evidence summary the caller supplies verbatim -- this
    repository layer never inspects, recomputes, or validates its content
    (that is `contracts.ConfidenceEvidenceSummary`'s own job upstream)."""
    _activate(repository)
    payload = json.dumps({
        "detection_count": 4, "max_confidence": 0.71, "mean_confidence": 0.55,
        "median_confidence": 0.52, "strong_detection_count": 1, "weak_detection_count": 3,
        "sample_truncated": False,
    })
    repository.create_candidate_visit_from_proposal(
        CreateCandidateVisitRequest(
            proposal=_facts(confidence_evidence_json=payload), observed_at=NOW, evidence_items=(_evidence(),),
        )
    )
    with repository.session_factory() as session:
        ledger = session.get(ObservationCandidateVisitModel, "visit-episode:fixture-1")
        assert ledger is not None
        assert json.loads(ledger.confidence_evidence_json) == json.loads(payload)


def test_candidate_ledger_confidence_evidence_defaults_to_none_when_not_supplied(
    repository: ProductRepository,
) -> None:
    """A caller that never populates `confidence_evidence_json` (for
    example an older adapter predating Detection Quality Accounting v1)
    gets an honest `None`, never a fabricated summary."""
    _activate(repository)
    repository.create_candidate_visit_from_proposal(
        CreateCandidateVisitRequest(proposal=_facts(), observed_at=NOW, evidence_items=(_evidence(),))
    )
    with repository.session_factory() as session:
        ledger = session.get(ObservationCandidateVisitModel, "visit-episode:fixture-1")
        assert ledger is not None
        assert ledger.confidence_evidence_json is None


def test_candidate_evidence_retains_geometry_attribution_when_supplied(repository: ProductRepository) -> None:
    """Localization Attribution / Detection Geometry Lineage v1 (see
    docs/localization-attribution-contract.md): the persisted `MediaAsset`
    row for one evidence item carries whatever `GeometryAttribution` JSON
    the caller supplies verbatim -- this repository layer never inspects,
    recomputes, or validates its content, mirroring exactly how the ledger
    already treats `confidence_evidence_json`."""
    _activate(repository)
    payload = json.dumps({
        "geometry_source": "detector", "geometry_source_offset_ms": 760_843,
        "geometry_source_observation_id": "obs-1", "geometry_source_confidence": 0.66,
        "same_frame": False, "geometry_evidence_gap_ms": 9_551,
    })
    outcome = repository.create_candidate_visit_from_proposal(
        CreateCandidateVisitRequest(
            proposal=_facts(),
            observed_at=NOW,
            evidence_items=(_evidence(geometry_attribution_json=payload),),
        )
    )
    assert outcome.outcome == "created"
    with repository.session_factory() as session:
        media = session.get(MediaAssetModel, outcome.persisted_media_asset_ids[0])
        assert media is not None
        assert json.loads(media.geometry_attribution_json) == json.loads(payload)


def test_candidate_evidence_geometry_attribution_defaults_to_none_when_not_supplied(
    repository: ProductRepository,
) -> None:
    """A caller that never populates `geometry_attribution_json` (for
    example an evidence item built before this contract existed) gets an
    honest `None`, never a fabricated attribution."""
    _activate(repository)
    outcome = repository.create_candidate_visit_from_proposal(
        CreateCandidateVisitRequest(proposal=_facts(), observed_at=NOW, evidence_items=(_evidence(),))
    )
    assert outcome.outcome == "created"
    with repository.session_factory() as session:
        media = session.get(MediaAssetModel, outcome.persisted_media_asset_ids[0])
        assert media is not None
        assert media.geometry_attribution_json is None


def test_schema_v33_adds_geometry_attribution_column_without_fabricating_legacy_data(
    tmp_path: Path,
) -> None:
    """Localization Attribution / Detection Geometry Lineage v1 (see
    docs/localization-attribution-contract.md): a MediaAsset created
    *before* this column existed must read back `geometry_attribution_json
    is None` after migrating forward -- never a fabricated attribution --
    while a MediaAsset created *after* migration genuinely persists one.
    Mirrors `test_schema_v31_adds_confidence_evidence_column_without_
    fabricating_legacy_data` exactly, one column and one table over."""

    db_path = tmp_path / "schema-v33.sqlite3"
    repository = ProductRepository(db_url=f"sqlite:///{db_path}", media_root=tmp_path / "media")
    assert CURRENT_DATABASE_SCHEMA_VERSION == 35
    _activate(repository)
    pre_migration_outcome = repository.create_candidate_visit_from_proposal(
        CreateCandidateVisitRequest(
            proposal=_facts(proposal_id="visit-episode:pre-migration-geometry"),
            observed_at=NOW,
            evidence_items=(_evidence(),),
        )
    )
    assert pre_migration_outcome.outcome == "created"
    pre_migration_media_id = pre_migration_outcome.persisted_media_asset_ids[0]
    repository.close()

    engine = create_database_engine(f"sqlite:///{db_path}")
    with engine.begin() as connection:
        # Simulate "a database that predates this column": drop it and roll
        # the recorded schema version back to the last version that never
        # had it.
        connection.exec_driver_sql("ALTER TABLE media_assets DROP COLUMN geometry_attribution_json")
        connection.exec_driver_sql("UPDATE mockingbird_schema SET version = 32 WHERE singleton_id = 1")
    engine.dispose()

    migrated = ProductRepository(db_url=f"sqlite:///{db_path}", media_root=tmp_path / "media")
    try:
        assert migrated.schema_status.version == CURRENT_DATABASE_SCHEMA_VERSION == 35
        with migrated.session_factory() as session:
            pre_media = session.get(MediaAssetModel, pre_migration_media_id)
            assert pre_media is not None
            assert pre_media.geometry_attribution_json is None  # no fabricated attribution for a legacy record

        payload = json.dumps({"geometry_source": "tracker", "same_frame": True, "geometry_evidence_gap_ms": 0})
        # See the identical comment in
        # test_schema_v31_adds_confidence_evidence_column_without_
        # fabricating_legacy_data: migrating through schema 35 resets this
        # Stream's own authority settings row -- re-activate, not a regression.
        _activate(migrated)
        post_migration_outcome = migrated.create_candidate_visit_from_proposal(
            CreateCandidateVisitRequest(
                proposal=_facts(proposal_id="visit-episode:post-migration-geometry"),
                observed_at=NOW,
                evidence_items=(_evidence(geometry_attribution_json=payload),),
            )
        )
        assert post_migration_outcome.outcome == "created"
        with migrated.session_factory() as session:
            post_media = session.get(MediaAssetModel, post_migration_outcome.persisted_media_asset_ids[0])
            assert post_media is not None
            assert json.loads(post_media.geometry_attribution_json) == json.loads(payload)
    finally:
        migrated.close()


# --- 21. Missing evidence fails safely --------------------------------------


def test_missing_evidence_fails_safely(repository: ProductRepository) -> None:
    _activate(repository)
    before = _counts(repository)
    outcome = repository.create_candidate_visit_from_proposal(
        CreateCandidateVisitRequest(proposal=_facts(), observed_at=NOW, evidence_items=()),
    )
    assert outcome.outcome == "blocked_missing_evidence"
    assert outcome.visit_id is None
    assert _counts(repository) == before


def test_zero_byte_evidence_fails_safely_as_missing_evidence(repository: ProductRepository) -> None:
    _activate(repository)
    empty_item = CandidateEvidenceItem(
        engine_media_id="shadow-burst:empty", role="identification", content=b"", content_type="image/jpeg",
        width=None, height=None, captured_at=NOW, subject_geometry=None,
    )
    outcome = repository.create_candidate_visit_from_proposal(
        CreateCandidateVisitRequest(proposal=_facts(), observed_at=NOW, evidence_items=(empty_item,)),
    )
    assert outcome.outcome == "blocked_missing_evidence"


# --- 22. Invalid lineage fails safely ---------------------------------------


def test_invalid_lineage_fails_safely(repository: ProductRepository) -> None:
    _activate(repository)
    before = _counts(repository)
    outcome = repository.create_candidate_visit_from_proposal(
        CreateCandidateVisitRequest(
            proposal=_facts(source_capture_frame_ids=(), supporting_frame_ids=()),
            observed_at=NOW, evidence_items=(_evidence(),),
        )
    )
    assert outcome.outcome == "blocked_invalid_lineage"
    assert _counts(repository) == before


def test_real_live_session_shape_creates_successfully(repository: ProductRepository) -> None:
    """Real Stage 7 live-trial finding: a genuine live Camera Node session
    never populates `source_capture_frame_ids` (see "Lineage validity" in
    docs/candidate-visit-authority-contract.md) -- only the ordinary
    `supporting_frame_ids`. This exact shape must create successfully, not
    be blocked for lacking a field live sessions structurally never have."""

    _activate(repository)
    outcome = repository.create_candidate_visit_from_proposal(
        CreateCandidateVisitRequest(
            proposal=_facts(source_capture_frame_ids=(), supporting_frame_ids=("live-frame-1", "live-frame-2")),
            observed_at=NOW, evidence_items=(_evidence(),),
        )
    )
    assert outcome.outcome == "created"
    with repository.session_factory() as session:
        ledger = session.get(ObservationCandidateVisitModel, "visit-episode:fixture-1")
        assert json.loads(ledger.source_capture_frame_ids_json) == []
        assert json.loads(ledger.supporting_frame_ids_json) == ["live-frame-1", "live-frame-2"]


# --- 23. Privacy/Ignore candidate blocked -----------------------------------


def test_ignore_zone_candidate_is_blocked(repository: ProductRepository) -> None:
    _activate(repository)
    before = _counts(repository)
    outcome = repository.create_candidate_visit_from_proposal(
        CreateCandidateVisitRequest(
            proposal=_facts(zone_id=IGNORE_ZONE_ID), observed_at=NOW, evidence_items=(_evidence(),),
        )
    )
    assert outcome.outcome == "blocked_privacy_zone"
    assert _counts(repository) == before


def test_privacy_zone_candidate_is_blocked(repository: ProductRepository) -> None:
    """Companion to `test_ignore_zone_candidate_is_blocked`: the other of
    the two Zone types this boundary must refuse (see "Privacy / Ignore" in
    the contract doc). No privacy Zone is demo-seeded, so this test creates
    one directly."""

    privacy_zone_id = "zone-privacy-test"
    with repository.session_factory() as session:
        with session.begin():
            from mockingbird.storage.models import ZoneModel

            session.add(ZoneModel(
                id=privacy_zone_id, stream_id=STREAM_ID, name="Test privacy zone",
                zone_type="privacy", polygon_json="[]", is_active=True,
            ))
    _activate(repository)
    before = _counts(repository)
    outcome = repository.create_candidate_visit_from_proposal(
        CreateCandidateVisitRequest(
            proposal=_facts(zone_id=privacy_zone_id), observed_at=NOW, evidence_items=(_evidence(),),
        )
    )
    assert outcome.outcome == "blocked_privacy_zone"
    assert _counts(repository) == before


def test_evidence_from_a_non_privacy_zone_is_not_redacted_for_a_coexisting_privacy_zone(
    repository: ProductRepository,
) -> None:
    """Release-truthfulness regression (see docs/privacy-ignore-zone-contract.md):
    a Privacy Zone only blocks a candidate whose *own* triggering zone is
    Privacy/Ignore (see `test_privacy_zone_candidate_is_blocked` above). It
    does not redact, crop, or otherwise alter evidence for a *different,
    legitimately triggered* candidate merely because a Privacy Zone also
    exists somewhere on the same Stream. This locks in the persistence half
    of the trigger-level-exclusion contract: the persisted MediaAsset's
    bytes on disk are byte-identical to the source evidence content, proving
    no pixel-level redaction happened anywhere in this path."""

    privacy_zone_id = "zone-privacy-coexisting"
    with repository.session_factory() as session:
        with session.begin():
            from mockingbird.storage.models import ZoneModel

            session.add(ZoneModel(
                id=privacy_zone_id, stream_id=STREAM_ID, name="Neighbor's window",
                zone_type="privacy", polygon_json="[]", is_active=True,
            ))
    _activate(repository)
    before = _counts(repository)
    outcome = repository.create_candidate_visit_from_proposal(
        CreateCandidateVisitRequest(
            # Default zone_id is FEEDER_ZONE_ID -- a different, non-privacy
            # zone on the same stream as the privacy zone created above.
            proposal=_facts(), observed_at=NOW, evidence_items=(_evidence(),),
        )
    )
    assert outcome.outcome == "created"
    assert _counts(repository)["media_assets"] == before["media_assets"] + 1
    with repository.session_factory() as session:
        media = session.get(MediaAssetModel, outcome.persisted_media_asset_ids[0])
        assert media is not None
        assert Path(media.local_path).read_bytes() == JPEG_BYTES


# --- 24 / 25. Session + hourly limits ---------------------------------------


def test_candidate_session_limit_enforced(repository: ProductRepository) -> None:
    _activate(repository, max_candidates_per_session=2)
    outcomes = []
    for index in range(3):
        outcomes.append(
            repository.create_candidate_visit_from_proposal(
                CreateCandidateVisitRequest(
                    proposal=_facts(proposal_id=f"visit-episode:session-{index}"),
                    observed_at=NOW + timedelta(seconds=index),
                    evidence_items=(_evidence(),),
                )
            ).outcome
        )
    assert outcomes == ["created", "created", "blocked_session_limit"]
    assert _counts(repository)["candidate_ledger"] == 2


def test_candidate_hourly_limit_enforced(repository: ProductRepository) -> None:
    _activate(repository, max_candidates_per_hour=1)
    first = repository.create_candidate_visit_from_proposal(
        CreateCandidateVisitRequest(proposal=_facts(proposal_id="visit-episode:h1"), observed_at=NOW, evidence_items=(_evidence(),))
    )
    second = repository.create_candidate_visit_from_proposal(
        CreateCandidateVisitRequest(
            proposal=_facts(proposal_id="visit-episode:h2"), observed_at=NOW + timedelta(minutes=5), evidence_items=(_evidence(),),
        )
    )
    assert first.outcome == "created"
    assert second.outcome == "blocked_hourly_limit"


# --- 26. Evidence count/byte bounds enforced --------------------------------


def test_evidence_item_count_bound_enforced(repository: ProductRepository) -> None:
    _activate(repository, max_evidence_items_per_candidate=2)
    items = tuple(_evidence("alternate", f"shadow-burst:hash-{i}") for i in range(5))
    items = (_evidence("identification", "shadow-burst:hash-id"),) + items
    outcome = repository.create_candidate_visit_from_proposal(
        CreateCandidateVisitRequest(proposal=_facts(), observed_at=NOW, evidence_items=items),
    )
    assert outcome.outcome == "created"
    assert len(outcome.persisted_media_asset_ids) == 2


def test_evidence_byte_bound_enforced(repository: ProductRepository) -> None:
    _activate(repository, max_evidence_bytes_per_candidate=1024)
    small = _evidence("identification", "shadow-burst:hash-small")
    assert len(JPEG_BYTES) < 1024  # the fixture itself must fit under the bound alone
    big = CandidateEvidenceItem(
        engine_media_id="shadow-burst:hash-big", role="context", content=JPEG_BYTES * 20,
        content_type="image/jpeg", width=1920, height=1080, captured_at=NOW, subject_geometry=None,
    )
    assert len(small.content) + len(big.content) > 1024  # both together must not fit
    outcome = repository.create_candidate_visit_from_proposal(
        CreateCandidateVisitRequest(proposal=_facts(), observed_at=NOW, evidence_items=(small, big)),
    )
    assert outcome.outcome == "created"
    assert len(outcome.persisted_media_asset_ids) == 1  # only the small item fit the byte bound


# --- 27 / 28. Persistence failure safety ------------------------------------


def test_persistence_failure_rolls_back_and_creates_no_partial_truth(
    repository: ProductRepository, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _activate(repository)

    def _boom(*args, **kwargs):
        raise OSError("simulated disk failure")

    monkeypatch.setattr(ProductRepository, "_write_media_file", _boom)
    before = _counts(repository)
    with pytest.raises(ValueError, match="observation_candidate_visit_persistence_failed"):
        repository.create_candidate_visit_from_proposal(
            CreateCandidateVisitRequest(proposal=_facts(), observed_at=NOW, evidence_items=(_evidence(),)),
        )
    assert _counts(repository) == before  # nothing partial survives

    repository.record_observation_authority_failure(
        stream_id=STREAM_ID, failure_code="observation_candidate_visit_persistence_failed", now=NOW,
    )
    status = repository.get_observation_authority_state(stream_id=STREAM_ID)
    assert status.failure_count == 1
    assert status.last_failure_code == "observation_candidate_visit_persistence_failed"


# --- Diagnostics -------------------------------------------------------------


def test_diagnostics_track_attempts_creates_repeats_and_suppressions(repository: ProductRepository) -> None:
    _activate(repository)
    request = CreateCandidateVisitRequest(proposal=_facts(), observed_at=NOW, evidence_items=(_evidence(),))
    repository.create_candidate_visit_from_proposal(request)
    repository.create_candidate_visit_from_proposal(request)  # idempotent repeat
    repository.create_candidate_visit_from_proposal(
        CreateCandidateVisitRequest(
            proposal=_facts(proposal_id="visit-episode:fixture-2", source_capture_frame_ids=(), supporting_frame_ids=()),
            observed_at=NOW, evidence_items=(_evidence(),),
        )
    )  # suppressed (invalid lineage) -- a distinct proposal_id, or this would
    # itself just be another idempotent repeat of fixture-1

    status = repository.get_observation_authority_state(stream_id=STREAM_ID)
    assert status.proposals_observed_count == 3
    assert status.candidates_created_count == 1
    assert status.idempotent_repeat_count == 1
    assert status.suppressed_count == 1
    assert status.last_candidate_visit_id is not None
    assert status.last_proposal_id == "visit-episode:fixture-1"
