"""Deterministic, shadow-only cross-candidate detector comparison.

Observation Engine v2 Stage 6.3. This module is pure: no model inference, no
filesystem I/O, no product repository import. It consumes already-produced
Stage 6.2 `detector-benchmark-report.json` payloads -- one baseline (MDv5) and
one or more candidates, each already scored against the same reviewed
calibration cohort with its own explicit threshold grid -- and produces a
deterministic side-by-side comparison. It never re-runs inference, never
compares raw confidence values across models as if they were calibrated
identically, never selects an automatic winner, and never mutates a runtime
threshold, Ignore region, tracker, or default-model setting. Runtime/resource
facts (latency, GPU memory, model size, and the acceptable/degraded/
unacceptable classification derived from them) are reported only in the
non-semantic `execution` section and never influence `semantic_fingerprint`
or `final_recommendation`; see docs/detector-candidate-comparison-contract.md.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from typing import Literal

from mockingbird.observation.replay import semantic_fingerprint

COMPARISON_SCHEMA_VERSION = 1
COMPARISON_VERSION = "detector-candidate-comparison-v1"

# A metric within this fraction of the baseline is "equivalent" rather than a
# noisy better/worse call on a still-small reviewed cohort.
METRIC_EQUIVALENCE_TOLERANCE = 0.02
# Runtime acceptability bounds (informational classification only; never
# semantic -- see `execution.runtime_facts_by_candidate` in the report).
RUNTIME_LATENCY_DEGRADED_RATIO = 3.0
RUNTIME_LATENCY_UNACCEPTABLE_RATIO = 10.0
RUNTIME_GPU_MEMORY_DEGRADED_MIB = 4096
RUNTIME_GPU_MEMORY_UNACCEPTABLE_MIB = 7000

HOOK_SCENE_GROUP = "front-yard-camera-daylight-smoke-2026-08-05"
HOOK_STRUCTURE_LABEL = "shepherds_hook_plant_hanger"

Classification = Literal["better", "equivalent", "worse", "insufficient_truth", "unsupported_for_one_model"]


class DetectorComparisonError(ValueError):
    """A bounded detector-comparison validation or execution failure code."""


# --------------------------------------------------------------------------
# Report summaries
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class ModelSummary:
    label: str
    model_key: str
    model_version: str
    model_fingerprint: str
    license: str
    redistribution: str
    taxonomy: str
    broad_classes: tuple[str, ...]
    animal_classes: tuple[str, ...]
    decoder: str
    manifest_fingerprint: str
    configured_threshold: float
    threshold_grid: tuple[float, ...]
    overall_classification: str


def _string_tuple(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(item for item in value if isinstance(item, str))


def _model_summary(label: str, report: dict[str, object]) -> ModelSummary:
    provider = _require_dict(report, "provider")
    model = _require_dict(provider, "model")
    cohort = _require_dict(report, "cohort")
    return ModelSummary(
        label=label,
        model_key=str(model.get("key", "")),
        model_version=str(model.get("version", "")),
        model_fingerprint=str(model.get("fingerprint", "")),
        license=str(model.get("license", "unknown")),
        redistribution=str(model.get("redistribution", "unknown")),
        taxonomy=str(model.get("taxonomy", "unknown")),
        broad_classes=_string_tuple(model.get("broad_classes")),
        animal_classes=_string_tuple(model.get("animal_classes")),
        decoder=str(model.get("decoder", "unknown")),
        manifest_fingerprint=str(cohort.get("manifest_fingerprint", "")),
        configured_threshold=float(report.get("configured_threshold", 0.0)),  # type: ignore[arg-type]
        threshold_grid=tuple(report.get("threshold_grid", ())),  # type: ignore[arg-type]
        overall_classification=str(report.get("overall_classification", "unknown")),
    )


def _taxonomy_documented(summary: ModelSummary) -> bool:
    """A model whose report never recorded what its broad-class taxonomy
    means cannot be trusted to mean the same thing by "animal" as the other
    side; numeric precision/recall/subject-size comparison is unsupported,
    not silently computed, when either side is undocumented this way."""

    return bool(summary.taxonomy) and summary.taxonomy != "unknown"


def _require_dict(value: dict[str, object], key: str) -> dict[str, object]:
    result = value.get(key)
    if not isinstance(result, dict):
        raise DetectorComparisonError(f"invalid_report_missing_{key}")
    return result


def _configured_row(report: dict[str, object]) -> dict[str, object] | None:
    sweep = report.get("threshold_sweep")
    if not isinstance(sweep, list):
        return None
    for row in sweep:
        if isinstance(row, dict) and row.get("is_configured_threshold"):
            return row
    return None


# --------------------------------------------------------------------------
# Cohort consistency
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class CohortConsistency:
    consistent: bool
    baseline_manifest_fingerprint: str
    candidate_manifest_fingerprint: str
    reason: str | None = None


def _check_cohort_consistency(baseline: dict[str, object], candidate: dict[str, object]) -> CohortConsistency:
    baseline_cohort = _require_dict(baseline, "cohort")
    candidate_cohort = _require_dict(candidate, "cohort")
    baseline_fp = str(baseline_cohort.get("manifest_fingerprint", ""))
    candidate_fp = str(candidate_cohort.get("manifest_fingerprint", ""))
    if baseline_fp and baseline_fp == candidate_fp:
        return CohortConsistency(True, baseline_fp, candidate_fp)
    return CohortConsistency(
        False, baseline_fp, candidate_fp,
        reason="manifest_fingerprint mismatch: baseline and candidate were not scored against the identical reviewed cohort",
    )


# --------------------------------------------------------------------------
# Metric comparison (each model's own configured operating point)
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class MetricComparison:
    metric: str
    baseline_value: float | int | None
    candidate_value: float | int | None
    classification: Classification


def _compare_value(
    metric: str, baseline_value: object, candidate_value: object, *, lower_is_better: bool = False,
    tolerance: float = METRIC_EQUIVALENCE_TOLERANCE,
) -> MetricComparison:
    b = baseline_value if isinstance(baseline_value, (int, float)) and not isinstance(baseline_value, bool) else None
    c = candidate_value if isinstance(candidate_value, (int, float)) and not isinstance(candidate_value, bool) else None
    if b is None or c is None:
        classification: Classification = "insufficient_truth"
    else:
        diff = c - b
        if abs(diff) <= tolerance:
            classification = "equivalent"
        else:
            better = diff < 0 if lower_is_better else diff > 0
            classification = "better" if better else "worse"
    return MetricComparison(metric, b, c, classification)


_ACCURACY_METRICS: tuple[tuple[str, bool], ...] = (
    ("precision", False),
    ("recall", False),
    ("positive_frame_recall", False),
    ("false_positives_per_negative_frame", True),
    ("false_positive_frame_count", True),
    ("duplicate_detections", True),
)


def _accuracy_metrics(baseline_row: dict[str, object] | None, candidate_row: dict[str, object] | None) -> tuple[MetricComparison, ...]:
    if baseline_row is None or candidate_row is None:
        return tuple(
            MetricComparison(name, None, None, "unsupported_for_one_model") for name, _ in _ACCURACY_METRICS
        )
    return tuple(
        _compare_value(name, baseline_row.get(name), candidate_row.get(name), lower_is_better=lower_is_better)
        for name, lower_is_better in _ACCURACY_METRICS
    )


@dataclass(frozen=True)
class StratumComparison:
    stratum_kind: Literal["scene_group", "subject_size"]
    stratum_key: str
    metric: str
    baseline_value: float | int | None
    candidate_value: float | int | None
    classification: Classification


def _scene_group_metrics(baseline_row: dict[str, object] | None, candidate_row: dict[str, object] | None) -> tuple[StratumComparison, ...]:
    if baseline_row is None or candidate_row is None:
        return ()
    baseline_scenes = {
        item["scene_group"]: item for item in baseline_row.get("scene_group_breakdown", []) if isinstance(item, dict)
    }
    candidate_scenes = {
        item["scene_group"]: item for item in candidate_row.get("scene_group_breakdown", []) if isinstance(item, dict)
    }
    results = []
    for scene in sorted(set(baseline_scenes) | set(candidate_scenes)):
        baseline_item = baseline_scenes.get(scene)
        candidate_item = candidate_scenes.get(scene)
        for metric in ("precision", "recall"):
            comparison = _compare_value(
                metric,
                baseline_item.get(metric) if baseline_item else None,
                candidate_item.get(metric) if candidate_item else None,
            )
            results.append(StratumComparison("scene_group", scene, metric, comparison.baseline_value, comparison.candidate_value, comparison.classification))
    return tuple(results)


def _subject_size_metrics(baseline_row: dict[str, object] | None, candidate_row: dict[str, object] | None) -> tuple[StratumComparison, ...]:
    if baseline_row is None or candidate_row is None:
        return ()
    baseline_sizes = {
        item["distance_bucket"]: item for item in baseline_row.get("subject_size_breakdown", []) if isinstance(item, dict)
    }
    candidate_sizes = {
        item["distance_bucket"]: item for item in candidate_row.get("subject_size_breakdown", []) if isinstance(item, dict)
    }
    results = []
    for bucket in sorted(set(baseline_sizes) | set(candidate_sizes)):
        baseline_item = baseline_sizes.get(bucket)
        candidate_item = candidate_sizes.get(bucket)
        comparison = _compare_value(
            "recall",
            baseline_item.get("recall") if baseline_item else None,
            candidate_item.get("recall") if candidate_item else None,
        )
        results.append(StratumComparison("subject_size", bucket, "recall", comparison.baseline_value, comparison.candidate_value, comparison.classification))
    return tuple(results)


# Strata the task requires reporting on, but this reviewed cohort never
# populates (every frame's `occlusion`/`blur` field is `None` -- no reviewer
# recorded either fact). Reported as an explicit, honest gap rather than a
# fabricated single "unknown" bucket breakdown.
UNEVALUATED_STRATA = ("blur", "occlusion")


# --------------------------------------------------------------------------
# Static false-positive cluster / shepherd's-hook diagnostic
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class HookDiagnostic:
    detects_hook: bool
    hook_score_minimum: float | None
    hook_score_maximum: float | None
    hook_frames_affected: int
    other_daylight_scene_clusters: int
    temporal_false_episodes_aggregate: int | None


def _hook_diagnostic(report: dict[str, object]) -> HookDiagnostic:
    static_report = _require_dict(report, "static_false_positive_clusters")
    clusters = [item for item in static_report.get("clusters", []) if isinstance(item, dict)]
    daylight_clusters = [item for item in clusters if item.get("scene_group") == HOOK_SCENE_GROUP]
    hook_clusters = [item for item in daylight_clusters if item.get("matched_static_structure") == HOOK_STRUCTURE_LABEL]
    other_clusters = [item for item in daylight_clusters if item not in hook_clusters]

    temporal = [item for item in report.get("temporal_policy_simulation", []) if isinstance(item, dict)]
    multi_frame_false_episodes = [
        item.get("confirmed_false_episodes") for item in temporal
        if item.get("supported") and item.get("policy") != "single_detection"
        and isinstance(item.get("confirmed_false_episodes"), int)
    ]
    aggregate_false_episodes = max(multi_frame_false_episodes, default=None) if multi_frame_false_episodes else None

    if hook_clusters:
        cluster = hook_clusters[0]
        return HookDiagnostic(
            True, cluster.get("score_minimum"), cluster.get("score_maximum"),
            len(cluster.get("frame_ids", ())), len(other_clusters), aggregate_false_episodes,
        )
    return HookDiagnostic(False, None, None, 0, len(other_clusters), aggregate_false_episodes)


@dataclass(frozen=True)
class StaticClusterBehavior:
    baseline: HookDiagnostic
    candidate: HookDiagnostic
    classification: Literal["better", "equivalent", "worse", "insufficient_truth"]
    note: str


def _static_cluster_behavior(baseline_report: dict[str, object], candidate_report: dict[str, object]) -> StaticClusterBehavior:
    baseline_hook = _hook_diagnostic(baseline_report)
    candidate_hook = _hook_diagnostic(candidate_report)
    if candidate_hook.detects_hook and not baseline_hook.detects_hook:
        classification: Literal["better", "equivalent", "worse", "insufficient_truth"] = "worse"
        note = "candidate newly clusters the shepherd's-hook hard negative; baseline does not"
    elif baseline_hook.detects_hook and not candidate_hook.detects_hook:
        classification = "better"
        note = "candidate does not cluster the shepherd's-hook hard negative; baseline does"
    elif baseline_hook.detects_hook and candidate_hook.detects_hook:
        classification = "equivalent"
        note = "both models cluster the shepherd's-hook hard negative"
    else:
        classification = "equivalent"
        note = "neither model clusters the shepherd's-hook hard negative"
    if candidate_hook.other_daylight_scene_clusters > baseline_hook.other_daylight_scene_clusters:
        note += "; candidate also produces additional recurring static cluster(s) in the same scene not present for baseline"
    return StaticClusterBehavior(baseline_hook, candidate_hook, classification, note)


# --------------------------------------------------------------------------
# Temporal-policy comparison
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class TemporalMetricComparison:
    policy: str
    baseline_confirmed_true: int | None
    candidate_confirmed_true: int | None
    baseline_confirmed_false: int | None
    candidate_confirmed_false: int | None
    baseline_missed: int | None
    candidate_missed: int | None
    supported: bool


def _temporal_comparison(baseline_report: dict[str, object], candidate_report: dict[str, object]) -> tuple[TemporalMetricComparison, ...]:
    baseline_policies = {
        item["policy"]: item for item in baseline_report.get("temporal_policy_simulation", []) if isinstance(item, dict)
    }
    candidate_policies = {
        item["policy"]: item for item in candidate_report.get("temporal_policy_simulation", []) if isinstance(item, dict)
    }
    results = []
    for policy in sorted(set(baseline_policies) | set(candidate_policies)):
        baseline_item = baseline_policies.get(policy, {})
        candidate_item = candidate_policies.get(policy, {})
        supported = bool(baseline_item.get("supported")) and bool(candidate_item.get("supported"))
        results.append(TemporalMetricComparison(
            policy,
            baseline_item.get("confirmed_true_appearances"), candidate_item.get("confirmed_true_appearances"),
            baseline_item.get("confirmed_false_episodes"), candidate_item.get("confirmed_false_episodes"),
            baseline_item.get("missed_true_appearances"), candidate_item.get("missed_true_appearances"),
            supported,
        ))
    return tuple(results)


# --------------------------------------------------------------------------
# Runtime comparison. Never semantic -- not just the raw numbers (latency,
# GPU memory, model size), but also the acceptable/degraded/unacceptable
# classification derived from them. That classification is a deterministic
# function of its inputs, but the inputs themselves (wall-clock latency,
# reported GPU memory) are not bit-for-bit reproducible across two separate
# process runs of the identical model/cohort (scheduling jitter, GPU
# thermal/contention state), so a classification built from them cannot be
# allowed to influence `semantic_fingerprint` either -- a value that is
# merely usually stable is not the same guarantee as one that structurally
# cannot change. The full comparison, raw numbers and classification
# together, is reported only in the non-semantic `execution` section (see
# `_runtime_facts_dict`); `semantic_fingerprint` and `final_recommendation`
# never read from it.
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class RuntimeComparison:
    baseline_latency_ms_median: float | None
    candidate_latency_ms_median: float | None
    latency_ratio: float | None
    baseline_gpu_memory_mib: float | None
    candidate_gpu_memory_mib: float | None
    baseline_model_size_bytes: int | None
    candidate_model_size_bytes: int | None
    classification: Literal["acceptable", "degraded", "unacceptable", "insufficient_evidence"]


def _execution_dict(report: dict[str, object]) -> dict[str, object]:
    execution = report.get("execution")
    return execution if isinstance(execution, dict) else {}


def _execution_number(report: dict[str, object], *keys: str) -> float | None:
    """Walk a dotted path of dict keys inside `execution`; the last key's
    value must be a plain (non-bool) int/float or this returns None."""

    node: object = _execution_dict(report)
    for key in keys:
        if not isinstance(node, dict):
            return None
        node = node.get(key)
    return float(node) if isinstance(node, (int, float)) and not isinstance(node, bool) else None


def _runtime_comparison(baseline_report: dict[str, object], candidate_report: dict[str, object]) -> RuntimeComparison:
    baseline_latency = _execution_number(baseline_report, "primary_execution_facts", "latency_ms_median")
    candidate_latency = _execution_number(candidate_report, "primary_execution_facts", "latency_ms_median")
    baseline_gpu_memory_mib = _execution_number(baseline_report, "gpu_memory_after_mib")
    candidate_gpu_memory_mib = _execution_number(candidate_report, "gpu_memory_after_mib")
    baseline_model_size = _execution_number(baseline_report, "model_size_bytes")
    candidate_model_size = _execution_number(candidate_report, "model_size_bytes")
    baseline_model_size_bytes = int(baseline_model_size) if baseline_model_size is not None else None
    candidate_model_size_bytes = int(candidate_model_size) if candidate_model_size is not None else None
    ratio = (candidate_latency / baseline_latency) if baseline_latency and candidate_latency and baseline_latency > 0 else None

    if ratio is None:
        classification: Literal["acceptable", "degraded", "unacceptable", "insufficient_evidence"] = "insufficient_evidence"
    elif ratio <= RUNTIME_LATENCY_DEGRADED_RATIO and (
        candidate_gpu_memory_mib is None or candidate_gpu_memory_mib <= RUNTIME_GPU_MEMORY_DEGRADED_MIB
    ):
        classification = "acceptable"
    elif ratio <= RUNTIME_LATENCY_UNACCEPTABLE_RATIO and (
        candidate_gpu_memory_mib is None or candidate_gpu_memory_mib <= RUNTIME_GPU_MEMORY_UNACCEPTABLE_MIB
    ):
        classification = "degraded"
    else:
        classification = "unacceptable"

    return RuntimeComparison(
        baseline_latency, candidate_latency, ratio,
        baseline_gpu_memory_mib, candidate_gpu_memory_mib,
        baseline_model_size_bytes, candidate_model_size_bytes,
        classification,
    )


# --------------------------------------------------------------------------
# Licensing and integration complexity
# --------------------------------------------------------------------------

LicensingClassification = Literal["acceptable", "restricted", "unacceptable"]


def classify_license(license_text: str, redistribution_text: str) -> LicensingClassification:
    """Bounded, deterministic, explainable license gate.

    MIT/Apache/BSD-family -> acceptable. GPL (non-AGPL) -> restricted (usable
    for local shadow evaluation, not cleared for redistribution). AGPL, or an
    explicit "unacceptable" in the recorded redistribution text -> unacceptable.
    Never a substitute for real legal review before any redistribution
    decision; this only gates whether *this benchmark* may proceed.

    A real candidate's provenance note (`data/models/observation-onnx-cuda-
    candidates/mdv1000-spruce/model-bundle.json`) explicitly documents its
    license as "non-AGPL" -- a plain `"agpl" in text` substring search
    matches inside that negation and would misclassify it unacceptable, so
    an explicitly negated mention is stripped before the real check."""

    text = f"{license_text} {redistribution_text}".lower()
    without_negated_agpl = re.sub(r"non-?agpl|not\s+agpl", " ", text)
    if "agpl" in without_negated_agpl:
        return "unacceptable"
    if "unacceptable" in text:
        return "unacceptable"
    if "gpl" in text or "restricted" in text or "not audited" in text:
        return "restricted"
    if "mit" in text or "apache" in text or "bsd" in text:
        return "acceptable"
    return "restricted"


IntegrationComplexity = Literal["bounded", "material", "high"]


def classify_integration_complexity(baseline_summary: ModelSummary, candidate_summary: ModelSummary) -> IntegrationComplexity:
    """Reuse of the exact existing decoder plus an identical structured
    broad/animal-class convention is `bounded` integration work; the same
    class convention needing a new decoder is `material`; a genuinely
    different class convention is `high`.

    Deliberately compares the structured `broad_classes`/`animal_classes`
    lists, not the free-text `taxonomy` prose: two bundles can (and, for the
    real MDv5/spruce pair, do) describe the identical animal/person/vehicle
    convention in different words -- md-v5a's bundle says "MegaDetector v5
    broad classes" while spruce's says "MegaDetector broad classes
    (identical animal/person/vehicle convention to md-v5a; not COCO; no
    taxonomy remapping needed)". A prose-equality check would misclassify
    that pairing as `high` despite explicitly documented, genuine identity."""

    same_classes = (
        bool(candidate_summary.broad_classes)
        and candidate_summary.animal_classes == baseline_summary.animal_classes
        and candidate_summary.broad_classes == baseline_summary.broad_classes
    )
    if candidate_summary.decoder == baseline_summary.decoder and same_classes:
        return "bounded"
    if same_classes:
        return "material"
    return "high"


# --------------------------------------------------------------------------
# Final verdict
# --------------------------------------------------------------------------

FinalRecommendation = Literal[
    "retain_mdv5_baseline",
    "continue_candidate_shadow_evaluation",
    "candidate_ready_for_live_shadow_trial",
    "candidate_unsuitable",
    "insufficient_reviewed_data",
]


@dataclass(frozen=True)
class CandidateVerdict:
    candidate_label: str
    precision: Classification
    recall: Classification
    small_subject_recall: Classification
    static_scene_behavior: Literal["better", "equivalent", "worse", "insufficient_truth"]
    temporal_confirmation_behavior: Literal["better", "equivalent", "worse", "insufficient_truth"]
    # No `resource_usage` field: runtime/resource classification is reported
    # independently (see `_runtime_facts_dict`) but is never a semantic
    # verdict input -- see the `RuntimeComparison` section above.
    licensing: LicensingClassification
    integration_complexity: IntegrationComplexity
    evidence_sufficient: bool
    final_recommendation: FinalRecommendation
    rationale: tuple[str, ...]
    safe_for_shadow_experimentation: bool = True
    safe_for_production_authority: bool = False


def _temporal_behavior_classification(temporal: tuple[TemporalMetricComparison, ...]) -> Literal["better", "equivalent", "worse", "insufficient_truth"]:
    supported = [item for item in temporal if item.supported and item.policy != "single_detection"]
    if not supported:
        return "insufficient_truth"
    baseline_false = sum(item.baseline_confirmed_false or 0 for item in supported)
    candidate_false = sum(item.candidate_confirmed_false or 0 for item in supported)
    if candidate_false < baseline_false:
        return "better"
    if candidate_false > baseline_false:
        return "worse"
    return "equivalent"


def _small_subject_classification(subject_size: tuple[StratumComparison, ...]) -> Classification:
    far = next((item for item in subject_size if item.stratum_key == "far"), None)
    return far.classification if far is not None else "insufficient_truth"


def _final_recommendation(
    *,
    cohort_consistency: CohortConsistency,
    sufficiency_ok: bool,
    licensing: LicensingClassification,
    precision: Classification,
    recall: Classification,
    small_subject_recall: Classification,
    static_scene_behavior: str,
) -> tuple[FinalRecommendation, tuple[str, ...]]:
    """Deterministic verdict from semantic inputs only.

    Deliberately takes no `RuntimeComparison`: resource use is reported
    independently (`execution.runtime_facts_by_candidate`) precisely so it
    can never make this reproducible classification depend on wall-clock
    measurement. A reader combines both sections for a full readiness
    picture; this function alone answers only the accuracy/licensing
    question, holding the reviewed cohort fixed."""

    rationale: list[str] = []
    if not cohort_consistency.consistent:
        return "insufficient_reviewed_data", (cohort_consistency.reason or "cohort mismatch",)
    if not sufficiency_ok:
        rationale.append("reviewed cohort does not clear this benchmark's own sample-sufficiency bound")
        return "insufficient_reviewed_data", tuple(rationale)
    if licensing == "unacceptable":
        rationale.append(f"licensing classified unacceptable ({licensing})")
        return "candidate_unsuitable", tuple(rationale)

    worse_count = sum(1 for item in (precision, recall, small_subject_recall) if item == "worse")
    better_or_equal = all(item in ("better", "equivalent") for item in (precision, recall))

    if precision == "worse" and recall == "worse":
        rationale.append("both precision and recall worse than baseline at each model's own configured threshold")
        return "retain_mdv5_baseline", tuple(rationale)

    if (
        better_or_equal
        and small_subject_recall != "worse"
        and static_scene_behavior != "worse"
        and licensing in ("acceptable", "restricted")
    ):
        rationale.append(
            "precision and recall at least equivalent, small-subject recall not worse, no new "
            "static-scene regression, licensing acceptable for shadow evaluation -- check the "
            "separate non-semantic runtime/resource facts before a live shadow trial"
        )
        return "candidate_ready_for_live_shadow_trial", tuple(rationale)

    if worse_count >= 2:
        rationale.append("worse on at least two of precision/recall/small-subject recall")
        return "retain_mdv5_baseline", tuple(rationale)

    rationale.append("mixed or inconclusive evidence; more reviewed data or a follow-up comparison is warranted before a shadow-trial call")
    return "continue_candidate_shadow_evaluation", tuple(rationale)


def _candidate_verdict(
    label: str,
    *,
    cohort_consistency: CohortConsistency,
    baseline_summary: ModelSummary,
    candidate_summary: ModelSummary,
    accuracy: tuple[MetricComparison, ...],
    subject_size: tuple[StratumComparison, ...],
    static_cluster: StaticClusterBehavior,
    temporal: tuple[TemporalMetricComparison, ...],
    sufficiency_ok: bool,
) -> CandidateVerdict:
    by_metric = {item.metric: item.classification for item in accuracy}
    precision = by_metric.get("precision", "insufficient_truth")
    recall = by_metric.get("recall", "insufficient_truth")
    small_subject_recall = _small_subject_classification(subject_size)
    temporal_behavior = _temporal_behavior_classification(temporal)
    licensing = classify_license(candidate_summary.license, candidate_summary.redistribution)
    integration = classify_integration_complexity(baseline_summary, candidate_summary)

    recommendation, rationale = _final_recommendation(
        cohort_consistency=cohort_consistency, sufficiency_ok=sufficiency_ok, licensing=licensing,
        precision=precision, recall=recall, small_subject_recall=small_subject_recall,
        static_scene_behavior=static_cluster.classification,
    )
    return CandidateVerdict(
        candidate_label=label,
        precision=precision, recall=recall, small_subject_recall=small_subject_recall,
        static_scene_behavior=static_cluster.classification,
        temporal_confirmation_behavior=temporal_behavior,
        licensing=licensing,
        integration_complexity=integration,
        evidence_sufficient=cohort_consistency.consistent and sufficiency_ok,
        final_recommendation=recommendation,
        rationale=rationale,
    )


# --------------------------------------------------------------------------
# Report assembly
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class CandidateComparison:
    candidate_label: str
    cohort_consistency: CohortConsistency
    baseline_summary: ModelSummary
    candidate_summary: ModelSummary
    accuracy_metrics: tuple[MetricComparison, ...]
    scene_group_metrics: tuple[StratumComparison, ...]
    subject_size_metrics: tuple[StratumComparison, ...]
    unevaluated_strata: tuple[str, ...]
    static_cluster_behavior: StaticClusterBehavior
    temporal_comparison: tuple[TemporalMetricComparison, ...]
    runtime: RuntimeComparison
    verdict: CandidateVerdict


def compare_candidate(
    *,
    baseline_label: str,
    baseline_report: dict[str, object],
    candidate_label: str,
    candidate_report: dict[str, object],
) -> CandidateComparison:
    cohort_consistency = _check_cohort_consistency(baseline_report, candidate_report)
    baseline_summary = _model_summary(baseline_label, baseline_report)
    candidate_summary = _model_summary(candidate_label, candidate_report)

    if not cohort_consistency.consistent:
        empty_accuracy = tuple(MetricComparison(name, None, None, "unsupported_for_one_model") for name, _ in _ACCURACY_METRICS)
        static_cluster = StaticClusterBehavior(
            HookDiagnostic(False, None, None, 0, 0, None), HookDiagnostic(False, None, None, 0, 0, None),
            "insufficient_truth", "cohort mismatch: static-cluster comparison skipped",
        )
        runtime = RuntimeComparison(None, None, None, None, None, None, None, "insufficient_evidence")
        verdict = _candidate_verdict(
            candidate_label, cohort_consistency=cohort_consistency, baseline_summary=baseline_summary,
            candidate_summary=candidate_summary, accuracy=empty_accuracy, subject_size=(),
            static_cluster=static_cluster, temporal=(), sufficiency_ok=False,
        )
        return CandidateComparison(
            candidate_label, cohort_consistency, baseline_summary, candidate_summary,
            empty_accuracy, (), (), UNEVALUATED_STRATA, static_cluster, (), runtime, verdict,
        )

    # A model whose report never documented its broad-class taxonomy cannot
    # be trusted to compare numerically: reuse the same "row unavailable"
    # handling `_accuracy_metrics`/`_scene_group_metrics`/
    # `_subject_size_metrics` already use for a missing configured row, so
    # an undocumented taxonomy reports `unsupported_for_one_model` rather
    # than a fabricated number.
    taxonomy_documented = _taxonomy_documented(baseline_summary) and _taxonomy_documented(candidate_summary)
    baseline_row = _configured_row(baseline_report) if taxonomy_documented else None
    candidate_row = _configured_row(candidate_report) if taxonomy_documented else None
    accuracy = _accuracy_metrics(baseline_row, candidate_row)
    scene_metrics = _scene_group_metrics(baseline_row, candidate_row)
    size_metrics = _subject_size_metrics(baseline_row, candidate_row)
    static_cluster = _static_cluster_behavior(baseline_report, candidate_report)
    temporal = _temporal_comparison(baseline_report, candidate_report)
    runtime = _runtime_comparison(baseline_report, candidate_report)
    candidate_sufficiency = candidate_report.get("sample_sufficiency")
    sufficiency_ok = bool(isinstance(candidate_sufficiency, dict) and candidate_sufficiency.get("sufficient_for_threshold_selection"))

    verdict = _candidate_verdict(
        candidate_label, cohort_consistency=cohort_consistency, baseline_summary=baseline_summary,
        candidate_summary=candidate_summary, accuracy=accuracy, subject_size=size_metrics,
        static_cluster=static_cluster, temporal=temporal, sufficiency_ok=sufficiency_ok,
    )
    return CandidateComparison(
        candidate_label, cohort_consistency, baseline_summary, candidate_summary,
        accuracy, scene_metrics, size_metrics, UNEVALUATED_STRATA, static_cluster, temporal, runtime, verdict,
    )


def _semantic_comparison_dict(comparison: CandidateComparison) -> dict[str, object]:
    """`asdict(comparison)` with the entire `runtime` field removed.

    Not just the raw numbers (latency, GPU memory, model size) -- the
    derived acceptable/degraded/unacceptable classification too, since it is
    a function of numbers that are not bit-for-bit reproducible across two
    separate process runs. Both the raw numbers and the classification still
    reach the written report through `_runtime_facts_dict`, in the separate
    non-semantic `execution` section; only the fingerprinted payload excludes
    them."""

    payload = asdict(comparison)
    payload.pop("runtime", None)
    return payload


def _runtime_facts_dict(comparison: CandidateComparison) -> dict[str, object]:
    """The full runtime/resource comparison -- raw numbers and the derived
    classification together -- for the non-semantic `execution` section
    only. Never read by `_semantic_comparison_dict` or `semantic_fingerprint`."""

    runtime = comparison.runtime
    return {
        "baseline_latency_ms_median": runtime.baseline_latency_ms_median,
        "candidate_latency_ms_median": runtime.candidate_latency_ms_median,
        "latency_ratio": runtime.latency_ratio,
        "baseline_gpu_memory_mib": runtime.baseline_gpu_memory_mib,
        "candidate_gpu_memory_mib": runtime.candidate_gpu_memory_mib,
        "baseline_model_size_bytes": runtime.baseline_model_size_bytes,
        "candidate_model_size_bytes": runtime.candidate_model_size_bytes,
        "classification": runtime.classification,
    }


def build_comparison_semantic_report(
    *,
    baseline_label: str,
    baseline_report: dict[str, object],
    candidate_reports: dict[str, dict[str, object]],
) -> dict[str, object]:
    """Assemble the deterministic semantic comparison report plus its
    separate non-semantic `execution` section.

    `candidate_reports` is consumed in sorted-label order regardless of
    caller/dict ordering, so the output is stable no matter how the caller
    assembled its inputs. Runtime/resource facts (latency, GPU memory, model
    size) are read directly from each report's own non-semantic `execution`
    section; both those raw numbers and the acceptable/degraded/unacceptable
    classification derived from them are written only to this report's own
    `execution` section and never enter `semantic_fingerprint`."""

    comparisons = []
    for label in sorted(candidate_reports):
        comparison = compare_candidate(
            baseline_label=baseline_label, baseline_report=baseline_report,
            candidate_label=label, candidate_report=candidate_reports[label],
        )
        comparisons.append(comparison)

    semantic: dict[str, object] = {
        "schema_version": COMPARISON_SCHEMA_VERSION,
        "comparison_version": COMPARISON_VERSION,
        "baseline_label": baseline_label,
        "baseline_summary": asdict(_model_summary(baseline_label, baseline_report)),
        "candidate_labels": sorted(candidate_reports),
        "comparisons": [_semantic_comparison_dict(item) for item in comparisons],
        "creates_truth": False,
        "shadow_only": True,
        "production_proposal_authority": False,
        "no_automatic_default_model_change": True,
    }
    execution = {
        "runtime_facts_by_candidate": {item.candidate_label: _runtime_facts_dict(item) for item in comparisons},
    }
    return {**semantic, "semantic_fingerprint": semantic_fingerprint(semantic), "execution": execution}


__all__ = [
    "COMPARISON_SCHEMA_VERSION",
    "COMPARISON_VERSION",
    "HOOK_SCENE_GROUP",
    "HOOK_STRUCTURE_LABEL",
    "METRIC_EQUIVALENCE_TOLERANCE",
    "RUNTIME_GPU_MEMORY_DEGRADED_MIB",
    "RUNTIME_GPU_MEMORY_UNACCEPTABLE_MIB",
    "RUNTIME_LATENCY_DEGRADED_RATIO",
    "RUNTIME_LATENCY_UNACCEPTABLE_RATIO",
    "UNEVALUATED_STRATA",
    "CandidateComparison",
    "CandidateVerdict",
    "CohortConsistency",
    "DetectorComparisonError",
    "HookDiagnostic",
    "MetricComparison",
    "ModelSummary",
    "RuntimeComparison",
    "StaticClusterBehavior",
    "StratumComparison",
    "TemporalMetricComparison",
    "build_comparison_semantic_report",
    "classify_integration_complexity",
    "classify_license",
    "compare_candidate",
]
