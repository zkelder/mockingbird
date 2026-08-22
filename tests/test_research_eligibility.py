"""Pure-module tests for `mockingbird.research.eligibility` (see
docs/research-conservation-export-contract.md "Research-safe eligibility").
"""

from __future__ import annotations

from mockingbird.research.eligibility import evaluate_research_export_eligibility


def _eval(**overrides):
    defaults = dict(
        review_status="reviewed",
        is_authoritative_review=True,
        is_structurally_superseded=False,
        taxon_category="bird",
        has_scientific_name=True,
        has_suggestion=False,
    )
    defaults.update(overrides)
    return evaluate_research_export_eligibility(**defaults)


def test_confirmed_reviewed_taxon_is_eligible_as_named_taxon():
    result = _eval()
    assert result.classification == "confirmed_taxon"
    assert result.eligible_as_named_taxon is True
    assert result.eligible_as_unidentified_wildlife is False
    assert result.eligible is True
    assert result.required_reasons == ()


def test_provisional_suggestion_is_never_eligible_as_named_taxon():
    result = _eval(review_status="needs_review", is_authoritative_review=False, has_suggestion=True)
    assert result.classification == "provisional_suggestion"
    assert result.eligible is False
    assert "provisional_suggestion_only" in result.required_reasons


def test_needs_review_with_no_suggestion_is_unresolved():
    result = _eval(review_status="needs_review", is_authoritative_review=False, has_suggestion=False)
    assert result.classification == "unresolved"
    assert result.eligible is False
    assert "not_yet_reviewed" in result.required_reasons


def test_confirmed_unidentified_wildlife_is_honestly_represented_and_eligible():
    result = _eval(taxon_category="unknown")
    assert result.classification == "confirmed_unidentified_wildlife"
    assert result.eligible_as_unidentified_wildlife is True
    assert result.eligible_as_named_taxon is False
    assert result.eligible is True


def test_rejected_false_positive_is_never_eligible():
    result = _eval(review_status="rejected", taxon_category=None)
    assert result.classification == "rejected"
    assert result.eligible is False
    assert "rejected_false_positive" in result.required_reasons


def test_reviewed_false_positive_taxon_is_classified_rejected():
    result = _eval(taxon_category="false_positive")
    assert result.classification == "rejected"
    assert result.eligible is False


def test_non_wildlife_taxon_is_real_but_not_eligible_for_wildlife_export():
    result = _eval(taxon_category="pet")
    assert result.classification == "non_wildlife"
    assert result.eligible is False
    assert "not_wildlife" in result.required_reasons


def test_reviewed_label_with_no_resolvable_taxonomy_row_is_unresolved_not_fabricated():
    result = _eval(taxon_category=None, has_scientific_name=False)
    assert result.classification == "unresolved"
    assert result.eligible is False
    assert "taxon_unresolved" in result.required_reasons
    assert "taxon_identity_incomplete" in result.recommended_reasons


def test_non_authoritative_review_never_becomes_confirmed_truth():
    result = _eval(is_authoritative_review=False)
    assert result.classification == "unresolved"
    assert result.eligible is False
    assert "no_authoritative_review" in result.required_reasons


def test_structurally_superseded_visit_is_excluded_from_current_export():
    result = _eval(is_structurally_superseded=True)
    assert result.classification == "superseded"
    assert result.eligible is False
    assert result.required_reasons == ("structurally_superseded_visit",)


def test_superseded_historical_review_row_is_excluded_from_current_export():
    result = _eval(is_current_effective=False)
    assert result.classification == "superseded"
    assert result.eligible is False
    assert result.required_reasons == ("superseded_by_later_review",)


def test_missing_scientific_name_is_recommended_not_required():
    result = _eval(has_scientific_name=False)
    assert result.eligible is True
    assert "taxon_identity_incomplete" in result.recommended_reasons
    assert result.required_reasons == ()


def test_uncertain_capture_timestamp_is_recommended_not_required():
    result = _eval(capture_timestamp_known=False)
    assert result.eligible is True
    assert "capture_timestamp_uncertain" in result.recommended_reasons
    assert result.required_reasons == ()


def test_missing_evidence_media_is_recommended_not_required():
    result = _eval(has_evidence_media=False)
    assert result.eligible is True
    assert "no_evidence_media" in result.recommended_reasons


def test_unknown_resolution_provenance_is_recommended_not_required():
    result = _eval(resolution_provenance_known=False)
    assert result.eligible is True
    assert "resolution_provenance_unknown" in result.recommended_reasons


def test_privacy_restriction_withholds_an_otherwise_eligible_confirmed_taxon():
    result = _eval(is_privacy_restricted=True)
    assert result.classification == "confirmed_taxon"
    assert result.eligible is False
    assert "privacy_restricted" in result.required_reasons


def test_privacy_restriction_withholds_confirmed_unidentified_wildlife_too():
    result = _eval(taxon_category="unknown", is_privacy_restricted=True)
    assert result.classification == "confirmed_unidentified_wildlife"
    assert result.eligible is False
    assert "privacy_restricted" in result.required_reasons


def test_privacy_flag_is_a_no_op_for_an_already_ineligible_record():
    result = _eval(review_status="rejected", taxon_category=None, is_privacy_restricted=True)
    assert result.required_reasons == ("rejected_false_positive",)
