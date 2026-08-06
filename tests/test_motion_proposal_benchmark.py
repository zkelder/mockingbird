"""Hardware-free tests for the Stage 6.5 adaptive motion-proposal report
assembly, proposal-behavior accounting, and three-way strategy decision.

All detections/manifests here are synthetic; no ONNX Runtime, CUDA, camera,
or product database is touched. Numbered sections mirror the task's
required hardware-free-test list.
"""
from __future__ import annotations

from datetime import UTC, datetime

from mockingbird.observation.contracts import DetectionObservation
from mockingbird.observation.detector_benchmark import CalibrationFrame, CalibrationManifest, ReviewedBox
from mockingbird.observation.motion_proposal_benchmark import (
    MIN_FRAMES_ELIGIBLE_FOR_TEMPORAL_SUFFICIENCY,
    MIN_FRAMES_WITH_PROPOSALS_FOR_TEMPORAL_SUFFICIENCY,
    build_adaptive_decision_report,
    build_motion_proposal_semantic_report,
    compute_proposal_behavior,
    merge_frame_proposal_windows,
)
from mockingbird.observation.motion_proposal_strategy import (
    FULL_FRAME_PLUS_MOTION_PROPOSALS,
    ChangeRegion,
    ProposalGenerationResult,
    ProposalWindow,
    RejectedProposal,
    RejectedRegion,
)
from mockingbird.observation.multi_scale_strategy import StrategyWindow

CFG = FULL_FRAME_PLUS_MOTION_PROPOSALS
FULL_FRAME_WINDOW = StrategyWindow("full_frame", "full_frame", (0.0, 0.0, 1.0, 1.0))


def _det(obs_id: str, box: tuple[float, float, float, float] | None, score: float, *, label: str = "animal") -> DetectionObservation:
    return DetectionObservation(
        detector_id="fixture", label=label, confidence=score, captured_at=datetime(2026, 8, 5, tzinfo=UTC),
        observation_id=obs_id, frame_id="f1", provider_id="onnx-cuda", model_key="fixture",
        generation_id="g", bounding_box=box, class_source_label="0" if label == "animal" else "1",
        is_animal=label == "animal",
    )


def _proposal_window(window_id: str, box: tuple[float, float, float, float]) -> StrategyWindow:
    return StrategyWindow(window_id, "tile", box)


def _region(box: tuple[float, float, float, float], *, pixel_count: int = 50) -> ChangeRegion:
    return ChangeRegion(box=box, changed_pixel_count=pixel_count, area_fraction=0.01)


def _proposal_result(
    frame_id: str, *, predecessor_frame_id: str | None = "predecessor", proposals: tuple[ProposalWindow, ...] = (),
    pair_eligible: bool = True, pair_reason_code: str | None = None,
    rejected_regions: tuple[RejectedRegion, ...] = (), rejected_proposals: tuple[RejectedProposal, ...] = (),
) -> ProposalGenerationResult:
    return ProposalGenerationResult(
        frame_id=frame_id, predecessor_frame_id=predecessor_frame_id, pair_eligible=pair_eligible,
        pair_reason_code=pair_reason_code, changed_pixel_ratio=0.01, mean_absolute_delta=5.0,
        proposals=proposals, rejected_regions=rejected_regions, rejected_proposals=rejected_proposals,
    )


def _manifest(frames: tuple[CalibrationFrame, ...]) -> CalibrationManifest:
    return CalibrationManifest(version=1, cohort_id="fixture-motion-proposal", annotation_policy="synthetic fixture", frames=frames)


def _frame(frame_id: str, *, animal_present: str = "yes", boxes=(), scene_group: str = "fixture-scene") -> CalibrationFrame:
    return CalibrationFrame(
        frame_id=frame_id, image_path=f"{frame_id}.jpg", content_hash=None, width=1000, height=1000,
        animal_present=animal_present, boxes=boxes, scene_group=scene_group,
    )


