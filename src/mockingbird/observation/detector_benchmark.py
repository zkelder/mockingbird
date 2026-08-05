"""Deterministic, shadow-only detector precision/recall calibration benchmark.

Observation Engine v2 Stage 6.2. This module is pure: no model inference, no
camera/network access, no product repository import, and no filesystem I/O.
It scores already-decoded `DetectionObservation` facts against a reviewed
`CalibrationManifest` truth set across an explicit bounded score-threshold
grid, clusters recurring static false-positive geometry, simulates bounded
temporal confirmation policies over recorded detections, and classifies
candidate follow-up actions. It never selects or mutates a runtime threshold,
Ignore region, or tracker setting; every output remains diagnostic evidence
with no production authority. See
docs/detector-calibration-benchmark-contract.md.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass
from typing import Literal

from mockingbird.observation.contracts import DetectionObservation
from mockingbird.observation.replay import semantic_fingerprint

MANIFEST_VERSION = 1
REPORT_SCHEMA_VERSION = 1
BENCHMARK_VERSION = "detector-calibration-v1"

# One explicit IoU for all reviewed-box truth matching (shared with the
# existing Stage 2 replay detection metrics for cross-tool consistency).
MATCH_IOU_THRESHOLD = 0.5
# A looser IoU used only to group recurring false-positive geometry across
# frames from the same fixed scene; a box that shifts slightly between two
# otherwise-identical detections of the same static object should still
# cluster even if it would not count as a "duplicate" of a single instant.
CLUSTER_IOU_THRESHOLD = 0.3
CLUSTER_CENTROID_THRESHOLD = 0.05
CLUSTER_SCORE_BAND = 0.15
CLUSTER_MIN_RECURRENCE = 2

DEFAULT_THRESHOLD_GRID: tuple[float, ...] = (0.02, 0.05, 0.1, 0.15, 0.2, 0.3, 0.5, 0.7, 0.9)
# The one-run anchor decode must gate strictly below every requested sweep
# threshold. NMS suppression only ever lets a higher-scored box suppress a
# lower-scored one (never the reverse), so decoding once at
# `min(grid) - ANCHOR_MARGIN` and then filtering the surviving set with
# `score >= threshold` for each row reproduces exactly what a fresh decode at
# that threshold would keep -- the anchor pass is a safe, deterministic
# substitute for re-running inference once per threshold.
ANCHOR_MARGIN = 0.01

MIN_CONFIDENCE_INTERVAL_SAMPLE = 10
STRONG_DETECTION_SCORE_DEFAULT = 0.7
TEMPORAL_MINIMUM_SPAN_MS = 1000
TEMPORAL_MAX_GAP_MS = 2000

MAX_FRAMES = 5_000
MAX_BOXES_PER_FRAME = 64
MAX_PRIVACY_REGIONS_PER_FRAME = 32
MAX_SCENE_STRUCTURES = 64
MAX_THRESHOLDS = 32
MAX_STRING_LENGTH = 2048

AnimalPresence = Literal["yes", "no", "ambiguous"]


class DetectorBenchmarkError(ValueError):
    """A bounded detector-benchmark validation or execution failure code."""


def _valid_box(box: tuple[float, float, float, float]) -> bool:
    return (
        len(box) == 4
        and all(isinstance(value, (int, float)) and not isinstance(value, bool) for value in box)
        and all(0.0 <= float(value) <= 1.0 for value in box)
        and box[0] < box[2]
        and box[1] < box[3]
    )


def _iou(first: tuple[float, float, float, float], second: tuple[float, float, float, float]) -> float:
    left, top = max(first[0], second[0]), max(first[1], second[1])
    right, bottom = min(first[2], second[2]), min(first[3], second[3])
    intersection = max(0.0, right - left) * max(0.0, bottom - top)
    first_area = (first[2] - first[0]) * (first[3] - first[1])
    second_area = (second[2] - second[0]) * (second[3] - second[1])
    union = first_area + second_area - intersection
    return 0.0 if union <= 0 else intersection / union


def _centroid(box: tuple[float, float, float, float]) -> tuple[float, float]:
    return ((box[0] + box[2]) / 2.0, (box[1] + box[3]) / 2.0)


def _centroid_distance(first: tuple[float, float, float, float], second: tuple[float, float, float, float]) -> float:
    fx, fy = _centroid(first)
    sx, sy = _centroid(second)
    return ((fx - sx) ** 2 + (fy - sy) ** 2) ** 0.5


def _centroid_in_region(box: tuple[float, float, float, float], region: tuple[float, float, float, float]) -> bool:
    x, y = _centroid(box)
    return region[0] <= x <= region[2] and region[1] <= y <= region[3]


# --------------------------------------------------------------------------
# Reviewed truth manifest
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class ReviewedBox:
    """One reviewer-drawn animal box, in the frame's own normalized space."""

    box: tuple[float, float, float, float]
    broad_class: str = "animal"

    def __post_init__(self) -> None:
        if not _valid_box(self.box):
            raise DetectorBenchmarkError("invalid_reviewed_box")
        if not self.broad_class or len(self.broad_class) > 64:
            raise DetectorBenchmarkError("invalid_reviewed_box_class")


@dataclass(frozen=True)
class StaticStructure:
    """A human-identified static scene structure, for cross-referencing
    algorithmic false-positive clusters against a real, reviewed cause
    (for example the specific feeder pole or a patch of tree bark). This is
    descriptive evidence only; it is never used to suppress a detection or
    create an Ignore region."""

    label: str
    box: tuple[float, float, float, float]
    note: str | None = None

    def __post_init__(self) -> None:
        if not self.label or len(self.label) > 128:
            raise DetectorBenchmarkError("invalid_static_structure_label")
        if not _valid_box(self.box):
            raise DetectorBenchmarkError("invalid_static_structure_box")
        if self.note is not None and len(self.note) > MAX_STRING_LENGTH:
            raise DetectorBenchmarkError("invalid_static_structure_note")


