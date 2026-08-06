"""Human-annotation schema, validation, active-learning classification,
dataset statistics, and benchmark-manifest export transforms for the Stage
6.6 reviewed temporal dataset pipeline.

This module is pure: no filesystem I/O, no product repository import, no
CUDA/ONNX Runtime/OpenCV type. It consumes a `temporal_capture.
CaptureSessionManifest`-shaped dict (as written by `temporal_capture_io`)
and an `AnnotationSet` (as edited by a human reviewer) and produces
validation reports, active-learning categories, dataset statistics, and
already-existing benchmark manifest shapes
(`detector_benchmark.CalibrationManifest`, the same schema reused for
motion-proposal cohorts in Stage 6.5, and Stage 2's own
`replay.BenchmarkManifest`/`ReplayInput`) -- it invents no new schema for
those three exports. See docs/temporal-review-capture-contract.md.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
from typing import Callable, Literal

from mockingbird.observation.temporal_capture import TRIGGER_RECURRING_STATIC_GEOMETRY

ANNOTATION_SCHEMA_VERSION = 1
ANNOTATION_CONTRACT_VERSION = "temporal-review-annotation-v1"
MATCH_IOU_THRESHOLD = 0.5

WholeFrameTruth = Literal["yes", "no", "ambiguous", "unreviewed"]
WHOLE_FRAME_TRUTH_VALUES: tuple[str, ...] = ("yes", "no", "ambiguous", "unreviewed")

TruthSource = Literal[
    "full_frame_inspection", "detector_crop", "high_resolution_burst",
    "adjacent_sequence", "product_review_record", "operator_marker",
]
TRUTH_SOURCES: tuple[str, ...] = (
    "full_frame_inspection", "detector_crop", "high_resolution_burst",
    "adjacent_sequence", "product_review_record", "operator_marker",
)

MAX_BOXES_PER_FRAME = 64
MAX_FRAMES = 20_000
MAX_APPEARANCES = 2_000


class TemporalAnnotationError(ValueError):
    """A bounded annotation schema validation or execution failure code."""


# --------------------------------------------------------------------------
# Annotation schema
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class BoxAnnotation:
    """One reviewed animal box, in the frame's own source-normalized space."""

    box: tuple[float, float, float, float]
    broad_class: str = "animal"
    partially_visible: bool = False
    occluded: bool = False
    edge_clipped: bool = False
    blurred: bool = False
    distance: str | None = None  # "far" / "typical" / "unknown", same proxy convention as detector_benchmark
    box_confidence: Literal["confident", "limited"] = "confident"
    review_limitation: str | None = None

    def __post_init__(self) -> None:
        left, top, right, bottom = self.box
        if not (0.0 <= left < right <= 1.0 and 0.0 <= top < bottom <= 1.0):
            raise TemporalAnnotationError("box_outside_image_bounds")
        if not self.broad_class:
            raise TemporalAnnotationError("invalid_box_broad_class")
        if self.distance is not None and self.distance not in ("far", "typical", "unknown"):
            raise TemporalAnnotationError("invalid_box_distance")


@dataclass(frozen=True)
class AppearanceInterval:
    """One reviewed temporal appearance, expressed as an ordered pair of
    already-retained frame identities (an instantaneous appearance uses the
    same frame_id for both ends)."""

    appearance_id: str
    start_frame_id: str
    end_frame_id: str
    instantaneous: bool = False
    entry_uncertain: bool = False
    exit_uncertain: bool = False
    continuity_ambiguous: bool = False

    def __post_init__(self) -> None:
        if not self.appearance_id or not self.start_frame_id or not self.end_frame_id:
            raise TemporalAnnotationError("invalid_appearance_identity")


@dataclass(frozen=True)
class EvidenceUsefulness:
    broad_animal_confirmation_useful: bool | None = None
    identification_potentially_useful: bool | None = None
    context_useful: bool | None = None
    subject_absent: bool | None = None
    undecodable: bool = False
    ambiguous: bool = False


@dataclass(frozen=True)
class Provenance:
    reviewer: str
    reviewed_at_iso: str
    source_capture_session: str
    truth_source: TruthSource
    # Descriptive context only, never itself truth: what the product's own
    # ReviewLabel said for this content, if any was ever attached. Recording
    # it lets the validator prove a reviewer did not silently inherit it.
    product_review_label: str | None = None
    whole_frame_independently_confirmed: bool = False

    def __post_init__(self) -> None:
        if not self.reviewer or not self.reviewed_at_iso or not self.source_capture_session:
            raise TemporalAnnotationError("invalid_provenance")
        if self.truth_source not in TRUTH_SOURCES:
            raise TemporalAnnotationError("invalid_truth_source")


@dataclass(frozen=True)
class FrameAnnotation:
    frame_id: str
    whole_frame_truth: WholeFrameTruth = "unreviewed"
    yes_but_unscorable: bool = False
    boxes: tuple[BoxAnnotation, ...] = ()
    evidence_usefulness: EvidenceUsefulness | None = None
    provenance: Provenance | None = None
    privacy_ignore_override: bool = False
    reviewer_note: str = ""

    def __post_init__(self) -> None:
        if not self.frame_id:
            raise TemporalAnnotationError("invalid_frame_identity")
        if self.whole_frame_truth not in WHOLE_FRAME_TRUTH_VALUES:
            raise TemporalAnnotationError("invalid_whole_frame_truth")
        if len(self.boxes) > MAX_BOXES_PER_FRAME:
            raise TemporalAnnotationError("frame_box_limit")
        if len(self.reviewer_note) > 2000:
            raise TemporalAnnotationError("invalid_reviewer_note")

    @property
    def is_reviewed(self) -> bool:
        return self.whole_frame_truth != "unreviewed"

    @property
    def is_scorable(self) -> bool:
        return self.whole_frame_truth in ("yes", "no") and not (
            self.whole_frame_truth == "yes" and self.yes_but_unscorable
        )


