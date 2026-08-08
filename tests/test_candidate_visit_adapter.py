"""Stage 7 end-to-end wiring: real `Tracklet` -> `assemble_visit_episodes` ->
`AssembledVisitProposal` -> `CandidateVisitAuthorityAdapter` -> real
`ProductRepository` (isolated `tmp_path` SQLite, never the product database).
Complements `tests/test_candidate_visit_authority.py` (pure gate unit tests)
and `tests/test_candidate_visit_repository.py` (repository transaction
tests) by proving the full pipeline the contract doc describes actually
wires together.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from mockingbird.observation.candidate_visit_adapter import CandidateVisitAuthorityAdapter
from mockingbird.observation.candidate_visit_authority import ObservationAuthorityMode
from mockingbird.observation.contracts import EvidenceCandidate
from mockingbird.observation.visit_episode_assembler import Tracklet, assemble_visit_episodes
from mockingbird.repository.product_repository import ObservationCandidateVisitModel, ProductRepository, VisitModel

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
    repository.set_observation_authority_mode(ObservationAuthorityMode.candidate_visit, now=now)


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
    repository.set_observation_authority_mode(ObservationAuthorityMode.shadow, now=NOW)
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

    status = repository.get_observation_authority_state()
    assert status.failure_count == 1