# --------------------------------------------------------------------------
# 16. Full-frame and proposal detections merge consistently
# --------------------------------------------------------------------------


def test_full_frame_and_proposal_detections_merge_into_one_source_ordered_set() -> None:
    proposal_window = _proposal_window("motion-proposal-f1-00", (0.4, 0.4, 0.6, 0.6))
    result = _proposal_result("f1", proposals=(ProposalWindow("motion-proposal-f1-00", proposal_window, 0, _region((0.4, 0.4, 0.6, 0.6)), "predecessor"),))

    local_detections = {
        "full_frame": (_det("full-det", (0.1, 0.1, 0.2, 0.2), 0.5),),
        "motion-proposal-f1-00": (_det("prop-det", (0.2, 0.2, 0.8, 0.8), 0.6),),
    }
    kept, suppressed = merge_frame_proposal_windows("f1", result, FULL_FRAME_WINDOW, local_detections, cross_window_iou_threshold=0.5, max_final_detections=300)

    assert len(kept) == 2
    assert suppressed == ()
    window_ids = {item.window.window_id for item in kept}
    assert window_ids == {"full_frame", "motion-proposal-f1-00"}


# --------------------------------------------------------------------------
# 17. Cross-window duplicates collapse once
# --------------------------------------------------------------------------


def test_same_animal_seen_by_full_frame_and_proposal_window_collapses_to_one() -> None:
    proposal_window = _proposal_window("motion-proposal-f1-00", (0.3, 0.3, 0.7, 0.7))
    result = _proposal_result("f1", proposals=(ProposalWindow("motion-proposal-f1-00", proposal_window, 0, _region((0.3, 0.3, 0.7, 0.7)), "predecessor"),))

    # Full-frame sees the animal at (0.45,0.45,0.55,0.55) with a lower score;
    # the proposal window's local (0.5,0.5,0.5,0.5) maps to the same source
    # point via the window's own box -- same physical animal, two windows.
    local_detections = {
        "full_frame": (_det("full-det", (0.45, 0.45, 0.55, 0.55), 0.4),),
        "motion-proposal-f1-00": (_det("prop-det", (0.375, 0.375, 0.625, 0.625), 0.8),),
    }
    kept, suppressed = merge_frame_proposal_windows("f1", result, FULL_FRAME_WINDOW, local_detections, cross_window_iou_threshold=0.5, max_final_detections=300)

    assert len(kept) == 1
    assert len(suppressed) == 1
    # The higher-scored (proposal-window) detection survives.
    assert kept[0].detection.observation_id == "prop-det"
    assert suppressed[0].detection.observation_id == "full-det"


# --------------------------------------------------------------------------
# 18. Distinct animals remain separate
# --------------------------------------------------------------------------


def test_two_distinct_nearby_animals_both_survive_merge() -> None:
    proposal_window = _proposal_window("motion-proposal-f1-00", (0.0, 0.0, 1.0, 1.0))
    result = _proposal_result("f1", proposals=(ProposalWindow("motion-proposal-f1-00", proposal_window, 0, _region((0.0, 0.0, 1.0, 1.0)), "predecessor"),))

    local_detections = {
        "full_frame": (_det("left-animal", (0.1, 0.1, 0.2, 0.2), 0.5),),
        "motion-proposal-f1-00": (_det("right-animal", (0.7, 0.7, 0.8, 0.8), 0.5),),
    }
    kept, suppressed = merge_frame_proposal_windows("f1", result, FULL_FRAME_WINDOW, local_detections, cross_window_iou_threshold=0.5, max_final_detections=300)

    assert len(kept) == 2
    assert suppressed == ()


# --------------------------------------------------------------------------
# 19-22. Report-level truth accounting (reused Stage 6.2/6.4 pipeline)
# --------------------------------------------------------------------------


