"""Hardware-free tests for the Stage 6.4 multi-scale strategy geometry.

All detections here are synthetic (`DetectionObservation` built directly);
no ONNX Runtime, CUDA, camera, or product database is touched. Numbered
sections mirror the task's required-test list.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

import pytest

from mockingbird.observation.contracts import DetectionObservation
from mockingbird.observation.multi_scale_strategy import (
    FULL_FRAME_PLUS_UNIFORM_TILES,
    MultiScaleStrategyConfig,
    MultiScaleStrategyError,
    StrategyWindow,
    WindowedDetection,
    map_window_box_to_source,
    normalize_window_detections,
    remap_regions_to_window,
    suppress_cross_window_duplicates,
    windows_for_frame,
)


def _det(obs_id: str, box: tuple[float, float, float, float] | None, score: float, *, label: str = "animal") -> DetectionObservation:
    return DetectionObservation(
        detector_id="fixture", label=label, confidence=score, captured_at=datetime(2026, 8, 5, tzinfo=UTC),
        observation_id=obs_id, frame_id="f1", provider_id="onnx-cuda", model_key="fixture",
        generation_id="g", bounding_box=box, class_source_label="0" if label == "animal" else "1",
        is_animal=label == "animal",
    )


# --------------------------------------------------------------------------
# 1. Deterministic uniform tile generation
# --------------------------------------------------------------------------


def test_deterministic_uniform_tile_generation() -> None:
    first = windows_for_frame(FULL_FRAME_PLUS_UNIFORM_TILES, source_width=3840, source_height=2160)
    second = windows_for_frame(FULL_FRAME_PLUS_UNIFORM_TILES, source_width=3840, source_height=2160)

    assert first == second


# --------------------------------------------------------------------------
# 2. Tile bounds cover the intended source area
# --------------------------------------------------------------------------


def test_tile_bounds_cover_the_full_source_area() -> None:
    windows = windows_for_frame(FULL_FRAME_PLUS_UNIFORM_TILES, source_width=3840, source_height=2160)
    tiles = [window for window in windows if window.window_kind == "tile"]

    assert tiles
    assert min(tile.source_box[0] for tile in tiles) == 0.0
    assert min(tile.source_box[1] for tile in tiles) == 0.0
    assert max(tile.source_box[2] for tile in tiles) == 1.0
    assert max(tile.source_box[3] for tile in tiles) == 1.0


def test_small_source_frame_degrades_to_full_frame_only() -> None:
    # Below FULL_FRAME_PLUS_UNIFORM_TILES.min_source_width/height: tiling is
    # skipped entirely rather than upsampling a too-small source.
    windows = windows_for_frame(FULL_FRAME_PLUS_UNIFORM_TILES, source_width=640, source_height=480)

    assert len(windows) == 1
    assert windows[0].window_kind == "full_frame"


# --------------------------------------------------------------------------
# 3. Maximum tile count is enforced
# --------------------------------------------------------------------------


def test_maximum_tile_count_is_enforced() -> None:
    tiny_tiles_huge_frame = replace(FULL_FRAME_PLUS_UNIFORM_TILES, tile_width=32, tile_height=32, max_tiles_per_frame=9)

    windows = windows_for_frame(tiny_tiles_huge_frame, source_width=8000, source_height=8000)

    tile_count = sum(1 for window in windows if window.window_kind == "tile")
    assert tile_count <= 9


def test_maximum_tile_count_enforced_across_many_frame_sizes() -> None:
    strategy = replace(FULL_FRAME_PLUS_UNIFORM_TILES, tile_width=64, tile_height=64, max_tiles_per_frame=16, min_source_width=64, min_source_height=64)
    for width, height in ((500, 500), (1920, 1080), (4000, 6000), (10000, 200)):
        windows = windows_for_frame(strategy, source_width=width, source_height=height)
        tile_count = sum(1 for window in windows if window.window_kind == "tile")
        assert tile_count <= 16, f"{width}x{height} produced {tile_count} tiles"


def test_invalid_max_tiles_per_frame_is_rejected() -> None:
    with pytest.raises(MultiScaleStrategyError):
        replace(FULL_FRAME_PLUS_UNIFORM_TILES, max_tiles_per_frame=0)


# --------------------------------------------------------------------------
# 4. Source-coordinate round trip
# --------------------------------------------------------------------------


def test_source_coordinate_round_trip() -> None:
    window = StrategyWindow("tile-r0-c1", "tile", (0.5, 0.0, 1.0, 0.5))

    mapped = map_window_box_to_source(window, (0.2, 0.2, 0.8, 0.8))

    # local (0.2..0.8) inside a window spanning source (0.5..1.0) -> source (0.6..0.9)
    assert mapped == (0.6, 0.1, 0.9, 0.4)


def test_full_frame_window_is_an_identity_mapping() -> None:
    window = StrategyWindow("full_frame", "full_frame", (0.0, 0.0, 1.0, 1.0))

    mapped = map_window_box_to_source(window, (0.25, 0.3, 0.75, 0.9))

    assert mapped == (0.25, 0.3, 0.75, 0.9)


def test_source_box_is_clipped_to_unit_range() -> None:
    window = StrategyWindow("tile-r0-c0", "tile", (0.9, 0.9, 1.0, 1.0))

    mapped = map_window_box_to_source(window, (0.5, 0.5, 1.5, 1.5))

    assert all(0.0 <= value <= 1.0 for value in mapped)


# --------------------------------------------------------------------------
# 5. Full-frame and tile detections normalize consistently
# --------------------------------------------------------------------------


def test_full_frame_and_tile_detections_normalize_consistently() -> None:
    full_frame = StrategyWindow("full_frame", "full_frame", (0.0, 0.0, 1.0, 1.0))
    tile = StrategyWindow("tile-r0-c0", "tile", (0.0, 0.0, 0.5, 0.5))

    # The same physical source region (0.1..0.2) expressed once as a
    # full-frame-local box and once as a tile-local box (tile spans 0..0.5,
    # so 0.1..0.2 in source is 0.2..0.4 in tile-local space).
    from_full_frame = normalize_window_detections(full_frame, (_det("a", (0.1, 0.1, 0.2, 0.2), 0.5),))
    from_tile = normalize_window_detections(tile, (_det("b", (0.2, 0.2, 0.4, 0.4), 0.5),))

    assert from_full_frame[0].detection.bounding_box == (0.1, 0.1, 0.2, 0.2)
    assert from_tile[0].detection.bounding_box == (0.1, 0.1, 0.2, 0.2)


def test_normalize_drops_detections_without_a_box() -> None:
    window = StrategyWindow("full_frame", "full_frame", (0.0, 0.0, 1.0, 1.0))

    normalized = normalize_window_detections(window, (_det("a", None, 0.5),))

    assert normalized == ()


# --------------------------------------------------------------------------
# 6. Same animal from multiple windows collapses once
# --------------------------------------------------------------------------


def test_same_animal_from_multiple_windows_collapses_once() -> None:
    full_frame = StrategyWindow("full_frame", "full_frame", (0.0, 0.0, 1.0, 1.0))
    tile = StrategyWindow("tile-r0-c0", "tile", (0.0, 0.0, 0.5, 0.5))
    same_animal = (
        WindowedDetection(_det("a", (0.10, 0.10, 0.20, 0.20), 0.6), full_frame, (0.10, 0.10, 0.20, 0.20)),
        WindowedDetection(_det("b", (0.11, 0.11, 0.19, 0.19), 0.8), tile, (0.22, 0.22, 0.38, 0.38)),
    )

    kept, suppressed = suppress_cross_window_duplicates(same_animal, iou_threshold=0.5, max_final_detections=300)

    assert len(kept) == 1
    assert kept[0].detection.observation_id == "b"  # higher score wins
    assert [item.detection.observation_id for item in suppressed] == ["a"]


# --------------------------------------------------------------------------
# 7. Distinct nearby animals remain separate
# --------------------------------------------------------------------------


def test_distinct_nearby_animals_remain_separate() -> None:
    tile = StrategyWindow("tile-r0-c0", "tile", (0.0, 0.0, 0.5, 0.5))
    distinct = (
        WindowedDetection(_det("a", (0.10, 0.10, 0.15, 0.15), 0.7), tile, (0.2, 0.2, 0.3, 0.3)),
        WindowedDetection(_det("b", (0.30, 0.30, 0.35, 0.35), 0.7), tile, (0.6, 0.6, 0.7, 0.7)),
    )

    kept, suppressed = suppress_cross_window_duplicates(distinct, iou_threshold=0.5, max_final_detections=300)

    assert len(kept) == 2
    assert suppressed == ()


def test_distinct_broad_classes_do_not_suppress_each_other() -> None:
    tile = StrategyWindow("tile-r0-c0", "tile", (0.0, 0.0, 0.5, 0.5))
    overlapping_different_classes = (
        WindowedDetection(_det("a", (0.10, 0.10, 0.20, 0.20), 0.7, label="animal"), tile, (0.2, 0.2, 0.4, 0.4)),
        WindowedDetection(_det("b", (0.10, 0.10, 0.20, 0.20), 0.7, label="vehicle"), tile, (0.2, 0.2, 0.4, 0.4)),
    )

    kept, suppressed = suppress_cross_window_duplicates(overlapping_different_classes, iou_threshold=0.5, max_final_detections=300)

    assert len(kept) == 2
    assert suppressed == ()


# --------------------------------------------------------------------------
# 8. Tile-border detection is retained
# --------------------------------------------------------------------------


def test_tile_border_detection_is_retained_not_dropped() -> None:
    tile = StrategyWindow("tile-r0-c0", "tile", (0.0, 0.0, 0.5, 0.5))
    edge_local_box = (0.85, 0.40, 0.99, 0.60)
    border = WindowedDetection(_det("a", map_window_box_to_source(tile, edge_local_box), 0.6), tile, edge_local_box)

    assert border.touches_window_edge is True

    kept, suppressed = suppress_cross_window_duplicates((border,), iou_threshold=0.5, max_final_detections=300)

    assert kept == (border,)
    assert suppressed == ()


def test_interior_detection_does_not_touch_window_edge() -> None:
    tile = StrategyWindow("tile-r0-c0", "tile", (0.0, 0.0, 0.5, 0.5))
    interior = WindowedDetection(_det("a", (0.4, 0.4, 0.5, 0.5), 0.6), tile, (0.4, 0.4, 0.5, 0.5))

    assert interior.touches_window_edge is False


def test_full_frame_window_never_touches_edge() -> None:
    full_frame = StrategyWindow("full_frame", "full_frame", (0.0, 0.0, 1.0, 1.0))
    at_the_edge = WindowedDetection(_det("a", (0.0, 0.0, 0.01, 0.01), 0.6), full_frame, (0.0, 0.0, 0.01, 0.01))

    assert at_the_edge.touches_window_edge is False


# --------------------------------------------------------------------------
# 9. Input ordering does not affect output
# --------------------------------------------------------------------------


def test_input_ordering_does_not_affect_suppression_output() -> None:
    full_frame = StrategyWindow("full_frame", "full_frame", (0.0, 0.0, 1.0, 1.0))
    tile = StrategyWindow("tile-r0-c0", "tile", (0.0, 0.0, 0.5, 0.5))
    items = (
        WindowedDetection(_det("a", (0.10, 0.10, 0.20, 0.20), 0.6), full_frame, (0.10, 0.10, 0.20, 0.20)),
        WindowedDetection(_det("b", (0.11, 0.11, 0.19, 0.19), 0.8), tile, (0.22, 0.22, 0.38, 0.38)),
        WindowedDetection(_det("c", (0.60, 0.60, 0.70, 0.70), 0.5), full_frame, (0.60, 0.60, 0.70, 0.70)),
    )

    forward_kept, forward_suppressed = suppress_cross_window_duplicates(items, iou_threshold=0.5, max_final_detections=300)
    backward_kept, backward_suppressed = suppress_cross_window_duplicates(tuple(reversed(items)), iou_threshold=0.5, max_final_detections=300)

    assert forward_kept == backward_kept
    assert forward_suppressed == backward_suppressed


# --------------------------------------------------------------------------
# 10. Observation IDs are deterministic
# --------------------------------------------------------------------------


def test_observation_ids_survive_normalization_and_suppression_deterministically() -> None:
    tile = StrategyWindow("tile-r0-c0", "tile", (0.0, 0.0, 0.5, 0.5))

    first_run = normalize_window_detections(tile, (_det("stable-id", (0.2, 0.2, 0.4, 0.4), 0.6),))
    second_run = normalize_window_detections(tile, (_det("stable-id", (0.2, 0.2, 0.4, 0.4), 0.6),))

    assert first_run[0].detection.observation_id == "stable-id"
    assert first_run[0].detection.observation_id == second_run[0].detection.observation_id


# --------------------------------------------------------------------------
# 17. Privacy/Ignore masking applies before each inference window
# --------------------------------------------------------------------------


def test_privacy_region_remaps_into_overlapping_tile_local_space() -> None:
    tile = StrategyWindow("tile-r0-c1", "tile", (0.5, 0.0, 1.0, 0.5))
    source_privacy_region = (0.0, 0.0, 0.6, 1.0)

    remapped = remap_regions_to_window(tile, (source_privacy_region,))

    assert remapped == ((0.0, 0.0, 0.2, 1.0),)


def test_privacy_region_outside_window_is_dropped() -> None:
    tile = StrategyWindow("tile-r0-c1", "tile", (0.5, 0.0, 1.0, 0.5))
    unrelated_region = (0.0, 0.6, 0.2, 0.9)

    remapped = remap_regions_to_window(tile, (unrelated_region,))

    assert remapped == ()


def test_privacy_region_fully_covering_tile_masks_the_whole_window() -> None:
    tile = StrategyWindow("tile-r0-c0", "tile", (0.2, 0.2, 0.4, 0.4))
    covering_region = (0.0, 0.0, 1.0, 1.0)

    remapped = remap_regions_to_window(tile, (covering_region,))

    assert remapped == ((0.0, 0.0, 1.0, 1.0),)


def test_full_frame_window_privacy_regions_are_unchanged() -> None:
    full_frame = StrategyWindow("full_frame", "full_frame", (0.0, 0.0, 1.0, 1.0))
    region = (0.1, 0.1, 0.3, 0.3)

    remapped = remap_regions_to_window(full_frame, (region,))

    assert remapped == (region,)


# --------------------------------------------------------------------------
# 22. All counts and temporary buffers remain bounded
# --------------------------------------------------------------------------


def test_max_final_detections_bounds_kept_results() -> None:
    tile = StrategyWindow("tile-r0-c0", "tile", (0.0, 0.0, 1.0, 1.0))
    many_distinct = tuple(
        WindowedDetection(_det(f"d{i}", (i * 0.01, i * 0.01, i * 0.01 + 0.005, i * 0.01 + 0.005), 0.9 - i * 0.001), tile, (0.0, 0.0, 0.005, 0.005))
        for i in range(20)
    )

    kept, suppressed = suppress_cross_window_duplicates(many_distinct, iou_threshold=0.5, max_final_detections=5)

    assert len(kept) == 5
    assert len(suppressed) == 15


def test_strategy_config_rejects_out_of_bound_fields() -> None:
    with pytest.raises(MultiScaleStrategyError):
        replace(FULL_FRAME_PLUS_UNIFORM_TILES, horizontal_overlap=1.0)
    with pytest.raises(MultiScaleStrategyError):
        replace(FULL_FRAME_PLUS_UNIFORM_TILES, per_window_score_threshold=0.0)
    with pytest.raises(MultiScaleStrategyError):
        replace(FULL_FRAME_PLUS_UNIFORM_TILES, tile_width=8)


def test_strategy_producing_zero_windows_is_rejected() -> None:
    with pytest.raises(MultiScaleStrategyError):
        MultiScaleStrategyConfig(
            strategy_key="empty", strategy_version="v1", full_frame_enabled=False, tile_width=None, tile_height=None,
            horizontal_overlap=0.0, vertical_overlap=0.0, max_tiles_per_frame=1, min_source_width=1, min_source_height=1,
            tile_selection_method="none", edge_padding_behavior="clip_to_source_bounds",
            per_window_preprocessing="n/a", per_window_score_threshold=0.1, cross_window_iou_threshold=0.5,
            duplicate_suppression_rule="n/a", max_final_detections=10, resource_bounds="n/a", limitations=(),
        )


def test_window_count_never_exceeds_configured_max_windows_per_frame() -> None:
    windows = windows_for_frame(FULL_FRAME_PLUS_UNIFORM_TILES, source_width=7680, source_height=4320)

    assert len(windows) <= FULL_FRAME_PLUS_UNIFORM_TILES.max_windows_per_frame


# --------------------------------------------------------------------------
# No product repository dependency / no truth-write path
# --------------------------------------------------------------------------


def test_module_source_has_no_product_repository_or_truth_imports() -> None:
    from pathlib import Path

    for name in ("multi_scale_strategy.py",):
        source = Path(f"src/mockingbird/observation/{name}").read_text(encoding="utf-8")
        forbidden = (
            "mockingbird.db", "mockingbird.repositories", "sqlite3", "ReviewLabel",
            "MotionEvidence", "monitoring_policy", "Event(", "Visit(", "import requests",
            "urllib", "socket", "onnxruntime", "import cv2",
        )
        for token in forbidden:
            assert token not in source, f"{name} unexpectedly references {token}"