@dataclass(frozen=True)
class AnnotationSet:
    schema_version: int
    capture_session_id: str
    capture_manifest_fingerprint: str
    frames: tuple[FrameAnnotation, ...]
    appearances: tuple[AppearanceInterval, ...] = ()

    def __post_init__(self) -> None:
        if self.schema_version != ANNOTATION_SCHEMA_VERSION:
            raise TemporalAnnotationError("unsupported_annotation_schema_version")
        if not self.capture_session_id:
            raise TemporalAnnotationError("invalid_capture_session_identity")
        if len(self.frames) > MAX_FRAMES or len(self.appearances) > MAX_APPEARANCES:
            raise TemporalAnnotationError("annotation_set_limit")

    def frame(self, frame_id: str) -> FrameAnnotation | None:
        for item in self.frames:
            if item.frame_id == frame_id:
                return item
        return None


def annotation_skeleton(frame_ids: tuple[str, ...], *, capture_session_id: str, capture_manifest_fingerprint: str) -> AnnotationSet:
    """A default, entirely-`unreviewed` annotation set for a fresh review
    packet -- the file a human reviewer edits in place."""

    return AnnotationSet(
        ANNOTATION_SCHEMA_VERSION, capture_session_id, capture_manifest_fingerprint,
        tuple(FrameAnnotation(frame_id) for frame_id in frame_ids),
    )


# --------------------------------------------------------------------------
# Validation
# --------------------------------------------------------------------------

# Stable validation codes (task-required checks).
V_SCORABLE_YES_REQUIRES_BOX = "scorable_yes_requires_box_or_unscorable"
V_NEGATIVE_FRAME_HAS_POSITIVE_BOXES = "negative_frame_has_positive_boxes"
V_BOX_OUTSIDE_IMAGE_BOUNDS = "box_outside_image_bounds"
V_TEMPORAL_INTERVAL_OUTSIDE_SEQUENCE_BOUNDS = "temporal_interval_outside_sequence_bounds"
V_APPEARANCE_INTERVAL_REVERSED = "appearance_interval_reversed"
V_DUPLICATE_LOGICAL_IDENTITY = "duplicate_logical_identity"
V_MISSING_SOURCE_MEDIA = "missing_source_media"
V_CONTENT_HASH_MISMATCH = "content_hash_mismatch"
V_PRODUCT_FALSE_POSITIVE_AS_FRAME_NEGATIVE = "product_false_positive_treated_as_frame_negative"
V_STALE_GENERATION_EVIDENCE = "stale_generation_evidence"
V_PRIVACY_MASKED_MARKED_USABLE = "privacy_masked_content_marked_usable_without_override"
V_AMBIGUOUS_IN_SCORING_DENOMINATOR = "ambiguous_truth_in_scoring_denominator"
V_UNKNOWN_FRAME_REFERENCE = "unknown_frame_reference"
V_CAPTURE_FINGERPRINT_MISMATCH = "capture_manifest_fingerprint_mismatch"
V_APPEARANCE_CONTINUITY_UNMARKED = "overlapping_appearance_continuity_unmarked"

_REJECT_CODES = frozenset({
    V_SCORABLE_YES_REQUIRES_BOX, V_NEGATIVE_FRAME_HAS_POSITIVE_BOXES, V_BOX_OUTSIDE_IMAGE_BOUNDS,
    V_TEMPORAL_INTERVAL_OUTSIDE_SEQUENCE_BOUNDS, V_APPEARANCE_INTERVAL_REVERSED,
    V_DUPLICATE_LOGICAL_IDENTITY, V_MISSING_SOURCE_MEDIA, V_CONTENT_HASH_MISMATCH,
    V_PRODUCT_FALSE_POSITIVE_AS_FRAME_NEGATIVE, V_STALE_GENERATION_EVIDENCE,
    V_PRIVACY_MASKED_MARKED_USABLE, V_UNKNOWN_FRAME_REFERENCE, V_CAPTURE_FINGERPRINT_MISMATCH,
})
# Flagged (surfaced, does not by itself fail validation): ambiguous-in-scoring
# is enforced structurally by export (ambiguous frames are always excluded),
# so a frame merely *carrying* ambiguous truth is a flag, not a rejection;
# unmarked overlapping continuity is a reviewer prompt, not a hard failure.
_FLAG_CODES = frozenset({V_AMBIGUOUS_IN_SCORING_DENOMINATOR, V_APPEARANCE_CONTINUITY_UNMARKED})


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    severity: Literal["reject", "flag"]
    frame_id: str | None
    detail: str


@dataclass(frozen=True)
class ValidationReport:
    ok: bool
    issues: tuple[ValidationIssue, ...]
    scorable_frame_count: int
    reviewed_frame_count: int
    ambiguous_frame_count: int
    unreviewed_frame_count: int

    @property
    def reject_count(self) -> int:
        return sum(1 for item in self.issues if item.severity == "reject")


