"""Focused activity crop planning for saved-snapshot motion checks."""

from __future__ import annotations

from dataclasses import dataclass
from math import ceil, floor, isfinite
from typing import Literal

CropReason = Literal["user_zone", "auto_region_cluster", "full_frame_fallback"]

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
