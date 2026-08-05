"""Deterministic, shadow-only multi-scale detector benchmark and
strategy-vs-strategy comparison.

Observation Engine v2 Stage 6.4. This module is pure: no model inference, no
filesystem I/O, no product repository import. It consumes already-decoded,
already-cross-window-suppressed detections (produced by the caller from one
or more `multi_scale_strategy.StrategyWindow` inference calls per frame) and
reuses the existing Stage 6.2 `detector_benchmark` pipeline -- `classify_frame`,
`sweep_thresholds`, `cluster_static_false_positives`,
`simulate_temporal_policies`, `classify_sample_sufficiency` -- unchanged, over
the merged multi-scale `detections_by_frame`. It adds only what is genuinely
new at this stage: a visibility/occlusion/blur/clipping breakdown, scale-
specific facts (which window kind actually found which reviewed appearance),
and a strategy-vs-strategy comparison with the same runtime/resource
semantic exclusion `detector_comparison` established. See
docs/multi-scale-detector-benchmark-contract.md.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass
from typing import Literal

from mockingbird.observation.contracts import DetectionObservation
from mockingbird.observation.detector_benchmark import (
    MATCH_IOU_THRESHOLD,
    CalibrationManifest,
    classify_frame,
    classify_sample_sufficiency,
    cluster_static_false_positives,
    overall_classification,
    simulate_temporal_policies,
    sweep_thresholds,
)
from mockingbird.observation.multi_scale_strategy import (
    MultiScaleStrategyConfig,
    StrategyWindow,
    WindowedDetection,
    normalize_window_detections,
    suppress_cross_window_duplicates,
)
from mockingbird.observation.replay import semantic_fingerprint

MULTI_SCALE_REPORT_SCHEMA_VERSION = 1
MULTI_SCALE_BENCHMARK_VERSION = "multi-scale-detector-benchmark-v1"
COMPARISON_SCHEMA_VERSION = 1
COMPARISON_VERSION = "multi-scale-strategy-comparison-v1"

METRIC_EQUIVALENCE_TOLERANCE = 0.02


class MultiScaleBenchmarkError(ValueError):
    """A bounded multi-scale benchmark validation or execution failure code."""


def _ratio(numerator: int, denominator: int) -> float | None:
    return None if denominator <= 0 else numerator / denominator


# --------------------------------------------------------------------------
# Per-frame window merge (source-remapped, cross-window suppressed)
# --------------------------------------------------------------------------


def merge_frame_windows(
    windows: tuple[StrategyWindow, ...],
    local_detections_by_window: dict[str, tuple[DetectionObservation, ...]],
    *,
    cross_window_iou_threshold: float,
    max_final_detections: int,
) -> tuple[tuple[WindowedDetection, ...], tuple[WindowedDetection, ...]]:
    """Normalize every window's own local-space detections into source
    coordinates, then run one deterministic cross-window duplicate
    suppression pass over the whole merged set for this frame. Returns
    (kept, suppressed); both retain full window provenance."""

    windows_by_id = {window.window_id: window for window in windows}
    all_windowed: list[WindowedDetection] = []
    for window_id, local_detections in local_detections_by_window.items():
        window = windows_by_id.get(window_id)
        if window is None:
            raise MultiScaleBenchmarkError("unknown_window_id")
        all_windowed.extend(normalize_window_detections(window, local_detections))
    return suppress_cross_window_duplicates(
        tuple(all_windowed), iou_threshold=cross_window_iou_threshold, max_final_detections=max_final_detections,
    )


# --------------------------------------------------------------------------
# Visibility / occlusion / blur / clipping breakdown
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class VisibilityMetrics:
    """Recall broken out by one reviewed visibility fact at a time. Every
    bucket that a frame never populates ("unknown") is reported explicitly
    rather than silently folded into a denominator that implies more
    evidence than the cohort actually has."""

    fact: Literal["occlusion", "blur", "clipped"]
    bucket: str
    scorable_positive_frames: int
    true_positives: int
    false_negatives: int
    recall: float | None


def _visibility_bucket(frame_value: object) -> str:
    if frame_value is None:
        return "unknown"
    return str(frame_value)


def visibility_breakdown(
    manifest: CalibrationManifest, detections_by_frame: dict[str, tuple[DetectionObservation, ...]], *, threshold: float,
) -> tuple[VisibilityMetrics, ...]:
    results: list[VisibilityMetrics] = []
    for fact in ("occlusion", "blur", "clipped"):
        buckets: dict[str, list[tuple[int, int]]] = defaultdict(list)
        for frame in sorted(manifest.frames, key=lambda item: item.frame_id):
            if not frame.is_scorable or frame.animal_present != "yes":
                continue
            classification = classify_frame(frame, detections_by_frame.get(frame.frame_id, ()), threshold=threshold)
            fn = (
                classification.false_negative_below_threshold_count
                + classification.false_negative_privacy_masked_count
                + classification.false_negative_true_miss_count
            )
            bucket = _visibility_bucket(getattr(frame, fact))
            buckets[bucket].append((classification.true_positive_count, fn))
        for bucket, counts in sorted(buckets.items()):
            tp = sum(item[0] for item in counts)
            fn = sum(item[1] for item in counts)
            results.append(VisibilityMetrics(fact, bucket, len(counts), tp, fn, _ratio(tp, tp + fn)))  # type: ignore[arg-type]
    return tuple(results)


# --------------------------------------------------------------------------
# Scale-specific facts
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class ScaleSpecificFacts:
    true_appearances_full_frame_only: int
    true_appearances_tile_only: int
    true_appearances_both: int
    tile_recovered_true_appearances: int
    tile_introduced_false_positives: int
    tile_border_detection_count: int
    cross_window_duplicate_suppressions: int
    duplicates_before_suppression: int
    duplicates_after_suppression: int
    source_subject_pixel_area_median: float | None
    inferred_window_subject_pixel_area_median: float | None


def _iou(first: tuple[float, float, float, float], second: tuple[float, float, float, float]) -> float:
    left, top = max(first[0], second[0]), max(first[1], second[1])
    right, bottom = min(first[2], second[2]), min(first[3], second[3])
    intersection = max(0.0, right - left) * max(0.0, bottom - top)
    first_area = (first[2] - first[0]) * (first[3] - first[1])
    second_area = (second[2] - second[0]) * (second[3] - second[1])
    union = first_area + second_area - intersection
    return 0.0 if union <= 0.0 else intersection / union


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    mid = len(ordered) // 2
    return ordered[mid] if len(ordered) % 2 else (ordered[mid - 1] + ordered[mid]) / 2.0


def compute_scale_specific_facts(
    manifest: CalibrationManifest,
    kept_by_frame: dict[str, tuple[WindowedDetection, ...]],
    suppressed_by_frame: dict[str, tuple[WindowedDetection, ...]],
    *,
    threshold: float,
) -> ScaleSpecificFacts:
    """Diagnostic evidence only: never used to alter a detection, a
    threshold, or which window's result is kept. Every count here is
    derived strictly from the same already-decided (kept, suppressed) sets
    the accuracy metrics use; this never re-runs matching with different
    rules."""

    full_only = tile_only = both = tile_recovered = tile_fp = border_count = 0
    cross_window_suppressions = 0
    source_areas: list[float] = []
    window_areas: list[float] = []

    for frame in manifest.frames:
        if not frame.is_scorable:
            continue
        kept = kept_by_frame.get(frame.frame_id, ())
        suppressed = suppressed_by_frame.get(frame.frame_id, ())
        cross_window_suppressions += len(suppressed)
        eligible = [
            item for item in (*kept, *suppressed)
            if (item.detection.confidence or 0.0) >= threshold and item.detection.is_animal
        ]
        border_count += sum(1 for item in eligible if item.touches_window_edge)

        if frame.animal_present == "yes":
            source_width, source_height = frame.width, frame.height
            for truth in frame.boxes:
                overlapping = [item for item in eligible if _iou(truth.box, item.detection.bounding_box) >= MATCH_IOU_THRESHOLD]  # type: ignore[arg-type]
                kinds = {item.window.window_kind for item in overlapping}
                if kinds == {"full_frame"}:
                    full_only += 1
                elif kinds == {"tile"}:
                    tile_only += 1
                    tile_recovered += 1
                elif kinds == {"full_frame", "tile"}:
                    both += 1
                truth_width = (truth.box[2] - truth.box[0]) * source_width
                truth_height = (truth.box[3] - truth.box[1]) * source_height
                source_areas.append(truth_width * truth_height)
                tile_matches = [item for item in overlapping if item.window.window_kind == "tile"]
                if tile_matches:
                    best = max(tile_matches, key=lambda item: _iou(truth.box, item.detection.bounding_box))  # type: ignore[arg-type]
                    window = best.window
                    window_pixel_width = (window.source_box[2] - window.source_box[0]) * source_width
                    window_pixel_height = (window.source_box[3] - window.source_box[1]) * source_height
                    local_left, local_top, local_right, local_bottom = best.window_local_box
                    window_areas.append(
                        (local_right - local_left) * window_pixel_width
                        * (local_bottom - local_top) * window_pixel_height
                    )
        elif frame.animal_present == "no":
            tile_fp += sum(
                1 for item in kept
                if (item.detection.confidence or 0.0) >= threshold and item.detection.is_animal
                and item.window.window_kind == "tile"
            )

    duplicates_before = sum(len(kept_by_frame.get(f.frame_id, ())) + len(suppressed_by_frame.get(f.frame_id, ())) for f in manifest.frames)
    duplicates_after = sum(len(kept_by_frame.get(f.frame_id, ())) for f in manifest.frames)

    return ScaleSpecificFacts(
        true_appearances_full_frame_only=full_only,
        true_appearances_tile_only=tile_only,
        true_appearances_both=both,
        tile_recovered_true_appearances=tile_recovered,
        tile_introduced_false_positives=tile_fp,
        tile_border_detection_count=border_count,
        cross_window_duplicate_suppressions=cross_window_suppressions,
        duplicates_before_suppression=duplicates_before,
        duplicates_after_suppression=duplicates_after,
        source_subject_pixel_area_median=_median(source_areas),
        inferred_window_subject_pixel_area_median=_median(window_areas),
    )


# --------------------------------------------------------------------------
# Report assembly
# --------------------------------------------------------------------------


def build_multi_scale_semantic_report(
    *,
    manifest: CalibrationManifest,
    strategy: MultiScaleStrategyConfig,
    kept_by_frame: dict[str, tuple[WindowedDetection, ...]],
    suppressed_by_frame: dict[str, tuple[WindowedDetection, ...]],
    provider: dict[str, object],
) -> dict[str, object]:
    """Assemble the deterministic semantic report and its fingerprint.

    Absolute paths, host/PID facts, wall-clock timestamps, execution
    duration, windows-inferred-per-frame counts, and all latency/RSS/GPU
    facts never enter this dict; callers append those separately under an
    `execution` key excluded from `semantic_fingerprint`, the same
    convention `detector_benchmark.build_semantic_report` already uses."""

    threshold = strategy.per_window_score_threshold
    detections_by_frame = {
        frame_id: tuple(item.detection for item in items) for frame_id, items in kept_by_frame.items()
    }
    sweep = sweep_thresholds(manifest, detections_by_frame, (threshold,), configured_threshold=threshold)
    static_report = cluster_static_false_positives(manifest, detections_by_frame, threshold=threshold)
    temporal_results = simulate_temporal_policies(manifest, detections_by_frame, threshold=threshold)
    sufficiency = classify_sample_sufficiency(manifest)
    visibility = visibility_breakdown(manifest, detections_by_frame, threshold=threshold)
    scale_facts = compute_scale_specific_facts(manifest, kept_by_frame, suppressed_by_frame, threshold=threshold)

    semantic: dict[str, object] = {
        "schema_version": MULTI_SCALE_REPORT_SCHEMA_VERSION,
        "benchmark_version": MULTI_SCALE_BENCHMARK_VERSION,
        "strategy": asdict(strategy),
        "cohort": {
            "cohort_id": manifest.cohort_id,
            "manifest_fingerprint": manifest.fingerprint,
            "frame_count": len(manifest.frames),
        },
        "provider": provider,
        "threshold_sweep": [asdict(row) for row in sweep],
        "static_false_positive_clusters": asdict(static_report),
        "temporal_policy_simulation": [asdict(row) for row in temporal_results],
        "visibility_breakdown": [asdict(row) for row in visibility],
        "scale_specific_facts": asdict(scale_facts),
        "sample_sufficiency": asdict(sufficiency),
        "overall_classification": overall_classification(sufficiency),
        "creates_truth": False,
        "shadow_only": True,
        "production_proposal_authority": False,
    }
    return {**semantic, "semantic_fingerprint": semantic_fingerprint(semantic)}


# --------------------------------------------------------------------------
# Strategy-vs-strategy comparison (same model, two strategies)
# --------------------------------------------------------------------------

Classification = Literal["better", "equivalent", "worse", "insufficient_truth"]
DuplicateBehavior = Literal["acceptable", "degraded", "unacceptable", "insufficient_evidence"]
ResourceCost = Literal["acceptable", "degraded", "unacceptable", "insufficient_evidence"]
FinalRecommendation = Literal[
    "retain_full_frame_inference",
    "continue_tiled_strategy_offline_evaluation",
    "tiled_strategy_ready_for_bounded_live_shadow_trial",
    "tiled_strategy_unsuitable",
    "insufficient_reviewed_small_subject_data",
]

# Resource acceptability bounds (informational classification only; never
# semantic -- see `execution.resource_facts` in the report, mirroring
# `detector_comparison`'s runtime-exclusion boundary).
RESOURCE_WINDOWS_DEGRADED_RATIO = 3.0
RESOURCE_WINDOWS_UNACCEPTABLE_RATIO = 10.0


def _require_dict(value: dict[str, object], key: str) -> dict[str, object]:
    result = value.get(key)
    if not isinstance(result, dict):
        raise MultiScaleBenchmarkError(f"invalid_report_missing_{key}")
    return result


def _configured_row(report: dict[str, object]) -> dict[str, object] | None:
    sweep = report.get("threshold_sweep")
    if not isinstance(sweep, list) or not sweep:
        return None
    row = sweep[0]
    return row if isinstance(row, dict) else None


def _check_cohort_consistency(baseline: dict[str, object], candidate: dict[str, object]) -> tuple[bool, str | None]:
    baseline_fp = str(_require_dict(baseline, "cohort").get("manifest_fingerprint", ""))
    candidate_fp = str(_require_dict(candidate, "cohort").get("manifest_fingerprint", ""))
    if baseline_fp and baseline_fp == candidate_fp:
        return True, None
    return False, "manifest_fingerprint mismatch: baseline and candidate strategies were not scored against the identical reviewed cohort"


def _compare_value(baseline_value: object, candidate_value: object, *, lower_is_better: bool = False) -> Classification:
    b = baseline_value if isinstance(baseline_value, (int, float)) and not isinstance(baseline_value, bool) else None
    c = candidate_value if isinstance(candidate_value, (int, float)) and not isinstance(candidate_value, bool) else None
    if b is None or c is None:
        return "insufficient_truth"
    diff = c - b
    if abs(diff) <= METRIC_EQUIVALENCE_TOLERANCE:
        return "equivalent"
    better = diff < 0 if lower_is_better else diff > 0
    return "better" if better else "worse"


def _small_subject_recall_classification(baseline_row: dict[str, object] | None, candidate_row: dict[str, object] | None) -> Classification:
    if baseline_row is None or candidate_row is None:
        return "insufficient_truth"
    baseline_far = next(
        (item for item in baseline_row.get("subject_size_breakdown", []) if isinstance(item, dict) and item.get("distance_bucket") == "far"), None,
    )
    candidate_far = next(
        (item for item in candidate_row.get("subject_size_breakdown", []) if isinstance(item, dict) and item.get("distance_bucket") == "far"), None,
    )
    if baseline_far is None or candidate_far is None:
        return "insufficient_truth"
    return _compare_value(baseline_far.get("recall"), candidate_far.get("recall"))


def _static_scene_classification(baseline_report: dict[str, object], candidate_report: dict[str, object]) -> Classification:
    baseline_clusters = len(_require_dict(baseline_report, "static_false_positive_clusters").get("clusters", []))
    candidate_clusters = len(_require_dict(candidate_report, "static_false_positive_clusters").get("clusters", []))
    return _compare_value(baseline_clusters, candidate_clusters, lower_is_better=True)


def _duplicate_behavior(candidate_report: dict[str, object]) -> DuplicateBehavior:
    facts = candidate_report.get("scale_specific_facts")
    if not isinstance(facts, dict):
        return "insufficient_evidence"
    before, after = facts.get("duplicates_before_suppression"), facts.get("duplicates_after_suppression")
    if not isinstance(before, int) or not isinstance(after, int) or before <= 0:
        return "insufficient_evidence"
    suppressed_ratio = (before - after) / before
    # A large fraction of raw candidates being cross-window duplicates is
    # expected and healthy (tiling deliberately re-examines overlapping
    # regions); only a pathological case where suppression barely reduces
    # an inflated raw count signals degraded duplicate behavior.
    if suppressed_ratio >= 0.2 or before == after:
        return "acceptable"
    return "degraded"


def _resource_cost(baseline_report: dict[str, object], candidate_report: dict[str, object]) -> ResourceCost:
    baseline_windows = _execution_number(baseline_report, "max_windows_per_frame")
    candidate_windows = _execution_number(candidate_report, "max_windows_per_frame")
    if baseline_windows is None or candidate_windows is None or baseline_windows <= 0:
        return "insufficient_evidence"
    ratio = candidate_windows / baseline_windows
    if ratio <= RESOURCE_WINDOWS_DEGRADED_RATIO:
        return "acceptable"
    if ratio <= RESOURCE_WINDOWS_UNACCEPTABLE_RATIO:
        return "degraded"
    return "unacceptable"


def _execution_number(report: dict[str, object], key: str) -> float | None:
    execution = report.get("execution")
    if not isinstance(execution, dict):
        return None
    value = execution.get(key)
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _final_recommendation(
    *,
    cohort_consistent: bool, cohort_reason: str | None, sufficiency_ok: bool,
    recall: Classification, small_subject_recall: Classification, precision: Classification,
    static_scene_behavior: Classification, duplicate_behavior: DuplicateBehavior,
) -> tuple[FinalRecommendation, tuple[str, ...]]:
    """Deterministic verdict from semantic inputs only. Deliberately takes
    no resource-cost input: resource use is reported independently
    (`execution.resource_facts`) so it can never make this reproducible
    classification depend on wall-clock/RSS/GPU measurement."""

    if not cohort_consistent:
        return "insufficient_reviewed_small_subject_data", (cohort_reason or "cohort mismatch",)
    if not sufficiency_ok:
        return "insufficient_reviewed_small_subject_data", ("reviewed cohort does not clear the sample-sufficiency bound",)
    if duplicate_behavior == "unacceptable":
        return "tiled_strategy_unsuitable", ("duplicate behavior classified unacceptable",)
    if precision == "worse" and recall == "worse":
        return "retain_full_frame_inference", ("both precision and recall worse than the full-frame baseline",)
    if (
        recall in ("better", "equivalent")
        and precision in ("better", "equivalent")
        and small_subject_recall != "worse"
        and static_scene_behavior != "worse"
        and duplicate_behavior in ("acceptable", "degraded")
    ):
        return "tiled_strategy_ready_for_bounded_live_shadow_trial", (
            "recall and precision at least equivalent, small-subject recall not worse, no new "
            "static-scene regression -- check the separate non-semantic resource facts before a live shadow trial",
        )
    if small_subject_recall == "insufficient_truth":
        return "insufficient_reviewed_small_subject_data", ("far/small-subject bucket has no comparable truth on this cohort",)
    return "continue_tiled_strategy_offline_evaluation", ("mixed or inconclusive evidence; more reviewed small-subject data is warranted",)


def compare_strategy_reports(baseline_report: dict[str, object], candidate_report: dict[str, object]) -> dict[str, object]:
    """Compare a candidate strategy (e.g. `full_frame_plus_uniform_tiles`)
    against a baseline strategy (`full_frame`) for the *same model*, using
    two already-produced `build_multi_scale_semantic_report` payloads.
    Mirrors `detector_comparison.build_comparison_semantic_report`'s
    runtime-exclusion boundary: resource facts (windows inferred per frame,
    latency, RSS, GPU memory) are read from each report's own non-semantic
    `execution` section and never enter this comparison's own
    `semantic_fingerprint`."""

    cohort_consistent, cohort_reason = _check_cohort_consistency(baseline_report, candidate_report)
    baseline_row = _configured_row(baseline_report) if cohort_consistent else None
    candidate_row = _configured_row(candidate_report) if cohort_consistent else None

    precision = _compare_value(baseline_row.get("precision") if baseline_row else None, candidate_row.get("precision") if candidate_row else None)
    recall = _compare_value(baseline_row.get("recall") if baseline_row else None, candidate_row.get("recall") if candidate_row else None)
    small_subject_recall = _small_subject_recall_classification(baseline_row, candidate_row)
    static_scene_behavior = _static_scene_classification(baseline_report, candidate_report) if cohort_consistent else "insufficient_truth"
    duplicate_behavior = _duplicate_behavior(candidate_report)

    candidate_sufficiency = candidate_report.get("sample_sufficiency")
    sufficiency_ok = bool(isinstance(candidate_sufficiency, dict) and candidate_sufficiency.get("sufficient_for_threshold_selection"))

    recommendation, rationale = _final_recommendation(
        cohort_consistent=cohort_consistent, cohort_reason=cohort_reason, sufficiency_ok=sufficiency_ok,
        recall=recall, small_subject_recall=small_subject_recall, precision=precision,
        static_scene_behavior=static_scene_behavior, duplicate_behavior=duplicate_behavior,
    )

    semantic: dict[str, object] = {
        "schema_version": COMPARISON_SCHEMA_VERSION,
        "comparison_version": COMPARISON_VERSION,
        "baseline_strategy": _require_dict(baseline_report, "strategy").get("strategy_key"),
        "candidate_strategy": _require_dict(candidate_report, "strategy").get("strategy_key"),
        "cohort_consistent": cohort_consistent,
        "cohort_reason": cohort_reason,
        "precision": precision,
        "recall": recall,
        "small_subject_recall": small_subject_recall,
        "static_scene_behavior": static_scene_behavior,
        "duplicate_behavior": duplicate_behavior,
        "evidence_sufficient": cohort_consistent and sufficiency_ok,
        "final_recommendation": recommendation,
        "rationale": rationale,
        "creates_truth": False,
        "shadow_only": True,
        "production_proposal_authority": False,
    }
    execution = {
        "resource_facts": {
            "baseline_max_windows_per_frame": _execution_number(baseline_report, "max_windows_per_frame"),
            "candidate_max_windows_per_frame": _execution_number(candidate_report, "max_windows_per_frame"),
            "resource_cost": _resource_cost(baseline_report, candidate_report),
        },
    }
    return {**semantic, "semantic_fingerprint": semantic_fingerprint(semantic), "execution": execution}


__all__ = [
    "COMPARISON_SCHEMA_VERSION",
    "COMPARISON_VERSION",
    "METRIC_EQUIVALENCE_TOLERANCE",
    "MULTI_SCALE_BENCHMARK_VERSION",
    "MULTI_SCALE_REPORT_SCHEMA_VERSION",
    "RESOURCE_WINDOWS_DEGRADED_RATIO",
    "RESOURCE_WINDOWS_UNACCEPTABLE_RATIO",
    "MultiScaleBenchmarkError",
    "ScaleSpecificFacts",
    "VisibilityMetrics",
    "build_multi_scale_semantic_report",
    "compare_strategy_reports",
    "compute_scale_specific_facts",
    "merge_frame_windows",
    "visibility_breakdown",
]