def validate_annotations(
    capture_manifest: dict[str, object],
    annotations: AnnotationSet,
    *,
    actual_content_hash: Callable[[str], str | None] | None = None,
) -> ValidationReport:
    """Validate a reviewer-edited `AnnotationSet` against its capture
    manifest. `actual_content_hash` is an optional, caller-supplied lookup
    (frame_id -> on-disk sha256) so this function stays pure while still
    supporting the missing-media/hash-mismatch checks the IO layer alone can
    resolve."""

    issues: list[ValidationIssue] = []
    frames_by_id = {item["frame_id"]: item for item in capture_manifest.get("frames", [])}  # type: ignore[union-attr]
    if annotations.capture_manifest_fingerprint != capture_manifest.get("semantic_fingerprint", capture_manifest.get("fingerprint")):
        issues.append(ValidationIssue(V_CAPTURE_FINGERPRINT_MISMATCH, "reject", None, "annotation set was not built against this exact capture manifest"))

    seen_ids: set[str] = set()
    for frame in annotations.frames:
        if frame.frame_id in seen_ids:
            issues.append(ValidationIssue(V_DUPLICATE_LOGICAL_IDENTITY, "reject", frame.frame_id, "duplicate frame_id in annotation set"))
            continue
        seen_ids.add(frame.frame_id)
        record = frames_by_id.get(frame.frame_id)
        if record is None:
            issues.append(ValidationIssue(V_UNKNOWN_FRAME_REFERENCE, "reject", frame.frame_id, "frame_id not present in capture manifest"))
            continue

        if actual_content_hash is not None:
            actual = actual_content_hash(frame.frame_id)
            if actual is None:
                issues.append(ValidationIssue(V_MISSING_SOURCE_MEDIA, "reject", frame.frame_id, "source media file not found"))
            elif actual != record.get("content_hash"):
                issues.append(ValidationIssue(V_CONTENT_HASH_MISMATCH, "reject", frame.frame_id, "on-disk content hash no longer matches the capture manifest"))

        if frame.whole_frame_truth == "yes" and not frame.yes_but_unscorable and not frame.boxes:
            issues.append(ValidationIssue(V_SCORABLE_YES_REQUIRES_BOX, "reject", frame.frame_id, "scorable yes frame carries no reviewed box"))
        if frame.whole_frame_truth in ("no", "ambiguous") and frame.boxes:
            issues.append(ValidationIssue(V_NEGATIVE_FRAME_HAS_POSITIVE_BOXES, "reject", frame.frame_id, f"{frame.whole_frame_truth} frame carries reviewed boxes"))
        if frame.whole_frame_truth == "ambiguous":
            issues.append(ValidationIssue(V_AMBIGUOUS_IN_SCORING_DENOMINATOR, "flag", frame.frame_id, "ambiguous frame excluded from scoring by export, not by itself"))

        provenance = frame.provenance
        if provenance is not None and provenance.product_review_label == "false_positive" and frame.whole_frame_truth == "no" and not provenance.whole_frame_independently_confirmed:
            issues.append(ValidationIssue(
                V_PRODUCT_FALSE_POSITIVE_AS_FRAME_NEGATIVE, "reject", frame.frame_id,
                "product false_positive Visit label was used as whole-frame negative truth without independent full-frame confirmation",
            ))

        privacy_regions = capture_manifest.get("config", {}).get("privacy_ignore_regions", [])  # type: ignore[union-attr]
        if privacy_regions and frame.whole_frame_truth in ("yes", "no") and not frame.privacy_ignore_override:
            for box in frame.boxes:
                if _centroid_in_any(box.box, privacy_regions):  # type: ignore[arg-type]
                    issues.append(ValidationIssue(
                        V_PRIVACY_MASKED_MARKED_USABLE, "reject", frame.frame_id,
                        "reviewed box centered inside a declared Privacy/Ignore region without an explicit reviewer override",
                    ))
                    break

    duration_ms = int(capture_manifest.get("end_source_offset_ms", 0)) - int(capture_manifest.get("start_source_offset_ms", 0))
    appearance_ids: set[str] = set()
    sorted_appearances = list(annotations.appearances)
    for appearance in sorted_appearances:
        if appearance.appearance_id in appearance_ids:
            issues.append(ValidationIssue(V_DUPLICATE_LOGICAL_IDENTITY, "reject", None, f"duplicate appearance_id {appearance.appearance_id}"))
        appearance_ids.add(appearance.appearance_id)
        start_record = frames_by_id.get(appearance.start_frame_id)
        end_record = frames_by_id.get(appearance.end_frame_id)
        if start_record is None or end_record is None:
            issues.append(ValidationIssue(V_UNKNOWN_FRAME_REFERENCE, "reject", None, f"appearance {appearance.appearance_id} references an unknown frame"))
            continue
        start_offset, end_offset = int(start_record["source_offset_ms"]), int(end_record["source_offset_ms"])
        if start_offset > end_offset:
            issues.append(ValidationIssue(V_APPEARANCE_INTERVAL_REVERSED, "reject", None, f"appearance {appearance.appearance_id} has reversed times"))
        if start_offset < 0 or end_offset > duration_ms:
            issues.append(ValidationIssue(V_TEMPORAL_INTERVAL_OUTSIDE_SEQUENCE_BOUNDS, "reject", None, f"appearance {appearance.appearance_id} falls outside the capture session's own duration"))
        if start_record.get("provider_generation") != end_record.get("provider_generation"):
            issues.append(ValidationIssue(V_STALE_GENERATION_EVIDENCE, "reject", None, f"appearance {appearance.appearance_id} spans a provider-generation reset"))

    for i, first in enumerate(sorted_appearances):
        for second in sorted_appearances[i + 1:]:
            if _appearance_overlaps(first, second, frames_by_id) and not (first.continuity_ambiguous or second.continuity_ambiguous):
                issues.append(ValidationIssue(
                    V_APPEARANCE_CONTINUITY_UNMARKED, "flag", None,
                    f"appearances {first.appearance_id} and {second.appearance_id} overlap without continuity_ambiguous set",
                ))

    reviewed = sum(1 for item in annotations.frames if item.is_reviewed)
    ambiguous = sum(1 for item in annotations.frames if item.whole_frame_truth == "ambiguous")
    unreviewed = sum(1 for item in annotations.frames if not item.is_reviewed)
    scorable = sum(1 for item in annotations.frames if item.is_scorable)
    ok = not any(item.severity == "reject" for item in issues)
    return ValidationReport(ok, tuple(issues), scorable, reviewed, ambiguous, unreviewed)


