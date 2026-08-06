"""Deterministic, shadow-only adaptive motion-proposal detector benchmark and
three-way (full_frame vs uniform_tiles vs motion_proposals) strategy decision.

Observation Engine v2 Stage 6.5. This module is pure: no model inference, no
filesystem I/O, no product repository import. It consumes already-decoded,
already-cross-window-suppressed detections exactly the way
`multi_scale_benchmark.py` does (a motion proposal becomes a
`multi_scale_strategy.StrategyWindow` once it has a source-normalized box, so
`merge_frame_windows`/`compute_scale_specific_facts`/`visibility_breakdown`
are reused completely unchanged) and reuses the Stage 6.2 `detector_benchmark`
pipeline (`sweep_thresholds`, `cluster_static_false_positives`,
`simulate_temporal_policies`, `classify_sample_sufficiency`) unchanged as
well. The only genuinely new report content is `proposal_behavior` (how many
frames were even eligible for a temporal proposal, how many proposals fired
or were rejected and why) and the three-way decision layer below, which
reuses `multi_scale_benchmark.compare_strategy_reports` for its two pairwise
comparisons rather than reimplementing metric comparison. See
docs/adaptive-motion-proposal-benchmark-contract.md.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
from typing import Literal

from mockingbird.observation.detector_benchmark import (
    CalibrationManifest,
    classify_sample_sufficiency,
    cluster_static_false_positives,
    overall_classification,
    simulate_temporal_policies,
    sweep_thresholds,
)
from mockingbird.observation.motion_proposal_strategy import (
    MotionProposalStrategyConfig,
    ProposalGenerationResult,
)
from mockingbird.observation.multi_scale_benchmark import (
    compare_strategy_reports,
    compute_scale_specific_facts,
    merge_frame_windows,
    visibility_breakdown,
)
from mockingbird.observation.multi_scale_strategy import WindowedDetection
from mockingbird.observation.replay import semantic_fingerprint

MOTION_PROPOSAL_REPORT_SCHEMA_VERSION = 1
MOTION_PROPOSAL_BENCHMARK_VERSION = "motion-proposal-detector-benchmark-v1"
DECISION_SCHEMA_VERSION = 1
DECISION_VERSION = "motion-proposal-three-way-decision-v1"

# A temporal-behavior sufficiency bar independent of the reused
# `classify_sample_sufficiency` (which only knows about static-cohort frame
# counts, not whether the strategy's own proposal mechanism ever actually
# fired). Deliberately small and general -- not tuned to any one cohort's
# size -- because a strategy that essentially never sees an eligible
# predecessor cannot honestly be judged "ready" no matter how the handful of
# frames it did see turned out.
MIN_FRAMES_ELIGIBLE_FOR_TEMPORAL_SUFFICIENCY = 10
MIN_FRAMES_WITH_PROPOSALS_FOR_TEMPORAL_SUFFICIENCY = 5


class MotionProposalBenchmarkError(ValueError):
    """A bounded motion-proposal benchmark validation or execution failure code."""


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    mid = len(ordered) // 2
    return ordered[mid] if len(ordered) % 2 else (ordered[mid - 1] + ordered[mid]) / 2.0


# --------------------------------------------------------------------------
# Proposal-behavior accounting (the genuinely new content at this stage)
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class ProposalRecord:
    """One retained proposal's full provenance, for report-level auditing
    and for the "proposal IDs are deterministic" / "retain proposal
    provenance" requirements. Never used as a truth source itself."""

    frame_id: str
    predecessor_frame_id: str
    proposal_id: str
    rank: int
    source_box: tuple[float, float, float, float]
    changed_pixel_count: int
    source_area_fraction: float


@dataclass(frozen=True)
class ProposalBehaviorMetrics:
    frames_eligible_for_temporal_proposals: int
    frames_with_proposals: int
    total_proposal_count: int
    total_proposals_rejected: int
    rejection_reason_distribution: tuple[tuple[str, int], ...]
    proposed_source_area_fraction_mean: float | None
    proposed_source_area_fraction_median: float | None


