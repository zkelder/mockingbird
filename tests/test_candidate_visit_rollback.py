"""Stage 7 rollback drill (see "Rollback test" in the Stage 7 operating
order and "Kill switch" in docs/candidate-visit-authority-contract.md).

Walks the exact documented rollback procedure end to end against one
isolated `tmp_path` database:

1. disable candidate authority (the kill switch)
2. verify no new candidates occur
3. live shadow (the assembler itself) continues unaffected
4. existing candidates remain intact and reviewable
5. no truth is lost or corrupted
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from mockingbird.api.schemas import ReviewCorrectionCreate
from mockingbird.observation.candidate_visit_authority import ObservationAuthorityMode
from mockingbird.observation.visit_episode_assembler import Tracklet, assemble_visit_episodes
from mockingbird.repository.product_repository import (
    CandidateEvidenceItem,
    CandidateVisitProposalFacts,
    CreateCandidateVisitRequest,
    ObservationCandidateVisitModel,
    ProductRepository,
    VisitModel,
)

STREAM_ID = "stream-backyard-feeder"
FEEDER_ZONE_ID = "zone-feeder"
NOW = datetime(2026, 8, 8, 12, 0, 0, tzinfo=UTC)
JPEG_BYTES = b"\xff\xd8\xff\xe0" + b"0" * 64 + b"\xff\xd9"


@pytest.fixture
def repository(tmp_path: Path) -> ProductRepository:
    repo = ProductRepository(db_url=f"sqlite:///{tmp_path / 'mockingbird.sqlite3'}", media_root=tmp_path / "media")
    yield repo
    repo.close()


def _create(repository: ProductRepository, proposal_id: str, observed_at: datetime):
    facts = CandidateVisitProposalFacts(
        proposal_id=proposal_id, stream_id=STREAM_ID, zone_id=FEEDER_ZONE_ID, broad_class="animal",
        start_offset_ms=0, end_offset_ms=4500, constituent_generation_ids=("gen-1",),
        constituent_track_ids=("track-1",), source_capture_frame_ids=("frame-1",),
        evidence_candidate_ids=("shadow-burst:hash-1",), limitation_facts=(), ambiguous_adjacent_proposal_ids=(),
        assembler_version="tracklet-visit-assembler-v1",
    )
    item = CandidateEvidenceItem(
        engine_media_id="shadow-burst:hash-1", role="identification", content=JPEG_BYTES,
        content_type="image/jpeg", width=1920, height=1080, captured_at=observed_at, subject_geometry=(0.4, 0.4, 0.6, 0.6),
    )
    return repository.create_candidate_visit_from_proposal(
        CreateCandidateVisitRequest(proposal=facts, observed_at=observed_at, evidence_items=(item,))
    )


def test_full_rollback_drill(repository: ProductRepository) -> None:
    # --- Setup: authority active, two genuine candidates created ---------
    repository.set_observation_authority_mode(ObservationAuthorityMode.candidate_visit, now=NOW)
    first = _create(repository, "visit-episode:rollback-a", NOW)
    second = _create(repository, "visit-episode:rollback-b", NOW + timedelta(seconds=1))
    assert first.outcome == "created"
    assert second.outcome == "created"

    # A human reviews the first candidate through the exact existing path,
    # producing real reviewed truth before rollback -- proving rollback
    # must not touch it.
    repository.create_review_label(
        ReviewCorrectionCreate(target_type="visit", target_id=first.visit_id, label="false_positive", review_origin="human"),
    )
    reviewed_snapshot_before = repository.get_visit(first.visit_id)
    assert reviewed_snapshot_before.review_status.value == "reviewed"

    # --- Step 1: disable candidate authority (the kill switch) -----------
    status = repository.set_observation_authority_mode(ObservationAuthorityMode.shadow, now=NOW + timedelta(seconds=2))
    assert status.mode == "shadow"
    assert status.activation_boundary_at is None

    # --- Step 2: verify no new candidates occur ---------------------------
    third = _create(repository, "visit-episode:rollback-c", NOW + timedelta(seconds=3))
    assert third.outcome == "blocked_shadow_mode"
    assert third.visit_id is None

    # --- Step 3: live shadow (the assembler) continues unaffected --------
    tracklet = Tracklet(
        generation_id="rollback-gen", stream_id=STREAM_ID, broad_class="animal",
        start_offset_ms=0, end_offset_ms=1000, start_bounding_box=(0.4, 0.4, 0.5, 0.5),
        end_bounding_box=(0.4, 0.4, 0.5, 0.5), geometry_envelope=(0.4, 0.4, 0.5, 0.5),
        terminal_reason="maximum_unsupported_duration", track_ids=("rollback-gen-track",),
    )
    assembly = assemble_visit_episodes((tracklet,))
    assert len(assembly.proposals) == 1  # the assembler runs identically regardless of authority mode

    # --- Step 4: existing candidates remain intact and reviewable --------
    replay_of_first = repository.create_candidate_visit_from_proposal(
        CreateCandidateVisitRequest(
            proposal=CandidateVisitProposalFacts(
                proposal_id="visit-episode:rollback-a", stream_id=STREAM_ID, zone_id=FEEDER_ZONE_ID,
                broad_class="animal", start_offset_ms=0, end_offset_ms=4500,
                constituent_generation_ids=("gen-1",), constituent_track_ids=("track-1",),
                source_capture_frame_ids=("frame-1",), evidence_candidate_ids=("shadow-burst:hash-1",),
                limitation_facts=(), ambiguous_adjacent_proposal_ids=(), assembler_version="tracklet-visit-assembler-v1",
            ),
            observed_at=NOW + timedelta(seconds=4),
            evidence_items=(CandidateEvidenceItem(
                engine_media_id="shadow-burst:hash-1", role="identification", content=JPEG_BYTES,
                content_type="image/jpeg", width=1920, height=1080, captured_at=NOW, subject_geometry=None,
            ),),
        )
    )
    assert replay_of_first.outcome == "idempotent_repeat"  # still reachable/idempotent even while disabled
    assert replay_of_first.visit_id == first.visit_id

    second_visit = repository.get_visit(second.visit_id)
    assert second_visit is not None
    assert second_visit.review_status.value == "needs_review"  # still exactly as reviewable as before

    # Human review still works normally on the still-open second candidate
    # even with authority disabled -- the review path is independent of
    # Stage 7 authority state entirely.
    repository.create_review_label(
        ReviewCorrectionCreate(target_type="visit", target_id=second.visit_id, label="squirrel", review_origin="human"),
    )
    assert repository.get_visit(second.visit_id).review_status.value == "reviewed"

    # --- Step 5: no truth is lost or corrupted ----------------------------
    reviewed_snapshot_after = repository.get_visit(first.visit_id)
    assert reviewed_snapshot_after.review_status.value == reviewed_snapshot_before.review_status.value
    assert reviewed_snapshot_after.reviewed_label == reviewed_snapshot_before.reviewed_label == "false_positive"
    with repository.session_factory() as session:
        assert session.get(VisitModel, first.visit_id) is not None
        assert session.get(VisitModel, second.visit_id) is not None
        assert session.get(ObservationCandidateVisitModel, "visit-episode:rollback-a") is not None
        assert session.get(ObservationCandidateVisitModel, "visit-episode:rollback-b") is not None
        assert session.get(ObservationCandidateVisitModel, "visit-episode:rollback-c") is None
