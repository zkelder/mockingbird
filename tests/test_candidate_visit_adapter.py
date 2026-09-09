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
import errno
import json
from pathlib import Path

import pytest

from mockingbird.observation.candidate_visit_adapter import (
    _MAX_PERSISTENCE_ATTEMPTS,
    _PERSISTENCE_CONTENTION_CODE,
    CandidateVisitAuthorityAdapter,
)
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


# =============================================================================
# Pending-Proposal Evidence Preservation & Arbitration Fallback Correctness
# v1: `priority_evidence_ids_for_proposal`/`CandidateVisitAuthorityAdapter.
# priority_evidence_ids` -- the bounded preview `engine_runtime._compute_
# protected_evidence_ids` uses to decide which handful of a still-pending
# proposal's own evidence is worth protecting.
# =============================================================================


def test_priority_evidence_ids_picks_the_real_identification_candidate() -> None:
    from mockingbird.observation.candidate_visit_adapter import priority_evidence_ids_for_proposal

    tracklet = _tracklet("gen-1", 0, 4500)
    proposal = assemble_visit_episodes((tracklet,)).proposals[0]
    picks = priority_evidence_ids_for_proposal(
        proposal, evidence_candidates=_evidence_candidates(), media={"shadow-burst:hash-id": JPEG_BYTES},
    )
    assert "shadow-burst:hash-id" in picks


def test_priority_evidence_ids_is_empty_with_no_media_at_all() -> None:
    """Without any real bytes, `evidence_scoring._score` hard-rejects every
    candidate (`candidate_unavailable`) unless metadata already declares
    `decodable=True` (this file's own `_evidence_candidates()` fixture
    does; a real, live-captured `high_resolution_burst` candidate this
    project actually constructs never does -- see `camera_node_live.py`).
    This is deliberate, honest behavior, not a bug: a preview with nothing
    real to preview correctly protects nothing, rather than fabricating a
    pick for bytes that do not exist."""
    from mockingbird.observation.candidate_visit_adapter import priority_evidence_ids_for_proposal
    from mockingbird.observation.contracts import EvidenceCandidate

    tracklet = _tracklet("gen-1", 0, 4500)
    proposal = assemble_visit_episodes((tracklet,)).proposals[0]
    undeclared = EvidenceCandidate(
        media_asset_id="shadow-burst:hash-id", stream_id=STREAM_ID, role="high_resolution_burst",
        captured_at=NOW, frame_id="gen-1-frame-1", track_generation_id="gen-1",
        subject_geometry=(0.4, 0.4, 0.5, 0.5), width=1920, height=1080,
    )
    picks = priority_evidence_ids_for_proposal(proposal, evidence_candidates=(undeclared,), media=None)
    assert picks == ()


def test_priority_evidence_ids_only_considers_this_proposals_own_evidence() -> None:
    """A candidate belonging to a *different* proposal's own generation
    must never be picked, even if real bytes exist for it -- mirrors
    `score_proposal_evidence`'s own existing `available_ids`/`track_
    generation_id` scoping exactly, never a new filter invented here."""
    from mockingbird.observation.candidate_visit_adapter import priority_evidence_ids_for_proposal
    from mockingbird.observation.contracts import EvidenceCandidate

    tracklet = _tracklet("gen-1", 0, 4500)
    proposal = assemble_visit_episodes((tracklet,)).proposals[0]
    unrelated = EvidenceCandidate(
        media_asset_id="shadow-burst:unrelated", stream_id=STREAM_ID, role="high_resolution_burst",
        captured_at=NOW, frame_id="gen-2-frame-1", track_generation_id="gen-2",
        subject_geometry=(0.4, 0.4, 0.5, 0.5), width=1920, height=1080,
    )
    picks = priority_evidence_ids_for_proposal(
        proposal, evidence_candidates=(*_evidence_candidates(), unrelated),
        media={"shadow-burst:hash-id": JPEG_BYTES, "shadow-burst:unrelated": JPEG_BYTES},
    )
    assert "shadow-burst:unrelated" not in picks


