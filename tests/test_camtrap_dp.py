"""Pure-module tests for `mockingbird.research.camtrap_dp` (see
docs/research-conservation-export-contract.md "Camtrap DP mapping").
"""

from __future__ import annotations

from datetime import UTC, datetime

from mockingbird.research.camtrap_dp import (
    CamtrapDpMappingOptions,
    build_camtrap_dp_package,
    datapackage_descriptor,
    observation_to_row,
    validate_camtrap_dp_package,
)
from mockingbird.research.eligibility import evaluate_research_export_eligibility
from mockingbird.research.research_export import ResearchEvidenceRecord, ResearchObservation

_ELIGIBLE_NAMED = evaluate_research_export_eligibility(
    review_status="reviewed", is_authoritative_review=True, is_structurally_superseded=False,
    taxon_category="bird", has_scientific_name=True, has_suggestion=False,
)
_ELIGIBLE_UNIDENTIFIED = evaluate_research_export_eligibility(
    review_status="reviewed", is_authoritative_review=True, is_structurally_superseded=False,
    taxon_category="unknown", has_scientific_name=False, has_suggestion=False,
)
_INELIGIBLE_PROVISIONAL = evaluate_research_export_eligibility(
    review_status="needs_review", is_authoritative_review=False, is_structurally_superseded=False,
    taxon_category=None, has_scientific_name=False, has_suggestion=True,
)


_UNSET = object()  # see taxon_display_name/taxon_category/is_species below


def _observation(
    observation_id: str,
    *,
    eligibility,
    captured_at: datetime = datetime(2026, 8, 1, 7, tzinfo=UTC),
    event_id: str = "event-1",
    taxon_label: str | None = "northern_cardinal",
    taxon_display_name: object = _UNSET,
    taxon_scientific_name: str | None = "Cardinalis cardinalis",
    taxon_category: object = _UNSET,
    is_species: object = _UNSET,
    classification: str = "confirmed_taxon",
    evidence: tuple[ResearchEvidenceRecord, ...] = (),
    suggested_taxon_label: str | None = None,
    suggested_taxon_scientific_name: str | None = None,
    suggested_by: str | None = None,
    suggested_confidence: float | None = None,
    reviewed_by: str | None = "jane researcher",
) -> ResearchObservation:
    # Broader Wildlife Maturity v1 (see docs/broader-wildlife-maturity-v1-
    # contract.md): taxon_display_name/taxon_category/is_species used to be
    # *derived* from whether taxon_label was non-None, hardcoded to bird
    # values ("Northern Cardinal"/"bird"/True) -- a caller could not
    # construct an internally-consistent reviewed-mammal fixture (e.g.
    # taxon_label="raccoon" still got display_name="Northern Cardinal",
    # category="bird") without first patching this helper. Every existing
    # call site relies on that exact bird-shaped default (none pass these
    # three params), so the _UNSET sentinel preserves it unchanged while
    # letting a new caller override all three consistently.
    resolved_display_name = (
        ("Northern Cardinal" if taxon_label else None) if taxon_display_name is _UNSET else taxon_display_name
    )
    resolved_category = ("bird" if taxon_label else None) if taxon_category is _UNSET else taxon_category
    resolved_is_species = (True if taxon_label else None) if is_species is _UNSET else is_species
    return ResearchObservation(
        observation_id=observation_id,
        event_id=event_id,
        source_id="source-1",
        source_name="Backyard Feeder",
        stream_id="stream-1",
        stream_name="Feeder Cam",
        acquisition_type="continuous_live",
        acquisition_provider="camera_node",
        is_offline_acquisition=False,
        captured_at=captured_at,
        captured_at_end=None,
        capture_timestamp_confidence="recorded",
        review_status="reviewed",
        reviewed_at=captured_at,
        reviewed_by=reviewed_by,
        classification=classification,
        taxon_label=taxon_label,
        taxon_display_name=resolved_display_name,
        taxon_scientific_name=taxon_scientific_name,
        taxon_category=resolved_category,
        is_species=resolved_is_species,
        zone_id="zone-1",
        zone_name="Feeder Zone",
        zone_type="feeder",
        resolution_provenance="exact_same_frame",
        evidence=evidence,
        eligibility=eligibility,
        suggested_taxon_label=suggested_taxon_label,
        suggested_taxon_scientific_name=suggested_taxon_scientific_name,
        suggested_by=suggested_by,
        suggested_confidence=suggested_confidence,
        suggested_at=captured_at if suggested_taxon_label else None,
    )


def _evidence(media_id: str = "media-1") -> ResearchEvidenceRecord:
    return ResearchEvidenceRecord(
        media_id=media_id, evidence_role="identification", captured_at=datetime(2026, 8, 1, 7, tzinfo=UTC),
        width=1920, height=1080, content_type="image/jpeg", resolution_provenance="exact_same_frame",
        is_crop=False, content_sha256=None,
    )


