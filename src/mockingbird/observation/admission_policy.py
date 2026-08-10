"""Detection Quality Accounting v1 -- SHADOW-only confidence-aware
admission-policy evaluation (see docs/detection-quality-accounting-contract.md).

Compares the de-facto current production policy (which never reads detector
confidence at all -- see Part 1 of the milestone's final report) against
candidate evidence policies parametrized over minimum confidence, qualifying
-detection count, and consecutive-frame confirmation, on top of the
`ConfidenceEvidenceSummary` accounting `contracts.py`/`visit_episode_
assembler.py` now preserve.

This module grants no production authority by itself and changes no
existing gate. `candidate_visit_authority.py`/`candidate_quality_gate.py`
remain exactly as confidence-blind as before this module exists; a policy
evaluated here becomes production behavior only through a separate,
explicitly scoped follow-up decision that satisfies every condition in
"Production authority gate" in docs/detection-quality-accounting-contract.md.

Pure: no filesystem, network, CUDA/ONNX Runtime/OpenCV, product-repository,
or SQLAlchemy import -- the same structural convention every other Stage
6.x/7 decision module in this package follows
(`test_admission_policy_module_has_no_product_repository_import`). It
invents no new detector/evidence-quality threshold beyond the parameters a
caller explicitly configures.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal, Sequence

from mockingbird.observation.contracts import ConfidenceEvidenceSummary
from mockingbird.observation.detector_benchmark import DEFAULT_THRESHOLD_GRID

ADMISSION_POLICY_MODULE_VERSION = "admission-policy-shadow-v1"

AdmissionOutcome = Literal["admit", "reject", "insufficient_evidence"]
Aggregate = Literal["max", "mean", "median"]

# What a labeled example's own *ground truth* says, independent of whether
# it is reviewed (see `mockingbird.observation.evaluation_governance` for
# the orthogonal *review-provenance* dimension -- an example must already
# be `reviewed_truth` there before it may honestly carry either "reviewed_*"
# status here).
TruthStatus = Literal[
    "reviewed_true_positive",   # a reviewed real animal Visit
    "reviewed_false_positive",  # proven false: no corresponding reviewed Visit exists in a fully-reviewed session
    "reviewed_ambiguous",       # touches more than one reviewed Visit, or the reviewer marked it ambiguous
    "diagnostic_only",          # a known hard case without human-review provenance (e.g. agent visual inspection)
    "unreviewed",               # no truth assertion at all
]


@dataclass(frozen=True)
class AdmissionPolicy:
    """One deterministic, bounded candidate SHADOW admission policy.

    `minimum_confidence` alone: this proposal's own `aggregate` confidence
    statistic must meet it. `minimum_qualifying_detections`: at least this
    many individual detections must reach `minimum_confidence` (or, if
    `minimum_confidence` is `None`, at least this many detections must have
    occurred at all -- a pure temporal-persistence filter). `minimum_
    consecutive_confirmed_frames`: the tracker's own already-computed
    consecutive-confirmation streak (`ConfidenceEvidenceSummary.max_
    consecutive_detector_confirmed_frames`) must reach this bound. Any
    combination may be set together; an unset dimension imposes no
    constraint. A policy with every dimension unset (`is_baseline`) is the
    de-facto current production behavior: it admits whatever already
    reached this stage, exactly as today's confidence-blind gates do.
    """

    name: str
    minimum_confidence: float | None = None
    aggregate: Aggregate = "max"
    minimum_qualifying_detections: int | None = None
    minimum_consecutive_confirmed_frames: int | None = None

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("invalid_admission_policy")
        if self.minimum_confidence is not None and not 0.0 <= self.minimum_confidence <= 1.0:
            raise ValueError("invalid_admission_policy")
        if self.minimum_qualifying_detections is not None and self.minimum_qualifying_detections < 1:
            raise ValueError("invalid_admission_policy")
        if self.minimum_consecutive_confirmed_frames is not None and self.minimum_consecutive_confirmed_frames < 1:
            raise ValueError("invalid_admission_policy")

    @property
    def is_baseline(self) -> bool:
        return (
            self.minimum_confidence is None
            and self.minimum_qualifying_detections is None
            and self.minimum_consecutive_confirmed_frames is None
        )


@dataclass(frozen=True)
class PolicyDecision:
    """One deterministic classification of whether `evidence` satisfies one
    policy. `insufficient_evidence` is returned -- never a guessed admit or
    reject -- whenever the exact fact this policy needs was not known (for
    example a legacy-reconstructed proposal with no per-detection samples);
    see "no fabricated confidence for legacy records" in product-doctrine.md."""

    policy_name: str
    outcome: AdmissionOutcome
    reason: str

    @property
    def admitted(self) -> bool:
        return self.outcome == "admit"


BASELINE_POLICY = AdmissionPolicy(name="baseline_current_production_no_confidence_filter")

# The current production MDv5 bundle's own configured `score_threshold`
# (`onnx_provider.OnnxModelBundle.score_threshold`) -- included explicitly
# so the sweep always covers "the current 0.1 behavior" as the milestone
# requires, independent of whatever else `DEFAULT_THRESHOLD_GRID` contains.
CURRENT_PRODUCTION_SCORE_THRESHOLD = 0.1


def _confidence_only_sweep() -> tuple[AdmissionPolicy, ...]:
    """One pure-confidence policy per already-calibrated `detector_
    benchmark.DEFAULT_THRESHOLD_GRID` value (which already includes
    `CURRENT_PRODUCTION_SCORE_THRESHOLD`) -- reused, not a new grid, per
    this codebase's own "reuse an already-calibrated constant" convention."""
    thresholds = sorted({*DEFAULT_THRESHOLD_GRID, CURRENT_PRODUCTION_SCORE_THRESHOLD})
    return tuple(
        AdmissionPolicy(name=f"min_confidence_{threshold:.2f}_max", minimum_confidence=threshold, aggregate="max")
        for threshold in thresholds
    )


