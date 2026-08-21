"""Canonical identification eligibility + classification abstention decision
boundary (Identification Eligibility + Abstention v1).

Species assistance must be useful and honest, not compulsory (see
docs/roadmap.md "Gate B -- Useful Species Assistance" and
docs/identification-eligibility-abstention-v1-report.md). Before this
module, BioCLIP inference ran unconditionally on every admitted Visit with a
usable media asset, and its closed-set, forced-choice 14-label output always
produced a rank-1 label -- there was no eligibility gate before inference and
no abstention path after it (confirmed directly: `docs/person-background-
false-positive-attribution-v1-report.md` S9, "BioCLIP 2 ran unconditionally
(no eligibility/gating call precedes it)"; `docs/architecture.md`'s
"Detection Quality Accounting" stage 12, "abstention -- not yet implemented
anywhere in the pipeline").

This module answers two deliberately separate questions (do not conflate
them -- see the report's "Two different questions" section):

1. **Evidence eligibility** (`evaluate_identification_eligibility`) -- is the
   selected classifier input good enough to even attempt identification?
   Runs *before* any model call, using only already-computed crop/lineage
   facts (`species/classifier_input.py`, `product_repository.
   _review_species_crop_context`). A structural floor only: real field data
   (n=70 real Visits plus the mandatory Visit 139/140 hard negatives, see the
   report) proved subject bbox coverage does *not* separate real animals from
   background/false-positive evidence (nearly identical distributions), so
   this deliberately does not gate on a tuned "small bird" cutoff -- only on
   a crop so small that BioCLIP's 224x224 resize would be mostly synthesized
   interpolation, not real signal.

2. **Classification abstention** (`evaluate_classification_abstention`) --
   even given a real model call, is the *result* strong and specific enough
   to present as a species suggestion? BioCLIP's score is a closed-set
   relative softmax over only the configured candidate labels
   (`bioclip_adapter.BIOCLIP_SCORE_KIND = "candidate_relative_softmax"`), not
   a calibrated open-world probability -- it always sums to 1 across those
   labels regardless of whether any of them actually matches the input. Real
   field data proved this concretely: background/false-positive Visits in
   the same real n=70 cohort scored as high as 99.5%, and one real full-frame
   misidentification (Visit 011, `docs/identification-eligibility-
   abstention-v1-report.md` "difficult-case" data) scored 79.6% with a 0.73
   margin over rank 2 while still being wrong. A single blanket threshold
   cannot separate these; this module instead requires a real subject-focused
   crop tier to clear a much lower bar than a last-resort full-frame
   classification, on top of a score+margin floor -- both grounded in real
   measured separation between the mandatory hard negatives (Visits 139/140,
   scores 0.5275/0.5986) and every known real positive control (minimum real
   score 0.784 at the subject-focused tier; the full-frame tier's own real
   difficult-case cluster tops out at 0.817).

Pure module: no filesystem, network, PIL/imaging, or SQLAlchemy import,
matching `species/classifier_input.py`'s established convention. It decides
*whether* to identify and *whether* to trust the result; a caller
(`product_repository.py`) adapts real ORM/runtime types into the small
structural types here and turns a `reason_code` into the product's existing
error/status vocabulary -- this module never raises, never touches storage,
and never knows about `SpeciesSuggestionModel`, `ValueError` reason strings,
or `ReviewIdentificationStatus`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

# One version stamp for the whole policy (both decisions below) -- persisted
# alongside a suggestion's own provenance and a withheld attempt's crop
# context so a future policy change is reproducible/comparable, never silent.
IDENTIFICATION_ELIGIBILITY_POLICY_VERSION = "identification-eligibility-v1"

# --- Evidence eligibility ---------------------------------------------------

# A structural floor, not a tuned "small bird" cutoff: BioCLIP resizes its
# input to 224x224 internally (`bioclip_adapter._infer_scores`), so a crop
# smaller than this on either side is mostly synthesized upsampling detail,
# not real visual signal, regardless of species. Deliberately far below the
# real range measured across 70 real reviewed Visits (bbox coverage implied
# a typical subject crop of roughly 100-300px on a side on a 3840x2160
# frame; see docs/identification-eligibility-abstention-v1-report.md) --
# this floor exists for genuinely degenerate input, not ordinary small/far
# birds, which real data proved indistinguishable from real/false outcomes
# by size alone and are therefore a classification-abstention concern (via
# the resulting low/ambiguous score), not an evidence-eligibility one.
MINIMUM_CLASSIFIER_INPUT_DIMENSION_PX = 32

EligibilityReasonCode = Literal["evidence_below_resolution_floor"]


@dataclass(frozen=True)
class EligibilityDecision:
    """Whether identification should even be attempted."""

    eligible: bool
    reason_code: EligibilityReasonCode | None
    classifier_input_width: int | None
    classifier_input_height: int | None
    policy_version: str = IDENTIFICATION_ELIGIBILITY_POLICY_VERSION

    def __post_init__(self) -> None:
        if self.eligible and self.reason_code is not None:
            raise ValueError("eligible decision must not carry a reason_code")
        if not self.eligible and self.reason_code is None:
            raise ValueError("ineligible decision must carry a reason_code")


def evaluate_identification_eligibility(
    *,
    classifier_input_width: int | None,
    classifier_input_height: int | None,
) -> EligibilityDecision:
    """Is the selected classifier input worth running a model on at all?

    `classifier_input_width`/`classifier_input_height` are the pixel
    dimensions of whatever image region would actually be handed to
    BioCLIP -- the same-frame/persisted crop's own dimensions, or the
    padded MegaDetector/activity crop, or the full source frame for a
    full-frame fallback (see `product_repository._review_species_crop_
    context`).

    `None` (dimensions unknown -- the MediaAsset row's own `image_width`/
    `image_height` were never recorded) deliberately does *not* fail this
    check: an unknown size is a data-completeness gap, not positive
    evidence the crop is too small, and a separate, more authoritative
    mechanism already exists to reject genuinely undecodable media
    (`_load_bioclip_input_image` raises its own typed error when the real
    bytes cannot be opened). Mirrors the established "degrade safely,
    never block on an absent fact" convention `classifier_input.py`'s
    resolver already follows. Only a *known*, positive size below the
    floor is treated as ineligible.
    """

    known_and_too_small = (
        classifier_input_width is not None
        and classifier_input_height is not None
        and (
            classifier_input_width < MINIMUM_CLASSIFIER_INPUT_DIMENSION_PX
            or classifier_input_height < MINIMUM_CLASSIFIER_INPUT_DIMENSION_PX
        )
    )
    if known_and_too_small:
        return EligibilityDecision(
            eligible=False,
            reason_code="evidence_below_resolution_floor",
            classifier_input_width=classifier_input_width,
            classifier_input_height=classifier_input_height,
        )
    return EligibilityDecision(
        eligible=True,
        reason_code=None,
        classifier_input_width=classifier_input_width,
        classifier_input_height=classifier_input_height,
    )


# --- Classification abstention ----------------------------------------------

ClassifierInputTier = Literal["subject_focused", "full_frame"]
AbstentionReasonCode = Literal["ambiguous_top_candidates"]

# A real, already-persisted subject-centric crop (same-frame exact box,
# reused persisted crop, or a MegaDetector/activity-derived box) -- BioCLIP
# saw *something* deliberately isolated as the subject.
SUBJECT_FOCUSED_SCORE_FLOOR = 0.70
SUBJECT_FOCUSED_MARGIN_FLOOR = 0.20

# The last-resort fallback: BioCLIP classified the entire scene with no
# subject isolation attempted at all. Real field data (the 2026-08-11/
# 2026-08-14 full-frame "Red-bellied Woodpecker bias" cohort, 8 real
# Visits -- docs/identification-eligibility-abstention-v1-report.md) showed
# this tier can be *confidently* wrong (up to 81.7% score, 0.75 margin) --
# every one of those 8 real cases falls at or below 0.817, so this floor
# sits just above the entire known real cluster.
FULL_FRAME_SCORE_FLOOR = 0.85
FULL_FRAME_MARGIN_FLOOR = 0.40


@dataclass(frozen=True)
class ScoredCandidate:
    """The minimal shape this module needs from one ranked BioCLIP
    candidate -- deliberately not `bioclip_adapter.BioClipRankedSuggestion`
    itself, so this module never needs to import that (heavier, optional-
    runtime-adjacent) module. The caller adapts."""

    label: str
    score: float


@dataclass(frozen=True)
class AbstentionDecision:
    """Whether a real, already-computed ranked result is strong and
    specific enough to present as a species suggestion."""

    abstained: bool
    reason_code: AbstentionReasonCode | None
    tier: ClassifierInputTier
    top1_label: str | None
    top1_score: float | None
    margin: float | None
    score_floor: float
    margin_floor: float
    policy_version: str = IDENTIFICATION_ELIGIBILITY_POLICY_VERSION

    def __post_init__(self) -> None:
        if self.abstained and self.reason_code is None:
            raise ValueError("abstained decision must carry a reason_code")
        if not self.abstained and self.reason_code is not None:
            raise ValueError("non-abstained decision must not carry a reason_code")


def classifier_input_tier(
    *,
    classifier_input_type: str | None,
    crop_source: str,
) -> ClassifierInputTier:
    """Map the existing crop-provenance vocabulary
    (`_ReviewSpeciesCropContext.source` / `.classifier_input_type`) onto the
    two abstention tiers above. `classifier_input_type` (`same_frame_crop` /
    `persisted_crop`) is set only for the Same-Frame Species Evidence v1
    override tier; a plain `crop_source` of `"megadetector"` or `"activity"`
    is also a real, deliberately-isolated subject box (just from an older
    lineage), so both count as `subject_focused`. Only the honest
    `"full_frame"` fallback -- no subject isolation attempted at all -- gets
    the stricter tier."""

    if classifier_input_type in {"same_frame_crop", "persisted_crop"}:
        return "subject_focused"
    if crop_source in {"megadetector", "activity"}:
        return "subject_focused"
    return "full_frame"


def evaluate_classification_abstention(
    candidates: tuple[ScoredCandidate, ...],
    *,
    tier: ClassifierInputTier,
) -> AbstentionDecision:
    """`candidates` must already be ranked best-first (as BioCLIP/
    `_rank_suggestions` returns them) and non-empty -- the caller is
    responsible for the pre-existing "no result at all" case
    (`BioClipNoResultError`), which is a different, already-handled failure
    mode from ambiguity."""

    if not candidates:
        raise ValueError("evaluate_classification_abstention requires at least one candidate")

    score_floor = (
        FULL_FRAME_SCORE_FLOOR if tier == "full_frame" else SUBJECT_FOCUSED_SCORE_FLOOR
    )
    margin_floor = (
        FULL_FRAME_MARGIN_FLOOR if tier == "full_frame" else SUBJECT_FOCUSED_MARGIN_FLOOR
    )
    top1 = candidates[0]
    margin = top1.score - candidates[1].score if len(candidates) > 1 else top1.score
    supported = top1.score >= score_floor and margin >= margin_floor
    return AbstentionDecision(
        abstained=not supported,
        reason_code=None if supported else "ambiguous_top_candidates",
        tier=tier,
        top1_label=top1.label,
        top1_score=top1.score,
        margin=margin,
        score_floor=score_floor,
        margin_floor=margin_floor,
    )


__all__ = [
    "AbstentionDecision",
    "AbstentionReasonCode",
    "ClassifierInputTier",
    "EligibilityDecision",
    "EligibilityReasonCode",
    "FULL_FRAME_MARGIN_FLOOR",
    "FULL_FRAME_SCORE_FLOOR",
    "IDENTIFICATION_ELIGIBILITY_POLICY_VERSION",
    "MINIMUM_CLASSIFIER_INPUT_DIMENSION_PX",
    "ScoredCandidate",
    "SUBJECT_FOCUSED_MARGIN_FLOOR",
    "SUBJECT_FOCUSED_SCORE_FLOOR",
    "classifier_input_tier",
    "evaluate_classification_abstention",
    "evaluate_identification_eligibility",
]
