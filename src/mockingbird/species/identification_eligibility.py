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

# Background / Empty Evidence Species-Confidence Correctness v1: the
# resolution floor above answers "is this crop big enough to carry real
# signal," never "does this crop's own geometry still correspond to a real,
# contemporaneous subject observation." Representative Daylight Gate A Field
# Acceptance v5 (docs/representative-daylight-gate-a-field-acceptance-v5-
# report.md, "Defects") reproduced a case neither the resolution floor nor
# `evaluate_classification_abstention` below can catch: a single weak,
# `terminal_reason: maximum_unsupported_duration` MDv5 detection -- a track
# the tracker kept alive on tracker-only support past its last real detector
# confirmation, per `frame_tracker.py` -- localized to empty background, then
# padded to an ordinary-sized "subject-focused" crop (the exact source tier
# -- the `DetectionProposal`-backed `"megadetector"` pick or the legacy
# `"activity"` focus-crop pick -- is not recoverable from the field report
# alone; both map to this same tier and both lack any other same-moment-
# correspondence guarantee, see below) that cleared every existing floor
# (89.9% score, 0.857 margin -- both well clear of even the *stricter*
# `full_frame` floor below, so no score/margin/tier change of any kind can
# catch this case; see the milestone report's "Root cause").
# `MediaAssetModel.geometry_attribution_json` (Localization Attribution /
# Detection Geometry Lineage v1, schema 33) already, independently of
# BioCLIP, records whether the box a classifier-input crop is built from came
# from a genuine matched detector observation this exact moment
# (`geometry_source == "detector"`) or from tracker-only extrapolation/a
# stale carried-forward position (`"tracker"`/`"carried_forward"`) -- exactly
# the "evidence captured after, not at, the triggering detection" mechanism
# `roadmap.md`'s Gate A section already documents. `classifier_input_tier`
# below already treats a sibling field on the same `GeometryAttribution`
# object (`resolution_provenance == "synchronized"`) as informing how much a
# crop should be trusted; this is the same precedent, extended to the two
# crop tiers (`"megadetector"`, and the legacy `"activity"` focus-crop pick
# -- never the Same-Frame/Persisted-Crop/Native-Resolution *override* tiers,
# which are also reported as `source="activity"` but already carry their own
# stronger guarantee; the caller distinguishes by `classifier_input_type`)
# that have no other same-moment-correspondence guarantee at all.
# `docs/localization-attribution-contract.md` is explicit
# that this lineage is "diagnostic, never observational truth" and must never
# be treated as "proof" an animal was or was not present -- this check
# honors that: it never asserts the evidence *is* background, only that the
# system's own basis for trusting this specific crop's correspondence to a
# real moment is too thin to *automatically* claim a species, exactly the
# same revisable, human-overridable abstention this module already applies
# for other reasons. Empirically bounded, not asserted from nothing: measured
# against the real, independently-adjudicated 70-Visit cohort (`data/
# evaluations/scene-confusor-suspicion-v1/`), non-`"detector"` geometry
# sources correctly separate 11/40 real `GROUND_TRUTH=False` Visits (idx 24,
# 39, 41, 43, 44, 45, 49, 65, 68, 81, 85) while wrongly withholding only 2/30
# real `GROUND_TRUTH=True` Visits (idx 57, 73) -- a real, bounded,
# abstention-friendly-doctrine-consistent trade, not a clean discriminator
# (see the milestone report for the full accounting, including the disclosed
# residual this does *not* close: a detector-sourced-but-still-wrong crop,
# e.g. idx=36 in the same cohort, `TestBackgroundEmptyEvidence.
# test_a_high_scoring_real_background_visit_is_a_disclosed_residual`, remains
# exactly as unclosed as before). The real-cohort validation numbers above
# are about `MediaAssetModel.geometry_attribution_json` itself, independent
# of which crop tier read it -- the caller (`product_repository._review_
# species_run_context`) is the one place that decides which crop tiers are
# in scope; see its own comment for exactly why (`"megadetector"` and the
# legacy `"activity"` focus-crop tier, never the same-frame/persisted/
# native-resolution *override* tiers, which already carry their own,
# stronger, separately-validated correspondence guarantees --
# `fov_alignment_proven`/`resolution_provenance` -- that this check must not
# second-guess).
GeometrySource = Literal["detector", "tracker", "carried_forward"]

