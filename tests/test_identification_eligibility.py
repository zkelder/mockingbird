"""Identification Eligibility + Abstention v1 -- deterministic regression
coverage for the canonical decision boundary
(`mockingbird.species.identification_eligibility`).

Every score/margin used for a "real" case below is copied verbatim from an
already-committed, cited source -- never fabricated -- matching the
established convention in `test_human_background_admission_hard_negative_
2026_08_20.py`. See `scripts/benchmark_identification_eligibility.py` for
the full real-cohort benchmark this module's policy was measured against
before being wired into production, and
docs/identification-eligibility-abstention-v1-report.md for the milestone
report these numbers are drawn from.

Covers milestone items 1-7, 13-14 of the mandatory behavioral-regression
list at the pure decision-function level (deterministic, no DB/API
scaffolding needed to prove a property of the policy itself). Items 8-12
(multi-frame/sibling/reviewed-truth/Visit-continuity behavior, which require
real repository wiring) are covered in
`test_identification_eligibility_regression_2026_08_21.py`.
"""

from __future__ import annotations

import pytest

from mockingbird.species.identification_eligibility import (
    FULL_FRAME_MARGIN_FLOOR,
    FULL_FRAME_SCORE_FLOOR,
    MINIMUM_CLASSIFIER_INPUT_DIMENSION_PX,
    FrameClassificationResult,
    ScoredCandidate,
    SUBJECT_FOCUSED_MARGIN_FLOOR,
    SUBJECT_FOCUSED_SCORE_FLOOR,
    classifier_input_tier,
    evaluate_classification_abstention,
    evaluate_identification_eligibility,
    evaluate_multi_frame_consensus,
)


def _c(label: str, score: float) -> ScoredCandidate:
    return ScoredCandidate(label=label, score=score)


def _frame(
    media_asset_id: str, label: str, score: float, *, second_label: str = "other_species", second_score: float = 0.02,
    tier: str = "subject_focused",
) -> FrameClassificationResult:
    return FrameClassificationResult(
        media_asset_id=media_asset_id,
        tier=tier,
        candidates=(_c(label, score), _c(second_label, second_score)),
    )


# --- Evidence eligibility ---------------------------------------------------


class TestEvidenceEligibility:
    def test_known_normal_size_is_eligible(self) -> None:
        decision = evaluate_identification_eligibility(
            classifier_input_width=200, classifier_input_height=150
        )
        assert decision.eligible is True
        assert decision.reason_code is None

    def test_known_degenerate_size_is_ineligible(self) -> None:
        """Item 5: tiny/far subject below the evidence-quality floor ->
        abstain. A genuinely degenerate crop -- smaller than BioCLIP's own
        224x224 internal resize would ever produce real signal from -- not
        a tuned "small bird" cutoff (see the module docstring)."""

        decision = evaluate_identification_eligibility(
            classifier_input_width=10, classifier_input_height=10
        )
        assert decision.eligible is False
        assert decision.reason_code == "evidence_below_resolution_floor"

    def test_boundary_at_exactly_the_floor_is_eligible(self) -> None:
        decision = evaluate_identification_eligibility(
            classifier_input_width=MINIMUM_CLASSIFIER_INPUT_DIMENSION_PX,
            classifier_input_height=MINIMUM_CLASSIFIER_INPUT_DIMENSION_PX,
        )
        assert decision.eligible is True

    def test_one_pixel_under_the_floor_is_ineligible(self) -> None:
        decision = evaluate_identification_eligibility(
            classifier_input_width=MINIMUM_CLASSIFIER_INPUT_DIMENSION_PX - 1,
            classifier_input_height=200,
        )
        assert decision.eligible is False

    def test_unknown_dimensions_do_not_block_eligibility(self) -> None:
        """A missing size fact is a data-completeness gap, not positive
        evidence of a too-small crop -- a separate, more authoritative
        mechanism (`_load_bioclip_input_image`) already rejects genuinely
        undecodable media. Discovered via a real regression while wiring
        this into `product_repository.py`: test fixtures using placeholder
        image bytes have no decoded `image_width`/`image_height` at all,
        and treating that as "too small" would have wrongly blocked
        identification whenever size metadata is merely absent."""

        decision = evaluate_identification_eligibility(
            classifier_input_width=None, classifier_input_height=None
        )
        assert decision.eligible is True
        assert decision.reason_code is None

    def test_eligible_decision_carries_no_reason_code(self) -> None:
        decision = evaluate_identification_eligibility(
            classifier_input_width=100, classifier_input_height=100
        )
        with pytest.raises(ValueError):
            type(decision)(
                eligible=True,
                reason_code="evidence_below_resolution_floor",
                classifier_input_width=100,
                classifier_input_height=100,
            )

    def test_ineligible_decision_requires_a_reason_code(self) -> None:
        from mockingbird.species.identification_eligibility import EligibilityDecision

        with pytest.raises(ValueError):
            EligibilityDecision(
                eligible=False,
                reason_code=None,
                classifier_input_width=1,
                classifier_input_height=1,
            )


