"""Classifier-input resolver for automatic species suggestion (Automatic
Species Suggestion v1.1). Direct, deterministic, hardware-free tests for the
pure `mockingbird.species.classifier_input` decision module -- no DB, no
filesystem, no PIL/BioCLIP.

Some scenarios deliberately reproduce the *numeric shape* of real archived
evidence (visit-observation-candidate-011..018, 2026-08-14 subject-centric-
crop field evidence: every real MediaAsset's own geometry lineage has
`same_frame=False`, typically a 3.5-9s gap, because the live Observation
Engine's high-resolution evidence burst is, by construction, always a
separate later capture -- see `classifier_input.py`'s module docstring and
project memory) without hard-coding an exact historical value as an
assertion target.
"""

from __future__ import annotations

import pytest

from mockingbird.motion.activity_crop import (
    DEFAULT_CROP_PADDING_RATIO,
    plan_activity_crop,
)
from mockingbird.observation.contracts import GeometryAttribution
from mockingbird.species.classifier_input import (
    ClassifierInputCropAsset,
    ClassifierInputPlan,
    ClassifierInputSubjectFrame,
    apply_classifier_input_plan,
    resolve_classifier_input,
)


def _attribution(
    *,
    same_frame: bool | None,
    gap_ms: int | None = None,
    source: str | None = "detector",
) -> GeometryAttribution:
    return GeometryAttribution(
        geometry_source=source,
        geometry_source_offset_ms=1_173_165,
        geometry_source_observation_id="obs-1",
        geometry_source_confidence=0.79,
        same_frame=same_frame,
        geometry_evidence_gap_ms=gap_ms,
    )


def _subject_frame(
    *,
    parent_media_asset_id: str | None = None,
    normalized_track_box: tuple[float, float, float, float] | None = (0.46, 0.59, 0.51, 0.63),
    geometry_attribution: GeometryAttribution | None = None,
    image_width: int = 3840,
    image_height: int = 2160,
) -> ClassifierInputSubjectFrame:
    return ClassifierInputSubjectFrame(
        media_asset_id="media-candidate-999",
        image_width=image_width,
        image_height=image_height,
        parent_media_asset_id=parent_media_asset_id,
        normalized_track_box=normalized_track_box,
        geometry_attribution=geometry_attribution,
    )


def _crop_asset(
    *,
    evidence_role: str | None = "activity_crop",
    parent_media_asset_id: str | None = "media-candidate-999",
    image_width: int | None = 800,
    image_height: int | None = 600,
    media_asset_id: str = "media-candidate-crop-1",
) -> ClassifierInputCropAsset:
    return ClassifierInputCropAsset(
        media_asset_id=media_asset_id,
        evidence_role=evidence_role,
        parent_media_asset_id=parent_media_asset_id,
        image_width=image_width,
        image_height=image_height,
    )


# ---------------------------------------------------------------------------
# Tier 1: existing persisted subject crop selection
# ---------------------------------------------------------------------------


def test_usable_persisted_crop_is_preferred_over_everything_else() -> None:
    plan = resolve_classifier_input(
        subject_frame=_subject_frame(geometry_attribution=_attribution(same_frame=True, gap_ms=0)),
        persisted_crop_candidates=(_crop_asset(),),
    )
    assert plan.source == "persisted_subject_crop"
    assert plan.media_asset_id == "media-candidate-crop-1"
    assert plan.used_full_frame_fallback is False
    assert plan.crop_method == "reused_existing_persisted_crop"
    assert plan.crop_box_normalized is None
    assert plan.crop_box_pixels is None
    assert plan.input_width == 800
    assert plan.input_height == 600
    assert plan.original_width == 800
    assert plan.original_height == 600


@pytest.mark.parametrize("evidence_role", ["activity_crop", "user_refined_crop"])
def test_both_recognized_persisted_crop_roles_are_usable(evidence_role: str) -> None:
    plan = resolve_classifier_input(
        subject_frame=_subject_frame(),
        persisted_crop_candidates=(_crop_asset(evidence_role=evidence_role),),
    )
    assert plan.source == "persisted_subject_crop"


