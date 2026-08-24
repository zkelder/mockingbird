"""Scene confusor suspicion: bounded, evidence-weighted disclosure that one
candidate's own persisted evidence geometry closely, repeatedly matches an
image-space region this Stream has produced many prior admission attempts
from, without any of them ever being confirmed a real animal by reviewed
truth. See docs/scene-confusor-suspicion-contract.md for the full contract
this module implements.

Motivated by Observational Quality Closure v1's own finding (see
docs/observational-quality-closure-v1-report.md): slightly over half
(52.9%, 37/70) of real admitted candidate Visits in a large,
non-session-concentrated real cohort showed no animal at all, and 76% of
those false positives clustered into just six recurring static geometric
hot spots -- not diffuse noise. Confidence-gated admission was directly
swept against that same cohort and rejected (see "Production authority
gate" in docs/detection-quality-accounting-contract.md): no confidence
threshold materially rejects the recurring false positives without also
losing real animals. This module answers a different question a confidence
floor cannot: not "how confident was this one detection" but "does this
detection's own geometry keep recurring at this Stream, across separate
admission attempts, without ever once being confirmed a real animal."

Pure: no filesystem, network, CUDA/ONNX Runtime/OpenCV, product-repository,
or SQLAlchemy import -- the same structural convention every sibling
Stage 6.x/7 decision module in this package follows
(`test_scene_confusor_module_has_no_product_repository_import`). This
module never fetches, creates, or evicts a durable region record itself; a
caller (the one impure seam, `mockingbird.repository.product_repository`)
fetches a small, bounded, already-capped snapshot of a Stream's own durable
regions and supplies it here as `SceneRegionSnapshot`s -- mirroring
`candidate_visit_authority.AuthorityState` exactly: a pure decision over an
already-fetched fact, never a live database handle threaded through a
"pure" module.

## Why recurrence, not confidence or single-visit stillness

A static scene artifact (a shadow, a feeder-silhouette texture) and a real
bird perched motionless at the same spot for a whole visit produce
*structurally identical* single-encounter evidence: a small, possibly-low-
confidence box that does not move much. Neither raw detector confidence
(already tested and rejected at real cohort scale, above) nor within-visit
stillness can safely tell them apart without risking exactly the recall
harm this milestone's own governing constraints prohibit -- a bird may
repeatedly perch on exactly the same feeder, branch, lawn patch, roof edge,
or fence post. What *does* differ is repetition **across separate
encounters**: one assembled proposal is one bounded episode (see
tracklet-visit-assembly-contract.md) regardless of how long the underlying
visit lasted, so a single five-minute stationary bird contributes exactly
one occurrence to a region no matter how still it sat -- it is
structurally incapable of building suspicion by itself (see
`test_a_single_stationary_visit_cannot_alone_build_suspicion`). Suspicion
only accumulates from many *separate* admission attempts recurring at
closely matching geometry, a materially safer claim than "this subject did
not move."
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Literal, Sequence

BoundingBox = tuple[float, float, float, float]

# Reused, not invented: identical to `burst_scheduler.BurstSchedulerConfig`'s
# own already-validated geometry-recurrence formula and thresholds (IoU +
# centroid + size-ratio -- the same convention `detector_benchmark.
# cluster_static_false_positives` and `temporal_capture.
# RecurringGeometryTracker` independently already use for the same purpose
# at other pipeline stages). The formula is duplicated here, not imported,
# matching this package's own established "each pure module stays
# self-contained" convention (see e.g. counterfactual_lineage.py's
# identical disclosure for its own duplicated geometry helpers).
GEOMETRY_IOU_THRESHOLD = 0.3
GEOMETRY_CENTROID_THRESHOLD = 0.05
SIZE_CHANGE_RATIO_THRESHOLD = 0.35

# Deliberately more conservative than `burst_scheduler.BurstSchedulerConfig.
# min_recurrence_to_suppress` (2): that decision only costs one extra
# high-resolution photo and is reversible on the very next opportunity;
# this decision can withhold an entire reviewable Visit from a human, for a
# proposal that already passed detector confirmation, tracking, and shadow
# assembly. Direct replay simulation against this milestone's own real
# cohort (see docs/scene-confusor-suspicion-contract.md "Why occurrence
# count alone is not enough") found `min_occurrences_to_suspect=2` lets a
# real bird get incorrectly suspected the moment it lands near an
# unrelated, coincidentally-nearby false detection, before enough history
# exists to tell the two apart -- a genuine, demonstrated recall hazard,
# not a hypothetical one. Combined with the geometry-spread requirement
# below, an exhaustive grid search over this same real replay found 3 the
# smallest value on the stable, wide (not knife-edge) zero-real-harm
# plateau -- see the contract doc for the full sweep.
DEFAULT_MIN_OCCURRENCES_TO_SUSPECT = 3

# Reused, not invented: identical to
# `burst_scheduler.BurstSchedulerConfig.stronger_confidence_delta`.
DEFAULT_STRONGER_CONFIDENCE_DELTA = 0.15

# Reused, not invented: identical to `frame_tracker.TrackerConfiguration.
# strong_detection_threshold` / `encounter_accounting.STRONG_CONFIDENCE_
# THRESHOLD` -- this codebase's own already-established, independently-
# precedented bar for "genuinely confirmed," not a new number invented for
# this module. A second, real replay-simulation finding (see "Why
# occurrence count alone is not enough," above) motivates its use here
# specifically: a steady-state stress replay (the same tiny, real,
# tightly-clustered pair of sightings recurring several times with zero
# intervening review) found the *relative* `stronger_confidence_delta`
# escape alone insufficient -- a region's own historical ceiling can equal
# a real subject's own typical confidence, so a repeat of the same real
# subject can never look "stronger than its own history." An *absolute*
# escape closes this: `docs/sustained-visit-continuity-contract.md`'s own
# real measurement already established that a static/hardware confusor's
# confidence essentially never reaches this bar at all (attempt-2's real
# red-glass-feeder clutter measured a maximum of 0.417 across its entire
# session) -- so a candidate that independently clears it is real,
# corroborating evidence on its own, regardless of what this region's own
# history looks like.
DEFAULT_STRONG_DETECTION_THRESHOLD = 0.7

# Reused, not invented: identical to `burst_scheduler.BurstSchedulerConfig.
# max_recurrence_groups` / `temporal_capture._MAX_TRACKED_CLUSTERS`.
DEFAULT_MAX_REGIONS_PER_STREAM = 64

# A genuinely static scene artifact (a shadow, a feeder-silhouette texture)
# re-detects at essentially pixel-identical geometry every single time --
# only detector/quantization noise separates one occurrence's box from the
# next. Real, repeated animal activity at a popular real location (the same
# feeder perch visited by many different individual birds over time) instead
# shows meaningfully more box-to-box variation, even while every individual
# occurrence still matches the same region under `find_matching_region`'s
# own IoU/centroid/size test. This was not assumed -- it was measured
# directly against this milestone's own real cohort (see
# docs/scene-confusor-suspicion-contract.md "Why a geometry-spread
# requirement, not occurrence count alone"): the confirmed-false-only
# dome-top region's own centroid spread across all 8 real occurrences
# stayed flat at 0.0045 (normalized) or below; a real, popular feeder-perch
# region's own spread was already 0.0105 by its 3rd occurrence and grew to
# 0.0524 by its 15th. 0.008 sits in the middle of the wide, stable
# zero-real-harm plateau (~0.0045-0.010) an exhaustive grid search found
# against that same real cohort, comfortably above the tightest confirmed
# confusor and comfortably below where the popular real perch's own early
# growth would otherwise start being wrongly caught.
DEFAULT_GEOMETRY_SPREAD_CEILING = 0.008

# A bounded, conservative, disclosed default -- not derived from a
# representative longitudinal sample (the only real cohort available when
# this module was built spans four days, too short to responsibly derive a
# decay constant from). Long enough that a genuinely persistent confusor
# (a shadow, a chimney vent) is not forgotten between infrequent real
# sessions; short enough that a camera moved or reconfigured without
# tripping the explicit invalidation hook (see the repository-level
# `apply_camera_configuration` integration) does not carry stale
# suspicion indefinitely. Revisit once more longitudinal field data exists.
DEFAULT_REGION_TTL_DAYS = 45

# Site-Specific Learning & Local Adaptation v1 (see docs/scene-confusor-
# suspicion-contract.md, "Reviewed-negative-evidence suspicion"):
# `reviewed_false_count` existed on every region since schema 34 but was
# write-only -- it named the disclosed reason once occurrence-count alone
# already reached suspicion, but never independently drove the `outcome`.
# This constant is the one new recurrence gate the milestone actually
# needed: a smaller bound than `DEFAULT_MIN_OCCURRENCES_TO_SUSPECT` (3) is
# justified because each contributing example here already passed a much
# higher bar than a raw unreviewed detector proposal -- an authority-
# eligible human explicitly reviewed this exact recurring geometry and
# labeled it `false_positive` (see `review_provenance.is_authority_eligible`
# and "Reviewed-truth interaction," below). Deliberately never 1: this
# milestone's own governing constraint is that a single correction must
# never alone create a permanent suppression rule, so `SceneConfusorConfig.
# __post_init__` enforces a floor of 2 structurally, not just by default.
# Unlike `min_occurrences_to_suspect`/`geometry_spread_ceiling`, this value
# was not derived from a real-cohort grid search -- this repository's own
# live database has zero pre-existing `scene_confusor_regions` rows to
# replay against (every one of its real `false_positive` reviews predates
# or bypassed a live admission session that would have built recurrence
# history). 2 is a disclosed, conservative starting point pending real
# field evidence, exactly like every other "insufficient evidence yet"
# posture this milestone's own doctrine treats as a legitimate, honest
# state -- not a hypothetical hedge. Acceptance correction (2026-08-24,
# see "Reviewed-negative-evidence production activation" in
# docs/scene-confusor-suspicion-contract.md): precisely *because* this value
# was never organically field-validated, `SceneConfusorConfig.
# reviewed_evidence_enabled` now defaults `False` -- this gate remains fully
# defined, structurally floored, and available for a caller (production, once
# an operator opts in; a shadow/counterfactual evaluation always) to engage
# explicitly, but no longer engages itself in production admission merely by
# existing.
DEFAULT_MIN_REVIEWED_FALSE_TO_SUSPECT = 2

SceneConfusorOutcome = Literal["not_suspected", "suspected_confusor"]


@dataclass(frozen=True)
class SceneConfusorConfig:
    """Every bound is explicit, reused where possible, and validated --
    matching `BurstSchedulerConfig`'s own `__post_init__` convention."""

    geometry_iou_threshold: float = GEOMETRY_IOU_THRESHOLD
    geometry_centroid_threshold: float = GEOMETRY_CENTROID_THRESHOLD
    size_change_ratio_threshold: float = SIZE_CHANGE_RATIO_THRESHOLD
    min_occurrences_to_suspect: int = DEFAULT_MIN_OCCURRENCES_TO_SUSPECT
    stronger_confidence_delta: float = DEFAULT_STRONGER_CONFIDENCE_DELTA
    strong_detection_threshold: float = DEFAULT_STRONG_DETECTION_THRESHOLD
    geometry_spread_ceiling: float = DEFAULT_GEOMETRY_SPREAD_CEILING
    max_regions_per_stream: int = DEFAULT_MAX_REGIONS_PER_STREAM
    region_ttl_days: int = DEFAULT_REGION_TTL_DAYS
    # Site-Specific Learning & Local Adaptation v1: the independent
    # reviewed-negative-evidence recurrence gate (see
    # `DEFAULT_MIN_REVIEWED_FALSE_TO_SUSPECT`'s own docstring). Structurally
    # floored at 2 in `__post_init__`, not just defaulted -- this milestone's
    # own governing constraint ("never turn a single correction into a
    # permanent ignore rule") is enforced as an invariant of the config
    # itself, not merely a convention a caller could accidentally override.
    min_reviewed_false_to_suspect: int = DEFAULT_MIN_REVIEWED_FALSE_TO_SUSPECT
    # Per-Stream operator control (see "Reset / disable" in the contract
    # doc): `False` restores exactly this module's pre-milestone shipped
    # behavior (occurrence-count recurrence only) without discarding any
    # already-accumulated `reviewed_real_count`/`reviewed_false_count`
    # bookkeeping -- disabling is instant and reversible, distinct from
    # resetting (deleting) region history entirely.
    #
    # Acceptance correction (2026-08-24): defaults `False`, not `True` --
    # conservative-by-default, not merely "harmless by default." The
    # original `True` default relied entirely on the abstention gate above
    # (this path is a no-op wherever `reviewed_false_count` has not yet
    # earned it) to argue enabling it changed no *currently* observed
    # behavior. That argument says nothing about the future: the very first
    # time a real Stream's own field use produces two authority-eligible
    # `false_positive` reviews at the same recurring geometry, a `True`
    # default would have started influencing production admission on an
    # unvalidated threshold (`min_reviewed_false_to_suspect`, disclosed
    # candidate-not-field-validated -- see its own docstring) with no
    # explicit operator decision ever having been made. `False` makes that
    # decision require an actual, explicit, informed opt-in (see
    # `ProductRepository.set_scene_confusor_reviewed_evidence_enabled`) --
    # exactly the field-testing posture this milestone's own doctrine
    # otherwise asks for. Nothing else about the mechanism is gated by this
    # flag: occurrence-count recurrence (the pre-existing, already-
    # field-validated mechanism), reviewed-evidence state accumulation,
    # reversibility (revision/reopen retraction), and status/counterfactual
    # reporting are all unconditional and continue exactly as before,
    # regardless of this flag's value -- only step 3's independent
    # reviewed-false recurrence gate (`evaluate_scene_confusor_suspicion`,
    # below) reads it at all.
    reviewed_evidence_enabled: bool = False

    def __post_init__(self) -> None:
        if not (0.0 <= self.geometry_iou_threshold <= 1.0):
            raise ValueError("geometry_iou_threshold must be within [0, 1]")
        if not (0.0 <= self.geometry_centroid_threshold <= 1.0):
            raise ValueError("geometry_centroid_threshold must be within [0, 1]")
        if not (0.0 <= self.size_change_ratio_threshold <= 1.0):
            raise ValueError("size_change_ratio_threshold must be within [0, 1]")
        if self.min_occurrences_to_suspect < 1:
            raise ValueError("min_occurrences_to_suspect must be at least 1")
        if not (0.0 <= self.stronger_confidence_delta <= 1.0):
            raise ValueError("stronger_confidence_delta must be within [0, 1]")
        if not (0.0 <= self.strong_detection_threshold <= 1.0):
            raise ValueError("strong_detection_threshold must be within [0, 1]")
        if self.geometry_spread_ceiling < 0.0:
            raise ValueError("geometry_spread_ceiling must not be negative")
        if self.max_regions_per_stream < 1:
            raise ValueError("max_regions_per_stream must be at least 1")
        if self.region_ttl_days < 1:
            raise ValueError("region_ttl_days must be at least 1")
        if self.min_reviewed_false_to_suspect < 2:
            raise ValueError(
                "min_reviewed_false_to_suspect must be at least 2 -- a single "
                "reviewed correction must never alone create a permanent "
                "suppression rule"
            )