def _centroid_in_any(box: tuple[float, float, float, float], regions: list) -> bool:
    x, y = (box[0] + box[2]) / 2.0, (box[1] + box[3]) / 2.0
    for region in regions:
        left, top, right, bottom = region
        if left <= x <= right and top <= y <= bottom:
            return True
    return False


def _appearance_overlaps(first: AppearanceInterval, second: AppearanceInterval, frames_by_id: dict) -> bool:
    def _bounds(item: AppearanceInterval) -> tuple[int, int] | None:
        start, end = frames_by_id.get(item.start_frame_id), frames_by_id.get(item.end_frame_id)
        if start is None or end is None:
            return None
        return int(start["source_offset_ms"]), int(end["source_offset_ms"])

    first_bounds, second_bounds = _bounds(first), _bounds(second)
    if first_bounds is None or second_bounds is None:
        return False
    return first_bounds[0] <= second_bounds[1] and second_bounds[0] <= first_bounds[1]


# --------------------------------------------------------------------------
# Active-learning classification (engineering dataset categories only)
# --------------------------------------------------------------------------

AL_TRUE_POSITIVE = "true_positive"
AL_FALSE_POSITIVE = "false_positive"
AL_FALSE_NEGATIVE = "false_negative"
AL_BELOW_THRESHOLD_TRUE_POSITIVE = "below_threshold_true_positive"
AL_HARD_NEGATIVE_STATIC = "hard_negative_static"
AL_HARD_NEGATIVE_MOTION = "hard_negative_motion"
AL_DUPLICATE_DETECTION = "duplicate_detection"
AL_AMBIGUOUS_TRUTH = "ambiguous_truth"
AL_PRIVACY_EXCLUDED = "privacy_excluded"
AL_TRACKING_FAILURE = "tracking_failure"
AL_EPISODE_BOUNDARY_FAILURE = "episode_boundary_failure"
AL_USEFUL_TRAINING_POSITIVE = "useful_training_positive"
AL_USEFUL_TRAINING_NEGATIVE = "useful_training_negative"
AL_HOLD_FOR_REVIEW = "hold_for_review"

ACTIVE_LEARNING_CATEGORIES: tuple[str, ...] = (
    AL_TRUE_POSITIVE, AL_FALSE_POSITIVE, AL_FALSE_NEGATIVE, AL_BELOW_THRESHOLD_TRUE_POSITIVE,
    AL_HARD_NEGATIVE_STATIC, AL_HARD_NEGATIVE_MOTION, AL_DUPLICATE_DETECTION, AL_AMBIGUOUS_TRUTH,
    AL_PRIVACY_EXCLUDED, AL_TRACKING_FAILURE, AL_EPISODE_BOUNDARY_FAILURE,
    AL_USEFUL_TRAINING_POSITIVE, AL_USEFUL_TRAINING_NEGATIVE, AL_HOLD_FOR_REVIEW,
)


def _iou(first: tuple[float, float, float, float], second: tuple[float, float, float, float]) -> float:
    left, top = max(first[0], second[0]), max(first[1], second[1])
    right, bottom = min(first[2], second[2]), min(first[3], second[3])
    intersection = max(0.0, right - left) * max(0.0, bottom - top)
    first_area = (first[2] - first[0]) * (first[3] - first[1])
    second_area = (second[2] - second[0]) * (second[3] - second[1])
    union = first_area + second_area - intersection
    return 0.0 if union <= 0.0 else intersection / union


