"""Hardware-free tests for the Stage 6.2 detector-calibration benchmark.

All observations here are synthetic (`DetectionObservation` built directly);
no ONNX Runtime, CUDA, camera, or product database is touched.
"""
from __future__ import annotations

from datetime import UTC, datetime

import pytest

from mockingbird.observation.contracts import DetectionObservation
from mockingbird.observation.detector_benchmark import (
    CLUSTER_MIN_RECURRENCE,
    DEFAULT_THRESHOLD_GRID,
    CalibrationFrame,
    CalibrationManifest,
    DetectorBenchmarkError,
    ReviewedBox,
    StaticStructure,
    anchor_score_threshold,
    build_semantic_report,
    classify_frame,
    classify_recommendations,
    classify_sample_sufficiency,
    cluster_static_false_positives,
    compare_preprocessing,
    effective_threshold_grid,
    overall_classification,
    simulate_temporal_policies,
    sweep_thresholds,
)


def _det(
    frame_id: str,
    box: tuple[float, float, float, float] | None,
    score: float,
    *,
    label: str = "animal",
    observation_id: str | None = None,
) -> DetectionObservation:
    return DetectionObservation(
        detector_id="fixture-detector",
        label=label,
        confidence=score,
        captured_at=datetime(2026, 8, 5, tzinfo=UTC),
        observation_id=observation_id or f"{frame_id}:{box}:{score}:{label}",
        frame_id=frame_id,
        provider_id="onnx-cuda",
        model_key="fixture",
        generation_id="fixture-generation",
        bounding_box=box,
        class_source_label="0" if label == "animal" else "1",
        is_animal=label == "animal",
    )


def _frame(frame_id: str, **overrides: object) -> CalibrationFrame:
    values: dict[str, object] = {
        "frame_id": frame_id,
        "image_path": f"images/{frame_id}.jpg",
        "content_hash": "a" * 64,
        "width": 200,
        "height": 100,
        "animal_present": "no",
        "scene_group": "scene-default",
    }
    values.update(overrides)
    return CalibrationFrame(**values)  # type: ignore[arg-type]


def _manifest(frames: tuple[CalibrationFrame, ...], **overrides: object) -> CalibrationManifest:
    values: dict[str, object] = {
        "version": 1,
        "cohort_id": "fixture-cohort",
        "annotation_policy": "synthetic fixture",
        "frames": frames,
    }
    values.update(overrides)
    return CalibrationManifest(**values)  # type: ignore[arg-type]


# --------------------------------------------------------------------------
# 1. True-positive box matching
# --------------------------------------------------------------------------


def test_true_positive_box_matching() -> None:
    frame = _frame("bird-1", animal_present="yes", boxes=(ReviewedBox((0.40, 0.40, 0.60, 0.60)),))
    detections = (_det("bird-1", (0.41, 0.41, 0.59, 0.59), 0.8),)

    result = classify_frame(frame, detections, threshold=0.5)

    assert result.true_positive_count == 1
    assert result.false_positive_count == 0
    assert result.detections[0].outcome == "true_positive"


# --------------------------------------------------------------------------
# 2. False-positive classification
# --------------------------------------------------------------------------


def test_false_positive_classification_on_negative_frame() -> None:
    frame = _frame("empty-1", animal_present="no")
    detections = (_det("empty-1", (0.1, 0.1, 0.2, 0.2), 0.6),)

    result = classify_frame(frame, detections, threshold=0.5)

    assert result.false_positive_count == 1
    assert result.true_positive_count == 0
    assert result.detections[0].outcome == "false_positive"


def test_unmatched_extra_box_on_positive_frame_is_also_false_positive() -> None:
    frame = _frame("bird-2", animal_present="yes", boxes=(ReviewedBox((0.40, 0.40, 0.60, 0.60)),))
    detections = (
        _det("bird-2", (0.41, 0.41, 0.59, 0.59), 0.8, observation_id="real"),
        _det("bird-2", (0.01, 0.01, 0.05, 0.05), 0.7, observation_id="extra"),
    )

    result = classify_frame(frame, detections, threshold=0.5)

    assert result.true_positive_count == 1
    assert result.false_positive_count == 1


# --------------------------------------------------------------------------
# 3. False-negative classification (below-threshold vs true miss)
# --------------------------------------------------------------------------


def test_false_negative_below_threshold_is_distinguished_from_true_miss() -> None:
    recoverable_frame = _frame("bird-3", animal_present="yes", boxes=(ReviewedBox((0.40, 0.40, 0.60, 0.60)),))
    recoverable_detections = (_det("bird-3", (0.41, 0.41, 0.59, 0.59), 0.2),)
    recoverable = classify_frame(recoverable_frame, recoverable_detections, threshold=0.5)
    assert recoverable.false_negative_below_threshold_count == 1
    assert recoverable.false_negative_true_miss_count == 0

    missed_frame = _frame("bird-4", animal_present="yes", boxes=(ReviewedBox((0.40, 0.40, 0.60, 0.60)),))
    missed = classify_frame(missed_frame, (), threshold=0.02)
    assert missed.false_negative_below_threshold_count == 0
    assert missed.false_negative_true_miss_count == 1


