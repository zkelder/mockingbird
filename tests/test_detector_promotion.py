"""Hardware-free tests for the provider-neutral promotion boundary."""
from __future__ import annotations

from mockingbird.observation.detector_benchmark import CalibrationFrame, CalibrationManifest, ReviewedBox
from mockingbird.observation.detector_promotion import (
    CandidateFrameResult,
    CandidateFrameTiming,
    CandidateInputStrategy,
    CandidateModelProvenance,
    DetectorPromotionError,
    GovernedBenchmarkCase,
    NormalizedCandidateDetection,
    diagnostic_case_summary,
    isolate_candidate_failure,
    normalize_pixel_xyxy,
    reviewed_metric_summary,
    semantic_report,
)
import pytest


def _provenance(**changes: object) -> CandidateModelProvenance:
    values: dict[str, object] = {
        "model_key": "mdv6-apa-rtdetr-c",
        "model_version": "MDV6-apa-rtdetr-c",
        "architecture": "RT-DETRv2 R18",
        "weights_sha256": "a" * 64,
        "weights_source": "https://zenodo.org/records/18164133",
        "model_license": "Apache-2.0",
        "weights_license": "Apache-2.0",
        "redistribution": "Apache-2.0 redistribution permitted",
        "runtime_name": "PytorchWildlife",
        "runtime_version": "1.3.0",
        "package_sha256": "b" * 64,
        "backend": "torch-cuda",
        "input_width": 640,
        "input_height": 640,
        "preprocessing": "RGB stretch to 640x640; ToTensor",
        "postprocessing": "official RT-DETR postprocessor; threshold 0.1",
        "taxonomy": "MegaDetector animal/person/vehicle",
    }
    values.update(changes)
    return CandidateModelProvenance(**values)  # type: ignore[arg-type]


STRATEGY = CandidateInputStrategy("native-full-frame", "original source pixels", 640, 640)
TIMING = CandidateFrameTiming(1.0, 2.0, 0.5, 3.5)


def _det(
    frame_id: str, box: tuple[float, float, float, float], confidence: float = 0.8,
) -> NormalizedCandidateDetection:
    provenance = _provenance()
    return NormalizedCandidateDetection(
        frame_id, "animal", confidence, box, "animal", provenance.model_key,
        provenance.model_version, STRATEGY.strategy_key, provenance.backend,
    )


def test_pixel_output_normalizes_to_source_relative_box() -> None:
    result = normalize_pixel_xyxy(
        frame_id="bird", xyxy=(100, 50, 300, 150), source_width=1000,
        source_height=500, confidence=0.75, native_label="animal",
        broad_class="animal", provenance=_provenance(), strategy=STRATEGY,
    )
    assert result.source_box == (0.1, 0.1, 0.3, 0.3)
    assert result.broad_class == "animal"


def test_normalization_rejects_out_of_source_box_instead_of_clipping() -> None:
    with pytest.raises(DetectorPromotionError, match="pixel_detection_outside_source"):
        normalize_pixel_xyxy(
            frame_id="bird", xyxy=(-1, 0, 2, 2), source_width=10,
            source_height=10, confidence=0.5, native_label="animal",
            broad_class="animal", provenance=_provenance(), strategy=STRATEGY,
        )


def test_provenance_records_checksums_and_permissive_license() -> None:
    provenance = _provenance()
    assert provenance.weights_sha256 == "a" * 64
    assert provenance.package_sha256 == "b" * 64
    assert provenance.license_classification == "acceptable"
    assert provenance.promotion_license_eligible is True


def test_agpl_weights_are_not_promotion_license_eligible() -> None:
    provenance = _provenance(model_license="AGPL-3.0", weights_license="AGPL-3.0")
    assert provenance.license_classification == "unacceptable"
    assert provenance.promotion_license_eligible is False


def test_invalid_weight_fingerprint_is_rejected() -> None:
    with pytest.raises(DetectorPromotionError, match="invalid_weights_sha256"):
        _provenance(weights_sha256="not-a-checksum")