EligibilityReasonCode = Literal[
    "evidence_below_resolution_floor", "evidence_geometry_uncorroborated"
]


@dataclass(frozen=True)
class EligibilityDecision:
    """Whether identification should even be attempted."""

    eligible: bool
    reason_code: EligibilityReasonCode | None
    classifier_input_width: int | None
    classifier_input_height: int | None
    geometry_source: GeometrySource | None = None
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
    geometry_source: GeometrySource | None = None,
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

    `geometry_source` (see the module-level comment above this function,
    Background / Empty Evidence Species-Confidence Correctness v1): only a
    *known*, non-`"detector"` source is treated as ineligible -- `None`
    (the caller has no geometry-lineage fact for this crop, or deliberately
    did not pass one for a tier this signal was not validated against)
    degrades safely to "no opinion," the same convention the size check
    above already establishes, never a guessed positive.
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
            geometry_source=geometry_source,
        )
    if geometry_source is not None and geometry_source != "detector":
        return EligibilityDecision(
            eligible=False,
            reason_code="evidence_geometry_uncorroborated",
            classifier_input_width=classifier_input_width,
            classifier_input_height=classifier_input_height,
            geometry_source=geometry_source,
        )
    return EligibilityDecision(
        eligible=True,
        reason_code=None,
        classifier_input_width=classifier_input_width,
        classifier_input_height=classifier_input_height,
        geometry_source=geometry_source,
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
    `persisted_crop` / `native_resolution_crop`) is set only for the
    Same-Frame Species Evidence v1 / Source-Resolution + Multi-Frame Species
    Evidence v1 override tiers; a plain `crop_source` of `"megadetector"` or
    `"activity"` is also a real, deliberately-isolated subject box (just
    from an older lineage), so all count as `subject_focused`.
    `native_resolution_crop` is, if anything, a *stronger* subject-focused
    crop than the others (a genuinely higher-resolution image with an
    equally proven correspondence guarantee -- see `GeometryAttribution.
    resolution_provenance == "synchronized"`), never a weaker one; it is
    never given a stricter bar than an ordinary subject-focused crop. Only
    the honest `"full_frame"` fallback -- no subject isolation attempted at
    all -- gets the stricter tier."""

    if classifier_input_type in {"same_frame_crop", "persisted_crop", "native_resolution_crop"}:
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


# --- Multi-frame consensus (Source-Resolution + Multi-Frame Species -------
# --- Evidence v1) --------------------------------------------------------

# Version stamp for the consensus policy specifically -- persisted alongside
# (never instead of) `IDENTIFICATION_ELIGIBILITY_POLICY_VERSION`, the same
# "reproducible/comparable, never silent" convention as the module docstring
# already establishes for the eligibility/abstention policies above.
MULTI_FRAME_CONSENSUS_POLICY_VERSION = "multi-frame-consensus-v1"

ConsensusBasis = Literal[
    "single_frame",
    "unanimous_agreement",
    "majority_agreement",
    "no_confident_frame",
    "cross_frame_disagreement",
]
ConsensusReasonCode = Literal["no_confident_frame_result", "cross_frame_disagreement"]


@dataclass(frozen=True)
class FrameClassificationResult:
    """One already-run classifier result for one candidate evidence frame --
    the minimal shape `evaluate_multi_frame_consensus` needs, deliberately
    not the real BioCLIP/ORM types (same "caller adapts" convention as
    `ScoredCandidate` above). `candidates` must already be ranked best-first
    and non-empty, exactly like `evaluate_classification_abstention`
    requires on its own.

    `media_asset_id` is carried through purely for provenance/reporting
    (which real persisted evidence this result came from) -- never
    interpreted or compared by this module.
    """

    media_asset_id: str
    tier: ClassifierInputTier
    candidates: tuple[ScoredCandidate, ...]

    def __post_init__(self) -> None:
        if not self.candidates:
            raise ValueError("frame_classification_result_requires_at_least_one_candidate")


@dataclass(frozen=True)
class MultiFrameConsensusDecision:
    """Whether several already-evaluated candidate frames, taken together,
    are strong and specific enough to present as one species suggestion.

    Reuses `evaluate_classification_abstention`'s own per-tier score/margin
    floors for each frame independently -- this module never invents a
    second, softer bar for multi-frame evidence, and never blends/averages
    raw scores across frames (see "Multi-frame species inference" in
    docs/source-resolution-multi-frame-species-evidence-contract.md).
    `top1_score`/`margin` (when not abstained) are the *reported* frame's own
    real, unmodified values -- the best-quality frame that actually agrees,
    never a synthesized aggregate.
    """

    abstained: bool
    reason_code: ConsensusReasonCode | None
    consensus_basis: ConsensusBasis
    top1_label: str | None
    top1_score: float | None
    margin: float | None
    reporting_media_asset_id: str | None
    frame_count: int
    confident_frame_count: int
    agreeing_frame_count: int
    per_frame: tuple[AbstentionDecision, ...]
    policy_version: str = MULTI_FRAME_CONSENSUS_POLICY_VERSION

    def __post_init__(self) -> None:
        if self.abstained and self.reason_code is None:
            raise ValueError("abstained consensus decision must carry a reason_code")
        if not self.abstained and self.reason_code is not None:
            raise ValueError("non-abstained consensus decision must not carry a reason_code")
        if self.frame_count < 1:
            raise ValueError("invalid_multi_frame_consensus_decision")
        if not 0 <= self.confident_frame_count <= self.frame_count:
            raise ValueError("invalid_multi_frame_consensus_decision")
        if not 0 <= self.agreeing_frame_count <= self.confident_frame_count:
            raise ValueError("invalid_multi_frame_consensus_decision")


def evaluate_multi_frame_consensus(
    frame_results: tuple[FrameClassificationResult, ...],
) -> MultiFrameConsensusDecision:
    """Combine independently-evaluated candidate-frame classifications into
    one honest decision, without blindly averaging softmax scores across
    frames.

    `frame_results` must be non-empty and already ordered best-quality-first
    (the same order the multi-frame candidate builder already produces --
    see `ProductRepository.species_multi_frame_candidate_plans`): when
    multiple frames agree, the *first* (best-quality) agreeing frame's own
    real score/margin is reported, never a synthesized average -- this is
    the one place frame order affects the outcome, and it is a deliberate
    quality-priority choice, not an arbitrary dependency (see "Source-
    resolution metadata deterministic regardless of candidate ordering" --
    that invariant is about *provenance* fields, not this reporting choice).

    Policy (see "Consensus/abstention policy" in
    docs/source-resolution-multi-frame-species-evidence-contract.md):

    1. Each frame is independently scored via `evaluate_classification_
       abstention`, using *that frame's own* tier floor -- a native-
       resolution frame gets no softer (or stricter) bar than any other
       subject-focused frame.
    2. A single evaluated frame (`len(frame_results) == 1`) degenerates to
       exactly that frame's own decision -- the existing single-frame
       behavior is unchanged, never a new "multi-frame" code path for a
       Visit that only ever had one usable frame.
    3. No confident (non-abstained) frame at all -> abstain
       (`no_confident_frame_result`) -- honest "not clear enough," not a
       forced guess from a weak frame.
    4. Every confident frame agrees on the same top-1 label -> suggest
       (`unanimous_agreement`).
    5. A strict majority (> half) of confident frames agree on one label ->
       suggest (`majority_agreement`) -- "one anomalous frame cannot
       overpower several strong contradictory frames," but a real majority,
       never a plurality (a 2-2 split among four confident frames has no
       majority and abstains, not merely "the largest group").
    6. Otherwise (a genuine, no-majority split) -> abstain
       (`cross_frame_disagreement`) -- disagreement is treated as positive
       evidence for abstention, not discarded.
    """
    if not frame_results:
        raise ValueError("evaluate_multi_frame_consensus requires at least one frame result")

    per_frame = tuple(
        evaluate_classification_abstention(result.candidates, tier=result.tier)
        for result in frame_results
    )
    confident = [
        (result, decision)
        for result, decision in zip(frame_results, per_frame)
        if not decision.abstained
    ]

    def _decision(
        *,
        abstained: bool,
        reason_code: ConsensusReasonCode | None,
        consensus_basis: ConsensusBasis,
        reported: tuple[FrameClassificationResult, AbstentionDecision] | None,
        agreeing_frame_count: int,
    ) -> MultiFrameConsensusDecision:
        return MultiFrameConsensusDecision(
            abstained=abstained,
            reason_code=reason_code,
            consensus_basis=consensus_basis,
            top1_label=reported[1].top1_label if reported is not None else None,
            top1_score=reported[1].top1_score if reported is not None else None,
            margin=reported[1].margin if reported is not None else None,
            reporting_media_asset_id=reported[0].media_asset_id if reported is not None else None,
            frame_count=len(frame_results),
            confident_frame_count=len(confident),
            agreeing_frame_count=agreeing_frame_count,
            per_frame=per_frame,
        )

    if not confident:
        return _decision(
            abstained=True, reason_code="no_confident_frame_result",
            consensus_basis="no_confident_frame", reported=None, agreeing_frame_count=0,
        )

    if len(frame_results) == 1:
        result, decision = confident[0]
        return _decision(
            abstained=False, reason_code=None, consensus_basis="single_frame",
            reported=(result, decision), agreeing_frame_count=1,
        )

    label_counts: dict[str, int] = {}
    first_by_label: dict[str, tuple[FrameClassificationResult, AbstentionDecision]] = {}
    for result, decision in confident:
        label = decision.top1_label
        assert label is not None  # non-abstained AbstentionDecision always carries one
        label_counts[label] = label_counts.get(label, 0) + 1
        first_by_label.setdefault(label, (result, decision))

    if len(label_counts) == 1:
        (label,) = label_counts
        return _decision(
            abstained=False, reason_code=None, consensus_basis="unanimous_agreement",
            reported=first_by_label[label], agreeing_frame_count=len(confident),
        )

    majority_label, majority_count = max(label_counts.items(), key=lambda item: item[1])
    if majority_count * 2 > len(confident):
        return _decision(
            abstained=False, reason_code=None, consensus_basis="majority_agreement",
            reported=first_by_label[majority_label], agreeing_frame_count=majority_count,
        )

    return _decision(
        abstained=True, reason_code="cross_frame_disagreement",
        consensus_basis="cross_frame_disagreement", reported=None, agreeing_frame_count=0,
    )


__all__ = [
    "AbstentionDecision",
    "AbstentionReasonCode",
    "ClassifierInputTier",
    "ConsensusBasis",
    "ConsensusReasonCode",
    "EligibilityDecision",
    "EligibilityReasonCode",
    "FrameClassificationResult",
    "FULL_FRAME_MARGIN_FLOOR",
    "FULL_FRAME_SCORE_FLOOR",
    "GeometrySource",
    "IDENTIFICATION_ELIGIBILITY_POLICY_VERSION",
    "MINIMUM_CLASSIFIER_INPUT_DIMENSION_PX",
    "MULTI_FRAME_CONSENSUS_POLICY_VERSION",
    "MultiFrameConsensusDecision",
    "ScoredCandidate",
    "SUBJECT_FOCUSED_MARGIN_FLOOR",
    "SUBJECT_FOCUSED_SCORE_FLOOR",
    "classifier_input_tier",
    "evaluate_classification_abstention",
    "evaluate_identification_eligibility",
    "evaluate_multi_frame_consensus",
]
