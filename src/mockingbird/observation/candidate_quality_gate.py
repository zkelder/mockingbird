"""Stage 7 product admission boundary: assembled proposal -> candidate
authority -> (this gate) -> Review Queue candidate.

Problem: `candidate_visit_authority.evaluate_candidate_authority` decides
whether a proposal is *allowed* to create a candidate Visit (mode,
activation, lineage, ambiguity, rate budget). It says nothing about whether
the evidence that survived is actually *worth a human's time* -- an
authority-approved proposal can still carry only a low-confidence
`"alternate"` pick, or a pick with no known subject location at all, and
`evidence_scoring.score_proposal_evidence` already flags exactly that with
its own existing `no_useful_evidence` fact and per-candidate
`subject_geometry`. This module composes those already-measured facts into
one conservative "reviewable enough" decision so the product prefers
"nothing surfaced" over "please review this meaningless dark patch."

Pure: no filesystem, network, CUDA/ONNX Runtime/OpenCV, product-repository,
or SQLAlchemy import -- the same structural convention every other Stage 6.x/7
decision module in this package follows
(`test_candidate_quality_gate_module_has_no_product_repository_import`). It
invents no new detector or evidence-quality threshold: every fact this gate
reads (`role`, `subject_geometry`, `constituent_generation_ids`,
`broad_class`) is already produced upstream by the unmodified assembler and
evidence scorer, never recomputed here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol, Sequence, runtime_checkable

QUALITY_GATE_VERSION = "candidate-quality-gate-v1"


@runtime_checkable
class EvidenceItemFacts(Protocol):
    """The only shape this gate needs from one already-selected, already
    bounded evidence item -- deliberately a structural `Protocol`, not an
    import of `product_repository.CandidateEvidenceItem`, so this module
    stays product-repository-free while `CandidateEvidenceItem` satisfies it
    unchanged (the same convention `candidate_visit_authority.ProposalLineage`
    already establishes for proposal facts)."""

    role: str
    content: bytes
    subject_geometry: tuple[float, float, float, float] | None


@runtime_checkable
class ProposalSupportFacts(Protocol):
    constituent_generation_ids: tuple[str, ...]
    broad_class: str


QualityOutcome = Literal[
    "admit",
    "reject_no_identification_or_context",
    "reject_subject_geometry_invalid",
    "reject_insufficient_proposal_support",
]

# Outcomes that mean the proposal never reached the Review Queue because of
# *this* gate specifically -- distinct from an authority-gate block, so a
# caller's diagnostics can report "why" separately from "was authority even
# on" (see docs/candidate-visit-authority-contract.md and the product-vertical
# -slice requirement to "count/report why" a proposal stayed shadow-only).
REJECTED_OUTCOMES: frozenset[QualityOutcome] = frozenset(
    {
        "reject_no_identification_or_context",
        "reject_subject_geometry_invalid",
        "reject_insufficient_proposal_support",
    }
)


@dataclass(frozen=True)
class QualityDecision:
    """One deterministic classification of whether already-authority-approved
    evidence is reviewable enough to actually persist. Reason strings are
    stable, sanitized codes -- never a raw exception message or path."""

    outcome: QualityOutcome
    reason: str

    @property
    def admitted(self) -> bool:
        return self.outcome == "admit"


def _valid_normalized_box(box: tuple[float, float, float, float] | None) -> bool:
    """A real, non-degenerate subject location -- not merely "a tuple exists".
    Mirrors the bounded normalized-box convention already used across the
    Observation Engine v2 media/burst contracts (for example
    `media_contracts._valid_box`, `burst_scheduler._valid_box`): four
    coordinates in `[0, 1]` with a positive area."""

    if box is None or len(box) != 4:
        return False
    left, top, right, bottom = box
    return 0.0 <= left < right <= 1.0 and 0.0 <= top < bottom <= 1.0


def evaluate_evidence_admission(
    proposal: ProposalSupportFacts,
    items: Sequence[EvidenceItemFacts],
) -> QualityDecision:
    """Classify one authority-approved candidate's already-selected,
    already-byte-backed evidence set.

    Deliberately conservative and composed only from existing signals:

    1. Proposal support: a genuine assembled proposal always carries at
       least one constituent track generation and a broad subject class;
       this is a defense-in-depth structural check, not a new policy --
       the assembler and tracker already guarantee it upstream.
    2. At least one *meaningfully selected* candidate exists: the scorer's
       own `identification`/`context` picks (never a leftover `"alternate"`
       alone, which by definition lost to something better or nothing at
       all -- see `evidence_scoring.score_proposal_evidence`'s
       `no_useful_evidence` fact, which is exactly "identification is None
       and context is None").
    3. That candidate's own subject geometry is a real, non-degenerate box
       -- a reviewer must be able to see *where* the claimed subject is, not
       just that some frame was captured.

    Decodability is intentionally not re-checked here: only a candidate the
    scorer already judged `eligible` (which already excludes
    `candidate_undecodable`/`candidate_unavailable`) can ever reach this
    gate as an `identification`/`context` pick, so re-deciding it a second
    time here would duplicate, not add, an existing judgment.
    """

    if not proposal.constituent_generation_ids or not (proposal.broad_class or "").strip():
        return QualityDecision(
            "reject_insufficient_proposal_support",
            "proposal_missing_constituent_generation_or_broad_class",
        )

    primary = next((item for item in items if item.role == "identification"), None)
    primary = primary or next((item for item in items if item.role == "context"), None)
    if primary is None:
        return QualityDecision(
            "reject_no_identification_or_context",
            "only_alternate_or_no_selected_evidence_available",
        )

    if not _valid_normalized_box(primary.subject_geometry):
        return QualityDecision(
            "reject_subject_geometry_invalid",
            "selected_evidence_missing_subject_geometry",
        )

    return QualityDecision("admit", "evidence_sufficient_for_review")
