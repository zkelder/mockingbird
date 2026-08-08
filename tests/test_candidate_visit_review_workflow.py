"""Stage 7 human-review boundary: proves the *existing*, unmodified review/
correction path is what -- and the only thing that -- can turn a candidate
Visit into reviewed truth (scenarios 34/35; see "Truth boundary" and "Human
review must use the exact existing review/truth path" in
docs/candidate-visit-authority-contract.md). No Stage 7 code is touched by
this file; it only exercises `ProductRepository.create_review_label`, the
same explicit correction endpoint every other Visit in this product uses.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from mockingbird.api.schemas import ReviewCorrectionCreate
from mockingbird.observation.candidate_visit_authority import ObservationAuthorityMode
from mockingbird.repository.product_repository import (
    CandidateEvidenceItem,
    CandidateVisitProposalFacts,
    CreateCandidateVisitRequest,
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


def _create_candidate(repository: ProductRepository) -> str:
    repository.set_observation_authority_mode(ObservationAuthorityMode.candidate_visit, now=NOW)
    facts = CandidateVisitProposalFacts(
        proposal_id="visit-episode:review-workflow-fixture",
        stream_id=STREAM_ID,
        zone_id=FEEDER_ZONE_ID,
        broad_class="animal",
        start_offset_ms=0,
        end_offset_ms=4500,
        constituent_generation_ids=("gen-1",),
        constituent_track_ids=("track-1",),
        source_capture_frame_ids=("frame-1",),
        evidence_candidate_ids=("shadow-burst:hash-1",),
        limitation_facts=(),
        ambiguous_adjacent_proposal_ids=(),
        assembler_version="tracklet-visit-assembler-v1",
    )
    item = CandidateEvidenceItem(
        engine_media_id="shadow-burst:hash-1", role="identification", content=JPEG_BYTES,
        content_type="image/jpeg", width=1920, height=1080, captured_at=NOW, subject_geometry=(0.4, 0.4, 0.6, 0.6),
    )
    outcome = repository.create_candidate_visit_from_proposal(
        CreateCandidateVisitRequest(proposal=facts, observed_at=NOW, evidence_items=(item,))
    )
    assert outcome.outcome == "created"
    return outcome.visit_id


def test_existing_review_endpoint_can_review_a_candidate_visit(repository: ProductRepository) -> None:
    visit_id = _create_candidate(repository)

    # Before human review: needs_review, no truth -- the Stage 7 boundary itself.
    before = repository.get_visit(visit_id)
    assert before is not None
    assert before.review_status.value == "needs_review"
    assert before.reviewed_label is None

    # The exact existing, unmodified correction path -- no Stage 7 involvement.
    result = repository.create_review_label(
        ReviewCorrectionCreate(target_type="visit", target_id=visit_id, label="false_positive"),
    )
    assert result is not None

    after = repository.get_visit(visit_id)
    assert after.review_status.value == "reviewed"
    assert after.reviewed_label == "false_positive"


def test_candidate_review_status_never_becomes_reviewed_without_the_explicit_call(
    repository: ProductRepository,
) -> None:
    """Restates the truth boundary directly: nothing about candidate
    *creation* itself ever sets review_status to reviewed -- only the
    explicit call above does."""

    visit_id = _create_candidate(repository)
    with repository.session_factory() as session:
        visit = session.get(VisitModel, visit_id)
        assert visit.review_status == "needs_review"
        assert visit.reviewed_label is None
        assert visit.species_guess is None
