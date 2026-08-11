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
from mockingbird.storage.models import CameraSourceModel, StreamModel, ZoneModel

STREAM_ID = "stream-backyard-feeder"
FEEDER_ZONE_ID = "zone-feeder"
# A genuine (non-demo) Stream/Zone for the Review Queue / Today product-flow
# tests below: the seeded demo stream above is *intentionally* excluded from
# useful wildlife presentation (`is_demo_source`), so proving Stage 7
# candidates read as real, useful wildlife Visits needs a real Source/Stream,
# the same fixture convention `tests/test_dashboard_today.py` establishes.
REAL_SOURCE_ID = "source-review-workflow-real"
REAL_STREAM_ID = "stream-review-workflow-real"
REAL_ZONE_ID = "zone-review-workflow-real"
NOW = datetime(2026, 8, 8, 12, 0, 0, tzinfo=UTC)
JPEG_BYTES = b"\xff\xd8\xff\xe0" + b"0" * 64 + b"\xff\xd9"


@pytest.fixture
def repository(tmp_path: Path) -> ProductRepository:
    repo = ProductRepository(db_url=f"sqlite:///{tmp_path / 'mockingbird.sqlite3'}", media_root=tmp_path / "media")
    yield repo
    repo.close()


def _use_real_stream(repository: ProductRepository) -> None:
    """Insert a real, non-demo Source/Stream/Zone with fixed ids, matching
    `tests/test_dashboard_today.py`'s established fixture convention."""

    with repository.session_factory() as session:
        with session.begin():
            if session.get(StreamModel, REAL_STREAM_ID) is not None:
                return
            session.add(
                CameraSourceModel(
                    id=REAL_SOURCE_ID, name="Real backyard camera", kind="integration",
                    status="connected", description="Non-demo fixture Source for product-flow tests.",
                )
            )
            session.add(
                StreamModel(
                    id=REAL_STREAM_ID, source_id=REAL_SOURCE_ID, name="Real backyard stream",
                    description="Non-demo fixture Stream for product-flow tests.", is_live=True,
                )
            )
            session.add(
                ZoneModel(
                    id=REAL_ZONE_ID, stream_id=REAL_STREAM_ID, name="Feeder", zone_type="feeder",
                    polygon_json="[]", is_active=True,
                )
            )


