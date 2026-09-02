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

Hard-Negative Visit Admission Precision & Species-Escalation Correctness v1
(see docs/hard-negative-visit-admission-precision-species-escalation-
correctness-v1-report.md): adds one further, optional check --
`reject_insufficient_detector_corroboration` -- using `confidence_evidence`
(`contracts.ConfidenceEvidenceSummary`, already computed by Detection
Quality Accounting v1 and already threaded onto every `AssembledVisitProposal`
today, just never previously read at this boundary). This is deliberately
**not** a confidence-magnitude threshold: `admission_policy.py`'s own
already-swept `minimum_confidence` dimension was already conclusively
rejected against 70 real reviewed Visits (no threshold clears both
false-positive-rejection and real-animal recall together -- see "Production
authority gate" in docs/detection-quality-accounting-contract.md) and this
gate does not re-litigate that. Instead it asks a narrower, structural
question the prior sweep could not answer (its own legacy corpus predated
per-detection sample retention, so its `minimum_qualifying_detections`/
`minimum_consecutive_confirmed_frames` dimensions were structurally
`insufficient_evidence` throughout): did *anything* beyond the tracker's own
bare `minimum_detector_confirmations` floor (2, `frame_driven_provider.
FrameDrivenSettings`) ever corroborate this proposal, on *any* axis --
total genuine detector-matched count, an unbroken consecutive-frame streak,
or a clean/strong single detection? A proposal whose entire evidentiary
basis is that bare structural minimum, on every axis, at once, is treated as
insufficiently corroborated for a user-visible Visit -- narrower than, and
independently justified from, the confidence-threshold question the gate
above already settled. Duck-typed via `object`/`getattr` exactly like
`candidate_visit_authority.ProposalArbitrationFacts.confidence_evidence`
already is, so this module still imports neither `contracts` nor
`admission_policy`.
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
    "reject_insufficient_detector_corroboration",
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
        "reject_insufficient_detector_corroboration",
    }
)

# Hard-Negative Visit Admission Precision & Species-Escalation Correctness v1
# -- field-grounded, not intuition-tuned, and deliberately resistant to
# being gamed by chaining more bare-minimum track generations together.
#
# `_BARE_DETECTOR_CONFIRMATIONS_PER_GENERATION` reuses (does not re-import;
# this module stays decoupled from tracker configuration) the tracker's own
# existing `minimum_detector_confirmations` default (2,
# `frame_driven_provider.FrameDrivenSettings`) -- the bare number of
# genuine, spatially-coherent detections needed to confirm a track *at all*.
# A proposal's own `detection_count` is a *sum* across every constituent
# generation (`contracts.merge_confidence_evidence`), so a chain of `N`
# independently-restarted generations, each contributing nothing beyond
# that bare floor, can always reach `2 * N` purely by repetition -- Gate A
# Field Acceptance v9's own `visit-observation-candidate-027` shows exactly
# this shape (many short, independently-restarted generations at one static
# location, each never exceeding the tracker's own bare confirmation floor).
# Scaling the qualifying floor by `N` closes that loophole: a chain must
# show genuinely more corroboration than "the bare minimum, once per
# restart" to pass on this axis, for any `N`, not only `N == 1`.
# `_QUALIFYING_DETECTIONS_MARGIN` is the one further real number this check
# needs, and it is field-grounded, not guessed: the same v9 session's own
# `visit-observation-candidate-026` (the one confirmed-false Visit that went
# on to receive a confident wrong species label) is a single-generation
# proposal (`N=1`) whose entire genuine-detector basis was exactly 3 raw
# detections (confidence 0.109-0.111, never within reach of `strong_
# detection_threshold`) -- `2*1 + 1 = 3` reproduces that exact real,
# confirmed-false count as the common single-generation floor: a proposal
# needs *more* than that specific real signature to pass on this axis, for
# any `N`.
#
# `_MINIMUM_CONSECUTIVE_DETECTOR_CONFIRMED_FRAMES` is the second, structurally
# ungameable axis: `merge_confidence_evidence` deliberately takes the *max*,
# never the sum, of `max_consecutive_detector_confirmed_frames` across
# constituent generations ("a real gap between two merged tracklets is not
# 'more consecutive support'") -- chaining more bare-minimum restarts
# together can never inflate it. Requiring at least a 2-frame unbroken
# genuine-detection run somewhere in the whole proposal is a fact no amount
# of repetition can manufacture. Both axes are deliberately permissive (an
# OR, not an AND, with each other -- see `_insufficient_detector_
# corroboration`): either one being cleared is enough to admit (this is what
# lets a genuinely intermittent, never-consecutive real bird pass on the
# scaled-count axis, and what lets a genuinely brief-but-continuous real
# bird pass on the streak axis even with few total detections), and either
# fact being unknown never causes a reject.
_BARE_DETECTOR_CONFIRMATIONS_PER_GENERATION = 2
_QUALIFYING_DETECTIONS_MARGIN = 1
_MINIMUM_CONSECUTIVE_DETECTOR_CONFIRMED_FRAMES = 1

