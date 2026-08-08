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
from mockingbird.storage.database import CURRENT_DATABASE_SCHEMA_VERSION

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
    zone_id: str | None = FEEDER_ZONE_ID,
    source_capture_frame_ids: tuple[str, ...] = ("frame-1", "frame-2"),
    supporting_frame_ids: tuple[str, ...] = ("frame-1", "frame-2"),
    ambiguous_adjacent_proposal_ids: tuple[str, ...] = (),
) -> CandidateVisitProposalFacts:
    return CandidateVisitProposalFacts(
        proposal_id=proposal_id,
        stream_id=STREAM_ID,
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
    )


def _evidence(role: str = "identification", engine_media_id: str = "shadow-burst:hash-1") -> CandidateEvidenceItem:
    return CandidateEvidenceItem(
        engine_media_id=engine_media_id,
        role=role,
        content=JPEG_BYTES,
        content_type="image/jpeg",
        width=1920,
        height=1080,
        captured_at=NOW,
        subject_geometry=(0.4, 0.4, 0.6, 0.6),
    )


def _activate(repository: ProductRepository, *, now: datetime = NOW, **limits) -> None:
    repository.set_observation_authority_mode(ObservationAuthorityMode.candidate_visit, now=now, **limits)


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


# --- 1. Default authority is shadow -----------------------------------------


def test_fresh_repository_defaults_to_shadow_authority(repository: ProductRepository) -> None:
    status = repository.get_observation_authority_state()
    assert status.mode == "shadow"
    assert status.activation_boundary_at is None
    assert status.candidates_created_count == 0


def test_status_read_never_creates_settings_row(repository: ProductRepository) -> None:
    repository.get_observation_authority_state()
    with repository.session_factory() as session:
        from mockingbird.repository.product_repository import ObservationAuthoritySettingsModel

        assert session.get(ObservationAuthoritySettingsModel, 1) is None


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
    repository.set_observation_authority_mode(ObservationAuthorityMode.shadow, now=NOW)
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
    repository.set_observation_authority_mode(ObservationAuthorityMode.shadow, now=NOW)
    with repository.session_factory() as session:
        visit = session.get(VisitModel, created.visit_id)
        assert visit is not None
        assert visit.review_status == "needs_review"


def test_toggle_back_to_candidate_authority_gets_fresh_activation_boundary(repository: ProductRepository) -> None:
    _activate(repository, now=NOW)
    repository.set_observation_authority_mode(ObservationAuthorityMode.shadow, now=NOW + timedelta(minutes=1))
    status = repository.get_observation_authority_state()
    assert status.activation_boundary_at is None
    _activate(repository, now=NOW + timedelta(minutes=2))
    status = repository.get_observation_authority_state()
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
        context_media = session.get(MediaAssetModel, ledger.selected_context_media_asset_id)
        assert context_media.evidence_role == "context"


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

    repository.record_observation_authority_failure(failure_code="observation_candidate_visit_persistence_failed", now=NOW)
    status = repository.get_observation_authority_state()
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

    status = repository.get_observation_authority_state()
    assert status.proposals_observed_count == 3
    assert status.candidates_created_count == 1
    assert status.idempotent_repeat_count == 1
    assert status.suppressed_count == 1
    assert status.last_candidate_visit_id is not None
    assert status.last_proposal_id == "visit-episode:fixture-1"