def classify_active_learning(
    frame_record: dict[str, object],
    annotation: FrameAnnotation,
    *,
    shadow_operating_point: float,
) -> tuple[str, ...]:
    """Bounded, deterministic engineering dataset categories for one frame.
    Never mutates a model or a runtime threshold; these are dataset-curation
    labels only, distinct from product ReviewLabel truth."""

    if not annotation.is_reviewed:
        return (AL_HOLD_FOR_REVIEW,)
    if annotation.whole_frame_truth == "ambiguous":
        return (AL_AMBIGUOUS_TRUTH, AL_HOLD_FOR_REVIEW)

    categories: list[str] = []
    detections = [tuple(item) for item in frame_record.get("detection_boxes", [])]  # type: ignore[union-attr]
    trigger_reasons = frame_record.get("trigger_reasons", ())

    if annotation.whole_frame_truth == "yes":
        matched_any_above = False
        matched_any_below = False
        for box in annotation.boxes:
            overlaps = [item for item in detections if _iou(box.box, tuple(item[:4])) >= MATCH_IOU_THRESHOLD]  # type: ignore[index]
            if any(item[4] >= shadow_operating_point for item in overlaps):  # type: ignore[index]
                matched_any_above = True
            elif overlaps:
                matched_any_below = True
        if matched_any_above:
            categories.append(AL_TRUE_POSITIVE)
        elif matched_any_below:
            categories.append(AL_BELOW_THRESHOLD_TRUE_POSITIVE)
        else:
            categories.append(AL_FALSE_NEGATIVE)
        if not annotation.yes_but_unscorable and any(not (box.occluded and box.blurred) for box in annotation.boxes):
            categories.append(AL_USEFUL_TRAINING_POSITIVE)
    elif annotation.whole_frame_truth == "no":
        unmatched = [
            item for item in detections
            if not any(_iou(tuple(item[:4]), box.box) >= MATCH_IOU_THRESHOLD for box in annotation.boxes)  # type: ignore[index]
        ]
        if unmatched:
            categories.append(AL_FALSE_POSITIVE)
            if TRIGGER_RECURRING_STATIC_GEOMETRY in trigger_reasons:
                categories.append(AL_HARD_NEGATIVE_STATIC)
            elif frame_record.get("motion_proposal_count", 0):
                categories.append(AL_HARD_NEGATIVE_MOTION)
        if frame_record.get("privacy_ignore_interaction"):
            categories.append(AL_PRIVACY_EXCLUDED)
        else:
            categories.append(AL_USEFUL_TRAINING_NEGATIVE)

    for index, first in enumerate(detections):
        for second in detections[index + 1:]:
            if _iou(tuple(first[:4]), tuple(second[:4])) >= MATCH_IOU_THRESHOLD:  # type: ignore[index]
                categories.append(AL_DUPLICATE_DETECTION)
                break
        if AL_DUPLICATE_DETECTION in categories:
            break

    if annotation.whole_frame_truth == "yes" and int(frame_record.get("active_track_count", 0)) == 0:
        categories.append(AL_TRACKING_FAILURE)

    return tuple(dict.fromkeys(categories)) or (AL_HOLD_FOR_REVIEW,)


def classify_episode_boundary_failures(annotations: AnnotationSet, frames_by_id: dict[str, dict[str, object]]) -> tuple[str, ...]:
    """Appearance intervals the reviewer marked as one continuous appearance
    but whose retained frames span more than one tracker generation --
    engineering evidence of a tracker episode-boundary problem, never a
    tracker reconfiguration."""

    failures: list[str] = []
    for appearance in annotations.appearances:
        if appearance.continuity_ambiguous:
            continue
        start, end = frames_by_id.get(appearance.start_frame_id), frames_by_id.get(appearance.end_frame_id)
        if start is None or end is None:
            continue
        generations: set[str] = set()
        for frame in frames_by_id.values():
            offset = int(frame["source_offset_ms"])  # type: ignore[index]
            if int(start["source_offset_ms"]) <= offset <= int(end["source_offset_ms"]):  # type: ignore[index]
                generations.update(frame.get("track_generation_ids", ()))  # type: ignore[union-attr]
        if len(generations) > 1:
            failures.append(appearance.appearance_id)
    return tuple(failures)