@dataclass(frozen=True)
class CalibrationFrame:
    """One reviewed-truth record for a single logical analysis frame."""

    frame_id: str
    image_path: str
    content_hash: str | None
    width: int
    height: int
    animal_present: AnimalPresence
    boxes: tuple[ReviewedBox, ...] = ()
    scorable: bool = True
    occlusion: str | None = None
    blur: str | None = None
    clipped: bool | None = None
    distance: str | None = None
    privacy_ignore_regions: tuple[tuple[float, float, float, float], ...] = ()
    scene_group: str = "default"
    sequence_id: str | None = None
    sequence_order: int | None = None
    source_offset_ms: int | None = None
    provenance: str = ""
    reviewer_note: str = ""

    def __post_init__(self) -> None:
        if not self.frame_id or len(self.frame_id) > 256:
            raise DetectorBenchmarkError("invalid_frame_id")
        if self.width < 1 or self.height < 1:
            raise DetectorBenchmarkError("invalid_frame_dimensions")
        if self.animal_present not in ("yes", "no", "ambiguous"):
            raise DetectorBenchmarkError("invalid_animal_present")
        if len(self.boxes) > MAX_BOXES_PER_FRAME:
            raise DetectorBenchmarkError("frame_box_limit")
        if self.animal_present != "yes" and self.boxes:
            # Ambiguous frames must not silently imply negative *or* positive
            # truth: a box is only meaningful once a reviewer has committed to
            # "yes". A "no"/"ambiguous" frame with a box is an authoring bug,
            # not data the benchmark should interpret.
            raise DetectorBenchmarkError("boxes_require_animal_present_yes")
        if self.animal_present == "yes" and self.scorable and not self.boxes:
            # A reviewer who is confident enough to say "yes" but not
            # confident enough to draw a box should mark the frame
            # unscorable instead; box-level truth-aware matching has nothing
            # to work with otherwise, and silently treating every detector
            # box on the frame as a false positive would be dishonest.
            raise DetectorBenchmarkError("scorable_animal_present_yes_requires_boxes")
        if len(self.privacy_ignore_regions) > MAX_PRIVACY_REGIONS_PER_FRAME:
            raise DetectorBenchmarkError("frame_privacy_region_limit")
        if any(not _valid_box(region) for region in self.privacy_ignore_regions):
            raise DetectorBenchmarkError("invalid_privacy_region")
        if not self.scene_group or len(self.scene_group) > 256:
            raise DetectorBenchmarkError("invalid_scene_group")
        if self.sequence_order is not None and self.sequence_order < 0:
            raise DetectorBenchmarkError("invalid_sequence_order")
        if self.source_offset_ms is not None and self.source_offset_ms < 0:
            raise DetectorBenchmarkError("invalid_source_offset_ms")
        for text in (self.provenance, self.reviewer_note):
            if len(text) > MAX_STRING_LENGTH:
                raise DetectorBenchmarkError("invalid_frame_text")

    @property
    def is_scorable(self) -> bool:
        return self.scorable and self.animal_present != "ambiguous"


@dataclass(frozen=True)
class CalibrationManifest:
    """A versioned, reviewed detector-calibration truth cohort."""

    version: int
    cohort_id: str
    annotation_policy: str
    frames: tuple[CalibrationFrame, ...]
    scene_static_structures: dict[str, tuple[StaticStructure, ...]] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.scene_static_structures is None:
            object.__setattr__(self, "scene_static_structures", {})
        if self.version != MANIFEST_VERSION:
            raise DetectorBenchmarkError("unsupported_manifest_version")
        if not self.cohort_id or len(self.cohort_id) > 256:
            raise DetectorBenchmarkError("invalid_cohort_id")
        if not self.frames or len(self.frames) > MAX_FRAMES:
            raise DetectorBenchmarkError("frame_limit")
        ids = [frame.frame_id for frame in self.frames]
        if len(ids) != len(set(ids)):
            raise DetectorBenchmarkError("duplicate_frame_id")
        if len(self.scene_static_structures) > MAX_SCENE_STRUCTURES:
            raise DetectorBenchmarkError("scene_structure_limit")

    @property
    def fingerprint(self) -> str:
        # `image_path` is deliberately excluded: it is a relative name that
        # can legitimately differ between two otherwise-identical cohort
        # copies, while `content_hash` already proves byte-identical image
        # content. Nothing here is an absolute path.
        value = {
            "version": self.version,
            "cohort_id": self.cohort_id,
            "annotation_policy": self.annotation_policy,
            "frames": [
                {**asdict(frame), "boxes": [asdict(box) for box in frame.boxes], "image_path": None}
                for frame in sorted(self.frames, key=lambda item: item.frame_id)
            ],
            "scene_static_structures": {
                scene: [asdict(item) for item in structures]
                for scene, structures in sorted(self.scene_static_structures.items())
            },
        }
        return semantic_fingerprint(value)

    def frame(self, frame_id: str) -> CalibrationFrame:
        for frame in self.frames:
            if frame.frame_id == frame_id:
                return frame
        raise DetectorBenchmarkError("unknown_frame_id")


# --------------------------------------------------------------------------
# Threshold grid
# --------------------------------------------------------------------------


def effective_threshold_grid(
    configured_threshold: float,
    grid: tuple[float, ...] = DEFAULT_THRESHOLD_GRID,
) -> tuple[float, ...]:
    """Merge the live configured threshold into the candidate grid.

    Bounded to valid model scores (0, 1], deterministically sorted and
    deduplicated, with the currently configured value always present so a
    reader can compare every other row against "what is deployed today"."""

    if not 0.0 < configured_threshold <= 1.0:
        raise DetectorBenchmarkError("invalid_configured_threshold")
    values = {round(float(value), 6) for value in grid if 0.0 < float(value) <= 1.0}
    values.add(round(float(configured_threshold), 6))
    if len(values) > MAX_THRESHOLDS:
        raise DetectorBenchmarkError("threshold_grid_limit")
    return tuple(sorted(values))


def anchor_score_threshold(thresholds: tuple[float, ...]) -> float:
    """The one safe low-water decode threshold for the whole sweep (see
    `ANCHOR_MARGIN`)."""

    if not thresholds:
        raise DetectorBenchmarkError("empty_threshold_grid")
    return max(0.0, min(thresholds) - ANCHOR_MARGIN)


# --------------------------------------------------------------------------
# Per-frame, per-threshold classification
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class ClassifiedDetection:
    observation_id: str | None
    confidence: float
    bounding_box: tuple[float, float, float, float]
    outcome: Literal["true_positive", "false_positive", "duplicate", "privacy_excluded"]


@dataclass(frozen=True)
class FrameClassification:
    frame_id: str
    scene_group: str
    threshold: float
    scorable: bool
    animal_present: AnimalPresence
    true_positive_count: int = 0
    false_positive_count: int = 0
    false_negative_below_threshold_count: int = 0
    false_negative_privacy_masked_count: int = 0
    false_negative_true_miss_count: int = 0
    duplicate_count: int = 0
    privacy_excluded_count: int = 0
    detections: tuple[ClassifiedDetection, ...] = ()


def _sorted_animal_detections(
    detections: tuple[DetectionObservation, ...], *, threshold: float
) -> list[DetectionObservation]:
    eligible = [item for item in detections if item.is_animal and (item.confidence or 0.0) >= threshold]
    # Stable regardless of upstream ordering: descending score, then a fully
    # deterministic tiebreak on box/observation id.
    return sorted(
        eligible,
        key=lambda item: (
            -(item.confidence or 0.0),
            item.bounding_box or (0.0, 0.0, 0.0, 0.0),
            item.observation_id or "",
        ),
    )


def _collapse_duplicates(
    detections: list[DetectionObservation],
) -> tuple[list[DetectionObservation], list[DetectionObservation]]:
    """Greedy same-class NMS-style collapse at `MATCH_IOU_THRESHOLD`.

    `detections` must already be sorted by descending confidence (a stable
    order); a later, lower- (or equal-) scored box that overlaps an
    already-kept box is a duplicate of it, never the reverse, so the result
    does not depend on input ordering beyond that stable sort key."""

    kept: list[DetectionObservation] = []
    duplicates: list[DetectionObservation] = []
    for candidate in detections:
        box = candidate.bounding_box
        if box is not None and any(
            existing.bounding_box is not None
            and existing.label == candidate.label
            and _iou(box, existing.bounding_box) >= MATCH_IOU_THRESHOLD
            for existing in kept
        ):
            duplicates.append(candidate)
        else:
            kept.append(candidate)
    return kept, duplicates