def test_persisted_crop_picks_first_usable_candidate_in_order() -> None:
    unusable = _crop_asset(evidence_role="context", media_asset_id="media-context")
    usable_first = _crop_asset(media_asset_id="media-crop-a")
    usable_second = _crop_asset(media_asset_id="media-crop-b")
    plan = resolve_classifier_input(
        subject_frame=_subject_frame(),
        persisted_crop_candidates=(unusable, usable_first, usable_second),
    )
    assert plan.media_asset_id == "media-crop-a"


def test_persisted_crop_role_alone_is_not_trusted_without_a_parent_asset() -> None:
    """A role label of activity_crop/user_refined_crop with no
    parent_media_asset_id is not actually a derived crop -- "no using a box
    merely because it exists" applies to role names too."""
    not_really_a_crop = _crop_asset(parent_media_asset_id=None)
    plan = resolve_classifier_input(
        subject_frame=_subject_frame(geometry_attribution=None),
        persisted_crop_candidates=(not_really_a_crop,),
    )
    assert plan.source == "full_frame"


@pytest.mark.parametrize(
    ("image_width", "image_height"),
    [(None, 600), (800, None), (0, 600), (800, 0), (-1, 600)],
)
def test_persisted_crop_with_degenerate_dimensions_is_rejected(
    image_width: int | None, image_height: int | None
) -> None:
    degenerate = _crop_asset(image_width=image_width, image_height=image_height)
    plan = resolve_classifier_input(
        subject_frame=_subject_frame(geometry_attribution=None),
        persisted_crop_candidates=(degenerate,),
    )
    assert plan.source == "full_frame"


def test_no_persisted_crop_candidates_falls_through_to_next_tier() -> None:
    plan = resolve_classifier_input(
        subject_frame=_subject_frame(geometry_attribution=_attribution(same_frame=True, gap_ms=0)),
        persisted_crop_candidates=(),
    )
    assert plan.source == "exact_frame_subject_box"


# ---------------------------------------------------------------------------
# Tier 2: exact-frame geometry eligibility / rejection of cross-frame geometry
# ---------------------------------------------------------------------------


def test_same_frame_true_box_is_eligible_and_padded_like_the_existing_convention() -> None:
    box = (0.46, 0.59, 0.51, 0.63)
    plan = resolve_classifier_input(
        subject_frame=_subject_frame(
            normalized_track_box=box,
            geometry_attribution=_attribution(same_frame=True, gap_ms=0),
        ),
    )
    assert plan.source == "exact_frame_subject_box"
    assert plan.used_full_frame_fallback is False
    assert plan.crop_method == "exact_frame_subject_box_padded"

    expected = plan_activity_crop(
        source_media_asset_id="media-candidate-999",
        image_width=3840,
        image_height=2160,
        left=box[0],
        top=box[1],
        right=box[2],
        bottom=box[3],
        crop_reason="activity_motion",
    )
    assert plan.crop_box_normalized == expected.crop_box_normalized
    assert plan.crop_box_pixels == expected.crop_box_pixels
    assert plan.input_width == expected.crop_box_pixels.width
    assert plan.input_height == expected.crop_box_pixels.height
    # Real project padding convention (~2x via 0.5 padding_ratio / 15% min
    # size), not a bespoke crop-parameter optimization.
    assert expected.padding_ratio == DEFAULT_CROP_PADDING_RATIO


@pytest.mark.parametrize("same_frame", [False, None])
def test_non_proven_same_frame_is_rejected_regardless_of_gap(same_frame: bool | None) -> None:
    """No cross-frame coordinate guessing: even a tiny/zero/unknown gap is
    not eligible unless same_frame is proven True."""
    plan = resolve_classifier_input(
        subject_frame=_subject_frame(
            geometry_attribution=_attribution(same_frame=same_frame, gap_ms=0),
        ),
    )
    assert plan.source == "full_frame"
    assert plan.selection_reason == "geometry_not_proven_same_frame_as_classified_image"


