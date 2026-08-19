"""Stage 7 end-to-end wiring: real `Tracklet` -> `assemble_visit_episodes` ->
`AssembledVisitProposal` -> `CandidateVisitAuthorityAdapter` -> real
`ProductRepository` (isolated `tmp_path` SQLite, never the product database).
Complements `tests/test_candidate_visit_authority.py` (pure gate unit tests)
and `tests/test_candidate_visit_repository.py` (repository transaction
tests) by proving the full pipeline the contract doc describes actually
wires together.
"""

from __future__ import annotations

from dataclasses import asdict, replace
from datetime import UTC, datetime
import json
from pathlib import Path

import pytest

from mockingbird.observation.candidate_visit_adapter import CandidateVisitAuthorityAdapter
from mockingbird.observation.candidate_visit_authority import ObservationAuthorityMode
from mockingbird.observation.contracts import (
    CLASSIFIER_SAME_FRAME_EVIDENCE_ROLE,
    EvidenceCandidate,
    GeometryAttribution,
)
from mockingbird.observation.visit_episode_assembler import Tracklet, assemble_visit_episodes
from mockingbird.repository.product_repository import (
    MediaAssetModel,
    ObservationCandidateVisitModel,
    ProductRepository,
    VisitEvidenceLinkModel,
    VisitModel,
)

STREAM_ID = "stream-backyard-feeder"
FEEDER_ZONE_ID = "zone-feeder"
NOW = datetime(2026, 8, 8, 12, 0, 0, tzinfo=UTC)
JPEG_BYTES = b"\xff\xd8\xff\xe0" + b"1" * 128 + b"\xff\xd9"


@pytest.fixture
def repository(tmp_path: Path) -> ProductRepository:
    repo = ProductRepository(db_url=f"sqlite:///{tmp_path / 'mockingbird.sqlite3'}", media_root=tmp_path / "media")
    yield repo
    repo.close()


def _tracklet(generation_id: str, start: int, end: int, **overrides: object) -> Tracklet:
    values: dict[str, object] = {
        "generation_id": generation_id,
        "stream_id": STREAM_ID,
        "broad_class": "animal",
        "start_offset_ms": start,
        "end_offset_ms": end,
        "start_bounding_box": (0.4, 0.4, 0.5, 0.5),
        "end_bounding_box": (0.42, 0.42, 0.52, 0.52),
        "geometry_envelope": (0.4, 0.4, 0.52, 0.52),
        "terminal_reason": "maximum_unsupported_duration",
        "track_ids": (f"{generation_id}-track",),
        "source_capture_frame_ids": (f"{generation_id}-frame-1", f"{generation_id}-frame-2"),
        "evidence_candidate_ids": ("shadow-burst:hash-id", "shadow-burst:hash-ctx"),
        "zone_id": FEEDER_ZONE_ID,
    }
    values.update(overrides)
    return Tracklet(**values)


def _evidence_candidates() -> tuple[EvidenceCandidate, ...]:
    return (
        EvidenceCandidate(
            media_asset_id="shadow-burst:hash-id",
            stream_id=STREAM_ID,
            role="high_resolution_burst",
            captured_at=NOW,
            frame_id="gen-1-frame-1",
            source_offset_ms=500,
            width=1920,
            height=1080,
            subject_geometry=(0.4, 0.4, 0.5, 0.5),
            track_generation_id="gen-1",
            quality_facts=(
                ("decodable", True),
                ("temporal_alignment", "aligned"),
                ("track_supported", True),
            ),
        ),
        EvidenceCandidate(
            media_asset_id="shadow-burst:hash-ctx",
            stream_id=STREAM_ID,
            role="context",
            captured_at=NOW,
            frame_id="gen-1-frame-2",
            source_offset_ms=100,
            width=1920,
            height=1080,
            subject_geometry=(0.35, 0.35, 0.55, 0.55),
            track_generation_id="gen-1",
            quality_facts=(
                ("decodable", True),
                ("temporal_alignment", "aligned"),
                ("track_supported", True),
            ),
        ),
    )


def _adapter(repository: ProductRepository) -> CandidateVisitAuthorityAdapter:
    return CandidateVisitAuthorityAdapter(
        repository,
        detector_provenance="onnx-cuda",
        tracker_provenance="frame-driven-onnx-cuda-v1",
        provider_key="frame-driven-onnx-cuda",
    )


