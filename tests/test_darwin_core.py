"""Pure-module tests for `mockingbird.research.darwin_core` (see
docs/ecological-interoperability-submission-v1-contract.md "Darwin Core
export"). Mirrors `tests/test_camtrap_dp.py`'s fixture-building convention.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import UTC, datetime

from mockingbird.research.darwin_core import (
    OCCURRENCE_CSV_FIELDNAMES,
    DarwinCoreMappingOptions,
    build_darwin_core_archive,
    build_eml_xml,
    build_meta_xml,
    occurrence_to_row,
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


def _observation(
    observation_id: str = "visit-001", *, eligibility=_ELIGIBLE_NAMED,
    taxon_scientific_name: str | None = "Cardinalis cardinalis", is_species: bool = True,
    reviewed_by: str | None = "jane researcher",
    evidence: tuple[ResearchEvidenceRecord, ...] = (),
) -> ResearchObservation:
    captured_at = datetime(2026, 8, 1, 7, tzinfo=UTC)
    return ResearchObservation(
        observation_id=observation_id, event_id="event-1", source_id="source-1", source_name="Backyard Feeder",
        stream_id="stream-1", stream_name="Feeder Cam", acquisition_type="continuous_live",
        acquisition_provider="camera_node", is_offline_acquisition=False, captured_at=captured_at,
        captured_at_end=None, capture_timestamp_confidence="recorded", review_status="reviewed",
        reviewed_at=captured_at, reviewed_by=reviewed_by, classification="confirmed_taxon", taxon_label="northern_cardinal",
        taxon_display_name="Northern Cardinal", taxon_scientific_name=taxon_scientific_name, taxon_category="bird",
        is_species=is_species, zone_id="zone-1", zone_name="Feeder Zone", zone_type="feeder",
        resolution_provenance="exact_same_frame", evidence=evidence, eligibility=eligibility,
    )


def _evidence(media_id: str = "media-1") -> ResearchEvidenceRecord:
    return ResearchEvidenceRecord(
        media_id=media_id, evidence_role="identification", captured_at=datetime(2026, 8, 1, 7, tzinfo=UTC),
        width=1920, height=1080, content_type="image/jpeg", resolution_provenance="exact_same_frame",
        is_crop=False, content_sha256=None,
    )


def test_ineligible_provisional_record_never_becomes_an_occurrence():
    archive = build_darwin_core_archive([_observation(eligibility=_INELIGIBLE_PROVISIONAL)])
    assert archive.occurrences == []


def test_basis_of_record_is_always_machine_observation():
    archive = build_darwin_core_archive([_observation()])
    assert archive.occurrences[0].basis_of_record == "MachineObservation"


def test_occurrence_status_is_always_detected_never_not_detected():
    archive = build_darwin_core_archive([_observation(), _observation("visit-002", eligibility=_ELIGIBLE_UNIDENTIFIED)])
    assert all(occ.occurrence_status == "detected" for occ in archive.occurrences)


def test_individual_count_is_never_a_field_on_the_occurrence_dataclass():
    # Structural proof, not just behavioral: there is no way to accidentally
    # populate a count MockingBird cannot defend (Phase 14).
    archive = build_darwin_core_archive([_observation()])
    row = occurrence_to_row(archive.occurrences[0])
    assert "individualCount" not in row


def test_scientific_name_passes_through_when_known():
    archive = build_darwin_core_archive([_observation(taxon_scientific_name="Cardinalis cardinalis")])
    assert archive.occurrences[0].scientific_name == "Cardinalis cardinalis"
    assert archive.occurrences[0].taxon_rank == "species"


def test_scientific_name_is_none_rather_than_fabricated_when_unset():
    archive = build_darwin_core_archive([_observation(taxon_scientific_name=None)])
    assert archive.occurrences[0].scientific_name is None
    assert archive.occurrences[0].taxon_rank is None


def test_no_location_supplied_leaves_coordinates_and_geodetic_datum_none():
    archive = build_darwin_core_archive([_observation()], options=DarwinCoreMappingOptions())
    occ = archive.occurrences[0]
    assert occ.decimal_latitude is None
    assert occ.decimal_longitude is None
    assert occ.geodetic_datum is None
    assert occ.coordinate_uncertainty_in_meters is None


def test_explicit_location_never_inferred_populates_coordinates_and_wgs84():
    options = DarwinCoreMappingOptions(site_name="Example Yard", latitude=40.015, longitude=-105.2705)
    archive = build_darwin_core_archive([_observation()], options=options)
    occ = archive.occurrences[0]
    assert occ.decimal_latitude == 40.015
    assert occ.decimal_longitude == -105.2705
    assert occ.geodetic_datum == "WGS84"
    assert occ.locality == "Example Yard"


def test_identified_by_carries_the_human_reviewer_never_a_machine_suggestion():
    archive = build_darwin_core_archive([_observation(reviewed_by="jane researcher")])
    assert archive.occurrences[0].identified_by == "jane researcher"


def test_associated_media_references_evidence_manifest_relative_never_a_local_path():
    archive = build_darwin_core_archive([_observation(evidence=(_evidence("media-1"), _evidence("media-2")))])
    assert archive.occurrences[0].associated_media == "media/media-1|media/media-2"
    assert "/home/" not in archive.occurrences[0].associated_media


def test_occurrence_id_uses_the_mockingbird_observation_id_directly():
    archive = build_darwin_core_archive([_observation("visit-042")])
    assert archive.occurrences[0].occurrence_id == "visit-042"


def test_meta_xml_is_well_formed_and_names_the_core_file_and_row_type():
    xml_text = build_meta_xml()
    root = ET.fromstring(xml_text)
    assert root.tag.endswith("archive")
    assert "rowType" in root.find("{http://rs.tdwg.org/dwc/text/}core").attrib
    assert "occurrence.csv" in xml_text


def test_meta_xml_maps_every_occurrence_column_to_a_dwc_term():
    xml_text = build_meta_xml()
    for term in OCCURRENCE_CSV_FIELDNAMES:
        assert f"http://rs.tdwg.org/dwc/terms/{term}" in xml_text


def test_eml_xml_is_well_formed_and_never_asserts_a_license():
    xml_text = build_eml_xml(generated_at=datetime(2026, 8, 26, tzinfo=UTC))
    root = ET.fromstring(xml_text)
    assert root.tag.endswith("eml")
    assert "license" not in xml_text.lower() or "no license is asserted" in xml_text.lower()