# Independent Corroboration Value & Persistent-Confusor Admission
# Correctness v1 (see docs/independent-corroboration-value-persistent-
# confusor-admission-correctness-v1-report.md): reopened by Representative
# Daylight Gate A Field Acceptance v10's own real field evidence -- the
# fix above correctly rejected 3/3 classic bare-minimum single-generation
# hard negatives this session, but the *same* recurring background
# confusor (a tube-feeder-area location) defeated the count-based axis 4
# separate times by accumulating many individually-insufficient detections
# *within one already-confirmed generation's own natural persistence*,
# never by chaining many bare-minimum restarts together (the shape the
# formula above was already built to close). No raw-count/confidence
# threshold retune can separate this v10 signature from a genuine
# real weak bird: the two disclosed field ranges (persistent confusor,
# 9-33 detections; v10's own genuine small/distant bird, 13-18
# detections, "admitted purely via count-based corroboration") overlap,
# and this is not incidental -- for a single constituent generation
# (`constituent_generation_count == 1`), `detection_count` and
# `max_single_generation_detection_count` are the same fact by
# construction, so *no* function of `detection_count` alone, for any
# constant, can separate them (the false cluster's own single-generation
# case is the same structurally-irreducible residual Hard-Negative Visit
# Admission Precision v1's own report already disclosed for a
# hypothetical bird "at the exact same corroboration floor," now
# concretely reproduced with real field data rather than hypothetical --
# see "Independence analysis" in this milestone's own report for the
# full derivation, including why every per-generation-cap variant was
# tried and mathematically ruled out). What *is* real and fixable: a
# **multi**-generation proposal (`constituent_generation_count >= 2`)
# whose count-axis credit is concentrated almost entirely in one
# generation's own extended persistence, with the rest of its own
# "chain" contributing nothing beyond what those *other* generations
# would already need to justify *themselves* -- see
# `_concentrated_in_single_generation`. This introduces no new numeric
# constant: it recursively re-applies the identical, already-justified
# `_BARE_DETECTOR_CONFIRMATIONS_PER_GENERATION`/`_QUALIFYING_DETECTIONS_
# MARGIN` formula to "the chain minus its own single largest member,"
# which is what makes it resistant to gaming by padding a dominant
# generation's chain with more bare-minimum filler restarts (the
# remaining generations' own floor grows right along with them). The
# ungameable, uncapped streak axis (`max_consecutive_detector_confirmed_
# frames`) remains a completely independent escape, untouched by this --
# a genuinely sustained multi-generation encounter with at least one real
# back-to-back pair anywhere still admits exactly as before. Cross-
# session recurrence of the *same* never-strong single-generation
# signature at one location is a separate, already-live, unmodified
# mechanism this module does not duplicate -- see
# `mockingbird.observation.scene_confusor` and this milestone's own
# report for the empirical composition result.


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