def _built_report(frames, kept_by_frame, suppressed_by_frame, proposal_results):
    manifest = _manifest(frames)
    return build_motion_proposal_semantic_report(
        manifest=manifest, strategy=CFG, kept_by_frame=kept_by_frame, suppressed_by_frame=suppressed_by_frame,
        proposal_results=proposal_results, provider={"provider_key": "onnx-cuda"},
    )


def test_proposal_only_true_positive_is_measured() -> None:
    frame = _frame("f1", animal_present="yes", boxes=(ReviewedBox((0.45, 0.45, 0.55, 0.55)),))
    proposal_window = _proposal_window("motion-proposal-f1-00", (0.3, 0.3, 0.7, 0.7))
    result = _proposal_result("f1", proposals=(ProposalWindow("motion-proposal-f1-00", proposal_window, 0, _region((0.3, 0.3, 0.7, 0.7)), "predecessor"),))

    # The proposal window finds the animal; the full-frame pass finds nothing.
    # Window box (0.3,0.3,0.7,0.7) local (0.375,0.375,0.625,0.625) maps
    # exactly onto the truth box (0.45,0.45,0.55,0.55) in source space.
    from mockingbird.observation.multi_scale_strategy import normalize_window_detections
    kept = (
        *normalize_window_detections(proposal_window, (_det("prop-det", (0.375, 0.375, 0.625, 0.625), 0.8),)),
    )
    kept_by_frame = {"f1": kept}
    suppressed_by_frame = {"f1": ()}

    report = _built_report((frame,), kept_by_frame, suppressed_by_frame, {"f1": result})

    assert report["scale_specific_facts"]["true_appearances_tile_only"] == 1
    assert report["scale_specific_facts"]["tile_recovered_true_appearances"] == 1
    assert report["scale_specific_facts"]["true_appearances_full_frame_only"] == 0


def test_proposal_introduced_false_positive_is_measured() -> None:
    frame = _frame("f1", animal_present="no")
    proposal_window = _proposal_window("motion-proposal-f1-00", (0.3, 0.3, 0.7, 0.7))
    result = _proposal_result("f1", proposals=(ProposalWindow("motion-proposal-f1-00", proposal_window, 0, _region((0.3, 0.3, 0.7, 0.7)), "predecessor"),))

    from mockingbird.observation.multi_scale_strategy import normalize_window_detections
    kept = normalize_window_detections(proposal_window, (_det("false-positive", (0.5, 0.5, 0.6, 0.6), 0.6),))
    report = _built_report((frame,), {"f1": kept}, {"f1": ()}, {"f1": result})

    assert report["scale_specific_facts"]["tile_introduced_false_positives"] == 1
    assert report["threshold_sweep"][0]["false_positives"] == 1


def test_true_appearance_outside_proposals_is_measured() -> None:
    frame = _frame("f1", animal_present="yes", boxes=(ReviewedBox((0.05, 0.05, 0.15, 0.15)),))
    result = _proposal_result("f1", proposals=())  # no proposal fired this frame

    full_frame_detection = _det("full-det", (0.05, 0.05, 0.15, 0.15), 0.7)
    kept_by_frame = {"f1": (type("W", (), {})(),)}  # placeholder overwritten below
    from mockingbird.observation.multi_scale_strategy import normalize_window_detections
    kept_by_frame = {"f1": normalize_window_detections(FULL_FRAME_WINDOW, (full_frame_detection,))}
    report = _built_report((frame,), kept_by_frame, {"f1": ()}, {"f1": result})

    assert report["scale_specific_facts"]["true_appearances_full_frame_only"] == 1
    assert report["scale_specific_facts"]["true_appearances_tile_only"] == 0


