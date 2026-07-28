"""Safe geometry mapping and crop derivation for bounded high-resolution evidence."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha1
from math import ceil, isfinite
from typing import Iterable

import cv2
import numpy as np


NormalizedBox = tuple[float, float, float, float]
MAX_HIGH_RESOLUTION_CROP_BYTES = 16_000_000
MIN_REFINED_CROP_WIDTH_PIXELS = 64
MIN_REFINED_CROP_HEIGHT_PIXELS = 64
MAX_REFINED_CROP_AREA_RATIO = 0.90


@dataclass(frozen=True)
class CaptureProfileGeometry:
    profile_id: str
    width: int
    height: int
    geometry_group: str | None
    orientation: str
    mirrored: bool
    same_fov: bool


@dataclass(frozen=True)
class NormalizedGeometryTransform:
    """A normalized, lossless orientation transform between same-FOV profiles."""

    transform_id: str
    rotation: int = 0
    mirrored: bool = False

    def map_point(self, x: float, y: float) -> tuple[float, float]:
        if self.mirrored:
            x = 1.0 - x
        if self.rotation == 90:
            x, y = 1.0 - y, x
        elif self.rotation == 180:
            x, y = 1.0 - x, 1.0 - y
        elif self.rotation == 270:
            x, y = y, 1.0 - x
        return _bounded(x), _bounded(y)

    def map_box(self, box: NormalizedBox) -> NormalizedBox | None:
        if not _valid_box(box):
            return None
        left, top, right, bottom = box
        mapped = [
            self.map_point(x, y)
            for x, y in (
                (left, top),
                (right, top),
                (left, bottom),
                (right, bottom),
            )
        ]
        return _box_from_points(mapped)


@dataclass(frozen=True)
class AlignmentDecision:
    status: str
    transform: NormalizedGeometryTransform | None
    failure_code: str | None = None


@dataclass(frozen=True)
class CropResult:
    image: bytes
    width: int
    height: int
    normalized_crop_box: NormalizedBox


def resolve_alignment(
    monitoring: CaptureProfileGeometry | None,
    evidence: CaptureProfileGeometry | None,
) -> AlignmentDecision:
    """Only approve a normalized crop when Node metadata proves a shared FOV."""

    if monitoring is None or evidence is None:
        return AlignmentDecision("full_only", None, "capture_profile_unavailable")
    if (
        not monitoring.geometry_group
        or monitoring.geometry_group != evidence.geometry_group
        or not monitoring.same_fov
        or not evidence.same_fov
    ):
        return AlignmentDecision("full_only", None, "geometry_unproven")
    rotation = _orientation_delta(monitoring.orientation, evidence.orientation)
    if rotation is None:
        return AlignmentDecision("full_only", None, "orientation_unproven")
    transform = NormalizedGeometryTransform(
        transform_id=_transform_id(monitoring, evidence, rotation),
        rotation=rotation,
        mirrored=monitoring.mirrored != evidence.mirrored,
    )
    return AlignmentDecision("aligned", transform)


def padded_box(box: NormalizedBox, *, padding_ratio: float = 0.18) -> NormalizedBox | None:
    if not _valid_box(box) or not 0.0 <= padding_ratio <= 0.5:
        return None
    left, top, right, bottom = box
    width, height = right - left, bottom - top
    return _box_from_points(
        (
            (_bounded(left - width * padding_ratio), _bounded(top - height * padding_ratio)),
            (_bounded(right + width * padding_ratio), _bounded(bottom + height * padding_ratio)),
        )
    )


def crop_jpeg(
    image: bytes,
    box: NormalizedBox,
) -> CropResult | None:
    """Create one bounded JPEG crop without retaining or decoding video frames."""

    if not image or len(image) > MAX_HIGH_RESOLUTION_CROP_BYTES or not _valid_box(box):
        return None
    decoded = cv2.imdecode(np.frombuffer(image, dtype=np.uint8), cv2.IMREAD_COLOR)
    if decoded is None or decoded.ndim != 3:
        return None
    height, width = decoded.shape[:2]
    if width < 2 or height < 2:
        return None
    left, top, right, bottom = box
    x0, y0 = int(left * width), int(top * height)
    x1, y1 = int(np.ceil(right * width)), int(np.ceil(bottom * height))
    x0, y0 = max(0, min(x0, width - 1)), max(0, min(y0, height - 1))
    x1, y1 = max(x0 + 1, min(x1, width)), max(y0 + 1, min(y1, height))
    crop = decoded[y0:y1, x0:x1]
    encoded, output = cv2.imencode(".jpg", crop)
    if not encoded:
        return None
    data = output.tobytes()
    if not data or len(data) > MAX_HIGH_RESOLUTION_CROP_BYTES:
        return None
    return CropResult(
        image=data,
        width=x1 - x0,
        height=y1 - y0,
        normalized_crop_box=(x0 / width, y0 / height, x1 / width, y1 / height),
    )


def validate_refined_crop_box(
    box: Iterable[float],
    *,
    image_width: int,
    image_height: int,
) -> NormalizedBox | None:
    """Validate a reviewer selection before reading or writing a derived image.

    The bounds are deliberately normalized and source-relative: callers cannot
    supply a media path, output dimensions, or pixel data. The same rounded
    pixel geometry used by ``crop_jpeg`` is checked so a valid-looking browser
    rectangle cannot collapse into an unusable saved crop.
    """

    values = tuple(box)
    if image_width < 1 or image_height < 1 or len(values) != 4:
        return None
    try:
        left, top, right, bottom = (float(value) for value in values)
    except (TypeError, ValueError):
        return None
    if (
        not all(isfinite(value) for value in (left, top, right, bottom))
        or not 0.0 <= left < right <= 1.0
        or not 0.0 <= top < bottom <= 1.0
        or (right - left) * (bottom - top) > MAX_REFINED_CROP_AREA_RATIO
    ):
        return None
    x0, y0 = int(left * image_width), int(top * image_height)
    x1, y1 = int(ceil(right * image_width)), int(ceil(bottom * image_height))
    if (
        x1 - x0 < MIN_REFINED_CROP_WIDTH_PIXELS
        or y1 - y0 < MIN_REFINED_CROP_HEIGHT_PIXELS
    ):
        return None
    return (left, top, right, bottom)


def _orientation_delta(source: str, destination: str) -> int | None:
    values = {"normal": 0, "rotate_90": 90, "rotate_180": 180, "rotate_270": 270}
    if source not in values or destination not in values:
        return None
    return (values[destination] - values[source]) % 360


def _transform_id(
    monitoring: CaptureProfileGeometry,
    evidence: CaptureProfileGeometry,
    rotation: int,
) -> str:
    fingerprint = sha1(
        "|".join(
            (
                monitoring.profile_id,
                evidence.profile_id,
                monitoring.geometry_group or "",
                str(rotation),
                str(monitoring.mirrored != evidence.mirrored),
            )
        ).encode("utf-8")
    ).hexdigest()[:16]
    return f"normalized-fov-{fingerprint}"


def _valid_box(box: Iterable[float]) -> bool:
    values = tuple(box)
    if len(values) != 4:
        return False
    try:
        left, top, right, bottom = (float(value) for value in values)
    except (TypeError, ValueError):
        return False
    return 0.0 <= left < right <= 1.0 and 0.0 <= top < bottom <= 1.0


def _box_from_points(points: Iterable[tuple[float, float]]) -> NormalizedBox | None:
    items = tuple(points)
    if not items:
        return None
    left, right = min(item[0] for item in items), max(item[0] for item in items)
    top, bottom = min(item[1] for item in items), max(item[1] for item in items)
    box = (_bounded(left), _bounded(top), _bounded(right), _bounded(bottom))
    return box if _valid_box(box) else None


def _bounded(value: float) -> float:
    return max(0.0, min(1.0, float(value)))
