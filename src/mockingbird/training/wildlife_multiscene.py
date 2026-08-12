"""Multi-Scene Backyard Domain Acquisition + Holdout v2 v1.

Governs three things, all filesystem-only and prioritization/accounting
only -- never human truth, never a training run:

1. **Feeder-tranche reclassification.** `select_feeder_correction_subset`
   selects a deterministic ~200-frame high-information subset of the
   existing 700-frame Stage-3 Tranche A
   (`mockingbird.training.wildlife_stage3_tranche`) so the *default*
   Stage-3 plan no longer leans on ~560 frames from one physical
   environment. Every selected row keeps its inherited `review_status:
   "unreviewed"`/`training_eligible: False` unchanged -- this module never
   creates human truth, exactly like the tranche it draws from.
2. **Scene identity provenance.** `SceneFrameProvenance` and
   `scan_scene_manifests` read the stable physical-scene identity
   `mockingbird.observation.temporal_capture` now attaches to every newly
   captured local frame (`RetainedFrameRecord.scene_id`,
   `CaptureSessionConfig.scene_id`/`capture_purpose`) and join it with
   review provenance from an already-loaded `AnnotationSet`, never
   inferring or guessing a fact no capture/review record actually made.
3. **Holdout v2 scene/session isolation.** `assert_scene_session_holdout_
   isolation` fails closed the moment any row's own `scene_id`/
   `capture_session_id` matches a declared Holdout v2 scene/session,
   independent of that row's own per-row flag. `holdout_v2_records` builds
   the same `HoldoutRecord` shape `wildlife.verify_frozen_benchmark`
   already returns for the frozen-75, so the already-tested, already-
   trusted `wildlife.contamination_report` (exact/identity/parent-identity/
   site-camera-sequence-lineage/near-duplicate) protects a captured
   Holdout v2 scene exactly like it already protects the frozen-75 --
   no new contamination logic invented. `camera_id` carries the scene id
   and `sequence_id` carries the capture session id, so a same-scene
   derived crop (via `parent_identity`, once crop generation exists) or a
   neighboring burst/sequence frame from the same session (via the
   site/camera/sequence lineage-group match) is caught even when its own
   pixels differ enough to dodge the hash checks.

See docs/wildlife-detector-training-contract.md "Scene identity and
multi-scene acquisition" for the governing contract. Nothing in this module
opens the product database, starts a camera/worker, does species
identification, or grants a candidate detector production authority.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from mockingbird.observation.temporal_annotation import AnnotationSet
from mockingbird.observation.temporal_capture import (
    CAPTURE_PURPOSE_HOLDOUT_V2_CANDIDATE,
    CAPTURE_PURPOSE_TRAINING_CANDIDATE,
    SCENE_ID_PATTERN,
)
from mockingbird.observation.temporal_capture_io import FRAMES_DIRECTORY_NAME, HIGH_RESOLUTION_DIRECTORY_NAME
from mockingbird.training.wildlife import (
    HoldoutRecord,
    WildlifeTrainingError,
    canonical_fingerprint,
    dhash64,
    phash64,
    source_pixel_size_bucket,
)
from mockingbird.training.wildlife_stage3_tranche import (
    LANE_EDGE_CONDITION,
    LANE_HARD_NEGATIVE_CONFUSOR,
    LANE_SMALL_FAR_POSITIVE,
    TRANCHE_ID as STAGE3_TRANCHE_A_ID,
    deduplicate,
    distinct_scenes,
)


class WildlifeMultiSceneError(WildlifeTrainingError):
    """A bounded multi-scene acquisition/governance validation error."""


def validate_scene_id(value: str) -> str:
    if not value or not SCENE_ID_PATTERN.fullmatch(value):
        raise WildlifeMultiSceneError("invalid_scene_id")
    return value


# ---------------------------------------------------------------------------
# 1. Feeder-tranche reclassification
# ---------------------------------------------------------------------------

FEEDER_SUBSET_ID = "mockingbird-wildlife-feeder-correction-subset-v1"

# One legacy accounting label applied only by this module's own functions to
# every frame in the existing Stage-2/Stage-3 feeder corpus -- never a
# literal captured `scene_id`. Every one of those frames was captured before
# the `scene_id` field existed (`RetainedFrameRecord.scene_id` is new in
# this same milestone); this label is a disclosed backfill so the scene-
# diversity report (below) can honestly account for "the one scene every
# prior local frame came from" without pretending it was ever recorded that
# way at capture time, and without writing the label back onto any
# historical capture manifest or tranche file.
LEGACY_FEEDER_SCENE_ID = "legacy-feeder-camera-pre-scene-identity"

# Task targets: ~100 small/far-or-known-animal-opportunity, ~70 hard local
# confusors/negatives, ~30 difficult lighting/weather/edge cases -- mapped
# onto Tranche A's own three existing lanes (no new lane vocabulary).
FEEDER_SUBSET_TARGETS: dict[str, int] = {
    LANE_SMALL_FAR_POSITIVE: 100,
    LANE_HARD_NEGATIVE_CONFUSOR: 70,
    LANE_EDGE_CONDITION: 30,
}


def load_tranche_a(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(Path(path).read_text())
    except (OSError, json.JSONDecodeError) as error:
        raise WildlifeMultiSceneError("feeder_subset_source_tranche_unreadable") from error
    if not isinstance(payload, dict) or payload.get("tranche_id") != STAGE3_TRANCHE_A_ID:
        raise WildlifeMultiSceneError("feeder_subset_source_tranche_identity_invalid")
    return payload


def select_feeder_correction_subset(
    tranche_payload: Mapping[str, Any], *, targets: Mapping[str, int] = FEEDER_SUBSET_TARGETS,
) -> dict[str, Any]:
    """Deterministic ~200-frame high-information subset of an already-built
    Stage-3 Tranche A payload (`scripts/build_wildlife_stage3_correction_
    tranche.py`). Reuses the tranche's own existing per-lane priority order
    and `deduplicate`'s encounter-redundancy reduction unchanged -- "prefer
    non-redundant encounters" is exactly what a stricter `min_keep` on the
    same, already-calibrated two-layer dedup already guarantees, not a new
    redundancy rule. Never mutates `review_status`/`training_eligible`, and
    fails closed if any candidate row does not already carry this module's
    own required unreviewed/training-ineligible invariant -- "do not create
    human truth" is enforced, not merely intended.
    """

    if tranche_payload.get("tranche_id") != STAGE3_TRANCHE_A_ID:
        raise WildlifeMultiSceneError("feeder_subset_source_tranche_identity_invalid")
    expected_fingerprint = canonical_fingerprint(
        {key: value for key, value in tranche_payload.items() if key != "semantic_fingerprint"}
    )
    if tranche_payload.get("semantic_fingerprint") != expected_fingerprint:
        raise WildlifeMultiSceneError("feeder_subset_source_tranche_fingerprint_mismatch")

    by_lane: dict[str, list[dict[str, Any]]] = {lane: [] for lane in targets}
    for row in tranche_payload["frames"]:
        lane = row.get("stage3_target_lane")
        if lane in by_lane:
            by_lane[lane].append(row)

    lanes: dict[str, dict[str, Any]] = {}
    selected_flat: list[dict[str, Any]] = []
    for lane, target in targets.items():
        candidates = by_lane[lane]
        for row in candidates:
            if row.get("review_status") != "unreviewed" or row.get("training_eligible") is not False:
                raise WildlifeMultiSceneError("feeder_subset_source_row_not_unreviewed")
        deduped, stats = deduplicate(candidates, min_keep=target)
        if len(deduped) < target:
            raise WildlifeMultiSceneError(f"feeder_subset_lane_unavailable:{lane}")
        selected = deduped[:target]
        stats = stats.capped_to_lane_target(target)
        lanes[lane] = {"target": target, "candidate_pool": len(candidates), "dedup": stats.to_dict()}
        selected_flat.extend(
            {**row, "feeder_subset_id": FEEDER_SUBSET_ID, "feeder_subset_scene_id": LEGACY_FEEDER_SCENE_ID}
            for row in selected
        )

    scenes = distinct_scenes(selected_flat)
    payload: dict[str, Any] = {
        "schema_version": 1,
        "feeder_subset_id": FEEDER_SUBSET_ID,
        "scene_id": LEGACY_FEEDER_SCENE_ID,
        "source_tranche_id": tranche_payload["tranche_id"],
        "source_tranche_fingerprint": tranche_payload["semantic_fingerprint"],
        "targets": dict(targets),
        "lanes": lanes,
        "selected_count": len(selected_flat),
        "distinct_capture_sessions": scenes["distinct_capture_sessions"],
        "frames_per_session": scenes["frames_per_session"],
        "truth_policy": (
            "prioritization only, identical to the source Stage-3 tranche -- every row remains "
            "unreviewed and training-ineligible until named human full-frame review completes"
        ),
        "creates_product_truth": False,
        "frames": selected_flat,
    }
    payload["semantic_fingerprint"] = canonical_fingerprint(payload)
    return payload


def feeder_subset_session_concentration(payload: Mapping[str, Any]) -> dict[str, Any]:
    """The exact retained subset's own session concentration: which single
    capture session contributes the largest share, and how large. All 200
    frames share one physical scene by construction (`LEGACY_FEEDER_SCENE_ID`)
    -- this reports *session*, the next-strongest lineage this legacy corpus
    carries (see docs/wildlife-detector-training-contract.md "Pixel, size,
    and split semantics")."""

    frames_per_session: Mapping[str, int] = payload.get("frames_per_session", {})
    total = sum(frames_per_session.values())
    if not total:
        return {"total": 0, "most_concentrated_session": None, "most_concentrated_fraction": 0.0}
    session, count = max(frames_per_session.items(), key=lambda item: item[1])
    return {
        "total": total,
        "distinct_sessions": len(frames_per_session),
        "most_concentrated_session": session,
        "most_concentrated_count": count,
        "most_concentrated_fraction": count / total,
    }


# ---------------------------------------------------------------------------
# 2. Scene identity provenance
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SceneFrameProvenance:
    """One retained local frame's scene-tagged provenance, read directly
    from an already-persisted capture manifest and, when supplied, an
    already-loaded review `AnnotationSet` -- nothing here is inferred or
    guessed. Only frames carrying a non-empty, explicitly operator-set
    `scene_id` are ever represented (see `scene_frame_provenance_from_
    manifest`); the pre-existing feeder corpus is accounted for separately
    and explicitly via `LEGACY_FEEDER_SCENE_ID`, never backfilled here."""

    scene_id: str
    capture_session_id: str
    source_camera: str
    capture_time: str | None
    frame_id: str
    content_hash: str
    width: int
    height: int
    capture_purpose: str
    high_resolution: bool
    capture_manifest: str
    review_status: str = "unreviewed"
    reviewer: str | None = None
    reviewed_at: str | None = None

    def __post_init__(self) -> None:
        if not self.scene_id or not SCENE_ID_PATTERN.fullmatch(self.scene_id):
            raise WildlifeMultiSceneError("invalid_scene_id")
        if not self.capture_session_id or not self.frame_id or len(self.content_hash) != 64:
            raise WildlifeMultiSceneError("invalid_scene_frame_provenance")
        if self.width < 1 or self.height < 1:
            raise WildlifeMultiSceneError("invalid_scene_frame_dimensions")
        if self.capture_purpose not in (CAPTURE_PURPOSE_TRAINING_CANDIDATE, CAPTURE_PURPOSE_HOLDOUT_V2_CANDIDATE):
            raise WildlifeMultiSceneError("invalid_capture_purpose")


def _review_fields(annotations: AnnotationSet | None, frame_id: str) -> tuple[str, str | None, str | None]:
    if annotations is None:
        return "unreviewed", None, None
    frame = annotations.frame(frame_id)
    if frame is None or not frame.is_reviewed:
        return "unreviewed", None, None
    status = {"yes": "reviewed_positive", "no": "reviewed_negative", "ambiguous": "reviewed_ambiguous"}.get(
        frame.whole_frame_truth, "unreviewed"
    )
    reviewer = frame.provenance.reviewer if frame.provenance is not None else None
    reviewed_at = frame.provenance.reviewed_at_iso if frame.provenance is not None else None
    return status, reviewer, reviewed_at


def scene_frame_provenance_from_manifest(
    manifest_path: Path, *, annotations: AnnotationSet | None = None,
) -> tuple[SceneFrameProvenance, ...]:
    """Real, disk-scanned per-frame scene provenance for one already-written
    `capture-session-manifest.json`. `manifest_path` is kept as a real,
    directly-openable path (not relativized) -- like every `image`/
    `capture_manifest` field the existing Stage-3 tranche pipeline already
    carries, this stays under ignored `data/` and is never committed
    verbatim; only aggregate accounting derived from it is."""

    try:
        payload = json.loads(Path(manifest_path).read_text())
    except (OSError, json.JSONDecodeError) as error:
        raise WildlifeMultiSceneError("scene_manifest_unreadable") from error
    if not isinstance(payload, dict):
        raise WildlifeMultiSceneError("scene_manifest_unreadable")

    config = payload.get("config") or {}
    session_id = str(payload.get("session_id") or "")
    source_camera = str(config.get("stream_id") or "")
    default_width = int(config.get("analysis_width") or 0) or 1
    default_height = int(config.get("analysis_height") or 0) or 1
    manifest_reference = str(manifest_path)

    records: list[SceneFrameProvenance] = []
    for frame in payload.get("frames", []):
        scene_id = str(frame.get("scene_id") or "")
        if not scene_id:
            # Honest omission, not a guess: a frame that predates this field
            # (or was retained by a session that never named its scene) is
            # not represented here at all -- see the module docstring.
            continue
        exact_input = ((frame.get("exact_analysis") or {}).get("detector_input")) or {}
        width = int(exact_input.get("width") or default_width)
        height = int(exact_input.get("height") or default_height)
        capture_time = frame.get("source_capture_timestamp") or frame.get("host_received_at") or None
        frame_id = str(frame["frame_id"])
        status, reviewer, reviewed_at = _review_fields(annotations, frame_id)
        records.append(SceneFrameProvenance(
            scene_id=scene_id,
            capture_session_id=session_id,
            source_camera=source_camera,
            capture_time=str(capture_time) if capture_time else None,
            frame_id=frame_id,
            content_hash=str(frame["content_hash"]),
            width=width,
            height=height,
            capture_purpose=(
                CAPTURE_PURPOSE_HOLDOUT_V2_CANDIDATE if frame.get("holdout_v2_candidate") else CAPTURE_PURPOSE_TRAINING_CANDIDATE
            ),
            high_resolution=bool(frame.get("high_resolution")),
            capture_manifest=manifest_reference,
            review_status=status, reviewer=reviewer, reviewed_at=reviewed_at,
        ))
    return tuple(records)


def scan_scene_manifests(
    manifest_paths: Iterable[Path], *, annotations_by_manifest: Mapping[str, AnnotationSet] | None = None,
) -> tuple[SceneFrameProvenance, ...]:
    """Scan every distinct manifest at most once. `annotations_by_manifest`
    (keyed by `str(manifest_path)`) is optional and additive -- omitted
    entirely, every frame simply reports `review_status="unreviewed"`,
    never a fabricated review outcome."""

    annotations_by_manifest = annotations_by_manifest or {}
    records: list[SceneFrameProvenance] = []
    for manifest_path in dict.fromkeys(manifest_paths):
        records.extend(scene_frame_provenance_from_manifest(
            manifest_path, annotations=annotations_by_manifest.get(str(manifest_path)),
        ))
    return tuple(records)


def annotation_counts_for_scene(
    annotations: AnnotationSet, frame_dimensions: Mapping[str, tuple[int, int]],
) -> dict[str, Any]:
    """Reviewed-truth counts for one scene's own already-loaded
    `AnnotationSet`: usable positive/negative, ambiguous, animal boxes, and
    a source-pixel size-bucket distribution reusing `wildlife.source_pixel_
    size_bucket` -- the same buckets Stage 1-3 already use, never a new
    bucketing scheme. `frame_dimensions` supplies each frame's real source
    width/height (`BoxAnnotation.box` is normalized 0-1); a frame missing
    from it contributes its box count but not a size bucket, honestly."""

    reviewed_positive = reviewed_negative = ambiguous = animal_boxes = 0
    size_buckets: Counter[str] = Counter()
    for frame in annotations.frames:
        if not frame.is_reviewed:
            continue
        if frame.whole_frame_truth == "ambiguous":
            ambiguous += 1
            continue
        if not frame.is_scorable:
            continue
        if frame.whole_frame_truth == "yes":
            reviewed_positive += 1
            width, height = frame_dimensions.get(frame.frame_id, (0, 0))
            for box in frame.boxes:
                animal_boxes += 1
                if width > 0 and height > 0:
                    left, top, right, bottom = box.box
                    size_buckets[source_pixel_size_bucket((right - left) * width, (bottom - top) * height)] += 1
        elif frame.whole_frame_truth == "no":
            reviewed_negative += 1
    return {
        "reviewed_positive": reviewed_positive,
        "reviewed_negative": reviewed_negative,
        "ambiguous": ambiguous,
        "animal_boxes": animal_boxes,
        "size_buckets": dict(sorted(size_buckets.items())),
    }


# ---------------------------------------------------------------------------
# 3. Holdout v2 scene/session isolation (fail closed)
# ---------------------------------------------------------------------------


def scene_capture_purposes(records: Iterable[SceneFrameProvenance]) -> dict[str, frozenset[str]]:
    """Every distinct `capture_purpose` ever recorded for each `scene_id`.
    A scene mapping to more than one purpose is a real, operator-visible
    conflict (a scene captured as both a training candidate and a Holdout
    v2 reservation) -- surfaced by `conflicting_purpose_scene_ids`, never
    silently resolved by picking one."""

    purposes: dict[str, set[str]] = {}
    for record in records:
        purposes.setdefault(record.scene_id, set()).add(record.capture_purpose)
    return {scene_id: frozenset(values) for scene_id, values in purposes.items()}


def conflicting_purpose_scene_ids(purposes: Mapping[str, frozenset[str]]) -> frozenset[str]:
    return frozenset(scene_id for scene_id, values in purposes.items() if len(values) > 1)


def assert_no_scene_purpose_conflict(purposes: Mapping[str, frozenset[str]]) -> None:
    conflicts = conflicting_purpose_scene_ids(purposes)
    if conflicts:
        raise WildlifeMultiSceneError(f"scene_purpose_conflict:{','.join(sorted(conflicts))}")


def holdout_v2_scene_ids(purposes: Mapping[str, frozenset[str]]) -> frozenset[str]:
    return frozenset(
        scene_id for scene_id, values in purposes.items()
        if values == frozenset({CAPTURE_PURPOSE_HOLDOUT_V2_CANDIDATE})
    )


def training_scene_ids(purposes: Mapping[str, frozenset[str]]) -> frozenset[str]:
    return frozenset(
        scene_id for scene_id, values in purposes.items()
        if values == frozenset({CAPTURE_PURPOSE_TRAINING_CANDIDATE})
    )


def assert_scene_session_holdout_isolation(
    rows: Iterable[Mapping[str, Any]],
    *,
    holdout_scene_ids: frozenset[str] = frozenset(),
    holdout_session_ids: frozenset[str] = frozenset(),
) -> None:
    """Fail closed, independent of (never a replacement for) any single
    row's own `holdout_v2_candidate`/`capture_purpose` flag: raise the
    moment ANY row's own `scene_id` or `capture_session_id` matches a
    declared Holdout v2 scene/session, regardless of what that row's own
    per-row flag says. A second, coarser-grained layer -- a row cannot
    misreport its own scene/session identity as easily as one boolean --
    protecting against a future ingestion path that copies frame bytes/
    metadata without faithfully carrying the per-frame flag forward."""

    for row in rows:
        scene_id = str(row.get("scene_id") or "")
        session_id = str(row.get("capture_session_id") or row.get("session_id") or "")
        if scene_id and scene_id in holdout_scene_ids:
            raise WildlifeMultiSceneError(f"holdout_v2_scene_contamination:{scene_id}")
        if session_id and session_id in holdout_session_ids:
            raise WildlifeMultiSceneError(f"holdout_v2_session_contamination:{session_id}")


def holdout_v2_records(
    frame_rows: Iterable[Mapping[str, Any]], *, holdout_scene_ids: frozenset[str],
) -> tuple[HoldoutRecord, ...]:
    """Build the same `HoldoutRecord` shape `wildlife.verify_frozen_
    benchmark` already returns for the frozen-75, for every already-
    captured local frame belonging to a declared Holdout-v2 scene -- so the
    SAME, already-tested `wildlife.contamination_report` protects Holdout
    v2 with zero new contamination logic. `camera_id` carries the scene id
    and `sequence_id` the capture session id: a shared-scene lineage match
    (a neighboring burst/sequence frame from the same session, even one
    whose own pixels differ enough to dodge the hash checks) is caught by
    `contamination_report`'s existing `site_camera_sequence_matches` check.
    `parent_identity=None` here is honest, not a limitation this function
    hides: no local crop-generation step exists yet in this milestone (see
    docs/wildlife-detector-training-contract.md "Stage-3 future corpus
    policy") -- once one does, giving a crop's `parent_identity` its source
    frame's own `source_identity` (already produced below) makes
    `contamination_report`'s existing `holdout_parents` check catch it
    automatically, with no change needed here."""

    records: list[HoldoutRecord] = []
    for row in frame_rows:
        scene_id = str(row.get("scene_id") or "")
        if scene_id not in holdout_scene_ids:
            continue
        image_path = Path(str(row["image"]))
        records.append(HoldoutRecord(
            frame_id=str(row["frame_id"]),
            sha256=str(row["content_hash"]),
            dhash64=dhash64(image_path),
            phash64=phash64(image_path),
            source_identity=f"mockingbird-local-scene:{scene_id}:{row['frame_id']}",
            parent_identity=None,
            site_id="mockingbird-local-site",
            camera_id=scene_id,
            sequence_id=str(row.get("capture_session_id") or ""),
        ))
    return tuple(records)


# ---------------------------------------------------------------------------
# 6. Scene diversity accounting (read-only)
# ---------------------------------------------------------------------------

# Visibility heuristic only -- never an enforced gate (task requirement: "do
# not enforce a magical percentage without evidence, but make concentration
# visible"). More than half the local *training* correction pool coming
# from one physical scene is worth a human's attention; nothing in this
# module blocks selection, training, or review because of it.
SCENE_CONCENTRATION_WARNING_FRACTION = 0.5

# A practical first multi-scene target (task Section 5): not thousands of
# random frames, 5-8 materially distinct physical scenes, at least 3-5
# training/domain-correction scenes and 2+ Holdout-v2-only scenes. The
# lower bound of each range is used as the readiness bar here; the report
# also always states the achieved counts so a human can judge progress
# toward the fuller 5-8/3-5/2+ range directly.
FIRST_MULTISCENE_TARGET_TOTAL_SCENES = 5
FIRST_MULTISCENE_TARGET_TRAINING_SCENES = 3
FIRST_MULTISCENE_TARGET_HOLDOUT_SCENES = 2


def scene_diversity_report(
    *,
    feeder_subset: Mapping[str, Any] | None = None,
    feeder_annotation_counts: Mapping[str, Any] | None = None,
    scene_records: Sequence[SceneFrameProvenance] = (),
    scene_annotation_counts: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Read-only accounting across every known local scene: the legacy
    feeder corpus (if `feeder_subset` -- typically `select_feeder_
    correction_subset`'s own output -- is supplied) plus any newly scanned
    multi-scene captures (`scene_records`, typically `scan_scene_manifests`'s
    output). Never mutates any input; never writes a file itself."""

    scene_annotation_counts = scene_annotation_counts or {}
    scenes: dict[str, dict[str, Any]] = {}

    if feeder_subset is not None:
        frames_per_session = feeder_subset.get("frames_per_session", {})
        counts = feeder_annotation_counts or {}
        scenes[LEGACY_FEEDER_SCENE_ID] = {
            "purpose": CAPTURE_PURPOSE_TRAINING_CANDIDATE,
            "sessions": len(frames_per_session),
            "retained_frames": feeder_subset.get("selected_count", 0),
            "reviewed_positive": counts.get("reviewed_positive", 0),
            "reviewed_negative": counts.get("reviewed_negative", 0),
            "ambiguous": counts.get("ambiguous", 0),
            "animal_boxes": counts.get("animal_boxes", 0),
            "size_buckets": dict(counts.get("size_buckets", {})),
            "note": "backfilled legacy label for the pre-existing single-scene feeder corpus; no frame "
                    "here ever recorded a literal scene_id at capture time",
        }

    purposes = scene_capture_purposes(scene_records)
    conflicts = conflicting_purpose_scene_ids(purposes)
    sessions_by_scene: dict[str, set[str]] = {}
    frames_by_scene: Counter[str] = Counter()
    for record in scene_records:
        sessions_by_scene.setdefault(record.scene_id, set()).add(record.capture_session_id)
        frames_by_scene[record.scene_id] += 1

    for scene_id, values in purposes.items():
        counts = scene_annotation_counts.get(scene_id, {})
        purpose = next(iter(values)) if len(values) == 1 else "conflicting"
        scenes[scene_id] = {
            "purpose": purpose,
            "sessions": len(sessions_by_scene.get(scene_id, ())),
            "retained_frames": frames_by_scene.get(scene_id, 0),
            "reviewed_positive": counts.get("reviewed_positive", 0),
            "reviewed_negative": counts.get("reviewed_negative", 0),
            "ambiguous": counts.get("ambiguous", 0),
            "animal_boxes": counts.get("animal_boxes", 0),
            "size_buckets": dict(counts.get("size_buckets", {})),
        }

    training_scenes = [scene_id for scene_id, info in scenes.items() if info["purpose"] == CAPTURE_PURPOSE_TRAINING_CANDIDATE]
    holdout_scenes = [scene_id for scene_id, info in scenes.items() if info["purpose"] == CAPTURE_PURPOSE_HOLDOUT_V2_CANDIDATE]

    total_training_frames = sum(
        info["retained_frames"] for info in scenes.values() if info["purpose"] == CAPTURE_PURPOSE_TRAINING_CANDIDATE
    )
    concentration: dict[str, Any] = {
        "most_concentrated_scene": None, "most_concentrated_fraction": 0.0, "warning": False,
        "warning_fraction_threshold": SCENE_CONCENTRATION_WARNING_FRACTION,
    }
    if total_training_frames:
        scene_id, info = max(
            ((sid, data) for sid, data in scenes.items() if data["purpose"] == CAPTURE_PURPOSE_TRAINING_CANDIDATE),
            key=lambda item: item[1]["retained_frames"],
        )
        fraction = info["retained_frames"] / total_training_frames
        concentration.update({
            "most_concentrated_scene": scene_id,
            "most_concentrated_frames": info["retained_frames"],
            "total_training_frames": total_training_frames,
            "most_concentrated_fraction": fraction,
            "warning": fraction > SCENE_CONCENTRATION_WARNING_FRACTION,
        })

    reasons: list[str] = []
    if len(scenes) < FIRST_MULTISCENE_TARGET_TOTAL_SCENES:
        reasons.append(f"fewer than {FIRST_MULTISCENE_TARGET_TOTAL_SCENES} total scenes ({len(scenes)})")
    if len(training_scenes) < FIRST_MULTISCENE_TARGET_TRAINING_SCENES:
        reasons.append(f"fewer than {FIRST_MULTISCENE_TARGET_TRAINING_SCENES} training scenes ({len(training_scenes)})")
    if len(holdout_scenes) < FIRST_MULTISCENE_TARGET_HOLDOUT_SCENES:
        reasons.append(f"fewer than {FIRST_MULTISCENE_TARGET_HOLDOUT_SCENES} Holdout v2 scenes ({len(holdout_scenes)})")
    if conflicts:
        reasons.append(f"scenes with conflicting capture purpose: {sorted(conflicts)}")

    return {
        "total_scenes": len(scenes),
        "training_scenes": len(training_scenes),
        "holdout_scenes": len(holdout_scenes),
        "conflicting_purpose_scenes": sorted(conflicts),
        "scenes": scenes,
        "concentration": concentration,
        "first_multiscene_target": {
            "total_scenes_target": FIRST_MULTISCENE_TARGET_TOTAL_SCENES,
            "training_scenes_target": FIRST_MULTISCENE_TARGET_TRAINING_SCENES,
            "holdout_scenes_target": FIRST_MULTISCENE_TARGET_HOLDOUT_SCENES,
            "met": not reasons,
            "reasons": reasons,
        },
    }


# ---------------------------------------------------------------------------
# 7. Human review by scene/session
# ---------------------------------------------------------------------------

# `mockingbird.observation.temporal_review_io.build_stage3_tranche_review_
# packet` requires `priority_tier`/`stage3_target_lane` on every row (the
# shared schema it and `render_review_ui` already read) -- these placeholder
# values carry no Stage-3 lane-prioritization meaning; every row in a scene/
# session review tranche gets the same one, honestly named once here rather
# than a borrowed Stage-3 tier that would misleadingly imply prioritization
# that never happened.
SCENE_REVIEW_PRIORITY_TIER = "scene_capture_review"
SCENE_REVIEW_LANE = "scene_review"


def _scene_record_image_path(record: SceneFrameProvenance) -> Path:
    capture_directory = Path(record.capture_manifest).parent
    subdirectory = HIGH_RESOLUTION_DIRECTORY_NAME if record.high_resolution else FRAMES_DIRECTORY_NAME
    return capture_directory / subdirectory / f"{record.frame_id}.jpg"


def build_scene_review_tranche(
    records: Sequence[SceneFrameProvenance], *, scene_id: str | None = None, session_id: str | None = None,
) -> dict[str, Any]:
    """Filter already-scanned scene provenance to one scene and/or one
    session and re-package it into the same tranche JSON shape `stage3-
    tranche-review-build` already consumes unmodified -- reusing the
    existing browser localization reviewer, not a second review system
    (task requirement). At least one of `scene_id`/`session_id` is
    required; both together reviews one session within one scene."""

    if scene_id is None and session_id is None:
        raise WildlifeMultiSceneError("scene_review_tranche_requires_scene_or_session")
    selected = [
        record for record in records
        if (scene_id is None or record.scene_id == scene_id)
        and (session_id is None or record.capture_session_id == session_id)
    ]
    if not selected:
        raise WildlifeMultiSceneError("scene_review_tranche_empty_selection")

    suffix = ":".join(part for part in (scene_id, session_id) if part)
    frames = [
        {
            "frame_id": record.frame_id,
            "content_hash": record.content_hash,
            "image": str(_scene_record_image_path(record)),
            "capture_session_id": record.capture_session_id,
            "capture_manifest": record.capture_manifest,
            "high_resolution": record.high_resolution,
            "detector_observation_count": 0,
            "animal_detection_count": 0,
            "max_animal_score": None,
            "motion_proposal_count": 0,
            "trigger_reasons": [],
            "priority_tier": SCENE_REVIEW_PRIORITY_TIER,
            "stage3_target_lane": SCENE_REVIEW_LANE,
            "scene_id": record.scene_id,
            "capture_purpose": record.capture_purpose,
        }
        for record in selected
    ]
    payload: dict[str, Any] = {
        "schema_version": 1,
        "tranche_id": f"mockingbird-wildlife-scene-review-tranche-v1:{suffix}",
        "source_queue_id": "mockingbird-wildlife-scene-review-v1",
        "scene_id": scene_id,
        "session_id": session_id,
        "frame_count": len(frames),
        "truth_policy": (
            "prioritization-free grouping only; every row remains unreviewed and training-ineligible "
            "until named human full-frame review completes"
        ),
        "creates_product_truth": False,
        "frames": frames,
    }
    payload["semantic_fingerprint"] = canonical_fingerprint(payload)
    return payload


__all__ = [
    "CAPTURE_PURPOSE_HOLDOUT_V2_CANDIDATE",
    "CAPTURE_PURPOSE_TRAINING_CANDIDATE",
    "FEEDER_SUBSET_ID",
    "FEEDER_SUBSET_TARGETS",
    "FIRST_MULTISCENE_TARGET_HOLDOUT_SCENES",
    "FIRST_MULTISCENE_TARGET_TOTAL_SCENES",
    "FIRST_MULTISCENE_TARGET_TRAINING_SCENES",
    "LEGACY_FEEDER_SCENE_ID",
    "SCENE_CONCENTRATION_WARNING_FRACTION",
    "SCENE_REVIEW_LANE",
    "SCENE_REVIEW_PRIORITY_TIER",
    "SceneFrameProvenance",
    "WildlifeMultiSceneError",
    "annotation_counts_for_scene",
    "assert_no_scene_purpose_conflict",
    "assert_scene_session_holdout_isolation",
    "build_scene_review_tranche",
    "conflicting_purpose_scene_ids",
    "feeder_subset_session_concentration",
    "holdout_v2_records",
    "holdout_v2_scene_ids",
    "load_tranche_a",
    "scan_scene_manifests",
    "scene_capture_purposes",
    "scene_diversity_report",
    "scene_frame_provenance_from_manifest",
    "select_feeder_correction_subset",
    "training_scene_ids",
    "validate_scene_id",
]