def _temporal_only_sweep() -> tuple[AdmissionPolicy, ...]:
    """Pure temporal-persistence policies, no confidence bar at all --
    isolates whether requiring more/consecutive detections helps
    independent of any confidence threshold. Bounded at 4: the tracker's
    own default `minimum_detector_confirmations` is 2, so 1-4 spans
    "looser than today" through "meaningfully stricter than today.\""""
    return tuple(
        AdmissionPolicy(name=f"min_qualifying_detections_{count}", minimum_qualifying_detections=count)
        for count in (1, 2, 3, 4)
    ) + tuple(
        AdmissionPolicy(name=f"min_consecutive_confirmed_{count}", minimum_consecutive_confirmed_frames=count)
        for count in (1, 2, 3, 4)
    )


def _combined_sweep() -> tuple[AdmissionPolicy, ...]:
    """A bounded set of confidence-plus-temporal combinations -- not a full
    cartesian product (see "Do not build a giant analytics platform" in
    this milestone's own scope). Also covers the `mean`/`median` aggregate
    dimension, which a pure-`max` sweep cannot exercise."""
    combined = tuple(
        AdmissionPolicy(
            name=f"min_confidence_{threshold:.2f}_max_and_min_qualifying_2",
            minimum_confidence=threshold, aggregate="max", minimum_qualifying_detections=2,
        )
        for threshold in (0.1, 0.2, 0.3, 0.5)
    )
    aggregates = tuple(
        AdmissionPolicy(name=f"min_confidence_{threshold:.2f}_{aggregate}", minimum_confidence=threshold, aggregate=aggregate)
        for threshold in (0.1, 0.3)
        for aggregate in ("mean", "median")
    )
    consecutive_plus_confidence = tuple(
        AdmissionPolicy(
            name=f"min_confidence_{threshold:.2f}_max_and_min_consecutive_2",
            minimum_confidence=threshold, aggregate="max", minimum_consecutive_confirmed_frames=2,
        )
        for threshold in (0.1, 0.3)
    )
    return combined + aggregates + consecutive_plus_confidence


