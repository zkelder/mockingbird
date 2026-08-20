"""Perception Replay Regression Harness v1: `admission_replay.py` bridge.

Proves the *wiring*, not the admission policy itself (that policy is already
covered by `test_candidate_visit_authority.py`/`test_candidate_visit_
repository.py`): a replay-assembled `AssembledVisitProposal` reaches the
real, unmodified Stage 7 gates through an isolated, disposable repository,
never the real product database, with deterministic logical-time semantics.
"""
from __future__ import annotations

from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image
from sqlalchemy import select

from mockingbird.observation.admission_replay import (
    AdmissionReplayError,
    IsolatedAdmissionRepository,
    admission_report_to_json,
    evaluate_shadow_admission,
    require_replay_stream_id,
)
from mockingbird.observation.contracts import EvidenceCandidate
from mockingbird.observation.visit_episode_assembler import AssembledVisitProposal, BoundaryDecision
from mockingbird.repository.product_repository import EventModel, ObservationCandidateVisitModel, VisitModel
from mockingbird.storage.database import DEFAULT_DB_URL

STREAM_ID = "replay:fixture-feeder"
NOW = datetime(2026, 1, 1, tzinfo=UTC)


def _real_jpeg_bytes(*, size: tuple[int, int] = (640, 480)) -> bytes:
    """A genuinely PIL-decodable JPEG -- `evidence_scoring._score` hard-
    rejects (`candidate_undecodable`) anything that isn't, so a fixture must
    supply real image bytes, not merely bytes shaped like a JPEG header."""

    buffer = BytesIO()
    Image.new("RGB", size, color=(80, 140, 90)).save(buffer, format="JPEG")
    return buffer.getvalue()


JPEG_BYTES = _real_jpeg_bytes()


def _proposal(
    *,
    proposal_id: str = "assembled:fixture-1",
    stream_id: str = STREAM_ID,
    start_offset_ms: int = 0,
    end_offset_ms: int = 4000,
    constituent_generation_ids: tuple[str, ...] = ("gen-1",),
    assembly_decisions: tuple[BoundaryDecision, ...] = (),
    ambiguous_adjacent_proposal_ids: tuple[str, ...] = (),
    continuation_pending: bool = False,
) -> AssembledVisitProposal:
    return AssembledVisitProposal(
        proposal_id=proposal_id,
        stream_id=stream_id,
        broad_class="animal",
        start_offset_ms=start_offset_ms,
        end_offset_ms=end_offset_ms,
        constituent_generation_ids=constituent_generation_ids,
        constituent_track_ids=("track-1",),
        supporting_frame_ids=("frame-1", "frame-2"),
        source_capture_frame_ids=(),
        evidence_candidate_ids=("replay:0",),
        assembly_decisions=assembly_decisions,
        ambiguous_adjacent_proposal_ids=ambiguous_adjacent_proposal_ids,
        continuation_pending=continuation_pending,
    )


def _evidence(*, generation_id: str = "gen-1", media_asset_id: str = "replay:0") -> EvidenceCandidate:
    return EvidenceCandidate(
        media_asset_id=media_asset_id,
        stream_id=STREAM_ID,
        role="tracked_best",
        captured_at=NOW,
        frame_id=media_asset_id,
        source_offset_ms=0,
        width=640,
        height=480,
        subject_geometry=(0.3, 0.3, 0.6, 0.6),
        track_generation_id=generation_id,
    )


def test_require_replay_stream_id_rejects_a_non_replay_identity() -> None:
    with pytest.raises(AdmissionReplayError, match="stream_id_not_replay_namespaced"):
        require_replay_stream_id("stream-real-backyard-feeder")
    require_replay_stream_id("replay:anything")  # does not raise


def test_isolated_repository_never_touches_the_real_default_database(tmp_path: Path) -> None:
    """The isolated repository's own `db_url` must never resolve to
    `database_url_from_env()`'s real default -- proving isolation is a
    property of *this call*, not merely an assumption."""

    with IsolatedAdmissionRepository(directory=tmp_path, stream_id=STREAM_ID, activation_boundary_at=NOW) as repository:
        assert str(tmp_path) in repository.db_url
        assert repository.db_url != DEFAULT_DB_URL
        assert "data/mockingbird.sqlite3" not in repository.db_url