def test_adapter_priority_evidence_ids_uses_its_own_configured_scoring_bounds() -> None:
    """`CandidateVisitAuthorityAdapter.priority_evidence_ids` threads its
    own `scoring_bounds` through exactly like `attempt_candidate` does --
    a caller with a tighter/looser configured bound sees it reflected in
    the preview, never a hardcoded default silently substituted."""
    from mockingbird.observation.evidence_scoring import EvidenceScoringBounds

    tracklet = _tracklet("gen-1", 0, 4500)
    proposal = assemble_visit_episodes((tracklet,)).proposals[0]
    adapter = CandidateVisitAuthorityAdapter(
        None, scoring_bounds=EvidenceScoringBounds(max_candidates=1),  # repository unused by this call
    )
    picks = adapter.priority_evidence_ids(
        proposal, evidence_candidates=_evidence_candidates(), media={"shadow-burst:hash-id": JPEG_BYTES},
    )
    # With `max_candidates=1`, only one of the two real candidates is even
    # considered at all -- proving the bound actually reached the
    # underlying scorer, not merely accepted and ignored.
    assert len(picks) <= 1


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
# Concurrent Candidate Visit Persistence Reliability v1 (see docs/concurrent-
# candidate-visit-persistence-reliability-v1-report.md): deterministic,
# mock-based proof of the bounded retry/classification logic itself -- fast
# and independent of real thread-timing luck. Complements the slower, real-
# SQLite-lock end-to-end proof in
# tests/test_concurrent_candidate_visit_persistence_reliability.py.
# --------------------------------------------------------------------------