# --------------------------------------------------------------------------
# 4. Ambiguous frame excluded from precision/recall denominator
# --------------------------------------------------------------------------


def test_ambiguous_frame_excluded_from_denominator() -> None:
    positive = _frame("bird-5", animal_present="yes", boxes=(ReviewedBox((0.4, 0.4, 0.6, 0.6)),))
    ambiguous = _frame("maybe-1", animal_present="ambiguous")
    manifest = _manifest((positive, ambiguous))
    detections = {
        "bird-5": (_det("bird-5", (0.41, 0.41, 0.59, 0.59), 0.8),),
        # A confident detection on the ambiguous frame must never silently
        # become a false positive (or a true positive).
        "maybe-1": (_det("maybe-1", (0.1, 0.1, 0.3, 0.3), 0.95),),
    }

    sweep = sweep_thresholds(manifest, detections, (0.5,), configured_threshold=0.5)

    row = sweep[0]
    assert row.ambiguous_or_unscorable_frame_count == 1
    assert row.true_positives == 1
    assert row.false_positives == 0
    assert row.scorable_positive_frames == 1
    assert row.scorable_negative_frames == 0


def test_unscorable_frame_excluded_from_denominator_even_when_not_ambiguous() -> None:
    frame = _frame("skip-1", animal_present="no", scorable=False)
    manifest = _manifest((frame, _frame("empty-only", animal_present="no")))
    detections = {"skip-1": (_det("skip-1", (0.1, 0.1, 0.2, 0.2), 0.99),)}

    sweep = sweep_thresholds(manifest, detections, (0.5,), configured_threshold=0.5)

    row = sweep[0]
    assert row.ambiguous_or_unscorable_frame_count == 1
    assert row.false_positives == 0


# --------------------------------------------------------------------------
# 5 & 6. Deterministic threshold sweep; precision/recall change correctly
# --------------------------------------------------------------------------


def test_threshold_sweep_is_deterministic_regardless_of_input_order() -> None:
    positive = _frame("bird-6", animal_present="yes", boxes=(ReviewedBox((0.4, 0.4, 0.6, 0.6)),))
    negative = _frame("empty-2", animal_present="no")
    manifest = _manifest((positive, negative))
    detections = {
        "bird-6": (_det("bird-6", (0.41, 0.41, 0.59, 0.59), 0.6),),
        "empty-2": (_det("empty-2", (0.1, 0.1, 0.2, 0.2), 0.3),),
    }
    thresholds = (0.7, 0.1, 0.4)

    first = sweep_thresholds(manifest, detections, thresholds, configured_threshold=0.4)
    second = sweep_thresholds(manifest, dict(reversed(list(detections.items()))), tuple(reversed(thresholds)), configured_threshold=0.4)

    assert first == second
    assert [row.threshold for row in first] == sorted(thresholds)


def test_precision_and_recall_move_correctly_across_thresholds() -> None:
    positive = _frame("bird-7", animal_present="yes", boxes=(ReviewedBox((0.4, 0.4, 0.6, 0.6)),))
    negative = _frame("empty-3", animal_present="no")
    manifest = _manifest((positive, negative))
    detections = {
        "bird-7": (_det("bird-7", (0.41, 0.41, 0.59, 0.59), 0.6),),
        # A false positive that only clears the lowest grid rung.
        "empty-3": (_det("empty-3", (0.1, 0.1, 0.2, 0.2), 0.15),),
    }

    sweep = sweep_thresholds(manifest, detections, (0.1, 0.3, 0.5, 0.9), configured_threshold=0.3)
    by_threshold = {row.threshold: row for row in sweep}

    # At 0.1 both the true animal and the false positive clear the bar.
    assert by_threshold[0.1].true_positives == 1
    assert by_threshold[0.1].false_positives == 1
    assert by_threshold[0.1].precision == 0.5
    # Raising the threshold drops the false positive but keeps the real bird.
    assert by_threshold[0.3].false_positives == 0
    assert by_threshold[0.3].precision == 1.0
    assert by_threshold[0.3].recall == 1.0
    # Raising it past the real bird's own score drops recall to zero.
    assert by_threshold[0.9].recall == 0.0
    assert by_threshold[0.9].true_positives == 0