def test_isolated_repository_refuses_a_non_replay_stream_id(tmp_path: Path) -> None:
    with pytest.raises(AdmissionReplayError, match="stream_id_not_replay_namespaced"):
        with IsolatedAdmissionRepository(directory=tmp_path, stream_id="stream-real", activation_boundary_at=NOW):
            pass  # pragma: no cover - must never be reached


def test_isolated_repository_without_directory_creates_and_removes_a_temp_dir() -> None:
    captured_db_url: str | None = None
    with IsolatedAdmissionRepository(stream_id=STREAM_ID, activation_boundary_at=NOW) as repository:
        captured_db_url = repository.db_url
        db_path = Path(captured_db_url.removeprefix("sqlite:///"))
        assert db_path.exists()
        temp_dir = db_path.parent
    # Cleaned up on exit -- nothing left behind for a caller to accidentally reuse.
    assert not temp_dir.exists()


def test_evaluate_shadow_admission_creates_a_real_isolated_visit(tmp_path: Path) -> None:
    proposal = _proposal()
    evidence = (_evidence(),)
    with IsolatedAdmissionRepository(directory=tmp_path, stream_id=STREAM_ID, activation_boundary_at=NOW) as repository:
        report = evaluate_shadow_admission(
            (proposal,),
            repository=repository,
            stream_id=STREAM_ID,
            evidence_candidates=evidence,
            evidence_bytes={"replay:0": JPEG_BYTES},
            base_observed_at=NOW,
        )
        assert report.outcome_counts.get("created") == 1
        outcome = report.outcomes[0]
        assert outcome.created
        assert outcome.visit_id is not None
        assert outcome.event_id is not None
        assert outcome.observed_at == NOW  # start_offset_ms == 0

        # Really persisted, in the isolated DB alone -- not merely reported.
        # A fresh `ProductRepository` seeds its own unrelated demo content
        # (`seed_if_empty`), so assert on this proposal's own ledger/ids
        # specifically rather than a global row count.
        with repository.session_factory() as session:
            assert session.get(VisitModel, outcome.visit_id) is not None
            assert session.get(EventModel, outcome.event_id) is not None
            assert session.get(ObservationCandidateVisitModel, proposal.proposal_id) is not None


def test_evaluate_shadow_admission_uses_logical_time_from_start_offset_ms(tmp_path: Path) -> None:
    proposal = _proposal(start_offset_ms=90_000, end_offset_ms=95_000)
    evidence = (_evidence(),)
    with IsolatedAdmissionRepository(directory=tmp_path, stream_id=STREAM_ID, activation_boundary_at=NOW) as repository:
        report = evaluate_shadow_admission(
            (proposal,), repository=repository, stream_id=STREAM_ID,
            evidence_candidates=evidence, evidence_bytes={"replay:0": JPEG_BYTES}, base_observed_at=NOW,
        )
        outcome = report.outcomes[0]
        assert (outcome.observed_at - NOW).total_seconds() == 90.0


def test_evaluate_shadow_admission_blocks_before_authority_activation(tmp_path: Path) -> None:
    """A proposal observed before the activation boundary must never create
    a candidate, even though evidence/lineage are otherwise valid --
    mirroring production's own `blocked_pre_activation` rule exactly."""

    proposal = _proposal(start_offset_ms=0)
    evidence = (_evidence(),)
    later_activation = datetime(2026, 1, 1, 0, 5, tzinfo=UTC)
    with IsolatedAdmissionRepository(
        directory=tmp_path, stream_id=STREAM_ID, activation_boundary_at=later_activation,
    ) as repository:
        report = evaluate_shadow_admission(
            (proposal,), repository=repository, stream_id=STREAM_ID,
            evidence_candidates=evidence, evidence_bytes={"replay:0": JPEG_BYTES}, base_observed_at=NOW,
        )
        assert report.outcomes[0].outcome == "blocked_pre_activation"


def test_evaluate_shadow_admission_reports_missing_evidence_honestly(tmp_path: Path) -> None:
    """No fabricated bytes: a candidate with no real bytes behind it is
    honestly skipped (mirroring `candidate_visit_adapter._build_evidence_
    items`'s own "skip, never fabricate" discipline), which correctly
    leaves this proposal with zero real evidence items -- the repository's
    own `blocked_missing_evidence` pre-check, ahead of the quality gate."""

    proposal = _proposal()
    evidence = (_evidence(),)
    with IsolatedAdmissionRepository(directory=tmp_path, stream_id=STREAM_ID, activation_boundary_at=NOW) as repository:
        report = evaluate_shadow_admission(
            (proposal,), repository=repository, stream_id=STREAM_ID,
            evidence_candidates=evidence, evidence_bytes={}, base_observed_at=NOW,
        )
        outcome = report.outcomes[0]
        assert outcome.outcome == "blocked_missing_evidence"
        assert outcome.evidence_bytes_available_count == 0
        assert outcome.evidence_candidate_count == 1