def test_subject_size_metrics_remain_honest_for_a_far_bucket_frame() -> None:
    frame = CalibrationFrame(
        frame_id="f1", image_path="f1.jpg", content_hash=None, width=1000, height=1000,
        animal_present="yes", boxes=(ReviewedBox((0.45, 0.45, 0.46, 0.46)),),  # 10px longest side -> "far"
        distance="far", scene_group="fixture-scene",
    )
    result = _proposal_result("f1", proposals=())
    report = _built_report((frame,), {"f1": ()}, {"f1": ()}, {"f1": result})

    far_bucket = next(row for row in report["threshold_sweep"][0]["subject_size_breakdown"] if row["distance_bucket"] == "far")
    assert far_bucket["scorable_positive_frames"] == 1
    assert far_bucket["true_positives"] == 0
    assert far_bucket["recall"] == 0.0  # honestly reported miss, not hidden


# --------------------------------------------------------------------------
# 23. Missing temporal truth reports insufficient truth
# --------------------------------------------------------------------------


def _decision_report(strategy_key, *, precision, recall, fingerprint="fp-1", windows=1, sufficient=True, far_recall=0.1, tp=10, eligible=20, with_proposals=8, recovered=2, clusters=0):
    row = {
        "threshold": 0.1, "is_configured_threshold": True, "precision": precision, "recall": recall,
        "true_positives": tp, "false_positives": 3,
        "subject_size_breakdown": [{"distance_bucket": "far", "recall": far_recall}],
    }
    return {
        "strategy": {"strategy_key": strategy_key}, "cohort": {"manifest_fingerprint": fingerprint},
        "threshold_sweep": [row], "static_false_positive_clusters": {"clusters": [{}] * clusters},
        "scale_specific_facts": {"duplicates_before_suppression": 10, "duplicates_after_suppression": 8, "tile_recovered_true_appearances": recovered},
        "sample_sufficiency": {"sufficient_for_threshold_selection": sufficient},
        "execution": {"max_windows_per_frame": windows},
        "proposal_behavior": {"frames_eligible_for_temporal_proposals": eligible, "frames_with_proposals": with_proposals},
    }


def test_thin_temporal_evidence_is_reported_insufficient_not_a_false_verdict() -> None:
    full_frame = _decision_report("full_frame", precision=0.3, recall=0.35)
    uniform_tiles = _decision_report("full_frame_plus_uniform_tiles", precision=0.05, recall=0.5, windows=9, far_recall=0.2)
    motion_proposals = _decision_report(
        "full_frame_plus_motion_proposals", precision=0.35, recall=0.4, windows=4, far_recall=0.15,
        eligible=1, with_proposals=1,  # below both temporal-sufficiency bounds
    )

    decision = build_adaptive_decision_report(full_frame, uniform_tiles, motion_proposals)

    assert decision["final_recommendation"] == "insufficient_temporal_data"
    assert decision["evidence_sufficient"] is False
    assert any("eligible for a temporal proposal" in reason for reason in decision["evidence_limitations"])


def test_sufficient_temporal_evidence_with_favorable_metrics_is_ready_for_shadow_trial() -> None:
    full_frame = _decision_report("full_frame", precision=0.3, recall=0.35, far_recall=0.1)
    uniform_tiles = _decision_report("full_frame_plus_uniform_tiles", precision=0.05, recall=0.5, windows=9, far_recall=0.5)
    motion_proposals = _decision_report(
        "full_frame_plus_motion_proposals", precision=0.35, recall=0.5, windows=4, far_recall=0.2,
        eligible=MIN_FRAMES_ELIGIBLE_FOR_TEMPORAL_SUFFICIENCY, with_proposals=MIN_FRAMES_WITH_PROPOSALS_FOR_TEMPORAL_SUFFICIENCY, recovered=3,
    )

    decision = build_adaptive_decision_report(full_frame, uniform_tiles, motion_proposals)

    assert decision["final_recommendation"] == "adaptive_strategy_ready_for_bounded_live_shadow_trial"
    assert decision["safe_for_production_authority"] is False