def _activate(repository: ProductRepository, *, now: datetime = NOW) -> None:
    repository.set_observation_authority_mode(ObservationAuthorityMode.candidate_visit, stream_id=STREAM_ID, now=now)


def test_end_to_end_assembled_proposal_creates_one_candidate_visit(repository: ProductRepository) -> None:
    tracklet = _tracklet("gen-1", 0, 4500)
    result = assemble_visit_episodes((tracklet,))
    assert len(result.proposals) == 1
    proposal = result.proposals[0]

    _activate(repository)
    candidates = _evidence_candidates()
    evidence_bytes = {"shadow-burst:hash-id": JPEG_BYTES, "shadow-burst:hash-ctx": JPEG_BYTES}
    outcome = _adapter(repository).attempt_candidate(
        proposal, evidence_candidates=candidates, evidence_bytes=evidence_bytes, observed_at=NOW,
    )
    assert outcome.created
    assert outcome.visit_id is not None

    with repository.session_factory() as session:
        visit = session.get(VisitModel, outcome.visit_id)
        assert visit is not None
        assert visit.review_status == "needs_review"
        ledger = session.get(ObservationCandidateVisitModel, proposal.proposal_id)
        assert ledger is not None
        assert ledger.detector_provenance == "onnx-cuda"
        assert ledger.tracker_provenance == "frame-driven-onnx-cuda-v1"
        assert ledger.provider_key == "frame-driven-onnx-cuda"
        assert ledger.selected_identification_media_asset_id is not None
        assert ledger.selected_context_media_asset_id is not None


def test_geometry_attribution_flows_from_evidence_candidate_to_persisted_media_asset(
    repository: ProductRepository,
) -> None:
    """Localization Attribution / Detection Geometry Lineage v1 (see
    docs/localization-attribution-contract.md): an `EvidenceCandidate`'s own
    `geometry_attribution` -- computed upstream by the provider/live-session
    layer, never recomputed here -- must survive the full adapter ->
    repository path onto the persisted MediaAsset's own
    `geometry_attribution_json`, verbatim."""
    tracklet = _tracklet("gen-1", 0, 4500)
    proposal = assemble_visit_episodes((tracklet,)).proposals[0]
    _activate(repository)

    attribution = GeometryAttribution(
        geometry_source="detector", geometry_source_offset_ms=500, geometry_source_observation_id="obs-1",
        geometry_source_confidence=0.66, same_frame=False, geometry_evidence_gap_ms=9_551,
    )
    identification, context = _evidence_candidates()
    candidates = (replace(identification, geometry_attribution=attribution), context)
    evidence_bytes = {"shadow-burst:hash-id": JPEG_BYTES, "shadow-burst:hash-ctx": JPEG_BYTES}
    outcome = _adapter(repository).attempt_candidate(
        proposal, evidence_candidates=candidates, evidence_bytes=evidence_bytes, observed_at=NOW,
    )
    assert outcome.created

    with repository.session_factory() as session:
        ledger = session.get(ObservationCandidateVisitModel, proposal.proposal_id)
        assert ledger is not None
        identification_media = session.get(MediaAssetModel, ledger.selected_identification_media_asset_id)
        assert identification_media is not None
        assert json.loads(identification_media.geometry_attribution_json) == asdict(attribution)
        # The context candidate never had a `geometry_attribution` set --
        # honestly `None`, never inherited from its sibling.
        context_media = session.get(MediaAssetModel, ledger.selected_context_media_asset_id)
        assert context_media is not None
        assert context_media.geometry_attribution_json is None


def test_shadow_mode_end_to_end_creates_nothing(repository: ProductRepository) -> None:
    tracklet = _tracklet("gen-1", 0, 4500)
    proposal = assemble_visit_episodes((tracklet,)).proposals[0]
    candidates = _evidence_candidates()
    evidence_bytes = {"shadow-burst:hash-id": JPEG_BYTES, "shadow-burst:hash-ctx": JPEG_BYTES}
    outcome = _adapter(repository).attempt_candidate(
        proposal, evidence_candidates=candidates, evidence_bytes=evidence_bytes, observed_at=NOW,
    )
    assert outcome.outcome == "blocked_shadow_mode"
    assert not outcome.created