def test_subject_size_breakdown_separates_small_and_typical_recall() -> None:
    # A small ("far") subject the detector misses and a typical-sized subject
    # it finds must not average into one misleading recall number.
    far_frame = _frame(
        "bird-far", animal_present="yes", boxes=(ReviewedBox((0.40, 0.40, 0.42, 0.42)),),
        distance="far",
    )
    typical_frame = _frame(
        "bird-typical", animal_present="yes", boxes=(ReviewedBox((0.40, 0.40, 0.60, 0.60)),),
        distance="typical",
    )
    manifest = _manifest((far_frame, typical_frame))
    detections = {
        "bird-far": (),  # missed entirely
        "bird-typical": (_det("bird-typical", (0.41, 0.41, 0.59, 0.59), 0.8),),
    }

    sweep = sweep_thresholds(manifest, detections, (0.5,), configured_threshold=0.5)
    row = sweep[0]
    by_bucket = {item.distance_bucket: item for item in row.subject_size_breakdown}

    assert by_bucket["far"].scorable_positive_frames == 1
    assert by_bucket["far"].recall == 0.0
    assert by_bucket["typical"].scorable_positive_frames == 1
    assert by_bucket["typical"].recall == 1.0
    # The overall (unstratified) recall must not be silently derivable from
    # only one bucket -- both buckets sum to the frame-level recall
    # denominator.
    assert by_bucket["far"].scorable_positive_frames + by_bucket["typical"].scorable_positive_frames == row.scorable_positive_frames


def test_effective_threshold_grid_is_bounded_deduplicated_and_sorted() -> None:
    grid = effective_threshold_grid(0.1, (0.9, 0.5, 0.1, 1.5, -0.2, 0.0))
    assert grid == tuple(sorted(grid))
    assert all(0.0 < value <= 1.0 for value in grid)
    assert len(grid) == len(set(grid))
    assert 0.1 in grid

    with pytest.raises(DetectorBenchmarkError):
        effective_threshold_grid(0.0)
    with pytest.raises(DetectorBenchmarkError):
        effective_threshold_grid(1.5)


def test_anchor_threshold_stays_strictly_below_every_grid_value() -> None:
    grid = effective_threshold_grid(0.1, DEFAULT_THRESHOLD_GRID)
    anchor = anchor_score_threshold(grid)
    assert anchor < min(grid)
    assert anchor >= 0.0


# --------------------------------------------------------------------------
# 7 & 8. Duplicate-box handling; stable IoU matching
# --------------------------------------------------------------------------


def test_duplicate_boxes_collapse_to_one_detection_and_are_counted() -> None:
    frame = _frame("empty-4", animal_present="no")
    # Two near-identical boxes for the same static object; a lower-scored
    # detector re-observation must not double the false-positive count.
    detections = (
        _det("empty-4", (0.40, 0.40, 0.50, 0.50), 0.6, observation_id="a"),
        _det("empty-4", (0.405, 0.405, 0.505, 0.505), 0.55, observation_id="b"),
    )

    result = classify_frame(frame, detections, threshold=0.5)

    assert result.false_positive_count == 1
    assert result.duplicate_count == 1
    outcomes = {item.outcome for item in result.detections}
    assert outcomes == {"false_positive", "duplicate"}


def test_duplicate_collapse_keeps_the_higher_scoring_box_regardless_of_input_order() -> None:
    high = _det("empty-5", (0.40, 0.40, 0.50, 0.50), 0.9, observation_id="high")
    low = _det("empty-5", (0.405, 0.405, 0.505, 0.505), 0.3, observation_id="low")
    frame = _frame("empty-5", animal_present="no")

    forward = classify_frame(frame, (high, low), threshold=0.1)
    backward = classify_frame(frame, (low, high), threshold=0.1)

    for result in (forward, backward):
        kept = [item for item in result.detections if item.outcome == "false_positive"]
        assert len(kept) == 1
        assert kept[0].confidence == 0.9


def test_iou_matching_is_stable_and_symmetric_around_the_configured_threshold() -> None:
    # Boxes with IoU just above and just below MATCH_IOU_THRESHOLD (0.5).
    frame_above = _frame("iou-above", animal_present="yes", boxes=(ReviewedBox((0.0, 0.0, 0.20, 0.20)),))
    close_box = (0.02, 0.0, 0.22, 0.20)  # high overlap
    above = classify_frame(frame_above, (_det("iou-above", close_box, 0.9),), threshold=0.5)
    assert above.true_positive_count == 1

    frame_below = _frame("iou-below", animal_present="yes", boxes=(ReviewedBox((0.0, 0.0, 0.20, 0.20)),))
    far_box = (0.15, 0.0, 0.35, 0.20)  # low overlap
    below = classify_frame(frame_below, (_det("iou-below", far_box, 0.9),), threshold=0.5)
    assert below.true_positive_count == 0
    assert below.false_positive_count == 1


