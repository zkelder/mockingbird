"""Provider-neutral multi-scale inference-window strategy geometry.

Observation Engine v2 Stage 6.4. This module is pure: no model inference, no
filesystem I/O, no CUDA/ONNX Runtime import, and no scene-specific (Zone,
camera, or "this yard") coordinates. It only computes deterministic
inference-window geometry from a frame's own source dimensions, maps
per-window detections back into source-frame normalized coordinates, and
performs deterministic cross-window duplicate suppression. Actually running
a detector provider once per window is the caller's job (see
`multi_scale_benchmark_io`/`multi_scale_cli`); this module never imports a
provider. See docs/multi-scale-detector-benchmark-contract.md.

Some geometry here (uniform-grid tiling, same-class IoU collapse) continues
the general, non-scene-specific parts of the pre-existing local
`mockingbird.detectors.small_bird_benchmark` probe. That module's
`aspect_preserving_zone_jpeg`/`run_strategy` are deliberately not reused:
they are coupled to the separate official-package `megadetector_adapter`
byte-input runner, not the ONNX Runtime CUDA provider this benchmark uses.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
import math
from typing import Literal

from mockingbird.observation.contracts import DetectionObservation

TILE_SELECTION_UNIFORM_GRID = "uniform_grid"
EDGE_PADDING_CLIP_TO_SOURCE_BOUNDS = "clip_to_source_bounds"

# Box coordinates round to 4 decimals and confidence to 3, matching the
# existing MDv5 raw decoder's committed quantization convention (see
# onnx-cuda-shadow-provider-contract.md) so multi-scale output is directly
# comparable to single-pass detector-benchmark output.
BOX_COORDINATE_DECIMALS = 4
SCORE_DECIMALS = 3

MAX_TILES_PER_FRAME_LIMIT = 64


class MultiScaleStrategyError(ValueError):
    """A bounded multi-scale strategy validation or execution failure code."""


# --------------------------------------------------------------------------
# Strategy configuration contract
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class MultiScaleStrategyConfig:
    """The explicit, provider-neutral multi-scale strategy contract.

    Deliberately carries no CUDA, ONNX Runtime, or model-specific class or
    value -- `per_window_preprocessing` is a descriptive fact ("reuse the
    configured detector provider's own preprocessing contract unchanged"),
    not a live provider reference. Each field mirrors one bullet of the
    Stage 6.4 strategy contract."""

    strategy_key: str
    strategy_version: str
    full_frame_enabled: bool
    tile_width: int | None
    tile_height: int | None
    horizontal_overlap: float
    vertical_overlap: float
    max_tiles_per_frame: int
    min_source_width: int
    min_source_height: int
    tile_selection_method: str
    edge_padding_behavior: str
    per_window_preprocessing: str
    per_window_score_threshold: float
    cross_window_iou_threshold: float
    duplicate_suppression_rule: str
    max_final_detections: int
    resource_bounds: str
    limitations: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.strategy_key or len(self.strategy_key) > 128:
            raise MultiScaleStrategyError("invalid_strategy_key")
        if not self.strategy_version:
            raise MultiScaleStrategyError("invalid_strategy_version")
        if not self.full_frame_enabled and self.tile_width is None:
            # A strategy that runs neither the full frame nor any tile would
            # produce zero windows for every frame; refuse to construct it.
            raise MultiScaleStrategyError("strategy_produces_no_windows")
        if self.tile_width is not None and (self.tile_width < 32 or self.tile_height is None or self.tile_height < 32):
            raise MultiScaleStrategyError("invalid_tile_dimensions")
        if not (0.0 <= self.horizontal_overlap < 1.0) or not (0.0 <= self.vertical_overlap < 1.0):
            raise MultiScaleStrategyError("invalid_overlap")
        if not 1 <= self.max_tiles_per_frame <= MAX_TILES_PER_FRAME_LIMIT:
            raise MultiScaleStrategyError("invalid_max_tiles_per_frame")
        if self.min_source_width < 1 or self.min_source_height < 1:
            raise MultiScaleStrategyError("invalid_min_source_dimensions")
        if not 0.0 < self.per_window_score_threshold <= 1.0:
            raise MultiScaleStrategyError("invalid_per_window_score_threshold")
        if not 0.0 < self.cross_window_iou_threshold < 1.0:
            raise MultiScaleStrategyError("invalid_cross_window_iou_threshold")
        if not 1 <= self.max_final_detections <= 1000:
            raise MultiScaleStrategyError("invalid_max_final_detections")

    @property
    def max_windows_per_frame(self) -> int:
        """The hard per-frame resource bound: every tile plus the optional
        full-frame pass."""

        tiles = self.max_tiles_per_frame if self.tile_width is not None else 0
        return tiles + (1 if self.full_frame_enabled else 0)


FULL_FRAME = MultiScaleStrategyConfig(
    strategy_key="full_frame",
    strategy_version="multi-scale-strategy-v1",
    full_frame_enabled=True,
    tile_width=None,
    tile_height=None,
    horizontal_overlap=0.0,
    vertical_overlap=0.0,
    max_tiles_per_frame=1,
    min_source_width=1,
    min_source_height=1,
    tile_selection_method="none",
    edge_padding_behavior=EDGE_PADDING_CLIP_TO_SOURCE_BOUNDS,
    per_window_preprocessing="reuses the configured detector provider's own preprocessing contract unchanged",
    per_window_score_threshold=0.1,
    cross_window_iou_threshold=0.5,
    duplicate_suppression_rule="not applicable: exactly one window per frame",
    max_final_detections=300,
    resource_bounds="exactly one inference call per frame",
    limitations=(
        "current production baseline: single full-frame inference pass",
        "a small or distant subject may be reduced below detectable size by the model's fixed input resolution",
    ),
)

FULL_FRAME_PLUS_UNIFORM_TILES = MultiScaleStrategyConfig(
    strategy_key="full_frame_plus_uniform_tiles",
    strategy_version="multi-scale-strategy-v1",
    full_frame_enabled=True,
    tile_width=640,
    tile_height=640,
    horizontal_overlap=0.20,
    vertical_overlap=0.20,
    max_tiles_per_frame=9,
    min_source_width=960,
    min_source_height=960,
    tile_selection_method=TILE_SELECTION_UNIFORM_GRID,
    edge_padding_behavior=EDGE_PADDING_CLIP_TO_SOURCE_BOUNDS,
    per_window_preprocessing="reuses the configured detector provider's own preprocessing contract unchanged",
    per_window_score_threshold=0.1,
    cross_window_iou_threshold=0.5,
    duplicate_suppression_rule=(
        "same-broad-class IoU >= cross_window_iou_threshold collapses to the higher-scored "
        "detection, stable tiebreak on source box then observation id"
    ),
    max_final_detections=300,
    resource_bounds="at most max_windows_per_frame inference calls per frame (uniform grid capped at max_tiles_per_frame, plus one full-frame pass)",
    limitations=(
        "uniform grid only; no content-aware or saliency-driven tile placement",
        "frames smaller than min_source_width/min_source_height run full-frame only (tiling degrades gracefully rather than upsampling)",
        "a tile grid capped by max_tiles_per_frame may realize larger tiles than the requested tile_width/tile_height on very large source frames",
    ),
)

STRATEGIES = (FULL_FRAME, FULL_FRAME_PLUS_UNIFORM_TILES)


# --------------------------------------------------------------------------
# Window generation (source dimensions only; no scene-specific coordinates)
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class StrategyWindow:
    """One inference window in the source frame's own normalized space."""

    window_id: str
    window_kind: Literal["full_frame", "tile"]
    source_box: tuple[float, float, float, float]
    row: int | None = None
    column: int | None = None

    def __post_init__(self) -> None:
        left, top, right, bottom = self.source_box
        if not (0.0 <= left < right <= 1.0) or not (0.0 <= top < bottom <= 1.0):
            raise MultiScaleStrategyError("invalid_window_box")


def _axis_tile_count(tile_fraction: float, overlap: float) -> int:
    """How many tiles of normalized size `tile_fraction` (with `overlap`
    fractional overlap) are needed to fully cover one axis of length 1.0."""

    if tile_fraction >= 1.0:
        return 1
    step = tile_fraction * (1.0 - overlap)
    if step <= 0.0:
        return 1
    return 1 + math.ceil((1.0 - tile_fraction) / step)


def _bounded_axis_counts(
    *, tile_width_fraction: float, tile_height_fraction: float,
    horizontal_overlap: float, vertical_overlap: float, max_tiles_per_frame: int,
) -> tuple[int, int]:
    """Deterministically cap (columns, rows) so `columns * rows` never
    exceeds `max_tiles_per_frame`, capping each axis independently at
    `isqrt(max_tiles_per_frame)`: `isqrt(n) ** 2 <= n` always, so the bound
    is mathematically guaranteed regardless of source aspect ratio."""

    columns = _axis_tile_count(tile_width_fraction, horizontal_overlap)
    rows = _axis_tile_count(tile_height_fraction, vertical_overlap)
    per_axis_cap = max(1, math.isqrt(max_tiles_per_frame))
    return min(columns, per_axis_cap), min(rows, per_axis_cap)


def _uniform_tile_boxes(
    *, columns: int, rows: int, horizontal_overlap: float, vertical_overlap: float,
) -> tuple[tuple[float, float, float, float, int, int], ...]:
    """A deterministic, full-coverage uniform grid over the unit square.

    Reuses the exact tiling formula the preserved local small-bird
    tiling probe already validated (`tiled_coordinate_boxes`): tile size is
    derived from the column/row count so the grid's union is always exactly
    [0,1] x [0,1], with the last row/column snapped to the far edge rather
    than left short by rounding."""

    tile_width = 1.0 / (columns - (columns - 1) * horizontal_overlap) if columns > 1 else 1.0
    tile_height = 1.0 / (rows - (rows - 1) * vertical_overlap) if rows > 1 else 1.0
    step_x = tile_width * (1.0 - horizontal_overlap)
    step_y = tile_height * (1.0 - vertical_overlap)
    boxes: list[tuple[float, float, float, float, int, int]] = []
    for row in range(rows):
        top = row * step_y
        bottom = 1.0 if row == rows - 1 else top + tile_height
        for column in range(columns):
            left = column * step_x
            right = 1.0 if column == columns - 1 else left + tile_width
            boxes.append((left, top, right, bottom, row, column))
    return tuple(boxes)


def windows_for_frame(
    config: MultiScaleStrategyConfig, *, source_width: int, source_height: int,
) -> tuple[StrategyWindow, ...]:
    """Deterministic, source-dimension-only window generation.

    Never reads a Zone, camera identity, or any per-scene coordinate --
    `source_width`/`source_height` are the only inputs besides the
    strategy's own configuration. Below `min_source_width`/
    `min_source_height`, tiling degrades gracefully to full-frame-only
    rather than upsampling a too-small source."""

    if source_width < 1 or source_height < 1:
        raise MultiScaleStrategyError("invalid_source_dimensions")

    windows: list[StrategyWindow] = []
    if config.full_frame_enabled:
        windows.append(StrategyWindow("full_frame", "full_frame", (0.0, 0.0, 1.0, 1.0)))

    if (
        config.tile_width is not None and config.tile_height is not None
        and source_width >= config.min_source_width and source_height >= config.min_source_height
    ):
        tile_width_fraction = min(1.0, config.tile_width / source_width)
        tile_height_fraction = min(1.0, config.tile_height / source_height)
        columns, rows = _bounded_axis_counts(
            tile_width_fraction=tile_width_fraction, tile_height_fraction=tile_height_fraction,
            horizontal_overlap=config.horizontal_overlap, vertical_overlap=config.vertical_overlap,
            max_tiles_per_frame=config.max_tiles_per_frame,
        )
        for left, top, right, bottom, row, column in _uniform_tile_boxes(
            columns=columns, rows=rows,
            horizontal_overlap=config.horizontal_overlap, vertical_overlap=config.vertical_overlap,
        ):
            windows.append(StrategyWindow(
                window_id=f"tile-r{row}-c{column}", window_kind="tile",
                source_box=(left, top, right, bottom), row=row, column=column,
            ))

    if len(windows) > config.max_windows_per_frame:
        raise MultiScaleStrategyError("window_count_exceeds_bound")  # pragma: no cover - guaranteed by _bounded_axis_counts
    return tuple(windows)


# --------------------------------------------------------------------------
# Coordinate normalization
# --------------------------------------------------------------------------


def _clip_unit(value: float) -> float:
    return min(1.0, max(0.0, value))


def map_window_box_to_source(
    window: StrategyWindow, window_local_box: tuple[float, float, float, float],
) -> tuple[float, float, float, float]:
    """Map a detection box from one window's own [0,1] local space into the
    source frame's normalized space, clipped and quantized to the committed
    4-decimal box convention."""

    left, top, right, bottom = window.source_box
    width, height = right - left, bottom - top
    x1, y1, x2, y2 = window_local_box
    mapped = (
        left + x1 * width, top + y1 * height,
        left + x2 * width, top + y2 * height,
    )
    return tuple(round(_clip_unit(value), BOX_COORDINATE_DECIMALS) for value in mapped)  # type: ignore[return-value]


def normalize_window_detections(
    window: StrategyWindow, window_local_detections: tuple[DetectionObservation, ...],
) -> tuple[WindowedDetection, ...]:
    """Map one window's already-decoded, already-thresholded detections
    (in that window's own local [0,1] space, exactly as the detector
    provider decoded them) into source-frame coordinates, tagged with
    window provenance. A detection without a box is dropped -- this
    benchmark is box-based throughout."""

    normalized = []
    for detection in window_local_detections:
        local_box = detection.bounding_box
        if local_box is None:
            continue
        source_box = map_window_box_to_source(window, local_box)
        quantized_confidence = round(detection.confidence or 0.0, SCORE_DECIMALS)
        remapped = replace(detection, bounding_box=source_box, confidence=quantized_confidence)
        normalized.append(WindowedDetection(remapped, window, local_box))
    return tuple(normalized)


def remap_regions_to_window(
    window: StrategyWindow, source_regions: tuple[tuple[float, float, float, float], ...],
) -> tuple[tuple[float, float, float, float], ...]:
    """Intersect and remap source-frame Privacy/Ignore regions into one
    window's own local [0,1] space, for masking before that window's own
    inference call. A region wholly outside the window is dropped; a region
    only partially inside the window is clipped to the window bounds first."""

    left, top, right, bottom = window.source_box
    width, height = right - left, bottom - top
    if width <= 0.0 or height <= 0.0:
        return ()
    remapped: list[tuple[float, float, float, float]] = []
    for region_left, region_top, region_right, region_bottom in source_regions:
        clipped_left, clipped_top = max(region_left, left), max(region_top, top)
        clipped_right, clipped_bottom = min(region_right, right), min(region_bottom, bottom)
        if clipped_left >= clipped_right or clipped_top >= clipped_bottom:
            continue
        remapped.append((
            round(_clip_unit((clipped_left - left) / width), BOX_COORDINATE_DECIMALS),
            round(_clip_unit((clipped_top - top) / height), BOX_COORDINATE_DECIMALS),
            round(_clip_unit((clipped_right - left) / width), BOX_COORDINATE_DECIMALS),
            round(_clip_unit((clipped_bottom - top) / height), BOX_COORDINATE_DECIMALS),
        ))
    return tuple(remapped)


# --------------------------------------------------------------------------
# Windowed detections and cross-window duplicate suppression
# --------------------------------------------------------------------------


EDGE_TOUCH_MARGIN = 0.02


@dataclass(frozen=True)
class WindowedDetection:
    """One detection already normalized into source-frame coordinates, with
    the window that produced it and its original window-local box retained
    as provenance (the local box is what lets a caller ask "did this
    detection touch the tile edge" without an inverse coordinate transform)."""

    detection: DetectionObservation
    window: StrategyWindow
    window_local_box: tuple[float, float, float, float]

    def __post_init__(self) -> None:
        if self.detection.bounding_box is None:
            raise MultiScaleStrategyError("windowed_detection_requires_box")

    @property
    def touches_window_edge(self) -> bool:
        """A tile-local box within `EDGE_TOUCH_MARGIN` of any tile edge may
        represent a subject split across tile boundaries; reported as a
        scale-specific fact, never used to suppress or alter a detection."""

        if self.window.window_kind != "tile":
            return False
        left, top, right, bottom = self.window_local_box
        return (
            left <= EDGE_TOUCH_MARGIN or top <= EDGE_TOUCH_MARGIN
            or right >= 1.0 - EDGE_TOUCH_MARGIN or bottom >= 1.0 - EDGE_TOUCH_MARGIN
        )


def _iou(first: tuple[float, float, float, float], second: tuple[float, float, float, float]) -> float:
    left, top = max(first[0], second[0]), max(first[1], second[1])
    right, bottom = min(first[2], second[2]), min(first[3], second[3])
    intersection = max(0.0, right - left) * max(0.0, bottom - top)
    first_area = (first[2] - first[0]) * (first[3] - first[1])
    second_area = (second[2] - second[0]) * (second[3] - second[1])
    union = first_area + second_area - intersection
    return 0.0 if union <= 0.0 else intersection / union


def _stable_order_key(item: WindowedDetection) -> tuple[object, ...]:
    """Frame sequence is caller context (per-frame grouping happens one
    level up); within one frame this key is: descending quantized score,
    broad class, normalized source-space box, strategy/window identity,
    stable observation id."""

    detection = item.detection
    score = round(detection.confidence or 0.0, SCORE_DECIMALS)
    return (
        -score, detection.label, detection.bounding_box or (0.0, 0.0, 0.0, 0.0),
        item.window.window_id, detection.observation_id or "",
    )


def suppress_cross_window_duplicates(
    detections: tuple[WindowedDetection, ...], *, iou_threshold: float, max_final_detections: int,
) -> tuple[tuple[WindowedDetection, ...], tuple[WindowedDetection, ...]]:
    """Deterministic same-broad-class greedy NMS across every window's
    already-source-remapped detections for one frame.

    Input order never affects the result: detections are sorted by the
    stable key first, so a later (lower- or equal-scored) box that overlaps
    an already-kept box is always the one suppressed, regardless of which
    window or input order produced either one. Two distinct, non-overlapping
    animals in neighboring or overlapping windows both survive; the same
    physical animal seen by two windows collapses to its single
    higher-scored observation. Bounded to `max_final_detections` kept
    results (excess lowest-priority detections move to the suppressed set,
    not silently dropped)."""

    ordered = sorted(detections, key=_stable_order_key)
    kept: list[WindowedDetection] = []
    suppressed: list[WindowedDetection] = []
    for candidate in ordered:
        candidate_box = candidate.detection.bounding_box
        assert candidate_box is not None
        is_duplicate = any(
            existing.detection.label == candidate.detection.label
            and _iou(candidate_box, existing.detection.bounding_box) >= iou_threshold  # type: ignore[arg-type]
            for existing in kept
        )
        if is_duplicate or len(kept) >= max_final_detections:
            suppressed.append(candidate)
        else:
            kept.append(candidate)
    return tuple(kept), tuple(suppressed)


__all__ = [
    "BOX_COORDINATE_DECIMALS",
    "EDGE_PADDING_CLIP_TO_SOURCE_BOUNDS",
    "EDGE_TOUCH_MARGIN",
    "FULL_FRAME",
    "FULL_FRAME_PLUS_UNIFORM_TILES",
    "MAX_TILES_PER_FRAME_LIMIT",
    "SCORE_DECIMALS",
    "STRATEGIES",
    "TILE_SELECTION_UNIFORM_GRID",
    "MultiScaleStrategyConfig",
    "MultiScaleStrategyError",
    "StrategyWindow",
    "WindowedDetection",
    "map_window_box_to_source",
    "normalize_window_detections",
    "remap_regions_to_window",
    "suppress_cross_window_duplicates",
    "windows_for_frame",
]
