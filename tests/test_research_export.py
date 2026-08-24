"""Pure-module tests for `mockingbird.research.research_export` (see
docs/research-conservation-export-contract.md "Generic export").
"""

from __future__ import annotations

from datetime import UTC, datetime

from mockingbird.research.eligibility import evaluate_research_export_eligibility
from mockingbird.research.research_export import (
    OBSERVATION_CSV_FIELDNAMES,
    ResearchEvidenceRecord,
    ResearchObservation,
    media_records_for_observations,
    observation_to_csv_row,
    observation_to_json,
    observations_content_fingerprint,
    source_records_for_observations,
    sorted_observations,
)

_ELIGIBLE = evaluate_research_export_eligibility(
    review_status="reviewed", is_authoritative_review=True, is_structurally_superseded=False,
    taxon_category="bird", has_scientific_name=True, has_suggestion=False,
)


def _observation(
    observation_id: str,
    *,
    captured_at: datetime,
    event_id: str = "event-1",
    evidence: tuple[ResearchEvidenceRecord, ...] = (),
    source_id: str = "source-1",
    stream_id: str = "stream-1",
    # Broader Wildlife Maturity v1: every taxon field below defaults to the
    # original hardcoded bird values (no existing call site overrides any
    # of them), but a new test can now build an internally-consistent
    # reviewed-mammal fixture directly -- see docs/broader-wildlife-
    # maturity-v1-contract.md's export section.
    taxon_label: str | None = "northern_cardinal",
    taxon_display_name: str | None = "Northern Cardinal",
    taxon_scientific_name: str | None = "Cardinalis cardinalis",
    taxon_category: str | None = "bird",
    is_species: bool | None = True,
) -> ResearchObservation:
    return ResearchObservation(
        observation_id=observation_id,
        event_id=event_id,
        source_id=source_id,
        source_name="Backyard Feeder",
        stream_id=stream_id,
        stream_name="Feeder Cam",
        acquisition_type="continuous_live",
        acquisition_provider="camera_node",
        is_offline_acquisition=False,
        captured_at=captured_at,
        captured_at_end=None,
        capture_timestamp_confidence="recorded",
        review_status="reviewed",
        reviewed_at=captured_at,
        reviewed_by="jane researcher",
        classification="confirmed_taxon",
        taxon_label=taxon_label,
        taxon_display_name=taxon_display_name,
        taxon_scientific_name=taxon_scientific_name,
        taxon_category=taxon_category,
        is_species=is_species,
        zone_id="zone-1",
        zone_name="Feeder Zone",
        zone_type="feeder",
        resolution_provenance="exact_same_frame",
        evidence=evidence,
        eligibility=_ELIGIBLE,
    )


def test_sorted_observations_is_deterministic_regardless_of_input_order():
    t1 = datetime(2026, 8, 1, tzinfo=UTC)
    t2 = datetime(2026, 8, 2, tzinfo=UTC)
    a = _observation("visit-002", captured_at=t2)
    b = _observation("visit-001", captured_at=t1)
    c = _observation("visit-003", captured_at=t1)  # same timestamp as b, tie-broken by id

    assert [o.observation_id for o in sorted_observations([a, b, c])] == ["visit-001", "visit-003", "visit-002"]
    # Reversed input yields the identical output order.
    assert [o.observation_id for o in sorted_observations([c, b, a])] == ["visit-001", "visit-003", "visit-002"]


def test_observation_to_json_never_includes_a_local_filesystem_path_field():
    obs = _observation("visit-001", captured_at=datetime(2026, 8, 1, tzinfo=UTC))
    payload = observation_to_json(obs)
    for key in payload:
        assert "path" not in key.lower()
        assert "local" not in key.lower()
    assert payload["taxon_scientific_name"] == "Cardinalis cardinalis"


def test_observation_to_csv_row_matches_declared_fieldnames_exactly():
    obs = _observation("visit-001", captured_at=datetime(2026, 8, 1, tzinfo=UTC))
    row = observation_to_csv_row(obs)
    assert set(row.keys()) == set(OBSERVATION_CSV_FIELDNAMES)
    assert row["evidence_ids"] == ""


def test_a_reviewed_mammal_exports_its_real_taxon_identity_not_bird_semantics():
    """Broader Wildlife Maturity v1 (see docs/broader-wildlife-maturity-v1-
    contract.md). A reviewed raccoon (this milestone's newly-seeded
    kind-level taxonomy row) must export its own real category/identity --
    the same generic JSON/CSV shape a bird uses, no coercion into bird
    fields and no dropped observation."""

    obs = _observation(
        "visit-raccoon-1", captured_at=datetime(2026, 8, 1, tzinfo=UTC),
        taxon_label="raccoon", taxon_display_name="Raccoon", taxon_scientific_name=None,
        taxon_category="mammal", is_species=False,
    )
    payload = observation_to_json(obs)
    assert payload["taxon_label"] == "raccoon"
    assert payload["taxon_display_name"] == "Raccoon"
    assert payload["taxon_category"] == "mammal"
    assert payload["taxon_scientific_name"] is None
    assert payload["is_species"] is False

    row = observation_to_csv_row(obs)
    assert set(row.keys()) == set(OBSERVATION_CSV_FIELDNAMES)
    assert row["taxon_label"] == "raccoon"
    assert row["taxon_category"] == "mammal"


def test_media_records_are_deduplicated_and_never_carry_a_local_path():
    shared_evidence = ResearchEvidenceRecord(
        media_id="media-1", evidence_role="identification", captured_at=datetime(2026, 8, 1, tzinfo=UTC),
        width=1920, height=1080, content_type="image/jpeg", resolution_provenance="exact_same_frame",
        is_crop=False, content_sha256="abc123",
    )
    obs_a = _observation("visit-001", captured_at=datetime(2026, 8, 1, tzinfo=UTC), evidence=(shared_evidence,))
    obs_b = _observation("visit-002", captured_at=datetime(2026, 8, 2, tzinfo=UTC), evidence=(shared_evidence,))
    rows = media_records_for_observations([obs_a, obs_b])
    assert len(rows) == 1
    assert rows[0]["media_id"] == "media-1"
    for key in rows[0]:
        assert "path" not in key.lower()


def test_source_records_are_deduplicated_across_shared_source_and_stream():
    obs_a = _observation("visit-001", captured_at=datetime(2026, 8, 1, tzinfo=UTC))
    obs_b = _observation("visit-002", captured_at=datetime(2026, 8, 2, tzinfo=UTC))
    rows = source_records_for_observations([obs_a, obs_b])
    assert len(rows) == 1
    assert rows[0]["source_id"] == "source-1"


def test_fingerprint_is_deterministic_and_order_independent():
    a = _observation("visit-001", captured_at=datetime(2026, 8, 1, tzinfo=UTC))
    b = _observation("visit-002", captured_at=datetime(2026, 8, 2, tzinfo=UTC))
    fingerprint_1 = observations_content_fingerprint([a, b])
    fingerprint_2 = observations_content_fingerprint([b, a])
    assert fingerprint_1 == fingerprint_2
    assert len(fingerprint_1) == 64  # sha256 hex digest


def test_fingerprint_changes_when_a_taxon_correction_changes_exported_truth():
    original = _observation("visit-001", captured_at=datetime(2026, 8, 1, tzinfo=UTC))
    corrected = ResearchObservation(**{**original.__dict__, "taxon_label": "house_finch"})
    assert observations_content_fingerprint([original]) != observations_content_fingerprint([corrected])