@dataclass(frozen=True)
class SceneRegionSnapshot:
    """One already-fetched durable per-Stream recurring-geometry fact --
    never constructed by this module. `region_id` is a stable, content
    -addressed identity (see `region_fingerprint`, and
    `product_repository.SceneConfusorRegionModel` for the durable row this
    is projected from). Carries only what a pure decision needs, the same
    "snapshot, never a live handle" shape as
    `candidate_visit_authority.AuthorityState`.

    `centroid_min`/`centroid_max` are the running bounding range of every
    occurrence's own centroid ever matched to this region (cheap, O(1) to
    update per occurrence -- see `update_region_bounds`); `centroid_spread`
    derives the one scalar `evaluate_scene_confusor_suspicion` actually
    needs from them. A brand-new region (its own first occurrence, not yet
    touched a second time) reports `centroid_spread == 0.0`, honestly --
    not enough history to show any spread at all yet, never fabricated."""

    region_id: str
    representative_box: BoundingBox
    representative_area: float
    broad_class: str
    occurrence_count: int
    reviewed_real_count: int
    reviewed_false_count: int
    max_confidence_observed: float | None
    centroid_min: tuple[float, float]
    centroid_max: tuple[float, float]

    @property
    def centroid_spread(self) -> float:
        dx = self.centroid_max[0] - self.centroid_min[0]
        dy = self.centroid_max[1] - self.centroid_min[1]
        return (dx * dx + dy * dy) ** 0.5