# --------------------------------------------------------------------------
# Dataset statistics
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class DatasetStatistics:
    total_sessions: int
    total_frames: int
    reviewed_frame_count: int
    unreviewed_frame_count: int
    positive_frame_count: int
    negative_frame_count: int
    ambiguous_frame_count: int
    reviewed_box_count: int
    temporal_sequence_count: int
    appearance_interval_count: int
    small_subject_count: int
    blurred_count: int
    clipped_count: int
    occluded_count: int
    scene_group_count: int
    hard_negative_cluster_count: int
    false_negative_count: int
    below_threshold_positive_count: int
    privacy_ignore_example_count: int
    provider_fingerprints: tuple[str, ...]
    content_hash_duplicate_count: int
    benchmark_sufficiency: dict[str, object]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def compute_dataset_statistics(
    sessions: tuple[dict[str, object], ...], annotation_sets: tuple[AnnotationSet, ...],
) -> DatasetStatistics:
    """Aggregate honest counts across one or more (capture_manifest,
    annotation_set) session pairs. Never claims sufficiency from a single
    feeder or a single day -- see `benchmark_sufficiency`."""

    total_frames = sum(len(session.get("frames", [])) for session in sessions)  # type: ignore[arg-type]
    reviewed = unreviewed = positive = negative = ambiguous = 0
    boxes = small_subject = blurred = clipped = occluded = 0
    false_negative = below_threshold = privacy_examples = 0
    scene_groups: set[str] = set()
    provider_fingerprints: set[str] = set()
    hashes: Counter[str] = Counter()
    hard_negative_clusters: set[tuple[str, ...]] = set()
    appearance_total = 0

    frames_by_session: dict[str, dict[str, dict[str, object]]] = {}
    for session in sessions:
        session_id = str(session.get("session_id"))
        frames_by_session[session_id] = {item["frame_id"]: item for item in session.get("frames", [])}  # type: ignore[union-attr]
        scene_groups.add(str(session.get("config", {}).get("stream_id")))  # type: ignore[union-attr]
        provider_fingerprints.add(str(session.get("model_fingerprint")))
        for record in session.get("frames", []):  # type: ignore[union-attr]
            hashes[str(record.get("content_hash"))] += 1  # type: ignore[union-attr]
            if TRIGGER_RECURRING_STATIC_GEOMETRY in record.get("trigger_reasons", ()):  # type: ignore[union-attr]
                hard_negative_clusters.add(tuple(sorted(record.get("trigger_reasons", ()))))  # type: ignore[union-attr]

    for annotation_set in annotation_sets:
        frames_lookup = frames_by_session.get(annotation_set.capture_session_id, {})
        appearance_total += len(annotation_set.appearances)
        for frame in annotation_set.frames:
            if not frame.is_reviewed:
                unreviewed += 1
                continue
            reviewed += 1
            if frame.whole_frame_truth == "yes":
                positive += 1
            elif frame.whole_frame_truth == "no":
                negative += 1
            elif frame.whole_frame_truth == "ambiguous":
                ambiguous += 1
            record = frames_lookup.get(frame.frame_id, {})
            operating_point = 0.5
            categories = classify_active_learning(record, frame, shadow_operating_point=operating_point) if record else ()
            if AL_FALSE_NEGATIVE in categories:
                false_negative += 1
            if AL_BELOW_THRESHOLD_TRUE_POSITIVE in categories:
                below_threshold += 1
            if AL_PRIVACY_EXCLUDED in categories:
                privacy_examples += 1
            for box in frame.boxes:
                boxes += 1
                if box.distance == "far":
                    small_subject += 1
                if box.blurred:
                    blurred += 1
                if box.edge_clipped:
                    clipped += 1
                if box.occluded:
                    occluded += 1

    duplicate_hashes = sum(1 for count in hashes.values() if count > 1)
    sufficiency = {
        target: classify_export_sufficiency(positive, negative, scene_groups=len(scene_groups), sequences=len(sessions))
        for target in ("detector_calibration", "motion_proposal", "replay")
    }
    return DatasetStatistics(
        total_sessions=len(sessions), total_frames=total_frames, reviewed_frame_count=reviewed,
        unreviewed_frame_count=unreviewed, positive_frame_count=positive, negative_frame_count=negative,
        ambiguous_frame_count=ambiguous, reviewed_box_count=boxes, temporal_sequence_count=len(sessions),
        appearance_interval_count=appearance_total, small_subject_count=small_subject, blurred_count=blurred,
        clipped_count=clipped, occluded_count=occluded, scene_group_count=len(scene_groups),
        hard_negative_cluster_count=len(hard_negative_clusters), false_negative_count=false_negative,
        below_threshold_positive_count=below_threshold, privacy_ignore_example_count=privacy_examples,
        provider_fingerprints=tuple(sorted(provider_fingerprints)), content_hash_duplicate_count=duplicate_hashes,
        benchmark_sufficiency=sufficiency,
    )


MIN_POSITIVE_FRAMES_FOR_SUFFICIENCY = 20
MIN_NEGATIVE_FRAMES_FOR_SUFFICIENCY = 20
MIN_SCENE_GROUPS_FOR_SUFFICIENCY = 2
MIN_SEQUENCES_FOR_TEMPORAL_SUFFICIENCY = 3


def classify_export_sufficiency(positive: int, negative: int, *, scene_groups: int, sequences: int) -> dict[str, object]:
    """Honest, general sample-sufficiency bounds -- identical in spirit to
    `detector_benchmark.classify_sample_sufficiency`, deliberately not
    satisfiable by one feeder or one day's capture alone."""

    reasons = []
    if positive < MIN_POSITIVE_FRAMES_FOR_SUFFICIENCY:
        reasons.append(f"fewer than {MIN_POSITIVE_FRAMES_FOR_SUFFICIENCY} reviewed positive frames ({positive})")
    if negative < MIN_NEGATIVE_FRAMES_FOR_SUFFICIENCY:
        reasons.append(f"fewer than {MIN_NEGATIVE_FRAMES_FOR_SUFFICIENCY} reviewed negative frames ({negative})")
    if scene_groups < MIN_SCENE_GROUPS_FOR_SUFFICIENCY:
        reasons.append(f"fewer than {MIN_SCENE_GROUPS_FOR_SUFFICIENCY} distinct scene/camera groups ({scene_groups})")
    if sequences < MIN_SEQUENCES_FOR_TEMPORAL_SUFFICIENCY:
        reasons.append(f"fewer than {MIN_SEQUENCES_FOR_TEMPORAL_SUFFICIENCY} distinct capture sessions ({sequences})")
    return {"sufficient": not reasons, "reasons": reasons}


# --------------------------------------------------------------------------
# Export transforms (reuse existing benchmark manifest schemas unchanged)
# --------------------------------------------------------------------------


def _distance_bucket(box: BoxAnnotation, *, width: int, height: int) -> str | None:
    if box.distance is not None:
        return box.distance
    longest_side_px = max((box.box[2] - box.box[0]) * width, (box.box[3] - box.box[1]) * height)
    return "far" if longest_side_px <= 96 else "typical"


