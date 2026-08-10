"""Detection Quality Accounting v1 SHADOW-only admission-policy evaluation
(see docs/detection-quality-accounting-contract.md)."""

from __future__ import annotations

from pathlib import Path

import pytest

from mockingbird.observation.admission_policy import (
    AdmissionPolicy,
    BASELINE_POLICY,
    CURRENT_PRODUCTION_SCORE_THRESHOLD,
    LabeledProposal,
    default_policy_sweep,
    evaluate_admission_policy,
    evaluate_policy_against_examples,
    evaluate_policy_sweep,
)
from mockingbird.observation.contracts import ConfidenceEvidenceSummary, DetectionEvidenceSample


def test_admission_policy_module_has_no_product_repository_import() -> None:
    """Structural guard, matching every other Stage 6.x/7 pure decision
    module's own established convention."""
    source = Path("src/mockingbird/observation/admission_policy.py").read_text(encoding="utf-8")
    forbidden = (
        "mockingbird.repository", "mockingbird.storage", "mockingbird.api", "sqlalchemy",
        "import socket", "import requests", "onnxruntime", "cv2",
    )
    for token in forbidden:
        assert token not in source, f"admission_policy.py must not reference {token}"


def _evidence(
    *, max_confidence: float | None, samples: tuple[float, ...] = (), consecutive: int | None = 1,
    detection_count: int | None = None,
) -> ConfidenceEvidenceSummary:
    count = detection_count if detection_count is not None else max(1, len(samples))
    return ConfidenceEvidenceSummary(
        detection_count=count,
        max_confidence=max_confidence,
        mean_confidence=(sum(samples) / len(samples)) if samples else None,
        median_confidence=None,
        strong_detection_count=sum(1 for value in samples if value >= 0.7) if samples else None,
        weak_detection_count=sum(1 for value in samples if value < 0.7) if samples else None,
        max_consecutive_detector_confirmed_frames=consecutive,
        samples=tuple(
            DetectionEvidenceSample(value, index * 500, f"frame-{index}", f"obs-{index}", value >= 0.7)
            for index, value in enumerate(samples)
        ),
        broad_class="animal",
        first_detection_offset_ms=0 if samples else None,
        last_detection_offset_ms=(len(samples) - 1) * 500 if samples else None,
        sample_truncated=not samples and count > 0,
    )


# --- AdmissionPolicy validation -------------------------------------------------


def test_admission_policy_rejects_out_of_range_confidence() -> None:
    with pytest.raises(ValueError, match="invalid_admission_policy"):
        AdmissionPolicy(name="bad", minimum_confidence=1.5)


def test_admission_policy_rejects_non_positive_counts() -> None:
    with pytest.raises(ValueError, match="invalid_admission_policy"):
        AdmissionPolicy(name="bad", minimum_qualifying_detections=0)
    with pytest.raises(ValueError, match="invalid_admission_policy"):
        AdmissionPolicy(name="bad", minimum_consecutive_confirmed_frames=0)


def test_baseline_policy_has_no_configured_criteria() -> None:
    assert BASELINE_POLICY.is_baseline is True
    assert AdmissionPolicy(name="x", minimum_confidence=0.1).is_baseline is False


# --- evaluate_admission_policy ---------------------------------------------------


def test_baseline_policy_always_admits_when_evidence_exists() -> None:
    decision = evaluate_admission_policy(BASELINE_POLICY, _evidence(max_confidence=0.01, samples=(0.01,)))
    assert decision.outcome == "admit"
    assert decision.reason == "no_confidence_criteria_configured"


def test_missing_evidence_is_insufficient_evidence_not_a_guess() -> None:
    decision = evaluate_admission_policy(BASELINE_POLICY, None)
    assert decision.outcome == "insufficient_evidence"


def test_minimum_confidence_admits_above_and_rejects_below() -> None:
    policy = AdmissionPolicy(name="p", minimum_confidence=0.5)
    assert evaluate_admission_policy(policy, _evidence(max_confidence=0.6, samples=(0.6,))).admitted
    assert not evaluate_admission_policy(policy, _evidence(max_confidence=0.4, samples=(0.4,))).admitted


def test_minimum_confidence_reports_insufficient_evidence_when_aggregate_unavailable() -> None:
    """A legacy-reconstructed proposal with no retained samples has no
    `mean_confidence` -- a policy requiring the mean must say so honestly,
    never silently fall back to `max_confidence` or guess."""
    policy = AdmissionPolicy(name="p", minimum_confidence=0.5, aggregate="mean")
    legacy_evidence = ConfidenceEvidenceSummary(
        detection_count=3, max_confidence=0.8, mean_confidence=None, median_confidence=None,
        strong_detection_count=None, weak_detection_count=None, max_consecutive_detector_confirmed_frames=None,
        samples=(), broad_class="animal", first_detection_offset_ms=None, last_detection_offset_ms=None,
        sample_truncated=True,
    )
    decision = evaluate_admission_policy(policy, legacy_evidence)
    assert decision.outcome == "insufficient_evidence"
    assert decision.reason == "mean_confidence_unavailable"


def test_minimum_qualifying_detections_counts_samples_at_or_above_threshold() -> None:
    policy = AdmissionPolicy(name="p", minimum_confidence=0.3, minimum_qualifying_detections=2)
    two_qualifying = _evidence(max_confidence=0.6, samples=(0.1, 0.4, 0.6))
    one_qualifying = _evidence(max_confidence=0.6, samples=(0.1, 0.2, 0.6))
    assert evaluate_admission_policy(policy, two_qualifying).admitted
    assert not evaluate_admission_policy(policy, one_qualifying).admitted