def test_missing_evidence_bytes_are_skipped_not_fabricated(repository: ProductRepository) -> None:
    """A candidate the adapter has no real bytes for must never appear as a
    persisted evidence item; if *nothing* has bytes, creation fails safely."""

    tracklet = _tracklet("gen-1", 0, 4500)
    proposal = assemble_visit_episodes((tracklet,)).proposals[0]
    _activate(repository)
    outcome = _adapter(repository).attempt_candidate(
        proposal, evidence_candidates=_evidence_candidates(), evidence_bytes={}, observed_at=NOW,
    )
    assert outcome.outcome == "blocked_missing_evidence"
    assert not outcome.created


def test_partial_evidence_bytes_still_creates_a_candidate(repository: ProductRepository) -> None:
    tracklet = _tracklet("gen-1", 0, 4500)
    proposal = assemble_visit_episodes((tracklet,)).proposals[0]
    _activate(repository)
    outcome = _adapter(repository).attempt_candidate(
        proposal, evidence_candidates=_evidence_candidates(),
        evidence_bytes={"shadow-burst:hash-id": JPEG_BYTES}, observed_at=NOW,
    )
    assert outcome.created
    with repository.session_factory() as session:
        ledger = session.get(ObservationCandidateVisitModel, proposal.proposal_id)
        assert ledger.selected_identification_media_asset_id is not None
        assert ledger.selected_context_media_asset_id is None


def test_multi_tracklet_merged_episode_creates_one_candidate_with_full_lineage(repository: ProductRepository) -> None:
    """Two tracklets the assembler merges into one Visit episode must
    produce exactly one candidate Visit whose ledger lineage spans both
    constituent generations -- proving the adapter consumes the assembler's
    *merged* proposal, not one candidate per raw tracklet."""

    first = _tracklet("gen-1", 0, 1500)
    second = _tracklet("gen-2", 6000, 7500)  # within merge_gap_ms(15000) of gen-1's end
    result = assemble_visit_episodes((first, second))
    assert len(result.proposals) == 1
    proposal = result.proposals[0]
    assert proposal.constituent_generation_ids == ("gen-1", "gen-2")

    _activate(repository)
    evidence_bytes = {"shadow-burst:hash-id": JPEG_BYTES, "shadow-burst:hash-ctx": JPEG_BYTES}
    outcome = _adapter(repository).attempt_candidate(
        proposal, evidence_candidates=_evidence_candidates(), evidence_bytes=evidence_bytes, observed_at=NOW,
    )
    assert outcome.created
    with repository.session_factory() as session:
        import json

        ledger = session.get(ObservationCandidateVisitModel, proposal.proposal_id)
        assert json.loads(ledger.constituent_generation_ids_json) == ["gen-1", "gen-2"]


def test_ambiguous_assembled_boundary_is_blocked_end_to_end(repository: ProductRepository) -> None:
    """Two real tracklets whose gap (20s) sits inside the assembler's own
    `ambiguous_gap_ms` window (15s-45s) with compatible geometry produce two
    genuinely `ambiguous_boundary`-linked proposals (see "Ambiguity policy"
    in docs/tracklet-visit-assembly-contract.md) -- proving Stage 7's own
    "blocked according to explicit policy" (scenario 29) against real
    assembler output, not just a hand-built fixture."""

    first = _tracklet("gen-1", 0, 1000)
    second = _tracklet("gen-2", 21_000, 22_000)  # 20s gap: > merge_gap_ms, < ambiguous_gap_ms
    result = assemble_visit_episodes((first, second))
    assert len(result.proposals) == 2
    assert all(proposal.ambiguous_adjacent_proposal_ids for proposal in result.proposals)

    _activate(repository)
    evidence_bytes = {"shadow-burst:hash-id": JPEG_BYTES, "shadow-burst:hash-ctx": JPEG_BYTES}
    for proposal in result.proposals:
        outcome = _adapter(repository).attempt_candidate(
            proposal, evidence_candidates=_evidence_candidates(), evidence_bytes=evidence_bytes, observed_at=NOW,
        )
        assert outcome.outcome == "blocked_ambiguous_boundary"
        assert not outcome.created

    with repository.session_factory() as session:
        from sqlalchemy import func, select

        assert session.scalar(select(func.count(ObservationCandidateVisitModel.proposal_id))) == 0


