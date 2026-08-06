"""Hardware-free tests for the Stage 6.5 adaptive motion-proposal strategy
geometry and temporal-eligibility rules.

All frame planes here are synthetic plain-Python grayscale grids; no PIL,
OpenCV, ONNX Runtime, CUDA, camera, or product database is touched. Numbered
sections mirror the task's required hardware-free-test list.
"""
from __future__ import annotations

from dataclasses import replace

import pytest

from mockingbird.observation.motion_proposal_strategy import (
    FULL_FRAME_PLUS_MOTION_PROPOSALS,
    MAX_RAW_REGIONS_BEFORE_MERGE,
    REASON_DUPLICATE_FRAME_IDENTITY,
    REASON_EXCESSIVE_CHANGED_PIXEL_RATIO,
    REASON_EXCESSIVE_SOURCE_TIME_GAP,
    REASON_FIRST_FRAME_NO_PREDECESSOR,
    REASON_FULLY_PRIVACY_MASKED,
    REASON_GLOBAL_LUMINANCE_SHIFT,
    REASON_PROVIDER_GENERATION_CHANGED,
    REASON_SEQUENCE_BOUNDARY,
    REASON_TEMPORAL_EVIDENCE_UNAVAILABLE,
    REASON_UNSTABLE_COMPARISON_INPUT,
    FrameIdentity,
    MotionProposalStrategyError,
    check_predecessor_eligibility,
    detect_changed_regions,
    finalize_proposal_window,
    generate_proposals,
)

CFG = FULL_FRAME_PLUS_MOTION_PROPOSALS
W, H = CFG.comparison_width, CFG.comparison_height


def _blank(value: float = 10.0) -> list[list[float]]:
    return [[value] * W for _ in range(H)]


def _square(plane: list[list[float]], *, x0: int, y0: int, x1: int, y1: int, value: float) -> list[list[float]]:
    out = [row[:] for row in plane]
    for y in range(y0, y1):
        for x in range(x0, x1):
            out[y][x] = value
    return out


def _id(frame_id: str, *, sequence_id: str | None = "seq", offset_ms: int | None = 0, **kwargs) -> FrameIdentity:
    return FrameIdentity(frame_id=frame_id, sequence_id=sequence_id, source_offset_ms=offset_ms, **kwargs)


# --------------------------------------------------------------------------
# 1. Deterministic frame differencing
# --------------------------------------------------------------------------


def test_deterministic_frame_differencing_is_reproducible() -> None:
    predecessor = _blank()
    current = _square(predecessor, x0=40, y0=30, x1=60, y1=50, value=200.0)

    first = detect_changed_regions(predecessor, current, config=CFG)
    second = detect_changed_regions(predecessor, current, config=CFG)

    assert first == second
    assert first.eligible is True
    assert len(first.regions) == 1


# --------------------------------------------------------------------------
# 2. Stable proposal ordering
# --------------------------------------------------------------------------


def test_proposal_ordering_is_stable_across_runs() -> None:
    predecessor = _blank()
    current = _square(predecessor, x0=5, y0=5, x1=15, y1=15, value=200.0)
    current = _square(current, x0=120, y0=90, x1=150, y1=110, value=200.0)

    current_identity, predecessor_identity = _id("cur"), _id("pred")
    first = generate_proposals(CFG, current=current_identity, predecessor=predecessor_identity, predecessor_plane=predecessor, current_plane=current)
    second = generate_proposals(CFG, current=current_identity, predecessor=predecessor_identity, predecessor_plane=predecessor, current_plane=current)

    assert [p.proposal_id for p in first.proposals] == [p.proposal_id for p in second.proposals]
    assert [p.window.source_box for p in first.proposals] == [p.window.source_box for p in second.proposals]
    # Larger changed region (the second, bigger square) ranks first.
    assert first.proposals[0].source_region.changed_pixel_count >= first.proposals[1].source_region.changed_pixel_count


# --------------------------------------------------------------------------
# 3. Proposal count bound
# --------------------------------------------------------------------------


