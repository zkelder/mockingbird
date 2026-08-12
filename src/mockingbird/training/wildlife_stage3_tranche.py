"""Stage-3 local domain-correction Tranche A: deterministic prioritization,
redundancy reduction, split assignment, and frozen-holdout contamination
checking over the existing, already-governed 2,000-frame local-correction
queue (`scripts/build_wildlife_local_correction_queue.py`).

This module never labels a frame. It only ranks, deduplicates, and groups
already-unreviewed candidates so a human reviewer's limited time goes to the
highest-information, least-redundant examples first. Every selected row
keeps `review_status: "unreviewed"`/`training_eligible: False` exactly as the
source queue already set them -- see docs/wildlife-detector-training-contract.md
"The deterministic Stage-2 local-correction queue is prioritization only."
The same rule governs this tranche.

Prioritization signals are limited to what the existing queue/manifests
already record (agent full-frame diagnostic review, detector counts/scores,
trigger reasons, existing lane assignment). No exact-frame capture in the
current corpus was ever retained with `--retain-exact-analysis`, so no row
carries a real Geometry Attribution/Counterfactual Lineage envelope; the two
highest-priority task categories ("known detector misses", "off-target
localization failures") are therefore approximated honestly from the two
real signals that do exist (`agent_suggested_positive`, `animal_detection_
count`/`max_animal_score`) and documented as a disclosed proxy, never
claimed as pixel-verified fact -- see `PRIORITY_TIER_KNOWN_MISS_OR_
LOCALIZATION_FAILURE`. If a future capture run does retain a real envelope,
`_priority_tier` reads it automatically and this proxy stops mattering for
those rows without any caller change.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from mockingbird.training.wildlife import (
    HoldoutRecord,
    WildlifeTrainingError,
    canonical_fingerprint,
    dhash64,
    dhash_distance,
    phash64,
    phash_distance,
    sha256_file,
)

TRANCHE_ID = "mockingbird-wildlife-stage3-correction-tranche-a-v1"
SOURCE_QUEUE_ID = "mockingbird-local-wildlife-correction-v0.2"
SEED = 260812

# --------------------------------------------------------------------------
# Lanes (outcome composition) -- task targets: ~325 / ~275 / ~100 of ~700.
# --------------------------------------------------------------------------

LANE_SMALL_FAR_POSITIVE = "small_far_positive_opportunity"
LANE_HARD_NEGATIVE_CONFUSOR = "local_hard_negative_confusor"
LANE_EDGE_CONDITION = "night_weather_edge_condition"

LANE_TARGETS: dict[str, int] = {
    LANE_SMALL_FAR_POSITIVE: 325,
    LANE_HARD_NEGATIVE_CONFUSOR: 275,
    LANE_EDGE_CONDITION: 100,
}

# --------------------------------------------------------------------------
# Priority tiers (global preference order). Tiers 1+2 and 6+7 of the task's
# own nine-step list are honestly merged -- see the two notes below and the
# module docstring.
# --------------------------------------------------------------------------

# Task steps 1 ("known MDv5 detector misses where a real animal was
# independently established") and 2 ("off-target/localization failures") are
# merged into one tier: this corpus's rows carry no raw per-detection box
# geometry (only counts/scores), so a true spatial "off-target" claim cannot
# be distinguished from a plain "miss" without fabricating geometry that was
# never captured. Subset A (a real detector miss: agent-confirmed positive,
# zero detections) is still ranked strictly ahead of subset B (a weak/
# uncertain detector engagement below `LOCALIZATION_FAILURE_SCORE_CEILING`,
# the closest honest proxy for "engaged but likely off-target or unreliable")
# within this one tier -- see `_known_miss_or_localization_failure_key`.
PRIORITY_TIER_KNOWN_MISS_OR_LOCALIZATION_FAILURE = "known_detector_miss_or_localization_failure"
PRIORITY_TIER_SMALL_FAR_OPPORTUNITY = "small_far_opportunity"
PRIORITY_TIER_HIGH_CONFIDENCE_FALSE_POSITIVE = "high_confidence_false_positive"
PRIORITY_TIER_FEEDER_HARDWARE_CONFUSOR = "feeder_hardware_confusor"
# Task steps 6 ("branches/bark/vegetation") and 7 ("shadows/dappled light/
# pavement") are merged: nothing in the existing queue/manifest metadata
# distinguishes vegetation confusors from shadow/pavement confusors (both
# are `static_clutter_negative_candidate` rows without a recurring-geometry
# trigger); a human reviewer applies the specific `branch_or_vegetation` or
# `other_confusor`/`difficult_lighting` difficulty tag once they see the
# actual pixels. See docs/wildlife-detector-training-contract.md "Use
# existing diagnostic/model metadata only for prioritization."
PRIORITY_TIER_VEGETATION_OR_SHADOW_CONFUSOR = "vegetation_or_shadow_confusor"
PRIORITY_TIER_EDGE_CONDITION = "edge_condition"
PRIORITY_TIER_ORDINARY_NEGATIVE_ANCHOR = "ordinary_negative_anchor"

PRIORITY_TIER_ORDER: tuple[str, ...] = (
    PRIORITY_TIER_KNOWN_MISS_OR_LOCALIZATION_FAILURE,
    PRIORITY_TIER_SMALL_FAR_OPPORTUNITY,
    PRIORITY_TIER_HIGH_CONFIDENCE_FALSE_POSITIVE,
    PRIORITY_TIER_FEEDER_HARDWARE_CONFUSOR,
    PRIORITY_TIER_VEGETATION_OR_SHADOW_CONFUSOR,
    PRIORITY_TIER_EDGE_CONDITION,
    PRIORITY_TIER_ORDINARY_NEGATIVE_ANCHOR,
)

# The lane each tier's candidates are drawn into. `ORDINARY_NEGATIVE_ANCHOR`
# is a backstop only, applied to whichever negative lane is short after its
# own natural tiers are exhausted -- never to the positive lane (an
# "ordinary negative" cannot honestly anchor a positive-opportunity quota).
_TIER_LANE: dict[str, str] = {
    PRIORITY_TIER_KNOWN_MISS_OR_LOCALIZATION_FAILURE: LANE_SMALL_FAR_POSITIVE,
    PRIORITY_TIER_SMALL_FAR_OPPORTUNITY: LANE_SMALL_FAR_POSITIVE,
    PRIORITY_TIER_HIGH_CONFIDENCE_FALSE_POSITIVE: LANE_HARD_NEGATIVE_CONFUSOR,
    PRIORITY_TIER_FEEDER_HARDWARE_CONFUSOR: LANE_HARD_NEGATIVE_CONFUSOR,
    PRIORITY_TIER_VEGETATION_OR_SHADOW_CONFUSOR: LANE_HARD_NEGATIVE_CONFUSOR,
    PRIORITY_TIER_EDGE_CONDITION: LANE_EDGE_CONDITION,
}

# A confidence the detector reaches only with real conviction: well above
# the production 0.1 operating point and the review/shadow floors used
# elsewhere, so a row here is a genuinely confident false trigger, not a
# barely-tripped one. See docs/wildlife-detector-stage2-report.md Section 8
# (Stage-2 selected its own 0.3 F1-maximizing threshold from validation).
HIGH_CONFIDENCE_FALSE_POSITIVE_SCORE_FLOOR = 0.5
# The Stage-2 validation-selected operating threshold (see
# docs/wildlife-detector-stage2-report.md Section 8) reused here as the
# ceiling below which an agent-confirmed positive's own detector engagement
# counts as "weak" -- the closest honest proxy this corpus's metadata
# supports for a localization-failure-adjacent case (see the module
# docstring and `PRIORITY_TIER_KNOWN_MISS_OR_LOCALIZATION_FAILURE`).
LOCALIZATION_FAILURE_SCORE_CEILING = 0.3

# Calibrated against this real corpus, not picked a priori: an initial 10s
# bucket, measured after correctly excluding real frozen-benchmark
# near-duplicates (see `frozen_contamination_content_hashes`), left the
# small/far positive lane short of its target by a real ~15% margin -- not a
# bug, but not comfortable headroom for the bounded perceptual pass either.
# 5s is still a materially aggressive sub-burst window (well under half the
# existing `periodic_negative_interval_seconds=30` this codebase already
# uses for spacing *negative* samples, and on the same order as
# `CaptureBounds.pretrigger_frame_count`/`post_trigger_frame_count` context
# windows at typical analysis-stream frame rates) and comfortably clears all
# three lane targets with real headroom to spare for `deduplicate`'s own
# perceptual layer.
DEDUP_TIME_BUCKET_SECONDS = 5
# Frozen-benchmark contamination matching (`check_frozen_contamination`)
# reuses `wildlife.contamination_report`'s own dual-hash convention exactly:
# a real duplicate there may be re-encoded/resized, and a false negative
# (missing genuine contamination) is far more costly than a false positive
# (an extra manual look at 75 fixed images), so a looser bound is correct.
NEAR_DUPLICATE_DHASH_DISTANCE = 4
NEAR_DUPLICATE_PHASH_DISTANCE = 6
# Intra-corpus redundancy dedup (`deduplicate`) is deliberately much
# stricter. Measured directly against this corpus (outdoor daylight feeder
# scenes, small/subtle subjects): whole-frame low-resolution dHash/pHash is
# background-dominated -- a small bird rarely moves enough low-frequency
# energy to change either hash, so the *contamination* thresholds above
# collapsed 1000 candidates to 34 by matching on "same static background"
# rather than genuine repeat shots (verified by direct visual inspection of
# matched pairs). A tight, near-exact bound here still catches real repeats
# (including ones that straddle a time-bucket boundary) without discarding
# visually distinct examples that merely share a background. See
# `deduplicate`'s `min_keep` for the complementary guarantee that this pass
# never removes more than the lane's own target allows regardless of
# threshold.
INTRA_CORPUS_NEAR_DUPLICATE_DHASH_DISTANCE = 1
INTRA_CORPUS_NEAR_DUPLICATE_PHASH_DISTANCE = 2
VALIDATION_FRACTION_TARGET = 0.25


class WildlifeStage3TrancheError(WildlifeTrainingError):
    """A bounded Stage-3 tranche-selection validation or execution failure."""


# --------------------------------------------------------------------------
# Loading
# --------------------------------------------------------------------------


def load_queue(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as error:
        raise WildlifeStage3TrancheError("stage3_source_queue_unreadable") from error
    if not isinstance(payload, dict) or payload.get("queue_id") != SOURCE_QUEUE_ID:
        raise WildlifeStage3TrancheError("stage3_source_queue_identity_invalid")
    frames = payload.get("frames")
    if not isinstance(frames, list) or not frames:
        raise WildlifeStage3TrancheError("stage3_source_queue_empty")
    if payload.get("semantic_fingerprint") != canonical_fingerprint(
        {key: value for key, value in payload.items() if key != "semantic_fingerprint"}
    ):
        raise WildlifeStage3TrancheError("stage3_source_queue_fingerprint_mismatch")
    return payload


def holdout_v2_content_hashes(manifest_paths: Iterable[Path]) -> set[str]:
    """The `content_hash` of every frame any referenced capture manifest
    marks `holdout_v2_candidate=True`. Reads each distinct manifest at most
    once. A manifest predating the Stage-3 Holdout v2 field (every manifest
    in this corpus today) simply contributes nothing -- honest absence, not
    a fabricated `False`. See `temporal_capture.RetainedFrameRecord.
    holdout_v2_candidate`."""

    reserved: set[str] = set()
    for manifest_path in dict.fromkeys(manifest_paths):
        try:
            payload = json.loads(Path(manifest_path).read_text())
        except (OSError, json.JSONDecodeError):
            continue
        for frame in payload.get("frames", []):
            if isinstance(frame, dict) and frame.get("holdout_v2_candidate") is True:
                content_hash = frame.get("content_hash")
                if isinstance(content_hash, str):
                    reserved.add(content_hash)
    return reserved


# --------------------------------------------------------------------------
# Priority tier classification (pure; operates on one queue row dict)
# --------------------------------------------------------------------------


def _known_miss_or_localization_failure_key(row: Mapping[str, Any]) -> tuple[Any, ...] | None:
    if not row.get("agent_suggested_positive"):
        return None
    detections = int(row.get("animal_detection_count") or 0)
    score = row.get("max_animal_score")
    score = float(score) if score is not None else 0.0
    if detections == 0:
        return (0, row["selection_tie_break"])  # subset A: real miss, most severe
    if score < LOCALIZATION_FAILURE_SCORE_CEILING:
        return (1, score, row["selection_tie_break"])  # subset B: weak engagement
    return None


def priority_tier(row: Mapping[str, Any]) -> str | None:
    """The one priority tier one queue row belongs to, or `None` if it does
    not qualify for any tier (never selected). Deterministic and total over
    every row the source queue can produce -- every row falls into exactly
    one tier or `None`, never more than one, so `select_tranche` can assign
    lanes by simple tier membership without a second reconciliation pass."""

    lane = row.get("target_lane")
    if _known_miss_or_localization_failure_key(row) is not None:
        return PRIORITY_TIER_KNOWN_MISS_OR_LOCALIZATION_FAILURE
    if lane == "likely_positive_requires_human_boxes":
        return PRIORITY_TIER_SMALL_FAR_OPPORTUNITY
    score = row.get("max_animal_score")
    score = float(score) if score is not None else 0.0
    if lane in ("static_clutter_negative_candidate", "weather_lighting_negative_candidate"):
        if score >= HIGH_CONFIDENCE_FALSE_POSITIVE_SCORE_FLOOR:
            return PRIORITY_TIER_HIGH_CONFIDENCE_FALSE_POSITIVE
    if lane == "static_clutter_negative_candidate":
        if "recurring_static_geometry" in row.get("trigger_reasons", ()):
            return PRIORITY_TIER_FEEDER_HARDWARE_CONFUSOR
        return PRIORITY_TIER_VEGETATION_OR_SHADOW_CONFUSOR
    if lane == "weather_lighting_negative_candidate":
        return PRIORITY_TIER_EDGE_CONDITION
    return None


def _within_tier_sort_key(row: Mapping[str, Any], tier: str) -> tuple[Any, ...]:
    if tier == PRIORITY_TIER_KNOWN_MISS_OR_LOCALIZATION_FAILURE:
        key = _known_miss_or_localization_failure_key(row)
        assert key is not None  # only called for rows already classified into this tier
        return key
    if tier == PRIORITY_TIER_HIGH_CONFIDENCE_FALSE_POSITIVE:
        score = row.get("max_animal_score")
        score = float(score) if score is not None else 0.0
        return (-score, row["selection_tie_break"])
    # Every other tier reuses the source queue's own already-deterministic
    # within-lane ranking (`lane_priority`, built from `_positive_order`/
    # `_static_order`/`_weather_order` at queue-build time) rather than
    # recomputing an equivalent rule.
    return (int(row.get("lane_priority") or 0), row["selection_tie_break"])


# --------------------------------------------------------------------------
# Redundancy reduction
# --------------------------------------------------------------------------


def _temporal_cluster_key(row: Mapping[str, Any]) -> str:
    """Strongest cheap redundancy signal: same capture session (== one
    continuous scene/camera run) and the same short time bucket. Encounter/
    session and temporal-neighborhood in one key, at zero image-decode cost.
    A row with no parseable timestamp is never silently merged into another
    row's cluster -- it gets its own singleton key instead."""

    session = str(row.get("capture_session_id") or "")
    timestamp = row.get("source_capture_timestamp")
    if timestamp:
        try:
            parsed = datetime.fromisoformat(str(timestamp))
            bucket = int(parsed.timestamp() // DEDUP_TIME_BUCKET_SECONDS)
            return f"{session}:{bucket}"
        except ValueError:
            pass
    return f"{session}:frame:{row.get('frame_id')}"


@dataclass(frozen=True)
class DedupStats:
    candidates_before_dedup: int
    removed_by_temporal_cluster: int
    removed_by_perceptual_similarity: int
    selected: int
    # Surplus, non-duplicate rows trimmed only because a lane already had
    # enough higher-priority representatives without them -- never a
    # detected duplicate. Zero unless `capped_to_lane_target` applied one.
    removed_above_lane_target: int = 0

    def capped_to_lane_target(self, target: int) -> "DedupStats":
        """Layer a lane's own target cap on top of this already-deduped
        result, honestly attributing any further trim to its own category
        instead of silently inflating `removed_by_perceptual_similarity` or
        leaving `selected` describing a pre-truncation count nothing
        downstream actually receives. A no-op when `target` does not need
        to remove anything further (the lane's own `deduplicate(...,
        min_keep=target)` call already guarantees `selected >= target`)."""

        if target >= self.selected:
            return self
        return DedupStats(
            candidates_before_dedup=self.candidates_before_dedup,
            removed_by_temporal_cluster=self.removed_by_temporal_cluster,
            removed_by_perceptual_similarity=self.removed_by_perceptual_similarity,
            selected=target,
            removed_above_lane_target=self.selected - target,
        )

    def to_dict(self) -> dict[str, int]:
        return {
            "candidates_before_dedup": self.candidates_before_dedup,
            "removed_by_temporal_cluster": self.removed_by_temporal_cluster,
            "removed_by_perceptual_similarity": self.removed_by_perceptual_similarity,
            "removed_above_lane_target": self.removed_above_lane_target,
            "selected": self.selected,
            "redundancy_removed": self.candidates_before_dedup - self.selected,
        }


def deduplicate(
    ordered_rows: list[dict[str, Any]],
    *,
    near_dhash: int = INTRA_CORPUS_NEAR_DUPLICATE_DHASH_DISTANCE,
    near_phash: int = INTRA_CORPUS_NEAR_DUPLICATE_PHASH_DISTANCE,
    min_keep: int = 0,
) -> tuple[list[dict[str, Any]], DedupStats]:
    """Two-layer, priority-order-preserving redundancy reduction. `ordered_rows`
    must already be in the caller's own priority order -- the first (highest-
    priority) row in a redundant cluster always wins the representative slot.

    Layer 1 (free): collapse same-session/same-time-bucket rows to one
    representative -- "one or a few representative frames per redundant
    cluster" for the dominant real-world case (a burst of near-identical
    frames from one encounter). Bucket granularity (`DEDUP_TIME_BUCKET_
    SECONDS`) is deliberately short enough that genuine temporal variation
    across a longer encounter still yields multiple representative frames.

    Layer 2 (bounded image decode, layer-1 survivors only): a perceptual
    dHash+pHash dual-corroborated near-duplicate pass -- catches a near-
    duplicate scene that recurs outside one time bucket (a long static
    stretch, or a different session revisiting a visually identical
    composition). `min_keep` bounds how much this layer alone may remove: it
    stops dropping rows once `min_keep` would be breached, so a caller that
    passes its own lane target here gets the most aggressive redundancy
    reduction that still honestly reaches that target, never less -- see
    `INTRA_CORPUS_NEAR_DUPLICATE_DHASH_DISTANCE`'s docstring for why this
    layer needs a floor at all rather than just a stricter fixed threshold.
    Layer 1 has no such floor: session/time-bucket collapse is cheap,
    unambiguous, and never adjustable away from being "the same moment."
    """

    before = len(ordered_rows)
    by_cluster: dict[str, dict[str, Any]] = {}
    cluster_order: list[str] = []
    for row in ordered_rows:
        key = _temporal_cluster_key(row)
        if key not in by_cluster:
            by_cluster[key] = row
            cluster_order.append(key)
    layer1 = [by_cluster[key] for key in cluster_order]
    removed_layer1 = before - len(layer1)

    kept: list[dict[str, Any]] = []
    kept_hashes: list[tuple[str, str]] = []
    removed_layer2 = 0
    removable_budget = max(0, len(layer1) - max(0, min_keep))
    for row in layer1:
        duplicate = False
        if removable_budget > 0:
            image_path = Path(row["image"])
            if image_path.is_file():
                row_dhash = dhash64(image_path)
                row_phash = phash64(image_path)
                for existing_dhash, existing_phash in kept_hashes:
                    if (
                        dhash_distance(row_dhash, existing_dhash) <= near_dhash
                        and phash_distance(row_phash, existing_phash) <= near_phash
                    ):
                        duplicate = True
                        break
                if not duplicate:
                    kept_hashes.append((row_dhash, row_phash))
        if duplicate:
            removed_layer2 += 1
            removable_budget -= 1
            continue
        kept.append(row)

    stats = DedupStats(
        candidates_before_dedup=before, removed_by_temporal_cluster=removed_layer1,
        removed_by_perceptual_similarity=removed_layer2, selected=len(kept),
    )
    return kept, stats


# --------------------------------------------------------------------------
# Selection orchestration
# --------------------------------------------------------------------------


def select_tranche(
    queue_payload: Mapping[str, Any],
    *,
    holdout_v2_hashes: frozenset[str] = frozenset(),
    frozen_contamination_hashes: frozenset[str] = frozenset(),
    lane_targets: Mapping[str, int] = LANE_TARGETS,
) -> dict[str, Any]:
    """Build Tranche A from an already-loaded queue payload. Returns the
    lane-by-lane selection, dedup accounting, and the flat selected-frame
    list (each row annotated with `priority_tier`/`target_lane` -- renamed
    from the source queue's own `target_lane` to `source_lane` to avoid
    collision -- plus `stage3_tranche_id`).

    Both exclusion sets are applied *before* tier classification -- not only
    checked afterward -- so a lane a contaminated or holdout-v2-reserved row
    would otherwise have occupied naturally backfills from the next-best
    real candidate instead of silently shipping a smaller tranche. See
    `frozen_contamination_content_hashes` and `holdout_v2_content_hashes`.
    """

    excluded_holdout_v2 = 0
    excluded_frozen_contamination = 0
    by_tier: dict[str, list[dict[str, Any]]] = {tier: [] for tier in PRIORITY_TIER_ORDER}
    for row in queue_payload["frames"]:
        content_hash = row.get("content_hash")
        if content_hash in holdout_v2_hashes:
            excluded_holdout_v2 += 1
            continue
        if content_hash in frozen_contamination_hashes:
            excluded_frozen_contamination += 1
            continue
        tier = priority_tier(row)
        if tier is not None:
            by_tier[tier].append(row)
    for tier in by_tier:
        by_tier[tier].sort(key=lambda row, tier=tier: _within_tier_sort_key(row, tier))

    lanes: dict[str, dict[str, Any]] = {}
    # Backstop pool: leftover static-clutter/weather rows not claimed by any
    # of their lane's own tiers, ordered by the source queue's own `lane_
    # priority`. Given the current `priority_tier` rules, every static-
    # clutter/weather row is always classified into tier 4, 5, 6-7, or 8
    # (exhaustively confirmed: no input leaves either negative lane
    # unclassified), so this pool is always empty against this contract's
    # own tier rules today -- it is deliberate defense-in-depth, not dead
    # code removed, so a future `priority_tier` refinement that legitimately
    # leaves a negative-lane row unclassified still degrades to "anchor with
    # an ordinary negative" instead of silently under-filling a lane.
    claimed_ids = {
        id(row) for tier in PRIORITY_TIER_ORDER if tier != PRIORITY_TIER_ORDINARY_NEGATIVE_ANCHOR
        for row in by_tier[tier]
    }
    backstop_pool = [
        row for row in queue_payload["frames"]
        if row.get("content_hash") not in holdout_v2_hashes
        and row.get("content_hash") not in frozen_contamination_hashes
        and row.get("target_lane") in ("static_clutter_negative_candidate", "weather_lighting_negative_candidate")
        and id(row) not in claimed_ids
    ]
    backstop_pool.sort(key=lambda row: (int(row.get("lane_priority") or 0), row["selection_tie_break"]))
    by_tier[PRIORITY_TIER_ORDINARY_NEGATIVE_ANCHOR] = backstop_pool

    for lane, target in lane_targets.items():
        tiers_for_lane = [tier for tier in PRIORITY_TIER_ORDER if _TIER_LANE.get(tier) == lane]
        if lane != LANE_SMALL_FAR_POSITIVE:
            tiers_for_lane.append(PRIORITY_TIER_ORDINARY_NEGATIVE_ANCHOR)
        candidate_order = [row for tier in tiers_for_lane for row in by_tier[tier]]
        # `min_keep=target`: dedup as aggressively as the real image content
        # allows, but never past the point of honestly under-shooting this
        # lane's own target -- see `deduplicate`'s docstring.
        deduped, stats = deduplicate(candidate_order, min_keep=target)
        if len(deduped) < target:
            raise WildlifeStage3TrancheError(f"stage3_tranche_lane_unavailable:{lane}")
        selected = deduped[:target]
        stats = stats.capped_to_lane_target(target)
        tier_of: dict[int, str] = {}
        for tier in tiers_for_lane:
            for row in by_tier[tier]:
                tier_of.setdefault(id(row), tier)
        lanes[lane] = {
            "target": target,
            "candidate_pool_by_tier": {tier: len(by_tier[tier]) for tier in tiers_for_lane},
            "dedup": stats.to_dict(),
            "selected_rows": [
                {**row, "priority_tier": tier_of[id(row)], "stage3_target_lane": lane}
                for row in selected
            ],
        }

    selected_flat = [row for lane_result in lanes.values() for row in lane_result["selected_rows"]]
    return {
        "excluded_holdout_v2_hashes": excluded_holdout_v2,
        "excluded_frozen_contamination_hashes": excluded_frozen_contamination,
        "lanes": {
            lane: {
                "target": result["target"],
                "candidate_pool_by_tier": result["candidate_pool_by_tier"],
                "dedup": result["dedup"],
            }
            for lane, result in lanes.items()
        },
        "frames": selected_flat,
    }


# --------------------------------------------------------------------------
# Train/validation split (session/encounter-level, deterministic)
# --------------------------------------------------------------------------

LOCAL_TRAIN_CANDIDATE = "local_train_candidate"
LOCAL_VALIDATION_CANDIDATE = "local_validation_candidate"


def _stable_hash(*parts: object, seed: int) -> str:
    return sha256(":".join([str(seed), *(str(part) for part in parts)]).encode()).hexdigest()


# 2**22 candidate subsets (~4.2M) stays a sub-second scan; comfortable
# headroom over the real governing corpus (11 sessions) for a while yet.
# Beyond this, `_closest_validation_prefix` remains correct, just no longer
# exhaustively optimal.
_EXHAUSTIVE_SPLIT_SEARCH_SESSION_LIMIT = 22


def _closest_validation_subset(session_sizes: list[int], target_validation: int) -> tuple[int, ...]:
    """Every possible whole-session grouping (2**N, N = len(session_sizes)),
    scored by absolute distance from `target_validation`; the closest wins.
    Deterministic: session order is already seed-derived, and ties break on
    the lowest subset (as a bitmask) at the winning distance -- both fully
    reproducible for a fixed seed and input order, never randomized."""

    best_mask = 0
    best_distance = target_validation  # the empty subset has a sum of 0
    for mask in range(1, 1 << len(session_sizes)):
        total = sum(size for index, size in enumerate(session_sizes) if mask & (1 << index))
        distance = abs(total - target_validation)
        if distance < best_distance:
            best_distance = distance
            best_mask = mask
    return tuple(index for index in range(len(session_sizes)) if best_mask & (1 << index))


def _closest_validation_prefix(session_sizes: list[int], target_validation: int) -> tuple[int, ...]:
    """Cheaper fallback for a session count too large to search
    exhaustively: the closest whole-session *prefix* of the already seed-
    ordered session list, not necessarily the closest possible subset."""

    best_prefix_length = 0
    best_distance = target_validation  # the empty prefix has running=0
    running = 0
    for index, size in enumerate(session_sizes, start=1):
        running += size
        distance = abs(running - target_validation)
        if distance < best_distance:
            best_distance = distance
            best_prefix_length = index
    return tuple(range(best_prefix_length))


def assign_local_split(
    selected_rows: list[dict[str, Any]], *, seed: int = SEED, validation_fraction: float = VALIDATION_FRACTION_TARGET,
) -> dict[str, Any]:
    """Assign every selected row a `split_candidate` at whole-
    `capture_session_id` granularity -- never frame-randomized within a
    session (task requirement).

    Real sessions vary widely in size, so a plain "stop at the first prefix
    that reaches the target" greedy walk can overshoot badly (measured: one
    real run landed at 37.6% validation against a 25% target this way).
    With a small number of distinct sessions (the real governing case: this
    corpus has 11), `_closest_validation_subset` instead searches every
    possible whole-session grouping exhaustively for the one closest to the
    target frame count -- still fully deterministic (a fixed seed always
    finds the same subset; ties break on the seed-derived seed-hash order),
    still never splits a session, and demonstrably closer to the stated
    target than either a greedy walk or a single prefix search can
    guarantee. Falls back to the cheaper closest-prefix search only when the
    session count is too large to search exhaustively."""

    sessions: dict[str, list[dict[str, Any]]] = {}
    for row in selected_rows:
        sessions.setdefault(str(row["capture_session_id"]), []).append(row)
    total = len(selected_rows)
    target_validation = round(total * validation_fraction)

    ordered_sessions = sorted(sessions, key=lambda session_id: _stable_hash(session_id, seed=seed))
    session_sizes = [len(sessions[session_id]) for session_id in ordered_sessions]
    if len(ordered_sessions) <= _EXHAUSTIVE_SPLIT_SEARCH_SESSION_LIMIT:
        validation_indices = _closest_validation_subset(session_sizes, target_validation)
    else:
        validation_indices = _closest_validation_prefix(session_sizes, target_validation)
    validation_sessions: set[str] = {ordered_sessions[index] for index in validation_indices}

    for row in selected_rows:
        row["split_candidate"] = (
            LOCAL_VALIDATION_CANDIDATE if row["capture_session_id"] in validation_sessions else LOCAL_TRAIN_CANDIDATE
        )

    validation_count = sum(1 for row in selected_rows if row["split_candidate"] == LOCAL_VALIDATION_CANDIDATE)
    return {
        "seed": seed,
        "validation_fraction_target": validation_fraction,
        "validation_session_count": len(validation_sessions),
        "train_session_count": len(sessions) - len(validation_sessions),
        "validation_frame_count": validation_count,
        "train_frame_count": total - validation_count,
        "validation_fraction_achieved": (validation_count / total) if total else 0.0,
    }


def assert_no_split_leakage(selected_rows: Iterable[dict[str, Any]]) -> None:
    """One `capture_session_id` (the strongest available encounter/session
    lineage this queue's rows carry) can never appear on both sides of the
    split -- mirrors `wildlife.assert_no_group_leakage`'s invariant."""

    assignment: dict[str, str] = {}
    for row in selected_rows:
        session_id = str(row["capture_session_id"])
        split = row["split_candidate"]
        existing = assignment.setdefault(session_id, split)
        if existing != split:
            raise WildlifeStage3TrancheError("stage3_split_session_leakage")


# --------------------------------------------------------------------------
# Frozen-benchmark contamination check
# --------------------------------------------------------------------------


def _row_matches_against_holdout(
    row: Mapping[str, Any], holdout: tuple[HoldoutRecord, ...], *, near_dhash: int, near_phash: int,
) -> tuple[str | None, list[dict[str, str]], list[dict[str, Any]]]:
    """One row's real content-hash integrity result, exact-SHA-256 matches,
    and dual-hash near-duplicate matches against the frozen holdout. Shared
    by the pre-selection exclusion scan and the post-selection verification
    pass so both apply byte-identical matching logic."""

    image_path = Path(row["image"])
    actual_sha256 = sha256_file(image_path)
    if actual_sha256 != row["content_hash"]:
        return actual_sha256, [], []
    exact = [
        {"frame_id": row["frame_id"], "holdout_frame_id": record.frame_id}
        for record in holdout if actual_sha256 == record.sha256
    ]
    row_dhash, row_phash = dhash64(image_path), phash64(image_path)
    near = []
    for record in holdout:
        dhash_gap = dhash_distance(row_dhash, record.dhash64)
        phash_gap = phash_distance(row_phash, record.phash64)
        if dhash_gap <= near_dhash and phash_gap <= near_phash:
            near.append({
                "frame_id": row["frame_id"], "holdout_frame_id": record.frame_id,
                "dhash_distance": dhash_gap, "phash_distance": phash_gap,
            })
    return actual_sha256, exact, near


def frozen_contamination_content_hashes(
    rows: list[dict[str, Any]],
    *,
    holdout: tuple[HoldoutRecord, ...],
    near_dhash: int = NEAR_DUPLICATE_DHASH_DISTANCE,
    near_phash: int = NEAR_DUPLICATE_PHASH_DISTANCE,
) -> tuple[set[str], dict[str, Any]]:
    """Pre-selection exclusion scan: every `content_hash` among `rows`
    (typically the *full* source queue, not only an already-selected
    tranche) that exactly matches or is a dual-hash near-duplicate of one of
    the frozen-benchmark images in `holdout`. Excluding these *before*
    prioritization -- not only checking the final selection afterward --
    means a lane short-filled by contamination naturally backfills from the
    next-best candidate instead of silently shipping a smaller tranche.

    `holdout` is supplied by the caller (typically `wildlife.
    verify_frozen_benchmark`'s real, checksum-verified return value) rather
    than loaded here, mirroring `wildlife.contamination_report`'s own
    convention exactly: the expensive per-image hashing of the 75 frozen
    frames happens once regardless of how many times a caller needs to
    check against it, and a test can supply a small synthetic `HoldoutRecord`
    tuple without needing to satisfy `verify_frozen_benchmark`'s own
    checksum-pinned-to-the-real-file gate."""

    excluded: set[str] = set()
    exact_count = near_count = integrity_failures = 0
    for row in rows:
        actual_sha256, exact, near = _row_matches_against_holdout(row, holdout, near_dhash=near_dhash, near_phash=near_phash)
        if actual_sha256 != row["content_hash"]:
            integrity_failures += 1
            continue
        if exact:
            exact_count += 1
            excluded.add(row["content_hash"])
        if near:
            near_count += 1
            excluded.add(row["content_hash"])
    summary = {
        "scanned_rows": len(rows),
        "checked_holdout_frames": len(holdout),
        "near_duplicate_dhash_distance": near_dhash,
        "near_duplicate_phash_distance": near_phash,
        "excluded_exact_match_count": exact_count,
        "excluded_near_duplicate_count": near_count,
        "content_hash_integrity_failures": integrity_failures,
        "total_excluded_content_hashes": len(excluded),
    }
    return excluded, summary


def check_frozen_contamination(
    selected_rows: list[dict[str, Any]],
    *,
    holdout: tuple[HoldoutRecord, ...],
    near_dhash: int = NEAR_DUPLICATE_DHASH_DISTANCE,
    near_phash: int = NEAR_DUPLICATE_PHASH_DISTANCE,
) -> dict[str, Any]:
    """Verify every *already-selected* Tranche-A frame against `holdout`
    (typically `wildlife.verify_frozen_benchmark`'s real, checksum-verified
    75-frame return value) -- the final, honest proof step, run after
    `frozen_contamination_content_hashes` has already excluded contaminated
    rows upstream (see `select_tranche`), using the same exact-SHA-256 and
    dual-hash near-duplicate rules `wildlife.contamination_report` applies
    for materialization -- reimplemented here (not called directly) because
    `contamination_report` requires a fully reviewed, truth-authoritative
    `CorpusExample`, which a pre-review Tranche-A candidate structurally
    cannot honestly construct (see docs/wildlife-detector-training-contract.md
    "Model- or agent-generated boxes are suggestions only"). Source/parent-
    identity and site/camera/sequence lineage matches from that function are
    intentionally not reimplemented: a local capture frame has no external
    corpus source/site identity to coincidentally collide with beyond exact
    bytes or a genuine near-duplicate, both of which are checked here."""

    exact_matches: list[dict[str, str]] = []
    near_matches: list[dict[str, Any]] = []
    integrity_failures: list[dict[str, str]] = []
    for row in selected_rows:
        actual_sha256, exact, near = _row_matches_against_holdout(row, holdout, near_dhash=near_dhash, near_phash=near_phash)
        if actual_sha256 != row["content_hash"]:
            integrity_failures.append({"frame_id": row["frame_id"], "expected": row["content_hash"], "actual": actual_sha256})
            continue
        exact_matches.extend(exact)
        near_matches.extend(near)
    return {
        "checked_frames": len(selected_rows),
        "checked_holdout_frames": len(holdout),
        "near_duplicate_dhash_distance": near_dhash,
        "near_duplicate_phash_distance": near_phash,
        "exact_sha256_matches": exact_matches,
        "near_duplicate_matches": near_matches,
        "content_hash_integrity_failures": integrity_failures,
        "passed": not (exact_matches or near_matches or integrity_failures),
    }


# --------------------------------------------------------------------------
# Reporting helpers
# --------------------------------------------------------------------------


def distinct_scenes(selected_rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    sessions = Counter(row["capture_session_id"] for row in selected_rows)
    return {
        "distinct_capture_sessions": len(sessions),
        "frames_per_session": dict(sorted(sessions.items())),
    }


__all__ = [
    "DEDUP_TIME_BUCKET_SECONDS",
    "HIGH_CONFIDENCE_FALSE_POSITIVE_SCORE_FLOOR",
    "LANE_EDGE_CONDITION",
    "LANE_HARD_NEGATIVE_CONFUSOR",
    "LANE_SMALL_FAR_POSITIVE",
    "LANE_TARGETS",
    "LOCALIZATION_FAILURE_SCORE_CEILING",
    "LOCAL_TRAIN_CANDIDATE",
    "LOCAL_VALIDATION_CANDIDATE",
    "INTRA_CORPUS_NEAR_DUPLICATE_DHASH_DISTANCE",
    "INTRA_CORPUS_NEAR_DUPLICATE_PHASH_DISTANCE",
    "NEAR_DUPLICATE_DHASH_DISTANCE",
    "NEAR_DUPLICATE_PHASH_DISTANCE",
    "PRIORITY_TIER_EDGE_CONDITION",
    "PRIORITY_TIER_FEEDER_HARDWARE_CONFUSOR",
    "PRIORITY_TIER_HIGH_CONFIDENCE_FALSE_POSITIVE",
    "PRIORITY_TIER_KNOWN_MISS_OR_LOCALIZATION_FAILURE",
    "PRIORITY_TIER_ORDER",
    "PRIORITY_TIER_ORDINARY_NEGATIVE_ANCHOR",
    "PRIORITY_TIER_SMALL_FAR_OPPORTUNITY",
    "PRIORITY_TIER_VEGETATION_OR_SHADOW_CONFUSOR",
    "SEED",
    "SOURCE_QUEUE_ID",
    "TRANCHE_ID",
    "VALIDATION_FRACTION_TARGET",
    "DedupStats",
    "WildlifeStage3TrancheError",
    "assert_no_split_leakage",
    "assign_local_split",
    "check_frozen_contamination",
    "deduplicate",
    "distinct_scenes",
    "frozen_contamination_content_hashes",
    "holdout_v2_content_hashes",
    "load_queue",
    "priority_tier",
    "select_tranche",
]