def classify_frame(
    frame: CalibrationFrame,
    raw_detections: tuple[DetectionObservation, ...],
    *,
    threshold: float,
) -> FrameClassification:
    """Classify one frame's detector output at one threshold.

    `raw_detections` must be the *anchor*-threshold decode for this frame
    (every observation with confidence at or above the sweep's lowest
    threshold); this function itself performs the `>= threshold` filter, the
    privacy/ignore exclusion, deduplication, and truth matching for exactly
    one row of the sweep."""

    if not frame.is_scorable:
        return FrameClassification(
            frame.frame_id, frame.scene_group, threshold, False, frame.animal_present,
        )

    eligible = _sorted_animal_detections(raw_detections, threshold=threshold)
    privacy_excluded = [
        item for item in eligible
        if any(_centroid_in_region(item.bounding_box, region) for region in frame.privacy_ignore_regions)
        if item.bounding_box is not None
    ]
    remaining = [item for item in eligible if item not in privacy_excluded]
    kept, duplicates = _collapse_duplicates(remaining)

    classified: list[ClassifiedDetection] = [
        ClassifiedDetection(item.observation_id, item.confidence or 0.0, item.bounding_box, "privacy_excluded")
        for item in privacy_excluded
        if item.bounding_box is not None
    ] + [
        ClassifiedDetection(item.observation_id, item.confidence or 0.0, item.bounding_box, "duplicate")
        for item in duplicates
        if item.bounding_box is not None
    ]

    if frame.animal_present == "no":
        for item in kept:
            if item.bounding_box is not None:
                classified.append(ClassifiedDetection(item.observation_id, item.confidence or 0.0, item.bounding_box, "false_positive"))
        return FrameClassification(
            frame.frame_id, frame.scene_group, threshold, True, frame.animal_present,
            false_positive_count=len(kept),
            duplicate_count=len(duplicates),
            privacy_excluded_count=len(privacy_excluded),
            detections=tuple(classified),
        )

    # animal_present == "yes": greedy truth-box matching, stable regardless
    # of input order.
    truth_boxes = sorted(frame.boxes, key=lambda item: item.box)
    unmatched_predictions = list(kept)
    true_positive_count = 0
    below_threshold = 0
    privacy_masked_fn = 0
    true_miss = 0
    for truth in truth_boxes:
        candidates = [
            prediction for prediction in unmatched_predictions
            if prediction.bounding_box is not None and _iou(truth.box, prediction.bounding_box) >= MATCH_IOU_THRESHOLD
        ]
        if candidates:
            best = max(
                candidates,
                key=lambda item: (_iou(truth.box, item.bounding_box), item.observation_id or ""),
            )
            unmatched_predictions.remove(best)
            true_positive_count += 1
            classified.append(ClassifiedDetection(best.observation_id, best.confidence or 0.0, best.bounding_box, "true_positive"))
            continue
        # No prediction survived at this threshold. Did any raw (anchor-level)
        # detection overlap this truth box at all? Distinguish *why* it did
        # not survive: a genuinely lower-scored, non-masked candidate is
        # recoverable by lowering the threshold; a candidate that only ever
        # existed inside a Privacy/Ignore region would stay excluded at any
        # threshold, so it is a privacy exclusion, not a threshold problem;
        # no overlapping candidate at all, even at the anchor floor, is a
        # true detector miss that no threshold change can fix.
        overlapping_raw = [
            item for item in raw_detections
            if item.is_animal and item.bounding_box is not None
            and _iou(truth.box, item.bounding_box) >= MATCH_IOU_THRESHOLD
        ]
        overlapping_masked = [
            item for item in overlapping_raw
            if any(_centroid_in_region(item.bounding_box, region) for region in frame.privacy_ignore_regions)
        ]
        if len(overlapping_masked) < len(overlapping_raw):
            below_threshold += 1
        elif overlapping_masked:
            privacy_masked_fn += 1
        else:
            true_miss += 1

    for leftover in unmatched_predictions:
        if leftover.bounding_box is not None:
            classified.append(ClassifiedDetection(leftover.observation_id, leftover.confidence or 0.0, leftover.bounding_box, "false_positive"))

    return FrameClassification(
        frame.frame_id, frame.scene_group, threshold, True, frame.animal_present,
        true_positive_count=true_positive_count,
        false_positive_count=len(unmatched_predictions),
        false_negative_below_threshold_count=below_threshold,
        false_negative_privacy_masked_count=privacy_masked_fn,
        false_negative_true_miss_count=true_miss,
        duplicate_count=len(duplicates),
        privacy_excluded_count=len(privacy_excluded),
        detections=tuple(classified),
    )


# --------------------------------------------------------------------------
# Threshold-sweep aggregation
# --------------------------------------------------------------------------


def _ratio(numerator: int, denominator: int) -> float | None:
    return None if denominator <= 0 else numerator / denominator


@dataclass(frozen=True)
class ScoreDistribution:
    count: int
    minimum: float | None = None
    median: float | None = None
    maximum: float | None = None


def _score_distribution(values: list[float]) -> ScoreDistribution:
    if not values:
        return ScoreDistribution(0)
    ordered = sorted(values)
    mid = len(ordered) // 2
    median = ordered[mid] if len(ordered) % 2 else (ordered[mid - 1] + ordered[mid]) / 2.0
    return ScoreDistribution(len(ordered), ordered[0], median, ordered[-1])


@dataclass(frozen=True)
class ConfidenceInterval:
    lower: float
    upper: float
    method: str = "wilson-score-95"


def _wilson_interval(successes: int, total: int, *, z: float = 1.959963984540054) -> ConfidenceInterval | None:
    """A 95% Wilson score interval for a proportion.

    Deliberately withheld (returns None) below `MIN_CONFIDENCE_INTERVAL_SAMPLE`
    rather than reporting a wide, misleading interval from a handful of
    frames; callers must treat `None` as "sample size does not support an
    interval", not as zero uncertainty."""

    if total < MIN_CONFIDENCE_INTERVAL_SAMPLE:
        return None
    phat = successes / total
    denominator = 1 + z * z / total
    center = (phat + z * z / (2 * total)) / denominator
    margin = (z * ((phat * (1 - phat) + z * z / (4 * total)) / total) ** 0.5) / denominator
    return ConfidenceInterval(max(0.0, center - margin), min(1.0, center + margin))


@dataclass(frozen=True)
class SceneGroupMetrics:
    scene_group: str
    scorable_positive_frames: int
    scorable_negative_frames: int
    true_positives: int
    false_positives: int
    false_negatives: int
    precision: float | None
    recall: float | None


@dataclass(frozen=True)
class ThresholdMetrics:
    threshold: float
    is_configured_threshold: bool
    scorable_positive_frames: int
    scorable_negative_frames: int
    ambiguous_or_unscorable_frame_count: int
    true_positives: int
    false_positives: int
    false_positives_on_negative_frames: int
    false_positives_on_positive_frames: int
    false_negatives_below_threshold: int
    false_negatives_privacy_masked: int
    false_negatives_true_miss: int
    duplicate_detections: int
    privacy_excluded_detections: int
    false_positive_frame_count: int
    precision: float | None
    recall: float | None
    f1_descriptive_only: float | None
    false_positives_per_negative_frame: float | None
    positive_frame_recall: float | None
    precision_confidence_interval: ConfidenceInterval | None
    recall_confidence_interval: ConfidenceInterval | None
    true_positive_score_distribution: ScoreDistribution
    false_positive_score_distribution: ScoreDistribution
    scene_group_breakdown: tuple[SceneGroupMetrics, ...]