def default_policy_sweep() -> tuple[AdmissionPolicy, ...]:
    """The full bounded, deterministic candidate policy sweep this
    milestone's Part 6 requires: the baseline plus every dimension above,
    a handful of bounded combinations, and always including the current
    `0.1` behavior (see "Do not assume a single score threshold is
    sufficient" / "At minimum include the current 0.1 behavior")."""
    return (BASELINE_POLICY, *_confidence_only_sweep(), *_temporal_only_sweep(), *_combined_sweep())


def _aggregate_value(evidence: ConfidenceEvidenceSummary, aggregate: Aggregate) -> float | None:
    if aggregate == "max":
        return evidence.max_confidence
    if aggregate == "mean":
        return evidence.mean_confidence
    return evidence.median_confidence


def _qualifying_detection_count(evidence: ConfidenceEvidenceSummary, minimum_confidence: float | None) -> int | None:
    if minimum_confidence is None:
        return evidence.detection_count
    if not evidence.samples:
        # Zero detections is a real, known zero; any positive detection
        # count with no retained samples is unknown (see `contracts.
        # ConfidenceEvidenceSummary`'s own `strong_detection_count`
        # docstring for the identical reasoning).
        return 0 if evidence.detection_count == 0 else None
    return sum(1 for sample in evidence.samples if sample.confidence >= minimum_confidence)


def evaluate_admission_policy(
    policy: AdmissionPolicy, evidence: ConfidenceEvidenceSummary | None,
) -> PolicyDecision:
    """Classify one already-assembled proposal's own `ConfidenceEvidenceSummary`
    against one candidate SHADOW admission policy. Deterministic and side-
    effect free; grants no production authority (see the module docstring).
    """
    if evidence is None:
        return PolicyDecision(policy.name, "insufficient_evidence", "no_confidence_evidence_available")
    if policy.is_baseline:
        # The de-facto current production behavior: neither `candidate_
        # visit_authority.evaluate_candidate_authority` nor `candidate_
        # quality_gate.evaluate_evidence_admission` reads confidence at
        # all, so a proposal that reached this evaluator already survived
        # every *other* structural gate -- this baseline policy adds no
        # further filter, by design.
        return PolicyDecision(policy.name, "admit", "no_confidence_criteria_configured")

    if policy.minimum_confidence is not None:
        value = _aggregate_value(evidence, policy.aggregate)
        if value is None:
            return PolicyDecision(policy.name, "insufficient_evidence", f"{policy.aggregate}_confidence_unavailable")
        if value < policy.minimum_confidence:
            return PolicyDecision(policy.name, "reject", f"{policy.aggregate}_confidence_below_minimum")

    if policy.minimum_qualifying_detections is not None:
        count = _qualifying_detection_count(evidence, policy.minimum_confidence)
        if count is None:
            return PolicyDecision(policy.name, "insufficient_evidence", "qualifying_detection_count_unavailable")
        if count < policy.minimum_qualifying_detections:
            return PolicyDecision(policy.name, "reject", "insufficient_qualifying_detection_count")

    if policy.minimum_consecutive_confirmed_frames is not None:
        streak = evidence.max_consecutive_detector_confirmed_frames
        if streak is None:
            return PolicyDecision(policy.name, "insufficient_evidence", "consecutive_confirmation_unavailable")
        if streak < policy.minimum_consecutive_confirmed_frames:
            return PolicyDecision(policy.name, "reject", "insufficient_consecutive_confirmation")

    return PolicyDecision(policy.name, "admit", "meets_all_configured_criteria")


@dataclass(frozen=True)
class LabeledProposal:
    """One proposal this shadow evaluator can score a policy against,
    paired with its own confidence evidence and ground-truth status. Pair
    with `mockingbird.observation.evaluation_governance.EvaluationExample`
    for the *review-provenance* half of this fact -- only a `reviewed_
    truth`-provenance example may honestly carry a `reviewed_*`
    `truth_status` here."""

    proposal_id: str
    truth_status: TruthStatus
    confidence_evidence: ConfidenceEvidenceSummary | None = None