def test_cohort_mismatch_is_reported_insufficient_not_compared_numerically() -> None:
    full_frame = _decision_report("full_frame", precision=0.3, recall=0.35, fingerprint="cohort-a")
    uniform_tiles = _decision_report("full_frame_plus_uniform_tiles", precision=0.05, recall=0.5, windows=9, fingerprint="cohort-a")
    motion_proposals = _decision_report("full_frame_plus_motion_proposals", precision=0.35, recall=0.4, windows=4, fingerprint="cohort-b")

    decision = build_adaptive_decision_report(full_frame, uniform_tiles, motion_proposals)

    assert decision["final_recommendation"] == "insufficient_temporal_data"
    assert decision["evidence_sufficient"] is False


def test_worse_precision_and_recall_retains_full_frame_inference() -> None:
    full_frame = _decision_report("full_frame", precision=0.3, recall=0.35)
    uniform_tiles = _decision_report("full_frame_plus_uniform_tiles", precision=0.05, recall=0.5, windows=9)
    motion_proposals = _decision_report(
        "full_frame_plus_motion_proposals", precision=0.05, recall=0.05, windows=4, tp=1, recovered=0,
        eligible=MIN_FRAMES_ELIGIBLE_FOR_TEMPORAL_SUFFICIENCY, with_proposals=MIN_FRAMES_WITH_PROPOSALS_FOR_TEMPORAL_SUFFICIENCY,
    )

    decision = build_adaptive_decision_report(full_frame, uniform_tiles, motion_proposals)

    assert decision["final_recommendation"] == "retain_full_frame_inference"


def test_no_outcome_ever_authorizes_production() -> None:
    reports = [
        _decision_report("full_frame", precision=0.3, recall=0.35),
        _decision_report("full_frame_plus_uniform_tiles", precision=0.05, recall=0.5, windows=9),
        _decision_report("full_frame_plus_motion_proposals", precision=0.35, recall=0.5, windows=4, eligible=50, with_proposals=30, recovered=5),
    ]
    decision = build_adaptive_decision_report(*reports)
    assert decision["safe_for_production_authority"] is False
    assert decision["production_proposal_authority"] is False
    assert decision["creates_truth"] is False


# --------------------------------------------------------------------------
# 25. Runtime differences do not alter semantic fingerprints
# --------------------------------------------------------------------------


def test_semantic_report_never_receives_an_execution_parameter() -> None:
    import inspect
    signature = inspect.signature(build_motion_proposal_semantic_report)
    assert "execution" not in signature.parameters


def test_semantic_report_is_identical_regardless_of_caller_side_execution_facts() -> None:
    frame = _frame("f1", animal_present="no")
    result = _proposal_result("f1", proposals=())
    report_one = _built_report((frame,), {"f1": ()}, {"f1": ()}, {"f1": result})
    report_two = _built_report((frame,), {"f1": ()}, {"f1": ()}, {"f1": result})

    assert report_one["semantic_fingerprint"] == report_two["semantic_fingerprint"]
    assert "execution" not in report_one


# --------------------------------------------------------------------------
# compute_proposal_behavior: rejection-reason accounting
# --------------------------------------------------------------------------


def test_compute_proposal_behavior_counts_every_reason_exactly_once() -> None:
    results = {
        "f1": _proposal_result("f1", pair_eligible=False, pair_reason_code="first_frame_no_predecessor"),
        "f2": _proposal_result(
            "f2", proposals=(ProposalWindow("p", _proposal_window("p", (0.1, 0.1, 0.3, 0.3)), 0, _region((0.1, 0.1, 0.3, 0.3)), "pred"),),
            rejected_regions=(RejectedRegion(_region((0.0, 0.0, 0.01, 0.01)), "region_area_below_minimum"),),
        ),
    }
    metrics, records = compute_proposal_behavior(results)

    assert metrics.frames_eligible_for_temporal_proposals == 1
    assert metrics.frames_with_proposals == 1
    assert metrics.total_proposal_count == 1
    assert metrics.total_proposals_rejected == 1
    assert dict(metrics.rejection_reason_distribution) == {
        "first_frame_no_predecessor": 1, "region_area_below_minimum": 1,
    }
    assert len(records) == 1
    assert records[0].frame_id == "f2"