# --- Classifier-input tier mapping ------------------------------------------


class TestClassifierInputTier:
    def test_same_frame_crop_is_subject_focused(self) -> None:
        assert (
            classifier_input_tier(classifier_input_type="same_frame_crop", crop_source="activity")
            == "subject_focused"
        )

    def test_persisted_crop_is_subject_focused(self) -> None:
        assert (
            classifier_input_tier(classifier_input_type="persisted_crop", crop_source="activity")
            == "subject_focused"
        )

    def test_megadetector_crop_source_is_subject_focused(self) -> None:
        assert (
            classifier_input_tier(classifier_input_type=None, crop_source="megadetector")
            == "subject_focused"
        )

    def test_activity_crop_source_is_subject_focused(self) -> None:
        assert (
            classifier_input_tier(classifier_input_type=None, crop_source="activity")
            == "subject_focused"
        )

    def test_full_frame_with_no_override_is_full_frame_tier(self) -> None:
        """Item 14: fallback/full-frame evidence is treated according to
        its real quality/provenance, not silently as equivalent to a
        subject crop -- this is the exact mapping that enforces that."""

        assert (
            classifier_input_tier(classifier_input_type=None, crop_source="full_frame")
            == "full_frame"
        )


# --- Classification abstention: mandatory hard negatives --------------------


class TestMandatoryHardNegatives:
    """Visits 139/140: real person-plus-dog passage, MDv5 `animal`-class
    false detection, real BioCLIP scores on the real `classifier_same_frame`
    crop -- docs/person-background-false-positive-attribution-v1-report.md
    S2-3/S9. Neither may produce a confident named bird species suggestion
    under the new policy (milestone items 2-3). No person recognition/
    human-tracking/face-detection is added or implied -- the assertion is
    only that species identification is unsupported, never that "this is a
    person."""

    def test_visit_139_does_not_produce_a_species_suggestion(self) -> None:
        decision = evaluate_classification_abstention(
            (_c("brown_thrasher", 0.5275),), tier="subject_focused",
        )
        assert decision.abstained is True
        assert decision.reason_code == "ambiguous_top_candidates"

    def test_visit_140_does_not_produce_a_species_suggestion(self) -> None:
        # Visit 140's max_confidence (0.877) exceeded every genuine bird
        # Visit in the same 90-minute session (report S12) -- this is the
        # concrete case proving detector confidence cannot substitute for
        # a visual eligibility/abstention signal. The BioCLIP *species*
        # score used here (0.5986) is the separate, later, real number
        # actually used for species inference.
        decision = evaluate_classification_abstention(
            (_c("red_bellied_woodpecker", 0.5986),), tier="subject_focused",
        )
        assert decision.abstained is True
        assert decision.reason_code == "ambiguous_top_candidates"