def compute_proposal_behavior(
    proposal_results: dict[str, ProposalGenerationResult],
) -> tuple[ProposalBehaviorMetrics, tuple[ProposalRecord, ...]]:
    """Diagnostic evidence only: never alters a detection, a window, or a
    threshold. Every count here comes strictly from the already-decided
    `ProposalGenerationResult` per frame the caller already produced."""

    reasons: Counter[str] = Counter()
    total_rejected = 0
    eligible = 0
    with_proposals = 0
    areas: list[float] = []
    records: list[ProposalRecord] = []

    for frame_id in sorted(proposal_results):
        result = proposal_results[frame_id]
        if result.pair_eligible:
            eligible += 1
        elif result.pair_reason_code is not None:
            reasons[result.pair_reason_code] += 1
        if result.proposals:
            with_proposals += 1
        for rejected in result.rejected_regions:
            reasons[rejected.reason_code] += 1
            total_rejected += 1
        for rejected in result.rejected_proposals:
            reasons[rejected.reason_code] += 1
            total_rejected += 1
        for proposal in result.proposals:
            left, top, right, bottom = proposal.window.source_box
            area = (right - left) * (bottom - top)
            areas.append(area)
            records.append(ProposalRecord(
                frame_id=frame_id, predecessor_frame_id=proposal.predecessor_frame_id,
                proposal_id=proposal.proposal_id, rank=proposal.rank,
                source_box=proposal.window.source_box,
                changed_pixel_count=proposal.source_region.changed_pixel_count,
                source_area_fraction=round(area, 6),
            ))

    metrics = ProposalBehaviorMetrics(
        frames_eligible_for_temporal_proposals=eligible,
        frames_with_proposals=with_proposals,
        total_proposal_count=sum(len(result.proposals) for result in proposal_results.values()),
        total_proposals_rejected=total_rejected,
        rejection_reason_distribution=tuple(sorted(reasons.items())),
        proposed_source_area_fraction_mean=(sum(areas) / len(areas)) if areas else None,
        proposed_source_area_fraction_median=_median(areas),
    )
    return metrics, tuple(sorted(records, key=lambda item: (item.frame_id, item.rank)))


# --------------------------------------------------------------------------
# Report assembly (reuses the Stage 6.2/6.4 pipeline unchanged)
# --------------------------------------------------------------------------


def merge_frame_proposal_windows(
    frame_id: str,
    proposal_result: ProposalGenerationResult,
    full_frame_window: object,
    local_detections_by_window: dict[str, tuple[object, ...]],
    *,
    cross_window_iou_threshold: float,
    max_final_detections: int,
) -> tuple[tuple[WindowedDetection, ...], tuple[WindowedDetection, ...]]:
    """Thin adapter from one frame's `ProposalGenerationResult` to
    `multi_scale_benchmark.merge_frame_windows`: a motion proposal's
    `StrategyWindow` is structurally identical to a uniform-grid tile, so
    the actual merge/cross-window-suppression logic is reused verbatim."""

    windows = (full_frame_window, *(proposal.window for proposal in proposal_result.proposals))
    return merge_frame_windows(
        windows, local_detections_by_window,
        cross_window_iou_threshold=cross_window_iou_threshold, max_final_detections=max_final_detections,
    )


def build_motion_proposal_semantic_report(
    *,
    manifest: CalibrationManifest,
    strategy: MotionProposalStrategyConfig,
    kept_by_frame: dict[str, tuple[WindowedDetection, ...]],
    suppressed_by_frame: dict[str, tuple[WindowedDetection, ...]],
    proposal_results: dict[str, ProposalGenerationResult],
    provider: dict[str, object],
) -> dict[str, object]:
    """Assemble the deterministic semantic report and its fingerprint.

    Shape-compatible with `multi_scale_benchmark.build_multi_scale_semantic_report`'s
    output (same `strategy`/`cohort`/`threshold_sweep`/
    `static_false_positive_clusters`/`scale_specific_facts`/
    `sample_sufficiency`/`execution.max_windows_per_frame` keys) so the
    existing, unmodified `compare_strategy_reports` and `multi-scale-comparison`
    CLI command work on this report without any duck-typing special case;
    `proposal_behavior` and `proposal_records` are additive. Absolute paths,
    host/PID facts, wall-clock timestamps, and every runtime/resource fact
    never enter this dict -- callers append those separately under an
    `execution` key excluded from `semantic_fingerprint`."""

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
    proposal_behavior, proposal_records = compute_proposal_behavior(proposal_results)

    semantic: dict[str, object] = {
        "schema_version": MOTION_PROPOSAL_REPORT_SCHEMA_VERSION,
        "benchmark_version": MOTION_PROPOSAL_BENCHMARK_VERSION,
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
        "proposal_behavior": asdict(proposal_behavior),
        "proposal_records": [asdict(row) for row in proposal_records],
        "sample_sufficiency": asdict(sufficiency),
        "overall_classification": overall_classification(sufficiency),
        "creates_truth": False,
        "shadow_only": True,
        "production_proposal_authority": False,
    }
    return {**semantic, "semantic_fingerprint": semantic_fingerprint(semantic)}