def _export_frame_dicts(
    session: dict[str, object], annotations: AnnotationSet, *, scene_group: str, cohort_prefix: str,
) -> list[dict[str, object]]:
    frames_by_id = {item["frame_id"]: item for item in session.get("frames", [])}  # type: ignore[union-attr]
    records = []
    for frame in annotations.frames:
        if not frame.is_reviewed:
            continue
        record = frames_by_id.get(frame.frame_id)
        if record is None:
            continue
        width, height = session["config"]["analysis_width"], session["config"]["analysis_height"]  # type: ignore[index]
        boxes = [
            {"box": list(box.box), "broad_class": box.broad_class}
            for box in frame.boxes
        ]
        primary = frame.boxes[0] if frame.boxes else None
        records.append({
            "frame_id": f"{cohort_prefix}:{frame.frame_id}",
            "image": f"images/{frame.frame_id}.jpg",
            "content_hash": record.get("content_hash"),
            "width": width, "height": height,
            "animal_present": frame.whole_frame_truth,
            "boxes": boxes,
            "scorable": frame.is_scorable,
            "occlusion": "occluded" if primary and primary.occluded else None,
            "blur": "blurred" if primary and primary.blurred else None,
            "clipped": bool(primary.edge_clipped) if primary else None,
            "distance": _distance_bucket(primary, width=width, height=height) if primary else None,  # type: ignore[arg-type]
            "privacy_ignore_regions": session.get("config", {}).get("privacy_ignore_regions", []),  # type: ignore[union-attr]
            "scene_group": scene_group,
            "sequence_id": str(session.get("session_id")),
            "sequence_order": record.get("sequence"),
            "source_offset_ms": record.get("source_offset_ms"),
            "provenance": (
                f"Stage 6.6 reviewed temporal capture session {session.get('session_id')}; "
                f"reviewer={frame.provenance.reviewer if frame.provenance else 'unknown'}"
            ),
            "reviewer_note": frame.reviewer_note,
        })
    return records


def build_detector_calibration_export(session: dict[str, object], annotations: AnnotationSet, *, scene_group: str) -> dict[str, object]:
    """The existing `detector_benchmark.CalibrationManifest` shape (schema
    version 1), unchanged -- see docs/detector-calibration-benchmark-contract.md."""

    frames = _export_frame_dicts(session, annotations, scene_group=scene_group, cohort_prefix="temporal-review")
    return {
        "version": 1,
        "cohort_id": f"temporal-review-{session.get('session_id')}-detector-calibration",
        "annotation_policy": (
            "Human-reviewed whole-frame and box truth from a Stage 6.6 reviewed temporal "
            "capture session; a product Visit-level false_positive label was never treated "
            "as automatic whole-frame negative truth (see provenance.whole_frame_independently_confirmed)."
        ),
        "frames": frames,
        "scene_static_structures": {},
    }


def build_motion_proposal_export(session: dict[str, object], annotations: AnnotationSet, *, scene_group: str) -> dict[str, object]:
    """The identical `CalibrationManifest` schema Stage 6.5 already reuses
    for temporal cohorts, with real sequencing populated from the live
    capture session's own frame order -- see
    docs/adaptive-motion-proposal-benchmark-contract.md."""

    frames = _export_frame_dicts(session, annotations, scene_group=scene_group, cohort_prefix="temporal-review")
    ordered = sorted(frames, key=lambda item: item["sequence_order"] or 0)
    present_intervals = []
    run: list[dict[str, object]] = []
    for frame in ordered:
        if frame["animal_present"] == "yes":
            run.append(frame)
            continue
        if run:
            present_intervals.append({"start_offset_ms": run[0]["source_offset_ms"], "end_offset_ms": run[-1]["source_offset_ms"]})
            run = []
    if run:
        present_intervals.append({"start_offset_ms": run[0]["source_offset_ms"], "end_offset_ms": run[-1]["source_offset_ms"]})
    return {
        "version": 1,
        "cohort_id": f"temporal-review-{session.get('session_id')}-motion-proposal",
        "annotation_policy": "Human-reviewed truth from a Stage 6.6 reviewed temporal capture session, ordered by real source-relative capture time.",
        "frames": ordered,
        "scene_static_structures": {},
        "temporal_sequences": [{
            "sequence_id": str(session.get("session_id")),
            "scene_group": scene_group,
            "ordered_frame_ids": [item["frame_id"] for item in ordered],
            "source_offset_ms_range": [session.get("start_source_offset_ms"), session.get("end_source_offset_ms")],
            "animal_present_intervals": present_intervals,
            "sequence_gap_count": session.get("sequence_gap_count"),
            "generation_reset_count": session.get("generation_reset_count"),
            "proposal_truth": "boxes above reflect reviewed truth only; proposal-generated windows are provenance, not truth",
        }],
    }