def test_diagnostic_case_never_becomes_a_population_metric() -> None:
    case = GovernedBenchmarkCase(
        "bird", "diagnostic_only", "agent-visual-inspection-2026-08-11",
        "real bird with diagnostic ROI", "field-report:candidate-011", "yes",
        bird_box=(0.4, 0.4, 0.5, 0.5),
        reviewed_by="agent visual inspection, not independently human-confirmed",
    )
    result = CandidateFrameResult(
        "bird", (_det("bird", (0.41, 0.41, 0.49, 0.49)), _det("bird", (0.7, 0.7, 0.8, 0.8), 0.9)), TIMING,
    )
    summary = diagnostic_case_summary(case, result)
    assert summary["detected_actual_bird"] is True
    assert summary["best_bird_confidence"] == 0.8
    assert summary["highest_confidence_off_roi"] == 0.9
    assert summary["creates_population_metric"] is False
    assert case.reviewed_metric_eligible is False
    assert case.localization_metric_eligible is False


def test_reviewed_truth_requires_human_reviewer_identity() -> None:
    with pytest.raises(ValueError, match="reviewed_truth_requires_reviewer_identity"):
        GovernedBenchmarkCase(
            "reviewed", "reviewed_truth", "reviewed-cohort", "bird", "manifest:frame", "yes",
            bird_box=(0.4, 0.4, 0.5, 0.5),
        )


def test_reviewed_metric_calculation_reuses_accepted_iou_scorer() -> None:
    manifest = CalibrationManifest(1, "fixture", "human-reviewed fixture", (
        CalibrationFrame(
            "positive", "images/positive.jpg", "a" * 64, 100, 100, "yes",
            boxes=(ReviewedBox((0.2, 0.2, 0.4, 0.4)),), scene_group="a",
        ),
        CalibrationFrame(
            "negative", "images/negative.jpg", "b" * 64, 100, 100, "no", scene_group="b",
        ),
    ))
    results = (
        CandidateFrameResult("positive", (_det("positive", (0.2, 0.2, 0.4, 0.4)),), TIMING),
        CandidateFrameResult("negative", (), TIMING),
    )
    metrics = reviewed_metric_summary(manifest, results, threshold=0.1)
    assert metrics["true_positives"] == 1
    assert metrics["false_positives"] == 0
    assert metrics["false_negatives_true_miss"] == 0
    assert metrics["precision"] == 1.0
    assert metrics["recall"] == 1.0


def test_semantic_report_is_deterministic_and_candidate_order_independent() -> None:
    first = {
        "candidate_key": "z", "metric": 1, "runtime": {"latency_ms": 10},
        "model": {"runtime": "onnxruntime-gpu 1.28.0"},
    }
    second = {"candidate_key": "a", "metric": 2, "timing_ms": {"total": 20}}
    report_a = semantic_report(
        corpus={"fingerprint": "c"}, candidates=(first, second),
        decision={"state": "C"},
        diagnostics=({"case_id": "d", "timing_ms": {"total": 10}},),
    )
    report_b = semantic_report(
        corpus={"fingerprint": "c"},
        candidates=(
            {**second, "timing_ms": {"total": 999}},
            {**first, "runtime": {"latency_ms": 999}},
        ),
        decision={"state": "C"},
        diagnostics=({"case_id": "d", "timing_ms": {"total": 999}},),
    )
    assert report_a == report_b
    assert report_a["changes_production_authority"] is False
    assert "runtime" not in report_a["candidates"][1]
    assert report_a["candidates"][1]["model"]["runtime"] == "onnxruntime-gpu 1.28.0"
    assert "timing_ms" not in report_a["candidates"][0]
    assert report_b["diagnostic_cases"] == [{"case_id": "d"}]


def test_candidate_failure_is_isolated() -> None:
    def fail() -> int:
        raise RuntimeError("cuda out of memory")

    value, failure = isolate_candidate_failure("candidate-a", fail)
    assert value is None
    assert failure is not None
    assert failure.candidate_key == "candidate-a"
    assert failure.error_type == "RuntimeError"
    assert failure.error_code == "cuda out of memory"

    value, failure = isolate_candidate_failure("candidate-b", lambda: 7)
    assert value == 7
    assert failure is None
