"""Classifier-input resolver for automatic species suggestion (Automatic
Species Suggestion v1.1 -- subject-centric classifier input).

Real live acceptance of the automatic BioCLIP assist (see
[[species-suggestion-real-live-acceptance-2026-08-13]] in project memory, and
`data/field-acceptance/`) found every real prediction classified the entire
3840x2160 backyard scene -- the actual bird occupies a few percent of the
frame -- which is the most likely cause of a strong, wrong, consistent bias
toward a bark/trunk-associated class (Red-bellied Woodpecker) across 7/8 real
encounters. This module answers one narrow question: what is the smallest,
safest image we can hand the classifier instead of the full frame?

**Critical safety rule (do not weaken this):** a subject box is eligible to
crop the exact image being classified only when that image's own geometry
lineage *proves* the box belongs to it -- `GeometryAttribution.same_frame is
True`, never merely "close enough" or "within a bounded gap." This is a
strictly stronger bar than
`mockingbird.observation.localization_attribution.classify_localization_attribution`,
which deliberately tolerates a several-second gap as "not misaligned" for its
own *diagnostic attribution* purpose (explaining why a box might be wrong)
-- reusing that looser tolerance here would silently reintroduce the exact
cross-frame coordinate guessing this module exists to forbid. See
`resolve_classifier_input`'s docstring for the concrete, real evidence this
distinction is based on (padding a stale box still lands off-subject often
enough -- empty background, or half the bird clipped out -- to be unsafe as
automatic, unreviewed classifier input).

This module is pure: no filesystem, network, PIL/imaging, or SQLAlchemy
import, matching the same convention `activity_crop.py` and
`localization_attribution.py` already follow. It decides *what* to classify
and *why*; a thin, separate caller-side step (not this module) actually
decodes and crops pixels, exactly the way `product_repository.py`'s existing
`_load_bioclip_input_image` already separates crop-box decision from pixel
work for today's `_ReviewSpeciesCropContext`.

Wired into the automatic species-assist path since Same-Frame Species
Evidence v1 (`product_repository._classifier_input_override`, see
docs/same-frame-species-evidence-contract.md) -- not the "always inert"
infrastructure this module's introduction described. Tier 2 below is
regularly reachable on real data once a Visit has a persisted
`classifier_same_frame` asset.

Source-Resolution + Multi-Frame Species Evidence v1 adds one more tier,
`native_resolution_subject_box` (`resolve_native_resolution_subject_crop`):
the live Observation Engine's separate, later high-resolution burst
(`geometry_attribution_for_burst`) is never `same_frame`, but can now carry
its own honest `GeometryAttribution.resolution_provenance` fact -- when a
Camera Node's real capture-profile metadata *proves* the burst image shares
the analysis frame's field of view (`resolution_provenance == "synchronized"`,
see `mockingbird.observation.localization_attribution`), its own subject box
is exactly as safe to crop against as an `exact_frame_subject_box` --
proximity in time is never enough on its own (still gated on the bounded
misalignment threshold), and a genuinely higher-resolution crop is the
entire point of this milestone. The same "proof, not a bounded gap
tolerance" rule below applies unchanged to *this* tier's `same_frame=False`
evidence: `resolution_provenance` must be the structurally stronger
`"synchronized"`, never merely `"near_time_capture"` (FOV alignment
unproven) -- see docs/source-resolution-multi-frame-species-evidence
-contract.md.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from mockingbird.motion.activity_crop import (
    DEFAULT_CROP_PADDING_RATIO,
    DEFAULT_MIN_CROP_SIZE_RATIO,
    CropBoxNormalized,
    CropBoxPixels,
    plan_activity_crop,
)
from mockingbird.observation.contracts import GeometryAttribution

CLASSIFIER_INPUT_RESOLVER_VERSION = "classifier-input-resolver-v1"

# The two `MediaAssetModel.evidence_role` values this codebase already uses
# to mean "a real derived pixel crop, not just a role label" -- see
# `product_repository.py` (`evidence_role in {"activity_crop",
# "user_refined_crop"}`, e.g. around candidate primary-crop promotion and
# reviewer refinement). Reused, not reinvented.
PERSISTED_CROP_EVIDENCE_ROLES = frozenset({"activity_crop", "user_refined_crop"})

ClassifierInputSource = Literal[
    "persisted_subject_crop",
    "native_resolution_subject_box",
    "exact_frame_subject_box",
    "full_frame",
]


@dataclass(frozen=True)
class ClassifierInputCropAsset:
    """Already-known facts about one persisted MediaAsset that might already
    be a useful, bird-centric crop for this Visit's evidence. Never
    re-derived from the DB/filesystem here; the caller supplies them."""

    media_asset_id: str
    evidence_role: str | None
    parent_media_asset_id: str | None
    image_width: int | None
    image_height: int | None


@dataclass(frozen=True)
class ClassifierInputSubjectFrame:
    """The full-FOV evidence frame that would otherwise be classified as-is
    (today's full-frame behavior) -- the facts needed to decide whether its
    own `normalized_track_box` is safe to crop against."""

    media_asset_id: str
    image_width: int
    image_height: int
    parent_media_asset_id: str | None
    normalized_track_box: tuple[float, float, float, float] | None
    geometry_attribution: GeometryAttribution | None

    def __post_init__(self) -> None:
        if self.image_width < 1 or self.image_height < 1:
            raise ValueError("invalid_classifier_input_subject_frame")
        if self.normalized_track_box is not None and len(self.normalized_track_box) != 4:
            raise ValueError("invalid_classifier_input_subject_frame")


@dataclass(frozen=True)
class ClassifierInputPlan:
    """What to hand the classifier, and why. Provenance-complete on its own
    -- a caller can persist this without recomputing anything, and it says
    honestly whether the full-frame fallback was used."""

    source: ClassifierInputSource
    media_asset_id: str
    used_full_frame_fallback: bool
    crop_method: str
    selection_reason: str
    original_width: int | None
    original_height: int | None
    input_width: int | None
    input_height: int | None
    crop_box_normalized: CropBoxNormalized | None = None
    crop_box_pixels: CropBoxPixels | None = None
    resolver_version: str = CLASSIFIER_INPUT_RESOLVER_VERSION


def resolve_classifier_input(
    *,
    subject_frame: ClassifierInputSubjectFrame,
    persisted_crop_candidates: tuple[ClassifierInputCropAsset, ...] = (),
    native_resolution_candidates: tuple[ClassifierInputSubjectFrame, ...] = (),
    padding_ratio: float = DEFAULT_CROP_PADDING_RATIO,
    min_crop_size_ratio: float = DEFAULT_MIN_CROP_SIZE_RATIO,
) -> ClassifierInputPlan:
    """Decide the smallest safe classifier input for one Visit's species
    inference.

    Decision order (most-preferred first; the first eligible tier wins):

    1. `persisted_subject_crop` -- an already-persisted, already-derived crop
       MediaAsset exists for this Visit's evidence (`evidence_role` of
       `activity_crop` or `user_refined_crop`, with sane non-degenerate
       dimensions and real derivation -- `parent_media_asset_id` set; a role
       label alone is never trusted, matching "no using a box merely because
       it exists" in the product's safety rule). Used as-is, never
       re-cropped -- generating a second derivative of an already-good crop
       would just add another lossy step. Preferred over resolution: reusing
       an asset a human or an earlier deliberate step already curated
       outranks an automated resolution optimization.
    2. `native_resolution_subject_box` (Source-Resolution + Multi-Frame
       Species Evidence v1) -- the first of `native_resolution_candidates`
       (already caller-ordered, best-first) whose own subject box is safe to
       crop against: not itself a derived crop, has a `normalized_track_box`,
       and `geometry_attribution.resolution_provenance == "synchronized"` --
       see `resolve_native_resolution_subject_crop`. Ranked above tier 3
       precisely because it is genuinely higher-resolution evidence with an
       equally strong (FOV-proof-backed, not merely proximate) correspondence
       guarantee -- the product requirement this milestone exists to satisfy.
    3. `exact_frame_subject_box` -- the *primary* `subject_frame` is not
       itself a derived crop (`parent_media_asset_id is None`, so a
       full-FOV-relative box is meaningful on its own pixels -- the same
       precondition `_frame_local_subject_box` already applies elsewhere), it
       has a `normalized_track_box`, and that box's own lineage *proves* it
       belongs to this exact image (`geometry_attribution.same_frame is
       True`) -- never a bounded-gap approximation. Expanded with the
       existing, already-reviewed `plan_activity_crop` padding/min-size
       convention and clamped to image bounds.
    4. `full_frame` -- the honest fallback, always available.

    Real diagnostic evidence for why tier 3 requires *proof*, not a bounded
    gap tolerance (2026-08-14, real archived/fresh field evidence, 8 real
    bird encounters, out-of-band manual comparison -- never wired into
    production, see project memory): padding a same_frame=False box (the
    only kind real evidence currently ever has, typically 3.5-9s stale) with
    this exact padding convention put the real bird inside the crop in only
    4/8 cases; the other 4/8 produced an empty-background or near-empty
    crop indistinguishable, by geometry metadata alone, from a good one.
    Proof, not proximity, is what keeps this resolver from doing that
    silently -- tier 2 above applies the identical discipline to
    higher-resolution evidence (a proven `resolution_provenance ==
    "synchronized"`, never a bare "captured soon after").
    """
    persisted_crop = _first_usable_persisted_crop(persisted_crop_candidates)
    if persisted_crop is not None:
        return ClassifierInputPlan(
            source="persisted_subject_crop",
            media_asset_id=persisted_crop.media_asset_id,
            used_full_frame_fallback=False,
            crop_method="reused_existing_persisted_crop",
            selection_reason=(
                f"Reused existing persisted {persisted_crop.evidence_role} "
                "media asset already derived from this Visit's evidence; "
                "not re-cropped."
            ),
            original_width=persisted_crop.image_width,
            original_height=persisted_crop.image_height,
            input_width=persisted_crop.image_width,
            input_height=persisted_crop.image_height,
        )

    for candidate in native_resolution_candidates:
        native_plan = resolve_native_resolution_subject_crop(
            candidate, padding_ratio=padding_ratio, min_crop_size_ratio=min_crop_size_ratio,
        )
        if native_plan is not None:
            return native_plan

    eligible, reason = _exact_frame_box_eligibility(subject_frame)
    if eligible:
        box = subject_frame.normalized_track_box
        assert box is not None
        plan = plan_activity_crop(
            source_media_asset_id=subject_frame.media_asset_id,
            image_width=subject_frame.image_width,
            image_height=subject_frame.image_height,
            left=box[0],
            top=box[1],
            right=box[2],
            bottom=box[3],
            crop_reason="activity_motion",
            padding_ratio=padding_ratio,
            min_crop_size_ratio=min_crop_size_ratio,
        )
        if not plan.is_full_frame_fallback:
            return ClassifierInputPlan(
                source="exact_frame_subject_box",
                media_asset_id=subject_frame.media_asset_id,
                used_full_frame_fallback=False,
                crop_method="exact_frame_subject_box_padded",
                selection_reason=(
                    "Subject box proven same_frame=True for this exact "
                    "media asset; expanded with generous context and "
                    "clamped to image bounds."
                ),
                original_width=subject_frame.image_width,
                original_height=subject_frame.image_height,
                input_width=plan.crop_box_pixels.width,
                input_height=plan.crop_box_pixels.height,
                crop_box_normalized=plan.crop_box_normalized,
                crop_box_pixels=plan.crop_box_pixels,
            )
        reason = plan.warning or "geometry_collapsed_after_padding"

    return ClassifierInputPlan(
        source="full_frame",
        media_asset_id=subject_frame.media_asset_id,
        used_full_frame_fallback=True,
        crop_method="full_frame_fallback",
        selection_reason=reason,
        original_width=subject_frame.image_width,
        original_height=subject_frame.image_height,
        input_width=subject_frame.image_width,
        input_height=subject_frame.image_height,
    )


def apply_classifier_input_plan(image: Any, plan: ClassifierInputPlan) -> Any:
    """Apply `plan` to an already-decoded image -- a PIL `Image.Image`, or
    anything duck-type-compatible with its `.crop((left, top, right,
    bottom))` -- and return the (possibly cropped) image. Deliberately does
    not import an imaging library, matching `bioclip_adapter._copy_rgb_image`
    already accepting a generic `Any` decoded image.

    Returns `image` unchanged for a `full_frame` plan, and for a
    `persisted_subject_crop` plan (the caller already opened *that* asset's
    own file directly -- this never re-crops an already-derived crop). Crops
    for `exact_frame_subject_box` and `native_resolution_subject_box`. Never
    decodes, opens, or closes a file; that stays the caller's job, exactly
    like `bioclip_adapter.run_bioclip_on_image` already expects an in-memory
    image, not a path.
    """
    if plan.crop_box_pixels is None:
        return image
    box = plan.crop_box_pixels
    return image.crop((box.left, box.top, box.right, box.bottom))


def resolve_native_resolution_subject_crop(
    subject_frame: ClassifierInputSubjectFrame,
    *,
    padding_ratio: float = DEFAULT_CROP_PADDING_RATIO,
    min_crop_size_ratio: float = DEFAULT_MIN_CROP_SIZE_RATIO,
) -> ClassifierInputPlan | None:
    """Build a `native_resolution_subject_box` plan for one candidate
    higher-resolution evidence frame (typically a persisted
    `high_resolution_burst` MediaAsset), or `None` when it is not safe to
    crop against -- never a fallback plan itself; the caller (`resolve_
    classifier_input`, or the multi-frame candidate builder in
    `product_repository.py`) decides what to do with `None`.

    Eligible only when `subject_frame` is not itself a derived crop
    (`parent_media_asset_id is None`), has a `normalized_track_box`, and its
    lineage *proves* a genuinely aligned correspondence --
    `geometry_attribution.resolution_provenance == "synchronized"` (real,
    FOV-proven-aligned, bounded-gap capture -- see
    `mockingbird.observation.localization_attribution.
    resolution_provenance_for_burst`). Deliberately stricter than
    `"near_time_capture"` (a real capture within the bounded gap, but with no
    proven field-of-view match): the same "proof, not proximity" rule
    `_exact_frame_box_eligibility` already enforces for `same_frame`, applied
    identically here so a genuinely higher-resolution image never gets a
    weaker safety bar than a same-resolution one.
    """
    eligible, _ = _native_resolution_box_eligibility(subject_frame)
    if not eligible:
        return None
    box = subject_frame.normalized_track_box
    assert box is not None
    plan = plan_activity_crop(
        source_media_asset_id=subject_frame.media_asset_id,
        image_width=subject_frame.image_width,
        image_height=subject_frame.image_height,
        left=box[0],
        top=box[1],
        right=box[2],
        bottom=box[3],
        crop_reason="activity_motion",
        padding_ratio=padding_ratio,
        min_crop_size_ratio=min_crop_size_ratio,
    )
    if plan.is_full_frame_fallback:
        # A degenerate box after padding is exactly as unsafe here as it is
        # for `exact_frame_subject_box` -- never silently promote it to a
        # full-frame *native-resolution* plan; the caller's own full_frame
        # fallback (on whatever asset it considers primary) already covers
        # that honestly.
        return None
    return ClassifierInputPlan(
        source="native_resolution_subject_box",
        media_asset_id=subject_frame.media_asset_id,
        used_full_frame_fallback=False,
        crop_method="native_resolution_subject_box_padded",
        selection_reason=(
            "Subject box proven resolution_provenance=synchronized "
            "(FOV-aligned, bounded-gap higher-resolution capture); "
            "expanded with generous context and clamped to image bounds."
        ),
        original_width=subject_frame.image_width,
        original_height=subject_frame.image_height,
        input_width=plan.crop_box_pixels.width,
        input_height=plan.crop_box_pixels.height,
        crop_box_normalized=plan.crop_box_normalized,
        crop_box_pixels=plan.crop_box_pixels,
    )


def _first_usable_persisted_crop(
    candidates: tuple[ClassifierInputCropAsset, ...],
) -> ClassifierInputCropAsset | None:
    for candidate in candidates:
        if _is_usable_persisted_crop(candidate):
            return candidate
    return None


def _is_usable_persisted_crop(asset: ClassifierInputCropAsset) -> bool:
    if asset.evidence_role not in PERSISTED_CROP_EVIDENCE_ROLES:
        return False
    if asset.parent_media_asset_id is None:
        # A "crop" role with nothing it was derived from is not actually a
        # derived crop -- never trust the role name alone.
        return False
    if (
        asset.image_width is None
        or asset.image_height is None
        or asset.image_width < 1
        or asset.image_height < 1
    ):
        return False
    return True


def _exact_frame_box_eligibility(
    subject_frame: ClassifierInputSubjectFrame,
) -> tuple[bool, str]:
    if subject_frame.parent_media_asset_id is not None:
        return False, "subject_frame_is_itself_a_derived_crop"
    if subject_frame.normalized_track_box is None:
        return False, "no_subject_box_recorded_for_this_media_asset"
    attribution = subject_frame.geometry_attribution
    if attribution is None:
        return False, "no_geometry_attribution_lineage_for_this_media_asset"
    if attribution.same_frame is not True:
        return False, "geometry_not_proven_same_frame_as_classified_image"
    return True, "exact_frame_subject_box_eligible"


def _native_resolution_box_eligibility(
    subject_frame: ClassifierInputSubjectFrame,
) -> tuple[bool, str]:
    if subject_frame.parent_media_asset_id is not None:
        return False, "subject_frame_is_itself_a_derived_crop"
    if subject_frame.normalized_track_box is None:
        return False, "no_subject_box_recorded_for_this_media_asset"
    attribution = subject_frame.geometry_attribution
    if attribution is None:
        return False, "no_geometry_attribution_lineage_for_this_media_asset"
    if attribution.resolution_provenance != "synchronized":
        return False, "resolution_provenance_not_proven_synchronized"
    return True, "native_resolution_subject_box_eligible"


__all__ = [
    "CLASSIFIER_INPUT_RESOLVER_VERSION",
    "PERSISTED_CROP_EVIDENCE_ROLES",
    "ClassifierInputCropAsset",
    "ClassifierInputPlan",
    "ClassifierInputSource",
    "ClassifierInputSubjectFrame",
    "apply_classifier_input_plan",
    "resolve_classifier_input",
    "resolve_native_resolution_subject_crop",
]