def _aggregate_scene_metrics(scene_group: str, classifications: list[FrameClassification]) -> SceneGroupMetrics:
    positive = [item for item in classifications if item.animal_present == "yes"]
    negative = [item for item in classifications if item.animal_present == "no"]
    tp = sum(item.true_positive_count for item in classifications)
    fp = sum(item.false_positive_count for item in classifications)
    fn = sum(
        item.false_negative_below_threshold_count
        + item.false_negative_privacy_masked_count
        + item.false_negative_true_miss_count
        for item in classifications
    )
    return SceneGroupMetrics(
        scene_group, len(positive), len(negative), tp, fp, fn,
        _ratio(tp, tp + fp), _ratio(tp, tp + fn),
    )


def _threshold_metrics(classifications: list[FrameClassification], *, threshold: float, is_configured: bool) -> ThresholdMetrics:
    scorable = [item for item in classifications if item.scorable]
    positive = [item for item in scorable if item.animal_present == "yes"]
    negative = [item for item in scorable if item.animal_present == "no"]
    unscorable_count = len(classifications) - len(scorable)

    true_positives = sum(item.true_positive_count for item in scorable)
    fp_negative = sum(item.false_positive_count for item in negative)
    fp_positive = sum(item.false_positive_count for item in positive)
    false_negatives_below = sum(item.false_negative_below_threshold_count for item in scorable)
    false_negatives_masked = sum(item.false_negative_privacy_masked_count for item in scorable)
    false_negatives_miss = sum(item.false_negative_true_miss_count for item in scorable)
    duplicates = sum(item.duplicate_count for item in classifications)
    privacy_excluded = sum(item.privacy_excluded_count for item in classifications)
    false_positive_frames = sum(1 for item in negative if item.false_positive_count > 0)

    total_fp = fp_negative + fp_positive
    total_fn = false_negatives_below + false_negatives_masked + false_negatives_miss
    precision = _ratio(true_positives, true_positives + total_fp)
    recall = _ratio(true_positives, true_positives + total_fn)
    f1 = (
        2 * precision * recall / (precision + recall)
        if precision is not None and recall is not None and (precision + recall) > 0
        else None
    )
    positive_frame_recall = _ratio(sum(1 for item in positive if item.true_positive_count > 0), len(positive))

    true_positive_scores = [
        detection.confidence for item in scorable for detection in item.detections if detection.outcome == "true_positive"
    ]
    false_positive_scores = [
        detection.confidence for item in scorable for detection in item.detections if detection.outcome == "false_positive"
    ]

    scenes: dict[str, list[FrameClassification]] = defaultdict(list)
    for item in classifications:
        scenes[item.scene_group].append(item)
    scene_breakdown = tuple(
        _aggregate_scene_metrics(scene, items) for scene, items in sorted(scenes.items())
    )

    return ThresholdMetrics(
        threshold=threshold,
        is_configured_threshold=is_configured,
        scorable_positive_frames=len(positive),
        scorable_negative_frames=len(negative),
        ambiguous_or_unscorable_frame_count=unscorable_count,
        true_positives=true_positives,
        false_positives=total_fp,
        false_positives_on_negative_frames=fp_negative,
        false_positives_on_positive_frames=fp_positive,
        false_negatives_below_threshold=false_negatives_below,
        false_negatives_privacy_masked=false_negatives_masked,
        false_negatives_true_miss=false_negatives_miss,
        duplicate_detections=duplicates,
        privacy_excluded_detections=privacy_excluded,
        false_positive_frame_count=false_positive_frames,
        precision=precision,
        recall=recall,
        f1_descriptive_only=f1,
        false_positives_per_negative_frame=_ratio(fp_negative, len(negative)),
        positive_frame_recall=positive_frame_recall,
        precision_confidence_interval=_wilson_interval(true_positives, true_positives + total_fp) if precision is not None else None,
        recall_confidence_interval=_wilson_interval(true_positives, true_positives + total_fn) if recall is not None else None,
        true_positive_score_distribution=_score_distribution(true_positive_scores),
        false_positive_score_distribution=_score_distribution(false_positive_scores),
        scene_group_breakdown=scene_breakdown,
    )


def sweep_thresholds(
    manifest: CalibrationManifest,
    detections_by_frame: dict[str, tuple[DetectionObservation, ...]],
    thresholds: tuple[float, ...],
    *,
    configured_threshold: float,
) -> tuple[ThresholdMetrics, ...]:
    """Score every already-decoded anchor observation across the whole grid.

    `detections_by_frame` must contain the *anchor*-threshold decode (see
    `anchor_score_threshold`); no inference happens here, so the grid can be
    swept as many times as needed with no additional CUDA/CPU model work."""

    if not thresholds:
        raise DetectorBenchmarkError("empty_threshold_grid")
    ordered_frames = sorted(manifest.frames, key=lambda item: item.frame_id)
    results = []
    for threshold in sorted(set(round(float(value), 6) for value in thresholds)):
        classifications = [
            classify_frame(frame, detections_by_frame.get(frame.frame_id, ()), threshold=threshold)
            for frame in ordered_frames
        ]
        results.append(
            _threshold_metrics(
                classifications, threshold=threshold,
                is_configured=abs(threshold - configured_threshold) < 1e-9,
            )
        )
    return tuple(results)


# --------------------------------------------------------------------------
# Static false-positive clustering
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class ClusterMember:
    frame_id: str
    confidence: float
    bounding_box: tuple[float, float, float, float]


@dataclass(frozen=True)
class FalsePositiveCluster:
    cluster_id: str
    scene_group: str
    broad_class: str
    member_count: int
    frame_ids: tuple[str, ...]
    representative_box: tuple[float, float, float, float]
    score_minimum: float
    score_maximum: float
    matched_static_structure: str | None
    members: tuple[ClusterMember, ...]


@dataclass(frozen=True)
class StaticClusterReport:
    threshold: float
    clusters: tuple[FalsePositiveCluster, ...]
    independent_false_positive_count: int


def _mean_box(boxes: list[tuple[float, float, float, float]]) -> tuple[float, float, float, float]:
    count = len(boxes)
    return tuple(round(sum(box[index] for box in boxes) / count, 6) for index in range(4))  # type: ignore[return-value]