class TestBackgroundEmptyEvidence:
    def test_a_real_background_visit_score_is_abstained(self) -> None:
        """Item 4: empty/background evidence -> no forced species name.
        Real score from the independently re-adjudicated 70-Visit cohort
        (`data/evaluations/scene-confusor-suspicion-v1/`, idx=30,
        `GROUND_TRUTH[30] is False`): tufted_titmouse at 20.65%."""

        decision = evaluate_classification_abstention(
            (_c("tufted_titmouse", 0.20652459561824799),), tier="subject_focused",
        )
        assert decision.abstained is True

    def test_a_high_scoring_real_background_visit_is_a_disclosed_residual(self) -> None:
        """Real, disclosed limitation (not silently hidden): a static,
        recurring background region can score confidently and
        consistently -- neither score nor margin distinguishes "confidently
        wrong every time" from "confidently right." Real score from the
        same cohort, idx=36 (`GROUND_TRUTH[36] is False`), mourning_dove at
        99.5%. This residual is a known limit of this v1 policy, addressed
        by the separately-accepted Scene Confusor Suppression v1 admission-
        layer mechanism, not solved twice -- see the final report."""

        decision = evaluate_classification_abstention(
            (_c("mourning_dove", 0.9949748516082764),), tier="subject_focused",
        )
        assert decision.abstained is False  # disclosed, not asserted away


class TestNuthatchDifficultCases:
    """The real 2026-08-11/2026-08-14 full-frame classification cohort
    (data/field-acceptance/2026-08-14-subject-centric-species-crop/
    FINAL-REPORT.md S5) -- this milestone's mandatory difficult-positive
    cases. Full-frame classification (today's real fallback path) must not
    produce a confident wrong species name; abstaining, not a forced
    nuthatch label, is the acceptable v1 outcome (milestone item 6)."""

    def test_low_confidence_ambiguous_full_frame_case_abstains(self) -> None:
        # Visit 014: Tufted Titmouse 36.9% vs Red-bellied Woodpecker 26.9%
        # -- low score AND thin margin; the real bird was later confirmed
        # (via a same-photograph subject-crop diagnostic) to be a House
        # Finch, so this specific full-frame answer was concretely wrong.
        decision = evaluate_classification_abstention(
            (_c("tufted_titmouse", 0.369), _c("red_bellied_woodpecker", 0.269)),
            tier="full_frame",
        )
        assert decision.abstained is True

    def test_high_confidence_wide_margin_full_frame_case_still_abstains(self) -> None:
        """The harder, more important case: Visit 011 scored Red-bellied
        Woodpecker at 79.6% with a 0.73 margin over rank 2 -- a score AND
        margin that would look "confident" by almost any single-threshold
        policy -- yet the crop diagnostic showed the real subject was
        barely in frame. This is exactly why the full-frame tier uses a
        stricter floor (0.85/0.40) grounded in the real full-frame score
        cluster (max 0.817 across all 8 real cases) rather than reusing
        the subject-focused floor: score+margin alone cannot separate this
        case from a well-supported one."""

        decision = evaluate_classification_abstention(
            (_c("red_bellied_woodpecker", 0.796), _c("downy_woodpecker", 0.068)),
            tier="full_frame",
        )
        assert decision.abstained is True
        assert decision.top1_score == pytest.approx(0.796)
        assert decision.margin == pytest.approx(0.728)


