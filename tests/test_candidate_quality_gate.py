"""Product admission boundary between authority-approved candidates and the
Review Queue (Product requirement 2). Pure unit tests only -- repository
composition is proven end-to-end in `tests/test_candidate_visit_repository.py`
and `tests/test_candidate_visit_adapter.py`.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from mockingbird.observation.candidate_quality_gate import (
    EvidenceItemFacts,
    ProposalSupportFacts,
    evaluate_evidence_admission,
)


@dataclass(frozen=True)
class _Item:
    role: str
    content: bytes = b"\xff\xd8\xff\xd9"
    subject_geometry: tuple[float, float, float, float] | None = (0.4, 0.4, 0.6, 0.6)


@dataclass(frozen=True)
class _Proposal:
    constituent_generation_ids: tuple[str, ...] = ("gen-1",)
    broad_class: str = "animal"


def test_identification_with_valid_geometry_is_admitted() -> None:
    decision = evaluate_evidence_admission(_Proposal(), [_Item("identification")])
    assert decision.admitted
    assert decision.outcome == "admit"


def test_context_only_with_valid_geometry_is_admitted() -> None:
    """Identification and context may legitimately coincide (see
    evidence_scoring's "may coincide when only one usable candidate
    exists"); a context-only pick is still meaningfully selected evidence."""

    decision = evaluate_evidence_admission(_Proposal(), [_Item("context")])
    assert decision.admitted


def test_identification_preferred_over_context_when_both_present() -> None:
    items = [_Item("context", subject_geometry=None), _Item("identification")]
    decision = evaluate_evidence_admission(_Proposal(), items)
    assert decision.admitted  # the geometry-valid identification pick wins, not the bad context one


def test_alternate_only_evidence_is_rejected() -> None:
    """An `"alternate"` is by definition a candidate the scorer did not
    select as its best identification or context evidence -- admitting a
    Visit on alternates alone is exactly the "meaningless dark patch"
    failure mode this gate exists to prevent."""

    decision = evaluate_evidence_admission(_Proposal(), [_Item("alternate"), _Item("alternate")])
    assert not decision.admitted
    assert decision.outcome == "reject_no_identification_or_context"


def test_no_evidence_items_is_rejected() -> None:
    decision = evaluate_evidence_admission(_Proposal(), [])
    assert not decision.admitted
    assert decision.outcome == "reject_no_identification_or_context"


def test_missing_subject_geometry_is_rejected() -> None:
    decision = evaluate_evidence_admission(_Proposal(), [_Item("identification", subject_geometry=None)])
    assert not decision.admitted
    assert decision.outcome == "reject_subject_geometry_invalid"


def test_degenerate_zero_area_geometry_is_rejected() -> None:
    decision = evaluate_evidence_admission(
        _Proposal(), [_Item("identification", subject_geometry=(0.5, 0.5, 0.5, 0.9))],
    )
    assert not decision.admitted
    assert decision.outcome == "reject_subject_geometry_invalid"


def test_out_of_bounds_geometry_is_rejected() -> None:
    decision = evaluate_evidence_admission(
        _Proposal(), [_Item("identification", subject_geometry=(-0.1, 0.1, 0.5, 0.5))],
    )
    assert not decision.admitted
    assert decision.outcome == "reject_subject_geometry_invalid"


def test_falls_back_to_context_geometry_when_identification_lacks_one() -> None:
    """Identification is preferred by role, but when *it* lacks usable
    geometry and a context pick has one, the gate still honestly rejects --
    it does not silently swap in the context pick's box for a different
    role. This proves geometry is checked on the item actually selected as
    primary, not "any item with a box"."""

    items = [_Item("identification", subject_geometry=None), _Item("context")]
    decision = evaluate_evidence_admission(_Proposal(), items)
    assert not decision.admitted
    assert decision.outcome == "reject_subject_geometry_invalid"


def test_missing_constituent_generations_is_rejected() -> None:
    proposal = _Proposal(constituent_generation_ids=())
    decision = evaluate_evidence_admission(proposal, [_Item("identification")])
    assert not decision.admitted
    assert decision.outcome == "reject_insufficient_proposal_support"


def test_blank_broad_class_is_rejected() -> None:
    proposal = _Proposal(broad_class="  ")
    decision = evaluate_evidence_admission(proposal, [_Item("identification")])
    assert not decision.admitted
    assert decision.outcome == "reject_insufficient_proposal_support"


def test_decision_is_deterministic_for_same_inputs() -> None:
    items = [_Item("identification")]
    first = evaluate_evidence_admission(_Proposal(), items)
    second = evaluate_evidence_admission(_Proposal(), items)
    assert first == second


def test_candidate_evidence_item_structurally_satisfies_the_protocol() -> None:
    """`product_repository.CandidateEvidenceItem` must keep satisfying this
    gate's structural protocol without this module ever importing it."""
    from mockingbird.repository.product_repository import CandidateEvidenceItem

    item = CandidateEvidenceItem(
        engine_media_id="shadow-burst:hash-1", role="identification", content=b"\xff\xd8\xff\xd9",
        content_type="image/jpeg", width=1920, height=1080, captured_at=None,
        subject_geometry=(0.4, 0.4, 0.6, 0.6),
    )
    assert isinstance(item, EvidenceItemFacts)

    from mockingbird.repository.product_repository import CandidateVisitProposalFacts

    facts = CandidateVisitProposalFacts(
        proposal_id="visit-episode:fixture", stream_id="stream-1", zone_id=None, broad_class="animal",
        start_offset_ms=0, end_offset_ms=1000, constituent_generation_ids=("gen-1",),
        constituent_track_ids=("track-1",), source_capture_frame_ids=(), evidence_candidate_ids=(),
        limitation_facts=(), ambiguous_adjacent_proposal_ids=(), assembler_version="tracklet-visit-assembler-v1",
    )
    assert isinstance(facts, ProposalSupportFacts)


def test_candidate_quality_gate_module_has_no_product_repository_import() -> None:
    """Structural guard, the same convention every Stage 6.x/7 decision
    module in this package follows: this gate must stay pure so it can be
    the adapter's *and* the repository's shared, independently-testable
    judgment, never something that itself opens a database or a file."""

    source = Path("src/mockingbird/observation/candidate_quality_gate.py").read_text(encoding="utf-8")
    forbidden = (
        "mockingbird.repository", "mockingbird.storage", "mockingbird.api", "sqlalchemy",
        "import socket", "import requests", "from PIL", "import PIL",
    )
    for token in forbidden:
        assert token not in source, f"unexpected impure dependency: {token}"