def cluster_static_false_positives(
    manifest: CalibrationManifest,
    detections_by_frame: dict[str, tuple[DetectionObservation, ...]],
    *,
    threshold: float,
) -> StaticClusterReport:
    """Group recurring false-positive geometry within the same scene_group.

    This is diagnostic evidence only: it never creates or implies an Ignore
    region. Different scene groups never cluster together, since a shared
    static cause can only exist within one fixed camera framing."""

    false_positives: list[tuple[str, str, tuple[float, float, float, float], float]] = []
    for frame in manifest.frames:
        if not frame.is_scorable:
            continue
        classification = classify_frame(frame, detections_by_frame.get(frame.frame_id, ()), threshold=threshold)
        for detection in classification.detections:
            if detection.outcome == "false_positive":
                false_positives.append((frame.scene_group, frame.frame_id, detection.bounding_box, detection.confidence))

    # Deterministic regardless of upstream ordering.
    false_positives.sort(key=lambda item: (item[0], item[2], item[1], item[3]))

    groups: list[dict[str, object]] = []
    for scene_group, frame_id, box, confidence in false_positives:
        match = None
        for group in groups:
            if group["scene_group"] != scene_group:
                continue
            representative = group["representative_box"]
            score_range = group["scores"]
            score_reference = (min(score_range) + max(score_range)) / 2.0
            if (
                _iou(box, representative) >= CLUSTER_IOU_THRESHOLD
                and _centroid_distance(box, representative) <= CLUSTER_CENTROID_THRESHOLD
                and abs(confidence - score_reference) <= CLUSTER_SCORE_BAND
            ):
                match = group
                break
        if match is None:
            groups.append({
                "scene_group": scene_group,
                "boxes": [box],
                "representative_box": box,
                "frame_ids": {frame_id},
                "scores": [confidence],
                "members": [ClusterMember(frame_id, confidence, box)],
            })
        else:
            match["boxes"].append(box)  # type: ignore[union-attr]
            match["representative_box"] = _mean_box(match["boxes"])  # type: ignore[arg-type]
            match["frame_ids"].add(frame_id)  # type: ignore[union-attr]
            match["scores"].append(confidence)  # type: ignore[union-attr]
            match["members"].append(ClusterMember(frame_id, confidence, box))  # type: ignore[union-attr]

    clusters: list[FalsePositiveCluster] = []
    independent = 0
    for group in groups:
        frame_ids = tuple(sorted(group["frame_ids"]))  # type: ignore[arg-type]
        if len(frame_ids) < CLUSTER_MIN_RECURRENCE:
            independent += len(group["members"])  # type: ignore[arg-type]
            continue
        scene_group = group["scene_group"]
        representative = group["representative_box"]
        structures = manifest.scene_static_structures.get(scene_group, ())  # type: ignore[union-attr]
        matched_label = next(
            (
                structure.label for structure in structures
                if _iou(representative, structure.box) > 0.0 or _centroid_in_region(representative, structure.box)
            ),
            None,
        )
        scores = group["scores"]  # type: ignore[assignment]
        cluster_id = semantic_fingerprint((scene_group, [round(value, 4) for value in representative]))[:16]
        clusters.append(FalsePositiveCluster(
            cluster_id=cluster_id,
            scene_group=scene_group,  # type: ignore[arg-type]
            broad_class="animal",
            member_count=len(group["members"]),  # type: ignore[arg-type]
            frame_ids=frame_ids,
            representative_box=representative,  # type: ignore[arg-type]
            score_minimum=min(scores),  # type: ignore[arg-type]
            score_maximum=max(scores),  # type: ignore[arg-type]
            matched_static_structure=matched_label,
            members=tuple(sorted(group["members"], key=lambda item: (item.frame_id, item.confidence))),  # type: ignore[arg-type]
        ))

    clusters.sort(key=lambda item: (item.scene_group, item.representative_box))
    return StaticClusterReport(threshold=threshold, clusters=tuple(clusters), independent_false_positive_count=independent)


# --------------------------------------------------------------------------
# Temporal confirmation-policy simulation
# --------------------------------------------------------------------------

TEMPORAL_POLICIES = (
    "single_detection",
    "two_detections",
    "two_distinct_frames",
    "minimum_temporal_span",
    "spatial_coherence",
    "score_aggregation",
    "detector_plus_tracker_confirmation",
)
SPATIAL_COHERENCE_CENTROID_BOUND = 0.15


@dataclass(frozen=True)
class TemporalPolicyResult:
    policy: str
    supported: bool
    sequences_evaluated: int
    sequences_skipped_insufficient_frames: int
    confirmed_true_appearances: int
    confirmed_false_episodes: int
    missed_true_appearances: int
    fragmented_episode_count: int | None
    precision: float | None
    recall: float | None
    unsupported_limitations: tuple[str, ...] = ()


def _sequence_groups(manifest: CalibrationManifest) -> dict[str, tuple[CalibrationFrame, ...]]:
    groups: dict[str, list[CalibrationFrame]] = defaultdict(list)
    for frame in manifest.frames:
        if not frame.is_scorable:
            continue
        key = frame.sequence_id or f"__singleton__:{frame.frame_id}"
        groups[key].append(frame)
    return {
        key: tuple(sorted(
            frames,
            key=lambda item: (
                item.sequence_order if item.sequence_order is not None else 0,
                item.source_offset_ms if item.source_offset_ms is not None else 0,
                item.frame_id,
            ),
        ))
        for key, frames in sorted(groups.items())
    }


def _qualifying_detections_by_frame(
    sequence: tuple[CalibrationFrame, ...],
    detections_by_frame: dict[str, tuple[DetectionObservation, ...]],
    *,
    threshold: float,
) -> dict[str, tuple[ClassifiedDetection, ...]]:
    result = {}
    for frame in sequence:
        classification = classify_frame(frame, detections_by_frame.get(frame.frame_id, ()), threshold=threshold)
        result[frame.frame_id] = tuple(
            detection for detection in classification.detections
            if detection.outcome in ("true_positive", "false_positive")
        )
    return result


def _policy_fires(
    policy: str,
    sequence: tuple[CalibrationFrame, ...],
    qualifying: dict[str, tuple[ClassifiedDetection, ...]],
) -> bool | None:
    """Return True/False, or None when this sequence cannot be evaluated for
    this policy (missing timing facts)."""

    all_detections = [detection for frame in sequence for detection in qualifying[frame.frame_id]]
    frames_with_detection = [frame for frame in sequence if qualifying[frame.frame_id]]

    if policy == "single_detection":
        return len(all_detections) >= 1
    if policy == "two_detections":
        return len(all_detections) >= 2
    if policy == "two_distinct_frames":
        return len(frames_with_detection) >= 2
    if policy == "minimum_temporal_span":
        if any(frame.source_offset_ms is None for frame in frames_with_detection):
            return None
        if len(frames_with_detection) < 2:
            return False
        offsets = [frame.source_offset_ms for frame in frames_with_detection]  # type: ignore[misc]
        return (max(offsets) - min(offsets)) >= TEMPORAL_MINIMUM_SPAN_MS
    if policy == "spatial_coherence":
        if len(all_detections) < 2:
            return False
        boxes = [detection.bounding_box for detection in all_detections]
        return all(
            _centroid_distance(first, second) <= SPATIAL_COHERENCE_CENTROID_BOUND
            for index, first in enumerate(boxes)
            for second in boxes[index + 1:]
        )
    if policy == "score_aggregation":
        if any(detection.confidence >= STRONG_DETECTION_SCORE_DEFAULT for detection in all_detections):
            return True
        return len(all_detections) >= 2
    raise DetectorBenchmarkError(f"unknown_temporal_policy:{policy}")


def _fragmentation_count(
    sequence: tuple[CalibrationFrame, ...],
    qualifying: dict[str, tuple[ClassifiedDetection, ...]],
) -> int | None:
    frames_with_detection = [frame for frame in sequence if qualifying[frame.frame_id]]
    if len(frames_with_detection) < 2 or any(frame.source_offset_ms is None for frame in frames_with_detection):
        return None
    offsets = sorted(frame.source_offset_ms for frame in frames_with_detection)  # type: ignore[misc]
    episodes = 1
    for earlier, later in zip(offsets, offsets[1:]):
        if later - earlier > TEMPORAL_MAX_GAP_MS:
            episodes += 1
    return episodes - 1