# --------------------------------------------------------------------------
# Three-way decision (full_frame vs uniform_tiles vs motion_proposals)
# --------------------------------------------------------------------------

Classification = Literal["better", "equivalent", "worse", "insufficient_truth"]
FinalRecommendation = Literal[
    "retain_full_frame_inference",
    "continue_adaptive_strategy_offline",
    "expand_temporal_benchmark_truth",
    "adaptive_strategy_ready_for_bounded_live_shadow_trial",
    "adaptive_strategy_unsuitable",
    "insufficient_temporal_data",
]


def _require_dict(value: dict[str, object], key: str) -> dict[str, object]:
    result = value.get(key)
    if not isinstance(result, dict):
        raise MotionProposalBenchmarkError(f"invalid_report_missing_{key}")
    return result


def _configured_row(report: dict[str, object]) -> dict[str, object] | None:
    sweep = report.get("threshold_sweep")
    if not isinstance(sweep, list) or not sweep:
        return None
    row = sweep[0]
    return row if isinstance(row, dict) else None


def _proposal_region_recall(motion_proposal_report: dict[str, object]) -> float | None:
    """Of the true positives this strategy actually found, what fraction
    were found *only* through a proposal window -- i.e. marginal recall the
    full-frame pass alone would have missed. Computed strictly from already-
    produced report fields (`scale_specific_facts.tile_recovered_true_appearances`,
    reused unchanged from `compute_scale_specific_facts`, and the configured
    threshold row's own `true_positives`)."""

    facts = motion_proposal_report.get("scale_specific_facts")
    row = _configured_row(motion_proposal_report)
    if not isinstance(facts, dict) or row is None:
        return None
    recovered = facts.get("tile_recovered_true_appearances")
    true_positives = row.get("true_positives")
    if (
        not isinstance(recovered, int) or isinstance(recovered, bool)
        or not isinstance(true_positives, int) or isinstance(true_positives, bool)
        or true_positives <= 0
    ):
        return None
    return recovered / true_positives


def _temporal_sufficiency(motion_proposal_report: dict[str, object]) -> tuple[bool, tuple[str, ...]]:
    behavior = motion_proposal_report.get("proposal_behavior")
    if not isinstance(behavior, dict):
        return False, ("motion-proposal report carries no proposal_behavior section",)
    eligible = behavior.get("frames_eligible_for_temporal_proposals")
    with_proposals = behavior.get("frames_with_proposals")
    reasons: list[str] = []
    if not isinstance(eligible, int) or eligible < MIN_FRAMES_ELIGIBLE_FOR_TEMPORAL_SUFFICIENCY:
        reasons.append(
            f"fewer than {MIN_FRAMES_ELIGIBLE_FOR_TEMPORAL_SUFFICIENCY} frames were eligible for a "
            f"temporal proposal ({eligible if isinstance(eligible, int) else 'unknown'})"
        )
    if not isinstance(with_proposals, int) or with_proposals < MIN_FRAMES_WITH_PROPOSALS_FOR_TEMPORAL_SUFFICIENCY:
        reasons.append(
            f"fewer than {MIN_FRAMES_WITH_PROPOSALS_FOR_TEMPORAL_SUFFICIENCY} frames actually produced a "
            f"proposal ({with_proposals if isinstance(with_proposals, int) else 'unknown'})"
        )
    return not reasons, tuple(reasons)


@dataclass(frozen=True)
class AdaptiveStrategyDecision:
    recall_vs_full_frame: Classification
    recall_vs_uniform_tiles: Classification
    small_subject_recall_vs_full_frame: Classification
    precision_vs_full_frame: Classification
    precision_vs_uniform_tiles: Classification
    static_scene_behavior_vs_full_frame: Classification
    proposal_region_recall: float | None
    duplicate_behavior: str
    resource_cost_vs_full_frame: str
    resource_cost_vs_uniform_tiles: str
    evidence_sufficient: bool
    evidence_limitations: tuple[str, ...]
    final_recommendation: FinalRecommendation
    rationale: tuple[str, ...]


