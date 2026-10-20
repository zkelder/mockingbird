"""Hardware-free tests for the Stage 6.4 multi-scale benchmark report
assembly and strategy-vs-strategy comparison.

All inputs are synthetic; no ONNX Runtime, CUDA, camera, or product
database is touched. Numbered sections mirror the task's required-test list.
"""
from __future__ import annotations

import copy
from datetime import UTC, datetime
import json

from mockingbird.observation.contracts import DetectionObservation
from mockingbird.observation.detector_benchmark import CalibrationFrame, CalibrationManifest, ReviewedBox
from mockingbird.observation.multi_scale_benchmark import (
    build_multi_scale_semantic_report,
    compare_strategy_reports,
    merge_frame_windows,
)
from mockingbird.observation.multi_scale_strategy import (
    FULL_FRAME,
    FULL_FRAME_PLUS_UNIFORM_TILES,
    windows_for_frame,
)


def _det(obs_id: str, box: tuple[float, float, float, float], score: float) -> DetectionObservation:
    return DetectionObservation(
        detector_id="fixture", label="animal", confidence=score, captured_at=datetime(2026, 8, 5, tzinfo=UTC),
        observation_id=obs_id, frame_id="f1", provider_id="onnx-cuda", model_key="fixture",
        generation_id="g", bounding_box=box, class_source_label="0", is_animal=True,
    )