def test_ineligible_provisional_record_never_becomes_a_camtrap_observation():
    obs = _observation("visit-001", eligibility=_INELIGIBLE_PROVISIONAL, evidence=(_evidence(),))
    package = build_camtrap_dp_package([obs])
    assert package.deployments == []
    assert package.media == []
    assert package.observations == []


def test_confirmed_taxon_produces_one_human_observation_with_scientific_name():
    obs = _observation("visit-001", eligibility=_ELIGIBLE_NAMED, evidence=(_evidence(),))
    package = build_camtrap_dp_package([obs])
    assert len(package.observations) == 1
    human = package.observations[0]
    assert human.classification_method == "human"
    assert human.scientific_name == "Cardinalis cardinalis"
    assert human.observation_type == "animal"
    assert human.classification_probability is None  # never a probability on a human row


def test_confirmed_unidentified_wildlife_is_honest_no_fabricated_species_name():
    obs = _observation(
        "visit-002", eligibility=_ELIGIBLE_UNIDENTIFIED, taxon_label=None, taxon_scientific_name=None,
        classification="confirmed_unidentified_wildlife",
    )
    package = build_camtrap_dp_package([obs])
    assert len(package.observations) == 1
    assert package.observations[0].scientific_name is None
    assert package.observations[0].observation_type == "animal"


# --- Broader Wildlife Maturity v1: a reviewed mammal, not a second bird ----
#
# See docs/broader-wildlife-maturity-v1-contract.md. `_observation`'s bug
# above (category/display-name/is_species silently hardcoded to bird
# values) meant no test here could previously construct an internally-
# consistent reviewed-mammal fixture at all -- these are genuinely new
# coverage, not a copy of an existing bird test with different names.


def test_reviewed_mammal_without_a_scientific_name_exports_honestly_no_fabricated_name():
    """The seeded "raccoon" taxonomy row (Broader Wildlife Maturity v1) has
    no scientific_name on file -- Camtrap DP's real spec has no common-name
    field at the observation level (see the contract doc's export section),
    so this correctly omits scientificName rather than fabricating one or
    silently dropping the whole observation."""

    obs = _observation(
        "visit-raccoon-1", eligibility=_ELIGIBLE_UNIDENTIFIED,
        taxon_label="raccoon", taxon_display_name="Raccoon", taxon_scientific_name=None,
        taxon_category="mammal", is_species=False, evidence=(_evidence(),),
    )
    package = build_camtrap_dp_package([obs])
    assert len(package.observations) == 1
    human = package.observations[0]
    assert human.classification_method == "human"
    assert human.scientific_name is None
    assert human.observation_type == "animal"


def test_reviewed_mammal_with_a_scientific_name_maps_correctly_not_coerced_to_bird_semantics():
    """A taxonomy enriched with a real scientific name (an operator/
    researcher can supply one even though the stock seed does not -- see
    the contract doc) maps identically to the bird path: the same
    `scientificName` field, the same `classification_method == "human"`,
    no separate "mammal observation" shape anywhere in the schema."""

    obs = _observation(
        "visit-raccoon-2", eligibility=_ELIGIBLE_NAMED,
        taxon_label="raccoon", taxon_display_name="Raccoon", taxon_scientific_name="Procyon lotor",
        taxon_category="mammal", is_species=True, evidence=(_evidence(),),
    )
    package = build_camtrap_dp_package([obs])
    assert len(package.observations) == 1
    human = package.observations[0]
    assert human.classification_method == "human"
    assert human.scientific_name == "Procyon lotor"
    assert human.observation_type == "animal"
    assert human.classification_probability is None


def test_machine_suggestion_is_a_separate_row_never_blended_into_human_truth():
    obs = _observation(
        "visit-001", eligibility=_ELIGIBLE_NAMED, evidence=(_evidence(),),
        suggested_taxon_label="house_finch", suggested_taxon_scientific_name="Haemorhous mexicanus",
        suggested_by="bioclip", suggested_confidence=0.62,
    )
    package = build_camtrap_dp_package([obs])
    assert len(package.observations) == 2
    human = next(o for o in package.observations if o.classification_method == "human")
    machine = next(o for o in package.observations if o.classification_method == "machine")
    # The human-validated row keeps the *human* taxon, never the machine's.
    assert human.scientific_name == "Cardinalis cardinalis"
    assert machine.scientific_name == "Haemorhous mexicanus"
    assert machine.classification_probability == 0.62
    assert machine.classified_by == "bioclip"
    assert human.observation_id != machine.observation_id


def test_machine_classifications_can_be_excluded_by_option():
    obs = _observation(
        "visit-001", eligibility=_ELIGIBLE_NAMED,
        suggested_taxon_label="house_finch", suggested_by="bioclip", suggested_confidence=0.62,
    )
    package = build_camtrap_dp_package(
        [obs], options=CamtrapDpMappingOptions(include_machine_classifications=False)
    )
    assert len(package.observations) == 1
    assert package.observations[0].classification_method == "human"


