"""Provider-neutral adaptive motion-proposal strategy geometry.

Observation Engine v2 Stage 6.5. This module is pure: no model inference, no
filesystem I/O, no CUDA/ONNX Runtime/OpenCV import, and no scene-specific
(Zone, camera, or "this yard") coordinate. It derives a small bounded number
of high-resolution inference windows from a *pair* of already-decoded,
already-downsampled grayscale frame planes (the same `FramePlane` convention
`mockingbird.motion.scoring`/`mockingbird.motion.activity_crop` already use --
a rectangular sequence-of-sequences of numeric grayscale values -- reused by
type only, not by importing product motion-evidence behavior). Decoding a
JPEG/PNG into a frame plane, and actually running a detector provider once
per window, are the caller's job (see `motion_proposal_io`/`motion_proposal_cli`);
this module never imports a provider and never touches a raw image file. See
docs/adaptive-motion-proposal-benchmark-contract.md.

Finalized proposal windows are emitted as `multi_scale_strategy.StrategyWindow`
so the existing Stage 6.4 window-merge, cross-window-duplicate-suppression,
and report-assembly pipeline can be reused unchanged (see
`motion_proposal_benchmark.py`); a motion proposal is geometrically identical
to a "tile" window once it has a source-normalized box, it is simply derived
from real local change instead of a fixed uniform grid.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from math import isfinite
from numbers import Real
from typing import Literal

from mockingbird.observation.multi_scale_strategy import (
    BOX_COORDINATE_DECIMALS,
    EDGE_PADDING_CLIP_TO_SOURCE_BOUNDS,
    StrategyWindow,
)

Number = int | float
# Reuses the exact `FramePlane` convention already established by
# `mockingbird.motion.scoring`/`mockingbird.motion.activity_crop` (a
# rectangular sequence-of-sequences of grayscale numbers) so the same
# already-decoded plane shape works across both subsystems; this module does
# not import that package, it only mirrors its type shape.
FramePlane = Sequence[Sequence[Number]]
NormalizedBox = tuple[float, float, float, float]

MOTION_PROPOSAL_STRATEGY_KEY = "full_frame_plus_motion_proposals"

# --------------------------------------------------------------------------
# Stable rejection/degradation reason codes
# --------------------------------------------------------------------------

REASON_FIRST_FRAME_NO_PREDECESSOR = "first_frame_no_predecessor"
REASON_TEMPORAL_EVIDENCE_UNAVAILABLE = "temporal_evidence_unavailable"
REASON_SEQUENCE_BOUNDARY = "sequence_boundary"
REASON_PROVIDER_GENERATION_CHANGED = "provider_generation_changed"
REASON_DUPLICATE_FRAME_IDENTITY = "duplicate_frame_identity"
REASON_EXCESSIVE_SOURCE_TIME_GAP = "excessive_source_time_gap"
REASON_UNSTABLE_COMPARISON_INPUT = "unstable_comparison_input"
REASON_FULLY_PRIVACY_MASKED = "fully_privacy_masked"
REASON_GLOBAL_LUMINANCE_SHIFT = "global_luminance_shift"
REASON_EXCESSIVE_CHANGED_PIXEL_RATIO = "excessive_changed_pixel_ratio"
REASON_REGION_AREA_BELOW_MINIMUM = "region_area_below_minimum"
REASON_REGION_AREA_ABOVE_MAXIMUM = "region_area_above_maximum"
REASON_PROPOSAL_COUNT_EXCEEDS_MAXIMUM = "proposal_count_exceeds_maximum"

REASON_CODES: tuple[str, ...] = (
    REASON_FIRST_FRAME_NO_PREDECESSOR,
    REASON_TEMPORAL_EVIDENCE_UNAVAILABLE,
    REASON_SEQUENCE_BOUNDARY,
    REASON_PROVIDER_GENERATION_CHANGED,
    REASON_DUPLICATE_FRAME_IDENTITY,
    REASON_EXCESSIVE_SOURCE_TIME_GAP,
    REASON_UNSTABLE_COMPARISON_INPUT,
    REASON_FULLY_PRIVACY_MASKED,
    REASON_GLOBAL_LUMINANCE_SHIFT,
    REASON_EXCESSIVE_CHANGED_PIXEL_RATIO,
    REASON_REGION_AREA_BELOW_MINIMUM,
    REASON_REGION_AREA_ABOVE_MAXIMUM,
    REASON_PROPOSAL_COUNT_EXCEEDS_MAXIMUM,
)

# A pair-level reason: the comparison could not even be attempted honestly.
_UNSUPPORTED_REASONS = frozenset({
    REASON_FIRST_FRAME_NO_PREDECESSOR, REASON_TEMPORAL_EVIDENCE_UNAVAILABLE,
    REASON_SEQUENCE_BOUNDARY, REASON_PROVIDER_GENERATION_CHANGED,
    REASON_DUPLICATE_FRAME_IDENTITY, REASON_EXCESSIVE_SOURCE_TIME_GAP,
    REASON_UNSTABLE_COMPARISON_INPUT, REASON_FULLY_PRIVACY_MASKED,
})
# A pair-level reason: the comparison ran but was bounded/degraded to zero
# proposals as a camera-motion/lighting safeguard.
_DEGRADED_REASONS = frozenset({REASON_GLOBAL_LUMINANCE_SHIFT, REASON_EXCESSIVE_CHANGED_PIXEL_RATIO})

# Safety bound on raw connected-component count before attempting merge; a
# frame that fragments into more components than this is itself evidence of
# an unstable comparison (sensor noise, heavy foliage flicker, or a broad
# scene change) rather than a handful of bounded local subjects, and pure-
# Python pairwise merge cost is kept small and predictable by refusing to run
# on pathological input instead of scaling unboundedly.
MAX_RAW_REGIONS_BEFORE_MERGE = 64
_NEIGHBOR_OFFSETS_8: tuple[tuple[int, int], ...] = (
    (-1, -1), (0, -1), (1, -1), (-1, 0), (1, 0), (-1, 1), (0, 1), (1, 1),
)


class MotionProposalStrategyError(ValueError):
    """A bounded motion-proposal strategy validation or execution failure code."""


# --------------------------------------------------------------------------
# Strategy configuration contract
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class MotionProposalStrategyConfig:
    """The explicit, provider-neutral bounded motion-proposal contract.

    Deliberately carries no OpenCV, CUDA, ONNX Runtime, or camera-provider
    type or value -- every field is a plain string, bool, int, or float, the
    same convention `multi_scale_strategy.MultiScaleStrategyConfig` already
    established. Each field maps to one bullet of the Stage 6.5 provider-
    neutral proposal contract."""

    strategy_key: str
    strategy_version: str
    # -- temporal frame requirements --
    requires_predecessor_frame: bool
    temporal_frame_requirement: str
    max_predecessor_gap_ms: int
    # -- comparison/downsample --
    comparison_width: int
    comparison_height: int
    pixel_delta_threshold: float
    # -- connected-region extraction and merge --
    region_connectivity: Literal["4", "8"]
    min_region_area_fraction: float
    max_region_area_fraction: float
    region_merge_gap_fraction: float
    # -- window finalization --
    context_padding_ratio: float
    target_aspect_ratio: float
    min_window_dimension_fraction: float
    max_proposal_source_area_fraction: float
    max_proposals_per_frame: int
    ranking_rule: str
    # -- camera-motion / lighting protection --
    max_changed_pixel_ratio: float
    global_luminance_shift_threshold: float
    camera_motion_rejection: str
    # -- Privacy/Ignore --
    privacy_ignore_handling: str
    # -- detector-integration facts, shared convention with multi_scale_strategy --
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
            raise MotionProposalStrategyError("invalid_strategy_key")
        if not self.strategy_version:
            raise MotionProposalStrategyError("invalid_strategy_version")
        if self.max_predecessor_gap_ms < 0:
            raise MotionProposalStrategyError("invalid_max_predecessor_gap_ms")
        if self.comparison_width < 8 or self.comparison_height < 8:
            raise MotionProposalStrategyError("invalid_comparison_dimensions")
        if self.pixel_delta_threshold < 0:
            raise MotionProposalStrategyError("invalid_pixel_delta_threshold")
        if self.region_connectivity not in ("4", "8"):
            raise MotionProposalStrategyError("invalid_region_connectivity")
        if not 0.0 <= self.min_region_area_fraction < self.max_region_area_fraction <= 1.0:
            raise MotionProposalStrategyError("invalid_region_area_bounds")
        if self.region_merge_gap_fraction < 0.0:
            raise MotionProposalStrategyError("invalid_region_merge_gap_fraction")
        if self.context_padding_ratio < 0.0:
            raise MotionProposalStrategyError("invalid_context_padding_ratio")
        if self.target_aspect_ratio <= 0.0:
            raise MotionProposalStrategyError("invalid_target_aspect_ratio")
        if not 0.0 <= self.min_window_dimension_fraction <= 1.0:
            raise MotionProposalStrategyError("invalid_min_window_dimension_fraction")
        if not 0.0 < self.max_proposal_source_area_fraction <= 1.0:
            raise MotionProposalStrategyError("invalid_max_proposal_source_area_fraction")
        if not 1 <= self.max_proposals_per_frame <= 32:
            raise MotionProposalStrategyError("invalid_max_proposals_per_frame")
        if not 0.0 < self.max_changed_pixel_ratio <= 1.0:
            raise MotionProposalStrategyError("invalid_max_changed_pixel_ratio")
        if self.global_luminance_shift_threshold < 0.0:
            raise MotionProposalStrategyError("invalid_global_luminance_shift_threshold")
        if not 0.0 < self.per_window_score_threshold <= 1.0:
            raise MotionProposalStrategyError("invalid_per_window_score_threshold")
        if not 0.0 < self.cross_window_iou_threshold < 1.0:
            raise MotionProposalStrategyError("invalid_cross_window_iou_threshold")
        if not 1 <= self.max_final_detections <= 1000:
            raise MotionProposalStrategyError("invalid_max_final_detections")


# Suggested initial bound from the Stage 6.5 task packet (no more than 3
# adaptive windows per frame); every other bound below was chosen to be a
# general, scene-independent default and exercised against the real reviewed
# temporal cohort rather than hand-tuned to it (see the contract doc).
DEFAULT_MAX_PROPOSALS_PER_FRAME = 3

FULL_FRAME_PLUS_MOTION_PROPOSALS = MotionProposalStrategyConfig(
    strategy_key=MOTION_PROPOSAL_STRATEGY_KEY,
    strategy_version="motion-proposal-strategy-v1",
    requires_predecessor_frame=True,
    temporal_frame_requirement=(
        "requires one ordered predecessor frame sharing the current frame's sequence_id, "
        "with a recorded source_offset_ms on both frames; a frame with no eligible "
        "predecessor produces an explicit unsupported reason, never a silent full-frame-only fallback"
    ),
    max_predecessor_gap_ms=90_000,
    comparison_width=160,
    comparison_height=120,
    pixel_delta_threshold=25.0,
    region_connectivity="8",
    min_region_area_fraction=0.0015,
    max_region_area_fraction=0.35,
    region_merge_gap_fraction=0.02,
    context_padding_ratio=0.5,
    target_aspect_ratio=1.0,
    min_window_dimension_fraction=0.08,
    max_proposal_source_area_fraction=0.25,
    max_proposals_per_frame=DEFAULT_MAX_PROPOSALS_PER_FRAME,
    ranking_rule="descending changed-pixel count on the merged, pre-padding region, tie-broken by normalized box then region index",
    max_changed_pixel_ratio=0.6,
    global_luminance_shift_threshold=40.0,
    camera_motion_rejection=(
        "a whole-frame mean absolute delta at or above global_luminance_shift_threshold, or a "
        "changed-pixel ratio at or above max_changed_pixel_ratio, rejects the whole pair before any "
        "region is considered -- zero proposal windows are produced rather than one window per "
        "spuriously changed region, so a lighting shift or camera bump cannot itself create a "
        "grid of proposals"
    ),
    privacy_ignore_handling=(
        "declared Privacy/Ignore regions are excluded from both frame planes before any pixel "
        "comparison: excluded pixels never contribute to the changed-pixel ratio, the mean "
        "luminance-shift statistic, or any connected region; a pair whose excluded area covers "
        "the entire comparison plane is reported fully_privacy_masked rather than compared"
    ),
    edge_padding_behavior=EDGE_PADDING_CLIP_TO_SOURCE_BOUNDS,
    per_window_preprocessing="reuses the configured detector provider's own preprocessing contract unchanged",
    per_window_score_threshold=0.1,
    cross_window_iou_threshold=0.5,
    duplicate_suppression_rule=(
        "same-broad-class IoU >= cross_window_iou_threshold collapses to the higher-scored "
        "detection, stable tiebreak on source box then observation id -- identical rule and "
        "identical shared function (multi_scale_strategy.suppress_cross_window_duplicates) as "
        "the Stage 6.4 uniform-tile strategy, so a detection is never counted twice, and is never "
        "counted as independent temporal confirmation, merely because two overlapping windows saw it"
    ),
    max_final_detections=300,
    resource_bounds="at most max_proposals_per_frame proposal windows plus one full-frame pass per frame",
    limitations=(
        "requires ordered source-relative timestamps within a shared sequence_id; a curated "
        "still-image cohort with no such sequencing produces no proposals for any of its frames",
        "comparison runs on a fixed-size downsampled grayscale plane, not full source resolution; "
        "a subject smaller than roughly one comparison-plane pixel may not register as changed",
        "broad scene displacement (for example a physically bumped or reframed camera) is only "
        "caught incidentally through the excessive-changed-pixel-ratio guard; no independent "
        "motion-vector or optical-flow displacement estimate is computed",
        "pure frame-differencing cannot distinguish a genuine animal from any other locally "
        "bounded change (blowing foliage, a shadow edge, a passing vehicle); it proposes where to "
        "look at higher resolution, it does not itself confirm an animal is present",
        "max_predecessor_gap_ms assumes a periodic or motion-triggered snapshot cadence measured "
        "in seconds-to-low-minutes, not a fixed video frame rate; it is not derived from any one "
        "camera's configured capture interval",
    ),
)


# --------------------------------------------------------------------------
# Temporal predecessor eligibility
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class FrameIdentity:
    """The bounded set of provider-neutral facts needed to decide whether one
    frame may be diffed against a candidate predecessor. Deliberately holds
    no pixel data, camera identity, or Zone reference."""

    frame_id: str
    sequence_id: str | None
    source_offset_ms: int | None
    content_hash: str | None = None
    provider_generation: str | None = None

    def __post_init__(self) -> None:
        if not self.frame_id:
            raise MotionProposalStrategyError("invalid_frame_id")
        if self.source_offset_ms is not None and self.source_offset_ms < 0:
            raise MotionProposalStrategyError("invalid_source_offset_ms")


@dataclass(frozen=True)
class PredecessorEligibility:
    eligible: bool
    reason_code: str | None
    gap_ms: int | None = None


def check_predecessor_eligibility(
    config: MotionProposalStrategyConfig, *, current: FrameIdentity, predecessor: FrameIdentity | None,
) -> PredecessorEligibility:
    """Decide, from identity/timing facts alone (no pixels), whether
    `predecessor` may be diffed against `current`. Every branch returns a
    stable reason code instead of raising, so a caller walking an ordered
    cohort can report an honest per-frame outcome rather than aborting."""

    if current.sequence_id is None:
        # No temporal grouping exists for this frame at all -- distinct from
        # "this frame is genuinely first in a real sequence" below, and
        # checked first so a caller never has to guess which honest reason
        # applies to a still-image-only cohort.
        return PredecessorEligibility(False, REASON_TEMPORAL_EVIDENCE_UNAVAILABLE)
    if predecessor is None:
        return PredecessorEligibility(False, REASON_FIRST_FRAME_NO_PREDECESSOR)
    if predecessor.sequence_id != current.sequence_id:
        return PredecessorEligibility(False, REASON_SEQUENCE_BOUNDARY)
    if (
        (predecessor.provider_generation is not None or current.provider_generation is not None)
        and predecessor.provider_generation != current.provider_generation
    ):
        return PredecessorEligibility(False, REASON_PROVIDER_GENERATION_CHANGED)
    if predecessor.frame_id == current.frame_id:
        return PredecessorEligibility(False, REASON_DUPLICATE_FRAME_IDENTITY)
    if (
        predecessor.content_hash is not None
        and current.content_hash is not None
        and predecessor.content_hash == current.content_hash
    ):
        return PredecessorEligibility(False, REASON_DUPLICATE_FRAME_IDENTITY)
    if current.source_offset_ms is None or predecessor.source_offset_ms is None:
        return PredecessorEligibility(False, REASON_TEMPORAL_EVIDENCE_UNAVAILABLE)
    gap = current.source_offset_ms - predecessor.source_offset_ms
    if gap < 0:
        # Out of declared order; never guess intent, report the same
        # boundary reason a genuine discontinuity would produce.
        return PredecessorEligibility(False, REASON_SEQUENCE_BOUNDARY, gap_ms=gap)
    if gap > config.max_predecessor_gap_ms:
        return PredecessorEligibility(False, REASON_EXCESSIVE_SOURCE_TIME_GAP, gap_ms=gap)
    return PredecessorEligibility(True, None, gap_ms=gap)


# --------------------------------------------------------------------------
# Deterministic frame differencing and connected-region extraction
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class ChangeRegion:
    """One merged connected region of changed pixels, in the comparison
    plane's own normalized [0,1] space (resolution/aspect independent --
    mapping to source coordinates is later a pure multiply, exactly like
    `multi_scale_strategy.map_window_box_to_source`)."""

    box: NormalizedBox
    changed_pixel_count: int
    area_fraction: float


@dataclass(frozen=True)
class RejectedRegion:
    region: ChangeRegion
    reason_code: str


@dataclass(frozen=True)
class ChangeDetectionResult:
    """Whole-pair-level outcome. `eligible=False` means zero regions were
    even considered (a pair-level safeguard fired); `eligible=True` with an
    empty `regions` tuple honestly means the pair compared cleanly and
    nothing survived region-level filtering (for example only noise-sized
    specks changed) -- both are valid, distinct outcomes."""

    eligible: bool
    reason_code: str | None
    changed_pixel_ratio: float | None
    mean_absolute_delta: float | None
    analyzed_pixel_count: int
    regions: tuple[ChangeRegion, ...] = ()
    rejected_regions: tuple[RejectedRegion, ...] = ()


def _validate_plane(plane: FramePlane, *, name: str, expected_width: int, expected_height: int) -> None:
    if isinstance(plane, (str, bytes)) or not isinstance(plane, Sequence) or len(plane) != expected_height:
        raise MotionProposalStrategyError(REASON_UNSTABLE_COMPARISON_INPUT)
    for row in plane:
        if isinstance(row, (str, bytes)) or not isinstance(row, Sequence) or len(row) != expected_width:
            raise MotionProposalStrategyError(REASON_UNSTABLE_COMPARISON_INPUT)
        for value in row:
            if not isinstance(value, Real) or isinstance(value, bool) or not isfinite(float(value)):
                raise MotionProposalStrategyError(REASON_UNSTABLE_COMPARISON_INPUT)


def _excluded_pixel_mask(
    *, width: int, height: int, excluded_regions: tuple[NormalizedBox, ...],
) -> list[list[bool]] | None:
    if not excluded_regions:
        return None
    mask = [[False] * width for _ in range(height)]
    for left, top, right, bottom in excluded_regions:
        px0, py0 = max(0, int(left * width)), max(0, int(top * height))
        px1, py1 = min(width, int(round(right * width))), min(height, int(round(bottom * height)))
        for y in range(py0, py1):
            row = mask[y]
            for x in range(px0, px1):
                row[x] = True
    return mask


@dataclass(frozen=True)
class _RawComponent:
    min_x: int
    min_y: int
    max_x: int
    max_y: int
    pixel_count: int

    def normalized_box(self, *, width: int, height: int) -> NormalizedBox:
        return (
            self.min_x / width, self.min_y / height,
            (self.max_x + 1) / width, (self.max_y + 1) / height,
        )


def _connected_components(mask: list[list[bool]], *, width: int, height: int) -> list[_RawComponent]:
    """Deterministic 8-connected flood fill over a fixed boolean grid.

    Raster-scan discovery order plus a stack-based fill make the result fully
    determined by the mask alone -- no dict/set hash-order dependency, no
    reliance on any external caller-supplied ordering."""

    visited = [[False] * width for _ in range(height)]
    components: list[_RawComponent] = []
    for start_y in range(height):
        for start_x in range(width):
            if not mask[start_y][start_x] or visited[start_y][start_x]:
                continue
            stack = [(start_x, start_y)]
            visited[start_y][start_x] = True
            min_x = max_x = start_x
            min_y = max_y = start_y
            count = 0
            while stack:
                x, y = stack.pop()
                count += 1
                if x < min_x:
                    min_x = x
                if x > max_x:
                    max_x = x
                if y < min_y:
                    min_y = y
                if y > max_y:
                    max_y = y
                for dx, dy in _NEIGHBOR_OFFSETS_8:
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < width and 0 <= ny < height and mask[ny][nx] and not visited[ny][nx]:
                        visited[ny][nx] = True
                        stack.append((nx, ny))
            components.append(_RawComponent(min_x, min_y, max_x, max_y, count))
    return components


def _boxes_within_gap(a: _RawComponent, b: _RawComponent, *, width: int, height: int, gap_fraction: float) -> bool:
    pad_x, pad_y = gap_fraction * width, gap_fraction * height
    ax0, ay0, ax1, ay1 = a.min_x - pad_x, a.min_y - pad_y, a.max_x + pad_x, a.max_y + pad_y
    return not (ax1 < b.min_x or b.max_x < ax0 or ay1 < b.min_y or b.max_y < ay0)


def _union(a: _RawComponent, b: _RawComponent) -> _RawComponent:
    return _RawComponent(
        min(a.min_x, b.min_x), min(a.min_y, b.min_y),
        max(a.max_x, b.max_x), max(a.max_y, b.max_y),
        a.pixel_count + b.pixel_count,
    )


def _merge_nearby_components(
    components: list[_RawComponent], *, width: int, height: int, gap_fraction: float,
) -> list[_RawComponent]:
    """Approximate a morphological "close" (dilate, merge, erode) without an
    OpenCV dependency: repeatedly union any two components whose bounding
    boxes fall within `gap_fraction` of each other until no pair qualifies.
    Bounded by `MAX_RAW_REGIONS_BEFORE_MERGE` before this is ever called."""

    working = list(components)
    merged = True
    while merged:
        merged = False
        for i in range(len(working)):
            for j in range(i + 1, len(working)):
                if _boxes_within_gap(working[i], working[j], width=width, height=height, gap_fraction=gap_fraction):
                    working[i] = _union(working[i], working[j])
                    del working[j]
                    merged = True
                    break
            if merged:
                break
    return working


def detect_changed_regions(
    predecessor_plane: FramePlane,
    current_plane: FramePlane,
    *,
    config: MotionProposalStrategyConfig,
    excluded_regions: tuple[NormalizedBox, ...] = (),
) -> ChangeDetectionResult:
    """Deterministic whole-plane differencing, camera-motion/lighting
    safeguards, and bounded connected-region extraction.

    Privacy/Ignore regions are masked (excluded from every statistic and from
    region membership) before any comparison, matching the existing
    `onnx_provider`/`multi_scale_strategy` convention that masking happens
    before, not after, analysis."""

    width, height = config.comparison_width, config.comparison_height
    _validate_plane(predecessor_plane, name="predecessor_frame", expected_width=width, expected_height=height)
    _validate_plane(current_plane, name="current_frame", expected_width=width, expected_height=height)

    excluded = _excluded_pixel_mask(width=width, height=height, excluded_regions=excluded_regions)
    total_pixels = width * height
    excluded_count = sum(row.count(True) for row in excluded) if excluded else 0
    analyzed_pixel_count = total_pixels - excluded_count
    if analyzed_pixel_count <= 0:
        return ChangeDetectionResult(False, REASON_FULLY_PRIVACY_MASKED, None, None, 0)

    changed_mask = [[False] * width for _ in range(height)]
    changed_count = 0
    delta_sum = 0.0
    threshold = config.pixel_delta_threshold
    for y in range(height):
        previous_row, current_row = predecessor_plane[y], current_plane[y]
        excluded_row = excluded[y] if excluded else None
        mask_row = changed_mask[y]
        for x in range(width):
            if excluded_row is not None and excluded_row[x]:
                continue
            delta = abs(float(current_row[x]) - float(previous_row[x]))
            delta_sum += delta
            if delta >= threshold:
                mask_row[x] = True
                changed_count += 1

    mean_absolute_delta = delta_sum / analyzed_pixel_count
    changed_pixel_ratio = changed_count / analyzed_pixel_count

    if mean_absolute_delta >= config.global_luminance_shift_threshold:
        return ChangeDetectionResult(False, REASON_GLOBAL_LUMINANCE_SHIFT, changed_pixel_ratio, mean_absolute_delta, analyzed_pixel_count)
    if changed_pixel_ratio >= config.max_changed_pixel_ratio:
        return ChangeDetectionResult(False, REASON_EXCESSIVE_CHANGED_PIXEL_RATIO, changed_pixel_ratio, mean_absolute_delta, analyzed_pixel_count)
    if changed_count == 0:
        return ChangeDetectionResult(True, None, changed_pixel_ratio, mean_absolute_delta, analyzed_pixel_count)

    raw = _connected_components(changed_mask, width=width, height=height)
    if len(raw) > MAX_RAW_REGIONS_BEFORE_MERGE:
        return ChangeDetectionResult(False, REASON_UNSTABLE_COMPARISON_INPUT, changed_pixel_ratio, mean_absolute_delta, analyzed_pixel_count)
    merged = _merge_nearby_components(raw, width=width, height=height, gap_fraction=config.region_merge_gap_fraction)

    accepted: list[ChangeRegion] = []
    rejected: list[RejectedRegion] = []
    for component in merged:
        area_fraction = component.pixel_count / total_pixels
        region = ChangeRegion(component.normalized_box(width=width, height=height), component.pixel_count, area_fraction)
        if area_fraction < config.min_region_area_fraction:
            rejected.append(RejectedRegion(region, REASON_REGION_AREA_BELOW_MINIMUM))
        elif area_fraction > config.max_region_area_fraction:
            rejected.append(RejectedRegion(region, REASON_REGION_AREA_ABOVE_MAXIMUM))
        else:
            accepted.append(region)

    return ChangeDetectionResult(
        True, None, changed_pixel_ratio, mean_absolute_delta, analyzed_pixel_count,
        regions=tuple(accepted), rejected_regions=tuple(rejected),
    )


# --------------------------------------------------------------------------
# Window finalization: padding, aspect normalization, clipping, dimensions
# --------------------------------------------------------------------------


def _clamp01(value: float) -> float:
    return min(1.0, max(0.0, value))


def _pad_box(box: NormalizedBox, *, padding_ratio: float) -> NormalizedBox:
    left, top, right, bottom = box
    width, height = right - left, bottom - top
    pad_x, pad_y = width * padding_ratio, height * padding_ratio
    return (left - pad_x, top - pad_y, right + pad_x, bottom + pad_y)


def _normalize_aspect_ratio(box: NormalizedBox, *, target_ratio: float) -> NormalizedBox:
    left, top, right, bottom = box
    width, height = right - left, bottom - top
    if width <= 0.0 or height <= 0.0:
        return box
    center_x, center_y = (left + right) / 2.0, (top + bottom) / 2.0
    current_ratio = width / height
    if current_ratio < target_ratio:
        new_width = height * target_ratio
        return (center_x - new_width / 2.0, top, center_x + new_width / 2.0, bottom)
    if current_ratio > target_ratio:
        new_height = width / target_ratio
        return (left, center_y - new_height / 2.0, right, center_y + new_height / 2.0)
    return box


def _clip_preserving_size(box: NormalizedBox) -> NormalizedBox:
    """Shift a box fully inside [0,1] before shrinking it, so a proposal near
    one edge does not silently lose width/height (and therefore aspect
    ratio) only on the side that happened to clip."""

    left, top, right, bottom = box
    if left < 0.0:
        right -= left
        left = 0.0
    if top < 0.0:
        bottom -= top
        top = 0.0
    if right > 1.0:
        left -= (right - 1.0)
        right = 1.0
    if bottom > 1.0:
        top -= (bottom - 1.0)
        bottom = 1.0
    return (_clamp01(left), _clamp01(top), _clamp01(right), _clamp01(bottom))


def _enforce_min_dimension(box: NormalizedBox, *, min_dimension_fraction: float) -> NormalizedBox:
    left, top, right, bottom = box
    center_x, center_y = (left + right) / 2.0, (top + bottom) / 2.0
    if right - left < min_dimension_fraction:
        left, right = center_x - min_dimension_fraction / 2.0, center_x + min_dimension_fraction / 2.0
    if bottom - top < min_dimension_fraction:
        top, bottom = center_y - min_dimension_fraction / 2.0, center_y + min_dimension_fraction / 2.0
    return (left, top, right, bottom)


def _enforce_max_area(box: NormalizedBox, *, max_area_fraction: float) -> NormalizedBox:
    left, top, right, bottom = box
    width, height = right - left, bottom - top
    area = width * height
    if area <= max_area_fraction or area <= 0.0:
        return box
    scale = (max_area_fraction / area) ** 0.5
    center_x, center_y = (left + right) / 2.0, (top + bottom) / 2.0
    new_width, new_height = width * scale, height * scale
    return (center_x - new_width / 2.0, center_y - new_height / 2.0, center_x + new_width / 2.0, center_y + new_height / 2.0)


def finalize_proposal_window(box: NormalizedBox, *, config: MotionProposalStrategyConfig) -> NormalizedBox:
    """Steps 4-7 of proposal window generation, in the documented order: pad,
    normalize aspect ratio, clip to source bounds, enforce minimum and
    maximum window size -- reclipping defensively after each size change."""

    box = _clip_preserving_size(_pad_box(box, padding_ratio=config.context_padding_ratio))
    box = _clip_preserving_size(_normalize_aspect_ratio(box, target_ratio=config.target_aspect_ratio))
    box = _clip_preserving_size(_enforce_min_dimension(box, min_dimension_fraction=config.min_window_dimension_fraction))
    box = _clip_preserving_size(_enforce_max_area(box, max_area_fraction=config.max_proposal_source_area_fraction))
    return tuple(round(_clamp01(value), BOX_COORDINATE_DECIMALS) for value in box)  # type: ignore[return-value]


# --------------------------------------------------------------------------
# Top-level orchestration: pair -> ranked, bounded proposal windows
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class ProposalWindow:
    """One finalized, ranked motion proposal, retaining full provenance back
    to the raw changed region and predecessor frame that produced it."""

    proposal_id: str
    window: StrategyWindow
    rank: int
    source_region: ChangeRegion
    predecessor_frame_id: str


@dataclass(frozen=True)
class RejectedProposal:
    candidate_box: NormalizedBox
    source_region: ChangeRegion
    reason_code: str


@dataclass(frozen=True)
class ProposalGenerationResult:
    """The complete, honest outcome for one (predecessor, current) frame
    pair: either a stable pair-level reason (no region was ever considered,
    or a camera-motion/lighting safeguard fired), or zero-or-more ranked,
    bounded proposal windows plus every region-level rejection along the way."""

    frame_id: str
    predecessor_frame_id: str | None
    pair_eligible: bool
    pair_reason_code: str | None
    changed_pixel_ratio: float | None
    mean_absolute_delta: float | None
    proposals: tuple[ProposalWindow, ...] = ()
    rejected_regions: tuple[RejectedRegion, ...] = ()
    rejected_proposals: tuple[RejectedProposal, ...] = ()

    @property
    def is_unsupported(self) -> bool:
        return self.pair_reason_code in _UNSUPPORTED_REASONS

    @property
    def is_degraded(self) -> bool:
        return self.pair_reason_code in _DEGRADED_REASONS


def _rank_key(region: ChangeRegion) -> tuple[object, ...]:
    return (-region.changed_pixel_count, region.box, region.area_fraction)


def generate_proposals(
    config: MotionProposalStrategyConfig,
    *,
    current: FrameIdentity,
    predecessor: FrameIdentity | None,
    predecessor_plane: FramePlane | None,
    current_plane: FramePlane | None,
    excluded_regions: tuple[NormalizedBox, ...] = (),
) -> ProposalGenerationResult:
    """Full pipeline for one frame: eligibility -> differencing -> region
    filtering -> window finalization -> deterministic ranking -> hard count
    bound -> stable proposal identities."""

    eligibility = check_predecessor_eligibility(config, current=current, predecessor=predecessor)
    if not eligibility.eligible:
        return ProposalGenerationResult(
            current.frame_id, predecessor.frame_id if predecessor else None,
            False, eligibility.reason_code, None, None,
        )
    assert predecessor is not None
    if predecessor_plane is None or current_plane is None:
        return ProposalGenerationResult(
            current.frame_id, predecessor.frame_id, False, REASON_UNSTABLE_COMPARISON_INPUT, None, None,
        )

    detected = detect_changed_regions(
        predecessor_plane, current_plane, config=config, excluded_regions=excluded_regions,
    )
    if not detected.eligible:
        return ProposalGenerationResult(
            current.frame_id, predecessor.frame_id, False, detected.reason_code,
            detected.changed_pixel_ratio, detected.mean_absolute_delta,
        )

    finalized = [
        (region, finalize_proposal_window(region.box, config=config))
        for region in detected.regions
    ]
    ordered = sorted(finalized, key=lambda item: _rank_key(item[0]))

    kept = ordered[: config.max_proposals_per_frame]
    overflow = ordered[config.max_proposals_per_frame :]

    proposals: list[ProposalWindow] = []
    for rank, (region, box) in enumerate(kept):
        proposal_id = f"motion-proposal-{current.frame_id}-{rank:02d}"
        window = StrategyWindow(window_id=proposal_id, window_kind="tile", source_box=box)
        proposals.append(ProposalWindow(proposal_id, window, rank, region, predecessor.frame_id))

    rejected_proposals = tuple(
        RejectedProposal(box, region, REASON_PROPOSAL_COUNT_EXCEEDS_MAXIMUM) for region, box in overflow
    )

    return ProposalGenerationResult(
        current.frame_id, predecessor.frame_id, True, None,
        detected.changed_pixel_ratio, detected.mean_absolute_delta,
        proposals=tuple(proposals), rejected_regions=detected.rejected_regions,
        rejected_proposals=rejected_proposals,
    )


__all__ = [
    "DEFAULT_MAX_PROPOSALS_PER_FRAME",
    "FULL_FRAME_PLUS_MOTION_PROPOSALS",
    "MAX_RAW_REGIONS_BEFORE_MERGE",
    "MOTION_PROPOSAL_STRATEGY_KEY",
    "REASON_CODES",
    "REASON_DUPLICATE_FRAME_IDENTITY",
    "REASON_EXCESSIVE_CHANGED_PIXEL_RATIO",
    "REASON_EXCESSIVE_SOURCE_TIME_GAP",
    "REASON_FIRST_FRAME_NO_PREDECESSOR",
    "REASON_FULLY_PRIVACY_MASKED",
    "REASON_GLOBAL_LUMINANCE_SHIFT",
    "REASON_PROPOSAL_COUNT_EXCEEDS_MAXIMUM",
    "REASON_PROVIDER_GENERATION_CHANGED",
    "REASON_REGION_AREA_ABOVE_MAXIMUM",
    "REASON_REGION_AREA_BELOW_MINIMUM",
    "REASON_SEQUENCE_BOUNDARY",
    "REASON_TEMPORAL_EVIDENCE_UNAVAILABLE",
    "REASON_UNSTABLE_COMPARISON_INPUT",
    "ChangeDetectionResult",
    "ChangeRegion",
    "FramePlane",
    "FrameIdentity",
    "MotionProposalStrategyConfig",
    "MotionProposalStrategyError",
    "PredecessorEligibility",
    "ProposalGenerationResult",
    "ProposalWindow",
    "RejectedProposal",
    "RejectedRegion",
    "check_predecessor_eligibility",
    "detect_changed_regions",
    "finalize_proposal_window",
    "generate_proposals",
]
