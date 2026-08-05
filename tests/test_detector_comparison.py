"""Hardware-free tests for the Stage 6.3 detector-candidate comparison module.

All inputs here are synthetic `detector-benchmark-report.json`-shaped dicts
built by the `_report`/`_model`/`_threshold_row` helpers below; no ONNX
Runtime, CUDA, camera, or product database is touched. Numbered sections
mirror the task's required-test list.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

from mockingbird.observation.detector_comparison import (
    HOOK_SCENE_GROUP,
    HOOK_STRUCTURE_LABEL,
    METRIC_EQUIVALENCE_TOLERANCE,
    build_comparison_semantic_report,
    classify_integration_complexity,
    classify_license,
    compare_candidate,
)


def _model(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "key": "md-v5a", "version": "MDv5a.0.1-onnx-opset18", "fingerprint": "model-fp-baseline",
        "license": "MIT", "redistribution": "not audited",
        "taxonomy": "MegaDetector broad classes", "decoder": "megadetector_v5_yolov5_raw_v1",
        "broad_classes": ["animal", "person", "vehicle"], "animal_classes": ["animal"],
    }
    values.update(overrides)
    return values


def _threshold_row(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "threshold": 0.1, "is_configured_threshold": True,
        "precision": 0.5, "recall": 0.6, "positive_frame_recall": 0.7,
        "false_positives_per_negative_frame": 0.2, "false_positive_frame_count": 3,
        "duplicate_detections": 1,
        "scene_group_breakdown": [], "subject_size_breakdown": [],
    }
    values.update(overrides)
    return values


def _report(
    *,
    manifest_fingerprint: str = "cohort-fp-1",
    model: dict[str, object] | None = None,
    configured_threshold: float = 0.1,
    threshold_grid: tuple[float, ...] = (0.05, 0.1, 0.2),
    threshold_sweep: list[dict[str, object]] | None = None,
    clusters: list[dict[str, object]] | None = None,
    temporal: list[dict[str, object]] | None = None,
    sufficient: bool = True,
    latency_ms_median: float = 100.0,
    gpu_memory_after_mib: float = 500.0,
    model_size_bytes: int = 1_000_000,
    overall_classification: str = "DETECTOR_CALIBRATION_CHARACTERIZED",
) -> dict[str, object]:
    """A minimal but shape-complete stand-in for a real
    `detector-benchmark-report.json`, covering only the keys
    `detector_comparison.py` actually reads."""

    return {
        "cohort": {"manifest_fingerprint": manifest_fingerprint, "cohort_id": "fixture-cohort", "frame_count": 70},
        "provider": {"model": model if model is not None else _model()},
        "configured_threshold": configured_threshold,
        "threshold_grid": list(threshold_grid),
        "threshold_sweep": (
            threshold_sweep if threshold_sweep is not None
            else [_threshold_row(threshold=configured_threshold)]
        ),
        "static_false_positive_clusters": {"clusters": clusters if clusters is not None else []},
        "temporal_policy_simulation": temporal if temporal is not None else [],
        "sample_sufficiency": {"sufficient_for_threshold_selection": sufficient},
        "overall_classification": overall_classification,
        "execution": {
            "primary_execution_facts": {"latency_ms_median": latency_ms_median},
            "model_size_bytes": model_size_bytes,
            "gpu_memory_after_mib": gpu_memory_after_mib,
        },
    }


# --------------------------------------------------------------------------
# 1. Valid comparison of two benchmark reports
# --------------------------------------------------------------------------


def test_valid_comparison_of_two_benchmark_reports() -> None:
    baseline = _report()
    candidate = _report(model=_model(key="md-v1000-spruce", version="spruce-v1"))

    comparison = compare_candidate(
        baseline_label="mdv5", baseline_report=baseline,
        candidate_label="spruce", candidate_report=candidate,
    )

    assert comparison.cohort_consistency.consistent is True
    assert comparison.candidate_label == "spruce"
    assert comparison.baseline_summary.model_key == "md-v5a"
    assert comparison.candidate_summary.model_key == "md-v1000-spruce"
    assert comparison.verdict.evidence_sufficient is True


def test_valid_comparison_rejects_mismatched_cohort() -> None:
    baseline = _report(manifest_fingerprint="cohort-a")
    candidate = _report(manifest_fingerprint="cohort-b")

    comparison = compare_candidate(
        baseline_label="mdv5", baseline_report=baseline,
        candidate_label="spruce", candidate_report=candidate,
    )

    assert comparison.cohort_consistency.consistent is False
    assert comparison.verdict.final_recommendation == "insufficient_reviewed_data"
    assert comparison.verdict.evidence_sufficient is False


# --------------------------------------------------------------------------
# 2. Per-model threshold grids remain distinct
# --------------------------------------------------------------------------


def test_per_model_threshold_grids_remain_distinct() -> None:
    baseline = _report(configured_threshold=0.1, threshold_grid=(0.02, 0.1, 0.5))
    candidate = _report(configured_threshold=0.2, threshold_grid=(0.05, 0.2, 0.9))

    comparison = compare_candidate(
        baseline_label="mdv5", baseline_report=baseline,
        candidate_label="spruce", candidate_report=candidate,
    )

    assert comparison.baseline_summary.threshold_grid == (0.02, 0.1, 0.5)
    assert comparison.candidate_summary.threshold_grid == (0.05, 0.2, 0.9)
    assert comparison.baseline_summary.threshold_grid != comparison.candidate_summary.threshold_grid


# --------------------------------------------------------------------------
# 3. Raw score scales are not compared directly
# --------------------------------------------------------------------------


def test_raw_score_scales_are_not_compared_directly() -> None:
    # MDv5 operates at 0.1; the candidate's own calibrated operating point is
    # 0.6 -- a very different raw score scale. Both rows report the *same*
    # outcome-level precision (0.9): the comparison must read that outcome,
    # never assert or require the raw threshold values to be equal.
    baseline = _report(
        configured_threshold=0.1,
        threshold_sweep=[_threshold_row(threshold=0.1, precision=0.9, recall=0.6)],
    )
    candidate = _report(
        configured_threshold=0.6,
        threshold_sweep=[_threshold_row(threshold=0.6, precision=0.9, recall=0.6)],
    )

    comparison = compare_candidate(
        baseline_label="mdv5", baseline_report=baseline,
        candidate_label="spruce", candidate_report=candidate,
    )

    # Each model keeps its own raw configured threshold, unmodified and
    # unequalized.
    assert comparison.baseline_summary.configured_threshold == 0.1
    assert comparison.candidate_summary.configured_threshold == 0.6
    # The outcome-level comparison reads each side's own configured-row
    # precision/recall and finds them equivalent, entirely independent of
    # how different the two raw threshold scales are.
    by_metric = {item.metric: item.classification for item in comparison.accuracy_metrics}
    assert by_metric["precision"] == "equivalent"
    assert by_metric["recall"] == "equivalent"


# --------------------------------------------------------------------------
# 4. Precision comparison
# --------------------------------------------------------------------------


def test_precision_comparison_better_worse_equivalent() -> None:
    baseline = _report(threshold_sweep=[_threshold_row(precision=0.50)])

    better = compare_candidate(
        baseline_label="mdv5", baseline_report=baseline, candidate_label="c",
        candidate_report=_report(threshold_sweep=[_threshold_row(precision=0.80)]),
    )
    worse = compare_candidate(
        baseline_label="mdv5", baseline_report=baseline, candidate_label="c",
        candidate_report=_report(threshold_sweep=[_threshold_row(precision=0.20)]),
    )
    equivalent = compare_candidate(
        baseline_label="mdv5", baseline_report=baseline, candidate_label="c",
        candidate_report=_report(threshold_sweep=[_threshold_row(precision=0.50 + METRIC_EQUIVALENCE_TOLERANCE / 2)]),
    )

    def precision_of(comparison: object) -> str:
        return next(item.classification for item in comparison.accuracy_metrics if item.metric == "precision")  # type: ignore[attr-defined]

    assert precision_of(better) == "better"
    assert precision_of(worse) == "worse"
    assert precision_of(equivalent) == "equivalent"


# --------------------------------------------------------------------------
# 5. Recall comparison
# --------------------------------------------------------------------------


def test_recall_comparison_better_worse_equivalent() -> None:
    baseline = _report(threshold_sweep=[_threshold_row(recall=0.50)])

    better = compare_candidate(
        baseline_label="mdv5", baseline_report=baseline, candidate_label="c",
        candidate_report=_report(threshold_sweep=[_threshold_row(recall=0.90)]),
    )
    worse = compare_candidate(
        baseline_label="mdv5", baseline_report=baseline, candidate_label="c",
        candidate_report=_report(threshold_sweep=[_threshold_row(recall=0.10)]),
    )
    equivalent = compare_candidate(
        baseline_label="mdv5", baseline_report=baseline, candidate_label="c",
        candidate_report=_report(threshold_sweep=[_threshold_row(recall=0.50)]),
    )

    def recall_of(comparison: object) -> str:
        return next(item.classification for item in comparison.accuracy_metrics if item.metric == "recall")  # type: ignore[attr-defined]

    assert recall_of(better) == "better"
    assert recall_of(worse) == "worse"
    assert recall_of(equivalent) == "equivalent"


# --------------------------------------------------------------------------
# 6. Small-subject recall comparison
# --------------------------------------------------------------------------


def test_small_subject_recall_comparison() -> None:
    def with_far_recall(value: float) -> dict[str, object]:
        return _report(threshold_sweep=[_threshold_row(
            subject_size_breakdown=[{"distance_bucket": "far", "scorable_positive_frames": 5, "recall": value}],
        )])

    baseline = with_far_recall(0.2)
    better = compare_candidate(
        baseline_label="mdv5", baseline_report=baseline, candidate_label="c",
        candidate_report=with_far_recall(0.9),
    )
    worse = compare_candidate(
        baseline_label="mdv5", baseline_report=baseline, candidate_label="c",
        candidate_report=with_far_recall(0.0),
    )

    assert better.verdict.small_subject_recall == "better"
    assert worse.verdict.small_subject_recall == "worse"


# --------------------------------------------------------------------------
# 7. Missing subject-size truth reports insufficient truth
# --------------------------------------------------------------------------


def test_missing_subject_size_truth_reports_insufficient_truth() -> None:
    baseline = _report(threshold_sweep=[_threshold_row(subject_size_breakdown=[])])
    candidate = _report(threshold_sweep=[_threshold_row(subject_size_breakdown=[])])

    comparison = compare_candidate(
        baseline_label="mdv5", baseline_report=baseline,
        candidate_label="spruce", candidate_report=candidate,
    )

    assert comparison.subject_size_metrics == ()
    assert comparison.verdict.small_subject_recall == "insufficient_truth"


# --------------------------------------------------------------------------
# 8. Static-cluster comparison (shepherd's-hook hard negative)
# --------------------------------------------------------------------------


def _hook_cluster(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "scene_group": HOOK_SCENE_GROUP, "matched_static_structure": HOOK_STRUCTURE_LABEL,
        "score_minimum": 0.05, "score_maximum": 0.3, "frame_ids": ["a", "b"],
    }
    values.update(overrides)
    return values


def test_static_cluster_comparison_shepherds_hook() -> None:
    baseline_clusters_it = _report(clusters=[_hook_cluster()])
    neither_clusters_it = _report(clusters=[])

    candidate_fixes_it = compare_candidate(
        baseline_label="mdv5", baseline_report=baseline_clusters_it,
        candidate_label="spruce", candidate_report=neither_clusters_it,
    )
    candidate_regresses = compare_candidate(
        baseline_label="mdv5", baseline_report=neither_clusters_it,
        candidate_label="spruce", candidate_report=baseline_clusters_it,
    )
    neither = compare_candidate(
        baseline_label="mdv5", baseline_report=neither_clusters_it,
        candidate_label="spruce", candidate_report=neither_clusters_it,
    )

    assert candidate_fixes_it.static_cluster_behavior.classification == "better"
    assert candidate_regresses.static_cluster_behavior.classification == "worse"
    assert neither.static_cluster_behavior.classification == "equivalent"
    assert candidate_regresses.static_cluster_behavior.candidate.detects_hook is True


# --------------------------------------------------------------------------
# 9. Temporal-policy comparison
# --------------------------------------------------------------------------


def _temporal_row(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "policy": "two_detections", "supported": True,
        "confirmed_true_appearances": 5, "confirmed_false_episodes": 2, "missed_true_appearances": 1,
    }
    values.update(overrides)
    return values


def test_temporal_policy_comparison() -> None:
    baseline = _report(temporal=[_temporal_row(confirmed_false_episodes=2)])

    better = compare_candidate(
        baseline_label="mdv5", baseline_report=baseline, candidate_label="c",
        candidate_report=_report(temporal=[_temporal_row(confirmed_false_episodes=0)]),
    )
    worse = compare_candidate(
        baseline_label="mdv5", baseline_report=baseline, candidate_label="c",
        candidate_report=_report(temporal=[_temporal_row(confirmed_false_episodes=5)]),
    )
    equivalent = compare_candidate(
        baseline_label="mdv5", baseline_report=baseline, candidate_label="c",
        candidate_report=_report(temporal=[_temporal_row(confirmed_false_episodes=2)]),
    )
    # single_detection is explicitly excluded from the aggregate; an
    # improvement there alone must not flip the verdict.
    single_detection_only = compare_candidate(
        baseline_label="mdv5",
        baseline_report=_report(temporal=[_temporal_row(policy="single_detection", confirmed_false_episodes=9)]),
        candidate_label="c",
        candidate_report=_report(temporal=[_temporal_row(policy="single_detection", confirmed_false_episodes=0)]),
    )

    assert better.verdict.temporal_confirmation_behavior == "better"
    assert worse.verdict.temporal_confirmation_behavior == "worse"
    assert equivalent.verdict.temporal_confirmation_behavior == "equivalent"
    assert single_detection_only.verdict.temporal_confirmation_behavior == "insufficient_truth"


# --------------------------------------------------------------------------
# 10. Licensing restrictions affect readiness
# --------------------------------------------------------------------------


def _favorable_candidate_report(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {"threshold_sweep": [_threshold_row(precision=0.9, recall=0.9)]}
    values.update(overrides)
    return _report(**values)  # type: ignore[arg-type]


def test_unacceptable_licensing_forces_candidate_unsuitable_despite_good_metrics() -> None:
    baseline = _report(threshold_sweep=[_threshold_row(precision=0.5, recall=0.5)])
    candidate = _favorable_candidate_report(model=_model(license="AGPL-3.0", redistribution="not audited"))

    comparison = compare_candidate(
        baseline_label="mdv5", baseline_report=baseline,
        candidate_label="spruce", candidate_report=candidate,
    )

    assert comparison.verdict.licensing == "unacceptable"
    assert comparison.verdict.final_recommendation == "candidate_unsuitable"


def test_restricted_licensing_is_distinct_but_does_not_by_itself_block_shadow_trial() -> None:
    baseline = _report(threshold_sweep=[_threshold_row(precision=0.5, recall=0.5)])
    candidate = _favorable_candidate_report(model=_model(
        license="GPL-3.0", redistribution="local shadow evaluation only, not cleared for redistribution",
    ))

    comparison = compare_candidate(
        baseline_label="mdv5", baseline_report=baseline,
        candidate_label="spruce", candidate_report=candidate,
    )

    assert comparison.verdict.licensing == "restricted"
    assert comparison.verdict.final_recommendation == "candidate_ready_for_live_shadow_trial"


def test_classify_license_boundaries() -> None:
    assert classify_license("MIT", "unaudited") == "acceptable"
    assert classify_license("Apache-2.0", "") == "acceptable"
    assert classify_license("GPL-3.0", "local only") == "restricted"
    assert classify_license("AGPL-3.0", "") == "unacceptable"
    assert classify_license("proprietary", "unacceptable for MockingBird") == "unacceptable"


def test_classify_license_does_not_misread_explicit_non_agpl_note() -> None:
    # Regression: the real spruce candidate's provenance text explicitly
    # says "non-AGPL" GPL -- a naive `"agpl" in text` substring search
    # matches inside that negation and would wrongly classify it
    # unacceptable.
    license_text = (
        "GPL-3.0 (weights, per official MegaDetector release notes' non-AGPL "
        "'ILMS' column for md_v1000.0.0-spruce.pt); inference-code dependency "
        "ultralytics-yolov5 is also GPL-3.0; the megadetector Python wrapper "
        "package itself is MIT"
    )
    redistribution_text = (
        "Local ignored activation artifact only; GPL-3.0 weights and GPL-3.0 "
        "inference-code dependency restrict redistribution of a combined/"
        "derivative work; not cleared for redistribution or bundling; local "
        "shadow evaluation only"
    )

    assert classify_license(license_text, redistribution_text) == "restricted"
    # A genuine (non-negated) AGPL mention elsewhere in the same text must
    # still be caught.
    assert classify_license("AGPL-3.0, previously non-AGPL in an earlier release", "") == "unacceptable"


# --------------------------------------------------------------------------
# 11. Missing taxonomy mapping reports unsupported
# --------------------------------------------------------------------------


def test_missing_taxonomy_mapping_reports_unsupported() -> None:
    baseline = _report()
    candidate = _report(model=_model(taxonomy=""))

    comparison = compare_candidate(
        baseline_label="mdv5", baseline_report=baseline,
        candidate_label="spruce", candidate_report=candidate,
    )

    by_metric = {item.metric: item.classification for item in comparison.accuracy_metrics}
    assert by_metric["precision"] == "unsupported_for_one_model"
    assert by_metric["recall"] == "unsupported_for_one_model"
    assert comparison.scene_group_metrics == ()
    assert comparison.subject_size_metrics == ()


def test_default_unknown_taxonomy_also_reports_unsupported() -> None:
    # `_model_summary` itself falls back to "unknown" when a report never
    # populated `taxonomy` at all.
    model_without_taxonomy = _model()
    del model_without_taxonomy["taxonomy"]
    comparison = compare_candidate(
        baseline_label="mdv5", baseline_report=_report(),
        candidate_label="spruce", candidate_report=_report(model=model_without_taxonomy),
    )

    assert comparison.candidate_summary.taxonomy == "unknown"
    by_metric = {item.metric: item.classification for item in comparison.accuracy_metrics}
    assert by_metric["precision"] == "unsupported_for_one_model"


# --------------------------------------------------------------------------
# 12. Better precision with worse recall is reported honestly
# --------------------------------------------------------------------------


def test_better_precision_with_worse_recall_is_reported_honestly() -> None:
    baseline = _report(threshold_sweep=[_threshold_row(precision=0.5, recall=0.6)])
    candidate = _report(threshold_sweep=[_threshold_row(precision=0.8, recall=0.3)])

    comparison = compare_candidate(
        baseline_label="mdv5", baseline_report=baseline,
        candidate_label="spruce", candidate_report=candidate,
    )

    assert comparison.verdict.precision == "better"
    assert comparison.verdict.recall == "worse"
    # Mixed evidence must never be silently promoted to a shadow-trial
    # recommendation just because one axis improved.
    assert comparison.verdict.final_recommendation != "candidate_ready_for_live_shadow_trial"


# --------------------------------------------------------------------------
# 13. Better recall with unacceptable false positives is not promoted
# --------------------------------------------------------------------------


def test_better_recall_with_worse_false_positives_is_not_promoted() -> None:
    baseline = _report(threshold_sweep=[_threshold_row(
        precision=0.6, recall=0.5, false_positives_per_negative_frame=0.1,
    )])
    candidate = _report(threshold_sweep=[_threshold_row(
        precision=0.2, recall=0.9, false_positives_per_negative_frame=0.9,
    )])

    comparison = compare_candidate(
        baseline_label="mdv5", baseline_report=baseline,
        candidate_label="spruce", candidate_report=candidate,
    )

    by_metric = {item.metric: item.classification for item in comparison.accuracy_metrics}
    assert comparison.verdict.recall == "better"
    assert by_metric["false_positives_per_negative_frame"] == "worse"
    assert comparison.verdict.precision == "worse"
    assert comparison.verdict.final_recommendation != "candidate_ready_for_live_shadow_trial"


# --------------------------------------------------------------------------
# 14. Runtime/resource differences do not change semantic fingerprints
# --------------------------------------------------------------------------


def test_runtime_and_resource_differences_do_not_change_semantic_fingerprint() -> None:
    baseline = _report()

    def candidate_with(**runtime: object) -> dict[str, object]:
        return _report(model=_model(key="candidate"), **runtime)  # type: ignore[arg-type]

    mild = build_comparison_semantic_report(
        baseline_label="mdv5", baseline_report=baseline,
        candidate_reports={"c": candidate_with(latency_ms_median=100.0, gpu_memory_after_mib=500.0, model_size_bytes=1_000_000)},
    )
    # Deliberately crosses every RUNTIME_* classification boundary (latency
    # ratio well past 10x, GPU memory well past the unacceptable bound) --
    # the adversarial case, not just ordinary measurement jitter.
    extreme = build_comparison_semantic_report(
        baseline_label="mdv5", baseline_report=baseline,
        candidate_reports={"c": candidate_with(latency_ms_median=50_000.0, gpu_memory_after_mib=50_000.0, model_size_bytes=999_999_999)},
    )

    assert mild["semantic_fingerprint"] == extreme["semantic_fingerprint"]
    # The runtime facts genuinely differ (proving this test is not vacuous)
    # and the derived classification really does flip...
    mild_facts = mild["execution"]["runtime_facts_by_candidate"]["c"]
    extreme_facts = extreme["execution"]["runtime_facts_by_candidate"]["c"]
    assert mild_facts["classification"] == "acceptable"
    assert extreme_facts["classification"] == "unacceptable"
    assert mild_facts != extreme_facts
    # ...yet neither the raw numbers nor the classification appear anywhere
    # in the semantic (fingerprinted) portion of the report.
    semantic_only = json.dumps({k: v for k, v in mild.items() if k != "execution"})
    assert "50000" not in semantic_only
    assert "999999999" not in semantic_only
    assert "unacceptable" not in semantic_only
    # No `runtime` key anywhere in a comparison entry or its verdict (a
    # plain prose mention of the word "runtime" inside a rationale string is
    # fine; a structured field carrying the classification is not).
    assert "runtime" not in mild["comparisons"][0]
    assert "runtime" not in mild["comparisons"][0]["verdict"]


def test_final_recommendation_is_identical_despite_runtime_divergence() -> None:
    baseline = _report(threshold_sweep=[_threshold_row(precision=0.9, recall=0.9)])
    fast = compare_candidate(
        baseline_label="mdv5", baseline_report=baseline, candidate_label="c",
        candidate_report=_report(threshold_sweep=[_threshold_row(precision=0.9, recall=0.9)], latency_ms_median=10.0),
    )
    slow = compare_candidate(
        baseline_label="mdv5", baseline_report=baseline, candidate_label="c",
        candidate_report=_report(threshold_sweep=[_threshold_row(precision=0.9, recall=0.9)], latency_ms_median=100_000.0),
    )

    assert fast.verdict.final_recommendation == slow.verdict.final_recommendation


# --------------------------------------------------------------------------
# 15. Absolute paths remain non-semantic
# --------------------------------------------------------------------------


def test_absolute_paths_remain_non_semantic() -> None:
    baseline = _report()
    candidate = _report(model=_model(key="candidate"))
    poisoned_path = "/home/zkelder/projects/mockingbird-active/data/models/observation-onnx-cuda-candidates/mdv1000-spruce/model-bundle.json"
    # A red-herring absolute path placed somewhere the comparison module
    # does not read (mirroring how a real detector-benchmark-report.json
    # never contains one either -- this proves the comparison would not
    # propagate one even if a future report accidentally carried it).
    candidate["execution"]["model_bundle_path"] = poisoned_path
    baseline["some_future_unread_field"] = poisoned_path

    report = build_comparison_semantic_report(
        baseline_label="mdv5", baseline_report=baseline, candidate_reports={"c": candidate},
    )

    semantic_only = json.dumps({k: v for k, v in report.items() if k != "execution"})
    assert poisoned_path not in semantic_only
    assert "/home/" not in semantic_only


# --------------------------------------------------------------------------
# 16. Stable deterministic ordering
# --------------------------------------------------------------------------


def test_stable_deterministic_ordering_independent_of_input_order() -> None:
    baseline = _report()
    candidates = {
        "zeta": _report(model=_model(key="zeta")),
        "alpha": _report(model=_model(key="alpha")),
        "mike": _report(model=_model(key="mike")),
    }

    report = build_comparison_semantic_report(
        baseline_label="mdv5", baseline_report=baseline, candidate_reports=candidates,
    )

    assert report["candidate_labels"] == ["alpha", "mike", "zeta"]
    assert [item["candidate_label"] for item in report["comparisons"]] == ["alpha", "mike", "zeta"]


def test_ordering_is_independent_of_dict_construction_order() -> None:
    baseline = _report()
    forward = {"alpha": _report(), "zeta": _report()}
    backward = {"zeta": _report(), "alpha": _report()}

    forward_report = build_comparison_semantic_report(baseline_label="mdv5", baseline_report=baseline, candidate_reports=forward)
    backward_report = build_comparison_semantic_report(baseline_label="mdv5", baseline_report=baseline, candidate_reports=backward)

    assert forward_report["semantic_fingerprint"] == backward_report["semantic_fingerprint"]


# --------------------------------------------------------------------------
# 17. Repeated semantic fingerprints match
# --------------------------------------------------------------------------


def test_repeated_semantic_fingerprints_match() -> None:
    baseline = _report()
    candidates = {"spruce": _report(model=_model(key="candidate"))}

    first = build_comparison_semantic_report(baseline_label="mdv5", baseline_report=copy.deepcopy(baseline), candidate_reports=copy.deepcopy(candidates))
    second = build_comparison_semantic_report(baseline_label="mdv5", baseline_report=copy.deepcopy(baseline), candidate_reports=copy.deepcopy(candidates))

    assert first["semantic_fingerprint"] == second["semantic_fingerprint"]
    assert {k: v for k, v in first.items() if k != "execution"} == {k: v for k, v in second.items() if k != "execution"}


# --------------------------------------------------------------------------
# 18. No runtime/model configuration mutation
# --------------------------------------------------------------------------


def test_comparison_does_not_mutate_input_reports() -> None:
    baseline = _report()
    candidate = _report(model=_model(key="candidate"))
    baseline_before = copy.deepcopy(baseline)
    candidate_before = copy.deepcopy(candidate)

    build_comparison_semantic_report(baseline_label="mdv5", baseline_report=baseline, candidate_reports={"c": candidate})

    assert baseline == baseline_before
    assert candidate == candidate_before


def test_candidate_reports_mapping_itself_is_not_mutated() -> None:
    candidates = {"zeta": _report(), "alpha": _report()}
    original_keys = list(candidates.keys())

    build_comparison_semantic_report(baseline_label="mdv5", baseline_report=_report(), candidate_reports=candidates)

    assert list(candidates.keys()) == original_keys


# --------------------------------------------------------------------------
# 19. No product repository dependency / 20. No truth-write path
# --------------------------------------------------------------------------


def test_module_source_has_no_product_repository_or_truth_imports() -> None:
    for name in ("detector_comparison.py", "detector_comparison_io.py", "detector_comparison_cli.py"):
        source = Path(f"src/mockingbird/observation/{name}").read_text(encoding="utf-8")
        forbidden = (
            "mockingbird.db", "mockingbird.repositories", "sqlite3", "ReviewLabel",
            "MotionEvidence", "monitoring_policy", "Event(", "Visit(", "import requests",
            "urllib", "socket",
        )
        for token in forbidden:
            assert token not in source, f"{name} unexpectedly references {token}"


def test_report_always_declares_shadow_only_and_no_truth() -> None:
    report = build_comparison_semantic_report(
        baseline_label="mdv5", baseline_report=_report(), candidate_reports={"c": _report()},
    )

    assert report["creates_truth"] is False
    assert report["shadow_only"] is True
    assert report["production_proposal_authority"] is False
    assert report["no_automatic_default_model_change"] is True


def test_verdict_never_claims_production_authority() -> None:
    comparison = compare_candidate(
        baseline_label="mdv5", baseline_report=_report(),
        candidate_label="spruce", candidate_report=_report(model=_model(key="candidate")),
    )

    assert comparison.verdict.safe_for_production_authority is False
    assert comparison.verdict.safe_for_shadow_experimentation is True


# --------------------------------------------------------------------------
# Integration-complexity classification (supporting coverage)
# --------------------------------------------------------------------------


def test_integration_complexity_classification() -> None:
    baseline = compare_candidate(
        baseline_label="mdv5", baseline_report=_report(), candidate_label="c",
        candidate_report=_report(model=_model(key="candidate")),
    ).candidate_summary
    bounded = compare_candidate(
        baseline_label="mdv5", baseline_report=_report(), candidate_label="c",
        candidate_report=_report(model=_model(key="candidate")),
    )
    material = compare_candidate(
        baseline_label="mdv5", baseline_report=_report(), candidate_label="c",
        candidate_report=_report(model=_model(key="candidate", decoder="a-different-decoder")),
    )
    high = compare_candidate(
        baseline_label="mdv5", baseline_report=_report(), candidate_label="c",
        candidate_report=_report(model=_model(
            key="candidate", decoder="a-different-decoder",
            broad_classes=["animal", "vehicle"], animal_classes=["animal"],
        )),
    )

    assert bounded.verdict.integration_complexity == "bounded"
    assert material.verdict.integration_complexity == "material"
    assert high.verdict.integration_complexity == "high"
    assert classify_integration_complexity(baseline, baseline) == "bounded"


def test_integration_complexity_uses_structured_classes_not_taxonomy_prose() -> None:
    # Regression: the real spruce candidate documents the identical
    # animal/person/vehicle convention as md-v5a in different prose
    # ("MegaDetector v5 broad classes" vs "MegaDetector broad classes
    # (identical animal/person/vehicle convention to md-v5a; ...)"). A
    # taxonomy-prose-equality check would misclassify this pairing `high`;
    # the structured class lists are what actually decide it.
    baseline = _report(model=_model(taxonomy="MegaDetector v5 broad classes"))
    candidate = _report(model=_model(
        key="md-v1000-spruce",
        taxonomy="MegaDetector broad classes (identical animal/person/vehicle convention to md-v5a; not COCO; no taxonomy remapping needed)",
    ))

    comparison = compare_candidate(
        baseline_label="mdv5", baseline_report=baseline,
        candidate_label="spruce", candidate_report=candidate,
    )

    assert comparison.baseline_summary.taxonomy != comparison.candidate_summary.taxonomy
    assert comparison.baseline_summary.broad_classes == comparison.candidate_summary.broad_classes
    assert comparison.verdict.integration_complexity == "bounded"


def test_integration_complexity_high_when_broad_classes_missing() -> None:
    model_without_classes = _model(key="candidate")
    del model_without_classes["broad_classes"]
    del model_without_classes["animal_classes"]

    comparison = compare_candidate(
        baseline_label="mdv5", baseline_report=_report(),
        candidate_label="c", candidate_report=_report(model=model_without_classes),
    )

    assert comparison.candidate_summary.broad_classes == ()
    assert comparison.verdict.integration_complexity == "high"
