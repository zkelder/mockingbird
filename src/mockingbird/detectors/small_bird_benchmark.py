"""Pure, local-only evaluation helpers for feeder-zone small-bird detection.

The helpers deliberately work on caller-owned image arrays and annotations.  They
do not know about the product repository, so a benchmark can neither create an
Event/Visit nor turn detector output into reviewed truth.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
import math
from statistics import median
from typing import Any

import cv2
import numpy as np

from mockingbird.detectors.megadetector_adapter import (
    MEGADETECTOR_MAX_LIVE_CROP_BYTES,
    MegaDetectorBox,
    MegaDetectorProposal,
)


@dataclass(frozen=True)
class NormalizedBox:
    """A half-open normalized source-frame rectangle."""

    left: float
    top: float
    right: float
    bottom: float

    def __post_init__(self) -> None:
        values = (self.left, self.top, self.right, self.bottom)
        if (
            not all(math.isfinite(value) and 0.0 <= value <= 1.0 for value in values)
            or self.left >= self.right
            or self.top >= self.bottom
        ):
            raise ValueError("normalized_box_invalid")

    @property
    def width(self) -> float:
        return self.right - self.left

    @property
    def height(self) -> float:
        return self.bottom - self.top

    @property
    def area(self) -> float:
        return self.width * self.height

    def as_megadetector_box(self) -> MegaDetectorBox:
        return MegaDetectorBox(
            x=self.left,
            y=self.top,
            width=self.width,
            height=self.height,
        )

    @classmethod
    def from_xyxy(cls, value: Sequence[object]) -> "NormalizedBox":
        if len(value) != 4:
            raise ValueError("normalized_box_invalid")
        try:
            return cls(*(float(item) for item in value))
        except (TypeError, ValueError) as error:
            raise ValueError("normalized_box_invalid") from error

    @classmethod
    def from_megadetector_box(cls, value: MegaDetectorBox) -> "NormalizedBox":
        return cls(value.x, value.y, value.x + value.width, value.y + value.height)


@dataclass(frozen=True)
class SmallBirdStrategy:
    """A bounded candidate input policy for the same local MDv5 runtime."""

    name: str
    input_long_edge: int | None
    columns: int = 1
    rows: int = 1
    overlap: float = 0.0

    def __post_init__(self) -> None:
        if self.input_long_edge is not None and self.input_long_edge < 32:
            raise ValueError("input_long_edge_invalid")
        if self.columns < 1 or self.rows < 1 or self.columns * self.rows > 4:
            raise ValueError("tile_count_invalid")
        if not 0.0 <= self.overlap < 0.5:
            raise ValueError("tile_overlap_invalid")


CURRENT_SINGLE_PASS = SmallBirdStrategy("current_single_pass", None)
HIGHER_RESOLUTION_ZONE = SmallBirdStrategy("higher_resolution_zone", 1600)
OVERLAPPING_ZONE_TILES = SmallBirdStrategy(
    "overlapping_zone_tiles", 1280, columns=2, rows=2, overlap=0.20
)
SMALL_BIRD_STRATEGIES = (
    CURRENT_SINGLE_PASS,
    HIGHER_RESOLUTION_ZONE,
    OVERLAPPING_ZONE_TILES,
)


def tiled_coordinate_boxes(
    zone: NormalizedBox,
    *,
    columns: int,
    rows: int,
    overlap: float,
) -> tuple[NormalizedBox, ...]:
    """Cover a Zone with a deterministic, bounded set of overlapping tiles."""

    if columns < 1 or rows < 1 or columns * rows > 4:
        raise ValueError("tile_count_invalid")
    if not 0.0 <= overlap < 0.5:
        raise ValueError("tile_overlap_invalid")

    tile_width = zone.width / (columns - (columns - 1) * overlap)
    tile_height = zone.height / (rows - (rows - 1) * overlap)
    step_x = tile_width * (1.0 - overlap)
    step_y = tile_height * (1.0 - overlap)
    tiles: list[NormalizedBox] = []
    for row in range(rows):
        top = zone.top + row * step_y
        bottom = zone.bottom if row == rows - 1 else top + tile_height
        for column in range(columns):
            left = zone.left + column * step_x
            right = zone.right if column == columns - 1 else left + tile_width
            tiles.append(NormalizedBox(left, top, right, bottom))
    return tuple(tiles)


def aspect_preserving_zone_jpeg(
    image: np.ndarray,
    coordinate_box: NormalizedBox,
    *,
    target_long_edge: int | None,
) -> tuple[bytes, tuple[int, int]]:
    """Encode one source-aligned Zone tile without stretching it.

    The returned coordinate box is still in source-normalized coordinates; a
    detector result can therefore map directly back to the monitoring frame.
    """

    if not isinstance(image, np.ndarray) or image.ndim not in {2, 3}:
        raise ValueError("benchmark_image_invalid")
    height, width = image.shape[:2]
    if width < 1 or height < 1:
        raise ValueError("benchmark_image_invalid")
    left = max(0, min(width - 1, math.floor(coordinate_box.left * width)))
    top = max(0, min(height - 1, math.floor(coordinate_box.top * height)))
    right = max(left + 1, min(width, math.ceil(coordinate_box.right * width)))
    bottom = max(top + 1, min(height, math.ceil(coordinate_box.bottom * height)))
    crop = image[top:bottom, left:right]
    crop_height, crop_width = crop.shape[:2]
    if target_long_edge is not None:
        scale = target_long_edge / float(max(crop_width, crop_height))
        resized_width = max(1, round(crop_width * scale))
        resized_height = max(1, round(crop_height * scale))
        if (resized_width, resized_height) != (crop_width, crop_height):
            interpolation = cv2.INTER_AREA if scale < 1.0 else cv2.INTER_CUBIC
            crop = cv2.resize(crop, (resized_width, resized_height), interpolation=interpolation)
    encoded, jpeg = cv2.imencode(".jpg", crop, [cv2.IMWRITE_JPEG_QUALITY, 92])
    if not encoded or len(jpeg) > MEGADETECTOR_MAX_LIVE_CROP_BYTES:
        raise ValueError("benchmark_crop_too_large")
    encoded_height, encoded_width = crop.shape[:2]
    return jpeg.tobytes(), (encoded_width, encoded_height)


def box_iou(left: NormalizedBox, right: NormalizedBox) -> float:
    intersection_left = max(left.left, right.left)
    intersection_top = max(left.top, right.top)
    intersection_right = min(left.right, right.right)
    intersection_bottom = min(left.bottom, right.bottom)
    intersection = max(0.0, intersection_right - intersection_left) * max(
        0.0, intersection_bottom - intersection_top
    )
    union = left.area + right.area - intersection
    return 0.0 if union <= 0.0 else intersection / union


def contains_box(container: NormalizedBox, subject: NormalizedBox, *, tolerance: float = 0.0) -> bool:
    return (
        container.left <= subject.left + tolerance
        and container.top <= subject.top + tolerance
        and container.right + tolerance >= subject.right
        and container.bottom + tolerance >= subject.bottom
    )


def deduplicate_tiled_proposals(
    proposals: Sequence[MegaDetectorProposal],
    *,
    iou_threshold: float = 0.5,
) -> list[MegaDetectorProposal]:
    """Perform stable same-class NMS across overlapping tile outputs."""

    if not 0.0 < iou_threshold <= 1.0:
        raise ValueError("iou_threshold_invalid")
    ordered = sorted(
        (proposal for proposal in proposals if proposal.bbox is not None),
        key=lambda proposal: (
            -proposal.confidence,
            proposal.label,
            proposal.bbox.x if proposal.bbox else 0.0,
            proposal.bbox.y if proposal.bbox else 0.0,
            proposal.bbox.width if proposal.bbox else 0.0,
            proposal.bbox.height if proposal.bbox else 0.0,
        ),
    )
    retained: list[MegaDetectorProposal] = []
    for candidate in ordered:
        assert candidate.bbox is not None
        candidate_box = NormalizedBox.from_megadetector_box(candidate.bbox)
        if any(
            existing.label == candidate.label
            and existing.bbox is not None
            and box_iou(candidate_box, NormalizedBox.from_megadetector_box(existing.bbox))
            >= iou_threshold
            for existing in retained
        ):
            continue
        retained.append(candidate)
    return retained


def run_strategy(
    image: np.ndarray,
    *,
    zone: NormalizedBox,
    strategy: SmallBirdStrategy,
    runner: Callable[[bytes, MegaDetectorBox], list[MegaDetectorProposal]],
) -> tuple[list[MegaDetectorProposal], tuple[tuple[int, int], ...]]:
    """Run one bounded candidate serially through one supplied detector runtime."""

    tiles = tiled_coordinate_boxes(
        zone,
        columns=strategy.columns,
        rows=strategy.rows,
        overlap=strategy.overlap,
    )
    proposals: list[MegaDetectorProposal] = []
    input_sizes: list[tuple[int, int]] = []
    for tile in tiles:
        image_bytes, input_size = aspect_preserving_zone_jpeg(
            image,
            tile,
            target_long_edge=strategy.input_long_edge,
        )
        input_sizes.append(input_size)
        proposals.extend(runner(image_bytes, tile.as_megadetector_box()))
    if len(tiles) > 1:
        proposals = deduplicate_tiled_proposals(proposals)
    return proposals, tuple(input_sizes)


def _frame_box(frame: Mapping[str, object]) -> NormalizedBox | None:
    value = frame.get("manual_bird_box")
    if value is None:
        return None
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ValueError("manual_bird_box_invalid")
    return NormalizedBox.from_xyxy(value)


def _animal_boxes(proposals: Sequence[MegaDetectorProposal]) -> list[NormalizedBox]:
    return [
        NormalizedBox.from_megadetector_box(proposal.bbox)
        for proposal in proposals
        if proposal.label == "animal" and proposal.bbox is not None
    ]


def _ratio(numerator: int, denominator: int) -> float | None:
    return None if denominator == 0 else numerator / denominator


def _percentile(values: Sequence[int], fraction: float) -> int | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, math.ceil(len(ordered) * fraction) - 1))
    return ordered[index]


def evaluation_metrics(
    *,
    frames: Sequence[Mapping[str, object]],
    predictions: Mapping[str, Sequence[MegaDetectorProposal]],
    latencies_ms: Mapping[str, int],
    match_iou_threshold: float = 0.1,
    loose_area_ratio: float = 4.0,
) -> dict[str, object]:
    """Measure detector evidence against human annotations only.

    ``bird_visible=uncertain`` and out-of-target-zone birds remain in the
    manifest but never inflate or deflate feeder-zone precision/recall.
    """

    positive_frames = 0
    negative_frames = 0
    ignored_frames = 0
    hits = 0
    false_positive_frames = 0
    predicted_positive_frames = 0
    containment_hits = 0
    containment_candidates = 0
    clipped_boxes = 0
    loose_boxes = 0
    matched_ious: list[float] = []
    small_positive_frames = 0
    small_hits = 0
    evaluated_latencies: list[int] = []
    by_source: dict[str, dict[str, int]] = defaultdict(
        lambda: {"positive": 0, "hits": 0, "negative": 0, "false_positive": 0}
    )

    for frame in frames:
        frame_id = frame.get("id")
        visible = frame.get("bird_visible")
        source_group = str(frame.get("source_group", "unknown"))
        if not isinstance(frame_id, str):
            raise ValueError("benchmark_frame_id_invalid")
        proposals = predictions.get(frame_id, ())
        animal_boxes = _animal_boxes(proposals)
        if frame_id in latencies_ms:
            evaluated_latencies.append(max(0, int(latencies_ms[frame_id])))
        if visible == "no":
            negative_frames += 1
            by_source[source_group]["negative"] += 1
            if animal_boxes:
                false_positive_frames += 1
                predicted_positive_frames += 1
                by_source[source_group]["false_positive"] += 1
            continue
        if visible != "yes" or frame.get("in_target_zone") is False:
            ignored_frames += 1
            continue

        ground_truth = _frame_box(frame)
        if ground_truth is None:
            raise ValueError("visible_bird_requires_manual_box")
        positive_frames += 1
        by_source[source_group]["positive"] += 1
        is_small_subject = False
        width = frame.get("width")
        height = frame.get("height")
        if isinstance(width, int) and isinstance(height, int):
            longest_side = max(ground_truth.width * width, ground_truth.height * height)
            is_small_subject = longest_side <= 96
            if is_small_subject:
                small_positive_frames += 1
        if frame.get("full_bird_visible") is True:
            containment_candidates += 1
        if animal_boxes:
            predicted_positive_frames += 1
        best_box = max(animal_boxes, key=lambda box: box_iou(box, ground_truth), default=None)
        if best_box is None:
            continue
        overlap = box_iou(best_box, ground_truth)
        if overlap < match_iou_threshold:
            continue
        hits += 1
        by_source[source_group]["hits"] += 1
        matched_ious.append(overlap)
        if frame.get("full_bird_visible") is True:
            if contains_box(best_box, ground_truth, tolerance=0.002):
                containment_hits += 1
            else:
                clipped_boxes += 1
        if best_box.area / ground_truth.area > loose_area_ratio:
            loose_boxes += 1
        if is_small_subject:
            small_hits += 1

    source_summary = {
        group: {
            **counts,
            "recall": _ratio(counts["hits"], counts["positive"]),
            "false_positive_rate": _ratio(counts["false_positive"], counts["negative"]),
        }
        for group, counts in sorted(by_source.items())
    }
    precision_denominator = predicted_positive_frames
    return {
        "visible_bird_frame_recall": _ratio(hits, positive_frames),
        "positive_frames": positive_frames,
        "negative_frames": negative_frames,
        "ignored_frames": ignored_frames,
        "false_positive_frames": false_positive_frames,
        "false_positive_rate": _ratio(false_positive_frames, negative_frames),
        "precision": _ratio(hits, precision_denominator),
        "mean_box_iou": (sum(matched_ious) / len(matched_ious)) if matched_ious else None,
        "full_body_containment": _ratio(containment_hits, containment_candidates),
        "clipped_full_body_boxes": clipped_boxes,
        "excessively_loose_boxes": loose_boxes,
        "small_bird": {
            "definition": "manual bird longest side <= 96 source pixels",
            "positive_frames": small_positive_frames,
            "hits": small_hits,
            "recall": _ratio(small_hits, small_positive_frames),
        },
        "latency_ms": {
            "count": len(evaluated_latencies),
            "median": int(median(evaluated_latencies)) if evaluated_latencies else None,
            "p95": _percentile(evaluated_latencies, 0.95),
            "max": max(evaluated_latencies) if evaluated_latencies else None,
        },
        "by_source": source_summary,
        "safety": {
            "product_writes": False,
            "reviewed_truth_created": False,
            "model_score_used_as_ground_truth": False,
        },
    }


def track_sequence_metrics(
    *,
    frames: Sequence[Mapping[str, object]],
    predictions: Mapping[str, Sequence[MegaDetectorProposal]],
    association_iou: float = 0.2,
    max_gap_frames: int = 1,
) -> dict[str, object]:
    """Report simple bounded ordered-sequence continuity for benchmark evidence."""

    sequences: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    for frame in frames:
        sequence_id = frame.get("sequence_id")
        if isinstance(sequence_id, str):
            sequences[sequence_id].append(frame)
    results: list[dict[str, object]] = []
    for sequence_id, sequence_frames in sorted(sequences.items()):
        ordered = sorted(sequence_frames, key=lambda frame: int(frame.get("sequence_order", 0)))
        tracks: list[dict[str, object]] = []
        for index, frame in enumerate(ordered):
            frame_id = frame.get("id")
            if not isinstance(frame_id, str):
                continue
            boxes = _animal_boxes(predictions.get(frame_id, ()))
            for box in boxes:
                candidates = [
                    track
                    for track in tracks
                    if index - int(track["last_index"]) <= max_gap_frames + 1
                ]
                match = max(
                    candidates,
                    key=lambda track: box_iou(box, track["last_box"]),
                    default=None,
                )
                if match is not None and box_iou(box, match["last_box"]) >= association_iou:
                    match["last_box"] = box
                    match["last_index"] = index
                    match["hits"] = int(match["hits"]) + 1
                else:
                    tracks.append({"last_box": box, "last_index": index, "hits": 1})
        results.append(
            {
                "sequence_id": sequence_id,
                "frame_count": len(ordered),
                "track_count": len(tracks),
                "coherent_single_subject": len(tracks) == 1 and bool(tracks),
                "max_track_hits": max((int(track["hits"]) for track in tracks), default=0),
            }
        )
    return {
        "sequence_count": len(results),
        "results": results,
        "note": (
            "No ordered benchmark sequence was available."
            if not results
            else "Sequence continuity is an offline evidence metric; it creates no product records."
        ),
    }


def proposal_as_dict(proposal: MegaDetectorProposal) -> dict[str, object]:
    payload: dict[str, object] = {
        "label": proposal.label,
        "confidence": proposal.confidence,
    }
    if proposal.bbox is not None:
        payload["bbox"] = [
            proposal.bbox.x,
            proposal.bbox.y,
            proposal.bbox.x + proposal.bbox.width,
            proposal.bbox.y + proposal.bbox.height,
        ]
    return payload