def test_minimum_qualifying_detections_without_confidence_bar_counts_all_detections() -> None:
    policy = AdmissionPolicy(name="p", minimum_qualifying_detections=3)
    assert evaluate_admission_policy(policy, _evidence(max_confidence=0.1, samples=(0.1, 0.1, 0.1))).admitted
    assert not evaluate_admission_policy(policy, _evidence(max_confidence=0.1, samples=(0.1,))).admitted


def test_minimum_consecutive_confirmed_frames() -> None:
    policy = AdmissionPolicy(name="p", minimum_consecutive_confirmed_frames=3)
    assert evaluate_admission_policy(policy, _evidence(max_confidence=0.5, samples=(0.5,), consecutive=3)).admitted
    assert not evaluate_admission_policy(policy, _evidence(max_confidence=0.5, samples=(0.5,), consecutive=2)).admitted


def test_minimum_consecutive_confirmed_frames_insufficient_evidence_when_unknown() -> None:
    policy = AdmissionPolicy(name="p", minimum_consecutive_confirmed_frames=2)
    decision = evaluate_admission_policy(policy, _evidence(max_confidence=0.5, samples=(0.5,), consecutive=None))
    assert decision.outcome == "insufficient_evidence"


def test_combined_policy_requires_every_configured_dimension() -> None:
    policy = AdmissionPolicy(name="p", minimum_confidence=0.5, minimum_qualifying_detections=2)
    meets_confidence_not_count = _evidence(max_confidence=0.6, samples=(0.6,))
    meets_both = _evidence(max_confidence=0.6, samples=(0.6, 0.55))
    assert not evaluate_admission_policy(policy, meets_confidence_not_count).admitted
    assert evaluate_admission_policy(policy, meets_both).admitted


# --- default_policy_sweep --------------------------------------------------------


def test_default_policy_sweep_includes_baseline_and_current_production_threshold() -> None:
    sweep = default_policy_sweep()
    names = [policy.name for policy in sweep]
    assert len(names) == len(set(names))  # every policy uniquely named
    assert BASELINE_POLICY in sweep
    assert any(
        policy.minimum_confidence == CURRENT_PRODUCTION_SCORE_THRESHOLD and policy.aggregate == "max"
        for policy in sweep
    )


def test_default_policy_sweep_is_deterministic() -> None:
    assert default_policy_sweep() == default_policy_sweep()


# --- evaluate_policy_against_examples / evaluate_policy_sweep -------------------


def test_evaluate_policy_against_examples_labels_insufficient_data_with_zero_sample_size() -> None:
    policy = AdmissionPolicy(name="p", minimum_confidence=0.5)
    result = evaluate_policy_against_examples(policy, ())
    assert result["reviewed_true_positive_retention_rate"] == {"state": "insufficient_data", "value": None}
    assert result["reviewed_false_positive_rejection_rate"] == {"state": "insufficient_data", "value": None}
    assert result["reviewed_true_positive_sample_size"] == 0


def test_evaluate_policy_against_examples_computes_retention_and_rejection_rates() -> None:
    policy = AdmissionPolicy(name="p", minimum_confidence=0.5)
    examples = (
        LabeledProposal("real-1", "reviewed_true_positive", _evidence(max_confidence=0.8, samples=(0.8,))),
        LabeledProposal("real-2", "reviewed_true_positive", _evidence(max_confidence=0.2, samples=(0.2,))),
        LabeledProposal("bark-1", "reviewed_false_positive", _evidence(max_confidence=0.15, samples=(0.15,))),
        LabeledProposal("bark-2", "reviewed_false_positive", _evidence(max_confidence=0.9, samples=(0.9,))),
    )
    result = evaluate_policy_against_examples(policy, examples)
    assert result["reviewed_true_positive_retention_rate"] == {"state": "evaluated", "value": 0.5}
    assert result["reviewed_false_positive_rejection_rate"] == {"state": "evaluated", "value": 0.5}


def test_evaluate_policy_against_examples_reports_diagnostic_outcomes_without_scoring_them_as_truth() -> None:
    policy = AdmissionPolicy(name="p", minimum_confidence=0.5)
    examples = (
        LabeledProposal(
            "visit-observation-candidate-001", "diagnostic_only",
            _evidence(max_confidence=0.12, samples=(0.12,)),
        ),
    )
    result = evaluate_policy_against_examples(policy, examples)
    # Diagnostic examples never feed a retention/rejection rate.
    assert result["reviewed_true_positive_sample_size"] == 0
    assert result["reviewed_false_positive_sample_size"] == 0
    assert result["diagnostic_only_outcomes"] == [
        {"proposal_id": "visit-observation-candidate-001", "outcome": "reject", "reason": "max_confidence_below_minimum"},
    ]


def test_evaluate_policy_sweep_evaluates_every_policy_and_grants_no_authority() -> None:
    examples = (
        LabeledProposal("real-1", "reviewed_true_positive", _evidence(max_confidence=0.8, samples=(0.8,))),
        LabeledProposal("bark-1", "reviewed_false_positive", _evidence(max_confidence=0.15, samples=(0.15,))),
    )
    policies = (BASELINE_POLICY, AdmissionPolicy(name="strict", minimum_confidence=0.5))
    report = evaluate_policy_sweep(policies, examples)
    assert len(report["policy_results"]) == 2
    assert report["safety"] == {"production_authority_changed": False, "reviewed_truth_created": False}
    assert report["reviewed_true_positive_sample_size"] == 1
    assert report["reviewed_false_positive_sample_size"] == 1