def _local_box_for(window, source_box: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
    left, top, right, bottom = window.source_box
    width, height = right - left, bottom - top
    sl, st, sr, sb = source_box
    return ((sl - left) / width, (st - top) / height, (sr - left) / width, (sb - top) / height)


PROVIDER = {"provider_key": "onnx-cuda", "model": {"key": "md-v5a", "license": "MIT"}}


def _run_strategy(
    manifest: CalibrationManifest, strategy, *,
    small_bird_truth: tuple[float, float, float, float] | None = None,
    tile_false_positive: bool = False,
    findable_by_full_frame: bool = False,
):
    """A small, deterministic harness: places a synthetic detection wherever
    an *eligible* window covers the given truth box (for `small_bird_frame`),
    and optionally injects a tile-only false positive on the negative frame.

    `findable_by_full_frame` models whether a full-resolution, whole-frame
    inference pass could plausibly resolve this subject at all -- a tile
    window can always find a truth box it geometrically covers (that is the
    point of tiling), but a real detector's full-frame pass at fixed input
    resolution genuinely may not, which is exactly the scale-reduction
    question this benchmark exists to characterize. Defaulting this to
    `False` keeps the small/distant-subject scenario honest rather than
    letting geometric coverage alone imply detectability."""

    kept_by_frame, suppressed_by_frame = {}, {}
    for frame in manifest.frames:
        windows = windows_for_frame(strategy, source_width=frame.width, source_height=frame.height)
        local_dets = {window.window_id: () for window in windows}
        if small_bird_truth is not None and frame.animal_present == "yes":
            for window in windows:
                if window.window_kind == "full_frame" and not findable_by_full_frame:
                    continue
                left, top, right, bottom = window.source_box
                truth_left, truth_top, truth_right, truth_bottom = small_bird_truth
                if left <= truth_left and truth_right <= right and top <= truth_top and truth_bottom <= bottom:
                    local_box = _local_box_for(window, small_bird_truth)
                    local_dets[window.window_id] = (_det(f"bird-{window.window_id}", local_box, 0.6),)
        if tile_false_positive and frame.animal_present == "no":
            for window in windows:
                if window.window_kind == "tile":
                    local_dets[window.window_id] = (_det(f"fp-{window.window_id}", (0.4, 0.4, 0.6, 0.6), 0.55),)
                    break
        kept, suppressed = merge_frame_windows(
            windows, local_dets, cross_window_iou_threshold=strategy.cross_window_iou_threshold,
            max_final_detections=strategy.max_final_detections,
        )
        kept_by_frame[frame.frame_id] = kept
        suppressed_by_frame[frame.frame_id] = suppressed
    return build_multi_scale_semantic_report(
        manifest=manifest, strategy=strategy, kept_by_frame=kept_by_frame,
        suppressed_by_frame=suppressed_by_frame, provider=PROVIDER,
    )


def _small_bird_manifest(*, extra_positive_frames: int = 0) -> CalibrationManifest:
    truth = (0.42, 0.42, 0.44, 0.44)
    frames = [
        CalibrationFrame(
            frame_id="small-bird", image_path="images/small-bird.jpg", content_hash="a" * 64,
            width=3840, height=2160, animal_present="yes", boxes=(ReviewedBox(truth),),
            distance="far", scene_group="scene-a",
        ),
        CalibrationFrame(
            frame_id="empty", image_path="images/empty.jpg", content_hash="b" * 64,
            width=3840, height=2160, animal_present="no", scene_group="scene-a",
        ),
    ]
    for index in range(extra_positive_frames):
        frames.append(CalibrationFrame(
            frame_id=f"typical-{index}", image_path=f"images/typical-{index}.jpg", content_hash=f"{index:064x}",
            width=1920, height=1080, animal_present="yes",
            boxes=(ReviewedBox((0.3, 0.3, 0.7, 0.7)),), distance="typical", scene_group="scene-a",
        ))
    return CalibrationManifest(1, "sanity-cohort", "synthetic sanity check", tuple(frames))


# --------------------------------------------------------------------------
# 12. Full-frame-only true positive
# --------------------------------------------------------------------------


def test_full_frame_only_true_positive() -> None:
    # A truth box large enough for full-frame inference to actually find.
    large_truth_manifest = CalibrationManifest(1, "cohort", "policy", (
        CalibrationFrame(
            frame_id="big-bird", image_path="images/big.jpg", content_hash="c" * 64,
            width=1920, height=1080, animal_present="yes",
            boxes=(ReviewedBox((0.3, 0.3, 0.7, 0.7)),), distance="typical", scene_group="scene-a",
        ),
        CalibrationFrame(
            frame_id="empty", image_path="images/empty.jpg", content_hash="b" * 64,
            width=1920, height=1080, animal_present="no", scene_group="scene-a",
        ),
    ))
    report = _run_strategy(large_truth_manifest, FULL_FRAME_PLUS_UNIFORM_TILES, small_bird_truth=(0.3, 0.3, 0.7, 0.7), findable_by_full_frame=True)

    facts = report["scale_specific_facts"]
    assert facts["true_appearances_full_frame_only"] + facts["true_appearances_both"] >= 1


# --------------------------------------------------------------------------
# 13. Tile-only true positive
# --------------------------------------------------------------------------


def test_tile_only_true_positive_recovers_a_small_subject() -> None:
    manifest = _small_bird_manifest()

    full_frame_report = _run_strategy(manifest, FULL_FRAME, small_bird_truth=(0.42, 0.42, 0.44, 0.44))
    tiled_report = _run_strategy(manifest, FULL_FRAME_PLUS_UNIFORM_TILES, small_bird_truth=(0.42, 0.42, 0.44, 0.44))

    assert full_frame_report["threshold_sweep"][0]["recall"] == 0.0
    assert tiled_report["threshold_sweep"][0]["recall"] == 1.0
    assert tiled_report["scale_specific_facts"]["true_appearances_tile_only"] == 1
    assert tiled_report["scale_specific_facts"]["tile_recovered_true_appearances"] == 1


# --------------------------------------------------------------------------
# 14. Tile-introduced false positive
# --------------------------------------------------------------------------


def test_tile_introduced_false_positive_is_reported() -> None:
    manifest = _small_bird_manifest()

    report = _run_strategy(manifest, FULL_FRAME_PLUS_UNIFORM_TILES, tile_false_positive=True)

    assert report["scale_specific_facts"]["tile_introduced_false_positives"] == 1
    assert report["threshold_sweep"][0]["false_positives_on_negative_frames"] >= 1


# --------------------------------------------------------------------------
# 15. Small-subject recall metrics
# --------------------------------------------------------------------------


def test_small_subject_recall_metrics_are_bucketed_separately() -> None:
    manifest = _small_bird_manifest(extra_positive_frames=1)

    report = _run_strategy(manifest, FULL_FRAME_PLUS_UNIFORM_TILES, small_bird_truth=(0.42, 0.42, 0.44, 0.44))

    breakdown = {item["distance_bucket"]: item for item in report["threshold_sweep"][0]["subject_size_breakdown"]}
    assert breakdown["far"]["scorable_positive_frames"] == 1
    assert breakdown["far"]["recall"] == 1.0
    assert breakdown["typical"]["scorable_positive_frames"] == 1
    # The typical-sized extra frame's truth was never given a matching
    # detection by this harness, so it stays a false negative -- proves the
    # two buckets are independent, not averaged together.
    assert breakdown["typical"]["recall"] == 0.0


# --------------------------------------------------------------------------
# 16. Missing small-subject truth reports insufficient truth
# --------------------------------------------------------------------------


def test_missing_far_bucket_reports_insufficient_truth_in_comparison() -> None:
    # A cohort with only typical-sized subjects -- no "far" bucket entries
    # at all on either side.
    manifest = CalibrationManifest(1, "cohort", "policy", (
        CalibrationFrame(
            frame_id="typical", image_path="images/typical.jpg", content_hash="d" * 64,
            width=1920, height=1080, animal_present="yes",
            boxes=(ReviewedBox((0.3, 0.3, 0.7, 0.7)),), distance="typical", scene_group="scene-a",
        ),
        CalibrationFrame(
            frame_id="empty", image_path="images/empty.jpg", content_hash="b" * 64,
            width=1920, height=1080, animal_present="no", scene_group="scene-a",
        ),
    ))
    baseline = _run_strategy(manifest, FULL_FRAME, small_bird_truth=(0.3, 0.3, 0.7, 0.7))
    candidate = _run_strategy(manifest, FULL_FRAME_PLUS_UNIFORM_TILES, small_bird_truth=(0.3, 0.3, 0.7, 0.7))
    baseline["execution"] = {"max_windows_per_frame": FULL_FRAME.max_windows_per_frame}
    candidate["execution"] = {"max_windows_per_frame": FULL_FRAME_PLUS_UNIFORM_TILES.max_windows_per_frame}

    comparison = compare_strategy_reports(baseline, candidate)

    assert comparison["small_subject_recall"] == "insufficient_truth"


# --------------------------------------------------------------------------
# 18. Absolute paths remain non-semantic
# --------------------------------------------------------------------------


def test_absolute_paths_remain_non_semantic_in_benchmark_report() -> None:
    manifest = _small_bird_manifest()
    report = _run_strategy(manifest, FULL_FRAME)

    semantic_only = json.dumps(report)
    assert "/home/" not in semantic_only
    assert "/tmp/" not in semantic_only


def test_absolute_paths_remain_non_semantic_in_comparison_report() -> None:
    manifest = _small_bird_manifest()
    baseline = _run_strategy(manifest, FULL_FRAME)
    candidate = _run_strategy(manifest, FULL_FRAME_PLUS_UNIFORM_TILES)
    poisoned = "/home/user/projects/mockingbird-active/data/models/some-bundle.json"
    baseline["some_future_unread_field"] = poisoned
    candidate["execution"] = {"max_windows_per_frame": FULL_FRAME_PLUS_UNIFORM_TILES.max_windows_per_frame, "model_bundle_path": poisoned}
    baseline["execution"] = {"max_windows_per_frame": FULL_FRAME.max_windows_per_frame}

    comparison = compare_strategy_reports(baseline, candidate)

    semantic_only = json.dumps({key: value for key, value in comparison.items() if key != "execution"})
    assert poisoned not in semantic_only


# --------------------------------------------------------------------------
# 19. Runtime/resource differences do not alter fingerprints
# --------------------------------------------------------------------------


def test_runtime_and_resource_differences_do_not_change_comparison_fingerprint() -> None:
    manifest = _small_bird_manifest()
    baseline = _run_strategy(manifest, FULL_FRAME)
    candidate = _run_strategy(manifest, FULL_FRAME_PLUS_UNIFORM_TILES)
    baseline["execution"] = {"max_windows_per_frame": FULL_FRAME.max_windows_per_frame}

    mild_candidate = copy.deepcopy(candidate)
    mild_candidate["execution"] = {"max_windows_per_frame": 10}
    extreme_candidate = copy.deepcopy(candidate)
    extreme_candidate["execution"] = {"max_windows_per_frame": 999}  # crosses every resource-cost boundary

    mild = compare_strategy_reports(baseline, mild_candidate)
    extreme = compare_strategy_reports(baseline, extreme_candidate)

    assert mild["semantic_fingerprint"] == extreme["semantic_fingerprint"]
    assert mild["execution"]["resource_facts"]["resource_cost"] == "degraded"
    assert extreme["execution"]["resource_facts"]["resource_cost"] == "unacceptable"
    assert mild["final_recommendation"] == extreme["final_recommendation"]
    assert "resource_cost" not in {k for k in mild if k != "execution"}


def test_build_report_never_takes_execution_facts_as_input() -> None:
    # Structural guarantee, not just a behavioral one: the pure report
    # builder's signature has no execution/runtime parameter at all, so it
    # cannot leak one even by future accident inside this test file's own
    # harness usage.
    import inspect

    signature = inspect.signature(build_multi_scale_semantic_report)
    assert "execution" not in signature.parameters


# --------------------------------------------------------------------------
# 20. No runtime configuration or product truth mutation
# --------------------------------------------------------------------------


def test_compare_strategy_reports_does_not_mutate_inputs() -> None:
    manifest = _small_bird_manifest()
    baseline = _run_strategy(manifest, FULL_FRAME)
    candidate = _run_strategy(manifest, FULL_FRAME_PLUS_UNIFORM_TILES)
    baseline["execution"] = {"max_windows_per_frame": FULL_FRAME.max_windows_per_frame}
    candidate["execution"] = {"max_windows_per_frame": FULL_FRAME_PLUS_UNIFORM_TILES.max_windows_per_frame}
    baseline_before, candidate_before = copy.deepcopy(baseline), copy.deepcopy(candidate)

    compare_strategy_reports(baseline, candidate)

    assert baseline == baseline_before
    assert candidate == candidate_before


def test_report_always_declares_shadow_only_and_no_truth() -> None:
    manifest = _small_bird_manifest()
    report = _run_strategy(manifest, FULL_FRAME)

    assert report["creates_truth"] is False
    assert report["shadow_only"] is True
    assert report["production_proposal_authority"] is False


def test_comparison_always_declares_shadow_only_and_no_truth() -> None:
    manifest = _small_bird_manifest()
    baseline = _run_strategy(manifest, FULL_FRAME)
    candidate = _run_strategy(manifest, FULL_FRAME_PLUS_UNIFORM_TILES)
    baseline["execution"] = {"max_windows_per_frame": FULL_FRAME.max_windows_per_frame}
    candidate["execution"] = {"max_windows_per_frame": FULL_FRAME_PLUS_UNIFORM_TILES.max_windows_per_frame}

    comparison = compare_strategy_reports(baseline, candidate)

    assert comparison["creates_truth"] is False
    assert comparison["shadow_only"] is True
    assert comparison["production_proposal_authority"] is False


def test_module_source_has_no_product_repository_or_truth_imports() -> None:
    from pathlib import Path

    for name in ("multi_scale_benchmark.py", "multi_scale_benchmark_io.py", "multi_scale_cli.py"):
        source = Path(f"src/mockingbird/observation/{name}").read_text(encoding="utf-8")
        forbidden = (
            "mockingbird.db", "mockingbird.repositories", "sqlite3", "ReviewLabel",
            "MotionEvidence", "monitoring_policy", "Event(", "Visit(", "import requests", "urllib",
        )
        for token in forbidden:
            assert token not in source, f"{name} unexpectedly references {token}"


# --------------------------------------------------------------------------
# 11. Duplicate windows do not count as temporal support (report-level)
# --------------------------------------------------------------------------


def test_duplicate_window_detections_do_not_inflate_temporal_confirmation() -> None:
    # One frame, two overlapping windows both detecting the identical
    # physical animal -- after merge+suppression only one detection can
    # possibly reach the temporal-policy simulation for this single-frame
    # sequence, so `two_detections` must not be satisfied by within-frame
    # window duplication alone.
    truth = (0.10, 0.10, 0.20, 0.20)
    frame = CalibrationFrame(
        frame_id="single", image_path="images/single.jpg", content_hash="e" * 64,
        width=1920, height=1080, animal_present="yes", boxes=(ReviewedBox(truth),),
        scene_group="scene-a", sequence_id="seq-1", sequence_order=0, source_offset_ms=0,
    )
    manifest = CalibrationManifest(1, "cohort", "policy", (frame,))
    strategy = FULL_FRAME_PLUS_UNIFORM_TILES
    windows = windows_for_frame(strategy, source_width=frame.width, source_height=frame.height)
    # Full-frame AND a covering tile both "detect" the same animal.
    local_dets = {window.window_id: () for window in windows}
    local_dets["full_frame"] = (_det("full", truth, 0.6),)
    for window in windows:
        if window.window_kind == "tile":
            left, top, right, bottom = window.source_box
            if left <= truth[0] and truth[2] <= right and top <= truth[1] and truth[3] <= bottom:
                local_dets[window.window_id] = (_det(f"tile-{window.window_id}", _local_box_for(window, truth), 0.8),)

    kept, suppressed = merge_frame_windows(windows, local_dets, cross_window_iou_threshold=strategy.cross_window_iou_threshold, max_final_detections=strategy.max_final_detections)
    assert len(kept) == 1  # collapsed to one despite two windows finding it

    report = build_multi_scale_semantic_report(
        manifest=manifest, strategy=strategy, kept_by_frame={"single": kept},
        suppressed_by_frame={"single": suppressed}, provider=PROVIDER,
    )
    two_detections_policy = next(item for item in report["temporal_policy_simulation"] if item["policy"] == "two_detections")
    assert two_detections_policy["confirmed_true_appearances"] == 0  # only one surviving detection, policy requires >= 2