@dataclass(frozen=True)
class SceneConfusorDecision:
    """`reason` is a stable, enumerable code (never free text) -- see
    docs/scene-confusor-suspicion-contract.md for the full vocabulary.
    `escape_signal` names which countervailing evidence let a
    geometrically-matching, otherwise-suspectable region through, mirroring
    `burst_scheduler.BurstDecision`'s own `novelty_signals` disclosure."""

    outcome: SceneConfusorOutcome
    reason: str
    matched_region_id: str | None
    escape_signal: str | None


def _box_area(box: BoundingBox) -> float:
    left, top, right, bottom = box
    return max(0.0, right - left) * max(0.0, bottom - top)


def _centroid(box: BoundingBox) -> tuple[float, float]:
    left, top, right, bottom = box
    return ((left + right) / 2.0, (top + bottom) / 2.0)


def _centroid_distance(a: BoundingBox, b: BoundingBox) -> float:
    ax, ay = _centroid(a)
    bx, by = _centroid(b)
    return ((ax - bx) ** 2 + (ay - by) ** 2) ** 0.5


def _iou(a: BoundingBox, b: BoundingBox) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    intersection = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    union = _box_area(a) + _box_area(b) - intersection
    return intersection / union if union > 0 else 0.0


def _size_ratio_within(area_a: float, area_b: float, threshold: float) -> bool:
    if area_a <= 0 or area_b <= 0:
        return False
    ratio = min(area_a, area_b) / max(area_a, area_b)
    return ratio >= (1.0 - threshold)


