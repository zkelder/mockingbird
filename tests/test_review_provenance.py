"""Pure unit tests for mockingbird.review_provenance (see
docs/review-decision-provenance-contract.md). No product repository, no
database -- see tests/test_review_decision_provenance.py for the repository/
API-level integration coverage."""

from __future__ import annotations

import pytest

from mockingbird import review_provenance as rp
from mockingbird.observation import evaluation_governance as eg


def test_human_and_imported_curated_are_authority_eligible() -> None:
    assert rp.is_authority_eligible("human") is True
    assert rp.is_authority_eligible("imported_curated") is True


def test_agent_diagnostic_is_never_authority_eligible() -> None:
    assert rp.is_authority_eligible("agent_diagnostic") is False


def test_omitted_origin_is_never_authority_eligible() -> None:
    """The one non-negotiable rule (Part 4): omission must never grant
    authority."""

    assert rp.is_authority_eligible(None) is False


def test_legacy_unattributed_is_authority_eligible_by_deliberate_policy() -> None:
    """This is the backward-compatibility policy choice Part 9 asks for --
    deliberate and documented, distinct from `None` (see the module
    docstring)."""

    assert rp.is_authority_eligible(rp.LEGACY_UNATTRIBUTED_ORIGIN) is True
    assert rp.LEGACY_UNATTRIBUTED_ORIGIN not in rp.REVIEW_ORIGIN_VALUES


@pytest.mark.parametrize("origin", ["imported_curated", "agent_diagnostic"])
def test_identity_required_origins_reject_missing_or_blank_identity(origin: str) -> None:
    with pytest.raises(rp.ReviewProvenanceError, match=f"{origin}_requires_reviewer_identity"):
        rp.validate_review_origin(origin, None)
    with pytest.raises(rp.ReviewProvenanceError, match=f"{origin}_requires_reviewer_identity"):
        rp.validate_review_origin(origin, "   ")


def test_human_origin_does_not_require_reviewer_identity() -> None:
    rp.validate_review_origin("human", None)  # must not raise


def test_unsupported_origin_value_is_rejected() -> None:
    with pytest.raises(rp.ReviewProvenanceError, match="unsupported_review_origin"):
        rp.validate_review_origin("robot_overlord", "some-identity")


def test_legacy_unattributed_cannot_be_claimed_by_a_create_request() -> None:
    assert rp.is_creatable_review_origin(rp.LEGACY_UNATTRIBUTED_ORIGIN) is False
    with pytest.raises(rp.ReviewProvenanceError, match="unsupported_review_origin"):
        rp.validate_review_origin(rp.LEGACY_UNATTRIBUTED_ORIGIN, "someone")


def test_human_origin_conflicting_with_disclosed_notes_is_rejected() -> None:
    with pytest.raises(rp.ReviewProvenanceError, match="human_origin_conflicts_with_disclosed_non_human_review"):
        rp.validate_review_origin(
            "human", None, notes="[AGENT VISUAL REVIEW -- not independently human-confirmed]"
        )


@pytest.mark.parametrize(
    "text",
    [
        "[AGENT VISUAL REVIEW -- 2026-08-10 fresh-cohort field session]",
        "Reviewed by Claude, an LLM assistant.",
        "autonomous re-check of the localization box",
        "AI visual inspection suggests this is grass, not a bird.",
    ],
)
def test_discloses_non_human_review_matches_established_disclosure_convention(text: str) -> None:
    assert rp.discloses_non_human_review(text) is True


def test_discloses_non_human_review_does_not_flag_ordinary_human_notes() -> None:
    assert rp.discloses_non_human_review("Confirmed squirrel activity under the feeder.") is False
    assert rp.discloses_non_human_review(None, None) is False


# --- Composability with the offline evaluation-governance boundary (Part 12 #7) ---


def test_agent_diagnostic_review_origin_is_naturally_representable_as_diagnostic_only() -> None:
    """A ReviewLabel repaired to `agent_diagnostic` provenance (Part 8) and
    a `diagnostic_only` `EvaluationExample` (the earlier Detection Quality
    Accounting v1 governance boundary) describe the *same* underlying fact
    two different ways -- confirm they agree rather than silently diverging
    on what counts as "not human"."""

    identity = "claude-agent-visual-inspection-2026-08-10"
    assert rp.is_authority_eligible("agent_diagnostic") is False

    example = eg.EvaluationExample(
        example_id="visit-observation-candidate-004",
        status="diagnostic_only",
        source=identity,
        description="box lands on empty grass beside a real bird",
    )
    assert example.training_eligible is False
    assert example.evaluation_metric_eligible is False

    # And the same identity string would be rejected outright if a future
    # script carelessly tried to claim `reviewed_truth` with it -- the two
    # modules independently agree this identity self-discloses non-human
    # origin.
    with pytest.raises(eg.EvaluationGovernanceError, match="reviewed_truth_requires_human_reviewer"):
        eg.EvaluationExample(
            example_id="visit-observation-candidate-004",
            status="reviewed_truth",
            source="rescore_visit_truth.py",
            description="box lands on empty grass beside a real bird",
            reviewed_by=identity,
        )
    assert rp.discloses_non_human_review(identity) is True