def test_non_contention_failure_is_not_retried(
    repository: ProductRepository, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A permanent (non-contention) repository failure must fail on the
    very first attempt, exactly as before this milestone -- retrying it
    would waste time for no benefit and could mask a genuine bug."""

    tracklet = _tracklet("gen-1", 0, 4500)
    proposal = assemble_visit_episodes((tracklet,)).proposals[0]
    _activate(repository)
    calls = []

    def _boom(self, request):
        calls.append(request.proposal.proposal_id)
        raise ValueError("observation_candidate_visit_persistence_failed")

    monkeypatch.setattr(ProductRepository, "create_candidate_visit_from_proposal", _boom)
    outcome = _adapter(repository).attempt_candidate(
        proposal, evidence_candidates=_evidence_candidates(),
        evidence_bytes={"shadow-burst:hash-id": JPEG_BYTES}, observed_at=NOW,
    )
    assert outcome.outcome == "failed"
    assert len(calls) == 1  # no retry for a non-retryable code
    status = repository.get_observation_authority_state(stream_id=STREAM_ID)
    assert status.failure_count == 1
    assert status.last_failure_code == "observation_candidate_visit_persistence_failed"


def test_disk_full_write_failure_rolls_back_atomically_and_is_not_retried(
    repository: ProductRepository, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Product Operations & First-Observation Completion v1: closes the one
    real test-depth gap an independent storage-survival audit found --
    every existing test above proves the *mechanism* generically (a bare
    `ValueError` with the right code, injected at
    `create_candidate_visit_from_proposal` itself); none proves it
    specifically for the real shape a genuinely full disk produces. This
    injects a literal `OSError(errno.ENOSPC, ...)` at the real Host
    media-write function (`_write_media_file` -- the exact function the
    audit named), and lets the real, unmodified
    `create_candidate_visit_from_proposal` / `_create_candidate_visit_locked`
    transactional write path and the real `CandidateVisitAuthorityAdapter`
    run for real underneath it -- proving, not merely arguing, that a
    disk-full condition: (1) fails the whole attempt atomically (zero
    partial rows survive -- SQLAlchemy's `session.begin()` rollback), (2)
    surfaces as the same typed `"failed"` outcome, never a crash, and (3)
    is never retried (an `OSError`-shaped failure is not the classified
    -retryable SQLite-contention code)."""

    tracklet = _tracklet("gen-1", 0, 4500)
    proposal = assemble_visit_episodes((tracklet,)).proposals[0]
    _activate(repository)

    def _table_counts() -> tuple[int, int, int]:
        from sqlalchemy import func, select

        with repository.session_factory() as session:
            return (
                session.scalar(select(func.count(ObservationCandidateVisitModel.proposal_id))) or 0,
                session.scalar(select(func.count(VisitModel.id))) or 0,
                session.scalar(select(func.count(MediaAssetModel.id))) or 0,
            )

    # `ProductRepository.__init__` unconditionally seeds two demo Visits
    # (`demo_data.seed_product_data()`, confirmed by direct inspection --
    # never zero) on a genuinely fresh database, so the correct atomicity
    # proof is "the counts did not change," never "the counts are zero" --
    # a naive absolute-zero assertion here is a real bug in *this test*,
    # not evidence of a production defect (caught by this milestone's own
    # real Core-gate run, not assumed).
    before_ledger_count, before_visit_count, before_media_count = _table_counts()

    def _disk_full(self: ProductRepository, filename: str, content: bytes) -> tuple[str, Path]:
        raise OSError(errno.ENOSPC, "No space left on device")

    monkeypatch.setattr(ProductRepository, "_write_media_file", _disk_full)

    outcome = _adapter(repository).attempt_candidate(
        proposal, evidence_candidates=_evidence_candidates(),
        evidence_bytes={"shadow-burst:hash-id": JPEG_BYTES}, observed_at=NOW,
    )

    assert outcome.outcome == "failed"
    assert not outcome.created

    status = repository.get_observation_authority_state(stream_id=STREAM_ID)
    assert status.failure_count == 1  # exactly one attempt -- never retried

    # The core survival proof: atomic rollback left zero *new* rows -- no
    # candidate-visit ledger row, Visit, or MediaAsset from the failed
    # attempt, never a corrupt/half-written record, and never a regression
    # against whatever legitimately existed before this attempt.
    after_ledger_count, after_visit_count, after_media_count = _table_counts()
    assert after_ledger_count == before_ledger_count
    assert after_visit_count == before_visit_count
    assert after_media_count == before_media_count


def test_transient_persistence_contention_recovers_via_bounded_retry(
    repository: ProductRepository, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The demonstrated root cause (a real `sqlalchemy.exc.OperationalError`
    -- SQLite lock/busy contention under real concurrent multi-Stream
    writes, see `ProductRepository.create_candidate_visit_from_proposal`'s
    own docstring) recovers instead of silently losing the candidate: a
    proposal that fails with the classified-retryable code on its first two
    attempts must still end up created, not lost, on the real, unmodified
    repository call it eventually succeeds on."""

    tracklet = _tracklet("gen-1", 0, 4500)
    proposal = assemble_visit_episodes((tracklet,)).proposals[0]
    _activate(repository)
    real_create = ProductRepository.create_candidate_visit_from_proposal
    calls = []

    def _flaky(self, request):
        calls.append(request.proposal.proposal_id)
        if len(calls) < 3:
            raise ValueError(_PERSISTENCE_CONTENTION_CODE)
        return real_create(self, request)

    monkeypatch.setattr(ProductRepository, "create_candidate_visit_from_proposal", _flaky)
    outcome = _adapter(repository).attempt_candidate(
        proposal, evidence_candidates=_evidence_candidates(), evidence_bytes={"shadow-burst:hash-id": JPEG_BYTES},
        observed_at=NOW,
    )
    assert outcome.created  # recovered -- never silently lost
    assert len(calls) == 3
    # A candidate lost this way must never also show up as a recorded
    # failure -- the eventual success is the only fact of record.
    status = repository.get_observation_authority_state(stream_id=STREAM_ID)
    assert status.failure_count == 0


def test_persistent_contention_exhausts_bounded_retry_and_is_recorded_failed(
    repository: ProductRepository, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Contention that never clears must still give up -- bounded recovery,
    never an infinite retry loop -- and the resulting `"failed"` outcome
    must be honestly distinguishable, in the durable per-Stream diagnostic,
    from a failure that was never retried at all."""

    tracklet = _tracklet("gen-1", 0, 4500)
    proposal = assemble_visit_episodes((tracklet,)).proposals[0]
    _activate(repository)
    calls = []

    def _always_contended(self, request):
        calls.append(request.proposal.proposal_id)
        raise ValueError(_PERSISTENCE_CONTENTION_CODE)

    monkeypatch.setattr(ProductRepository, "create_candidate_visit_from_proposal", _always_contended)
    outcome = _adapter(repository).attempt_candidate(
        proposal, evidence_candidates=_evidence_candidates(), evidence_bytes={"shadow-burst:hash-id": JPEG_BYTES},
        observed_at=NOW,
    )
    assert outcome.outcome == "failed"
    assert not outcome.created
    assert len(calls) == _MAX_PERSISTENCE_ATTEMPTS  # bounded -- not one, not unbounded
    status = repository.get_observation_authority_state(stream_id=STREAM_ID)
    # Exactly one recorded failure per genuinely-lost candidate, never one
    # per internal retry attempt.
    assert status.failure_count == 1
    assert status.last_failure_code == f"{_PERSISTENCE_CONTENTION_CODE}:retries_exhausted"


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


# =============================================================================
# Multi-Subject Visit Assembly & Review v1, Phase 2 (see docs/multi-subject-
# visit-assembly-review-v1.md): full pipeline (real Tracklet -> real
# assemble_visit_episodes, unmodified -> real adapter -> real repository)
# coverage for concurrent-sibling Event reuse. Complements the repository-
# transaction-level tests in test_candidate_visit_repository.py by proving
# the actual assembler-produced `concurrent_sibling_proposal_ids` -- never
# hand-built facts -- drives the same grouping end to end.
# =============================================================================


def _evidence_candidates_for(
    generation_id: str, suffix: str, *, box: tuple[float, float, float, float],
) -> tuple[EvidenceCandidate, ...]:
    """A per-subject identification/context pair, mirroring `_evidence_
    candidates()` but parametrized so several simultaneous subjects can each
    carry their own distinct, non-colliding evidence."""

    return (
        EvidenceCandidate(
            media_asset_id=f"shadow-burst:hash-{suffix}-id",
            stream_id=STREAM_ID,
            role="high_resolution_burst",
            captured_at=NOW,
            frame_id=f"{generation_id}-frame-1",
            source_offset_ms=500,
            width=1920,
            height=1080,
            subject_geometry=box,
            track_generation_id=generation_id,
            quality_facts=(("decodable", True), ("temporal_alignment", "aligned"), ("track_supported", True)),
        ),
        EvidenceCandidate(
            media_asset_id=f"shadow-burst:hash-{suffix}-ctx",
            stream_id=STREAM_ID,
            role="context",
            captured_at=NOW,
            frame_id=f"{generation_id}-frame-2",
            source_offset_ms=100,
            width=1920,
            height=1080,
            subject_geometry=box,
            track_generation_id=generation_id,
            quality_facts=(("decodable", True), ("temporal_alignment", "aligned"), ("track_supported", True)),
        ),
    )


def test_two_simultaneous_subjects_produce_two_visits_sharing_one_event(repository: ProductRepository) -> None:
    """Case D (docs/multi-subject-visit-assembly-review-v1.md "Design
    acceptance cases"): two genuinely overlapping tracklets -> the real,
    unmodified `assemble_visit_episodes` recognizes them as concurrent
    siblings (Phase 1) -> the real adapter/repository must persist two
    distinct Visits sharing one Event, with zero evidence cross-
    contamination."""

    left = _tracklet(
        "gen-left", 0, 8000,
        start_bounding_box=(0.05, 0.05, 0.2, 0.2), end_bounding_box=(0.05, 0.05, 0.2, 0.2),
        evidence_candidate_ids=("shadow-burst:hash-left-id", "shadow-burst:hash-left-ctx"),
        source_capture_frame_ids=("gen-left-frame-1", "gen-left-frame-2"),
    )
    right = _tracklet(
        "gen-right", 2000, 10000,
        start_bounding_box=(0.8, 0.8, 0.95, 0.95), end_bounding_box=(0.8, 0.8, 0.95, 0.95),
        evidence_candidate_ids=("shadow-burst:hash-right-id", "shadow-burst:hash-right-ctx"),
        source_capture_frame_ids=("gen-right-frame-1", "gen-right-frame-2"),
    )
    result = assemble_visit_episodes((left, right))
    assert result.assembled_proposal_count == 2
    left_proposal = next(p for p in result.proposals if p.constituent_generation_ids == ("gen-left",))
    right_proposal = next(p for p in result.proposals if p.constituent_generation_ids == ("gen-right",))
    assert left_proposal.concurrent_sibling_proposal_ids == (right_proposal.proposal_id,)

    _activate(repository)
    candidates = _evidence_candidates_for("gen-left", "left", box=(0.05, 0.05, 0.2, 0.2)) + _evidence_candidates_for(
        "gen-right", "right", box=(0.8, 0.8, 0.95, 0.95),
    )
    evidence_bytes = {candidate.media_asset_id: JPEG_BYTES for candidate in candidates}
    adapter = _adapter(repository)
    left_outcome = adapter.attempt_candidate(
        left_proposal, evidence_candidates=candidates, evidence_bytes=evidence_bytes, observed_at=NOW,
    )
    right_outcome = adapter.attempt_candidate(
        right_proposal, evidence_candidates=candidates, evidence_bytes=evidence_bytes, observed_at=NOW,
    )
    assert left_outcome.created and right_outcome.created
    assert left_outcome.visit_id != right_outcome.visit_id
    assert left_outcome.event_id == right_outcome.event_id

    with repository.session_factory() as session:
        left_links = {
            link.media_asset_id for link in session.query(VisitEvidenceLinkModel).filter_by(visit_id=left_outcome.visit_id)
        }
        right_links = {
            link.media_asset_id for link in session.query(VisitEvidenceLinkModel).filter_by(visit_id=right_outcome.visit_id)
        }
        assert left_links.isdisjoint(right_links)  # each subject's own evidence, never a sibling's
        left_visit = session.get(VisitModel, left_outcome.visit_id)
        right_visit = session.get(VisitModel, right_outcome.visit_id)
        # Gate B (species quality) is explicitly not this milestone -- both
        # subjects must independently stay unidentified at creation time.
        assert left_visit.species_guess is None and right_visit.species_guess is None


def test_three_simultaneous_subjects_share_one_event_nuthatch_and_two_finches(repository: ProductRepository) -> None:
    """Hard regression target (docs/roadmap.md "Multi-subject Visit
    correctness"): the real observed encounter shape -- one nuthatch, two
    finches, all present at once -- must produce three independent,
    evidence-backed subject Visits sharing one encounter Event, never
    collapsed to fewer, attempted out of admission order to prove the
    shared Event never depends on which subject is admitted first."""

    nuthatch = _tracklet(
        "nuthatch-center", 0, 9000,
        start_bounding_box=(0.4, 0.4, 0.5, 0.5), end_bounding_box=(0.4, 0.4, 0.5, 0.5),
        evidence_candidate_ids=("shadow-burst:hash-nuthatch-id", "shadow-burst:hash-nuthatch-ctx"),
        source_capture_frame_ids=("nuthatch-frame-1", "nuthatch-frame-2"),
    )
    finch_left = _tracklet(
        "finch-left", 1000, 6000,
        start_bounding_box=(0.05, 0.05, 0.2, 0.2), end_bounding_box=(0.05, 0.05, 0.2, 0.2),
        evidence_candidate_ids=("shadow-burst:hash-finch-left-id", "shadow-burst:hash-finch-left-ctx"),
        source_capture_frame_ids=("finch-left-frame-1", "finch-left-frame-2"),
    )
    finch_right = _tracklet(
        "finch-right", 2000, 7000,
        start_bounding_box=(0.8, 0.8, 0.95, 0.95), end_bounding_box=(0.8, 0.8, 0.95, 0.95),
        evidence_candidate_ids=("shadow-burst:hash-finch-right-id", "shadow-burst:hash-finch-right-ctx"),
        source_capture_frame_ids=("finch-right-frame-1", "finch-right-frame-2"),
    )
    result = assemble_visit_episodes((nuthatch, finch_left, finch_right))
    assert result.assembled_proposal_count == 3
    by_generation = {p.constituent_generation_ids[0]: p for p in result.proposals}
    assert set(by_generation) == {"nuthatch-center", "finch-left", "finch-right"}
    for proposal in by_generation.values():
        assert len(proposal.concurrent_sibling_proposal_ids) == 2  # full mutual recognition -- a 3-clique

    _activate(repository)
    candidates = (
        _evidence_candidates_for("nuthatch-center", "nuthatch", box=(0.4, 0.4, 0.5, 0.5))
        + _evidence_candidates_for("finch-left", "finch-left", box=(0.05, 0.05, 0.2, 0.2))
        + _evidence_candidates_for("finch-right", "finch-right", box=(0.8, 0.8, 0.95, 0.95))
    )
    evidence_bytes = {candidate.media_asset_id: JPEG_BYTES for candidate in candidates}
    adapter = _adapter(repository)
    # Attempted out of "natural" order (finch-right, nuthatch, finch-left)
    # to prove the shared Event never depends on admission order.
    outcomes = {
        "finch-right": adapter.attempt_candidate(
            by_generation["finch-right"], evidence_candidates=candidates, evidence_bytes=evidence_bytes, observed_at=NOW,
        ),
        "nuthatch-center": adapter.attempt_candidate(
            by_generation["nuthatch-center"], evidence_candidates=candidates, evidence_bytes=evidence_bytes, observed_at=NOW,
        ),
        "finch-left": adapter.attempt_candidate(
            by_generation["finch-left"], evidence_candidates=candidates, evidence_bytes=evidence_bytes, observed_at=NOW,
        ),
    }
    assert all(outcome.created for outcome in outcomes.values())
    event_ids = {outcome.event_id for outcome in outcomes.values()}
    assert len(event_ids) == 1  # one shared encounter
    visit_ids = {outcome.visit_id for outcome in outcomes.values()}
    assert len(visit_ids) == 3  # three distinct subjects, never collapsed

    expected_boxes = {
        "nuthatch-center": (0.4, 0.4, 0.5, 0.5),
        "finch-left": (0.05, 0.05, 0.2, 0.2),
        "finch-right": (0.8, 0.8, 0.95, 0.95),
    }
    with repository.session_factory() as session:
        for name, outcome in outcomes.items():
            ledger = session.get(ObservationCandidateVisitModel, outcome.proposal_id)
            assert json.loads(ledger.concurrent_sibling_proposal_ids_json) != []
            identification_media = session.get(MediaAssetModel, ledger.selected_identification_media_asset_id)
            assert identification_media is not None
            # Each Visit's own primary evidence box matches only its own
            # subject -- never silently substituted from a sibling's.
            assert tuple(json.loads(identification_media.normalized_track_box_json)) == expected_boxes[name]
        visits = session.query(VisitModel).filter_by(event_id=next(iter(event_ids))).all()
        assert len(visits) == 3
        assert all(visit.species_guess is None for visit in visits)


def test_one_bird_fragmented_across_merging_tracklets_produces_one_visit_no_sibling_grouping(
    repository: ProductRepository,
) -> None:
    """Regression target (docs/multi-subject-visit-assembly-review-v1.md
    "Design acceptance cases", F): ordinary sequential tracklet fragments of
    one real bird -- close enough in time/geometry for the real, unmodified
    assembler to merge them into one proposal -- must remain exactly one
    Visit, with an empty `concurrent_sibling_proposal_ids`, minting its own
    Event exactly as before this milestone. Fragmentation must never become
    worse merely because sibling-grouping metadata now exists."""

    first = _tracklet("gen-1", 0, 1500)
    second = _tracklet("gen-2", 6000, 7500)  # within merge_gap_ms(15000) of gen-1's end
    result = assemble_visit_episodes((first, second))
    assert result.assembled_proposal_count == 1
    proposal = result.proposals[0]
    assert proposal.concurrent_sibling_proposal_ids == ()

    _activate(repository)
    evidence_bytes = {"shadow-burst:hash-id": JPEG_BYTES, "shadow-burst:hash-ctx": JPEG_BYTES}
    outcome = _adapter(repository).attempt_candidate(
        proposal, evidence_candidates=_evidence_candidates(), evidence_bytes=evidence_bytes, observed_at=NOW,
    )
    assert outcome.created
    assert outcome.reason == "candidate_visit_created"  # its own new Event -- never a shared/grouped one
    # Not an absolute-count check: a fresh repository auto-seeds its own
    # demo walkthrough graph (`seed_if_empty`), so other Events/Visits
    # legitimately already exist. The correctness claim is that this one
    # merged proposal's own Event has exactly one Visit -- itself.
    with repository.session_factory() as session:
        visits = session.query(VisitModel).filter_by(event_id=outcome.event_id).all()
        assert [visit.id for visit in visits] == [outcome.visit_id]


def test_staggered_arrival_while_encounter_remains_active_shares_one_event(repository: ProductRepository) -> None:
    """Case E (docs/multi-subject-visit-assembly-review-v1.md "Design
    acceptance cases"): one subject leaves while another, later-arriving
    subject remains present -- a staggered, not fully nested, temporal
    overlap -- must still produce two Visits sharing one Event, each
    retaining its own correct temporal span."""

    early = _tracklet(
        "gen-early", 0, 4000,
        start_bounding_box=(0.05, 0.05, 0.2, 0.2), end_bounding_box=(0.05, 0.05, 0.2, 0.2),
        evidence_candidate_ids=("shadow-burst:hash-early-id", "shadow-burst:hash-early-ctx"),
        source_capture_frame_ids=("gen-early-frame-1", "gen-early-frame-2"),
    )
    late = _tracklet(
        "gen-late", 3000, 9000,
        start_bounding_box=(0.8, 0.8, 0.95, 0.95), end_bounding_box=(0.8, 0.8, 0.95, 0.95),
        evidence_candidate_ids=("shadow-burst:hash-late-id", "shadow-burst:hash-late-ctx"),
        source_capture_frame_ids=("gen-late-frame-1", "gen-late-frame-2"),
    )
    result = assemble_visit_episodes((early, late))
    assert result.assembled_proposal_count == 2
    early_proposal = next(p for p in result.proposals if p.constituent_generation_ids == ("gen-early",))
    late_proposal = next(p for p in result.proposals if p.constituent_generation_ids == ("gen-late",))
    assert early_proposal.concurrent_sibling_proposal_ids == (late_proposal.proposal_id,)
    assert early_proposal.start_offset_ms == 0 and early_proposal.end_offset_ms == 4000
    assert late_proposal.start_offset_ms == 3000 and late_proposal.end_offset_ms == 9000

    _activate(repository)
    candidates = _evidence_candidates_for("gen-early", "early", box=(0.05, 0.05, 0.2, 0.2)) + _evidence_candidates_for(
        "gen-late", "late", box=(0.8, 0.8, 0.95, 0.95),
    )
    evidence_bytes = {candidate.media_asset_id: JPEG_BYTES for candidate in candidates}
    adapter = _adapter(repository)
    early_outcome = adapter.attempt_candidate(
        early_proposal, evidence_candidates=candidates, evidence_bytes=evidence_bytes, observed_at=NOW,
    )
    late_outcome = adapter.attempt_candidate(
        late_proposal, evidence_candidates=candidates, evidence_bytes=evidence_bytes, observed_at=NOW,
    )
    assert early_outcome.created and late_outcome.created
    assert early_outcome.event_id == late_outcome.event_id
    assert early_outcome.visit_id != late_outcome.visit_id