class TestStrongPositiveControls:
    """Item 7: strong, clearly-separated classification -> suggest. Item 1:
    strong genuine bird evidence -> species suggestion remains possible."""

    def test_real_authoritative_reviewed_cardinal_suggests(self) -> None:
        # visit-motion-005, local dev DB: reviewed_label=northern_cardinal
        # (authoritative, review_origin in {human, legacy_unattributed}),
        # real bioclip_2 suggestion, megadetector crop_source.
        decision = evaluate_classification_abstention(
            (_c("northern_cardinal", 0.8906447291374207), _c("brown_thrasher", 0.06705698370933533)),
            tier="subject_focused",
        )
        assert decision.abstained is False
        assert decision.top1_label == "northern_cardinal"

    def test_real_production_same_frame_house_finch_suggests(self) -> None:
        # visit-observation-candidate-019, real production same-frame
        # capture (Same-Frame Species Evidence v1 FINAL-REPORT.md): House
        # Finch 93.7%, visually confirmed correct by direct human review.
        decision = evaluate_classification_abstention(
            (_c("house_finch", 0.9374827742576599),), tier="subject_focused",
        )
        assert decision.abstained is False

    def test_real_carolina_wren_suggests(self) -> None:
        # 70-Visit cohort idx=38, GROUND_TRUTH[38] is True -- real species
        # diversity beyond House Finch/Cardinal.
        decision = evaluate_classification_abstention(
            (_c("carolina_wren", 0.9054259061813354),), tier="subject_focused",
        )
        assert decision.abstained is False

    def test_lowest_real_score_in_the_70_visit_cohort_still_suggests(self) -> None:
        # idx=33, GROUND_TRUTH[33] is True -- the floor of what real,
        # confirmed-real evidence actually scores at in this cohort.
        decision = evaluate_classification_abstention(
            (_c("house_finch", 0.783930778503418),), tier="subject_focused",
        )
        assert decision.abstained is False

    def test_clean_diagnostic_subject_crop_suggests_with_wide_margin(self) -> None:
        # Same real photographs as the difficult full-frame cases above,
        # diagnostic subject-crop reproduction (Visit 013): House Finch
        # 99.8% vs Eastern Bluebird 0.07% once actually shown the bird.
        decision = evaluate_classification_abstention(
            (_c("house_finch", 0.998), _c("eastern_bluebird", 0.0007)),
            tier="subject_focused",
        )
        assert decision.abstained is False


class TestFullFrameStricterThanSubjectFocused:
    """Item 14 again, at the numeric-boundary level: the identical score
    is trusted at the subject-focused tier and withheld at the full-frame
    tier -- full-frame evidence is never silently treated as equivalent to
    a real subject crop."""

    def test_identical_score_suggests_at_subject_focused_tier(self) -> None:
        decision = evaluate_classification_abstention(
            (_c("house_finch", 0.80), _c("carolina_wren", 0.05)), tier="subject_focused",
        )
        assert decision.abstained is False

    def test_identical_score_abstains_at_full_frame_tier(self) -> None:
        decision = evaluate_classification_abstention(
            (_c("house_finch", 0.80), _c("carolina_wren", 0.05)), tier="full_frame",
        )
        assert decision.abstained is True


class TestMarginRequirement:
    def test_high_score_but_thin_margin_abstains(self) -> None:
        decision = evaluate_classification_abstention(
            (_c("house_finch", 0.72), _c("purple_finch", 0.60)), tier="subject_focused",
        )
        assert decision.abstained is True
        assert decision.top1_score == pytest.approx(0.72)
        assert decision.margin == pytest.approx(0.12)

    def test_single_candidate_uses_score_as_its_own_margin(self) -> None:
        """A degenerate but real case: exactly one candidate returned.
        Margin cannot be computed against a rank 2 that does not exist, so
        it conservatively falls back to the score itself -- never treated
        as an automatic pass via a fabricated large margin."""

        decision = evaluate_classification_abstention(
            (_c("house_finch", 0.95),), tier="subject_focused",
        )
        assert decision.margin == pytest.approx(0.95)
        assert decision.abstained is False

    def test_empty_candidates_raises_rather_than_silently_passing(self) -> None:
        with pytest.raises(ValueError):
            evaluate_classification_abstention((), tier="subject_focused")


class TestPolicyVersionAndFloorsAreExposed:
    """Calibration policy must be versioned and reproducible (milestone
    item 12) -- every decision carries its own policy version and the
    exact floors it was measured against, not an opaque bool."""

    def test_decision_carries_policy_version_and_floors(self) -> None:
        decision = evaluate_classification_abstention(
            (_c("house_finch", 0.5),), tier="subject_focused",
        )
        assert decision.policy_version == "identification-eligibility-v1"
        assert decision.score_floor == SUBJECT_FOCUSED_SCORE_FLOOR
        assert decision.margin_floor == SUBJECT_FOCUSED_MARGIN_FLOOR

    def test_full_frame_floors_are_stricter_than_subject_focused(self) -> None:
        assert FULL_FRAME_SCORE_FLOOR > SUBJECT_FOCUSED_SCORE_FLOOR
        assert FULL_FRAME_MARGIN_FLOOR > SUBJECT_FOCUSED_MARGIN_FLOOR