# --------------------------------------------------------------------------
# 9 & 10. Recurring static false-positive clustering; scene groups separate
# --------------------------------------------------------------------------


def test_recurring_static_false_positive_clusters_across_frames() -> None:
    frames = tuple(_frame(f"scene-a-{i}", animal_present="no", scene_group="scene-a") for i in range(3))
    manifest = _manifest(frames)
    box = (0.45, 0.45, 0.50, 0.50)
    detections = {
        frame.frame_id: (_det(frame.frame_id, box, 0.2 + index * 0.01),)
        for index, frame in enumerate(frames)
    }

    report = cluster_static_false_positives(manifest, detections, threshold=0.1)

    assert len(report.clusters) == 1
    cluster = report.clusters[0]
    assert cluster.member_count == 3
    assert cluster.scene_group == "scene-a"
    assert report.independent_false_positive_count == 0


def test_independent_false_positives_are_reported_separately_from_clusters() -> None:
    frames = (
        _frame("scene-b-1", animal_present="no", scene_group="scene-b"),
        _frame("scene-b-2", animal_present="no", scene_group="scene-b"),
    )
    manifest = _manifest(frames)
    detections = {
        "scene-b-1": (_det("scene-b-1", (0.1, 0.1, 0.15, 0.15), 0.2),),
        "scene-b-2": (_det("scene-b-2", (0.8, 0.8, 0.85, 0.85), 0.2),),
    }

    report = cluster_static_false_positives(manifest, detections, threshold=0.1)

    assert report.clusters == ()
    assert report.independent_false_positive_count == 2


def test_static_structure_label_is_attached_to_a_matching_cluster() -> None:
    frames = tuple(_frame(f"hook-{i}", animal_present="no", scene_group="yard") for i in range(2))
    manifest = _manifest(
        frames,
        scene_static_structures={
            "yard": (StaticStructure("shepherds_hook", (0.44, 0.44, 0.50, 0.50)),),
        },
    )
    box = (0.455, 0.455, 0.475, 0.475)
    detections = {frame.frame_id: (_det(frame.frame_id, box, 0.12),) for frame in frames}

    report = cluster_static_false_positives(manifest, detections, threshold=0.1)

    assert len(report.clusters) == 1
    assert report.clusters[0].matched_static_structure == "shepherds_hook"


def test_separate_scene_groups_never_cluster_together() -> None:
    box = (0.45, 0.45, 0.50, 0.50)
    frame_a = _frame("group-a", animal_present="no", scene_group="camera-a")
    frame_b = _frame("group-b", animal_present="no", scene_group="camera-b")
    manifest = _manifest((frame_a, frame_b))
    detections = {
        "group-a": (_det("group-a", box, 0.2),),
        "group-b": (_det("group-b", box, 0.2),),
    }

    report = cluster_static_false_positives(manifest, detections, threshold=0.1)

    assert report.clusters == ()
    assert report.independent_false_positive_count == 2


def test_cluster_minimum_recurrence_is_respected() -> None:
    assert CLUSTER_MIN_RECURRENCE >= 2


# --------------------------------------------------------------------------
# 11. Privacy/Ignore detections excluded or reported separately
# --------------------------------------------------------------------------


def test_privacy_region_detection_is_excluded_and_reported_separately() -> None:
    frame = _frame(
        "privacy-1", animal_present="no",
        privacy_ignore_regions=((0.0, 0.0, 0.3, 0.3),),
    )
    inside = _det("privacy-1", (0.05, 0.05, 0.15, 0.15), 0.9, observation_id="inside")
    outside = _det("privacy-1", (0.6, 0.6, 0.7, 0.7), 0.9, observation_id="outside")

    result = classify_frame(frame, (inside, outside), threshold=0.5)

    assert result.privacy_excluded_count == 1
    assert result.false_positive_count == 1
    outcomes = {item.observation_id: item.outcome for item in result.detections}
    assert outcomes["inside"] == "privacy_excluded"
    assert outcomes["outside"] == "false_positive"


def test_privacy_excluded_detections_never_count_as_true_positive_either() -> None:
    frame = _frame(
        "privacy-2", animal_present="yes",
        boxes=(ReviewedBox((0.05, 0.05, 0.15, 0.15)),),
        privacy_ignore_regions=((0.0, 0.0, 0.3, 0.3),),
    )
    detection = _det("privacy-2", (0.05, 0.05, 0.15, 0.15), 0.95)

    result = classify_frame(frame, (detection,), threshold=0.5)

    assert result.true_positive_count == 0
    assert result.privacy_excluded_count == 1
    # The truth box is still unmatched, but its only overlapping candidate
    # was privacy-masked (not merely low-scored), so it is neither a
    # fabricated true positive nor a generic "below threshold" miss.
    assert result.false_negative_privacy_masked_count == 1
    assert result.false_negative_below_threshold_count == 0
    assert result.false_negative_true_miss_count == 0