def test_proposal_count_never_exceeds_configured_maximum() -> None:
    predecessor = _blank()
    current = predecessor
    # Five well-separated small squares -- more than max_proposals_per_frame (3).
    for column in range(5):
        x0 = 5 + column * 30
        current = _square(current, x0=x0, y0=5, x1=x0 + 10, y1=15, value=200.0)

    result = generate_proposals(CFG, current=_id("cur"), predecessor=_id("pred"), predecessor_plane=predecessor, current_plane=current)

    assert len(result.proposals) <= CFG.max_proposals_per_frame
    assert len(result.proposals) == CFG.max_proposals_per_frame
    assert len(result.rejected_proposals) == 5 - CFG.max_proposals_per_frame
    assert all(item.reason_code == "proposal_count_exceeds_maximum" for item in result.rejected_proposals)


def test_invalid_max_proposals_per_frame_is_rejected() -> None:
    with pytest.raises(MotionProposalStrategyError):
        replace(CFG, max_proposals_per_frame=0)


# --------------------------------------------------------------------------
# 4. Region merge behavior
# --------------------------------------------------------------------------


def test_adjacent_components_merge_into_one_region() -> None:
    predecessor = _blank()
    # Two small squares one pixel apart -- well within region_merge_gap_fraction.
    current = _square(predecessor, x0=40, y0=40, x1=50, y1=50, value=200.0)
    current = _square(current, x0=51, y0=40, x1=61, y1=50, value=200.0)

    result = detect_changed_regions(predecessor, current, config=CFG)

    assert len(result.regions) == 1


def test_distant_components_do_not_merge() -> None:
    predecessor = _blank()
    current = _square(predecessor, x0=5, y0=5, x1=15, y1=15, value=200.0)
    current = _square(current, x0=140, y0=100, x1=155, y1=115, value=200.0)

    result = detect_changed_regions(predecessor, current, config=CFG)

    assert len(result.regions) == 2


# --------------------------------------------------------------------------
# 5. Context padding and clipping
# --------------------------------------------------------------------------


def test_finalized_window_is_padded_larger_than_the_raw_region() -> None:
    raw_box = (0.4, 0.4, 0.5, 0.5)
    finalized = finalize_proposal_window(raw_box, config=CFG)

    raw_area = (raw_box[2] - raw_box[0]) * (raw_box[3] - raw_box[1])
    finalized_area = (finalized[2] - finalized[0]) * (finalized[3] - finalized[1])
    assert finalized_area > raw_area


def test_finalized_window_near_edge_clips_without_losing_size_when_possible() -> None:
    # A region hard against the left/top edge should still produce a
    # full-size, in-bounds window (shifted, not merely truncated).
    raw_box = (0.0, 0.0, 0.05, 0.05)
    finalized = finalize_proposal_window(raw_box, config=CFG)

    left, top, right, bottom = finalized
    assert 0.0 <= left < right <= 1.0
    assert 0.0 <= top < bottom <= 1.0
    # Width/height should approach the configured minimum window dimension,
    # not be squashed toward zero by naive per-coordinate clamping.
    assert (right - left) >= CFG.min_window_dimension_fraction - 1e-9
    assert (bottom - top) >= CFG.min_window_dimension_fraction - 1e-9


def test_finalized_window_never_exceeds_max_proposal_source_area() -> None:
    raw_box = (0.1, 0.1, 0.9, 0.9)  # a large raw region
    finalized = finalize_proposal_window(raw_box, config=CFG)

    left, top, right, bottom = finalized
    area = (right - left) * (bottom - top)
    assert area <= CFG.max_proposal_source_area_fraction + 1e-6


# --------------------------------------------------------------------------
# 6. Source-coordinate round trip
# --------------------------------------------------------------------------


def test_proposal_window_source_box_round_trips_through_map_window_box_to_source() -> None:
    from mockingbird.observation.multi_scale_strategy import map_window_box_to_source

    predecessor = _blank()
    current = _square(predecessor, x0=40, y0=30, x1=60, y1=50, value=200.0)
    result = generate_proposals(CFG, current=_id("cur"), predecessor=_id("pred"), predecessor_plane=predecessor, current_plane=current)
    assert result.proposals

    window = result.proposals[0].window
    # The window's own full local extent must map back exactly onto its own
    # already-recorded source box -- the definition of a coordinate round trip.
    mapped = map_window_box_to_source(window, (0.0, 0.0, 1.0, 1.0))
    assert mapped == window.source_box