def test_ambiguous_cluster_admits_at_most_one_winner(tmp_path: Path) -> None:
    """Two mutually-ambiguous proposals: arbitration picks exactly one
    winner (the longer constituent chain, per `_arbitration_key`); the other
    still correctly blocks -- at most one Visit per ambiguous cluster,
    exactly like the live path this bridge reuses unmodified."""

    winner = _proposal(
        proposal_id="assembled:winner", start_offset_ms=0, end_offset_ms=4000,
        constituent_generation_ids=("gen-1", "gen-2"),
        assembly_decisions=(BoundaryDecision("gen-1", "gen-2", "merge_same_visit", "bounded_gap_compatible_geometry", gap_ms=1000),),
        ambiguous_adjacent_proposal_ids=("assembled:loser",),
    )
    loser = _proposal(
        proposal_id="assembled:loser", start_offset_ms=5000, end_offset_ms=9000,
        ambiguous_adjacent_proposal_ids=("assembled:winner",),
    )
    evidence = (
        _evidence(generation_id="gen-1", media_asset_id="replay:0"),
        _evidence(generation_id="gen-2", media_asset_id="replay:1"),
    )
    with IsolatedAdmissionRepository(directory=tmp_path, stream_id=STREAM_ID, activation_boundary_at=NOW) as repository:
        report = evaluate_shadow_admission(
            (winner, loser), repository=repository, stream_id=STREAM_ID,
            evidence_candidates=evidence,
            evidence_bytes={"replay:0": JPEG_BYTES, "replay:1": JPEG_BYTES},
            base_observed_at=NOW,
        )
        by_id = {item.proposal_id: item for item in report.outcomes}
        assert by_id["assembled:winner"].outcome == "created"
        assert by_id["assembled:loser"].outcome == "blocked_ambiguous_boundary"
        assert report.arbitration.resolved_winner_ids == frozenset({"assembled:winner"})


def test_repeated_attempt_for_the_same_proposal_is_idempotent(tmp_path: Path) -> None:
    proposal = _proposal()
    evidence = (_evidence(),)
    with IsolatedAdmissionRepository(directory=tmp_path, stream_id=STREAM_ID, activation_boundary_at=NOW) as repository:
        first = evaluate_shadow_admission(
            (proposal,), repository=repository, stream_id=STREAM_ID,
            evidence_candidates=evidence, evidence_bytes={"replay:0": JPEG_BYTES}, base_observed_at=NOW,
        )
        second = evaluate_shadow_admission(
            (proposal,), repository=repository, stream_id=STREAM_ID,
            evidence_candidates=evidence, evidence_bytes={"replay:0": JPEG_BYTES}, base_observed_at=NOW,
        )
        assert first.outcomes[0].outcome == "created"
        assert second.outcomes[0].outcome == "idempotent_repeat"
        assert second.outcomes[0].visit_id == first.outcomes[0].visit_id  # same Visit, never duplicated
        with repository.session_factory() as session:
            ledger_rows = session.scalars(
                select(ObservationCandidateVisitModel).where(
                    ObservationCandidateVisitModel.proposal_id == proposal.proposal_id
                )
            ).all()
            assert len(ledger_rows) == 1  # one ledger row for this proposal, never duplicated


def test_admission_report_to_json_is_deterministic_and_path_free(tmp_path: Path) -> None:
    proposal = _proposal()
    evidence = (_evidence(),)
    with IsolatedAdmissionRepository(directory=tmp_path, stream_id=STREAM_ID, activation_boundary_at=NOW) as repository:
        report = evaluate_shadow_admission(
            (proposal,), repository=repository, stream_id=STREAM_ID,
            evidence_candidates=evidence, evidence_bytes={"replay:0": JPEG_BYTES}, base_observed_at=NOW,
        )
        payload = admission_report_to_json(report)
        assert payload["outcome_counts"] == {"created": 1}
        assert str(tmp_path) not in repr(payload)
        assert payload == admission_report_to_json(report)  # deterministic re-projection