def _concentrated_in_single_generation(
    confidence_evidence: object, *, count: int, generations: int,
) -> bool:
    """Independent Corroboration Value & Persistent-Confusor Admission
    Correctness v1: whether a *multi*-generation proposal's own count-axis
    credit (already known to clear `2 * generations + 1` -- the caller's
    own responsibility to check first) is, despite that, concentrated
    almost entirely in one constituent generation's own extended
    persistence -- recognized by asking whether the *other* generations,
    on their own, with the single largest contributor excluded, would
    already have cleared their own identically-scaled floor. Only ever
    called for `generations >= 2`; a single-generation proposal has
    nothing to recurse against (see `_insufficient_detector_
    corroboration`'s own call site) and is completely unaffected by this
    function's existence.

    Unknown-safe: `max_single_generation_detection_count` being
    unavailable (a legacy proposal, or any caller that predates this
    fact) returns `False` -- never concentrated, never a guessed reject --
    so a proposal with this one new fact missing is judged exactly as it
    was before this milestone, identical to every other unknown-evidence
    rule already established on `confidence_evidence`.
    """

    if generations < 2:
        return False
    dominant = getattr(confidence_evidence, "max_single_generation_detection_count", None)
    if dominant is None:
        return False
    remainder = count - dominant
    remaining_generations = generations - 1
    remaining_floor = (
        _BARE_DETECTOR_CONFIRMATIONS_PER_GENERATION * remaining_generations + _QUALIFYING_DETECTIONS_MARGIN
    )
    return remainder <= remaining_floor


def _insufficient_detector_corroboration(
    confidence_evidence: object | None, *, constituent_generation_count: int,
) -> str | None:
    """The one new check Hard-Negative Visit Admission Precision & Species-
    Escalation Correctness v1 adds (see the module docstring's own account
    of why this is not a confidence-magnitude threshold, and the module
    -level constants above for the full gaming-resistance rationale).
    Returns a reason string when -- and only when -- every one of the
    following is *known* (never guessed) and shows the bare-minimum
    signature; returns `None` (admit on this axis) otherwise, including
    whenever any needed fact is unavailable:

    - `strong_detection_count` is known and exactly `0` -- never once
      reached `strong_detection_threshold` (0.70). A proposal with even one
      clean, confident detection already has real corroboration this check
      has nothing further to add to.
    - `detection_count` is known and does not exceed `_BARE_DETECTOR_
      CONFIRMATIONS_PER_GENERATION * constituent_generation_count +
      _QUALIFYING_DETECTIONS_MARGIN` -- a floor that scales with how many
      track generations this proposal chains together, so a chain of bare
      -minimum restarts can never simply out-accumulate a fixed number --
      OR -- `max_consecutive_detector_confirmed_frames` is known and does
      not exceed `_MINIMUM_CONSECUTIVE_DETECTOR_CONFIRMED_FRAMES` (1),
      structurally ungameable by chaining (see `contracts.merge_confidence_
      evidence`'s own max-not-sum handling of this exact field). Either
      axis clearing its own floor is enough to admit (a deliberately
      permissive OR): a genuinely present weak/small/brief/partially-
      occluded/intermittently-corroborated bird (see this milestone's own
      required positive controls) realistically accumulates *some* real
      corroboration beyond the scaled bare-restart floor -- more total
      genuine detections than repeated bare-minimum restarts alone could
      produce, or at least one back-to-back pair once actually acquired --
      even when no single detection is ever strong. A proposal that clears
      *neither* axis, with zero strong detections, has shown literally
      nothing beyond what repeating the tracker's own bare per-generation
      confirmation floor, as many times as it likes, could already produce.

    Independent Corroboration Value & Persistent-Confusor Admission
    Correctness v1 (see the module-level comment above `_BARE_DETECTOR_
    CONFIRMATIONS_PER_GENERATION` for the full field-evidenced rationale):
    clearing the count axis's own scaled floor is *necessary but no
    longer alone sufficient* for a multi-generation proposal
    (`constituent_generation_count >= 2`) -- `_concentrated_in_single_
    generation` additionally asks whether that credit is concentrated
    almost entirely in one constituent generation's own extended
    persistence, with the rest of the chain contributing nothing beyond
    what those *other* generations would already need to justify
    *themselves*. A single-generation proposal is completely unaffected
    (nothing to recurse against); the streak axis is completely
    unaffected either way (it was never count-based to begin with).

    Unknown-safe throughout, matching this codebase's universal "never a
    guessed reject" convention (see `contracts.ConfidenceEvidenceSummary`'s
    own honesty rules): `confidence_evidence` itself, or any of the
    fields read from it, being `None`/absent never causes a reject -- a
    legacy proposal with no retained confidence lineage, or a caller that
    predates this fact, is admitted exactly as before this check existed.
    """

    if confidence_evidence is None:
        return None
    count = getattr(confidence_evidence, "detection_count", None)
    # A confirmed track always retains at least one genuine detection sample
    # (`frame_tracker._observe_detection` appends to `confidence_samples`
    # unconditionally on every genuine match, and `_confirm` cannot fire
    # without at least one such match) -- `detection_count == 0` is
    # therefore never a real production fact for a genuinely assembled
    # proposal. It is exactly what `contracts.EMPTY_CONFIDENCE_EVIDENCE`
    # (the dataclass default) leaves a caller that never populated this
    # fact at all with -- a legacy record, or a test fixture unrelated to
    # detector-confidence behavior. Treated as "this fact was never
    # computed," identical to `None`, never as "known: zero corroboration."
    if count == 0:
        return None
    strong = getattr(confidence_evidence, "strong_detection_count", None)
    if strong is None or strong > 0:
        return None
    generations = max(1, constituent_generation_count)
    qualifying_floor = _BARE_DETECTOR_CONFIRMATIONS_PER_GENERATION * generations + _QUALIFYING_DETECTIONS_MARGIN
    count_clears_floor = count is not None and count > qualifying_floor
    concentrated = count_clears_floor and _concentrated_in_single_generation(
        confidence_evidence, count=count, generations=generations,
    )
    if count_clears_floor and not concentrated:
        return None
    streak = getattr(confidence_evidence, "max_consecutive_detector_confirmed_frames", None)
    if streak is not None and streak > _MINIMUM_CONSECUTIVE_DETECTOR_CONFIRMED_FRAMES:
        return None
    if count is None and streak is None:
        return None
    if concentrated:
        return "corroboration_concentrated_in_single_generation"
    return "never_strong_and_minimal_detector_corroboration"


