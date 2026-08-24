"""Scene confusor suspicion: pure decision-logic coverage (see
docs/scene-confusor-suspicion-contract.md). Mirrors the established
Stage 6.x/7 pure-module test shape (`tests/test_candidate_visit_authority.py`,
`tests/test_burst_scheduler.py`): no product repository, no database, no
filesystem/network -- these tests exercise `evaluate_scene_confusor_suspicion`
and its geometry-matching/bookkeeping helpers directly, over already-supplied
`SceneRegionSnapshot` facts, never a live query.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from mockingbird.observation.scene_confusor import (
    DEFAULT_GEOMETRY_SPREAD_CEILING,
    DEFAULT_MIN_OCCURRENCES_TO_SUSPECT,
    DEFAULT_MIN_REVIEWED_FALSE_TO_SUSPECT,
    DEFAULT_STRONGER_CONFIDENCE_DELTA,
    SceneConfusorConfig,
    SceneRegionSnapshot,
    evaluate_scene_confusor_suspicion,
    find_matching_region,
    region_fingerprint,
    update_region_bounds,
    update_representative_box,
)

FEEDER_BOX = (0.44, 0.52, 0.49, 0.55)
FAR_AWAY_BOX = (0.05, 0.05, 0.10, 0.10)
SLIGHTLY_SHIFTED_BOX = (0.445, 0.522, 0.492, 0.552)  # within IoU/centroid/size tolerance of FEEDER_BOX
MATERIALLY_DIFFERENT_SIZE_BOX = (0.44, 0.52, 0.60, 0.70)  # same top-left, much larger -- fails size-ratio


def _region(
    *,
    region_id: str = "scene-region:fixture",
    box=FEEDER_BOX,
    broad_class: str = "animal",
    occurrence_count: int = 5,
    reviewed_real_count: int = 0,
    reviewed_false_count: int = 0,
    max_confidence_observed: float | None = 0.4,
    centroid_spread: float = 0.0,
) -> SceneRegionSnapshot:
    x1, y1, x2, y2 = box
    cx, cy = (x1 + x2) / 2.0, (y1 + y2) / 2.0
    # A tight, zero-spread region by default (a static-artifact shape);
    # `centroid_spread` widens the bounds symmetrically around the box's
    # own centroid so callers can construct an arbitrary spread directly
    # rather than replaying a whole occurrence history just for one test.
    half = centroid_spread / 2.0
    return SceneRegionSnapshot(
        region_id=region_id,
        representative_box=box,
        representative_area=(x2 - x1) * (y2 - y1),
        broad_class=broad_class,
        occurrence_count=occurrence_count,
        reviewed_real_count=reviewed_real_count,
        reviewed_false_count=reviewed_false_count,
        max_confidence_observed=max_confidence_observed,
        centroid_min=(cx - half, cy - half),
        centroid_max=(cx + half, cy + half),
    )


# --- module structure --------------------------------------------------------


def test_scene_confusor_module_has_no_product_repository_import() -> None:
    """Structural convention every sibling Stage 6.x/7 decision module in
    this package follows (see e.g. `test_candidate_visit_authority.py`'s
    identical test): pure logic, no filesystem/network/SQLAlchemy/product-
    repository import, so a caller must supply an already-fetched snapshot
    rather than this module reaching for the database itself."""

    source = Path("src/mockingbird/observation/scene_confusor.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    forbidden = {"sqlalchemy", "mockingbird.repository", "mockingbird.api", "requests", "httpx", "sqlite3"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = {alias.name for alias in node.names}
        elif isinstance(node, ast.ImportFrom):
            names = {node.module} if node.module else set()
        else:
            continue
        for name in names:
            assert not any(name == mod or name.startswith(mod + ".") for mod in forbidden), (
                f"scene_confusor.py must stay pure; found forbidden import {name!r}"
            )


# --- no match / brand new geometry -------------------------------------------


def test_no_regions_at_all_is_never_suspected() -> None:
    decision = evaluate_scene_confusor_suspicion(
        candidate_box=FEEDER_BOX, broad_class="animal", max_confidence=0.3, regions=(),
    )
    assert decision.outcome == "not_suspected"
    assert decision.matched_region_id is None


def test_geometrically_distant_region_does_not_match() -> None:
    decision = evaluate_scene_confusor_suspicion(
        candidate_box=FAR_AWAY_BOX, broad_class="animal", max_confidence=0.3,
        regions=(_region(occurrence_count=10),),
    )
    assert decision.outcome == "not_suspected"
    assert decision.reason == "no_recurring_geometry_match"


def test_different_broad_class_does_not_match_even_at_same_geometry() -> None:
    decision = evaluate_scene_confusor_suspicion(
        candidate_box=FEEDER_BOX, broad_class="person", max_confidence=0.3,
        regions=(_region(broad_class="animal", occurrence_count=10),),
    )
    assert decision.outcome == "not_suspected"


def test_materially_different_box_size_does_not_match() -> None:
    decision = evaluate_scene_confusor_suspicion(
        candidate_box=MATERIALLY_DIFFERENT_SIZE_BOX, broad_class="animal", max_confidence=0.3,
        regions=(_region(occurrence_count=10),),
    )
    assert decision.outcome == "not_suspected"


def test_slightly_shifted_box_still_matches_the_same_region() -> None:
    region = _region(occurrence_count=10)
    match = find_matching_region(SLIGHTLY_SHIFTED_BOX, "animal", (region,), SceneConfusorConfig())
    assert match is not None
    assert match.region_id == region.region_id


# --- the first and second occurrence are never suspected ---------------------


def test_first_occurrence_at_a_location_is_never_suspected() -> None:
    # No region exists yet at all -- structurally identical to "no match."
    decision = evaluate_scene_confusor_suspicion(
        candidate_box=FEEDER_BOX, broad_class="animal", max_confidence=0.3, regions=(),
    )
    assert decision.outcome == "not_suspected"


def test_occurrence_count_below_minimum_is_not_suspected() -> None:
    config = SceneConfusorConfig(min_occurrences_to_suspect=DEFAULT_MIN_OCCURRENCES_TO_SUSPECT)
    region = _region(occurrence_count=DEFAULT_MIN_OCCURRENCES_TO_SUSPECT - 1)
    decision = evaluate_scene_confusor_suspicion(
        candidate_box=FEEDER_BOX, broad_class="animal", max_confidence=0.3, regions=(region,), config=config,
    )
    assert decision.outcome == "not_suspected"
    assert decision.reason == "insufficient_recurrence_history"


def test_a_single_stationary_visit_cannot_alone_build_suspicion() -> None:
    """One long, motionless real visit is exactly one occurrence (a
    proposal is one bounded episode regardless of its own duration -- see
    docs/scene-confusor-suspicion-contract.md "Why recurrence, not
    confidence or single-visit stillness"). It can never, by itself, reach
    `min_occurrences_to_suspect` -- this is the structural recall-safety
    property the mechanism is built on, not a tuned threshold."""

    region = _region(occurrence_count=1)
    decision = evaluate_scene_confusor_suspicion(
        candidate_box=FEEDER_BOX, broad_class="animal", max_confidence=0.2, regions=(region,),
    )
    assert decision.outcome == "not_suspected"


# --- recurrence past the threshold is suspected -------------------------------


def test_recurrence_past_threshold_with_no_escape_is_suspected() -> None:
    config = SceneConfusorConfig(min_occurrences_to_suspect=2, stronger_confidence_delta=0.15)
    region = _region(occurrence_count=5, max_confidence_observed=0.4)
    decision = evaluate_scene_confusor_suspicion(
        candidate_box=FEEDER_BOX, broad_class="animal", max_confidence=0.35, regions=(region,), config=config,
    )
    assert decision.outcome == "suspected_confusor"
    assert decision.matched_region_id == region.region_id
    assert decision.reason == "recurring_static_scene_geometry"


def test_reviewed_false_history_is_named_in_the_reason() -> None:
    region = _region(occurrence_count=5, reviewed_false_count=2, max_confidence_observed=0.4)
    decision = evaluate_scene_confusor_suspicion(
        candidate_box=FEEDER_BOX, broad_class="animal", max_confidence=0.3, regions=(region,),
    )
    assert decision.outcome == "suspected_confusor"
    assert decision.reason == "recurring_geometry_with_reviewed_false_history"


# --- reviewed-real protection wins unconditionally ----------------------------


def test_region_with_any_reviewed_real_animal_is_never_suspected() -> None:
    """Human-reviewed true-animal evidence in a region must protect that
    region from suppression, regardless of how much unreviewed recurrence
    history has also accumulated there -- the core recall-safety guarantee
    this milestone requires."""

    region = _region(occurrence_count=50, reviewed_real_count=1, max_confidence_observed=0.9)
    decision = evaluate_scene_confusor_suspicion(
        candidate_box=FEEDER_BOX, broad_class="animal", max_confidence=0.2, regions=(region,),
    )
    assert decision.outcome == "not_suspected"
    assert decision.reason == "region_protected_by_reviewed_real_animal"
    assert decision.escape_signal == "reviewed_real_protection"


def test_reviewed_real_protection_overrides_even_reviewed_false_history() -> None:
    # A region that once looked like a confusor but was later, even once,
    # confirmed to hold a real animal must never suppress again -- reviewed
    # truth always outranks accumulated unreviewed suspicion.
    region = _region(occurrence_count=20, reviewed_false_count=10, reviewed_real_count=1)
    decision = evaluate_scene_confusor_suspicion(
        candidate_box=FEEDER_BOX, broad_class="animal", max_confidence=0.3, regions=(region,),
    )
    assert decision.outcome == "not_suspected"


# --- stronger-than-ever-seen confidence is an escape hatch --------------------


def test_materially_stronger_confidence_than_region_history_escapes_suspicion() -> None:
    config = SceneConfusorConfig(stronger_confidence_delta=DEFAULT_STRONGER_CONFIDENCE_DELTA)
    region = _region(occurrence_count=10, max_confidence_observed=0.3)
    decision = evaluate_scene_confusor_suspicion(
        candidate_box=FEEDER_BOX, broad_class="animal",
        max_confidence=0.3 + DEFAULT_STRONGER_CONFIDENCE_DELTA, regions=(region,), config=config,
    )
    assert decision.outcome == "not_suspected"
    assert decision.escape_signal == "stronger_confidence"


def test_confidence_only_slightly_above_history_does_not_escape() -> None:
    config = SceneConfusorConfig(stronger_confidence_delta=DEFAULT_STRONGER_CONFIDENCE_DELTA)
    region = _region(occurrence_count=10, max_confidence_observed=0.3)
    decision = evaluate_scene_confusor_suspicion(
        candidate_box=FEEDER_BOX, broad_class="animal",
        max_confidence=0.3 + (DEFAULT_STRONGER_CONFIDENCE_DELTA / 2), regions=(region,), config=config,
    )
    assert decision.outcome == "suspected_confusor"


def test_independently_strong_detection_escapes_regardless_of_region_history() -> None:
    """The steady-state recall-safety case this test documents: a real,
    tightly-clustered pair of sightings recurring several times with zero
    intervening review found the *relative* stronger-confidence escape
    alone insufficient (a repeat of the same real subject can never look
    stronger than its own already-strong prior history). This absolute
    escape closes it."""

    config = SceneConfusorConfig()
    region = _region(occurrence_count=10, max_confidence_observed=0.855, centroid_spread=0.001)
    decision = evaluate_scene_confusor_suspicion(
        candidate_box=FEEDER_BOX, broad_class="animal", max_confidence=0.855, regions=(region,), config=config,
    )
    assert decision.outcome == "not_suspected"
    assert decision.reason == "independently_strong_detection"
    assert decision.escape_signal == "strong_detection"


def test_confidence_below_strong_threshold_does_not_use_the_absolute_escape() -> None:
    # Equal to the region's own historical max (no *relative* escape) and
    # below `strong_detection_threshold` (no *absolute* escape either).
    config = SceneConfusorConfig()
    region = _region(occurrence_count=10, max_confidence_observed=0.5, centroid_spread=0.001)
    decision = evaluate_scene_confusor_suspicion(
        candidate_box=FEEDER_BOX, broad_class="animal", max_confidence=0.5, regions=(region,), config=config,
    )
    assert decision.outcome == "suspected_confusor"


def test_unknown_confidence_never_fabricates_an_escape() -> None:
    # `None` means "not known," never treated as either "very low" or "very
    # high" -- honesty rule matching `ConfidenceEvidenceSummary`'s own
    # convention (docs/detection-quality-accounting-contract.md).
    region = _region(occurrence_count=10, max_confidence_observed=None)
    decision = evaluate_scene_confusor_suspicion(
        candidate_box=FEEDER_BOX, broad_class="animal", max_confidence=None, regions=(region,),
    )
    assert decision.outcome == "suspected_confusor"


# --- geometry-spread requirement: the mechanism's core recall-safety fix -----
#
# Motivated by a real failure this milestone's own replay simulation found:
# a popular real feeder perch happened to sit close enough to one unrelated
# false detection that occurrence-count alone would have suspected (and
# blocked) a genuine bird landing there for the third time. Real, repeated
# animal activity spreads its own geometry meaningfully more than a static
# artifact re-detecting identical pixels -- see this module's own
# `DEFAULT_GEOMETRY_SPREAD_CEILING` docstring for the measured real numbers.


def test_wide_geometry_spread_escapes_suspicion_even_past_occurrence_threshold() -> None:
    region = _region(occurrence_count=15, centroid_spread=0.06, max_confidence_observed=0.8)
    decision = evaluate_scene_confusor_suspicion(
        candidate_box=FEEDER_BOX, broad_class="animal", max_confidence=0.2, regions=(region,),
    )
    assert decision.outcome == "not_suspected"
    assert decision.reason == "region_geometry_too_varied_for_static_artifact"
    assert decision.escape_signal == "geometry_spread_exceeds_ceiling"


def test_tight_geometry_spread_past_occurrence_threshold_is_suspected() -> None:
    region = _region(occurrence_count=15, centroid_spread=0.001, max_confidence_observed=0.4)
    decision = evaluate_scene_confusor_suspicion(
        candidate_box=FEEDER_BOX, broad_class="animal", max_confidence=0.2, regions=(region,),
    )
    assert decision.outcome == "suspected_confusor"


def test_real_bird_near_a_coincidental_false_detection_is_not_suspected() -> None:
    """The exact recall-hazard shape this milestone's own replay found: two
    real sightings and one unrelated false detection have already recurred
    at closely matching geometry (3 occurrences, past a naive threshold of
    2), with no review yet and no confidence spike -- but the region's own
    accumulated geometry already shows real spread from the two different
    real birds, which must protect the third (real) arrival."""

    config = SceneConfusorConfig(min_occurrences_to_suspect=2)
    region = _region(occurrence_count=3, centroid_spread=0.04, max_confidence_observed=0.72)
    decision = evaluate_scene_confusor_suspicion(
        candidate_box=FEEDER_BOX, broad_class="animal", max_confidence=0.71, regions=(region,), config=config,
    )
    assert decision.outcome == "not_suspected"


def test_update_region_bounds_starts_at_the_first_occurrence_with_zero_spread() -> None:
    box = (0.4, 0.4, 0.5, 0.5)
    updated_min, updated_max = update_region_bounds(None, None, box)
    expected_centroid = ((box[0] + box[2]) / 2.0, (box[1] + box[3]) / 2.0)
    assert updated_min == updated_max == expected_centroid


def test_update_region_bounds_widens_monotonically() -> None:
    first_min, first_max = update_region_bounds(None, None, FEEDER_BOX)
    second_min, second_max = update_region_bounds(first_min, first_max, SLIGHTLY_SHIFTED_BOX)
    # Widening is monotone: the new bounds can only grow to include the new
    # occurrence, never shrink away from the old one.
    assert second_min[0] <= first_min[0] and second_min[1] <= first_min[1]
    assert second_max[0] >= first_max[0] and second_max[1] >= first_max[1]


def test_default_spread_ceiling_matches_measured_real_cohort_evidence() -> None:
    # Documents the two real, measured numbers this default was chosen
    # from (see the module's own docstring) -- a regression test for the
    # constant's own justification, not just its value: comfortably above
    # the tightest confirmed-confusor spread ever measured (0.0045), and
    # comfortably below the popular real perch's own spread by its 3rd
    # occurrence (0.0105) -- the earliest point recall harm was observed.
    assert 0.0045 < DEFAULT_GEOMETRY_SPREAD_CEILING < 0.0105


# --- geometry helpers: deterministic, reused thresholds -----------------------


@pytest.mark.parametrize(
    "box_a,box_b,expect_match",
    [
        (FEEDER_BOX, FEEDER_BOX, True),
        (FEEDER_BOX, SLIGHTLY_SHIFTED_BOX, True),
        (FEEDER_BOX, FAR_AWAY_BOX, False),
        (FEEDER_BOX, MATERIALLY_DIFFERENT_SIZE_BOX, False),
    ],
)
def test_find_matching_region_geometry_formula(box_a, box_b, expect_match) -> None:
    region = _region(box=box_a, occurrence_count=3)
    match = find_matching_region(box_b, "animal", (region,), SceneConfusorConfig())
    assert (match is not None) is expect_match


def test_region_fingerprint_is_deterministic_and_content_addressed() -> None:
    first = region_fingerprint("stream-1", "animal", FEEDER_BOX)
    second = region_fingerprint("stream-1", "animal", FEEDER_BOX)
    different_stream = region_fingerprint("stream-2", "animal", FEEDER_BOX)
    assert first == second
    assert first != different_stream


def test_update_representative_box_is_an_incremental_mean() -> None:
    updated = update_representative_box(FEEDER_BOX, 1, SLIGHTLY_SHIFTED_BOX)
    for original, shifted, merged in zip(FEEDER_BOX, SLIGHTLY_SHIFTED_BOX, updated):
        low, high = sorted((original, shifted))
        assert low <= merged <= high


def test_config_rejects_out_of_bounds_thresholds() -> None:
    with pytest.raises(ValueError):
        SceneConfusorConfig(geometry_iou_threshold=1.5)
    with pytest.raises(ValueError):
        SceneConfusorConfig(min_occurrences_to_suspect=0)
    with pytest.raises(ValueError):
        SceneConfusorConfig(max_regions_per_stream=0)


# --- Site-Specific Learning & Local Adaptation v1: reviewed-negative-------
# evidence is a second, independent recurrence gate -------------------------
#
# `reviewed_false_count` existed on every region since schema 34 but was
# write-only: it only ever named the disclosed reason once occurrence-count
# alone had already reached suspicion (see `test_reviewed_false_history_is_
# named_in_the_reason`, above), never independently driving the `outcome`.
# These tests cover the new independent path this milestone adds -- see
# "Reviewed-negative-evidence suspicion" in docs/scene-confusor-suspicion-
# contract.md.


def test_reviewed_false_evidence_past_its_own_threshold_is_suspected_below_occurrence_threshold() -> None:
    """The core new capability: two authority-eligible `false_positive`
    reviews at the same recurring geometry are enough to suspect a region
    even though only two admission attempts have ever happened there at all
    -- one occurrence short of the unreviewed `min_occurrences_to_suspect`
    (3). Reviewed evidence is authoritative human truth, not raw pattern
    noise, so a smaller bound is justified (see `DEFAULT_MIN_REVIEWED_
    FALSE_TO_SUSPECT`'s own docstring)."""

    region = _region(
        occurrence_count=DEFAULT_MIN_OCCURRENCES_TO_SUSPECT - 1,
        reviewed_false_count=DEFAULT_MIN_REVIEWED_FALSE_TO_SUSPECT,
        max_confidence_observed=0.3,
    )
    decision = evaluate_scene_confusor_suspicion(
        candidate_box=FEEDER_BOX, broad_class="animal", max_confidence=0.3, regions=(region,),
    )
    assert decision.outcome == "suspected_confusor"
    assert decision.reason == "recurring_geometry_with_reviewed_false_history"


def test_reviewed_false_evidence_below_its_own_threshold_never_alone_suspects() -> None:
    """A single reviewed `false_positive` correction must never alone
    create suspicion -- this milestone's own governing constraint, enforced
    twice: structurally by `SceneConfusorConfig.__post_init__` (a threshold
    below 2 cannot even be configured) and behaviorally here (one reviewed-
    false example, with occurrence count also below its own threshold, is
    not enough)."""

    region = _region(
        occurrence_count=DEFAULT_MIN_OCCURRENCES_TO_SUSPECT - 1,
        reviewed_false_count=1,
        max_confidence_observed=0.3,
    )
    decision = evaluate_scene_confusor_suspicion(
        candidate_box=FEEDER_BOX, broad_class="animal", max_confidence=0.3, regions=(region,),
    )
    assert decision.outcome == "not_suspected"
    assert decision.reason == "insufficient_recurrence_history"


def test_reviewed_evidence_disabled_falls_back_to_pre_milestone_behavior() -> None:
    """The per-Stream "Local adjustment disabled" control: with
    `reviewed_evidence_enabled=False`, a region that would otherwise be
    suspected purely from reviewed-false evidence must behave exactly as
    this module did before this milestone -- occurrence-count recurrence
    only."""

    config = SceneConfusorConfig(reviewed_evidence_enabled=False)
    region = _region(
        occurrence_count=DEFAULT_MIN_OCCURRENCES_TO_SUSPECT - 1,
        reviewed_false_count=10,
        max_confidence_observed=0.3,
    )
    decision = evaluate_scene_confusor_suspicion(
        candidate_box=FEEDER_BOX, broad_class="animal", max_confidence=0.3, regions=(region,), config=config,
    )
    assert decision.outcome == "not_suspected"
    assert decision.reason == "insufficient_recurrence_history"


def test_reviewed_real_protection_wins_even_when_reviewed_false_threshold_is_met() -> None:
    """The core recall-safety guarantee (step 2) is checked before the new
    independent path (step 3) can ever run -- a region a human has ever
    confirmed holds a real animal is never suspected, no matter how much
    reviewed-false evidence has also accumulated there. Conflicting
    reviewed evidence must always resolve toward recall safety."""

    region = _region(
        occurrence_count=1,
        reviewed_false_count=10,
        reviewed_real_count=1,
        max_confidence_observed=0.9,
    )
    decision = evaluate_scene_confusor_suspicion(
        candidate_box=FEEDER_BOX, broad_class="animal", max_confidence=0.2, regions=(region,),
    )
    assert decision.outcome == "not_suspected"
    assert decision.reason == "region_protected_by_reviewed_real_animal"


def test_geometry_spread_escape_still_applies_via_the_reviewed_false_path() -> None:
    """Reviewed-negative evidence satisfies only the recurrence gate (step
    3) -- every escape past it still applies exactly as before. A region
    whose own geometry has spread beyond a static artifact's shape must
    stay protected even once the reviewed-false threshold alone would
    otherwise have been enough to suspect it."""

    region = _region(
        occurrence_count=1,
        reviewed_false_count=DEFAULT_MIN_REVIEWED_FALSE_TO_SUSPECT,
        centroid_spread=0.06,
        max_confidence_observed=0.8,
    )
    decision = evaluate_scene_confusor_suspicion(
        candidate_box=FEEDER_BOX, broad_class="animal", max_confidence=0.2, regions=(region,),
    )
    assert decision.outcome == "not_suspected"
    assert decision.reason == "region_geometry_too_varied_for_static_artifact"


def test_independently_strong_detection_escapes_even_via_the_reviewed_false_path() -> None:
    """A genuinely new, strong detection at a region reviewed-false
    evidence would otherwise suspect must still escape -- this is exactly
    the "new-to-Place species can still be discovered" guarantee at the
    decision-logic level (see Journey 5 in the governing milestone brief)."""

    # Equal to the region's own historical max (no *relative* escape --
    # mirrors `test_independently_strong_detection_escapes_regardless_of_
    # region_history`'s own isolation of the *absolute* escape alone) but
    # past `strong_detection_threshold`.
    region = _region(
        occurrence_count=1,
        reviewed_false_count=DEFAULT_MIN_REVIEWED_FALSE_TO_SUSPECT,
        centroid_spread=0.001,
        max_confidence_observed=0.855,
    )
    decision = evaluate_scene_confusor_suspicion(
        candidate_box=FEEDER_BOX, broad_class="animal", max_confidence=0.855, regions=(region,),
    )
    assert decision.outcome == "not_suspected"
    assert decision.reason == "independently_strong_detection"


def test_config_rejects_reviewed_false_threshold_below_two() -> None:
    with pytest.raises(ValueError):
        SceneConfusorConfig(min_reviewed_false_to_suspect=1)
    with pytest.raises(ValueError):
        SceneConfusorConfig(min_reviewed_false_to_suspect=0)
    # 2 is the smallest legal value -- must not itself raise.
    SceneConfusorConfig(min_reviewed_false_to_suspect=2)