# --------------------------------------------------------------------------
# 12 & 13. Temporal policy simulation; one-frame vs multi-frame tradeoff
# --------------------------------------------------------------------------


def _temporal_manifest() -> tuple[CalibrationManifest, dict[str, tuple[DetectionObservation, ...]]]:
    # A static false positive recurs at the same spot across a 3-frame
    # sequence where no real animal is present.
    box = (0.45, 0.45, 0.50, 0.50)
    frames = tuple(
        _frame(
            f"seq-{index}", animal_present="no", scene_group="yard",
            sequence_id="yard-sequence", sequence_order=index, source_offset_ms=index * 1000,
        )
        for index in range(3)
    )
    manifest = _manifest(frames)
    detections = {frame.frame_id: (_det(frame.frame_id, box, 0.15),) for frame in frames}
    return manifest, detections


def test_temporal_policy_simulation_reports_confirmed_false_episodes() -> None:
    manifest, detections = _temporal_manifest()

    results = simulate_temporal_policies(manifest, detections, threshold=0.1)

    by_policy = {row.policy: row for row in results}
    assert by_policy["single_detection"].confirmed_false_episodes == 1
    assert by_policy["two_distinct_frames"].confirmed_false_episodes == 1
    assert by_policy["detector_plus_tracker_confirmation"].supported is False
    assert by_policy["detector_plus_tracker_confirmation"].unsupported_limitations


def test_single_frame_policy_fires_on_a_single_frame_where_multi_frame_policy_does_not() -> None:
    box = (0.45, 0.45, 0.50, 0.50)
    lone_negative = _frame("lone-empty", animal_present="no", scene_group="lone")
    manifest = _manifest((lone_negative,))
    detections = {"lone-empty": (_det("lone-empty", box, 0.9),)}

    results = simulate_temporal_policies(manifest, detections, threshold=0.1)
    by_policy = {row.policy: row for row in results}

    # A single strong detection on a single frame: a one-frame policy
    # confirms it (falsely); a distinct-frames policy structurally cannot.
    assert by_policy["single_detection"].confirmed_false_episodes == 1
    assert by_policy["two_distinct_frames"].confirmed_false_episodes == 0
    assert by_policy["two_distinct_frames"].sequences_evaluated == 1


def test_temporal_policy_recovers_a_true_appearance_across_frames() -> None:
    box = (0.45, 0.45, 0.50, 0.50)
    frames = tuple(
        _frame(
            f"real-{index}", animal_present="yes" if index < 2 else "no",
            boxes=(ReviewedBox(box),) if index < 2 else (),
            scene_group="yard", sequence_id="real-sequence", sequence_order=index,
            source_offset_ms=index * 1000,
        )
        for index in range(3)
    )
    manifest = _manifest(frames)
    detections = {
        "real-0": (_det("real-0", box, 0.6),),
        "real-1": (_det("real-1", box, 0.6),),
        "real-2": (),
    }

    results = simulate_temporal_policies(manifest, detections, threshold=0.5)
    by_policy = {row.policy: row for row in results}

    assert by_policy["two_distinct_frames"].confirmed_true_appearances == 1
    assert by_policy["two_distinct_frames"].confirmed_false_episodes == 0
    assert by_policy["single_detection"].confirmed_true_appearances == 1


def test_temporal_span_policy_reports_missing_offsets_as_skipped_not_silently_false() -> None:
    frames = (
        _frame("no-offset-a", animal_present="no", scene_group="s", sequence_id="seq-x"),
        _frame("no-offset-b", animal_present="no", scene_group="s", sequence_id="seq-x"),
    )
    manifest = _manifest(frames)
    detections = {
        "no-offset-a": (_det("no-offset-a", (0.4, 0.4, 0.5, 0.5), 0.9),),
        "no-offset-b": (_det("no-offset-b", (0.4, 0.4, 0.5, 0.5), 0.9),),
    }

    results = simulate_temporal_policies(manifest, detections, threshold=0.1)
    span = next(row for row in results if row.policy == "minimum_temporal_span")

    assert span.sequences_skipped_insufficient_frames == 1
    assert span.sequences_evaluated == 0
    assert span.unsupported_limitations


# --------------------------------------------------------------------------
# 14. Missing truth returns insufficient truth
# --------------------------------------------------------------------------


def test_missing_reviewed_boxes_still_scores_frame_level_truth_honestly() -> None:
    # A "yes" frame with no reviewed boxes at all is a manifest authoring
    # error (a reviewer must commit to at least one box), not a silent
    # insufficient-truth case.
    with pytest.raises(DetectorBenchmarkError):
        CalibrationFrame(
            frame_id="broken", image_path="images/broken.jpg", content_hash="a" * 64,
            width=10, height=10, animal_present="yes", boxes=(),
        )


