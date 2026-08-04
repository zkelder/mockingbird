"""Deterministic decoder for the raw YOLOv5 tensor emitted by MDv5a."""

from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
import math
from typing import Any, Protocol

from mockingbird.observation.replay import ReplayValidationError


MDV5_DECODER_KEY = "megadetector_v5_yolov5_raw_v1"
MDV5_RAW_COLUMNS = 8
MDV5_CLASS_COUNT = 3
MDV5_COORD_DIGITS = 4
MDV5_CONFIDENCE_DIGITS = 3
MAX_MDV5_RAW_CANDIDATES = 150_000


class SourceTransform(Protocol):
    scale_x: float
    scale_y: float
    pad_x: float
    pad_y: float
    source_width: int
    source_height: int


@dataclass(frozen=True)
class MdV5Detection:
    class_index: int
    confidence: float
    bounding_box: tuple[float, float, float, float]


def decode_md_v5_raw(
    outputs: Any,
    *,
    score_threshold: float,
    nms_iou_threshold: float,
    nms_max_detections: int,
    max_decode_candidates: int,
    raw_output_shape: tuple[int, int, int] | None,
    transform: SourceTransform,
) -> tuple[MdV5Detection, ...]:
    """Apply the working MegaDetector v5 confidence/NMS/rounding contract."""

    try:
        numpy = import_module("numpy")
        if not isinstance(outputs, (list, tuple)) or not outputs:
            raise ReplayValidationError("malformed_detector_output")
        raw = numpy.asarray(outputs[0])
        if raw.ndim != 3 or raw.shape[0] != 1 or raw.shape[2] != MDV5_RAW_COLUMNS:
            raise ReplayValidationError("malformed_detector_output")
        candidate_count = int(raw.shape[1])
        if candidate_count > max_decode_candidates:
            raise ReplayValidationError("detector_output_limit")
        if raw_output_shape is not None and tuple(int(value) for value in raw.shape) != raw_output_shape:
            raise ReplayValidationError("malformed_detector_output")
        if not bool(numpy.isfinite(raw).all()):
            raise ReplayValidationError("malformed_detector_output")

        rows = raw[0]
        if candidate_count == 0:
            return ()
        if bool((rows[:, 2:4] <= 0).any()):
            raise ReplayValidationError("malformed_detector_output")
        probabilities = rows[:, 4:]
        if bool(((probabilities < 0) | (probabilities > 1)).any()):
            raise ReplayValidationError("malformed_detector_output")

        object_mask = rows[:, 4] > score_threshold
        eligible_indices = numpy.flatnonzero(object_mask)
        if not len(eligible_indices):
            return ()
        eligible = rows[eligible_indices]
        class_scores = eligible[:, 5:] * eligible[:, 4:5]
        class_indices = class_scores.argmax(axis=1)
        scores = class_scores[numpy.arange(len(eligible)), class_indices]
        score_mask = scores > score_threshold
        if not bool(score_mask.any()):
            return ()

        eligible_indices = eligible_indices[score_mask]
        eligible = eligible[score_mask]
        class_indices = class_indices[score_mask]
        scores = scores[score_mask]
        boxes = numpy.empty((len(eligible), 4), dtype=eligible.dtype)
        boxes[:, 0] = eligible[:, 0] - eligible[:, 2] / 2.0
        boxes[:, 1] = eligible[:, 1] - eligible[:, 3] / 2.0
        boxes[:, 2] = eligible[:, 0] + eligible[:, 2] / 2.0
        boxes[:, 3] = eligible[:, 1] + eligible[:, 3] / 2.0

        kept: list[int] = []
        for class_index in range(MDV5_CLASS_COUNT):
            positions = numpy.flatnonzero(class_indices == class_index)
            if len(positions):
                kept.extend(
                    _class_nms(
                        positions,
                        boxes,
                        scores,
                        nms_iou_threshold=nms_iou_threshold,
                        original_indices=eligible_indices,
                    )
                )
        kept.sort(key=lambda position: (-float(scores[position]), int(eligible_indices[position])))
        kept = kept[:nms_max_detections]

        decoded: list[MdV5Detection] = []
        for position in kept:
            source_box = _classic_source_box(tuple(float(value) for value in boxes[position]), transform)
            if source_box is None:
                continue
            decoded.append(
                MdV5Detection(
                    class_index=int(class_indices[position]),
                    confidence=_truncate(float(scores[position]), MDV5_CONFIDENCE_DIGITS),
                    bounding_box=source_box,
                )
            )
        return tuple(decoded)
    except ReplayValidationError:
        raise
    except Exception as error:
        raise ReplayValidationError("malformed_detector_output") from error


def _class_nms(
    positions: Any,
    boxes: Any,
    scores: Any,
    *,
    nms_iou_threshold: float,
    original_indices: Any,
) -> list[int]:
    ordered = sorted(
        (int(position) for position in positions),
        key=lambda position: (-float(scores[position]), int(original_indices[position])),
    )
    kept: list[int] = []
    while ordered:
        current = ordered.pop(0)
        kept.append(current)
        ordered = [
            other
            for other in ordered
            if _iou(boxes[current], boxes[other]) <= nms_iou_threshold
        ]
    return kept


def _iou(first: Any, second: Any) -> float:
    left = max(float(first[0]), float(second[0]))
    top = max(float(first[1]), float(second[1]))
    right = min(float(first[2]), float(second[2]))
    bottom = min(float(first[3]), float(second[3]))
    intersection = max(0.0, right - left) * max(0.0, bottom - top)
    first_area = max(0.0, float(first[2]) - float(first[0])) * max(
        0.0, float(first[3]) - float(first[1])
    )
    second_area = max(0.0, float(second[2]) - float(second[0])) * max(
        0.0, float(second[3]) - float(second[1])
    )
    union = first_area + second_area - intersection
    return 0.0 if union <= 0 else intersection / union


def _classic_source_box(
    box: tuple[float, float, float, float],
    transform: SourceTransform,
) -> tuple[float, float, float, float] | None:
    source_pixels = (
        (box[0] - transform.pad_x) / transform.scale_x,
        (box[1] - transform.pad_y) / transform.scale_y,
        (box[2] - transform.pad_x) / transform.scale_x,
        (box[3] - transform.pad_y) / transform.scale_y,
    )
    x1 = round(min(float(transform.source_width), max(0.0, source_pixels[0])))
    y1 = round(min(float(transform.source_height), max(0.0, source_pixels[1])))
    x2 = round(min(float(transform.source_width), max(0.0, source_pixels[2])))
    y2 = round(min(float(transform.source_height), max(0.0, source_pixels[3])))
    if x1 >= x2 or y1 >= y2:
        return None

    x = _truncate(x1 / transform.source_width, MDV5_COORD_DIGITS)
    y = _truncate(y1 / transform.source_height, MDV5_COORD_DIGITS)
    width = _truncate((x2 - x1) / transform.source_width, MDV5_COORD_DIGITS)
    height = _truncate((y2 - y1) / transform.source_height, MDV5_COORD_DIGITS)
    values = (x, y, min(1.0, x + width), min(1.0, y + height))
    return tuple(round(value, 6) for value in values)


def _truncate(value: float, digits: int) -> float:
    if not math.isfinite(value):
        raise ReplayValidationError("malformed_detector_output")
    scale = 10**digits
    return math.trunc(value * scale) / scale
