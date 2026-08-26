"""Pure-module tests for `mockingbird.ecological.inaturalist_csv` (see
docs/ecological-interoperability-submission-v1-contract.md "iNaturalist
workflow"). Confirms the exact confirmed 8-column shape and ordering, and
the honest, never-fabricating taxon/geoprivacy mapping rules.
"""

from __future__ import annotations

import csv
import io
from datetime import UTC, datetime

from mockingbird.ecological.adapters import (
    DestinationTaxonomyMapping,
    LocationSelection,
    MediaSelection,
    build_submission_candidate,
)
from mockingbird.ecological.inaturalist_csv import (
    INATURALIST_CSV_COLUMNS,
    build_inaturalist_csv,
    submission_candidate_to_inaturalist_row,
)
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


def _observation(*, eligibility=_ELIGIBLE_NAMED, classification="confirmed_taxon",
                  taxon_label="northern_cardinal", reviewed_by="jane researcher") -> ResearchObservation:
    captured_at = datetime(2026, 8, 1, 18, 30, tzinfo=UTC)  # deliberately not midnight, exercises real conversion
    return ResearchObservation(
        observation_id="visit-001", event_id="event-1", source_id="source-1", source_name="Backyard Feeder",
        stream_id="stream-1", stream_name="Feeder Cam", acquisition_type="continuous_live",
        acquisition_provider="camera_node", is_offline_acquisition=False, captured_at=captured_at,
        captured_at_end=None, capture_timestamp_confidence="recorded", review_status="reviewed",
        reviewed_at=captured_at, reviewed_by=reviewed_by, classification=classification, taxon_label=taxon_label,
        taxon_display_name=("Northern Cardinal" if taxon_label else None), taxon_scientific_name=None,
        taxon_category=("bird" if taxon_label else "unknown"), is_species=(True if taxon_label else False),
        zone_id="zone-1", zone_name="Feeder Zone", zone_type="feeder", resolution_provenance="exact_same_frame",
        evidence=(), eligibility=eligibility,
    )


def _candidate(*, taxonomy_mapping=None, location=LocationSelection(), **observation_kwargs):
    return build_submission_candidate(
        _observation(**observation_kwargs), destination="inaturalist", taxonomy_mapping=taxonomy_mapping,
        location=location, media=MediaSelection(),
    )


def test_csv_columns_match_the_confirmed_8_column_import_shape_in_order():
    assert INATURALIST_CSV_COLUMNS == (
        "species_guess", "observed_on_string", "description", "place_guess",
        "latitude", "longitude", "tags", "geoprivacy",
    )


def test_matched_mapping_uses_the_destination_scientific_name_as_species_guess():
    mapping = DestinationTaxonomyMapping(match_status="matched", destination_taxon_id="9083",
                                          destination_scientific_name="Cardinalis cardinalis")
    row = submission_candidate_to_inaturalist_row(_candidate(taxonomy_mapping=mapping))
    assert row["species_guess"] == "Cardinalis cardinalis"


def test_unresolved_mapping_falls_back_to_the_mockingbird_display_name_never_a_wrong_id():
    row = submission_candidate_to_inaturalist_row(_candidate(taxonomy_mapping=None))
    assert row["species_guess"] == "Northern Cardinal"


def test_confirmed_unidentified_wildlife_leaves_species_guess_blank_never_fabricated():
    row = submission_candidate_to_inaturalist_row(
        _candidate(eligibility=_ELIGIBLE_UNIDENTIFIED, classification="confirmed_unidentified_wildlife",
                   taxon_label=None)
    )
    assert row["species_guess"] == ""


def test_no_location_choice_leaves_lat_long_and_geoprivacy_blank():
    row = submission_candidate_to_inaturalist_row(_candidate(location=LocationSelection(choice="none")))
    assert row["latitude"] == ""
    assert row["longitude"] == ""
    assert row["geoprivacy"] == ""


def test_exact_location_choice_maps_to_open_geoprivacy_with_the_real_coordinate():
    row = submission_candidate_to_inaturalist_row(
        _candidate(location=LocationSelection(choice="exact", latitude=40.015, longitude=-105.2705))
    )
    assert row["geoprivacy"] == "open"
    assert row["latitude"] == "40.015000"
    assert row["longitude"] == "-105.270500"


def test_coarse_location_choice_maps_to_obscured_but_still_carries_the_real_coordinate():
    # See the module's own doctrine comment: "obscured" only affects public
    # display on iNaturalist's side -- the true value is still submitted
    # here, never itself fuzzed by MockingBird (that would be a separate,
    # explicit product choice, not something this row-builder does silently).
    row = submission_candidate_to_inaturalist_row(
        _candidate(location=LocationSelection(choice="coarse", latitude=40.0, longitude=-105.0))
    )
    assert row["geoprivacy"] == "obscured"
    assert row["latitude"] == "40.000000"


def test_observed_on_string_is_iso8601_with_an_explicit_utc_offset():
    row = submission_candidate_to_inaturalist_row(_candidate())
    value = row["observed_on_string"]
    assert "T" in value
    assert value[-6] in ("+", "-") or value.endswith("Z")


def test_description_credits_the_reviewer_when_known():
    row = submission_candidate_to_inaturalist_row(_candidate())
    assert "jane researcher" in row["description"]
    assert "MockingBird" in row["description"]


def test_tags_always_carries_the_mockingbird_marker():
    row = submission_candidate_to_inaturalist_row(_candidate())
    assert row["tags"] == "mockingbird"


def test_build_inaturalist_csv_produces_a_parseable_csv_with_a_header_row():
    csv_text = build_inaturalist_csv([_candidate()])
    reader = csv.DictReader(io.StringIO(csv_text))
    assert reader.fieldnames == list(INATURALIST_CSV_COLUMNS)
    rows = list(reader)
    assert len(rows) == 1
    assert rows[0]["species_guess"] == "Northern Cardinal"


def test_build_inaturalist_csv_never_includes_a_photo_column():
    csv_text = build_inaturalist_csv([_candidate()])
    header = csv_text.splitlines()[0]
    assert "photo" not in header.lower()
