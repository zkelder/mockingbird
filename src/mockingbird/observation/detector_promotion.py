"""Provider-neutral records and scoring for detector promotion benchmarks.

Candidate runtimes may use ONNX Runtime, native PyTorch, TensorRT, or another
local backend, but they normalize their output here before the existing
reviewed detector benchmark scores it. Runtime measurements remain
non-semantic and diagnostic cases remain outside reviewed metric denominators.
See ``docs/detector-promotion-benchmark-contract.md``.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from hashlib import sha256
import json
import math
import re
from typing import Callable, Literal, TypeVar, cast

from mockingbird.observation.contracts import DetectionObservation
from mockingbird.observation.detector_benchmark import CalibrationManifest, sweep_thresholds
from mockingbird.observation.detector_comparison import classify_license
from mockingbird.observation.evaluation_governance import EvaluationExample, EvaluationExampleStatus

PROMOTION_BENCHMARK_SCHEMA_VERSION = 1
PROMOTION_BENCHMARK_VERSION = "detector-promotion-benchmark-v1"
DEFAULT_MATCH_IOU = 0.5
BroadClass = Literal["animal", "person", "vehicle", "other"]
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_NON_SEMANTIC_REPORT_KEYS = frozenset({"execution", "resource_usage", "timing", "timing_ms"})


class DetectorPromotionError(ValueError):
    """A bounded validation failure at the candidate benchmark boundary."""


def _finite(value: float) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _validate_box(box: tuple[float, float, float, float]) -> None:
    if not all(_finite(item) for item in box):
        raise DetectorPromotionError("invalid_source_relative_box")
    left, top, right, bottom = box
    if left < 0 or top < 0 or right > 1 or bottom > 1 or right <= left or bottom <= top:
        raise DetectorPromotionError("invalid_source_relative_box")


@dataclass(frozen=True)
class CandidateModelProvenance:
    """Exact model, weights, runtime, and licensing facts for one candidate."""

    model_key: str
    model_version: str
    architecture: str
    weights_sha256: str
    weights_source: str
    model_license: str
    weights_license: str
    redistribution: str
    runtime_name: str
    runtime_version: str
    package_sha256: str | None
    backend: str
    input_width: int
    input_height: int
    preprocessing: str
    postprocessing: str
    taxonomy: str

    def __post_init__(self) -> None:
        required = (
            self.model_key, self.model_version, self.architecture, self.weights_source,
            self.model_license, self.weights_license, self.redistribution,
            self.runtime_name, self.runtime_version, self.backend,
            self.preprocessing, self.postprocessing, self.taxonomy,
        )
        if any(not value.strip() for value in required):
            raise DetectorPromotionError("incomplete_candidate_provenance")
        if not _SHA256.fullmatch(self.weights_sha256):
            raise DetectorPromotionError("invalid_weights_sha256")
        if self.package_sha256 is not None and not _SHA256.fullmatch(self.package_sha256):
            raise DetectorPromotionError("invalid_package_sha256")
        if self.input_width <= 0 or self.input_height <= 0:
            raise DetectorPromotionError("invalid_candidate_input_resolution")

    @property
    def license_classification(self) -> str:
        return classify_license(
            f"{self.model_license}; weights={self.weights_license}", self.redistribution,
        )

    @property
    def promotion_license_eligible(self) -> bool:
        return self.license_classification == "acceptable"


@dataclass(frozen=True)
class CandidateInputStrategy:
    strategy_key: str
    source_pixel_policy: str
    inference_width: int
    inference_height: int
    full_frame_enabled: bool = True
    max_tiles_per_frame: int = 0
    tile_overlap: float = 0.0

    def __post_init__(self) -> None:
        if not self.strategy_key.strip() or not self.source_pixel_policy.strip():
            raise DetectorPromotionError("invalid_candidate_input_strategy")
        if self.inference_width <= 0 or self.inference_height <= 0 or self.max_tiles_per_frame < 0:
            raise DetectorPromotionError("invalid_candidate_input_strategy")
        if not 0 <= self.tile_overlap < 1:
            raise DetectorPromotionError("invalid_candidate_input_strategy")


@dataclass(frozen=True)
class NormalizedCandidateDetection:
    """One candidate output in MockingBird source-coordinate semantics."""

    frame_id: str
    broad_class: BroadClass
    confidence: float
    source_box: tuple[float, float, float, float]
    native_label: str
    model_key: str
    model_version: str
    strategy_key: str
    backend: str

    def __post_init__(self) -> None:
        text = (
            self.frame_id, self.native_label, self.model_key, self.model_version,
            self.strategy_key, self.backend,
        )
        if any(not value.strip() for value in text):
            raise DetectorPromotionError("incomplete_normalized_detection")
        if self.broad_class not in {"animal", "person", "vehicle", "other"}:
            raise DetectorPromotionError("invalid_broad_class")
        if not _finite(self.confidence) or not 0 <= self.confidence <= 1:
            raise DetectorPromotionError("invalid_candidate_confidence")
        _validate_box(self.source_box)

    def as_observation(self, *, ordinal: int) -> DetectionObservation:
        stable = json.dumps(
            [self.frame_id, self.model_key, self.model_version, self.strategy_key,
             self.broad_class, self.native_label, self.confidence, self.source_box, ordinal],
            separators=(",", ":"), ensure_ascii=True,
        )
        return DetectionObservation(
            detector_id=self.model_key, label=self.broad_class, confidence=self.confidence,
            captured_at=datetime(1970, 1, 1, tzinfo=UTC),
            observation_id=sha256(stable.encode()).hexdigest(), frame_id=self.frame_id,
            provider_id=self.backend, model_key=self.model_key,
            generation_id=f"{self.model_key}:{self.model_version}:{self.strategy_key}",
            bounding_box=self.source_box, class_source_label=self.native_label,
            is_animal=self.broad_class == "animal",
        )


def normalize_pixel_xyxy(
    *, frame_id: str, xyxy: tuple[float, float, float, float], source_width: int,
    source_height: int, confidence: float, native_label: str,
    broad_class: BroadClass, provenance: CandidateModelProvenance,
    strategy: CandidateInputStrategy,
) -> NormalizedCandidateDetection:
    """Normalize a source-pixel ``xyxy`` record without resizing or clipping it."""

    if source_width <= 0 or source_height <= 0 or not all(_finite(item) for item in xyxy):
        raise DetectorPromotionError("invalid_pixel_detection")
    left, top, right, bottom = xyxy
    if left < 0 or top < 0 or right > source_width or bottom > source_height:
        raise DetectorPromotionError("pixel_detection_outside_source")
    return NormalizedCandidateDetection(
        frame_id=frame_id, broad_class=broad_class, confidence=float(confidence),
        source_box=(left / source_width, top / source_height, right / source_width, bottom / source_height),
        native_label=native_label, model_key=provenance.model_key,
        model_version=provenance.model_version, strategy_key=strategy.strategy_key,
        backend=provenance.backend,
    )


@dataclass(frozen=True)
class CandidateFrameTiming:
    preprocessing_ms: float
    inference_ms: float
    postprocessing_ms: float
    total_ms: float

    def __post_init__(self) -> None:
        values = (self.preprocessing_ms, self.inference_ms, self.postprocessing_ms, self.total_ms)
        if not all(_finite(value) and value >= 0 for value in values):
            raise DetectorPromotionError("invalid_candidate_timing")
        if self.total_ms + 1e-6 < self.preprocessing_ms + self.inference_ms + self.postprocessing_ms:
            raise DetectorPromotionError("invalid_candidate_timing_total")


@dataclass(frozen=True)
class CandidateFrameResult:
    frame_id: str
    detections: tuple[NormalizedCandidateDetection, ...]
    timing: CandidateFrameTiming

    def __post_init__(self) -> None:
        if not self.frame_id.strip() or any(item.frame_id != self.frame_id for item in self.detections):
            raise DetectorPromotionError("candidate_frame_identity_mismatch")


@dataclass(frozen=True)
class CandidateFailure:
    candidate_key: str
    error_type: str
    error_code: str


T = TypeVar("T")


def isolate_candidate_failure(candidate_key: str, operation: Callable[[], T]) -> tuple[T | None, CandidateFailure | None]:
    """Keep one optional benchmark backend failure from aborting other models."""

    try:
        return operation(), None
    except Exception as error:  # third-party adapter boundary is intentionally contained
        code = str(error).strip().splitlines()[0][:160] or "candidate_runtime_failed"
        return None, CandidateFailure(candidate_key, type(error).__name__, code)


@dataclass(frozen=True)
class GovernedBenchmarkCase:
    """Governance attached to a preserved image; never inferred from output."""

    case_id: str
    status: EvaluationExampleStatus
    source: str
    description: str
    provenance_ref: str
    animal_present: Literal["yes", "no", "ambiguous"]
    bird_box: tuple[float, float, float, float] | None = None
    reviewed_by: str | None = None

    def __post_init__(self) -> None:
        EvaluationExample(
            example_id=self.case_id, status=self.status, source=self.source,
            description=self.description, provenance_ref=self.provenance_ref,
            reviewed_by=self.reviewed_by,
        )
        if self.bird_box is not None:
            _validate_box(self.bird_box)

    @property
    def reviewed_metric_eligible(self) -> bool:
        return self.status == "reviewed_truth"

    @property
    def localization_metric_eligible(self) -> bool:
        return self.reviewed_metric_eligible and self.bird_box is not None


def intersection_over_union(
    first: tuple[float, float, float, float], second: tuple[float, float, float, float],
) -> float:
    _validate_box(first)
    _validate_box(second)
    left, top = max(first[0], second[0]), max(first[1], second[1])
    right, bottom = min(first[2], second[2]), min(first[3], second[3])
    intersection = max(0.0, right - left) * max(0.0, bottom - top)
    first_area = (first[2] - first[0]) * (first[3] - first[1])
    second_area = (second[2] - second[0]) * (second[3] - second[1])
    union = first_area + second_area - intersection
    return 0.0 if union <= 0 else intersection / union


def diagnostic_case_summary(
    case: GovernedBenchmarkCase, result: CandidateFrameResult, *, match_iou: float = DEFAULT_MATCH_IOU,
) -> dict[str, object]:
    """Engineering facts for one case; explicitly refuses reviewed cases."""

    if case.status != "diagnostic_only":
        raise DetectorPromotionError("diagnostic_summary_requires_diagnostic_case")
    if case.case_id != result.frame_id:
        raise DetectorPromotionError("diagnostic_case_result_mismatch")
    animal = tuple(item for item in result.detections if item.broad_class == "animal")
    overlaps = [intersection_over_union(item.source_box, case.bird_box) for item in animal] if case.bird_box else []
    best_iou = max(overlaps, default=None)
    on_bird = [(item, overlap) for item, overlap in zip(animal, overlaps) if overlap >= match_iou]
    off_bird = [
        item for index, item in enumerate(animal)
        if not overlaps or index >= len(overlaps) or overlaps[index] < match_iou
    ]
    return {
        "case_id": case.case_id, "truth_status": case.status,
        "creates_population_metric": False,
        "detected_actual_bird": bool(on_bird) if case.bird_box else None,
        "best_bird_confidence": max((item.confidence for item, _ in on_bird), default=None),
        "best_iou_with_diagnostic_roi": best_iou,
        "highest_confidence_off_roi": max((item.confidence for item in off_bird), default=None),
        "off_roi_detection_count": len(off_bird), "animal_detection_count": len(animal),
        "timing_ms": asdict(result.timing),
    }


def reviewed_metric_summary(
    manifest: CalibrationManifest, frame_results: tuple[CandidateFrameResult, ...], *, threshold: float,
) -> dict[str, object]:
    """Delegate reviewed IoU/precision/recall accounting to the accepted scorer."""

    by_frame: dict[str, tuple[DetectionObservation, ...]] = {}
    for frame_result in sorted(frame_results, key=lambda item: item.frame_id):
        ordered = sorted(
            frame_result.detections,
            key=lambda item: (-item.confidence, item.broad_class, item.source_box, item.native_label),
        )
        by_frame[frame_result.frame_id] = tuple(
            item.as_observation(ordinal=index) for index, item in enumerate(ordered)
        )
    row = sweep_thresholds(manifest, by_frame, (threshold,), configured_threshold=threshold)[0]
    return asdict(row)


def _semantic_projection(value: object, *, root: bool = True) -> object:
    """Remove explicitly non-semantic execution facts from a report value."""

    if isinstance(value, dict):
        return {
            key: _semantic_projection(item, root=False)
            for key, item in value.items()
            if key not in _NON_SEMANTIC_REPORT_KEYS and not (root and key == "runtime")
        }
    if isinstance(value, (list, tuple)):
        return [_semantic_projection(item, root=False) for item in value]
    return value


def semantic_report(
    *, corpus: dict[str, object], candidates: tuple[dict[str, object], ...],
    decision: dict[str, object], diagnostics: tuple[dict[str, object], ...] = (),
) -> dict[str, object]:
    """Create a stable report fingerprint; callers keep runtime facts separate."""

    projected_corpus = _semantic_projection(corpus)
    projected_candidates = [
        cast(dict[str, object], _semantic_projection(item))
        for item in candidates
    ]
    projected_decision = _semantic_projection(decision)
    projected_diagnostics = [
        cast(dict[str, object], _semantic_projection(item))
        for item in diagnostics
    ]
    semantic: dict[str, object] = {
        "schema_version": PROMOTION_BENCHMARK_SCHEMA_VERSION,
        "benchmark_version": PROMOTION_BENCHMARK_VERSION,
        "corpus": projected_corpus,
        "candidates": sorted(projected_candidates, key=lambda item: str(item.get("candidate_key", ""))),
        "decision": projected_decision,
        "diagnostic_cases": sorted(
            projected_diagnostics,
            key=lambda item: (str(item.get("case_id", "")), str(item.get("candidate_strategy", ""))),
        ),
        "creates_truth": False,
        "changes_production_authority": False,
    }
    serialized = json.dumps(semantic, sort_keys=True, separators=(",", ":"), default=str).encode()
    return {**semantic, "semantic_fingerprint": sha256(serialized).hexdigest()}


__all__ = [
    "CandidateFailure", "CandidateFrameResult", "CandidateFrameTiming", "CandidateInputStrategy",
    "CandidateModelProvenance", "DetectorPromotionError", "GovernedBenchmarkCase",
    "NormalizedCandidateDetection", "diagnostic_case_summary", "intersection_over_union",
    "isolate_candidate_failure", "normalize_pixel_xyxy", "reviewed_metric_summary", "semantic_report",
]
