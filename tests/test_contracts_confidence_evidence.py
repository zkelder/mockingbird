"""Detection Quality Accounting v1 (see
docs/detection-quality-accounting-contract.md): focused unit tests for
`ConfidenceEvidenceSummary`/`DetectionEvidenceSample`/
`merge_confidence_evidence` in isolation from the tracker/assembler
integration these types flow through."""

from __future__ import annotations

import pytest

from mockingbird.observation.contracts import (
    ConfidenceEvidenceSummary,
    DetectionEvidenceSample,
    EMPTY_CONFIDENCE_EVIDENCE,
    merge_confidence_evidence,
)


def _summary(**overrides: object) -> ConfidenceEvidenceSummary:
    values: dict[str, object] = {
        "detection_count": 0, "max_confidence": None, "mean_confidence": None, "median_confidence": None,
        "strong_detection_count": 0, "weak_detection_count": 0, "max_consecutive_detector_confirmed_frames": 0,
        "samples": (), "broad_class": "animal", "first_detection_offset_ms": None, "last_detection_offset_ms": None,
    }
    values.update(overrides)
    return ConfidenceEvidenceSummary(**values)


def _sample(confidence: float, offset_ms: int, *, is_strong: bool = False) -> DetectionEvidenceSample:
    return DetectionEvidenceSample(confidence, offset_ms, f"frame-{offset_ms}", f"obs-{offset_ms}", is_strong)


# --- structural invariants -----------------------------------------------------


def test_negative_detection_count_is_rejected() -> None:
    with pytest.raises(ValueError, match="invalid_confidence_evidence_summary"):
        _summary(detection_count=-1)


def test_strong_plus_weak_exceeding_detection_count_is_rejected() -> None:
    with pytest.raises(ValueError, match="invalid_confidence_evidence_summary"):
        _summary(detection_count=2, strong_detection_count=2, weak_detection_count=1)


def test_unknown_strong_or_weak_count_does_not_trip_the_sum_check() -> None:
    """`None` means "unknown," not zero -- the sum invariant must not fire
    just because one side is unknown."""
    _summary(detection_count=5, strong_detection_count=None, weak_detection_count=None)
    _summary(detection_count=5, strong_detection_count=3, weak_detection_count=None)


def test_empty_confidence_evidence_is_honestly_zero_not_unknown() -> None:
    """Zero detections is a real, known fact -- distinct from "detections
    happened but we don't know how many were strong/weak.\""""
    assert EMPTY_CONFIDENCE_EVIDENCE.detection_count == 0
    assert EMPTY_CONFIDENCE_EVIDENCE.strong_detection_count == 0
    assert EMPTY_CONFIDENCE_EVIDENCE.weak_detection_count == 0
    assert EMPTY_CONFIDENCE_EVIDENCE.sample_truncated is False


# --- merge_confidence_evidence --------------------------------------------------


def test_merge_of_no_summaries_returns_empty() -> None:
    assert merge_confidence_evidence(()) == EMPTY_CONFIDENCE_EVIDENCE


def test_merge_of_one_summary_returns_it_unchanged() -> None:
    only = _summary(detection_count=3, max_confidence=0.5)
    assert merge_confidence_evidence((only,)) is only


def test_merge_combines_counts_and_orders_samples_by_offset() -> None:
    first = _summary(
        detection_count=2, max_confidence=0.6, strong_detection_count=1, weak_detection_count=1,
        samples=(_sample(0.6, 1000, is_strong=True), _sample(0.3, 0)),
        first_detection_offset_ms=0, last_detection_offset_ms=1000,
    )
    second = _summary(
        detection_count=1, max_confidence=0.4, strong_detection_count=0, weak_detection_count=1,
        samples=(_sample(0.4, 500),), first_detection_offset_ms=500, last_detection_offset_ms=500,
    )

    merged = merge_confidence_evidence((first, second))

    assert merged.detection_count == 3
    assert merged.max_confidence == 0.6
    assert merged.strong_detection_count == 1
    assert merged.weak_detection_count == 2
    assert [sample.source_offset_ms for sample in merged.samples] == [0, 500, 1000]  # ordered, not concatenation order
    assert merged.first_detection_offset_ms == 0
    assert merged.last_detection_offset_ms == 1000
    assert merged.mean_confidence == pytest.approx((0.3 + 0.4 + 0.6) / 3)


def test_merge_max_consecutive_takes_the_max_not_the_sum() -> None:
    """A real gap between two merged tracklets is not "more consecutive
    support" -- see the docstring on `merge_confidence_evidence`."""
    first = _summary(max_consecutive_detector_confirmed_frames=4)
    second = _summary(max_consecutive_detector_confirmed_frames=7)

    merged = merge_confidence_evidence((first, second))

    assert merged.max_consecutive_detector_confirmed_frames == 7


def test_merge_propagates_unknown_strong_weak_counts_rather_than_fabricating_a_partial_sum() -> None:
    """If one constituent's strong/weak split is genuinely unknown (a
    legacy-reconstructed tracklet), the merged total must not silently
    treat that unknown as zero."""
    known = _summary(detection_count=2, strong_detection_count=2, weak_detection_count=0)
    unknown = _summary(detection_count=3, strong_detection_count=None, weak_detection_count=None)

    merged = merge_confidence_evidence((known, unknown))

    assert merged.detection_count == 5
    assert merged.strong_detection_count is None
    assert merged.weak_detection_count is None


def test_merge_reports_broad_class_only_when_constituents_agree() -> None:
    matching = merge_confidence_evidence((_summary(broad_class="animal"), _summary(broad_class="animal")))
    assert matching.broad_class == "animal"

    # Structurally should never happen (classify_boundary already refuses to
    # merge mismatched broad_class tracklets) -- but this module must not
    # guess if it somehow did.
    mismatched = merge_confidence_evidence((_summary(broad_class="animal"), _summary(broad_class="person")))
    assert mismatched.broad_class is None


def test_merge_marks_truncated_when_any_constituent_was_or_when_the_merged_total_implies_it() -> None:
    complete = _summary(detection_count=1, samples=(_sample(0.5, 0),), sample_truncated=False)
    already_truncated = _summary(detection_count=5, samples=(), sample_truncated=True)

    merged = merge_confidence_evidence((complete, already_truncated))

    assert merged.sample_truncated is True