def test_real_archived_visit_geometry_shape_falls_back_to_full_frame() -> None:
    """Reproduces the numeric shape (not the exact private values) of real
    archived/fresh field evidence for visit-observation-candidate-011..018:
    a genuine, temporally-plausible detector box (`source="detector"`,
    confidence 0.79) that is nonetheless *not* the same captured frame, with
    a multi-second gap well inside what
    `classify_localization_attribution`'s own *diagnostic* tolerance (5s)
    would call "not misaligned." This resolver's bar is strictly stronger:
    the real evidence is not eligible for automatic cropping."""
    plan = resolve_classifier_input(
        subject_frame=_subject_frame(
            normalized_track_box=(0.2812, 0.5861, 0.3353, 0.6367),
            geometry_attribution=_attribution(same_frame=False, gap_ms=4_149),
        ),
    )
    assert plan.source == "full_frame"
    assert plan.used_full_frame_fallback is True


def test_derived_subject_frame_is_never_treated_as_full_fov_even_with_proven_geometry() -> None:
    """A frame with its own parent_media_asset_id is not full-FOV-relative
    (mirrors `_frame_local_subject_box`'s existing precondition); a box
    normalized against the *original* full frame would land on the wrong
    pixels of an already-cropped derivative."""
    plan = resolve_classifier_input(
        subject_frame=_subject_frame(
            parent_media_asset_id="media-candidate-parent",
            geometry_attribution=_attribution(same_frame=True, gap_ms=0),
        ),
    )
    assert plan.source == "full_frame"
    assert plan.selection_reason == "subject_frame_is_itself_a_derived_crop"


def test_missing_box_falls_back_to_full_frame() -> None:
    plan = resolve_classifier_input(
        subject_frame=_subject_frame(
            normalized_track_box=None,
            geometry_attribution=_attribution(same_frame=True, gap_ms=0),
        ),
    )
    assert plan.source == "full_frame"
    assert plan.selection_reason == "no_subject_box_recorded_for_this_media_asset"


def test_missing_geometry_attribution_falls_back_to_full_frame() -> None:
    plan = resolve_classifier_input(subject_frame=_subject_frame(geometry_attribution=None))
    assert plan.source == "full_frame"
    assert plan.selection_reason == "no_geometry_attribution_lineage_for_this_media_asset"


def test_tiny_same_frame_box_that_collapses_after_padding_falls_back_honestly() -> None:
    plan = resolve_classifier_input(
        subject_frame=_subject_frame(
            normalized_track_box=(0.5, 0.5, 0.5, 0.5),  # degenerate: zero area
            geometry_attribution=_attribution(same_frame=True, gap_ms=0),
        ),
    )
    assert plan.source == "full_frame"


# ---------------------------------------------------------------------------
# Context expansion / clamping
# ---------------------------------------------------------------------------


def test_context_expansion_is_generous_relative_to_the_raw_box() -> None:
    box = (0.46, 0.59, 0.51, 0.63)  # ~2-5% of frame width/height, like real evidence
    plan = resolve_classifier_input(
        subject_frame=_subject_frame(
            normalized_track_box=box,
            geometry_attribution=_attribution(same_frame=True, gap_ms=0),
        ),
    )
    assert plan.crop_box_pixels is not None
    raw_width_px = (box[2] - box[0]) * 3840
    raw_height_px = (box[3] - box[1]) * 2160
    assert plan.crop_box_pixels.width >= 2 * raw_width_px
    assert plan.crop_box_pixels.height >= 2 * raw_height_px
    assert plan.crop_box_pixels.width <= 4 * raw_width_px + 1
    assert plan.crop_box_pixels.height <= 4 * raw_height_px + 1


def test_box_near_image_edge_is_clamped_within_bounds() -> None:
    plan = resolve_classifier_input(
        subject_frame=_subject_frame(
            normalized_track_box=(0.0, 0.0, 0.02, 0.02),
            geometry_attribution=_attribution(same_frame=True, gap_ms=0),
            image_width=3840,
            image_height=2160,
        ),
    )
    assert plan.crop_box_pixels is not None
    box = plan.crop_box_pixels
    assert 0 <= box.left < box.right <= 3840
    assert 0 <= box.top < box.bottom <= 2160