def test_negative_frame_cannot_declare_reviewed_boxes() -> None:
    with pytest.raises(DetectorBenchmarkError):
        CalibrationFrame(
            frame_id="broken-2", image_path="images/broken-2.jpg", content_hash="a" * 64,
            width=10, height=10, animal_present="no", boxes=(ReviewedBox((0.1, 0.1, 0.2, 0.2)),),
        )


def test_sample_sufficiency_reports_insufficient_data_for_a_tiny_cohort() -> None:
    manifest = _manifest((
        _frame("only-1", animal_present="yes", boxes=(ReviewedBox((0.4, 0.4, 0.6, 0.6)),)),
        _frame("only-2", animal_present="no"),
    ))

    sufficiency = classify_sample_sufficiency(manifest)

    assert sufficiency.sufficient_for_threshold_selection is False
    assert overall_classification(sufficiency) == "DETECTOR_CALIBRATION_INSUFFICIENT_DATA"
    assert sufficiency.reasons


def test_sample_sufficiency_flags_low_geometric_diversity() -> None:
    # Five "positive" frames that are really the same repeated crop.
    same_box = ReviewedBox((0.44, 0.55, 0.48, 0.60))
    frames = tuple(
        _frame(f"repeat-{index}", animal_present="yes", boxes=(same_box,), scene_group="feeder")
        for index in range(5)
    ) + tuple(_frame(f"neg-{index}", animal_present="no", scene_group="feeder") for index in range(20))
    manifest = _manifest(frames)

    sufficiency = classify_sample_sufficiency(manifest)

    assert any("distinct reviewed-box location" in reason for reason in sufficiency.reasons)


def test_recurring_cluster_recommendation_reports_one_readable_metric_string() -> None:
    # Regression: a `tuple(f"...")` bug once shredded this metric string into
    # one tuple entry per character instead of a single readable sentence.
    frames = tuple(_frame(f"cl-{i}", animal_present="no", scene_group="yard") for i in range(2))
    manifest = _manifest(frames)
    box = (0.45, 0.45, 0.50, 0.50)
    detections = {frame.frame_id: (_det(frame.frame_id, box, 0.2),) for frame in frames}
    thresholds = (0.1,)
    sweep = sweep_thresholds(manifest, detections, thresholds, configured_threshold=0.1)
    static_report = cluster_static_false_positives(manifest, detections, threshold=0.1)
    temporal = simulate_temporal_policies(manifest, detections, threshold=0.1)
    configured_row = sweep[0]
    preprocessing = compare_preprocessing(configured_row, None, primary_resize_mode="letterbox", alternative_resize_mode=None, unsupported_reason="fixture")
    sufficiency = classify_sample_sufficiency(manifest)

    recommendations = classify_recommendations(
        sweep=sweep, static_report=static_report, temporal_results=temporal,
        preprocessing=preprocessing, sufficiency=sufficiency,
    )

    region = next(item for item in recommendations if item.action == "recurring_static_false_positive_region")
    assert region.verdict == "identified"
    assert len(region.supporting_metrics) == 1
    assert region.supporting_metrics[0].startswith("1 recurring cluster")
    assert "yard" in region.supporting_metrics[0]


def test_detector_replacement_needed_when_true_misses_dominate_even_with_adequate_best_recall() -> None:
    # A cohort where every positive frame's real animal is *never* observed
    # by the detector at any score is exactly the case no threshold change
    # can fix; a best-recall-only heuristic must not silently call this fine
    # just because a handful of *other* positive frames pull the top-line
    # number above an arbitrary bound.
    box = (0.4, 0.4, 0.6, 0.6)
    always_missed = tuple(
        _frame(f"missed-{i}", animal_present="yes", boxes=(ReviewedBox(box),), scene_group="s")
        for i in range(12)
    )
    always_found = tuple(
        _frame(f"found-{i}", animal_present="yes", boxes=(ReviewedBox(box),), scene_group="s")
        for i in range(12)
    )
    negatives = tuple(_frame(f"neg-{i}", animal_present="no", scene_group="s") for i in range(20))
    manifest = _manifest(always_missed + always_found + negatives)
    detections = {frame.frame_id: () for frame in always_missed}
    detections.update({frame.frame_id: (_det(frame.frame_id, box, 0.6),) for frame in always_found})
    detections.update({frame.frame_id: () for frame in negatives})

    thresholds = effective_threshold_grid(0.1, DEFAULT_THRESHOLD_GRID)
    sweep = sweep_thresholds(manifest, detections, thresholds, configured_threshold=0.1)
    static_report = cluster_static_false_positives(manifest, detections, threshold=0.1)
    temporal = simulate_temporal_policies(manifest, detections, threshold=0.1)
    configured_row = next(row for row in sweep if row.is_configured_threshold)
    preprocessing = compare_preprocessing(configured_row, None, primary_resize_mode="letterbox", alternative_resize_mode=None, unsupported_reason="fixture")
    sufficiency = classify_sample_sufficiency(manifest)

    # Best achievable recall (12 of 24) clears a naive 0.5 bound...
    best_recall = max(row.recall for row in sweep if row.recall is not None)
    assert best_recall == 0.5

    recommendations = classify_recommendations(
        sweep=sweep, static_report=static_report, temporal_results=temporal,
        preprocessing=preprocessing, sufficiency=sufficiency,
    )

    replacement = next(item for item in recommendations if item.action == "detector_replacement_evaluation")
    assert replacement.verdict == "needed"
    assert any("never observed by the detector" in metric for metric in replacement.supporting_metrics)