def find_matching_region(
    box: BoundingBox,
    broad_class: str,
    regions: Sequence[SceneRegionSnapshot],
    config: SceneConfusorConfig | None = None,
) -> SceneRegionSnapshot | None:
    """Deterministic: the first supplied region whose own representative
    geometry matches `box` on every dimension (class, IoU, centroid
    distance, size ratio) -- identical formula to
    `burst_scheduler.BurstScheduler._matches`, reused at a durable,
    cross-session granularity instead of an in-memory, per-session one. No
    exact coordinate or scene name is ever compared; every test is a
    general, relative geometry test that behaves the same for any camera
    layout or subject location."""

    config = config or SceneConfusorConfig()
    for region in regions:
        if region.broad_class != broad_class:
            continue
        if _iou(box, region.representative_box) < config.geometry_iou_threshold:
            continue
        if _centroid_distance(box, region.representative_box) > config.geometry_centroid_threshold:
            continue
        if not _size_ratio_within(_box_area(box), region.representative_area, config.size_change_ratio_threshold):
            continue
        return region
    return None


def evaluate_scene_confusor_suspicion(
    *,
    candidate_box: BoundingBox,
    broad_class: str,
    max_confidence: float | None,
    regions: Sequence[SceneRegionSnapshot],
    config: SceneConfusorConfig | None = None,
) -> SceneConfusorDecision:
    """The one decision function this module exists to provide. Never
    raises for ordinary input; never fabricates a match, a protection, or
    an escape it cannot support from the supplied facts. Decision order:

    1. No geometrically-matching region at all -> `not_suspected` (a brand
       new location, or this Stream's history genuinely does not cover it,
       always gets the benefit of the doubt -- matches
       `burst_scheduler`'s own "first occurrence never suppressed"
       precedent).
    2. The matched region has ever been confirmed to hold a real animal by
       authority-eligible reviewed truth -> `not_suspected`,
       unconditionally, regardless of how much unreviewed recurrence
       history -- or reviewed-false history -- has also accumulated there.
       See "Reviewed-truth interaction" in docs/scene-confusor-suspicion-
       contract.md -- this is the mechanism's core recall-safety guarantee,
       and it is checked before either recurrence gate below, so it can
       never be raced or outvoted by them.
    3. The matched region has not yet recurred `min_occurrences_to_suspect`
       times, AND has not separately accumulated `min_reviewed_false_to_
       suspect` authority-eligible `false_positive` reviews (only when
       `reviewed_evidence_enabled`) -> `not_suspected` (a single visit,
       however long or still, cannot alone build suspicion; see this
       module's own docstring). Reviewed-negative evidence is a second,
       independent path to satisfy this same gate -- not a bypass of
       anything past it: every escape below (geometry spread, both
       confidence escapes) still applies exactly the same regardless of
       which path got a candidate this far, so a genuinely different or
       stronger real detection at this geometry is exactly as protected
       either way.
    4. The matched region's own accumulated geometry across its recurrences
       is more varied than `geometry_spread_ceiling` -> `not_suspected` (an
       escape: real, repeated animal activity at a popular real location
       measurably spreads more than a static artifact re-detecting the same
       pixels -- see "Why a geometry-spread requirement, not occurrence
       count alone" in docs/scene-confusor-suspicion-contract.md. This is
       what protects a real bird returning to a favorite perch that happens
       to sit near an unrelated, coincidental false detection: occurrence
       count alone cannot tell the two apart this early, but the region's
       own shape can.)
    5. This candidate's own confidence is materially higher than anything
       this region has ever produced -> `not_suspected` (an escape,
       mirroring `burst_scheduler`'s `stronger_confidence` novelty signal).
    6. This candidate's own confidence independently clears
       `strong_detection_threshold`, regardless of this region's own
       history -> `not_suspected` (an absolute escape distinct from step 5;
       see `DEFAULT_STRONG_DETECTION_THRESHOLD`'s own docstring for the
       real steady-state replay finding this closes -- a repeat real
       sighting at its own already-strong confidence can never be
       penalized merely for matching its own prior strength).
    7. Otherwise -> `suspected_confusor`. Never a permanent verdict on the
       region itself (see the repository-level reviewed-truth/
       reconfiguration-invalidation hooks) -- only a decision about this
       one candidate, at this one moment, given the evidence available now.
    """

    config = config or SceneConfusorConfig()
    region = find_matching_region(candidate_box, broad_class, regions, config)
    if region is None:
        return SceneConfusorDecision("not_suspected", "no_recurring_geometry_match", None, None)

    if region.reviewed_real_count > 0:
        return SceneConfusorDecision(
            "not_suspected",
            "region_protected_by_reviewed_real_animal",
            region.region_id,
            "reviewed_real_protection",
        )

    reviewed_false_eligible = (
        config.reviewed_evidence_enabled
        and region.reviewed_false_count >= config.min_reviewed_false_to_suspect
    )
    if region.occurrence_count < config.min_occurrences_to_suspect and not reviewed_false_eligible:
        return SceneConfusorDecision(
            "not_suspected", "insufficient_recurrence_history", region.region_id, None,
        )

    if region.centroid_spread > config.geometry_spread_ceiling:
        return SceneConfusorDecision(
            "not_suspected",
            "region_geometry_too_varied_for_static_artifact",
            region.region_id,
            "geometry_spread_exceeds_ceiling",
        )

    if (
        max_confidence is not None
        and region.max_confidence_observed is not None
        and max_confidence >= region.max_confidence_observed + config.stronger_confidence_delta
    ):
        return SceneConfusorDecision(
            "not_suspected",
            "stronger_confidence_than_region_history",
            region.region_id,
            "stronger_confidence",
        )

    # Absolute escape, independent of this region's own history (see
    # `DEFAULT_STRONG_DETECTION_THRESHOLD`'s own docstring for the real
    # replay finding this closes): a candidate whose own confidence
    # independently clears this codebase's already-established "genuinely
    # confirmed" bar is real, corroborating evidence on its own -- a
    # repeat real sighting can never be penalized merely for matching its
    # own, already-strong, prior confidence.
    if max_confidence is not None and max_confidence >= config.strong_detection_threshold:
        return SceneConfusorDecision(
            "not_suspected",
            "independently_strong_detection",
            region.region_id,
            "strong_detection",
        )

    reason = (
        "recurring_geometry_with_reviewed_false_history"
        if region.reviewed_false_count > 0
        else "recurring_static_scene_geometry"
    )
    return SceneConfusorDecision("suspected_confusor", reason, region.region_id, None)


