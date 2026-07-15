"""Focused activity crop planning for saved-snapshot motion checks."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from math import ceil, floor, isfinite
from numbers import Real
from typing import Literal

CropReason = Literal["activity_motion", "full_frame_fallback"]
FramePlane = Sequence[Sequence[int | float]]

DEFAULT_CROP_PADDING_RATIO = 0.5
DEFAULT_MIN_CROP_SIZE_RATIO = 0.15


@dataclass(frozen=True)
class CropBoxNormalized:
    left: float
    top: float
    right: float
    bottom: float


@dataclass(frozen=True)
class CropBoxPixels:
    left: int
    top: int
    right: int
    bottom: int
    width: int
    height: int


@dataclass(frozen=True)
class ActivityCropPlan:
    source_media_asset_id: str | None
    crop_box_normalized: CropBoxNormalized
    crop_box_pixels: CropBoxPixels
    crop_reason: CropReason
    padding_ratio: float
    is_full_frame_fallback: bool
    derived_crop_media_asset_id: str | None = None
    warning: str | None = None


@dataclass(frozen=True)
class ActivityCropBoundsPlan:
    crop_box_normalized: CropBoxNormalized
    padding_ratio: float
    is_full_frame_fallback: bool
    warning: str | None = None


@dataclass(frozen=True)
class ChangedActivityBounds:
    """Measured changed-pixel extent for one motion frame pair.

    Search bounds associate the change with a motion candidate. They never
    become the returned bounds by themselves; the result is always calculated
    from pixels that crossed the motion threshold.
    """

    box_normalized: CropBoxNormalized
    changed_pixel_count: int


def locate_changed_activity_bounds(
    previous_frame: FramePlane,
    current_frame: FramePlane,
    *,
    pixel_delta_threshold: float,
    search_bounds: CropBoxNormalized | None = None,
) -> ChangedActivityBounds | None:
    """Locate actual changed pixels without treating Zone geometry as the crop."""

    width, height = _frame_pair_dimensions(previous_frame, current_frame)
    if (
        not isinstance(pixel_delta_threshold, Real)
        or isinstance(pixel_delta_threshold, bool)
        or not isfinite(float(pixel_delta_threshold))
        or pixel_delta_threshold < 0
    ):
        raise ValueError("pixel_delta_threshold must be a non-negative number")

    search = search_bounds or CropBoxNormalized(0.0, 0.0, 1.0, 1.0)
    if not _valid_bounds(search.left, search.top, search.right, search.bottom):
        raise ValueError("search_bounds must contain valid normalized bounds")
    left = _clamp_int(floor(_clamp(search.left, 0.0, 1.0) * width), 0, width - 1)
    top = _clamp_int(floor(_clamp(search.top, 0.0, 1.0) * height), 0, height - 1)
    right = _clamp_int(ceil(_clamp(search.right, 0.0, 1.0) * width), left + 1, width)
    bottom = _clamp_int(ceil(_clamp(search.bottom, 0.0, 1.0) * height), top + 1, height)

    min_x = width
    min_y = height
    max_x = -1
    max_y = -1
    changed_pixel_count = 0
    for y in range(top, bottom):
        previous_row = previous_frame[y]
        current_row = current_frame[y]
        for x in range(left, right):
            if abs(float(current_row[x]) - float(previous_row[x])) < pixel_delta_threshold:
                continue
            changed_pixel_count += 1
            min_x = min(min_x, x)
            min_y = min(min_y, y)
            max_x = max(max_x, x)
            max_y = max(max_y, y)

    if changed_pixel_count == 0:
        return None
    return ChangedActivityBounds(
        box_normalized=CropBoxNormalized(
            left=min_x / width,
            top=min_y / height,
            right=(max_x + 1) / width,
            bottom=(max_y + 1) / height,
        ),
        changed_pixel_count=changed_pixel_count,
    )


def plan_activity_crop_bounds(
    *,
    left: float | None,
    top: float | None,
    right: float | None,
    bottom: float | None,
    padding_ratio: float = DEFAULT_CROP_PADDING_RATIO,
    min_crop_size_ratio: float = DEFAULT_MIN_CROP_SIZE_RATIO,
) -> ActivityCropBoundsPlan:
    """Plan padded normalized activity bounds without requiring a decoded frame."""

    safe_padding = max(0.0, padding_ratio if isfinite(padding_ratio) else 0.0)
    safe_min_size = _clamp(
        min_crop_size_ratio if isfinite(min_crop_size_ratio) else DEFAULT_MIN_CROP_SIZE_RATIO,
        0.0,
        1.0,
    )

    if not _valid_bounds(left, top, right, bottom):
        return _full_frame_bounds_plan(
            padding_ratio=safe_padding,
            warning="Focused crop bounds unavailable; full snapshot remains the review context.",
        )

    base = CropBoxNormalized(
        left=_clamp(float(left), 0.0, 1.0),
        top=_clamp(float(top), 0.0, 1.0),
        right=_clamp(float(right), 0.0, 1.0),
        bottom=_clamp(float(bottom), 0.0, 1.0),
    )
    if base.left >= base.right or base.top >= base.bottom:
        return _full_frame_bounds_plan(
            padding_ratio=safe_padding,
            warning="Focused crop bounds fell outside the image; full snapshot remains the review context.",
        )

    padded = _pad_box(base, padding_ratio=safe_padding)
    expanded = _expand_to_min_size(padded, min_size_ratio=safe_min_size)
    crop = CropBoxNormalized(
        left=_clamp(expanded.left, 0.0, 1.0),
        top=_clamp(expanded.top, 0.0, 1.0),
        right=_clamp(expanded.right, 0.0, 1.0),
        bottom=_clamp(expanded.bottom, 0.0, 1.0),
    )
    if crop.left >= crop.right or crop.top >= crop.bottom:
        return _full_frame_bounds_plan(
            padding_ratio=safe_padding,
            warning="Focused crop collapsed after padding; full snapshot remains the review context.",
        )

    return ActivityCropBoundsPlan(
        crop_box_normalized=crop,
        padding_ratio=safe_padding,
        is_full_frame_fallback=False,
    )


def plan_activity_crop(
    *,
    source_media_asset_id: str | None,
    image_width: int,
    image_height: int,
    left: float | None,
    top: float | None,
    right: float | None,
    bottom: float | None,
    crop_reason: CropReason,
    padding_ratio: float = DEFAULT_CROP_PADDING_RATIO,
    min_crop_size_ratio: float = DEFAULT_MIN_CROP_SIZE_RATIO,
) -> ActivityCropPlan:
    """Plan a padded activity crop without writing files or replacing the snapshot."""

    if image_width < 1 or image_height < 1:
        raise ValueError("image dimensions must be positive")
    bounds_plan = plan_activity_crop_bounds(
        left=left,
        top=top,
        right=right,
        bottom=bottom,
        padding_ratio=padding_ratio,
        min_crop_size_ratio=min_crop_size_ratio,
    )

    return ActivityCropPlan(
        source_media_asset_id=source_media_asset_id,
        crop_box_normalized=bounds_plan.crop_box_normalized,
        crop_box_pixels=_pixel_box(
            bounds_plan.crop_box_normalized,
            image_width=image_width,
            image_height=image_height,
        ),
        crop_reason=(
            "full_frame_fallback" if bounds_plan.is_full_frame_fallback else crop_reason
        ),
        padding_ratio=bounds_plan.padding_ratio,
        is_full_frame_fallback=bounds_plan.is_full_frame_fallback,
        warning=bounds_plan.warning,
    )


def _full_frame_bounds_plan(
    *,
    padding_ratio: float,
    warning: str,
) -> ActivityCropBoundsPlan:
    crop = CropBoxNormalized(left=0.0, top=0.0, right=1.0, bottom=1.0)
    return ActivityCropBoundsPlan(
        crop_box_normalized=crop,
        padding_ratio=padding_ratio,
        is_full_frame_fallback=True,
        warning=warning,
    )


def _full_frame_plan(
    *,
    source_media_asset_id: str | None,
    image_width: int,
    image_height: int,
    padding_ratio: float,
    warning: str,
) -> ActivityCropPlan:
    crop = CropBoxNormalized(left=0.0, top=0.0, right=1.0, bottom=1.0)
    return ActivityCropPlan(
        source_media_asset_id=source_media_asset_id,
        crop_box_normalized=crop,
        crop_box_pixels=_pixel_box(crop, image_width=image_width, image_height=image_height),
        crop_reason="full_frame_fallback",
        padding_ratio=padding_ratio,
        is_full_frame_fallback=True,
        warning=warning,
    )


def _valid_bounds(
    left: float | None,
    top: float | None,
    right: float | None,
    bottom: float | None,
) -> bool:
    values = [left, top, right, bottom]
    return (
        all(isinstance(value, (int, float)) and not isinstance(value, bool) for value in values)
        and all(isfinite(float(value)) for value in values if value is not None)
        and left is not None
        and top is not None
        and right is not None
        and bottom is not None
        and float(left) < float(right)
        and float(top) < float(bottom)
    )


def _frame_pair_dimensions(
    previous_frame: FramePlane,
    current_frame: FramePlane,
) -> tuple[int, int]:
    previous = _frame_dimensions(previous_frame, name="previous_frame")
    current = _frame_dimensions(current_frame, name="current_frame")
    if previous != current:
        raise ValueError("previous_frame and current_frame dimensions must match")
    return previous


def _frame_dimensions(frame: FramePlane, *, name: str) -> tuple[int, int]:
    if isinstance(frame, (str, bytes)) or not isinstance(frame, Sequence) or not frame:
        raise ValueError(f"{name} must be a non-empty rectangular 2D sequence")
    width: int | None = None
    for row in frame:
        if isinstance(row, (str, bytes)) or not isinstance(row, Sequence) or not row:
            raise ValueError(f"{name} rows must be non-empty sequences")
        if width is None:
            width = len(row)
        elif len(row) != width:
            raise ValueError(f"{name} must be rectangular")
        if any(
            not isinstance(value, Real)
            or isinstance(value, bool)
            or not isfinite(float(value))
            for value in row
        ):
            raise ValueError(f"{name} pixels must be finite numbers")
    return width or 0, len(frame)


def _pad_box(box: CropBoxNormalized, *, padding_ratio: float) -> CropBoxNormalized:
    width = box.right - box.left
    height = box.bottom - box.top
    pad_x = width * padding_ratio
    pad_y = height * padding_ratio
    return CropBoxNormalized(
        left=box.left - pad_x,
        top=box.top - pad_y,
        right=box.right + pad_x,
        bottom=box.bottom + pad_y,
    )


def _expand_to_min_size(
    box: CropBoxNormalized,
    *,
    min_size_ratio: float,
) -> CropBoxNormalized:
    return _expand_axis(box, min_size_ratio=min_size_ratio, horizontal=True)


def _expand_axis(
    box: CropBoxNormalized,
    *,
    min_size_ratio: float,
    horizontal: bool,
) -> CropBoxNormalized:
    left = box.left
    top = box.top
    right = box.right
    bottom = box.bottom

    width = right - left
    height = bottom - top
    if horizontal and width < min_size_ratio:
        center = (left + right) / 2
        half_size = min_size_ratio / 2
        left = center - half_size
        right = center + half_size
    if not horizontal and height < min_size_ratio:
        center = (top + bottom) / 2
        half_size = min_size_ratio / 2
        top = center - half_size
        bottom = center + half_size

    expanded = CropBoxNormalized(left=left, top=top, right=right, bottom=bottom)
    if horizontal:
        return _expand_axis(expanded, min_size_ratio=min_size_ratio, horizontal=False)
    return expanded


def _pixel_box(
    box: CropBoxNormalized,
    *,
    image_width: int,
    image_height: int,
) -> CropBoxPixels:
    left = _clamp_int(floor(box.left * image_width), 0, image_width - 1)
    top = _clamp_int(floor(box.top * image_height), 0, image_height - 1)
    right = _clamp_int(ceil(box.right * image_width), left + 1, image_width)
    bottom = _clamp_int(ceil(box.bottom * image_height), top + 1, image_height)
    return CropBoxPixels(
        left=left,
        top=top,
        right=right,
        bottom=bottom,
        width=right - left,
        height=bottom - top,
    )


def _clamp(value: float, lower: float, upper: float) -> float:
    return min(upper, max(lower, value))


def _clamp_int(value: int, lower: int, upper: int) -> int:
    return min(upper, max(lower, value))