# --------------------------------------------------------------------------
# 7. First frame produces no unsupported temporal claim
# --------------------------------------------------------------------------


def test_first_frame_reports_explicit_no_predecessor_not_a_silent_empty_result() -> None:
    result = generate_proposals(CFG, current=_id("cur"), predecessor=None, predecessor_plane=None, current_plane=None)

    assert result.pair_eligible is False
    assert result.pair_reason_code == REASON_FIRST_FRAME_NO_PREDECESSOR
    assert result.is_unsupported is True
    assert result.proposals == ()


def test_frame_with_no_sequence_id_reports_temporal_evidence_unavailable_not_first_frame() -> None:
    eligibility = check_predecessor_eligibility(CFG, current=_id("cur", sequence_id=None), predecessor=None)

    assert eligibility.reason_code == REASON_TEMPORAL_EVIDENCE_UNAVAILABLE


# --------------------------------------------------------------------------
# 8. Duplicate frames do not produce motion
# --------------------------------------------------------------------------


def test_identical_planes_report_eligible_with_zero_regions() -> None:
    plane = _blank()
    result = detect_changed_regions(plane, plane, config=CFG)

    assert result.eligible is True
    assert result.reason_code is None
    assert result.regions == ()
    assert result.changed_pixel_ratio == 0.0


def test_duplicate_frame_identity_by_id_is_rejected_before_differencing() -> None:
    eligibility = check_predecessor_eligibility(CFG, current=_id("same"), predecessor=_id("same"))
    assert eligibility.reason_code == REASON_DUPLICATE_FRAME_IDENTITY


def test_duplicate_frame_identity_by_content_hash_is_rejected() -> None:
    eligibility = check_predecessor_eligibility(
        CFG, current=_id("cur", content_hash="abc"), predecessor=_id("pred", content_hash="abc"),
    )
    assert eligibility.reason_code == REASON_DUPLICATE_FRAME_IDENTITY


# --------------------------------------------------------------------------
# 9. Excessive frame gap rejects comparison
# --------------------------------------------------------------------------


def test_excessive_source_time_gap_is_rejected() -> None:
    too_far = CFG.max_predecessor_gap_ms + 1
    eligibility = check_predecessor_eligibility(
        CFG, current=_id("cur", offset_ms=too_far), predecessor=_id("pred", offset_ms=0),
    )
    assert eligibility.reason_code == REASON_EXCESSIVE_SOURCE_TIME_GAP


def test_gap_at_exactly_the_bound_is_still_eligible() -> None:
    eligibility = check_predecessor_eligibility(
        CFG, current=_id("cur", offset_ms=CFG.max_predecessor_gap_ms), predecessor=_id("pred", offset_ms=0),
    )
    assert eligibility.eligible is True


def test_out_of_order_offsets_are_rejected_as_a_sequence_boundary() -> None:
    eligibility = check_predecessor_eligibility(
        CFG, current=_id("cur", offset_ms=0), predecessor=_id("pred", offset_ms=5_000),
    )
    assert eligibility.reason_code == REASON_SEQUENCE_BOUNDARY


# --------------------------------------------------------------------------
# 10. Global brightness change is rejected or degraded honestly
# --------------------------------------------------------------------------


def test_global_luminance_shift_is_rejected_with_zero_regions() -> None:
    predecessor = _blank(value=20.0)
    current = _blank(value=20.0 + CFG.global_luminance_shift_threshold + 5.0)

    result = detect_changed_regions(predecessor, current, config=CFG)

    assert result.eligible is False
    assert result.reason_code == REASON_GLOBAL_LUMINANCE_SHIFT
    assert result.regions == ()
    # The degrading facts are still honestly reported, not hidden.
    assert result.mean_absolute_delta is not None and result.mean_absolute_delta >= CFG.global_luminance_shift_threshold


def test_full_pipeline_reports_degraded_not_unsupported_for_luminance_shift() -> None:
    predecessor = _blank(value=20.0)
    current = _blank(value=20.0 + CFG.global_luminance_shift_threshold + 5.0)
    result = generate_proposals(CFG, current=_id("cur"), predecessor=_id("pred"), predecessor_plane=predecessor, current_plane=current)

    assert result.is_degraded is True
    assert result.is_unsupported is False