def simulate_temporal_policies(
    manifest: CalibrationManifest,
    detections_by_frame: dict[str, tuple[DetectionObservation, ...]],
    *,
    threshold: float,
) -> tuple[TemporalPolicyResult, ...]:
    """Simulate bounded confirmation policies over recorded detections only.

    This never touches the real frame-driven tracker (Stage 4/6.1); it is a
    pure re-classification of already-scored detections grouped by the
    manifest's own `sequence_id`. `detector_plus_tracker_confirmation` is
    always reported unsupported because this cohort carries no `TrackUpdate`
    facts -- evaluating it honestly requires the real replay tracker over a
    continuous ordered replay with expected-Visit annotations, which this
    still-image cohort is not."""

    sequences = _sequence_groups(manifest)
    results = []
    for policy in TEMPORAL_POLICIES:
        if policy == "detector_plus_tracker_confirmation":
            results.append(TemporalPolicyResult(
                policy, False, 0, len(sequences), 0, 0, 0, None, None, None,
                unsupported_limitations=(
                    "requires TrackUpdate facts from the frame-driven replay tracker over a "
                    "continuous ordered replay with expected-Visit annotations; this "
                    "calibration cohort is a curated still-image set, not a continuous replay",
                ),
            ))
            continue
        confirmed_true = confirmed_false = missed_true = 0
        fragmented_total = 0
        fragmented_scorable = False
        evaluated = skipped = 0
        for key, sequence in sequences.items():
            qualifying = _qualifying_detections_by_frame(sequence, detections_by_frame, threshold=threshold)
            fires = _policy_fires(policy, sequence, qualifying)
            if fires is None:
                skipped += 1
                continue
            evaluated += 1
            expected_appearance = any(frame.animal_present == "yes" for frame in sequence)
            if fires and expected_appearance:
                confirmed_true += 1
            elif fires and not expected_appearance:
                confirmed_false += 1
            elif not fires and expected_appearance:
                missed_true += 1
            if fires and expected_appearance:
                fragments = _fragmentation_count(sequence, qualifying)
                if fragments is not None:
                    fragmented_scorable = True
                    fragmented_total += fragments
        limitations: tuple[str, ...] = ()
        if skipped:
            limitations = (
                f"{skipped} of {skipped + evaluated} sequences lack recorded "
                "source_offset_ms for every qualifying frame and were excluded from this policy",
            )
        results.append(TemporalPolicyResult(
            policy=policy,
            supported=True,
            sequences_evaluated=evaluated,
            sequences_skipped_insufficient_frames=skipped,
            confirmed_true_appearances=confirmed_true,
            confirmed_false_episodes=confirmed_false,
            missed_true_appearances=missed_true,
            fragmented_episode_count=fragmented_total if fragmented_scorable else None,
            precision=_ratio(confirmed_true, confirmed_true + confirmed_false),
            recall=_ratio(confirmed_true, confirmed_true + missed_true),
            unsupported_limitations=limitations,
        ))
    return tuple(results)


# --------------------------------------------------------------------------
# Preprocessing comparison
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class PreprocessingComparison:
    supported: bool
    primary_resize_mode: str
    alternative_resize_mode: str | None
    at_threshold: float
    primary_precision: float | None
    primary_recall: float | None
    alternative_precision: float | None
    alternative_recall: float | None
    regressions: tuple[str, ...]
    unsupported_reason: str | None = None


def compare_preprocessing(
    primary: ThresholdMetrics | None,
    alternative: ThresholdMetrics | None,
    *,
    primary_resize_mode: str,
    alternative_resize_mode: str | None,
    unsupported_reason: str | None = None,
) -> PreprocessingComparison:
    if primary is None or alternative is None or unsupported_reason is not None:
        return PreprocessingComparison(
            False, primary_resize_mode, alternative_resize_mode,
            primary.threshold if primary is not None else 0.0,
            primary.precision if primary is not None else None,
            primary.recall if primary is not None else None,
            None, None, (),
            unsupported_reason or "alternative preprocessing metrics unavailable",
        )
    regressions = []
    if alternative.precision is not None and primary.precision is not None and alternative.precision < primary.precision:
        regressions.append(f"precision {primary.precision:.3f} -> {alternative.precision:.3f}")
    if alternative.recall is not None and primary.recall is not None and alternative.recall < primary.recall:
        regressions.append(f"recall {primary.recall:.3f} -> {alternative.recall:.3f}")
    return PreprocessingComparison(
        True, primary_resize_mode, alternative_resize_mode, primary.threshold,
        primary.precision, primary.recall, alternative.precision, alternative.recall,
        tuple(regressions),
    )


# --------------------------------------------------------------------------
# Sample sufficiency
# --------------------------------------------------------------------------

MIN_POSITIVE_FRAMES = 20
MIN_NEGATIVE_FRAMES = 20
MIN_SCENE_GROUPS = 2
MIN_FRAMES_FOR_DIVERSITY_CHECK = 5
MIN_DISTINCT_POSITIVE_LOCATIONS = 3
CENTROID_BIN_SIZE = 0.05

OVERALL_INSUFFICIENT_DATA = "DETECTOR_CALIBRATION_INSUFFICIENT_DATA"
OVERALL_CHARACTERIZED = "DETECTOR_CALIBRATION_CHARACTERIZED"


@dataclass(frozen=True)
class SampleSufficiency:
    total_frames: int
    scorable_positive_frames: int
    scorable_negative_frames: int
    distinct_scene_groups: int
    sufficient_for_threshold_selection: bool
    reasons: tuple[str, ...]


def _diversity_reasons(manifest: CalibrationManifest) -> tuple[str, ...]:
    """A repeated crop of the same visit is not an independent example; flag
    scene groups whose positive boxes collapse onto very few locations."""

    by_scene: dict[str, list[CalibrationFrame]] = defaultdict(list)
    for frame in manifest.frames:
        if frame.is_scorable and frame.animal_present == "yes":
            by_scene[frame.scene_group].append(frame)
    reasons = []
    for scene, frames in sorted(by_scene.items()):
        if len(frames) < MIN_FRAMES_FOR_DIVERSITY_CHECK:
            continue
        bins = {
            (round(_centroid(box.box)[0] / CENTROID_BIN_SIZE), round(_centroid(box.box)[1] / CENTROID_BIN_SIZE))
            for frame in frames for box in frame.boxes
        }
        if len(bins) < MIN_DISTINCT_POSITIVE_LOCATIONS:
            reasons.append(
                f"scene_group '{scene}' has {len(frames)} positive frames but only "
                f"{len(bins)} distinct reviewed-box location(s) (likely repeated captures "
                "of the same visit rather than independent examples)"
            )
    return tuple(reasons)


def classify_sample_sufficiency(manifest: CalibrationManifest) -> SampleSufficiency:
    scorable = [frame for frame in manifest.frames if frame.is_scorable]
    positive = [frame for frame in scorable if frame.animal_present == "yes"]
    negative = [frame for frame in scorable if frame.animal_present == "no"]
    scene_groups = {frame.scene_group for frame in scorable}
    reasons = []
    if len(positive) < MIN_POSITIVE_FRAMES:
        reasons.append(f"fewer than {MIN_POSITIVE_FRAMES} scorable positive frames ({len(positive)})")
    if len(negative) < MIN_NEGATIVE_FRAMES:
        reasons.append(f"fewer than {MIN_NEGATIVE_FRAMES} scorable negative frames ({len(negative)})")
    if len(scene_groups) < MIN_SCENE_GROUPS:
        reasons.append(f"fewer than {MIN_SCENE_GROUPS} distinct scene groups ({len(scene_groups)})")
    reasons += list(_diversity_reasons(manifest))
    return SampleSufficiency(
        len(manifest.frames), len(positive), len(negative), len(scene_groups),
        not reasons, tuple(reasons),
    )