def test_authority_mode_never_affects_assembler_output(repository: ProductRepository) -> None:
    """Scenario 10 / rollback: the shadow assembler's own decisions are
    computed with zero knowledge of, or dependency on, current authority
    state -- toggling authority on/off must not change what
    `assemble_visit_episodes` itself produces."""

    tracklet = _tracklet("gen-1", 0, 4500)
    before_toggle = assemble_visit_episodes((tracklet,))
    _activate(repository)
    repository.set_observation_authority_mode(ObservationAuthorityMode.shadow, stream_id=STREAM_ID, now=NOW)
    after_toggle = assemble_visit_episodes((tracklet,))
    assert before_toggle.proposals[0].proposal_id == after_toggle.proposals[0].proposal_id
    assert before_toggle.proposals == after_toggle.proposals


def test_repository_failure_is_caught_and_recorded_not_raised(
    repository: ProductRepository, monkeypatch: pytest.MonkeyPatch,
) -> None:
    tracklet = _tracklet("gen-1", 0, 4500)
    proposal = assemble_visit_episodes((tracklet,)).proposals[0]
    _activate(repository)

    def _boom(self, request):
        raise ValueError("observation_candidate_visit_persistence_failed")

    monkeypatch.setattr(ProductRepository, "create_candidate_visit_from_proposal", _boom)
    outcome = _adapter(repository).attempt_candidate(
        proposal, evidence_candidates=_evidence_candidates(),
        evidence_bytes={"shadow-burst:hash-id": JPEG_BYTES}, observed_at=NOW,
    )
    assert outcome.outcome == "failed"
    assert not outcome.created

    status = repository.get_observation_authority_state(stream_id=STREAM_ID)
    assert status.failure_count == 1


# --------------------------------------------------------------------------
# Same-Frame Species Evidence v1 (see docs/same-frame-species-evidence-
# contract.md)
# --------------------------------------------------------------------------


def _same_frame_candidate(
    media_asset_id: str = "shadow-same-frame:hash-sf", *, generation_id: str = "gen-1",
) -> EvidenceCandidate:
    return EvidenceCandidate(
        media_asset_id=media_asset_id,
        stream_id=STREAM_ID,
        role=CLASSIFIER_SAME_FRAME_EVIDENCE_ROLE,
        captured_at=NOW,
        frame_id=f"{generation_id}-frame-1",
        source_offset_ms=500,
        width=640,
        height=480,
        subject_geometry=(0.4, 0.4, 0.5, 0.5),
        track_generation_id=generation_id,
        quality_facts=(("content_hash", media_asset_id.split(":")[-1]), ("temporal_alignment", "same_frame")),
        geometry_attribution=GeometryAttribution(
            geometry_source="detector", geometry_source_offset_ms=500, geometry_source_observation_id="obs-1",
            geometry_source_confidence=0.9, same_frame=True, geometry_evidence_gap_ms=0,
        ),
    )


def test_same_frame_evidence_persisted_alongside_identification_without_displacing_it(
    repository: ProductRepository,
) -> None:
    """A `classifier_same_frame` candidate becomes its own persisted
    MediaAsset/VisitEvidenceLink, but never wins the `identification`/
    `context` slot -- the human-facing burst/context selections are
    unaffected by its mere presence."""

    tracklet = _tracklet(
        "gen-1", 0, 4500,
        evidence_candidate_ids=("shadow-burst:hash-id", "shadow-burst:hash-ctx", "shadow-same-frame:hash-sf"),
    )
    proposal = assemble_visit_episodes((tracklet,)).proposals[0]
    _activate(repository)
    candidates = _evidence_candidates() + (_same_frame_candidate(),)
    evidence_bytes = {
        "shadow-burst:hash-id": JPEG_BYTES,
        "shadow-burst:hash-ctx": JPEG_BYTES,
        "shadow-same-frame:hash-sf": JPEG_BYTES,
    }
    outcome = _adapter(repository).attempt_candidate(
        proposal, evidence_candidates=candidates, evidence_bytes=evidence_bytes, observed_at=NOW,
    )
    assert outcome.created

    with repository.session_factory() as session:
        ledger = session.get(ObservationCandidateVisitModel, proposal.proposal_id)
        assert ledger is not None
        # Unchanged from the no-same-frame case: still the burst/context
        # picks, never displaced by the new role.
        identification_media = session.get(MediaAssetModel, ledger.selected_identification_media_asset_id)
        assert identification_media is not None and identification_media.evidence_role == "identification"
        context_media = session.get(MediaAssetModel, ledger.selected_context_media_asset_id)
        assert context_media is not None and context_media.evidence_role == "context"

        links = session.query(VisitEvidenceLinkModel).filter_by(visit_id=ledger.visit_id).all()
        same_frame_links = [link for link in links if link.evidence_role == CLASSIFIER_SAME_FRAME_EVIDENCE_ROLE]
        assert len(same_frame_links) == 1
        same_frame_media = session.get(MediaAssetModel, same_frame_links[0].media_asset_id)
        assert same_frame_media is not None
        assert same_frame_media.evidence_role == CLASSIFIER_SAME_FRAME_EVIDENCE_ROLE
        assert same_frame_media.image_width == 640 and same_frame_media.image_height == 480
        assert not same_frame_links[0].is_primary
        attribution = json.loads(same_frame_media.geometry_attribution_json)
        assert attribution["same_frame"] is True
        assert attribution["geometry_evidence_gap_ms"] == 0