def test_deployment_bounds_reflect_actual_exported_window_not_a_fabricated_install_date():
    early = _observation("visit-001", eligibility=_ELIGIBLE_NAMED, captured_at=datetime(2026, 1, 1, tzinfo=UTC))
    late = _observation("visit-002", eligibility=_ELIGIBLE_NAMED, captured_at=datetime(2026, 6, 1, tzinfo=UTC))
    package = build_camtrap_dp_package([early, late])
    assert len(package.deployments) == 1
    deployment = package.deployments[0]
    assert deployment.deployment_start == datetime(2026, 1, 1, tzinfo=UTC)
    assert deployment.deployment_end == datetime(2026, 6, 1, tzinfo=UTC)


def test_deployment_id_is_deterministic_across_repeated_builds():
    obs = _observation("visit-001", eligibility=_ELIGIBLE_NAMED)
    first = build_camtrap_dp_package([obs])
    second = build_camtrap_dp_package([obs])
    assert first.deployments[0].deployment_id == second.deployments[0].deployment_id


def test_coordinates_are_null_by_default_never_fabricated():
    obs = _observation("visit-001", eligibility=_ELIGIBLE_NAMED)
    package = build_camtrap_dp_package([obs])
    assert package.deployments[0].latitude is None
    assert package.deployments[0].longitude is None


def test_explicit_export_time_coordinate_override_is_honored():
    obs = _observation("visit-001", eligibility=_ELIGIBLE_NAMED)
    package = build_camtrap_dp_package(
        [obs], options=CamtrapDpMappingOptions(latitude=40.0, longitude=-105.0, site_name="Test Yard")
    )
    assert package.deployments[0].latitude == 40.0
    assert package.deployments[0].longitude == -105.0
    assert package.deployments[0].location_name == "Test Yard"


def test_count_is_never_a_field_on_the_camtrap_observation_shape():
    obs = _observation("visit-001", eligibility=_ELIGIBLE_NAMED)
    package = build_camtrap_dp_package([obs])
    row = observation_to_row(package.observations[0])
    assert "count" not in row


def test_media_deduplicated_across_observations_sharing_the_same_evidence():
    shared = _evidence("media-shared")
    a = _observation("visit-001", eligibility=_ELIGIBLE_NAMED, evidence=(shared,))
    b = _observation("visit-002", eligibility=_ELIGIBLE_NAMED, evidence=(shared,), captured_at=datetime(2026, 8, 2, tzinfo=UTC))
    package = build_camtrap_dp_package([a, b])
    assert len(package.media) == 1
    assert package.media[0].media_id == "media-shared"
    assert "path" not in package.media[0].file_path or package.media[0].file_path.startswith("media/")


def test_validator_reports_a_valid_structurally_sound_package():
    obs = _observation("visit-001", eligibility=_ELIGIBLE_NAMED, evidence=(_evidence(),))
    package = build_camtrap_dp_package([obs])
    result = validate_camtrap_dp_package(package)
    assert result.valid is True
    assert result.errors == ()
    # Missing coordinates are disclosed as a warning, never hidden.
    assert any("latitude/longitude" in warning for warning in result.warnings)


def test_validator_catches_a_dangling_deployment_reference():
    obs = _observation("visit-001", eligibility=_ELIGIBLE_NAMED, evidence=(_evidence(),))
    package = build_camtrap_dp_package([obs])
    from dataclasses import replace

    broken_media = [replace(m, deployment_id="does-not-exist") for m in package.media]
    broken_package = replace(package, media=broken_media)
    result = validate_camtrap_dp_package(broken_package)
    assert result.valid is False
    assert any("not in deployments" in error for error in result.errors)


def test_validator_catches_a_human_row_with_a_probability():
    obs = _observation("visit-001", eligibility=_ELIGIBLE_NAMED)
    package = build_camtrap_dp_package([obs])
    from dataclasses import replace

    tainted = [replace(o, classification_probability=0.9) for o in package.observations]
    tainted_package = replace(package, observations=tainted)
    result = validate_camtrap_dp_package(tainted_package)
    assert result.valid is False


def test_datapackage_descriptor_names_the_targeted_spec_version():
    obs = _observation("visit-001", eligibility=_ELIGIBLE_NAMED)
    package = build_camtrap_dp_package([obs])
    descriptor = datapackage_descriptor(package, generated_at=datetime(2026, 8, 22, tzinfo=UTC), software_version="0.1.0")
    assert "1.0.2" in descriptor["profile"]
    resource_names = {resource["name"] for resource in descriptor["resources"]}
    assert resource_names == {"deployments", "media", "observations"}