def overall_classification(sufficiency: SampleSufficiency) -> str:
    return OVERALL_CHARACTERIZED if sufficiency.sufficient_for_threshold_selection else OVERALL_INSUFFICIENT_DATA


# --------------------------------------------------------------------------
# Recommendation classification
# --------------------------------------------------------------------------

RECOMMENDATION_ACTIONS = (
    "threshold_increase",
    "threshold_decrease",
    "temporal_confirmation_change",
    "recurring_static_false_positive_region",
    "preprocessing_investigation",
    "detector_replacement_evaluation",
    "insufficient_reviewed_data",
)


@dataclass(frozen=True)
class Recommendation:
    action: str
    verdict: str
    supporting_metrics: tuple[str, ...]
    regressions: tuple[str, ...]
    sample_size_limitations: tuple[str, ...]
    safe_for_shadow_experimentation: bool = True
    safe_for_production_authority: bool = False


def _configured_row(sweep: tuple[ThresholdMetrics, ...]) -> ThresholdMetrics:
    for row in sweep:
        if row.is_configured_threshold:
            return row
    raise DetectorBenchmarkError("configured_threshold_row_missing")


def _threshold_direction_recommendation(
    action: str,
    sweep: tuple[ThresholdMetrics, ...],
    configured: ThresholdMetrics,
    *,
    higher: bool,
    sufficiency: SampleSufficiency,
) -> Recommendation:
    candidates = [
        row for row in sweep
        if (row.threshold > configured.threshold if higher else row.threshold < configured.threshold)
    ]
    limitations = list(sufficiency.reasons)
    if not candidates:
        return Recommendation(action, "not_supported", ("no candidate rows on that side of the configured threshold",), (), tuple(limitations))
    reference = min(candidates, key=lambda row: row.threshold) if higher else max(candidates, key=lambda row: row.threshold)
    if reference.precision is None or configured.precision is None or reference.recall is None or configured.recall is None:
        return Recommendation(action, "inconclusive", ("precision/recall not evaluated at one of the compared rows",), (), tuple(limitations))

    metrics = (
        f"precision {configured.precision:.3f} -> {reference.precision:.3f} at threshold "
        f"{configured.threshold:g} -> {reference.threshold:g}",
        f"recall {configured.recall:.3f} -> {reference.recall:.3f}",
    )
    regressions = []
    if higher:
        recall_regressed = reference.recall < configured.recall
        precision_improved = reference.precision > configured.precision
        if recall_regressed:
            regressions.append(f"recall drops {configured.recall:.3f} -> {reference.recall:.3f}")
        supported = precision_improved and not recall_regressed
    else:
        recall_improved = reference.recall > configured.recall
        precision_regressed = reference.precision < configured.precision
        if precision_regressed:
            regressions.append(f"precision drops {configured.precision:.3f} -> {reference.precision:.3f}")
        supported = recall_improved and not precision_regressed

    if not limitations and (configured.true_positives + configured.false_positives) < MIN_CONFIDENCE_INTERVAL_SAMPLE:
        limitations.append("fewer than the minimum sample size for a confident direction call at the configured threshold")

    if limitations:
        verdict = "inconclusive"
    elif supported:
        verdict = "supported"
    elif reference.precision == configured.precision and reference.recall == configured.recall:
        verdict = "inconclusive"
    else:
        verdict = "not_supported"
    return Recommendation(action, verdict, metrics, tuple(regressions), tuple(limitations))