def test_unsupported_preprocessing_alternative_is_reported_honestly() -> None:
    comparison = compare_preprocessing(
        None, None, primary_resize_mode="letterbox", alternative_resize_mode=None,
        unsupported_reason="fixed 1280x1280 export has no valid alternative input size",
    )
    assert comparison.supported is False
    assert comparison.unsupported_reason


# --------------------------------------------------------------------------
# 15. Stable semantic fingerprint
# --------------------------------------------------------------------------


def _full_report(manifest: CalibrationManifest, detections: dict[str, tuple[DetectionObservation, ...]]) -> dict[str, object]:
    thresholds = effective_threshold_grid(0.1, DEFAULT_THRESHOLD_GRID)
    sweep = sweep_thresholds(manifest, detections, thresholds, configured_threshold=0.1)
    static_report = cluster_static_false_positives(manifest, detections, threshold=0.1)
    temporal = simulate_temporal_policies(manifest, detections, threshold=0.1)
    configured_row = next(row for row in sweep if row.is_configured_threshold)
    preprocessing = compare_preprocessing(
        configured_row, None, primary_resize_mode="letterbox", alternative_resize_mode=None,
        unsupported_reason="fixture",
    )
    sufficiency = classify_sample_sufficiency(manifest)
    recommendations = classify_recommendations(
        sweep=sweep, static_report=static_report, temporal_results=temporal,
        preprocessing=preprocessing, sufficiency=sufficiency,
    )
    return build_semantic_report(
        manifest=manifest, configured_threshold=0.1, thresholds=thresholds, sweep=sweep,
        static_report=static_report, temporal_results=temporal, preprocessing=preprocessing,
        sufficiency=sufficiency, recommendations=recommendations,
        provider={"provider_key": "onnx-cuda", "provider_version": "fixture"},
    )


def _sample_manifest_and_detections() -> tuple[CalibrationManifest, dict[str, tuple[DetectionObservation, ...]]]:
    positive = _frame("bird-fp", animal_present="yes", boxes=(ReviewedBox((0.4, 0.4, 0.6, 0.6)),), scene_group="scene-a")
    negative = _frame("empty-fp", animal_present="no", scene_group="scene-a")
    manifest = _manifest((positive, negative))
    detections = {
        "bird-fp": (_det("bird-fp", (0.41, 0.41, 0.59, 0.59), 0.6),),
        "empty-fp": (_det("empty-fp", (0.1, 0.1, 0.2, 0.2), 0.15),),
    }
    return manifest, detections


def test_semantic_fingerprint_is_stable_across_independent_runs() -> None:
    manifest, detections = _sample_manifest_and_detections()

    first = _full_report(manifest, detections)
    second = _full_report(manifest, detections)

    assert first["semantic_fingerprint"] == second["semantic_fingerprint"]
    assert first == second


# --------------------------------------------------------------------------
# 16. Absolute paths and runtime latency remain non-semantic
# --------------------------------------------------------------------------


def test_semantic_report_never_contains_an_absolute_path() -> None:
    manifest, detections = _sample_manifest_and_detections()
    report = _full_report(manifest, detections)

    import json
    serialized = json.dumps(report)
    assert "/home/" not in serialized
    assert "/tmp/" not in serialized


def test_semantic_report_has_no_latency_or_duration_fields() -> None:
    manifest, detections = _sample_manifest_and_detections()
    report = _full_report(manifest, detections)

    import json
    serialized = json.dumps(report).lower()
    for token in ("latency", "duration_ms", "wall_clock", "elapsed"):
        assert token not in serialized


# --------------------------------------------------------------------------
# 17. No product repository or truth-write dependency
# --------------------------------------------------------------------------


