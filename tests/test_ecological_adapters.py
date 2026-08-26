"""Pure-module tests for `mockingbird.ecological.adapters` and
`mockingbird.ecological.fingerprint` (see docs/ecological-interoperability-
submission-v1-contract.md "Canonical reviewed external observation",
"Destination decisions", and "Export reproducibility")."""

from __future__ import annotations

from datetime import UTC, datetime

from mockingbird.ecological.adapters import (
    DESTINATION_ADAPTERS,
    DestinationTaxonomyMapping,
    EBirdAdapter,
    INaturalistAdapter,
    LocationSelection,
    MediaSelection,
    build_submission_candidate,
)
from mockingbird.ecological.fingerprint import submission_candidate_fingerprint
from mockingbird.research.eligibility import evaluate_research_export_eligibility
from mockingbird.research.research_export import ResearchObservation

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

_NO_LOCATION = LocationSelection()
_NO_MEDIA = MediaSelection()
_MATCHED_MAPPING = DestinationTaxonomyMapping(
    match_status="matched", destination_taxon_id="9083",
    destination_scientific_name="Cardinalis cardinalis", taxonomy_source_version="inaturalist-v1-taxa-api",
)


def _observation(
    *,
    eligibility=_ELIGIBLE_NAMED,
    observation_id: str = "visit-001",
    classification: str = "confirmed_taxon",
    taxon_label: str | None = "northern_cardinal",
    taxon_scientific_name: str | None = None,
    reviewed_by: str | None = "jane researcher",
) -> ResearchObservation:
    captured_at = datetime(2026, 8, 1, 14, tzinfo=UTC)
    return ResearchObservation(
        observation_id=observation_id, event_id="event-1", source_id="source-1", source_name="Backyard Feeder",
        stream_id="stream-1", stream_name="Feeder Cam", acquisition_type="continuous_live",
        acquisition_provider="camera_node", is_offline_acquisition=False, captured_at=captured_at,
        captured_at_end=None, capture_timestamp_confidence="recorded", review_status="reviewed",
        reviewed_at=captured_at, reviewed_by=reviewed_by, classification=classification, taxon_label=taxon_label,
        taxon_display_name=("Northern Cardinal" if taxon_label else None), taxon_scientific_name=taxon_scientific_name,
        taxon_category=("bird" if taxon_label else "unknown"), is_species=(True if taxon_label else False),
        zone_id="zone-1", zone_name="Feeder Zone", zone_type="feeder", resolution_provenance="exact_same_frame",
        evidence=(), eligibility=eligibility,
    )


def test_ebird_adapter_is_never_offered_and_carries_a_cited_reason():
    adapter = EBirdAdapter()
    requirements = adapter.requirements()
    assert requirements.offered is False
    assert "feeder" in requirements.offered_reason.lower()
    assert "ebird" in requirements.offered_reason.lower() or "eBird" in requirements.offered_reason


def test_inaturalist_adapter_is_offered_and_does_not_require_location_or_count():
    requirements = INaturalistAdapter().requirements()
    assert requirements.offered is True
    assert requirements.requires_location is False
    assert requirements.requires_count is False
    assert requirements.accepts_unidentified_wildlife is True


def test_destination_registry_has_exactly_the_two_researched_destinations():
    assert set(DESTINATION_ADAPTERS.keys()) == {"inaturalist", "ebird"}


def test_build_submission_candidate_for_ebird_is_always_excluded_regardless_of_record_quality():
    candidate = build_submission_candidate(
        _observation(), destination="ebird", taxonomy_mapping=_MATCHED_MAPPING,
        location=LocationSelection(choice="exact", latitude=40.0, longitude=-105.0), media=_NO_MEDIA,
    )
    assert candidate.destination_eligibility.status == "excluded"
    assert candidate.destination_eligibility.excluded_reasons == ("destination_not_offered",)


def test_build_submission_candidate_for_inaturalist_confirmed_taxon_with_mapping_is_eligible():
    candidate = build_submission_candidate(
        _observation(), destination="inaturalist", taxonomy_mapping=_MATCHED_MAPPING,
        location=_NO_LOCATION, media=_NO_MEDIA,
    )
    assert candidate.destination_eligibility.eligible


def test_build_submission_candidate_for_inaturalist_confirmed_taxon_without_mapping_needs_input():
    candidate = build_submission_candidate(
        _observation(), destination="inaturalist", taxonomy_mapping=None, location=_NO_LOCATION, media=_NO_MEDIA,
    )
    assert candidate.destination_eligibility.status == "needs_input"
    assert "taxonomy_mapping_unresolved" in candidate.destination_eligibility.needs_input_reasons


def test_build_submission_candidate_for_inaturalist_unidentified_wildlife_never_needs_a_mapping():
    candidate = build_submission_candidate(
        _observation(eligibility=_ELIGIBLE_UNIDENTIFIED, classification="confirmed_unidentified_wildlife",
                     taxon_label=None),
        destination="inaturalist", taxonomy_mapping=None, location=_NO_LOCATION, media=_NO_MEDIA,
    )
    assert candidate.destination_eligibility.eligible


def test_build_submission_candidate_excludes_a_provisional_record_before_any_destination_check():
    candidate = build_submission_candidate(
        _observation(eligibility=_PROVISIONAL), destination="inaturalist",
        taxonomy_mapping=_MATCHED_MAPPING, location=_NO_LOCATION, media=_NO_MEDIA,
    )
    assert candidate.destination_eligibility.status == "excluded"
    assert candidate.destination_eligibility.excluded_reasons == ("provisional_suggestion_only",)


# --- fingerprint -----------------------------------------------------------


def _candidate(**overrides):
    defaults = dict(
        observation=_observation(), destination="inaturalist", taxonomy_mapping=_MATCHED_MAPPING,
        location=_NO_LOCATION, media=_NO_MEDIA,
    )
    defaults.update(overrides)
    observation = defaults.pop("observation")
    return build_submission_candidate(observation, **defaults)


def test_fingerprint_is_deterministic_for_the_same_inputs():
    assert submission_candidate_fingerprint(_candidate()) == submission_candidate_fingerprint(_candidate())


def test_fingerprint_changes_when_the_underlying_taxon_label_changes():
    original = submission_candidate_fingerprint(_candidate())
    corrected = submission_candidate_fingerprint(
        _candidate(observation=_observation(taxon_label="blue_jay"))
    )
    assert original != corrected


def test_fingerprint_changes_when_the_taxonomy_mapping_changes():
    original = submission_candidate_fingerprint(_candidate())
    remapped = submission_candidate_fingerprint(
        _candidate(taxonomy_mapping=DestinationTaxonomyMapping(match_status="not_found"))
    )
    assert original != remapped


def test_fingerprint_changes_when_the_location_choice_changes():
    original = submission_candidate_fingerprint(_candidate())
    with_location = submission_candidate_fingerprint(
        _candidate(location=LocationSelection(choice="exact", latitude=40.0, longitude=-105.0))
    )
    assert original != with_location


def test_fingerprint_changes_when_the_destination_changes():
    inat = submission_candidate_fingerprint(_candidate())
    ebird = submission_candidate_fingerprint(_candidate(destination="ebird"))
    assert inat != ebird
