"""Persistent Scene Confusor Suppression v1: repository-level integration
coverage (see docs/scene-confusor-suspicion-contract.md). Uses an isolated
`tmp_path` SQLite database for every test -- never the real product
database -- per the established `tests/test_candidate_visit_repository.py`
fixture convention, which this file mirrors closely.

Motivated directly by real evidence: Observational Quality Closure v1 found
52.9% (37/70) of real admitted candidate Visits in a large cohort were false
positives, 76% clustered into six recurring static scene confusors. This
milestone's own replay simulation against that real cohort (see the
contract doc) found the naive version of this mechanism (recurrence count
alone) would wrongly suppress a real bird landing near an unrelated,
coincidentally-nearby false detection -- the tests below cover exactly that
recall-safety property, not just the confusor-suppression happy path.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import func, select

from mockingbird.api.schemas import (
    CameraConfigurationApplyRequest,
    CameraConfigurationImpactPreviewRequest,
    CameraSetupCompleteRequest,
    Point,
    ReviewCorrectionCreate,
)
from mockingbird.observation.candidate_visit_authority import ObservationAuthorityMode
from mockingbird.observation.counterfactual_lineage import ADMISSION_REJECTED_OUTCOMES
from mockingbird.observation.scene_confusor import DEFAULT_MAX_REGIONS_PER_STREAM
from mockingbird.repository.product_repository import (
    CandidateEvidenceItem,
    CandidateVisitProposalFacts,
    CreateCandidateVisitRequest,
    EventModel,
    MediaAssetModel,
    ProductRepository,
    SceneConfusorRegionModel,
    VisitModel,
)

STREAM_ID = "stream-backyard-feeder"
FEEDER_ZONE_ID = None
NOW = datetime(2026, 8, 19, 12, 0, 0, tzinfo=UTC)
JPEG_BYTES = b"\xff\xd8\xff\xe0" + b"0" * 64 + b"\xff\xd9"

# A tight box, and near-identical repeats of it -- the "static confusor"
# shape (real, measured spread for this exact shape was <=0.0045 in the
# governing cohort; see the module docstring).
CONFUSOR_BOX = (0.464, 0.535, 0.486, 0.551)
CONFUSOR_JITTER = [
    (0.4640, 0.5350, 0.4860, 0.5510),
    (0.4643, 0.5352, 0.4863, 0.5513),
    (0.4638, 0.5348, 0.4858, 0.5508),
    (0.4645, 0.5355, 0.4865, 0.5515),
    (0.4641, 0.5349, 0.4861, 0.5509),
]

# A "popular real perch" shape -- meaningfully more geometric spread across
# occurrences (different individual birds/poses), same measured order of
# magnitude (~0.05) as the real governing cohort's own popular-perch region.
POPULAR_PERCH_BOXES = [
    (0.460, 0.630, 0.490, 0.680),
    (0.475, 0.650, 0.505, 0.700),
    (0.450, 0.610, 0.480, 0.660),
    (0.480, 0.660, 0.512, 0.710),
    (0.455, 0.620, 0.485, 0.670),
]


@pytest.fixture
def repository(tmp_path: Path) -> ProductRepository:
    repo = ProductRepository(db_url=f"sqlite:///{tmp_path / 'mockingbird.sqlite3'}", media_root=tmp_path / "media")
    yield repo
    repo.close()


def _facts(
    *, proposal_id: str, confidence_evidence_json: str | None = None, stream_id: str = STREAM_ID,
) -> CandidateVisitProposalFacts:
    return CandidateVisitProposalFacts(
        proposal_id=proposal_id,
        stream_id=stream_id,
        zone_id=FEEDER_ZONE_ID,
        broad_class="animal",
        start_offset_ms=0,
        end_offset_ms=4500,
        constituent_generation_ids=(f"{proposal_id}-gen",),
        constituent_track_ids=(f"{proposal_id}-track",),
        source_capture_frame_ids=(f"{proposal_id}-frame",),
        supporting_frame_ids=(f"{proposal_id}-frame",),
        evidence_candidate_ids=(f"shadow-burst:{proposal_id}",),
        limitation_facts=(),
        ambiguous_adjacent_proposal_ids=(),
        assembler_version="tracklet-visit-assembler-v1",
        detector_provenance="onnx-cuda",
        tracker_provenance="frame-driven-onnx-cuda-v1",
        provider_key="frame-driven-onnx-cuda",
        confidence_evidence_json=confidence_evidence_json,
    )


def _evidence(box: tuple[float, float, float, float], *, proposal_id: str) -> CandidateEvidenceItem:
    return CandidateEvidenceItem(
        engine_media_id=f"shadow-burst:{proposal_id}",
        role="identification",
        content=JPEG_BYTES,
        content_type="image/jpeg",
        width=3840,
        height=2160,
        captured_at=NOW,
        subject_geometry=box,
    )


def _activate(repository: ProductRepository) -> None:
    repository.set_observation_authority_mode(ObservationAuthorityMode.candidate_visit, now=NOW)


def _attempt(repository, box, *, proposal_id, at, confidence=0.3, stream_id=STREAM_ID):
    conf_json = f'{{"detection_count": 1, "max_confidence": {confidence}}}'
    return repository.create_candidate_visit_from_proposal(
        CreateCandidateVisitRequest(
            proposal=_facts(proposal_id=proposal_id, confidence_evidence_json=conf_json, stream_id=stream_id),
            observed_at=at,
            evidence_items=(_evidence(box, proposal_id=proposal_id),),
        )
    )


def _region_count(repository) -> int:
    with repository.session_factory() as session:
        return session.scalar(select(func.count(SceneConfusorRegionModel.id)))


# --- 1. Recurring static confusor is eventually suspected and blocked -------


def test_recurring_static_confusor_is_eventually_suspected_and_blocked(repository: ProductRepository) -> None:
    _activate(repository)
    outcomes = []
    for index, box in enumerate(CONFUSOR_JITTER):
        outcome = _attempt(repository, box, proposal_id=f"visit-episode:confusor-{index}", at=NOW + timedelta(minutes=index))
        outcomes.append(outcome.outcome)

    # The first several occurrences must always be admitted -- there is no
    # history yet to suspect them from (see "never a permanent verdict at
    # first sight").
    assert outcomes[0] == "created"
    assert outcomes[1] == "created"
    # By the time enough tight-geometry recurrence has accumulated, a later
    # occurrence is suspected and blocked -- the actual defect this
    # milestone exists to fix.
    assert "blocked_scene_confusor_suspected" in outcomes
    blocked_index = outcomes.index("blocked_scene_confusor_suspected")
    blocked_outcome = _attempt(
        repository, CONFUSOR_JITTER[blocked_index], proposal_id="visit-episode:confusor-recheck", at=NOW + timedelta(hours=1),
    )
    assert blocked_outcome.outcome == "blocked_scene_confusor_suspected"
    assert blocked_outcome.visit_id is None
    assert blocked_outcome.event_id is None


def test_suspected_confusor_creates_no_partial_visit_or_media(repository: ProductRepository) -> None:
    """A blocked proposal must leave zero trace -- no MediaAsset, Visit, or
    Event -- exactly like `blocked_privacy_zone`/`blocked_missing_evidence`
    already guarantee. This is also the property that keeps the mechanism
    from ever being able to *cause* Visit fragmentation/duplication: it can
    only ever prevent a Visit from being created, never create an extra
    one."""

    _activate(repository)
    for index, box in enumerate(CONFUSOR_JITTER):
        _attempt(repository, box, proposal_id=f"visit-episode:confusor-{index}", at=NOW + timedelta(minutes=index))

    with repository.session_factory() as session:
        visit_count_before = session.scalar(select(func.count(VisitModel.id)))
        event_count_before = session.scalar(select(func.count(EventModel.id)))
        media_count_before = session.scalar(select(func.count(MediaAssetModel.id)))

    outcome = _attempt(
        repository, CONFUSOR_JITTER[0], proposal_id="visit-episode:confusor-extra", at=NOW + timedelta(hours=2),
    )
    assert outcome.outcome == "blocked_scene_confusor_suspected"

    with repository.session_factory() as session:
        assert session.scalar(select(func.count(VisitModel.id))) == visit_count_before
        assert session.scalar(select(func.count(EventModel.id))) == event_count_before
        assert session.scalar(select(func.count(MediaAssetModel.id))) == media_count_before


# --- 2. A real animal recurring at a popular, geometrically-varied spot -----


def test_real_animal_repeatedly_at_a_popular_perch_is_retained(repository: ProductRepository) -> None:
    """The core recall-safety property this milestone's own replay
    simulation found missing from a naive (occurrence-count-only) design:
    many different real sightings at the same general, popular location
    must never be suppressed just because they recur -- their own
    geometric spread (different birds, different poses) is real,
    measurable evidence they are not one static artifact."""

    _activate(repository)
    outcomes = []
    for index, box in enumerate(POPULAR_PERCH_BOXES):
        outcome = _attempt(
            repository, box, proposal_id=f"visit-episode:popular-perch-{index}",
            at=NOW + timedelta(hours=index), confidence=0.4 + 0.05 * index,
        )
        outcomes.append(outcome.outcome)
    assert outcomes == ["created"] * len(POPULAR_PERCH_BOXES)


# --- 3. One stationary genuine bird visit cannot alone build suspicion ------


def test_stationary_genuine_bird_single_long_visit_is_never_suspected(repository: ProductRepository) -> None:
    """A single proposal is one bounded episode regardless of how long the
    underlying visit lasted -- a five-minute motionless perch contributes
    exactly one occurrence, structurally incapable of ever reaching
    `min_occurrences_to_suspect` by itself."""

    _activate(repository)
    outcome = _attempt(repository, CONFUSOR_BOX, proposal_id="visit-episode:stationary-real-bird", at=NOW)
    assert outcome.outcome == "created"


# --- 4. Human-reviewed genuine animal prevents unsafe future suppression ----


def test_human_reviewed_real_animal_protects_region_from_future_suspicion(repository: ProductRepository) -> None:
    _activate(repository)
    # Build up enough tight-geometry recurrence that a further occurrence
    # would ordinarily be suspected.
    created_visit_id = None
    for index, box in enumerate(CONFUSOR_JITTER[:3]):
        outcome = _attempt(repository, box, proposal_id=f"visit-episode:reviewed-region-{index}", at=NOW + timedelta(minutes=index))
        if outcome.outcome == "created":
            created_visit_id = outcome.visit_id
    assert created_visit_id is not None

    # A genuine human review confirms this specific candidate is a real
    # animal (any non-`false_positive` label).
    repository.create_review_label(
        ReviewCorrectionCreate(
            target_type="visit", target_id=created_visit_id, label="house_finch",
            review_origin="human", reviewer_identity="test-reviewer",
        ),
        created_at=NOW + timedelta(minutes=10),
    )

    # A later occurrence at the same geometry, which would otherwise be
    # suspected, must now be protected.
    outcome = _attempt(
        repository, CONFUSOR_JITTER[3], proposal_id="visit-episode:reviewed-region-protected", at=NOW + timedelta(hours=1),
    )
    assert outcome.outcome == "created"


def test_non_authoritative_review_does_not_protect_a_region(repository: ProductRepository) -> None:
    """An `agent_diagnostic` (or omitted-origin) review is durably recorded
    but never authoritative (see docs/review-decision-provenance-
    contract.md) -- it must not be able to protect a region either, since
    that would let a non-human assessment silently gain the same authority
    a genuine human correction has."""

    _activate(repository)
    created_visit_id = None
    for index, box in enumerate(CONFUSOR_JITTER[:3]):
        outcome = _attempt(repository, box, proposal_id=f"visit-episode:nonauth-{index}", at=NOW + timedelta(minutes=index))
        if outcome.outcome == "created":
            created_visit_id = outcome.visit_id
    assert created_visit_id is not None

    repository.create_review_label(
        ReviewCorrectionCreate(
            target_type="visit", target_id=created_visit_id, label="house_finch",
            review_origin="agent_diagnostic", reviewer_identity="claude-test-session",
        ),
        created_at=NOW + timedelta(minutes=10),
    )

    outcome = _attempt(
        repository, CONFUSOR_JITTER[3], proposal_id="visit-episode:nonauth-followup", at=NOW + timedelta(hours=1),
    )
    assert outcome.outcome == "blocked_scene_confusor_suspected"


def test_reviewed_false_positive_is_named_in_the_persisted_reason(repository: ProductRepository) -> None:
    _activate(repository)
    created_visit_id = None
    for index, box in enumerate(CONFUSOR_JITTER[:3]):
        outcome = _attempt(repository, box, proposal_id=f"visit-episode:revfalse-{index}", at=NOW + timedelta(minutes=index))
        if outcome.outcome == "created":
            created_visit_id = outcome.visit_id
    assert created_visit_id is not None

    repository.create_review_label(
        ReviewCorrectionCreate(
            target_type="visit", target_id=created_visit_id, label="false_positive",
            review_origin="human", reviewer_identity="test-reviewer",
        ),
        created_at=NOW + timedelta(minutes=10),
    )
    outcome = _attempt(
        repository, CONFUSOR_JITTER[3], proposal_id="visit-episode:revfalse-followup", at=NOW + timedelta(hours=1),
    )
    assert outcome.outcome == "blocked_scene_confusor_suspected"
    assert outcome.reason == "recurring_geometry_with_reviewed_false_history"


# --- 5. Camera reconfiguration invalidates stale regions --------------------


def _complete_setup(repository: ProductRepository):
    return repository.complete_camera_setup(
        CameraSetupCompleteRequest(
            camera_name="Backyard feeder", stream_name="Feeder view", provider_key="external_url",
            config={"url": "https://camera.local/still.jpg", "notes": "North feeder"},
            zones=[{
                "name": "Feeder", "zone_type": "feeder",
                "polygon": [Point(x=0.2, y=0.2), Point(x=0.8, y=0.2), Point(x=0.8, y=0.8), Point(x=0.2, y=0.8)],
            }],
            enable_monitoring=False, idempotency_key="scene-confusor-setup-001",
        )
    )


def test_camera_reconfiguration_purges_stale_regions_for_that_stream(repository: ProductRepository) -> None:
    completed = _complete_setup(repository)
    stream_id = completed.stream.id
    _activate(repository)
    for index, box in enumerate(CONFUSOR_JITTER):
        _attempt(
            repository, box, proposal_id=f"visit-episode:invalidation-{index}", at=NOW + timedelta(minutes=index),
            stream_id=stream_id,
        )
    assert _region_count(repository) > 0

    before = repository.get_camera_configuration_edit(stream_id)
    assert before is not None
    preview_request = CameraConfigurationImpactPreviewRequest(
        provider_key="external_url",
        config={"url": "https://camera.local/new-still.jpg"},
        secret_actions={},
        expected_state_token=before.state_token,
    )
    preview = repository.preview_camera_configuration(stream_id, preview_request)
    assert preview is not None
    assert preview.restart_required is True  # a URL/geometry-affecting change, not a cosmetic one

    apply_request = CameraConfigurationApplyRequest(
        **preview_request.model_dump(), preview_token=preview.preview_token,
        idempotency_key="scene-confusor-apply-001", restart_monitoring=False,
    )
    applied = repository.apply_camera_configuration(stream_id, apply_request)
    assert applied is not None

    assert _region_count(repository) == 0


def test_cosmetic_camera_edit_does_not_purge_regions(repository: ProductRepository) -> None:
    """`restart_required=False` (a display-name/notes-only change) must
    leave durable recurring-geometry history intact -- invalidation is
    scoped to genuinely geometry-affecting changes only."""

    completed = _complete_setup(repository)
    stream_id = completed.stream.id
    _activate(repository)
    for index, box in enumerate(CONFUSOR_JITTER):
        _attempt(
            repository, box, proposal_id=f"visit-episode:cosmetic-{index}", at=NOW + timedelta(minutes=index),
            stream_id=stream_id,
        )
    before_count = _region_count(repository)
    assert before_count > 0

    before = repository.get_camera_configuration_edit(stream_id)
    assert before is not None
    preview_request = CameraConfigurationImpactPreviewRequest(
        provider_key="external_url", config={"notes": "Updated feeder note"}, secret_actions={},
        expected_state_token=before.state_token,
    )
    preview = repository.preview_camera_configuration(stream_id, preview_request)
    assert preview is not None
    assert preview.restart_required is False

    apply_request = CameraConfigurationApplyRequest(
        **preview_request.model_dump(), preview_token=preview.preview_token,
        idempotency_key="scene-confusor-cosmetic-apply-001", restart_monitoring=False,
    )
    applied = repository.apply_camera_configuration(stream_id, apply_request)
    assert applied is not None

    assert _region_count(repository) == before_count


# --- 6. Counterfactual lineage integration -----------------------------------


def test_scene_confusor_outcome_is_recognized_by_counterfactual_lineage() -> None:
    """Extends, not replaces, the existing rejected/suppressed Detection
    Attribution vocabulary (see docs/rejected-detection-attribution-
    contract.md): a `blocked_scene_confusor_suspected` outcome must be
    classified as `admission_rejected`, never fall through to
    `insufficient_counterfactual_lineage` for an outcome the ledger
    actually has a recorded fact for."""

    assert "blocked_scene_confusor_suspected" in ADMISSION_REJECTED_OUTCOMES


# --- 7. Bounded per-Stream history lookup ------------------------------------


def test_region_history_is_bounded_per_stream(repository: ProductRepository) -> None:
    """Guards against a Review-Queue-style O(N-history) defect: the number
    of durable regions retained for one Stream never exceeds
    `max_regions_per_stream`, regardless of how many distinct geometries
    have ever been observed."""

    _activate(repository)
    distinct_locations = DEFAULT_MAX_REGIONS_PER_STREAM + 20
    for index in range(distinct_locations):
        # Spread boxes widely across the frame so every one starts its own
        # distinct region (never matches a prior one).
        column = (index % 10) * 0.09
        row = (index // 10) * 0.09
        box = (column, row, column + 0.03, row + 0.03)
        _attempt(repository, box, proposal_id=f"visit-episode:bounded-{index}", at=NOW + timedelta(minutes=index))

    assert _region_count(repository) <= DEFAULT_MAX_REGIONS_PER_STREAM