def build_replay_export(session: dict[str, object], annotations: AnnotationSet) -> dict[str, object]:
    """The existing Stage 2 `replay.ReplayInput`/`BenchmarkManifest` shape,
    unchanged -- see docs/observation-replay-benchmark-contract.md. Visit-
    level grouping is left empty (`visits: []`) rather than invented: this
    annotation contract records appearance intervals, not reviewed Visit
    boundaries."""

    frames_by_id = {item["frame_id"]: item for item in session.get("frames", [])}  # type: ignore[union-attr]
    ordered_records = sorted(session.get("frames", []), key=lambda item: item["sequence"])  # type: ignore[arg-type,union-attr]
    replay_frames = [
        {
            "index": index, "source_offset_ms": record["source_offset_ms"],
            "content_hash": record["content_hash"], "source_path": f"images/{record['frame_id']}.jpg",
            "analysis_excluded_regions": session.get("config", {}).get("privacy_ignore_regions", []),  # type: ignore[union-attr]
        }
        for index, record in enumerate(ordered_records)
    ]
    index_by_frame_id = {record["frame_id"]: index for index, record in enumerate(ordered_records)}

    appearances = []
    for item in annotations.appearances:
        start, end = frames_by_id.get(item.start_frame_id), frames_by_id.get(item.end_frame_id)
        if start is None or end is None:
            continue
        appearances.append({
            "appearance_id": item.appearance_id,
            "start_offset_ms": start["source_offset_ms"], "end_offset_ms": end["source_offset_ms"],
            "outcome": None, "ambiguous": item.continuity_ambiguous,
        })

    detections = []
    evidence = []
    for frame in annotations.frames:
        if frame.frame_id not in index_by_frame_id or not frame.is_reviewed:
            continue
        index = index_by_frame_id[frame.frame_id]
        for box_index, box in enumerate(frame.boxes):
            detections.append({
                "annotation_id": f"{frame.frame_id}:{box_index}", "frame_index": index,
                "broad_class": box.broad_class, "bounding_box": list(box.box),
            })
        usefulness = frame.evidence_usefulness
        evidence.append({
            "candidate_id": frame.frame_id,
            "subject_visible": frame.whole_frame_truth == "yes",
            "subject_geometry": list(frame.boxes[0].box) if frame.boxes else None,
            "useful_animal_confirmation": usefulness.broad_animal_confirmation_useful if usefulness else None,
            "useful_identification": usefulness.identification_potentially_useful if usefulness else None,
            "useful_context": usefulness.context_useful if usefulness else None,
            "preferred_context": None,
            "ambiguous": frame.whole_frame_truth == "ambiguous",
            "obstruction": any(box.occluded for box in frame.boxes) if frame.boxes else None,
            "motion_blur": any(box.blurred for box in frame.boxes) if frame.boxes else None,
            "clipping": any(box.edge_clipped for box in frame.boxes) if frame.boxes else None,
            "subject_absent": usefulness.subject_absent if usefulness else (frame.whole_frame_truth == "no"),
        })

    return {
        "version": 1,
        "benchmark_id": f"temporal-review-{session.get('session_id')}-replay",
        "input": {
            "input_id": str(session.get("session_id")), "stream_id": session.get("config", {}).get("stream_id"),  # type: ignore[union-attr]
            "width": session.get("config", {}).get("analysis_width"), "height": session.get("config", {}).get("analysis_height"),  # type: ignore[union-attr]
            "nominal_fps": session.get("config", {}).get("nominal_fps"), "frames": replay_frames,  # type: ignore[union-attr]
        },
        "appearances": appearances,
        "visits": [],
        "detections": detections,
        "evidence": evidence,
    }


__all__ = [
    "ACTIVE_LEARNING_CATEGORIES",
    "AL_AMBIGUOUS_TRUTH",
    "AL_BELOW_THRESHOLD_TRUE_POSITIVE",
    "AL_DUPLICATE_DETECTION",
    "AL_EPISODE_BOUNDARY_FAILURE",
    "AL_FALSE_NEGATIVE",
    "AL_FALSE_POSITIVE",
    "AL_HARD_NEGATIVE_MOTION",
    "AL_HARD_NEGATIVE_STATIC",
    "AL_HOLD_FOR_REVIEW",
    "AL_PRIVACY_EXCLUDED",
    "AL_TRACKING_FAILURE",
    "AL_TRUE_POSITIVE",
    "AL_USEFUL_TRAINING_NEGATIVE",
    "AL_USEFUL_TRAINING_POSITIVE",
    "MIN_NEGATIVE_FRAMES_FOR_SUFFICIENCY",
    "MIN_POSITIVE_FRAMES_FOR_SUFFICIENCY",
    "MIN_SCENE_GROUPS_FOR_SUFFICIENCY",
    "MIN_SEQUENCES_FOR_TEMPORAL_SUFFICIENCY",
    "DatasetStatistics",
    "build_detector_calibration_export",
    "build_motion_proposal_export",
    "build_replay_export",
    "classify_active_learning",
    "classify_episode_boundary_failures",
    "classify_export_sufficiency",
    "compute_dataset_statistics",
    "ANNOTATION_CONTRACT_VERSION",
    "ANNOTATION_SCHEMA_VERSION",
    "MATCH_IOU_THRESHOLD",
    "TRUTH_SOURCES",
    "V_AMBIGUOUS_IN_SCORING_DENOMINATOR",
    "V_APPEARANCE_CONTINUITY_UNMARKED",
    "V_APPEARANCE_INTERVAL_REVERSED",
    "V_BOX_OUTSIDE_IMAGE_BOUNDS",
    "V_CAPTURE_FINGERPRINT_MISMATCH",
    "V_CONTENT_HASH_MISMATCH",
    "V_DUPLICATE_LOGICAL_IDENTITY",
    "V_MISSING_SOURCE_MEDIA",
    "V_NEGATIVE_FRAME_HAS_POSITIVE_BOXES",
    "V_PRIVACY_MASKED_MARKED_USABLE",
    "V_PRODUCT_FALSE_POSITIVE_AS_FRAME_NEGATIVE",
    "V_SCORABLE_YES_REQUIRES_BOX",
    "V_STALE_GENERATION_EVIDENCE",
    "V_TEMPORAL_INTERVAL_OUTSIDE_SEQUENCE_BOUNDS",
    "V_UNKNOWN_FRAME_REFERENCE",
    "WHOLE_FRAME_TRUTH_VALUES",
    "AnnotationSet",
    "AppearanceInterval",
    "BoxAnnotation",
    "EvidenceUsefulness",
    "FrameAnnotation",
    "Provenance",
    "TemporalAnnotationError",
    "ValidationIssue",
    "ValidationReport",
    "annotation_skeleton",
    "validate_annotations",
]