def _final_recommendation(
    *,
    temporal_sufficient: bool,
    cohort_consistent_ff: bool,
    cohort_consistent_ut: bool,
    sample_sufficiency_ok: bool,
    recall_vs_ff: Classification,
    recall_vs_ut: Classification,
    precision_vs_ff: Classification,
    small_subject_vs_ff: Classification,
    static_scene_vs_ff: Classification,
    duplicate_behavior: str,
    proposal_region_recall: float | None,
    frames_with_proposals: int | None,
) -> tuple[FinalRecommendation, tuple[str, ...]]:
    """Deterministic verdict from semantic inputs only -- never a resource/
    latency measurement (mirrors `multi_scale_benchmark._final_recommendation`'s
    structural exclusion of runtime facts from the decision)."""

    if not temporal_sufficient:
        return "insufficient_temporal_data", ("reviewed temporal cohort does not clear the eligibility/proposal-count sufficiency bound",)
    if not (cohort_consistent_ff and cohort_consistent_ut):
        return "insufficient_temporal_data", ("motion-proposal report was not scored against the identical reviewed cohort as one or both baselines",)
    if not sample_sufficiency_ok:
        return "insufficient_temporal_data", ("reviewed cohort does not clear the static sample-sufficiency bound",)
    if duplicate_behavior == "unacceptable":
        return "adaptive_strategy_unsuitable", ("cross-window duplicate behavior classified unacceptable",)
    if precision_vs_ff == "worse" and recall_vs_ff == "worse":
        return "retain_full_frame_inference", ("both precision and recall worse than the full-frame baseline",)
    if proposal_region_recall is None or not frames_with_proposals:
        return "expand_temporal_benchmark_truth", (
            "no reviewed true appearance fell inside a proposal window on this cohort; more temporal "
            "truth is needed before recall/precision differences are attributable to the proposal mechanism",
        )
    if (
        recall_vs_ff in ("better", "equivalent") and precision_vs_ff in ("better", "equivalent")
        and recall_vs_ut in ("better", "equivalent")
        and small_subject_vs_ff != "worse" and static_scene_vs_ff != "worse"
        and duplicate_behavior in ("acceptable", "degraded")
        and proposal_region_recall > 0.0
    ):
        return "adaptive_strategy_ready_for_bounded_live_shadow_trial", (
            "recall and precision at least equivalent to full-frame, recall at least equivalent to uniform "
            "tiles, small-subject recall and static-scene behavior not worse, proposal-region recall is "
            "positive -- check the separate non-semantic resource facts before a live shadow trial",
        )
    return "continue_adaptive_strategy_offline", ("mixed or inconclusive evidence; continue offline evaluation",)


