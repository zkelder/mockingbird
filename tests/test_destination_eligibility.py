"""Pure-module tests for `mockingbird.ecological.destination_eligibility`
(see docs/ecological-interoperability-submission-v1-contract.md "Reviewed-
truth gate" and "Eligibility preview")."""

from __future__ import annotations

from mockingbird.ecological.destination_eligibility import (
    DestinationRequirements,
    evaluate_destination_eligibility,
)
from mockingbird.research.eligibility import evaluate_research_export_eligibility

_ELIGIBLE_NAMED = evaluate_research_export_eligibility(
    review_status="reviewed", is_authoritative_review=True, is_structurally_superseded=False,
    taxon_category="bird", has_scientific_name=True, has_suggestion=False,
)
_ELIGIBLE_UNIDENTIFIED = evaluate_research_export_eligibility(
    review_status="reviewed", is_authoritative_review=True, is_structurally_superseded=False,
    taxon_category="unknown", has_scientific_name=False, has_suggestion=False,
)
_PROVISIONAL = evaluate_research_export_eligibility(
    review_status="needs_review", is_authoritative_review=False, is_structurally_superseded=False,
    taxon_category=None, has_scientific_name=False, has_suggestion=True,
)
_REJECTED = evaluate_research_export_eligibility(
    review_status="rejected", is_authoritative_review=True, is_structurally_superseded=False,
    taxon_category="false_positive", has_scientific_name=False, has_suggestion=False,
)
_PRIVACY_RESTRICTED = evaluate_research_export_eligibility(
    review_status="reviewed", is_authoritative_review=True, is_structurally_superseded=False,
    taxon_category="bird", has_scientific_name=True, has_suggestion=False, is_privacy_restricted=True,
)

_OFFERED = DestinationRequirements(offered=True)
_NOT_OFFERED = DestinationRequirements(offered=False, offered_reason="policy conflict")
_REQUIRES_LOCATION = DestinationRequirements(offered=True, requires_location=True)
_REQUIRES_SPECIES = DestinationRequirements(offered=True, requires_species_level_taxon=True)
_EXCLUDES_UNIDENTIFIED = DestinationRequirements(offered=True, accepts_unidentified_wildlife=False)
_REQUIRES_COUNT = DestinationRequirements(offered=True, requires_count=True)


def _evaluate(research_eligibility, requirements, **kwargs):
    defaults = {"has_taxonomy_mapping": True, "has_location": False, "has_count": True}
    defaults.update(kwargs)
    return evaluate_destination_eligibility(research_eligibility, requirements, **defaults)


def test_underlying_research_ineligibility_always_wins_regardless_of_destination():
    for eligibility in (_PROVISIONAL, _REJECTED, _PRIVACY_RESTRICTED):
        result = _evaluate(eligibility, _OFFERED)
        assert result.status == "excluded"
        assert result.excluded_reasons == eligibility.required_reasons


def test_a_not_offered_destination_is_always_excluded_even_for_a_perfect_record():
    result = _evaluate(_ELIGIBLE_NAMED, _NOT_OFFERED, has_taxonomy_mapping=True, has_location=True)
    assert result.status == "excluded"
    assert result.excluded_reasons == ("destination_not_offered",)


def test_eligible_named_taxon_with_a_resolved_mapping_is_eligible():
    result = _evaluate(_ELIGIBLE_NAMED, _OFFERED, has_taxonomy_mapping=True)
    assert result.eligible
    assert result.status == "eligible"


def test_named_taxon_with_no_resolved_mapping_needs_input():
    result = _evaluate(_ELIGIBLE_NAMED, _OFFERED, has_taxonomy_mapping=False)
    assert result.status == "needs_input"
    assert result.needs_input_reasons == ("taxonomy_mapping_unresolved",)


def test_named_taxon_with_an_ambiguous_mapping_needs_input_distinctly():
    result = _evaluate(
        _ELIGIBLE_NAMED, _OFFERED, has_taxonomy_mapping=False, taxonomy_mapping_ambiguous=True,
    )
    assert result.status == "needs_input"
    assert result.needs_input_reasons == ("taxonomy_mapping_ambiguous",)


def test_confirmed_unidentified_wildlife_never_needs_a_taxonomy_mapping():
    # No taxonomy mapping can exist for an honestly-unresolved species --
    # this must never be reported as a missing/ambiguous mapping gap.
    result = _evaluate(_ELIGIBLE_UNIDENTIFIED, _OFFERED, has_taxonomy_mapping=False)
    assert result.eligible


def test_destination_requiring_species_level_taxon_excludes_unidentified_wildlife():
    result = _evaluate(_ELIGIBLE_UNIDENTIFIED, _REQUIRES_SPECIES, has_taxonomy_mapping=False)
    assert result.status == "excluded"
    assert result.excluded_reasons == ("species_level_taxon_required",)


def test_destination_that_flatly_excludes_unidentified_wildlife():
    result = _evaluate(_ELIGIBLE_UNIDENTIFIED, _EXCLUDES_UNIDENTIFIED, has_taxonomy_mapping=False)
    assert result.status == "excluded"
    assert result.excluded_reasons == ("species_level_taxon_required",)


def test_destination_requiring_location_needs_input_when_absent():
    result = _evaluate(_ELIGIBLE_NAMED, _REQUIRES_LOCATION, has_taxonomy_mapping=True, has_location=False)
    assert result.status == "needs_input"
    assert result.needs_input_reasons == ("location_required",)


def test_destination_requiring_location_is_eligible_once_supplied():
    result = _evaluate(_ELIGIBLE_NAMED, _REQUIRES_LOCATION, has_taxonomy_mapping=True, has_location=True)
    assert result.eligible


def test_multiple_needs_input_reasons_are_all_reported_not_just_the_first():
    result = _evaluate(
        _ELIGIBLE_NAMED, _REQUIRES_LOCATION, has_taxonomy_mapping=False, has_location=False,
    )
    assert result.status == "needs_input"
    assert set(result.needs_input_reasons) == {"taxonomy_mapping_unresolved", "location_required"}


def test_a_destination_requiring_count_never_invents_visit_count_as_individual_count():
    # No real destination in this milestone sets requires_count=True (see
    # Phase 14: MockingBird never turns a Visit count into an individual
    # count), but the general contract must still behave correctly if one
    # ever did -- this proves the plumbing without inventing a count value.
    result = _evaluate(_ELIGIBLE_NAMED, _REQUIRES_COUNT, has_taxonomy_mapping=True, has_count=False)
    assert result.status == "needs_input"
    assert result.needs_input_reasons == ("count_required",)