def _metric(value: object, state: str) -> dict[str, object]:
    """Mirrors the `{"state": ..., "value": ...}` convention already
    established by `replay.py`/`detector_benchmark.py`."""
    return {"state": state, "value": value}


def _rate(decisions: Sequence[PolicyDecision], *, predicate) -> dict[str, object]:
    evaluated = [decision for decision in decisions if decision.outcome != "insufficient_evidence"]
    if not evaluated:
        return _metric(None, "insufficient_data")
    return _metric(sum(1 for decision in evaluated if predicate(decision)) / len(evaluated), "evaluated")


def evaluate_policy_against_examples(
    policy: AdmissionPolicy, examples: Sequence[LabeledProposal],
) -> dict[str, object]:
    """Score one policy against a labeled example set, reporting admitted/
    rejected/insufficient-evidence counts and, where the sample size
    actually supports it, reviewed true-positive retention and reviewed
    false-positive rejection rates -- `insufficient_data`, never a
    misleading number, whenever a category's sample size is zero (see "Do
    not print misleading precision/recall numbers when the denominator is
    not actually known" in this milestone's own instructions)."""

    scored = tuple((example, evaluate_admission_policy(policy, example.confidence_evidence)) for example in examples)
    by_status: dict[str, list[PolicyDecision]] = {}
    for example, decision in scored:
        by_status.setdefault(example.truth_status, []).append(decision)
    all_decisions = [decision for _, decision in scored]
    diagnostic_outcomes = [
        {"proposal_id": example.proposal_id, "outcome": decision.outcome, "reason": decision.reason}
        for example, decision in scored
        if example.truth_status == "diagnostic_only"
    ]
    return {
        "policy_name": policy.name,
        "policy": asdict(policy),
        "example_count": len(examples),
        "admitted_count": sum(1 for decision in all_decisions if decision.outcome == "admit"),
        "rejected_count": sum(1 for decision in all_decisions if decision.outcome == "reject"),
        "insufficient_evidence_count": sum(1 for decision in all_decisions if decision.outcome == "insufficient_evidence"),
        "reviewed_true_positive_retention_rate": _rate(
            by_status.get("reviewed_true_positive", ()), predicate=lambda decision: decision.admitted,
        ),
        "reviewed_true_positive_sample_size": len(by_status.get("reviewed_true_positive", ())),
        "reviewed_false_positive_rejection_rate": _rate(
            by_status.get("reviewed_false_positive", ()), predicate=lambda decision: decision.outcome == "reject",
        ),
        "reviewed_false_positive_sample_size": len(by_status.get("reviewed_false_positive", ())),
        "diagnostic_only_outcomes": diagnostic_outcomes,
    }


def evaluate_policy_sweep(
    policies: Sequence[AdmissionPolicy], examples: Sequence[LabeledProposal],
) -> dict[str, object]:
    """Evaluate every policy in `policies` against the same `examples` and
    return one bounded, deterministic comparison report. No candidate
    policy is marked "winning" or granted authority here -- see "Production
    authority gate" in docs/detection-quality-accounting-contract.md; this
    is measurement only."""

    reviewed_positive_total = sum(1 for example in examples if example.truth_status == "reviewed_true_positive")
    reviewed_negative_total = sum(1 for example in examples if example.truth_status == "reviewed_false_positive")
    diagnostic_total = sum(1 for example in examples if example.truth_status == "diagnostic_only")
    return {
        "module_version": ADMISSION_POLICY_MODULE_VERSION,
        "example_count": len(examples),
        "reviewed_true_positive_sample_size": reviewed_positive_total,
        "reviewed_false_positive_sample_size": reviewed_negative_total,
        "diagnostic_only_sample_size": diagnostic_total,
        "policy_results": [evaluate_policy_against_examples(policy, examples) for policy in policies],
        "safety": {
            "production_authority_changed": False,
            "reviewed_truth_created": False,
        },
    }