def build_adaptive_decision_report(
    full_frame_report: dict[str, object],
    uniform_tiles_report: dict[str, object],
    motion_proposal_report: dict[str, object],
) -> dict[str, object]:
    """Compare the adaptive strategy separately against both baselines and
    emit one deterministic, non-opaque decision. Reuses
    `compare_strategy_reports` (unchanged) for both pairwise metric
    comparisons rather than reimplementing precision/recall comparison."""

    vs_full_frame = compare_strategy_reports(full_frame_report, motion_proposal_report)
    vs_uniform_tiles = compare_strategy_reports(uniform_tiles_report, motion_proposal_report)

    temporal_sufficient, temporal_limitations = _temporal_sufficiency(motion_proposal_report)
    proposal_recall = _proposal_region_recall(motion_proposal_report)
    behavior = motion_proposal_report.get("proposal_behavior")
    frames_with_proposals = behavior.get("frames_with_proposals") if isinstance(behavior, dict) else None
    candidate_sufficiency = motion_proposal_report.get("sample_sufficiency")
    sample_sufficiency_ok = bool(isinstance(candidate_sufficiency, dict) and candidate_sufficiency.get("sufficient_for_threshold_selection"))

    duplicate_behavior = str(vs_full_frame.get("duplicate_behavior", "insufficient_evidence"))
    recommendation, rationale = _final_recommendation(
        temporal_sufficient=temporal_sufficient,
        cohort_consistent_ff=bool(vs_full_frame.get("cohort_consistent")),
        cohort_consistent_ut=bool(vs_uniform_tiles.get("cohort_consistent")),
        sample_sufficiency_ok=sample_sufficiency_ok,
        recall_vs_ff=vs_full_frame.get("recall", "insufficient_truth"),  # type: ignore[arg-type]
        recall_vs_ut=vs_uniform_tiles.get("recall", "insufficient_truth"),  # type: ignore[arg-type]
        precision_vs_ff=vs_full_frame.get("precision", "insufficient_truth"),  # type: ignore[arg-type]
        small_subject_vs_ff=vs_full_frame.get("small_subject_recall", "insufficient_truth"),  # type: ignore[arg-type]
        static_scene_vs_ff=vs_full_frame.get("static_scene_behavior", "insufficient_truth"),  # type: ignore[arg-type]
        duplicate_behavior=duplicate_behavior,
        proposal_region_recall=proposal_recall,
        frames_with_proposals=frames_with_proposals if isinstance(frames_with_proposals, int) else None,
    )

    decision = AdaptiveStrategyDecision(
        recall_vs_full_frame=vs_full_frame.get("recall", "insufficient_truth"),  # type: ignore[arg-type]
        recall_vs_uniform_tiles=vs_uniform_tiles.get("recall", "insufficient_truth"),  # type: ignore[arg-type]
        small_subject_recall_vs_full_frame=vs_full_frame.get("small_subject_recall", "insufficient_truth"),  # type: ignore[arg-type]
        precision_vs_full_frame=vs_full_frame.get("precision", "insufficient_truth"),  # type: ignore[arg-type]
        precision_vs_uniform_tiles=vs_uniform_tiles.get("precision", "insufficient_truth"),  # type: ignore[arg-type]
        static_scene_behavior_vs_full_frame=vs_full_frame.get("static_scene_behavior", "insufficient_truth"),  # type: ignore[arg-type]
        proposal_region_recall=proposal_recall,
        duplicate_behavior=duplicate_behavior,
        resource_cost_vs_full_frame=str(vs_full_frame.get("execution", {}).get("resource_facts", {}).get("resource_cost", "insufficient_evidence")),
        resource_cost_vs_uniform_tiles=str(vs_uniform_tiles.get("execution", {}).get("resource_facts", {}).get("resource_cost", "insufficient_evidence")),
        evidence_sufficient=temporal_sufficient and sample_sufficiency_ok and bool(vs_full_frame.get("cohort_consistent")) and bool(vs_uniform_tiles.get("cohort_consistent")),
        evidence_limitations=temporal_limitations,
        final_recommendation=recommendation,
        rationale=rationale,
    )

    semantic: dict[str, object] = {
        "schema_version": DECISION_SCHEMA_VERSION,
        "decision_version": DECISION_VERSION,
        **asdict(decision),
        "safe_for_shadow_experimentation": True,
        "safe_for_production_authority": False,
        "creates_truth": False,
        "shadow_only": True,
        "production_proposal_authority": False,
    }
    execution = {
        "comparison_vs_full_frame": {k: v for k, v in vs_full_frame.items() if k in ("execution",)}.get("execution", {}),
        "comparison_vs_uniform_tiles": {k: v for k, v in vs_uniform_tiles.items() if k in ("execution",)}.get("execution", {}),
    }
    return {**semantic, "semantic_fingerprint": semantic_fingerprint(semantic), "execution": execution}


__all__ = [
    "DECISION_SCHEMA_VERSION",
    "DECISION_VERSION",
    "MIN_FRAMES_ELIGIBLE_FOR_TEMPORAL_SUFFICIENCY",
    "MIN_FRAMES_WITH_PROPOSALS_FOR_TEMPORAL_SUFFICIENCY",
    "MOTION_PROPOSAL_BENCHMARK_VERSION",
    "MOTION_PROPOSAL_REPORT_SCHEMA_VERSION",
    "AdaptiveStrategyDecision",
    "MotionProposalBenchmarkError",
    "ProposalBehaviorMetrics",
    "ProposalRecord",
    "build_adaptive_decision_report",
    "build_motion_proposal_semantic_report",
    "compute_proposal_behavior",
    "merge_frame_proposal_windows",
]