# --------------------------------------------------------------------------
# 11. Broad camera motion does not create unbounded proposals
# --------------------------------------------------------------------------


def test_excessive_changed_pixel_ratio_rejects_with_zero_windows() -> None:
    predecessor = _blank(value=10.0)
    # 80% of columns shift by just over pixel_delta_threshold (26 >= 25),
    # every row identically: changed_pixel_ratio = 0.8 (>= max_changed_pixel_
    # ratio 0.6) while mean_absolute_delta stays 0.8*26 = 20.8 (well under
    # global_luminance_shift_threshold 40) -- isolates the ratio guard from
    # the separate whole-frame luminance guard, simulating a broad scene
    # displacement/camera-shake pattern rather than a uniform brightness change.
    current = [[36.0 if (x % 10) < 8 else 10.0 for x in range(W)] for _ in range(H)]

    result = detect_changed_regions(predecessor, current, config=CFG)

    assert result.eligible is False
    assert result.reason_code == REASON_EXCESSIVE_CHANGED_PIXEL_RATIO
    assert result.regions == ()
    assert result.mean_absolute_delta < CFG.global_luminance_shift_threshold


def test_highly_fragmented_input_is_rejected_as_unstable_rather_than_hanging() -> None:
    predecessor = _blank(value=10.0)
    # One isolated changed pixel every 3rd column/row: far more raw
    # components than MAX_RAW_REGIONS_BEFORE_MERGE, none touching, and a
    # ratio too low to trip the whole-frame guard -- exercises the
    # component-count safety bound specifically.
    current = [row[:] for row in predecessor]
    produced = 0
    for y in range(0, H, 6):
        for x in range(0, W, 6):
            current[y][x] = 250.0
            produced += 1
    assert produced > MAX_RAW_REGIONS_BEFORE_MERGE

    result = detect_changed_regions(predecessor, current, config=CFG)

    assert result.eligible is False
    assert result.reason_code == REASON_UNSTABLE_COMPARISON_INPUT


# --------------------------------------------------------------------------
# 12. Small localized change creates one bounded proposal
# --------------------------------------------------------------------------


def test_small_localized_change_creates_exactly_one_proposal() -> None:
    predecessor = _blank()
    current = _square(predecessor, x0=60, y0=45, x1=75, y1=60, value=200.0)

    result = generate_proposals(CFG, current=_id("cur"), predecessor=_id("pred"), predecessor_plane=predecessor, current_plane=current)

    assert result.pair_eligible is True
    assert len(result.proposals) == 1
    box = result.proposals[0].window.source_box
    assert 0.0 <= box[0] < box[2] <= 1.0
    assert 0.0 <= box[1] < box[3] <= 1.0


# --------------------------------------------------------------------------
# 13. Two separate changes remain separate when appropriate
# --------------------------------------------------------------------------


def test_two_well_separated_changes_produce_two_proposals() -> None:
    predecessor = _blank()
    current = _square(predecessor, x0=5, y0=5, x1=15, y1=15, value=200.0)
    current = _square(current, x0=130, y0=95, x1=145, y1=110, value=200.0)

    result = generate_proposals(CFG, current=_id("cur"), predecessor=_id("pred"), predecessor_plane=predecessor, current_plane=current)

    assert len(result.proposals) == 2
    boxes = sorted(p.window.source_box for p in result.proposals)
    # The two windows should not overlap given how far apart the sources are.
    first, second = boxes
    assert first[2] <= second[0] or first[3] <= second[1] or second[2] <= first[0] or second[3] <= first[1]


# --------------------------------------------------------------------------
# 14. Privacy/Ignore regions are masked before differencing
# --------------------------------------------------------------------------


def test_change_entirely_inside_privacy_region_produces_no_proposal() -> None:
    predecessor = _blank()
    current = _square(predecessor, x0=10, y0=10, x1=20, y1=20, value=200.0)

    unmasked = detect_changed_regions(predecessor, current, config=CFG)
    assert len(unmasked.regions) == 1

    masked = detect_changed_regions(predecessor, current, config=CFG, excluded_regions=((0.0, 0.0, 0.2, 0.2),))
    assert masked.eligible is True
    assert masked.regions == ()
    assert masked.changed_pixel_ratio == 0.0