def evaluate_evidence_admission(
    proposal: ProposalSupportFacts,
    items: Sequence[EvidenceItemFacts],
    *,
    confidence_evidence: object | None = None,
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
    4. Detector corroboration (Hard-Negative Visit Admission Precision &
       Species-Escalation Correctness v1, optional -- see `confidence_
       evidence`'s own parameter doc and `_insufficient_detector_
       corroboration`'s docstring for the complete field-grounded
       rationale): a proposal that never reached a strong detection and
       never showed real corroboration on any other axis either is
       rejected here, last, only once every check above has already passed
       -- i.e. only for a proposal that already has valid geometry and a
       meaningfully selected evidence item, exactly the shape a real
       admitted-but-empty background Visit takes.

    Decodability is intentionally not re-checked here: only a candidate the
    scorer already judged `eligible` (which already excludes
    `candidate_undecodable`/`candidate_unavailable`) can ever reach this
    gate as an `identification`/`context` pick, so re-deciding it a second
    time here would duplicate, not add, an existing judgment.

    `confidence_evidence` is this proposal's own merged `contracts.
    ConfidenceEvidenceSummary` (or any object duck-typing its
    `strong_detection_count`/`detection_count`/`max_consecutive_detector_
    confirmed_frames` attributes -- mirroring `candidate_visit_authority.
    ProposalArbitrationFacts.confidence_evidence`'s own established
    convention, so this module still never imports `contracts`). Defaulted
    `None` so every pre-existing caller (this gate's own unit tests, and
    any caller that predates this fact) is unaffected -- `None` degrades to
    "this check never fires," identical to the pre-fix gate.
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

    corroboration_reason = _insufficient_detector_corroboration(
        confidence_evidence, constituent_generation_count=len(proposal.constituent_generation_ids),
    )
    if corroboration_reason is not None:
        return QualityDecision("reject_insufficient_detector_corroboration", corroboration_reason)

    return QualityDecision("admit", "evidence_sufficient_for_review")