def test_same_frame_evidence_missing_bytes_degrades_without_blocking_candidate(
    repository: ProductRepository,
) -> None:
    """Species inference safety net proven one layer down: a same-frame
    candidate this adapter has no real bytes for is honestly skipped --
    never fabricated -- and never blocks identification/context admission."""

    tracklet = _tracklet(
        "gen-1", 0, 4500,
        evidence_candidate_ids=("shadow-burst:hash-id", "shadow-burst:hash-ctx", "shadow-same-frame:hash-sf"),
    )
    proposal = assemble_visit_episodes((tracklet,)).proposals[0]
    _activate(repository)
    candidates = _evidence_candidates() + (_same_frame_candidate(),)
    evidence_bytes = {"shadow-burst:hash-id": JPEG_BYTES, "shadow-burst:hash-ctx": JPEG_BYTES}
    outcome = _adapter(repository).attempt_candidate(
        proposal, evidence_candidates=candidates, evidence_bytes=evidence_bytes, observed_at=NOW,
    )
    assert outcome.created
    with repository.session_factory() as session:
        ledger = session.get(ObservationCandidateVisitModel, proposal.proposal_id)
        links = session.query(VisitEvidenceLinkModel).filter_by(visit_id=ledger.visit_id).all()
        assert not any(link.evidence_role == CLASSIFIER_SAME_FRAME_EVIDENCE_ROLE for link in links)


def test_at_most_one_same_frame_evidence_persisted_when_multiple_generations_merge(
    repository: ProductRepository,
) -> None:
    """A multi-tracklet-merged Visit could in principle carry a same-frame
    candidate from each constituent generation; the milestone's "at most
    ONE same-frame evidence image per Visit/candidate" bound is enforced
    deterministically here, not left to chance."""

    first = _tracklet(
        "gen-1", 0, 1500,
        evidence_candidate_ids=("shadow-burst:hash-id", "shadow-burst:hash-ctx", "shadow-same-frame:hash-sf-1"),
    )
    second = _tracklet(
        "gen-2", 6000, 7500,
        evidence_candidate_ids=("shadow-same-frame:hash-sf-2",),
    )
    proposal = assemble_visit_episodes((first, second)).proposals[0]
    assert proposal.constituent_generation_ids == ("gen-1", "gen-2")

    _activate(repository)
    candidates = _evidence_candidates() + (
        _same_frame_candidate("shadow-same-frame:hash-sf-1", generation_id="gen-1"),
        _same_frame_candidate("shadow-same-frame:hash-sf-2", generation_id="gen-2"),
    )
    evidence_bytes = {
        "shadow-burst:hash-id": JPEG_BYTES,
        "shadow-burst:hash-ctx": JPEG_BYTES,
        "shadow-same-frame:hash-sf-1": JPEG_BYTES,
        "shadow-same-frame:hash-sf-2": JPEG_BYTES,
    }
    outcome = _adapter(repository).attempt_candidate(
        proposal, evidence_candidates=candidates, evidence_bytes=evidence_bytes, observed_at=NOW,
    )
    assert outcome.created
    with repository.session_factory() as session:
        ledger = session.get(ObservationCandidateVisitModel, proposal.proposal_id)
        links = session.query(VisitEvidenceLinkModel).filter_by(visit_id=ledger.visit_id).all()
        same_frame_links = [link for link in links if link.evidence_role == CLASSIFIER_SAME_FRAME_EVIDENCE_ROLE]
        assert len(same_frame_links) == 1