def test_fully_masked_comparison_plane_is_rejected() -> None:
    predecessor, current = _blank(), _blank(value=250.0)
    result = detect_changed_regions(predecessor, current, config=CFG, excluded_regions=((0.0, 0.0, 1.0, 1.0),))

    assert result.eligible is False
    assert result.reason_code == REASON_FULLY_PRIVACY_MASKED


def test_privacy_masked_pixels_are_excluded_from_changed_ratio_denominator() -> None:
    predecessor = _blank()
    # Change fills the whole frame except a masked strip; masking that strip
    # must not, by itself, change the ratio computed over the remaining area.
    current = _square(predecessor, x0=0, y0=0, x1=W, y1=H, value=200.0)
    result = detect_changed_regions(predecessor, current, config=CFG, excluded_regions=((0.0, 0.0, 0.1, 1.0),))

    assert result.changed_pixel_ratio == 1.0


# --------------------------------------------------------------------------
# 15. Proposal IDs are deterministic
# --------------------------------------------------------------------------


def test_proposal_ids_are_deterministic_and_rank_ordered() -> None:
    predecessor = _blank()
    current = _square(predecessor, x0=5, y0=5, x1=15, y1=15, value=200.0)
    current = _square(current, x0=100, y0=80, x1=115, y1=95, value=200.0)

    result = generate_proposals(CFG, current=_id("frame-42"), predecessor=_id("pred"), predecessor_plane=predecessor, current_plane=current)

    ids = [p.proposal_id for p in result.proposals]
    assert ids == [f"motion-proposal-frame-42-{index:02d}" for index in range(len(ids))]
    assert len(ids) == len(set(ids))


# --------------------------------------------------------------------------
# 30. Provider reset/generation changes clear temporal state
# --------------------------------------------------------------------------


def test_provider_generation_change_rejects_the_pair() -> None:
    eligibility = check_predecessor_eligibility(
        CFG,
        current=_id("cur", provider_generation="gen-2"),
        predecessor=_id("pred", provider_generation="gen-1"),
    )
    assert eligibility.reason_code == REASON_PROVIDER_GENERATION_CHANGED


def test_same_generation_on_both_sides_remains_eligible() -> None:
    eligibility = check_predecessor_eligibility(
        CFG,
        current=_id("cur", provider_generation="gen-1"),
        predecessor=_id("pred", provider_generation="gen-1"),
    )
    assert eligibility.eligible is True


def test_missing_generation_on_both_sides_is_not_treated_as_a_change() -> None:
    eligibility = check_predecessor_eligibility(CFG, current=_id("cur"), predecessor=_id("pred"))
    assert eligibility.eligible is True


# --------------------------------------------------------------------------
# 29. Buffers remain bounded (unstable/oversized input is refused, not grown)
# --------------------------------------------------------------------------


def test_mismatched_plane_dimensions_are_rejected_not_silently_resized() -> None:
    predecessor = _blank()
    too_wide = [row + [10.0] for row in predecessor]

    with pytest.raises(MotionProposalStrategyError):
        detect_changed_regions(predecessor, too_wide, config=CFG)


def test_non_finite_pixel_values_are_rejected() -> None:
    predecessor = _blank()
    current = [row[:] for row in predecessor]
    current[0][0] = float("nan")

    with pytest.raises(MotionProposalStrategyError):
        detect_changed_regions(predecessor, current, config=CFG)


def test_region_and_rejection_counts_stay_bounded_for_a_noisy_frame() -> None:
    predecessor = _blank()
    # Alternating rows at a delta just below threshold everywhere except one
    # small deliberate patch -- exercises a large but sub-threshold pattern
    # plus one genuine bounded region together.
    current = [[10.0 + (5.0 if y % 2 == 0 else 0.0) for _ in range(W)] for y in range(H)]
    current = _square(current, x0=40, y0=40, x1=55, y1=55, value=220.0)

    result = detect_changed_regions(predecessor, current, config=CFG)

    assert len(result.regions) <= MAX_RAW_REGIONS_BEFORE_MERGE
    assert len(result.regions) + len(result.rejected_regions) <= MAX_RAW_REGIONS_BEFORE_MERGE