def test_custom_padding_ratio_is_honored() -> None:
    box = (0.4, 0.4, 0.6, 0.6)
    frame = _subject_frame(
        normalized_track_box=box,
        geometry_attribution=_attribution(same_frame=True, gap_ms=0),
    )
    tight = resolve_classifier_input(subject_frame=frame, padding_ratio=0.0, min_crop_size_ratio=0.0)
    generous = resolve_classifier_input(subject_frame=frame, padding_ratio=1.5, min_crop_size_ratio=0.0)
    assert tight.crop_box_pixels is not None
    assert generous.crop_box_pixels is not None
    assert generous.crop_box_pixels.width > tight.crop_box_pixels.width
    assert generous.crop_box_pixels.height > tight.crop_box_pixels.height


# ---------------------------------------------------------------------------
# Full-frame fallback / provenance completeness
# ---------------------------------------------------------------------------


def test_full_frame_fallback_provenance_is_complete_and_honest() -> None:
    plan = resolve_classifier_input(subject_frame=_subject_frame(geometry_attribution=None))
    assert plan.source == "full_frame"
    assert plan.used_full_frame_fallback is True
    assert plan.crop_box_normalized is None
    assert plan.crop_box_pixels is None
    assert plan.original_width == plan.input_width == 3840
    assert plan.original_height == plan.input_height == 2160
    assert plan.media_asset_id == "media-candidate-999"
    assert plan.selection_reason  # never empty -- always says *why*
    assert plan.resolver_version


def test_default_call_with_no_geometry_at_all_is_full_frame() -> None:
    plan = resolve_classifier_input(
        subject_frame=_subject_frame(normalized_track_box=None, geometry_attribution=None)
    )
    assert plan.source == "full_frame"


def test_subject_frame_rejects_invalid_dimensions() -> None:
    with pytest.raises(ValueError):
        _subject_frame(image_width=0)
    with pytest.raises(ValueError):
        _subject_frame(image_height=-1)


def test_subject_frame_rejects_malformed_box() -> None:
    with pytest.raises(ValueError):
        ClassifierInputSubjectFrame(
            media_asset_id="m1",
            image_width=100,
            image_height=100,
            parent_media_asset_id=None,
            normalized_track_box=(0.1, 0.2, 0.3),  # type: ignore[arg-type]
            geometry_attribution=None,
        )


# ---------------------------------------------------------------------------
# apply_classifier_input_plan
# ---------------------------------------------------------------------------


class _FakeImage:
    def __init__(self, label: str) -> None:
        self.label = label
        self.cropped_with: tuple[int, int, int, int] | None = None

    def crop(self, box: tuple[int, int, int, int]) -> "_FakeImage":
        result = _FakeImage(f"{self.label}-cropped")
        result.cropped_with = box
        return result


def test_apply_full_frame_plan_returns_image_unchanged() -> None:
    plan = resolve_classifier_input(subject_frame=_subject_frame(geometry_attribution=None))
    image = _FakeImage("orig")
    result = apply_classifier_input_plan(image, plan)
    assert result is image


def test_apply_persisted_crop_plan_returns_image_unchanged() -> None:
    plan = resolve_classifier_input(
        subject_frame=_subject_frame(),
        persisted_crop_candidates=(_crop_asset(),),
    )
    image = _FakeImage("already-cropped-asset")
    result = apply_classifier_input_plan(image, plan)
    assert result is image


def test_apply_exact_frame_plan_crops_with_the_resolved_pixel_box() -> None:
    plan = resolve_classifier_input(
        subject_frame=_subject_frame(geometry_attribution=_attribution(same_frame=True, gap_ms=0)),
    )
    assert plan.crop_box_pixels is not None
    image = _FakeImage("full-frame")
    result = apply_classifier_input_plan(image, plan)
    assert isinstance(result, _FakeImage)
    assert result is not image
    box = plan.crop_box_pixels
    assert result.cropped_with == (box.left, box.top, box.right, box.bottom)


def test_plan_is_frozen_and_hashable_shape_stable_for_provenance_persistence() -> None:
    plan = resolve_classifier_input(subject_frame=_subject_frame(geometry_attribution=None))
    assert isinstance(plan, ClassifierInputPlan)
    with pytest.raises(Exception):
        plan.source = "full_frame"  # type: ignore[misc]