def classify_recommendations(
    *,
    sweep: tuple[ThresholdMetrics, ...],
    static_report: StaticClusterReport,
    temporal_results: tuple[TemporalPolicyResult, ...],
    preprocessing: PreprocessingComparison,
    sufficiency: SampleSufficiency,
) -> tuple[Recommendation, ...]:
    """Classify each candidate action separately; never an aggregate score.

    Structurally excludes F1 from every decision input (only precision,
    recall, false-positive rate, and sample size are read here)."""

    configured = _configured_row(sweep)
    recommendations = [
        _threshold_direction_recommendation("threshold_increase", sweep, configured, higher=True, sufficiency=sufficiency),
        _threshold_direction_recommendation("threshold_decrease", sweep, configured, higher=False, sufficiency=sufficiency),
    ]

    supported_temporal = [
        result for result in temporal_results
        if result.supported and result.confirmed_false_episodes == 0 and result.confirmed_true_appearances > 0
    ]
    if not any(result.supported for result in temporal_results):
        recommendations.append(Recommendation(
            "temporal_confirmation_change", "not_supported",
            ("no temporal policy was evaluable on this cohort",), (), tuple(sufficiency.reasons),
        ))
    elif supported_temporal:
        chosen = supported_temporal[0]
        recommendations.append(Recommendation(
            "temporal_confirmation_change", "supported",
            (f"policy '{chosen.policy}' confirmed {chosen.confirmed_true_appearances} true appearance(s) "
             f"with 0 false episodes across {chosen.sequences_evaluated} evaluated sequence(s)",),
            (), tuple(sufficiency.reasons),
        ))
    else:
        worst = max((r for r in temporal_results if r.supported), key=lambda r: r.confirmed_false_episodes, default=None)
        metrics = (
            (f"policy '{worst.policy}' still confirms {worst.confirmed_false_episodes} false episode(s)",)
            if worst is not None else ()
        )
        recommendations.append(Recommendation("temporal_confirmation_change", "not_supported", metrics, (), tuple(sufficiency.reasons)))

    if static_report.clusters:
        labels = sorted({
            f"{cluster.scene_group}:{cluster.matched_static_structure or 'unlabeled-cluster-' + cluster.cluster_id}"
            for cluster in static_report.clusters
        })
        recommendations.append(Recommendation(
            "recurring_static_false_positive_region", "identified",
            (f"{len(static_report.clusters)} recurring cluster(s): {', '.join(labels)}",),
            (), tuple(sufficiency.reasons),
        ))
    else:
        recommendations.append(Recommendation(
            "recurring_static_false_positive_region", "not_identified", (), (), tuple(sufficiency.reasons),
        ))

    if not preprocessing.supported:
        recommendations.append(Recommendation(
            "preprocessing_investigation", "unsupported",
            (preprocessing.unsupported_reason or "unsupported",), (), tuple(sufficiency.reasons),
        ))
    else:
        meaningful = bool(preprocessing.regressions) or (
            preprocessing.alternative_precision is not None and preprocessing.primary_precision is not None
            and abs(preprocessing.alternative_precision - preprocessing.primary_precision) > 0.02
        ) or (
            preprocessing.alternative_recall is not None and preprocessing.primary_recall is not None
            and abs(preprocessing.alternative_recall - preprocessing.primary_recall) > 0.02
        )
        recommendations.append(Recommendation(
            "preprocessing_investigation", "needed" if meaningful else "not_needed",
            (
                f"{preprocessing.primary_resize_mode} precision={preprocessing.primary_precision} "
                f"recall={preprocessing.primary_recall} vs {preprocessing.alternative_resize_mode} "
                f"precision={preprocessing.alternative_precision} recall={preprocessing.alternative_recall}",
            ),
            preprocessing.regressions, tuple(sufficiency.reasons),
        ))

    best_recall_row = max((row for row in sweep if row.recall is not None), key=lambda row: row.recall, default=None)
    best_precision_row = max((row for row in sweep if row.precision is not None), key=lambda row: row.precision, default=None)
    weak_recall = best_recall_row is not None and best_recall_row.recall < 0.5 and (best_recall_row.true_positives + best_recall_row.false_negatives_true_miss) >= MIN_CONFIDENCE_INTERVAL_SAMPLE
    weak_precision = best_precision_row is not None and best_precision_row.precision < 0.3 and (best_precision_row.true_positives + best_precision_row.false_positives) >= MIN_CONFIDENCE_INTERVAL_SAMPLE
    # A threshold can only ever trade recovered/lost detections that the
    # detector actually produced somewhere in the grid; the true-miss rate at
    # the most permissive (lowest) row measures the part no threshold change
    # can ever fix -- reviewed animals the detector never observed at all,
    # even at the anchor floor.
    lowest_row = min(sweep, key=lambda row: row.threshold, default=None)
    true_miss_denominator = (
        lowest_row.true_positives + lowest_row.false_negatives_below_threshold
        + lowest_row.false_negatives_privacy_masked + lowest_row.false_negatives_true_miss
    ) if lowest_row is not None else 0
    true_miss_rate = _ratio(lowest_row.false_negatives_true_miss, true_miss_denominator) if lowest_row is not None else None
    weak_true_miss = (
        true_miss_rate is not None and true_miss_rate > 0.3
        and true_miss_denominator >= MIN_CONFIDENCE_INTERVAL_SAMPLE
    )
    if weak_recall or weak_precision or weak_true_miss:
        metrics = tuple(
            text for text in (
                f"best achievable recall in the grid is {best_recall_row.recall:.3f}" if weak_recall else None,
                f"best achievable precision in the grid is {best_precision_row.precision:.3f}" if weak_precision else None,
                (
                    f"{lowest_row.false_negatives_true_miss}/{true_miss_denominator} reviewed animals "
                    f"({true_miss_rate:.3f}) are never observed by the detector at any score down to the "
                    f"threshold-{lowest_row.threshold:g} anchor; no threshold change can recover a true miss"
                ) if weak_true_miss else None,
            ) if text is not None
        )
        recommendations.append(Recommendation("detector_replacement_evaluation", "needed", metrics, (), tuple(sufficiency.reasons)))
    else:
        recommendations.append(Recommendation("detector_replacement_evaluation", "not_needed", (), (), tuple(sufficiency.reasons)))

    recommendations.append(Recommendation(
        "insufficient_reviewed_data",
        "yes" if not sufficiency.sufficient_for_threshold_selection else "no",
        (
            f"{sufficiency.scorable_positive_frames} scorable positive / "
            f"{sufficiency.scorable_negative_frames} scorable negative frames across "
            f"{sufficiency.distinct_scene_groups} scene group(s)",
        ),
        (), tuple(sufficiency.reasons),
    ))
    return tuple(recommendations)


# --------------------------------------------------------------------------
# Report assembly
# --------------------------------------------------------------------------


def build_semantic_report(
    *,
    manifest: CalibrationManifest,
    configured_threshold: float,
    thresholds: tuple[float, ...],
    sweep: tuple[ThresholdMetrics, ...],
    static_report: StaticClusterReport,
    temporal_results: tuple[TemporalPolicyResult, ...],
    preprocessing: PreprocessingComparison,
    sufficiency: SampleSufficiency,
    recommendations: tuple[Recommendation, ...],
    provider: dict[str, object],
) -> dict[str, object]:
    """Assemble the deterministic semantic report and its fingerprint.

    Absolute paths, host/PID facts, wall-clock timestamps, and execution
    duration never enter this dict; callers append those separately under an
    `execution` key that is excluded from `semantic_fingerprint`."""

    semantic: dict[str, object] = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "benchmark_version": BENCHMARK_VERSION,
        "cohort": {
            "cohort_id": manifest.cohort_id,
            "manifest_fingerprint": manifest.fingerprint,
            "frame_count": len(manifest.frames),
        },
        "configured_threshold": configured_threshold,
        "threshold_grid": list(thresholds),
        "match_iou_threshold": MATCH_IOU_THRESHOLD,
        "cluster_iou_threshold": CLUSTER_IOU_THRESHOLD,
        "provider": provider,
        "threshold_sweep": [asdict(row) for row in sweep],
        "static_false_positive_clusters": asdict(static_report),
        "temporal_policy_simulation": [asdict(row) for row in temporal_results],
        "preprocessing_comparison": asdict(preprocessing),
        "sample_sufficiency": asdict(sufficiency),
        "overall_classification": overall_classification(sufficiency),
        "recommendations": [asdict(row) for row in recommendations],
        "creates_truth": False,
        "shadow_only": True,
        "production_proposal_authority": False,
    }
    return {**semantic, "semantic_fingerprint": semantic_fingerprint(semantic)}


__all__ = [
    "ANCHOR_MARGIN",
    "BENCHMARK_VERSION",
    "CLUSTER_CENTROID_THRESHOLD",
    "CLUSTER_IOU_THRESHOLD",
    "CLUSTER_MIN_RECURRENCE",
    "CLUSTER_SCORE_BAND",
    "DEFAULT_THRESHOLD_GRID",
    "MANIFEST_VERSION",
    "MATCH_IOU_THRESHOLD",
    "MIN_CONFIDENCE_INTERVAL_SAMPLE",
    "MIN_NEGATIVE_FRAMES",
    "MIN_POSITIVE_FRAMES",
    "MIN_SCENE_GROUPS",
    "OVERALL_CHARACTERIZED",
    "OVERALL_INSUFFICIENT_DATA",
    "REPORT_SCHEMA_VERSION",
    "RECOMMENDATION_ACTIONS",
    "STRONG_DETECTION_SCORE_DEFAULT",
    "TEMPORAL_MAX_GAP_MS",
    "TEMPORAL_MINIMUM_SPAN_MS",
    "TEMPORAL_POLICIES",
    "CalibrationFrame",
    "CalibrationManifest",
    "ClassifiedDetection",
    "ClusterMember",
    "ConfidenceInterval",
    "DetectorBenchmarkError",
    "FalsePositiveCluster",
    "FrameClassification",
    "PreprocessingComparison",
    "Recommendation",
    "ReviewedBox",
    "SampleSufficiency",
    "SceneGroupMetrics",
    "ScoreDistribution",
    "StaticClusterReport",
    "StaticStructure",
    "TemporalPolicyResult",
    "ThresholdMetrics",
    "anchor_score_threshold",
    "build_semantic_report",
    "classify_frame",
    "classify_recommendations",
    "classify_sample_sufficiency",
    "cluster_static_false_positives",
    "compare_preprocessing",
    "effective_threshold_grid",
    "overall_classification",
    "simulate_temporal_policies",
    "sweep_thresholds",
]