def test_module_source_has_no_product_repository_or_truth_imports() -> None:
    from pathlib import Path

    for name in ("detector_benchmark.py", "detector_benchmark_io.py", "detector_benchmark_cli.py"):
        source = Path(f"src/mockingbird/observation/{name}").read_text(encoding="utf-8")
        forbidden = (
            "mockingbird.db", "mockingbird.repositories", "sqlite3", "ReviewLabel",
            "MotionEvidence", "monitoring_policy", "Event(", "Visit(",
        )
        for token in forbidden:
            assert token not in source, f"{name} unexpectedly references {token}"


def test_report_always_declares_shadow_only_and_no_truth() -> None:
    manifest, detections = _sample_manifest_and_detections()
    report = _full_report(manifest, detections)

    assert report["creates_truth"] is False
    assert report["shadow_only"] is True
    assert report["production_proposal_authority"] is False


# --------------------------------------------------------------------------
# 19. No automatic threshold or Ignore-region mutation
# --------------------------------------------------------------------------


def test_recommendations_never_carry_production_authority() -> None:
    manifest, detections = _sample_manifest_and_detections()
    thresholds = effective_threshold_grid(0.1, DEFAULT_THRESHOLD_GRID)
    sweep = sweep_thresholds(manifest, detections, thresholds, configured_threshold=0.1)
    static_report = cluster_static_false_positives(manifest, detections, threshold=0.1)
    temporal = simulate_temporal_policies(manifest, detections, threshold=0.1)
    configured_row = next(row for row in sweep if row.is_configured_threshold)
    preprocessing = compare_preprocessing(configured_row, None, primary_resize_mode="letterbox", alternative_resize_mode=None, unsupported_reason="fixture")
    sufficiency = classify_sample_sufficiency(manifest)

    recommendations = classify_recommendations(
        sweep=sweep, static_report=static_report, temporal_results=temporal,
        preprocessing=preprocessing, sufficiency=sufficiency,
    )

    assert len(recommendations) == 7
    for recommendation in recommendations:
        assert recommendation.safe_for_production_authority is False


def test_clustering_never_mutates_manifest_or_creates_ignore_regions() -> None:
    frames = tuple(_frame(f"scene-c-{i}", animal_present="no", scene_group="scene-c") for i in range(3))
    manifest = _manifest(frames)
    box = (0.45, 0.45, 0.50, 0.50)
    detections = {frame.frame_id: (_det(frame.frame_id, box, 0.2),) for frame in frames}

    before = manifest.fingerprint
    cluster_static_false_positives(manifest, detections, threshold=0.1)
    after = manifest.fingerprint

    assert before == after
    for frame in manifest.frames:
        assert frame.privacy_ignore_regions == ()


# --------------------------------------------------------------------------
# 20. Bounded report and candidate counts
# --------------------------------------------------------------------------


def test_frame_box_count_is_bounded() -> None:
    from mockingbird.observation.detector_benchmark import MAX_BOXES_PER_FRAME

    too_many = tuple(ReviewedBox((0.0, 0.0, 0.01, 0.01)) for _ in range(MAX_BOXES_PER_FRAME + 1))
    with pytest.raises(DetectorBenchmarkError):
        CalibrationFrame(
            frame_id="too-many", image_path="images/x.jpg", content_hash="a" * 64,
            width=10, height=10, animal_present="yes", boxes=too_many,
        )


def test_manifest_frame_count_is_bounded() -> None:
    with pytest.raises(DetectorBenchmarkError):
        CalibrationManifest(1, "cohort", "policy", ())


def test_duplicate_frame_id_is_rejected() -> None:
    with pytest.raises(DetectorBenchmarkError):
        _manifest((_frame("dup"), _frame("dup")))


def test_threshold_grid_size_is_bounded() -> None:
    from mockingbird.observation.detector_benchmark import MAX_THRESHOLDS

    huge_grid = tuple(round(value, 4) for value in [i / 1000 for i in range(1, MAX_THRESHOLDS + 20)])
    with pytest.raises(DetectorBenchmarkError):
        effective_threshold_grid(0.1, huge_grid)


# --------------------------------------------------------------------------
# Manifest/box validation odds and ends
# --------------------------------------------------------------------------


def test_invalid_box_coordinates_are_rejected() -> None:
    with pytest.raises(DetectorBenchmarkError):
        ReviewedBox((0.6, 0.6, 0.4, 0.4))  # right < left


def test_invalid_privacy_region_is_rejected() -> None:
    with pytest.raises(DetectorBenchmarkError):
        _frame("bad-privacy", privacy_ignore_regions=((1.5, 0.0, 2.0, 1.0),))


def test_unsupported_manifest_version_is_rejected() -> None:
    with pytest.raises(DetectorBenchmarkError):
        CalibrationManifest(2, "cohort", "policy", (_frame("x"),))