def region_fingerprint(stream_id: str, broad_class: str, box: BoundingBox) -> str:
    """A stable, content-addressed region identity -- mirrors
    `burst_scheduler`'s own `"recurrence:" + fingerprint(...)` convention,
    deliberately *not* including a session/process identity (unlike that
    in-memory precedent), since this identity must remain stable across
    sessions and app restarts. Rounded to 3 decimal places (~1px at
    typical source resolution) so float jitter from the incremental-mean
    update below never mints a second identity for what is, in every
    geometry test above, the same region."""

    rounded = tuple(round(value, 3) for value in box)
    payload = "|".join((stream_id, broad_class, *(str(value) for value in rounded)))
    return "scene-region:" + sha256(payload.encode("utf-8")).hexdigest()[:24]


def update_representative_box(
    existing_box: BoundingBox, existing_occurrence_count: int, new_box: BoundingBox,
) -> BoundingBox:
    """Incremental running mean -- identical shape to
    `burst_scheduler._RecurrenceGroup`'s own `_touch_group` update, so a
    region's representative geometry stays centered on its own true
    average location rather than drifting to whichever occurrence happened
    to create it. `existing_occurrence_count` is the count *before* this
    new occurrence (must be >= 1; a brand-new region has no "existing" box
    to average against and should simply start at `new_box`)."""

    count = max(1, existing_occurrence_count)
    return tuple(
        round((existing * count + new) / (count + 1), 6)
        for existing, new in zip(existing_box, new_box)
    )


def update_region_bounds(
    existing_min: tuple[float, float] | None,
    existing_max: tuple[float, float] | None,
    new_box: BoundingBox,
) -> tuple[tuple[float, float], tuple[float, float]]:
    """Cheap, O(1) running centroid-bounds update backing
    `SceneRegionSnapshot.centroid_spread` -- never a retained per-occurrence
    history (this package's own established "bounded structured facts, not
    full history" convention; see e.g. `counterfactual_lineage.
    TrackGenerationRecord`'s identical envelope-not-trajectory tradeoff).
    `existing_min`/`existing_max` are `None` for a region's own first
    occurrence (nothing to bound against yet)."""

    new_centroid = _centroid(new_box)
    if existing_min is None or existing_max is None:
        return new_centroid, new_centroid
    updated_min = (min(existing_min[0], new_centroid[0]), min(existing_min[1], new_centroid[1]))
    updated_max = (max(existing_max[0], new_centroid[0]), max(existing_max[1], new_centroid[1]))
    return updated_min, updated_max