class TestMultiFrameConsensus:
    """Source-Resolution + Multi-Frame Species Evidence v1: combining
    several independently-evaluated candidate-frame classifications into
    one honest decision, without blindly averaging softmax scores."""

    def test_empty_frame_results_raises(self) -> None:
        with pytest.raises(ValueError):
            evaluate_multi_frame_consensus(())

    def test_single_confident_frame_degenerates_to_its_own_decision(self) -> None:
        decision = evaluate_multi_frame_consensus((
            _frame("asset-1", "house_finch", 0.93),
        ))
        assert decision.abstained is False
        assert decision.consensus_basis == "single_frame"
        assert decision.top1_label == "house_finch"
        assert decision.top1_score == pytest.approx(0.93)
        assert decision.reporting_media_asset_id == "asset-1"
        assert decision.frame_count == 1
        assert decision.confident_frame_count == 1
        assert len(decision.per_frame) == 1

    def test_single_weak_frame_abstains_exactly_like_todays_single_frame_path(self) -> None:
        decision = evaluate_multi_frame_consensus((
            _frame("asset-1", "house_finch", 0.5, second_score=0.45),
        ))
        assert decision.abstained is True
        assert decision.reason_code == "no_confident_frame_result"
        assert decision.consensus_basis == "no_confident_frame"
        assert decision.top1_label is None

    def test_unanimous_agreement_across_frames_suggests_and_reports_first_frame(self) -> None:
        decision = evaluate_multi_frame_consensus((
            _frame("asset-native", "house_finch", 0.91),
            _frame("asset-same-frame", "house_finch", 0.78),
        ))
        assert decision.abstained is False
        assert decision.consensus_basis == "unanimous_agreement"
        assert decision.top1_label == "house_finch"
        # Reports the *first* (best-quality, caller-ordered) agreeing
        # frame's own real score -- never an average of 0.91 and 0.78.
        assert decision.top1_score == pytest.approx(0.91)
        assert decision.reporting_media_asset_id == "asset-native"
        assert decision.agreeing_frame_count == 2

    def test_one_anomalous_frame_cannot_overpower_a_strong_majority(self) -> None:
        """The exact scenario the milestone names: two strong agreeing
        frames plus one contradictory outlier still yields a majority
        suggestion, not an abstention."""

        decision = evaluate_multi_frame_consensus((
            _frame("asset-1", "house_finch", 0.90),
            _frame("asset-2", "house_finch", 0.85),
            _frame("asset-3", "tufted_titmouse", 0.88),
        ))
        assert decision.abstained is False
        assert decision.consensus_basis == "majority_agreement"
        assert decision.top1_label == "house_finch"
        assert decision.top1_score == pytest.approx(0.90)
        assert decision.agreeing_frame_count == 2

    def test_tied_split_with_no_majority_abstains(self) -> None:
        decision = evaluate_multi_frame_consensus((
            _frame("asset-1", "house_finch", 0.90),
            _frame("asset-2", "house_finch", 0.85),
            _frame("asset-3", "tufted_titmouse", 0.88),
            _frame("asset-4", "tufted_titmouse", 0.83),
        ))
        assert decision.abstained is True
        assert decision.reason_code == "cross_frame_disagreement"
        assert decision.consensus_basis == "cross_frame_disagreement"
        assert decision.top1_label is None
        assert decision.top1_score is None

    def test_two_frame_disagreement_has_no_majority_and_abstains(self) -> None:
        decision = evaluate_multi_frame_consensus((
            _frame("asset-1", "house_finch", 0.90),
            _frame("asset-2", "tufted_titmouse", 0.88),
        ))
        assert decision.abstained is True
        assert decision.reason_code == "cross_frame_disagreement"

    def test_non_confident_frames_are_excluded_from_the_agreement_count(self) -> None:
        """A weak/ambiguous frame does not count as a 'vote' either way --
        only frames that individually clear their own tier's floor
        participate in the majority calculation."""

        decision = evaluate_multi_frame_consensus((
            _frame("asset-1", "house_finch", 0.91),
            _frame("asset-2", "house_finch", 0.80),
            _frame("asset-3", "tufted_titmouse", 0.50, second_score=0.48),  # weak, abstains individually
        ))
        assert decision.abstained is False
        assert decision.consensus_basis == "unanimous_agreement"
        assert decision.frame_count == 3
        assert decision.confident_frame_count == 2
        assert decision.agreeing_frame_count == 2
        assert len(decision.per_frame) == 3

    def test_all_frames_individually_weak_abstains(self) -> None:
        decision = evaluate_multi_frame_consensus((
            _frame("asset-1", "house_finch", 0.5, second_score=0.45),
            _frame("asset-2", "tufted_titmouse", 0.4, second_score=0.35),
        ))
        assert decision.abstained is True
        assert decision.reason_code == "no_confident_frame_result"
        assert decision.confident_frame_count == 0

    def test_full_frame_tier_uses_its_own_stricter_floor_per_frame(self) -> None:
        """A full-frame-tier frame is judged by the full-frame floor, not
        silently relaxed just because it is being evaluated alongside other
        frames."""

        decision = evaluate_multi_frame_consensus((
            _frame("asset-1", "house_finch", 0.80, tier="full_frame"),  # clears subject-focused but not full-frame floor
        ))
        assert decision.abstained is True
        assert decision.reason_code == "no_confident_frame_result"

    def test_decision_is_deterministic_for_the_same_input(self) -> None:
        frames = (
            _frame("asset-1", "house_finch", 0.90),
            _frame("asset-2", "tufted_titmouse", 0.88),
            _frame("asset-3", "house_finch", 0.85),
        )
        first = evaluate_multi_frame_consensus(frames)
        second = evaluate_multi_frame_consensus(frames)
        assert first == second

    def test_per_frame_decisions_are_preserved_in_order(self) -> None:
        decision = evaluate_multi_frame_consensus((
            _frame("asset-1", "house_finch", 0.91),
            _frame("asset-2", "tufted_titmouse", 0.50, second_score=0.48),
        ))
        assert len(decision.per_frame) == 2
        assert decision.per_frame[0].top1_label == "house_finch"
        assert decision.per_frame[0].abstained is False
        assert decision.per_frame[1].abstained is True

    def test_policy_version_is_exposed_and_distinct_from_abstention_version(self) -> None:
        decision = evaluate_multi_frame_consensus((_frame("asset-1", "house_finch", 0.91),))
        assert decision.policy_version == "multi-frame-consensus-v1"

    def test_frame_classification_result_rejects_empty_candidates(self) -> None:
        with pytest.raises(ValueError):
            FrameClassificationResult(media_asset_id="asset-1", tier="subject_focused", candidates=())

    def test_consensus_decision_rejects_inconsistent_abstained_reason_pairing(self) -> None:
        from mockingbird.species.identification_eligibility import MultiFrameConsensusDecision

        with pytest.raises(ValueError):
            MultiFrameConsensusDecision(
                abstained=True, reason_code=None, consensus_basis="no_confident_frame",
                top1_label=None, top1_score=None, margin=None, reporting_media_asset_id=None,
                frame_count=1, confident_frame_count=0, agreeing_frame_count=0, per_frame=(),
            )
        with pytest.raises(ValueError):
            MultiFrameConsensusDecision(
                abstained=False, reason_code="no_confident_frame_result", consensus_basis="single_frame",
                top1_label="house_finch", top1_score=0.9, margin=0.8, reporting_media_asset_id="asset-1",
                frame_count=1, confident_frame_count=1, agreeing_frame_count=1, per_frame=(),
            )