def _create_candidate(
    repository: ProductRepository,
    *,
    stream_id: str = STREAM_ID,
    zone_id: str | None = FEEDER_ZONE_ID,
    proposal_id: str = "visit-episode:review-workflow-fixture",
) -> str:
    repository.set_observation_authority_mode(ObservationAuthorityMode.candidate_visit, now=NOW)
    facts = CandidateVisitProposalFacts(
        proposal_id=proposal_id,
        stream_id=stream_id,
        zone_id=zone_id,
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


def _create_real_candidate(repository: ProductRepository, *, proposal_id: str = "visit-episode:real-fixture") -> str:
    _use_real_stream(repository)
    return _create_candidate(repository, stream_id=REAL_STREAM_ID, zone_id=REAL_ZONE_ID, proposal_id=proposal_id)


def test_existing_review_endpoint_can_review_a_candidate_visit(repository: ProductRepository) -> None:
    visit_id = _create_candidate(repository)

    # Before human review: needs_review, no truth -- the Stage 7 boundary itself.
    before = repository.get_visit(visit_id)
    assert before is not None
    assert before.review_status.value == "needs_review"
    assert before.reviewed_label is None

    # The exact existing, unmodified correction path -- no Stage 7 involvement.
    result = repository.create_review_label(
        ReviewCorrectionCreate(target_type="visit", target_id=visit_id, label="false_positive", review_origin="human"),
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


# --- Product vertical slice: Review Queue / effective-primary / Today ------
# integration for Stage 7 evidence roles (Product requirements 3 and 6).


def test_unreviewed_candidate_is_visible_in_the_default_review_queue(
    repository: ProductRepository,
) -> None:
    """The default Review Queue tab is driven by `product_category ==
    "animal"`, derived from durable detector provenance. Stage 7 candidates
    carry no legacy MotionEvidence scoring blob, so without the Stage 7
    fallback this item would silently classify as "unchecked" and never
    appear under Animals at all."""

    visit_id = _create_real_candidate(repository)
    items = repository.review_queue_items()
    matching = [item for item in items if item.visit_id == visit_id]
    assert len(matching) == 1
    item = matching[0]
    assert item.product_category == "animal"
    assert item.detector_class == "animal"
    # The real reviewable image, not a missing-evidence placeholder.
    assert item.best_media_asset_id is not None
    assert item.media_asset is not None
    assert item.media_asset.id == item.best_media_asset_id


def test_candidate_effective_primary_prefers_identification_evidence(
    repository: ProductRepository,
) -> None:
    visit_id = _create_real_candidate(repository)
    preview = repository.effective_primary_preview(visit_id)
    assert preview is not None
    assert preview["is_useful"] is True
    assert preview["selection_reason"] == "identification_evidence_preferred"
    assert preview["recommended_effective_primary_media_asset_id"] == preview["selected_media_asset_id"]


def test_unreviewed_candidate_counts_as_detector_qualified_and_needs_help(
    repository: ProductRepository,
) -> None:
    """Before human review, a genuine Stage 7 candidate is exactly the
    "useful wildlife Visit ready for confirmation" Today in Your Yard should
    surface -- not invisible, and not masquerading as confirmed truth."""

    _create_real_candidate(repository)
    summary = repository.dashboard_summary(now=NOW)
    assert summary.today.detector_qualified_animal_visit_count == 1
    assert summary.today.unresolved_animal_visit_count == 1
    assert summary.today.confirmed_bird_visit_count == 0
    assert summary.today.confirmed_species_count == 0


def test_false_positive_review_removes_candidate_from_wildlife_presentation(
    repository: ProductRepository,
) -> None:
    visit_id = _create_real_candidate(repository)
    repository.create_review_label(
        ReviewCorrectionCreate(target_type="visit", target_id=visit_id, label="false_positive", review_origin="human"),
    )
    summary = repository.dashboard_summary(now=NOW)
    assert summary.today.detector_qualified_animal_visit_count == 0
    assert summary.today.unresolved_animal_visit_count == 0
    assert summary.today.confirmed_bird_visit_count == 0


def test_unknown_bird_review_remains_valid_wildlife_without_invented_species(
    repository: ProductRepository,
) -> None:
    visit_id = _create_real_candidate(repository)
    repository.create_review_label(
        ReviewCorrectionCreate(target_type="visit", target_id=visit_id, label="unknown_bird", review_origin="human"),
    )
    summary = repository.dashboard_summary(now=NOW)
    # Still a countable, real wildlife moment...
    assert summary.today.detector_qualified_animal_visit_count == 1
    assert summary.today.unresolved_animal_visit_count == 0
    # ...but never promoted to a confirmed species truth it does not have.
    assert summary.today.confirmed_bird_visit_count == 0
    assert summary.today.confirmed_species_count == 0


def test_confirmed_species_review_closes_the_loop_into_today(repository: ProductRepository) -> None:
    visit_id = _create_real_candidate(repository)
    repository.create_review_label(
        ReviewCorrectionCreate(target_type="visit", target_id=visit_id, label="northern_cardinal", review_origin="human"),
    )
    summary = repository.dashboard_summary(now=NOW)
    assert summary.today.confirmed_bird_visit_count == 1
    assert summary.today.confirmed_species_count == 1
    assert summary.today.unresolved_animal_visit_count == 0
    assert [species.label for species in summary.today.new_today] == ["northern_cardinal"]


def test_reviewed_candidate_moves_to_the_reviewed_review_queue_tab(repository: ProductRepository) -> None:
    visit_id = _create_real_candidate(repository)
    repository.create_review_label(
        ReviewCorrectionCreate(target_type="visit", target_id=visit_id, label="false_positive", review_origin="human"),
    )
    unreviewed = [item.visit_id for item in repository.review_queue_items()]
    assert visit_id not in unreviewed
    reviewed = [item.visit_id for item in repository.review_queue_items(include_reviewed=True)]
    assert visit_id in reviewed
    reviewed_item = next(item for item in repository.review_queue_items(include_reviewed=True) if item.visit_id == visit_id)
    assert reviewed_item.product_category == "reviewed"
