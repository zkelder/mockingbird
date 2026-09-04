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


@dataclass(frozen=True)
class _Corroboration:
    """Duck-typed `confidence_evidence` for these tests -- mirrors
    `product_repository._CorroborationFacts` exactly, without importing the
    repository (this gate stays product-repository-free)."""

    strong_detection_count: int | None = None
    detection_count: int | None = None
    max_consecutive_detector_confirmed_frames: int | None = None
    max_single_generation_detection_count: int | None = None


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


# --- All-Alternate Subject Evidence Recall Correctness v1 -------------------
#
# Root cause (see docs/all-alternate-subject-evidence-recall-correctness-v1-
# report.md): `evidence_scoring.score_proposal_evidence` deliberately never
# lets a `classifier_same_frame` item compete for `identification`/`context`
# (Same-Frame Species Evidence v1 -- it must never outrank a real
# high-resolution burst). That is correct. But when the real burst's own
# bytes never survive to admission (lost before harvest, or independently
# failing the scorer's own eligibility checks -- a real, disclosed,
# bounded residual, not a hypothetical), the proposal's *only* persisted,
# byte-backed evidence can be its own same-frame snapshot -- a real,
# tracker/detector-confirmed, provably-this-exact-frame subject capture,
# not "no evidence." Before this milestone's fix, that shape was
# indistinguishable, at this gate, from `test_alternate_only_evidence_is_
# rejected` above and was discarded the same way. `test_same_frame_only_
# evidence_is_admitted_as_last_resort` below is this defect's exact,
# faithful RED (fails against the pre-fix gate)/GREEN (passes against the
# fixed one) reproducer at the pure-gate level; `tests/test_same_frame_
# species_evidence.py::test_same_frame_only_evidence_creates_a_reviewable_
# visit` proves the same fact end to end through the real repository.


def test_same_frame_only_evidence_is_admitted_as_last_resort() -> None:
    """The exact defect this milestone fixes: a proposal whose only
    persisted evidence is its own `classifier_same_frame` snapshot must not
    vanish -- a real, geometrically-proven subject capture exists, it is
    just not identification-grade. RED against the pre-fix gate (asserted
    `reject_no_identification_or_context`); GREEN here."""

    decision = evaluate_evidence_admission(_Proposal(), [_Item("classifier_same_frame")])
    assert decision.admitted
    assert decision.outcome == "admit"
    assert decision.reason == "evidence_sufficient_for_review:same_frame_primary"


def test_same_frame_fallback_only_used_when_no_identification_or_context() -> None:
    """A real identification/context pick still wins outright -- the
    same-frame fallback is a last resort, never a competitor. Distinguishes
    the ordinary `evidence_sufficient_for_review` reason from the fallback's
    own `:same_frame_primary` suffix, proving the fallback did not fire."""

    items = [_Item("classifier_same_frame", subject_geometry=None), _Item("identification")]
    decision = evaluate_evidence_admission(_Proposal(), items)
    assert decision.admitted
    assert decision.reason == "evidence_sufficient_for_review"


def test_same_frame_fallback_still_requires_valid_geometry() -> None:
    """The new fallback is not a bypass: every check after primary
    resolution still applies, unchanged, to whatever `primary` turned out
    to be -- including the same-frame item."""

    decision = evaluate_evidence_admission(
        _Proposal(), [_Item("classifier_same_frame", subject_geometry=None)],
    )
    assert not decision.admitted
    assert decision.outcome == "reject_subject_geometry_invalid"


def test_same_frame_fallback_still_rejects_insufficient_detector_corroboration() -> None:
    """Precision safety bar: a same-frame-only proposal with the exact
    never-strong, bare-minimum-detection signature `reject_insufficient_
    detector_corroboration` already exists to catch (see docs/hard-negative-
    visit-admission-precision-species-escalation-correctness-v1-report.md)
    must still be rejected -- this fix only changes what counts as a
    *candidate* primary, never the corroboration bar a real subject capture
    must still clear. Mirrors real field data: MockingBird's own 2026-09-03
    persistent red-flag confusor's weakest generations show exactly this
    shape (1 detection, confidence 0.121-0.184, never strong)."""

    decision = evaluate_evidence_admission(
        _Proposal(),
        [_Item("classifier_same_frame")],
        confidence_evidence=_Corroboration(strong_detection_count=0, detection_count=1),
    )
    assert not decision.admitted
    assert decision.outcome == "reject_insufficient_detector_corroboration"


def test_same_frame_fallback_admits_a_real_weak_but_corroborated_encounter() -> None:
    """A genuinely present, brief real subject -- more than the tracker's
    own bare confirmation floor, even though never a *strong* detection --
    now gets a real, reviewable Visit instead of vanishing. Detection
    count/confidence grounded in a real 2026-09-03 confirmed-real-bird
    track generation (`stream-5288453906fb:frame-track:80735c36ab6a3cd599a7`,
    8 detections, max confidence 0.479, single generation) -- reused here
    only to ground the corroboration math in a real signature, not to
    assert this reproduces that generation's own recorded admission-
    authority outcome (a different, unrelated ambiguous-boundary-arbitration
    defect, out of this milestone's scope -- see the milestone report's own
    "v12 reproduced misses" section)."""

    decision = evaluate_evidence_admission(
        _Proposal(),
        [_Item("classifier_same_frame")],
        confidence_evidence=_Corroboration(strong_detection_count=0, detection_count=8),
    )
    assert decision.admitted
    assert decision.reason == "evidence_sufficient_for_review:same_frame_primary"


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
